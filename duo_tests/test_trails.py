import unittest
import numpy as np

from duo_run import Run
from duo_trail import NAMES


class RecordedRoutes(unittest.TestCase):
    def test_profiles_and_waypoint_bounds(self):
        for name in NAMES:
            run=Run(name)
            trail=run.vision.trail
            self.assertEqual(len(trail.routes),2)
            for i,route in enumerate(trail.routes):
                self.assertTrue(route)
                for x,y,kind,_ in route:
                    self.assertGreater(min(x,y),0)
                    self.assertIn(kind,('walk','fight','visit'))
                if trail.party_at:self.assertLessEqual(trail.party_at[i],len(route))
                if trail.patrol:
                    lo,hi=trail.patrol[i]
                    self.assertTrue(0<=lo<hi<=len(route))

    def test_fire_needs_kills_and_both_positions_to_invite(self):
        run=Run('勇闯火焰山')
        for r,n in zip(run.roles,run.vision.trail.party_at):
            r.index=n
            r.entered=True
        self.assertFalse(run.party_ready())
        run.kills_done=True
        self.assertTrue(run.party_ready())
        run.roles[1].index-=1
        self.assertFalse(run.party_ready())

    def test_follower_does_not_issue_movement(self):
        run=Run('拯救蓝星人')
        run.started=run.in_party=True
        run.roles[1].entered=True
        frames=[np.zeros((448,800,3),np.uint8)]*2
        self.assertIsNone(run.propose(1,frames,['field','field'],123))

    def test_unknown_position_does_not_click_map(self):
        run=Run('侏罗纪牧场')
        run.started=run.roles[0].entered=True
        frames=[np.zeros((448,800,3),np.uint8)]*2
        self.assertIsNone(run.propose(0,frames,['map','field'],123))
