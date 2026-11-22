"""Fill the fixed local room code only after a taught private-room transition."""
import ctypes
from ctypes import wintypes
from pathlib import Path
import re
import sys
from room_route import normalized
from fruit_screen import classify

FIELDS = {'PRIVATE_CREATE': (444,244), 'PRIVATE_JOIN': (441,248)}


def configured_code():
    root = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).parent
    path = root / 'room-code.txt'
    if not path.is_file():
        return None
    code = path.read_text(encoding='ascii').strip()
    if not re.fullmatch('[0-9]{4}', code):
        raise ValueError('房间密码配置应为四位数字')
    return code


def field_empty(frame,state):
    # Placeholder text spans both sides of the center; four digits occupy the center only.
    x,y = FIELDS[state]
    grey = normalized(frame).convert('L')
    for left,right in ((x-40,x-21),(x+21,x+40)):
        band = grey.crop((left,y-5,right,y+6))
        if max(band.getdata())-min(band.getdata()) < 19:
            return False
    return True


def fill_room(provider, window, rect, state, code, stop, click):
    if state not in FIELDS or stop.is_set():
        return False
    frame = provider.screenshot(window.hwnd)
    if not frame or classify(frame)!=state or not field_empty(frame,state) or stop.is_set():
        return False
    click(provider,window,rect,FIELDS[state])
    user = provider.user32
    user.GetForegroundWindow.restype = wintypes.HWND
    user.GetGUIThreadInfo.argtypes = [wintypes.DWORD,ctypes.c_void_p]
    user.IsChild.argtypes = [wintypes.HWND,wintypes.HWND]
    class GuiInfo(ctypes.Structure):
        _fields_ = [('size',wintypes.DWORD),('flags',wintypes.DWORD)] + [
            (name,wintypes.HWND) for name in ('active','focus','capture','menu','move','caret')
        ] + [('caret_rect',wintypes.RECT)]
    send = user.SendMessageTimeoutW
    send.argtypes = [wintypes.HWND,wintypes.UINT,wintypes.WPARAM,wintypes.LPARAM,
                     wintypes.UINT,wintypes.UINT,ctypes.POINTER(ctypes.c_size_t)]
    send.restype = wintypes.LPARAM
    info = GuiInfo()
    info.size = ctypes.sizeof(info)
    target = None
    for digit in code:
        if (stop.is_set() or provider.identity(window.hwnd)!=window or provider.client_rect(window.hwnd)!=rect
                or user.GetForegroundWindow()!=window.hwnd or not user.GetGUIThreadInfo(0,ctypes.byref(info))
                or not info.focus or not (info.focus==window.hwnd or user.IsChild(window.hwnd,info.focus))
                or (target is not None and info.focus!=target)):
            raise ValueError('输入焦点变化，请核对游戏中的房间密码')
        target = info.focus
        result = ctypes.c_size_t()
        if not send(target,0x0102,ord(digit),1,2,250,ctypes.byref(result)):
            raise ValueError('游戏未响应，请手动核对房间密码')
    return True
