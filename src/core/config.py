import secrets
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings


def _default_secret_key() -> str:
    """Generate an ephemeral JWT signing key when SECRET_KEY is not set.

    pydantic-settings only calls this when the SECRET_KEY environment variable
    is absent. An ephemeral key means tokens do not survive process restarts,
    but it guarantees no two deployments accidentally share a hardcoded
    default. Set SECRET_KEY explicitly in production.
    """
    return secrets.token_urlsafe(32)


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+psycopg2://postgres:postgres@postgres:5432/log_intelligence"

    # Connection pool (Postgres only -- sqlite keeps a single shared
    # connection via StaticPool for dev/test). Tune for the number of
    # API workers x threads plus Celery worker concurrency.
    database_pool_size: int = 5
    database_max_overflow: int = 10

    # Redis
    redis_url: str = "redis://redis:6379/0"

    # Domain event bus (Redis pub/sub) for job/incident events. The SSE
    # endpoint subscribes instead of polling the DB every second.
    #   "redis":  redis-py pub/sub against redis_url (above) — required
    #             when the API and Celery workers run in separate
    #             containers, since events must cross process boundaries.
    #   "memory": process-local fan-out. Tests and single-process dev
    #             only; workers in other processes won't see these events.
    event_bus: str = "redis"

    # Celery
    celery_broker_url: str = "redis://redis:6379/0"
    celery_result_backend: str = "redis://redis:6379/0"

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_debug: bool = False

    # gRPC streaming (typed alternative to SSE over the same event bus).
    # Runs alongside FastAPI on its own port; lifecycle is tied to the
    # app's startup/shutdown handlers. Disable with GRPC_ENABLED=false.
    grpc_enabled: bool = True
    grpc_port: int = 50051

    # Security
    # No default is committed. If SECRET_KEY is unset, an ephemeral per-process
    # key is generated (JWTs won't survive restarts). Set SECRET_KEY in prod.
    secret_key: str = Field(default_factory=_default_secret_key)
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # Log Processing
    max_file_size_mb: int = 2048
    chunk_size: int = 8192
    pattern_library_path: str = "./patterns/"

    # --- Chunked pipeline (Celery group + chord fan-out) ---
    # Object-storage uploads are split into line-count chunks processed by
    # parallel workers. Distinct from chunk_size above (a byte count used
    # for streaming I/O); this one bounds the work unit per worker.
    chunk_lines: int = 10000

    # --- Upload object storage (API -> Celery handoff) ---
    # The API streams multipart uploads into the configured backend and hands
    # the worker a content reference (backend + bucket + key) — never a local
    # filesystem path, so the handoff works when the API and worker run in
    # separate containers with no shared volume.
    #   "local": plain files under local_upload_dir. Dev, tests, and
    #            single-host deployments where API and worker share a disk.
    #   "s3":    any S3-compatible endpoint via boto3 (MinIO in compose,
    #            AWS S3 in production). Fails fast when the S3_* vars below
    #            are unset.
    storage_backend: str = "local"
    local_upload_dir: str = "./uploads"
    s3_endpoint_url: Optional[str] = None
    s3_access_key: Optional[str] = None
    s3_secret_key: Optional[str] = None
    s3_bucket: str = "pscale-async-uploads"
    s3_region: str = "us-east-1"

    # OneFS Cluster Configuration — no defaults are committed. Real-cluster
    # features fail fast in OneFSClient when these are unset; set
    # ONEFS_MOCK_MODE=true for local development without a cluster.
    onefs_mock_mode: bool = False
    onefs_host: Optional[str] = None
    onefs_ssh_port: int = 22  # SSH port - Set ONEFS_SSH_PORT in production
    onefs_api_port: int = 8080  # HTTP API port - Set ONEFS_API_PORT in production
    onefs_user: Optional[str] = None
    onefs_pass: str = ""  # Set ONEFS_PASS in production (never commit real credentials)
    onefs_ssh_key_path: str = "~/.ssh/id_rsa"  # Set ONEFS_SSH_KEY_PATH in production

    # Allowed base directory for remote log reads (defense against path traversal)
    onefs_log_dir: str = "/var/log"

    # Legacy / Demo OneFS Tunnel Configuration (kept for compatibility;
    # prefer ONEFS_HOST / ONEFS_USER — these legacy aliases also fail fast
    # when unset)
    cluster_host: Optional[str] = None  # Legacy alias for onefs_host
    cluster_port: int = 22  # Mapped from onefs_ssh_port
    cluster_api_port: int = 8080  # Mapped from onefs_api_port
    isilon_user: Optional[str] = None  # Legacy alias for onefs_user
    isilon_pass: str = ""  # Mapped from onefs_pass
    ssh_key_path: str = "~/.ssh/id_rsa"  # Mapped from onefs_ssh_key_path

    # Legacy OneFS Tunnel Configuration (for Docker service names - disable for direct SSH)
    isilon_host: str = "localhost"  # Changed from "isilon-tunnel" to "localhost" for direct connection
    isilon_port: int = 8080

    class Config:
        env_file = ".env"


settings = Settings()
