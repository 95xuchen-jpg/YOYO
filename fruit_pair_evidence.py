"""Advisory Fruit Troupe evidence from two synchronized, independent desktop grabs."""
from dataclasses import asdict, dataclass
from hashlib import sha256
from io import BytesIO
from time import monotonic
from uuid import uuid4

from PIL import Image, ImageChops, ImageStat

from fruit_screen import TEMPLATES, _matches, classify
from fruit_sequence_gate import FruitEvidence, FruitSequenceGate
from observation_bridge import CaptureEvidence, _valid_png
from room_route import ink_agreement

# Upper bound from before the first grab through evaluation of the second.
MAX_AGE = 4.0
_HOST = dict(TEMPLATES)["LEADER_READY"]
_WAIT = dict(TEMPLATES)["ROOM_WAITING"]
_ROOM = {"HOST_MEMBER_ROW", "GUEST_MEMBER_ROW"}


@dataclass(frozen=True)
class Grab:
    source_id: str
    started: float
    ended: float


@dataclass(frozen=True)
class PairResult:
    captures: tuple[CaptureEvidence, ...]
    sources: tuple[Grab, ...]
    member_text_shape_agrees: bool
    reason: str

    def sequence(self):
        # The recording has no validated unique room, instance or reward key.
        # Binding labels, same-name rows and JSONL replay flags cannot supply one.
        states = tuple("ROOM_WAITING" if e.screen in _ROOM else e.screen for e in self.captures)
        stable = tuple(e.screen != "UNKNOWN" and e.two_frames_present for e in self.captures)
        return FruitSequenceGate().advance(FruitEvidence(*states, *stable))

    def summary(self):
        return dict(sources=[asdict(s) for s in self.sources], member_text_shape_agrees=self.member_text_shape_agrees,
                    same_room="UNKNOWN", same_instance="UNKNOWN", reason=self.reason,
                    sequence=self.sequence())


def _room_marker(image):
    """Recognize complementary controls and compare only the visible second name row."""
    if abs(image.width / image.height - 16 / 9) > 0.05:
        return None
    rgb = image.resize((800, 448), Image.Resampling.LANCZOS)
    gray = rgb.convert("L")
    red, _, blue = ImageStat.Stat(rgb.crop((425, 360, 436, 370))).mean
    kick = _matches(gray, *_HOST[1])
    if kick and blue - red > 60 and _matches(gray, *_HOST[2]):
        role = "HOST_MEMBER_ROW"
    elif not kick and abs(blue - red) < 10 and _matches(gray, *_WAIT[1]):
        role = "GUEST_MEMBER_ROW"
    else:
        return None
    ink = rgb.getchannel("R").crop((340, 193, 460, 219)).point(lambda x: 255 if x > 204 else 0)
    bounds = ink.getbbox()
    if not bounds or not (100 <= ink.histogram()[255] <= 850):
        return None
    x, y, right, bottom = bounds
    if not (0 < x < right < ink.width and 0 < y < bottom < ink.height and 9 <= bottom-y <= 19):
        return None
    return role, ink


def _agree(a, b):
    ax, ay, ar, ab = a.getbbox()
    bx, by, br, bb = b.getbbox()
    if abs((ar - ax) - (br - bx)) > 2 or abs((ab - ay) - (bb - by)) > 2:
        return False
    return any(ink_agreement(a, ImageChops.offset(b, x, y)) >= 0.74
               for x in (0, 1, -1, 2, -2, 3, -3) for y in (0, 1, -1, 2, -2, 3, -3))


def _context(provider, bindings):
    contexts = []
    for _, hwnd, pid in bindings:
        identity = provider.identity(hwnd)
        if identity is None or (identity.hwnd, identity.pid) != (hwnd, pid):
            raise ValueError("window_identity_changed")
        rect = provider.client_rect(hwnd)
        if rect is None:
            raise ValueError("geometry_unavailable")
        dpi = provider.visible_dpi(hwnd, rect)
        if type(dpi) is not int or dpi <= 0:
            raise ValueError("visibility_or_dpi_unverified")
        contexts.append((identity, rect, dpi))
    return tuple(contexts)


def observe_pair(provider, bindings, *, clock=monotonic):
    """Use only the selected live provider. No caller-supplied states or identity claims."""
    if (len(bindings) != 2 or tuple(b[0] for b in bindings) != ("main", "alt")
            or any(type(v) is not int or v <= 0 for _, *ids in bindings for v in ids)
            or any(len({b[i] for b in bindings}) != 2 for i in (1, 2))):
        raise ValueError("distinct main/alt window bindings required")
    sources = []
    unknown = tuple(CaptureEvidence(*b, False, False, False) for b in bindings)

    def abstain(reason):
        return PairResult(unknown, tuple(sources), False, reason)

    try:
        initial = _context(provider, bindings)
        rects = tuple(c[1] for c in initial)
        rounds = []
        for _ in range(2):
            if _context(provider, bindings) != initial:
                return abstain("capture_context_changed")
            start = clock()
            data = provider.screenshot_pair(rects)
            end = clock()
            if end < start or (sources and start <= sources[-1].ended):
                return abstain("capture_time_invalid")
            if _context(provider, bindings) != initial:
                return abstain("capture_context_changed")
            if not data or len(data) != 2 or not all(_valid_png(d, r) for d, r in zip(data, rects)):
                return abstain("paired_capture_missing")
            rounds.append(data)
            sources.append(Grab(uuid4().hex, start, end))
        screens, markers = [], []
        seen = set()
        for data in rounds:
            row = []
            for d in data:
                with Image.open(BytesIO(d)) as image:
                    rgb = image.convert("RGB")
                    digest = (rgb.size, sha256(rgb.tobytes()).digest())
                    if digest in seen:
                        return abstain("static_or_replayed_capture")
                    seen.add(digest)
                    row.append(_room_marker(rgb))
            markers.append(row)
            screens.append(tuple(m[0] if m else classify(d) for m, d in zip(row, data)))
        if _context(provider, bindings) != initial:
            return abstain("capture_context_changed")
        now = clock()
        if now < sources[-1].ended or now - sources[0].started > MAX_AGE:
            return abstain("stale_pair")
        captures = tuple(CaptureEvidence(*b, True, True, True, first if first == second else "UNKNOWN")
                         for b, first, second in zip(bindings, *screens))
        paired_rows = all(s == ("HOST_MEMBER_ROW", "GUEST_MEMBER_ROW") for s in screens)
        agreed = paired_rows and all(_agree(markers[0][0][1], m[1]) for row in markers for m in row)
        reason = "shared_identifiers_unobserved"
        if any(e.screen == "UNKNOWN" for e in captures):
            reason = "unknown_or_transitioning_panel"
        elif any(e.screen in _ROOM for e in captures) and not paired_rows:
            reason = "complementary_room_views_missing"
        elif paired_rows and not agreed:
            reason = "member_row_disagreement"
        return PairResult(captures, tuple(sources), agreed, reason)
    except ValueError as exc:
        reason = str(exc)
        if reason in {"window_identity_changed", "geometry_unavailable", "visibility_or_dpi_unverified"}:
            return abstain(reason)
        return abstain("capture_unavailable")
    except Exception:
        return abstain("capture_unavailable")
