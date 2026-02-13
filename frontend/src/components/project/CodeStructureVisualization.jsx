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

import ClassNode from './nodes/ClassNode';
import ModuleNode from './nodes/ModuleNode';
import StickyNote from './StickyNote';
import { StickyNoteButton, ThemeToggleButton } from './ToolbarButtons';
import CodeStructureInsightGuide from './CodeStructureInsightGuide';
import NodeDetailModal from './NodeDetailModal';
import { transformCodeStructureData, estimateStructureNodeHeight, getStructureNodeWidth } from '../../utils/codeStructureTransform';
import { applySavedLayout } from '../../utils/layoutUtils';
import { useStickyNotes, restoreStickyNotesFromLayout } from '../../hooks/useStickyNotes';
import { useEdgeHighlighting } from '../../hooks/useEdgeHighlighting';

const nodeTypes = {
  classNode: ClassNode,
  moduleNode: ModuleNode,
  stickyNote: StickyNote,
};

/**
 * Apply Dagre layout to structure nodes
 */
const getLayoutedStructureElements = (nodes, edges, direction = 'TB') => {
  const stickyNotes = nodes.filter(n => n.type === 'stickyNote');
  const structureNodes = nodes.filter(n => n.type !== 'stickyNote');

  const dagreGraph = new dagre.graphlib.Graph();
  dagreGraph.setDefaultEdgeLabel(() => ({}));

  dagreGraph.setGraph({
    rankdir: direction,
    nodesep: 140,
    ranksep: 180,
    marginx: 50,
    marginy: 50,
  });

  structureNodes.forEach((node) => {
    const width = getStructureNodeWidth(node);
    const height = estimateStructureNodeHeight(node);
    dagreGraph.setNode(node.id, { width, height });
  });

  edges.forEach((edge) => {
    dagreGraph.setEdge(edge.source, edge.target);
  });

  dagre.layout(dagreGraph);

  const layoutedNodes = structureNodes.map((node) => {
    const nodeWithPosition = dagreGraph.node(node.id);
    const width = getStructureNodeWidth(node);
    const height = estimateStructureNodeHeight(node);

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

export default function CodeStructureVisualization({ structureData, isDark, onToggleTheme, layoutTrigger, projectId, savedLayout, onNodesUpdate, onNodesDragged }) {
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

  // Transform and layout structure data on initial load
  useEffect(() => {
    if (structureData) {
      const { nodes: structureNodes, edges: structureEdges } = transformCodeStructureData(structureData);

      if (structureNodes.length > 0) {
        const { nodes: layoutedNodes, edges: layoutedEdges } = getLayoutedStructureElements(
          structureNodes,
          structureEdges
        );

        const finalNodes = applySavedLayout(layoutedNodes, savedLayout);

        const stickyNotes = restoreStickyNotesFromLayout(savedLayout, {
          onTextChange: handleNoteTextChange,
          onColorChange: handleNoteColorChange,
          onDelete: handleDeleteNote,
        });

        setNodes([...finalNodes, ...stickyNotes]);
        setEdges(layoutedEdges);
        setInitialNodes(structureNodes);
        setInitialEdges(structureEdges);
      }
    }
  }, [structureData, savedLayout, setNodes, setEdges, handleNoteTextChange, handleNoteColorChange, handleDeleteNote]);

  // Re-layout when layoutTrigger changes (preserve sticky notes)
  useEffect(() => {
    if (layoutTrigger > 0 && initialNodes.length > 0) {
      const { nodes: layoutedNodes, edges: layoutedEdges } = getLayoutedStructureElements(
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

  const statistics = structureData?.statistics ?? null;

  if (!structureData || nodes.length === 0) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center">
          <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2"
              d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
          </svg>
          <h3 className="mt-2 text-sm font-medium text-gray-900 dark:text-gray-100">
            No code structure data
          </h3>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
            Click "Analyze Code Structure" to generate the visualization
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
            if (node.type === 'moduleNode') return '#64748b';
            if (node.type === 'classNode') {
              if (node.data?.is_interface) return '#06b6d4';
              if (node.data?.is_abstract) return '#f59e0b';
              return '#6366f1';
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

        {/* Statistics overlay */}
        {statistics && (
          <div className="absolute top-4 right-4 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg shadow-lg p-4 min-w-[200px]">
            <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-3">
              Structure Statistics
            </h3>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-gray-600 dark:text-gray-400">Modules:</span>
                <span className="font-medium text-gray-900 dark:text-gray-100">
                  {statistics.total_modules}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600 dark:text-gray-400">Classes:</span>
                <span className="font-medium text-gray-900 dark:text-gray-100">
                  {statistics.total_classes}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600 dark:text-gray-400">Methods:</span>
                <span className="font-medium text-gray-900 dark:text-gray-100">
                  {statistics.total_methods}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600 dark:text-gray-400">Properties:</span>
                <span className="font-medium text-gray-900 dark:text-gray-100">
                  {statistics.total_properties}
                </span>
              </div>
              {statistics.classes_with_inheritance > 0 && (
                <div className="flex justify-between">
                  <span className="text-gray-600 dark:text-gray-400">Inheritance:</span>
                  <span className="font-medium text-indigo-600 dark:text-indigo-400">
                    {statistics.classes_with_inheritance} chains
                  </span>
                </div>
              )}
              {statistics.max_inheritance_depth > 0 && (
                <div className="flex justify-between">
                  <span className="text-gray-600 dark:text-gray-400">Max Depth:</span>
                  <span className="font-medium text-gray-900 dark:text-gray-100">
                    {statistics.max_inheritance_depth}
                  </span>
                </div>
              )}
            </div>
          </div>
        )}
      </ReactFlow>

      {/* Insight Guide Modal */}
      <CodeStructureInsightGuide
        isOpen={showInsightGuide}
        onClose={() => setShowInsightGuide(false)}
        isDark={isDark}
        structureData={structureData}
        projectId={projectId}
      />

      {/* Node Detail Modal */}
      <NodeDetailModal
        isOpen={!!detailNode}
        onClose={handleDetailClose}
        isDark={isDark}
        node={detailNode}
        edges={edges}
        contextData={{ structure: structureData }}
      />
    </div>
  );
}
