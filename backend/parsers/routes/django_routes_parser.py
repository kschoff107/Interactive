"""
Django URL Routes Parser - Extract API route definitions from Django URL configurations.

Uses Python's AST module for static code analysis without executing code.
Detects path(), re_path(), include(), and Django REST Framework router registrations.
"""

import ast
import logging
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


# Standard HTTP methods
ALL_METHODS = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS']

# DRF ViewSet action -> (method, url_suffix, action_name)
VIEWSET_ACTIONS = [
    ('GET', '', 'list'),
    ('POST', '', 'create'),
    ('GET', '/{id}', 'retrieve'),
    ('PUT', '/{id}', 'update'),
    ('PATCH', '/{id}', 'partial_update'),
    ('DELETE', '/{id}', 'destroy'),
]


def _get_constant_value(node: ast.AST) -> Optional:
    """Extract a constant value from an AST node, or None if not constant."""
    if isinstance(node, ast.Constant):
        return node.value
    return None


def _get_name(node: ast.AST) -> Optional[str]:
    """Get a simple name from a Name or Attribute node."""
    if isinstance(node, ast.Name):
        return node.id
    elif isinstance(node, ast.Attribute):
        return node.attr
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


class DjangoURLVisitor(ast.NodeVisitor):
    """AST visitor that extracts Django URL configuration from a single file.

    Detects:
        - path('url/', view, name='name') calls
        - re_path(r'^url/', view, name='name') calls
        - include('app.urls') references
        - router.register(r'prefix', ViewSet) for DRF
        - urlpatterns = [...] lists
    """

    def __init__(self, filepath: str, module_name: str):
        self.filepath = filepath
        self.module_name = module_name
        self.routes: List[Dict] = []
        self.includes: List[Dict] = []
        self.router_registrations: List[Dict] = []
        self._router_vars: Set[str] = set()
        self._route_counter = 0

    def visit_Assign(self, node: ast.Assign):
        """Detect router instantiation and urlpatterns assignments."""
        for target in node.targets:
            if isinstance(target, ast.Name):
                # Detect router = DefaultRouter() or SimpleRouter()
                if isinstance(node.value, ast.Call):
                    func_name = _get_name(node.value.func)
                    if func_name in ('DefaultRouter', 'SimpleRouter',
                                     'DefaultRouter', 'SimpleRouter'):
                        self._router_vars.add(target.id)

                # Detect urlpatterns = [...]
                if target.id == 'urlpatterns' and isinstance(node.value, ast.List):
                    self._process_urlpatterns(node.value)

        self.generic_visit(node)

    def visit_AugAssign(self, node: ast.AugAssign):
        """Detect urlpatterns += [...] augmented assignments."""
        if (isinstance(node.target, ast.Name) and
                node.target.id == 'urlpatterns' and
                isinstance(node.value, ast.List)):
            self._process_urlpatterns(node.value)
        self.generic_visit(node)

    def visit_Expr(self, node: ast.Expr):
        """Detect router.register() calls as standalone expressions."""
        if isinstance(node.value, ast.Call):
            self._check_router_register(node.value)
        # Do NOT call generic_visit here to avoid visiting the Call node
        # again through visit_Call (which would cause duplication).

    def _check_router_register(self, call: ast.Call):
        """Check if a call is router.register() and extract the registration."""
        if not isinstance(call.func, ast.Attribute):
            return
        if call.func.attr != 'register':
            return

        # Check if the object is a known router variable
        obj_name = _get_name(call.func.value)
        if obj_name not in self._router_vars:
            return

        prefix = None
        viewset_name = None
        basename = None

        # First arg: URL prefix
        if len(call.args) >= 1:
            val = _get_constant_value(call.args[0])
            if val is not None:
                prefix = val

        # Second arg: ViewSet class
        if len(call.args) >= 2:
            viewset_name = _get_name(call.args[1])

        # Optional basename keyword
        for keyword in call.keywords:
            if keyword.arg == 'basename':
                val = _get_constant_value(keyword.value)
                if val:
                    basename = val

        if prefix is not None and viewset_name:
            self.router_registrations.append({
                'prefix': prefix,
                'viewset': viewset_name,
                'basename': basename or viewset_name.lower().replace('viewset', ''),
                'line_number': call.lineno,
            })

    def _process_urlpatterns(self, list_node: ast.List):
        """Process a urlpatterns = [...] list."""
        for elt in list_node.elts:
            if isinstance(elt, ast.Call):
                self._process_url_call(elt)

    def _process_url_call(self, call: ast.Call):
        """Process a single path() or re_path() call."""
        func_name = _get_name(call.func)
        if func_name not in ('path', 're_path', 'url'):
            return

        is_regex = func_name in ('re_path', 'url')

        # Extract URL pattern (first argument)
        url_pattern = ''
        if call.args:
            val = _get_constant_value(call.args[0])
            if val is not None:
                url_pattern = val

        # Check if second argument is include()
        view_func = None
        include_target = None
        if len(call.args) >= 2:
            second_arg = call.args[1]
            if isinstance(second_arg, ast.Call):
                inc_name = _get_name(second_arg.func)
                if inc_name == 'include':
                    include_target = self._parse_include(second_arg)
                else:
                    view_func = inc_name
            elif isinstance(second_arg, ast.Attribute):
                # views.user_list
                view_func = f'{_get_name(second_arg.value)}.{second_arg.attr}' if isinstance(
                    second_arg.value, ast.Name) else second_arg.attr
            elif isinstance(second_arg, ast.Name):
                view_func = second_arg.id

        # Check keyword arguments
        route_name = None
        kwargs = {}
        for keyword in call.keywords:
            if keyword.arg == 'name':
                route_name = _get_constant_value(keyword.value)
            elif keyword.arg == 'kwargs':
                pass  # Could extract default kwargs

        # Also check for view/name as keyword args
        for keyword in call.keywords:
            if keyword.arg == 'view' and view_func is None:
                view_func = _get_name(keyword.value)

        if include_target:
            self.includes.append({
                'url_prefix': url_pattern,
                'target': include_target,
                'is_regex': is_regex,
                'line_number': call.lineno,
            })
        else:
            self._route_counter += 1
            route_id = f'route_{self.module_name}_{self._route_counter}_{call.lineno}'

            # Convert Django path converters to display format
            display_pattern = url_pattern
            if not is_regex:
                # <int:pk> -> {pk}, <str:slug> -> {slug}
                display_pattern = re.sub(
                    r'<(\w+:)?(\w+)>', r'{\2}', url_pattern)

            self.routes.append({
                'id': route_id,
                'type': 'route',
                'url_pattern': url_pattern,
                'full_url': '/' + url_pattern.lstrip('/') if url_pattern else '/',
                'display_url': '/' + display_pattern.lstrip('/') if display_pattern else '/',
                'methods': ALL_METHODS if view_func else ['GET'],
                'function_name': view_func or '',
                'route_name': route_name,
                'is_regex': is_regex,
                'blueprint_id': None,
                'parameters': {
                    'path_params': self._extract_path_params(url_pattern, is_regex),
                    'query_params': [],
                },
                'security': {
                    'requires_auth': False,
                    'auth_decorators': [],
                },
                'file_path': self.filepath,
                'module': self.module_name,
                'line_number': call.lineno,
                'docstring': None,
            })

    def _parse_include(self, call: ast.Call) -> Dict:
        """Parse an include() call.

        Handles:
            include('app.urls')
            include(('app.urls', 'app'), namespace='app')
            include(router.urls)
        """
        target = {
            'module': None,
            'namespace': None,
            'app_name': None,
        }

        if call.args:
            first_arg = call.args[0]
            if isinstance(first_arg, ast.Constant):
                target['module'] = first_arg.value
            elif isinstance(first_arg, ast.Tuple) and len(first_arg.elts) >= 1:
                # include(('app.urls', 'app'))
                module_val = _get_constant_value(first_arg.elts[0])
                if module_val:
                    target['module'] = module_val
                if len(first_arg.elts) >= 2:
                    app_val = _get_constant_value(first_arg.elts[1])
                    if app_val:
                        target['app_name'] = app_val
            elif isinstance(first_arg, ast.Attribute):
                # router.urls
                obj = _get_name(first_arg.value)
                if obj and first_arg.attr == 'urls':
                    target['module'] = f'{obj}.urls'

        for keyword in call.keywords:
            if keyword.arg == 'namespace':
                val = _get_constant_value(keyword.value)
                if val:
                    target['namespace'] = val

        return target

    def _extract_path_params(self, url_pattern: str,
                             is_regex: bool) -> List[Dict]:
        """Extract path parameters from URL pattern."""
        params = []
        if is_regex:
            # Named groups: (?P<name>pattern)
            for match in re.finditer(r'\(\?P<(\w+)>[^)]+\)', url_pattern):
                params.append({'name': match.group(1), 'type': 'string'})
        else:
            # Django path converters: <int:pk>, <str:slug>, <pk>
            for match in re.finditer(r'<(\w+:)?(\w+)>', url_pattern):
                type_hint = match.group(1)
                name = match.group(2)
                param_type = type_hint.rstrip(':') if type_hint else 'string'
                params.append({'name': name, 'type': param_type})
        return params


class DjangoRoutesParser:
    """Parse Django project to extract API route definitions from URL configurations.

    Scans urls.py files for path(), re_path(), include(), and DRF router
    registrations. Produces a standardized api_routes dict that the frontend
    can render.
    """

    def __init__(self, project_path: str, options: Optional[Dict] = None):
        """Initialize parser with project directory.

        Args:
            project_path: Root directory of Django project.
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
        python_files = self._find_url_files()

        all_visitors = []
        for filepath in python_files:
            visitor = self._parse_file(filepath)
            if visitor:
                all_visitors.append(visitor)

        # Process includes as blueprints
        for visitor in all_visitors:
            for include in visitor.includes:
                bp = self._create_blueprint_from_include(include, visitor)
                if bp:
                    self.blueprints.append(bp)

            # Process DRF router registrations
            for reg in visitor.router_registrations:
                bp, routes = self._expand_viewset(reg, visitor)
                if bp:
                    self.blueprints.append(bp)
                self.routes.extend(routes)

            # Add direct routes
            self.routes.extend(visitor.routes)

        # Assign routes to blueprints based on URL prefix matching
        self._assign_routes_to_blueprints()

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

    def _find_url_files(self) -> List[Path]:
        """Find URL configuration files in the project.

        Primarily looks for urls.py files, but also scans other Python files
        that might contain URL patterns (e.g. routers.py, api.py).
        """
        skip_dirs = {
            '__pycache__', '.git', '.venv', 'venv', 'env', 'node_modules',
            '.pytest_cache', '.tox', 'dist', 'build', '.eggs',
            'migrations', 'static', 'templates', 'media',
        }
        url_files = []
        other_py_files = []

        for root, dirs, files in os.walk(self.project_path):
            dirs[:] = [d for d in dirs if d not in skip_dirs]
            for file in files:
                if file.endswith('.py'):
                    filepath = Path(root) / file
                    if file in ('urls.py', 'routers.py', 'api_urls.py'):
                        url_files.append(filepath)
                    else:
                        other_py_files.append(filepath)

        # If no explicit URL files found, scan all Python files
        if not url_files:
            return other_py_files

        return url_files

    def _parse_file(self, filepath: Path) -> Optional[DjangoURLVisitor]:
        """Parse a single Python file for URL patterns."""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                source = f.read()

            tree = ast.parse(source, filename=str(filepath))

            rel_path = filepath.relative_to(self.project_path)
            module_name = str(rel_path.with_suffix('')).replace(os.sep, '.')

            visitor = DjangoURLVisitor(str(filepath), module_name)
            visitor.visit(tree)

            return visitor

        except SyntaxError as e:
            logger.warning("Failed to parse %s: %s", filepath, e)
        except Exception as e:
            logger.warning("Failed to parse %s: %s", filepath, e)
        return None

    def _create_blueprint_from_include(self, include: Dict,
                                       visitor: DjangoURLVisitor) -> Optional[Dict]:
        """Create a blueprint entry from an include() reference."""
        target = include['target']
        module = target.get('module', '')
        namespace = target.get('namespace') or target.get('app_name')

        if not module and not namespace:
            return None

        name = namespace or module.split('.')[-1] if module else 'unknown'
        bp_id = f'blueprint_{name}_{include["line_number"]}'

        return {
            'id': bp_id,
            'type': 'blueprint',
            'name': name,
            'module': module,
            'namespace': namespace,
            'url_prefix': '/' + include['url_prefix'].strip('/') if include['url_prefix'] else '',
            'file_path': visitor.filepath,
            'line_number': include['line_number'],
            'route_count': 0,
        }

    def _expand_viewset(self, registration: Dict,
                        visitor: DjangoURLVisitor) -> Tuple[Optional[Dict], List[Dict]]:
        """Expand a DRF ViewSet registration into individual routes.

        A ViewSet registered with router.register(r'users', UserViewSet)
        creates routes for list, create, retrieve, update, partial_update,
        and destroy actions.
        """
        prefix = registration['prefix'].strip('/')
        viewset = registration['viewset']
        basename = registration['basename']
        line = registration['line_number']

        # Create a blueprint for the viewset
        bp_id = f'blueprint_viewset_{basename}_{line}'
        blueprint = {
            'id': bp_id,
            'type': 'blueprint',
            'name': f'{viewset}',
            'viewset': viewset,
            'url_prefix': '/' + prefix if prefix else '/',
            'file_path': visitor.filepath,
            'line_number': line,
            'route_count': 0,
        }

        routes = []
        for method, suffix, action in VIEWSET_ACTIONS:
            url = prefix + suffix
            display_url = '/' + url.lstrip('/') if url else '/'
            route_id = f'route_viewset_{basename}_{action}_{line}'

            path_params = []
            if '{id}' in display_url:
                path_params.append({'name': 'id', 'type': 'int'})

            routes.append({
                'id': route_id,
                'type': 'route',
                'url_pattern': url,
                'full_url': display_url,
                'display_url': display_url,
                'methods': [method],
                'function_name': f'{viewset}.{action}',
                'route_name': f'{basename}-{action}' if action != 'list' else f'{basename}-list',
                'is_regex': False,
                'blueprint_id': bp_id,
                'parameters': {
                    'path_params': path_params,
                    'query_params': [],
                },
                'security': {
                    'requires_auth': False,
                    'auth_decorators': [],
                },
                'file_path': visitor.filepath,
                'module': visitor.module_name,
                'line_number': line,
                'docstring': None,
            })

        return blueprint, routes

    def _assign_routes_to_blueprints(self):
        """Assign routes to blueprints based on URL prefix matching."""
        for route in self.routes:
            if route.get('blueprint_id'):
                continue
            full_url = route.get('full_url', '')
            best_match = None
            best_len = 0
            for bp in self.blueprints:
                prefix = bp.get('url_prefix', '')
                if prefix and full_url.startswith(prefix) and len(prefix) > best_len:
                    best_match = bp
                    best_len = len(prefix)
            if best_match:
                route['blueprint_id'] = best_match['id']

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
