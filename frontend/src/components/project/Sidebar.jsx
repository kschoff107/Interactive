import React, { useState, useRef, useEffect } from 'react';
import SourceFilesPanel from './SourceFilesPanel';

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
    disabled: true,
  },
];

function WorkspaceItem({ workspace, isActive, onSelect, onRename, onDelete }) {
  const [isEditing, setIsEditing] = useState(false);
  const [editName, setEditName] = useState(workspace.name);
  const [showActions, setShowActions] = useState(false);
  const inputRef = useRef(null);

  useEffect(() => {
    if (isEditing && inputRef.current) {
      inputRef.current.focus();
      inputRef.current.select();
    }
  }, [isEditing]);

  const handleDoubleClick = (e) => {
    e.stopPropagation();
    setEditName(workspace.name);
    setIsEditing(true);
  };

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

  return (
    <div
      className="group relative"
      onMouseEnter={() => setShowActions(true)}
      onMouseLeave={() => setShowActions(false)}
    >
      <button
        onClick={onSelect}
        onDoubleClick={handleDoubleClick}
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

        {/* Delete button on hover */}
        {showActions && !isEditing && (
          <button
            onClick={(e) => {
              e.stopPropagation();
              onDelete();
            }}
            className="flex-shrink-0 p-0.5 rounded hover:bg-red-100 dark:hover:bg-red-900/30 text-gray-400 hover:text-red-500 dark:hover:text-red-400 transition-colors"
            title="Delete workspace"
          >
            <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        )}
      </button>
    </div>
  );
}

export default function Sidebar({
  activeView,
  onViewChange,
  project,
  workspaces = {},
  activeWorkspaceId,
  onWorkspaceSelect,
  onWorkspaceCreate,
  onWorkspaceRename,
  onWorkspaceDelete,
}) {
  // Auto-expand sections that contain the active workspace or have workspaces
  const [expanded, setExpanded] = useState(() => {
    const initial = {};
    navigationItems.forEach(item => {
      if (!item.disabled) initial[item.id] = true;
    });
    return initial;
  });

  const toggleExpand = (itemId) => {
    setExpanded(prev => ({ ...prev, [itemId]: !prev[itemId] }));
  };

  return (
    <div className="w-[220px] bg-white dark:bg-gray-800 border-r border-gray-200 dark:border-gray-700 flex flex-col">
      {/* Sidebar Header */}
      <div className="px-4 py-6 border-b border-gray-200 dark:border-gray-700">
        <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-300 uppercase tracking-wider">
          Visualizations
        </h2>
      </div>

      {/* Navigation Items */}
      <nav className="flex-1 px-2 py-4 space-y-0.5 overflow-y-auto">
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
                    />
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </nav>

      {/* Source Files Panel (git-imported projects only) */}
      <SourceFilesPanel project={project} />

      {/* Sidebar Footer */}
      <div className="px-4 py-3 border-t border-gray-200 dark:border-gray-700">
        <p className="text-xs text-gray-500 dark:text-gray-400">
          Click + to add workspaces, double-click to rename
        </p>
      </div>
    </div>
  );
}
