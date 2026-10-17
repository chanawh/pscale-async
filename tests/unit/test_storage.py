"""Unit tests for the object-storage upload handoff (src/core/storage.py).

These tests need no live infrastructure: the local backend runs against
tmp_path, and the S3 backend is exercised only for its fail-fast paths
(construction is never attempted without credentials, and boto3-dependent
behavior is skipped when boto3 is installed).
"""
import importlib.util
import io

import pytest

from src.core.storage import (
    LocalStorageBackend,
    S3StorageBackend,
    StorageReference,
    backend_from_settings,
    build_object_key,
    build_storage_backend,
    sanitize_filename,
    stream_to_text_lines,
)


class TestSanitizeFilename:
    def test_plain_name_unchanged(self):
        assert sanitize_filename("messages.log") == "messages.log"

    def test_path_traversal_stripped(self):
        assert sanitize_filename("../../etc/passwd") == "passwd"
        assert sanitize_filename("..\\windows\\system32.log") == "system32.log"

    def test_unsafe_chars_replaced(self):
        assert sanitize_filename("my log; rm -rf.txt") == "my_log__rm_-rf.txt"

    def test_empty_and_none_fall_back(self):
        assert sanitize_filename("") == "upload.log"
        assert sanitize_filename(None) == "upload.log"


class TestObjectKey:
    def test_key_format(self):
        key = build_object_key("job-123", "messages.log")
        assert key == "jobs/job-123/messages.log"

    def test_key_sanitizes_filename(self):
        key = build_object_key("job-123", "../../etc/passwd")
        assert key == "jobs/job-123/passwd"
        assert ".." not in key


class TestStorageReference:
    def test_round_trip(self):
        ref = StorageReference(backend="s3", bucket="b", key="jobs/1/a.log")
        assert StorageReference.from_dict(ref.to_dict()) == ref

    def test_to_dict_is_json_safe(self):
        import json

        ref = StorageReference(backend="local", bucket="", key="jobs/1/a.log")
        assert json.loads(json.dumps(ref.to_dict())) == ref.to_dict()

    def test_from_dict_rejects_bad_input(self):
        with pytest.raises(ValueError):
            StorageReference.from_dict({"backend": "s3", "bucket": "b"})  # no key
        with pytest.raises(ValueError):
            StorageReference.from_dict(
                {"backend": "ftp", "bucket": "b", "key": "k"}
            )
        with pytest.raises(ValueError):
            StorageReference.from_dict("not-a-dict")


class TestLocalStorageBackend:
    def test_put_open_round_trip(self, tmp_path):
        backend = LocalStorageBackend(root=str(tmp_path))
        ref = backend.put_stream("jobs/1/a.log", io.BytesIO(b"line1\nline2\n"))
        assert ref.backend == "local"
        assert ref.key == "jobs/1/a.log"
        assert backend.exists(ref)
        with backend.open_stream(ref) as stream:
            assert stream.read() == b"line1\nline2\n"

    def test_stream_to_text_lines(self, tmp_path):
        backend = LocalStorageBackend(root=str(tmp_path))
        ref = backend.put_stream("jobs/1/a.log", io.BytesIO("héllo\nwörld\n".encode()))
        with backend.open_stream(ref) as stream:
            assert stream_to_text_lines(stream) == ["héllo\n", "wörld\n"]

    def test_delete(self, tmp_path):
        backend = LocalStorageBackend(root=str(tmp_path))
        ref = backend.put_stream("jobs/1/a.log", io.BytesIO(b"x"))
        backend.delete(ref)
        assert not backend.exists(ref)
        backend.delete(ref)  # idempotent

    def test_traversal_key_rejected(self, tmp_path):
        backend = LocalStorageBackend(root=str(tmp_path))
        with pytest.raises(ValueError):
            backend.put_stream("../escape.log", io.BytesIO(b"x"))
        # A hostile reference dict is rejected the same way.
        evil = StorageReference(backend="local", bucket="", key="../../evil")
        assert not backend.exists(evil)
        with pytest.raises((ValueError, FileNotFoundError)):
            with backend.open_stream(evil):
                pass

    def test_wrong_backend_reference_rejected(self, tmp_path):
        backend = LocalStorageBackend(root=str(tmp_path))
        s3ref = StorageReference(backend="s3", bucket="b", key="k")
        with pytest.raises(ValueError):
            with backend.open_stream(s3ref):
                pass

    def test_missing_object(self, tmp_path):
        backend = LocalStorageBackend(root=str(tmp_path))
        ref = StorageReference(backend="local", bucket="", key="jobs/nope/a.log")
        assert not backend.exists(ref)
        with pytest.raises(FileNotFoundError):
            with backend.open_stream(ref):
                pass


class TestBuildStorageBackend:
    def test_unknown_backend_raises(self):
        with pytest.raises(RuntimeError, match="unknown STORAGE_BACKEND"):
            build_storage_backend(backend="ftp")

    def test_local_default(self, tmp_path):
        backend = build_storage_backend(backend="local", local_dir=str(tmp_path))
        assert isinstance(backend, LocalStorageBackend)

    def test_s3_missing_config_fails_fast(self):
        # Fails on missing config BEFORE boto3 is even imported.
        with pytest.raises(RuntimeError, match="S3_ENDPOINT_URL"):
            build_storage_backend(backend="s3")

    def test_s3_without_boto3_explains_itself(self):
        if importlib.util.find_spec("boto3") is not None:
            pytest.skip("boto3 is installed; cannot test the missing-boto3 path")
        with pytest.raises(RuntimeError, match="boto3"):
            build_storage_backend(
                backend="s3",
                s3_endpoint_url="http://localhost:9000",
                s3_access_key="ak",
                s3_secret_key="sk",
            )


class TestBackendFromSettings:
    def test_duck_typed_settings(self, tmp_path):
        class FakeSettings:
            storage_backend = "local"
            local_upload_dir = str(tmp_path)
            s3_endpoint_url = None
            s3_access_key = None
            s3_secret_key = None
            s3_bucket = "b"
            s3_region = "us-east-1"

        backend = backend_from_settings(FakeSettings())
        assert isinstance(backend, LocalStorageBackend)
