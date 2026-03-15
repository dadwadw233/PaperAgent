import os
from contextlib import contextmanager

from sqlalchemy import event
from sqlalchemy.exc import OperationalError
from sqlmodel import Session
from sqlmodel import SQLModel, create_engine


def get_database_url() -> str:
    return os.getenv("DATABASE_URL", "sqlite:///./paper_agent.db")


def create_db_engine(echo: bool = False):
    database_url = get_database_url()
    is_sqlite = database_url.startswith("sqlite")
    connect_args = {"check_same_thread": False, "timeout": 30} if is_sqlite else {}
    engine = create_engine(database_url, echo=echo, connect_args=connect_args)
    if is_sqlite:
        @event.listens_for(engine, "connect")
        def _set_sqlite_pragma(dbapi_connection, _connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL;")
            cursor.execute("PRAGMA synchronous=NORMAL;")
            cursor.execute("PRAGMA busy_timeout=30000;")
            cursor.close()
    return engine


def get_session(engine=None) -> Session:
    if engine is None:
        engine = create_db_engine()
    return Session(engine)


@contextmanager
def session_scope(engine=None):
    session = get_session(engine)
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db(engine=None) -> None:
    if engine is None:
        engine = create_db_engine()
    try:
        SQLModel.metadata.create_all(engine)
    except OperationalError as exc:
        raise RuntimeError(f"Failed to initialize database: {exc}") from exc
