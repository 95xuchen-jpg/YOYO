"""Read-only two-account observation bridge. No input actions or game-state assumptions."""
from dataclasses import dataclass
from core import Window
from adapters import WindowGuard

@dataclass(frozen=True)
class PreflightResult:
    account: str
    handle: int
    status: str
    reason: str


def inspect_two_windows(provider, detector, bindings, expected_state):
    """Fail closed on identity, duplicate handles, changed geometry, or uncertain vision.

    bindings: exactly two Window objects with distinct account/handle. The caller
    must bind/verify the provider's OS identity before invoking this function.
    """
    if len(bindings) != 2:
        raise ValueError('exactly two account windows required')
    if len({w.account for w in bindings}) != 2 or len({w.handle for w in bindings}) != 2:
        raise ValueError('duplicate account or window handle')
    guard = WindowGuard(provider, detector)
    results = []
    for window in bindings:
        observation = guard.observe(window, expected_state)
        results.append(PreflightResult(window.account, window.handle,
                       'observed' if observation else 'paused',
                       'two_frames_confirmed' if observation else 'stale_window_or_unverified_state'))
    return results


def windows_readonly_preflight(title_filter, expected_state, detector):
    """Windows-only opt-in preflight. Never sends keyboard or mouse input.

    No built-in game detector is supplied: the caller must provide a separately
    validated detector; arbitrary screenshot bytes are NOT evidence of a state.
    """
    from windows_provider import WindowsClientProvider
    provider = WindowsClientProvider()
    candidates = provider.discover(title_filter)
    if len(candidates) != 2:
        return {'status': 'paused', 'reason': 'expected_exactly_two_matching_windows', 'found': len(candidates)}
    bindings = []
    for index, identity in enumerate(candidates):
        provider.bind(identity.hwnd)
        bounds = provider.client_rect(identity.hwnd)
        if bounds is None:
            return {'status': 'paused', 'reason': 'invalid_window_bounds'}
        # Geometry only; no reference coordinate mapping until viewport is calibrated.
        bindings.append(Window(f'account_{index+1}', identity.hwnd, bounds, bounds.width, bounds.height))
    observations = inspect_two_windows(provider, detector, bindings, expected_state)
    return {'status': 'observed' if all(x.status == 'observed' for x in observations) else 'paused',
            'results': [x.__dict__ for x in observations], 'mode': 'read_only_no_game_input'}
