// ============================================================
// 枚举
// ============================================================

export const ProjectStatus = {
  QUEUED: 'queued',
  RUNNING: 'running',
  AWAITING_APPROVAL: 'awaiting_approval',
  COMPLETED: 'completed',
  FAILED: 'failed',
  CANCELLED: 'cancelled',
} as const;

export type ProjectStatus = (typeof ProjectStatus)[keyof typeof ProjectStatus];

export const StyleOption = {
  CINEMATIC: 'cinematic',
  ANIME: 'anime',
  CYBERPUNK: 'cyberpunk',
  INK_WASH: 'ink_wash',
  REALISTIC: 'realistic',
} as const;

export type StyleOption = (typeof StyleOption)[keyof typeof StyleOption];

// ============================================================
// 请求
// ============================================================

export interface CreateProjectRequest {
  prompt: string;
  style?: StyleOption;
  duration?: number;
  title?: string;
  language?: string;
  auto_approve?: boolean;
}

export interface RetryStageRequest {
  stage: string;
  feedback?: string;
}

// ============================================================
// 响应
// ============================================================

export interface HealthResponse {
  status: string;
  version: string;
  active_projects: number;
  queue_size: number;
}

export interface CreateProjectResponse {
  project_id: string;
  status: ProjectStatus;
  message: string;
}

export interface ProjectBrief {
  project_id: string;
  title: string | null;
  status: ProjectStatus;
  style: string;
  duration: number;
  created_at: string;
  progress_percent: number;
}

export interface StageProgress {
  stage_name: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  score: number | null;
  retry_count: number;
  message: string | null;
}

export interface ProjectDetail {
  project_id: string;
  title: string | null;
  status: ProjectStatus;
  style: string;
  duration: number;
  created_at: string;
  prompt: string;
  stages: StageProgress[];
  current_stage: string | null;
  video_url: string | null;
  screenplay_summary: string | null;
  quality_scores: Record<string, number | null>;
  error: string | null;
}

export interface ProjectListResponse {
  projects: ProjectBrief[];
  total: number;
  page: number;
  page_size: number;
}

export interface StyleInfo {
  id: string;
  name: string;
  description: string;
}

export interface DownloadResponse {
  project_id: string;
  video_url: string;
  title: string | null;
}
