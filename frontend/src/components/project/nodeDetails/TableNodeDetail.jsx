import React from 'react';

const TableNodeDetail = ({ node, edges, contextData }) => {
  const schema = contextData?.schema;
  if (!schema) return <p className="node-detail-empty">No schema data available.</p>;

  const tableName = node.data?.tableName || node.id;
  const table = schema.tables?.find(t => t.name === tableName);

  if (!table) return <p className="node-detail-empty">Table "{tableName}" not found in schema data.</p>;

  // Get relationships involving this table
  const relationships = (schema.relationships || []).filter(
    r => r.from_table === tableName || r.to_table === tableName
  );

  const foreignKeys = table.foreign_keys || [];

  return (
    <>
      {/* Columns Table */}
      <div className="node-detail-section">
        <h3 className="node-detail-section-title">Columns</h3>
        {table.columns && table.columns.length > 0 ? (
          <table className="node-detail-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Type</th>
                <th>PK</th>
                <th>Nullable</th>
                <th>Unique</th>
                <th>FK Reference</th>
              </tr>
            </thead>
            <tbody>
              {table.columns.map((col, i) => {
                const fk = foreignKeys.find(f => f.column === col.name);
                return (
                  <tr key={i}>
                    <td><span className="node-detail-code">{col.name}</span></td>
                    <td>{col.type}</td>
                    <td>{col.primary_key ? 'Yes' : ''}</td>
                    <td>{col.nullable ? 'Yes' : 'No'}</td>
                    <td>{col.unique ? 'Yes' : ''}</td>
                    <td>
                      {fk ? (
                        <span className="node-detail-code">
                          {fk.references_table}.{fk.references_column}
                        </span>
                      ) : ''}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        ) : (
          <p className="node-detail-empty">No columns found.</p>
        )}
      </div>

      {/* Relationships */}
      <div className="node-detail-section">
        <h3 className="node-detail-section-title">Relationships</h3>
        {relationships.length > 0 ? (
          <ul className="node-detail-connections">
            {relationships.map((rel, i) => {
              const isOutbound = rel.from_table === tableName;
              return (
                <li key={i}>
                  <span className="conn-arrow">{isOutbound ? '\u2192' : '\u2190'}</span>
                  <span className="conn-name">{isOutbound ? rel.to_table : rel.from_table}</span>
                  <span className="conn-detail">
                    {rel.from_column} → {rel.to_column} ({rel.type || 'many-to-one'})
                  </span>
                </li>
              );
            })}
          </ul>
        ) : (
          <p className="node-detail-empty">No relationships detected.</p>
        )}
      </div>

      {/* Foreign Keys */}
      {foreignKeys.length > 0 && (
        <div className="node-detail-section">
          <h3 className="node-detail-section-title">Foreign Keys</h3>
          <ul className="node-detail-connections">
            {foreignKeys.map((fk, i) => (
              <li key={i}>
                <span className="conn-arrow">→</span>
                <span className="conn-name">
                  <span className="node-detail-code">{fk.column}</span>
                </span>
                <span className="conn-detail">
                  references {fk.references_table}.{fk.references_column}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </>
  );
};

export default TableNodeDetail;
