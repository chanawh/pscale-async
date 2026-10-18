"""Mock Dell OneFS Platform API server for tests.

Modeled on the sibling pscale-exporter's ``mock_onefs`` pattern (session
login at POST /session/1/session, cookie + CSRF-token auth, fixture data)
but implemented with the stdlib ``http.server`` so the mock runs anywhere
-- including environments without FastAPI installed -- and the same mock
serves both the pytest suite and the standalone verification harness.

Implements exactly the endpoints ``src/onefs/platform_api.py`` uses:

* ``POST /session/1/session`` / ``DELETE /session/1/session``
* ``GET /platform/3/cluster/identity``, ``GET /platform/3/cluster/nodes``
* ``GET /platform/16/event/eventgroup-occurrences`` (+ ``/<id>``)
* ``PUT /platform/16/event/eventgroup-occurrences/<id>``
  (requires the X-CSRF-Token header, like real OneFS with CSRF on)
* ``GET /platform/16/event/eventgroup-definitions``

Fixture data is illustrative, not a transcription of Dell's schemas.

Usage::

    from tests.mock_platform_api import MockPlatformAPI

    with MockPlatformAPI(username="admin", password="s3cret") as mock:
        client = PlatformAPIClient({...}, scheme="http")
        ...
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse, parse_qs


def _fixture_occurrences() -> List[Dict[str, Any]]:
    return [
        {
            "id": 101,
            "eventgroup_definition_id": 9001,
            "severity": "CRITICAL",
            "resolved": False,
            "ignore": False,
            "lnn": 1,
            "devid": 12,
            "message": "Drive bay 1:4 SMART failure predicted",
            "started": 1760000000,
        },
        {
            "id": 102,
            "eventgroup_definition_id": 9002,
            "severity": "WARNING",
            "resolved": True,
            "ignore": False,
            "lnn": 2,
            "devid": 25,
            "message": "Node 2 CPU temperature above threshold",
            "started": 1759900000,
        },
    ]


def _fixture_definitions() -> List[Dict[str, Any]]:
    return [
        {"id": 9001, "name": "drive.smart.fail", "severity": "CRITICAL"},
        {"id": 9002, "name": "node.temp.high", "severity": "WARNING"},
    ]


class _Handler(BaseHTTPRequestHandler):
    server: "MockPlatformAPI"  # type: ignore[assignment]

    # -- helpers ------------------------------------------------------
    def _send_json(self, status: int, body: Any, cookies: Optional[List[str]] = None) -> None:
        payload = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        for cookie in cookies or []:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()
        self.wfile.write(payload)

    def _read_json(self) -> Dict[str, Any]:
        length = int(self.headers.get("Content-Length") or 0)
        if not length:
            return {}
        return json.loads(self.rfile.read(length) or b"{}")

    def _session_id(self) -> Optional[str]:
        cookie = self.headers.get("Cookie") or ""
        for part in cookie.split(";"):
            name, _, value = part.strip().partition("=")
            if name.strip() == "papi_session":
                return value.strip()
        return None

    def _authed(self) -> bool:
        return self._session_id() in self.server.valid_sessions

    def log_message(self, *args: Any) -> None:  # keep test output clean
        pass

    # -- session ------------------------------------------------------
    def do_POST(self) -> None:
        if urlparse(self.path).path != "/session/1/session":
            self._send_json(404, {"error": "not found"})
            return
        body = self._read_json()
        if (
            body.get("username") != self.server.username
            or body.get("password") != self.server.password
        ):
            self._send_json(401, {"error": "authentication failed"})
            return
        sid = f"mock-session-{len(self.server.valid_sessions) + 1}"
        self.server.valid_sessions.add(sid)
        self._send_json(
            201,
            {
                "csrf_token": self.server.csrf_token,
                "timeout_absolute": 14400,
                "services": body.get("services", ["platform"]),
            },
            cookies=[
                f"papi_session={sid}; Path=/; HttpOnly",
                f"isicsrf={self.server.csrf_token}; Path=/",
            ],
        )

    def do_DELETE(self) -> None:
        if urlparse(self.path).path != "/session/1/session":
            self._send_json(404, {"error": "not found"})
            return
        self.server.valid_sessions.discard(self._session_id() or "")
        self._send_json(200, {})

    # -- platform resources -------------------------------------------
    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        if not self._authed():
            self._send_json(401, {"error": "no valid session"})
            return
        if path == "/platform/3/cluster/identity":
            self._send_json(
                200,
                {"name": "mock-cluster", "id": "mock-cluster-id", "version": "OneFS 9.5.0.0"},
            )
        elif path == "/platform/3/cluster/nodes":
            self._send_json(
                200,
                {
                    "nodes": [
                        {"id": 1, "lnn": 1, "status": "OK"},
                        {"id": 2, "lnn": 2, "status": "OK"},
                        {"id": 3, "lnn": 3, "status": "DOWN"},
                    ]
                },
            )
        elif path == "/platform/16/event/eventgroup-occurrences":
            query = parse_qs(parsed.query)
            occs = self.server.occurrences
            if "resolved" in query:
                want = query["resolved"][0].lower() == "true"
                occs = [o for o in occs if o["resolved"] == want]
            self._send_json(200, {"eventgroup_occurrences": occs})
        elif path.startswith("/platform/16/event/eventgroup-occurrences/"):
            try:
                oid = int(path.rsplit("/", 1)[-1])
            except ValueError:
                self._send_json(400, {"error": "bad id"})
                return
            match = next((o for o in self.server.occurrences if o["id"] == oid), None)
            if match is None:
                self._send_json(404, {"error": "not found"})
            else:
                self._send_json(200, match)
        elif path == "/platform/16/event/eventgroup-definitions":
            self._send_json(200, {"eventgroup_definitions": _fixture_definitions()})
        else:
            self._send_json(404, {"error": "not found"})

    def do_PUT(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        if not self._authed():
            self._send_json(401, {"error": "no valid session"})
            return
        # Real OneFS with CSRF protection rejects mutating requests that do
        # not echo the token back as X-CSRF-Token.
        if self.headers.get("X-CSRF-Token") != self.server.csrf_token:
            self._send_json(403, {"error": "missing or invalid CSRF token"})
            return
        if path.startswith("/platform/16/event/eventgroup-occurrences/"):
            try:
                oid = int(path.rsplit("/", 1)[-1])
            except ValueError:
                self._send_json(400, {"error": "bad id"})
                return
            match = next((o for o in self.server.occurrences if o["id"] == oid), None)
            if match is None:
                self._send_json(404, {"error": "not found"})
                return
            body = self._read_json()
            match["resolved"] = bool(body.get("resolved", True))
            match["ignore"] = bool(body.get("ignore", False))
            self._send_json(200, {"id": oid})
        else:
            self._send_json(404, {"error": "not found"})


class MockPlatformAPI(ThreadingHTTPServer):
    """A running mock OneFS Platform API. Use as a context manager."""

    allow_reuse_address = True

    def __init__(self, username: str = "admin", password: str = "s3cret") -> None:
        self.username = username
        self.password = password
        self.csrf_token = "mock-csrf-token-123"
        self.valid_sessions: set = set()
        self.occurrences: List[Dict[str, Any]] = _fixture_occurrences()
        super().__init__(("127.0.0.1", 0), _Handler)
        self._thread = threading.Thread(target=self.serve_forever, daemon=True)

    @property
    def port(self) -> int:
        return self.server_address[1]

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def invalidate_sessions(self) -> None:
        """Simulate session expiry: next request gets a 401."""
        self.valid_sessions.clear()

    def __enter__(self) -> "MockPlatformAPI":
        self._thread.start()
        return self

    def __exit__(self, *exc_info: Any) -> None:
        self.shutdown()
        self.server_close()
        self._thread.join(timeout=5)


if __name__ == "__main__":
    # Manual smoke: python3 tests/mock_platform_api.py
    with MockPlatformAPI() as mock:
        print(f"mock Platform API listening on {mock.url} (admin/s3cret)")
        threading.Event().wait()
