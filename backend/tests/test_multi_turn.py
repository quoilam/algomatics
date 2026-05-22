"""Tests for multi-turn conversation support."""
import os
import sys
import tempfile
import shutil
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from controller.controller import ControllerAgent


class TestMultiTurn:
    """Test multi-turn conversation creation, migration, and file isolation."""

    @patch.dict(os.environ, {"OPENROUTER_API_KEY": "sk-test", "OPENROUTER_MODEL": "test-model"})
    def setup_method(self, method=None):
        self.tmpdir = tempfile.mkdtemp()
        self.controller = ControllerAgent(session_root=self.tmpdir)

    def teardown_method(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_new_session_has_empty_turns(self):
        """New session has empty turns array and current_turn_index=0."""
        sid = self.controller.create_session()
        session = self.controller.get_session(sid)
        assert session["turns"] == []
        assert session["current_turn_index"] == 0

    def test_create_turn_adds_to_session(self):
        """_create_turn appends to turns array and updates current_turn_index."""
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
        """Second turn gets turn_id=2 and can reference first turn."""
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
        """_sync_computed_fields copies latest turn fields to session top-level."""
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
        """Old session (no turns array) gets wrapped into turn_1 after migration."""
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
        """Session with turns array is not double-migrated."""
        session = {
            "turns": [{"turn_id": 1, "user_request": "already migrated"}],
        }
        migrated = self.controller._migrate_old_session(session)
        assert len(migrated["turns"]) == 1
        assert migrated["turns"][0]["user_request"] == "already migrated"

    def test_build_turn_output_dir_creates_subdirectory(self):
        """build_turn_output_dir creates turn_N subdirectory under outputs/."""
        sid = self.controller.create_session()
        turn_dir = self.controller.resource_manager.build_turn_output_dir(sid, 1)
        assert os.path.isdir(turn_dir)
        assert turn_dir.endswith(os.path.join("outputs", "turn_1"))

    def test_turn_output_isolation(self):
        """Different turn output files are written to different subdirectories."""
        sid = self.controller.create_session()
        dir1 = self.controller.resource_manager.build_turn_output_dir(sid, 1)
        dir2 = self.controller.resource_manager.build_turn_output_dir(sid, 2)
        with open(os.path.join(dir1, "result.png"), "w") as f:
            f.write("turn1")
        with open(os.path.join(dir2, "result.png"), "w") as f:
            f.write("turn2")
        with open(os.path.join(dir1, "result.png")) as f:
            assert f.read() == "turn1"
        with open(os.path.join(dir2, "result.png")) as f:
            assert f.read() == "turn2"

    def test_workspace_code_prefixed_with_turn_id(self):
        """save_workspace_code with turn_id prefixes filename with turn_N_."""
        sid = self.controller.create_session()
        path = self.controller.resource_manager.save_workspace_code(
            sid, "iteration_1.py", "code1", turn_id=2
        )
        assert "turn_2_iteration_1.py" in path
        assert os.path.exists(path)
