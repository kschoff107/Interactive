import React, { useState, useRef, useEffect, useCallback } from 'react';
import SourceFilesPanel from './SourceFilesPanel';
import ResizeHandle from './ResizeHandle';

const navigationItems = [
  {
    id: 'schema',
    analysisType: 'database_schema',
    name: 'Database Schema',
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5c0 2.21-3.582 4-8 4s-8-1.79-8-4" />
      </svg>
    ),
    disabled: false,
  },
  {
    id: 'flow',
    analysisType: 'runtime_flow',
    name: 'Runtime Flow',
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
      </svg>
    ),
    disabled: false,
  },
  {
    id: 'api',
    analysisType: 'api_routes',
    name: 'API Routes',
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9" />
      </svg>
    ),
    disabled: false,
  },
  {
    id: 'structure',
    analysisType: 'code_structure',
    name: 'Code Structure',
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
      </svg>
    ),
    disabled: false,
  },
];

function WorkspaceItem({ workspace, isActive, onSelect, onRename, onDelete, onDuplicate, onClearData }) {
  const [isEditing, setIsEditing] = useState(false);
  const [editName, setEditName] = useState(workspace.name);
  const [showDots, setShowDots] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const inputRef = useRef(null);
  const menuRef = useRef(null);
  const dotsRef = useRef(null);

  useEffect(() => {
    if (isEditing && inputRef.current) {
      inputRef.current.focus();
      inputRef.current.select();
    }
  }, [isEditing]);

  // Close menu on click outside
  useEffect(() => {
    if (!menuOpen) return;
    const handleClickOutside = (e) => {
      if (menuRef.current && !menuRef.current.contains(e.target) &&
          dotsRef.current && !dotsRef.current.contains(e.target)) {
        setMenuOpen(false);
      }
    };
    const handleEscape = (e) => {
      if (e.key === 'Escape') setMenuOpen(false);
    };
    document.addEventListener('mousedown', handleClickOutside);
    document.addEventListener('keydown', handleEscape);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('keydown', handleEscape);
    };
  }, [menuOpen]);

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') {
      confirmRename();
    } else if (e.key === 'Escape') {
      setIsEditing(false);
      setEditName(workspace.name);
    }
  };

  const confirmRename = () => {
    const trimmed = editName.trim();
    if (trimmed && trimmed !== workspace.name) {
      onRename(trimmed);
    }
    setIsEditing(false);
  };

  const menuActions = [
    {
      label: 'Rename',
      icon: (
        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
        </svg>
      ),
      onClick: () => {
        setMenuOpen(false);
        setEditName(workspace.name);
        setIsEditing(true);
      },
    },
    {
      label: 'Duplicate',
      icon: (
        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
        </svg>
      ),
      onClick: () => {
        setMenuOpen(false);
        onDuplicate && onDuplicate();
      },
    },
    {
      label: 'Clear Data',
      icon: (
        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
        </svg>
      ),
      onClick: () => {
        setMenuOpen(false);
        onClearData && onClearData();
      },
    },
    {
      label: 'Delete',
      icon: (
        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
        </svg>
      ),
      danger: true,
      onClick: () => {
        setMenuOpen(false);
        setShowDeleteConfirm(true);
      },
    },
  ];

  return (
    <>
      <div
        className="group relative"
        onMouseEnter={() => setShowDots(true)}
        onMouseLeave={() => { if (!menuOpen) setShowDots(false); }}
      >
        <button
          onClick={onSelect}
          className={`
            w-full flex items-center gap-2 pl-10 pr-2 py-1.5 text-xs rounded-md
            transition-all duration-150 relative
            ${isActive
              ? 'bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300'
              : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700/50 hover:text-gray-800 dark:hover:text-gray-200'
            }
          `}
        >
          {isActive && (
            <div className="absolute left-0 top-0 bottom-0 w-0.5 bg-blue-600 rounded-r" />
          )}

          {/* Workspace icon */}
          <svg className="w-3.5 h-3.5 flex-shrink-0 opacity-60" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>

          {isEditing ? (
            <input
              ref={inputRef}
              value={editName}
              onChange={(e) => setEditName(e.target.value)}
              onBlur={confirmRename}
              onKeyDown={handleKeyDown}
              onClick={(e) => e.stopPropagation()}
              className="flex-1 bg-white dark:bg-gray-700 border border-blue-400 rounded px-1 py-0 text-xs outline-none min-w-0"
            />
          ) : (
            <span className="flex-1 text-left truncate">{workspace.name}</span>
          )}

          {/* Three-dot menu button */}
          {(showDots || menuOpen) && !isEditing && (
            <span
              ref={dotsRef}
              onClick={(e) => {
                e.stopPropagation();
                setMenuOpen(!menuOpen);
              }}
              className="flex-shrink-0 p-0.5 rounded hover:bg-gray-200 dark:hover:bg-gray-600 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors cursor-pointer"
              title="Workspace options"
            >
              <svg className="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 20 20">
                <path d="M10 6a2 2 0 110-4 2 2 0 010 4zM10 12a2 2 0 110-4 2 2 0 010 4zM10 18a2 2 0 110-4 2 2 0 010 4z" />
              </svg>
            </span>
          )}
        </button>

        {/* Dropdown menu */}
        {menuOpen && (
          <div
            ref={menuRef}
            className="absolute right-0 top-full mt-1 z-50 w-40 bg-white dark:bg-gray-800 rounded-lg shadow-lg border border-gray-200 dark:border-gray-600 py-1 text-xs"
          >
            {menuActions.map((action) => (
              <button
                key={action.label}
                onClick={(e) => {
                  e.stopPropagation();
                  action.onClick();
                }}
                className={`w-full flex items-center gap-2 px-3 py-1.5 text-left transition-colors ${
                  action.danger
                    ? 'text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20'
                    : 'text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700'
                }`}
              >
                {action.icon}
                {action.label}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Delete confirmation modal */}
      {showDeleteConfirm && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/50">
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl p-6 max-w-sm mx-4 border border-gray-200 dark:border-gray-700">
            <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-2">
              Delete "{workspace.name}"?
            </h3>
            <p className="text-xs text-gray-500 dark:text-gray-400 mb-4">
              This will permanently remove all files and analysis data in this workspace. This action cannot be undone.
            </p>
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setShowDeleteConfirm(false)}
                className="px-3 py-1.5 text-xs rounded-md bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={() => {
                  setShowDeleteConfirm(false);
                  onDelete();
                }}
                className="px-3 py-1.5 text-xs rounded-md bg-red-600 text-white hover:bg-red-700 transition-colors"
              >
                Delete
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

export default function Sidebar({
  width = 220,
  activeView,
  onViewChange,
  project,
  workspaces = {},
  activeWorkspaceId,
  onWorkspaceSelect,
  onWorkspaceCreate,
  onWorkspaceRename,
  onWorkspaceDelete,
  onWorkspaceDuplicate,
  onWorkspaceClearData,
  onImportSourceFiles,
}) {
  // Auto-expand sections that contain the active workspace or have workspaces
  const [expanded, setExpanded] = useState(() => {
    const initial = {};
    navigationItems.forEach(item => {
      if (!item.disabled) initial[item.id] = true;
    });
    return initial;
  });

  const isGitProject = project && project.source_type === 'git';

  // Vertical split: fraction of flexible area given to nav (rest goes to source panel)
  const [verticalSplit, setVerticalSplit] = useState(() => {
    const saved = localStorage.getItem('sidebarVerticalSplit');
    return saved ? parseFloat(saved) : 0.6;
  });

  const contentRef = useRef(null);

  useEffect(() => {
    localStorage.setItem('sidebarVerticalSplit', verticalSplit.toString());
  }, [verticalSplit]);

  const handleVerticalResize = useCallback((deltaY) => {
    if (!contentRef.current) return;
    const h = contentRef.current.clientHeight;
    if (h === 0) return;
    setVerticalSplit(prev => Math.max(0.2, Math.min(0.8, prev + deltaY / h)));
  }, []);

  const toggleExpand = (itemId) => {
    setExpanded(prev => ({ ...prev, [itemId]: !prev[itemId] }));
  };

  return (
    <div
      style={{ width }}
      className="bg-white dark:bg-gray-800 border-r border-gray-200 dark:border-gray-700 flex flex-col flex-shrink-0"
    >
      {/* Sidebar Header */}
      <div className="px-4 py-6 border-b border-gray-200 dark:border-gray-700">
        <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-300 uppercase tracking-wider">
          Visualizations
        </h2>
      </div>

      {/* Flexible content area */}
      <div ref={contentRef} className="flex-1 flex flex-col overflow-hidden min-h-0">
        {/* Navigation Items */}
        <nav
          className="px-2 py-4 space-y-0.5 overflow-y-auto sidebar-scroll"
          style={isGitProject ? { flex: `0 0 ${verticalSplit * 100}%` } : { flex: 1 }}
        >
          {navigationItems.map((item) => {
            const isDisabled = item.disabled;
            const itemWorkspaces = workspaces[item.analysisType] || [];
            const isExpanded = expanded[item.id];
            const hasActiveChild = itemWorkspaces.some(ws => ws.id === activeWorkspaceId);

            return (
              <div key={item.id}>
                {/* Type header */}
                <div className="flex items-center">
                  <button
                    onClick={() => {
                      if (isDisabled) return;
                      toggleExpand(item.id);
                      // If clicking a type that has workspaces, also select the first one
                      if (itemWorkspaces.length > 0 && !hasActiveChild && onWorkspaceSelect) {
                        onWorkspaceSelect(item.id, itemWorkspaces[0].id);
                      } else if (itemWorkspaces.length === 0) {
                        onViewChange(item.id);
                      }
                    }}
                    disabled={isDisabled}
                    className={`
                      flex-1 flex items-center gap-3 px-4 py-2.5 rounded-lg text-sm font-medium
                      transition-all duration-200 relative
                      ${hasActiveChild
                        ? 'text-blue-700 dark:text-blue-300'
                        : isDisabled
                        ? 'text-gray-400 dark:text-gray-600 cursor-not-allowed opacity-50'
                        : 'text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700/50'
                      }
                    `}
                  >
                    {/* Icon */}
                    <span className={hasActiveChild ? 'text-blue-600 dark:text-blue-400' : ''}>
                      {item.icon}
                    </span>

                    {/* Label */}
                    <span className="flex-1 text-left">{item.name}</span>

                    {/* Coming Soon badge */}
                    {isDisabled && (
                      <span className="text-xs px-2 py-0.5 bg-gray-200 dark:bg-gray-700 text-gray-500 dark:text-gray-400 rounded">
                        Soon
                      </span>
                    )}

                    {/* Chevron for expandable items */}
                    {!isDisabled && (
                      <svg
                        className={`w-3.5 h-3.5 transition-transform duration-200 text-gray-400 ${isExpanded ? 'rotate-90' : ''}`}
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5l7 7-7 7" />
                      </svg>
                    )}
                  </button>

                  {/* Add workspace button */}
                  {!isDisabled && onWorkspaceCreate && (
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onWorkspaceCreate(item.analysisType);
                        if (!isExpanded) {
                          setExpanded(prev => ({ ...prev, [item.id]: true }));
                        }
                      }}
                      className="p-1.5 mr-1 rounded hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors"
                      title={`Add ${item.name} workspace`}
                    >
                      <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4v16m8-8H4" />
                      </svg>
                    </button>
                  )}
                </div>

                {/* Workspace sub-items */}
                {!isDisabled && isExpanded && itemWorkspaces.length > 0 && (
                  <div className="mt-0.5 mb-1 space-y-0.5">
                    {itemWorkspaces.map(ws => (
                      <WorkspaceItem
                        key={ws.id}
                        workspace={ws}
                        isActive={activeWorkspaceId === ws.id}
                        onSelect={() => onWorkspaceSelect && onWorkspaceSelect(item.id, ws.id)}
                        onRename={(newName) => onWorkspaceRename && onWorkspaceRename(ws.id, newName)}
                        onDelete={() => onWorkspaceDelete && onWorkspaceDelete(ws.id)}
                        onDuplicate={() => onWorkspaceDuplicate && onWorkspaceDuplicate(ws.id, item.analysisType)}
                        onClearData={() => onWorkspaceClearData && onWorkspaceClearData(ws.id)}
                      />
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </nav>

        {/* Vertical resize handle + Source Files Panel (git projects only) */}
        {isGitProject && (
          <>
            <ResizeHandle direction="vertical" onResize={handleVerticalResize} />
            <div
              style={{ flex: `0 0 ${(1 - verticalSplit) * 100}%` }}
              className="overflow-hidden min-h-0"
            >
              <SourceFilesPanel project={project} onImportFiles={onImportSourceFiles} />
            </div>
          </>
        )}
      </div>

      {/* Sidebar Footer */}
      <div className="px-4 py-3 border-t border-gray-200 dark:border-gray-700">
        <p className="text-xs text-gray-500 dark:text-gray-400">
          Click + to add workspaces
        </p>
      </div>
    </div>
  );
}
