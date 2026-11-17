"""Safe, offline-testable dual-window orchestration primitives.
No game interaction occurs in this module. Integration requires explicit adapters.
"""
from dataclasses import dataclass, field
from collections import deque
from threading import Lock
import time

@dataclass(frozen=True)
class Rect:
    x: int
    y: int
    width: int
    height: int
    def __post_init__(self):
        if self.width <= 0 or self.height <= 0:
            raise ValueError('invalid rectangle')

@dataclass(frozen=True)
class Window:
    account: str
    handle: int
    client: Rect
    reference_width: int
    reference_height: int
    def map_point(self, x: float, y: float, content: Rect | None = None):
        """Map a reference coordinate into screen coordinates within client/content area.
        Content is the detected game viewport (excluding letterbox); never guess it.
        """
        if not (0 <= x < self.reference_width and 0 <= y < self.reference_height):
            raise ValueError('reference point outside reference viewport')
        area = content or self.client
        if (area.x < self.client.x or area.y < self.client.y or
            area.x + area.width > self.client.x + self.client.width or
            area.y + area.height > self.client.y + self.client.height):
            raise ValueError('content outside client')
        px = area.x + int(x * area.width / self.reference_width)
        py = area.y + int(y * area.height / self.reference_height)
        if not (area.x <= px < area.x + area.width and area.y <= py < area.y + area.height):
            raise ValueError('mapped point outside content')
        return px, py

@dataclass
class Task:
    account: str
    name: str
    deadline: float
    state: str = 'queued'
    attempts: int = 0

class DualAccountQueue:
    """One global foreground lease; independent per-account queues and fail-closed timeouts."""
    def __init__(self, clock=time.time):
        self.clock = clock
        self.queues = {}
        self._lock = Lock()
        self._active = None
        self._order = deque()
        self.events = []
        self.expired_tasks = []

    def submit(self, task: Task):
        with self._lock:
            if task.account not in self.queues:
                self.queues[task.account] = deque()
                self._order.append(task.account)
            self.queues[task.account].append(task)
            self.events.append(('submit', task.account, task.name))

    def acquire(self):
        with self._lock:
            if self._active is not None:
                return None
            for _ in range(len(self._order)):
                account = self._order[0]
                self._order.rotate(-1)
                queue = self.queues[account]
                while queue and self.clock() >= queue[0].deadline:
                    task = queue.popleft()
                    task.state = 'timed_out'
                    self.events.append(('timeout', account, task.name))
                    self.expired_tasks.append(task)
                if queue:
                    task = queue.popleft()
                    task.state = 'active'
                    task.attempts += 1
                    self._active = task
                    self.events.append(('acquire', account, task.name))
                    return task
            return None

    def finish(self, task: Task, verified: bool):
        with self._lock:
            if task is not self._active:
                raise RuntimeError('invalid foreground lease')
            task.state = 'verified' if verified and self.clock() < task.deadline else 'paused'
            self.events.append((task.state, task.account, task.name))
            self._active = None

    def expire_active(self):
        with self._lock:
            if self._active is not None and self.clock() >= self._active.deadline:
                task = self._active
                task.state = 'timed_out'
                self.events.append(('timeout', task.account, task.name))
                self._active = None
                return task
            return None
