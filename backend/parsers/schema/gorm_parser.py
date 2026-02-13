"""
Go GORM schema parser.

Parses Go struct definitions with GORM tags to extract database schema
and relationships using regex-based analysis.
"""

import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from ..base import (
    BaseSchemaParser, find_source_files, read_file_safe,
    line_number_at, strip_comments_only,
)

# ---------------------------------------------------------------------------
# Compiled regex patterns
# ---------------------------------------------------------------------------

# type User struct {
_STRUCT_RE = re.compile(
    r'type\s+(\w+)\s+struct\s*\{',
    re.MULTILINE,
)

# gorm.Model embedded struct
_GORM_MODEL_RE = re.compile(r'^\s*gorm\.Model\b', re.MULTILINE)

# Struct field line:
#   Name  string  `gorm:"column:name;type:varchar(100);not null" json:"name"`
_FIELD_RE = re.compile(
    r'^\s+(\w+)\s+'                    # field name
    r'(\*?\[?\]?\*?\w+(?:\.\w+)?)\s*'  # field type (supports *Type, []Type, *[]Type, pkg.Type)
    r'(?:`([^`]*)`)?',                 # optional struct tags
    re.MULTILINE,
)

# GORM tag extractors
_GORM_TAG_RE = re.compile(r'gorm:"([^"]*)"')
_COLUMN_TAG_RE = re.compile(r'column:(\w+)')
_TYPE_TAG_RE = re.compile(r'type:([^;]+)')
_NOT_NULL_TAG_RE = re.compile(r'not null', re.IGNORECASE)
_UNIQUE_TAG_RE = re.compile(r'uniqueIndex|unique', re.IGNORECASE)
_PRIMARY_KEY_TAG_RE = re.compile(r'primaryKey|primary_key', re.IGNORECASE)
_DEFAULT_TAG_RE = re.compile(r'default:([^;]+)')
_FK_TAG_RE = re.compile(r'foreignKey:(\w+)')
_INDEX_TAG_RE = re.compile(r'index(?::(\w+))?', re.IGNORECASE)
_AUTOINCREMENT_TAG_RE = re.compile(r'autoIncrement', re.IGNORECASE)

# Go type → SQL type mapping
_GO_TYPE_MAP = {
    'string': 'VARCHAR',
    'int': 'INTEGER',
    'int8': 'SMALLINT',
    'int16': 'SMALLINT',
    'int32': 'INTEGER',
    'int64': 'BIGINT',
    'uint': 'INTEGER',
    'uint8': 'SMALLINT',
    'uint16': 'SMALLINT',
    'uint32': 'INTEGER',
    'uint64': 'BIGINT',
    'float32': 'FLOAT',
    'float64': 'DOUBLE',
    'bool': 'BOOLEAN',
    'time.Time': 'TIMESTAMP',
    'sql.NullString': 'VARCHAR',
    'sql.NullInt64': 'BIGINT',
    'sql.NullFloat64': 'DOUBLE',
    'sql.NullBool': 'BOOLEAN',
    'sql.NullTime': 'TIMESTAMP',
    'datatypes.JSON': 'JSON',
    'datatypes.Date': 'DATE',
    'datatypes.Time': 'TIME',
    'uuid.UUID': 'UUID',
    'byte': 'TINYINT',
    '[]byte': 'BLOB',
}


def _snake_case(name: str) -> str:
    """Convert CamelCase/PascalCase to snake_case."""
    s1 = re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1_\2', name)
    s2 = re.sub(r'([a-z\d])([A-Z])', r'\1_\2', s1)
    return s2.lower()


def _pluralize_simple(name: str) -> str:
    """Very basic pluralization for GORM table name convention."""
    if name.endswith('y') and name[-2:] not in ('ay', 'ey', 'oy', 'uy'):
        return name[:-1] + 'ies'
    if name.endswith(('s', 'ss', 'sh', 'ch', 'x', 'z')):
        return name + 'es'
    return name + 's'


def _go_type_to_sql(go_type: str) -> str:
    """Map a Go type string to a SQL type."""
    # Strip pointer prefix
    clean = go_type.lstrip('*')

    # Direct lookup
    if clean in _GO_TYPE_MAP:
        return _GO_TYPE_MAP[clean]

    # Check for slice types
    if clean.startswith('[]'):
        inner = clean[2:]
        if inner == 'byte':
            return 'BLOB'
        return 'JSON'  # slices often stored as JSON

    # Package-qualified types
    if '.' in clean:
        if clean in _GO_TYPE_MAP:
            return _GO_TYPE_MAP[clean]
        # Unknown package type, default to VARCHAR
        return 'VARCHAR'

    return 'VARCHAR'


def _is_relation_type(go_type: str) -> bool:
    """Check if a Go type likely represents a GORM relationship (struct or slice of structs)."""
    clean = go_type.lstrip('*')
    # Slice of structs: []Post, []*Post
    if clean.startswith('[]'):
        inner = clean[2:].lstrip('*')
        # Primitive slices are not relationships
        if inner.lower() in _GO_TYPE_MAP or inner == 'byte':
            return False
        # Uppercase first letter = struct
        return inner[:1].isupper() if inner else False
    # Single struct reference (not a primitive, not a known type)
    if clean[:1].isupper() and clean not in ('string',) and '.' not in clean:
        if clean.lower() not in _GO_TYPE_MAP:
            return True
    return False


class GORMParser(BaseSchemaParser):
    """Parse Go GORM struct definitions to extract database schema."""

    FILE_EXTENSIONS = ['.go']

    def parse(self, project_path: str) -> Dict:
        """Parse GORM model structs from Go source files.

        Returns:
            Standardized schema dict with tables and relationships.
        """
        tables: List[Dict] = []
        relationships: List[Dict] = []

        go_files = find_source_files(project_path, ['.go'])

        for fpath in go_files:
            content = read_file_safe(fpath)
            if not content:
                continue

            parsed_tables, parsed_rels = self._parse_file(content, fpath)
            tables.extend(parsed_tables)
            relationships.extend(parsed_rels)

        # If no explicit relationships, derive from foreign keys
        if not relationships:
            relationships = self._detect_relationships(tables)

        return self.make_schema_result(tables, relationships)

    def _parse_file(self, content: str, file_path: str) -> Tuple[List[Dict], List[Dict]]:
        """Parse a single Go file for GORM structs."""
        stripped = strip_comments_only(content, 'go')
        tables: List[Dict] = []
        relationships: List[Dict] = []

        for match in _STRUCT_RE.finditer(stripped):
            struct_name = match.group(1)
            struct_start = match.end()

            # Extract the struct body (between { and })
            body = self._extract_struct_body(stripped, struct_start - 1)
            if not body:
                continue

            # Check if this looks like a GORM model
            has_gorm_tags = bool(_GORM_TAG_RE.search(body))
            has_gorm_model = bool(_GORM_MODEL_RE.search(body))
            if not has_gorm_tags and not has_gorm_model:
                continue

            # GORM table name convention: snake_case + plural
            table_name = _pluralize_simple(_snake_case(struct_name))

            columns, fks, rels = self._parse_struct_fields(
                body, struct_name, table_name, file_path
            )

            # gorm.Model adds standard columns
            if has_gorm_model:
                gorm_model_cols = [
                    {
                        'name': 'id',
                        'type': 'BIGINT',
                        'nullable': False,
                        'primary_key': True,
                        'unique': True,
                        'auto_increment': True,
                    },
                    {
                        'name': 'created_at',
                        'type': 'TIMESTAMP',
                        'nullable': True,
                        'primary_key': False,
                        'unique': False,
                    },
                    {
                        'name': 'updated_at',
                        'type': 'TIMESTAMP',
                        'nullable': True,
                        'primary_key': False,
                        'unique': False,
                    },
                    {
                        'name': 'deleted_at',
                        'type': 'TIMESTAMP',
                        'nullable': True,
                        'primary_key': False,
                        'unique': False,
                    },
                ]
                columns = gorm_model_cols + columns

            indexes = self._extract_indexes(columns)

            tables.append({
                'name': table_name,
                'columns': columns,
                'foreign_keys': fks,
                'indexes': indexes,
                'source_file': file_path,
                'line_number': line_number_at(content, match.start()),
                'struct_name': struct_name,
            })
            relationships.extend(rels)

        return tables, relationships

    def _extract_struct_body(self, content: str, brace_pos: int) -> Optional[str]:
        """Extract the body between { and } for a struct definition."""
        depth = 0
        body_start = -1

        for i in range(brace_pos, len(content)):
            ch = content[i]
            if ch == '{':
                if depth == 0:
                    body_start = i + 1
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    return content[body_start:i]

        return None

    def _parse_struct_fields(self, body: str, struct_name: str,
                             table_name: str,
                             file_path: str) -> Tuple[List[Dict], List[Dict], List[Dict]]:
        """Parse struct fields into columns, foreign keys, and relationships."""
        columns: List[Dict] = []
        foreign_keys: List[Dict] = []
        relationships: List[Dict] = []

        for match in _FIELD_RE.finditer(body):
            field_name = match.group(1)
            field_type = match.group(2)
            tags = match.group(3) or ''

            # Skip unexported fields (lowercase first letter)
            if field_name[0].islower():
                continue

            # Skip embedded gorm.Model (handled separately)
            if field_name == 'gorm' and field_type == '.Model':
                continue

            # Parse GORM tag
            gorm_tag_match = _GORM_TAG_RE.search(tags)
            gorm_tag = gorm_tag_match.group(1) if gorm_tag_match else ''

            # Check if this is a relationship field
            if _is_relation_type(field_type) or _FK_TAG_RE.search(gorm_tag):
                rel_info = self._parse_relationship_field(
                    field_name, field_type, gorm_tag,
                    struct_name, table_name, file_path
                )
                if rel_info:
                    relationships.append(rel_info)

                # Relationship fields with foreignKey also need the FK column
                fk_match = _FK_TAG_RE.search(gorm_tag)
                if fk_match and _is_relation_type(field_type):
                    # The FK column itself is usually declared as a separate field
                    pass
                continue

            # Regular column
            column = self._parse_column_field(field_name, field_type, gorm_tag)
            columns.append(column)

            # Check for foreign key pattern (e.g., DeptID with column:department_id)
            col_name = column['name']
            if col_name.endswith('_id'):
                ref_name = col_name[:-3]
                ref_table = _pluralize_simple(ref_name)
                foreign_keys.append({
                    'column': col_name,
                    'references_table': ref_table,
                    'references_column': 'id',
                })

        return columns, foreign_keys, relationships

    def _parse_column_field(self, field_name: str, field_type: str,
                            gorm_tag: str) -> Dict:
        """Parse a regular struct field into a column definition."""
        # Column name: from tag or derived from field name
        col_match = _COLUMN_TAG_RE.search(gorm_tag)
        if col_match:
            col_name = col_match.group(1)
        else:
            col_name = _snake_case(field_name)

        # Column type: from tag or derived from Go type
        type_match = _TYPE_TAG_RE.search(gorm_tag)
        if type_match:
            col_type = type_match.group(1).strip().upper()
        else:
            col_type = _go_type_to_sql(field_type)

        # Nullable: pointer types are nullable, or explicit in tag
        is_pointer = field_type.startswith('*')
        nullable = is_pointer or not _NOT_NULL_TAG_RE.search(gorm_tag)
        if _NOT_NULL_TAG_RE.search(gorm_tag):
            nullable = False

        # Primary key
        primary_key = bool(_PRIMARY_KEY_TAG_RE.search(gorm_tag))

        # Unique
        unique = bool(_UNIQUE_TAG_RE.search(gorm_tag))

        # Default
        default_match = _DEFAULT_TAG_RE.search(gorm_tag)
        default_val = default_match.group(1).strip() if default_match else None

        # Auto increment
        auto_inc = bool(_AUTOINCREMENT_TAG_RE.search(gorm_tag))

        column: Dict = {
            'name': col_name,
            'type': col_type,
            'nullable': nullable,
            'primary_key': primary_key,
            'unique': unique,
        }
        if default_val is not None:
            column['default'] = default_val
        if auto_inc:
            column['auto_increment'] = True

        return column

    def _parse_relationship_field(self, field_name: str, field_type: str,
                                  gorm_tag: str, struct_name: str,
                                  table_name: str,
                                  file_path: str) -> Optional[Dict]:
        """Parse a relationship field."""
        clean_type = field_type.lstrip('*')
        is_slice = clean_type.startswith('[]')

        if is_slice:
            related_type = clean_type[2:].lstrip('*')
            rel_type = 'one-to-many'
        else:
            related_type = clean_type
            rel_type = 'many-to-one'

        related_table = _pluralize_simple(_snake_case(related_type))

        # Check for foreignKey in tag
        fk_match = _FK_TAG_RE.search(gorm_tag)
        fk_column = _snake_case(fk_match.group(1)) if fk_match else None

        return {
            'from': table_name,
            'to': related_table,
            'type': rel_type,
            'foreign_key': fk_column,
            'source_struct': struct_name,
            'source_file': file_path,
        }

    def _extract_indexes(self, columns: List[Dict]) -> List[Dict]:
        """Extract indexes from column definitions."""
        indexes: List[Dict] = []
        for col in columns:
            if col.get('unique') and not col.get('primary_key'):
                indexes.append({
                    'columns': [col['name']],
                    'unique': True,
                })
        return indexes
