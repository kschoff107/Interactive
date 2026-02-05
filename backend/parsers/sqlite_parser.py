import sqlite3
import os
from typing import Dict, List

class SQLiteParser:
    """Parser for SQLite database files"""

    def parse(self, project_path: str) -> Dict:
        """Parse SQLite database schema"""
        # Find the first .db file in the project
        db_file = self._find_db_file(project_path)
        if not db_file:
            return {'tables': [], 'relationships': [], 'error': 'No database file found'}

        try:
            conn = sqlite3.connect(db_file)
            cursor = conn.cursor()

            # Get all tables
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
            table_names = [row[0] for row in cursor.fetchall()]

            tables = []
            relationships = []

            for table_name in table_names:
                # Get table info
                cursor.execute(f"PRAGMA table_info({table_name})")
                columns_info = cursor.fetchall()

                columns = []
                for col in columns_info:
                    columns.append({
                        'name': col[1],
                        'type': col[2],
                        'nullable': not col[3],
                        'primary_key': bool(col[5])
                    })

                tables.append({
                    'name': table_name,
                    'columns': columns
                })

                # Get foreign keys
                cursor.execute(f"PRAGMA foreign_key_list({table_name})")
                fks = cursor.fetchall()

                for fk in fks:
                    relationships.append({
                        'from_table': table_name,
                        'to_table': fk[2],
                        'from_column': fk[3],
                        'to_column': fk[4],
                        'type': 'foreign_key'
                    })

            conn.close()

            return {
                'tables': tables,
                'relationships': relationships,
                'database_file': os.path.basename(db_file)
            }

        except Exception as e:
            return {
                'tables': [],
                'relationships': [],
                'error': f'Failed to parse database: {str(e)}'
            }

    def _find_db_file(self, path: str) -> str:
        """Find the first SQLite database file"""
        for root, dirs, files in os.walk(path):
            for file in files:
                if file.endswith(('.db', '.sqlite', '.sqlite3')):
                    return os.path.join(root, file)
        return None
