"""Session-scoped resource layout and persistence helpers."""

import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from werkzeug.utils import secure_filename


class SessionResourceManager:
    """Owns disk resources for each agentic session."""

    def __init__(self, root_dir: str = "sessions"):
        self.root_dir = root_dir
        os.makedirs(self.root_dir, exist_ok=True)
        self.latest_link_path = os.path.join(self.root_dir, "latest")

    def get_paths(self, session_id: str) -> Dict[str, str]:
        base_dir = os.path.join(self.root_dir, session_id)
        return {
            "base_dir": base_dir,
            "uploads_dir": os.path.join(base_dir, "uploads"),
            "outputs_dir": os.path.join(base_dir, "outputs"),
            "workspace_dir": os.path.join(base_dir, "workspace"),
            "state_file": os.path.join(base_dir, "state.json"),
            "state_logs_file": os.path.join(base_dir, "state_logs.jsonl"),
            "agent_calls_file": os.path.join(base_dir, "agent_calls.jsonl"),
        }

    def ensure_session(self, session_id: str) -> Dict[str, str]:
        paths = self.get_paths(session_id)
        for key in ("base_dir", "uploads_dir", "outputs_dir", "workspace_dir"):
            os.makedirs(paths[key], exist_ok=True)
        return paths

    def link_latest_session(self, session_id: str) -> str:
        """Point sessions/latest at the most recently created session directory."""
        paths = self.ensure_session(session_id)
        latest_link_path = self.latest_link_path
        tmp_link_path = f"{latest_link_path}.tmp"

        if os.path.lexists(tmp_link_path):
            os.unlink(tmp_link_path)

        if os.path.lexists(latest_link_path) and not os.path.islink(latest_link_path):
            raise FileExistsError(
                f"Cannot update latest session link because {latest_link_path} already exists and is not a symlink"
            )

        relative_target = os.path.relpath(paths["base_dir"], self.root_dir)
        os.symlink(relative_target, tmp_link_path)
        os.replace(tmp_link_path, latest_link_path)
        return latest_link_path

    def session_resource_payload(self, session_id: str) -> Dict[str, str]:
        paths = self.ensure_session(session_id)
        return {
            "root": paths["base_dir"],
            "uploads": paths["uploads_dir"],
            "outputs": paths["outputs_dir"],
            "workspace": paths["workspace_dir"],
            "state_file": paths["state_file"],
            "state_logs_file": paths["state_logs_file"],
            "agent_calls_file": paths["agent_calls_file"],
        }

    def save_session_state(self, session_id: str, session: Dict[str, Any]) -> None:
        paths = self.ensure_session(session_id)
        with open(paths["state_file"], "w", encoding="utf-8") as file_handle:
            json.dump(session, file_handle, ensure_ascii=False, indent=2, default=str)

    def append_state_log(self, session_id: str, log_entry: Dict[str, Any]) -> None:
        paths = self.ensure_session(session_id)
        self._append_jsonl(paths["state_logs_file"], log_entry)

    def append_agent_call(self,
                          session_id: str,
                          agent_name: str,
                          action: str,
                          payload: Optional[Dict[str, Any]] = None,
                          result: Optional[Dict[str, Any]] = None) -> None:
        paths = self.ensure_session(session_id)
        entry = {
            "timestamp": datetime.now().isoformat(),
            "session_id": session_id,
            "agent": agent_name,
            "action": action,
            "payload": payload or {},
            "result": result or {},
        }
        self._append_jsonl(paths["agent_calls_file"], entry)

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

    def build_upload_path(self, session_id: str, filename: str) -> str:
        paths = self.ensure_session(session_id)
        safe_filename = secure_filename(filename) or "upload.bin"
        return os.path.join(paths["uploads_dir"], safe_filename)

    def build_unique_upload_path(self, session_id: str, filename: str, suffix: str) -> str:
        safe_filename = secure_filename(filename) or "upload.bin"
        return self.build_upload_path(session_id, f"{suffix}_{safe_filename}")

    def build_turn_output_dir(self, session_id: str, turn_id: int) -> str:
        """Return the output directory for a specific turn, creating it if needed."""
        paths = self.ensure_session(session_id)
        turn_dir = os.path.join(paths["outputs_dir"], f"turn_{turn_id}")
        os.makedirs(turn_dir, exist_ok=True)
        return turn_dir

    @staticmethod
    def _append_jsonl(file_path: str, entry: Dict[str, Any]) -> None:
        with open(file_path, "a", encoding="utf-8") as file_handle:
            file_handle.write(json.dumps(entry, ensure_ascii=False, default=str))
            file_handle.write("\n")
