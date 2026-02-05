import psycopg2
from psycopg2.extras import RealDictCursor
from config import Config

def get_connection():
    """Get database connection with dict cursor"""
    conn = psycopg2.connect(Config.SQLALCHEMY_DATABASE_URI)
    conn.cursor_factory = RealDictCursor
    return conn
