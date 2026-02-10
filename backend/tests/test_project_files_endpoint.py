"""
Tests for GET /api/projects/<id>/files endpoint

Tests cover:
  1. Authentication requirements
  2. Project ownership verification
  3. Empty response when no files on disk
  4. File listing with nested directories
  5. Windows path normalization (backslashes → forward slashes)
  6. File size reporting
  7. Alphabetical sort order
"""
import os
import json
import pytest
import tempfile
import shutil
from unittest.mock import patch
from flask_jwt_extended import create_access_token

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


@pytest.fixture
def client():
    """Create test client"""
    from app import app
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def auth_token(client):
    """Create auth token for test user"""
    from database import get_connection
    from models import User
    from app import app

    with app.app_context():
        with get_connection() as conn:
            cur = conn.cursor()
            password_hash = User.hash_password('password123')
            cur.execute(
                'INSERT INTO users (username, email, password_hash) VALUES (%s, %s, %s) RETURNING id',
                ('filestestuser', 'filestest@example.com', password_hash)
            )
            user_id = cur.fetchone()['id']

        token = create_access_token(identity=str(user_id))

    return token, user_id


@pytest.fixture
def project_with_auth(client, auth_token):
    """Create a project and return (project_id, token, user_id)"""
    token, user_id = auth_token
    response = client.post('/api/projects',
        headers={'Authorization': f'Bearer {token}'},
        json={'name': 'Files Test', 'description': 'Test project for files endpoint'}
    )
    data = response.get_json()
    project_id = data['project']['id']
    return project_id, token, user_id


@pytest.fixture
def project_with_files(project_with_auth):
    """Create a project with actual files on disk"""
    project_id, token, user_id = project_with_auth

    # Create a temp directory with some files
    tmp_dir = tempfile.mkdtemp(prefix='codevis_test_')

    # Root-level files
    with open(os.path.join(tmp_dir, 'app.py'), 'w') as f:
        f.write('from flask import Flask\napp = Flask(__name__)\n')
    with open(os.path.join(tmp_dir, 'config.py'), 'w') as f:
        f.write('DEBUG = True\n')

    # Nested directory
    models_dir = os.path.join(tmp_dir, 'models')
    os.makedirs(models_dir)
    with open(os.path.join(models_dir, 'user.py'), 'w') as f:
        f.write('class User:\n    pass\n')
    with open(os.path.join(models_dir, 'post.py'), 'w') as f:
        f.write('class Post:\n    pass\n')

    # Deeper nesting
    utils_dir = os.path.join(tmp_dir, 'utils', 'helpers')
    os.makedirs(utils_dir)
    with open(os.path.join(utils_dir, 'format.py'), 'w') as f:
        f.write('def format_date(d): return str(d)\n')

    # Update project file_path in DB
    from database import get_connection
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute('UPDATE projects SET file_path = %s WHERE id = %s',
                    (tmp_dir, project_id))

    yield project_id, token, user_id, tmp_dir

    # Cleanup
    shutil.rmtree(tmp_dir, ignore_errors=True)


# ── Authentication ──────────────────────────────────────────────────────────

def test_files_requires_auth(client, project_with_auth):
    """GET /files without token returns 422"""
    project_id, _, _ = project_with_auth
    response = client.get(f'/api/projects/{project_id}/files')
    assert response.status_code == 422


def test_files_wrong_user(client, project_with_auth):
    """GET /files with different user's token returns 404"""
    project_id, _, _ = project_with_auth
    from app import app
    from database import get_connection
    from models import User

    with app.app_context():
        with get_connection() as conn:
            cur = conn.cursor()
            password_hash = User.hash_password('password123')
            cur.execute(
                'INSERT INTO users (username, email, password_hash) VALUES (%s, %s, %s) RETURNING id',
                ('otheruser', 'other@example.com', password_hash)
            )
            other_user_id = cur.fetchone()['id']

        other_token = create_access_token(identity=str(other_user_id))

    response = client.get(f'/api/projects/{project_id}/files',
        headers={'Authorization': f'Bearer {other_token}'})
    assert response.status_code == 404


def test_files_nonexistent_project(client, auth_token):
    """GET /files for non-existent project returns 404"""
    token, _ = auth_token
    response = client.get('/api/projects/99999/files',
        headers={'Authorization': f'Bearer {token}'})
    assert response.status_code == 404


# ── No files on disk ───────────────────────────────────────────────────────

def test_files_no_file_path(client, project_with_auth):
    """Project with no file_path returns empty list"""
    project_id, token, _ = project_with_auth
    response = client.get(f'/api/projects/{project_id}/files',
        headers={'Authorization': f'Bearer {token}'})
    assert response.status_code == 200
    data = response.get_json()
    assert data['files'] == []
    assert data['total_count'] == 0


def test_files_nonexistent_path(client, project_with_auth):
    """Project with file_path pointing to missing directory returns empty list"""
    project_id, token, _ = project_with_auth

    from database import get_connection
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute('UPDATE projects SET file_path = %s WHERE id = %s',
                    ('/nonexistent/path/12345', project_id))

    response = client.get(f'/api/projects/{project_id}/files',
        headers={'Authorization': f'Bearer {token}'})
    assert response.status_code == 200
    data = response.get_json()
    assert data['files'] == []
    assert data['total_count'] == 0


# ── File listing ───────────────────────────────────────────────────────────

def test_files_lists_all(client, project_with_files):
    """Endpoint returns all files including nested ones"""
    project_id, token, _, _ = project_with_files
    response = client.get(f'/api/projects/{project_id}/files',
        headers={'Authorization': f'Bearer {token}'})
    assert response.status_code == 200
    data = response.get_json()

    paths = [f['path'] for f in data['files']]
    assert data['total_count'] == 5
    assert 'app.py' in paths
    assert 'config.py' in paths
    assert 'models/user.py' in paths
    assert 'models/post.py' in paths
    assert 'utils/helpers/format.py' in paths


def test_files_type_is_file(client, project_with_files):
    """All entries have type 'file' (directories are implicit from paths)"""
    project_id, token, _, _ = project_with_files
    response = client.get(f'/api/projects/{project_id}/files',
        headers={'Authorization': f'Bearer {token}'})
    data = response.get_json()

    for f in data['files']:
        assert f['type'] == 'file'


def test_files_have_size(client, project_with_files):
    """All entries have a positive integer size"""
    project_id, token, _, _ = project_with_files
    response = client.get(f'/api/projects/{project_id}/files',
        headers={'Authorization': f'Bearer {token}'})
    data = response.get_json()

    for f in data['files']:
        assert isinstance(f['size'], int)
        assert f['size'] > 0


def test_files_sorted_alphabetically(client, project_with_files):
    """Files are returned in alphabetical order by path"""
    project_id, token, _, _ = project_with_files
    response = client.get(f'/api/projects/{project_id}/files',
        headers={'Authorization': f'Bearer {token}'})
    data = response.get_json()

    paths = [f['path'] for f in data['files']]
    assert paths == sorted(paths)


def test_files_use_forward_slashes(client, project_with_files):
    """All paths use forward slashes, even on Windows"""
    project_id, token, _, _ = project_with_files
    response = client.get(f'/api/projects/{project_id}/files',
        headers={'Authorization': f'Bearer {token}'})
    data = response.get_json()

    for f in data['files']:
        assert '\\' not in f['path'], f"Backslash found in path: {f['path']}"


def test_files_empty_directory(client, project_with_auth):
    """Project with an empty directory returns empty list"""
    project_id, token, _ = project_with_auth

    tmp_dir = tempfile.mkdtemp(prefix='codevis_test_empty_')

    from database import get_connection
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute('UPDATE projects SET file_path = %s WHERE id = %s',
                    (tmp_dir, project_id))

    response = client.get(f'/api/projects/{project_id}/files',
        headers={'Authorization': f'Bearer {token}'})
    assert response.status_code == 200
    data = response.get_json()
    assert data['files'] == []
    assert data['total_count'] == 0

    shutil.rmtree(tmp_dir, ignore_errors=True)
