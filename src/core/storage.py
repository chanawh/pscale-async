"""Object-storage abstraction for the upload handoff.

The API streams multipart uploads into the configured backend and hands the
Celery worker a *content reference* (backend + bucket + key) — never a local
filesystem path. The worker resolves the reference through the same backend,
so the handoff works when the API and the worker run in separate containers
with no shared filesystem.

Backends:
- ``local``: plain files under a root directory. For development, tests, and
  single-host deployments where the API and worker share the filesystem.
- ``s3``: any S3-compatible endpoint via boto3 (MinIO in docker compose,
  AWS S3 in production). ``boto3`` is imported lazily so the rest of the
  application — and the unit tests — do not require it.

This module is intentionally stdlib-only at import time. Configuration comes
in through explicit constructor arguments (see :func:`build_storage_backend`
and :func:`backend_from_settings`); nothing is read from the global settings
object here, which keeps the abstraction testable in isolation.
"""

import io
import os
import re
import shutil
from abc import ABC, abstractmethod
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, ContextManager, Dict, Iterator, Optional

_VALID_BACKENDS = ("local", "s3")

_SAFE_KEY_CHARS = re.compile(r"[^A-Za-z0-9._-]")

# How much of an upload the API keeps in memory for format detection while
# the full stream goes to the backend. Detection only needs the head.
DETECTION_HEAD_BYTES = 131072  # 128 KiB

# Read size for streaming an UploadFile into the backend.
STREAM_CHUNK_BYTES = 65536  # 64 KiB


@dataclass(frozen=True)
class StorageReference:
    """A content reference handed to the Celery worker.

    Serializable to a plain dict (JSON-safe) so it can travel as a Celery
    task argument. The worker must resolve it through a backend — it is
    never a filesystem path.
    """

    backend: str  # "local" | "s3"
    bucket: str  # S3 bucket; "" for the local backend
    key: str  # object key, e.g. "jobs/<job_id>/<filename>"

    def to_dict(self) -> Dict[str, str]:
        return {"backend": self.backend, "bucket": self.bucket, "key": self.key}

    @classmethod
    def from_dict(cls, data: Dict[str, str]) -> "StorageReference":
        if not isinstance(data, dict):
            raise ValueError(f"storage reference must be a dict, got {type(data).__name__}")
        for field in ("backend", "bucket", "key"):
            if field not in data or not isinstance(data[field], str):
                raise ValueError(f"storage reference missing string field {field!r}")
        if data["backend"] not in _VALID_BACKENDS:
            raise ValueError(
                f"unknown storage backend {data['backend']!r} "
                f"(expected one of {_VALID_BACKENDS})"
            )
        if not data["key"]:
            raise ValueError("storage reference has an empty key")
        return cls(backend=data["backend"], bucket=data["bucket"], key=data["key"])


class StorageBackend(ABC):
    """Interface every upload backend implements."""

    @abstractmethod
    def put_stream(
        self,
        key: str,
        stream: BinaryIO,
        *,
        content_type: str = "application/octet-stream",
    ) -> StorageReference:
        """Store the bytes read from ``stream`` under ``key``.

        Returns the content reference the worker will resolve later.
        """

    @abstractmethod
    def open_stream(self, ref: StorageReference) -> ContextManager[BinaryIO]:
        """Open the referenced object for streaming reads.

        A context manager yielding a binary file-like object. The caller
        must consume it inside the ``with`` block.
        """

    @abstractmethod
    def delete(self, ref: StorageReference) -> None:
        """Delete the referenced object. Best-effort idempotent."""

    @abstractmethod
    def exists(self, ref: StorageReference) -> bool:
        """Return True if the referenced object exists."""


class LocalStorageBackend(StorageBackend):
    """Filesystem backend rooted at a single directory.

    Object keys are namespaced under the root (``jobs/<job_id>/<file>``);
    any key that would resolve outside the root is rejected.
    """

    backend_name = "local"

    def __init__(self, root: str = "./uploads"):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _resolve(self, key: str) -> Path:
        if not key or key.startswith("/"):
            raise ValueError(f"refusing absolute/empty object key: {key!r}")
        candidate = (self.root / key).resolve()
        if candidate != self.root and self.root not in candidate.parents:
            raise ValueError(f"object key escapes storage root: {key!r}")
        return candidate

    def _check_ref(self, ref: StorageReference) -> None:
        if ref.backend != self.backend_name:
            raise ValueError(
                f"local backend cannot resolve {ref.backend!r} reference"
            )

    def put_stream(self, key, stream, *, content_type="application/octet-stream"):
        dest = self._resolve(key)
        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(dest, "wb") as f:
            shutil.copyfileobj(stream, f, length=STREAM_CHUNK_BYTES)
        return StorageReference(backend=self.backend_name, bucket="", key=key)

    @contextmanager
    def open_stream(self, ref: StorageReference) -> Iterator[BinaryIO]:
        self._check_ref(ref)
        path = self._resolve(ref.key)
        if not path.is_file():
            raise FileNotFoundError(f"stored object not found: {ref.key!r}")
        with open(path, "rb") as f:
            yield f

    def delete(self, ref: StorageReference) -> None:
        self._check_ref(ref)
        try:
            self._resolve(ref.key).unlink(missing_ok=True)
        except ValueError:
            # Key was invalid — nothing to delete.
            pass

    def exists(self, ref: StorageReference) -> bool:
        self._check_ref(ref)
        try:
            return self._resolve(ref.key).is_file()
        except ValueError:
            return False


class S3StorageBackend(StorageBackend):
    """S3-compatible backend via boto3 (MinIO, AWS S3, ...).

    ``endpoint_url`` is always required and is what makes the same code work
    against MinIO in compose and AWS S3 in production. The bucket is created
    on first construction if it does not exist, so a misconfigured endpoint
    or bad credentials fail fast at startup instead of on the first upload.
    """

    backend_name = "s3"

    def __init__(
        self,
        *,
        endpoint_url: str,
        access_key: str,
        secret_key: str,
        bucket: str,
        region: str = "us-east-1",
    ):
        # Validate configuration before importing boto3 so a missing
        # endpoint/credential fails fast with an actionable message even
        # where boto3 is not installed.
        missing = [
            name
            for name, value in (
                ("S3_ENDPOINT_URL", endpoint_url),
                ("S3_ACCESS_KEY", access_key),
                ("S3_SECRET_KEY", secret_key),
                ("S3_BUCKET", bucket),
            )
            if not value
        ]
        if missing:
            raise RuntimeError(
                "STORAGE_BACKEND=s3 is set but the following are unset: "
                + ", ".join(missing)
                + ". See .env.example."
            )
        try:
            import boto3
            from botocore.exceptions import ClientError
        except ImportError:
            raise RuntimeError(
                "STORAGE_BACKEND=s3 requires the 'boto3' package "
                "(pip install boto3). Set STORAGE_BACKEND=local to run "
                "without object storage."
            )
        self._ClientError = ClientError
        self.bucket = bucket
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
        )
        # Fail fast on bad endpoint/credentials; create the bucket if needed.
        try:
            self._client.head_bucket(Bucket=bucket)
        except ClientError as e:
            code = e.response.get("Error", {}).get("Code")
            if code == "404":
                self._client.create_bucket(Bucket=bucket)
            else:
                raise RuntimeError(
                    f"cannot access S3 bucket {bucket!r} at {endpoint_url}: "
                    f"{e}. Check S3_ENDPOINT_URL and credentials."
                ) from e

    def _check_ref(self, ref: StorageReference) -> None:
        if ref.backend != self.backend_name:
            raise ValueError(f"s3 backend cannot resolve {ref.backend!r} reference")

    def put_stream(self, key, stream, *, content_type="application/octet-stream"):
        self._client.upload_fileobj(
            stream, self.bucket, key, ExtraArgs={"ContentType": content_type}
        )
        return StorageReference(backend=self.backend_name, bucket=self.bucket, key=key)

    @contextmanager
    def open_stream(self, ref: StorageReference) -> Iterator[BinaryIO]:
        self._check_ref(ref)
        try:
            response = self._client.get_object(Bucket=ref.bucket, Key=ref.key)
        except self._ClientError as e:
            raise FileNotFoundError(
                f"stored object not found: {ref.bucket}/{ref.key}"
            ) from e
        body = response["Body"]
        try:
            yield body
        finally:
            body.close()

    def delete(self, ref: StorageReference) -> None:
        self._check_ref(ref)
        # delete_object is idempotent — missing keys are not an error.
        self._client.delete_object(Bucket=ref.bucket, Key=ref.key)

    def exists(self, ref: StorageReference) -> bool:
        self._check_ref(ref)
        try:
            self._client.head_object(Bucket=ref.bucket, Key=ref.key)
            return True
        except self._ClientError as e:
            if e.response.get("Error", {}).get("Code") == "404":
                return False
            raise


def sanitize_filename(filename: Optional[str]) -> str:
    """Make an uploader-supplied filename safe for use in an object key.

    Strips directories (path traversal, both ``/`` and Windows ``\\`` separators)
    and replaces anything outside ``[A-Za-z0-9._-]`` 1:1 with ``_`` so the key
    is safe for both the local backend and S3.
    """
    base = os.path.basename((filename or "").replace("\\", "/"))
    base = _SAFE_KEY_CHARS.sub("_", base).strip("._")
    return base or "upload.log"


def build_object_key(job_id: str, filename: Optional[str]) -> str:
    """Object key for an upload: ``jobs/<job_id>/<sanitized filename>``."""
    return f"jobs/{job_id}/{sanitize_filename(filename)}"


def build_storage_backend(
    *,
    backend: str,
    local_dir: str = "./uploads",
    s3_endpoint_url: Optional[str] = None,
    s3_access_key: Optional[str] = None,
    s3_secret_key: Optional[str] = None,
    s3_bucket: str = "pscale-async-uploads",
    s3_region: str = "us-east-1",
) -> StorageBackend:
    """Construct the configured backend, failing fast on misconfiguration."""
    if backend not in _VALID_BACKENDS:
        raise RuntimeError(
            f"unknown STORAGE_BACKEND {backend!r} (expected one of {_VALID_BACKENDS})"
        )
    if backend == "local":
        return LocalStorageBackend(root=local_dir)
    return S3StorageBackend(
        endpoint_url=s3_endpoint_url or "",
        access_key=s3_access_key or "",
        secret_key=s3_secret_key or "",
        bucket=s3_bucket,
        region=s3_region,
    )


def backend_from_settings(s) -> StorageBackend:
    """Build the backend from a settings object (duck-typed).

    Takes ``s`` instead of importing the global settings so this module
    stays importable without the application dependency stack (pydantic,
    boto3, ...). The API and worker pass ``src.core.config.settings``.
    """
    return build_storage_backend(
        backend=getattr(s, "storage_backend", "local"),
        local_dir=getattr(s, "local_upload_dir", "./uploads"),
        s3_endpoint_url=getattr(s, "s3_endpoint_url", None),
        s3_access_key=getattr(s, "s3_access_key", None),
        s3_secret_key=getattr(s, "s3_secret_key", None),
        s3_bucket=getattr(s, "s3_bucket", "pscale-async-uploads"),
        s3_region=getattr(s, "s3_region", "us-east-1"),
    )


def stream_to_text_lines(stream: BinaryIO) -> list:
    """Read a binary object stream into decoded text lines.

    Kept as a helper so the API fallback path and the worker share the
    same decoding behavior (utf-8, ignore errors).
    """
    with io.TextIOWrapper(stream, encoding="utf-8", errors="ignore") as text:
        return text.readlines()
