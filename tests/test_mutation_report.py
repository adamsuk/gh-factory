"""The mutation-testing job is report-only: it must never be able to fail a PR."""

import importlib.util
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("mutation_report", ROOT / ".github/scripts/mutation_report.py")
mr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mr)

WORKFLOW = (ROOT / ".github/workflows/mutation.yml").read_text()


def test_changed_modules_filters_to_mutable_source():
    paths = [
        "src/factory/plan.py",
        "src/factory/plan.py",
        "src/factory/__init__.py",
        "src/factory/_vendor/yaml/x.py",
        "tests/test_plan.py",
        "README.md",
    ]
    assert mr.changed_modules(paths) == ["factory.plan"]


def test_parse_and_render_survivors():
    out = "    factory.plan.x_a__mutmut_1: survived\n    factory.plan.x_a__mutmut_2: survived\n    factory.report.x_b__mutmut_1: timeout\n"
    modules = ["factory.plan", "factory.report"]
    counts = mr.parse_results(out, modules)
    assert counts == {"factory.plan": {"survived": 2}, "factory.report": {"timeout": 1}}
    report = mr.render(modules, counts)
    assert "| `factory/plan.py` | 2 | 0 |" in report
    assert "| `factory/report.py` | 0 | 1 timeout |" in report


def test_render_with_nothing_changed():
    assert "nothing was mutated" in mr.render([], {})


@pytest.mark.parametrize("stdin", ["src/factory/plan.py\n", "README.md\n"])
def test_main_exits_zero_even_when_mutmut_fails(monkeypatch, capsys, stdin):
    import io

    monkeypatch.setattr("sys.stdin", io.StringIO(stdin))
    monkeypatch.setattr(mr, "run", lambda cmd, timeout: ("    factory.plan.x_a__mutmut_1: survived\n", "`mutmut run` exited 1"))
    assert mr.main([]) == 0
    assert "report only" in capsys.readouterr().out


def test_run_reports_missing_binary_instead_of_raising():
    out, problem = mr.run(["definitely-not-a-binary-xyz", "run"], 5)
    assert out == ""
    assert "could not run" in problem


def test_workflow_cannot_block_merge():
    assert re.search(r"^    continue-on-error: true$", WORKFLOW, re.M)
    assert re.search(r"^    timeout-minutes: \d+$", WORKFLOW, re.M)
    assert "pull_request:" in WORKFLOW
    assert "pull_request_target" not in WORKFLOW
    # Every run step either cannot fail the job or is a `uses` step.
    assert WORKFLOW.count("continue-on-error: true") >= 3
    assert "|| true" in WORKFLOW
