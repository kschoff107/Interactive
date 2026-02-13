import React from 'react';

export default function ModuleNodeDetail({ node, edges, contextData }) {
  // Look up full module record from backend data
  const moduleDetail = contextData?.structure?.modules?.find(m => m.id === node.id);
  const data = moduleDetail || node.data || {};

  // Find all classes in this module
  const allClasses = contextData?.structure?.classes || [];
  const moduleClasses = allClasses.filter(c => c.module === data.name);

  // Find imports for this module
  const allImports = contextData?.structure?.imports || [];
  const moduleImports = allImports.filter(i => i.module === data.name);

  return (
    <div>
      {/* Identity */}
      <section className="node-detail-section">
        <h3 className="node-detail-section-title">Module Info</h3>
        <table className="node-detail-table">
          <tbody>
            <tr><td className="node-detail-table-label">Name</td><td><code>{data.name}</code></td></tr>
            {data.file_path && (
              <tr><td className="node-detail-table-label">File</td><td><code>{data.file_path}</code></td></tr>
            )}
            <tr><td className="node-detail-table-label">Classes</td><td>{data.class_count ?? moduleClasses.length}</td></tr>
            <tr><td className="node-detail-table-label">Imports</td><td>{data.import_count ?? moduleImports.length}</td></tr>
          </tbody>
        </table>
      </section>

      {/* Classes in this module */}
      {moduleClasses.length > 0 && (
        <section className="node-detail-section">
          <h3 className="node-detail-section-title">Classes ({moduleClasses.length})</h3>
          <table className="node-detail-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Base Classes</th>
                <th>Methods</th>
                <th>Properties</th>
                <th>Line</th>
              </tr>
            </thead>
            <tbody>
              {moduleClasses.map((cls, i) => (
                <tr key={i}>
                  <td>
                    <code>{cls.name}</code>
                    {cls.is_abstract && <span className="node-detail-badge node-detail-badge-yellow" style={{ marginLeft: 4 }}>abstract</span>}
                    {cls.is_interface && <span className="node-detail-badge node-detail-badge-blue" style={{ marginLeft: 4 }}>interface</span>}
                  </td>
                  <td>{(cls.base_classes || []).join(', ') || '—'}</td>
                  <td>{(cls.methods || []).length}</td>
                  <td>{(cls.properties || []).length}</td>
                  <td>{cls.line_number || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      {/* Imports */}
      {moduleImports.length > 0 && (
        <section className="node-detail-section">
          <h3 className="node-detail-section-title">Imports ({moduleImports.length})</h3>
          <div className="node-detail-connection-list">
            {moduleImports.slice(0, 20).map((imp, i) => (
              <div key={i} className="node-detail-connection-item">
                <span className="node-detail-badge node-detail-badge-gray">import</span>
                <code>{imp.imported}</code>
                {imp.alias && <span className="node-detail-connection-context">as {imp.alias}</span>}
              </div>
            ))}
            {moduleImports.length > 20 && (
              <div className="node-detail-connection-item" style={{ fontStyle: 'italic', opacity: 0.7 }}>
                ... and {moduleImports.length - 20} more imports
              </div>
            )}
          </div>
        </section>
      )}

      {/* Empty state */}
      {moduleClasses.length === 0 && moduleImports.length === 0 && (
        <section className="node-detail-section">
          <div className="node-detail-info-box">
            This module contains no classes or imports.
          </div>
        </section>
      )}
    </div>
  );
}
