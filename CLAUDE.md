# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目目标

构建一个 **agentic 的、由 LLM agent 驱动的图像算法自动化系统**。用户输入一段提示词和一张图片，系统自动规划、执行、评估并迭代，最后返回处理结果。整个系统必须有计划、执行、感知、迭代、状态管理等 agentic 特征，**不能退化为简单的 workflow/pipeline**。

## 常用命令

### 后端（Python + Flask，uv 管理依赖）

```bash
# 安装依赖
uv sync

# 启动后端开发服务器（默认端口 5008）
cd backend && uv run python app.py

# 运行单个测试文件
cd backend && uv run python -m pytest tests/test_retrieval_agent.py -v

# 运行端到端测试
uv run python test_mvp_e2e.py
```

### 前端（React + pnpm）

```bash
cd frontend

# 安装依赖
pnpm install

# 启动开发服务器
pnpm dev

# 类型检查 + 构建
pnpm build

# 代码检查
pnpm lint
```

## 环境变量

在项目根目录创建 `.env` 文件（参考 `.env.example`）：

```
OPENROUTER_API_KEY=sk-...
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_MODEL=qwen/qwen-turbo
OPENROUTER_IMAGE_MODEL=qwen/qwen-vl-plus
TAVILY_API_KEY=tvly-dev-...
```

所有 LLM 调用通过 OpenRouter 代理，Tavily 用于联网检索。API 可用性已针对 `qwen/qwen-turbo`、`qwen/qwen-vl-plus` 和 Tavily 验证过。

## 架构概览

### Agentic 流程（核心）

`ControllerAgent` 是系统的核心编排器，管理完整的 agentic 循环。四个子 Agent 各司其职：

1. **RetrievalAgent** (`backend/agents/retrieval_agent.py`) — 真正的 agentic 搜索，非固定模板拼接。LLM 自主规划多角度搜索词 → Tavily 多路检索 → LLM 综合提取算法要点 → 质量自评。结果带 TTL 缓存（1小时）。
2. **CodeGenerationAgent** (`backend/agents/code_generation_agent.py`) — 基于检索简报 + 用户需求生成 Python 图像处理代码。有独立的系统上下文（已安装的库、OS 环境）。
3. **ExecutionAgent** (`backend/agents/execution_agent.py`) — 在本地执行生成的代码，捕获输出/错误，返回结果图片路径。
4. **EvaluationAgent** (`backend/agents/evaluation_agent.py`) — 评估生成图片质量，给出四维度评分（技术质量、内容匹配度、艺术效果、处理效果），驱动是否继续迭代的决策。

**迭代逻辑**：Controller 管理评分驱动的自动迭代。Evaluation 评分低于阈值时自动重新生成代码，直到达标或达到最大迭代次数。每轮迭代的结果和评分都记录在会话状态中。

### 会话与资源管理

`SessionResourceManager` (`backend/session_resources.py`) 管理每个 session 的磁盘资源布局：

```
sessions/<session_id>/
  uploads/        # 用户上传的图片
  outputs/        # 生成的输出图片
  workspace/      # 生成的 Python 代码文件
  state.json      # 会话状态快照
  state_logs.jsonl   # 状态日志（追加写）
  agent_calls.jsonl  # agent 调用记录（追加写）
```

`sessions/latest` 是指向最近 session 的符号链接。

### 后端 API（Flask, 端口 5008）

| 端点 | 方法 | 用途 |
|------|------|------|
| `/api/session/create` | POST | 创建新会话 |
| `/api/session/<id>` | GET | 获取会话完整状态 |
| `/api/sessions` | GET | 列出所有会话摘要 |
| `/api/process` | POST | 提交用户请求，启动 agentic 处理 |
| `/api/stream` | GET | SSE 事件流，实时推送处理进度 |
| `/api/upload` | POST | 上传图片 |
| `/api/feedback` | POST | 用户反馈（评分/接受/拒绝） |
| `/api/state-diagram/<id>` | GET | 会话的状态日志 |
| `/api/history` | GET | 全局状态历史 |
| `/api/session/<id>/output/<filename>` | GET | 获取输出图片 |
| `/api/session/<id>/files/<area>/<filename>` | GET | 获取会话资源文件 |

SSE 事件类型：`message`、`state`、`status`、`error`、`complete`。

### 前端（React + Zustand + TypeScript）

状态管理使用 Zustand (`frontend/src/store.ts`)，管理会话列表、消息、状态日志、UI 模式。

核心组件：
- `ChatWindow.tsx` — 消息展示区，渲染 assistant/user 消息
- `InputArea.tsx` — 用户输入（文本 + 图片上传）
- `MessageItem.tsx` — 单条消息渲染，支持 Markdown + 代码高亮
- `ProcessTimeline.tsx` — 可视化 agentic 处理时间线，展示各 agent 的状态流转
- `Sidebar.tsx` — 会话列表侧边栏

SSE 流通过 `api.ts` 中的 `openSessionStream()` 连接，支持 EventSource 主通道 + 轮询 fallback。

## 行为准则

- 不要主动调用浏览器，由用户操作
- 用户 shell 使用的是 fish，命令需符合 fish 格式
- 所有 LLM 调用均通过 OpenRouter API
