from io import BytesIO
import unittest
from PIL import Image, ImageDraw
from room_route import ROW_MARKS, join_target, ROUTE


def listing(rows):
    img = Image.new('RGB',(800,448),'white')
    draw = ImageDraw.Draw(img)
    for y, owner in rows:
        draw.rectangle((193,y-4,213,y+3),fill='red')
        for x,mask in zip((329,590),ROW_MARKS):
            img.paste('black',(x,y-9,x+mask.width,y-9+mask.height),mask)
        draw.rectangle((482+owner,y-5,506+owner,y+6),fill='black')
    buf=BytesIO()
    img.save(buf,format='PNG')
    return buf.getvalue()


class RoomRouting(unittest.TestCase):
    def test_changed_row_and_owner(self):
        _,signature=join_target(listing([(173,0)]))
        self.assertEqual(join_target(listing([(212,0)]),signature)[0],(655,212))
        self.assertIsNone(join_target(listing([(173,40)]),signature))
        self.assertIsNone(join_target(listing([(134,0),(212,0)]),signature))
        self.assertIsNone(join_target(listing([(134,0),(212,40)])))
        self.assertIsNone(join_target(listing([])))

    def test_roles_and_password_screen(self):
        self.assertEqual(ROUTE[0,'CATALOG'][1],'FRUIT_DETAILS')
        self.assertEqual(ROUTE[1,'CATALOG'][1],'ROOM_LIST')
        for role in (0,1):
            self.assertNotIn((role,'PRIVATE_CREATE'),ROUTE)
            self.assertNotIn((role,'PRIVATE_JOIN'),ROUTE)
