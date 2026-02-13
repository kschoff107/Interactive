"""
ABAP Runtime Flow Parser - Extract subroutines, methods, function module calls,
and control flow from ABAP source code.

Uses regex-based parsing on comment-stripped, case-normalized source.
ABAP statements end with periods (.) and keywords are case-insensitive.
Blocks are delimited by keyword pairs (IF/ENDIF, LOOP/ENDLOOP, etc.).
"""

import logging
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from ..base import (
    BaseFlowParser,
    find_source_files,
    line_number_at,
    read_file_safe,
    strip_comments,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Compiled regex patterns (all match against UPPERCASED source)
# ---------------------------------------------------------------------------

# FORM name USING ... CHANGING ...
# Captures name and the full parameter clause up to the period/newline
# Uses negative lookbehind to avoid matching PER-FORM
_RE_FORM = re.compile(
    r'(?<![A-Z])FORM\s+(\w+)'
    r'((?:\s+(?:USING|CHANGING|TABLES|RAISING)\b[^.]*)*)'
    r'\s*\.',
)

# ENDFORM
_RE_ENDFORM = re.compile(r'ENDFORM\s*\.')

# CLASS name DEFINITION ... ENDCLASS.
_RE_CLASS_DEF = re.compile(
    r'CLASS\s+(\w+)\s+DEFINITION'
    r'((?:\s+(?:INHERITING\s+FROM|PUBLIC|ABSTRACT|FINAL|CREATE\s+\w+|FOR\s+TESTING)\b[^.]*)*)'
    r'\s*\.',
)

# CLASS name IMPLEMENTATION ... ENDCLASS.
_RE_CLASS_IMPL = re.compile(
    r'CLASS\s+(\w+)\s+IMPLEMENTATION\s*\.',
)

# ENDCLASS
_RE_ENDCLASS = re.compile(r'ENDCLASS\s*\.')

# METHOD name.
_RE_METHOD_START = re.compile(r'METHOD\s+(\S+)\s*\.')

# ENDMETHOD
_RE_ENDMETHOD = re.compile(r'ENDMETHOD\s*\.')

# METHODS: name IMPORTING ... EXPORTING ... RETURNING ... (in class DEFINITION)
_RE_METHOD_DECL = re.compile(
    r'METHODS\s*:?\s*(\S+)'
    r'((?:\s+(?:IMPORTING|EXPORTING|CHANGING|RETURNING|RAISING|REDEFINITION|'
    r'FOR\s+TESTING|ABSTRACT|FINAL)\b[^,.]*)*)',
)

# PERFORM name [USING ...] [CHANGING ...].
_RE_PERFORM = re.compile(
    r'PERFORM\s+(\w+)',
)

# CALL FUNCTION 'name'
_RE_CALL_FUNCTION = re.compile(
    r"CALL\s+FUNCTION\s+'([^']+)'",
)

# CALL METHOD (legacy syntax)
_RE_CALL_METHOD = re.compile(
    r'CALL\s+METHOD\s+(\S+)',
)

# Functional method call: obj->method( or class=>method( or method(
_RE_FUNC_CALL = re.compile(
    r'(\w+(?:->|=>)\w+)\s*\(',
)

# Standalone method/function call: name( — not preceded by METHOD or FORM
_RE_SIMPLE_CALL = re.compile(
    r'(?<!METHOD\s)(?<!FORM\s)(?<!CLASS\s)(?<!TYPES\s)(?<!DATA\s)'
    r'\b(\w+)\s*\(\s*',
)

# INHERITING FROM class_name
_RE_INHERITING = re.compile(r'INHERITING\s+FROM\s+(\w+)')

# --- Control flow patterns ---

_RE_IF = re.compile(r'\bIF\b\s+(.+?)\s*\.')
_RE_ELSEIF = re.compile(r'\bELSEIF\b\s+(.+?)\s*\.')
_RE_ELSE = re.compile(r'\bELSE\s*\.')
_RE_ENDIF = re.compile(r'\bENDIF\s*\.')

_RE_LOOP = re.compile(r'\bLOOP\s+AT\b\s+(.+?)\s*\.')
_RE_ENDLOOP = re.compile(r'\bENDLOOP\s*\.')

_RE_DO = re.compile(r'\bDO\b(?:\s+(\d+)\s+TIMES)?\s*\.')
_RE_ENDDO = re.compile(r'\bENDDO\s*\.')

_RE_WHILE = re.compile(r'\bWHILE\b\s+(.+?)\s*\.')
_RE_ENDWHILE = re.compile(r'\bENDWHILE\s*\.')

_RE_CASE = re.compile(r'\bCASE\b\s+([\w-]+)\s*\.')
_RE_WHEN = re.compile(r'\bWHEN\b\s+(.+?)\s*\.')
_RE_ENDCASE = re.compile(r'\bENDCASE\s*\.')

_RE_TRY = re.compile(r'\bTRY\s*\.')
_RE_CATCH = re.compile(r'\bCATCH\b\s+(.+?)\s*\.')
_RE_ENDTRY = re.compile(r'\bENDTRY\s*\.')

# --- Entry point events ---
_RE_START_OF_SELECTION = re.compile(r'\bSTART-OF-SELECTION\s*\.')
_RE_AT_SELECTION_SCREEN = re.compile(r'\bAT\s+SELECTION-SCREEN\b')
_RE_INITIALIZATION = re.compile(r'\bINITIALIZATION\s*\.')
_RE_END_OF_SELECTION = re.compile(r'\bEND-OF-SELECTION\s*\.')
_RE_TOP_OF_PAGE = re.compile(r'\bTOP-OF-PAGE\s*\.')

# USING/CHANGING parameter extraction
_RE_PARAM_USING = re.compile(
    r'USING\s+((?:\w+\s+TYPE\s+\w+\s*)+)',
)
_RE_PARAM_CHANGING = re.compile(
    r'CHANGING\s+((?:\w+\s+TYPE\s+\w+\s*)+)',
)
_RE_PARAM_ITEM = re.compile(
    r'(\w+)\s+TYPE\s+(\w+)',
)

# Method declaration parameter extraction
_RE_IMPORTING_PARAMS = re.compile(
    r'IMPORTING\s+((?:\w+\s+TYPE\s+\S+\s*)+)',
)
_RE_EXPORTING_PARAMS = re.compile(
    r'EXPORTING\s+((?:\w+\s+TYPE\s+\S+\s*)+)',
)
_RE_RETURNING_PARAMS = re.compile(
    r'RETURNING\s+VALUE\s*\(\s*(\w+)\s*\)\s+TYPE\s+(\S+)',
)


class ABAPFlowParser(BaseFlowParser):
    """Parse ABAP source code to extract runtime flow information.

    Extracts:
    - FORM ... ENDFORM subroutines
    - CLASS ... ENDCLASS definitions and implementations
    - METHOD ... ENDMETHOD bodies
    - PERFORM calls (subroutine invocations)
    - CALL FUNCTION calls (function module invocations)
    - CALL METHOD and functional method calls (obj->method(), class=>method())
    - Control flow: IF/ELSEIF/ELSE/ENDIF, LOOP/ENDLOOP, DO/ENDDO,
      WHILE/ENDWHILE, TRY/CATCH/ENDTRY, CASE/WHEN/ENDCASE
    - Entry points: START-OF-SELECTION, AT SELECTION-SCREEN, INITIALIZATION
    """

    FILE_EXTENSIONS = ['.abap', '.txt']

    def parse(self) -> Dict:
        """Parse all ABAP files in the project path."""
        files = find_source_files(str(self.project_path), self.FILE_EXTENSIONS)

        for fpath in files:
            content = read_file_safe(fpath)
            if not content:
                continue
            try:
                self._parse_file(content, fpath)
            except Exception as e:
                logger.warning("Failed to parse %s: %s", fpath, e)
                continue

        self._resolve_calls()
        return self.make_flow_result()

    # ------------------------------------------------------------------
    # File-level parsing
    # ------------------------------------------------------------------

    def _parse_file(self, content: str, file_path: str):
        """Parse a single ABAP source file."""
        stripped = strip_comments(content, 'abap')
        upper = stripped.upper()

        # Derive module name from file path
        rel_path = os.path.relpath(file_path, str(self.project_path))
        module_name = rel_path.replace(os.sep, '.').rsplit('.', 1)[0]

        self.modules.append({
            'id': f'module_{module_name}',
            'name': module_name,
            'file_path': file_path,
            'function_count': 0,  # updated later
        })

        func_count = 0

        # --- Parse FORM ... ENDFORM blocks ---
        func_count += self._parse_forms(upper, content, file_path, module_name)

        # --- Parse CLASS DEFINITION blocks ---
        self._parse_class_definitions(upper, content, file_path, module_name)

        # --- Parse CLASS IMPLEMENTATION blocks with METHODs ---
        func_count += self._parse_class_implementations(
            upper, content, file_path, module_name
        )

        # --- Parse entry point events ---
        self._parse_entry_points(upper, content, file_path, module_name)

        # --- Parse top-level calls (outside any function/method) ---
        self._parse_top_level_calls(upper, content, file_path, module_name)

        # Update module function count
        for mod in self.modules:
            if mod['id'] == f'module_{module_name}':
                mod['function_count'] = func_count
                break

    # ------------------------------------------------------------------
    # FORM parsing
    # ------------------------------------------------------------------

    def _parse_forms(
        self, upper: str, original: str, file_path: str, module_name: str
    ) -> int:
        """Parse FORM ... ENDFORM subroutine blocks. Returns count."""
        count = 0
        form_starts = list(_RE_FORM.finditer(upper))
        endform_positions = [m.start() for m in _RE_ENDFORM.finditer(upper)]

        for fm in form_starts:
            form_name = fm.group(1).strip()
            param_clause = fm.group(2).strip() if fm.group(2) else ''

            # Find matching ENDFORM
            body_start = fm.end()
            body_end = len(upper)
            for ep in endform_positions:
                if ep > fm.start():
                    body_end = ep
                    break

            body = upper[body_start:body_end]
            line_num = line_number_at(original, fm.start())
            end_line = line_number_at(original, body_end)

            # Parse parameters
            params = self._parse_form_params(param_clause)

            func_id = f'func_{module_name}_{form_name}_{line_num}'
            self.functions.append({
                'id': func_id,
                'type': 'subroutine',
                'name': form_name,
                'qualified_name': f'{module_name}.{form_name}',
                'module': module_name,
                'file_path': file_path,
                'line_number': line_num,
                'end_line': end_line,
                'parameters': params,
                'decorators': [],
                'is_async': False,
                'is_method': False,
                'class_name': None,
                'docstring': None,
                'complexity': self._calculate_complexity(body),
            })
            count += 1

            # Parse calls and control flow within the FORM body
            self._parse_calls_in_body(body, original, body_start, func_id, file_path)
            self._parse_control_flow_in_body(body, original, body_start, func_id, file_path)

        return count

    def _parse_form_params(self, clause: str) -> List[str]:
        """Extract parameter names from FORM USING/CHANGING clause."""
        params = []
        for pm in _RE_PARAM_ITEM.finditer(clause):
            param_name = pm.group(1).strip()
            if param_name not in ('USING', 'CHANGING', 'TABLES', 'RAISING'):
                params.append(param_name)
        return params

    # ------------------------------------------------------------------
    # CLASS parsing
    # ------------------------------------------------------------------

    def _parse_class_definitions(
        self, upper: str, original: str, file_path: str, module_name: str
    ):
        """Parse CLASS ... DEFINITION blocks to extract class metadata."""
        for m in _RE_CLASS_DEF.finditer(upper):
            class_name = m.group(1).strip()
            options = m.group(2).strip() if m.group(2) else ''
            line_num = line_number_at(original, m.start())

            # Extract parent class
            parent_class = None
            inherit_m = _RE_INHERITING.search(options)
            if inherit_m:
                parent_class = inherit_m.group(1).strip()

            # Find the ENDCLASS for this definition
            # Search from after the CLASS DEFINITION statement
            search_start = m.end()
            endclass_m = _RE_ENDCLASS.search(upper, search_start)
            end_line = line_number_at(original, endclass_m.start()) if endclass_m else line_num

            # Extract method declarations from the definition body
            def_body_end = endclass_m.start() if endclass_m else len(upper)
            def_body = upper[m.end():def_body_end]

            method_decls = []
            for md in _RE_METHOD_DECL.finditer(def_body):
                method_name = md.group(1).strip()
                method_decls.append(method_name)

            # Record as a module-level entry (class)
            class_id = f'class_{module_name}_{class_name}_{line_num}'
            self.functions.append({
                'id': class_id,
                'type': 'class',
                'name': class_name,
                'qualified_name': f'{module_name}.{class_name}',
                'module': module_name,
                'file_path': file_path,
                'line_number': line_num,
                'end_line': end_line,
                'parameters': [],
                'decorators': [],
                'is_async': False,
                'is_method': False,
                'class_name': None,
                'parent_class': parent_class,
                'method_declarations': method_decls,
                'docstring': None,
                'complexity': 1,
            })

    def _parse_class_implementations(
        self, upper: str, original: str, file_path: str, module_name: str
    ) -> int:
        """Parse CLASS ... IMPLEMENTATION blocks with METHOD bodies. Returns method count."""
        count = 0
        impl_starts = list(_RE_CLASS_IMPL.finditer(upper))

        # Find all ENDCLASS positions
        endclass_positions = [m.start() for m in _RE_ENDCLASS.finditer(upper)]

        for ci in impl_starts:
            class_name = ci.group(1).strip()
            impl_start = ci.end()

            # Find matching ENDCLASS
            impl_end = len(upper)
            for ep in endclass_positions:
                if ep > ci.start():
                    impl_end = ep
                    break

            impl_body = upper[impl_start:impl_end]

            # Parse METHOD ... ENDMETHOD blocks within the class
            method_starts = list(_RE_METHOD_START.finditer(impl_body))
            endmethod_positions = [m.start() for m in _RE_ENDMETHOD.finditer(impl_body)]

            for mm in method_starts:
                method_name = mm.group(1).strip()
                method_body_start = mm.end()

                # Find matching ENDMETHOD
                method_body_end = len(impl_body)
                for ep in endmethod_positions:
                    if ep > mm.start():
                        method_body_end = ep
                        break

                method_body = impl_body[method_body_start:method_body_end]
                abs_start = impl_start + mm.start()
                abs_body_start = impl_start + method_body_start
                line_num = line_number_at(original, abs_start)
                end_line = line_number_at(original, impl_start + method_body_end)

                # Extract parameters from method declaration (if we can find it)
                params = self._find_method_params(upper, class_name, method_name)

                func_id = f'func_{module_name}_{class_name}_{method_name}_{line_num}'
                self.functions.append({
                    'id': func_id,
                    'type': 'method',
                    'name': method_name,
                    'qualified_name': f'{module_name}.{class_name}.{method_name}',
                    'module': module_name,
                    'file_path': file_path,
                    'line_number': line_num,
                    'end_line': end_line,
                    'parameters': params,
                    'decorators': [],
                    'is_async': False,
                    'is_method': True,
                    'class_name': class_name,
                    'docstring': None,
                    'complexity': self._calculate_complexity(method_body),
                })
                count += 1

                # Parse calls and control flow within method body
                self._parse_calls_in_body(
                    method_body, original, abs_body_start, func_id, file_path
                )
                self._parse_control_flow_in_body(
                    method_body, original, abs_body_start, func_id, file_path
                )

        return count

    def _find_method_params(
        self, upper: str, class_name: str, method_name: str
    ) -> List[str]:
        """Try to find parameter declarations for a method in the class definition."""
        params = []
        # Build pattern to find the method declaration line
        pattern = re.compile(
            r'METHODS\s*:?\s*' + re.escape(method_name) + r'\b'
            r'((?:\s+(?:IMPORTING|EXPORTING|CHANGING|RETURNING|RAISING|'
            r'REDEFINITION|FOR\s+TESTING|ABSTRACT)\b[^,.]*)*)',
            re.DOTALL,
        )
        m = pattern.search(upper)
        if not m:
            return params

        decl = m.group(1) if m.group(1) else ''

        # Extract IMPORTING params
        for pm in _RE_PARAM_ITEM.finditer(decl):
            pname = pm.group(1).strip()
            if pname not in ('IMPORTING', 'EXPORTING', 'CHANGING', 'RETURNING',
                             'RAISING', 'VALUE', 'REDEFINITION'):
                params.append(pname)

        # Extract RETURNING VALUE(name) TYPE type
        ret_m = _RE_RETURNING_PARAMS.search(decl)
        if ret_m:
            params.append(ret_m.group(1).strip())

        return params

    # ------------------------------------------------------------------
    # Call extraction
    # ------------------------------------------------------------------

    def _parse_calls_in_body(
        self, body: str, original: str, abs_offset: int,
        caller_id: str, file_path: str
    ):
        """Extract all calls from a function/method body."""
        # PERFORM calls
        for m in _RE_PERFORM.finditer(body):
            callee = m.group(1).strip()
            line_num = line_number_at(original, abs_offset + m.start())
            call_id = f'call_{caller_id}_to_{callee}_{line_num}'
            self.calls.append({
                'id': call_id,
                'type': 'call',
                'call_kind': 'perform',
                'caller_id': caller_id,
                'callee_name': callee,
                'file_path': file_path,
                'line_number': line_num,
                'is_conditional': False,
                'is_loop': False,
            })

        # CALL FUNCTION calls
        for m in _RE_CALL_FUNCTION.finditer(body):
            func_name = m.group(1).strip()
            line_num = line_number_at(original, abs_offset + m.start())
            call_id = f'call_{caller_id}_to_FM_{func_name}_{line_num}'
            self.calls.append({
                'id': call_id,
                'type': 'call',
                'call_kind': 'function_module',
                'caller_id': caller_id,
                'callee_name': func_name,
                'file_path': file_path,
                'line_number': line_num,
                'is_conditional': False,
                'is_loop': False,
            })

        # CALL METHOD (legacy)
        for m in _RE_CALL_METHOD.finditer(body):
            method_ref = m.group(1).strip()
            line_num = line_number_at(original, abs_offset + m.start())
            call_id = f'call_{caller_id}_to_{method_ref}_{line_num}'
            self.calls.append({
                'id': call_id,
                'type': 'call',
                'call_kind': 'method',
                'caller_id': caller_id,
                'callee_name': method_ref,
                'file_path': file_path,
                'line_number': line_num,
                'is_conditional': False,
                'is_loop': False,
            })

        # Functional method calls: obj->method( or class=>method(
        for m in _RE_FUNC_CALL.finditer(body):
            method_ref = m.group(1).strip()
            line_num = line_number_at(original, abs_offset + m.start())
            call_id = f'call_{caller_id}_to_{method_ref}_{line_num}'
            self.calls.append({
                'id': call_id,
                'type': 'call',
                'call_kind': 'functional_method',
                'caller_id': caller_id,
                'callee_name': method_ref,
                'file_path': file_path,
                'line_number': line_num,
                'is_conditional': False,
                'is_loop': False,
            })

    def _parse_top_level_calls(
        self, upper: str, original: str, file_path: str, module_name: str
    ):
        """Parse PERFORM and CALL FUNCTION at the top level (outside FORM/METHOD)."""
        # This handles report-style programs with calls outside subroutines
        # We use a synthetic "top_level" caller
        caller_id = f'func_{module_name}___top_level__'

        # We only add top-level calls if there are PERFORM/CALL outside blocks
        # Simple approach: find all PERFORMs and filter out those inside known blocks
        # For now, top-level detection is best-effort via entry points
        pass

    # ------------------------------------------------------------------
    # Control flow extraction
    # ------------------------------------------------------------------

    def _parse_control_flow_in_body(
        self, body: str, original: str, abs_offset: int,
        parent_func_id: str, file_path: str
    ):
        """Extract control flow structures from a function/method body."""
        # IF statements
        for m in _RE_IF.finditer(body):
            condition = m.group(1).strip()[:100]  # Truncate long conditions
            line_num = line_number_at(original, abs_offset + m.start())
            ctrl_id = f'ctrl_if_{parent_func_id}_{line_num}'

            # Determine branches by scanning for ELSEIF/ELSE before ENDIF
            branches = self._determine_if_branches(body, m.start())

            self.control_flows.append({
                'id': ctrl_id,
                'type': 'control_flow',
                'flow_type': 'if_else',
                'parent_function_id': parent_func_id,
                'file_path': file_path,
                'line_number': line_num,
                'end_line': line_num,
                'condition': condition,
                'branches': branches,
            })

        # LOOP AT
        for m in _RE_LOOP.finditer(body):
            condition = m.group(1).strip()[:100]
            line_num = line_number_at(original, abs_offset + m.start())
            ctrl_id = f'ctrl_loop_{parent_func_id}_{line_num}'
            self.control_flows.append({
                'id': ctrl_id,
                'type': 'control_flow',
                'flow_type': 'loop',
                'parent_function_id': parent_func_id,
                'file_path': file_path,
                'line_number': line_num,
                'end_line': line_num,
                'condition': f'LOOP AT {condition}',
                'branches': ['body'],
            })

        # DO ... TIMES
        for m in _RE_DO.finditer(body):
            times = m.group(1) or 'indefinite'
            line_num = line_number_at(original, abs_offset + m.start())
            ctrl_id = f'ctrl_do_{parent_func_id}_{line_num}'
            self.control_flows.append({
                'id': ctrl_id,
                'type': 'control_flow',
                'flow_type': 'do_loop',
                'parent_function_id': parent_func_id,
                'file_path': file_path,
                'line_number': line_num,
                'end_line': line_num,
                'condition': f'DO {times} TIMES',
                'branches': ['body'],
            })

        # WHILE
        for m in _RE_WHILE.finditer(body):
            condition = m.group(1).strip()[:100]
            line_num = line_number_at(original, abs_offset + m.start())
            ctrl_id = f'ctrl_while_{parent_func_id}_{line_num}'
            self.control_flows.append({
                'id': ctrl_id,
                'type': 'control_flow',
                'flow_type': 'while_loop',
                'parent_function_id': parent_func_id,
                'file_path': file_path,
                'line_number': line_num,
                'end_line': line_num,
                'condition': f'WHILE {condition}',
                'branches': ['body'],
            })

        # CASE
        for m in _RE_CASE.finditer(body):
            variable = m.group(1).strip()
            line_num = line_number_at(original, abs_offset + m.start())
            ctrl_id = f'ctrl_case_{parent_func_id}_{line_num}'

            # Find WHEN branches
            branches = self._determine_case_branches(body, m.start())

            self.control_flows.append({
                'id': ctrl_id,
                'type': 'control_flow',
                'flow_type': 'case',
                'parent_function_id': parent_func_id,
                'file_path': file_path,
                'line_number': line_num,
                'end_line': line_num,
                'condition': f'CASE {variable}',
                'branches': branches,
            })

        # TRY/CATCH
        for m in _RE_TRY.finditer(body):
            line_num = line_number_at(original, abs_offset + m.start())
            ctrl_id = f'ctrl_try_{parent_func_id}_{line_num}'

            # Find CATCH branches
            branches = self._determine_try_branches(body, m.start())

            self.control_flows.append({
                'id': ctrl_id,
                'type': 'control_flow',
                'flow_type': 'try_catch',
                'parent_function_id': parent_func_id,
                'file_path': file_path,
                'line_number': line_num,
                'end_line': line_num,
                'condition': 'TRY',
                'branches': branches,
            })

    def _determine_if_branches(self, body: str, if_pos: int) -> List[str]:
        """Determine branches of an IF block (if, elseif, else)."""
        branches = ['if']
        # Simple scan: look for ELSEIF and ELSE before the next ENDIF
        # We track nesting depth
        depth = 1
        pos = if_pos + 2  # skip past 'IF'
        while pos < len(body) and depth > 0:
            remaining = body[pos:]
            # Check for nested IF
            if_m = re.match(r'\bIF\b', remaining)
            endif_m = re.match(r'\bENDIF\b', remaining)
            elseif_m = re.match(r'\bELSEIF\b', remaining)
            else_m = re.match(r'\bELSE\b(?!IF)', remaining)

            if endif_m:
                depth -= 1
                if depth == 0:
                    break
                pos += 5
            elif if_m and not remaining.startswith('ENDIF'):
                depth += 1
                pos += 2
            elif depth == 1 and elseif_m:
                branches.append('elseif')
                pos += 6
            elif depth == 1 and else_m:
                branches.append('else')
                pos += 4
            else:
                pos += 1

        return branches

    def _determine_case_branches(self, body: str, case_pos: int) -> List[str]:
        """Determine WHEN branches of a CASE block."""
        branches = []
        # Scan from case_pos to ENDCASE, collecting WHEN values
        search_start = case_pos + 4
        endcase_m = _RE_ENDCASE.search(body, search_start)
        search_end = endcase_m.start() if endcase_m else len(body)

        case_body = body[search_start:search_end]
        for wm in _RE_WHEN.finditer(case_body):
            value = wm.group(1).strip()[:50]
            if value == 'OTHERS':
                branches.append('WHEN OTHERS')
            else:
                branches.append(f'WHEN {value}')

        return branches or ['WHEN ...']

    def _determine_try_branches(self, body: str, try_pos: int) -> List[str]:
        """Determine CATCH branches of a TRY block."""
        branches = ['try']
        search_start = try_pos + 3
        endtry_m = _RE_ENDTRY.search(body, search_start)
        search_end = endtry_m.start() if endtry_m else len(body)

        try_body = body[search_start:search_end]
        for cm in _RE_CATCH.finditer(try_body):
            exc_types = cm.group(1).strip()[:80]
            branches.append(f'CATCH {exc_types}')

        return branches

    # ------------------------------------------------------------------
    # Entry points
    # ------------------------------------------------------------------

    def _parse_entry_points(
        self, upper: str, original: str, file_path: str, module_name: str
    ):
        """Detect ABAP event blocks as entry points."""
        entry_patterns = [
            (_RE_START_OF_SELECTION, 'START-OF-SELECTION', 'event'),
            (_RE_AT_SELECTION_SCREEN, 'AT SELECTION-SCREEN', 'event'),
            (_RE_INITIALIZATION, 'INITIALIZATION', 'event'),
            (_RE_END_OF_SELECTION, 'END-OF-SELECTION', 'event'),
            (_RE_TOP_OF_PAGE, 'TOP-OF-PAGE', 'event'),
        ]

        for pattern, name, ep_type in entry_patterns:
            m = pattern.search(upper)
            if m:
                line_num = line_number_at(original, m.start())
                func_id = f'func_{module_name}_{name.replace("-", "_").replace(" ", "_")}_{line_num}'
                self.functions.append({
                    'id': func_id,
                    'type': 'event',
                    'name': name,
                    'qualified_name': f'{module_name}.{name}',
                    'module': module_name,
                    'file_path': file_path,
                    'line_number': line_num,
                    'end_line': line_num,
                    'parameters': [],
                    'decorators': [],
                    'is_async': False,
                    'is_method': False,
                    'class_name': None,
                    'docstring': None,
                    'complexity': 1,
                })

    def _detect_entry_points(self) -> List[Dict]:
        """Override base class entry point detection for ABAP specifics."""
        entry_points = []

        for func in self.functions:
            if func['type'] == 'event':
                entry_points.append({
                    'id': f"entry_{func['id']}",
                    'type': 'abap_event',
                    'function_id': func['id'],
                    'event_name': func['name'],
                    'file_path': func['file_path'],
                    'line_number': func['line_number'],
                })

        return entry_points

    # ------------------------------------------------------------------
    # Complexity
    # ------------------------------------------------------------------

    @staticmethod
    def _calculate_complexity(body: str) -> int:
        """Calculate cyclomatic complexity from an ABAP code body."""
        complexity = 1  # base complexity

        decision_patterns = [
            r'\bIF\b', r'\bELSEIF\b', r'\bLOOP\b', r'\bDO\b',
            r'\bWHILE\b', r'\bCATCH\b', r'\bWHEN\b',
        ]

        for pat in decision_patterns:
            complexity += len(re.findall(pat, body))

        # Boolean operators
        complexity += len(re.findall(r'\bAND\b', body))
        complexity += len(re.findall(r'\bOR\b', body))

        return complexity
