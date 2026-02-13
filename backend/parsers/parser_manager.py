"""
Parser Manager — detects languages/frameworks and routes to appropriate parsers.

Supports: Python, JavaScript/TypeScript, Java, C#, Ruby, Go, PHP, ABAP, SQLite.
"""

import json
import os
from typing import Dict, List, Tuple

from .base import find_source_files, read_file_safe

# Lazy imports — parsers are imported only when needed to avoid circular imports
# and keep startup fast. Each _get_*_parser() function handles the import.


class UnsupportedFrameworkError(Exception):
    """Raised when the detected framework has no parser available."""
    pass


class ParserManager:
    """Manages detection and routing to appropriate parsers."""

    # -----------------------------------------------------------------------
    # Language / framework detection
    # -----------------------------------------------------------------------

    def detect_language_and_framework(self, project_path: str) -> Tuple[str, str]:
        """Detect the primary language and framework from project files.

        Returns the first strong detection. For multi-language projects,
        use detect_all() to get all detected combos.
        """
        detections = self.detect_all(project_path)
        if detections:
            return detections[0]
        return ('unknown', 'unknown')

    def detect_all(self, project_path: str) -> List[Tuple[str, str]]:
        """Detect all languages and frameworks present in a project.

        Returns a list of (language, framework) tuples ordered by priority.
        """
        detections = []

        # SQLite databases (highest priority — definitive signal)
        if self._has_database_files(project_path):
            detections.append(('database', 'sqlite'))

        # Python
        if (self._has_file(project_path, 'requirements.txt') or
                self._has_file(project_path, 'setup.py') or
                self._has_file(project_path, 'pyproject.toml') or
                self._has_python_files(project_path)):
            framework = self._detect_python_framework(project_path)
            if framework != 'unknown':
                detections.append(('python', framework))

        # Prisma (can coexist with JS — check before generic JS detection)
        if self._has_prisma_schema(project_path):
            detections.append(('javascript', 'prisma'))

        # JavaScript / TypeScript
        if self._has_file(project_path, 'package.json'):
            framework = self._detect_js_framework(project_path)
            if framework != 'unknown' and ('javascript', framework) not in detections:
                detections.append(('javascript', framework))

        # Java
        if (self._has_file(project_path, 'pom.xml') or
                self._has_file(project_path, 'build.gradle') or
                self._has_file(project_path, 'build.gradle.kts')):
            framework = self._detect_java_framework(project_path)
            detections.append(('java', framework))

        # C#
        if self._has_files_matching(project_path, '.csproj') or self._has_files_matching(project_path, '.sln'):
            framework = self._detect_csharp_framework(project_path)
            detections.append(('csharp', framework))

        # Ruby
        if self._has_file(project_path, 'Gemfile'):
            framework = self._detect_ruby_framework(project_path)
            detections.append(('ruby', framework))

        # Go
        if self._has_file(project_path, 'go.mod'):
            framework = self._detect_go_framework(project_path)
            detections.append(('go', framework))

        # PHP
        if self._has_file(project_path, 'composer.json'):
            framework = self._detect_php_framework(project_path)
            detections.append(('php', framework))

        # ABAP
        if self._has_abap_files(project_path):
            framework = self._detect_abap_framework(project_path)
            detections.append(('abap', framework))

        # Fallback — check for source files directly
        if not detections:
            for ext, lang in [('.java', 'java'), ('.cs', 'csharp'),
                              ('.go', 'go'), ('.rb', 'ruby'), ('.php', 'php'),
                              ('.ts', 'javascript'), ('.js', 'javascript')]:
                if find_source_files(project_path, [ext]):
                    detections.append((lang, 'unknown'))
                    break

        return detections

    # -----------------------------------------------------------------------
    # Schema parsing
    # -----------------------------------------------------------------------

    def parse_database_schema(self, project_path: str, language: str, framework: str) -> Dict:
        """Route to appropriate schema parser and return standardized result."""
        parser = self._get_schema_parser(language, framework)
        if parser:
            return parser.parse(project_path)

        raise UnsupportedFrameworkError(
            f"No database schema parser available for {language}/{framework}")

    def _get_schema_parser(self, language: str, framework: str):
        """Return the schema parser instance for a (language, framework) pair."""
        key = (language, framework)

        if key == ('python', 'sqlalchemy'):
            from .schema.sqlalchemy_parser import SQLAlchemyParser
            return SQLAlchemyParser()
        if key == ('database', 'sqlite'):
            from .schema.sqlite_parser import SQLiteParser
            return SQLiteParser()
        if key == ('python', 'django'):
            from .schema.django_parser import DjangoParser
            return DjangoParser()
        if key == ('javascript', 'prisma'):
            from .schema.prisma_parser import PrismaParser
            return PrismaParser()
        if key == ('javascript', 'typeorm'):
            from .schema.typeorm_parser import TypeORMParser
            return TypeORMParser()
        if key == ('javascript', 'sequelize'):
            from .schema.sequelize_parser import SequelizeParser
            return SequelizeParser()
        if key == ('javascript', 'mongoose'):
            from .schema.mongoose_parser import MongooseParser
            return MongooseParser()
        if key == ('java', 'jpa') or key == ('java', 'hibernate'):
            from .schema.jpa_parser import JPAParser
            return JPAParser()
        if key == ('csharp', 'entityframework'):
            from .schema.ef_parser import EntityFrameworkParser
            return EntityFrameworkParser()
        if key == ('ruby', 'activerecord') or key == ('ruby', 'rails'):
            from .schema.activerecord_parser import ActiveRecordParser
            return ActiveRecordParser()
        if key == ('go', 'gorm'):
            from .schema.gorm_parser import GORMParser
            return GORMParser()
        if key == ('php', 'eloquent') or key == ('php', 'laravel'):
            from .schema.eloquent_parser import EloquentParser
            return EloquentParser()
        if key == ('abap', 'dictionary') or key == ('abap', 'abap'):
            from .schema.abap_dict_parser import ABAPDictParser
            return ABAPDictParser()

        return None

    # -----------------------------------------------------------------------
    # Runtime flow parsing
    # -----------------------------------------------------------------------

    def parse_runtime_flow(self, project_path: str, options: Dict = None) -> Dict:
        """Parse source code to extract runtime flow information.

        Detects language and routes to appropriate flow parser.
        """
        parser = self._get_flow_parser(project_path, options)
        if parser:
            return parser.parse()

        raise UnsupportedFrameworkError(
            "No supported source files found for runtime flow analysis. "
            "Supported: Python (.py), JavaScript/TypeScript (.js/.ts), Java (.java), ABAP (.abap)")

    def _get_flow_parser(self, project_path: str, options: Dict = None):
        """Return the appropriate flow parser for the project."""
        if self._has_python_files(project_path):
            from .flow.python_flow_parser import RuntimeFlowParser
            return RuntimeFlowParser(project_path, options)
        if find_source_files(project_path, ['.js', '.ts', '.jsx', '.tsx']):
            from .flow.js_flow_parser import JSFlowParser
            return JSFlowParser(project_path, options)
        if find_source_files(project_path, ['.java']):
            from .flow.java_flow_parser import JavaFlowParser
            return JavaFlowParser(project_path, options)
        if self._has_abap_files(project_path):
            from .flow.abap_flow_parser import ABAPFlowParser
            return ABAPFlowParser(project_path, options)
        return None

    # -----------------------------------------------------------------------
    # API routes parsing
    # -----------------------------------------------------------------------

    def parse_api_routes(self, project_path: str, options: Dict = None) -> Dict:
        """Parse source code to extract API route definitions.

        Detects language/framework and routes to appropriate routes parser.
        """
        parser = self._get_routes_parser(project_path, options)
        if parser:
            return parser.parse()

        raise UnsupportedFrameworkError(
            "No supported web framework detected for API routes analysis. "
            "Supported: Flask, Django, FastAPI, Express, NestJS, Spring Boot, "
            "ASP.NET, Rails, Laravel, Gin/Echo, ABAP ICF/OData")

    def _get_routes_parser(self, project_path: str, options: Dict = None):
        """Return the appropriate routes parser for the project."""
        # Python web frameworks
        if self._has_python_files(project_path):
            py_framework = self._detect_python_web_framework(project_path)
            if py_framework == 'flask':
                from .routes.flask_parser import FlaskRoutesParser
                return FlaskRoutesParser(project_path, options)
            if py_framework == 'fastapi':
                from .routes.fastapi_parser import FastAPIParser
                return FastAPIParser(project_path, options)
            if py_framework == 'django':
                from .routes.django_routes_parser import DjangoRoutesParser
                return DjangoRoutesParser(project_path, options)

        # JS/TS web frameworks
        js_files = find_source_files(project_path, ['.js', '.ts', '.jsx', '.tsx'])
        if js_files:
            js_framework = self._detect_js_web_framework(project_path)
            if js_framework == 'express':
                from .routes.express_parser import ExpressParser
                return ExpressParser(project_path, options)
            if js_framework == 'nestjs':
                from .routes.nestjs_parser import NestJSParser
                return NestJSParser(project_path, options)

        # Java — Spring Boot
        java_files = find_source_files(project_path, ['.java'])
        if java_files:
            if self._has_spring_framework(project_path):
                from .routes.spring_parser import SpringParser
                return SpringParser(project_path, options)

        # C# — ASP.NET
        cs_files = find_source_files(project_path, ['.cs'])
        if cs_files:
            if self._has_aspnet_framework(project_path):
                from .routes.aspnet_parser import ASPNetParser
                return ASPNetParser(project_path, options)

        # Ruby — Rails
        if self._has_file(project_path, 'Gemfile'):
            if self._detect_ruby_framework(project_path) == 'rails':
                from .routes.rails_routes_parser import RailsRoutesParser
                return RailsRoutesParser(project_path, options)

        # PHP — Laravel
        if self._has_file(project_path, 'composer.json'):
            if self._detect_php_framework(project_path) == 'laravel':
                from .routes.laravel_parser import LaravelParser
                return LaravelParser(project_path, options)

        # Go — Gin/Echo
        go_files = find_source_files(project_path, ['.go'])
        if go_files:
            go_fw = self._detect_go_web_framework(project_path)
            if go_fw:
                from .routes.gin_parser import GinParser
                return GinParser(project_path, options)

        # ABAP — ICF/OData
        if self._has_abap_files(project_path):
            from .routes.abap_icf_parser import ABAPICFParser
            return ABAPICFParser(project_path, options)

        return None

    # -----------------------------------------------------------------------
    # Code structure parsing
    # -----------------------------------------------------------------------

    def parse_code_structure(self, project_path: str, options: Dict = None) -> Dict:
        """Parse source code to extract class/module structure.

        Detects language and routes to appropriate structure parser.
        """
        parser = self._get_structure_parser(project_path, options)
        if parser:
            return parser.parse()

        raise UnsupportedFrameworkError(
            "No supported source files found for code structure analysis. "
            "Supported: Python (.py), JavaScript/TypeScript (.js/.ts/.jsx/.tsx)")

    def _get_structure_parser(self, project_path: str, options: Dict = None):
        """Return the appropriate structure parser for the project."""
        if self._has_python_files(project_path):
            from .structure.python_structure_parser import PythonStructureParser
            return PythonStructureParser(project_path, options)
        if find_source_files(project_path, ['.js', '.ts', '.jsx', '.tsx']):
            from .structure.js_structure_parser import JSStructureParser
            return JSStructureParser(project_path, options)
        return None

    # -----------------------------------------------------------------------
    # File and language detection helpers
    # -----------------------------------------------------------------------

    @staticmethod
    def _has_file(path: str, filename: str) -> bool:
        """Check if file exists in project root."""
        return os.path.exists(os.path.join(path, filename))

    @staticmethod
    def _has_files_matching(path: str, extension: str) -> bool:
        """Check if any files with extension exist (recursive)."""
        for root, dirs, files in os.walk(path):
            dirs[:] = [d for d in dirs if d not in {'.git', 'node_modules', 'vendor'}]
            for f in files:
                if f.endswith(extension):
                    return True
        return False

    @staticmethod
    def _has_database_files(path: str) -> bool:
        for root, dirs, files in os.walk(path):
            dirs[:] = [d for d in dirs if d not in {
                '.git', 'node_modules', '__pycache__', '.venv', 'venv',
                'env', 'vendor', 'dist', 'build', '.eggs', '.tox',
            }]
            for f in files:
                if f.endswith(('.db', '.sqlite', '.sqlite3')):
                    return True
        return False

    @staticmethod
    def _has_python_files(path: str) -> bool:
        for root, dirs, files in os.walk(path):
            dirs[:] = [d for d in dirs if d not in {'__pycache__', '.git', '.venv', 'venv', 'node_modules'}]
            for f in files:
                if f.endswith('.py'):
                    return True
        return False

    @staticmethod
    def _has_prisma_schema(path: str) -> bool:
        for root, dirs, files in os.walk(path):
            dirs[:] = [d for d in dirs if d not in {'node_modules', '.git'}]
            for f in files:
                if f.endswith('.prisma'):
                    return True
        return False

    @staticmethod
    def _has_abap_files(path: str) -> bool:
        for root, dirs, files in os.walk(path):
            dirs[:] = [d for d in dirs if d not in {'.git'}]
            for f in files:
                if f.endswith(('.abap', '.ABAP')):
                    return True
        return False

    # -----------------------------------------------------------------------
    # Python framework detection
    # -----------------------------------------------------------------------

    @staticmethod
    def _detect_python_framework(path: str) -> str:
        """Detect Python ORM/framework for schema parsing."""
        for root, dirs, files in os.walk(path):
            dirs[:] = [d for d in dirs if d not in {'__pycache__', '.git', '.venv', 'venv', 'node_modules'}]
            for fname in files:
                if fname.endswith('.py'):
                    content = read_file_safe(os.path.join(root, fname))
                    if not content:
                        continue
                    cl = content.lower()
                    if 'from sqlalchemy' in cl or 'import sqlalchemy' in cl:
                        return 'sqlalchemy'
                    if 'from django' in cl or 'import django' in cl:
                        return 'django'
        return 'unknown'

    @staticmethod
    def _detect_python_web_framework(path: str) -> str:
        """Detect Python web framework (Flask, FastAPI, Django)."""
        for root, dirs, files in os.walk(path):
            dirs[:] = [d for d in dirs if d not in {'__pycache__', '.git', '.venv', 'venv', 'node_modules'}]
            for fname in files:
                if fname.endswith('.py'):
                    content = read_file_safe(os.path.join(root, fname))
                    if not content:
                        continue
                    cl = content.lower()
                    if 'from flask' in cl or 'import flask' in cl:
                        return 'flask'
                    if 'from fastapi' in cl or 'import fastapi' in cl:
                        return 'fastapi'
                    if 'from django' in cl or 'import django' in cl:
                        return 'django'
        return None

    # -----------------------------------------------------------------------
    # JavaScript / TypeScript framework detection
    # -----------------------------------------------------------------------

    def _detect_js_framework(self, path: str) -> str:
        """Detect JS/TS ORM framework from package.json dependencies."""
        pkg = self._read_package_json(path)
        if not pkg:
            return 'unknown'
        all_deps = {**pkg.get('dependencies', {}), **pkg.get('devDependencies', {})}

        if 'prisma' in all_deps or '@prisma/client' in all_deps:
            return 'prisma'
        if 'typeorm' in all_deps:
            return 'typeorm'
        if 'sequelize' in all_deps:
            return 'sequelize'
        if 'mongoose' in all_deps:
            return 'mongoose'
        if 'express' in all_deps:
            return 'express'
        if '@nestjs/core' in all_deps:
            return 'nestjs'
        return 'unknown'

    def _detect_js_web_framework(self, path: str) -> str:
        """Detect JS/TS web framework specifically for routes parsing."""
        pkg = self._read_package_json(path)
        if not pkg:
            # Fall back to scanning imports in source files
            return self._detect_js_web_from_source(path)
        all_deps = {**pkg.get('dependencies', {}), **pkg.get('devDependencies', {})}

        if '@nestjs/core' in all_deps:
            return 'nestjs'
        if 'express' in all_deps:
            return 'express'
        return None

    @staticmethod
    def _detect_js_web_from_source(path: str) -> str:
        """Detect JS web framework by scanning source files for imports."""
        for fpath in find_source_files(path, ['.js', '.ts', '.jsx', '.tsx'])[:20]:
            content = read_file_safe(fpath)
            if not content:
                continue
            if 'from \'express\'' in content or 'require(\'express\')' in content or \
               'from "express"' in content or 'require("express")' in content:
                return 'express'
            if '@nestjs/' in content:
                return 'nestjs'
        return None

    @staticmethod
    def _read_package_json(path: str) -> dict:
        pkg_path = os.path.join(path, 'package.json')
        if not os.path.exists(pkg_path):
            return None
        try:
            with open(pkg_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return None

    # -----------------------------------------------------------------------
    # Java framework detection
    # -----------------------------------------------------------------------

    def _detect_java_framework(self, path: str) -> str:
        """Detect Java framework from build files."""
        # Check pom.xml for Spring Boot / JPA
        pom_path = os.path.join(path, 'pom.xml')
        if os.path.exists(pom_path):
            content = read_file_safe(pom_path) or ''
            if 'spring-boot' in content:
                return 'spring'
            if 'hibernate' in content or 'javax.persistence' in content or 'jakarta.persistence' in content:
                return 'jpa'

        # Check build.gradle
        for gradle_name in ['build.gradle', 'build.gradle.kts']:
            gradle_path = os.path.join(path, gradle_name)
            if os.path.exists(gradle_path):
                content = read_file_safe(gradle_path) or ''
                if 'spring-boot' in content:
                    return 'spring'
                if 'hibernate' in content or 'javax.persistence' in content or 'jakarta.persistence' in content:
                    return 'jpa'

        # Scan Java source for annotations
        for fpath in find_source_files(path, ['.java'])[:20]:
            content = read_file_safe(fpath)
            if not content:
                continue
            if '@SpringBootApplication' in content or '@RestController' in content:
                return 'spring'
            if '@Entity' in content and ('javax.persistence' in content or 'jakarta.persistence' in content):
                return 'jpa'

        return 'unknown'

    @staticmethod
    def _has_spring_framework(path: str) -> bool:
        """Check if project uses Spring Boot/MVC."""
        for fpath in find_source_files(path, ['.java'])[:30]:
            content = read_file_safe(fpath)
            if content and ('@RestController' in content or '@Controller' in content or
                            '@RequestMapping' in content or '@GetMapping' in content):
                return True
        return False

    # -----------------------------------------------------------------------
    # C# framework detection
    # -----------------------------------------------------------------------

    def _detect_csharp_framework(self, path: str) -> str:
        """Detect C# framework from project files."""
        for fpath in find_source_files(path, ['.csproj'])[:5]:
            content = read_file_safe(fpath) or ''
            if 'Microsoft.EntityFrameworkCore' in content or 'EntityFramework' in content:
                return 'entityframework'
            if 'Microsoft.AspNetCore' in content:
                return 'aspnet'

        for fpath in find_source_files(path, ['.cs'])[:20]:
            content = read_file_safe(fpath)
            if not content:
                continue
            if 'DbContext' in content or 'DbSet<' in content:
                return 'entityframework'
            if '[ApiController]' in content or '[HttpGet' in content:
                return 'aspnet'

        return 'unknown'

    @staticmethod
    def _has_aspnet_framework(path: str) -> bool:
        for fpath in find_source_files(path, ['.cs'])[:30]:
            content = read_file_safe(fpath)
            if content and ('[ApiController]' in content or '[HttpGet' in content or
                            '[Route(' in content):
                return True
        return False

    # -----------------------------------------------------------------------
    # Ruby framework detection
    # -----------------------------------------------------------------------

    @staticmethod
    def _detect_ruby_framework(path: str) -> str:
        gemfile_path = os.path.join(path, 'Gemfile')
        if os.path.exists(gemfile_path):
            content = read_file_safe(gemfile_path) or ''
            if 'rails' in content.lower():
                return 'rails'
            if 'activerecord' in content.lower() or 'active_record' in content.lower():
                return 'activerecord'
        if os.path.exists(os.path.join(path, 'config', 'routes.rb')):
            return 'rails'
        return 'unknown'

    # -----------------------------------------------------------------------
    # Go framework detection
    # -----------------------------------------------------------------------

    @staticmethod
    def _detect_go_framework(path: str) -> str:
        gomod_path = os.path.join(path, 'go.mod')
        if os.path.exists(gomod_path):
            content = read_file_safe(gomod_path) or ''
            if 'gorm.io' in content:
                return 'gorm'
            if 'gin-gonic' in content:
                return 'gin'
            if 'labstack/echo' in content:
                return 'echo'
        return 'unknown'

    @staticmethod
    def _detect_go_web_framework(path: str) -> str:
        gomod_path = os.path.join(path, 'go.mod')
        if os.path.exists(gomod_path):
            content = read_file_safe(gomod_path) or ''
            if 'gin-gonic' in content:
                return 'gin'
            if 'labstack/echo' in content:
                return 'echo'
        # Scan source
        for fpath in find_source_files(path, ['.go'])[:20]:
            content = read_file_safe(fpath)
            if content and ('gin.Default()' in content or 'gin.New()' in content):
                return 'gin'
            if content and ('echo.New()' in content):
                return 'echo'
        return None

    # -----------------------------------------------------------------------
    # PHP framework detection
    # -----------------------------------------------------------------------

    @staticmethod
    def _detect_php_framework(path: str) -> str:
        composer_path = os.path.join(path, 'composer.json')
        if os.path.exists(composer_path):
            try:
                with open(composer_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                all_deps = {**data.get('require', {}), **data.get('require-dev', {})}
                if 'laravel/framework' in all_deps:
                    return 'laravel'
                if 'illuminate/database' in all_deps:
                    return 'eloquent'
            except Exception:
                pass
        if os.path.exists(os.path.join(path, 'artisan')):
            return 'laravel'
        return 'unknown'

    # -----------------------------------------------------------------------
    # ABAP detection
    # -----------------------------------------------------------------------

    @staticmethod
    def _detect_abap_framework(path: str) -> str:
        """Detect ABAP framework type."""
        for fpath in find_source_files(path, ['.abap', '.ABAP'])[:20]:
            content = read_file_safe(fpath)
            if not content:
                continue
            upper = content.upper()
            if 'CALL FUNCTION' in upper or 'FUNCTION-POOL' in upper:
                return 'dictionary'
            if 'CLASS ' in upper and 'METHOD ' in upper:
                return 'dictionary'
        return 'abap'

