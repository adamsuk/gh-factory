"""Tests for the dated-entry check in .github/workflows/changelog.yml."""

import os
import stat
import subprocess

import pytest

from factory._vendor import yaml

from .conftest import ROOT

WORKFLOW = ROOT / ".github" / "workflows" / "changelog.yml"

HEAD_BASE = "# Changelog\n\n## [Unreleased]\n\n## 2026-10-29 (x)\n\n### Fixed\n\n- old\n"

FAKE_GH = """#!/bin/sh
case "$*" in
  *pulls/*/files*select*) printf '%s' "$FAKE_PATCH" ;;
  *pulls/*/files*) printf '%s\\n' "$FAKE_FILES" ;;
  *contents/*) printf '%s' "$FAKE_HEAD" ;;
esac
"""


def _run_step():
    wf = yaml.safe_load(WORKFLOW.read_text())
    step = next(s for s in wf["jobs"]["changelog"]["steps"] if "run" in s)
    return step["run"]


def _check(tmp_path, patch, head, *, files="CHANGELOG.md", labels="[]"):
    gh = tmp_path / "gh"
    gh.write_text(FAKE_GH)
    gh.chmod(gh.stat().st_mode | stat.S_IEXEC)
    env = {
        **os.environ,
        "PATH": f"{tmp_path}:{os.environ['PATH']}",
        "PR": "1",
        "REPO": "o/r",
        "HEAD_REPO": "o/r",
        "HEAD_SHA": "abc",
        "LABELS": labels,
        "CHANGELOG_FILE": "CHANGELOG.md",
        "SKIP_LABEL": "skip-changelog",
        "SKIP_AUTHORS": "dependabot[bot]",
        "AUTHOR": "someone",
        "FAKE_PATCH": patch,
        "FAKE_FILES": files,
        "FAKE_HEAD": head,
    }
    return subprocess.run(["bash", "-c", _run_step()], env=env, capture_output=True, text=True)


def test_no_changelog_change_fails(tmp_path):
    r = _check(tmp_path, "", HEAD_BASE, files="README.md")
    assert r.returncode == 1
    assert "Add an entry" in r.stdout


def test_entry_under_unreleased_only_fails(tmp_path):
    head = "# Changelog\n\n## [Unreleased]\n\n- new thing\n\n## 2026-10-29 (x)\n"
    patch = "@@ -2,3 +2,5 @@\n \n ## [Unreleased]\n \n+- new thing\n+\n"
    r = _check(tmp_path, patch, head)
    assert r.returncode == 1
    assert "## YYYY-MM-DD" in r.stdout


def test_new_dated_heading_passes(tmp_path):
    head = "# Changelog\n\n## [Unreleased]\n\n## 2026-11-02 (y)\n\n- thing\n\n## 2026-10-29 (x)\n"
    patch = "@@ -3,2 +3,6 @@\n ## [Unreleased]\n \n+## 2026-11-02 (y)\n+\n+- thing\n+\n"
    assert _check(tmp_path, patch, head).returncode == 0


def test_addition_under_existing_dated_heading_passes(tmp_path):
    head = HEAD_BASE + "- another\n"
    patch = "@@ -8,2 +8,3 @@\n \n - old\n+- another\n"
    r = _check(tmp_path, patch, head)
    assert r.returncode == 0, r.stdout


def test_impossible_date_fails(tmp_path):
    head = "# Changelog\n\n## 2026-13-45\n\n- thing\n"
    patch = "@@ -1,2 +1,5 @@\n # Changelog\n \n+## 2026-13-45\n+\n+- thing\n"
    assert _check(tmp_path, patch, head).returncode == 1


def test_skip_label_skips_everything(tmp_path):
    r = _check(tmp_path, "", HEAD_BASE, files="README.md", labels='["skip-changelog"]')
    assert r.returncode == 0
    assert "Skipped" in r.stdout


@pytest.mark.parametrize("author", ["dependabot[bot]"])
def test_skip_author(tmp_path, author):
    gh = tmp_path / "x"
    gh.write_text("")
    env = {**os.environ, "PR": "1", "SKIP_AUTHORS": author, "AUTHOR": author}
    r = subprocess.run(["bash", "-c", _run_step()], env=env, capture_output=True, text=True)
    assert r.returncode == 0
