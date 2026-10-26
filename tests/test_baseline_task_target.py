from factory._vendor import yaml
from factory.render import render_template


def test_baseline_task_form_prefills_one_target_repo_above_problem(cfg, baseline):
    form = yaml.safe_load(render_template(baseline, cfg, ".github/ISSUE_TEMPLATE/task.yml", "app"))
    body = form["body"]
    problem_at = next(
        i for i, item in enumerate(body) if item.get("type") == "textarea" and item.get("attributes", {}).get("label") == "Problem"
    )
    assert problem_at > 0
    target = body[problem_at - 1]
    assert target["type"] == "textarea"
    assert target["validations"]["required"] is True
    # A trailing newline from a YAML block scalar is fine; a second line is not.
    assert target["attributes"]["value"].splitlines() == ["Target repo: owner/repo"]
