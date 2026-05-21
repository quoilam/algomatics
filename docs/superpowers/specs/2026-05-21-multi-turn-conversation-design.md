# Multi-Turn Conversation Design

## Problem

A session currently holds only one output image. Each `process_user_request` call overwrites scalar session fields (`generated_code`, `execution_result`, `evaluation_result`, `input_image`). Output filenames (`result_{iteration}.png`) restart from 1 each call, overwriting previous outputs. There is no "turn" concept — no history of processing rounds within a session.

## Goal

Enable multi-turn conversations where:
- Later turns default to using the previous turn's output image as input
- All intermediate results are preserved and viewable
- New outputs never overwrite previous ones
- Old sessions without turns are auto-migrated on load

## Design: Turn-Based Architecture

### Data Model

**Session** — turns array drives everything; top-level fields become computed from latest turn for backward compatibility.

```python
{
    "turns": [],              # Turn[] — all rounds
    "current_turn_index": 0,  # 1-based
    # Computed from latest turn (kept for old API consumers):
    "user_request": ..., "input_image": ..., "generated_code": ...,
    "execution_result": ..., "evaluation_result": ...,
}
```

**Turn object:**

```python
{
    "turn_id": 1,
    "user_request": "...",
    "input_image": "/sessions/xxx/uploads/photo.png",
    "input_source": "upload",          # "upload" | "previous_output"
    "input_from_turn": None,           # int | None
    "messages": [...],
    "generated_code": "...",
    "code_path": "...",
    "execution_result": {...},
    "evaluation_result": {...},
    "iterations": [...],
    "status": "completed",
    "created_at": "...",
}
```

### File Layout

```
sessions/<id>/
  uploads/
  outputs/
    turn_1/result_1.png
    turn_1/result_1_repair1.png
    turn_2/result_1.png
  workspace/
    turn_1_iteration_1.py
    turn_2_iteration_1.py
  state.json
```

### Backend Changes

**`session_resources.py`** — new method `build_turn_output_dir(session_id, turn_id)`.

**`controller.py`:**
- `create_session` — init `turns: []`, `current_turn_index: 0`
- `process_user_request` — create new Turn on each call; auto-link previous turn's output as input; save outputs under turn-scoped dir; append turn to `turns` array on completion; sync computed fields
- `is_followup` detection — check `len(session["turns"]) > 0`
- New helper: `_create_turn(session_id, user_request, input_image)` — initialize turn object
- New helper: `_finalize_turn(session, turn)` — append turn, update computed fields, persist

**`app.py`:**
- `GET /api/session/<id>/turns` — list turn summaries
- `GET /api/session/<id>/turns/<turn_id>` — full turn detail with output_image_base64
- `GET /api/session/<id>` response gains `turns` and `current_turn_index` fields

### Frontend Changes

**`types.ts`** — new `Turn` interface.

**`store.ts`:**
- Session gains `turns: Turn[]`, `currentTurnIndex: number`
- New methods: `setActiveTurn(turnId)`, `hydrateTurns(turns)`

**`ChatWindow.tsx`** — render messages grouped by turn; each turn block shows its output image thumbnail + score badge + collapsible code.

**`MessageItem.tsx`** — render `outputImageUrl` when present.

**`InputArea.tsx`** — indicator showing input source (previous turn output vs. upload).

### Migration

Old sessions (no `turns` field) are migrated on load: existing scalar fields wrapped into `turn_1`. Top-level API response fields remain unchanged — the `turns` array is additive.

## Verification

- Two-turn processing: upload image → process → verify output saved → send follow-up request → verify second output saved in `turn_2/` without overwriting `turn_1/`
- Old session migration: load a pre-existing session → verify it gets a `turn_1` and functions normally
- API backward compatibility: existing `GET /api/session/<id>` still returns `output_image_base64` and `execution_result`
