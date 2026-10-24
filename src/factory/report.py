"""Render plans as Markdown (job summary) and JSON."""

from __future__ import annotations

from .plan import RepoPlan

ICON = {
    "create": "➕",
    "update": "✏️",
    "enable": "🔒",
    "open-pr": "📬",
    "update-pr": "📬",
    "drift": "⚠️",
    "unknown": "❔",
    "unavailable": "⛔",
    "skipped": "⏭️",
    "error": "❌",
}


def markdown(plans: list[RepoPlan], *, mode: str, scope: str, topic: str) -> str:
    lines = [f"# Factory plan ({mode})", "", scope, ""]
    if not plans:
        lines.append(f"No enrolled repos found. Add the `{topic}` topic to a repo to enrol it.")
        return "\n".join(lines) + "\n"
    for p in plans:
        writes = sum(c.writes for c in p.changes)
        note = "" if p.enrolled else f" · not enrolled (no `{topic}` topic)"
        lines += [f"## {p.full_name}", "", f"{writes} change(s), default branch `{p.default_branch}`{note}", ""]
        if not p.changes:
            lines.append("- ✅ already matches the baseline")
        for c in p.changes:
            detail = f": {c.detail}" if c.detail else ""
            lines.append(f"- {ICON.get(c.action, '•')} **{c.action}** {c.item} `{c.target}`{detail}")
        lines.append("")
    return "\n".join(lines) + "\n"


def as_json(plans: list[RepoPlan]) -> list[dict]:
    return [
        {
            "repo": p.full_name,
            "default_branch": p.default_branch,
            "enrolled": p.enrolled,
            "changes": [{"item": c.item, "action": c.action, "target": c.target, "detail": c.detail} for c in p.changes],
        }
        for p in plans
    ]
