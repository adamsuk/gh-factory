import re
from pathlib import Path

from factory._vendor import yaml
from factory.render import detect_codeql_languages, detect_ecosystems, render_codeql, render_dependabot, render_template

ROOT = Path(__file__).resolve().parent.parent


def test_detect_ecosystems():
    paths = [
        "package.json",
        "web/package.json",
        "node_modules/x/package.json",
        "api/requirements-dev.txt",
        "Dockerfile",
        "go.mod",
        "README.md",
    ]
    assert detect_ecosystems(paths) == {
        "npm": ["/", "/web"],
        "pip": ["/api"],
        "gomod": ["/"],
        "docker": ["/"],
        "github-actions": ["/"],
    }


def test_dependabot_is_valid_yaml_with_marker(cfg):
    text = render_dependabot(cfg, ["package.json"])
    assert text.startswith("# factory-managed")
    data = yaml.safe_load(text)
    assert data["version"] == 2
    assert [u["package-ecosystem"] for u in data["updates"]] == ["npm", "github-actions"]


def test_codeql_languages_and_workflow(cfg, baseline):
    langs = detect_codeql_languages(["src/a.ts", "x.py", "dist/b.go", ".github/workflows/ci.yml"])
    assert langs == ["actions", "javascript-typescript", "python"]
    text = render_codeql(cfg, baseline, "o/r", "main", langs)
    data = yaml.safe_load(text)
    include = data["jobs"]["analyze"]["strategy"]["matrix"]["include"]
    assert {i["language"]: i["build-mode"] for i in include} == {"actions": "none", "javascript-typescript": "none", "python": "none"}
    assert data[True]["push"]["branches"] == ["main"]  # YAML 1.1 reads `on` as True
    assert render_codeql(cfg, baseline, "o/r", "main", langs) == text  # deterministic


def test_rendered_templates_are_valid(cfg, baseline):
    from factory.config import FILE_ITEMS
    from factory.render import render_template

    for path in FILE_ITEMS.values():
        if (baseline.files_dir / path).exists():
            text = render_template(baseline, cfg, path, "app")
            assert "{{" not in text, path
            if path.endswith(".yml"):
                yaml.safe_load(text)
    caller = yaml.safe_load(render_template(baseline, cfg, ".github/workflows/changelog.yml", "app"))
    assert caller["jobs"]["changelog"]["uses"] == f"adamsuk/gh-factory/.github/workflows/changelog.yml@{cfg.workflows_ref}"


def test_pip_keeps_lower_bounds(cfg):
    data = yaml.safe_load(render_dependabot(cfg, ["pyproject.toml", "package.json"]))
    by_eco = {u["package-ecosystem"]: u for u in data["updates"]}
    assert by_eco["pip"]["versioning-strategy"] == "increase-if-necessary"
    assert "versioning-strategy" not in by_eco["npm"]


SHA_PIN = re.compile(r"uses: [\w./-]+@[0-9a-f]{40} # \S+$")


def _uses_lines(text):
    return [ln.strip().lstrip("- ") for ln in text.splitlines() if ln.strip().lstrip("- ").startswith("uses:")]


def test_delivered_workflows_pin_every_action_to_a_sha(cfg, baseline):
    codeql = render_codeql(cfg, baseline, "o/r", "main", ["python"])
    caller = render_template(baseline, cfg, ".github/workflows/changelog.yml", "app")
    lines = _uses_lines(codeql) + _uses_lines(caller)
    assert len(lines) == 4
    for line in lines:
        assert SHA_PIN.match(line), line
    assert "changelog.yml@283fa179145dab3b40dbb4b2100fcb50910d7eb1 # main" in caller


def test_own_workflows_are_pinned_and_match_the_baseline(baseline):
    for wf in (ROOT / ".github" / "workflows").glob("*.yml"):
        for line in _uses_lines(wf.read_text()):
            if line.startswith("uses: ./"):
                continue  # a reusable workflow in this repo, run at the same commit
            assert SHA_PIN.match(line), f"{wf.name}: {line}"
            action, _, rest = line.removeprefix("uses: ").partition("@")
            repo = "/".join(action.split("/")[:2])
            if repo in baseline.actions:
                pin = baseline.actions[repo]
                assert rest == f"{pin['sha']} # {pin['version']}", f"{wf.name}: bump baseline/actions.yml with {line}"


def test_baseline_dependabot_always_covers_github_actions(cfg):
    data = yaml.safe_load(render_dependabot(cfg, []))
    assert [u["package-ecosystem"] for u in data["updates"]] == ["github-actions"]


def test_pr_template_changelog_line_reads_well_without_a_changelog(cfg, baseline):
    text = render_template(baseline, cfg, ".github/pull_request_template.md", "app")
    line = next(ln for ln in text.splitlines() if "CHANGELOG" in ln)
    assert line == "- [ ] CHANGELOG.md updated, if this repo keeps one (or the `skip-changelog` label applied)"


def test_issue_template_acceptance_criteria_is_a_placeholder_not_prefilled(cfg, baseline):
    # A prefilled `value` satisfies `required: true` on its own, so an empty checklist could be submitted.
    form = yaml.safe_load(render_template(baseline, cfg, ".github/ISSUE_TEMPLATE/task.yml", "app"))
    acceptance = next(item for item in form["body"] if item.get("id") == "acceptance")
    assert "value" not in acceptance["attributes"]
    assert acceptance["attributes"]["placeholder"].strip().startswith("- [ ]")
    assert acceptance["validations"]["required"] is True
