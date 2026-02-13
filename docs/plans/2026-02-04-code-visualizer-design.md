# Code Visualizer - Design Document

**Date:** February 4, 2026 (Updated: February 13, 2026 — Node Detail Modal)
**Project:** Visual Backend Code Analyzer
**Architecture:** Monolithic Flask App with Modular Parsers
**Status:** MVP Deployed on Render

## Current Implementation Status

### ✅ Implemented Features

**Backend (Python/Flask):**
- ✅ Flask application with JWT authentication
- ✅ PostgreSQL database with all tables (users, projects, analysis_results, workspace_layouts, workspace_notes, workspaces, workspace_files)
- ✅ SQLite support for local development
- ✅ Database abstraction layer supporting both SQLite and PostgreSQL
- ✅ User registration and login
- ✅ Project CRUD operations
- ✅ File upload functionality
- ✅ Parser Manager with multi-language detection (Python, JS/TS, Java, C#, Ruby, Go, PHP, ABAP)
- ✅ Base parser classes with shared utilities (comment stripping, brace counting, file discovery)
- ✅ Database Schema parsers (13): SQLAlchemy, SQLite, Django ORM, Prisma, TypeORM, Sequelize, Mongoose, JPA/Hibernate, Entity Framework, ActiveRecord, Eloquent, GORM, ABAP Dictionary
- ✅ Runtime Flow parsers (4): Python AST, JavaScript/TypeScript, Java, ABAP
- ✅ API Routes parsers (11): Flask, Django, FastAPI, Express, NestJS, Spring Boot, ASP.NET, Rails, Laravel, Gin/Echo, ABAP ICF/OData
- ✅ AI-powered code analysis with Claude API
- ✅ GitHub API-based repository import (no full cloning)
- ✅ Git API service with URL parsing, tree fetching, selective file download
- ✅ `git_branch` persistence on import
- ✅ `GET /projects/<id>/files` endpoint for listing project files on disk
- ✅ Multi-workspace support: `workspaces` table, `workspace_id` on analysis/layout/notes tables
- ✅ Workspace CRUD API endpoints (list, create, rename, delete)
- ✅ Workspace-scoped data endpoints (layout, analysis, runtime-flow, api-routes per workspace)
- ✅ Per-workspace file storage: upload, list, and delete files per workspace
- ✅ Import source files from GitHub to workspace via API endpoint (`POST /workspaces/{ws_id}/import-source`)
- ✅ Workspace-scoped analysis: analyze only workspace files (not project-level)
- ✅ Auto-creation of default workspaces for backward compatibility
- ✅ Security: path traversal prevention, URL validation (github.com only), file size/count limits

**Frontend (React):**
- ✅ Authentication pages (Login/Register)
- ✅ Dashboard with project cards
- ✅ Project visualization workspace with React Flow
- ✅ Light/Dark mode toggle (Dashboard and Workspace)
- ✅ Sticky notes functionality (all three visualization views: Schema, Runtime Flow, API Routes)
- ✅ Workspace layout persistence
- ✅ Theme persistence (localStorage)
- ✅ Responsive design with Tailwind CSS
- ✅ Toast notifications
- ✅ Runtime Flow visualization with custom nodes (FunctionNode, ConditionalNode, etc.), sticky notes, toolbar
- ✅ API Routes visualization with BlueprintNode and RouteNode (method badges, auth indicators), sticky notes, toolbar
- ✅ Sidebar navigation between visualization types
- ✅ "Decode This" insight guide with AI-powered code analysis
- ✅ GitHub Import modal with file browser, checkbox selection, quick-select by extension
- ✅ Source Files panel in sidebar (git-imported projects) — full repo tree from GitHub API, clickable repo link, branch badge, refresh button
- ✅ Drag-and-drop import from Source Files panel to workspace (individual files or entire folders)
- ✅ Resizable sidebar — drag right edge to adjust width (180–500px, persisted to localStorage)
- ✅ Vertical split between workspace nav and Source Files panel — drag divider to allocate space (20–80%, persisted to localStorage)
- ✅ Reusable ResizeHandle component (horizontal/vertical, visual feedback on hover/drag)
- ✅ Discrete thin scrollbars in sidebar panels (4px webkit, thin Firefox, dark mode support)
- ✅ Multi-workspace sidebar: expandable two-level tree with workspace sub-items per visualization type
- ✅ Workspace creation (+) in sidebar
- ✅ Three-dot context menu on workspace items: Rename, Duplicate, Clear Data, Delete (with confirmation modal)
- ✅ Workspace-aware data loading and layout persistence (each workspace loads independently)
- ✅ Per-workspace file upload via CenterUploadArea (files go to workspace, not project)
- ✅ Empty workspace detection: shows upload area when workspace has no analysis data
- ✅ Node Detail Modal — double-click any node to open expanded detail view with full context
  - 4 detail renderers: TableNodeDetail, FunctionNodeDetail, BlueprintNodeDetail, RouteNodeDetail
  - Each renderer looks up full record from raw backend data via `contextData` prop (no transform changes needed)
  - Schema view: full columns table (nullable, unique, FK ref), relationships with direction arrows, foreign keys
  - Flow view: full identity, all decorators, docstring, complexity breakdown, callers/callees with context, internal control flow, orphan warning
  - API Routes (blueprint): file location, full route listing with method badges, security summary, method breakdown
  - API Routes (route): full URL, docstring, path parameters, security with auth decorators, blueprint context with sibling routes
  - Shared ref-counted scroll lock utility (`modalScrollLock.js`) prevents body scroll leak when multiple modals overlap
  - ESC key, backdrop click, and close button all dismiss the modal
  - Full dark mode support via CSS class-based `.node-detail-overlay.dark` selectors

**Deployment:**
- ✅ Deployed on Render (https://interactive-frontend.onrender.com)
- ✅ Backend API running on Render with PostgreSQL
- ✅ Frontend static site on Render
- ✅ Auto-deploy from `qual` branch
- ✅ Environment variables configured
- ✅ Database initialization on deployment

**Theme System:**
- ✅ ThemeContext with React Context API
- ✅ Persistent theme preference (localStorage)
- ✅ Light/Dark mode toggle button (bottom left on both pages)
- ✅ Full dark mode support across all components
- ✅ Tailwind CSS dark: prefix classes

### 🚧 In Progress / Planned

- ⏳ Export functionality (PNG, SVG, PDF)
- ⏳ Advanced filtering and search
- ⏳ Private Git repository support (OAuth)

### 📊 Current Architecture

**Production URLs:**
- Frontend: https://interactive-frontend.onrender.com
- Backend API: https://interactive-qual.onrender.com/api
- Database: PostgreSQL on Render

**Git Branches:**
- `master` - Main development branch (includes theme toggle)
- `qual` - Production deployment branch (Render deploys from here)

## Overview

A web application that helps visual learners understand backend systems by analyzing code and generating interactive visualizations. Starting with database schema visualization, with plans to expand to API routes, code structure, and runtime flow visualization.

**Target Users:** Developers, students, bootcamp learners, and non-technical stakeholders who want to understand backend systems visually.

**Tech Stack:**
- Backend: Python/Flask with PostgreSQL
- Frontend: React with React Flow
- Analysis: Multiple language parsers (Python, JS/TS, Java, C#, Ruby, Go, PHP, ABAP)

---

## 1. Overall Architecture & System Components

**High-Level Structure:**

```
┌─────────────────────────────────────────────┐
│           React Frontend (SPA)              │
│  - Auth pages (login/register)              │
│  - Dashboard (user's projects)              │
│  - Visualization workspace                  │
│  - Left sidebar navigation                  │
└──────────────────┬──────────────────────────┘
                   │ REST API
┌──────────────────▼──────────────────────────┐
│         Flask Backend (main app)            │
│  ┌─────────────────────────────────────┐   │
│  │  Routes/Blueprints                  │   │
│  │  - auth_bp (login, register)        │   │
│  │  - projects_bp (CRUD projects)      │   │
│  │  - analysis_bp (trigger/get results)│   │
│  └─────────────────────────────────────┘   │
│  ┌─────────────────────────────────────┐   │
│  │  Parser Manager                     │   │
│  │  - Detects language/framework       │   │
│  │  - Routes to appropriate parser     │   │
│  └─────────────────────────────────────┘   │
│  ┌─────────────────────────────────────┐   │
│  │  Language Parsers (modular)         │   │
│  │  - parsers/schema/ (13 parsers)     │   │
│  │  - parsers/flow/   (4 parsers)      │   │
│  │  - parsers/routes/ (11 parsers)     │   │
│  │  - parsers/base.py (shared utils)   │   │
│  └─────────────────────────────────────┘   │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│         PostgreSQL Database                 │
│  - users table                              │
│  - projects table                           │
│  - analysis_results table (JSON)            │
│  - workspace_notes table                    │
│  - workspace_layouts table                  │
└─────────────────────────────────────────────┘

┌─────────────────────────────────────────────┐
│      File Storage (local/S3)                │
│  - Per-workspace files:                     │
│    storage/uploads/{uid}/{pid}/ws_{wid}/    │
│  - Legacy project-level files:              │
│    storage/uploads/{uid}/{pid}/             │
└─────────────────────────────────────────────┘
```

**Core Components:**
- **Flask backend** handles auth, project management, file uploads, Git cloning, and code analysis
- **Modular parsers** are Python modules that extract database schema from different languages/ORMs
- **PostgreSQL** stores user accounts, project metadata, and analysis results (as JSON)
- **React frontend** provides the visualization interface with interactive schema diagrams
- **File storage** keeps uploaded/cloned code for re-analysis

---

## 2. Database Schema & Data Models

**PostgreSQL Tables:**

### users table
```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(80) UNIQUE NOT NULL,
    email VARCHAR(120) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### projects table
```sql
CREATE TABLE projects (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    source_type VARCHAR(20) NOT NULL, -- 'upload' or 'git'
    git_url VARCHAR(500),  -- if source_type='git'
    git_branch VARCHAR(100), -- branch used for git import
    file_path VARCHAR(500), -- local storage path
    language VARCHAR(50),  -- detected: 'python', 'typescript', etc.
    framework VARCHAR(50), -- detected: 'sqlalchemy', 'prisma', etc.
    has_database_schema BOOLEAN DEFAULT FALSE,
    has_runtime_flow BOOLEAN DEFAULT FALSE,
    has_api_routes BOOLEAN DEFAULT FALSE,
    last_upload_date TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### workspaces table
```sql
CREATE TABLE workspaces (
    id SERIAL PRIMARY KEY,
    project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
    analysis_type VARCHAR(50) NOT NULL, -- 'database_schema', 'runtime_flow', 'api_routes'
    name VARCHAR(200) NOT NULL,
    sort_order INTEGER DEFAULT 0,
    file_path VARCHAR(500),  -- workspace-specific file directory
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### workspace_files table
```sql
CREATE TABLE workspace_files (
    id SERIAL PRIMARY KEY,
    workspace_id INTEGER REFERENCES workspaces(id) ON DELETE CASCADE,
    file_name VARCHAR(255) NOT NULL,
    file_path VARCHAR(500) NOT NULL,
    file_size INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### analysis_results table
```sql
CREATE TABLE analysis_results (
    id SERIAL PRIMARY KEY,
    project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
    analysis_type VARCHAR(50) NOT NULL, -- 'database_schema', 'api_routes', etc.
    result_data JSONB NOT NULL, -- the parsed schema/data
    workspace_id INTEGER REFERENCES workspaces(id) ON DELETE SET NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### workspace_notes table
```sql
CREATE TABLE workspace_notes (
    id SERIAL PRIMARY KEY,
    project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
    analysis_type VARCHAR(50) NOT NULL, -- 'database_schema', etc.
    note_text TEXT NOT NULL,
    position_x FLOAT NOT NULL,
    position_y FLOAT NOT NULL,
    color VARCHAR(20) DEFAULT 'yellow', -- 'yellow', 'blue', 'green', 'pink'
    workspace_id INTEGER REFERENCES workspaces(id) ON DELETE SET NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### workspace_layouts table
```sql
CREATE TABLE workspace_layouts (
    id SERIAL PRIMARY KEY,
    project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
    analysis_type VARCHAR(50) NOT NULL,
    layout_data JSONB NOT NULL, -- stores table positions
    workspace_id INTEGER REFERENCES workspaces(id) ON DELETE SET NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Result Data Structure (JSON for database_schema):**
```json
{
  "tables": [
    {
      "name": "users",
      "columns": [
        {
          "name": "id",
          "type": "INTEGER",
          "nullable": false,
          "primary_key": true
        },
        {
          "name": "username",
          "type": "VARCHAR(80)",
          "nullable": false,
          "unique": true
        }
      ],
      "foreign_keys": [],
      "indexes": [
        {
          "name": "idx_username",
          "columns": ["username"]
        }
      ]
    },
    {
      "name": "projects",
      "columns": [...],
      "foreign_keys": [
        {
          "column": "user_id",
          "references_table": "users",
          "references_column": "id"
        }
      ]
    }
  ],
  "relationships": [
    {
      "from": "projects",
      "to": "users",
      "type": "many-to-one"
    }
  ]
}
```

---

## 3. User Workflow & Data Flow

**User Journey:**

1. **Authentication:**
   - User registers/logs in via React frontend
   - Flask issues JWT token or session cookie
   - Token included in subsequent API requests

2. **Create Project:**
   - User clicks "New Project" in dashboard
   - Chooses method: "Upload Files" or "Connect Git Repo"
   - Provides project name and description

3. **Upload/Clone Code:**
   - **If Upload to Workspace:** User drags/drops files into a workspace
     - React sends files to `/api/projects/{id}/workspaces/{ws_id}/upload`
     - Flask saves files to `storage/uploads/{user_id}/{project_id}/ws_{workspace_id}/`
     - Files tracked in `workspace_files` table
   - **If Git:** User provides repo URL
     - React sends URL to `/api/projects/clone` endpoint
     - Flask downloads selected files to `storage/uploads/{user_id}/{project_id}/`
     - Supports public GitHub repos (API-based, no full cloning)

4. **Workspace Analysis:**
   - User triggers analysis from workspace UI (or auto after upload):
     - Analyze endpoint checks workspace-specific files in `ws_{workspace_id}/` directory
     - If workspace has no files, returns error prompting upload first
     - Parser analyzes only the workspace's files
     - Results saved to `analysis_results` with `workspace_id`
     - Each workspace's analysis is independent

5. **View Visualization:**
   - User navigates to project detail page
   - React fetches analysis results from API
   - Renders interactive diagram using React Flow
   - User can click tables, zoom, pan, search, filter

6. **Generate Documentation:**
   - User clicks "Export" button
   - Options: PNG, SVG, PDF diagram, or Markdown documentation
   - Flask generates file and returns download link

**Key API Endpoints:**
- `POST /api/auth/register`
- `POST /api/auth/login`
- `GET /api/projects` (list user's projects)
- `POST /api/projects/upload`
- `POST /api/projects/clone`
- `GET /api/projects/{id}/analysis/{type}`
- `POST /api/projects/{id}/reanalyze`
- `GET /api/projects/{id}/export/{format}`
- `POST /api/projects/{id}/notes`
- `PUT /api/notes/{note_id}`
- `DELETE /api/notes/{note_id}`
- `PUT /api/projects/{id}/layout`
- `GET /api/projects/{id}/workspaces` (list workspaces grouped by type)
- `POST /api/projects/{id}/workspaces` (create workspace)
- `PATCH /api/projects/{id}/workspaces/{ws_id}` (rename)
- `DELETE /api/projects/{id}/workspaces/{ws_id}` (delete)
- `GET/POST /api/projects/{id}/workspaces/{ws_id}/layout` (workspace-scoped layout)
- `GET /api/projects/{id}/workspaces/{ws_id}/analysis` (workspace-scoped schema)
- `GET/POST /api/projects/{id}/workspaces/{ws_id}/runtime-flow` (workspace-scoped flow)
- `GET/POST /api/projects/{id}/workspaces/{ws_id}/api-routes` (workspace-scoped routes)
- `POST /api/projects/{id}/workspaces/{ws_id}/upload` (upload files to workspace)
- `GET /api/projects/{id}/workspaces/{ws_id}/files` (list workspace files)
- `DELETE /api/projects/{id}/workspaces/{ws_id}/files/{file_id}` (delete workspace file)
- `POST /api/projects/{id}/workspaces/{ws_id}/import-source` (import GitHub source files to workspace)

---

## 4. Parser Architecture & Language Support

**Directory Structure:**

```
backend/parsers/
    __init__.py                    # Backward-compatible re-exports
    base.py                        # BaseSchemaParser, BaseFlowParser, BaseRoutesParser, utilities
    parser_manager.py              # Multi-language detection + routing

    schema/                        # 13 parsers
        sqlalchemy_parser.py       # Python — SQLAlchemy (AST)
        sqlite_parser.py           # SQLite database files (direct DB query)
        django_parser.py           # Python — Django ORM (AST)
        prisma_parser.py           # JS/TS — Prisma (line-by-line DSL)
        typeorm_parser.py          # TypeScript — TypeORM (regex + brace counting)
        sequelize_parser.py        # JavaScript — Sequelize (regex)
        mongoose_parser.py         # JS/TS — Mongoose (regex)
        jpa_parser.py              # Java — JPA/Hibernate (regex + brace counting)
        ef_parser.py               # C# — Entity Framework (regex, Data Annotations + Fluent API)
        activerecord_parser.py     # Ruby — Rails ActiveRecord (regex, migrations + models)
        gorm_parser.py             # Go — GORM (regex, struct tags)
        eloquent_parser.py         # PHP — Laravel Eloquent (regex)
        abap_dict_parser.py        # ABAP — Dictionary (regex, TYPES/DATA/CDS views)

    flow/                          # 4 parsers
        python_flow_parser.py      # Python (AST — functions, calls, control flow)
        js_flow_parser.py          # JS/TS (regex — functions, arrows, classes)
        java_flow_parser.py        # Java (regex — methods, calls, control flow)
        abap_flow_parser.py        # ABAP (regex — FORM/PERFORM, METHOD, FUNCTION MODULE)

    routes/                        # 11 parsers
        flask_parser.py            # Python — Flask (AST)
        django_routes_parser.py    # Python — Django (AST, urls.py + DRF ViewSets)
        fastapi_parser.py          # Python — FastAPI (AST, decorators + Depends)
        express_parser.py          # JS/TS — Express (regex)
        nestjs_parser.py           # TypeScript — NestJS (regex + brace counting)
        spring_parser.py           # Java — Spring Boot (regex + brace counting)
        aspnet_parser.py           # C# — ASP.NET Core (regex + brace counting)
        rails_routes_parser.py     # Ruby — Rails (regex, routes.rb DSL)
        laravel_parser.py          # PHP — Laravel (regex, Route:: DSL)
        gin_parser.py              # Go — Gin/Echo (regex)
        abap_icf_parser.py         # ABAP — ICF/OData/RAP (regex)
```

**Parser Manager:**

Routes analysis to correct parser based on detected language/framework. Detection checks manifest files in priority order:

```python
class ParserManager:
    def detect_all(self, project_path) -> List[Tuple[str, str]]:
        """Detect all languages/frameworks present in a project."""
        # Priority order:
        # 1. SQLite databases (.db, .sqlite, .sqlite3)
        # 2. Python (requirements.txt, setup.py, pyproject.toml)
        # 3. Prisma (.prisma files)
        # 4. JS/TS (package.json → inspect deps for Express, NestJS, Prisma, etc.)
        # 5. Java (pom.xml, build.gradle → inspect for Spring, JPA)
        # 6. C# (.csproj, .sln → inspect for EF, ASP.NET)
        # 7. Ruby (Gemfile → inspect for Rails)
        # 8. Go (go.mod → inspect for Gin, GORM)
        # 9. PHP (composer.json → inspect for Laravel)
        # 10. ABAP (.abap files)
        # 11. Fallback: scan source file extensions
```

**Base Classes (`base.py`):**

Shared utilities used by all parsers — zero new dependencies (all stdlib):

- `BaseSchemaParser` — `parse()`, `find_files()`, `make_schema_result()`, `_detect_relationships()`
- `BaseFlowParser` — `parse()`, `make_flow_result()`, `_resolve_calls()`, `_detect_entry_points()`
- `BaseRoutesParser` — `parse()`, `make_routes_result()`, `_calculate_statistics()`
- `strip_comments(content, language)` — removes comments and string literals before regex parsing (supports c_family, python, ruby, php, abap)
- `extract_block_body(content, start)` — brace counting for class/method body extraction
- `find_source_files(path, extensions)` — recursive file discovery with common directory exclusions

**Parsing Strategies:**

| Language | Strategy | Notes |
|----------|----------|-------|
| Python | AST (`ast.parse`) | Full fidelity, handles all syntax |
| Prisma | Line-by-line DSL | `.prisma` files have simple grammar |
| Java, C#, TypeScript | Regex + brace counting | Compiled patterns, `strip_comments()` prevents false matches |
| Ruby, PHP, Go | Regex | Custom comment strippers preserve string literals |
| ABAP | Regex + uppercase normalization | Case-insensitive language |
| SQLite | Direct database query | `sqlite3` module reads `sqlite_master` |

**Standardized Output:**
- All parsers return the same JSON structure per analysis type
- Frontend is completely language-agnostic
- Easy to add new parsers without changing frontend
- Old import paths (`from backend.parsers.sqlalchemy_parser import ...`) still work via shim files

---

## 5. React Frontend Structure & Visualization

**Component Structure:**

```
src/
├── components/
│   ├── auth/
│   │   ├── Login.jsx
│   │   └── Register.jsx
│   ├── dashboard/
│   │   ├── Dashboard.jsx          # ✅ Implemented with dark mode
│   │   └── GitImportModal.jsx     # ✅ GitHub file browser & import
│   ├── project/
│   │   ├── ProjectUpload.jsx      # ✅ File upload UI
│   │   ├── ProjectVisualization.jsx # ✅ React Flow workspace + horizontal resize
│   │   ├── Sidebar.jsx            # ✅ Expandable workspace tree + Source panel + vertical split
│   │   ├── SourceFilesPanel.jsx   # ✅ GitHub repo tree, refresh button, drag-to-import
│   │   ├── ResizeHandle.jsx       # ✅ Reusable horizontal/vertical drag handle
│   │   ├── CenterUploadArea.jsx   # ✅ Drag-and-drop upload zone (files + source import)
│   │   ├── FlowVisualization.jsx  # ✅ Runtime flow view
│   │   ├── ApiRoutesVisualization.jsx # ✅ API routes view
│   │   ├── NodeDetailModal.jsx    # ✅ Double-click detail modal (dispatches to node type renderers)
│   │   ├── NodeDetailModal.css    # ✅ Modal styling with full dark mode
│   │   └── nodeDetails/           # ✅ Detail renderers per node type
│   │       ├── TableNodeDetail.jsx      # Schema table: columns, relationships, FKs
│   │       ├── FunctionNodeDetail.jsx   # Flow function: identity, callers/callees, control flow
│   │       ├── BlueprintNodeDetail.jsx  # API blueprint: route listing, security summary
│   │       └── RouteNodeDetail.jsx      # API route: full URL, params, security, siblings
│   └── common/
│       └── ProtectedRoute.jsx     # ✅ Auth guard
├── services/
│   └── api.js                     # ✅ Axios instance with JWT + gitAPI + workspacesAPI
├── utils/
│   └── modalScrollLock.js         # ✅ Ref-counted body scroll lock (shared across all modals)
├── context/
│   ├── AuthContext.jsx            # ✅ User auth state
│   └── ThemeContext.jsx           # ✅ Light/Dark mode state
└── App.jsx                        # ✅ Main routing
```

**Visualization Library: React Flow**

Chosen for:
- Built for interactive node-based diagrams
- Native zoom, pan, drag-and-drop support
- Customizable nodes for tables
- Good performance with many nodes
- Active community

**Left Sidebar Menu (Expandable Tree with Multi-Workspace):**
```
VISUALIZATIONS
  Database Schema          [+]
    > Default
    > (user-created workspaces...)
  Runtime Flow             [+]
    > Default
  API Routes               [+]
    > Default
  Code Structure           Soon

─── drag divider ───  (vertical resize)

SOURCE (git-imported projects only)
  owner/repo →
  ◊ main  ↻
  ▸ src/
  ▸ tests/
    README.md
```
- Each visualization type is expandable with chevron toggle
- [+] button creates a new workspace under that type
- Clicking a workspace loads its analysis data and layout
- Hover shows three-dot (...) menu with: Rename, Duplicate, Clear Data, Delete
- Delete action shows confirmation modal before proceeding
- Sidebar right edge is draggable to resize width (180–500px, persisted to localStorage)
- Divider between workspace nav and Source Files panel is draggable vertically (20–80% split, persisted)
- Source Files panel shows full repo tree with drag-to-import and click-to-import actions
- Refresh button next to branch badge re-fetches the GitHub repo tree on demand

**Main Workspace Layout:**

```
┌─────────────────────────────────────────────┐
│  Header (logo, project name, user menu)    │
├────────┬────────────────────────────────────┤
│ Side   │  Workspace                         │
│ bar    │  ┌──────────────────────────────┐  │
│        │  │ [Add Note] [Search] [Export] │  │
│ • DB   │  ├──────────────────────────────┤  │
│   Schema│  │                              │  │
│ • API  │  │   [Table: Users]             │  │
│ • Code │  │        ↓ (FK)                │  │
│ • Flow │  │   [Table: Projects]          │  │
│        │  │   [Sticky Note]              │  │
│        │  └──────────────────────────────┘  │
└────────┴────────────────────────────────────┘
```

**Table Node Features:**
- Table name header
- Columns with types displayed
- PK indicator (key icon)
- FK indicator (link icon)
- Click to highlight related tables
- Double-click for detailed view modal (NodeDetailModal — renders full context per node type)

**Theme System (Implemented):**

The application supports light and dark modes with persistent user preference.

**ThemeContext Structure:**
```javascript
// src/context/ThemeContext.jsx
export const ThemeProvider = ({ children }) => {
  const [isDark, setIsDark] = useState(() => {
    const saved = localStorage.getItem('theme');
    return saved === 'dark';
  });

  useEffect(() => {
    if (isDark) {
      document.documentElement.classList.add('dark');
      localStorage.setItem('theme', 'dark');
    } else {
      document.documentElement.classList.remove('dark');
      localStorage.setItem('theme', 'light');
    }
  }, [isDark]);

  const toggleTheme = () => setIsDark(!isDark);

  return (
    <ThemeContext.Provider value={{ isDark, toggleTheme }}>
      {children}
    </ThemeContext.Provider>
  );
};
```

**Theme Toggle Button:**
- **Location:** Bottom left corner (fixed position)
- **Icon:** Sun (light mode) / Moon (dark mode)
- **Styling:** White/gray-800 background with shadow
- **Behavior:** Toggles theme and saves to localStorage
- **Pages:** Dashboard and ProjectVisualization workspace

**Dark Mode Implementation:**
- **Tailwind CSS:** Uses `dark:` prefix classes
- **CSS Variables:** For ReactFlow nodes and edges
- **Components:** All components support dark mode
- **Colors:**
  - Light: gray-50 background, gray-900 text
  - Dark: gray-900 background, white text

**Example Dark Mode Classes:**
```jsx
<div className="bg-white dark:bg-gray-800">
  <h1 className="text-gray-900 dark:text-white">Title</h1>
  <p className="text-gray-600 dark:text-gray-300">Content</p>
</div>
```

---

## 6. Workspace Features & User Customizations

**Draggable Tables:**
- Tables are React Flow nodes with `draggable: true`
- Position changes auto-save to `workspace_layouts` table
- Positions restored on reload

**Sticky Notes:**
- Free-floating note boxes users can place anywhere
- Features:
  - Inline text editing
  - Draggable
  - Color picker (yellow, blue, green, pink)
  - Delete button
  - Auto-save on blur/color change
- Stored in `workspace_notes` table

**Workspace Toolbar:**
```
[Add Note] [Search Tables] [Filter] [Auto-Layout]
[Zoom -] [Zoom +] [Fit View] [Export]
```

**Auto-Layout:**
- Automatically arranges tables using dagre algorithm
- Useful when workspace gets messy
- User can manually adjust after

**Context Menu (Right-click):**
- On table: "Add Note Here", "Hide Table", "View Details"
- On canvas: "Add Note", "Reset Layout"

**Persistence:**
- All changes auto-save (debounced)
- Each visualization type has separate workspace
- Loading spinner on auto-save

---

## 7. Error Handling & Edge Cases

**File Upload & Git Cloning:**

1. **File Size Limits:**
   - Max upload: 100MB (configurable)
   - 413 error with clear message if exceeded

2. **Git Clone Failures:**
   - Invalid URL validation
   - Private repos: "Not supported yet" message
   - Network timeout: Retry once, then fail gracefully
   - Large repos (>500MB): Warning with proceed/cancel option

3. **Malformed Files:**
   - Try-catch around file reads
   - Mark project as "Analysis Failed"
   - Clear error message to user

**Parser Errors:**

1. **Unsupported Framework:**
   - Save project, mark as "Unsupported"
   - Message: "We don't support [framework] yet"
   - Allow re-analysis later

2. **Partial Parse Failures:**
   - Return partial results with warning
   - Show: "Analyzed 8 of 10 model files"

3. **No Schema Found:**
   - Return empty schema
   - Message: "No database models found"

**Runtime Errors:**

1. **Database Connection:**
   - Connection pooling with retry logic
   - 503 Service Unavailable if PostgreSQL down

2. **File Storage:**
   - Disk full: 507 Insufficient Storage
   - Permission errors: Log and return 500

**Frontend Error Handling:**

- Toast notifications for errors
- Network errors: "Connection lost"
- 401: Redirect to login
- 500: "Something went wrong. Try again."
- Visualization fallback if React Flow fails

**Data Validation:**

- Backend: marshmallow or pydantic schemas
- Frontend: Form validation before submission
- Parameterized SQL queries (injection protection)

**Logging:**

- Log all errors with context (user_id, project_id)
- Python logging module
- Consider Sentry for error tracking (later)

---

## 8. Testing Strategy

**Backend Testing:**

### Parser Unit Tests
```python
# tests/test_parsers/test_sqlalchemy_parser.py

def test_parse_simple_model():
    parser = SQLAlchemyParser()
    result = parser.parse('tests/fixtures/simple_sqlalchemy_project')

    assert len(result['tables']) == 2
    assert result['tables'][0]['name'] == 'users'
    assert result['tables'][0]['columns'][0]['primary_key'] == True
```

### API Endpoint Tests
```python
def test_create_project_upload(client, auth_token):
    response = client.post(
        '/api/projects/upload',
        headers={'Authorization': f'Bearer {auth_token}'},
        data={'name': 'Test Project', 'files': [...]}
    )
    assert response.status_code == 201
```

### Test Fixtures
Sample projects for each framework/language:
```
tests/fixtures/
├── django_models/          # Django ORM models
├── django_urls/            # Django URL configuration + DRF router
├── fastapi_routes/         # FastAPI app with routers and Depends
├── prisma_schema/          # Prisma schema with 5 models + enum
├── typeorm_models/         # TypeORM entities with decorators
├── sequelize_models/       # Sequelize define() + Model.init()
├── mongoose_models/        # Mongoose schemas with refs
├── jpa_models/             # JPA entities with annotations
├── ef_models/              # EF DbContext + Data Annotations + Fluent API
├── activerecord/           # Rails migrations + model associations
├── eloquent_models/        # Laravel Eloquent models + migrations
├── gorm_models/            # Go GORM structs with tags
├── express_routes/         # Express routers with middleware
├── nestjs_routes/          # NestJS controllers with guards
├── spring_routes/          # Spring Boot REST controllers
├── aspnet_routes/          # ASP.NET API controllers
├── rails_routes/           # Rails routes.rb DSL
├── laravel_routes/         # Laravel Route:: definitions
├── gin_routes/             # Go Gin route groups
├── js_flow/                # JS/TS functions and classes
├── java_flow/              # Java methods and control flow
├── abap_dictionary/        # ABAP TYPES/DATA/CDS views
├── abap_flow/              # ABAP FORM/METHOD/events
└── abap_icf/               # ABAP OData DPC + RAP + ICF handlers
```

**Frontend Testing:**

### Component Tests (React Testing Library)
```javascript
test('renders tables from analysis data', () => {
  render(<DatabaseSchema data={mockData} />);
  expect(screen.getByText('users')).toBeInTheDocument();
});

test('allows adding sticky notes', () => {
  render(<DatabaseSchema data={mockData} />);
  fireEvent.click(screen.getByText('Add Note'));
  expect(screen.getByPlaceholderText('Add note...')).toBeInTheDocument();
});
```

**Testing Priorities:**

**Phase 1 (MVP):**
- Parser unit tests (critical)
- API endpoint tests (critical)
- Basic component tests (important)

**Phase 2 (Post-MVP):**
- Integration tests
- E2E tests (Playwright/Cypress)
- Performance tests (large codebases)

---

## 9. Deployment & Technology Stack

**Technology Stack:**

**Backend:**
- Python 3.10+
- Flask 3.x
- Flask-JWT-Extended (auth)
- SQLAlchemy (PostgreSQL ORM)
- PostgreSQL 14+
- GitPython (Git operations)
- AST module (Python parsing)
- Regex + brace counting (non-Python language parsing — zero extra dependencies)

**Frontend:**
- React 18+
- React Flow (visualization)
- Axios (API calls)
- React Router (navigation)
- Tailwind CSS (styling)
- React Toastify (notifications)

**Development Tools:**
- pytest (backend testing)
- React Testing Library (frontend)
- ESLint + Prettier

**Current Deployment (Render):**

### ✅ Production Setup (Currently Deployed)
**Platform:** Render.com
- **Backend Service:** `interactive-qual`
  - Runtime: Python 3
  - Region: Oregon (US West)
  - Build Command: `pip install -r requirements.txt && python init_db.py`
  - Start Command: `gunicorn --bind 0.0.0.0:$PORT app:app`
  - Root Directory: `backend`
  - Branch: `qual`

- **Frontend Service:** `interactive-frontend`
  - Type: Static Site
  - Region: Global CDN
  - Build Command: `cd frontend && npm install && npm run build`
  - Publish Directory: `frontend/build`
  - Environment: `REACT_APP_API_URL=https://interactive-qual.onrender.com/api`

- **Database:** `interact-db`
  - Type: PostgreSQL 18
  - Region: Oregon (US West)
  - Connection: Internal connection string to backend

**Environment Variables (Backend):**
```bash
DATABASE_URL=<PostgreSQL connection string from Render>
SECRET_KEY=<generated>
JWT_SECRET_KEY=<generated>
FLASK_DEBUG=False
STORAGE_PATH=/opt/render/project/src/storage
```

**Deployment Flow:**
1. Push code to `qual` branch on GitHub
2. Render automatically detects changes
3. Builds backend and frontend
4. Runs database initialization
5. Deploys to production URLs

**Free Tier Limitations:**
- Services spin down after 15 minutes of inactivity
- First request after spin-down takes 30-60 seconds
- Suitable for development and small user base

### Alternative Deployment Options (Future)

### Option 1: Simple VPS
- DigitalOcean, Linode
- Nginx reverse proxy
- Gunicorn for Flask
- PostgreSQL on same server
- Local file storage
- Cost: ~$20-40/month
- Good for 100-1000 users

### Option 2: Containerized
- Docker containers
- Cloud Run/AWS ECS
- Better for scaling
- More complex setup

**Development Setup:**

```bash
# Backend
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
createdb code_visualizer_db
flask db upgrade
flask run

# Frontend
cd frontend
npm install
npm start
```

**Environment Variables:**

```bash
# Backend
DATABASE_URL=postgresql://user:pass@localhost/code_visualizer_db
SECRET_KEY=your-secret-key
FLASK_ENV=development
MAX_UPLOAD_SIZE=104857600
STORAGE_PATH=/path/to/storage

# Frontend
REACT_APP_API_URL=http://localhost:5000/api
```

**Project Structure:**

```
code-visualizer/
├── backend/
│   ├── app.py
│   ├── config.py
│   ├── init_db.py
│   ├── requirements.txt
│   ├── models/
│   │   ├── workspace.py             # Workspace model (multi-workspace)
│   │   ├── analysis_result.py       # + workspace_id field
│   │   ├── workspace_layout.py      # + workspace_id field
│   │   └── workspace_note.py        # + workspace_id field
│   ├── routes/
│   │   └── workspace_routes.py      # Workspace CRUD + file upload + scoped data endpoints
│   ├── parsers/
│   │   ├── base.py                    # Shared base classes + utilities
│   │   ├── parser_manager.py          # Multi-language detection + routing
│   │   ├── schema/                    # 13 schema parsers
│   │   ├── flow/                      # 4 flow parsers
│   │   └── routes/                    # 11 routes parsers
│   ├── services/
│   │   ├── code_analysis_service.py  # AI-powered analysis
│   │   └── git_api_service.py        # GitHub API integration
│   └── tests/
├── frontend/
│   ├── public/
│   ├── src/
│   ├── package.json
│   └── tailwind.config.js
├── storage/
├── docs/
│   └── plans/
└── README.md
```

**Security Considerations:**

- HTTPS in production (Let's Encrypt)
- Rate limiting (Flask-Limiter)
- File upload sanitization
- Parameterized SQL queries
- CORS configuration
- JWT token expiration
- Never execute uploaded code (only parse AST)

---

## Completed Steps

1. ✅ **Setup git worktree** for isolated development
2. ✅ **Create implementation plan** with detailed tasks
3. ✅ **Start with backend foundation** (Flask app, database, auth)
4. ✅ **Build first parser** (SQLAlchemy)
5. ✅ **Create React frontend** (auth + dashboard)
6. ✅ **Add visualization workspace** (React Flow integration)
7. ✅ **Implement sticky notes** and workspace persistence
8. ✅ **Deploy MVP** to Render
9. ✅ **Add light/dark mode** toggle
10. ✅ **PostgreSQL production database** with SQLite dev support
11. ✅ **Runtime Flow visualization** (AST-based function/call graph)
12. ✅ **AI-powered code analysis** with Claude API ("Decode This" feature)
13. ✅ **API Routes visualization** (Flask routes parser with blueprints, methods, auth detection)
14. ✅ **GitHub repository import** (API-based, selective file download — no full cloning)
15. ✅ **Source Files panel** in project sidebar (full repo tree, branch badge, clickable repo link)
16. ✅ **Multi-workspace support** — multiple workspaces per visualization type with create, rename, delete; expandable sidebar tree; workspace-scoped data loading and layout persistence
17. ✅ **Per-workspace file storage** — files uploaded and stored per workspace (not project-level); workspace_files table tracks files; analyze endpoints use workspace files only; empty workspace shows upload area; workspace deletion cleans up files on disk
18. ✅ **Workspace context menu** — replaced red X delete button with three-dot (...) menu on hover; dropdown with Rename, Duplicate, Clear Data, Delete options; delete requires confirmation modal; duplicate creates new workspace with "(Copy)" suffix; clear data removes all files and analysis from workspace
19. ✅ **Drag-and-drop source file import** — drag files/folders from Source Files panel to workspace upload area, or click import icon; backend `POST /workspaces/{ws_id}/import-source` downloads files from GitHub API and stores in workspace directory
20. ✅ **Resizable sidebar** — horizontal drag handle on sidebar right edge (180–500px width, localStorage persistence); vertical drag handle between workspace nav and Source Files panel (20–80% split, localStorage persistence); reusable ResizeHandle component with hover/drag visual feedback; discrete 4px thin scrollbars in sidebar panels
21. ✅ **Source Files refresh button** — manual refresh button next to branch badge in Source Files panel; re-fetches GitHub repo tree on click; spinning animation during fetch
22. ✅ **Database schema analyze endpoint** — `POST /workspaces/{ws_id}/analyze/database-schema` runs parser on workspace files; frontend triggers analysis after upload instead of just reloading
23. ✅ **GitHub API token support** — optional `GITHUB_TOKEN` env var for authenticated requests (5,000 req/hour vs 60 unauthenticated); applied to all git API service calls
24. ✅ **Sticky notes in all views** — Runtime Flow and API Routes views now have sticky notes and full toolbar (zoom, add note, theme toggle); notes persist via layout save; excluded from dagre auto-layout; preserved during Quick Organize
25. ✅ **Multi-language parser support** — 27 new parsers across 8 languages (Python, JS/TS, Java, C#, Ruby, Go, PHP, ABAP); modular directory structure (`parsers/schema/`, `parsers/flow/`, `parsers/routes/`); shared base classes with comment stripping, brace counting, and file discovery utilities; ParserManager rewritten with multi-language detection from manifest files; backward-compatible shim imports; zero new dependencies; 24 test fixtures covering all parsers; see `docs/plans/2026-02-12-multi-language-parsers.md` for full implementation details
26. ✅ **Node Detail Modal** — double-click any node across all 3 visualization views to open expanded detail modal; 4 dedicated renderers (TableNodeDetail, FunctionNodeDetail, BlueprintNodeDetail, RouteNodeDetail) each look up full records from raw backend data via `contextData` prop; shared ref-counted `modalScrollLock.js` utility prevents body scroll leak when multiple modals overlap; full dark mode support; ESC/backdrop/close-button dismiss; see `docs/plans/2026-02-13-node-detail-modal.md` for full implementation details

## Next Steps

1. **Add export functionality** (PNG, SVG, PDF, Markdown)
2. **Add workspace features:**
   - Table search and filtering
3. **Write comprehensive tests:**
   - Parser unit tests for all 28 parsers
   - API endpoint tests
   - Component tests
   - E2E tests
4. **Performance optimization:**
   - Handle large codebases
   - Optimize React Flow rendering
   - Add pagination for projects
5. **User experience improvements:**
   - Better error messages
   - Loading states
   - Onboarding tutorial
6. **Security hardening:**
   - Rate limiting
   - File upload sanitization
   - CORS configuration review

---

## Future Enhancements (Post-MVP)

- Code Structure diagram
- **Process Flow visualization** (Business process modeling)
  - BPMN-style process diagrams
  - Visual process builder with drag-and-drop
  - Support for process elements:
    - Tasks/Activities (rectangles)
    - Decision points/Gateways (diamonds)
    - Start/End events (circles)
    - Swim lanes for actors/systems
    - Connectors and sequence flows
  - Process validation and execution path analysis
  - Map business processes to code implementation
  - Export to BPMN XML format
  - Use cases: Document workflows, map business logic to code, process improvement, compliance documentation
- Private Git repository support (GitHub OAuth for higher API rate limits)
- GitLab and Bitbucket repository support
- Branch selection dropdown in import modal
- ~~"Re-import" button to refresh files from repo~~ ✅ Done (refresh button in Source Files panel)
- Collaborative workspaces (multi-user)
- Real-time collaboration on diagrams
- ~~More language/framework support~~ ✅ Done (28 parsers across 8 languages)
- AI-powered insights and recommendations
- Integration with CI/CD pipelines
- VSCode extension
