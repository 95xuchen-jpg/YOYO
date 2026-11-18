import unittest
from unittest.mock import Mock, patch

from launcher import execute


class GatedOfflineTests(unittest.TestCase):
    def test_failed_preflight_never_runs_scheduler(self):
        with patch('readonly_probe.probe', return_value={'status': 'paused'}), patch('runner.simulate') as scheduler:
            result = execute('windows-gated-offline', title='Game', provider=Mock())
        self.assertEqual(result['status'], 'paused')
        self.assertFalse(result['input_enabled'])
        scheduler.assert_not_called()

    def test_scheduler_exception_fails_closed(self):
        ready = {'status': 'capture_ready_not_game_verified', 'windows': [{'handle': 1}, {'handle': 2}]}
        with patch('readonly_probe.probe', return_value=ready), patch('runner.simulate', side_effect=RuntimeError('simulated crash')) as scheduler:
            result = execute('windows-gated-offline', title='Game', provider=Mock())
        self.assertEqual(result['status'], 'paused')
        self.assertEqual(result['reason'], 'offline_rehearsal_failed')
        self.assertEqual(result['error_type'], 'RuntimeError')
        self.assertFalse(result['input_enabled'])
        self.assertFalse(result['game_state_verified'])
        scheduler.assert_called_once()

    def test_window_change_after_rehearsal_pauses(self):
        before = {'status': 'capture_ready_not_game_verified', 'windows': [{'handle': 1}, {'handle': 2}]}
        after = {'status': 'capture_ready_not_game_verified', 'windows': [{'handle': 1}, {'handle': 3}]}
        with patch('readonly_probe.probe', side_effect=[before, after]), patch('runner.simulate', return_value={'mode': 'offline_simulation_only'}):
            result = execute('windows-gated-offline', title='Game', provider=Mock())
        self.assertEqual(result['status'], 'paused')
        self.assertEqual(result['reason'], 'window_changed_during_rehearsal')
        self.assertFalse(result['input_enabled'])

    def test_preflight_exception_fails_closed(self):
        with patch('readonly_probe.probe', side_effect=OSError('capture unavailable')), patch('runner.simulate') as scheduler:
            result = execute('windows-gated-offline', title='Game', provider=Mock())
        self.assertEqual(result['status'], 'paused')
        self.assertEqual(result['reason'], 'window_preflight_failed')
        self.assertEqual(result['error_type'], 'OSError')
        self.assertFalse(result['input_enabled'])
        scheduler.assert_not_called()

    def test_revalidation_exception_fails_closed(self):
        ready = {'status': 'capture_ready_not_game_verified', 'windows': [{'handle': 1}, {'handle': 2}]}
        with patch('readonly_probe.probe', side_effect=[ready, OSError('window closed')]), patch('runner.simulate', return_value={'mode': 'offline_simulation_only'}):
            result = execute('windows-gated-offline', title='Game', provider=Mock())
        self.assertEqual(result['status'], 'paused')
        self.assertEqual(result['reason'], 'window_revalidation_failed')
        self.assertEqual(result['error_type'], 'OSError')
        self.assertFalse(result['input_enabled'])


    def test_stable_pair_completes_read_only_rehearsal(self):
        ready = {'status': 'capture_ready_not_game_verified',
                 'windows': [{'handle': 1, 'pid': 10}, {'handle': 2, 'pid': 20}]}
        with patch('readonly_probe.probe', side_effect=[ready, ready]) as probe, \
             patch('runner.simulate', return_value={'mode': 'offline_simulation_only'}) as scheduler:
            result = execute('windows-gated-offline', title='Game', provider=Mock())
        self.assertEqual(result['status'], 'offline_rehearsal_only')
        self.assertFalse(result['input_enabled'])
        self.assertFalse(result['game_state_verified'])
        self.assertEqual(probe.call_count, 2)
        scheduler.assert_called_once()

    def test_missing_title_never_runs_scheduler(self):
        with patch('runner.simulate') as scheduler:
            result = execute('windows-gated-offline', title=None, provider=Mock())
        self.assertEqual(result['status'], 'paused')
        self.assertFalse(result['input_enabled'])
        scheduler.assert_not_called()


if __name__ == '__main__':
    unittest.main()
