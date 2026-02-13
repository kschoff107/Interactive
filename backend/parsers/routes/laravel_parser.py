"""
Laravel routes parser.

Parses Laravel route files (routes/api.php, routes/web.php) to extract
API route definitions using regex-based analysis.
"""

import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from ..base import (
    BaseRoutesParser, find_source_files, read_file_safe,
    extract_block_body, line_number_at, strip_comments_only,
)

# ---------------------------------------------------------------------------
# Compiled regex patterns
# ---------------------------------------------------------------------------

# Route::get('/path', [Controller::class, 'method'])
# Route::get('/path', 'Controller@method')
_ROUTE_METHOD_RE = re.compile(
    r"Route\s*::\s*(get|post|put|patch|delete|options|any)\s*\("
    r"\s*['\"]([^'\"]+)['\"]"
    r"(?:\s*,\s*(?:"
    r"\[\s*(\w+)\s*::\s*class\s*,\s*['\"](\w+)['\"]\s*\]"  # [Controller::class, 'method']
    r"|['\"](\w+)@(\w+)['\"]"                                  # 'Controller@method'
    r"|(\w+)\s*::\s*class"                                     # Controller::class (invokable)
    r"|['\"]([^'\"]+)['\"]"                                    # 'Controller'
    r"))?",
    re.MULTILINE,
)

# Route::resource('posts', PostController::class)
# Route::apiResource('comments', CommentController::class)
_RESOURCE_RE = re.compile(
    r"Route\s*::\s*(resource|apiResource)\s*\(\s*['\"](\w+)['\"]"
    r"(?:\s*,\s*(\w+)\s*::\s*class)?"
    r"(?:\s*\)\s*->\s*only\s*\(\s*\[([^\]]*)\]\s*\))?"
    r"(?:\s*\)\s*->\s*except\s*\(\s*\[([^\]]*)\]\s*\))?",
    re.MULTILINE,
)

# Route::middleware('auth:sanctum')->group(function () {
_MIDDLEWARE_GROUP_RE = re.compile(
    r"Route\s*::\s*middleware\s*\(\s*['\"]([^'\"]+)['\"]\s*\)"
    r"\s*->\s*group\s*\(",
    re.MULTILINE,
)

# Route::prefix('api/v1')->group(function () {
_PREFIX_GROUP_RE = re.compile(
    r"Route\s*::\s*prefix\s*\(\s*['\"]([^'\"]+)['\"]\s*\)"
    r"(?:\s*->\s*middleware\s*\(\s*['\"]([^'\"]+)['\"]\s*\))?"
    r"\s*->\s*group\s*\(",
    re.MULTILINE,
)

# Route::group(['prefix' => 'api', 'middleware' => 'auth'], function () {
_GROUP_ARRAY_RE = re.compile(
    r"Route\s*::\s*group\s*\(\s*\[([^\]]*)\]\s*,\s*function",
    re.MULTILINE,
)

# Extract prefix from group array: 'prefix' => 'api'
_GROUP_PREFIX_RE = re.compile(r"['\"]prefix['\"]\s*=>\s*['\"]([^'\"]+)['\"]")
_GROUP_MIDDLEWARE_RE = re.compile(r"['\"]middleware['\"]\s*=>\s*['\"]([^'\"]+)['\"]")

# String items in arrays
_STRING_ITEM_RE = re.compile(r"['\"](\w+)['\"]")

# Auth-related middleware names
_AUTH_MIDDLEWARES = frozenset({
    'auth', 'auth:sanctum', 'auth:api', 'auth:web',
    'auth.basic', 'verified', 'can', 'password.confirm',
})

# Standard resource actions
_RESOURCE_ACTIONS = {
    'index':   ('GET',    '',          'list all'),
    'create':  ('GET',    '/create',  'create form'),
    'store':   ('POST',   '',          'store'),
    'show':    ('GET',    '/{id}',    'show one'),
    'edit':    ('GET',    '/{id}/edit', 'edit form'),
    'update':  ('PUT',    '/{id}',    'update'),
    'destroy': ('DELETE', '/{id}',    'delete'),
}

# API resource actions (no create/edit form routes)
_API_RESOURCE_ACTIONS = {
    'index':   ('GET',    '',          'list all'),
    'store':   ('POST',   '',          'store'),
    'show':    ('GET',    '/{id}',    'show one'),
    'update':  ('PUT',    '/{id}',    'update'),
    'destroy': ('DELETE', '/{id}',    'delete'),
}


class LaravelParser(BaseRoutesParser):
    """Parse Laravel route definitions from route files."""

    FILE_EXTENSIONS = ['.php']

    def parse(self) -> Dict:
        """Parse Laravel routes from the project.

        Returns:
            Standardized API routes dict.
        """
        route_files = self._find_route_files()

        for fpath in route_files:
            content = read_file_safe(fpath)
            if not content:
                continue
            self._parse_routes_file(content, fpath)

        # Update blueprint route counts
        self._update_blueprint_counts()

        return self.make_routes_result()

    def _find_route_files(self) -> List[str]:
        """Find Laravel route files."""
        results = []
        routes_dir = os.path.join(str(self.project_path), 'routes')

        if os.path.isdir(routes_dir):
            for fname in ('api.php', 'web.php', 'channels.php', 'console.php'):
                fpath = os.path.join(routes_dir, fname)
                if os.path.isfile(fpath):
                    results.append(fpath)
        else:
            # Fallback: search for route files
            all_php = find_source_files(str(self.project_path), ['.php'])
            for fpath in all_php:
                basename = os.path.basename(fpath)
                if basename in ('api.php', 'web.php') or 'routes' in fpath.lower():
                    results.append(fpath)

        return results

    def _parse_routes_file(self, content: str, file_path: str):
        """Parse a single route file."""
        stripped = strip_comments_only(content, 'php')
        self._parse_block(stripped, content, file_path, prefix='', auth=False)

    def _parse_block(self, stripped: str, original: str, file_path: str,
                     prefix: str, auth: bool):
        """Parse route definitions within a block, handling groups.

        Processes group constructs one at a time, blanking each consumed
        region to prevent its content from being re-parsed at this level.
        """
        remaining = stripped

        # --- Middleware groups (one at a time) ---
        while True:
            match = _MIDDLEWARE_GROUP_RE.search(remaining)
            if not match:
                break

            middleware = match.group(1)
            is_auth = middleware in _AUTH_MIDDLEWARES or middleware.startswith('auth')
            start_pos = match.end()

            body, body_start, body_end = extract_block_body(remaining, start_pos - 1)
            if not body:
                blanked = re.sub(r'[^\n]', ' ', remaining[match.start():match.end()])
                remaining = remaining[:match.start()] + blanked + remaining[match.end():]
                continue

            blueprint_id = f'middleware_{middleware.replace(":", "_")}_{len(self.blueprints)}'
            self.blueprints.append({
                'id': blueprint_id,
                'type': 'middleware_group',
                'name': middleware,
                'url_prefix': prefix,
                'middleware': middleware,
                'file_path': file_path,
                'line_number': line_number_at(original, match.start()),
                'route_count': 0,
            })

            self._parse_block(
                body, original, file_path,
                prefix=prefix,
                auth=auth or is_auth,
            )

            # Blank the entire group region
            # body_end + 1 to include the closing brace, then skip );
            blank_end = body_end + 1
            # Skip past closing ");" or "});"
            close_match = re.compile(r'\s*\)\s*;?').match(remaining, blank_end)
            if close_match:
                blank_end = close_match.end()
            blanked = re.sub(r'[^\n]', ' ', remaining[match.start():blank_end])
            remaining = remaining[:match.start()] + blanked + remaining[blank_end:]

        # --- Prefix groups (one at a time) ---
        while True:
            match = _PREFIX_GROUP_RE.search(remaining)
            if not match:
                break

            group_prefix = match.group(1)
            middleware = match.group(2)
            is_auth = (
                middleware in _AUTH_MIDDLEWARES or middleware.startswith('auth')
            ) if middleware else False
            start_pos = match.end()

            body, body_start, body_end = extract_block_body(remaining, start_pos - 1)
            if not body:
                blanked = re.sub(r'[^\n]', ' ', remaining[match.start():match.end()])
                remaining = remaining[:match.start()] + blanked + remaining[match.end():]
                continue

            full_prefix = f'{prefix}/{group_prefix}'.rstrip('/')

            blueprint_id = f'prefix_{group_prefix.replace("/", "_")}_{len(self.blueprints)}'
            self.blueprints.append({
                'id': blueprint_id,
                'type': 'prefix_group',
                'name': group_prefix,
                'url_prefix': full_prefix,
                'file_path': file_path,
                'line_number': line_number_at(original, match.start()),
                'route_count': 0,
            })

            self._parse_block(
                body, original, file_path,
                prefix=full_prefix,
                auth=auth or is_auth,
            )

            blank_end = body_end + 1
            close_match = re.compile(r'\s*\)\s*;?').match(remaining, blank_end)
            if close_match:
                blank_end = close_match.end()
            blanked = re.sub(r'[^\n]', ' ', remaining[match.start():blank_end])
            remaining = remaining[:match.start()] + blanked + remaining[blank_end:]

        # --- Array-style groups (one at a time) ---
        while True:
            match = _GROUP_ARRAY_RE.search(remaining)
            if not match:
                break

            group_opts = match.group(1)
            group_prefix_match = _GROUP_PREFIX_RE.search(group_opts)
            group_mw_match = _GROUP_MIDDLEWARE_RE.search(group_opts)

            group_prefix = group_prefix_match.group(1) if group_prefix_match else ''
            middleware = group_mw_match.group(1) if group_mw_match else None
            is_auth = (
                middleware in _AUTH_MIDDLEWARES or middleware.startswith('auth')
            ) if middleware else False

            start_pos = match.end()
            body, body_start, body_end = extract_block_body(remaining, start_pos - 1)
            if not body:
                blanked = re.sub(r'[^\n]', ' ', remaining[match.start():match.end()])
                remaining = remaining[:match.start()] + blanked + remaining[match.end():]
                continue

            full_prefix = f'{prefix}/{group_prefix}'.rstrip('/') if group_prefix else prefix

            self._parse_block(
                body, original, file_path,
                prefix=full_prefix,
                auth=auth or is_auth,
            )

            blank_end = body_end + 1
            close_match = re.compile(r'\s*\)\s*;?').match(remaining, blank_end)
            if close_match:
                blank_end = close_match.end()
            blanked = re.sub(r'[^\n]', ' ', remaining[match.start():blank_end])
            remaining = remaining[:match.start()] + blanked + remaining[blank_end:]

        stripped = remaining  # use blanked version for route parsing

        # --- Individual routes ---
        for match in _ROUTE_METHOD_RE.finditer(stripped):
            method = match.group(1).upper()
            if method == 'ANY':
                methods = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE']
            else:
                methods = [method]

            path = match.group(2)
            controller = match.group(3) or match.group(5) or match.group(7) or match.group(8)
            action = match.group(4) or match.group(6)

            full_path = f'{prefix}/{path.lstrip("/")}'.rstrip('/')
            if not full_path:
                full_path = '/'

            route_id = f'route_{method.lower()}_{full_path.replace("/", "_")}_{len(self.routes)}'
            self.routes.append({
                'id': route_id,
                'type': 'route',
                'url_pattern': path,
                'full_url': full_path,
                'methods': methods,
                'controller': controller,
                'action': action,
                'function_name': f'{controller}@{action}' if controller and action else controller,
                'file_path': file_path,
                'line_number': line_number_at(original, match.start()),
                'blueprint_id': self.blueprints[-1]['id'] if self.blueprints else None,
                'parameters': {
                    'path_params': self._extract_path_params(full_path),
                    'query_params': [],
                },
                'security': {
                    'requires_auth': auth,
                    'auth_decorators': [],
                },
            })

        # --- Resource routes ---
        for match in _RESOURCE_RE.finditer(stripped):
            resource_type = match.group(1)
            resource_name = match.group(2)
            controller = match.group(3)
            only_str = match.group(4)
            except_str = match.group(5)

            if resource_type == 'apiResource':
                all_actions = _API_RESOURCE_ACTIONS
            else:
                all_actions = _RESOURCE_ACTIONS

            actions = self._resolve_actions(only_str, except_str, all_actions)

            resource_prefix = f'{prefix}/{resource_name}'

            for action_name in actions:
                method, path_suffix, description = all_actions[action_name]
                full_path = resource_prefix + path_suffix

                route_id = f'route_{resource_name}_{action_name}_{len(self.routes)}'
                self.routes.append({
                    'id': route_id,
                    'type': 'route',
                    'url_pattern': f'/{resource_name}{path_suffix}',
                    'full_url': full_path,
                    'methods': [method],
                    'controller': controller or resource_name.title() + 'Controller',
                    'action': action_name,
                    'function_name': action_name,
                    'file_path': file_path,
                    'line_number': line_number_at(original, match.start()),
                    'blueprint_id': self.blueprints[-1]['id'] if self.blueprints else None,
                    'parameters': {
                        'path_params': self._extract_path_params(full_path),
                        'query_params': [],
                    },
                    'security': {
                        'requires_auth': auth,
                        'auth_decorators': [],
                    },
                })

    def _resolve_actions(self, only_str: Optional[str],
                         except_str: Optional[str],
                         all_actions: Dict) -> List[str]:
        """Resolve which actions to generate based on only/except."""
        if only_str:
            only = set(_STRING_ITEM_RE.findall(only_str))
            return [a for a in all_actions if a in only]
        if except_str:
            excluded = set(_STRING_ITEM_RE.findall(except_str))
            return [a for a in all_actions if a not in excluded]
        return list(all_actions.keys())

    def _extract_path_params(self, path: str) -> List[Dict]:
        """Extract path parameters from Laravel-style URL patterns."""
        params = []
        for match in re.finditer(r'\{(\w+)\??}', path):
            params.append({
                'name': match.group(1),
                'type': 'string',
                'optional': '?' in match.group(0),
            })
        return params

    def _update_blueprint_counts(self):
        """Update route_count for each blueprint."""
        counts: Dict[str, int] = {}
        for route in self.routes:
            bp_id = route.get('blueprint_id')
            if bp_id:
                counts[bp_id] = counts.get(bp_id, 0) + 1

        for bp in self.blueprints:
            bp['route_count'] = counts.get(bp['id'], 0)
