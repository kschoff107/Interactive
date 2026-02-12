"""
Runtime Flow Parser - Extract function definitions, calls, and control flow from Python code.

Uses Python's AST module for static code analysis without executing code.
"""

import ast
import os
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple


class FlowVisitor(ast.NodeVisitor):
    """AST visitor to extract runtime flow information from Python code."""

    def __init__(self, filepath: str, module_name: str):
        self.filepath = filepath
        self.module_name = module_name
        self.functions = []
        self.calls = []
        self.control_flows = []
        self.imports = {}  # module_name -> imported_items
        self.current_function = None
        self.current_class = None
        self.control_flow_stack = []  # Track nested control structures

    def visit_Import(self, node: ast.Import):
        """Handle import statements: import module"""
        for alias in node.names:
            module_name = alias.name
            as_name = alias.asname or alias.name
            self.imports[as_name] = {'module': module_name, 'items': ['*']}
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        """Handle from...import statements: from module import item"""
        if node.module:
            items = [alias.name for alias in node.names]
            self.imports[node.module] = {'module': node.module, 'items': items}
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef):
        """Handle class definitions (for tracking methods)."""
        old_class = self.current_class
        self.current_class = node.name
        self.generic_visit(node)
        self.current_class = old_class

    def visit_FunctionDef(self, node: ast.FunctionDef):
        """Handle regular function definitions."""
        self._process_function(node, is_async=False)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        """Handle async function definitions."""
        self._process_function(node, is_async=True)

    def _process_function(self, node, is_async: bool):
        """Process a function definition node."""
        # Extract function metadata
        func_name = node.name
        line_number = node.lineno
        end_line = node.end_lineno or line_number

        # Extract parameters
        params = [arg.arg for arg in node.args.args]

        # Extract decorators
        decorators = []
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Name):
                decorators.append(f"@{decorator.id}")
            elif isinstance(decorator, ast.Attribute):
                decorators.append(f"@{ast.unparse(decorator)}")
            elif isinstance(decorator, ast.Call):
                if isinstance(decorator.func, ast.Name):
                    decorators.append(f"@{decorator.func.id}")
                elif isinstance(decorator.func, ast.Attribute):
                    decorators.append(f"@{ast.unparse(decorator.func)}")

        # Extract docstring
        docstring = ast.get_docstring(node)

        # Calculate cyclomatic complexity (basic)
        complexity = self._calculate_complexity(node)

        # Generate unique ID
        func_id = f"func_{self.module_name}_{func_name}_{line_number}"

        # Create function record
        function_data = {
            'id': func_id,
            'type': 'function',
            'name': func_name,
            'qualified_name': f"{self.module_name}.{func_name}",
            'module': self.module_name,
            'file_path': self.filepath,
            'line_number': line_number,
            'end_line': end_line,
            'parameters': params,
            'decorators': decorators,
            'is_async': is_async,
            'is_method': self.current_class is not None,
            'class_name': self.current_class,
            'docstring': docstring,
            'complexity': complexity
        }

        self.functions.append(function_data)

        # Set current function context for processing calls within it
        old_function = self.current_function
        self.current_function = func_id

        # Visit function body to extract calls and control flow
        self.generic_visit(node)

        # Restore previous function context
        self.current_function = old_function

    def visit_Call(self, node: ast.Call):
        """Handle function call expressions."""
        if self.current_function:  # Only track calls inside functions
            # Extract call information
            callee_name = self._get_call_name(node.func)

            if callee_name:
                call_id = f"call_{self.current_function}_to_{callee_name}_{node.lineno}"

                # Determine if call is conditional or in a loop
                is_conditional = any(cf['flow_type'] in ['if_else', 'try_except']
                                    for cf in self.control_flow_stack)
                is_loop = any(cf['flow_type'] in ['for_loop', 'while_loop']
                             for cf in self.control_flow_stack)

                call_data = {
                    'id': call_id,
                    'type': 'call',
                    'caller_id': self.current_function,
                    'callee_name': callee_name,
                    'file_path': self.filepath,
                    'line_number': node.lineno,
                    'is_conditional': is_conditional,
                    'is_loop': is_loop
                }

                self.calls.append(call_data)

        self.generic_visit(node)

    def visit_If(self, node: ast.If):
        """Handle if/else structures."""
        if self.current_function:
            ctrl_id = f"ctrl_if_else_{self.module_name}_{node.lineno}"

            # Extract condition as string
            condition = ast.unparse(node.test) if hasattr(ast, 'unparse') else '<condition>'

            # Determine branches
            branches = ['if']
            if node.orelse:
                if len(node.orelse) == 1 and isinstance(node.orelse[0], ast.If):
                    branches.append('elif')
                else:
                    branches.append('else')

            control_flow = {
                'id': ctrl_id,
                'type': 'control_flow',
                'flow_type': 'if_else',
                'parent_function_id': self.current_function,
                'file_path': self.filepath,
                'line_number': node.lineno,
                'end_line': node.end_lineno or node.lineno,
                'condition': condition,
                'branches': branches
            }

            self.control_flows.append(control_flow)
            self.control_flow_stack.append(control_flow)

        self.generic_visit(node)

        if self.current_function and self.control_flow_stack:
            self.control_flow_stack.pop()

    def visit_For(self, node: ast.For):
        """Handle for loops."""
        if self.current_function:
            ctrl_id = f"ctrl_for_loop_{self.module_name}_{node.lineno}"

            # Extract loop variable and iterable
            target = ast.unparse(node.target) if hasattr(ast, 'unparse') else 'item'
            iter_expr = ast.unparse(node.iter) if hasattr(ast, 'unparse') else 'items'
            condition = f"for {target} in {iter_expr}"

            control_flow = {
                'id': ctrl_id,
                'type': 'control_flow',
                'flow_type': 'for_loop',
                'parent_function_id': self.current_function,
                'file_path': self.filepath,
                'line_number': node.lineno,
                'end_line': node.end_lineno or node.lineno,
                'condition': condition,
                'branches': ['body']
            }

            self.control_flows.append(control_flow)
            self.control_flow_stack.append(control_flow)

        self.generic_visit(node)

        if self.current_function and self.control_flow_stack:
            self.control_flow_stack.pop()

    def visit_While(self, node: ast.While):
        """Handle while loops."""
        if self.current_function:
            ctrl_id = f"ctrl_while_loop_{self.module_name}_{node.lineno}"

            condition = ast.unparse(node.test) if hasattr(ast, 'unparse') else '<condition>'

            control_flow = {
                'id': ctrl_id,
                'type': 'control_flow',
                'flow_type': 'while_loop',
                'parent_function_id': self.current_function,
                'file_path': self.filepath,
                'line_number': node.lineno,
                'end_line': node.end_lineno or node.lineno,
                'condition': f"while {condition}",
                'branches': ['body']
            }

            self.control_flows.append(control_flow)
            self.control_flow_stack.append(control_flow)

        self.generic_visit(node)

        if self.current_function and self.control_flow_stack:
            self.control_flow_stack.pop()

    def visit_Try(self, node: ast.Try):
        """Handle try/except structures."""
        if self.current_function:
            ctrl_id = f"ctrl_try_except_{self.module_name}_{node.lineno}"

            # Extract exception types
            exception_types = []
            for handler in node.handlers:
                if handler.type:
                    exc_type = ast.unparse(handler.type) if hasattr(ast, 'unparse') else 'Exception'
                    exception_types.append(exc_type)

            branches = ['try'] + [f'except {t}' for t in exception_types]
            if node.orelse:
                branches.append('else')
            if node.finalbody:
                branches.append('finally')

            control_flow = {
                'id': ctrl_id,
                'type': 'control_flow',
                'flow_type': 'try_except',
                'parent_function_id': self.current_function,
                'file_path': self.filepath,
                'line_number': node.lineno,
                'end_line': node.end_lineno or node.lineno,
                'condition': f"try/except {', '.join(exception_types) if exception_types else ''}",
                'branches': branches
            }

            self.control_flows.append(control_flow)
            self.control_flow_stack.append(control_flow)

        self.generic_visit(node)

        if self.current_function and self.control_flow_stack:
            self.control_flow_stack.pop()

    def _get_call_name(self, node) -> Optional[str]:
        """Extract function name from a Call node."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            # Method call like obj.method()
            return ast.unparse(node) if hasattr(ast, 'unparse') else node.attr
        elif isinstance(node, ast.Call):
            # Nested call
            return self._get_call_name(node.func)
        return None

    def _calculate_complexity(self, node) -> int:
        """Calculate cyclomatic complexity of a function."""
        complexity = 1  # Base complexity

        for child in ast.walk(node):
            # Add 1 for each decision point
            if isinstance(child, (ast.If, ast.For, ast.While, ast.ExceptHandler)):
                complexity += 1
            elif isinstance(child, ast.BoolOp):
                # Add for boolean operators (and, or)
                complexity += len(child.values) - 1

        return complexity


class RuntimeFlowParser:
    """Parse Python source code to extract runtime flow information."""

    def __init__(self, project_path: str, options: Optional[Dict] = None):
        """
        Initialize parser with project directory.

        Args:
            project_path: Root directory of Python project
            options: Configuration options (entry_points, max_depth, etc.)
        """
        self.project_path = Path(project_path)
        self.options = options or {}
        self.functions = []
        self.calls = []
        self.control_flows = []
        self.modules = []
        self.all_imports = {}

    def parse(self) -> Dict:
        """
        Main parsing method - orchestrates the analysis.

        Returns:
            {
                'functions': [...],
                'calls': [...],
                'control_flows': [...],
                'modules': [...],
                'entry_points': [...],
                'statistics': {...}
            }
        """
        # Find all Python files
        python_files = self._find_python_files()

        # Parse each file
        for filepath in python_files:
            self._parse_file(filepath)

        # Resolve function calls
        self._resolve_calls()

        # Detect entry points
        entry_points = self._detect_entry_points()

        # Calculate statistics
        statistics = self._calculate_statistics()

        return {
            'analysis_type': 'runtime_flow',
            'version': '1.0',
            'project_path': str(self.project_path),
            'modules': self.modules,
            'functions': self.functions,
            'calls': self.calls,
            'control_flows': self.control_flows,
            'entry_points': entry_points,
            'statistics': statistics
        }

    def _find_python_files(self) -> List[Path]:
        """Find all Python files in the project directory."""
        python_files = []

        # Walk through project directory
        for root, dirs, files in os.walk(self.project_path):
            # Skip common non-source directories
            dirs[:] = [d for d in dirs if d not in [
                '__pycache__', '.git', '.venv', 'venv', 'node_modules',
                '.pytest_cache', '.tox', 'dist', 'build', '.eggs'
            ]]

            for file in files:
                if file.endswith('.py'):
                    filepath = Path(root) / file
                    python_files.append(filepath)

        return python_files

    def _parse_file(self, filepath: Path):
        """Parse a single Python file."""
        try:
            # Read file content
            with open(filepath, 'r', encoding='utf-8') as f:
                source = f.read()

            # Parse AST
            tree = ast.parse(source, filename=str(filepath))

            # Generate module name
            rel_path = filepath.relative_to(self.project_path)
            module_name = str(rel_path.with_suffix('')).replace(os.sep, '.')

            # Create visitor and extract information
            visitor = FlowVisitor(str(filepath), module_name)
            visitor.visit(tree)

            # Collect results
            self.functions.extend(visitor.functions)
            self.calls.extend(visitor.calls)
            self.control_flows.extend(visitor.control_flows)
            self.all_imports.update(visitor.imports)

            # Track module
            self.modules.append({
                'id': f"module_{module_name}",
                'name': module_name,
                'file_path': str(filepath),
                'function_count': len(visitor.functions)
            })

        except SyntaxError as e:
            print(f"Syntax error in {filepath}: {e}")
        except Exception as e:
            print(f"Error parsing {filepath}: {e}")

    def _resolve_calls(self):
        """Resolve function calls to their definitions."""
        # Create function lookup by name
        func_by_name = {}
        for func in self.functions:
            func_by_name[func['name']] = func
            func_by_name[func['qualified_name']] = func

        # Resolve each call
        for call in self.calls:
            callee_name = call['callee_name']

            # Try to find the called function
            if callee_name in func_by_name:
                call['callee_id'] = func_by_name[callee_name]['id']
                call['call_type'] = 'direct'
            else:
                # Mark as external or unresolved
                call['callee_id'] = f"external_{callee_name}"
                call['call_type'] = 'external'

    def _detect_entry_points(self) -> List[Dict]:
        """Identify entry points (main blocks, Flask routes, etc.)."""
        entry_points = []

        for func in self.functions:
            # Check for Flask/FastAPI route decorators
            for decorator in func.get('decorators', []):
                if 'route' in decorator.lower() or 'get' in decorator.lower() or 'post' in decorator.lower():
                    entry_points.append({
                        'id': f"entry_{func['id']}",
                        'type': 'route',
                        'function_id': func['id'],
                        'decorator': decorator,
                        'file_path': func['file_path'],
                        'line_number': func['line_number']
                    })
                    break

            # Check for main function
            if func['name'] == 'main':
                entry_points.append({
                    'id': f"entry_{func['id']}",
                    'type': 'main_function',
                    'function_id': func['id'],
                    'file_path': func['file_path'],
                    'line_number': func['line_number']
                })

        return entry_points

    def _calculate_statistics(self) -> Dict:
        """Calculate statistics about the analyzed code."""
        # Find circular dependencies (simplified check)
        circular_deps = self._detect_circular_dependencies()

        # Find orphan functions (never called)
        called_func_ids = {call['callee_id'] for call in self.calls if call['call_type'] == 'direct'}
        all_func_ids = {func['id'] for func in self.functions}
        orphan_funcs = list(all_func_ids - called_func_ids)

        # Calculate max call depth (simplified)
        max_depth = self._calculate_max_depth()

        return {
            'total_functions': len(self.functions),
            'total_calls': len(self.calls),
            'total_control_flows': len(self.control_flows),
            'max_call_depth': max_depth,
            'circular_dependencies': circular_deps,
            'orphan_functions': orphan_funcs[:10]  # Limit to first 10
        }

    def _detect_circular_dependencies(self) -> List[List[str]]:
        """Detect circular call dependencies using DFS."""
        # Build adjacency list
        graph = {}
        for call in self.calls:
            if call['call_type'] == 'direct':
                caller = call['caller_id']
                callee = call['callee_id']
                if caller not in graph:
                    graph[caller] = []
                graph[caller].append(callee)

        visited = set()
        rec_stack = set()
        cycles = []

        def dfs(node, path):
            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            for neighbor in graph.get(node, []):
                if neighbor not in visited:
                    dfs(neighbor, path[:])
                elif neighbor in rec_stack:
                    # Found cycle
                    cycle_start = path.index(neighbor)
                    cycle = path[cycle_start:]
                    if cycle not in cycles and len(cycle) > 1:
                        cycles.append(cycle)

            rec_stack.discard(node)

        for node in graph:
            if node not in visited:
                dfs(node, [])

        return cycles[:5]  # Limit to first 5 cycles

    def _calculate_max_depth(self) -> int:
        """Calculate maximum call depth from entry points."""
        # Build adjacency list
        graph = {}
        for call in self.calls:
            if call['call_type'] == 'direct':
                caller = call['caller_id']
                callee = call['callee_id']
                if caller not in graph:
                    graph[caller] = []
                graph[caller].append(callee)

        def dfs_depth(node, visited):
            if node in visited or node not in graph:
                return 0

            visited.add(node)
            max_child_depth = 0

            for neighbor in graph[node]:
                child_depth = dfs_depth(neighbor, visited.copy())
                max_child_depth = max(max_child_depth, child_depth)

            return 1 + max_child_depth

        max_depth = 0
        for func in self.functions:
            depth = dfs_depth(func['id'], set())
            max_depth = max(max_depth, depth)

        return max_depth
