from threading import Event
import unittest
from unittest.mock import patch

from PIL import Image

from fruit_pair_evidence import Grab, PairResult, watch_pair
from fruit_receipt import CHANNEL, OBTAINED, GIFT, QUANTITY, FRUIT, PORT, outcome_panel
from observation_bridge import CaptureEvidence
from test_fruit_pair_evidence import BINDINGS, Provider


def render(*markers):
    image = Image.new("L", (800, 448), 36)
    for box, mask in markers:
        image.paste(235, box, mask)
    return image


class ReceiptTests(unittest.TestCase):
    def test_visible_system_gift_in_port(self):
        img = render(PORT, CHANNEL, OBTAINED, GIFT, QUANTITY)
        self.assertEqual(outcome_panel(img, "UNKNOWN"), "FRUIT_RECEIPT_IN_PORT")
        self.assertEqual(outcome_panel(img, "ROOM_LIST"), "ROOM_LIST")

    def test_each_text_region_is_required(self):
        markers = (PORT, CHANNEL, OBTAINED, GIFT, QUANTITY)
        for i in range(len(markers)):
            with self.subTest(index=i):
                self.assertEqual(outcome_panel(render(*markers[:i], *markers[i+1:]), "UNKNOWN"), "UNKNOWN")

    def test_near_match_missing_single_character(self):
        img = render(PORT, CHANNEL, OBTAINED, GIFT, QUANTITY)
        x, y, right, bottom = GIFT[0]
        img.paste(36, (right - 13, y, right, bottom))
        self.assertEqual(outcome_panel(img, "UNKNOWN"), "UNKNOWN")

    def test_old_line_at_settlement(self):
        img = render(FRUIT)
        box, mask = GIFT
        x, y, right, bottom = box
        img.paste(225, (x, y-18, right, bottom-18), mask)
        self.assertEqual(outcome_panel(img, "REWARD_PANEL"), "FRUIT_SETTLEMENT_WITH_RECEIPT")
        self.assertEqual(outcome_panel(render(), "REWARD_PANEL"), "REWARD_PANEL")


class WatchTests(unittest.TestCase):
    def run_watch(self, rows):
        events = []
        stop = Event()
        batches = []
        for t, *states in rows:
            captures = tuple(CaptureEvidence(*b, True, True, True, s) for b, s in zip(BINDINGS, states))
            batches.append(PairResult(captures, (Grab(str(t), t, t+0.1), Grab(str(t+1), t+0.2, t+0.3)),
                                      False, "shared_identifiers_unobserved"))
        def read(*args, **kwargs):
            if len(batches) == 1:
                # The following wait cancels only after processing the last sample.
                stop.wait = lambda _: stop.set()
            return batches.pop(0)
        with patch("fruit_pair_evidence.observe_pair", side_effect=read):
            result = watch_pair(Provider([]), BINDINGS, stop, events.append, clock=lambda: 0)
        self.assertFalse(result["input_enabled"])
        self.assertFalse(result["game_state_verified"])
        self.assertEqual(result["same_instance"], "UNKNOWN")
        return result

    def test_old_messages_on_launch_never_complete(self):
        result = self.run_watch([(1, "FRUIT_RECEIPT_IN_PORT", "FRUIT_RECEIPT_IN_PORT")])
        self.assertEqual(result["receipt_after_settlement"], {"main": False, "alt": False})

    def test_prior_receipt_and_repeated_capture_pause(self):
        settlement = "FRUIT_SETTLEMENT"
        old = self.run_watch([(1, settlement, "FRUIT_SETTLEMENT_WITH_RECEIPT")])
        self.assertEqual(old["reason"], "receipt_already_visible_at_settlement")
        reused = self.run_watch([(1, settlement, settlement), (1, settlement, settlement)])
        self.assertEqual(reused["reason"], "capture_time_invalid")

    def test_single_receipt_and_expired_association(self):
        settlement, receipt = "FRUIT_SETTLEMENT", "FRUIT_RECEIPT_IN_PORT"
        result = self.run_watch([(1, settlement, settlement), (2, receipt, "UNKNOWN")])
        self.assertEqual(result["receipt_after_settlement"], {"main": True, "alt": False})
        result = self.run_watch([(1, settlement, settlement), (20, receipt, receipt)])
        self.assertEqual(result["reason"], "settlement_window_expired")

    def test_reentry_breaks_settlement_association(self):
        result = self.run_watch([(1, "FRUIT_SETTLEMENT", "FRUIT_SETTLEMENT"), (2, "OBJECTIVES", "FRUIT_BATTLE")])
        self.assertEqual(result["reason"], "scene_changed_after_settlement")
