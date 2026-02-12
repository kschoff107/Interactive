"""
Laravel Eloquent schema parser.

Parses Eloquent model files and Laravel migrations to extract database
schema and relationships using regex-based analysis.
"""

import os
import re
from pathlib import Path
from typing import Dict, List, Optional

from ..base import (
    BaseSchemaParser, find_source_files, read_file_safe,
    strip_comments, extract_block_body, line_number_at,
)

# Custom comment-only stripping for PHP that preserves string literals.
# The standard strip_comments('php') also removes strings, which destroys
# table names, column names, and other values we need to parse.
_PHP_COMMENT_ONLY_RE = re.compile(
    r'//[^\n]*'             # single-line //
    r'|#[^\n]*'             # single-line #
    r'|/\*.*?\*/',          # multi-line /* */
    re.DOTALL,
)


def _strip_php_comments_only(content: str) -> str:
    """Strip PHP comments while preserving string literals."""
    return _PHP_COMMENT_ONLY_RE.sub(
        lambda m: re.sub(r'[^\n]', ' ', m.group(0)),
        content,
    )

# ---------------------------------------------------------------------------
# Compiled regex patterns — Model parsing
# ---------------------------------------------------------------------------

# class User extends Model
_MODEL_CLASS_RE = re.compile(
    r'class\s+(\w+)\s+extends\s+(?:Model|Authenticatable|Pivot)',
    re.MULTILINE,
)

# protected $table = 'users';
_TABLE_NAME_RE = re.compile(
    r'protected\s+\$table\s*=\s*[\'"](\w+)[\'"]',
    re.MULTILINE,
)

# protected $fillable = ['name', 'email', 'password'];
_FILLABLE_RE = re.compile(
    r'protected\s+\$fillable\s*=\s*\[([^\]]*)\]',
    re.DOTALL,
)

# protected $casts = ['email_verified_at' => 'datetime', ...];
_CASTS_RE = re.compile(
    r'protected\s+\$casts\s*=\s*\[([^\]]*)\]',
    re.DOTALL,
)

# protected $hidden = ['password', 'remember_token'];
_HIDDEN_RE = re.compile(
    r'protected\s+\$hidden\s*=\s*\[([^\]]*)\]',
    re.DOTALL,
)

# String items in arrays: 'name' or "name"
_ARRAY_ITEM_RE = re.compile(r"['\"](\w+)['\"]")

# Cast entries: 'field' => 'type'
_CAST_ENTRY_RE = re.compile(r"['\"](\w+)['\"]\s*=>\s*['\"](\w+)['\"]")

# Relationship methods: return $this->hasMany(Post::class)
_RELATIONSHIP_RE = re.compile(
    r'return\s+\$this\s*->\s*(hasMany|hasOne|belongsTo|belongsToMany'
    r'|hasManyThrough|hasOneThrough|morphMany|morphOne|morphTo'
    r'|morphToMany|morphedByMany)\s*\(\s*(\w+)::class',
    re.MULTILINE,
)

# Function declaration for relationship methods
_FUNCTION_RE = re.compile(
    r'(?:public\s+)?function\s+(\w+)\s*\(\s*\)',
    re.MULTILINE,
)

# ---------------------------------------------------------------------------
# Compiled regex patterns — Migration parsing
# ---------------------------------------------------------------------------

# Schema::create('users', function (Blueprint $table) {
_SCHEMA_CREATE_RE = re.compile(
    r"Schema\s*::\s*create\s*\(\s*['\"](\w+)['\"]",
    re.MULTILINE,
)

# $table->string('name');  $table->integer('age')->nullable();
_MIGRATION_COL_RE = re.compile(
    r'\$\w+\s*->\s*(id|string|text|integer|bigInteger|smallInteger|tinyInteger'
    r'|float|double|decimal|boolean|date|dateTime|dateTimeTz|time|timeTz'
    r'|timestamp|timestampTz|binary|enum|json|jsonb|uuid|ipAddress'
    r'|macAddress|year|char|mediumText|longText|unsignedInteger'
    r'|unsignedBigInteger|unsignedSmallInteger|unsignedTinyInteger'
    r'|foreignId|foreignUuid|softDeletes|softDeletesTz|rememberToken'
    r'|timestamps|timestampsTz|nullableTimestamps|morphs|nullableMorphs)'
    r'(?:\s*\(\s*[\'"](\w+)[\'"](?:\s*,\s*[^\)]*?)?\s*\))?'
    r'((?:\s*->\s*\w+\s*\([^\)]*\))*)',
    re.MULTILINE,
)

# Chained methods: ->nullable(), ->unique(), ->default(value)
_NULLABLE_CHAIN_RE = re.compile(r'->\s*nullable\s*\(')
_UNIQUE_CHAIN_RE = re.compile(r'->\s*unique\s*\(')
_DEFAULT_CHAIN_RE = re.compile(r'->\s*default\s*\(\s*([^\)]+)\s*\)')
_CONSTRAINED_CHAIN_RE = re.compile(r'->\s*constrained\s*\(')

# Laravel type → SQL type mapping
_TYPE_MAP = {
    'id': 'BIGINT',
    'string': 'VARCHAR',
    'text': 'TEXT',
    'mediumText': 'MEDIUMTEXT',
    'longText': 'LONGTEXT',
    'char': 'CHAR',
    'integer': 'INTEGER',
    'bigInteger': 'BIGINT',
    'smallInteger': 'SMALLINT',
    'tinyInteger': 'TINYINT',
    'unsignedInteger': 'INTEGER',
    'unsignedBigInteger': 'BIGINT',
    'unsignedSmallInteger': 'SMALLINT',
    'unsignedTinyInteger': 'TINYINT',
    'float': 'FLOAT',
    'double': 'DOUBLE',
    'decimal': 'DECIMAL',
    'boolean': 'BOOLEAN',
    'date': 'DATE',
    'dateTime': 'DATETIME',
    'dateTimeTz': 'DATETIME',
    'time': 'TIME',
    'timeTz': 'TIME',
    'timestamp': 'TIMESTAMP',
    'timestampTz': 'TIMESTAMP',
    'binary': 'BLOB',
    'enum': 'ENUM',
    'json': 'JSON',
    'jsonb': 'JSONB',
    'uuid': 'UUID',
    'ipAddress': 'VARCHAR',
    'macAddress': 'VARCHAR',
    'year': 'YEAR',
    'foreignId': 'BIGINT',
    'foreignUuid': 'UUID',
    'rememberToken': 'VARCHAR',
}

# Eloquent relationship → schema relationship type
_REL_TYPE_MAP = {
    'hasMany': 'one-to-many',
    'hasOne': 'one-to-one',
    'belongsTo': 'many-to-one',
    'belongsToMany': 'many-to-many',
    'hasManyThrough': 'one-to-many',
    'hasOneThrough': 'one-to-one',
    'morphMany': 'one-to-many',
    'morphOne': 'one-to-one',
    'morphTo': 'many-to-one',
    'morphToMany': 'many-to-many',
    'morphedByMany': 'many-to-many',
}


def _pluralize_simple(name: str) -> str:
    """Very basic pluralization for Laravel table name convention."""
    if name.endswith('y') and name[-2:] not in ('ay', 'ey', 'oy', 'uy'):
        return name[:-1] + 'ies'
    if name.endswith(('s', 'sh', 'ch', 'x', 'z')):
        return name + 'es'
    return name + 's'


def _snake_case(name: str) -> str:
    """Convert CamelCase to snake_case."""
    s1 = re.sub(r'(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', s1).lower()


class EloquentParser(BaseSchemaParser):
    """Parse Laravel Eloquent models and migrations."""

    FILE_EXTENSIONS = ['.php']

    def parse(self, project_path: str) -> Dict:
        """Parse Eloquent models and Laravel migrations.

        Returns:
            Standardized schema dict with tables and relationships.
        """
        tables: List[Dict] = []
        relationships: List[Dict] = []
        model_tables: Dict[str, str] = {}  # ClassName -> table_name

        # --- Parse model files ---
        model_files = self._find_model_files(project_path)
        for fpath in model_files:
            content = read_file_safe(fpath)
            if not content:
                continue

            model_info = self._parse_model(content, fpath)
            if model_info:
                model_tables[model_info['class_name']] = model_info['table_name']
                relationships.extend(model_info.get('relationships', []))

        # --- Parse migration files ---
        migration_files = self._find_migration_files(project_path)
        migration_files.sort()
        for fpath in migration_files:
            content = read_file_safe(fpath)
            if not content:
                continue
            parsed = self._parse_migration(content, fpath)
            tables.extend(parsed)

        # If no explicit relationships, derive from foreign keys
        if not relationships:
            relationships = self._detect_relationships(tables)

        return self.make_schema_result(tables, relationships)

    # ------------------------------------------------------------------
    # File discovery
    # ------------------------------------------------------------------

    def _find_model_files(self, project_path: str) -> List[str]:
        """Find Eloquent model files."""
        # Standard Laravel: app/Models/
        models_dir = os.path.join(project_path, 'app', 'Models')
        if os.path.isdir(models_dir):
            return find_source_files(models_dir, ['.php'])

        # Older Laravel: app/ (models directly in app)
        app_dir = os.path.join(project_path, 'app')
        if os.path.isdir(app_dir):
            return find_source_files(app_dir, ['.php'])

        # Fallback: search everywhere
        return find_source_files(project_path, ['.php'])

    def _find_migration_files(self, project_path: str) -> List[str]:
        """Find Laravel migration files."""
        migrate_dir = os.path.join(project_path, 'database', 'migrations')
        if os.path.isdir(migrate_dir):
            return find_source_files(migrate_dir, ['.php'])

        # Fallback: look for migration-like directories
        results = []
        all_php = find_source_files(project_path, ['.php'])
        for fpath in all_php:
            if 'migration' in fpath.lower():
                results.append(fpath)
        return results

    # ------------------------------------------------------------------
    # Model parsing
    # ------------------------------------------------------------------

    def _parse_model(self, content: str, file_path: str) -> Optional[Dict]:
        """Parse a single Eloquent model file."""
        stripped = _strip_php_comments_only(content)

        class_match = _MODEL_CLASS_RE.search(stripped)
        if not class_match:
            return None

        class_name = class_match.group(1)

        # Determine table name
        table_match = _TABLE_NAME_RE.search(stripped)
        if table_match:
            table_name = table_match.group(1)
        else:
            # Laravel convention: CamelCase model → snake_case plural table
            table_name = _pluralize_simple(_snake_case(class_name))

        # Parse fillable fields
        fillable = []
        fillable_match = _FILLABLE_RE.search(stripped)
        if fillable_match:
            fillable = _ARRAY_ITEM_RE.findall(fillable_match.group(1))

        # Parse casts
        casts = {}
        casts_match = _CASTS_RE.search(stripped)
        if casts_match:
            for field, cast_type in _CAST_ENTRY_RE.findall(casts_match.group(1)):
                casts[field] = cast_type

        # Parse hidden fields
        hidden = []
        hidden_match = _HIDDEN_RE.search(stripped)
        if hidden_match:
            hidden = _ARRAY_ITEM_RE.findall(hidden_match.group(1))

        # Parse relationships
        relationships = self._parse_relationships(stripped, class_name, table_name, file_path)

        return {
            'class_name': class_name,
            'table_name': table_name,
            'fillable': fillable,
            'casts': casts,
            'hidden': hidden,
            'relationships': relationships,
            'source_file': file_path,
        }

    def _parse_relationships(self, content: str, class_name: str,
                             table_name: str, file_path: str) -> List[Dict]:
        """Parse relationship methods from model content."""
        relationships: List[Dict] = []

        for match in _RELATIONSHIP_RE.finditer(content):
            rel_type = match.group(1)
            related_class = match.group(2)
            related_table = _pluralize_simple(_snake_case(related_class))

            relationships.append({
                'from': table_name,
                'to': related_table,
                'type': _REL_TYPE_MAP.get(rel_type, 'unknown'),
                'source_association': rel_type,
                'related_model': related_class,
                'source_file': file_path,
            })

        return relationships

    # ------------------------------------------------------------------
    # Migration parsing
    # ------------------------------------------------------------------

    def _parse_migration(self, content: str, file_path: str) -> List[Dict]:
        """Parse a Laravel migration file."""
        stripped = _strip_php_comments_only(content)
        tables: List[Dict] = []

        for match in _SCHEMA_CREATE_RE.finditer(stripped):
            table_name = match.group(1)
            start_pos = match.end()

            # Extract the closure body
            body, body_start, body_end = extract_block_body(stripped, start_pos)
            if not body:
                continue

            columns = self._parse_migration_columns(body)
            foreign_keys = self._extract_migration_fks(body, table_name)
            indexes = self._extract_migration_indexes(body)

            tables.append({
                'name': table_name,
                'columns': columns,
                'foreign_keys': foreign_keys,
                'indexes': indexes,
                'source_file': file_path,
                'line_number': line_number_at(content, match.start()),
            })

        return tables

    def _parse_migration_columns(self, body: str) -> List[Dict]:
        """Parse column definitions from a migration closure body."""
        columns: List[Dict] = []

        for match in _MIGRATION_COL_RE.finditer(body):
            col_type = match.group(1)
            col_name = match.group(2)  # May be None for id(), timestamps(), etc.
            chain = match.group(3) or ''

            # Handle special column types
            if col_type == 'id':
                columns.append({
                    'name': col_name or 'id',
                    'type': 'BIGINT',
                    'nullable': False,
                    'primary_key': True,
                    'unique': True,
                })
                continue

            if col_type in ('timestamps', 'timestampsTz', 'nullableTimestamps'):
                nullable = col_type == 'nullableTimestamps'
                columns.append({
                    'name': 'created_at',
                    'type': 'TIMESTAMP',
                    'nullable': nullable,
                    'primary_key': False,
                    'unique': False,
                })
                columns.append({
                    'name': 'updated_at',
                    'type': 'TIMESTAMP',
                    'nullable': nullable,
                    'primary_key': False,
                    'unique': False,
                })
                continue

            if col_type in ('softDeletes', 'softDeletesTz'):
                columns.append({
                    'name': 'deleted_at',
                    'type': 'TIMESTAMP',
                    'nullable': True,
                    'primary_key': False,
                    'unique': False,
                })
                continue

            if col_type == 'rememberToken':
                columns.append({
                    'name': 'remember_token',
                    'type': 'VARCHAR',
                    'nullable': True,
                    'primary_key': False,
                    'unique': False,
                })
                continue

            if col_type in ('morphs', 'nullableMorphs'):
                if col_name:
                    nullable = col_type == 'nullableMorphs'
                    columns.append({
                        'name': f'{col_name}_type',
                        'type': 'VARCHAR',
                        'nullable': nullable,
                        'primary_key': False,
                        'unique': False,
                    })
                    columns.append({
                        'name': f'{col_name}_id',
                        'type': 'BIGINT',
                        'nullable': nullable,
                        'primary_key': False,
                        'unique': False,
                    })
                continue

            if not col_name:
                continue

            # Standard column
            nullable = bool(_NULLABLE_CHAIN_RE.search(chain))
            unique = bool(_UNIQUE_CHAIN_RE.search(chain))

            default_match = _DEFAULT_CHAIN_RE.search(chain)
            default_val = default_match.group(1).strip() if default_match else None

            # foreignId implies not null by default
            if col_type == 'foreignId':
                nullable = nullable  # explicit nullable overrides
                col_name_actual = col_name
            else:
                col_name_actual = col_name

            column = {
                'name': col_name_actual,
                'type': _TYPE_MAP.get(col_type, col_type.upper()),
                'nullable': nullable,
                'primary_key': False,
                'unique': unique,
            }
            if default_val is not None:
                column['default'] = default_val

            columns.append(column)

        return columns

    def _extract_migration_fks(self, body: str, table_name: str) -> List[Dict]:
        """Extract foreign keys from migration body."""
        foreign_keys: List[Dict] = []

        # foreignId('department_id')->constrained()
        for match in _MIGRATION_COL_RE.finditer(body):
            col_type = match.group(1)
            col_name = match.group(2)
            chain = match.group(3) or ''

            if col_type == 'foreignId' and col_name:
                if _CONSTRAINED_CHAIN_RE.search(chain):
                    # Derive referenced table: department_id → departments
                    ref_name = col_name
                    if ref_name.endswith('_id'):
                        ref_name = ref_name[:-3]
                    ref_table = _pluralize_simple(ref_name)

                    foreign_keys.append({
                        'column': col_name,
                        'references_table': ref_table,
                        'references_column': 'id',
                    })

        return foreign_keys

    def _extract_migration_indexes(self, body: str) -> List[Dict]:
        """Extract index definitions from migration body."""
        indexes: List[Dict] = []

        for match in _MIGRATION_COL_RE.finditer(body):
            col_name = match.group(2)
            chain = match.group(3) or ''

            if col_name and _UNIQUE_CHAIN_RE.search(chain):
                indexes.append({
                    'columns': [col_name],
                    'unique': True,
                })

        return indexes
