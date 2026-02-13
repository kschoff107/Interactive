from flask import Flask, jsonify
from flask_jwt_extended import JWTManager
from flask_cors import CORS
from config import Config
import traceback

app = Flask(__name__)
app.config.from_object(Config)

# Initialize extensions
jwt = JWTManager(app)
CORS(app)

# JWT error handlers
@jwt.invalid_token_loader
def invalid_token_callback(error):
    print(f"JWT INVALID TOKEN: {error}")
    return jsonify({'error': 'Invalid token', 'details': str(error)}), 422

@jwt.unauthorized_loader
def unauthorized_callback(error):
    print(f"JWT UNAUTHORIZED: {error}")
    return jsonify({'error': 'Missing Authorization header', 'details': str(error)}), 422

@jwt.expired_token_loader
def expired_token_callback(jwt_header, jwt_payload):
    print(f"JWT EXPIRED: header={jwt_header}, payload={jwt_payload}")
    return jsonify({'error': 'Token has expired'}), 422

@jwt.revoked_token_loader
def revoked_token_callback(jwt_header, jwt_payload):
    print(f"JWT REVOKED: header={jwt_header}, payload={jwt_payload}")
    return jsonify({'error': 'Token has been revoked'}), 422

# Error handlers
@app.errorhandler(Exception)
def handle_error(error):
    print(f"ERROR CAUGHT: {error}")
    print(f"ERROR TYPE: {type(error).__name__}")
    print(f"ERROR ERRNO: {getattr(error, 'errno', None)}")
    print("TRACEBACK:")
    traceback.print_exc()
    return jsonify({
        'error': str(error),
        'error_type': type(error).__name__,
        'errno': getattr(error, 'errno', None)
    }), 500

@app.errorhandler(422)
def handle_unprocessable_entity(error):
    print(f"422 ERROR: {error}")
    print(traceback.format_exc())
    return jsonify({'error': 'Unprocessable entity', 'details': str(error)}), 422

# Register routes
from routes import init_routes
init_routes(app)

# Initialize database (runs on import, including gunicorn)
from db.init_db import init_database
init_database()

if __name__ == '__main__':
    # Disable reloader to avoid Windows-specific issues with file handles
    app.run(debug=True, host='0.0.0.0', port=5000, use_reloader=False)
