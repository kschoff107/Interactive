# Code Visualizer - Design Document

**Date:** February 4, 2026
**Project:** Visual Backend Code Analyzer
**Architecture:** Monolithic Flask App with Modular Parsers

## Overview

A web application that helps visual learners understand backend systems by analyzing code and generating interactive visualizations. Starting with database schema visualization, with plans to expand to API routes, code structure, and runtime flow visualization.

**Target Users:** Developers, students, bootcamp learners, and non-technical stakeholders who want to understand backend systems visually.

**Tech Stack:**
- Backend: Python/Flask with PostgreSQL
- Frontend: React with React Flow
- Analysis: Multiple language parsers (Python, TypeScript/JavaScript)

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
│  │  - parsers/python_parser.py         │   │
│  │  - parsers/typescript_parser.py     │   │
│  │  - parsers/javascript_parser.py     │   │
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
│  - Uploaded project files                   │
│  - Cloned Git repositories                  │
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
    file_path VARCHAR(500), -- local storage path
    language VARCHAR(50),  -- detected: 'python', 'typescript', etc.
    framework VARCHAR(50), -- detected: 'sqlalchemy', 'prisma', etc.
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### analysis_results table
```sql
CREATE TABLE analysis_results (
    id SERIAL PRIMARY KEY,
    project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
    analysis_type VARCHAR(50) NOT NULL, -- 'database_schema', 'api_routes', etc.
    result_data JSONB NOT NULL, -- the parsed schema/data
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
   - **If Upload:** User drags/drops folder or selects files
     - React sends files to `/api/projects/upload` endpoint
     - Flask saves files to `storage/uploads/{user_id}/{project_id}/`
   - **If Git:** User provides repo URL
     - React sends URL to `/api/projects/clone` endpoint
     - Flask clones repo to `storage/repos/{user_id}/{project_id}/`
     - Supports public repos initially (GitHub, GitLab, Bitbucket)

4. **Automatic Analysis:**
   - After upload/clone, Flask automatically:
     - Detects language/framework by scanning files
     - Calls appropriate parser
     - Parser returns standardized JSON structure
     - Saves to `analysis_results` table
     - Returns project ID and analysis status to frontend

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

---

## 4. Parser Architecture & Language Support

**Parser Manager:**

Routes analysis to correct parser based on detected language/framework.

```python
# parsers/parser_manager.py

class ParserManager:
    def detect_language_and_framework(self, project_path):
        """Scan project files to detect language/framework"""
        if os.path.exists(f"{project_path}/requirements.txt"):
            return self._detect_python_framework(project_path)
        elif os.path.exists(f"{project_path}/package.json"):
            return self._detect_js_framework(project_path)
        # Add more detection logic

    def parse_database_schema(self, project_path, language, framework):
        """Route to appropriate parser"""
        parser_map = {
            ('python', 'sqlalchemy'): SQLAlchemyParser(),
            ('python', 'django'): DjangoParser(),
            ('typescript', 'prisma'): PrismaParser(),
            ('javascript', 'sequelize'): SequelizeParser(),
        }
        parser = parser_map.get((language, framework))
        if parser:
            return parser.parse(project_path)
        else:
            raise UnsupportedFrameworkError()
```

**Individual Parser Structure:**

```python
# parsers/python_parser.py

class SQLAlchemyParser:
    def parse(self, project_path) -> Dict:
        """Parse SQLAlchemy models and return standardized schema"""
        tables = []
        model_files = self._find_model_files(project_path)

        for file_path in model_files:
            with open(file_path, 'r') as f:
                tree = ast.parse(f.read())
                tables.extend(self._extract_tables_from_ast(tree))

        relationships = self._detect_relationships(tables)

        return {
            'tables': tables,
            'relationships': relationships
        }
```

**Standardized Output:**
- All parsers return the same JSON structure
- Frontend is language-agnostic
- Easy to add new parsers without changing frontend

**Language Support Phases:**
- **Phase 1:** Python (SQLAlchemy, Django ORM)
- **Phase 2:** TypeScript/JavaScript (Prisma, TypeORM)
- **Phase 3:** Additional frameworks as needed

---

## 5. React Frontend Structure & Visualization

**Component Structure:**

```
src/
├── components/
│   ├── auth/
│   │   ├── Login.jsx
│   │   └── Register.jsx
│   ├── layout/
│   │   ├── Sidebar.jsx
│   │   ├── Header.jsx
│   │   └── Layout.jsx
│   ├── dashboard/
│   │   ├── Dashboard.jsx
│   │   └── ProjectCard.jsx
│   ├── project/
│   │   ├── NewProject.jsx
│   │   ├── ProjectDetail.jsx
│   │   └── ExportMenu.jsx
│   └── visualization/
│       ├── DatabaseSchema.jsx
│       ├── TableNode.jsx
│       ├── RelationshipEdge.jsx
│       └── StickyNote.jsx
├── services/
│   └── api.js
├── context/
│   └── AuthContext.jsx
└── App.jsx
```

**Visualization Library: React Flow**

Chosen for:
- Built for interactive node-based diagrams
- Native zoom, pan, drag-and-drop support
- Customizable nodes for tables
- Good performance with many nodes
- Active community

**Left Sidebar Menu:**
```
• Database Schema (active)
• API Routes (future)
• Code Structure (future)
• Runtime Flow (future)
```

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
- Double-click for detailed view modal

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
Create sample projects for each framework to test against:
```
tests/fixtures/
├── sqlalchemy_simple/
├── sqlalchemy_complex/
├── django_basic/
├── prisma_example/
└── typescript_typeorm/
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

**Deployment Options:**

### Option 1: Simple VPS (Recommended for MVP)
- DigitalOcean, Linode
- Nginx reverse proxy
- Gunicorn for Flask
- PostgreSQL on same server
- Local file storage
- Cost: ~$20-40/month
- Good for 100-1000 users

### Option 2: Cloud Platform (Easiest)
- Heroku, Railway, Render
- Git push to deploy
- Managed PostgreSQL
- S3 for file storage
- Cost: ~$25-50/month
- Zero DevOps required

### Option 3: Containerized (Future)
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
│   ├── requirements.txt
│   ├── models/
│   ├── routes/
│   ├── parsers/
│   ├── services/
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

## Next Steps

1. **Setup git worktree** for isolated development
2. **Create implementation plan** with detailed tasks
3. **Start with backend foundation** (Flask app, database, auth)
4. **Build first parser** (SQLAlchemy)
5. **Create React frontend** (auth + dashboard)
6. **Add visualization workspace** (React Flow integration)
7. **Implement sticky notes** and workspace persistence
8. **Add export functionality**
9. **Write tests**
10. **Deploy MVP**

---

## Future Enhancements (Post-MVP)

- API Routes visualization
- Code Structure diagram
- Runtime Flow visualization
- Private Git repository support (OAuth)
- Collaborative workspaces (multi-user)
- Real-time collaboration on diagrams
- More language/framework support
- AI-powered insights and recommendations
- Integration with CI/CD pipelines
- VSCode extension
