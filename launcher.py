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


def execute(mode, *, db=None, title=None, provider=None, main_hwnd=None, alt_hwnd=None, dungeon=None, expected_windows=None):
    if mode == 'offline':
        from runner import simulate, simulate_window_preflight
        import tempfile
        if db is None:
            with tempfile.TemporaryDirectory() as tmp:
                result = simulate(Path(tmp) / 'state.sqlite')
                result['journal'] = 'temporary (removed)'
        else:
            result = simulate(Path(db))
        result['status'] = 'offline_rehearsal_only'
        result['input_enabled'] = False
        result['game_state_verified'] = False
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
            if expected_windows is not None and (by_hwnd[main_hwnd], by_hwnd[alt_hwnd]) != expected_windows:
                raise ValueError('selected_windows_changed')
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



def launch_readonly_gui():
    """Double-clickable diagnostic interface; deliberately no game input."""
    import tkinter as tk
    from tkinter import ttk
    import threading
    import queue
    if os.name == 'nt':
        from dpi_awareness import enable_per_monitor_dpi
        enable_per_monitor_dpi()
    root = tk.Tk()
    root.title('YOYO 双账号助手 - 只读诊断版（未验证游戏）')
    root.geometry('760x500')
    root.minsize(600, 400)
    frame = ttk.Frame(root, padding=14)
    frame.pack(fill='both', expand=True)
    ttk.Label(frame, text='只读诊断版：不会组队、点击、战斗或自动通关。', foreground='#9b341f').pack(anchor='w')
    ttk.Label(frame, text='双击可运行，无需安装 Python。运行结果自动保存至 ~/YOYO_Logs。').pack(anchor='w', pady=(5, 10))
    from tkinter import messagebox
    selector = ttk.Frame(frame)
    selector.pack(fill='x', pady=4)
    ttk.Label(selector, text='游戏窗口标题关键词').pack(side='left')
    title = tk.StringVar()
    ttk.Entry(selector, textvariable=title, width=18).pack(side='left', padx=6)
    main_choice = ttk.Combobox(frame, state='readonly')
    ttk.Label(frame, text='选择主号窗口（另一个窗口作为副号）').pack(anchor='w')
    main_choice.pack(fill='x')
    choices = {}
    selected_title = ''

    def refresh():
        nonlocal selected_title
        choices.clear()
        main_choice.set('')
        main_choice.configure(values=())
        selected_title = title.get().strip()
        if not selected_title:
            messagebox.showinfo('窗口绑定', '请输入两个游戏窗口标题共有的文字。')
            return
        try:
            from windows_provider import WindowsClientProvider
            provider = WindowsClientProvider()
            windows = provider.discover(selected_title)
            if len(windows) != 2 or len({w.pid for w in windows}) != 2:
                raise ValueError('请打开两个独立的游戏窗口，并缩小标题匹配范围。')
            for window in windows:
                if provider.bind(window.hwnd) != window:
                    raise ValueError('窗口已变化，请刷新。')
                rect = provider.client_rect(window.hwnd)
                if rect is None:
                    raise ValueError('请恢复两个游戏窗口后刷新。')
                label = f'{window.title}　位置 ({rect.x}, {rect.y})　窗口 {window.hwnd}'
                choices[label] = window
            main_choice.configure(values=tuple(choices))
        except Exception as exc:
            choices.clear()
            messagebox.showwarning('窗口绑定', str(exc))

    ttk.Button(selector, text='查找双窗口', command=refresh).pack(side='left')
    output = tk.Text(frame, wrap='word', height=18)
    output.pack(fill='both', expand=True)
    output.insert('end', '点击“离线自检”开始。此操作不访问游戏窗口。\\n')
    output.configure(state='disabled')

    results = queue.Queue()
    stopped = False
    running = False

    def close_gui():
        # Only offline diagnostics run in the worker; no game input exists.
        # Closing the GUI must not wait for the worker to finish.
        nonlocal stopped
        stopped = True
        root.destroy()

    def poll_result():
        nonlocal running
        if stopped:
            return
        try:
            result = results.get_nowait()
        except queue.Empty:
            if running:
                root.after(100, poll_result)
            return
        running = False
        output.configure(state='normal')
        output.delete('1.0', 'end')
        output.insert('end', json.dumps(result, ensure_ascii=False, indent=2))
        output.configure(state='disabled')
        button.configure(state='normal')
        observe_button.configure(state='normal')

    def diagnostic_worker(mode, options):
        try:
            try:
                result = execute(mode, **options)
            except Exception as exc:
                result = {'mode': mode, 'status': 'paused',
                          'reason': 'unexpected_runtime_error',
                          'error_type': type(exc).__name__,
                          'input_enabled': False, 'game_state_verified': False}
            try:
                path = write_session_log(result)
                result['log_path'] = str(path)
            except OSError as exc:
                result['status'] = 'paused'
                result['reason'] = 'log_write_failed'
                result['log_error'] = type(exc).__name__
        except Exception as exc:
            result = {'mode': mode, 'status': 'paused',
                      'reason': 'diagnostic_worker_failed',
                      'error_type': type(exc).__name__,
                      'input_enabled': False, 'game_state_verified': False}
        results.put(result)

    def run(mode='offline', **options):
        nonlocal running
        if running or stopped:
            return
        running = True
        button.configure(state='disabled')
        observe_button.configure(state='disabled')
        threading.Thread(target=diagnostic_worker, args=(mode, options), daemon=True).start()
        root.after(100, poll_result)

    def observe():
        main = choices.get(main_choice.get())
        if not main or len(choices) != 2 or selected_title != title.get().strip():
            messagebox.showinfo('水果剧团', '请查找双窗口并选择主号。')
            return
        alt = next(w for w in choices.values() if w != main)
        run('windows-dungeon-observe', title=selected_title, main_hwnd=main.hwnd,
            alt_hwnd=alt.hwnd, dungeon='水果剧团', expected_windows=(main, alt))

    bar = ttk.Frame(frame)
    bar.pack(fill='x', pady=(10, 0))
    button = ttk.Button(bar, text='离线自检（不操作游戏）', command=run)
    button.pack(side='left')
    observe_button = ttk.Button(bar, text='水果剧团双窗观察', command=observe)
    observe_button.pack(side='left', padx=6)
    ttk.Button(bar, text='退出 / 停止诊断', command=close_gui).pack(side='right')
    root.protocol('WM_DELETE_WINDOW', close_gui)
    root.mainloop()


def main(argv=None):
    if argv is None and len(sys.argv) == 1:
        launch_readonly_gui()
        return 0
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
    try:
        result = execute(args.mode, db=args.db, title=args.title,
                         main_hwnd=args.main_hwnd, alt_hwnd=args.alt_hwnd, dungeon=args.dungeon)
    except Exception as exc:
        # Unexpected runtime failures must still leave a durable, non-sensitive
        # diagnostic record instead of silently terminating the frozen EXE.
        result = {'mode': args.mode, 'status': 'paused',
                  'reason': 'unexpected_runtime_error',
                  'error_type': type(exc).__name__,
                  'input_enabled': False, 'game_state_verified': False}
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
