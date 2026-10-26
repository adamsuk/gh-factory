from .conftest import ROOT

README_BENCH_ISSUE_LABEL = (
    "Station 03 Bench picks an open issue labelled factory:ready whose target repo lists builder in agents.roles. "
    "gh-factory does not pick issues or open pull requests."
)


def test_readme_says_bench_picks_factory_ready_issues():
    readme = (ROOT / "README.md").read_text()
    assert README_BENCH_ISSUE_LABEL in readme
    row = next(line for line in readme.splitlines() if line.startswith("| `issue_label` |"))
    cells = [cell.strip() for cell in row.strip().strip("|").split("|")]
    assert cells[0] == "`issue_label`" and cells[1] == "`factory`"
    meaning = cells[2]
    assert meaning.startswith(README_BENCH_ISSUE_LABEL)
    assert "picked up by the builder" not in meaning
    assert "`factory` is a baseline label; a different label gets a plan note so you remember to create it." in meaning
