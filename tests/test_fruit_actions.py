import os
import unittest
from io import BytesIO
from types import SimpleNamespace
from PIL import Image
from fruit_actions import changed, click_client, same_party


class FruitActions(unittest.TestCase):
    def test_room_wait_and_other_dialogs_do_not_verify_entry(self):
        self.assertFalse(changed('LEADER_READY',None,'ROOM_WAITING',None))
        self.assertFalse(changed('LEADER_READY',None,'UNKNOWN',None))
        self.assertTrue(changed('LEADER_READY',None,'FRUIT_LOADING',None))

    def test_blank_rosters_do_not_match(self):
        frame=BytesIO()
        Image.new('RGB',(800,448)).save(frame,'PNG')
        self.assertFalse(same_party(frame.getvalue(),frame.getvalue()))

    @unittest.skipUnless(os.name=='nt','requires Windows')
    def test_native_window_receives_only_the_addressed_click(self):
        import tkinter as tk
        import ctypes
        from ctypes import wintypes
        from windows_provider import WindowsClientProvider
        root=tk.Tk()
        try:
            root.geometry('400x225+50+50')
            root.attributes('-topmost',True)
            canvas=tk.Canvas(root,highlightthickness=0)
            canvas.pack(fill='both',expand=True)
            events=[]
            canvas.bind('<ButtonRelease-1>',lambda e: events.append((e.x,e.y)))
            root.update()
            provider=WindowsClientProvider()
            window=provider.bind(canvas.winfo_id())
            rect=provider.client_rect(window.hwnd)
            click_client(provider,window,rect,(400,224))
            from time import monotonic, sleep
            deadline=monotonic()+1
            while not events and monotonic()<deadline:
                root.update()
                sleep(0.01)
            self.assertEqual(events,[(round(rect.width/2),round(rect.height/2))])
        finally:
            root.destroy()
