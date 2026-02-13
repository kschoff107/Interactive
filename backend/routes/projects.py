from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from db import get_connection
from models import Project
import os
import json
from werkzeug.utils import secure_filename
from config import Config
from parsers.parser_manager import ParserManager, UnsupportedFrameworkError
from services.git_api_service import GitApiService

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
    user_id = int(get_jwt_identity())
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
               VALUES (%s, %s, %s, %s) RETURNING id''',
            (user_id, name, description, 'upload')
        )
        result = cur.fetchone()
        project_id = result['id']

        # Get created project
        cur.execute('SELECT * FROM projects WHERE id = %s', (project_id,))
        project_data = cur.fetchone()

    # Debug logging
    print("DEBUG: project_data keys:", project_data.keys() if hasattr(project_data, 'keys') else 'Not a dict')
    print("DEBUG: project_data:", project_data)

    project = Project(**project_data)

    return jsonify({'project': project.to_dict()}), 201

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

@projects_bp.route('/<int:project_id>/status', methods=['GET'])
@jwt_required()
def get_project_status(project_id):
    """Get project file upload status and analysis availability"""
    user_id = int(get_jwt_identity())

    with get_connection() as conn:
        cur = conn.cursor()

        # Verify project ownership
        cur.execute('SELECT * FROM projects WHERE id = %s AND user_id = %s', (project_id, user_id))
        project_data = cur.fetchone()

        if not project_data:
            return jsonify({'error': 'Project not found'}), 404

        # Get file counts by analysis type
        file_path = project_data.get('file_path')
        file_count = 0
        if file_path and os.path.exists(file_path):
            file_count = len([f for f in os.listdir(file_path) if os.path.isfile(os.path.join(file_path, f))])

        # Convert last_upload_date to string if it exists
        last_upload = project_data.get('last_upload_date')
        last_upload_str = last_upload.isoformat() if last_upload else None

        return jsonify({
            'project_id': project_id,
            'has_database_schema': project_data.get('has_database_schema', False),
            'has_runtime_flow': project_data.get('has_runtime_flow', False),
            'has_api_routes': project_data.get('has_api_routes', False),
            'last_upload_date': last_upload_str,
            'file_count': file_count,
            'available_views': [
                view for view, available in [
                    ('database_schema', project_data.get('has_database_schema', False)),
                    ('runtime_flow', project_data.get('has_runtime_flow', False)),
                    ('api_routes', project_data.get('has_api_routes', False))
                ] if available
            ],
            'missing_views': [
                view for view, available in [
                    ('database_schema', project_data.get('has_database_schema', False)),
                    ('runtime_flow', project_data.get('has_runtime_flow', False)),
                    ('api_routes', project_data.get('has_api_routes', False))
                ] if not available
            ]
        }), 200

@projects_bp.route('/<int:project_id>/upload', methods=['POST'])
@jwt_required()
def upload_project_files(project_id):
    """Upload files for a project and analyze"""
    from datetime import datetime
    user_id = int(get_jwt_identity())  # Convert from string to int

    # Get optional file_type parameter from form data
    file_type = request.form.get('file_type', 'auto')  # 'database_schema', 'runtime_flow', or 'auto'

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

        # Get list of existing files for duplicate checking
        existing_files = set(os.listdir(upload_dir)) if os.path.exists(upload_dir) else set()

        # Save uploaded files and track results
        files = request.files.getlist('files')
        upload_results = []

        for file in files:
            if file.filename:
                filename = secure_filename(file.filename)

                # Check for duplicates
                if filename in existing_files:
                    upload_results.append({
                        'filename': filename,
                        'status': 'skipped',
                        'reason': 'File already exists'
                    })
                    continue

                # Save file
                file_path = os.path.join(upload_dir, filename)
                file.save(file_path)
                upload_results.append({
                    'filename': filename,
                    'status': 'success',
                    'file_type': file_type
                })

        # Update project file_path if not set
        if not project_data.get('file_path'):
            cur.execute('UPDATE projects SET file_path = %s WHERE id = %s', (upload_dir, project_id))

        # Detect and analyze based on file_type
        try:
            manager = ParserManager()
            language, framework = manager.detect_language_and_framework(upload_dir)

            # Update project with detected info
            cur.execute(
                'UPDATE projects SET language = %s, framework = %s, last_upload_date = %s WHERE id = %s',
                (language, framework, datetime.now(), project_id)
            )

            # Determine what analysis to run
            response_data = {
                'message': 'Files uploaded and analyzed',
                'uploads': upload_results,
                'language': language,
                'framework': framework
            }

            # Run database schema analysis
            if file_type in ['database_schema', 'auto']:
                try:
                    schema = manager.parse_database_schema(upload_dir, language, framework)

                    # Only save and mark as having schema if actual tables were found (excluding placeholders)
                    tables = schema.get('tables', []) if schema else []
                    # Filter out placeholder tables like Example_Table
                    real_tables = [t for t in tables if t.get('name') not in ['Example_Table', 'example_table']]
                    has_tables = len(real_tables) > 0

                    if has_tables:
                        # Save or update analysis result
                        cur.execute(
                            '''INSERT INTO analysis_results (project_id, analysis_type, result_data)
                               VALUES (%s, %s, %s)''',
                            (project_id, 'database_schema', json.dumps(schema))
                        )

                        # Update project status
                        cur.execute(
                            'UPDATE projects SET has_database_schema = %s WHERE id = %s',
                            (True, project_id)
                        )

                        response_data['schema'] = schema
                    else:
                        print(f"Database schema analysis returned no tables")
                except Exception as schema_error:
                    print(f"Database schema analysis failed: {schema_error}")
                    # Don't fail the entire upload if schema analysis fails

            # Run runtime flow analysis
            if file_type in ['runtime_flow', 'auto']:
                try:
                    flow_data = manager.parse_runtime_flow(upload_dir)

                    # Save or update analysis result
                    cur.execute(
                        '''INSERT INTO analysis_results (project_id, analysis_type, result_data)
                           VALUES (%s, %s, %s)''',
                        (project_id, 'runtime_flow', json.dumps(flow_data))
                    )

                    # Update project status
                    cur.execute(
                        'UPDATE projects SET has_runtime_flow = %s WHERE id = %s',
                        (True, project_id)
                    )

                    response_data['flow'] = flow_data
                except Exception as flow_error:
                    print(f"Runtime flow analysis failed: {flow_error}")
                    # Don't fail the entire upload if flow analysis fails

            # Get updated project status
            cur.execute('SELECT has_database_schema, has_runtime_flow FROM projects WHERE id = %s', (project_id,))
            status = cur.fetchone()
            response_data['project_status'] = {
                'has_database_schema': status['has_database_schema'],
                'has_runtime_flow': status['has_runtime_flow']
            }

            return jsonify(response_data), 200

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

@projects_bp.route('/<int:project_id>/analyze/api-routes', methods=['POST'])
@jwt_required()
def analyze_api_routes(project_id):
    """Analyze Flask/FastAPI routes in project files"""
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
            # Parse API routes
            manager = ParserManager()
            routes_data = manager.parse_api_routes(file_path)

            # Save analysis result
            cur.execute(
                '''INSERT INTO analysis_results (project_id, analysis_type, result_data)
                   VALUES (%s, %s, %s)''',
                (project_id, 'api_routes', json.dumps(routes_data))
            )

            # Update project status
            cur.execute(
                'UPDATE projects SET has_api_routes = %s WHERE id = %s',
                (True, project_id)
            )

            return jsonify({
                'message': 'API routes analysis completed',
                'routes': routes_data
            }), 200

        except UnsupportedFrameworkError as e:
            return jsonify({'error': str(e)}), 400
        except Exception as e:
            conn.rollback()
            return jsonify({'error': f'API routes analysis failed: {str(e)}'}), 500


@projects_bp.route('/<int:project_id>/api-routes', methods=['GET'])
@jwt_required()
def get_api_routes(project_id):
    """Get cached API routes analysis results"""
    user_id = int(get_jwt_identity())

    with get_connection() as conn:
        cur = conn.cursor()

        # Verify project ownership
        cur.execute('SELECT * FROM projects WHERE id = %s AND user_id = %s', (project_id, user_id))
        project_data = cur.fetchone()

        if not project_data:
            return jsonify({'error': 'Project not found'}), 404

        # Get latest api_routes analysis result
        cur.execute(
            '''SELECT * FROM analysis_results
               WHERE project_id = %s AND analysis_type = %s
               ORDER BY created_at DESC LIMIT 1''',
            (project_id, 'api_routes')
        )
        analysis_data = cur.fetchone()

    if not analysis_data:
        return jsonify({'error': 'No API routes analysis found. Please analyze the project first.'}), 404

    return jsonify({
        'analysis_id': analysis_data['id'],
        'routes': json.loads(analysis_data['result_data']),
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


# ---------------------------------------------------------------------------
# Project Files Endpoint
# ---------------------------------------------------------------------------

@projects_bp.route('/<int:project_id>/files', methods=['GET'])
@jwt_required()
def get_project_files(project_id):
    """List all files stored on disk for a project.

    Returns the same shape as the git tree endpoint so the frontend
    buildFileTree() logic works for both:
        {files: [{path, type, size}], total_count: int}
    """
    user_id = int(get_jwt_identity())

    with get_connection() as conn:
        cur = conn.cursor()

        # Verify project ownership
        cur.execute('SELECT * FROM projects WHERE id = %s AND user_id = %s',
                    (project_id, user_id))
        project_data = cur.fetchone()

        if not project_data:
            return jsonify({'error': 'Project not found'}), 404

    file_path = project_data.get('file_path')

    # No files on disk yet
    if not file_path or not os.path.exists(file_path):
        return jsonify({'files': [], 'total_count': 0}), 200

    files = []
    for dirpath, dirnames, filenames in os.walk(file_path):
        # Build relative path and normalise separators for Windows
        rel_dir = os.path.relpath(dirpath, file_path)
        if rel_dir == '.':
            rel_dir = ''

        for fname in filenames:
            full = os.path.join(dirpath, fname)
            rel = os.path.join(rel_dir, fname) if rel_dir else fname
            # Normalise Windows backslashes to forward slashes
            rel = rel.replace('\\', '/')

            try:
                size = os.path.getsize(full)
            except OSError:
                size = 0

            files.append({
                'path': rel,
                'type': 'file',
                'size': size
            })

    # Sort alphabetically for consistent output
    files.sort(key=lambda f: f['path'])

    return jsonify({
        'files': files,
        'total_count': len(files)
    }), 200


# ---------------------------------------------------------------------------
# Git Import Endpoints
# ---------------------------------------------------------------------------

@projects_bp.route('/git/tree', methods=['GET'])
@jwt_required()
def get_git_tree():
    """Fetch file tree from a public GitHub repository"""
    url = request.args.get('url')
    if not url:
        return jsonify({'error': 'URL parameter is required'}), 400

    git_service = GitApiService()

    # Parse and validate URL
    parsed = git_service.parse_github_url(url)
    if not parsed['valid']:
        return jsonify({'error': parsed['error']}), 400

    # Use branch from URL if provided, otherwise auto-detect
    branch = parsed.get('branch')

    # Get file tree
    result = git_service.get_repo_tree(parsed['owner'], parsed['repo'], branch)
    if not result['success']:
        return jsonify({'error': result['error']}), 400

    return jsonify({
        'owner': parsed['owner'],
        'repo': parsed['repo'],
        'branch': result['branch'],
        'files': result['files'],
        'truncated': result['truncated']
    }), 200


@projects_bp.route('/<int:project_id>/import-git', methods=['POST'])
@jwt_required()
def import_from_git(project_id):
    """Import selected files from a GitHub repository into a project"""
    from datetime import datetime
    user_id = int(get_jwt_identity())
    data = request.get_json()

    url = data.get('url')
    files = data.get('files', [])
    branch = data.get('branch', 'main')

    if not url:
        return jsonify({'error': 'Repository URL is required'}), 400

    if not files:
        return jsonify({'error': 'At least one file must be selected'}), 400

    if len(files) > 50:
        return jsonify({'error': 'Maximum 50 files can be imported at once'}), 400

    git_service = GitApiService()

    # Parse and validate URL
    parsed = git_service.parse_github_url(url)
    if not parsed['valid']:
        return jsonify({'error': parsed['error']}), 400

    with get_connection() as conn:
        cur = conn.cursor()

        # Verify project ownership
        cur.execute('SELECT * FROM projects WHERE id = %s AND user_id = %s',
                    (project_id, user_id))
        project_data = cur.fetchone()

        if not project_data:
            return jsonify({'error': 'Project not found'}), 404

        # Download files to project storage
        upload_dir = os.path.join(Config.STORAGE_PATH, 'uploads',
                                  str(user_id), str(project_id))

        result = git_service.download_files(
            parsed['owner'], parsed['repo'], files, upload_dir, branch
        )

        if result['downloaded'] == 0:
            return jsonify({
                'error': 'Failed to download any files',
                'details': result['errors']
            }), 500

        # Update project metadata
        cur.execute('''
            UPDATE projects
            SET file_path = %s, git_url = %s, source_type = %s,
                git_branch = %s, last_upload_date = %s
            WHERE id = %s
        ''', (upload_dir, url, 'git', branch, datetime.now(), project_id))

        # Run analysis (same flow as file upload)
        response_data = {
            'message': 'Files imported from GitHub',
            'downloaded': result['downloaded'],
            'failed': result['failed'],
            'errors': result['errors']
        }

        try:
            manager = ParserManager()
            language, framework = manager.detect_language_and_framework(upload_dir)

            cur.execute(
                'UPDATE projects SET language = %s, framework = %s WHERE id = %s',
                (language, framework, project_id)
            )

            response_data['language'] = language
            response_data['framework'] = framework

            # Run database schema analysis
            try:
                schema = manager.parse_database_schema(upload_dir, language, framework)

                tables = schema.get('tables', []) if schema else []
                real_tables = [t for t in tables if t.get('name') not in ['Example_Table', 'example_table']]

                if len(real_tables) > 0:
                    cur.execute(
                        '''INSERT INTO analysis_results (project_id, analysis_type, result_data)
                           VALUES (%s, %s, %s)''',
                        (project_id, 'database_schema', json.dumps(schema))
                    )
                    cur.execute(
                        'UPDATE projects SET has_database_schema = %s WHERE id = %s',
                        (True, project_id)
                    )
                    response_data['schema'] = schema
            except Exception as schema_error:
                print(f"Database schema analysis failed: {schema_error}")

            # Run runtime flow analysis
            try:
                flow_data = manager.parse_runtime_flow(upload_dir)

                cur.execute(
                    '''INSERT INTO analysis_results (project_id, analysis_type, result_data)
                       VALUES (%s, %s, %s)''',
                    (project_id, 'runtime_flow', json.dumps(flow_data))
                )
                cur.execute(
                    'UPDATE projects SET has_runtime_flow = %s WHERE id = %s',
                    (True, project_id)
                )
                response_data['flow'] = flow_data
            except Exception as flow_error:
                print(f"Runtime flow analysis failed: {flow_error}")

            # Run API routes analysis
            try:
                routes_data = manager.parse_api_routes(upload_dir)

                cur.execute(
                    '''INSERT INTO analysis_results (project_id, analysis_type, result_data)
                       VALUES (%s, %s, %s)''',
                    (project_id, 'api_routes', json.dumps(routes_data))
                )
                cur.execute(
                    'UPDATE projects SET has_api_routes = %s WHERE id = %s',
                    (True, project_id)
                )
                response_data['routes'] = routes_data
            except Exception as routes_error:
                print(f"API routes analysis failed: {routes_error}")

            # Get updated project status
            cur.execute(
                'SELECT has_database_schema, has_runtime_flow, has_api_routes FROM projects WHERE id = %s',
                (project_id,)
            )
            status = cur.fetchone()
            response_data['project_status'] = {
                'has_database_schema': status['has_database_schema'],
                'has_runtime_flow': status['has_runtime_flow'],
                'has_api_routes': status['has_api_routes']
            }

        except UnsupportedFrameworkError as e:
            response_data['analysis_error'] = str(e)
        except Exception as e:
            print(f"Analysis failed during git import: {e}")
            response_data['analysis_error'] = f'Analysis failed: {str(e)}'

        return jsonify(response_data), 200
