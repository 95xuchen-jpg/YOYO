"""Explicit, fail-closed startup reconciliation; never automatically replay an action."""
from dataclasses import dataclass
import math
from core import Task

@dataclass(frozen=True)
class RecoveryReport:
    restored: tuple
    paused: tuple
    expired: tuple


def recover_queued(journal, coordinator, clock):
    """Rehydrate only untouched queued tasks; pause interrupted/expired tasks.

    Call with a fresh coordinator/queue and journal after restart. A queued task
    is safe to requeue because it was never marked active, but it still needs
    visual preflight before any game action. A paused task needs manual review.
    """
    if coordinator.journal is not journal:
        raise ValueError('journal mismatch')
    if coordinator.queue._active is not None or coordinator._keys:
        raise RuntimeError('recovery requires an empty coordinator')
    rows = journal.db.execute('SELECT task_id,account,name,state,attempts,deadline FROM tasks ORDER BY updated,task_id').fetchall()
    restored, paused, expired = [], [], []
    now = float(clock())
    for key, account, name, state, attempts, deadline in rows:
        if state == 'paused':
            paused.append(key)
        elif state == 'queued':
            if not math.isfinite(deadline) or now >= deadline:
                journal.timeout_queued(key)
                expired.append(key)
            elif attempts != 0:
                # An allegedly untouched task with attempts is ambiguous.
                journal.pause_queued(key)
                paused.append(key)
            else:
                task = Task(account, name, deadline)
                coordinator._keys[id(task)] = key
                coordinator.queue.submit(task)
                restored.append(key)
    return RecoveryReport(tuple(restored), tuple(paused), tuple(expired))
