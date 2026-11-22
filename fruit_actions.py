"""Session-only UI teaching and guarded one-shot replay for the Fruit Troupe."""
import ctypes
import threading
from contextlib import contextmanager
from ctypes import wintypes
from io import BytesIO
from time import monotonic
from PIL import Image, ImageChops, ImageStat
from fruit_screen import classify

POINTS = {'LEADER_READY': (462, 366), 'FRUIT_BATTLE': (399, 338)}
LABELS = {'LEADER_READY': '房主可开始挑战', 'ROOM_WAITING': '等待队员',
          'FRUIT_LOADING': '水果剧团加载中', 'FRUIT_BATTLE': '水果剧团战斗中',
          'FRUIT_DETAILS': '水果剧团详情'}


def patch(frame, state):
    image = Image.open(BytesIO(frame)).convert('RGB').resize((800,448), Image.Resampling.LANCZOS)
    if state == 'LEADER_READY':
        # Retain both member rows to reject a changed party on the next attempt.
        return image.crop((290,150,506,223))
    return image.crop((382,321,416,352))


def distance(a, b):
    return sum(ImageStat.Stat(ImageChops.difference(a,b)).mean) / 3


def click_client(provider, window, rect, point):
    if provider.identity(window.hwnd) != window or provider.client_rect(window.hwnd) != rect:
        raise ValueError('窗口变化')
    x = round(point[0]*rect.width/800)
    y = round(point[1]*rect.height/448)
    user = provider.user32
    user.WindowFromPoint.argtypes = [wintypes.POINT]
    user.WindowFromPoint.restype = wintypes.HWND
    if user.WindowFromPoint(wintypes.POINT(rect.x+x,rect.y+y)) != window.hwnd:
        raise ValueError('目标按钮被遮挡')
    send = user.SendMessageTimeoutW
    send.argtypes = [wintypes.HWND,wintypes.UINT,wintypes.WPARAM,wintypes.LPARAM,
                     wintypes.UINT,wintypes.UINT,ctypes.POINTER(ctypes.c_size_t)]
    send.restype = wintypes.LPARAM
    pos = (y << 16) | x
    result = ctypes.c_size_t()
    for message, flags in ((0x201,1),(0x202,0)):
        if not send(window.hwnd,message,flags,pos,2,250,ctypes.byref(result)):
            raise ValueError('游戏窗口未响应')


def same_party(main, guest):
    # Compare both displayed member names. Allow the few pixels of displacement
    # between the room owner's panel and the guest's panel.
    def normalized(frame):
        return Image.open(BytesIO(frame)).convert('L').resize((800,448), Image.Resampling.LANCZOS)
    a,b = normalized(main),normalized(guest)
    for top in (156,203):
        sample = a.crop((345,top,427,top+10))
        if ImageStat.Stat(sample).stddev[0] < 10:
            return False
        if min(ImageStat.Stat(ImageChops.difference(sample,b.crop((345+x,top+y,427+x,top+y+10)))).mean[0]
               for x in range(-5,4) for y in range(-2,3)) > 16:
            return False
    return True


def changed(state, before, after_state, after):
    if state == 'LEADER_READY':
        return after_state in ('FRUIT_LOADING','OBJECTIVES','FRUIT_BATTLE')
    return after_state == state and distance(before, patch(after,state)) >= 32


@contextmanager
def manual_clicks(provider, teaching):
    """Record only physical left clicks on the explicitly armed client control."""
    armed = [None]
    seen = set()
    done = threading.Event()
    def watch():
        user = provider.user32
        user.WindowFromPoint.argtypes = [wintypes.POINT]
        user.WindowFromPoint.restype = wintypes.HWND
        down = bool(user.GetAsyncKeyState(1) & 0x8000)
        while not done.wait(0.01):
            pressed = bool(user.GetAsyncKeyState(1) & 0x8000)
            if pressed and not down:
                pos = wintypes.POINT()
                if user.GetCursorPos(ctypes.byref(pos)):
                    hwnd = user.WindowFromPoint(pos)
                    for key, target, rect, point in tuple(armed[0] or ()):
                        x = (pos.x-rect.x)*800/rect.width
                        y = (pos.y-rect.y)*448/rect.height
                        if target == hwnd and abs(x-point[0])<15 and abs(y-point[1])<11:
                            seen.add(key)
            down = pressed
    if teaching:
        threading.Thread(target=watch,daemon=True).start()
    try:
        yield armed,seen
    finally:
        done.set()


def session(provider, windows, teaching, rules, stop, report):
    with manual_clicks(provider, teaching) as (armed, seen):
        _observe(provider, windows, teaching, rules, stop, report, armed, seen)


def _observe(provider, windows, teaching, rules, stop, report, armed, seen):
    """Monitor until stopped. Teach first, replay only a separately confirmed rule."""
    for window in windows:
        if provider.bind(window.hwnd) != window:
            raise ValueError('窗口已变化，请重新绑定')
    pending = {}
    previous = {}
    used = set()
    end = monotonic()+900
    while monotonic()<end and not stop.is_set():
        for i, window in enumerate(windows):
            if stop.is_set():
                return
            if any(provider.identity(w.hwnd)!=w for w in windows):
                raise ValueError('双窗绑定已变化')
            rect = provider.client_rect(window.hwnd)
            frame = provider.screenshot(window.hwnd) if rect else None
            if not frame or rect != provider.client_rect(window.hwnd):
                raise ValueError('无法稳定读取窗口')
            state = classify(frame)
            key = (windows, i, state)
            now = monotonic()
            old = previous.get(i)
            previous[i] = (state, rect, frame)
            if old is None or old[0]!=state or old[1]!=rect:
                continue
            if i in pending:
                k, before, deadline = pending[i]
                if now > deadline:
                    raise ValueError('未在规定时间观察到操作结果，请重新核对游戏状态')
                if teaching and k not in seen:
                    continue
                if changed(k[-1],before,state,frame) and changed(k[-1],before,state,old[2]):
                    if k[-1]=='FRUIT_BATTLE' and distance(patch(frame,state),patch(old[2],state))>5:
                        continue
                    if not teaching and k[-1]=='FRUIT_BATTLE' and distance(rules[k][1],patch(frame,state))>6:
                        continue
                    if teaching:
                        after = patch(frame,state) if state=='FRUIT_BATTLE' and k[-1]=='FRUIT_BATTLE' else None
                        rules[k]=(before,after)
                    report(i,'已观察到操作结果',state)
                    del pending[i]
                continue
            if key in used or state not in POINTS or (state=='LEADER_READY' and i!=0):
                continue
            before = patch(frame,state)
            if distance(before,patch(old[2],state))>5:
                continue
            if state=='LEADER_READY':
                guest = windows[1]
                peer = provider.screenshot(guest.hwnd)
                if not peer or not same_party(frame,peer):
                    continue
                fresh = provider.screenshot(window.hwnd)
                if not fresh or classify(fresh)!=state or distance(before,patch(fresh,state))>5:
                    continue
            if teaching:
                # Operator arms teaching before manually starting the challenge or
                # enabling a previously disabled native auto-battle control.
                if state=='FRUIT_BATTLE' and key in rules:
                    continue
                armed[0] = tuple(armed[0] or ()) + ((key,window.hwnd,rect,POINTS[state]),)
                report(i,'已记录操作前画面，请手动开始挑战或开启游戏内自动战斗',state)
            else:
                rule = rules.get(key)
                if rule is None or distance(rule[0],before)>6:
                    continue
                if rule[1] is not None and distance(rule[1],before)<24:
                    continue
                if stop.is_set():
                    return
                click_client(provider,window,rect,POINTS[state])
                report(i,'已向绑定窗口发送一次点击',state)
            pending[i]=(key,before,now+25)
            used.add(key)
        stop.wait(0.15)
