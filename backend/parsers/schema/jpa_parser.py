"""
JPA/Hibernate Schema Parser - Extract entity definitions from Java JPA annotations.

Uses regex-based parsing with brace counting to extract @Entity classes,
@Column definitions, relationship annotations, and table metadata.
"""

import os
import re
from typing import Dict, List, Optional, Tuple

from ..base import (
    BaseSchemaParser,
    extract_block_body,
    find_source_files,
    line_number_at,
    read_file_safe,
    strip_comments,
)

# ---------------------------------------------------------------------------
# Compiled regex patterns
# ---------------------------------------------------------------------------

# Entity class detection: @Entity (optionally followed by @Table) then class declaration
_RE_ENTITY = re.compile(
    r'@Entity\b'
    r'(?P<pre_class>.*?)'
    r'(?:public\s+)?class\s+(?P<class_name>\w+)'
    r'(?:\s+extends\s+\w+)?'
    r'(?:\s+implements\s+[\w,\s]+)?'
    r'\s*\{',
    re.DOTALL,
)

# @Table(name = "xxx") — captures the table name
_RE_TABLE_NAME = re.compile(
    r'@Table\s*\(\s*(?:[^)]*?\bname\s*=\s*"(?P<name>[^"]+)"[^)]*?)\)',
    re.DOTALL,
)

# Field declaration: captures type and field name
# Matches patterns like: private Long id; / private String username; / private List<Post> posts;
_RE_FIELD = re.compile(
    r'(?:private|protected|public)\s+'
    r'(?:(?:static|final|transient|volatile)\s+)*'
    r'(?P<type>[\w<>,\s\?]+?)\s+'
    r'(?P<name>\w+)\s*;',
)

# @Id annotation
_RE_ID = re.compile(r'@Id\b')

# @GeneratedValue annotation with optional strategy
_RE_GENERATED_VALUE = re.compile(
    r'@GeneratedValue\s*(?:\(\s*(?:strategy\s*=\s*'
    r'(?:GenerationType\.)?(?P<strategy>\w+))?\s*\))?',
)

# @Column annotation with attributes
_RE_COLUMN = re.compile(
    r'@Column\s*\((?P<attrs>[^)]*)\)',
    re.DOTALL,
)

# Individual column attributes
_RE_COL_NAME = re.compile(r'\bname\s*=\s*"(?P<val>[^"]+)"')
_RE_COL_NULLABLE = re.compile(r'\bnullable\s*=\s*(?P<val>true|false)', re.IGNORECASE)
_RE_COL_UNIQUE = re.compile(r'\bunique\s*=\s*(?P<val>true|false)', re.IGNORECASE)
_RE_COL_LENGTH = re.compile(r'\blength\s*=\s*(?P<val>\d+)')
_RE_COL_COLDEF = re.compile(r'\bcolumnDefinition\s*=\s*"(?P<val>[^"]+)"')

# Relationship annotations
_RE_MANY_TO_ONE = re.compile(
    r'@ManyToOne\b(?:\s*\((?P<attrs>[^)]*)\))?',
    re.DOTALL,
)
_RE_ONE_TO_MANY = re.compile(
    r'@OneToMany\b(?:\s*\((?P<attrs>[^)]*)\))?',
    re.DOTALL,
)
_RE_ONE_TO_ONE = re.compile(
    r'@OneToOne\b(?:\s*\((?P<attrs>[^)]*)\))?',
    re.DOTALL,
)
_RE_MANY_TO_MANY = re.compile(
    r'@ManyToMany\b(?:\s*\((?P<attrs>[^)]*)\))?',
    re.DOTALL,
)

# @JoinColumn(name = "xxx")
_RE_JOIN_COLUMN = re.compile(
    r'@JoinColumn\s*\((?P<attrs>[^)]*)\)',
    re.DOTALL,
)
_RE_JOIN_COL_NAME = re.compile(r'\bname\s*=\s*"(?P<val>[^"]+)"')
_RE_JOIN_COL_REF = re.compile(r'\breferencedColumnName\s*=\s*"(?P<val>[^"]+)"')
_RE_JOIN_COL_NULLABLE = re.compile(r'\bnullable\s*=\s*(?P<val>true|false)', re.IGNORECASE)

# @JoinTable annotation
_RE_JOIN_TABLE = re.compile(
    r'@JoinTable\s*\((?P<attrs>[^)]*(?:\([^)]*\)[^)]*)*)\)',
    re.DOTALL,
)
_RE_JOIN_TABLE_NAME = re.compile(r'\bname\s*=\s*"(?P<val>[^"]+)"')

# mappedBy inside relationship annotations
_RE_MAPPED_BY = re.compile(r'\bmappedBy\s*=\s*"(?P<val>[^"]+)"')

# @Transient — fields to skip
_RE_TRANSIENT = re.compile(r'@Transient\b')

# ---------------------------------------------------------------------------
# Java type to SQL type mapping
# ---------------------------------------------------------------------------

_JAVA_TO_SQL = {
    'Long': 'BIGINT',
    'long': 'BIGINT',
    'Integer': 'INTEGER',
    'int': 'INTEGER',
    'Short': 'SMALLINT',
    'short': 'SMALLINT',
    'Byte': 'TINYINT',
    'byte': 'TINYINT',
    'Float': 'FLOAT',
    'float': 'FLOAT',
    'Double': 'DOUBLE',
    'double': 'DOUBLE',
    'BigDecimal': 'DECIMAL',
    'String': 'VARCHAR',
    'Boolean': 'BOOLEAN',
    'boolean': 'BOOLEAN',
    'Date': 'DATE',
    'LocalDate': 'DATE',
    'LocalDateTime': 'TIMESTAMP',
    'Instant': 'TIMESTAMP',
    'ZonedDateTime': 'TIMESTAMP',
    'LocalTime': 'TIME',
    'byte[]': 'BLOB',
    'Blob': 'BLOB',
    'Clob': 'CLOB',
    'UUID': 'UUID',
}

# Relationship types as a set for relationship detection
_RELATIONSHIP_ANNOTATIONS = {'ManyToOne', 'OneToMany', 'OneToOne', 'ManyToMany'}


class JPAParser(BaseSchemaParser):
    """Parser for JPA/Hibernate entity definitions in Java source files."""

    FILE_EXTENSIONS = ['.java']

    def parse(self, project_path: str) -> Dict:
        """Parse JPA entities and return standardized schema.

        Args:
            project_path: Root directory of Java project.

        Returns:
            Standardized schema dict with tables and relationships.
        """
        tables: List[Dict] = []
        relationships: List[Dict] = []
        java_files = self.find_files(project_path)

        for file_path in java_files:
            content = read_file_safe(file_path)
            if content is None:
                continue

            try:
                file_tables, file_rels = self._parse_file(content, file_path)
                tables.extend(file_tables)
                relationships.extend(file_rels)
            except Exception:
                continue

        # If no explicit relationships were found, derive from foreign keys
        if not relationships:
            relationships = self._detect_relationships(tables)

        return self.make_schema_result(tables, relationships)

    def _parse_file(self, content: str, file_path: str) -> Tuple[List[Dict], List[Dict]]:
        """Parse a single Java file for JPA entities.

        Returns:
            Tuple of (tables, relationships).
        """
        stripped = strip_comments(content, 'java')
        tables: List[Dict] = []
        relationships: List[Dict] = []

        for match in _RE_ENTITY.finditer(stripped):
            class_name = match.group('class_name')
            class_start = match.start()

            # Use the original (unstripped) content for @Table name extraction
            # because strip_comments replaces string literals with spaces
            original_pre_class = content[class_start:match.end()]
            table_name = self._extract_table_name(original_pre_class, class_name)

            # Extract class body using brace counting
            body, body_start, body_end = extract_block_body(stripped, match.start())
            if body_start == -1:
                continue

            line = line_number_at(content, class_start)

            # Parse fields within the class body
            columns, foreign_keys, field_rels = self._parse_fields(
                body, class_name, table_name, file_path, content, body_start
            )

            tables.append({
                'name': table_name,
                'class_name': class_name,
                'columns': columns,
                'foreign_keys': foreign_keys,
                'indexes': [],
                'file_path': file_path,
                'line_number': line,
            })

            relationships.extend(field_rels)

        return tables, relationships

    @staticmethod
    def _extract_table_name(pre_class_text: str, class_name: str) -> str:
        """Extract table name from @Table annotation or derive from class name."""
        m = _RE_TABLE_NAME.search(pre_class_text)
        if m:
            return m.group('name')
        # Default: lowercase class name
        return class_name.lower()

    def _parse_fields(
        self,
        body: str,
        class_name: str,
        table_name: str,
        file_path: str,
        original_content: str,
        body_offset: int,
    ) -> Tuple[List[Dict], List[Dict], List[Dict]]:
        """Parse fields within an entity class body.

        Returns:
            Tuple of (columns, foreign_keys, relationships).
        """
        columns: List[Dict] = []
        foreign_keys: List[Dict] = []
        relationships: List[Dict] = []

        # Build the original body text (unstripped) at the same offsets
        # so we can extract string-valued annotation attributes
        original_body = original_content[body_offset:body_offset + len(body)]

        for field_match in _RE_FIELD.finditer(body):
            field_name = field_match.group('name')
            java_type = field_match.group('type').strip()
            field_pos = field_match.start()

            # Get annotation block from original content (preserves string literals)
            annotations_text = self._get_annotations_before(original_body, field_pos)

            # Skip @Transient fields
            if _RE_TRANSIENT.search(annotations_text):
                continue

            line = line_number_at(original_content, body_offset + field_pos)

            # Check for relationship annotations
            rel_info = self._parse_relationship(
                annotations_text, java_type, field_name, class_name, table_name
            )

            if rel_info:
                rel_type, rel_data = rel_info
                relationships.append(rel_data)

                # For ManyToOne and OneToOne owning side, also create FK column
                if rel_type in ('ManyToOne', 'OneToOne'):
                    join_col = self._parse_join_column(annotations_text, field_name)
                    if join_col:
                        fk_col_name = join_col['column_name']
                        ref_table = self._type_to_table_name(java_type)
                        ref_column = join_col.get('referenced_column', 'id')
                        nullable = join_col.get('nullable', True)

                        columns.append({
                            'name': fk_col_name,
                            'type': 'BIGINT',
                            'nullable': nullable,
                            'primary_key': False,
                            'unique': rel_type == 'OneToOne',
                            'foreign_key': True,
                            'references': f'{ref_table}.{ref_column}',
                            'line_number': line,
                        })

                        foreign_keys.append({
                            'column': fk_col_name,
                            'references_table': ref_table,
                            'references_column': ref_column,
                        })
                continue

            # Regular column (non-relationship)
            col_info = self._parse_column(
                annotations_text, field_name, java_type, line
            )
            columns.append(col_info)

        return columns, foreign_keys, relationships

    @staticmethod
    def _get_annotations_before(body: str, field_pos: int) -> str:
        """Extract the annotation block preceding a field declaration.

        Scans backward from field_pos to find all @ annotations,
        including multi-line annotation arguments (e.g. @JoinTable with
        nested @JoinColumn lines).
        """
        lines_before = body[:field_pos].split('\n')
        annotation_lines: List[str] = []
        paren_depth = 0

        for line in reversed(lines_before):
            stripped = line.strip()

            # Count parens on this line (scanning backward, so closing
            # parens increase depth, opening parens decrease)
            for ch in reversed(stripped):
                if ch == ')':
                    paren_depth += 1
                elif ch == '(':
                    paren_depth -= 1

            # Include lines that are: annotations, empty, or inside
            # multi-line annotation parentheses
            if stripped.startswith('@') or not stripped or paren_depth > 0:
                annotation_lines.insert(0, line)
            elif paren_depth == 0 and (
                stripped.startswith(')') or
                stripped.endswith(',') or
                stripped.endswith(')')
            ):
                # Continuation or closing line of a multi-line annotation
                annotation_lines.insert(0, line)
            else:
                # If we're not inside parens and line isn't an annotation, stop
                if paren_depth <= 0:
                    break
                annotation_lines.insert(0, line)

        return '\n'.join(annotation_lines)

    def _parse_column(
        self,
        annotations_text: str,
        field_name: str,
        java_type: str,
        line: int,
    ) -> Dict:
        """Parse a regular column field and its @Column annotation."""
        is_id = bool(_RE_ID.search(annotations_text))

        # Defaults
        col_name = field_name
        nullable = not is_id  # IDs are not nullable by default
        unique = is_id
        primary_key = is_id
        length = None
        column_def = None

        # Auto-generation strategy
        generated = None
        gen_match = _RE_GENERATED_VALUE.search(annotations_text)
        if gen_match:
            generated = gen_match.group('strategy') or 'AUTO'

        # Parse @Column attributes
        col_match = _RE_COLUMN.search(annotations_text)
        if col_match:
            attrs = col_match.group('attrs')

            name_m = _RE_COL_NAME.search(attrs)
            if name_m:
                col_name = name_m.group('val')

            nullable_m = _RE_COL_NULLABLE.search(attrs)
            if nullable_m:
                nullable = nullable_m.group('val').lower() == 'true'

            unique_m = _RE_COL_UNIQUE.search(attrs)
            if unique_m:
                unique = unique_m.group('val').lower() == 'true'

            len_m = _RE_COL_LENGTH.search(attrs)
            if len_m:
                length = int(len_m.group('val'))

            coldef_m = _RE_COL_COLDEF.search(attrs)
            if coldef_m:
                column_def = coldef_m.group('val')

        # Map Java type to SQL type
        base_type = self._extract_base_type(java_type)
        sql_type = column_def if column_def else _JAVA_TO_SQL.get(base_type, 'VARCHAR')

        # Append length for VARCHAR
        if sql_type == 'VARCHAR' and length:
            sql_type = f'VARCHAR({length})'

        col: Dict = {
            'name': col_name,
            'type': sql_type,
            'nullable': nullable,
            'primary_key': primary_key,
            'unique': unique,
            'line_number': line,
        }

        if generated:
            col['auto_generated'] = generated

        return col

    def _parse_relationship(
        self,
        annotations_text: str,
        java_type: str,
        field_name: str,
        class_name: str,
        table_name: str,
    ) -> Optional[Tuple[str, Dict]]:
        """Parse relationship annotations on a field.

        Returns:
            Tuple of (relationship_type, relationship_dict) or None.
        """
        target_type = self._extract_generic_type(java_type) or java_type
        target_table = self._type_to_table_name(target_type)

        # Check each relationship type
        m = _RE_MANY_TO_ONE.search(annotations_text)
        if m:
            return 'ManyToOne', {
                'from': table_name,
                'to': target_table,
                'type': 'many-to-one',
                'field': field_name,
                'source_class': class_name,
                'target_class': target_type,
            }

        m = _RE_ONE_TO_MANY.search(annotations_text)
        if m:
            attrs = m.group('attrs') or ''
            mapped_by = None
            mb = _RE_MAPPED_BY.search(attrs)
            if mb:
                mapped_by = mb.group('val')

            return 'OneToMany', {
                'from': table_name,
                'to': target_table,
                'type': 'one-to-many',
                'field': field_name,
                'mapped_by': mapped_by,
                'source_class': class_name,
                'target_class': target_type,
            }

        m = _RE_ONE_TO_ONE.search(annotations_text)
        if m:
            attrs = m.group('attrs') or ''
            mapped_by = None
            mb = _RE_MAPPED_BY.search(attrs)
            if mb:
                mapped_by = mb.group('val')

            return 'OneToOne', {
                'from': table_name,
                'to': target_table,
                'type': 'one-to-one',
                'field': field_name,
                'mapped_by': mapped_by,
                'source_class': class_name,
                'target_class': target_type,
            }

        m = _RE_MANY_TO_MANY.search(annotations_text)
        if m:
            # Check for @JoinTable
            join_table_name = None
            jt_match = _RE_JOIN_TABLE.search(annotations_text)
            if jt_match:
                jt_attrs = jt_match.group('attrs')
                jtn = _RE_JOIN_TABLE_NAME.search(jt_attrs)
                if jtn:
                    join_table_name = jtn.group('val')

            attrs = m.group('attrs') or ''
            mapped_by = None
            mb = _RE_MAPPED_BY.search(attrs)
            if mb:
                mapped_by = mb.group('val')

            return 'ManyToMany', {
                'from': table_name,
                'to': target_table,
                'type': 'many-to-many',
                'field': field_name,
                'join_table': join_table_name,
                'mapped_by': mapped_by,
                'source_class': class_name,
                'target_class': target_type,
            }

        return None

    @staticmethod
    def _parse_join_column(annotations_text: str, field_name: str) -> Optional[Dict]:
        """Parse @JoinColumn annotation for FK column info."""
        m = _RE_JOIN_COLUMN.search(annotations_text)
        if m:
            attrs = m.group('attrs')
            result: Dict = {}

            name_m = _RE_JOIN_COL_NAME.search(attrs)
            result['column_name'] = name_m.group('val') if name_m else f'{field_name}_id'

            ref_m = _RE_JOIN_COL_REF.search(attrs)
            if ref_m:
                result['referenced_column'] = ref_m.group('val')

            nullable_m = _RE_JOIN_COL_NULLABLE.search(attrs)
            if nullable_m:
                result['nullable'] = nullable_m.group('val').lower() == 'true'

            return result

        # No @JoinColumn — derive default column name
        return {'column_name': f'{field_name}_id'}

    @staticmethod
    def _extract_base_type(java_type: str) -> str:
        """Extract the base type from a Java type, stripping generics."""
        # Handle List<Post> -> Post, Map<String,Object> -> Map, etc.
        idx = java_type.find('<')
        if idx != -1:
            return java_type[:idx].strip()
        return java_type.strip()

    @staticmethod
    def _extract_generic_type(java_type: str) -> Optional[str]:
        """Extract the generic parameter from types like List<Post> or Set<User>."""
        m = re.search(r'<\s*(\w+)\s*>', java_type)
        return m.group(1) if m else None

    @staticmethod
    def _type_to_table_name(class_name: str) -> str:
        """Convert a Java class name to a presumed table name.

        Uses lowercase of the class name as a simple heuristic.
        E.g., 'Department' -> 'department', 'Post' -> 'post'.
        """
        # Simple: camelCase to snake_case, then lower
        # Insert underscore before uppercase letters, then lowercase
        s1 = re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1_\2', class_name)
        s2 = re.sub(r'([a-z\d])([A-Z])', r'\1_\2', s1)
        return s2.lower()
