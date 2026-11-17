import unittest
from unittest.mock import patch
from windows_provider import WindowsClientProvider, WindowIdentity
from core import Rect

class ProviderTests(unittest.TestCase):
    def test_non_windows_fails_closed(self):
        with patch('windows_provider.os.name', 'posix'):
            with self.assertRaises(RuntimeError):
                WindowsClientProvider()
    def test_stale_binding_blocks_capture(self):
        p=object.__new__(WindowsClientProvider)
        p._identity={101:WindowIdentity(101,12,'Game','UnityWndClass')}
        p.identity=lambda hwnd: WindowIdentity(hwnd,13,'Game','UnityWndClass')
        p._capture=lambda bounds: b'image'
        self.assertIsNone(p.client_rect(101))
        self.assertIsNone(p.screenshot(101))
    def test_unbound_blocks_capture(self):
        p=object.__new__(WindowsClientProvider)
        p._identity={}
        p._capture=lambda bounds: b'image'
        self.assertIsNone(p.client_rect(101))
        self.assertIsNone(p.screenshot(101))
    def test_capture_exception_returns_none(self):
        p=object.__new__(WindowsClientProvider)
        p.client_rect=lambda hwnd: Rect(1,2,300,200)
        def fail(bounds): raise OSError('screen inaccessible')
        p._capture=fail
        self.assertIsNone(p.screenshot(101))
    def test_capture_uses_client_bounds(self):
        p=object.__new__(WindowsClientProvider)
        p.client_rect=lambda hwnd: Rect(1,2,300,200)
        p._capture=lambda bounds: (str(bounds)).encode()
        self.assertIn(b'300',p.screenshot(101))
if __name__=='__main__':unittest.main()
