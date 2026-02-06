import sqlite3
import os
from contextlib import contextmanager
from config import Config

def dict_factory(cursor, row):
    """Convert row to dictionary"""
    fields = [column[0] for column in cursor.description]
    return {key: value for key, value in zip(fields, row)}

def dict_factory_pg(cursor, row):
    """Convert PostgreSQL row to dictionary"""
    if cursor.description is None:
        return None
    fields = [column[0] for column in cursor.description]
    return {key: value for key, value in zip(fields, row)}

class DictCursorWrapper:
    """Wrapper to make PostgreSQL cursor return dicts like SQLite"""
    def __init__(self, cursor):
        self._cursor = cursor

    def execute(self, query, params=None):
        """Execute query and return result"""
        if params:
            return self._cursor.execute(query, params)
        return self._cursor.execute(query)

    def fetchone(self):
        """Fetch one row as dict"""
        row = self._cursor.fetchone()
        if row is None:
            return None
        return dict_factory_pg(self._cursor, row)

    def fetchall(self):
        """Fetch all rows as list of dicts"""
        rows = self._cursor.fetchall()
        return [dict_factory_pg(self._cursor, row) for row in rows]

    @property
    def lastrowid(self):
        """Get last inserted row ID"""
        # PostgreSQL doesn't have lastrowid like SQLite
        # This should be handled by RETURNING clause in INSERT
        return getattr(self._cursor, 'lastrowid', None)

    @property
    def rowcount(self):
        """Get number of affected rows"""
        return self._cursor.rowcount

    def __getattr__(self, name):
        """Proxy other attributes to underlying cursor"""
        return getattr(self._cursor, name)

@contextmanager
def get_connection():
    """Get database connection as context manager"""
    db_url = Config.SQLALCHEMY_DATABASE_URI

    # Handle SQLite
    if db_url.startswith('sqlite:///'):
        db_path = db_url.replace('sqlite:///', '')

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

    # Handle PostgreSQL
    elif db_url.startswith('postgres://') or db_url.startswith('postgresql://'):
        import psycopg2
        from psycopg2.extras import RealDictCursor

        conn = psycopg2.connect(db_url)
        # Wrap connection to return dict cursor
        original_cursor = conn.cursor
        conn.cursor = lambda: DictCursorWrapper(original_cursor(cursor_factory=RealDictCursor))

        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    else:
        raise ValueError(f"Unsupported database URL format: {db_url}")
