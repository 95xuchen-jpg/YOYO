"""Observation-driven dual-account dungeon/co-op state machines.

This module only interprets verified observations and emits advisory plans.
It never clicks, sends keys, spends items, starts battles, or claims rewards.
"""
from dataclasses import asdict, dataclass
from typing import Iterable


# Source-backed catalog. "guide_level" is a progression hint, not an enforced minimum.
# Player-count rules are only recorded where the official TapTap announcement states them.
DUNGEON_RULES = {
    "水果剧团": {"sweep": True, "party_range": None},
    "挑战十二生肖": {"sweep": True, "party_range": None},
    "史莱姆居地": {"sweep": True, "party_range": (2, 12)},
    "幽灵之地": {"sweep": True, "party_range": (2, 12)},
    "马利大进击": {"sweep": True, "party_range": (2, 12)},
    "亚历山大帝": {"sweep": False, "party_range": (2, 12)},
    "十八铜人阵": {"sweep": False, "party_range": (2, 12)},
    "海底全动员": {"sweep": False, "party_range": (2, 12)},
    "侏罗纪牧场": {"sweep": False, "party_range": (2, 12)},
    "勇闯火焰山": {"sweep": False, "party_range": (2, 12)},
    "拯救蓝星人": {"sweep": False, "party_range": (2, 12)},
    # The 10/13 official notice added sweep for these exact names.
    "黑暗藏身地": {"sweep": True, "party_range": None},
    "海底总动员": {"sweep": True, "party_range": None},
}

COOP_MODE_RANGES = {
    "协力对战": (2, 4),
    "黑蔷薇之影": (2, 4),
}

SWEEP_DUNGEONS = frozenset(name for name, spec in DUNGEON_RULES.items() if spec["sweep"])


@dataclass(frozen=True)
class FlowDecision:
    status: str
    phase: str
    action: str
    account: str | None = None
    reason: str | None = None
    input_enabled: bool = False

    def to_dict(self):
        return asdict(self)


@dataclass(frozen=True)
class CoopObservation:
    account_id: str
    window_id: int
    server_id: str
    screen: str
    stable: bool = False
    identity_ok: bool = False
    geometry_ok: bool = False
    mode: str = ""
    room_id: str | None = None
    room_owner: str | None = None
    room_members: tuple[str, ...] = ()
    room_capacity: int | None = None
    listed_room_id: str | None = None
    listed_room_owner: str | None = None
    match_id: str | None = None
    result: str | None = None
    daily_rewards_remaining: int | None = None


@dataclass(frozen=True)
class DungeonObservation:
    account_id: str
    window_id: int
    server_id: str
    dungeon: str
    screen: str
    stable: bool = False
    identity_ok: bool = False
    geometry_ok: bool = False
    room_id: str | None = None
    room_owner: str | None = None
    room_members: tuple[str, ...] = ()
    listed_room_id: str | None = None
    listed_room_owner: str | None = None
    instance_id: str | None = None
    # Each item is (objective_name, completed_count, total_count).
    objectives: tuple[tuple[str, int, int], ...] = ()
    battle_round: int | None = None
    auto_battle_active: bool = False
    result: str | None = None
    sweep_unlocked: bool = False
    sweep_coupon_count: int = 0


def _validate_pair(observations: Iterable, accounts: tuple[str, str]):
    items = tuple(observations)
    if len(items) != 2:
        return None, "exactly_two_observations_required"
    by_account = {item.account_id: item for item in items}
    if len(by_account) != 2 or set(by_account) != set(accounts):
        return None, "account_identity_mismatch"
    ordered = tuple(by_account[name] for name in accounts)
    if len({item.window_id for item in ordered}) != 2:
        return None, "duplicate_window_binding"
    if any(not item.stable for item in ordered):
        return None, "two_frame_confirmation_missing"
    if any(not item.identity_ok for item in ordered):
        return None, "window_identity_unverified"
    if any(not item.geometry_ok for item in ordered):
        return None, "window_geometry_unstable"
    servers = {item.server_id for item in ordered}
    if len(servers) != 1 or not next(iter(servers)):
        return None, "server_mismatch_or_unknown"
    return ordered, None


def sweep_advice(dungeon: str, *, explicitly_requested: bool,
                 unlocked: bool, coupon_count: int):
    """Return a read-only eligibility assessment; never consumes a sweep ticket."""
    spec = DUNGEON_RULES.get(dungeon)
    if spec is None:
        return {"eligible": False, "reason": "unknown_dungeon", "input_enabled": False}
    if not explicitly_requested:
        return {"eligible": False, "reason": "explicit_opt_in_required", "input_enabled": False}
    if not spec["sweep"]:
        return {"eligible": False, "reason": "sweep_not_confirmed_for_dungeon", "input_enabled": False}
    if not unlocked:
        return {"eligible": False, "reason": "dungeon_not_observed_as_unlocked", "input_enabled": False}
    if coupon_count <= 0:
        return {"eligible": False, "reason": "no_sweep_coupon_observed", "input_enabled": False}
    return {"eligible": True, "reason": "review_confirmation_manually", 
            "action": "REVIEW_SWEEP_CONFIRMATION", "input_enabled": False}


class CoopFlow:
    """Two-account co-op room/match/battle/result state machine.

    The video shows a 2/2 room followed by automatic matching. The machine therefore
    waits for matching after the full room is verified; it does not click a start button.
    """
    def __init__(self, account_a: str, account_b: str, *, leader: str,
                 mode: str = "协力对战", expected_players: int = 2,
                 stall_timeout: float = 180.0, clock=None):
        if not account_a or not account_b or account_a == account_b:
            raise ValueError("two distinct account IDs required")
        if leader not in (account_a, account_b):
            raise ValueError("leader must be one of the configured accounts")
        if mode not in COOP_MODE_RANGES:
            raise ValueError("unsupported co-op mode")
        low, high = COOP_MODE_RANGES[mode]
        if expected_players != 2 or not low <= expected_players <= high:
            raise ValueError("this controller manages exactly the two configured accounts")
        if stall_timeout <= 0:
            raise ValueError("stall_timeout must be positive")
        import time
        self.accounts = (account_a, account_b)
        self.leader = leader
        self.guest = account_b if leader == account_a else account_a
        self.mode = mode
        self.expected_players = expected_players
        self.stall_timeout = float(stall_timeout)
        self.clock = clock or time.monotonic
        self.phase = "WAITING"
        self.reason = None
        self._last_signature = None
        self._last_change = self.clock()

    def _decision(self, status, action, account=None, reason=None):
        return FlowDecision(status, self.phase, action, account, reason, False)

    def _pause(self, reason):
        self.phase = "PAUSED"
        self.reason = reason
        return self._decision("paused", "STOP_AND_REVIEW", reason=reason)

    def advance(self, observations):
        if self.phase == "PAUSED":
            return self._decision("paused", "STOP_AND_REVIEW", reason=self.reason)
        if self.phase == "COMPLETED":
            return self._decision("completed", "NO_OP")
        pair, error = _validate_pair(observations, self.accounts)
        if error:
            return self._pause(error)
        a, b = pair
        by_account = {o.account_id: o for o in pair}
        leader = by_account[self.leader]
        guest = by_account[self.guest]

        if any(o.daily_rewards_remaining is not None and o.daily_rewards_remaining <= 0 for o in pair):
            return self._pause("daily_coop_rewards_exhausted")
        if any(o.mode and o.mode != self.mode for o in pair):
            return self._pause("co_op_mode_mismatch")

        signature = tuple(
            (o.account_id, o.screen, o.mode, o.room_id, o.room_owner,
             tuple(sorted(o.room_members)), o.room_capacity, o.listed_room_id,
             o.listed_room_owner, o.match_id, o.result, o.daily_rewards_remaining)
            for o in pair
        )
        now = self.clock()
        if signature != self._last_signature:
            self._last_signature = signature
            self._last_change = now
        elif now - self._last_change > self.stall_timeout:
            return self._pause("co_op_state_stalled")

        screens = (a.screen, b.screen)

        if all(screen in ("COOP_HOME", "ROOM_LIST") for screen in screens):
            self.phase = "ROOM_SETUP"
            return self._decision("ready", "CREATE_ROOM", self.leader)

        if (leader.screen == "ROOM" and leader.room_id and
                leader.room_owner == self.leader and
                set(leader.room_members) == {self.leader}):
            if (guest.screen == "ROOM_LIST" and
                    guest.listed_room_id == leader.room_id and
                    guest.listed_room_owner == self.leader):
                self.phase = "ROOM_SETUP"
                return self._decision("ready", "JOIN_ROOM", self.guest)
            if guest.screen in ("COOP_HOME", "ROOM_LIST"):
                self.phase = "ROOM_SETUP"
                return self._decision("waiting", "OPEN_ROOM_LIST", self.guest)

        if all(screen == "ROOM" for screen in screens):
            if not a.room_id or a.room_id != b.room_id:
                return self._pause("co_op_room_id_mismatch")
            if a.room_owner != self.leader or b.room_owner != self.leader:
                return self._pause("unexpected_room_owner")
            if a.mode != self.mode or b.mode != self.mode:
                return self._pause("room_mode_not_confirmed")
            members_a, members_b = set(a.room_members), set(b.room_members)
            expected = set(self.accounts)
            if members_a != expected or members_b != expected:
                return self._pause("room_members_not_exactly_two_accounts")
            if a.room_capacity is None or b.room_capacity is None:
                return self._pause("room_capacity_unverified")
            low, high = COOP_MODE_RANGES[self.mode]
            if not (low <= a.room_capacity <= high and low <= b.room_capacity <= high):
                return self._pause("room_capacity_outside_mode_range")
            if a.room_capacity != b.room_capacity:
                return self._pause("room_capacity_observations_disagree")
            self.phase = "MATCHING"
            return self._decision("waiting", "WAIT_FOR_MATCH", self.leader)

        if all(screen == "MATCH_SUCCESS" for screen in screens):
            if not a.match_id or a.match_id != b.match_id:
                return self._pause("match_id_mismatch")
            self.phase = "MATCHED"
            return self._decision("waiting", "WAIT_FOR_BATTLE")

        if all(screen == "BATTLE" for screen in screens):
            if not a.match_id or a.match_id != b.match_id:
                return self._pause("battle_match_id_mismatch")
            self.phase = "BATTLE"
            return self._decision("waiting", "WAIT_FOR_BATTLE_RESULT")

        if all(screen == "RESULT" for screen in screens):
            if not a.match_id or a.match_id != b.match_id:
                return self._pause("result_match_id_mismatch")
            if not a.result or a.result != b.result:
                return self._pause("result_observations_disagree")
            self.phase = "COMPLETED"
            return self._decision("completed", "REVIEW_RESULT_AND_REWARDS", reason=a.result)

        # The uploaded recording briefly shows one client in battle while the other
        # remains on the room list. That is not safe evidence of a paired match.
        return self._pause("dual_account_phase_mismatch")


class DungeonFlow:
    """Shared-room or parallel-instance dungeon observer.

    `shared` requires both accounts to prove the same room/instance.
    `parallel` allows independent progress but still emits only advisory actions.
    """
    VALID_SCREENS = {"ROOM_LIST", "ROOM", "LOADING", "MAP", "BATTLE", "REWARD", "COMPLETE"}

    def __init__(self, account_a: str, account_b: str, *, dungeon: str,
                 leader: str, relationship: str = "shared",
                 stall_timeout: float = 300.0, clock=None):
        if account_a == account_b or not account_a or not account_b:
            raise ValueError("two distinct account IDs required")
        if leader not in (account_a, account_b):
            raise ValueError("leader must be one of the configured accounts")
        if dungeon not in DUNGEON_RULES:
            raise ValueError("unknown dungeon; add source-backed catalog entry first")
        if relationship not in ("shared", "parallel"):
            raise ValueError("relationship must be shared or parallel")
        if stall_timeout <= 0:
            raise ValueError("stall_timeout must be positive")
        import time
        self.accounts = (account_a, account_b)
        self.leader = leader
        self.guest = account_b if leader == account_a else account_a
        self.dungeon = dungeon
        self.relationship = relationship
        self.stall_timeout = float(stall_timeout)
        self.clock = clock or time.monotonic
        self.phase = "WAITING"
        self.reason = None
        self._last_signatures = {}
        self._last_change = {}
        self._objective_progress = {}

    def _decision(self, status, action, account=None, reason=None):
        return FlowDecision(status, self.phase, action, account, reason, False)

    def _pause(self, reason):
        self.phase = "PAUSED"
        self.reason = reason
        return self._decision("paused", "STOP_AND_REVIEW", reason=reason)

    def _validate_objectives(self, observation):
        if not observation.objectives:
            return None
        current = {}
        for name, done, total in observation.objectives:
            if not name or total <= 0 or done < 0 or done > total or name in current:
                return "invalid_objective_snapshot"
            current[name] = (done, total)
        previous = self._objective_progress.get(observation.account_id, {})
        for name, (done, total) in current.items():
            if name in previous:
                old_done, old_total = previous[name]
                if total != old_total or done < old_done:
                    return "objective_progress_regressed_or_changed"
        self._objective_progress[observation.account_id] = current
        return None

    def _touch(self, observations):
        now = self.clock()
        for o in observations:
            signature = (o.screen, o.instance_id, o.room_id, o.battle_round,
                         o.result, tuple(o.objectives), o.auto_battle_active)
            old = self._last_signatures.get(o.account_id)
            if signature != old:
                self._last_signatures[o.account_id] = signature
                self._last_change[o.account_id] = now
            elif now - self._last_change[o.account_id] > self.stall_timeout:
                return "dungeon_state_stalled:" + o.account_id
        return None

    def advance(self, observations):
        if self.phase == "PAUSED":
            return self._decision("paused", "STOP_AND_REVIEW", reason=self.reason)
        if self.phase == "COMPLETED":
            return self._decision("completed", "NO_OP")
        pair, error = _validate_pair(observations, self.accounts)
        if error:
            return self._pause(error)
        if any(o.dungeon != self.dungeon for o in pair):
            return self._pause("dungeon_name_mismatch")
        if any(o.screen not in self.VALID_SCREENS for o in pair):
            return self._pause("unknown_dungeon_screen")
        for o in pair:
            error = self._validate_objectives(o)
            if error:
                return self._pause(error)
        stall = self._touch(pair)
        if stall:
            return self._pause(stall)

        if self.relationship == "parallel":
            return self._advance_parallel(pair)
        return self._advance_shared(pair)

    def _advance_shared(self, pair):
        a, b = pair
        by_account = {o.account_id: o for o in pair}
        leader, guest = by_account[self.leader], by_account[self.guest]
        if leader.screen == "ROOM_LIST" and guest.screen == "ROOM_LIST":
            self.phase = "ROOM_SETUP"
            return self._decision("ready", "CREATE_ROOM", self.leader)
        if (leader.screen == "ROOM" and leader.room_id and
                leader.room_owner == self.leader and
                set(leader.room_members) == {self.leader}):
            if (guest.screen == "ROOM_LIST" and
                    guest.listed_room_id == leader.room_id and
                    guest.listed_room_owner == self.leader):
                self.phase = "ROOM_SETUP"
                return self._decision("ready", "JOIN_ROOM", self.guest)
            if guest.screen == "ROOM_LIST":
                return self._decision("waiting", "REFRESH_ROOM_LIST", self.guest)
        if all(o.screen == "ROOM" for o in pair):
            if not a.room_id or a.room_id != b.room_id:
                return self._pause("shared_room_id_mismatch")
            if a.room_owner != self.leader or b.room_owner != self.leader:
                return self._pause("shared_room_owner_mismatch")
            if set(a.room_members) != set(self.accounts) or set(b.room_members) != set(self.accounts):
                return self._pause("shared_room_membership_unverified")
            party_range = DUNGEON_RULES[self.dungeon]["party_range"]
            if party_range and not party_range[0] <= len(a.room_members) <= party_range[1]:
                return self._pause("shared_party_size_outside_official_range")
            self.phase = "ROOM_READY"
            return self._decision("ready", "START_DUNGEON", self.leader)
        if all(o.screen == "LOADING" for o in pair):
            if not a.instance_id or a.instance_id != b.instance_id:
                return self._pause("shared_instance_id_mismatch")
            self.phase = "LOADING"
            return self._decision("waiting", "WAIT_FOR_INSTANCE")
        if all(o.screen == "MAP" for o in pair):
            if not a.instance_id or a.instance_id != b.instance_id:
                return self._pause("shared_map_instance_mismatch")
            self.phase = "MAP"
            return self._decision("waiting", "WAIT_FOR_OBJECTIVE_PROGRESS")
        if all(o.screen == "BATTLE" for o in pair):
            if not a.instance_id or a.instance_id != b.instance_id:
                return self._pause("shared_battle_instance_mismatch")
            if a.battle_round is None or a.battle_round != b.battle_round:
                return self._pause("shared_battle_round_disagrees")
            self.phase = "BATTLE"
            return self._decision("waiting", "WAIT_FOR_BATTLE_RESULT")
        if all(o.screen == "REWARD" for o in pair):
            if not a.instance_id or a.instance_id != b.instance_id:
                return self._pause("shared_reward_instance_mismatch")
            self.phase = "REWARD"
            return self._decision("review", "VERIFY_REWARD_SCREEN")
        if all(o.screen == "COMPLETE" for o in pair):
            if not a.instance_id or a.instance_id != b.instance_id:
                return self._pause("shared_completion_instance_mismatch")
            if a.result != "win" or b.result != "win":
                return self._pause("dungeon_not_confirmed_won")
            self.phase = "COMPLETED"
            return self._decision("completed", "REVIEW_COMPLETION")
        return self._pause("shared_dungeon_phase_mismatch")

    def _advance_parallel(self, pair):
        decisions = []
        for o in pair:
            if o.screen == "ROOM_LIST":
                decisions.append((o.account_id, "CREATE_ROOM"))
            elif o.screen == "ROOM":
                if not o.room_id or o.account_id not in set(o.room_members):
                    return self._pause("parallel_room_membership_unverified:" + o.account_id)
                decisions.append((o.account_id, "WAIT_FOR_ROOM_READY"))
            elif o.screen == "LOADING":
                if not o.instance_id:
                    return self._pause("parallel_instance_id_missing:" + o.account_id)
                decisions.append((o.account_id, "WAIT_FOR_INSTANCE"))
            elif o.screen == "MAP":
                if not o.instance_id:
                    return self._pause("parallel_map_instance_missing:" + o.account_id)
                decisions.append((o.account_id, "WAIT_FOR_OBJECTIVE_PROGRESS"))
            elif o.screen == "BATTLE":
                if not o.instance_id:
                    return self._pause("parallel_battle_instance_missing:" + o.account_id)
                decisions.append((o.account_id, "WAIT_FOR_BATTLE_RESULT" if o.auto_battle_active else "MANUAL_BATTLE_REQUIRED"))
            elif o.screen == "REWARD":
                if not o.instance_id:
                    return self._pause("parallel_reward_instance_missing:" + o.account_id)
                decisions.append((o.account_id, "VERIFY_REWARD_SCREEN"))
            elif o.screen == "COMPLETE":
                if o.result != "win":
                    return self._pause("parallel_dungeon_not_confirmed_won:" + o.account_id)
                decisions.append((o.account_id, "ACCOUNT_COMPLETE"))
        if all(action == "ACCOUNT_COMPLETE" for _, action in decisions):
            self.phase = "COMPLETED"
            return self._decision("completed", "REVIEW_BOTH_COMPLETIONS")
        self.phase = "RUNNING"
        # Existing scheduler has one global foreground lease; expose one action at a time.
        account, action = next(((account, action) for account, action in decisions
                                if action != "ACCOUNT_COMPLETE"), (None, "WAIT"))
        return self._decision("waiting", action, account)


def gameplay_demo():
    """Deterministic offline rehearsal used by the CLI and Windows EXE smoke test."""
    accounts = ("account_A", "account_B")
    coop = CoopFlow(*accounts, leader="account_A", mode="协力对战")
    def cobs(screen, *, room_id=None, members=(), capacity=None, listed=None, match_id=None, result=None):
        return (
            CoopObservation("account_A", 101, "server", screen, stable=True, identity_ok=True, geometry_ok=True, mode="协力对战",
                            room_id=room_id, room_owner="account_A" if room_id else None,
                            room_members=tuple(members), room_capacity=capacity, match_id=match_id, result=result),
            CoopObservation("account_B", 202, "server", screen, stable=True, identity_ok=True, geometry_ok=True, mode="协力对战",
                            room_id=room_id, room_owner="account_A" if room_id else None,
                            room_members=tuple(members), room_capacity=capacity, match_id=match_id, result=result),
        )
    coop_steps = [
        coop.advance(cobs("COOP_HOME")),
        coop.advance((
            CoopObservation("account_A", 101, "server", "ROOM", stable=True, identity_ok=True, geometry_ok=True, mode="协力对战", room_id="R1",
                            room_owner="account_A", room_members=("account_A",), room_capacity=4),
            CoopObservation("account_B", 202, "server", "ROOM_LIST", stable=True, identity_ok=True, geometry_ok=True, mode="协力对战",
                            listed_room_id="R1", listed_room_owner="account_A"),
        )),
        coop.advance(cobs("ROOM", room_id="R1", members=accounts, capacity=4)),
        coop.advance(cobs("MATCH_SUCCESS", match_id="M1")),
        coop.advance(cobs("BATTLE", match_id="M1")),
        coop.advance(cobs("RESULT", match_id="M1", result="win")),
    ]

    dungeon = DungeonFlow(*accounts, dungeon="勇闯火焰山", leader="account_A", relationship="shared")
    def dobs(screen, *, room_id=None, members=(), instance_id=None, battle_round=None, result=None, objectives=()):
        return (
            DungeonObservation("account_A", 101, "server", "勇闯火焰山", screen, stable=True, identity_ok=True, geometry_ok=True,
                               room_id=room_id, room_owner="account_A" if room_id else None,
                               room_members=tuple(members), instance_id=instance_id,
                               battle_round=battle_round, result=result, objectives=tuple(objectives)),
            DungeonObservation("account_B", 202, "server", "勇闯火焰山", screen, stable=True, identity_ok=True, geometry_ok=True,
                               room_id=room_id, room_owner="account_A" if room_id else None,
                               room_members=tuple(members), instance_id=instance_id,
                               battle_round=battle_round, result=result, objectives=tuple(objectives)),
        )
    dungeon_steps = [
        dungeon.advance(dobs("ROOM", room_id="D1", members=accounts)),
        dungeon.advance(dobs("LOADING", instance_id="I1")),
        dungeon.advance(dobs("MAP", instance_id="I1", objectives=(("关卡目标", 1, 3),))),
        dungeon.advance(dobs("BATTLE", instance_id="I1", battle_round=1)),
        dungeon.advance(dobs("REWARD", instance_id="I1")),
        dungeon.advance(dobs("COMPLETE", instance_id="I1", result="win")),
    ]
    return {
        "mode": "gameplay_flow_simulation_only",
        "input_enabled": False,
        "game_state_verified": False,
        "coop": [item.to_dict() for item in coop_steps],
        "dungeon": [item.to_dict() for item in dungeon_steps],
        "note": "Synthetic observations only; no screenshots, clicks, purchases, or live game verification.",
    }
