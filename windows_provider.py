"""Read-only Windows client discovery/capture adapter. No keyboard/mouse injection.

Uses Win32 client-area geometry and Pillow ImageGrab. Not executable on Linux.
"""
from __future__ import annotations
import ctypes
import os
from dataclasses import dataclass
from typing import Callable
from core import Rect
from capture_watchdog import CaptureWatchdog

@dataclass(frozen=True)
class WindowIdentity:
    hwnd: int
    pid: int
    title: str
    class_name: str

class WindowsClientProvider:
    def __init__(self, capture: Callable | None = None, watchdog: CaptureWatchdog | None = None):
        if os.name != 'nt':
            raise RuntimeError('Windows 10/11 required')
        from ctypes import wintypes
        self.wintypes = wintypes
        self.user32 = ctypes.WinDLL('user32', use_last_error=True)
        self.user32.IsWindow.argtypes = [wintypes.HWND]
        self.user32.IsWindow.restype = wintypes.BOOL
        self.user32.IsWindowVisible.argtypes = [wintypes.HWND]
        self.user32.IsWindowVisible.restype = wintypes.BOOL
        self.user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        self.user32.GetWindowThreadProcessId.restype = wintypes.DWORD
        self.user32.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
        self.user32.GetClientRect.restype = wintypes.BOOL
        self.user32.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
        self.user32.ClientToScreen.restype = wintypes.BOOL
        self.user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
        self.user32.GetWindowTextLengthW.restype = ctypes.c_int
        self.user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
        self.user32.GetWindowTextW.restype = ctypes.c_int
        self.user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
        self.user32.GetClassNameW.restype = ctypes.c_int
        self._callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        self.user32.EnumWindows.argtypes = [self._callback_type, wintypes.LPARAM]
        self.user32.EnumWindows.restype = wintypes.BOOL
        self._capture = capture
        self._watchdog = watchdog or CaptureWatchdog()
        self._identity: dict[int, WindowIdentity] = {}

    def identity(self, hwnd: int) -> WindowIdentity | None:
        if not self.user32.IsWindow(hwnd) or not self.user32.IsWindowVisible(hwnd):
            return None
        pid = self.wintypes.DWORD()
        self.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if not pid.value:
            return None
        length = self.user32.GetWindowTextLengthW(hwnd)
        title = ctypes.create_unicode_buffer(length + 1)
        self.user32.GetWindowTextW(hwnd, title, len(title))
        klass = ctypes.create_unicode_buffer(256)
        self.user32.GetClassNameW(hwnd, klass, len(klass))
        return WindowIdentity(hwnd, pid.value, title.value, klass.value)

    def discover(self, title_contains: str) -> list[WindowIdentity]:
        if not title_contains:
            raise ValueError('explicit title filter required')
        results = []
        callback_type = self._callback_type
        def callback(hwnd, unused):
            ident = self.identity(hwnd)
            if ident and title_contains.casefold() in ident.title.casefold():
                results.append(ident)
            return True
        cb = callback_type(callback)
        self.user32.EnumWindows(cb, 0)
        return results

    def bind(self, hwnd: int) -> WindowIdentity:
        ident = self.identity(hwnd)
        if ident is None:
            raise ValueError('window unavailable')
        self._identity[hwnd] = ident
        return ident

    def client_rect(self, hwnd: int) -> Rect | None:
        if hwnd not in self._identity or self.identity(hwnd) != self._identity[hwnd]:
            return None
        rect = self.wintypes.RECT()
        origin = self.wintypes.POINT(0, 0)
        if not self.user32.GetClientRect(hwnd, ctypes.byref(rect)):
            return None
        if not self.user32.ClientToScreen(hwnd, ctypes.byref(origin)):
            return None
        width, height = rect.right - rect.left, rect.bottom - rect.top
        if width <= 0 or height <= 0:
            return None
        return Rect(origin.x, origin.y, width, height)

    def screenshot(self, hwnd: int) -> bytes | None:
        bounds = self.client_rect(hwnd)
        if bounds is None:
            return None
        try:
            if self._capture is None:
                return self._watchdog.capture(bounds)
            return self._capture(bounds)
        except Exception:
            return None
