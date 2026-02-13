"""
JavaScript/TypeScript Structure Parser - Extract class and module structure
from JS/TS source code using regex.

Detects:
  - Class declarations (with inheritance, implements, abstract)
  - Interface declarations (with extends)
  - Methods (with visibility, static, async, abstract modifiers)
  - Properties (with type annotations)
  - Decorators (@Decorator patterns)
  - Import statements
"""

import logging
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from ..base import (
    BaseStructureParser,
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

# [export] [abstract] class Name [extends Base] [implements A, B] {
_CLASS_RE = re.compile(
    r'(?:export\s+)?(?:abstract\s+)?class\s+(\w+)'
    r'(?:\s+extends\s+([\w.]+))?'
    r'(?:\s+implements\s+([\w.,\s]+))?'
    r'\s*\{',
)

# [export] interface Name [extends A, B] {
_INTERFACE_RE = re.compile(
    r'(?:export\s+)?interface\s+(\w+)'
    r'(?:\s+extends\s+([\w.,\s]+))?'
    r'\s*\{',
)

# Method signatures with optional modifiers:
# [public|private|protected] [static] [async] [abstract] [readonly] name(params) [: ReturnType] {
_METHOD_RE = re.compile(
    r'(?:(?:public|private|protected)\s+)?'
    r'(?:static\s+)?'
    r'(?:async\s+)?'
    r'(?:abstract\s+)?'
    r'(?:readonly\s+)?'
    r'(\w+)\s*\(([^)]*)\)'
    r'(?:\s*:\s*[\w<>\[\],\s|&?.*]+?)?'
    r'\s*[{;]',
)

# Property declarations with type annotations: name[?]: Type
_PROPERTY_RE = re.compile(
    r'(?:(?:public|private|protected)\s+)?'
    r'(?:static\s+)?'
    r'(?:readonly\s+)?'
    r'(\w+)(\??)\s*:\s*([\w<>\[\],\s|&?.*]+?)\s*[;=\n]',
)

# import ... from 'module'
_IMPORT_RE = re.compile(
    r"""import\s+(?:(?:type\s+)?(?:\{[^}]*\}|\*\s+as\s+\w+|\w+)"""
    r"""(?:\s*,\s*(?:\{[^}]*\}|\*\s+as\s+\w+))?)\s+from\s+['"]([^'"]+)['"]""",
)

# @DecoratorName or @DecoratorName(...)
_DECORATOR_RE = re.compile(
    r'@(\w+)(?:\([^)]*\))?',
)

# Keywords that should not be treated as method names
_SKIP_METHOD_NAMES = frozenset({
    'if', 'else', 'for', 'while', 'switch', 'return',
    'const', 'let', 'var', 'new', 'throw', 'import', 'export',
})


class JSStructureParser(BaseStructureParser):
    """Parse JavaScript/TypeScript source code to extract class and module structure."""

    FILE_EXTENSIONS = ['.js', '.ts', '.jsx', '.tsx']

    def parse(self) -> Dict:
        """Parse all JS/TS files and return standardized code structure dict."""
        files = find_source_files(str(self.project_path), self.FILE_EXTENSIONS)

        for fpath in files:
            try:
                self._parse_file(fpath)
            except Exception as e:
                logger.warning("Failed to parse %s: %s", fpath, e)
                continue

        return self.make_structure_result()

    # ------------------------------------------------------------------
    # File-level parsing
    # ------------------------------------------------------------------

    def _parse_file(self, filepath: str):
        """Parse a single JS/TS file for classes, interfaces, and imports."""
        content = read_file_safe(filepath)
        if not content:
            return

        stripped = strip_comments(content, 'javascript')
        rel_path = self._relative_path(filepath)
        module_name = rel_path.replace(os.sep, '.').rsplit('.', 1)[0]

        # --- Extract imports ---
        for m in _IMPORT_RE.finditer(stripped):
            import_source = m.group(1)
            line_num = line_number_at(content, m.start())
            self.imports.append({
                'module': module_name,
                'file_path': filepath,
                'line_number': line_num,
                'source': import_source,
                'statement': content[m.start():m.end()].strip(),
            })

        # --- Extract classes ---
        for m in _CLASS_RE.finditer(stripped):
            class_name = m.group(1)
            base_class = m.group(2)
            implements_str = m.group(3)
            line_num = line_number_at(content, m.start())

            # Determine base classes
            base_classes = []
            if base_class:
                base_classes.append(base_class.strip())

            # Determine implemented interfaces
            interfaces = []
            if implements_str:
                interfaces = [s.strip() for s in implements_str.split(',')
                              if s.strip()]

            # Detect abstract
            prefix_text = stripped[max(0, m.start() - 30):m.start()]
            is_abstract = bool(re.search(r'\babstract\b', prefix_text))

            # Extract decorators above the class declaration
            decorators = self._extract_decorators(content, m.start())

            # Extract body
            body, body_start, body_end = extract_block_body(stripped, m.start())

            # Extract members from body
            methods = []
            properties = []
            if body and body_start >= 0:
                methods, properties = self._extract_members(
                    body, body_start, content,
                )

            class_id = f"class_{module_name}_{class_name}"
            self.classes.append({
                'id': class_id,
                'name': class_name,
                'type': 'class',
                'module': module_name,
                'file_path': filepath,
                'line_number': line_num,
                'end_line': line_number_at(content, body_end) if body_end >= 0 else line_num,
                'base_classes': base_classes,
                'interfaces': interfaces,
                'is_abstract': is_abstract,
                'decorators': decorators,
                'methods': methods,
                'properties': properties,
            })

        # --- Extract interfaces ---
        for m in _INTERFACE_RE.finditer(stripped):
            iface_name = m.group(1)
            extends_str = m.group(2)
            line_num = line_number_at(content, m.start())

            base_classes = []
            if extends_str:
                base_classes = [s.strip() for s in extends_str.split(',')
                                if s.strip()]

            # Extract body
            body, body_start, body_end = extract_block_body(stripped, m.start())

            methods = []
            properties = []
            if body and body_start >= 0:
                methods, properties = self._extract_members(
                    body, body_start, content,
                )

            iface_id = f"interface_{module_name}_{iface_name}"
            self.classes.append({
                'id': iface_id,
                'name': iface_name,
                'type': 'interface',
                'module': module_name,
                'file_path': filepath,
                'line_number': line_num,
                'end_line': line_number_at(content, body_end) if body_end >= 0 else line_num,
                'base_classes': base_classes,
                'interfaces': [],
                'is_abstract': False,
                'is_interface': True,
                'decorators': [],
                'methods': methods,
                'properties': properties,
            })

        # --- Track module ---
        class_count = sum(
            1 for c in self.classes if c.get('module') == module_name
        )
        if class_count > 0 or any(
            i.get('module') == module_name for i in self.imports
        ):
            self.modules.append({
                'id': f"module_{module_name}",
                'name': module_name,
                'file_path': filepath,
                'class_count': class_count,
            })

    # ------------------------------------------------------------------
    # Member extraction
    # ------------------------------------------------------------------

    def _extract_members(
        self, body: str, body_start: int, original: str,
    ) -> Tuple[List[Dict], List[Dict]]:
        """Extract methods and properties from a class/interface body.

        Args:
            body: The text inside the class braces.
            body_start: Absolute position of body start in original content.
            original: The original (unstripped) file content for line numbers.

        Returns:
            (methods, properties) tuple.
        """
        methods = []
        method_names: Set[str] = set()

        # --- Methods ---
        for m in _METHOD_RE.finditer(body):
            method_name = m.group(1)
            params_str = m.group(2)

            # Skip false-positive keyword matches
            if method_name in _SKIP_METHOD_NAMES:
                continue

            method_names.add(method_name)

            # Inspect prefix text for modifiers
            prefix_start = max(0, m.start() - 60)
            prefix_text = body[prefix_start:m.start()]

            visibility = 'public'
            if re.search(r'\bprivate\b', prefix_text):
                visibility = 'private'
            elif re.search(r'\bprotected\b', prefix_text):
                visibility = 'protected'

            is_static = bool(re.search(r'\bstatic\b', prefix_text))
            is_async = bool(re.search(r'\basync\b', prefix_text))
            is_abstract = bool(re.search(r'\babstract\b', prefix_text))

            # Parse parameters
            params = self._parse_params(params_str)

            # Extract return type if present
            return_type = None
            after_paren = body[m.start():m.end()]
            rt_match = re.search(r'\)\s*:\s*([\w<>\[\],\s|&?.*]+?)\s*[{;]$', after_paren)
            if rt_match:
                return_type = rt_match.group(1).strip()

            abs_pos = body_start + m.start()
            line_num = line_number_at(original, abs_pos)

            methods.append({
                'name': method_name,
                'line_number': line_num,
                'parameters': params,
                'return_type': return_type,
                'visibility': visibility,
                'is_static': is_static,
                'is_async': is_async,
                'is_abstract': is_abstract,
            })

        # --- Properties ---
        properties = []
        for m in _PROPERTY_RE.finditer(body):
            prop_name = m.group(1)
            is_optional = m.group(2) == '?'
            prop_type = m.group(3).strip()

            # Skip if name is actually a method or a keyword
            if prop_name in method_names:
                continue
            if prop_name in _SKIP_METHOD_NAMES:
                continue

            # Inspect prefix text for modifiers
            prefix_start = max(0, m.start() - 60)
            prefix_text = body[prefix_start:m.start()]

            visibility = 'public'
            if re.search(r'\bprivate\b', prefix_text):
                visibility = 'private'
            elif re.search(r'\bprotected\b', prefix_text):
                visibility = 'protected'

            is_static = bool(re.search(r'\bstatic\b', prefix_text))
            is_readonly = bool(re.search(r'\breadonly\b', prefix_text))

            abs_pos = body_start + m.start()
            line_num = line_number_at(original, abs_pos)

            properties.append({
                'name': prop_name,
                'type': prop_type,
                'line_number': line_num,
                'visibility': visibility,
                'is_static': is_static,
                'is_readonly': is_readonly,
                'is_optional': is_optional,
            })

        return methods, properties

    # ------------------------------------------------------------------
    # Decorator extraction
    # ------------------------------------------------------------------

    def _extract_decorators(self, content: str, class_start: int) -> List[str]:
        """Extract decorator names from lines above a class declaration.

        Scans backward from class_start to find @Decorator patterns on
        preceding lines.

        Args:
            content: Full original file content.
            class_start: Character position where the class match starts.

        Returns:
            List of decorator name strings.
        """
        decorators = []

        # Find the start of the line containing class_start
        line_start = content.rfind('\n', 0, class_start)
        if line_start < 0:
            line_start = 0
        else:
            line_start += 1  # skip the newline itself

        # Look at up to 20 lines above the class
        preceding_text = content[max(0, line_start - 1000):line_start]
        lines = preceding_text.split('\n')

        # Walk backward through lines looking for decorators
        for line in reversed(lines):
            stripped_line = line.strip()
            if not stripped_line:
                continue
            dec_match = _DECORATOR_RE.match(stripped_line)
            if dec_match:
                decorators.append(dec_match.group(1))
            else:
                # Stop once we hit a non-decorator, non-empty line
                break

        decorators.reverse()
        return decorators

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_params(params_str: str) -> List[str]:
        """Parse parameter string into list of parameter names."""
        if not params_str or not params_str.strip():
            return []
        params = []
        for p in params_str.split(','):
            p = p.strip()
            # Remove TypeScript type annotations
            p = re.sub(r':\s*[\w<>\[\],\s|&?.*]+$', '', p)
            # Remove default values
            p = re.sub(r'\s*=\s*.*$', '', p)
            p = p.strip()
            if p and p not in ('', '{', '}', '...'):
                # Handle rest params
                p = p.lstrip('.')
                if p:
                    params.append(p)
        return params

    def _relative_path(self, file_path: str) -> str:
        """Get path relative to project root."""
        try:
            return str(Path(file_path).relative_to(self.project_path))
        except ValueError:
            return os.path.basename(file_path)
