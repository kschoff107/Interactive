import json
import hashlib
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

import anthropic
from config import Config
from database import get_connection
from models import CodeAnalysis


class CodeAnalysisError(Exception):
    """Custom exception for code analysis errors"""
    def __init__(self, message: str, retry_after: Optional[int] = None):
        super().__init__(message)
        self.retry_after = retry_after


class CodeAnalysisService:
    """Service for generating AI-powered code analysis using Claude"""

    # Runtime Flow prompts
    SYSTEM_PROMPT = """You are an expert code educator helping students understand their Python code's runtime behavior. Analyze the provided runtime flow data and write clear, friendly explanations as if teaching a student. Focus on insights, patterns, and learning opportunities. Be specific with function names and line numbers."""

    USER_PROMPT_TEMPLATE = """Analyze this Python code's runtime flow and create educational explanations for these sections:

1. OVERVIEW (100 words): High-level summary of what this codebase does
2. HOW YOUR APPLICATION STARTS (150 words): Explain entry points and trace typical execution
3. THE ARCHITECTURE (150 words): Hub functions, key modules, decorator patterns
4. COMPLEXITY ANALYSIS (150 words): High-complexity functions with refactoring suggestions
5. POTENTIAL ISSUES (150 words): Circular dependencies, orphan functions, security notes
6. CALL CHAIN EXAMPLES (100 words): Show deepest/interesting execution paths

Runtime Flow Data:
{flow_data}

Return ONLY valid JSON with no additional text:
{{
  "overview": "...",
  "how_it_starts": "...",
  "architecture": "...",
  "complexity": "...",
  "potential_issues": "...",
  "call_chains": "..."
}}"""

    # API Routes prompts
    API_ROUTES_SYSTEM_PROMPT = """You are an expert API architect helping developers understand their Flask API structure. Analyze the provided API routes data and write clear, insightful explanations. Focus on REST design patterns, security considerations, and architectural best practices. Be specific with route paths, methods, and blueprint names."""

    API_ROUTES_PROMPT_TEMPLATE = """Analyze this Flask API's route structure and create educational explanations for these sections:

1. API OVERVIEW (100 words): High-level summary of what this API does, its main purpose and capabilities
2. ROUTE ORGANIZATION (150 words): How routes are organized into blueprints, URL patterns, and naming conventions
3. HTTP METHODS ANALYSIS (150 words): How different HTTP methods are used (GET/POST/PUT/DELETE), RESTful design adherence
4. SECURITY REVIEW (150 words): Protected vs unprotected routes, authentication patterns, potential security concerns
5. API DESIGN PATTERNS (150 words): Common patterns observed, consistency in design, areas for improvement
6. ENDPOINT EXAMPLES (100 words): Highlight interesting or important endpoints and what they do

API Routes Data:
{routes_data}

Return ONLY valid JSON with no additional text:
{{
  "overview": "...",
  "route_organization": "...",
  "http_methods": "...",
  "security_review": "...",
  "design_patterns": "...",
  "endpoint_examples": "..."
}}"""

    def __init__(self):
        self.api_key = Config.ANTHROPIC_API_KEY
        self.model = Config.ANTHROPIC_MODEL
        self.max_tokens = Config.ANTHROPIC_MAX_TOKENS
        self.temperature = Config.ANTHROPIC_TEMPERATURE
        self.cache_days = Config.ANALYSIS_CACHE_DAYS

        if self.api_key:
            self.client = anthropic.Anthropic(api_key=self.api_key)
        else:
            self.client = None

    def _calculate_file_hash(self, flow_data: Dict) -> str:
        """Calculate SHA256 hash of flow data for cache lookup"""
        data_str = json.dumps(flow_data, sort_keys=True)
        return hashlib.sha256(data_str.encode()).hexdigest()

    def _get_cached_analysis(self, project_id: int, file_hash: str) -> Optional[CodeAnalysis]:
        """Check if a valid cached analysis exists"""
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT id, project_id, file_hash, analysis_type, narrative_json,
                       model_used, tokens_used, generation_time_ms, created_at, expires_at
                FROM code_analysis
                WHERE project_id = %s AND file_hash = %s
                  AND (expires_at IS NULL OR expires_at > %s)
            """, (project_id, file_hash, datetime.utcnow()))
            row = cur.fetchone()

            if row:
                return CodeAnalysis(**row)
            return None

    def _save_analysis(self, project_id: int, file_hash: str, narrative: Dict,
                       model_used: str, tokens_used: int, generation_time_ms: int) -> CodeAnalysis:
        """Save analysis to database"""
        narrative_json = json.dumps(narrative)
        expires_at = datetime.utcnow() + timedelta(days=self.cache_days)

        with get_connection() as conn:
            cur = conn.cursor()

            # Use UPSERT pattern for PostgreSQL
            cur.execute("""
                INSERT INTO code_analysis
                    (project_id, file_hash, analysis_type, narrative_json,
                     model_used, tokens_used, generation_time_ms, created_at, expires_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (project_id, file_hash)
                DO UPDATE SET
                    narrative_json = EXCLUDED.narrative_json,
                    model_used = EXCLUDED.model_used,
                    tokens_used = EXCLUDED.tokens_used,
                    generation_time_ms = EXCLUDED.generation_time_ms,
                    created_at = EXCLUDED.created_at,
                    expires_at = EXCLUDED.expires_at
                RETURNING id, project_id, file_hash, analysis_type, narrative_json,
                          model_used, tokens_used, generation_time_ms, created_at, expires_at
            """, (project_id, file_hash, 'runtime_flow', narrative_json,
                  model_used, tokens_used, generation_time_ms, datetime.utcnow(), expires_at))

            row = cur.fetchone()
            return CodeAnalysis(**row)

    def _call_claude_api(self, flow_data: Dict) -> tuple[Dict, int]:
        """Call Claude API and return parsed narrative with token count"""
        if not self.client:
            raise CodeAnalysisError("AI analysis not configured. ANTHROPIC_API_KEY is missing.")

        user_prompt = self.USER_PROMPT_TEMPLATE.format(
            flow_data=json.dumps(flow_data, indent=2)
        )

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                system=self.SYSTEM_PROMPT,
                messages=[
                    {"role": "user", "content": user_prompt}
                ]
            )

            # Extract text content
            content = response.content[0].text

            # Parse JSON from response
            try:
                narrative = json.loads(content)
            except json.JSONDecodeError:
                # Try to extract JSON from response if it has extra text
                import re
                json_match = re.search(r'\{[\s\S]*\}', content)
                if json_match:
                    narrative = json.loads(json_match.group())
                else:
                    raise CodeAnalysisError("Failed to parse AI response as JSON")

            # Validate required fields
            required_fields = ['overview', 'how_it_starts', 'architecture',
                               'complexity', 'potential_issues', 'call_chains']
            for field in required_fields:
                if field not in narrative:
                    narrative[field] = "Analysis not available for this section."

            total_tokens = response.usage.input_tokens + response.usage.output_tokens
            return narrative, total_tokens

        except anthropic.RateLimitError as e:
            raise CodeAnalysisError("Rate limit exceeded. Please try again later.", retry_after=60)
        except anthropic.AuthenticationError:
            raise CodeAnalysisError("AI service authentication failed. Check API key configuration.")
        except anthropic.APIError as e:
            raise CodeAnalysisError(f"AI service error: {str(e)}")

    def analyze(self, project_id: int, flow_data: Dict, force_regenerate: bool = False) -> Dict[str, Any]:
        """
        Generate or retrieve cached code analysis.

        Args:
            project_id: The project ID
            flow_data: The runtime flow data to analyze
            force_regenerate: If True, bypass cache and regenerate

        Returns:
            Dictionary with analysis results and metadata
        """
        file_hash = self._calculate_file_hash(flow_data)

        # Check cache first (unless force regenerate)
        if not force_regenerate:
            cached = self._get_cached_analysis(project_id, file_hash)
            if cached:
                return {
                    'status': 'success',
                    'analysis': cached.get_narrative(),
                    'cached': True,
                    'generated_at': cached.created_at.isoformat() if cached.created_at else None
                }

        # Generate new analysis
        start_time = time.time()
        narrative, tokens_used = self._call_claude_api(flow_data)
        generation_time_ms = int((time.time() - start_time) * 1000)

        # Save to cache
        saved = self._save_analysis(
            project_id=project_id,
            file_hash=file_hash,
            narrative=narrative,
            model_used=self.model,
            tokens_used=tokens_used,
            generation_time_ms=generation_time_ms
        )

        return {
            'status': 'success',
            'analysis': narrative,
            'cached': False,
            'generated_at': saved.created_at.isoformat() if saved.created_at else None
        }

    def is_configured(self) -> bool:
        """Check if the service is properly configured"""
        return self.client is not None

    def _call_claude_api_routes(self, routes_data: Dict) -> tuple[Dict, int]:
        """Call Claude API for API routes analysis and return parsed narrative with token count"""
        if not self.client:
            raise CodeAnalysisError("AI analysis not configured. ANTHROPIC_API_KEY is missing.")

        user_prompt = self.API_ROUTES_PROMPT_TEMPLATE.format(
            routes_data=json.dumps(routes_data, indent=2)
        )

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                system=self.API_ROUTES_SYSTEM_PROMPT,
                messages=[
                    {"role": "user", "content": user_prompt}
                ]
            )

            # Extract text content
            content = response.content[0].text

            # Parse JSON from response
            try:
                narrative = json.loads(content)
            except json.JSONDecodeError:
                # Try to extract JSON from response if it has extra text
                import re
                json_match = re.search(r'\{[\s\S]*\}', content)
                if json_match:
                    narrative = json.loads(json_match.group())
                else:
                    raise CodeAnalysisError("Failed to parse AI response as JSON")

            # Validate required fields
            required_fields = ['overview', 'route_organization', 'http_methods',
                               'security_review', 'design_patterns', 'endpoint_examples']
            for field in required_fields:
                if field not in narrative:
                    narrative[field] = "Analysis not available for this section."

            total_tokens = response.usage.input_tokens + response.usage.output_tokens
            return narrative, total_tokens

        except anthropic.RateLimitError as e:
            raise CodeAnalysisError("Rate limit exceeded. Please try again later.", retry_after=60)
        except anthropic.AuthenticationError:
            raise CodeAnalysisError("AI service authentication failed. Check API key configuration.")
        except anthropic.APIError as e:
            raise CodeAnalysisError(f"AI service error: {str(e)}")

    def _save_api_routes_analysis(self, project_id: int, file_hash: str, narrative: Dict,
                                   model_used: str, tokens_used: int, generation_time_ms: int) -> CodeAnalysis:
        """Save API routes analysis to database"""
        narrative_json = json.dumps(narrative)
        expires_at = datetime.utcnow() + timedelta(days=self.cache_days)

        with get_connection() as conn:
            cur = conn.cursor()

            # Use first 60 chars of hash + 'api' suffix to stay within VARCHAR(64)
            api_hash = file_hash[:60] + "_api"
            cur.execute("""
                INSERT INTO code_analysis
                    (project_id, file_hash, analysis_type, narrative_json,
                     model_used, tokens_used, generation_time_ms, created_at, expires_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (project_id, file_hash)
                DO UPDATE SET
                    narrative_json = EXCLUDED.narrative_json,
                    model_used = EXCLUDED.model_used,
                    tokens_used = EXCLUDED.tokens_used,
                    generation_time_ms = EXCLUDED.generation_time_ms,
                    created_at = EXCLUDED.created_at,
                    expires_at = EXCLUDED.expires_at
                RETURNING id, project_id, file_hash, analysis_type, narrative_json,
                          model_used, tokens_used, generation_time_ms, created_at, expires_at
            """, (project_id, api_hash, 'api_routes', narrative_json,
                  model_used, tokens_used, generation_time_ms, datetime.utcnow(), expires_at))

            row = cur.fetchone()
            return CodeAnalysis(**row)

    def _get_cached_api_routes_analysis(self, project_id: int, file_hash: str) -> Optional[CodeAnalysis]:
        """Check if a valid cached API routes analysis exists"""
        api_hash = file_hash[:60] + "_api"
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT id, project_id, file_hash, analysis_type, narrative_json,
                       model_used, tokens_used, generation_time_ms, created_at, expires_at
                FROM code_analysis
                WHERE project_id = %s AND file_hash = %s AND analysis_type = %s
                  AND (expires_at IS NULL OR expires_at > %s)
            """, (project_id, api_hash, 'api_routes', datetime.utcnow()))
            row = cur.fetchone()

            if row:
                return CodeAnalysis(**row)
            return None

    def analyze_api_routes(self, project_id: int, routes_data: Dict, force_regenerate: bool = False) -> Dict[str, Any]:
        """
        Generate or retrieve cached API routes analysis.

        Args:
            project_id: The project ID
            routes_data: The API routes data to analyze
            force_regenerate: If True, bypass cache and regenerate

        Returns:
            Dictionary with analysis results and metadata
        """
        file_hash = self._calculate_file_hash(routes_data)

        # Check cache first (unless force regenerate)
        if not force_regenerate:
            cached = self._get_cached_api_routes_analysis(project_id, file_hash)
            if cached:
                return {
                    'status': 'success',
                    'analysis': cached.get_narrative(),
                    'cached': True,
                    'generated_at': cached.created_at.isoformat() if cached.created_at else None
                }

        # Generate new analysis
        start_time = time.time()
        narrative, tokens_used = self._call_claude_api_routes(routes_data)
        generation_time_ms = int((time.time() - start_time) * 1000)

        # Save to cache
        saved = self._save_api_routes_analysis(
            project_id=project_id,
            file_hash=file_hash,
            narrative=narrative,
            model_used=self.model,
            tokens_used=tokens_used,
            generation_time_ms=generation_time_ms
        )

        return {
            'status': 'success',
            'analysis': narrative,
            'cached': False,
            'generated_at': saved.created_at.isoformat() if saved.created_at else None
        }
