"""
Tests for Phase 2: Git Import Backend Endpoints

Tests cover:
  1. GET /api/projects/git/tree - Fetch repository file tree
  2. POST /api/projects/<id>/import-git - Import files from GitHub
  3. Authentication requirements
  4. Input validation
  5. Error handling
"""
import os
import json
import pytest
from unittest.mock import patch, MagicMock
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
    """Create auth token for test user (matches existing pattern)"""
    from database import get_connection
    from models import User
    from app import app

    with app.app_context():
        with get_connection() as conn:
            cur = conn.cursor()
            password_hash = User.hash_password('password123')
            cur.execute(
                'INSERT INTO users (username, email, password_hash) VALUES (%s, %s, %s) RETURNING id',
                ('gittestuser', 'gittest@example.com', password_hash)
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
        json={'name': 'Git Import Test', 'description': 'Test project for git import'}
    )
    data = response.get_json()
    return data['project']['id'], token, user_id


# ---------------------------------------------------------------------------
# 1. GET /api/projects/git/tree
# ---------------------------------------------------------------------------

class TestGetGitTree:
    """Test the git tree endpoint"""

    @patch('routes.projects.GitApiService')
    def test_successful_tree_fetch(self, MockService, client, auth_token):
        token, _ = auth_token

        mock_instance = MockService.return_value
        mock_instance.parse_github_url.return_value = {
            'valid': True, 'owner': 'user', 'repo': 'flask-app',
            'branch': None, 'error': None
        }
        mock_instance.get_repo_tree.return_value = {
            'success': True,
            'files': [
                {'path': 'app.py', 'type': 'file', 'size': 2100},
                {'path': 'models', 'type': 'dir', 'size': 0},
                {'path': 'models/user.py', 'type': 'file', 'size': 1200},
            ],
            'branch': 'main',
            'truncated': False,
            'error': None
        }

        response = client.get(
            '/api/projects/git/tree?url=https://github.com/user/flask-app',
            headers={'Authorization': f'Bearer {token}'}
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data['owner'] == 'user'
        assert data['repo'] == 'flask-app'
        assert data['branch'] == 'main'
        assert len(data['files']) == 3
        assert data['truncated'] is False

    @patch('routes.projects.GitApiService')
    def test_tree_with_branch_in_url(self, MockService, client, auth_token):
        token, _ = auth_token

        mock_instance = MockService.return_value
        mock_instance.parse_github_url.return_value = {
            'valid': True, 'owner': 'user', 'repo': 'repo',
            'branch': 'develop', 'error': None
        }
        mock_instance.get_repo_tree.return_value = {
            'success': True, 'files': [], 'branch': 'develop',
            'truncated': False, 'error': None
        }

        response = client.get(
            '/api/projects/git/tree?url=https://github.com/user/repo/tree/develop',
            headers={'Authorization': f'Bearer {token}'}
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data['branch'] == 'develop'
        mock_instance.get_repo_tree.assert_called_with('user', 'repo', 'develop')

    def test_tree_missing_url_param(self, client, auth_token):
        token, _ = auth_token

        response = client.get(
            '/api/projects/git/tree',
            headers={'Authorization': f'Bearer {token}'}
        )

        assert response.status_code == 400
        assert 'URL parameter is required' in response.get_json()['error']

    @patch('routes.projects.GitApiService')
    def test_tree_invalid_url(self, MockService, client, auth_token):
        token, _ = auth_token

        mock_instance = MockService.return_value
        mock_instance.parse_github_url.return_value = {
            'valid': False, 'owner': None, 'repo': None,
            'branch': None, 'error': 'Only GitHub URLs are supported (github.com)'
        }

        response = client.get(
            '/api/projects/git/tree?url=https://gitlab.com/user/repo',
            headers={'Authorization': f'Bearer {token}'}
        )

        assert response.status_code == 400
        assert 'GitHub' in response.get_json()['error']

    @patch('routes.projects.GitApiService')
    def test_tree_repo_not_found(self, MockService, client, auth_token):
        token, _ = auth_token

        mock_instance = MockService.return_value
        mock_instance.parse_github_url.return_value = {
            'valid': True, 'owner': 'user', 'repo': 'nonexistent',
            'branch': None, 'error': None
        }
        mock_instance.get_repo_tree.return_value = {
            'success': False, 'files': [], 'branch': None,
            'truncated': False,
            'error': 'Repository not found. Make sure it exists and is public.'
        }

        response = client.get(
            '/api/projects/git/tree?url=https://github.com/user/nonexistent',
            headers={'Authorization': f'Bearer {token}'}
        )

        assert response.status_code == 400
        assert 'not found' in response.get_json()['error'].lower()

    def test_tree_requires_auth(self, client):
        """App returns 422 for missing auth (custom JWT handler)"""
        response = client.get('/api/projects/git/tree?url=https://github.com/user/repo')
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# 2. POST /api/projects/<id>/import-git
# ---------------------------------------------------------------------------

class TestImportFromGit:
    """Test the git import endpoint"""

    @patch('routes.projects.GitApiService')
    @patch('routes.projects.ParserManager')
    def test_successful_import(self, MockParser, MockGit, client, project_with_auth):
        project_id, token, user_id = project_with_auth

        # Mock git service
        mock_git = MockGit.return_value
        mock_git.parse_github_url.return_value = {
            'valid': True, 'owner': 'user', 'repo': 'flask-app',
            'branch': None, 'error': None
        }
        mock_git.download_files.return_value = {
            'success': True, 'downloaded': 2, 'failed': 0, 'errors': []
        }

        # Mock parser
        mock_parser = MockParser.return_value
        mock_parser.detect_language_and_framework.return_value = ('python', 'flask')
        mock_parser.parse_database_schema.return_value = {'tables': [], 'relationships': []}
        mock_parser.parse_runtime_flow.return_value = {'functions': [], 'calls': []}
        mock_parser.parse_api_routes.return_value = {'routes': [], 'blueprints': []}

        response = client.post(
            f'/api/projects/{project_id}/import-git',
            headers={'Authorization': f'Bearer {token}'},
            json={
                'url': 'https://github.com/user/flask-app',
                'files': ['app.py', 'models/user.py'],
                'branch': 'main'
            }
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data['message'] == 'Files imported from GitHub'
        assert data['downloaded'] == 2
        assert data['failed'] == 0
        assert data['language'] == 'python'
        assert data['framework'] == 'flask'

    def test_import_missing_url(self, client, project_with_auth):
        project_id, token, _ = project_with_auth

        response = client.post(
            f'/api/projects/{project_id}/import-git',
            headers={'Authorization': f'Bearer {token}'},
            json={'files': ['app.py']}
        )

        assert response.status_code == 400
        assert 'URL is required' in response.get_json()['error']

    def test_import_missing_files(self, client, project_with_auth):
        project_id, token, _ = project_with_auth

        response = client.post(
            f'/api/projects/{project_id}/import-git',
            headers={'Authorization': f'Bearer {token}'},
            json={'url': 'https://github.com/user/repo', 'files': []}
        )

        assert response.status_code == 400
        assert 'At least one file' in response.get_json()['error']

    def test_import_too_many_files(self, client, project_with_auth):
        project_id, token, _ = project_with_auth

        response = client.post(
            f'/api/projects/{project_id}/import-git',
            headers={'Authorization': f'Bearer {token}'},
            json={
                'url': 'https://github.com/user/repo',
                'files': [f'file{i}.py' for i in range(51)]
            }
        )

        assert response.status_code == 400
        assert 'Maximum 50' in response.get_json()['error']

    @patch('routes.projects.GitApiService')
    def test_import_invalid_url(self, MockService, client, project_with_auth):
        project_id, token, _ = project_with_auth

        mock_instance = MockService.return_value
        mock_instance.parse_github_url.return_value = {
            'valid': False, 'owner': None, 'repo': None,
            'branch': None, 'error': 'Only GitHub URLs are supported'
        }

        response = client.post(
            f'/api/projects/{project_id}/import-git',
            headers={'Authorization': f'Bearer {token}'},
            json={
                'url': 'https://gitlab.com/user/repo',
                'files': ['app.py']
            }
        )

        assert response.status_code == 400

    def test_import_nonexistent_project(self, client, auth_token):
        token, _ = auth_token

        response = client.post(
            '/api/projects/99999/import-git',
            headers={'Authorization': f'Bearer {token}'},
            json={
                'url': 'https://github.com/user/repo',
                'files': ['app.py']
            }
        )

        assert response.status_code == 404

    def test_import_requires_auth(self, client):
        """App returns 422 for missing auth (custom JWT handler)"""
        response = client.post(
            '/api/projects/1/import-git',
            json={'url': 'https://github.com/user/repo', 'files': ['app.py']}
        )
        assert response.status_code == 422

    @patch('routes.projects.GitApiService')
    def test_import_download_failure(self, MockService, client, project_with_auth):
        project_id, token, _ = project_with_auth

        mock_instance = MockService.return_value
        mock_instance.parse_github_url.return_value = {
            'valid': True, 'owner': 'user', 'repo': 'repo',
            'branch': None, 'error': None
        }
        mock_instance.download_files.return_value = {
            'success': False, 'downloaded': 0, 'failed': 2,
            'errors': [
                {'path': 'a.py', 'error': 'File not found'},
                {'path': 'b.py', 'error': 'File not found'}
            ]
        }

        response = client.post(
            f'/api/projects/{project_id}/import-git',
            headers={'Authorization': f'Bearer {token}'},
            json={
                'url': 'https://github.com/user/repo',
                'files': ['a.py', 'b.py'],
                'branch': 'main'
            }
        )

        assert response.status_code == 500
        assert 'Failed to download' in response.get_json()['error']

    @patch('routes.projects.GitApiService')
    @patch('routes.projects.ParserManager')
    def test_import_partial_download(self, MockParser, MockGit, client, project_with_auth):
        """Partial downloads should still succeed with analysis"""
        project_id, token, _ = project_with_auth

        mock_git = MockGit.return_value
        mock_git.parse_github_url.return_value = {
            'valid': True, 'owner': 'user', 'repo': 'repo',
            'branch': None, 'error': None
        }
        mock_git.download_files.return_value = {
            'success': False, 'downloaded': 1, 'failed': 1,
            'errors': [{'path': 'missing.py', 'error': 'Not found'}]
        }

        mock_parser = MockParser.return_value
        mock_parser.detect_language_and_framework.return_value = ('python', 'unknown')
        mock_parser.parse_database_schema.return_value = {'tables': []}
        mock_parser.parse_runtime_flow.return_value = {'functions': []}
        mock_parser.parse_api_routes.return_value = {'routes': []}

        response = client.post(
            f'/api/projects/{project_id}/import-git',
            headers={'Authorization': f'Bearer {token}'},
            json={
                'url': 'https://github.com/user/repo',
                'files': ['good.py', 'missing.py'],
                'branch': 'main'
            }
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data['downloaded'] == 1
        assert data['failed'] == 1

    @patch('routes.projects.GitApiService')
    @patch('routes.projects.ParserManager')
    def test_import_updates_project_source_type(self, MockParser, MockGit, client, project_with_auth):
        """Verify project source_type is set to 'git' after import"""
        project_id, token, _ = project_with_auth

        mock_git = MockGit.return_value
        mock_git.parse_github_url.return_value = {
            'valid': True, 'owner': 'user', 'repo': 'repo',
            'branch': None, 'error': None
        }
        mock_git.download_files.return_value = {
            'success': True, 'downloaded': 1, 'failed': 0, 'errors': []
        }

        mock_parser = MockParser.return_value
        mock_parser.detect_language_and_framework.return_value = ('python', 'flask')
        mock_parser.parse_database_schema.return_value = {'tables': []}
        mock_parser.parse_runtime_flow.return_value = {'functions': []}
        mock_parser.parse_api_routes.return_value = {'routes': []}

        # Do the import
        client.post(
            f'/api/projects/{project_id}/import-git',
            headers={'Authorization': f'Bearer {token}'},
            json={
                'url': 'https://github.com/user/repo',
                'files': ['app.py'],
                'branch': 'main'
            }
        )

        # Verify project was updated
        response = client.get(
            f'/api/projects/{project_id}',
            headers={'Authorization': f'Bearer {token}'}
        )
        data = response.get_json()
        assert data['project']['source_type'] == 'git'
        assert data['project']['git_url'] == 'https://github.com/user/repo'


# ---------------------------------------------------------------------------
# 3. Cleanup fixture
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clean_git_test_data():
    """Clean up test data after each test"""
    yield
    from database import get_connection
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM analysis_results WHERE project_id IN (SELECT id FROM projects WHERE name = 'Git Import Test')")
        cur.execute("DELETE FROM projects WHERE name = 'Git Import Test'")
        cur.execute("DELETE FROM users WHERE username = 'gittestuser'")
        conn.commit()
        cur.close()
