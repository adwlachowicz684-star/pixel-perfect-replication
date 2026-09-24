#!/usr/bin/env python3
"""证据检索层 —— 上万条证据怎么查、怎么对账、怎么防重复。

**为什么需要**：S2 挖出上万条证据（features/bugs/params/assets/texts/faults），
全是 CSV/Markdown，**没有检索层就查不动、对不上账、容易重复挖同一条**。

优先用 DuckDB（能直接 SQL 查 CSV/JSON/Parquet）；
**不可用时降级为纯 Python 实现**，保证核心查询**任何环境都能跑**。

用法:
  duckdb_evidence.py --work work/ --stats              # 各清单条目数
  duckdb_evidence.py --work work/ --cross              # 台账 ↔ 对照表对账
  duckdb_evidence.py --work work/ --dup                # 疑似重复条目
  duckdb_evidence.py --work work/ --search "拖拽"      # 全文搜索
  duckdb_evidence.py --work work/ --sql "SELECT ..."   # 原生 SQL（需 duckdb）

退出码: 0 正常 / 1 对账不一致 / 2 用法错误
"""
import argparse
import csv
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import get_spec  # noqa: E402

LEDGERS = {
    "features": "ledger/features.md",
    "bugs": "ledger/bugs.md",
    "feature_matrix": "ledger/feature_matrix.md",
    "params": "ledger/params.md",
    "texts": "ledger/texts.md",
    "faults": "ledger/faults.csv",
    "unknown": "ledger/unknown.md",
    "assets": "ledger/assets.md",
}


def parse_md_table(path):
    """从 Markdown 里抽出表格行（跳过分隔行）。"""
    if not os.path.exists(path):
        return None, []
    header, items = None, []
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            s = line.strip()
            if not s.startswith("|"):
                continue
            cells = [c.strip() for c in s.strip("|").split("|")]
            if all(set(c) <= set("-: ") for c in cells if c):
                continue
            if header is None:
                header = cells
                continue
            if len(cells) != len(header):
                continue
            items.append(dict(zip(header, cells)))
    return header, items


def load_csv(path):
    if not os.path.exists(path):
        return None, []
    with open(path, encoding="utf-8", errors="replace", newline="") as f:
        rd = csv.DictReader(f)
        rows = list(rd)
    return (rd.fieldnames or []), rows


def load_ledger(work, rel):
    p = os.path.join(work, rel)
    if rel.endswith(".csv"):
        return load_csv(p)
    return parse_md_table(p)


def col(row, *names):
    for n in names:
        for k in row:
            if n in k:
                return row[k]
    return ""


def cmd_stats(a):
    print("=" * 66)
    print(f"证据统计 · {a.work}")
    print("=" * 66)
    total = 0
    for name, rel in LEDGERS.items():
        _, items = load_ledger(a.work, rel)
        if items is None:
            print(f"   {name:<16} （文件不存在）")
            continue
        total += len(items)
        print(f"   {name:<16} {len(items)}")
    print(f"\n   合计 {total}")
    print("\n⚠️ 条目数 0 的清单要确认：是「真的没有」还是「还没挖」。")
    print("   **这两者必须区分**，否则会误判为穷尽。")
    return 0


def cmd_cross(a):
    _, feats = load_ledger(a.work, LEDGERS["features"])
    _, matrix = load_ledger(a.work, LEDGERS["feature_matrix"])
    if not feats and not matrix:
        print("❌ 两份清单都不存在或为空")
        return 2
    fids = {col(r, "编号").strip() for r in (feats or [])}
    mids = {col(r, "编号").strip() for r in (matrix or [])}
    fids.discard("")
    mids.discard("")
    only_f = sorted(fids - mids)
    only_m = sorted(mids - fids)

    print("=" * 66)
    print(f"台账 ↔ 对照表对账（{len(fids)} vs {len(mids)}）")
    print("=" * 66)
    if only_f:
        print(f"\n❌ 台账有、对照表无 {len(only_f)}: {', '.join(only_f[:20])}")
        print("   → 挖到了但**没定处置**")
    if only_m:
        print(f"\n❌ 对照表有、台账无 {len(only_m)}: {', '.join(only_m[:20])}")
        print("   → 定了处置但**没进台账**")
    if not only_f and not only_m:
        print("\n✅ 双向对齐")
    return 1 if (only_f or only_m) else 0


def cmd_dup(a):
    print("=" * 66)
    print("疑似重复条目（同一清单内功能名/文案高度相似）")
    print("=" * 66)
    found = 0
    for name, rel in LEDGERS.items():
        _, items = load_ledger(a.work, rel)
        if not items:
            continue
        seen = {}
        for r in items:
            key = col(r, "功能", "一句话", "文案", "名称", "name").strip()
            if not key or key in ("—", "-"):
                continue
            norm = "".join(ch for ch in key if ch.isalnum())
            if not norm:
                continue
            if norm in seen:
                print(f"   [{name}] 「{key}」 与 「{seen[norm]}」 疑似重复")
                found += 1
            else:
                seen[norm] = key
    if not found:
        print("   ✅ 未发现明显重复")
    else:
        print(f"\n   共 {found} 组疑似重复")
        print("   ⚠️ 重复条目要标明是「同一条」还是「确实两个」——")
        print("      否则以后会**重新挖一遍当新发现**。")
    return 0


def cmd_search(a):
    q = a.search
    print("=" * 66)
    print(f"搜索「{q}」")
    print("=" * 66)
    hits = 0
    for name, rel in LEDGERS.items():
        _, items = load_ledger(a.work, rel)
        for r in (items or []):
            blob = " ".join(str(v) for v in r.values())
            if q in blob:
                title = col(r, "功能", "一句话", "文案", "名称", "name")[:40]
                print(f"   [{name}] {title}")
                hits += 1
    print(f"\n   共 {hits} 条命中")
    if hits == 0:
        print("   ⚠️ 0 命中要确认：是「真没有」还是「用了不同措辞」。")
        print("      **0 命中不等于不存在** —— 换同义词再搜一次。")
    return 0


def cmd_sql(a):
    try:
        import duckdb
    except ImportError:
        print("❌ 原生 SQL 需要 duckdb：`pip install duckdb`")
        print("   ⚠️ 降级：本脚本的 --stats / --cross / --dup / --search ")
        print("      均为纯 Python 实现，**不依赖 duckdb，可直接使用**。")
        return 2
    con = duckdb.connect()
    for name, rel in LEDGERS.items():
        p = os.path.join(a.work, rel)
        if rel.endswith(".csv") and os.path.exists(p):
            con.execute(f"CREATE VIEW {name} AS SELECT * FROM read_csv_auto('{p}')")
    try:
        res = con.execute(a.sql).fetchall()
        for row in res:
            print(row)
    except Exception as e:
        print(f"❌ SQL 失败: {e}")
        print("   ⚠️ Markdown 表格无法直接 SQL 查询（非结构化）；")
        print("      CSV 清单（faults）可查，Markdown 请用 --search。")
        return 2
    return 0


def main():
    ap = argparse.ArgumentParser(description="证据检索层")
    ap.add_argument("--work", default="work")
    ap.add_argument("--stats", action="store_true")
    ap.add_argument("--cross", action="store_true")
    ap.add_argument("--dup", action="store_true")
    ap.add_argument("--search")
    ap.add_argument("--sql")
    a = ap.parse_args()

    if a.cross:
        return cmd_cross(a)
    if a.dup:
        return cmd_dup(a)
    if a.search:
        return cmd_search(a)
    if a.sql:
        return cmd_sql(a)
    if a.stats:
        return cmd_stats(a)
    print("❌ 需要 --stats / --cross / --dup / --search / --sql 之一")
    return 2


if __name__ == "__main__":
    sys.exit(main())
