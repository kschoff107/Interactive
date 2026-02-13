# Fix Edge Readability in Flow Visualizations

## Context

In the Runtime Flow and API Routes visualizations, edges overlap and tangle when there are many connections, making it impossible to trace which node connects to which. The root causes are:

1. **`smoothstep` edges share orthogonal paths** — when multiple edges have similar source/target positions, they overlap on the same intermediate horizontal/vertical segments
2. **Single handle per side** — all outgoing edges exit from exactly the same pixel at Position.Bottom
3. **Modest Dagre spacing** — nodes are close together, compressing edge routing space
4. **No interactivity** — no way to hover/select to trace individual connections

## Solution: 3 Changes

### 1. Interactive Highlighting (highest impact)

Create a shared `useEdgeHighlighting` hook:
- **Node hover** → highlight connected edges + connected nodes, dim everything else
- **Edge hover** → highlight that edge + its source/target nodes, dim everything else
- **Mouse leave** → restore normal state
- Applied as a presentation layer (opacity styles) — does NOT modify canonical node/edge state
- Uses `useMemo` for performance (O(nodes + edges) per hover change)

### 2. Increased Layout Spacing

Give edges more room to route without overlapping:
- **FlowVisualization**: `nodesep` 100→160, `ranksep` 150→220
- **ApiRoutesVisualization**: `nodesep` 80→120, `ranksep` 100→160
- Saved layouts are unaffected (applySavedLayout overrides Dagre positions)

### 3. Thinner Default Edges + CSS Transitions

- Default `strokeWidth` from 2→1.5 and add `opacity: 0.7` so overlapping edges look less dense
- Highlighted edges get `strokeWidth: 3` and `opacity: 1` for clear focus
- CSS transitions on `.react-flow__edge path` and `.react-flow__node` for smooth fading
- Wider invisible edge hover target (20px) so users don't need pixel-perfect aim

## Files to Change

| File | Change |
|------|--------|
| `frontend/src/hooks/useEdgeHighlighting.js` | **NEW** — shared hook for hover highlighting |
| `frontend/src/components/project/FlowVisualization.jsx` | Import hook, pass highlighted data + event handlers to ReactFlow, increase Dagre spacing |
| `frontend/src/components/project/ApiRoutesVisualization.jsx` | Import hook (composed with existing method filter), pass highlighted data + event handlers, increase Dagre spacing |
| `frontend/src/utils/flowTransform.js` | Edge style: `strokeWidth: 1.5`, `opacity: 0.7` |
| `frontend/src/utils/apiRoutesTransform.js` | Edge style: `strokeWidth: 1.5`, `opacity: 0.7` |
| `frontend/src/index.css` | CSS transitions for edges/nodes, widen edge hover target |

## Implementation Steps

### Step 1: Create `frontend/src/hooks/useEdgeHighlighting.js`

```javascript
import { useState, useMemo, useCallback } from 'react';

export function useEdgeHighlighting(nodes, edges) {
  const [hoveredElement, setHoveredElement] = useState(null);

  // Build adjacency map (rebuilds only when edges change)
  const { nodeToEdges, edgeEndpoints } = useMemo(() => {
    const nodeToEdges = new Map();
    const edgeEndpoints = new Map();
    edges.forEach(edge => {
      edgeEndpoints.set(edge.id, { source: edge.source, target: edge.target });
      if (!nodeToEdges.has(edge.source)) nodeToEdges.set(edge.source, new Set());
      if (!nodeToEdges.has(edge.target)) nodeToEdges.set(edge.target, new Set());
      nodeToEdges.get(edge.source).add(edge.id);
      nodeToEdges.get(edge.target).add(edge.id);
    });
    return { nodeToEdges, edgeEndpoints };
  }, [edges]);

  // Compute active sets from hovered element
  const { activeNodeIds, activeEdgeIds } = useMemo(() => {
    if (!hoveredElement) return { activeNodeIds: null, activeEdgeIds: null };
    const activeNodeIds = new Set();
    const activeEdgeIds = new Set();

    if (hoveredElement.type === 'node') {
      activeNodeIds.add(hoveredElement.id);
      (nodeToEdges.get(hoveredElement.id) || new Set()).forEach(edgeId => {
        activeEdgeIds.add(edgeId);
        const ep = edgeEndpoints.get(edgeId);
        if (ep) { activeNodeIds.add(ep.source); activeNodeIds.add(ep.target); }
      });
    } else {
      activeEdgeIds.add(hoveredElement.id);
      const ep = edgeEndpoints.get(hoveredElement.id);
      if (ep) { activeNodeIds.add(ep.source); activeNodeIds.add(ep.target); }
    }
    return { activeNodeIds, activeEdgeIds };
  }, [hoveredElement, nodeToEdges, edgeEndpoints]);

  // Apply highlighting to nodes
  const highlightedNodes = useMemo(() => {
    if (!activeNodeIds) return nodes;
    return nodes.map(node => {
      if (node.type === 'stickyNote') return node;
      return {
        ...node,
        style: { ...node.style, opacity: activeNodeIds.has(node.id) ? 1 : 0.25 },
      };
    });
  }, [nodes, activeNodeIds]);

  // Apply highlighting to edges
  const highlightedEdges = useMemo(() => {
    if (!activeEdgeIds) return edges;
    return edges.map(edge => {
      const isActive = activeEdgeIds.has(edge.id);
      return {
        ...edge,
        style: {
          ...edge.style,
          opacity: isActive ? 1 : 0.1,
          strokeWidth: isActive ? 3 : (edge.style?.strokeWidth || 1.5),
        },
        zIndex: isActive ? 10 : 0,
        animated: isActive ? (edge.animated ?? false) : false,
      };
    });
  }, [edges, activeEdgeIds]);

  const onNodeMouseEnter = useCallback((_, node) => {
    if (node.type !== 'stickyNote') setHoveredElement({ type: 'node', id: node.id });
  }, []);
  const onNodeMouseLeave = useCallback(() => setHoveredElement(null), []);
  const onEdgeMouseEnter = useCallback((_, edge) => {
    setHoveredElement({ type: 'edge', id: edge.id });
  }, []);
  const onEdgeMouseLeave = useCallback(() => setHoveredElement(null), []);

  return {
    highlightedNodes, highlightedEdges,
    onNodeMouseEnter, onNodeMouseLeave,
    onEdgeMouseEnter, onEdgeMouseLeave,
  };
}
```

### Step 2: Update edge defaults in transform utilities

**`flowTransform.js`** — change edge style (lines 49-50):
- `strokeWidth: 2` → `strokeWidth: 1.5`
- Add `opacity: 0.7`

**`apiRoutesTransform.js`** — change edge style (line 58):
- `strokeWidth: 2` → `strokeWidth: 1.5`
- Add `opacity: 0.7`

### Step 3: Increase Dagre spacing

**`FlowVisualization.jsx`** — `getLayoutedFlowElements` (lines 43-49):
- `nodesep: 100` → `nodesep: 160`
- `ranksep: 150` → `ranksep: 220`

**`ApiRoutesVisualization.jsx`** — `getLayoutedRouteElements` (lines 39-45):
- `nodesep: 80` → `nodesep: 120`
- `ranksep: 100` → `ranksep: 160`

### Step 4: Integrate hook into FlowVisualization.jsx

- Import `useEdgeHighlighting`
- Call hook with `nodes` and `edges`
- Pass `highlightedNodes`/`highlightedEdges` + 4 mouse handlers to `<ReactFlow>`

### Step 5: Integrate hook into ApiRoutesVisualization.jsx

- Import `useEdgeHighlighting`
- Call hook with `filteredNodes` and `filteredEdges` (after method filter — this is critical)
- Pass `highlightedNodes`/`highlightedEdges` + 4 mouse handlers to `<ReactFlow>`

### Step 6: Add CSS transitions

Append to `frontend/src/index.css`:
```css
.react-flow__edge path {
  transition: opacity 0.2s ease, stroke-width 0.2s ease;
}
.react-flow__edge .react-flow__edge-interaction {
  stroke-width: 20px;
}
.react-flow__node {
  transition: opacity 0.2s ease;
}
```

## Verification

1. Open a Runtime Flow visualization with multiple interconnected functions
2. Hover a node → its connected edges and neighbor nodes highlight, everything else dims
3. Hover an edge → that edge and its two endpoint nodes highlight, everything else dims
4. Move mouse away → all elements return to default semi-transparent state
5. Repeat in API Routes view with method filter active
6. Verify sticky notes are never dimmed
7. Verify dark mode looks correct
8. Click re-layout → wider spacing, highlighting still works
9. Load project with saved layout → positions unchanged, highlighting works
