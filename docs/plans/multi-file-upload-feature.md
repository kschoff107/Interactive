# Implementation Plan: Add Multi-File Upload to Code Visualizer

## Overview
Add the ability to upload additional files to existing projects after initial creation, with separate support for database schema files and runtime flow files. Display a centered upload area in the workspace when the selected analysis type hasn't been uploaded yet.

## User Requirements
1. Allow uploading MORE files after a project is already created (not just during initial upload)
2. Support uploading database schema files separately from runtime flow files
3. Show an upload area in the middle of the workspace if database schema hasn't been uploaded yet
4. Support adding files for either analysis type at any time

## Current Architecture Context
- **Backend**: Flask API with PostgreSQL or SQLite database
- **Frontend**: React with ReactFlow for visualization
- **Storage**: Files in `storage/uploads/<user_id>/<project_id>/`
- **Analysis Types**: Database Schema (SQLAlchemy/SQLite) and Runtime Flow (Python AST)
- **Existing Upload**: `POST /api/projects/<project_id>/upload` (lines 147-209 in routes/projects.py)

---

## Implementation Steps

### 1. Database Schema Changes

#### Add tracking fields to projects table
**File**: `c:\Claude\Interactive\backend\init_db.py`

Add new columns to track file upload status:
```sql
ALTER TABLE projects ADD COLUMN has_database_schema BOOLEAN DEFAULT FALSE;
ALTER TABLE projects ADD COLUMN has_runtime_flow BOOLEAN DEFAULT FALSE;
ALTER TABLE projects ADD COLUMN last_upload_date TIMESTAMP;
```

Update both `init_postgres_database()` and `init_sqlite_database()` functions to include these fields in the CREATE TABLE statements.

#### Create migration script
**File**: `c:\Claude\Interactive\backend\migrations\add_file_tracking.py` (new file)

Create a migration script that:
- Checks if columns exist
- Adds them if missing
- Sets initial values based on existing analysis_results

### 2. Backend API Enhancements

#### Modify upload endpoint to support additional uploads
**File**: `c:\Claude\Interactive\backend\routes\projects.py` (lines 147-209)

**Changes needed**:
1. Add optional `file_type` parameter from request form: `database_schema` | `runtime_flow` | `auto`
2. Check for duplicate filenames before saving
3. Update project metadata fields (has_database_schema, has_runtime_flow, last_upload_date)
4. Support multiple analysis types in same project
5. Return enhanced response with project status

**Enhanced response format**:
```python
{
    "message": "Files uploaded and analyzed",
    "uploads": [
        {"filename": "models.py", "status": "success", "file_type": "sqlalchemy"}
    ],
    "project_status": {
        "has_database_schema": True,
        "has_runtime_flow": False
    },
    "language": "python",
    "framework": "sqlalchemy",
    "schema": {...}  # or "flow": {...}
}
```

#### Add new endpoint: Get project status
**File**: `c:\Claude\Interactive\backend\routes\projects.py` (new endpoint)

```python
@projects_bp.route('/<int:project_id>/status', methods=['GET'])
@jwt_required()
def get_project_status(project_id):
    """Get project file upload status"""
    # Return: has_database_schema, has_runtime_flow, file counts, last_upload_date
```

#### Update analysis logic to handle incremental uploads
**File**: `c:\Claude\Interactive\backend\routes\projects.py` (upload endpoint)

Logic to determine analysis type:
1. If `file_type` parameter provided, use it
2. If `file_type='auto'` or not provided, detect based on file extensions:
   - `.db`, `.sqlite`, `.sqlite3` → database_schema (SQLite)
   - `.py` with SQLAlchemy imports → database_schema (SQLAlchemy)
   - `.py` without ORM → runtime_flow
3. Update appropriate `has_*` field after successful analysis

### 3. Frontend UI Changes

#### Add state management for project status
**File**: `c:\Claude\Interactive\frontend\src\components\project\ProjectVisualization.jsx`

Add new state variables (around line 36):
```javascript
const [projectStatus, setProjectStatus] = useState({
  has_database_schema: false,
  has_runtime_flow: false,
  last_upload_date: null
});
const [showUploadArea, setShowUploadArea] = useState(false);
```

#### Fetch project status on mount
Add new useEffect after line 72:
```javascript
useEffect(() => {
  const fetchProjectStatus = async () => {
    try {
      const response = await api.get(`/projects/${projectId}/status`);
      setProjectStatus(response.data);
    } catch (error) {
      console.error('Error fetching project status:', error);
    }
  };
  fetchProjectStatus();
}, [projectId]);
```

#### Implement conditional upload area display
Add logic to determine when to show upload area:
```javascript
useEffect(() => {
  // Show upload area if current view's analysis type is missing
  const shouldShow =
    (activeView === 'schema' && !projectStatus.has_database_schema) ||
    (activeView === 'flow' && !projectStatus.has_runtime_flow);
  setShowUploadArea(shouldShow);
}, [activeView, projectStatus]);
```

#### Create centered upload area component
**File**: `c:\Claude\Interactive\frontend\src\components\project\CenterUploadArea.jsx` (new file)

Component features:
- Drag-and-drop file upload using react-dropzone
- Display appropriate message based on analysis type
- Show upload progress indicator
- Display success/error messages
- Automatically refresh view after successful upload
- Centered in workspace with attractive styling

Props:
- `projectId`: Current project ID
- `analysisType`: 'database_schema' or 'runtime_flow'
- `onUploadComplete`: Callback to refresh parent component

#### Integrate upload area into ProjectVisualization
**File**: `c:\Claude\Interactive\frontend\src\components\project\ProjectVisualization.jsx`

Around the ReactFlow render section (estimate line 400+), add conditional rendering:

```javascript
<div className="visualization-workspace">
  {showUploadArea ? (
    <CenterUploadArea
      projectId={projectId}
      analysisType={activeView === 'schema' ? 'database_schema' : 'runtime_flow'}
      onUploadComplete={handleUploadComplete}
    />
  ) : (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      // ... existing props
    />
  )}
</div>
```

Add upload complete handler:
```javascript
const handleUploadComplete = async (result) => {
  // Update project status
  setProjectStatus(result.project_status);
  // Reload visualization data
  await loadProjectAndVisualization();
  toast.success('Files uploaded and analyzed successfully!');
};
```

#### Add "Add More Files" button (optional enhancement)
In the toolbar area, add a button that's always visible:
```javascript
<button
  className="add-files-btn"
  onClick={() => setShowAddFilesModal(true)}
  title="Upload additional files"
>
  + Add Files
</button>
```

This provides an alternative way to upload files even when visualization is already showing.

### 4. Styling

#### Create CSS for CenterUploadArea
**File**: `c:\Claude\Interactive\frontend\src\components\project\CenterUploadArea.css` (new file)

Styles needed:
- Centered container (flexbox center)
- Drag-drop zone with dashed border
- Hover state for drag-over
- Upload icon/emoji
- Progress indicator (spinner)
- Success/error message styling
- Responsive design

### 5. Project Model Update

**File**: `c:\Claude\Interactive\backend\models\project.py`

Update the `__init__` method to include new fields:
```python
def __init__(self, id, user_id, name, description, source_type, git_url,
             file_path, language, framework, created_at, updated_at,
             has_database_schema=False, has_runtime_flow=False,
             last_upload_date=None):
    # ... existing assignments
    self.has_database_schema = has_database_schema
    self.has_runtime_flow = has_runtime_flow
    self.last_upload_date = last_upload_date
```

Update `to_dict()` method to include new fields in the return dictionary.

---

## Critical Files to Modify

1. **c:\Claude\Interactive\backend\init_db.py** - Add new columns to projects table schema
2. **c:\Claude\Interactive\backend\routes\projects.py** - Enhance upload endpoint (lines 147-209) and add status endpoint
3. **c:\Claude\Interactive\backend\models\project.py** - Add new fields to Project model
4. **c:\Claude\Interactive\frontend\src\components\project\ProjectVisualization.jsx** - Add state management and conditional rendering
5. **c:\Claude\Interactive\frontend\src\components\project\CenterUploadArea.jsx** - New component for centered upload UI

---

## Edge Cases & Error Handling

1. **Duplicate Files**: Check for existing files with same name, optionally allow overwriting
2. **Mixed Analysis Types**: Support both database schema and runtime flow in same project
3. **Analysis Failures**: Show clear error messages, don't block UI
4. **No Files Selected**: Disable upload button until files are selected
5. **Network Errors**: Show retry option on upload failure
6. **Large Files**: Show upload progress for files >1MB

---

## Verification Steps

### Backend Testing
1. Start backend server: `cd c:\Claude\Interactive\backend && python app.py`
2. Test upload endpoint with curl or Postman:
   ```bash
   # Upload database schema files
   curl -X POST http://localhost:5000/api/projects/1/upload \
     -H "Authorization: Bearer <token>" \
     -F "files=@models.py" \
     -F "file_type=database_schema"

   # Upload runtime flow files
   curl -X POST http://localhost:5000/api/projects/1/upload \
     -H "Authorization: Bearer <token>" \
     -F "files=@app.py" \
     -F "file_type=runtime_flow"
   ```
3. Verify database updates: Check projects table for has_database_schema and has_runtime_flow flags
4. Test status endpoint: `GET /api/projects/1/status`

### Frontend Testing
1. Start frontend server: `cd c:\Claude\Interactive\frontend && npm start`
2. Create a new project without uploading files initially (if initial upload is optional)
3. Navigate to project workspace
4. Verify upload area appears when switching to Database Schema view (if no schema uploaded)
5. Drag and drop database files (.py with SQLAlchemy or .db files)
6. Verify upload progress indicator appears
7. Verify success message and automatic view refresh
8. Switch to Runtime Flow view
9. Verify upload area appears (if no runtime flow uploaded)
10. Upload Python source files
11. Verify both views now work with uploaded data

### Integration Testing
1. Upload database schema files → Verify schema view displays tables
2. Upload runtime flow files → Verify flow view displays function graph
3. Upload additional files to existing project → Verify incremental analysis works
4. Test with both SQLAlchemy models and SQLite databases in same project
5. Test error handling: Upload invalid file types, upload with network disconnected
6. Test UI responsiveness: Ensure upload area is properly centered and responsive

### End-to-End User Flow
1. User creates project and uploads only runtime flow files initially
2. User views runtime flow visualization
3. User switches to "Database Schema" view
4. System shows centered upload area with message: "Upload Database Schema Files"
5. User drags SQLAlchemy models.py file into area
6. Upload progress indicator shows
7. Success message appears
8. View automatically refreshes showing database schema visualization
9. User can now switch between both views seamlessly

---

## Implementation Sequence

1. **Backend Foundation** (Database & Models)
   - Add columns to projects table
   - Update Project model
   - Create migration script
   - Test database changes

2. **Backend API** (Routes & Logic)
   - Enhance upload endpoint
   - Add status endpoint
   - Update analysis logic
   - Test endpoints with Postman

3. **Frontend Component** (CenterUploadArea)
   - Create CenterUploadArea.jsx
   - Create CenterUploadArea.css
   - Test component in isolation

4. **Frontend Integration** (ProjectVisualization)
   - Add state management
   - Add status fetching
   - Implement conditional rendering
   - Test integration

5. **End-to-End Testing**
   - Test complete upload flow
   - Test edge cases
   - Fix any issues
   - Polish UI/UX

---

## Success Criteria

✅ User can upload additional files after project creation
✅ Upload area appears in center when analysis type is missing
✅ Database schema and runtime flow files can be uploaded separately
✅ Multiple file uploads work correctly
✅ Analysis runs automatically after upload
✅ UI updates immediately after successful upload
✅ Error messages are clear and actionable
✅ Both SQLite and PostgreSQL databases work correctly
