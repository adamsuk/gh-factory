"""Render the files the factory delivers, tailored to each repo's contents."""

from __future__ import annotations

import hashlib
import posixpath

from . import yamlio
from .config import Baseline, FactoryConfig

SKIP_DIRS = ("node_modules/", "vendor/", "dist/", "build/", ".venv/", "third_party/")

# Manifest file name -> Dependabot ecosystem.
ECOSYSTEM_FILES = {
    "package.json": "npm",
    "requirements.txt": "pip",
    "pyproject.toml": "pip",
    "Pipfile": "pip",
    "setup.py": "pip",
    "go.mod": "gomod",
    "Cargo.toml": "cargo",
    "Gemfile": "bundler",
    "composer.json": "composer",
    "pom.xml": "maven",
    "build.gradle": "gradle",
    "build.gradle.kts": "gradle",
    "Dockerfile": "docker",
}
ECOSYSTEM_ORDER = ["npm", "pip", "gomod", "cargo", "bundler", "composer", "maven", "gradle", "docker", "github-actions"]

# File extension -> CodeQL language.
CODEQL_EXT = {
    ".js": "javascript-typescript",
    ".jsx": "javascript-typescript",
    ".mjs": "javascript-typescript",
    ".cjs": "javascript-typescript",
    ".ts": "javascript-typescript",
    ".tsx": "javascript-typescript",
    ".py": "python",
    ".go": "go",
    ".java": "java-kotlin",
    ".kt": "java-kotlin",
    ".cs": "csharp",
    ".c": "c-cpp",
    ".cc": "c-cpp",
    ".cpp": "c-cpp",
    ".h": "c-cpp",
    ".hpp": "c-cpp",
    ".rb": "ruby",
    ".swift": "swift",
}
AUTOBUILD = {"go", "c-cpp", "swift"}
PIP_LIKE = {"pip"}


def header(cfg: FactoryConfig) -> str:
    return f"# {cfg.marker}: maintained by https://github.com/{cfg.workflows_repo}. Remove this line to take ownership.\n"


def _kept(paths: list[str]) -> list[str]:
    return [p for p in paths if not any(p.startswith(d) or f"/{d}" in p for d in SKIP_DIRS)]


def detect_ecosystems(paths: list[str]) -> dict[str, list[str]]:
    found: dict[str, set[str]] = {}
    for p in _kept(paths):
        base = posixpath.basename(p)
        eco = ECOSYSTEM_FILES.get(base)
        if base.startswith("requirements") and base.endswith(".txt"):
            eco = "pip"
        if eco:
            d = "/" + posixpath.dirname(p)
            found.setdefault(eco, set()).add(d.rstrip("/") or "/")
    # The factory delivers workflows, so Actions are always kept up to date.
    found.setdefault("github-actions", set()).add("/")
    return {e: sorted(found[e]) for e in ECOSYSTEM_ORDER if e in found}


def detect_codeql_languages(paths: list[str]) -> list[str]:
    langs = set()
    for p in _kept(paths):
        lang = CODEQL_EXT.get(posixpath.splitext(p)[1].lower())
        if lang:
            langs.add(lang)
        if p.startswith(".github/workflows/") and p.endswith((".yml", ".yaml")):
            langs.add("actions")
    return sorted(langs)


def render_dependabot(cfg: FactoryConfig, paths: list[str]) -> str:
    updates = []
    for eco, dirs in detect_ecosystems(paths).items():
        labels = ["dependencies"] + (["github_actions"] if eco == "github-actions" else [])
        entry = {"package-ecosystem": eco, "directories": dirs, "schedule": {"interval": "weekly"}}
        if eco in PIP_LIKE:
            # Keep deliberate lower bounds (e.g. in pyproject.toml); exact pins still get bumped.
            entry["versioning-strategy"] = "increase-if-necessary"
        entry["labels"] = labels
        entry["groups"] = {"minor-and-patch": {"update-types": ["minor", "patch"]}}
        updates.append(entry)
    body = yamlio.dump({"version": 2, "updates": updates})
    return header(cfg) + body


def _cron(full_name: str) -> str:
    h = int(hashlib.sha256(full_name.lower().encode()).hexdigest(), 16)
    return f"{h % 60} {(h // 60) % 24} * * {(h // 1440) % 7}"


def render_codeql(cfg: FactoryConfig, baseline: Baseline, full_name: str, default_branch: str, languages: list[str]) -> str:
    include = "\n".join(
        f"          - language: {lang}\n            build-mode: {'autobuild' if lang in AUTOBUILD else 'none'}" for lang in languages
    )
    return (
        header(cfg)
        + f"""name: CodeQL

on:
  push:
    branches: [{default_branch}]
  pull_request:
    branches: [{default_branch}]
  schedule:
    - cron: "{_cron(full_name)}"

permissions:
  contents: read

jobs:
  analyze:
    name: Analyze (${{{{ matrix.language }}}})
    runs-on: ${{{{ matrix.language == 'swift' && 'macos-latest' || 'ubuntu-latest' }}}}
    permissions:
      actions: read
      contents: read
      security-events: write
    strategy:
      fail-fast: false
      matrix:
        include:
{include}
    steps:
      - uses: {baseline.pin("actions/checkout")}
      - uses: {baseline.pin("github/codeql-action/init")}
        with:
          languages: ${{{{ matrix.language }}}}
          build-mode: ${{{{ matrix.build-mode }}}}
      - uses: {baseline.pin("github/codeql-action/analyze")}
        with:
          category: "/language:${{{{ matrix.language }}}}"
"""
    )


def render_codeowners(cfg: FactoryConfig, owners: list[str]) -> str:
    who = " ".join(owners)
    return (
        f"# {cfg.marker}: maintained by https://github.com/{cfg.workflows_repo}. Remove this line to take ownership.\n"
        f"* {who}\n"
        f"/.github/ {who}\n"
    )


def render_template(baseline: Baseline, cfg: FactoryConfig, rel: str, repo_name: str) -> str:
    text = baseline.template(rel)
    for k, v in {
        "workflows_repo": cfg.workflows_repo,
        "workflows_ref": cfg.workflows_ref,
        "workflows_pin": cfg.workflows_ref
        + (f" # {cfg.workflows_ref_comment}" if cfg.workflows_ref_comment and cfg.workflows_ref_comment != cfg.workflows_ref else ""),
        "repo": repo_name,
        "marker": cfg.marker,
    }.items():
        text = text.replace("{{" + k + "}}", v)
    return text
