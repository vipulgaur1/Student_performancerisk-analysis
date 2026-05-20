import sqlite3
import os
from flask import g

DATABASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'database.db')


def get_db():
    """Return the per-request database connection, creating it if needed."""
    if '_database' not in g:
        g._database = sqlite3.connect(DATABASE)
        g._database.row_factory = sqlite3.Row
        _ensure_extra_tables(g._database)
    return g._database


def _ensure_extra_tables(conn):
    """Create any tables added after the initial schema without dropping existing data."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS interventions (
            student_id            TEXT PRIMARY KEY,
            mentoring_done        INTEGER DEFAULT 0,
            remedial_assigned     INTEGER DEFAULT 0,
            parent_contacted      INTEGER DEFAULT 0,
            counselling_suggested INTEGER DEFAULT 0,
            notes                 TEXT    DEFAULT '',
            updated_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.commit()


def init_db():
    """
    Initialise the database from schema.sql.
    Uses a direct connection (not get_db) so it can be called
    outside of a request context (e.g. from app startup).
    """
    schema_path = os.path.join(os.path.dirname(__file__), 'schema.sql')

    if not os.path.exists(schema_path):
        raise FileNotFoundError(f"Schema file not found: {schema_path}")

    conn = sqlite3.connect(DATABASE)
    try:
        with open(schema_path, 'r') as f:
            conn.executescript(f.read())
        conn.commit()
        print(f"Database initialised at: {DATABASE}")
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def close_connection(exception=None):
    """Teardown helper -- close DB connection at end of request."""
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()
