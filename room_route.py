"""Steps verified in the two-client Fruit Troupe recording. Coordinates are client-relative."""
from base64 import b85decode
from io import BytesIO
from PIL import Image, ImageChops, ImageStat

# Role, screen -> control, expected resulting screen, sample region, prompt.
ROUTE = {
    (0,'DAILY'): ((751,169),'CATALOG',(738,144,770,185),'点「副本」'),
    (1,'DAILY'): ((751,169),'CATALOG',(738,144,770,185),'点「副本」'),
    (0,'CATALOG'): ((245,211),'FRUIT_DETAILS',(212,202,280,225),'点「水果剧团」卡片名称'),
    (1,'CATALOG'): ((83,139),'ROOM_LIST',(49,128,119,153),'点「房间列表」'),
    (0,'FRUIT_DETAILS'): ((604,401),'CREATE_OPTIONS',(565,391,642,411),'点「创建房间」'),
    (0,'CREATE_OPTIONS'): ((467,205),'PRIVATE_CREATE',(453,192,507,217),'点「私人」选项'),
}


def normalized(frame):
    with Image.open(BytesIO(frame)) as img:
        return img.convert('RGB').resize((800,448),Image.Resampling.LANCZOS)


def row_signature(image,y):
    # Compare the ink shape, ignoring light backgrounds and the cursor on the plus.
    strip=image.crop((477,y-9,575,y+10)).convert('L')
    return strip.point(lambda v: 255 if v < 160 else 0)


def ink_agreement(a,b):
    aa=a.histogram()[255]
    bb=b.histogram()[255]
    if min(aa,bb)<30:
        return 0
    overlap=ImageChops.darker(a,b).histogram()[255]
    return 2*overlap/(aa+bb)


ROW_MARKS = tuple(Image.open(BytesIO(b85decode(s))).convert("L") for s in ['iBL{Q4GJ0x0000DNk~Le0000!0000J2mk;80PUFJZ~y=Rkx4{BRCt{2Q9%;KFbIOq{{PGD!B{b|eZbCoXp;zt3j70r#*6%2lC&XDMj#~QXQkB-0Io@hvp&G>zv$t~RB4<taCY;taw=LOxQjJ&X`Za23|Ks^LAb(UKFW27>GEONX+E=}otxa<RUhl+=}3{*10>Q2<5F^;wQCI%?-w(Fd#1Uj%8*rfh?mrl#utI|PVj#))`I{5002ovPDHLkV1f', 'iBL{Q4GJ0x0000DNk~Le0000c0000J2mk;80NLRnYybcNO-V#SRCt`-k1-AaAP572|NprTMgo*X<KQ4m%^e|C<eLFK0q_<fBxp0VyBnZgck>>B(KUBkO|l3{U)Ytf%5?>rzFs)0X6-;dp8=q_9r8JHasmJV002ovPDHLkV1f'])


def matches_marker(image,x,y,marker):
    w,h = marker.size
    return any(ink_agreement(marker,image.crop((x+dx,y+dy,x+dx+w,y+dy+h)).convert("L").point(lambda v: 255 if v<160 else 0)) >= 0.66
               for dx in (0,-1,1,-2,2,-3,3) for dy in (0,-1,1,-2,2))


def join_target(frame, signature=None):
    image=normalized(frame)
    # Only private rows have red text under the type column. Orange/blue rows are ignored.
    candidates=[]
    for y in (134,173,212,251,291):
        label=image.crop((188,y-9,227,y+10))
        if sum(r>g+38 and r>b+33 for r,g,b in label.getdata())<12:
            continue
        if not (matches_marker(image,329,y-9,ROW_MARKS[0]) and matches_marker(image,590,y-9,ROW_MARKS[1])):
            continue
        name=row_signature(image,y)
        if ImageStat.Stat(name).stddev[0]<20:
            continue
        if signature is None or ink_agreement(signature,name)>=0.82:
            candidates.append(((655,y),name))
    return candidates[0] if len(candidates)==1 else None
