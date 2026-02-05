import sqlite3
import os
from config import Config

def init_database():
    """Initialize SQLite database with all tables"""
    # Extract database path from DATABASE_URL
    db_url = Config.SQLALCHEMY_DATABASE_URI
    if db_url.startswith('sqlite:///'):
        db_path = db_url.replace('sqlite:///', '')
    else:
        print("ERROR: DATABASE_URL is not SQLite format")
        return

    # Get absolute path
    if not os.path.isabs(db_path):
        db_path = os.path.join(os.path.dirname(__file__), db_path)

    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()

        # Create users table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username VARCHAR(80) UNIQUE NOT NULL,
                email VARCHAR(120) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # Create projects table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name VARCHAR(200) NOT NULL,
                description TEXT,
                source_type VARCHAR(20) NOT NULL,
                git_url VARCHAR(500),
                file_path VARCHAR(500),
                language VARCHAR(50),
                framework VARCHAR(50),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );
        """)

        # Create analysis_results table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS analysis_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                analysis_type VARCHAR(50) NOT NULL,
                result_data TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
            );
        """)

        # Create workspace_notes table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS workspace_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                analysis_type VARCHAR(50) NOT NULL,
                note_text TEXT NOT NULL,
                position_x FLOAT NOT NULL,
                position_y FLOAT NOT NULL,
                color VARCHAR(20) DEFAULT 'yellow',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
            );
        """)

        # Create workspace_layouts table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS workspace_layouts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                analysis_type VARCHAR(50) NOT NULL,
                layout_data TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
            );
        """)

        # Create indexes for performance
        cur.execute("CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_projects_user_id ON projects(user_id);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_analysis_results_project_id ON analysis_results(project_id);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_workspace_notes_project_id ON workspace_notes(project_id);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_workspace_layouts_project_id ON workspace_layouts(project_id);")

        conn.commit()
        print(f"Database initialized successfully at: {db_path}")
    except Exception as e:
        print(f"ERROR: Unexpected error during initialization: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

    return True

if __name__ == '__main__':
    init_database()
