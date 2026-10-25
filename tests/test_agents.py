import json

import pytest

from factory.config import AGENT_ROLES, AgentSettings, ConfigError, load_baseline, parse_overrides
from factory.plan import NO_CHECKS_AGENT_MERGE, plan_repo
from factory.report import as_json, markdown

from .conftest import FakeClient, repo_routes

FULL = "touchlineHQ/app"


def test_agents_default_off_with_builder_and_reviewer():
    for text in (None, "", "skip: [codeql]\n", "agents:\n", "agents: {}\n"):
        a = parse_overrides(text).agents
        assert a == AgentSettings()
        assert a.merge is False and a.roles == ["builder", "reviewer"] and a.issue_label == "factory"


def test_agents_full_section():
    ov = parse_overrides("agents:\n  merge: true\n  roles: [intake, research, builder, reviewer]\n  issue_label: agent-ready\n")
    assert ov.agents.as_dict() == {"merge": True, "roles": list(AGENT_ROLES), "issue_label": "agent-ready"}


def test_agents_empty_roles_means_no_agents_work_here():
    assert parse_overrides("agents:\n  roles: []\n").agents.roles == []


@pytest.mark.parametrize(
    ("text", "match"),
    [
        ("agents: yes\n", "must be a mapping"),
        ("agents: [builder]\n", "must be a mapping"),
        ("agents:\n  merge: 'yes'\n", "merge must be true or false"),
        ("agents:\n  merge: 1\n", "merge must be true or false"),
        ("agents:\n  roles: builder\n", "roles must be a list"),
        ("agents:\n  roles: [builder, deployer]\n", "unknown roles \\['deployer'\\]"),
        ("agents:\n  roles: [builder, builder]\n", "more than once"),
        ("agents:\n  issue_label: ''\n", "issue_label must be a non-empty string"),
        ("agents:\n  issue_label: 3\n", "issue_label must be a non-empty string"),
        ("agents:\n  automerge: true\n", "unknown keys \\['automerge'\\]"),
    ],
)
def test_agents_validation(text, match):
    with pytest.raises(ConfigError, match=match):
        parse_overrides(text)


def test_factory_label_is_in_the_baseline():
    names = [lbl["name"] for lbl in load_baseline().labels]
    assert "factory" in names


def plan_with(cfg, baseline, override):
    routes = repo_routes(files={".github/factory.yml": override})
    return plan_repo(FakeClient(routes), cfg, baseline, FULL)


def test_plan_reports_agents_in_markdown_and_json(cfg, baseline):
    plan = plan_with(cfg, baseline, "required_checks: [Test]\nagents:\n  merge: true\n  roles: [builder]\n")
    assert plan.agents.merge is True and plan.agent_notes == []
    md = markdown([plan], mode="dry run", scope="", topic="factory")
    assert "Agents: roles builder · merge on · issue label `factory`" in md
    data = json.loads(json.dumps(as_json([plan])))
    assert data[0]["agents"] == {"merge": True, "roles": ["builder"], "issue_label": "factory", "notes": []}


def test_plan_defaults_agents_when_there_is_no_override(cfg, baseline):
    plan = plan_repo(FakeClient(repo_routes()), cfg, baseline, FULL)
    assert as_json([plan])[0]["agents"] == {"merge": False, "roles": ["builder", "reviewer"], "issue_label": "factory", "notes": []}
    assert "merge off" in markdown([plan], mode="dry run", scope="", topic="factory")


def test_plan_notes_merge_without_required_checks(cfg, baseline):
    plan = plan_with(cfg, baseline, "agents:\n  merge: true\n")
    assert plan.agent_notes == [NO_CHECKS_AGENT_MERGE]
    assert NO_CHECKS_AGENT_MERGE in markdown([plan], mode="dry run", scope="", topic="factory")


def test_plan_notes_a_custom_issue_label(cfg, baseline):
    plan = plan_with(cfg, baseline, "agents:\n  issue_label: agent-ready\n")
    assert plan.agent_notes == ["issue label `agent-ready` is not a baseline label; create it in the repo"]


def test_invalid_agents_section_stops_the_repo(cfg, baseline):
    plan = plan_with(cfg, baseline, "agents:\n  merge: maybe\n")
    assert [(c.item, c.action) for c in plan.changes] == [("config", "error")]
    assert plan.agents is None and as_json([plan])[0]["agents"] is None
