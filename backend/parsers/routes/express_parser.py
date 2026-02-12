"""
Express.js Routes Parser - Extract API route definitions from Express applications.

Uses regex on comment-stripped source to detect:
  - app.get/post/put/delete/patch/use() calls
  - express.Router() instances and their route definitions
  - app.use('/prefix', router) for prefix composition
  - Middleware functions recognized as auth guards

Note: We strip only line comments (not string literals) because route paths
and prefix strings must be preserved for extraction.
"""

import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from ..base import (
    BaseRoutesParser,
    find_source_files,
    line_number_at,
    read_file_safe,
)

# Strip line comments only, preserving string literals
_RE_LINE_COMMENT = re.compile(r'//[^\n]*')

# ---------------------------------------------------------------------------
# Compiled regex patterns
# ---------------------------------------------------------------------------

# Router creation: const router = express.Router()
_RE_ROUTER = re.compile(
    r"""(?:const|let|var)\s+(\w+)\s*=\s*(?:express\.)?Router\s*\(""",
)

# Route definitions:
#   app.get('/path', handler)
#   router.post('/path', middleware, handler)
#   app.get('/path', (req, res) => { ... })
# We capture: (1) obj, (2) method, (3) path, (4) rest of line for handler extraction
_RE_ROUTE = re.compile(
    r"""(\w+)\.(get|post|put|delete|patch|options|head|all)\s*\(\s*['"]([^'"]+)['"]"""
    r"""[,\s]*([^\n]*)""",
)

# Use mount: app.use('/prefix', router)  or  app.use('/prefix', require('./routes'))
_RE_USE_MOUNT = re.compile(
    r"""(\w+)\.use\s*\(\s*['"]([^'"]+)['"]\s*,\s*(\w+)""",
)

# Use middleware (no path): app.use(cors())  app.use(authenticate)
_RE_USE_MIDDLEWARE = re.compile(
    r"""(\w+)\.use\s*\(\s*(\w+)""",
)

# Identify handler function names in route args (anything that looks like an identifier)
_RE_HANDLER_NAME = re.compile(r'\b([a-zA-Z_]\w*)\b')

# Known auth/security middleware names
_AUTH_MIDDLEWARE = {
    'authenticate', 'auth', 'isAuth', 'isAuthenticated',
    'requireAuth', 'requireLogin', 'isAdmin', 'isLoggedIn',
    'jwt', 'jwtAuth', 'passport', 'verifyToken', 'checkAuth',
    'authMiddleware', 'protect', 'authorize', 'ensureAuthenticated',
}

# Path parameter extraction: :id, :userId
_RE_PATH_PARAM = re.compile(r':(\w+)')


class ExpressParser(BaseRoutesParser):
    """Parse Express.js applications to extract API route definitions."""

    FILE_EXTENSIONS = ['.js', '.ts', '.mjs']

    def parse(self) -> Dict:
        """Parse all JS/TS files and return standardized routes result."""
        files = find_source_files(str(self.project_path), self.FILE_EXTENSIONS)

        for fpath in files:
            content = read_file_safe(fpath)
            if not content:
                continue
            try:
                self._parse_file(content, fpath)
            except Exception:
                continue

        # Resolve router prefixes
        self._resolve_prefixes()

        # Update blueprint route counts
        self._update_blueprint_counts()

        return self.make_routes_result()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _parse_file(self, content: str, file_path: str):
        """Parse a single file for routes, routers, and mounts."""
        stripped = _RE_LINE_COMMENT.sub('', content)
        rel_path = self._relative_path(file_path)
        module_name = rel_path.replace(os.sep, '.').rsplit('.', 1)[0]

        # Track router variables and their prefixes
        router_vars: Dict[str, Dict] = {}
        mount_prefixes: Dict[str, str] = {}  # router_var -> prefix

        # --- Detect Router() instances ---
        for m in _RE_ROUTER.finditer(stripped):
            var_name = m.group(1)
            bp_id = f"router_{module_name}_{var_name}_{line_number_at(content, m.start())}"
            bp = {
                'id': bp_id,
                'type': 'router',
                'name': var_name,
                'variable': var_name,
                'url_prefix': '',
                'file_path': file_path,
                'line_number': line_number_at(content, m.start()),
                'route_count': 0,
            }
            self.blueprints.append(bp)
            router_vars[var_name] = bp

        # --- Detect app.use('/prefix', router) mounts ---
        for m in _RE_USE_MOUNT.finditer(stripped):
            mount_var = m.group(1)
            prefix = m.group(2)
            router_var = m.group(3)
            if router_var in router_vars:
                router_vars[router_var]['url_prefix'] = prefix
                mount_prefixes[router_var] = prefix

        # --- Detect route definitions ---
        for m in _RE_ROUTE.finditer(stripped):
            obj_var = m.group(1)
            http_method = m.group(2).upper()
            url_pattern = m.group(3)
            args_rest = m.group(4) or ''

            # Determine blueprint
            blueprint_id = None
            full_url = url_pattern
            if obj_var in router_vars:
                blueprint_id = router_vars[obj_var]['id']
                prefix = router_vars[obj_var].get('url_prefix', '')
                if prefix:
                    full_url = prefix.rstrip('/') + '/' + url_pattern.lstrip('/')

            # Extract handlers and middleware from args
            handlers = self._extract_handlers(args_rest)
            auth_middleware = [h for h in handlers if h in _AUTH_MIDDLEWARE]
            handler_name = handlers[-1] if handlers else None

            # Extract path parameters
            path_params = [
                {'name': p, 'type': 'string'}
                for p in _RE_PATH_PARAM.findall(url_pattern)
            ]

            line_num = line_number_at(content, m.start())
            route_id = f"route_{module_name}_{http_method}_{url_pattern}_{line_num}"

            self.routes.append({
                'id': route_id,
                'type': 'route',
                'url_pattern': url_pattern,
                'full_url': full_url,
                'methods': [http_method],
                'blueprint_id': blueprint_id,
                'blueprint_var': obj_var if obj_var in router_vars else None,
                'function_name': handler_name,
                'line_number': line_num,
                'file_path': file_path,
                'module': module_name,
                'parameters': {
                    'path_params': path_params,
                    'query_params': [],
                },
                'security': {
                    'requires_auth': len(auth_middleware) > 0,
                    'auth_decorators': auth_middleware,
                },
            })

    def _extract_handlers(self, args_str: str) -> List[str]:
        """Extract handler/middleware function names from route arguments."""
        handlers = []
        # Find all identifiers that look like handler names
        # Skip common non-handler words
        skip = {'req', 'res', 'next', 'err', 'error', 'async', 'function', 'return',
                'const', 'let', 'var', 'true', 'false', 'null', 'undefined'}
        for m in _RE_HANDLER_NAME.finditer(args_str):
            name = m.group(1)
            if name not in skip and not name.startswith('_'):
                handlers.append(name)
        return handlers

    def _resolve_prefixes(self):
        """Apply blueprint prefixes to routes that don't yet have them."""
        bp_by_id = {bp['id']: bp for bp in self.blueprints}
        for route in self.routes:
            bp_id = route.get('blueprint_id')
            if bp_id and bp_id in bp_by_id:
                prefix = bp_by_id[bp_id].get('url_prefix', '')
                if prefix and not route['full_url'].startswith(prefix):
                    route['full_url'] = prefix.rstrip('/') + '/' + route['url_pattern'].lstrip('/')

    def _update_blueprint_counts(self):
        """Update route_count for each blueprint."""
        counts: Dict[str, int] = {}
        for route in self.routes:
            bp_id = route.get('blueprint_id')
            if bp_id:
                counts[bp_id] = counts.get(bp_id, 0) + 1
        for bp in self.blueprints:
            bp['route_count'] = counts.get(bp['id'], 0)

    def _relative_path(self, file_path: str) -> str:
        """Get path relative to project root."""
        try:
            return str(Path(file_path).relative_to(self.project_path))
        except ValueError:
            return os.path.basename(file_path)
