#!/usr/bin/env python3
"""战斗手感与 AI 行为取证（深化 B / C 类）—— **must-match 的重灾区**。

**🔑 B 类最容易滑向主观评价。正确流程**：
> **先锁输入，再锁时间，最后观察判定。**

**🔑 C 类不能只比较最终路径**：
> 要比较**决策与状态转移**。感知采样频率变了，
> 即使"看起来会绕路"，AI 在相同关卡中会出现**不同发现顺序** —— 属行为偏离。

用法:
  game_combat_ai.py --framedata     # 帧数据逐帧账本
  game_combat_ai.py --hitbox        # 判定盒是**每帧的多重集合**
  game_combat_ai.py --input         # 输入系统也是 must-match
  game_combat_ai.py --conflict      # 同时命中/优先级/取消矩阵
  game_combat_ai.py --ai            # AI 状态转移与决策日志
  game_combat_ai.py --nav           # 寻路三阶段
  game_combat_ai.py --sense         # 感知参数化
  game_combat_ai.py --init ledger/combat_ai.csv
  game_combat_ai.py --check ledger/combat_ai.csv --gate

退出码: 0 通过 / 1 缺项 / 2 用法错误
"""
import argparse
import csv
import os
import sys

# 帧数据：**把「感觉」改写成逐帧观测**
FRAME_DATA = [
    "动作 ID", "动画长度", "**动画帧率**", "**逻辑步长**",
    "startup", "active", "recovery", "硬直",
    "**取消窗口**", "**输入窗口**", "目押窗口",
    "**无敌帧区间**", "霸体区间", "受身窗口",
    "击退曲线", "伤害", "属性", "打击优先级",
    "**命中暂停**", "屏幕效果", "音效事件",
]

FRAME_BIND = [
    "`global_frame`", "`tick_count`", "`animation_frame`", "`state_id`",
]

FRAME_TRAP = "⚠️ **不要把视觉帧号与逻辑帧号混为一谈**"

# 判定盒：**每帧的多重集合**
HITBOX_KINDS = [
    ("hitbox", "伤害盒、投技盒、投掷受付盒、反弹盒"),
    ("hurtbox", "受击部位、**受伤倍率**、无敌状态"),
    ("pushbox", "碰撞/挤压盒"),
    ("proximity/confirm box", "确认盒、**指令投窗口**"),
    ("projectile ownership", "抛射体**所有者**、状态与父子关系"),
]

HITBOX_FIELDS = [
    "几何", "相对骨骼偏移", "缩放", "朝向", "**激活起止帧**",
    "命中次数上限", "穿透", "伤害修正", "**事件副作用**",
]

HITBOX_RULES = [
    "⚠️ 盒体应用**角色坐标 + 世界坐标双写**",
    "⚠️ 处理**镜像、动画根运动、局部缩放、跨帧插值**",
    "⚠️ 只导出顶点坐标而**没有帧号、所有权和动画上下文**，"
    "不能支持任何手感门禁",
]

# 输入系统：**也是 must-match**
INPUT_FIELDS = [
    "设备轮询时刻", "边沿", "按键持续帧", "**SOCD 解决规则**",
    "方向优先级", "**输入缓冲队列长度**", "**缓冲有效期**",
    "读取时机", "**输入消耗规则**", "宏边界",
]

INPUT_TOOLS = [
    "逐帧显示「上一输入 / 当前输入 / 下一允许输入」",
    "**单帧步进**", "状态冻结", "**重设随机种子**", "盒体覆盖层", "事件日志",
]

# 冲突测试矩阵（**枚举，不是随机对打**）
CONFLICTS = [
    "两个攻击同时 active",
    "命中恢复与受击同时发生",
    "投技与普通命中竞争",
    "**无敌帧与命中暂停重叠**",
    "取消窗口边界",
    "**状态切换与动画结束同一帧**",
]

CONFLICT_NOTE = [
    "🔑 测试应枚举「**状态 × 事件 × 当前帧偏移**」，**不是随机对打**。",
    "⚠️ 社区的 `frame_data` 表只能作**初始假设**；"
    "若没有原始内存或代码证据，须标为 **`unverified`**。",
]

# AI 三个输出
AI_OUTPUTS = [
    ("ai_state_machine.csv", "状态、进入条件、退出条件、转移、超时、优先级、中断"),
    ("ai_decision_log.csv", "全局帧、实体 ID、感知输入、评分、选中动作、参数、**失败原因**"),
    ("navmesh_coverage.json", "网格哈希、**连通分量**、可行走面积、过滤条件、路径点误差"),
]

AI_METHOD = [
    "🔑 状态枚举必须**从原版执行结果反推** —— 只阅读反编译代码不够："
    "条件常量、浮点误差、优先级变化会让相同代码产生不同选择。",
    "① 可重复输入下让原版 AI 跑大量回合 → 从日志提取**实际到达状态**",
    "② 用控制流分析穷举**静态可达状态**",
    "③ **两者差集** = 「代码可达但未观测」或「已观测但代码证据不足」",
    "⚠️ 未观测状态必须保留为 **`unconfirmed_reachable`，不得直接删除**",
]

# 寻路三阶段
NAV_STAGES = [
    ("1 几何", "可行走面积、不可行走区域、边界、**代理高度**、台阶高度、"
               "斜率、代价层、动态障碍"),
    ("2 单条路径", "长度、航点、拐点、重规划"),
    ("3 群集", "拥挤避让、分离、队列、朝向、停止半径"),
]

SENSE_FIELDS = [
    "视野锥角度", "距离", "高度", "遮挡掩码", "背光",
    "听觉半径", "声压衰减", "**感知更新频率**", "记忆时长",
    "警报传播", "视线采样点",
]

SENSE_RECORD = [
    "**首次发现帧**", "**最后看见帧**", "**记忆过期帧**",
]

SENSE_RULE = [
    "⚠️ AI 应录制「首次发现帧 / 最后看见帧 / 记忆过期帧」，"
    "**而非只记录是否发现**。",
    "⚠️ 若只是「看起来会绕路」，但**感知采样频率改变** → "
    "AI 在相同关卡中出现不同发现顺序 → **行为偏离**。",
]

FIELDS = [
    ("item_id", "项编号"),
    ("domain", "域（framedata / hitbox / input / ai_state / nav / sense）"),
    ("legacy_value", "**原版值**（逐帧/逐状态）"),
    ("new_value", "新引擎值"),
    ("match", "**是否一致**"),
    ("evidence_level", "证据等级（**社区表只能作 unverified**）"),
    ("tolerance", "公差"),
]


def _print_table(title, w=78):
    print("=" * w)
    print(title)
    print("=" * w)


def cmd_framedata(a):
    _print_table("帧数据逐帧账本（**把「感觉」改写成观测**）")
    for f in FRAME_DATA:
        print(f"   · {f}")
    print("\n每项必须绑定: " + " · ".join(FRAME_BIND))
    print(f"\n{FRAME_TRAP}")
    print("\n🔑 **先锁输入 → 再锁时间 → 最后观察判定。**")
    print("   BizHawk 可作为原版取证基线：同一模拟核心上产生**可重放输入**，")
    print("   并导出**逐帧内存状态** —— 避免「人类试玩样本」的不确定性。")
    return 0


def cmd_hitbox(a):
    _print_table("判定盒（**每帧的多重集合，不是三个彩色矩形**）")
    for k, why in HITBOX_KINDS:
        print(f"\n   【{k}】{why}")
    print("\n每帧输出:")
    for f in HITBOX_FIELDS:
        print(f"   · {f}")
    print("\n规则:")
    for r in HITBOX_RULES:
        print(f"   {r}")
    return 0


def cmd_input(a):
    _print_table("输入系统（**也是 must-match**）")
    for f in INPUT_FIELDS:
        print(f"   · {f}")
    print("\n训练模式应提供:")
    for t in INPUT_TOOLS:
        print(f"   · {t}")
    return 0


def cmd_conflict(a):
    _print_table("同时命中 / 优先级 / 取消 —— 冲突测试矩阵")
    for c in CONFLICTS:
        print(f"   · {c}")
    print("")
    for n in CONFLICT_NOTE:
        print(f"   {n}")
    return 0


def cmd_ai(a):
    _print_table("AI 取证（**比较决策与状态转移，不只比最终路径**）")
    for k, why in AI_OUTPUTS:
        print(f"\n   【{k}】{why}")
    print("\n方法:")
    for m in AI_METHOD:
        print(f"   {m}")
    print("\n⚠️ BehaviorTree.CPP 吸收的是**AI 取证流程**，"
          "不是把机器人行为树直接复制进游戏。")
    print("   原版 AI 先用**状态转移表**描述，再保留后续实现选择：")
    print("   行为树 / 分层状态机 / GOAP / 实用 AI / 规则表 / 手写脚本。")
    return 0


def cmd_nav(a):
    _print_table("寻路验证三阶段")
    for k, why in NAV_STAGES:
        print(f"\n   【{k}】{why}")
    print("\n⚠️ recastnavigation（Recast / Detour / DetourCrowd）是导航网格与")
    print("   寻路工具集，但其 `License.txt` 需在使用前复核。")
    return 0


def cmd_sense(a):
    _print_table("感知参数化")
    for f in SENSE_FIELDS:
        print(f"   · {f}")
    print("\n必须录制（**不是只记「是否发现」**）:")
    for r in SENSE_RECORD:
        print(f"   · {r}")
    print("\n规则:")
    for r in SENSE_RULE:
        print(f"   {r}")
    return 0


def cmd_init(a):
    os.makedirs(os.path.dirname(a.init) or ".", exist_ok=True)
    with open(a.init, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow([k for k, _ in FIELDS])
        w.writerow(["TODO"] * len(FIELDS))
    print(f"已生成战斗/AI 取证表: {a.init}")
    print("\n⚠️ 六域：framedata / hitbox / input / ai_state / nav / sense")
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

    weak, mismatch, no_legacy = [], [], []
    for i, r in enumerate(rows, 1):
        lv = g(r, "evidence_level").lower()
        if lv in ("unverified", "community", "社区表", "待验证"):
            weak.append(i)
        m = g(r, "match").lower()
        if m not in ("yes", "y", "true", "是", "一致"):
            mismatch.append(i)
        if not g(r, "legacy_value") or g(r, "legacy_value") == "TODO":
            no_legacy.append(i)

    print("=" * 76)
    print(f"战斗/AI 取证 · {len(rows)} 条")
    print("=" * 76)
    if weak:
        print(f"\n⚠️  {len(weak)} 条证据等级为 unverified（行 {weak[:15]}）")
        print("   → 社区 frame_data 表只能作**初始假设**，需原始内存或代码证据")
    if mismatch:
        print(f"\n🚫 **must-match 不一致** {len(mismatch)} 条（行 {mismatch[:15]}）")
        print("   → 手感/判定/时序**不许以「新引擎更好」为由擅自改动**")
    if no_legacy:
        print(f"\n❌ {len(no_legacy)} 条缺**原版值**（行 {no_legacy[:15]}）")

    if not (mismatch or no_legacy):
        print("\n✅ 战斗/AI 取证一致")

    print("\n🔑 **先锁输入 → 再锁时间 → 最后观察判定。**")
    print("   **AI 比较决策与状态转移，不只比最终路径。**")
    return 1 if (a.gate and (mismatch or no_legacy)) else 0


def main():
    ap = argparse.ArgumentParser(description="战斗手感与 AI 行为取证")
    ap.add_argument("--framedata", action="store_true")
    ap.add_argument("--hitbox", action="store_true")
    ap.add_argument("--input", action="store_true")
    ap.add_argument("--conflict", action="store_true")
    ap.add_argument("--ai", action="store_true")
    ap.add_argument("--nav", action="store_true")
    ap.add_argument("--sense", action="store_true")
    ap.add_argument("--init")
    ap.add_argument("--check")
    ap.add_argument("--gate", action="store_true")
    a = ap.parse_args()
    fns = {"framedata": cmd_framedata, "hitbox": cmd_hitbox, "input": cmd_input,
           "conflict": cmd_conflict, "ai": cmd_ai, "nav": cmd_nav, "sense": cmd_sense}
    for k, fn in fns.items():
        if getattr(a, k):
            return fn(a)
    if a.init:
        return cmd_init(a)
    if a.check:
        return cmd_check(a)
    print("❌ 需要 --framedata / --hitbox / --input / --conflict / --ai / "
          "--nav / --sense / --init / --check 之一")
    return 2


if __name__ == "__main__":
    sys.exit(main())
