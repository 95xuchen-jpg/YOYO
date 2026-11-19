import unittest

from gameplay_flows import (
    COOP_MODE_RANGES, DUNGEON_RULES, CoopFlow, CoopObservation,
    DungeonFlow, DungeonObservation, gameplay_demo, sweep_advice,
)


def co(*args, **kwargs):
    kwargs.setdefault("stable", True)
    kwargs.setdefault("identity_ok", True)
    kwargs.setdefault("geometry_ok", True)
    return CoopObservation(*args, **kwargs)


def do(*args, **kwargs):
    kwargs.setdefault("stable", True)
    kwargs.setdefault("identity_ok", True)
    kwargs.setdefault("geometry_ok", True)
    return DungeonObservation(*args, **kwargs)


class CoopFlowTests(unittest.TestCase):
    def setUp(self):
        self.flow = CoopFlow("A", "B", leader="A", mode="协力对战")

    def pair(self, screen, **kwargs):
        common = dict(mode="协力对战", daily_rewards_remaining=3)
        common.update(kwargs)
        return (
            co("A", 101, "S", screen, **common),
            co("B", 202, "S", screen, **common),
        )

    def test_unverified_observation_defaults_fail_closed(self):
        pair = (
            CoopObservation("A", 101, "S", "COOP_HOME", mode="协力对战"),
            CoopObservation("B", 202, "S", "COOP_HOME", mode="协力对战"),
        )
        self.assertEqual(self.flow.advance(pair).reason, "two_frame_confirmation_missing")

    def test_controller_rejects_more_than_its_two_accounts(self):
        with self.assertRaises(ValueError):
            CoopFlow("A", "B", leader="A", expected_players=3)

    def test_create_room_from_coop_home(self):
        d = self.flow.advance(self.pair("COOP_HOME"))
        self.assertEqual((d.action, d.account, d.phase), ("CREATE_ROOM", "A", "ROOM_SETUP"))
        self.assertFalse(d.input_enabled)

    def test_join_only_exact_visible_room(self):
        pair = (
            co("A", 101, "S", "ROOM", mode="协力对战", room_id="R",
                            room_owner="A", room_members=("A",), room_capacity=4),
            co("B", 202, "S", "ROOM_LIST", mode="协力对战",
                            listed_room_id="R", listed_room_owner="A"),
        )
        d = self.flow.advance(pair)
        self.assertEqual((d.action, d.account), ("JOIN_ROOM", "B"))

    def test_full_room_waits_for_automatic_match(self):
        d = self.flow.advance(self.pair("ROOM", room_id="R", room_owner="A",
                                        room_members=("A", "B"), room_capacity=4))
        self.assertEqual((d.phase, d.action), ("MATCHING", "WAIT_FOR_MATCH"))

    def test_complete_match_battle_result_sequence(self):
        steps = [
            self.pair("COOP_HOME"),
            (
                co("A", 101, "S", "ROOM", mode="协力对战", room_id="R",
                                room_owner="A", room_members=("A",), room_capacity=4),
                co("B", 202, "S", "ROOM_LIST", mode="协力对战",
                                listed_room_id="R", listed_room_owner="A"),
            ),
            self.pair("ROOM", room_id="R", room_owner="A", room_members=("A", "B"), room_capacity=4),
            self.pair("MATCH_SUCCESS", match_id="M"),
            self.pair("BATTLE", match_id="M"),
            self.pair("RESULT", match_id="M", result="win"),
        ]
        results = [self.flow.advance(x) for x in steps]
        self.assertEqual(results[-1].phase, "COMPLETED")
        self.assertEqual(results[-1].action, "REVIEW_RESULT_AND_REWARDS")
        self.assertTrue(all(not x.input_enabled for x in results))

    def test_room_id_mismatch_pauses(self):
        d = self.flow.advance((
            co("A", 101, "S", "ROOM", mode="协力对战", room_id="R1",
                            room_owner="A", room_members=("A", "B"), room_capacity=4),
            co("B", 202, "S", "ROOM", mode="协力对战", room_id="R2",
                            room_owner="A", room_members=("A", "B"), room_capacity=4),
        ))
        self.assertEqual((d.status, d.reason), ("paused", "co_op_room_id_mismatch"))

    def test_account_hwnd_swap_pauses(self):
        self.flow.advance(self.pair("COOP_HOME"))
        swapped = (
            co("A", 202, "S", "COOP_HOME", mode="协力对战"),
            co("B", 101, "S", "COOP_HOME", mode="协力对战"),
        )
        self.assertEqual(self.flow.advance(swapped).reason, "account_window_binding_changed")

    def test_wrong_server_pauses(self):
        pair = self.pair("COOP_HOME")
        pair = (pair[0], co("B", 202, "OTHER", "COOP_HOME", mode="协力对战"))
        self.assertEqual(self.flow.advance(pair).reason, "server_mismatch_or_unknown")

    def test_unstable_frame_pair_pauses(self):
        pair = self.pair("COOP_HOME")
        pair = (pair[0], co("B", 202, "S", "COOP_HOME", stable=False))
        self.assertEqual(self.flow.advance(pair).reason, "two_frame_confirmation_missing")

    def test_capacity_outside_mode_range_pauses(self):
        d = self.flow.advance(self.pair("ROOM", room_id="R", room_owner="A",
                                        room_members=("A", "B"), room_capacity=5))
        self.assertEqual(d.reason, "room_capacity_outside_mode_range")

    def test_no_daily_reward_pauses(self):
        d = self.flow.advance(self.pair("COOP_HOME", daily_rewards_remaining=0))
        self.assertEqual(d.reason, "daily_coop_rewards_exhausted")

    def test_one_account_in_battle_other_in_room_list_pauses(self):
        pair = (
            co("A", 101, "S", "BATTLE", mode="协力对战", match_id="M"),
            co("B", 202, "S", "ROOM_LIST", mode="协力对战"),
        )
        self.assertEqual(self.flow.advance(pair).reason, "dual_account_phase_mismatch")

    def test_match_ids_must_match(self):
        d = self.flow.advance((
            co("A", 101, "S", "MATCH_SUCCESS", mode="协力对战", match_id="M1"),
            co("B", 202, "S", "MATCH_SUCCESS", mode="协力对战", match_id="M2"),
        ))
        self.assertEqual(d.reason, "match_id_mismatch")

    def test_stall_timeout_pauses(self):
        now = [0.0]
        flow = CoopFlow("A", "B", leader="A", clock=lambda: now[0], stall_timeout=5)
        pair = (
            co("A", 101, "S", "COOP_HOME", mode="协力对战"),
            co("B", 202, "S", "COOP_HOME", mode="协力对战"),
        )
        flow.advance(pair)
        now[0] = 6
        d = flow.advance(pair)
        self.assertEqual(d.reason, "co_op_state_stalled")


class DungeonFlowTests(unittest.TestCase):
    def setUp(self):
        self.flow = DungeonFlow("A", "B", dungeon="勇闯火焰山", leader="A")

    def pair(self, screen, **kwargs):
        return (
            do("A", 101, "S", "勇闯火焰山", screen, **kwargs),
            do("B", 202, "S", "勇闯火焰山", screen, **kwargs),
        )

    def test_shared_room_starts_only_after_both_members_verified(self):
        d = self.flow.advance(self.pair("ROOM", room_id="R", room_owner="A", room_members=("A", "B")))
        self.assertEqual((d.phase, d.action, d.account), ("ROOM_READY", "START_DUNGEON", "A"))

    def test_shared_instance_progression(self):
        steps = [
            self.pair("ROOM", room_id="R", room_owner="A", room_members=("A", "B")),
            self.pair("LOADING", instance_id="I"),
            self.pair("MAP", instance_id="I", objectives=(("目标", 1, 3),)),
            self.pair("BATTLE", instance_id="I", battle_round=1),
            self.pair("REWARD", instance_id="I"),
            self.pair("COMPLETE", instance_id="I", result="win"),
        ]
        results = [self.flow.advance(x) for x in steps]
        self.assertEqual(results[-1].phase, "COMPLETED")
        self.assertEqual(results[-1].action, "REVIEW_COMPLETION")

    def test_shared_room_membership_mismatch_pauses(self):
        d = self.flow.advance(self.pair("ROOM", room_id="R", room_owner="A", room_members=("A",)))
        self.assertEqual(d.reason, "shared_room_membership_unverified")

    def test_dungeon_account_hwnd_swap_pauses(self):
        self.flow.advance(self.pair("ROOM", room_id="R", room_owner="A", room_members=("A", "B")))
        swapped = (
            do("A", 202, "S", "勇闯火焰山", "LOADING", instance_id="I"),
            do("B", 101, "S", "勇闯火焰山", "LOADING", instance_id="I"),
        )
        self.assertEqual(self.flow.advance(swapped).reason, "account_window_binding_changed")

    def test_shared_instance_mismatch_pauses(self):
        d = self.flow.advance((
            do("A", 101, "S", "勇闯火焰山", "LOADING", instance_id="I1"),
            do("B", 202, "S", "勇闯火焰山", "LOADING", instance_id="I2"),
        ))
        self.assertEqual(d.reason, "shared_instance_id_mismatch")

    def test_objective_regression_pauses(self):
        self.flow.advance(self.pair("MAP", instance_id="I", objectives=(("目标", 2, 3),)))
        d = self.flow.advance(self.pair("MAP", instance_id="I", objectives=(("目标", 1, 3),)))
        self.assertEqual(d.reason, "objective_progress_regressed_or_changed")

    def test_shared_battle_round_disagreement_pauses(self):
        d = self.flow.advance((
            do("A", 101, "S", "勇闯火焰山", "BATTLE", instance_id="I", battle_round=2),
            do("B", 202, "S", "勇闯火焰山", "BATTLE", instance_id="I", battle_round=3),
        ))
        self.assertEqual(d.reason, "shared_battle_round_disagrees")

    def test_parallel_mode_allows_different_screens_but_never_inputs(self):
        flow = DungeonFlow("A", "B", dungeon="水果剧团", leader="A", relationship="parallel")
        pair = (
            do("A", 101, "S", "水果剧团", "MAP", instance_id="IA"),
            do("B", 202, "S", "水果剧团", "BATTLE", instance_id="IB", auto_battle_active=False),
        )
        d = flow.advance(pair)
        self.assertEqual(d.status, "waiting")
        self.assertEqual(d.account, "A")
        self.assertFalse(d.input_enabled)

    def test_parallel_battle_reports_manual_required(self):
        flow = DungeonFlow("A", "B", dungeon="水果剧团", leader="A", relationship="parallel")
        pair = (
            do("A", 101, "S", "水果剧团", "COMPLETE", instance_id="IA", result="win"),
            do("B", 202, "S", "水果剧团", "BATTLE", instance_id="IB", auto_battle_active=False),
        )
        d = flow.advance(pair)
        self.assertEqual((d.action, d.account), ("MANUAL_BATTLE_REQUIRED", "B"))

    def test_unknown_screen_pauses(self):
        d = self.flow.advance(self.pair("UNKNOWN", instance_id="I"))
        self.assertEqual(d.reason, "unknown_dungeon_screen")

    def test_sweep_requires_explicit_opt_in_and_unlock(self):
        self.assertEqual(sweep_advice("水果剧团", explicitly_requested=False, unlocked=True, coupon_count=1)["reason"],
                         "explicit_opt_in_required")
        self.assertEqual(sweep_advice("勇闯火焰山", explicitly_requested=True, unlocked=True, coupon_count=1)["reason"],
                         "sweep_not_confirmed_for_dungeon")
        self.assertTrue(sweep_advice("水果剧团", explicitly_requested=True, unlocked=True, coupon_count=1)["eligible"])
        self.assertFalse(sweep_advice("水果剧团", explicitly_requested=True, unlocked=False, coupon_count=1)["eligible"])

    def test_demo_runs_both_flows_without_input(self):
        report = gameplay_demo()
        self.assertFalse(report["input_enabled"])
        self.assertEqual(report["coop"][-1]["phase"], "COMPLETED")
        self.assertEqual(report["dungeon"][-1]["phase"], "COMPLETED")


if __name__ == "__main__":
    unittest.main()
