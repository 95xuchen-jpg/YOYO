"""Offline through the actual observer, with an optional replay of the private source MP4."""
import ctypes
from ctypes import wintypes
import hashlib
import json
import os
import subprocess
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import Mock
from threading import Event

from PIL import Image, ImageDraw
from core import Rect
from fruit_pair_evidence import observe_pair, watch_pair
from fruit_screen import TEMPLATES
from launcher import write_session_log
from windows_provider import WindowIdentity, WindowsClientProvider

BINDINGS = (("main", 10, 100), ("alt", 20, 200))
TILES = dict(TEMPLATES)


def png(img, **kwargs):
    output = BytesIO()
    img.save(output, 'PNG', **kwargs)
    return output.getvalue()


def panel(name, counter, changed_name=False):
    img = Image.new("RGB", (800, 448), (30, 65, 100))
    draw = ImageDraw.Draw(img)
    if name in ("host", "guest"):
        regions = TILES["LEADER_READY"][1:] if name == "host" else TILES["ROOM_WAITING"][1:]
        for box, template in regions:
            img.paste(template.convert("RGB"), box)
        if name == "host":
            draw.rectangle((425, 360, 435, 369), fill=(109, 160, 225))
        # Synthetic name-shaped strokes in an otherwise blank row.
        for x in range(348, 411, 7):
            y = 201 if not changed_name else 194 + (x % 6)
            draw.rectangle((x, y, x + 2, y + 10), fill="white")
    elif name in TILES:
        for box, template in TILES[name]:
            img.paste(template.convert("RGB"), box)
    img.putpixel((0, 0), (counter, 0, 0))
    return png(img)


class Provider:
    def __init__(self, rounds, size=(800, 448)):
        self.rounds = iter(rounds)
        self.rects = {hwnd: Rect(i * size[0], 0, *size) for i, (_, hwnd, _) in enumerate(BINDINGS)}
        self.ids = {hwnd: WindowIdentity(hwnd, pid, "private window title", "game")
                    for _, hwnd, pid in BINDINGS}

    def identity(self, hwnd):
        return self.ids[hwnd]

    def client_rect(self, hwnd):
        return self.rects[hwnd]

    def visible_dpi(self, hwnd, rect):
        return 96

    def screenshot_pair(self, rects):
        return next(self.rounds)


def rooms(first="host", second="guest", different=False):
    return [(panel(first, i), panel(second, i+2, different)) for i in range(2)]


class FruitPairTest(unittest.TestCase):
    def check(self, provider, **kwargs):
        result = observe_pair(provider, BINDINGS, **kwargs)
        summary = result.summary()
        self.assertEqual((summary["same_room"], summary["same_instance"]), ("UNKNOWN", "UNKNOWN"))
        self.assertEqual(summary["sequence"]["status"], "paused")
        self.assertFalse(summary["sequence"]["input_enabled"])
        return result

    def test_complementary_views_matching_member_abstain_on_shared_identity(self):
        result = self.check(Provider(rooms()))
        self.assertEqual([c.screen for c in result.captures], ["HOST_MEMBER_ROW", "GUEST_MEMBER_ROW"])
        self.assertTrue(result.member_text_shape_agrees)
        self.assertEqual(result.reason, "shared_identifiers_unobserved")
        self.assertEqual(len({s.source_id for s in result.sources}), 2)
        self.assertLess(result.sources[0].ended, result.sources[1].started)

    def test_different_members_in_lookalike_rooms(self):
        self.assertFalse(self.check(Provider(rooms(different=True))).member_text_shape_agrees)

    def test_identical_room_layout_same_role_and_swapped_roles(self):
        for roles in [("host", "host"), ("guest", "host")]:
            with self.subTest(roles=roles):
                result = self.check(Provider(rooms(*roles)))
                self.assertFalse(result.member_text_shape_agrees)
                self.assertEqual(result.reason, "complementary_room_views_missing")

    def test_single_window(self):
        self.assertEqual(self.check(Provider([(panel("host", 0),)])).reason, "paired_capture_missing")

    def test_replayed_pixels_reencoded(self):
        rounds = rooms()
        with Image.open(BytesIO(rounds[0][1])) as first:
            rounds[1] = rounds[1][0], png(first, compress_level=1)
        self.assertEqual(self.check(Provider(rounds)).reason, "static_or_replayed_capture")

    def test_watch_refuses_replay_across_batches(self):
        rounds = rooms()
        result = watch_pair(Provider(rounds + rounds), BINDINGS, Event(), lambda event: None)
        self.assertEqual(result["reason"], "static_or_replayed_capture")
        self.assertEqual(result["samples"], 1)

    def test_stale_pair(self):
        times = iter((1.0, 1.1, 2.0, 2.1, 10.0))
        self.assertEqual(self.check(Provider(rooms()), clock=lambda: next(times)).reason, "stale_pair")

    def test_pid_change_after_second_grab(self):
        p = Provider(rooms())
        def read(rects):
            data = next(p.rounds)
            if read.calls:
                p.ids[10] = p.ids[20]
            read.calls += 1
            return data
        read.calls = 0
        p.screenshot_pair = read
        self.assertEqual(self.check(p).reason, "window_identity_changed")

    def test_dpi_change_occlusion_and_geometry_drift(self):
        for problem in ("dpi", "occlusion", "geometry"):
            with self.subTest(problem=problem):
                p = Provider(rooms())
                def capture(rects):
                    if problem == "geometry":
                        p.rects[10] = Rect(1, 0, 800, 448)
                    else:
                        p.visible_dpi = lambda hwnd, rect: 120 if problem == "dpi" else None
                    return next(p.rounds)
                p.screenshot_pair = capture
                self.assertFalse(any(c.geometry_ok for c in self.check(p).captures))

    def test_transition_and_disappearing_member(self):
        first, second = rooms()
        result = self.check(Provider([first, (second[0], panel("FRUIT_LOADING", 8))]))
        self.assertEqual(result.captures[1].screen, "UNKNOWN")
        self.assertFalse(result.member_text_shape_agrees)

    def test_one_sided_reward(self):
        result = self.check(Provider(rooms("REWARD_PANEL", "FRUIT_BATTLE")))
        self.assertEqual([c.screen for c in result.captures], ["REWARD_PANEL", "FRUIT_BATTLE"])
        self.assertEqual(result.reason, "shared_identifiers_unobserved")

    def test_jsonl_contains_only_safe_evidence(self):
        summary = self.check(Provider(rooms())).summary()
        with tempfile.TemporaryDirectory() as folder:
            path = write_session_log({"paired_evidence": summary, "frame": b"private pixels",
                                      "room_code": "secret sentinel"}, log_dir=folder)
            data = Path(path).read_text(encoding="utf-8")
            self.assertEqual(json.loads(data)["details"]["paired_evidence"], summary)
            for sentinel in ("private window title", "private pixels", "secret sentinel"):
                self.assertNotIn(sentinel, data)

    def test_actual_visibility_guard_interior_overlay_and_dpi_awareness(self):
        p = object.__new__(WindowsClientProvider)
        p.wintypes, p.user32 = wintypes, Mock()
        user = p.user32
        user.GetAwarenessFromDpiAwarenessContext.return_value = 2
        user.IsIconic.return_value = False
        user.MonitorFromPoint.return_value = 5
        user.GetDpiForWindow.return_value = 144
        user.IsWindowVisible.return_value = True
        rect = Rect(0, 0, 800, 448)
        user.GetWindow.return_value = 0
        self.assertEqual(p.visible_dpi(10, rect), 144)
        def overlay(hwnd, pointer):
            box = ctypes.cast(pointer, ctypes.POINTER(wintypes.RECT)).contents
            box.left, box.top, box.right, box.bottom = (300, 150, 310, 160)
            return True
        user.GetWindow.side_effect = lambda hwnd, direction: 99 if hwnd == 10 else 0
        user.GetWindowRect.side_effect = overlay
        self.assertIsNone(p.visible_dpi(10, rect))
        user.GetAwarenessFromDpiAwarenessContext.return_value = 1
        self.assertIsNone(p.visible_dpi(10, rect))

    def test_one_desktop_grab_split_in_binding_order(self):
        p = object.__new__(WindowsClientProvider)
        im = Image.new("RGB", (6, 2), "red")
        ImageDraw.Draw(im).rectangle((4, 0, 5, 1), fill="blue")
        p._capture = Mock(return_value=png(im))
        rects = (Rect(2, -1, 2, 2), Rect(-2, -1, 2, 2))
        result = p.screenshot_pair(rects)
        p._capture.assert_called_once_with(Rect(-2, -1, 6, 2))
        colors = [Image.open(BytesIO(data)).getpixel((0, 0)) for data in result]
        self.assertEqual(colors, [(0, 0, 255), (255, 0, 0)])


@unittest.skipUnless(os.environ.get("YOYO_FRUIT_VIDEO"), "optional original dual-window MP4")
class RecordingTest(unittest.TestCase):
    def test_real_recording(self):
        path = Path(os.environ["YOYO_FRUIT_VIDEO"])
        with path.open("rb") as f:
            self.assertEqual(hashlib.file_digest(f, "sha256").hexdigest(),
                             "ddfaeeb849cd2fb9ad0a266370c64c7446ef2cfedf56b0c13f555b574060a7e2")
        # Geometry belongs only to this SHA-pinned recording. No full frames persisted.
        cases = [
            ((27.4, 28.0), ("ROOM_WAITING", "PRIVATE_JOIN"), False),
            ((28.75, 28.8), ("HOST_MEMBER_ROW", "GUEST_MEMBER_ROW"), True),
            ((28.8, 29.6), ("UNKNOWN", "UNKNOWN"), False),
            ((29.2, 29.6), ("FRUIT_LOADING", "FRUIT_LOADING"), False),
            ((189.4, 189.65), ("FRUIT_SETTLEMENT", "FRUIT_SETTLEMENT"), False),
            ((190.1, 190.6), ("UNKNOWN", "FRUIT_SETTLEMENT"), False),
            ((191, 191.4), ("FRUIT_RECEIPT_IN_PORT", "UNKNOWN"), False),
            ((191.9, 192.05), ("FRUIT_RECEIPT_IN_PORT", "FRUIT_RECEIPT_IN_PORT"), False),
        ]
        outcome_rounds = []
        for times, expected, agreement in cases:
            with self.subTest(times=times):
                rounds = []
                for t in times:
                    data = subprocess.check_output(["ffmpeg", "-v", "error", "-ss", str(t), "-i",
                        str(path), "-frames:v", "1", "-f", "image2pipe", "-c:v", "png", "-"])
                    with Image.open(BytesIO(data)) as im:
                        rounds.append(tuple(png(im.crop((x, 369, x+1228, 1059))) for x in (55, 1286)))
                if times[0] >= 189:
                    outcome_rounds.extend(rounds)
                result = observe_pair(Provider(rounds, (1228, 690)), BINDINGS)
                self.assertEqual(tuple(c.screen for c in result.captures), expected)
                self.assertEqual(result.member_text_shape_agrees, agreement)
                self.assertEqual(result.sequence()["status"], "paused")
                self.assertFalse(result.sequence()["input_enabled"])

        events = []
        result = watch_pair(Provider(outcome_rounds, (1228, 690)), BINDINGS, Event(), events.append)
        self.assertEqual(result["reason"], "both_port_receipts_observed_after_settlement")
        self.assertEqual(result["samples"], 4)
        self.assertEqual(result["same_instance"], "UNKNOWN")
        self.assertFalse(result["input_enabled"])
        self.assertEqual([list(e["receipt_after_settlement"].values()) for e in events],
                         [[False, False], [False, False], [True, False], [True, True]])
