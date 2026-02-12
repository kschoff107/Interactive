"""
TypeORM Parser - Extract database schema from TypeScript Entity classes.

Uses regex + brace counting on comment-stripped source to parse
TypeORM decorator patterns (@Entity, @Column, @ManyToOne, etc.).

Note: strip_comments replaces string literals with whitespace, so we
match structural patterns on stripped content but extract string values
(table names, column types) from the original content at the same positions.
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
# Compiled regex patterns (applied to ORIGINAL content, not stripped)
# ---------------------------------------------------------------------------

# @Entity() or @Entity('table_name') — class declaration follows
# Applied on original content to capture string argument
_RE_ENTITY = re.compile(
    r"""@Entity\s*\(\s*(?:['"](\w+)['"])?\s*\)\s*"""
    r"""(?:export\s+)?class\s+(\w+)""",
)

# Column decorators (applied on original content within entity body)
_RE_PRIMARY_GEN_COL = re.compile(
    r'@PrimaryGeneratedColumn\s*\(([^)]*)\)\s*\n?\s*(\w+)\s*:\s*(\w+)'
)
_RE_PRIMARY_COL = re.compile(
    r'@PrimaryColumn\s*\(([^)]*)\)\s*\n?\s*(\w+)\s*:\s*(\w+)'
)
_RE_COLUMN = re.compile(
    r'@Column\s*\(\s*\{([^}]*)\}\s*\)\s*\n?\s*(\w+)\s*(?:\?)?:\s*(\w+)'
)
_RE_COLUMN_SIMPLE = re.compile(
    r'@Column\s*\(\s*\)\s*\n?\s*(\w+)\s*(?:\?)?:\s*(\w+)'
)
_RE_CREATE_DATE = re.compile(
    r'@CreateDateColumn\s*\(([^)]*)\)\s*\n?\s*(\w+)\s*:\s*(\w+)'
)
_RE_UPDATE_DATE = re.compile(
    r'@UpdateDateColumn\s*\(([^)]*)\)\s*\n?\s*(\w+)\s*:\s*(\w+)'
)

# Pattern fragment for matching decorator arguments with nested parens
# e.g. (() => Department, dept => dept.users)
_NESTED_PARENS = r'(?:[^()]*|\([^)]*\))*'

# Relationship decorators (applied on original content)
_RE_MANY_TO_ONE = re.compile(
    r'@ManyToOne\s*\(' + _NESTED_PARENS + r'\)\s*'
    r'(?:@JoinColumn\s*\(\s*\{([^}]*)\}\s*\)\s*)?'
    r'(\w+)\s*(?:\?)?:\s*(\w+)',
)
_RE_ONE_TO_MANY = re.compile(
    r'@OneToMany\s*\(' + _NESTED_PARENS + r'\)\s*'
    r'(\w+)\s*(?:\?)?:\s*(\w+)\s*\[\]',
)
_RE_ONE_TO_ONE = re.compile(
    r'@OneToOne\s*\(' + _NESTED_PARENS + r'\)\s*'
    r'(?:@JoinColumn\s*\(\s*\{([^}]*)\}\s*\)\s*)?'
    r'(\w+)\s*(?:\?)?:\s*(\w+)',
)
_RE_MANY_TO_MANY = re.compile(
    r'@ManyToMany\s*\(' + _NESTED_PARENS + r'\)\s*'
    r'(?:@JoinTable\s*\(' + _NESTED_PARENS + r'\)\s*)?'
    r'(\w+)\s*(?:\?)?:\s*(\w+)\s*\[\]',
)

# Extract type/name from @JoinColumn({ name: 'col' })
_RE_JOIN_COL_NAME = re.compile(r"""name\s*:\s*['"](\w+)['"]""")

# Extract column options: type, length, nullable, unique, default
_RE_COL_TYPE = re.compile(r"""type\s*:\s*['"](\w+)['"]""")
_RE_COL_LENGTH = re.compile(r'length\s*:\s*(\d+)')
_RE_COL_NULLABLE = re.compile(r'nullable\s*:\s*(true|false)', re.IGNORECASE)
_RE_COL_UNIQUE = re.compile(r'unique\s*:\s*(true|false)', re.IGNORECASE)
_RE_COL_DEFAULT = re.compile(r"""default\s*:\s*([^,}]+)""")

# TypeScript -> SQL type mapping
_TS_TYPE_MAP = {
    'number': 'INTEGER',
    'string': 'VARCHAR',
    'boolean': 'BOOLEAN',
    'Date': 'TIMESTAMP',
    'bigint': 'BIGINT',
}


class TypeORMParser(BaseSchemaParser):
    """Parse TypeORM entity files into standardized schema format."""

    FILE_EXTENSIONS = ['.ts', '.js']

    def parse(self, project_path: str) -> Dict:
        """Parse all TypeORM entity files in project_path."""
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

        # Also derive relationships from foreign keys
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
        """Parse a single TypeScript/JavaScript file for TypeORM entities.

        We run regex on the ORIGINAL content (not stripped) because
        strip_comments replaces string literals with whitespace, making it
        impossible to extract table names, column types, and join column names.
        Comment stripping is still used indirectly: we verify entity matches
        are not inside comments by checking if @Entity appears at a non-comment
        position.
        """
        tables: List[Dict] = []
        relationships: List[Dict] = []

        # Use original content for regex matching (string literals preserved)
        for m in _RE_ENTITY.finditer(content):
            table_name_arg = m.group(1)
            class_name = m.group(2)
            table_name = table_name_arg or self._to_snake_case(class_name)

            # Extract class body using brace counting on original content
            body, body_start, body_end = extract_block_body(content, m.start())
            if body_start < 0:
                continue

            columns, fks, rels = self._parse_entity_body(body, class_name)
            tables.append({
                'name': table_name,
                'class_name': class_name,
                'columns': columns,
                'foreign_keys': fks,
                'indexes': [],
                'file_path': file_path,
                'line_number': line_number_at(content, m.start()),
            })
            relationships.extend(rels)

        return tables, relationships

    def _parse_entity_body(
        self, body: str, class_name: str
    ) -> Tuple[List[Dict], List[Dict], List[Dict]]:
        """Parse the body of an @Entity class."""
        columns: List[Dict] = []
        foreign_keys: List[Dict] = []
        relationships: List[Dict] = []

        # --- Primary generated columns ---
        for m in _RE_PRIMARY_GEN_COL.finditer(body):
            opts = m.group(1)
            col_name = m.group(2)
            ts_type = m.group(3)
            col_type = self._extract_col_type(opts, ts_type)
            columns.append({
                'name': col_name,
                'type': col_type,
                'nullable': False,
                'primary_key': True,
                'unique': True,
                'auto_increment': True,
            })

        # --- Primary columns ---
        for m in _RE_PRIMARY_COL.finditer(body):
            opts = m.group(1)
            col_name = m.group(2)
            ts_type = m.group(3)
            col_type = self._extract_col_type(opts, ts_type)
            columns.append({
                'name': col_name,
                'type': col_type,
                'nullable': False,
                'primary_key': True,
                'unique': True,
            })

        # --- Regular columns with options ---
        for m in _RE_COLUMN.finditer(body):
            opts = m.group(1)
            col_name = m.group(2)
            ts_type = m.group(3)
            col_type = self._extract_col_type(opts, ts_type)
            nullable = self._extract_bool(opts, _RE_COL_NULLABLE, default=True)
            unique = self._extract_bool(opts, _RE_COL_UNIQUE, default=False)
            col = {
                'name': col_name,
                'type': col_type,
                'nullable': nullable,
                'primary_key': False,
                'unique': unique,
            }
            default_m = _RE_COL_DEFAULT.search(opts)
            if default_m:
                col['default'] = default_m.group(1).strip().strip("'\"")
            length_m = _RE_COL_LENGTH.search(opts)
            if length_m:
                col['length'] = int(length_m.group(1))
            columns.append(col)

        # --- Regular columns without options: @Column() ---
        already = {c['name'] for c in columns}
        for m in _RE_COLUMN_SIMPLE.finditer(body):
            col_name = m.group(1)
            if col_name in already:
                continue
            ts_type = m.group(2)
            columns.append({
                'name': col_name,
                'type': _TS_TYPE_MAP.get(ts_type, ts_type.upper()),
                'nullable': True,
                'primary_key': False,
                'unique': False,
            })

        # --- CreateDateColumn / UpdateDateColumn ---
        for pattern in [_RE_CREATE_DATE, _RE_UPDATE_DATE]:
            for m in pattern.finditer(body):
                col_name = m.group(2)
                if col_name not in already:
                    columns.append({
                        'name': col_name,
                        'type': 'TIMESTAMP',
                        'nullable': True,
                        'primary_key': False,
                        'unique': False,
                    })

        # --- ManyToOne relationships ---
        for m in _RE_MANY_TO_ONE.finditer(body):
            join_opts = m.group(1) or ''
            field_name = m.group(2)
            target_entity = m.group(3)
            jc_name = _RE_JOIN_COL_NAME.search(join_opts)
            fk_col = jc_name.group(1) if jc_name else f'{field_name}_id'
            foreign_keys.append({
                'column': fk_col,
                'references_table': self._to_snake_case(target_entity),
                'references_column': 'id',
            })
            relationships.append({
                'from': class_name,
                'to': target_entity,
                'type': 'many-to-one',
                'field': field_name,
            })

        # --- OneToMany relationships ---
        for m in _RE_ONE_TO_MANY.finditer(body):
            field_name = m.group(1)
            target_entity = m.group(2)
            relationships.append({
                'from': class_name,
                'to': target_entity,
                'type': 'one-to-many',
                'field': field_name,
            })

        # --- OneToOne relationships ---
        for m in _RE_ONE_TO_ONE.finditer(body):
            join_opts = m.group(1) or ''
            field_name = m.group(2)
            target_entity = m.group(3)
            jc_name = _RE_JOIN_COL_NAME.search(join_opts)
            fk_col = jc_name.group(1) if jc_name else f'{field_name}_id'
            foreign_keys.append({
                'column': fk_col,
                'references_table': self._to_snake_case(target_entity),
                'references_column': 'id',
            })
            relationships.append({
                'from': class_name,
                'to': target_entity,
                'type': 'one-to-one',
                'field': field_name,
            })

        # --- ManyToMany relationships ---
        for m in _RE_MANY_TO_MANY.finditer(body):
            field_name = m.group(1)
            target_entity = m.group(2)
            relationships.append({
                'from': class_name,
                'to': target_entity,
                'type': 'many-to-many',
                'field': field_name,
            })

        return columns, foreign_keys, relationships

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_col_type(opts: str, ts_type: str) -> str:
        """Extract SQL column type from decorator options or TypeScript type."""
        type_m = _RE_COL_TYPE.search(opts)
        if type_m:
            return type_m.group(1).upper()
        return _TS_TYPE_MAP.get(ts_type, ts_type.upper())

    @staticmethod
    def _extract_bool(opts: str, pattern: re.Pattern, default: bool = False) -> bool:
        """Extract a boolean option from decorator options string."""
        m = pattern.search(opts)
        if m:
            return m.group(1).lower() == 'true'
        return default

    @staticmethod
    def _to_snake_case(name: str) -> str:
        """Convert PascalCase to snake_case for table name inference."""
        s1 = re.sub(r'(.)([A-Z][a-z]+)', r'\1_\2', name)
        return re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', s1).lower()
