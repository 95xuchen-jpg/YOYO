"""Fail-closed, advisory-only Fruit Troupe dual-account evidence gate.

Repeated verified frames are expected during real video capture. They must not
cause false stops, but missing verification, disagreement, or skipped phases do.
No game input is sent by this module.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class FruitEvidence:
    main_state: str
    alt_state: str
    main_stable: bool
    alt_stable: bool
    same_room_verified: bool = False
    same_instance_verified: bool = False
    main_reward_specific: bool = False
    alt_reward_specific: bool = False


class FruitSequenceGate:
    def __init__(self):
        self.phase = "ROOM"
        self.stopped = False
        self.reason = None

    def advance(self, evidence: FruitEvidence):
        if self.stopped:
            return self._result("paused", "STOP_AND_REVIEW")
        if not evidence.main_stable or not evidence.alt_stable:
            return self._pause("unstable_dual_capture")
        states = (evidence.main_state, evidence.alt_state)
        if any(s in ("UNKNOWN", "ERROR", "") for s in states):
            return self._pause("unknown_screen")
        if states[0] != states[1]:
            return self._pause("dual_account_state_mismatch")

        state = states[0]
        if self.phase == "ROOM":
            if state == "ROOM_WAITING" and evidence.same_room_verified:
                self.phase = "READY"
                return self._result("waiting", "REVIEW_START")
            return self._pause("same_room_not_confirmed")
        if self.phase == "READY":
            if state == "ROOM_WAITING" and evidence.same_room_verified:
                return self._result("waiting", "REVIEW_START")
            if state == "FRUIT_LOADING" and evidence.same_instance_verified:
                self.phase = "LOADING"
                return self._result("waiting", "WAIT_FOR_BATTLE")
            return self._pause("entry_not_confirmed")
        if self.phase == "LOADING":
            if state == "FRUIT_LOADING" and evidence.same_instance_verified:
                return self._result("waiting", "WAIT_FOR_BATTLE")
            if state == "FRUIT_BATTLE" and evidence.same_instance_verified:
                self.phase = "BATTLE"
                return self._result("waiting", "OBSERVE_BATTLE")
            return self._pause("battle_not_confirmed")
        if self.phase == "BATTLE":
            if state == "FRUIT_BATTLE" and evidence.same_instance_verified:
                return self._result("waiting", "OBSERVE_BATTLE")
            if (state == "REWARD" and evidence.same_instance_verified
                    and evidence.main_reward_specific and evidence.alt_reward_specific):
                self.phase = "REWARD"
                return self._result("waiting", "REVIEW_REWARDS")
            return self._pause("dungeon_specific_reward_not_confirmed")
        if self.phase == "REWARD":
            if (state == "REWARD" and evidence.same_instance_verified
                    and evidence.main_reward_specific and evidence.alt_reward_specific):
                return self._result("waiting", "REVIEW_REWARDS")
            if state == "COMPLETE" and evidence.same_instance_verified:
                self.phase = "COMPLETE"
                return self._result("completed", "NO_OP")
            return self._pause("completion_not_confirmed")
        if state == "COMPLETE" and evidence.same_instance_verified:
            return self._result("completed", "NO_OP")
        return self._pause("completion_regressed")

    def _result(self, status, action):
        return {"status": status, "phase": self.phase, "action": action,
                "reason": self.reason, "input_enabled": False}

    def _pause(self, reason):
        self.reason = reason
        self.stopped = True
        self.phase = "PAUSED"
        return self._result("paused", "STOP_AND_REVIEW")
