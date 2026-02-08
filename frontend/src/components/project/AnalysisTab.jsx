import React from 'react';
import LoadingAnalysis from './LoadingAnalysis';
import { generateBasicAnalysis, isAIAnalysis } from '../../utils/basicAnalysis';

/**
 * Analysis Tab Component
 * Displays AI-generated or fallback code analysis in 6 sections
 */
const AnalysisTab = ({
  analysis,
  loading,
  error,
  flowData,
  onRetry,
  onUseFallback,
  onCancel
}) => {
  // Show loading state
  if (loading) {
    return <LoadingAnalysis onCancel={onCancel} />;
  }

  // Show error state
  if (error) {
    return (
      <div className="analysis-error">
        <div className="error-icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
            <circle cx="12" cy="12" r="10" strokeWidth="2" />
            <path strokeLinecap="round" strokeWidth="2" d="M12 8v4M12 16h.01" />
          </svg>
        </div>
        <h3 className="error-title">Analysis Generation Failed</h3>
        <p className="error-message">
          {error.message || "We couldn't generate the AI analysis."}
        </p>
        <p className="error-reasons">This might be due to:</p>
        <ul className="error-list">
          <li>API rate limits</li>
          <li>Network issues</li>
          <li>Service temporarily unavailable</li>
        </ul>
        <div className="error-actions">
          <button className="retry-btn" onClick={onRetry}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2"
                d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            Retry Analysis
          </button>
          <button className="fallback-btn" onClick={onUseFallback}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2"
                d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
            </svg>
            Use Basic Insights
          </button>
        </div>
      </div>
    );
  }

  // No analysis yet - show prompt to generate
  if (!analysis) {
    return (
      <div className="analysis-prompt">
        <div className="prompt-icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2"
              d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
          </svg>
        </div>
        <h3 className="prompt-title">Ready to Analyze Your Code</h3>
        <p className="prompt-text">
          Click the button above to generate a personalized analysis of your code's runtime flow.
          You'll get insights about architecture, complexity, and potential issues.
        </p>
      </div>
    );
  }

  // Determine if this is AI or fallback analysis
  const isAI = isAIAnalysis(analysis);

  // Section configuration
  const sections = [
    {
      key: 'overview',
      title: 'Overview',
      icon: '📋',
      content: analysis.overview
    },
    {
      key: 'how_it_starts',
      title: 'How Your Application Starts',
      icon: '🚀',
      content: analysis.how_it_starts
    },
    {
      key: 'architecture',
      title: 'The Architecture',
      icon: '🏗️',
      content: analysis.architecture
    },
    {
      key: 'complexity',
      title: 'Complexity Analysis',
      icon: '📊',
      content: analysis.complexity
    },
    {
      key: 'potential_issues',
      title: 'Potential Issues',
      icon: '⚠️',
      content: analysis.potential_issues
    },
    {
      key: 'call_chains',
      title: 'Call Chain Examples',
      icon: '🔗',
      content: analysis.call_chains
    }
  ];

  return (
    <div className="analysis-content">
      {/* Analysis Type Badge */}
      <div className={`analysis-badge ${isAI ? 'ai-badge' : 'basic-badge'}`}>
        {isAI ? (
          <>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2"
                d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
            </svg>
            AI Analysis
          </>
        ) : (
          <>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2"
                d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
            </svg>
            Basic Insights
          </>
        )}
      </div>

      {/* Analysis Sections */}
      {sections.map((section) => (
        <div key={section.key} className="analysis-section">
          <h4 className="analysis-section-title">
            <span className="analysis-section-icon">{section.icon}</span>
            {section.title}
          </h4>
          <p className="analysis-section-content">{section.content}</p>
        </div>
      ))}

      {/* Footer */}
      <div className="analysis-footer">
        {!isAI && flowData && (
          <button className="try-ai-btn" onClick={onRetry}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2"
                d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
            </svg>
            Try AI Analysis
          </button>
        )}
        <p className="analysis-note">
          {isAI
            ? "This analysis was generated by Claude AI based on your code's runtime flow."
            : "This is a basic analysis based on your code's structure. Try AI Analysis for more detailed insights."
          }
        </p>
      </div>
    </div>
  );
};

export default AnalysisTab;
