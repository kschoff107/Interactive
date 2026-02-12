"""
ABAP ICF/OData/RAP Service Parser - Extract API route definitions from
ABAP service implementations: OData DPC classes, RAP behavior definitions,
and ICF HTTP handler classes.

Uses regex-based parsing on comment-stripped, case-normalized source.
ABAP statements end with periods (.) and keywords are case-insensitive.
"""

import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from ..base import (
    BaseRoutesParser,
    find_source_files,
    line_number_at,
    read_file_safe,
    strip_comments,
)

# ---------------------------------------------------------------------------
# OData DPC operation -> HTTP method mapping
# ---------------------------------------------------------------------------

_ODATA_METHOD_MAP = {
    'GET_ENTITYSET': 'GET',
    'GET_ENTITY': 'GET',
    'CREATE_ENTITY': 'POST',
    'UPDATE_ENTITY': 'PUT',
    'DELETE_ENTITY': 'DELETE',
    'EXECUTE_ACTION': 'POST',
    'PATCH_ENTITY': 'PATCH',
    'GET_STREAM': 'GET',
    'CREATE_STREAM': 'POST',
    'UPDATE_STREAM': 'PUT',
    'DELETE_STREAM': 'DELETE',
}

# OData operation -> description
_ODATA_OP_DESC = {
    'GET_ENTITYSET': 'List entities',
    'GET_ENTITY': 'Get single entity',
    'CREATE_ENTITY': 'Create entity',
    'UPDATE_ENTITY': 'Update entity',
    'DELETE_ENTITY': 'Delete entity',
    'EXECUTE_ACTION': 'Execute action',
    'PATCH_ENTITY': 'Patch entity',
    'GET_STREAM': 'Get media resource',
    'CREATE_STREAM': 'Create media resource',
    'UPDATE_STREAM': 'Update media resource',
    'DELETE_STREAM': 'Delete media resource',
}

# RAP operation -> HTTP method mapping
_RAP_METHOD_MAP = {
    'CREATE': 'POST',
    'UPDATE': 'PUT',
    'DELETE': 'DELETE',
    'READ': 'GET',
    'ACTION': 'POST',
    'FUNCTION': 'GET',
    'DETERMINATION': 'POST',
    'VALIDATION': 'POST',
}

# ICF handler method -> HTTP method mapping
_ICF_HANDLER_MAP = {
    'HANDLE_REQUEST': 'ALL',
    'IF_HTTP_EXTENSION~HANDLE_REQUEST': 'ALL',
    'GET_ROOT_HANDLER': 'ALL',
    'HANDLE_GET': 'GET',
    'HANDLE_POST': 'POST',
    'HANDLE_PUT': 'PUT',
    'HANDLE_DELETE': 'DELETE',
    'HANDLE_PATCH': 'PATCH',
    'HANDLE_HEAD': 'HEAD',
    'HANDLE_OPTIONS': 'OPTIONS',
}

# Known ABAP HTTP handler base classes
_HTTP_HANDLER_BASES = {
    'CL_REST_HTTP_HANDLER',
    'CL_HTTP_HANDLER',
    'IF_HTTP_EXTENSION',
    'CL_REST_RESOURCE',
    'IF_REST_RESOURCE',
}

# Known OData base class pattern (ends with _DPC)
_RE_DPC_CLASS_NAME = re.compile(r'\w+_DPC(?:_EXT)?$')

# ---------------------------------------------------------------------------
# Compiled regex patterns
# ---------------------------------------------------------------------------

# CLASS name DEFINITION [INHERITING FROM parent] ...
_RE_CLASS_DEF = re.compile(
    r'CLASS\s+(\w+)\s+DEFINITION'
    r'((?:\s+(?:INHERITING\s+FROM\s+\w+|PUBLIC|ABSTRACT|FINAL|'
    r'CREATE\s+\w+|FOR\s+TESTING)\b[^.]*)*)'
    r'\s*\.',
)

# INHERITING FROM parent
_RE_INHERITING = re.compile(r'INHERITING\s+FROM\s+(\w+)')

# CLASS ... ENDCLASS block boundary
_RE_ENDCLASS = re.compile(r'ENDCLASS\s*\.')

# METHOD declarations (in DEFINITION sections)
_RE_METHOD_DECL = re.compile(
    r'METHODS\s*:?\s*(\S+)'
    r'((?:\s+(?:IMPORTING|EXPORTING|CHANGING|RETURNING|RAISING|REDEFINITION|'
    r'FOR\s+TESTING|ABSTRACT|FINAL)\b[^,.]*)*)',
)

# OData interface method redefinition pattern
# e.g., /IWBEP/IF_MGW_APPL_SRV_RUNTIME~GET_ENTITYSET REDEFINITION
_RE_ODATA_REDEF = re.compile(
    r'(?:/\w+/)?IF_MGW_APPL_SRV_RUNTIME~(\w+)\s+REDEFINITION',
)

# CLASS name IMPLEMENTATION
_RE_CLASS_IMPL = re.compile(
    r'CLASS\s+(\w+)\s+IMPLEMENTATION\s*\.',
)

# METHOD name.
_RE_METHOD_START = re.compile(r'METHOD\s+(\S+)\s*\.')

# ENDMETHOD.
_RE_ENDMETHOD = re.compile(r'ENDMETHOD\s*\.')

# RAP behavior definition:
# define behavior for ENTITY alias ALIAS { ... }
# Uses a non-greedy match that allows nested braces
_RE_RAP_BEHAVIOR = re.compile(
    r'DEFINE\s+BEHAVIOR\s+FOR\s+(\w+)'
    r'(?:\s+ALIAS\s+(\w+))?'
    r'\s*\{((?:[^{}]|\{[^{}]*\})*)\}',
    re.DOTALL,
)

# RAP CRUD operations
_RE_RAP_CREATE = re.compile(r'\bCREATE\s*;')
_RE_RAP_UPDATE = re.compile(r'\bUPDATE\s*;')
_RE_RAP_DELETE = re.compile(r'\bDELETE\s*;')

# RAP action: action name [result [1] $self] ;
_RE_RAP_ACTION = re.compile(
    r'\bACTION\s+(\w+)[^;]*;',
)

# RAP association: association _Name { create; }
_RE_RAP_ASSOCIATION = re.compile(
    r'\bASSOCIATION\s+(\w+)\s*\{([^}]*)\}',
    re.DOTALL,
)

# RAP determination/validation
_RE_RAP_DETERMINATION = re.compile(
    r'\bDETERMINATION\s+(\w+)\s+ON\s+(?:MODIFY|SAVE)\b',
)
_RE_RAP_VALIDATION = re.compile(
    r'\bVALIDATION\s+(\w+)\s+ON\s+(?:SAVE)\b',
)

# REST handler method names — matches both METHODS: name and comma-separated names
_RE_HANDLER_METHOD = re.compile(
    r'(?:METHODS?\s*:?\s*|,\s*)(HANDLE_\w+|GET_ROOT_HANDLER|'
    r'IF_HTTP_EXTENSION~HANDLE_REQUEST|HANDLE_REQUEST)',
)

# Entity name extraction from OData DPC class name:
# ZCL_USER_DPC_EXT -> USER (strip prefix Z/Y + CL_ and suffix _DPC/_DPC_EXT)
_RE_ENTITY_FROM_CLASS = re.compile(
    r'^[ZY]?CL_(.+?)_DPC(?:_EXT)?$',
)

# Annotations for CDS/RAP: @EndUserText.label: 'text'
_RE_ANNOTATION_LABEL = re.compile(
    r"@ENDUSERTEXT\.LABEL\s*:\s*'([^']*)'",
)


class ABAPICFParser(BaseRoutesParser):
    """Parse ABAP service implementations into standardized API routes format.

    Handles:
    - OData DPC classes (inheriting from *_DPC) with entity CRUD operations
    - RAP behavior definitions (define behavior for ... { create; update; ... })
    - ICF HTTP handler classes (inheriting from cl_rest_http_handler etc.)
    - Maps operations to HTTP methods and route patterns
    """

    FILE_EXTENSIONS = ['.abap', '.txt', '.bdef', '.asddls']

    def parse(self) -> Dict:
        """Parse all ABAP files for service/route definitions."""
        files = find_source_files(str(self.project_path), self.FILE_EXTENSIONS)

        for fpath in files:
            content = read_file_safe(fpath)
            if not content:
                continue
            try:
                self._parse_file(content, fpath)
            except Exception:
                continue

        return self.make_routes_result()

    # ------------------------------------------------------------------
    # File-level parsing
    # ------------------------------------------------------------------

    def _parse_file(self, content: str, file_path: str):
        """Parse a single ABAP file for service definitions."""
        stripped = strip_comments(content, 'abap')
        upper = stripped.upper()

        # Derive module name
        rel_path = os.path.relpath(file_path, str(self.project_path))
        module_name = rel_path.replace(os.sep, '.').rsplit('.', 1)[0]

        # Parse class definitions to find DPC / handler classes
        self._parse_odata_dpc_classes(upper, content, file_path, module_name)

        # Parse RAP behavior definitions
        self._parse_rap_behaviors(upper, content, file_path, module_name)

        # Parse ICF handler classes
        self._parse_icf_handlers(upper, content, file_path, module_name)

    # ------------------------------------------------------------------
    # OData DPC class parsing
    # ------------------------------------------------------------------

    def _parse_odata_dpc_classes(
        self, upper: str, original: str, file_path: str, module_name: str
    ):
        """Parse OData Data Provider Classes (DPC) for entity operations."""
        for cm in _RE_CLASS_DEF.finditer(upper):
            class_name = cm.group(1).strip()
            options = cm.group(2).strip() if cm.group(2) else ''

            # Check if this is a DPC class
            if not _RE_DPC_CLASS_NAME.match(class_name):
                # Also check parent class
                inherit_m = _RE_INHERITING.search(options)
                parent = inherit_m.group(1).strip() if inherit_m else ''
                if not _RE_DPC_CLASS_NAME.match(parent):
                    continue

            # Extract entity name from class name
            entity_name = self._extract_entity_name(class_name)
            line_num = line_number_at(original, cm.start())

            # Find the class body (up to ENDCLASS)
            search_start = cm.end()
            endclass_m = _RE_ENDCLASS.search(upper, search_start)
            class_body_end = endclass_m.start() if endclass_m else len(upper)
            class_body = upper[search_start:class_body_end]

            # Find OData method redefinitions
            operations = []
            for rm in _RE_ODATA_REDEF.finditer(class_body):
                op_name = rm.group(1).strip()
                operations.append(op_name)

            # Also check method declarations for common patterns
            for md in _RE_METHOD_DECL.finditer(class_body):
                method_name = md.group(1).strip()
                method_upper = method_name.upper()
                for op_key in _ODATA_METHOD_MAP:
                    if op_key in method_upper:
                        if op_key not in operations:
                            operations.append(op_key)

            if not operations:
                continue

            # Create blueprint for this DPC class
            bp_id = f'blueprint_{module_name}_{class_name}_{line_num}'
            service_path = f'/sap/opu/odata/sap/{entity_name}'

            self.blueprints.append({
                'id': bp_id,
                'type': 'odata_service',
                'name': entity_name,
                'class_name': class_name,
                'url_prefix': service_path,
                'file_path': file_path,
                'line_number': line_num,
                'route_count': len(operations),
            })

            # Create routes for each operation
            for op_name in operations:
                http_method = _ODATA_METHOD_MAP.get(op_name, 'GET')
                description = _ODATA_OP_DESC.get(op_name, op_name)

                # Determine URL pattern
                if 'ENTITYSET' in op_name:
                    url_pattern = f'/{entity_name}Set'
                elif 'STREAM' in op_name:
                    url_pattern = f'/{entity_name}Set({{key}})/$value'
                elif op_name in ('CREATE_ENTITY', 'EXECUTE_ACTION'):
                    url_pattern = f'/{entity_name}Set'
                else:
                    url_pattern = f'/{entity_name}Set({{key}})'

                route_id = f'route_{module_name}_{class_name}_{op_name}_{line_num}'
                op_line = line_number_at(original, cm.start())

                self.routes.append({
                    'id': route_id,
                    'type': 'route',
                    'url_pattern': url_pattern,
                    'full_url': f'{service_path}{url_pattern}',
                    'methods': [http_method],
                    'blueprint_id': bp_id,
                    'function_name': op_name,
                    'line_number': op_line,
                    'end_line': op_line,
                    'docstring': description,
                    'file_path': file_path,
                    'module': module_name,
                    'security': {
                        'requires_auth': True,  # OData always requires SAP auth
                        'auth_decorators': ['sap_auth'],
                    },
                    'parameters': {
                        'path_params': self._odata_path_params(op_name),
                        'query_params': self._odata_query_params(op_name),
                    },
                })

    # ------------------------------------------------------------------
    # RAP behavior definition parsing
    # ------------------------------------------------------------------

    def _parse_rap_behaviors(
        self, upper: str, original: str, file_path: str, module_name: str
    ):
        """Parse RAP (RESTful ABAP Programming) behavior definitions."""
        # Check for label annotation preceding behavior definition
        label = None
        label_m = _RE_ANNOTATION_LABEL.search(upper)
        if label_m:
            label = label_m.group(1).strip()

        for bm in _RE_RAP_BEHAVIOR.finditer(upper):
            entity_name = bm.group(1).strip()
            alias = bm.group(2).strip() if bm.group(2) else entity_name
            behavior_body = bm.group(3)
            line_num = line_number_at(original, bm.start())

            # Create blueprint for the RAP service
            bp_id = f'blueprint_{module_name}_{entity_name}_{line_num}'
            service_path = f'/sap/opu/odata4/sap/{alias.lower()}'

            self.blueprints.append({
                'id': bp_id,
                'type': 'rap_service',
                'name': alias,
                'entity_name': entity_name,
                'url_prefix': service_path,
                'file_path': file_path,
                'line_number': line_num,
                'route_count': 0,  # updated below
                'label': label,
            })

            route_count = 0

            # CRUD operations
            crud_ops = [
                (_RE_RAP_CREATE, 'CREATE', 'POST', f'/{alias}'),
                (_RE_RAP_UPDATE, 'UPDATE', 'PUT', f'/{alias}({{key}})'),
                (_RE_RAP_DELETE, 'DELETE', 'DELETE', f'/{alias}({{key}})'),
            ]

            for pattern, op_name, http_method, url_pat in crud_ops:
                if pattern.search(behavior_body):
                    route_id = f'route_{module_name}_{entity_name}_{op_name}_{line_num}'
                    self.routes.append({
                        'id': route_id,
                        'type': 'route',
                        'url_pattern': url_pat,
                        'full_url': f'{service_path}{url_pat}',
                        'methods': [http_method],
                        'blueprint_id': bp_id,
                        'function_name': op_name,
                        'line_number': line_num,
                        'end_line': line_num,
                        'docstring': f'{op_name} {alias}',
                        'file_path': file_path,
                        'module': module_name,
                        'security': {
                            'requires_auth': True,
                            'auth_decorators': ['sap_auth'],
                        },
                        'parameters': {
                            'path_params': [],
                            'query_params': [],
                        },
                    })
                    route_count += 1

            # READ is implicit in RAP if entity is defined
            route_id = f'route_{module_name}_{entity_name}_READ_{line_num}'
            self.routes.append({
                'id': route_id,
                'type': 'route',
                'url_pattern': f'/{alias}',
                'full_url': f'{service_path}/{alias}',
                'methods': ['GET'],
                'blueprint_id': bp_id,
                'function_name': 'READ',
                'line_number': line_num,
                'end_line': line_num,
                'docstring': f'Read {alias}',
                'file_path': file_path,
                'module': module_name,
                'security': {
                    'requires_auth': True,
                    'auth_decorators': ['sap_auth'],
                },
                'parameters': {
                    'path_params': [],
                    'query_params': [
                        {'name': '$filter', 'type': 'string'},
                        {'name': '$select', 'type': 'string'},
                        {'name': '$expand', 'type': 'string'},
                    ],
                },
            })
            route_count += 1

            # Actions
            for am in _RE_RAP_ACTION.finditer(behavior_body):
                action_name = am.group(1).strip()
                route_id = f'route_{module_name}_{entity_name}_action_{action_name}_{line_num}'
                self.routes.append({
                    'id': route_id,
                    'type': 'route',
                    'url_pattern': f'/{alias}({{key}})/{action_name}',
                    'full_url': f'{service_path}/{alias}({{key}})/{action_name}',
                    'methods': ['POST'],
                    'blueprint_id': bp_id,
                    'function_name': action_name,
                    'line_number': line_num,
                    'end_line': line_num,
                    'docstring': f'Action: {action_name}',
                    'file_path': file_path,
                    'module': module_name,
                    'security': {
                        'requires_auth': True,
                        'auth_decorators': ['sap_auth'],
                    },
                    'parameters': {
                        'path_params': [{'name': 'key', 'type': 'string'}],
                        'query_params': [],
                    },
                })
                route_count += 1

            # Associations with create
            for assoc_m in _RE_RAP_ASSOCIATION.finditer(behavior_body):
                assoc_name = assoc_m.group(1).strip()
                assoc_body = assoc_m.group(2).strip()
                if 'CREATE' in assoc_body.upper():
                    route_id = f'route_{module_name}_{entity_name}_assoc_{assoc_name}_{line_num}'
                    self.routes.append({
                        'id': route_id,
                        'type': 'route',
                        'url_pattern': f'/{alias}({{key}})/{assoc_name}',
                        'full_url': f'{service_path}/{alias}({{key}})/{assoc_name}',
                        'methods': ['POST'],
                        'blueprint_id': bp_id,
                        'function_name': f'create_{assoc_name}',
                        'line_number': line_num,
                        'end_line': line_num,
                        'docstring': f'Create via association {assoc_name}',
                        'file_path': file_path,
                        'module': module_name,
                        'security': {
                            'requires_auth': True,
                            'auth_decorators': ['sap_auth'],
                        },
                        'parameters': {
                            'path_params': [{'name': 'key', 'type': 'string'}],
                            'query_params': [],
                        },
                    })
                    route_count += 1

            # Determinations and validations
            for det_m in _RE_RAP_DETERMINATION.finditer(behavior_body):
                det_name = det_m.group(1).strip()
                route_count += 1  # Counted but not exposed as HTTP routes

            for val_m in _RE_RAP_VALIDATION.finditer(behavior_body):
                val_name = val_m.group(1).strip()
                route_count += 1

            # Update blueprint route count
            for bp in self.blueprints:
                if bp['id'] == bp_id:
                    bp['route_count'] = route_count
                    break

    # ------------------------------------------------------------------
    # ICF HTTP handler parsing
    # ------------------------------------------------------------------

    def _parse_icf_handlers(
        self, upper: str, original: str, file_path: str, module_name: str
    ):
        """Parse ICF HTTP handler classes."""
        for cm in _RE_CLASS_DEF.finditer(upper):
            class_name = cm.group(1).strip()
            options = cm.group(2).strip() if cm.group(2) else ''

            # Check if this inherits from an HTTP handler base
            inherit_m = _RE_INHERITING.search(options)
            parent = inherit_m.group(1).strip() if inherit_m else ''

            if parent not in _HTTP_HANDLER_BASES:
                # Also skip DPC classes (already handled)
                if _RE_DPC_CLASS_NAME.match(class_name):
                    continue
                if parent not in _HTTP_HANDLER_BASES:
                    continue

            line_num = line_number_at(original, cm.start())

            # Find handler methods in the class body
            search_start = cm.end()
            endclass_m = _RE_ENDCLASS.search(upper, search_start)
            class_body_end = endclass_m.start() if endclass_m else len(upper)
            class_body = upper[search_start:class_body_end]

            # Extract handler method names
            handler_methods = []
            for hm in _RE_HANDLER_METHOD.finditer(class_body):
                method_name = hm.group(1).strip()
                handler_methods.append(method_name)

            # Also scan for method declarations
            for md in _RE_METHOD_DECL.finditer(class_body):
                method_name = md.group(1).strip()
                method_upper = method_name.upper()
                if method_upper in _ICF_HANDLER_MAP:
                    if method_upper not in [h.upper() for h in handler_methods]:
                        handler_methods.append(method_upper)

            if not handler_methods:
                continue

            # Derive service path from class name
            service_name = class_name.lstrip('ZY').lstrip('CL_').lower()
            service_path = f'/sap/bc/http/sap/{service_name}'

            # Create blueprint
            bp_id = f'blueprint_{module_name}_{class_name}_{line_num}'
            self.blueprints.append({
                'id': bp_id,
                'type': 'icf_handler',
                'name': service_name,
                'class_name': class_name,
                'url_prefix': service_path,
                'file_path': file_path,
                'line_number': line_num,
                'route_count': len(handler_methods),
            })

            # Create routes for each handler method
            for method_name in handler_methods:
                method_upper = method_name.upper()
                http_method = _ICF_HANDLER_MAP.get(method_upper, 'ALL')

                route_id = f'route_{module_name}_{class_name}_{method_name}_{line_num}'
                self.routes.append({
                    'id': route_id,
                    'type': 'route',
                    'url_pattern': '/',
                    'full_url': service_path,
                    'methods': [http_method] if http_method != 'ALL' else [
                        'GET', 'POST', 'PUT', 'DELETE', 'PATCH',
                    ],
                    'blueprint_id': bp_id,
                    'function_name': method_name,
                    'line_number': line_num,
                    'end_line': line_num,
                    'docstring': f'HTTP handler: {method_name}',
                    'file_path': file_path,
                    'module': module_name,
                    'security': {
                        'requires_auth': True,
                        'auth_decorators': ['sap_auth'],
                    },
                    'parameters': {
                        'path_params': [],
                        'query_params': [],
                    },
                })

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_entity_name(class_name: str) -> str:
        """Extract entity/service name from a DPC class name.

        ZCL_USER_DPC_EXT -> USER
        ZCL_ORDER_DPC -> ORDER
        YCL_MATERIAL_SRV_DPC_EXT -> MATERIAL_SRV
        """
        m = _RE_ENTITY_FROM_CLASS.match(class_name)
        if m:
            return m.group(1).strip()
        # Fallback: strip common prefixes/suffixes
        name = class_name
        for prefix in ('ZCL_', 'YCL_', 'CL_', 'Z_', 'Y_'):
            if name.startswith(prefix):
                name = name[len(prefix):]
                break
        for suffix in ('_DPC_EXT', '_DPC', '_SRV'):
            if name.endswith(suffix):
                name = name[:-len(suffix)]
                break
        return name

    @staticmethod
    def _odata_path_params(op_name: str) -> List[Dict]:
        """Return path parameters for an OData operation."""
        if op_name in ('GET_ENTITYSET', 'CREATE_ENTITY'):
            return []
        return [{'name': 'key', 'type': 'string'}]

    @staticmethod
    def _odata_query_params(op_name: str) -> List[Dict]:
        """Return standard OData query parameters for GET operations."""
        if 'GET' in op_name:
            params = [
                {'name': '$format', 'type': 'string'},
            ]
            if 'ENTITYSET' in op_name:
                params.extend([
                    {'name': '$filter', 'type': 'string'},
                    {'name': '$select', 'type': 'string'},
                    {'name': '$expand', 'type': 'string'},
                    {'name': '$top', 'type': 'integer'},
                    {'name': '$skip', 'type': 'integer'},
                    {'name': '$orderby', 'type': 'string'},
                    {'name': '$inlinecount', 'type': 'string'},
                ])
            return params
        return []
