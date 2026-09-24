#!/usr/bin/env python3
"""输入到光子延迟 + 相机系统（深化第四轮 A / C 类）。

**🔑 A 类核心**：
> **延迟不是单一帧时间，而是九段累加链路。**
> 迁移只比对帧率会漏掉它 —— **逻辑未变，手感已变**。

最反直觉的一条：**DXGI 默认会在第三个已排队 Present 之后阻塞**
（即第四份 Present 才等待）—— 默认实现就可能多约**三帧**显示延迟。

**🔑 C 类核心**：
> **相机不是 Transform 快照，而是有独立响应特性的控制系统。**

用法:
  game_latency_camera.py --chain       # 九段延迟链路
  game_latency_camera.py --measure     # 测量方法与校准
  game_latency_camera.py --sync        # 垂直同步/VRR 与**禁用项**
  game_latency_camera.py --timeline    # 引擎中立 InputTimeline
  game_latency_camera.py --camera      # 第三人称八个耦合子系统
  game_latency_camera.py --shake       # 震屏（**确定性最容易坏**）
  game_latency_camera.py --fov         # FoV 会改观感速度
  game_latency_camera.py --fp          # 第一人称感知链路
  game_latency_camera.py --init ledger/latency_camera.csv
  game_latency_camera.py --check ledger/latency_camera.csv --gate

退出码: 0 通过 / 1 缺项 / 2 用法错误
"""
import argparse
import csv
import os
import sys

# 九段链路
CHAIN = [
    "按键接触抖动与去抖",
    "控制器轮询 / 无线链路",
    "USB 传输与主机中断",
    "OS / 驱动分发",
    "**引擎消息泵或输入轮询**",
    "逻辑帧推进",
    "动画 / 物理变换",
    "渲染提交与 command buffer",
    "合成器 → 扫描输出",
]

CHAIN_NOTE = [
    "🔑 再加上控制器振动反馈与显示实际光子输出，"
    "形成完整 **click-to-photon / click-to-vibration**",
    "⚠️ 原游戏录像的「视觉开始时间」**不能等同于「输入被采样时间」** —— "
    "两个客户端实现可能看起来同样正确，却感觉不同",
]

# 延迟工具
LATENCY_TOOLS = [
    ("NVIDIA Reflex", "NVIDIA-RTX/REFLEX", "引擎埋点：sleep mode、PC latency、flash indicator",
     "⚠️ 依赖 NVIDIA GPU/驱动/兼容显示器；**不是跨平台标准**"),
    ("Open-Source-LDAT", "S4N-T0S/Open-Source-LDAT",
     "DIY click-to-photon（Teensy 4.1 + TEMT6000 + OLED + 按键）",
     "许可证待最终确认；适合平台中立冒烟测量"),
    ("G2GDelay", "cbachhuber/G2GDelay", "低预算 G2G 基线（Arduino/Android/Python）",
     "⚠️ 精度与传感器、阈值、样本强相关，**不可直接当像素级绝对基准**"),
    ("arduino-latency-test", "sqwk/arduino-latency-test", "MIT；Arduino UNO + LED + 光敏电阻",
     "最简单光电闭环原型；缺多通道与严格时序验证"),
    ("Optick", "linux-automation（厂商原型）", "21ns 分辨率双通道",
     "偏视频链路；可借双通道做屏幕顶部/底部撕裂测量"),
]

MEASURE_FIELDS = [
    "min / median / **p95 / p99**", "标准差", "直方图", "丢帧计数",
    "**光传感器阈值校准值**",
]

MEASURE_CALIBRATION = [
    "🔑 高速摄像机法：LED 并置按键，同时拍屏幕，数 LED 亮起到屏幕反应帧",
    "🔑 闭环法（精度更高）：单片机同时记录按键与光敏管边沿 —— "
    "**必须先把 LED 与传感器直触测得零点并扣除偏移**",
    "🔑 DUT 侧加**纯输入反应测试**：输入事件改变屏幕指定矩形颜色，"
    "矩形**只读取刚被采样到的输入**，不能读上帧缓存",
]

MEASURE_CHECKS = [
    "传感器量程未饱和", "屏幕最大亮度", "**关闭自动曝光**",
    "**关闭动态背光**", "**禁用可变刷新率或记录当前状态**",
]

# swap chain 必录字段
SWAPCHAIN_FIELDS = [
    "**缓冲数量**", "**最大排队帧**", "present 同步间隔", "等待可对象",
    "**flip / blt 模式**", "全屏独占 / 无边框", "composition rate",
    "tearing 允许标志", "GPU 反压",
    "**输入采样位于逻辑开始前 / 中 / 后**",
]

LATENCY_GATE = [
    "🔑 **双层门禁**：",
    "   ① 绝对门禁：原版 p50/p95/p99 **+3 ms**",
    "   ② 相对门禁：**同硬件、同显示器、同一测试路线**",
    "⚠️ 门禁**不应只设阈值**",
]

SYNC_MODELS = [
    ("固定刷新同步", "稳定扫描输出、最小撕裂", "最多增加约**一帧排队**"),
    ("无同步", "把最新完成帧送合成器、丢弃旧帧", "减少排队但**可能撕裂**"),
    ("VRR / G-Sync / FreeSync", "扫描周期跟随 GPU 完成时间", "**并非零延迟**"),
]

SYNC_FIELDS = [
    "显示器处理延迟", "**Overdrive 档位**", "运动模糊降低（ULMB 等）",
    "背光频闪", "帧倍频 / 插黑", "**扫描延迟**",
]

SYNC_RULE = [
    "🔴 若原版跑在 **60 Hz 垂直同步、采样于逻辑帧首**，"
    "而复刻跑在 **120 Hz 无同步、采样于渲染前** ——",
    "   **即使帧预算相同，也绝不应标记为功能一致**。",
]

# 引擎中立 InputTimeline
TIMELINE_FIELDS = [
    "**输入硬件时间戳**", "OS 投递时间", "消息泵时间",
    "模拟开始 / 结束", "GPU 开始 / 结束", "present", "**scan-out estimate**",
]

TIMELINE_RULE = [
    "🔑 建立**引擎中立** `InputTimeline`，各后端填平台能拿到的字段",
    "⚠️ 平台专有 SDK（Reflex / Anti-Lag / Intel）**可以验证，"
    "但不得替代跨平台取证协议**",
]

# 相机：第三人称八个耦合子系统
CAMERA_SUBSYS = [
    ("理想位置", "pivot、distance、height、**shoulder offset**、yaw/pitch、min/max pitch、up vector、正交化规则"),
    ("输入响应", "死区、灵敏度、**指数曲线**、轴向独立灵敏度、加速度、匀速/阻尼模式、输入平滑"),
    ("跟随", "位置/旋转/分轴弹簧、**critically damped smoothing**、指数衰减、最大速度"),
    ("**碰撞**", "raycast/spherecast/capsulecast、layer mask、**碰撞半径/缓冲距离**、回缩插值、卡墙恢复、近裁切保护"),
    ("遮挡", "fade-in/out、对象替换、轮廓可见性、仅遮挡对象集合、cross-fade 时间"),
    ("预测", "velocity/acceleration prediction、yaw 追随、瞄准偏移、命中目标影响"),
    ("POI", "target list、priority、weight、fov zoom、look-at height、视线 clearance"),
    ("锁定 / 自由视角", "lock-on range、切换顺序、自动解除、camera assist；clamp、orbit reset、input scale"),
]

CAMERA_FORMULA = [
    "🔑 常见实现 `position = lerp(position, target, 1 - exp(-k*dt))` —— "
    "**「相同 k」在固定步长 60Hz 与可变步长下表现不同**",
    "✅ 更稳妥：显式计算 `exp(-k*dt)` 并**固定采样位置**",
    "必存字段：smooth coefficient · exp 系数 · **collision margin** · "
    "near clip · raycast from height · recover speed · 分轴 clamp",
    "⚠️ 缓冲距离过短 → 近裁面贴墙，**一帧穿透一帧遮挡的闪烁**；"
    "过长 → 角色头部占屏过多",
]

CAMERA_TRACE = [
    "世界时间", "real deltaTime", "smooth deltaTime",
    "camera pose/orientation/**FoV**", "player pose/velocity/acceleration",
    "input", "target pose", "**raycast hit**", "occluder layer",
    "collider bounds", "animation root motion", "gameplay state",
]

CAMERA_METHOD = "🔑 固定种子 + 固定控制器 + 固定输入时间序列，原版与复刻**相同操作序列回放**"

# 震屏：**确定性最容易坏**
SHAKE_FIELDS = [
    "trauma", "intensity", "frequency", "**decay curve**", "duration",
    "blend-in/out", "**rotation/translation 比例**", "**noise seed**",
    "noise axis offset", "per-axis enable", "frame count",
    "**timescale 影响**", "camera shake scale", "listener 状态",
]

SHAKE_RULES = [
    "🔴 原版若用 `time += dt*frequency`，复刻**不得改成基于 `Time.time` 的全局噪声** —— "
    "切场景、暂停、慢动作或不同帧率会**改变相位**",
    "🔑 纯随机适合爆炸瞬间；**持续震动几乎总应使用连续噪声**",
    "🔑 必须记录是 Perlin/Simplex 1D/2D、**多个独立 axis seed**，"
    "还是同一低维噪声采不同坐标",
    "⚠️ 旋转与平移的耦合、相机 roll、viewmodel shake 与 head bob"
    "**必须分轨，不能合并成「shake 强度」**",
]

FOV_FIELDS = [
    "**水平 FoV 与垂直 FoV**", "宽高比换算",
    "ADS / sprint / vehicle / interaction 的 **zoom 曲线**",
    "zoom duration/ease", "**viewmodel FoV**", "near/far clip",
    "motion sickness 安全区", "**瞄准灵敏度补偿**", "replays/photo mode override",
]

FOV_RULES = [
    "🔑 **FoV 会改观感速度** —— 不能只当「看起来更广」",
    "🔑 渲染宽高比变化时，必须显式记录是**锁定 horizontal 还是 vertical FoV** —— "
    "二者可见范围与透视变形不同",
    "⚠️ FoV 变化还会改变地面纹理移动速度、动画视差、遮挡频率、景深感知"
    " → **要与 input response 一起回归**",
]

FP_FIELDS = [
    "**head bob** cycle/phase/**step event source**",
    "vertical/horizontal displacement", "velocity remap",
    "landing/falling additive", "weapon/viewmodel sway", "idle drift",
    "breathing", "走路惯性", "viewmodel FoV/position/rotation",
    "吸附", "瞄准回正", "camera roll", "base/local space",
    "帧时间影响", "disable 条件",
]

FP_TRAPS = [
    "⚠️ 若 bob 读取**动画 normalized time** 而原版读取**真实步频** —— "
    "换速度或插入打断动画后，复刻的呼吸节奏会**漂移**",
    "⚠️ 相机轻微 roll 与震屏 rotation 若在同一 space 简单相加 —— "
    "**锁定瞄准时可能产生不应出现的倾斜**",
]

FIELDS = [
    ("item_id", "项编号"),
    ("domain", "域（latency / swapchain / sync / timeline / camera / shake / fov / fp）"),
    ("legacy_value", "**原版值**"),
    ("new_value", "新引擎值"),
    ("match", "**是否一致**"),
    ("measurement_method", "测量方法（**必须可复现**）"),
    ("evidence", "证据"),
]


def _hdr(t, w=80):
    print("=" * w)
    print(t)
    print("=" * w)


def cmd_chain(a):
    _hdr("🔴 输入到光子：九段累加链路（**逻辑未变，手感已变**）")
    for i, c in enumerate(CHAIN, 1):
        print(f"   {i}. {c}")
    print("")
    for n in CHAIN_NOTE:
        print(f"   {n}")
    print("\n工具:")
    for name, repo, what, limit in LATENCY_TOOLS:
        print(f"\n   【{name}】{repo}")
        print(f"      {what}")
        print(f"      {limit}")
    return 0


def cmd_measure(a):
    _hdr("测量方法（**必须可复现**）")
    print("输出: " + " · ".join(MEASURE_FIELDS))
    print("\n方法:")
    for m in MEASURE_CALIBRATION:
        print(f"   {m}")
    print("\n强制校验:")
    for c in MEASURE_CHECKS:
        print(f"   · {c}")
    print("\n门禁:")
    for g in LATENCY_GATE:
        print(f"   {g}")
    return 0


def cmd_sync(a):
    _hdr("垂直同步 / VRR（**不能混为同一个延迟模型**）")
    for k, what, cost in SYNC_MODELS:
        print(f"\n   【{k}】{what}")
        print(f"      代价: {cost}")
    print("\n显示侧必录: " + " · ".join(SYNC_FIELDS))
    print("\n规则:")
    for r in SYNC_RULE:
        print(f"   {r}")
    return 0


def cmd_swapchain(a):
    _hdr("🔴 Swap Chain 必录字段（**DXGI 默认三帧队列**）")
    print("🔑 NVIDIA 明确指出：**DXGI 默认会在第三个已排队 Present 之后阻塞**")
    print("   —— 即第四份 Present 调用才等待。")
    print("   设 `DXGI_SWAP_CHAIN_FLAG_FRAME_LATENCY_WAITABLE_OBJECT` 后，")
    print("   可用 `IDXGISwapChain2::SetMaximumFrameLatency` 覆盖默认队列长度。")
    print("\n字段:")
    for f in SWAPCHAIN_FIELDS:
        print(f"   · {f}")
    print("\n门禁:")
    for g in LATENCY_GATE:
        print(f"   {g}")
    return 0


def cmd_timeline(a):
    _hdr("引擎中立 InputTimeline")
    for f in TIMELINE_FIELDS:
        print(f"   · {f}")
    print("\n规则:")
    for r in TIMELINE_RULE:
        print(f"   {r}")
    return 0


def cmd_camera(a):
    _hdr("相机（**不是 Transform 快照，是有独立响应特性的控制系统**）")
    for k, why in CAMERA_SUBSYS:
        print(f"\n   【{k}】{why}")
    print("\n公式与字段:")
    for f in CAMERA_FORMULA:
        print(f"   {f}")
    print("\ntrace 必录: " + " · ".join(CAMERA_TRACE))
    print(f"\n{CAMERA_METHOD}")
    return 0


def cmd_shake(a):
    _hdr("震屏（🔴 **确定性最容易坏的子系统之一**）")
    for f in SHAKE_FIELDS:
        print(f"   · {f}")
    print("\n规则:")
    for r in SHAKE_RULES:
        print(f"   {r}")
    return 0


def cmd_fov(a):
    _hdr("FoV（**会改观感速度，不是「看起来更广」**）")
    for f in FOV_FIELDS:
        print(f"   · {f}")
    print("\n规则:")
    for r in FOV_RULES:
        print(f"   {r}")
    return 0


def cmd_fp(a):
    _hdr("第一人称（**一条感知链路**）")
    for f in FP_FIELDS:
        print(f"   · {f}")
    print("\n极细踩坑:")
    for t in FP_TRAPS:
        print(f"   {t}")
    return 0


def cmd_init(a):
    os.makedirs(os.path.dirname(a.init) or ".", exist_ok=True)
    with open(a.init, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow([k for k, _ in FIELDS])
        w.writerow(["TODO"] * len(FIELDS))
    print(f"已生成延迟/相机表: {a.init}")
    print("\n⚠️ 八域：latency / swapchain / sync / timeline / "
          "camera / shake / fov / fp")
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

    no_method, mismatch, no_legacy = [], [], []
    for i, r in enumerate(rows, 1):
        if not g(r, "measurement_method") or g(r, "measurement_method") == "TODO":
            no_method.append(i)
        m = g(r, "match").lower()
        if m not in ("yes", "y", "true", "是", "一致"):
            mismatch.append(i)
        if not g(r, "legacy_value") or g(r, "legacy_value") == "TODO":
            no_legacy.append(i)

    print("=" * 76)
    print(f"延迟/相机 · {len(rows)} 条")
    print("=" * 76)
    if no_method:
        print(f"\n❌ {len(no_method)} 条缺**测量方法**（行 {no_method[:15]}）")
        print("   → 延迟与相机参数**必须可复现测量**，不能凭感觉调")
    if mismatch:
        print(f"\n🚫 **不一致** {len(mismatch)} 条（行 {mismatch[:15]}）")
        print("   → 延迟与相机手感是 must-match，**不许以「性能优化」擅自改**")
    if no_legacy:
        print(f"\n❌ {len(no_legacy)} 条缺**原版值**（行 {no_legacy[:15]}）")

    if not (no_method or mismatch or no_legacy):
        print("\n✅ 延迟与相机：测量可复现、一致、原版值完整")

    print("\n🔑 **只测 FPS 会漏掉延迟** —— 同一平均帧率下，"
          "帧节奏、队列和采样点仍可能完全不同。")
    print("   **DXGI 默认三帧队列**意味着默认实现就可能多约三帧显示延迟。")
    return 1 if (a.gate and (no_method or mismatch or no_legacy)) else 0


def main():
    ap = argparse.ArgumentParser(description="输入延迟与相机系统")
    ap.add_argument("--chain", action="store_true")
    ap.add_argument("--measure", action="store_true")
    ap.add_argument("--sync", action="store_true")
    ap.add_argument("--swapchain", action="store_true")
    ap.add_argument("--timeline", action="store_true")
    ap.add_argument("--camera", action="store_true")
    ap.add_argument("--shake", action="store_true")
    ap.add_argument("--fov", action="store_true")
    ap.add_argument("--fp", action="store_true")
    ap.add_argument("--init")
    ap.add_argument("--check")
    ap.add_argument("--gate", action="store_true")
    a = ap.parse_args()
    fns = {"chain": cmd_chain, "measure": cmd_measure, "sync": cmd_sync,
           "swapchain": cmd_swapchain, "timeline": cmd_timeline,
           "camera": cmd_camera, "shake": cmd_shake, "fov": cmd_fov, "fp": cmd_fp}
    for k, fn in fns.items():
        if getattr(a, k):
            return fn(a)
    if a.init:
        return cmd_init(a)
    if a.check:
        return cmd_check(a)
    print("❌ 需要 --chain / --measure / --sync / --swapchain / --timeline / "
          "--camera / --shake / --fov / --fp / --init / --check 之一")
    return 2


if __name__ == "__main__":
    sys.exit(main())
