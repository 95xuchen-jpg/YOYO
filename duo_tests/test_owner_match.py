import unittest

import cv2
import numpy as np

from duo_run import Run


class OwnerMatchTests(unittest.TestCase):
    def setUp(self):
        self.run = Run('水果剧团')
        self.host = np.full((448, 800, 3), (175, 125, 85), np.uint8)
        self.guest = np.full((448, 800, 3), 237, np.uint8)
        for key in ('owner_badge', 'host_start_label', 'emptyrow', 'room'):
            box, pattern = self.run.vision.patterns[key]
            x, y, u, v = box
            self.host[y:v, x:u] = pattern
        cv2.putText(self.host, 'M2K85', (348, 163), cv2.FONT_HERSHEY_SIMPLEX,
                    .48, (255, 255, 255), 1, cv2.LINE_AA)

    def row(self, y, owner, public=True):
        for key, x in [('fruit_rowname', 355), ('plus', 658), ('public_type_compact', 207)]:
            if not public and key == 'public_type_compact':
                continue
            _, template = self.run.vision.patterns[key]
            h, w = template.shape[:2]
            top, left = y-h//2, x-w//2
            self.guest[top:top+h, left:left+w] = template
        cv2.putText(self.guest, owner, (485, y+5), cv2.FONT_HERSHEY_SIMPLEX,
                    .48, (68, 68, 68), 1, cv2.LINE_AA)

    def propose(self, now):
        return self.run.propose(1, [self.host, self.guest], ['room', 'list'], now)

    def test_already_open_and_owner_on_second_row(self):
        self.row(134, 'M2K8X')
        self.row(173, 'M2K85')
        action = self.propose(1)
        self.assertEqual((action.name, action.point), ('加入主号公开房', (658, 173)))

    def test_similar_name_or_private_row_is_skipped(self):
        self.row(134, 'M2K8X')
        self.row(173, 'M2K85', public=False)
        self.assertIsNone(self.propose(1))

    def test_duplicate_owner_is_ambiguous(self):
        self.row(134, 'M2K85')
        self.row(212, 'M2K85')
        self.assertIsNone(self.propose(1))

    def test_retry_rechecks_name_and_position(self):
        self.row(134, 'M2K85')
        action = self.propose(1)
        self.run.sent(1, action, None, 1)
        self.assertIsNone(self.propose(2))
        self.guest.fill(237)
        self.row(134, 'M2K8X')
        self.row(212, 'M2K85')
        for now in (6, 11):
            retry = self.propose(now)
            self.assertEqual(retry.point, (658, 212))
            self.run.sent(1, retry, None, now)
        with self.assertRaisesRegex(ValueError, '三次'):
            self.propose(16)
