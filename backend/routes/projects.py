from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from database import get_connection
from models import Project
import os
import json
from werkzeug.utils import secure_filename
from config import Config
from parsers.parser_manager import ParserManager, UnsupportedFrameworkError

projects_bp = Blueprint('projects', __name__)

@projects_bp.before_request
def log_request():
    import sys
    print(f"DEBUG: Request to {request.path}", file=sys.stderr, flush=True)
    print(f"DEBUG: Method = {request.method}", file=sys.stderr, flush=True)
    print(f"DEBUG: Authorization header = {request.headers.get('Authorization')}", file=sys.stderr, flush=True)

@projects_bp.route('/test', methods=['GET'])
def test_endpoint():
    """Test endpoint without JWT"""
    return jsonify({'message': 'Test successful', 'headers': dict(request.headers)}), 200

@projects_bp.route('/<int:project_id>/analysis', methods=['GET'])
@jwt_required()
def get_analysis(project_id):
    """Get analysis results for a project"""
    user_id = int(get_jwt_identity())

    with get_connection() as conn:
        cur = conn.cursor()

        # Verify project ownership
        cur.execute('SELECT * FROM projects WHERE id = ? AND user_id = ?', (project_id, user_id))
        project_data = cur.fetchone()

        if not project_data:
            return jsonify({'error': 'Project not found'}), 404

        # Get latest analysis result
        cur.execute(
            'SELECT * FROM analysis_results WHERE project_id = ? ORDER BY created_at DESC LIMIT 1',
            (project_id,)
        )
        analysis_data = cur.fetchone()

    if not analysis_data:
        return jsonify({'error': 'No analysis found'}), 404

    return jsonify({
        'analysis_id': analysis_data['id'],
        'analysis_type': analysis_data['analysis_type'],
        'schema': json.loads(analysis_data['result_data']),
        'created_at': analysis_data['created_at']
    }), 200

@projects_bp.route('/<int:project_id>', methods=['DELETE'])
@jwt_required()
def delete_project(project_id):
    """Delete a project"""
    user_id = int(get_jwt_identity())

    with get_connection() as conn:
        cur = conn.cursor()

        # Verify project ownership
        cur.execute('SELECT * FROM projects WHERE id = ? AND user_id = ?', (project_id, user_id))
        project_data = cur.fetchone()

        if not project_data:
            return jsonify({'error': 'Project not found'}), 404

        # Delete project (cascade will delete related records)
        cur.execute('DELETE FROM projects WHERE id = ?', (project_id,))

    return jsonify({'message': 'Project deleted successfully'}), 200

@projects_bp.route('', methods=['GET'])
@jwt_required()
def list_projects():
    """List all projects for current user"""
    from flask import request
    print(f"DEBUG: Headers = {dict(request.headers)}")
    print(f"DEBUG: Authorization = {request.headers.get('Authorization')}")
    user_id = int(get_jwt_identity())  # Convert from string to int

    with get_connection() as conn:
        cur = conn.cursor()

        cur.execute('SELECT * FROM projects WHERE user_id = ? ORDER BY created_at DESC', (user_id,))
        projects_data = cur.fetchall()

    projects = [Project(**p).to_dict() for p in projects_data]

    return jsonify({'projects': projects}), 200

@projects_bp.route('', methods=['POST'])
@jwt_required()
def create_project():
    """Create a new project"""
    from flask import request
    print(f"DEBUG: Headers = {dict(request.headers)}")
    print(f"DEBUG: Authorization = {request.headers.get('Authorization')}")
    user_id = int(get_jwt_identity())  # Convert from string to int
    data = request.get_json()

    name = data.get('name')
    description = data.get('description', '')

    if not name:
        return jsonify({'error': 'Project name is required'}), 400

    with get_connection() as conn:
        cur = conn.cursor()

        # Create project (initially without source)
        cur.execute(
            '''INSERT INTO projects (user_id, name, description, source_type)
               VALUES (?, ?, ?, ?)''',
            (user_id, name, description, 'upload')
        )
        project_id = cur.lastrowid

        # Get created project
        cur.execute('SELECT * FROM projects WHERE id = ?', (project_id,))
        project_data = cur.fetchone()

    project = Project(**project_data)

    return jsonify({'project': project.to_dict()}), 201

@projects_bp.route('/<int:project_id>', methods=['GET'])
@jwt_required()
def get_project(project_id):
    """Get a specific project"""
    user_id = int(get_jwt_identity())  # Convert from string to int

    with get_connection() as conn:
        cur = conn.cursor()

        cur.execute('SELECT * FROM projects WHERE id = ? AND user_id = ?', (project_id, user_id))
        project_data = cur.fetchone()

    if not project_data:
        return jsonify({'error': 'Project not found'}), 404

    project = Project(**project_data)

    return jsonify({'project': project.to_dict()}), 200

@projects_bp.route('/<int:project_id>/upload', methods=['POST'])
@jwt_required()
def upload_project_files(project_id):
    """Upload files for a project and analyze"""
    user_id = int(get_jwt_identity())  # Convert from string to int

    with get_connection() as conn:
        cur = conn.cursor()

        # Verify project ownership
        cur.execute('SELECT * FROM projects WHERE id = ? AND user_id = ?', (project_id, user_id))
        project_data = cur.fetchone()

        if not project_data:
            return jsonify({'error': 'Project not found'}), 404

        # Create upload directory
        upload_dir = os.path.join(Config.STORAGE_PATH, 'uploads', str(user_id), str(project_id))
        os.makedirs(upload_dir, exist_ok=True)

        # Save uploaded files
        files = request.files.getlist('files')
        for file in files:
            if file.filename:
                filename = secure_filename(file.filename)
                file.save(os.path.join(upload_dir, filename))

        # Update project file_path
        cur.execute('UPDATE projects SET file_path = ? WHERE id = ?', (upload_dir, project_id))

        # Detect and analyze
        try:
            manager = ParserManager()
            language, framework = manager.detect_language_and_framework(upload_dir)

            # Update project with detected info
            cur.execute(
                'UPDATE projects SET language = ?, framework = ? WHERE id = ?',
                (language, framework, project_id)
            )

            # Parse schema
            schema = manager.parse_database_schema(upload_dir, language, framework)

            # Save analysis result
            cur.execute(
                '''INSERT INTO analysis_results (project_id, analysis_type, result_data)
                   VALUES (?, ?, ?)''',
                (project_id, 'database_schema', json.dumps(schema))
            )

            return jsonify({
                'message': 'Files uploaded and analyzed',
                'language': language,
                'framework': framework,
                'schema': schema
            }), 200

        except UnsupportedFrameworkError as e:
            return jsonify({'error': str(e)}), 400
        except Exception as e:
            conn.rollback()
            return jsonify({'error': f'Analysis failed: {str(e)}'}), 500
