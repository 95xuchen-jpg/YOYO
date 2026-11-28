import unittest
from unittest.mock import Mock
import numpy as np
from duo_run import Run
from duo_vision import DUNGEONS, map_origin, matching_rosters


class FilmRouteTests(unittest.TestCase):
    def setUp(self):
        self.run = Run('水果剧团')
        self.blank = np.zeros((448,800,3), np.uint8)
        self.pair = [self.blank,self.blank]

    def test_blank_window_never_produces_input_or_route_position(self):
        for name in DUNGEONS:
            controller = Run(name)
            self.assertEqual(controller.vision.scene(self.blank), 'unknown')
            self.assertIsNone(controller.propose(0,self.pair,['unknown','unknown'],5))
            self.assertIsNone(map_origin(controller.vision.atlas,self.blank))
            self.assertFalse(matching_rosters(self.pair))

    def test_both_roles_must_enter_then_settle_before_return(self):
        ctl=self.run
        ctl.started=True
        ctl.observe(self.pair,['settle','port'],0)
        self.assertFalse(any(r.returned or r.settled for r in ctl.roles))
        for i,scenes in enumerate([['field','field'],['battle','map'],['settle','battle'],
                                   ['port','battle'],['port','settle'],['port','port']]):
            ctl.observe(self.pair,scenes,i+1)
            self.assertEqual(all(r.returned for r in ctl.roles),i==5)

    def test_incidental_battle_does_not_consume_slime_boss(self):
        ctl=Run('史莱姆居地')
        ctl.started=True
        ctl.roles[0].routed=True
        ctl.observe(self.pair,['battle','field'],1)
        ctl.observe(self.pair,['map','battle'],2)
        self.assertEqual(ctl.roles[0].index,0)

    def test_role_advances_independently_after_interaction_and_fight(self):
        ctl=self.run
        ctl.started=True
        ctl.roles[1].targeted=True
        ctl.observe(self.pair,['map','battle'],1)
        ctl.observe(self.pair,['battle','field'],2)
        self.assertEqual([r.index for r in ctl.roles],[0,1])

    def test_guest_cannot_join_before_selected_host_room(self):
        ctl=self.run
        ctl.vision.room_row=Mock(return_value=(656,173))
        self.assertIsNone(ctl.propose(1,self.pair,['detail','list'],1))
        self.assertIsNone(ctl.propose(1,self.pair,['room','list'],1))
        ctl.host_created=True
        self.assertIsNone(ctl.propose(1,self.pair,['room','list'],1))
        ctl.public_confirmed=True
        self.assertEqual(ctl.propose(1,self.pair,['room','list'],1).name,'加入主号公开房')
