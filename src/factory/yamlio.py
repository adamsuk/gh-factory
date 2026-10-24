"""YAML via the vendored pure-Python PyYAML, so output is identical on every machine."""

from ._vendor import yaml

YAMLError = yaml.YAMLError


def load(text: str):
    return yaml.safe_load(text)


def dump(data) -> str:
    return yaml.safe_dump(data, sort_keys=False, default_flow_style=False)
