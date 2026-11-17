import tempfile
import unittest
from pathlib import Path
from core import DualAccountQueue, Task
from journal import TaskJournal
from coordinator import DurableCoordinator

class TimeoutSyncTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.now = [100.0]
        self.clock = lambda: self.now[0]
        self.j = TaskJournal(Path(self.temp.name) / 'tasks.db', self.clock)
        self.q = DualAccountQueue(clock=self.clock)
        self.c = DurableCoordinator(self.q, self.j)
    def tearDown(self):
        self.j.close()
        self.temp.cleanup()
    def test_expired_head_persisted(self):
        self.c.submit('x', Task('a', 'daily', 101))
        self.now[0] = 102
        self.assertIsNone(self.c.acquire())
        self.assertEqual(self.j.get('x')['state'], 'timed_out')
    def test_multiple_expiries_same_name_different_accounts(self):
        self.c.submit('a', Task('a', 'daily', 101))
        self.c.submit('b', Task('b', 'daily', 101))
        self.now[0] = 102
        self.assertIsNone(self.c.acquire())
        self.assertEqual([self.j.get(k)['state'] for k in ('a','b')], ['timed_out']*2)
    def test_expired_head_does_not_block_fresh_work(self):
        self.c.submit('old', Task('a', 'daily', 101))
        self.c.submit('new', Task('a', 'daily', 200))
        self.now[0] = 102
        task = self.c.acquire()
        self.assertEqual(task.deadline, 200)
        self.assertEqual(self.j.get('old')['state'], 'timed_out')
        self.assertEqual(self.j.get('new')['state'], 'active')
    def test_active_timeout_persisted(self):
        self.c.submit('a', Task('a','daily',101))
        self.c.acquire()
        self.now[0] = 102
        self.assertIsNotNone(self.c.expire_active())
        self.assertEqual(self.j.get('a')['state'], 'timed_out')
        self.assertIsNone(self.q._active)
    def test_repeated_sync_idempotent(self):
        self.c.submit('a', Task('a','daily',101))
        self.now[0] = 102
        self.c.acquire(); self.c.acquire()
        self.assertEqual(self.j.get('a')['state'], 'timed_out')

if __name__ == '__main__': unittest.main()
