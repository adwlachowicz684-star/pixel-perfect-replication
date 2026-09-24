#!/usr/bin/env python3
"""功能对照表校验（S3/S5/S7）—— 原先有什么、现在有什么、每条怎么定的。

**为什么需要**：台账 `features.md` 管"挖全了没"，
对照表管"每条怎么定的、哪些还没定"。**两者互补，不是替代**。

五类处置（每行必填，不许空）:
  原样复刻 | 考虑优化 | 架构性调整 | 需要讨论 | 不适用

**❗ 本脚本最硬的检查是"需要讨论"项** ——
只有写全 `卡在哪 / 谁拍板 / 截止时间 / 超时默认动作` 才算登记完成。
**没有超时默认动作，"讨论"就会无限期挂着**，最后变成一笔糊涂账。

用法:
  feature_matrix.py --check ledger/feature_matrix.md
  feature_matrix.py --check ledger/feature_matrix.md --gate
  feature_matrix.py --check ledger/feature_matrix.md --features ledger/features.md --gate
  feature_matrix.py --init ledger/feature_matrix.md
  feature_matrix.py --classes

退出码: 0 无阻断 / 1 有阻断项 / 2 用法或文件错误
"""
import argparse
import os
import re
import sys

DISPOSITIONS = ["原样复刻", "考虑优化", "架构性调整", "需要讨论", "不适用"]

# discuss 必须写全的四栏
DISCUSS_FIELDS = ["卡在哪", "谁拍板", "截止时间", "超时默认"]

VALID_STATUS = ["待判", "待做", "进行中", "完成", "待拍板", "已裁定"]

TEMPLATE = """# 功能对照表

| 编号 | 功能 | 原版 | 新版 | 处置 | 依据（证据卡/性质） | 状态 |
|---|---|---|---|---|---|---|
| 1 | 示例：跨栏拖到空白=换栏移动 | ✅ | ✅ | 原样复刻 | E-001 设计意图 | 完成 |
| 2 | 示例：名称校验三处重复 | ✅ | ✅ | 考虑优化 | E-002 无意识坏味 → merge | 完成 |
| 3 | 示例：配置读写散落多处 | ✅ | ✅ | 架构性调整 | E-003 统一入口 | 完成 |
| 4 | 示例：启动弹更新提示 | ✅ | ❌ | 需要讨论 | 卡在哪：无证据判断使用量 / 谁拍板：产品 / 截止时间：TODO / 超时默认：按原样复刻 | 待拍板 |
| 5 | 示例：托盘图标动画 | ✅ | ❌ | 不适用 | 平台差异 | 已裁定 |
| 6 | 示例：深色模式跟随系统 | ❌ | ✅ | — | 反向清单 R-001 | 勿删 |

**处置五选一**：{d}
**⚠️「需要讨论」必须写全四栏**：{f}
"""


def parse_table(text, need=None):
    """解析 Markdown 表格。

    need=None → 通用模式：表头含「编号」即认，适合任何清单对账。
    need=(...) → 要求表头含指定列名（用于找主表）。
    """
    rows = [l for l in text.splitlines()
            if l.strip().startswith("|") and not re.match(r"^\|[\s\-:|]+\|$", l.strip())]
    header, items = None, []
    for l in rows:
        cells = [c.strip() for c in l.strip().strip("|").split("|")]
        if header is None:
            if need:
                ok = all(any(n in c for c in cells) for n in need)
            else:
                ok = any("编号" in c for c in cells)
            if ok:
                header = cells
            continue
        if len(cells) != len(header):
            continue
        items.append(dict(zip(header, cells)))
    return items


def idx_of(d, *names):
    for n in names:
        for k in d:
            if n in k:
                return d[k]
    return ""


def cmd_classes(a):
    print("五类处置（每行必填，不许空）:")
    for d, why in [
        ("原样复刻", "行为、参数、文案、边界全照搬；须附证据卡 ID + 性质"),
        ("考虑优化", "换实现但**行为等价**；须附新方案 + **边界如何等价**"),
        ("架构性调整", "跨模块重组；须附重组前后对照 + 每个原入口的新落点"),
        ("需要讨论", "卡住了；**须写全四栏**，否则不算登记完成"),
        ("不适用", "平台或架构差异；须附差异说明"),
    ]:
        print(f"   {d:<10} {why}")
    print("\n四条判据（区分这五类）:")
    for q, a_ in [
        ("去掉它，体验或正确性会受损吗？", "会 → 原样复刻"),
        ("换实现但行为不变吗？", "是 → 考虑优化"),
        ("动的是模块边界而非单点实现吗？", "是 → 架构性调整"),
        ("拿不到证据 / 需要业务裁决吗？", "是 → 需要讨论"),
    ]:
        print(f"   {q}  {a_}")
    print("\n三种「不齐」状态:")
    for o, n, why in [
        ("✅", "❌", "**缺口** —— 是「还没做」还是「有意不迁移」？后者要写理由"),
        ("❌", "✅", "**增强** —— 记入反向清单（勿删），别在对齐时被误删"),
        ("✅", "✅", "已对齐 —— 处置四选一"),
    ]:
        print(f"   原版{o} 新版{n} → {why}")
    print("\n⚠️ 「原版有新版无」且状态为「完成」是最危险的组合 ——")
    print("   说明被当成做完了，实际是丢了。脚本会单独挑出来。")
    return 0


def cmd_init(a):
    os.makedirs(os.path.dirname(a.init) or ".", exist_ok=True)
    body = TEMPLATE.format(d=" / ".join(DISPOSITIONS), f=" / ".join(DISCUSS_FIELDS))
    with open(a.init, "w", encoding="utf-8") as f:
        f.write(body)
    print(f"已生成功能对照表骨架: {a.init}")
    print("\n⚠️ 「需要讨论」项必须写全四栏，否则 --gate 会阻断。")
    return 0


def cmd_check(a):
    if not os.path.exists(a.check):
        print(f"❌ 文件不存在: {a.check}")
        return 2
    with open(a.check, encoding="utf-8", errors="replace") as f:
        text = f.read()

    items = parse_table(text, need=("功能", "处置"))
    if not items:
        print("❌ 未解析到表体（表头需含「功能」与「处置」两列）")
        return 2

    print("=" * 68)
    print(f"功能对照表 · {len(items)} 条")
    print("=" * 68)

    counts, blockers, warns = {}, [], []

    for it in items:
        no = idx_of(it, "编号")
        name = idx_of(it, "功能")
        old = idx_of(it, "原版")
        new = idx_of(it, "新版")
        disp = idx_of(it, "处置")
        basis = idx_of(it, "依据")
        status = idx_of(it, "状态")
        tag = f"{no} {name}".strip()[:40]

        # 1. 处置必填
        if not disp or disp == "—":
            if old.strip() and new.strip() and old == new:
                blockers.append((tag, "处置栏为空（原版新版都有 → 必须定处置）"))
            continue
        hit = next((d for d in DISPOSITIONS if d in disp), None)
        if hit is None:
            blockers.append((tag, f"处置「{disp}」不在五类中"))
            continue
        counts[hit] = counts.get(hit, 0) + 1

        # 2. discuss 四栏
        if hit == "需要讨论":
            missing = [f for f in DISCUSS_FIELDS
                       if f not in basis and f not in disp and f not in it.get("功能", "")]
            if missing:
                blockers.append((tag, f"「需要讨论」缺 {len(missing)} 栏: {', '.join(missing)}"))
            elif "TODO" in basis or "待填" in basis:
                blockers.append((tag, "「需要讨论」四栏含 TODO/待填"))
            if status and status.strip() not in ("待拍板", "完成"):
                warns.append((tag, f"需讨论项状态为「{status}」，建议「待拍板」"))

        # 3. 不适用须有说明
        if hit == "不适用" and (not basis or basis == "—"):
            blockers.append((tag, "「不适用」缺差异说明"))

        # 4. 原版有新版无 + 已完成 = 危险组合
        if "✅" in old and ("❌" in new or not new.strip()):
            if hit != "不适用" and "完成" in status:
                blockers.append((tag, "**原版有新版无却标完成** —— 被当做了，实际丢了"))
            elif hit != "不适用":
                warns.append((tag, "原版有新版无：需说明是「还没做」还是「有意不迁移」"))

        # 5. 状态合法性
        if status and status.strip() and status.strip() not in VALID_STATUS \
                and "勿删" not in status:
            warns.append((tag, f"状态「{status}」不在 {VALID_STATUS}"))

    print("\n处置分布:")
    for d in DISPOSITIONS:
        print(f"   {d:<10} {counts.get(d, 0)}")
    print(f"   {'（增强/勿删）':<10} {len(items) - sum(counts.values())}")

    if blockers:
        print(f"\n❌ 阻断 {len(blockers)} 项:")
        for tag, why in blockers:
            print(f"   {tag} — {why}")
    if warns:
        print(f"\n⚠️  提醒 {len(warns)} 项:")
        for tag, why in warns[:12]:
            print(f"   {tag} — {why}")

    # 与功能清单对账
    if a.features:
        if not os.path.exists(a.features):
            print(f"\n❌ 功能清单不存在: {a.features}")
            return 2
        with open(a.features, encoding="utf-8", errors="replace") as f:
            fitems = parse_table(f.read())
        fids = {str(idx_of(i, "编号")).strip() for i in fitems}
        mids = {str(idx_of(i, "编号")).strip() for i in items}
        fids.discard("")
        mids.discard("")
        only_f = sorted(fids - mids)
        only_m = sorted(mids - fids)
        print(f"\n对账（功能清单 {len(fids)} vs 对照表 {len(mids)}）:")
        if only_f:
            print(f"   ❌ 台账有、对照表无 {len(only_f)} 条: {', '.join(only_f[:15])}")
            print("      → 挖到了但**没定处置**")
            blockers.append(("对账", f"{len(only_f)} 条功能未定处置"))
        if only_m:
            print(f"   ❌ 对照表有、台账无 {len(only_m)} 条: {', '.join(only_m[:15])}")
            print("      → 定了处置但**没进台账**")
            blockers.append(("对账", f"{len(only_m)} 条功能未进台账"))
        if not only_f and not only_m:
            print("   ✅ 双向对齐")

    if not blockers and not warns:
        print("\n✅ 对照表完整")

    print("\n⚠️ 收工判据：无「待判」、无「待拍板」、")
    print("   无「原版有新版无却标完成」的项。")
    print("⚠️ 「需要讨论」超时默认动作必须写 ——")
    print("   **默认按「原样复刻」执行**（保守优先：漏做是确定的缺失）。")

    return 1 if (a.gate and blockers) else 0


def main():
    ap = argparse.ArgumentParser(description="功能对照表校验")
    ap.add_argument("--check", help="对照表文件")
    ap.add_argument("--features", help="功能清单，做双向对账")
    ap.add_argument("--init", help="生成骨架")
    ap.add_argument("--gate", action="store_true")
    ap.add_argument("--classes", action="store_true")
    a = ap.parse_args()

    if a.classes:
        return cmd_classes(a)
    if a.init:
        return cmd_init(a)
    if a.check:
        return cmd_check(a)
    print("❌ 需要 --check / --init / --classes 之一")
    return 2


if __name__ == "__main__":
    sys.exit(main())
