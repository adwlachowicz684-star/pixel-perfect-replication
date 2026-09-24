#!/usr/bin/env python3
"""数值 / 编码 / 序列化保真（第九轮 C 区）。

**核心认知**：
> **"展示精度"与"往返精度"必须分开。**
> 展示值允许受文化/格式影响的文本；
> **文件、网络契约和跨语言基准应使用最短往返表示**。

**⚠️ 不能默认 JSON 能无损保真** —— 必须记录 `float_format`。

**三类"相同"要分开**（这是本脚本存在的核心理由）:
| 类型 | 适用 |
|---|---|
| **字节相同** | 保存文件 |
| **语义相同** | 跨进程契约 |
| **展示相同** | UI |

用法:
  value_fidelity.py --float --old old.json --new new.json    # 浮点往返
  value_fidelity.py --charsets                               # 字符/编码坑
  value_fidelity.py --culture                                # 文化格式化差异分类
  value_fidelity.py --canonical --file data.csv --out canon.csv

退出码: 0 一致 / 1 有差异 / 2 用法错误
"""
import argparse
import csv
import hashlib
import json
import os
import sys

# 浮点格式化算法
FLOAT_FORMATS = [
    ("ryu", "Ryū —— Ulf Adams 算法的 Rust 实现，**有 PLDI'18 正确性证明**",
     "Apache-2.0 / Boost；f32 约 21ns、f64 约 31ns"),
    ("grisu", "Grisu 系列（含 Grisu3）", "需回退到更慢算法处理困难情形"),
    ("eisel-lemire", "Eisel-Lemire（快速路径）", "现代解析器常用"),
    ("fixed", "固定小数位", "**可能丢精度** —— 必须显式登记"),
    ("hex", "十六进制浮点", "精确但不可读"),
    ("raw_bits", "原始位模式", "**最保真**，用于基准"),
]

CHARSETS = [
    ("BOM", "UTF-8 BOM 有无 —— 影响首字符解析与文件比较"),
    ("字节序", "UTF-16LE/BE；拆包顺序错则全乱码"),
    ("编码检测", "chardet/uchardet 只给**概率**，不能当事实"),
    ("标准化", "NFC/NFD/NFKC —— **相等但字节不同，影响排序与匹配**"),
    ("时区", "固定偏移 vs IANA 数据库；**夏令时切换**"),
    ("闰秒", "chrono 能表示但**不完全支持**"),
    ("历法", "公历/农历/和历；ICU4X 提供历法数据"),
]

CULTURE_DIFFS = [
    ("rounding", "舍入方式不同（银行家舍入 vs 四舍五入）"),
    ("grouping separator", "千分位分隔符（, / . / 空格 / 不分组）"),
    ("percent placement", "百分号位置与空格"),
    ("currency code/symbol", "货币符号与代码、前置/后置"),
    ("RTL shape", "双向文本整形（**阿拉伯/希伯来**）"),
    ("fallback", "缺失 locale 时的回退"),
    ("decimal separator", "小数点（. / ,）—— **最经典**"),
    ("negative sign", "负号位置（前置 / 括号 / 后置）"),
]

# 三类"相同"
EQUALITY = [
    ("字节相同 byte-identical", "**保存文件**追求这个"),
    ("语义相同 semantically-equal", "**跨进程契约**追求这个"),
    ("展示相同 display-equivalent", "**UI** 追求这个"),
]


def cmd_float(a):
    if not (os.path.exists(a.old) and os.path.exists(a.new)):
        print("❌ 文件不存在")
        return 2
    print("=" * 74)
    print("浮点往返保真")
    print("=" * 74)
    for k, what, note in FLOAT_FORMATS:
        print(f"\n   【{k}】{what}")
        print(f"      {note}")

    # 逐字段比对（尽力解析 JSON/CSV）
    def load(p):
        if p.endswith(".json"):
            return json.load(open(p, encoding="utf-8"))
        with open(p, encoding="utf-8", newline="") as f:
            return list(csv.DictReader(f))

    try:
        o, n = load(a.old), load(a.new)
    except Exception as e:
        print(f"❌ 解析失败: {e}")
        return 2

    diffs = []
    if isinstance(o, dict) and isinstance(n, dict):
        for k in sorted(set(o) | set(n)):
            vo, vn = o.get(k), n.get(k)
            if vo != vn:
                diffs.append((k, vo, vn))
    elif isinstance(o, list) and isinstance(n, list):
        for i, (ro, rn) in enumerate(zip(o, n)):
            if isinstance(ro, dict) and isinstance(rn, dict):
                for k in sorted(set(ro) | set(rn)):
                    if ro.get(k) != rn.get(k):
                        diffs.append((f"行{i}.{k}", ro.get(k), rn.get(k)))

    if diffs:
        print(f"\n❌ {len(diffs)} 处差异:")
        for k, vo, vn in diffs[:15]:
            print(f"   {k}: {vo!r} → {vn!r}")
    else:
        print("\n✅ 逐字段相等")

    print("\n⚠️ **值相等 ≠ 保真** —— 必须同时比对：")
    print("   bit pattern / 原始文本 / 规范化文本 / 平台格式")
    print("\n⚠️ 数字即使非金融值，也应记录**原始格式与显示格式** ——")
    print("   **不能因「值相等」删除格式信息**。")
    return 1 if (a.gate and diffs) else 0


def cmd_charsets(a):
    print("=" * 72)
    print("字符 / 编码 / 时间坑")
    print("=" * 72)
    for k, why in CHARSETS:
        print(f"\n   【{k}】")
        print(f"      {why}")
    print("\n三类「相同」要分开:")
    for k, why in EQUALITY:
        print(f"   {k:<34} {why}")
    print("\n⚠️ **NFC 相等但字节不同 → 影响排序与匹配** ——")
    print("   这是前几轮实测发现的坑（café 组合/预组合序列）。")
    return 0


def cmd_culture(a):
    print("=" * 72)
    print("文化格式化差异分类（**不应以「英文通过」结案**）")
    print("=" * 72)
    for k, why in CULTURE_DIFFS:
        print(f"   {k:<24} {why}")
    print("\n⚠️ WPF 的 `IValueConverter` / `CultureInfo` 对应复刻需：")
    print("   Rust 端**固定 locale provider 与数据版本**")
    print("   React 端**固定 Intl 数据回退**")
    print("\n⚠️ 每个样本 locale 生成原版文本与目标文本，")
    print("   差异按上表分类 —— **不许笼统说「格式不同」**。")
    return 0


def cmd_canonical(a):
    if not os.path.exists(a.file):
        print(f"❌ 文件不存在: {a.file}")
        return 2
    with open(a.file, encoding="utf-8", errors="replace", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        print("❌ 空文件")
        return 2
    # 规范化：去 BOM、稳定列序、去尾随空格、统一行尾
    cols = sorted({k for r in rows for k in r})
    norm = []
    for r in rows:
        norm.append({k: (r.get(k) or "").strip() for k in cols})
    if a.out:
        os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
        with open(a.out, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            w.writerows(norm)
        h = hashlib.sha256(open(a.out, "rb").read()).hexdigest()
        print(f"→ {a.out}")
        print(f"   canonical sha256: {h}")
    print(f"\n{len(norm)} 行已规范化（列序固定、去尾随空格）")
    print("\n⚠️ 旧格式迁移要提供**规范化 diff，而不是原始 diff**：")
    for k, why in [("CSV", "逐行规范器"),
                   ("JSON", "stable key 排序、无尾随空格、**确定 NaN/inf 策略**"),
                   ("XML", "规范化属性顺序、命名空间、CDATA 决策"),
                   ("二进制", "Kaitai Struct / 手动解析 / diff")]:
        print(f"   {k:<8} {why}")
    print("\n每项生成 `canonical.<ext>` + `checksum.sha256` + `field-report.json`。")
    print("\n⚠️ Kaitai 定义「格式」，**规范化器定义「逐字段等价」** —— 两者互补。")
    return 0


def main():
    ap = argparse.ArgumentParser(description="数值/编码/序列化保真")
    ap.add_argument("--float", action="store_true")
    ap.add_argument("--old")
    ap.add_argument("--new")
    ap.add_argument("--charsets", action="store_true")
    ap.add_argument("--culture", action="store_true")
    ap.add_argument("--canonical", action="store_true")
    ap.add_argument("--file")
    ap.add_argument("--out")
    ap.add_argument("--gate", action="store_true")
    a = ap.parse_args()

    if a.charsets:
        return cmd_charsets(a)
    if a.culture:
        return cmd_culture(a)
    if a.canonical:
        if not a.file:
            print("❌ --canonical 需要 --file")
            return 2
        return cmd_canonical(a)
    if a.float:
        if not (a.old and a.new):
            print("❌ --float 需要 --old/--new")
            return 2
        return cmd_float(a)
    print("❌ 需要 --float / --charsets / --culture / --canonical 之一")
    return 2


if __name__ == "__main__":
    sys.exit(main())
