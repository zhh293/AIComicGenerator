# AI Film Studio

基于 CrewAI 多智能体架构的 AI 短剧/短片端到端生成平台。输入一段文字描述，自动完成剧本创作、素材生成、视频合成的全流程，输出一部完整短片。

## 核心理念

用 AI Agent 模拟真实影视制作团队的分工协作——编剧、导演、摄影、音频、调色各司其职，通过 CrewAI Flow 编排多阶段流水线，以质量检查+自动重试机制确保产出质量。

## 架构概览

```
用户输入 (文字创意)
       │
       ▼
┌─────────────────────────────────────────────┐
│  Stage 1: 初始化                              │
│  解析用户输入，确定风格配置                      │
└────────────────────┬────────────────────────┘
                     ▼
┌─────────────────────────────────────────────┐
│  Stage 2-3: 剧本创作 + 质量检查                │
│  ScreenplayCrew (3 Agents)                   │
│  · 故事架构师 → 三幕结构                       │
│  · 分镜编剧 → 场景序列 + visual prompt         │
│  · 角色设计师 → 精确视觉档案                    │
│  不通过 → 自动重试（附带修改建议）                │
└────────────────────┬────────────────────────┘
                     ▼
┌─────────────────────────────────────────────┐
│  Stage 4-5: 素材生成 + 质量检查                │
│  AssetGenerationCrew (3 Agents)              │
│  · 视觉导演 → 视频片段 + 关键帧                 │
│  · 音频制作人 → TTS 配音 (+ 背景音乐)          │
│  · 一致性检查员 → 角色/风格/连续性验证           │
└────────────────────┬────────────────────────┘
                     ▼
┌─────────────────────────────────────────────┐
│  Stage 6-7: 视频合成 + 最终检查                │
│  VideoCompositionCrew (3 Agents)             │
│  · 视频剪辑师 → 片段拼接 + 转场               │
│  · 音频混音师 → 音轨混合 + 响度标准化           │
│  · 调色师 → 全片色彩统一 + 风格化              │
└────────────────────┬────────────────────────┘
                     ▼
              最终成片 (MP4)
```

## 技术栈

| 模块 | 技术选型 | 说明 |
|------|----------|------|
| Agent 框架 | CrewAI (Flow + Crew) | 多 Agent 编排与协作 |
| LLM | DeepSeek (OpenAI 兼容) | 性价比极高的国产大模型 |
| 语音合成 | Edge-TTS (微软免费) | 多语言神经网络 TTS，无需 API Key |
| 视频生成 | Kling / Runway / Pika | 可切换的视频生成 API |
| 视频处理 | FFmpeg | 拼接、转场、调色、混音、字幕 |
| 背景音乐 | Suno (可选，默认关闭) | 后期可自行剪辑配乐 |
| 图片生成 | DALL-E / Stable Diffusion | 角色参考图、关键帧 |
| API 服务 | FastAPI | RESTful API + 异步任务管理 |
| 配置管理 | pydantic-settings | 环境变量 + .env 文件 |

## 项目结构

```
ai-film-studio/
├── config/
│   ├── api_keys.env.example   # 环境变量模板
│   └── api_keys.env           # 实际配置（不入库）
├── luts/                      # 调色 LUT 文件
├── output/                    # 成片输出目录
├── temp/                      # 中间文件临时目录
├── src/
│   ├── main.py                # FastAPI 服务入口
│   ├── config.py              # 全局配置管理
│   ├── llm.py                 # LLM 工厂函数
│   ├── api/                   # API 路由层
│   │   ├── routes.py          # 路由定义
│   │   ├── schemas.py         # 请求/响应模型
│   │   └── task_manager.py    # 异步任务管理器
│   ├── crews/                 # CrewAI Crew 定义
│   │   ├── screenplay_crew.py       # 剧本创作 Crew
│   │   ├── asset_generation_crew.py  # 素材生成 Crew
│   │   └── video_composition_crew.py # 视频合成 Crew
│   ├── flow/                  # Flow 编排层
│   │   ├── film_production_flow.py   # 主控 Flow（8 阶段流水线）
│   │   └── state.py           # 全局状态模型（Pydantic）
│   ├── tools/                 # CrewAI Tools 封装
│   │   ├── video_gen_tool.py  # 视频生成（Kling/Runway/Pika）
│   │   ├── image_gen_tool.py  # 图片生成
│   │   ├── tts_tool.py        # 语音合成（Edge-TTS）
│   │   ├── music_gen_tool.py  # 音乐生成（Suno，可选）
│   │   └── ffmpeg_tools.py    # FFmpeg 工具集
│   ├── style/                 # 风格系统
│   │   ├── presets.py         # 内置风格预设（5 种）
│   │   ├── prompt_engine.py   # Prompt 工程引擎
│   │   └── api_adapter.py     # 多平台 API 格式适配
│   ├── consistency/           # 一致性保障
│   │   ├── character_manager.py    # 角色一致性管理
│   │   ├── scene_continuity.py     # 场景连续性管理
│   │   └── style_anchor.py         # 风格锚定
│   └── quality/               # 质量控制
│       ├── evaluators.py      # 质量评估器
│       └── retry_strategy.py  # 智能重试策略
└── pyproject.toml             # 项目依赖配置
```

## 内置风格

| 风格 | 说明 |
|------|------|
| 电影质感 (cinematic) | 好莱坞级画面，浅景深，温暖色调，变形宽荧幕 |
| 日系动漫 (anime) | 新海诚光影 + 吉卜力温暖，赛璐璐着色 |
| 赛博朋克 (cyberpunk) | 霓虹暗夜，高对比度，品红/青色光污染 |
| 水墨中国风 (ink_wash) | 传统水墨韵味，留白写意，宋代山水美学 |
| 写实纪录 (realistic) | 纪录片质感，自然光线，真实色彩 |

每种风格包含完整的视觉前缀、调色参数、镜头偏好、音频风格和转场偏好配置。

## 快速开始

### 1. 环境要求

- Python >= 3.11
- FFmpeg（需在 PATH 中）
- DeepSeek API Key

### 2. 安装依赖

```bash
cd ai-film-studio
pip install -e .
```

### 3. 配置

```bash
cp config/api_keys.env.example config/api_keys.env
```

编辑 `config/api_keys.env`，填入必要的 API Key：

```env
# 必须：LLM（DeepSeek）
OPENAI_API_KEY=sk-your-deepseek-key
OPENAI_API_BASE=https://api.deepseek.com
OPENAI_MODEL_NAME=deepseek-chat

# 必须：视频生成（至少配一个）
KLING_API_KEY=your-kling-key

# 可选：TTS 音色配置（Edge-TTS 无需 Key）
TTS_DEFAULT_VOICE=zh-CN-XiaoxiaoNeural

# 可选：音乐生成（默认关闭）
ENABLE_MUSIC_GENERATION=false
```

### 4. 启动服务

```bash
uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

访问 `http://localhost:8000/docs` 查看 API 文档。

### 5. 创建一个短片项目

```bash
curl -X POST http://localhost:8000/api/v1/projects \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "一个独居老人在雨天收到了一封来自三十年前自己写的信，信中预言了他现在的生活",
    "style": "cinematic",
    "duration": 60
  }'
```

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/health` | 健康检查 |
| POST | `/api/v1/projects` | 创建项目（开始生成） |
| GET | `/api/v1/projects` | 项目列表 |
| GET | `/api/v1/projects/{id}` | 项目详情与进度 |
| DELETE | `/api/v1/projects/{id}` | 取消项目 |
| POST | `/api/v1/projects/{id}/retry` | 手动触发某阶段重试 |
| GET | `/api/v1/projects/{id}/download` | 获取成片下载地址 |
| GET | `/api/v1/styles` | 可用风格列表 |

## 关键设计

### 质量控制 & 自动重试

每个核心阶段（剧本、素材、成片）完成后都有质量评估环节。评分低于阈值时，系统会自动带上改进建议进行重试，最多重试 3 次。阈值可在配置中调整：

```env
QUALITY_THRESHOLD_SCREENPLAY=0.8
QUALITY_THRESHOLD_VISUAL=0.75
QUALITY_THRESHOLD_AUDIO=0.7
```

### 一致性保障

AI 生成最大的挑战是多场景间的一致性。本项目通过三层机制解决：

- **角色一致性** — 精确的视觉档案（量化到色号、厘米），作为每次生成的 prompt 约束
- **风格锚定** — 首场景作为全片视觉锚点，后续场景参考锚点保持统一
- **场景连续性** — 上一场景末帧作为下一场景首帧参考，确保转接自然

### 成本结构

| 模块 | 成本 |
|------|------|
| LLM (DeepSeek) | 极低（约 ¥0.01/千 token） |
| TTS (Edge-TTS) | 免费 |
| 背景音乐 | 免费（已关闭，自行剪辑） |
| 视频生成 | 按量付费（Kling 最经济） |
| 图片生成 | 按量付费 |

一部 60 秒短片的 LLM + TTS 成本基本可以忽略不计，主要开销在视频/图片生成 API。

## 开发

```bash
# 安装开发依赖
pip install -e ".[dev]"

# 代码检查
ruff check src/

# 运行测试
pytest tests/ -v
```

## License

MIT
