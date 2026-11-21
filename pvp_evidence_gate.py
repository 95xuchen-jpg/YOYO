"""Conservative offline-only dual-account team-PVP evidence gate.

This module does not capture screenshots, recognize game screens or send inputs.
Only explicitly reviewed phase observations may pass. Even then, input stays off.
"""
from dataclasses import dataclass
from enum import Enum

class Phase(str, Enum):
    UNKNOWN = "UNKNOWN"
    LOBBY = "LOBBY"
    TEAM = "TEAM"
    QUEUE = "QUEUE"
    MATCH = "MATCH"
    BATTLE = "BATTLE"
    RESULT = "RESULT"

@dataclass(frozen=True)
class Evidence:
    account: str
    hwnd: int
    pid: int
    phase: Phase
    frame_hashes: tuple[str, str]
    session_id: str
    reviewed: bool = False

def inspect_pair(records):
    paused = {"status": "paused", "phase": "UNKNOWN",
              "input_enabled": False, "game_state_verified": False}
    if not isinstance(records, (tuple, list)) or len(records) != 2:
        return {**paused, "reason": "two_accounts_required"}
    if not all(isinstance(x, Evidence) for x in records):
        return {**paused, "reason": "malformed_evidence"}
    a, b = records
    if ((a.account, b.account) != ("main", "alt")
        or any(type(x.hwnd) is not int or x.hwnd <= 0 or type(x.pid) is not int or x.pid <= 0 for x in records)
        or a.hwnd == b.hwnd or a.pid == b.pid):
        return {**paused, "reason": "identity_mismatch"}
    for x in records:
        hashes = x.frame_hashes
        if (not isinstance(x.phase, Phase) or x.phase is Phase.UNKNOWN
            or not x.reviewed or not isinstance(x.session_id, str) or not x.session_id.strip()
            or not isinstance(hashes, tuple) or len(hashes) != 2
            or any(not isinstance(h, str) or len(h) != 64 or any(c not in "0123456789abcdef" for c in h) for h in hashes)
            or hashes[0] == hashes[1]):
            return {**paused, "reason": "unverified_visual_evidence"}
    if a.session_id != b.session_id or a.phase != b.phase:
        return {**paused, "reason": "phase_or_session_conflict"}
    return {"status": "observed", "phase": a.phase.value,
            "reason": "reviewed_offline_evidence_only",
            "input_enabled": False, "game_state_verified": True}
