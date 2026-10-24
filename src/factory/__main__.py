"""CLI: python -m factory [--apply] [--owner X] [--repo owner/name]"""

from __future__ import annotations

import argparse
import json
import os
import sys

from .apply import apply_plan
from .client import GhCliClient, HttpClient
from .config import load_baseline, load_factory_config
from .discover import discover
from .plan import plan_repo
from .report import as_json, markdown


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="factory", description=__doc__)
    ap.add_argument("--config", default="factory.yml")
    ap.add_argument("--baseline", default="baseline")
    ap.add_argument("--owner", action="append", help="limit to these owners (default: all in factory.yml)")
    ap.add_argument("--repo", help="limit to one enrolled repo, owner/name")
    ap.add_argument("--apply", action="store_true", help="make changes (default is a read-only dry run)")
    ap.add_argument("--summary", help="append the Markdown plan to this file (e.g. $GITHUB_STEP_SUMMARY)")
    ap.add_argument("--json", dest="json_path", help="write the plan as JSON to this file")
    args = ap.parse_args(argv)

    cfg = load_factory_config(args.config)
    baseline = load_baseline(args.baseline)
    owners = args.owner or cfg.owners
    if args.repo:
        owners = [o for o in owners if o.lower() == args.repo.split("/")[0].lower()]
        if not owners:
            print(f"{args.repo} is not under the configured owners; nothing to do.")
            return 0

    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    read_only = not args.apply
    client = HttpClient(token, read_only) if token else GhCliClient(read_only)

    names, source, scanned = discover(client, owners, cfg.topic, args.repo)
    plans = []
    for name in names:
        plan = plan_repo(client, cfg, baseline, name)
        if args.apply and plan.has_writes and not plan.errors:
            apply_plan(client, plan, cfg)
        plans.append(plan)

    mode = "apply" if args.apply else "dry run"
    md = markdown(plans, mode=mode, owners=owners, topic=cfg.topic, source=f"{source}, {scanned} repos scanned")
    print(md)
    if args.summary:
        with open(args.summary, "a") as f:
            f.write(md)
    if args.json_path:
        with open(args.json_path, "w") as f:
            json.dump(as_json(plans), f, indent=2)
    return 1 if any(p.errors for p in plans) else 0


if __name__ == "__main__":
    sys.exit(main())
