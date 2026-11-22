import tempfile
import unittest
from pathlib import Path
from account_roles import id_in_title, load_ids, resolve_roles, save_ids


class RoleTests(unittest.TestCase):
    def test_order_and_leading_zeros(self):
        self.assertEqual(resolve_roles([('007', 20), ('42', 10)], '42'), (10,20,'007'))
        for ids, main in [(['1','1'],'1'), (['','2'],'2'), (['1','2'],'3')]:
            with self.assertRaises(ValueError):
                resolve_roles(list(zip(ids,[10,20])), main)

    def test_titles(self):
        ids = ['23','123']
        self.assertEqual(id_in_title('游戏 [123]', ids),'123')
        self.assertEqual(id_in_title('游戏', ids),'')
        self.assertEqual(id_in_title('游戏 123 23', ids),'')

    def test_preferences(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)/'prefs.json'
            self.assertEqual(load_ids(path), ([], ''))
            save_ids(path, ['02','1'], '1')
            self.assertEqual(load_ids(path), (['02','1'], '1'))
