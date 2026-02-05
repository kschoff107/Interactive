import psycopg2
import sys
from config import Config

def init_database():
    """Initialize database with all tables"""
    conn = None
    cur = None
    try:
        conn = psycopg2.connect(Config.SQLALCHEMY_DATABASE_URI)
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
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                name VARCHAR(200) NOT NULL,
                description TEXT,
                source_type VARCHAR(20) NOT NULL,
                git_url VARCHAR(500),
                file_path VARCHAR(500),
                language VARCHAR(50),
                framework VARCHAR(50),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # Create analysis_results table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS analysis_results (
                id SERIAL PRIMARY KEY,
                project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
                analysis_type VARCHAR(50) NOT NULL,
                result_data JSONB NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # Create workspace_notes table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS workspace_notes (
                id SERIAL PRIMARY KEY,
                project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
                analysis_type VARCHAR(50) NOT NULL,
                note_text TEXT NOT NULL,
                position_x FLOAT NOT NULL,
                position_y FLOAT NOT NULL,
                color VARCHAR(20) DEFAULT 'yellow',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # Create workspace_layouts table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS workspace_layouts (
                id SERIAL PRIMARY KEY,
                project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
                analysis_type VARCHAR(50) NOT NULL,
                layout_data JSONB NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
        print("Database initialized successfully")
    except psycopg2.OperationalError as e:
        print(f"ERROR: Could not connect to database: {e}")
        sys.exit(1)
    except psycopg2.ProgrammingError as e:
        print(f"ERROR: SQL syntax error: {e}")
        if conn:
            conn.rollback()
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: Unexpected error during initialization: {e}")
        if conn:
            conn.rollback()
        sys.exit(1)
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

if __name__ == '__main__':
    init_database()
