from factory.apply import apply_plan
from factory.client import parse_include_output
from factory.discover import discover
from factory.plan import plan_repo

from .conftest import FakeClient, repo_routes


def _repo(full, topics, archived=False):
    return {"full_name": full, "owner": {"login": full.split("/")[0]}, "topics": topics, "archived": archived}


def test_discover_with_user_token_lists_owners():
    client = FakeClient(
        {
            ("GET", "/users/touchlineHQ"): (200, {"type": "Organization"}),
            ("GET", "/orgs/touchlineHQ/repos"): (200, [_repo("touchlineHQ/a", ["factory"])]),
            ("GET", "/users/adamsuk"): (200, {"type": "User"}),
            ("GET", "/user"): (200, {"login": "adamsuk"}),
            ("GET", "/user/repos"): (200, [_repo("adamsuk/x", ["factory"]), _repo("touchlineHQ/a", ["factory"])]),
        }
    )
    names, scanned = discover(client, ["touchlineHQ", "adamsuk"], "factory")
    assert names == ["adamsuk/x", "touchlineHQ/a"] and scanned == 2
    assert client.writes == []


def test_apply_opens_one_pr_and_never_pushes_default_branch(cfg, baseline):
    full = "touchlineHQ/app"
    routes = repo_routes(full, vuln=404)
    routes.update(
        {
            ("GET", f"/repos/{full}/git/ref/heads/main"): (200, {"object": {"sha": "base"}}),
            ("GET", f"/repos/{full}/git/commits/base"): (200, {"tree": {"sha": "t0"}}),
            ("POST", f"/repos/{full}/git/trees"): (201, {"sha": "t1"}),
            ("POST", f"/repos/{full}/git/commits"): (201, {"sha": "c1"}),
            ("POST", f"/repos/{full}/git/refs"): (201, {}),
            ("POST", f"/repos/{full}/pulls"): (201, {"number": 5, "html_url": "https://github.com/x/pull/5"}),
            ("POST", f"/repos/{full}/issues/5/labels"): (200, []),
            ("PATCH", f"/repos/{full}"): (200, {}),
            ("PUT", f"/repos/{full}/vulnerability-alerts"): (204, None),
            ("POST", f"/repos/{full}/rulesets"): (201, {}),
            ("POST", f"/repos/{full}/labels"): (201, {}),
        }
    )
    client = FakeClient(routes)
    plan = plan_repo(client, cfg, baseline, full)
    client.read_only = False
    apply_plan(client, plan, cfg)
    assert not plan.errors
    writes = [(m, p) for m, p, _ in client.writes]
    assert ("POST", f"/repos/{full}/git/refs") in writes
    ref_body = next(b for m, p, b in client.writes if p.endswith("/git/refs"))
    assert ref_body["ref"] == "refs/heads/factory/sync"
    assert not any("heads/main" in p for _, p in writes)
    assert writes.count(("POST", f"/repos/{full}/pulls")) == 1
    pr = next(b for m, p, b in client.writes if p.endswith("/pulls"))
    assert pr["head"] == "factory/sync" and pr["base"] == "main"
    assert "CHANGELOG.md updated" in pr["body"]


def test_apply_skips_unchanged_sync_branch(cfg, baseline):
    full = "touchlineHQ/app"
    routes = repo_routes(full, prs=[{"number": 5}])
    routes.update(
        {
            ("GET", f"/repos/{full}/git/ref/heads/main"): (200, {"object": {"sha": "base"}}),
            ("GET", f"/repos/{full}/git/commits/base"): (200, {"tree": {"sha": "t0"}}),
            ("POST", f"/repos/{full}/git/trees"): (201, {"sha": "t1"}),
            ("GET", f"/repos/{full}/git/ref/heads/factory/sync"): (200, {"object": {"sha": "c1"}}),
            ("GET", f"/repos/{full}/git/commits/c1"): (200, {"tree": {"sha": "t1"}, "parents": [{"sha": "base"}]}),
            ("PATCH", f"/repos/{full}/pulls/5"): (200, {}),
        }
    )
    client = FakeClient(routes)
    plan = plan_repo(client, cfg, baseline, full)
    plan.changes = [c for c in plan.changes if c.item == "files" or c.target in plan.files]
    client.read_only = False
    apply_plan(client, plan, cfg)
    paths = [p for _, p, _ in client.writes]
    assert f"/repos/{full}/git/commits" not in paths
    assert not any(p.endswith("/git/refs/heads/factory/sync") for p in paths)


def test_parse_gh_include_output():
    out = 'HTTP/2.0 404 Not Found\r\nContent-Type: application/json\r\nLink: <x>; rel="next"\r\n\r\n{"message":"Not Found"}'
    status, headers, body = parse_include_output(out)
    assert status == 404 and headers["link"] == '<x>; rel="next"' and "Not Found" in body
