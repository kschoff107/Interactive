import React, { memo } from 'react';
import { Handle, Position } from 'reactflow';

const visibilityIcon = (v) => {
  if (v === 'private') return '−';
  if (v === 'protected') return '#';
  return '+';
};

const ClassNode = memo(({ data }) => {
  const {
    name, base_classes = [], is_abstract, is_interface,
    visibleMethods = [], methodCount = 0, propertyCount = 0,
    properties = [], decorators = [],
  } = data;

  const visibleProps = properties.slice(0, 4);
  const hiddenMethodCount = methodCount - visibleMethods.length;

  return (
    <div className="bg-white dark:bg-gray-800 border-2 border-indigo-400 dark:border-indigo-500 rounded-lg shadow-md min-w-[220px] max-w-[280px] text-left">
      <Handle type="target" position={Position.Top} className="!bg-indigo-400" />

      {/* Header */}
      <div className="bg-indigo-50 dark:bg-indigo-900/30 px-3 py-2 rounded-t-md border-b border-indigo-200 dark:border-indigo-700">
        <div className="flex items-center gap-1.5 flex-wrap">
          {is_interface && (
            <span className="px-1.5 py-0.5 text-[10px] font-bold bg-cyan-100 dark:bg-cyan-900 text-cyan-700 dark:text-cyan-300 rounded">
              interface
            </span>
          )}
          {is_abstract && (
            <span className="px-1.5 py-0.5 text-[10px] font-bold bg-amber-100 dark:bg-amber-900 text-amber-700 dark:text-amber-300 rounded italic">
              abstract
            </span>
          )}
          {decorators.length > 0 && (
            <span className="px-1.5 py-0.5 text-[10px] font-medium bg-purple-100 dark:bg-purple-900 text-purple-700 dark:text-purple-300 rounded">
              @{decorators[0]}
            </span>
          )}
        </div>
        <div className="font-bold text-sm text-gray-900 dark:text-gray-100 mt-1 truncate" title={name}>
          {name}
        </div>
        {base_classes.length > 0 && (
          <div className="text-[10px] text-indigo-600 dark:text-indigo-400 mt-0.5 truncate" title={base_classes.join(', ')}>
            extends {base_classes.join(', ')}
          </div>
        )}
      </div>

      {/* Properties section */}
      {visibleProps.length > 0 && (
        <div className="px-3 py-1.5 border-b border-gray-100 dark:border-gray-700">
          <div className="text-[10px] font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-1">
            Properties ({propertyCount})
          </div>
          {visibleProps.map((prop, idx) => (
            <div key={idx} className="text-[11px] text-gray-700 dark:text-gray-300 truncate leading-[18px]" title={`${prop.name}: ${prop.type}`}>
              {prop.name}
              {prop.type && <span className="text-gray-400 dark:text-gray-500">: {prop.type}</span>}
            </div>
          ))}
          {propertyCount > 4 && (
            <div className="text-[10px] text-gray-400 dark:text-gray-500 italic">
              +{propertyCount - 4} more
            </div>
          )}
        </div>
      )}

      {/* Methods section */}
      {visibleMethods.length > 0 && (
        <div className="px-3 py-1.5">
          <div className="text-[10px] font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-1">
            Methods ({methodCount})
          </div>
          {visibleMethods.map((method, idx) => (
            <div key={idx} className="text-[11px] text-gray-700 dark:text-gray-300 truncate leading-[20px] flex items-center gap-1">
              <span className="text-gray-400 dark:text-gray-500 font-mono text-[10px] w-3">
                {visibilityIcon(method.visibility)}
              </span>
              <span className={method.is_static ? 'underline' : ''}>
                {method.name}
              </span>
              <span className="text-gray-400 dark:text-gray-500">()</span>
              {method.is_async && (
                <span className="text-[9px] text-blue-500 dark:text-blue-400 font-medium">async</span>
              )}
              {method.is_abstract && (
                <span className="text-[9px] text-amber-500 dark:text-amber-400 font-medium italic">abs</span>
              )}
            </div>
          ))}
          {hiddenMethodCount > 0 && (
            <div className="text-[10px] text-gray-400 dark:text-gray-500 italic mt-0.5">
              +{hiddenMethodCount} more
            </div>
          )}
        </div>
      )}

      {/* Empty state */}
      {visibleMethods.length === 0 && visibleProps.length === 0 && (
        <div className="px-3 py-2 text-[11px] text-gray-400 dark:text-gray-500 italic">
          Empty class
        </div>
      )}

      <Handle type="source" position={Position.Bottom} className="!bg-indigo-400" />
    </div>
  );
});

ClassNode.displayName = 'ClassNode';
export default ClassNode;
