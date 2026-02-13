import React, { memo } from 'react';
import { Handle, Position } from 'reactflow';

const ModuleNode = memo(({ data }) => {
  const { name, class_count = 0, import_count = 0 } = data;

  // Shorten module name to last 2 segments for readability
  const parts = name.split(/[./]/);
  const shortName = parts.length > 2 ? '.../' + parts.slice(-2).join('/') : name;

  return (
    <div className="bg-slate-100 dark:bg-slate-800 border-2 border-slate-400 dark:border-slate-500 rounded-lg shadow-sm min-w-[180px] max-w-[220px] text-left">
      <Handle type="target" position={Position.Top} className="!bg-slate-400" />

      <div className="px-3 py-2">
        <div className="flex items-center gap-1.5 mb-1">
          <svg className="w-3.5 h-3.5 text-slate-500 dark:text-slate-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
          <span className="font-semibold text-xs text-gray-800 dark:text-gray-200 truncate" title={name}>
            {shortName}
          </span>
        </div>
        <div className="flex gap-3 text-[10px] text-gray-500 dark:text-gray-400">
          <span>{class_count} class{class_count !== 1 ? 'es' : ''}</span>
          {import_count > 0 && <span>{import_count} imports</span>}
        </div>
      </div>

      <Handle type="source" position={Position.Bottom} className="!bg-slate-400" />
    </div>
  );
});

ModuleNode.displayName = 'ModuleNode';
export default ModuleNode;
