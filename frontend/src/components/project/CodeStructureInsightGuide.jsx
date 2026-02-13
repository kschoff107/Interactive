import React, { useState, useEffect, useCallback } from 'react';
import api from '../../services/api';
import { lockScroll, unlockScroll } from '../../utils/modalScrollLock';
import './InsightGuide.css';

/* ------------------------------------------------------------------ */
/*  Guide content (static educational sections)                        */
/* ------------------------------------------------------------------ */
const GuideContent = () => (
  <div className="insight-guide-content">
    {/* Section 1 — What is Code Structure? */}
    <div className="insight-section">
      <h3 className="section-title">
        <span className="section-icon">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="16" x2="12" y2="12" />
            <line x1="12" y1="8" x2="12.01" y2="8" />
          </svg>
        </span>
        What is Code Structure?
      </h3>
      <div className="section-text">
        <div className="concept-block">
          <p className="concept-text">
            The Code Structure visualization maps out the <strong>class hierarchy</strong> in
            your project — every class, its properties, methods, and how classes relate to one
            another through inheritance and composition.
          </p>
        </div>
        <div className="info-box">
          <strong>Think of it this way:</strong> if your code were an organization chart,
          classes are the people, inheritance is the reporting chain, and composition is
          who works closely with whom. This graph lets you see the whole picture at a glance
          so you can spot overly deep hierarchies, tightly coupled components, or classes
          that are doing too much.
        </div>
      </div>
    </div>

    {/* Section 2 — Reading the Graph */}
    <div className="insight-section">
      <h3 className="section-title">
        <span className="section-icon">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
          </svg>
        </span>
        Reading the Graph
      </h3>
      <div className="section-text">
        <div className="concept-block">
          <h4 className="concept-title">ClassNode (boxes)</h4>
          <p className="concept-text">
            Each class appears as a card with three sections:
          </p>
          <ul className="concept-list">
            <li><strong>Header</strong> — the class name, along with badges for abstract, interface, or decorator status.</li>
            <li><strong>Properties</strong> — listed with their visibility icon and type annotation (when available).</li>
            <li><strong>Methods</strong> — listed with visibility, parameters, and return type.</li>
          </ul>
        </div>
        <div className="concept-block">
          <h4 className="concept-title">ModuleNode (gray containers)</h4>
          <p className="concept-text">
            Files are grouped into gray container nodes. Each module node holds every class
            defined in that file, making it easy to see which classes live together.
          </p>
        </div>
        <div className="concept-block">
          <h4 className="concept-title">Edge Types</h4>
          <ul className="concept-list">
            <li><strong>Solid purple line</strong> — inheritance (class B extends A).</li>
            <li><strong>Dashed yellow line</strong> — composition (class A holds a reference to B).</li>
            <li><strong>Gray line</strong> — module-to-class containment (which file defines which class).</li>
          </ul>
        </div>
      </div>
    </div>

    {/* Section 3 — Understanding Badges */}
    <div className="insight-section">
      <h3 className="section-title">
        <span className="section-icon">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M20.59 13.41l-7.17 7.17a2 2 0 01-2.83 0L2 12V2h10l8.59 8.59a2 2 0 010 2.82z" />
            <line x1="7" y1="7" x2="7.01" y2="7" />
          </svg>
        </span>
        Understanding Badges
      </h3>
      <div className="section-text">
        <div className="pattern-grid">
          <div className="pattern-card">
            <div className="pattern-header">
              <span className="pattern-emoji" role="img" aria-label="abstract">A</span>
              <strong>abstract</strong>
            </div>
            <p className="pattern-tip">Italic amber badge — the class cannot be instantiated directly; it must be subclassed.</p>
          </div>
          <div className="pattern-card">
            <div className="pattern-header">
              <span className="pattern-emoji" role="img" aria-label="interface">I</span>
              <strong>interface</strong>
            </div>
            <p className="pattern-tip">Cyan badge — a contract that other classes implement without providing logic itself.</p>
          </div>
          <div className="pattern-card">
            <div className="pattern-header">
              <span className="pattern-emoji" role="img" aria-label="decorator">@</span>
              <strong>@decorator</strong>
            </div>
            <p className="pattern-tip">Purple badge — indicates the class or method uses a decorator pattern.</p>
          </div>
          <div className="pattern-card">
            <div className="pattern-header">
              <span className="pattern-emoji" role="img" aria-label="visibility">+/−/#</span>
              <strong>Visibility Icons</strong>
            </div>
            <p className="pattern-tip">
              <strong>+</strong> public, <strong>−</strong> private, <strong>#</strong> protected.
              These appear next to properties and methods.
            </p>
          </div>
          <div className="pattern-card">
            <div className="pattern-header">
              <span className="pattern-emoji" role="img" aria-label="static">S</span>
              <strong>static</strong>
            </div>
            <p className="pattern-tip">Underlined label — the member belongs to the class itself, not to instances.</p>
          </div>
          <div className="pattern-card">
            <div className="pattern-header">
              <span className="pattern-emoji" role="img" aria-label="async">~</span>
              <strong>async</strong>
            </div>
            <p className="pattern-tip">Blue badge — the method is asynchronous and returns a promise or future.</p>
          </div>
        </div>
      </div>
    </div>

    {/* Section 4 — Statistics Explained */}
    <div className="insight-section">
      <h3 className="section-title">
        <span className="section-icon">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="18" y1="20" x2="18" y2="10" />
            <line x1="12" y1="20" x2="12" y2="4" />
            <line x1="6" y1="20" x2="6" y2="14" />
          </svg>
        </span>
        Statistics Explained
      </h3>
      <div className="section-text">
        <ul className="concept-list">
          <li><strong>Modules</strong> — total number of files (modules) that contain class definitions.</li>
          <li><strong>Classes</strong> — total number of classes discovered across all modules.</li>
          <li><strong>Methods</strong> — combined count of methods across every class.</li>
          <li><strong>Properties</strong> — combined count of properties (fields / attributes) across every class.</li>
          <li><strong>Inheritance chains</strong> — number of distinct parent &rarr; child inheritance relationships.</li>
          <li><strong>Max Depth</strong> — the longest chain of inheritance from a root class to its deepest descendant. Deep hierarchies can signal excessive coupling.</li>
        </ul>
      </div>
    </div>

    {/* Section 5 — OOP Best Practices */}
    <div className="insight-section">
      <h3 className="section-title">
        <span className="section-icon">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M2 3h6a4 4 0 014 4v14a3 3 0 00-3-3H2z" />
            <path d="M22 3h-6a4 4 0 00-4 4v14a3 3 0 013-3h7z" />
          </svg>
        </span>
        OOP Best Practices
      </h3>
      <div className="section-text">
        <div className="tip-box">
          <strong>Keep these principles in mind when reviewing your structure graph:</strong>
        </div>
        <ul className="tips-list">
          <li>
            <strong>Favor composition over inheritance</strong> — prefer holding references
            to other objects (dashed yellow edges) rather than deep class hierarchies (solid
            purple chains). Composition is more flexible and easier to change.
          </li>
          <li>
            <strong>Keep class hierarchies shallow</strong> — if your Max Depth exceeds 3 or
            4 levels, consider flattening. Deep trees are harder to reason about and lead to
            fragile base-class problems.
          </li>
          <li>
            <strong>Single Responsibility Principle</strong> — each class should have one
            reason to change. If a ClassNode card is overflowing with methods, it may be doing
            too much.
          </li>
          <li>
            <strong>Use interfaces for contracts</strong> — define behavior with interfaces
            (cyan badges) and let concrete classes provide the implementation. This decouples
            consumers from providers.
          </li>
          <li>
            <strong>Watch for god classes</strong> — a class with many properties and methods
            that connects to most of the graph is likely a god class. Break it apart into
            focused collaborators.
          </li>
        </ul>
      </div>
    </div>

    {/* Footer */}
    <div className="insight-footer">
      <p>
        Want to learn more? Check out the{' '}
        <a
          href="https://github.com/kschoff107/Interactive"
          target="_blank"
          rel="noopener noreferrer"
          className="footer-link"
        >
          project documentation
        </a>{' '}
        for detailed guides and examples.
      </p>
    </div>
  </div>
);

/* ------------------------------------------------------------------ */
/*  Inline Analysis Tab                                                */
/* ------------------------------------------------------------------ */
const InlineAnalysisTab = ({ analysis, loading, error, onRetry, onCancel }) => {
  if (loading) {
    return (
      <div className="insight-guide-content" style={{ textAlign: 'center', padding: '3rem 1rem' }}>
        <div className="tab-loading-dot" />
        <p style={{ marginTop: '1rem', opacity: 0.8 }}>Analyzing your code structure...</p>
        <button
          onClick={onCancel}
          style={{
            marginTop: '1rem',
            padding: '0.4rem 1rem',
            background: 'transparent',
            border: '1px solid currentColor',
            borderRadius: '6px',
            color: 'inherit',
            cursor: 'pointer',
            opacity: 0.7,
          }}
        >
          Cancel
        </button>
      </div>
    );
  }

  if (error) {
    return (
      <div className="insight-guide-content" style={{ textAlign: 'center', padding: '3rem 1rem' }}>
        <p style={{ color: '#ef4444', marginBottom: '1rem' }}>{error}</p>
        <button
          onClick={onRetry}
          style={{
            padding: '0.5rem 1.25rem',
            background: '#7c3aed',
            border: 'none',
            borderRadius: '6px',
            color: '#fff',
            cursor: 'pointer',
            fontWeight: 600,
          }}
        >
          Retry Analysis
        </button>
      </div>
    );
  }

  if (!analysis) {
    return (
      <div className="insight-guide-content" style={{ textAlign: 'center', padding: '3rem 1rem', opacity: 0.6 }}>
        <p>No analysis available yet. Switch to this tab to trigger analysis.</p>
      </div>
    );
  }

  // Render markdown-like sections by splitting on ### headers
  const sections = analysis.split(/(?=^###\s)/m).filter(Boolean);

  return (
    <div className="insight-guide-content">
      {sections.map((section, idx) => {
        const lines = section.split('\n');
        const headerMatch = lines[0] && lines[0].match(/^###\s+(.*)/);
        const title = headerMatch ? headerMatch[1] : null;
        const body = headerMatch ? lines.slice(1).join('\n').trim() : section.trim();

        return (
          <div key={idx} className="insight-section">
            {title && (
              <h3 className="section-title">
                <span className="section-icon">
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
                  </svg>
                </span>
                {title}
              </h3>
            )}
            {body && (
              <div className="section-text">
                <p className="concept-text" style={{ whiteSpace: 'pre-wrap' }}>{body}</p>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
};

/* ------------------------------------------------------------------ */
/*  Main component                                                     */
/* ------------------------------------------------------------------ */
const CodeStructureInsightGuide = ({ isOpen, onClose, isDark, structureData, projectId }) => {
  const [activeTab, setActiveTab] = useState('guide');
  const [analysis, setAnalysis] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [abortController, setAbortController] = useState(null);

  // Lock / unlock body scroll
  useEffect(() => {
    if (isOpen) {
      lockScroll();
    } else {
      unlockScroll();
    }
    return () => unlockScroll();
  }, [isOpen]);

  // ESC key handler
  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  // Fetch analysis
  const fetchAnalysis = useCallback(
    async (forceRegenerate = false) => {
      if (!projectId) return;
      const controller = new AbortController();
      setAbortController(controller);
      setLoading(true);
      setError(null);

      try {
        const response = await api.post(
          `/projects/${projectId}/analyze-code-structure`,
          { force_regenerate: forceRegenerate },
          { signal: controller.signal }
        );
        setAnalysis(response.data.analysis || response.data);
      } catch (err) {
        if (err.name === 'AbortError' || err.name === 'CanceledError') return;
        setError(err.response?.data?.error || err.message || 'Failed to analyze code structure.');
      } finally {
        setLoading(false);
        setAbortController(null);
      }
    },
    [projectId]
  );

  // Auto-fetch when switching to analyze tab
  useEffect(() => {
    if (activeTab === 'analyze' && !analysis && !loading && !error) {
      fetchAnalysis(false);
    }
  }, [activeTab, analysis, loading, error, fetchAnalysis]);

  const handleRetry = useCallback(() => {
    fetchAnalysis(true);
  }, [fetchAnalysis]);

  const handleCancel = useCallback(() => {
    if (abortController) {
      abortController.abort();
    }
    setLoading(false);
  }, [abortController]);

  // Reset state when modal closes
  useEffect(() => {
    if (!isOpen) {
      setActiveTab('guide');
      setAnalysis(null);
      setLoading(false);
      setError(null);
    }
  }, [isOpen]);

  if (!isOpen) return null;

  return (
    <div className="insight-guide-overlay" onClick={onClose}>
      <div
        className={`insight-guide-modal ${isDark ? 'dark' : ''}`}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="insight-guide-header">
          <h2 className="insight-guide-title">
            <span className="insight-icon">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <rect x="2" y="3" width="20" height="14" rx="2" ry="2" />
                <line x1="8" y1="21" x2="16" y2="21" />
                <line x1="12" y1="17" x2="12" y2="21" />
              </svg>
            </span>
            Code Structure Insight Guide
          </h2>
          <button className="insight-close-btn" onClick={onClose} aria-label="Close">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>

        {/* Tabs */}
        <div className="insight-guide-tabs">
          <button
            className={`insight-tab ${activeTab === 'guide' ? 'active' : ''}`}
            onClick={() => setActiveTab('guide')}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M2 3h6a4 4 0 014 4v14a3 3 0 00-3-3H2z" />
              <path d="M22 3h-6a4 4 0 00-4 4v14a3 3 0 013-3h7z" />
            </svg>
            Understanding Code Structure
          </button>
          <button
            className={`insight-tab ${activeTab === 'analyze' ? 'active' : ''}`}
            onClick={() => setActiveTab('analyze')}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <rect x="2" y="3" width="20" height="14" rx="2" ry="2" />
              <line x1="8" y1="21" x2="16" y2="21" />
              <line x1="12" y1="17" x2="12" y2="21" />
            </svg>
            Analyze My Code
          </button>
        </div>

        {/* Tab content */}
        {activeTab === 'guide' ? (
          <GuideContent />
        ) : (
          <InlineAnalysisTab
            analysis={analysis}
            loading={loading}
            error={error}
            onRetry={handleRetry}
            onCancel={handleCancel}
          />
        )}
      </div>
    </div>
  );
};

export default CodeStructureInsightGuide;
