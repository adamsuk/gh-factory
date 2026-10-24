"""Work out, read-only, what the factory would change in one repo."""

from __future__ import annotations

import base64
import json
import urllib.parse
from dataclasses import dataclass, field
from typing import Any

from . import render
from .client import ApiError, Client
from .config import (
    FILE_ITEMS,
    OVERRIDE_PATH,
    Baseline,
    ConfigError,
    FactoryConfig,
    RepoOverrides,
    parse_overrides,
)

# Actions that change something. Everything else is informational.
WRITE_ACTIONS = {"create", "update", "enable", "open-pr", "update-pr"}


@dataclass
class Change:
    item: str
    action: str  # create | update | enable | open-pr | update-pr | drift | unavailable | skipped | error
    target: str
    detail: str = ""
    payload: Any = None

    @property
    def writes(self) -> bool:
        return self.action in WRITE_ACTIONS


@dataclass
class RepoPlan:
    full_name: str
    default_branch: str = "main"
    changes: list[Change] = field(default_factory=list)
    files: dict[str, str] = field(default_factory=dict)  # path -> content to commit on the sync branch
    open_pr: dict | None = None

    @property
    def owner(self) -> str:
        return self.full_name.split("/")[0]

    @property
    def name(self) -> str:
        return self.full_name.split("/")[1]

    @property
    def has_writes(self) -> bool:
        return any(c.writes for c in self.changes)

    @property
    def errors(self) -> list[Change]:
        return [c for c in self.changes if c.action == "error"]

    def add(self, *args, **kwargs) -> Change:
        c = Change(*args, **kwargs)
        self.changes.append(c)
        return c


def _q(s: str) -> str:
    return urllib.parse.quote(s, safe="")


def read_file(client: Client, full_name: str, path: str, ref: str) -> str | None:
    try:
        data = client.get(f"/repos/{full_name}/contents/{urllib.parse.quote(path)}", {"ref": ref})
    except ApiError as e:
        if e.status == 404:
            return None
        raise
    if not isinstance(data, dict) or data.get("type") != "file":
        return None
    return base64.b64decode(data.get("content", "")).decode("utf-8", errors="replace")


def _public(repo: dict) -> bool:
    return repo.get("visibility", "private" if repo.get("private") else "public") == "public"


def _feature_on(repo: dict, *keys: str) -> bool:
    sa = repo.get("security_and_analysis") or {}
    return any((sa.get(k) or {}).get("status") == "enabled" for k in keys)


# ---------------------------------------------------------------- settings


def plan_settings(plan: RepoPlan, repo: dict, baseline: Baseline) -> None:
    diff = {k: v for k, v in baseline.settings.items() if repo.get(k) != v}
    if diff:
        detail = ", ".join(f"{k}: {json.dumps(repo.get(k))} → {json.dumps(v)}" for k, v in diff.items())
        plan.add("settings", "update", "repository settings", detail, diff)


def plan_secret_scanning(plan: RepoPlan, repo: dict, baseline: Baseline) -> None:
    wanted = [k for k in ("secret_scanning", "secret_scanning_push_protection") if baseline.security.get(k)]
    if not wanted:
        return
    if not (_public(repo) or _feature_on(repo, "advanced_security", "secret_protection")):
        plan.add("secret-scanning", "unavailable", "secret scanning", "private repo without GitHub Secret Protection/Advanced Security")
        return
    sa = repo.get("security_and_analysis") or {}
    todo = [k for k in wanted if (sa.get(k) or {}).get("status") != "enabled"]
    if todo:
        plan.add(
            "secret-scanning",
            "enable",
            "secret scanning",
            ", ".join(todo),
            {"security_and_analysis": {k: {"status": "enabled"} for k in todo}},
        )


def plan_vulnerability_alerts(plan: RepoPlan, client: Client, baseline: Baseline) -> None:
    if not baseline.security.get("vulnerability_alerts"):
        return
    status = client.status(f"/repos/{plan.full_name}/vulnerability-alerts")
    if status == 204:
        return
    if status == 404:
        plan.add("vulnerability-alerts", "enable", "Dependabot vulnerability alerts")
    else:
        plan.add("vulnerability-alerts", "error", "Dependabot vulnerability alerts", f"could not read status (HTTP {status})")


# ---------------------------------------------------------------- ruleset


def desired_ruleset(baseline: Baseline, approvals: int, checks: list[str]) -> dict:
    rs = baseline.ruleset
    pr = {
        "required_approving_review_count": approvals,
        "dismiss_stale_reviews_on_push": bool(rs.get("pull_request", {}).get("dismiss_stale_reviews_on_push", False)),
        "require_code_owner_review": bool(rs.get("pull_request", {}).get("require_code_owner_review", False)),
        "require_last_push_approval": bool(rs.get("pull_request", {}).get("require_last_push_approval", False)),
        "required_review_thread_resolution": bool(rs.get("pull_request", {}).get("required_review_thread_resolution", False)),
    }
    methods = rs.get("pull_request", {}).get("allowed_merge_methods")
    if methods:
        pr["allowed_merge_methods"] = list(methods)
    rules: list[dict] = []
    if rs.get("block_deletion", True):
        rules.append({"type": "deletion"})
    if rs.get("block_force_push", True):
        rules.append({"type": "non_fast_forward"})
    rules.append({"type": "pull_request", "parameters": pr})
    if checks:
        rules.append(
            {
                "type": "required_status_checks",
                "parameters": {
                    "strict_required_status_checks_policy": bool(rs.get("strict_required_status_checks_policy", False)),
                    "required_status_checks": [{"context": c} for c in checks],
                },
            }
        )
    return {
        "name": rs.get("name", "factory-main"),
        "target": "branch",
        "enforcement": rs.get("enforcement", "active"),
        "bypass_actors": [],
        "conditions": {"ref_name": {"include": list(rs.get("include", ["~DEFAULT_BRANCH"])), "exclude": []}},
        "rules": rules,
    }


def _subset(want: Any, have: Any) -> bool:
    """True when every key in `want` matches `have` (extra keys in `have` are ignored)."""
    if isinstance(want, dict):
        return isinstance(have, dict) and all(_subset(v, have.get(k)) for k, v in want.items())
    if isinstance(want, list):
        if not isinstance(have, list) or len(want) != len(have):
            return False
        if all(isinstance(x, dict) and "context" in x for x in want):
            return sorted(x["context"] for x in want) == sorted((y or {}).get("context") for y in have)
        if all(isinstance(x, str) for x in want):
            return sorted(want) == sorted(have)
        return all(_subset(a, b) for a, b in zip(want, have, strict=True))
    return want == have


def ruleset_diff(existing: dict, desired: dict) -> list[str]:
    reasons = []
    for k in ("target", "enforcement", "conditions"):
        if not _subset(desired[k], existing.get(k)):
            reasons.append(k)
    if existing.get("bypass_actors"):
        reasons.append("bypass_actors")
    have = {r.get("type"): r for r in existing.get("rules") or []}
    want = {r["type"]: r for r in desired["rules"]}
    for t in sorted(set(have) | set(want)):
        if t not in want:
            reasons.append(f"remove rule {t}")
        elif t not in have:
            reasons.append(f"add rule {t}")
        elif not _subset(want[t].get("parameters", {}), have[t].get("parameters") or {}):
            reasons.append(f"rule {t}")
    return reasons


def plan_ruleset(plan: RepoPlan, client: Client, baseline: Baseline, approvals: int, checks: list[str]) -> None:
    desired = desired_ruleset(baseline, approvals, checks)
    name = desired["name"]
    summary = f"PR required ({approvals} approvals), checks: {', '.join(checks) or 'none'}, no force-push, no deletion"
    try:
        rulesets = client.paginate(f"/repos/{plan.full_name}/rulesets", {"includes_parents": "false"})
    except ApiError as e:
        if e.status in (403, 404):
            plan.add("ruleset", "unavailable", name, f"rulesets not available here (HTTP {e.status}; private repos need GitHub Pro/Team)")
            return
        raise
    mine = [r for r in rulesets if r.get("name") == name and r.get("source_type", "Repository") == "Repository"]
    if not mine:
        plan.add("ruleset", "create", name, summary, {"body": desired})
        return
    existing = client.get(f"/repos/{plan.full_name}/rulesets/{mine[0]['id']}")
    reasons = ruleset_diff(existing, desired)
    if reasons:
        plan.add("ruleset", "update", name, f"{summary} (differs: {', '.join(reasons)})", {"id": mine[0]["id"], "body": desired})


# ---------------------------------------------------------------- labels


def plan_labels(plan: RepoPlan, client: Client, baseline: Baseline) -> None:
    existing = {lbl["name"].lower(): lbl for lbl in client.paginate(f"/repos/{plan.full_name}/labels")}
    for want in baseline.labels:
        body = {"name": want["name"], "color": str(want["color"]).lower().lstrip("#"), "description": want.get("description", "")}
        have = existing.get(want["name"].lower())
        if not have:
            plan.add("labels", "create", want["name"], payload={"body": body})
            continue
        diffs = [k for k in ("name", "description") if (have.get(k) or "") != body[k]]
        if (have.get("color") or "").lower() != body["color"]:
            diffs.append("color")
        if diffs:
            plan.add(
                "labels",
                "update",
                want["name"],
                f"differs: {', '.join(diffs)}",
                {"current": have["name"], "body": {"new_name": body["name"], "color": body["color"], "description": body["description"]}},
            )


# ---------------------------------------------------------------- files


def desired_files(
    plan: RepoPlan, repo: dict, cfg: FactoryConfig, baseline: Baseline, ov: RepoOverrides, paths: list[str]
) -> dict[str, tuple[str, str | None, bool]]:
    """Return path -> (item, content or None if unavailable, managed). managed=False means create-only."""
    out: dict[str, tuple[str, str | None, bool]] = {}
    for item, path in FILE_ITEMS.items():
        if ov.skips(item):
            plan.add(item, "skipped", path, f"skipped by {OVERRIDE_PATH}")
            continue
        if item == "codeowners":
            content = render.render_codeowners(cfg, ov.codeowners or cfg.codeowners)
        elif item == "dependabot":
            content = render.render_dependabot(cfg, paths)
        elif item == "codeql":
            if not (_public(repo) or _feature_on(repo, "advanced_security", "code_security")):
                plan.add(item, "unavailable", path, "private repo without GitHub Code Security/Advanced Security")
                continue
            langs = render.detect_codeql_languages(paths)
            if not langs:
                plan.add(item, "skipped", path, "no CodeQL-supported languages found")
                continue
            content = render.render_codeql(cfg, plan.full_name, plan.default_branch, langs)
        else:
            content = render.render_template(baseline, cfg, path, plan.name)
        out[path] = (item, content, item != "changelog-stub")
    return out


def plan_files(
    plan: RepoPlan, client: Client, repo: dict, cfg: FactoryConfig, baseline: Baseline, ov: RepoOverrides, paths: list[str]
) -> None:
    present = set(paths)
    for path, (item, content, managed) in desired_files(plan, repo, cfg, baseline, ov, paths).items():
        if item == "codeowners" and path not in present:
            other = next((p for p in ("CODEOWNERS", "docs/CODEOWNERS") if p in present), None)
            if other:
                plan.add(item, "drift", path, f"repo already has {other}; left alone")
                continue
        if path not in present:
            plan.add(item, "create", path, "via pull request")
            plan.files[path] = content
            continue
        if not managed:
            continue  # create-only file that already exists
        current = read_file(client, plan.full_name, path, plan.default_branch)
        if current == content:
            continue
        if current is not None and cfg.marker in current:
            plan.add(item, "update", path, "via pull request")
            plan.files[path] = content
        else:
            plan.add(item, "drift", path, f"differs from baseline and has no `{cfg.marker}` marker; left alone")


def plan_pull_request(plan: RepoPlan, client: Client, cfg: FactoryConfig) -> None:
    prs = client.get(f"/repos/{plan.full_name}/pulls", {"head": f"{plan.owner}:{cfg.sync_branch}", "state": "open"}) or []
    plan.open_pr = prs[0] if prs else None
    if not plan.files:
        if plan.open_pr:
            plan.add("files", "drift", f"PR #{plan.open_pr['number']}", "open factory PR but the default branch already matches; close it")
        return
    n = len(plan.files)
    if plan.open_pr:
        plan.add("files", "update-pr", f"PR #{plan.open_pr['number']}", f"refresh {cfg.sync_branch} ({n} files)")
    else:
        plan.add("files", "open-pr", cfg.sync_branch, f"open one PR into {plan.default_branch} ({n} files)")


# ---------------------------------------------------------------- repo


def plan_repo(client: Client, cfg: FactoryConfig, baseline: Baseline, full_name: str) -> RepoPlan:
    plan = RepoPlan(full_name)
    try:
        repo = client.get(f"/repos/{full_name}")
    except ApiError as e:
        plan.add("repo", "error", full_name, str(e))
        return plan
    plan.default_branch = repo.get("default_branch") or "main"

    paths: list[str] | None = None
    try:
        tree = client.get(f"/repos/{full_name}/git/trees/{_q(plan.default_branch)}", {"recursive": "1"})
        paths = [t["path"] for t in tree.get("tree", []) if t.get("type") == "blob"]
    except ApiError as e:
        if e.status not in (404, 409):  # 409: empty repository
            plan.add("files", "error", "repository tree", str(e))

    ov = RepoOverrides()
    if paths is not None and OVERRIDE_PATH in paths:
        try:
            ov = parse_overrides(read_file(client, full_name, OVERRIDE_PATH, plan.default_branch))
        except ConfigError as e:
            plan.add("config", "error", OVERRIDE_PATH, f"{e}; nothing applied to this repo")
            return plan

    approvals = ov.approvals if ov.approvals is not None else cfg.approvals
    checks = ov.required_checks if ov.required_checks is not None else cfg.required_checks

    steps = [
        ("settings", lambda: plan_settings(plan, repo, baseline)),
        ("secret-scanning", lambda: plan_secret_scanning(plan, repo, baseline)),
        ("vulnerability-alerts", lambda: plan_vulnerability_alerts(plan, client, baseline)),
        ("ruleset", lambda: plan_ruleset(plan, client, baseline, approvals, checks)),
        ("labels", lambda: plan_labels(plan, client, baseline)),
    ]
    for item, fn in steps:
        if ov.skips(item):
            plan.add(item, "skipped", item, f"skipped by {OVERRIDE_PATH}")
            continue
        try:
            fn()
        except ApiError as e:
            plan.add(item, "error", item, str(e))

    if ov.skips("files"):
        plan.add("files", "skipped", "files", f"skipped by {OVERRIDE_PATH}")
    elif paths is None:
        plan.add("files", "unavailable", "files", "empty repository; push a first commit")
    else:
        try:
            plan_files(plan, client, repo, cfg, baseline, ov, paths)
            plan_pull_request(plan, client, cfg)
        except ApiError as e:
            plan.add("files", "error", "files", str(e))
    return plan
