"""
Python code structure parser using the AST module.

Extracts classes, methods, properties, imports, and module-level information
from Python source files to build a structural representation of a codebase.
"""

import ast
import logging
import os

from ..base import BaseStructureParser, find_source_files, read_file_safe

logger = logging.getLogger(__name__)


class StructureVisitor(ast.NodeVisitor):
    """AST visitor that collects structural information from Python source files.

    Extracts classes (with methods, properties, decorators, base classes),
    imports, and module-level metadata.
    """

    def __init__(self, module_name, file_path):
        self.module_name = module_name
        self.file_path = file_path
        self.classes = []
        self.imports = []
        self._class_counter = 0

    # ------------------------------------------------------------------
    # Imports
    # ------------------------------------------------------------------

    def visit_Import(self, node):
        """Handle ``import x, y as z`` statements."""
        for alias in node.names:
            self.imports.append({
                "module": alias.name,
                "name": alias.name,
                "alias": alias.asname,
                "line_number": node.lineno,
                "from_module": None,
            })
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        """Handle ``from x import y`` statements."""
        from_module = node.module or ""
        for alias in node.names:
            self.imports.append({
                "module": from_module,
                "name": alias.name,
                "alias": alias.asname,
                "line_number": node.lineno,
                "from_module": from_module,
            })
        self.generic_visit(node)

    # ------------------------------------------------------------------
    # Classes
    # ------------------------------------------------------------------

    def visit_ClassDef(self, node):
        """Extract full class information including methods and properties."""
        self._class_counter += 1

        class_name = node.name
        class_id = f"class_{self.module_name}_{class_name}_{self._class_counter}"

        base_classes = [self._resolve_base_class(b) for b in node.bases]
        decorators = [self._resolve_decorator(d) for d in node.decorator_list]
        docstring = ast.get_docstring(node)

        is_abstract = (
            any(d in ("abstractmethod", "abc.abstractmethod") for d in decorators)
            or any(b in ("ABC", "ABCMeta", "abc.ABC", "abc.ABCMeta") for b in base_classes)
        )

        methods = []
        properties = []

        for child in node.body:
            # --- Methods / functions ---
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                method_info = self._extract_method(child)
                methods.append(method_info)

                # If the method is __init__, also harvest self.x assignments
                if child.name == "__init__":
                    properties.extend(self._extract_init_properties(child))

            # --- Annotated assignments at class level (e.g. name: str) ---
            elif isinstance(child, ast.AnnAssign):
                prop = self._extract_annotated_property(child)
                if prop is not None:
                    properties.append(prop)

            # --- Plain assignments at class level (e.g. x = 5) ---
            elif isinstance(child, ast.Assign):
                for target in child.targets:
                    if isinstance(target, ast.Name):
                        properties.append({
                            "name": target.id,
                            "type": None,
                            "line_number": child.lineno,
                        })

        self.classes.append({
            "id": class_id,
            "name": class_name,
            "module": self.module_name,
            "file_path": self.file_path,
            "line_number": node.lineno,
            "end_line": node.end_lineno,
            "base_classes": base_classes,
            "decorators": decorators,
            "docstring": docstring,
            "is_abstract": is_abstract,
            "methods": methods,
            "properties": properties,
        })

        # Do NOT call generic_visit — we handle children manually above and
        # nested classes would be collected as top-level otherwise.

    # ------------------------------------------------------------------
    # Methods
    # ------------------------------------------------------------------

    def _extract_method(self, node):
        """Build a method descriptor from a FunctionDef / AsyncFunctionDef."""
        decorators = [self._resolve_decorator(d) for d in node.decorator_list]
        docstring = ast.get_docstring(node)

        is_static = "staticmethod" in decorators
        is_classmethod = "classmethod" in decorators
        is_property = "property" in decorators
        is_abstract = any(
            d in ("abstractmethod", "abc.abstractmethod") for d in decorators
        )
        is_async = isinstance(node, ast.AsyncFunctionDef)

        # Visibility
        name = node.name
        if name.startswith("__") and name.endswith("__"):
            visibility = "dunder"
        elif name.startswith("_"):
            visibility = "private"
        else:
            visibility = "public"

        parameters = self._extract_parameters(node.args)
        return_type = self._unparse_annotation(node.returns)

        return {
            "name": name,
            "parameters": parameters,
            "return_type": return_type,
            "decorators": decorators,
            "docstring": docstring,
            "line_number": node.lineno,
            "end_line": node.end_lineno,
            "is_static": is_static,
            "is_classmethod": is_classmethod,
            "is_property": is_property,
            "is_abstract": is_abstract,
            "is_async": is_async,
            "visibility": visibility,
        }

    def _extract_parameters(self, args_node):
        """Return a list of parameter dicts from an ``ast.arguments`` node."""
        params = []

        # Combine all positional args (posonlyargs + args)
        all_positional = list(args_node.posonlyargs) + list(args_node.args)

        for arg in all_positional:
            params.append({
                "name": arg.arg,
                "type": self._unparse_annotation(arg.annotation),
            })

        if args_node.vararg:
            params.append({
                "name": f"*{args_node.vararg.arg}",
                "type": self._unparse_annotation(args_node.vararg.annotation),
            })

        for arg in args_node.kwonlyargs:
            params.append({
                "name": arg.arg,
                "type": self._unparse_annotation(arg.annotation),
            })

        if args_node.kwarg:
            params.append({
                "name": f"**{args_node.kwarg.arg}",
                "type": self._unparse_annotation(args_node.kwarg.annotation),
            })

        return params

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    def _extract_annotated_property(self, node):
        """Extract a property from a class-level ``ast.AnnAssign``."""
        if isinstance(node.target, ast.Name):
            return {
                "name": node.target.id,
                "type": self._unparse_annotation(node.annotation),
                "line_number": node.lineno,
            }
        return None

    def _extract_init_properties(self, func_node):
        """Harvest ``self.x = ...`` assignments from an ``__init__`` body."""
        properties = []
        for child in ast.walk(func_node):
            if not isinstance(child, ast.Assign):
                continue
            for target in child.targets:
                if (
                    isinstance(target, ast.Attribute)
                    and isinstance(target.value, ast.Name)
                    and target.value.id == "self"
                ):
                    properties.append({
                        "name": target.attr,
                        "type": None,
                        "line_number": child.lineno,
                    })
        return properties

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_base_class(node):
        """Return a string representation of a base-class node."""
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            parts = []
            current = node
            while isinstance(current, ast.Attribute):
                parts.append(current.attr)
                current = current.value
            if isinstance(current, ast.Name):
                parts.append(current.id)
            return ".".join(reversed(parts))
        try:
            return ast.unparse(node)
        except Exception:
            return "<unknown>"

    @staticmethod
    def _resolve_decorator(node):
        """Return the string name of a decorator."""
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            parts = []
            current = node
            while isinstance(current, ast.Attribute):
                parts.append(current.attr)
                current = current.value
            if isinstance(current, ast.Name):
                parts.append(current.id)
            return ".".join(reversed(parts))
        if isinstance(node, ast.Call):
            return StructureVisitor._resolve_decorator(node.func)
        try:
            return ast.unparse(node)
        except Exception:
            return "<unknown>"

    @staticmethod
    def _unparse_annotation(node):
        """Safely convert an annotation AST node to its string form."""
        if node is None:
            return None
        try:
            return ast.unparse(node)
        except Exception:
            return None


class PythonStructureParser(BaseStructureParser):
    """Structure parser for Python source files.

    Uses the built-in ``ast`` module to extract classes, methods, properties,
    and import information from every ``.py`` file discovered under the
    configured project path.
    """

    FILE_EXTENSIONS = [".py"]

    def parse(self):
        """Find all Python files in the project and parse each one.

        Returns:
            dict: The combined structure result produced by
            ``self.make_structure_result()``.
        """
        source_files = find_source_files(self.project_path, self.FILE_EXTENSIONS)

        for filepath in source_files:
            try:
                self._parse_file(filepath)
            except SyntaxError:
                logger.warning("Syntax error in %s — skipping file", filepath)
            except Exception:
                logger.warning(
                    "Unexpected error parsing %s — skipping file",
                    filepath,
                    exc_info=True,
                )

        return self.make_structure_result()

    def _parse_file(self, filepath):
        """Parse a single Python file and extend internal collections.

        Args:
            filepath: Absolute path to the ``.py`` file.
        """
        source = read_file_safe(filepath)
        if source is None:
            return

        # Derive a dotted module name from the file path relative to the
        # project root.  e.g.  ``backend/parsers/foo.py`` -> ``backend.parsers.foo``
        rel_path = os.path.relpath(filepath, self.project_path)
        module_name = (
            rel_path
            .replace(os.sep, ".")
            .replace("/", ".")
            .removesuffix(".py")
        )

        tree = ast.parse(source, filename=filepath)

        # Build a module entry
        module_id = f"module_{module_name}"
        docstring = ast.get_docstring(tree)

        self.modules.append({
            "id": module_id,
            "name": module_name,
            "file_path": filepath,
            "docstring": docstring,
        })

        # Visit the tree to collect classes and imports
        visitor = StructureVisitor(module_name, filepath)
        visitor.visit(tree)

        self.classes.extend(visitor.classes)
        self.imports.extend(visitor.imports)
