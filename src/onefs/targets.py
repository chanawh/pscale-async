"""Multi-cluster target resolution for OneFS clusters.

Mirrors the proven pattern from the sibling pscale-exporter repo
(``ISILON_TARGETS`` / ``ISILON_TARGETS_FILE``), adapted for this repo's
SSH-first access model:

- ``ONEFS_TARGETS``: JSON list of target objects (see below).
- ``ONEFS_TARGETS_FILE``: path to a JSON file (or YAML if PyYAML is
  installed) with the same list. Useful for k8s Secret-mounted files.
- Fallback: single target from ``ONEFS_HOST`` / ``ONEFS_USER`` /
  ``ONEFS_PASS`` (plus legacy ``CLUSTER_HOST`` / ``ISILON_USER`` /
  ``ISILON_PASS``) — v1 behavior, unchanged.

Target object fields::

    {
        "name":     "prod",            # unique; defaults to "host"
        "host":     "10.0.0.5",        # required
        "user":     "root",            # default "root"
        "password": "...",             # required ("pass" also accepted)
        "port":     22,               # SSH port, default 22
        "api_port": 8080,             # Platform API port, default 8080
        "log_dir":  "/var/log"        # default from ONEFS_LOG_DIR or /var/log
    }

Every target needs a host and a password -- fail fast otherwise, exactly
like the exporter. Names must be unique.

This module is stdlib-only at import time so unit tests can exercise
target parsing without paramiko, pydantic, or any app dependencies.
"""

import json
import os
from typing import Dict, List, Optional

DEFAULT_SSH_PORT = 22
DEFAULT_API_PORT = 8080
DEFAULT_USER = "root"
DEFAULT_LOG_DIR = "/var/log"


class ClusterNotFoundError(Exception):
    """Raised when a cluster name matches no configured target."""


def _coerce_entry(entry, index: int, env_log_dir: str) -> Dict:
    """Validate one raw target entry into a normalized target dict.

    ``env_log_dir`` is the ONEFS_LOG_DIR default resolved by the caller
    from the same env mapping the entries came from.
    """
    if not isinstance(entry, dict):
        raise TypeError(
            f"Invalid OneFS target entry #{index} (must be an object): {entry!r}"
        )
    host = entry.get("host")
    password = entry.get("password", entry.get("pass", ""))
    if not host or not str(host).strip():
        raise RuntimeError(
            f"OneFS target entry #{index} is missing required 'host': {entry!r}"
        )
    if not password or not str(password):
        raise RuntimeError(
            f"OneFS target entry #{index} is missing required "
            f"'password' for host {host!r}: refusing to configure a "
            f"passwordless cluster target"
        )
    name = str(entry.get("name") or host).strip()
    if not name:
        raise RuntimeError(
            f"OneFS target entry #{index} has an empty 'name': {entry!r}"
        )
    try:
        port = int(entry.get("port", DEFAULT_SSH_PORT))
        api_port = int(entry.get("api_port", DEFAULT_API_PORT))
    except (TypeError, ValueError):
        raise RuntimeError(
            f"OneFS target entry #{index} has a non-integer "
            f"port/api_port: {entry!r}"
        )
    log_dir = str(entry.get("log_dir") or env_log_dir).strip()
    if not log_dir.startswith("/"):
        raise RuntimeError(
            f"OneFS target entry #{index} 'log_dir' must be absolute: {entry!r}"
        )
    return {
        "name": name,
        "host": str(host).strip(),
        "user": str(entry.get("user", DEFAULT_USER)).strip() or DEFAULT_USER,
        "password": str(password),
        "port": port,
        "api_port": api_port,
        "log_dir": log_dir,
    }


def _single_target_fallback(env) -> List[Dict]:
    """v1 behavior: one target from the single-cluster env vars."""
    host = env.get("ONEFS_HOST") or env.get("CLUSTER_HOST")
    user = env.get("ONEFS_USER") or env.get("ISILON_USER")
    password = env.get("ONEFS_PASS") or env.get("ISILON_PASS") or ""
    if not host or not user:
        raise RuntimeError(
            "OneFS cluster access requires ONEFS_HOST and ONEFS_USER "
            "environment variables (legacy aliases: CLUSTER_HOST / "
            "ISILON_USER), or a configured ONEFS_TARGETS / "
            "ONEFS_TARGETS_FILE. Set ONEFS_MOCK_MODE=true for local "
            "development without a cluster."
        )
    if not password:
        raise RuntimeError(
            "ONEFS_PASS is not set: refusing to configure a passwordless "
            "cluster target"
        )
    try:
        port = int(env.get("ONEFS_SSH_PORT", DEFAULT_SSH_PORT))
    except (TypeError, ValueError):
        raise RuntimeError("ONEFS_SSH_PORT must be an integer")
    return [
        _coerce_entry(
            {
                "name": host,
                "host": host,
                "user": user,
                "password": password,
                "port": port,
            },
            0,
            str(env.get("ONEFS_LOG_DIR") or "").strip() or DEFAULT_LOG_DIR,
        )
    ]


def load_targets(env=None) -> List[Dict]:
    """Resolve the list of configured OneFS cluster targets.

    ``env`` defaults to ``os.environ``; tests pass a dict. Entries are
    validated and normalized; any malformed configuration raises
    immediately (fail fast) instead of failing mid-ingest.
    """
    env = os.environ if env is None else env
    raw = (env.get("ONEFS_TARGETS", "") or "").strip()
    path = (env.get("ONEFS_TARGETS_FILE", "") or "").strip()

    entries: list = []
    if path:
        try:
            with open(path) as f:
                text = f.read()
        except OSError as e:
            raise RuntimeError(
                f"ONEFS_TARGETS_FILE points at an unreadable file: {path}: {e}"
            )
        try:
            entries = json.loads(text)
        except ValueError:
            try:
                import yaml  # optional; JSON always works

                entries = yaml.safe_load(text)
            except ImportError:
                raise RuntimeError(
                    f"{path} is not valid JSON and PyYAML is not installed"
                )
    elif raw:
        try:
            entries = json.loads(raw)
        except ValueError as e:
            raise RuntimeError(f"ONEFS_TARGETS is not valid JSON: {e}")
    else:
        return _single_target_fallback(env)

    env_log_dir = (
        str(env.get("ONEFS_LOG_DIR") or "").strip() or DEFAULT_LOG_DIR
    )

    if not isinstance(entries, list) or not entries:
        raise RuntimeError(
            "No OneFS targets configured (ONEFS_TARGETS / "
            "ONEFS_TARGETS_FILE is empty or not a list)"
        )
    targets = [_coerce_entry(e, i, env_log_dir) for i, e in enumerate(entries)]
    names = [t["name"] for t in targets]
    dupes = sorted({n for n in names if names.count(n) > 1})
    if dupes:
        raise RuntimeError(
            f"Duplicate OneFS target names (must be unique): {dupes}"
        )
    return targets


def resolve_target(
    name: Optional[str], targets: Optional[List[Dict]] = None
) -> Dict:
    """Return the target dict for ``name``.

    ``None`` resolves to the first configured target (the default cluster;
    in single-cluster setups this is the only target, so existing behavior
    is unchanged). Unknown names raise :class:`ClusterNotFoundError`.
    """
    targets = load_targets() if targets is None else targets
    if name is None:
        return targets[0]
    for target in targets:
        if target["name"] == name:
            return target
    known = [t["name"] for t in targets]
    raise ClusterNotFoundError(
        f"Unknown OneFS cluster {name!r}. Configured clusters: {known}"
    )


def default_target_name(targets: Optional[List[Dict]] = None) -> str:
    """Name of the default cluster (first configured target)."""
    return resolve_target(None, targets)["name"]
