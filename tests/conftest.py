import os
import tempfile

# Trust/safety baseline: importing the app fails fast unless the bootstrap
# admin identity is configured. Provide test-only credentials so the suite can
# import the app under pytest. Never used outside the test suite.
os.environ.setdefault("ADMIN_USERNAME", "test-admin")
os.environ.setdefault(
    "ADMIN_PASSWORD_HASH",
    "$2b$12$X.m9BbKu7XC9SABo6YiDqOF4lxzqLFkja5AqjBnmL9RuWIc7Ocf8a",  # bcrypt("admin123"), test-only
)

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.core.config import settings
from src.db.database import Base, get_db


@pytest.fixture(scope="session")
def postgres_container():
    """Start PostgreSQL container for tests.

    testcontainers is imported lazily so pure unit tests (which never
    request this fixture) can run without the package -- and without
    Docker -- installed.
    """
    from testcontainers.postgres import PostgresContainer

    with PostgresContainer("postgres:15") as postgres:
        yield postgres


@pytest.fixture(scope="session")
def test_db_url(postgres_container):
    """Get test database URL"""
    return postgres_container.get_connection_url()


@pytest.fixture(scope="session")
def configure_test_database(test_db_url):
    """Configure all database connections to use test database.

    NOT autouse: only tests that request a DB fixture (test_engine and
    everything built on it) trigger the Docker Postgres container.
    Pure unit tests (matcher, chunking, storage, events, dedup, AST
    guards) run with no Docker and no database at all -- this is what
    lets CI run them on a plain runner.
    """
    import os
    # Set environment variable so worker uses test database
    os.environ["DATABASE_URL"] = test_db_url
    # Re-import settings to pick up new database URL
    from src.core.config import settings
    settings.database_url = test_db_url
    yield


@pytest.fixture(scope="session")
def test_engine(test_db_url, configure_test_database):
    """Create test database engine and clear stale data.

    Explicitly depends on configure_test_database so any test using a
    DB fixture gets the Docker container + settings pointed at it.
    """
    # Ensure we use the test database URL
    import os
    os.environ["DATABASE_URL"] = test_db_url

    engine = create_engine(test_db_url)

    # Clear all tables to remove stale data from previous runs
    from sqlalchemy import text
    from sqlalchemy.exc import ProgrammingError

    with engine.connect() as conn:
        try:
            # Truncate all tables in correct order (respecting FK constraints)
            # Order: child tables first, then parent tables
            conn.execute(text("TRUNCATE TABLE incident_activities CASCADE"))
            conn.execute(text("TRUNCATE TABLE incidents CASCADE"))
            conn.execute(text("TRUNCATE TABLE jobs CASCADE"))
            conn.execute(text("TRUNCATE TABLE patterns CASCADE"))
            conn.execute(text("TRUNCATE TABLE nodes CASCADE"))
            conn.commit()
        except ProgrammingError:
            # Tables may not exist yet on fresh database, that's OK
            conn.rollback()

    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def test_db_session(test_engine):
    """Create test database session.

    Truncates all tables on teardown (replaces the old autouse
    cleanup_tables fixture, which forced Docker on every test).
    """
    TestingSessionLocal = sessionmaker(
        autocommit=False, autoflush=False, bind=test_engine
    )
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        from sqlalchemy import text
        with test_engine.connect() as conn:
            conn.execute(text("TRUNCATE TABLE incident_activities CASCADE"))
            conn.execute(text("TRUNCATE TABLE incidents CASCADE"))
            conn.execute(text("TRUNCATE TABLE jobs CASCADE"))
            conn.execute(text("TRUNCATE TABLE patterns CASCADE"))
            conn.execute(text("TRUNCATE TABLE nodes CASCADE"))
            conn.commit()


@pytest.fixture
def override_get_db(test_db_session):
    """Override get_db dependency for tests"""

    def _override_get_db():
        try:
            yield test_db_session
        finally:
            pass

    return _override_get_db


@pytest.fixture
def sample_log_file():
    """Create a temporary log file for testing"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
        f.write("2024-01-01 10:00:00 INFO System started\n")
        f.write("2024-01-01 10:01:00 ERROR Disk failure detected on /dev/sda\n")
        f.write("2024-01-01 10:02:00 WARNING Network timeout occurred\n")
        f.write("2024-01-01 10:03:00 CRITICAL Memory pressure detected\n")
        f.write("2024-01-01 10:04:00 INFO User authentication failed\n")
        temp_file_path = f.name

    yield temp_file_path

    # Cleanup
    if os.path.exists(temp_file_path):
        os.remove(temp_file_path)


@pytest.fixture
def test_node(test_db_session):
    """Create a test node."""
    import time

    from src.models import Node

    # Use unique hostname to avoid conflicts
    node = Node(
        hostname=f"test-node-{time.time()}",
        ip_address="192.168.1.100",
        node_type="storage",
    )
    test_db_session.add(node)
    test_db_session.commit()
    test_db_session.refresh(node)
    return node


@pytest.fixture
def test_patterns(test_db_session):
    """Create test patterns."""
    import time

    from src.models import Pattern

    patterns = [
        Pattern(
            name=f"Test Disk Failure {time.time()}",
            description="Disk failure detected",
            regex_pattern=r"disk.*fail",
            category="hardware",
            severity_level="CRITICAL",
        ),
        Pattern(
            name=f"Test Network Timeout {time.time()}",
            description="Network timeout",
            regex_pattern=r"network.*timeout",
            category="network",
            severity_level="HIGH",
        ),
    ]

    for pattern in patterns:
        test_db_session.add(pattern)
    test_db_session.commit()

    for pattern in patterns:
        test_db_session.refresh(pattern)

    return patterns


@pytest.fixture
def sample_log_lines():
    """Sample log lines for testing"""
    return [
        "2024-01-01 10:00:00 INFO System started",
        "2024-01-01 10:01:00 ERROR Disk failure detected on /dev/sda",
        "2024-01-01 10:02:00 WARNING Network timeout occurred",
        "2024-01-01 10:03:00 CRITICAL Memory pressure detected",
        "2024-01-01 10:04:00 INFO User authentication failed",
    ]
