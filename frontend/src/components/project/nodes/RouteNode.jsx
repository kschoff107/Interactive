import React, { memo } from 'react';
import { Handle, Position } from 'reactflow';

const METHOD_COLORS = {
  GET: { bg: 'bg-green-500', text: 'text-white' },
  POST: { bg: 'bg-blue-500', text: 'text-white' },
  PUT: { bg: 'bg-orange-500', text: 'text-white' },
  DELETE: { bg: 'bg-red-500', text: 'text-white' },
  PATCH: { bg: 'bg-purple-500', text: 'text-white' },
  OPTIONS: { bg: 'bg-gray-500', text: 'text-white' },
};

const RouteNode = memo(({ data, selected }) => {
  const { name, url_pattern, methods, requires_auth, docstring } = data;

  return (
    <div
      className={`
        px-4 py-3 rounded-lg border-2 bg-white dark:bg-gray-800
        ${selected ? 'border-blue-500 shadow-lg' : 'border-gray-300 dark:border-gray-600 shadow-md'}
        transition-all duration-200
      `}
      style={{ minWidth: '200px', maxWidth: '300px' }}
    >
      <Handle
        type="target"
        position={Position.Top}
        className="w-3 h-3 !bg-gray-400"
      />

      {/* Method badges */}
      <div className="flex flex-wrap gap-1 mb-2">
        {methods && methods.map((method) => (
          <span
            key={method}
            className={`px-2 py-0.5 text-xs font-bold rounded ${METHOD_COLORS[method]?.bg || 'bg-gray-500'} ${METHOD_COLORS[method]?.text || 'text-white'}`}
          >
            {method}
          </span>
        ))}
        {requires_auth && (
          <span className="px-2 py-0.5 text-xs bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300 rounded flex items-center gap-1">
            <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M5 9V7a5 5 0 0110 0v2a2 2 0 012 2v5a2 2 0 01-2 2H5a2 2 0 01-2-2v-5a2 2 0 012-2zm8-2v2H7V7a3 3 0 016 0z" clipRule="evenodd" />
            </svg>
            Auth
          </span>
        )}
      </div>

      {/* URL pattern */}
      <div className="font-mono text-sm text-gray-900 dark:text-gray-100 mb-1 break-all">
        {url_pattern}
      </div>

      {/* Function name */}
      <div className="text-xs text-gray-500 dark:text-gray-400">
        {name}()
      </div>

      {/* Docstring preview */}
      {docstring && (
        <div className="mt-2 text-xs text-gray-400 dark:text-gray-500 truncate" title={docstring}>
          {docstring}
        </div>
      )}

      <Handle
        type="source"
        position={Position.Bottom}
        className="w-3 h-3 !bg-gray-400"
      />
    </div>
  );
});

RouteNode.displayName = 'RouteNode';

export default RouteNode;
