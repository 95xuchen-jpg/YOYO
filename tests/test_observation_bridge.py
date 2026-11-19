import unittest
from dataclasses import dataclass
from io import BytesIO
from PIL import Image
from observation_bridge import capture_pair, safe_coop_observations, safe_dungeon_observations
from gameplay_flows import CoopFlow, DungeonFlow

@dataclass(frozen=True)
class Ident:
    hwnd: int
    pid: int

@dataclass(frozen=True)
class Rect:
    width: int
    height: int

class FakeProvider:
    def __init__(self):
        self.ids = {1: Ident(1, 101), 2: Ident(2, 202)}
        self.rects = {1: Rect(800, 600), 2: Rect(640, 480)}
        self.calls = 0
        self.fail_capture = False
    def identity(self, hwnd):
        return self.ids.get(hwnd)
    def client_rect(self, hwnd):
        return self.rects.get(hwnd)
    def screenshot(self, hwnd):
        self.calls += 1
        if self.fail_capture:
            return None
        rect = self.rects[hwnd]
        output = BytesIO()
        Image.new('RGB', (rect.width, rect.height), 'black').save(output, format='PNG')
        return output.getvalue()

class TestBridge(unittest.TestCase):
    def setUp(self):
        self.p = FakeProvider()
        self.bindings = (("main", 1, 101), ("alt", 2, 202))
    def test_two_frame_capture_and_no_game_claim(self):
        ev = capture_pair(self.p, self.bindings)
        self.assertEqual(self.p.calls, 4)
        self.assertTrue(all(e.identity_ok and e.geometry_ok and e.two_frames_present for e in ev))
        self.assertTrue(all(not x.stable and not x.identity_ok for x in safe_coop_observations(ev)))
    def test_malformed_png_fails_closed(self):
        self.p.screenshot = lambda hwnd: b'frame'
        ev = capture_pair(self.p, self.bindings)
        self.assertFalse(any(e.two_frames_present for e in ev))

    def test_wrong_dimensions_fail_closed(self):
        def wrong_size(hwnd):
            output = BytesIO()
            Image.new('RGB', (10, 10)).save(output, format='PNG')
            return output.getvalue()
        self.p.screenshot = wrong_size
        ev = capture_pair(self.p, self.bindings)
        self.assertFalse(any(e.two_frames_present for e in ev))

    def test_pid_swap_fails_closed(self):
        self.p.ids[1] = Ident(1, 202)
        ev = capture_pair(self.p, self.bindings)
        self.assertFalse(ev[0].identity_ok)
    def test_missing_frames_fails_closed(self):
        self.p.fail_capture = True
        ev = capture_pair(self.p, self.bindings)
        self.assertFalse(any(e.two_frames_present for e in ev))
    def test_duplicate_binding_rejected(self):
        with self.assertRaises(ValueError):
            capture_pair(self.p, (("main", 1, 101), ("alt", 1, 202)))
    def test_coop_state_machine_pauses_without_game_recognition(self):
        ev = capture_pair(self.p, self.bindings)
        flow = CoopFlow("main", "alt", leader="main")
        self.assertEqual(flow.advance(safe_coop_observations(ev)).status, "paused")
    def test_dungeon_state_machine_pauses_without_game_recognition(self):
        ev = capture_pair(self.p, self.bindings)
        flow = DungeonFlow("main", "alt", dungeon="勇闯火焰山", leader="main")
        self.assertEqual(flow.advance(safe_dungeon_observations(ev, "勇闯火焰山")).status, "paused")

if __name__ == "__main__":
    unittest.main()
