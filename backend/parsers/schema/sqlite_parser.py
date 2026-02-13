import logging
import sqlite3
import os
import re
from typing import Dict, List, Optional

from ..base import BaseSchemaParser, SKIP_DIRS

logger = logging.getLogger(__name__)

# Regex to validate SQLite identifier names: alphanumeric + underscore only.
# Table names from sqlite_master should always pass, but defense-in-depth
# against crafted .db files with adversarial table names.
_SAFE_IDENTIFIER_RE = re.compile(r'^[\w]+$', re.ASCII)


class SQLiteParser(BaseSchemaParser):
    """Parser for SQLite database files.

    Handles user-uploaded .db files — all table names are treated as
    untrusted input and sanitized before use in PRAGMA queries.
    """

    def parse(self, project_path: str) -> Dict:
        """Parse SQLite database schema."""
        db_file = self._find_db_file(project_path)
        if not db_file:
            return {'tables': [], 'relationships': [], 'error': 'No database file found'}

        try:
            with sqlite3.connect(db_file) as conn:
                cursor = conn.cursor()

                # Get all user tables (exclude SQLite internals)
                cursor.execute(
                    "SELECT name FROM sqlite_master "
                    "WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                )
                table_names = [row[0] for row in cursor.fetchall()]

                tables = []
                relationships = []

                for table_name in table_names:
                    safe_name = self._quote_identifier(table_name)

                    # Get column info
                    cursor.execute(f"PRAGMA table_info({safe_name})")
                    columns_info = cursor.fetchall()

                    columns = []
                    for col in columns_info:
                        columns.append({
                            'name': col[1],
                            'type': col[2] or 'TEXT',
                            'nullable': not col[3],
                            'primary_key': bool(col[5]),
                        })

                    tables.append({
                        'name': table_name,
                        'columns': columns,
                    })

                    # Get foreign keys
                    cursor.execute(f"PRAGMA foreign_key_list({safe_name})")
                    fks = cursor.fetchall()

                    for fk in fks:
                        relationships.append({
                            'from_table': table_name,
                            'to_table': fk[2],
                            'from_column': fk[3],
                            'to_column': fk[4],
                            'type': 'many-to-one',
                        })

                result = self.make_schema_result(tables, relationships)
                result['database_file'] = os.path.basename(db_file)
                return result

        except Exception as e:
            logger.warning("Failed to parse SQLite database %s: %s", db_file, e)
            return {
                'tables': [],
                'relationships': [],
                'error': f'Failed to parse database: {str(e)}',
            }

    def _find_db_file(self, path: str) -> Optional[str]:
        """Find the first SQLite database file, skipping vendor directories."""
        for root, dirs, files in os.walk(path):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            for file in files:
                if file.endswith(('.db', '.sqlite', '.sqlite3')):
                    return os.path.join(root, file)
        return None

    @staticmethod
    def _quote_identifier(name: str) -> str:
        """Safely quote a SQLite identifier for use in PRAGMA statements.

        PRAGMA doesn't support parameterized queries, so we must sanitize
        identifiers manually. Uses standard SQL double-quote escaping:
        any embedded double-quote is doubled.
        """
        escaped = name.replace('"', '""')
        return f'"{escaped}"'
