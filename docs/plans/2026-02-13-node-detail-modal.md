# Node Detail Modal — Double-Click to Expand

## Context

The app has 3 visualization views (Database Schema, Runtime Flow, API Routes), each with compact node representations. Nodes show summary info but much richer data exists in the backend response that isn't displayed. Users need a way to drill into any node and understand its full context — what it is, what it connects to, and why it matters.

**Goal:** Double-click any node to open a detail modal showing expanded, contextual information about that node.

---

## What Each Node Type Will Show

### Database Table Nodes (Schema View)
Currently shows: table name, columns with types, PK indicator

**Expanded detail will add:**
- **Full Column Table** — nullable, unique, FK reference for each column (data exists in `table.columns[]` and `table.foreign_keys[]`)
- **Relationships** — all inbound and outbound relationships filtered from `schema.relationships[]`, showing direction arrows, related table names, column mappings, and relationship type
- **Foreign Keys** — explicit list of FK constraints with referenced table/column

### Function Nodes (Runtime Flow View)
Currently shows: name, params, decorators (max 3), complexity badge, async/entry badges

**Expanded detail will add:**
- **Full Identity** — module path, file path, line number, qualified name, class name (if method). All available via lookup in `flowData.functions[]`
- **Full Decorators** — all decorators, not truncated to 3
- **Docstring** — extracted by backend parser (`func.docstring`) but never passed to frontend
- **Complexity Breakdown** — score with color + explanatory text + line count (`end_line - line_number`)
- **Callers** — "Who calls this?" — derived from `flowData.calls[]` where `callee_id === node.id`
- **Callees** — "What does this call?" — derived from `flowData.calls[]` where `caller_id === node.id`, with conditional/loop context
- **Internal Control Flow** — if/else, loops, try/except blocks inside this function, from `flowData.control_flows[]` where `parent_function_id === node.id`
- **Orphan Warning** — if function is in `statistics.orphan_functions`, show "no callers detected" warning

### Blueprint Nodes (API Routes View)
Currently shows: name, url_prefix, route_count

**Expanded detail will add:**
- **File Location** — file_path, line_number (from `routesData.blueprints[]` lookup)
- **Route Listing** — all routes in this blueprint with method badges, URL patterns, function names, and auth status
- **Security Summary** — count of protected vs unprotected routes
- **Method Breakdown** — count of routes by HTTP method

### Route Nodes (API Routes View)
Currently shows: methods, url_pattern, function name, auth badge, docstring preview

**Expanded detail will add:**
- **Full URL** — `routeData.full_url` displayed prominently
- **Full Docstring** — not truncated
- **Path Parameters** — table of param name + type from `routeData.parameters.path_params[]`
- **Security Detail** — auth decorators list (not just boolean), warning if unprotected
- **Blueprint Context** — parent blueprint name/prefix, sibling routes in same blueprint
- **File Location** — file_path, line_number

---

## Implementation Plan

### Step 1: Create `NodeDetailModal.css`
**New file:** `frontend/src/components/project/NodeDetailModal.css`

Copy the overlay/modal/header/animation patterns from `InsightGuide.css` with `.node-detail-` prefix. Add styles for:
- Section headings, content tables, badges, connection lists
- Warning/info callout boxes, monospace code display
- Dark mode variants for all classes

### Step 2: Create detail renderer components
**New directory:** `frontend/src/components/project/nodeDetails/`

Four pure presentational components, each receives `{ node, edges, contextData }`:

- `TableNodeDetail.jsx` — columns table, relationships, foreign keys
- `FunctionNodeDetail.jsx` — identity, signature, complexity, callers/callees, control flow, orphan warning
- `BlueprintNodeDetail.jsx` — identity, route listing, security summary, method breakdown
- `RouteNodeDetail.jsx` — full URL, docstring, path params, security, blueprint context

Each derives rich data by looking up the full record from `contextData`:
```js
// Flow view — look up full function record
const funcDetail = contextData.flowData.functions.find(f => f.id === node.id);

// API view — look up full route/blueprint record
const routeDetail = contextData.routesData.routes.find(r => r.id === node.id);
```

This avoids modifying the transform functions or inflating node data.

### Step 3: Create `NodeDetailModal.jsx`
**New file:** `frontend/src/components/project/NodeDetailModal.jsx`

Shell component following `InsightGuide.jsx` pattern:
- Props: `{ isOpen, onClose, isDark, node, edges, contextData }`
- Same ESC key handler, backdrop click, body scroll lock
- Dynamic header with node-type-appropriate icon, name, and subtitle
- Dispatches to the appropriate detail renderer based on `node.type`:
  - `'default'` + `contextData.schema` → `TableNodeDetail`
  - `'functionNode'` → `FunctionNodeDetail`
  - `'blueprintNode'` → `BlueprintNodeDetail`
  - `'routeNode'` → `RouteNodeDetail`
  - `'stickyNote'` → return null (no detail for sticky notes)

### Step 4: Wire up `FlowVisualization.jsx`
**Modify:** `frontend/src/components/project/FlowVisualization.jsx`

- Add state: `const [detailNode, setDetailNode] = useState(null);`
- Add handler: skip `stickyNote` type, then `setDetailNode(node)`
- Add `onNodeDoubleClick` prop to `<ReactFlow>`
- Render `<NodeDetailModal>` with `contextData={{ flowData }}`

### Step 5: Wire up `ApiRoutesVisualization.jsx`
**Modify:** `frontend/src/components/project/ApiRoutesVisualization.jsx`

Same pattern as Step 4, passing `contextData={{ routesData: routesData }}`

### Step 6: Wire up `ProjectVisualization.jsx` (Schema View)
**Modify:** `frontend/src/components/project/ProjectVisualization.jsx`

- Add `const [schemaData, setSchemaData] = useState(null);` to store raw schema
- Store schema in `createVisualizationFromSchema()` and `createVisualizationWithLayout()` before transforming to nodes
- Add `detailNode` state and `onNodeDoubleClick` handler (skip stickyNote and placeholder node id '1')
- Add `onNodeDoubleClick` prop to schema `<ReactFlow>`
- Render `<NodeDetailModal>` with `contextData={{ schema: schemaData }}`

---

## Key Files

| File | Action |
|------|--------|
| `frontend/src/components/project/NodeDetailModal.jsx` | **Create** — modal shell |
| `frontend/src/components/project/NodeDetailModal.css` | **Create** — styling |
| `frontend/src/components/project/nodeDetails/TableNodeDetail.jsx` | **Create** |
| `frontend/src/components/project/nodeDetails/FunctionNodeDetail.jsx` | **Create** |
| `frontend/src/components/project/nodeDetails/BlueprintNodeDetail.jsx` | **Create** |
| `frontend/src/components/project/nodeDetails/RouteNodeDetail.jsx` | **Create** |
| `frontend/src/components/project/FlowVisualization.jsx` | **Modify** — add double-click + modal |
| `frontend/src/components/project/ApiRoutesVisualization.jsx` | **Modify** — add double-click + modal |
| `frontend/src/components/project/ProjectVisualization.jsx` | **Modify** — add schemaData state + double-click + modal |
| `frontend/src/components/project/InsightGuide.jsx` | **Reference** — modal pattern |
| `frontend/src/components/project/InsightGuide.css` | **Reference** — CSS pattern |

---

## Verification

1. **Schema view** — double-click a table node → modal shows full columns table, relationships, FKs
2. **Flow view** — double-click a function node → modal shows callers/callees, docstring, control flow
3. **API routes view** — double-click a route node → modal shows full URL, params, security detail
4. **API routes view** — double-click a blueprint node → modal shows route listing, security summary
5. **Sticky notes** — double-click a sticky note → nothing happens (no modal)
6. **Dark mode** — toggle theme, verify modal renders correctly in both modes
7. **Dismiss** — ESC key, backdrop click, and close button all close the modal
8. **Coexistence** — InsightGuide and NodeDetailModal don't interfere with each other
