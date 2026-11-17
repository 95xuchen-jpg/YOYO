import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from core import DualAccountQueue, Task
from coordinator import DurableCoordinator
from journal import TaskJournal

class FaultInjectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.now = [100.]
        self.clock = lambda: self.now[0]
        self.j = TaskJournal(Path(self.temp.name)/'tasks.db', self.clock)
        self.q = DualAccountQueue(clock=self.clock)
        self.c = DurableCoordinator(self.q, self.j)
    def tearDown(self):
        self.j.close(); self.temp.cleanup()
    def test_start_write_failure_blocks_all_accounts(self):
        self.c.submit('a', Task('a','daily',200))
        self.c.submit('b', Task('b','daily',200))
        with patch.object(self.j,'start',side_effect=OSError('disk full')):
            with self.assertRaises(OSError): self.c.acquire()
        self.assertTrue(self.c.blocked)
        with self.assertRaises(RuntimeError): self.c.acquire()
        self.assertEqual(self.j.get('a')['state'],'queued')
    def test_timeout_write_failure_blocks_queue(self):
        self.c.submit('a',Task('a','daily',101))
        self.now[0]=102
        with patch.object(self.j,'timeout_queued',side_effect=OSError('disk full')):
            with self.assertRaises(OSError): self.c.acquire()
        with self.assertRaises(RuntimeError): self.c.submit('b',Task('b','daily',200))
    def test_active_timeout_write_failure_blocks_queue(self):
        self.c.submit('a',Task('a','daily',101)); self.c.acquire()
        self.now[0]=102
        with patch.object(self.j,'timeout_active',side_effect=OSError('disk full')):
            with self.assertRaises(OSError): self.c.expire_active()
        self.assertTrue(self.c.blocked)
    def test_completion_write_failure_does_not_release_lease(self):
        self.c.submit('a',Task('a','daily',200)); task=self.c.acquire()
        with patch.object(self.j,'complete',side_effect=OSError('disk full')):
            with self.assertRaises(OSError): self.c.finish(task,True)
        self.assertIs(self.q._active,task)
        self.assertTrue(self.c.blocked)
    def test_default_queue_and_journal_use_epoch_deadline(self):
        # Real-world UNIX deadline must work with default queue clock.
        import time
        q=DualAccountQueue()
        q.submit(Task('a','daily',time.time()+60))
        self.assertIsNotNone(q.acquire())

if __name__=='__main__': unittest.main()
