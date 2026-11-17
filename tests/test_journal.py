import tempfile
import unittest
from pathlib import Path
from journal import TaskJournal

class JournalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'tasks.sqlite'
        self.now = [100.0]
        self.j = TaskJournal(self.path, lambda: self.now[0])

    def tearDown(self):
        self.j.close()
        self.tmp.cleanup()

    def test_duplicate_submission_is_idempotent(self):
        self.assertTrue(self.j.enqueue('a:daily:2026-11-17', 'a', 'daily', 200))
        self.assertFalse(self.j.enqueue('a:daily:2026-11-17', 'a', 'daily', 200))
        self.assertEqual(self.j.get('a:daily:2026-11-17')['attempts'], 0)

    def test_collision_rejected(self):
        self.j.enqueue('key', 'a', 'daily', 200)
        with self.assertRaises(ValueError):
            self.j.enqueue('key', 'b', 'daily', 200)

    def test_crash_recovery_pauses_active(self):
        self.j.enqueue('key', 'a', 'daily', 200)
        self.assertTrue(self.j.start('key'))
        self.j.close()
        self.j = TaskJournal(self.path, lambda: self.now[0])
        self.assertEqual(self.j.get('key')['state'], 'paused')
        self.assertEqual(self.j.get('key')['attempts'], 1)
        with self.assertRaises(RuntimeError):
            self.j.start('key')

    def test_verified_is_not_replayed(self):
        self.j.enqueue('key', 'a', 'daily', 200)
        self.j.start('key')
        self.assertEqual(self.j.complete('key', True), 'verified')
        with self.assertRaises(RuntimeError):
            self.j.start('key')

    def test_unverified_pauses(self):
        self.j.enqueue('key', 'a', 'daily', 200)
        self.j.start('key')
        self.assertEqual(self.j.complete('key', False), 'paused')

    def test_deadline_blocks_start(self):
        self.j.enqueue('key', 'a', 'daily', 100)
        self.assertFalse(self.j.start('key'))
        self.assertEqual(self.j.get('key')['state'], 'timed_out')

    def test_deadline_blocks_completion(self):
        self.j.enqueue('key', 'a', 'daily', 200)
        self.j.start('key')
        self.now[0] = 201
        self.assertEqual(self.j.complete('key', True), 'paused')

    def test_single_global_lease(self):
        self.j.enqueue('a', 'a', 'daily', 200)
        self.j.enqueue('b', 'b', 'daily', 200)
        self.j.start('a')
        with self.assertRaises(RuntimeError):
            self.j.start('b')
        self.j.complete('a', True)
        self.assertTrue(self.j.start('b'))

if __name__ == '__main__':
    unittest.main()
