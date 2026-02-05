from werkzeug.security import generate_password_hash, check_password_hash

class User:
    def __init__(self, id, username, email, password_hash, created_at):
        self.id = id
        self.username = username
        self.email = email
        self.password_hash = password_hash
        self.created_at = created_at

    @staticmethod
    def hash_password(password):
        """Hash a password for storing"""
        return generate_password_hash(password)

    def check_password(self, password):
        """Check hashed password"""
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'created_at': self.created_at  # SQLite returns timestamps as strings
        }
