"""Decode the fixed-size coordinate display after the game window is normalized."""
import json
from pathlib import Path

import cv2
import numpy as np


class Coordinates:
    def __init__(self):
        glyphs = json.loads((Path(__file__).with_name('duo_trails')/'digits.json').read_text())
        self.bank = [np.array(glyphs[c], np.float32).reshape(-1,60) for c in '0123456789(,)']
        self.bank = [self.normalized(b) for b in self.bank]

    @staticmethod
    def normalized(rows):
        rows = rows - rows.mean(axis=1, keepdims=True)
        return rows / np.maximum(1.,np.linalg.norm(rows, axis=1, keepdims=True))

    def read(self, im, big):
        x0,y0 = (561,341) if big else (681,104)
        crop = cv2.cvtColor(im[y0:y0+19,x0:x0+85],cv2.COLOR_BGR2GRAY)
        cells = np.lib.stride_tricks.sliding_window_view(crop,(10,6))
        h,w = cells.shape[:2]
        rows = self.normalized(cells.reshape(-1,60).astype(np.float32))
        scores = np.stack([np.einsum('id,jd->ij',rows,b,optimize=False).max(axis=1) for b in self.bank],axis=1).reshape(h,w,13)
        vals, chars = scores[:,:,:10].max(axis=2),scores[:,:,:10].argmax(axis=2)
        best=None
        for first in range(7,14):
            for n in (3,4,5):
                for m in (3,4,5):
                    starts=[first+round(j*5.91) for j in range(n)]
                    starts += [first+round((n+j)*5.91+3.25) for j in range(m)]
                    left,comma,right=first-4,first+round(n*5.91)-1,first+round((n+m)*5.91+2.5)
                    glyph=vals[:,starts]
                    punct=np.stack([scores[:,left,10],scores[:,comma,11],scores[:,right,12]],axis=1)
                    grade=.65*glyph.mean(axis=1)+.35*punct.mean(axis=1)
                    grade[(glyph.min(axis=1)<.60)|(punct.min(axis=1)<.54)]=-1
                    y=int(grade.argmax()); score=float(grade[y])
                    if score>.80 and (best is None or score>best[0]):
                        s=''.join(str(z) for z in chars[y,starts]);best=(score,(int(s[:n]),int(s[n:])))
        return best[1] if best else None
