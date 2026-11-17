import unittest
from core import Rect, Window
from preflight import inspect_two_windows

class FakeProvider:
    def __init__(self, change=False):
        self.rects = {101: Rect(0,0,800,600), 202: Rect(800,0,640,480)}
        self.calls = {}
        self.change = change
    def client_rect(self, handle):
        self.calls[handle] = self.calls.get(handle, 0) + 1
        if self.change and handle == 202 and self.calls[handle] > 1:
            return Rect(800,0,320,240)
        return self.rects.get(handle)
    def screenshot(self, handle):
        return b'confirmed' if handle in self.rects else None
class Detector:
    def detect(self, screenshot):
        return 'ready' if screenshot == b'confirmed' else None
class PreflightTests(unittest.TestCase):
    def setUp(self):
        self.bindings = [Window('A',101,Rect(0,0,800,600),800,600),
                         Window('B',202,Rect(800,0,640,480),640,480)]
    def test_two_windows_confirmed(self):
        self.assertEqual([r.status for r in inspect_two_windows(FakeProvider(), Detector(),self.bindings,'ready')], ['observed','observed'])
    def test_resized_window_pauses_only_affected(self):
        self.assertEqual([r.status for r in inspect_two_windows(FakeProvider(change=True), Detector(),self.bindings,'ready')], ['observed','paused'])
    def test_duplicate_handle_rejected(self):
        with self.assertRaises(ValueError):
            inspect_two_windows(FakeProvider(),Detector(),[self.bindings[0],Window('B',101,self.bindings[0].client,800,600)],'ready')
    def test_duplicate_account_rejected(self):
        with self.assertRaises(ValueError):
            inspect_two_windows(FakeProvider(),Detector(),[self.bindings[0],Window('A',202,self.bindings[1].client,640,480)],'ready')
    def test_unverified_state_pauses_both(self):
        self.assertEqual([r.status for r in inspect_two_windows(FakeProvider(),Detector(),self.bindings,'unknown')], ['paused','paused'])

class EntrypointIntegrationTests(unittest.TestCase):
    def test_synthetic_window_bridge_from_unified_runner(self):
        from runner import simulate_window_preflight
        report = simulate_window_preflight()
        self.assertEqual(report['mode'], 'synthetic_frames_only')
        self.assertEqual([r['status'] for r in report['observations']], ['observed','observed'])
