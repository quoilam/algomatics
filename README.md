# Algomatics

Algomatics is a demo of an agentic image-algorithm automation system. A user provides a prompt and an image, then the backend lets several LLM-driven agents plan, search, generate Python image-processing code, execute it, evaluate the result, and iterate until the output is acceptable or the iteration limit is reached.

The goal of this repository is to make the demo easy to understand and run locally. It is not packaged as a production deployment.

## What This Demo Shows

- A `ControllerAgent` that owns the full agentic loop instead of a fixed pipeline.
- Dedicated agents for retrieval, code generation, execution, and visual evaluation.
- Score-driven automatic iteration when the generated image is not good enough.
- Session-level state, generated code, outputs, and agent call logs on disk.
- A React frontend that streams status updates and renders the agent timeline.
- A PPT-style architecture report in [`ppt/index.html`](ppt/index.html) and [`ppt/algomatics-agentic-report.pdf`](ppt/algomatics-agentic-report.pdf).

## Repository Layout

```text
.
├── backend/                  # Flask API and agent implementation
│   ├── agents/               # Retrieval, code generation, execution, evaluation agents
│   ├── controller/           # ControllerAgent, planning, task parsing, coordination
│   ├── knowledge/            # Lightweight knowledge base
│   └── tests/                # Backend-focused tests
├── frontend/                 # React + TypeScript + Zustand UI
├── docs/                     # Design notes and MVP reports
├── ppt/                      # Demo presentation and exported pages
├── test_mvp_e2e.py           # End-to-end MVP smoke script
├── pyproject.toml            # Python dependencies for uv
└── .env.example              # Required environment variables template
```

## Prerequisites

- Python 3.12+
- [`uv`](https://docs.astral.sh/uv/) for Python dependency management
- Node.js 18+ and pnpm 8+
- OpenRouter API key
- Tavily API key

All LLM calls go through OpenRouter. Tavily is used for web retrieval.

## Setup

Clone the repository, then install backend dependencies from the repository root:

```bash
uv sync
```

Create your local environment file:

```bash
cp .env.example .env
```

Fill in the real values:

```env
OPENROUTER_API_KEY=sk-...
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_MODEL=qwen/qwen-turbo
OPENROUTER_IMAGE_MODEL=qwen/qwen-vl-plus
TAVILY_API_KEY=tvly-dev-...
```

Install frontend dependencies:

```bash
cd frontend
pnpm install
```

## Run Locally

Start the backend from the repository root:

```bash
cd backend
uv run python app.py
```

The backend listens on `http://127.0.0.1:5008`.

In another terminal, start the frontend:

```bash
cd frontend
pnpm dev
```

Open `http://localhost:5173`.

The frontend defaults to `http://127.0.0.1:5008/api`. If your backend runs somewhere else, create `frontend/.env`:

```env
VITE_API_BASE_URL=http://127.0.0.1:5008
```

## Basic Demo Flow

1. Start backend and frontend.
2. Open the frontend.
3. Create or use the current session.
4. Upload an image.
5. Enter an image-processing prompt, for example:

```text
增强这张图片的边缘细节，提升对比度，并保持自然色彩
```

6. Watch the agent timeline: planning, retrieval, code generation, execution, evaluation, and optional iteration.
7. Review the generated output image and session logs.

Runtime session files are written under `backend/sessions/` and are ignored by git.

## Useful Commands

Run a focused backend test:

```bash
cd backend
uv run python -m pytest tests/test_task_parser.py -q
```

Run backend tests:

```bash
cd backend
uv run python -m pytest tests -q
```

Run the MVP smoke script:

```bash
uv run python test_mvp_e2e.py
```

Build the frontend:

```bash
cd frontend
pnpm build
```

## API Summary

The backend exposes a Flask API on port `5008`.

| Endpoint | Method | Purpose |
| --- | --- | --- |
| `/api/session/create` | POST | Create a session |
| `/api/session/<id>` | GET | Get full session state |
| `/api/sessions` | GET | List session summaries |
| `/api/process` | POST | Submit prompt and optional image |
| `/api/stream` | GET | SSE progress stream |
| `/api/upload` | POST | Upload an image |
| `/api/feedback` | POST | Submit user feedback |
| `/api/state-diagram/<id>` | GET | Get state logs |
| `/api/history` | GET | Get global state history |

More frontend-facing details are in [`frontend/BACKEND_REQUIREMENTS.md`](frontend/BACKEND_REQUIREMENTS.md).

## Demo Notes

- This project intentionally demonstrates local agent orchestration and generated-code execution.
- The execution agent runs generated Python code locally. Do not expose this demo directly to the public internet or use it with untrusted users.
- `backend/sessions/`, uploads, generated outputs, caches, virtual environments, and dependency folders are ignored by git.
- The architecture deck in `ppt/` is included so reviewers can understand the system without reading all source files first.

## Troubleshooting

- Missing API key errors: confirm `.env` exists at the repository root and contains `OPENROUTER_API_KEY` and `TAVILY_API_KEY`.
- Frontend cannot reach backend: confirm the backend is running on port `5008`, or set `frontend/.env` with `VITE_API_BASE_URL`.
- Image evaluation fails: confirm `OPENROUTER_IMAGE_MODEL` points to a model that supports image input through OpenRouter.
- Generated code fails: inspect the session workspace under `backend/sessions/<session_id>/workspace/` and the state logs in the UI.
