"""Read-only glyph matching for the Fruit gift system message and map header."""
from base64 import b85decode
from PIL import Image, ImageChops, ImageOps


def _marker(box, encoded):
    x, y, right, bottom = box
    mask = Image.frombytes("1", (right - x, bottom - y), b85decode(encoded)).convert("L")
    return box, mask


# Monochrome static UI lettering from the source MP4 at 189.70 and 193.40 s.
# The receipt requires the channel, verb, item and quantity on the same line.
CHANNEL = _marker((14, 416, 41, 430), '0000000000KjDM`e}TV%41+&_KZD5tKL?wD9O1u!KjYc}HZz(462KAwa%1v<Ml*AO1ONd5')
OBTAINED = _marker((46, 417, 72, 430), '00000fAPP79m6qz2!b(yFrmKyaj_o&U-LhJ8G!=;dBHz`SwS-Z8etOvHZcYO00000')
GIFT = _marker((89, 416, 167, 430), '00000000000006200000000310s;RYg#Y0f1AqbnyBO5MV~`Hu0wMn&w1OwlKlpoLvl}%3;E+Ga8^Qk@G>0LW4d5GqI3M(mBbW>z62t$K6q+a458yIjd>@qZAs8R<Vle(3#D*ae7SKWyla$27VHp<C4gwH|%>UsJKllIu0000000000')
QUANTITY = _marker((170, 417, 190, 430), '0000000006000L7L<0b10{}P!02l)RI0FDI0{~_ZfB*mh0000')
PORT = _marker((689, 9, 720, 21), '00000KLTMiKZG&<KZ%ewKZC>mf5u@Zf1mh%e}*CU8w4RR9|z+yVa6aF00000')
FRUIT = _marker((688, 9, 735, 21), '0000000065`0*d$1_s!fF(3v<`28^;KE~L!Kj04o`28~=8wdThHy{#+`Tad0B4hE%Gav>g&G|pz3;;k&5Fh{m00000')

def _gift_glyphs():
    (x, y, _, bottom), mask = GIFT
    width = mask.width // len("水果剧团礼盒")
    return tuple(((x + i, y, x + i + width, bottom), mask.crop((i, 0, i + width, mask.height)))
                 for i in range(0, mask.width, width))


_GLYPHS = _gift_glyphs()
_OFFSETS = (0, -1, 1, -2, 2, -3, 3)


def _match(gray, marker, dx, dy):
    (x, y, right, bottom), mask = marker
    patch = gray.crop((x + dx, y + dy, right + dx, bottom + dy))
    low, high = patch.getextrema()
    if high - low < 25:
        return False
    ink = ImageOps.autocontrast(patch).point(lambda p: 255 if p >= 133 else 0)
    # Both missing and additional strokes count against a match.
    overlap = ImageChops.darker(ink, mask).histogram()[255]
    return 2 * overlap >= 0.74 * (ink.histogram()[255] + mask.histogram()[255])


def _find(gray, marker):
    return any(_match(gray, marker, dx, dy) for dx in _OFFSETS for dy in _OFFSETS)


def receipt_visible(gray):
    # Both clients show the newest system message on the last chat line.
    # A moved/scrolled or hidden row has no positive evidence.
    return any(all(_match(gray, m, dx, dy) for m in (GIFT, OBTAINED, CHANNEL, QUANTITY, *_GLYPHS))
               for dx in _OFFSETS for dy in _OFFSETS)


def outcome_panel(gray, panel):
    if panel == "REWARD_PANEL" and _find(gray, FRUIT):
        # A receipt already visible at settlement cannot establish a new award.
        for line in (0, -18, -36, -54):
            if any(_match(gray, GIFT, dx, line + dy) for dx in _OFFSETS for dy in _OFFSETS):
                return "FRUIT_SETTLEMENT_WITH_RECEIPT"
        return "FRUIT_SETTLEMENT"
    if panel == "UNKNOWN" and _find(gray, PORT) and receipt_visible(gray):
        return "FRUIT_RECEIPT_IN_PORT"
    return panel
