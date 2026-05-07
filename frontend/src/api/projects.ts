import apiClient from './client';
import type {
  CreateProjectRequest,
  CreateProjectResponse,
  DownloadResponse,
  HealthResponse,
  ProjectDetail,
  ProjectListResponse,
  StyleInfo,
} from './types';

export const projectApi = {
  health: () => apiClient.get('/health') as Promise<HealthResponse>,

  create: (data: CreateProjectRequest) =>
    apiClient.post('/projects', data) as Promise<CreateProjectResponse>,

  list: (params: { page?: number; page_size?: number; status?: string }) =>
    apiClient.get('/projects', { params }) as Promise<ProjectListResponse>,

  getDetail: (id: string) =>
    apiClient.get(`/projects/${id}`) as Promise<ProjectDetail>,

  approve: (id: string) =>
    apiClient.post(`/projects/${id}/approve`) as Promise<{ message: string }>,

  cancel: (id: string) =>
    apiClient.delete(`/projects/${id}`) as Promise<{ message: string }>,

  retry: (id: string, stage: string, feedback?: string) =>
    apiClient.post(`/projects/${id}/retry`, { stage, feedback }) as Promise<{ message: string }>,

  getDownload: (id: string) =>
    apiClient.get(`/projects/${id}/download`) as Promise<DownloadResponse>,

  getStyles: () => apiClient.get('/styles') as Promise<StyleInfo[]>,
};
