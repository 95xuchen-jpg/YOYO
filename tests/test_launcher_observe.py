import unittest
from io import BytesIO
from PIL import Image
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

        def png_for(hwnd):
            width, height = ((800, 600) if hwnd == 101 else (640, 480))
            stream = BytesIO()
            Image.new('RGB', (width, height)).save(stream, format='PNG')
            return stream.getvalue()

        p.screenshot.side_effect = png_for
        return p

    def test_no_title(self):
        result = execute('windows-observe', title='', main_hwnd=101, alt_hwnd=202)
        self.assertEqual(result['status'], 'paused')
        self.assertEqual(result['reason'], 'explicit_title_required')
        self.assertFalse(result['input_enabled'])

    def test_dual_capture_is_not_game_recognition(self):
        p = self.provider()
        result = execute('windows-observe', title='Game', provider=p,
                         main_hwnd=101, alt_hwnd=202)
        self.assertEqual(p.screenshot.call_count, 4)
        self.assertEqual(len(result['captures']), 2)
        self.assertEqual(result['reason'], 'two_frame_confirmation_missing')
        self.assertFalse(result['game_state_verified'])
        self.assertFalse(result['input_enabled'])

    def test_duplicate_pid_stops_before_capture(self):
        p = self.provider()
        p.discover.return_value = [WindowIdentity(101, 10, 'Game', 'X'),
                                   WindowIdentity(202, 10, 'Game', 'X')]
        result = execute('windows-observe', title='Game', provider=p,
                         main_hwnd=101, alt_hwnd=202)
        self.assertEqual(result['status'], 'paused')
        self.assertEqual(result['reason'], 'observation_preflight_failed')
        p.screenshot.assert_not_called()

    def test_capture_failure_stays_paused(self):
        p = self.provider()
        p.screenshot.side_effect = lambda hwnd: None
        result = execute('windows-observe', title='Game', provider=p,
                         main_hwnd=101, alt_hwnd=202)
        self.assertEqual(len(result['captures']), 2)
        self.assertFalse(any(x['two_frames_present'] for x in result['captures']))
        self.assertEqual(result['status'], 'paused')
        self.assertFalse(result['input_enabled'])


    def test_fruit_dungeon_missing_explicit_name_pauses_before_discovery(self):
        p = self.provider()
        result = execute('windows-dungeon-observe', title='Game', provider=p,
                         main_hwnd=101, alt_hwnd=202)
        self.assertEqual(result['reason'], 'explicit_fruit_dungeon_required')
        self.assertFalse(result['input_enabled'])
        p.discover.assert_not_called()

    def test_fruit_dungeon_reads_both_windows_but_never_guesses_game_state(self):
        p = self.provider()
        result = execute('windows-dungeon-observe', title='Game', provider=p,
                         main_hwnd=202, alt_hwnd=101, dungeon='水果剧团')
        self.assertEqual(result['status'], 'paused')
        self.assertEqual(result['reason'], 'two_frame_confirmation_missing')
        self.assertEqual(result['dungeon'], '水果剧团')
        self.assertEqual([x['hwnd'] for x in result['captures']], [202, 101])
        self.assertEqual(p.screenshot.call_count, 4)
        self.assertTrue(all(x['two_frames_present'] for x in result['captures']))
        self.assertFalse(result['input_enabled'])
        self.assertFalse(result['game_state_verified'])

    def test_fruit_dungeon_bad_frame_pauses(self):
        p = self.provider()
        p.screenshot.side_effect = lambda hwnd: b'bad-frame'
        result = execute('windows-dungeon-observe', title='Game', provider=p,
                         main_hwnd=101, alt_hwnd=202, dungeon='水果剧团')
        self.assertEqual(result['status'], 'paused')
        self.assertFalse(any(x['two_frames_present'] for x in result['captures']))
        self.assertFalse(result['input_enabled'])

    def test_fruit_dungeon_rejects_mismatched_account_window(self):
        p = self.provider()
        result = execute('windows-dungeon-observe', title='Game', provider=p,
                         main_hwnd=101, alt_hwnd=999, dungeon='水果剧团')
        self.assertEqual(result['status'], 'paused')
        self.assertEqual(result['reason'], 'observation_preflight_failed')
        p.screenshot.assert_not_called()



if __name__ == '__main__':
    unittest.main()
