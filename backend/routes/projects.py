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

@projects_bp.route('', methods=['GET'])
@jwt_required()
def list_projects():
    """List all projects for current user"""
    user_id = get_jwt_identity()

    with get_connection() as conn:
        cur = conn.cursor()

        cur.execute('SELECT * FROM projects WHERE user_id = %s ORDER BY created_at DESC', (user_id,))
        projects_data = cur.fetchall()

    projects = [Project(**p).to_dict() for p in projects_data]

    return jsonify({'projects': projects}), 200

@projects_bp.route('', methods=['POST'])
@jwt_required()
def create_project():
    """Create a new project"""
    user_id = get_jwt_identity()
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
               VALUES (%s, %s, %s, %s)
               RETURNING *''',
            (user_id, name, description, 'upload')
        )
        project_data = cur.fetchone()

    project = Project(**project_data)

    return jsonify({'project': project.to_dict()}), 201

@projects_bp.route('/<int:project_id>', methods=['GET'])
@jwt_required()
def get_project(project_id):
    """Get a specific project"""
    user_id = get_jwt_identity()

    with get_connection() as conn:
        cur = conn.cursor()

        cur.execute('SELECT * FROM projects WHERE id = %s AND user_id = %s', (project_id, user_id))
        project_data = cur.fetchone()

    if not project_data:
        return jsonify({'error': 'Project not found'}), 404

    project = Project(**project_data)

    return jsonify({'project': project.to_dict()}), 200

@projects_bp.route('/<int:project_id>/upload', methods=['POST'])
@jwt_required()
def upload_project_files(project_id):
    """Upload files for a project and analyze"""
    user_id = get_jwt_identity()

    with get_connection() as conn:
        cur = conn.cursor()

        # Verify project ownership
        cur.execute('SELECT * FROM projects WHERE id = %s AND user_id = %s', (project_id, user_id))
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
        cur.execute('UPDATE projects SET file_path = %s WHERE id = %s', (upload_dir, project_id))

        # Detect and analyze
        try:
            manager = ParserManager()
            language, framework = manager.detect_language_and_framework(upload_dir)

            # Update project with detected info
            cur.execute(
                'UPDATE projects SET language = %s, framework = %s WHERE id = %s',
                (language, framework, project_id)
            )

            # Parse schema
            schema = manager.parse_database_schema(upload_dir, language, framework)

            # Save analysis result
            cur.execute(
                '''INSERT INTO analysis_results (project_id, analysis_type, result_data)
                   VALUES (%s, %s, %s) RETURNING id''',
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
