import React, { useState, useEffect, useMemo } from 'react';
import ReactFlow, {
  MiniMap,
  Controls,
  ControlButton,
  Background,
  useNodesState,
  useEdgesState,
} from 'reactflow';
import 'reactflow/dist/style.css';
import dagre from 'dagre';

import RouteNode from './nodes/RouteNode';
import BlueprintNode from './nodes/BlueprintNode';
import { transformApiRoutesData, estimateRouteNodeHeight, getRouteNodeWidth } from '../../utils/apiRoutesTransform';

// Register custom node types for API routes
const nodeTypes = {
  routeNode: RouteNode,
  blueprintNode: BlueprintNode,
};

/**
 * Apply Dagre layout to route nodes
 */
const getLayoutedRouteElements = (nodes, edges, direction = 'TB') => {
  const dagreGraph = new dagre.graphlib.Graph();
  dagreGraph.setDefaultEdgeLabel(() => ({}));

  dagreGraph.setGraph({
    rankdir: direction,
    nodesep: 80,
    ranksep: 100,
    marginx: 50,
    marginy: 50,
  });

  // Add nodes to dagre
  nodes.forEach((node) => {
    const width = getRouteNodeWidth(node);
    const height = estimateRouteNodeHeight(node);
    dagreGraph.setNode(node.id, { width, height });
  });

  // Add edges
  edges.forEach((edge) => {
    dagreGraph.setEdge(edge.source, edge.target);
  });

  // Run layout
  dagre.layout(dagreGraph);

  // Apply positions
  const layoutedNodes = nodes.map((node) => {
    const nodeWithPosition = dagreGraph.node(node.id);
    const width = getRouteNodeWidth(node);
    const height = estimateRouteNodeHeight(node);

    return {
      ...node,
      position: {
        x: nodeWithPosition.x - width / 2,
        y: nodeWithPosition.y - height / 2,
      },
    };
  });

  return { nodes: layoutedNodes, edges };
};

export default function ApiRoutesVisualization({ routesData, isDark, onToggleTheme, layoutTrigger, projectId }) {
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [initialNodes, setInitialNodes] = useState([]);
  const [initialEdges, setInitialEdges] = useState([]);
  const [methodFilter, setMethodFilter] = useState(null);

  // Transform and layout routes data on initial load
  useEffect(() => {
    if (routesData) {
      const { nodes: routeNodes, edges: routeEdges } = transformApiRoutesData(routesData);

      if (routeNodes.length > 0) {
        const { nodes: layoutedNodes, edges: layoutedEdges } = getLayoutedRouteElements(
          routeNodes,
          routeEdges
        );
        setNodes(layoutedNodes);
        setEdges(layoutedEdges);
        // Store initial state for re-layout
        setInitialNodes(routeNodes);
        setInitialEdges(routeEdges);
      }
    }
  }, [routesData, setNodes, setEdges]);

  // Re-layout when layoutTrigger changes
  useEffect(() => {
    if (layoutTrigger > 0 && initialNodes.length > 0) {
      const { nodes: layoutedNodes, edges: layoutedEdges } = getLayoutedRouteElements(
        initialNodes,
        initialEdges
      );
      setNodes(layoutedNodes);
      setEdges(layoutedEdges);
    }
  }, [layoutTrigger, initialNodes, initialEdges, setNodes, setEdges]);

  // Calculate statistics
  const statistics = useMemo(() => {
    if (!routesData || !routesData.statistics) {
      return null;
    }
    return routesData.statistics;
  }, [routesData]);

  // Method filter options
  const methods = ['GET', 'POST', 'PUT', 'DELETE', 'PATCH'];
  const methodColors = {
    GET: 'bg-green-500',
    POST: 'bg-blue-500',
    PUT: 'bg-orange-500',
    DELETE: 'bg-red-500',
    PATCH: 'bg-purple-500',
  };

  if (!routesData || nodes.length === 0) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center">
          <svg
            className="mx-auto h-12 w-12 text-gray-400"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth="2"
              d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9"
            />
          </svg>
          <h3 className="mt-2 text-sm font-medium text-gray-900 dark:text-gray-100">
            No API routes data
          </h3>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
            Click "Analyze API Routes" to generate the visualization
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="w-full h-full relative">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.2, maxZoom: 1 }}
        minZoom={0.1}
        maxZoom={2}
        defaultEdgeOptions={{
          type: 'smoothstep',
        }}
        className={isDark ? 'dark' : ''}
      >
        <Background
          color={isDark ? '#374151' : '#e5e7eb'}
          gap={16}
          size={1}
        />

        <Controls
          showInteractive={false}
          className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden"
        >
          <ControlButton
            onClick={onToggleTheme}
            title={isDark ? 'Switch to Light Mode' : 'Switch to Dark Mode'}
          >
            {isDark ? (
              <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M10 2a1 1 0 011 1v1a1 1 0 11-2 0V3a1 1 0 011-1zm4 8a4 4 0 11-8 0 4 4 0 018 0zm-.464 4.95l.707.707a1 1 0 001.414-1.414l-.707-.707a1 1 0 00-1.414 1.414zm2.12-10.607a1 1 0 010 1.414l-.706.707a1 1 0 11-1.414-1.414l.707-.707a1 1 0 011.414 0zM17 11a1 1 0 100-2h-1a1 1 0 100 2h1zm-7 4a1 1 0 011 1v1a1 1 0 11-2 0v-1a1 1 0 011-1zM5.05 6.464A1 1 0 106.465 5.05l-.708-.707a1 1 0 00-1.414 1.414l.707.707zm1.414 8.486l-.707.707a1 1 0 01-1.414-1.414l.707-.707a1 1 0 011.414 1.414zM4 11a1 1 0 100-2H3a1 1 0 000 2h1z" clipRule="evenodd" />
              </svg>
            ) : (
              <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                <path d="M17.293 13.293A8 8 0 016.707 2.707a8.001 8.001 0 1010.586 10.586z" />
              </svg>
            )}
          </ControlButton>
        </Controls>

        <MiniMap
          nodeColor={(node) => {
            if (node.type === 'blueprintNode') return '#64748b';
            if (node.type === 'routeNode') {
              const methods = node.data?.methods || [];
              if (methods.includes('DELETE')) return '#ef4444';
              if (methods.includes('POST')) return '#3b82f6';
              if (methods.includes('PUT')) return '#f59e0b';
              if (methods.includes('PATCH')) return '#8b5cf6';
              return '#10b981'; // GET
            }
            return '#6b7280';
          }}
          className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg"
          maskColor={isDark ? 'rgb(17, 24, 39, 0.6)' : 'rgb(243, 244, 246, 0.6)'}
        />

        {/* Method filter buttons - top-left */}
        <div className="absolute top-4 left-4 z-10 flex flex-wrap gap-2">
          <button
            onClick={() => setMethodFilter(null)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all duration-200 ${
              methodFilter === null
                ? 'bg-gray-800 dark:bg-gray-200 text-white dark:text-gray-800'
                : 'bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-300 border border-gray-300 dark:border-gray-600 hover:bg-gray-100 dark:hover:bg-gray-700'
            }`}
          >
            All
          </button>
          {methods.map((method) => (
            <button
              key={method}
              onClick={() => setMethodFilter(methodFilter === method ? null : method)}
              className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all duration-200 ${
                methodFilter === method
                  ? `${methodColors[method]} text-white shadow-lg`
                  : 'bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-300 border border-gray-300 dark:border-gray-600 hover:bg-gray-100 dark:hover:bg-gray-700'
              }`}
            >
              {method}
            </button>
          ))}
        </div>

        {/* Statistics overlay */}
        {statistics && (
          <div className="absolute top-4 right-4 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg shadow-lg p-4 min-w-[200px]">
            <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-3">
              API Statistics
            </h3>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-gray-600 dark:text-gray-400">Blueprints:</span>
                <span className="font-medium text-gray-900 dark:text-gray-100">
                  {statistics.total_blueprints}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600 dark:text-gray-400">Total Routes:</span>
                <span className="font-medium text-gray-900 dark:text-gray-100">
                  {statistics.total_routes}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600 dark:text-gray-400">Protected:</span>
                <span className="font-medium text-amber-600 dark:text-amber-400">
                  {statistics.protected_routes}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600 dark:text-gray-400">Unprotected:</span>
                <span className="font-medium text-gray-900 dark:text-gray-100">
                  {statistics.unprotected_routes}
                </span>
              </div>

              {/* Method breakdown */}
              {statistics.routes_by_method && Object.keys(statistics.routes_by_method).length > 0 && (
                <div className="pt-2 border-t border-gray-200 dark:border-gray-700">
                  <div className="text-xs text-gray-500 dark:text-gray-400 mb-2">By Method:</div>
                  <div className="flex flex-wrap gap-1">
                    {Object.entries(statistics.routes_by_method).map(([method, count]) => (
                      <span
                        key={method}
                        className={`px-2 py-0.5 rounded text-xs font-medium ${methodColors[method] || 'bg-gray-500'} text-white`}
                      >
                        {method}: {count}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </ReactFlow>
    </div>
  );
}
