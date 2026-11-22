"""User-confirmed in-game IDs; persisted preferences contain no window handles."""
import json
import os
import tempfile
from pathlib import Path
import re


def resolve_roles(rows, main_id):
    ids = [value.strip() for value, _ in rows]
    if len(ids) != 2 or not all(ids) or ids[0] == ids[1]:
        raise ValueError('请为两个窗口分别填写不同的游戏 ID。')
    if main_id not in ids:
        raise ValueError('请选择本次两个 ID 中的一个作为主号。')
    index = ids.index(main_id)
    return rows[index][1], rows[1 - index][1], ids[1 - index]


def id_in_title(title, ids):
    hits = [value for value in ids if re.search(r'(?<![A-Za-z0-9_])' + re.escape(value)
                                                + r'(?![A-Za-z0-9_])', title)]
    return hits[0] if len(hits) == 1 else ''


def load_ids(path):
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        values = data['ids']
        if (isinstance(values, list) and len(values) == 2 and
                all(isinstance(x, str) and x.strip() == x and x for x in values)
                and values[0] != values[1] and data['main'] in values):
            return values, data['main']
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return [], ''


def save_ids(path, ids, main):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                     delete=False) as out:
        temp = Path(out.name)
        try:
            json.dump({'ids': ids, 'main': main}, out, ensure_ascii=False)
            out.close()
            os.replace(temp, path)
        finally:
            out.close()
            temp.unlink(missing_ok=True)
