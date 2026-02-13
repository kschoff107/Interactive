import React, { useState, useEffect, useCallback } from 'react';
import ApiRoutesAnalysisTab from './ApiRoutesAnalysisTab';
import api from '../../services/api';
import { lockScroll, unlockScroll } from '../../utils/modalScrollLock';
import './InsightGuide.css';

const ApiRoutesInsightGuide = ({ isOpen, onClose, isDark, routesData, projectId }) => {
  // Tab state
  const [activeTab, setActiveTab] = useState('guide');

  // Analysis state
  const [analysis, setAnalysis] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Handle ESC key to close modal
  useEffect(() => {
    const handleEsc = (e) => {
      if (e.key === 'Escape') {
        onClose();
      }
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

  // Reset state when modal opens
  useEffect(() => {
    if (isOpen) {
      setActiveTab('guide');
      setError(null);
    }
  }, [isOpen]);

  // Handle analyze click
  const handleAnalyzeClick = useCallback(async () => {
    // If we already have analysis, just switch tabs
    if (analysis && activeTab !== 'analyze') {
      setActiveTab('analyze');
      return;
    }

    // Switch to analyze tab and start loading
    setActiveTab('analyze');
    setLoading(true);
    setError(null);

    try {
      // Call the API for API routes analysis
      const response = await api.post(`/projects/${projectId}/analyze-api-routes`, { force_regenerate: false });

      setAnalysis(response.data.analysis);
    } catch (err) {
      console.error('Analysis error:', err);
      const message = err.response?.data?.error || err.message || 'Failed to generate analysis';
      setError({ message });
    } finally {
      setLoading(false);
    }
  }, [projectId, analysis, activeTab]);

  // Handle retry
  const handleRetry = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      // Call the API with force regenerate
      const response = await api.post(`/projects/${projectId}/analyze-api-routes`, { force_regenerate: true });

      setAnalysis(response.data.analysis);
    } catch (err) {
      console.error('Retry error:', err);
      const message = err.response?.data?.error || err.message || 'Failed to generate analysis';
      setError({ message });
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  // Handle cancel loading
  const handleCancel = useCallback(() => {
    setLoading(false);
    setActiveTab('guide');
  }, []);

  if (!isOpen) return null;

  // Handle click on backdrop to close
  const handleBackdropClick = (e) => {
    if (e.target === e.currentTarget) {
      onClose();
    }
  };

  // Check if we can show the analyze tab
  const canAnalyze = routesData && projectId;

  return (
    <div
      className={`insight-guide-overlay ${isDark ? 'dark' : ''}`}
      onClick={handleBackdropClick}
    >
      <div className="insight-guide-modal">
        {/* Header */}
        <div className="insight-guide-header">
          <h2 className="insight-guide-title">
            <span className="insight-icon">🔍</span>
            Decode This
          </h2>
          <button
            className="insight-close-btn"
            onClick={onClose}
            aria-label="Close guide"
          >
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Tabs */}
        <div className="insight-guide-tabs">
          <button
            className={`insight-tab ${activeTab === 'guide' ? 'active' : ''}`}
            onClick={() => setActiveTab('guide')}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2"
                d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
            </svg>
            Understanding API Routes
          </button>
          <button
            className={`insight-tab ${activeTab === 'analyze' ? 'active' : ''} ${!canAnalyze ? 'disabled' : ''}`}
            onClick={canAnalyze ? handleAnalyzeClick : undefined}
            disabled={!canAnalyze}
            title={!canAnalyze ? 'Analyze API routes first to enable AI analysis' : ''}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2"
                d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
            </svg>
            Analyze My API
            {loading && <span className="tab-loading-dot"></span>}
          </button>
        </div>

        {/* Content */}
        <div className="insight-guide-content">
          {activeTab === 'guide' ? (
            <GuideContent />
          ) : (
            <ApiRoutesAnalysisTab
              analysis={analysis}
              loading={loading}
              error={error}
              onRetry={handleRetry}
              onCancel={handleCancel}
            />
          )}
        </div>
      </div>
    </div>
  );
};

/**
 * Guide content for API Routes visualization
 */
const GuideContent = () => (
  <>
    {/* Section 1: Overview */}
    <section className="insight-section">
      <h3 className="section-title">
        <span className="section-icon">🎯</span>
        What is API Routes Visualization?
      </h3>
      <p className="section-text">
        This visualization shows all the <strong>HTTP endpoints</strong> in your Flask application.
        It maps out your API structure, showing how routes are organized into blueprints and what
        HTTP methods each endpoint supports.
      </p>
      <div className="info-box">
        <strong>💡 Quick Analogy:</strong> If your API were a restaurant menu, blueprints are the
        categories (Appetizers, Main Courses) and routes are the individual dishes customers can order!
      </div>
    </section>

    {/* Section 2: Reading the Graph */}
    <section className="insight-section">
      <h3 className="section-title">
        <span className="section-icon">📊</span>
        Reading the Graph
      </h3>

      <div className="concept-block">
        <h4 className="concept-title">Gray Boxes = Blueprints</h4>
        <p className="concept-text">Each gray container represents a Flask Blueprint – a way to organize related routes.</p>
        <ul className="concept-list">
          <li><strong>Blueprint Name:</strong> The identifier used in your code</li>
          <li><strong>URL Prefix:</strong> The base path all routes in this blueprint share (e.g., <code>/api/users</code>)</li>
          <li><strong>Route Count:</strong> How many endpoints are registered to this blueprint</li>
        </ul>
      </div>

      <div className="concept-block">
        <h4 className="concept-title">White Cards = Routes</h4>
        <p className="concept-text">Each card represents an API endpoint your application exposes.</p>
        <ul className="concept-list">
          <li><strong>HTTP Method Badge:</strong> GET, POST, PUT, DELETE, or PATCH (color-coded)</li>
          <li><strong>🔒 Auth Badge:</strong> Shows if the route requires authentication</li>
          <li><strong>URL Pattern:</strong> The path to access this endpoint</li>
          <li><strong>Function Name:</strong> The Python function that handles requests</li>
          <li><strong>Description:</strong> What the endpoint does (from docstrings)</li>
        </ul>
      </div>
    </section>

    {/* Section 3: HTTP Methods */}
    <section className="insight-section">
      <h3 className="section-title">
        <span className="section-icon">🎨</span>
        HTTP Methods Explained
      </h3>
      <p className="section-text">
        Each HTTP method has a specific purpose in RESTful APIs:
      </p>
      <div className="complexity-guide">
        <div className="complexity-item green">
          <div className="complexity-badge" style={{ background: '#10b981' }}>GET</div>
          <div className="complexity-info">
            <strong>Read Data</strong>
            <p>Retrieve information without modifying anything. Safe to call multiple times.</p>
          </div>
        </div>
        <div className="complexity-item" style={{ borderLeftColor: '#3b82f6' }}>
          <div className="complexity-badge" style={{ background: '#3b82f6' }}>POST</div>
          <div className="complexity-info">
            <strong>Create Data</strong>
            <p>Submit new data to be processed or stored. Creates new resources.</p>
          </div>
        </div>
        <div className="complexity-item" style={{ borderLeftColor: '#f59e0b' }}>
          <div className="complexity-badge" style={{ background: '#f59e0b' }}>PUT</div>
          <div className="complexity-info">
            <strong>Update Data</strong>
            <p>Replace existing data entirely. Updates or creates if not found.</p>
          </div>
        </div>
        <div className="complexity-item" style={{ borderLeftColor: '#8b5cf6' }}>
          <div className="complexity-badge" style={{ background: '#8b5cf6' }}>PATCH</div>
          <div className="complexity-info">
            <strong>Partial Update</strong>
            <p>Modify specific fields of existing data without replacing everything.</p>
          </div>
        </div>
        <div className="complexity-item red">
          <div className="complexity-badge" style={{ background: '#ef4444' }}>DELETE</div>
          <div className="complexity-info">
            <strong>Remove Data</strong>
            <p>Delete existing resources. Use with caution!</p>
          </div>
        </div>
      </div>
    </section>

    {/* Section 4: Statistics Panel */}
    <section className="insight-section">
      <h3 className="section-title">
        <span className="section-icon">📈</span>
        Statistics Explained
      </h3>
      <p className="section-text">
        The panel in the top-right corner shows key metrics about your API:
      </p>
      <dl className="stats-list">
        <dt>Blueprints</dt>
        <dd>How many route groups/modules your API has</dd>

        <dt>Total Routes</dt>
        <dd>The total number of API endpoints available</dd>

        <dt>Protected</dt>
        <dd>Routes that require authentication (JWT, login, etc.)</dd>

        <dt>Unprotected</dt>
        <dd>Public routes accessible without authentication</dd>

        <dt>By Method</dt>
        <dd>Breakdown of routes by HTTP method type</dd>
      </dl>
    </section>

    {/* Section 5: Security */}
    <section className="insight-section">
      <h3 className="section-title">
        <span className="section-icon">🔒</span>
        Authentication & Security
      </h3>

      <div className="pattern-grid">
        <div className="pattern-card">
          <div className="pattern-header">
            <span className="pattern-emoji">🔐</span>
            <h4>Protected Routes</h4>
          </div>
          <p>
            Routes marked with <strong>Auth</strong> require valid authentication.
            These are protected by decorators like <code>@jwt_required()</code> or
            <code>@login_required</code>.
          </p>
          <p className="pattern-tip">
            <strong>What it means:</strong> Users must be logged in to access these endpoints.
          </p>
        </div>

        <div className="pattern-card warning">
          <div className="pattern-header">
            <span className="pattern-emoji">⚠️</span>
            <h4>Unprotected Routes</h4>
          </div>
          <p>
            Routes without the Auth badge are publicly accessible. Make sure this is intentional!
            Login and registration routes should be unprotected, but data endpoints usually shouldn't be.
          </p>
          <p className="pattern-tip">
            <strong>Review carefully:</strong> Ensure sensitive data isn't exposed on public routes.
          </p>
        </div>
      </div>
    </section>

    {/* Section 6: Filter Buttons */}
    <section className="insight-section">
      <h3 className="section-title">
        <span className="section-icon">🔍</span>
        Using the Filter Buttons
      </h3>
      <p className="section-text">
        The filter buttons at the top center let you focus on specific HTTP methods:
      </p>
      <ul className="tips-list">
        <li>
          <strong>All:</strong> Show all routes (default view)
        </li>
        <li>
          <strong>GET:</strong> Show only read operations
        </li>
        <li>
          <strong>POST:</strong> Show only create operations
        </li>
        <li>
          <strong>PUT/PATCH:</strong> Show only update operations
        </li>
        <li>
          <strong>DELETE:</strong> Show only delete operations – review these carefully!
        </li>
      </ul>
      <div className="tip-box">
        <strong>💡 Pro Tip:</strong> Use filters to audit specific operation types.
        For example, filter by DELETE to review all destructive operations in your API.
      </div>
    </section>

    {/* Section 7: Best Practices */}
    <section className="insight-section">
      <h3 className="section-title">
        <span className="section-icon">💡</span>
        API Design Best Practices
      </h3>
      <ul className="tips-list">
        <li>
          <strong>🏷️ Use descriptive URL patterns</strong> – <code>/users/&lt;id&gt;</code> is better than <code>/get-user</code>
        </li>
        <li>
          <strong>🔒 Protect sensitive routes</strong> – Always require auth for data modification
        </li>
        <li>
          <strong>📁 Organize with Blueprints</strong> – Group related routes together
        </li>
        <li>
          <strong>📝 Add docstrings</strong> – Document what each endpoint does
        </li>
        <li>
          <strong>🎯 Use correct HTTP methods</strong> – GET for reading, POST for creating, etc.
        </li>
        <li>
          <strong>⚡ Keep route handlers focused</strong> – One responsibility per endpoint
        </li>
      </ul>
    </section>

    {/* Footer */}
    <div className="insight-footer">
      <p>
        <strong>Need more help?</strong> Check the{' '}
        <a
          href="https://github.com/kschoff107/Interactive"
          target="_blank"
          rel="noopener noreferrer"
          className="footer-link"
        >
          documentation
        </a>
        {' '}or explore your API structure!
      </p>
    </div>
  </>
);

export default ApiRoutesInsightGuide;
