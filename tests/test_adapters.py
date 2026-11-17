import unittest
from core import Window, Rect
from adapters import WindowGuard

class FakeProvider:
    def __init__(self, rects=None, frames=None):
        self.rects=list(rects if rects is not None else [Rect(0,0,800,600)]*3)
        self.frames=list(frames if frames is not None else [b'ready',b'ready'])
        self.calls=0
    def client_rect(self, handle):
        self.calls+=1
        return self.rects.pop(0) if self.rects else None
    def screenshot(self, handle):
        return self.frames.pop(0) if self.frames else None
class Detector:
    def detect(self, data):
        return data.decode() if data else None
class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.w=Window('a',101,Rect(0,0,800,600),800,600)
    def test_double_frame_agreement(self):
        self.assertEqual(WindowGuard(FakeProvider(),Detector()).safe_point(self.w,'ready',400,300),(400,300))
    def test_state_change_pauses(self):
        self.assertIsNone(WindowGuard(FakeProvider(frames=[b'ready',b'other']),Detector()).observe(self.w,'ready'))
    def test_resized_window_pauses(self):
        rects=[Rect(0,0,800,600),Rect(0,0,640,480)]
        self.assertIsNone(WindowGuard(FakeProvider(rects=rects),Detector()).observe(self.w,'ready'))
    def test_stale_handle_pauses(self):
        self.assertIsNone(WindowGuard(FakeProvider(rects=[None]),Detector()).observe(self.w,'ready'))
    def test_missing_screenshot_pauses(self):
        self.assertIsNone(WindowGuard(FakeProvider(frames=[b'ready',None]),Detector()).observe(self.w,'ready'))
    def test_unknown_state_pauses(self):
        self.assertIsNone(WindowGuard(FakeProvider(frames=[b'unknown']),Detector()).observe(self.w,'ready'))
    def test_no_action_on_bad_reference_point(self):
        self.assertIsNone(WindowGuard(FakeProvider(),Detector()).safe_point(self.w,'ready',900,300))
    def test_invalid_content_rect_pauses(self):
        self.assertIsNone(WindowGuard(FakeProvider(),Detector()).safe_point(self.w,'ready',400,300,Rect(900,0,100,100)))
    def test_invalid_coordinate_type_pauses(self):
        self.assertIsNone(WindowGuard(FakeProvider(),Detector()).safe_point(self.w,'ready',None,300))
    def test_bounds_change_after_second_frame_pauses(self):
        rects=[Rect(0,0,800,600),Rect(0,0,800,600),Rect(1,0,800,600)]
        self.assertIsNone(WindowGuard(FakeProvider(rects=rects),Detector()).observe(self.w,'ready'))
if __name__=='__main__': unittest.main()
