"""
Ruby on Rails ActiveRecord schema parser.

Parses ActiveRecord migrations (db/migrate/) and model associations
(app/models/) to extract database schema and relationships using
regex-based analysis.
"""

import os
import re
from pathlib import Path
from typing import Dict, List, Optional

from ..base import (
    BaseSchemaParser, find_source_files, read_file_safe,
    strip_comments, line_number_at,
)

# ---------------------------------------------------------------------------
# Compiled regex patterns
# ---------------------------------------------------------------------------

# Migration: create_table :name do |t|
_CREATE_TABLE_RE = re.compile(
    r'create_table\s+:(\w+)(?:\s*,\s*[^d]*?)?\s+do\s*\|(\w+)\|',
    re.MULTILINE,
)

# Column definitions inside create_table block:
#   t.string :name, null: false, index: { unique: true }
_COLUMN_RE = re.compile(
    r'(\w+)\.(string|text|integer|bigint|float|decimal|boolean|date|datetime'
    r'|time|timestamp|binary|references|json|jsonb|uuid|inet|cidr|macaddr'
    r'|hstore|array|numrange|tsrange|daterange)\s+:(\w+)'
    r'((?:\s*,\s*[^\n]*)?)',
    re.MULTILINE,
)

# t.timestamps (no column name, adds created_at and updated_at)
_TIMESTAMPS_RE = re.compile(r'(\w+)\.timestamps', re.MULTILINE)

# add_index :table, :column, unique: true
_ADD_INDEX_RE = re.compile(
    r'add_index\s+:(\w+)\s*,\s*:(\w+)(?:\s*,\s*unique:\s*true)?',
    re.MULTILINE,
)

# Model class: class User < ApplicationRecord
_MODEL_CLASS_RE = re.compile(
    r'class\s+(\w+)\s*<\s*(?:ApplicationRecord|ActiveRecord::Base)',
    re.MULTILINE,
)

# Association macros
_HAS_MANY_RE = re.compile(
    r'has_many\s+:(\w+)(?:\s*,\s*([^\n]*))?', re.MULTILINE,
)
_BELONGS_TO_RE = re.compile(
    r'belongs_to\s+:(\w+)(?:\s*,\s*([^\n]*))?', re.MULTILINE,
)
_HAS_ONE_RE = re.compile(
    r'has_one\s+:(\w+)(?:\s*,\s*([^\n]*))?', re.MULTILINE,
)
_HABTM_RE = re.compile(
    r'has_and_belongs_to_many\s+:(\w+)(?:\s*,\s*([^\n]*))?', re.MULTILINE,
)

# Option extractors
_NULL_FALSE_RE = re.compile(r'null:\s*false')
_UNIQUE_RE = re.compile(r'unique:\s*true')
_FOREIGN_KEY_RE = re.compile(r'foreign_key:\s*true')
_DEFAULT_RE = re.compile(r'default:\s*([^\s,]+)')
_CLASS_NAME_RE = re.compile(r'class_name:\s*["\'](\w+)["\']')

# Rails type → SQL type mapping
_TYPE_MAP = {
    'string': 'VARCHAR',
    'text': 'TEXT',
    'integer': 'INTEGER',
    'bigint': 'BIGINT',
    'float': 'FLOAT',
    'decimal': 'DECIMAL',
    'boolean': 'BOOLEAN',
    'date': 'DATE',
    'datetime': 'DATETIME',
    'time': 'TIME',
    'timestamp': 'TIMESTAMP',
    'binary': 'BLOB',
    'references': 'INTEGER',
    'json': 'JSON',
    'jsonb': 'JSONB',
    'uuid': 'UUID',
    'inet': 'INET',
    'cidr': 'CIDR',
    'macaddr': 'MACADDR',
    'hstore': 'HSTORE',
    'array': 'ARRAY',
    'numrange': 'NUMRANGE',
    'tsrange': 'TSRANGE',
    'daterange': 'DATERANGE',
}


def _pluralize_simple(name: str) -> str:
    """Very basic pluralization for Rails table name convention."""
    if name.endswith('y') and name[-2:] not in ('ay', 'ey', 'oy', 'uy'):
        return name[:-1] + 'ies'
    if name.endswith(('s', 'sh', 'ch', 'x', 'z')):
        return name + 'es'
    return name + 's'


class ActiveRecordParser(BaseSchemaParser):
    """Parse Ruby on Rails ActiveRecord migrations and model associations."""

    FILE_EXTENSIONS = ['.rb']

    def parse(self, project_path: str) -> Dict:
        """Parse ActiveRecord migrations and models.

        Looks in db/migrate/ for migration files and app/models/ for
        model association definitions.

        Returns:
            Standardized schema dict with tables and relationships.
        """
        tables: List[Dict] = []
        relationships: List[Dict] = []

        # --- Parse migrations ---
        migrate_dir = os.path.join(project_path, 'db', 'migrate')
        if os.path.isdir(migrate_dir):
            migration_files = find_source_files(migrate_dir, ['.rb'])
            # Sort by filename (migrations are timestamp-prefixed)
            migration_files.sort()
            for fpath in migration_files:
                content = read_file_safe(fpath)
                if content:
                    parsed = self._parse_migration(content, fpath)
                    tables.extend(parsed)
        else:
            # Fallback: search entire project for migration-like files
            all_rb = find_source_files(project_path, ['.rb'])
            for fpath in all_rb:
                if 'migrate' in fpath.lower():
                    content = read_file_safe(fpath)
                    if content:
                        tables.extend(self._parse_migration(content, fpath))

        # --- Parse model associations ---
        models_dir = os.path.join(project_path, 'app', 'models')
        if os.path.isdir(models_dir):
            model_files = find_source_files(models_dir, ['.rb'])
            for fpath in model_files:
                content = read_file_safe(fpath)
                if content:
                    rels = self._parse_model_associations(content, fpath)
                    relationships.extend(rels)
        else:
            # Fallback: search entire project for model-like files
            all_rb = find_source_files(project_path, ['.rb'])
            for fpath in all_rb:
                if 'model' in fpath.lower():
                    content = read_file_safe(fpath)
                    if content:
                        rels = self._parse_model_associations(content, fpath)
                        relationships.extend(rels)

        # If no explicit relationships from models, derive from foreign keys
        if not relationships:
            relationships = self._detect_relationships(tables)

        return self.make_schema_result(tables, relationships)

    # ------------------------------------------------------------------
    # Migration parsing
    # ------------------------------------------------------------------

    def _parse_migration(self, content: str, file_path: str) -> List[Dict]:
        """Parse a single migration file for create_table statements."""
        stripped = strip_comments(content, 'ruby')
        tables: List[Dict] = []

        for match in _CREATE_TABLE_RE.finditer(stripped):
            table_name = match.group(1)
            block_var = match.group(2)
            block_start = match.end()

            # Find the matching 'end' for this do block
            block_body = self._extract_do_block(stripped, block_start)
            if not block_body:
                continue

            columns = self._parse_columns(block_body, block_var)
            foreign_keys = self._extract_foreign_keys(block_body, block_var, table_name)
            indexes = self._extract_inline_indexes(block_body, block_var)

            # Add standalone add_index calls from the rest of the file
            for idx_match in _ADD_INDEX_RE.finditer(stripped):
                if idx_match.group(1) == table_name:
                    indexes.append({
                        'columns': [idx_match.group(2)],
                        'unique': 'unique: true' in (idx_match.group(0) or ''),
                    })

            # Rails always adds an implicit 'id' primary key unless disabled
            has_id = any(c['name'] == 'id' for c in columns)
            if not has_id:
                columns.insert(0, {
                    'name': 'id',
                    'type': 'BIGINT',
                    'nullable': False,
                    'primary_key': True,
                    'unique': True,
                })

            tables.append({
                'name': table_name,
                'columns': columns,
                'foreign_keys': foreign_keys,
                'indexes': indexes,
                'source_file': file_path,
                'line_number': line_number_at(content, match.start()),
            })

        return tables

    def _extract_do_block(self, content: str, start_pos: int) -> Optional[str]:
        """Extract the body of a Ruby do...end block starting from start_pos."""
        depth = 1
        i = start_pos

        # Keywords that open new blocks
        block_openers = re.compile(
            r'\b(do|def|class|module|if|unless|while|until|for|case|begin)\b'
        )
        block_closer = re.compile(r'\bend\b')

        while i < len(content):
            # Check for block openers
            opener = block_openers.search(content, i)
            closer = block_closer.search(content, i)

            if closer is None:
                return None

            if opener and opener.start() < closer.start():
                depth += 1
                i = opener.end()
            else:
                depth -= 1
                if depth == 0:
                    return content[start_pos:closer.start()]
                i = closer.end()

        return None

    def _parse_columns(self, block_body: str, block_var: str) -> List[Dict]:
        """Parse column definitions from a create_table block body."""
        columns: List[Dict] = []

        for match in _COLUMN_RE.finditer(block_body):
            var_name = match.group(1)
            if var_name != block_var:
                continue

            col_type = match.group(2)
            col_name = match.group(3)
            options = match.group(4) or ''

            nullable = not bool(_NULL_FALSE_RE.search(options))
            unique = bool(_UNIQUE_RE.search(options))

            default_match = _DEFAULT_RE.search(options)
            default_val = default_match.group(1) if default_match else None

            # References add a foreign key column: t.references :user → user_id
            if col_type == 'references':
                columns.append({
                    'name': f'{col_name}_id',
                    'type': 'BIGINT',
                    'nullable': nullable,
                    'primary_key': False,
                    'unique': unique,
                })
            else:
                column = {
                    'name': col_name,
                    'type': _TYPE_MAP.get(col_type, col_type.upper()),
                    'nullable': nullable,
                    'primary_key': False,
                    'unique': unique,
                }
                if default_val is not None:
                    column['default'] = default_val
                columns.append(column)

        # Handle t.timestamps
        if _TIMESTAMPS_RE.search(block_body):
            columns.append({
                'name': 'created_at',
                'type': 'DATETIME',
                'nullable': False,
                'primary_key': False,
                'unique': False,
            })
            columns.append({
                'name': 'updated_at',
                'type': 'DATETIME',
                'nullable': False,
                'primary_key': False,
                'unique': False,
            })

        return columns

    def _extract_foreign_keys(self, block_body: str, block_var: str,
                              table_name: str) -> List[Dict]:
        """Extract foreign keys from t.references calls."""
        foreign_keys: List[Dict] = []

        for match in _COLUMN_RE.finditer(block_body):
            if match.group(1) != block_var:
                continue
            if match.group(2) != 'references':
                continue

            ref_name = match.group(3)
            options = match.group(4) or ''

            # t.references :department, foreign_key: true
            # By default references implies a foreign key in Rails
            referenced_table = _pluralize_simple(ref_name)

            foreign_keys.append({
                'column': f'{ref_name}_id',
                'references_table': referenced_table,
                'references_column': 'id',
            })

        return foreign_keys

    def _extract_inline_indexes(self, block_body: str,
                                block_var: str) -> List[Dict]:
        """Extract inline index definitions from column options."""
        indexes: List[Dict] = []

        for match in _COLUMN_RE.finditer(block_body):
            if match.group(1) != block_var:
                continue

            col_name = match.group(3)
            col_type = match.group(2)
            options = match.group(4) or ''

            actual_col = f'{col_name}_id' if col_type == 'references' else col_name

            if _UNIQUE_RE.search(options) or 'index:' in options:
                unique = _UNIQUE_RE.search(options) is not None
                indexes.append({
                    'columns': [actual_col],
                    'unique': unique,
                })

        return indexes

    # ------------------------------------------------------------------
    # Model association parsing
    # ------------------------------------------------------------------

    def _parse_model_associations(self, content: str, file_path: str) -> List[Dict]:
        """Parse model file for association macros."""
        stripped = strip_comments(content, 'ruby')
        relationships: List[Dict] = []

        # Find the model class name
        class_match = _MODEL_CLASS_RE.search(stripped)
        if not class_match:
            return relationships

        model_name = class_match.group(1)
        model_table = _pluralize_simple(model_name.lower())

        # has_many :posts → one-to-many
        for match in _HAS_MANY_RE.finditer(stripped):
            assoc_name = match.group(1)
            options = match.group(2) or ''
            class_name_match = _CLASS_NAME_RE.search(options)
            target_table = (
                _pluralize_simple(class_name_match.group(1).lower())
                if class_name_match
                else assoc_name
            )
            relationships.append({
                'from': model_table,
                'to': target_table,
                'type': 'one-to-many',
                'source_association': 'has_many',
                'source_file': file_path,
            })

        # belongs_to :department → many-to-one
        for match in _BELONGS_TO_RE.finditer(stripped):
            assoc_name = match.group(1)
            options = match.group(2) or ''
            class_name_match = _CLASS_NAME_RE.search(options)
            target_table = (
                _pluralize_simple(class_name_match.group(1).lower())
                if class_name_match
                else _pluralize_simple(assoc_name)
            )
            relationships.append({
                'from': model_table,
                'to': target_table,
                'type': 'many-to-one',
                'source_association': 'belongs_to',
                'source_file': file_path,
            })

        # has_one :profile → one-to-one
        for match in _HAS_ONE_RE.finditer(stripped):
            assoc_name = match.group(1)
            options = match.group(2) or ''
            class_name_match = _CLASS_NAME_RE.search(options)
            target_table = (
                _pluralize_simple(class_name_match.group(1).lower())
                if class_name_match
                else _pluralize_simple(assoc_name)
            )
            relationships.append({
                'from': model_table,
                'to': target_table,
                'type': 'one-to-one',
                'source_association': 'has_one',
                'source_file': file_path,
            })

        # has_and_belongs_to_many :roles → many-to-many
        for match in _HABTM_RE.finditer(stripped):
            assoc_name = match.group(1)
            options = match.group(2) or ''
            class_name_match = _CLASS_NAME_RE.search(options)
            target_table = (
                _pluralize_simple(class_name_match.group(1).lower())
                if class_name_match
                else assoc_name
            )
            relationships.append({
                'from': model_table,
                'to': target_table,
                'type': 'many-to-many',
                'source_association': 'has_and_belongs_to_many',
                'source_file': file_path,
            })

        return relationships
