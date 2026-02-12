"""
Entity Framework Schema Parser - Extract database schema from C# EF models.

Uses regex-based parsing with brace counting to handle both Data Annotations
style (attributes on properties) and Fluent API style (OnModelCreating).
"""

import re
from typing import Dict, List, Optional, Tuple

from ..base import (
    BaseSchemaParser, read_file_safe,
    strip_comments, extract_block_body,
)

# ---------------------------------------------------------------------------
# C# type to SQL type mapping
# ---------------------------------------------------------------------------

_CSHARP_TYPE_MAP = {
    'int': 'INTEGER',
    'long': 'BIGINT',
    'short': 'SMALLINT',
    'byte': 'TINYINT',
    'decimal': 'DECIMAL',
    'float': 'FLOAT',
    'double': 'DOUBLE',
    'bool': 'BOOLEAN',
    'string': 'VARCHAR',
    'char': 'CHAR',
    'DateTime': 'DATETIME',
    'DateTimeOffset': 'DATETIMEOFFSET',
    'TimeSpan': 'TIME',
    'Guid': 'UNIQUEIDENTIFIER',
    'byte[]': 'BLOB',
    'Int32': 'INTEGER',
    'Int64': 'BIGINT',
    'Int16': 'SMALLINT',
    'Boolean': 'BOOLEAN',
    'String': 'VARCHAR',
    'Single': 'FLOAT',
    'Double': 'DOUBLE',
    'Decimal': 'DECIMAL',
}

# ---------------------------------------------------------------------------
# Compiled regex patterns — Data Annotations
# ---------------------------------------------------------------------------

# Class declaration: public class User { ... } or public class User : BaseEntity { ... }
_RE_CLASS = re.compile(
    r'(?:(?:\[[\w\s,(")\[\].=]+?\]\s*)*)'   # optional attributes before class
    r'(?:public\s+)?class\s+(\w+)'            # class name
    r'(?:\s*:\s*([\w\s,<>]+?))?'               # optional base classes/interfaces
    r'\s*\{',
    re.DOTALL,
)

# [Table("name")] attribute
_RE_TABLE_ATTR = re.compile(r'\[Table\(\s*"([^"]+)"\s*\)\]')

# [Key] attribute
_RE_KEY_ATTR = re.compile(r'\[Key\]')

# [Column("name")] attribute
_RE_COLUMN_ATTR = re.compile(r'\[Column\(\s*"([^"]+)"\s*\)\]')

# [Required] attribute
_RE_REQUIRED_ATTR = re.compile(r'\[Required\]')

# [StringLength(n)] attribute
_RE_STRING_LENGTH_ATTR = re.compile(r'\[StringLength\(\s*(\d+)\s*\)\]')

# [MaxLength(n)] attribute
_RE_MAX_LENGTH_ATTR = re.compile(r'\[MaxLength\(\s*(\d+)\s*\)\]')

# [ForeignKey("nav")] attribute
_RE_FOREIGN_KEY_ATTR = re.compile(r'\[ForeignKey\(\s*"([^"]+)"\s*\)\]')

# [NotMapped] attribute
_RE_NOT_MAPPED_ATTR = re.compile(r'\[NotMapped\]')

# [DatabaseGenerated(...)] attribute
_RE_DB_GENERATED_ATTR = re.compile(r'\[DatabaseGenerated\(\s*(\w+(?:\.\w+)?)\s*\)\]')

# Auto-property: public Type Name { get; set; }
# Handles nullable types (Type?), generic types (ICollection<T>), etc.
_RE_PROPERTY = re.compile(
    r'public\s+'
    r'(?:virtual\s+)?'
    r'([\w<>\[\]?,\s]+?)\s+'    # type (including generics and nullable)
    r'(\w+)\s*'                  # property name
    r'\{\s*get\s*;\s*set\s*;\s*\}',
)

# Collection navigation property types
_RE_COLLECTION_TYPE = re.compile(
    r'(?:ICollection|IList|List|IEnumerable|ISet|HashSet)<(\w+)>'
)

# Nullable type: int?, bool?, DateTime?
_RE_NULLABLE_TYPE = re.compile(r'^(\w+)\?$')

# ---------------------------------------------------------------------------
# Compiled regex patterns — DbContext / Fluent API
# ---------------------------------------------------------------------------

# DbSet<T> property: public DbSet<User> Users { get; set; }
_RE_DBSET = re.compile(
    r'public\s+DbSet<(\w+)>\s+(\w+)\s*\{\s*get\s*;\s*set\s*;\s*\}'
)

# DbContext class: public class AppDbContext : DbContext
_RE_DBCONTEXT_CLASS = re.compile(
    r'(?:public\s+)?class\s+(\w+)\s*:\s*(?:\w+,\s*)*DbContext(?:\s*,\s*\w+)*\s*\{'
)

# OnModelCreating method
_RE_ON_MODEL_CREATING = re.compile(
    r'(?:protected\s+)?override\s+void\s+OnModelCreating\s*\('
)

# Fluent API: modelBuilder.Entity<T>()
_RE_FLUENT_ENTITY = re.compile(
    r'modelBuilder\s*\.\s*Entity<(\w+)>\s*\(\s*\)'
)

# .ToTable("name")
_RE_FLUENT_TO_TABLE = re.compile(
    r'\.ToTable\(\s*"([^"]+)"\s*\)'
)

# .HasKey(e => e.Prop) or .HasKey(e => new { e.Prop1, e.Prop2 })
_RE_FLUENT_HAS_KEY = re.compile(
    r'\.HasKey\(\s*\w+\s*=>\s*(?:\w+\.(\w+)|new\s*\{([^}]+)\})\s*\)'
)

# .Property(e => e.Name)
_RE_FLUENT_PROPERTY = re.compile(
    r'\.Property\(\s*\w+\s*=>\s*\w+\.(\w+)\s*\)'
)

# .HasMaxLength(n)
_RE_FLUENT_MAX_LENGTH = re.compile(r'\.HasMaxLength\(\s*(\d+)\s*\)')

# .IsRequired()
_RE_FLUENT_IS_REQUIRED = re.compile(r'\.IsRequired\(\s*\)')

# .HasColumnName("name")
_RE_FLUENT_COLUMN_NAME = re.compile(r'\.HasColumnName\(\s*"([^"]+)"\s*\)')

# .HasColumnType("type")
_RE_FLUENT_COLUMN_TYPE = re.compile(r'\.HasColumnType\(\s*"([^"]+)"\s*\)')

# .HasMany(e => e.Nav)
_RE_FLUENT_HAS_MANY = re.compile(
    r'\.HasMany\(\s*\w+\s*=>\s*\w+\.(\w+)\s*\)'
)

# .HasOne(e => e.Nav)
_RE_FLUENT_HAS_ONE = re.compile(
    r'\.HasOne\(\s*\w+\s*=>\s*\w+\.(\w+)\s*\)'
)

# .WithOne(e => e.Nav)
_RE_FLUENT_WITH_ONE = re.compile(
    r'\.WithOne\(\s*\w+\s*=>\s*\w+\.(\w+)\s*\)'
)

# .WithMany(e => e.Nav)
_RE_FLUENT_WITH_MANY = re.compile(
    r'\.WithMany\(\s*(?:\w+\s*=>\s*\w+\.(\w+))?\s*\)'
)

# .HasForeignKey(e => e.Prop)
_RE_FLUENT_HAS_FK = re.compile(
    r'\.HasForeignKey\(\s*\w+\s*=>\s*\w+\.(\w+)\s*\)'
)


class EntityFrameworkParser(BaseSchemaParser):
    """Parse C# Entity Framework models into standardized schema format.

    Supports both Data Annotations and Fluent API configurations:
    - Data Annotations: [Table], [Key], [Column], [Required], [ForeignKey],
      [StringLength], [MaxLength], [NotMapped], [DatabaseGenerated]
    - Fluent API: OnModelCreating with modelBuilder.Entity<T>() chains
    - DbContext: DbSet<T> declarations for entity-table mappings
    """

    FILE_EXTENSIONS = ['.cs']

    def parse(self, project_path: str) -> Dict:
        """Parse all .cs files in project_path and return schema dict."""
        files = self.find_files(project_path)

        # Phase 1: Parse all entity classes with data annotations
        entity_map: Dict[str, Dict] = {}   # class_name -> table dict
        nav_properties: Dict[str, List[Dict]] = {}  # class_name -> nav props

        # Phase 2 data: DbContext info
        dbset_mappings: Dict[str, str] = {}  # entity_name -> dbset_name
        fluent_configs: List[Dict] = []
        fluent_relationships: List[Dict] = []

        for fpath in files:
            content = read_file_safe(fpath)
            if not content:
                continue

            raw_content = content
            content = strip_comments(content, 'csharp')

            try:
                # Check for DbContext
                ctx_match = _RE_DBCONTEXT_CLASS.search(content)
                if ctx_match:
                    mappings, configs, rels = self._parse_dbcontext(
                        content, ctx_match, fpath
                    )
                    dbset_mappings.update(mappings)
                    fluent_configs.extend(configs)
                    fluent_relationships.extend(rels)

                # Parse entity classes (pass raw_content for attribute strings)
                entities, navs = self._parse_entity_classes(
                    content, raw_content, fpath
                )
                for name, table in entities.items():
                    if name in entity_map:
                        # Merge — later file doesn't overwrite
                        existing = entity_map[name]
                        for col in table['columns']:
                            if not any(c['name'] == col['name']
                                       for c in existing['columns']):
                                existing['columns'].append(col)
                    else:
                        entity_map[name] = table

                for name, props in navs.items():
                    nav_properties.setdefault(name, []).extend(props)

            except Exception:
                continue

        # Phase 3: Apply Fluent API configs on top of data annotation results
        self._apply_fluent_configs(entity_map, fluent_configs)

        # Phase 4: Apply DbSet mappings — set table names from DbSet property
        #          names where no explicit [Table] was given
        for entity_name, dbset_name in dbset_mappings.items():
            if entity_name in entity_map:
                table = entity_map[entity_name]
                # Only override if table name is still the class name
                # (i.e., no [Table("...")] or .ToTable("...") was specified)
                if table['name'] == entity_name:
                    table['name'] = dbset_name

        # Phase 5: Resolve fluent API relationship targets using nav property info
        self._resolve_fluent_relationships(
            fluent_relationships, entity_map, nav_properties
        )

        # Phase 6: Resolve nav-based FK references
        self._resolve_nav_fks(entity_map, nav_properties)

        # Phase 7: Collect all relationships, deduplicating by (from, to, type)
        all_relationships: List[Dict] = []
        seen_rels: set = set()

        def _add_rel(rel: Dict) -> None:
            key = (rel.get('from', ''), rel.get('to', ''), rel.get('type', ''))
            if key not in seen_rels:
                seen_rels.add(key)
                all_relationships.append(rel)

        # Fluent API relationships (highest priority)
        for r in fluent_relationships:
            _add_rel(r)

        # Navigation property relationships
        for r in self._detect_nav_relationships(entity_map, nav_properties):
            _add_rel(r)

        tables = list(entity_map.values())

        # Implicit relationships from foreign key columns
        for r in self._detect_relationships(tables):
            _add_rel(r)

        return self.make_schema_result(tables, all_relationships)

    # ------------------------------------------------------------------
    # Entity class parsing (Data Annotations)
    # ------------------------------------------------------------------

    def _parse_entity_classes(
        self, content: str, raw_content: str, file_path: str
    ) -> Tuple[Dict[str, Dict], Dict[str, List[Dict]]]:
        """Parse entity classes from a C# file.

        Args:
            content: Comment-stripped source (for structural matching).
            raw_content: Original source (for attribute string arguments).
            file_path: Path to the source file.

        Returns (entity_map, nav_properties) where entity_map is
        class_name -> table dict and nav_properties is class_name -> list of
        navigation property dicts.
        """
        entity_map: Dict[str, Dict] = {}
        nav_properties: Dict[str, List[Dict]] = {}

        for class_match in _RE_CLASS.finditer(content):
            class_name = class_match.group(1)
            base_classes = class_match.group(2) or ''

            # Skip DbContext classes — handled separately
            if 'DbContext' in base_classes:
                continue

            class_start = class_match.start()
            body, body_start, body_end = extract_block_body(content, class_start)
            if body_start == -1:
                continue

            # Extract raw body at same positions (for attribute string args)
            raw_body = raw_content[body_start:body_end]

            # Look for [Table("name")] before the class declaration
            # Use raw_content so the string literal is intact
            preceding_raw = raw_content[max(0, class_start - 500):class_start]
            table_match = _RE_TABLE_ATTR.search(preceding_raw)
            table_name = table_match.group(1) if table_match else class_name

            # Parse properties from class body
            columns, foreign_keys, navs = self._parse_properties(
                body, raw_body, class_name, file_path
            )

            if not columns and not navs:
                # Not an entity class (no properties found)
                continue

            entity_map[class_name] = {
                'name': table_name,
                'model_name': class_name,
                'columns': columns,
                'foreign_keys': foreign_keys,
                'indexes': [],
                'file_path': file_path,
            }
            if navs:
                nav_properties[class_name] = navs

        return entity_map, nav_properties

    def _parse_properties(
        self, body: str, raw_body: str, class_name: str, file_path: str
    ) -> Tuple[List[Dict], List[Dict], List[Dict]]:
        """Parse properties from a class body.

        Args:
            body: Comment-stripped class body (for structural matching).
            raw_body: Original class body (for attribute string arguments).
            class_name: Name of the enclosing class.
            file_path: Path to the source file.

        Returns (columns, foreign_keys, navigation_properties).
        """
        columns: List[Dict] = []
        foreign_keys: List[Dict] = []
        nav_properties: List[Dict] = []

        # Track previous property end to limit backward attribute search
        prev_end = 0

        # Split body into segments: each property preceded by its attributes
        # We process each property match and look backward for attributes
        for prop_match in _RE_PROPERTY.finditer(body):
            prop_type = prop_match.group(1).strip()
            prop_name = prop_match.group(2)

            # Get the text preceding this property (attributes) — only
            # text between the previous property's end and this one's start,
            # so we don't accidentally pick up attributes from prior properties.
            # Use raw_body for attribute text so string literals in annotations
            # (e.g. [Column("name")], [ForeignKey("nav")]) remain intact.
            raw_preceding = raw_body[prev_end:prop_match.start()]
            # Also get stripped preceding for non-string attrs ([Key], [Required])
            preceding = body[prev_end:prop_match.start()]
            prev_end = prop_match.end()

            # Check for [NotMapped] (no string args, stripped is fine)
            if _RE_NOT_MAPPED_ATTR.search(preceding):
                continue

            # Check if this is a navigation property (collection or entity ref)
            collection_match = _RE_COLLECTION_TYPE.search(prop_type)
            if collection_match:
                nav_properties.append({
                    'name': prop_name,
                    'target_type': collection_match.group(1),
                    'relationship': 'one-to-many',
                })
                continue

            # Check if this is a single navigation property (reference to another entity)
            # Heuristic: type starts with uppercase and isn't a known C# type
            base_type = _RE_NULLABLE_TYPE.match(prop_type)
            clean_type = base_type.group(1) if base_type else prop_type
            if (clean_type[0:1].isupper() and
                    clean_type not in _CSHARP_TYPE_MAP and
                    clean_type not in ('DateTime', 'DateTimeOffset', 'TimeSpan',
                                       'Guid', 'String', 'Boolean', 'Int32',
                                       'Int64', 'Int16', 'Single', 'Double',
                                       'Decimal', 'Byte')):
                nav_properties.append({
                    'name': prop_name,
                    'target_type': clean_type,
                    'relationship': 'many-to-one',
                })
                # Check if there's a [ForeignKey] on this nav property
                fk_match = _RE_FOREIGN_KEY_ATTR.search(raw_preceding)
                if fk_match:
                    fk_column = fk_match.group(1)
                    foreign_keys.append({
                        'column': fk_column,
                        'references_table': clean_type,
                        'references_column': 'Id',
                    })
                continue

            # This is a regular data property — build column info
            # Use stripped preceding for simple attrs, raw for string-valued attrs
            is_key = bool(_RE_KEY_ATTR.search(preceding))
            is_required = bool(_RE_REQUIRED_ATTR.search(preceding))
            column_name_match = _RE_COLUMN_ATTR.search(raw_preceding)
            str_len_match = _RE_STRING_LENGTH_ATTR.search(raw_preceding)
            max_len_match = _RE_MAX_LENGTH_ATTR.search(raw_preceding)
            fk_match = _RE_FOREIGN_KEY_ATTR.search(raw_preceding)
            db_gen_match = _RE_DB_GENERATED_ATTR.search(raw_preceding)

            # Determine nullability: nullable types (int?) are nullable,
            # reference types (string, byte[]) are nullable by default,
            # value types (int, bool, DateTime) are non-nullable by default
            is_nullable_type = prop_type.endswith('?')
            is_reference_type = clean_type in ('string', 'String', 'byte[]')
            is_nullable = (is_nullable_type or is_reference_type) and not is_required

            # Convention: property named "Id" or "<ClassName>Id" is primary key
            if prop_name == 'Id' or prop_name == f'{class_name}Id':
                is_key = True

            # Map type
            sql_type = self._map_csharp_type(clean_type)

            # Apply string length
            max_length = None
            if str_len_match:
                max_length = int(str_len_match.group(1))
            elif max_len_match:
                max_length = int(max_len_match.group(1))

            if max_length and sql_type == 'VARCHAR':
                sql_type = f'VARCHAR({max_length})'

            column = {
                'name': column_name_match.group(1) if column_name_match else prop_name,
                'type': sql_type,
                'nullable': is_nullable if not is_key else False,
                'primary_key': is_key,
                'unique': is_key,
                'property_name': prop_name,
            }

            if max_length:
                column['max_length'] = max_length
            if is_required:
                column['nullable'] = False
            if db_gen_match:
                column['database_generated'] = db_gen_match.group(1)

            columns.append(column)

            # Check for [ForeignKey] on a data property (FK column)
            if fk_match:
                nav_name = fk_match.group(1)
                # The nav_name refers to the navigation property;
                # we'll resolve the target table later
                foreign_keys.append({
                    'column': prop_name,
                    'references_table': nav_name,
                    'references_column': 'Id',
                    '_is_nav_ref': True,
                })

        return columns, foreign_keys, nav_properties

    # ------------------------------------------------------------------
    # DbContext parsing
    # ------------------------------------------------------------------

    def _parse_dbcontext(
        self, content: str, ctx_match: re.Match, file_path: str
    ) -> Tuple[Dict[str, str], List[Dict], List[Dict]]:
        """Parse a DbContext class for DbSet mappings and Fluent API configs.

        Returns (dbset_mappings, fluent_configs, fluent_relationships).
        """
        dbset_mappings: Dict[str, str] = {}
        fluent_configs: List[Dict] = []
        fluent_relationships: List[Dict] = []

        ctx_start = ctx_match.start()
        body, body_start, body_end = extract_block_body(content, ctx_start)
        if body_start == -1:
            return dbset_mappings, fluent_configs, fluent_relationships

        # Extract DbSet<T> declarations
        for dbset_match in _RE_DBSET.finditer(body):
            entity_name = dbset_match.group(1)
            dbset_name = dbset_match.group(2)
            dbset_mappings[entity_name] = dbset_name

        # Find OnModelCreating method
        omc_match = _RE_ON_MODEL_CREATING.search(body)
        if omc_match:
            omc_body, omc_start, omc_end = extract_block_body(
                body, omc_match.start()
            )
            if omc_start != -1:
                configs, rels = self._parse_fluent_api(omc_body)
                fluent_configs.extend(configs)
                fluent_relationships.extend(rels)

        return dbset_mappings, fluent_configs, fluent_relationships

    # ------------------------------------------------------------------
    # Fluent API parsing
    # ------------------------------------------------------------------

    def _parse_fluent_api(
        self, omc_body: str
    ) -> Tuple[List[Dict], List[Dict]]:
        """Parse modelBuilder.Entity<T>() chains from OnModelCreating body.

        Returns (fluent_configs, fluent_relationships).
        """
        configs: List[Dict] = []
        relationships: List[Dict] = []

        # Split on statement boundaries (semicolons) for cleaner parsing
        statements = omc_body.split(';')

        for stmt in statements:
            stmt = stmt.strip()
            if not stmt:
                continue

            # Find which entity this statement configures
            entity_match = _RE_FLUENT_ENTITY.search(stmt)
            if not entity_match:
                continue

            entity_name = entity_match.group(1)

            config: Dict = {'entity': entity_name}

            # .ToTable("name")
            table_match = _RE_FLUENT_TO_TABLE.search(stmt)
            if table_match:
                config['table_name'] = table_match.group(1)

            # .HasKey(...)
            key_match = _RE_FLUENT_HAS_KEY.search(stmt)
            if key_match:
                if key_match.group(1):
                    config['key_columns'] = [key_match.group(1)]
                elif key_match.group(2):
                    # Composite key: new { e.Col1, e.Col2 }
                    parts = key_match.group(2)
                    config['key_columns'] = [
                        p.strip().split('.')[-1]
                        for p in parts.split(',')
                        if p.strip()
                    ]

            # .Property(e => e.Name) chain
            prop_match = _RE_FLUENT_PROPERTY.search(stmt)
            if prop_match:
                prop_name = prop_match.group(1)
                prop_config: Dict = {'property': prop_name}

                length_match = _RE_FLUENT_MAX_LENGTH.search(stmt)
                if length_match:
                    prop_config['max_length'] = int(length_match.group(1))

                required_match = _RE_FLUENT_IS_REQUIRED.search(stmt)
                if required_match:
                    prop_config['required'] = True

                col_name_match = _RE_FLUENT_COLUMN_NAME.search(stmt)
                if col_name_match:
                    prop_config['column_name'] = col_name_match.group(1)

                col_type_match = _RE_FLUENT_COLUMN_TYPE.search(stmt)
                if col_type_match:
                    prop_config['column_type'] = col_type_match.group(1)

                config['property_config'] = prop_config

            # Relationship: .HasMany / .HasOne / .WithOne / .WithMany
            has_many_match = _RE_FLUENT_HAS_MANY.search(stmt)
            has_one_match = _RE_FLUENT_HAS_ONE.search(stmt)
            with_one_match = _RE_FLUENT_WITH_ONE.search(stmt)
            with_many_match = _RE_FLUENT_WITH_MANY.search(stmt)
            fk_match = _RE_FLUENT_HAS_FK.search(stmt)

            if has_many_match:
                nav_name = has_many_match.group(1)
                rel: Dict = {
                    'from': entity_name,
                    'to': nav_name,  # nav prop name; resolved later
                    'type': 'one-to-many',
                    'field': nav_name,
                    '_needs_resolve': True,
                }
                if with_one_match:
                    rel['inverse_field'] = with_one_match.group(1)
                if fk_match:
                    rel['foreign_key'] = fk_match.group(1)
                relationships.append(rel)

            elif has_one_match:
                nav_name = has_one_match.group(1)
                rel = {
                    'from': entity_name,
                    'to': nav_name,  # nav prop name; resolved later
                    'type': 'one-to-one' if with_one_match else 'many-to-one',
                    'field': nav_name,
                    '_needs_resolve': True,
                }
                if with_many_match:
                    rel['type'] = 'many-to-one'
                    if with_many_match.group(1):
                        rel['inverse_field'] = with_many_match.group(1)
                if fk_match:
                    rel['foreign_key'] = fk_match.group(1)
                relationships.append(rel)

            configs.append(config)

        return configs, relationships

    # ------------------------------------------------------------------
    # Apply Fluent API configurations
    # ------------------------------------------------------------------

    def _apply_fluent_configs(
        self, entity_map: Dict[str, Dict], configs: List[Dict]
    ) -> None:
        """Apply Fluent API configurations to entity table definitions."""
        for config in configs:
            entity_name = config.get('entity')
            if entity_name not in entity_map:
                continue

            table = entity_map[entity_name]

            # Apply table name
            if 'table_name' in config:
                table['name'] = config['table_name']

            # Apply key columns
            if 'key_columns' in config:
                for col in table['columns']:
                    prop_name = col.get('property_name', col['name'])
                    if prop_name in config['key_columns']:
                        col['primary_key'] = True
                        col['nullable'] = False
                        col['unique'] = True

            # Apply property config
            if 'property_config' in config:
                pc = config['property_config']
                prop_name = pc['property']
                for col in table['columns']:
                    if col.get('property_name', col['name']) == prop_name:
                        if 'max_length' in pc:
                            col['max_length'] = pc['max_length']
                            if col['type'] == 'VARCHAR':
                                col['type'] = f"VARCHAR({pc['max_length']})"
                        if pc.get('required'):
                            col['nullable'] = False
                        if 'column_name' in pc:
                            col['name'] = pc['column_name']
                        if 'column_type' in pc:
                            col['type'] = pc['column_type'].upper()
                        break

    # ------------------------------------------------------------------
    # Resolve fluent API relationship targets
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_fluent_relationships(
        fluent_rels: List[Dict],
        entity_map: Dict[str, Dict],
        nav_properties: Dict[str, List[Dict]],
    ) -> None:
        """Resolve 'to' field in fluent relationships using nav property types.

        Fluent API .HasMany(u => u.Posts) stores field='Posts' but needs
        to='Post' (the target entity type). Look up the nav property type
        from the entity's parsed navigation properties.
        """
        for rel in fluent_rels:
            if not rel.get('_needs_resolve'):
                continue

            entity_name = rel['from']
            nav_name = rel['field']

            # Look up navigation property type
            navs = nav_properties.get(entity_name, [])
            for nav in navs:
                if nav['name'] == nav_name:
                    target_type = nav['target_type']
                    # Resolve to table name if entity is known
                    if target_type in entity_map:
                        rel['to'] = entity_map[target_type]['name']
                    else:
                        rel['to'] = target_type
                    break
            else:
                # Nav property not found in parsed entities; keep field name
                # as best guess (already set as placeholder)
                pass

            # Convert 'from' entity class name to table name
            if entity_name in entity_map:
                rel['from'] = entity_map[entity_name]['name']

            # Clean up internal flag
            rel.pop('_needs_resolve', None)

    # ------------------------------------------------------------------
    # Relationship detection from navigation properties
    # ------------------------------------------------------------------

    def _detect_nav_relationships(
        self, entity_map: Dict[str, Dict],
        nav_properties: Dict[str, List[Dict]]
    ) -> List[Dict]:
        """Detect relationships from navigation property metadata."""
        relationships: List[Dict] = []
        seen = set()

        for class_name, navs in nav_properties.items():
            if class_name not in entity_map:
                continue
            table_name = entity_map[class_name]['name']

            for nav in navs:
                target_type = nav['target_type']
                target_table = (entity_map[target_type]['name']
                                if target_type in entity_map
                                else target_type)
                rel_type = nav['relationship']

                pair = (table_name, target_table, rel_type)
                if pair not in seen:
                    seen.add(pair)
                    relationships.append({
                        'from': table_name,
                        'to': target_table,
                        'type': rel_type,
                        'field': nav['name'],
                    })

        return relationships

    # ------------------------------------------------------------------
    # Resolve navigation-based foreign keys
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_nav_fks(
        entity_map: Dict[str, Dict],
        nav_properties: Dict[str, List[Dict]]
    ) -> None:
        """Resolve [ForeignKey("NavProp")] references to actual table names."""
        for class_name, table in entity_map.items():
            navs = {n['name']: n for n in nav_properties.get(class_name, [])}
            for fk in table['foreign_keys']:
                if fk.get('_is_nav_ref'):
                    nav_name = fk['references_table']
                    if nav_name in navs:
                        fk['references_table'] = navs[nav_name]['target_type']
                    del fk['_is_nav_ref']

    # ------------------------------------------------------------------
    # Type mapping
    # ------------------------------------------------------------------

    @staticmethod
    def _map_csharp_type(csharp_type: str) -> str:
        """Map a C# type name to a SQL type."""
        # Strip Nullable<T> wrapper
        if csharp_type.startswith('Nullable<') and csharp_type.endswith('>'):
            csharp_type = csharp_type[9:-1]
        return _CSHARP_TYPE_MAP.get(csharp_type, 'VARCHAR')
