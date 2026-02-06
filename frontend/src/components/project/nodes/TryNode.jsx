import React, { memo } from 'react';
import { Handle, Position } from 'reactflow';

const TryNode = memo(({ data, selected }) => {
  const { handlers, hasFinally } = data;

  return (
    <div
      className={`
        px-4 py-3 border-2 bg-white dark:bg-gray-800
        ${selected ? 'border-red-500 shadow-lg' : 'border-red-400 dark:border-red-600 shadow-md'}
        transition-all duration-200
      `}
      style={{
        minWidth: '160px',
        maxWidth: '220px',
        clipPath: 'polygon(30% 0%, 70% 0%, 100% 30%, 100% 70%, 70% 100%, 30% 100%, 0% 70%, 0% 30%)'
      }}
    >
      <Handle
        type="target"
        position={Position.Top}
        className="w-3 h-3 !bg-red-500"
      />

      <div className="text-center py-2">
        {/* Try/Except icon */}
        <div className="flex justify-center mb-2">
          <svg className="w-5 h-5 text-red-600 dark:text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
        </div>

        {/* Label */}
        <div className="font-semibold text-sm text-gray-900 dark:text-gray-100 mb-2">
          try/except
        </div>

        {/* Exception handlers */}
        {handlers && handlers.length > 0 && (
          <div className="flex flex-col gap-1 mb-1">
            {handlers.slice(0, 2).map((handler, idx) => (
              <span
                key={idx}
                className="text-xs px-2 py-0.5 bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300 rounded font-mono"
              >
                {handler}
              </span>
            ))}
            {handlers.length > 2 && (
              <span className="text-xs text-gray-500 dark:text-gray-400">
                +{handlers.length - 2} more
              </span>
            )}
          </div>
        )}

        {/* Finally indicator */}
        {hasFinally && (
          <div className="text-xs px-2 py-0.5 bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 rounded inline-block">
            has finally
          </div>
        )}
      </div>

      <Handle
        type="source"
        position={Position.Bottom}
        className="w-3 h-3 !bg-red-500"
      />
    </div>
  );
});

TryNode.displayName = 'TryNode';

export default TryNode;
