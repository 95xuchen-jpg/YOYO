"""Fail-closed Windows window/screenshot integration boundary; no input injection."""
from dataclasses import dataclass
from typing import Protocol
from core import Window, Rect

class WindowProvider(Protocol):
    def client_rect(self, handle: int) -> Rect | None: ...
    def screenshot(self, handle: int) -> bytes | None: ...

class StateDetector(Protocol):
    def detect(self, screenshot: bytes) -> str | None: ...

@dataclass(frozen=True)
class Observation:
    account: str
    handle: int
    state: str
    bounds: Rect

class WindowGuard:
    """Check current client bounds, then require two independent agreeing frames."""
    def __init__(self, provider: WindowProvider, detector: StateDetector):
        self.provider = provider
        self.detector = detector

    def observe(self, window: Window, expected_state: str) -> Observation | None:
        if not expected_state:
            raise ValueError('expected_state required')
        try:
            return self._observe_checked(window, expected_state)
        except (Exception,):
            return None

    def _observe_checked(self, window: Window, expected_state: str) -> Observation | None:
        first_bounds = self.provider.client_rect(window.handle)
        if first_bounds is None or first_bounds != window.client:
            return None  # stale handle, resized/moved window, or vanished client
        first = self.provider.screenshot(window.handle)
        if not first or self.detector.detect(first) != expected_state:
            return None
        second_bounds = self.provider.client_rect(window.handle)
        if second_bounds != first_bounds:
            return None
        second = self.provider.screenshot(window.handle)
        if not second or self.detector.detect(second) != expected_state:
            return None
        final_bounds = self.provider.client_rect(window.handle)
        if final_bounds != first_bounds:
            return None
        return Observation(window.account, window.handle, expected_state, final_bounds)

    def safe_point(self, window: Window, expected_state: str, x: float, y: float,
                   content: Rect | None = None) -> tuple[int,int] | None:
        observation = self.observe(window, expected_state)
        if observation is None:
            return None
        return window.map_point(x, y, content)
