from factory._vendor import yaml

from .conftest import ROOT

LIVE_TASK = ROOT / ".github" / "ISSUE_TEMPLATE" / "task.yml"
MARKER = "# factory-managed: maintained by https://github.com/adamsuk/gh-factory. Remove this line to take ownership."

PROBLEM = {
    "type": "textarea",
    "id": "problem",
    "attributes": {
        "label": "Problem",
        "description": "What is wrong or missing, and who it affects.",
    },
    "validations": {"required": True},
}
PROPOSAL = {
    "type": "textarea",
    "id": "proposal",
    "attributes": {
        "label": "Proposal",
        "description": "What should change. Leave room for the implementer to choose how.",
    },
    "validations": {"required": False},
}
CONTEXT = {
    "type": "textarea",
    "id": "context",
    "attributes": {
        "label": "Context",
        "description": "Links, screenshots, logs.",
    },
    "validations": {"required": False},
}


def test_live_task_form_prefills_one_target_repo_above_problem():
    text = LIVE_TASK.read_text()
    assert text.splitlines()[0] == MARKER
    body = yaml.safe_load(text)["body"]
    problem_at = next(i for i, item in enumerate(body) if item.get("id") == "problem")
    assert problem_at > 0
    target = body[problem_at - 1]
    assert target["type"] == "textarea"
    assert target["id"] == "target"
    assert target["attributes"]["label"] == "Target repository"
    assert target["attributes"]["description"] == "The one repository this change lands in. Replace owner/repo and leave a single line."
    assert target["validations"]["required"] is True
    # A trailing newline from a YAML block scalar is fine; a second line is not.
    assert target["attributes"]["value"].splitlines() == ["Target repo: owner/repo"]
    assert body[problem_at] == PROBLEM
    by_id = {item.get("id"): item for item in body}
    assert by_id["proposal"] == PROPOSAL
    assert by_id["context"] == CONTEXT
    assert by_id["acceptance"]["validations"]["required"] is True
