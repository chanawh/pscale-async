"""
OneFS integration module for Async Log Intelligence API
"""

# Lazy import (PEP 562): src.onefs.client needs paramiko and
# src.onefs.platform_api needs requests, but sibling submodules
# (targets, registry helpers) are stdlib-only by design so unit tests can
# import them without heavy dependencies installed.
# ``from src.onefs import OneFSClient`` keeps working exactly as before.
__all__ = ["OneFSClient", "PlatformAPIClient", "targets", "registry"]


def __getattr__(name):
    if name == "OneFSClient":
        from .client import OneFSClient

        return OneFSClient
    if name == "PlatformAPIClient":
        from .platform_api import PlatformAPIClient

        return PlatformAPIClient
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
