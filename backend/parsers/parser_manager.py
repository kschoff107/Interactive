import os
from typing import Tuple, Dict
from .sqlalchemy_parser import SQLAlchemyParser

class UnsupportedFrameworkError(Exception):
    """Raised when framework is not supported"""
    pass

class ParserManager:
    """Manages detection and routing to appropriate parsers"""

    def detect_language_and_framework(self, project_path: str) -> Tuple[str, str]:
        """Detect language and framework from project files"""

        # Check for Python projects
        if self._has_file(project_path, 'requirements.txt') or self._has_file(project_path, 'setup.py'):
            framework = self._detect_python_framework(project_path)
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
        }

        parser = parser_map.get((language, framework))
        if not parser:
            raise UnsupportedFrameworkError(f"Unsupported framework: {language}/{framework}")

        return parser.parse(project_path)

    def _has_file(self, path: str, filename: str) -> bool:
        """Check if file exists in project"""
        return os.path.exists(os.path.join(path, filename))

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
