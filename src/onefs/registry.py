"""Per-cluster OneFS client registry.

SSH clients are expensive to build (TCP + auth handshake, plus the
client's own connection pooling and circuit breaker), so one client is
kept per configured cluster name and shared by every task and request
that touches that cluster. :func:`get_cluster_client` is the only entry
point the rest of the app should use.

The OneFSClient import is lazy (inside the function) because paramiko is
a hard dependency of the client but this module is imported by routers
that unit tests may load without it.
"""

import threading
from typing import Dict, List, Optional

from src.onefs.targets import ClusterNotFoundError, load_targets, resolve_target

_lock = threading.Lock()
_clients: Dict[str, object] = {}


def list_cluster_names() -> List[str]:
    """Names of all configured OneFS targets, in configuration order."""
    return [t["name"] for t in load_targets()]


def get_cluster_client(name: Optional[str] = None):
    """Return the shared OneFSClient for cluster ``name``.

    ``None`` resolves to the default cluster (first configured target),
    so single-cluster deployments behave exactly as before. Unknown names
    raise :class:`ClusterNotFoundError` — API callers translate that to a
    400, never a 500.
    """
    from src.onefs.client import OneFSClient

    target = resolve_target(name)
    key = target["name"]
    with _lock:
        client = _clients.get(key)
        if client is None:
            client = OneFSClient(target=target)
            _clients[key] = client
        return client


def reset_registry() -> None:
    """Drop all cached clients. Tests use this to switch targets mid-run."""
    with _lock:
        _clients.clear()
