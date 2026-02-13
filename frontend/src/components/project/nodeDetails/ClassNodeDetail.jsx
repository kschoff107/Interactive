import React from 'react';

const visibilityLabel = (v) => {
  if (v === 'private') return 'private';
  if (v === 'protected') return 'protected';
  if (v === 'dunder') return 'dunder';
  return 'public';
};

export default function ClassNodeDetail({ node, edges, contextData }) {
  // Look up full class record from backend data
  const classDetail = contextData?.structure?.classes?.find(c => c.id === node.id);
  const data = classDetail || node.data || {};

  const methods = data.methods || [];
  const properties = data.properties || [];
  const baseClasses = data.base_classes || [];
  const decorators = data.decorators || [];

  // Find subclasses (nodes that inherit from this class)
  const relationships = contextData?.structure?.relationships || [];
  const subclassRels = relationships.filter(r => r.target_id === node.id && r.type === 'inheritance');
  const parentRels = relationships.filter(r => r.source_id === node.id && r.type === 'inheritance');
  const compositionRels = relationships.filter(r => r.source_id === node.id && r.type === 'composition');

  const allClasses = contextData?.structure?.classes || [];
  const subclasses = subclassRels.map(r => allClasses.find(c => c.id === r.source_id)).filter(Boolean);
  const parents = parentRels.map(r => allClasses.find(c => c.id === r.target_id)).filter(Boolean);

  return (
    <div>
      {/* Identity */}
      <section className="node-detail-section">
        <h3 className="node-detail-section-title">Identity</h3>
        <table className="node-detail-table">
          <tbody>
            <tr><td className="node-detail-table-label">Name</td><td>{data.name}</td></tr>
            <tr><td className="node-detail-table-label">Module</td><td><code>{data.module}</code></td></tr>
            {data.file_path && (
              <tr><td className="node-detail-table-label">File</td><td><code>{data.file_path}</code></td></tr>
            )}
            {data.line_number && (
              <tr><td className="node-detail-table-label">Line</td><td>{data.line_number}{data.end_line ? ` – ${data.end_line}` : ''}</td></tr>
            )}
          </tbody>
        </table>
      </section>

      {/* Badges */}
      <section className="node-detail-section">
        <div className="node-detail-badge-row">
          {data.is_interface && <span className="node-detail-badge node-detail-badge-blue">interface</span>}
          {data.is_abstract && <span className="node-detail-badge node-detail-badge-yellow">abstract</span>}
          {decorators.map((dec, i) => (
            <span key={i} className="node-detail-badge node-detail-badge-purple">@{dec}</span>
          ))}
        </div>
      </section>

      {/* Docstring */}
      {data.docstring && (
        <section className="node-detail-section">
          <h3 className="node-detail-section-title">Docstring</h3>
          <div className="node-detail-code-block">{data.docstring}</div>
        </section>
      )}

      {/* Inheritance */}
      {(baseClasses.length > 0 || parents.length > 0) && (
        <section className="node-detail-section">
          <h3 className="node-detail-section-title">Inherits From</h3>
          <div className="node-detail-connection-list">
            {baseClasses.map((base, i) => {
              const parentClass = parents.find(p => p.name === base);
              return (
                <div key={i} className="node-detail-connection-item">
                  <span className="node-detail-badge node-detail-badge-purple">extends</span>
                  <span>{base}</span>
                  {parentClass && <span className="node-detail-connection-context">{parentClass.module}</span>}
                </div>
              );
            })}
          </div>
        </section>
      )}

      {/* Subclasses */}
      {subclasses.length > 0 && (
        <section className="node-detail-section">
          <h3 className="node-detail-section-title">Subclasses ({subclasses.length})</h3>
          <div className="node-detail-connection-list">
            {subclasses.map((sub, i) => (
              <div key={i} className="node-detail-connection-item">
                <span className="node-detail-badge node-detail-badge-green">{sub.name}</span>
                <span className="node-detail-connection-context">{sub.module}</span>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Composition */}
      {compositionRels.length > 0 && (
        <section className="node-detail-section">
          <h3 className="node-detail-section-title">Composition</h3>
          <div className="node-detail-connection-list">
            {compositionRels.map((rel, i) => {
              const target = allClasses.find(c => c.id === rel.target_id);
              return (
                <div key={i} className="node-detail-connection-item">
                  <span className="node-detail-badge node-detail-badge-yellow">has</span>
                  <span>{rel.label}</span>
                  {target && <span className="node-detail-connection-context">→ {target.name}</span>}
                </div>
              );
            })}
          </div>
        </section>
      )}

      {/* Properties */}
      {properties.length > 0 && (
        <section className="node-detail-section">
          <h3 className="node-detail-section-title">Properties ({properties.length})</h3>
          <table className="node-detail-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Type</th>
                <th>Line</th>
              </tr>
            </thead>
            <tbody>
              {properties.map((prop, i) => (
                <tr key={i}>
                  <td><code>{prop.name}</code></td>
                  <td>{prop.type || '—'}</td>
                  <td>{prop.line_number || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      {/* Methods */}
      {methods.length > 0 && (
        <section className="node-detail-section">
          <h3 className="node-detail-section-title">Methods ({methods.length})</h3>
          <table className="node-detail-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Parameters</th>
                <th>Return</th>
                <th>Visibility</th>
                <th>Line</th>
              </tr>
            </thead>
            <tbody>
              {methods.map((method, i) => (
                <tr key={i}>
                  <td>
                    <code>{method.name}</code>
                    {method.is_static && <span className="node-detail-badge node-detail-badge-gray" style={{ marginLeft: 4 }}>static</span>}
                    {method.is_async && <span className="node-detail-badge node-detail-badge-blue" style={{ marginLeft: 4 }}>async</span>}
                    {method.is_abstract && <span className="node-detail-badge node-detail-badge-yellow" style={{ marginLeft: 4 }}>abstract</span>}
                    {method.is_classmethod && <span className="node-detail-badge node-detail-badge-green" style={{ marginLeft: 4 }}>cls</span>}
                  </td>
                  <td>
                    {(method.parameters || []).map(p => p.type ? `${p.name}: ${p.type}` : p.name).join(', ') || '—'}
                  </td>
                  <td>{method.return_type || '—'}</td>
                  <td>{visibilityLabel(method.visibility)}</td>
                  <td>{method.line_number || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      {/* Empty state */}
      {methods.length === 0 && properties.length === 0 && (
        <section className="node-detail-section">
          <div className="node-detail-info-box">
            This class has no methods or properties defined.
          </div>
        </section>
      )}
    </div>
  );
}
