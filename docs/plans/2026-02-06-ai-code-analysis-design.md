# AI-Powered Code Analysis Feature Design

**Date:** 2026-02-06
**Status:** Design Approved
**Feature:** "Analyze My Code" tab with AI-generated narrative explanations

## Overview

Enhance the existing "Decode This" InsightGuide with a second tab that provides AI-generated, educational narratives explaining the user's specific runtime flow. Instead of generic "how to read this" content, provide personalized insights like a teacher walking a student through their code.

## User Vision

"A well thought out explanation of what is actually happening with the code. Something like a teacher teaching a student and walking them through what they are seeing and why."

## Architecture

### System Flow

1. **Upload Phase** (Existing)
   - User uploads Python files
   - Backend analyzes and stores `flowData` with functions, calls, statistics

2. **Guide Access** (Existing)
   - User clicks "🔍 Decode This" button
   - Modal opens showing "Understanding Runtime Flow" tab (generic educational content)

3. **Analysis Generation** (New)
   - User clicks "Analyze My Code" tab
   - Frontend checks cache via API call
   - **If cached:** Display immediately
   - **If not cached:**
     - Show animated progress with steps
     - Backend sends `flowData` to Claude API
     - Claude generates 6-section narrative
     - Backend stores in database with 30-day expiration
     - Return analysis to frontend
     - Display narrative sections

### Key Components

- **Frontend:** Enhanced `InsightGuide.jsx` with tabs, loading states, error handling, fallback
- **Backend:** New `/api/projects/{id}/analyze-code` endpoint orchestrating Claude API
- **Database:** New `code_analysis` table for caching generated narratives
- **AI Service:** Claude 3.5 Sonnet integration for narrative generation
- **Fallback:** Template-based basic insights when AI unavailable

## Database Schema

### New Table: `code_analysis`

```sql
CREATE TABLE code_analysis (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    file_hash VARCHAR(64) NOT NULL,  -- SHA256 of uploaded files
    analysis_type VARCHAR(50) DEFAULT 'runtime_flow',

    -- Generated content
    narrative_json TEXT NOT NULL,  -- Stores the 6 sections as JSON

    -- Metadata
    model_used VARCHAR(50),  -- e.g., "claude-3-5-sonnet-20241022"
    tokens_used INTEGER,
    generation_time_ms INTEGER,

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,  -- Auto-expire after 30 days

    -- Foreign key and constraints
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    UNIQUE(project_id, file_hash)
);

CREATE INDEX idx_code_analysis_lookup ON code_analysis(project_id, file_hash);
CREATE INDEX idx_code_analysis_expires ON code_analysis(expires_at);
```

### JSON Structure in `narrative_json`

```json
{
  "overview": "You've uploaded a Flask web application...",
  "how_it_starts": "Your application has 3 entry points...",
  "architecture": "The hub of your application is...",
  "complexity": "Two functions need attention...",
  "potential_issues": "There's a circular dependency...",
  "call_chains": "The deepest execution path is..."
}
```

## Backend API

### New Endpoint: `POST /api/projects/{project_id}/analyze-code`

**Request:**
```json
{
  "force_regenerate": false  // Optional: bypass cache
}
```

**Response (Success):**
```json
{
  "status": "success",
  "analysis": {
    "overview": "You've uploaded a Flask web application...",
    "how_it_starts": "Your application has 3 entry points...",
    "architecture": "The hub of your application is...",
    "complexity": "Two functions need attention...",
    "potential_issues": "There's a circular dependency...",
    "call_chains": "The deepest execution path is..."
  },
  "cached": true,
  "generated_at": "2024-01-15T10:30:00Z"
}
```

**Response (Error):**
```json
{
  "status": "error",
  "error": "Rate limit exceeded. Please try again in 60 seconds.",
  "retry_after": 60
}
```

**Backend Logic:**
1. Validate project exists and has flowData
2. Calculate file hash from uploaded files
3. Query database for cached analysis (project_id + file_hash)
4. If cached and not expired → Return immediately
5. If not cached or force_regenerate:
   - Call `generate_code_analysis()` service function
   - Store result in database with 30-day expiration
   - Return analysis to frontend

## AI Integration - Claude API

### Model Configuration

- **Model:** `claude-3-5-sonnet-20241022`
- **Temperature:** 0.3 (consistent, focused responses)
- **Max Tokens:** 4000
- **SDK:** Official Anthropic Python SDK

### Prompt Structure

**System Prompt:**
```
You are an expert code educator helping students understand their Python code's runtime behavior. Analyze the provided runtime flow data and write clear, friendly explanations as if teaching a student. Focus on insights, patterns, and learning opportunities. Be specific with function names and line numbers.
```

**User Prompt:**
```
Analyze this Python code's runtime flow and create educational explanations for these sections:

1. OVERVIEW (100 words): High-level summary of what this codebase does
2. HOW YOUR APPLICATION STARTS (150 words): Explain entry points and trace typical execution
3. THE ARCHITECTURE (150 words): Hub functions, key modules, decorator patterns
4. COMPLEXITY ANALYSIS (150 words): High-complexity functions with refactoring suggestions
5. POTENTIAL ISSUES (150 words): Circular dependencies, orphan functions, security notes
6. CALL CHAIN EXAMPLES (100 words): Show deepest/interesting execution paths

Runtime Flow Data:
{flowData JSON with functions, calls, statistics}

Return ONLY valid JSON:
{
  "overview": "...",
  "how_it_starts": "...",
  "architecture": "...",
  "complexity": "...",
  "potential_issues": "...",
  "call_chains": "..."
}
```

### Narrative Sections Explained

Each section serves a specific educational purpose:

1. **Overview (100 words)**
   - High-level summary of what the codebase does
   - File/module count, primary purpose
   - Example: "You've uploaded a Flask web application with 23 functions across 3 modules. This appears to be a user management system..."

2. **How Your Application Starts (150 words)**
   - Entry points explained with actual function names
   - Trace typical execution path from entry to completion
   - Example: "Your app has 3 entry points. When a user hits `/login`, the `handle_login()` function validates credentials, calls `authenticate_user()`, then..."

3. **The Architecture (150 words)**
   - Hub functions (most frequently called)
   - Key modules and their roles
   - Decorator patterns (Flask routes, async, static methods)
   - Example: "The hub of your application is `process_user_data()` - called by 8 different functions..."

4. **Complexity Analysis (150 words)**
   - High-complexity functions (complexity > 10) with line numbers
   - Why complexity matters for those specific functions
   - Gentle, specific refactoring suggestions
   - Example: "`authenticate_user()` at line 45 has complexity 15 due to nested validation logic. Consider extracting..."

5. **Potential Issues (150 words)**
   - Circular dependencies with function names explained
   - Orphan functions - whether to keep or remove
   - Security considerations if applicable
   - Example: "There's a circular dependency between `validate_data()` and `sanitize_input()`. This could cause..."

6. **Call Chain Examples (100 words)**
   - Deepest call chain shown as narrative
   - Interesting execution paths
   - Example: "Your deepest call chain is 7 levels: `main() → process() → validate() → check_format() → ...`"

## Frontend Implementation

### Enhanced `InsightGuide.jsx`

**New State Variables:**
```jsx
const [activeTab, setActiveTab] = useState('guide');
const [analysis, setAnalysis] = useState(null);
const [loading, setLoading] = useState(false);
const [error, setError] = useState(null);
const [loadingStep, setLoadingStep] = useState(0);
```

**Tab Structure:**
```jsx
<div className="insight-guide-tabs">
  <button
    className={activeTab === 'guide' ? 'active' : ''}
    onClick={() => setActiveTab('guide')}
  >
    Understanding Runtime Flow
  </button>
  <button
    className={activeTab === 'analyze' ? 'active' : ''}
    onClick={() => handleAnalyzeClick()}
  >
    Analyze My Code
  </button>
</div>

<div className="insight-guide-content">
  {activeTab === 'guide' ? (
    <GuideContent />
  ) : (
    <AnalysisContent
      analysis={analysis}
      loading={loading}
      error={error}
      loadingStep={loadingStep}
    />
  )}
</div>
```

### Loading State - Animated Progress

**Loading Steps (Simulated Progress):**
```jsx
const loadingSteps = [
  { label: 'Tracing function calls', duration: 2000 },
  { label: 'Identifying entry points', duration: 2000 },
  { label: 'Analyzing complexity patterns', duration: 3000 },
  { label: 'Detecting potential issues', duration: 2000 },
  { label: 'Generating insights', duration: 5000 }
];
```

**Visual Display:**
```
┌─────────────────────────────────────────┐
│ 🔍 Analyzing Your Code...               │
│                                         │
│ ✓ Tracing function calls                │
│ ✓ Identifying entry points              │
│ ⋯ Analyzing complexity patterns         │
│   Detecting potential issues            │
│   Generating insights                   │
│                                         │
│ [Progress bar ████████░░░░░░] 60%       │
└─────────────────────────────────────────┘
```

- ✓ = Completed step (green checkmark)
- ⋯ = Current step (animated spinner)
- Gray text = Upcoming steps
- Progress bar updates based on elapsed time

### Error Handling - Graceful Fallback

**Error Display:**
```
┌─────────────────────────────────────────┐
│ ⚠️ Analysis Generation Failed           │
│                                         │
│ We couldn't generate the AI analysis.   │
│ This might be due to:                   │
│ • API rate limits                       │
│ • Network issues                        │
│ • Service temporarily unavailable       │
│                                         │
│ [Retry Analysis]  [Use Basic Insights]  │
└─────────────────────────────────────────┘
```

**Actions:**
- **Retry Analysis** → Attempt API call again
- **Use Basic Insights** → Fall back to template-based analysis

### Basic Fallback System

When Claude API fails, provide template-based insights using `flowData`:

```javascript
function generateBasicAnalysis(flowData) {
  const stats = flowData.statistics;
  const functions = flowData.functions || [];
  const entryPoints = functions.filter(f => f.is_entry_point);
  const highComplexity = functions.filter(f => f.complexity > 10);
  const orphans = stats.orphan_functions || [];

  return {
    overview: `You've uploaded ${stats.total_functions} functions with ${stats.total_calls} function calls. ${entryPoints.length} entry points detected.`,

    how_it_starts: `Entry points: ${entryPoints.map(f => f.name).join(', ')}. Max call depth: ${stats.max_call_depth}.`,

    architecture: `Key functions and their relationships. Most connected functions form the hub of your application.`,

    complexity: highComplexity.length > 0
      ? `${highComplexity.length} functions have high complexity (>10): ${highComplexity.map(f => `${f.name} (${f.complexity})`).join(', ')}`
      : `All functions have manageable complexity (≤10).`,

    potential_issues: stats.circular_dependencies?.length > 0
      ? `${stats.circular_dependencies.length} circular dependencies detected. ${orphans.length} orphan functions found that are never called.`
      : `No circular dependencies detected. ${orphans.length} orphan functions found.`,

    call_chains: `Maximum call depth is ${stats.max_call_depth} levels. This represents the deepest chain of function calls.`
  };
}
```

**Visual Indicator:**
- Show badge: **"AI Analysis"** vs **"Basic Insights"**
- User knows which mode they're viewing

## Configuration

### Environment Variables

```bash
# .env file
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxx
ANTHROPIC_MODEL=claude-3-5-sonnet-20241022
ANTHROPIC_MAX_TOKENS=4000
ANTHROPIC_TEMPERATURE=0.3

# Optional settings
ANALYSIS_RATE_LIMIT=10      # Max analyses per hour per project
ANALYSIS_CACHE_DAYS=30       # Days before cache expires
```

### Backend Configuration

```python
# config.py
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')
    ANTHROPIC_MODEL = os.getenv('ANTHROPIC_MODEL', 'claude-3-5-sonnet-20241022')
    ANTHROPIC_MAX_TOKENS = int(os.getenv('ANTHROPIC_MAX_TOKENS', 4000))
    ANTHROPIC_TEMPERATURE = float(os.getenv('ANTHROPIC_TEMPERATURE', 0.3))
    ANALYSIS_CACHE_DAYS = int(os.getenv('ANALYSIS_CACHE_DAYS', 30))

    @staticmethod
    def validate():
        if not Config.ANTHROPIC_API_KEY:
            raise ValueError("ANTHROPIC_API_KEY not configured")
```

### Error Handling

- **Missing API Key:** Return error: "AI analysis not configured. Contact administrator."
- **Invalid API Key:** Return error: "AI service authentication failed."
- **Rate Limit:** Return error with `retry_after` seconds
- **All Errors:** Frontend automatically falls back to basic insights

### Installation

```bash
# Backend dependencies
pip install anthropic  # Official Anthropic Python SDK
```

## File Structure

### New Files to Create

**Backend:**
```
backend/
├── services/
│   └── code_analysis_service.py     # Claude API integration and prompt management
├── routes/
│   └── analysis_routes.py           # /analyze-code endpoint
├── models/
│   └── code_analysis.py             # SQLAlchemy model for code_analysis table
└── migrations/
    └── add_code_analysis_table.sql  # Schema migration SQL
```

**Frontend:**
```
frontend/src/
├── components/project/
│   ├── InsightGuide.jsx             # MODIFY: Add tab switching
│   ├── InsightGuide.css             # MODIFY: Add tab styles, loading animations
│   ├── AnalysisTab.jsx              # NEW: Analysis content display
│   └── LoadingAnalysis.jsx          # NEW: Animated loading component
└── utils/
    └── basicAnalysis.js             # NEW: Fallback template generator
```

### Files to Modify

1. **`backend/routes/__init__.py`** - Register analysis routes
2. **`frontend/src/components/project/InsightGuide.jsx`** - Add tabs, API integration
3. **`frontend/src/components/project/InsightGuide.css`** - Tab styling, animations
4. **Database** - Run migration to create `code_analysis` table

## Implementation Order

### Phase 1: Backend Foundation
1. Create database migration and run it
2. Create `code_analysis.py` model
3. Install Anthropic SDK: `pip install anthropic`
4. Create `code_analysis_service.py` with Claude integration
5. Create `analysis_routes.py` endpoint
6. Test endpoint with curl/Postman

### Phase 2: Frontend Fallback
7. Create `basicAnalysis.js` utility
8. Test fallback system with mock data
9. Ensure fallback works before AI integration

### Phase 3: Frontend UI
10. Modify `InsightGuide.jsx` - add tab structure
11. Create `LoadingAnalysis.jsx` component
12. Create `AnalysisTab.jsx` component
13. Update `InsightGuide.css` with tab styles

### Phase 4: Integration
14. Connect frontend to backend API
15. Implement loading states and error handling
16. Test end-to-end flow

### Phase 5: Polish & Deploy
17. Add retry logic and rate limiting
18. Test edge cases (no data, large files, API failures)
19. Add API key to production environment
20. Deploy and monitor

## Success Criteria

✅ Users can click "Analyze My Code" tab
✅ AI generates narrative explanations in 6 sections
✅ Loading shows animated progress with steps
✅ Analysis cached for 30 days (instant on repeat views)
✅ Graceful fallback to basic insights when AI fails
✅ Clear error messages with retry option
✅ Educational, narrative tone like "teacher to student"
✅ Specific function names, line numbers, and insights
✅ Works across all screen sizes (responsive)

## Future Enhancements

- **Regenerate Button:** Allow users to force fresh analysis
- **Export Analysis:** Download as PDF or markdown
- **Streaming Results:** Show sections as they generate (real-time)
- **Code Snippets:** Include actual code excerpts in explanations
- **Comparison Mode:** Compare analysis across different versions
- **Multi-Language Support:** Expand beyond Python to JavaScript, etc.
- **Custom Insights:** Let users ask specific questions about their code
- **Team Sharing:** Share analysis with team members

## Cost Estimation

**Per Analysis:**
- Average flowData size: ~10-50 KB → ~5,000 tokens input
- Generated narrative: ~800 words → ~1,000 tokens output
- **Total:** ~6,000 tokens per analysis

**Pricing (Claude 3.5 Sonnet):**
- Input: $3 per 1M tokens
- Output: $15 per 1M tokens
- **Cost per analysis:** ~$0.03 (3 cents)

**With Caching:**
- 30-day cache means most users see analysis instantly (free)
- Only first generation costs money
- Expected cost: **<$5/month** for typical usage

## Security Considerations

1. **API Key Protection:** Store in environment variables, never commit
2. **Rate Limiting:** Prevent abuse (10 analyses per hour per project)
3. **Data Privacy:** User code sent to Anthropic API (review privacy policy)
4. **Input Validation:** Sanitize flowData before sending to Claude
5. **Error Messages:** Don't expose internal errors to users

## Testing Strategy

1. **Unit Tests:** Test `basicAnalysis.js` fallback generator
2. **Integration Tests:** Test API endpoint with mock Claude responses
3. **E2E Tests:** Test full flow from tab click to display
4. **Error Scenarios:** Test API failures, rate limits, missing data
5. **Performance:** Test with large codebases (100+ functions)
6. **Cost Monitoring:** Track token usage and costs

---

**Design Approved:** 2026-02-06
**Ready for Implementation:** Yes
