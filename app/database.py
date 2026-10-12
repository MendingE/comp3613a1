import logging
import threading
import time
from contextlib import contextmanager

from sqlalchemy import MetaData, inspect
from sqlalchemy.exc import DBAPIError, OperationalError, ProgrammingError
from sqlmodel import SQLModel, Session, create_engine

from app.config import get_settings

logger = logging.getLogger(__name__)

_schema_lock = threading.Lock()


def sqlalchemy_uri(uri: str) -> str:
    """Accept Render's postgres:// URLs in the sync SQLAlchemy engine."""
    if uri.startswith("postgres://"):
        return "postgresql+psycopg2://" + uri[len("postgres://") :]
    if uri.startswith("postgresql://"):
        return "postgresql+psycopg2://" + uri[len("postgresql://") :]
    return uri


engine = create_engine(
    sqlalchemy_uri(get_settings().database_uri),
    echo=get_settings().env.lower()
    in ["dev", "development", "test", "testing", "staging"],
    pool_size=get_settings().db_pool_size,
    max_overflow=get_settings().db_additional_overflow,
    pool_timeout=get_settings().db_pool_timeout,
    pool_recycle=get_settings().db_pool_recycle,
)


def create_db_and_tables() -> None:
    # Ensure model modules are imported so tables are registered on metadata.
    import app.models  # noqa: F401

    SQLModel.metadata.create_all(engine)
    _repair_empty_legacy_eventregistration_table()


def _repair_empty_legacy_eventregistration_table() -> None:
    """Rebuild only the known empty SQLite table left by the earlier model."""
    if engine.dialect.name != "sqlite":
        return

    from app.models.event import EventRegistration

    table_name = EventRegistration.__tablename__
    staging_name = "_eventregistration_repair"
    expected_columns = list(EventRegistration.__table__.columns.keys())

    with engine.connect() as connection:
        connection.exec_driver_sql("BEGIN IMMEDIATE")
        try:
            inspector = inspect(connection)
            if not inspector.has_table(table_name):
                connection.commit()
                return

            columns = inspector.get_columns(table_name)
            column_names = [column["name"] for column in columns]
            if column_names == expected_columns:
                indexes = inspector.get_indexes(table_name)
                stale_staging_indexes = [
                    index["name"]
                    for index in indexes
                    if index["name"].startswith("ix__eventregistration_repair_")
                ]
                for index_name in stale_staging_indexes:
                    connection.exec_driver_sql(
                        f'DROP INDEX "{index_name}"'
                    )

                existing_index_names = {
                    index["name"] for index in inspector.get_indexes(table_name)
                }
                for index in EventRegistration.__table__.indexes:
                    if index.name not in existing_index_names:
                        index.create(connection, checkfirst=False)
                connection.commit()
                return

            is_known_legacy_shape = (
                column_names == ["registration_id"]
                and str(columns[0]["type"]).upper() == "INTEGER"
                and not columns[0]["nullable"]
                and columns[0]["primary_key"] == 1
                and not inspector.get_indexes(table_name)
                and not inspector.get_foreign_keys(table_name)
                and not inspector.get_unique_constraints(table_name)
            )
            if not is_known_legacy_shape:
                raise RuntimeError(
                    "Cannot safely repair eventregistration: its schema is not "
                    "the known legacy shape."
                )

            row_count = connection.exec_driver_sql(
                f'SELECT COUNT(*) FROM "{table_name}"'
            ).scalar_one()
            if row_count != 0:
                raise RuntimeError(
                    "Cannot safely repair eventregistration: the legacy table "
                    "contains data."
                )
            if inspector.has_table(staging_name):
                raise RuntimeError(
                    "Cannot safely repair eventregistration: the repair staging "
                    "table already exists."
                )

            repair_metadata = MetaData()
            for related_table_name in ("alumnus", "event"):
                SQLModel.metadata.tables[related_table_name].to_metadata(
                    repair_metadata
                )
            repair_table = EventRegistration.__table__.to_metadata(
                repair_metadata, name=staging_name
            )
            repair_table.indexes.clear()
            repair_table.create(connection)
            connection.exec_driver_sql(f'DROP TABLE "{table_name}"')
            connection.exec_driver_sql(
                f'ALTER TABLE "{staging_name}" RENAME TO "{table_name}"'
            )
            for index in EventRegistration.__table__.indexes:
                index.create(connection, checkfirst=False)

            violations = connection.exec_driver_sql(
                f'PRAGMA foreign_key_check("{table_name}")'
            ).all()
            if violations:
                raise RuntimeError(
                    "Foreign-key validation failed after repairing "
                    "eventregistration."
                )
            connection.commit()
        except Exception:
            connection.rollback()
            raise


def drop_all() -> None:
    SQLModel.metadata.drop_all(bind=engine)


def is_db_not_ready_error(exc: BaseException) -> bool:
    """True when Postgres is unreachable or the schema/tables are missing."""
    if isinstance(exc, OperationalError):
        return True
    if isinstance(exc, ProgrammingError):
        return True
    if isinstance(exc, DBAPIError) and getattr(exc, "connection_invalidated", False):
        return True

    text = str(exc).lower()
    markers = (
        "does not exist",
        "undefinedtable",
        "undefined table",
        "no such table",
        "relation ",
        "could not connect",
        "connection refused",
        "connection timed out",
        "server closed the connection",
        "the database system is starting up",
        "remaining connection slots",
        "too many connections",
        "ssl connection has been closed",
    )
    return any(m in text for m in markers)


def ensure_db_and_tables(
    *,
    retries: int = 8,
    delay_seconds: float = 2.0,
) -> None:
    """Create tables, retrying while the prod DB is still coming up."""
    last: BaseException | None = None
    for attempt in range(1, retries + 1):
        try:
            with _schema_lock:
                create_db_and_tables()
            if attempt > 1:
                logger.info("Database schema ready after %s attempt(s)", attempt)
            return
        except Exception as exc:  # noqa: BLE001 — first-boot resilience
            last = exc
            if not is_db_not_ready_error(exc) or attempt >= retries:
                raise
            logger.warning(
                "Database not ready (attempt %s/%s): %s",
                attempt,
                retries,
                exc,
            )
            time.sleep(delay_seconds * attempt)
    if last is not None:
        raise last


def recover_if_uninitialized(exc: BaseException) -> bool:
    """If *exc* looks like a missing schema, create tables and return True."""
    if not is_db_not_ready_error(exc):
        return False
    logger.warning("Uninitialized database detected; creating tables: %s", exc)
    ensure_db_and_tables()
    return True


def _session_generator():
    with Session(engine) as session:
        try:
            yield session
        except Exception as e:
            logger.error(f"Database session error: {e}")
            raise
        finally:
            session.close()


def get_session():
    yield from _session_generator()


@contextmanager
def get_cli_session():
    yield from _session_generator()
