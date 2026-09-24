#!/usr/bin/env python3
"""数值/随机/存档/成就（深化 D / E 类）。

**🔑 D 类最容易犯两类错误**：
1. 相信"**理论权重 = 实际分布**" —— 忽略条件门槛、保底、抽取顺序、
   去重、跨表引用
2. 相信"**统计不显著 = 实现正确**" —— 忽略样本不足、稀有项、小概率事件

> 正确流程：**先实现可重放 RNG，再验证抽取分布**。
> **统计检验只能作辅助，不能替代规格比对。**

**🔑 E 类**：存档不是"读出来再写一遍"，而是映射为**带版本的规范 schema**。
> **未知字段不得因为"看起来没影响"就丢弃** ——
> 一个未命名位可能控制跨章节解锁。

用法:
  game_rng_save.py --rng           # RNG 三合一验证
  game_rng_save.py --rng-traps     # RNG 常见漏点
  game_rng_save.py --drops         # 掉落表与统计检验
  game_rng_save.py --economy       # 经济系统
  game_rng_save.py --save          # 存档字段分类与迁移
  game_rng_save.py --achievement   # 成就/统计穷举
  game_rng_save.py --init ledger/rng_save.csv
  game_rng_save.py --check ledger/rng_save.csv --gate

退出码: 0 通过 / 1 有丢弃未知字段或不可重放 / 2 用法错误
"""
import argparse
import csv
import os
import sys

# RNG 一次抽取的记录字段
RNG_FIELDS = [
    "全局帧", "调用栈或系统 ID", "**算法/实现名**", "状态快照版本",
    "**种子来源**", "**状态克隆点**", "**调用序号**", "输入整数",
    "分布变换", "最终结果", "**副作用**",
]

RNG_ALGO_NOTE = [
    "⚠️ 算法名**不能只写「MT19937」** —— 应同时记录：字长、参数、初始化、"
    "索引位置、进位、输出变换、分布实现。",
    "⚠️ PCG / xorshift / LFSR 同理。",
    "🔴 **版本、编译器、整数宽度或提取方式不同，同名算法也可能产生不同序列**。",
]

RNG_TRAPS = [
    "每帧重新播种",
    "把**系统时间或指针混入状态**",
    "**战斗、掉落、地图生成共享同一状态**",
    "保存/读取复制状态",
    "网络同步点重置状态",
    "**多线程各自推进**",
    "游戏结束重试不重置",
    "客户端与服务器顺序不同",
]

RNG_RULE = [
    "🔑 复刻侧必须提供「**RNG 观测点**」—— 允许重放相同种子并比对"
    "**每次抽取结果**，而不只是保存最终随机数。",
]

# 统计检验
TESTS = [
    ("卡方拟合优度", "类别型掉落：原版观测频数 vs 理论期望",
     "⚠️ **期望频数不能过低** —— 稀有项应合并尾类，或用精确检验/模拟分布"),
    ("双样本 KS", "连续型奖励或暴击伤害",
     "⚠️ 对位置、尺度、尾部敏感；**离散类别需离散适配**"),
    ("二项概率 + 置信区间", "样本量预注册",
     "⚠️ 防止「抽几百次没看见传说物品」被误判为零概率"),
]

TEST_NOTE = [
    "🔑 检验零假设：「原版与复刻来自**同一离散/连续分布**」。",
    "⚠️ p 值很小**只能拒绝该假设**，**不能单独指出错在哪个字段**。",
    "⚠️ **统计检验用于发现长期偏差，不能替代规格比对。**",
]

ECONOMY_FIELDS = [
    "货币", "商店品", "价格", "库存", "刷新", "折扣", "买卖限制", "掉率",
    "任务奖励", "交易税", "通胀", "**绑定/不可绑定**", "**跨商店套利**", "价格边界",
]

ECONOMY_CHECKS = [
    "整数溢出", "负数", "浮点误差", "**跨会话持久化**",
]

GROWTH = [
    "等级断点", "累计值", "前置条件", "**重置与返还**",
]

GROWTH_NOTE = "⚠️ 用数学公式计算**每个断点**，**避免只检查最后一级**。"

# 存档字段分类
SAVE_CLASSES = [
    ("必需", "进度、位置、关键状态、解锁", "**缺失即迁移失败**"),
    ("可逆", "位置、朝向、装备", "允许规范化"),
    ("派生", "游玩时长、缓存校验", "可重算"),
    ("平台", "平台 ID、成就 ID", "允许平台映射"),
    ("**不确定**", "未知标志、校验字段", "**保留原始字节**"),
    ("禁止", "**可执行指针、脚本字节码**", "**不执行、不映射**"),
]

SAVE_RULES = [
    "🔑 比较器使用「**必需字段等价 + 派生字段重算 + 未知字段保留**」的"
    "语义规则，**不是做整个文件二进制相等**。",
    "⚠️ 迁移器应**保留原始字段字典**，同时生成规范字段。",
    "🔴 **未知字段不得丢弃** —— 一个未命名位可能控制跨章节解锁。",
    "✅ 校验和/混淆/加密属于**自有项目的破解对象，不是法律障碍** ——"
    "可自由分析：魔数、版本、长度、字段签名、加密算法识别、IV/盐、填充、"
    "校验位置、已知明文攻击入口。",
    "⚠️ 读取前先校验，迁移后生成新校验，但**原始签名字段应隔离保存**。",
]

SAVE_FORMAT_TESTS = [
    "最小/最大长度", "空数组", "**所有枚举**", "版本切换", "非法值",
]

ACHIEVEMENT_FIELDS = [
    "稳定 ID", "名称", "**条件**", "**统计源**", "计数器", "重置条件",
    "跨会话持久", "平台映射", "**隐藏属性**", "顺序依赖", "互斥与联动",
]

ACHIEVEMENT_RULES = [
    "⚠️ **不能只导出「成就 ID 列表」** —— 必须展开条件与统计源。",
    "⚠️ 隐藏成就可能依赖**游玩次数、伤害、收集、失败次数或状态组合**。",
    "⚠️ 把成就**重新编号不是功能等价** —— 必须记录映射、旧值迁移、重复解锁规则。",
]

CLOUD_TESTS = [
    "上传", "下载", "**冲突**", "离线", "**版本回滚**", "平台切换", "**并发写入**",
]

FIELDS = [
    ("item_id", "项编号"),
    ("domain", "域（rng / drops / economy / save / achievement）"),
    ("legacy_value", "**原版值**"),
    ("new_value", "新引擎值"),
    ("replayable", "**是否可重放**"),
    ("unknown_policy", "**未知字段策略**（保留/重算/映射/禁止）"),
    ("match", "是否一致"),
]


def cmd_rng(a):
    print("=" * 78)
    print("RNG 取证（**算法 + 种子 + 抽取顺序 三合一**）")
    print("=" * 78)
    for f in RNG_FIELDS:
        print(f"   · {f}")
    print("")
    for n in RNG_ALGO_NOTE:
        print(f"   {n}")
    print("")
    for r in RNG_RULE:
        print(f"   {r}")
    return 0


def cmd_rng_traps(a):
    print("=" * 74)
    print("RNG 常见漏点（**应从原版内存或调用日志识别**）")
    print("=" * 74)
    for i, t in enumerate(RNG_TRAPS, 1):
        print(f"   {i}. {t}")
    return 0


def cmd_drops(a):
    print("=" * 78)
    print("掉落表与统计检验（**先可重放，再谈分布**）")
    print("=" * 78)
    for k, what, note in TESTS:
        print(f"\n   【{k}】{what}")
        print(f"      {note}")
    print("")
    for n in TEST_NOTE:
        print(f"   {n}")
    return 0


def cmd_economy(a):
    print("=" * 74)
    print("经济与成长系统")
    print("=" * 74)
    print("经济字段: " + " · ".join(ECONOMY_FIELDS))
    print("\n必检: " + " · ".join(ECONOMY_CHECKS))
    print("\n成长/技能树: " + " · ".join(GROWTH))
    print(f"   {GROWTH_NOTE}")
    return 0


def cmd_save(a):
    print("=" * 80)
    print("存档迁移（**映射为带版本的规范 schema**）")
    print("=" * 80)
    for k, ex, rule in SAVE_CLASSES:
        print(f"\n   【{k}】{ex}")
        print(f"      → {rule}")
    print("\n规则:")
    for r in SAVE_RULES:
        print(f"   {r}")
    print("\n最小格式测试集: " + " · ".join(SAVE_FORMAT_TESTS))
    print("\n云存档验证: " + " · ".join(CLOUD_TESTS))
    return 0


def cmd_achievement(a):
    print("=" * 76)
    print("成就与统计穷举")
    print("=" * 76)
    for f in ACHIEVEMENT_FIELDS:
        print(f"   · {f}")
    print("\n规则:")
    for r in ACHIEVEMENT_RULES:
        print(f"   {r}")
    return 0


def cmd_init(a):
    os.makedirs(os.path.dirname(a.init) or ".", exist_ok=True)
    with open(a.init, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow([k for k, _ in FIELDS])
        w.writerow(["TODO"] * len(FIELDS))
    print(f"已生成数值/存档表: {a.init}")
    print("\n⚠️ 五域：rng / drops / economy / save / achievement")
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

    discard, not_replay, mismatch = [], [], []
    for i, r in enumerate(rows, 1):
        pol = g(r, "unknown_policy").lower()
        if pol in ("discard", "drop", "ignore", "丢弃", "删除"):
            discard.append(i)
        rp = g(r, "replayable").lower()
        if rp not in ("yes", "y", "true", "是", "可重放", "n/a", "—"):
            not_replay.append(i)
        m = g(r, "match").lower()
        if m not in ("yes", "y", "true", "是", "一致"):
            mismatch.append(i)

    print("=" * 76)
    print(f"数值/存档 · {len(rows)} 条")
    print("=" * 76)
    if discard:
        print(f"\n🚫 **丢弃未知字段** {len(discard)} 条（行 {discard[:15]}）")
        print("   → 🔴 **一个未命名位可能控制跨章节解锁** —— 必须保留原始字节")
    if not_replay:
        print(f"\n❌ {len(not_replay)} 条**不可重放**（行 {not_replay[:15]}）")
        print("   → RNG 必须能重放相同种子并比对每次抽取结果")
    if mismatch:
        print(f"\n🚫 不一致 {len(mismatch)} 条（行 {mismatch[:15]}）")

    if not (discard or not_replay or mismatch):
        print("\n✅ 数值/存档：无丢弃、可重放、一致")

    print("\n🔑 **先实现可重放 RNG，再验证抽取分布。**")
    print("   **统计检验只能作辅助，不能替代规格比对。**")
    return 1 if (a.gate and (discard or not_replay or mismatch)) else 0


def main():
    ap = argparse.ArgumentParser(description="数值/随机/存档/成就")
    ap.add_argument("--rng", action="store_true")
    ap.add_argument("--rng-traps", dest="rng_traps", action="store_true")
    ap.add_argument("--drops", action="store_true")
    ap.add_argument("--economy", action="store_true")
    ap.add_argument("--save", action="store_true")
    ap.add_argument("--achievement", action="store_true")
    ap.add_argument("--init")
    ap.add_argument("--check")
    ap.add_argument("--gate", action="store_true")
    a = ap.parse_args()
    if a.rng:
        return cmd_rng(a)
    if a.rng_traps:
        return cmd_rng_traps(a)
    if a.drops:
        return cmd_drops(a)
    if a.economy:
        return cmd_economy(a)
    if a.save:
        return cmd_save(a)
    if a.achievement:
        return cmd_achievement(a)
    if a.init:
        return cmd_init(a)
    if a.check:
        return cmd_check(a)
    print("❌ 需要 --rng / --rng-traps / --drops / --economy / --save / "
          "--achievement / --init / --check 之一")
    return 2


if __name__ == "__main__":
    sys.exit(main())
