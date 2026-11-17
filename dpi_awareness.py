"""Set DPI awareness before querying Win32 window geometry."""
import ctypes
import os

def enable_per_monitor_dpi(*, platform=None, user32=None, shcore=None):
    platform = os.name if platform is None else platform
    if platform != 'nt':
        return 'not_windows'
    try:
        user32 = user32 or ctypes.WinDLL('user32', use_last_error=True)
        if user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)):
            return 'per_monitor_v2'
    except (AttributeError, OSError, ValueError):
        pass
    try:
        shcore = shcore or ctypes.WinDLL('shcore', use_last_error=True)
        if shcore.SetProcessDpiAwareness(2) == 0:
            return 'per_monitor_v1'
    except (AttributeError, OSError, ValueError):
        pass
    try:
        if user32.SetProcessDPIAware():
            return 'system_dpi'
    except (AttributeError, OSError, ValueError, UnboundLocalError):
        pass
    return 'unavailable'
