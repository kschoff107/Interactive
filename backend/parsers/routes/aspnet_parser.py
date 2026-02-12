"""
ASP.NET Core Routes Parser - Extract API route definitions from C# controllers.

Uses regex-based parsing with brace counting to handle attribute-routed
ASP.NET Core Web API controllers ([ApiController], [HttpGet], etc.).
"""

import os
import re
from typing import Dict, List, Optional

from ..base import (
    BaseRoutesParser, find_source_files, read_file_safe,
    strip_comments, extract_block_body, line_number_at,
)

# ---------------------------------------------------------------------------
# Compiled regex patterns — Controller detection
# ---------------------------------------------------------------------------

# [ApiController] attribute (can appear on its own line before class)
_RE_API_CONTROLLER = re.compile(r'\[ApiController\]')

# [Route("prefix")] at class level
_RE_ROUTE_ATTR = re.compile(r'\[Route\(\s*"([^"]+)"\s*\)\]')

# Class declaration: public class UsersController : ControllerBase
_RE_CONTROLLER_CLASS = re.compile(
    r'(?:public\s+)?class\s+(\w+)\s*:\s*([\w\s,<>]+?)\s*\{'
)

# Controller base class detection
_RE_CONTROLLER_BASE = re.compile(
    r'(?:ControllerBase|Controller|ApiController)\b'
)

# ---------------------------------------------------------------------------
# Compiled regex patterns — HTTP method attributes
# ---------------------------------------------------------------------------

# [HttpGet], [HttpGet("path")], [HttpGet("{id}")]
_RE_HTTP_GET = re.compile(r'\[HttpGet(?:\(\s*"([^"]*)")?\s*\)?\]')
_RE_HTTP_POST = re.compile(r'\[HttpPost(?:\(\s*"([^"]*)")?\s*\)?\]')
_RE_HTTP_PUT = re.compile(r'\[HttpPut(?:\(\s*"([^"]*)")?\s*\)?\]')
_RE_HTTP_DELETE = re.compile(r'\[HttpDelete(?:\(\s*"([^"]*)")?\s*\)?\]')
_RE_HTTP_PATCH = re.compile(r'\[HttpPatch(?:\(\s*"([^"]*)")?\s*\)?\]')

# Combined pattern for any HTTP method attribute
_RE_HTTP_METHOD = re.compile(
    r'\[(Http(?:Get|Post|Put|Delete|Patch))'
    r'(?:\(\s*"([^"]*)"\s*\))?'
    r'\]'
)

# [Route("custom")] on individual methods
_RE_METHOD_ROUTE = re.compile(r'\[Route\(\s*"([^"]+)"\s*\)\]')

# ---------------------------------------------------------------------------
# Compiled regex patterns — Auth attributes
# ---------------------------------------------------------------------------

# [Authorize] or [Authorize(Roles = "Admin")]
_RE_AUTHORIZE = re.compile(
    r'\[Authorize'
    r'(?:\(\s*'
    r'(?:Roles\s*=\s*"([^"]*)")?'
    r'(?:,?\s*Policy\s*=\s*"([^"]*)")?'
    r'(?:,?\s*AuthenticationSchemes\s*=\s*"([^"]*)")?'
    r'\s*\))?'
    r'\]'
)

# [AllowAnonymous]
_RE_ALLOW_ANONYMOUS = re.compile(r'\[AllowAnonymous\]')

# ---------------------------------------------------------------------------
# Compiled regex patterns — Parameters
# ---------------------------------------------------------------------------

# [FromBody] TypeName paramName
_RE_FROM_BODY = re.compile(r'\[FromBody\]\s*([\w<>\[\]?,\s]+?)\s+(\w+)')

# [FromQuery] TypeName paramName or [FromQuery(Name = "n")] TypeName paramName
_RE_FROM_QUERY = re.compile(
    r'\[FromQuery(?:\(\s*Name\s*=\s*"([^"]*)"\s*\))?\]\s*'
    r'([\w<>\[\]?,\s]+?)\s+(\w+)'
)

# [FromRoute] TypeName paramName
_RE_FROM_ROUTE = re.compile(r'\[FromRoute\]\s*([\w<>\[\]?,\s]+?)\s+(\w+)')

# [FromHeader] TypeName paramName
_RE_FROM_HEADER = re.compile(r'\[FromHeader\]\s*([\w<>\[\]?,\s]+?)\s+(\w+)')

# Path parameters in route templates: {id}, {id:int}, {*slug}
_RE_PATH_PARAM = re.compile(r'\{(\*?)(\w+)(?::(\w+))?\}')

# ---------------------------------------------------------------------------
# Compiled regex patterns — Method signature
# ---------------------------------------------------------------------------

# Method declaration: public async Task<ActionResult<User>> GetById(...)
_RE_METHOD = re.compile(
    r'public\s+'
    r'(?:async\s+)?'
    r'(?:virtual\s+)?'
    r'(?:override\s+)?'
    r'([\w<>\[\]?,\s]+?)\s+'       # return type
    r'(\w+)\s*'                      # method name
    r'\(([^)]*)\)\s*'                # parameters
    r'\{',
)

# HTTP method name to method string mapping
_HTTP_ATTR_TO_METHOD = {
    'HttpGet': 'GET',
    'HttpPost': 'POST',
    'HttpPut': 'PUT',
    'HttpDelete': 'DELETE',
    'HttpPatch': 'PATCH',
}


class ASPNetParser(BaseRoutesParser):
    """Parse ASP.NET Core Web API controllers into standardized routes format.

    Handles:
    - [ApiController] with [Route("api/[controller]")] class-level routing
    - [HttpGet], [HttpPost], [HttpPut], [HttpDelete], [HttpPatch] method attributes
    - [Authorize], [AllowAnonymous] security attributes
    - [FromBody], [FromQuery], [FromRoute], [FromHeader] parameter bindings
    - [Route("custom")] method-level route overrides
    - [controller] token replacement in route templates
    """

    FILE_EXTENSIONS = ['.cs']

    def parse(self) -> Dict:
        """Parse all .cs files and return standardized api_routes dict."""
        files = find_source_files(str(self.project_path), self.FILE_EXTENSIONS)

        for fpath in files:
            content = read_file_safe(fpath)
            if not content:
                continue

            raw_content = content
            content = strip_comments(content, 'csharp')

            try:
                self._parse_file(content, raw_content, fpath)
            except Exception:
                continue

        # Update blueprint route counts
        self._update_blueprint_counts()

        return self.make_routes_result()

    # ------------------------------------------------------------------
    # File-level parsing
    # ------------------------------------------------------------------

    def _parse_file(self, content: str, raw_content: str, file_path: str) -> None:
        """Parse a single .cs file for controllers and action methods.

        Args:
            content: Comment-stripped source (for structural matching).
            raw_content: Original source (for attribute string arguments).
            file_path: Path to the source file.
        """
        # Find all controller classes
        for class_match in _RE_CONTROLLER_CLASS.finditer(content):
            class_name = class_match.group(1)
            base_classes = class_match.group(2)

            # Verify this is a controller (inherits from ControllerBase/Controller)
            if not _RE_CONTROLLER_BASE.search(base_classes):
                continue

            class_start = class_match.start()
            body, body_start, body_end = extract_block_body(content, class_start)
            if body_start == -1:
                continue

            # Extract raw body at same positions
            raw_body = raw_content[body_start:body_end]

            # Get preceding text for class-level attributes — use raw for
            # string-valued attrs like [Route("...")] and [Authorize(Roles="...")]
            preceding_start = max(0, class_start - 1000)
            preceding = raw_content[preceding_start:class_start]

            # Check for [ApiController]
            is_api_controller = bool(_RE_API_CONTROLLER.search(preceding))

            # Get class-level [Route("...")] prefix
            route_prefix = self._extract_class_route(preceding, class_name)

            # Check for class-level [Authorize]
            class_auth = self._extract_auth_info(preceding)

            # Generate relative path for module name
            try:
                rel_path = os.path.relpath(file_path, str(self.project_path))
            except ValueError:
                rel_path = file_path
            module_name = rel_path.replace(os.sep, '.').replace('.cs', '')

            # Create blueprint for this controller
            line_num = line_number_at(content, class_start)
            blueprint_id = f"controller_{class_name}_{line_num}"
            blueprint = {
                'id': blueprint_id,
                'type': 'controller',
                'name': class_name,
                'route_prefix': route_prefix,
                'is_api_controller': is_api_controller,
                'file_path': file_path,
                'line_number': line_num,
                'module': module_name,
                'route_count': 0,
            }
            if class_auth.get('requires_auth'):
                blueprint['security'] = class_auth

            self.blueprints.append(blueprint)

            # Parse action methods inside this controller
            self._parse_action_methods(
                body, raw_body, body_start, content, raw_content,
                file_path, module_name, blueprint_id, route_prefix,
                class_auth,
            )

    # ------------------------------------------------------------------
    # Class-level route extraction
    # ------------------------------------------------------------------

    def _extract_class_route(self, preceding: str, class_name: str) -> str:
        """Extract and resolve the class-level [Route("...")] prefix.

        Handles [controller] token replacement: strips "Controller" suffix
        from class name and lowercases.
        """
        route_match = _RE_ROUTE_ATTR.search(preceding)
        if not route_match:
            return ''

        route_template = route_match.group(1)

        # Replace [controller] token
        controller_name = class_name
        if controller_name.endswith('Controller'):
            controller_name = controller_name[:-len('Controller')]
        controller_name = controller_name.lower()

        route_template = route_template.replace('[controller]', controller_name)

        # Ensure prefix starts with /
        if route_template and not route_template.startswith('/'):
            route_template = '/' + route_template

        return route_template

    # ------------------------------------------------------------------
    # Action method parsing
    # ------------------------------------------------------------------

    def _parse_action_methods(
        self, body: str, raw_body: str, body_offset: int,
        full_content: str, raw_full_content: str,
        file_path: str, module_name: str, blueprint_id: str,
        route_prefix: str, class_auth: Dict,
    ) -> None:
        """Parse action methods from a controller body.

        Args:
            body: Comment-stripped controller body (structural matching).
            raw_body: Original controller body (attribute string arguments).
            body_offset: Absolute position of body_start in full_content.
            full_content: Full stripped source.
            raw_full_content: Full raw source.
            file_path: Source file path.
            module_name: Dotted module name.
            blueprint_id: Parent blueprint/controller ID.
            route_prefix: Class-level route prefix.
            class_auth: Class-level auth info dict.
        """
        # Track previous method end to scope attribute lookups
        prev_end = 0

        for method_match in _RE_METHOD.finditer(body):
            return_type = method_match.group(1).strip()
            method_name = method_match.group(2)
            # Use raw_body for params to preserve string literals in [FromQuery] etc.
            raw_params_str = raw_body[method_match.start(3):method_match.end(3)].strip()

            method_start = method_match.start()

            # Get preceding text for attributes — scoped to text since previous
            # method ended, and use raw_body for string-valued attributes
            raw_preceding = raw_body[prev_end:method_start]
            preceding = body[prev_end:method_start]
            prev_end = method_match.end()

            # Find HTTP method attribute (use raw to get path templates)
            http_methods = []
            route_template = ''

            for http_match in _RE_HTTP_METHOD.finditer(raw_preceding):
                attr_name = http_match.group(1)
                path_template = http_match.group(2) or ''
                http_method = _HTTP_ATTR_TO_METHOD.get(attr_name)
                if http_method:
                    http_methods.append(http_method)
                if path_template:
                    route_template = path_template

            if not http_methods:
                # No HTTP method attribute — skip non-action methods
                continue

            # Check for method-level [Route("...")] override (raw for strings)
            method_route_match = _RE_METHOD_ROUTE.search(raw_preceding)
            if method_route_match:
                route_template = method_route_match.group(1)

            # Build full URL
            full_url = self._build_full_url(route_prefix, route_template)

            # Extract path parameters from URL template
            path_params = self._extract_path_params(full_url)

            # Extract parameter binding attributes (raw for string args)
            body_params = self._extract_from_body_params(raw_params_str)
            query_params = self._extract_from_query_params(raw_params_str)
            route_params = self._extract_from_route_params(raw_params_str)
            header_params = self._extract_from_header_params(raw_params_str)

            # Determine auth: method-level overrides class-level (raw for Roles)
            allow_anonymous = bool(_RE_ALLOW_ANONYMOUS.search(raw_preceding))
            method_auth = self._extract_auth_info(raw_preceding)

            if allow_anonymous:
                security = {
                    'requires_auth': False,
                    'allow_anonymous': True,
                }
            elif method_auth.get('requires_auth'):
                security = method_auth
            else:
                # Inherit from class
                security = dict(class_auth) if class_auth.get('requires_auth') else {
                    'requires_auth': False,
                }

            # Extract response type from return type
            response_type = self._extract_response_type(return_type)

            # Calculate line number
            abs_pos = body_offset + method_start
            line_num = line_number_at(full_content, abs_pos)

            route_id = f"route_{module_name}_{method_name}_{line_num}"

            route = {
                'id': route_id,
                'type': 'route',
                'url_pattern': route_template or '/',
                'full_url': full_url,
                'methods': http_methods,
                'function_name': method_name,
                'blueprint_id': blueprint_id,
                'line_number': line_num,
                'file_path': file_path,
                'module': module_name,
                'parameters': {
                    'path_params': path_params,
                    'query_params': query_params,
                    'body_params': body_params,
                    'route_params': route_params,
                    'header_params': header_params,
                },
                'security': security,
            }

            if response_type:
                route['response_type'] = response_type

            self.routes.append(route)

    # ------------------------------------------------------------------
    # URL building
    # ------------------------------------------------------------------

    @staticmethod
    def _build_full_url(prefix: str, template: str) -> str:
        """Combine route prefix and method template into full URL."""
        if not prefix and not template:
            return '/'

        if not template:
            return prefix or '/'

        # If template starts with / or ~/, it's an absolute route
        if template.startswith('/') or template.startswith('~/'):
            return '/' + template.lstrip('~/')

        # Combine prefix and template
        prefix = prefix.rstrip('/')
        template = template.lstrip('/')
        return f"{prefix}/{template}" if prefix else f"/{template}"

    # ------------------------------------------------------------------
    # Path parameter extraction
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_path_params(url: str) -> List[Dict]:
        """Extract path parameters from URL template like {id} or {id:int}."""
        params = []
        for match in _RE_PATH_PARAM.finditer(url):
            is_catch_all = bool(match.group(1))
            name = match.group(2)
            constraint = match.group(3)
            params.append({
                'name': name,
                'type': constraint or 'string',
                'catch_all': is_catch_all,
            })
        return params

    # ------------------------------------------------------------------
    # Parameter binding extraction
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_from_body_params(params_str: str) -> List[Dict]:
        """Extract [FromBody] parameters from method signature."""
        params = []
        for match in _RE_FROM_BODY.finditer(params_str):
            params.append({
                'name': match.group(2),
                'type': match.group(1).strip(),
                'source': 'body',
            })
        return params

    @staticmethod
    def _extract_from_query_params(params_str: str) -> List[Dict]:
        """Extract [FromQuery] parameters from method signature."""
        params = []
        for match in _RE_FROM_QUERY.finditer(params_str):
            query_name = match.group(1)  # from Name="..."
            param_type = match.group(2).strip()
            param_name = match.group(3)
            params.append({
                'name': query_name or param_name,
                'type': param_type,
                'source': 'query',
                'parameter_name': param_name,
            })
        return params

    @staticmethod
    def _extract_from_route_params(params_str: str) -> List[Dict]:
        """Extract [FromRoute] parameters from method signature."""
        params = []
        for match in _RE_FROM_ROUTE.finditer(params_str):
            params.append({
                'name': match.group(2),
                'type': match.group(1).strip(),
                'source': 'route',
            })
        return params

    @staticmethod
    def _extract_from_header_params(params_str: str) -> List[Dict]:
        """Extract [FromHeader] parameters from method signature."""
        params = []
        for match in _RE_FROM_HEADER.finditer(params_str):
            params.append({
                'name': match.group(2),
                'type': match.group(1).strip(),
                'source': 'header',
            })
        return params

    # ------------------------------------------------------------------
    # Auth extraction
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_auth_info(text: str) -> Dict:
        """Extract [Authorize] attribute information."""
        auth_match = _RE_AUTHORIZE.search(text)
        if not auth_match:
            return {'requires_auth': False}

        result: Dict = {'requires_auth': True}

        roles = auth_match.group(1)
        policy = auth_match.group(2)
        scheme = auth_match.group(3)

        if roles:
            result['roles'] = [r.strip() for r in roles.split(',')]
        if policy:
            result['policy'] = policy
        if scheme:
            result['authentication_scheme'] = scheme

        return result

    # ------------------------------------------------------------------
    # Response type extraction
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_response_type(return_type: str) -> Optional[str]:
        """Extract the response model type from return type annotation.

        Handles nested generics like Task<ActionResult<IEnumerable<User>>>.
        Extracts the innermost meaningful type from ActionResult<T>.
        """
        # Strip Task<...> wrapper
        inner = return_type.strip()
        if inner.startswith('Task<') and inner.endswith('>'):
            inner = inner[5:-1].strip()

        # Strip ActionResult<...> wrapper
        if inner.startswith('ActionResult<') and inner.endswith('>'):
            inner = inner[13:-1].strip()
            return inner

        # No extractable type for plain ActionResult or IActionResult
        if inner in ('ActionResult', 'IActionResult'):
            return None

        return None

    # ------------------------------------------------------------------
    # Blueprint counts
    # ------------------------------------------------------------------

    def _update_blueprint_counts(self) -> None:
        """Update route_count for each blueprint/controller."""
        counts: Dict[str, int] = {}
        for route in self.routes:
            bp_id = route.get('blueprint_id')
            if bp_id:
                counts[bp_id] = counts.get(bp_id, 0) + 1

        for bp in self.blueprints:
            bp['route_count'] = counts.get(bp['id'], 0)
