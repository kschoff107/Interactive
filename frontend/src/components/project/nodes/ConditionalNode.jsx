import React, { memo } from 'react';
import { Handle, Position } from 'reactflow';

const ConditionalNode = memo(({ data, selected }) => {
  const { condition, branches } = data;

  return (
    <div
      className={`
        px-4 py-3 rounded-lg border-2 bg-white dark:bg-gray-800
        ${selected ? 'border-orange-500 shadow-lg' : 'border-orange-400 dark:border-orange-600 shadow-md'}
        transition-all duration-200 transform rotate-45
      `}
      style={{ minWidth: '160px', maxWidth: '220px' }}
    >
      <div className="transform -rotate-45">
        <Handle
          type="target"
          position={Position.Top}
          className="w-3 h-3 !bg-orange-500 transform rotate-45"
        />

        {/* Header */}
        <div className="flex items-center gap-2 mb-2">
          {/* Conditional icon */}
          <svg className="w-4 h-4 text-orange-600 dark:text-orange-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 9l4-4 4 4m0 6l-4 4-4-4" />
          </svg>

          {/* Label */}
          <span className="font-semibold text-sm text-gray-900 dark:text-gray-100">
            if/else
          </span>
        </div>

        {/* Condition */}
        {condition && (
          <div className="text-xs text-gray-600 dark:text-gray-400 mb-2 font-mono truncate">
            {condition.length > 30 ? `${condition.substring(0, 30)}...` : condition}
          </div>
        )}

        {/* Branches */}
        {branches && branches.length > 0 && (
          <div className="flex gap-1 flex-wrap">
            {branches.map((branch, idx) => (
              <span
                key={idx}
                className="text-xs px-1.5 py-0.5 bg-orange-100 dark:bg-orange-900/30 text-orange-700 dark:text-orange-300 rounded"
              >
                {branch}
              </span>
            ))}
          </div>
        )}

        <Handle
          type="source"
          position={Position.Bottom}
          className="w-3 h-3 !bg-orange-500 transform rotate-45"
        />
      </div>
    </div>
  );
});

ConditionalNode.displayName = 'ConditionalNode';

export default ConditionalNode;
