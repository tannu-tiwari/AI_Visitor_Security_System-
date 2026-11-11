import os
import sqlite3
from contextlib import contextmanager

from flask import has_app_context
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import event, inspect, text
from sqlalchemy.engine import Engine

# Database configuration
#
# The SQLite file lives inside the project's data/ directory by default and
# can be overridden with the VISITOR_DB_PATH environment variable or the
# database_path argument to init_database(). Paths are resolved from the
# project root, so they do not depend on the current working directory.

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DB_PATH = os.path.join(BASE_DIR, "data", "visitor_management.db")
ENV_DB_PATH = "VISITOR_DB_PATH"

db = SQLAlchemy()

_application = None

USER_COLUMN_ADDITIONS = {
    "role": "VARCHAR(20) CHECK (role IN ('admin', 'security', 'host'))",
    "department": "VARCHAR(120)",
}

VISITOR_COLUMN_ADDITIONS = {
    "host_user_id": "INTEGER REFERENCES users(id) ON DELETE SET NULL",
}


def resolve_database_path(database_path=None):
    """Return the configured SQLite file path (absolute)."""
    path = database_path or os.environ.get(ENV_DB_PATH) or DEFAULT_DB_PATH
    return os.path.abspath(path)


def sqlite_uri(database_path):
    """Build a SQLAlchemy SQLite URI for an absolute filesystem path."""
    # SQLAlchemy needs forward slashes in the absolute path on Windows.
    return "sqlite:///" + database_path.replace("\\", "/")


@event.listens_for(Engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_connection, connection_record):
    # SQLite does not enforce foreign keys unless asked to, per connection.
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def init_database(app, database_path=None):
    """
    Configure Flask-SQLAlchemy for this app and create missing tables.

    Safe to call on every startup: create_all() only creates tables that do
    not exist yet and never drops or overwrites data.
    """
    global _application

    path = resolve_database_path(database_path)
    os.makedirs(os.path.dirname(path), exist_ok=True)

    app.config.setdefault("SQLALCHEMY_TRACK_MODIFICATIONS", False)
    app.config["SQLALCHEMY_DATABASE_URI"] = sqlite_uri(path)
    app.config.setdefault(
        "SQLALCHEMY_ENGINE_OPTIONS",
        {
            "connect_args": {
                # The camera streaming thread logs alongside request threads.
                "check_same_thread": False,
                "timeout": 30,
            }
        },
    )

    db.init_app(app)
    _application = app

    with app.app_context():
        # Importing the models registers them with SQLAlchemy metadata.
        from . import models  # noqa: F401
        db.create_all()
        ensure_user_schema()
        ensure_visitor_schema()

    return path


def ensure_user_schema():
    """
    Add role/department columns to a pre-RBAC users table.

    SQLite cannot add a NOT NULL column without choosing a value for existing
    rows, and inventing a role would be unsafe. Existing accounts therefore get
    NULL (unassigned) and keep their password hashes until an administrator
    runs ``flask assign-role``. Fresh databases get the full model schema.
    """
    inspector = inspect(db.engine)
    if "users" not in inspector.get_table_names():
        return []

    existing_columns = {
        column["name"] for column in inspector.get_columns("users")
    }
    added = []

    with db.engine.begin() as connection:
        for column_name, definition in USER_COLUMN_ADDITIONS.items():
            if column_name in existing_columns:
                continue
            connection.execute(
                text(
                    f"ALTER TABLE users ADD COLUMN "
                    f"{column_name} {definition}"
                )
            )
            added.append(column_name)

    return added


def ensure_visitor_schema():
    """
    Add the host account link to a pre-assignment visitors table.

    The column is nullable because historical registrations only stored a host
    name and some names do not match an account. A unique, case-insensitive
    name match is backfilled; ambiguous names stay unassigned and are visible
    to administrators only.
    """
    inspector = inspect(db.engine)
    if "visitors" not in inspector.get_table_names():
        return []

    existing_columns = {
        column["name"] for column in inspector.get_columns("visitors")
    }
    added = []

    with db.engine.begin() as connection:
        for column_name, definition in VISITOR_COLUMN_ADDITIONS.items():
            if column_name in existing_columns:
                continue
            connection.execute(
                text(
                    f"ALTER TABLE visitors ADD COLUMN "
                    f"{column_name} {definition}"
                )
            )
            added.append(column_name)

        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_visitors_host_user_id "
                "ON visitors (host_user_id)"
            )
        )

        connection.execute(
            text("""
                UPDATE visitors
                SET host_user_id = (
                    SELECT users.id
                    FROM users
                    WHERE users.role = 'host'
                      AND users.is_active = 1
                      AND trim(users.full_name) <> ''
                      AND lower(trim(users.full_name)) =
                          lower(trim(visitors.host))
                    ORDER BY users.id
                    LIMIT 1
                )
                WHERE host_user_id IS NULL
                  AND trim(visitors.host) <> ''
                  AND (
                    SELECT count(*)
                    FROM users
                    WHERE users.role = 'host'
                      AND users.is_active = 1
                      AND trim(users.full_name) <> ''
                      AND lower(trim(users.full_name)) =
                          lower(trim(visitors.host))
                  ) = 1
            """)
        )

    return added


def commit_session():
    """Commit the current session, rolling back cleanly if anything fails."""
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise


@contextmanager
def app_scope():
    """
    Run database work inside an application context.

    Routes and the migration script already have one; the face-recognition
    streaming thread may not, so core modules use this instead of assuming.
    """
    if has_app_context():
        yield
        return

    if _application is None:
        raise RuntimeError(
            "Database is not initialized. Call init_database(app) first."
        )

    with _application.app_context():
        yield
