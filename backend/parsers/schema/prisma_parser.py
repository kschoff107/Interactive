"""
Prisma Schema Parser - Extract database schema from .prisma files.

Uses line-by-line DSL parsing (not regex on full content) to handle
Prisma's block-structured format: model, enum, datasource, generator blocks.
"""

import logging
import os
import re
from typing import Dict, List, Optional, Tuple

from ..base import BaseSchemaParser, find_source_files, read_file_safe

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Compiled regex patterns
# ---------------------------------------------------------------------------

# Block openers: model User { / enum Role {
_RE_MODEL_BLOCK = re.compile(r'^\s*model\s+(\w+)\s*\{')
_RE_ENUM_BLOCK = re.compile(r'^\s*enum\s+(\w+)\s*\{')

# Field line inside a model block:
#   name  Type?  @id @default(autoincrement()) @relation(...)
_RE_FIELD = re.compile(
    r'^\s*(\w+)\s+'           # field name
    r'(\w+)(\?)?(\[\])?'      # type, optional?, list?
    r'(.*)'                   # rest of the line (decorators)
)

# Decorator patterns (applied to the "rest" portion of a field line)
_RE_AT_ID = re.compile(r'@id\b')
_RE_AT_UNIQUE = re.compile(r'@unique\b')
_RE_AT_DEFAULT = re.compile(r'@default\(([^)]*)\)')
_RE_AT_UPDATEDAT = re.compile(r'@updatedAt\b')
_RE_AT_MAP = re.compile(r'@map\("([^"]*)"\)')
_RE_AT_RELATION = re.compile(
    r'@relation\('
    r'(?:[^)]*?fields:\s*\[([^\]]*)\])?'   # fields: [col, ...]
    r'(?:[^)]*?references:\s*\[([^\]]*)\])?' # references: [col, ...]
    r'[^)]*\)'
)

# @@map("table_name") on model level
_RE_TABLE_MAP = re.compile(r'^\s*@@map\("([^"]*)"\)')

# Enum value line (simple identifier, possibly with @map)
_RE_ENUM_VALUE = re.compile(r'^\s*(\w+)')

# Single-line comment
_RE_COMMENT = re.compile(r'//.*$')


class PrismaParser(BaseSchemaParser):
    """Parse Prisma schema files (.prisma) into standardized schema format."""

    FILE_EXTENSIONS = ['.prisma']

    def parse(self, project_path: str) -> Dict:
        """Parse all .prisma files in project_path and return schema dict."""
        files = self.find_files(project_path)
        all_tables: List[Dict] = []
        all_enums: List[Dict] = []
        all_relationships: List[Dict] = []

        for fpath in files:
            content = read_file_safe(fpath)
            if not content:
                continue
            try:
                tables, enums, rels = self._parse_content(content, fpath)
                all_tables.extend(tables)
                all_enums.extend(enums)
                all_relationships.extend(rels)
            except Exception as e:
                logger.warning("Failed to parse %s: %s", fpath, e)
                continue

        # Also derive implicit relationships from foreign key columns
        implicit_rels = self._detect_relationships(all_tables)
        # Merge, avoiding duplicates (handle both from/to and from_table/to_table keys)
        existing = {
            (r.get('from_table') or r.get('from', ''),
             r.get('to_table') or r.get('to', ''))
            for r in all_relationships
        }
        for r in implicit_rels:
            key = (r.get('from_table') or r.get('from', ''),
                   r.get('to_table') or r.get('to', ''))
            if key not in existing:
                all_relationships.append(r)

        result = self.make_schema_result(all_tables, all_relationships)
        if all_enums:
            result['enums'] = all_enums
        return result

    # ------------------------------------------------------------------
    # Internal parsing
    # ------------------------------------------------------------------

    def _parse_content(
        self, content: str, file_path: str
    ) -> Tuple[List[Dict], List[Dict], List[Dict]]:
        """Parse a single .prisma file and return (tables, enums, relationships)."""
        tables: List[Dict] = []
        enums: List[Dict] = []
        relationships: List[Dict] = []

        lines = content.splitlines()
        i = 0
        while i < len(lines):
            line = _RE_COMMENT.sub('', lines[i])  # strip inline comments

            # --- model block ---
            m = _RE_MODEL_BLOCK.match(line)
            if m:
                model_name = m.group(1)
                block_lines, end_i = self._collect_block(lines, i)
                table, rels = self._parse_model(model_name, block_lines, file_path)
                tables.append(table)
                relationships.extend(rels)
                i = end_i + 1
                continue

            # --- enum block ---
            m = _RE_ENUM_BLOCK.match(line)
            if m:
                enum_name = m.group(1)
                block_lines, end_i = self._collect_block(lines, i)
                enums.append(self._parse_enum(enum_name, block_lines, file_path))
                i = end_i + 1
                continue

            i += 1

        return tables, enums, relationships

    @staticmethod
    def _collect_block(lines: List[str], start: int) -> Tuple[List[str], int]:
        """Collect lines from opening '{' to matching '}', return (body_lines, end_index)."""
        depth = 0
        body: List[str] = []
        for i in range(start, len(lines)):
            stripped = _RE_COMMENT.sub('', lines[i])
            if '{' in stripped:
                depth += stripped.count('{')
            if '}' in stripped:
                depth -= stripped.count('}')
                if depth <= 0:
                    return body, i
            # Only add lines *after* the opening line
            if i > start:
                body.append(stripped)
        return body, len(lines) - 1

    def _parse_model(
        self, model_name: str, body_lines: List[str], file_path: str
    ) -> Tuple[Dict, List[Dict]]:
        """Parse a model block body into a table dict and relationship list."""
        columns: List[Dict] = []
        foreign_keys: List[Dict] = []
        relationships: List[Dict] = []
        table_mapped_name: Optional[str] = None

        for line in body_lines:
            line = line.strip()
            if not line or line.startswith('//') or line.startswith('}'):
                continue

            # @@map on model level
            tm = _RE_TABLE_MAP.match(line)
            if tm:
                table_mapped_name = tm.group(1)
                continue

            # Skip @@index, @@unique, @@id lines
            if line.startswith('@@'):
                continue

            fm = _RE_FIELD.match(line)
            if not fm:
                continue

            field_name = fm.group(1)
            field_type = fm.group(2)
            is_optional = fm.group(3) is not None
            is_list = fm.group(4) is not None
            rest = fm.group(5) or ''

            is_id = bool(_RE_AT_ID.search(rest))
            is_unique = bool(_RE_AT_UNIQUE.search(rest))
            default_match = _RE_AT_DEFAULT.search(rest)
            default_value = default_match.group(1) if default_match else None

            column = {
                'name': field_name,
                'type': field_type,
                'nullable': is_optional,
                'primary_key': is_id,
                'unique': is_unique or is_id,
                'is_list': is_list,
            }
            if default_value is not None:
                column['default'] = default_value

            # Check for @map("col_name")
            map_match = _RE_AT_MAP.search(rest)
            if map_match:
                column['mapped_name'] = map_match.group(1)

            # Check for @relation -> foreign key
            rel_match = _RE_AT_RELATION.search(rest)
            if rel_match:
                fields_str = rel_match.group(1)
                refs_str = rel_match.group(2)
                if fields_str and refs_str:
                    fk_cols = [c.strip() for c in fields_str.split(',')]
                    ref_cols = [c.strip() for c in refs_str.split(',')]
                    for fk_col, ref_col in zip(fk_cols, ref_cols):
                        foreign_keys.append({
                            'column': fk_col,
                            'references_table': field_type,
                            'references_column': ref_col,
                        })
                # Record relationship regardless
                rel_type = 'one-to-many' if is_list else 'many-to-one'
                relationships.append({
                    'from': model_name,
                    'to': field_type,
                    'type': rel_type,
                    'field': field_name,
                })
            elif is_list and field_type[0].isupper():
                # Implicit relation list (no explicit @relation)
                relationships.append({
                    'from': model_name,
                    'to': field_type,
                    'type': 'one-to-many',
                    'field': field_name,
                })

            columns.append(column)

        actual_name = table_mapped_name or model_name
        table = {
            'name': actual_name,
            'model_name': model_name,
            'columns': columns,
            'foreign_keys': foreign_keys,
            'indexes': [],
            'file_path': file_path,
        }
        return table, relationships

    @staticmethod
    def _parse_enum(enum_name: str, body_lines: List[str], file_path: str) -> Dict:
        """Parse an enum block body into an enum dict."""
        values: List[str] = []
        for line in body_lines:
            line = line.strip()
            if not line or line.startswith('//') or line.startswith('}'):
                continue
            m = _RE_ENUM_VALUE.match(line)
            if m:
                values.append(m.group(1))
        return {
            'name': enum_name,
            'values': values,
            'file_path': file_path,
        }
