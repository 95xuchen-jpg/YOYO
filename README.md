# 双账号助手 V2 集成核心（离线原型）

本工程只包含可测试的窗口坐标映射和双账号前台互斥调度器；**没有连接真实游戏，也不是可用 EXE**。

运行测试：`PYTHONPATH=. python -m unittest discover -s tests -v`

## 已实现
- 两账号独立任务队列与公平轮询
- 单一前台租约，防止两个窗口同时输入
- 超时释放、失效任务跳过、未验证操作暂停
- 基于客户区和显式检测到的游戏内容区进行坐标缩放，越界拒绝

## 待集成
- Windows HWND 发现与窗口身份核验、客户区/DPI实时获取
- 黑边和UI锚点识别（禁止默认把整个客户区当作有效内容）
- 游戏截图、双帧验证、输入驱动、持久化日志与崩溃恢复
- v1.0.6模块接入、真实双开测试、Windows EXE构建

## 安全
- 无网络访问、无游戏输入、无自动消费；不运行第三方二进制。

## Iteration 05 (offline)
Added `adapters.py` with a read-only `WindowProvider` and `StateDetector` protocol.
`WindowGuard` requires the same expected state in two independent screenshots,
checking client geometry before/between/after them. It returns no click target
if state, screenshot, window handle or geometry is invalid. No Windows API or
mouse/keyboard input is implemented yet. All tests use fake providers.

Run tests: `PYTHONPATH=. python -m unittest discover -s tests -v`.
Status: 16/16 offline tests pass; **not integrated into v1.0.6**, no EXE built,
no Windows or live-game validation. No claims of real screenshot detection.

### Iteration 06 (2026-11-17)
Adds `windows_provider.py`: read-only Win32 window discovery, explicit binding to HWND+PID+title+class, client bounds via ClientToScreen, and optional Pillow screenshot capture. This is an *adapter*, not a full game automation system. `ImageGrab` can fail on minimized, obscured or protected windows, and screen capture cannot prove the target window is foreground. DPI awareness must be established by the eventual process entrypoint before obtaining window bounds. No input injection is included. Do not run against live game without explicit verification.

Run offline tests from `pln_assistant_v2` with `python -m unittest discover -s tests -v`.

## Iteration 07
The default Windows screenshot path now uses a disposable spawn-process with a 3-second watchdog and 20 MB payload limit. It terminates and joins hung capture workers. WindowGuard fails closed on provider/detector exceptions. No input injection or game-side changes. Linux unit tests do not validate real Windows screenshot behavior.

## Iteration 08 (2026-11-17, offline)
Added `journal.py`: transactional SQLite journal with durable task IDs, collision
rejection, one active task globally, deadline checks, and fail-closed restart
recovery. Interrupted active tasks become **paused**, never automatically
replayed or marked verified. This is a standalone integration component; it
has not been wired into the `DualAccountQueue` or live Windows input driver.
The tests use temporary local databases and injected clocks.

`coordinator.py` now connects journal writes to the existing dual-account queue
for submit/acquire/finish operations. It is an offline prototype; in-memory
queue reconstruction after restart is deliberately disabled pending explicit
reconciliation. Crash after journal commit but before queue release requires
restart and manual review. No Windows input or live-game verification.

## Iteration 09 — safe restart reconciliation (offline only)
`recovery.recover_queued(journal, fresh_coordinator, clock)` reconstructs only untouched, unexpired `queued` records in a fresh queue. Interrupted `active` records are converted to `paused` by `TaskJournal` on open; expired queued records become `timed_out`; inconsistent queued records with attempts >0 become `paused`. Completed records never replay. Restored queued work still requires actual game UI preflight before executing. This is not Windows/game validation. Note: queue-local expiration and journal state can diverge if tasks expire before acquisition; that path needs a later integration fix before release.

## Iteration 10 — queue/journal deadline synchronization (offline only)
The in-memory queue now records expired Task objects by identity. `DurableCoordinator.acquire()` persists every queued timeout to SQLite, including several tasks with identical names across accounts. `DurableCoordinator.expire_active()` persists active-task timeouts before returning. Added five regression tests; 47/47 offline tests pass. **Known limitation:** a database write failure after the in-memory queue has expired a task can still leave queue and journal temporarily divergent until retry or process restart. Do not connect a real input driver before transaction/recovery fault injection and Windows validation. No live-game actions, EXE build, or Windows tests were performed.

## Iteration 11 (offline only, 2026-11-17)
- Queue default clock changed to wall-clock UNIX time, matching durable journal deadlines; previously the queue defaulted to monotonic time, silently allowing expired epoch-deadline tasks.
- DurableCoordinator enters fail-closed blocked mode on journal start/timeout/completion synchronization exceptions. No further work can be dispatched until restart and reconciliation.
- Five fault-injection and default-clock regression tests added. Tests run on Linux mocks only, not on a Windows game client.
- Known limitation: a blocked coordinator must be restarted; journal startup reconciliation pauses interrupted active tasks. Original v1.0.6 executable has not been integrated.

## Iteration 13: unified read-only preflight (offline)
Run `python runner.py --preflight-demo` to execute the existing durable dual-account
simulation and the newly connected two-window observation boundary. All frames and
window IDs are synthetic. `preflight.py` also provides an opt-in Windows discovery
boundary, but requires an externally validated game state detector; it is not
invoked by the default runner and cannot click or play the game. No real Windows
or game verification has occurred. Never use synthetic `observed` statuses as
proof of live gameplay readiness.

## Iteration 14 read-only Windows capture probe
Run `python readonly_probe.py --title "<exact distinctive game window title substring>"` on Windows 11 with two separate game processes. The probe does not click, save frames, or verify gameplay. It fails closed for duplicate process IDs, changing geometry, and failed screenshots. Linux returns unsupported (exit code 2). This is a diagnostic only, not an autonomous game assistant.
