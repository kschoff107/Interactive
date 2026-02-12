"""
Go Gin/Echo routes parser.

Parses Go source files for Gin and Echo framework route definitions
using regex-based analysis.
"""

import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from ..base import (
    BaseRoutesParser, find_source_files, read_file_safe,
    line_number_at,
)

# Custom comment-only stripping for Go that preserves string literals.
# Gin/Echo route definitions use strings for paths and handler references.
# Standard strip_comments('go') removes these strings via c_family patterns.
_GO_COMMENT_ONLY_RE = re.compile(
    r'//[^\n]*'              # single-line comments
    r'|/\*.*?\*/',           # multi-line comments
    re.DOTALL,
)


def _strip_go_comments_only(content: str) -> str:
    """Strip Go comments while preserving string literals."""
    return _GO_COMMENT_ONLY_RE.sub(
        lambda m: re.sub(r'[^\n]', ' ', m.group(0)),
        content,
    )

# ---------------------------------------------------------------------------
# Compiled regex patterns
# ---------------------------------------------------------------------------

# Router/engine initialization:
#   r := gin.Default()  /  r := gin.New()  /  e := echo.New()
_GIN_INIT_RE = re.compile(
    r'(\w+)\s*:?=\s*gin\s*\.\s*(?:Default|New)\s*\(',
    re.MULTILINE,
)
_ECHO_INIT_RE = re.compile(
    r'(\w+)\s*:?=\s*echo\s*\.\s*New\s*\(',
    re.MULTILINE,
)

# Route group:
#   api := r.Group("/api/v1")
_GROUP_RE = re.compile(
    r'(\w+)\s*:?=\s*(\w+)\s*\.\s*Group\s*\(\s*["\']([^"\']+)["\']\s*\)',
    re.MULTILINE,
)

# Individual route (Gin and Echo):
#   r.GET("/path", handler)
#   api.POST("/path", handler, middleware)
_ROUTE_RE = re.compile(
    r'(\w+)\s*\.\s*(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS|Any|Match)'
    r'\s*\(\s*["\']([^"\']*)["\']'
    r'(?:\s*,\s*(\w+))?',
    re.MULTILINE,
)

# Middleware:
#   r.Use(AuthMiddleware())
#   api.Use(middleware.Auth())
_USE_RE = re.compile(
    r'(\w+)\s*\.\s*Use\s*\(\s*(\w+)',
    re.MULTILINE,
)

# Echo-specific route methods (same pattern, included for completeness):
#   e.GET("/users", getUsers)
#   e.POST("/users", createUser, authMiddleware)

# Static file serving:
#   r.Static("/assets", "./public")
#   r.StaticFile("/favicon.ico", "./favicon.ico")
_STATIC_RE = re.compile(
    r'(\w+)\s*\.\s*(?:Static|StaticFile|StaticFS)\s*\(\s*["\']([^"\']+)["\']',
    re.MULTILINE,
)

# NoRoute / NoMethod handlers
_NO_ROUTE_RE = re.compile(
    r'(\w+)\s*\.\s*NoRoute\s*\(',
    re.MULTILINE,
)

# Auth-related middleware name patterns
_AUTH_MIDDLEWARE_PATTERNS = re.compile(
    r'[Aa]uth|[Jj][Ww][Tt]|[Tt]oken|[Ss]ession|[Ll]ogin|[Pp]ermission|[Rr]ole',
)


class GinParser(BaseRoutesParser):
    """Parse Go Gin and Echo route definitions."""

    FILE_EXTENSIONS = ['.go']

    def parse(self) -> Dict:
        """Parse Gin/Echo routes from Go source files.

        Returns:
            Standardized API routes dict.
        """
        go_files = find_source_files(str(self.project_path), ['.go'])

        # First pass: collect all router variables, groups, and middleware
        router_vars: Dict[str, str] = {}           # var_name -> type ('gin'/'echo')
        group_vars: Dict[str, Dict] = {}            # var_name -> group info
        middleware_vars: Dict[str, List[str]] = {}   # var_name -> middleware list

        for fpath in go_files:
            content = read_file_safe(fpath)
            if not content:
                continue
            stripped = _strip_go_comments_only(content)

            # Detect router initializations
            for match in _GIN_INIT_RE.finditer(stripped):
                var_name = match.group(1)
                router_vars[var_name] = 'gin'
                middleware_vars[var_name] = []

            for match in _ECHO_INIT_RE.finditer(stripped):
                var_name = match.group(1)
                router_vars[var_name] = 'echo'
                middleware_vars[var_name] = []

            # Detect groups
            for match in _GROUP_RE.finditer(stripped):
                group_var = match.group(1)
                parent_var = match.group(2)
                group_path = match.group(3)

                group_vars[group_var] = {
                    'parent': parent_var,
                    'path': group_path,
                    'file_path': fpath,
                    'line_number': line_number_at(content, match.start()),
                }
                middleware_vars[group_var] = []

            # Detect middleware usage
            for match in _USE_RE.finditer(stripped):
                var_name = match.group(1)
                mw_name = match.group(2)
                if var_name in middleware_vars:
                    middleware_vars[var_name].append(mw_name)
                elif var_name in group_vars:
                    middleware_vars.setdefault(var_name, []).append(mw_name)

        # Resolve group prefixes and create blueprints
        group_prefixes = self._resolve_group_prefixes(
            group_vars, router_vars
        )

        # Create blueprints for groups
        for var_name, info in group_vars.items():
            full_prefix = group_prefixes.get(var_name, info['path'])
            has_auth = self._has_auth_middleware(var_name, middleware_vars, group_vars)

            blueprint_id = f'group_{var_name}_{full_prefix.replace("/", "_")}'
            self.blueprints.append({
                'id': blueprint_id,
                'type': 'route_group',
                'name': var_name,
                'url_prefix': full_prefix,
                'middleware': middleware_vars.get(var_name, []),
                'file_path': info['file_path'],
                'line_number': info['line_number'],
                'route_count': 0,
            })

        # Second pass: parse actual routes
        for fpath in go_files:
            content = read_file_safe(fpath)
            if not content:
                continue
            stripped = _strip_go_comments_only(content)
            self._parse_routes(
                stripped, content, fpath,
                router_vars, group_vars, group_prefixes, middleware_vars,
            )

        # Update blueprint route counts
        self._update_blueprint_counts()

        return self.make_routes_result()

    def _resolve_group_prefixes(self, group_vars: Dict[str, Dict],
                                router_vars: Dict[str, str]) -> Dict[str, str]:
        """Resolve full path prefix for each group by walking the parent chain."""
        prefixes: Dict[str, str] = {}

        def resolve(var_name: str) -> str:
            if var_name in prefixes:
                return prefixes[var_name]
            if var_name in router_vars:
                return ''
            info = group_vars.get(var_name)
            if not info:
                return ''

            parent_prefix = resolve(info['parent'])
            full = f'{parent_prefix}{info["path"]}'.rstrip('/')
            prefixes[var_name] = full
            return full

        for var_name in group_vars:
            resolve(var_name)

        return prefixes

    def _has_auth_middleware(self, var_name: str,
                            middleware_vars: Dict[str, List[str]],
                            group_vars: Dict[str, Dict]) -> bool:
        """Check if a variable or any of its parents have auth middleware."""
        checked = set()
        current = var_name

        while current and current not in checked:
            checked.add(current)
            for mw in middleware_vars.get(current, []):
                if _AUTH_MIDDLEWARE_PATTERNS.search(mw):
                    return True
            # Walk up to parent
            info = group_vars.get(current)
            if info:
                current = info['parent']
            else:
                break

        return False

    def _parse_routes(self, stripped: str, original: str, file_path: str,
                      router_vars: Dict[str, str],
                      group_vars: Dict[str, Dict],
                      group_prefixes: Dict[str, str],
                      middleware_vars: Dict[str, List[str]]):
        """Parse individual route definitions from a file."""

        for match in _ROUTE_RE.finditer(stripped):
            var_name = match.group(1)
            method = match.group(2).upper()
            path = match.group(3)
            handler = match.group(4)

            # Determine the full path prefix
            if var_name in group_prefixes:
                prefix = group_prefixes[var_name]
            elif var_name in router_vars:
                prefix = ''
            else:
                # Unknown variable, try to use as-is
                prefix = ''

            full_path = f'{prefix}{path}'.rstrip('/')
            if not full_path:
                full_path = '/'

            # Determine methods
            if method == 'ANY':
                methods = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE']
            else:
                methods = [method]

            # Determine auth
            has_auth = self._has_auth_middleware(var_name, middleware_vars, group_vars)

            # Find associated blueprint
            blueprint_id = None
            if var_name in group_vars:
                full_prefix = group_prefixes.get(var_name, '')
                blueprint_id = f'group_{var_name}_{full_prefix.replace("/", "_")}'

            route_id = f'route_{method.lower()}_{full_path.replace("/", "_")}_{len(self.routes)}'
            self.routes.append({
                'id': route_id,
                'type': 'route',
                'url_pattern': path,
                'full_url': full_path,
                'methods': methods,
                'handler': handler,
                'function_name': handler,
                'file_path': file_path,
                'line_number': line_number_at(original, match.start()),
                'blueprint_id': blueprint_id,
                'parameters': {
                    'path_params': self._extract_path_params(full_path),
                    'query_params': [],
                },
                'security': {
                    'requires_auth': has_auth,
                    'auth_decorators': middleware_vars.get(var_name, []),
                },
            })

    def _extract_path_params(self, path: str) -> List[Dict]:
        """Extract path parameters from Gin/Echo style URL patterns.

        Gin uses :param syntax, Echo uses :param syntax too.
        Some also use *param for catch-all.
        """
        params = []
        # Match :param_name or *param_name
        for match in re.finditer(r'[:*](\w+)', path):
            params.append({
                'name': match.group(1),
                'type': 'string',
                'catch_all': match.group(0).startswith('*'),
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
