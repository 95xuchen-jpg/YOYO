import unittest
from core import Rect, Window
from adapters import WindowGuard
from capture_watchdog import CaptureWatchdog

class FailingProvider:
    def client_rect(self, handle): raise RuntimeError('capture provider failed')
    def screenshot(self, handle): raise RuntimeError('should not be reached')
class Detector:
    def detect(self, frame): raise RuntimeError('detector failed')
class FrameProvider:
    def client_rect(self, handle): return Rect(0,0,800,600)
    def screenshot(self, handle): return b'frame'

class WatchdogTests(unittest.TestCase):
    def test_bad_timeout(self):
        with self.assertRaises(ValueError): CaptureWatchdog(timeout=0)
    def test_bad_size(self):
        with self.assertRaises(ValueError): CaptureWatchdog(max_bytes=0)
    def test_provider_exception_pauses(self):
        w=Window('a',1,Rect(0,0,800,600),800,600)
        self.assertIsNone(WindowGuard(FailingProvider(),Detector()).observe(w,'ready'))
    def test_detector_exception_pauses(self):
        w=Window('a',1,Rect(0,0,800,600),800,600)
        self.assertIsNone(WindowGuard(FrameProvider(),Detector()).observe(w,'ready'))

if __name__=='__main__': unittest.main()
