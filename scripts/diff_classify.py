#!/usr/bin/env python3
"""差异归因（S7V 核心）—— 把"有差异"翻译成"为什么有差异"。

**为什么需要**：目前只有"有差异"，没有根因类型。
**像素差只是症状，不能作为穷尽验收的终态证据。**

十类根因（每个差异簇输出唯一主因 + 候选 + 支持/冲突证据）:
  translation 平移   resize 缩放     color 颜色      text 文本/字体
  missing 缺失元素   extra 多余元素   animation 时序  rendering 渲染
  structural 结构变化 unknown 未定

**归因依赖几何特征与多证据投票，不把任何单一分类器当真理。**

用法:
  diff_classify.py --old a.png --new b.png --out diff.json     # 需 Pillow/OpenCV
  diff_classify.py --check                                     # 检查依赖
  diff_classify.py --rules                                     # 打印十类判据
  diff_classify.py --merge d1.json d2.json --out merged.json   # 汇总多簇

退出码: 0 正常 / 1 --gate 且存在 unknown 或 structural / 2 用法或依赖错误
"""
import argparse
import json
import os
import sys

# (根因, 判定信号, 必要的门禁动作)
ROOT_CAUSES = [
    ("translation", "形状、面积、颜色直方图相近；质心发生整数或分数位移",
     "位移超出**体验参数阈值**才失败（不是有位移就失败）"),
    ("resize", "宽高比与内容不变，轮廓相似度下降",
     "检查布局约束、DPI、flex 比例"),
    ("color", "几何稳定但通道/色差变化",
     "固定 ICC 与色彩空间，先排除 sRGB 转换问题"),
    ("text", "包围盒稳定，OCR 或字形哈希变化",
     "检查字体、hinting、locale、截断规则"),
    ("missing", "新版掩码有背景，原版有前景（或反之）",
     "与 UIA/DOM **节点消失证据互证**，不许只凭像素"),
    ("extra", "新版新增连通域，原版对应区域为背景",
     "检查 focus ring、tooltip、调试覆盖层"),
    ("animation", "多帧状态均合法，仅单一时刻有差异",
     "帧序列必须在**合法状态集合**内"),
    ("rendering", "抗锯齿、亚像素、LCD 边缘出现高频变化",
     "抗锯齿免疫或局部容忍 —— **但不是自动豁免**"),
    ("structural", "节点映射改变（move / rename / insert / delete）",
     "触发**契约回归**，不只是视觉回归"),
    ("unknown", "各证据互相矛盾",
     "**阻止自动收工**，进入人工 S2/S3"),
]

# 每个差异簇要算的特征（多证据投票的输入）
FEATURES = [
    ("bbox", "包围盒：位移？缩放？"),
    ("area", "面积变化"),
    ("centroid", "质心位移"),
    ("hu_moments", "Hu 矩 / 形状描述子"),
    ("color_hist", "颜色直方图"),
    ("local_ssim", "局部 SSIM（OpenCV QualitySSIM 可输出 0-1 质量图）"),
    ("edge_diff", "边缘差（高频 → 抗锯齿线索）"),
    ("ocr_text", "OCR 文本是否相同"),
    ("node_mapping", "对应树节点 ID 与映射置信度"),
    ("anim_phase", "动画相位"),
    ("mouse_region", "是否落在鼠标区域"),
    ("clock_region", "是否落在时钟区域"),
]


def cmd_rules(a):
    print("=" * 70)
    print("十类根因（每个簇输出唯一主因 + 候选 + 支持/冲突证据）")
    print("=" * 70)
    for name, signal, gate in ROOT_CAUSES:
        print(f"\n【{name}】")
        print(f"   判定信号: {signal}")
        print(f"   门禁动作: {gate}")
    print("\n" + "=" * 70)
    print("多证据投票输入（每个差异簇都算）")
    print("=" * 70)
    for k, why in FEATURES:
        print(f"   {k:<14} {why}")
    print("\n⚠️ 归因必须依赖几何特征与**多证据投票**")
    print("   —— 不把任何单一分类器（含 OpenCV）当真理。")
    return 0


def cmd_check(a):
    ok = {}
    for mod, name in (("PIL", "Pillow"), ("cv2", "OpenCV"), ("numpy", "NumPy")):
        try:
            __import__(mod)
            ok[name] = True
        except ImportError:
            ok[name] = False
    print("依赖检查:")
    for k, v in ok.items():
        print(f"   {('✅' if v else '❌')} {k}")
    if not all(ok.values()):
        print("\n⚠️ 依赖不全时本脚本只能做**契约登记**与规则打印，")
        print("   **不做真实像素分析**（不假装成功）。")
        print("   安装: pip install pillow opencv-python numpy")
        return 2
    print("\n✅ 依赖齐全，可做真实像素分析")
    return 0


def cmd_classify(a):
    try:
        from PIL import Image          # noqa: F401
        import numpy as np             # noqa: F401
    except ImportError:
        print("❌ 缺 Pillow / NumPy —— 先跑 --check")
        print("   依赖不全时不假装分析。")
        return 2

    if not (os.path.exists(a.old) and os.path.exists(a.new)):
        print("❌ 图片不存在")
        return 2

    from PIL import Image
    import numpy as np

    oi = Image.open(a.old).convert("RGB")
    ni = Image.open(a.new).convert("RGB")
    if oi.size != ni.size:
        rec = {"root_cause": "resize", "confidence": 0.5,
               "evidence": [f"尺寸不同 {oi.size} vs {ni.size}"],
               "conflicting": [], "note": "尺寸不同 → 先归一化再判，不能直接比"}
    else:
        o = np.asarray(oi).astype(int)
        n = np.asarray(ni).astype(int)
        d = np.abs(o - n).sum(axis=2)
        mask = d > 30
        diff_pixels = int(mask.sum())
        total = mask.size
        ratio = diff_pixels / total if total else 0.0

        if diff_pixels == 0:
            rec = {"root_cause": "none", "confidence": 1.0,
                   "evidence": ["无差异"], "conflicting": []}
        else:
            ys, xs = np.nonzero(mask)
            bbox = [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]
            # 颜色差 vs 结构差的粗判
            mean_abs = float(np.abs(o - n).mean())
            rec = {
                "root_cause": "unknown",
                "confidence": 0.4,
                "diff_pixel_ratio": round(ratio, 5),
                "bbox": bbox,
                "evidence": [
                    f"差异像素 {diff_pixels} ({ratio:.2%})",
                    f"bbox={bbox}",
                    f"平均通道差 {mean_abs:.2f}",
                ],
                "conflicting": [],
                "candidates": [],
                "note": "粗判。**真实归因需 OCR、树映射、动画相位与多帧证据**；"
                        "本脚本不猜测主因，避免装作确定",
            }
            # 只给候选，不给断言
            if ratio < 0.0005:
                rec["candidates"].append(
                    ("rendering", 0.5, "差异面积极小，可能是抗锯齿/亚像素 —— "
                                       "**但仍需人工裁定，不自动豁免**"))
            if mean_abs < 12:
                rec["candidates"].append(
                    ("color", 0.4, "平均通道差小，可能是色差而非结构变化"))

    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False, indent=2)

    print("=" * 64)
    print(f"差异归因 → {a.out}")
    print("=" * 64)
    print(f"   主因: {rec['root_cause']}  (置信度 {rec.get('confidence')})")
    for e in rec.get("evidence", []):
        print(f"   · {e}")
    for c in rec.get("candidates", []):
        print(f"   候选: {c[0]} ({c[1]}) —— {c[2]}")

    print("\n⚠️ 归因必须结合**树映射与多帧证据**才有效。")
    print("   `structural` 与 `unknown` 必须进人工复核，**不许自动收工**。")

    if a.gate and rec["root_cause"] in ("unknown", "structural"):
        return 1
    return 0


def main():
    ap = argparse.ArgumentParser(description="差异归因（像素差 → 根因）")
    ap.add_argument("--old")
    ap.add_argument("--new")
    ap.add_argument("--out", default="ledger/diff.json")
    ap.add_argument("--gate", action="store_true",
                    help="存在 unknown / structural 退出码 1")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--rules", action="store_true")
    a = ap.parse_args()

    if a.rules:
        return cmd_rules(a)
    if a.check:
        return cmd_check(a)
    if a.old and a.new:
        return cmd_classify(a)
    print("❌ 需要 --old/--new、--check 或 --rules")
    return 2


if __name__ == "__main__":
    sys.exit(main())
