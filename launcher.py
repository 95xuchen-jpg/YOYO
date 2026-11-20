"""Single safe entrypoint for offline simulation and Windows read-only diagnostics.

No keyboard/mouse input is implemented; no game state or completion is inferred.
"""
import argparse
import multiprocessing
import json
import os
import sys
from pathlib import Path


def execute(mode, *, db=None, title=None, provider=None, main_hwnd=None, alt_hwnd=None):
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
    if mode == 'windows-gated-offline':
        try:
            observation = execute('windows-probe', title=title, provider=provider)
        except Exception as exc:
            return {'mode': mode, 'status': 'paused', 'reason': 'window_preflight_failed',
                    'error_type': type(exc).__name__, 'input_enabled': False,
                    'game_state_verified': False}
        if observation.get('status') != 'capture_ready_not_game_verified':
            return {'mode': mode, 'status': 'paused', 'preflight': observation,
                    'input_enabled': False, 'game_state_verified': False}
        # Rehearsal only: this never sends input to either game window.
        from runner import simulate
        import tempfile
        try:
            if db is None:
                with tempfile.TemporaryDirectory() as tmp:
                    rehearsal = simulate(Path(tmp) / 'state.sqlite')
                    rehearsal['journal'] = 'temporary (removed)'
            else:
                rehearsal = simulate(Path(db))
        except Exception as exc:
            return {'mode': mode, 'status': 'paused', 'reason': 'offline_rehearsal_failed',
                    'error_type': type(exc).__name__, 'input_enabled': False,
                    'game_state_verified': False}
        try:
            after = execute('windows-probe', title=title, provider=provider)
        except Exception as exc:
            return {'mode': mode, 'status': 'paused', 'reason': 'window_revalidation_failed',
                    'error_type': type(exc).__name__, 'input_enabled': False,
                    'game_state_verified': False}
        if after.get('status') != 'capture_ready_not_game_verified' or after.get('windows') != observation.get('windows'):
            return {'mode': mode, 'status': 'paused', 'reason': 'window_changed_during_rehearsal',
                    'input_enabled': False, 'game_state_verified': False}
        return {'mode': mode, 'status': 'offline_rehearsal_only', 'preflight': after,
                'rehearsal': rehearsal, 'input_enabled': False, 'game_state_verified': False}
    if mode == 'windows-observe':
        if (type(main_hwnd) is not int or type(alt_hwnd) is not int or
                main_hwnd <= 0 or alt_hwnd <= 0 or main_hwnd == alt_hwnd):
            return {'mode': mode, 'status': 'paused', 'reason': 'explicit_distinct_hwnds_required',
                    'input_enabled': False, 'game_state_verified': False}
        if not title or not title.strip():
            return {'mode': mode, 'status': 'paused', 'reason': 'explicit_title_required',
                    'input_enabled': False, 'game_state_verified': False}
        if provider is None:
            if os.name != 'nt':
                return {'mode': mode, 'status': 'unsupported', 'reason': 'requires_windows',
                        'input_enabled': False, 'game_state_verified': False}
            from dpi_awareness import enable_per_monitor_dpi
            enable_per_monitor_dpi()
            from windows_provider import WindowsClientProvider
            provider = WindowsClientProvider()
        from observation_bridge import capture_pair, safe_coop_observations
        from gameplay_flows import CoopFlow
        try:
            windows = provider.discover(title)
            if len(windows) != 2 or len({w.hwnd for w in windows}) != 2 or len({w.pid for w in windows}) != 2:
                raise ValueError('exactly_two_distinct_windows_required')
            by_hwnd = {w.hwnd: w for w in windows}
            if set(by_hwnd) != {main_hwnd, alt_hwnd}:
                raise ValueError('explicit_window_binding_mismatch')
            bindings = (('main', main_hwnd, by_hwnd[main_hwnd].pid),
                        ('alt', alt_hwnd, by_hwnd[alt_hwnd].pid))
            for w in windows:
                if provider.bind(w.hwnd) != w:
                    raise ValueError('window_binding_changed')
            evidence = capture_pair(provider, bindings)
            observations = safe_coop_observations(evidence)
            decision = CoopFlow('main', 'alt', leader='main').advance(observations)
            return {'mode': mode, 'status': 'paused', 'reason': decision.reason,
                    'captures': [dict(account_id=e.account_id, hwnd=e.hwnd, pid=e.pid,
                                      identity_ok=e.identity_ok, geometry_ok=e.geometry_ok,
                                      two_frames_present=e.two_frames_present) for e in evidence],
                    'input_enabled': False, 'game_state_verified': False}
        except Exception as exc:
            return {'mode': mode, 'status': 'paused', 'reason': 'observation_preflight_failed',
                    'error_type': type(exc).__name__, 'input_enabled': False,
                    'game_state_verified': False}
    if mode == 'gameplay-demo':
        from gameplay_flows import gameplay_demo
        return gameplay_demo()
    raise ValueError('unsupported mode')


def main(argv=None):
    parser = argparse.ArgumentParser(description='Safe dual-account diagnostics; no game input')
    parser.add_argument('--mode', required=True,
                        choices=['offline', 'windows-probe', 'windows-gated-offline', 'windows-observe', 'gameplay-demo'])
    parser.add_argument('--title', help='Required for Windows probe: exact title substring')
    parser.add_argument('--db', help='Persistent SQLite database for offline simulation only')
    parser.add_argument('--main-hwnd', type=int, help='Explicit main-account window handle for read-only observation')
    parser.add_argument('--alt-hwnd', type=int, help='Explicit alt-account window handle for read-only observation')
    args = parser.parse_args(argv)
    if args.mode == 'windows-probe' and args.db:
        parser.error('--db is not supported in windows-probe mode')
    result = execute(args.mode, db=args.db, title=args.title,
                     main_hwnd=args.main_hwnd, alt_hwnd=args.alt_hwnd)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get('status') not in ('paused', 'unsupported') else 2


if __name__ == '__main__':
    multiprocessing.freeze_support()
    sys.exit(main())
