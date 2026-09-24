#!/usr/bin/env python3
"""BUG 与审查问题清单的分诊统计 + 门禁（G11）。

扫 `ledger/bugs.md` 的表格清单，检查:
  1. P0 / P1 未处置项     —— 硬阻塞（含 [险] 标记）
  2. B5 存疑未确认项      —— 硬阻塞（等同 unknown，不许默认当 BUG 修）
  3. 分诊=简单但未修复    —— 警告：简单项应当场给方案并修掉
  4. 类别 B1（原版 BUG）已修但清单里未见行为变更登记 —— 警告：静默改需求
  5. 编号重复/缺号

表格列按表头名定位（编号/类别/严重度/分诊/状态），找不到表头则用默认列序。

用法:
  bug_triage.py ledger/bugs.md
  bug_triage.py ledger/bugs.md --gate          # 有阻塞项退出码 1（CI 用）
  bug_triage.py ledger/bugs.md --strict        # 警告也算阻塞
"""
import argparse
import os
import re
import sys

# 已处置状态（视为关闭）
DONE = {"已完成", "已修", "已修复", "已修（当场）", "决定不修", "已确认非BUG",
        "已确认非 BUG", "已作废", "不适用"}
# 未处置状态
OPEN = {"待修", "待确认", "待分诊", "待判", "进行中", "未处理", ""}

BLOCK_SEV = {"P0", "P1"}


def parse(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        lines = f.read().splitlines()

    header_idx = {}   # 列名 -> 列序号（0 基，去掉首尾空列后的数据列序号）
    rows = []
    for l in lines:
        s = l.strip()
        if not s.startswith("|"):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        joined = "".join(cells)
        if set(joined) <= set("-: "):      # 分隔行
            continue
        if not header_idx and any(k in c for c in cells for k in ("编号", "严重度")):
            for i, c in enumerate(cells):
                for key in ("编号", "类别", "严重度", "分诊", "状态"):
                    if key in c:
                        header_idx.setdefault(key, i)
            continue
        if not any(re.match(r"^B-?\d+", c) for c in cells):
            continue
        rows.append(cells)

    def col(r, key, default):
        i = header_idx.get(key, default)
        return r[i] if i < len(r) else ""

    out = []
    for r in rows:
        bid = next((c for c in r if re.match(r"^B-?\d+", c)), "?")
        out.append({
            "id": bid,
            "cat": col(r, "类别", 3),
            "sev": col(r, "严重度", 4).upper(),
            "triage": col(r, "分诊", 5),
            "status": col(r, "状态", 6),
            "raw": " | ".join(r),
        })
    return out, lines


def main():
    ap = argparse.ArgumentParser(description="BUG 清单分诊与门禁")
    ap.add_argument("file", nargs="?", default="ledger/bugs.md")
    ap.add_argument("--gate", action="store_true", help="有阻塞项退出码 1")
    ap.add_argument("--strict", action="store_true", help="警告也算阻塞")
    a = ap.parse_args()

    if not os.path.exists(a.file):
        print(f"⚠️  缺少 {a.file}（视为 0 条；若确实还没挖到 BUG 属正常）")
        return 0

    rows, lines = parse(a.file)
    if not rows:
        print(f"⚠️  {a.file} 中未解析到 B-N 条目行")
        return 0

    text = "\n".join(lines)
    has_change_reg = ("行为变更登记" in text) or ("intentional-change" in text)

    by_cat, by_sev = {}, {}
    blockers, warns = [], []
    for r in rows:
        by_cat[r["cat"]] = by_cat.get(r["cat"], 0) + 1
        by_sev[r["sev"]] = by_sev.get(r["sev"], 0) + 1
        st, sev, cat = r["status"], r["sev"], r["cat"]
        risky = "[险]" in r["raw"]
        closed = st in DONE

        if not closed:
            if any(p in sev for p in BLOCK_SEV) or risky:
                blockers.append(f"{r['id']} [{sev}]{'(险)' if risky else ''} "
                                f"{r['raw'][:70]} —— 状态：{st or '空'}")
            elif "B5" in cat or "待确认" in st:
                blockers.append(f"{r['id']} [B5 存疑] {r['raw'][:70]} "
                                f"—— 未确认前不许当 BUG 修（等同 unknown）")
        if "简单" in r["triage"] and not closed:
            warns.append(f"{r['id']} 分诊=简单但未修复 —— 简单项应当场给方案并修掉")
        if "B1" in cat and closed and not has_change_reg:
            warns.append(f"{r['id']} 是原版 BUG 且已修，但清单中未见「行为变更登记」"
                         f" —— 修原版 BUG 属于有意行为变更，不登记 = 静默改需求")

    ids = [r["id"] for r in rows]
    dup = sorted({i for i in ids if ids.count(i) > 1})
    if dup:
        warns.append(f"编号重复: {dup}")

    print("=" * 60)
    print(f"BUG 与审查问题 {len(rows)} 条")
    print(f"类别分布 : {by_cat}")
    print(f"严重度   : {by_sev}")
    print("=" * 60)

    for w in warns:
        print(f"⚠️  {w}")

    if blockers:
        print(f"\n❌ [G11] {len(blockers)} 项未处置（硬阻塞，必须修完才许收工）:")
        for b in blockers:
            print("   ", b)
        print("\n处置：简单项当场给方案并修掉；复杂项进批次但收工前必须修完。")
        print("      B5 存疑项先确认是不是真 BUG —— 不许默认当 BUG 修。")
        rc = 1 if a.gate else 0
    else:
        print("\n✅ [G11] 无未处置的阻断/严重项")
        rc = 1 if (a.strict and warns) else 0

    return rc


if __name__ == "__main__":
    sys.exit(main())
