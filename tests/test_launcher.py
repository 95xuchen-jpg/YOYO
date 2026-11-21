import unittest
import tempfile
import json
from pathlib import Path
from unittest.mock import Mock, patch
from io import StringIO
from launcher import main
from launcher import execute, write_session_log
from windows_provider import WindowIdentity
from core import Rect

class LauncherTests(unittest.TestCase):
    def test_session_log_appends_machine_readable_events(self):
        with tempfile.TemporaryDirectory() as directory:
            result = {'mode': 'windows-dungeon-observe', 'status': 'paused',
                      'reason': 'two_frame_confirmation_missing', 'input_enabled': False}
            path = write_session_log(result, log_dir=directory)
            write_session_log(result, log_dir=directory)
            events = [json.loads(line) for line in Path(path).read_text(encoding='utf-8').splitlines()]
            self.assertEqual(len(events), 2)
            self.assertEqual(events[0]['reason'], 'two_frame_confirmation_missing')
            self.assertFalse(events[0]['input_enabled'])
            self.assertFalse(events[0]['game_state_verified'])

    def test_unexpected_error_fails_closed_and_writes_log(self):
        with tempfile.TemporaryDirectory() as directory:
            output = StringIO()
            with patch('launcher.execute', side_effect=RuntimeError('sensitive details')), patch('sys.stdout', output):
                code = main(['--mode', 'offline', '--log-dir', directory])
            self.assertEqual(code, 2)
            report = json.loads(output.getvalue())
            self.assertEqual(report['reason'], 'unexpected_runtime_error')
            self.assertEqual(report['error_type'], 'RuntimeError')
            self.assertNotIn('sensitive details', output.getvalue())
            event = json.loads(Path(report['log_path']).read_text(encoding='utf-8').splitlines()[-1])
            self.assertFalse(event['input_enabled'])
            self.assertFalse(event['game_state_verified'])

    def test_retired_pvp_mode_cannot_be_invoked(self):
        with self.assertRaisesRegex(ValueError, 'unsupported mode'):
            execute('team-pvp-readiness', title='Game', main_hwnd=101, alt_hwnd=202)

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
        provider.identity.side_effect = lambda handle: {101: windows[0], 202: windows[1]}[handle]
        provider.client_rect.side_effect = lambda handle: {101: Rect(0,0,800,600), 202: Rect(800,0,640,480)}[handle]
        provider.screenshot.return_value = b'fake-frame'
        result = execute('windows-probe', title='Game', provider=provider)
        self.assertEqual(result['status'], 'capture_ready_not_game_verified')
        self.assertFalse(result['input_enabled'])
        self.assertFalse(result['game_state_verified'])

    def test_identity_swap_during_capture_pauses(self):
        provider = Mock()
        windows = [WindowIdentity(101, 10, 'Game', 'GameClass'), WindowIdentity(202, 20, 'Game', 'GameClass')]
        provider.discover.return_value = windows
        provider.bind.side_effect = windows
        provider.identity.side_effect = [WindowIdentity(101, 999, 'Game', 'GameClass'), windows[1]]
        provider.client_rect.side_effect = [Rect(0,0,800,600)] * 3 + [Rect(800,0,640,480)] * 3
        provider.screenshot.return_value = b'fake-frame'
        result = execute('windows-probe', title='Game', provider=provider)
        self.assertEqual(result['status'], 'paused')
        self.assertFalse(result['input_enabled'])

    def test_observe_requires_explicit_distinct_handles(self):
        for main, alt in ((None, None), (101, None), (101, 101), (0, 202), (True, 202)):
            provider = Mock()
            result = execute('windows-observe', title='Game', provider=provider,
                             main_hwnd=main, alt_hwnd=alt)
            self.assertEqual(result['reason'], 'explicit_distinct_hwnds_required')
            provider.discover.assert_not_called()

    def test_observe_explicit_order_is_not_hwnd_sort_order(self):
        provider = Mock()
        a = WindowIdentity(101, 10, 'Game', 'GameClass')
        b = WindowIdentity(202, 20, 'Game', 'GameClass')
        provider.discover.return_value = [a, b]
        provider.bind.side_effect = lambda hwnd: {101: a, 202: b}[hwnd]
        provider.identity.side_effect = lambda hwnd: {101: a, 202: b}[hwnd]
        provider.client_rect.side_effect = lambda hwnd: {101: Rect(0,0,800,600), 202: Rect(800,0,640,480)}[hwnd]
        provider.screenshot.return_value = b'invalid-png'
        result = execute('windows-observe', title='Game', provider=provider,
                         main_hwnd=202, alt_hwnd=101)
        self.assertEqual([x['account_id'] if 'account_id' in x else x['account'] for x in result.get('captures', [])],
                         ['main', 'alt'])
        self.assertEqual([x['hwnd'] for x in result.get('captures', [])], [202, 101])
        self.assertFalse(result['input_enabled'])

    def test_observe_rejects_unrecognized_handle(self):
        provider = Mock()
        provider.discover.return_value = [
            WindowIdentity(101, 10, 'Game', 'X'),
            WindowIdentity(202, 20, 'Game', 'X')]
        result = execute('windows-observe', title='Game', provider=provider,
                         main_hwnd=101, alt_hwnd=303)
        self.assertEqual(result['status'], 'paused')
        provider.screenshot.assert_not_called()

    def test_duplicate_pid_pauses(self):
        provider = Mock()
        provider.discover.return_value = [WindowIdentity(1, 10, 'Game', 'X'), WindowIdentity(2, 10, 'Game', 'X')]
        result = execute('windows-probe', title='Game', provider=provider)
        self.assertEqual(result['status'], 'paused')
        provider.screenshot.assert_not_called()

if __name__ == '__main__':
    unittest.main()
