"""
NestJS Routes Parser - Extract API route definitions from NestJS controllers.

Uses regex + brace counting on source to parse NestJS decorator patterns
(@Controller, @Get, @Post, @UseGuards, etc.).

Note: We strip only line comments (not string literals) because decorator
arguments like @Controller('users') and @Get(':id') contain string values
that must be preserved for route path extraction.
"""

import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from ..base import (
    BaseRoutesParser,
    extract_block_body,
    find_source_files,
    line_number_at,
    read_file_safe,
)

# Strip line comments only, preserving string literals
_RE_LINE_COMMENT = re.compile(r'//[^\n]*')

# ---------------------------------------------------------------------------
# Compiled regex patterns
# ---------------------------------------------------------------------------

# @Controller('prefix') or @Controller() — class declaration follows
_RE_CONTROLLER = re.compile(
    r"""@Controller\s*\(\s*(?:['"]([^'"]*)['"]\s*)?\)\s*"""
    r"""(?:export\s+)?class\s+(\w+)""",
)

# HTTP method decorators: @Get(), @Post(), @Put(), @Delete(), @Patch(), @Options(), @Head(), @All()
_RE_METHOD_DECORATOR = re.compile(
    r"""@(Get|Post|Put|Delete|Patch|Options|Head|All)\s*\(\s*(?:['"]([^'"]*)['"]\s*)?\)""",
)

# @UseGuards(AuthGuard, RolesGuard) — may appear before class or method
_RE_USE_GUARDS = re.compile(
    r"""@UseGuards\s*\(([^)]*)\)""",
)

# @Roles('admin', 'user')
_RE_ROLES = re.compile(
    r"""@Roles\s*\(([^)]*)\)""",
)

# Method signature after decorators
_RE_METHOD_SIG = re.compile(
    r"""(?:async\s+)?(\w+)\s*\(([^)]*)\)\s*(?::\s*\w+[<>\[\]\w\s,|]*)?""",
)

# @Param('id'), @Body(), @Query() in method parameters
_RE_PARAM_DECORATOR = re.compile(
    r"""@Param\s*\(\s*(?:['"](\w+)['"]\s*)?\)""",
)
_RE_BODY_DECORATOR = re.compile(r'@Body\s*\(')
_RE_QUERY_DECORATOR = re.compile(
    r"""@Query\s*\(\s*(?:['"](\w+)['"]\s*)?\)""",
)

# Path parameter extraction from route string: ':id', ':userId'
_RE_PATH_PARAM = re.compile(r':(\w+)')

# Known guard names that indicate authentication
_AUTH_GUARDS = {
    'AuthGuard', 'JwtAuthGuard', 'JwtGuard', 'LocalAuthGuard',
    'RolesGuard', 'AdminGuard', 'TokenGuard', 'SessionGuard',
}


class NestJSParser(BaseRoutesParser):
    """Parse NestJS controller files to extract API route definitions."""

    FILE_EXTENSIONS = ['.ts', '.js']

    def parse(self) -> Dict:
        """Parse all TS/JS files and return standardized routes result."""
        files = find_source_files(str(self.project_path), self.FILE_EXTENSIONS)

        for fpath in files:
            content = read_file_safe(fpath)
            if not content:
                continue
            try:
                self._parse_file(content, fpath)
            except Exception:
                continue

        # Update blueprint route counts
        self._update_blueprint_counts()

        return self.make_routes_result()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _parse_file(self, content: str, file_path: str):
        """Parse a single TypeScript file for NestJS controllers."""
        stripped = _RE_LINE_COMMENT.sub('', content)
        rel_path = self._relative_path(file_path)
        module_name = rel_path.replace(os.sep, '.').rsplit('.', 1)[0]

        for m in _RE_CONTROLLER.finditer(stripped):
            controller_prefix = m.group(1) or ''
            controller_name = m.group(2)

            # Check for class-level @UseGuards
            # Only look in the region between the previous closing '}' and @Controller
            scan_start = max(0, m.start() - 500)
            prev_brace = stripped.rfind('}', scan_start, m.start())
            guard_region_start = prev_brace + 1 if prev_brace >= scan_start else scan_start
            pre_controller = stripped[guard_region_start:m.start()]
            class_guards = self._extract_guards(pre_controller)

            # Extract controller body
            body, body_start, body_end = extract_block_body(stripped, m.start())
            if body_start < 0:
                continue

            line_num = line_number_at(content, m.start())
            bp_id = f"controller_{module_name}_{controller_name}_{line_num}"

            self.blueprints.append({
                'id': bp_id,
                'type': 'controller',
                'name': controller_name,
                'url_prefix': '/' + controller_prefix.strip('/') if controller_prefix else '',
                'file_path': file_path,
                'line_number': line_num,
                'route_count': 0,
            })

            # Parse methods inside controller body
            self._parse_controller_body(
                body, body_start, content, stripped,
                bp_id, controller_prefix, controller_name,
                class_guards, file_path, module_name,
            )

    def _parse_controller_body(
        self, body: str, body_start: int, original: str, stripped: str,
        bp_id: str, prefix: str, controller_name: str,
        class_guards: List[str], file_path: str, module_name: str,
    ):
        """Parse route methods inside a controller class body."""
        # Names that are decorators, not actual method names
        _decorator_names = {
            'UseGuards', 'Roles', 'SetMetadata', 'UseInterceptors',
            'UsePipes', 'UseFilters', 'Header', 'Redirect', 'HttpCode',
            'Render', 'ApiTags', 'ApiOperation', 'ApiResponse',
        }

        # Find all method decorators in the body
        pos = 0
        while pos < len(body):
            m = _RE_METHOD_DECORATOR.search(body, pos)
            if not m:
                break

            http_method = m.group(1).upper()
            route_path = m.group(2) or ''

            # Find the actual method name by skipping decorator-like identifiers
            after_decorator = body[m.end():]
            method_name = None
            params_str = ''
            sig_abs_end = m.end()
            search_text = after_decorator
            while True:
                sig_m = _RE_METHOD_SIG.search(search_text)
                if not sig_m:
                    break
                candidate = sig_m.group(1)
                if candidate not in _decorator_names:
                    method_name = candidate
                    params_str = sig_m.group(2)
                    sig_abs_end = m.end() + (len(after_decorator) - len(search_text)) + sig_m.end()
                    break
                # Skip this decorator match and continue searching
                search_text = search_text[sig_m.end():]

            if not method_name:
                pos = m.end()
                continue

            # Skip constructor and lifecycle hooks
            if method_name in ('constructor', 'onModuleInit', 'onModuleDestroy',
                               'onApplicationBootstrap', 'onApplicationShutdown'):
                pos = m.end()
                continue

            # Now scan for guards/roles in the decorator block for THIS method.
            # Region: from previous method's closing '}' to the actual method signature.
            scan_back = max(0, m.start() - 200)
            last_brace = body.rfind('}', scan_back, m.start())
            region_start = last_brace + 1 if last_brace >= scan_back else scan_back
            decorator_region = body[region_start:sig_abs_end]
            method_guards = self._extract_guards(decorator_region)
            method_roles = self._extract_roles(decorator_region)

            # Build full URL
            url_pattern = '/' + route_path.strip('/') if route_path else ''
            if prefix:
                full_url = '/' + prefix.strip('/') + url_pattern
            else:
                full_url = url_pattern or '/'

            # Extract path parameters
            path_params = [
                {'name': p, 'type': 'string'}
                for p in _RE_PATH_PARAM.findall(route_path)
            ]

            # Extract query parameters from @Query decorators
            query_params = []
            for qm in _RE_QUERY_DECORATOR.finditer(params_str):
                if qm.group(1):
                    query_params.append({'name': qm.group(1), 'type': 'string'})

            # Determine auth
            all_guards = list(set(class_guards + method_guards))
            auth_guards = [g for g in all_guards if g in _AUTH_GUARDS]
            requires_auth = len(auth_guards) > 0

            abs_pos = body_start + m.start()
            line_num = line_number_at(original, abs_pos)
            route_id = f"route_{module_name}_{method_name}_{line_num}"

            self.routes.append({
                'id': route_id,
                'type': 'route',
                'url_pattern': url_pattern or '/',
                'full_url': full_url,
                'methods': [http_method],
                'blueprint_id': bp_id,
                'controller': controller_name,
                'function_name': method_name,
                'line_number': line_num,
                'file_path': file_path,
                'module': module_name,
                'parameters': {
                    'path_params': path_params,
                    'query_params': query_params,
                },
                'security': {
                    'requires_auth': requires_auth,
                    'guards': all_guards,
                    'roles': method_roles,
                    'auth_decorators': auth_guards,
                },
            })

            pos = m.end() + sig_m.end()

    @staticmethod
    def _extract_guards(text: str) -> List[str]:
        """Extract guard names from @UseGuards(...) in the given text."""
        guards = []
        for m in _RE_USE_GUARDS.finditer(text):
            args = m.group(1)
            # Parse guard identifiers
            for name in re.findall(r'\b([A-Z]\w*)\b', args):
                guards.append(name)
        return guards

    @staticmethod
    def _extract_roles(text: str) -> List[str]:
        """Extract role names from @Roles(...) in the given text."""
        roles = []
        for m in _RE_ROLES.finditer(text):
            args = m.group(1)
            for role in re.findall(r"""['"](\w+)['"]""", args):
                roles.append(role)
        return roles

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
