import yaml

from factory.render import detect_codeql_languages, detect_ecosystems, render_codeql, render_dependabot


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


def test_codeql_languages_and_workflow(cfg):
    langs = detect_codeql_languages(["src/a.ts", "x.py", "dist/b.go", ".github/workflows/ci.yml"])
    assert langs == ["actions", "javascript-typescript", "python"]
    text = render_codeql(cfg, "o/r", "main", langs)
    data = yaml.safe_load(text)
    include = data["jobs"]["analyze"]["strategy"]["matrix"]["include"]
    assert {i["language"]: i["build-mode"] for i in include} == {"actions": "none", "javascript-typescript": "none", "python": "none"}
    assert data[True]["push"]["branches"] == ["main"]  # YAML 1.1 reads `on` as True
    assert render_codeql(cfg, "o/r", "main", langs) == text  # deterministic


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
    assert caller["jobs"]["changelog"]["uses"] == "adamsuk/factory/.github/workflows/changelog.yml@main"
