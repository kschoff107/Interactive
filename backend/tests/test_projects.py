import pytest
from flask_jwt_extended import create_access_token

@pytest.fixture
def auth_token():
    """Create auth token for test user"""
    from db import get_connection
    from models import User

    with get_connection() as conn:
        cur = conn.cursor()

        password_hash = User.hash_password('password123')
        cur.execute(
            'INSERT INTO users (username, email, password_hash) VALUES (%s, %s, %s) RETURNING id',
            ('testuser', 'test@example.com', password_hash)
        )
        user_id = cur.fetchone()['id']

    return create_access_token(identity=user_id)

def test_list_projects_empty(client, auth_token):
    """Test listing projects when none exist"""
    response = client.get('/api/projects', headers={'Authorization': f'Bearer {auth_token}'})
    assert response.status_code == 200
    data = response.get_json()
    assert data['projects'] == []

def test_create_project(client, auth_token):
    """Test creating a project"""
    response = client.post('/api/projects',
        headers={'Authorization': f'Bearer {auth_token}'},
        json={
            'name': 'Test Project',
            'description': 'A test project'
        })
    assert response.status_code == 201
    data = response.get_json()
    assert data['project']['name'] == 'Test Project'
    assert 'id' in data['project']
