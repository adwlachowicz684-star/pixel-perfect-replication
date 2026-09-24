#!/usr/bin/env python3
"""时间域与暂停语义 + 帧 pacing + 抗锯齿（第九轮 A / F / G 类）。

**🔑 A 类核心**：
> **一张全局 `timeScale` 无法覆盖原游戏的暂停体验** ——
> 必须用**时钟域 + 子系统暂停掩码**表达。
>
> 最典型的四种失真必须**分别记录**，不能合并成"完全/不完全暂停"：
> 菜单动画继续但世界逻辑继续 · 冷却不走但 UI 动画走 ·
> 粒子停但音乐停 · AI 冻结但布娃娃和受伤判定仍演化

**🔑 F 类核心**：
> **若原作让伤害次数、跳跃高度、Buff 时长依赖帧率，
> "固定逻辑步长 + 真实时间插值"虽然更稳，却不是复刻。**

**🔑 G 类核心**：
> **TAA 的"静止画面表现"是图像一致性问题，不是性能优化** ——
> 相机不动时是否仍有像素闪烁、UI 停止后是否留残影。

用法:
  game_time_pacing.py --timedomain  # 时钟域 + 暂停掩码
  game_time_pacing.py --timer       # 🔴 计时器**五个字段**，不能写 t -= dt
  game_time_pacing.py --scale       # 🔴 乘法链 vs 覆盖链
  game_time_pacing.py --slowmo      # 慢动作**输入采样率**须单独写进合同
  game_time_pacing.py --dilation    # dilation vs scale 术语规范
  game_time_pacing.py --pacing      # 帧 pacing 是**时间预算**
  game_time_pacing.py --refresh     # 刷新率是**动态可观测变量**
  game_time_pacing.py --aa          # 🔴 AA 是画面合同
  game_time_pacing.py --taa         # TAA 静止画面与残影
  game_time_pacing.py --init ledger/time_pacing.csv
  game_time_pacing.py --check ledger/time_pacing.csv --gate

退出码: 0 通过 / 1 缺项 / 2 用法错误
"""
import argparse
import csv
import os
import sys

# 时钟域
CLOCK_IDS = [
    "realtime", "game", "fixed", "animation", "particle",
    "audio", "ui", "network",
]

TIME_DOMAIN_FIELDS = [
    ("clock_id", "realtime / game / fixed / animation / particle / audio / ui / network"),
    ("pause_contract", "running / paused / **independent**"),
    ("scale_operator", "**set / multiply / clamp / inherit**"),
    ("owner", "所属子系统，例如 AI、physics、animation"),
    ("sample_rate_hz", "**逻辑采样上限；慢动作时是否变化**"),
    ("affected_timers", "冷却、Buff、状态机、输入缓冲、陷阱、限时目标"),
    ("observed_case", "可复现场景、输入序列、前后状态"),
    ("must_match", "与原游戏逐帧结果是否一致"),
]

TIME_ENGINE = [
    "⚠️ Unity 的 `deltaTime` 受 `timeScale` 与 `maximumDeltaTime` 影响，"
    "而 `unscaledDeltaTime` **不按同一规则钳制** —— "
    "不能把「不受缩放」理解为「物理真实时间」",
    "⚠️ `WaitForSeconds` 与定时器等也需**逐项验证**",
    "⚠️ Unreal 有全局 dilation、Actor/Component **层级 dilation** 与 "
    "**tick group** 的组合 —— **不能只记录一个全局值**",
    "🔑 必须写明「**原引擎语义**」和「**目标引擎映射**」 —— "
    "避免把旧项目的时间 bug 翻译成目标引擎的新 bug",
]

# 计时器五字段
TIMER_FIELDS = [
    "**clock**", "**auto_pause**", "cap_at_zero",
    "**catch_up_policy**", "wraparound_policy",
]

TIMER_RULE = [
    "🔴 计时器语义应在**数据层声明**，"
    "不能在 `Update` 里随手写 `t -= dt`",
    "🔑 开菜单时若原作**冷却继续**，复刻也必须继续",
    "🔑 若 UI 技能图标使用另一时钟，则**图标动画不能成为时间证据**",
    "🔑 输入缓冲窗口四种不同体验：菜单内采样停止 / 输入仍被缓冲 / "
    "输入立即消费 / **跨暂停保留**",
    "🔑 教程、检查点、Boss 重试的「已看/已失败/已解锁」应归入独立 "
    "`MetaProgress` 域，**避免与角色存档混写**",
]

# 🔴 乘法链 vs 覆盖链
SCALE_RULE = [
    "🔴 **`scale = 0.5` 与 `scale *= 0.5` 不是同义** —— "
    "后者会令多重 slow-motion 叠加后**迅速逼近冻结**",
    "🔴 多个系统写入同一全局变量时，**结束顺序还会改变最终值**",
    "✅ 推荐 `target_scale + multiplier tree + override_priority`："
    "每个时间域有目标值 · 子系统乘数为独立节点 · "
    "**暂停为最高优先级覆盖** · 持续时间结束按**栈式 owner 回退**",
]

# 慢动作
SLOWMO_FIELDS = [
    "进入曲线（linear / ease_in / **instant**）",
    "进入是否消耗一帧",
    "退出曲线是否对称、是否允许被打断、打断后是否回到原速度",
    "进入触发窗口（伤害判定帧 / 相机锁定帧 / **玩家输入冻结帧**）",
    "持续时间（固定时长 / 事件结束 / 可被打断）",
    "受影响系统（逻辑/动画/粒子/物理/音频/镜头）",
    "**fixed-step 策略**（保持真实时间步数 / 保持游戏时间步数 / 允许丢失 tick）",
    "**输入采样**（慢动作期间是否仍按真实 60/120Hz 采样，还是被降频）",
    "网络/回放（是否进入确定性模式、是否允许客户端自行变速）",
    "**多效果优先级**（Buff、顿帧、死亡、Pause、结算同时触发时的裁决顺序）",
]

SLOWMO_RULE = [
    "🔴 **慢动作下的输入采样率必须单独写进合同**，"
    "**不能由帧 pacing 隐含决定**",
    "🔑 若逻辑时间放慢到 20% 但输入仍按真实 1000Hz 采样 → "
    "长 press、双击窗口、连招缓冲和摇杆轨迹会与正常速度不同",
    "🔑 若采样也被缩放 → 玩家主观操作感会变「**钝**」",
    "🔑 这**不是「延迟问题」**，而是**时间域问题**",
]

# dilation vs scale
DILATION_RULE = [
    "🔑 `Time.dilation` 与 `Time.scale` **可以同名，却可能是两套架构**",
    "✅ 内部规范固定为：",
    "   `dilation` = 某系统相对游戏时钟的**可观测速率**",
    "   `scale`    = 驱动它的**参数**",
    "🔑 于是 Bullet Time 可写成"
    "「游戏逻辑 dilation 0.3 · 相机动画 1.0 · 音频 1.0 · "
    "**输入采样保持真实时间**」，而不是一句含糊的「时间变慢」",
]

# 帧 pacing
PACING_FIELDS = [
    "目标 FPS", "**帧上限策略**", "**后台节流**", "最小/最大步长",
    "**掉帧补偿**", "交换间隔", "显示刷新率", "**VRR 状态**",
    "tearing policy", "**GPU 队列深度**", "CPU/GPU 时序",
    "**垂直同步失败回退**",
]

PACING_DIFF = [
    "无同步时**长短帧**", "vsync 下**等待 VBlank**",
    "VRR 下**动态刷新**", "帧生成时**原始帧/合成帧区分**",
]

PACING_RULE = [
    "🔑 帧 pacing 是**时间预算**，不是锁帧开关",
    "🔴 **后台节流会改变冷却、动画、网络、音频调度与输入重放窗口** —— "
    "不能只标「降低帧率」",
]

REFRESH_FIELDS = [
    "原生刷新率", "当前模式", "**可变刷新范围**", "最小稳定帧率",
    "最大预渲染帧", "**分辨率切换后的刷新率**",
    "**HDR/窗口模式切换**", "**热插拔与多显示器主屏变化**",
]

REFRESH_RULE = [
    "🔑 刷新率**不是启动配置**，而是一组**动态可观测变量**",
    "🔑 120/144/240Hz 的差异**不仅是动画更顺** —— "
    "物理子步 · 输入采样 · 固定 tick · 慢动作倍率 · 后处理累积 · "
    "触摸/手柄轮询都可能产生**新行为**",
]

# 🔴 AA
AA_FIELDS = [
    "方案（MSAA / TAA / FXAA / SMAA / DLAA / **TAAU**）",
    "采样数", "是否使用**深度/速度/法线重投影**",
    "**jitter pattern**", "**历史帧数**", "响应曲线",
    "**静止帧钳制**", "最小/最大 velocity",
    "**UI/半透明处理**", "粒子/贴花/体积雾处理",
    "**alpha-tested 边缘**", "输出分辨率", "动态分辨率",
    "**超分耦合**", "HDR 格式", "**色调映射顺序**", "运动向量来源",
]

AA_RULE = [
    "🔑 **AA 是完整渲染路径的一部分** —— "
    "替换方案会改变**静止画面、UI、半透明与历史累积**",
    "❌ 不能只写「高画质」 —— 若目标引擎把 jitter、TAA、TAAU、FSR/DLSS "
    "打包为「质量档」，**必须拆开记录**",
    "🔴 否则同一 must-match 项目会在低画质档**悄悄改变历史长度、"
    "抖动幅度和动态分辨率**",
]

TAA_STATIC = [
    "相机不动、角色不动时**是否仍有像素闪烁**",
    "**UI 移动后停止是否留下残影**",
    "**半透明特效是否污染历史**",
    "**粒子突然消失是否产生拖影**",
    "**遮挡关系切换时是否保持一帧 ghost**",
]

TAA_RULE = [
    "🔑 这些**不是性能优化，而是图像一致性**",
]

TAA_JITTER = [
    "jitter 模式", "相位数", "旋转 / Halton / **R2 序列**",
    "**重投影偏移**", "**历史样本权重**", "**disocclusion 处理**",
]

CONFLICTS = [
    "❌ **全局 `timeScale = 0` / 全局 pause flag / 简单 `SetActive(false)`** —— "
    "把暂停语义压成全有或全无，UI tick、音频 source、粒子、动画通知"
    "被同一个开关错误冻结",
    "❌ **「固定逻辑步长 + 真实时间插值」当正确答案** —— "
    "若原作明确让机制依赖帧率，这不是复刻，须标 `frame_coupled` 逐项决定",
    "❌ **把帧率与游戏机制解耦**（主流实践）可能与原作 must-match 冲突",
    "❌ **现成 TAA 开源实现直接套用** —— 只适合做差异测试",
    "❌ **TAA 抖动与超分解耦**可能掩盖采样缺口",
    "🔑 引擎内置暂停开关仅用于**参考实现或原型**；"
    "最终生产必须使用**原游戏的时钟域映射**",
]

FIELDS = [
    ("item_id", "项编号"),
    ("domain", "域（timedomain / timer / scale / slowmo / pacing / refresh / aa / taa）"),
    ("legacy_value", "**原版值**"),
    ("new_value", "新引擎值"),
    ("match", "**是否一致**"),
    ("clock_id", "**所属时钟域**"),
    ("evidence", "证据"),
]


def _hdr(t, w=80):
    print("=" * w)
    print(t)
    print("=" * w)


def cmd_timedomain(a):
    _hdr("🔴 时间域（**一张 timeScale 覆盖不了**）")
    print("clock_id: " + " · ".join(CLOCK_IDS))
    print("\nTimeDomainRecord 字段:")
    for k, why in TIME_DOMAIN_FIELDS:
        print(f"\n   【{k}】{why}")
    print("\n引擎差异（也是取证内容）:")
    for e in TIME_ENGINE:
        print(f"   {e}")
    return 0


def cmd_timer(a):
    _hdr("🔴 计时器（**不能写 t -= dt**）")
    for f in TIMER_FIELDS:
        print(f"   · {f}")
    print("\n规则:")
    for r in TIMER_RULE:
        print(f"   {r}")
    return 0


def cmd_scale(a):
    _hdr("🔴 时间缩放（**乘法链 vs 覆盖链**）")
    for r in SCALE_RULE:
        print(f"   {r}")
    return 0


def cmd_slowmo(a):
    _hdr("慢动作（🔴 **输入采样率须单独写进合同**）")
    for f in SLOWMO_FIELDS:
        print(f"   · {f}")
    print("\n规则:")
    for r in SLOWMO_RULE:
        print(f"   {r}")
    return 0


def cmd_dilation(a):
    _hdr("dilation vs scale（**术语规范**）")
    for r in DILATION_RULE:
        print(f"   {r}")
    return 0


def cmd_pacing(a):
    _hdr("帧 pacing（**时间预算，不是锁帧开关**）")
    for f in PACING_FIELDS:
        print(f"   · {f}")
    print("\n需复现的差异: " + " · ".join(PACING_DIFF))
    print("\n规则:")
    for r in PACING_RULE:
        print(f"   {r}")
    return 0


def cmd_refresh(a):
    _hdr("刷新率（**动态可观测变量**）")
    for f in REFRESH_FIELDS:
        print(f"   · {f}")
    print("\n规则:")
    for r in REFRESH_RULE:
        print(f"   {r}")
    return 0


def cmd_aa(a):
    _hdr("🔴 抗锯齿（**画面合同**）")
    for f in AA_FIELDS:
        print(f"   · {f}")
    print("\n规则:")
    for r in AA_RULE:
        print(f"   {r}")
    return 0


def cmd_taa(a):
    _hdr("TAA 静止画面与残影")
    print("静止画面必测:")
    for t in TAA_STATIC:
        print(f"   · {t}")
    print("\njitter: " + " · ".join(TAA_JITTER))
    print("\n规则:")
    for r in TAA_RULE:
        print(f"   {r}")
    return 0


def cmd_init(a):
    os.makedirs(os.path.dirname(a.init) or ".", exist_ok=True)
    with open(a.init, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow([k for k, _ in FIELDS])
        w.writerow(["TODO"] * len(FIELDS))
    print(f"已生成时间/pacing 表: {a.init}")
    print("\n⚠️ 八域：timedomain / timer / scale / slowmo / pacing / "
          "refresh / aa / taa")
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

    mismatch, no_legacy, no_clock = [], [], []
    for i, r in enumerate(rows, 1):
        m = g(r, "match").lower()
        if m not in ("yes", "y", "true", "是", "一致"):
            mismatch.append(i)
        if not g(r, "legacy_value") or g(r, "legacy_value") == "TODO":
            no_legacy.append(i)
        c = g(r, "clock_id")
        if not c or c == "TODO":
            no_clock.append(i)

    print("=" * 76)
    print(f"时间/pacing/AA · {len(rows)} 条")
    print("=" * 76)
    if mismatch:
        print(f"\n🚫 **不一致** {len(mismatch)} 条（行 {mismatch[:15]}）")
    if no_legacy:
        print(f"\n❌ {len(no_legacy)} 条缺**原版值**（行 {no_legacy[:15]}）")
    if no_clock:
        print(f"\n⚠️  {len(no_clock)} 条**未声明所属时钟域**（行 {no_clock[:15]}）")
        print("   → 🔴 计时器必须显式声明 clock，"
              "**不能默认共用一个 deltaTime**")

    if not (mismatch or no_legacy):
        print("\n✅ 时间/pacing/AA：一致且原版值完整")

    print("\n🔑 **scale = 0.5 与 scale *= 0.5 不是同义。**")
    print("   **慢动作的输入采样率须单独写进合同。**")
    print("   **TAA 静止画面表现是图像一致性，不是性能优化。**")
    return 1 if (a.gate and (mismatch or no_legacy)) else 0


def main():
    ap = argparse.ArgumentParser(description="时间域/pacing/抗锯齿")
    ap.add_argument("--timedomain", action="store_true")
    ap.add_argument("--timer", action="store_true")
    ap.add_argument("--scale", action="store_true")
    ap.add_argument("--slowmo", action="store_true")
    ap.add_argument("--dilation", action="store_true")
    ap.add_argument("--pacing", action="store_true")
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--aa", action="store_true")
    ap.add_argument("--taa", action="store_true")
    ap.add_argument("--init")
    ap.add_argument("--check")
    ap.add_argument("--gate", action="store_true")
    a = ap.parse_args()
    fns = {"timedomain": cmd_timedomain, "timer": cmd_timer, "scale": cmd_scale,
           "slowmo": cmd_slowmo, "dilation": cmd_dilation, "pacing": cmd_pacing,
           "refresh": cmd_refresh, "aa": cmd_aa, "taa": cmd_taa}
    for k, fn in fns.items():
        if getattr(a, k):
            return fn(a)
    if a.init:
        return cmd_init(a)
    if a.check:
        return cmd_check(a)
    print("❌ 需要 --timedomain / --timer / --scale / --slowmo / --dilation / "
          "--pacing / --refresh / --aa / --taa / --init / --check 之一")
    return 2


if __name__ == "__main__":
    sys.exit(main())
