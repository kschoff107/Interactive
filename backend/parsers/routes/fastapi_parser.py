"""
FastAPI Routes Parser - Extract API route definitions from FastAPI applications.

Uses Python's AST module for static code analysis without executing code.
Detects FastAPI app and APIRouter route decorators, router inclusion,
dependency injection (Depends), and path/query parameter definitions.
"""

import ast
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple


# Known auth-related dependency names (heuristic detection)
AUTH_DEPENDENCY_NAMES = {
    'get_current_user', 'get_current_active_user', 'get_current_superuser',
    'require_auth', 'verify_token', 'check_permissions', 'authenticate',
    'oauth2_scheme', 'get_token_header', 'verify_api_key',
    'login_required', 'auth_required', 'jwt_required',
}

# HTTP method decorators supported by FastAPI
HTTP_METHODS = {'get', 'post', 'put', 'delete', 'patch', 'options', 'head'}

# FastAPI/Starlette app and router class names
APP_CLASS_NAMES = {'FastAPI', 'Starlette'}
ROUTER_CLASS_NAMES = {'APIRouter'}


def _get_name(node: ast.AST) -> Optional[str]:
    """Get a simple name from a Name or Attribute node."""
    if isinstance(node, ast.Name):
        return node.id
    elif isinstance(node, ast.Attribute):
        return node.attr
    return None


def _get_constant_value(node: ast.AST) -> Optional:
    """Extract a constant value from an AST node."""
    if isinstance(node, ast.Constant):
        return node.value
    return None


def _normalize_url(prefix: str, path: str) -> str:
    """Combine a URL prefix and path, ensuring proper slash handling."""
    prefix = prefix.rstrip('/')
    path = path.lstrip('/')
    if not prefix and not path:
        return '/'
    if not prefix:
        return '/' + path if not path.startswith('/') else path
    if not path:
        return prefix + '/' if not prefix.endswith('/') else prefix
    return f'{prefix}/{path}'


def _get_dotted_name(node: ast.AST) -> Optional[str]:
    """Get a dotted name like 'module.attr' from an AST node."""
    if isinstance(node, ast.Name):
        return node.id
    elif isinstance(node, ast.Attribute):
        parent = _get_dotted_name(node.value)
        if parent:
            return f'{parent}.{node.attr}'
        return node.attr
    return None


class FastAPIRouteVisitor(ast.NodeVisitor):
    """AST visitor that extracts FastAPI route definitions from a single file.

    Detects:
        - @app.get("/path"), @app.post("/path"), etc.
        - @router.get("/path"), @router.post("/path"), etc.
        - APIRouter(prefix="/api", tags=["tag"])
        - app.include_router(router, prefix="/api")
        - Depends(get_current_user) as auth indicators
    """

    def __init__(self, filepath: str, module_name: str):
        self.filepath = filepath
        self.module_name = module_name
        self.routes: List[Dict] = []
        self.routers: List[Dict] = []      # APIRouter definitions
        self.includes: List[Dict] = []     # include_router calls
        self._app_vars: Set[str] = set()   # FastAPI() instance variable names
        self._router_vars: Dict[str, Dict] = {}  # var_name -> router_info
        self._route_counter = 0

    def visit_Assign(self, node: ast.Assign):
        """Detect FastAPI app and APIRouter assignments."""
        for target in node.targets:
            if isinstance(target, ast.Name) and isinstance(node.value, ast.Call):
                func_name = _get_name(node.value.func)

                if func_name in APP_CLASS_NAMES:
                    self._app_vars.add(target.id)

                elif func_name in ROUTER_CLASS_NAMES:
                    router_info = self._extract_router(target, node.value, node.lineno)
                    self._router_vars[target.id] = router_info
                    self.routers.append(router_info)

        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        """Extract route decorators from function definitions."""
        self._process_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        """Extract route decorators from async function definitions."""
        self._process_function(node)

    def visit_Expr(self, node: ast.Expr):
        """Detect app.include_router() calls."""
        if isinstance(node.value, ast.Call):
            self._check_include_router(node.value)
        self.generic_visit(node)

    def _process_function(self, node):
        """Process a function definition and extract route info from decorators."""
        route_decorators = []
        auth_deps = []

        for decorator in node.decorator_list:
            if self._is_route_decorator(decorator):
                route_decorators.append(decorator)

        # Check function parameters for Depends() auth dependencies
        auth_deps = self._extract_auth_dependencies(node)

        for decorator in route_decorators:
            route_info = self._parse_route_decorator(decorator, node)
            if route_info:
                route_info['function_name'] = node.name
                route_info['line_number'] = node.lineno
                route_info['end_line'] = node.end_lineno or node.lineno
                route_info['docstring'] = ast.get_docstring(node)
                route_info['is_async'] = isinstance(node, ast.AsyncFunctionDef)

                # Merge auth info from Depends + decorator-level dependencies
                decorator_deps = self._extract_decorator_dependencies(decorator)
                all_auth = list(set(auth_deps + decorator_deps))

                route_info['security'] = {
                    'requires_auth': len(all_auth) > 0,
                    'auth_decorators': all_auth,
                }

                route_info['file_path'] = self.filepath
                route_info['module'] = self.module_name
                self.routes.append(route_info)

        self.generic_visit(node)

    def _is_route_decorator(self, decorator: ast.AST) -> bool:
        """Check if a decorator is a FastAPI route decorator.

        Matches patterns like:
            @app.get("/path")
            @router.post("/path")
            @app.api_route("/path")
        """
        if isinstance(decorator, ast.Call):
            func = decorator.func
            if isinstance(func, ast.Attribute):
                attr = func.attr
                obj_name = _get_name(func.value)

                # Check if object is a known app or router variable
                is_known = (obj_name in self._app_vars or
                            obj_name in self._router_vars)

                if attr in HTTP_METHODS or attr == 'api_route':
                    return is_known or attr in HTTP_METHODS
            elif isinstance(func, ast.Name):
                return func.id in HTTP_METHODS
        return False

    def _parse_route_decorator(self, decorator: ast.Call,
                               func_node: ast.AST) -> Optional[Dict]:
        """Parse a route decorator to extract URL pattern and methods."""
        url_pattern = ''
        methods = []
        router_var = None
        tags = []
        response_model = None
        status_code = None

        func = decorator.func

        # Determine method from decorator name
        if isinstance(func, ast.Attribute):
            attr = func.attr
            if attr in HTTP_METHODS:
                methods = [attr.upper()]
            elif attr == 'api_route':
                methods = ['GET']  # Default; may be overridden by methods kwarg
            router_var = _get_name(func.value)
        elif isinstance(func, ast.Name):
            if func.id in HTTP_METHODS:
                methods = [func.id.upper()]

        # First argument: URL path
        if decorator.args:
            val = _get_constant_value(decorator.args[0])
            if val is not None:
                url_pattern = val

        # Keyword arguments
        for keyword in decorator.keywords:
            if keyword.arg == 'methods':
                if isinstance(keyword.value, ast.List):
                    methods = []
                    for elt in keyword.value.elts:
                        val = _get_constant_value(elt)
                        if val:
                            methods.append(val.upper())
            elif keyword.arg == 'tags':
                if isinstance(keyword.value, ast.List):
                    for elt in keyword.value.elts:
                        val = _get_constant_value(elt)
                        if val:
                            tags.append(val)
            elif keyword.arg == 'response_model':
                response_model = _get_name(keyword.value)
            elif keyword.arg == 'status_code':
                status_code = _get_constant_value(keyword.value)
            elif keyword.arg == 'summary':
                pass  # Could extract for docs
            elif keyword.arg == 'description':
                pass  # Could extract for docs

        if not methods:
            methods = ['GET']

        # Determine blueprint/router association
        blueprint_id = None
        router_prefix = ''
        if router_var and router_var in self._router_vars:
            router_info = self._router_vars[router_var]
            blueprint_id = router_info.get('id')
            router_prefix = router_info.get('prefix', '')

        # Build full URL
        full_url = _normalize_url(router_prefix, url_pattern)

        # Extract path parameters from FastAPI path syntax: {item_id}
        path_params = self._extract_path_params(url_pattern)

        # Extract query parameters from function signature
        query_params = self._extract_query_params(func_node, path_params)

        self._route_counter += 1
        route_id = f'route_{self.module_name}_{func_node.name}_{func_node.lineno}'

        return {
            'id': route_id,
            'type': 'route',
            'url_pattern': url_pattern,
            'full_url': full_url,
            'methods': methods,
            'blueprint_id': blueprint_id,
            'blueprint_var': router_var,
            'tags': tags,
            'response_model': response_model,
            'status_code': status_code,
            'is_async': False,  # Will be overridden in _process_function
            'parameters': {
                'path_params': path_params,
                'query_params': query_params,
            },
        }

    def _extract_router(self, target: ast.Name, call: ast.Call,
                        lineno: int) -> Dict:
        """Extract APIRouter information from its constructor."""
        prefix = ''
        tags = []

        for keyword in call.keywords:
            if keyword.arg == 'prefix':
                val = _get_constant_value(keyword.value)
                if val:
                    prefix = val
            elif keyword.arg == 'tags':
                if isinstance(keyword.value, ast.List):
                    for elt in keyword.value.elts:
                        val = _get_constant_value(elt)
                        if val:
                            tags.append(val)

        router_id = f'blueprint_{target.id}_{lineno}'

        return {
            'id': router_id,
            'type': 'blueprint',
            'name': target.id,
            'variable': target.id,
            'prefix': prefix,
            'url_prefix': prefix,
            'tags': tags,
            'file_path': self.filepath,
            'line_number': lineno,
            'route_count': 0,
        }

    def _check_include_router(self, call: ast.Call):
        """Check if a call is app.include_router() and extract info."""
        if not isinstance(call.func, ast.Attribute):
            return
        if call.func.attr != 'include_router':
            return

        obj_name = _get_name(call.func.value)
        if obj_name not in self._app_vars:
            # Could be any object, still process it
            pass

        router_var = None
        prefix = None
        tags = []

        # First arg: router variable
        if call.args:
            router_var = _get_name(call.args[0])

        # Keyword arguments
        for keyword in call.keywords:
            if keyword.arg == 'prefix':
                val = _get_constant_value(keyword.value)
                if val is not None:
                    prefix = val
            elif keyword.arg == 'tags':
                if isinstance(keyword.value, ast.List):
                    for elt in keyword.value.elts:
                        val = _get_constant_value(elt)
                        if val:
                            tags.append(val)

        self.includes.append({
            'router_var': router_var,
            'prefix': prefix,
            'tags': tags,
            'line_number': call.lineno,
        })

    def _extract_path_params(self, url_pattern: str) -> List[Dict]:
        """Extract path parameters from FastAPI URL pattern.

        Matches {param_name} and {param_name:type} syntax.
        """
        params = []
        for match in re.finditer(r'\{(\w+)(?::([^}]+))?\}', url_pattern):
            name = match.group(1)
            type_hint = match.group(2) or 'string'
            params.append({'name': name, 'type': type_hint})
        return params

    def _extract_query_params(self, func_node: ast.AST,
                              path_params: List[Dict]) -> List[Dict]:
        """Extract query parameters from function signature.

        In FastAPI, function parameters that are not path parameters and
        don't use Depends() are treated as query parameters.
        """
        path_param_names = {p['name'] for p in path_params}
        query_params = []

        for arg in func_node.args.args:
            name = arg.arg
            # Skip 'self', 'cls', and path params
            if name in ('self', 'cls') or name in path_param_names:
                continue

            # Check if parameter has a Depends() default (skip those)
            # We can't easily check defaults matched to specific args in AST,
            # but we can check annotation
            annotation = None
            if arg.annotation:
                annotation = _get_name(arg.annotation)

            # Skip parameters with special FastAPI types
            if annotation in ('Request', 'Response', 'WebSocket',
                              'BackgroundTasks', 'Depends'):
                continue

            param_type = annotation or 'string'
            query_params.append({
                'name': name,
                'type': param_type,
            })

        return query_params

    def _extract_auth_dependencies(self, func_node: ast.AST) -> List[str]:
        """Extract auth-related Depends() from function parameters.

        Detects patterns like:
            def endpoint(current_user: User = Depends(get_current_user)):
            def endpoint(user = Depends(authenticate)):
        """
        auth_deps = []

        # Check all default values for Depends() calls
        defaults = func_node.args.defaults + func_node.args.kw_defaults
        for default in defaults:
            if default is None:
                continue
            if isinstance(default, ast.Call):
                func_name = _get_name(default.func)
                if func_name == 'Depends' and default.args:
                    dep_name = _get_name(default.args[0])
                    if dep_name and dep_name.lower() in {
                            n.lower() for n in AUTH_DEPENDENCY_NAMES}:
                        auth_deps.append(dep_name)
                    elif dep_name and any(
                            kw in dep_name.lower()
                            for kw in ('auth', 'user', 'token', 'permission',
                                       'login', 'jwt', 'verify')):
                        auth_deps.append(dep_name)

        return auth_deps

    def _extract_decorator_dependencies(self, decorator: ast.Call) -> List[str]:
        """Extract auth dependencies from decorator keyword arguments.

        Detects: @app.get("/", dependencies=[Depends(verify_token)])
        """
        auth_deps = []
        for keyword in decorator.keywords:
            if keyword.arg == 'dependencies':
                if isinstance(keyword.value, ast.List):
                    for elt in keyword.value.elts:
                        if isinstance(elt, ast.Call):
                            func_name = _get_name(elt.func)
                            if func_name == 'Depends' and elt.args:
                                dep_name = _get_name(elt.args[0])
                                if dep_name and dep_name.lower() in {
                                        n.lower() for n in AUTH_DEPENDENCY_NAMES}:
                                    auth_deps.append(dep_name)
                                elif dep_name and any(
                                        kw in dep_name.lower()
                                        for kw in ('auth', 'user', 'token',
                                                   'permission', 'login',
                                                   'jwt', 'verify')):
                                    auth_deps.append(dep_name)
        return auth_deps


class FastAPIParser:
    """Parse FastAPI application to extract API route definitions.

    Scans Python files for FastAPI and APIRouter route decorators,
    router inclusion, and dependency injection patterns. Produces a
    standardized api_routes dict that the frontend can render.
    """

    def __init__(self, project_path: str, options: Optional[Dict] = None):
        """Initialize parser with project directory.

        Args:
            project_path: Root directory of FastAPI project.
            options: Configuration options.
        """
        self.project_path = Path(project_path)
        self.options = options or {}
        self.blueprints: List[Dict] = []
        self.routes: List[Dict] = []

    def parse(self) -> Dict:
        """Main parsing method - orchestrates the analysis.

        Returns:
            Standardized api_routes dict with blueprints, routes, and statistics.
        """
        python_files = self._find_python_files()

        all_visitors = []
        for filepath in python_files:
            visitor = self._parse_file(filepath)
            if visitor:
                all_visitors.append(visitor)

        # Process routers and includes
        for visitor in all_visitors:
            self.blueprints.extend(visitor.routers)
            self.routes.extend(visitor.routes)

        # Apply include_router prefixes
        self._apply_include_prefixes(all_visitors)

        # Update full URLs based on final router prefixes
        self._update_route_urls()

        # Update blueprint route counts
        self._update_blueprint_counts()

        return {
            'analysis_type': 'api_routes',
            'version': '1.0',
            'project_path': str(self.project_path),
            'blueprints': self.blueprints,
            'routes': self.routes,
            'statistics': self._calculate_statistics(),
        }

    def _find_python_files(self) -> List[Path]:
        """Find all Python files in the project directory."""
        skip_dirs = {
            '__pycache__', '.git', '.venv', 'venv', 'env', 'node_modules',
            '.pytest_cache', '.tox', 'dist', 'build', '.eggs', 'tests',
            'test', 'migrations', 'static', 'templates',
        }
        python_files = []

        for root, dirs, files in os.walk(self.project_path):
            dirs[:] = [d for d in dirs if d not in skip_dirs]
            for file in files:
                if file.endswith('.py'):
                    python_files.append(Path(root) / file)

        return python_files

    def _parse_file(self, filepath: Path) -> Optional[FastAPIRouteVisitor]:
        """Parse a single Python file for FastAPI routes."""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                source = f.read()

            tree = ast.parse(source, filename=str(filepath))

            rel_path = filepath.relative_to(self.project_path)
            module_name = str(rel_path.with_suffix('')).replace(os.sep, '.')

            visitor = FastAPIRouteVisitor(str(filepath), module_name)
            visitor.visit(tree)

            return visitor

        except SyntaxError as e:
            print(f"Syntax error in {filepath}: {e}")
        except Exception as e:
            print(f"Error parsing {filepath}: {e}")
        return None

    def _apply_include_prefixes(self, visitors: List[FastAPIRouteVisitor]):
        """Apply prefix overrides from include_router() calls.

        When app.include_router(router, prefix="/api/v1") is called,
        the prefix from include_router takes precedence over the
        APIRouter(prefix=...) definition.
        """
        for visitor in visitors:
            for include in visitor.includes:
                router_var = include.get('router_var')
                include_prefix = include.get('prefix')

                if not router_var:
                    continue

                # Find the matching blueprint and update its prefix
                for bp in self.blueprints:
                    if bp.get('variable') == router_var or bp.get('name') == router_var:
                        if include_prefix is not None:
                            bp['prefix'] = include_prefix
                            bp['url_prefix'] = include_prefix

                        # Merge tags
                        include_tags = include.get('tags', [])
                        if include_tags:
                            existing = set(bp.get('tags', []))
                            bp['tags'] = list(existing | set(include_tags))
                        break

    def _update_route_urls(self):
        """Update route full URLs based on final router prefixes."""
        # Build router prefix lookup
        prefix_map = {}
        for bp in self.blueprints:
            prefix_map[bp['id']] = bp.get('prefix', '')

        for route in self.routes:
            bp_id = route.get('blueprint_id')
            if bp_id and bp_id in prefix_map:
                prefix = prefix_map[bp_id]
                route['full_url'] = _normalize_url(prefix, route['url_pattern'])

    def _update_blueprint_counts(self):
        """Update route_count for each blueprint."""
        counts = {}
        for route in self.routes:
            bp_id = route.get('blueprint_id')
            if bp_id:
                counts[bp_id] = counts.get(bp_id, 0) + 1
        for bp in self.blueprints:
            bp['route_count'] = counts.get(bp['id'], 0)

    def _calculate_statistics(self) -> Dict:
        """Calculate statistics about the analyzed routes."""
        routes_by_method = {}
        for route in self.routes:
            for method in route.get('methods', ['GET']):
                routes_by_method[method] = routes_by_method.get(method, 0) + 1

        protected = sum(
            1 for r in self.routes
            if r.get('security', {}).get('requires_auth', False)
        )

        return {
            'total_blueprints': len(self.blueprints),
            'total_routes': len(self.routes),
            'routes_by_method': routes_by_method,
            'protected_routes': protected,
            'unprotected_routes': len(self.routes) - protected,
        }
