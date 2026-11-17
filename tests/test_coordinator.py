import tempfile
import unittest
from pathlib import Path
from core import DualAccountQueue, Task
from journal import TaskJournal
from coordinator import DurableCoordinator

class CoordinatorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.now = [100.0]
        self.j = TaskJournal(Path(self.tmp.name) / 'journal.db', lambda: self.now[0])
        self.q = DualAccountQueue(clock=lambda: self.now[0])
        self.c = DurableCoordinator(self.q, self.j)

    def tearDown(self):
        self.j.close()
        self.tmp.cleanup()

    def test_connected_verified_transition(self):
        task = Task('a', 'daily', 200)
        self.assertTrue(self.c.submit('a:daily:day', task))
        self.assertIs(self.c.acquire(), task)
        self.assertEqual(self.c.finish(task, True), 'verified')
        self.assertEqual(self.j.get('a:daily:day')['state'], 'verified')

    def test_duplicate_does_not_requeue(self):
        self.assertTrue(self.c.submit('key', Task('a', 'daily', 200)))
        self.assertFalse(self.c.submit('key', Task('a', 'daily', 200)))
        self.assertEqual(len(self.q.queues['a']), 1)

    def test_global_lease_across_two_accounts(self):
        self.c.submit('a', Task('a', 'daily', 200))
        self.c.submit('b', Task('b', 'daily', 200))
        first = self.c.acquire()
        self.assertIsNone(self.c.acquire())
        self.c.finish(first, True)
        self.assertIsNotNone(self.c.acquire())

if __name__ == '__main__':
    unittest.main()
