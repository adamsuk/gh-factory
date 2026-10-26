from factory.config import parse_overrides

from .conftest import ROOT


def test_own_factory_yml_lists_intake_builder_and_reviewer():
    text = (ROOT / ".github" / "factory.yml").read_text()
    assert parse_overrides(text).agents.roles == ["intake", "builder", "reviewer"]
