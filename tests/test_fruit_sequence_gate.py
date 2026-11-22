import unittest

from fruit_sequence_gate import FruitEvidence, FruitSequenceGate


def evidence(main, alt=None, **kwargs):
    return FruitEvidence(main, alt if alt is not None else main, True, True, **kwargs)


def enter_battle(gate):
    gate.advance(evidence("ROOM_WAITING", same_room_verified=True))
    gate.advance(evidence("FRUIT_LOADING", same_instance_verified=True))


class FruitSequenceGateTests(unittest.TestCase):
    def test_ordered_two_account_progress_is_advisory(self):
        gate = FruitSequenceGate()
        steps = [
            evidence("ROOM_WAITING", same_room_verified=True),
            evidence("FRUIT_LOADING", same_instance_verified=True),
            evidence("FRUIT_BATTLE", same_instance_verified=True),
            evidence("REWARD", same_instance_verified=True,
                     main_reward_specific=True, alt_reward_specific=True),
            evidence("COMPLETE", same_instance_verified=True),
        ]
        results = [gate.advance(step) for step in steps]
        self.assertEqual(results[-1]["status"], "completed")
        self.assertTrue(all(not item["input_enabled"] for item in results))

    def test_repeated_map_and_battle_frames_allow_local_phase_difference(self):
        gate = FruitSequenceGate()
        enter_battle(gate)
        first = gate.advance(evidence(
            "OBJECTIVES", "FRUIT_BATTLE", same_instance_verified=True))
        second = gate.advance(evidence(
            "FRUIT_BATTLE", "OBJECTIVES", same_instance_verified=True))
        self.assertEqual(first["phase"], "BATTLE")
        self.assertEqual(second["phase"], "BATTLE")
        self.assertEqual(second["action"], "OBSERVE_BATTLE")
        self.assertFalse(second["input_enabled"])

    def test_one_account_can_reach_reward_before_the_other(self):
        gate = FruitSequenceGate()
        enter_battle(gate)
        ahead = gate.advance(evidence(
            "REWARD", "FRUIT_BATTLE", same_instance_verified=True,
            main_reward_specific=True))
        self.assertEqual(ahead["status"], "waiting")
        self.assertEqual(ahead["phase"], "BATTLE")
        self.assertEqual(ahead["action"], "WAIT_FOR_OTHER_ACCOUNT_REWARD")
        both_rewarded = gate.advance(evidence(
            "COMPLETE", "REWARD", same_instance_verified=True,
            alt_reward_specific=True))
        self.assertEqual(both_rewarded["phase"], "REWARD")
        self.assertEqual(both_rewarded["action"], "REVIEW_REWARDS")
        completed = gate.advance(evidence(
            "COMPLETE", "COMPLETE", same_instance_verified=True))
        self.assertEqual(completed["status"], "completed")
        self.assertFalse(completed["input_enabled"])

    def test_generic_reward_is_not_completion_evidence(self):
        gate = FruitSequenceGate()
        enter_battle(gate)
        generic = gate.advance(evidence(
            "REWARD_PANEL", "REWARD_PANEL", same_instance_verified=True))
        self.assertEqual(generic["status"], "waiting")
        self.assertEqual(generic["phase"], "BATTLE")
        self.assertEqual(generic["reason"], "dungeon_specific_reward_not_confirmed")
        skipped = gate.advance(evidence(
            "COMPLETE", "COMPLETE", same_instance_verified=True))
        self.assertEqual(skipped["status"], "paused")
        self.assertEqual(skipped["reason"], "completion_without_reward_evidence")

    def test_mismatched_account_state_stops(self):
        gate = FruitSequenceGate()
        result = gate.advance(evidence(
            "ROOM_WAITING", "ROOM_LIST", same_room_verified=True))
        self.assertEqual(result["status"], "paused")

    def test_unstable_capture_stops(self):
        gate = FruitSequenceGate()
        result = gate.advance(FruitEvidence(
            "ROOM_WAITING", "ROOM_WAITING", True, False, True))
        self.assertEqual(result["reason"], "unstable_dual_capture")

    def test_cannot_skip_to_reward(self):
        gate = FruitSequenceGate()
        result = gate.advance(evidence(
            "REWARD", same_instance_verified=True,
            main_reward_specific=True, alt_reward_specific=True))
        self.assertEqual(result["status"], "paused")

    def test_missing_instance_verification_stops_after_room(self):
        gate = FruitSequenceGate()
        gate.advance(evidence("ROOM_WAITING", same_room_verified=True))
        result = gate.advance(evidence("FRUIT_LOADING"))
        self.assertEqual(result["reason"], "shared_instance_not_confirmed")

    def test_account_phase_regression_stops(self):
        gate = FruitSequenceGate()
        enter_battle(gate)
        result = gate.advance(evidence(
            "ROOM_WAITING", "FRUIT_BATTLE", same_instance_verified=True))
        self.assertEqual(result["reason"], "account_phase_regressed")

    def test_unknown_screen_stops(self):
        gate = FruitSequenceGate()
        result = gate.advance(evidence(
            "ROOM_WAITING", "UNKNOWN", same_room_verified=True))
        self.assertEqual(result["reason"], "unknown_screen")


if __name__ == "__main__":
    unittest.main()
