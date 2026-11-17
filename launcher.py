"""Single safe entrypoint for offline simulation and Windows read-only diagnostics.

No keyboard/mouse input is implemented; no game state or completion is inferred.
"""
import argparse
import multiprocessing
import json
import os
import sys
from pathlib import Path


def execute(mode, *, db=None, title=None, provider=None):
    if mode == 'offline':
        from runner import simulate, simulate_window_preflight
        import tempfile
        if db is None:
            with tempfile.TemporaryDirectory() as tmp:
                result = simulate(Path(tmp) / 'state.sqlite')
                result['journal'] = 'temporary (removed)'
        else:
            result = simulate(Path(db))
        result['window_preflight'] = simulate_window_preflight()
        return result
    if mode == 'windows-probe':
        if not title or not title.strip():
            return {'mode': 'read_only', 'status': 'paused', 'reason': 'explicit_title_required'}
        if provider is None:
            if os.name != 'nt':
                return {'mode': 'read_only', 'status': 'unsupported', 'reason': 'requires_windows'}
            from dpi_awareness import enable_per_monitor_dpi
            enable_per_monitor_dpi()
            from windows_provider import WindowsClientProvider
            provider = WindowsClientProvider()
        from readonly_probe import probe
        return probe(provider, title)
    raise ValueError('unsupported mode')


def main(argv=None):
    parser = argparse.ArgumentParser(description='Safe dual-account diagnostics; no game input')
    parser.add_argument('--mode', required=True, choices=['offline', 'windows-probe'])
    parser.add_argument('--title', help='Required for Windows probe: exact title substring')
    parser.add_argument('--db', help='Persistent SQLite database for offline simulation only')
    args = parser.parse_args(argv)
    if args.mode != 'offline' and args.db:
        parser.error('--db is only supported in offline mode')
    result = execute(args.mode, db=args.db, title=args.title)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get('status') not in ('paused', 'unsupported') else 2


if __name__ == '__main__':
    multiprocessing.freeze_support()
    sys.exit(main())
