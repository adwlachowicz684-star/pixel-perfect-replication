#!/usr/bin/env python3
"""resvg 封装 —— SVG 确定性位图渲染。

**为什么需要**：`asset_conversion_graph` 的一环 ——
`source → detected format → transform chain → hash → target`。
**不得把"看起来差不多"的压缩产物直接发布**。

**必须记录的参数**（否则"确定性"不成立）:
  resvg 版本 · DPI · 背景 · CSS 注入 · **文本 shaping 后端**

**许可**：MPL-2.0（**非 MIT**，需留意）。

用法:
  resvg_render.py --svg icon.svg --out baseline/icon.png --dpi 96
  resvg_render.py --graph ledger/asset_conversion_graph.csv   # 打印转换图格式
  resvg_render.py --check-env

退出码: 0 正常 / 2 工具不可用或用法错误
"""
import argparse
import csv
import hashlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import require, run, emit, print_summary  # noqa: E402

MUST_RECORD = [
    "resvg **版本**（不同版本渲染结果可能不同）",
    "**DPI**",
    "背景（是否透明）",
    "注入的 CSS",
    "**文本 shaping 后端**（影响字形簇）",
]


def cmd_graph(a):
    print("=" * 70)
    print("asset_conversion_graph 格式")
    print("=" * 70)
    print("   source → detected format → transform chain → hash → target")
    print("\n   示例 CSV 表头:")
    cols = ["source", "detected_format", "transform_chain",
            "output_hash", "target", "lossy", "baseline_kept", "ssim"]
    print("   " + " | ".join(cols))
    print("\n⚠️ **不得把「看起来差不多」的压缩产物直接发布** ——")
    print("   有损量化须：保留无损基准 + 失真预算 + SSIM/PSNR 记录。")
    print("\n工具分层:")
    for t, why in [
        ("resvg", "构建期**确定性**位图（本脚本）"),
        ("librsvg / rsvg-convert", "矢量 PDF 参考"),
        ("sharp (libvips)", "运行时多尺寸/压缩 —— **有操作顺序依赖**"),
        ("icotool / png2ico / png2icns", "ICO / ICNS"),
        ("oxipng / pngquant / svgo", "优化层"),
    ]:
        print(f"   {t:<26} {why}")
    print("\n⚠️ sharp 有操作顺序依赖，**不能替代构建期确定性基准**。")
    return 0


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(65536), b""):
            h.update(b)
    return h.hexdigest()


def cmd_run(a):
    if not os.path.exists(a.svg):
        print(f"❌ SVG 不存在: {a.svg}")
        return 2
    spec = require("resvg")
    if spec is None:
        emit("resvg", False, a.out_json or "ledger/resvg.json",
             warnings=["resvg 不可用 —— 确定性基准位图未生成"])
        return 2

    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    cmd = ["resvg", a.svg, a.out]
    if a.dpi:
        cmd += ["--dpi", str(a.dpi)]
    if a.background:
        cmd += ["--background", a.background]
    rc, out, err = run(cmd, timeout=300)
    if rc != 0:
        print(f"❌ resvg 失败 rc={rc}: {(err or '')[:200]}")
        return 2

    h = sha256(a.out) if os.path.exists(a.out) else None
    warn = []
    if not a.record_all:
        warn.append("**未记录全部参数**（版本/DPI/背景/CSS/shaping 后端）"
                    "—— 不记录则「确定性」不成立，换机器就对不上")

    rec = emit("resvg", True, a.out_json or "ledger/resvg.json",
               evidence=[f"svg={a.svg}", f"out={a.out}",
                         f"dpi={a.dpi}", f"background={a.background}",
                         f"sha256={h[:32] if h else '?'}…"],
               warnings=warn,
               extra={"output": a.out, "sha256": h, "dpi": a.dpi,
                      "background": a.background})
    print_summary(rec)
    print("\n必须记录的参数:")
    for m in MUST_RECORD:
        print(f"   {m}")
    return 0


def cmd_env(a):
    spec = require("resvg")
    if spec is None:
        return 2
    print_summary(emit("resvg", True, None, evidence=["resvg 可用"],
                       warnings=["MPL-2.0 —— **非 MIT**，需留意"]))
    return 0


def main():
    ap = argparse.ArgumentParser(description="resvg 确定性 SVG 渲染")
    ap.add_argument("--svg")
    ap.add_argument("--out", default="baseline/icon.png")
    ap.add_argument("--out-json", dest="out_json")
    ap.add_argument("--dpi", type=int)
    ap.add_argument("--background")
    ap.add_argument("--record-all", action="store_true",
                    help="声明已记录全部必需参数")
    ap.add_argument("--graph", action="store_true")
    ap.add_argument("--check-env", action="store_true")
    a = ap.parse_args()
    if a.graph:
        return cmd_graph(a)
    if a.check_env:
        return cmd_env(a)
    if not a.svg:
        print("❌ 需要 --svg，或 --graph / --check-env")
        return 2
    return cmd_run(a)


if __name__ == "__main__":
    sys.exit(main())
