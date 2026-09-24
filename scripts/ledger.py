#!/usr/bin/env python3
"""文件台账：全量入账 / 未读 diff / 按档位列 / 清零率 / 门禁。

穷尽挖掘的主判据 —— "感觉挖得差不多了"不可靠，台账把"挖过没有"变成可查询的事实。

用法:
  ledger.py --init   --src <原版src> --ledger ledger/files.csv
  ledger.py --unread --ledger ledger/files.csv
  ledger.py --by-band --band 60-150 --ledger ledger/files.csv
  ledger.py --gate   --src <原版src> --ledger ledger/files.csv
  ledger.py --stats  --ledger ledger/files.csv
"""
import argparse
import csv
import os
import sys

FIELDS = ["path", "lines", "band", "skim", "deep", "review", "items", "doubts", "status"]

# 允许的源码后缀（不在列表里的文件仍会入账，但不计入行数档位统计）
CODE_EXT = {".cs", ".xaml", ".rs", ".ts", ".tsx", ".js", ".jsx", ".py", ".go",
            ".java", ".cpp", ".h", ".c", ".vue", ".json", ".yaml", ".yml", ".md",
            ".css", ".scss", ".xml", ".ini", ".sh", ".ps1", ".toml"}


def band_of(n):
    if n > 500:
        return "大>500"
    if n > 150:
        return "中上150-500"
    if n > 60:
        return "中等60-150"
    return "小<=60"


def count_lines(p):
    try:
        with open(p, encoding="utf-8", errors="replace") as f:
            return sum(1 for _ in f)
    except Exception:
        return 0


def walk(src):
    out = []
    for root, dirs, files in os.walk(src):
        dirs[:] = [d for d in dirs if d not in
                   (".git", "node_modules", "target", "bin", "obj", "dist", "build")]
        for fn in files:
            out.append(os.path.join(root, fn))
    return sorted(out)


def load(path):
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8", errors="replace", newline="") as f:
        return list(csv.DictReader(f))


def save(path, rows):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in FIELDS})


def cmd_init(a):
    files = walk(a.src)
    rows = []
    for p in files:
        ext = os.path.splitext(p)[1].lower()
        n = count_lines(p) if ext in CODE_EXT else 0
        rows.append({"path": p, "lines": n, "band": band_of(n) if n else "-",
                     "skim": "", "deep": "", "review": "", "items": "0",
                     "doubts": "0", "status": "未读"})
    save(a.ledger, rows)
    print(f"入账 {len(rows)} 个文件 -> {a.ledger}")
    print("档位分布:")
    for b in ["大>500", "中上150-500", "中等60-150", "小<=60", "-"]:
        c = sum(1 for r in rows if r["band"] == b)
        if c:
            print(f"  {b}: {c}")


def cmd_unread(a):
    rows = load(a.ledger)
    todo = [r for r in rows if r["status"].strip() != "清零"]
    print(f"未清零 {len(todo)} / {len(rows)}")
    for r in todo:
        print(f"  [{r['status'] or '未读'}] {r['band']} {r['lines']:>5} {r['path']}")


def cmd_by_band(a):
    rows = load(a.ledger)
    todo = [r for r in rows if r["status"].strip() != "清零" and r["band"] == a.band]
    print(f"档位 {a.band}: 未清零 {len(todo)}")
    for r in todo:
        print(f"  {r['lines']:>5} {r['path']}")


def cmd_stats(a):
    rows = load(a.ledger)
    if not rows:
        print("台账为空，先跑 --init")
        return
    total = len(rows)
    done = sum(1 for r in rows if r["status"].strip() == "清零")
    items = sum(int(r["items"] or 0) for r in rows)
    doubts = sum(int(r["doubts"] or 0) for r in rows)
    print(f"文件总数 {total} | 清零 {done} | 清零率 {done * 100 // total}%")
    print(f"累计产出项 {items} | 待清疑问 {doubts}")


def cmd_gate(a):
    """门禁 G1：未读文件为 0、清零率 100%。不通过退出码 1。"""
    rows = load(a.ledger)
    ok = True
    if not rows:
        print("❌ [G1] 台账为空")
        return 1
    # 1) 台账是否覆盖全部实际文件
    if a.src and os.path.isdir(a.src):
        actual = set(walk(a.src))
        known = {r["path"] for r in rows}
        missing = sorted(actual - known)
        if missing:
            ok = False
            print(f"❌ [G1] 有 {len(missing)} 个文件未入账:")
            for m in missing[:20]:
                print("   ", m)
    # 2) 是否全部清零
    todo = [r for r in rows if r["status"].strip() != "清零"]
    if todo:
        ok = False
        print(f"❌ [G1] 有 {len(todo)} 个文件未清零（不许跳档，按档位继续）:")
        for r in todo[:20]:
            print(f"    [{r['status'] or '未读'}] {r['band']} {r['path']}")
    if ok:
        print(f"✅ [G1] 台账 {len(rows)} 个文件全部清零")
        return 0
    return 1


def main():
    ap = argparse.ArgumentParser(description="文件台账与穷尽门禁")
    ap.add_argument("--init", action="store_true")
    ap.add_argument("--unread", action="store_true")
    ap.add_argument("--by-band", action="store_true")
    ap.add_argument("--stats", action="store_true")
    ap.add_argument("--gate", action="store_true")
    ap.add_argument("--src", default="")
    ap.add_argument("--ledger", default="ledger/files.csv")
    ap.add_argument("--band", default="中等60-150")
    a = ap.parse_args()

    if a.init:
        cmd_init(a)
    elif a.unread:
        cmd_unread(a)
    elif a.by_band:
        cmd_by_band(a)
    elif a.stats:
        cmd_stats(a)
    elif a.gate:
        sys.exit(cmd_gate(a))
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
