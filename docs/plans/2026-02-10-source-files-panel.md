# Add GitHub Source Panel to Project Sidebar

## Context

Git-imported projects store `git_url` and the imported files on disk, but this information is invisible once the user is on the project visualization page. Adding a collapsible "Source" panel in the left sidebar gives users context about where their code came from and what files were imported — without requiring any additional storage.

## Changes Overview

| File | Action | Purpose |
|------|--------|---------|
| `backend/init_db.py` | Modify | Add `git_branch` column migration |
| `backend/models/project.py` | Modify | Add `git_branch` to model + `to_dict()` |
| `backend/routes/projects.py` | Modify | Persist `git_branch` on import; add `GET /<id>/files` endpoint |
| `frontend/src/services/api.js` | Modify | Add `getFiles(id)` to `projectsAPI` |
| `frontend/src/components/project/SourceFilesPanel.jsx` | Create | Collapsible panel with repo link, branch, file tree |
| `frontend/src/components/project/Sidebar.jsx` | Modify | Accept `project` prop, render `SourceFilesPanel` |
| `frontend/src/components/project/ProjectVisualization.jsx` | Modify | Pass `project` to `Sidebar` |

## Implementation Steps

### Step 1: Add `git_branch` column

The import endpoint already receives `branch` from the frontend but doesn't persist it. Fix this.

**`backend/init_db.py`** — Add to the migrations array (line 133):
```
"ALTER TABLE projects ADD COLUMN IF NOT EXISTS git_branch VARCHAR(100);"
```

**`backend/models/project.py`** — Add `git_branch=None` param to `__init__`, store as `self.git_branch`, add `'git_branch': self.git_branch` to `to_dict()`.

**`backend/routes/projects.py`** — In `import_from_git`, update the SQL at the project metadata UPDATE to also set `git_branch = %s` with the `branch` value.

### Step 2: Backend `GET /files` endpoint

**`backend/routes/projects.py`** — New endpoint that walks the project's `file_path` directory and returns the file list. Uses `os.walk()` with `os.path.relpath()`, normalizing `\\` to `/` for Windows compatibility. Returns `{files: [{path, type, size}], total_count}` — same shape as the git tree endpoint so the frontend `buildFileTree()` logic works for both.

JWT-protected, verifies project ownership. Returns empty array if no files on disk.

### Step 3: Frontend API method

**`frontend/src/services/api.js`** — Add to `projectsAPI`:
```js
getFiles: (id) => api.get(`/projects/${id}/files`),
```

### Step 4: Create `SourceFilesPanel` component

**`frontend/src/components/project/SourceFilesPanel.jsx`** — New component:
- Returns `null` if `project.source_type !== 'git'` (safe to render unconditionally)
- Collapsible header with GitHub icon + "SOURCE" label
- Clickable repo link (`owner/repo` parsed from `git_url`, opens in new tab)
- Branch badge (hidden if `git_branch` is null for older imports)
- Read-only file tree (reuse `buildFileTree()` pattern from `GitImportModal`, no checkboxes)
- File count footer
- Scrollable tree area (`max-h-60 overflow-y-auto`) for the 220px sidebar width
- Full dark mode support, text-xs sizing to fit the sidebar

### Step 5: Wire into Sidebar

**`frontend/src/components/project/Sidebar.jsx`** — Add `project` to props, import `SourceFilesPanel`, render it between `</nav>` and the footer `<div>`.

**`frontend/src/components/project/ProjectVisualization.jsx`** — Pass `project={project}` to the `<Sidebar>` component.

## Verification

1. Run backend tests: `python -m pytest tests/ --tb=short`
2. Build frontend: `npm run build`
3. Start both servers and test with an existing git-imported project — panel should appear with repo link, branch, and file tree
4. Test with a regular uploaded project — panel should not appear
5. Import a new repo — verify branch is persisted and shown
6. Test expand/collapse of folders in the panel
7. Test dark mode
