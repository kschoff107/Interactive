"""
Java Runtime Flow Parser - Extract method definitions, calls, and control flow from Java code.

Uses regex-based parsing with brace counting to extract method declarations,
method calls, control flow structures, and entry points from Java source files.
"""

import logging
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

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Compiled regex patterns
# ---------------------------------------------------------------------------

# Class declaration
_RE_CLASS = re.compile(
    r'(?:(?:public|protected|private)\s+)?'
    r'(?:(?:static|final|abstract)\s+)*'
    r'class\s+(?P<class_name>\w+)'
    r'(?:\s+extends\s+(?P<parent>\w+))?'
    r'(?:\s+implements\s+(?P<interfaces>[\w,\s]+))?'
    r'\s*\{',
)

# Method declaration (includes constructors via return_type being optional)
# Requires an access modifier to avoid matching method calls or local statements.
_RE_METHOD = re.compile(
    r'(?P<annotations>(?:\s*@\w+(?:\s*\([^)]*(?:\([^)]*\))*[^)]*\))?)*?)\s*'
    r'(?P<modifiers>(?:public|protected|private)\s+'
    r'(?:(?:static|final|abstract|synchronized|native)\s+)*)'
    r'(?:(?P<return_type>[\w<>,\s\?\[\]]+?)\s+)?'
    r'(?P<method_name>\w+)\s*'
    r'\((?P<params>(?:[^()]*|\([^)]*\))*)\)\s*'
    r'(?:throws\s+[\w,\s]+\s*)?'
    r'(?:\{|;)',
)

# Method call: name( — but filter out Java keywords
_RE_METHOD_CALL = re.compile(
    r'(?<!\w)(?P<callee>(?:(?:\w+\.)*\w+))\s*\(',
)

# Java keywords and structures that look like calls but aren't
_JAVA_KEYWORDS = frozenset({
    'if', 'else', 'for', 'while', 'do', 'switch', 'case', 'try', 'catch',
    'finally', 'return', 'throw', 'new', 'class', 'interface', 'enum',
    'extends', 'implements', 'import', 'package', 'this', 'super',
    'instanceof', 'assert', 'synchronized', 'default', 'break', 'continue',
})

# Control flow patterns
_RE_IF = re.compile(
    r'\bif\s*\((?P<condition>[^)]*(?:\([^)]*\))*[^)]*)\)',
)
_RE_ELSE_IF = re.compile(
    r'\}\s*else\s+if\s*\((?P<condition>[^)]*(?:\([^)]*\))*[^)]*)\)',
)
_RE_ELSE = re.compile(
    r'\}\s*else\s*\{',
)
_RE_FOR = re.compile(
    r'\bfor\s*\((?P<condition>[^)]*(?:\([^)]*\))*[^)]*)\)',
)
_RE_WHILE = re.compile(
    r'\bwhile\s*\((?P<condition>[^)]*(?:\([^)]*\))*[^)]*)\)',
)
_RE_DO_WHILE = re.compile(
    r'\bdo\s*\{',
)
_RE_TRY = re.compile(
    r'\btry\s*(?:\([^)]*\)\s*)?\{',
)
_RE_CATCH = re.compile(
    r'\bcatch\s*\(\s*(?P<exception_type>[\w\s|]+)\s+\w+\s*\)',
)
_RE_FINALLY = re.compile(
    r'\bfinally\s*\{',
)
_RE_SWITCH = re.compile(
    r'\bswitch\s*\((?P<expression>[^)]*)\)',
)
_RE_CASE = re.compile(
    r'\bcase\s+(?P<value>[^:]+):',
)

# Entry point annotations
_RE_ENTRY_ANNOTATION = re.compile(
    r'@(?:GetMapping|PostMapping|PutMapping|DeleteMapping|PatchMapping|'
    r'RequestMapping|Scheduled|EventListener|RabbitListener|KafkaListener)\b',
)

# Main method pattern
_RE_MAIN_METHOD = re.compile(
    r'public\s+static\s+void\s+main\s*\(\s*String\s*\[\s*\]\s+\w+\s*\)',
)

# Annotation extraction
_RE_ANNOTATION = re.compile(
    r'@(\w+)(?:\s*\([^)]*\))?',
)


class JavaFlowParser(BaseFlowParser):
    """Parser for Java runtime flow analysis using regex-based parsing."""

    FILE_EXTENSIONS = ['.java']

    def parse(self) -> Dict:
        """Parse Java source files and return standardized runtime flow.

        Returns:
            Standardized runtime_flow dict.
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

        # Resolve calls to definitions
        self._resolve_calls()

        return self.make_flow_result()

    def _parse_file(self, content: str, file_path: str) -> None:
        """Parse a single Java file for methods, calls, and control flow."""
        stripped = strip_comments(content, 'java')

        # Derive module name from relative path
        rel_path = os.path.relpath(file_path, str(self.project_path))
        module_name = rel_path.replace(os.sep, '.').replace('.java', '')

        # Find classes
        classes_found = list(_RE_CLASS.finditer(stripped))

        if not classes_found:
            # Parse file-level content even without explicit class
            self._parse_methods_in_scope(
                stripped, 0, len(stripped), None, module_name, file_path, content
            )
            self.modules.append({
                'id': f'module_{module_name}',
                'name': module_name,
                'file_path': file_path,
                'function_count': 0,
            })
            return

        for class_match in classes_found:
            class_name = class_match.group('class_name')
            class_pos = class_match.start()

            body, body_start, body_end = extract_block_body(stripped, class_pos)
            if body_start == -1:
                continue

            line = line_number_at(content, class_pos)

            # Track module
            mod_id = f'module_{module_name}.{class_name}'
            self.modules.append({
                'id': mod_id,
                'name': f'{module_name}.{class_name}',
                'file_path': file_path,
                'line_number': line,
                'function_count': 0,
            })

            # Parse methods within the class body
            method_count = self._parse_methods_in_scope(
                body, body_start, body_end, class_name, module_name,
                file_path, content,
            )

            # Update module function count
            self.modules[-1]['function_count'] = method_count

    def _parse_methods_in_scope(
        self,
        body: str,
        body_start: int,
        body_end: int,
        class_name: Optional[str],
        module_name: str,
        file_path: str,
        original_content: str,
    ) -> int:
        """Parse methods within a class or file scope.

        Returns:
            Number of methods found.
        """
        method_count = 0

        # Build original (unstripped) body for extracting string-valued annotations
        original_body = original_content[body_start:body_start + len(body)]

        for method_match in _RE_METHOD.finditer(body):
            method_name = method_match.group('method_name')
            modifiers_str = method_match.group('modifiers') or ''
            return_type = method_match.group('return_type')
            params_text = method_match.group('params') or ''
            # Use original body for annotations to preserve string literals
            ann_start = method_match.start('annotations')
            ann_end = method_match.end('annotations')
            annotations_text = original_body[ann_start:ann_end] if ann_start >= 0 else ''

            # Skip if this looks like a control structure or keyword
            if method_name in _JAVA_KEYWORDS:
                continue

            # Skip if this is inside a method body (nested class or lambda)
            # We only want top-level methods of the class

            method_pos = method_match.start()
            abs_pos = body_start + method_pos
            line = line_number_at(original_content, abs_pos)

            # Determine method type
            is_static = 'static' in modifiers_str
            is_abstract = 'abstract' in modifiers_str
            is_constructor = return_type is None or (
                class_name is not None and method_name == class_name
            )

            # Check if declaration ends with ; (abstract/interface method)
            decl_end_char = body[method_match.end() - 1] if method_match.end() > 0 else ''
            has_body = decl_end_char == '{'

            # Extract parameters
            parameters = self._parse_parameters(params_text)

            # Extract decorators/annotations
            decorators = [
                f'@{m.group(1)}' for m in _RE_ANNOTATION.finditer(annotations_text)
            ]

            # Calculate complexity and extract calls/control flow from body
            complexity = 1  # base complexity
            method_body = ''
            end_line = line

            if has_body:
                method_body, mb_start, mb_end = extract_block_body(
                    body, method_match.start()
                )
                if mb_end != -1:
                    end_line = line_number_at(original_content, body_start + mb_end)

            # Build qualified name
            if class_name:
                qualified_name = f'{module_name}.{class_name}.{method_name}'
            else:
                qualified_name = f'{module_name}.{method_name}'

            # Generate unique ID
            func_id = f'func_{module_name}_{class_name or ""}_{method_name}_{line}'

            # Determine method type label
            if is_constructor:
                func_type = 'constructor'
            elif is_abstract:
                func_type = 'abstract_method'
            elif is_static:
                func_type = 'static_method'
            else:
                func_type = 'method'

            func_data = {
                'id': func_id,
                'type': func_type,
                'name': method_name,
                'qualified_name': qualified_name,
                'module': module_name,
                'class_name': class_name,
                'file_path': file_path,
                'line_number': line,
                'end_line': end_line,
                'parameters': parameters,
                'return_type': return_type.strip() if return_type else None,
                'decorators': decorators,
                'is_async': False,
                'is_method': class_name is not None,
                'is_static': is_static,
                'is_abstract': is_abstract,
                'is_constructor': is_constructor,
                'complexity': 1,  # will be updated below
            }

            # Parse method body for calls and control flow
            if has_body and method_body:
                complexity = self._calculate_complexity(method_body)
                mb_abs_offset = body_start + (mb_start if mb_start != -1 else method_pos)
                # Get original (unstripped) method body for string values
                original_method_body = original_content[mb_abs_offset:mb_abs_offset + len(method_body)]
                self._extract_calls(
                    method_body, func_id, file_path, module_name,
                    original_content, mb_abs_offset,
                )
                self._extract_control_flow(
                    method_body, original_method_body, func_id, file_path, module_name,
                    original_content, mb_abs_offset,
                )

            func_data['complexity'] = complexity
            self.functions.append(func_data)
            method_count += 1

        return method_count

    @staticmethod
    def _parse_parameters(params_text: str) -> List[str]:
        """Parse method parameter list into a list of parameter names.

        Args:
            params_text: Text inside parentheses, e.g. 'Long id, String name'

        Returns:
            List of parameter name strings.
        """
        params = []
        if not params_text.strip():
            return params

        for param in params_text.split(','):
            param = param.strip()
            if not param:
                continue
            # Remove annotations like @PathVariable, @RequestBody, etc.
            param = re.sub(r'@\w+(?:\s*\([^)]*\))?\s*', '', param).strip()
            # Split on whitespace; last token is the name
            parts = param.split()
            if parts:
                params.append(parts[-1])

        return params

    def _extract_calls(
        self,
        method_body: str,
        caller_id: str,
        file_path: str,
        module_name: str,
        original_content: str,
        body_abs_offset: int,
    ) -> None:
        """Extract method calls from a method body."""
        for m in _RE_METHOD_CALL.finditer(method_body):
            callee_raw = m.group('callee')
            call_pos = m.start()

            # Get the simple method name (last part of dotted expression)
            parts = callee_raw.split('.')
            callee_name = parts[-1]

            # Skip Java keywords and common non-method patterns
            if callee_name in _JAVA_KEYWORDS:
                continue

            # Skip class instantiation-like patterns (starts with uppercase after 'new')
            # But allow normal method calls on objects
            preceding = method_body[max(0, call_pos - 5):call_pos].strip()
            if preceding.endswith('new'):
                continue

            line = line_number_at(original_content, body_abs_offset + call_pos)

            call_id = f'call_{caller_id}_to_{callee_name}_{line}'

            self.calls.append({
                'id': call_id,
                'type': 'call',
                'caller_id': caller_id,
                'callee_name': callee_name,
                'callee_qualified': callee_raw,
                'file_path': file_path,
                'line_number': line,
                'is_conditional': False,
                'is_loop': False,
            })

    def _extract_control_flow(
        self,
        method_body: str,
        original_method_body: str,
        parent_func_id: str,
        file_path: str,
        module_name: str,
        original_content: str,
        body_abs_offset: int,
    ) -> None:
        """Extract control flow structures from a method body.

        Uses stripped method_body for regex matching and original_method_body
        for extracting string-containing conditions (switch/case values).
        """

        # if statements
        for m in _RE_IF.finditer(method_body):
            # Skip else-if matches (handled separately)
            before = method_body[max(0, m.start() - 10):m.start()]
            if 'else' in before:
                continue

            line = line_number_at(original_content, body_abs_offset + m.start())
            branches = ['if']

            # Check for else/else-if after this if
            after_pos = m.end()
            remaining = method_body[after_pos:]
            if _RE_ELSE_IF.search(remaining):
                branches.append('else-if')
            if _RE_ELSE.search(remaining):
                branches.append('else')

            self.control_flows.append({
                'id': f'ctrl_if_{module_name}_{line}',
                'type': 'control_flow',
                'flow_type': 'if_else',
                'parent_function_id': parent_func_id,
                'file_path': file_path,
                'line_number': line,
                'condition': m.group('condition').strip(),
                'branches': branches,
            })

        # for loops
        for m in _RE_FOR.finditer(method_body):
            line = line_number_at(original_content, body_abs_offset + m.start())
            self.control_flows.append({
                'id': f'ctrl_for_{module_name}_{line}',
                'type': 'control_flow',
                'flow_type': 'for_loop',
                'parent_function_id': parent_func_id,
                'file_path': file_path,
                'line_number': line,
                'condition': f'for ({m.group("condition").strip()})',
                'branches': ['body'],
            })

        # while loops
        for m in _RE_WHILE.finditer(method_body):
            # Skip do-while condition
            before = method_body[max(0, m.start() - 5):m.start()].strip()
            if before.endswith('}'):
                # This could be the while in a do-while, but we detect do separately
                pass

            line = line_number_at(original_content, body_abs_offset + m.start())
            self.control_flows.append({
                'id': f'ctrl_while_{module_name}_{line}',
                'type': 'control_flow',
                'flow_type': 'while_loop',
                'parent_function_id': parent_func_id,
                'file_path': file_path,
                'line_number': line,
                'condition': f'while ({m.group("condition").strip()})',
                'branches': ['body'],
            })

        # do-while loops
        for m in _RE_DO_WHILE.finditer(method_body):
            line = line_number_at(original_content, body_abs_offset + m.start())
            self.control_flows.append({
                'id': f'ctrl_do_while_{module_name}_{line}',
                'type': 'control_flow',
                'flow_type': 'do_while_loop',
                'parent_function_id': parent_func_id,
                'file_path': file_path,
                'line_number': line,
                'condition': 'do-while',
                'branches': ['body'],
            })

        # try/catch/finally
        for m in _RE_TRY.finditer(method_body):
            line = line_number_at(original_content, body_abs_offset + m.start())
            branches = ['try']

            # Find catch blocks after this try
            after_pos = m.end()
            remaining = method_body[after_pos:]
            for catch_m in _RE_CATCH.finditer(remaining):
                exc_type = catch_m.group('exception_type').strip()
                branches.append(f'catch ({exc_type})')

            if _RE_FINALLY.search(remaining):
                branches.append('finally')

            self.control_flows.append({
                'id': f'ctrl_try_{module_name}_{line}',
                'type': 'control_flow',
                'flow_type': 'try_catch',
                'parent_function_id': parent_func_id,
                'file_path': file_path,
                'line_number': line,
                'condition': 'try/catch',
                'branches': branches,
            })

        # switch/case
        for m in _RE_SWITCH.finditer(method_body):
            line = line_number_at(original_content, body_abs_offset + m.start())
            expression = m.group('expression').strip()

            # Find case labels in the switch body using original content
            # to preserve string literal values in case labels
            switch_body, sb_start, sb_end = extract_block_body(
                method_body, m.start()
            )
            cases = []
            if switch_body and sb_start >= 0:
                # Use original method body at same offsets for case values
                # sb_start/sb_end are absolute positions in method_body
                original_switch_body = original_method_body[sb_start:sb_end]
                for case_m in _RE_CASE.finditer(original_switch_body):
                    cases.append(case_m.group('value').strip())
                if 'default:' in switch_body or 'default :' in switch_body:
                    cases.append('default')

            self.control_flows.append({
                'id': f'ctrl_switch_{module_name}_{line}',
                'type': 'control_flow',
                'flow_type': 'switch',
                'parent_function_id': parent_func_id,
                'file_path': file_path,
                'line_number': line,
                'condition': f'switch ({expression})',
                'branches': cases or ['default'],
            })

    @staticmethod
    def _calculate_complexity(method_body: str) -> int:
        """Calculate cyclomatic complexity for a method body.

        Counts decision points: if, else if, for, while, do, case,
        catch, &&, ||, ternary ?.
        """
        complexity = 1  # base complexity

        # Decision point patterns
        complexity += len(re.findall(r'\bif\s*\(', method_body))
        complexity += len(re.findall(r'\belse\s+if\s*\(', method_body))
        complexity += len(re.findall(r'\bfor\s*\(', method_body))
        complexity += len(re.findall(r'\bwhile\s*\(', method_body))
        complexity += len(re.findall(r'\bdo\s*\{', method_body))
        complexity += len(re.findall(r'\bcase\s+', method_body))
        complexity += len(re.findall(r'\bcatch\s*\(', method_body))

        # Boolean operators add to complexity
        complexity += len(re.findall(r'&&', method_body))
        complexity += len(re.findall(r'\|\|', method_body))

        # Ternary operator
        complexity += len(re.findall(r'\?[^?]', method_body))

        return complexity

    def _detect_entry_points(self) -> List[Dict]:
        """Identify Java entry points: main methods, mapped endpoints, scheduled tasks."""
        entry_points: List[Dict] = []

        for func in self.functions:
            decorators = func.get('decorators', [])
            annotations_str = ' '.join(decorators)

            # Check for public static void main
            if (func['name'] == 'main' and
                    func.get('is_static') and
                    func.get('return_type') in ('void', None)):
                entry_points.append({
                    'id': f'entry_{func["id"]}',
                    'type': 'main_method',
                    'function_id': func['id'],
                    'file_path': func['file_path'],
                    'line_number': func['line_number'],
                })
                continue

            # Check for Spring mapping annotations
            for ann in decorators:
                if any(mapping in ann for mapping in (
                    '@GetMapping', '@PostMapping', '@PutMapping',
                    '@DeleteMapping', '@PatchMapping', '@RequestMapping',
                )):
                    entry_points.append({
                        'id': f'entry_{func["id"]}',
                        'type': 'route',
                        'function_id': func['id'],
                        'decorator': ann,
                        'file_path': func['file_path'],
                        'line_number': func['line_number'],
                    })
                    break

            # Check for scheduled tasks
            for ann in decorators:
                if '@Scheduled' in ann:
                    entry_points.append({
                        'id': f'entry_{func["id"]}',
                        'type': 'scheduled',
                        'function_id': func['id'],
                        'decorator': ann,
                        'file_path': func['file_path'],
                        'line_number': func['line_number'],
                    })
                    break

        return entry_points
