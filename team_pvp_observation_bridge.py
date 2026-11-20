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
    # Require explicit, non-interchangeable capture identities before consulting
    # the phase tracker. This is only structural validation, NOT proof of the
    # on-screen account or game phase.
    try:
        accounts = [record.get("account_id") for record in windows]
        handles = [record.get("hwnd") for record in windows]
        pids = [record.get("pid") for record in windows]
        if (any(not isinstance(record, dict) for record in windows)
                or accounts != ["main", "alt"]
                or any(type(h) is not int or h <= 0 for h in handles)
                or len(set(handles)) != 2
                or any(type(p) is not int or p <= 0 for p in pids)
                or len(set(pids)) != 2):
            raise ValueError("invalid capture identity")
    except (AttributeError, TypeError, ValueError):
        return {"status": "paused", "reason": "capture_identity_mismatch",
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
