import React, { memo } from 'react';
import { Handle, Position } from 'reactflow';

const FunctionNode = memo(({ data, selected }) => {
  const { name, parameters, decorators, complexity, isAsync, isEntryPoint } = data;

  return (
    <div
      className={`
        px-4 py-3 rounded-lg border-2 bg-white dark:bg-gray-800
        ${selected ? 'border-blue-500 shadow-lg' : 'border-blue-400 dark:border-blue-600 shadow-md'}
        transition-all duration-200
      `}
      style={{ minWidth: '200px', maxWidth: '300px' }}
    >
      <Handle
        type="target"
        position={Position.Top}
        className="w-3 h-3 !bg-blue-500"
      />

      {/* Header */}
      <div className="flex items-center gap-2 mb-2">
        {/* Function icon */}
        <svg className="w-4 h-4 text-blue-600 dark:text-blue-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
        </svg>

        {/* Function name */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1">
            {isAsync && (
              <span className="text-xs px-1.5 py-0.5 bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300 rounded font-mono">
                async
              </span>
            )}
            <span className="font-semibold text-sm text-gray-900 dark:text-gray-100 truncate">
              {name}
            </span>
          </div>
        </div>

        {/* Entry point badge */}
        {isEntryPoint && (
          <span className="text-xs px-1.5 py-0.5 bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300 rounded font-medium flex-shrink-0">
            Entry
          </span>
        )}
      </div>

      {/* Decorators */}
      {decorators && decorators.length > 0 && (
        <div className="mb-2 flex flex-wrap gap-1">
          {decorators.slice(0, 3).map((decorator, idx) => (
            <span
              key={idx}
              className="text-xs px-1.5 py-0.5 bg-amber-50 dark:bg-amber-900/20 text-amber-700 dark:text-amber-300 rounded font-mono"
            >
              {decorator}
            </span>
          ))}
          {decorators.length > 3 && (
            <span className="text-xs text-gray-500 dark:text-gray-400">
              +{decorators.length - 3}
            </span>
          )}
        </div>
      )}

      {/* Parameters */}
      <div className="text-xs text-gray-600 dark:text-gray-400 mb-2 font-mono">
        ({parameters && parameters.length > 0 ? parameters.join(', ') : ''})
      </div>

      {/* Complexity indicator */}
      {complexity !== undefined && (
        <div className="flex items-center gap-2 text-xs">
          <span className="text-gray-500 dark:text-gray-400">Complexity:</span>
          <div className="flex items-center gap-1">
            <div
              className={`
                px-2 py-0.5 rounded font-medium
                ${
                  complexity <= 5
                    ? 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300'
                    : complexity <= 10
                    ? 'bg-yellow-100 dark:bg-yellow-900/30 text-yellow-700 dark:text-yellow-300'
                    : 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300'
                }
              `}
            >
              {complexity}
            </div>
          </div>
        </div>
      )}

      <Handle
        type="source"
        position={Position.Bottom}
        className="w-3 h-3 !bg-blue-500"
      />
    </div>
  );
});

FunctionNode.displayName = 'FunctionNode';

export default FunctionNode;
