# API Routes Visualization - Design Document

**Date:** 2026-02-09
**Status:** Implemented
**Feature:** Add API Routes visualization to Code Visualizer

---

## Overview

Enable users to visualize Flask API routes in a hierarchical graph showing blueprints, endpoints, HTTP methods, and authentication requirements. This completes the third visualization type in the sidebar (currently grayed out with "Soon" badge).

---

## Goals

1. Parse Flask routes from uploaded Python projects using AST analysis
2. Display routes grouped by blueprint with method badges and auth indicators
3. Follow established patterns from Database Schema and Runtime Flow visualizations
4. Provide filtering and statistics for route analysis

---

## Technical Design

### Backend Parser

**File:** `backend/parsers/flask_routes_parser.py`

Following the pattern from `runtime_flow_parser.py`, create an AST-based parser:

```python
class RouteVisitor(ast.NodeVisitor):
    """AST visitor to extract Flask route definitions."""

    def __init__(self, filepath: str, module_name: str):
        self.filepath = filepath
        self.module_name = module_name
        self.blueprints = []
        self.routes = []
        self.current_blueprint = None

    def visit_Assign(self, node: ast.Assign):
        """Detect Blueprint assignments: auth_bp = Blueprint('auth', __name__)"""
        # Extract blueprint name and store for later route association

    def visit_FunctionDef(self, node: ast.FunctionDef):
        """Extract route decorators from function definitions"""
        for decorator in node.decorator_list:
            if self._is_route_decorator(decorator):
                route_info = self._parse_route_decorator(decorator)
                route_info['function_name'] = node.name
                route_info['docstring'] = ast.get_docstring(node)
                route_info['security'] = self._extract_security(node.decorator_list)
                self.routes.append(route_info)
```

**Output Schema:**

```json
{
  "analysis_type": "api_routes",
  "version": "1.0",
  "project_path": "/path/to/project",

  "blueprints": [
    {
      "id": "blueprint_auth_5",
      "type": "blueprint",
      "name": "auth",
      "url_prefix": "/api/auth",
      "file_path": "routes/auth.py",
      "line_number": 5,
      "route_count": 2
    }
  ],

  "routes": [
    {
      "id": "route_auth_register_8",
      "type": "route",
      "name": "register",
      "blueprint_id": "blueprint_auth_5",
      "url_pattern": "/register",
      "full_url": "/api/auth/register",
      "methods": ["POST"],
      "function_name": "register",
      "file_path": "routes/auth.py",
      "line_number": 8,
      "docstring": "Register a new user",
      "parameters": {
        "path_params": [],
        "query_params": []
      },
      "security": {
        "requires_auth": false,
        "auth_decorators": []
      }
    }
  ],

  "statistics": {
    "total_blueprints": 3,
    "total_routes": 16,
    "routes_by_method": {"GET": 8, "POST": 6, "DELETE": 2},
    "protected_routes": 14,
    "unprotected_routes": 2
  }
}
```

### AST Extraction Details

**1. Blueprint Detection:**
```python
# Pattern: auth_bp = Blueprint('auth', __name__)
def _extract_blueprint(self, node: ast.Assign):
    for target in node.targets:
        if isinstance(target, ast.Name) and isinstance(node.value, ast.Call):
            if self._is_blueprint_call(node.value):
                return {
                    'id': f"blueprint_{target.id}_{node.lineno}",
                    'name': self._get_blueprint_name(node.value),
                    'variable': target.id,
                    'line_number': node.lineno
                }
```

**2. Route Decorator Parsing:**
```python
# Pattern: @auth_bp.route('/register', methods=['POST'])
def _parse_route_decorator(self, decorator: ast.Call):
    url_pattern = ""
    methods = ["GET"]  # Default

    # First arg is URL pattern
    if decorator.args:
        url_pattern = ast.literal_eval(decorator.args[0])

    # methods keyword arg
    for keyword in decorator.keywords:
        if keyword.arg == 'methods':
            methods = [m.s for m in keyword.value.elts]

    return {'url_pattern': url_pattern, 'methods': methods}
```

**3. Security Detection:**
```python
# Detect: @jwt_required(), @login_required, @auth_required
AUTH_DECORATORS = {'jwt_required', 'login_required', 'auth_required', 'require_auth'}

def _extract_security(self, decorators: list):
    auth_decorators = []
    for dec in decorators:
        name = self._get_decorator_name(dec)
        if name in self.AUTH_DECORATORS:
            auth_decorators.append(name)
    return {
        'requires_auth': len(auth_decorators) > 0,
        'auth_decorators': auth_decorators
    }
```

**4. Path Parameter Extraction:**
```python
# Parse: /<int:project_id>/upload -> {'project_id': 'int'}
import re

def _extract_path_params(self, url_pattern: str):
    params = []
    matches = re.findall(r'<(\w+:)?(\w+)>', url_pattern)
    for type_hint, name in matches:
        params.append({
            'name': name,
            'type': type_hint.rstrip(':') if type_hint else 'string'
        })
    return params
```

---

### Backend API Endpoints

**File:** `backend/routes/projects.py`

```python
@projects_bp.route('/<int:project_id>/analyze/api-routes', methods=['POST'])
@jwt_required()
def analyze_api_routes(project_id):
    """Analyze Flask/FastAPI routes in project files"""
    user_id = int(get_jwt_identity())

    # Verify project ownership
    conn = get_connection()
    cur = conn.cursor()
    cur.execute('SELECT * FROM projects WHERE id = %s AND user_id = %s',
                (project_id, user_id))
    project = cur.fetchone()

    if not project:
        return jsonify({'error': 'Project not found'}), 404

    # Parse routes
    manager = ParserManager()
    try:
        routes_data = manager.parse_api_routes(project['file_path'])
    except UnsupportedFrameworkError as e:
        return jsonify({'error': str(e)}), 400

    # Store results
    cur.execute('''
        INSERT INTO analysis_results (project_id, analysis_type, result_data)
        VALUES (%s, 'api_routes', %s)
        ON CONFLICT (project_id, analysis_type)
        DO UPDATE SET result_data = EXCLUDED.result_data, created_at = NOW()
    ''', (project_id, json.dumps(routes_data)))

    # Update project status
    cur.execute('UPDATE projects SET has_api_routes = TRUE WHERE id = %s', (project_id,))
    conn.commit()

    return jsonify({'message': 'API routes analysis complete', 'routes': routes_data}), 200


@projects_bp.route('/<int:project_id>/api-routes', methods=['GET'])
@jwt_required()
def get_api_routes(project_id):
    """Get cached API routes analysis"""
    user_id = int(get_jwt_identity())

    conn = get_connection()
    cur = conn.cursor()

    # Verify ownership and get results
    cur.execute('''
        SELECT ar.result_data FROM analysis_results ar
        JOIN projects p ON ar.project_id = p.id
        WHERE ar.project_id = %s AND p.user_id = %s AND ar.analysis_type = 'api_routes'
    ''', (project_id, user_id))

    result = cur.fetchone()
    if not result:
        return jsonify({'error': 'No API routes analysis found'}), 404

    return jsonify({'routes': json.loads(result['result_data'])}), 200
```

---

### Frontend Components

#### RouteNode.jsx

Custom ReactFlow node for displaying API routes:

```jsx
import React, { memo } from 'react';
import { Handle, Position } from 'reactflow';

const METHOD_COLORS = {
  GET: { bg: 'bg-green-500', text: 'text-white' },
  POST: { bg: 'bg-blue-500', text: 'text-white' },
  PUT: { bg: 'bg-orange-500', text: 'text-white' },
  DELETE: { bg: 'bg-red-500', text: 'text-white' },
  PATCH: { bg: 'bg-purple-500', text: 'text-white' },
};

const RouteNode = memo(({ data, selected }) => {
  const { name, url_pattern, methods, requires_auth, docstring, path_params } = data;

  return (
    <div className={`
      px-4 py-3 rounded-lg border-2 min-w-[200px] max-w-[300px]
      ${selected ? 'border-blue-500 shadow-lg' : 'border-gray-300 dark:border-gray-600'}
      bg-white dark:bg-gray-800
    `}>
      <Handle type="target" position={Position.Top} className="!bg-gray-400" />

      {/* Method badges */}
      <div className="flex flex-wrap gap-1 mb-2">
        {methods.map((method) => (
          <span
            key={method}
            className={`px-2 py-0.5 text-xs font-bold rounded ${METHOD_COLORS[method]?.bg || 'bg-gray-500'} ${METHOD_COLORS[method]?.text || 'text-white'}`}
          >
            {method}
          </span>
        ))}
        {requires_auth && (
          <span className="px-2 py-0.5 text-xs bg-amber-100 dark:bg-amber-900 text-amber-700 dark:text-amber-300 rounded flex items-center gap-1">
            <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M5 9V7a5 5 0 0110 0v2a2 2 0 012 2v5a2 2 0 01-2 2H5a2 2 0 01-2-2v-5a2 2 0 012-2zm8-2v2H7V7a3 3 0 016 0z" clipRule="evenodd" />
            </svg>
            Auth
          </span>
        )}
      </div>

      {/* URL pattern */}
      <div className="font-mono text-sm text-gray-900 dark:text-gray-100 mb-1 break-all">
        {url_pattern}
      </div>

      {/* Function name */}
      <div className="text-xs text-gray-500 dark:text-gray-400">
        {name}()
      </div>

      {/* Docstring preview */}
      {docstring && (
        <div className="mt-2 text-xs text-gray-400 dark:text-gray-500 truncate" title={docstring}>
          {docstring}
        </div>
      )}

      <Handle type="source" position={Position.Bottom} className="!bg-gray-400" />
    </div>
  );
});

RouteNode.displayName = 'RouteNode';
export default RouteNode;
```

#### BlueprintNode.jsx

Container node for grouping routes by blueprint:

```jsx
import React, { memo } from 'react';
import { Handle, Position } from 'reactflow';

const BlueprintNode = memo(({ data, selected }) => {
  const { name, url_prefix, route_count } = data;

  return (
    <div className={`
      px-5 py-4 rounded-xl border-2 min-w-[180px]
      ${selected ? 'border-blue-500 shadow-lg' : 'border-slate-400 dark:border-slate-500'}
      bg-slate-100 dark:bg-slate-700
    `}>
      <Handle type="target" position={Position.Top} className="!bg-slate-500" />

      {/* Blueprint icon and name */}
      <div className="flex items-center gap-2 mb-1">
        <svg className="w-5 h-5 text-slate-600 dark:text-slate-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
        </svg>
        <span className="font-semibold text-slate-700 dark:text-slate-200">
          {name}
        </span>
      </div>

      {/* URL prefix */}
      <div className="font-mono text-xs text-slate-500 dark:text-slate-400 mb-2">
        {url_prefix || '/'}
      </div>

      {/* Route count badge */}
      <div className="inline-flex items-center px-2 py-0.5 rounded bg-slate-200 dark:bg-slate-600 text-xs text-slate-600 dark:text-slate-300">
        {route_count} route{route_count !== 1 ? 's' : ''}
      </div>

      <Handle type="source" position={Position.Bottom} className="!bg-slate-500" />
    </div>
  );
});

BlueprintNode.displayName = 'BlueprintNode';
export default BlueprintNode;
```

#### apiRoutesTransform.js

Transform backend data to ReactFlow format:

```javascript
/**
 * Transform API routes data to ReactFlow nodes and edges
 */
export const transformApiRoutesData = (routesData) => {
  if (!routesData?.routes) {
    return { nodes: [], edges: [] };
  }

  const nodes = [];
  const edges = [];

  // Create blueprint nodes
  routesData.blueprints?.forEach((blueprint) => {
    nodes.push({
      id: blueprint.id,
      type: 'blueprintNode',
      data: {
        name: blueprint.name,
        url_prefix: blueprint.url_prefix,
        route_count: blueprint.route_count,
      },
      position: { x: 0, y: 0 },
    });
  });

  // Create route nodes and edges to blueprints
  routesData.routes.forEach((route) => {
    nodes.push({
      id: route.id,
      type: 'routeNode',
      data: {
        name: route.function_name,
        url_pattern: route.full_url || route.url_pattern,
        methods: route.methods,
        requires_auth: route.security?.requires_auth || false,
        docstring: route.docstring,
        path_params: route.parameters?.path_params || [],
      },
      position: { x: 0, y: 0 },
    });

    // Edge from blueprint to route
    if (route.blueprint_id) {
      edges.push({
        id: `edge-${route.blueprint_id}-${route.id}`,
        source: route.blueprint_id,
        target: route.id,
        type: 'smoothstep',
        style: { stroke: '#94a3b8' },
      });
    }
  });

  return { nodes, edges };
};

/**
 * Estimate node dimensions for Dagre layout
 */
export const getRouteNodeWidth = () => 240;
export const getRouteNodeHeight = (node) => {
  const base = 80;
  const methodRows = Math.ceil(node.data.methods?.length / 3) * 20;
  return base + methodRows;
};

export const getBlueprintNodeWidth = () => 200;
export const getBlueprintNodeHeight = () => 100;
```

---

### Integration Points

#### Sidebar.jsx (Line 32)

Change `disabled: true` to `disabled: false`:

```javascript
{
  id: 'api',
  name: 'API Routes',
  icon: (/* existing icon */),
  disabled: false,  // Enable the item
},
```

#### ProjectVisualization.jsx

Add state and handlers:

```javascript
// State
const [apiRoutesData, setApiRoutesData] = useState(null);

// Load function
const loadApiRoutesData = async () => {
  try {
    const response = await api.get(`/projects/${projectId}/api-routes`);
    setApiRoutesData(response.data.routes);
  } catch (error) {
    if (error.response?.status !== 404) {
      console.error('Failed to load API routes:', error);
    }
  }
};

// Effect to load on view switch
useEffect(() => {
  if (activeView === 'api' && !apiRoutesData && project) {
    loadApiRoutesData();
  }
}, [activeView, project]);

// Render in view switching logic
{activeView === 'api' && (
  <ApiRoutesVisualization
    routesData={apiRoutesData}
    isDark={isDark}
    projectId={projectId}
  />
)}
```

---

### Database Migration

Add `has_api_routes` column:

```sql
-- SQLite
ALTER TABLE projects ADD COLUMN has_api_routes BOOLEAN DEFAULT 0;

-- PostgreSQL
ALTER TABLE projects ADD COLUMN IF NOT EXISTS has_api_routes BOOLEAN DEFAULT FALSE;
```

---

## Visualization Design

### Layout
- **Style:** Hierarchical tree (top-to-bottom)
- **Algorithm:** Dagre with `rankdir: 'TB'`, `nodesep: 80`, `ranksep: 100`
- **Grouping:** Blueprints at top, routes below

### Color Scheme

| Element | Color | Purpose |
|---------|-------|---------|
| GET badge | Green #10b981 | Safe, read-only |
| POST badge | Blue #3b82f6 | Create operations |
| PUT badge | Orange #f59e0b | Update operations |
| DELETE badge | Red #ef4444 | Destructive operations |
| Auth indicator | Amber #f59e0b | Protected route |
| Blueprint node | Slate #64748b | Container/group |

### Statistics Panel

Display in top-right corner:
- Total routes count
- Routes by method (mini bar chart)
- Protected vs unprotected ratio
- Total blueprints

---

## File Changes Summary

| File | Action | Description |
|------|--------|-------------|
| `backend/parsers/flask_routes_parser.py` | Create | AST-based Flask route parser |
| `backend/parsers/parser_manager.py` | Modify | Add `parse_api_routes()` method |
| `backend/parsers/__init__.py` | Modify | Export FlaskRoutesParser |
| `backend/routes/projects.py` | Modify | Add two new endpoints |
| `frontend/src/components/project/nodes/RouteNode.jsx` | Create | Route display component |
| `frontend/src/components/project/nodes/BlueprintNode.jsx` | Create | Blueprint container component |
| `frontend/src/components/project/ApiRoutesVisualization.jsx` | Create | Main visualization |
| `frontend/src/utils/apiRoutesTransform.js` | Create | Data transformation |
| `frontend/src/components/project/Sidebar.jsx` | Modify | Enable API Routes item |
| `frontend/src/components/project/ProjectVisualization.jsx` | Modify | Add view handling |

---

## Testing Plan

### Backend Tests

Create `backend/tests/test_parsers/test_flask_routes_parser.py`:

1. **test_parse_simple_route** - Single route with GET method
2. **test_parse_multiple_methods** - Route with `methods=['GET', 'POST']`
3. **test_parse_blueprint** - Blueprint detection and association
4. **test_parse_jwt_required** - Auth decorator detection
5. **test_parse_path_parameters** - URL parameter extraction
6. **test_parse_docstring** - Docstring extraction
7. **test_parse_multiple_blueprints** - Complex project structure

### Manual Testing

1. Upload Flask project (use this codebase's own backend)
2. Navigate to API Routes view
3. Verify blueprints display with correct route counts
4. Verify routes show correct methods, auth status, URLs
5. Test layout and zoom/pan
6. Verify dark mode styling

---

## Future Enhancements

1. **FastAPI Support** - Detect and parse FastAPI routes
2. **Database Connections** - Show which routes access which tables
3. **Request/Response Schemas** - Display expected payloads
4. **Route Search** - Filter by URL pattern or method
5. **Export** - Generate OpenAPI/Swagger documentation
