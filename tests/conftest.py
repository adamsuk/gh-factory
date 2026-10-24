import base64
import json
import urllib.parse
from pathlib import Path

import pytest

from factory.client import Client
from factory.config import load_baseline, load_factory_config

ROOT = Path(__file__).resolve().parent.parent


class FakeClient(Client):
    """Serves canned responses keyed by (METHOD, path without query). Records every call."""

    def __init__(self, routes, read_only=True):
        super().__init__(read_only)
        self.routes = dict(routes)
        self.calls = []

    def _raw(self, method, url, body):
        parsed = urllib.parse.urlparse(url)
        path = urllib.parse.unquote(parsed.path)
        self.calls.append((method, path, body))
        resp = self.routes.get((method, path))
        if resp is None:
            return 404, {}, json.dumps({"message": "Not Found"})
        if callable(resp):
            resp = resp(body)
        status, data = resp
        return status, {}, "" if data is None else json.dumps(data)

    @property
    def writes(self):
        return [c for c in self.calls if c[0] != "GET"]


def b64(text):
    return {"type": "file", "content": base64.b64encode(text.encode()).decode()}


@pytest.fixture
def cfg():
    return load_factory_config(ROOT / "factory.yml")


@pytest.fixture
def baseline():
    return load_baseline(ROOT / "baseline")


def repo_routes(
    full="touchlineHQ/app",
    *,
    visibility="public",
    paths=("package.json", "src/index.ts"),
    settings=None,
    labels=(),
    rulesets=(),
    files=None,
    vuln=204,
    prs=(),
):
    """Routes describing one repo."""
    files = files or {}
    repo = {
        "full_name": full,
        "default_branch": "main",
        "visibility": visibility,
        "private": visibility != "public",
        "allow_squash_merge": True,
        "allow_merge_commit": True,
        "allow_rebase_merge": True,
        "allow_auto_merge": False,
        "delete_branch_on_merge": False,
        "squash_merge_commit_title": "COMMIT_OR_PR_TITLE",
        "squash_merge_commit_message": "COMMIT_MESSAGES",
        "security_and_analysis": {
            "secret_scanning": {"status": "disabled"},
            "secret_scanning_push_protection": {"status": "disabled"},
        },
        **(settings or {}),
    }
    all_paths = list(paths) + list(files)
    routes = {
        ("GET", f"/repos/{full}"): (200, repo),
        ("GET", f"/repos/{full}/git/trees/main"): (200, {"tree": [{"path": p, "type": "blob"} for p in all_paths]}),
        ("GET", f"/repos/{full}/vulnerability-alerts"): (vuln, None),
        ("GET", f"/repos/{full}/rulesets"): (200, [{"id": r["id"], "name": r["name"], "source_type": "Repository"} for r in rulesets]),
        ("GET", f"/repos/{full}/labels"): (200, list(labels)),
        ("GET", f"/repos/{full}/pulls"): (200, list(prs)),
    }
    for r in rulesets:
        routes[("GET", f"/repos/{full}/rulesets/{r['id']}")] = (200, r)
    for p, text in files.items():
        routes[("GET", f"/repos/{full}/contents/{p}")] = (200, b64(text))
    return routes
