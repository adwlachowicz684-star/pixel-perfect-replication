#!/usr/bin/env python3
"""odiff 封装 —— 图像差异，含抗锯齿识别。

**⚠️ 最关键的一条纪律**：
> **odiff 的抗锯齿忽略是「候选分类」，不是「默认豁免」。**

像素级复刻的目标是**保留原版外观**，所以必须把"边缘变化"拆成两类：
1. 无法消除的渲染环境差 → 入 `known_environmental_diff`
2. **真实的圆角/渐变/阴影变化** → **仍进契约回归**

**这个区别是本 Skill 与普通视觉回归产品最关键的分界。**

用法:
  odiff_image.py --old a.png --new b.png --out ledger/image_diff.json
  odiff_image.py --old a.png --new b.png --threshold 0.1 --gate
  odiff_image.py --classes          # 打印差异分类判据

退出码: 0 无差异或已分类 / 1 --gate 且超阈值 / 2 工具不可用
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import require, run, emit, print_summary  # noqa: E402

CLASSES = [
    ("antialiasing", "抗锯齿/亚像素",
     "**可归入 known_environmental_diff** —— 但仅当确属渲染环境差"),
    ("real_geometry", "真实几何变化",
     "圆角、边框宽度、间距 → **必须进契约回归**"),
    ("real_color", "真实颜色变化",
     "渐变、阴影、透明度 → **必须进契约回归**"),
    ("missing_element", "元素缺失/多余",
     "与 UIA/DOM 节点证据互证，**不许只凭像素**"),
    ("unknown", "未定", "**阻止自动收工**，进人工复核"),
]


def cmd_classes(a):
    print("差异分类（**抗锯齿不是默认豁免**）:")
    for k, name, action in CLASSES:
        print(f"\n【{name}】 {k}")
        print(f"   处置: {action}")
    print("\n⚠️ 只保留分类名而删除原始截图 → 后续无法复核。")
    print("   只保留截图而不解释 → 无法完成穷尽验收。")
    print("   **两者都要。**")
    return 0


def cmd_run(a):
    if not (os.path.exists(a.old) and os.path.exists(a.new)):
        print("❌ 图片不存在")
        return 2

    spec = require("odiff")
    if spec is None:
        emit("odiff", False, a.out,
             warnings=["odiff 不可用 —— 图像差异证据未采集，必须进 unknown"])
        return 2

    cmd = ["odiff", a.old, a.new, a.diff_out]
    if a.threshold is not None:
        cmd += ["--threshold", str(a.threshold)]
    if a.ignore:
        cmd += ["--ignore", a.ignore]
    rc, out, err = run(cmd, timeout=300)
    combined = (out or "") + (err or "")

    # odiff: 0=无差异 1=有差异 2=错误
    if rc == 0:
        diff = False
        detail = "无差异"
    elif rc == 1:
        diff = True
        detail = combined.strip()[:200] or "有差异（未给数值）"
    else:
        print(f"❌ odiff 错误 rc={rc}: {combined[:200]}")
        emit("odiff", False, a.out, warnings=[f"odiff 错误: {combined[:200]}"])
        return 2

    warn = []
    if diff:
        warn.append("存在图像差异 —— **必须归类**：是抗锯齿还是真实几何/颜色变化？")
        warn.append("不许直接标 known_environmental_diff 了事")

    rec = emit("odiff", True, a.out,
               evidence=[f"old={a.old}", f"new={a.new}",
                         f"threshold={a.threshold}", f"结果: {detail}"],
               warnings=warn,
               extra={"has_diff": diff, "detail": detail,
                      "diff_image": a.diff_out if diff else None,
                      "class": "unknown" if diff else "identical"})
    print_summary(rec)

    if diff:
        print("\n⚠️ 下一步：用 `diff_classify.py` 归类到十类根因之一。")
        print("   `structural` 与 `unknown` 必须人工复核，**不许自动收工**。")
        return 1 if a.gate else 0
    return 0


def main():
    ap = argparse.ArgumentParser(description="odiff 图像差异（抗锯齿感知）")
    ap.add_argument("--old")
    ap.add_argument("--new")
    ap.add_argument("--out", default="ledger/image_diff.json")
    ap.add_argument("--diff-out", dest="diff_out", default="ledger/diff.png")
    ap.add_argument("--threshold", type=float)
    ap.add_argument("--ignore", help="忽略区域文件")
    ap.add_argument("--gate", action="store_true")
    ap.add_argument("--classes", action="store_true")
    a = ap.parse_args()

    if a.classes:
        return cmd_classes(a)
    if not (a.old and a.new):
        print("❌ 需要 --old 与 --new（或 --classes）")
        return 2
    return cmd_run(a)


if __name__ == "__main__":
    sys.exit(main())
