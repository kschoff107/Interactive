"""
Migration: Add file tracking columns to projects table

This migration adds the following columns to support multi-file uploads:
- has_database_schema: BOOLEAN to track if database schema files have been uploaded
- has_runtime_flow: BOOLEAN to track if runtime flow files have been uploaded
- last_upload_date: TIMESTAMP of the most recent file upload
"""

import sys
import os

# Add parent directory to path to import config and database
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import Config

def run_migration():
    """Run the migration to add file tracking columns"""
    db_url = Config.SQLALCHEMY_DATABASE_URI

    is_postgres = db_url.startswith('postgres://') or db_url.startswith('postgresql://')
    is_sqlite = db_url.startswith('sqlite:///')

    if is_postgres:
        return migrate_postgres(db_url)
    elif is_sqlite:
        return migrate_sqlite(db_url)
    else:
        print(f"ERROR: Unsupported DATABASE_URL format: {db_url}")
        return False

def migrate_postgres(db_url):
    """Migrate PostgreSQL database"""
    import psycopg2

    try:
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()

        print("Starting PostgreSQL migration...")

        # Check if columns already exist
        cur.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name='projects' AND column_name IN ('has_database_schema', 'has_runtime_flow', 'last_upload_date');
        """)
        existing_columns = {row[0] for row in cur.fetchall()}

        # Add has_database_schema column if it doesn't exist
        if 'has_database_schema' not in existing_columns:
            print("  Adding has_database_schema column...")
            cur.execute("""
                ALTER TABLE projects
                ADD COLUMN has_database_schema BOOLEAN DEFAULT FALSE;
            """)

            # Set initial values based on existing analysis_results
            cur.execute("""
                UPDATE projects
                SET has_database_schema = TRUE
                WHERE id IN (
                    SELECT DISTINCT project_id
                    FROM analysis_results
                    WHERE analysis_type = 'database_schema'
                );
            """)
            print("  [OK] has_database_schema column added")
        else:
            print("  [SKIP] has_database_schema column already exists")

        # Add has_runtime_flow column if it doesn't exist
        if 'has_runtime_flow' not in existing_columns:
            print("  Adding has_runtime_flow column...")
            cur.execute("""
                ALTER TABLE projects
                ADD COLUMN has_runtime_flow BOOLEAN DEFAULT FALSE;
            """)

            # Set initial values based on existing analysis_results
            cur.execute("""
                UPDATE projects
                SET has_runtime_flow = TRUE
                WHERE id IN (
                    SELECT DISTINCT project_id
                    FROM analysis_results
                    WHERE analysis_type = 'runtime_flow'
                );
            """)
            print("  [OK] has_runtime_flow column added")
        else:
            print("  [SKIP] has_runtime_flow column already exists")

        # Add last_upload_date column if it doesn't exist
        if 'last_upload_date' not in existing_columns:
            print("  Adding last_upload_date column...")
            cur.execute("""
                ALTER TABLE projects
                ADD COLUMN last_upload_date TIMESTAMP;
            """)

            # Set initial value to created_at for existing projects
            cur.execute("""
                UPDATE projects
                SET last_upload_date = created_at
                WHERE last_upload_date IS NULL;
            """)
            print("  [OK] last_upload_date column added")
        else:
            print("  [SKIP] last_upload_date column already exists")

        conn.commit()
        print("PostgreSQL migration completed successfully!")
        return True

    except Exception as e:
        print(f"ERROR: PostgreSQL migration failed: {e}")
        if 'conn' in locals():
            conn.rollback()
        return False
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()

def migrate_sqlite(db_url):
    """Migrate SQLite database"""
    import sqlite3

    db_path = db_url.replace('sqlite:///', '')

    # Get absolute path
    if not os.path.isabs(db_path):
        db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), db_path)

    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()

        print(f"Starting SQLite migration for: {db_path}")

        # Get existing columns
        cur.execute("PRAGMA table_info(projects);")
        existing_columns = {row[1] for row in cur.fetchall()}

        # Add has_database_schema column if it doesn't exist
        if 'has_database_schema' not in existing_columns:
            print("  Adding has_database_schema column...")
            cur.execute("""
                ALTER TABLE projects
                ADD COLUMN has_database_schema BOOLEAN DEFAULT 0;
            """)

            # Set initial values based on existing analysis_results
            cur.execute("""
                UPDATE projects
                SET has_database_schema = 1
                WHERE id IN (
                    SELECT DISTINCT project_id
                    FROM analysis_results
                    WHERE analysis_type = 'database_schema'
                );
            """)
            print("  [OK] has_database_schema column added")
        else:
            print("  [SKIP] has_database_schema column already exists")

        # Add has_runtime_flow column if it doesn't exist
        if 'has_runtime_flow' not in existing_columns:
            print("  Adding has_runtime_flow column...")
            cur.execute("""
                ALTER TABLE projects
                ADD COLUMN has_runtime_flow BOOLEAN DEFAULT 0;
            """)

            # Set initial values based on existing analysis_results
            cur.execute("""
                UPDATE projects
                SET has_runtime_flow = 1
                WHERE id IN (
                    SELECT DISTINCT project_id
                    FROM analysis_results
                    WHERE analysis_type = 'runtime_flow'
                );
            """)
            print("  [OK] has_runtime_flow column added")
        else:
            print("  [SKIP] has_runtime_flow column already exists")

        # Add last_upload_date column if it doesn't exist
        if 'last_upload_date' not in existing_columns:
            print("  Adding last_upload_date column...")
            cur.execute("""
                ALTER TABLE projects
                ADD COLUMN last_upload_date TIMESTAMP;
            """)

            # Set initial value to created_at for existing projects
            cur.execute("""
                UPDATE projects
                SET last_upload_date = created_at
                WHERE last_upload_date IS NULL;
            """)
            print("  [OK] last_upload_date column added")
        else:
            print("  [SKIP] last_upload_date column already exists")

        conn.commit()
        print("SQLite migration completed successfully!")
        return True

    except Exception as e:
        print(f"ERROR: SQLite migration failed: {e}")
        if 'conn' in locals():
            conn.rollback()
        return False
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()

if __name__ == '__main__':
    success = run_migration()
    sys.exit(0 if success else 1)
