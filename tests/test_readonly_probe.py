import unittest
from types import SimpleNamespace
from core import Rect
from readonly_probe import probe

class Provider:
    def __init__(self, fail=False, change=False):
        self.fail, self.change = fail, change
        self.windows = [SimpleNamespace(hwnd=1,pid=10),SimpleNamespace(hwnd=2,pid=20)]
        self.calls = 0
    def discover(self, title): return self.windows
    def bind(self, handle): return self.windows[handle-1]
    def client_rect(self, handle):
        self.calls += 1
        if self.change and self.calls == 2: return Rect(0,0,799,600)
        return Rect(0,0,800,600)
    def screenshot(self, handle): return None if self.fail else b'frame'

class TestProbe(unittest.TestCase):
    def test_success_not_game_verified(self):
        result = probe(Provider(), 'game')
        self.assertEqual(result['status'], 'capture_ready_not_game_verified')
        self.assertFalse(result['game_state_verified'])
        self.assertFalse(result['input_enabled'])
    def test_capture_failure(self): self.assertEqual(probe(Provider(fail=True),'game')['status'],'paused')
    def test_geometry_change(self): self.assertEqual(probe(Provider(change=True),'game')['status'],'paused')
    def test_ambiguous_pid(self):
        p=Provider(); p.windows[1].pid=10
        self.assertEqual(probe(p,'game')['reason'],'ambiguous_window_identity')
    def test_missing_window(self):
        p=Provider(); p.windows=[]
        self.assertEqual(probe(p,'game')['count'],0)
    def test_empty_filter(self):
        with self.assertRaises(ValueError): probe(Provider(),'')

class SecondFrameFails(Provider):
    def __init__(self):
        super().__init__()
        self.screenshots = 0
    def screenshot(self, handle):
        self.screenshots += 1
        return None if self.screenshots == 2 else b'frame'

class TestTwoFrame(unittest.TestCase):
    def test_second_frame_failure_pauses(self):
        result = probe(SecondFrameFails(), 'game')
        self.assertEqual(result['status'], 'paused')
        self.assertFalse(result['windows'][0]['capture_ok'])
    def test_geometry_changed_after_second_frame_pauses(self):
        class LateChange(Provider):
            def client_rect(self, handle):
                self.calls += 1
                return Rect(0,0,801,600) if self.calls == 3 else Rect(0,0,800,600)
        self.assertEqual(probe(LateChange(),'game')['status'],'paused')
