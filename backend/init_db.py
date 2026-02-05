"""Database initialization script."""

import sys
from pathlib import Path

# Add backend directory to path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from database import engine, Base, init_db
from models import User, Project, AnalysisResult, WorkspaceNote, WorkspaceLayout


def create_tables():
    """Create all database tables."""
    print("Creating database tables...")
    try:
        # Import all models to ensure they're registered with Base
        # This is already done via the models import above

        # Create all tables
        Base.metadata.create_all(bind=engine)

        print("Successfully created the following tables:")
        for table_name in Base.metadata.tables.keys():
            print(f"  - {table_name}")

        return True
    except Exception as e:
        print(f"Error creating tables: {e}")
        return False


def drop_tables():
    """Drop all database tables. Use with caution!"""
    print("WARNING: Dropping all database tables...")
    try:
        Base.metadata.drop_all(bind=engine)
        print("Successfully dropped all tables.")
        return True
    except Exception as e:
        print(f"Error dropping tables: {e}")
        return False


def reset_database():
    """Drop and recreate all tables. Use with caution!"""
    print("Resetting database...")
    if drop_tables():
        return create_tables()
    return False


if __name__ == "__main__":
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        if command == "create":
            create_tables()
        elif command == "drop":
            response = input("Are you sure you want to drop all tables? (yes/no): ")
            if response.lower() == "yes":
                drop_tables()
            else:
                print("Operation cancelled.")
        elif command == "reset":
            response = input("Are you sure you want to reset the database? (yes/no): ")
            if response.lower() == "yes":
                reset_database()
            else:
                print("Operation cancelled.")
        else:
            print(f"Unknown command: {command}")
            print("Available commands: create, drop, reset")
    else:
        # Default: create tables
        create_tables()
