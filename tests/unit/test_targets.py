"""Tests for multi-cluster target resolution (src/onefs/targets.py),
the per-cluster client registry (src/onefs/registry.py), and
cluster-scoped event channels (src.core.events.job_channel).

Written for CI (pytest). Validated here via a standalone stdlib harness
because pytest/paramiko/pydantic are not installed in this environment;
the registry tests run with ONEFS_MOCK_MODE=true and stubbed paramiko /
requests modules so no real SSH is attempted.
"""

import json
import os

import pytest

from src.onefs.targets import (
    ClusterNotFoundError,
    default_target_name,
    load_targets,
    resolve_target,
)
from src.core.events import job_channel


def _env(**overrides):
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith("ONEFS_") or k == "ONEFS_LOG_DIR"
    }
    env.pop("ONEFS_TARGETS", None)
    env.pop("ONEFS_TARGETS_FILE", None)
    env.pop("ONEFS_HOST", None)
    env.pop("ONEFS_USER", None)
    env.pop("ONEFS_PASS", None)
    env.update(overrides)
    return env


def test_json_env_two_targets_with_defaults():
    env = _env(
        ONEFS_TARGETS=json.dumps(
            [
                {"name": "prod", "host": "10.0.0.5", "user": "admin",
                 "password": "s3cret"},
                {"host": "10.0.1.5", "password": "other"},
            ]
        )
    )
    targets = load_targets(env)
    assert len(targets) == 2
    prod, dr = targets
    assert prod["name"] == "prod"
    assert prod["port"] == 22
    assert prod["api_port"] == 8080
    assert prod["log_dir"] == "/var/log"
    # name defaults to host; user defaults to root
    assert dr["name"] == "10.0.1.5"
    assert dr["user"] == "root"


def test_explicit_ports_and_log_dir():
    env = _env(
        ONEFS_TARGETS=json.dumps(
            [{"name": "a", "host": "h", "password": "p",
              "port": 2222, "api_port": 8443, "log_dir": "/var/log/onefs"}]
        )
    )
    (t,) = load_targets(env)
    assert t["port"] == 2222
    assert t["api_port"] == 8443
    assert t["log_dir"] == "/var/log/onefs"


def test_password_alias_pass():
    env = _env(
        ONEFS_TARGETS=json.dumps([{"host": "h", "pass": "p"}])
    )
    (t,) = load_targets(env)
    assert t["password"] == "p"


@pytest.mark.parametrize(
    "entries, why",
    [
        ("not a list", "not a list"),
        ([], "empty list"),
        (["host-only"], "non-dict entry"),
        ([{"name": "x"}], "missing host"),
        ([{"host": "h"}], "missing password"),
        ([{"host": "h", "password": ""}], "empty password"),
        (
            [{"name": "a", "host": "h1", "password": "p"},
             {"name": "a", "host": "h2", "password": "p"}],
            "duplicate names",
        ),
        ([{"host": "h", "password": "p", "port": "NaN"}],
         "non-integer port"),
    ],
)
def test_malformed_entries_fail_fast(entries, why):
    env = _env(ONEFS_TARGETS=json.dumps(entries))
    with pytest.raises((RuntimeError, TypeError, ValueError)):
        load_targets(env)


def test_targets_file_json(tmp_path):
    f = tmp_path / "targets.json"
    f.write_text(json.dumps([{"name": "file", "host": "h", "password": "p"}]))
    (t,) = load_targets(_env(ONEFS_TARGETS_FILE=str(f)))
    assert t["name"] == "file"


def test_targets_file_yaml_fallback(tmp_path):
    """A YAML (non-JSON) targets file parses iff PyYAML is installed;
    otherwise it must fail fast, never silently misconfigure."""
    f = tmp_path / "targets.yaml"
    f.write_text("- name: file\n  host: h\n  password: p\n")
    try:
        import yaml  # noqa: F401

        (t,) = load_targets(_env(ONEFS_TARGETS_FILE=str(f)))
        assert t["host"] == "h"
    except ImportError:
        with pytest.raises(RuntimeError):
            load_targets(_env(ONEFS_TARGETS_FILE=str(f)))


def test_targets_file_unreadable(tmp_path):
    with pytest.raises(RuntimeError):
        load_targets(_env(ONEFS_TARGETS_FILE=str(tmp_path / "nope.json")))


def test_single_cluster_fallback():
    env = _env(ONEFS_HOST="single.local", ONEFS_USER="ops",
               ONEFS_PASS="pw", ONEFS_SSH_PORT="2222")
    (t,) = load_targets(env)
    assert t["name"] == "single.local"
    assert t["host"] == "single.local"
    assert t["user"] == "ops"
    assert t["port"] == 2222


def test_single_cluster_fallback_missing_fail_fast():
    with pytest.raises(RuntimeError):
        load_targets(_env())


def test_resolve_target():
    targets = [
        {"name": "a", "host": "h1", "user": "u", "password": "p",
         "port": 22, "api_port": 8080, "log_dir": "/var/log"},
        {"name": "b", "host": "h2", "user": "u", "password": "p",
         "port": 22, "api_port": 8080, "log_dir": "/var/log"},
    ]
    assert resolve_target(None, targets)["name"] == "a"
    assert resolve_target("b", targets)["host"] == "h2"
    assert default_target_name(targets) == "a"
    with pytest.raises(ClusterNotFoundError):
        resolve_target("nope", targets)


def test_job_channel_scoping():
    # Backwards compatible: no cluster -> bare channel
    assert job_channel("abc") == "job:abc"
    assert job_channel("abc", None) == "job:abc"
    # Named clusters are isolated from each other
    assert job_channel("abc", "prod") == "job:prod:abc"
    assert job_channel("abc", "prod") != job_channel("abc", "dr")


class TestRegistry:
    """Needs ONEFS_MOCK_MODE=true + stubbed paramiko/requests (no net)."""

    @pytest.fixture(autouse=True)
    def _mock_env(self, monkeypatch):
        pytest.importorskip("paramiko", reason="registry needs the client module")
        monkeypatch.setenv("ONEFS_MOCK_MODE", "true")
        monkeypatch.setenv(
            "ONEFS_TARGETS",
            json.dumps(
                [
                    {"name": "prod", "host": "10.0.0.5", "password": "p"},
                    {"name": "dr", "host": "10.0.1.5", "password": "p"},
                ]
            ),
        )
        from src.onefs import registry

        registry.reset_registry()
        yield
        registry.reset_registry()

    def test_per_cluster_client_isolation(self):
        from src.onefs import registry

        prod = registry.get_cluster_client("prod")
        dr = registry.get_cluster_client("dr")
        assert prod is not dr
        assert prod.target_name == "prod"
        assert dr.target_name == "dr"
        assert dr.cluster_host == "10.0.1.5"

    def test_same_name_returns_shared_client(self):
        from src.onefs import registry

        assert registry.get_cluster_client("prod") is registry.get_cluster_client("prod")

    def test_default_is_first_target(self):
        from src.onefs import registry

        assert registry.get_cluster_client(None).target_name == "prod"
        assert registry.list_cluster_names() == ["prod", "dr"]

    def test_unknown_cluster_raises(self):
        from src.onefs import registry

        with pytest.raises(ClusterNotFoundError):
            registry.get_cluster_client("nope")
