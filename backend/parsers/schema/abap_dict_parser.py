"""
ABAP Dictionary Parser - Extract schema from ABAP type definitions,
data declarations, and CDS view definitions.

Uses regex-based parsing on comment-stripped, case-normalized source.
ABAP statements end with periods (.) and keywords are case-insensitive.
"""

import logging
import os
import re
from typing import Dict, List, Optional, Tuple

from ..base import (
    BaseSchemaParser,
    find_source_files,
    line_number_at,
    read_file_safe,
    strip_comments,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# ABAP type -> SQL type mapping
# ---------------------------------------------------------------------------

_ABAP_TYPE_MAP = {
    'CHAR': 'VARCHAR',
    'NUMC': 'VARCHAR',
    'CLNT': 'VARCHAR',
    'MANDT': 'VARCHAR',
    'LANG': 'VARCHAR',
    'CUKY': 'VARCHAR',
    'UNIT': 'VARCHAR',
    'STRING': 'TEXT',
    'XSTRING': 'BLOB',
    'INT1': 'SMALLINT',
    'INT2': 'SMALLINT',
    'INT4': 'INTEGER',
    'INT8': 'BIGINT',
    'INTEGER': 'INTEGER',
    'I': 'INTEGER',
    'P': 'DECIMAL',
    'DEC': 'DECIMAL',
    'CURR': 'DECIMAL',
    'QUAN': 'DECIMAL',
    'FLTP': 'FLOAT',
    'F': 'FLOAT',
    'D': 'DATE',
    'DATS': 'DATE',
    'T': 'TIME',
    'TIMS': 'TIME',
    'TIMESTAMP': 'TIMESTAMP',
    'TIMESTAMPL': 'TIMESTAMP',
    'ABAP_BOOL': 'BOOLEAN',
    'BOOLE_D': 'BOOLEAN',
    'FLAG': 'BOOLEAN',
    'RAW': 'VARBINARY',
    'LRAW': 'BLOB',
    'X': 'VARBINARY',
    'N': 'VARCHAR',
    'C': 'VARCHAR',
}

# Well-known ABAP key data elements that typically reference other entities
_KNOWN_KEY_FIELDS = {
    'KUNNR': 'customers',       # Customer number
    'LIFNR': 'vendors',         # Vendor number
    'MATNR': 'materials',       # Material number
    'VBELN': 'sales_documents', # Sales document number
    'BUKRS': 'company_codes',   # Company code
    'WERKS': 'plants',          # Plant
    'EBELN': 'purchase_orders', # Purchase order number
    'BELNR': 'accounting_docs', # Accounting document number
    'PERNR': 'employees',       # Personnel number
    'AUFNR': 'orders',          # Order number
    'KOSTL': 'cost_centers',    # Cost center
    'GJAHR': 'fiscal_years',    # Fiscal year
    'PSPNR': 'wbs_elements',   # WBS element
    'MBLNR': 'material_docs',  # Material document number
}

# ---------------------------------------------------------------------------
# Compiled regex patterns
# ---------------------------------------------------------------------------

# TYPES: BEGIN OF name, ... END OF name.
# Captures the structure name and the block of fields up to END OF
_RE_TYPES_BEGIN = re.compile(
    r'TYPES\s*:\s*BEGIN\s+OF\s+(\w+)\s*[,.]'
    r'(.*?)'
    r'END\s+OF\s+\1\s*\.',
    re.DOTALL,
)

# DATA: BEGIN OF name, ... END OF name.
_RE_DATA_BEGIN = re.compile(
    r'DATA\s*:\s*BEGIN\s+OF\s+(\w+)\s*[,.]'
    r'(.*?)'
    r'END\s+OF\s+\1\s*\.',
    re.DOTALL,
)

# Field line inside a structure block:
#   fieldname TYPE typename,
#   fieldname TYPE typename LENGTH n,
#   fieldname(length) TYPE c,
_RE_FIELD = re.compile(
    r'(\w+)\s*'
    r'(?:\(\s*(\d+)\s*\)\s*)?'       # optional (length)
    r'TYPE\s+'
    r'(\w+)'                          # type name
    r'(?:\s*\(\s*(\d+)\s*\))?'       # optional (length) after type
    r'(?:\s+LENGTH\s+(\d+))?'        # optional LENGTH n
    r'(?:\s+DECIMALS\s+(\d+))?',     # optional DECIMALS n
)

# Table type: TYPES: tt_name TYPE (STANDARD|SORTED|HASHED) TABLE OF typename ...
_RE_TABLE_TYPE = re.compile(
    r'TYPES\s*:\s*(\w+)\s+TYPE\s+'
    r'(?:STANDARD|SORTED|HASHED)\s+TABLE\s+OF\s+(\w+)',
)

# Data table: DATA: gt_name TYPE (STANDARD|SORTED|HASHED) TABLE OF typename ...
_RE_DATA_TABLE = re.compile(
    r'DATA\s*:\s*(\w+)\s+TYPE\s+'
    r'(?:STANDARD|SORTED|HASHED)\s+TABLE\s+OF\s+(\w+)',
)

# INCLUDE TYPE name.
_RE_INCLUDE_TYPE = re.compile(
    r'INCLUDE\s+TYPE\s+(\w+)\s*\.',
)

# CONSTANTS: gc_name TYPE typename VALUE 'value'.
_RE_CONSTANT = re.compile(
    r"CONSTANTS\s*:\s*(\w+)\s+TYPE\s+(\w+)\s+VALUE\s+'([^']*)'",
)

# CDS view: define view NAME as select from TABLE { fields }
_RE_CDS_VIEW = re.compile(
    r'DEFINE\s+VIEW\s+(\w+)\s+AS\s+SELECT\s+FROM\s+(\w+)'
    r'\s*\{([^}]*)\}',
    re.DOTALL,
)

# CDS annotation: @AbapCatalog.sqlViewName: 'name'
_RE_CDS_SQL_VIEW = re.compile(
    r"@ABAPCATALOG\.SQLVIEWNAME\s*:\s*'(\w+)'",
)

# CDS annotation: @EndUserText.label: 'label'
_RE_CDS_LABEL = re.compile(
    r"@ENDUSERTEXT\.LABEL\s*:\s*'([^']*)'",
)


class ABAPDictParser(BaseSchemaParser):
    """Parse ABAP Dictionary definitions into standardized schema format.

    Handles:
    - TYPES: BEGIN OF ... END OF. structure definitions
    - DATA: BEGIN OF ... END OF. structure declarations
    - Table type declarations (STANDARD/SORTED/HASHED TABLE OF)
    - CDS view definitions (define view ... as select from ...)
    - INCLUDE TYPE directives
    - Foreign key detection from field naming conventions
    """

    FILE_EXTENSIONS = ['.abap', '.txt', '.asddls']

    def parse(self, project_path: str) -> Dict:
        """Parse all ABAP source files in project_path for schema definitions."""
        files = self.find_files(project_path)
        all_tables: List[Dict] = []
        all_relationships: List[Dict] = []
        table_type_refs: Dict[str, str] = {}  # table_type_name -> structure_name

        for fpath in files:
            content = read_file_safe(fpath)
            if not content:
                continue
            try:
                tables, rels, tt_refs = self._parse_file(content, fpath)
                all_tables.extend(tables)
                all_relationships.extend(rels)
                table_type_refs.update(tt_refs)
            except Exception as e:
                logger.warning("Failed to parse %s: %s", fpath, e)
                continue

        # Derive implicit relationships from foreign key detection
        implicit = self._detect_relationships(all_tables)
        existing = {
            (r.get('from_table') or r.get('from', ''),
             r.get('to_table') or r.get('to', ''))
            for r in all_relationships
        }
        for r in implicit:
            key = (r.get('from_table') or r.get('from', ''),
                   r.get('to_table') or r.get('to', ''))
            if key not in existing:
                all_relationships.append(r)

        return self.make_schema_result(all_tables, all_relationships)

    # ------------------------------------------------------------------
    # Internal parsing
    # ------------------------------------------------------------------

    def _parse_file(
        self, content: str, file_path: str
    ) -> Tuple[List[Dict], List[Dict], Dict[str, str]]:
        """Parse a single ABAP file for schema definitions."""
        stripped = strip_comments(content, 'abap')
        upper = stripped.upper()

        tables: List[Dict] = []
        relationships: List[Dict] = []
        table_type_refs: Dict[str, str] = {}

        # Parse TYPES: BEGIN OF ... END OF blocks
        for m in _RE_TYPES_BEGIN.finditer(upper):
            struct_name = m.group(1).strip()
            body = m.group(2)
            columns, fks = self._parse_structure_body(body)
            if columns:
                tables.append({
                    'name': struct_name,
                    'class_name': struct_name,
                    'columns': columns,
                    'foreign_keys': fks,
                    'indexes': [],
                    'file_path': file_path,
                    'line_number': line_number_at(content, m.start()),
                    'source_type': 'TYPES',
                })
                for fk in fks:
                    relationships.append({
                        'from': struct_name,
                        'to': fk['references_table'],
                        'type': 'many-to-one',
                    })

        # Parse DATA: BEGIN OF ... END OF blocks
        for m in _RE_DATA_BEGIN.finditer(upper):
            struct_name = m.group(1).strip()
            body = m.group(2)
            columns, fks = self._parse_structure_body(body)
            if columns:
                tables.append({
                    'name': struct_name,
                    'class_name': struct_name,
                    'columns': columns,
                    'foreign_keys': fks,
                    'indexes': [],
                    'file_path': file_path,
                    'line_number': line_number_at(content, m.start()),
                    'source_type': 'DATA',
                })
                for fk in fks:
                    relationships.append({
                        'from': struct_name,
                        'to': fk['references_table'],
                        'type': 'many-to-one',
                    })

        # Parse table type declarations
        for m in _RE_TABLE_TYPE.finditer(upper):
            tt_name = m.group(1).strip()
            ref_type = m.group(2).strip()
            table_type_refs[tt_name] = ref_type

        for m in _RE_DATA_TABLE.finditer(upper):
            tt_name = m.group(1).strip()
            ref_type = m.group(2).strip()
            table_type_refs[tt_name] = ref_type

        # Parse CDS views
        cds_tables, cds_rels = self._parse_cds_views(upper, content, file_path)
        tables.extend(cds_tables)
        relationships.extend(cds_rels)

        return tables, relationships, table_type_refs

    def _parse_structure_body(
        self, body: str
    ) -> Tuple[List[Dict], List[Dict]]:
        """Parse field definitions from a structure body block."""
        columns: List[Dict] = []
        foreign_keys: List[Dict] = []
        seen_fields: set = set()

        for m in _RE_FIELD.finditer(body):
            field_name = m.group(1).strip()

            # Skip END keyword that might match
            if field_name in ('END', 'BEGIN'):
                continue

            # Avoid duplicates
            if field_name in seen_fields:
                continue
            seen_fields.add(field_name)

            abap_type = m.group(3).strip()
            paren_len = m.group(2) or m.group(4)  # (length) before or after TYPE
            explicit_len = m.group(5)              # LENGTH n
            decimals = m.group(6)                  # DECIMALS n

            sql_type = self._map_type(abap_type, paren_len, explicit_len, decimals)

            # Detect primary key heuristic: field named MANDT or ending with _ID
            # where it's the first field, or field named *KEY*
            is_pk = field_name == 'MANDT' or (
                field_name.endswith('_ID') and len(columns) == 0
            )

            col = {
                'name': field_name,
                'type': sql_type,
                'nullable': not is_pk,
                'primary_key': is_pk,
                'unique': is_pk,
                'abap_type': abap_type,
            }

            columns.append(col)

            # Detect foreign key patterns
            fk = self._detect_foreign_key(field_name, abap_type)
            if fk:
                foreign_keys.append(fk)

        return columns, foreign_keys

    def _parse_cds_views(
        self, upper_content: str, original_content: str, file_path: str
    ) -> Tuple[List[Dict], List[Dict]]:
        """Parse CDS view definitions."""
        tables: List[Dict] = []
        relationships: List[Dict] = []

        for m in _RE_CDS_VIEW.finditer(upper_content):
            view_name = m.group(1).strip()
            source_table = m.group(2).strip()
            fields_block = m.group(3)

            # Extract SQL view name from annotation if present
            sql_view_name = None
            # Look backwards from the match for @AbapCatalog.sqlViewName
            prefix = upper_content[:m.start()]
            sql_m = _RE_CDS_SQL_VIEW.search(prefix[-500:] if len(prefix) > 500 else prefix)
            if sql_m:
                sql_view_name = sql_m.group(1).strip()

            # Extract label from annotation
            label = None
            label_m = _RE_CDS_LABEL.search(prefix[-500:] if len(prefix) > 500 else prefix)
            if label_m:
                label = label_m.group(1).strip()

            # Parse field list
            columns = self._parse_cds_fields(fields_block)

            tables.append({
                'name': view_name,
                'class_name': view_name,
                'columns': columns,
                'foreign_keys': [],
                'indexes': [],
                'file_path': file_path,
                'line_number': line_number_at(original_content, m.start()),
                'source_type': 'CDS_VIEW',
                'source_table': source_table,
                'sql_view_name': sql_view_name,
                'label': label,
            })

            # CDS view references a source table
            relationships.append({
                'from': view_name,
                'to': source_table,
                'type': 'view-of',
            })

        return tables, relationships

    def _parse_cds_fields(self, fields_block: str) -> List[Dict]:
        """Parse CDS field list from { key field1, field2, ... } block."""
        columns: List[Dict] = []
        # Split by comma, handling KEY prefix
        fields_text = fields_block.strip()
        if not fields_text:
            return columns

        for field_str in fields_text.split(','):
            field_str = field_str.strip()
            if not field_str:
                continue

            is_key = False
            if field_str.startswith('KEY '):
                is_key = True
                field_str = field_str[4:].strip()

            # Handle alias: field AS alias
            parts = field_str.split()
            field_name = parts[0].strip() if parts else ''
            if not field_name or not re.match(r'^\w+$', field_name):
                continue

            columns.append({
                'name': field_name,
                'type': 'VARCHAR',  # CDS types resolved at runtime
                'nullable': not is_key,
                'primary_key': is_key,
                'unique': is_key,
            })

        return columns

    # ------------------------------------------------------------------
    # Type mapping and FK detection
    # ------------------------------------------------------------------

    def _map_type(
        self,
        abap_type: str,
        paren_len: Optional[str],
        explicit_len: Optional[str],
        decimals: Optional[str],
    ) -> str:
        """Map an ABAP type to a SQL type string.

        Handles embedded-length types like CHAR10, CHAR40, NUMC5
        by splitting into base type + length.
        """
        # First, try direct lookup
        base = _ABAP_TYPE_MAP.get(abap_type)

        embedded_len = None
        if base is None:
            # Try to split embedded length: CHAR10 -> CHAR + 10
            em = re.match(r'^([A-Z]+?)(\d+)$', abap_type)
            if em:
                type_prefix = em.group(1)
                embedded_len = em.group(2)
                base = _ABAP_TYPE_MAP.get(type_prefix)
            if base is None:
                base = abap_type  # fallback to raw type name

        length = paren_len or explicit_len or embedded_len

        if base == 'DECIMAL' and length:
            dec = decimals or '0'
            return f'DECIMAL({length},{dec})'
        elif base == 'VARCHAR' and length:
            return f'VARCHAR({length})'
        elif length and base not in ('DATE', 'TIME', 'TIMESTAMP', 'BOOLEAN',
                                      'INTEGER', 'BIGINT', 'SMALLINT', 'FLOAT'):
            return f'{base}({length})'

        return base

    def _detect_foreign_key(
        self, field_name: str, abap_type: str
    ) -> Optional[Dict]:
        """Detect foreign key relationships from field naming conventions."""
        # Check against known ABAP key data elements
        if abap_type in _KNOWN_KEY_FIELDS:
            return {
                'column': field_name,
                'references_table': _KNOWN_KEY_FIELDS[abap_type],
                'references_column': abap_type,
            }

        # Convention: fields ending with _ID likely reference another table
        if field_name.endswith('_ID') and field_name != 'USER_ID':
            # Infer table from field name: DEPT_ID -> depts, CUSTOMER_ID -> customers
            prefix = field_name[:-3].lower()
            if prefix:
                ref_table = prefix + 's'
                return {
                    'column': field_name,
                    'references_table': ref_table,
                    'references_column': 'id',
                }

        return None
