"""
Django ORM Schema Parser - Extract database schema from Django model definitions.

Uses Python's AST module for static code analysis without executing code.
Detects Django model classes inheriting from models.Model, their fields,
foreign keys, many-to-many relationships, and Meta options.
"""

import ast
import logging
import os
import re
from typing import Dict, List, Optional, Tuple

from ..base import BaseSchemaParser, find_source_files, SKIP_DIRS

logger = logging.getLogger(__name__)


# Map Django field types to simplified SQL-like types for display
DJANGO_FIELD_TYPE_MAP = {
    'AutoField': 'INTEGER',
    'BigAutoField': 'BIGINT',
    'SmallAutoField': 'SMALLINT',
    'BigIntegerField': 'BIGINT',
    'BinaryField': 'BLOB',
    'BooleanField': 'BOOLEAN',
    'CharField': 'VARCHAR',
    'DateField': 'DATE',
    'DateTimeField': 'DATETIME',
    'DecimalField': 'DECIMAL',
    'DurationField': 'INTERVAL',
    'EmailField': 'VARCHAR',
    'FileField': 'VARCHAR',
    'FilePathField': 'VARCHAR',
    'FloatField': 'FLOAT',
    'GenericIPAddressField': 'VARCHAR',
    'IPAddressField': 'VARCHAR',
    'ImageField': 'VARCHAR',
    'IntegerField': 'INTEGER',
    'JSONField': 'JSON',
    'NullBooleanField': 'BOOLEAN',
    'PositiveBigIntegerField': 'BIGINT',
    'PositiveIntegerField': 'INTEGER',
    'PositiveSmallIntegerField': 'SMALLINT',
    'SlugField': 'VARCHAR',
    'SmallIntegerField': 'SMALLINT',
    'TextField': 'TEXT',
    'TimeField': 'TIME',
    'URLField': 'VARCHAR',
    'UUIDField': 'UUID',
    'ForeignKey': 'INTEGER',
    'OneToOneField': 'INTEGER',
}


def _get_attr_chain(node: ast.AST) -> Optional[str]:
    """Resolve a dotted attribute access chain, e.g. models.CharField -> 'CharField'.

    Returns the final attribute name, or the Name id for simple names.
    Returns None for unsupported node types.
    """
    if isinstance(node, ast.Attribute):
        return node.attr
    elif isinstance(node, ast.Name):
        return node.id
    return None


def _get_constant_value(node: ast.AST) -> Optional:
    """Extract a constant value from an AST node, or None if not a constant."""
    if isinstance(node, ast.Constant):
        return node.value
    return None


class DjangoModelVisitor(ast.NodeVisitor):
    """AST visitor that extracts Django model definitions from a single file."""

    def __init__(self, filepath: str):
        self.filepath = filepath
        self.models: List[Dict] = []
        self._current_model: Optional[str] = None

    def visit_ClassDef(self, node: ast.ClassDef):
        """Process class definitions, looking for Django model classes."""
        if self._is_django_model(node):
            model_info = self._extract_model(node)
            if model_info:
                self.models.append(model_info)
        # Visit nested classes only if they are not Meta
        self.generic_visit(node)

    def _is_django_model(self, node: ast.ClassDef) -> bool:
        """Check if a class inherits from models.Model or Model.

        Detects:
            - class Foo(models.Model):
            - class Foo(Model):
            - class Foo(SomeAbstractModel):  -- not detected (would need import resolution)
        """
        for base in node.bases:
            if isinstance(base, ast.Attribute):
                # models.Model
                if (isinstance(base.value, ast.Name) and
                        base.value.id == 'models' and
                        base.attr == 'Model'):
                    return True
            elif isinstance(base, ast.Name):
                # Model (direct import)
                if base.id == 'Model':
                    return True
        return False

    def _extract_model(self, node: ast.ClassDef) -> Optional[Dict]:
        """Extract full model information from a class definition."""
        class_name = node.name
        table_name = self._extract_table_name(node, class_name)
        columns = []
        foreign_keys = []
        m2m_relations = []
        indexes = []

        for item in node.body:
            if not isinstance(item, ast.Assign):
                continue
            for target in item.targets:
                if not isinstance(target, ast.Name):
                    continue
                field_name = target.id
                if field_name.startswith('_') and field_name != '__str__':
                    continue

                if isinstance(item.value, ast.Call):
                    field_type_name = _get_attr_chain(item.value.func)
                    if not field_type_name:
                        continue

                    if field_type_name == 'ForeignKey':
                        fk_info = self._parse_foreign_key(
                            field_name, item.value, table_name)
                        if fk_info:
                            foreign_keys.append(fk_info['fk'])
                            columns.append(fk_info['column'])
                    elif field_type_name == 'OneToOneField':
                        fk_info = self._parse_foreign_key(
                            field_name, item.value, table_name,
                            one_to_one=True)
                        if fk_info:
                            foreign_keys.append(fk_info['fk'])
                            columns.append(fk_info['column'])
                    elif field_type_name == 'ManyToManyField':
                        m2m = self._parse_many_to_many(
                            field_name, item.value, table_name)
                        if m2m:
                            m2m_relations.append(m2m)
                    elif field_type_name in DJANGO_FIELD_TYPE_MAP or self._looks_like_field(field_type_name):
                        col_info = self._parse_field(
                            field_name, field_type_name, item.value)
                        if col_info:
                            columns.append(col_info)

        # Django auto-adds an 'id' primary key unless one is explicitly defined
        has_pk = any(c.get('primary_key') for c in columns)
        if not has_pk:
            columns.insert(0, {
                'name': 'id',
                'type': 'INTEGER',
                'nullable': False,
                'primary_key': True,
                'unique': True,
                'auto_generated': True,
            })

        # Extract indexes from Meta class
        indexes = self._extract_indexes(node, table_name)

        return {
            'name': table_name,
            'class_name': class_name,
            'columns': columns,
            'foreign_keys': foreign_keys,
            'indexes': indexes,
            'file_path': self.filepath,
            'line_number': node.lineno,
            '_m2m_relations': m2m_relations,  # Internal; consumed by parser
        }

    def _extract_table_name(self, node: ast.ClassDef, class_name: str) -> str:
        """Extract the database table name.

        Checks class Meta: db_table first, otherwise derives from class name
        using Django's convention: AppLabel_ModelName -> lowercase model name.
        Since we don't know the app label statically, we use the lowercase
        class name as a reasonable approximation.
        """
        for item in node.body:
            if isinstance(item, ast.ClassDef) and item.name == 'Meta':
                for meta_item in item.body:
                    if isinstance(meta_item, ast.Assign):
                        for target in meta_item.targets:
                            if (isinstance(target, ast.Name) and
                                    target.id == 'db_table'):
                                val = _get_constant_value(meta_item.value)
                                if val:
                                    return val
        # Django default: app_label + '_' + model_name.lower()
        # Without app_label we use just the lowercased class name
        return class_name.lower()

    def _parse_field(self, field_name: str, field_type_name: str,
                     call: ast.Call) -> Optional[Dict]:
        """Parse a standard Django model field (CharField, IntegerField, etc.)."""
        sql_type = DJANGO_FIELD_TYPE_MAP.get(field_type_name, field_type_name)

        column = {
            'name': field_name,
            'type': sql_type,
            'nullable': True,
            'primary_key': False,
            'unique': False,
        }

        # Extract keyword arguments
        for keyword in call.keywords:
            if keyword.arg == 'primary_key':
                val = _get_constant_value(keyword.value)
                if val is True:
                    column['primary_key'] = True
                    column['nullable'] = False
            elif keyword.arg == 'null':
                val = _get_constant_value(keyword.value)
                if val is not None:
                    column['nullable'] = bool(val)
            elif keyword.arg == 'unique':
                val = _get_constant_value(keyword.value)
                if val is True:
                    column['unique'] = True
            elif keyword.arg == 'max_length':
                val = _get_constant_value(keyword.value)
                if val is not None:
                    column['type'] = f'{sql_type}({val})'
            elif keyword.arg == 'default':
                val = _get_constant_value(keyword.value)
                if val is not None:
                    column['default'] = val
            elif keyword.arg == 'max_digits':
                val = _get_constant_value(keyword.value)
                if val is not None:
                    column['max_digits'] = val
            elif keyword.arg == 'decimal_places':
                val = _get_constant_value(keyword.value)
                if val is not None:
                    column['decimal_places'] = val
            elif keyword.arg == 'auto_now' or keyword.arg == 'auto_now_add':
                val = _get_constant_value(keyword.value)
                if val is True:
                    column['auto_generated'] = True

        # Django fields are NOT NULL by default (null=False is the default)
        # unless null=True is explicitly set
        if not any(kw.arg == 'null' for kw in call.keywords):
            column['nullable'] = False

        return column

    def _parse_foreign_key(self, field_name: str, call: ast.Call,
                           source_table: str,
                           one_to_one: bool = False) -> Optional[Dict]:
        """Parse a ForeignKey or OneToOneField.

        Django stores FK as <field_name>_id in the database.
        """
        referenced_model = self._get_related_model_name(call)
        if not referenced_model:
            return None

        # Django convention: FK column is <field_name>_id
        db_column = f'{field_name}_id'

        # Check for explicit db_column
        for keyword in call.keywords:
            if keyword.arg == 'db_column':
                val = _get_constant_value(keyword.value)
                if val:
                    db_column = val

        # Determine nullability
        nullable = False
        for keyword in call.keywords:
            if keyword.arg == 'null':
                val = _get_constant_value(keyword.value)
                if val is True:
                    nullable = True

        referenced_table = referenced_model.lower()

        column = {
            'name': db_column,
            'type': 'INTEGER',
            'nullable': nullable,
            'primary_key': one_to_one,  # OneToOneField can serve as PK
            'unique': one_to_one,
            'is_foreign_key': True,
        }

        fk = {
            'column': db_column,
            'references_table': referenced_table,
            'references_column': 'id',
            'on_delete': self._get_on_delete(call),
            'relationship_type': 'one-to-one' if one_to_one else 'many-to-one',
        }

        return {'column': column, 'fk': fk}

    def _parse_many_to_many(self, field_name: str, call: ast.Call,
                            source_table: str) -> Optional[Dict]:
        """Parse a ManyToManyField. These create a junction table in the DB."""
        referenced_model = self._get_related_model_name(call)
        if not referenced_model:
            return None

        # Check for explicit through model
        through_model = None
        for keyword in call.keywords:
            if keyword.arg == 'through':
                val = _get_constant_value(keyword.value)
                if val:
                    through_model = val

        return {
            'field_name': field_name,
            'from_table': source_table,
            'to_table': referenced_model.lower(),
            'through': through_model,
        }

    def _get_related_model_name(self, call: ast.Call) -> Optional[str]:
        """Extract the related model name from a relationship field.

        Handles:
            - ForeignKey(User, ...) -> 'User'
            - ForeignKey('User', ...) -> 'User'
            - ForeignKey('myapp.User', ...) -> 'User'
            - ForeignKey('self', ...) -> uses current context
        """
        if not call.args:
            return None

        first_arg = call.args[0]
        if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
            model_ref = first_arg.value
            # Handle 'app_label.ModelName' format
            if '.' in model_ref:
                model_ref = model_ref.split('.')[-1]
            return model_ref
        elif isinstance(first_arg, ast.Name):
            return first_arg.id
        elif isinstance(first_arg, ast.Attribute):
            return first_arg.attr

        return None

    def _get_on_delete(self, call: ast.Call) -> str:
        """Extract the on_delete behavior from a FK field."""
        for keyword in call.keywords:
            if keyword.arg == 'on_delete':
                action = _get_attr_chain(keyword.value)
                if action:
                    return action
        # Also check positional: ForeignKey(Model, models.CASCADE)
        if len(call.args) >= 2:
            action = _get_attr_chain(call.args[1])
            if action:
                return action
        return 'CASCADE'

    def _extract_indexes(self, node: ast.ClassDef, table_name: str) -> List[Dict]:
        """Extract index definitions from Meta class."""
        indexes = []
        for item in node.body:
            if isinstance(item, ast.ClassDef) and item.name == 'Meta':
                for meta_item in item.body:
                    if isinstance(meta_item, ast.Assign):
                        for target in meta_item.targets:
                            if isinstance(target, ast.Name):
                                if target.id == 'unique_together':
                                    idx = self._parse_unique_together(
                                        meta_item.value, table_name)
                                    indexes.extend(idx)
                                elif target.id == 'indexes':
                                    idx = self._parse_meta_indexes(
                                        meta_item.value, table_name)
                                    indexes.extend(idx)
        return indexes

    def _parse_unique_together(self, node: ast.AST, table_name: str) -> List[Dict]:
        """Parse unique_together from Meta class.

        Handles:
            unique_together = [('field1', 'field2')]
            unique_together = (('field1', 'field2'),)
        """
        indexes = []
        if isinstance(node, (ast.List, ast.Tuple)):
            for elt in node.elts:
                if isinstance(elt, (ast.List, ast.Tuple)):
                    cols = []
                    for col_node in elt.elts:
                        val = _get_constant_value(col_node)
                        if val:
                            cols.append(val)
                    if cols:
                        indexes.append({
                            'name': f'unique_{table_name}_{"_".join(cols)}',
                            'columns': cols,
                            'unique': True,
                        })
        return indexes

    def _parse_meta_indexes(self, node: ast.AST, table_name: str) -> List[Dict]:
        """Parse indexes from Meta.indexes list.

        Handles:
            indexes = [models.Index(fields=['field1', 'field2'], name='idx_name')]
        """
        indexes = []
        if isinstance(node, ast.List):
            for elt in node.elts:
                if isinstance(elt, ast.Call):
                    idx = self._parse_index_call(elt, table_name)
                    if idx:
                        indexes.append(idx)
        return indexes

    def _parse_index_call(self, call: ast.Call, table_name: str) -> Optional[Dict]:
        """Parse a models.Index() call."""
        fields = []
        index_name = None

        for keyword in call.keywords:
            if keyword.arg == 'fields':
                if isinstance(keyword.value, ast.List):
                    for elt in keyword.value.elts:
                        val = _get_constant_value(elt)
                        if val:
                            fields.append(val)
            elif keyword.arg == 'name':
                val = _get_constant_value(keyword.value)
                if val:
                    index_name = val

        if fields:
            return {
                'name': index_name or f'idx_{table_name}_{"_".join(fields)}',
                'columns': fields,
                'unique': False,
            }
        return None

    @staticmethod
    def _looks_like_field(name: str) -> bool:
        """Heuristic check if a name looks like a Django field type."""
        return name.endswith('Field')


class DjangoParser(BaseSchemaParser):
    """Parse Django project to extract database schema from model definitions.

    Scans all Python files in a project directory for Django model classes
    (classes inheriting from models.Model), extracts their fields, foreign keys,
    many-to-many relationships, and Meta options, then produces a standardized
    schema dict that the frontend can render.
    """

    def parse(self, project_path: str) -> Dict:
        """Parse Django models and return standardized schema.

        Args:
            project_path: Root directory to scan for Django model files.

        Returns:
            Dict with 'tables' and 'relationships' keys matching the
            standardized schema format.
        """
        tables = []
        m2m_relations = []

        model_files = find_source_files(
            project_path, ['.py'],
            skip_dirs=SKIP_DIRS | {'migrations', 'static', 'templates', 'media'},
        )

        for file_path in model_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    source = f.read()

                tree = ast.parse(source, filename=file_path)
                visitor = DjangoModelVisitor(file_path)
                visitor.visit(tree)

                for model in visitor.models:
                    # Separate internal m2m data from public table data
                    m2m = model.pop('_m2m_relations', [])
                    m2m_relations.extend(m2m)
                    tables.append(model)

            except SyntaxError as e:
                logger.warning("Failed to parse %s: %s", file_path, e)
                continue
            except Exception as e:
                logger.warning("Failed to parse %s: %s", file_path, e)
                continue

        if not tables:
            return {'tables': [], 'relationships': []}

        # Build table name lookup for resolving references
        table_by_class = {}
        for table in tables:
            table_by_class[table.get('class_name', '')] = table['name']

        # Resolve FK references: convert class names to table names
        for table in tables:
            for fk in table.get('foreign_keys', []):
                ref_table = fk['references_table']
                # If ref_table matches a known class name, use its table name
                if ref_table in table_by_class:
                    fk['references_table'] = table_by_class[ref_table]
                elif ref_table.capitalize() in table_by_class:
                    fk['references_table'] = table_by_class[ref_table.capitalize()]
                # If 'self', reference own table
                if ref_table == 'self':
                    fk['references_table'] = table['name']

        # Detect relationships
        relationships = self._detect_relationships(tables)

        # Add many-to-many relationships
        for m2m in m2m_relations:
            to_table = m2m['to_table']
            # Resolve class name to table name
            if to_table in table_by_class:
                to_table = table_by_class[to_table]
            elif to_table.capitalize() in table_by_class:
                to_table = table_by_class[to_table.capitalize()]

            relationships.append({
                'from_table': m2m['from_table'],
                'to_table': to_table,
                'from_column': '',
                'to_column': '',
                'type': 'many-to-many',
            })

        return self.make_schema_result(tables, relationships)

    @staticmethod
    def _detect_relationships(tables: List[Dict]) -> List[Dict]:
        """Derive relationships from foreign keys across all tables."""
        relationships = []
        for table in tables:
            for fk in table.get('foreign_keys', []):
                rel_type = fk.get('relationship_type', 'many-to-one')
                relationships.append({
                    'from_table': table['name'],
                    'to_table': fk['references_table'],
                    'from_column': fk.get('column', ''),
                    'to_column': fk.get('references_column', ''),
                    'type': rel_type,
                })
        return relationships
