import pytest
from db import get_connection

@pytest.fixture
def client():
    """Create test client"""
    from app import app
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

@pytest.fixture(autouse=True)
def clean_database():
    """Clean database before each test"""
    with get_connection() as conn:
        cur = conn.cursor()
        # Delete in order due to foreign key constraints
        cur.execute("DELETE FROM projects")
        cur.execute("DELETE FROM users")
        conn.commit()
        cur.close()
    yield
