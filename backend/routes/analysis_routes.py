import json
import sys
import traceback
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from database import get_connection
from services.code_analysis_service import CodeAnalysisService, CodeAnalysisError

analysis_bp = Blueprint('analysis', __name__)


@analysis_bp.route('/<int:project_id>/analyze-code', methods=['POST'])
@jwt_required()
def analyze_code(project_id):
    """
    Generate AI-powered code analysis for a project.

    Request Body (optional):
        {
            "force_regenerate": false  // Bypass cache and regenerate
        }

    Returns:
        {
            "status": "success",
            "analysis": {
                "overview": "...",
                "how_it_starts": "...",
                "architecture": "...",
                "complexity": "...",
                "potential_issues": "...",
                "call_chains": "..."
            },
            "cached": true/false,
            "generated_at": "2024-01-15T10:30:00Z"
        }
    """
    print(f"=== analyze_code called for project {project_id} ===", file=sys.stderr)

    try:
        user_id = int(get_jwt_identity())
        print(f"User ID: {user_id}", file=sys.stderr)

        # Get request options (handle missing or empty body)
        data = {}
        if request.is_json:
            data = request.get_json() or {}
        force_regenerate = data.get('force_regenerate', False)

        with get_connection() as conn:
            cur = conn.cursor()

            # Verify project ownership
            cur.execute('SELECT * FROM projects WHERE id = %s AND user_id = %s', (project_id, user_id))
            project_data = cur.fetchone()

            if not project_data:
                return jsonify({'status': 'error', 'error': 'Project not found'}), 404

            # Check if project has runtime flow data
            if not project_data.get('has_runtime_flow'):
                return jsonify({
                    'status': 'error',
                    'error': 'No runtime flow data available. Please upload and analyze Python files first.'
                }), 400

            # Get the runtime flow data from analysis_results
            cur.execute(
                '''SELECT result_data FROM analysis_results
                   WHERE project_id = %s AND analysis_type = %s
                   ORDER BY created_at DESC LIMIT 1''',
                (project_id, 'runtime_flow')
            )
            analysis_row = cur.fetchone()

            if not analysis_row:
                return jsonify({
                    'status': 'error',
                    'error': 'Runtime flow data not found. Please re-analyze the project.'
                }), 404

            flow_data = json.loads(analysis_row['result_data'])

        # Initialize the analysis service
        service = CodeAnalysisService()
        print(f"Service configured: {service.is_configured()}", file=sys.stderr)

        # Check if service is configured
        if not service.is_configured():
            return jsonify({
                'status': 'error',
                'error': 'AI analysis not configured. Contact administrator.'
            }), 503

        # Generate or retrieve analysis
        print("Calling service.analyze()...", file=sys.stderr)
        result = service.analyze(
            project_id=project_id,
            flow_data=flow_data,
            force_regenerate=force_regenerate
        )
        print(f"Analysis result received: {bool(result)}", file=sys.stderr)
        return jsonify(result), 200

    except CodeAnalysisError as e:
        print(f"CodeAnalysisError: {e}", file=sys.stderr)
        response = {
            'status': 'error',
            'error': str(e)
        }
        if e.retry_after:
            response['retry_after'] = e.retry_after
        return jsonify(response), 503
    except Exception as e:
        print(f"Unexpected error in analyze_code: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        return jsonify({
            'status': 'error',
            'error': f'Unexpected error: {str(e)}'
        }), 500


@analysis_bp.route('/<int:project_id>/analyze-code', methods=['GET'])
@jwt_required()
def get_cached_analysis(project_id):
    """
    Get cached code analysis for a project (if available).

    Returns cached analysis without generating new one.
    Use POST endpoint to generate if not cached.
    """
    user_id = int(get_jwt_identity())

    with get_connection() as conn:
        cur = conn.cursor()

        # Verify project ownership
        cur.execute('SELECT * FROM projects WHERE id = %s AND user_id = %s', (project_id, user_id))
        project_data = cur.fetchone()

        if not project_data:
            return jsonify({'status': 'error', 'error': 'Project not found'}), 404

        # Get the latest cached analysis
        cur.execute(
            '''SELECT narrative_json, model_used, created_at, expires_at
               FROM code_analysis
               WHERE project_id = %s
               ORDER BY created_at DESC LIMIT 1''',
            (project_id,)
        )
        cached = cur.fetchone()

        if not cached:
            return jsonify({
                'status': 'not_found',
                'message': 'No cached analysis available. Use POST to generate.'
            }), 404

        return jsonify({
            'status': 'success',
            'analysis': json.loads(cached['narrative_json']),
            'cached': True,
            'model_used': cached['model_used'],
            'generated_at': cached['created_at'].isoformat() if cached['created_at'] else None,
            'expires_at': cached['expires_at'].isoformat() if cached['expires_at'] else None
        }), 200


@analysis_bp.route('/<int:project_id>/analyze-code/status', methods=['GET'])
@jwt_required()
def get_analysis_status(project_id):
    """
    Check if AI analysis is available and configured.

    Returns:
        {
            "configured": true/false,
            "has_cached": true/false,
            "has_flow_data": true/false
        }
    """
    user_id = int(get_jwt_identity())

    with get_connection() as conn:
        cur = conn.cursor()

        # Verify project ownership
        cur.execute('SELECT has_runtime_flow FROM projects WHERE id = %s AND user_id = %s',
                    (project_id, user_id))
        project_data = cur.fetchone()

        if not project_data:
            return jsonify({'status': 'error', 'error': 'Project not found'}), 404

        # Check for cached analysis
        cur.execute(
            'SELECT COUNT(*) as count FROM code_analysis WHERE project_id = %s',
            (project_id,)
        )
        cache_count = cur.fetchone()['count']

    service = CodeAnalysisService()

    return jsonify({
        'configured': service.is_configured(),
        'has_cached': cache_count > 0,
        'has_flow_data': project_data.get('has_runtime_flow', False)
    }), 200
