"""
Flask Routes Parser - Extract API route definitions from Flask applications.

Uses Python's AST module for static code analysis without executing code.
"""

import ast
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Set


# Known auth decorator names
AUTH_DECORATORS = {'jwt_required', 'login_required', 'auth_required', 'require_auth', 'authenticated'}


class RouteVisitor(ast.NodeVisitor):
    """AST visitor to extract Flask route definitions from Python code."""

    def __init__(self, filepath: str, module_name: str):
        self.filepath = filepath
        self.module_name = module_name
        self.blueprints = []
        self.routes = []
        self.blueprint_vars = {}  # variable_name -> blueprint_info

    def visit_Assign(self, node: ast.Assign):
        """Detect Blueprint assignments: auth_bp = Blueprint('auth', __name__)"""
        for target in node.targets:
            if isinstance(target, ast.Name) and isinstance(node.value, ast.Call):
                if self._is_blueprint_call(node.value):
                    blueprint_info = self._extract_blueprint(target, node.value, node.lineno)
                    if blueprint_info:
                        self.blueprints.append(blueprint_info)
                        self.blueprint_vars[target.id] = blueprint_info
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        """Extract route decorators from function definitions."""
        self._process_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        """Extract route decorators from async function definitions."""
        self._process_function(node)

    def _process_function(self, node):
        """Process a function definition and extract route info."""
        route_decorator = None
        auth_decorators = []

        for decorator in node.decorator_list:
            # Check for route decorator
            if self._is_route_decorator(decorator):
                route_decorator = decorator
            # Check for auth decorators
            auth_name = self._get_decorator_name(decorator)
            if auth_name in AUTH_DECORATORS:
                auth_decorators.append(auth_name)

        if route_decorator:
            route_info = self._parse_route_decorator(route_decorator, node)
            if route_info:
                route_info['function_name'] = node.name
                route_info['line_number'] = node.lineno
                route_info['end_line'] = node.end_lineno or node.lineno
                route_info['docstring'] = ast.get_docstring(node)
                route_info['security'] = {
                    'requires_auth': len(auth_decorators) > 0,
                    'auth_decorators': auth_decorators
                }
                route_info['file_path'] = self.filepath
                route_info['module'] = self.module_name
                self.routes.append(route_info)

        self.generic_visit(node)

    def _is_blueprint_call(self, node: ast.Call) -> bool:
        """Check if a Call node is a Blueprint constructor."""
        if isinstance(node.func, ast.Name):
            return node.func.id == 'Blueprint'
        elif isinstance(node.func, ast.Attribute):
            return node.func.attr == 'Blueprint'
        return False

    def _extract_blueprint(self, target: ast.Name, call: ast.Call, lineno: int) -> Optional[Dict]:
        """Extract blueprint information from a Blueprint() call."""
        blueprint_name = None
        url_prefix = None

        # First arg is blueprint name
        if call.args:
            first_arg = call.args[0]
            if isinstance(first_arg, ast.Constant):
                blueprint_name = first_arg.value

        # Look for url_prefix in keywords
        for keyword in call.keywords:
            if keyword.arg == 'url_prefix':
                if isinstance(keyword.value, ast.Constant):
                    url_prefix = keyword.value.value

        if blueprint_name:
            return {
                'id': f"blueprint_{target.id}_{lineno}",
                'type': 'blueprint',
                'name': blueprint_name,
                'variable': target.id,
                'url_prefix': url_prefix or '',
                'file_path': self.filepath,
                'line_number': lineno,
                'route_count': 0  # Will be updated later
            }
        return None

    def _is_route_decorator(self, decorator: ast.AST) -> bool:
        """Check if a decorator is a route decorator."""
        if isinstance(decorator, ast.Call):
            func = decorator.func
            if isinstance(func, ast.Attribute):
                # @bp.route(), @app.route(), @bp.get(), @bp.post(), etc.
                return func.attr in ['route', 'get', 'post', 'put', 'delete', 'patch', 'options']
            elif isinstance(func, ast.Name):
                # @route()
                return func.id == 'route'
        elif isinstance(decorator, ast.Attribute):
            # @bp.route without call (unlikely but possible)
            return decorator.attr in ['route', 'get', 'post', 'put', 'delete', 'patch', 'options']
        return False

    def _parse_route_decorator(self, decorator: ast.Call, func_node: ast.AST) -> Optional[Dict]:
        """Parse route decorator to extract URL pattern and methods."""
        url_pattern = ""
        methods = ["GET"]  # Default
        blueprint_var = None

        # Get the blueprint variable name
        if isinstance(decorator.func, ast.Attribute):
            if isinstance(decorator.func.value, ast.Name):
                blueprint_var = decorator.func.value.id

            # Handle method shortcuts like @bp.get(), @bp.post()
            method_name = decorator.func.attr.upper()
            if method_name in ['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS']:
                methods = [method_name]

        # First arg is URL pattern
        if decorator.args:
            first_arg = decorator.args[0]
            if isinstance(first_arg, ast.Constant):
                url_pattern = first_arg.value

        # Look for methods keyword
        for keyword in decorator.keywords:
            if keyword.arg == 'methods':
                if isinstance(keyword.value, ast.List):
                    methods = []
                    for elt in keyword.value.elts:
                        if isinstance(elt, ast.Constant):
                            methods.append(elt.value)

        # Extract path parameters
        path_params = self._extract_path_params(url_pattern)

        # Find associated blueprint
        blueprint_id = None
        full_url = url_pattern
        if blueprint_var and blueprint_var in self.blueprint_vars:
            bp_info = self.blueprint_vars[blueprint_var]
            blueprint_id = bp_info['id']
            prefix = bp_info.get('url_prefix', '')
            full_url = prefix + url_pattern if prefix else url_pattern

        # Generate unique ID
        route_id = f"route_{self.module_name}_{func_node.name}_{func_node.lineno}"

        return {
            'id': route_id,
            'type': 'route',
            'url_pattern': url_pattern,
            'full_url': full_url,
            'methods': methods,
            'blueprint_id': blueprint_id,
            'blueprint_var': blueprint_var,
            'parameters': {
                'path_params': path_params,
                'query_params': []  # Would need more complex analysis
            }
        }

    def _extract_path_params(self, url_pattern: str) -> List[Dict]:
        """Extract path parameters from URL pattern like /<int:project_id>"""
        params = []
        # Match patterns like <type:name> or <name>
        matches = re.findall(r'<(\w+:)?(\w+)>', url_pattern)
        for type_hint, name in matches:
            params.append({
                'name': name,
                'type': type_hint.rstrip(':') if type_hint else 'string'
            })
        return params

    def _get_decorator_name(self, decorator: ast.AST) -> Optional[str]:
        """Get the name of a decorator."""
        if isinstance(decorator, ast.Name):
            return decorator.id
        elif isinstance(decorator, ast.Call):
            if isinstance(decorator.func, ast.Name):
                return decorator.func.id
            elif isinstance(decorator.func, ast.Attribute):
                return decorator.func.attr
        elif isinstance(decorator, ast.Attribute):
            return decorator.attr
        return None


class FlaskRoutesParser:
    """Parse Flask application to extract API route definitions."""

    def __init__(self, project_path: str, options: Optional[Dict] = None):
        """
        Initialize parser with project directory.

        Args:
            project_path: Root directory of Flask project
            options: Configuration options
        """
        self.project_path = Path(project_path)
        self.options = options or {}
        self.blueprints = []
        self.routes = []
        self.blueprint_prefixes = {}  # blueprint_id -> url_prefix from register_blueprint

    def parse(self) -> Dict:
        """
        Main parsing method - orchestrates the analysis.

        Returns:
            {
                'analysis_type': 'api_routes',
                'blueprints': [...],
                'routes': [...],
                'statistics': {...}
            }
        """
        # Find all Python files
        python_files = self._find_python_files()

        # Parse each file
        for filepath in python_files:
            self._parse_file(filepath)

        # Look for register_blueprint calls to get url_prefix
        for filepath in python_files:
            self._find_blueprint_registration(filepath)

        # Update route full URLs with registered prefixes
        self._update_route_urls()

        # Update blueprint route counts
        self._update_blueprint_counts()

        # Calculate statistics
        statistics = self._calculate_statistics()

        return {
            'analysis_type': 'api_routes',
            'version': '1.0',
            'project_path': str(self.project_path),
            'blueprints': self.blueprints,
            'routes': self.routes,
            'statistics': statistics
        }

    def _find_python_files(self) -> List[Path]:
        """Find all Python files in the project directory."""
        python_files = []

        for root, dirs, files in os.walk(self.project_path):
            # Skip common non-source directories
            dirs[:] = [d for d in dirs if d not in [
                '__pycache__', '.git', '.venv', 'venv', 'node_modules',
                '.pytest_cache', '.tox', 'dist', 'build', '.eggs', 'tests'
            ]]

            for file in files:
                if file.endswith('.py'):
                    filepath = Path(root) / file
                    python_files.append(filepath)

        return python_files

    def _parse_file(self, filepath: Path):
        """Parse a single Python file for routes and blueprints."""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                source = f.read()

            tree = ast.parse(source, filename=str(filepath))

            # Generate module name
            rel_path = filepath.relative_to(self.project_path)
            module_name = str(rel_path.with_suffix('')).replace(os.sep, '.')

            # Create visitor and extract information
            visitor = RouteVisitor(str(filepath), module_name)
            visitor.visit(tree)

            # Collect results
            self.blueprints.extend(visitor.blueprints)
            self.routes.extend(visitor.routes)

        except SyntaxError as e:
            print(f"Syntax error in {filepath}: {e}")
        except Exception as e:
            print(f"Error parsing {filepath}: {e}")

    def _find_blueprint_registration(self, filepath: Path):
        """Find register_blueprint calls to get url_prefix."""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                source = f.read()

            tree = ast.parse(source, filename=str(filepath))

            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    # Look for app.register_blueprint() or similar
                    if isinstance(node.func, ast.Attribute):
                        if node.func.attr == 'register_blueprint':
                            self._parse_register_blueprint(node)

        except Exception:
            pass

    def _parse_register_blueprint(self, call: ast.Call):
        """Parse register_blueprint call for url_prefix."""
        blueprint_var = None
        url_prefix = None

        # First arg should be blueprint variable
        if call.args:
            if isinstance(call.args[0], ast.Name):
                blueprint_var = call.args[0].id

        # Look for url_prefix keyword
        for keyword in call.keywords:
            if keyword.arg == 'url_prefix':
                if isinstance(keyword.value, ast.Constant):
                    url_prefix = keyword.value.value

        if blueprint_var and url_prefix:
            # Find matching blueprint and update
            for bp in self.blueprints:
                if bp.get('variable') == blueprint_var:
                    self.blueprint_prefixes[bp['id']] = url_prefix
                    bp['url_prefix'] = url_prefix

    def _update_route_urls(self):
        """Update route full URLs based on registered blueprint prefixes."""
        for route in self.routes:
            if route.get('blueprint_id'):
                bp_id = route['blueprint_id']
                if bp_id in self.blueprint_prefixes:
                    prefix = self.blueprint_prefixes[bp_id]
                    route['full_url'] = prefix + route['url_pattern']

    def _update_blueprint_counts(self):
        """Update route_count for each blueprint."""
        # Count routes per blueprint
        counts = {}
        for route in self.routes:
            bp_id = route.get('blueprint_id')
            if bp_id:
                counts[bp_id] = counts.get(bp_id, 0) + 1

        # Update blueprints
        for bp in self.blueprints:
            bp['route_count'] = counts.get(bp['id'], 0)

    def _calculate_statistics(self) -> Dict:
        """Calculate statistics about the analyzed routes."""
        # Count routes by method
        routes_by_method = {}
        for route in self.routes:
            for method in route.get('methods', ['GET']):
                routes_by_method[method] = routes_by_method.get(method, 0) + 1

        # Count protected vs unprotected
        protected = sum(1 for r in self.routes if r.get('security', {}).get('requires_auth', False))
        unprotected = len(self.routes) - protected

        return {
            'total_blueprints': len(self.blueprints),
            'total_routes': len(self.routes),
            'routes_by_method': routes_by_method,
            'protected_routes': protected,
            'unprotected_routes': unprotected
        }
