import React, { useState, useEffect, useMemo, useCallback } from 'react';
import ReactFlow, {
  MiniMap,
  Controls,
  Background,
  useNodesState,
  useEdgesState,
} from 'reactflow';
import 'reactflow/dist/style.css';
import dagre from 'dagre';

import RouteNode from './nodes/RouteNode';
import BlueprintNode from './nodes/BlueprintNode';
import StickyNote from './StickyNote';
import { StickyNoteButton, ThemeToggleButton } from './ToolbarButtons';
import ApiRoutesInsightGuide from './ApiRoutesInsightGuide';
import { transformApiRoutesData, estimateRouteNodeHeight, getRouteNodeWidth } from '../../utils/apiRoutesTransform';
import { applySavedLayout } from '../../utils/layoutUtils';
import { useStickyNotes, restoreStickyNotesFromLayout } from '../../hooks/useStickyNotes';

// Register custom node types for API routes
const nodeTypes = {
  routeNode: RouteNode,
  blueprintNode: BlueprintNode,
  stickyNote: StickyNote,
};

/**
 * Apply Dagre layout to route nodes
 */
const getLayoutedRouteElements = (nodes, edges, direction = 'TB') => {
  // Separate sticky notes from route nodes — notes skip dagre layout
  const stickyNotes = nodes.filter(n => n.type === 'stickyNote');
  const routeNodes = nodes.filter(n => n.type !== 'stickyNote');

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
  routeNodes.forEach((node) => {
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
  const layoutedNodes = routeNodes.map((node) => {
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

  return { nodes: [...layoutedNodes, ...stickyNotes], edges };
};

export default function ApiRoutesVisualization({ routesData, isDark, onToggleTheme, layoutTrigger, projectId, savedLayout, onNodesUpdate, onNodesDragged }) {
  const [nodes, setNodes, onNodesChangeBase] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [initialNodes, setInitialNodes] = useState([]);
  const [initialEdges, setInitialEdges] = useState([]);
  const [methodFilter, setMethodFilter] = useState(null);
  const [showInsightGuide, setShowInsightGuide] = useState(false);

  // Wrap onNodesChange to detect drag completions
  const onNodesChange = useCallback((changes) => {
    onNodesChangeBase(changes);
    const hasDragEnd = changes.some(c => c.type === 'position' && c.dragging === false);
    if (hasDragEnd && onNodesDragged) onNodesDragged();
  }, [onNodesChangeBase, onNodesDragged]);

  // Report nodes to parent whenever they change
  useEffect(() => {
    if (onNodesUpdate) onNodesUpdate(nodes);
  }, [nodes, onNodesUpdate]);

  // Sticky Note handlers
  const { handleNoteTextChange, handleNoteColorChange, handleDeleteNote, handleAddNote } =
    useStickyNotes(setNodes, onNodesDragged);

  // Transform and layout routes data on initial load
  useEffect(() => {
    if (routesData) {
      const { nodes: routeNodes, edges: routeEdges } = transformApiRoutesData(routesData);

      if (routeNodes.length > 0) {
        const { nodes: layoutedNodes, edges: layoutedEdges } = getLayoutedRouteElements(
          routeNodes,
          routeEdges
        );

        // Apply saved layout positions if available
        const finalNodes = applySavedLayout(layoutedNodes, savedLayout);

        // Restore sticky notes from saved layout
        const stickyNotes = restoreStickyNotesFromLayout(savedLayout, {
          onTextChange: handleNoteTextChange,
          onColorChange: handleNoteColorChange,
          onDelete: handleDeleteNote,
        });

        setNodes([...finalNodes, ...stickyNotes]);
        setEdges(layoutedEdges);
        // Store initial state for re-layout
        setInitialNodes(routeNodes);
        setInitialEdges(routeEdges);
      }
    }
  }, [routesData, savedLayout, setNodes, setEdges, handleNoteTextChange, handleNoteColorChange, handleDeleteNote]);

  // Re-layout when layoutTrigger changes (preserve sticky notes)
  useEffect(() => {
    if (layoutTrigger > 0 && initialNodes.length > 0) {
      const { nodes: layoutedNodes, edges: layoutedEdges } = getLayoutedRouteElements(
        initialNodes,
        initialEdges
      );
      setNodes((currentNodes) => {
        const existingStickyNotes = currentNodes.filter(n => n.type === 'stickyNote');
        return [...layoutedNodes, ...existingStickyNotes];
      });
      setEdges(layoutedEdges);
    }
  }, [layoutTrigger, initialNodes, initialEdges, setNodes, setEdges]);

  const statistics = routesData?.statistics ?? null;

  // Method filter options
  const methods = ['GET', 'POST', 'PUT', 'DELETE', 'PATCH'];
  const methodColors = {
    GET: 'bg-green-500',
    POST: 'bg-blue-500',
    PUT: 'bg-orange-500',
    DELETE: 'bg-red-500',
    PATCH: 'bg-purple-500',
  };

  // Filter nodes based on selected method
  const filteredNodes = useMemo(() => {
    if (!methodFilter) return nodes;

    // Get IDs of route nodes that match the filter
    const matchingRouteIds = new Set();
    const matchingBlueprintIds = new Set();

    nodes.forEach(node => {
      if (node.type === 'routeNode' && node.data?.methods?.includes(methodFilter)) {
        matchingRouteIds.add(node.id);
        // Find parent blueprint from edges
        edges.forEach(edge => {
          if (edge.target === node.id) {
            matchingBlueprintIds.add(edge.source);
          }
        });
      }
    });

    return nodes.filter(node => {
      if (node.type === 'routeNode') {
        return matchingRouteIds.has(node.id);
      }
      if (node.type === 'blueprintNode') {
        return matchingBlueprintIds.has(node.id);
      }
      return true;
    });
  }, [nodes, edges, methodFilter]);

  // Filter edges to only show connections between visible nodes
  const filteredEdges = useMemo(() => {
    if (!methodFilter) return edges;

    const visibleNodeIds = new Set(filteredNodes.map(n => n.id));
    return edges.filter(edge =>
      visibleNodeIds.has(edge.source) && visibleNodeIds.has(edge.target)
    );
  }, [edges, filteredNodes, methodFilter]);

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
        nodes={filteredNodes}
        edges={filteredEdges}
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
          <StickyNoteButton onAddNote={handleAddNote} />
          <ThemeToggleButton isDark={isDark} onToggle={onToggleTheme} />
        </Controls>

        <MiniMap
          nodeColor={(node) => {
            if (node.type === 'stickyNote') return '#fbbf24';
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

        {/* Decode This button - top-left */}
        <div className="absolute top-4 left-4 z-10">
          <button
            onClick={() => setShowInsightGuide(true)}
            className="bg-purple-600 hover:bg-purple-700 dark:bg-purple-500 dark:hover:bg-purple-600 text-white px-4 py-2 rounded-lg shadow-lg transition-all duration-200 flex items-center gap-2 font-medium text-sm"
            title="Learn about this visualization"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2"
                d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            Decode This
          </button>
        </div>

        {/* Method filter buttons - top center */}
        <div className="absolute top-4 left-1/2 transform -translate-x-1/2 z-10 flex flex-wrap gap-2 justify-center">
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

      {/* Insight Guide Modal */}
      <ApiRoutesInsightGuide
        isOpen={showInsightGuide}
        onClose={() => setShowInsightGuide(false)}
        isDark={isDark}
        routesData={routesData}
        projectId={projectId}
      />
    </div>
  );
}
