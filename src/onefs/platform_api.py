"""Dell OneFS Platform API (PAPI) client.

Division of labor with the SSH transport (``src/onefs/client.py``):

* **Platform API is primary** for structured cluster data served by
  documented REST resources: cluster identity/nodes (pre-flight metadata)
  and the event subsystem (eventgroup occurrences / definitions). These
  replace brittle SSH screen-scraping wherever they cover the need.
* **SSH is retained as the log transport** and as the fallback. There is
  deliberately no Platform API endpoint used here for raw log-file
  contents: the documented resource surface (see inventory below) has no
  resource that serves ``/var/log/*`` file contents. ``tail``/``cat`` over
  SSH remains the only supported way to fetch the raw log files the
  ingest pipeline processes.

Documented endpoint inventory (all against real OneFS; nothing invented):

* ``POST /session/1/session``
  body ``{"username","password","services":["platform"]}`` -- session
  cookie auth. ``DELETE /session/1/session`` logs out.
  Source: Dell PowerScale OneFS API Reference, "OneFS API authentication"
  (Session cookies: Create a session / Send a request through a session
  cookie / Log out of a session). Wire shape (payload keys, ``isicsrf``
  cookie + ``X-CSRF-Token`` header) verified against the sibling
  pscale-exporter's working scraper, which authenticates this exact way
  against a live cluster.
* ``GET /platform/3/cluster/identity``, ``GET /platform/3/cluster/nodes``.
  Source: same working client (used in production scrapes).
* ``GET /platform/16/event/eventgroup-occurrences``
  ``GET /platform/16/event/eventgroup-occurrences/<ID>``
  ``PUT /platform/16/event/eventgroup-occurrences[/<ID>]``
  ``GET /platform/16/event/eventgroup-definitions``
  Source: Dell PowerScale OneFS 9.5.0.0 API Reference Guide,
  "Event eventgroups occurrences resource" /
  "Event eventgroup definitions resource".

Designed next step (not built here): feed structured
``eventgroup-occurrences`` into the incident pipeline as a second source
alongside log lines. The client methods are ready; the pipeline work is
a separate change.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import requests
import urllib3

logger = logging.getLogger(__name__)

# OneFS ships a self-signed certificate; the rest of the codebase already
# runs PAPI traffic with verification off. Keep the warning quiet the
# same way src/onefs/client.py does.
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class PlatformAPIError(Exception):
    """Any failure talking to the OneFS Platform API."""


class PlatformAPIAuthError(PlatformAPIError):
    """Authentication against /session/1/session failed."""


class PlatformAPIClient:
    """Session-authenticated client for the OneFS Platform API.

    ``target`` is a target dict from :func:`src.onefs.targets.load_targets`
    (keys: name, host, user, password, api_port, ...). Sessions are
    established lazily on first use and re-established once on a 401.
    """

    def __init__(
        self,
        target: Dict,
        *,
        scheme: str = "https",
        verify_tls: bool = False,
        timeout: int = 30,
    ) -> None:
        self.target = target
        self.base_url = f"{scheme}://{target['host']}:{target.get('api_port', 8080)}"
        self.verify_tls = verify_tls
        self.timeout = timeout
        self.session = requests.Session()
        self.session.verify = verify_tls
        self._logged_in = False

    # ------------------------------------------------------------------
    # authentication
    # ------------------------------------------------------------------
    def login(self) -> Dict[str, Any]:
        """Create a PAPI session (POST /session/1/session)."""
        url = f"{self.base_url}/session/1/session"
        payload = {
            "username": self.target.get("user"),
            "password": self.target.get("password"),
            "services": ["platform"],
        }
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Referer": f"{self.base_url}/",
        }
        try:
            resp = self.session.post(url, json=payload, headers=headers, timeout=self.timeout)
        except requests.RequestException as exc:
            raise PlatformAPIAuthError(
                f"session login to {self.target.get('name')} failed: {exc}"
            ) from exc
        if resp.status_code in (401, 403):
            raise PlatformAPIAuthError(
                f"session login to {self.target.get('name')} rejected "
                f"({resp.status_code}): bad credentials or missing PAPI privilege"
            )
        if not resp.ok:
            raise PlatformAPIAuthError(
                f"session login to {self.target.get('name')} failed "
                f"({resp.status_code}): {resp.text[:200]}"
            )
        body = resp.json() if resp.content else {}
        csrf_token = (
            body.get("csrf_token")
            or self.session.cookies.get("is_csrf_token")
            or self.session.cookies.get("isicsrf")
        )
        if csrf_token:
            self.session.headers.update({"X-CSRF-Token": csrf_token})
        self.session.headers.update({"Referer": f"{self.base_url}/"})
        self._logged_in = True
        logger.info("Platform API session established for %s", self.target.get("name"))
        return body

    def logout(self) -> None:
        """Best-effort session teardown; never raises."""
        if not self._logged_in:
            return
        try:
            self.session.delete(
                f"{self.base_url}/session/1/session", timeout=self.timeout
            )
        except Exception as exc:  # noqa: BLE001 - teardown must not fail callers
            logger.debug("Platform API logout failed (ignored): %s", exc)
        finally:
            self._logged_in = False

    def close(self) -> None:
        self.logout()
        self.session.close()

    def __enter__(self) -> "PlatformAPIClient":
        self.login()
        return self

    def __exit__(self, *exc_info: Any) -> None:
        self.close()

    # ------------------------------------------------------------------
    # low-level request with one transparent re-login on 401
    # ------------------------------------------------------------------
    def _request(
        self,
        method: str,
        path: str,
        *,
        api_version: int = 16,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if not self._logged_in:
            self.login()
        url = f"{self.base_url}/platform/{api_version}{path}"
        for attempt in (1, 2):
            try:
                resp = self.session.request(
                    method,
                    url,
                    params=params,
                    json=json_body,
                    timeout=self.timeout,
                )
            except requests.RequestException as exc:
                raise PlatformAPIError(
                    f"{method} {path} on {self.target.get('name')} failed: {exc}"
                ) from exc
            if resp.status_code == 401 and attempt == 1:
                logger.info("Platform API session expired; re-authenticating")
                self._logged_in = False
                self.login()
                continue
            if not resp.ok:
                raise PlatformAPIError(
                    f"{method} {path} on {self.target.get('name')} returned "
                    f"{resp.status_code}: {resp.text[:200]}"
                )
            return resp.json() if resp.content else {}
        raise PlatformAPIError(f"{method} {path}: authentication retry exhausted")

    # ------------------------------------------------------------------
    # cluster metadata (pre-flight)
    # ------------------------------------------------------------------
    def cluster_identity(self) -> Dict[str, Any]:
        """GET /platform/3/cluster/identity -- cluster name/version."""
        return self._request("GET", "/cluster/identity", api_version=3)

    def cluster_nodes(self) -> Dict[str, Any]:
        """GET /platform/3/cluster/nodes -- node inventory."""
        return self._request("GET", "/cluster/nodes", api_version=3)

    # ------------------------------------------------------------------
    # events (structured cluster events -- the API-native incident source)
    # ------------------------------------------------------------------
    def list_eventgroup_occurrences(
        self,
        *,
        resolved: Optional[bool] = None,
        limit: Optional[int] = None,
        sort: str = "id",
        dir: str = "DESC",  # noqa: A002 - matches the PAPI query parameter name
    ) -> List[Dict[str, Any]]:
        """GET /platform/16/event/eventgroup-occurrences.

        Returns the raw occurrence list (envelope key
        ``eventgroup_occurrences`` per the OneFS collection pattern).
        """
        params: Dict[str, Any] = {"sort": sort, "dir": dir}
        if resolved is not None:
            params["resolved"] = str(resolved).lower()
        if limit is not None:
            params["limit"] = limit
        body = self._request("GET", "/event/eventgroup-occurrences", params=params)
        return body.get("eventgroup_occurrences", body if isinstance(body, list) else [])

    def get_eventgroup_occurrence(self, occurrence_id: int) -> Dict[str, Any]:
        """GET /platform/16/event/eventgroup-occurrences/<ID>."""
        return self._request("GET", f"/event/eventgroup-occurrences/{occurrence_id}")

    def resolve_eventgroup_occurrence(
        self,
        occurrence_id: int,
        *,
        resolved: bool = True,
        ignore: bool = False,
    ) -> Dict[str, Any]:
        """PUT /platform/16/event/eventgroup-occurrences/<ID>.

        Marks an occurrence resolved/ignored. Requires the CSRF token
        captured at login (sent as X-CSRF-Token).
        """
        return self._request(
            "PUT",
            f"/event/eventgroup-occurrences/{occurrence_id}",
            json_body={"resolved": resolved, "ignore": ignore},
        )

    def list_eventgroup_definitions(self) -> List[Dict[str, Any]]:
        """GET /platform/16/event/eventgroup-definitions."""
        body = self._request("GET", "/event/eventgroup-definitions")
        return body.get("eventgroup_definitions", body if isinstance(body, list) else [])
