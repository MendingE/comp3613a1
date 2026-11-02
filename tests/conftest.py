import os
import sys
from importlib import import_module
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import make_url
from sqlmodel import Session

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEST_DATA_DIR = PROJECT_ROOT / ".test-data"
TEST_DATABASE_PATH = TEST_DATA_DIR / "assignment2-tests.sqlite3"
DEVELOPMENT_DATABASE_PATH = PROJECT_ROOT / "database.db"

if any(module == "app" or module.startswith("app.") for module in sys.modules):
    raise RuntimeError(
        "The application was imported before the isolated test database was configured."
    )
if TEST_DATA_DIR.is_symlink() or TEST_DATABASE_PATH.is_symlink():
    raise RuntimeError("The test database path must not be a symbolic link.")

resolved_test_path = TEST_DATABASE_PATH.resolve()
resolved_development_path = DEVELOPMENT_DATABASE_PATH.resolve()
if resolved_test_path == resolved_development_path:
    raise RuntimeError("The test database cannot be the development database.")
if (
    TEST_DATABASE_PATH.exists()
    and DEVELOPMENT_DATABASE_PATH.exists()
    and os.path.samefile(TEST_DATABASE_PATH, DEVELOPMENT_DATABASE_PATH)
):
    raise RuntimeError("The test database cannot share the development database file.")

TEST_DATA_DIR.mkdir(exist_ok=True)
TEST_DATABASE_URI = f"sqlite:///{TEST_DATABASE_PATH.as_posix()}"
test_url = make_url(TEST_DATABASE_URI)
if (
    test_url.get_backend_name() != "sqlite"
    or not test_url.database
    or Path(test_url.database).resolve() != resolved_test_path
):
    raise RuntimeError("The test database URI is not the expected local SQLite file.")

os.environ["DATABASE_URI"] = TEST_DATABASE_URI
os.environ["ENV"] = "testing"

from app.database import engine, get_session
from app.main import app as fastapi_app


def _assert_isolated_engine() -> None:
    database = engine.url.database
    if (
        engine.url.get_backend_name() != "sqlite"
        or not database
        or Path(database).resolve() != resolved_test_path
        or os.environ.get("DATABASE_URI") != TEST_DATABASE_URI
    ):
        raise RuntimeError(
            "Tests must use the dedicated SQLite database at "
            f"{resolved_test_path}; refusing to use another database."
        )


_assert_isolated_engine()


@pytest.fixture(scope="session")
def app():
    _assert_isolated_engine()
    return fastapi_app


@pytest.fixture(autouse=True)
def db_session():
    from app.database import create_db_and_tables, drop_all

    _assert_isolated_engine()
    import_module("app.models")
    drop_all()
    create_db_and_tables()
    try:
        with Session(engine) as session:
            yield session
    finally:
        drop_all()


@pytest.fixture
def client(app, db_session):
    _assert_isolated_engine()
    missing = object()
    previous_override = app.dependency_overrides.get(get_session, missing)

    def override_session():
        _assert_isolated_engine()
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        if previous_override is missing:
            app.dependency_overrides.pop(get_session, None)
        else:
            app.dependency_overrides[get_session] = previous_override
