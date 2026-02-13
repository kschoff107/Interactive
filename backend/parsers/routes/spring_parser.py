"""
Spring Boot Routes Parser - Extract REST endpoint definitions from Spring MVC annotations.

Uses regex-based parsing with brace counting to extract @RestController classes,
@RequestMapping prefixes, and method-level mapping annotations.
"""

import logging
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
    strip_comments,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Compiled regex patterns
# ---------------------------------------------------------------------------

# Controller class detection: @RestController or @Controller
_RE_CONTROLLER = re.compile(
    r'(?P<annotations>(?:\s*@\w+(?:\s*\([^)]*\))?)*?)'
    r'\s*(?:@RestController|@Controller)\b'
    r'(?P<post_annotations>(?:\s*@\w+(?:\s*\([^)]*\))?)*?)'
    r'\s*(?:public\s+)?class\s+(?P<class_name>\w+)'
    r'(?:\s+extends\s+\w+)?'
    r'(?:\s+implements\s+[\w,\s]+)?'
    r'\s*\{',
    re.DOTALL,
)

# Class-level @RequestMapping("/prefix")
_RE_REQUEST_MAPPING_CLASS = re.compile(
    r'@RequestMapping\s*\(\s*(?:'
    r'"(?P<path1>[^"]*)"'                      # @RequestMapping("/path")
    r'|value\s*=\s*"(?P<path2>[^"]*)"'         # @RequestMapping(value = "/path")
    r'|path\s*=\s*"(?P<path3>[^"]*)"'          # @RequestMapping(path = "/path")
    r')\s*(?:,[^)]*)?\)',
)

# Method-level mapping annotations
_RE_GET_MAPPING = re.compile(
    r'@GetMapping\b(?:\s*\(\s*(?:'
    r'"(?P<path1>[^"]*)"'
    r'|value\s*=\s*"(?P<path2>[^"]*)"'
    r'|path\s*=\s*"(?P<path3>[^"]*)"'
    r')?\s*(?:,[^)]*)?\))?',
)
_RE_POST_MAPPING = re.compile(
    r'@PostMapping\b(?:\s*\(\s*(?:'
    r'"(?P<path1>[^"]*)"'
    r'|value\s*=\s*"(?P<path2>[^"]*)"'
    r'|path\s*=\s*"(?P<path3>[^"]*)"'
    r')?\s*(?:,[^)]*)?\))?',
)
_RE_PUT_MAPPING = re.compile(
    r'@PutMapping\b(?:\s*\(\s*(?:'
    r'"(?P<path1>[^"]*)"'
    r'|value\s*=\s*"(?P<path2>[^"]*)"'
    r'|path\s*=\s*"(?P<path3>[^"]*)"'
    r')?\s*(?:,[^)]*)?\))?',
)
_RE_DELETE_MAPPING = re.compile(
    r'@DeleteMapping\b(?:\s*\(\s*(?:'
    r'"(?P<path1>[^"]*)"'
    r'|value\s*=\s*"(?P<path2>[^"]*)"'
    r'|path\s*=\s*"(?P<path3>[^"]*)"'
    r')?\s*(?:,[^)]*)?\))?',
)
_RE_PATCH_MAPPING = re.compile(
    r'@PatchMapping\b(?:\s*\(\s*(?:'
    r'"(?P<path1>[^"]*)"'
    r'|value\s*=\s*"(?P<path2>[^"]*)"'
    r'|path\s*=\s*"(?P<path3>[^"]*)"'
    r')?\s*(?:,[^)]*)?\))?',
)

# Generic @RequestMapping on methods (with method attribute)
_RE_REQUEST_MAPPING_METHOD = re.compile(
    r'@RequestMapping\s*\((?P<attrs>[^)]*)\)',
    re.DOTALL,
)
_RE_RM_VALUE = re.compile(
    r'(?:value|path)\s*=\s*"(?P<val>[^"]*)"'
)
_RE_RM_PATH_DIRECT = re.compile(
    r'(?<!\w)"(?P<val>[^"]*)"'
)
_RE_RM_METHOD = re.compile(
    r'method\s*=\s*(?:RequestMethod\.)?(?P<method>\w+)'
)

# Method declaration (Java method signature)
# Requires an access modifier to avoid matching annotation names as return types.
# Params capture handles one level of nested parens (for annotation arguments).
_RE_METHOD_DECL = re.compile(
    r'(?:public|protected|private)\s+'
    r'(?:(?:static|final|abstract|synchronized)\s+)*'
    r'(?P<return_type>[\w<>,\s\?\[\]]+?)\s+'
    r'(?P<method_name>\w+)\s*'
    r'\((?P<params>(?:[^()]*|\([^)]*\))*)\)\s*'
    r'(?:throws\s+[\w,\s]+\s*)?'
    r'\{',
)

# Security / auth annotations
_RE_PRE_AUTHORIZE = re.compile(
    r'@PreAuthorize\s*\(\s*"(?P<expr>[^"]+)"\s*\)',
)
_RE_SECURED = re.compile(
    r'@Secured\s*\(\s*(?:"(?P<role>[^"]+)"|'
    r'\{(?P<roles>[^}]+)\})\s*\)',
)
_RE_ROLES_ALLOWED = re.compile(
    r'@RolesAllowed\s*\(\s*(?:"(?P<role>[^"]+)"|'
    r'\{(?P<roles>[^}]+)\})\s*\)',
)

# Parameter annotations
_RE_PATH_VARIABLE = re.compile(
    r'@PathVariable\b(?:\s*\(\s*(?:"(?P<name1>[^"]*)"'
    r'|value\s*=\s*"(?P<name2>[^"]*)"'
    r')?\s*\))?\s*'
    r'(?P<type>\w+)\s+(?P<param>\w+)',
)
_RE_REQUEST_PARAM = re.compile(
    r'@RequestParam\b(?:\s*\((?P<attrs>[^)]*)\))?\s*'
    r'(?P<type>\w+)\s+(?P<param>\w+)',
)
_RE_REQUEST_BODY = re.compile(
    r'@RequestBody\s+(?P<type>\w+)\s+(?P<param>\w+)',
)
_RE_REQ_PARAM_NAME = re.compile(r'(?:value\s*=\s*|^)"?(?P<val>\w+)"?')
_RE_REQ_PARAM_REQUIRED = re.compile(r'required\s*=\s*(?P<val>true|false)', re.IGNORECASE)
_RE_REQ_PARAM_DEFAULT = re.compile(r'defaultValue\s*=\s*"(?P<val>[^"]*)"')

# Path parameter extraction from URL patterns like /{id}
_RE_PATH_PARAM_URL = re.compile(r'\{(?P<name>\w+)\}')

# Mapping type -> HTTP method
_MAPPING_METHODS = {
    'GetMapping': 'GET',
    'PostMapping': 'POST',
    'PutMapping': 'PUT',
    'DeleteMapping': 'DELETE',
    'PatchMapping': 'PATCH',
}

_MAPPING_PATTERNS = [
    ('GET', _RE_GET_MAPPING),
    ('POST', _RE_POST_MAPPING),
    ('PUT', _RE_PUT_MAPPING),
    ('DELETE', _RE_DELETE_MAPPING),
    ('PATCH', _RE_PATCH_MAPPING),
]


class SpringParser(BaseRoutesParser):
    """Parser for Spring Boot REST controller annotations."""

    FILE_EXTENSIONS = ['.java']

    def parse(self) -> Dict:
        """Parse Spring controllers and return standardized API routes.

        Returns:
            Standardized api_routes dict with blueprints and routes.
        """
        java_files = find_source_files(str(self.project_path), self.FILE_EXTENSIONS)

        for file_path in java_files:
            content = read_file_safe(file_path)
            if content is None:
                continue

            try:
                self._parse_file(content, file_path)
            except Exception as e:
                logger.warning("Failed to parse %s: %s", file_path, e)
                continue

        # Update blueprint route counts
        self._update_blueprint_counts()

        return self.make_routes_result()

    def _parse_file(self, content: str, file_path: str) -> None:
        """Parse a single Java file for Spring controllers."""
        stripped = strip_comments(content, 'java')

        for ctrl_match in _RE_CONTROLLER.finditer(stripped):
            class_name = ctrl_match.group('class_name')
            ctrl_start = ctrl_match.start()

            # Use original content for annotation attribute values (string literals
            # are replaced with spaces by strip_comments)
            pre_start = max(0, ctrl_start - 500)
            pre_text_original = content[pre_start:ctrl_match.end()]

            # Extract class-level @RequestMapping prefix from original content
            prefix = self._extract_class_prefix(pre_text_original)

            # Determine if this is a @RestController or @Controller
            is_rest = '@RestController' in pre_text_original

            # Extract class body
            body, body_start, body_end = extract_block_body(stripped, ctrl_match.start())
            if body_start == -1:
                continue

            line = line_number_at(content, ctrl_start)

            # Derive module name from file path
            rel_path = os.path.relpath(file_path, str(self.project_path))
            module_name = rel_path.replace(os.sep, '.').replace('.java', '')

            # Create blueprint for this controller
            blueprint_id = f"controller_{module_name}_{class_name}_{line}"
            self.blueprints.append({
                'id': blueprint_id,
                'type': 'controller',
                'name': class_name,
                'url_prefix': prefix,
                'is_rest_controller': is_rest,
                'file_path': file_path,
                'line_number': line,
                'route_count': 0,
            })

            # Parse methods within the controller body
            self._parse_controller_methods(
                body, body_start, blueprint_id, prefix,
                class_name, module_name, file_path, content,
            )

    @staticmethod
    def _extract_class_prefix(text: str) -> str:
        """Extract class-level @RequestMapping prefix."""
        m = _RE_REQUEST_MAPPING_CLASS.search(text)
        if m:
            return m.group('path1') or m.group('path2') or m.group('path3') or ''
        return ''

    def _parse_controller_methods(
        self,
        body: str,
        body_offset: int,
        blueprint_id: str,
        prefix: str,
        class_name: str,
        module_name: str,
        file_path: str,
        original_content: str,
    ) -> None:
        """Parse mapping annotations on methods within a controller body."""
        # Build original (unstripped) body for extracting string-valued attributes
        original_body = original_content[body_offset:body_offset + len(body)]

        for method_match in _RE_METHOD_DECL.finditer(body):
            method_name = method_match.group('method_name')
            method_pos = method_match.start()

            # Use original content for annotations (preserves string literals)
            annotations_text = self._get_annotations_before(original_body, method_pos)
            # Use original content for parameter text (preserves string literals)
            params_text = original_body[method_match.start('params'):method_match.end('params')]

            # Try each mapping type
            mapping_info = self._detect_mapping(annotations_text)
            if mapping_info is None:
                continue

            http_method, method_path = mapping_info
            line = line_number_at(original_content, body_offset + method_pos)

            # Compose full URL
            full_url = self._compose_url(prefix, method_path)

            # Extract path parameters from URL pattern
            path_params = self._extract_path_params_from_url(full_url)

            # Extract annotated parameters
            annotated_params = self._extract_parameters(params_text)

            # Merge path params from URL with annotated path variables
            for pp in path_params:
                if not any(ap['name'] == pp['name'] for ap in annotated_params.get('path_params', [])):
                    annotated_params.setdefault('path_params', []).append(pp)

            # Detect security annotations
            security = self._detect_security(annotations_text)

            # Generate route ID
            route_id = f"route_{module_name}_{class_name}_{method_name}_{line}"

            # Determine method end line
            method_body, _, m_end = extract_block_body(body, method_match.start())
            end_line = line_number_at(original_content, body_offset + m_end) if m_end != -1 else line

            self.routes.append({
                'id': route_id,
                'type': 'route',
                'url_pattern': method_path,
                'full_url': full_url,
                'methods': [http_method],
                'blueprint_id': blueprint_id,
                'function_name': method_name,
                'class_name': class_name,
                'parameters': annotated_params,
                'security': security,
                'file_path': file_path,
                'module': module_name,
                'line_number': line,
                'end_line': end_line,
            })

    def _detect_mapping(self, annotations_text: str) -> Optional[Tuple[str, str]]:
        """Detect which HTTP mapping annotation is present.

        Returns:
            Tuple of (http_method, path) or None.
        """
        # Check specific mapping annotations first
        for http_method, pattern in _MAPPING_PATTERNS:
            m = pattern.search(annotations_text)
            if m:
                path = m.group('path1') or m.group('path2') or m.group('path3') or ''
                return http_method, path

        # Check generic @RequestMapping on method
        m = _RE_REQUEST_MAPPING_METHOD.search(annotations_text)
        if m:
            attrs = m.group('attrs')

            # Extract path
            path = ''
            path_m = _RE_RM_VALUE.search(attrs)
            if path_m:
                path = path_m.group('val')
            else:
                path_m = _RE_RM_PATH_DIRECT.search(attrs)
                if path_m:
                    path = path_m.group('val')

            # Extract method
            method = 'GET'
            method_m = _RE_RM_METHOD.search(attrs)
            if method_m:
                method = method_m.group('method').upper()

            return method, path

        return None

    @staticmethod
    def _get_annotations_before(body: str, method_pos: int) -> str:
        """Extract annotation block preceding a method declaration."""
        lines_before = body[:method_pos].split('\n')
        annotation_lines: List[str] = []

        for line in reversed(lines_before):
            stripped = line.strip()
            if stripped.startswith('@') or not stripped:
                annotation_lines.insert(0, line)
            else:
                break

        return '\n'.join(annotation_lines)

    @staticmethod
    def _compose_url(prefix: str, method_path: str) -> str:
        """Compose full URL from class prefix and method path.

        Ensures proper slash handling between prefix and path.
        """
        if not prefix and not method_path:
            return '/'
        if not prefix:
            return method_path if method_path.startswith('/') else f'/{method_path}'
        if not method_path:
            return prefix

        # Remove trailing slash from prefix, ensure leading slash on path
        clean_prefix = prefix.rstrip('/')
        clean_path = method_path if method_path.startswith('/') else f'/{method_path}'
        return f'{clean_prefix}{clean_path}'

    @staticmethod
    def _extract_path_params_from_url(url: str) -> List[Dict]:
        """Extract path parameters from URL pattern like /api/users/{id}."""
        params = []
        for m in _RE_PATH_PARAM_URL.finditer(url):
            params.append({
                'name': m.group('name'),
                'type': 'string',
                'in': 'path',
            })
        return params

    @staticmethod
    def _extract_parameters(params_text: str) -> Dict:
        """Extract annotated parameters from method signature."""
        result: Dict = {
            'path_params': [],
            'query_params': [],
            'body_param': None,
        }

        # @PathVariable
        for m in _RE_PATH_VARIABLE.finditer(params_text):
            name = m.group('name1') or m.group('name2') or m.group('param')
            result['path_params'].append({
                'name': name,
                'type': m.group('type'),
                'in': 'path',
            })

        # @RequestParam
        for m in _RE_REQUEST_PARAM.finditer(params_text):
            param_name = m.group('param')
            param_type = m.group('type')
            attrs = m.group('attrs') or ''

            required = True
            default_value = None

            req_m = _RE_REQ_PARAM_REQUIRED.search(attrs)
            if req_m:
                required = req_m.group('val').lower() == 'true'

            def_m = _RE_REQ_PARAM_DEFAULT.search(attrs)
            if def_m:
                default_value = def_m.group('val')

            # Check if attrs has a name/value override
            name_m = _RE_REQ_PARAM_NAME.search(attrs)
            if name_m and name_m.group('val') not in ('required', 'defaultValue'):
                param_name = name_m.group('val')

            result['query_params'].append({
                'name': param_name,
                'type': param_type,
                'in': 'query',
                'required': required,
                'default_value': default_value,
            })

        # @RequestBody
        m = _RE_REQUEST_BODY.search(params_text)
        if m:
            result['body_param'] = {
                'name': m.group('param'),
                'type': m.group('type'),
                'in': 'body',
            }

        return result

    @staticmethod
    def _detect_security(annotations_text: str) -> Dict:
        """Detect security annotations on a method."""
        auth_decorators: List[str] = []
        roles: List[str] = []

        # @PreAuthorize
        m = _RE_PRE_AUTHORIZE.search(annotations_text)
        if m:
            expr = m.group('expr')
            auth_decorators.append(f'@PreAuthorize("{expr}")')
            # Extract all single-quoted role names from hasRole/hasAnyRole expressions
            role_matches = re.findall(r"'([^']+)'", expr)
            roles.extend(role_matches)

        # @Secured
        m = _RE_SECURED.search(annotations_text)
        if m:
            role = m.group('role')
            role_list = m.group('roles')
            if role:
                auth_decorators.append(f'@Secured("{role}")')
                roles.append(role.replace('ROLE_', ''))
            elif role_list:
                auth_decorators.append(f'@Secured({{{role_list}}})')
                for r in re.findall(r'"([^"]+)"', role_list):
                    roles.append(r.replace('ROLE_', ''))

        # @RolesAllowed
        m = _RE_ROLES_ALLOWED.search(annotations_text)
        if m:
            role = m.group('role')
            role_list = m.group('roles')
            if role:
                auth_decorators.append(f'@RolesAllowed("{role}")')
                roles.append(role)
            elif role_list:
                auth_decorators.append(f'@RolesAllowed({{{role_list}}})')
                for r in re.findall(r'"([^"]+)"', role_list):
                    roles.append(r)

        return {
            'requires_auth': len(auth_decorators) > 0,
            'auth_decorators': auth_decorators,
            'roles': roles,
        }

    def _update_blueprint_counts(self) -> None:
        """Update route_count for each blueprint."""
        counts: Dict[str, int] = {}
        for route in self.routes:
            bp_id = route.get('blueprint_id')
            if bp_id:
                counts[bp_id] = counts.get(bp_id, 0) + 1

        for bp in self.blueprints:
            bp['route_count'] = counts.get(bp['id'], 0)
