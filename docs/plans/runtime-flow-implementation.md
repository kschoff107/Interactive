# Runtime Flow Visualization - Implementation Plan

## Implementation Status

**Last Updated:** February 6, 2026

### ✅ Phase 1: Backend Parser (COMPLETE)
- **Status:** Committed to master (commit: 08bab91)
- **Completed:** February 6, 2026
- **Files Created:**
  - `backend/parsers/runtime_flow_parser.py` - Full AST-based Python parser
  - `backend/parsers/parser_manager.py` - Integration complete
- **Testing:** Verified with sample Flask app, all features working
- **Details:** See Phase 1 section below

### ✅ Phase 2: Backend API (COMPLETE)
- **Status:** COMPLETE (February 6, 2026)
- **Completed:** February 6, 2026
- **Tasks:**
  - ✅ Add REST API endpoints to `backend/routes/projects.py`
  - ✅ Store runtime flow analysis in database
  - ✅ Error handling and validation
- **Files Modified:**
  - `backend/routes/projects.py` - Added two new endpoints
- **Testing:** All 8 unit tests passing

### 🔄 Phase 3: Frontend Visualization (NEXT)
- **Status:** TODO - Start next session
- **Priority:** HIGH

### ⏳ Phase 4: Integration (PENDING)
- **Status:** TODO

### ⏳ Phase 5: Advanced Features (PENDING)
- **Status:** TODO

---

## Overview

Add Runtime Flow visualization to the Code Visualizer application, enabling users to visualize Python code execution paths, function call hierarchies, and control flow structures using Python AST analysis and ReactFlow.

## Architecture

### Backend Components
1. **RuntimeFlowParser** - Python AST-based code analyzer
   - Extracts function definitions, calls, and control flow
   - Follows existing SQLAlchemyParser pattern
   - Location: `backend/parsers/runtime_flow_parser.py`

2. **API Endpoints**
   - `POST /api/projects/<id>/analyze/runtime-flow` - Trigger analysis
   - `GET /api/projects/<id>/runtime-flow` - Retrieve results
   - Stores results as `analysis_type='runtime_flow'` in database

3. **ParserManager Enhancement**
   - Detect Python projects for runtime analysis
   - Route to RuntimeFlowParser

### Frontend Components
1. **FlowVisualization.jsx** - Main component
   - Uses ReactFlow with custom node types
   - Fetches flow data from API
   - Applies dagre layout algorithm

2. **Custom Node Types**
   - FunctionNode - Standard functions (blue rectangles)
   - ConditionalNode - If/else blocks (orange diamonds)
   - LoopNode - For/while loops (green circles)
   - TryNode - Try/except blocks (red hexagons)

3. **Integration**
   - Update ProjectVisualization.jsx to support view switching
   - Reuse existing layout persistence and sticky notes

## Data Structures

### Function Node
```json
{
  "id": "func_<module>_<name>_<line>",
  "type": "function",
  "name": "process_order",
  "module": "routes.orders",
  "file_path": "routes/orders.py",
  "line_number": 45,
  "parameters": ["order_id", "user_id"],
  "decorators": ["@login_required"],
  "complexity": 12
}
```

### Function Call
```json
{
  "id": "call_<from>_to_<to>_<line>",
  "caller_id": "func_routes_process_order_45",
  "callee_id": "func_db_save_order_120",
  "line_number": 52,
  "is_conditional": true
}
```

### Control Flow
```json
{
  "id": "ctrl_<type>_<file>_<line>",
  "flow_type": "if_else",
  "parent_function_id": "func_routes_process_order_45",
  "condition": "order.status == 'pending'",
  "branches": ["if", "else"]
}
```

## Implementation Phases

### Phase 1: Backend Parser ✅ COMPLETE
**Status**: COMPLETE (February 6, 2026)
**Goal**: Create Python AST parser to extract flow data

**Tasks**:
1. ✅ Create `backend/parsers/runtime_flow_parser.py`
   - ✅ Implement `FlowVisitor` class using `ast.NodeVisitor`
   - ✅ Extract function definitions (FunctionDef, AsyncFunctionDef)
   - ✅ Extract function calls (Call nodes)
   - ✅ Extract control flow (If, For, While, Try nodes)
   - ✅ Track imports for call resolution

2. ✅ Implement call resolution
   - ✅ Resolve local function calls
   - ✅ Resolve imported function calls
   - ✅ Mark external library calls

3. ✅ Add to ParserManager
   - ✅ Detect Python projects
   - ✅ Route to RuntimeFlowParser
   - ✅ Return structured flow data

**Testing**: ✅ Tested with sample Flask application - all features working correctly

**Deliverables**:
- `backend/parsers/runtime_flow_parser.py` (583 lines)
- Updated `backend/parsers/parser_manager.py`
- Successfully extracts: 6 functions, 14 calls, 8 control flows
- Correctly identifies: async functions, decorators, entry points
- Calculates: complexity, call depth, circular dependencies

### Phase 2: Backend API ✅ COMPLETE
**Status**: COMPLETE (February 6, 2026)
**Priority**: HIGH
**Goal**: Add API endpoints for flow analysis

**Tasks**:
1. ✅ Add analysis endpoint in `backend/routes/projects.py`
   - ✅ `POST /api/projects/<id>/analyze/runtime-flow`
   - ✅ Trigger RuntimeFlowParser
   - ✅ Store results in `analysis_results` table with `analysis_type='runtime_flow'`
   - ✅ Error handling for missing files and unsupported frameworks

2. ✅ Add retrieval endpoint
   - ✅ `GET /api/projects/<id>/runtime-flow`
   - ✅ Return cached analysis results
   - ✅ Return 404 if no analysis found

3. ✅ Error handling and validation
   - ✅ Verify project ownership
   - ✅ Check file path exists
   - ✅ Handle parser errors gracefully
   - ✅ Return appropriate HTTP status codes

**Implementation Details**:
- Added `analyze_runtime_flow()` endpoint at line 234 of `backend/routes/projects.py`
- Added `get_runtime_flow()` endpoint at line 267 of `backend/routes/projects.py`
- Both endpoints require JWT authentication via `@jwt_required()` decorator
- Analysis results stored in existing `analysis_results` table
- Reuses existing `ParserManager.parse_runtime_flow()` method

**Testing**: ✅ Complete - All 8 unit tests passing
- Created `backend/tests/test_runtime_flow_api.py` with comprehensive test coverage:
  - ✅ test_analyze_runtime_flow - Happy path analysis
  - ✅ test_get_runtime_flow - Happy path retrieval
  - ✅ test_get_runtime_flow_not_analyzed - Error case: no analysis
  - ✅ test_analyze_runtime_flow_no_files - Error case: no files uploaded
  - ✅ test_analyze_runtime_flow_unauthorized - Security: missing auth
  - ✅ test_get_runtime_flow_unauthorized - Security: missing auth
  - ✅ test_runtime_flow_data_persistence - Data integrity
  - ✅ test_multiple_analyses - Repeated analysis handling

### Phase 3: Frontend Visualization (Priority: HIGH)
**Goal**: Create ReactFlow visualization component

**Tasks**:
1. Create `frontend/src/components/project/FlowVisualization.jsx`
   - Fetch flow data from API
   - Transform to ReactFlow nodes/edges format
   - Apply dagre layout algorithm
   - Render with ReactFlow

2. Create custom node components
   - `frontend/src/components/project/nodes/FunctionNode.jsx`
   - `frontend/src/components/project/nodes/ConditionalNode.jsx`
   - `frontend/src/components/project/nodes/LoopNode.jsx`
   - `frontend/src/components/project/nodes/TryNode.jsx`

3. Data transformation utilities
   - Convert functions → nodes
   - Convert calls → edges
   - Apply styling and colors

4. Layout utilities
   - Integrate dagre for hierarchical layout
   - Handle circular dependencies
   - Apply node spacing

**Testing**: Component tests with mock data

### Phase 4: Integration (Priority: MEDIUM)
**Goal**: Integrate with existing UI

**Tasks**:
1. Update `ProjectVisualization.jsx`
   - Support activeView switching ('schema' vs 'flow')
   - Render appropriate component based on view
   - Maintain state between switches

2. Trigger analysis flow
   - Add "Analyze Runtime Flow" button or auto-trigger
   - Show loading state during analysis
   - Handle errors gracefully

3. Layout persistence
   - Reuse existing workspace_layouts system
   - Save/restore flow node positions
   - Persist sticky notes

**Testing**: E2E tests for full flow

### Phase 5: Advanced Features (Priority: LOW)
**Goal**: Add polish and advanced functionality

**Tasks**:
1. Node details panel
   - Show function metadata on click
   - Display call relationships
   - Link to source code

2. Search and filter
   - Search functions by name
   - Filter by module
   - Show entry points only

3. Call chain highlighting
   - Highlight callers/callees
   - Show call depth
   - Visualize execution paths

4. Complexity visualization
   - Color-code by cyclomatic complexity
   - Add complexity legend
   - Show statistics

**Testing**: User acceptance testing

## Critical Files

### To Create
- `backend/parsers/runtime_flow_parser.py` - Core AST parser
- `frontend/src/components/project/FlowVisualization.jsx` - Main visualization
- `frontend/src/components/project/nodes/FunctionNode.jsx` - Function node type
- `frontend/src/components/project/nodes/ConditionalNode.jsx` - Conditional node
- `frontend/src/components/project/nodes/LoopNode.jsx` - Loop node
- `frontend/src/components/project/nodes/TryNode.jsx` - Try/except node

### To Modify
- `backend/parsers/parser_manager.py` - Add Python flow detection
- `backend/routes/projects.py` - Add flow analysis endpoints
- `frontend/src/components/project/ProjectVisualization.jsx` - Integrate flow view

## Technical Challenges

### 1. Circular Dependencies
**Solution**: Detect cycles using DFS, mark circular edges with dashed styling

### 2. Dynamic Call Resolution
**Solution**: Mark unresolved calls as "external" or "unresolved", focus on static patterns

### 3. Large Graph Performance
**Solution**: Module clustering, depth filtering, virtual scrolling, progressive rendering

### 4. Cross-File Imports
**Solution**: Build import graph first, resolve using project structure and imports

## Verification

### Backend Verification
1. Upload Python Flask project
2. Trigger runtime flow analysis via API
3. Verify analysis_results table contains flow data
4. Check data structure matches expected format
5. Verify function definitions extracted correctly
6. Verify function calls resolved properly

### Frontend Verification
1. Navigate to project visualization
2. Click "Runtime Flow" in sidebar
3. Verify flow graph renders with nodes and edges
4. Test node dragging and repositioning
5. Test "Quick Organize" layout button
6. Test "Save Layout" persistence
7. Verify sticky notes work on flow view
8. Test dark mode toggle

### Integration Verification
1. Upload project → Analyze flow → Visualize
2. Switch between Database Schema and Runtime Flow views
3. Verify layout persists when switching views
4. Test search and filter functionality
5. Test node detail panel
6. Verify call chain highlighting works

## Success Criteria

1. ✅ Backend parser successfully extracts functions and calls from Python code
2. ✅ API endpoints return structured flow data
3. ✅ Frontend renders interactive flow graph
4. ✅ Custom node types display correctly (function, conditional, loop, try)
5. ✅ Layout algorithm positions nodes hierarchically
6. ✅ Users can drag nodes and save positions
7. ✅ Circular dependencies are detected and visualized
8. ✅ Integration with existing sidebar navigation works
9. ✅ Performance acceptable for projects up to 500 functions

## Dependencies

### Backend
- Python `ast` module (built-in)
- Existing Flask, SQLite/PostgreSQL setup

### Frontend
- `reactflow` (already installed: ^11.11.4)
- `dagre` (already installed: ^0.8.5)
- Existing React, Tailwind setup

## Estimated Timeline

- Phase 1 (Backend Parser): 1-2 weeks
- Phase 2 (Backend API): 1 week
- Phase 3 (Frontend Visualization): 2 weeks
- Phase 4 (Integration): 1 week
- Phase 5 (Advanced Features): 2 weeks
- **Total**: 7-8 weeks

## Notes

- Start with Phase 1 backend parser as foundation
- Phase 3 frontend can begin in parallel once data structures are defined
- Focus on Flask projects initially, expand to Django/FastAPI later
- Reuse existing patterns from database schema visualization
- Follow existing code style and architecture
