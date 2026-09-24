#!/usr/bin/env python3
"""OCR 封装 —— 从截图反推文案（**拿不到源码时的候选证据**）。

**⚠️ 定位必须说清**：
> OCR 结果**只能作候选**，不能替代源码文案清单，**必须人工确认**。

它解决的是"原版跑不起来、源码不全时，至少知道界面上写了什么"。
但 OCR 会漏（小字号、低对比度、复杂背景）也会错（形近字、字体替换），
**把 OCR 结果当真文案是危险的**。

**优先级顺序**：
  源码资源文件 > 反编译字符串表 > 运行时 UI 自动化提取 > **OCR（最后手段）**

用法:
  ocr_text.py --image shot.png --out ledger/ocr_texts.csv --lang chi_sim+eng
  ocr_text.py --image shot.png --compare ledger/texts-old.csv   # 与已知文案比对

退出码: 0 正常 / 2 工具不可用或用法错误
"""
import argparse
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import require, run, emit, print_summary  # noqa: E402

PRIORITY = [
    ("1 源码资源文件", "最可靠 —— .resx / .xaml / 语言包"),
    ("2 反编译字符串表", "ILSpy / ilspycmd 提取"),
    ("3 运行时 UI 自动化", "FlaUI / pywinauto 读控件 Name/Text"),
    ("4 **OCR**", "最后手段 —— 本脚本，结果**必须人工确认**"),
]


def cmd_run(a):
    if not os.path.exists(a.image):
        print(f"❌ 图片不存在: {a.image}")
        return 2

    spec = require("tesseract")
    if spec is None:
        emit("tesseract", False, a.out,
             warnings=["OCR 不可用 —— 候选文案未采集，必须进 unknown"])
        return 2

    base = os.path.splitext(a.image)[0]
    cmd = ["tesseract", a.image, base]
    if a.lang:
        cmd += ["-l", a.lang]
    rc, out, err = run(cmd, timeout=300)
    if rc != 0:
        print(f"❌ tesseract 失败 rc={rc}: {(err or '')[:200]}")
        return 2

    txt_path = base + ".txt"
    lines = []
    if os.path.exists(txt_path):
        with open(txt_path, encoding="utf-8", errors="replace") as f:
            lines = [l.strip() for l in f if l.strip()]

    warn = [
        "**OCR 结果只作候选** —— 必须人工确认后才能进文案清单",
        "OCR 会漏：小字号、低对比度、复杂背景、旋转文本",
        "OCR 会错：形近字、字体替换、连字（fi/fl）",
    ]
    if not lines:
        warn.append("**0 条识别结果** —— 可能是图片无文字，也可能是 OCR 失败；"
                    "**不许直接认定「无文案」**")

    rec = emit("tesseract", True, a.out,
               evidence=[f"image={a.image}", f"lang={a.lang or '默认'}",
                         f"识别 {len(lines)} 行"],
               warnings=warn,
               confidence="low",
               extra={"lines": lines, "source": "ocr",
                      "needs_human_confirm": True})
    print_summary(rec)

    if a.out and a.out.endswith(".csv") and lines:
        with open(a.out, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["id", "text", "source", "confirmed"])
            for i, l in enumerate(lines, 1):
                w.writerow([f"OCR-{i:03d}", l, "ocr", ""])
        print(f"→ {a.out}（confirmed 列留空 = **待人工确认**）")

    # 与已知文案比对
    if a.compare and os.path.exists(a.compare):
        with open(a.compare, encoding="utf-8", errors="replace", newline="") as f:
            known = {r.get("text", "").strip()
                     for r in csv.DictReader(f) if r.get("text", "").strip()}
        matched = [l for l in lines if l in known]
        unmatched = [l for l in lines if l not in known]
        print(f"\n与已知文案比对: 匹配 {len(matched)} / 未匹配 {len(unmatched)}")
        for l in unmatched[:12]:
            print(f"   ❓ 未匹配: {l}")
        print("\n⚠️ 未匹配项要逐条确认 —— 可能是 OCR 错字，")
        print("   也可能是**原版有而我们漏登记的文案**。")

    print("\n证据优先级:")
    for k, why in PRIORITY:
        print(f"   {k:<20} {why}")
    return 0


def main():
    ap = argparse.ArgumentParser(description="OCR（拿不到源码时的候选证据）")
    ap.add_argument("--image")
    ap.add_argument("--lang", help="如 chi_sim+eng")
    ap.add_argument("--out", default="ledger/ocr_texts.csv")
    ap.add_argument("--compare")
    a = ap.parse_args()
    if not a.image:
        print("❌ 需要 --image")
        return 2
    return cmd_run(a)


if __name__ == "__main__":
    sys.exit(main())
