/**
 * Transform runtime flow data from API to ReactFlow format
 * Converts functions, calls, and control flows to nodes and edges
 */

/**
 * Transform runtime flow data to ReactFlow nodes and edges
 * @param {Object} flowData - Runtime flow data from API
 * @returns {Object} Object with nodes and edges arrays
 */
export const transformFlowData = (flowData) => {
  if (!flowData || !flowData.functions) {
    return { nodes: [], edges: [] };
  }

  const nodes = [];
  const edges = [];

  // Create function nodes
  flowData.functions.forEach((func, index) => {
    nodes.push({
      id: func.id,
      type: 'functionNode',
      data: {
        name: func.name,
        parameters: func.parameters || [],
        decorators: func.decorators || [],
        complexity: func.complexity,
        isAsync: func.is_async,
        isEntryPoint: flowData.entry_points?.includes(func.id),
        module: func.module,
        line: func.line_number,
      },
      position: { x: 0, y: 0 }, // Will be layouted by dagre
    });
  });

  // Create edges from function calls
  if (flowData.calls) {
    flowData.calls.forEach((call, index) => {
      // Only create edges for direct calls between known functions
      if (call.call_type === 'direct' && call.caller_id && call.callee_id) {
        edges.push({
          id: `call-${index}`,
          source: call.caller_id,
          target: call.callee_id,
          label: call.is_conditional ? 'conditional' : '',
          animated: true,
          style: {
            stroke: call.is_conditional ? '#f59e0b' : '#3b82f6',
            strokeWidth: 2,
          },
          labelStyle: {
            fontSize: '10px',
            fontWeight: 500,
          },
          type: 'smoothstep',
        });
      }
    });
  }

  // TODO: In future, add control flow nodes (conditionals, loops, try/except)
  // For now, focus on function call graph

  return { nodes, edges };
};

/**
 * Estimate height for flow nodes
 * @param {Object} node - ReactFlow node
 * @returns {number} Estimated height in pixels
 */
export const estimateFlowNodeHeight = (node) => {
  if (node.type === 'functionNode') {
    let height = 80; // Base height

    // Add height for decorators
    if (node.data?.decorators && node.data.decorators.length > 0) {
      height += Math.min(node.data.decorators.length, 3) * 20;
    }

    // Add height for parameters
    if (node.data?.parameters && node.data.parameters.length > 0) {
      height += 20;
    }

    // Add height for complexity indicator
    if (node.data?.complexity !== undefined) {
      height += 20;
    }

    return Math.max(height, 100);
  }

  if (node.type === 'conditionalNode') {
    return 180; // Diamond shape needs more space
  }

  if (node.type === 'loopNode') {
    return 160; // Circle shape
  }

  if (node.type === 'tryNode') {
    let height = 120;
    if (node.data?.handlers && node.data.handlers.length > 0) {
      height += Math.min(node.data.handlers.length, 2) * 25;
    }
    return height;
  }

  return 100; // Default
};

/**
 * Get node width based on type
 * @param {Object} node - ReactFlow node
 * @returns {number} Width in pixels
 */
export const getFlowNodeWidth = (node) => {
  if (node.type === 'functionNode') {
    return 240;
  }

  if (node.type === 'conditionalNode') {
    return 200;
  }

  if (node.type === 'loopNode') {
    return 160;
  }

  if (node.type === 'tryNode') {
    return 200;
  }

  return 220; // Default
};

/**
 * Get statistics from flow data
 * @param {Object} flowData - Runtime flow data from API
 * @returns {Object} Statistics object
 */
export const getFlowStatistics = (flowData) => {
  if (!flowData) {
    return {
      totalFunctions: 0,
      totalCalls: 0,
      entryPoints: 0,
      maxComplexity: 0,
      avgComplexity: 0,
    };
  }

  const functions = flowData.functions || [];
  const calls = flowData.calls || [];
  const entryPoints = flowData.entry_points || [];

  const complexities = functions
    .map(f => f.complexity)
    .filter(c => c !== undefined && c !== null);

  return {
    totalFunctions: functions.length,
    totalCalls: calls.length,
    entryPoints: entryPoints.length,
    maxComplexity: complexities.length > 0 ? Math.max(...complexities) : 0,
    avgComplexity: complexities.length > 0
      ? (complexities.reduce((a, b) => a + b, 0) / complexities.length).toFixed(1)
      : 0,
  };
};

/**
 * Filter flow data by module
 * @param {Object} flowData - Runtime flow data from API
 * @param {string} moduleName - Module to filter by (null for all)
 * @returns {Object} Filtered flow data
 */
export const filterByModule = (flowData, moduleName) => {
  if (!moduleName || !flowData) {
    return flowData;
  }

  const filteredFunctions = flowData.functions.filter(
    f => f.module === moduleName
  );

  const functionIds = new Set(filteredFunctions.map(f => f.id));

  const filteredCalls = flowData.calls.filter(
    c => functionIds.has(c.caller_id) && functionIds.has(c.callee_id)
  );

  return {
    ...flowData,
    functions: filteredFunctions,
    calls: filteredCalls,
  };
};

/**
 * Get entry point functions from flow data
 * @param {Object} flowData - Runtime flow data from API
 * @returns {Array} Array of entry point functions
 */
export const getEntryPointFunctions = (flowData) => {
  if (!flowData || !flowData.entry_points || !flowData.functions) {
    return [];
  }

  const entryPointIds = new Set(flowData.entry_points);
  return flowData.functions.filter(f => entryPointIds.has(f.id));
};
