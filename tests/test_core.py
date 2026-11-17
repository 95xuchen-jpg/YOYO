import unittest
from core import Rect, Window, Task, DualAccountQueue

class CoreTests(unittest.TestCase):
    def test_scaled_windows_are_independent(self):
        a=Window('a',101,Rect(0,0,800,600),800,600)
        b=Window('b',102,Rect(900,50,400,300),800,600)
        self.assertEqual(a.map_point(400,300),(400,300))
        self.assertEqual(b.map_point(400,300),(1100,200))
    def test_letterbox_viewport(self):
        w=Window('a',1,Rect(10,20,1000,600),800,600)
        self.assertEqual(w.map_point(400,300,Rect(110,20,800,600)),(510,320))
    def test_outside_rejected(self):
        w=Window('a',1,Rect(0,0,400,300),800,600)
        with self.assertRaises(ValueError):w.map_point(800,0)
        with self.assertRaises(ValueError):w.map_point(1,1,Rect(-1,0,400,300))
    def test_no_simultaneous_foreground(self):
        now=[0.]
        q=DualAccountQueue(clock=lambda:now[0]);a=Task('a','vitality',10);b=Task('b','vitality',10)
        q.submit(a);q.submit(b)
        self.assertIs(q.acquire(),a)
        self.assertIsNone(q.acquire())
        q.finish(a,True)
        self.assertIs(q.acquire(),b)
        q.finish(b,True)
        self.assertEqual((a.state,b.state),('verified','verified'))
    def test_timeout_releases_lease(self):
        now=[0.];q=DualAccountQueue(clock=lambda:now[0]);a=Task('a','vitality',2);b=Task('b','daily',10)
        q.submit(a);q.submit(b);q.acquire();now[0]=3
        self.assertIs(q.expire_active(),a)
        self.assertIs(q.acquire(),b)
        self.assertEqual(a.state,'timed_out')
    def test_stale_completion_rejected(self):
        q=DualAccountQueue(clock=lambda:0);a=Task('a','x',10)
        with self.assertRaises(RuntimeError):q.finish(a,True)
    def test_deadline_queue_skip(self):
        q=DualAccountQueue(clock=lambda:5);a=Task('a','x',4);b=Task('b','x',6)
        q.submit(a);q.submit(b)
        self.assertIs(q.acquire(),b)
        self.assertEqual(a.state,'timed_out')
    def test_no_unverified_success(self):
        q=DualAccountQueue(clock=lambda:0);a=Task('a','x',10);q.submit(a);q.acquire();q.finish(a,False)
        self.assertEqual(a.state,'paused')

if __name__=='__main__':unittest.main()
