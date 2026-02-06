import React, { useState, useEffect, useMemo } from 'react';
import ReactFlow, {
  MiniMap,
  Controls,
  Background,
  useNodesState,
  useEdgesState,
} from 'reactflow';
import 'reactflow/dist/style.css';
import dagre from 'dagre';

import FunctionNode from './nodes/FunctionNode';
import ConditionalNode from './nodes/ConditionalNode';
import LoopNode from './nodes/LoopNode';
import TryNode from './nodes/TryNode';
import { transformFlowData, estimateFlowNodeHeight, getFlowNodeWidth } from '../../utils/flowTransform';
import { detectCircularEdges } from '../../utils/layoutUtils';

// Register custom node types for runtime flow
const nodeTypes = {
  functionNode: FunctionNode,
  conditionalNode: ConditionalNode,
  loopNode: LoopNode,
  tryNode: TryNode,
};

/**
 * Apply Dagre layout to flow nodes
 */
const getLayoutedFlowElements = (nodes, edges, direction = 'TB') => {
  const dagreGraph = new dagre.graphlib.Graph();
  dagreGraph.setDefaultEdgeLabel(() => ({}));

  dagreGraph.setGraph({
    rankdir: direction,
    nodesep: 100,
    ranksep: 150,
    marginx: 50,
    marginy: 50,
  });

  // Detect circular edges
  const circularEdgeIds = detectCircularEdges(edges, nodes);

  // Add nodes to dagre
  nodes.forEach((node) => {
    const width = getFlowNodeWidth(node);
    const height = estimateFlowNodeHeight(node);
    dagreGraph.setNode(node.id, { width, height });
  });

  // Add edges (excluding circular ones)
  edges.forEach((edge) => {
    if (!circularEdgeIds.has(edge.id)) {
      dagreGraph.setEdge(edge.source, edge.target);
    }
  });

  // Run layout
  dagre.layout(dagreGraph);

  // Apply positions
  const layoutedNodes = nodes.map((node) => {
    const nodeWithPosition = dagreGraph.node(node.id);
    const width = getFlowNodeWidth(node);
    const height = estimateFlowNodeHeight(node);

    return {
      ...node,
      position: {
        x: nodeWithPosition.x - width / 2,
        y: nodeWithPosition.y - height / 2,
      },
    };
  });

  // Mark circular edges
  const layoutedEdges = edges.map((edge) => {
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

  return { nodes: layoutedNodes, edges: layoutedEdges };
};

export default function FlowVisualization({ flowData, isDark }) {
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [isLayouting, setIsLayouting] = useState(false);

  // Transform and layout flow data
  useEffect(() => {
    if (flowData) {
      const { nodes: flowNodes, edges: flowEdges } = transformFlowData(flowData);

      if (flowNodes.length > 0) {
        const { nodes: layoutedNodes, edges: layoutedEdges } = getLayoutedFlowElements(
          flowNodes,
          flowEdges
        );
        setNodes(layoutedNodes);
        setEdges(layoutedEdges);
      }
    }
  }, [flowData, setNodes, setEdges]);

  // Handle quick organize
  const handleQuickOrganize = () => {
    setIsLayouting(true);
    const { nodes: layoutedNodes, edges: layoutedEdges } = getLayoutedFlowElements(
      nodes,
      edges
    );
    setNodes(layoutedNodes);
    setEdges(layoutedEdges);
    setTimeout(() => setIsLayouting(false), 300);
  };

  // Calculate statistics
  const statistics = useMemo(() => {
    if (!flowData || !flowData.statistics) {
      return null;
    }
    return flowData.statistics;
  }, [flowData]);

  if (!flowData || nodes.length === 0) {
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
              d="M13 10V3L4 14h7v7l9-11h-7z"
            />
          </svg>
          <h3 className="mt-2 text-sm font-medium text-gray-900 dark:text-gray-100">
            No runtime flow data
          </h3>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
            Click "Analyze Runtime Flow" to generate the visualization
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
          animated: true,
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
        />

        <MiniMap
          nodeColor={(node) => {
            if (node.type === 'functionNode') return '#3b82f6';
            if (node.type === 'conditionalNode') return '#f59e0b';
            if (node.type === 'loopNode') return '#10b981';
            if (node.type === 'tryNode') return '#ef4444';
            return '#6b7280';
          }}
          className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg"
          maskColor={isDark ? 'rgb(17, 24, 39, 0.6)' : 'rgb(243, 244, 246, 0.6)'}
        />

        {/* Statistics overlay */}
        {statistics && (
          <div className="absolute top-4 right-4 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg shadow-lg p-4 min-w-[200px]">
            <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-3">
              Flow Statistics
            </h3>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-gray-600 dark:text-gray-400">Functions:</span>
                <span className="font-medium text-gray-900 dark:text-gray-100">
                  {statistics.total_functions}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600 dark:text-gray-400">Calls:</span>
                <span className="font-medium text-gray-900 dark:text-gray-100">
                  {statistics.total_calls}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600 dark:text-gray-400">Entry Points:</span>
                <span className="font-medium text-gray-900 dark:text-gray-100">
                  {statistics.entry_point_count}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600 dark:text-gray-400">Max Depth:</span>
                <span className="font-medium text-gray-900 dark:text-gray-100">
                  {statistics.max_call_depth}
                </span>
              </div>
              {statistics.circular_dependencies && statistics.circular_dependencies.length > 0 && (
                <div className="flex justify-between">
                  <span className="text-gray-600 dark:text-gray-400">Circular:</span>
                  <span className="font-medium text-orange-600 dark:text-orange-400">
                    {statistics.circular_dependencies.length}
                  </span>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Quick Organize button */}
        <button
          onClick={handleQuickOrganize}
          disabled={isLayouting}
          className="absolute bottom-4 left-4 px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 text-white rounded-lg shadow-lg text-sm font-medium transition-colors duration-200"
        >
          {isLayouting ? 'Organizing...' : 'Quick Organize'}
        </button>
      </ReactFlow>
    </div>
  );
}
