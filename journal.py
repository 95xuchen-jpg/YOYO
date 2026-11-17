"""Durable, fail-closed task journal; does not interact with a game.

SQLite transactions make state transitions atomic. A process restart never assumes
an interrupted action completed and never silently retries it.
"""
import sqlite3
import time
from pathlib import Path

STATES = {'queued', 'active', 'verified', 'paused', 'timed_out'}

class TaskJournal:
    def __init__(self, path, clock=time.time):
        self.clock = clock
        self.path = str(Path(path))
        self.db = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        self.db.execute('PRAGMA busy_timeout=5000')
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.execute('''CREATE TABLE IF NOT EXISTS tasks (
            task_id TEXT PRIMARY KEY, account TEXT NOT NULL, name TEXT NOT NULL,
            state TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
            deadline REAL NOT NULL, updated REAL NOT NULL)''')
        self.db.execute('''CREATE TABLE IF NOT EXISTS events (
            seq INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT NOT NULL,
            old_state TEXT, new_state TEXT NOT NULL, at REAL NOT NULL)''')
        # Interrupted tasks require manual state reconciliation, not replay.
        with self.db:
            for (task_id,) in self.db.execute("SELECT task_id FROM tasks WHERE state='active'").fetchall():
                self._transition(task_id, 'active', 'paused')

    def _transition(self, task_id, old, new):
        if new not in STATES:
            raise ValueError('invalid state')
        cur = self.db.execute('UPDATE tasks SET state=?, updated=? WHERE task_id=? AND state=?',
                              (new, self.clock(), task_id, old))
        if cur.rowcount != 1:
            raise RuntimeError('unexpected task state')
        self.db.execute('INSERT INTO events(task_id,old_state,new_state,at) VALUES(?,?,?,?)',
                        (task_id, old, new, self.clock()))

    def enqueue(self, task_id, account, name, deadline):
        if not all(isinstance(v, str) and v.strip() for v in (task_id, account, name)):
            raise ValueError('missing task identity')
        with self.db:
            existing = self.db.execute('SELECT account,name,deadline FROM tasks WHERE task_id=?', (task_id,)).fetchone()
            if existing:
                if existing != (account, name, float(deadline)):
                    raise ValueError('idempotency key collision')
                return False
            self.db.execute('INSERT INTO tasks VALUES(?,?,?,?,?,?,?)',
                            (task_id, account, name, 'queued', 0, float(deadline), self.clock()))
            self.db.execute('INSERT INTO events(task_id,old_state,new_state,at) VALUES(?,?,?,?)',
                            (task_id, None, 'queued', self.clock()))
            return True

    def start(self, task_id):
        with self.db:
            task = self.get(task_id)
            if task is None or task['state'] != 'queued':
                raise RuntimeError('not queued')
            if self.clock() >= task['deadline']:
                self._transition(task_id, 'queued', 'timed_out')
                return False
            # At most one active task globally, including across accounts.
            if self.db.execute("SELECT 1 FROM tasks WHERE state='active' LIMIT 1").fetchone():
                raise RuntimeError('foreground lease occupied')
            self._transition(task_id, 'queued', 'active')
            self.db.execute('UPDATE tasks SET attempts=attempts+1 WHERE task_id=?', (task_id,))
            return True

    def complete(self, task_id, verified):
        with self.db:
            task = self.get(task_id)
            if task is None or task['state'] != 'active':
                raise RuntimeError('not active')
            new_state = 'verified' if verified and self.clock() < task['deadline'] else 'paused'
            self._transition(task_id, 'active', new_state)
            return new_state

    def timeout_active(self, task_id):
        with self.db:
            self._transition(task_id, 'active', 'timed_out')

    def timeout_queued(self, task_id):
        with self.db:
            self._transition(task_id, 'queued', 'timed_out')

    def pause_queued(self, task_id):
        with self.db:
            self._transition(task_id, 'queued', 'paused')

    def get(self, task_id):
        row = self.db.execute('SELECT task_id,account,name,state,attempts,deadline FROM tasks WHERE task_id=?',
                              (task_id,)).fetchone()
        return dict(zip(('task_id','account','name','state','attempts','deadline'), row)) if row else None

    def close(self):
        self.db.close()
