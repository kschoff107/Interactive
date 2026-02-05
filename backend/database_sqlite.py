import sqlite3
import os
from contextlib import contextmanager
from config import Config

def dict_factory(cursor, row):
    """Convert row to dictionary"""
    fields = [column[0] for column in cursor.description]
    return {key: value for key, value in zip(fields, row)}

@contextmanager
def get_connection():
    """Get database connection as context manager"""
    # Extract database path from DATABASE_URL
    db_url = Config.SQLALCHEMY_DATABASE_URI
    if db_url.startswith('sqlite:///'):
        db_path = db_url.replace('sqlite:///', '')
    else:
        raise ValueError("DATABASE_URL must be SQLite format")

    # Get absolute path
    if not os.path.isabs(db_path):
        db_path = os.path.join(os.path.dirname(__file__), db_path)

    conn = sqlite3.connect(db_path)
    conn.row_factory = dict_factory
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
