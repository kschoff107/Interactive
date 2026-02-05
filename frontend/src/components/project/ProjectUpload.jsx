import React, { useState, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useDropzone } from 'react-dropzone';
import api from '../../services/api';
import { toast } from 'react-toastify';

export default function ProjectUpload() {
  const { projectId } = useParams();
  const navigate = useNavigate();
  const [uploading, setUploading] = useState(false);
  const [files, setFiles] = useState([]);

  const onDrop = useCallback((acceptedFiles, rejectedFiles) => {
    if (rejectedFiles.length > 0) {
      toast.error(`${rejectedFiles.length} file(s) rejected. Please upload code files.`);
    }
    if (acceptedFiles.length > 0) {
      setFiles(prevFiles => [...prevFiles, ...acceptedFiles]);
      toast.success(`${acceptedFiles.length} file(s) added`);
    }
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'text/plain': ['.py', '.js', '.jsx', '.ts', '.tsx', '.java', '.go', '.rb', '.php', '.cs', '.cpp', '.c', '.h', '.hpp', '.sql'],
      'text/x-python': ['.py'],
      'application/x-python': ['.py'],
      'application/javascript': ['.js', '.jsx'],
      'application/typescript': ['.ts', '.tsx'],
      'text/x-java-source': ['.java'],
      'text/x-go': ['.go'],
      'text/x-ruby': ['.rb'],
      'text/x-php': ['.php'],
      'text/x-c': ['.c', '.h'],
      'text/x-c++': ['.cpp', '.hpp', '.cc', '.cxx'],
      'application/x-sqlite3': ['.db', '.sqlite', '.sqlite3'],
      'application/sql': ['.sql']
    },
    multiple: true
  });

  const handleUpload = async () => {
    if (files.length === 0) {
      toast.error('Please select files to upload');
      return;
    }

    setUploading(true);
    const formData = new FormData();
    files.forEach((file) => {
      formData.append('files', file);
    });

    try {
      const response = await api.post(`/projects/${projectId}/upload`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data'
        }
      });

      toast.success('Files uploaded and analyzed successfully!');
      navigate(`/project/${projectId}/visualize`);
    } catch (error) {
      toast.error(error.response?.data?.error || 'Upload failed');
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-3xl mx-auto px-4">
        <div className="mb-6">
          <button
            onClick={() => navigate('/dashboard')}
            className="text-blue-600 hover:text-blue-700 text-sm"
          >
            ← Back to Dashboard
          </button>
        </div>

        <div className="bg-white rounded-lg shadow p-8">
          <h2 className="text-2xl font-bold text-gray-900 mb-2">Upload Project Files</h2>
          <p className="text-gray-600 mb-6">
            Upload your code files to analyze database schemas and relationships
          </p>

          {/* Dropzone */}
          <div
            {...getRootProps()}
            className={`border-2 border-dashed rounded-lg p-12 text-center cursor-pointer transition ${
              isDragActive
                ? 'border-blue-500 bg-blue-50'
                : 'border-gray-300 hover:border-gray-400'
            }`}
          >
            <input {...getInputProps()} />
            <svg
              className="mx-auto h-12 w-12 text-gray-400 mb-4"
              stroke="currentColor"
              fill="none"
              viewBox="0 0 48 48"
            >
              <path
                d="M28 8H12a4 4 0 00-4 4v20m32-12v8m0 0v8a4 4 0 01-4 4H12a4 4 0 01-4-4v-4m32-4l-3.172-3.172a4 4 0 00-5.656 0L28 28M8 32l9.172-9.172a4 4 0 015.656 0L28 28m0 0l4 4m4-24h8m-4-4v8m-12 4h.02"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
            {isDragActive ? (
              <p className="text-blue-600 font-medium">Drop the files here...</p>
            ) : (
              <div>
                <p className="text-gray-700 font-medium mb-1">
                  Drag & drop files here, or click to select
                </p>
                <p className="text-sm text-gray-500">
                  Supports: Python, JavaScript, TypeScript, Java, Go, Ruby, PHP, C/C++, SQL, SQLite (.db)
                </p>
              </div>
            )}
          </div>

          {/* Selected Files */}
          {files.length > 0 && (
            <div className="mt-6">
              <h3 className="text-sm font-medium text-gray-700 mb-3">
                Selected Files ({files.length})
              </h3>
              <div className="space-y-2 max-h-48 overflow-y-auto">
                {files.map((file, index) => (
                  <div
                    key={index}
                    className="flex items-center justify-between p-3 bg-gray-50 rounded"
                  >
                    <span className="text-sm text-gray-700">{file.name}</span>
                    <span className="text-xs text-gray-500">
                      {(file.size / 1024).toFixed(2)} KB
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Upload Button */}
          <div className="mt-6 flex gap-3">
            <button
              onClick={handleUpload}
              disabled={uploading || files.length === 0}
              className="flex-1 px-6 py-3 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition font-medium"
            >
              {uploading ? 'Analyzing...' : 'Upload & Analyze'}
            </button>
            {files.length > 0 && (
              <button
                onClick={() => setFiles([])}
                className="px-6 py-3 border border-gray-300 text-gray-700 rounded-md hover:bg-gray-50 transition"
              >
                Clear
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
