import React from 'react';

const RouteNodeDetail = ({ node, edges, contextData }) => {
  const routesData = contextData?.routesData;
  if (!routesData) return <p className="node-detail-empty">No routes data available.</p>;

  const route = routesData.routes?.find(r => r.id === node.id);
  if (!route) return <p className="node-detail-empty">Route details not found.</p>;

  // Find parent blueprint
  const blueprint = route.blueprint_id
    ? routesData.blueprints?.find(b => b.id === route.blueprint_id)
    : null;

  // Sibling routes (same blueprint, excluding this one)
  const siblings = blueprint
    ? (routesData.routes || []).filter(r => r.blueprint_id === route.blueprint_id && r.id !== route.id)
    : [];

  const pathParams = route.parameters?.path_params || [];
  const authDecorators = route.security?.auth_decorators || [];
  const requiresAuth = route.security?.requires_auth || false;

  return (
    <>
      {/* Full URL */}
      <div className="node-detail-section">
        <h3 className="node-detail-section-title">Endpoint</h3>
        <div className="node-detail-codeblock" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <div style={{ display: 'flex', gap: '4px', flexShrink: 0 }}>
            {(route.methods || []).map((m, i) => (
              <span key={i} className={`node-detail-method ${m}`}>{m}</span>
            ))}
          </div>
          <span>{route.full_url || route.url_pattern}</span>
        </div>
      </div>

      {/* Identity */}
      <div className="node-detail-section">
        <h3 className="node-detail-section-title">Details</h3>
        <table className="node-detail-table">
          <tbody>
            {route.function_name && (
              <tr>
                <td><strong>Handler</strong></td>
                <td><span className="node-detail-code">{route.function_name}</span></td>
              </tr>
            )}
            {route.file_path && (
              <tr>
                <td><strong>File</strong></td>
                <td><span className="node-detail-code">{route.file_path}</span></td>
              </tr>
            )}
            {route.line_number && (
              <tr>
                <td><strong>Line</strong></td>
                <td>{route.line_number}</td>
              </tr>
            )}
            {route.module && (
              <tr>
                <td><strong>Module</strong></td>
                <td>{route.module}</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Docstring */}
      {route.docstring && (
        <div className="node-detail-section">
          <h3 className="node-detail-section-title">Docstring</h3>
          <div className="node-detail-info">{route.docstring}</div>
        </div>
      )}

      {/* Path Parameters */}
      {pathParams.length > 0 && (
        <div className="node-detail-section">
          <h3 className="node-detail-section-title">Path Parameters</h3>
          <table className="node-detail-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Type</th>
              </tr>
            </thead>
            <tbody>
              {pathParams.map((p, i) => (
                <tr key={i}>
                  <td><span className="node-detail-code">{p.name}</span></td>
                  <td>{p.type || 'string'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Security */}
      <div className="node-detail-section">
        <h3 className="node-detail-section-title">Security</h3>
        <div className="node-detail-tags">
          {requiresAuth ? (
            <span className="node-detail-badge green">Authenticated</span>
          ) : (
            <span className="node-detail-badge red">No Authentication</span>
          )}
        </div>
        {authDecorators.length > 0 && (
          <div className="node-detail-codeblock" style={{ marginTop: '8px' }}>
            {authDecorators.map((d, i) => (
              <div key={i}>@{d}</div>
            ))}
          </div>
        )}
        {!requiresAuth && (
          <div className="node-detail-warning" style={{ marginTop: '8px' }}>
            This route has no authentication — it is publicly accessible.
          </div>
        )}
      </div>

      {/* Blueprint Context */}
      {blueprint && (
        <div className="node-detail-section">
          <h3 className="node-detail-section-title">Blueprint Context</h3>
          <table className="node-detail-table">
            <tbody>
              <tr>
                <td><strong>Blueprint</strong></td>
                <td>{blueprint.name}</td>
              </tr>
              <tr>
                <td><strong>Prefix</strong></td>
                <td><span className="node-detail-code">{blueprint.url_prefix || '/'}</span></td>
              </tr>
            </tbody>
          </table>

          {siblings.length > 0 && (
            <>
              <h4 className="node-detail-section-title" style={{ fontSize: '12px', marginTop: '12px', marginBottom: '8px' }}>
                Sibling Routes ({siblings.length})
              </h4>
              {siblings.map((s, i) => (
                <div key={i} className="node-detail-route-row">
                  <div style={{ display: 'flex', gap: '4px', flexShrink: 0 }}>
                    {(s.methods || []).map((m, j) => (
                      <span key={j} className={`node-detail-method ${m}`}>{m}</span>
                    ))}
                  </div>
                  <span className="node-detail-route-url">{s.full_url || s.url_pattern}</span>
                </div>
              ))}
            </>
          )}
        </div>
      )}
    </>
  );
};

export default RouteNodeDetail;
