"""Fail-closed synchronization of the queue and durable task journal (offline prototype)."""

class DurableCoordinator:
    def __init__(self, queue, journal):
        self.queue = queue
        self.journal = journal
        self._keys = {}
        self.blocked = False

    def _ensure_ready(self):
        if self.blocked:
            raise RuntimeError("journal synchronization failed; restart and reconcile")

    def submit(self, key, task):
        self._ensure_ready()
        if not self.journal.enqueue(key, task.account, task.name, task.deadline):
            return False
        self._keys[id(task)] = key
        self.queue.submit(task)
        return True

    def _sync_queue_timeouts(self):
        """Synchronize actual expired task identities, not ambiguous task names."""
        while self.queue.expired_tasks:
            task = self.queue.expired_tasks[0]
            key = self._keys[id(task)]
            state = self.journal.get(key)['state']
            if state == 'queued':
                self.journal.timeout_queued(key)
            elif state != 'timed_out':
                raise RuntimeError('queue/journal timeout divergence')
            self.queue.expired_tasks.pop(0)

    def acquire(self):
        self._ensure_ready()
        try:
            task = self.queue.acquire()
            self._sync_queue_timeouts()
        except Exception:
            self.blocked = True
            raise
        if task is None:
            return None
        key = self._keys[id(task)]
        try:
            if not self.journal.start(key):
                self.queue.finish(task, False)
                return None
        except Exception:
            self.blocked = True
            self.queue.finish(task, False)
            raise
        return task

    def expire_active(self):
        self._ensure_ready()
        task = self.queue.expire_active()
        if task is not None:
            key = self._keys[id(task)]
            try:
                self.journal.timeout_active(key)
            except Exception:
                self.blocked = True
                raise
        return task

    def finish(self, task, verified):
        self._ensure_ready()
        key = self._keys[id(task)]
        try:
            state = self.journal.complete(key, verified)
        except Exception:
            self.blocked = True
            raise
        self.queue.finish(task, state == 'verified')
        return state
