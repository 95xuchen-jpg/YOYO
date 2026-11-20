import unittest
from unittest.mock import Mock, patch
from team_pvp_readiness import inspect


class PvpReadinessTests(unittest.TestCase):
    def provider(self):
        p = Mock()
        from windows_provider import WindowIdentity
        w1 = WindowIdentity(101, 11, "Game", "Class")
        w2 = WindowIdentity(202, 22, "Game", "Class")
        p.discover.return_value = [w1, w2]
        p.bind.side_effect = lambda hwnd: {101: w1, 202: w2}[hwnd]
        return p

    def test_requires_explicit_binding(self):
        self.assertEqual(inspect(Mock(), "Game", 101, 101)["reason"],
                         "explicit_distinct_hwnds_required")

    def test_rejects_duplicate_pid(self):
        p = self.provider()
        from windows_provider import WindowIdentity
        p.discover.return_value = [WindowIdentity(101, 11, "Game", "Class"),
                                   WindowIdentity(202, 11, "Game", "Class")]
        self.assertEqual(inspect(p, "Game", 101, 202)["reason"], "preflight_failed")

    def test_rejects_wrong_hwnd(self):
        p = self.provider()
        self.assertEqual(inspect(p, "Game", 101, 999)["status"], "paused")

    @patch("team_pvp_readiness.capture_pair")
    def test_good_capture_never_claims_pvp_recognition(self, capture):
        from observation_bridge import CaptureEvidence
        capture.return_value = (CaptureEvidence("main", 202, 22, True, True, True),
                                CaptureEvidence("alt", 101, 11, True, True, True))
        result = inspect(self.provider(), "Game", 202, 101)
        self.assertEqual(result["status"], "capture_ready")
        self.assertEqual(result["reason"], "game_state_unverified")
        self.assertEqual([w["hwnd"] for w in result["windows"]], [202, 101])

    @patch("team_pvp_readiness.capture_pair")
    def test_swapped_capture_account_is_rejected(self, capture):
        from observation_bridge import CaptureEvidence
        capture.return_value = (CaptureEvidence("main", 101, 11, True, True, True),
                                CaptureEvidence("alt", 202, 22, True, True, True))
        result = inspect(self.provider(), "Game", 202, 101)
        self.assertEqual(result["status"], "paused")
        self.assertEqual(result["reason"], "capture_binding_mismatch")

    @patch("team_pvp_readiness.capture_pair")
    def test_bad_capture_pauses(self, capture):
        from observation_bridge import CaptureEvidence
        capture.return_value = (CaptureEvidence("main", 101, 11, True, False, False),
                                CaptureEvidence("alt", 202, 22, True, True, True))
        self.assertEqual(inspect(self.provider(), "Game", 101, 202)["status"], "paused")

    def test_launcher_rejects_missing_team_pvp_binding(self):
        from launcher import execute
        result = execute("team-pvp-readiness", title="Game")
        self.assertEqual(result["status"], "paused")
        self.assertEqual(result["reason"], "explicit_distinct_hwnds_required")
        self.assertFalse(result["input_enabled"])
        self.assertFalse(result["game_state_verified"])

    @patch("team_pvp_readiness.capture_pair")
    def test_launcher_team_pvp_is_read_only(self, capture):
        from observation_bridge import CaptureEvidence
        from launcher import execute
        capture.return_value = (CaptureEvidence("main", 101, 11, True, True, True),
                                CaptureEvidence("alt", 202, 22, True, True, True))
        result = execute("team-pvp-readiness", title="Game",
                         provider=self.provider(), main_hwnd=101, alt_hwnd=202)
        self.assertEqual(result["status"], "capture_ready")
        self.assertEqual(result["reason"], "game_state_unverified")
        self.assertFalse(result["input_enabled"])
        self.assertFalse(result["game_state_verified"])


if __name__ == "__main__":
    unittest.main()
