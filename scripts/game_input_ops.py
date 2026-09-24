#!/usr/bin/env python3
"""输入设备深化 / 跨版本存档链 / 崩溃诊断 / 音频预算（第五轮 C/D/E/G 类）。

**🔴 D 类最值得记住的三条**：
> **鼠标**：若原版读原始输入，Windows"提高指针精度"不影响游戏内值；
> 若用系统指针，**这些系统设置就进入 must-match**。
>
> **键盘**：扫描码决定物理位置，虚拟键受布局影响 ——
> **不能把 `KeyW` 直接写成固定扫描码**。
>
> **手柄至少要有三个独立死区**，不能只写一个 0.1。
> XInput 把**摇杆和两枚扳机**都定义为需要死区的输入。

用法:
  game_input_ops.py --mouse      # 鼠标（DPI/轮询率/**指针加速**）
  game_input_ops.py --keyboard   # 键盘（扫描码/布局/NKRO/IME 冲突）
  game_input_ops.py --gamepad    # 手柄（**三个死区**与死区形状）
  game_input_ops.py --touch      # 触摸与体感
  game_input_ops.py --a11y       # 无障碍输入
  game_input_ops.py --savechain  # 跨版本存档**迁移链**
  game_input_ops.py --ops        # 运营时间与赛季
  game_input_ops.py --crash      # 崩溃诊断与日志
  game_input_ops.py --voice      # 🔴 声音优先级与 voice stealing
  game_input_ops.py --init ledger/input_ops.csv
  game_input_ops.py --check ledger/input_ops.csv --gate

退出码: 0 通过 / 1 缺项 / 2 用法错误
"""
import argparse
import csv
import os
import sys

# 鼠标
MOUSE_FIELDS = [
    "device index", "USB vendor/product", "**report rate（轮询率）**",
    "**DPI profile**", "**raw / smoothed 标记**",
    "**OS acceleration 状态**（Windows 提高指针精度）",
    "capture state", "cursor clip", "sensitivity curve",
    "acceleration exponent", "yaw/pitch scale", "DPI scaling",
    "HiDPI", "display refresh rate", "桌面缩放", "**pointer ballistics 版本**",
]

MOUSE_RULE = [
    "🔴 若原版**读取原始输入** → Windows「提高指针精度」、鼠标加速、"
    "指针平滑、采样率**都不会改变游戏内值**",
    "🔴 若原版**使用系统指针** → 这些系统设置**进入 must-match**",
    "🔑 必须先确认原版走哪条路，再决定要记录哪些字段",
]

# 键盘
KEYBOARD_RULES = [
    "🔑 **扫描码**决定物理位置，**虚拟键**受布局影响 —— 两者都要记",
    "⚠️ QWERTY / AZERTY / QWERTZ / Dvorak / JIS 会改变 WASD、邻近键和**肌肉记忆**",
    "❌ **禁止把 `KeyW` 直接写成固定扫描码** —— 应以 scan code 作物理标识，"
    "逻辑动作作 gameplay binding，再分别记 layout-specific label、virtual key、dead key",
]

KEYBOARD_FIELDS = [
    "**NKRO / rollover**", "ghost key blocking",
    "**key repeat delay / rate**", "release ordering",
    "模拟按键", "粘滞键 / 筛选键",
    "**IME 组合输入与游戏热键冲突**",
]

# 手柄：**三个独立死区**
GAMEPAD_DEADZONES = [
    ("摇杆径向/轴向死区", "XInput 明确摇杆未操作时也会产生 movement"),
    ("**扳机阈值**", "两枚模拟扳机也需要死区"),
    ("**外圈加速起点**", "外圈加速曲线的起点"),
]

GAMEPAD_FIELDS = [
    "**死区形状**（圆形 / 方形 / 十字）", "轴向独立性",
    "**径向先减死区后归一化**", "轴向 clamp 是否先于长度归一化",
    "**轴到 d-pad 阈值**", "左右摇杆互换", "扳机模拟键阈值",
    "震动左右电机曲线", "按钮延迟", "自动瞄准辅助",
    "插拔归属", "**控制器排序**",
]

GAMEPAD_NOTE = [
    "🔑 XInput 官方列出 7849、8689、30 等推荐值，摇杆范围 ±32767 —— "
    "**这些是 API 参考值，不是原版应复刻值**",
    "🔑 这些值**不能跨项目直接沿用**，但足以证明："
    "取证要记录**原始报告值**，而不是先标准化再观察",
    "⚠️ SDL 的价值在统一设备层，**不在替代原版手柄语义** —— "
    "原始设备事件、HID usage、厂商驱动曲线、XInput 0–3 固定端口语义需单独取证",
]

TOUCH_FIELDS = [
    "手指数", "**pointerId**", "hit radius", "start / current / end",
    "**cancel**", "**palm rejection**", "touch rate", "**edge dead zone**",
    "双摇杆同指跨越", "长按阈值", "惯性",
]

GYRO_FIELDS = [
    "采样率", "坐标系", "死区", "**漂移校正**", "低通", "增益",
    "吸附", "暂停/菜单内行为",
]

GYRO_RULE = "⚠️ 手柄陀螺仪还应与摇杆输入**竞争同一动作**"

A11Y_FIELDS = [
    "单手模式", "开关控制扫描", "眼动 dwell", "语音", "自动连招",
    "减速时间", "**震动 / 闪光 / 字幕替代通道**", "**输入提示一致性**",
]

# 跨版本存档链
SAVE_CHAIN = [
    "🔑 存档兼容**不是读取旧版本**，而是维护**完整迁移链**",
    "每个 schema 版本建立：reader · writer · migrator · fixture · "
    "**round-trip 测试** · 破坏性变更清单",
    "🔴 必须支持 v1→v2、v2→v3，**以及 v1→v3 的升级路径**",
    "🔴 每个中间版本都要保留 **golden fixture** —— "
    "**不能只测最新版读最新版**",
]

SAVE_FIELD_MIGRATIONS = [
    "重命名", "改类型", "**改单位**", "**改精度**", "改枚举", "删除",
    "新增默认值", "**数组顺序语义**", "map 键归一化", "**NaN / Inf**",
    "版本缺失", "**CRC/hash 算法升级**", "压缩格式升级", "**平台大小端**",
]

SAVE_NOTE = "⚠️ 当前**没有可核验的通用游戏专用权威开源实现** —— 应标为待取证，"
"不能塞入笼统数据库迁移工具"

# 运营时间
OPS_TIME = [
    "**服务器时间 vs 本地时间**", "**时区**", "**夏令时**",
    "**离线时间计算**", "游戏内日历", "真实时间事件",
    "赛季 / 活动 / 限时内容的**时间窗口**",
]

OPS_RULE = [
    "🔑 限时内容的时间窗口必须记录**以哪个时钟为准** —— "
    "玩家改本地时间是否能刷到内容，是真实的玩法差异",
]

# 崩溃诊断
CRASH_FIELDS = [
    "**minidump**", "符号", "**崩溃后恢复**", "崩溃率统计",
    "错误上报字段", "**上报是否可离线查看**",
]

LOG_FIELDS = [
    "日志等级", "分类", "持久化", "**日志导致的卡顿**",
    "**发布版断言行为**", "日志轮转",
]

# 音频预算
VOICE_STEALING = [
    "🔴 **同时 64 个声音时谁被掐掉** —— 这是真实的听感差异",
    "记录：**voice priority** · **virtual voice 规则** · stealing 策略 · "
    "淡出时间 · 最小音量阈值",
    "⚠️ 同时发声数上限、每类声音预算、CPU 预算",
]

AUDIO_PERF = [
    "音频线程优先级", "**音频线程卡顿**", "缓冲大小", "回调周期",
    "**音频与帧率耦合**（音频卡导致主线程卡）",
]

FIELDS = [
    ("item_id", "项编号"),
    ("domain", "域（mouse / keyboard / gamepad / touch / a11y / savechain / ops / crash / voice）"),
    ("legacy_value", "**原版值**"),
    ("new_value", "新引擎值"),
    ("match", "**是否一致**"),
    ("evidence", "证据"),
]


def _hdr(t, w=80):
    print("=" * w)
    print(t)
    print("=" * w)


def cmd_mouse(a):
    _hdr("鼠标（🔴 **不只记录灵敏度**）")
    for f in MOUSE_FIELDS:
        print(f"   · {f}")
    print("\n规则:")
    for r in MOUSE_RULE:
        print(f"   {r}")
    return 0


def cmd_keyboard(a):
    _hdr("键盘（**物理码 vs 布局 vs 输入法**）")
    for f in KEYBOARD_FIELDS:
        print(f"   · {f}")
    print("\n规则:")
    for r in KEYBOARD_RULES:
        print(f"   {r}")
    return 0


def cmd_gamepad(a):
    _hdr("手柄（🔴 **至少三个独立死区，不能只写一个 0.1**）")
    for k, why in GAMEPAD_DEADZONES:
        print(f"\n   【{k}】{why}")
    print("\n其余必录:")
    for f in GAMEPAD_FIELDS:
        print(f"   · {f}")
    print("\n注意:")
    for n in GAMEPAD_NOTE:
        print(f"   {n}")
    return 0


def cmd_touch(a):
    _hdr("触摸与体感")
    print("触屏: " + " · ".join(TOUCH_FIELDS))
    print("\n陀螺仪: " + " · ".join(GYRO_FIELDS))
    print(f"\n{GYRO_RULE}")
    print("\n🔑 触屏、体感与无障碍必须**进入同一张输入时间轴**")
    return 0


def cmd_a11y(a):
    _hdr("无障碍输入")
    for f in A11Y_FIELDS:
        print(f"   · {f}")
    return 0


def cmd_savechain(a):
    _hdr("跨版本存档**迁移链**")
    for s in SAVE_CHAIN:
        print(f"   {s}")
    print("\n字段迁移至少区分:")
    for f in SAVE_FIELD_MIGRATIONS:
        print(f"   · {f}")
    print(f"\n⚠️ {SAVE_NOTE}")
    return 0


def cmd_ops(a):
    _hdr("运营时间与赛季")
    for f in OPS_TIME:
        print(f"   · {f}")
    print("\n规则:")
    for r in OPS_RULE:
        print(f"   {r}")
    return 0


def cmd_crash(a):
    _hdr("崩溃诊断与日志")
    print("崩溃: " + " · ".join(CRASH_FIELDS))
    print("\n日志: " + " · ".join(LOG_FIELDS))
    print("\n⚠️ 崩溃日志是否上传、上传哪些字段、是否可离线查看 —— "
          "**必须以原版行为为准**")
    return 0


def cmd_voice(a):
    _hdr("🔴 声音优先级与 voice stealing")
    for v in VOICE_STEALING:
        print(f"   {v}")
    print("\n音频性能:")
    for p in AUDIO_PERF:
        print(f"   · {p}")
    return 0


def cmd_init(a):
    os.makedirs(os.path.dirname(a.init) or ".", exist_ok=True)
    with open(a.init, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow([k for k, _ in FIELDS])
        w.writerow(["TODO"] * len(FIELDS))
    print(f"已生成输入/运营表: {a.init}")
    print("\n⚠️ 九域：mouse / keyboard / gamepad / touch / a11y / "
          "savechain / ops / crash / voice")
    return 0


def cmd_check(a):
    if not os.path.exists(a.check):
        print(f"❌ 文件不存在: {a.check}")
        return 2
    with open(a.check, encoding="utf-8", errors="replace", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        print("❌ 空表")
        return 1

    def g(r, k):
        return (r.get(k) or "").strip()

    mismatch, no_legacy = [], []
    for i, r in enumerate(rows, 1):
        m = g(r, "match").lower()
        if m not in ("yes", "y", "true", "是", "一致"):
            mismatch.append(i)
        if not g(r, "legacy_value") or g(r, "legacy_value") == "TODO":
            no_legacy.append(i)

    print("=" * 76)
    print(f"输入/运营 · {len(rows)} 条")
    print("=" * 76)
    if mismatch:
        print(f"\n🚫 **不一致** {len(mismatch)} 条（行 {mismatch[:15]}）")
        print("   → 输入设备参数是最直接的手感来源")
    if no_legacy:
        print(f"\n❌ {len(no_legacy)} 条缺**原版值**（行 {no_legacy[:15]}）")

    if not (mismatch or no_legacy):
        print("\n✅ 输入/运营：一致且原版值完整")

    print("\n🔑 **手柄三个独立死区**；**KeyW 不许写死扫描码**；")
    print("   **先确认原版走原始输入还是系统指针**。")
    print("   **存档是迁移链，不是读旧版本**。")
    return 1 if (a.gate and (mismatch or no_legacy)) else 0


def main():
    ap = argparse.ArgumentParser(description="输入深化/存档链/崩溃/音频预算")
    ap.add_argument("--mouse", action="store_true")
    ap.add_argument("--keyboard", action="store_true")
    ap.add_argument("--gamepad", action="store_true")
    ap.add_argument("--touch", action="store_true")
    ap.add_argument("--a11y", action="store_true")
    ap.add_argument("--savechain", action="store_true")
    ap.add_argument("--ops", action="store_true")
    ap.add_argument("--crash", action="store_true")
    ap.add_argument("--voice", action="store_true")
    ap.add_argument("--init")
    ap.add_argument("--check")
    ap.add_argument("--gate", action="store_true")
    a = ap.parse_args()
    fns = {"mouse": cmd_mouse, "keyboard": cmd_keyboard, "gamepad": cmd_gamepad,
           "touch": cmd_touch, "a11y": cmd_a11y, "savechain": cmd_savechain,
           "ops": cmd_ops, "crash": cmd_crash, "voice": cmd_voice}
    for k, fn in fns.items():
        if getattr(a, k):
            return fn(a)
    if a.init:
        return cmd_init(a)
    if a.check:
        return cmd_check(a)
    print("❌ 需要 --mouse / --keyboard / --gamepad / --touch / --a11y / "
          "--savechain / --ops / --crash / --voice / --init / --check 之一")
    return 2


if __name__ == "__main__":
    sys.exit(main())
