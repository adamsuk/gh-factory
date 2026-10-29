"""Tests for the Python embedded in .github/workflows/release.yml."""

import os
import subprocess
import textwrap

import pytest

from factory._vendor import yaml

from .conftest import ROOT

WORKFLOW = ROOT / ".github" / "workflows" / "release.yml"


def _script():
    wf = yaml.safe_load(WORKFLOW.read_text())
    step = next(s for s in wf["jobs"]["release"]["steps"] if "python3 - <<'PY'" in s.get("run", ""))
    body = step["run"].split("<<'PY'\n", 1)[1].rsplit("\nPY", 1)[0]
    return textwrap.dedent(body)


@pytest.fixture(scope="module")
def rel():
    ns = {"__name__": "release_under_test"}
    exec(compile(_script(), str(WORKFLOW), "exec"), ns)
    return ns


@pytest.mark.parametrize(
    ("subject", "body", "level"),
    [
        ("feat: agents section (#8)", "", "minor"),
        ("feat(plan): x", "", "minor"),
        ("fix: placeholder (#10)", "", "patch"),
        ("perf: faster", "", "patch"),
        ("feat!: rework", "", "major"),
        ("fix(cli)!: rename flag", "", "major"),
        ("refactor: x", "BREAKING CHANGE: flag removed", "major"),
        ("chore: sync factory baseline (#5)", "", None),
        ("docs: readme", "", None),
        ("ci: pin", "", None),
        ("test: more", "", None),
        ("chore(release): v0.2.0 (#12)", "", None),
        ("Merge branch main", "", None),
        ("feat:missing space", "", None),
    ],
)
def test_classify(rel, subject, body, level):
    assert rel["classify"](subject, body) == level


def test_bump(rel):
    assert rel["bump"]("0.1.0", "minor") == "0.2.0"
    assert rel["bump"]("0.2.3", "patch") == "0.2.4"
    assert rel["bump"]("0.2.3", "major") == "1.0.0"


CHANGELOG = """# Changelog

## [Unreleased]

## 2026-10-25 (agents section)

### Added

- An `agents:` section.

```yaml
# not a heading
agents: {}
```

## [0.1.0] - 2026-10-25

### 2026-10-25 (v0.1.0)

- Old.
"""


def test_cut_release_moves_unreleased_entries(rel):
    text, notes = rel["cut_release"](CHANGELOG, "0.2.0", "2026-10-26")
    assert "## [Unreleased]\n\n## [0.2.0] - 2026-10-26\n\n### 2026-10-25 (agents section)\n\n#### Added" in text
    assert "# not a heading" in text and "## # not a heading" not in text
    assert text.index("## [0.2.0]") < text.index("## [0.1.0]")
    assert notes.startswith("### 2026-10-25 (agents section)")
    assert rel["section"](text, "0.2.0") == notes
    assert rel["section"](text, "0.1.0") == "### 2026-10-25 (v0.1.0)\n\n- Old."
    assert rel["section"](text, "9.9.9") is None


def test_cut_release_needs_unreleased_heading(rel):
    with pytest.raises(SystemExit):
        rel["cut_release"]("# Changelog\n", "0.2.0", "2026-10-26")


def test_bump_files(rel, tmp_path):
    p = tmp_path / "pyproject.toml"
    p.write_text('[project]\nversion = "0.1.0"\ntarget-version = "py310"\ndeps = ["x==0.1.0"]\n')
    i = tmp_path / "__init__.py"
    i.write_text('__version__ = "0.1.0"\n')
    rel["bump_files"]([str(p), str(i)], "0.1.0", "0.2.0")
    assert p.read_text() == '[project]\nversion = "0.2.0"\ntarget-version = "py310"\ndeps = ["x==0.1.0"]\n'
    assert i.read_text() == '__version__ = "0.2.0"\n'
    with pytest.raises(SystemExit):
        rel["bump_files"]([str(i)], "0.1.0", "0.3.0")


def _git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, check=True, text=True, capture_output=True).stdout.strip()


def test_end_to_end_release_pr_then_release(rel, tmp_path, monkeypatch):
    remote, work, calls = tmp_path / "remote.git", tmp_path / "work", tmp_path / "gh-calls"
    _git(tmp_path, "init", "-q", "--bare", str(remote))
    _git(tmp_path, "init", "-q", "-b", "main", str(work))
    for k, v in {"user.name": "t", "user.email": "t@example.com"}.items():
        _git(work, "config", k, v)
    _git(work, "remote", "add", "origin", str(remote))
    (work / "CHANGELOG.md").write_text("# Changelog\n\n## [Unreleased]\n\n## [0.1.0] - 2026-10-25\n\n- Old.\n")
    (work / "__init__.py").write_text('__version__ = "0.1.0"\n')
    _git(work, "add", "-A")
    _git(work, "commit", "-qm", "feat: first")
    _git(work, "tag", "v0.1.0")
    (work / "CHANGELOG.md").write_text(
        "# Changelog\n\n## [Unreleased]\n\n## 2026-10-26 (thing)\n\n### Fixed\n\n- A fix.\n\n## [0.1.0] - 2026-10-25\n\n- Old.\n"
    )
    _git(work, "commit", "-qam", "fix: a fix (#2)")
    _git(work, "commit", "-q", "--allow-empty", "-m", "chore: tidy (#3)")

    bindir = tmp_path / "bin"
    bindir.mkdir()
    gh = bindir / "gh"
    gh.write_text(f'#!/bin/sh\nprintf "%s\\n" "$*" >> {calls}\n')
    gh.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bindir}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.chdir(work)
    for k, v in {
        "CHANGELOG_FILE": "CHANGELOG.md",
        "VERSION_FILES": "__init__.py",
        "TAG_PREFIX": "v",
        "RELEASE_BRANCH": "release/next",
        "INITIAL_VERSION": "0.0.0",
        "BASE_BRANCH": "main",
    }.items():
        monkeypatch.setenv(k, v)

    rel["main"]()
    log = calls.read_text()
    assert "pr create --head release/next --base main --title chore(release): v0.1.1" in log
    assert _git(remote, "log", "-1", "--format=%s", "release/next") == "chore(release): v0.1.1"
    released = _git(remote, "show", "release/next:CHANGELOG.md")
    assert "## [Unreleased]\n\n## [0.1.1] - " in released and "### 2026-10-26 (thing)\n\n#### Fixed" in released
    assert _git(remote, "show", "release/next:__init__.py") == '__version__ = "0.1.1"'

    # Squash-merge the release PR onto main, then the workflow runs again and releases.
    _git(work, "checkout", "-q", "main")
    _git(work, "merge", "-q", "--squash", "release/next")
    _git(work, "commit", "-qm", "chore(release): v0.1.1 (#4)")
    calls.write_text("")
    rel["main"]()
    log = calls.read_text()
    assert log.startswith("release create v0.1.1 --target ")
    assert "--title v0.1.1 --notes-file" in log

    # Nothing releasable since the tag: no PR, no release.
    _git(work, "tag", "v0.1.1")
    _git(work, "commit", "-q", "--allow-empty", "-m", "docs: words (#5)")
    calls.write_text("")
    rel["main"]()
    assert calls.read_text() == ""


@pytest.mark.parametrize(
    ("entry", "dated", "sub"),
    [
        ("## 2026-10-25 (x)\n\n### Added", "##", "###"),  # house style
        ("### 2026-10-25 (x)\n\n#### Added", "###", "####"),  # one level too deep
        ("#### 2026-10-25 (x)\n\n##### Added", "####", "#####"),  # two levels too deep
        ("# 2026-10-25 (x)\n\n## Added", "#", "##"),  # too shallow
    ],
)
def test_cut_release_relevels_entries_to_house_levels(rel, entry, dated, sub):
    text = f"# Changelog\n\n## [Unreleased]\n\n{entry}\n\n- Thing.\n\n## [0.1.0] - 2026-10-24\n\n### 2026-10-24\n\n- Old.\n"
    new, notes = rel["cut_release"](text, "0.2.0", "2026-10-26")
    assert notes == "### 2026-10-25 (x)\n\n#### Added\n\n- Thing."
    assert "## [0.2.0] - 2026-10-26\n\n### 2026-10-25 (x)\n\n#### Added\n\n- Thing.\n\n## [0.1.0]" in new


def test_relevel_handles_mixed_depths_nesting_fences_and_undated_headings(rel):
    block = "\n".join(
        [
            "### Note before any entry",
            "",
            "#### Detail",
            "",
            "## 2026-10-25 (house)",
            "",
            "### Added",
            "",
            "#### Sub-point",
            "",
            "```md",
            "## 2026-01-01 not a heading",
            "```",
            "",
            "~~~",
            "```",
            "# still fenced",
            "~~~ not a close",
            "~~~",
            "",
            "#### 2026-10-24 (too deep)",
            "",
            "##### Fixed",
            "",
            "##### Changed",
            "",
            "#### 2026-10-23 (no subsections)",
            "",
            "- Plain.",
        ]
    )
    heads = [line for line in rel["_relevel"](block).splitlines() if line.startswith("#")]
    assert heads == [
        "### Note before any entry",
        "#### Detail",
        "### 2026-10-25 (house)",
        "#### Added",
        "##### Sub-point",
        "## 2026-01-01 not a heading",
        "# still fenced",
        "### 2026-10-24 (too deep)",
        "#### Fixed",
        "#### Changed",
        "### 2026-10-23 (no subsections)",
    ]


def test_changelog_release_sections_use_house_levels():
    """Every dated entry under a released version is `###`, and its shallowest subsection is `####`."""
    import re

    text = (ROOT / "CHANGELOG.md").read_text()
    unreleased = re.search(r"^## \[Unreleased\]", text, re.M).end()
    released = text[unreleased:]
    released = released[re.search(r"^## \[", released, re.M).start() :]
    fence, entries = "", []  # entries: [dated heading line, [subsection levels]]
    for line in released.splitlines():
        f = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", line)
        if f and not fence:
            fence = f.group(1)
            continue
        if f and fence and f.group(1)[0] == fence[0] and len(f.group(1)) >= len(fence) and not f.group(2).strip():
            fence = ""
            continue
        m = None if fence else re.match(r"^(#+) +(.*)$", line)
        if not m or m.group(1) == "##":
            continue
        if re.match(r"\d{4}-\d{2}-\d{2}\b", m.group(2)):
            assert len(m.group(1)) == 3, line
            entries.append([line, []])
        else:
            assert entries and len(m.group(1)) >= 4, line
            entries[-1][1].append(len(m.group(1)))
    assert entries
    for head, subs in entries:
        assert not subs or min(subs) == 4, head


def test_release_attests_source_archive():
    wf = yaml.safe_load(WORKFLOW.read_text())
    job = wf["jobs"]["release"]
    assert job["permissions"]["id-token"] == "write"
    assert job["permissions"]["attestations"] == "write"
    steps = job["steps"]
    attest = next(s for s in steps if s.get("uses", "").startswith("actions/attest-build-provenance@"))
    assert len(attest["uses"].split("@")[1].split()[0]) == 40
    assert attest["if"] == "steps.release.outputs.tag != ''"
    assert "steps.archive.outputs.path" in attest["with"]["subject-path"]
    assert any("gh release upload" in s.get("run", "") for s in steps)


def test_release_archive_is_rerun_safe_and_slash_safe():
    text = WORKFLOW.read_text()
    wf = yaml.safe_load(text)
    steps = wf["jobs"]["release"]["steps"]
    archive = next(s for s in steps if s.get("id") == "archive")["run"]
    assert "--clobber" in archive
    assert "${TAG//\\//-}" in archive
    assert 'gh release upload "$TAG"' in archive
    attest = next(s for s in steps if s.get("uses", "").startswith("actions/attest-build-provenance@"))
    assert attest["continue-on-error"] is True
    # The already-tagged early return must still write the tag output.
    exists = text.split("already exists", 1)[1].split("return", 1)[0]
    assert "GITHUB_OUTPUT" in exists
