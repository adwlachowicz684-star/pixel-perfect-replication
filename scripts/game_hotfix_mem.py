#!/usr/bin/env python3
"""热更新生命周期 / 内存与 GC / 引擎隐藏默认值（第七轮 C / F / G 类）。

**🔑 C 类核心**：
> 热更新记录的是**版本生命周期**，不是编辑器打包按钮。
> 运行时内容交付至少**八态**：清单→下载→校验→原子落盘→激活→回滚→
> 失败隔离→过期清理。

**🔑 F 类核心**：
> 内存回归要检查**卸载后的反向根** —— 常见路径**不是对象未 Dispose**，
> 而是事件、静态缓存、未完成异步句柄、协程、DontDestroyOnLoad、资源引用、
> 调试可视化或 Profiler 采样仍持有对象。

**🔑 G 类核心**：
> 迁移差异最大的**不是手写的 10%，而是另外 90% 的未配置默认值**。

用法:
  game_hotfix_mem.py --hotfix       # 🔴 八态生命周期
  game_hotfix_mem.py --rollback     # 回滚与断点续传**不能靠框架声称**
  game_hotfix_mem.py --depgraph     # 依赖图：引用关系 + 生命周期关系
  game_hotfix_mem.py --serialize    # 对象持久化：稳定 ID 与引用修复
  game_hotfix_mem.py --gc           # 🔴 每帧分配与 GC 卡顿
  game_hotfix_mem.py --snapshot     # 内存快照**五个点**
  game_hotfix_mem.py --defaults     # 🔴 三引擎隐藏默认值表
  game_hotfix_mem.py --verify       # 默认值差异的验证清单
  game_hotfix_mem.py --init ledger/hotfix_mem.csv
  game_hotfix_mem.py --check ledger/hotfix_mem.csv --gate

退出码: 0 通过 / 1 缺项 / 2 用法错误
"""
import argparse
import csv
import os
import sys

# 🔴 热更新八态
HOTFIX_STATES = [
    ("版本探测", "本地版本、远端版本、渠道、灰度、AB 组",
     "首启、弱网、回退版本", "version_source / rollout_group"),
    ("清单", "manifest hash、内容 hash、签名、大小、依赖图",
     "篡改、截断、重复字段", "manifest_schema_version"),
    ("下载", "并发、重试、退避、断点、限速",
     "断网续传、低电量、后台回前台", "resume_cursor / retry_policy"),
    ("校验", "完整文件、依赖闭包、平台格式",
     "半写入、错误包、磁盘满", "verify_algorithm / expected_hash"),
    ("**原子提交**", "临时目录、提交点、旧版本保留数",
     "校验后崩溃、覆盖后失败", "staging_dir / commit_point"),
    ("**回滚**", "可回滚版本、失败条件、数据迁移反向",
     "新资源崩溃、旧逻辑不兼容新数据", "rollback_frontier"),
    ("激活", "热替换窗口、引用兼容、对象重生",
     "战斗中换包、加载屏退出", "activation_gate"),
    ("清理", "LRU、最低保留、依赖锁、下载缓存",
     "低端机反复下载", "retain_min / evict_policy"),
]

HOTFIX_RULE = [
    "🔑 **回滚和断点续传必须显式写入，不能用「下载框架支持」代替**",
    "🔑 临时文件**只在完整校验后**才进入可激活目录",
    "🔑 激活版本应和**存档 schema 版本绑定**",
    "🔴 不能回滚代码时，**资源降级也必须停止**",
]

HOTFIX_CACHE = [
    "重启后从哪个 byte 续传", "catalog 与 bundle 是否同版本",
    "**半下载 catalog 会不会污染下一次探测**",
    "取消后临时文件是否计入预算",
]

# 依赖图
DEP_REF = [
    "直接", "传递", "**软引用**", "**代码反射引用**", "编辑器-only 引用",
]

DEP_LIFECYCLE = [
    "加载顺序", "初始化顺序", "就绪事件", "卸载顺序",
    "**反向依赖**", "强/弱引用",
]

DEP_REDUNDANT = [
    "🔑 冗余资产**不能只看「两个包都有」** —— "
    "还要判断是否因不同 mip、平台、压缩、变体或实例化方式产生",
]

DEP_CYCLE = [
    "🔑 循环依赖**不能只报错误** —— "
    "要记录桥接共享包、接口包、延迟绑定与运行时 Patch 路径",
]

# 序列化
SER_STABLE_ID = [
    "GUID", "局部路径", "命名 ID", "序列号", "**生成规则**",
]

SER_REF_TYPES = [
    "强", "弱", "软", "延迟", "**跨场景**", "运行时临时",
]

SER_FIELDS = [
    ("稳定 ID", "重建世界后引用丢失；覆盖安装后 ID 变化", "stable_id / authority"),
    ("引用修复", "跨场景引用空值；旧存档指向已删除对象", "reference_fixup_order"),
    ("版本演进", "旧字段默认值变化；迁移重复执行", "schema_version / migrations"),
    ("**未知字段**", "新版本读到旧数据表现不同", "unknown_field_policy"),
    ("预制件变体", "父预制件改后子变体不更新；覆盖被吞", "prefab_chain / overrides"),
    ("数据资产", "运行时修改跨场景保留或丢失", "data_asset_lifetime"),
    ("跨场景引用", "场景卸载后悬空；返回后重生对象", "cross_scene_binding"),
]

SER_RULE = [
    "🔑 版本化格式必须区分「**兼容**」和「**可复刻**」 —— "
    "兼容只保证能读，**不保证游戏行为一致**",
    "⚠️ 默认值变化、字段解释变化、**未知字段丢弃**都会影响 must-match",
    "🔑 序列化测试要覆盖：最旧生产版本 · 每个迁移版本 · 当前版本 · "
    "损坏包 · 截断包 · 重复字段 · 未知字段 · **平台字节序**",
]

# 🔴 GC
GC_FIELDS = [
    "**每帧分配**", "临时对象", "闭包分配", "装箱",
    "**反向引用**", "销毁帧", "GC 触发原因", "代", "增量切片", "主线程/worker",
]

GC_RULE = [
    "🔴 内存回归要检查**卸载后的反向根** —— "
    "常见路径**不是对象未 Dispose**，而是：",
    "   事件 · 静态缓存 · **未完成异步句柄** · 协程 · DontDestroyOnLoad · "
    "资源引用 · 调试可视化 · **Profiler 采样**",
    "⚠️ 「非分代、非压缩」等通用说法**不能直接写入结论** —— "
    "运行时、引擎版本、平台、IL2CPP/Mono 与 GC 模式都可能变，字段应**绑定版本**",
]

SNAPSHOT_POINTS = [
    "基线", "**峰值前**", "**卸载后**", "**GC 后**", "空闲稳态",
]

SNAPSHOT_RULE = "🔑 五个点各做一次快照，对每个异常增长对象**回溯反向引用链**"

MEM_BUDGET = [
    "代码", "托管", "Native", "纹理", "网格", "音频", "**峰值**", "**保留**",
]

# 🔴 引擎隐藏默认值
DEFAULTS_UNITY = [
    "**Fixed Timestep**（默认 0.02 秒）", "**Maximum Allowed Timestep**",
    "重力", "默认接触偏移", "Solver Iterations", "Sleep Threshold",
    "Bounce Threshold", "Default Material", "Quality 各档", "VSync",
    "渲染路径", "**Gamma / Linear**", "**默认碰撞矩阵**", "Layer 数量",
    "UI Canvas 更新", "脚本运行时", "**GC 模式**",
]

DEFAULTS_UE = [
    "Map / GameMode", "NetDriver", "RHI", "Renderer", "Physics Solver",
    "Collision", "Input", "**ConsoleVariables**",
]

DEFAULTS_GODOT = [
    "application/run", "rendering/", "physics/", "input/", "audio/",
    "display/window", "shadows", "**thread model**",
]

DEFAULTS_RULE = [
    "🔑 每项必须记录：**源值 / 源是否显式设置 / 目标默认值 / 目标值 / "
    "行为测试 / 偏差等级**",
    "🔴 **特别检查未设置键** —— 未知键必须进入 review，"
    "**禁止默认视为「无关」**",
    "🔑 默认值表**必须带版本和平台** —— "
    "同 Unity 版本的 Android/iOS/Console、同 UE 版本的 Shipping/Development、"
    "同 Godot 版本的 Forward+/Mobile 都可能有不同默认行为",
    "🔑 目标端以**干净模板 + 相同版本**创建对照工程，逐项记录差值",
]

VERIFY_PHYSICS = [
    "静止抖动", "滑落", "滚动", "弹跳", "关节稳定", "穿透", "睡眠",
    "连续碰撞", "最大解算",
]

VERIFY_TIME = [
    "固定步模拟次数", "**最大追赶**", "暂停", "慢帧", "动画时间缩放",
]

VERIFY_RENDER = [
    "Gamma / Linear", "sRGB", "MSAA", "阴影", "LOD bias", "最大画质档",
]

VERIFY_INPUT = [
    "轴", "死区", "按键名", "手势", "重映射",
]

CONFLICTS = [
    "❌ **自动依赖** —— 不能证明依赖图、冗余和加载顺序正确",
    "❌ **对象池** —— 回收顺序会改变对象复用",
    "❌ **增量 GC** —— 便利但不证明对象寿命与销毁帧一致",
    "❌ **自动回滚** —— 必须显式写入，不能靠框架声称",
    "❌ **自动原点重置** —— 会掩盖坐标表示差异",
    "❌ **为性能自动改串行为并行** —— 要求证明顺序等价",
    "❌ **结构体重排 / 字段压缩 / 延迟初始化 / 字符串驻留 / pooling** —— "
    "性能导向、可能冲突",
    "🔑 缓存友好只在目标端允许优化时才研究：先按原顺序实现，"
    "再通过 A/B 与回放证明无行为差，再启用布局优化",
]

FIELDS = [
    ("item_id", "项编号"),
    ("domain", "域（hotfix / dep / serialize / gc / mem / defaults）"),
    ("legacy_value", "**原版值**"),
    ("new_value", "新引擎值"),
    ("match", "**是否一致**"),
    ("explicitly_set", "**源是否显式设置**"),
    ("evidence", "证据"),
]


def _hdr(t, w=80):
    print("=" * w)
    print(t)
    print("=" * w)


def cmd_hotfix(a):
    _hdr("🔴 热更新八态（**版本生命周期，不是打包按钮**）")
    for i, (k, fields, test, newf) in enumerate(HOTFIX_STATES, 1):
        print(f"\n   {i}. 【{k}】")
        print(f"      必记: {fields}")
        print(f"      验证: {test}")
        print(f"      字段: {newf}")
    print("\n规则:")
    for r in HOTFIX_RULE:
        print(f"   {r}")
    print("\n热状态磁盘缓存:")
    for c in HOTFIX_CACHE:
        print(f"   · {c}")
    return 0


def cmd_rollback(a):
    _hdr("回滚与断点续传")
    for r in HOTFIX_RULE:
        print(f"   {r}")
    print("\n缓存验证:")
    for c in HOTFIX_CACHE:
        print(f"   · {c}")
    return 0


def cmd_depgraph(a):
    _hdr("依赖图（**引用关系 + 生命周期关系**）")
    print("引用图: " + " · ".join(DEP_REF))
    print("\n生命周期图: " + " · ".join(DEP_LIFECYCLE))
    print("\n冗余:")
    for d in DEP_REDUNDANT:
        print(f"   {d}")
    print("\n循环依赖:")
    for d in DEP_CYCLE:
        print(f"   {d}")
    return 0


def cmd_serialize(a):
    _hdr("对象持久化（**稳定 ID 与引用修复**）")
    print("稳定 ID: " + " · ".join(SER_STABLE_ID))
    print("引用类型: " + " · ".join(SER_REF_TYPES))
    print("\n矩阵:")
    for k, risk, field in SER_FIELDS:
        print(f"\n   【{k}】→ {field}")
        print(f"      典型差异: {risk}")
    print("\n规则:")
    for r in SER_RULE:
        print(f"   {r}")
    return 0


def cmd_gc(a):
    _hdr("🔴 GC 与卡顿")
    for f in GC_FIELDS:
        print(f"   · {f}")
    print("\n规则:")
    for r in GC_RULE:
        print(f"   {r}")
    print("\n内存预算: " + " · ".join(MEM_BUDGET))
    return 0


def cmd_snapshot(a):
    _hdr("内存快照（**五个点**）")
    for i, p in enumerate(SNAPSHOT_POINTS, 1):
        print(f"   {i}. {p}")
    print(f"\n{SNAPSHOT_RULE}")
    return 0


def cmd_defaults(a):
    _hdr("🔴 引擎隐藏默认值（**另外 90%**）")
    print("Unity ProjectSettings:")
    for f in DEFAULTS_UNITY:
        print(f"   · {f}")
    print("\nUE DefaultEngine.ini / DefaultGame.ini / DefaultPhysics.ini / DefaultInput.ini:")
    for f in DEFAULTS_UE:
        print(f"   · {f}")
    print("\nGodot project.godot:")
    for f in DEFAULTS_GODOT:
        print(f"   · {f}")
    print("\n规则:")
    for r in DEFAULTS_RULE:
        print(f"   {r}")
    return 0


def cmd_verify(a):
    _hdr("默认值差异的验证清单")
    print("物理: " + " · ".join(VERIFY_PHYSICS))
    print("\n时间: " + " · ".join(VERIFY_TIME))
    print("\n渲染: " + " · ".join(VERIFY_RENDER))
    print("\n输入: " + " · ".join(VERIFY_INPUT))
    print("\n🔑 复刻验收**不接受「肉眼近似」**")
    return 0


def cmd_init(a):
    os.makedirs(os.path.dirname(a.init) or ".", exist_ok=True)
    with open(a.init, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow([k for k, _ in FIELDS])
        w.writerow(["TODO"] * len(FIELDS))
    print(f"已生成热更新/内存表: {a.init}")
    print("\n⚠️ 六域：hotfix / dep / serialize / gc / mem / defaults")
    print("⚠️ `explicitly_set` 留空视为**未显式设置** → 必须复核目标默认值")
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

    mismatch, no_legacy, not_explicit = [], [], []
    for i, r in enumerate(rows, 1):
        m = g(r, "match").lower()
        if m not in ("yes", "y", "true", "是", "一致"):
            mismatch.append(i)
        if not g(r, "legacy_value") or g(r, "legacy_value") == "TODO":
            no_legacy.append(i)
        ex = g(r, "explicitly_set").lower()
        if ex in ("", "todo", "unknown"):
            not_explicit.append(i)

    print("=" * 76)
    print(f"热更新/内存 · {len(rows)} 条")
    print("=" * 76)
    if mismatch:
        print(f"\n🚫 **不一致** {len(mismatch)} 条（行 {mismatch[:15]}）")
    if no_legacy:
        print(f"\n❌ {len(no_legacy)} 条缺**原版值**（行 {no_legacy[:15]}）")
    if not_explicit:
        print(f"\n⚠️  {len(not_explicit)} 条**未标明源是否显式设置**"
              f"（行 {not_explicit[:15]}）")
        print("   → 🔴 **未设置键就是潜在差异** —— 未知键必须进 review，"
              "不得默认视为无关")

    if not (mismatch or no_legacy):
        print("\n✅ 热更新/内存：一致且原版值完整")

    print("\n🔑 **差异最大的不是手写的 10%，是另外 90% 的未配置默认值。**")
    print("   **兼容只保证能读，不保证游戏行为一致。**")
    print("   **兼容 ≠ 可复刻。**")
    return 1 if (a.gate and (mismatch or no_legacy)) else 0


def main():
    ap = argparse.ArgumentParser(description="热更新/内存/默认值")
    ap.add_argument("--hotfix", action="store_true")
    ap.add_argument("--rollback", action="store_true")
    ap.add_argument("--depgraph", action="store_true")
    ap.add_argument("--serialize", action="store_true")
    ap.add_argument("--gc", action="store_true")
    ap.add_argument("--snapshot", action="store_true")
    ap.add_argument("--defaults", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--init")
    ap.add_argument("--check")
    ap.add_argument("--gate", action="store_true")
    a = ap.parse_args()
    fns = {"hotfix": cmd_hotfix, "rollback": cmd_rollback, "depgraph": cmd_depgraph,
           "serialize": cmd_serialize, "gc": cmd_gc, "snapshot": cmd_snapshot,
           "defaults": cmd_defaults, "verify": cmd_verify}
    for k, fn in fns.items():
        if getattr(a, k):
            return fn(a)
    if a.init:
        return cmd_init(a)
    if a.check:
        return cmd_check(a)
    print("❌ 需要 --hotfix / --rollback / --depgraph / --serialize / --gc / "
          "--snapshot / --defaults / --verify / --init / --check 之一")
    return 2


if __name__ == "__main__":
    sys.exit(main())
