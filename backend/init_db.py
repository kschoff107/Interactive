import os
from config import Config

def init_database():
    """Initialize database with all tables (supports SQLite and PostgreSQL)"""
    db_url = Config.SQLALCHEMY_DATABASE_URI

    # Determine database type
    is_postgres = db_url.startswith('postgres://') or db_url.startswith('postgresql://')
    is_sqlite = db_url.startswith('sqlite:///')

    if is_postgres:
        return init_postgres_database(db_url)
    elif is_sqlite:
        return init_sqlite_database(db_url)
    else:
        print(f"ERROR: Unsupported DATABASE_URL format: {db_url}")
        return False

def init_postgres_database(db_url):
    """Initialize PostgreSQL database"""
    import psycopg2
    from psycopg2 import sql

    try:
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()

        # Create users table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username VARCHAR(80) UNIQUE NOT NULL,
                email VARCHAR(120) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # Create projects table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id SERIAL PRIMARY KEY,
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
                id SERIAL PRIMARY KEY,
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
                id SERIAL PRIMARY KEY,
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
                id SERIAL PRIMARY KEY,
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
        print("PostgreSQL database initialized successfully")
        return True

    except Exception as e:
        print(f"ERROR: Failed to initialize PostgreSQL database: {e}")
        if 'conn' in locals():
            conn.rollback()
        return False
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()

def init_sqlite_database(db_url):
    """Initialize SQLite database"""
    import sqlite3

    db_path = db_url.replace('sqlite:///', '')

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
        print(f"SQLite database initialized successfully at: {db_path}")
        return True

    except Exception as e:
        print(f"ERROR: Failed to initialize SQLite database: {e}")
        if 'conn' in locals():
            conn.rollback()
        return False
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()

if __name__ == '__main__':
    init_database()
