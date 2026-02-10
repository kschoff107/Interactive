"""
Migration: Add has_api_routes column to projects table

This migration adds the following column to support API routes visualization:
- has_api_routes: BOOLEAN to track if API routes analysis has been completed
"""

import sys
import os

# Add parent directory to path to import config and database
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import Config

def run_migration():
    """Run the migration to add has_api_routes column"""
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

        print("Starting PostgreSQL migration for has_api_routes...")

        # Check if column already exists
        cur.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name='projects' AND column_name = 'has_api_routes';
        """)
        existing = cur.fetchone()

        if not existing:
            print("  Adding has_api_routes column...")
            cur.execute("""
                ALTER TABLE projects
                ADD COLUMN has_api_routes BOOLEAN DEFAULT FALSE;
            """)

            # Set initial values based on existing analysis_results
            cur.execute("""
                UPDATE projects
                SET has_api_routes = TRUE
                WHERE id IN (
                    SELECT DISTINCT project_id
                    FROM analysis_results
                    WHERE analysis_type = 'api_routes'
                );
            """)
            print("  [OK] has_api_routes column added")
        else:
            print("  [SKIP] has_api_routes column already exists")

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

        if 'has_api_routes' not in existing_columns:
            print("  Adding has_api_routes column...")
            cur.execute("""
                ALTER TABLE projects
                ADD COLUMN has_api_routes BOOLEAN DEFAULT 0;
            """)

            # Set initial values based on existing analysis_results
            cur.execute("""
                UPDATE projects
                SET has_api_routes = 1
                WHERE id IN (
                    SELECT DISTINCT project_id
                    FROM analysis_results
                    WHERE analysis_type = 'api_routes'
                );
            """)
            print("  [OK] has_api_routes column added")
        else:
            print("  [SKIP] has_api_routes column already exists")

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
