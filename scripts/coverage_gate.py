#!/usr/bin/env python3
"""覆盖率与 unknown 门禁（G2）：unknown > 0 一律阻塞，禁止声明完成。

扫两份产物:
  unknown.md   未知/待确认清单，未关闭项写作 "- [ ] ..."
  features.md  功能缺口清单，条目行形如 "| 123 | ... |"

输出:
  发现项 / 已验证项 / unknown / 覆盖率

退出码:
  0 = 通过（unknown 为 0）
  1 = 阻塞（unknown > 0，或未做故障注入标记）

用法:
  coverage_gate.py ledger/unknown.md ledger/features.md
  coverage_gate.py ledger/unknown.md ledger/features.md --require-fault-injection
"""
import argparse
import re
import sys
import os

UNKNOWN_OPEN = re.compile(r"^\s*[-*]\s*\[\s*\]\s*(.+)$")
UNKNOWN_ANY = re.compile(r"^\s*[-*]\s*\[([ xX])\]\s*(.+)$")
ROW = re.compile(r"^\|\s*(\d{1,4})\s*\|")


def scan(path, pattern):
    if not os.path.exists(path):
        print(f"⚠️  缺少 {path}（视为 0 条）")
        return []
    with open(path, encoding="utf-8", errors="replace") as f:
        return [m for m in (pattern.match(l) for l in f) if m]


def main():
    ap = argparse.ArgumentParser(description="覆盖率与 unknown 门禁")
    ap.add_argument("unknown", nargs="?", default="ledger/unknown.md")
    ap.add_argument("features", nargs="?", default="ledger/features.md")
    ap.add_argument("--require-fault-injection", action="store_true",
                    help="同时要求 features 中出现故障注入记录")
    a = ap.parse_args()

    rows = scan(a.features, ROW)
    found = len(rows)
    nums = [int(m.group(1)) for m in rows]

    any_unk = scan(a.unknown, UNKNOWN_ANY)
    open_unk = [m for m in any_unk if m.group(1).strip() == ""]

    verified = found - len(open_unk)
    cov = (verified * 100 // found) if found else 0

    print("=" * 52)
    print(f"发现项        : {found}")
    print(f"已验证/可迁移 : {verified}")
    print(f"unknown 未关闭: {len(open_unk)}")
    print(f"覆盖率        : {cov}%")
    print("=" * 52)

    ok = True
    if found == 0:
        print("❌ [G2] 没有发现任何功能项 —— 说明还没开始挖，或清单格式不对")
        ok = False
    dup = sorted({n for n in nums if nums.count(n) > 1})
    if dup:
        print(f"❌ [G2] 编号重复: {dup}")
        ok = False
    if open_unk:
        ok = False
        print(f"❌ [G2] unknown 未清零 —— **禁止声明复刻完成**。未关闭项:")
        for m in open_unk[:30]:
            print("    -", m.group(2).strip()[:90])
    if a.require_fault_injection:
        txt = open(a.features, encoding="utf-8", errors="replace").read() \
            if os.path.exists(a.features) else ""
        if "故障注入" not in txt:
            print("❌ [G5] 未见故障注入记录 —— 校验脚本未经验证，视为未验证")
            ok = False

    if ok:
        print("✅ [G2] unknown 已清零，可进入下一阶段")
        return 0
    print("\n处置：按 切角 → 层 → 文件档位 → 复查轮 顺序继续挖，不许收工。")
    return 1


if __name__ == "__main__":
    sys.exit(main())
