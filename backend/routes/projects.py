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

# @projects_bp.before_request
# def log_request():
#     import sys
#     print(f"DEBUG: Request to {request.path}", file=sys.stderr)
#     print(f"DEBUG: Method = {request.method}", file=sys.stderr)
#     print(f"DEBUG: Authorization header = {request.headers.get('Authorization')}", file=sys.stderr)

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
        cur.execute('SELECT * FROM projects WHERE id = %s AND user_id = %s', (project_id, user_id))
        project_data = cur.fetchone()

        if not project_data:
            return jsonify({'error': 'Project not found'}), 404

        # Get latest analysis result
        cur.execute(
            'SELECT * FROM analysis_results WHERE project_id = %s ORDER BY created_at DESC LIMIT 1',
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
        cur.execute('SELECT * FROM projects WHERE id = %s AND user_id = %s', (project_id, user_id))
        project_data = cur.fetchone()

        if not project_data:
            return jsonify({'error': 'Project not found'}), 404

        # Delete project (cascade will delete related records)
        cur.execute('DELETE FROM projects WHERE id = %s', (project_id,))

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

        cur.execute('SELECT * FROM projects WHERE user_id = %s ORDER BY created_at DESC', (user_id,))
        projects_data = cur.fetchall()

    projects = [Project(**p).to_dict() for p in projects_data]

    return jsonify({'projects': projects}), 200

@projects_bp.route('', methods=['POST'])
@jwt_required()
def create_project():
    """Create a new project"""
    import sys
    from flask import request
    try:
        print(f"DEBUG: create_project called", file=sys.stderr)
        user_id = int(get_jwt_identity())
        print(f"DEBUG: user_id = {user_id}", file=sys.stderr)
        data = request.get_json()
        print(f"DEBUG: data = {data}", file=sys.stderr)

        name = data.get('name')
        description = data.get('description', '')

        if not name:
            return jsonify({'error': 'Project name is required'}), 400

        print(f"DEBUG: About to get connection", file=sys.stderr)
        with get_connection() as conn:
            print(f"DEBUG: Got connection", file=sys.stderr)
            cur = conn.cursor()

            # Create project (initially without source)
            print(f"DEBUG: About to insert project", file=sys.stderr)
            cur.execute(
                '''INSERT INTO projects (user_id, name, description, source_type)
                   VALUES (%s, %s, %s, %s) RETURNING id''',
                (user_id, name, description, 'upload')
            )
            result = cur.fetchone()
            project_id = result['id']
            print(f"DEBUG: Inserted project with id={project_id}", file=sys.stderr)

            # Get created project
            print(f"DEBUG: About to fetch project", file=sys.stderr)
            cur.execute('SELECT * FROM projects WHERE id = %s', (project_id,))
            project_data = cur.fetchone()
            print(f"DEBUG: Fetched project_data = {project_data}", file=sys.stderr)

        print(f"DEBUG: About to create Project object", file=sys.stderr)
        project = Project(**project_data)
        print(f"DEBUG: Created Project object", file=sys.stderr)

        return jsonify({'project': project.to_dict()}), 201
    except Exception as e:
        print(f"DEBUG ERROR in create_project: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        raise

@projects_bp.route('/<int:project_id>', methods=['GET'])
@jwt_required()
def get_project(project_id):
    """Get a specific project"""
    user_id = int(get_jwt_identity())  # Convert from string to int

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
    user_id = int(get_jwt_identity())  # Convert from string to int

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
                   VALUES (%s, %s, %s)''',
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

# GET /api/projects/<project_id>/layout
@projects_bp.route('/<int:project_id>/analyze/runtime-flow', methods=['POST'])
@jwt_required()
def analyze_runtime_flow(project_id):
    """Analyze Python code for runtime flow visualization"""
    user_id = int(get_jwt_identity())

    with get_connection() as conn:
        cur = conn.cursor()

        # Verify project ownership
        cur.execute('SELECT * FROM projects WHERE id = %s AND user_id = %s', (project_id, user_id))
        project_data = cur.fetchone()

        if not project_data:
            return jsonify({'error': 'Project not found'}), 404

        # Check if project has files uploaded
        file_path = project_data.get('file_path')
        if not file_path or not os.path.exists(file_path):
            return jsonify({'error': 'Project files not found. Please upload project files first.'}), 400

        try:
            # Parse runtime flow
            manager = ParserManager()
            flow_data = manager.parse_runtime_flow(file_path)

            # Save analysis result
            cur.execute(
                '''INSERT INTO analysis_results (project_id, analysis_type, result_data)
                   VALUES (%s, %s, %s)''',
                (project_id, 'runtime_flow', json.dumps(flow_data))
            )

            return jsonify({
                'message': 'Runtime flow analysis completed',
                'flow': flow_data
            }), 200

        except UnsupportedFrameworkError as e:
            return jsonify({'error': str(e)}), 400
        except Exception as e:
            conn.rollback()
            return jsonify({'error': f'Runtime flow analysis failed: {str(e)}'}), 500

@projects_bp.route('/<int:project_id>/runtime-flow', methods=['GET'])
@jwt_required()
def get_runtime_flow(project_id):
    """Get cached runtime flow analysis results"""
    user_id = int(get_jwt_identity())

    with get_connection() as conn:
        cur = conn.cursor()

        # Verify project ownership
        cur.execute('SELECT * FROM projects WHERE id = %s AND user_id = %s', (project_id, user_id))
        project_data = cur.fetchone()

        if not project_data:
            return jsonify({'error': 'Project not found'}), 404

        # Get latest runtime_flow analysis result
        cur.execute(
            '''SELECT * FROM analysis_results
               WHERE project_id = %s AND analysis_type = %s
               ORDER BY created_at DESC LIMIT 1''',
            (project_id, 'runtime_flow')
        )
        analysis_data = cur.fetchone()

    if not analysis_data:
        return jsonify({'error': 'No runtime flow analysis found. Please analyze the project first.'}), 404

    return jsonify({
        'analysis_id': analysis_data['id'],
        'flow': json.loads(analysis_data['result_data']),
        'created_at': analysis_data['created_at']
    }), 200

@projects_bp.route('/<int:project_id>/layout', methods=['GET'])
@jwt_required()
def get_workspace_layout(project_id):
    """Get saved workspace layout for a project"""
    user_id = int(get_jwt_identity())

    with get_connection() as conn:
        cur = conn.cursor()

        # Verify project ownership
        cur.execute('SELECT * FROM projects WHERE id = %s AND user_id = %s',
                   (project_id, user_id))
        if not cur.fetchone():
            return jsonify({'error': 'Project not found'}), 404

        # Get layout for database_schema analysis type
        cur.execute(
            '''SELECT * FROM workspace_layouts
               WHERE project_id = %s AND analysis_type = %s
               ORDER BY updated_at DESC LIMIT 1''',
            (project_id, 'database_schema')
        )
        layout_data = cur.fetchone()

    if not layout_data:
        return jsonify({'layout': None}), 200

    return jsonify({
        'layout': {
            'id': layout_data['id'],
            'layout_data': json.loads(layout_data['layout_data']),
            'updated_at': layout_data['updated_at']
        }
    }), 200


# POST /api/projects/<project_id>/layout
@projects_bp.route('/<int:project_id>/layout', methods=['POST'])
@jwt_required()
def save_workspace_layout(project_id):
    """Save or update workspace layout for a project"""
    user_id = int(get_jwt_identity())
    data = request.get_json()

    layout_data = data.get('layout_data')
    if not layout_data:
        return jsonify({'error': 'layout_data is required'}), 400

    with get_connection() as conn:
        cur = conn.cursor()

        # Verify project ownership
        cur.execute('SELECT * FROM projects WHERE id = %s AND user_id = %s',
                   (project_id, user_id))
        if not cur.fetchone():
            return jsonify({'error': 'Project not found'}), 404

        analysis_type = 'database_schema'

        # Check if layout exists
        cur.execute(
            'SELECT id FROM workspace_layouts WHERE project_id = %s AND analysis_type = %s',
            (project_id, analysis_type)
        )
        existing = cur.fetchone()

        if existing:
            # Update
            cur.execute(
                '''UPDATE workspace_layouts
                   SET layout_data = %s, updated_at = CURRENT_TIMESTAMP
                   WHERE id = %s''',
                (json.dumps(layout_data), existing['id'])
            )
            layout_id = existing['id']
        else:
            # Create
            cur.execute(
                '''INSERT INTO workspace_layouts (project_id, analysis_type, layout_data)
                   VALUES (%s, %s, %s) RETURNING id''',
                (project_id, analysis_type, json.dumps(layout_data))
            )
            result = cur.fetchone()
            layout_id = result['id']

    return jsonify({
        'message': 'Layout saved successfully',
        'layout_id': layout_id
    }), 200
