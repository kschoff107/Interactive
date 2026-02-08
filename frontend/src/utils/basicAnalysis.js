/**
 * Basic Analysis Utility
 *
 * Generates template-based code analysis insights from flowData
 * when the AI service is unavailable. Provides a fallback experience
 * that still gives users useful information about their code.
 */

/**
 * Generate basic analysis from flowData without AI
 * @param {Object} flowData - The runtime flow data from the parser
 * @returns {Object} Analysis object with 6 narrative sections
 */
export function generateBasicAnalysis(flowData) {
  if (!flowData) {
    return getEmptyAnalysis();
  }

  const stats = flowData.statistics || {};
  const functions = flowData.functions || [];
  const entryPoints = flowData.entry_points || [];
  const modules = flowData.modules || [];
  const calls = flowData.calls || [];

  return {
    overview: generateOverview(stats, functions, modules, entryPoints),
    how_it_starts: generateHowItStarts(entryPoints, functions, stats),
    architecture: generateArchitecture(functions, calls, modules),
    complexity: generateComplexity(functions),
    potential_issues: generatePotentialIssues(stats, functions),
    call_chains: generateCallChains(stats, calls, functions)
  };
}

/**
 * Returns empty analysis when no data is available
 */
function getEmptyAnalysis() {
  return {
    overview: "No code data available to analyze. Please upload Python files to see insights.",
    how_it_starts: "Upload your code to discover entry points and execution flow.",
    architecture: "Code structure information will appear here after analysis.",
    complexity: "Complexity metrics will be calculated after code upload.",
    potential_issues: "Potential issues will be identified after analysis.",
    call_chains: "Call chain information will be available after code upload."
  };
}

/**
 * Generate overview section
 */
function generateOverview(stats, functions, modules, entryPoints) {
  const funcCount = stats.total_functions || functions.length || 0;
  const moduleCount = modules.length || 0;
  const entryCount = entryPoints.length || 0;
  const callCount = stats.total_calls || 0;

  if (funcCount === 0) {
    return "No functions were detected in the uploaded code. This might be a configuration file or non-Python code.";
  }

  // Detect application type
  let appType = "Python application";
  const decorators = functions.flatMap(f => f.decorators || []);

  if (decorators.some(d => d.includes('app.route') || d.includes('app.get') || d.includes('app.post'))) {
    appType = "Flask web application";
  } else if (decorators.some(d => d.includes('router') || d.includes('APIRouter'))) {
    appType = "FastAPI web application";
  } else if (functions.some(f => f.name === 'main')) {
    appType = "Python script/CLI application";
  }

  // Count async functions
  const asyncCount = functions.filter(f => f.is_async).length;
  const asyncNote = asyncCount > 0 ? ` It includes ${asyncCount} async function${asyncCount > 1 ? 's' : ''} for concurrent operations.` : '';

  return `You've uploaded a ${appType} with ${funcCount} function${funcCount !== 1 ? 's' : ''} across ${moduleCount} module${moduleCount !== 1 ? 's' : ''}. ` +
    `The code has ${entryCount} entry point${entryCount !== 1 ? 's' : ''} and ${callCount} function call${callCount !== 1 ? 's' : ''} between components.${asyncNote}`;
}

/**
 * Generate how it starts section
 */
function generateHowItStarts(entryPoints, functions, stats) {
  if (entryPoints.length === 0) {
    // Look for main functions or standalone scripts
    const mainFunc = functions.find(f => f.name === 'main');
    if (mainFunc) {
      return `Your application starts with the main() function at line ${mainFunc.line_number}. ` +
        `This is typically called when the script is run directly. ` +
        `From there, execution flows through ${stats.max_call_depth || 1} level${(stats.max_call_depth || 1) !== 1 ? 's' : ''} of function calls.`;
    }

    return "No clear entry points were detected. This might be a library or module meant to be imported by other code. " +
      "Functions defined here are likely called from external modules.";
  }

  // Group entry points by type
  const routes = entryPoints.filter(e => e.type === 'route');
  const mainFuncs = entryPoints.filter(e => e.type === 'main_function');

  let description = `Your application has ${entryPoints.length} entry point${entryPoints.length !== 1 ? 's' : ''}. `;

  if (routes.length > 0) {
    const routeNames = routes.slice(0, 3).map(r => {
      const func = functions.find(f => f.id === r.function_id);
      return func ? func.name : 'unknown';
    });

    description += `There ${routes.length === 1 ? 'is' : 'are'} ${routes.length} API route${routes.length !== 1 ? 's' : ''} ` +
      `(${routeNames.join(', ')}${routes.length > 3 ? '...' : ''}) that handle incoming requests. `;
  }

  if (mainFuncs.length > 0) {
    description += `The main() function serves as the primary entry point for script execution. `;
  }

  description += `Maximum call depth is ${stats.max_call_depth || 1} level${(stats.max_call_depth || 1) !== 1 ? 's' : ''}.`;

  return description;
}

/**
 * Generate architecture section
 */
function generateArchitecture(functions, calls, modules) {
  if (functions.length === 0) {
    return "No functions detected to analyze architecture.";
  }

  // Find hub functions (most called)
  const callCounts = {};
  calls.forEach(call => {
    if (call.call_type === 'direct' && call.callee_id) {
      callCounts[call.callee_id] = (callCounts[call.callee_id] || 0) + 1;
    }
  });

  const hubFunctions = Object.entries(callCounts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 3)
    .map(([funcId, count]) => {
      const func = functions.find(f => f.id === funcId);
      return { func, count };
    })
    .filter(item => item.func);

  // Analyze decorators
  const decoratorTypes = {};
  functions.forEach(f => {
    (f.decorators || []).forEach(d => {
      const type = categorizeDecorator(d);
      decoratorTypes[type] = (decoratorTypes[type] || 0) + 1;
    });
  });

  let description = "";

  if (hubFunctions.length > 0) {
    const hubNames = hubFunctions.map(h => `${h.func.name} (called ${h.count}x)`);
    description += `The hub of your application ${hubFunctions.length === 1 ? 'is' : 'includes'} ${hubNames.join(', ')}. ` +
      `${hubFunctions.length === 1 ? 'This function is' : 'These functions are'} central to the code flow. `;
  }

  // Add module info
  if (modules.length > 1) {
    description += `Code is organized across ${modules.length} modules. `;
  }

  // Add decorator patterns
  const patterns = [];
  if (decoratorTypes['route'] > 0) patterns.push(`${decoratorTypes['route']} route handler${decoratorTypes['route'] > 1 ? 's' : ''}`);
  if (decoratorTypes['static'] > 0) patterns.push(`${decoratorTypes['static']} static method${decoratorTypes['static'] > 1 ? 's' : ''}`);
  if (decoratorTypes['class'] > 0) patterns.push(`${decoratorTypes['class']} class method${decoratorTypes['class'] > 1 ? 's' : ''}`);
  if (decoratorTypes['property'] > 0) patterns.push(`${decoratorTypes['property']} propert${decoratorTypes['property'] > 1 ? 'ies' : 'y'}`);

  if (patterns.length > 0) {
    description += `Decorator patterns found: ${patterns.join(', ')}.`;
  }

  return description || "The codebase has a straightforward structure with functions calling each other directly.";
}

/**
 * Categorize a decorator string
 */
function categorizeDecorator(decorator) {
  const d = decorator.toLowerCase();
  if (d.includes('route') || d.includes('get') || d.includes('post') || d.includes('put') || d.includes('delete')) {
    return 'route';
  }
  if (d.includes('staticmethod')) return 'static';
  if (d.includes('classmethod')) return 'class';
  if (d.includes('property')) return 'property';
  return 'other';
}

/**
 * Generate complexity section
 */
function generateComplexity(functions) {
  if (functions.length === 0) {
    return "No functions available to analyze complexity.";
  }

  // Categorize functions by complexity
  const simple = functions.filter(f => (f.complexity || 1) <= 5);
  const moderate = functions.filter(f => (f.complexity || 1) > 5 && (f.complexity || 1) <= 10);
  const high = functions.filter(f => (f.complexity || 1) > 10);

  let description = "";

  if (high.length > 0) {
    const highNames = high.slice(0, 3).map(f =>
      `${f.name} (complexity ${f.complexity}, line ${f.line_number})`
    );
    description += `${high.length} function${high.length !== 1 ? 's have' : ' has'} high complexity (>10): ${highNames.join(', ')}${high.length > 3 ? '...' : ''}. ` +
      `Consider breaking ${high.length === 1 ? 'it' : 'them'} into smaller, focused functions. `;
  }

  if (moderate.length > 0) {
    description += `${moderate.length} function${moderate.length !== 1 ? 's have' : ' has'} moderate complexity (6-10). `;
  }

  if (simple.length > 0 && high.length === 0 && moderate.length === 0) {
    description += `All ${simple.length} function${simple.length !== 1 ? 's have' : ' has'} low complexity (≤5). Your code is well-structured and should be easy to test and maintain.`;
  } else if (simple.length > 0) {
    description += `${simple.length} function${simple.length !== 1 ? 's are' : ' is'} simple (≤5) and easy to maintain.`;
  }

  return description || "Complexity analysis not available.";
}

/**
 * Generate potential issues section
 */
function generatePotentialIssues(stats, functions) {
  const issues = [];

  // Check circular dependencies
  const circularDeps = stats.circular_dependencies || [];
  if (circularDeps.length > 0) {
    issues.push(
      `${circularDeps.length} circular dependenc${circularDeps.length === 1 ? 'y was' : 'ies were'} detected. ` +
      `This means some functions call each other in a cycle, which could cause infinite recursion or make the code harder to understand.`
    );
  }

  // Check orphan functions
  const orphans = stats.orphan_functions || [];
  if (orphans.length > 0) {
    const orphanNames = orphans.slice(0, 3).map(id => {
      const func = functions.find(f => f.id === id);
      return func ? func.name : id.split('_').pop();
    });

    issues.push(
      `${orphans.length} orphan function${orphans.length !== 1 ? 's were' : ' was'} found (${orphanNames.join(', ')}${orphans.length > 3 ? '...' : ''}). ` +
      `These are defined but never called from within the analyzed code. They might be unused, or called from external modules.`
    );
  }

  // Check for high complexity functions
  const highComplexity = functions.filter(f => (f.complexity || 1) > 15);
  if (highComplexity.length > 0) {
    issues.push(
      `${highComplexity.length} function${highComplexity.length !== 1 ? 's have' : ' has'} very high complexity (>15), ` +
      `which may indicate code that's difficult to test and prone to bugs.`
    );
  }

  if (issues.length === 0) {
    return "No significant issues detected. Your code structure appears clean with no circular dependencies and all functions seem to be in use.";
  }

  return issues.join(' ');
}

/**
 * Generate call chains section
 */
function generateCallChains(stats, calls, functions) {
  const maxDepth = stats.max_call_depth || 0;

  if (maxDepth === 0) {
    return "No function call chains detected. Functions appear to operate independently.";
  }

  // Count conditional vs direct calls
  const conditionalCalls = calls.filter(c => c.is_conditional).length;
  const loopCalls = calls.filter(c => c.is_loop).length;
  const directCalls = calls.length - conditionalCalls - loopCalls;

  let description = `Your deepest call chain is ${maxDepth} level${maxDepth !== 1 ? 's' : ''} deep. `;

  if (maxDepth > 5) {
    description += `This relatively deep nesting might make debugging more challenging. `;
  } else if (maxDepth <= 2) {
    description += `This shallow structure keeps the code easy to follow. `;
  }

  // Add call type breakdown
  const callBreakdown = [];
  if (directCalls > 0) callBreakdown.push(`${directCalls} direct`);
  if (conditionalCalls > 0) callBreakdown.push(`${conditionalCalls} conditional`);
  if (loopCalls > 0) callBreakdown.push(`${loopCalls} in loops`);

  if (callBreakdown.length > 0) {
    description += `Call types: ${callBreakdown.join(', ')}.`;
  }

  return description;
}

/**
 * Check if analysis is from AI or fallback
 * @param {Object} analysis - The analysis object
 * @returns {boolean} True if this appears to be AI-generated
 */
export function isAIAnalysis(analysis) {
  // AI analysis typically has more detailed, varied content
  // This is a heuristic check
  if (!analysis) return false;

  const overview = analysis.overview || '';

  // Fallback uses specific template phrases
  const fallbackPhrases = [
    "No code data available",
    "No functions were detected",
    "You've uploaded a"
  ];

  return !fallbackPhrases.some(phrase => overview.includes(phrase));
}

export default generateBasicAnalysis;
