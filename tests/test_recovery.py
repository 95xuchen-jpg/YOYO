import tempfile
import unittest
from pathlib import Path
from core import Task, DualAccountQueue
from journal import TaskJournal
from coordinator import DurableCoordinator
from recovery import recover_queued

class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'tasks.db'
        self.now = [100.]
        self.clock = lambda: self.now[0]
        self.j = TaskJournal(self.path, self.clock)

    def tearDown(self):
        self.j.close(); self.tmp.cleanup()

    def fresh(self):
        q = DualAccountQueue(clock=self.clock)
        return DurableCoordinator(q, self.j)

    def test_restart_requeues_only_untouched(self):
        self.j.enqueue('a:1','a','daily',200)
        self.j.enqueue('b:1','b','daily',200)
        self.j.start('b:1')
        self.j.close(); self.j = TaskJournal(self.path, self.clock)
        c = self.fresh(); report = recover_queued(self.j,c,self.clock)
        self.assertEqual(report.restored, ('a:1',))
        self.assertEqual(report.paused, ('b:1',))
        self.assertEqual(c.acquire().account, 'a')

    def test_expired_is_not_requeued(self):
        self.j.enqueue('x','a','daily',101)
        self.now[0] = 102
        c = self.fresh(); report = recover_queued(self.j,c,self.clock)
        self.assertEqual(report.expired, ('x',))
        self.assertIsNone(c.acquire())
        self.assertEqual(self.j.get('x')['state'], 'timed_out')

    def test_idempotent_second_restart(self):
        self.j.enqueue('x','a','daily',200)
        c = self.fresh(); recover_queued(self.j,c,self.clock)
        self.j.close(); self.j = TaskJournal(self.path, self.clock)
        d = self.fresh(); report = recover_queued(self.j,d,self.clock)
        self.assertEqual(report.restored, ('x',))
        self.assertEqual(len(d.queue.queues['a']),1)

    def test_refuse_nonempty_coordinator(self):
        c = self.fresh(); c.submit('x',Task('a','daily',200))
        with self.assertRaises(RuntimeError): recover_queued(self.j,c,self.clock)

    def test_no_retry_of_verified(self):
        self.j.enqueue('x','a','daily',200)
        self.j.start('x'); self.j.complete('x',True)
        c=self.fresh(); self.assertEqual(recover_queued(self.j,c,self.clock).restored,())

    def test_suspicious_attempts_pause(self):
        self.j.enqueue('x','a','daily',200)
        self.j.db.execute('UPDATE tasks SET attempts=1 WHERE task_id=?',('x',))
        c=self.fresh(); self.assertEqual(recover_queued(self.j,c,self.clock).paused,('x',))
        self.assertEqual(self.j.get('x')['state'],'paused')

if __name__=='__main__': unittest.main()
