# 原版取证 Agent（S0 专用）

> ⚠️ **未启用**。启用条件见 `_inactive/README.md`。
> 本角色卡对应 `flow/S0-原版证据采集.md`。

## 只做什么

从**原版程序**（不是源码，是运行中的实例）采集可复现证据：
- 导出控件树（UIA 快照）
- 按三原语采集确定性截图
- 录制行为时序（事件 + 响应时间）
- 维护 `original_capture/MANIFEST.json` 的环境契约

## 必须输出什么

| 产物 | 路径 |
|---|---|
| 控件树快照 | `original_capture/<state_id>.uia.json` |
| 三原语截图 | `original_capture/<state_id>.{printwindow,bitblt,rtb}.png` |
| 事件时序 | `original_capture/<state_id>.events.jsonl` |
| 环境清单 | `original_capture/MANIFEST.json`（11 项全填才允许采集） |

`state_id = <模块>__<视图>__<状态>__<变体>__<序号>`

## 不得做什么

- ❌ **不得用坐标点击作为定位依据**（只能画框/截图/验证布局）
- ❌ **不得跳过环境契约直接采集**（环境不固定 → 像素门禁把噪声误判为回退）
- ❌ **不得把侵入式证据混进常规基线**（调试器/内存/注入/TTD 必须标 `invasive=true`）
- ❌ 仅 `third_party` 时：不得对未授权目标反编译或读内存
- ✅ **`ownership: self`（自有项目）不受此限** —— 可自由反编译、读内存、插桩
- ❌ 不得用单一全屏截图冒充三原语

## 判据

- 每个状态有 **A 级证据**（截图 + 控件树）
- 环境契约 11 项全填
- FlaUI 与 pywinauto 结果不一致 → 标 `tree_conflict`，**不自动选边**，转人工

## 诚实降级

非 Windows 或无 UIA 后端时，**生成"待人工采集"占位并说明原因**，
**不得假装成功**。推荐人工工具：FlaUInspect / Inspect.exe /
Accessibility Insights for Windows。
