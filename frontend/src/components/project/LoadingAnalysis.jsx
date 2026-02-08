import React, { useState, useEffect } from 'react';

/**
 * Animated loading component for AI analysis generation
 * Shows step-by-step progress with visual indicators
 */
const LoadingAnalysis = ({ onCancel }) => {
  const [currentStep, setCurrentStep] = useState(0);
  const [progress, setProgress] = useState(0);

  const loadingSteps = [
    { label: 'Tracing function calls', duration: 2000 },
    { label: 'Identifying entry points', duration: 2000 },
    { label: 'Analyzing complexity patterns', duration: 3000 },
    { label: 'Detecting potential issues', duration: 2000 },
    { label: 'Generating insights', duration: 5000 }
  ];

  const totalDuration = loadingSteps.reduce((sum, step) => sum + step.duration, 0);

  useEffect(() => {
    let elapsed = 0;
    let stepElapsed = 0;
    let stepIndex = 0;

    const interval = setInterval(() => {
      elapsed += 100;
      stepElapsed += 100;

      // Update overall progress
      setProgress(Math.min((elapsed / totalDuration) * 100, 95));

      // Check if we should move to next step
      if (stepIndex < loadingSteps.length - 1 && stepElapsed >= loadingSteps[stepIndex].duration) {
        stepIndex++;
        stepElapsed = 0;
        setCurrentStep(stepIndex);
      }
    }, 100);

    return () => clearInterval(interval);
  }, []);

  return (
    <div className="loading-analysis">
      <div className="loading-header">
        <div className="loading-icon">
          <svg className="spinner" viewBox="0 0 24 24" fill="none" stroke="currentColor">
            <circle cx="12" cy="12" r="10" strokeWidth="3" strokeLinecap="round" strokeDasharray="31.4 31.4" />
          </svg>
        </div>
        <h3 className="loading-title">Analyzing Your Code...</h3>
      </div>

      <div className="loading-steps">
        {loadingSteps.map((step, index) => (
          <div
            key={index}
            className={`loading-step ${
              index < currentStep ? 'completed' :
              index === currentStep ? 'active' : 'pending'
            }`}
          >
            <div className="step-indicator">
              {index < currentStep ? (
                <svg className="check-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7" />
                </svg>
              ) : index === currentStep ? (
                <div className="step-spinner"></div>
              ) : (
                <div className="step-dot"></div>
              )}
            </div>
            <span className="step-label">{step.label}</span>
          </div>
        ))}
      </div>

      <div className="loading-progress">
        <div className="progress-bar">
          <div
            className="progress-fill"
            style={{ width: `${progress}%` }}
          ></div>
        </div>
        <span className="progress-text">{Math.round(progress)}%</span>
      </div>

      <p className="loading-info">
        This may take a few moments while we analyze your code structure...
      </p>

      {onCancel && (
        <button className="cancel-btn" onClick={onCancel}>
          Cancel
        </button>
      )}
    </div>
  );
};

export default LoadingAnalysis;
