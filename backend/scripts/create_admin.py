import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db import get_connection
from werkzeug.security import generate_password_hash

username = "Admin"
email = "admin@localhost.com"
password = "LocalHost"

password_hash = generate_password_hash(password)

with get_connection() as conn:
    cur = conn.cursor()

    # Check if user already exists
    cur.execute('SELECT id FROM users WHERE username = ?', (username,))
    existing = cur.fetchone()

    if existing:
        print(f"User '{username}' already exists with ID {existing['id']}")
    else:
        # Create the user
        cur.execute(
            'INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)',
            (username, email, password_hash)
        )
        user_id = cur.lastrowid
        print(f"Created user '{username}' with ID {user_id}")
        print(f"Email: {email}")
        print(f"Password: {password}")
