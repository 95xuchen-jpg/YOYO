import unittest
from unittest.mock import Mock
from team_pvp_window_list import list_candidates
from windows_provider import WindowIdentity


class WindowListTests(unittest.TestCase):
    def test_explicit_title_required(self):
        self.assertEqual(list_candidates(Mock(), "")["reason"], "explicit_title_required")

    def test_two_windows_require_user_choice(self):
        provider = Mock()
        provider.discover.return_value = [
            WindowIdentity(101, 11, "Game", "Class"),
            WindowIdentity(202, 22, "Game", "Class"),
        ]
        result = list_candidates(provider, "Game")
        self.assertEqual(result["status"], "choose_main_alt")
        self.assertEqual([w["hwnd"] for w in result["windows"]], [101, 202])

    def test_duplicate_pid_pauses(self):
        provider = Mock()
        provider.discover.return_value = [
            WindowIdentity(101, 11, "Game", "Class"),
            WindowIdentity(202, 11, "Game", "Class"),
        ]
        self.assertEqual(list_candidates(provider, "Game")["status"], "paused")

    def test_more_than_two_pauses(self):
        provider = Mock()
        provider.discover.return_value = [
            WindowIdentity(101, 11, "Game", "Class"),
            WindowIdentity(202, 22, "Game", "Class"),
            WindowIdentity(303, 33, "Game", "Class"),
        ]
        self.assertEqual(list_candidates(provider, "Game")["status"], "paused")

    def test_discovery_failure_pauses(self):
        provider = Mock()
        provider.discover.side_effect = RuntimeError("not available")
        result = list_candidates(provider, "Game")
        self.assertEqual(result["reason"], "discovery_failed")
        self.assertNotIn("not available", str(result))


if __name__ == "__main__":
    unittest.main()
