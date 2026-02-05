import sqlite3
from database import get_connection

# Test database connection
try:
    with get_connection() as conn:
        cur = conn.cursor()

        # Insert a test project
        cur.execute(
            '''INSERT INTO projects (user_id, name, description, source_type)
               VALUES (?, ?, ?, ?)''',
            (2, "Debug Test", "Test description", "upload")
        )
        project_id = cur.lastrowid
        print(f"Created project with ID: {project_id}")

        # Fetch it back
        cur.execute('SELECT * FROM projects WHERE id = ?', (project_id,))
        project_data = cur.fetchone()
        print(f"Fetched data: {project_data}")
        print(f"Data type: {type(project_data)}")
        print(f"Keys: {project_data.keys() if project_data else 'None'}")

        # Try to create Project object
        from models import Project
        try:
            project = Project(**project_data)
            print(f"Successfully created Project object: {project.to_dict()}")
        except Exception as e:
            print(f"Error creating Project: {e}")
            import traceback
            traceback.print_exc()

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
