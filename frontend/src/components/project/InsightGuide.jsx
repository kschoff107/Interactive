import React, { useState, useEffect, useCallback } from 'react';
import AnalysisTab from './AnalysisTab';
import { generateBasicAnalysis } from '../../utils/basicAnalysis';
import api from '../../services/api';
import { lockScroll, unlockScroll } from '../../utils/modalScrollLock';
import './InsightGuide.css';

const InsightGuide = ({ isOpen, onClose, isDark, flowData, projectId }) => {
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
      // Call the API using the configured api service
      const response = await api.post(`/projects/${projectId}/analyze-code`, { force_regenerate: false });

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
      // Call the API using the configured api service
      const response = await api.post(`/projects/${projectId}/analyze-code`, { force_regenerate: true });

      setAnalysis(response.data.analysis);
    } catch (err) {
      console.error('Retry error:', err);
      const message = err.response?.data?.error || err.message || 'Failed to generate analysis';
      setError({ message });
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  // Handle use fallback
  const handleUseFallback = useCallback(() => {
    if (flowData) {
      const basicAnalysis = generateBasicAnalysis(flowData);
      setAnalysis(basicAnalysis);
      setError(null);
    }
  }, [flowData]);

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
  const canAnalyze = flowData && projectId;

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
            Understanding Runtime Flow
          </button>
          <button
            className={`insight-tab ${activeTab === 'analyze' ? 'active' : ''} ${!canAnalyze ? 'disabled' : ''}`}
            onClick={canAnalyze ? handleAnalyzeClick : undefined}
            disabled={!canAnalyze}
            title={!canAnalyze ? 'Upload code to enable analysis' : ''}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2"
                d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
            </svg>
            Analyze My Code
            {loading && <span className="tab-loading-dot"></span>}
          </button>
        </div>

        {/* Content */}
        <div className="insight-guide-content">
          {activeTab === 'guide' ? (
            <GuideContent />
          ) : (
            <AnalysisTab
              analysis={analysis}
              loading={loading}
              error={error}
              flowData={flowData}
              onRetry={handleRetry}
              onUseFallback={handleUseFallback}
              onCancel={handleCancel}
            />
          )}
        </div>
      </div>
    </div>
  );
};

/**
 * Original guide content as a separate component
 */
const GuideContent = () => (
  <>
    {/* Section 1: Overview */}
    <section className="insight-section">
      <h3 className="section-title">
        <span className="section-icon">🎯</span>
        What is Runtime Flow?
      </h3>
      <p className="section-text">
        This visualization shows how functions in your code call each other during execution.
        Think of it as a <strong>map of your code's behavior</strong> – it traces the path from where
        your program starts to where it goes.
      </p>
      <div className="info-box">
        <strong>💡 Quick Analogy:</strong> If your code were a city, this map shows the roads (function calls)
        connecting different buildings (functions). Entry points are where visitors arrive!
      </div>
    </section>

    {/* Section 2: Reading the Graph */}
    <section className="insight-section">
      <h3 className="section-title">
        <span className="section-icon">📊</span>
        Reading the Graph
      </h3>

      <div className="concept-block">
        <h4 className="concept-title">Blue Boxes = Functions</h4>
        <p className="concept-text">Each blue box represents a function or method in your code.</p>
        <ul className="concept-list">
          <li><strong>Name & Parameters:</strong> What the function is called and what inputs it takes</li>
          <li><strong>📍 Line Number:</strong> Where to find it in your source file</li>
          <li><strong>🏷️ Decorators:</strong> Special markers like <code>@app.route</code> or <code>@staticmethod</code></li>
          <li><strong>🎯 Complexity Score:</strong> How many decision points the function has (see below)</li>
          <li><strong>⚡ Async Badge:</strong> Shows if function runs asynchronously</li>
          <li><strong>⭐ Entry Point:</strong> Where execution begins (routes, main functions)</li>
        </ul>
      </div>

      <div className="concept-block">
        <h4 className="concept-title">Arrows = Function Calls</h4>
        <p className="concept-text">Arrows show which functions call which other functions.</p>
        <div className="edge-examples">
          <div className="edge-example">
            <div className="edge-line blue-edge"></div>
            <div className="edge-desc">
              <strong>Blue Solid Line:</strong> Direct function call
              <br />
              <span className="edge-detail">Function A always calls Function B</span>
            </div>
          </div>
          <div className="edge-example">
            <div className="edge-line orange-edge"></div>
            <div className="edge-desc">
              <strong>Orange Solid Line:</strong> Conditional call
              <br />
              <span className="edge-detail">Call happens inside if/else or loop</span>
            </div>
          </div>
          <div className="edge-example">
            <div className="edge-line dashed-edge"></div>
            <div className="edge-desc">
              <strong>Dashed Line:</strong> Circular dependency ⚠️
              <br />
              <span className="edge-detail">Functions call each other (potential issue)</span>
            </div>
          </div>
        </div>
      </div>
    </section>

    {/* Section 3: Statistics Panel */}
    <section className="insight-section">
      <h3 className="section-title">
        <span className="section-icon">📈</span>
        Statistics Explained
      </h3>
      <p className="section-text">
        The panel in the top-right corner shows key metrics about your code:
      </p>
      <dl className="stats-list">
        <dt>Total Functions</dt>
        <dd>How many functions exist in your codebase</dd>

        <dt>Total Calls</dt>
        <dd>How many times functions call each other (more calls = more complexity)</dd>

        <dt>Entry Points</dt>
        <dd>Where execution starts – typically API routes, CLI commands, or main() functions</dd>

        <dt>Max Depth</dt>
        <dd>The deepest chain of function calls (A → B → C → D = depth of 4)</dd>

        <dt>Circular Dependencies</dt>
        <dd>Functions that call each other in a loop – may cause infinite recursion or tight coupling</dd>
      </dl>
    </section>

    {/* Section 4: Complexity Guide */}
    <section className="insight-section">
      <h3 className="section-title">
        <span className="section-icon">🎨</span>
        Understanding Complexity
      </h3>
      <p className="section-text">
        <strong>Cyclomatic Complexity</strong> measures how many decision points (if/else, loops, etc.)
        exist in a function. More decisions = harder to test and understand.
      </p>
      <div className="complexity-guide">
        <div className="complexity-item green">
          <div className="complexity-badge">🟢 1-5</div>
          <div className="complexity-info">
            <strong>Simple</strong>
            <p>Easy to understand and test. Few decision points. ✨</p>
          </div>
        </div>
        <div className="complexity-item yellow">
          <div className="complexity-badge">🟡 6-10</div>
          <div className="complexity-info">
            <strong>Moderate</strong>
            <p>Still manageable but getting complex. Watch it carefully.</p>
          </div>
        </div>
        <div className="complexity-item red">
          <div className="complexity-badge">🔴 11+</div>
          <div className="complexity-info">
            <strong>High Complexity</strong>
            <p>Consider refactoring! Hard to test and maintain. ⚠️</p>
          </div>
        </div>
      </div>
      <div className="tip-box">
        <strong>💡 Pro Tip:</strong> Lower complexity = easier to understand, test, and maintain.
        Try to keep functions under 10!
      </div>
    </section>

    {/* Section 5: Common Patterns */}
    <section className="insight-section">
      <h3 className="section-title">
        <span className="section-icon">🔍</span>
        What to Look For
      </h3>

      <div className="pattern-grid">
        <div className="pattern-card">
          <div className="pattern-header">
            <span className="pattern-emoji">✨</span>
            <h4>Entry Points</h4>
          </div>
          <p>
            Functions marked with a ⭐ badge are entry points – where execution begins.
            In web apps, these are usually API routes (<code>@app.get</code>, <code>@app.post</code>).
            In scripts, it's the <code>main()</code> function.
          </p>
          <p className="pattern-tip">
            <strong>What it means:</strong> These are your app's public interface!
          </p>
        </div>

        <div className="pattern-card warning">
          <div className="pattern-header">
            <span className="pattern-emoji">⚠️</span>
            <h4>Circular Dependencies</h4>
          </div>
          <p>
            When you see dashed lines, it means functions call each other in a cycle
            (A calls B, B calls A). This can cause infinite loops or make code hard to reason about.
          </p>
          <p className="pattern-tip">
            <strong>What to do:</strong> Review if the circular calls are intentional.
            Consider refactoring to break the cycle.
          </p>
        </div>

        <div className="pattern-card">
          <div className="pattern-header">
            <span className="pattern-emoji">🔗</span>
            <h4>Orphan Functions</h4>
          </div>
          <p>
            Functions with no incoming arrows are "orphans" – they're defined but never called.
            They might be unused code or only called from external modules.
          </p>
          <p className="pattern-tip">
            <strong>What to do:</strong> Check if they're still needed. May be safe to delete!
          </p>
        </div>

        <div className="pattern-card">
          <div className="pattern-header">
            <span className="pattern-emoji">🌊</span>
            <h4>Call Chains</h4>
          </div>
          <p>
            Follow the arrows to trace execution flow. Long chains might indicate deep nesting,
            while wide chains suggest many parallel operations.
          </p>
          <p className="pattern-tip">
            <strong>What it means:</strong> Understand the path your data takes through your code!
          </p>
        </div>
      </div>
    </section>

    {/* Section 6: Tips & Tricks */}
    <section className="insight-section">
      <h3 className="section-title">
        <span className="section-icon">💡</span>
        Pro Tips & Best Practices
      </h3>
      <ul className="tips-list">
        <li>
          <strong>🎨 Use "Quick Organize"</strong> to auto-layout the graph if it gets messy
        </li>
        <li>
          <strong>🖱️ Click nodes</strong> to highlight connected functions and see relationships
        </li>
        <li>
          <strong>🔴 High complexity functions</strong> (red badges) are good candidates for refactoring
        </li>
        <li>
          <strong>⭐ Entry points</strong> reveal your app's API surface or main execution paths
        </li>
        <li>
          <strong>⚠️ Circular dependencies</strong> might need architectural review to prevent issues
        </li>
        <li>
          <strong>🔍 Zoom and pan</strong> to explore different parts of your codebase
        </li>
        <li>
          <strong>📊 Watch the statistics</strong> panel to track code health over time
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
        {' '}or explore your code to discover patterns!
      </p>
    </div>
  </>
);

export default InsightGuide;
