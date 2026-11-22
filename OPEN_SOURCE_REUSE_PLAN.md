# YOYO 开源复用与避免重复开发方案

## 目标与约束

优先复用现有 Windows 11 双账号架构；开源组件只承担通用基础设施，不引入其他游戏的账号、网络协议、反作弊绕过或自动消费逻辑。所有新增输入保持验证门禁，真实双开验收前不得开放。

## 候选项目（2026-11-22 初步调研）

| 项目 | 地址 | 适用范围 | 引入前验证 |
| --- | --- | --- | --- |
| pywinauto | https://github.com/pywinauto/pywinauto | Windows 窗口枚举、焦点、原生控件；Win32/UIA | 游戏自绘窗口是否暴露可用控件；HWND/PID 显式绑定和 DPI；BSD-3-Clause 许可证 |
| Osprey | https://github.com/wazgf1f/osprey | 截图、模板匹配、多尺度视觉、超时/停止结构 | 不直接运行第三方 EXE；仅审阅可复用代码/设计；MIT 许可证 |
| win-computer-use | https://github.com/CarlosShao/win-computer-use | 截图、OpenCV、紧急停止、边界检查 | 依赖和安全审查；不得覆盖现有身份/几何双校验；MIT 许可证 |
| PyAutoGUI | https://github.com/asweigart/pyautogui | 普通桌面鼠标键盘输入 | 仅作为现有 Win32 SendInput 不足时的可选后备；避免跨窗口误点 |

## 对现有仓库的映射

- `windows_provider.py`, `dpi_awareness.py`: 保留现有 HWND/PID/窗口矩形校验；只在测试证明收益后考虑 pywinauto。
- `fruit_screen.py`, `room_route.py`: 保留真实录像参考样本；对比 OpenCV 多尺度模板匹配与现有 PIL 方法，使用同一批正例、反例和不同分辨率测试。
- `fruit_actions.py`: 保留人工示教、双窗安全检查、一次性动作、停止标志；不直接替换为通用点击框架。
- `fruit_sequence_gate.py`, `fruit_replay.py`: 优先接入已有 JSONL 证据和离线回放；先识别再动作。
- `build_windows.ps1` 和 Actions: 增加依赖前先核对 PyInstaller 体积、构建时长、离线启动、日志与 Windows CI。

## 迭代验收顺序

1. 现有代码能力盘点，避免重复实现。
2. 对每个候选库进行许可证、维护情况、依赖体积与安全检查；只选择必要组件。
3. 用用户提供的水果剧团录像进行双窗同步正例/反例、多分辨率回放。
4. Windows CI 通过后提供 EXE、日志和 SHA256；真实双开验证前不得宣称自动通关。

## 明确排除

团P、自动炼金、合成、采购、未知游戏安装包、反作弊绕过、密码写入仓库或公开构建物。此文件仅是开发决策，不代表第三方库已经安装或接入。
