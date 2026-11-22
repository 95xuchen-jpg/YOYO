"""Fail-closed, advisory-only Fruit Troupe dual-account evidence gate.

The two clients may show different local phases while progressing through the same
shared instance (for example, one client is on the objective map while the other is
in battle). This gate tracks each account independently and advances only when both
accounts have reached the relevant milestone. It never sends game input.
"""
from dataclasses import dataclass


VALID_STATES = frozenset({
    "ROOM_WAITING",
    "FRUIT_LOADING",
    "OBJECTIVES",
    "FRUIT_BATTLE",
    "REWARD",
    "REWARD_PANEL",
    "COMPLETE",
})
ACTIVE_STATES = frozenset({"OBJECTIVES", "FRUIT_BATTLE"})
REWARD_STATES = frozenset({"REWARD", "REWARD_PANEL"})


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
    """Advisory state gate for two explicitly bound accounts in one Fruit instance."""

    def __init__(self):
        self.phase = "ROOM"
        self.stopped = False
        self.reason = None
        self._progress = {"main": 0, "alt": 0}
        self._reward_verified = {"main": False, "alt": False}

    def advance(self, evidence: FruitEvidence):
        if self.stopped:
            return self._result("paused", "STOP_AND_REVIEW")

        boolean_fields = (
            evidence.main_stable,
            evidence.alt_stable,
            evidence.same_room_verified,
            evidence.same_instance_verified,
            evidence.main_reward_specific,
            evidence.alt_reward_specific,
        )
        if any(type(value) is not bool for value in boolean_fields):
            return self._pause("invalid_evidence")
        states = (evidence.main_state, evidence.alt_state)
        if any(not isinstance(state, str) or state not in VALID_STATES for state in states):
            return self._pause("unknown_screen")
        if not evidence.main_stable or not evidence.alt_stable:
            return self._pause("unstable_dual_capture")

        if self.phase == "ROOM":
            if states == ("ROOM_WAITING", "ROOM_WAITING") and evidence.same_room_verified:
                self.phase = "READY"
                return self._result("waiting", "REVIEW_START")
            return self._pause("same_room_not_confirmed")

        if states == ("ROOM_WAITING", "ROOM_WAITING") and evidence.same_room_verified:
            if self._progress == {"main": 0, "alt": 0}:
                return self._result("waiting", "REVIEW_START")
        elif states == ("ROOM_WAITING", "ROOM_WAITING") and not evidence.same_room_verified:
            return self._pause("same_room_not_confirmed")

        if not evidence.same_instance_verified:
            return self._pause("shared_instance_not_confirmed")

        account_evidence = (
            ("main", evidence.main_state, evidence.main_reward_specific),
            ("alt", evidence.alt_state, evidence.alt_reward_specific),
        )
        generic_reward_accounts = []
        current_states = {}
        for account, state, reward_specific in account_evidence:
            current_states[account] = state
            previous = self._progress[account]
            if reward_specific and state not in REWARD_STATES:
                return self._pause("reward_evidence_state_mismatch")

            if state == "ROOM_WAITING":
                rank = 0
            elif state == "FRUIT_LOADING":
                rank = 1
            elif state in ACTIVE_STATES:
                rank = 2
            elif state in REWARD_STATES:
                if previous < 2:
                    return self._pause("reward_before_battle")
                if reward_specific:
                    self._reward_verified[account] = True
                elif not self._reward_verified[account]:
                    generic_reward_accounts.append(account)
                rank = 3 if self._reward_verified[account] else 2
            else:  # COMPLETE
                if not self._reward_verified[account]:
                    return self._pause("completion_without_reward_evidence")
                rank = 4

            if rank < previous:
                return self._pause("account_phase_regressed")
            self._progress[account] = rank

        lowest = min(self._progress.values())
        highest = max(self._progress.values())
        if lowest == 0:
            self.phase = "READY"
            return self._result(
                "waiting", "WAIT_FOR_OTHER_ACCOUNT",
                "awaiting_both_accounts_in_instance",
            )
        if lowest == 1:
            self.phase = "LOADING"
            action = "WAIT_FOR_OTHER_ACCOUNT" if highest > 1 else "WAIT_FOR_BATTLE"
            return self._result("waiting", action, "awaiting_both_accounts_loading")

        if lowest == 2:
            self.phase = "BATTLE"
            if generic_reward_accounts:
                return self._result(
                    "waiting", "WAIT_FOR_DUNGEON_SPECIFIC_REWARD",
                    "dungeon_specific_reward_not_confirmed",
                )
            if highest > 2:
                return self._result(
                    "waiting", "WAIT_FOR_OTHER_ACCOUNT_REWARD",
                    "awaiting_other_account_reward",
                )
            action = (
                "OBSERVE_BATTLE"
                if "FRUIT_BATTLE" in current_states.values()
                else "OBSERVE_OBJECTIVES"
            )
            return self._result("waiting", action)

        if lowest == 3:
            self.phase = "REWARD"
            return self._result("waiting", "REVIEW_REWARDS")
        if lowest == 4:
            self.phase = "COMPLETE"
            return self._result("completed", "NO_OP")
        return self._pause("invalid_progress_state")

    def _result(self, status, action, reason=None):
        return {
            "status": status,
            "phase": self.phase,
            "action": action,
            "reason": self.reason if reason is None else reason,
            "input_enabled": False,
        }

    def _pause(self, reason):
        self.reason = reason
        self.stopped = True
        self.phase = "PAUSED"
        return self._result("paused", "STOP_AND_REVIEW")
