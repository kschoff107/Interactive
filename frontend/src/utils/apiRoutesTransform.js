/**
 * Transform API routes data from API to ReactFlow format
 * Converts blueprints and routes to nodes and edges
 */

/**
 * Transform API routes data to ReactFlow nodes and edges
 * @param {Object} routesData - API routes data from backend
 * @returns {Object} Object with nodes and edges arrays
 */
export const transformApiRoutesData = (routesData) => {
  if (!routesData || !routesData.routes) {
    return { nodes: [], edges: [] };
  }

  const nodes = [];
  const edges = [];

  // Create blueprint nodes
  if (routesData.blueprints) {
    routesData.blueprints.forEach((blueprint) => {
      nodes.push({
        id: blueprint.id,
        type: 'blueprintNode',
        data: {
          name: blueprint.name,
          url_prefix: blueprint.url_prefix,
          route_count: blueprint.route_count,
        },
        position: { x: 0, y: 0 }, // Will be layouted by dagre
      });
    });
  }

  // Create route nodes and edges to blueprints
  routesData.routes.forEach((route, index) => {
    nodes.push({
      id: route.id,
      type: 'routeNode',
      data: {
        name: route.function_name,
        url_pattern: route.full_url || route.url_pattern,
        methods: route.methods || ['GET'],
        requires_auth: route.security?.requires_auth || false,
        docstring: route.docstring,
        path_params: route.parameters?.path_params || [],
      },
      position: { x: 0, y: 0 },
    });

    // Edge from blueprint to route
    if (route.blueprint_id) {
      edges.push({
        id: `edge-${route.blueprint_id}-${route.id}`,
        source: route.blueprint_id,
        target: route.id,
        type: 'smoothstep',
        style: { stroke: '#94a3b8', strokeWidth: 1.5, opacity: 0.7 },
        animated: false,
      });
    }
  });

  return { nodes, edges };
};

/**
 * Estimate height for route nodes
 * @param {Object} node - ReactFlow node
 * @returns {number} Estimated height in pixels
 */
export const estimateRouteNodeHeight = (node) => {
  if (node.type === 'blueprintNode') {
    return 100;
  }

  if (node.type === 'routeNode') {
    let height = 80; // Base height

    // Add height for method badges
    const methods = node.data?.methods || [];
    if (methods.length > 3) {
      height += 20; // Extra row for methods
    }

    // Add height for docstring
    if (node.data?.docstring) {
      height += 20;
    }

    return Math.max(height, 100);
  }

  return 100; // Default
};

/**
 * Get node width based on type
 * @param {Object} node - ReactFlow node
 * @returns {number} Width in pixels
 */
export const getRouteNodeWidth = (node) => {
  if (node.type === 'blueprintNode') {
    return 180;
  }

  if (node.type === 'routeNode') {
    return 240;
  }

  return 220; // Default
};

/**
 * Get statistics from routes data
 * @param {Object} routesData - API routes data from backend
 * @returns {Object} Statistics object
 */
export const getRoutesStatistics = (routesData) => {
  if (!routesData) {
    return {
      totalBlueprints: 0,
      totalRoutes: 0,
      routesByMethod: {},
      protectedRoutes: 0,
      unprotectedRoutes: 0,
    };
  }

  return routesData.statistics || {
    totalBlueprints: (routesData.blueprints || []).length,
    totalRoutes: (routesData.routes || []).length,
    routesByMethod: {},
    protectedRoutes: 0,
    unprotectedRoutes: 0,
  };
};

/**
 * Filter routes by HTTP method
 * @param {Object} routesData - API routes data from backend
 * @param {string} method - HTTP method to filter by (null for all)
 * @returns {Object} Filtered routes data
 */
export const filterByMethod = (routesData, method) => {
  if (!method || !routesData) {
    return routesData;
  }

  const filteredRoutes = routesData.routes.filter(
    route => route.methods && route.methods.includes(method)
  );

  // Keep all blueprints but update their route counts
  const blueprintIds = new Set(filteredRoutes.map(r => r.blueprint_id).filter(Boolean));
  const filteredBlueprints = routesData.blueprints?.map(bp => ({
    ...bp,
    route_count: filteredRoutes.filter(r => r.blueprint_id === bp.id).length,
  })).filter(bp => blueprintIds.has(bp.id));

  return {
    ...routesData,
    blueprints: filteredBlueprints || [],
    routes: filteredRoutes,
  };
};

/**
 * Filter routes by authentication requirement
 * @param {Object} routesData - API routes data from backend
 * @param {boolean} requiresAuth - True for protected routes, false for unprotected
 * @returns {Object} Filtered routes data
 */
export const filterByAuth = (routesData, requiresAuth) => {
  if (requiresAuth === null || requiresAuth === undefined || !routesData) {
    return routesData;
  }

  const filteredRoutes = routesData.routes.filter(
    route => (route.security?.requires_auth || false) === requiresAuth
  );

  // Keep all blueprints but update their route counts
  const blueprintIds = new Set(filteredRoutes.map(r => r.blueprint_id).filter(Boolean));
  const filteredBlueprints = routesData.blueprints?.map(bp => ({
    ...bp,
    route_count: filteredRoutes.filter(r => r.blueprint_id === bp.id).length,
  })).filter(bp => blueprintIds.has(bp.id));

  return {
    ...routesData,
    blueprints: filteredBlueprints || [],
    routes: filteredRoutes,
  };
};
