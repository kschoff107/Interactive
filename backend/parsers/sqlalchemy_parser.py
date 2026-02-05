import ast
import os
from typing import Dict, List

class SQLAlchemyParser:
    """Parser for SQLAlchemy models"""

    def parse(self, project_path: str) -> Dict:
        """Parse SQLAlchemy models and return standardized schema"""
        tables = []

        # Find all Python files
        model_files = self._find_python_files(project_path)

        for file_path in model_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    tree = ast.parse(f.read())
                    tables.extend(self._extract_tables_from_ast(tree))
            except Exception as e:
                print(f"Error parsing {file_path}: {e}")
                continue

        # Detect relationships
        relationships = self._detect_relationships(tables)

        return {
            'tables': tables,
            'relationships': relationships
        }

    def _find_python_files(self, path: str) -> List[str]:
        """Find all Python files in path"""
        python_files = []
        for root, dirs, files in os.walk(path):
            for file in files:
                if file.endswith('.py'):
                    python_files.append(os.path.join(root, file))
        return python_files

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
        """Extract columns from class definition"""
        columns = []

        for item in class_node.body:
            if isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name):
                        col_name = target.id
                        if col_name.startswith('_'):
                            continue

                        # Parse Column() call
                        if isinstance(item.value, ast.Call):
                            if isinstance(item.value.func, ast.Name) and item.value.func.id == 'Column':
                                column_info = self._parse_column_call(col_name, item.value)
                                columns.append(column_info)

        return columns

    def _parse_column_call(self, name: str, call: ast.Call) -> Dict:
        """Parse a Column() call"""
        column = {
            'name': name,
            'type': 'String',
            'nullable': True,
            'primary_key': False,
            'unique': False
        }

        # Get type from first arg
        if call.args:
            first_arg = call.args[0]
            if isinstance(first_arg, ast.Name):
                column['type'] = first_arg.id
            elif isinstance(first_arg, ast.Call) and isinstance(first_arg.func, ast.Name):
                column['type'] = first_arg.func.id

        # Parse keyword arguments
        for keyword in call.keywords:
            if keyword.arg == 'primary_key':
                column['primary_key'] = isinstance(keyword.value, ast.Constant) and keyword.value.value == True
            elif keyword.arg == 'nullable':
                column['nullable'] = not (isinstance(keyword.value, ast.Constant) and keyword.value.value == False)
            elif keyword.arg == 'unique':
                column['unique'] = isinstance(keyword.value, ast.Constant) and keyword.value.value == True

        return column

    def _extract_foreign_keys(self, class_node: ast.ClassDef) -> List[Dict]:
        """Extract foreign keys from class definition"""
        foreign_keys = []

        for item in class_node.body:
            if isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name):
                        col_name = target.id

                        # Look for Column with ForeignKey
                        if isinstance(item.value, ast.Call) and isinstance(item.value.func, ast.Name) and item.value.func.id == 'Column':
                            for arg in item.value.args:
                                if isinstance(arg, ast.Call) and isinstance(arg.func, ast.Name) and arg.func.id == 'ForeignKey':
                                    if arg.args:
                                        fk_target = arg.args[0]
                                        if isinstance(fk_target, ast.Constant):
                                            # Parse 'table.column' format
                                            parts = fk_target.value.split('.')
                                            if len(parts) == 2:
                                                foreign_keys.append({
                                                    'column': col_name,
                                                    'references_table': parts[0],
                                                    'references_column': parts[1]
                                                })

        return foreign_keys

    def _detect_relationships(self, tables: List[Dict]) -> List[Dict]:
        """Detect relationships between tables based on foreign keys"""
        relationships = []

        for table in tables:
            for fk in table['foreign_keys']:
                relationships.append({
                    'from': table['name'],
                    'to': fk['references_table'],
                    'type': 'many-to-one'
                })

        return relationships
