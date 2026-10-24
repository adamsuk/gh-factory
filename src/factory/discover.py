"""Find enrolled repos: non-archived repos carrying the factory topic."""

from __future__ import annotations

from .client import ApiError, Client


def _enrolled(repo: dict, topic: str, owners: set[str]) -> bool:
    return (
        not repo.get("archived")
        and not repo.get("disabled")
        and topic in (repo.get("topics") or [])
        and repo["owner"]["login"].lower() in owners
    )


def list_owner_repos(client: Client, owner: str) -> list[dict]:
    """All repos of a user or org visible to the token (used with a personal token)."""
    account = client.get(f"/users/{owner}")
    if account.get("type") == "Organization":
        return client.paginate(f"/orgs/{owner}/repos", {"type": "all"})
    try:
        me = client.get("/user").get("login", "")
    except ApiError:
        me = ""
    if me.lower() == owner.lower():
        return client.paginate("/user/repos", {"affiliation": "owner", "visibility": "all"})
    return client.paginate(f"/users/{owner}/repos", {"type": "owner"})


def discover(client: Client, owners: list[str], topic: str, only: str | None = None) -> tuple[list[str], str, int]:
    """Return (sorted full names, source, repos scanned). Uses the App installation's repo list when the
    token is an installation token, otherwise lists each owner's repos."""
    wanted = {o.lower() for o in owners}
    try:
        repos = client.paginate("/installation/repositories", key="repositories")
        source = "installation"
    except ApiError:
        repos, source = [], "owner listing"
        for owner in owners:
            repos += list_owner_repos(client, owner)
    names = sorted({r["full_name"] for r in repos if _enrolled(r, topic, wanted)}, key=str.lower)
    if only:
        names = [n for n in names if n.lower() == only.lower()]
    return names, source, len(repos)
