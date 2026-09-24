#!/usr/bin/env python3
"""二进制函数覆盖与等价候选（B 类）—— 原版函数集合是否被穷尽覆盖。

**为什么需要**：
> 没有二进制 diff，就无法回答"**原版究竟有多少个行为单元**、
> 哪些已被覆盖、哪些只是名字相似"。

**⚠️ 最重要的纪律**：
> **禁止把自动映射直接写入规范。**
> 必须保留 `match_type / confidence / similarity / algorithm / manual_review`。

**二进制 diff 的首要价值是发现未覆盖函数，不是美化迁移后的代码。**

`unmatched_primary` = 原版有、新版无 ← **最危险，即漏做**
`unmatched_secondary` = 新版多出 ← 增强或多余，需说明
`low_confidence` = 必须进人工队列

用法:
  binary_coverage.py --init ledger/binary_coverage.csv
  binary_coverage.py --check ledger/binary_coverage.csv --gate
  binary_coverage.py --tools                    # 工具分工与许可约束

退出码: 0 通过 / 1 有未覆盖函数、低置信未复核或缺项 / 2 用法错误
"""
import argparse
import csv
import os
import sys

TOOLS = [
    ("google/bindiff", "函数级二进制 diff", "Apache-2.0",
     "⚠️ 要求 **IDA 9.0+** —— **不能宣传成无商业依赖**；作为 Ghidra/radare2 之上的交叉验证器"),
    ("joxeankoret/diaphora", "汇编/CFG/符号/注释迁移、手动匹配、调用图、伪代码启发",
     "**AGPL-3.0**", "⚠️ 要求 **IDA 7.4+**（支持 6.8–9.4）；AGPL 仅 `third_party` 时提示"),
    ("clearbluejar/ghidriff", "**基于 Ghidra** 的二进制 diff，命令行/批量/CI 化",
     "—", "✅ **降低 IDA 依赖的关键候选**；但以 Ghidra 分析质量为前提"),
    ("avast/retdec", "基于 LLVM 的可重定向反编译器", "MIT（含 zlib/libpng 第三方）",
     "用于**第二套伪代码交叉验证**，不取代 Ghidra/IDA"),
    ("angr/angr", "加载/IR 提升/插桩/符号执行/控制流/数据依赖/值集分析", "BSD-2-Clause", ""),
    ("JonathanSalwan/Triton", "动态符号执行、污点分析、AST、ISA 语义、SMT", "Apache-2.0",
     "⚠️ 同名也可能是商业 AI 平台 —— 只吸收此仓库"),
    ("klee/klee", "LLVM 上的符号虚拟机", "—", ""),
    ("trailofbits/manticore / BinaryAnalysisPlatform/bap", "污点与程序分析", "—", ""),
]

FIELDS = [
    ("match_type", "匹配类型（exact / similar / renamed / manual / none）"),
    ("confidence", "置信度（**low 必须人工复核**）"),
    ("similarity", "相似度数值"),
    ("algorithm", "所用算法"),
    ("primary_address", "原版地址"),
    ("secondary_address", "新版地址"),
    ("name_match", "名称是否匹配"),
    ("signature_match", "签名是否匹配"),
    ("cfg_edit_distance", "CFG 编辑距离"),
    ("callgraph_support", "调用图是否支持"),
    ("manual_review", "**是否已人工复核**"),
    ("disposition", "处置（preserve / replace / merge / remove / defer）"),
]



# ==========================================================================
# 🔑 第五十九轮新增：**白名单枚举** + **跨字段一致性**
#
# 🔴 混沌测试（第五十六～五十八轮）连续三轮发现：本脚本属于 A 类盲区——
#    `--check` 只做**结构性缺失**检查（空值/TODO），
#    🔴 **填任意非法值都静默通过**（黑名单式校验的通病）。
# 🔑 修复：关键字段改为**白名单枚举**；并检测"字段合法但整行自相矛盾"。
# ==========================================================================

# ==========================================================================
# 🔑 第六十一轮新增：**枚举的两类语义必须分开**
#
# 🔴 第六十轮留下的未闭合缺口：这些 `ENUMS` 合法值是**按字段语义推断**的，
#    不是从原版证据提取的。
# 🔑 本轮不是去"补全证据"（那需要原版取证），而是**把语义显式标出来**：
#
#    ENUMS_KIND = 'constraint'  → **校验器输入约束**
#        只用于"防止填错值"，🔴 **不构成 must-match 主张**。
#        例：level 只能是 debug/info/warn——这是我们给表定的填写规范。
#
#    ENUMS_KIND = 'must_match'  → **原版行为事实**
#        枚举本身是 must-match 对象，🔴 **必须由原版证据支撑**，
#        例：某作"处置"字段只有这三种，是原版真实存在的分类。
#
# 🔑 当前全部标为 'constraint' —— **因为我们没有原版证据**。
# 🔴 若某天要把它升为 'must_match'，必须同时补 `evidence` 字段，
#    **不能只改标签**。
# ==========================================================================
ENUMS_KIND = 'constraint'   # 🔴 不是 must-match；升级需附原版证据

ENUMS = {'match_type': ('exact', 'renamed', 'moved', 'similar', 'new_only', 'added', 'secondary_only', 'none', 'unknown'), 'confidence': ('high', 'medium', 'low', 'unknown'), 'manual_review': ('yes', 'no', 'y', 'n', 'true', 'false', '是', '否', '已复核', '未复核'), 'disposition': ('match', 'deviation', 'unknown', 'preserve', 'blocked')}
_CLAIM_OK = {'match_type': ('exact',)}
_WEAK_EVIDENCE = ('unknown', 'secondhand', 'unverified', '', 'todo')


def _enum_violations(rows, enums=None):
    """🔑 白名单校验：值不在合法枚举内 → 违例。"""
    enums = enums or ENUMS
    out = []
    for i, r in enumerate(rows, 1):
        for k, ok in enums.items():
            v = (r.get(k) or '').strip()
            if not v or v.lower() in ('todo', 'tbd', '待填', '—'):
                continue          # 🔑 结构性缺失由原有逻辑负责
            if v.lower() not in ok:
                out.append((i, k, v))
    return out


def _contradictions(rows, enums=None):
    """🔑 跨字段一致性：**每个字段都合法，但整行在说谎**。"""
    enums = enums or ENUMS
    out = []
    for i, r in enumerate(rows, 1):
        ev = (r.get('evidence') or '').strip().lower()
        # 🔑 第六十四轮：**没有 evidence 列就不做证据一致性断言**
        #    🔴 与第六十一轮 fault_matrix 是同一个病——
        #       断言一个表里根本不存在的字段 → 每行都被判矛盾 → 误杀
        if not any((r.get(k) or '').strip()
                   for k in ('evidence', 'evidence_level')):
            continue
        for k, claims in _CLAIM_OK.items():
            v = (r.get(k) or '').strip().lower()
            if v in claims and ev in _WEAK_EVIDENCE:
                out.append((i, '`' + k + '`=`' + v + '` 但 evidence=`'
                            + (ev or '(空)') + '`（证据不支持强主张）'))
        conf = (r.get('confidence') or '').strip().lower()
        mt = (r.get('match_type') or '').strip().lower()
        if mt == 'exact' and conf == 'low':
            out.append((i, 'match_type=exact 但 confidence=low（低置信不能声称精确）'))
    return out

def cmd_tools(a):
    print("=" * 76)
    print("二进制 diff 工具（**都有附加约束，不许宣传成零成本**）")
    print("=" * 76)
    for repo, what, lic, note in TOOLS:
        print(f"\n【{repo}】 ({lic})")
        print(f"   {what}")
        if note:
            print(f"   {note}")
    print("\n" + "=" * 76)
    print("三条硬纪律")
    print("=" * 76)
    print("   1. **禁止把自动映射直接写入规范** —— 必须保留置信度与人工复核状态")
    print("   2. 三个工具结论冲突时，不得**自动择多**，要补插桩样本/类型恢复/调试信息")
    print("   3. 二进制匹配答「函数是否仍是同一份逻辑」，**不答「渲染结果是否一致」**")
    print("\n⚠️ 变量名、注释、控制流相似都可能是编译器/混淆/内联/重构的产物。")
    print("   只有与真实输入输出、错误路径、性能轨迹、视觉输出结合，才接近像素级覆盖。")
    print("   → 二进制 diff **产出待验假设**，不能成为「已完成迁移」的证据。")
    print("\n⚠️ 符号执行只能证明**有限语义**，不许宣称证明任意输入上全同。")
    print("   「等价」必须写成**可证伪命题**（约束输入长度、范围、稳定性、字节序、舍入…）")
    print("   求解超时与未建模外部调用须进 `assumptions` / `limitations`。")
    return 0


def cmd_init(a):
    os.makedirs(os.path.dirname(a.init) or ".", exist_ok=True)
    with open(a.init, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow([k for k, _ in FIELDS])
        w.writerow(["TODO"] * len(FIELDS))
    print(f"已生成二进制覆盖表: {a.init}")
    return 0


def cmd_check(a):
    if not os.path.exists(a.check):
        print(f"❌ 文件不存在: {a.check}")
        return 2
    with open(a.check, encoding="utf-8", errors="replace", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        print("❌ 空表 —— 未做二进制比对，无法证明覆盖")
        return 1

    def v(r, k):
        return (r.get(k) or "").strip()

    unmatched_primary, unmatched_secondary = [], []
    low_conf_unreviewed, missing_fields = [], []

    for i, r in enumerate(rows, 1):
        mt = v(r, "match_type").lower()
        if mt in ("none", "", "todo", "待填", "—"):
            unmatched_primary.append(i)
        if mt in ("new_only", "added", "secondary_only"):
            unmatched_secondary.append(i)
        conf = v(r, "confidence").lower()
        reviewed = v(r, "manual_review").lower()
        if conf in ("low", "medium") and reviewed not in ("yes", "y", "true", "是", "已复核"):
            low_conf_unreviewed.append((i, conf))
        miss = [k for k, _ in FIELDS
                if not v(r, k) or v(r, k) in ("TODO", "待填", "—")]
        if miss:
            missing_fields.append((i, miss))

    print("=" * 72)
    print(f"二进制覆盖 · {len(rows)} 条")
    print("=" * 72)

    if unmatched_primary:
        print(f"\n🔴 **原版有、新版无** {len(unmatched_primary)} 条（行 {unmatched_primary[:15]}）")
        print("   → **即漏做**。这是二进制 diff 首要价值所在。")
    if unmatched_secondary:
        print(f"\n🔵 新版多出 {len(unmatched_secondary)} 条（行 {unmatched_secondary[:15]}）")
        print("   → 需说明是增强还是多余，**不许默认无害**")
    if low_conf_unreviewed:
        print(f"\n⚠️ 低/中置信未人工复核 {len(low_conf_unreviewed)} 条:")
        for i, c in low_conf_unreviewed[:8]:
            print(f"   行{i} confidence={c}")
        print("   → 必须进人工队列，**不得自动采信**")
    if missing_fields:
        print(f"\n❌ {len(missing_fields)} 条字段不全")
        for i, miss in missing_fields[:5]:
            print(f"   行{i}: 缺 {', '.join(miss[:5])}")

    if not (unmatched_primary or low_conf_unreviewed or missing_fields):
        print("\n✅ 无未覆盖函数、无未复核低置信")

    print("\n⚠️ 视觉/脚本/插桩发现的外部可见行为，也应与**原版函数表交叉引用** ——")
    print("   「未覆盖」应由**至少两条证据链**共同提出。")
    # 🔑 第五十九轮：白名单违例 + 语义矛盾 也须阻断
    _ev = _enum_violations(rows)
    if _ev:
        print('\n🚫 **字段白名单违例**（🔴 黑名单只查空值，查不出**填错的值**）:')
        for i, k, v in _ev[:12]:
            print(f'   行 {i}: `{k}` = `{v}` 不在合法枚举内')
        print('   🔑 合法值见本文件顶部 ENUMS')
    _ct = _contradictions(rows)
    if _ct:
        print('\n🚫 **跨字段语义矛盾**（🔑 字段合法 ≠ 行自洽）:')
        for i, w in _ct[:12]:
            print(f'   行 {i}: {w}')

    return 1 if (a.gate and (unmatched_primary or low_conf_unreviewed
                             or missing_fields or _ev or _ct)) else 0


def main():
    ap = argparse.ArgumentParser(description="二进制函数覆盖")
    ap.add_argument("--tools", action="store_true")
    ap.add_argument("--init")
    ap.add_argument("--check")
    ap.add_argument("--gate", action="store_true")
    a = ap.parse_args()
    if a.tools:
        return cmd_tools(a)
    if a.init:
        return cmd_init(a)
    if a.check:
        return cmd_check(a)
    print("❌ 需要 --tools / --init / --check 之一")
    return 2


if __name__ == "__main__":
    sys.exit(main())
