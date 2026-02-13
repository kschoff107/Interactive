import ast
import logging
import os
from typing import Dict, List

from ..base import BaseSchemaParser, find_source_files, read_file_safe

logger = logging.getLogger(__name__)


class SQLAlchemyParser(BaseSchemaParser):
    """Parser for SQLAlchemy models."""

    FILE_EXTENSIONS = ['.py']

    def parse(self, project_path: str) -> Dict:
        """Parse SQLAlchemy models and return standardized schema."""
        tables = []

        model_files = self.find_files(project_path)

        for file_path in model_files:
            content = read_file_safe(file_path)
            if not content:
                continue
            try:
                tree = ast.parse(content)
                tables.extend(self._extract_tables_from_ast(tree))
            except Exception as e:
                logger.warning("Failed to parse %s: %s", file_path, e)
                continue

        return self.make_schema_result(tables)

    def _extract_tables_from_ast(self, tree: ast.AST) -> List[Dict]:
        """Extract table definitions from AST"""
        tables = []

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                # Check if class has __tablename__ attribute
                table_name = None
                for item in node.body:
                    if isinstance(item, ast.Assign):
                        for target in item.targets:
                            if isinstance(target, ast.Name) and target.id == '__tablename__':
                                if isinstance(item.value, ast.Constant):
                                    table_name = item.value.value

                if table_name:
                    columns = self._extract_columns(node)
                    foreign_keys = self._extract_foreign_keys(node)

                    tables.append({
                        'name': table_name,
                        'columns': columns,
                        'foreign_keys': foreign_keys,
                        'indexes': []
                    })

        return tables

    def _extract_columns(self, class_node: ast.ClassDef) -> List[Dict]:
        """Extract columns from class definition.

        Handles both plain SQLAlchemy (Column(...)) and Flask-SQLAlchemy
        (db.Column(...)) patterns.
        """
        columns = []

        for item in class_node.body:
            if isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name):
                        col_name = target.id
                        if col_name.startswith('_'):
                            continue

                        if isinstance(item.value, ast.Call) and self._is_column_call(item.value):
                            column_info = self._parse_column_call(col_name, item.value)
                            columns.append(column_info)

        return columns

    def _parse_column_call(self, name: str, call: ast.Call) -> Dict:
        """Parse a Column() call."""
        column = {
            'name': name,
            'type': 'String',
            'nullable': True,
            'primary_key': False,
            'unique': False,
        }

        # Get type from first arg — handles both String and db.String
        if call.args:
            first_arg = call.args[0]
            col_type = self._extract_name(first_arg)
            if col_type:
                column['type'] = col_type
            elif isinstance(first_arg, ast.Call):
                # String(255), db.String(255)
                inner_name = self._extract_name(first_arg.func)
                if inner_name:
                    column['type'] = inner_name

        # Parse keyword arguments
        for keyword in call.keywords:
            if keyword.arg == 'primary_key':
                column['primary_key'] = isinstance(keyword.value, ast.Constant) and keyword.value.value is True
            elif keyword.arg == 'nullable':
                column['nullable'] = not (isinstance(keyword.value, ast.Constant) and keyword.value.value is False)
            elif keyword.arg == 'unique':
                column['unique'] = isinstance(keyword.value, ast.Constant) and keyword.value.value is True

        return column

    def _extract_foreign_keys(self, class_node: ast.ClassDef) -> List[Dict]:
        """Extract foreign keys from class definition.

        Handles both Column(ForeignKey(...)) and db.Column(db.ForeignKey(...)).
        """
        foreign_keys = []

        for item in class_node.body:
            if isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name):
                        col_name = target.id

                        if isinstance(item.value, ast.Call) and self._is_column_call(item.value):
                            for arg in item.value.args:
                                if isinstance(arg, ast.Call) and self._is_fk_call(arg):
                                    if arg.args and isinstance(arg.args[0], ast.Constant):
                                        parts = str(arg.args[0].value).split('.')
                                        if len(parts) == 2:
                                            foreign_keys.append({
                                                'column': col_name,
                                                'references_table': parts[0],
                                                'references_column': parts[1],
                                            })

        return foreign_keys

    @staticmethod
    def _is_column_call(node: ast.Call) -> bool:
        """Check if an AST Call node is Column() or db.Column()."""
        func = node.func
        if isinstance(func, ast.Name) and func.id == 'Column':
            return True
        if isinstance(func, ast.Attribute) and func.attr == 'Column':
            return True
        return False

    @staticmethod
    def _is_fk_call(node: ast.Call) -> bool:
        """Check if an AST Call node is ForeignKey() or db.ForeignKey()."""
        func = node.func
        if isinstance(func, ast.Name) and func.id == 'ForeignKey':
            return True
        if isinstance(func, ast.Attribute) and func.attr == 'ForeignKey':
            return True
        return False

    @staticmethod
    def _extract_name(node: ast.AST) -> str:
        """Extract a simple name from ast.Name or ast.Attribute (e.g. db.String → 'String')."""
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            return node.attr
        return ''

