import os
from typing import Tuple, Dict
from .sqlalchemy_parser import SQLAlchemyParser
from .sqlite_parser import SQLiteParser
from .runtime_flow_parser import RuntimeFlowParser

class UnsupportedFrameworkError(Exception):
    """Raised when framework is not supported"""
    pass

class ParserManager:
    """Manages detection and routing to appropriate parsers"""

    def detect_language_and_framework(self, project_path: str) -> Tuple[str, str]:
        """Detect language and framework from project files"""

        # Check for database files
        if self._has_database_files(project_path):
            return ('database', 'sqlite')

        # Check for Python projects
        if self._has_file(project_path, 'requirements.txt') or self._has_file(project_path, 'setup.py'):
            framework = self._detect_python_framework(project_path)
            return ('python', framework)

        # Check for Python files
        if self._has_python_files(project_path):
            framework = self._detect_python_framework(project_path)
            if framework != 'unknown':
                return ('python', framework)

        # Check for Node.js projects
        if self._has_file(project_path, 'package.json'):
            framework = self._detect_js_framework(project_path)
            return ('javascript', framework)

        return ('unknown', 'unknown')

    def parse_database_schema(self, project_path: str, language: str, framework: str) -> Dict:
        """Route to appropriate parser and return schema"""
        parser_map = {
            ('python', 'sqlalchemy'): SQLAlchemyParser(),
            ('database', 'sqlite'): SQLiteParser(),
        }

        parser = parser_map.get((language, framework))
        if not parser:
            # For unknown frameworks, return a placeholder schema
            if language == 'unknown' and framework == 'unknown':
                return self._create_placeholder_schema(project_path, language, framework)
            raise UnsupportedFrameworkError(f"Unsupported framework: {language}/{framework}")

        return parser.parse(project_path)

    def parse_runtime_flow(self, project_path: str, options: Dict = None) -> Dict:
        """Parse Python code to extract runtime flow information"""
        # Check if project has Python files
        if not self._has_python_files(project_path):
            raise UnsupportedFrameworkError("No Python files found in project")

        # Use RuntimeFlowParser
        parser = RuntimeFlowParser(project_path, options)
        return parser.parse()

    def _create_placeholder_schema(self, project_path: str, language: str, framework: str) -> Dict:
        """Create a placeholder schema for unsupported frameworks"""
        return {
            'tables': [
                {
                    'name': 'Example_Table',
                    'columns': [
                        {'name': 'id', 'type': 'INTEGER', 'primary_key': True},
                        {'name': 'name', 'type': 'TEXT', 'nullable': True},
                    ]
                }
            ],
            'relationships': [],
            'note': f'Schema visualization is not yet implemented for {language}/{framework}. This is a placeholder.'
        }

    def _has_file(self, path: str, filename: str) -> bool:
        """Check if file exists in project"""
        return os.path.exists(os.path.join(path, filename))

    def _has_database_files(self, path: str) -> bool:
        """Check if directory contains database files"""
        for root, dirs, files in os.walk(path):
            for file in files:
                if file.endswith(('.db', '.sqlite', '.sqlite3')):
                    return True
        return False

    def _has_python_files(self, path: str) -> bool:
        """Check if directory contains Python files"""
        for root, dirs, files in os.walk(path):
            for file in files:
                if file.endswith('.py'):
                    return True
        return False

    def _detect_python_framework(self, path: str) -> str:
        """Detect Python framework"""
        # Check for SQLAlchemy imports in Python files
        for root, dirs, files in os.walk(path):
            for file in files:
                if file.endswith('.py'):
                    file_path = os.path.join(root, file)
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                            if 'from sqlalchemy' in content or 'import sqlalchemy' in content:
                                return 'sqlalchemy'
                            if 'from django' in content or 'import django' in content:
                                return 'django'
                    except:
                        continue

        return 'unknown'

    def _detect_js_framework(self, path: str) -> str:
        """Detect JavaScript/TypeScript framework"""
        # TODO: Implement JS framework detection
        return 'unknown'
