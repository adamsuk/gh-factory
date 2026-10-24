"""Find enrolled repos (non-archived repos carrying the factory topic) and manage the topic."""

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


def discover(client: Client, owners: list[str], topic: str) -> tuple[list[str], int]:
    """Return (sorted full names of enrolled repos, number of repos scanned)."""
    wanted = {o.lower() for o in owners}
    repos: list[dict] = []
    for owner in owners:
        repos += list_owner_repos(client, owner)
    names = sorted({r["full_name"] for r in repos if _enrolled(r, topic, wanted)}, key=str.lower)
    return names, len({r["full_name"] for r in repos})


def get_topics(client: Client, full_name: str) -> list[str]:
    return list((client.get(f"/repos/{full_name}/topics") or {}).get("names") or [])


def set_topics(client: Client, full_name: str, names: list[str]) -> None:
    client.put(f"/repos/{full_name}/topics", {"names": names})
