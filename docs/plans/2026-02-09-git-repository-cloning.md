# Git Repository Import - Design Document

**Date:** February 9, 2026
**Feature:** Import from GitHub Repository (API-based, no cloning)
**Status:** Completed (February 10, 2026)
**Commit:** 484b893

## Decisions Made

- **Platform**: GitHub only for MVP (GitLab/Bitbucket can be added later)
- **UI**: Separate "Import from Git" button on Dashboard
- **Approach**: API-based file browsing (no full repo cloning)

## Overview

Allow users to import files from public GitHub repositories by browsing the repo structure via API and selecting specific files to analyze. **No cloning required** - only selected files are downloaded, minimizing storage usage.

## Why API-Based (Not Cloning)

| Approach | Storage | Speed | UX |
|----------|---------|-------|-----|
| Clone entire repo | 50-500MB per project | Slow | No control |
| **API + Select files** | 1-5MB per project | Instant tree | Full control |

## User Flow

```
1. User clicks "Import from Git" on Dashboard
         ↓
2. Enters URL: https://github.com/user/repo
         ↓
3. Backend calls GitHub API → returns file tree (instant, ~5KB)
         ↓
4. Modal shows file browser with checkboxes
         ↓
5. User selects files to import
         ↓
6. Backend fetches ONLY those files via API
         ↓
7. Files saved to storage/uploads/<user>/<project>/
         ↓
8. Analysis runs → Visualization displayed
```

## Visual Design

### Dashboard with "Import from Git" Button

```
┌──────────────────────────────────────────────────────────────────┐
│  Your Projects                   [+ New Project] [Import from Git]│
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌─────────────────────┐   ┌─────────────────────┐               │
│  │ 📁 My Flask API     │   │ 🐙 React Dashboard  │               │
│  │ Python • Flask      │   │ JavaScript • React  │               │
│  │ 📤 Uploaded         │   │ 🐙 github.com       │  ← Git badge  │
│  └─────────────────────┘   └─────────────────────┘               │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
```

### Import Modal with File Browser

```
┌──────────────────────────────────────────────────────────────────┐
│  Import from GitHub                                           ✕  │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Repository URL                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ https://github.com/user/my-flask-api                       │ │
│  └────────────────────────────────────────────────────────────┘ │
│  ✓ github.com/user/my-flask-api                    [Load Files]  │
│                                                                  │
├──────────────────────────────────────────────────────────────────┤
│  Select files to import:                    [Select All Python]  │
│  ──────────────────────────────────────────────────────────────  │
│  ▼ 📁 my-flask-api                                               │
│    ├── ☑ 📄 app.py (2.1 KB)                                     │
│    ├── ☑ 📄 config.py (856 B)                                   │
│    ├── ▼ 📁 models                                               │
│    │   ├── ☑ 📄 user.py (1.2 KB)                                │
│    │   └── ☑ 📄 post.py (980 B)                                 │
│    ├── ▶ 📁 tests (3 files)                      ☐              │
│    └── ▶ 📁 node_modules (1,234 files)           ☐              │
│                                                                  │
├──────────────────────────────────────────────────────────────────┤
│  Selected: 4 files (5.1 KB)                                      │
│                                                                  │
│                              [Cancel]    [Import & Analyze]      │
└──────────────────────────────────────────────────────────────────┘
```

---

## Implementation Plan

### Phase 1: Backend Git API Service

**New file: `backend/services/git_api_service.py`**

```python
import requests
from urllib.parse import urlparse
import base64
import os

class GitApiService:
    GITHUB_API_BASE = "https://api.github.com"

    def parse_github_url(self, url: str) -> dict:
        """
        Parse a GitHub URL and extract owner/repo.
        Returns: {valid: bool, owner: str, repo: str, error: str}
        """
        try:
            parsed = urlparse(url)
            if parsed.netloc != 'github.com':
                return {'valid': False, 'error': 'Only GitHub URLs are supported'}

            path_parts = [p for p in parsed.path.split('/') if p]
            if len(path_parts) < 2:
                return {'valid': False, 'error': 'Invalid GitHub URL format'}

            # Remove .git suffix if present
            repo = path_parts[1].replace('.git', '')

            return {
                'valid': True,
                'owner': path_parts[0],
                'repo': repo,
                'error': None
            }
        except Exception as e:
            return {'valid': False, 'error': str(e)}

    def get_repo_tree(self, owner: str, repo: str, branch: str = 'main') -> dict:
        """
        Fetch the complete file tree from GitHub API.
        Returns: {success: bool, files: list, error: str}
        """
        url = f"{self.GITHUB_API_BASE}/repos/{owner}/{repo}/git/trees/{branch}?recursive=1"

        try:
            response = requests.get(url, timeout=10)

            if response.status_code == 404:
                # Try 'master' branch if 'main' fails
                if branch == 'main':
                    return self.get_repo_tree(owner, repo, 'master')
                return {'success': False, 'error': 'Repository not found. Is it public?'}

            if response.status_code == 403:
                return {'success': False, 'error': 'GitHub API rate limit reached. Try again later.'}

            if response.status_code != 200:
                return {'success': False, 'error': f'GitHub API error: {response.status_code}'}

            data = response.json()
            files = []
            for item in data.get('tree', []):
                files.append({
                    'path': item['path'],
                    'type': 'file' if item['type'] == 'blob' else 'dir',
                    'size': item.get('size', 0)
                })

            return {
                'success': True,
                'files': files,
                'truncated': data.get('truncated', False),
                'branch': branch
            }

        except requests.exceptions.Timeout:
            return {'success': False, 'error': 'GitHub API request timed out'}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def get_file_content(self, owner: str, repo: str, path: str, branch: str = 'main') -> dict:
        """
        Fetch a single file's content from GitHub.
        Returns: {success: bool, content: str, error: str}
        """
        url = f"{self.GITHUB_API_BASE}/repos/{owner}/{repo}/contents/{path}?ref={branch}"

        try:
            response = requests.get(url, timeout=10)

            if response.status_code != 200:
                return {'success': False, 'error': f'Failed to fetch file: {path}'}

            data = response.json()

            # Content is base64 encoded
            content = base64.b64decode(data['content']).decode('utf-8')

            return {'success': True, 'content': content}

        except Exception as e:
            return {'success': False, 'error': str(e)}

    def download_files(self, owner: str, repo: str, paths: list,
                       target_dir: str, branch: str = 'main') -> dict:
        """
        Download multiple files and save to target directory.
        Returns: {success: bool, downloaded: int, errors: list}
        """
        os.makedirs(target_dir, exist_ok=True)
        downloaded = 0
        errors = []

        for path in paths:
            result = self.get_file_content(owner, repo, path, branch)

            if result['success']:
                # Create subdirectories if needed
                file_path = os.path.join(target_dir, path)
                os.makedirs(os.path.dirname(file_path), exist_ok=True)

                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(result['content'])
                downloaded += 1
            else:
                errors.append({'path': path, 'error': result['error']})

        return {
            'success': len(errors) == 0,
            'downloaded': downloaded,
            'errors': errors
        }
```

### Phase 2: Backend Endpoints

**Modify: `backend/routes/projects.py`**

```python
from services.git_api_service import GitApiService

# New endpoint: Get repository file tree
@projects_bp.route('/git/tree', methods=['GET'])
@jwt_required()
def get_git_tree():
    """Fetch file tree from a GitHub repository"""
    url = request.args.get('url')
    if not url:
        return jsonify({'error': 'URL parameter is required'}), 400

    git_service = GitApiService()

    # Parse URL
    parsed = git_service.parse_github_url(url)
    if not parsed['valid']:
        return jsonify({'error': parsed['error']}), 400

    # Get tree
    result = git_service.get_repo_tree(parsed['owner'], parsed['repo'])
    if not result['success']:
        return jsonify({'error': result['error']}), 400

    return jsonify({
        'owner': parsed['owner'],
        'repo': parsed['repo'],
        'branch': result['branch'],
        'files': result['files'],
        'truncated': result['truncated']
    })


# New endpoint: Import selected files from GitHub
@projects_bp.route('/<int:project_id>/import-git', methods=['POST'])
@jwt_required()
def import_from_git(project_id):
    """Import selected files from a GitHub repository"""
    user_id = int(get_jwt_identity())
    data = request.get_json()

    url = data.get('url')
    files = data.get('files', [])

    if not url or not files:
        return jsonify({'error': 'URL and files are required'}), 400

    if len(files) > 50:
        return jsonify({'error': 'Maximum 50 files can be imported at once'}), 400

    # Verify project ownership
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute('SELECT * FROM projects WHERE id = %s AND user_id = %s',
                    (project_id, user_id))
        project = cur.fetchone()

        if not project:
            return jsonify({'error': 'Project not found'}), 404

        git_service = GitApiService()

        # Parse URL
        parsed = git_service.parse_github_url(url)
        if not parsed['valid']:
            return jsonify({'error': parsed['error']}), 400

        # Download files
        upload_dir = os.path.join(Config.STORAGE_PATH, 'uploads',
                                  str(user_id), str(project_id))
        result = git_service.download_files(
            parsed['owner'], parsed['repo'], files, upload_dir
        )

        if not result['success'] and result['downloaded'] == 0:
            return jsonify({'error': 'Failed to download files'}), 500

        # Update project
        cur.execute('''
            UPDATE projects
            SET file_path = %s, git_url = %s, source_type = %s
            WHERE id = %s
        ''', (upload_dir, url, 'git', project_id))

        # Run analysis (same as upload flow)
        manager = ParserManager()
        language, framework = manager.detect_language_and_framework(upload_dir)

        cur.execute('''
            UPDATE projects SET language = %s, framework = %s
            WHERE id = %s
        ''', (language, framework, project_id))

        # Run parsers...
        # (same analysis logic as upload endpoint)

    return jsonify({
        'success': True,
        'downloaded': result['downloaded'],
        'errors': result['errors']
    })
```

### Phase 3: Frontend - GitImportModal Component

**New file: `frontend/src/components/dashboard/GitImportModal.jsx`**

Key features:
- URL input with validation
- "Load Files" button to fetch tree
- Expandable/collapsible folder tree
- Checkbox selection for files/folders
- "Select All Python" helper button
- File count and size display
- Import button with loading state

### Phase 4: Dashboard Integration

**Modify: `frontend/src/components/dashboard/Dashboard.jsx`**

Add "Import from Git" button:
```jsx
<button
  onClick={() => setShowGitImportModal(true)}
  className="flex items-center gap-2 px-4 py-2 bg-gray-700 text-white rounded-lg hover:bg-gray-600"
>
  <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
    {/* GitHub icon */}
  </svg>
  Import from Git
</button>
```

### Phase 5: API Service Updates

**Modify: `frontend/src/services/api.js`**

```javascript
// Add git methods
git: {
  getTree: (url) => api.get(`/projects/git/tree?url=${encodeURIComponent(url)}`),
  importFiles: (projectId, url, files) =>
    api.post(`/projects/${projectId}/import-git`, { url, files })
}
```

---

## Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `backend/services/git_api_service.py` | **Create** | GitHub API calls |
| `backend/routes/projects.py` | **Modify** | Add `/git/tree` and `/import-git` endpoints |
| `frontend/src/components/dashboard/GitImportModal.jsx` | **Create** | File browser modal |
| `frontend/src/components/dashboard/Dashboard.jsx` | **Modify** | Add "Import from Git" button |
| `frontend/src/services/api.js` | **Modify** | Add git API methods |

---

## GitHub API Rate Limits (Free)

| Mode | Limit | Notes |
|------|-------|-------|
| Unauthenticated | 60 req/hour | Shared across all users |
| With OAuth | 5,000 req/hour | Per authenticated user |

**MVP**: Start unauthenticated (60/hour - fine for small usage)
**Future**: Add "Login with GitHub" OAuth for higher limits

---

## Error Handling

| Error | User Message |
|-------|--------------|
| Invalid URL | "Please enter a valid GitHub repository URL (e.g., https://github.com/user/repo)" |
| Repo not found | "Repository not found. Make sure it exists and is public." |
| Private repo | "This repository is private. Only public repos are supported." |
| Rate limited | "GitHub API rate limit reached. Please wait a few minutes and try again." |
| File too large | "File exceeds size limit (1MB per file)" |

---

## Security

1. **URL validation**: Only allow github.com URLs
2. **No auth tokens stored**: API calls are unauthenticated (public repos only)
3. **File size limits**: Max 1MB per file, max 50 files per import
4. **Path validation**: Sanitize file paths before saving

---

## Verification Steps

1. Click "Import from Git" → modal should open
2. Enter valid GitHub URL → click "Load Files" → file tree should appear
3. Select files → click "Import & Analyze" → files downloaded, analysis runs
4. Enter private repo URL → should show friendly error
5. Enter invalid URL → should show validation error
6. Regular file upload → should still work unchanged

---

## Future Enhancements

- "Login with GitHub" OAuth for higher rate limits
- GitLab and Bitbucket support
- Branch selection dropdown
- Remember recently imported repos
- "Re-import" button to refresh from repo
