import tempfile
import unittest
from pathlib import Path
from runner import simulate
from journal import TaskJournal

class RunnerTests(unittest.TestCase):
    def test_two_accounts_end_to_end(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / 'journal.sqlite'
            report = simulate(db, now=1000)
            self.assertEqual([x['account'] for x in report['results']], ['account_A', 'account_B'])
            self.assertTrue(all(x['state'] == 'verified' for x in report['results']))

    def test_crash_recovery_is_paused_not_replayed(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / 'journal.sqlite'
            simulate(db, now=1000, fault='crash_after_acquire')
            report = simulate(db, now=1001)
            self.assertIn('offline-demo:0:account_A:preflight', report['recovered']['paused'])
            self.assertEqual(len(report['results']), 1)
            journal = TaskJournal(db, clock=lambda: 1001)
            self.assertEqual(journal.get('offline-demo:0:account_A:preflight')['state'], 'paused')
            journal.close()

    def test_idempotent_second_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / 'journal.sqlite'
            simulate(db, now=1000)
            report = simulate(db, now=1001)
            self.assertEqual(report['results'], [])
