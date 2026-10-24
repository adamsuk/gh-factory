"""Load factory.yml, the baseline, and a repo's own .github/factory.yml."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

# Items a repo can skip in its .github/factory.yml.
FILE_ITEMS = {
    "pr-template": ".github/pull_request_template.md",
    "issue-template": ".github/ISSUE_TEMPLATE/task.yml",
    "codeowners": ".github/CODEOWNERS",
    "dependabot": ".github/dependabot.yml",
    "codeql": ".github/workflows/codeql.yml",
    "changelog-check": ".github/workflows/changelog.yml",
    "changelog-stub": "CHANGELOG.md",
}
ITEMS = {"settings", "secret-scanning", "vulnerability-alerts", "ruleset", "labels", "files", *FILE_ITEMS}
OVERRIDE_KEYS = {"skip", "approvals", "required_checks", "codeowners"}
OVERRIDE_PATH = ".github/factory.yml"


class ConfigError(ValueError):
    pass


@dataclass
class FactoryConfig:
    owners: list[str]
    topic: str = "factory"
    approvals: int = 0
    codeowners: list[str] = field(default_factory=lambda: ["@adamsuk"])
    required_checks: list[str] = field(default_factory=list)
    sync_branch: str = "factory/sync"
    marker: str = "factory-managed"
    workflows_repo: str = "adamsuk/factory"
    workflows_ref: str = "main"


@dataclass
class Baseline:
    settings: dict[str, Any]
    security: dict[str, Any]
    ruleset: dict[str, Any]
    labels: list[dict[str, str]]
    files_dir: Path

    def template(self, rel: str) -> str:
        return (self.files_dir / rel).read_text()


@dataclass
class RepoOverrides:
    skip: set[str] = field(default_factory=set)
    approvals: int | None = None
    required_checks: list[str] | None = None
    codeowners: list[str] | None = None

    def skips(self, item: str) -> bool:
        if item in self.skip:
            return True
        return item in FILE_ITEMS and "files" in self.skip


def load_factory_config(path: str | Path) -> FactoryConfig:
    raw = yaml.safe_load(Path(path).read_text()) or {}
    owners = raw.get("owners") or []
    if not owners or not all(isinstance(o, str) for o in owners):
        raise ConfigError("factory.yml: `owners` must be a non-empty list of account names")
    d = raw.get("defaults") or {}
    cfg = FactoryConfig(owners=owners)
    cfg.topic = raw.get("topic", cfg.topic)
    cfg.approvals = int(d.get("approvals", cfg.approvals))
    cfg.codeowners = list(d.get("codeowners", cfg.codeowners))
    cfg.required_checks = list(d.get("required_checks", cfg.required_checks) or [])
    for k in ("sync_branch", "marker", "workflows_repo", "workflows_ref"):
        if k in raw:
            setattr(cfg, k, str(raw[k]))
    return cfg


def load_baseline(root: str | Path) -> Baseline:
    root = Path(root)
    settings = yaml.safe_load((root / "settings.yml").read_text()) or {}
    return Baseline(
        settings=settings.get("repository") or {},
        security=settings.get("security") or {},
        ruleset=yaml.safe_load((root / "ruleset.yml").read_text()) or {},
        labels=yaml.safe_load((root / "labels.yml").read_text()) or [],
        files_dir=root / "files",
    )


def parse_overrides(text: str | None) -> RepoOverrides:
    """Parse and validate a repo's .github/factory.yml. Raises ConfigError."""
    if not text or not text.strip():
        return RepoOverrides()
    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as e:
        raise ConfigError(f"{OVERRIDE_PATH} is not valid YAML: {e}") from e
    if raw is None:
        return RepoOverrides()
    if not isinstance(raw, dict):
        raise ConfigError(f"{OVERRIDE_PATH} must be a mapping")
    unknown = set(raw) - OVERRIDE_KEYS
    if unknown:
        raise ConfigError(f"{OVERRIDE_PATH}: unknown keys {sorted(unknown)}; allowed {sorted(OVERRIDE_KEYS)}")
    ov = RepoOverrides()
    skip = raw.get("skip") or []
    if not isinstance(skip, list):
        raise ConfigError(f"{OVERRIDE_PATH}: `skip` must be a list")
    bad = set(skip) - ITEMS
    if bad:
        raise ConfigError(f"{OVERRIDE_PATH}: unknown skip items {sorted(bad)}; allowed {sorted(ITEMS)}")
    ov.skip = set(skip)
    if "approvals" in raw:
        a = raw["approvals"]
        if not isinstance(a, int) or isinstance(a, bool) or not 0 <= a <= 10:
            raise ConfigError(f"{OVERRIDE_PATH}: `approvals` must be an integer 0-10")
        ov.approvals = a
    for key in ("required_checks", "codeowners"):
        if key in raw:
            v = raw[key] or []
            if not isinstance(v, list) or not all(isinstance(x, str) and x.strip() for x in v):
                raise ConfigError(f"{OVERRIDE_PATH}: `{key}` must be a list of strings")
            setattr(ov, key, list(v))
    return ov
