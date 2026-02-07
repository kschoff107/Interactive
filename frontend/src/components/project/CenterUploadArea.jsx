import React, { useState, useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import api from '../../services/api';
import './CenterUploadArea.css';

const CenterUploadArea = ({ projectId, analysisType, onUploadComplete }) => {
  const [uploading, setUploading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState(null);

  const onDrop = useCallback(async (acceptedFiles) => {
    if (acceptedFiles.length === 0) return;

    setUploading(true);
    setUploadStatus(null);

    const formData = new FormData();
    acceptedFiles.forEach(file => {
      formData.append('files', file);
    });
    formData.append('file_type', analysisType);

    try {
      const response = await api.post(`/projects/${projectId}/upload`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });

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
  }, [projectId, analysisType, onUploadComplete]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    disabled: uploading
  });

  const getAnalysisTypeDisplay = () => {
    const types = {
      'database_schema': {
        title: 'Upload Database Schema Files',
        description: 'Upload SQLAlchemy models (.py) or SQLite database (.db, .sqlite) files',
        icon: '🗄️',
        acceptedFiles: '.py, .db, .sqlite, .sqlite3'
      },
      'runtime_flow': {
        title: 'Upload Runtime Flow Files',
        description: 'Upload Python source files (.py) to analyze runtime execution flow',
        icon: '🔄',
        acceptedFiles: '.py'
      }
    };
    return types[analysisType] || types['database_schema'];
  };

  const display = getAnalysisTypeDisplay();

  return (
    <div className="center-upload-area">
      <div
        {...getRootProps()}
        className={`upload-dropzone ${isDragActive ? 'drag-active' : ''} ${uploading ? 'uploading' : ''}`}
      >
        <input {...getInputProps()} />

        <div className="upload-icon">{display.icon}</div>
        <h2>{display.title}</h2>
        <p className="upload-description">{display.description}</p>

        {!uploading && !uploadStatus && (
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

        {uploading && (
          <div className="upload-progress">
            <div className="spinner"></div>
            <p>Uploading and analyzing files...</p>
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
                    {item.reason && ` (${item.reason})`}
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default CenterUploadArea;
