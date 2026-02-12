"""
JavaScript/TypeScript Runtime Flow Parser - Extract function definitions,
calls, and control flow from JS/TS source code.

Uses regex on comment-stripped source to detect:
  - Function declarations and arrow functions
  - Class methods
  - Function calls within function bodies
  - Control flow structures (if/else, for, while, try/catch, switch)
  - Entry points (Express handlers, export default, module.exports)
"""

import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from ..base import (
    BaseFlowParser,
    extract_block_body,
    find_source_files,
    line_number_at,
    read_file_safe,
    strip_comments,
)

# ---------------------------------------------------------------------------
# Compiled regex patterns
# ---------------------------------------------------------------------------

# --- Function declarations ---
# function name(params) {
# async function name(params) {
# export function name(params) {
# export async function name(params) {
_RE_FUNC_DECL = re.compile(
    r'(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\(([^)]*)\)',
)

# --- Arrow function assignments ---
# const name = (params) => {
# const name = async (params) => {
# export const name = (params) => {
# const name = param => {
_RE_ARROW_FUNC = re.compile(
    r"""(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?"""
    r"""\(?([^)=]*?)\)?\s*=>\s*\{""",
)

# --- Class declarations ---
# class Name { ... }
# export class Name extends Base { ... }
_RE_CLASS = re.compile(
    r'(?:export\s+)?class\s+(\w+)(?:\s+extends\s+\w+)?\s*\{',
)

# --- Class method (inside class body) ---
# methodName(params) {
# async methodName(params) {
# static methodName(params) {
_RE_CLASS_METHOD = re.compile(
    r'(?:static\s+)?(?:async\s+)?(\w+)\s*\(([^)]*)\)\s*(?::\s*\w+[<>\[\]\w\s,|]*)?\s*\{',
)

# --- Function calls ---
# name(args)
# obj.method(args)
# obj.nested.method(args)
_RE_FUNC_CALL = re.compile(
    r'(?<!\w)([a-zA-Z_$][\w.$]*)\s*\(',
)

# --- Control flow ---
_RE_IF = re.compile(r'\bif\s*\(([^)]*)\)\s*\{')
_RE_ELSE_IF = re.compile(r'\belse\s+if\s*\(([^)]*)\)\s*\{')
_RE_ELSE = re.compile(r'\belse\s*\{')
_RE_FOR = re.compile(r'\bfor\s*\(([^)]*)\)\s*\{')
_RE_FOR_OF = re.compile(r'\bfor\s*\(\s*(?:const|let|var)\s+(\w+)\s+of\s+([^)]+)\)\s*\{')
_RE_FOR_IN = re.compile(r'\bfor\s*\(\s*(?:const|let|var)\s+(\w+)\s+in\s+([^)]+)\)\s*\{')
_RE_WHILE = re.compile(r'\bwhile\s*\(([^)]*)\)\s*\{')
_RE_DO_WHILE = re.compile(r'\bdo\s*\{')
_RE_TRY = re.compile(r'\btry\s*\{')
_RE_CATCH = re.compile(r'\bcatch\s*\(([^)]*)\)\s*\{')
_RE_FINALLY = re.compile(r'\bfinally\s*\{')
_RE_SWITCH = re.compile(r'\bswitch\s*\(([^)]*)\)\s*\{')

# --- Entry point patterns ---
# module.exports = ...
_RE_MODULE_EXPORTS = re.compile(r'module\.exports\s*=')
# export default
_RE_EXPORT_DEFAULT = re.compile(r'export\s+default\s+')
# Express route handler: app.get('/path', handler)
_RE_EXPRESS_HANDLER = re.compile(
    r"""(?:app|router)\.(get|post|put|delete|patch)\s*\(\s*['"][^'"]+['"]\s*,""",
)

# Skip these when recording function calls (language built-ins, control flow)
_SKIP_CALLS = {
    'if', 'else', 'for', 'while', 'switch', 'catch', 'return', 'throw',
    'new', 'typeof', 'instanceof', 'void', 'delete', 'await', 'yield',
    'require', 'import', 'export', 'super', 'this',
}


class JSFlowParser(BaseFlowParser):
    """Parse JavaScript/TypeScript source code to extract runtime flow information."""

    FILE_EXTENSIONS = ['.js', '.ts', '.jsx', '.tsx', '.mjs']

    def parse(self) -> Dict:
        """Parse all JS/TS files and return standardized runtime flow dict."""
        files = find_source_files(str(self.project_path), self.FILE_EXTENSIONS)

        for fpath in files:
            content = read_file_safe(fpath)
            if not content:
                continue
            try:
                self._parse_file(content, fpath)
            except Exception:
                continue

        # Resolve call targets
        self._resolve_calls()

        return self.make_flow_result()

    # ------------------------------------------------------------------
    # File-level parsing
    # ------------------------------------------------------------------

    def _parse_file(self, content: str, file_path: str):
        """Parse a single JS/TS file for functions, calls, and control flow."""
        stripped = strip_comments(content, 'javascript')
        rel_path = self._relative_path(file_path)
        module_name = rel_path.replace(os.sep, '.').rsplit('.', 1)[0]

        # Track module
        func_count_before = len(self.functions)

        # --- Parse top-level function declarations ---
        for m in _RE_FUNC_DECL.finditer(stripped):
            func_name = m.group(1)
            params = self._parse_params(m.group(2))
            is_async = 'async' in stripped[max(0, m.start() - 20):m.start()]
            line_num = line_number_at(content, m.start())

            body, bs, be = extract_block_body(stripped, m.end() - 1)
            if bs < 0:
                # Try from the match start in case params don't end right before {
                body, bs, be = extract_block_body(stripped, m.start())
                if bs < 0:
                    continue

            func_id = f"func_{module_name}_{func_name}_{line_num}"
            self.functions.append({
                'id': func_id,
                'type': 'function',
                'name': func_name,
                'qualified_name': f"{module_name}.{func_name}",
                'module': module_name,
                'file_path': file_path,
                'line_number': line_num,
                'end_line': line_number_at(content, bs + len(body)),
                'parameters': params,
                'decorators': [],
                'is_async': is_async,
                'is_method': False,
                'class_name': None,
                'complexity': self._calculate_complexity(body),
            })

            self._extract_calls(body, func_id, file_path, module_name, content, bs)
            self._extract_control_flow(body, func_id, file_path, module_name, content, bs)

        # --- Parse arrow function assignments ---
        for m in _RE_ARROW_FUNC.finditer(stripped):
            func_name = m.group(1)
            params = self._parse_params(m.group(2))
            is_async = 'async' in stripped[m.start():m.end()]
            line_num = line_number_at(content, m.start())

            body, bs, be = extract_block_body(stripped, m.end() - 1)
            if bs < 0:
                continue

            func_id = f"func_{module_name}_{func_name}_{line_num}"
            # Avoid duplicates from overlapping patterns
            if any(f['id'] == func_id for f in self.functions):
                continue

            self.functions.append({
                'id': func_id,
                'type': 'arrow_function',
                'name': func_name,
                'qualified_name': f"{module_name}.{func_name}",
                'module': module_name,
                'file_path': file_path,
                'line_number': line_num,
                'end_line': line_number_at(content, bs + len(body)),
                'parameters': params,
                'decorators': [],
                'is_async': is_async,
                'is_method': False,
                'class_name': None,
                'complexity': self._calculate_complexity(body),
            })

            self._extract_calls(body, func_id, file_path, module_name, content, bs)
            self._extract_control_flow(body, func_id, file_path, module_name, content, bs)

        # --- Parse classes and their methods ---
        for cm in _RE_CLASS.finditer(stripped):
            class_name = cm.group(1)
            class_body, cbs, cbe = extract_block_body(stripped, cm.start())
            if cbs < 0:
                continue
            self._parse_class_methods(
                class_body, cbs, class_name, content, stripped,
                file_path, module_name,
            )

        # Track module info
        func_count_after = len(self.functions)
        self.modules.append({
            'id': f"module_{module_name}",
            'name': module_name,
            'file_path': file_path,
            'function_count': func_count_after - func_count_before,
        })

    def _parse_class_methods(
        self, class_body: str, body_offset: int, class_name: str,
        original: str, stripped: str, file_path: str, module_name: str,
    ):
        """Parse methods inside a class body."""
        for m in _RE_CLASS_METHOD.finditer(class_body):
            method_name = m.group(1)
            params = self._parse_params(m.group(2))

            # Skip constructor-like patterns that aren't actual methods
            if method_name in ('if', 'for', 'while', 'switch', 'catch', 'class',
                               'function', 'return', 'new', 'get', 'set'):
                # 'get' and 'set' could be getters/setters; skip for simplicity
                continue

            is_async = bool(re.search(r'\basync\b', class_body[max(0, m.start() - 15):m.start()]))
            is_static = bool(re.search(r'\bstatic\b', class_body[max(0, m.start() - 15):m.start()]))
            abs_pos = body_offset + m.start()
            line_num = line_number_at(original, abs_pos)

            method_body, mbs, mbe = extract_block_body(class_body, m.start())
            if mbs < 0:
                continue

            func_id = f"func_{module_name}_{class_name}.{method_name}_{line_num}"
            if any(f['id'] == func_id for f in self.functions):
                continue

            self.functions.append({
                'id': func_id,
                'type': 'method',
                'name': method_name,
                'qualified_name': f"{module_name}.{class_name}.{method_name}",
                'module': module_name,
                'file_path': file_path,
                'line_number': line_num,
                'end_line': line_number_at(original, body_offset + mbs + len(method_body)),
                'parameters': params,
                'decorators': [],
                'is_async': is_async,
                'is_method': True,
                'is_static': is_static,
                'class_name': class_name,
                'complexity': self._calculate_complexity(method_body),
            })

            self._extract_calls(
                method_body, func_id, file_path, module_name,
                original, body_offset + mbs,
            )
            self._extract_control_flow(
                method_body, func_id, file_path, module_name,
                original, body_offset + mbs,
            )

    # ------------------------------------------------------------------
    # Call extraction
    # ------------------------------------------------------------------

    def _extract_calls(
        self, body: str, caller_id: str, file_path: str,
        module_name: str, original: str, body_offset: int,
    ):
        """Extract function calls from a function body."""
        for m in _RE_FUNC_CALL.finditer(body):
            callee_name = m.group(1)
            # Filter out noise
            if callee_name in _SKIP_CALLS:
                continue
            # Skip pure numeric or very short names
            if len(callee_name) < 2 and callee_name not in ('$',):
                continue

            abs_pos = body_offset + m.start()
            line_num = line_number_at(original, abs_pos)
            call_id = f"call_{caller_id}_to_{callee_name}_{line_num}"

            self.calls.append({
                'id': call_id,
                'type': 'call',
                'caller_id': caller_id,
                'callee_name': callee_name,
                'file_path': file_path,
                'line_number': line_num,
                'is_conditional': False,
                'is_loop': False,
            })

    # ------------------------------------------------------------------
    # Control flow extraction
    # ------------------------------------------------------------------

    def _extract_control_flow(
        self, body: str, func_id: str, file_path: str,
        module_name: str, original: str, body_offset: int,
    ):
        """Extract control flow structures from a function body."""
        # if / else if / else
        for m in _RE_IF.finditer(body):
            condition = m.group(1).strip()
            abs_pos = body_offset + m.start()
            line_num = line_number_at(original, abs_pos)
            branches = ['if']
            # Check for else/else-if after the if block
            if_body, ibs, ibe = extract_block_body(body, m.start())
            if ibe > 0:
                rest = body[ibe + 1:].lstrip()
                if rest.startswith('else if'):
                    branches.append('else if')
                elif rest.startswith('else'):
                    branches.append('else')

            self.control_flows.append({
                'id': f"ctrl_if_{module_name}_{line_num}",
                'type': 'control_flow',
                'flow_type': 'if_else',
                'parent_function_id': func_id,
                'file_path': file_path,
                'line_number': line_num,
                'condition': condition[:200],
                'branches': branches,
            })

        # for loops (standard, for-of, for-in)
        for m in _RE_FOR.finditer(body):
            condition = m.group(1).strip()
            abs_pos = body_offset + m.start()
            line_num = line_number_at(original, abs_pos)
            self.control_flows.append({
                'id': f"ctrl_for_{module_name}_{line_num}",
                'type': 'control_flow',
                'flow_type': 'for_loop',
                'parent_function_id': func_id,
                'file_path': file_path,
                'line_number': line_num,
                'condition': f"for ({condition[:150]})",
                'branches': ['body'],
            })

        # while loops
        for m in _RE_WHILE.finditer(body):
            condition = m.group(1).strip()
            abs_pos = body_offset + m.start()
            line_num = line_number_at(original, abs_pos)
            self.control_flows.append({
                'id': f"ctrl_while_{module_name}_{line_num}",
                'type': 'control_flow',
                'flow_type': 'while_loop',
                'parent_function_id': func_id,
                'file_path': file_path,
                'line_number': line_num,
                'condition': f"while ({condition[:150]})",
                'branches': ['body'],
            })

        # try/catch/finally
        for m in _RE_TRY.finditer(body):
            abs_pos = body_offset + m.start()
            line_num = line_number_at(original, abs_pos)
            branches = ['try']
            # Look for catch/finally after try block
            try_body, tbs, tbe = extract_block_body(body, m.start())
            if tbe > 0:
                rest = body[tbe + 1:]
                if _RE_CATCH.search(rest[:100]):
                    branches.append('catch')
                if _RE_FINALLY.search(rest[:200]):
                    branches.append('finally')

            self.control_flows.append({
                'id': f"ctrl_try_{module_name}_{line_num}",
                'type': 'control_flow',
                'flow_type': 'try_catch',
                'parent_function_id': func_id,
                'file_path': file_path,
                'line_number': line_num,
                'condition': 'try/catch',
                'branches': branches,
            })

        # switch
        for m in _RE_SWITCH.finditer(body):
            condition = m.group(1).strip()
            abs_pos = body_offset + m.start()
            line_num = line_number_at(original, abs_pos)
            self.control_flows.append({
                'id': f"ctrl_switch_{module_name}_{line_num}",
                'type': 'control_flow',
                'flow_type': 'switch',
                'parent_function_id': func_id,
                'file_path': file_path,
                'line_number': line_num,
                'condition': f"switch ({condition[:150]})",
                'branches': ['cases'],
            })

    # ------------------------------------------------------------------
    # Entry point detection
    # ------------------------------------------------------------------

    def _detect_entry_points(self) -> List[Dict]:
        """Identify entry points: Express handlers, exports, main functions."""
        entry_points = []

        for func in self.functions:
            fp = func.get('file_path', '')
            module = func.get('module', '')

            # Express route handlers
            if func['name'] in ('get', 'post', 'put', 'delete', 'patch'):
                continue  # These are HTTP verbs, not handlers

            # Check for common entry point names
            if func['name'] in ('main', 'start', 'init', 'bootstrap', 'run'):
                entry_points.append({
                    'id': f"entry_{func['id']}",
                    'type': 'main_function',
                    'function_id': func['id'],
                    'file_path': fp,
                    'line_number': func['line_number'],
                })
                continue

            # Check if function is exported (heuristic: look at file content)
            content = read_file_safe(fp)
            if content:
                stripped = strip_comments(content, 'javascript')
                # module.exports = funcName or exports.funcName
                if re.search(
                    rf'(?:module\.exports\s*=\s*{re.escape(func["name"])}|'
                    rf'exports\.{re.escape(func["name"])})',
                    stripped,
                ):
                    entry_points.append({
                        'id': f"entry_{func['id']}",
                        'type': 'export',
                        'function_id': func['id'],
                        'file_path': fp,
                        'line_number': func['line_number'],
                    })
                # export default funcName
                elif re.search(
                    rf'export\s+default\s+{re.escape(func["name"])}',
                    stripped,
                ):
                    entry_points.append({
                        'id': f"entry_{func['id']}",
                        'type': 'export_default',
                        'function_id': func['id'],
                        'file_path': fp,
                        'line_number': func['line_number'],
                    })

        return entry_points

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
            p = re.sub(r':\s*\w+[<>\[\]\w\s,|?]*$', '', p)
            # Remove default values
            p = re.sub(r'\s*=\s*.*$', '', p)
            # Remove destructuring (simplify)
            p = p.strip()
            if p and p not in ('', '{', '}', '...'):
                # Handle rest params
                p = p.lstrip('.')
                if p:
                    params.append(p)
        return params

    @staticmethod
    def _calculate_complexity(body: str) -> int:
        """Calculate cyclomatic complexity from function body text."""
        complexity = 1
        # Count decision points
        complexity += len(_RE_IF.findall(body))
        complexity += len(_RE_ELSE_IF.findall(body))
        complexity += len(_RE_FOR.findall(body))
        complexity += len(_RE_WHILE.findall(body))
        complexity += len(_RE_CATCH.findall(body))
        complexity += len(_RE_SWITCH.findall(body))
        # Count logical operators
        complexity += len(re.findall(r'&&|\|\|', body))
        return complexity

    def _relative_path(self, file_path: str) -> str:
        """Get path relative to project root."""
        try:
            return str(Path(file_path).relative_to(self.project_path))
        except ValueError:
            return os.path.basename(file_path)
