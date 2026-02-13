import React from 'react';

const BlueprintNodeDetail = ({ node, edges, contextData }) => {
  const routesData = contextData?.routesData;
  if (!routesData) return <p className="node-detail-empty">No routes data available.</p>;

  const blueprint = routesData.blueprints?.find(b => b.id === node.id);
  if (!blueprint) return <p className="node-detail-empty">Blueprint details not found.</p>;

  // Get all routes belonging to this blueprint
  const blueprintRoutes = (routesData.routes || []).filter(r => r.blueprint_id === node.id);

  // Method breakdown
  const methodCounts = {};
  blueprintRoutes.forEach(route => {
    (route.methods || []).forEach(m => {
      methodCounts[m] = (methodCounts[m] || 0) + 1;
    });
  });

  // Security summary
  const protectedCount = blueprintRoutes.filter(r => r.security?.requires_auth).length;
  const unprotectedCount = blueprintRoutes.length - protectedCount;

  return (
    <>
      {/* Identity */}
      <div className="node-detail-section">
        <h3 className="node-detail-section-title">Identity</h3>
        <table className="node-detail-table">
          <tbody>
            <tr>
              <td><strong>Name</strong></td>
              <td>{blueprint.name}</td>
            </tr>
            <tr>
              <td><strong>URL Prefix</strong></td>
              <td><span className="node-detail-code">{blueprint.url_prefix || '/'}</span></td>
            </tr>
            {blueprint.file_path && (
              <tr>
                <td><strong>File</strong></td>
                <td><span className="node-detail-code">{blueprint.file_path}</span></td>
              </tr>
            )}
            {blueprint.line_number && (
              <tr>
                <td><strong>Line</strong></td>
                <td>{blueprint.line_number}</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Security Summary */}
      <div className="node-detail-section">
        <h3 className="node-detail-section-title">Security Summary</h3>
        <div className="node-detail-tags">
          <span className="node-detail-badge green">{protectedCount} Protected</span>
          {unprotectedCount > 0 && (
            <span className="node-detail-badge red">{unprotectedCount} Unprotected</span>
          )}
        </div>
        {unprotectedCount > 0 && (
          <div className="node-detail-warning" style={{ marginTop: '8px' }}>
            {unprotectedCount} route{unprotectedCount > 1 ? 's' : ''} in this blueprint {unprotectedCount > 1 ? 'have' : 'has'} no authentication.
          </div>
        )}
      </div>

      {/* Method Breakdown */}
      {Object.keys(methodCounts).length > 0 && (
        <div className="node-detail-section">
          <h3 className="node-detail-section-title">Method Breakdown</h3>
          <div className="node-detail-tags">
            {Object.entries(methodCounts)
              .sort(([a], [b]) => a.localeCompare(b))
              .map(([method, count]) => (
                <span key={method} className={`node-detail-method ${method}`}>
                  {method} ({count})
                </span>
              ))}
          </div>
        </div>
      )}

      {/* Route Listing */}
      <div className="node-detail-section">
        <h3 className="node-detail-section-title">Routes ({blueprintRoutes.length})</h3>
        {blueprintRoutes.length > 0 ? (
          blueprintRoutes.map((route, i) => (
            <div key={i} className="node-detail-route-row">
              <div style={{ display: 'flex', gap: '4px', flexShrink: 0 }}>
                {(route.methods || []).map((m, j) => (
                  <span key={j} className={`node-detail-method ${m}`}>{m}</span>
                ))}
              </div>
              <span className="node-detail-route-url">{route.full_url || route.url_pattern}</span>
              {route.function_name && (
                <span className="node-detail-route-func">{route.function_name}</span>
              )}
              {route.security?.requires_auth ? (
                <span className="node-detail-badge green" style={{ fontSize: '10px', padding: '1px 6px' }}>Auth</span>
              ) : (
                <span className="node-detail-badge red" style={{ fontSize: '10px', padding: '1px 6px' }}>Open</span>
              )}
            </div>
          ))
        ) : (
          <p className="node-detail-empty">No routes in this blueprint.</p>
        )}
      </div>
    </>
  );
};

export default BlueprintNodeDetail;
