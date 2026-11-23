"""Advisory Fruit Troupe evidence from two synchronized, independent desktop grabs."""
from dataclasses import asdict, dataclass
from hashlib import sha256
from io import BytesIO
from time import perf_counter
from uuid import uuid4

from PIL import Image, ImageChops, ImageStat

from fruit_screen import TEMPLATES, _matches, classify
from fruit_receipt import outcome_panel
from fruit_sequence_gate import FruitEvidence, FruitSequenceGate
from observation_bridge import CaptureEvidence, _valid_png
from room_route import ink_agreement

# Use the high-resolution performance counter for both capture and session times.
# Adjacent grabs can share a tick of the lower-resolution Windows 3.11 monotonic clock.
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
        phases = {"HOST_MEMBER_ROW": "ROOM_WAITING", "GUEST_MEMBER_ROW": "ROOM_WAITING",
                  "FRUIT_SETTLEMENT": "REWARD_PANEL", "FRUIT_SETTLEMENT_WITH_RECEIPT": "REWARD_PANEL",
                  "FRUIT_RECEIPT_IN_PORT": "REWARD"}
        states = tuple(phases.get(e.screen, e.screen) for e in self.captures)
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


def observe_pair(provider, bindings, *, clock=perf_counter, expected_context=None, recent_pixels=None):
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
        if expected_context is not None and initial != expected_context:
            return abstain("capture_context_changed")
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
            labels = []
            for d in data:
                with Image.open(BytesIO(d)) as image:
                    rgb = image.convert("RGB")
                    digest = (rgb.size, sha256(rgb.tobytes()).digest())
                    if digest in seen or (recent_pixels is not None and digest in recent_pixels):
                        return abstain("static_or_replayed_capture")
                    seen.add(digest)
                    member = _room_marker(rgb)
                    row.append(member)
                    if member:
                        label = member[0]
                    else:
                        label = classify(d)
                        if abs(rgb.width / rgb.height - 16 / 9) <= 0.05:
                            gray = rgb.resize((800, 448), Image.Resampling.LANCZOS).convert("L")
                            label = outcome_panel(gray, label)
                    labels.append(label)
            markers.append(row)
            screens.append(tuple(labels))
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
        if recent_pixels is not None:
            recent_pixels.update(seen)
        return PairResult(captures, tuple(sources), agreed, reason)
    except ValueError as exc:
        reason = str(exc)
        if reason in {"window_identity_changed", "geometry_unavailable", "visibility_or_dpi_unverified"}:
            return abstain(reason)
        return abstain("capture_unavailable")
    except Exception:
        return abstain("capture_unavailable")


def watch_pair(provider, bindings, stop, on_change, *, clock=perf_counter, duration=900):
    """Follow one bound pair. Output only observed UI milestones, never authorize input."""
    accounts = ("main", "alt")
    # Settlement-to-port is a short transition. Expire associations across gaps.
    settlement = [None, None]
    receipt = [False, False]
    previous = None
    recent_pixels = set()  # Session-only pixel digests, excluded from reports.
    samples = 0
    since = clock()
    last_timestamp = since
    outcome = dict(status="paused", input_enabled=False, game_state_verified=False,
                   same_room="UNKNOWN", same_instance="UNKNOWN")
    initial = _context(provider, bindings)
    reason = "observation_timeout"
    while clock() - since < duration:
        if stop.is_set():
            reason = "observation_stopped"
            break
        pair = observe_pair(provider, bindings, clock=clock, expected_context=initial, recent_pixels=recent_pixels)
        if stop.is_set():
            reason = "observation_stopped"
            break
        if not all(c.identity_ok and c.geometry_ok and c.two_frames_present for c in pair.captures):
            reason = pair.reason
            break
        first, last = pair.sources
        if first.started < last_timestamp or last.ended <= last_timestamp:
            reason = "capture_time_invalid"
            break
        last_timestamp = last.ended
        samples += 1
        states = tuple(c.screen for c in pair.captures)
        for i, state in enumerate(states):
            if settlement[i] is not None and last.ended - settlement[i] > 15:
                reason = "settlement_window_expired"
                break
            if state == "FRUIT_SETTLEMENT_WITH_RECEIPT":
                reason = "receipt_already_visible_at_settlement"
                break
            if state == "FRUIT_SETTLEMENT" and settlement[i] is None:
                settlement[i] = last.ended
            if state == "FRUIT_RECEIPT_IN_PORT" and settlement[i] is not None:
                receipt[i] = True
            if settlement[i] is not None and state not in (
                    "FRUIT_SETTLEMENT", "FRUIT_RECEIPT_IN_PORT", "UNKNOWN", "FRUIT_LOADING"):
                reason = "scene_changed_after_settlement"
                break
        else:
            current = (states, tuple(receipt), pair.member_text_shape_agrees)
            if current != previous:
                event = dict(screens=dict(zip(accounts, states)), receipt_after_settlement=dict(zip(accounts, receipt)),
                             elapsed_seconds=round(last.ended - since, 2), **pair.summary())
                on_change(event)
                previous = current
            if all(receipt) and states == ("FRUIT_RECEIPT_IN_PORT", "FRUIT_RECEIPT_IN_PORT"):
                outcome["status"] = "observed"
                reason = "both_port_receipts_observed_after_settlement"
                break
            stop.wait(0.1)
            continue
        break
    return dict(outcome, reason=reason, samples=samples, receipt_after_settlement=dict(zip(accounts, receipt)))
