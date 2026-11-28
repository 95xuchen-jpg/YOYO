"""Windows desktop adapter for the recorded daily dungeons."""
import ctypes
import json
import os
from pathlib import Path
import threading
import time
from ctypes import wintypes

import cv2
import numpy as np
from mss import mss

from duo_run import Run, drive
from fruit_actions import click_client
from windows_provider import WindowsClientProvider


def play(dungeons, rounds, windows, stop, emit):
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
    left,top=min(r.x for r in rects),min(r.y for r in rects)
    box=dict(left=left,top=top,width=max(r.x+r.width for r in rects)-left,
             height=max(r.y+r.height for r in rects)-top)
    folder=Path.home()/'YOYO_Logs'
    folder.mkdir(parents=True,exist_ok=True)
    path=folder / f'duo-{time.strftime("%Y%m%d-%H%M%S")}-{os.getpid()}.jsonl'
    emit('日志：'+str(path))
    with mss() as desktop, path.open('x',encoding='utf8',buffering=1) as out:
        def log(i,event,step):
            out.write(json.dumps(dict(time=time.strftime('%H:%M:%S'),role=i,event=event,
                                      step=step,dungeon=dungeon),ensure_ascii=False)+'\n')
            emit(event if i<0 else f'{dungeon} · {"主号" if i==0 else "副号"} · {event} · 路线 {step}')
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
            swipes={'解除游戏省电模式':(322,492,224),'向后翻副本目录':(613,261,268),'向前翻副本目录':(240,592,268)}
            if action.name in swipes:
                swipe(user,w,rects[i],check,stopped,*swipes[action.name])
                return
            click_client(p,w,rects[i],action.point)
        def run_one(name,index,total):
            nonlocal dungeon
            dungeon=name
            run=Run(name)
            log(-1,f'开始队列 {index}/{total} · {name}',0)
            try:
                result=drive(run,capture,send,stopped,stop.wait,log)
            except Exception as exc:
                log(-1,'停止：'+str(exc),0)
                raise
            log(-1,result,0)
            return result
        dungeon=''
        return run_queue(dungeons,rounds,run_one,stopped)


def run_queue(dungeons,rounds,run_one,stopped):
    if not dungeons or rounds<1:raise ValueError('请选择副本并填写正整数轮数')
    order=tuple(dungeons)*rounds
    for index,name in enumerate(order,1):
        if stopped():return 'stopped'
        try:
            result=run_one(name,index,len(order))
        except Exception as exc:
            raise ValueError(f'队列 {index}/{len(order)} · {name} 已停止：{exc}') from exc
        if result!='both_returned_after_settlement':return 'stopped'
    return 'queue_complete'


def swipe(user,window,rect,check,stopped,start,end,y):
    user.WindowFromPoint.argtypes=[wintypes.POINT]
    user.WindowFromPoint.restype=wintypes.HWND
    def move(x):
        check()
        if stopped():raise InterruptedError('队列已停止')
        point=wintypes.POINT(rect.x+round(x*rect.width/800),rect.y+round(y*rect.height/448))
        if user.WindowFromPoint(point)!=window.hwnd or not user.SetCursorPos(point.x,point.y):
            raise ValueError('目标位置被遮挡或窗口已变化')
    move(start)
    user.mouse_event(0x0002,0,0,0,0)
    try:
        for step in range(1,27):
            move(start+(end-start)*step/26)
            time.sleep(.014)
    finally:
        user.mouse_event(0x0004,0,0,0,0)


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
    ttk.Label(body,text='两个角色停在曼谷港，开启游戏内自动战斗。助手会建公开房，副号按房主名称加入。').grid(row=0,columnspan=3,sticky='w')
    ttk.Label(body,text='运行期间保持两个游戏窗口并排可见。随时按 F8 停止。').grid(row=1,columnspan=3,sticky='w',pady=(0,10))
    query=tk.StringVar(value='飘流')
    ttk.Label(body,text='窗口标题包含').grid(row=2,column=0,sticky='w')
    ttk.Entry(body,textvariable=query).grid(row=2,column=1,sticky='ew')
    boxes=[]
    for row,label in enumerate(('主号窗口','副号窗口'),3):
        ttk.Label(body,text=label).grid(row=row,column=0,sticky='w')
        box=ttk.Combobox(body,state='readonly',width=42)
        box.grid(row=row,column=1,columnspan=2,sticky='ew',pady=3)
        boxes.append(box)
    selected=[]
    choices_frame=ttk.LabelFrame(body,text='按勾选顺序进入副本',padding=6)
    choices_frame.grid(row=5,columnspan=3,sticky='ew',pady=6)
    queue_text=tk.StringVar()
    def toggle(name,flag):
        if flag.get():selected.append(name)
        else:selected.remove(name)
        queue_text.set(' → '.join(selected) or '请选择副本')
    flags=[]
    for n,name in enumerate(DUNGEONS):
        flag=tk.BooleanVar(value=n==0)
        flags.append(flag)
        if n==0:toggle(name,flag)
        ttk.Checkbutton(choices_frame,text=name,variable=flag,
                        command=lambda name=name,f=flag:toggle(name,f)).grid(
                            row=n//3,column=n%3,sticky='w',padx=6)
    ttk.Label(body,textvariable=queue_text,wraplength=510).grid(row=6,columnspan=3,sticky='w')
    rounds=tk.StringVar(value='1')
    ttk.Label(body,text='队列轮数').grid(row=7,column=0,sticky='w')
    ttk.Spinbox(body,from_=1,to=99,textvariable=rounds,width=6).grid(row=7,column=1,sticky='w')
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
    ttk.Label(body,textvariable=status,wraplength=560).grid(row=9,columnspan=3,sticky='w',pady=8)
    stop=threading.Event()
    messages=queue.Queue()
    def worker(names,count,windows_pair):
        try:
            time.sleep(.65)
            result=play(names,count,windows_pair,stop,lambda s:messages.put((False,s)))
            final=f'队列完成，共 {len(names)*count} 场，两个账号均已结算回港。' if result=='queue_complete' else '队列已停止。'
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
        try:count=int(rounds.get())
        except ValueError:count=0
        if not selected or not 1<=count<=99:
            messagebox.showinfo('副本队列','请至少选择一个副本，队列轮数可填 1 至 99。')
            return
        names=tuple(selected)
        if not messagebox.askokcancel('运行队列',f'{" → ".join(names)}\n共 {count} 轮、{len(names)*count} 场。现在开始？'):
            return
        stop.clear()
        run_button.configure(state='disabled')
        root.iconify()
        threading.Thread(target=worker,args=(names,count,sel),daemon=True).start()
        root.after(100,poll)
    run_button=ttk.Button(body,text='开始队列',command=start)
    run_button.grid(row=8,column=1,sticky='ew',pady=8)
    ttk.Button(body,text='停止（F8）',command=stop.set).grid(row=8,column=2)
    root.protocol('WM_DELETE_WINDOW',lambda:(stop.set(),root.destroy()))
    root.mainloop()


if __name__=='__main__':
    import sys
    if sys.argv[1:]==['--self-test']:
        from duo_vision import DUNGEONS
        for name in DUNGEONS:
            r=Run(name)
            assert len(r.vision.route)==2 and all(r.vision.route) and not r.started
            assert r.vision.trail or r.vision.atlas.size
        assert len(DUNGEONS)==10
    else:
        gui()
