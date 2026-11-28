"""Read room owner names and dungeon card labels from the two live clients."""
import cv2
import numpy as np


def crop_ink(gray):
    ys,xs=np.where(gray>25)
    if len(xs)<12:return None
    return gray[ys.min():ys.max()+1,xs.min():xs.max()+1]


def same_owner(host,guest,y):
    # The owner's white roster text and the dark room-list text use different scales.
    a=cv2.cvtColor(host[148:169,342:459],cv2.COLOR_BGR2GRAY).astype(np.int16)
    b=cv2.cvtColor(guest[y-10:y+11,471:575],cv2.COLOR_BGR2GRAY).astype(np.int16)
    a=crop_ink(np.clip(a-np.median(a)-12,0,255).astype(np.uint8))
    b=crop_ink(np.clip(np.median(b)-b-14,0,255).astype(np.uint8))
    if a is None or b is None:return False
    if abs(np.log((a.shape[1]/a.shape[0])/(b.shape[1]/b.shape[0])))>.22:return False
    a,b=(cv2.resize(im,(max(14,b.shape[1]*2),27),interpolation=cv2.INTER_LINEAR) for im in (a,b))
    value=cv2.matchTemplate(cv2.copyMakeBorder(b,2,2,3,3,cv2.BORDER_CONSTANT),a,cv2.TM_CCOEFF_NORMED).max()
    return value>=.54


def card_label(im, pattern):
    # Only blue title lettering on the two caption lines of the catalog.
    def blue(im):
        b,_,r=cv2.split(im.astype(np.int16))
        return np.uint8(np.clip(b-r,0,145))
    label=crop_ink(blue(pattern))
    if label is None:return None
    best=[]
    for y in (213,355):
        strip=blue(im[y-14:y+14,174:684])
        peaks=[]
        for scale in (.88,.94,1.,1.06):
            needle=cv2.resize(label,None,fx=scale,fy=scale)
            matches=cv2.matchTemplate(strip,needle,cv2.TM_CCOEFF_NORMED)
            _,val,_,(x,dy)=cv2.minMaxLoc(matches)
            peaks.append((val,(174+x+needle.shape[1]//2,y-14+dy+needle.shape[0]//2)))
        best.append(max(peaks))
    score,pt=max(best)
    return pt if score>=.85 else None


def catalog_view(im):
    return cv2.resize(im[102:180,180:679],(64,12),interpolation=cv2.INTER_AREA).astype(np.int16)
