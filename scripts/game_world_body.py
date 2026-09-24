#!/usr/bin/env python3
"""世界模拟 + 玩家身体状态（第十轮 B / C 类）。

**🔑 B 类核心**：
> 应从"天气视觉效果"升级为"**世界因果链**"。
> 离线不是简单"时间流逝"，而是**多套时钟策略**。

**🔑 C 类核心**：
> 两条腿各伤 50% **是否等同于**一条腿伤 100%？
> 失去连接部位是否自动失能？这两个问题答错就是偏离。

用法:
  game_world_body.py --world       # 🔴 世界因果链
  game_world_body.py --schedule    # NPC 日程是**任务网络**不是时间表
  game_world_body.py --ecology     # 动物记**生态角色**不是 AI 行为名
  game_world_body.py --offline     # 🔴 离线推进**六层**
  game_world_body.py --body        # 部位伤害**四张时间表**
  game_world_body.py --bodypart    # 部位字段与**连接失能**
  game_world_body.py --need        # 需求系统（体力/饥饿/体温/呼吸）
  game_world_body.py --encumbrance # 🔴 负重**舍入**必须保留
  game_world_body.py --appearance  # 外观持久化**不是纯视觉**
  game_world_body.py --init ledger/world_body.csv
  game_world_body.py --check ledger/world_body.csv --gate

退出码: 0 通过 / 1 缺项 / 2 用法错误
"""
import argparse
import csv
import os
import sys

# 世界因果链
WORLD_CAUSALITY = [
    "输入", "转换", "输出", "**延迟**", "范围", "**副作用**",
    "**可逆性**", "**保存字段**",
]

# NPC 日程
SCHEDULE_FIELDS = [
    "**time_condition**（绝对时间、相对时间、光照、天气、月相）",
    "precondition", "location", "pathfinding_cost", "animation",
    "**interruption_priority**", "on_failure", "state_persistence",
]

SCHEDULE_CHECKS = [
    "NPC 是否**共用一个时钟**、是否一起冻结",
    "跨昼夜是否**补做未完成事项**",
    "被打断后是否回到路径点",
    "**睡眠是否被敌人永久取代**",
]

# 生态
ECOLOGY_FIELDS = [
    "物种", "群体规模", "**食性**", "**捕猎对象**", "**天敌**",
    "繁殖", "寿命", "迁徙", "栖息地", "资源贡献",
    "季节/天气响应", "**对玩家仇恨衰减**", "**尸体腐烂**", "**种群上限**",
]

ECOLOGY_CHECKS = [
    "动物是**随机刷新**、按区域容量刷新，还是依**猎物密度演化**",
    "**玩家过度捕猎是否会改变种群**",
    "NPC 是否共享同一**生态预算**",
    "存档读回后是否恢复**种群状态**",
]

# 🔴 离线六层
OFFLINE_LAYERS = [
    ("**真实墙钟**", "玩家离线多久", "real_time_start/end/scale"),
    ("**游戏时间**", "离线折算多少日", "game_time_per_real_second、上限、阈值"),
    ("**区域预算**", "哪个区域推进", "active_region、sim_radius、远端 LOD"),
    ("**系统白名单**", "哪些继续",
     "生态、贸易、生产、建筑、天气、NPC、物理、冷却"),
    ("**压缩策略**", "如何追赶", "逐步 tick、跳步、事件重演、关键帧"),
    ("**表现策略**", "上线后玩家看到什么", "无表现、动画、摘要、日志、弹窗"),
]

OFFLINE_FORMULA = [
    "🔑 `offline_game_seconds = clamp(real_elapsed_seconds * scale, min, max)`",
    "🔑 是否有**首次上线窗口** · 是否分区域预算 · "
    "是否只在特定设施/基地推进",
    "🔑 长离线是否按**日志式事件回放**",
    "🔑 上线时是播放过场、直接跳到结果，还是**逐个补 tick**",
    "🔴 若原版对 1 分钟 / 1 小时 / 24 小时 / 7 天给出**不同压缩率** → "
    "这就是 **must-match 曲线**，**不能自行改成平滑 1:1**",
]

# 部位伤害
BODYPART_FIELDS = [
    "父/子**连接**", "**左右侧**", "**关键性 vital**", "基础 HP",
    "当前/最大", "疼痛", "**出血**", "感染", "骨折", "**失能**",
    "暴露", "覆盖装备", "治疗材料消耗", "治疗时间", "**恢复曲线**",
    "**失能阈值**", "**永久疤痕/缺失**", "义体替代", "动画和 IK 映射",
]

BODYPART_Q = [
    "🔴 **两条腿各伤 50% 是否等同于一条腿伤 100%？**",
    "🔴 **失去连接部位是否自动失能？**",
    "🔑 治疗被打断是否**保留进度**",
    "🔑 睡眠/进食是否同时影响恢复",
    "🔑 死亡边界是总 HP / **关键部位** / 生命不可恢复比例 / 最低属性",
    "🔑 跨读盘是否**保留 HP 小数**",
]

# 四张时间表
BODY_TIMELINES = [
    ("**症状时间表**", "何时生效"),
    ("**急性时间表**", "流血 / 感染"),
    ("**治疗时间表**", "治疗速度、材料、环境、技能"),
    ("**恢复时间表**", "休息、营养、**永久损伤**"),
]

BODY_TIMELINE_RULE = "🔴 **这四类不应合并成一个「治疗速度」**"

BODY_WINDOW = [
    "死亡/倒地后的**时间窗口**", "队友复活", "**自动治疗上限**",
    "治疗特效开始/结束", "**生命值小数是否参与表现**",
]

# 需求
NEED_SYSTEMS = [
    "体力", "耐力", "饥饿", "**体温**", "**呼吸**", "**负重**",
    "口渴", "疲劳", "**睡眠**",
]

# 🔴 负重
ENCUMBRANCE_EFFECTS = [
    "加速", "最大速度", "刹车", "**转向**", "**跳跃高度**",
    "体力消耗", "**掉落伤害**", "**噪音**", "**视线遮挡**",
    "换弹", "交互速度",
]

ENCUMBRANCE_VOLUME = [
    "碰撞", "背包", "存物", "蹲伏", "载具",
]

ENCUMBRANCE_RULE = [
    "🔴 若原版把重量按**整数千克四舍五入**，目标端也必须保留该舍入 —— "
    "**不能用浮点千克让负重曲线逐渐漂移**",
    "🔑 左右手/双肩**不对称**是否影响后坐力、翻滚、持盾",
]

# 外观
APPEARANCE_FIELDS = [
    "**永久疤痕**", "污渍", "破损", "装备染色", "泥/血/雪", "湿身",
    "疲劳痕迹", "**体型**", "年龄", "受伤", "换装", "套装",
    "**跨保存**", "过场服装", "死亡/倒地状态",
    "**本地/队友/敌方可见性**",
]

APPEARANCE_CHECKS = [
    "外观是否影响**碰撞、识别、剧情、拍照、图鉴**",
    "**保存频率**",
    "是否随**身体部位缺失联动**",
    "是否影响**判定可读性**",
    "是否触发**材质重编译 / 纹理混合**",
]

APPEARANCE_RULE = "🔑 这里很容易发生「**更真实但不可控**」的偏离 → 优先 `must_match`"

CONFLICTS = [
    "❌ **把「真实医学模拟」作为目标** —— 与逐功能复刻原作语义冲突",
    "❌ 通用健康管理库 —— 健康曲线**可运行不等于正确**",
    "❌ **离线推进改成平滑 1:1** —— 原版分段压缩率是 must-match 曲线",
    "❌ 四张时间表合并成「治疗速度」",
    "❌ **负重改用浮点千克** —— 曲线会逐渐漂移",
]

FIELDS = [
    ("item_id", "项编号"),
    ("domain", "域（world / schedule / ecology / offline / body / need / encumbrance / appearance）"),
    ("legacy_value", "**原版值**"),
    ("new_value", "新引擎值"),
    ("match", "**是否一致**"),
    ("persisted", "**是否持久化**"),
    ("evidence", "证据"),
]


def _hdr(t, w=80):
    print("=" * w)
    print(t)
    print("=" * w)


def cmd_world(a):
    _hdr("🔴 世界因果链（**不是天气视觉效果**）")
    print("world_causality.yaml 字段: " + " · ".join(WORLD_CAUSALITY))
    print("\n🔑 还应记录：区域占领 · 势力消长 · 重建进度 · "
          "**可破坏是否永久/可修复/跨存档**")
    print("🔑 天气是否**影响玩法**：火蔓延 · 结冰 · 雷击 · 能见度 · **敌人行为**")
    return 0


def cmd_schedule(a):
    _hdr("NPC 日程（**任务网络，不是时间表**）")
    for f in SCHEDULE_FIELDS:
        print(f"   · {f}")
    print("\n检查:")
    for c in SCHEDULE_CHECKS:
        print(f"   · {c}")
    return 0


def cmd_ecology(a):
    _hdr("生态（**记生态角色，不是 AI 行为名**）")
    for f in ECOLOGY_FIELDS:
        print(f"   · {f}")
    print("\n食物链检查:")
    for c in ECOLOGY_CHECKS:
        print(f"   · {c}")
    return 0


def cmd_offline(a):
    _hdr("🔴 离线推进（**六层**）")
    for k, q, obj in OFFLINE_LAYERS:
        print(f"\n   【{k}】{q}")
        print(f"      记录: {obj}")
    print("\n算式与边界:")
    for f in OFFLINE_FORMULA:
        print(f"   {f}")
    return 0


def cmd_body(a):
    _hdr("受伤—治疗—恢复（**四张时间表**）")
    for k, why in BODY_TIMELINES:
        print(f"   {k:<16} {why}")
    print(f"\n{BODY_TIMELINE_RULE}")
    print("\n时间窗口: " + " · ".join(BODY_WINDOW))
    return 0


def cmd_bodypart(a):
    _hdr("部位伤害字段")
    for f in BODYPART_FIELDS:
        print(f"   · {f}")
    print("\n必答问题:")
    for q in BODYPART_Q:
        print(f"   {q}")
    return 0


def cmd_need(a):
    _hdr("需求系统")
    print("常见需求: " + " · ".join(NEED_SYSTEMS))
    print("\n🔑 每个需求要记：速率 · 阈值 · 惩罚曲线 · "
          "**是否随难度/周目变化** · **是否持久化**")
    return 0


def cmd_encumbrance(a):
    _hdr("🔴 负重（**舍入必须保留**）")
    print("重量影响: " + " · ".join(ENCUMBRANCE_EFFECTS))
    print("\n体积影响: " + " · ".join(ENCUMBRANCE_VOLUME))
    print("\n规则:")
    for r in ENCUMBRANCE_RULE:
        print(f"   {r}")
    return 0


def cmd_appearance(a):
    _hdr("外观持久化（**不是纯视觉**）")
    for f in APPEARANCE_FIELDS:
        print(f"   · {f}")
    print("\n检查:")
    for c in APPEARANCE_CHECKS:
        print(f"   · {c}")
    print(f"\n{APPEARANCE_RULE}")
    return 0


def cmd_init(a):
    os.makedirs(os.path.dirname(a.init) or ".", exist_ok=True)
    with open(a.init, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow([k for k, _ in FIELDS])
        w.writerow(["TODO"] * len(FIELDS))
    print(f"已生成世界/身体表: {a.init}")
    print("\n⚠️ 八域：world / schedule / ecology / offline / body / "
          "need / encumbrance / appearance")
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

    mismatch, no_legacy, no_persist = [], [], []
    for i, r in enumerate(rows, 1):
        m = g(r, "match").lower()
        if m not in ("yes", "y", "true", "是", "一致"):
            mismatch.append(i)
        if not g(r, "legacy_value") or g(r, "legacy_value") == "TODO":
            no_legacy.append(i)
        p = g(r, "persisted")
        if p in ("", "todo", "unknown"):
            no_persist.append(i)

    print("=" * 76)
    print(f"世界/身体 · {len(rows)} 条")
    print("=" * 76)
    if mismatch:
        print(f"\n🚫 **不一致** {len(mismatch)} 条（行 {mismatch[:15]}）")
    if no_legacy:
        print(f"\n❌ {len(no_legacy)} 条缺**原版值**（行 {no_legacy[:15]}）")
    if no_persist:
        print(f"\n⚠️  {len(no_persist)} 条**未判定是否持久化**（行 {no_persist[:15]}）")
        print("   → 🔑 世界状态与身体状态必须逐项声明是否持久化")

    if not (mismatch or no_legacy):
        print("\n✅ 世界/身体：一致且原版值完整")

    print("\n🔑 **离线推进是六层时钟策略，分段压缩率是 must-match 曲线。**")
    print("   **受伤四张时间表不能合并成「治疗速度」。**")
    print("   **负重舍入必须保留 —— 否则曲线逐渐漂移。**")
    return 1 if (a.gate and (mismatch or no_legacy)) else 0


def main():
    ap = argparse.ArgumentParser(description="世界模拟与身体状态")
    ap.add_argument("--world", action="store_true")
    ap.add_argument("--schedule", action="store_true")
    ap.add_argument("--ecology", action="store_true")
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--body", action="store_true")
    ap.add_argument("--bodypart", action="store_true")
    ap.add_argument("--need", action="store_true")
    ap.add_argument("--encumbrance", action="store_true")
    ap.add_argument("--appearance", action="store_true")
    ap.add_argument("--init")
    ap.add_argument("--check")
    ap.add_argument("--gate", action="store_true")
    a = ap.parse_args()
    fns = {"world": cmd_world, "schedule": cmd_schedule, "ecology": cmd_ecology,
           "offline": cmd_offline, "body": cmd_body, "bodypart": cmd_bodypart,
           "need": cmd_need, "encumbrance": cmd_encumbrance,
           "appearance": cmd_appearance}
    for k, fn in fns.items():
        if getattr(a, k):
            return fn(a)
    if a.init:
        return cmd_init(a)
    if a.check:
        return cmd_check(a)
    print("❌ 需要 --world / --schedule / --ecology / --offline / --body / "
          "--bodypart / --need / --encumbrance / --appearance / --init / "
          "--check 之一")
    return 2


if __name__ == "__main__":
    sys.exit(main())
