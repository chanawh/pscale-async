from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool, StaticPool

from src.core.config import settings


def _engine_kwargs() -> dict:
    """Pool configuration by database backend.

    - sqlite (dev/test): single shared connection via StaticPool, same as
      before — in-memory and file DBs need check_same_thread=False.
    - Postgres (and anything else): a real QueuePool. The old code used
      StaticPool unconditionally, which meant every API worker thread and
      every Celery worker shared ONE connection — requests and chunk
      tasks serialized on it and a dropped connection killed the app.
    """
    if settings.database_url.startswith("sqlite"):
        return {
            "poolclass": StaticPool,
            "connect_args": {"check_same_thread": False},
        }
    return {
        "poolclass": QueuePool,
        "pool_size": settings.database_pool_size,
        "max_overflow": settings.database_max_overflow,
        "pool_pre_ping": True,  # recycle stale connections instead of failing
    }


# Create database engine
engine = create_engine(settings.database_url, **_engine_kwargs())

# Create SessionLocal class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create Base class for models
Base = declarative_base()


def create_tables():
    """Create all database tables if they don't exist"""
    # Import all models to ensure they're registered with Base
    from src.models import Incident, IncidentActivity, Job, Node, Pattern

    Base.metadata.create_all(bind=engine)


def get_db():
    """Dependency to get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
