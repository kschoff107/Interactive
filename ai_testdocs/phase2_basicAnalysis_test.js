/**
 * Phase 2 Test: basicAnalysis.js Fallback System
 *
 * Run with: node phase2_basicAnalysis_test.js
 * From: C:\Claude\Interactive\ai_testdocs
 */

// Since we're in Node.js, we need to handle ES modules
const fs = require('fs');
const path = require('path');

// Read the source file and evaluate it
const sourceFile = path.join(__dirname, '..', 'frontend', 'src', 'utils', 'basicAnalysis.js');
const sourceCode = fs.readFileSync(sourceFile, 'utf-8');

// Convert ES module syntax to CommonJS for testing
const convertedCode = sourceCode
  .replace(/export function /g, 'function ')
  .replace(/export default .+;?/, '')
  .replace(/export \{ .+ \};?/, '');

// Execute the code to get the functions
eval(convertedCode);

// Test data - simulates real flowData from the parser
const mockFlowData = {
  analysis_type: 'runtime_flow',
  version: '1.0',
  project_path: '/test/project',
  modules: [
    { id: 'module_app', name: 'app', file_path: '/test/app.py', function_count: 5 },
    { id: 'module_utils', name: 'utils', file_path: '/test/utils.py', function_count: 3 }
  ],
  functions: [
    {
      id: 'func_app_handle_login_10',
      type: 'function',
      name: 'handle_login',
      qualified_name: 'app.handle_login',
      module: 'app',
      file_path: '/test/app.py',
      line_number: 10,
      end_line: 25,
      parameters: ['request'],
      decorators: ['@app.post'],
      is_async: false,
      is_method: false,
      class_name: null,
      docstring: 'Handle user login',
      complexity: 5
    },
    {
      id: 'func_app_validate_user_30',
      type: 'function',
      name: 'validate_user',
      qualified_name: 'app.validate_user',
      module: 'app',
      file_path: '/test/app.py',
      line_number: 30,
      end_line: 50,
      parameters: ['username', 'password'],
      decorators: [],
      is_async: false,
      is_method: false,
      class_name: null,
      docstring: null,
      complexity: 12
    },
    {
      id: 'func_app_process_data_60',
      type: 'function',
      name: 'process_data',
      qualified_name: 'app.process_data',
      module: 'app',
      file_path: '/test/app.py',
      line_number: 60,
      end_line: 80,
      parameters: ['data'],
      decorators: ['@staticmethod'],
      is_async: true,
      is_method: false,
      class_name: null,
      docstring: null,
      complexity: 3
    },
    {
      id: 'func_utils_helper_5',
      type: 'function',
      name: 'helper',
      qualified_name: 'utils.helper',
      module: 'utils',
      file_path: '/test/utils.py',
      line_number: 5,
      end_line: 15,
      parameters: [],
      decorators: [],
      is_async: false,
      is_method: false,
      class_name: null,
      docstring: null,
      complexity: 2
    },
    {
      id: 'func_app_main_100',
      type: 'function',
      name: 'main',
      qualified_name: 'app.main',
      module: 'app',
      file_path: '/test/app.py',
      line_number: 100,
      end_line: 110,
      parameters: [],
      decorators: [],
      is_async: false,
      is_method: false,
      class_name: null,
      docstring: null,
      complexity: 1
    }
  ],
  calls: [
    {
      id: 'call_1',
      type: 'call',
      caller_id: 'func_app_handle_login_10',
      callee_id: 'func_app_validate_user_30',
      callee_name: 'validate_user',
      file_path: '/test/app.py',
      line_number: 15,
      is_conditional: false,
      is_loop: false,
      call_type: 'direct'
    },
    {
      id: 'call_2',
      type: 'call',
      caller_id: 'func_app_validate_user_30',
      callee_id: 'func_utils_helper_5',
      callee_name: 'helper',
      file_path: '/test/app.py',
      line_number: 35,
      is_conditional: true,
      is_loop: false,
      call_type: 'direct'
    },
    {
      id: 'call_3',
      type: 'call',
      caller_id: 'func_app_main_100',
      callee_id: 'func_app_handle_login_10',
      callee_name: 'handle_login',
      file_path: '/test/app.py',
      line_number: 105,
      is_conditional: false,
      is_loop: true,
      call_type: 'direct'
    }
  ],
  control_flows: [],
  entry_points: [
    {
      id: 'entry_func_app_handle_login_10',
      type: 'route',
      function_id: 'func_app_handle_login_10',
      decorator: '@app.post',
      file_path: '/test/app.py',
      line_number: 10
    },
    {
      id: 'entry_func_app_main_100',
      type: 'main_function',
      function_id: 'func_app_main_100',
      file_path: '/test/app.py',
      line_number: 100
    }
  ],
  statistics: {
    total_functions: 5,
    total_calls: 3,
    total_control_flows: 0,
    max_call_depth: 3,
    circular_dependencies: [],
    orphan_functions: ['func_app_process_data_60']
  }
};

// Empty/minimal flow data for edge case testing
const emptyFlowData = null;

const minimalFlowData = {
  statistics: {},
  functions: [],
  entry_points: [],
  modules: [],
  calls: []
};

// Run tests
console.log('='.repeat(60));
console.log('Phase 2 Test: basicAnalysis.js Fallback System');
console.log('='.repeat(60));
console.log('');

let passed = 0;
let failed = 0;

function test(name, fn) {
  try {
    fn();
    console.log(`✓ ${name}`);
    passed++;
  } catch (error) {
    console.log(`✗ ${name}`);
    console.log(`  Error: ${error.message}`);
    failed++;
  }
}

function assert(condition, message) {
  if (!condition) {
    throw new Error(message || 'Assertion failed');
  }
}

// Test 1: Function exists
test('generateBasicAnalysis function exists', () => {
  assert(typeof generateBasicAnalysis === 'function', 'Function should exist');
});

// Test 2: Returns object with all 6 sections
test('Returns object with all 6 required sections', () => {
  const result = generateBasicAnalysis(mockFlowData);
  assert(result.overview, 'Should have overview');
  assert(result.how_it_starts, 'Should have how_it_starts');
  assert(result.architecture, 'Should have architecture');
  assert(result.complexity, 'Should have complexity');
  assert(result.potential_issues, 'Should have potential_issues');
  assert(result.call_chains, 'Should have call_chains');
});

// Test 3: Handles null input
test('Handles null flowData gracefully', () => {
  const result = generateBasicAnalysis(null);
  assert(result.overview.includes('No code data'), 'Should indicate no data');
  assert(typeof result.how_it_starts === 'string', 'Should return strings');
});

// Test 4: Handles empty flowData
test('Handles empty/minimal flowData', () => {
  const result = generateBasicAnalysis(minimalFlowData);
  assert(typeof result.overview === 'string', 'Should return string overview');
  assert(result.overview.length > 0, 'Overview should not be empty');
});

// Test 5: Detects Flask application
test('Detects Flask web application from decorators', () => {
  const result = generateBasicAnalysis(mockFlowData);
  assert(result.overview.includes('Flask') || result.overview.includes('web'),
    'Should detect Flask/web application');
});

// Test 6: Reports correct function count
test('Reports correct function count', () => {
  const result = generateBasicAnalysis(mockFlowData);
  assert(result.overview.includes('5 function'), 'Should report 5 functions');
});

// Test 7: Reports entry points
test('Reports entry points correctly', () => {
  const result = generateBasicAnalysis(mockFlowData);
  assert(result.how_it_starts.includes('2 entry point'), 'Should report 2 entry points');
});

// Test 8: Identifies high complexity functions
test('Identifies high complexity functions', () => {
  const result = generateBasicAnalysis(mockFlowData);
  assert(result.complexity.includes('validate_user') || result.complexity.includes('complexity'),
    'Should mention high complexity function');
});

// Test 9: Reports orphan functions
test('Reports orphan functions in potential issues', () => {
  const result = generateBasicAnalysis(mockFlowData);
  assert(result.potential_issues.includes('orphan') || result.potential_issues.includes('process_data'),
    'Should mention orphan functions');
});

// Test 10: Reports call depth
test('Reports call chain depth', () => {
  const result = generateBasicAnalysis(mockFlowData);
  assert(result.call_chains.includes('3 level'), 'Should report max depth of 3');
});

// Test 11: Async functions mentioned
test('Mentions async functions in overview', () => {
  const result = generateBasicAnalysis(mockFlowData);
  assert(result.overview.includes('async') || result.overview.includes('concurrent'),
    'Should mention async functions');
});

// Test 12: isAIAnalysis helper works
test('isAIAnalysis returns false for fallback content', () => {
  const result = generateBasicAnalysis(mockFlowData);
  const isAI = isAIAnalysis(result);
  assert(isAI === false, 'Should identify as fallback content');
});

// Summary
console.log('');
console.log('='.repeat(60));
console.log(`Results: ${passed} passed, ${failed} failed`);
console.log('='.repeat(60));

if (failed > 0) {
  process.exit(1);
}

// Print sample output
console.log('');
console.log('Sample Output (with mock data):');
console.log('-'.repeat(60));
const sampleOutput = generateBasicAnalysis(mockFlowData);
Object.entries(sampleOutput).forEach(([key, value]) => {
  console.log(`\n[${key.toUpperCase()}]`);
  console.log(value);
});
