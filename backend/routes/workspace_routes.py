from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from database import get_connection
import json
import os
from config import Config
from parsers.parser_manager import ParserManager, UnsupportedFrameworkError

workspaces_bp = Blueprint('workspaces', __name__)


def get_or_create_default_workspace(cur, project_id, analysis_type):
    """Get the first workspace for a project/analysis_type, creating 'Default' if none exist.
    Also backfills orphaned rows (workspace_id IS NULL) to the default workspace."""
    cur.execute(
        '''SELECT id FROM workspaces
           WHERE project_id = %s AND analysis_type = %s
           ORDER BY sort_order ASC LIMIT 1''',
        (project_id, analysis_type)
    )
    row = cur.fetchone()
    if row:
        return row['id']

    # Create default workspace
    cur.execute(
        '''INSERT INTO workspaces (project_id, analysis_type, name, sort_order)
           VALUES (%s, %s, %s, 0) RETURNING id''',
        (project_id, analysis_type, 'Default')
    )
    ws_id = cur.fetchone()['id']

    # Backfill orphaned rows
    for table in ('analysis_results', 'workspace_layouts', 'workspace_notes'):
        cur.execute(
            f'''UPDATE {table} SET workspace_id = %s
                WHERE project_id = %s AND analysis_type = %s AND workspace_id IS NULL''',
            (ws_id, project_id, analysis_type)
        )

    return ws_id


def verify_project_ownership(cur, project_id, user_id):
    """Verify project exists and belongs to user. Returns project row or None."""
    cur.execute('SELECT * FROM projects WHERE id = %s AND user_id = %s', (project_id, user_id))
    return cur.fetchone()


# ---------------------------------------------------------------------------
# Workspace CRUD
# ---------------------------------------------------------------------------

@workspaces_bp.route('/<int:project_id>/workspaces', methods=['GET'])
@jwt_required()
def list_workspaces(project_id):
    """List all workspaces for a project, grouped by analysis_type.
    Auto-creates default workspaces for existing data that has no workspace."""
    user_id = int(get_jwt_identity())

    with get_connection() as conn:
        cur = conn.cursor()

        project = verify_project_ownership(cur, project_id, user_id)
        if not project:
            return jsonify({'error': 'Project not found'}), 404

        # Auto-create defaults for analysis types that have data but no workspaces
        analysis_types = []
        if project.get('has_database_schema'):
            analysis_types.append('database_schema')
        if project.get('has_runtime_flow'):
            analysis_types.append('runtime_flow')
        if project.get('has_api_routes'):
            analysis_types.append('api_routes')

        for at in analysis_types:
            get_or_create_default_workspace(cur, project_id, at)

        # Fetch all workspaces
        cur.execute(
            '''SELECT * FROM workspaces
               WHERE project_id = %s
               ORDER BY analysis_type, sort_order ASC''',
            (project_id,)
        )
        rows = cur.fetchall()

    # Group by analysis_type
    grouped = {}
    for row in rows:
        at = row['analysis_type']
        if at not in grouped:
            grouped[at] = []
        grouped[at].append({
            'id': row['id'],
            'name': row['name'],
            'analysis_type': at,
            'sort_order': row['sort_order'],
            'created_at': row['created_at'],
            'updated_at': row['updated_at'],
        })

    return jsonify({'workspaces': grouped}), 200


@workspaces_bp.route('/<int:project_id>/workspaces', methods=['POST'])
@jwt_required()
def create_workspace(project_id):
    """Create a new workspace under a visualization type."""
    user_id = int(get_jwt_identity())
    data = request.get_json()

    analysis_type = data.get('analysis_type')
    name = data.get('name', '').strip()

    if analysis_type not in ('database_schema', 'runtime_flow', 'api_routes'):
        return jsonify({'error': 'Invalid analysis_type'}), 400

    if not name:
        name = 'Untitled Workspace'

    if len(name) > 200:
        return jsonify({'error': 'Name too long (max 200 characters)'}), 400

    with get_connection() as conn:
        cur = conn.cursor()

        if not verify_project_ownership(cur, project_id, user_id):
            return jsonify({'error': 'Project not found'}), 404

        # Get next sort_order
        cur.execute(
            '''SELECT COALESCE(MAX(sort_order), -1) + 1 AS next_order
               FROM workspaces
               WHERE project_id = %s AND analysis_type = %s''',
            (project_id, analysis_type)
        )
        next_order = cur.fetchone()['next_order']

        cur.execute(
            '''INSERT INTO workspaces (project_id, analysis_type, name, sort_order)
               VALUES (%s, %s, %s, %s) RETURNING id, created_at, updated_at''',
            (project_id, analysis_type, name, next_order)
        )
        result = cur.fetchone()

    return jsonify({
        'workspace': {
            'id': result['id'],
            'project_id': project_id,
            'analysis_type': analysis_type,
            'name': name,
            'sort_order': next_order,
            'created_at': result['created_at'],
            'updated_at': result['updated_at'],
        }
    }), 201


@workspaces_bp.route('/<int:project_id>/workspaces/<int:workspace_id>', methods=['PATCH'])
@jwt_required()
def rename_workspace(project_id, workspace_id):
    """Rename a workspace."""
    user_id = int(get_jwt_identity())
    data = request.get_json()

    name = data.get('name', '').strip()
    if not name:
        return jsonify({'error': 'Name is required'}), 400
    if len(name) > 200:
        return jsonify({'error': 'Name too long (max 200 characters)'}), 400

    with get_connection() as conn:
        cur = conn.cursor()

        if not verify_project_ownership(cur, project_id, user_id):
            return jsonify({'error': 'Project not found'}), 404

        # Verify workspace belongs to this project
        cur.execute(
            'SELECT id FROM workspaces WHERE id = %s AND project_id = %s',
            (workspace_id, project_id)
        )
        if not cur.fetchone():
            return jsonify({'error': 'Workspace not found'}), 404

        cur.execute(
            '''UPDATE workspaces SET name = %s, updated_at = CURRENT_TIMESTAMP
               WHERE id = %s''',
            (name, workspace_id)
        )

    return jsonify({'message': 'Workspace renamed', 'name': name}), 200


@workspaces_bp.route('/<int:project_id>/workspaces/<int:workspace_id>', methods=['DELETE'])
@jwt_required()
def delete_workspace(project_id, workspace_id):
    """Delete a workspace. Prevents deleting the last workspace of a type."""
    user_id = int(get_jwt_identity())

    with get_connection() as conn:
        cur = conn.cursor()

        if not verify_project_ownership(cur, project_id, user_id):
            return jsonify({'error': 'Project not found'}), 404

        # Get workspace info
        cur.execute(
            'SELECT * FROM workspaces WHERE id = %s AND project_id = %s',
            (workspace_id, project_id)
        )
        workspace = cur.fetchone()
        if not workspace:
            return jsonify({'error': 'Workspace not found'}), 404

        # Check if this is the last workspace for this analysis_type
        cur.execute(
            '''SELECT COUNT(*) AS cnt FROM workspaces
               WHERE project_id = %s AND analysis_type = %s''',
            (project_id, workspace['analysis_type'])
        )
        count = cur.fetchone()['cnt']
        if count <= 1:
            return jsonify({'error': 'Cannot delete the last workspace'}), 400

        # Delete workspace (cascade will clean up related data)
        cur.execute('DELETE FROM workspaces WHERE id = %s', (workspace_id,))

    return jsonify({'message': 'Workspace deleted'}), 200


# ---------------------------------------------------------------------------
# Workspace-scoped Layout Endpoints
# ---------------------------------------------------------------------------

@workspaces_bp.route('/<int:project_id>/workspaces/<int:workspace_id>/layout', methods=['GET'])
@jwt_required()
def get_workspace_layout(project_id, workspace_id):
    """Get saved layout for a specific workspace."""
    user_id = int(get_jwt_identity())

    with get_connection() as conn:
        cur = conn.cursor()

        if not verify_project_ownership(cur, project_id, user_id):
            return jsonify({'error': 'Project not found'}), 404

        cur.execute(
            '''SELECT * FROM workspace_layouts
               WHERE workspace_id = %s
               ORDER BY updated_at DESC LIMIT 1''',
            (workspace_id,)
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


@workspaces_bp.route('/<int:project_id>/workspaces/<int:workspace_id>/layout', methods=['POST'])
@jwt_required()
def save_workspace_layout(project_id, workspace_id):
    """Save or update layout for a specific workspace."""
    user_id = int(get_jwt_identity())
    data = request.get_json()

    layout_data = data.get('layout_data')
    if not layout_data:
        return jsonify({'error': 'layout_data is required'}), 400

    with get_connection() as conn:
        cur = conn.cursor()

        if not verify_project_ownership(cur, project_id, user_id):
            return jsonify({'error': 'Project not found'}), 404

        # Get workspace to know analysis_type
        cur.execute(
            'SELECT * FROM workspaces WHERE id = %s AND project_id = %s',
            (workspace_id, project_id)
        )
        workspace = cur.fetchone()
        if not workspace:
            return jsonify({'error': 'Workspace not found'}), 404

        # Check if layout exists for this workspace
        cur.execute(
            'SELECT id FROM workspace_layouts WHERE workspace_id = %s',
            (workspace_id,)
        )
        existing = cur.fetchone()

        if existing:
            cur.execute(
                '''UPDATE workspace_layouts
                   SET layout_data = %s, updated_at = CURRENT_TIMESTAMP
                   WHERE id = %s''',
                (json.dumps(layout_data), existing['id'])
            )
            layout_id = existing['id']
        else:
            cur.execute(
                '''INSERT INTO workspace_layouts
                   (project_id, analysis_type, layout_data, workspace_id)
                   VALUES (%s, %s, %s, %s) RETURNING id''',
                (project_id, workspace['analysis_type'], json.dumps(layout_data), workspace_id)
            )
            layout_id = cur.fetchone()['id']

    return jsonify({
        'message': 'Layout saved successfully',
        'layout_id': layout_id
    }), 200


# ---------------------------------------------------------------------------
# Workspace-scoped Analysis Endpoints
# ---------------------------------------------------------------------------

@workspaces_bp.route('/<int:project_id>/workspaces/<int:workspace_id>/analysis', methods=['GET'])
@jwt_required()
def get_workspace_analysis(project_id, workspace_id):
    """Get database schema analysis for a specific workspace."""
    user_id = int(get_jwt_identity())

    with get_connection() as conn:
        cur = conn.cursor()

        if not verify_project_ownership(cur, project_id, user_id):
            return jsonify({'error': 'Project not found'}), 404

        cur.execute(
            '''SELECT * FROM analysis_results
               WHERE workspace_id = %s AND analysis_type = %s
               ORDER BY created_at DESC LIMIT 1''',
            (workspace_id, 'database_schema')
        )
        analysis_data = cur.fetchone()

    if not analysis_data:
        # Fall back to project-level analysis (backward compat)
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                '''SELECT * FROM analysis_results
                   WHERE project_id = %s AND analysis_type = %s
                   ORDER BY created_at DESC LIMIT 1''',
                (project_id, 'database_schema')
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


@workspaces_bp.route('/<int:project_id>/workspaces/<int:workspace_id>/runtime-flow', methods=['GET'])
@jwt_required()
def get_workspace_runtime_flow(project_id, workspace_id):
    """Get runtime flow analysis for a specific workspace."""
    user_id = int(get_jwt_identity())

    with get_connection() as conn:
        cur = conn.cursor()

        if not verify_project_ownership(cur, project_id, user_id):
            return jsonify({'error': 'Project not found'}), 404

        cur.execute(
            '''SELECT * FROM analysis_results
               WHERE workspace_id = %s AND analysis_type = %s
               ORDER BY created_at DESC LIMIT 1''',
            (workspace_id, 'runtime_flow')
        )
        analysis_data = cur.fetchone()

    if not analysis_data:
        # Fall back to project-level
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                '''SELECT * FROM analysis_results
                   WHERE project_id = %s AND analysis_type = %s AND workspace_id IS NULL
                   ORDER BY created_at DESC LIMIT 1''',
                (project_id, 'runtime_flow')
            )
            analysis_data = cur.fetchone()

    if not analysis_data:
        return jsonify({'error': 'No runtime flow analysis found'}), 404

    return jsonify({
        'analysis_id': analysis_data['id'],
        'flow': json.loads(analysis_data['result_data']),
        'created_at': analysis_data['created_at']
    }), 200


@workspaces_bp.route('/<int:project_id>/workspaces/<int:workspace_id>/analyze/runtime-flow', methods=['POST'])
@jwt_required()
def analyze_workspace_runtime_flow(project_id, workspace_id):
    """Run runtime flow analysis and store under a specific workspace."""
    user_id = int(get_jwt_identity())

    with get_connection() as conn:
        cur = conn.cursor()

        project = verify_project_ownership(cur, project_id, user_id)
        if not project:
            return jsonify({'error': 'Project not found'}), 404

        # Verify workspace
        cur.execute(
            'SELECT * FROM workspaces WHERE id = %s AND project_id = %s',
            (workspace_id, project_id)
        )
        if not cur.fetchone():
            return jsonify({'error': 'Workspace not found'}), 404

        file_path = project.get('file_path')
        if not file_path or not os.path.exists(file_path):
            return jsonify({'error': 'Project files not found. Please upload project files first.'}), 400

        try:
            manager = ParserManager()
            flow_data = manager.parse_runtime_flow(file_path)

            cur.execute(
                '''INSERT INTO analysis_results (project_id, analysis_type, result_data, workspace_id)
                   VALUES (%s, %s, %s, %s)''',
                (project_id, 'runtime_flow', json.dumps(flow_data), workspace_id)
            )

            # Ensure project flag is set
            cur.execute(
                'UPDATE projects SET has_runtime_flow = %s WHERE id = %s',
                (True, project_id)
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


@workspaces_bp.route('/<int:project_id>/workspaces/<int:workspace_id>/api-routes', methods=['GET'])
@jwt_required()
def get_workspace_api_routes(project_id, workspace_id):
    """Get API routes analysis for a specific workspace."""
    user_id = int(get_jwt_identity())

    with get_connection() as conn:
        cur = conn.cursor()

        if not verify_project_ownership(cur, project_id, user_id):
            return jsonify({'error': 'Project not found'}), 404

        cur.execute(
            '''SELECT * FROM analysis_results
               WHERE workspace_id = %s AND analysis_type = %s
               ORDER BY created_at DESC LIMIT 1''',
            (workspace_id, 'api_routes')
        )
        analysis_data = cur.fetchone()

    if not analysis_data:
        # Fall back to project-level
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                '''SELECT * FROM analysis_results
                   WHERE project_id = %s AND analysis_type = %s AND workspace_id IS NULL
                   ORDER BY created_at DESC LIMIT 1''',
                (project_id, 'api_routes')
            )
            analysis_data = cur.fetchone()

    if not analysis_data:
        return jsonify({'error': 'No API routes analysis found'}), 404

    return jsonify({
        'analysis_id': analysis_data['id'],
        'routes': json.loads(analysis_data['result_data']),
        'created_at': analysis_data['created_at']
    }), 200


@workspaces_bp.route('/<int:project_id>/workspaces/<int:workspace_id>/analyze/api-routes', methods=['POST'])
@jwt_required()
def analyze_workspace_api_routes(project_id, workspace_id):
    """Run API routes analysis and store under a specific workspace."""
    user_id = int(get_jwt_identity())

    with get_connection() as conn:
        cur = conn.cursor()

        project = verify_project_ownership(cur, project_id, user_id)
        if not project:
            return jsonify({'error': 'Project not found'}), 404

        # Verify workspace
        cur.execute(
            'SELECT * FROM workspaces WHERE id = %s AND project_id = %s',
            (workspace_id, project_id)
        )
        if not cur.fetchone():
            return jsonify({'error': 'Workspace not found'}), 404

        file_path = project.get('file_path')
        if not file_path or not os.path.exists(file_path):
            return jsonify({'error': 'Project files not found. Please upload project files first.'}), 400

        try:
            manager = ParserManager()
            routes_data = manager.parse_api_routes(file_path)

            cur.execute(
                '''INSERT INTO analysis_results (project_id, analysis_type, result_data, workspace_id)
                   VALUES (%s, %s, %s, %s)''',
                (project_id, 'api_routes', json.dumps(routes_data), workspace_id)
            )

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
