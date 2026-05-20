import os
from contextlib import contextmanager
from datetime import datetime, timezone

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session

_engine = None
_SessionLocal = None


def get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(
            os.environ["DATABASE_URL"],
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
        )
    return _engine


def get_session_factory():
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine(), expire_on_commit=False)
    return _SessionLocal


@contextmanager
def db_session() -> Session:
    factory = get_session_factory()
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def log_run(session: Session, lane: str, action: str, payload: dict, result: dict, success: bool):
    """Append-only audit log -- never update, only insert."""
    session.execute(
        text("""
            INSERT INTO run_log (lane, action, payload, result, success, created_at)
            VALUES (:lane, :action, :payload::jsonb, :result::jsonb, :success, :created_at)
        """),
        {
            "lane": lane,
            "action": action,
            "payload": __import__("json").dumps(payload),
            "result": __import__("json").dumps(result),
            "success": success,
            "created_at": datetime.now(timezone.utc),
        },
    )


def log_income_event(session: Session, lane: str, event_type: str, amount_usd: float, metadata: dict):
    session.execute(
        text("""
            INSERT INTO income_events (lane, event_type, amount_usd, metadata, created_at)
            VALUES (:lane, :event_type, :amount_usd, :metadata::jsonb, :created_at)
        """),
        {
            "lane": lane,
            "event_type": event_type,
            "amount_usd": amount_usd,
            "metadata": __import__("json").dumps(metadata),
            "created_at": datetime.now(timezone.utc),
        },
    )
