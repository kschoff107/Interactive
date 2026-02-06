from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token
from database import get_connection
from models import User

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/register', methods=['POST'])
def register():
    """Register a new user"""
    data = request.get_json()

    username = data.get('username')
    email = data.get('email')
    password = data.get('password')

    if not all([username, email, password]):
        return jsonify({'error': 'Missing required fields'}), 400

    with get_connection() as conn:
        cur = conn.cursor()

        # Check if user exists
        cur.execute('SELECT id FROM users WHERE username = %s OR email = %s', (username, email))
        if cur.fetchone():
            return jsonify({'error': 'User already exists'}), 409

        # Create user
        password_hash = User.hash_password(password)
        cur.execute(
            'INSERT INTO users (username, email, password_hash) VALUES (%s, %s, %s) RETURNING id',
            (username, email, password_hash)
        )
        result = cur.fetchone()
        user_id = result['id']

        # Get created_at timestamp
        cur.execute('SELECT created_at FROM users WHERE id = %s', (user_id,))
        result = cur.fetchone()
        created_at = result['created_at']

        # Create JWT token (identity must be string)
        access_token = create_access_token(identity=str(user_id))

        user = User(user_id, username, email, password_hash, created_at)

        return jsonify({
            'access_token': access_token,
            'user': user.to_dict()
        }), 201

@auth_bp.route('/login', methods=['POST'])
def login():
    """Login existing user"""
    data = request.get_json()

    username = data.get('username')
    password = data.get('password')

    if not all([username, password]):
        return jsonify({'error': 'Missing required fields'}), 400

    with get_connection() as conn:
        cur = conn.cursor()

        cur.execute('SELECT * FROM users WHERE username = %s', (username,))
        user_data = cur.fetchone()

    if not user_data:
        return jsonify({'error': 'Invalid credentials'}), 401

    user = User(**user_data)

    if not user.check_password(password):
        return jsonify({'error': 'Invalid credentials'}), 401

    access_token = create_access_token(identity=str(user.id))

    return jsonify({
        'access_token': access_token,
        'user': user.to_dict()
    }), 200
