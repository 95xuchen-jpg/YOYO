"""Unified offline entrypoint. No game clicks, network calls, or purchases."""
import argparse
import json
import tempfile
import time
from pathlib import Path
from core import DualAccountQueue, Task
from coordinator import DurableCoordinator
from journal import TaskJournal
from recovery import recover_queued
from preflight import inspect_two_windows
from core import Rect, Window


def simulate(db_path, now=None, fault=None):
    now = time.time() if now is None else float(now)
    journal = TaskJournal(db_path, clock=lambda: now)
    try:
        queue = DualAccountQueue(clock=lambda: now)
        coordinator = DurableCoordinator(queue, journal)
        report = recover_queued(journal, coordinator, lambda: now)
        for account in ('account_A', 'account_B'):
            day = int(now // 86400)
            key = f'offline-demo:{day}:{account}:preflight'
            coordinator.submit(key, Task(account, 'visual_preflight_demo', (day + 1) * 86400))
        results = []
        for i in range(2):
            task = coordinator.acquire()
            if task is None:
                break
            if fault == 'crash_after_acquire' and i == 0:
                results.append({'account': task.account, 'state': 'interrupted_simulation'})
                break
            state = coordinator.finish(task, verified=True)
            results.append({'account': task.account, 'state': state})
        return {'mode': 'offline_simulation_only', 'recovered': report.__dict__, 'results': results,
                'journal': str(db_path)}
    finally:
        journal.close()


def simulate_window_preflight():
    """Deterministic synthetic frames, not screenshots from the game."""
    class SyntheticProvider:
        def __init__(self):
            self.bounds = {101: Rect(0, 0, 800, 600), 202: Rect(800, 0, 640, 480)}
        def client_rect(self, handle):
            return self.bounds.get(handle)
        def screenshot(self, handle):
            return b'synthetic-ready' if handle in self.bounds else None
    class SyntheticDetector:
        def detect(self, screenshot):
            return 'synthetic_ready' if screenshot == b'synthetic-ready' else None
    bindings = [Window('account_A', 101, Rect(0,0,800,600), 800,600),
                Window('account_B', 202, Rect(800,0,640,480), 640,480)]
    results = inspect_two_windows(SyntheticProvider(), SyntheticDetector(), bindings, 'synthetic_ready')
    return {'mode': 'synthetic_frames_only', 'observations': [r.__dict__ for r in results]}


def main():
    parser = argparse.ArgumentParser(description='Dual-account OFFLINE simulation; no game control')
    parser.add_argument('--db', help='SQLite state file (defaults to a temporary file)')
    parser.add_argument('--fault', choices=['crash_after_acquire'])
    parser.add_argument('--preflight-demo', action='store_true', help='Synthetic read-only two-window observation')
    args = parser.parse_args()
    if args.db:
        output = simulate(Path(args.db), fault=args.fault)
    else:
        with tempfile.TemporaryDirectory() as tmp:
            output = simulate(Path(tmp) / 'tasks.sqlite', fault=args.fault)
            output['journal'] = 'temporary (removed)'
    if args.preflight_demo:
        output['window_preflight'] = simulate_window_preflight()
    print(json.dumps(output, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
