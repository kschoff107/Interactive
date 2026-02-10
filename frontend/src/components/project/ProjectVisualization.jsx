import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import ReactFlow, {
  MiniMap,
  Controls,
  ControlButton,
  Background,
  useNodesState,
  useEdgesState,
  addEdge,
} from 'reactflow';
import 'reactflow/dist/style.css';
import api, { projectsAPI, workspacesAPI } from '../../services/api';
import { toast } from 'react-toastify';
import { useTheme } from '../../context/ThemeContext';
import { getLayoutedElements, serializeLayout, applySavedLayout } from '../../utils/layoutUtils';
import StickyNote from './StickyNote';
import Sidebar from './Sidebar';
import FlowVisualization from './FlowVisualization';
import ApiRoutesVisualization from './ApiRoutesVisualization';
import CenterUploadArea from './CenterUploadArea';

// Register custom node types
const nodeTypes = {
  stickyNote: StickyNote,
};

export default function ProjectVisualization() {
  const { projectId } = useParams();
  const navigate = useNavigate();
  const { isDark, toggleTheme } = useTheme();
  const [project, setProject] = useState(null);
  const [loading, setLoading] = useState(true);
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);

  // View state
  const [activeView, setActiveView] = useState('schema');

  // Runtime flow state
  const [runtimeFlowData, setRuntimeFlowData] = useState(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [flowLoading, setFlowLoading] = useState(false);
  const [flowLayoutTrigger, setFlowLayoutTrigger] = useState(0);

  // API routes state
  const [apiRoutesData, setApiRoutesData] = useState(null);
  const [isAnalyzingRoutes, setIsAnalyzingRoutes] = useState(false);
  const [apiRoutesLoading, setApiRoutesLoading] = useState(false);
  const [apiRoutesLayoutTrigger, setApiRoutesLayoutTrigger] = useState(0);

  // Project status state
  const [projectStatus, setProjectStatus] = useState({
    has_database_schema: false,
    has_runtime_flow: false,
    has_api_routes: false,
    last_upload_date: null
  });

  // Workspace state
  const [workspaces, setWorkspaces] = useState({});
  const [activeWorkspaceId, setActiveWorkspaceId] = useState(null);

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

  // Fetch project status
  const fetchProjectStatus = async () => {
    console.log('[DEBUG] Fetching project status for project:', projectId);
    try {
      const response = await api.get(`/projects/${projectId}/status`);
      console.log('[DEBUG] Project status response:', response.data);
      setProjectStatus(response.data);
    } catch (error) {
      console.error('Error fetching project status:', error);
    }
  };

  // Helper mappings
  const viewToAnalysisType = (view) => {
    const map = { schema: 'database_schema', flow: 'runtime_flow', api: 'api_routes' };
    return map[view];
  };
  const analysisTypeToView = (at) => {
    const map = { database_schema: 'schema', runtime_flow: 'flow', api_routes: 'api' };
    return map[at];
  };

  // Load workspaces
  const loadWorkspaces = async (selectView, selectWorkspaceId) => {
    try {
      const response = await workspacesAPI.list(projectId);
      const ws = response.data.workspaces || {};
      setWorkspaces(ws);

      // If a specific workspace was requested, select it
      if (selectWorkspaceId) {
        setActiveWorkspaceId(selectWorkspaceId);
        return;
      }

      // Auto-select first workspace of current (or requested) view
      const view = selectView || activeView;
      const at = viewToAnalysisType(view);
      const viewWorkspaces = ws[at] || [];
      if (viewWorkspaces.length > 0 && !activeWorkspaceId) {
        setActiveWorkspaceId(viewWorkspaces[0].id);
      }
    } catch (error) {
      console.error('Failed to load workspaces:', error);
    }
  };

  // Workspace handlers
  const handleWorkspaceSelect = (viewId, workspaceId) => {
    // Clear cached data when switching workspaces
    if (workspaceId !== activeWorkspaceId) {
      setRuntimeFlowData(null);
      setApiRoutesData(null);
      setNodes([]);
      setEdges([]);
      setHasUnsavedChanges(false);
      setLastSaved(null);
    }
    setActiveView(viewId);
    setActiveWorkspaceId(workspaceId);
  };

  const handleWorkspaceCreate = async (analysisType) => {
    try {
      const response = await workspacesAPI.create(projectId, analysisType, '');
      const newWs = response.data.workspace;
      await loadWorkspaces(null, newWs.id);
      // Switch to the new workspace
      const viewId = analysisTypeToView(analysisType);
      setActiveView(viewId);
      setActiveWorkspaceId(newWs.id);
      // Clear data for fresh workspace
      setRuntimeFlowData(null);
      setApiRoutesData(null);
      setNodes([]);
      setEdges([]);
      setHasUnsavedChanges(false);
      setLastSaved(null);
      toast.success('Workspace created');
    } catch (error) {
      toast.error('Failed to create workspace');
    }
  };

  const handleWorkspaceRename = async (workspaceId, newName) => {
    try {
      await workspacesAPI.rename(projectId, workspaceId, newName);
      await loadWorkspaces();
    } catch (error) {
      toast.error('Failed to rename workspace');
    }
  };

  const handleWorkspaceDelete = async (workspaceId) => {
    try {
      await workspacesAPI.delete(projectId, workspaceId);
      // If deleting the active workspace, switch to another or clear
      if (workspaceId === activeWorkspaceId) {
        const at = viewToAnalysisType(activeView);
        const remaining = (workspaces[at] || []).filter(ws => ws.id !== workspaceId);
        setRuntimeFlowData(null);
        setApiRoutesData(null);
        setNodes([]);
        setEdges([]);
        setHasUnsavedChanges(false);
        setLastSaved(null);
        if (remaining.length > 0) {
          setActiveWorkspaceId(remaining[0].id);
        } else {
          setActiveWorkspaceId(null);
        }
      }
      await loadWorkspaces();
      toast.success('Workspace deleted');
    } catch (error) {
      const msg = error.response?.data?.error || 'Failed to delete workspace';
      toast.error(msg);
    }
  };

  useEffect(() => {
    console.log('[DEBUG] Initial mount - loading project and status');
    loadProjectAndVisualization();
    fetchProjectStatus();
    loadWorkspaces();
  }, [projectId]);

  // Load data when switching views or workspaces
  useEffect(() => {
    if (!project || !activeWorkspaceId) return;
    if (activeView === 'flow') {
      loadRuntimeFlowData();
    } else if (activeView === 'api') {
      loadApiRoutesData();
    } else if (activeView === 'schema') {
      loadSchemaForWorkspace();
    }
  }, [activeView, activeWorkspaceId, project]);

  // Workspace-level empty state: show upload area when active workspace has no data
  const isWorkspaceEmpty = (() => {
    if (activeView === 'schema') {
      // Schema is empty if nodes only contain the placeholder node
      return nodes.length === 0 || (nodes.length === 1 && nodes[0].id === '1');
    }
    if (activeView === 'flow') return !runtimeFlowData && !flowLoading && !isAnalyzing;
    if (activeView === 'api') return !apiRoutesData && !apiRoutesLoading && !isAnalyzingRoutes;
    return false;
  })();

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
              fill: colors[fromIndex % colors.length],
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
              fill: colors[fromIndex % colors.length],
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

    // Restore sticky notes from saved layout
    const stickyNotes = [];
    if (savedLayout && savedLayout.nodes) {
      savedLayout.nodes.forEach((savedNode) => {
        if (savedNode.type === 'stickyNote') {
          stickyNotes.push({
            id: savedNode.id,
            type: 'stickyNote',
            position: savedNode.position,
            data: {
              id: savedNode.id,
              text: savedNode.data.text || '',
              color: savedNode.data.color || 'yellow',
              onTextChange: handleNoteTextChange,
              onColorChange: handleNoteColorChange,
              onDelete: handleDeleteNote,
            },
          });
        }
      });
    }

    setNodes([...layoutedNodes, ...stickyNotes]);
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
    if (activeView === 'schema' && nodes.length === 0) return;
    if (activeView === 'flow' && !runtimeFlowData) return;
    if (activeView === 'api' && !apiRoutesData) return;

    setIsLayouting(true);

    if (activeView === 'schema') {
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
    } else if (activeView === 'flow') {
      // Trigger re-layout in FlowVisualization component
      setFlowLayoutTrigger(prev => prev + 1);
      setTimeout(() => setIsLayouting(false), 300);
      toast.success('Layout organized!');
    } else if (activeView === 'api') {
      // Trigger re-layout in ApiRoutesVisualization component
      setApiRoutesLayoutTrigger(prev => prev + 1);
      setTimeout(() => setIsLayouting(false), 300);
      toast.success('Layout organized!');
    }
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
      if (activeWorkspaceId) {
        await workspacesAPI.saveLayout(projectId, activeWorkspaceId, layoutData);
      } else {
        await projectsAPI.saveLayout(projectId, layoutData);
      }

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

  // Sticky Note handlers
  const handleAddNote = () => {
    const newNote = {
      id: `note-${Date.now()}`,
      type: 'stickyNote',
      position: { x: 250, y: 150 },
      data: {
        id: `note-${Date.now()}`,
        text: '',
        color: 'yellow',
        onTextChange: handleNoteTextChange,
        onColorChange: handleNoteColorChange,
        onDelete: handleDeleteNote,
      },
    };
    setNodes((nds) => [...nds, newNote]);
    setHasUnsavedChanges(true);
  };

  const handleNoteTextChange = (noteId, newText) => {
    setNodes((nds) =>
      nds.map((node) => {
        if (node.id === noteId) {
          return {
            ...node,
            data: { ...node.data, text: newText },
          };
        }
        return node;
      })
    );
    setHasUnsavedChanges(true);
  };

  const handleNoteColorChange = (noteId, newColor) => {
    setNodes((nds) =>
      nds.map((node) => {
        if (node.id === noteId) {
          return {
            ...node,
            data: { ...node.data, color: newColor },
          };
        }
        return node;
      })
    );
    setHasUnsavedChanges(true);
  };

  const handleDeleteNote = (noteId) => {
    setNodes((nds) => nds.filter((node) => node.id !== noteId));
    setHasUnsavedChanges(true);
    toast.success('Note deleted');
  };

  const loadRuntimeFlowData = async () => {
    if (flowLoading) return;

    setFlowLoading(true);
    setRuntimeFlowData(null);
    try {
      const response = activeWorkspaceId
        ? await workspacesAPI.getRuntimeFlow(projectId, activeWorkspaceId)
        : await api.get(`/projects/${projectId}/runtime-flow`);
      setRuntimeFlowData(response.data.flow);
    } catch (error) {
      if (error.response?.status === 404) {
        console.log('No runtime flow analysis found');
      } else {
        console.error('Failed to load runtime flow:', error);
      }
    } finally {
      setFlowLoading(false);
    }
  };

  const handleAnalyzeRuntimeFlow = async () => {
    setIsAnalyzing(true);
    try {
      const response = activeWorkspaceId
        ? await workspacesAPI.analyzeRuntimeFlow(projectId, activeWorkspaceId)
        : await api.post(`/projects/${projectId}/analyze/runtime-flow`);
      setRuntimeFlowData(response.data.flow);
      toast.success('Runtime flow analysis completed');
    } catch (error) {
      const errorMsg = error.response?.data?.error || 'Failed to analyze runtime flow';
      toast.error(errorMsg);
      console.error('Runtime flow analysis error:', error);
    } finally {
      setIsAnalyzing(false);
    }
  };

  const loadApiRoutesData = async () => {
    if (apiRoutesLoading) return;

    setApiRoutesLoading(true);
    setApiRoutesData(null);
    try {
      const response = activeWorkspaceId
        ? await workspacesAPI.getApiRoutes(projectId, activeWorkspaceId)
        : await api.get(`/projects/${projectId}/api-routes`);
      setApiRoutesData(response.data.routes);
    } catch (error) {
      if (error.response?.status === 404) {
        console.log('No API routes analysis found');
      } else {
        console.error('Failed to load API routes:', error);
      }
    } finally {
      setApiRoutesLoading(false);
    }
  };

  const handleAnalyzeApiRoutes = async () => {
    setIsAnalyzingRoutes(true);
    try {
      const response = activeWorkspaceId
        ? await workspacesAPI.analyzeApiRoutes(projectId, activeWorkspaceId)
        : await api.post(`/projects/${projectId}/analyze/api-routes`);
      setApiRoutesData(response.data.routes);
      setProjectStatus(prev => ({ ...prev, has_api_routes: true }));
      toast.success('API routes analysis completed');
    } catch (error) {
      const errorMsg = error.response?.data?.error || 'Failed to analyze API routes';
      toast.error(errorMsg);
      console.error('API routes analysis error:', error);
    } finally {
      setIsAnalyzingRoutes(false);
    }
  };

  const loadSchemaForWorkspace = async () => {
    if (!activeWorkspaceId) return;
    try {
      const analysisResponse = await workspacesAPI.getAnalysis(projectId, activeWorkspaceId);
      const schema = analysisResponse.data.schema;

      // Try to load workspace layout
      try {
        const layoutResponse = await workspacesAPI.getLayout(projectId, activeWorkspaceId);
        if (layoutResponse.data.layout) {
          createVisualizationWithLayout(schema, layoutResponse.data.layout.layout_data);
          setLastSaved(new Date(layoutResponse.data.layout.updated_at).getTime());
        } else {
          createVisualizationFromSchema(schema);
        }
      } catch (layoutErr) {
        createVisualizationFromSchema(schema);
      }
    } catch (err) {
      if (err.response?.status === 404) {
        createVisualizationNodes(project);
      }
    }
  };

  const handleUploadComplete = async (result) => {
    toast.success('Files uploaded! Running analysis...');

    // After uploading files to workspace, trigger analysis
    try {
      if (activeView === 'flow') {
        await handleAnalyzeRuntimeFlow();
      } else if (activeView === 'api') {
        await handleAnalyzeApiRoutes();
      } else if (activeView === 'schema') {
        // Reload schema data for workspace
        await loadSchemaForWorkspace();
      }
    } catch (error) {
      // Analysis errors are handled in the individual handlers
    }

    // Refresh workspace list (file counts may have changed)
    await loadWorkspaces();
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
      <header className="bg-white dark:bg-gray-800 shadow-sm px-6 py-4 flex items-center justify-between z-10">
        <div className="flex items-center gap-4">
          <button
            onClick={() => navigate('/dashboard')}
            className="text-blue-600 hover:text-blue-700 dark:text-blue-400 dark:hover:text-blue-300"
          >
            ← Dashboard
          </button>
          <div>
            <h1 className="text-xl font-bold text-gray-900 dark:text-white">{project?.name}</h1>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              {activeView === 'schema' && 'Database Schema Visualization'}
              {activeView === 'flow' && 'Runtime Flow Visualization'}
              {activeView === 'api' && 'API Routes Visualization'}
              {activeView === 'structure' && 'Code Structure Visualization'}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {/* Runtime Flow Analysis Button */}
          {activeView === 'flow' && (
            <button
              onClick={handleAnalyzeRuntimeFlow}
              disabled={isAnalyzing}
              className="px-4 py-2 bg-purple-600 dark:bg-purple-700 text-white rounded hover:bg-purple-700 dark:hover:bg-purple-800 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
            >
              {isAnalyzing ? (
                <>
                  <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                  Analyzing...
                </>
              ) : (
                <>
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
                  </svg>
                  Analyze Runtime Flow
                </>
              )}
            </button>
          )}

          {/* API Routes Analysis Button */}
          {activeView === 'api' && (
            <button
              onClick={handleAnalyzeApiRoutes}
              disabled={isAnalyzingRoutes}
              className="px-4 py-2 bg-teal-600 dark:bg-teal-700 text-white rounded hover:bg-teal-700 dark:hover:bg-teal-800 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
            >
              {isAnalyzingRoutes ? (
                <>
                  <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                  Analyzing...
                </>
              ) : (
                <>
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9" />
                  </svg>
                  Analyze API Routes
                </>
              )}
            </button>
          )}

          {/* Layout Controls - Show for schema, flow, and api views */}
          {((activeView === 'schema' && nodes.length > 0) || (activeView === 'flow' && runtimeFlowData) || (activeView === 'api' && apiRoutesData)) && (
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

      {/* Main Content with Sidebar */}
      <div className="flex-1 flex overflow-hidden">
        {/* Sidebar */}
        <Sidebar
          activeView={activeView}
          onViewChange={setActiveView}
          project={project}
          workspaces={workspaces}
          activeWorkspaceId={activeWorkspaceId}
          onWorkspaceSelect={handleWorkspaceSelect}
          onWorkspaceCreate={handleWorkspaceCreate}
          onWorkspaceRename={handleWorkspaceRename}
          onWorkspaceDelete={handleWorkspaceDelete}
        />

        {/* Visualization Area */}
        <div className="flex-1 flex flex-col">
          {/* Visualization */}
          <div className="flex-1 relative">
            {activeView === 'schema' && (
              <>
                {isWorkspaceEmpty ? (
                  <CenterUploadArea
                    projectId={projectId}
                    workspaceId={activeWorkspaceId}
                    analysisType="database_schema"
                    onUploadComplete={handleUploadComplete}
                  />
                ) : (
                  <>
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
                      nodeTypes={nodeTypes}
                    >
                      <Controls>
                        <ControlButton
                          onClick={handleAddNote}
                          title="Add Sticky Note"
                        >
                          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                          </svg>
                        </ControlButton>
                        <ControlButton
                          onClick={toggleTheme}
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
                      <MiniMap />
                      <Background variant="dots" gap={12} size={1} />
                    </ReactFlow>
                  </>
                )}
              </>
            )}

            {activeView === 'flow' && (
              <>
                {isWorkspaceEmpty ? (
                  <CenterUploadArea
                    projectId={projectId}
                    workspaceId={activeWorkspaceId}
                    analysisType="runtime_flow"
                    onUploadComplete={handleUploadComplete}
                  />
                ) : (
                  <FlowVisualization
                    flowData={runtimeFlowData}
                    isDark={isDark}
                    onToggleTheme={toggleTheme}
                    layoutTrigger={flowLayoutTrigger}
                    projectId={projectId}
                  />
                )}
              </>
            )}

            {activeView === 'api' && (
              <>
                {isWorkspaceEmpty ? (
                  <CenterUploadArea
                    projectId={projectId}
                    workspaceId={activeWorkspaceId}
                    analysisType="api_routes"
                    onUploadComplete={handleUploadComplete}
                  />
                ) : (
                  <ApiRoutesVisualization
                    routesData={apiRoutesData}
                    isDark={isDark}
                    onToggleTheme={toggleTheme}
                    layoutTrigger={apiRoutesLayoutTrigger}
                    projectId={projectId}
                  />
                )}
              </>
            )}

            {activeView !== 'schema' && activeView !== 'flow' && activeView !== 'api' && (
              <div className="flex items-center justify-center h-full">
                <div className="text-center">
                  <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
                  </svg>
                  <h3 className="mt-2 text-sm font-medium text-gray-900 dark:text-gray-100">
                    Coming Soon
                  </h3>
                  <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
                    This visualization type is under development
                  </p>
                </div>
              </div>
            )}
          </div>

          {/* Info Panel */}
          {activeView === 'schema' && (
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
          )}
        </div>
      </div>
    </div>
  );
}
