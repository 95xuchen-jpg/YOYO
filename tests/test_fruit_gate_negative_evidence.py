"""Fail-closed negative cases for Fruit Troupe dual-account evidence gate.

These tests deliberately avoid any game input or room-code fixtures.
"""
import unittest

from fruit_sequence_gate import FruitEvidence, FruitSequenceGate


def frame(main, alt=None, **flags):
    return FruitEvidence(main, main if alt is None else alt, True, True, **flags)


class FruitGateNegativeTests(unittest.TestCase):
    def test_non_boolean_claims_cannot_unlock_room(self):
        for invalid in (1, "true", None):
            with self.subTest(value=invalid):
                gate = FruitSequenceGate()
                result = gate.advance(frame("ROOM_WAITING", same_room_verified=invalid))
                self.assertEqual(result["reason"], "invalid_evidence")
                self.assertFalse(result["input_enabled"])

    def test_instance_proof_cannot_be_dropped_mid_battle(self):
        gate = FruitSequenceGate()
        gate.advance(frame("ROOM_WAITING", same_room_verified=True))
        gate.advance(frame("FRUIT_LOADING", same_instance_verified=True))
        gate.advance(frame("FRUIT_BATTLE", same_instance_verified=True))
        result = gate.advance(frame("FRUIT_BATTLE"))
        self.assertEqual(result["reason"], "shared_instance_not_confirmed")
        self.assertFalse(result["input_enabled"])

    def test_reward_claim_on_battle_screen_stops(self):
        gate = FruitSequenceGate()
        gate.advance(frame("ROOM_WAITING", same_room_verified=True))
        gate.advance(frame("FRUIT_LOADING", same_instance_verified=True))
        gate.advance(frame("FRUIT_BATTLE", same_instance_verified=True))
        result = gate.advance(frame(
            "FRUIT_BATTLE", same_instance_verified=True,
            main_reward_specific=True))
        self.assertEqual(result["reason"], "reward_evidence_state_mismatch")

    def test_one_account_cannot_finish_without_own_reward(self):
        gate = FruitSequenceGate()
        gate.advance(frame("ROOM_WAITING", same_room_verified=True))
        gate.advance(frame("FRUIT_LOADING", same_instance_verified=True))
        gate.advance(frame("FRUIT_BATTLE", same_instance_verified=True))
        gate.advance(frame(
            "REWARD", "FRUIT_BATTLE", same_instance_verified=True,
            main_reward_specific=True))
        result = gate.advance(frame(
            "COMPLETE", "COMPLETE", same_instance_verified=True))
        self.assertEqual(result["reason"], "completion_without_reward_evidence")
        self.assertFalse(result["input_enabled"])

    def test_pause_is_latched_even_after_good_evidence(self):
        gate = FruitSequenceGate()
        gate.advance(frame("ROOM_WAITING"))
        result = gate.advance(frame("ROOM_WAITING", same_room_verified=True))
        self.assertEqual(result["status"], "paused")
        self.assertEqual(result["action"], "STOP_AND_REVIEW")
        self.assertFalse(result["input_enabled"])


if __name__ == "__main__":
    unittest.main()
