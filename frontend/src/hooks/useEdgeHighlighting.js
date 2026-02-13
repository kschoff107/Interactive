import { useState, useMemo, useCallback } from 'react';

/**
 * Hook that provides hover-based highlighting for ReactFlow edges and nodes.
 * When a node is hovered, its connected edges and neighbor nodes highlight
 * while everything else dims. Same for edge hover.
 *
 * This is a presentation-layer hook — it does NOT modify canonical state,
 * only wraps the output with opacity/strokeWidth overrides.
 *
 * @param {Array} nodes - ReactFlow nodes (may be pre-filtered)
 * @param {Array} edges - ReactFlow edges (may be pre-filtered)
 * @returns {Object} highlightedNodes, highlightedEdges, and 4 mouse event handlers
 */
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
        if (ep) {
          activeNodeIds.add(ep.source);
          activeNodeIds.add(ep.target);
        }
      });
    } else {
      activeEdgeIds.add(hoveredElement.id);
      const ep = edgeEndpoints.get(hoveredElement.id);
      if (ep) {
        activeNodeIds.add(ep.source);
        activeNodeIds.add(ep.target);
      }
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
        style: {
          ...node.style,
          opacity: activeNodeIds.has(node.id) ? 1 : 0.25,
        },
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
    if (node.type !== 'stickyNote') {
      setHoveredElement({ type: 'node', id: node.id });
    }
  }, []);

  const onNodeMouseLeave = useCallback(() => setHoveredElement(null), []);

  const onEdgeMouseEnter = useCallback((_, edge) => {
    setHoveredElement({ type: 'edge', id: edge.id });
  }, []);

  const onEdgeMouseLeave = useCallback(() => setHoveredElement(null), []);

  return {
    highlightedNodes,
    highlightedEdges,
    onNodeMouseEnter,
    onNodeMouseLeave,
    onEdgeMouseEnter,
    onEdgeMouseLeave,
  };
}
