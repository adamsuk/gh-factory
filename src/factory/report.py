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
    "warning": "⚠️",
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
        if p.agents is not None:
            a = p.agents
            roles = ", ".join(a.roles) or "none"
            test = f"`{a.test_command}`" if a.test_command else "from CI"
            lines += [
                f"Agents: roles {roles} · merge {'on' if a.merge else 'off'} · issue label `{a.issue_label}`"
                f" · review bot {a.review_bot} · test command {test}",
                "",
            ]
            lines += [f"- ℹ️ {n}" for n in p.agent_notes]
            if p.agent_notes:
                lines.append("")
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
            "agents": None if p.agents is None else {**p.agents.as_dict(), "notes": list(p.agent_notes)},
            "changes": [{"item": c.item, "action": c.action, "target": c.target, "detail": c.detail} for c in p.changes],
        }
        for p in plans
    ]
