"""One private two-character PvE run, driven by visible game screens."""
from dataclasses import dataclass, field
from math import dist
import time

from duo_vision import Action, Vision, matching_rosters


@dataclass
class Role:
    index: int = 0
    pin_filled: bool = False
    routed: bool = False
    targeted: bool = False
    fought: bool = False
    entered: bool = False
    settled: bool = False
    returned: bool = False
    last_walk: float = -100
    intermediates: set = field(default_factory=set)
    last_action: str = ''
    attempts: int = 0
    last_time: float = -100
    scene: str = ''
    since: float = 0

    def advance(self):
        self.index += 1
        self.routed = self.targeted = self.fought = False
        self.intermediates.clear()


class Run:
    def __init__(self, dungeon):
        self.vision = Vision(dungeon)
        self.roles = [Role(), Role()]
        self.host_created = self.join_selected = self.started = False
        self.slime_boss = False

    def observe(self, images, scenes, now):
        for i, (r, sc, im) in enumerate(zip(self.roles, scenes, images)):
            if sc != r.scene:
                r.scene, r.since = sc, now
                r.last_action, r.attempts = '', 0
            if self.started and sc in ('field','map','battle'):
                r.entered = True
            if sc == 'battle' and (r.targeted or (r.routed and self.vision.key != 'clip7')):
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

    def propose(self, i, images, scenes, now):
        v, r, im, sc = self.vision, self.roles[i], images[i], scenes[i]
        if r.returned:
            return None
        if not self.started:
            if i == 0 and sc == 'detail' and not self.host_created:
                return Action('创建房间',(605,402))
            if i == 0 and sc == 'settings' and self.host_created:
                return Action('选择私人房间',(467,205))
            allowed_pin = (i==0 and sc=='create_pin' and self.host_created
                           or i==1 and sc=='join_pin' and self.join_selected)
            if allowed_pin:
                if not r.pin_filled:
                    return Action('填写房间密码', (444,244) if i==0 else (440,248))
                ok = v.find(im, 'orange_ok')
                return Action('确认私人房间',ok) if ok else None
            if i == 1:
                if sc == 'daily':
                    return Action('打开副本目录',(750,165))
                if sc == 'catalog':
                    return Action('打开房间列表',(82,140))
                if sc == 'list' and scenes[0] == 'room' and self.host_created and not self.join_selected:
                    row = v.room_row(im)
                    if row:
                        return Action('加入私人房间',row)
                    if now-r.since>5:
                        return Action('刷新房间列表',(220,402))
            if (i==0 and scenes==['room','room'] and self.host_created and self.join_selected
                and v.find(im,'host_kick') and v.find(images[1],'guest')
                and v.find(im,'third_empty') and v.find(images[1],'third_empty')
                and matching_rosters(images)):
                return Action('双号到齐，开始挑战',(462,367))
            return None
        if sc=='settle' and r.settled:
            return Action('前往领奖', v.find(im,'reward'))
        if sc=='dialog' and r.entered:
            return Action('继续副本对话',v.find(im,'skip'))
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
        elif key=='加入私人房间': self.join_selected=True
        elif key=='填写房间密码': r.pin_filled=True
        elif key=='双号到齐，开始挑战': self.started=True
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


def drive(run, capture, send, stopped, wait, log, *, duration=1250, clock=time.monotonic):
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
            if not r.returned and not (r.entered and r.index>=len(run.vision.route[i])):
                if now-last_progress[i] > (240 if scenes[i]=='battle' else 85):
                    raise ValueError(f'{"主号" if i==0 else "副号"}长时间未推进：{scenes[i]}，路线第 {r.index+1} 段')
        if all(r.returned for r in run.roles):
            return 'both_returned_after_settlement'
        for i in (turn,1-turn):
            r=run.roles[i]
            action,step=unpack(run.propose(i,images,scenes,now))
            if not action or now-r.last_time<.6:
                continue
            if action.name==r.last_action:
                if r.attempts>=3 and action.name!='刷新房间列表':
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
            if second.name not in ('切换巡逻路点','重新定位目标'):
                send(i,second)
            run.sent(i,second,step,clock())
            log(i,second.name,r.index+1)
            turn=1-i
            break
        wait(.12)
    return 'stopped'
