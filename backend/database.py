import psycopg2
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager
from config import Config

@contextmanager
def get_connection():
    """Get database connection with dict cursor as context manager"""
    conn = psycopg2.connect(Config.SQLALCHEMY_DATABASE_URI, cursor_factory=RealDictCursor)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
