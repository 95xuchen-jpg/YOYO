import unittest
from unittest.mock import Mock

import numpy as np

from duo_run import Run
from duo_vision import Action
from duo_windows import run_queue


class PublicQueueTests(unittest.TestCase):
    def setUp(self):
        self.run=Run('水果剧团')
        self.frames=[np.zeros((448,800,3),np.uint8)]*2

    def test_default_public_and_previously_private(self):
        run=self.run
        run.sent(0,Action('创建房间'),None,0)
        self.assertEqual(run.propose(0,self.frames,['private_settings','list'],2).name,'改为公开房间')
        run.vision.find=Mock(return_value=(462,311))
        confirm=run.propose(0,self.frames,['public_settings','list'],4)
        self.assertEqual(confirm.name,'确认创建公开房')
        run.sent(0,confirm,None,4)
        self.assertTrue(run.public_confirmed)

    def test_unexpected_private_prompt_stops(self):
        with self.assertRaisesRegex(ValueError,'私房'):
            self.run.propose(1,self.frames,['room','join_pin'],5)

    def test_order_and_rounds(self):
        runner=Mock(return_value='both_returned_after_settlement')
        self.assertEqual(run_queue(['水果剧团','勇闯火焰山'],2,runner,lambda:False),'queue_complete')
        self.assertEqual([c.args for c in runner.call_args_list],[
            ('水果剧团',1,4),('勇闯火焰山',2,4),('水果剧团',3,4),('勇闯火焰山',4,4)])

    def test_partial_or_interrupted_result_stops_queue(self):
        runner=Mock(return_value='stopped')
        self.assertEqual(run_queue(['水果剧团','勇闯火焰山'],2,runner,lambda:False),'stopped')
        self.assertEqual(runner.call_count,1)
        runner.reset_mock()
        self.assertEqual(run_queue(['水果剧团'],1,runner,lambda:True),'stopped')
        runner.assert_not_called()

    def test_failure_shows_item_and_does_not_launch_next(self):
        runner=Mock(side_effect=ValueError('窗口被遮挡'))
        with self.assertRaisesRegex(ValueError,'1/2 · 水果剧团'):
            run_queue(['水果剧团','勇闯火焰山'],1,runner,lambda:False)
        self.assertEqual(runner.call_count,1)
