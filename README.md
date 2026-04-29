# cprp MVP

Minimal MVP implementing an agentic controller and two simple agents.

Quick start

1. Create a Python virtual env and install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Run the server:

```bash
python -m src.server
```

3. Call the endpoint (example):

```bash
curl -X POST http://127.0.0.1:8000/process \
  -H "Content-Type: application/json" \
  -d '{"prompt": "把这张图卡通化", "image_path": "./example.jpg"}'
```

Notes
- The agents are intentionally minimal and deterministic; replace with real retrieval/model calls to extend.
- Output image will be written next to input, named `<input>.<style>.jpg`.
# algomatics
