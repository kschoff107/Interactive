import axios from 'axios';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:5000/api';

const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add token to requests
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Auth endpoints
export const authAPI = {
  register: (username, email, password) =>
    api.post('/auth/register', { username, email, password }),
  login: (username, password) =>
    api.post('/auth/login', { username, password }),
};

// Project endpoints
export const projectsAPI = {
  list: () => api.get('/projects'),
  create: (name, description) => api.post('/projects', { name, description }),
  get: (id) => api.get(`/projects/${id}`),
  upload: (id, files) => {
    const formData = new FormData();
    files.forEach((file) => formData.append('files', file));
    return api.post(`/projects/${id}/upload`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  getFiles: (id) => api.get(`/projects/${id}/files`),
  // Layout endpoints
  getLayout: (id) => api.get(`/projects/${id}/layout`),
  saveLayout: (id, layoutData) =>
    api.post(`/projects/${id}/layout`, { layout_data: layoutData }),
};

// Workspace endpoints
export const workspacesAPI = {
  list: (projectId) => api.get(`/projects/${projectId}/workspaces`),
  create: (projectId, analysisType, name) =>
    api.post(`/projects/${projectId}/workspaces`, { analysis_type: analysisType, name }),
  rename: (projectId, workspaceId, name) =>
    api.patch(`/projects/${projectId}/workspaces/${workspaceId}`, { name }),
  delete: (projectId, workspaceId) =>
    api.delete(`/projects/${projectId}/workspaces/${workspaceId}`),
  getLayout: (projectId, workspaceId) =>
    api.get(`/projects/${projectId}/workspaces/${workspaceId}/layout`),
  saveLayout: (projectId, workspaceId, layoutData) =>
    api.post(`/projects/${projectId}/workspaces/${workspaceId}/layout`, { layout_data: layoutData }),
  getRuntimeFlow: (projectId, workspaceId) =>
    api.get(`/projects/${projectId}/workspaces/${workspaceId}/runtime-flow`),
  analyzeRuntimeFlow: (projectId, workspaceId) =>
    api.post(`/projects/${projectId}/workspaces/${workspaceId}/analyze/runtime-flow`),
  getApiRoutes: (projectId, workspaceId) =>
    api.get(`/projects/${projectId}/workspaces/${workspaceId}/api-routes`),
  analyzeApiRoutes: (projectId, workspaceId) =>
    api.post(`/projects/${projectId}/workspaces/${workspaceId}/analyze/api-routes`),
  analyzeDatabaseSchema: (projectId, workspaceId) =>
    api.post(`/projects/${projectId}/workspaces/${workspaceId}/analyze/database-schema`),
  getAnalysis: (projectId, workspaceId) =>
    api.get(`/projects/${projectId}/workspaces/${workspaceId}/analysis`),
  // Workspace file management
  uploadFiles: (projectId, workspaceId, files) => {
    const formData = new FormData();
    files.forEach((file) => formData.append('files', file));
    return api.post(`/projects/${projectId}/workspaces/${workspaceId}/upload`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  listFiles: (projectId, workspaceId) =>
    api.get(`/projects/${projectId}/workspaces/${workspaceId}/files`),
  deleteFile: (projectId, workspaceId, fileId) =>
    api.delete(`/projects/${projectId}/workspaces/${workspaceId}/files/${fileId}`),
  importSourceFiles: (projectId, workspaceId, paths) =>
    api.post(`/projects/${projectId}/workspaces/${workspaceId}/import-source`, { paths }),
  getCodeStructure: (projectId, workspaceId) =>
    api.get(`/projects/${projectId}/workspaces/${workspaceId}/code-structure`),
  analyzeCodeStructure: (projectId, workspaceId) =>
    api.post(`/projects/${projectId}/workspaces/${workspaceId}/analyze/code-structure`),
};

// Git import endpoints
export const gitAPI = {
  getTree: (url, config) =>
    api.get(`/projects/git/tree?url=${encodeURIComponent(url)}`, config),
  importFiles: (projectId, url, files, branch) =>
    api.post(`/projects/${projectId}/import-git`, { url, files, branch }),
};

export default api;
