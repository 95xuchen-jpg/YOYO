import json
import tempfile
import unittest
from pathlib import Path

from fruit_replay import replay_jsonl


def record(state, **kwargs):
    item = dict(main_state=state, alt_state=state, main_stable=True,
                alt_stable=True, same_room_verified=False,
                same_instance_verified=False, main_reward_specific=False,
                alt_reward_specific=False)
    item.update(kwargs)
    return item


class ReplayTests(unittest.TestCase):
    def replay(self, items):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "frames.jsonl"
            path.write_text("".join(json.dumps(x) + "\n" for x in items), encoding="utf-8")
            return replay_jsonl(path)

    def test_full_ordered_sequence_is_only_advisory(self):
        result = self.replay([
            record("ROOM_WAITING", same_room_verified=True),
            record("FRUIT_LOADING", same_instance_verified=True),
            record("FRUIT_BATTLE", same_instance_verified=True),
            record("REWARD", same_instance_verified=True,
                   main_reward_specific=True, alt_reward_specific=True),
            record("COMPLETE", same_instance_verified=True),
        ])
        self.assertEqual(result["status"], "completed")
        self.assertFalse(result["input_enabled"])

    def test_repeated_frames_do_not_stop_valid_capture(self):
        frames = [
            record("ROOM_WAITING", same_room_verified=True),
            record("ROOM_WAITING", same_room_verified=True),
            record("FRUIT_LOADING", same_instance_verified=True),
            record("FRUIT_LOADING", same_instance_verified=True),
            record("FRUIT_BATTLE", same_instance_verified=True),
            record("FRUIT_BATTLE", same_instance_verified=True),
            record("REWARD", same_instance_verified=True,
                   main_reward_specific=True, alt_reward_specific=True),
            record("REWARD", same_instance_verified=True,
                   main_reward_specific=True, alt_reward_specific=True),
            record("COMPLETE", same_instance_verified=True),
        ]
        result = self.replay(frames)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(len(result["decisions"]), len(frames))
        self.assertTrue(all(not d["input_enabled"] for d in result["decisions"]))

    def test_missing_verification_on_repeated_frame_pauses(self):
        result = self.replay([
            record("ROOM_WAITING", same_room_verified=True),
            record("ROOM_WAITING", same_room_verified=False),
        ])
        self.assertEqual(result["reason"], "entry_not_confirmed")

    def test_generic_reward_pauses(self):
        result = self.replay([
            record("ROOM_WAITING", same_room_verified=True),
            record("FRUIT_LOADING", same_instance_verified=True),
            record("FRUIT_BATTLE", same_instance_verified=True),
            record("REWARD", same_instance_verified=True),
        ])
        self.assertEqual(result["reason"], "dungeon_specific_reward_not_confirmed")

    def test_invalid_or_missing_fields_pause(self):
        self.assertEqual(self.replay([{"main_state": "ROOM_WAITING"}])["reason"], "invalid_evidence")
        self.assertEqual(self.replay([record("ROOM_WAITING", main_stable=1)])["reason"], "invalid_evidence")
        self.assertEqual(self.replay([])["reason"], "empty_evidence")

    def test_two_accounts_out_of_sync_pause(self):
        result = self.replay([record("ROOM_WAITING", alt_state="ROOM_LIST",
                                     same_room_verified=True)])
        self.assertEqual(result["reason"], "dual_account_state_mismatch")


if __name__ == "__main__":
    unittest.main()
