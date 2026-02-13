import React, { useEffect } from 'react';
import TableNodeDetail from './nodeDetails/TableNodeDetail';
import FunctionNodeDetail from './nodeDetails/FunctionNodeDetail';
import BlueprintNodeDetail from './nodeDetails/BlueprintNodeDetail';
import RouteNodeDetail from './nodeDetails/RouteNodeDetail';
import { lockScroll, unlockScroll } from '../../utils/modalScrollLock';
import './NodeDetailModal.css';

const NodeDetailModal = ({ isOpen, onClose, isDark, node, edges, contextData }) => {
  // Handle ESC key and body scroll lock
  useEffect(() => {
    const handleEsc = (e) => {
      if (e.key === 'Escape') onClose();
    };

    if (isOpen) {
      window.addEventListener('keydown', handleEsc);
      lockScroll();
    }

    return () => {
      window.removeEventListener('keydown', handleEsc);
      if (isOpen) unlockScroll();
    };
  }, [isOpen, onClose]);

  if (!isOpen || !node) return null;

  // Handle backdrop click
  const handleBackdropClick = (e) => {
    if (e.target === e.currentTarget) onClose();
  };

  // Determine node type and pick the right detail renderer
  const nodeType = node.type;
  let DetailComponent = null;
  let icon = '';
  let title = '';
  let subtitle = '';

  if (nodeType === 'functionNode') {
    DetailComponent = FunctionNodeDetail;
    icon = '\u2699\uFE0F';
    title = node.data?.name || 'Function';
    subtitle = node.data?.module ? `${node.data.module} : ${node.data.line || ''}` : '';
  } else if (nodeType === 'blueprintNode') {
    DetailComponent = BlueprintNodeDetail;
    icon = '\uD83D\uDDC2\uFE0F';
    title = node.data?.name || 'Blueprint';
    subtitle = node.data?.url_prefix || '';
  } else if (nodeType === 'routeNode') {
    DetailComponent = RouteNodeDetail;
    icon = '\uD83D\uDD17';
    title = node.data?.name || 'Route';
    subtitle = node.data?.url_pattern || '';
  } else if (contextData?.schema) {
    // Schema table node (type 'default')
    DetailComponent = TableNodeDetail;
    icon = '\uD83D\uDDC3\uFE0F';
    title = node.data?.tableName || node.id;
    subtitle = `${node.data?.columns?.length || 0} columns`;
  }

  if (!DetailComponent) return null;

  return (
    <div
      className={`node-detail-overlay ${isDark ? 'dark' : ''}`}
      onClick={handleBackdropClick}
    >
      <div className="node-detail-modal">
        {/* Header */}
        <div className="node-detail-header">
          <div className="node-detail-header-info">
            <span className="node-detail-icon">{icon}</span>
            <div>
              <h2 className="node-detail-title">{title}</h2>
              {subtitle && <p className="node-detail-subtitle">{subtitle}</p>}
            </div>
          </div>
          <button
            className="node-detail-close-btn"
            onClick={onClose}
            aria-label="Close detail"
          >
            <svg width="20" height="20" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Content */}
        <div className="node-detail-content">
          <DetailComponent node={node} edges={edges} contextData={contextData} />
        </div>
      </div>
    </div>
  );
};

export default NodeDetailModal;
