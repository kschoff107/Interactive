"""
Base classes and shared utilities for all parsers.

Provides standardized interfaces, file discovery, comment stripping,
and result formatting used across schema, flow, and routes parsers.
"""

import logging
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


SKIP_DIRS = {
    '__pycache__', '.git', '.venv', 'venv', 'env', 'node_modules',
    '.pytest_cache', '.tox', 'dist', 'build', '.eggs', 'vendor',
    'bin', 'obj', 'target', 'out', '.idea', '.vscode', '.next',
    'coverage', '.nyc_output', 'tmp', 'temp', '.bundle',
}


def find_source_files(project_path: str, extensions: List[str],
                      skip_dirs: Set[str] = None) -> List[str]:
    """Walk project_path returning file paths matching extensions.

    Args:
        project_path: Root directory to search.
        extensions: List of file extensions including dot (e.g. ['.py', '.pyi']).
        skip_dirs: Directory names to skip. Defaults to SKIP_DIRS.

    Returns:
        List of absolute file paths.
    """
    skip = skip_dirs or SKIP_DIRS
    ext_set = set(extensions)
    results = []

    for root, dirs, files in os.walk(project_path):
        dirs[:] = [d for d in dirs if d not in skip]
        for fname in files:
            if any(fname.endswith(ext) for ext in ext_set):
                results.append(os.path.join(root, fname))

    return results


def read_file_safe(file_path: str, encoding: str = 'utf-8') -> Optional[str]:
    """Read a file, returning content or None on error.

    Tries utf-8 first, falls back to latin-1 for non-UTF files (e.g. ABAP).
    """
    for enc in [encoding, 'latin-1']:
        try:
            with open(file_path, 'r', encoding=enc) as f:
                return f.read()
        except UnicodeDecodeError:
            continue
        except (PermissionError, OSError) as e:
            logger.warning("Cannot read %s: %s", file_path, e)
            return None
        except Exception as e:
            logger.error("Unexpected error reading %s: %s", file_path, e, exc_info=True)
            return None
    return None


# ---------------------------------------------------------------------------
# Comment / string-literal stripping
# ---------------------------------------------------------------------------

_STRIP_PATTERNS = {
    # C-family: Java, C#, Go, JavaScript, TypeScript
    'c_family': re.compile(
        r'//[^\n]*'              # single-line comments
        r'|/\*.*?\*/'            # multi-line comments
        r"|'(?:\\.|[^'\\])*'"    # single-quoted strings
        r'|"(?:\\.|[^"\\])*"'    # double-quoted strings
        r'|`(?:\\.|[^`\\])*`',   # template literals (JS/TS/Go)
        re.DOTALL,
    ),
    # Python
    'python': re.compile(
        r'""".*?"""'             # triple-double-quoted strings
        r"|'''.*?'''"            # triple-single-quoted strings
        r'|#[^\n]*'             # single-line comments
        r"|'(?:\\.|[^'\\])*'"   # single-quoted strings
        r'|"(?:\\.|[^"\\])*"',  # double-quoted strings
        re.DOTALL,
    ),
    # Ruby
    'ruby': re.compile(
        r'#[^\n]*'              # single-line comments
        r'|=begin.*?=end'       # block comments
        r"|'(?:\\.|[^'\\])*'"   # single-quoted strings
        r'|"(?:\\.|[^"\\])*"',  # double-quoted strings
        re.DOTALL,
    ),
    # PHP
    'php': re.compile(
        r'//[^\n]*'             # single-line comments
        r'|#[^\n]*'             # hash comments
        r'|/\*.*?\*/'           # multi-line comments
        r"|'(?:\\.|[^'\\])*'"   # single-quoted strings
        r'|"(?:\\.|[^"\\])*"',  # double-quoted strings
        re.DOTALL,
    ),
    # ABAP — comments start with * in column 1 or " anywhere
    'abap': re.compile(
        r'^\*[^\n]*'            # full-line comment (starts with *)
        r'|"[^\n]*',            # inline comment (starts with ")
        re.MULTILINE,
    ),
}

# Map language strings to pattern keys
_LANG_TO_PATTERN = {
    'java': 'c_family', 'csharp': 'c_family', 'go': 'c_family',
    'javascript': 'c_family', 'typescript': 'c_family',
    'python': 'python',
    'ruby': 'ruby',
    'php': 'php',
    'abap': 'abap',
}


def _replace_keeping_newlines(match):
    """Replace match content with spaces, preserving newlines for line numbers."""
    text = match.group(0)
    return re.sub(r'[^\n]', ' ', text)


def strip_comments(content: str, language: str) -> str:
    """Strip comments and string literals from source code.

    Preserves line count by replacing stripped text with spaces/newlines.
    This prevents regex-based parsers from matching patterns inside
    comments or string literals.

    Args:
        content: Raw source code.
        language: Language key (e.g. 'java', 'csharp', 'javascript', 'ruby').

    Returns:
        Source with comments and strings replaced by whitespace.
    """
    pattern_key = _LANG_TO_PATTERN.get(language, 'c_family')
    pattern = _STRIP_PATTERNS.get(pattern_key)
    if not pattern:
        return content
    return pattern.sub(_replace_keeping_newlines, content)


# Characters that start a string literal (vs. a comment)
_STRING_STARTERS = frozenset({"'", '"', '`'})


def _replace_comments_keep_strings(match):
    """Replace comments with whitespace but preserve string literals intact."""
    text = match.group(0)
    if text[0] in _STRING_STARTERS:
        return text  # string literal — keep unchanged
    return re.sub(r'[^\n]', ' ', text)  # comment — blank out


def strip_comments_only(content: str, language: str) -> str:
    """Strip comments but preserve string literals.

    Uses the same regex patterns as strip_comments() but only replaces
    comment matches. String literal matches are returned unchanged.
    Character positions are preserved (comments replaced with whitespace).

    Use this when regex patterns need to capture values from string literals
    but must not match inside comments.

    Args:
        content: Raw source code.
        language: Language key (e.g. 'java', 'csharp', 'javascript', 'ruby').

    Returns:
        Source with comments replaced by whitespace, strings intact.
    """
    pattern_key = _LANG_TO_PATTERN.get(language, 'c_family')
    pattern = _STRIP_PATTERNS.get(pattern_key)
    if not pattern:
        return content
    return pattern.sub(_replace_comments_keep_strings, content)


# ---------------------------------------------------------------------------
# Brace-counting utility for class/block body extraction
# ---------------------------------------------------------------------------

def extract_block_body(content: str, start_pos: int) -> Tuple[str, int, int]:
    """Extract the body of a brace-delimited block starting from start_pos.

    Scans forward from start_pos to find the opening '{', then counts
    braces to find the matching closing '}'.

    Args:
        content: Full source text (should be comment-stripped).
        start_pos: Position to start scanning from.

    Returns:
        (body_text, body_start, body_end) — the text between braces and
        the absolute positions. Returns ('', -1, -1) if no block found.
    """
    depth = 0
    body_start = -1

    for i in range(start_pos, len(content)):
        ch = content[i]
        if ch == '{':
            if depth == 0:
                body_start = i + 1
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                return content[body_start:i], body_start, i
    return '', -1, -1


def line_number_at(content: str, pos: int) -> int:
    """Return the 1-based line number for a character position in content."""
    return content[:pos].count('\n') + 1


# ---------------------------------------------------------------------------
# Base parser classes
# ---------------------------------------------------------------------------

class BaseSchemaParser:
    """Base class for database schema parsers."""

    FILE_EXTENSIONS: List[str] = []

    def parse(self, project_path: str) -> Dict:
        """Parse project and return standardized schema dict.

        Subclasses must override this method.
        """
        raise NotImplementedError

    def find_files(self, project_path: str, extensions: List[str] = None) -> List[str]:
        """Find source files matching extensions."""
        return find_source_files(project_path, extensions or self.FILE_EXTENSIONS)

    def make_schema_result(self, tables: List[Dict],
                           relationships: List[Dict] = None) -> Dict:
        """Build a standardized schema result dict."""
        raw = (relationships if relationships is not None
               else self._detect_relationships(tables))
        return {
            'tables': tables,
            'relationships': [self._normalize_relationship(r) for r in raw],
        }

    @staticmethod
    def _normalize_relationship(rel: Dict) -> Dict:
        """Normalize relationship dict to the canonical frontend format.

        Canonical keys: from_table, to_table, from_column, to_column, type.
        Accepts both {'from'/'to'} and {'from_table'/'to_table'} inputs.
        """
        return {
            'from_table': rel.get('from_table') or rel.get('from', ''),
            'to_table': rel.get('to_table') or rel.get('to', ''),
            'from_column': rel.get('from_column', ''),
            'to_column': rel.get('to_column', ''),
            'type': rel.get('type', 'many-to-one'),
        }

    @staticmethod
    def _detect_relationships(tables: List[Dict]) -> List[Dict]:
        """Derive relationships from foreign keys across all tables."""
        relationships = []
        for table in tables:
            for fk in table.get('foreign_keys', []):
                relationships.append({
                    'from_table': table['name'],
                    'to_table': fk['references_table'],
                    'from_column': fk.get('column', ''),
                    'to_column': fk.get('references_column', ''),
                    'type': 'many-to-one',
                })
        return relationships


class BaseFlowParser:
    """Base class for runtime flow parsers."""

    FILE_EXTENSIONS: List[str] = []

    def __init__(self, project_path: str, options: Dict = None):
        self.project_path = Path(project_path)
        self.options = options or {}
        self.functions: List[Dict] = []
        self.calls: List[Dict] = []
        self.control_flows: List[Dict] = []
        self.modules: List[Dict] = []

    def parse(self) -> Dict:
        """Parse and return standardized runtime flow dict.

        Subclasses must override this method.
        """
        raise NotImplementedError

    def make_flow_result(self, entry_points: List[Dict] = None) -> Dict:
        """Build standardized flow result from collected data."""
        if entry_points is None:
            entry_points = self._detect_entry_points()
        return {
            'analysis_type': 'runtime_flow',
            'version': '1.0',
            'project_path': str(self.project_path),
            'modules': self.modules,
            'functions': self.functions,
            'calls': self.calls,
            'control_flows': self.control_flows,
            'entry_points': entry_points,
            'statistics': self._calculate_statistics(),
        }

    def _detect_entry_points(self) -> List[Dict]:
        """Identify entry points. Override in subclasses for language specifics."""
        return []

    def _resolve_calls(self):
        """Resolve function calls to their definitions."""
        func_by_name = {}
        for func in self.functions:
            func_by_name[func['name']] = func
            func_by_name[func.get('qualified_name', func['name'])] = func

        for call in self.calls:
            callee_name = call.get('callee_name', '')
            if callee_name in func_by_name:
                call['callee_id'] = func_by_name[callee_name]['id']
                call['call_type'] = 'direct'
            else:
                call['callee_id'] = f"external_{callee_name}"
                call['call_type'] = 'external'

    def _calculate_statistics(self) -> Dict:
        """Calculate statistics about the analyzed code."""
        called_ids = {c['callee_id'] for c in self.calls if c.get('call_type') == 'direct'}
        all_ids = {f['id'] for f in self.functions}
        orphans = list(all_ids - called_ids)

        return {
            'total_functions': len(self.functions),
            'total_calls': len(self.calls),
            'total_control_flows': len(self.control_flows),
            'max_call_depth': self._calculate_max_depth(),
            'circular_dependencies': self._detect_circular_dependencies(),
            'orphan_functions': orphans[:10],
        }

    def _detect_circular_dependencies(self) -> List[List[str]]:
        """Detect circular call dependencies using DFS."""
        graph: Dict[str, List[str]] = {}
        for call in self.calls:
            if call.get('call_type') == 'direct':
                graph.setdefault(call['caller_id'], []).append(call['callee_id'])

        visited: Set[str] = set()
        rec_stack: Set[str] = set()
        cycles: List[List[str]] = []

        def dfs(node, path):
            visited.add(node)
            rec_stack.add(node)
            path.append(node)
            for neighbor in graph.get(node, []):
                if neighbor not in visited:
                    dfs(neighbor, path[:])
                elif neighbor in rec_stack:
                    idx = path.index(neighbor)
                    cycle = path[idx:]
                    if cycle not in cycles and len(cycle) > 1:
                        cycles.append(cycle)
            rec_stack.discard(node)

        for node in graph:
            if node not in visited:
                dfs(node, [])

        return cycles[:5]

    def _calculate_max_depth(self) -> int:
        """Calculate maximum call depth."""
        graph: Dict[str, List[str]] = {}
        for call in self.calls:
            if call.get('call_type') == 'direct':
                graph.setdefault(call['caller_id'], []).append(call['callee_id'])

        def depth(node, seen):
            if node in seen or node not in graph:
                return 0
            seen.add(node)
            return 1 + max((depth(n, seen.copy()) for n in graph[node]), default=0)

        return max((depth(f['id'], set()) for f in self.functions), default=0)


class BaseRoutesParser:
    """Base class for API routes parsers."""

    FILE_EXTENSIONS: List[str] = []

    def __init__(self, project_path: str, options: Dict = None):
        self.project_path = Path(project_path)
        self.options = options or {}
        self.blueprints: List[Dict] = []   # route groups (blueprints, controllers, routers)
        self.routes: List[Dict] = []

    def parse(self) -> Dict:
        """Parse and return standardized API routes dict.

        Subclasses must override this method.
        """
        raise NotImplementedError

    def make_routes_result(self) -> Dict:
        """Build standardized routes result from collected data."""
        return {
            'analysis_type': 'api_routes',
            'version': '1.0',
            'project_path': str(self.project_path),
            'blueprints': self.blueprints,
            'routes': self.routes,
            'statistics': self._calculate_statistics(),
        }

    def _calculate_statistics(self) -> Dict:
        """Calculate statistics about the analyzed routes."""
        routes_by_method: Dict[str, int] = {}
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


class BaseStructureParser:
    """Base class for code structure parsers."""

    FILE_EXTENSIONS: List[str] = []

    def __init__(self, project_path: str, options: Dict = None):
        self.project_path = Path(project_path)
        self.options = options or {}
        self.modules: List[Dict] = []
        self.classes: List[Dict] = []
        self.imports: List[Dict] = []

    def parse(self) -> Dict:
        """Parse and return standardized code structure dict.

        Subclasses must override this method.
        """
        raise NotImplementedError

    def make_structure_result(self) -> Dict:
        """Build standardized structure result from collected data."""
        return {
            'analysis_type': 'code_structure',
            'version': '1.0',
            'project_path': str(self.project_path),
            'modules': self.modules,
            'classes': self.classes,
            'imports': self.imports,
            'relationships': self._build_relationships(),
            'statistics': self._calculate_statistics(),
        }

    def _build_relationships(self) -> List[Dict]:
        """Build inheritance and composition relationships from collected classes."""
        relationships = []
        class_names = {c['name'] for c in self.classes}
        class_by_name = {c['name']: c for c in self.classes}

        for cls in self.classes:
            for base in cls.get('base_classes', []):
                if base in class_by_name:
                    relationships.append({
                        'source_id': cls['id'],
                        'target_id': class_by_name[base]['id'],
                        'type': 'inheritance',
                        'label': 'extends',
                    })

            # Composition: type hints referencing other known classes
            for prop in cls.get('properties', []):
                type_name = prop.get('type') or ''
                for wrapper in ['Optional[', 'List[', 'Set[', 'Dict[', 'Tuple[']:
                    if type_name.startswith(wrapper):
                        type_name = type_name[len(wrapper):-1].split(',')[0].strip()
                if type_name in class_names and type_name != cls['name']:
                    relationships.append({
                        'source_id': cls['id'],
                        'target_id': class_by_name[type_name]['id'],
                        'type': 'composition',
                        'label': prop['name'],
                    })

        return relationships

    def _calculate_statistics(self) -> Dict:
        """Calculate statistics about the analyzed code structure."""
        total_methods = sum(len(c.get('methods', [])) for c in self.classes)
        total_properties = sum(len(c.get('properties', [])) for c in self.classes)
        abstract_classes = sum(1 for c in self.classes if c.get('is_abstract', False))
        classes_with_bases = sum(1 for c in self.classes if c.get('base_classes'))

        return {
            'total_modules': len(self.modules),
            'total_classes': len(self.classes),
            'total_methods': total_methods,
            'total_properties': total_properties,
            'abstract_classes': abstract_classes,
            'classes_with_inheritance': classes_with_bases,
            'total_imports': len(self.imports),
            'max_inheritance_depth': self._max_inheritance_depth(),
        }

    def _max_inheritance_depth(self) -> int:
        """Calculate the deepest inheritance chain."""
        class_by_name = {c['name']: c for c in self.classes}

        def depth(name, seen):
            if name not in class_by_name or name in seen:
                return 0
            seen.add(name)
            bases = class_by_name[name].get('base_classes', [])
            if not bases:
                return 0
            return 1 + max((depth(b, seen.copy()) for b in bases
                            if b in class_by_name), default=0)

        return max((depth(c['name'], set()) for c in self.classes), default=0)
