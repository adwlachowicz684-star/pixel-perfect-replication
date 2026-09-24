#!/usr/bin/env python3
"""关卡空间体验 + 教程系统 + 难度平衡（第九轮 B / C / D / E 类）。

**🔑 B 类核心**：
> **"能走通"只证明路径存在，不能证明空间可读性。**
> 复刻时若只替换几何、不复制视觉引导的权重 ——
> **地形相似但玩家会迷路**。

**🔑 C 类核心**：
> 教程是**状态机**，不是一串文本气泡。
> ❌ **把文本提示直接写在触发盒里**会造成语言、设置、可访问性、
> 回放与平台控制提示的耦合。

**🔑 D 类核心**：
> **难度不是数值，是一张数值关系网。**
> DDA 的核心验收是「**是否改变可感知结果**」，不是"是否被玩家明确发现"。

用法:
  game_level_balance.py --level      # 🔴 LevelExperience 八维度
  game_level_balance.py --guide      # 视觉引导**四级**
  game_level_balance.py --boundary   # 🔴 隐形墙**五种语义**
  game_level_balance.py --checkpoint # 检查点与**重试惩罚**
  game_level_balance.py --tutorial   # 教程**五组状态**
  game_level_balance.py --newbie     # 新手保护（**别随教程优化掉**）
  game_level_balance.py --difficulty # 难度档位改的是**关系参数**
  game_level_balance.py --dda        # 🔴 DDA 四类机制
  game_level_balance.py --savestate  # 存档可见性**六态**
  game_level_balance.py --init ledger/level_balance.csv
  game_level_balance.py --check ledger/level_balance.csv --gate

退出码: 0 通过 / 1 缺项 / 2 用法错误
"""
import argparse
import csv
import os
import sys

# LevelExperience 八维度
LEVEL_DIMS = [
    ("战斗节奏", "遭遇间隔、敌人组合、波次、**压力峰值**",
     "玩家从发现敌情到首击的时间；连续两波间是否有喘息"),
    ("探索", "主路/岔路/死路、奖励类型、**回环**",
     "隐藏区是否有双向捷径；**返回奖励是否真实存在**"),
    ("视觉引导", "地标、光源方向、色相对比、**构图视线**",
     "地标从多远首次可见；**遮挡角**；背光剪影"),
    ("交互可读性", "可交互物亮度、轮廓、动态提示、遮挡",
     "目标离相机距离、**屏幕占比**、被其他物体遮挡帧数"),
    ("边界", "硬墙/软墙/空气墙/坠落区/迷雾",
     "**不可见边界距离最近可交互内容多远**"),
    ("检查点", "位置、朝向、资源重置、**重试路径**",
     "**死亡后回跑距离**、回跑期间敌人与资源状态"),
    ("失败惩罚", "跑图、资源、剧情、相机/菜单负担",
     "失败一次是否**重看不可跳过的演出**"),
    ("空间连通性", "捷径解锁、双向路径、死亡循环",
     "是否形成「**先绕远再解锁捷径**」的可验证结构"),
]

# 视觉引导四级
GUIDE_LEVELS = [
    ("**地标级**", "远处可见物"),
    ("**路径级**", "地面材质、光带、门洞"),
    ("**目标级**", "高亮 / 轮廓 / 声音"),
    ("**动作级**", "NPC 示范、可破坏物、敌人吸引"),
]

GUIDE_RULE = [
    "🔑 无 UI 引导**也不是「没有提示」** —— "
    "而是把信息编码在**光照方向、颜色冷暖、景深层次、开放度、声源方向、"
    "物体运动**上",
    "🔴 复刻时若只替换几何、不复制这些**视觉权重** → "
    "**地形相似但玩家会迷路**",
]

# 🔴 隐形墙五种语义
BOUNDARY_KINDS = [
    "可攀爬高度", "坠落死亡", "相机边界", "任务进度", "性能裁切",
]

BOUNDARY_FIELDS = [
    "碰撞高度", "厚度", "**法线反馈**", "贴图/粒子遮挡",
    "**角色贴边时的摩擦**", "相机碰撞", "**贴墙滑步**",
    "**连续碰撞**", "**TriggerExit 行为**",
]

BOUNDARY_RULE = [
    "🔴 **隐形墙是最典型的 must-match 体验资产** —— "
    "**不能因「看不见」而缺席 schema**",
    "🔴 若原作允许角色在墙边**卡住或贴墙滑行**，移除墙并不会「改善体验」，"
    "而是**偏离**",
]

# 检查点
CHECKPOINT_FIELDS = [
    "位置", "**朝向**", "**资源重置**", "**重试路径**",
    "死亡后回跑距离", "回跑期间**敌人与资源状态**",
]

CHECKPOINT_PENALTY = [
    "跑图距离", "资源损失", "剧情重放", "**不可跳过的演出**",
    "相机/菜单负担",
]

# 教程五组状态
TUTORIAL_STATES = [
    "**触发**", "**完成**", "**重看**", "**持久化**（seen flag）", "**关闭**",
]

TUTORIAL_FIELDS = [
    "提示触发条件与时机",
    "**一次性状态的持久化**（存档里是否记「已看过」）",
    "**提示消失条件**", "**可重看**", "**设置里能否关闭**",
]

TUTORIAL_RULE = [
    "🔑 教程至少包含**五组状态**：触发 / 完成 / 重看 / 持久化 / 关闭",
    "🔑 **`seen` flag 与玩家关闭偏好应独立存档**",
    "❌ **把文本提示直接写在触发盒里** → "
    "语言、设置、可访问性、回放与平台控制提示**耦合**",
    "✅ 触发器只产生 `TutorialEvent`；引导系统根据玩家状态选择提示、"
    "检查完成、写回 `seen` 状态并发送游戏命令",
]

# 新手保护
NEWBIE_FIELDS = [
    "宽限时间窗", "自动锁定/自动瞄准", "伤害减免", "容错次数",
    "提示频率", "**敌人攻击频率**", "**反应时间**",
    "**资源掉落修正**", "操作映射建议",
]

NEWBIE_RULE = [
    "🔴 **新手保护与自动辅助不能随教程一并「优化掉」**",
    "🔑 它们可能是 DDA，也可能是**固定新手期** —— "
    "必须记录触发条件、持续时间、退出方式和**版本变更**",
    "🔑 若原作在玩家连续失败后**悄悄降低难度** → 属于 **D 类**，不是 C 类",
]

# 难度：关系参数
DIFFICULTY_GRANULARITY = [
    "玩家 HP / 伤害 / 资源", "敌人 HP / 伤害 / 数量",
    "**AI 攻击频率**", "**AI 反应时间**", "**索敌范围**", "**警戒时长**",
    "**玩家容错**", "资源掉落", "检查点密度", "教程提示频率", "时间限制",
]

DIFFICULTY_RULE = [
    "🔑 难度档位应改「**关系参数**」，而不是只改血量、伤害与敌人数量",
    "🔴 只记录百分比调整不够 —— 必须记录它是"
    "**乘算 / 加算 / 覆盖 / 概率变化 / 参数表替换**",
]

TTK_RELATIONS = [
    "玩家可持续 DPS 与敌人 HP",
    "敌人单发伤害与玩家可恢复资源",
    "**玩家死亡时间窗与敌人攻击频率**",
    "**连续失败成本与检查点距离**",
    "单区域总资源消耗与总可获取资源",
    "**最短通过时间与最大失误次数**",
]

TTK_RULE = "🔑 应输出**差异曲线**，而不是只输出平均值"

# 🔴 DDA 四类
DDA_KINDS = [
    ("**永久新手保护**", "首次游玩固定生效"),
    ("**短期随机保护**", "避免连续好运或厄运"),
    ("**长期技能适配**", "长期跟随玩家表现"),
    ("**可关闭 DDA**", "可由玩家主动关闭"),
]

DDA_FIELDS = [
    "启用/关闭", "适用难度", "**观察窗口**",
    "指标（胜率、死亡次数、连败、资源剩余、任务超时、操作频率）",
    "触发阈值", "**调整对象**", "**调整幅度**", "最小/最大边界",
    "平滑步长", "冷却时间", "**是否可关闭**", "**是否显示**",
    "**是否进入存档**",
]

DDA_RULE = [
    "🔑 长期 DDA 常修改敌人强度、攻击频率、反应时间、资源、容错、事件概率 —— "
    "**不能只写「AI 会适应」**",
    "🔴 **若原作没有 DDA，复刻也不得「贴心加入」** —— 属于理念冲突",
    "🔑 核心验收是「**是否改变可感知结果**」，"
    "不是「**是否被玩家明确发现**」",
    "🔑 每次调整同时记录 `effect_size` 与 **`player_perceivable`** —— "
    "不能只记录 `enabled: true`",
    "🔑 竞技公平、排行榜、成就、隐藏规则与**玩家信任**都必须考虑",
]

# 存档可见性六态
SAVE_STATES = [
    "visible", "exportable", "deletable", "cloud_syncable",
    "backupable", "repairable",
]

SAVE_RULE = [
    "🔑 存档可见性应写成**独立权限状态机**，"
    "而不是在文件菜单里临时加按钮",
    "🔑 某些存档**不应被玩家完全删除**（授权、平台账户映射、跨设备锁）",
    "🔑 截图、设置、统计、地图探索度却**可能希望单独导出**",
    "⚠️ 字段缺失时，容易把「**玩家找不到存档目录**」误当成"
    "「**玩家不关心存档**」",
]

SAVE_CONFLICT = [
    "多设备同时玩的**冲突解决策略**：时间戳 / 版本号 / **玩家选择**",
    "**损坏恢复**：备份、回滚、**部分恢复**",
    "**跨设备/跨平台进度同步**",
]

FIELDS = [
    ("item_id", "项编号"),
    ("domain", "域（level / guide / boundary / checkpoint / tutorial / newbie / difficulty / dda / savestate）"),
    ("legacy_value", "**原版值**"),
    ("new_value", "新引擎值"),
    ("match", "**是否一致**"),
    ("player_perceivable", "**玩家能否察觉**"),
    ("evidence", "证据"),
]


def _hdr(t, w=80):
    print("=" * w)
    print(t)
    print("=" * w)


def cmd_level(a):
    _hdr("🔴 LevelExperience（**关卡不是几何体**）")
    for k, fields, probe in LEVEL_DIMS:
        print(f"\n   【{k}】{fields}")
        print(f"      取证: {probe}")
    return 0


def cmd_guide(a):
    _hdr("视觉引导四级")
    for k, why in GUIDE_LEVELS:
        print(f"   {k:<12} {why}")
    print("\n规则:")
    for r in GUIDE_RULE:
        print(f"   {r}")
    return 0


def cmd_boundary(a):
    _hdr("🔴 隐形墙（**最典型的 must-match 体验资产**）")
    print("五种语义: " + " · ".join(BOUNDARY_KINDS))
    print("\n必记: " + " · ".join(BOUNDARY_FIELDS))
    print("\n规则:")
    for r in BOUNDARY_RULE:
        print(f"   {r}")
    return 0


def cmd_checkpoint(a):
    _hdr("检查点与重试惩罚")
    print("必记: " + " · ".join(CHECKPOINT_FIELDS))
    print("\n惩罚: " + " · ".join(CHECKPOINT_PENALTY))
    return 0


def cmd_tutorial(a):
    _hdr("教程（**状态机，不是文本气泡**）")
    print("五组状态: " + " · ".join(TUTORIAL_STATES))
    print("\n字段: " + " · ".join(TUTORIAL_FIELDS))
    print("\n规则:")
    for r in TUTORIAL_RULE:
        print(f"   {r}")
    return 0


def cmd_newbie(a):
    _hdr("新手保护（**别随教程优化掉**）")
    for f in NEWBIE_FIELDS:
        print(f"   · {f}")
    print("\n规则:")
    for r in NEWBIE_RULE:
        print(f"   {r}")
    return 0


def cmd_difficulty(a):
    _hdr("难度（**关系参数，不只是数值**）")
    print("最低记录粒度: " + " · ".join(DIFFICULTY_GRANULARITY))
    print("\n规则:")
    for r in DIFFICULTY_RULE:
        print(f"   {r}")
    print("\nDPS/TTK 关系: " + " · ".join(TTK_RELATIONS))
    print(f"\n{TTK_RULE}")
    return 0


def cmd_dda(a):
    _hdr("🔴 DDA（**四类机制**）")
    for k, why in DDA_KINDS:
        print(f"   {k:<16} {why}")
    print("\n字段: " + " · ".join(DDA_FIELDS))
    print("\n规则:")
    for r in DDA_RULE:
        print(f"   {r}")
    return 0


def cmd_savestate(a):
    _hdr("存档可见性（**六态权限**）")
    for s in SAVE_STATES:
        print(f"   · {s}")
    print("\n规则:")
    for r in SAVE_RULE:
        print(f"   {r}")
    print("\n冲突与恢复:")
    for c in SAVE_CONFLICT:
        print(f"   · {c}")
    return 0


def cmd_init(a):
    os.makedirs(os.path.dirname(a.init) or ".", exist_ok=True)
    with open(a.init, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow([k for k, _ in FIELDS])
        w.writerow(["TODO"] * len(FIELDS))
    print(f"已生成关卡/平衡表: {a.init}")
    print("\n⚠️ 九域：level / guide / boundary / checkpoint / tutorial / "
          "newbie / difficulty / dda / savestate")
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

    mismatch, no_legacy, unclear = [], [], []
    for i, r in enumerate(rows, 1):
        m = g(r, "match").lower()
        if m not in ("yes", "y", "true", "是", "一致"):
            mismatch.append(i)
        if not g(r, "legacy_value") or g(r, "legacy_value") == "TODO":
            no_legacy.append(i)
        pp = g(r, "player_perceivable")
        if pp in ("", "todo", "unknown"):
            unclear.append(i)

    print("=" * 76)
    print(f"关卡/平衡 · {len(rows)} 条")
    print("=" * 76)
    if mismatch:
        print(f"\n🚫 **不一致** {len(mismatch)} 条（行 {mismatch[:15]}）")
    if no_legacy:
        print(f"\n❌ {len(no_legacy)} 条缺**原版值**（行 {no_legacy[:15]}）")
    if unclear:
        print(f"\n⚠️  {len(unclear)} 条**未判定玩家能否察觉**（行 {unclear[:15]}）")
        print("   → 🔴 DDA 与难度调整必须记录 `effect_size` 与 "
              "`player_perceivable`，不能只记 `enabled: true`")

    if not (mismatch or no_legacy):
        print("\n✅ 关卡/平衡：一致且原版值完整")

    print("\n🔑 **能走通只证明路径存在，不能证明空间可读性。**")
    print("   **难度不是数值，是一张关系网。**")
    print("   **若原作没有 DDA，复刻也不得贴心加入。**")
    return 1 if (a.gate and (mismatch or no_legacy)) else 0


def main():
    ap = argparse.ArgumentParser(description="关卡/教程/难度")
    ap.add_argument("--level", action="store_true")
    ap.add_argument("--guide", action="store_true")
    ap.add_argument("--boundary", action="store_true")
    ap.add_argument("--checkpoint", action="store_true")
    ap.add_argument("--tutorial", action="store_true")
    ap.add_argument("--newbie", action="store_true")
    ap.add_argument("--difficulty", action="store_true")
    ap.add_argument("--dda", action="store_true")
    ap.add_argument("--savestate", action="store_true")
    ap.add_argument("--init")
    ap.add_argument("--check")
    ap.add_argument("--gate", action="store_true")
    a = ap.parse_args()
    fns = {"level": cmd_level, "guide": cmd_guide, "boundary": cmd_boundary,
           "checkpoint": cmd_checkpoint, "tutorial": cmd_tutorial,
           "newbie": cmd_newbie, "difficulty": cmd_difficulty,
           "dda": cmd_dda, "savestate": cmd_savestate}
    for k, fn in fns.items():
        if getattr(a, k):
            return fn(a)
    if a.init:
        return cmd_init(a)
    if a.check:
        return cmd_check(a)
    print("❌ 需要 --level / --guide / --boundary / --checkpoint / --tutorial / "
          "--newbie / --difficulty / --dda / --savestate / --init / --check 之一")
    return 2


if __name__ == "__main__":
    sys.exit(main())
