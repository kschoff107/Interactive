import requests
import base64
import os
import re
from urllib.parse import urlparse
from typing import Dict, List, Optional


class GitApiError(Exception):
    """Custom exception for Git API service errors"""
    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


class GitApiService:
    """Service for browsing and downloading files from public GitHub repositories via API"""

    GITHUB_API_BASE = "https://api.github.com"
    MAX_FILE_SIZE = 1 * 1024 * 1024  # 1MB per file
    MAX_FILES_PER_IMPORT = 50
    REQUEST_TIMEOUT = 15

    def __init__(self):
        token = os.environ.get('GITHUB_TOKEN')
        self._headers = {}
        if token:
            self._headers['Authorization'] = f'token {token}'

    # Directories to exclude from tree display
    EXCLUDED_DIRS = {
        'node_modules', '.git', '__pycache__', '.tox', '.mypy_cache',
        '.pytest_cache', 'venv', '.venv', 'env', '.env', 'dist', 'build',
        '.next', '.nuxt', 'vendor', '.idea', '.vscode', 'coverage',
        '.eggs', '*.egg-info'
    }

    # File extensions we support for analysis
    SUPPORTED_EXTENSIONS = {
        '.py', '.js', '.jsx', '.ts', '.tsx', '.java', '.rb', '.go',
        '.rs', '.php', '.sql', '.json', '.yaml', '.yml', '.toml',
        '.cfg', '.ini', '.txt', '.md', '.html', '.css', '.scss',
        '.sh', '.bat', '.dockerfile', '.xml', '.csv'
    }

    def parse_github_url(self, url: str) -> Dict:
        """
        Parse a GitHub URL and extract owner/repo.
        Handles formats:
          - https://github.com/owner/repo
          - https://github.com/owner/repo.git
          - https://github.com/owner/repo/tree/branch
          - github.com/owner/repo

        Returns: {valid: bool, owner: str, repo: str, branch: str|None, error: str|None}
        """
        if not url or not isinstance(url, str):
            return {'valid': False, 'owner': None, 'repo': None,
                    'branch': None, 'error': 'URL is required'}

        url = url.strip()

        # Prepend https:// if no scheme
        if not url.startswith('http://') and not url.startswith('https://'):
            url = 'https://' + url

        try:
            parsed = urlparse(url)

            if parsed.netloc not in ('github.com', 'www.github.com'):
                return {'valid': False, 'owner': None, 'repo': None,
                        'branch': None,
                        'error': 'Only GitHub URLs are supported (github.com)'}

            path_parts = [p for p in parsed.path.split('/') if p]

            if len(path_parts) < 2:
                return {'valid': False, 'owner': None, 'repo': None,
                        'branch': None,
                        'error': 'Invalid GitHub URL. Expected format: github.com/owner/repo'}

            owner = path_parts[0]
            repo = path_parts[1].removesuffix('.git')

            # Validate owner/repo format (alphanumeric, hyphens, underscores, dots)
            if not re.match(r'^[a-zA-Z0-9._-]+$', owner):
                return {'valid': False, 'owner': None, 'repo': None,
                        'branch': None,
                        'error': f'Invalid repository owner: {owner}'}

            if not re.match(r'^[a-zA-Z0-9._-]+$', repo):
                return {'valid': False, 'owner': None, 'repo': None,
                        'branch': None,
                        'error': f'Invalid repository name: {repo}'}

            # Extract branch if /tree/branch is in URL
            branch = None
            if len(path_parts) >= 4 and path_parts[2] == 'tree':
                branch = path_parts[3]

            return {
                'valid': True,
                'owner': owner,
                'repo': repo,
                'branch': branch,
                'error': None
            }

        except Exception as e:
            return {'valid': False, 'owner': None, 'repo': None,
                    'branch': None, 'error': f'Failed to parse URL: {str(e)}'}

    def get_repo_info(self, owner: str, repo: str) -> Dict:
        """
        Fetch repository metadata (default branch, description, etc).
        Returns: {success: bool, default_branch: str, description: str, error: str|None}
        """
        url = f"{self.GITHUB_API_BASE}/repos/{owner}/{repo}"

        try:
            response = requests.get(url, headers=self._headers, timeout=self.REQUEST_TIMEOUT)

            if response.status_code == 404:
                return {'success': False,
                        'error': 'Repository not found. Make sure it exists and is public.'}

            if response.status_code == 403:
                remaining = response.headers.get('X-RateLimit-Remaining', 'unknown')
                return {'success': False,
                        'error': f'GitHub API rate limit reached (remaining: {remaining}). '
                                 'Please wait a few minutes and try again.'}

            if response.status_code != 200:
                return {'success': False,
                        'error': f'GitHub API error (HTTP {response.status_code})'}

            data = response.json()
            return {
                'success': True,
                'default_branch': data.get('default_branch', 'main'),
                'description': data.get('description', ''),
                'full_name': data.get('full_name', f'{owner}/{repo}'),
                'error': None
            }

        except requests.exceptions.Timeout:
            return {'success': False, 'error': 'GitHub API request timed out. Try again.'}
        except requests.exceptions.ConnectionError:
            return {'success': False, 'error': 'Could not connect to GitHub. Check your internet connection.'}
        except Exception as e:
            return {'success': False, 'error': f'Unexpected error: {str(e)}'}

    def get_repo_tree(self, owner: str, repo: str, branch: str = None) -> Dict:
        """
        Fetch the complete file tree from GitHub API.
        If no branch specified, auto-detects the default branch.

        Returns: {success: bool, files: list, branch: str, truncated: bool, error: str|None}
        """
        # Auto-detect default branch if not specified
        if not branch:
            info = self.get_repo_info(owner, repo)
            if not info['success']:
                return {'success': False, 'files': [], 'branch': None,
                        'truncated': False, 'error': info['error']}
            branch = info['default_branch']

        url = f"{self.GITHUB_API_BASE}/repos/{owner}/{repo}/git/trees/{branch}?recursive=1"

        try:
            response = requests.get(url, headers=self._headers, timeout=self.REQUEST_TIMEOUT)

            if response.status_code == 404:
                return {'success': False, 'files': [], 'branch': branch,
                        'truncated': False,
                        'error': f'Branch "{branch}" not found in {owner}/{repo}. '
                                 'The repository may be empty or the branch name is incorrect.'}

            if response.status_code == 403:
                remaining = response.headers.get('X-RateLimit-Remaining', 'unknown')
                return {'success': False, 'files': [], 'branch': branch,
                        'truncated': False,
                        'error': f'GitHub API rate limit reached (remaining: {remaining}). '
                                 'Please wait a few minutes and try again.'}

            if response.status_code != 200:
                return {'success': False, 'files': [], 'branch': branch,
                        'truncated': False,
                        'error': f'GitHub API error (HTTP {response.status_code})'}

            data = response.json()
            files = []

            for item in data.get('tree', []):
                path = item['path']
                item_type = 'file' if item['type'] == 'blob' else 'dir'
                size = item.get('size', 0)

                # Skip excluded directories and their contents
                path_parts = path.split('/')
                if any(part in self.EXCLUDED_DIRS for part in path_parts):
                    continue

                files.append({
                    'path': path,
                    'type': item_type,
                    'size': size
                })

            return {
                'success': True,
                'files': files,
                'branch': branch,
                'truncated': data.get('truncated', False),
                'error': None
            }

        except requests.exceptions.Timeout:
            return {'success': False, 'files': [], 'branch': branch,
                    'truncated': False,
                    'error': 'GitHub API request timed out. Try again.'}
        except requests.exceptions.ConnectionError:
            return {'success': False, 'files': [], 'branch': branch,
                    'truncated': False,
                    'error': 'Could not connect to GitHub. Check your internet connection.'}
        except Exception as e:
            return {'success': False, 'files': [], 'branch': branch,
                    'truncated': False,
                    'error': f'Unexpected error: {str(e)}'}

    def get_file_content(self, owner: str, repo: str, path: str,
                         branch: str = 'main') -> Dict:
        """
        Fetch a single file's content from GitHub.
        Returns: {success: bool, content: str, size: int, error: str|None}
        """
        url = f"{self.GITHUB_API_BASE}/repos/{owner}/{repo}/contents/{path}?ref={branch}"

        try:
            response = requests.get(url, headers=self._headers, timeout=self.REQUEST_TIMEOUT)

            if response.status_code == 404:
                return {'success': False, 'content': None, 'size': 0,
                        'error': f'File not found: {path}'}

            if response.status_code == 403:
                return {'success': False, 'content': None, 'size': 0,
                        'error': 'GitHub API rate limit reached'}

            if response.status_code != 200:
                return {'success': False, 'content': None, 'size': 0,
                        'error': f'Failed to fetch file: {path} (HTTP {response.status_code})'}

            data = response.json()
            file_size = data.get('size', 0)

            if file_size > self.MAX_FILE_SIZE:
                return {'success': False, 'content': None, 'size': file_size,
                        'error': f'File too large: {path} ({file_size:,} bytes). '
                                 f'Maximum is {self.MAX_FILE_SIZE:,} bytes.'}

            # Content is base64 encoded
            raw_content = data.get('content', '')
            content = base64.b64decode(raw_content).decode('utf-8')

            return {'success': True, 'content': content, 'size': file_size, 'error': None}

        except UnicodeDecodeError:
            return {'success': False, 'content': None, 'size': 0,
                    'error': f'Binary file cannot be imported: {path}'}
        except requests.exceptions.Timeout:
            return {'success': False, 'content': None, 'size': 0,
                    'error': f'Timeout fetching file: {path}'}
        except Exception as e:
            return {'success': False, 'content': None, 'size': 0,
                    'error': f'Error fetching {path}: {str(e)}'}

    def download_files(self, owner: str, repo: str, paths: List[str],
                       target_dir: str, branch: str = 'main') -> Dict:
        """
        Download multiple files and save to target directory.
        Preserves directory structure from the repository.

        Returns: {success: bool, downloaded: int, failed: int, errors: list}
        """
        if len(paths) > self.MAX_FILES_PER_IMPORT:
            return {
                'success': False,
                'downloaded': 0,
                'failed': 0,
                'errors': [{'path': None,
                            'error': f'Too many files. Maximum is {self.MAX_FILES_PER_IMPORT}, '
                                     f'got {len(paths)}.'}]
            }

        os.makedirs(target_dir, exist_ok=True)
        downloaded = 0
        errors = []

        for path in paths:
            # Sanitize path to prevent directory traversal
            safe_path = os.path.normpath(path)
            if safe_path.startswith('..') or os.path.isabs(safe_path):
                errors.append({'path': path, 'error': 'Invalid file path'})
                continue

            result = self.get_file_content(owner, repo, path, branch)

            if result['success']:
                file_path = os.path.join(target_dir, safe_path)
                file_dir = os.path.dirname(file_path)
                os.makedirs(file_dir, exist_ok=True)

                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(result['content'])
                downloaded += 1
            else:
                errors.append({'path': path, 'error': result['error']})

        return {
            'success': len(errors) == 0,
            'downloaded': downloaded,
            'failed': len(errors),
            'errors': errors
        }

    def get_rate_limit_status(self) -> Dict:
        """Check current GitHub API rate limit status"""
        try:
            response = requests.get(
                f"{self.GITHUB_API_BASE}/rate_limit",
                headers=self._headers,
                timeout=self.REQUEST_TIMEOUT
            )
            if response.status_code == 200:
                data = response.json()
                core = data.get('resources', {}).get('core', {})
                return {
                    'limit': core.get('limit', 0),
                    'remaining': core.get('remaining', 0),
                    'reset_at': core.get('reset', 0)
                }
        except Exception:
            pass

        return {'limit': 0, 'remaining': 0, 'reset_at': 0}
