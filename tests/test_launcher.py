import unittest
from unittest.mock import Mock
from launcher import execute
from windows_provider import WindowIdentity
from core import Rect

class LauncherTests(unittest.TestCase):
    def test_offline_full_chain(self):
        result = execute('offline')
        self.assertEqual(result['mode'], 'offline_simulation_only')
        self.assertEqual(len(result['results']), 2)
        self.assertEqual(len(result['window_preflight']['observations']), 2)

    def test_missing_title_fails_closed(self):
        self.assertEqual(execute('windows-probe', title='')['status'], 'paused')

    def test_windows_mock_readonly_chain(self):
        provider = Mock()
        windows = [WindowIdentity(101, 10, 'Game', 'GameClass'), WindowIdentity(202, 20, 'Game', 'GameClass')]
        provider.discover.return_value = windows
        provider.bind.side_effect = windows
        provider.client_rect.side_effect = [Rect(0,0,800,600)] * 3 + [Rect(800,0,640,480)] * 3
        provider.screenshot.return_value = b'fake-frame'
        result = execute('windows-probe', title='Game', provider=provider)
        self.assertEqual(result['status'], 'capture_ready_not_game_verified')
        self.assertFalse(result['input_enabled'])
        self.assertFalse(result['game_state_verified'])

    def test_duplicate_pid_pauses(self):
        provider = Mock()
        provider.discover.return_value = [WindowIdentity(1, 10, 'Game', 'X'), WindowIdentity(2, 10, 'Game', 'X')]
        result = execute('windows-probe', title='Game', provider=provider)
        self.assertEqual(result['status'], 'paused')
        provider.screenshot.assert_not_called()

if __name__ == '__main__':
    unittest.main()
