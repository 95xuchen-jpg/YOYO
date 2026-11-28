"""One public two-character PvE run, driven by visible game screens."""
from dataclasses import dataclass, field
from math import dist
import time

from duo_trail import party_visible, same_portrait
from duo_vision import Action, Vision, matching_rosters
from duo_lobby import card_label, catalog_view


@dataclass
class Role:
    index: int = 0
    routed: bool = False
    targeted: bool = False
    fought: bool = False
    entered: bool = False
    settled: bool = False
    returned: bool = False
    close_to_goal: bool = False
    last_walk: float = -100
    intermediates: set = field(default_factory=set)
    last_action: str = ''
    attempts: int = 0
    last_time: float = -100
    scene: str = ''
    since: float = 0

    def advance(self):
        self.close_to_goal = False
        self.index += 1
        self.routed = self.targeted = self.fought = False
        self.intermediates.clear()


class Run:
    def __init__(self, dungeon):
        self.vision = Vision(dungeon)
        self.roles = [Role(), Role()]
        self.host_created = self.join_selected = self.started = False
        self.swipe_before = None
        self.swipe_back = False
        self.catalog_image = None
        self.public_confirmed = False
        self.slime_boss = False
        self.invited = self.accepted = self.in_party = self.kills_done = False

    def observe(self, images, scenes, now):
        for i, (r, sc, im) in enumerate(zip(self.roles, scenes, images)):
            if i==0 and not self.started and sc=='catalog':
                self.catalog_image=catalog_view(im)
            if sc != r.scene:
                r.scene, r.since = sc, now
                r.last_action, r.attempts = '', 0
            if self.started and sc in ('field','map','battle'):
                r.entered = True
            tr=self.vision.trail
            if tr and self.started and r.entered:
                if tr.counter is not None and not self.kills_done and sc in ('field','map','battle'):
                    self.kills_done=bool(self.vision.find(im,'quest_finished',threshold=.82) or
                        self.vision.find(im,'quest_heading',threshold=.72) and tr.counter_state(im)=='complete')
                if self.accepted and tr.party_at and party_visible(im):
                    self.in_party=True
                if sc in ('field','map') and r.index<len(tr.routes[i]):
                    gx,gy,kind,_=tr.routes[i][r.index]
                    pos=tr.ocr.read(im,sc=='map')
                    if pos:r.close_to_goal=kind!='walk' and dist(pos,(gx,gy))<=330
            if sc == 'battle' and (r.targeted or (tr and r.close_to_goal) or
                                   (not tr and r.routed and self.vision.key != 'clip7')):
                r.fought = True
            if r.fought and sc in ('field','map'):
                r.advance()
            if self.started and r.entered and sc == 'settle':
                r.settled = True
            if r.settled and sc == 'port':
                r.returned = True
            if (self.vision.key == 'clip7' and r.entered and not self.slime_boss
                and sc in ('map','field','battle') and self.vision.find(im,'slime_ready')):
                self.slime_boss = True
                for player in self.roles:
                    player.index = 2
                    player.routed = player.targeted = player.fought = False
                    player.intermediates.clear()

    def party_ready(self):
        at=self.vision.trail.party_at
        return at is not None and (self.vision.trail.patrol is None or self.kills_done) and all(r.entered and r.index>=n for r,n in zip(self.roles,at))

    def party_action(self,i,images,scenes):
        v=self.vision
        im=images[i]
        if i==1:
            if (self.invited and scenes[i] in ('map','field') and v.find(im,'party_deny')
                and v.find(im,'party_confirm') and same_portrait(im[187:215,45:74],images[0])):
                return Action('接受主号邀请',v.find(im,'party_confirm'))
            return None
        if scenes[0]=='party_panel':
            if self.in_party:
                return Action('关闭邀请列表',v.find(im,'party_close')) if v.find(im,'party_close') else None
            button=v.find(im,'party_send') or v.find(im,'invite_plain',threshold=.75)
            second=(v.find(im,'party_send',(444,168,520,204)) or
                    v.find(im,'invite_plain',(444,168,520,204),.75))
            if not self.invited and button and not second and same_portrait(im[125:154,299:329],images[1]):
                return Action('邀请已绑定的副号',button)
            return None
        if self.in_party:return None
        if scenes[0]=='map':return Action('收起地图',(781,114))
        if scenes[0]!='field' or self.invited:return None
        invite=v.find(im,'party_open')
        if invite:return Action('打开组队邀请',invite)
        tab=v.find(im,'party_tab',threshold=.72)
        return Action('打开队伍页签',tab) if tab else None

    def trail_action(self,i,images,scenes,now):
        v=self.vision
        tr=v.trail
        r=self.roles[i];im=images[i];sc=scenes[i]
        gate=tr.party_at
        if (sc=='party_panel' and self.in_party) or (self.party_ready() and not self.in_party):
            return self.party_action(i,images,scenes)
        if sc not in ('field','map') or not r.entered:return None
        if gate is not None and not self.in_party and r.index>=gate[i]:
            # The other role can still be clearing its kill objective.
            if not tr.patrol or self.kills_done or i==0:return None
        if i==1 and self.in_party:return None
        if tr.patrol and not self.kills_done:
            lo,hi=tr.patrol[i]
            if r.index>=hi:
                # A hidden quest tracker cannot confirm that the kill gate has opened.
                if tr.counter_state(im) is None and v.find(im,'party_open'):
                    return Action('查看过关条件',(20,163))
                return Action('重复清怪巡逻'),lo
        if r.index>=len(v.route[i]):return None
        gx,gy,kind,_=v.route[i][r.index]
        pos=tr.ocr.read(im,sc=='map')
        if pos is None:return None
        distance=dist(pos,(gx,gy))
        if distance<= (155 if kind=='walk' else 205):
            if kind=='walk':return Action('已到路线坐标'),r.index
            if sc=='map':return Action('收起地图',(781,114))
            if kind=='visit' and r.targeted and now-r.last_time>3:return Action('已到路线坐标'),r.index
            if not r.targeted or now-r.last_time>=4:
                point=v.npc(im,i,r.index)
                if point:return Action('与目标交互',point)
                if kind=='visit':return Action('已到路线坐标'),r.index
            return None
        if now-r.last_walk<2:return None
        if sc=='field':
            return Action('展开副本地图',(737,54))
        p=tr.destination(im,pos,(gx,gy))
        if p:return Action('按当前坐标寻路',p),r.index
        return None

    def catalog_action(self,im,now):
        role=self.roles[0]
        if now-role.last_time<1.0:return None
        pattern=self.vision.patterns[self.vision.key+'_detailname'][1]
        point=card_label(im,pattern)
        if point:return Action('选择队列副本',point)
        reverse=self.swipe_back
        if self.swipe_before is not None and abs(catalog_view(im)-self.swipe_before).mean()<4:
            if reverse:
                raise ValueError('已查看副本目录，未找到所选副本，请检查开放条件。')
            reverse=True
        return Action('向前翻副本目录',(240,268)) if reverse else Action('向后翻副本目录',(613,268))

    def propose(self, i, images, scenes, now):
        v, r, im, sc = self.vision, self.roles[i], images[i], scenes[i]
        if r.returned:
            return None
        if not self.started:
            if i == 0 and sc == 'detail' and not self.host_created:
                return Action('创建房间',(605,402))
            if i==0 and self.host_created and sc=='private_settings':
                return Action('改为公开房间',(386,205))
            if i==0 and self.host_created and sc=='public_settings' and not self.public_confirmed:
                ok=v.find(im,'orange_ok')
                if ok:return Action('确认创建公开房',ok)
            if sc=='port':
                button=v.find(im,'port_daily',threshold=.72) or v.find(im,'dailybutton',threshold=.72)
                return Action('打开日常',button) if button else None
            if sc=='daily':
                return Action('打开副本目录',(750,165))
            if i==0 and sc=='list' and not self.host_created:
                return Action('打开副本资讯',(83,99))
            if i==0 and sc=='other_detail' and not self.host_created and now-r.since>=2:
                if v.find(im,v.key+'_detailname'):
                    raise ValueError('所选副本的创建按钮不可用，请检查入场次数和条件。')
                close=v.find(im,'detail_close')
                return Action('返回副本目录',close) if close else None
            if i==0 and sc=='catalog' and not self.host_created:
                return self.catalog_action(im,now)
            if i==1 and sc=='join_pin':
                raise ValueError('副号出现了私房密码框，队列已停止。')
            if i == 1:
                if sc == 'catalog':
                    return Action('打开房间列表',(82,140))
                if sc == 'list' and scenes[0] == 'room' and self.public_confirmed and not self.join_selected:
                    row = v.room_row(im,images[0])
                    if row:
                        return Action('加入主号公开房',row)
                    if now-r.since>5:
                        return Action('刷新房间列表',(220,402))
            if (i==0 and scenes==['room','room'] and self.public_confirmed and self.join_selected
                and v.find(im,'host_kick') and v.find(images[1],'guest')
                and v.find(im,'third_empty') and v.find(images[1],'third_empty')
                and v.find(im,'empty4') and v.find(images[1],'empty4')
                and matching_rosters(images)):
                return Action('双号到齐，开始挑战',(462,367))
            return None
        if sc=='idle' and r.entered:
            return Action('解除游戏省电模式',(380,225))
        if sc=='settle' and r.settled:
            return Action('前往领奖', v.find(im,'reward') or (v.find(im,'reward_alt',threshold=.65) if v.trail else None) or (586,337))
        if sc=='dialog' and r.entered:
            return Action('继续副本对话',v.find(im,'skip'))
        if v.trail:return self.trail_action(i,images,scenes,now)
        if sc not in ('field','map') or not r.entered:
            return None
        route=v.route[i]
        if r.index >= len(route):
            return None
        if sc=='field':
            if not r.routed and now-r.last_walk>=2 and not v.find(im,'walking'):
                return Action('展开副本地图',(737,54))
            if r.routed and now-r.last_walk>1.2 and (not r.targeted or now-r.last_time>4):
                npc = v.npc(im,i,r.index)
                if npc and (v.key!='clip7' or self.slime_boss):
                    return Action('与目标交互',npc)
            if r.routed and now-r.last_walk>8 and not v.find(im,'walking'):
                if v.key=='clip7' and not self.slime_boss:
                    return Action('切换巡逻路点')
                if not r.targeted and now-r.last_walk>15:
                    return Action('重新定位目标')
            return None
        if r.routed or now-r.last_walk<1.7:
            return Action('收起地图',(781,114))
        return v.destination(im, route[r.index], r.intermediates)

    def sent(self, i, action, intermediate, now):
        r=self.roles[i]
        key=action.name
        if key=='创建房间': self.host_created=True
        elif key=='加入主号公开房': self.join_selected=True
        elif key=='确认创建公开房':self.public_confirmed=True
        elif key in ('向后翻副本目录','向前翻副本目录'):
            self.swipe_before=self.catalog_image
            self.swipe_back=key=='向前翻副本目录'
        elif key=='双号到齐，开始挑战': self.started=True
        elif key=='邀请已绑定的副号': self.invited=True
        elif key=='接受主号邀请': self.accepted=True
        elif key=='按当前坐标寻路': r.last_walk=now
        elif key=='已到路线坐标': r.advance()
        elif key=='重复清怪巡逻':
            r.index=intermediate
            r.targeted=r.fought=r.close_to_goal=False
        elif key=='前往目标': r.routed=True; r.last_walk=now
        elif key=='途经地图路点': r.intermediates.add(intermediate); r.last_walk=now
        elif key=='与目标交互': r.targeted=True
        elif key=='切换巡逻路点':
            r.index=1-r.index
            r.routed=False
            r.intermediates.clear()
        elif key=='重新定位目标':
            r.routed=False
            r.intermediates.clear()
        r.attempts = r.attempts+1 if r.last_action==key else 1
        r.last_action, r.last_time = key, now


def unpack(proposal):
    return proposal if isinstance(proposal,tuple) else (proposal,None)


def drive(run, capture, send, stopped, wait, log, *, duration=None, clock=time.monotonic):
    if duration is None:duration=1850 if run.vision.key in ('dark','ghost') else 1250
    started=clock()
    last_progress=[started, started]
    signatures=[None,None]
    turn=0
    while not stopped():
        now=clock()
        if now-started >= duration:
            raise ValueError('本轮超过时限')
        images=capture()
        scenes=[run.vision.scene(im) for im in images]
        run.observe(images,scenes,now)
        for i,r in enumerate(run.roles):
            sig=(scenes[i],r.index,r.settled,r.returned)
            if signatures[i]!=sig:
                log(i,scenes[i],r.index+1)
                signatures[i]=sig
                last_progress[i]=now
            waiting=run.vision.trail and (r.entered and i==1 and run.in_party or
                r.entered and run.vision.trail.party_at and not run.in_party and
                r.index>=run.vision.trail.party_at[i] and not run.party_ready())
            if not waiting and not r.returned and not (r.entered and r.index>=len(run.vision.route[i])):
                if now-last_progress[i] > (360 if scenes[i]=='battle' else 85):
                    raise ValueError(f'{"主号" if i==0 else "副号"}长时间未推进：{scenes[i]}，路线第 {r.index+1} 段')
        if all(r.returned for r in run.roles):
            return 'both_returned_after_settlement'
        for i in (turn,1-turn):
            r=run.roles[i]
            action,step=unpack(run.propose(i,images,scenes,now))
            if not action or now-r.last_time<.6:
                continue
            if action.name==r.last_action:
                if r.attempts>=3 and action.name not in ('刷新房间列表','已到路线坐标','按当前坐标寻路','向前翻副本目录','向后翻副本目录'):
                    raise ValueError('同一步骤未生效：'+action.name)
                if now-r.last_time<(5 if action.name=='刷新房间列表' else 2):
                    continue
            fresh=capture()
            current=[run.vision.scene(im) for im in fresh]
            if current!=scenes:
                break
            second,second_step=unpack(run.propose(i,fresh,current,clock()))
            if (not second or second.name!=action.name or step!=second_step or
                dist(second.point,action.point)>5 or stopped()):
                break
            if second.name not in ('切换巡逻路点','重新定位目标','已到路线坐标','重复清怪巡逻'):
                send(i,second)
            run.sent(i,second,step,clock())
            log(i,second.name,r.index+1)
            turn=1-i
            break
        wait(.12)
    return 'stopped'
