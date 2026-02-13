"""Tests for Runtime Flow API endpoints"""

import pytest
import json
import os
import shutil
from pathlib import Path
from flask_jwt_extended import create_access_token

@pytest.fixture
def auth_token(client):
    """Create auth token for test user"""
    from db import get_connection
    from models import User
    from app import app

    with app.app_context():
        with get_connection() as conn:
            cur = conn.cursor()

            password_hash = User.hash_password('password123')
            cur.execute(
                'INSERT INTO users (username, email, password_hash) VALUES (%s, %s, %s) RETURNING id',
                ('testuser', 'test@example.com', password_hash)
            )
            user_id = cur.fetchone()['id']

        token = create_access_token(identity=str(user_id))

    return token, user_id

@pytest.fixture
def test_project(client, auth_token):
    """Create a test project with uploaded files"""
    token, user_id = auth_token

    # Create project
    response = client.post('/api/projects',
        headers={'Authorization': f'Bearer {token}'},
        json={
            'name': 'Runtime Flow Test',
            'description': 'Test project for runtime flow analysis'
        })

    project_id = response.get_json()['project']['id']

    # Set up test files (copy test_project to upload directory)
    source = Path(__file__).parent.parent / 'test_project'
    dest = Path(__file__).parent.parent / 'storage' / 'uploads' / str(user_id) / str(project_id)
    dest.mkdir(parents=True, exist_ok=True)

    # Copy Python files
    for py_file in source.glob('*.py'):
        shutil.copy(py_file, dest)

    # Update project file_path
    from db import get_connection
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute('UPDATE projects SET file_path = %s WHERE id = %s', (str(dest), project_id))

    return project_id, token

def test_analyze_runtime_flow(client, test_project):
    """Test POST /api/projects/<id>/analyze/runtime-flow"""
    project_id, token = test_project

    response = client.post(
        f'/api/projects/{project_id}/analyze/runtime-flow',
        headers={'Authorization': f'Bearer {token}'}
    )

    assert response.status_code == 200
    data = response.get_json()

    # Check response structure
    assert 'message' in data
    assert 'flow' in data

    flow_data = data['flow']

    # Verify flow data structure
    assert flow_data['analysis_type'] == 'runtime_flow'
    assert 'version' in flow_data
    assert 'modules' in flow_data
    assert 'functions' in flow_data
    assert 'calls' in flow_data
    assert 'control_flows' in flow_data
    assert 'entry_points' in flow_data
    assert 'statistics' in flow_data

    # Verify statistics
    stats = flow_data['statistics']
    assert stats['total_functions'] > 0
    assert stats['total_calls'] >= 0
    assert stats['total_control_flows'] >= 0

def test_get_runtime_flow(client, test_project):
    """Test GET /api/projects/<id>/runtime-flow"""
    project_id, token = test_project

    # First analyze
    client.post(
        f'/api/projects/{project_id}/analyze/runtime-flow',
        headers={'Authorization': f'Bearer {token}'}
    )

    # Then retrieve
    response = client.get(
        f'/api/projects/{project_id}/runtime-flow',
        headers={'Authorization': f'Bearer {token}'}
    )

    assert response.status_code == 200
    data = response.get_json()

    # Check response structure
    assert 'analysis_id' in data
    assert 'flow' in data
    assert 'created_at' in data

    # Verify flow data
    flow_data = data['flow']
    assert flow_data['analysis_type'] == 'runtime_flow'
    assert 'functions' in flow_data
    assert 'calls' in flow_data

def test_get_runtime_flow_not_analyzed(client, auth_token):
    """Test GET when project hasn't been analyzed yet"""
    token, user_id = auth_token

    # Create project without analysis
    response = client.post('/api/projects',
        headers={'Authorization': f'Bearer {token}'},
        json={'name': 'Unanalyzed Project', 'description': 'Test'})

    project_id = response.get_json()['project']['id']

    # Try to get runtime flow
    response = client.get(
        f'/api/projects/{project_id}/runtime-flow',
        headers={'Authorization': f'Bearer {token}'}
    )

    assert response.status_code == 404
    data = response.get_json()
    assert 'error' in data

def test_analyze_runtime_flow_no_files(client, auth_token):
    """Test analysis when no files are uploaded"""
    token, user_id = auth_token

    # Create project without uploading files
    response = client.post('/api/projects',
        headers={'Authorization': f'Bearer {token}'},
        json={'name': 'Empty Project', 'description': 'Test'})

    project_id = response.get_json()['project']['id']

    # Try to analyze
    response = client.post(
        f'/api/projects/{project_id}/analyze/runtime-flow',
        headers={'Authorization': f'Bearer {token}'}
    )

    assert response.status_code == 400
    data = response.get_json()
    assert 'error' in data

def test_analyze_runtime_flow_unauthorized(client, test_project):
    """Test analysis without authentication"""
    project_id, _ = test_project

    response = client.post(f'/api/projects/{project_id}/analyze/runtime-flow')

    # Flask-JWT-Extended returns 422 for missing Authorization header
    assert response.status_code == 422

def test_get_runtime_flow_unauthorized(client, test_project):
    """Test retrieval without authentication"""
    project_id, _ = test_project

    response = client.get(f'/api/projects/{project_id}/runtime-flow')

    # Flask-JWT-Extended returns 422 for missing Authorization header
    assert response.status_code == 422

def test_runtime_flow_data_persistence(client, test_project):
    """Test that runtime flow data is persisted correctly"""
    project_id, token = test_project

    # Analyze
    analyze_response = client.post(
        f'/api/projects/{project_id}/analyze/runtime-flow',
        headers={'Authorization': f'Bearer {token}'}
    )

    original_flow = analyze_response.get_json()['flow']

    # Retrieve multiple times
    for _ in range(3):
        get_response = client.get(
            f'/api/projects/{project_id}/runtime-flow',
            headers={'Authorization': f'Bearer {token}'}
        )

        cached_flow = get_response.get_json()['flow']

        # Verify data consistency
        assert cached_flow['statistics'] == original_flow['statistics']
        assert len(cached_flow['functions']) == len(original_flow['functions'])
        assert len(cached_flow['calls']) == len(original_flow['calls'])

def test_multiple_analyses(client, test_project):
    """Test running analysis multiple times"""
    project_id, token = test_project

    # Run analysis twice
    response1 = client.post(
        f'/api/projects/{project_id}/analyze/runtime-flow',
        headers={'Authorization': f'Bearer {token}'}
    )

    response2 = client.post(
        f'/api/projects/{project_id}/analyze/runtime-flow',
        headers={'Authorization': f'Bearer {token}'}
    )

    # Both should succeed
    assert response1.status_code == 200
    assert response2.status_code == 200

    # Latest analysis should be retrievable
    response = client.get(
        f'/api/projects/{project_id}/runtime-flow',
        headers={'Authorization': f'Bearer {token}'}
    )

    assert response.status_code == 200
    # Should get the most recent analysis
