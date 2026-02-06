# Code Visualizer - Design Document

**Date:** February 4, 2026 (Updated: February 6, 2026)
**Project:** Visual Backend Code Analyzer
**Architecture:** Monolithic Flask App with Modular Parsers
**Status:** MVP Deployed on Render

## Current Implementation Status

### ✅ Implemented Features

**Backend (Python/Flask):**
- ✅ Flask application with JWT authentication
- ✅ PostgreSQL database with all tables (users, projects, analysis_results, workspace_layouts, workspace_notes)
- ✅ SQLite support for local development
- ✅ Database abstraction layer supporting both SQLite and PostgreSQL
- ✅ User registration and login
- ✅ Project CRUD operations
- ✅ File upload functionality
- ✅ Parser Manager with framework detection
- ✅ SQLAlchemy parser for Python projects

**Frontend (React):**
- ✅ Authentication pages (Login/Register)
- ✅ Dashboard with project cards
- ✅ Project visualization workspace with React Flow
- ✅ Light/Dark mode toggle (Dashboard and Workspace)
- ✅ Sticky notes functionality
- ✅ Workspace layout persistence
- ✅ Theme persistence (localStorage)
- ✅ Responsive design with Tailwind CSS
- ✅ Toast notifications

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

- ⏳ Git repository cloning
- ⏳ Additional language parsers (TypeScript, JavaScript)
- ⏳ API Routes visualization
- ⏳ Export functionality (PNG, SVG, PDF)
- ⏳ Advanced filtering and search
- ⏳ Auto-layout algorithm

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
│   ├── dashboard/
│   │   └── Dashboard.jsx          # ✅ Implemented with dark mode
│   ├── project/
│   │   ├── ProjectUpload.jsx      # ✅ File upload UI
│   │   └── ProjectVisualization.jsx # ✅ React Flow workspace
│   └── common/
│       └── ProtectedRoute.jsx     # ✅ Auth guard
├── services/
│   └── api.js                     # ✅ Axios instance with JWT
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

## Next Steps

1. **Add export functionality** (PNG, SVG, PDF, Markdown)
2. **Implement Git repository cloning** (currently upload-only)
3. **Build additional parsers:**
   - Django ORM parser
   - Prisma parser (TypeScript)
   - TypeORM parser
   - Sequelize parser (JavaScript)
4. **Add workspace features:**
   - Table search and filtering
   - Auto-layout algorithm (dagre)
   - Context menu (right-click)
5. **Write comprehensive tests:**
   - Parser unit tests
   - API endpoint tests
   - Component tests
   - E2E tests
6. **Performance optimization:**
   - Handle large codebases
   - Optimize React Flow rendering
   - Add pagination for projects
7. **User experience improvements:**
   - Better error messages
   - Loading states
   - Onboarding tutorial
8. **Security hardening:**
   - Rate limiting
   - File upload sanitization
   - CORS configuration review

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
