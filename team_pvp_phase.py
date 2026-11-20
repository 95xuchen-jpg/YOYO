"""Fail-closed two-account team-PVP phase reconciler.

This module consumes observations from a future independently validated image
detector. It does NOT infer anything from opaque screenshots and never sends input.
"""
from dataclasses import dataclass
from enum import Enum


class Phase(str, Enum):
    UNKNOWN = "unknown"
    LOBBY = "lobby"
    TEAM = "team"
    QUEUED = "queued"
    MATCHED = "matched"
    BATTLE = "battle"
    RESULT = "result"


@dataclass(frozen=True)
class PvpObservation:
    account: str
    phase: Phase
    identity_verified: bool = False
    two_frames_agree: bool = False
    geometry_ok: bool = False
    session_id: str = ""
    evidence_id: str = ""


@dataclass(frozen=True)
class Decision:
    status: str
    reason: str
    phase: Phase = Phase.UNKNOWN
    input_enabled: bool = False


_ALLOWED = {
    Phase.LOBBY: {Phase.LOBBY, Phase.TEAM},
    Phase.TEAM: {Phase.TEAM, Phase.QUEUED, Phase.LOBBY},
    Phase.QUEUED: {Phase.QUEUED, Phase.MATCHED, Phase.TEAM},
    Phase.MATCHED: {Phase.MATCHED, Phase.BATTLE, Phase.QUEUED},
    Phase.BATTLE: {Phase.BATTLE, Phase.RESULT},
    Phase.RESULT: {Phase.RESULT, Phase.LOBBY},
}


class TeamPvpTracker:
    def __init__(self):
        self.phase = Phase.UNKNOWN
        self.session_id = ""

    def advance(self, observations):
        obs = tuple(observations)
        if len(obs) != 2 or {o.account for o in obs} != {"main", "alt"}:
            return Decision("paused", "exactly_two_explicit_accounts_required")
        if any(not isinstance(o.phase, Phase) or o.phase is Phase.UNKNOWN for o in obs):
            return Decision("paused", "unverified_phase")
        if any(not (o.identity_verified and o.two_frames_agree and o.geometry_ok
                    and o.evidence_id) for o in obs):
            return Decision("paused", "insufficient_image_evidence")
        if len({o.evidence_id for o in obs}) != 2:
            return Decision("paused", "duplicate_image_evidence")
        if any(not o.session_id for o in obs) or len({o.session_id for o in obs}) != 1:
            return Decision("paused", "session_not_correlated")
        phase = obs[0].phase
        if obs[1].phase != phase:
            return Decision("paused", "cross_account_phase_conflict")
        session_id = obs[0].session_id
        if self.session_id and self.session_id != session_id:
            return Decision("paused", "session_changed")
        if self.phase is Phase.UNKNOWN:
            if phase is not Phase.LOBBY:
                return Decision("paused", "initial_lobby_not_verified")
        elif phase not in _ALLOWED[self.phase]:
            return Decision("paused", "invalid_phase_transition")
        self.phase = phase
        self.session_id = session_id
        return Decision("observed", "read_only_phase_consensus", phase)
