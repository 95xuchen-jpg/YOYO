"""Route data and visual navigation for the six split-volume recordings."""
import json
from math import hypot
from pathlib import Path

import cv2
import numpy as np

from duo_coords import Coordinates


NAMES = {'勇闯火焰山':'fire','幽灵之地':'ghost','黑暗藏身地':'dark',
         '亚历山大帝':'alex','拯救蓝星人':'blue','侏罗纪牧场':'dino'}
ROOT = Path(__file__).with_name('duo_trails')


def cyan(im):
    return cv2.inRange(cv2.cvtColor(im,cv2.COLOR_BGR2HSV),(80,95,105),(104,255,255))


def arrow(im, flag):
    mask=cyan(im[128:339,562:790])
    count, labels, stats, centers=cv2.connectedComponentsWithStats(mask)
    candidates=[]
    for i in range(1,count):
        x,y,w,h,area=stats[i]
        if not (5<=w<=13 and 5<=h<=13 and 22<=area<=90):
            continue
        # The other cyan map icon is a flag with a straight pole and a right-facing pennant.
        patch=np.uint8(labels[y:y+h,x:x+w]==i)*255
        if w<8 and h>=8 and x<226:
            resized=cv2.resize(patch,(8,11),interpolation=cv2.INTER_NEAREST)
            if np.mean((resized>0)==flag)>.73 or (h>w and patch[-3:,:w//2+1].sum()>patch[-3:,w//2+1:].sum()*2.6):
                continue
        candidates.append(tuple(centers[i]+(562,128)))
    return candidates[0] if len(candidates)==1 else None


class Trail:
    def __init__(self,key):
        self.profile=json.loads((ROOT/(key+'.json')).read_text(encoding='utf8'))
        self.party=json.loads((ROOT/'party.json').read_text(encoding='utf8'))
        self.ocr=Coordinates()
        self.flag=np.asarray(self.party['flag'],bool)
        self.routes=self.profile['routes']
        self.scale=self.profile['scale']
        self.patrol=self.profile['patrol']
        self.party_at=self.profile['party_at']
        self.counter=self.profile['counter']
        if self.counter:
            self.counter=np.uint8(self.counter)*255

    def counter_state(self,im):
        if self.counter is None:return None
        hsv=cv2.cvtColor(im[200:303,55:138],cv2.COLOR_BGR2HSV)
        scores=[]
        for low,hi in ((10,36),(40,88)):
            m=cv2.inRange(hsv,(low,75,99),(hi,255,255))
            scores.append(cv2.minMaxLoc(cv2.matchTemplate(m,self.counter,cv2.TM_CCOEFF_NORMED))[1])
        if max(scores)<.46 or abs(scores[0]-scores[1])<.065:return None
        return 'complete' if scores[1]>scores[0] else 'pending'

    def destination(self,im,current,goal):
        origin=arrow(im,self.flag)
        if origin is None:return None
        x,y=origin
        dx=(goal[0]-current[0])*self.scale[0]
        dy=(goal[1]-current[1])*self.scale[1]
        for factor in (1.,.78,.58,.42,.30,.20,.13,.085):
            tx,ty=round(x+dx*factor),round(y+dy*factor)
            if (565<=tx<=787 and 131<=ty<=335 and (tx<759 or ty<264)
                    and hypot(tx-x,ty-y)>3):
                return tx,ty
        return None


def party_visible(im):
    """Both party roster rows show red HP and blue SP below the party tab."""
    hsv=cv2.cvtColor(im,cv2.COLOR_BGR2HSV)
    for y in (160,211):
        bars=hsv[y-13:y+15,82:153]
        red=cv2.inRange(bars,(0,97,90),(9,255,255)) | cv2.inRange(bars,(170,97,90),(179,255,255))
        blue=cv2.inRange(bars,(87,92,90),(115,255,255))
        if min(np.count_nonzero(red),np.count_nonzero(blue))<55:return False
    return True


def same_portrait(candidate, other):
    def hist(image):
        hsv=cv2.cvtColor(image,cv2.COLOR_BGR2HSV)
        counts=cv2.calcHist([hsv],[0,1],None,[12,4],[0,180,0,256])
        return cv2.normalize(counts,counts,1,0,cv2.NORM_L1)
    return cv2.compareHist(hist(candidate),hist(other[3:32,7:39]),cv2.HISTCMP_BHATTACHARYYA)<.61
