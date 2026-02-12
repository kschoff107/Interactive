"""
Mongoose Parser - Extract database schema from Mongoose model definitions.

Handles:
  - new Schema({ ... }) or new mongoose.Schema({ ... })
  - mongoose.model('Name', schema)
  - Field types, required, unique, ref (foreign keys)

Note: We run regex on original content (with only line comments stripped)
because strip_comments replaces string literals with whitespace, preventing
extraction of model names, ref targets, and enum values.
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
)

# ---------------------------------------------------------------------------
# Compiled regex patterns
# ---------------------------------------------------------------------------

# Single-line comment for manual stripping (preserves string literals)
_RE_LINE_COMMENT = re.compile(r'//[^\n]*')

# Schema variable assignment: const xxxSchema = new Schema({ or new mongoose.Schema({
_RE_SCHEMA_ASSIGN = re.compile(
    r"""(?:const|let|var)\s+(\w+)\s*=\s*new\s+(?:mongoose\.)?Schema\s*\(""",
)

# Model registration: mongoose.model('Name', schemaVar) or const X = mongoose.model('Name', schema)
_RE_MODEL_REGISTER = re.compile(
    r"""(?:mongoose\.model|model)\s*\(\s*['"](\w+)['"]\s*,\s*(\w+)""",
)

# Export with model: module.exports = mongoose.model('Name', schema)
_RE_EXPORT_MODEL = re.compile(
    r"""(?:module\.exports|export\s+default)\s*=\s*(?:mongoose\.)?model\s*\(\s*['"](\w+)['"]\s*,\s*(\w+)""",
)

# const X = mongoose.model('Name', schema)
_RE_CONST_MODEL = re.compile(
    r"""(?:const|let|var)\s+\w+\s*=\s*(?:mongoose\.)?model\s*\(\s*['"](\w+)['"]\s*,\s*(\w+)""",
)

# Field as shorthand type:  fieldName: String  or  fieldName: Number
_RE_FIELD_SHORTHAND_TYPE = re.compile(
    r'(\w+)\s*:\s*(String|Number|Boolean|Date|ObjectId|Buffer|Mixed|Map|Schema\.Types\.\w+)\b',
)

# Field as object:  fieldName: { ... }
_RE_FIELD_OBJECT = re.compile(
    r'(\w+)\s*:\s*\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}',
)

# Field as array of refs:  fieldName: [{ type: ..., ref: ... }]
_RE_FIELD_ARRAY = re.compile(
    r'(\w+)\s*:\s*\[\s*\{([^}]+)\}\s*\]',
)

# Field as array shorthand:  fieldName: [String]
_RE_FIELD_ARRAY_SHORTHAND = re.compile(
    r'(\w+)\s*:\s*\[(String|Number|Boolean|Date|ObjectId|Schema\.Types\.\w+)\]',
)

# Inside field objects
_RE_TYPE = re.compile(
    r'type\s*:\s*(String|Number|Boolean|Date|ObjectId|Buffer|Mixed|Map|Schema\.Types\.\w+)\b',
)
_RE_REQUIRED = re.compile(r'required\s*:\s*(true|false)', re.IGNORECASE)
_RE_UNIQUE = re.compile(r'unique\s*:\s*(true|false)', re.IGNORECASE)
_RE_DEFAULT = re.compile(r"""default\s*:\s*([^,}\]]+)""")
_RE_REF = re.compile(r"""ref\s*:\s*['"](\w+)['"]""")
_RE_ENUM = re.compile(r"""enum\s*:\s*\[([^\]]+)\]""")

# Mongoose type -> SQL-like type mapping (for visualization)
_MONGOOSE_TYPE_MAP = {
    'String': 'VARCHAR',
    'Number': 'INTEGER',
    'Boolean': 'BOOLEAN',
    'Date': 'TIMESTAMP',
    'ObjectId': 'OBJECT_ID',
    'Buffer': 'BINARY',
    'Mixed': 'JSON',
    'Map': 'JSON',
    'Schema.Types.ObjectId': 'OBJECT_ID',
    'Schema.Types.Mixed': 'JSON',
}


class MongooseParser(BaseSchemaParser):
    """Parse Mongoose schema definitions into standardized schema format."""

    FILE_EXTENSIONS = ['.js', '.ts']

    def parse(self, project_path: str) -> Dict:
        """Parse all Mongoose model files in project_path."""
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

        return self.make_schema_result(all_tables, all_relationships)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _parse_file(
        self, content: str, file_path: str
    ) -> Tuple[List[Dict], List[Dict]]:
        """Parse a single JS/TS file for Mongoose schemas and models.

        Uses original content with only line comments stripped so that
        string literals (model names, ref targets) are preserved.
        """
        cleaned = _RE_LINE_COMMENT.sub('', content)
        tables: List[Dict] = []
        relationships: List[Dict] = []

        # Map schema variable names to their parsed info
        schema_vars: Dict[str, Dict] = {}

        # Find all schema definitions
        for m in _RE_SCHEMA_ASSIGN.finditer(cleaned):
            var_name = m.group(1)
            # Extract the schema body (first arg to new Schema())
            body, bs, be = extract_block_body(cleaned, m.end() - 1)
            if bs < 0:
                continue
            columns, fks, rels = self._parse_schema_body(body)
            schema_vars[var_name] = {
                'columns': columns,
                'foreign_keys': fks,
                'line_number': line_number_at(content, m.start()),
            }
            relationships.extend(rels)

        # Map schemas to model names via mongoose.model() calls
        model_map: Dict[str, str] = {}  # schema_var -> model_name
        for m in _RE_MODEL_REGISTER.finditer(cleaned):
            model_name = m.group(1)
            schema_var = m.group(2)
            model_map[schema_var] = model_name

        for m in _RE_EXPORT_MODEL.finditer(cleaned):
            model_name = m.group(1)
            schema_var = m.group(2)
            model_map[schema_var] = model_name

        for m in _RE_CONST_MODEL.finditer(cleaned):
            model_name = m.group(1)
            schema_var = m.group(2)
            model_map[schema_var] = model_name

        # Build tables from matched schemas
        for var_name, info in schema_vars.items():
            model_name = model_map.get(var_name)
            if not model_name:
                # Guess from variable name: userSchema -> User
                model_name = self._guess_model_name(var_name)
            collection_name = self._to_collection_name(model_name)

            # Add implicit _id column (MongoDB always has one)
            has_id = any(c['name'] == '_id' for c in info['columns'])
            if not has_id:
                info['columns'].insert(0, {
                    'name': '_id',
                    'type': 'OBJECT_ID',
                    'nullable': False,
                    'primary_key': True,
                    'unique': True,
                })

            # Fix '<current>' placeholders in relationships
            for rel in relationships:
                if rel['from'] == '<current>':
                    # Check if this relationship came from fields in this schema
                    for fk in info['foreign_keys']:
                        if fk['column'] == rel.get('field'):
                            rel['from'] = model_name
                            break

            tables.append({
                'name': collection_name,
                'model_name': model_name,
                'columns': info['columns'],
                'foreign_keys': info['foreign_keys'],
                'indexes': [],
                'file_path': file_path,
                'line_number': info['line_number'],
            })

        # Final pass: fix any remaining '<current>' placeholders
        for rel in relationships:
            if rel['from'] == '<current>':
                rel['from'] = 'Unknown'

        return tables, relationships

    def _parse_schema_body(
        self, body: str
    ) -> Tuple[List[Dict], List[Dict], List[Dict]]:
        """Parse the fields object of a Schema definition."""
        columns: List[Dict] = []
        foreign_keys: List[Dict] = []
        relationships: List[Dict] = []
        seen_fields: set = set()

        # --- Array of refs: fieldName: [{ type: ObjectId, ref: 'Model' }] ---
        for m in _RE_FIELD_ARRAY.finditer(body):
            field_name = m.group(1)
            inner = m.group(2)
            seen_fields.add(field_name)
            type_m = _RE_TYPE.search(inner)
            mongoose_type = type_m.group(1) if type_m else 'Mixed'
            sql_type = _MONGOOSE_TYPE_MAP.get(mongoose_type, mongoose_type)
            ref_m = _RE_REF.search(inner)
            col = {
                'name': field_name,
                'type': f'ARRAY<{sql_type}>',
                'nullable': True,
                'primary_key': False,
                'unique': False,
                'is_array': True,
            }
            if ref_m:
                ref_model = ref_m.group(1)
                col['ref'] = ref_model
                foreign_keys.append({
                    'column': field_name,
                    'references_table': self._to_collection_name(ref_model),
                    'references_column': '_id',
                })
                relationships.append({
                    'from': '<current>',
                    'to': ref_model,
                    'type': 'many-to-many',
                    'field': field_name,
                })
            columns.append(col)

        # --- Array shorthand: fieldName: [String] ---
        for m in _RE_FIELD_ARRAY_SHORTHAND.finditer(body):
            field_name = m.group(1)
            if field_name in seen_fields:
                continue
            seen_fields.add(field_name)
            mongoose_type = m.group(2)
            sql_type = _MONGOOSE_TYPE_MAP.get(mongoose_type, mongoose_type)
            columns.append({
                'name': field_name,
                'type': f'ARRAY<{sql_type}>',
                'nullable': True,
                'primary_key': False,
                'unique': False,
                'is_array': True,
            })

        # --- Object-style fields: fieldName: { type: ..., ... } ---
        for m in _RE_FIELD_OBJECT.finditer(body):
            field_name = m.group(1)
            if field_name in seen_fields:
                continue
            seen_fields.add(field_name)
            field_body = m.group(2)

            type_m = _RE_TYPE.search(field_body)
            if not type_m:
                continue
            mongoose_type = type_m.group(1)
            sql_type = _MONGOOSE_TYPE_MAP.get(mongoose_type, mongoose_type)

            required = self._extract_bool(field_body, _RE_REQUIRED, default=False)
            unique = self._extract_bool(field_body, _RE_UNIQUE, default=False)

            col: Dict = {
                'name': field_name,
                'type': sql_type,
                'nullable': not required,
                'primary_key': False,
                'unique': unique,
            }

            default_m = _RE_DEFAULT.search(field_body)
            if default_m:
                col['default'] = default_m.group(1).strip()

            enum_m = _RE_ENUM.search(field_body)
            if enum_m:
                col['enum_values'] = [
                    v.strip().strip("'\"")
                    for v in enum_m.group(1).split(',')
                ]

            ref_m = _RE_REF.search(field_body)
            if ref_m:
                ref_model = ref_m.group(1)
                col['ref'] = ref_model
                foreign_keys.append({
                    'column': field_name,
                    'references_table': self._to_collection_name(ref_model),
                    'references_column': '_id',
                })
                relationships.append({
                    'from': '<current>',
                    'to': ref_model,
                    'type': 'many-to-one',
                    'field': field_name,
                })

            columns.append(col)

        # --- Shorthand fields: fieldName: String ---
        for m in _RE_FIELD_SHORTHAND_TYPE.finditer(body):
            field_name = m.group(1)
            if field_name in seen_fields or field_name == 'type':
                continue
            seen_fields.add(field_name)
            mongoose_type = m.group(2)
            sql_type = _MONGOOSE_TYPE_MAP.get(mongoose_type, mongoose_type)
            columns.append({
                'name': field_name,
                'type': sql_type,
                'nullable': True,
                'primary_key': False,
                'unique': False,
            })

        return columns, foreign_keys, relationships

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
    def _guess_model_name(var_name: str) -> str:
        """Guess model name from schema variable: userSchema -> User."""
        name = re.sub(r'[Ss]chema$', '', var_name)
        if name:
            return name[0].upper() + name[1:]
        return var_name

    @staticmethod
    def _to_collection_name(model_name: str) -> str:
        """Convert model name to MongoDB collection name (lowercase plural)."""
        name = model_name.lower()
        if not name.endswith('s'):
            name += 's'
        return name
