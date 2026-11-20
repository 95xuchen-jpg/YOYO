"""Fail-closed bridge from real dual-window readiness to team-PVP phase tracking.

Screenshots alone are NOT proof of a lobby, queue, match or battle. This
bridge deliberately produces UNKNOWN observations until a separately
validated, account-aware visual detector is available.
"""
from team_pvp_phase import Phase, PvpObservation, TeamPvpTracker


def inspect_pvp_phase(readiness):
    """Return a safe decision without inventing a shared match/session ID."""
    if not isinstance(readiness, dict) or readiness.get("status") != "capture_ready":
        return {"status": "paused", "reason": "capture_preflight_not_ready",
                "phase": Phase.UNKNOWN.value, "input_enabled": False,
                "game_state_verified": False}
    windows = readiness.get("windows")
    if not isinstance(windows, list) or len(windows) != 2:
        return {"status": "paused", "reason": "two_capture_records_required",
                "phase": Phase.UNKNOWN.value, "input_enabled": False,
                "game_state_verified": False}
    # Identity/geometry evidence is still not a trustworthy game-phase label.
    # Never synthesize a session ID, evidence ID, or phase from window handles.
    observations = (
        PvpObservation(account="main", phase=Phase.UNKNOWN),
        PvpObservation(account="alt", phase=Phase.UNKNOWN),
    )
    decision = TeamPvpTracker().advance(observations)
    return {"status": decision.status, "reason": decision.reason,
            "phase": decision.phase.value, "input_enabled": decision.input_enabled,
            "game_state_verified": False}
