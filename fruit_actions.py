"""Session-only UI teaching and guarded one-shot replay for the Fruit Troupe."""
import ctypes
import threading
from contextlib import contextmanager
from ctypes import wintypes
from io import BytesIO
from time import monotonic
from PIL import Image, ImageChops, ImageStat
from fruit_screen import classify
from room_route import ROUTE, normalized, join_target, ink_agreement

POINTS = {'LEADER_READY': (462, 366), 'FRUIT_BATTLE': (399, 338)}
LABELS = {'LEADER_READY': '房主可开始挑战', 'ROOM_WAITING': '等待队员',
          'FRUIT_LOADING': '水果剧团加载中', 'FRUIT_BATTLE': '水果剧团战斗中',
          'FRUIT_DETAILS': '水果剧团详情', 'DAILY':'日常任务', 'CATALOG':'副本目录',
          'CREATE_OPTIONS':'创建房间设置', 'PRIVATE_CREATE':'私人房间设置',
          'ROOM_LIST':'房间列表', 'PRIVATE_JOIN':'私人房间入房提示'}


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
    target = wintypes.POINT(rect.x+x,rect.y+y)
    if not user.SetCursorPos(target.x,target.y):
        raise ValueError('无法定位鼠标')
    cursor = wintypes.POINT()
    if (not user.GetCursorPos(ctypes.byref(cursor)) or (cursor.x,cursor.y)!=(target.x,target.y)
            or user.WindowFromPoint(cursor)!=window.hwnd or provider.identity(window.hwnd)!=window
            or provider.client_rect(window.hwnd)!=rect):
        raise ValueError('目标窗口或鼠标已移动')
    class MouseInput(ctypes.Structure):
        _fields_ = [('dx',wintypes.LONG),('dy',wintypes.LONG),('data',wintypes.DWORD),
                    ('flags',wintypes.DWORD),('time',wintypes.DWORD),('extra',ctypes.c_size_t)]
    class Input(ctypes.Structure):
        _fields_ = [('type',wintypes.DWORD),('mouse',MouseInput)]
    events=(Input*2)()
    events[0].mouse.flags=0x0002
    events[1].mouse.flags=0x0004
    user.SendInput.argtypes=[wintypes.UINT,ctypes.POINTER(Input),ctypes.c_int]
    if user.SendInput(2,events,ctypes.sizeof(Input))!=2:
        raise ValueError('系统未接受点击')


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
    from room_pin import configured_code, fill_room, field_empty
    room_code = None if teaching else configured_code()
    opened_fruit_settings = False
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
            if i in pending and now > pending[i][2]:
                raise ValueError('操作等待超时，请核对游戏画面')
            if old is None or old[0]!=state or old[1]!=rect:
                continue
            if i in pending:
                k, before, deadline = pending[i]
                if now > deadline:
                    raise ValueError('未在规定时间观察到操作结果，请重新核对游戏状态')
                if teaching and k not in seen:
                    continue
                route = ROUTE.get((i,k[-1]))
                expected = route[1] if route else 'PRIVATE_JOIN' if k[-1]=='ROOM_LIST' else None
                success = (state == expected if expected else
                           changed(k[-1],before,state,frame) and changed(k[-1],before,state,old[2]))
                if success:
                    if k[-1]=='FRUIT_BATTLE' and distance(patch(frame,state),patch(old[2],state))>5:
                        continue
                    if not teaching and k[-1]=='FRUIT_BATTLE' and distance(rules[k][1],patch(frame,state))>6:
                        continue
                    if k[-1]=='FRUIT_DETAILS' and state=='CREATE_OPTIONS':
                        opened_fruit_settings = True
                    if teaching:
                        after = patch(frame,state) if state=='FRUIT_BATTLE' and k[-1]=='FRUIT_BATTLE' else None
                        rules[k]=(before,after)
                    report(i,'已观察到操作结果',state)
                    if state in ('PRIVATE_CREATE','PRIVATE_JOIN'):
                        sent = (room_code is not None and field_empty(old[2],state) and field_empty(frame,state)
                                and fill_room(provider,window,rect,state,room_code,stop,click_client))
                        hint = '已发送固定房间密码，请核对四位数字并点确定' if sent else '请手动填写固定房间密码并确认'
                        report(i,hint,state)
                    del pending[i]
                continue
            if key in used:
                continue
            route = ROUTE.get((i,state))
            dynamic = state=='ROOM_LIST' and i==1
            if route:
                if state=='CREATE_OPTIONS' and not opened_fruit_settings:
                    continue
                point, _, region, hint = route
                before = normalized(frame).crop(region)
                if distance(before,normalized(old[2]).crop(region))>5:
                    continue
            elif dynamic:
                rule = rules.get(key)
                if not teaching and rule is None:
                    continue
                owner = previous.get(0)
                if owner is None or owner[0]!='ROOM_WAITING':
                    continue
                signature = rule[0] if not teaching else None
                candidate = join_target(frame,signature)
                prior = join_target(old[2],signature)
                if not candidate or not prior or prior[0]!=candidate[0] or ink_agreement(candidate[1],prior[1])<0.82:
                    continue
                point,before = candidate
                hint = '核对房主名后，点该私人水果剧团房间右侧的加号'
            elif state in POINTS and not (state=='LEADER_READY' and i!=0):
                point = POINTS[state]
                before = patch(frame,state)
                if distance(before,patch(old[2],state))>5:
                    continue
                hint = '点「开始挑战」' if state=='LEADER_READY' else '确认自动战斗关闭后点「自动战斗」'
            else:
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
                armed[0] = tuple(armed[0] or ()) + ((key,window.hwnd,rect,point),)
                report(i,'已就绪，请'+hint,state)
            else:
                rule = rules.get(key)
                if rule is None or (not dynamic and distance(rule[0],before)>6):
                    continue
                if rule[1] is not None and distance(rule[1],before)<24:
                    continue
                if stop.is_set():
                    return
                fresh = provider.screenshot(window.hwnd)
                if not fresh or classify(fresh)!=state or stop.is_set():
                    continue
                if dynamic:
                    current = join_target(fresh,rule[0])
                    if not current or current[0]!=point:
                        continue
                elif route:
                    if distance(normalized(fresh).crop(region),before)>5:
                        continue
                elif distance(patch(fresh,state),before)>5:
                    continue
                if stop.is_set():
                    return
                click_client(provider,window,rect,point)
                report(i,'已向绑定窗口发送一次点击',state)
            pending[i]=(key,before,now+25)
            used.add(key)
        stop.wait(0.15)
