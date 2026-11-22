"""Regression tests for the packaged launcher replay entrypoint."""
import json
import tempfile
import unittest
from pathlib import Path
from launcher import execute, write_session_log


class FruitReplayLauncherTests(unittest.TestCase):
    def test_requires_explicit_path(self):
        result = execute("fruit-replay")
        self.assertEqual(result["reason"], "explicit_jsonl_required")
        self.assertFalse(result["input_enabled"])

    def test_missing_file_fails_closed(self):
        result = execute("fruit-replay", db="/definitely/missing/fruit.jsonl")
        self.assertEqual(result["reason"], "replay_file_unavailable")
        self.assertFalse(result["input_enabled"])


    def test_session_log_redacts_nested_credentials_and_binary_frames(self):
        with tempfile.TemporaryDirectory() as folder:
            result = {
                "mode": "fruit-replay",
                "status": "paused",
                "reason": "manual_review",
                "details": {
                    "room_code": "test-room-secret-must-not-appear",
                    "nested": {"password": "test-password-must-not-appear"},
                    "frame_bytes": b"raw-frame-bytes-must-not-appear",
                    "safe_status": "visible",
                },
            }
            path = write_session_log(result, log_dir=folder)
            saved = path.read_text(encoding="utf-8")
        self.assertNotIn("test-room-secret-must-not-appear", saved)
        self.assertNotIn("test-password-must-not-appear", saved)
        self.assertNotIn("raw-frame-bytes-must-not-appear", saved)
        self.assertIn("[REDACTED]", saved)
        self.assertIn("[REDACTED_BINARY]", saved)
        self.assertIn("visible", saved)

    def test_invalid_evidence_fails_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "evidence.jsonl"
            path.write_text(json.dumps({"state": "COMPLETE"}) + "\n", encoding="utf-8")
            result = execute("fruit-replay", db=str(path))
        self.assertEqual(result["status"], "paused")
        self.assertEqual(result["reason"], "invalid_evidence")
        self.assertTrue(result["replay_only"])
        self.assertFalse(result["input_enabled"])
        self.assertFalse(result["game_state_verified"])


if __name__ == "__main__":
    unittest.main()
