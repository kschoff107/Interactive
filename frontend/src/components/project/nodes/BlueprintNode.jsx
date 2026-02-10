import React, { memo } from 'react';
import { Handle, Position } from 'reactflow';

const BlueprintNode = memo(({ data, selected }) => {
  const { name, url_prefix, route_count } = data;

  return (
    <div
      className={`
        px-5 py-4 rounded-xl border-2 bg-slate-100 dark:bg-slate-700
        ${selected ? 'border-blue-500 shadow-lg' : 'border-slate-400 dark:border-slate-500 shadow-md'}
        transition-all duration-200
      `}
      style={{ minWidth: '180px' }}
    >
      <Handle
        type="target"
        position={Position.Top}
        className="w-3 h-3 !bg-slate-500"
      />

      {/* Blueprint icon and name */}
      <div className="flex items-center gap-2 mb-1">
        <svg className="w-5 h-5 text-slate-600 dark:text-slate-300 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
        </svg>
        <span className="font-semibold text-slate-700 dark:text-slate-200">
          {name}
        </span>
      </div>

      {/* URL prefix */}
      <div className="font-mono text-xs text-slate-500 dark:text-slate-400 mb-2">
        {url_prefix || '/'}
      </div>

      {/* Route count badge */}
      <div className="inline-flex items-center px-2 py-0.5 rounded bg-slate-200 dark:bg-slate-600 text-xs text-slate-600 dark:text-slate-300">
        {route_count} route{route_count !== 1 ? 's' : ''}
      </div>

      <Handle
        type="source"
        position={Position.Bottom}
        className="w-3 h-3 !bg-slate-500"
      />
    </div>
  );
});

BlueprintNode.displayName = 'BlueprintNode';

export default BlueprintNode;
