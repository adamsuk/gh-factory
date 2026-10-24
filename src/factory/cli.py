"""gh factory: apply a standard baseline to every repo carrying a topic, using your gh login."""

from __future__ import annotations

import argparse
import json
import re
import sys
from typing import TextIO

from .apply import apply_plan
from .client import ApiError, Client, GhCliClient, authenticated_login
from .config import ConfigError, FactoryConfig, load_baseline, resolve_config
from .discover import discover, get_topics, set_topics
from .plan import RepoPlan, plan_repo
from .report import as_json, markdown

REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


class Abort(Exception):
    """Stop with a message and exit code 2 (usage error or declined prompt)."""


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--config", help="config file (default: ~/.config/gh-factory/config.yml if present)")
    common.add_argument("--owner", action="append", help="account to search for enrolled repos; repeatable (default: config, else you)")
    common.add_argument("--baseline", help="directory with your own baseline; missing pieces fall back to the built-in one")
    common.add_argument("--json", dest="json_path", help="also write the plan as JSON to this file")
    common.add_argument("--summary", help="also append the Markdown plan to this file (e.g. $GITHUB_STEP_SUMMARY)")

    ap = argparse.ArgumentParser(prog="gh factory", description=__doc__)
    sub = ap.add_subparsers(dest="command", required=True, metavar="COMMAND")
    p = sub.add_parser("plan", parents=[common], help="dry run: show what would change (read-only)")
    p.add_argument("repos", nargs="*", metavar="OWNER/REPO", help="repos to plan (default: every enrolled repo)")
    p = sub.add_parser("apply", parents=[common], help="apply the baseline to enrolled repos")
    p.add_argument("repos", nargs="*", metavar="OWNER/REPO", help="enrolled repos to apply (default: all)")
    p.add_argument("-y", "--yes", action="store_true", help="do not ask for confirmation")
    p = sub.add_parser("enrol", aliases=["enroll"], parents=[common], help="add the topic to a repo, then apply")
    p.add_argument("repo", metavar="OWNER/REPO")
    p.add_argument("-y", "--yes", action="store_true", help="do not ask for confirmation")
    p = sub.add_parser("leave", parents=[common], help="remove the topic only; settings and files stay")
    p.add_argument("repo", metavar="OWNER/REPO")
    return ap


def _check_repo(name: str) -> str:
    if not REPO_RE.match(name):
        raise Abort(f"expected OWNER/REPO, got {name!r}")
    return name


def _confirm(question: str, stdin: TextIO, out: TextIO) -> bool:
    if not stdin.isatty():
        raise Abort("refusing to change anything without a terminal; pass --yes to confirm")
    out.write(f"{question} [y/N] ")
    out.flush()
    return stdin.readline().strip().lower() in ("y", "yes")


def _emit(plans: list[RepoPlan], args, cfg: FactoryConfig, mode: str, scope: str, out: TextIO) -> None:
    md = markdown(plans, mode=mode, scope=scope, topic=cfg.topic)
    out.write(md)
    if args.summary:
        with open(args.summary, "a") as f:
            f.write(md)
    if args.json_path:
        with open(args.json_path, "w") as f:
            json.dump(as_json(plans), f, indent=2)


def _plans(client: Client, cfg: FactoryConfig, baseline, repos: list[str]) -> tuple[list[RepoPlan], str]:
    if repos:
        names = [_check_repo(r) for r in repos]
        scope = f"Repos: {', '.join(names)} · topic `{cfg.topic}` · config: {cfg.source}"
    else:
        names, scanned = discover(client, cfg.owners, cfg.topic)
        scope = (
            f"Owners: {', '.join(cfg.owners)} · topic `{cfg.topic}` · config: {cfg.source} · "
            f"{scanned} repos scanned · repos enrolled: {len(names)}"
        )
    return [plan_repo(client, cfg, baseline, n) for n in names], scope


def _apply_all(client: Client, cfg: FactoryConfig, plans: list[RepoPlan]) -> None:
    client.read_only = False
    try:
        for p in plans:
            if p.has_writes and not p.errors:
                apply_plan(client, p, cfg)
    finally:
        client.read_only = True


def run(args, client: Client, stdin: TextIO, out: TextIO) -> int:
    login_cache: list[str] = []

    def login() -> str:
        if not login_cache:
            login_cache.append(authenticated_login(client))
        return login_cache[0]

    cfg = resolve_config(args.config, args.owner, args.baseline, login)
    baseline = load_baseline(cfg.baseline)
    client.read_only = True
    cmd = args.command

    if cmd == "plan":
        plans, scope = _plans(client, cfg, baseline, args.repos)
        _emit(plans, args, cfg, "dry run", scope, out)
        return 1 if any(p.errors for p in plans) else 0

    if cmd == "apply":
        plans, scope = _plans(client, cfg, baseline, args.repos)
        for p in plans:
            if not p.enrolled:
                p.add("repo", "error", p.full_name, f"not enrolled; run `gh factory enrol {p.full_name}` first")
        _emit(plans, args, cfg, "dry run", scope, out)
        todo = [p for p in plans if p.has_writes and not p.errors]
        if not todo:
            out.write("\nNothing to apply.\n")
            return 1 if any(p.errors for p in plans) else 0
        n = sum(sum(c.writes for c in p.changes) for p in todo)
        if not args.yes and not _confirm(f"\nApply {n} change(s) to {len(todo)} repo(s)?", stdin, out):
            raise Abort("aborted; nothing changed")
        _apply_all(client, cfg, todo)
        _emit(plans, args, cfg, "applied", scope, out)
        return 1 if any(p.errors for p in plans) else 0

    if cmd in ("enrol", "enroll"):
        name = _check_repo(args.repo)
        topics = get_topics(client, name)
        plan = plan_repo(client, cfg, baseline, name)
        plan.enrolled = True
        _emit([plan], args, cfg, "dry run", f"Enrolling {name} · topic `{cfg.topic}` · config: {cfg.source}", out)
        if plan.errors:
            out.write("\nNot enrolled: fix the errors above first.\n")
            return 1
        n = sum(c.writes for c in plan.changes)
        already = cfg.topic in topics
        q = f"\n{'Apply' if already else f'Add the `{cfg.topic}` topic and apply'} {n} change(s) to {name}?"
        if not args.yes and not _confirm(q, stdin, out):
            raise Abort("aborted; nothing changed")
        client.read_only = False
        try:
            if not already:
                set_topics(client, name, [*topics, cfg.topic])
                out.write(f"\nAdded topic `{cfg.topic}` to {name}.\n")
        finally:
            client.read_only = True
        _apply_all(client, cfg, [plan])
        _emit([plan], args, cfg, "applied", f"Enrolled {name}", out)
        return 1 if plan.errors else 0

    if cmd == "leave":
        name = _check_repo(args.repo)
        topics = get_topics(client, name)
        if cfg.topic not in topics:
            out.write(f"{name} is not enrolled (no `{cfg.topic}` topic). Nothing changed.\n")
            return 0
        client.read_only = False
        try:
            set_topics(client, name, [t for t in topics if t != cfg.topic])
        finally:
            client.read_only = True
        out.write(
            f"Removed topic `{cfg.topic}` from {name}. The factory will no longer touch it.\n"
            "Its settings, the factory-main ruleset, labels and files were left in place; change or remove them as you like.\n"
        )
        prs = client.get(f"/repos/{name}/pulls", {"head": f"{name.split('/')[0]}:{cfg.sync_branch}", "state": "open"}) or []
        if prs:
            out.write(f"An open factory PR (#{prs[0]['number']}) was left open; close it if you don't want it.\n")
        return 0

    raise Abort(f"unknown command {cmd}")


def main(argv: list[str] | None = None, client: Client | None = None, stdin: TextIO | None = None, out: TextIO | None = None) -> int:
    args = build_parser().parse_args(argv)
    out = out or sys.stdout
    try:
        return run(args, client or GhCliClient(read_only=True), stdin or sys.stdin, out)
    except Abort as e:
        print(f"gh factory: {e}", file=sys.stderr)
        return 2
    except (ConfigError, ApiError) as e:
        print(f"gh factory: {e}", file=sys.stderr)
        return 1
