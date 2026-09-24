#!/usr/bin/env python3
"""HarfBuzz shaping 封装 —— L1 字形簇合同的金标准。

**为什么需要**：WPF 的 DirectWrite/Uniscribe 与浏览器 CSS 文本栈**不共享同一语义**。
只锁 hinting，仍可能在连字、字簇、双向重排上与原版不同。
**只在 Chromium 截图，无法判断差异来自排版、字体选择还是合成。**

产出 `glyphs.json`：glyph ID / cluster 映射 / advance / offset —— 可与原版逐项比对。

用法:
  harfbuzz_shape.py --font font.ttf --text "café" --out ledger/glyphs.json
  harfbuzz_shape.py --font font.ttf --text "مرحبا" --direction rtl
  harfbuzz_shape.py --font a.ttf --text "x" --compare b.json     # 与原版金标准比对
  harfbuzz_shape.py --features                                   # 常用 OpenType feature

退出码: 0 正常 / 1 比对有差异 / 2 用法错误或工具不可用
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import require, run, emit, print_summary  # noqa: E402

# 常用 OpenType feature（复刻时最容易丢的就是这些）
FEATURES = [
    ("liga", "标准连字", "fi/fl 等 —— 丢了会「看起来对但少了连字」"),
    ("dlig", " discretionary 连字", "装饰性连字"),
    ("kern", "字距调整", "**丢了字距会均匀但不对**"),
    ("calt", "上下文替代", "阿拉伯文等复杂脚本必需"),
    ("rlig", "必需连字", "某些脚本**不启用就显示错误**"),
    ("ss01-ss20", " stylistic set", "字体变体"),
    ("tnum", "等宽数字", "表格/对齐场景"),
    ("frac", "分数", "1/2 → ½"),
]


def cmd_features(a):
    print("常用 OpenType feature（复刻时最容易丢）:")
    for k, name, why in FEATURES:
        print(f"   {k:<12} {name}")
        print(f"                {why}")
    print("\n⚠️ `hb-subset` 默认会**丢弃部分 layout feature** ——")
    print("   子集化时必须用 `--layout-features` 显式保留，否则字形簇会变。")
    return 0


def shape(font, text, direction=None, language=None, features=None):
    cmd = ["hb-shape", font, f"--text={text}", "--output-format=json"]
    if direction:
        cmd.append(f"--direction={direction}")
    if language:
        cmd.append(f"--language={language}")
    if features:
        cmd.append(f"--features={features}")
    rc, out, err = run(cmd)
    return rc, out, err, " ".join(cmd)


def cmd_run(a):
    spec = require("harfbuzz")
    if spec is None:
        emit("harfbuzz", False, a.out,
             warnings=["hb-shape 不可用 —— 字形簇证据未采集"])
        return 2

    rc, out, err, cmdstr = shape(a.font, a.text, a.direction, a.language, a.features)
    if rc != 0:
        print(f"❌ hb-shape 失败 rc={rc}")
        print(f"   {err[:300]}")
        emit("harfbuzz", False, a.out,
             warnings=[f"hb-shape 执行失败: {err[:200]}"])
        return 2

    glyphs = []
    try:
        data = json.loads(out)
        for g in data:
            glyphs.append({
                "glyph_id": g.get("g"),
                "cluster": g.get("cl"),
                "x_advance": g.get("ax"),
                "y_advance": g.get("ay"),
                "x_offset": g.get("dx"),
                "y_offset": g.get("dy"),
            })
    except Exception:
        glyphs = []
        out_lines = out.strip()

    warn = []
    if not glyphs:
        warn.append("未解析到字形 —— 检查字体路径与文本内容")

    rec = emit("harfbuzz", True, a.out,
               evidence=[f"{len(glyphs)} 个字形簇",
                         f"command: {cmdstr}",
                         f"font={a.font} direction={a.direction or 'auto'}",
                         f"features={a.features or '(默认)'}"],
               warnings=warn,
               extra={"glyphs": glyphs, "raw": out[:4000],
                      "text": a.text, "font": os.path.basename(a.font),
                      "direction": a.direction, "features": a.features})
    print_summary(rec)

    # 与金标准比对
    if a.compare and os.path.exists(a.compare):
        with open(a.compare, encoding="utf-8") as f:
            base = json.load(f)
        bg = base.get("glyphs", [])
        diffs = []
        if len(bg) != len(glyphs):
            diffs.append(f"字形数量不同 金标准={len(bg)} 当前={len(glyphs)}")
        for i, (x, y) in enumerate(zip(bg, glyphs)):
            if x.get("glyph_id") != y.get("glyph_id"):
                diffs.append(f"#{i} glyph {x.get('glyph_id')} → {y.get('glyph_id')}")
            if x.get("x_advance") != y.get("x_advance"):
                diffs.append(f"#{i} advance {x.get('x_advance')} → {y.get('x_advance')}")
        print(f"\n与金标准比对: {len(diffs)} 处差异")
        for d in diffs[:15]:
            print(f"   ❌ {d}")
        if not diffs:
            print("   ✅ 字形簇一致（L1 合同通过）")
        print("\n⚠️ L1 字形簇合同通过 ≠ 视觉一致 ——")
        print("   L2 像素合同（fallback/hinting/subpixel/DPI）仍需单独验。")
        return 1 if diffs else 0

    return 0


def main():
    ap = argparse.ArgumentParser(description="HarfBuzz shaping（L1 字形簇合同）")
    ap.add_argument("--font", help="字体文件路径")
    ap.add_argument("--text", help="待 shaping 的文本")
    ap.add_argument("--direction", choices=["ltr", "rtl", "ttb"])
    ap.add_argument("--language")
    ap.add_argument("--features", help="如 liga,kern,calt")
    ap.add_argument("--out", default="ledger/glyphs.json")
    ap.add_argument("--compare", help="与金标准 JSON 比对")
    ap.add_argument("--features-list", dest="flist", action="store_true")
    a = ap.parse_args()

    if a.flist:
        return cmd_features(a)
    if not (a.font and a.text):
        print("❌ 需要 --font 与 --text（或 --features-list）")
        return 2
    return cmd_run(a)


if __name__ == "__main__":
    sys.exit(main())
