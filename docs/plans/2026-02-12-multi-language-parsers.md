# Multi-Language Parser Support

**Date:** February 12, 2026
**Project:** Visual Backend Code Analyzer
**Status:** In Progress

## Context

The Code Visualizer currently only parses **Python** projects (SQLAlchemy for schema, Python AST for runtime flow, Flask for API routes). Users importing projects in any other language get "Unsupported framework" errors. This plan adds parsers for the most commonly used backend languages plus ABAP (SAP), making the tool useful across the industry. Zero new dependencies — all parsing is pure Python regex/AST.

---

## Scope: 27 New Parsers

### Database Schema (11 new)
| Parser | Language | Framework | Parsing Strategy |
|--------|----------|-----------|-----------------|
| `django_parser.py` | Python | Django ORM | Python AST (`models.Model`, `CharField`, `ForeignKey`) |
| `prisma_parser.py` | JS/TS | Prisma | Line-by-line DSL parser (`.prisma` files) |
| `typeorm_parser.py` | TypeScript | TypeORM | Regex (`@Entity`, `@Column`, `@ManyToOne`) |
| `sequelize_parser.py` | JavaScript | Sequelize | Regex (`define()`, `DataTypes`) |
| `jpa_parser.py` | Java | JPA/Hibernate | Regex (`@Entity`, `@Table`, `@Column`, `@Id`) |
| `ef_parser.py` | C# | Entity Framework | Regex (`[Table]`, `[Key]`, `DbSet<T>`, Fluent API) |
| `activerecord_parser.py` | Ruby | Rails | Regex (migrations + model associations) |
| `gorm_parser.py` | Go | GORM | Regex (struct tags `gorm:"..."`) |
| `eloquent_parser.py` | PHP | Laravel | Regex (`$table`, `$fillable`, `hasMany()`) |
| `abap_dict_parser.py` | ABAP | Dictionary | Regex (`TYPES: BEGIN OF`, `DATA:`, table defs) |
| `mongoose_parser.py` | JS/TS | Mongoose | Regex (`new Schema({`, `mongoose.model()`) |

### Runtime Flow (3 new)
| Parser | Language | Parsing Strategy |
|--------|----------|-----------------|
| `js_flow_parser.py` | JS/TS | Regex (`function`, `=>`, `async`, `class` methods) |
| `java_flow_parser.py` | Java | Regex (method declarations, calls, control flow) |
| `abap_flow_parser.py` | ABAP | Regex (`FORM/PERFORM`, `METHOD/CALL METHOD`, `FUNCTION MODULE`) |

### API Routes (9 new)
| Parser | Language | Framework | Parsing Strategy |
|--------|----------|-----------|-----------------|
| `django_routes_parser.py` | Python | Django | Python AST (`path()`, `include()`, ViewSets) |
| `fastapi_parser.py` | Python | FastAPI | Python AST (`@app.get()`, `@router.post()`) |
| `express_parser.py` | JS/TS | Express | Regex (`app.get()`, `router.post()`, `app.use()`) |
| `nestjs_parser.py` | TypeScript | NestJS | Regex (`@Controller`, `@Get()`, `@Post()`) |
| `spring_parser.py` | Java | Spring Boot | Regex (`@RestController`, `@GetMapping`) |
| `aspnet_parser.py` | C# | ASP.NET | Regex (`[ApiController]`, `[HttpGet]`, `[Route]`) |
| `rails_routes_parser.py` | Ruby | Rails | Regex (`resources`, `get '/'`, route DSL) |
| `laravel_parser.py` | PHP | Laravel | Regex (`Route::get()`, `Route::resource()`) |
| `gin_parser.py` | Go | Gin/Echo | Regex (`r.GET()`, `e.POST()`, `Group()`) |

### ABAP ICF/OData (counted in routes above)
| Parser | Language | Framework | Parsing Strategy |
|--------|----------|-----------|-----------------|
| `abap_icf_parser.py` | ABAP | ICF/OData | Regex (ICF service defs, OData metadata, CDS views) |

---

## Architecture Changes

### New Directory Structure
```
backend/parsers/
    __init__.py                    # Updated: re-exports for backward compat
    parser_manager.py              # Updated: multi-language detection + routing
    base.py                        # NEW: BaseSchemaParser, BaseFlowParser, BaseRoutesParser

    schema/
        __init__.py
        sqlalchemy_parser.py       # MOVED (re-exported from old path)
        sqlite_parser.py           # MOVED (re-exported from old path)
        django_parser.py           # NEW
        prisma_parser.py           # NEW
        typeorm_parser.py          # NEW
        sequelize_parser.py        # NEW
        jpa_parser.py              # NEW
        ef_parser.py               # NEW
        activerecord_parser.py     # NEW
        gorm_parser.py             # NEW
        eloquent_parser.py         # NEW
        mongoose_parser.py         # NEW
        abap_dict_parser.py        # NEW

    flow/
        __init__.py
        python_flow_parser.py      # MOVED from runtime_flow_parser.py
        js_flow_parser.py          # NEW
        java_flow_parser.py        # NEW
        abap_flow_parser.py        # NEW

    routes/
        __init__.py
        flask_parser.py            # MOVED from flask_routes_parser.py
        django_routes_parser.py    # NEW
        fastapi_parser.py          # NEW
        express_parser.py          # NEW
        nestjs_parser.py           # NEW
        spring_parser.py           # NEW
        aspnet_parser.py           # NEW
        rails_routes_parser.py     # NEW
        laravel_parser.py          # NEW
        gin_parser.py              # NEW
        abap_icf_parser.py         # NEW
```

### Base Classes (`backend/parsers/base.py`)

```python
class BaseSchemaParser:
    FILE_EXTENSIONS = []
    SKIP_DIRS = {'__pycache__', '.git', '.venv', 'venv', 'node_modules', ...}

    def parse(self, project_path: str) -> dict: ...
    def find_files(self, project_path, extensions=None) -> list: ...
    def make_schema_result(self, tables, relationships=None) -> dict: ...
    def _detect_relationships(self, tables) -> list: ...  # FK-based

class BaseFlowParser:
    FILE_EXTENSIONS = []
    SKIP_DIRS = {...}

    def __init__(self, project_path, options=None): ...
    def parse(self) -> dict: ...
    def make_flow_result(self) -> dict: ...
    def _resolve_calls(self) -> None: ...
    def _detect_entry_points(self) -> list: ...
    def _calculate_statistics(self) -> dict: ...

class BaseRoutesParser:
    FILE_EXTENSIONS = []
    SKIP_DIRS = {...}

    def __init__(self, project_path, options=None): ...
    def parse(self) -> dict: ...
    def make_routes_result(self) -> dict: ...
    def _calculate_statistics(self) -> dict: ...
```

Shared utility: `strip_comments(content, language)` — removes comments and string literals before regex parsing (prevents false matches inside comments/strings). Preserves line numbers by replacing stripped content with whitespace.

### ParserManager Updates (`backend/parsers/parser_manager.py`)

**Enhanced detection** — checks manifest files in priority order:
- `requirements.txt` / `setup.py` / `pyproject.toml` → Python
- `package.json` → JS/TS (inspect deps for Express, NestJS, Prisma, TypeORM, Sequelize, Mongoose)
- `.prisma` files → Prisma
- `pom.xml` / `build.gradle` → Java (inspect for Spring Boot, JPA/Hibernate)
- `*.csproj` / `*.sln` → C# (inspect for EF, ASP.NET)
- `Gemfile` → Ruby (inspect for Rails, ActiveRecord)
- `go.mod` → Go (inspect for Gin, Echo, GORM)
- `composer.json` → PHP (inspect for Laravel, Eloquent)
- `*.abap` / `*.txt` with ABAP keywords → ABAP

**Updated parse methods** — `parse_runtime_flow()` and `parse_api_routes()` detect language internally (matching how `parse_database_schema()` already works) instead of hardcoding Python-only checks.

### Regex Parsing Strategy (non-Python languages)

All non-Python parsers use **compiled regex patterns** + **brace counting** for class body extraction:

1. Read file, run through `strip_comments(content, lang)` to remove comments/string literals
2. Match class-level markers (e.g., `@Entity`, `@Controller`, `[ApiController]`)
3. Extract class body via brace counting from match position
4. Within class body, match member-level markers (e.g., `@Column`, `@GetMapping`)
5. Extract names, types, attributes from annotation/decorator arguments

### Frontend Changes

**Only `CenterUploadArea.jsx`** needs updating — the `getAnalysisTypeDisplay()` function (lines 86-111):

```javascript
'database_schema': {
    title: 'Database Schema',
    description: 'Upload ORM model files or database files to visualize your schema',
    acceptedFiles: '.py, .ts, .js, .java, .cs, .rb, .go, .php, .prisma, .db, .sqlite',
},
'runtime_flow': {
    title: 'Runtime Flow',
    description: 'Upload source files to visualize runtime execution flow',
    acceptedFiles: '.py, .js, .ts, .java, .abap',
},
'api_routes': {
    title: 'API Routes',
    description: 'Upload source files to visualize API endpoints and routes',
    acceptedFiles: '.py, .js, .ts, .java, .cs, .rb, .go, .php',
}
```

No changes needed to `FlowVisualization.jsx`, `ApiRoutesVisualization.jsx`, or `apiRoutesTransform.js` — they consume the standardized JSON format and are language-agnostic.

---

## Implementation Phases

### Phase 1: Foundation
- Create `base.py` with base classes and `strip_comments()` utility
- Create `schema/`, `flow/`, `routes/` subdirectory packages
- Move existing parsers into subdirectories
- Update `parsers/__init__.py` with backward-compatible re-exports
- Enhance `ParserManager` with full multi-language detection
- Update `parse_runtime_flow()` and `parse_api_routes()` to use language-aware routing
- Verify all existing tests pass with moved files

### Phase 2: Python Ecosystem
- `schema/django_parser.py` (AST-based, sibling to SQLAlchemy parser)
- `routes/django_routes_parser.py` (AST-based, parse `urls.py` patterns)
- `routes/fastapi_parser.py` (AST-based, similar to Flask parser)
- Test fixtures + unit tests for each

### Phase 3: JavaScript/TypeScript Ecosystem
- `schema/prisma_parser.py` (line-by-line DSL parser)
- `schema/typeorm_parser.py` (regex + brace counting)
- `schema/sequelize_parser.py` (regex)
- `schema/mongoose_parser.py` (regex)
- `routes/express_parser.py` (regex)
- `routes/nestjs_parser.py` (regex + brace counting)
- `flow/js_flow_parser.py` (regex)
- Update `_detect_js_framework()` to inspect `package.json` dependencies
- Test fixtures + unit tests

### Phase 4: Java Ecosystem
- `schema/jpa_parser.py` (regex + brace counting)
- `routes/spring_parser.py` (regex + brace counting)
- `flow/java_flow_parser.py` (regex)
- Add `_detect_java_framework()` (inspect `pom.xml`/`build.gradle`)
- Test fixtures + unit tests

### Phase 5: C# Ecosystem
- `schema/ef_parser.py` (regex + brace counting, both Data Annotations and Fluent API)
- `routes/aspnet_parser.py` (regex + brace counting)
- Add `_detect_csharp_framework()` (inspect `.csproj`)
- Test fixtures + unit tests

### Phase 6: Ruby, PHP, Go Ecosystems
- `schema/activerecord_parser.py` (regex — migrations + model associations)
- `schema/eloquent_parser.py` (regex)
- `schema/gorm_parser.py` (regex — Go struct tags)
- `routes/rails_routes_parser.py` (regex — `routes.rb` DSL)
- `routes/laravel_parser.py` (regex)
- `routes/gin_parser.py` (regex)
- Add `_detect_ruby_framework()`, `_detect_php_framework()`, `_detect_go_framework()`
- Test fixtures + unit tests

### Phase 7: ABAP Ecosystem
- `schema/abap_dict_parser.py` (regex — ABAP Dictionary/DDIC definitions)
- `flow/abap_flow_parser.py` (regex — `FORM/PERFORM`, `METHOD/CALL METHOD`, `FUNCTION MODULE`)
- `routes/abap_icf_parser.py` (regex — ICF service nodes, OData service defs)
- Add `_detect_abap_framework()`
- Test fixtures + unit tests

### Phase 8: Frontend + Polish
- Update `CenterUploadArea.jsx` descriptions and accepted file types
- Final integration testing across all language paths

---

## Critical Files to Modify

| File | Change |
|------|--------|
| `backend/parsers/__init__.py` | Re-exports for backward compat |
| `backend/parsers/parser_manager.py` | Multi-language detection + routing |
| `backend/parsers/base.py` | NEW — base classes |
| `backend/parsers/schema/*.py` | NEW — 13 schema parsers (11 new + 2 moved) |
| `backend/parsers/flow/*.py` | NEW — 4 flow parsers (3 new + 1 moved) |
| `backend/parsers/routes/*.py` | NEW — 11 routes parsers (9 new + 2 moved — Flask + ABAP ICF) |
| `frontend/src/components/project/CenterUploadArea.jsx` | Update descriptions + accepted files |

Existing route handlers (`workspace_routes.py`, `projects.py`) require **zero changes** — they already call `ParserManager` methods which handle routing internally.

---

## Testing Strategy

**Test fixtures** under `backend/tests/fixtures/` — one minimal but realistic sample project per parser (e.g., `django_models/models.py`, `spring_routes/UserController.java`, `prisma_schema/schema.prisma`).

**Test pattern** for each parser:
1. `test_parse_basic_model` — extracts tables/functions/routes correctly
2. `test_parse_relationships` — detects foreign keys and associations
3. `test_parse_empty_project` — handles no matching files gracefully
4. `test_parse_malformed_file` — doesn't crash on syntax errors

**ParserManager tests** in `test_parser_manager.py`:
- Detection tests for each language/framework combo
- Routing tests to verify correct parser is invoked

---

## Verification

1. Run existing tests to confirm nothing breaks after file moves: `pytest backend/tests/`
2. Run each new parser's test suite as it's built
3. Manual integration test: upload sample files for each language through the UI and verify visualization renders correctly
4. Verify `CenterUploadArea.jsx` shows updated descriptions
5. Test the full flow: upload → detect → parse → store → retrieve → visualize for at least Python (existing), JS/Prisma, Java/Spring, and ABAP

---

## Dependencies

- **Zero new Python packages** — all parsing uses `re`, `ast`, `os`, `pathlib`, `json` (stdlib)
- **Zero frontend dependencies** — JSON format unchanged
- **Zero database migrations** — `language`/`framework` columns already accept any string
