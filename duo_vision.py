"""Identify controls and localize the expanded map against filmed terrain outlines."""
from collections import Counter
from dataclasses import dataclass
import base64
import json
from pathlib import Path

import cv2
import numpy as np


DUNGEONS = {"水果剧团": "fruit", "挑战十二生肖": "zodiac", "史莱姆居地": "clip7", "十八铜人阵": "clip2"}
from duo_trail import NAMES, Trail
from duo_lobby import same_owner
DUNGEONS.update(NAMES)

MAP_X, MAP_Y = 562, 129


@dataclass(frozen=True)
class Action:
    name: str
    point: tuple = (0, 0)


def peak(image, pattern):
    if any(x < y for x, y in zip(image.shape[:2], pattern.shape[:2])):
        return 0., (0, 0)
    scores = cv2.matchTemplate(image, pattern, cv2.TM_CCOEFF_NORMED)
    _, score, _, point = cv2.minMaxLoc(scores)
    return score, point


def outline(image):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return cv2.Canny(cv2.GaussianBlur(gray, (3, 3), 0), 10, 28)


def map_origin(atlas, image):
    """Vote across separated map patches; moving arrows and characters are outliers."""
    if atlas is None:
        return None
    local = outline(image[129:338, 562:765])
    votes = Counter()
    for y in (3, 59, 115, 159):
        for x in (4, 56, 104, 148):
            patch = local[y:y+43, x:x+46]
            if cv2.countNonZero(patch) < 45:
                continue
            scores = cv2.matchTemplate(atlas, patch, cv2.TM_CCORR_NORMED)
            _, score, _, (u, v) = cv2.minMaxLoc(scores)
            if score >= .52:
                votes[u-x, v-y] += 1
    candidates = []
    for u, v in votes:
        cluster = [(x, y) for (x, y), n in votes.items() for _ in range(n)
                   if max(abs(x-u), abs(y-v)) <= 2]
        candidates.append((len(cluster), tuple(int(round(z)) for z in np.median(cluster, axis=0))))
    candidates.sort(reverse=True)
    if not candidates or candidates[0][0] < 3:
        return None
    n, best = candidates[0]
    if any(count >= n-1 and np.linalg.norm(np.subtract(best, pos)) > 6 for count, pos in candidates[1:]):
        return None
    return best


class Vision:
    def __init__(self, dungeon):
        data = json.loads(Path(__file__).with_name('duo_profiles.json').read_text(encoding='utf8'))
        self.key = DUNGEONS[dungeon]
        routes,paths=data.pop('routes'),data.pop('paths')
        self.trail=Trail(self.key) if self.key in NAMES.values() else None
        self.route=self.trail.routes if self.trail else routes[self.key]
        self.path=paths.get(self.key,[])
        if self.trail:
            data.update(self.trail.profile['patterns'])
            data.update(self.trail.party['patterns'])
        data.update(json.loads((Path(__file__).with_name('duo_trails')/'public_lobby.json').read_text()))
        self.patterns = {}
        for name, (box, encoded) in data.items():
            if name.endswith('_atlas') and name != self.key + '_atlas':
                continue
            flags = cv2.IMREAD_COLOR if box else cv2.IMREAD_GRAYSCALE
            self.patterns[name] = box, cv2.imdecode(np.frombuffer(base64.b64decode(encoded), np.uint8), flags)
        self.atlas = None if self.trail else self.patterns[self.key+'_atlas'][1]

    def find(self, im, name, region=None, threshold=.81):
        box, template = self.patterns[name]
        if region is None:
            x, y, u, v = box
            region = (max(0, x-12), max(0, y-9), min(800, u+12), min(448, v+9))
        x, y, u, v = region
        score, (px, py) = peak(im[y:v, x:u], template)
        if score < threshold:
            return None
        h, w = template.shape[:2]
        return x+px+w//2, y+py+h//2

    def room_row(self, im, host):
        name = self.key+'_rowname'
        rows = []
        for y in (134, 173, 212, 252, 291):
            if (self.find(im, name, (293,y-15,416,y+17), .78) and
                self.find(im, 'public_type', (182,y-14,231,y+15), .84) and same_owner(host, im, y)):
                plus = self.find(im, 'plus', (638,y-15,674,y+15))
                if plus:
                    rows.append(plus)
        return rows[0] if len(rows) == 1 else None

    def scene(self, im):
        has = lambda key: self.find(im, key) is not None
        if self.trail and has('idle_gesture'): return 'idle'
        if self.trail and has('success') and (has('rewardtext') or has('reward_label')): return 'settle'
        if has('reward') and has('rewardtext'):
            return 'settle'
        if has('skip') and has('storybox'):
            return 'dialog'
        if has('join'):
            return 'join_pin'
        if has('settings'):
            if has('checked_public'):return 'public_settings'
            if has('unchecked_public'):return 'private_settings'
            return 'unknown'
        if has('room'):
            return 'room'
        if has('detail'):
            return 'detail' if has(self.key+'_detailname') and has('create') else 'other_detail'
        if has('list'):
            return 'list'
        if has('daily'):
            return 'daily'
        if has('catalog'):
            return 'catalog'
        if self.trail:
            if has('party_panel'): return 'party_panel'
            if has('port') or has('port_big'): return 'port'
            if has('battle'): return 'battle'
            if has('big') and has(self.key+'_bigtitle'): return 'map'
            if has(self.key+'_mapname') and not has('big'): return 'field'
            if has(self.key+'_fieldname') and not has('big') and self.trail.ocr.read(im,False):
                return 'field'
            return 'unknown'
        if has(self.key+'_fieldname'):
            if has('battle'):
                return 'battle'
            if has('big'):
                return 'map'
            if has(self.key+'_mapname'):
                return 'field'
        if has('port') or has('port_big'):
            return 'port'
        return 'unknown'

    def destination(self, im, goal, used):
        origin = map_origin(self.atlas, im)
        if origin is None:
            return None
        def screen(p):
            return p[0]-origin[0]+MAP_X, p[1]-origin[1]+MAP_Y
        def visible(p):
            x, y = screen(p)
            return 570 <= x <= 785 and 133 <= y <= 331 and (x<757 or y<261)
        if visible(goal):
            return Action('前往目标', screen(goal))
        options = [tuple(p) for p in self.path if visible(p) and tuple(p) not in used]
        if options:
            step = min(options, key=lambda p: np.linalg.norm(np.subtract(p, goal)))
            return Action('途经地图路点', screen(step)), step
        return None

    @staticmethod
    def clear_world(point):
        x,y=point
        return not ((x<170 and (y<104 or 125<y<309)) or (x>678 and y<124) or
                    (422<x<674 and y<58) or (178<x<213 and 125<y<209))

    def npc(self, im, role=None, index=None):
        ref = f'{self.key}_npc_{role}_{index}'
        if ref in self.patterns:
            template = self.patterns[ref][1]
            best = (0., None)
            for scale in (.8,1.,1.2):
                needle = cv2.resize(template, None, fx=scale, fy=scale)
                score, (x,y) = peak(im[28:335,40:749], needle)
                point = (40+x+needle.shape[1]//2, 28+y+needle.shape[0]//2)
                if self.clear_world(point) and score > best[0]:
                    best = (score,point)
            if best[0] >= .87:
                return best[1]
        # Quest marks float and change size with camera perspective. Compare the
        # yellow glyph and violet outline separately, excluding scenery colors.
        def masks(bgr):
            hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
            return (cv2.inRange(hsv,(17,85,175),(39,255,255)),
                    cv2.inRange(hsv,(129,62,72),(165,255,240)))
        gold, violet = masks(im)
        ref_gold, ref_violet = masks(self.patterns['quest'][1])
        candidates = []
        for contour in cv2.findContours(violet,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)[0]:
            x,y,w,h = cv2.boundingRect(contour)
            if not (7 <= w <= 34 and 9 <= h <= 40):
                continue
            cx, cy = x+w//2, y+h//2
            if cy>321 or cx<22 or cx>773 or (cx>677 and cy<127) or (cx<210 and 122<cy<314):
                continue
            if (cx<219 and cy<103) or (425<cx<670 and cy<59):
                continue
            # A small open contour may cover just the hook. Match the complete
            # question mark in a bounded search region around it.
            x0,y0=max(0,cx-24),max(0,cy-26)
            scores=[]
            for factor in (.72,.9,1.05,1.23,1.42):
                a,b=(cv2.resize(m,None,fx=factor,fy=factor,interpolation=cv2.INTER_NEAREST)
                     for m in (ref_gold,ref_violet))
                roi=(slice(y0,min(448,cy+30)),slice(x0,min(800,cx+27)))
                if min(gold[roi].shape[0]-a.shape[0],gold[roi].shape[1]-a.shape[1])<0:
                    continue
                maps=[cv2.matchTemplate(layer[roi],needle,cv2.TM_CCORR_NORMED)
                      for layer,needle in ((gold,a),(violet,b))]
                _,score,_,(u,v)=cv2.minMaxLoc(np.minimum(*maps))
                if score>.55:
                    scores.append((score,x0+u+a.shape[1]//2,y0+v+a.shape[0]//2,factor))
            if scores:
                score,mx,my,scale=max(scores)
                candidates.append((score,mx,my,scale))
        if candidates:
            score,x,y,scale=max(candidates)
            target=(x,min(345,round(y+43*scale)))
            if (target[0]<216 and 122<target[1]<315) or (target[0]>675 and target[1]<127):
                return None
            return target
        if self.trail:
            for key,(box,needle) in self.patterns.items():
                if not key.startswith(self.key+'_sprite_'):continue
                score,(x,y)=peak(im[30:323,42:747],needle)
                pt=42+x+needle.shape[1]//2,30+y+needle.shape[0]//2
                if score>.84 and self.clear_world(pt):return pt
        return None


def matching_rosters(images):
    """Compare both nonempty names between the two clients, allowing a small UI shift."""
    main, guest = images
    offsets = []
    for top in (159, 205):
        # Compare the lower strokes. The toast overlays the cap line of the host
        # name, and its opacity changes while the guest control becomes active.
        ink = cv2.cvtColor(main[top:top+8,347:426], cv2.COLOR_BGR2GRAY)
        search = cv2.cvtColor(guest[top-7:top+15,335:438], cv2.COLOR_BGR2GRAY)
        if ink.std() < 14 or np.count_nonzero(ink > np.median(ink)+22) < 24:
            return False
        score, (x,y) = peak(search, ink)
        if score < .76:
            return False
        offsets.append((x,y))
    return dist_pixels(offsets[0], offsets[1]) <= 3


def dist_pixels(a, b):
    return max(abs(a[0]-b[0]), abs(a[1]-b[1]))
