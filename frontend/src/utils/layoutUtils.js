import dagre from 'dagre';

/**
 * Estimate the height of a node based on its content
 * @param {Object} node - ReactFlow node
 * @returns {number} Estimated height in pixels
 */
export const estimateNodeHeight = (node) => {
  // Base height for header and padding
  let height = 60;

  // If node has columns in its data, estimate height based on column count
  if (node.data?.columns) {
    const columnCount = node.data.columns.length;
    height += columnCount * 20; // ~20px per column
  } else if (node.data?.label && typeof node.data.label === 'object') {
    // For JSX labels, use a rough estimate based on content
    height = 150; // Default for table nodes
  }

  return Math.max(height, 100); // Minimum height
};

/**
 * Detect circular edges using DFS to find back edges
 * @param {Array} edges - ReactFlow edges
 * @param {Array} nodes - ReactFlow nodes
 * @returns {Set} Set of edge IDs that create cycles
 */
export const detectCircularEdges = (edges, nodes) => {
  const circularEdgeIds = new Set();
  const visited = new Set();
  const recursionStack = new Set();

  // Build adjacency list
  const adjacencyList = new Map();
  nodes.forEach(node => adjacencyList.set(node.id, []));

  edges.forEach(edge => {
    if (!adjacencyList.has(edge.source)) {
      adjacencyList.set(edge.source, []);
    }
    adjacencyList.get(edge.source).push({ target: edge.target, edgeId: edge.id });
  });

  // DFS to detect cycles
  const dfs = (nodeId) => {
    visited.add(nodeId);
    recursionStack.add(nodeId);

    const neighbors = adjacencyList.get(nodeId) || [];
    for (const { target, edgeId } of neighbors) {
      if (!visited.has(target)) {
        if (dfs(target)) {
          return true;
        }
      } else if (recursionStack.has(target)) {
        // Back edge detected - this creates a cycle
        circularEdgeIds.add(edgeId);
      }
    }

    recursionStack.delete(nodeId);
    return false;
  };

  // Run DFS from each unvisited node
  nodes.forEach(node => {
    if (!visited.has(node.id)) {
      dfs(node.id);
    }
  });

  return circularEdgeIds;
};

/**
 * Apply Dagre hierarchical layout algorithm to nodes and edges
 * @param {Array} nodes - ReactFlow nodes
 * @param {Array} edges - ReactFlow edges
 * @param {string} direction - Layout direction: 'TB' (top-bottom), 'LR' (left-right), etc.
 * @returns {Object} Object with layouted nodes and processed edges
 */
export const getLayoutedElements = (nodes, edges, direction = 'TB') => {
  const dagreGraph = new dagre.graphlib.Graph();
  dagreGraph.setDefaultEdgeLabel(() => ({}));

  // Separate sticky notes from table nodes
  const stickyNotes = nodes.filter(n => n.type === 'stickyNote');
  const tableNodes = nodes.filter(n => n.type !== 'stickyNote');

  // Configure layout
  dagreGraph.setGraph({
    rankdir: direction,
    nodesep: 80,        // Horizontal spacing between nodes
    ranksep: 120,       // Vertical spacing between ranks
    marginx: 50,
    marginy: 50,
  });

  // Detect circular edges (only for table nodes)
  const circularEdgeIds = detectCircularEdges(edges, tableNodes);

  // Add only table nodes to dagre graph with estimated dimensions
  tableNodes.forEach((node) => {
    const height = estimateNodeHeight(node);
    const width = node.style?.width || 220;

    dagreGraph.setNode(node.id, { width, height });
  });

  // Add edges to dagre graph (excluding circular edges to prevent layout issues)
  edges.forEach((edge) => {
    if (!circularEdgeIds.has(edge.id)) {
      dagreGraph.setEdge(edge.source, edge.target);
    }
  });

  // Run layout algorithm
  dagre.layout(dagreGraph);

  // Apply layout to table nodes only
  const layoutedTableNodes = tableNodes.map((node) => {
    const nodeWithPosition = dagreGraph.node(node.id);
    const height = estimateNodeHeight(node);
    const width = node.style?.width || 220;

    return {
      ...node,
      position: {
        x: nodeWithPosition.x - width / 2,
        y: nodeWithPosition.y - height / 2,
      },
    };
  });

  // Combine layouted table nodes with unchanged sticky notes
  const layoutedNodes = [...layoutedTableNodes, ...stickyNotes];

  // Process edges - mark circular ones with dashed style
  const processedEdges = edges.map((edge) => {
    if (circularEdgeIds.has(edge.id)) {
      return {
        ...edge,
        label: edge.label ? `${edge.label} (circular)` : '(circular)',
        style: {
          ...edge.style,
          strokeDasharray: '5,5',
        },
        animated: false,
      };
    }
    return edge;
  });

  return { nodes: layoutedNodes, edges: processedEdges };
};

/**
 * Serialize node positions and sticky notes to save to database
 * @param {Array} nodes - ReactFlow nodes
 * @returns {Object} Layout data object
 */
export const serializeLayout = (nodes) => {
  return {
    version: '1.0',
    nodes: nodes.map(n => {
      const nodeData = {
        id: n.id,
        position: n.position
      };

      // For sticky notes, save the full data
      if (n.type === 'stickyNote') {
        nodeData.type = 'stickyNote';
        nodeData.data = {
          text: n.data.text,
          color: n.data.color
        };
      }

      return nodeData;
    }),
    layoutMetadata: {
      lastSaved: new Date().toISOString()
    }
  };
};

/**
 * Apply saved layout positions to nodes
 * @param {Array} nodes - ReactFlow nodes
 * @param {Object} savedLayout - Saved layout data from database
 * @returns {Array} Nodes with updated positions
 */
export const applySavedLayout = (nodes, savedLayout) => {
  if (!savedLayout || !savedLayout.nodes) {
    return nodes;
  }

  // Create a map of saved positions
  const positionMap = new Map();
  savedLayout.nodes.forEach(savedNode => {
    positionMap.set(savedNode.id, savedNode.position);
  });

  // Apply saved positions to nodes
  return nodes.map(node => {
    const savedPosition = positionMap.get(node.id);
    if (savedPosition) {
      return {
        ...node,
        position: savedPosition
      };
    }
    return node;
  });
};
