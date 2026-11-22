import unittest

from fruit_sequence_gate import FruitEvidence, FruitSequenceGate


def evidence(main, alt=None, **kwargs):
    return FruitEvidence(main, alt if alt is not None else main, True, True, **kwargs)


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

    def test_generic_reward_is_not_proof_of_completion(self):
        gate = FruitSequenceGate()
        for step in (
            evidence("ROOM_WAITING", same_room_verified=True),
            evidence("FRUIT_LOADING", same_instance_verified=True),
            evidence("FRUIT_BATTLE", same_instance_verified=True),
        ):
            gate.advance(step)
        result = gate.advance(evidence("REWARD", same_instance_verified=True))
        self.assertEqual(result["reason"], "dungeon_specific_reward_not_confirmed")
        self.assertEqual(gate.advance(evidence("COMPLETE", same_instance_verified=True))["status"], "paused")

    def test_mismatched_account_state_stops(self):
        gate = FruitSequenceGate()
        result = gate.advance(evidence("ROOM_WAITING", "ROOM_LIST", same_room_verified=True))
        self.assertEqual(result["status"], "paused")

    def test_unstable_capture_stops(self):
        gate = FruitSequenceGate()
        result = gate.advance(FruitEvidence("ROOM_WAITING", "ROOM_WAITING", True, False, True))
        self.assertEqual(result["reason"], "unstable_dual_capture")

    def test_cannot_skip_to_reward(self):
        gate = FruitSequenceGate()
        result = gate.advance(evidence("REWARD", same_instance_verified=True,
                                       main_reward_specific=True, alt_reward_specific=True))
        self.assertEqual(result["status"], "paused")


if __name__ == "__main__":
    unittest.main()
