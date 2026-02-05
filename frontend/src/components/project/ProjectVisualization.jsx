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
import api from '../../services/api';
import { toast } from 'react-toastify';

export default function ProjectVisualization() {
  const { projectId } = useParams();
  const navigate = useNavigate();
  const [project, setProject] = useState(null);
  const [loading, setLoading] = useState(true);
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);

  const onConnect = useCallback(
    (params) => setEdges((eds) => addEdge(params, eds)),
    [setEdges]
  );

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
          createVisualizationFromSchema(schema);
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
        },
        position: { x, y },
        style: {
          background: '#fff',
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
          });
        }
      });
    }

    setNodes(newNodes);
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
          background: '#fff',
          border: '2px solid #d1d5db',
          borderRadius: '8px',
          width: 200,
        },
      },
    ];

    setNodes(sampleNodes);
    setEdges([]);
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-gray-600">Loading visualization...</div>
      </div>
    );
  }

  return (
    <div className="h-screen flex flex-col bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow-sm px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <button
            onClick={() => navigate('/dashboard')}
            className="text-blue-600 hover:text-blue-700"
          >
            ← Dashboard
          </button>
          <div>
            <h1 className="text-xl font-bold text-gray-900">{project?.name}</h1>
            <p className="text-sm text-gray-500">Database Schema Visualization</p>
          </div>
        </div>
        <div className="flex gap-2">
          {project?.language && (
            <span className="px-3 py-1 bg-blue-100 text-blue-700 rounded text-sm">
              {project.language}
            </span>
          )}
          {project?.framework && (
            <span className="px-3 py-1 bg-green-100 text-green-700 rounded text-sm">
              {project.framework}
            </span>
          )}
        </div>
      </header>

      {/* Visualization */}
      <div className="flex-1">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          fitView
        >
          <Controls />
          <MiniMap />
          <Background variant="dots" gap={12} size={1} />
        </ReactFlow>
      </div>

      {/* Info Panel */}
      <div className="bg-white border-t border-gray-200 px-6 py-3">
        <div className="flex items-center justify-between text-sm text-gray-600">
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
