import React, { useState, useEffect, useCallback } from 'react';
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
import StickyNote from './StickyNote';
import { StickyNoteButton, ThemeToggleButton } from './ToolbarButtons';
import InsightGuide from './InsightGuide';
import NodeDetailModal from './NodeDetailModal';
import { transformFlowData, estimateFlowNodeHeight, getFlowNodeWidth } from '../../utils/flowTransform';
import { detectCircularEdges, applySavedLayout } from '../../utils/layoutUtils';
import { useStickyNotes, restoreStickyNotesFromLayout } from '../../hooks/useStickyNotes';
import { useEdgeHighlighting } from '../../hooks/useEdgeHighlighting';

// Register custom node types for runtime flow
const nodeTypes = {
  functionNode: FunctionNode,
  conditionalNode: ConditionalNode,
  loopNode: LoopNode,
  tryNode: TryNode,
  stickyNote: StickyNote,
};

/**
 * Apply Dagre layout to flow nodes
 */
const getLayoutedFlowElements = (nodes, edges, direction = 'TB') => {
  // Separate sticky notes from flow nodes — notes skip dagre layout
  const stickyNotes = nodes.filter(n => n.type === 'stickyNote');
  const flowNodes = nodes.filter(n => n.type !== 'stickyNote');

  const dagreGraph = new dagre.graphlib.Graph();
  dagreGraph.setDefaultEdgeLabel(() => ({}));

  dagreGraph.setGraph({
    rankdir: direction,
    nodesep: 160,
    ranksep: 220,
    marginx: 50,
    marginy: 50,
  });

  // Detect circular edges
  const circularEdgeIds = detectCircularEdges(edges, flowNodes);

  // Add nodes to dagre
  flowNodes.forEach((node) => {
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
  const layoutedNodes = flowNodes.map((node) => {
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

  return { nodes: [...layoutedNodes, ...stickyNotes], edges: layoutedEdges };
};

export default function FlowVisualization({ flowData, isDark, onToggleTheme, layoutTrigger, projectId, savedLayout, onNodesUpdate, onNodesDragged }) {
  const [nodes, setNodes, onNodesChangeBase] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [initialNodes, setInitialNodes] = useState([]);
  const [initialEdges, setInitialEdges] = useState([]);
  const [showInsightGuide, setShowInsightGuide] = useState(false);
  const [detailNode, setDetailNode] = useState(null);
  const handleDetailClose = useCallback(() => setDetailNode(null), []);

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

  // Edge highlighting on hover
  const {
    highlightedNodes,
    highlightedEdges,
    onNodeMouseEnter,
    onNodeMouseLeave,
    onEdgeMouseEnter,
    onEdgeMouseLeave,
  } = useEdgeHighlighting(nodes, edges);

  // Transform and layout flow data on initial load
  useEffect(() => {
    if (flowData) {
      const { nodes: flowNodes, edges: flowEdges } = transformFlowData(flowData);

      if (flowNodes.length > 0) {
        const { nodes: layoutedNodes, edges: layoutedEdges } = getLayoutedFlowElements(
          flowNodes,
          flowEdges
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
        setInitialNodes(flowNodes);
        setInitialEdges(flowEdges);
      }
    }
  }, [flowData, savedLayout, setNodes, setEdges, handleNoteTextChange, handleNoteColorChange, handleDeleteNote]);

  // Re-layout when layoutTrigger changes (preserve sticky notes)
  useEffect(() => {
    if (layoutTrigger > 0 && initialNodes.length > 0) {
      const { nodes: layoutedNodes, edges: layoutedEdges } = getLayoutedFlowElements(
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

  // Handle double-click to show node detail
  const handleNodeDoubleClick = useCallback((event, node) => {
    if (node.type === 'stickyNote') return;
    setDetailNode(node);
  }, []);

  const statistics = flowData?.statistics ?? null;

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
        nodes={highlightedNodes}
        edges={highlightedEdges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeMouseEnter={onNodeMouseEnter}
        onNodeMouseLeave={onNodeMouseLeave}
        onEdgeMouseEnter={onEdgeMouseEnter}
        onEdgeMouseLeave={onEdgeMouseLeave}
        onNodeDoubleClick={handleNodeDoubleClick}
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
        >
          <StickyNoteButton onAddNote={handleAddNote} />
          <ThemeToggleButton isDark={isDark} onToggle={onToggleTheme} />
        </Controls>

        <MiniMap
          nodeColor={(node) => {
            if (node.type === 'stickyNote') return '#fbbf24';
            if (node.type === 'functionNode') return '#3b82f6';
            if (node.type === 'conditionalNode') return '#f59e0b';
            if (node.type === 'loopNode') return '#10b981';
            if (node.type === 'tryNode') return '#ef4444';
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

      </ReactFlow>

      {/* Insight Guide Modal */}
      <InsightGuide
        isOpen={showInsightGuide}
        onClose={() => setShowInsightGuide(false)}
        isDark={isDark}
        flowData={flowData}
        projectId={projectId}
      />

      {/* Node Detail Modal */}
      <NodeDetailModal
        isOpen={!!detailNode}
        onClose={handleDetailClose}
        isDark={isDark}
        node={detailNode}
        edges={edges}
        contextData={{ flowData }}
      />
    </div>
  );
}
