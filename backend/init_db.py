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
                has_database_schema BOOLEAN DEFAULT FALSE,
                has_runtime_flow BOOLEAN DEFAULT FALSE,
                has_api_routes BOOLEAN DEFAULT FALSE,
                last_upload_date TIMESTAMP,
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

        # Create code_analysis table for AI-generated insights
        cur.execute("""
            CREATE TABLE IF NOT EXISTS code_analysis (
                id SERIAL PRIMARY KEY,
                project_id INTEGER NOT NULL,
                file_hash VARCHAR(64) NOT NULL,
                analysis_type VARCHAR(50) DEFAULT 'runtime_flow',
                narrative_json TEXT NOT NULL,
                model_used VARCHAR(50),
                tokens_used INTEGER,
                generation_time_ms INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
                UNIQUE(project_id, file_hash)
            );
        """)

        # Create workspaces table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS workspaces (
                id SERIAL PRIMARY KEY,
                project_id INTEGER NOT NULL,
                analysis_type VARCHAR(50) NOT NULL,
                name VARCHAR(200) NOT NULL,
                sort_order INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
            );
        """)

        # Create workspace_files table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS workspace_files (
                id SERIAL PRIMARY KEY,
                workspace_id INTEGER NOT NULL,
                file_name VARCHAR(255) NOT NULL,
                file_path VARCHAR(500) NOT NULL,
                file_size INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE
            );
        """)

        # Create indexes for performance
        cur.execute("CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_projects_user_id ON projects(user_id);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_analysis_results_project_id ON analysis_results(project_id);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_workspace_notes_project_id ON workspace_notes(project_id);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_workspace_layouts_project_id ON workspace_layouts(project_id);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_code_analysis_lookup ON code_analysis(project_id, file_hash);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_code_analysis_expires ON code_analysis(expires_at);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_workspaces_project_type ON workspaces(project_id, analysis_type);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_workspace_files_workspace_id ON workspace_files(workspace_id);")

        # Add missing columns to existing tables (migrations for existing deployments)
        # Each migration in its own try/except to handle partial schema states
        migrations = [
            "ALTER TABLE projects ADD COLUMN IF NOT EXISTS has_database_schema BOOLEAN DEFAULT FALSE;",
            "ALTER TABLE projects ADD COLUMN IF NOT EXISTS has_runtime_flow BOOLEAN DEFAULT FALSE;",
            "ALTER TABLE projects ADD COLUMN IF NOT EXISTS has_api_routes BOOLEAN DEFAULT FALSE;",
            "ALTER TABLE projects ADD COLUMN IF NOT EXISTS last_upload_date TIMESTAMP;",
            "ALTER TABLE projects ADD COLUMN IF NOT EXISTS git_branch VARCHAR(100);",
            "ALTER TABLE analysis_results ADD COLUMN IF NOT EXISTS workspace_id INTEGER REFERENCES workspaces(id) ON DELETE SET NULL;",
            "ALTER TABLE workspace_layouts ADD COLUMN IF NOT EXISTS workspace_id INTEGER REFERENCES workspaces(id) ON DELETE SET NULL;",
            "ALTER TABLE workspace_notes ADD COLUMN IF NOT EXISTS workspace_id INTEGER REFERENCES workspaces(id) ON DELETE SET NULL;",
            "ALTER TABLE workspaces ADD COLUMN IF NOT EXISTS file_path VARCHAR(500);",
        ]

        for migration in migrations:
            try:
                cur.execute(migration)
                conn.commit()
            except Exception as e:
                print(f"Migration skipped (may already exist): {e}")
                conn.rollback()

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
                has_database_schema BOOLEAN DEFAULT 0,
                has_runtime_flow BOOLEAN DEFAULT 0,
                has_api_routes BOOLEAN DEFAULT 0,
                last_upload_date TIMESTAMP,
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

        # Create code_analysis table for AI-generated insights
        cur.execute("""
            CREATE TABLE IF NOT EXISTS code_analysis (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                file_hash VARCHAR(64) NOT NULL,
                analysis_type VARCHAR(50) DEFAULT 'runtime_flow',
                narrative_json TEXT NOT NULL,
                model_used VARCHAR(50),
                tokens_used INTEGER,
                generation_time_ms INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
                UNIQUE(project_id, file_hash)
            );
        """)

        # Create workspaces table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS workspaces (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                analysis_type VARCHAR(50) NOT NULL,
                name VARCHAR(200) NOT NULL,
                sort_order INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
            );
        """)

        # Create workspace_files table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS workspace_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workspace_id INTEGER NOT NULL,
                file_name VARCHAR(255) NOT NULL,
                file_path VARCHAR(500) NOT NULL,
                file_size INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE
            );
        """)

        # Create indexes for performance
        cur.execute("CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_projects_user_id ON projects(user_id);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_analysis_results_project_id ON analysis_results(project_id);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_workspace_notes_project_id ON workspace_notes(project_id);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_workspace_layouts_project_id ON workspace_layouts(project_id);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_code_analysis_lookup ON code_analysis(project_id, file_hash);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_code_analysis_expires ON code_analysis(expires_at);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_workspaces_project_type ON workspaces(project_id, analysis_type);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_workspace_files_workspace_id ON workspace_files(workspace_id);")

        # Add workspace_id columns to existing tables (SQLite migration)
        sqlite_migrations = [
            ("analysis_results", "workspace_id", "INTEGER"),
            ("workspace_layouts", "workspace_id", "INTEGER"),
            ("workspace_notes", "workspace_id", "INTEGER"),
            ("workspaces", "file_path", "VARCHAR(500)"),
        ]
        for table, column, col_type in sqlite_migrations:
            try:
                cur.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type};")
            except Exception:
                pass  # Column already exists

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
