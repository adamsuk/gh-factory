"""Minimal GitHub REST client with a hard read-only mode for dry runs."""

from __future__ import annotations

import json
import re
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

API = "https://api.github.com"


class ApiError(Exception):
    def __init__(self, status: int, message: str, path: str = ""):
        super().__init__(f"HTTP {status} on {path}: {message}")
        self.status = status
        self.message = message
        self.path = path


class ReadOnlyViolation(RuntimeError):
    """Raised when a write is attempted while the client is read-only."""


def _next_link(link_header: str | None) -> str | None:
    if not link_header:
        return None
    for part in link_header.split(","):
        m = re.search(r'<([^>]+)>;\s*rel="next"', part)
        if m:
            return m.group(1)
    return None


class Client:
    """Base client. Subclasses implement `_raw`."""

    def __init__(self, read_only: bool = True):
        self.read_only = read_only

    # Subclasses return (status, headers, body_text).
    def _raw(self, method: str, url: str, body: Any | None) -> tuple[int, dict[str, str], str]:
        raise NotImplementedError

    def _url(self, path: str, params: dict[str, Any] | None = None) -> str:
        url = path if path.startswith("http") else API + path
        if params:
            sep = "&" if "?" in url else "?"
            url += sep + urllib.parse.urlencode(params)
        return url

    def request(
        self, method: str, path: str, body: Any | None = None, params: dict[str, Any] | None = None
    ) -> tuple[int, Any, dict[str, str]]:
        method = method.upper()
        if method != "GET" and self.read_only:
            raise ReadOnlyViolation(f"{method} {path} blocked: client is read-only (dry run)")
        status, headers, text = self._raw(method, self._url(path, params), body)
        data: Any = None
        if text.strip():
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                data = text
        if status >= 400:
            msg = data.get("message", "") if isinstance(data, dict) else str(data)
            raise ApiError(status, msg, path)
        return status, data, headers

    def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        return self.request("GET", path, params=params)[1]

    def status(self, path: str) -> int:
        """GET returning only the status code; 4xx is returned, not raised."""
        try:
            return self.request("GET", path)[0]
        except ApiError as e:
            return e.status

    def paginate(self, path: str, params: dict[str, Any] | None = None, key: str | None = None) -> list[Any]:
        params = {"per_page": 100, **(params or {})}
        url: str | None = self._url(path, params)
        out: list[Any] = []
        while url:
            _, data, headers = self.request("GET", url)
            items = data.get(key, []) if key and isinstance(data, dict) else data
            out.extend(items or [])
            url = _next_link(headers.get("link"))
        return out

    def post(self, path: str, body: Any) -> Any:
        return self.request("POST", path, body)[1]

    def patch(self, path: str, body: Any) -> Any:
        return self.request("PATCH", path, body)[1]

    def put(self, path: str, body: Any | None = None) -> Any:
        return self.request("PUT", path, body)[1]


class HttpClient(Client):
    """Talks to the API directly with a token (used in CI with the App token)."""

    def __init__(self, token: str, read_only: bool = True):
        super().__init__(read_only)
        self._token = token

    def _raw(self, method, url, body):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Accept", "application/vnd.github+json")
        req.add_header("X-GitHub-Api-Version", "2022-11-28")
        req.add_header("Authorization", f"Bearer {self._token}")
        req.add_header("User-Agent", "adamsuk-factory")
        if data is not None:
            req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                headers = {k.lower(): v for k, v in resp.headers.items()}
                return resp.status, headers, resp.read().decode()
        except urllib.error.HTTPError as e:
            headers = {k.lower(): v for k, v in e.headers.items()}
            return e.code, headers, e.read().decode()


class GhCliClient(Client):
    """Uses the authenticated `gh` CLI, so no token is handled here (local runs)."""

    def _raw(self, method, url, body):
        cmd = ["gh", "api", "--include", "--method", method, url.removeprefix(API)]
        stdin = None
        if body is not None:
            cmd += ["--input", "-"]
            stdin = json.dumps(body)
        proc = subprocess.run(cmd, input=stdin, capture_output=True, text=True)
        return parse_include_output(proc.stdout)


def parse_include_output(out: str) -> tuple[int, dict[str, str], str]:
    """Parse `gh api --include` output into (status, headers, body)."""
    out = out.replace("\r\n", "\n")
    head, _, body = out.partition("\n\n")
    lines = head.split("\n")
    m = re.match(r"HTTP/\S+\s+(\d+)", lines[0] if lines else "")
    status = int(m.group(1)) if m else 599
    headers: dict[str, str] = {}
    for line in lines[1:]:
        k, sep, v = line.partition(":")
        if sep:
            headers[k.strip().lower()] = v.strip()
    return status, headers, body
