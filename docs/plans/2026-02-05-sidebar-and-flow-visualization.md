# Sidebar Navigation and Flow Visualization Implementation Plan

**Date:** 2026-02-05
**Status:** Planning Phase
**Related:** 2026-02-04-code-visualizer-design.md

## Overview

Implement a left sidebar navigation system to switch between different visualization types, with initial focus on adding Runtime Flow visualization alongside the existing Database Schema view.

## Current State

### What We Have
- Database Schema visualization (fully functional)
  - ReactFlow-based node/edge visualization
  - Table nodes with columns and relationships
  - Sticky notes feature
  - Layout management (save/load, quick organize, undo)
  - Dark mode support

- Single view mode
  - No navigation between different visualization types
  - Header subtitle hardcoded to "Database Schema Visualization"

### What We Need
- Left sidebar navigation
- Multiple visualization types (Database Schema, Runtime Flow, API Routes, Code Structure)
- View switching logic
- Flow visualization implementation

---

## Design Specifications

### Sidebar Layout

```
┌──────────────┬─────────────────────────────────┐
│              │                                 │
│  Sidebar     │  Main Workspace                 │
│  (220px)     │  (flex-1)                       │
│              │                                 │
│  • DB Schema │  [ReactFlow Canvas]             │
│  • Flow      │                                 │
│  • API       │                                 │
│  • Structure │                                 │
│              │                                 │
└──────────────┴─────────────────────────────────┘
```

### Navigation Items

1. **Database Schema** (Active - Already Implemented)
   - Icon: Database icon
   - Shows table relationships and schema structure
   - Current functionality remains unchanged

2. **Runtime Flow** (To Implement)
   - Icon: Flow/Process icon
   - Shows code execution flow
   - Function call chains
   - Control flow visualization

3. **API Routes** (Future - Grayed Out)
   - Icon: API/Network icon
   - Placeholder for future implementation
   - Shows REST endpoints and their relationships

4. **Code Structure** (Future - Grayed Out)
   - Icon: Code/File tree icon
   - Placeholder for future implementation
   - Shows file/folder/module relationships

---

## Implementation Tasks

### Phase 1: Sidebar Component (Priority: High)

**File to Create:** `frontend/src/components/project/Sidebar.jsx`

**Features:**
- [ ] Create Sidebar component with navigation items
- [ ] Active state highlighting
- [ ] Icon support for each navigation type
- [ ] Hover states and transitions
- [ ] Dark mode styling
- [ ] Disabled state for future items (API Routes, Code Structure)
- [ ] Responsive behavior (optional: collapse on mobile)

**Props Interface:**
```javascript
{
  activeView: 'schema' | 'flow' | 'api' | 'structure',
  onViewChange: (view) => void,
  disabled: string[] // List of disabled view types
}
```

**Styling Requirements:**
- Width: 220px fixed
- Background: white (light) / gray-800 (dark)
- Border-right: gray-200 (light) / gray-700 (dark)
- Active item: blue-50 (light) / blue-900 (dark) background
- Active indicator: 3px blue-600 left border
- Hover effect on enabled items
- Opacity 50% for disabled items

### Phase 2: View State Management (Priority: High)

**File to Update:** `frontend/src/components/project/ProjectVisualization.jsx`

**Changes Needed:**
- [ ] Add state: `const [activeView, setActiveView] = useState('schema');`
- [ ] Import and integrate Sidebar component
- [ ] Update layout structure (flex row with sidebar + main content)
- [ ] Conditional rendering based on activeView
- [ ] Update header subtitle to reflect active view
- [ ] Maintain existing functionality for schema view

**Layout Structure:**
```jsx
<div className="h-screen flex flex-col">
  <Header />
  <div className="flex-1 flex">
    <Sidebar activeView={activeView} onViewChange={setActiveView} />
    <div className="flex-1">
      {activeView === 'schema' && <SchemaVisualization />}
      {activeView === 'flow' && <FlowVisualization />}
      {activeView === 'api' && <PlaceholderView />}
      {activeView === 'structure' && <PlaceholderView />}
    </div>
  </div>
  <Footer />
</div>
```

### Phase 3: Flow Visualization (Priority: Medium)

**Approach Options:**

#### Option A: Extract Existing Code (Recommended for MVP)
- Create `frontend/src/components/project/SchemaVisualization.jsx`
- Move current database schema logic into this component
- Keep ReactFlow infrastructure
- Create separate `FlowVisualization.jsx` with similar structure

#### Option B: Unified Component with Props
- Single visualization component that renders different node types
- Pass visualization type as prop
- Different node factories based on type

**Flow Visualization Requirements:**
- [ ] Create FlowVisualization component
- [ ] Define flow node types (function, conditional, loop, return)
- [ ] Create sample/placeholder data structure
- [ ] Implement basic flow rendering
- [ ] Add flow-specific styling (different colors, shapes)
- [ ] Support same interaction patterns (pan, zoom, drag)
- [ ] Reuse sticky notes, layout controls

**Data Structure for Flow:**
```javascript
{
  functions: [
    {
      name: 'functionName',
      file: 'path/to/file.py',
      line: 42,
      calls: ['otherFunction'],
      called_by: ['parentFunction']
    }
  ],
  control_flow: [
    {
      type: 'conditional' | 'loop' | 'try-catch',
      location: { file, line },
      branches: []
    }
  ]
}
```

### Phase 4: Backend Support for Flow Data (Priority: Low)

**Files to Update:**
- `backend/analyzers/python_analyzer.py` (or language-specific)
- `backend/routes/projects.py`

**Backend Tasks:**
- [ ] Add flow analysis endpoint: `GET /projects/:id/flow`
- [ ] Parse code to extract function calls
- [ ] Identify control flow structures
- [ ] Return structured flow data
- [ ] Cache analysis results

**API Response Format:**
```json
{
  "flow": {
    "functions": [...],
    "control_flow": [...],
    "relationships": [
      {
        "from": "functionA",
        "to": "functionB",
        "type": "calls"
      }
    ]
  }
}
```

---

## Technical Considerations

### ReactFlow Integration
- Both Schema and Flow views use ReactFlow
- Share common infrastructure (Controls, MiniMap, Background)
- Different node types registered in nodeTypes object
- Separate edge styling for different visualization types

### State Management
- activeView state in ProjectVisualization
- Separate data/nodes/edges state for each visualization type
- Preserve layout when switching views (if applicable)
- Clear separation between view types

### Performance
- Lazy load visualization data
- Only fetch flow data when Flow view is activated
- Memoize expensive computations
- Efficient node rendering

### User Experience
- Smooth transitions between views
- Preserve unsaved changes warning when switching views
- Loading states when fetching data
- Empty states for views with no data
- Clear visual feedback for active view

---

## Implementation Order (Recommended)

### Day 1: Foundation
1. Create Sidebar component (1-2 hours)
2. Update ProjectVisualization layout structure (30 min)
3. Add view switching state management (30 min)
4. Test navigation between views (30 min)

### Day 2: Schema Refactor
5. Extract schema visualization into separate component (1 hour)
6. Ensure all existing functionality works (1 hour)
7. Test schema view thoroughly (30 min)

### Day 3: Flow Visualization
8. Create FlowVisualization component skeleton (1 hour)
9. Add placeholder/sample data (30 min)
10. Implement basic flow node rendering (2 hours)
11. Add flow-specific controls (1 hour)

### Day 4: Polish & Backend (Optional)
12. Add backend flow analysis endpoint (2-3 hours)
13. Connect frontend to backend (1 hour)
14. Polish UI/UX (1 hour)
15. Update documentation (30 min)

---

## File Structure After Implementation

```
frontend/src/components/project/
├── ProjectVisualization.jsx      # Main container with sidebar
├── Sidebar.jsx                   # NEW: Navigation sidebar
├── SchemaVisualization.jsx       # NEW: Extracted from ProjectVisualization
├── FlowVisualization.jsx         # NEW: Runtime flow view
├── StickyNote.jsx                # Existing: Shared across views
└── PlaceholderView.jsx           # NEW: For future views

backend/routes/
└── projects.py                   # Add /projects/:id/flow endpoint

backend/analyzers/
└── flow_analyzer.py              # NEW: Extract flow data from code
```

---

## Questions to Resolve

1. **Flow Data Source**: Should we analyze uploaded code or use sample data initially?
   - **Recommendation**: Start with sample data, add real analysis later

2. **View Switching Behavior**: Should we preserve layout when switching views?
   - **Recommendation**: No, each view has independent layout

3. **Shared vs Separate State**: Should views share nodes/edges or have separate state?
   - **Recommendation**: Separate state, cleaner separation of concerns

4. **Sticky Notes**: Should sticky notes persist across views or be view-specific?
   - **Recommendation**: View-specific, saved per view type

5. **URL Routing**: Should view type be in URL (e.g., `/project/:id/flow`)?
   - **Recommendation**: No for MVP, add later if needed

---

## Success Criteria

### Minimum Viable Product (MVP)
- ✅ Sidebar renders with 4 navigation items
- ✅ Can switch between Schema and Flow views
- ✅ Schema view maintains all existing functionality
- ✅ Flow view renders with placeholder data
- ✅ Visual feedback for active view
- ✅ Dark mode support for all new components

### Full Implementation
- ✅ All MVP criteria
- ✅ Flow visualization with sample function call data
- ✅ Flow-specific node types and styling
- ✅ Backend endpoint for flow analysis
- ✅ Real code analysis (not just placeholder)
- ✅ Comprehensive testing

---

## Next Steps

1. Review this plan with team/stakeholders
2. Confirm approach (Option A vs B for visualization components)
3. Begin Phase 1: Sidebar component implementation
4. Create Git branch: `feature/sidebar-and-flow-visualization`
5. Implement incrementally with commits after each phase

---

## Notes

- Keep commits small and focused
- Test thoroughly after each phase
- Maintain backward compatibility with existing schema view
- Document any new APIs or data structures
- Update design doc after implementation
