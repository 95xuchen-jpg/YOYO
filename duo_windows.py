"""Windows desktop adapter for the four recorded daily dungeons."""
import ctypes
import json
import os
from pathlib import Path
import secrets
import threading
import time
from ctypes import wintypes

import cv2
import numpy as np
from mss import mss

from duo_run import Run, drive
from fruit_actions import click_client
from room_pin import configured_code
from windows_provider import WindowsClientProvider


def play(dungeon, windows, stop, emit):
    if len(windows)!=2 or len({w.hwnd for w in windows})!=2 or len({w.pid for w in windows})!=2:
        raise ValueError('请选择两个不同游戏进程的窗口')
    p=WindowsClientProvider()
    user=p.user32
    user.GetForegroundWindow.restype=wintypes.HWND
    rects=[]
    for w in windows:
        if p.bind(w.hwnd)!=w:
            raise ValueError('选中的游戏窗口已变化')
        rect=p.client_rect(w.hwnd)
        if not rect or rect.height<300 or abs(rect.width/rect.height-16/9)>.055:
            raise ValueError('两个客户区均需使用约 16:9 的窗口模式')
        rects.append(rect)
    def check():
        if user.GetAsyncKeyState(0x77) & 0x8001:
            stop.set()
        for w,rect in zip(windows,rects):
            if p.identity(w.hwnd)!=w or p.client_rect(w.hwnd)!=rect or not p.visible_dpi(w.hwnd,rect):
                raise ValueError('窗口移动、遮挡、最小化或绑定变化，请重新开始')
    def stopped():
        if user.GetAsyncKeyState(0x77) & 0x8001:
            stop.set()
        return stop.is_set()
    code=configured_code() or f'{secrets.randbelow(10000):04d}'
    left,top=min(r.x for r in rects),min(r.y for r in rects)
    box=dict(left=left,top=top,width=max(r.x+r.width for r in rects)-left,
             height=max(r.y+r.height for r in rects)-top)
    run=Run(dungeon)
    folder=Path.home()/'YOYO_Logs'
    folder.mkdir(parents=True,exist_ok=True)
    path=folder / f'duo-{time.strftime("%Y%m%d-%H%M%S")}-{os.getpid()}.jsonl'
    emit('日志：'+str(path))
    with mss() as desktop, path.open('x',encoding='utf8',buffering=1) as out:
        def log(i,event,step):
            out.write(json.dumps(dict(time=time.strftime('%H:%M:%S'),role=i,event=event,
                                      step=step,dungeon=dungeon),ensure_ascii=False)+'\n')
            emit(f'{"主号" if i==0 else "副号"} · {event} · 路线 {step}')
        def capture():
            check()
            image=np.asarray(desktop.grab(box))[:,:,:3]
            images=[]
            for r in rects:
                x,y=r.x-left,r.y-top
                images.append(cv2.resize(image[y:y+r.height,x:x+r.width], (800,448),
                                         interpolation=cv2.INTER_AREA))
            check()
            return images
        def send(i,action):
            check()
            if stopped():
                raise InterruptedError('本轮已停止')
            w=windows[i]
            click_client(p,w,rects[i],action.point)
            if action.name!='填写房间密码':
                return
            # The UI remembers some previous codes. Clear all four slots before typing.
            stop.wait(.12)
            for vk in [0x23]+[0x08]*4+[ord(c) for c in code]:
                check()
                if stopped() or user.GetForegroundWindow()!=w.hwnd:
                    raise ValueError('房间密码输入中止：焦点变化或按下停止键')
                # Both events are submitted together to avoid leaving a held key.
                _key_tap(user,vk)
                stop.wait(.045)
        initial=[run.vision.scene(im) for im in capture()]
        if initial[0]!='detail' or initial[1] not in ('list','daily','catalog'):
            raise ValueError('起始画面不符。主号打开所选副本详情，副号打开房间列表。当前：'+' / '.join(initial))
        try:
            status=drive(run,capture,send,stopped,stop.wait,log)
        except Exception as exc:
            log(-1,'暂停：'+str(exc),0)
            raise
        log(-1,status,0)
    return status


def _key_tap(user,vk):
    class Keyboard(ctypes.Structure):
        _fields_=[('vk',wintypes.WORD),('scan',wintypes.WORD),('flags',wintypes.DWORD),
                  ('time',wintypes.DWORD),('extra',ctypes.c_size_t)]
    class Mouse(ctypes.Structure):
        _fields_=[('x',wintypes.LONG),('y',wintypes.LONG),('data',wintypes.DWORD),
                  ('flags',wintypes.DWORD),('time',wintypes.DWORD),('extra',ctypes.c_size_t)]
    class Payload(ctypes.Union):
        _fields_=[('key',Keyboard),('mouse',Mouse)]
    class Event(ctypes.Structure):
        _fields_=[('kind',wintypes.DWORD),('payload',Payload)]
    pair=(Event*2)()
    for ev,flags in zip(pair,(0,2)):
        ev.kind=1
        ev.payload.key=Keyboard(vk,0,flags,0,0)
    user.SendInput.argtypes=[wintypes.UINT,ctypes.POINTER(Event),ctypes.c_int]
    if user.SendInput(2,pair,ctypes.sizeof(Event))!=2:
        raise OSError('Windows 未接收输入')


def gui():
    import queue
    import tkinter as tk
    from tkinter import messagebox,ttk
    from dpi_awareness import enable_per_monitor_dpi
    from duo_vision import DUNGEONS

    enable_per_monitor_dpi()
    root=tk.Tk()
    root.title('YOYO · 双账号日常副本')
    body=ttk.Frame(root,padding=15)
    body.pack(fill='both',expand=True)
    ttk.Label(body,text='主号打开目标副本详情，副号打开房间列表。两个角色提前开启游戏内自动战斗。').grid(row=0,columnspan=3,sticky='w')
    ttk.Label(body,text='运行期间保持两个游戏窗口并排可见。随时按 F8 停止。').grid(row=1,columnspan=3,sticky='w',pady=(0,10))
    query=tk.StringVar(value='飘流')
    ttk.Label(body,text='窗口标题包含').grid(row=2,column=0,sticky='w')
    ttk.Entry(body,textvariable=query).grid(row=2,column=1,sticky='ew')
    boxes=[]
    for row,label in enumerate(('主号窗口','副号窗口','副本'),3):
        ttk.Label(body,text=label).grid(row=row,column=0,sticky='w')
        box=ttk.Combobox(body,state='readonly',width=42)
        box.grid(row=row,column=1,columnspan=2,sticky='ew',pady=3)
        boxes.append(box)
    boxes[2].configure(values=list(DUNGEONS))
    boxes[2].current(0)
    windows={}
    def refresh():
        try:
            provider=WindowsClientProvider()
            windows.clear()
            for w in provider.discover(query.get().strip()):
                if provider.bind(w.hwnd)!=w: continue
                r=provider.client_rect(w.hwnd)
                if r and r.height>=300:
                    windows[f'{w.title}  ({r.x}, {r.y})  #{w.hwnd}']=w
            choices=list(windows)
            for n,b in enumerate(boxes[:2]):
                b.set('')
                b.configure(values=choices)
                if len(choices)==2:b.current(n)
            if not choices:messagebox.showinfo('查找窗口','请填写游戏标题栏里实际显示的文字，再查找。')
        except Exception as exc:messagebox.showerror('窗口',str(exc))
    ttk.Button(body,text='查找窗口',command=refresh).grid(row=2,column=2)
    status=tk.StringVar(value='等待选择窗口')
    ttk.Label(body,textvariable=status,wraplength=560).grid(row=7,columnspan=3,sticky='w',pady=8)
    stop=threading.Event()
    messages=queue.Queue()
    def worker(name,selected):
        try:
            time.sleep(.65)
            result=play(name,selected,stop,lambda s:messages.put((False,s)))
            final='两个账号均已结算并返回曼谷港。' if result=='both_returned_after_settlement' else '本轮已停止。'
        except Exception as exc:
            final=str(exc)
        messages.put((True,final))
    def poll():
        while not messages.empty():
            done,line=messages.get_nowait()
            status.set(line)
            if done:
                root.deiconify()
                run_button.configure(state='normal')
                return
        root.after(100,poll)
    def start():
        sel=[windows.get(b.get()) for b in boxes[:2]]
        if not all(sel) or sel[0].pid==sel[1].pid:
            messagebox.showinfo('双开窗口','请分别选择主号和副号。')
            return
        if not messagebox.askokcancel('运行一轮',f'{boxes[2].get()}：助手将控制这两个游戏窗口，完成一轮后停止。'):
            return
        stop.clear()
        run_button.configure(state='disabled')
        root.iconify()
        threading.Thread(target=worker,args=(boxes[2].get(),sel),daemon=True).start()
        root.after(100,poll)
    run_button=ttk.Button(body,text='运行一轮',command=start)
    run_button.grid(row=6,column=1,sticky='ew',pady=8)
    ttk.Button(body,text='停止（F8）',command=stop.set).grid(row=6,column=2)
    root.protocol('WM_DELETE_WINDOW',lambda:(stop.set(),root.destroy()))
    root.mainloop()


if __name__=='__main__':
    import sys
    if sys.argv[1:]==['--self-test']:
        from duo_vision import DUNGEONS
        for name in DUNGEONS:
            r=Run(name)
            assert len(r.vision.route)==2 and r.vision.atlas.size and not r.started
        print('OK: 4 profiles, 8 role routes')
    else:
        gui()
