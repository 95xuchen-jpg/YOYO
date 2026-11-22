import threading
import unittest
from unittest.mock import MagicMock,patch
from room_pin import fill_room

class RoomPinTests(unittest.TestCase):
    def test_no_click_for_other_screen_or_existing_value(self):
        provider=MagicMock()
        window=MagicMock()
        rect=MagicMock()
        click=MagicMock()
        for observed,empty in [('UNKNOWN',True),('PRIVATE_CREATE',False)]:
            with patch('room_pin.classify',return_value=observed), patch('room_pin.field_empty',return_value=empty):
                self.assertFalse(fill_room(provider,window,rect,'PRIVATE_CREATE','0123',threading.Event(),click))
        click.assert_not_called()

    def test_cancel_before_any_capture(self):
        stop=threading.Event()
        stop.set()
        provider=MagicMock()
        self.assertFalse(fill_room(provider,MagicMock(),None,'PRIVATE_JOIN','0123',stop,MagicMock()))
        provider.screenshot.assert_not_called()
