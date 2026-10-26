import re

from factory.config import load_baseline
from factory.plan import plan_repo

from .conftest import FakeClient, repo_routes

FULL = "touchlineHQ/app"


def actions(plan):
    return {(c.item, c.action, c.target) for c in plan.changes}


STATUS_LABELS = {
    "factory:triage": "01 Backlog: new issue waiting for triage",
    "factory:ready": "01 Backlog: triaged; single target repo, checkable acceptance criteria, sized",
    "factory:building": "03 Bench: a builder is working on it",
    "factory:gate": "04 Gate: PR open, waiting on required checks",
    "factory:review": "05 Review: checks green, waiting on review",
    "factory:merge": "05 Review: approved, waiting to merge",
    "factory:release": "07 Release: merged, waiting to ship",
    "factory:done": "09 Return: shipped and closed out",
    "factory:blocked": "Any station: needs a person; see the latest comment",
}


def test_status_labels_are_in_the_baseline():
    by_name = {lbl["name"]: lbl for lbl in load_baseline().labels}
    factory = by_name["factory"]
    assert factory["color"] == "1d76db"
    assert factory["description"] == "Opened by gh-factory, or an issue queued for the factory agents"
    for name, description in STATUS_LABELS.items():
        lbl = by_name[name]
        assert re.fullmatch(r"[0-9a-fA-F]{6}", lbl["color"])
        assert lbl["description"] == description
        assert 0 < len(lbl["description"]) <= 100
    assert by_name["factory:blocked"]["color"] == "b60205"


def test_plan_creates_status_labels_when_the_repo_has_none(cfg, baseline):
    plan = plan_repo(FakeClient(repo_routes()), cfg, baseline, FULL)
    got = actions(plan)
    for name in STATUS_LABELS:
        assert ("labels", "create", name) in got
