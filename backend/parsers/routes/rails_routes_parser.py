"""
Ruby on Rails routes parser.

Parses config/routes.rb to extract API route definitions using
regex-based analysis of Rails routing DSL.
"""

import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from ..base import (
    BaseRoutesParser, find_source_files, read_file_safe,
    line_number_at,
)

# Custom comment stripping for Ruby that preserves string literals.
# Rails routes use strings with '#' in them (e.g., 'controller#action').
# A naive #-comment regex would strip these. Instead we match string
# literals first (and keep them), then match actual comments (and strip).
_RUBY_SMART_STRIP_RE = re.compile(
    r"'(?:\\.|[^'\\])*'"    # single-quoted string (keep)
    r'|"(?:\\.|[^"\\])*"'   # double-quoted string (keep)
    r'|=begin.*?=end'       # block comment (strip)
    r'|#[^\n]*',            # single-line comment (strip)
    re.DOTALL,
)


def _strip_ruby_comments_only(content: str) -> str:
    """Strip Ruby comments while preserving string literals."""
    def _replacer(match):
        text = match.group(0)
        # If it starts with a quote, it's a string literal — keep it
        if text[0] in ("'", '"'):
            return text
        # Otherwise it's a comment — blank it
        return re.sub(r'[^\n]', ' ', text)
    return _RUBY_SMART_STRIP_RE.sub(_replacer, content)

# ---------------------------------------------------------------------------
# Compiled regex patterns
# ---------------------------------------------------------------------------

# Rails.application.routes.draw do
_ROUTES_DRAW_RE = re.compile(
    r'Rails\.application\.routes\.draw\s+do',
    re.MULTILINE,
)

# resources :users / resources :users, only: [:index, :create]
# Only matches plural 'resources', not singular 'resource'
_RESOURCES_RE = re.compile(
    r'resources\s+:(\w+)'
    r'(?:\s*,\s*only:\s*\[([^\]]*)\])?'
    r'(?:\s*,\s*except:\s*\[([^\]]*)\])?',
    re.MULTILINE,
)

# resource :profile (singular resource)
_RESOURCE_SINGULAR_RE = re.compile(
    r'resource\s+:(\w+)'
    r'(?:\s*,\s*only:\s*\[([^\]]*)\])?'
    r'(?:\s*,\s*except:\s*\[([^\]]*)\])?',
    re.MULTILINE,
)

# namespace :api do ... end
_NAMESPACE_RE = re.compile(
    r'namespace\s+:(\w+)\s+do',
    re.MULTILINE,
)

# scope '/api' do ... end  OR  scope :api do ... end
_SCOPE_RE = re.compile(
    r"scope\s+(?:['\"/](\w+)['\"]?|:(\w+))\s+do",
    re.MULTILINE,
)

# get '/path', to: 'controller#action'
_EXPLICIT_ROUTE_RE = re.compile(
    r"(get|post|put|patch|delete)\s+['\"]([^'\"]+)['\"]"
    r"(?:\s*,\s*to:\s*['\"](\w+)#(\w+)['\"])?",
    re.MULTILINE,
)

# root 'home#index'
_ROOT_RE = re.compile(
    r"root\s+['\"](\w+)#(\w+)['\"]",
    re.MULTILINE,
)

# Symbol list items: :index, :create, etc.
_SYMBOL_RE = re.compile(r':(\w+)')

# Standard REST actions mapped to HTTP methods and paths
_RESOURCE_ACTIONS = {
    'index':   ('GET',    '',          'list all'),
    'show':    ('GET',    '/:id',     'show one'),
    'new':     ('GET',    '/new',     'new form'),
    'create':  ('POST',   '',          'create'),
    'edit':    ('GET',    '/:id/edit', 'edit form'),
    'update':  ('PUT',    '/:id',     'update'),
    'destroy': ('DELETE', '/:id',     'delete'),
}

# Singular resource actions (no :index, no :id in paths)
_SINGULAR_RESOURCE_ACTIONS = {
    'show':    ('GET',    '',      'show'),
    'new':     ('GET',    '/new',  'new form'),
    'create':  ('POST',   '',      'create'),
    'edit':    ('GET',    '/edit', 'edit form'),
    'update':  ('PUT',    '',      'update'),
    'destroy': ('DELETE', '',      'delete'),
}

# Standard REST action names
_ALL_ACTIONS = frozenset(_RESOURCE_ACTIONS.keys())
_ALL_SINGULAR_ACTIONS = frozenset(_SINGULAR_RESOURCE_ACTIONS.keys())


class RailsRoutesParser(BaseRoutesParser):
    """Parse Ruby on Rails route definitions from config/routes.rb."""

    FILE_EXTENSIONS = ['.rb']

    def parse(self) -> Dict:
        """Parse Rails routes from the project.

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
        """Find Rails route files."""
        routes_file = os.path.join(str(self.project_path), 'config', 'routes.rb')
        if os.path.isfile(routes_file):
            return [routes_file]

        # Fallback: search for any routes.rb
        all_rb = find_source_files(str(self.project_path), ['.rb'])
        return [f for f in all_rb if f.endswith('routes.rb')]

    def _parse_routes_file(self, content: str, file_path: str):
        """Parse a single routes file."""
        stripped = _strip_ruby_comments_only(content)
        self._parse_block(stripped, content, file_path, prefix='', namespace_stack=[])

    def _parse_block(self, block_text: str, original: str, file_path: str,
                     prefix: str, namespace_stack: List[str],
                     auth: bool = False):
        """Recursively parse route blocks handling nesting.

        First extracts and recurses into namespace/scope blocks one at
        a time, blanking each consumed region before searching for the
        next. This prevents inner blocks from being re-parsed at
        the outer level.
        """
        remaining = block_text

        # --- Namespaces (process one at a time, blanking after each) ---
        while True:
            match = _NAMESPACE_RE.search(remaining)
            if not match:
                break

            ns_name = match.group(1)
            block_body = self._extract_do_block(remaining, match.end())
            if not block_body:
                # Blank just the keyword to avoid infinite loop
                blanked = re.sub(r'[^\n]', ' ', remaining[match.start():match.end()])
                remaining = remaining[:match.start()] + blanked + remaining[match.end():]
                continue

            ns_prefix = f'{prefix}/{ns_name}'
            blueprint_id = f'namespace_{ns_name}_{"_".join(namespace_stack + [ns_name])}'

            self.blueprints.append({
                'id': blueprint_id,
                'type': 'namespace',
                'name': ns_name,
                'url_prefix': ns_prefix,
                'file_path': file_path,
                'line_number': line_number_at(original, match.start()) if match.start() < len(original) else 0,
                'route_count': 0,
            })

            self._parse_block(
                block_body, original, file_path,
                prefix=ns_prefix,
                namespace_stack=namespace_stack + [ns_name],
                auth=auth,
            )

            # Blank the entire namespace region (keyword + do block + end)
            body_pos = remaining.find(block_body, match.end())
            ns_full_end = body_pos + len(block_body)
            end_match = re.compile(r'\bend\b').search(remaining, ns_full_end)
            if end_match:
                ns_full_end = end_match.end()
            blanked = re.sub(r'[^\n]', ' ', remaining[match.start():ns_full_end])
            remaining = remaining[:match.start()] + blanked + remaining[ns_full_end:]

        # --- Scopes (process one at a time) ---
        while True:
            match = _SCOPE_RE.search(remaining)
            if not match:
                break

            scope_name = match.group(1) or match.group(2)
            block_body = self._extract_do_block(remaining, match.end())
            if not block_body:
                blanked = re.sub(r'[^\n]', ' ', remaining[match.start():match.end()])
                remaining = remaining[:match.start()] + blanked + remaining[match.end():]
                continue

            scope_prefix = f'{prefix}/{scope_name}'
            self._parse_block(
                block_body, original, file_path,
                prefix=scope_prefix,
                namespace_stack=namespace_stack,
                auth=auth,
            )

            body_pos = remaining.find(block_body, match.end())
            scope_full_end = body_pos + len(block_body)
            end_match = re.compile(r'\bend\b').search(remaining, scope_full_end)
            if end_match:
                scope_full_end = end_match.end()
            blanked = re.sub(r'[^\n]', ' ', remaining[match.start():scope_full_end])
            remaining = remaining[:match.start()] + blanked + remaining[scope_full_end:]

        # --- Resources with nested blocks (e.g. resources :users do ... end) ---
        # Handle these first so we can recurse into nested resources
        for match in _RESOURCES_RE.finditer(remaining):
            resource_name = match.group(1)
            only_str = match.group(2)
            except_str = match.group(3)

            actions = self._resolve_actions(only_str, except_str, _ALL_ACTIONS)
            resource_prefix = f'{prefix}/{resource_name}'

            # Check for nested block
            after_match = remaining[match.end():]
            do_match = re.match(r'\s+do\b', after_match)
            if do_match:
                block_body = self._extract_do_block(
                    remaining, match.end() + do_match.end()
                )
                if block_body:
                    singular = resource_name[:-1] if resource_name.endswith('s') else resource_name
                    nested_prefix = f'{resource_prefix}/:{singular}_id'
                    self._parse_block(
                        block_body, original, file_path,
                        prefix=nested_prefix,
                        namespace_stack=namespace_stack + [resource_name],
                        auth=auth,
                    )

            # Generate routes for each action
            bp_id = self.blueprints[-1]['id'] if self.blueprints else None
            for ns_bp in reversed(self.blueprints):
                if any(ns_bp['id'].startswith(f'namespace_{ns}')
                       for ns in namespace_stack):
                    bp_id = ns_bp['id']
                    break

            for action in actions:
                method, path_suffix, description = _RESOURCE_ACTIONS[action]
                full_path = resource_prefix + path_suffix

                route_id = f'route_{resource_name}_{action}_{"_".join(namespace_stack)}_{len(self.routes)}'
                self.routes.append({
                    'id': route_id,
                    'type': 'route',
                    'url_pattern': path_suffix or '/',
                    'full_url': full_path,
                    'methods': [method],
                    'controller': resource_name,
                    'action': action,
                    'function_name': action,
                    'file_path': file_path,
                    'line_number': line_number_at(original, match.start()) if match.start() < len(original) else 0,
                    'blueprint_id': bp_id,
                    'parameters': {
                        'path_params': self._extract_path_params(full_path),
                        'query_params': [],
                    },
                    'security': {
                        'requires_auth': auth,
                        'auth_decorators': [],
                    },
                })

        # --- Singular resource ---
        for match in _RESOURCE_SINGULAR_RE.finditer(remaining):
            # Make sure this isn't part of a 'resources' match
            start = match.start()
            if start > 0 and remaining[start - 1:start] == 's':
                continue

            resource_name = match.group(1)
            only_str = match.group(2)
            except_str = match.group(3)

            actions = self._resolve_actions(only_str, except_str, _ALL_SINGULAR_ACTIONS)
            resource_prefix = f'{prefix}/{resource_name}'

            bp_id = self.blueprints[-1]['id'] if self.blueprints else None
            for ns_bp in reversed(self.blueprints):
                if any(ns_bp['id'].startswith(f'namespace_{ns}')
                       for ns in namespace_stack):
                    bp_id = ns_bp['id']
                    break

            for action in actions:
                method, path_suffix, description = _SINGULAR_RESOURCE_ACTIONS[action]
                full_path = resource_prefix + path_suffix

                route_id = f'route_{resource_name}_{action}_{"_".join(namespace_stack)}_{len(self.routes)}'
                self.routes.append({
                    'id': route_id,
                    'type': 'route',
                    'url_pattern': path_suffix or '/',
                    'full_url': full_path,
                    'methods': [method],
                    'controller': resource_name,
                    'action': action,
                    'function_name': action,
                    'file_path': file_path,
                    'line_number': line_number_at(original, match.start()) if match.start() < len(original) else 0,
                    'blueprint_id': bp_id,
                    'parameters': {
                        'path_params': self._extract_path_params(full_path),
                        'query_params': [],
                    },
                    'security': {
                        'requires_auth': auth,
                        'auth_decorators': [],
                    },
                })

        # --- Explicit routes: get '/search', to: 'search#index' ---
        for match in _EXPLICIT_ROUTE_RE.finditer(remaining):
            method = match.group(1).upper()
            path = match.group(2)
            controller = match.group(3)
            action = match.group(4)

            full_path = f'{prefix}/{path.lstrip("/")}'

            bp_id = self.blueprints[-1]['id'] if self.blueprints else None
            for ns_bp in reversed(self.blueprints):
                if any(ns_bp['id'].startswith(f'namespace_{ns}')
                       for ns in namespace_stack):
                    bp_id = ns_bp['id']
                    break

            route_id = f'route_{method.lower()}_{path.replace("/", "_")}_{"_".join(namespace_stack)}_{len(self.routes)}'
            self.routes.append({
                'id': route_id,
                'type': 'route',
                'url_pattern': path,
                'full_url': full_path,
                'methods': [method],
                'controller': controller,
                'action': action,
                'function_name': f'{controller}#{action}' if controller and action else None,
                'file_path': file_path,
                'line_number': line_number_at(original, match.start()) if match.start() < len(original) else 0,
                'blueprint_id': bp_id,
                'parameters': {
                    'path_params': self._extract_path_params(full_path),
                    'query_params': [],
                },
                'security': {
                    'requires_auth': auth,
                    'auth_decorators': [],
                },
            })

        # --- Root route ---
        for match in _ROOT_RE.finditer(remaining):
            controller = match.group(1)
            action = match.group(2)

            self.routes.append({
                'id': f'route_root_{"_".join(namespace_stack)}_{len(self.routes)}',
                'type': 'route',
                'url_pattern': '/',
                'full_url': '/',
                'methods': ['GET'],
                'controller': controller,
                'action': action,
                'function_name': f'{controller}#{action}',
                'file_path': file_path,
                'line_number': line_number_at(original, match.start()) if match.start() < len(original) else 0,
                'blueprint_id': None,
                'parameters': {
                    'path_params': [],
                    'query_params': [],
                },
                'security': {
                    'requires_auth': False,
                    'auth_decorators': [],
                },
            })

    def _resolve_actions(self, only_str: Optional[str],
                         except_str: Optional[str],
                         all_actions: frozenset) -> List[str]:
        """Resolve which REST actions to generate based on only/except filters."""
        if only_str:
            only = set(_SYMBOL_RE.findall(only_str))
            return [a for a in all_actions if a in only]
        if except_str:
            excluded = set(_SYMBOL_RE.findall(except_str))
            return [a for a in all_actions if a not in excluded]
        return list(all_actions)

    def _extract_do_block(self, content: str, start_pos: int) -> Optional[str]:
        """Extract the body of a Ruby do...end block."""
        depth = 1
        i = start_pos

        block_openers = re.compile(
            r'\b(do|def|class|module|if|unless|while|until|for|case|begin)\b'
        )
        block_closer = re.compile(r'\bend\b')

        while i < len(content):
            opener = block_openers.search(content, i)
            closer = block_closer.search(content, i)

            if closer is None:
                return None

            if opener and opener.start() < closer.start():
                depth += 1
                i = opener.end()
            else:
                depth -= 1
                if depth == 0:
                    return content[start_pos:closer.start()]
                i = closer.end()

        return None

    def _extract_path_params(self, path: str) -> List[Dict]:
        """Extract path parameters from Rails-style URL patterns."""
        params = []
        for match in re.finditer(r':(\w+)', path):
            params.append({
                'name': match.group(1),
                'type': 'string',
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
