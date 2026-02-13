# Code Structure Visualization — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build the 4th and final visualization type — Code Structure — showing classes, modules, inheritance hierarchies, and import dependencies as an interactive graph.

**Architecture:** Python AST-based parser extracts classes/modules/relationships → stored as JSON in `analysis_results` → frontend transforms to React Flow nodes/edges with ClassNode and ModuleNode custom components → dagre layout → full workspace integration (sticky notes, layout save, detail modal, insight guide).

**Tech Stack:** Python AST (backend parser), Flask endpoints, React Flow + dagre (frontend), Tailwind CSS (styling), existing shared hooks/utilities.

---

## Task 1: BaseStructureParser — Add Base Class to `base.py`

**Files:**
- Modify: `backend/parsers/base.py` (append after `BaseRoutesParser` class, ~line 458)

**Step 1: Add `BaseStructureParser` class**

Add this class at the end of `base.py`, after `BaseRoutesParser`:

```python
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
                type_name = prop.get('type', '')
                # Strip Optional[], List[], etc. to get base type
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
            return 1 + max((depth(b, seen.copy()) for b in bases if b in class_by_name), default=0)

        return max((depth(c['name'], set()) for c in self.classes), default=0)
```

**Step 2: Commit**

```bash
git add backend/parsers/base.py
git commit -m "feat(structure): add BaseStructureParser base class"
```

---

## Task 2: Python Structure Parser

**Files:**
- Create: `backend/parsers/structure/__init__.py`
- Create: `backend/parsers/structure/python_structure_parser.py`

**Step 1: Create directory and `__init__.py`**

Create `backend/parsers/structure/__init__.py` — empty file.

**Step 2: Create `python_structure_parser.py`**

Uses Python `ast` module to extract:
- **Modules** — one per `.py` file with file path, class count
- **Classes** — name, base classes, methods (name, params, decorators, line, is_static, is_classmethod, is_property, is_abstract, docstring), properties (name, type annotation), decorators, docstring, is_abstract flag, line_number, end_line
- **Imports** — from/import statements per module

```python
"""
Python code structure parser.

Uses AST to extract classes, methods, properties, inheritance, and imports.
"""

import ast
import logging
from pathlib import Path
from typing import Dict, List

from ..base import BaseStructureParser, find_source_files, read_file_safe

logger = logging.getLogger(__name__)


class StructureVisitor(ast.NodeVisitor):
    """AST visitor that extracts class/module structure."""

    def __init__(self, filepath: str, module_name: str):
        self.filepath = filepath
        self.module_name = module_name
        self.classes: List[Dict] = []
        self.imports: List[Dict] = []
        self._class_counter = 0

    def visit_Import(self, node):
        for alias in node.names:
            self.imports.append({
                'module': self.module_name,
                'imported': alias.name,
                'alias': alias.asname,
                'line_number': node.lineno,
            })
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        source = node.module or ''
        for alias in node.names:
            self.imports.append({
                'module': self.module_name,
                'imported': f"{source}.{alias.name}" if source else alias.name,
                'alias': alias.asname,
                'line_number': node.lineno,
                'from_module': source,
            })
        self.generic_visit(node)

    def visit_ClassDef(self, node):
        self._class_counter += 1
        class_id = f"class_{self.module_name}_{node.name}_{self._class_counter}"

        # Base classes
        base_classes = []
        for base in node.bases:
            if isinstance(base, ast.Name):
                base_classes.append(base.id)
            elif isinstance(base, ast.Attribute):
                base_classes.append(ast.dump(base).replace("Attribute", "").replace("(", ".").replace(")", ""))
                # Simplified: just get the attribute name
                parts = []
                current = base
                while isinstance(current, ast.Attribute):
                    parts.append(current.attr)
                    current = current.value
                if isinstance(current, ast.Name):
                    parts.append(current.id)
                base_classes[-1] = '.'.join(reversed(parts))

        # Decorators
        decorators = []
        for dec in node.decorator_list:
            if isinstance(dec, ast.Name):
                decorators.append(dec.id)
            elif isinstance(dec, ast.Attribute):
                decorators.append(dec.attr)
            elif isinstance(dec, ast.Call):
                if isinstance(dec.func, ast.Name):
                    decorators.append(dec.func.id)
                elif isinstance(dec.func, ast.Attribute):
                    decorators.append(dec.func.attr)

        # Docstring
        docstring = ast.get_docstring(node) or ''

        # Is abstract?
        is_abstract = 'abstractmethod' in str(decorators) or 'ABC' in base_classes or 'ABCMeta' in base_classes

        # Methods and properties
        methods = []
        properties = []
        for item in node.body:
            if isinstance(item, ast.FunctionDef) or isinstance(item, ast.AsyncFunctionDef):
                method_info = self._extract_method(item)
                if method_info.get('is_property'):
                    properties.append({
                        'name': method_info['name'],
                        'type': method_info.get('return_type', ''),
                        'line_number': method_info['line_number'],
                    })
                else:
                    methods.append(method_info)
            elif isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                # Class-level annotated assignment: name: Type = value
                type_str = self._annotation_to_str(item.annotation) if item.annotation else ''
                properties.append({
                    'name': item.target.id,
                    'type': type_str,
                    'line_number': item.lineno,
                })
            elif isinstance(item, ast.Assign):
                # Class-level assignment: name = value
                for target in item.targets:
                    if isinstance(target, ast.Name):
                        properties.append({
                            'name': target.id,
                            'type': '',
                            'line_number': item.lineno,
                        })

        # Also scan __init__ for self.x assignments as properties
        init_props = self._extract_init_properties(node)
        existing_prop_names = {p['name'] for p in properties}
        for prop in init_props:
            if prop['name'] not in existing_prop_names:
                properties.append(prop)

        self.classes.append({
            'id': class_id,
            'name': node.name,
            'module': self.module_name,
            'file_path': self.filepath,
            'line_number': node.lineno,
            'end_line': node.end_lineno if hasattr(node, 'end_lineno') else node.lineno,
            'base_classes': base_classes,
            'decorators': decorators,
            'docstring': docstring,
            'is_abstract': is_abstract,
            'is_async': False,
            'methods': methods,
            'properties': properties,
        })

        # Don't visit nested classes as top-level
        # (but still visit the class body for nested classes)
        for item in node.body:
            if isinstance(item, ast.ClassDef):
                self.visit_ClassDef(item)

    def _extract_method(self, node) -> Dict:
        """Extract method information from a FunctionDef node."""
        # Parameters (skip 'self' and 'cls')
        params = []
        for arg in node.args.args:
            name = arg.arg
            if name in ('self', 'cls'):
                continue
            type_str = self._annotation_to_str(arg.annotation) if arg.annotation else ''
            params.append({'name': name, 'type': type_str})

        # Decorators
        decorators = []
        is_static = False
        is_classmethod = False
        is_property = False
        is_abstract = False

        for dec in node.decorator_list:
            dec_name = ''
            if isinstance(dec, ast.Name):
                dec_name = dec.id
            elif isinstance(dec, ast.Attribute):
                dec_name = dec.attr
            elif isinstance(dec, ast.Call):
                if isinstance(dec.func, ast.Name):
                    dec_name = dec.func.id
                elif isinstance(dec.func, ast.Attribute):
                    dec_name = dec.func.attr
            decorators.append(dec_name)

            if dec_name == 'staticmethod':
                is_static = True
            elif dec_name == 'classmethod':
                is_classmethod = True
            elif dec_name == 'property':
                is_property = True
            elif dec_name == 'abstractmethod':
                is_abstract = True

        # Return type
        return_type = self._annotation_to_str(node.returns) if node.returns else ''

        # Docstring
        docstring = ast.get_docstring(node) or ''

        # Visibility
        visibility = 'private' if node.name.startswith('_') and not node.name.startswith('__') else 'public'
        if node.name.startswith('__') and node.name.endswith('__'):
            visibility = 'dunder'

        return {
            'name': node.name,
            'parameters': params,
            'return_type': return_type,
            'decorators': decorators,
            'docstring': docstring,
            'line_number': node.lineno,
            'end_line': node.end_lineno if hasattr(node, 'end_lineno') else node.lineno,
            'is_static': is_static,
            'is_classmethod': is_classmethod,
            'is_property': is_property,
            'is_abstract': is_abstract,
            'is_async': isinstance(node, ast.AsyncFunctionDef),
            'visibility': visibility,
        }

    def _extract_init_properties(self, class_node) -> List[Dict]:
        """Extract properties from __init__ method (self.x = ... patterns)."""
        props = []
        for item in class_node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == '__init__':
                for stmt in ast.walk(item):
                    if isinstance(stmt, ast.Assign):
                        for target in stmt.targets:
                            if (isinstance(target, ast.Attribute) and
                                    isinstance(target.value, ast.Name) and
                                    target.value.id == 'self'):
                                props.append({
                                    'name': target.attr,
                                    'type': '',
                                    'line_number': stmt.lineno,
                                })
                    elif isinstance(stmt, ast.AnnAssign):
                        if (isinstance(stmt.target, ast.Attribute) and
                                isinstance(stmt.target.value, ast.Name) and
                                stmt.target.value.id == 'self'):
                            type_str = self._annotation_to_str(stmt.annotation) if stmt.annotation else ''
                            props.append({
                                'name': stmt.target.attr,
                                'type': type_str,
                                'line_number': stmt.lineno,
                            })
        return props

    @staticmethod
    def _annotation_to_str(annotation) -> str:
        """Convert an AST annotation node to a readable string."""
        if annotation is None:
            return ''
        try:
            return ast.unparse(annotation)
        except Exception:
            if isinstance(annotation, ast.Name):
                return annotation.id
            if isinstance(annotation, ast.Constant):
                return str(annotation.value)
            return ''


class PythonStructureParser(BaseStructureParser):
    """Parses Python source code to extract class/module structure."""

    FILE_EXTENSIONS = ['.py']

    def parse(self) -> Dict:
        python_files = find_source_files(str(self.project_path), self.FILE_EXTENSIONS)

        for filepath in python_files:
            self._parse_file(Path(filepath))

        return self.make_structure_result()

    def _parse_file(self, filepath: Path):
        """Parse a single Python file."""
        content = read_file_safe(str(filepath))
        if not content:
            return

        # Derive module name from path
        try:
            rel_path = filepath.relative_to(self.project_path)
        except ValueError:
            rel_path = filepath
        module_name = str(rel_path).replace('\\', '/').replace('/', '.').rstrip('.py')
        if module_name.endswith('.py'):
            module_name = module_name[:-3]

        try:
            tree = ast.parse(content, filename=str(filepath))
        except SyntaxError as e:
            logger.warning("Syntax error in %s: %s", filepath, e)
            return

        visitor = StructureVisitor(str(filepath), module_name)
        visitor.visit(tree)

        # Add module
        self.modules.append({
            'id': f"module_{module_name}",
            'name': module_name,
            'file_path': str(filepath),
            'class_count': len(visitor.classes),
            'import_count': len(visitor.imports),
        })

        self.classes.extend(visitor.classes)
        self.imports.extend(visitor.imports)
```

**Step 3: Commit**

```bash
git add backend/parsers/structure/
git commit -m "feat(structure): add Python structure parser with AST-based class extraction"
```

---

## Task 3: JS/TS Structure Parser

**Files:**
- Create: `backend/parsers/structure/js_structure_parser.py`

**Step 1: Create `js_structure_parser.py`**

Uses regex to extract:
- ES6 classes (`class Foo extends Bar`), methods, properties
- TypeScript interfaces and type aliases
- Import/export statements
- Module structure

```python
"""
JavaScript/TypeScript code structure parser.

Uses regex to extract classes, interfaces, methods, properties, and imports.
"""

import logging
import re
from pathlib import Path
from typing import Dict, List

from ..base import (BaseStructureParser, find_source_files, read_file_safe,
                    strip_comments, extract_block_body, line_number_at)

logger = logging.getLogger(__name__)

# Regex patterns
_CLASS_RE = re.compile(
    r'(?:export\s+)?(?:abstract\s+)?class\s+(\w+)'
    r'(?:\s+extends\s+([\w.]+))?'
    r'(?:\s+implements\s+([\w.,\s]+))?',
    re.MULTILINE,
)

_INTERFACE_RE = re.compile(
    r'(?:export\s+)?interface\s+(\w+)'
    r'(?:\s+extends\s+([\w.,\s]+))?',
    re.MULTILINE,
)

_METHOD_RE = re.compile(
    r'(?:(?:public|private|protected|static|async|abstract|readonly)\s+)*'
    r'(\w+)\s*'
    r'(?:<[^>]*>)?\s*'  # optional generics
    r'\(([^)]*)\)'
    r'(?:\s*:\s*([^\s{;]+))?',  # optional return type
    re.MULTILINE,
)

_PROPERTY_RE = re.compile(
    r'(?:(?:public|private|protected|static|readonly)\s+)*'
    r'(\w+)\s*[?!]?\s*:\s*([^;=]+)',
    re.MULTILINE,
)

_IMPORT_RE = re.compile(
    r"import\s+(?:(?:type\s+)?(?:\{[^}]*\}|[\w*]+(?:\s+as\s+\w+)?)"
    r"(?:\s*,\s*(?:\{[^}]*\}|[\w*]+))?\s+from\s+)?['\"]([^'\"]+)['\"]",
    re.MULTILINE,
)

_DECORATOR_RE = re.compile(r'@(\w+)(?:\([^)]*\))?', re.MULTILINE)


class JSStructureParser(BaseStructureParser):
    """Parses JavaScript/TypeScript source code to extract class/module structure."""

    FILE_EXTENSIONS = ['.js', '.ts', '.jsx', '.tsx']

    def parse(self) -> Dict:
        source_files = find_source_files(str(self.project_path), self.FILE_EXTENSIONS)

        for filepath in source_files:
            self._parse_file(Path(filepath))

        return self.make_structure_result()

    def _parse_file(self, filepath: Path):
        """Parse a single JS/TS file."""
        content = read_file_safe(str(filepath))
        if not content:
            return

        # Derive module name
        try:
            rel_path = filepath.relative_to(self.project_path)
        except ValueError:
            rel_path = filepath
        module_name = str(rel_path).replace('\\', '/')
        # Remove extension
        for ext in self.FILE_EXTENSIONS:
            if module_name.endswith(ext):
                module_name = module_name[:-len(ext)]
                break

        # Strip comments for regex matching
        stripped = strip_comments(content, 'javascript')

        classes_found = []

        # Extract classes
        for match in _CLASS_RE.finditer(stripped):
            class_name = match.group(1)
            extends = match.group(2)
            implements = match.group(3)

            base_classes = []
            if extends:
                base_classes.append(extends.strip())
            if implements:
                base_classes.extend([i.strip() for i in implements.split(',')])

            line_num = line_number_at(content, match.start())
            class_id = f"class_{module_name}_{class_name}"

            # Extract class body
            body, body_start, body_end = extract_block_body(stripped, match.start())

            methods, properties = self._extract_members(body, body_start, content)

            # Decorators (scan lines above class declaration)
            decorators = self._extract_decorators(stripped, match.start())

            is_abstract = 'abstract' in stripped[max(0, match.start() - 50):match.start()]

            classes_found.append({
                'id': class_id,
                'name': class_name,
                'module': module_name,
                'file_path': str(filepath),
                'line_number': line_num,
                'end_line': line_number_at(content, body_end) if body_end > 0 else line_num,
                'base_classes': base_classes,
                'decorators': decorators,
                'docstring': '',
                'is_abstract': is_abstract,
                'is_interface': False,
                'methods': methods,
                'properties': properties,
            })

        # Extract interfaces (TypeScript)
        for match in _INTERFACE_RE.finditer(stripped):
            iface_name = match.group(1)
            extends = match.group(2)

            base_classes = []
            if extends:
                base_classes.extend([i.strip() for i in extends.split(',')])

            line_num = line_number_at(content, match.start())
            iface_id = f"interface_{module_name}_{iface_name}"

            body, body_start, body_end = extract_block_body(stripped, match.start())
            methods, properties = self._extract_members(body, body_start, content)

            classes_found.append({
                'id': iface_id,
                'name': iface_name,
                'module': module_name,
                'file_path': str(filepath),
                'line_number': line_num,
                'end_line': line_number_at(content, body_end) if body_end > 0 else line_num,
                'base_classes': base_classes,
                'decorators': [],
                'docstring': '',
                'is_abstract': False,
                'is_interface': True,
                'methods': methods,
                'properties': properties,
            })

        # Extract imports
        for match in _IMPORT_RE.finditer(stripped):
            self.imports.append({
                'module': module_name,
                'imported': match.group(1),
                'alias': None,
                'line_number': line_number_at(content, match.start()),
            })

        # Add module
        self.modules.append({
            'id': f"module_{module_name}",
            'name': module_name,
            'file_path': str(filepath),
            'class_count': len(classes_found),
            'import_count': len([i for i in self.imports if i['module'] == module_name]),
        })

        self.classes.extend(classes_found)

    def _extract_members(self, body: str, body_start: int, original: str):
        """Extract methods and properties from a class/interface body."""
        methods = []
        properties = []

        if not body:
            return methods, properties

        # Methods
        for match in _METHOD_RE.finditer(body):
            name = match.group(1)
            # Skip common non-method keywords
            if name in ('if', 'else', 'for', 'while', 'switch', 'return',
                        'const', 'let', 'var', 'new', 'throw', 'import', 'export'):
                continue
            params_str = match.group(2)
            return_type = match.group(3) or ''

            params = []
            if params_str.strip():
                for p in params_str.split(','):
                    p = p.strip()
                    if ':' in p:
                        pname, ptype = p.split(':', 1)
                        params.append({'name': pname.strip().rstrip('?'), 'type': ptype.strip()})
                    elif p:
                        params.append({'name': p.rstrip('?'), 'type': ''})

            prefix = body[max(0, match.start() - 80):match.start()]
            is_static = 'static' in prefix.split('\n')[-1] if '\n' in prefix else 'static' in prefix
            is_async = 'async' in prefix.split('\n')[-1] if '\n' in prefix else 'async' in prefix
            is_abstract = 'abstract' in prefix.split('\n')[-1] if '\n' in prefix else 'abstract' in prefix

            visibility = 'public'
            if 'private' in prefix:
                visibility = 'private'
            elif 'protected' in prefix:
                visibility = 'protected'

            line_num = line_number_at(original, body_start + match.start()) if body_start >= 0 else 0

            methods.append({
                'name': name,
                'parameters': params,
                'return_type': return_type,
                'decorators': [],
                'docstring': '',
                'line_number': line_num,
                'is_static': is_static,
                'is_async': is_async,
                'is_abstract': is_abstract,
                'visibility': visibility,
            })

        # Properties (only those not already found as methods)
        method_names = {m['name'] for m in methods}
        for match in _PROPERTY_RE.finditer(body):
            name = match.group(1)
            if name in method_names or name in ('if', 'else', 'return', 'const', 'let', 'var'):
                continue
            type_str = match.group(2).strip().rstrip(';')
            line_num = line_number_at(original, body_start + match.start()) if body_start >= 0 else 0
            properties.append({
                'name': name,
                'type': type_str,
                'line_number': line_num,
            })

        return methods, properties

    @staticmethod
    def _extract_decorators(content: str, class_start: int) -> List[str]:
        """Extract decorator names from lines above class/interface declaration."""
        decorators = []
        # Look backwards from class_start for @Decorator patterns
        prefix = content[max(0, class_start - 500):class_start]
        lines = prefix.split('\n')
        for line in reversed(lines):
            stripped = line.strip()
            if stripped.startswith('@'):
                match = _DECORATOR_RE.match(stripped)
                if match:
                    decorators.append(match.group(1))
            elif stripped and not stripped.startswith('//'):
                break  # Stop at first non-decorator, non-empty line
        return list(reversed(decorators))
```

**Step 2: Commit**

```bash
git add backend/parsers/structure/js_structure_parser.py
git commit -m "feat(structure): add JS/TS structure parser with regex-based class extraction"
```

---

## Task 4: Parser Manager — Add Code Structure Routing

**Files:**
- Modify: `backend/parsers/parser_manager.py` (add after `_get_routes_parser` method, ~line 288)

**Step 1: Add `parse_code_structure` and `_get_structure_parser` methods**

Add after the API routes parsing section (after line 288):

```python
    # -----------------------------------------------------------------------
    # Code structure parsing
    # -----------------------------------------------------------------------

    def parse_code_structure(self, project_path: str, options: Dict = None) -> Dict:
        """Parse source code to extract class/module structure.

        Detects language and routes to appropriate structure parser.
        """
        parser = self._get_structure_parser(project_path, options)
        if parser:
            return parser.parse()

        raise UnsupportedFrameworkError(
            "No supported source files found for code structure analysis. "
            "Supported: Python (.py), JavaScript/TypeScript (.js/.ts/.jsx/.tsx)")

    def _get_structure_parser(self, project_path: str, options: Dict = None):
        """Return the appropriate structure parser for the project."""
        if self._has_python_files(project_path):
            from .structure.python_structure_parser import PythonStructureParser
            return PythonStructureParser(project_path, options)
        if find_source_files(project_path, ['.js', '.ts', '.jsx', '.tsx']):
            from .structure.js_structure_parser import JSStructureParser
            return JSStructureParser(project_path, options)
        return None
```

**Step 2: Commit**

```bash
git add backend/parsers/parser_manager.py
git commit -m "feat(structure): add code structure routing to ParserManager"
```

---

## Task 5: Backend Endpoints — Workspace-Scoped Code Structure

**Files:**
- Modify: `backend/routes/workspace_routes.py` (add after the `analyze_workspace_api_routes` function)

**Step 1: Add GET endpoint for retrieving code structure data**

Add after the existing API routes endpoints (after `analyze_workspace_api_routes`):

```python
@workspaces_bp.route('/<int:project_id>/workspaces/<int:workspace_id>/code-structure', methods=['GET'])
@jwt_required()
def get_workspace_code_structure(project_id, workspace_id):
    """Get code structure analysis for a specific workspace."""
    user_id = int(get_jwt_identity())

    with get_connection() as conn:
        cur = conn.cursor()

        if not verify_project_ownership(cur, project_id, user_id):
            return jsonify({'error': 'Project not found'}), 404

        cur.execute(
            '''SELECT * FROM analysis_results
               WHERE workspace_id = %s AND analysis_type = %s
               ORDER BY created_at DESC LIMIT 1''',
            (workspace_id, 'code_structure')
        )
        analysis_data = cur.fetchone()

    if not analysis_data:
        return jsonify({'error': 'No code structure analysis found'}), 404

    try:
        parsed_result = json.loads(analysis_data['result_data'])
    except (json.JSONDecodeError, TypeError) as e:
        logger.error('Corrupt code structure data for workspace %s: %s', workspace_id, e)
        return jsonify({'error': 'Stored analysis data is corrupted. Try re-running the analysis.'}), 500

    return jsonify({
        'analysis_id': analysis_data['id'],
        'structure': parsed_result,
        'created_at': analysis_data['created_at']
    }), 200
```

**Step 2: Add POST endpoint for running code structure analysis**

```python
@workspaces_bp.route('/<int:project_id>/workspaces/<int:workspace_id>/analyze/code-structure', methods=['POST'])
@jwt_required()
def analyze_workspace_code_structure(project_id, workspace_id):
    """Run code structure analysis on workspace files."""
    user_id = int(get_jwt_identity())

    with get_connection() as conn:
        cur = conn.cursor()

        project = verify_project_ownership(cur, project_id, user_id)
        if not project:
            return jsonify({'error': 'Project not found'}), 404

        if not verify_workspace(cur, workspace_id, project_id):
            return jsonify({'error': 'Workspace not found'}), 404

        ws_dir = get_workspace_file_dir(user_id, project_id, workspace_id)

        cur.execute(
            'SELECT COUNT(*) as count FROM workspace_files WHERE workspace_id = %s',
            (workspace_id,)
        )
        file_count = cur.fetchone()['count']

        if file_count == 0 or not os.path.exists(ws_dir):
            return jsonify({
                'error': 'No files in this workspace. Upload files first before analyzing.'
            }), 400

        try:
            manager = ParserManager()
            structure_data = manager.parse_code_structure(ws_dir)

            cur.execute(
                'DELETE FROM analysis_results WHERE workspace_id = %s AND analysis_type = %s',
                (workspace_id, 'code_structure')
            )

            cur.execute(
                '''INSERT INTO analysis_results (project_id, analysis_type, result_data, workspace_id)
                   VALUES (%s, %s, %s, %s)''',
                (project_id, 'code_structure', json.dumps(structure_data), workspace_id)
            )

            conn.commit()

            return jsonify({
                'message': 'Code structure analysis completed',
                'structure': structure_data
            }), 200

        except UnsupportedFrameworkError as e:
            conn.rollback()
            return jsonify({'error': str(e)}), 400
        except Exception as e:
            conn.rollback()
            logger.exception('Code structure analysis failed for workspace %s', workspace_id)
            return jsonify({'error': 'Code structure analysis failed. Please try again or contact support.'}), 500
```

**Step 3: Commit**

```bash
git add backend/routes/workspace_routes.py
git commit -m "feat(structure): add workspace-scoped code structure endpoints"
```

---

## Task 6: Frontend API Service — Add Code Structure Methods

**Files:**
- Modify: `frontend/src/services/api.js`

**Step 1: Add methods to `workspacesAPI`**

Add to the `workspacesAPI` object (before the closing `};`):

```javascript
  getCodeStructure: (projectId, workspaceId) =>
    api.get(`/projects/${projectId}/workspaces/${workspaceId}/code-structure`),
  analyzeCodeStructure: (projectId, workspaceId) =>
    api.post(`/projects/${projectId}/workspaces/${workspaceId}/analyze/code-structure`),
```

**Step 2: Commit**

```bash
git add frontend/src/services/api.js
git commit -m "feat(structure): add code structure API methods"
```

---

## Task 7: Transform Utility — `codeStructureTransform.js`

**Files:**
- Create: `frontend/src/utils/codeStructureTransform.js`

**Step 1: Create the transform utility**

Converts backend code structure data to React Flow nodes and edges:

```javascript
/**
 * Transform code structure data from API into React Flow nodes and edges.
 */

/**
 * Transform backend structure data into React Flow format.
 */
export const transformCodeStructureData = (structureData) => {
  if (!structureData) {
    return { nodes: [], edges: [] };
  }

  const nodes = [];
  const edges = [];
  const { modules = [], classes = [], relationships = [] } = structureData;

  // Create module nodes (only if they contain classes)
  const modulesWithClasses = modules.filter(m => m.class_count > 0);
  modulesWithClasses.forEach((mod) => {
    nodes.push({
      id: mod.id,
      type: 'moduleNode',
      data: {
        name: mod.name,
        file_path: mod.file_path,
        class_count: mod.class_count,
        import_count: mod.import_count,
      },
      position: { x: 0, y: 0 },
    });
  });

  // Create class nodes
  classes.forEach((cls) => {
    const methodCount = (cls.methods || []).length;
    const propertyCount = (cls.properties || []).length;
    const visibleMethods = (cls.methods || [])
      .filter(m => m.visibility !== 'dunder')
      .slice(0, 6);

    nodes.push({
      id: cls.id,
      type: 'classNode',
      data: {
        name: cls.name,
        module: cls.module,
        file_path: cls.file_path,
        line_number: cls.line_number,
        base_classes: cls.base_classes || [],
        decorators: cls.decorators || [],
        docstring: cls.docstring || '',
        is_abstract: cls.is_abstract || false,
        is_interface: cls.is_interface || false,
        methods: cls.methods || [],
        properties: cls.properties || [],
        visibleMethods,
        methodCount,
        propertyCount,
      },
      position: { x: 0, y: 0 },
    });

    // Edge from module to class
    const moduleId = `module_${cls.module}`;
    const moduleExists = modulesWithClasses.some(m => m.id === moduleId);
    if (moduleExists) {
      edges.push({
        id: `module-edge-${cls.id}`,
        source: moduleId,
        target: cls.id,
        type: 'smoothstep',
        style: { stroke: '#6b7280', strokeWidth: 1.5 },
        animated: false,
      });
    }
  });

  // Create edges from relationships (inheritance, composition)
  relationships.forEach((rel, index) => {
    const isInheritance = rel.type === 'inheritance';
    edges.push({
      id: `rel-${index}`,
      source: rel.source_id,
      target: rel.target_id,
      label: rel.label || rel.type,
      type: 'smoothstep',
      animated: isInheritance,
      style: {
        stroke: isInheritance ? '#8b5cf6' : '#f59e0b',
        strokeWidth: isInheritance ? 2 : 1.5,
        strokeDasharray: isInheritance ? undefined : '5,5',
      },
      labelStyle: {
        fontSize: '11px',
        fontWeight: 500,
        fill: '#ffffff',
      },
      labelBgStyle: {
        fill: isInheritance ? '#8b5cf6' : '#f59e0b',
        fillOpacity: 0.9,
      },
      labelBgPadding: [6, 3],
      labelBgBorderRadius: 3,
    });
  });

  return { nodes, edges };
};

/**
 * Estimate node height for dagre layout.
 */
export const estimateStructureNodeHeight = (node) => {
  if (node.type === 'moduleNode') {
    return 70;
  }

  if (node.type === 'classNode') {
    const data = node.data || {};
    let height = 60; // header
    const visibleMethods = data.visibleMethods || [];
    const propertyCount = data.propertyCount || 0;

    if (data.base_classes?.length > 0) height += 24;
    if (propertyCount > 0) height += 20 + Math.min(propertyCount, 4) * 18;
    if (visibleMethods.length > 0) height += 20 + visibleMethods.length * 20;
    if ((data.methodCount || 0) > visibleMethods.length) height += 18; // "and N more"

    return Math.max(height, 100);
  }

  return 80;
};

/**
 * Get node width for dagre layout.
 */
export const getStructureNodeWidth = (node) => {
  if (node.type === 'moduleNode') return 200;
  if (node.type === 'classNode') return 260;
  return 220;
};
```

**Step 2: Commit**

```bash
git add frontend/src/utils/codeStructureTransform.js
git commit -m "feat(structure): add code structure transform utility"
```

---

## Task 8: ClassNode Custom Component

**Files:**
- Create: `frontend/src/components/project/nodes/ClassNode.jsx`

**Step 1: Create `ClassNode.jsx`**

Renders a class/interface as a card showing name, badges, base classes, properties preview, and methods preview:

```jsx
import React, { memo } from 'react';
import { Handle, Position } from 'reactflow';

const visibilityIcon = (v) => {
  if (v === 'private') return '−';
  if (v === 'protected') return '#';
  return '+';
};

const ClassNode = memo(({ data }) => {
  const {
    name, base_classes = [], is_abstract, is_interface,
    visibleMethods = [], methodCount = 0, propertyCount = 0,
    properties = [], decorators = [],
  } = data;

  const visibleProps = properties.slice(0, 4);
  const hiddenMethodCount = methodCount - visibleMethods.length;

  return (
    <div className="bg-white dark:bg-gray-800 border-2 border-indigo-400 dark:border-indigo-500 rounded-lg shadow-md min-w-[220px] max-w-[280px] text-left">
      <Handle type="target" position={Position.Top} className="!bg-indigo-400" />

      {/* Header */}
      <div className="bg-indigo-50 dark:bg-indigo-900/30 px-3 py-2 rounded-t-md border-b border-indigo-200 dark:border-indigo-700">
        <div className="flex items-center gap-1.5 flex-wrap">
          {is_interface && (
            <span className="px-1.5 py-0.5 text-[10px] font-bold bg-cyan-100 dark:bg-cyan-900 text-cyan-700 dark:text-cyan-300 rounded">
              interface
            </span>
          )}
          {is_abstract && (
            <span className="px-1.5 py-0.5 text-[10px] font-bold bg-amber-100 dark:bg-amber-900 text-amber-700 dark:text-amber-300 rounded italic">
              abstract
            </span>
          )}
          {decorators.length > 0 && (
            <span className="px-1.5 py-0.5 text-[10px] font-medium bg-purple-100 dark:bg-purple-900 text-purple-700 dark:text-purple-300 rounded">
              @{decorators[0]}
            </span>
          )}
        </div>
        <div className="font-bold text-sm text-gray-900 dark:text-gray-100 mt-1 truncate" title={name}>
          {name}
        </div>
        {base_classes.length > 0 && (
          <div className="text-[10px] text-indigo-600 dark:text-indigo-400 mt-0.5 truncate" title={base_classes.join(', ')}>
            extends {base_classes.join(', ')}
          </div>
        )}
      </div>

      {/* Properties section */}
      {visibleProps.length > 0 && (
        <div className="px-3 py-1.5 border-b border-gray-100 dark:border-gray-700">
          <div className="text-[10px] font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-1">
            Properties ({propertyCount})
          </div>
          {visibleProps.map((prop, idx) => (
            <div key={idx} className="text-[11px] text-gray-700 dark:text-gray-300 truncate leading-[18px]" title={`${prop.name}: ${prop.type}`}>
              {prop.name}
              {prop.type && <span className="text-gray-400 dark:text-gray-500">: {prop.type}</span>}
            </div>
          ))}
          {propertyCount > 4 && (
            <div className="text-[10px] text-gray-400 dark:text-gray-500 italic">
              +{propertyCount - 4} more
            </div>
          )}
        </div>
      )}

      {/* Methods section */}
      {visibleMethods.length > 0 && (
        <div className="px-3 py-1.5">
          <div className="text-[10px] font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-1">
            Methods ({methodCount})
          </div>
          {visibleMethods.map((method, idx) => (
            <div key={idx} className="text-[11px] text-gray-700 dark:text-gray-300 truncate leading-[20px] flex items-center gap-1">
              <span className="text-gray-400 dark:text-gray-500 font-mono text-[10px] w-3">
                {visibilityIcon(method.visibility)}
              </span>
              <span className={method.is_static ? 'underline' : ''}>
                {method.name}
              </span>
              <span className="text-gray-400 dark:text-gray-500">()</span>
              {method.is_async && (
                <span className="text-[9px] text-blue-500 dark:text-blue-400 font-medium">async</span>
              )}
              {method.is_abstract && (
                <span className="text-[9px] text-amber-500 dark:text-amber-400 font-medium italic">abs</span>
              )}
            </div>
          ))}
          {hiddenMethodCount > 0 && (
            <div className="text-[10px] text-gray-400 dark:text-gray-500 italic mt-0.5">
              +{hiddenMethodCount} more
            </div>
          )}
        </div>
      )}

      {/* Empty state */}
      {visibleMethods.length === 0 && visibleProps.length === 0 && (
        <div className="px-3 py-2 text-[11px] text-gray-400 dark:text-gray-500 italic">
          Empty class
        </div>
      )}

      <Handle type="source" position={Position.Bottom} className="!bg-indigo-400" />
    </div>
  );
});

ClassNode.displayName = 'ClassNode';
export default ClassNode;
```

**Step 2: Commit**

```bash
git add frontend/src/components/project/nodes/ClassNode.jsx
git commit -m "feat(structure): add ClassNode custom React Flow component"
```

---

## Task 9: ModuleNode Custom Component

**Files:**
- Create: `frontend/src/components/project/nodes/ModuleNode.jsx`

**Step 1: Create `ModuleNode.jsx`**

Compact container node showing module/file name and class count:

```jsx
import React, { memo } from 'react';
import { Handle, Position } from 'reactflow';

const ModuleNode = memo(({ data }) => {
  const { name, class_count = 0, import_count = 0 } = data;

  // Shorten module name to last 2 segments for readability
  const parts = name.split(/[./]/);
  const shortName = parts.length > 2 ? '.../' + parts.slice(-2).join('/') : name;

  return (
    <div className="bg-slate-100 dark:bg-slate-800 border-2 border-slate-400 dark:border-slate-500 rounded-lg shadow-sm min-w-[180px] max-w-[220px] text-left">
      <Handle type="target" position={Position.Top} className="!bg-slate-400" />

      <div className="px-3 py-2">
        <div className="flex items-center gap-1.5 mb-1">
          <svg className="w-3.5 h-3.5 text-slate-500 dark:text-slate-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
          <span className="font-semibold text-xs text-gray-800 dark:text-gray-200 truncate" title={name}>
            {shortName}
          </span>
        </div>
        <div className="flex gap-3 text-[10px] text-gray-500 dark:text-gray-400">
          <span>{class_count} class{class_count !== 1 ? 'es' : ''}</span>
          {import_count > 0 && <span>{import_count} imports</span>}
        </div>
      </div>

      <Handle type="source" position={Position.Bottom} className="!bg-slate-400" />
    </div>
  );
});

ModuleNode.displayName = 'ModuleNode';
export default ModuleNode;
```

**Step 2: Commit**

```bash
git add frontend/src/components/project/nodes/ModuleNode.jsx
git commit -m "feat(structure): add ModuleNode custom React Flow component"
```

---

## Task 10: CodeStructureVisualization Component

**Files:**
- Create: `frontend/src/components/project/CodeStructureVisualization.jsx`

**Step 1: Create the main visualization component**

Follow the exact pattern of `FlowVisualization.jsx` — dagre layout, sticky notes, edge highlighting, detail modal, insight guide, statistics overlay:

```jsx
import React, { useState, useEffect, useMemo, useCallback } from 'react';
import ReactFlow, {
  MiniMap,
  Controls,
  Background,
  useNodesState,
  useEdgesState,
} from 'reactflow';
import 'reactflow/dist/style.css';
import dagre from 'dagre';

import ClassNode from './nodes/ClassNode';
import ModuleNode from './nodes/ModuleNode';
import StickyNote from './StickyNote';
import { StickyNoteButton, ThemeToggleButton } from './ToolbarButtons';
import CodeStructureInsightGuide from './CodeStructureInsightGuide';
import NodeDetailModal from './NodeDetailModal';
import { transformCodeStructureData, estimateStructureNodeHeight, getStructureNodeWidth } from '../../utils/codeStructureTransform';
import { applySavedLayout } from '../../utils/layoutUtils';
import { useStickyNotes, restoreStickyNotesFromLayout } from '../../hooks/useStickyNotes';
import { useEdgeHighlighting } from '../../hooks/useEdgeHighlighting';

const nodeTypes = {
  classNode: ClassNode,
  moduleNode: ModuleNode,
  stickyNote: StickyNote,
};

const getLayoutedStructureElements = (nodes, edges, direction = 'TB') => {
  const stickyNotes = nodes.filter(n => n.type === 'stickyNote');
  const structureNodes = nodes.filter(n => n.type !== 'stickyNote');

  const dagreGraph = new dagre.graphlib.Graph();
  dagreGraph.setDefaultEdgeLabel(() => ({}));

  dagreGraph.setGraph({
    rankdir: direction,
    nodesep: 140,
    ranksep: 180,
    marginx: 50,
    marginy: 50,
  });

  structureNodes.forEach((node) => {
    const width = getStructureNodeWidth(node);
    const height = estimateStructureNodeHeight(node);
    dagreGraph.setNode(node.id, { width, height });
  });

  edges.forEach((edge) => {
    dagreGraph.setEdge(edge.source, edge.target);
  });

  dagre.layout(dagreGraph);

  const layoutedNodes = structureNodes.map((node) => {
    const nodeWithPosition = dagreGraph.node(node.id);
    const width = getStructureNodeWidth(node);
    const height = estimateStructureNodeHeight(node);

    return {
      ...node,
      position: {
        x: nodeWithPosition.x - width / 2,
        y: nodeWithPosition.y - height / 2,
      },
    };
  });

  return { nodes: [...layoutedNodes, ...stickyNotes], edges };
};

export default function CodeStructureVisualization({ structureData, isDark, onToggleTheme, layoutTrigger, projectId, savedLayout, onNodesUpdate, onNodesDragged }) {
  const [nodes, setNodes, onNodesChangeBase] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [initialNodes, setInitialNodes] = useState([]);
  const [initialEdges, setInitialEdges] = useState([]);
  const [showInsightGuide, setShowInsightGuide] = useState(false);
  const [detailNode, setDetailNode] = useState(null);
  const handleDetailClose = useCallback(() => setDetailNode(null), []);

  const onNodesChange = useCallback((changes) => {
    onNodesChangeBase(changes);
    const hasDragEnd = changes.some(c => c.type === 'position' && c.dragging === false);
    if (hasDragEnd && onNodesDragged) onNodesDragged();
  }, [onNodesChangeBase, onNodesDragged]);

  useEffect(() => {
    if (onNodesUpdate) onNodesUpdate(nodes);
  }, [nodes, onNodesUpdate]);

  const { handleNoteTextChange, handleNoteColorChange, handleDeleteNote, handleAddNote } =
    useStickyNotes(setNodes, onNodesDragged);

  const {
    highlightedNodes,
    highlightedEdges,
    onNodeMouseEnter,
    onNodeMouseLeave,
    onEdgeMouseEnter,
    onEdgeMouseLeave,
  } = useEdgeHighlighting(nodes, edges);

  useEffect(() => {
    if (structureData) {
      const { nodes: structureNodes, edges: structureEdges } = transformCodeStructureData(structureData);

      if (structureNodes.length > 0) {
        const { nodes: layoutedNodes, edges: layoutedEdges } = getLayoutedStructureElements(
          structureNodes,
          structureEdges
        );

        const finalNodes = applySavedLayout(layoutedNodes, savedLayout);

        const stickyNotes = restoreStickyNotesFromLayout(savedLayout, {
          onTextChange: handleNoteTextChange,
          onColorChange: handleNoteColorChange,
          onDelete: handleDeleteNote,
        });

        setNodes([...finalNodes, ...stickyNotes]);
        setEdges(layoutedEdges);
        setInitialNodes(structureNodes);
        setInitialEdges(structureEdges);
      }
    }
  }, [structureData, savedLayout, setNodes, setEdges, handleNoteTextChange, handleNoteColorChange, handleDeleteNote]);

  useEffect(() => {
    if (layoutTrigger > 0 && initialNodes.length > 0) {
      const { nodes: layoutedNodes, edges: layoutedEdges } = getLayoutedStructureElements(
        initialNodes,
        initialEdges
      );
      setNodes((currentNodes) => {
        const existingStickyNotes = currentNodes.filter(n => n.type === 'stickyNote');
        return [...layoutedNodes, ...existingStickyNotes];
      });
      setEdges(layoutedEdges);
    }
  }, [layoutTrigger, initialNodes, initialEdges, setNodes, setEdges]);

  const handleNodeDoubleClick = useCallback((event, node) => {
    if (node.type === 'stickyNote') return;
    setDetailNode(node);
  }, []);

  const statistics = structureData?.statistics ?? null;

  if (!structureData || nodes.length === 0) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center">
          <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2"
              d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
          </svg>
          <h3 className="mt-2 text-sm font-medium text-gray-900 dark:text-gray-100">
            No code structure data
          </h3>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
            Click "Analyze Code Structure" to generate the visualization
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="w-full h-full relative">
      <ReactFlow
        nodes={highlightedNodes}
        edges={highlightedEdges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeMouseEnter={onNodeMouseEnter}
        onNodeMouseLeave={onNodeMouseLeave}
        onEdgeMouseEnter={onEdgeMouseEnter}
        onEdgeMouseLeave={onEdgeMouseLeave}
        onNodeDoubleClick={handleNodeDoubleClick}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.2, maxZoom: 1 }}
        minZoom={0.1}
        maxZoom={2}
        defaultEdgeOptions={{
          type: 'smoothstep',
        }}
        className={isDark ? 'dark' : ''}
      >
        <Background
          color={isDark ? '#374151' : '#e5e7eb'}
          gap={16}
          size={1}
        />

        <Controls
          showInteractive={false}
          className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden"
        >
          <StickyNoteButton onAddNote={handleAddNote} />
          <ThemeToggleButton isDark={isDark} onToggle={onToggleTheme} />
        </Controls>

        <MiniMap
          nodeColor={(node) => {
            if (node.type === 'stickyNote') return '#fbbf24';
            if (node.type === 'moduleNode') return '#64748b';
            if (node.type === 'classNode') {
              if (node.data?.is_interface) return '#06b6d4';
              if (node.data?.is_abstract) return '#f59e0b';
              return '#6366f1';
            }
            return '#6b7280';
          }}
          className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg"
          maskColor={isDark ? 'rgb(17, 24, 39, 0.6)' : 'rgb(243, 244, 246, 0.6)'}
        />

        {/* Decode This button */}
        <div className="absolute top-4 left-4 z-10">
          <button
            onClick={() => setShowInsightGuide(true)}
            className="bg-purple-600 hover:bg-purple-700 dark:bg-purple-500 dark:hover:bg-purple-600 text-white px-4 py-2 rounded-lg shadow-lg transition-all duration-200 flex items-center gap-2 font-medium text-sm"
            title="Learn about this visualization"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2"
                d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            Decode This
          </button>
        </div>

        {/* Statistics overlay */}
        {statistics && (
          <div className="absolute top-4 right-4 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg shadow-lg p-4 min-w-[200px]">
            <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-3">
              Structure Statistics
            </h3>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-gray-600 dark:text-gray-400">Modules:</span>
                <span className="font-medium text-gray-900 dark:text-gray-100">
                  {statistics.total_modules}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600 dark:text-gray-400">Classes:</span>
                <span className="font-medium text-gray-900 dark:text-gray-100">
                  {statistics.total_classes}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600 dark:text-gray-400">Methods:</span>
                <span className="font-medium text-gray-900 dark:text-gray-100">
                  {statistics.total_methods}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600 dark:text-gray-400">Properties:</span>
                <span className="font-medium text-gray-900 dark:text-gray-100">
                  {statistics.total_properties}
                </span>
              </div>
              {statistics.classes_with_inheritance > 0 && (
                <div className="flex justify-between">
                  <span className="text-gray-600 dark:text-gray-400">Inheritance:</span>
                  <span className="font-medium text-indigo-600 dark:text-indigo-400">
                    {statistics.classes_with_inheritance} chains
                  </span>
                </div>
              )}
              {statistics.max_inheritance_depth > 0 && (
                <div className="flex justify-between">
                  <span className="text-gray-600 dark:text-gray-400">Max Depth:</span>
                  <span className="font-medium text-gray-900 dark:text-gray-100">
                    {statistics.max_inheritance_depth}
                  </span>
                </div>
              )}
            </div>
          </div>
        )}
      </ReactFlow>

      <CodeStructureInsightGuide
        isOpen={showInsightGuide}
        onClose={() => setShowInsightGuide(false)}
        isDark={isDark}
        structureData={structureData}
        projectId={projectId}
      />

      <NodeDetailModal
        isOpen={!!detailNode}
        onClose={handleDetailClose}
        isDark={isDark}
        node={detailNode}
        edges={edges}
        contextData={{ structure: structureData }}
      />
    </div>
  );
}
```

**Step 2: Commit**

```bash
git add frontend/src/components/project/CodeStructureVisualization.jsx
git commit -m "feat(structure): add CodeStructureVisualization main component"
```

---

## Task 11: CodeStructureInsightGuide

**Files:**
- Create: `frontend/src/components/project/CodeStructureInsightGuide.jsx`

Follow the exact pattern of `ApiRoutesInsightGuide.jsx` — modal shell with guide tab and analyze tab.

Guide content should explain:
- What Code Structure visualization shows (classes, modules, inheritance)
- How to read the graph (class nodes, module nodes, edges)
- Badges explained (abstract, interface, visibility)
- Statistics explained
- OOP best practices (SOLID principles, composition over inheritance)

The Analyze tab calls `POST /projects/${projectId}/analyze-code-structure` for AI-powered analysis.

**Step 1: Create the component (same pattern as `ApiRoutesInsightGuide.jsx`)**

**Step 2: Commit**

```bash
git add frontend/src/components/project/CodeStructureInsightGuide.jsx
git commit -m "feat(structure): add CodeStructureInsightGuide modal"
```

---

## Task 12: Node Detail Renderers — ClassNodeDetail and ModuleNodeDetail

**Files:**
- Create: `frontend/src/components/project/nodeDetails/ClassNodeDetail.jsx`
- Create: `frontend/src/components/project/nodeDetails/ModuleNodeDetail.jsx`
- Modify: `frontend/src/components/project/NodeDetailModal.jsx` — add dispatch for `classNode` and `moduleNode`

### ClassNodeDetail

Shows full class info: identity (module, file, line), all decorators, docstring, base classes with links, full properties table, full methods table (name, params, return type, visibility, decorators), subclasses (from edges), parent classes (from edges).

Looks up full class record from `contextData.structure.classes.find(c => c.id === node.id)`.

### ModuleNodeDetail

Shows module info: file path, class count, import count. Lists all classes in this module from `contextData.structure.classes.filter(c => c.module === moduleData.name)`.

### NodeDetailModal dispatch additions

Add to the dispatch logic:
```javascript
import ClassNodeDetail from './nodeDetails/ClassNodeDetail';
import ModuleNodeDetail from './nodeDetails/ModuleNodeDetail';

// In the dispatch:
} else if (nodeType === 'classNode') {
  DetailComponent = ClassNodeDetail;
  icon = node.data?.is_interface ? '📐' : '📦';
  title = node.data?.name || 'Class';
  subtitle = node.data?.module || '';
} else if (nodeType === 'moduleNode') {
  DetailComponent = ModuleNodeDetail;
  icon = '📄';
  title = node.data?.name || 'Module';
  subtitle = '';
}
```

**Step 1: Create both detail components and update NodeDetailModal dispatch**

**Step 2: Commit**

```bash
git add frontend/src/components/project/nodeDetails/ClassNodeDetail.jsx
git add frontend/src/components/project/nodeDetails/ModuleNodeDetail.jsx
git add frontend/src/components/project/NodeDetailModal.jsx
git commit -m "feat(structure): add ClassNodeDetail and ModuleNodeDetail renderers"
```

---

## Task 13: Wire Into ProjectVisualization.jsx

**Files:**
- Modify: `frontend/src/components/project/ProjectVisualization.jsx`

**Changes needed:**

1. **Import** `CodeStructureVisualization` at top
2. **Add state variables:**
   ```javascript
   const [codeStructureData, setCodeStructureData] = useState(null);
   const [isAnalyzingStructure, setIsAnalyzingStructure] = useState(false);
   const [structureLoading, setStructureLoading] = useState(false);
   const [structureLayoutTrigger, setStructureLayoutTrigger] = useState(0);
   const structureNodesRef = useRef([]);
   const handleStructureNodesUpdate = useCallback((n) => { structureNodesRef.current = n; }, []);
   ```
3. **Update `viewToAnalysisType`** — add `structure: 'code_structure'`
4. **Update `analysisTypeToView`** — add `code_structure: 'structure'`
5. **Add `loadCodeStructureData`** handler (same pattern as `loadRuntimeFlowData`)
6. **Add `handleAnalyzeCodeStructure`** handler (same pattern as `handleAnalyzeRuntimeFlow`)
7. **Update `useEffect` for view switching** — add `activeView === 'structure'` case
8. **Update `isWorkspaceEmpty`** — add structure case
9. **Update `handleWorkspaceSelect`** — clear `codeStructureData` on workspace switch
10. **Update `handleWorkspaceCreate`** — clear `codeStructureData`
11. **Update `handleWorkspaceDelete`** — clear `codeStructureData`
12. **Update `handleWorkspaceClearData`** — clear `codeStructureData`
13. **Update `handleQuickOrganize`** — add structure case using `structureLayoutTrigger`
14. **Update `handleSaveLayout`** — add structure case using `structureNodesRef`
15. **Update `handleUploadComplete`** — add structure case calling `handleAnalyzeCodeStructure`
16. **Update header** — add "Analyze Code Structure" button for `activeView === 'structure'`
17. **Update layout controls condition** — add `activeView === 'structure' && codeStructureData`
18. **Add rendering block** — `activeView === 'structure'` with `CenterUploadArea` or `CodeStructureVisualization`
19. **Remove "Coming Soon" fallback** since structure is now implemented

**Step 1: Apply all changes to ProjectVisualization.jsx**

**Step 2: Commit**

```bash
git add frontend/src/components/project/ProjectVisualization.jsx
git commit -m "feat(structure): wire CodeStructureVisualization into ProjectVisualization"
```

---

## Task 14: Enable Sidebar Navigation

**Files:**
- Modify: `frontend/src/components/project/Sidebar.jsx` (line 48)

**Step 1: Change `disabled: true` to `disabled: false`**

```javascript
// Line 48: change
disabled: true,
// to
disabled: false,
```

**Step 2: Commit**

```bash
git add frontend/src/components/project/Sidebar.jsx
git commit -m "feat(structure): enable Code Structure in sidebar navigation"
```

---

## Task 15: Test Fixtures

**Files:**
- Create: `backend/tests/fixtures/python_structure/models.py`
- Create: `backend/tests/fixtures/python_structure/services.py`
- Create: `backend/tests/fixtures/python_structure/utils.py`

Create sample Python files with:
- Base class with abstract methods
- Child classes with inheritance
- Properties (annotated and __init__)
- Static methods, class methods, async methods
- Decorators
- Docstrings
- Import statements

**Step 1: Create test fixture files**

**Step 2: Commit**

```bash
git add backend/tests/fixtures/python_structure/
git commit -m "test(structure): add Python structure test fixtures"
```

---

## Task 16: End-to-End Verification

**Steps:**

1. Start backend: `cd backend && python app.py`
2. Start frontend: `cd frontend && npm start`
3. Navigate to a project workspace
4. Click "Code Structure" in the sidebar — verify it's no longer disabled
5. Create a new workspace under Code Structure
6. Upload Python files (or import from GitHub)
7. Click "Analyze Code Structure" — verify analysis runs and visualization appears
8. Verify:
   - ClassNode and ModuleNode render correctly
   - Inheritance edges show with purple color
   - Module-to-class edges show with gray color
   - Statistics overlay shows correct counts
   - "Decode This" button opens CodeStructureInsightGuide
   - Double-click a class node → NodeDetailModal with ClassNodeDetail
   - Double-click a module node → NodeDetailModal with ModuleNodeDetail
   - Sticky notes work (add, edit, color, delete)
   - Quick Organize re-layouts correctly
   - Save Layout persists and restores on reload
   - Dark mode works correctly
   - Edge highlighting on hover works

**Step 1: Run verification**

**Step 2: Fix any issues found**

**Step 3: Final commit**

```bash
git add -A
git commit -m "feat(structure): complete Code Structure visualization — 4th visualization type"
```

---

## Key Files Summary

| File | Action | Purpose |
|------|--------|---------|
| `backend/parsers/base.py` | Modify | Add `BaseStructureParser` class |
| `backend/parsers/structure/__init__.py` | Create | Package init |
| `backend/parsers/structure/python_structure_parser.py` | Create | Python AST-based structure parser |
| `backend/parsers/structure/js_structure_parser.py` | Create | JS/TS regex-based structure parser |
| `backend/parsers/parser_manager.py` | Modify | Add `parse_code_structure()` routing |
| `backend/routes/workspace_routes.py` | Modify | Add GET/POST code-structure endpoints |
| `frontend/src/services/api.js` | Modify | Add `getCodeStructure`, `analyzeCodeStructure` |
| `frontend/src/utils/codeStructureTransform.js` | Create | Backend data → React Flow nodes/edges |
| `frontend/src/components/project/nodes/ClassNode.jsx` | Create | Class/interface card node |
| `frontend/src/components/project/nodes/ModuleNode.jsx` | Create | Module/file container node |
| `frontend/src/components/project/CodeStructureVisualization.jsx` | Create | Main visualization with dagre layout |
| `frontend/src/components/project/CodeStructureInsightGuide.jsx` | Create | Educational guide + AI analysis modal |
| `frontend/src/components/project/nodeDetails/ClassNodeDetail.jsx` | Create | Detail modal for class nodes |
| `frontend/src/components/project/nodeDetails/ModuleNodeDetail.jsx` | Create | Detail modal for module nodes |
| `frontend/src/components/project/NodeDetailModal.jsx` | Modify | Add classNode/moduleNode dispatch |
| `frontend/src/components/project/ProjectVisualization.jsx` | Modify | Wire in structure view + state + handlers |
| `frontend/src/components/project/Sidebar.jsx` | Modify | Enable Code Structure nav item |
| `backend/tests/fixtures/python_structure/` | Create | Test fixture files |

---

## Estimated Scope

- **Backend:** ~600 lines across 3 new files + 2 modified files
- **Frontend:** ~900 lines across 7 new files + 3 modified files
- **No database changes** — `analysis_results.analysis_type` already accepts `'code_structure'`
- **No new dependencies** — uses `ast` (stdlib), existing dagre/reactflow/tailwind
