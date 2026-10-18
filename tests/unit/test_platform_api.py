"""Tests for src/onefs/platform_api.py against tests/mock_platform_api.py.

The mock implements exactly the documented endpoints the client uses
(session/1/session, cluster/identity, cluster/nodes,
event/eventgroup-occurrences, event/eventgroup-definitions).
"""

import pytest

from src.onefs.platform_api import (
    PlatformAPIAuthError,
    PlatformAPIClient,
    PlatformAPIError,
)

requests = pytest.importorskip("requests")  # client is requests-based


def make_client(mock, **overrides):
    target = {
        "name": "mock",
        "host": "127.0.0.1",
        "user": "admin",
        "password": "s3cret",
        "api_port": mock.port,
    }
    target.update(overrides)
    return PlatformAPIClient(target, scheme="http")


@pytest.fixture()
def mock():
    from tests.mock_platform_api import MockPlatformAPI

    with MockPlatformAPI(username="admin", password="s3cret") as m:
        yield m


def test_login_round_trip(mock):
    client = make_client(mock)
    body = client.login()
    assert body["services"] == ["platform"]
    assert client.session.headers.get("X-CSRF-Token") == "mock-csrf-token-123"
    client.close()


def test_login_wrong_password(mock):
    client = make_client(mock, password="wrong")
    with pytest.raises(PlatformAPIAuthError):
        client.login()


def test_cluster_identity_and_nodes(mock):
    client = make_client(mock)
    identity = client.cluster_identity()
    assert identity["name"] == "mock-cluster"
    assert "OneFS" in identity["version"]
    nodes = client.cluster_nodes()
    assert len(nodes["nodes"]) == 3
    client.close()


def test_eventgroup_occurrences(mock):
    client = make_client(mock)
    occs = client.list_eventgroup_occurrences()
    assert len(occs) == 2
    assert occs[0]["severity"] == "CRITICAL"
    one = client.get_eventgroup_occurrence(101)
    assert one["id"] == 101
    client.close()


def test_resolve_occurrence_uses_csrf(mock):
    client = make_client(mock)
    client.login()
    result = client.resolve_eventgroup_occurrence(101, resolved=True)
    assert result["id"] == 101
    occs = client.list_eventgroup_occurrences(resolved=True)
    assert any(o["id"] == 101 for o in occs)
    client.close()


def test_put_without_csrf_is_rejected(mock):
    """Proves the client actually sends the CSRF token on PUT."""
    client = make_client(mock)
    client.login()
    del client.session.headers["X-CSRF-Token"]
    with pytest.raises(PlatformAPIError):
        client.resolve_eventgroup_occurrence(101)
    client.close()


def test_expired_session_triggers_relogin(mock):
    client = make_client(mock)
    client.login()
    mock.invalidate_sessions()  # server-side expiry -> next call 401s
    identity = client.cluster_identity()  # client must re-login once
    assert identity["name"] == "mock-cluster"
    client.close()


def test_unauthenticated_cluster_call_fails_before_login(mock):
    """A client pointed at the mock with no session at all still has to
    log in; with bad creds the failure surfaces as an auth error."""
    client = make_client(mock, password="bad")
    with pytest.raises(PlatformAPIError):
        client.cluster_identity()


def test_connection_refused_surfaces_as_api_error():
    client = PlatformAPIClient(
        {"name": "down", "host": "127.0.0.1", "user": "u",
         "password": "p", "api_port": 1},
        scheme="http",
        timeout=2,
    )
    with pytest.raises(PlatformAPIError):
        client.login()


def test_eventgroup_definitions(mock):
    client = make_client(mock)
    defs = client.list_eventgroup_definitions()
    assert {d["name"] for d in defs} == {"drive.smart.fail", "node.temp.high"}
    client.close()


def test_context_manager_logs_out(mock):
    with make_client(mock) as client:
        assert client.cluster_identity()["name"] == "mock-cluster"
    assert not client._logged_in
