import io

import pytest

from factory.cli import main

from .conftest import FakeClient, repo_routes

FULL = "adamsuk/app"


class Tty(io.StringIO):
    def isatty(self):
        return True


@pytest.fixture(autouse=True)
def isolated_config(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    monkeypatch.delenv("GH_FACTORY_CONFIG", raising=False)


def _listing(topics):
    return [{"full_name": FULL, "owner": {"login": "adamsuk"}, "topics": topics, "archived": False}]


def routes(topics=("factory",), apply_ready=False):
    r = repo_routes(FULL, vuln=404)
    r[("GET", f"/repos/{FULL}")][1]["topics"] = list(topics)
    r.update(
        {
            ("GET", "/user"): (200, {"login": "adamsuk"}),
            ("GET", "/users/adamsuk"): (200, {"type": "User"}),
            ("GET", "/user/repos"): (200, _listing(list(topics))),
            ("GET", f"/repos/{FULL}/topics"): (200, {"names": list(topics)}),
            ("PUT", f"/repos/{FULL}/topics"): lambda body: (200, body),
        }
    )
    if apply_ready:
        r.update(
            {
                ("GET", f"/repos/{FULL}/git/ref/heads/main"): (200, {"object": {"sha": "base"}}),
                ("GET", f"/repos/{FULL}/git/commits/base"): (200, {"tree": {"sha": "t0"}}),
                ("POST", f"/repos/{FULL}/git/trees"): (201, {"sha": "t1"}),
                ("POST", f"/repos/{FULL}/git/commits"): (201, {"sha": "c1"}),
                ("POST", f"/repos/{FULL}/git/refs"): (201, {}),
                ("POST", f"/repos/{FULL}/pulls"): (201, {"number": 5, "html_url": "https://github.com/x/pull/5"}),
                ("POST", f"/repos/{FULL}/issues/5/labels"): (200, []),
                ("PATCH", f"/repos/{FULL}"): (200, {}),
                ("PUT", f"/repos/{FULL}/vulnerability-alerts"): (204, None),
                ("POST", f"/repos/{FULL}/rulesets"): (201, {}),
                ("POST", f"/repos/{FULL}/labels"): (201, {}),
            }
        )
    return r


def run(argv, client, stdin=None):
    out = io.StringIO()
    code = main(argv, client=client, stdin=stdin or io.StringIO(), out=out)
    return code, out.getvalue()


def test_plan_defaults_to_the_authenticated_user_and_never_writes():
    client = FakeClient(routes())
    code, out = run(["plan"], client)
    assert code == 0
    assert "Owners: adamsuk" in out and "repos enrolled: 1" in out and "## adamsuk/app" in out
    assert client.writes == []


def test_plan_explicit_repo_marks_not_enrolled():
    client = FakeClient(routes(topics=()))
    code, out = run(["plan", FULL, "--owner", "someone"], client)
    assert code == 0 and "not enrolled" in out and client.writes == []


def test_plan_rejects_bad_repo_name():
    assert run(["plan", "not-a-repo"], FakeClient(routes()))[0] == 2


def test_apply_without_terminal_or_yes_refuses():
    client = FakeClient(routes(apply_ready=True))
    code, _ = run(["apply"], client)
    assert code == 2 and client.writes == []


def test_apply_prompt_declined_changes_nothing():
    client = FakeClient(routes(apply_ready=True))
    code, _ = run(["apply"], client, stdin=Tty("n\n"))
    assert code == 2 and client.writes == []


def test_apply_yes_applies_and_opens_one_pr():
    client = FakeClient(routes(apply_ready=True))
    code, out = run(["apply", "--yes"], client)
    assert code == 0, out
    paths = [(m, p) for m, p, _ in client.writes]
    assert paths.count(("POST", f"/repos/{FULL}/pulls")) == 1
    assert not any("heads/main" in p for _, p in paths)
    assert "# Factory plan (applied)" in out


def test_apply_refuses_repo_that_is_not_enrolled():
    client = FakeClient(routes(topics=(), apply_ready=True))
    code, out = run(["apply", FULL, "--yes"], client)
    assert code == 1 and "gh factory enrol" in out and client.writes == []


def test_enrol_adds_topic_then_applies():
    client = FakeClient(routes(topics=("python",), apply_ready=True))
    code, out = run(["enrol", FULL, "--yes"], client)
    assert code == 0, out
    first = client.writes[0]
    assert first[:2] == ("PUT", f"/repos/{FULL}/topics") and first[2] == {"names": ["python", "factory"]}
    assert ("POST", f"/repos/{FULL}/pulls") in [(m, p) for m, p, _ in client.writes]


def test_enrol_declined_changes_nothing():
    client = FakeClient(routes(topics=(), apply_ready=True))
    code, _ = run(["enrol", FULL], client, stdin=Tty("no\n"))
    assert code == 2 and client.writes == []


def test_leave_removes_only_the_topic():
    client = FakeClient(routes(topics=("python", "factory")))
    code, out = run(["leave", FULL], client)
    assert code == 0
    assert client.writes == [("PUT", f"/repos/{FULL}/topics", {"names": ["python"]})]
    assert "left in place" in out


def test_leave_when_not_enrolled_is_a_no_op():
    client = FakeClient(routes(topics=("python",)))
    code, out = run(["leave", FULL], client)
    assert code == 0 and "not enrolled" in out and client.writes == []


def test_config_flag_and_custom_baseline(tmp_path):
    (tmp_path / "std").mkdir()
    (tmp_path / "std" / "labels.yml").write_text("- name: mine\n  color: '000000'\n  description: x\n")
    conf = tmp_path / "c.yml"
    conf.write_text("owners: [adamsuk]\ncodeowners: ['@team']\nbaseline: std\n")
    client = FakeClient(routes())
    code, out = run(["plan", "--config", str(conf)], client)
    assert code == 0
    assert "labels `mine`" in out and "skip-changelog" not in out.split("labels `mine`")[0].split("## adamsuk/app")[1]
    # /user is only used by discovery to tell your own account apart, not to resolve defaults.
    assert [c for c in client.calls if c[1] == "/user"] == [("GET", "/user", None)]
