import { useState, useMemo, useCallback, useEffect } from 'react';

/**
 * Hook that provides hover-based highlighting for ReactFlow edges and nodes.
 * When a node is hovered, its connected edges and neighbor nodes highlight
 * while everything else dims. Same for edge hover.
 * Sticky note nodes are always excluded from highlighting (never dimmed, never trigger highlight).
 *
 * @param {import('reactflow').Node[]} nodes - ReactFlow nodes (may be pre-filtered)
 * @param {import('reactflow').Edge[]} edges - ReactFlow edges (may be pre-filtered)
 * @returns {{
 *   highlightedNodes: import('reactflow').Node[],
 *   highlightedEdges: import('reactflow').Edge[],
 *   onNodeMouseEnter: function,
 *   onNodeMouseLeave: function,
 *   onEdgeMouseEnter: function,
 *   onEdgeMouseLeave: function
 * }} Highlighted nodes/edges with opacity applied, and mouse event handlers for ReactFlow
 */
export function useEdgeHighlighting(nodes, edges) {
  const safeNodes = nodes || [];
  const safeEdges = edges || [];
  const [hoveredElement, setHoveredElement] = useState(null);

  // Reset hover state when input data changes (prevents stale highlight after filter/data change)
  useEffect(() => {
    setHoveredElement(null);
  }, [safeNodes, safeEdges]);

  // Build adjacency maps (rebuilds only when edges change)
  const { nodeToEdges, edgeEndpoints } = useMemo(() => {
    const nToE = new Map();
    const eToEndpoints = new Map();
    for (const edge of safeEdges) {
      if (!edge.id || !edge.source || !edge.target) {
        console.warn('useEdgeHighlighting: skipping malformed edge', edge);
        continue;
      }
      eToEndpoints.set(edge.id, { source: edge.source, target: edge.target });
      if (!nToE.has(edge.source)) nToE.set(edge.source, new Set());
      if (!nToE.has(edge.target)) nToE.set(edge.target, new Set());
      nToE.get(edge.source).add(edge.id);
      nToE.get(edge.target).add(edge.id);
    }
    return { nodeToEdges: nToE, edgeEndpoints: eToEndpoints };
  }, [safeEdges]);

  // Compute active sets from hovered element
  const { activeNodeIds, activeEdgeIds } = useMemo(() => {
    if (!hoveredElement) return { activeNodeIds: null, activeEdgeIds: null };
    const activeNodeIds = new Set();
    const activeEdgeIds = new Set();

    if (hoveredElement.type === 'node') {
      activeNodeIds.add(hoveredElement.id);
      const connectedEdges = nodeToEdges.get(hoveredElement.id);
      if (connectedEdges) {
        for (const edgeId of connectedEdges) {
          activeEdgeIds.add(edgeId);
          const ep = edgeEndpoints.get(edgeId);
          if (ep) {
            activeNodeIds.add(ep.source);
            activeNodeIds.add(ep.target);
          }
        }
      }
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
    if (!activeNodeIds) return safeNodes;
    return safeNodes.map(node => {
      // Sticky notes are excluded from dimming — always fully visible
      if (node.type === 'stickyNote') return node;
      return {
        ...node,
        style: {
          ...node.style,
          opacity: activeNodeIds.has(node.id) ? 1 : 0.25,
        },
      };
    });
  }, [safeNodes, activeNodeIds]);

  // Apply highlighting to edges
  const highlightedEdges = useMemo(() => {
    if (!activeEdgeIds) return safeEdges;
    return safeEdges.map(edge => {
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
  }, [safeEdges, activeEdgeIds]);

  // Sticky notes don't trigger highlighting — only real flow/route nodes do
  const onNodeMouseEnter = useCallback((_, node) => {
    if (node && node.type !== 'stickyNote') {
      setHoveredElement({ type: 'node', id: node.id });
    }
  }, []);

  const onEdgeMouseEnter = useCallback((_, edge) => {
    if (edge?.id) {
      setHoveredElement({ type: 'edge', id: edge.id });
    }
  }, []);

  const onMouseLeave = useCallback(() => setHoveredElement(null), []);

  return {
    highlightedNodes,
    highlightedEdges,
    onNodeMouseEnter,
    onNodeMouseLeave: onMouseLeave,
    onEdgeMouseEnter,
    onEdgeMouseLeave: onMouseLeave,
  };
}
