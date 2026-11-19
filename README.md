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

## Dual-account dungeon / co-op flow model (new)

`python launcher.py --mode gameplay-demo` runs a deterministic rehearsal of:
- co-op room creation, exact second-account join, 2/2 room verification, matchmaking, battle and result;
- a shared two-account dungeon from room verification through loading, map objectives, battle, reward and completion.

`gameplay_flows.py` is an observation-driven state machine, not an input driver. It requires stable two-frame observations, distinct HWND/PID-bound windows (the caller supplies verified account/window IDs), matching server IDs, and matching room/instance/match IDs. It emits advisory actions only. `input_enabled` remains `false`; no click, key, sweep-ticket use, item consumption, battle start, or reward claim is executed.

Two dungeon relationships are modeled:
- `shared`: both accounts must prove the same room and instance; any split state pauses.
- `parallel`: each account can be at a different point in its own run; one advisory action is returned at a time to preserve the global foreground lease.

Sweep is opt-in and read-only. Eligibility requires a source-listed dungeon, explicit request, an observed unlock, and an observed ticket count. The catalog records only source-backed level hints, player-count rules and sweep support; it does not infer undocumented requirements.