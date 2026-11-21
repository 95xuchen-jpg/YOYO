"""Regression coverage for the double-click diagnostic entrypoint.

These tests do not launch a game or enable any input.
"""
import sys
import unittest
from unittest.mock import patch

import launcher


class DoubleClickEntrypointTests(unittest.TestCase):
    def test_no_arguments_opens_readonly_gui_without_game_actions(self):
        with patch.object(sys, "argv", ["PLN_ReadOnly_Diagnostics.exe"]):
            with patch.object(launcher, "launch_readonly_gui") as gui:
                with patch.object(launcher, "execute") as execute:
                    self.assertEqual(launcher.main(), 0)
        gui.assert_called_once_with()
        execute.assert_not_called()

    def test_explicit_cli_mode_does_not_open_gui(self):
        with patch.object(launcher, "launch_readonly_gui") as gui:
            with patch.object(launcher, "execute", return_value={
                "mode": "offline", "status": "offline_rehearsal_only",
                "input_enabled": False, "game_state_verified": False,
            }):
                with patch.object(launcher, "write_session_log", return_value="test.log"):
                    with patch("builtins.print"):
                        self.assertEqual(launcher.main(["--mode", "offline"]), 0)
        gui.assert_not_called()

    def test_retired_pvp_is_rejected_before_execution(self):
        with patch.object(launcher, "execute") as execute:
            with patch("sys.stderr"):
                with self.assertRaises(SystemExit) as cm:
                    launcher.main(["--mode", "team-pvp-readiness"])
        self.assertEqual(cm.exception.code, 2)
        execute.assert_not_called()


if __name__ == "__main__":
    unittest.main()
