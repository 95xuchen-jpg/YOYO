import unittest
from dpi_awareness import enable_per_monitor_dpi
class FakeUser:
    def __init__(self, success=False): self.success=success
    def SetProcessDpiAwarenessContext(self, context): return self.success
    def SetProcessDPIAware(self): return True
class FakeCore:
    def __init__(self, result): self.result=result
    def SetProcessDpiAwareness(self, value): return self.result
class TestDpi(unittest.TestCase):
    def test_non_windows(self): self.assertEqual(enable_per_monitor_dpi(platform='posix'), 'not_windows')
    def test_v2(self): self.assertEqual(enable_per_monitor_dpi(platform='nt', user32=FakeUser(True), shcore=FakeCore(1)), 'per_monitor_v2')
    def test_v1(self): self.assertEqual(enable_per_monitor_dpi(platform='nt', user32=FakeUser(), shcore=FakeCore(0)), 'per_monitor_v1')
    def test_fallback(self): self.assertEqual(enable_per_monitor_dpi(platform='nt', user32=FakeUser(), shcore=FakeCore(1)), 'system_dpi')
