import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import ReactFlow, {
  MiniMap,
  Controls,
  Background,
  useNodesState,
  useEdgesState,
  addEdge,
} from 'reactflow';
import 'reactflow/dist/style.css';
import api, { projectsAPI } from '../../services/api';
import { toast } from 'react-toastify';
import { useTheme } from '../../context/ThemeContext';
import { getLayoutedElements, serializeLayout, applySavedLayout } from '../../utils/layoutUtils';

export default function ProjectVisualization() {
  const { projectId } = useParams();
  const navigate = useNavigate();
  const { isDark, toggleTheme } = useTheme();
  const [project, setProject] = useState(null);
  const [loading, setLoading] = useState(true);
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);

  // Layout state
  const [previousLayout, setPreviousLayout] = useState(null);
  const [isLayouting, setIsLayouting] = useState(false);
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [lastSaved, setLastSaved] = useState(null);

  const onConnect = useCallback(
    (params) => setEdges((eds) => addEdge(params, eds)),
    [setEdges]
  );

  // Track node changes and mark as unsaved when dragged
  const handleNodesChange = useCallback((changes) => {
    onNodesChange(changes);

    // Mark as unsaved if position changed after drag
    const hasPositionChange = changes.some(
      change => change.type === 'position' && change.dragging === false
    );

    if (hasPositionChange) {
      setHasUnsavedChanges(true);
    }
  }, [onNodesChange]);

  useEffect(() => {
    loadProjectAndVisualization();
  }, [projectId]);

  const loadProjectAndVisualization = async () => {
    try {
      // Load project details
      const projectResponse = await api.get(`/projects/${projectId}`);
      const projectData = projectResponse.data.project;
      setProject(projectData);

      // Fetch analysis results
      if (projectData.file_path) {
        try {
          // Get the latest analysis for this project
          const analysisResponse = await api.get(`/projects/${projectId}/analysis`);
          const schema = analysisResponse.data.schema;

          // Try to load saved layout
          try {
            const layoutResponse = await projectsAPI.getLayout(projectId);
            if (layoutResponse.data.layout) {
              createVisualizationWithLayout(schema, layoutResponse.data.layout.layout_data);
              setLastSaved(new Date(layoutResponse.data.layout.updated_at).getTime());
            } else {
              createVisualizationFromSchema(schema);
            }
          } catch (layoutErr) {
            // If layout fetch fails, just create default visualization
            createVisualizationFromSchema(schema);
          }
        } catch (err) {
          // If no analysis exists, show placeholder
          createVisualizationNodes(projectData);
        }
      } else {
        createVisualizationNodes(projectData);
      }
    } catch (error) {
      toast.error('Failed to load project');
      navigate('/dashboard');
    } finally {
      setLoading(false);
    }
  };

  const createVisualizationFromSchema = (schema) => {
    if (!schema || !schema.tables || schema.tables.length === 0) {
      createVisualizationNodes(project);
      return;
    }

    const newNodes = [];
    const newEdges = [];
    const colors = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899'];

    schema.tables.forEach((table, index) => {
      const x = 100 + (index % 3) * 300;
      const y = 100 + Math.floor(index / 3) * 250;

      newNodes.push({
        id: `table-${index}`,
        type: 'default',
        data: {
          label: (
            <div className="px-4 py-2">
              <div className="font-bold text-sm mb-2">{table.name}</div>
              <div className="text-xs space-y-1">
                {table.columns.map((col, colIdx) => (
                  <div key={colIdx}>
                    • {col.name} {col.type && `(${col.type})`}
                    {col.primary_key && ' PK'}
                  </div>
                ))}
              </div>
            </div>
          ),
          columns: table.columns, // Store for height estimation
        },
        position: { x, y },
        style: {
          background: 'var(--node-bg)',
          color: 'var(--node-text)',
          border: `2px solid ${colors[index % colors.length]}`,
          borderRadius: '8px',
          width: 220,
        },
      });
    });

    // Create edges from relationships
    if (schema.relationships) {
      schema.relationships.forEach((rel, index) => {
        const fromIndex = schema.tables.findIndex(t => t.name === rel.from_table);
        const toIndex = schema.tables.findIndex(t => t.name === rel.to_table);

        if (fromIndex !== -1 && toIndex !== -1) {
          newEdges.push({
            id: `edge-${index}`,
            source: `table-${fromIndex}`,
            target: `table-${toIndex}`,
            label: rel.from_column,
            animated: true,
            style: { stroke: colors[fromIndex % colors.length] },
            labelStyle: {
              fontSize: '18px',
              fontWeight: 500,
              fill: '#ffffff',
            },
            labelBgStyle: {
              fill: '#4b5563',
              fillOpacity: 1,
            },
            labelBgPadding: [8, 4],
            labelBgBorderRadius: 4,
          });
        }
      });
    }

    setNodes(newNodes);
    setEdges(newEdges);
  };

  const createVisualizationWithLayout = (schema, savedLayout) => {
    if (!schema || !schema.tables || schema.tables.length === 0) {
      createVisualizationNodes(project);
      return;
    }

    const newNodes = [];
    const newEdges = [];
    const colors = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899'];

    schema.tables.forEach((table, index) => {
      newNodes.push({
        id: `table-${index}`,
        type: 'default',
        data: {
          label: (
            <div className="px-4 py-2">
              <div className="font-bold text-sm mb-2">{table.name}</div>
              <div className="text-xs space-y-1">
                {table.columns.map((col, colIdx) => (
                  <div key={colIdx}>
                    • {col.name} {col.type && `(${col.type})`}
                    {col.primary_key && ' PK'}
                  </div>
                ))}
              </div>
            </div>
          ),
          columns: table.columns,
        },
        position: { x: 0, y: 0 }, // Will be updated by applySavedLayout
        style: {
          background: 'var(--node-bg)',
          color: 'var(--node-text)',
          border: `2px solid ${colors[index % colors.length]}`,
          borderRadius: '8px',
          width: 220,
        },
      });
    });

    // Create edges from relationships
    if (schema.relationships) {
      schema.relationships.forEach((rel, index) => {
        const fromIndex = schema.tables.findIndex(t => t.name === rel.from_table);
        const toIndex = schema.tables.findIndex(t => t.name === rel.to_table);

        if (fromIndex !== -1 && toIndex !== -1) {
          newEdges.push({
            id: `edge-${index}`,
            source: `table-${fromIndex}`,
            target: `table-${toIndex}`,
            label: rel.from_column,
            animated: true,
            style: { stroke: colors[fromIndex % colors.length] },
            labelStyle: {
              fontSize: '18px',
              fontWeight: 500,
              fill: '#ffffff',
            },
            labelBgStyle: {
              fill: '#4b5563',
              fillOpacity: 1,
            },
            labelBgPadding: [8, 4],
            labelBgBorderRadius: 4,
          });
        }
      });
    }

    // Apply saved layout positions
    const layoutedNodes = applySavedLayout(newNodes, savedLayout);

    setNodes(layoutedNodes);
    setEdges(newEdges);
  };

  const createVisualizationNodes = (project) => {
    // Placeholder when no analysis exists
    const sampleNodes = [
      {
        id: '1',
        type: 'default',
        data: {
          label: (
            <div className="px-4 py-2">
              <div className="font-bold text-sm mb-2">No Analysis Yet</div>
              <div className="text-xs text-gray-500">
                Upload files to see visualization
              </div>
            </div>
          ),
        },
        position: { x: 250, y: 150 },
        style: {
          background: 'var(--node-bg)',
          color: 'var(--node-text)',
          border: '2px solid #d1d5db',
          borderRadius: '8px',
          width: 200,
        },
      },
    ];

    setNodes(sampleNodes);
    setEdges([]);
  };

  // Event Handlers
  const handleQuickOrganize = async () => {
    if (nodes.length === 0) return;

    setIsLayouting(true);

    // Save current layout for undo
    setPreviousLayout({
      nodes: nodes.map(n => ({ id: n.id, position: { ...n.position } }))
    });

    // Apply dagre layout
    const { nodes: layoutedNodes, edges: processedEdges } = getLayoutedElements(nodes, edges, 'TB');

    setNodes(layoutedNodes);
    setEdges(processedEdges);
    setHasUnsavedChanges(true);
    setIsLayouting(false);

    toast.success('Layout organized!');
  };

  const handleUndoLayout = () => {
    if (!previousLayout) return;

    setNodes(currentNodes =>
      currentNodes.map(node => {
        const saved = previousLayout.nodes.find(n => n.id === node.id);
        return saved ? { ...node, position: { ...saved.position } } : node;
      })
    );

    setPreviousLayout(null);
    setHasUnsavedChanges(true);

    toast.info('Layout restored');
  };

  const handleSaveLayout = async () => {
    if (nodes.length === 0) return;

    setIsSaving(true);
    try {
      const layoutData = serializeLayout(nodes);
      await projectsAPI.saveLayout(projectId, layoutData);

      setHasUnsavedChanges(false);
      setLastSaved(Date.now());
      toast.success('Layout saved successfully!');
    } catch (error) {
      console.error('Failed to save layout:', error);
      toast.error('Failed to save layout');
    } finally {
      setIsSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-900">
        <div className="text-gray-600 dark:text-gray-300">Loading visualization...</div>
      </div>
    );
  }

  return (
    <div className="h-screen flex flex-col bg-gray-50 dark:bg-gray-900">
      {/* Header */}
      <header className="bg-white dark:bg-gray-800 shadow-sm px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <button
            onClick={() => navigate('/dashboard')}
            className="text-blue-600 hover:text-blue-700 dark:text-blue-400 dark:hover:text-blue-300"
          >
            ← Dashboard
          </button>
          <div>
            <h1 className="text-xl font-bold text-gray-900 dark:text-white">{project?.name}</h1>
            <p className="text-sm text-gray-500 dark:text-gray-400">Database Schema Visualization</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {/* Layout Controls */}
          {nodes.length > 0 && (
            <>
              <button
                onClick={handleQuickOrganize}
                disabled={isLayouting || nodes.length === 0}
                className="px-4 py-2 bg-blue-600 dark:bg-blue-700 text-white rounded hover:bg-blue-700 dark:hover:bg-blue-800 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
              >
                {isLayouting ? (
                  <>
                    <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                    </svg>
                    Organizing...
                  </>
                ) : (
                  'Quick Organize'
                )}
              </button>

              <button
                onClick={handleUndoLayout}
                disabled={!previousLayout}
                className="px-4 py-2 bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-200 rounded hover:bg-gray-300 dark:hover:bg-gray-600 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Undo Layout
              </button>

              <button
                onClick={handleSaveLayout}
                disabled={isSaving || !hasUnsavedChanges}
                className="px-4 py-2 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-200 rounded hover:bg-gray-50 dark:hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
              >
                {isSaving ? (
                  <>
                    <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                    </svg>
                    Saving...
                  </>
                ) : (
                  <>
                    Save Layout
                    {hasUnsavedChanges && <span className="text-yellow-600">•</span>}
                  </>
                )}
              </button>

              {lastSaved && (
                <span className="text-xs text-gray-500 dark:text-gray-400">
                  Saved {new Date(lastSaved).toLocaleTimeString()}
                </span>
              )}
            </>
          )}

          {/* Project Tags */}
          <div className="flex gap-2 ml-4 border-l dark:border-gray-600 pl-4">
            {project?.language && (
              <span className="px-3 py-1 bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-300 rounded text-sm">
                {project.language}
              </span>
            )}
            {project?.framework && (
              <span className="px-3 py-1 bg-green-100 dark:bg-green-900 text-green-700 dark:text-green-300 rounded text-sm">
                {project.framework}
              </span>
            )}
          </div>
        </div>
      </header>

      {/* Visualization */}
      <div className="flex-1 relative">
        <style>{`
          .react-flow__node {
            --node-bg: ${isDark ? '#1f2937' : '#ffffff'};
            --node-text: ${isDark ? '#f3f4f6' : '#111827'};
          }
          .react-flow__background {
            background-color: ${isDark ? '#111827' : '#f9fafb'};
          }
          .react-flow__edge-path {
            stroke: ${isDark ? '#6b7280' : '#9ca3af'};
          }
          .react-flow__minimap {
            background-color: ${isDark ? '#1f2937' : '#ffffff'};
          }
          .react-flow__controls {
            background-color: ${isDark ? '#1f2937' : '#ffffff'};
            border: 1px solid ${isDark ? '#374151' : '#e5e7eb'};
          }
          .react-flow__controls-button {
            background-color: ${isDark ? '#1f2937' : '#ffffff'};
            color: ${isDark ? '#f3f4f6' : '#111827'};
            border-bottom: 1px solid ${isDark ? '#374151' : '#e5e7eb'};
          }
          .react-flow__controls-button:hover {
            background-color: ${isDark ? '#374151' : '#f3f4f6'};
          }
        `}</style>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={handleNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          fitView
        >
          <Controls />
          <MiniMap />
          <Background variant="dots" gap={12} size={1} />
        </ReactFlow>

        {/* Theme Toggle Button */}
        <button
          onClick={toggleTheme}
          className="absolute bottom-5 left-5 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded shadow-md p-2 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
          title={isDark ? 'Switch to Light Mode' : 'Switch to Dark Mode'}
          style={{ zIndex: 5 }}
        >
          {isDark ? (
            <svg className="w-5 h-5 text-yellow-400" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M10 2a1 1 0 011 1v1a1 1 0 11-2 0V3a1 1 0 011-1zm4 8a4 4 0 11-8 0 4 4 0 018 0zm-.464 4.95l.707.707a1 1 0 001.414-1.414l-.707-.707a1 1 0 00-1.414 1.414zm2.12-10.607a1 1 0 010 1.414l-.706.707a1 1 0 11-1.414-1.414l.707-.707a1 1 0 011.414 0zM17 11a1 1 0 100-2h-1a1 1 0 100 2h1zm-7 4a1 1 0 011 1v1a1 1 0 11-2 0v-1a1 1 0 011-1zM5.05 6.464A1 1 0 106.465 5.05l-.708-.707a1 1 0 00-1.414 1.414l.707.707zm1.414 8.486l-.707.707a1 1 0 01-1.414-1.414l.707-.707a1 1 0 011.414 1.414zM4 11a1 1 0 100-2H3a1 1 0 000 2h1z" clipRule="evenodd" />
            </svg>
          ) : (
            <svg className="w-5 h-5 text-gray-700" fill="currentColor" viewBox="0 0 20 20">
              <path d="M17.293 13.293A8 8 0 016.707 2.707a8.001 8.001 0 1010.586 10.586z" />
            </svg>
          )}
        </button>
      </div>

      {/* Info Panel */}
      <div className="bg-white dark:bg-gray-800 border-t border-gray-200 dark:border-gray-700 px-6 py-3">
        <div className="flex items-center justify-between text-sm text-gray-600 dark:text-gray-300">
          <div>
            <span className="font-medium">Tables:</span> {nodes.length} |{' '}
            <span className="font-medium">Relationships:</span> {edges.length}
          </div>
          <div className="text-xs">
            Tip: Drag nodes to rearrange, scroll to zoom, click and drag background to pan
          </div>
        </div>
      </div>
    </div>
  );
}
