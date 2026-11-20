import unittest

from team_pvp_observation_bridge import inspect_pvp_phase


class TeamPvpObservationBridgeTests(unittest.TestCase):
    def test_ready_captures_do_not_imply_lobby(self):
        result = inspect_pvp_phase({"status": "capture_ready", "windows": [
            {"account_id": "main", "hwnd": 10, "pid": 100},
            {"account_id": "alt", "hwnd": 20, "pid": 200},
        ]})
        self.assertEqual(result["status"], "paused")
        self.assertEqual(result["reason"], "unverified_phase")
        self.assertEqual(result["phase"], "unknown")
        self.assertFalse(result["input_enabled"])
        self.assertFalse(result["game_state_verified"])


    def test_swapped_or_duplicate_capture_identity_pauses(self):
        base = [
            {"account_id": "main", "hwnd": 10, "pid": 100},
            {"account_id": "alt", "hwnd": 20, "pid": 200},
        ]
        variants = [
            list(reversed(base)),
            [base[0], dict(base[1], account_id="main")],
            [base[0], dict(base[1], hwnd=10)],
            [base[0], dict(base[1], pid=100)],
            [base[0], dict(base[1], hwnd=True)],
            [base[0], dict(base[1], pid=0)],
            [base[0], None],
        ]
        for windows in variants:
            with self.subTest(windows=windows):
                result = inspect_pvp_phase({"status": "capture_ready", "windows": windows})
                self.assertEqual(result["reason"], "capture_identity_mismatch")
                self.assertEqual(result["phase"], "unknown")
                self.assertFalse(result["input_enabled"])

    def test_preflight_failure_remains_paused(self):
        result = inspect_pvp_phase({"status": "paused", "reason": "pid_changed"})
        self.assertEqual(result["reason"], "capture_preflight_not_ready")
        self.assertFalse(result["input_enabled"])

    def test_invalid_capture_count_is_rejected(self):
        result = inspect_pvp_phase({"status": "capture_ready", "windows": [{}]})
        self.assertEqual(result["reason"], "two_capture_records_required")

    def test_missing_or_malformed_payload_is_rejected(self):
        for payload in (None, [], {}, {"status": "capture_ready"}):
            with self.subTest(payload=payload):
                result = inspect_pvp_phase(payload)
                self.assertEqual(result["status"], "paused")
                self.assertFalse(result["input_enabled"])


if __name__ == "__main__":
    unittest.main()
