import sqlite3
import os
from contextlib import contextmanager
from config import Config

def dict_factory(cursor, row):
    """Convert row to dictionary"""
    fields = [column[0] for column in cursor.description]
    return {key: value for key, value in zip(fields, row)}

class PostgreSQLConnectionWrapper:
    """Wrapper to make PostgreSQL connection work like SQLite"""
    def __init__(self, conn):
        self._conn = conn
        self._in_transaction = False

    def cursor(self):
        """Return a RealDictCursor that returns rows as dictionaries"""
        from psycopg2.extras import RealDictCursor
        return self._conn.cursor(cursor_factory=RealDictCursor)

    def commit(self):
        """Commit transaction"""
        return self._conn.commit()

    def rollback(self):
        """Rollback transaction"""
        return self._conn.rollback()

    def close(self):
        """Close connection"""
        return self._conn.close()

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        if exc_type is not None:
            self._conn.rollback()
        else:
            self._conn.commit()
        self._conn.close()

    def __getattr__(self, name):
        """Proxy other attributes to underlying connection"""
        return getattr(self._conn, name)

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

        conn = psycopg2.connect(db_url)
        wrapped_conn = PostgreSQLConnectionWrapper(conn)

        try:
            yield wrapped_conn
            wrapped_conn.commit()
        except Exception:
            wrapped_conn.rollback()
            raise
        finally:
            wrapped_conn.close()

    else:
        raise ValueError(f"Unsupported database URL format: {db_url}")
