"""Recognize visible Fruit Troupe objective and reward panels from two bound captures."""
from base64 import b85decode
from io import BytesIO
from PIL import Image, ImageChops, ImageStat

# Crops contain only static UI text from the reference recording.
# Coordinates use an 800 x 448 normalized client area.
REFERENCE = (
    ('OBJECTIVES', (((37, 157, 93, 176), 'iBL{Q4GJ0x0000DNk~Le0000u0000J2mk;80N{p^Hvj+wq)9|URCt^v%h_*~RTKd5bIv{Yn{Q@1Ez*%`JCF(nhN6~|uoy^*X#-RYf+&l`#HT)}QU4l)aV1J35jBQr5EqKIC_+P_0xcCR6eu8N=`!uN+<T4>{@#Ds2A}|H8m6i!3X0-E5g~|e#)uR3o-<<e>b$5!W+#Z?gcSh+)0%e=p3SNP2CM236Gk)LA4kicB=j)yk1uxh&bBQOujmkQ_Vit5bnL+hl}OT5L-jkO;qbY^@zUziv3S*n!K_wlefd_)AAV#0nkCG}QK@ig0vH&XtRZjH%=4G8S||6f)cKo3NgJrx@t<;Wh>O|}rD+_W{x;O?o`K#?FM<(Pn76lH;-96NI`_Oc5}3HKENdFI0f5LgZmZA9S@5W;kXzT_p*6?zSyf4VGJNLFQWLM)z4hQg22F5p;G(-Zc)bSI)9ueMC7<*Y2p}jv(Xyno*!Wc75r~nhKRnu3zN@uehkB4rG+5rqVWntKJt8p8uQt`abZ<h*s8IYJRTfr{o#@Dr^$ec!HSI(9?QhRad6Q<I9vz>_uNoPxiI&`am>=s|v*P4~W+p>IG`oKH6}5?wAz%QU>U{itn;n?xo*d$Nn{#n?k?Fc~KcKI&!Dv1o*4&856QJOZ7moM7#aZ$Ok(FF!SKnx(@;8-tKD#h^z?EKp#N*g^S?5Y&O?UtA9ZP?_;G99=^uU#M^%1BijtJAHH?AFyeZuknt8cHINLRl$`4JsCv3*l9UYNac`O}Y&o4>zKM7^d*&)CKN*BJo_8MOLKe|7!xAmXVH*4|pwUF!SZ1hc<RZfpNAbN=5~-mI>;4W*S~1hAoG9f#YcXaOt(PaLs9Wp(cunxqHkpBlcJDGaB<>7nI!X8$UmAB?IqQOmRE9@??Vdm>_3=L(((TLlm>8&1UxXw}U!E6kspvpyl#fTuO!G@F}7%1h!9ktCC!WA}dqFBXACl_3G+y+t4pHQreQk6r@?vCIKDq%^@=VE_bGvOY1as)B$9NYtcOogs2eMl()@GztX3qe_O*5Fpad#cr;$zPW=0#pkvxP=Jn>A_J!}pcmA-z4LrjUgvCWv8mipUn(dvqIaF+!_Zd#b5md418~9SyCb1#zqqz~*luk|?6Dym)$i(=$<%dcXZE>JRg!}f1y(7Pxws<}g2-d9e=&lht-;K>X+5(gl#Xbq>lWssCT{f)&L3_5a(}?2ZJjFqKPj%=K=Q#Zvj6}907*qoM6N<$f&'), ((37, 195, 97, 212), 'iBL{Q4GJ0x0000DNk~Le0000y0000H2mk;80HmdmMgRZ<gh@m}RCt^P!R=3#Wf%bP>$>jyexAeQIUHVwKxh!-sA#khNrkrFH2EMS!;Lo0mbpH(w%YnoYpu5af%@QwTGqx&SGF4J=ClvKP@zVJ882p}rkGHOz&Qt>m;1i1em`tx0ze{h5MY8#EHM#zvIK+*IPwuR2nzzB7LHIMp#TdYG5YCcK3P}W;v$fxg2mNqG=%1%at7ewiD03aj|Bjsy1@#x)+E4yhzOvy-O{tb2ZNN^^dXDhTvNTgV&sO7v(J5X$Ftb8ZD3ZC>$5=M?Y;%;PxT%7%OH~yK_sE_8~u>kR2M62U8;R;W8EhM@$QYBRw@c!+&0?O-t$I%0?IZve!s2_j7gCII!O>UFc;>FW_ew%YOh>8w?E$T*sw{jyzP+VmOXAV{<3n<@exgl**bo6NB!FsyLzJolhWLK=B(D_!u2ctMm=_)U37~<Ur<x^4h$Aq*gEg0lm6@Po1y*!8h_*ChZ=I9N8J~%;G7qiw@e6Vbmq6Cd)t3J@J#!`M3*h4s-);y6c#L7xYo5MdpX_w>ecDLOS<n-&B#&x^!TyTzz;^=no*#YGR1%GnZb&bsf^=7f3DTsKA}B9kdj?xcgMbHnVRod*Kz8X<D0!p`TA0?_Q6a(FUb{BpwY)io3clCu2%lL;i2Jd7Zsjdaafcv6~BD|3%O?}hW?xX=UVt(3$;HV^Rlk3CBJ@bR61tVWJ=GU-zg{0Kiu@qy(#KkF;xF`ci<3(++^!2c39H^{@h{;P@lUMW?uf`Tu?;Ip)#U@N-vCVx5Fx1F&LX%_khWbPZf?%dseJ}_^HZc@0}g%`t**^C@>d=rFMEEO`g;~GWv&4ysWYiV5T8grgN*Rqk+>t;1XS$@kk|^7q<U-SM*H!wFU%o&ZJ8`ft0V%u6<<#l7_maa9?&^FJ;V|-p?P+#>y9nR`zAhtg5Zve{)~OQvS1-+D-r|v7wMb2H@1i4}RBzt(ojX>+DRKO%S;-C(+vbPg9)j^e3*0(fRb2g^@^<iO97@7kuS+UcPRG$VOfYaD!zN16pLqsFfp|1i&n$lpu*qKx-5xqSz@>7%E~UK|}&<14I;2=v*SgfPg3j1O$TU5QRwz0Ehy|2q=sw0zd#72oL~6B0&KpazYG_Q3w&hYC+3JP?$&n!GZ!1K_m|U2TjkiuLJL&HUIzs07*qoM6N<$f&'))),
    ('REWARD_PANEL', (((127, 329, 248, 348), 'iBL{Q4GJ0x0000DNk~Le0001a0000J2mk;80FnOvsQ>^5DM>^@RCt_CmRoaF#}UW>|DHK#S9{e8-9SP@AP`1CFxZL+IC0{txGI%A<Rhi>q4JP~0uyiq#tAnG3v@vjgszB{wAwxAOm`kuGU>PJ>Y1MIneJcnFBE{m00J}xKpFr5gy2}{plYAiZ4(+mfq}+j9ok31+A1SJI$A>U%=FmMN9qAGAq_M!0#LSh0|s*dsYWw{GXp>nG&}N70SHn-{_I&9MD*wugm__ygqj*voWVfvvW5pjpd&j}9f_>kY6xK<Ggoak9gRc?IcXUSX{KZroEiX#6R0|&NpauU&X}RpiW{j@3IPLQu*fxGDYfU|5Y8EW$X|+;VDfT5|M~K!7}fp$hgol=5x6w|U0u>(6ynDIa<TraXB$pKe@)w=C2OkZqiM6`!nubH7k~h&o7m39Kh}kSv7HM+dF-cpSIH(;mZaVY@a9W#CUDK3!L2j9TMSV4<uU?33hCH{zm-Vt(F&RLUi#-)*WFXEnz7fe%RvZeKK=Wi%9s1|63U%v62wb~gSu{8nuw+v&I}+4H3S(x@%?b0_95@*4*DY>H(rku!OhDTcaZwAyal?Eyfb^ZUL6}RPtTPnTKgdUm4kQVCnpORPlf4hY1;yg$=F3TH#<DcA@o*mr?RxreJfU2HDBcL?h|+P2@Pu8zIQd+sj6y7RtsNNJ+=GHW5q8wJ}3#_TMd;6=LSDWsILr<eAjWgS$jXVLu98f|IpK4uelTXW`x#PZ)PI3u%}`S4_tpKE1Ju}XNB6co!CCNS020GNPtklAOoB^s08PoXmM{Uc!gxKlBr05Yd+TOo94hq;n91Sb*!wQR=g4|p9syYJlVmK*5BmMQ*$|Zce=iuSB8R8^B3{)&0_OUo%d1)v7n)~I#haf!_5dmg8>F+g~`r$&qgiUO`^i+i}j*6|NgZXH@99EGi0H8vhw8Q{Lsa>E|jkp%dMG4HgHw5>Al8=EUj*L(@f2zIeyv`p_DO1BR!iNhqX%S=D*a7`LU#S_n=z2@`@B3mmeg3dZC;yo@yPa-&zQTTOR&&DY)Q1`w(KNw(^tjR&(L$AI4ugr28uydw-mM*i&PD@6NZH9~~`pesMmxFyr0gTu!N7mBhF1U#mGi8{hxM?Wt6}J>B{y-Wj=W^Cr|F+OBd53ti<#*T}L;cjcwKb=gBknyV8tcK%1_U>Uv&|4!i+o`03R%^pn-jYw~PB*ateaVDB1S(avp2q4#Iaz=A`M%jlJ<-+wBFAsm4J#OXj{vg=<=<=goXIZYhx!ZngQ&3ytLjuO3SX}f(Qs`n?(u1|svfS6bo0BdcAB<XG-+$v?U5M6t=l5ze`>{gp^-@;p{?9@LGi4kZ$og;gUJ!Qb=F;<Mu5j(`d`{h9xs}BApH9lE4*c%T12rDCW)62IhbaytHt!6H1^u|0Zg2YShYf?@`^Rzw)pYO9j0P<X)Tf*4Yu)9R5imMu2IonYIH<ys^4Y4M8R{IIxp%03_Tfh<?+)JFPHyLr_Kzs{_xlXeZnJ{!8zppBI&$W14?YO10kuf1r!SW^9%Ku_pLzK-mQ~`^?S(gIJEHf`uh$p7QUD>v6fRl$tRI2YDrYOdUfCKgolp>^h1s)nbDJHv-Q6qScDyyWwpz*@*mgW{@ZZwF+eW$H0>r#x+ik6B`A|puR(8#V<VNCXpxgg`xp--HgLAEhfgcV9hI-<ukSFJgP669r*@>SmHdcqKLbc>0*XA4bft~5igYli&2-j+lM3kTbSlC@Vzp<VS$g)9N{3~K>(Zn&9G&LBFl~w}KB!s*<WORWB%dur}`6L(sgd;48AUKy903%IY0Kp(3Vn+0*TSve$xL_{Mr6CHfKsXO3j0`Ys2n_~<)d8a+Ag4?rmI+}@074JiMZ)M4sJ*E>hO-443}Q}=z`J9@8$_tqQpYp_jln~Vq$x!hj&SeP2m%Oj4n`=XJueu<jymxtF~DFr1|r*3q!?6a#`XwdW@Z!;acTrS6$Vm3v*Qc~98U&Nws~(n4(iCO;giw-Yw)w7wI_>Xy=4H9IXVi=@ITo<e!)@gJAwcJ002ovPDHLkV1f'), ((553, 329, 622, 348), 'iBL{Q4GJ0x0000DNk~Le0000*0000J2mk;80OK*A9{>OYZb?KzRCt_SlxuI5RS<>On)h~IdZSQUT0Ff_u;EfGatQ_0$S1z|1N>1Y`fp5(Kq40rO&bb`1+g530xi8jY0r7jyJz{~oL22*CwsD!S@X=wWb<nyXlR8Xhy)0tbqo*%3JyXLAPE3Ov2`<!0bwUZ-%bgc*e+`|XgxasnB3Yj1Y!YzgMb7Aka=8^A{pRDhbU1Z=`aVpjSI025OXILMTab~G=VD383(69lE<Z&1QeMovQhwSr`C1`QdHXMY8{SqBXwt)P4`+DJIeruvT=B%kq#g1AFOtVJs6sf8{?;l;B2$(I3gwL8eVM{qbC<DEbZLExq5T`!XJO8DZTUj%DtZRo;Njr_k4Z5dgthcc%S&>X`=tCh`#4DboO3p+TLvH^!&Xm-B*hfW?M&klGn?AW-Yn=)As`xZ>@#+)rrQ&#K%iD4jg-8+bnG;+17mKZoxvxvzPhCuhkEGlc?VYt^RuI=<Ss+3j3fwmdun-Z6bMpYdC&5GE++f|36VwEKfqVu<+4?!~0)lS0~SW_j8neH9Mbe?mu#)uk*%GwdT#Ky^H6nsV{6M7bjoLgx$VSJ~)22n9P>WKJOhc9Q*w5nyXY}y(8ZI<z3^@>y_&A@rSF(d*`yL;|KD!$B&ArwRiuj08rGCrKO58c-VI-DR8o1(ZoQQ-O4T$m7$wT;imW3)`lwYPtDB)8KPY*AfU~nqysW5?u@2L^1w82l-c5SovCaXqb5B%(INCz`cCK0XSH~jiXf(p6eW~wYp%ab_aCI=kM36@l%edo-B4=lmZW*Aay%d7R!p_mE^aFT6ck+0i-wC4jH-tmMZ=7pX9u4yWY>;XCT3pQoq9Ap`djzbt&K#9a~F%E#;jGdcQ@HB!ssJ|%`7?6k*?P2vwcaXzLDAC18<t$)sfM^ZXTHa^4Z3lmEG==&9}*=-g}-+cRrS}!LCDr3mxO>LM>kU;bi6bq5Ho-|Mc*~PkP?|xENksAFU>{OOXJ8-)_6Y(9yHJpD&g7hh>*~@@1L;MHWhWUUX?SDN`%D!rRj5P-V}%_QLQRZo@ds)Bz+a<2XbCR6;3|A;{ci3{a7jW`YMJgK^szQP#q;L@`A}EJS7kXa*99Aa_ClV>byvM9I|pyZ8?>-pumEB`{C`0000<MNUMnLSTX'))),
)

def _load_templates():
    return tuple((name, tuple((box, Image.open(BytesIO(b85decode(data))).convert("L"))
                             for box, data in regions)) for name, regions in REFERENCE)


TEMPLATES = _load_templates()


def _matches(image, box, template):
    # Test nearby translations to tolerate fractional DPI rounding.
    x, y, right, bottom = box
    for dx in (0, -1, 1, -2, 2, -3, 3):
        for dy in (0, -1, 1, -2, 2, -3, 3):
            patch = image.crop((x + dx, y + dy, right + dx, bottom + dy))
            if ImageStat.Stat(ImageChops.difference(template, patch)).mean[0] <= 22:
                return True
    return False


def classify(frame):
    with Image.open(BytesIO(frame)) as source:
        if abs(source.width / source.height - 16 / 9) > 0.05:
            return "UNKNOWN"
        image = source.convert("RGB").resize((800, 448), Image.Resampling.LANCZOS).convert("L")
    for name, regions in TEMPLATES:
        if all(_matches(image, box, template) for box, template in regions):
            return name
    return "UNKNOWN"
