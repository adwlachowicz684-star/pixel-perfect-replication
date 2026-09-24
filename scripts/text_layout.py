#!/usr/bin/env python3
"""文本排版金标准（S2T/S7）—— 文字"看起来一样"是不够的。

**为什么需要**：前几轮锁了 FreeType hinting，但那只解决光栅化一层。
WPF 的 DirectWrite/Uniscribe/ICU/Win32 locale 与浏览器 CSS 文本栈**不共享同一语义**。
只锁 hinting，仍可能在**连字、字簇、双向重排、换行点、排序键、日期格式**上与原版不同。

**核心方法**：把不可直接像素比较的语义，转成可比较的序列化金标准。

五张独立证据表:
  text_bytes     原始字节（含编码）
  nfc_normalized 归一化后字节（NFC/NFKC）
  canonical_bidi 逻辑序 + embedding level
  break_opportunities 断行机会（UAX #14）
  display_order  视觉序（UAX #9）

**⚠️ 关键分层**（两个独立合同，不许混）:
  L1 字形簇合同 —— glyph ID / cluster / advance（HarfBuzz `hb-shape`）
  L2 最终像素合同 —— 字体 fallback / hinting / subpixel / DPI（截图）
  **只在 Chromium 里截图，不能判断差异来自排版、字体选择还是合成。**

用法:
  text_layout.py --check                       # 检查依赖（缺则诚实降级）
  text_layout.py --old old.csv --new new.csv --out text.json --gate
  text_layout.py --dims                        # 打印五维与根因对照表

退出码: 0 一致 / 1 --gate 且有差异或未定项 / 2 用法错误
"""
import argparse
import csv
import json
import os
import sys
import unicodedata

# 五维证据（每维都要有金标准，不能只靠截图）
DIMS = [
    ("text_bytes", "原始字节与编码",
     "原字节哈希 + 探测编码 + 置信度 + 人工确认编码",
     "uchardet/chardet（**不作唯一解码源**，低置信度必须拒）"),
    ("nfc_normalized", "归一化",
     "NFC/NFKC 字节与序号比较结果",
     "ICU4X Normalizer；Python `unicodedata` 可作降级"),
    ("canonical_bidi", "双向文本",
     "逻辑序、视觉序、embedding level",
     "UAX #9；FriBiDi / SheenBidi / Raqm"),
    ("break_opportunities", "断行与分词",
     "断点集合、字素边界",
     "UAX #14 / UAX #29；ICU4X Segmenter"),
    ("collation_order", "排序与日期数字",
     "排序键、日期/数字格式字符串",
     "ICU4X Collator / DateTime / Number（**须固定 data 版本**）"),
]

# 根因 → 检测 → 金标准 → 可接受策略
ROOT_CAUSES = [
    ("字形替换/连字/字簇错误", "HarfBuzz `hb-shape` + 原版 DirectWrite/Uniscribe 捕获",
     "glyph/cluster/advance JSON", "先逐字符串复刻；失败时回退到视觉效果"),
    ("阿拉伯/希伯来 RTL 顺序错误", "FriBiDi / SheenBidi / Raqm / UAX #9 测试",
     "逻辑序、视觉序、embedding level", "**不以 `dir=\"rtl\"` 替代算法复刻**"),
    ("换行/分词/emoji 光标错误", "ICU4X Segmenter、UAX #14/#29 一致性测试",
     "断点集合、字素边界", "固定算法和数据版本，逐宽度复刻"),
    ("NFC/NFD、排序、日期数字差异", "ICU4X Normalizer / Collator / DateTime",
     "归一化字节、排序键、格式字符串", "按存储/展示职责分层"),
    ("编码误判、历史文件乱码", "uchardet/chardet、BOM/UTF-8 校验",
     "置信度、编码、语言、原字节", "默认拒绝低置信度，保留原字节样本"),
]

# 权威层分工（不许两边都算）
AUTHORITY = [
    ("数据库/业务排序、文件顺序、搜索索引", "**Rust 固定 locale 与 data 版本**"),
    ("展示格式", "前端按用户 locale 生成（Intl.*）"),
    ("最终渲染", "Chromium / HarfBuzz"),
]


def cmd_dims(a):
    print("=" * 72)
    print("五维文本证据（每维都要有金标准，不能只靠截图）")
    print("=" * 72)
    for k, name, gold, tool in DIMS:
        print(f"\n【{name}】 {k}")
        print(f"   金标准: {gold}")
        print(f"   工具:   {tool}")
    print("\n" + "=" * 72)
    print("根因 → 检测 → 金标准 → 可接受策略")
    print("=" * 72)
    for cause, detect, gold, strat in ROOT_CAUSES:
        print(f"\n{cause}")
        print(f"   检测:   {detect}")
        print(f"   金标准: {gold}")
        print(f"   策略:   {strat}")
    print("\n" + "=" * 72)
    print("权威层分工（**不许两边都算**）")
    print("=" * 72)
    for scope, owner in AUTHORITY:
        print(f"   {scope:<38} → {owner}")
    print("\n⚠️ L1 字形簇合同与 L2 像素合同是**两个独立合同**，不许混。")
    print("   只在 Chromium 截图，无法判断差异来自排版、字体选择还是合成。")
    return 0


def cmd_check(a):
    deps = {}
    for mod, name, need in [
        ("uharfbuzz", "uharfbuzz (HarfBuzz)", "L1 字形簇（glyph/cluster/advance）"),
        ("icu", "PyICU / ICU", "Bidi、断行、排序、日期"),
        ("chardet", "chardet", "编码探测（**低置信度必须拒**）"),
    ]:
        try:
            __import__(mod)
            deps[name] = True
        except ImportError:
            deps[name] = False
    builtin = True  # unicodedata 是标准库
    print("依赖检查:")
    for k, v in deps.items():
        print(f"   {'✅' if v else '❌'} {k}")
    print(f"   ✅ unicodedata（标准库）— 仅能覆盖 NFC/NFKC 归一化")

    missing = [k for k, v in deps.items() if not v]
    if missing:
        print(f"\n⚠️ 缺 {len(missing)} 项：**只能做归一化比较**")
        print("   Bidi / 断行 / 排序 / 字形簇 → **如实降级为 unknown，不猜测**")
        print("\n   安装: pip install uharfbuzz chardet     # ICU 建议用 icu4x / PyICU")
        print("\n   ⚠️ 不要因为拿不到 HarfBuzz 就用截图代替 ——")
        print("      截图能发现「不一样」，但**不能解释为什么不一样**。")
        return 2
    print("\n✅ 依赖齐全，可做五维比对")
    return 0


def load_csv(path):
    rows = []
    with open(path, encoding="utf-8", errors="replace") as f:
        for r in csv.DictReader(f):
            rows.append(r)
    return rows


def norm_forms(s):
    out = {}
    for form in ("NFC", "NFD", "NFKC", "NFKD"):
        try:
            out[form] = unicodedata.normalize(form, s)
        except Exception:
            out[form] = None
    return out


def cmd_compare(a):
    for p in (a.old, a.new):
        if not os.path.exists(p):
            print(f"❌ 文件不存在: {p}")
            return 2
    old_rows, new_rows = load_csv(a.old), load_csv(a.new)
    om = {r.get("id", str(i)): r for i, r in enumerate(old_rows)}
    nm = {r.get("id", str(i)): r for i, r in enumerate(new_rows)}

    diffs, unknown = [], []
    for k in sorted(set(om) | set(nm)):
        o, n = om.get(k), nm.get(k)
        if o is None:
            diffs.append((k, "新版新增", "原版无此条目 → 记入反向清单"))
            continue
        if n is None:
            diffs.append((k, "**原版有新版无**", "文案/文本丢失"))
            continue
        ot = o.get("text", "")
        nt = n.get("text", "")
        # 1. 直接相等
        if ot == nt:
            continue
        # 2. 归一化后相等 → 是编码/组合序列差异，不是内容差异
        onf, nnf = norm_forms(ot), norm_forms(nt)
        if onf["NFC"] == nnf["NFC"]:
            diffs.append((k, "NFC 相等但原字节不同",
                          "组合/分解序列差异 —— **会影响排序与匹配**，必须定权威归一化"))
            continue
        if onf["NFKC"] == nnf["NFKC"]:
            diffs.append((k, "NFKC 相等但 NFC 不同",
                          "兼容字符差异（如全角/半角）—— **显示可能相同但比较不同**"))
            continue
        # 3. 都不同，且没有更高层证据 → unknown
        have_bidi = bool(o.get("bidi") or n.get("bidi"))
        have_break = bool(o.get("break") or n.get("break"))
        have_glyph = bool(o.get("glyph") or n.get("glyph"))
        if not (have_bidi or have_break or have_glyph):
            unknown.append((k, "文本不同且无 Bidi/断行/字形证据 → **无法判因**"))
        else:
            diffs.append((k, "文本不同", "有部分高层证据，仍需逐维判定"))

    out = {"old": len(om), "new": len(nm), "diffs": diffs, "unknown": unknown,
           "authority": dict(AUTHORITY)}
    if a.out:
        os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)

    print("=" * 68)
    print(f"文本金标准比对 · 原版 {len(om)} / 新版 {len(nm)}")
    print("=" * 68)
    print(f"   差异 {len(diffs)} · 未定 {len(unknown)}")
    for k, why, note in diffs[:15]:
        print(f"\n   [{k}] {why}")
        print(f"        {note}")
    for k, why in unknown[:15]:
        print(f"\n   ❓ [{k}] {why}")

    print("\n⚠️ 未定项（无 Bidi/断行/字形证据）必须补齐证据，")
    print("   **不许用「看起来一样」结案**。")
    print("\n⚠️ 权威层：排序/索引由 Rust 固定版本，展示由前端按 locale，")
    print("   渲染由 Chromium/HarfBuzz —— **不许两边都算**。")

    return 1 if (a.gate and (diffs or unknown)) else 0


def main():
    ap = argparse.ArgumentParser(description="文本排版金标准")
    ap.add_argument("--old")
    ap.add_argument("--new")
    ap.add_argument("--out", default="ledger/text_layout.json")
    ap.add_argument("--gate", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--dims", action="store_true")
    a = ap.parse_args()

    if a.dims:
        return cmd_dims(a)
    if a.check:
        return cmd_check(a)
    if a.old and a.new:
        return cmd_compare(a)
    print("❌ 需要 --old/--new、--check 或 --dims")
    return 2


if __name__ == "__main__":
    sys.exit(main())
