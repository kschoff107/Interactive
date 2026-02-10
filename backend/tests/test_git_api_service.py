"""
Tests for GitApiService - Phase 1: Backend Git API Service

Tests cover:
  1. URL parsing (valid, invalid, edge cases)
  2. Repository info fetching
  3. File tree retrieval
  4. Single file content download
  5. Multi-file download with directory structure
  6. Rate limit status
  7. Security (path traversal prevention)
  8. Error handling (network, API, encoding)
"""
import os
import json
import shutil
import tempfile
import pytest
from unittest.mock import patch, MagicMock

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from services.git_api_service import GitApiService, GitApiError


@pytest.fixture
def service():
    """Create a fresh GitApiService instance"""
    return GitApiService()


@pytest.fixture
def temp_dir():
    """Create a temporary directory for file downloads"""
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d, ignore_errors=True)


# ---------------------------------------------------------------------------
# 1. URL PARSING
# ---------------------------------------------------------------------------

class TestParseGithubUrl:
    """Test GitHub URL parsing with various formats"""

    def test_standard_url(self, service):
        result = service.parse_github_url('https://github.com/pallets/flask')
        assert result['valid'] is True
        assert result['owner'] == 'pallets'
        assert result['repo'] == 'flask'
        assert result['error'] is None

    def test_url_with_git_suffix(self, service):
        result = service.parse_github_url('https://github.com/pallets/flask.git')
        assert result['valid'] is True
        assert result['owner'] == 'pallets'
        assert result['repo'] == 'flask'

    def test_url_with_branch_tree(self, service):
        result = service.parse_github_url('https://github.com/pallets/flask/tree/develop')
        assert result['valid'] is True
        assert result['owner'] == 'pallets'
        assert result['repo'] == 'flask'
        assert result['branch'] == 'develop'

    def test_url_without_scheme(self, service):
        result = service.parse_github_url('github.com/user/repo')
        assert result['valid'] is True
        assert result['owner'] == 'user'
        assert result['repo'] == 'repo'

    def test_www_subdomain(self, service):
        result = service.parse_github_url('https://www.github.com/user/repo')
        assert result['valid'] is True
        assert result['owner'] == 'user'
        assert result['repo'] == 'repo'

    def test_url_with_trailing_slash(self, service):
        result = service.parse_github_url('https://github.com/user/repo/')
        assert result['valid'] is True
        assert result['owner'] == 'user'
        assert result['repo'] == 'repo'

    def test_url_with_whitespace(self, service):
        result = service.parse_github_url('  https://github.com/user/repo  ')
        assert result['valid'] is True
        assert result['owner'] == 'user'
        assert result['repo'] == 'repo'

    def test_non_github_url(self, service):
        result = service.parse_github_url('https://gitlab.com/user/repo')
        assert result['valid'] is False
        assert 'Only GitHub' in result['error']

    def test_incomplete_url_no_repo(self, service):
        result = service.parse_github_url('https://github.com/user')
        assert result['valid'] is False
        assert 'Invalid GitHub URL' in result['error']

    def test_empty_url(self, service):
        result = service.parse_github_url('')
        assert result['valid'] is False

    def test_none_url(self, service):
        result = service.parse_github_url(None)
        assert result['valid'] is False

    def test_non_string_url(self, service):
        result = service.parse_github_url(12345)
        assert result['valid'] is False

    def test_owner_with_hyphens_dots(self, service):
        result = service.parse_github_url('https://github.com/my-org.team/my-repo.py')
        assert result['valid'] is True
        assert result['owner'] == 'my-org.team'
        assert result['repo'] == 'my-repo.py'

    def test_http_url_accepted(self, service):
        result = service.parse_github_url('http://github.com/user/repo')
        assert result['valid'] is True

    def test_branch_is_none_without_tree(self, service):
        result = service.parse_github_url('https://github.com/user/repo')
        assert result['branch'] is None


# ---------------------------------------------------------------------------
# 2. REPOSITORY INFO
# ---------------------------------------------------------------------------

class TestGetRepoInfo:
    """Test repository metadata fetching"""

    @patch('services.git_api_service.requests.get')
    def test_successful_repo_info(self, mock_get, service):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'default_branch': 'main',
            'description': 'A test repo',
            'full_name': 'user/test-repo'
        }
        mock_get.return_value = mock_response

        result = service.get_repo_info('user', 'test-repo')
        assert result['success'] is True
        assert result['default_branch'] == 'main'
        assert result['description'] == 'A test repo'

    @patch('services.git_api_service.requests.get')
    def test_repo_not_found(self, mock_get, service):
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        result = service.get_repo_info('user', 'nonexistent')
        assert result['success'] is False
        assert 'not found' in result['error'].lower()

    @patch('services.git_api_service.requests.get')
    def test_rate_limited(self, mock_get, service):
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.headers = {'X-RateLimit-Remaining': '0'}
        mock_get.return_value = mock_response

        result = service.get_repo_info('user', 'repo')
        assert result['success'] is False
        assert 'rate limit' in result['error'].lower()

    @patch('services.git_api_service.requests.get')
    def test_timeout(self, mock_get, service):
        import requests as req
        mock_get.side_effect = req.exceptions.Timeout()

        result = service.get_repo_info('user', 'repo')
        assert result['success'] is False
        assert 'timed out' in result['error'].lower()

    @patch('services.git_api_service.requests.get')
    def test_connection_error(self, mock_get, service):
        import requests as req
        mock_get.side_effect = req.exceptions.ConnectionError()

        result = service.get_repo_info('user', 'repo')
        assert result['success'] is False
        assert 'connect' in result['error'].lower()


# ---------------------------------------------------------------------------
# 3. FILE TREE RETRIEVAL
# ---------------------------------------------------------------------------

class TestGetRepoTree:
    """Test file tree fetching from GitHub API"""

    @patch('services.git_api_service.requests.get')
    def test_successful_tree(self, mock_get, service):
        # First call: repo info for default branch
        repo_info_response = MagicMock()
        repo_info_response.status_code = 200
        repo_info_response.json.return_value = {
            'default_branch': 'main',
            'description': '',
            'full_name': 'user/repo'
        }

        # Second call: tree
        tree_response = MagicMock()
        tree_response.status_code = 200
        tree_response.json.return_value = {
            'tree': [
                {'path': 'app.py', 'type': 'blob', 'size': 2100},
                {'path': 'models', 'type': 'tree', 'size': 0},
                {'path': 'models/user.py', 'type': 'blob', 'size': 1200},
            ],
            'truncated': False
        }

        mock_get.side_effect = [repo_info_response, tree_response]

        result = service.get_repo_tree('user', 'repo')
        assert result['success'] is True
        assert result['branch'] == 'main'
        assert len(result['files']) == 3
        assert result['files'][0]['path'] == 'app.py'
        assert result['files'][0]['type'] == 'file'
        assert result['files'][0]['size'] == 2100

    @patch('services.git_api_service.requests.get')
    def test_excludes_node_modules(self, mock_get, service):
        tree_response = MagicMock()
        tree_response.status_code = 200
        tree_response.json.return_value = {
            'tree': [
                {'path': 'app.py', 'type': 'blob', 'size': 100},
                {'path': 'node_modules', 'type': 'tree', 'size': 0},
                {'path': 'node_modules/express/index.js', 'type': 'blob', 'size': 500},
                {'path': '__pycache__/app.cpython-310.pyc', 'type': 'blob', 'size': 300},
            ],
            'truncated': False
        }
        mock_get.return_value = tree_response

        result = service.get_repo_tree('user', 'repo', branch='main')
        assert result['success'] is True
        # Only app.py should survive filtering
        assert len(result['files']) == 1
        assert result['files'][0]['path'] == 'app.py'

    @patch('services.git_api_service.requests.get')
    def test_tree_with_explicit_branch(self, mock_get, service):
        tree_response = MagicMock()
        tree_response.status_code = 200
        tree_response.json.return_value = {'tree': [], 'truncated': False}
        mock_get.return_value = tree_response

        result = service.get_repo_tree('user', 'repo', branch='develop')
        assert result['success'] is True
        assert result['branch'] == 'develop'
        # Should only make one call (no repo info needed)
        mock_get.assert_called_once()

    @patch('services.git_api_service.requests.get')
    def test_tree_branch_not_found(self, mock_get, service):
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        result = service.get_repo_tree('user', 'repo', branch='nonexistent')
        assert result['success'] is False
        assert 'not found' in result['error'].lower()

    @patch('services.git_api_service.requests.get')
    def test_tree_truncated_flag(self, mock_get, service):
        tree_response = MagicMock()
        tree_response.status_code = 200
        tree_response.json.return_value = {
            'tree': [{'path': 'a.py', 'type': 'blob', 'size': 10}],
            'truncated': True
        }
        mock_get.return_value = tree_response

        result = service.get_repo_tree('user', 'repo', branch='main')
        assert result['success'] is True
        assert result['truncated'] is True


# ---------------------------------------------------------------------------
# 4. SINGLE FILE CONTENT
# ---------------------------------------------------------------------------

class TestGetFileContent:
    """Test individual file content fetching"""

    @patch('services.git_api_service.requests.get')
    def test_successful_fetch(self, mock_get, service):
        import base64
        content = "print('hello world')\n"
        encoded = base64.b64encode(content.encode('utf-8')).decode('utf-8')

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'content': encoded,
            'size': len(content)
        }
        mock_get.return_value = mock_response

        result = service.get_file_content('user', 'repo', 'app.py', 'main')
        assert result['success'] is True
        assert result['content'] == content
        assert result['size'] == len(content)

    @patch('services.git_api_service.requests.get')
    def test_file_not_found(self, mock_get, service):
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        result = service.get_file_content('user', 'repo', 'missing.py', 'main')
        assert result['success'] is False
        assert 'not found' in result['error'].lower()

    @patch('services.git_api_service.requests.get')
    def test_file_too_large(self, mock_get, service):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'content': '',
            'size': 2 * 1024 * 1024  # 2MB - over limit
        }
        mock_get.return_value = mock_response

        result = service.get_file_content('user', 'repo', 'big.bin', 'main')
        assert result['success'] is False
        assert 'too large' in result['error'].lower()

    @patch('services.git_api_service.requests.get')
    def test_binary_file_rejected(self, mock_get, service):
        import base64
        # Binary content that can't be decoded as UTF-8
        binary_content = bytes(range(256))
        encoded = base64.b64encode(binary_content).decode('utf-8')

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'content': encoded,
            'size': 256
        }
        mock_get.return_value = mock_response

        result = service.get_file_content('user', 'repo', 'image.png', 'main')
        assert result['success'] is False
        assert 'binary' in result['error'].lower()


# ---------------------------------------------------------------------------
# 5. MULTI-FILE DOWNLOAD
# ---------------------------------------------------------------------------

class TestDownloadFiles:
    """Test downloading multiple files to local filesystem"""

    @patch('services.git_api_service.requests.get')
    def test_download_multiple_files(self, mock_get, service, temp_dir):
        import base64

        files_content = {
            'app.py': "from flask import Flask\n",
            'models/user.py': "class User:\n    pass\n"
        }

        def mock_response_for(url, **kwargs):
            resp = MagicMock()
            resp.status_code = 200
            for path, content in files_content.items():
                if path in url:
                    resp.json.return_value = {
                        'content': base64.b64encode(content.encode()).decode(),
                        'size': len(content)
                    }
                    return resp
            resp.status_code = 404
            return resp

        mock_get.side_effect = mock_response_for

        result = service.download_files(
            'user', 'repo',
            ['app.py', 'models/user.py'],
            temp_dir, 'main'
        )

        assert result['success'] is True
        assert result['downloaded'] == 2
        assert result['failed'] == 0
        assert len(result['errors']) == 0

        # Verify files exist with correct content
        assert os.path.isfile(os.path.join(temp_dir, 'app.py'))
        assert os.path.isfile(os.path.join(temp_dir, 'models', 'user.py'))

        with open(os.path.join(temp_dir, 'app.py'), 'r') as f:
            assert f.read() == "from flask import Flask\n"

    @patch('services.git_api_service.requests.get')
    def test_download_partial_failure(self, mock_get, service, temp_dir):
        import base64

        def mock_response_for(url, **kwargs):
            resp = MagicMock()
            if 'good.py' in url:
                resp.status_code = 200
                resp.json.return_value = {
                    'content': base64.b64encode(b'good').decode(),
                    'size': 4
                }
            else:
                resp.status_code = 404
            return resp

        mock_get.side_effect = mock_response_for

        result = service.download_files(
            'user', 'repo',
            ['good.py', 'missing.py'],
            temp_dir, 'main'
        )

        assert result['success'] is False
        assert result['downloaded'] == 1
        assert result['failed'] == 1
        assert len(result['errors']) == 1
        assert result['errors'][0]['path'] == 'missing.py'

    def test_download_too_many_files(self, service, temp_dir):
        paths = [f'file{i}.py' for i in range(51)]
        result = service.download_files('user', 'repo', paths, temp_dir, 'main')
        assert result['success'] is False
        assert 'Too many files' in result['errors'][0]['error']

    def test_path_traversal_blocked(self, service, temp_dir):
        """Ensure directory traversal attacks are blocked"""
        with patch('services.git_api_service.requests.get') as mock_get:
            result = service.download_files(
                'user', 'repo',
                ['../../etc/passwd'],
                temp_dir, 'main'
            )
            assert result['failed'] == 1
            assert 'Invalid file path' in result['errors'][0]['error']


# ---------------------------------------------------------------------------
# 6. RATE LIMIT STATUS
# ---------------------------------------------------------------------------

class TestRateLimitStatus:
    """Test rate limit checking"""

    @patch('services.git_api_service.requests.get')
    def test_rate_limit_check(self, mock_get, service):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'resources': {
                'core': {
                    'limit': 60,
                    'remaining': 42,
                    'reset': 1700000000
                }
            }
        }
        mock_get.return_value = mock_response

        result = service.get_rate_limit_status()
        assert result['limit'] == 60
        assert result['remaining'] == 42

    @patch('services.git_api_service.requests.get')
    def test_rate_limit_on_error(self, mock_get, service):
        mock_get.side_effect = Exception('network error')

        result = service.get_rate_limit_status()
        assert result['limit'] == 0
        assert result['remaining'] == 0


# ---------------------------------------------------------------------------
# 7. CONSTANTS AND CONFIGURATION
# ---------------------------------------------------------------------------

class TestServiceConfiguration:
    """Test service constants and defaults"""

    def test_max_file_size(self, service):
        assert service.MAX_FILE_SIZE == 1 * 1024 * 1024

    def test_max_files_per_import(self, service):
        assert service.MAX_FILES_PER_IMPORT == 50

    def test_excluded_dirs_include_common(self, service):
        assert 'node_modules' in service.EXCLUDED_DIRS
        assert '__pycache__' in service.EXCLUDED_DIRS
        assert '.git' in service.EXCLUDED_DIRS
        assert 'venv' in service.EXCLUDED_DIRS

    def test_api_base_url(self, service):
        assert service.GITHUB_API_BASE == "https://api.github.com"


# ---------------------------------------------------------------------------
# 8. INTEGRATION-STYLE TEST (mocked but end-to-end flow)
# ---------------------------------------------------------------------------

class TestEndToEndFlow:
    """Test the complete flow: parse URL -> get tree -> download files"""

    @patch('services.git_api_service.requests.get')
    def test_full_import_flow(self, mock_get, service, temp_dir):
        import base64

        # Step 1: Parse URL
        parsed = service.parse_github_url('https://github.com/testuser/testproject')
        assert parsed['valid'] is True

        # Step 2: Mock repo info + tree + file content calls
        call_count = [0]

        def mock_responses(url, **kwargs):
            call_count[0] += 1
            resp = MagicMock()

            if '/git/trees/' in url:
                resp.status_code = 200
                resp.json.return_value = {
                    'tree': [
                        {'path': 'main.py', 'type': 'blob', 'size': 50},
                        {'path': 'utils.py', 'type': 'blob', 'size': 30},
                    ],
                    'truncated': False
                }
            elif '/contents/main.py' in url:
                resp.status_code = 200
                content = "print('main')\n"
                resp.json.return_value = {
                    'content': base64.b64encode(content.encode()).decode(),
                    'size': len(content)
                }
            elif '/contents/utils.py' in url:
                resp.status_code = 200
                content = "def helper(): pass\n"
                resp.json.return_value = {
                    'content': base64.b64encode(content.encode()).decode(),
                    'size': len(content)
                }
            elif url.endswith(f"/repos/{parsed['owner']}/{parsed['repo']}"):
                resp.status_code = 200
                resp.json.return_value = {
                    'default_branch': 'main',
                    'description': 'A test project',
                    'full_name': 'testuser/testproject'
                }
            else:
                resp.status_code = 404
            return resp

        mock_get.side_effect = mock_responses

        # Step 3: Get tree
        tree = service.get_repo_tree(parsed['owner'], parsed['repo'])
        assert tree['success'] is True
        assert len(tree['files']) == 2

        # Step 4: Download selected files
        file_paths = [f['path'] for f in tree['files'] if f['type'] == 'file']
        download_result = service.download_files(
            parsed['owner'], parsed['repo'],
            file_paths, temp_dir, tree['branch']
        )

        assert download_result['success'] is True
        assert download_result['downloaded'] == 2
        assert os.path.isfile(os.path.join(temp_dir, 'main.py'))
        assert os.path.isfile(os.path.join(temp_dir, 'utils.py'))
