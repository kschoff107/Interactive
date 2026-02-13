import React from 'react';

/**
 * Build a human-readable context string from call flags.
 */
const callContext = (call) => {
  const parts = [
    call.is_conditional && 'conditional',
    call.is_loop && 'in loop',
  ].filter(Boolean);
  const ctx = parts.join(' / ');
  const loc = call.line_number ? `line ${call.line_number}` : '';
  return [ctx, loc].filter(Boolean).join(' \u2014 ');
};

const FunctionNodeDetail = ({ node, edges, contextData }) => {
  const flowData = contextData?.flowData;
  if (!flowData) return <p className="node-detail-empty">No flow data available.</p>;

  const funcDetail = flowData.functions?.find(f => f.id === node.id);
  if (!funcDetail) return <p className="node-detail-empty">Function details not found.</p>;

  // Derive callers and callees from calls[] — include all call types
  const calls = flowData.calls || [];
  const callers = calls.filter(c => c.callee_id === node.id);
  const callees = calls.filter(c => c.caller_id === node.id);

  // Control flows inside this function
  const controlFlows = (flowData.control_flows || []).filter(
    cf => cf.parent_function_id === node.id
  );

  // Check if orphan
  const isOrphan = flowData.statistics?.orphan_functions?.includes(node.id);

  // Complexity color
  const complexity = funcDetail.complexity;
  const complexityColor = complexity <= 5 ? 'green' : complexity <= 10 ? 'yellow' : 'red';
  const complexityLabel = complexity <= 5 ? 'Simple' : complexity <= 10 ? 'Moderate' : 'High';

  // Line count
  const lineCount = funcDetail.end_line && funcDetail.line_number
    ? funcDetail.end_line - funcDetail.line_number + 1
    : null;

  // Resolve function name by id for display
  const funcNameById = (id) => {
    const f = flowData.functions?.find(fn => fn.id === id);
    return f ? f.name : id;
  };

  // Render a single caller/callee list item
  const renderCallItem = (call, arrow, nameId, i) => {
    const isExternal = call.call_type !== 'direct';
    const ctx = callContext(call);
    return (
      <li key={i}>
        <span className="conn-arrow">{arrow}</span>
        <span className="conn-name">{funcNameById(nameId)}</span>
        {isExternal && <span className="node-detail-badge gray">external</span>}
        {ctx && <span className="conn-detail">{ctx}</span>}
      </li>
    );
  };

  return (
    <>
      {/* Orphan Warning */}
      {isOrphan && (
        <div className="node-detail-warning">
          No callers detected — this function may be unused or only called from external modules.
        </div>
      )}

      {/* Identity */}
      <div className="node-detail-section">
        <h3 className="node-detail-section-title">Identity</h3>
        <table className="node-detail-table">
          <tbody>
            {funcDetail.qualified_name && (
              <tr>
                <td><strong>Qualified Name</strong></td>
                <td><span className="node-detail-code">{funcDetail.qualified_name}</span></td>
              </tr>
            )}
            {funcDetail.module && (
              <tr>
                <td><strong>Module</strong></td>
                <td>{funcDetail.module}</td>
              </tr>
            )}
            {funcDetail.file_path && (
              <tr>
                <td><strong>File</strong></td>
                <td><span className="node-detail-code">{funcDetail.file_path}</span></td>
              </tr>
            )}
            <tr>
              <td><strong>Line</strong></td>
              <td>
                {funcDetail.line_number}
                {funcDetail.end_line ? ` – ${funcDetail.end_line}` : ''}
                {lineCount ? ` (${lineCount} lines)` : ''}
              </td>
            </tr>
            {funcDetail.class_name && (
              <tr>
                <td><strong>Class</strong></td>
                <td>{funcDetail.class_name}</td>
              </tr>
            )}
          </tbody>
        </table>

        {/* Badges */}
        <div className="node-detail-tags" style={{ marginTop: '8px' }}>
          {funcDetail.is_async && <span className="node-detail-badge purple">Async</span>}
          {funcDetail.is_method && <span className="node-detail-badge blue">Method</span>}
          {flowData.entry_points?.includes(node.id) && (
            <span className="node-detail-badge green">Entry Point</span>
          )}
        </div>
      </div>

      {/* Signature */}
      <div className="node-detail-section">
        <h3 className="node-detail-section-title">Signature</h3>
        <div className="node-detail-codeblock">
          {`${funcDetail.is_async ? 'async ' : ''}def ${funcDetail.name || 'unknown'}(${(funcDetail.parameters || []).join(', ')})`}
        </div>
      </div>

      {/* Decorators */}
      {funcDetail.decorators && funcDetail.decorators.length > 0 && (
        <div className="node-detail-section">
          <h3 className="node-detail-section-title">Decorators</h3>
          <div className="node-detail-codeblock">
            {funcDetail.decorators.map((d, i) => (
              <div key={i}>{d.startsWith('@') ? d : `@${d}`}</div>
            ))}
          </div>
        </div>
      )}

      {/* Docstring */}
      {funcDetail.docstring && (
        <div className="node-detail-section">
          <h3 className="node-detail-section-title">Docstring</h3>
          <div className="node-detail-info">{funcDetail.docstring}</div>
        </div>
      )}

      {/* Complexity */}
      {complexity !== undefined && complexity !== null && (
        <div className="node-detail-section">
          <h3 className="node-detail-section-title">Complexity</h3>
          <div className="node-detail-tags">
            <span className={`node-detail-badge ${complexityColor}`}>
              {complexity} — {complexityLabel}
            </span>
          </div>
        </div>
      )}

      {/* Callers */}
      <div className="node-detail-section">
        <h3 className="node-detail-section-title">Callers ({callers.length})</h3>
        {callers.length > 0 ? (
          <ul className="node-detail-connections">
            {callers.map((c, i) => renderCallItem(c, '\u2190', c.caller_id, i))}
          </ul>
        ) : (
          <p className="node-detail-empty">No callers detected.</p>
        )}
      </div>

      {/* Callees */}
      <div className="node-detail-section">
        <h3 className="node-detail-section-title">Callees ({callees.length})</h3>
        {callees.length > 0 ? (
          <ul className="node-detail-connections">
            {callees.map((c, i) => renderCallItem(c, '\u2192', c.callee_id, i))}
          </ul>
        ) : (
          <p className="node-detail-empty">No outgoing calls.</p>
        )}
      </div>

      {/* Control Flow */}
      {controlFlows.length > 0 && (
        <div className="node-detail-section">
          <h3 className="node-detail-section-title">Internal Control Flow ({controlFlows.length})</h3>
          <table className="node-detail-table">
            <thead>
              <tr>
                <th>Type</th>
                <th>Line</th>
                <th>Condition / Branches</th>
              </tr>
            </thead>
            <tbody>
              {controlFlows.map((cf, i) => (
                <tr key={i}>
                  <td>
                    <span className={`node-detail-badge ${
                      cf.flow_type === 'if_else' ? 'orange'
                      : cf.flow_type.includes('loop') ? 'green'
                      : cf.flow_type === 'try_except' ? 'red'
                      : 'gray'
                    }`}>
                      {cf.flow_type.replace(/_/g, '/')}
                    </span>
                  </td>
                  <td>{cf.line_number}{cf.end_line ? `–${cf.end_line}` : ''}</td>
                  <td>
                    {cf.condition && (
                      <span className="node-detail-code">{cf.condition}</span>
                    )}
                    {cf.branches && cf.branches.length > 0 && (
                      <span className="conn-detail" style={{ marginLeft: cf.condition ? '8px' : 0 }}>
                        [{cf.branches.join(', ')}]
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
};

export default FunctionNodeDetail;
