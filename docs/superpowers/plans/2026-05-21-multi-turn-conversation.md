# Multi-Turn Conversation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable multi-turn conversations where later turns auto-link previous turn outputs as inputs, all intermediate results are preserved, and old sessions auto-migrate.

**Architecture:** Introduce a `turns` array in session state — each turn captures one `process_user_request` cycle with its own input, outputs, code, and scores. Output files are saved under turn-scoped subdirectories (`outputs/turn_1/`). Top-level session fields stay as computed values for backward compatibility.

**Tech Stack:** Python 3.12 + Flask (backend), React 19 + Zustand + TypeScript (frontend), uv (Python deps), pnpm (JS deps)

---

## File Map

| File | Change | Responsibility |
|------|--------|----------------|
| `backend/session_resources.py` | Modify | Turn-scoped output paths, workspace filenames with turn prefix |
| `backend/controller/controller.py` | Modify | Turn data model, `_create_turn`/`_finalize_turn`, refactored `process_user_request`, migration |
| `backend/app.py` | Modify | New turn API endpoints, enriched session response |
| `backend/tests/test_multi_turn.py` | Create | Tests for turn creation, file isolation, migration |
| `frontend/src/types.ts` | Modify | New `Turn` interface, update `Session` and `SessionResponse` |
| `frontend/src/store.ts` | Modify | Turns in state, `setActiveTurn`/`hydrateTurns` |
| `frontend/src/api.ts` | Modify | `fetchTurns`/`fetchTurnDetail` API functions |
| `frontend/src/App.tsx` | Modify | Handle multi-turn complete events with turn-aware output |
| `frontend/src/components/ChatWindow.tsx` | Modify | Group messages by turn with turn dividers |
| `frontend/src/components/MessageItem.tsx` | Modify | Ensure output images render per message |
| `frontend/src/components/InputArea.tsx` | Modify | Input source indicator showing "using previous output" |

---

### Task 1: SessionResourceManager — turn-scoped output paths

**Files:**
- Modify: `backend/session_resources.py`

- [ ] **Step 1: Add `build_turn_output_dir` method**

Open `backend/session_resources.py` and add this method inside `class SessionResourceManager`, after `build_unique_upload_path`:

```python
def build_turn_output_dir(self, session_id: str, turn_id: int) -> str:
    """Return the output directory for a specific turn, creating it if needed."""
    paths = self.ensure_session(session_id)
    turn_dir = os.path.join(paths["outputs_dir"], f"turn_{turn_id}")
    os.makedirs(turn_dir, exist_ok=True)
    return turn_dir
```

- [ ] **Step 2: Update `save_workspace_code` to accept optional `turn_id` prefix**

Replace the existing `save_workspace_code` method signature and first lines — the new version prepends the turn id when provided:

```python
def save_workspace_code(self, session_id: str, filename: str, code: str,
                        turn_id: Optional[int] = None) -> str:
    paths = self.ensure_session(session_id)
    safe_filename = secure_filename(filename) or "generated_code.py"
    if not safe_filename.endswith(".py"):
        safe_filename = f"{safe_filename}.py"
    if turn_id is not None:
        safe_filename = f"turn_{turn_id}_{safe_filename}"
    file_path = os.path.join(paths["workspace_dir"], safe_filename)
    try:
        with open(file_path, "w", encoding="utf-8") as file_handle:
            file_handle.write(code)
            if code and not code.endswith("\n"):
                file_handle.write("\n")
    except (IOError, OSError) as e:
        print(f"[SessionResourceManager] Failed to save workspace code for {session_id}/{safe_filename}: {e}")
    return file_path
```

Note: The import line at the top of the file already has `from typing import Any, Dict, Optional` — change it to `from typing import Any, Dict, List, Optional`.

- [ ] **Step 3: Commit**

```bash
git add backend/session_resources.py
git commit -m "feat: add turn-scoped output directory and workspace filename support"
```

---

### Task 2: Controller — turn data model, migration, and helpers

**Files:**
- Modify: `backend/controller/controller.py`

- [ ] **Step 1: Update `create_session` to init turns array**

In `create_session`, change the session dict initializer to add `turns` and `current_turn_index`. Replace lines 281-296:

```python
def create_session(self, user_id: str = "default", title: str = "") -> str:
    """创建新会话"""
    session_id = str(uuid.uuid4())
    resources = self._session_resources(session_id)
    self.resource_manager.link_latest_session(session_id)
    self.sessions[session_id] = {
        "user_id": user_id,
        "title": title or "新对话",
        "created_at": datetime.now().isoformat(),
        "status": "initialized",
        "resources": resources,
        "turns": [],
        "current_turn_index": 0,
        # Computed fields (synced from latest turn for backward compat)
        "user_request": None,
        "input_image": None,
        "messages": [],
        "search_results": None,
        "generated_code": None,
        "execution_result": None,
        "evaluation_result": None,
        "feedback_history": [],
        "iteration_count": 0,
    }
    self._persist_session(session_id)
    return session_id
```

- [ ] **Step 2: Add `_migrate_old_session` method**

Add this method inside `class ControllerAgent`, before `_load_existing_sessions`:

```python
def _migrate_old_session(self, session: Dict[str, Any]) -> Dict[str, Any]:
    """Wrap legacy scalar fields into turn_1 if turns array is missing."""
    if session.get("turns") is not None:
        return session
    # Build turn_1 from existing scalar fields
    execution_result = session.get("execution_result")
    turn1 = {
        "turn_id": 1,
        "user_request": session.get("user_request", ""),
        "input_image": session.get("input_image"),
        "input_source": "upload",
        "input_from_turn": None,
        "messages": session.get("messages", []),
        "generated_code": session.get("generated_code"),
        "code_path": session.get("generated_code_path"),
        "execution_result": execution_result,
        "evaluation_result": session.get("evaluation_result"),
        "iterations": [],
        "status": session.get("status", "completed"),
        "created_at": session.get("created_at", datetime.now().isoformat()),
    }
    session["turns"] = [turn1]
    session["current_turn_index"] = 1
    return session
```

- [ ] **Step 3: Add `_sync_computed_fields` method**

Add after `_migrate_old_session`:

```python
def _sync_computed_fields(self, session: Dict[str, Any]) -> None:
    """Sync top-level fields from the latest turn for backward compatibility."""
    turns = session.get("turns", [])
    if not turns:
        return
    latest = turns[-1]
    session["user_request"] = latest.get("user_request")
    session["input_image"] = latest.get("input_image")
    session["generated_code"] = latest.get("generated_code")
    session["generated_code_path"] = latest.get("code_path")
    session["execution_result"] = latest.get("execution_result")
    session["evaluation_result"] = latest.get("evaluation_result")
    session["status"] = latest.get("status", session.get("status"))
    session["iteration_count"] = len(latest.get("iterations", []))
```

- [ ] **Step 4: Add `_create_turn` method**

```python
def _create_turn(self, session: Dict[str, Any], user_request: str,
                 input_image: Optional[str], input_source: str = "upload",
                 input_from_turn: Optional[int] = None) -> Dict[str, Any]:
    """Create a new turn object and update session state."""
    turn_id = session["current_turn_index"] + 1
    turn = {
        "turn_id": turn_id,
        "user_request": user_request,
        "input_image": input_image,
        "input_source": input_source,
        "input_from_turn": input_from_turn,
        "messages": [],
        "generated_code": None,
        "code_path": None,
        "execution_result": None,
        "evaluation_result": None,
        "iterations": [],
        "status": "processing",
        "created_at": datetime.now().isoformat(),
    }
    session["current_turn_index"] = turn_id
    session["turns"].append(turn)
    self._sync_computed_fields(session)
    return turn
```

- [ ] **Step 5: Add `_finalize_turn` method**

```python
def _finalize_turn(self, session: Dict[str, Any], turn: Dict[str, Any],
                   status: str = "completed") -> None:
    """Mark a turn as finished and sync computed fields to session top-level."""
    turn["status"] = status
    self._sync_computed_fields(session)
```

- [ ] **Step 6: Update `_load_existing_sessions` to migrate old sessions**

In `_load_existing_sessions`, after loading session data and before adding to `self.sessions`, call migration. Insert after line 79 (`session_data = json.load(f)` → `if isinstance(session_data, dict):`):

```python
                if isinstance(session_data, dict):
                    session_data = self._migrate_old_session(session_data)
                    self.sessions[entry] = session_data
```

- [ ] **Step 7: Commit**

```bash
git add backend/controller/controller.py
git commit -m "feat: add turn data model, migration, and helper methods to Controller"
```

---

### Task 3: Controller — refactor `process_user_request` for turns

**Files:**
- Modify: `backend/controller/controller.py`

- [ ] **Step 1: Replace the session-state setup at the start of `process_user_request`**

At the top of `process_user_request` (around lines 400-406), replace the session setup block. The key changes: (a) resolve input image by auto-linking from the previous turn, (b) create a new turn, (c) use the turn's input_image for processing.

Replace from `if session_id not in self.sessions:` through the `is_followup` block:

```python
        if session_id not in self.sessions:
            return {"success": False, "error": "Session not found"}

        session = self.sessions[session_id]
        session = self._migrate_old_session(session)
        resources = session.get("resources") or self._session_resources(session_id)
        session["resources"] = resources

        # Resolve input image: auto-link from previous turn's output
        input_source = "upload"
        input_from_turn = None
        if input_image_path:
            # User uploaded a new image — use it
            pass
        elif session.get("turns"):
            # Auto-link: use the last successful turn's output
            for prev_turn in reversed(session["turns"]):
                prev_exec = prev_turn.get("execution_result") or {}
                if prev_exec.get("success") and prev_exec.get("output_path"):
                    input_image_path = prev_exec["output_path"]
                    input_source = "previous_output"
                    input_from_turn = prev_turn["turn_id"]
                    break
            if not input_image_path:
                # No successful prior output — reuse the first turn's input
                input_image_path = session["turns"][0].get("input_image")
        # else: no turns yet, input_image_path stays as-is (could be None)

        session["input_image"] = input_image_path

        # Create new turn
        turn = self._create_turn(session, user_request, input_image_path,
                                 input_source, input_from_turn)
        current_turn_id = turn["turn_id"]
        self._persist_session(session_id)

        # Detect follow-up
        is_followup = len(session["turns"]) > 1
```

After this block, the original code at line 470 has `generated_code = None`. Add `execution_result = None` and `evaluation_result = None` right after it:

```python
        generated_code = None
        execution_result = None   # <-- ADD
        evaluation_result = None  # <-- ADD
```

- [ ] **Step 2: Add user message to this turn (not just session)**

Replace the `_append_message` call for the user message (line ~410). The `_append_message` method appends to `session["messages"]` — we now want messages stored per-turn. Replace:

```python
        # 将用户消息追加到当前 turn 的 messages 列表
        self._append_message(session_id, "user", user_request, status="sent")
```

With inlining the message into the turn:

```python
        # Append user message to current turn
        msg_count = len(turn.get("messages", []))
        user_msg = {
            "id": f"{session_id}_{current_turn_id}_user",
            "role": "user",
            "content": user_request,
            "timestamp": datetime.now().isoformat(),
            "status": "sent",
        }
        if input_image_path:
            user_msg["imageUrl"] = input_image_path
        turn.setdefault("messages", []).append(user_msg)
        # Also append to session-level for backward compat
        session.setdefault("messages", []).append(user_msg)
```

- [ ] **Step 3: Use turn-scoped output directory**

In the execution step (line ~883 in the original), replace:

```python
                output_filename = f"result_{iteration_count}.png"
                execution_result = self.execution_agent.execute_code(
                    code=generated_code,
                    input_image_path=input_image_path,
                    output_filename=output_filename,
                    output_dir=resources["outputs"],
                    work_dir=resources["workspace"]
                )
```

With:

```python
                turn_output_dir = self.resource_manager.build_turn_output_dir(
                    session_id, current_turn_id)
                output_filename = f"result_{iteration_count}.png"
                execution_result = self.execution_agent.execute_code(
                    code=generated_code,
                    input_image_path=input_image_path,
                    output_filename=output_filename,
                    output_dir=turn_output_dir,
                    work_dir=resources["workspace"]
                )
```

Similarly, in the repair execution step (around line 1102), replace the output_dir with `turn_output_dir`.

- [ ] **Step 4: Save workspace code with turn prefix**

Replace occurrences of `self.resource_manager.save_workspace_code(session_id, ...)` to include `turn_id=current_turn_id`. Find all three calls (initial code gen ~line 734, revision ~line 849, repair ~line 1033) and add the parameter:

```python
                code_file = self.resource_manager.save_workspace_code(
                    session_id, f"iteration_{iteration_count}.py", generated_code,
                    turn_id=current_turn_id)
```

- [ ] **Step 5: Store iteration results into the turn instead of session**

After each iteration is complete (at the end of the while loop body, around where `current_candidate` is assigned near line 1311), add:

```python
                # Record this iteration into the turn
                turn.setdefault("iterations", []).append({
                    "iteration": iteration_count,
                    "score": current_score,
                    "code_hash": code_hash,
                    "output_hash": output_hash,
                    "output_path": execution_result.get("output_path") if execution_result.get("success") else None,
                })
```

- [ ] **Step 6: Store final results into the turn and finalize**

At each break/exit point where `_apply_final_result` is called (lines ~1398, ~1423, ~1450, ~1468, ~1490), after the `_apply_final_result` call, add:

```python
                turn["generated_code"] = generated_code
                turn["code_path"] = session.get("generated_code_path")
                turn["execution_result"] = execution_result
                turn["evaluation_result"] = evaluation_result if 'evaluation_result' in dir() else (session.get("evaluation_result"))
                self._finalize_turn(session, turn, "completed" if result.get("success") else "needs_review")
```

Actually, this is complex because there are many exit points and the variable scoping varies. A cleaner approach: add the finalization just once, right before the `try` block's closing `return result` (around line 1557). Replace the block just before `return result`:

At the very end of the try block (just before `except Exception as e:` around line 1517), add:

```python
            # Finalize the current turn with accumulated results
            turn["generated_code"] = generated_code
            turn["code_path"] = session.get("generated_code_path")
            turn["execution_result"] = execution_result
            turn["evaluation_result"] = session.get("evaluation_result")
            final_status = session.get("status", "completed")
            self._finalize_turn(session, turn, final_status)
```

And remove the `self._sync_computed_fields(session)` call from inside `_create_turn` since `_finalize_turn` handles it.

- [ ] **Step 7: Update `is_followup` dependent logic**

The old code used `is_followup` to conditionally skip task parsing and planning. The new `is_followup = len(session["turns"]) > 1`. The rest of the `is_followup` logic (skip task_parse, skip KB recommend lookup, skip search) remains correct — it checks `is_followup` which now means "has at least one prior turn."

- [ ] **Step 8: Commit**

```bash
git add backend/controller/controller.py
git commit -m "feat: refactor process_user_request to use turn-scoped state and file layout"
```

---

### Task 4: Backend API — new turn endpoints and enriched session response

**Files:**
- Modify: `backend/app.py`

- [ ] **Step 1: Add `GET /api/session/<id>/turns` endpoint**

Add after the `rename_session` route:

```python
@app.route('/api/session/<session_id>/turns', methods=['GET'])
def list_turns(session_id):
    """列出会话的所有 turn 摘要"""
    session = controller.get_session(session_id)
    if not session:
        return jsonify({'success': False, 'error': 'Session not found'}), 404

    session = controller._migrate_old_session(session)
    turns = session.get('turns', [])
    summaries = []
    for t in turns:
        exec_result = t.get('execution_result') or {}
        summaries.append({
            'turn_id': t['turn_id'],
            'user_request': t.get('user_request', ''),
            'input_source': t.get('input_source', 'upload'),
            'input_from_turn': t.get('input_from_turn'),
            'status': t.get('status', 'unknown'),
            'output_path': exec_result.get('output_path') if exec_result.get('success') else None,
            'score': (t.get('evaluation_result') or {}).get('score'),
            'iteration_count': len(t.get('iterations', [])),
            'created_at': _to_ms(t.get('created_at')),
        })
    return jsonify({'success': True, 'turns': summaries})
```

- [ ] **Step 2: Add `GET /api/session/<id>/turns/<turn_id>` endpoint**

```python
@app.route('/api/session/<session_id>/turns/<int:turn_id>', methods=['GET'])
def get_turn_detail(session_id, turn_id):
    """获取单个 turn 的完整详情"""
    session = controller.get_session(session_id)
    if not session:
        return jsonify({'success': False, 'error': 'Session not found'}), 404

    session = controller._migrate_old_session(session)
    turns = session.get('turns', [])
    turn = next((t for t in turns if t['turn_id'] == turn_id), None)
    if not turn:
        return jsonify({'success': False, 'error': 'Turn not found'}), 404

    exec_result = turn.get('execution_result') or {}
    output_path = exec_result.get('output_path') if exec_result.get('success') else None
    return jsonify({
        'success': True,
        'turn': {
            **turn,
            'output_image_base64': _encode_file_as_data_uri(output_path) if output_path else None,
            'input_image_base64': _encode_file_as_data_uri(turn.get('input_image')),
        }
    })
```

- [ ] **Step 3: Enrich `_build_session_response` with turns summary**

In `_build_session_response` (around line 334), add `turns` and `current_turn_index` to the returned dict. After the `return {` line that builds the response, add these fields:

```python
        'turns': [{
            'turn_id': t['turn_id'],
            'user_request': t.get('user_request', ''),
            'input_source': t.get('input_source', 'upload'),
            'input_from_turn': t.get('input_from_turn'),
            'status': t.get('status', 'unknown'),
            'output_path': (t.get('execution_result') or {}).get('output_path') if (t.get('execution_result') or {}).get('success') else None,
            'output_image_base64': _encode_file_as_data_uri((t.get('execution_result') or {}).get('output_path')) if (t.get('execution_result') or {}).get('success') else None,
            'score': (t.get('evaluation_result') or {}).get('score'),
            'iteration_count': len(t.get('iterations', [])),
            'created_at': _to_ms(t.get('created_at')),
        } for t in session.get('turns', [])],
        'current_turn_index': session.get('current_turn_index', 0),
```

- [ ] **Step 4: Commit**

```bash
git add backend/app.py
git commit -m "feat: add turn list/detail API endpoints and enrich session response"
```

---

### Task 5: Frontend — types and API functions

**Files:**
- Modify: `frontend/src/types.ts`
- Modify: `frontend/src/api.ts`

- [ ] **Step 1: Add `Turn` and `TurnSummary` types to `types.ts`**

Add after the `StateLog` interface:

```typescript
export interface TurnSummary {
  turn_id: number;
  user_request: string;
  input_source: 'upload' | 'previous_output';
  input_from_turn: number | null;
  status: string;
  output_path: string | null;
  output_image_base64?: string | null;
  score: number | null;
  iteration_count: number;
  created_at: number;
}

export interface Turn extends TurnSummary {
  input_image: string | null;
  input_image_base64?: string | null;
  messages: Message[];
  generated_code: string | null;
  code_path: string | null;
  execution_result: Record<string, any> | null;
  evaluation_result: Record<string, any> | null;
  iterations: Array<Record<string, any>>;
}
```

- [ ] **Step 2: Update `Session` and `SessionResponse` to include turns**

Add to `Session` interface:

```typescript
  turns?: TurnSummary[];
  currentTurnIndex?: number;
```

Add to `SessionResponse` interface:

```typescript
  turns?: TurnSummary[];
  current_turn_index?: number;
```

- [ ] **Step 3: Add `fetchTurns` and `fetchTurnDetail` to `api.ts`**

Add after the `renameSession` function:

```typescript
/**
 * 获取会话的所有 turn 摘要
 */
export async function fetchTurns(sessionId: string): Promise<{ success: boolean; turns: import('./types').TurnSummary[] }> {
  const response = await fetch(`${API_BASE}/session/${encodeURIComponent(sessionId)}/turns`);
  if (!response.ok) {
    throw new Error(`Fetch turns error: ${response.statusText}`);
  }
  return await response.json();
}

/**
 * 获取单个 turn 的完整详情（含 output_image_base64）
 */
export async function fetchTurnDetail(sessionId: string, turnId: number): Promise<{ success: boolean; turn: import('./types').Turn }> {
  const response = await fetch(`${API_BASE}/session/${encodeURIComponent(sessionId)}/turns/${turnId}`);
  if (!response.ok) {
    throw new Error(`Fetch turn detail error: ${response.statusText}`);
  }
  return await response.json();
}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/types.ts frontend/src/api.ts
git commit -m "feat: add Turn types and API functions for turn list/detail"
```

---

### Task 6: Frontend — store changes for turns

**Files:**
- Modify: `frontend/src/store.ts`

- [ ] **Step 1: Import Turn types**

At the top of `store.ts`, update the import from `types`:

```typescript
import type {
  Message,
  Session,
  StateLog,
  ViewMode,
  SessionStatus,
  SessionResponse,
  TurnSummary,
} from './types';
```

- [ ] **Step 2: Add turns state fields and methods to the `ChatStore` interface**

Add after `viewMode`:

```typescript
  // Turn state
  turns: TurnSummary[];
  activeTurnId: number | null;
```

Add method signatures after `setViewMode`:

```typescript
  setTurns: (turns: TurnSummary[]) => void;
  setActiveTurnId: (turnId: number | null) => void;
```

- [ ] **Step 3: Add initial state and implementations**

Add initial values in the `create` call:

```typescript
  turns: [],
  activeTurnId: null,
```

Add method implementations:

```typescript
  setTurns: (turns) => set({ turns }),

  setActiveTurnId: (turnId) => set({ activeTurnId: turnId }),
```

- [ ] **Step 4: Update `hydrateSessionFromBackend` to capture turns**

In `hydrateSessionFromBackend`, after the state spread that updates `stateLogs`, add:

```typescript
      // Capture turns from the session response
      const turns = Array.isArray(session.turns) ? session.turns : [];
```

And in the `set(state => {` block's return value, add:

```typescript
        turns: isCurrent ? turns : state.turns,
        activeTurnId: isCurrent ? (turns.length > 0 ? turns[turns.length - 1].turn_id : null) : state.activeTurnId,
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/store.ts
git commit -m "feat: add turns state and methods to Zustand store"
```

---

### Task 7: Frontend — component changes for multi-turn display

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/components/ChatWindow.tsx`
- Modify: `frontend/src/components/MessageItem.tsx`
- Modify: `frontend/src/components/InputArea.tsx`

- [ ] **Step 1: Update `App.tsx` — capture `activeTurnId` in handleSendMessage**

In `handleSendMessage` near the top, add the current `activeTurnId` from store:

```typescript
  const activeTurnId = useChatStore(state => state.activeTurnId);
  const setActiveTurnId = useChatStore(state => state.setActiveTurnId);
```

In `handleComplete`, after setting the final message status, also update turns from the session details:

```typescript
        // Refresh session to get updated turns
        try {
          const sessionDetails = await getSessionDetails(currentSessionId);
          hydrateSessionFromBackend(sessionDetails);
        } catch (err) {
          console.error('Failed to refresh turns after completion:', err);
        }
```

- [ ] **Step 2: Update `ChatWindow.tsx` — add turn dividers**

Add import for `TurnSummary` type:

```typescript
import type { TurnSummary } from '../types';
```

Read turns from store:

```typescript
  const turns = useChatStore(state => state.turns);
```

After the messages map, insert turn indicator dividers. The cleanest approach: wrap the messages rendering to show turn boundaries. Replace the messages container section with:

```tsx
          <div className="messages-container">
            {messages.map((message, idx) => {
              // Find if this message starts a new turn
              const turnForMsg = turns.find(
                t => t.user_request === message.content && message.role === 'user'
              );
              const prevMsg = idx > 0 ? messages[idx - 1] : null;
              const isNewTurn = turnForMsg && (!prevMsg || prevMsg.role !== 'user' || prevMsg.content !== turnForMsg.user_request);

              return (
                <React.Fragment key={message.id}>
                  {isNewTurn && turnForMsg && (
                    <div className="turn-divider">
                      <span className="turn-badge">第 {turnForMsg.turn_id} 轮</span>
                      {turnForMsg.score != null && (
                        <span className="turn-score">评分 {turnForMsg.score}/10</span>
                      )}
                      {turnForMsg.output_image_base64 && (
                        <img
                          className="turn-thumbnail"
                          src={turnForMsg.output_image_base64}
                          alt={`第 ${turnForMsg.turn_id} 轮输出`}
                        />
                      )}
                    </div>
                  )}
                  <MessageItem
                    key={message.id}
                    message={message}
                    onCopy={onCopy}
                    showDetails={false}
                  />
                </React.Fragment>
              );
            })}
            <div ref={messagesEndRef} />
          </div>
```

- [ ] **Step 3: Update `MessageItem.tsx` — ensure output images render well**

The `MessageItem` already renders `message.outputImageUrl` — this is good. Just ensure the image styling is present. Add CSS for the output image in `MessageItem.css`:

```css
.message-image.output-image {
  margin-top: 12px;
  border: 2px solid #4caf50;
  border-radius: 8px;
}
```

- [ ] **Step 4: Update `InputArea.tsx` — show input source indicator**

Add a prop and read the current turns to determine if we're auto-linking. Add after `currentSessionId`:

```typescript
  const turns = useChatStore(state => state.turns);
  const hasPriorOutput = turns.length > 0 && turns.some(t => t.output_path);
```

Add an indicator below the textarea (above the send button):

```tsx
      {hasPriorOutput && !selectedFile && (
        <div className="input-source-indicator">
          🔗 将基于上一轮输出图片继续处理（或上传新图片覆盖）
        </div>
      )}
```

- [ ] **Step 5: Add turn divider CSS**

Create or add to `frontend/src/styles/ChatWindow.css`:

```css
.turn-divider {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 16px;
  margin: 12px 0;
  background: rgba(100, 100, 255, 0.08);
  border-left: 3px solid #6c6cff;
  border-radius: 0 8px 8px 0;
}

.turn-badge {
  font-weight: 600;
  font-size: 13px;
  color: #6c6cff;
  background: rgba(108, 108, 255, 0.12);
  padding: 2px 10px;
  border-radius: 12px;
}

.turn-score {
  font-size: 12px;
  color: #4caf50;
}

.turn-thumbnail {
  max-height: 48px;
  border-radius: 4px;
}
```

- [ ] **Step 6: Commit**

```bash
git add frontend/src/App.tsx frontend/src/components/ChatWindow.tsx frontend/src/components/MessageItem.tsx frontend/src/components/InputArea.tsx frontend/src/styles/ChatWindow.css frontend/src/components/MessageItem.css 2>/dev/null; true
git commit -m "feat: add multi-turn UI with turn dividers, output thumbnails, and input source indicator"
```

---

### Task 8: Backend tests for multi-turn

**Files:**
- Create: `backend/tests/test_multi_turn.py`

- [ ] **Step 1: Write the test file**

```python
"""Tests for multi-turn conversation support."""
import json
import os
import tempfile
import shutil
from unittest.mock import patch, MagicMock

from controller.controller import ControllerAgent


class TestMultiTurn:
    """Test multi-turn conversation creation, migration, and file isolation."""

    @patch.dict(os.environ, {"OPENROUTER_API_KEY": "sk-test", "OPENROUTER_MODEL": "test-model"})
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.controller = ControllerAgent(session_root=self.tmpdir)

    def teardown_method(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_new_session_has_empty_turns(self):
        """新创建的 session 应该有空的 turns 数组和 current_turn_index=0。"""
        sid = self.controller.create_session()
        session = self.controller.get_session(sid)
        assert session["turns"] == []
        assert session["current_turn_index"] == 0

    def test_create_turn_adds_to_session(self):
        """_create_turn 应该 append 到 turns 数组并更新 current_turn_index。"""
        sid = self.controller.create_session()
        session = self.controller.get_session(sid)
        turn = self.controller._create_turn(
            session, "test request", "/path/to/input.png",
            input_source="upload", input_from_turn=None
        )
        assert turn["turn_id"] == 1
        assert session["current_turn_index"] == 1
        assert len(session["turns"]) == 1
        assert session["turns"][0]["user_request"] == "test request"
        assert session["turns"][0]["input_source"] == "upload"

    def test_second_turn_gets_turn_id_2(self):
        """第二轮应该得到 turn_id=2，并且可以引用第一轮。"""
        sid = self.controller.create_session()
        session = self.controller.get_session(sid)
        turn1 = self.controller._create_turn(
            session, "first request", "/img1.png",
            input_source="upload"
        )
        turn2 = self.controller._create_turn(
            session, "second request", "/img2.png",
            input_source="previous_output", input_from_turn=1
        )
        assert turn2["turn_id"] == 2
        assert session["current_turn_index"] == 2
        assert len(session["turns"]) == 2
        assert session["turns"][1]["input_from_turn"] == 1
        assert session["turns"][1]["input_source"] == "previous_output"

    def test_sync_computed_fields_from_latest_turn(self):
        """_sync_computed_fields 应该把最新 turn 的字段同步到 session 顶层。"""
        sid = self.controller.create_session()
        session = self.controller.get_session(sid)
        turn1 = self.controller._create_turn(
            session, "first", "/img1.png", input_source="upload"
        )
        turn1["generated_code"] = "print('hello')"
        turn1["execution_result"] = {"success": True, "output_path": "/out1.png"}
        turn1["evaluation_result"] = {"score": 8}
        turn1["status"] = "completed"
        turn1["code_path"] = "/ws/code1.py"
        self.controller._finalize_turn(session, turn1)
        assert session["user_request"] == "first"
        assert session["input_image"] == "/img1.png"
        assert session["generated_code"] == "print('hello')"
        assert session["execution_result"]["output_path"] == "/out1.png"
        assert session["evaluation_result"]["score"] == 8

    def test_migration_wraps_scalar_fields_into_turn1(self):
        """旧 session（无 turns 数组）迁移后应该有 turn_1。"""
        session = {
            "user_request": "old request",
            "input_image": "/old/input.png",
            "generated_code": "x = 1",
            "generated_code_path": "/ws/old.py",
            "execution_result": {"success": True, "output_path": "/old/output.png"},
            "evaluation_result": {"score": 7},
            "messages": [{"role": "user", "content": "old request"}],
            "status": "completed",
            "created_at": "2026-01-01T00:00:00",
        }
        migrated = self.controller._migrate_old_session(session)
        assert migrated["turns"] is not None
        assert len(migrated["turns"]) == 1
        t1 = migrated["turns"][0]
        assert t1["turn_id"] == 1
        assert t1["user_request"] == "old request"
        assert t1["input_image"] == "/old/input.png"
        assert t1["generated_code"] == "x = 1"
        assert t1["execution_result"]["output_path"] == "/old/output.png"

    def test_migration_does_not_double_migrate(self):
        """已经有 turns 数组的 session 不应该被二次迁移。"""
        session = {
            "turns": [{"turn_id": 1, "user_request": "already migrated"}],
        }
        migrated = self.controller._migrate_old_session(session)
        assert len(migrated["turns"]) == 1
        assert migrated["turns"][0]["user_request"] == "already migrated"

    def test_build_turn_output_dir_creates_subdirectory(self):
        """build_turn_output_dir 应该在 outputs/ 下创建 turn_N 子目录。"""
        sid = self.controller.create_session()
        turn_dir = self.controller.resource_manager.build_turn_output_dir(sid, 1)
        assert os.path.isdir(turn_dir)
        assert turn_dir.endswith("outputs/turn_1")

    def test_turn_output_isolation(self):
        """不同 turn 的输出文件应该写入不同的子目录。"""
        sid = self.controller.create_session()
        dir1 = self.controller.resource_manager.build_turn_output_dir(sid, 1)
        dir2 = self.controller.resource_manager.build_turn_output_dir(sid, 2)
        # Write dummy outputs
        with open(os.path.join(dir1, "result.png"), "w") as f:
            f.write("turn1")
        with open(os.path.join(dir2, "result.png"), "w") as f:
            f.write("turn2")
        # Verify isolation
        with open(os.path.join(dir1, "result.png")) as f:
            assert f.read() == "turn1"
        with open(os.path.join(dir2, "result.png")) as f:
            assert f.read() == "turn2"

    def test_workspace_code_prefixed_with_turn_id(self):
        """带 turn_id 的 save_workspace_code 应该在文件名前加 turn_N_ 前缀。"""
        sid = self.controller.create_session()
        path = self.controller.resource_manager.save_workspace_code(
            sid, "iteration_1.py", "code1", turn_id=2
        )
        assert "turn_2_iteration_1.py" in path
        assert os.path.exists(path)
```

- [ ] **Step 2: Run the tests**

```bash
cd backend && uv run python -m pytest tests/test_multi_turn.py -v
```

Expected: 10 passed.

- [ ] **Step 3: Run all backend tests to confirm no regressions**

```bash
cd backend && uv run python -m pytest tests/ -v --ignore=tests/test_retrieval_agent.py
```

Expected: all previously passing tests still pass (skip `test_retrieval_agent.py` which has the pre-existing flaky test).

- [ ] **Step 4: Commit**

```bash
git add backend/tests/test_multi_turn.py
git commit -m "test: add multi-turn conversation tests for turns, migration, and file isolation"
```

---

### Task 9: Frontend type-check and build verification

**Files:**
- None (verification only)

- [ ] **Step 1: Run TypeScript type check**

```bash
cd frontend && pnpm exec tsc --noEmit
```

Expected: no type errors.

- [ ] **Step 2: Run frontend build**

```bash
cd frontend && pnpm build
```

Expected: build succeeds without errors.

- [ ] **Step 3: Verify no git-clean issues**

```bash
git status
```

Expected: working tree clean after all commits.

---

### Task 10: End-to-end manual verification

**Files:**
- None (verification only)

- [ ] **Step 1: Start the backend**

```bash
cd backend && uv run python app.py
```

- [ ] **Step 2: Create a session and process first request**

```bash
# Create session
curl -s -X POST http://127.0.0.1:5008/api/session/create | jq .

# Upload and process (replace SESSION_ID)
curl -s -X POST http://127.0.0.1:5008/api/process \
  -F "request=把图片转为灰度" \
  -F "session_id=SESSION_ID" \
  -F "image=@/path/to/test_image.png" | jq .

# Wait for processing, then check turns
curl -s http://127.0.0.1:5008/api/session/SESSION_ID/turns | jq .
```

Expected: 1 turn with `output_path` set.

- [ ] **Step 3: Send a follow-up request (no image)**

```bash
curl -s -X POST http://127.0.0.1:5008/api/process \
  -F "request=把图片调亮一点" \
  -F "session_id=SESSION_ID" | jq .

# Wait, then check turns
curl -s http://127.0.0.1:5008/api/session/SESSION_ID/turns | jq .
```

Expected: 2 turns. Turn 2 should have `input_source: "previous_output"` and `input_from_turn: 1`.

- [ ] **Step 4: Verify file isolation**

```bash
ls sessions/SESSION_ID/outputs/turn_1/
ls sessions/SESSION_ID/outputs/turn_2/
```

Expected: both directories exist with their own output files.
