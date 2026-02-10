import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { gitAPI } from '../../services/api';
import api from '../../services/api';
import { toast } from 'react-toastify';

function formatFileSize(bytes) {
  if (bytes === 0) return '0 B';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function buildFileTree(files) {
  const root = { name: '', children: {}, files: [] };

  for (const file of files) {
    const parts = file.path.split('/');
    let current = root;

    for (let i = 0; i < parts.length; i++) {
      const part = parts[i];
      if (i === parts.length - 1 && file.type === 'file') {
        current.files.push(file);
      } else {
        if (!current.children[part]) {
          current.children[part] = { name: part, children: {}, files: [] };
        }
        current = current.children[part];
      }
    }
  }

  return root;
}

function FileTreeNode({ node, name, depth, selectedFiles, onToggleFile, onToggleDir, expandedDirs, onToggleExpand }) {
  const dirFiles = useMemo(() => getAllFilesInDir(node), [node]);
  const isExpanded = expandedDirs.has(name);
  const allSelected = dirFiles.length > 0 && dirFiles.every(f => selectedFiles.has(f.path));
  const someSelected = dirFiles.some(f => selectedFiles.has(f.path));
  const childDirs = Object.entries(node.children);
  const childFiles = node.files;
  const fileCount = dirFiles.length;

  return (
    <div style={{ paddingLeft: depth > 0 ? 16 : 0 }}>
      {name && (
        <div
          className="flex items-center gap-2 py-1.5 px-2 rounded hover:bg-gray-50 dark:hover:bg-gray-700/50 cursor-pointer group"
          onClick={() => onToggleExpand(name)}
        >
          <svg
            className={`w-4 h-4 text-gray-400 transition-transform flex-shrink-0 ${isExpanded ? 'rotate-90' : ''}`}
            fill="currentColor" viewBox="0 0 20 20"
          >
            <path fillRule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clipRule="evenodd" />
          </svg>
          <input
            type="checkbox"
            checked={allSelected}
            ref={el => { if (el) el.indeterminate = someSelected && !allSelected; }}
            onChange={(e) => { e.stopPropagation(); onToggleDir(dirFiles); }}
            onClick={(e) => e.stopPropagation()}
            className="w-4 h-4 rounded border-gray-300 dark:border-gray-600 text-blue-600 focus:ring-blue-500"
          />
          <svg className="w-4 h-4 text-amber-500 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
            <path d="M2 6a2 2 0 012-2h5l2 2h5a2 2 0 012 2v6a2 2 0 01-2 2H4a2 2 0 01-2-2V6z" />
          </svg>
          <span className="text-sm text-gray-800 dark:text-gray-200 font-medium truncate">{node.name}</span>
          <span className="text-xs text-gray-400 dark:text-gray-500 ml-auto flex-shrink-0">
            {fileCount} file{fileCount !== 1 ? 's' : ''}
          </span>
        </div>
      )}

      {(isExpanded || !name) && (
        <div>
          {childDirs.map(([key, childNode]) => (
            <FileTreeNode
              key={key}
              node={childNode}
              name={key}
              depth={depth + 1}
              selectedFiles={selectedFiles}
              onToggleFile={onToggleFile}
              onToggleDir={onToggleDir}
              expandedDirs={expandedDirs}
              onToggleExpand={onToggleExpand}
            />
          ))}
          {childFiles.map((file) => (
            <div
              key={file.path}
              className="flex items-center gap-2 py-1.5 px-2 rounded hover:bg-gray-50 dark:hover:bg-gray-700/50 cursor-pointer"
              style={{ paddingLeft: (depth + 1) * 16 }}
              onClick={() => onToggleFile(file.path)}
            >
              <div className="w-4" />
              <input
                type="checkbox"
                checked={selectedFiles.has(file.path)}
                onChange={() => onToggleFile(file.path)}
                onClick={(e) => e.stopPropagation()}
                className="w-4 h-4 rounded border-gray-300 dark:border-gray-600 text-blue-600 focus:ring-blue-500"
              />
              <svg className="w-4 h-4 text-gray-400 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M4 4a2 2 0 012-2h4.586A2 2 0 0112 2.586L15.414 6A2 2 0 0116 7.414V16a2 2 0 01-2 2H6a2 2 0 01-2-2V4z" clipRule="evenodd" />
              </svg>
              <span className="text-sm text-gray-700 dark:text-gray-300 truncate">{file.path.split('/').pop()}</span>
              <span className="text-xs text-gray-400 dark:text-gray-500 ml-auto flex-shrink-0">
                {formatFileSize(file.size)}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function getAllFilesInDir(node) {
  const files = [...node.files];
  for (const child of Object.values(node.children)) {
    files.push(...getAllFilesInDir(child));
  }
  return files;
}

export default function GitImportModal({ isOpen, onClose, onImportComplete }) {
  const [url, setUrl] = useState('');
  const [repoData, setRepoData] = useState(null);
  const [loadingTree, setLoadingTree] = useState(false);
  const [importing, setImporting] = useState(false);
  const [selectedFiles, setSelectedFiles] = useState(new Set());
  const [expandedDirs, setExpandedDirs] = useState(new Set());
  const [projectName, setProjectName] = useState('');
  const [error, setError] = useState('');

  // Reset state when modal opens/closes
  useEffect(() => {
    if (!isOpen) {
      setUrl('');
      setRepoData(null);
      setSelectedFiles(new Set());
      setExpandedDirs(new Set());
      setProjectName('');
      setError('');
      setLoadingTree(false);
      setImporting(false);
    }
  }, [isOpen]);

  // Close on Escape key
  useEffect(() => {
    const handleEsc = (e) => {
      if (e.key === 'Escape' && !importing) onClose();
    };
    if (isOpen) {
      window.addEventListener('keydown', handleEsc);
      document.body.style.overflow = 'hidden';
    }
    return () => {
      window.removeEventListener('keydown', handleEsc);
      document.body.style.overflow = 'unset';
    };
  }, [isOpen, onClose, importing]);

  const handleLoadTree = async () => {
    if (!url.trim()) {
      setError('Please enter a GitHub repository URL');
      return;
    }

    setError('');
    setLoadingTree(true);
    setRepoData(null);
    setSelectedFiles(new Set());

    try {
      const response = await gitAPI.getTree(url.trim());
      const data = response.data;
      setRepoData(data);

      // Auto-set project name from repo name
      if (!projectName) {
        setProjectName(data.repo);
      }

      // Auto-expand first level
      const tree = buildFileTree(data.files);
      const firstLevelDirs = Object.keys(tree.children);
      setExpandedDirs(new Set(firstLevelDirs));

    } catch (err) {
      setError(err.response?.data?.error || 'Failed to load repository. Check the URL and try again.');
    } finally {
      setLoadingTree(false);
    }
  };

  const handleToggleFile = useCallback((path) => {
    setSelectedFiles(prev => {
      const next = new Set(prev);
      if (next.has(path)) {
        next.delete(path);
      } else {
        next.add(path);
      }
      return next;
    });
  }, []);

  const handleToggleDir = useCallback((dirFiles) => {
    setSelectedFiles(prev => {
      const next = new Set(prev);
      const allSelected = dirFiles.every(f => next.has(f.path));
      if (allSelected) {
        dirFiles.forEach(f => next.delete(f.path));
      } else {
        dirFiles.forEach(f => next.add(f.path));
      }
      return next;
    });
  }, []);

  const handleToggleExpand = useCallback((dirName) => {
    setExpandedDirs(prev => {
      const next = new Set(prev);
      if (next.has(dirName)) {
        next.delete(dirName);
      } else {
        next.add(dirName);
      }
      return next;
    });
  }, []);

  const handleSelectAllByExtension = useCallback((ext) => {
    if (!repoData) return;
    const matching = repoData.files.filter(f => f.type === 'file' && f.path.endsWith(ext));
    setSelectedFiles(prev => {
      const next = new Set(prev);
      const allSelected = matching.every(f => next.has(f.path));
      if (allSelected) {
        matching.forEach(f => next.delete(f.path));
      } else {
        matching.forEach(f => next.add(f.path));
      }
      return next;
    });
  }, [repoData]);

  const handleImport = async () => {
    if (!projectName.trim()) {
      toast.error('Project name is required');
      return;
    }

    if (selectedFiles.size === 0) {
      toast.error('Select at least one file to import');
      return;
    }

    if (selectedFiles.size > 50) {
      toast.error('Maximum 50 files can be imported at once');
      return;
    }

    setImporting(true);
    setError('');

    try {
      // Step 1: Create the project
      const createResponse = await api.post('/projects', {
        name: projectName.trim(),
        description: `Imported from ${repoData.owner}/${repoData.repo}`,
      });
      const project = createResponse.data.project;

      // Step 2: Import files from GitHub
      const importResponse = await gitAPI.importFiles(
        project.id,
        url.trim(),
        Array.from(selectedFiles),
        repoData.branch
      );

      const result = importResponse.data;

      if (result.downloaded > 0) {
        toast.success(
          `Imported ${result.downloaded} file${result.downloaded !== 1 ? 's' : ''} from GitHub`
        );
        if (result.failed > 0) {
          toast.warn(`${result.failed} file${result.failed !== 1 ? 's' : ''} failed to download`);
        }
        onImportComplete(project);
      } else {
        toast.error('No files could be downloaded');
      }

    } catch (err) {
      setError(err.response?.data?.error || 'Import failed. Please try again.');
      toast.error(err.response?.data?.error || 'Import failed');
    } finally {
      setImporting(false);
    }
  };

  const selectedSize = useMemo(() => {
    if (!repoData) return 0;
    return repoData.files
      .filter(f => selectedFiles.has(f.path))
      .reduce((sum, f) => sum + f.size, 0);
  }, [repoData, selectedFiles]);

  const fileTree = useMemo(() => {
    if (!repoData) return null;
    return buildFileTree(repoData.files);
  }, [repoData]);

  // Detect common extensions for quick-select buttons
  const extensionCounts = useMemo(() => {
    if (!repoData) return {};
    const counts = {};
    for (const file of repoData.files) {
      if (file.type !== 'file') continue;
      const ext = '.' + file.path.split('.').pop();
      if (['.py', '.js', '.jsx', '.ts', '.tsx', '.java', '.go', '.rs', '.rb'].includes(ext)) {
        counts[ext] = (counts[ext] || 0) + 1;
      }
    }
    return counts;
  }, [repoData]);

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50"
      onClick={(e) => { if (e.target === e.currentTarget && !importing) onClose(); }}
    >
      <div className="bg-white dark:bg-gray-800 rounded-xl shadow-2xl w-full max-w-2xl max-h-[85vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-700">
          <div className="flex items-center gap-3">
            <svg className="w-6 h-6 text-gray-700 dark:text-gray-300" fill="currentColor" viewBox="0 0 24 24">
              <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/>
            </svg>
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white">Import from GitHub</h3>
          </div>
          <button
            onClick={onClose}
            disabled={importing}
            className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 transition disabled:opacity-50"
          >
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
          {/* URL Input */}
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">
              Repository URL
            </label>
            <div className="flex gap-2">
              <input
                type="text"
                value={url}
                onChange={(e) => { setUrl(e.target.value); setError(''); }}
                onKeyDown={(e) => { if (e.key === 'Enter') handleLoadTree(); }}
                placeholder="https://github.com/user/repo"
                disabled={loadingTree || importing}
                className="flex-1 px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 text-sm"
              />
              <button
                onClick={handleLoadTree}
                disabled={loadingTree || importing || !url.trim()}
                className="px-4 py-2 bg-gray-800 dark:bg-gray-600 text-white rounded-md hover:bg-gray-700 dark:hover:bg-gray-500 transition text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed whitespace-nowrap"
              >
                {loadingTree ? (
                  <span className="flex items-center gap-2">
                    <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                    </svg>
                    Loading...
                  </span>
                ) : 'Load Files'}
              </button>
            </div>
          </div>

          {/* Error Display */}
          {error && (
            <div className="px-4 py-3 rounded-md bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800">
              <p className="text-sm text-red-700 dark:text-red-400">{error}</p>
            </div>
          )}

          {/* Repo Info Bar */}
          {repoData && (
            <div className="flex items-center gap-2 px-3 py-2 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-md">
              <svg className="w-4 h-4 text-green-600 dark:text-green-400 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
              </svg>
              <span className="text-sm text-green-800 dark:text-green-300 font-medium">
                {repoData.owner}/{repoData.repo}
              </span>
              <span className="text-xs text-green-600 dark:text-green-400 bg-green-100 dark:bg-green-900/40 px-2 py-0.5 rounded">
                {repoData.branch}
              </span>
              <span className="text-xs text-green-600 dark:text-green-400 ml-auto">
                {repoData.files.filter(f => f.type === 'file').length} files
              </span>
            </div>
          )}

          {/* Project Name */}
          {repoData && (
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">
                Project Name *
              </label>
              <input
                type="text"
                value={projectName}
                onChange={(e) => setProjectName(e.target.value)}
                disabled={importing}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 text-sm"
                placeholder="Project name"
              />
            </div>
          )}

          {/* Quick Select Buttons */}
          {repoData && Object.keys(extensionCounts).length > 0 && (
            <div className="flex flex-wrap gap-2">
              <span className="text-xs text-gray-500 dark:text-gray-400 self-center">Quick select:</span>
              {Object.entries(extensionCounts).sort((a, b) => b[1] - a[1]).map(([ext, count]) => (
                <button
                  key={ext}
                  onClick={() => handleSelectAllByExtension(ext)}
                  className="px-2.5 py-1 text-xs rounded-md border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 transition"
                >
                  All {ext} ({count})
                </button>
              ))}
            </div>
          )}

          {/* File Tree */}
          {repoData && fileTree && (
            <div className="border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden">
              <div className="px-3 py-2 bg-gray-50 dark:bg-gray-750 dark:bg-gray-900/50 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
                <span className="text-xs font-medium text-gray-600 dark:text-gray-400">Select files to import</span>
                <button
                  onClick={() => {
                    const allFiles = repoData.files.filter(f => f.type === 'file');
                    const allSelected = allFiles.every(f => selectedFiles.has(f.path));
                    if (allSelected) {
                      setSelectedFiles(new Set());
                    } else {
                      setSelectedFiles(new Set(allFiles.map(f => f.path)));
                    }
                  }}
                  className="text-xs text-blue-600 dark:text-blue-400 hover:underline"
                >
                  {repoData.files.filter(f => f.type === 'file').every(f => selectedFiles.has(f.path))
                    ? 'Deselect All'
                    : 'Select All'}
                </button>
              </div>
              <div className="max-h-72 overflow-y-auto p-2">
                <FileTreeNode
                  node={fileTree}
                  name=""
                  depth={0}
                  selectedFiles={selectedFiles}
                  onToggleFile={handleToggleFile}
                  onToggleDir={handleToggleDir}
                  expandedDirs={expandedDirs}
                  onToggleExpand={handleToggleExpand}
                />
              </div>
            </div>
          )}

          {repoData && repoData.truncated && (
            <div className="px-3 py-2 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-md">
              <p className="text-xs text-amber-700 dark:text-amber-400">
                This repository has too many files to display completely. Some files may not be shown.
              </p>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-gray-200 dark:border-gray-700 flex items-center justify-between">
          <div className="text-sm text-gray-500 dark:text-gray-400">
            {selectedFiles.size > 0 ? (
              <span>
                {selectedFiles.size} file{selectedFiles.size !== 1 ? 's' : ''} selected ({formatFileSize(selectedSize)})
              </span>
            ) : repoData ? (
              <span>No files selected</span>
            ) : null}
          </div>
          <div className="flex gap-3">
            <button
              onClick={onClose}
              disabled={importing}
              className="px-4 py-2 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-md transition text-sm disabled:opacity-50"
            >
              Cancel
            </button>
            {repoData && (
              <button
                onClick={handleImport}
                disabled={importing || selectedFiles.size === 0 || !projectName.trim()}
                className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
              >
                {importing ? (
                  <>
                    <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                    </svg>
                    Importing...
                  </>
                ) : (
                  `Import & Analyze`
                )}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
