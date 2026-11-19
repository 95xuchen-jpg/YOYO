"""Fail-closed two-frame observation bridge for existing gameplay state machines.

This layer verifies window identity, geometry and capture availability. It deliberately
does not infer game screen, room, match, instance or account from opaque pixels.
No keyboard or mouse actions are provided.
"""
from dataclasses import dataclass
from io import BytesIO
from PIL import Image
from gameplay_flows import CoopObservation, DungeonObservation


@dataclass(frozen=True)
class CaptureEvidence:
    account_id: str
    hwnd: int
    pid: int
    identity_ok: bool
    geometry_ok: bool
    two_frames_present: bool


def _valid_png(frame, rect):
    """Decode PNG fully and require exact physical client-area pixel dimensions."""
    if not isinstance(frame, bytes) or not frame.startswith(bytes((137,80,78,71,13,10,26,10))):
        return False
    if rect is None or rect.width <= 0 or rect.height <= 0:
        return False
    try:
        with Image.open(BytesIO(frame)) as img:
            if img.format != 'PNG' or img.size != (rect.width, rect.height):
                return False
            img.load()  # Reject truncated or malformed image payloads.
        return True
    except (OSError, ValueError, SyntaxError):
        return False


def capture_pair(provider, bindings):
    """Capture bound (account, hwnd, pid) pairs; reject any identity/geometry drift.

    A provider must implement identity(hwnd), client_rect(hwnd), screenshot(hwnd).
    Window coordinates are deliberately never converted into click coordinates.
    """
    if len(bindings) != 2 or len({b[0] for b in bindings}) != 2 or len({b[1] for b in bindings}) != 2 or len({b[2] for b in bindings}) != 2:
        raise ValueError("two distinct account, HWND and PID bindings required")
    evidence = []
    snapshots = []
    for account, hwnd, pid in bindings:
        valid_identity = valid_geometry = frames = False
        try:
            before_id = provider.identity(hwnd)
            before = provider.client_rect(hwnd)
            first = provider.screenshot(hwnd) if before is not None else None
            middle_id = provider.identity(hwnd)
            middle = provider.client_rect(hwnd)
            second = provider.screenshot(hwnd) if _valid_png(first, before) and middle == before else None
            after_id = provider.identity(hwnd)
            after = provider.client_rect(hwnd)
            valid_identity = all(x is not None and x.hwnd == hwnd and x.pid == pid and x == before_id for x in (before_id, middle_id, after_id))
            valid_geometry = before is not None and before == middle == after and before.width > 0 and before.height > 0
            frames = _valid_png(first, before) and _valid_png(second, after)
            snapshots.append((before_id, before))
        except Exception:
            snapshots.append((None, None))
        evidence.append(CaptureEvidence(account, hwnd, pid, valid_identity, valid_geometry, frames))
    # Recheck both windows after both capture sequences to catch cross-window drift.
    final = []
    for item, (identity, rect) in zip(evidence, snapshots):
        try:
            still_valid = identity is not None and provider.identity(item.hwnd) == identity
            still_valid = still_valid and rect is not None and provider.client_rect(item.hwnd) == rect
        except Exception:
            still_valid = False
        final.append(CaptureEvidence(item.account_id, item.hwnd, item.pid,
                                     item.identity_ok and still_valid,
                                     item.geometry_ok and still_valid,
                                     item.two_frames_present))
    return tuple(final)


def safe_coop_observations(evidence, server_id=""):
    """Unknown screen/account-to-game identity always remains unverified."""
    return tuple(CoopObservation(account_id=e.account_id, window_id=e.hwnd,
                                 server_id=server_id, screen="UNKNOWN",
                                 stable=False, identity_ok=False,
                                 geometry_ok=e.geometry_ok) for e in evidence)


def safe_dungeon_observations(evidence, dungeon, server_id=""):
    return tuple(DungeonObservation(account_id=e.account_id, window_id=e.hwnd,
                                    server_id=server_id, dungeon=dungeon,
                                    screen="UNKNOWN", stable=False,
                                    identity_ok=False,
                                    geometry_ok=e.geometry_ok) for e in evidence)
