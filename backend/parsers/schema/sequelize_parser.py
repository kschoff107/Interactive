"""
Sequelize Parser - Extract database schema from Sequelize model definitions.

Handles two patterns:
  1. sequelize.define('ModelName', { fields }, { options })
  2. class Model extends Model {} + Model.init({ fields }, { options })

Also detects association calls: hasMany, belongsTo, hasOne, belongsToMany.

Note: We run regex on original content (not comment-stripped) because
strip_comments replaces string literals with whitespace, preventing
extraction of model names, table names, and reference targets.
"""

import os
import re
from typing import Dict, List, Optional, Tuple

from ..base import (
    BaseSchemaParser,
    extract_block_body,
    find_source_files,
    line_number_at,
    read_file_safe,
    strip_comments,
)

# ---------------------------------------------------------------------------
# Compiled regex patterns
# ---------------------------------------------------------------------------

# sequelize.define('ModelName', { ... }, { ... })
_RE_DEFINE = re.compile(
    r"""(?:const|let|var)\s+(\w+)\s*=\s*\w+\.define\s*\(\s*['"](\w+)['"]\s*,""",
)

# Model.init({ ... }, { ... })
_RE_MODEL_INIT = re.compile(
    r'(\w+)\.init\s*\(',
)

# class ModelName extends Model
_RE_CLASS_EXTENDS_MODEL = re.compile(
    r'class\s+(\w+)\s+extends\s+(?:\w+\.)?Model\b',
)

# DataTypes.XXX  or  Sequelize.XXX
_RE_DATATYPE = re.compile(
    r'(?:DataTypes|Sequelize)\.(\w+)(?:\(([^)]*)\))?',
)

# Field defined as shorthand:  fieldName: DataTypes.STRING
_RE_FIELD_SHORTHAND = re.compile(
    r"""(\w+)\s*:\s*(?:DataTypes|Sequelize)\.(\w+)(?:\(([^)]*)\))?""",
)

# Field defined as object:  fieldName: { type: DataTypes.STRING, ... }
_RE_FIELD_OBJECT = re.compile(
    r'(\w+)\s*:\s*\{([^}]+)\}',
)

# Options inside field objects
_RE_TYPE_IN_OBJ = re.compile(
    r"""type\s*:\s*(?:DataTypes|Sequelize)\.(\w+)(?:\(([^)]*)\))?""",
)
_RE_ALLOW_NULL = re.compile(r'allowNull\s*:\s*(true|false)', re.IGNORECASE)
_RE_PRIMARY_KEY = re.compile(r'primaryKey\s*:\s*(true|false)', re.IGNORECASE)
_RE_UNIQUE = re.compile(r'unique\s*:\s*(true|false)', re.IGNORECASE)
_RE_DEFAULT_VAL = re.compile(r"""defaultValue\s*:\s*([^,}]+)""")
_RE_AUTO_INCREMENT = re.compile(r'autoIncrement\s*:\s*(true|false)', re.IGNORECASE)
_RE_REFERENCES = re.compile(
    r"""references\s*:\s*\{\s*model\s*:\s*['"](\w+)['"]\s*,\s*key\s*:\s*['"](\w+)['"]""",
)

# Table name option:  tableName: 'users'
_RE_TABLE_NAME = re.compile(r"""tableName\s*:\s*['"](\w+)['"]""")

# Association calls
_RE_HAS_MANY = re.compile(r"""(\w+)\.hasMany\s*\(\s*(\w+)""")
_RE_BELONGS_TO = re.compile(r"""(\w+)\.belongsTo\s*\(\s*(\w+)""")
_RE_HAS_ONE = re.compile(r"""(\w+)\.hasOne\s*\(\s*(\w+)""")
_RE_BELONGS_TO_MANY = re.compile(r"""(\w+)\.belongsToMany\s*\(\s*(\w+)""")

# foreignKey inside association options
_RE_FOREIGN_KEY = re.compile(r"""foreignKey\s*:\s*['"](\w+)['"]""")

# Single-line comment for manual stripping
_RE_LINE_COMMENT = re.compile(r'//[^\n]*')

# Sequelize type -> SQL type mapping
_SEQ_TYPE_MAP = {
    'STRING': 'VARCHAR',
    'TEXT': 'TEXT',
    'INTEGER': 'INTEGER',
    'BIGINT': 'BIGINT',
    'FLOAT': 'FLOAT',
    'DOUBLE': 'DOUBLE',
    'DECIMAL': 'DECIMAL',
    'BOOLEAN': 'BOOLEAN',
    'DATE': 'TIMESTAMP',
    'DATEONLY': 'DATE',
    'UUID': 'UUID',
    'UUIDV4': 'UUID',
    'JSON': 'JSON',
    'JSONB': 'JSONB',
    'BLOB': 'BLOB',
    'ENUM': 'ENUM',
    'ARRAY': 'ARRAY',
}


class SequelizeParser(BaseSchemaParser):
    """Parse Sequelize model definitions into standardized schema format."""

    FILE_EXTENSIONS = ['.js', '.ts']

    def parse(self, project_path: str) -> Dict:
        """Parse all Sequelize model files in project_path."""
        files = self.find_files(project_path)
        all_tables: List[Dict] = []
        all_relationships: List[Dict] = []

        for fpath in files:
            content = read_file_safe(fpath)
            if not content:
                continue
            try:
                tables, rels = self._parse_file(content, fpath)
                all_tables.extend(tables)
                all_relationships.extend(rels)
            except Exception:
                continue

        implicit = self._detect_relationships(all_tables)
        existing = {(r['from'], r['to']) for r in all_relationships}
        for r in implicit:
            if (r['from'], r['to']) not in existing:
                all_relationships.append(r)

        return self.make_schema_result(all_tables, all_relationships)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _parse_file(
        self, content: str, file_path: str
    ) -> Tuple[List[Dict], List[Dict]]:
        """Parse a single JS/TS file for Sequelize models and associations.

        Uses original content (not comment-stripped) so that string literals
        like model names, table names, and reference targets are preserved.
        Line comments are stripped manually to avoid matching inside comments.
        """
        # Strip only line comments, preserving string literals
        cleaned = _RE_LINE_COMMENT.sub('', content)
        tables: List[Dict] = []
        relationships: List[Dict] = []

        # Pattern 1: sequelize.define(...)
        for m in _RE_DEFINE.finditer(cleaned):
            var_name = m.group(1)
            model_name = m.group(2)
            # Find the fields object starting after the model name arg
            # We need to find the first { after the comma
            body, bs, be = extract_block_body(cleaned, m.end() - 1)
            if bs < 0:
                continue
            columns, fks = self._parse_fields(body, cleaned)
            # Try to find options block (second { } after first)
            table_name = self._to_plural_snake(model_name)
            rest_after_fields = cleaned[be + 1:]
            opts_body, obs, obe = extract_block_body(rest_after_fields, 0)
            if obs >= 0:
                tn_m = _RE_TABLE_NAME.search(opts_body)
                if tn_m:
                    table_name = tn_m.group(1)
            tables.append({
                'name': table_name,
                'model_name': model_name,
                'columns': columns,
                'foreign_keys': fks,
                'indexes': [],
                'file_path': file_path,
                'line_number': line_number_at(content, m.start()),
            })

        # Pattern 2: Model.init(...)
        for m in _RE_MODEL_INIT.finditer(cleaned):
            model_name = m.group(1)
            body, bs, be = extract_block_body(cleaned, m.end() - 1)
            if bs < 0:
                continue
            columns, fks = self._parse_fields(body, cleaned)
            table_name = self._to_plural_snake(model_name)
            # Try to find options in second arg
            rest_after_fields = cleaned[be + 1:]
            opts_body, obs, obe = extract_block_body(rest_after_fields, 0)
            if obs >= 0:
                tn_m = _RE_TABLE_NAME.search(opts_body)
                if tn_m:
                    table_name = tn_m.group(1)
            tables.append({
                'name': table_name,
                'model_name': model_name,
                'columns': columns,
                'foreign_keys': fks,
                'indexes': [],
                'file_path': file_path,
                'line_number': line_number_at(content, m.start()),
            })

        # --- Associations ---
        for pattern, rel_type in [
            (_RE_HAS_MANY, 'one-to-many'),
            (_RE_BELONGS_TO, 'many-to-one'),
            (_RE_HAS_ONE, 'one-to-one'),
            (_RE_BELONGS_TO_MANY, 'many-to-many'),
        ]:
            for m in pattern.finditer(cleaned):
                source = m.group(1)
                target = m.group(2)
                relationships.append({
                    'from': source,
                    'to': target,
                    'type': rel_type,
                })

        return tables, relationships

    def _parse_fields(self, body: str, full_content: str = '') -> Tuple[List[Dict], List[Dict]]:
        """Parse field definitions from the fields object body.

        Uses original content so that references with string model names
        can be extracted properly.
        """
        columns: List[Dict] = []
        foreign_keys: List[Dict] = []

        # Try object-style fields first: fieldName: { type: ... }
        for m in _RE_FIELD_OBJECT.finditer(body):
            field_name = m.group(1)
            field_body = m.group(2)
            type_m = _RE_TYPE_IN_OBJ.search(field_body)
            if not type_m:
                continue
            seq_type = type_m.group(1)
            sql_type = _SEQ_TYPE_MAP.get(seq_type, seq_type)

            nullable = self._extract_bool(field_body, _RE_ALLOW_NULL, default=True)
            primary_key = self._extract_bool(field_body, _RE_PRIMARY_KEY, default=False)
            unique = self._extract_bool(field_body, _RE_UNIQUE, default=False)
            auto_inc = self._extract_bool(field_body, _RE_AUTO_INCREMENT, default=False)

            col: Dict = {
                'name': field_name,
                'type': sql_type,
                'nullable': nullable,
                'primary_key': primary_key,
                'unique': unique or primary_key,
            }
            if auto_inc:
                col['auto_increment'] = True
            default_m = _RE_DEFAULT_VAL.search(field_body)
            if default_m:
                col['default'] = default_m.group(1).strip().strip("'\"")

            # Check for references (foreign key)
            ref_m = _RE_REFERENCES.search(field_body)
            if ref_m:
                foreign_keys.append({
                    'column': field_name,
                    'references_table': ref_m.group(1),
                    'references_column': ref_m.group(2),
                })

            columns.append(col)

        # Shorthand fields: fieldName: DataTypes.STRING
        # Only add fields not already found as objects
        existing_names = {c['name'] for c in columns}
        for m in _RE_FIELD_SHORTHAND.finditer(body):
            field_name = m.group(1)
            if field_name in existing_names or field_name == 'type':
                continue
            seq_type = m.group(2)
            sql_type = _SEQ_TYPE_MAP.get(seq_type, seq_type)
            columns.append({
                'name': field_name,
                'type': sql_type,
                'nullable': True,
                'primary_key': False,
                'unique': False,
            })

        return columns, foreign_keys

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_bool(text: str, pattern: re.Pattern, default: bool = False) -> bool:
        m = pattern.search(text)
        if m:
            return m.group(1).lower() == 'true'
        return default

    @staticmethod
    def _to_plural_snake(name: str) -> str:
        """Simple PascalCase -> plural_snake_case for table name guessing."""
        s1 = re.sub(r'(.)([A-Z][a-z]+)', r'\1_\2', name)
        snake = re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', s1).lower()
        if not snake.endswith('s'):
            snake += 's'
        return snake
