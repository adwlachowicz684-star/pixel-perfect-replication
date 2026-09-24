#!/usr/bin/env python3
"""编号自检：口头声称的总数必须与脚本统计一致。

⚠️ 踩过的坑：卷首索引里写 `#123` 而非 `| 123 |`，
会把索引误当新条目（实证：说 662，统计出 666）。
本脚本只统计表格行首的数字列，索引区请一律用表格形式。

用法:
  renumber_check.py ledger/features.md
  renumber_check.py ledger/features.md --fix-report
"""
import argparse
import re
import sys
import os

ROW = re.compile(r"^\|\s*(\d{1,4})\s*\|")


def main():
    ap = argparse.ArgumentParser(description="清单编号自检")
    ap.add_argument("file", nargs="?", default="ledger/features.md")
    ap.add_argument("--start", type=int, default=1, help="起始编号，默认 1")
    a = ap.parse_args()

    if not os.path.exists(a.file):
        print(f"❌ 文件不存在: {a.file}")
        return 1

    with open(a.file, encoding="utf-8", errors="replace") as f:
        lines = f.readlines()

    nums, hash_refs = [], []
    for i, l in enumerate(lines, 1):
        m = ROW.match(l)
        if m:
            nums.append(int(m.group(1)))
        elif re.match(r"^#{1,6}\s*#\d+", l):
            hash_refs.append((i, l.strip()[:60]))

    if not nums:
        print("❌ 未统计到任何条目行（形如 `| 123 | ...`）")
        return 1

    total = len(nums)
    lo, hi = min(nums), max(nums)
    dup = sorted({n for n in nums if nums.count(n) > 1})
    gap = [n for n in range(a.start, hi + 1) if n not in set(nums)]

    print(f"条目数   : {total}")
    print(f"编号范围 : {lo} - {hi}")
    print(f"重复编号 : {dup if dup else '无'}")
    print(f"缺号     : {gap if gap else '无'}")

    ok = True
    if dup:
        ok = False
        print("❌ 存在重复编号")
    if gap:
        ok = False
        print(f"❌ 存在缺号（{len(gap)} 个）")
    if hash_refs:
        print(f"⚠️  检测到 {len(hash_refs)} 处标题式引用（`#123`），"
              f"不会被计入统计 —— 若这是索引，请确认不会与正文编号混淆:")
        for i, s in hash_refs[:5]:
            print(f"    L{i}: {s}")

    if ok:
        print(f"✅ 编号连续无重复，口头总数应表述为 {total}")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
