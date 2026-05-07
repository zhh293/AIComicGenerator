# AI Film Studio 前端开发文档

## 项目背景

AI Film Studio 是一个多 Agent 协作的 AI 短剧自动生成平台。后端基于 FastAPI + CrewAI，提供 RESTful API。本文档为前端开发提供完整的接口对接、页面设计和交互逻辑参考。

---

## 技术栈建议

| 层面 | 选型 | 理由 |
|------|------|------|
| 框架 | React 18 + TypeScript | 类型安全，生态丰富 |
| 构建工具 | Vite | 开发体验好，HMR 快 |
| UI 组件库 | Ant Design 5 | 企业级组件，表单/表格/进度条齐全 |
| 状态管理 | Zustand | 轻量，适合中小型项目 |
| 请求库 | axios + react-query | 自动缓存、轮询、重试 |
| 图表 | ECharts 或 Recharts | 情绪曲线可视化 |
| 路由 | React Router v6 | |
| 样式 | Tailwind CSS + CSS Modules | 快速布局 + 组件隔离 |

---

## 后端 API 概览

基础地址：`http://localhost:8000/api/v1`

后端已配置 CORS 全开放（开发环境），前端直连即可。

### 接口列表

| 方法 | 路径 | 说明 | 请求体 | 响应 |
|------|------|------|--------|------|
| GET | `/health` | 健康检查 | - | `HealthResponse` |
| POST | `/projects` | 创建项目 | `CreateProjectRequest` | `CreateProjectResponse` |
| GET | `/projects` | 项目列表 | query: page, page_size, status | `ProjectListResponse` |
| GET | `/projects/{id}` | 项目详情 | - | `ProjectDetail` |
| DELETE | `/projects/{id}` | 取消项目 | - | `{message}` |
| POST | `/projects/{id}/approve` | 审批剧本 | - | `{message}` |
| POST | `/projects/{id}/retry` | 重试阶段 | `RetryStageRequest` | `{message}` |
| GET | `/projects/{id}/download` | 下载成片 | - | `{project_id, video_url, title}` |
| GET | `/styles` | 风格列表 | - | `StyleOption[]` |

### Swagger 文档

启动后端后访问 `http://localhost:8000/docs` 可查看完整的交互式 API 文档。

---

## 数据模型定义

以下 TypeScript 类型定义与后端 Pydantic schema 一一对应。

```typescript
// ============================================================
// 枚举
// ============================================================

enum ProjectStatus {
  QUEUED = "queued",
  RUNNING = "running",
  AWAITING_APPROVAL = "awaiting_approval",
  COMPLETED = "completed",
  FAILED = "failed",
  CANCELLED = "cancelled",
}

enum StyleOption {
  CINEMATIC = "cinematic",
  ANIME = "anime",
  CYBERPUNK = "cyberpunk",
  INK_WASH = "ink_wash",
  REALISTIC = "realistic",
}

// ============================================================
// 请求
// ============================================================

interface CreateProjectRequest {
  prompt: string;          // 10-5000 字符，用户的故事描述
  style?: StyleOption;     // 默认 cinematic
  duration?: number;       // 15-180 秒，默认 60
  title?: string;          // 可选自定义标题，最长 100
  language?: string;       // zh / en / ja，默认 zh
  auto_approve?: boolean;  // 默认 true，false 则剧本生成后暂停
}

interface RetryStageRequest {
  stage: string;           // "screenplay" | "assets" | "composition"
  feedback?: string;       // 附加修改建议
}

// ============================================================
// 响应
// ============================================================

interface HealthResponse {
  status: string;
  version: string;
  active_projects: number;
  queue_size: number;
}

interface CreateProjectResponse {
  project_id: string;
  status: ProjectStatus;
  message: string;
}

interface ProjectBrief {
  project_id: string;
  title: string | null;
  status: ProjectStatus;
  style: string;
  duration: number;
  created_at: string;       // ISO 时间
  progress_percent: number; // 0-100
}

interface StageProgress {
  stage_name: string;
  status: "pending" | "running" | "completed" | "failed";
  score: number | null;
  retry_count: number;
  message: string | null;
}

interface ProjectDetail {
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

interface ProjectListResponse {
  projects: ProjectBrief[];
  total: number;
  page: number;
  page_size: number;
}

interface StyleInfo {
  id: string;
  name: string;
  description: string;
}
```

---

## 页面结构

```
/                         → 首页/仪表盘
/create                   → 创建新项目
/projects                 → 项目列表
/projects/:id             → 项目详情（进度跟踪）
/projects/:id/approve     → 剧本审批页
/projects/:id/result      → 成片预览与下载
```

### 1. 首页 / 仪表盘 (`/`)

展示内容：

- 系统状态卡片（活跃项目数、队列大小、服务版本）— 数据来自 `GET /health`
- 最近项目列表（取最新 5 个）— 数据来自 `GET /projects?page=1&page_size=5`
- 快速创建入口按钮

交互逻辑：

- 页面加载时调用 `/health` 获取系统状态
- 每 10 秒轮询一次 `/health` 更新活跃状态
- 点击项目卡片跳转到详情页

### 2. 创建项目 (`/create`)

表单字段：

| 字段 | 组件类型 | 验证规则 |
|------|----------|----------|
| 故事描述 (prompt) | TextArea | 必填，10-5000 字 |
| 风格 (style) | Select/卡片选择 | 从 `GET /styles` 获取选项 |
| 目标时长 (duration) | Slider | 15-180秒，步长 5 |
| 自定义标题 (title) | Input | 可选，最长 100 |
| 语言 (language) | Radio | zh / en / ja |
| 自动审批 (auto_approve) | Switch | 默认开启 |

交互逻辑：

- 页面加载时调用 `GET /styles` 获取风格列表，以卡片形式展示（带封面图和描述）
- 提交调用 `POST /projects`
- 成功后跳转到 `/projects/:id` 进度页
- 失败时展示错误提示

风格选择器建议设计：每个风格用一张代表性图片 + 名称 + 一行描述，选中态高亮。

### 3. 项目列表 (`/projects`)

展示方式：表格或卡片网格。

列/字段：项目标题、风格标签、状态徽标、时长、进度条、创建时间。

交互逻辑：

- 支持按状态筛选（tabs 或下拉：全部 / 进行中 / 待审批 / 已完成 / 失败）
- 分页，默认 page_size=20
- 点击行跳转详情
- "待审批"状态行有特殊高亮提示
- 每 5 秒轮询刷新列表（如果有 running 状态的项目）

### 4. 项目详情 / 进度追踪 (`/projects/:id`)

这是核心页面，需要实时展示生产流水线的进度。

布局建议（三栏/三段式）：

**顶部信息栏：** 项目标题、风格标签、状态大标、进度百分比环形图。

**中部流水线可视化：** 水平步骤条展示五大阶段（初始化 → 剧本创作 → 素材生成 → 视频合成 → 完成），每个步骤显示状态图标和质量分数。当前执行阶段有动画效果。

**底部详情区：**

- Tab 1「剧本」：展示 `screenplay_summary`，待审批时显示完整剧本内容 + 审批按钮
- Tab 2「情绪曲线」：ECharts 折线图，横轴 scene_id，纵轴展示 tension/valence/energy 三条线
- Tab 3「质量报告」：各阶段评分雷达图
- Tab 4「错误日志」：如果 `error` 不为空则展示

交互逻辑：

- 页面加载调用 `GET /projects/:id`
- 如果 status 为 running 或 awaiting_approval，每 3 秒轮询一次
- 状态变为 completed 时停止轮询，展示成片入口
- 状态变为 awaiting_approval 时突出显示审批入口
- 取消按钮调用 `DELETE /projects/:id`
- 重试按钮调用 `POST /projects/:id/retry`

### 5. 剧本审批 (`/projects/:id/approve`)

可以做成详情页的一个 Modal 或独立页面。

展示内容：

- 剧本概要（title, logline, synopsis）
- 场景列表预览（每个场景的 mood、时长、角色）
- 情绪曲线折线图
- 审批操作区

操作：

- 「通过」按钮 → 调用 `POST /projects/:id/approve` → 成功后跳回详情页（状态变 running）
- 「打回重做」按钮 → 调用 `POST /projects/:id/retry` 并附带 feedback → 可弹窗让用户输入修改意见

### 6. 成片预览 (`/projects/:id/result`)

展示内容：

- 视频播放器（HTML5 video 标签，src 从 `GET /projects/:id/download` 获取 video_url）
- 项目元信息卡片（风格、时长、质量分数）
- 下载按钮
- 情绪曲线回顾图

---

## 轮询策略

由于后端没有 WebSocket（当前是 REST 轮询模式），前端需要根据项目状态智能控制轮询频率。

```typescript
function getPollingInterval(status: ProjectStatus): number | null {
  switch (status) {
    case ProjectStatus.QUEUED:
      return 5000;   // 排队中，5秒一次
    case ProjectStatus.RUNNING:
      return 3000;   // 运行中，3秒一次
    case ProjectStatus.AWAITING_APPROVAL:
      return 10000;  // 待审批，10秒一次（主要靠用户主动操作）
    default:
      return null;   // 终态（completed/failed/cancelled），停止轮询
  }
}
```

使用 react-query 的 `refetchInterval` 可以很自然地实现：

```typescript
const { data } = useQuery({
  queryKey: ["project", projectId],
  queryFn: () => fetchProjectDetail(projectId),
  refetchInterval: (data) => getPollingInterval(data?.status) ?? false,
});
```

---

## 情绪曲线可视化

后端在剧本生成后会自动计算情绪曲线并存入 `FilmProjectState.emotion_curve_data`。当前 API 的 `ProjectDetail` 没有直接暴露这个字段，需要后端新增一个接口或在 ProjectDetail 中补充。

建议后端新增：

```
GET /api/v1/projects/{id}/emotion-curve
→ { points: [{ scene_id, tension, valence, energy, mood_label }] }
```

前端可视化方案：

```
- 图表类型：多折线图 (Line Chart)
- X 轴：场景序号 (scene_id)
- Y 轴：数值
- 三条线：
  - tension (红色) — 张力
  - valence (蓝色) — 情感极性（可以用渐变色表示正负）
  - energy (橙色) — 能量/节奏
- 交互：hover 显示 mood_label 和具体数值
- 标注：在 climax 点（tension 最高处）加一个标记
```

---

## 风格选择器数据

调用 `GET /api/v1/styles` 返回格式：

```json
[
  { "id": "cinematic", "name": "电影感", "description": "高对比度、浅景深..." },
  { "id": "anime", "name": "动漫风", "description": "赛璐璐着色、干净线条..." },
  { "id": "cyberpunk", "name": "赛博朋克", "description": "霓虹灯、暗调..." },
  { "id": "ink_wash", "name": "水墨画", "description": "中国传统水墨..." },
  { "id": "realistic", "name": "写实", "description": "照片级真实感..." }
]
```

前端可以为每种风格本地预置一张缩略图（放在 `public/styles/` 目录），文件名与 id 对应。

---

## 状态流转与 UI 对应

```
queued (排队中)
  ↓
running (生产中)
  ├── initialization → 正在初始化...
  ├── screenplay_creation → 剧本创作中...
  ├── screenplay_quality_check → 剧本质检中...
  ├── asset_generation → 素材生成中... (最耗时)
  ├── asset_quality_check → 素材质检中...
  ├── video_composition → 视频合成中...
  └── final_quality_check → 最终质检中...
  ↓
awaiting_approval (待审批)  ← 仅当 auto_approve=false
  ↓ 用户点击 approve
running (继续生产)
  ↓
completed (完成)  /  failed (失败)
```

UI 状态映射建议：

| 状态 | 徽标颜色 | 图标 | 描述文案 |
|------|----------|------|----------|
| queued | 灰色 | 🕐 | 排队等待中 |
| running | 蓝色(动画) | ⚙️ | 生产进行中 |
| awaiting_approval | 橙色 | ✋ | 等待审批 |
| completed | 绿色 | ✅ | 制作完成 |
| failed | 红色 | ❌ | 生产失败 |
| cancelled | 灰色 | 🚫 | 已取消 |

---

## 目录结构建议

```
ai-film-studio/
├── frontend/                    # 前端项目根目录
│   ├── public/
│   │   ├── styles/              # 风格缩略图
│   │   └── favicon.ico
│   ├── src/
│   │   ├── api/                 # API 请求封装
│   │   │   ├── client.ts        # axios 实例配置
│   │   │   ├── projects.ts      # 项目相关 API
│   │   │   └── types.ts         # TypeScript 类型定义
│   │   ├── components/          # 通用组件
│   │   │   ├── Layout/          # 页面布局
│   │   │   ├── StatusBadge/     # 状态徽标
│   │   │   ├── StyleCard/       # 风格选择卡片
│   │   │   ├── EmotionChart/    # 情绪曲线图表
│   │   │   ├── PipelineSteps/   # 流水线步骤条
│   │   │   └── VideoPlayer/     # 视频播放器
│   │   ├── pages/               # 页面级组件
│   │   │   ├── Dashboard/
│   │   │   ├── Create/
│   │   │   ├── ProjectList/
│   │   │   ├── ProjectDetail/
│   │   │   └── Result/
│   │   ├── stores/              # Zustand 状态管理
│   │   │   └── projectStore.ts
│   │   ├── hooks/               # 自定义 hooks
│   │   │   ├── usePolling.ts
│   │   │   └── useProject.ts
│   │   ├── utils/               # 工具函数
│   │   ├── App.tsx
│   │   ├── main.tsx
│   │   └── router.tsx
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   └── tailwind.config.js
└── src/                         # 后端代码（已有）
```

---

## 开发环境搭建

```bash
# 1. 进入前端目录
cd ai-film-studio/frontend

# 2. 初始化项目
npm create vite@latest . -- --template react-ts

# 3. 安装依赖
npm install antd @ant-design/icons axios @tanstack/react-query zustand
npm install react-router-dom echarts echarts-for-react
npm install -D tailwindcss postcss autoprefixer @types/react-router-dom

# 4. 初始化 tailwind
npx tailwindcss init -p

# 5. 启动开发服务器
npm run dev
# 前端跑在 http://localhost:5173

# 6. 启动后端
cd ..
uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
# 后端跑在 http://localhost:8000
```

Vite 代理配置（解决开发环境跨域，虽然后端已开 CORS）：

```typescript
// vite.config.ts
export default defineConfig({
  server: {
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
```

---

## API 请求封装示例

```typescript
// src/api/client.ts
import axios from "axios";

const apiClient = axios.create({
  baseURL: "/api/v1",
  timeout: 30000,
  headers: { "Content-Type": "application/json" },
});

// 响应拦截：统一错误处理
apiClient.interceptors.response.use(
  (res) => res.data,
  (err) => {
    const message = err.response?.data?.detail || "请求失败";
    // 触发全局通知
    console.error(`[API Error] ${err.config.url}: ${message}`);
    return Promise.reject(err);
  }
);

export default apiClient;
```

```typescript
// src/api/projects.ts
import apiClient from "./client";
import type {
  CreateProjectRequest,
  CreateProjectResponse,
  ProjectDetail,
  ProjectListResponse,
  StyleInfo,
} from "./types";

export const projectApi = {
  create: (data: CreateProjectRequest) =>
    apiClient.post<CreateProjectResponse>("/projects", data),

  list: (params: { page?: number; page_size?: number; status?: string }) =>
    apiClient.get<ProjectListResponse>("/projects", { params }),

  getDetail: (id: string) =>
    apiClient.get<ProjectDetail>(`/projects/${id}`),

  approve: (id: string) =>
    apiClient.post(`/projects/${id}/approve`),

  cancel: (id: string) =>
    apiClient.delete(`/projects/${id}`),

  retry: (id: string, stage: string, feedback?: string) =>
    apiClient.post(`/projects/${id}/retry`, { stage, feedback }),

  getDownload: (id: string) =>
    apiClient.get(`/projects/${id}/download`),

  getStyles: () =>
    apiClient.get<StyleInfo[]>("/styles"),
};
```

---

## 关键交互流程

### 创建项目 → 等待完成

```
用户填写表单 → POST /projects → 获取 project_id
  → 跳转详情页 → 开始轮询 GET /projects/:id
  → status=running 时展示进度动画
  → status=completed 时停止轮询，显示"查看成片"按钮
```

### 人工审批流程

```
创建时 auto_approve=false
  → status 变为 awaiting_approval
  → 前端展示剧本预览 + 审批操作区
  → 用户点击「通过」→ POST /projects/:id/approve
  → status 变回 running，继续轮询
  → 用户点击「打回」→ POST /projects/:id/retry { stage: "screenplay", feedback: "..." }
```

### 失败重试

```
status=failed → 展示错误信息 + 重试按钮
  → 用户选择重试阶段并附加 feedback
  → POST /projects/:id/retry
  → status 变回 running
```

---

## 后端待补充接口建议

当前后端 API 基本满足前端需求，但为了更好的体验，建议后端补充以下接口：

1. **情绪曲线接口**
   - `GET /api/v1/projects/{id}/emotion-curve`
   - 返回 `{ points: EmotionPoint[] }`
   - 前端用于绘制情绪折线图

2. **剧本详情接口**
   - `GET /api/v1/projects/{id}/screenplay`
   - 返回完整的 Screenplay 对象（title, scenes, characters 等）
   - 用于审批页面展示完整剧本

3. **SSE/WebSocket 实时推送**（可选，优先级低）
   - `GET /api/v1/projects/{id}/stream` (SSE)
   - 替代轮询，实时推送阶段变化和进度更新
   - 可以后期优化时再加

---

## 注意事项

1. 后端 API 前缀是 `/api/v1`，前端请求要对齐。
2. 所有时间字段都是 UTC ISO 格式，前端显示时转为本地时间。
3. `video_url` 目前是本地文件路径，前端需要后端额外提供静态文件服务（或改为 URL）。建议后端在 FastAPI 中挂载 static files：`app.mount("/files", StaticFiles(directory="output"))`。
4. 项目 ID 是 UUID 前 12 位（如 `a1b2c3d4e5f6`），URL 安全。
5. 风格缩略图需要前端自行准备，放在 `public/styles/{style_id}.jpg`。
6. 开发时后端的 `auto_approve` 默认为 true，测试审批流程时记得传 false。
