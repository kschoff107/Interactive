import React, { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import { gitAPI } from '../../services/api';

function formatFileSize(bytes) {
  if (bytes === 0) return '0 B';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function parseRepoInfo(gitUrl) {
  if (!gitUrl) return null;
  try {
    const url = new URL(gitUrl);
    const parts = url.pathname.split('/').filter(Boolean);
    if (parts.length >= 2) {
      const repo = parts[1].replace(/\.git$/, '');
      return { owner: parts[0], repo, display: `${parts[0]}/${repo}`, url: gitUrl };
    }
  } catch {
    // ignore
  }
  return null;
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

function getAllFilesInNode(node) {
  const files = [...node.files];
  for (const child of Object.values(node.children)) {
    files.push(...getAllFilesInNode(child));
  }
  return files;
}

function TreeNode({ node, name, depth, onImportFiles }) {
  const [expanded, setExpanded] = useState(depth < 1);
  const childDirs = Object.entries(node.children);
  const childFiles = node.files;
  const hasChildren = childDirs.length > 0 || childFiles.length > 0;

  const handleFolderDragStart = (e) => {
    e.stopPropagation();
    const allFiles = getAllFilesInNode(node);
    const paths = allFiles.map(f => f.path);
    e.dataTransfer.setData('application/x-source-files', JSON.stringify(paths));
    e.dataTransfer.effectAllowed = 'copy';
  };

  const handleFolderImport = (e) => {
    e.stopPropagation();
    if (!onImportFiles) return;
    const allFiles = getAllFilesInNode(node);
    onImportFiles(allFiles.map(f => f.path));
  };

  return (
    <div style={{ paddingLeft: depth > 0 ? 12 : 0 }}>
      {name && (
        <div
          draggable
          onDragStart={handleFolderDragStart}
          className="group"
        >
          <button
            onClick={() => setExpanded(!expanded)}
            className="flex items-center gap-1.5 w-full py-0.5 px-1 rounded text-left hover:bg-gray-100 dark:hover:bg-gray-700/50"
          >
            {hasChildren ? (
              <svg
                className={`w-3 h-3 text-gray-400 transition-transform flex-shrink-0 ${expanded ? 'rotate-90' : ''}`}
                fill="currentColor" viewBox="0 0 20 20"
              >
                <path fillRule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clipRule="evenodd" />
              </svg>
            ) : (
              <span className="w-3" />
            )}
            <svg className="w-3.5 h-3.5 text-amber-500 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
              <path d="M2 6a2 2 0 012-2h5l2 2h5a2 2 0 012 2v6a2 2 0 01-2 2H4a2 2 0 01-2-2V6z" />
            </svg>
            <span className="text-xs text-gray-700 dark:text-gray-300 truncate flex-1">{node.name}</span>
            {onImportFiles && (
              <span
                onClick={handleFolderImport}
                className="opacity-0 group-hover:opacity-100 p-0.5 rounded hover:bg-blue-100 dark:hover:bg-blue-900/30 text-blue-500 transition-opacity cursor-pointer flex-shrink-0"
                title="Import folder to workspace"
              >
                <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                </svg>
              </span>
            )}
          </button>
        </div>
      )}

      {(expanded || !name) && (
        <div>
          {childDirs
            .sort(([a], [b]) => a.localeCompare(b))
            .map(([key, childNode]) => (
              <TreeNode key={key} node={childNode} name={key} depth={depth + 1} onImportFiles={onImportFiles} />
            ))}
          {childFiles
            .sort((a, b) => a.path.localeCompare(b.path))
            .map((file) => {
              const fileName = file.path.split('/').pop();
              return (
                <div
                  key={file.path}
                  draggable
                  onDragStart={(e) => {
                    e.dataTransfer.setData('application/x-source-files', JSON.stringify([file.path]));
                    e.dataTransfer.effectAllowed = 'copy';
                  }}
                  className="group flex items-center gap-1.5 py-0.5 px-1 rounded text-xs text-gray-600 dark:text-gray-400 cursor-grab active:cursor-grabbing hover:bg-gray-50 dark:hover:bg-gray-700/30"
                  style={{ paddingLeft: (depth + 1) * 12 }}
                >
                  <span className="w-3" />
                  <svg className="w-3.5 h-3.5 text-gray-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                  <span className="truncate flex-1">{fileName}</span>
                  {onImportFiles && (
                    <span
                      onClick={(e) => {
                        e.stopPropagation();
                        onImportFiles([file.path]);
                      }}
                      className="opacity-0 group-hover:opacity-100 p-0.5 rounded hover:bg-blue-100 dark:hover:bg-blue-900/30 text-blue-500 transition-opacity cursor-pointer flex-shrink-0"
                      title="Import to workspace"
                    >
                      <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                      </svg>
                    </span>
                  )}
                  <span className="ml-auto flex-shrink-0 text-gray-400 dark:text-gray-500">
                    {formatFileSize(file.size)}
                  </span>
                </div>
              );
            })}
        </div>
      )}
    </div>
  );
}

export default function SourceFilesPanel({ project, onImportFiles }) {
  const [collapsed, setCollapsed] = useState(false);
  const [files, setFiles] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const abortRef = useRef(null);

  const isGitProject = project && project.source_type === 'git';
  const projectId = project?.id;
  const repoInfo = useMemo(() => isGitProject ? parseRepoInfo(project.git_url) : null, [isGitProject, project?.git_url]);

  const fetchTree = useCallback(() => {
    if (!isGitProject || !project.git_url) return;
    // Abort any in-flight request before starting a new one
    if (abortRef.current) abortRef.current.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setLoading(true);
    setError(null);
    gitAPI
      .getTree(project.git_url, { signal: controller.signal })
      .then((res) => {
        if (!controller.signal.aborted) {
          const fileEntries = (res.data.files || []).filter(f => f.type === 'file');
          setFiles(fileEntries);
        }
      })
      .catch((err) => {
        if (controller.signal.aborted) return;
        const msg = err.response?.data?.error || 'Failed to load source files';
        console.error('Source file tree fetch failed:', err);
        setError(msg);
        setFiles([]);
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      });
  }, [isGitProject, project?.git_url]);

  useEffect(() => {
    fetchTree();
    return () => {
      if (abortRef.current) abortRef.current.abort();
    };
  }, [fetchTree]);

  const tree = useMemo(() => buildFileTree(files), [files]);

  // Only render for git-imported projects
  if (!isGitProject) return null;

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Header */}
      <button
        onClick={() => setCollapsed(!collapsed)}
        className="w-full flex items-center gap-2 px-4 py-3 text-left hover:bg-gray-50 dark:hover:bg-gray-700/30 flex-shrink-0"
      >
        <svg
          className={`w-3 h-3 text-gray-400 transition-transform flex-shrink-0 ${collapsed ? '' : 'rotate-90'}`}
          fill="currentColor" viewBox="0 0 20 20"
        >
          <path fillRule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clipRule="evenodd" />
        </svg>
        {/* GitHub icon */}
        <svg className="w-4 h-4 text-gray-500 dark:text-gray-400 flex-shrink-0" fill="currentColor" viewBox="0 0 24 24">
          <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z" />
        </svg>
        <span className="text-xs font-semibold text-gray-600 dark:text-gray-300 uppercase tracking-wider">
          Source
        </span>
      </button>

      {!collapsed && (
        <div className="flex-1 overflow-y-auto px-3 pb-3 min-h-0 sidebar-scroll">
          {/* Repo link */}
          {repoInfo && (
            <a
              href={repoInfo.url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1.5 px-1 py-1 rounded text-xs text-blue-600 dark:text-blue-400 hover:underline truncate"
              title={repoInfo.url}
            >
              <span className="truncate">{repoInfo.display}</span>
              <svg className="w-3 h-3 flex-shrink-0 opacity-60" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
              </svg>
            </a>
          )}

          {/* Branch badge + refresh */}
          {project.git_branch && (
            <div className="flex items-center gap-1.5 px-1 py-1">
              <svg className="w-3 h-3 text-gray-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
              </svg>
              <span className="text-xs px-1.5 py-0.5 bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 rounded font-mono">
                {project.git_branch}
              </span>
              <button
                onClick={fetchTree}
                disabled={loading}
                className="ml-auto p-0.5 rounded hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors disabled:opacity-50"
                title="Refresh source files"
              >
                <svg className={`w-3 h-3 ${loading ? 'animate-spin' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
              </button>
            </div>
          )}

          {/* Drag hint */}
          {onImportFiles && files.length > 0 && !loading && (
            <p className="text-xs text-gray-400 dark:text-gray-500 px-1 py-1 italic">
              Drag files to workspace or click the arrow icon
            </p>
          )}

          {/* File tree */}
          <div className="mt-2">
            {loading ? (
              <div className="flex items-center justify-center py-4">
                <svg className="animate-spin h-4 w-4 text-gray-400" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
              </div>
            ) : error ? (
              <div className="px-1 py-2">
                <p className="text-xs text-red-500 dark:text-red-400">{error}</p>
                <button
                  onClick={fetchTree}
                  className="text-xs text-blue-500 hover:text-blue-600 dark:text-blue-400 dark:hover:text-blue-300 mt-1 underline"
                >
                  Retry
                </button>
              </div>
            ) : files.length > 0 ? (
              <TreeNode node={tree} name="" depth={0} onImportFiles={onImportFiles} />
            ) : (
              <p className="text-xs text-gray-400 dark:text-gray-500 px-1 py-2">No files found</p>
            )}
          </div>

          {/* File count footer */}
          {files.length > 0 && !loading && (
            <div className="mt-2 px-1 text-xs text-gray-400 dark:text-gray-500">
              {files.length} file{files.length !== 1 ? 's' : ''} in repo
            </div>
          )}
        </div>
      )}
    </div>
  );
}
