#!/usr/bin/env python3
"""流式加载 + 多线程与确定性（第七轮 A / B 类）。

**🔑 A 类核心**：
> 流式加载的 must-match 对象**不是某个地块**，而是玩家从请求到可用
> 这一整条**七态状态链**。
> 仅记「半径 120 米加载」会漏掉：加载屏、**不可见碰撞**、**可穿透空气墙**、
> NPC 先生成后初始化、传送后黑屏或坠落。

**🔑 B 类核心**：
> **确定性复刻的隐藏杀手是「同一逻辑没有固定执行顺序」。**
> Job System 能挡住一批数据竞争，但**不保证跨 Job、跨帧、跨系统的结果顺序**。

用法:
  game_stream_thread.py --stream     # 七态模型
  game_stream_thread.py --hyst       # 🔴 hysteresis 是**迟滞环**，不是加余量
  game_stream_thread.py --syncgate   # 同步门与**输入冻结**
  game_stream_thread.py --fastmove   # 高速穿透（**不是看帧率**）
  game_stream_thread.py --world      # 🔴 大坐标浮点精度崩溃
  game_stream_thread.py --thread     # 线程归属与同步边界
  game_stream_thread.py --order      # 🔴 **容器迭代顺序**契约
  game_stream_thread.py --parallel   # 并行分区与**顺序确定**分两列
  game_stream_thread.py --init ledger/stream_thread.csv
  game_stream_thread.py --check ledger/stream_thread.csv --gate

退出码: 0 通过 / 1 缺项 / 2 用法错误
"""
import argparse
import csv
import os
import sys

# 七态
STREAM_STATES = [
    "请求", "可见", "**可碰撞**", "**可交互**", "**可寻路**",
    "**可音频遮挡**", "完成卸载",
]

STREAM_FIELDS = [
    "进入半径", "预加载半径", "低细节可见半径", "**可碰撞半径**",
    "卸载保留时间", "**重复穿越的 hysteresis**", "强制阻塞门",
    "后台带宽上限", "**单帧 IO 预算**", "依赖任务链", "失败重试", "取消策略",
]

STREAM_PROBES = [
    ("双半径与 hysteresis", "沿边界往返、直角折返、**低速擦边**、多人分处边界"),
    ("优先级冲突", "高速转向、贴地俯冲、镜头反向、任务事件触发"),
    ("同步门", "快速连按、断网、低存储、下载超时、杀进程"),
    ("碰撞可用性", "传送落地、弹射、载具冲入、瞬移技能"),
    ("卸载副作用", "在边界放对象、切枪、切关卡、快速返回"),
    ("内存预算", "低端档、热状态、后台切换、连续传送"),
]

# 🔴 hysteresis
HYST_FIELDS = [
    "加载进入阈值", "卸载离开阈值", "**连续命中帧数**",
    "**最小驻留时间**", "紧急卸载例外",
]

HYST_RULE = [
    "🔴 **hysteresis 不是「加 5% 余量」** —— "
    "加载和卸载必须形成真正的**迟滞环**",
    "🔴 若加载半径 == 卸载半径 → 玩家抖动、相机抖动或时间戳离散"
    "都可能触发**同帧反复请求**",
    "🔑 建议 `load_radius > visible_radius > collision_radius >= unload_radius`",
    "🔑 分别测量：小物件 · 碰撞壳 · 地形 · NavMesh · HLOD · **音频探头**",
]

# 同步门
GATE_FIELDS = [
    "**阻塞输入**", "播放过场", "显示遮罩", "最小完成比例", "失败重试",
]

GATE_INPUT = [
    "🔑 输入在**加载屏 / 同步加载点 / 异步等待**期间是：",
    "   响应 · **队列后回放** · **丢弃** · 冻结 —— 这是明确的体验 must-match",
]

GATE_TELEPORT = [
    "黑屏开始", "目标区域进入加载队列", "最低依赖组", "**碰撞注册完成**",
    "出生点可用性", "**输入重新接受**", "**首个可玩帧**",
]

FASTMOVE = [
    "🔑 高速运动测试要用「**穿透风险**」而非帧率",
    "🔑 以最大地面速度 · 坠落速度 · 传送距离 · 预测提前量 · "
    "**单帧加载最坏耗时**共同计算**安全距离**",
    "🔴 连续两帧主角包围盒跨越未加载块 → 验证是否：无碰撞 · "
    "击中错误关卡 · 回滚位置 · **卡死** · 瞬移",
]

# 🔴 大世界坐标
WORLD_FIELDS = [
    "源项目**最大世界坐标**", "单位", "**使用双精度还是定点**",
    "**原点重置阈值**", "是否只在渲染层平移",
    "相机/刚体/导航/植被/着色器各自**坐标空间**",
    "**远距离 Z 精度**", "天空盒和行星曲率",
]

WORLD_RULE = [
    "🔑 按「**双精度源状态 + 相机相对渲染 + 原点重置**」**双轨取证**",
    "🔴 大坐标下崩溃**往往要接近边界或高速运动才出现** —— "
    "**不能只在出生点测试**",
    "🔑 构造 8 方向 × 4 种速度 × 近/远距离 × 边界 × 地下 × 空中 × 快速旅行",
    "🔑 四项观察：坐标绝对值 · **相对位移** · **误差增长** · 碰撞法线",
]

# 多线程
THREAD_OWNERS = [
    "游戏线程", "渲染线程", "IO 线程", "worker", "音频", "网络", "脚本",
]

THREAD_MATRIX = [
    ("线程归属", "主线程完成前渲染旧快照；更新与渲染**错位一帧**", "thread_owner"),
    ("任务依赖", "先写后读变脏读；加载完成在生成**之后**", "predecessors/successors"),
    ("并行分区", "**不同核心数产生不同元素顺序**", "parallel_range/order_policy"),
    ("**迭代顺序**", "命中首个对象、播报顺序、序列化输出变化", "iteration_order_contract"),
    ("线程局部状态", "不同 worker 概率序列；**跨帧池污染**", "thread_local_ownership"),
    ("同步语义", "死锁、饥饿、回退、**多帧传播**", "sync_primitive/timeout"),
    ("亲和性与核数", "低端设备更慢却仍非确定性", "worker_count_affinity_matrix"),
]

# 🔴 容器迭代顺序契约
ORDER_CONTRACT = [
    "**顺序确定**", "稳定但不保证", "显式无序", "**实现定义**",
]

ORDER_RULE = [
    "🔑 对每个 `Dictionary`、`HashSet`、回调列表、资源 ID 列表、并行范围，"
    "先判定其公开契约属于哪一种",
    "🔑 **只有顺序影响命中、排序、播报、存档字节、网络包或随机种子时**"
    "才需要强约束；其余允许并行",
]

PARALLEL_RULE = [
    "🔑 迁移脚本应把「**可以并行**」和「**顺序确定**」分成两列",
    "🔑 Unity Job 关键记录：`IJob`/`IJobParallelFor` · NativeContainer 限制 · "
    "**Schedule/Complete 边界** · 与 main thread 同步位置 · "
    "**每个 chunk 是否有确定性归约**",
    "🔑 UE：Task Graph 依赖 · Named Thread · 任意 worker · 渲染命令围栏 · "
    "**Game/Render 帧差**",
    "🔑 Godot：SceneTree · ResourceLoader · "
    "RenderingServer/PhysicsServer/NavigationServer 的**线程假设与回调线程**",
]

DET_TESTS = [
    "固定种子", "**固定核数**", "**跨核数重复 20 次**", "**shuffle 输入**",
    "**强制交错**",
]

DET_RULE = "🔑 比较**逻辑哈希**而非屏幕截图"

CONFLICTS = [
    "❌ **不要为了性能自动改串行为并行** —— 并行循环、哈希遍历、无序任务图、"
    "无锁池都是「便利且通常正确」，但复刻要求**证明顺序等价**",
    "🔴 若原作依赖某个枚举顺序 → 目标端必须用**排序键、稳定归约或串行路径**",
    "🔴 **对象池回收顺序**会改变对象复用 → 影响动画状态、特效、音频句柄、"
    "调试命名与**反序列化字节**",
]

FIELDS = [
    ("item_id", "项编号"),
    ("domain", "域（stream / hyst / gate / world / thread / order / parallel）"),
    ("legacy_value", "**原版值**"),
    ("new_value", "新引擎值"),
    ("match", "**是否一致**"),
    ("deterministic", "**是否顺序确定**"),
    ("evidence", "证据"),
]


def _hdr(t, w=80):
    print("=" * w)
    print(t)
    print("=" * w)


def cmd_stream(a):
    _hdr("🔴 流式加载七态（**不是半径和 LOD**）")
    for i, s in enumerate(STREAM_STATES, 1):
        print(f"   {i}. {s}")
    print("\n必记字段:")
    for f in STREAM_FIELDS:
        print(f"   · {f}")
    print("\n探针:")
    for k, why in STREAM_PROBES:
        print(f"\n   【{k}】{why}")
    return 0


def cmd_hyst(a):
    _hdr("🔴 hysteresis（**是迟滞环，不是加余量**）")
    for f in HYST_FIELDS:
        print(f"   · {f}")
    print("\n规则:")
    for r in HYST_RULE:
        print(f"   {r}")
    return 0


def cmd_gate(a):
    _hdr("同步门与输入冻结")
    for f in GATE_FIELDS:
        print(f"   · {f}")
    print("\n输入:")
    for g in GATE_INPUT:
        print(f"   {g}")
    print("\n传送目标独立记录:")
    for f in GATE_TELEPORT:
        print(f"   · {f}")
    print("\n高速运动:")
    for f in FASTMOVE:
        print(f"   {f}")
    return 0


def cmd_fastmove(a):
    _hdr("高速穿透（**不是看帧率**）")
    for f in FASTMOVE:
        print(f"   {f}")
    return 0


def cmd_world(a):
    _hdr("🔴 大世界坐标精度（**测试时往往不出现**）")
    for f in WORLD_FIELDS:
        print(f"   · {f}")
    print("\n规则:")
    for r in WORLD_RULE:
        print(f"   {r}")
    return 0


def cmd_thread(a):
    _hdr("多线程（🔑 **确定性复刻的隐藏杀手**）")
    print("线程归属: " + " · ".join(THREAD_OWNERS))
    print("\n矩阵:")
    for k, risk, field in THREAD_MATRIX:
        print(f"\n   【{k}】→ {field}")
        print(f"      典型偏差: {risk}")
    return 0


def cmd_order(a):
    _hdr("🔴 容器迭代顺序契约")
    for c in ORDER_CONTRACT:
        print(f"   · {c}")
    print("\n规则:")
    for r in ORDER_RULE:
        print(f"   {r}")
    print("\n反非确定性测试: " + " · ".join(DET_TESTS))
    print(f"\n{DET_RULE}")
    return 0


def cmd_parallel(a):
    _hdr("并行（**「可以并行」与「顺序确定」分两列**）")
    for r in PARALLEL_RULE:
        print(f"   {r}")
    print("\n冲突:")
    for c in CONFLICTS:
        print(f"   {c}")
    return 0


def cmd_init(a):
    os.makedirs(os.path.dirname(a.init) or ".", exist_ok=True)
    with open(a.init, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow([k for k, _ in FIELDS])
        w.writerow(["TODO"] * len(FIELDS))
    print(f"已生成流式/线程表: {a.init}")
    print("\n⚠️ 七域：stream / hyst / gate / world / thread / order / parallel")
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

    mismatch, no_legacy, nondet = [], [], []
    for i, r in enumerate(rows, 1):
        m = g(r, "match").lower()
        if m not in ("yes", "y", "true", "是", "一致"):
            mismatch.append(i)
        if not g(r, "legacy_value") or g(r, "legacy_value") == "TODO":
            no_legacy.append(i)
        d = g(r, "deterministic")
        if d in ("", "TODO"):
            nondet.append(i)

    print("=" * 76)
    print(f"流式/线程 · {len(rows)} 条")
    print("=" * 76)
    if mismatch:
        print(f"\n🚫 **不一致** {len(mismatch)} 条（行 {mismatch[:15]}）")
    if no_legacy:
        print(f"\n❌ {len(no_legacy)} 条缺**原版值**（行 {no_legacy[:15]}）")
    if nondet:
        print(f"\n⚠️  {len(nondet)} 条**未判定是否顺序确定**（行 {nondet[:15]}）")
        print("   → 必须逐项判定：顺序确定 / 稳定但不保证 / 显式无序 / 实现定义")

    if not (mismatch or no_legacy):
        print("\n✅ 流式/线程：一致且原版值完整")

    print("\n🔑 **hysteresis 是迟滞环**；**大坐标崩溃只在接近边界时出现**；")
    print("   **容器迭代顺序是确定性的隐藏杀手**。")
    return 1 if (a.gate and (mismatch or no_legacy)) else 0


def main():
    ap = argparse.ArgumentParser(description="流式加载与多线程确定性")
    ap.add_argument("--stream", action="store_true")
    ap.add_argument("--hyst", action="store_true")
    ap.add_argument("--syncgate", action="store_true")
    ap.add_argument("--fastmove", action="store_true")
    ap.add_argument("--world", action="store_true")
    ap.add_argument("--thread", action="store_true")
    ap.add_argument("--order", action="store_true")
    ap.add_argument("--parallel", action="store_true")
    ap.add_argument("--init")
    ap.add_argument("--check")
    ap.add_argument("--gate", action="store_true")
    a = ap.parse_args()
    fns = {"stream": cmd_stream, "hyst": cmd_hyst, "syncgate": cmd_gate,
           "fastmove": cmd_fastmove,
           "world": cmd_world, "thread": cmd_thread,
           "order": cmd_order, "parallel": cmd_parallel}
    for k, fn in fns.items():
        if getattr(a, k):
            return fn(a)
    if a.init:
        return cmd_init(a)
    if a.check:
        return cmd_check(a)
    print("❌ 需要 --stream / --hyst / --syncgate / --fastmove / --world / "
          "--thread / --order / --parallel / --init / --check 之一")
    return 2


if __name__ == "__main__":
    sys.exit(main())
