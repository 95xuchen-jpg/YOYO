import unittest
from unittest.mock import Mock
from launcher import execute
from windows_provider import WindowIdentity
from core import Rect

class ObserveEntrypointTests(unittest.TestCase):
    def provider(self):
        p = Mock()
        windows = [WindowIdentity(101, 10, 'Game', 'X'), WindowIdentity(202, 20, 'Game', 'X')]
        p.discover.return_value = windows
        p.bind.side_effect = windows
        p.identity.side_effect = lambda hwnd: {101: windows[0], 202: windows[1]}[hwnd]
        p.client_rect.side_effect = lambda hwnd: {101: Rect(0, 0, 800, 600), 202: Rect(800, 0, 640, 480)}[hwnd]
        p.screenshot.return_value = b'frame'
        return p

    def test_no_title(self):
        result = execute('windows-observe', title='')
        self.assertEqual(result['status'], 'paused')
        self.assertFalse(result['input_enabled'])

    def test_dual_capture_is_not_game_recognition(self):
        p = self.provider()
        result = execute('windows-observe', title='Game', provider=p)
        self.assertEqual(p.screenshot.call_count, 4)
        self.assertEqual(len(result['captures']), 2)
        self.assertEqual(result['reason'], 'two_frame_confirmation_missing')
        self.assertFalse(result['game_state_verified'])
        self.assertFalse(result['input_enabled'])

    def test_duplicate_pid_stops_before_capture(self):
        p = self.provider()
        p.discover.return_value = [WindowIdentity(101, 10, 'Game', 'X'),
                                   WindowIdentity(202, 10, 'Game', 'X')]
        result = execute('windows-observe', title='Game', provider=p)
        self.assertEqual(result['status'], 'paused')
        p.screenshot.assert_not_called()

    def test_capture_failure_stays_paused(self):
        p = self.provider()
        p.screenshot.return_value = None
        result = execute('windows-observe', title='Game', provider=p)
        self.assertFalse(all(x['two_frames_present'] for x in result['captures']))
        self.assertEqual(result['status'], 'paused')

if __name__ == '__main__':
    unittest.main()
