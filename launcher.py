"""Single safe entrypoint for offline simulation and Windows read-only diagnostics.

No keyboard/mouse input is implemented; no game state or completion is inferred.
"""
import argparse
import multiprocessing
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


def execute(mode, *, db=None, title=None, provider=None, main_hwnd=None, alt_hwnd=None, dungeon=None):
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
    if mode in ('windows-observe', 'windows-dungeon-observe'):
        if mode == 'windows-dungeon-observe' and dungeon != '水果剧团':
            return {'mode': mode, 'status': 'paused', 'reason': 'explicit_fruit_dungeon_required',
                    'input_enabled': False, 'game_state_verified': False}
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
        from observation_bridge import capture_pair, safe_coop_observations, safe_dungeon_observations
        from gameplay_flows import CoopFlow, DungeonFlow
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
            if mode == 'windows-dungeon-observe':
                # Real screenshots are validated above. A detector has not yet
                # proven either on-screen account identity or dungeon state;
                # therefore all game observations must remain UNKNOWN.
                observations = safe_dungeon_observations(evidence, dungeon=dungeon)
                decision = DungeonFlow('main', 'alt', dungeon=dungeon, leader='main').advance(observations)
            else:
                observations = safe_coop_observations(evidence)
                decision = CoopFlow('main', 'alt', leader='main').advance(observations)
            return {'mode': mode, 'status': 'paused', 'reason': decision.reason,
                    'dungeon': dungeon if mode == 'windows-dungeon-observe' else None,
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


def write_session_log(result, *, log_dir=None):
    """Persist a diagnostic JSONL event without recording passwords or screenshots."""
    root = Path(log_dir) if log_dir else Path.home() / 'YOYO_Logs'
    root.mkdir(parents=True, exist_ok=True)
    path = root / ('session_' + datetime.now(timezone.utc).strftime('%Y%m%d') + '.log')
    event = {'timestamp_utc': datetime.now(timezone.utc).isoformat(),
             'mode': result.get('mode'), 'status': result.get('status'),
             'reason': result.get('reason'), 'input_enabled': False,
             'game_state_verified': False, 'details': result}
    with path.open('a', encoding='utf-8') as stream:
        stream.write(json.dumps(event, ensure_ascii=False, default=str) + '\n')
    return path


def main(argv=None):
    parser = argparse.ArgumentParser(description='Safe dual-account diagnostics; no game input')
    parser.add_argument('--mode', required=True,
                        choices=['offline', 'windows-probe', 'windows-gated-offline', 'windows-observe', 'windows-dungeon-observe', 'gameplay-demo'])
    parser.add_argument('--title', help='Required for Windows probe: exact title substring')
    parser.add_argument('--db', help='Persistent SQLite database for offline simulation only')
    parser.add_argument('--main-hwnd', type=int, help='Explicit main-account window handle for read-only observation')
    parser.add_argument('--alt-hwnd', type=int, help='Explicit alt-account window handle for read-only observation')
    parser.add_argument('--dungeon', help='Dungeon for read-only observation; currently only 水果剧团')
    parser.add_argument('--log-dir', help='Optional folder for automatic diagnostic LOG files')
    args = parser.parse_args(argv)
    if args.mode == 'windows-probe' and args.db:
        parser.error('--db is not supported in windows-probe mode')
    result = execute(args.mode, db=args.db, title=args.title,
                     main_hwnd=args.main_hwnd, alt_hwnd=args.alt_hwnd, dungeon=args.dungeon)
    try:
        log_path = write_session_log(result, log_dir=args.log_dir)
        result['log_path'] = str(log_path)
    except OSError as exc:
        result['log_error'] = type(exc).__name__
        result['status'] = 'paused'
        result['reason'] = 'log_write_failed'
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get('status') not in ('paused', 'unsupported') else 2


if __name__ == '__main__':
    multiprocessing.freeze_support()
    sys.exit(main())
