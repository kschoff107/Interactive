import React, { useState, useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { workspacesAPI } from '../../services/api';
import './CenterUploadArea.css';

const CenterUploadArea = ({ projectId, workspaceId, analysisType, onUploadComplete, onAnalyze, hasSourceFiles, onImportSourceFiles }) => {
  const [uploading, setUploading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState(null);
  const [isSourceDragOver, setIsSourceDragOver] = useState(false);

  const onDrop = useCallback(async (acceptedFiles) => {
    if (acceptedFiles.length === 0) return;
    if (!workspaceId) return;

    setUploading(true);
    setUploadStatus(null);

    try {
      const response = await workspacesAPI.uploadFiles(projectId, workspaceId, acceptedFiles);
      const result = response.data;

      if (result.message) {
        setUploadStatus({
          type: 'success',
          message: result.message,
          details: result.uploads
        });

        // Notify parent component after a short delay
        setTimeout(() => {
          onUploadComplete(result);
        }, 1500);
      } else {
        setUploadStatus({
          type: 'error',
          message: result.error || 'Upload failed'
        });
      }
    } catch (error) {
      setUploadStatus({
        type: 'error',
        message: `Upload error: ${error.response?.data?.error || error.message}`
      });
    } finally {
      setUploading(false);
    }
  }, [projectId, workspaceId, onUploadComplete]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    disabled: uploading || !workspaceId
  });

  // Custom handlers for source file drops (from SourceFilesPanel)
  const handleSourceDragOver = (e) => {
    if (e.dataTransfer.types.includes('application/x-source-files')) {
      e.preventDefault();
      e.dataTransfer.dropEffect = 'copy';
      setIsSourceDragOver(true);
    }
  };

  const handleSourceDragLeave = (e) => {
    if (!e.currentTarget.contains(e.relatedTarget)) {
      setIsSourceDragOver(false);
    }
  };

  const handleSourceDrop = (e) => {
    const sourceData = e.dataTransfer.getData('application/x-source-files');
    if (sourceData) {
      e.preventDefault();
      e.stopPropagation();
      setIsSourceDragOver(false);
      try {
        const paths = JSON.parse(sourceData);
        if (paths.length > 0 && onImportSourceFiles) {
          onImportSourceFiles(paths);
        }
      } catch {
        // ignore parse errors
      }
    }
  };

  const getAnalysisTypeDisplay = () => {
    const types = {
      'database_schema': {
        title: 'Database Schema',
        description: 'Upload SQLAlchemy models or database files to visualize your schema',
        icon: '🗄️',
        acceptedFiles: '.py, .db, .sqlite, .sqlite3',
        analyzeLabel: 'Analyze Database Schema',
      },
      'runtime_flow': {
        title: 'Runtime Flow',
        description: 'Upload Python source files to visualize runtime execution flow',
        icon: '🔄',
        acceptedFiles: '.py',
        analyzeLabel: 'Analyze Runtime Flow',
      },
      'api_routes': {
        title: 'API Routes',
        description: 'Upload Python source files to visualize API endpoints and routes',
        icon: '🌐',
        acceptedFiles: '.py',
        analyzeLabel: 'Analyze API Routes',
      }
    };
    return types[analysisType] || types['database_schema'];
  };

  const display = getAnalysisTypeDisplay();

  return (
    <div
      className="center-upload-area"
      onDragOver={handleSourceDragOver}
      onDragLeave={handleSourceDragLeave}
      onDrop={handleSourceDrop}
    >
      <div className="flex flex-col items-center justify-center h-full gap-6 p-8">
        <div className="text-5xl">{display.icon}</div>
        <h2 className="text-xl font-semibold text-gray-900 dark:text-gray-100">
          {display.title}
        </h2>
        <p className="text-sm text-gray-500 dark:text-gray-400 text-center max-w-md">
          {display.description}
        </p>

        {/* Upload area */}
        <div
          {...getRootProps()}
          className={`upload-dropzone ${isDragActive ? 'drag-active' : ''} ${isSourceDragOver ? 'source-drag-active' : ''} ${uploading ? 'uploading' : ''}`}
        >
          <input {...getInputProps()} />

          {!uploading && !uploadStatus && !isSourceDragOver && (
            <>
              <div className="upload-prompt">
                {isDragActive ?
                  'Drop files here...' :
                  'Drag & drop files here, or click to select'
                }
              </div>
              <button type="button" className="browse-button">Browse Files</button>
              <p className="accepted-files">Accepted: {display.acceptedFiles}</p>
            </>
          )}

          {!uploading && !uploadStatus && isSourceDragOver && (
            <div className="upload-prompt source-drop-prompt">
              <svg className="w-8 h-8 mx-auto mb-2 text-emerald-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
              </svg>
              Drop to import from source repository
            </div>
          )}

          {uploading && (
            <div className="upload-progress">
              <div className="spinner"></div>
              <p>Uploading files...</p>
            </div>
          )}

          {uploadStatus && (
            <div className={`upload-status ${uploadStatus.type}`}>
              <p className="status-message">
                {uploadStatus.type === 'success' ? '✓' : '✗'} {uploadStatus.message}
              </p>
              {uploadStatus.details && (
                <ul className="upload-details">
                  {uploadStatus.details.map((item, idx) => (
                    <li key={idx} className={item.status}>
                      {item.filename} - {item.status}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default CenterUploadArea;
