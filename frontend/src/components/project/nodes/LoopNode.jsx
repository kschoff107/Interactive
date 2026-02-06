import React, { memo } from 'react';
import { Handle, Position } from 'reactflow';

const LoopNode = memo(({ data, selected }) => {
  const { loopType, target, iterator } = data;

  return (
    <div
      className={`
        px-4 py-3 rounded-full border-2 bg-white dark:bg-gray-800
        ${selected ? 'border-green-500 shadow-lg' : 'border-green-400 dark:border-green-600 shadow-md'}
        transition-all duration-200 flex items-center justify-center
      `}
      style={{ minWidth: '140px', minHeight: '140px', maxWidth: '180px' }}
    >
      <Handle
        type="target"
        position={Position.Top}
        className="w-3 h-3 !bg-green-500"
      />

      <div className="text-center">
        {/* Loop icon */}
        <div className="flex justify-center mb-2">
          <svg className="w-5 h-5 text-green-600 dark:text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
        </div>

        {/* Loop type */}
        <div className="font-semibold text-sm text-gray-900 dark:text-gray-100 mb-1">
          {loopType || 'loop'}
        </div>

        {/* Target/Iterator */}
        {(target || iterator) && (
          <div className="text-xs text-gray-600 dark:text-gray-400 font-mono">
            {target && <div className="truncate max-w-[120px] mx-auto">{target}</div>}
            {iterator && <div className="text-xs text-gray-500 dark:text-gray-500 truncate max-w-[120px] mx-auto">in {iterator}</div>}
          </div>
        )}
      </div>

      <Handle
        type="source"
        position={Position.Bottom}
        className="w-3 h-3 !bg-green-500"
      />
    </div>
  );
});

LoopNode.displayName = 'LoopNode';

export default LoopNode;
