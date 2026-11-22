"""Regression tests for the packaged launcher replay entrypoint."""
import json
import tempfile
import unittest
from pathlib import Path
from launcher import execute


class FruitReplayLauncherTests(unittest.TestCase):
    def test_requires_explicit_path(self):
        result = execute("fruit-replay")
        self.assertEqual(result["reason"], "explicit_jsonl_required")
        self.assertFalse(result["input_enabled"])

    def test_missing_file_fails_closed(self):
        result = execute("fruit-replay", db="/definitely/missing/fruit.jsonl")
        self.assertEqual(result["reason"], "replay_file_unavailable")
        self.assertFalse(result["input_enabled"])

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
