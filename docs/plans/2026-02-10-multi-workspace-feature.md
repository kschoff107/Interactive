# Multi-Workspace Feature Plan

**Date:** February 10, 2026
**Feature:** Multiple workspaces per visualization type
**Status:** Planning

## Context

Currently each visualization type (Database Schema, Runtime Flow, API Routes) has exactly one workspace per project. The user wants multiple workspaces per visualization type so they can analyze different files separately — e.g., multiple runtime flow analyses for different parts of a codebase. Users should also be able to rename workspaces.

## Overview

Add a `workspaces` table and a `workspace_id` column to existing tables. Update the sidebar to show expandable sub-items under each visualization type with add/rename/delete. Each workspace gets its own analysis data and layout.

---

## Phase 1: Database & Backend Models

### 1.1 Add `workspaces` table to `backend/init_db.py`

Add to both `init_postgres_database()` and `init_sqlite_database()`:

```sql
CREATE TABLE IF NOT EXISTS workspaces (
    id SERIAL PRIMARY KEY,  -- (AUTOINCREMENT for SQLite)
    project_id INTEGER NOT NULL,
    analysis_type VARCHAR(50) NOT NULL,
    name VARCHAR(200) NOT NULL,
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);
```

Add `workspace_id` column to `analysis_results`, `workspace_layouts`, `workspace_notes` via migrations block (same pattern as existing `ALTER TABLE` migrations in init_db.py).

Add indexes: `idx_workspaces_project_type ON workspaces(project_id, analysis_type)`.

### 1.2 New model: `backend/models/workspace.py`

Simple data class with `id, project_id, analysis_type, name, sort_order, created_at, updated_at` and `to_dict()`.

### 1.3 Update `backend/models/__init__.py`

Add `Workspace` to imports and `__all__`.

### 1.4 Add `workspace_id` to existing models

Add optional `workspace_id=None` param to `AnalysisResult`, `WorkspaceLayout`, `WorkspaceNote` constructors and `to_dict()`.

---

## Phase 2: Backend API

### 2.1 New file: `backend/routes/workspace_routes.py`

New blueprint `workspaces_bp` with:

| Method | Path | Description |
|--------|------|-------------|
| GET | `/projects/<id>/workspaces` | List workspaces grouped by analysis_type. Auto-creates defaults for existing projects with data but no workspaces. |
| POST | `/projects/<id>/workspaces` | Create workspace. Body: `{analysis_type, name}` |
| PATCH | `/projects/<id>/workspaces/<ws_id>` | Rename. Body: `{name}` |
| DELETE | `/projects/<id>/workspaces/<ws_id>` | Delete (prevent deleting last workspace per type) |

Helper: `get_or_create_default_workspace(cur, project_id, analysis_type)` — looks up first workspace for that type, creates "Default" if none exist, backfills orphaned rows.

### 2.2 Add workspace-scoped data endpoints to `backend/routes/workspace_routes.py`

| Method | Path | Description |
|--------|------|-------------|
| GET | `/projects/<id>/workspaces/<ws_id>/layout` | Get layout for workspace |
| POST | `/projects/<id>/workspaces/<ws_id>/layout` | Save layout for workspace |
| GET | `/projects/<id>/workspaces/<ws_id>/analysis` | Get analysis data for workspace |
| GET | `/projects/<id>/workspaces/<ws_id>/runtime-flow` | Get runtime flow for workspace |
| POST | `/projects/<id>/workspaces/<ws_id>/analyze/runtime-flow` | Run runtime flow analysis, store under workspace |
| GET | `/projects/<id>/workspaces/<ws_id>/api-routes` | Get API routes for workspace |
| POST | `/projects/<id>/workspaces/<ws_id>/analyze/api-routes` | Run API routes analysis, store under workspace |

### 2.3 Register blueprint in `backend/routes/__init__.py`

Add `from .workspace_routes import workspaces_bp` and register with `url_prefix='/api/projects'`.

### 2.4 Keep existing endpoints working (backward compat)

Existing endpoints (`GET /projects/<id>/layout`, `GET /projects/<id>/runtime-flow`, etc.) remain unchanged. They continue to work by defaulting to the first/default workspace internally.

---

## Phase 3: Frontend — API + State

### 3.1 Update `frontend/src/services/api.js`

Add:
```javascript
export const workspacesAPI = {
  list: (projectId) => api.get(`/projects/${projectId}/workspaces`),
  create: (projectId, analysisType, name) =>
    api.post(`/projects/${projectId}/workspaces`, { analysis_type: analysisType, name }),
  rename: (projectId, workspaceId, name) =>
    api.patch(`/projects/${projectId}/workspaces/${workspaceId}`, { name }),
  delete: (projectId, workspaceId) =>
    api.delete(`/projects/${projectId}/workspaces/${workspaceId}`),
  getLayout: (projectId, workspaceId) =>
    api.get(`/projects/${projectId}/workspaces/${workspaceId}/layout`),
  saveLayout: (projectId, workspaceId, layoutData) =>
    api.post(`/projects/${projectId}/workspaces/${workspaceId}/layout`, { layout_data: layoutData }),
};
```

### 3.2 Update `frontend/src/components/project/ProjectVisualization.jsx`

New state:
- `workspaces` — object grouped by analysis_type
- `activeWorkspaceId` — currently selected workspace id

New handlers:
- `loadWorkspaces()` — fetch on mount, auto-select first workspace of active view
- `handleWorkspaceSelect(viewId, workspaceId)` — switch view + workspace, clear cached data
- `handleWorkspaceCreate(analysisType)` — create via API, refresh list, auto-select new one
- `handleWorkspaceRename(workspaceId, newName)` — rename via API, refresh list
- `handleWorkspaceDelete(workspaceId)` — delete via API, refresh list, select neighbor

Update data loading (`loadRuntimeFlowData`, `loadApiRoutesData`, `loadProjectAndVisualization`) to use workspace-scoped endpoints when `activeWorkspaceId` is set.

Update layout save/load to use workspace-scoped endpoints.

Pass new props to Sidebar: `workspaces`, `activeWorkspaceId`, `onWorkspaceSelect`, `onWorkspaceCreate`, `onWorkspaceRename`, `onWorkspaceDelete`.

---

## Phase 4: Frontend — Sidebar UI

### 4.1 Rewrite `frontend/src/components/project/Sidebar.jsx`

Transform from flat list to expandable two-level tree:

```
VISUALIZATIONS
  Database Schema          [+]
    > Default              (active, blue highlight)
    > Auth Tables
  Runtime Flow             [+]
    > Default
  API Routes               [+]
    > Default
  Code Structure           Soon
```

- Each enabled visualization type is expandable (auto-expand when it contains the active workspace)
- "+" button next to each type header to add a workspace
- Clicking a workspace sub-item calls `onWorkspaceSelect(viewId, workspaceId)`
- Double-click workspace name to rename (inline text input, Enter to confirm, Escape to cancel)
- Small "x" or trash icon on hover to delete (with confirmation if it has data)
- Active workspace gets the blue left-border highlight treatment

---

## Files Changed

| File | Action |
|------|--------|
| `backend/init_db.py` | MODIFY — add workspaces table + workspace_id columns |
| `backend/models/workspace.py` | NEW — Workspace model |
| `backend/models/__init__.py` | MODIFY — export Workspace |
| `backend/models/analysis_result.py` | MODIFY — add workspace_id |
| `backend/models/workspace_layout.py` | MODIFY — add workspace_id |
| `backend/models/workspace_note.py` | MODIFY — add workspace_id |
| `backend/routes/workspace_routes.py` | NEW — CRUD + workspace-scoped data endpoints |
| `backend/routes/__init__.py` | MODIFY — register workspaces_bp |
| `frontend/src/services/api.js` | MODIFY — add workspacesAPI |
| `frontend/src/components/project/Sidebar.jsx` | MODIFY — expandable tree with workspace sub-items |
| `frontend/src/components/project/ProjectVisualization.jsx` | MODIFY — workspace state + workspace-aware loading |

## Verification

1. Restart backend — confirm no startup errors, new table created
2. Open app — existing projects should still work (auto-created "Default" workspaces)
3. Sidebar shows expandable workspace list under each visualization type
4. Click "+" to add a new workspace — appears in sidebar
5. Double-click to rename — inline edit works
6. Select different workspaces — each loads its own data/layout independently
7. Run analysis in a new workspace — data saves to that workspace only
8. Delete a workspace — data cleaned up, cannot delete last one
9. Save/load layout per workspace — positions persist independently
