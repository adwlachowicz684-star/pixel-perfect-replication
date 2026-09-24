#!/usr/bin/env python3
"""运行时取证台账（A 类）—— 不改写原版即可取得可重放的行为证据。

**为什么这是最大盲区**：
> 我们有 Windows 的 Detours，但**跨平台动态插桩几乎是空的**。
> 原版跑起来后，怎么在**不改二进制**的前提下观察它？

**核心概念：原版行为基元**
最小工作单元不是"一个功能点"，而是：
`输入 / 触发条件 / 内部状态 / 可观察副作用 / 输出 / 时序 / 异常路径 / 对其他状态的副作用`

**⚠️ 最关键的一条纪律**：
> **Hook 数据 ≠ 语义事实。**
> **Frida 脚本不得直接修改游戏状态并声称观察到原版** ——
> 只读观察、参数快照、受控桩注入必须分开。

**工具分工（Detours 降为 Windows 旁路）**：
- **Frida** —— 默认主入口（跨平台黑盒附加、热改脚本、移动平台）
- **DynamoRIO / Pin** —— 需要细粒度指令/基本块/缓存/内存追踪时
- **Detours** —— 仅 Windows 需**持久化二进制桩**的任务
- **Qiling** —— 完整执行环境（含动态链接、系统调用、IO）
- **Unicorn** —— 只模拟 CPU，把已恢复状态放入单元测试验算法片段

用法:
  runtime_forensics.py --primitives               # 行为基元八要素
  runtime_forensics.py --init ledger/runtime_forensics.csv
  runtime_forensics.py --check ledger/runtime_forensics.csv --gate
  runtime_forensics.py --tools                    # 平台矩阵与分工

退出码: 0 通过 / 1 缺项或有未覆盖基元 / 2 用法错误
"""
import argparse
import csv
import os
import sys

PRIMITIVES = [
    "输入（参数值、缓冲区、设备状态）",
    "触发条件（什么前置状态才会执行）",
    "内部状态（执行前的关键变量）",
    "可观察副作用（文件/注册表/网络/内存）",
    "输出（返回值、写出的数据）",
    "时序（调用时刻、耗时、顺序）",
    "异常路径（错误码、异常、回退）",
    "**对其他状态的副作用**（最容易漏的一条）",
]

# 探针必填字段
FIELDS = [
    ("evidence_id", "证据编号"),
    ("original_build_id", "**原版构建身份**（缺此项无法复核）"),
    ("tool", "Frida / Qiling / Unicorn / DynamoRIO / dotnet-trace / bpftrace …"),
    ("target_module", "目标模块"),
    ("address", "地址（须含**模块基址**）"),
    ("symbol_origin", "符号来源（PDB / 导出表 / 签名 / 手工）"),
    ("hook_strategy", "Hook 策略（**只读观察 / 受控桩注入** —— 必须区分）"),
    ("call_index", "调用序号"),
    ("inputs_hash", "入参哈希"),
    ("outputs_hash", "出参哈希"),
    ("side_effects", "副作用"),
    ("clock_monotonic_ns", "**monotonic 时间戳**（不取墙钟）"),
    ("captured_bytes_path", "原始字节留存路径"),
    ("redacted", "是否已脱敏"),
    ("replay_command", "**可重放命令**"),
]

TOOLS = [
    ("Frida", "跨平台动态插桩主入口",
     "Win/macOS/Linux/Android/iOS/FreeBSD/QNX；注入脚本钩任意函数、监视私有代码",
     "⚠️ 移动端与 DRM/反调试场景可能采样失败 —— 以**失败计数**收口，"
     "不能因脚本运行成功而认定功能已覆盖"),
    ("Qiling", "**完整执行环境**（在 Unicorn 之上）",
     "提供可执行文件加载、动态链接、系统调用、IO、内存/寄存器/异常钩子；"
     "支持 PE/ELF/Mach-O、Win/Linux/macOS/Android/BSD",
     "适合答「给定环境和文件系统时这个原版子程序返回什么」"),
    ("Unicorn", "**只模拟 CPU**",
     "不理解动态库/系统调用/可执行格式",
     "适合把已恢复状态放入单元测试，验**单个算法片段**"),
    ("DynamoRIO", "运行时代码操纵（Win/Linux/Android）",
     "函数追踪、指令追踪、覆盖率、库追踪、内存地址/值追踪、缓存模拟",
     "Frida 不能稳定附加时的后手，**不是通用替代品**"),
    ("Intel Pin", "IA-32/x86-64 DBI 框架",
     "2026 年仍发布；按 Intel 官方分发条款使用",
     "⚠️ 工具本体与随附代码的许可证需**分别审查**"),
    ("dotnet-counters/trace/dump/gcdump/monitor/stack", ".NET 宿主运行时诊断",
     "实时计数器 / EventPipe 轨迹 / 核心转储 / GC 快照 / 线程栈",
     "⚠️ 对原版 **.NET Framework** 不能假设跨平台 .NET Core 工具全部适用；"
     "必要时改用性能计数器、ETW、CLR Profiler API"),
    ("bpftrace", "临时 eBPF 单行追踪（Linux）", "", "低开销结构化追踪用 LTTng"),
    ("LTTng / SystemTap / perf", "低开销结构化追踪 / 内核用户探测 / 采样与硬件事件",
     "", "Windows 原版应映射为 **ETW/WPR**，**不许宣称 eBPF 可直接观察**"),
]

# 推荐组合
PIPELINE = [
    "1 在原版或高保真兼容层用 Frida 取得**真实调用样本**",
    "2 用 Qiling 隔离复现关键函数",
    "3 把内存快照、寄存器、输入缓冲区、期望值固化为 `cases/*.json`",
    "4 在 Unicorn 中运行纯逻辑片段",
    "5 用属性测试**反证**新实现",
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

ENUMS = {'redacted': ('yes', 'no', 'partial', 'unknown'), 'symbol_origin': ('pdb', 'dwarf', 'exported', 'map_file', 'manual', 'unknown'), 'hook_strategy': ('patch', 'hook_write', 'detour', 'trampoline', 'unknown'), 'evidence': ('observed', 'measured', 'source', 'decompiled', 'secondhand', 'unverified', 'unknown')}
_CLAIM_OK = {'evidence': ('observed', 'measured', 'source')}
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

def cmd_primitives(a):
    print("=" * 72)
    print("原版行为基元（**最小工作单元不是功能点，是基元**）")
    print("=" * 72)
    for i, p in enumerate(PRIMITIVES, 1):
        print(f"   {i}. {p}")
    print("\n⚠️ 缺少运行时取证，所谓「逐文件复刻」会退化为")
    print("   **反编译器可读化之后的二次开发** —— 那就不是复刻了。")
    return 0


def cmd_tools(a):
    print("=" * 74)
    print("运行时取证工具分工（**Detours 降为 Windows 旁路**）")
    print("=" * 74)
    for name, what, detail, note in TOOLS:
        print(f"\n【{name}】{what}")
        if detail:
            print(f"   {detail}")
        if note:
            print(f"   {note}")
    print("\n" + "=" * 74)
    print("推荐组合：Qiling 取证 → Unicorn 冻结 → 属性测试反证")
    print("=" * 74)
    for s in PIPELINE:
        print(f"   {s}")
    print("\n⚠️ 模拟结果只能证明「**在该模型和桩下**」的行为，")
    print("   不能证明物理硬件上的像素或音频完全一致。")
    print("   风险：外部状态、浮点精度、线程竞争、系统时间、未建模系统调用。")
    return 0


def cmd_init(a):
    os.makedirs(os.path.dirname(a.init) or ".", exist_ok=True)
    with open(a.init, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow([k for k, _ in FIELDS])
        w.writerow(["TODO"] * len(FIELDS))
    print(f"已生成运行时取证台账: {a.init}")
    print("\n⚠️ 每个探针必须绑定**原版构建、进程位数、模块基址、符号来源**。")
    print("   地址不含基址 = 换个机器就对不上。")
    return 0


def cmd_check(a):
    if not os.path.exists(a.check):
        print(f"❌ 文件不存在: {a.check}")
        return 2
    with open(a.check, encoding="utf-8", errors="replace", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        print("❌ 空台账 —— **没有任何运行时证据**")
        return 1

    print("=" * 70)
    print(f"运行时取证 · {len(rows)} 条探针/样本")
    print("=" * 70)

    bad_rows, no_build, no_replay, mutating = [], [], [], []
    for i, r in enumerate(rows, 1):
        miss = [k for k, _ in FIELDS
                if not (r.get(k) or "").strip()
                or (r.get(k) or "").strip() in ("TODO", "待填", "—")]
        if miss:
            bad_rows.append((i, miss))
        v = (r.get("original_build_id") or "").strip()
        if not v or v == "TODO":
            no_build.append(i)
        v = (r.get("replay_command") or "").strip()
        if not v or v == "TODO":
            no_replay.append(i)
        strat = (r.get("hook_strategy") or "").lower()
        if any(w in strat for w in ("修改", "写入", "patch", "写内存", "hook_write")):
            mutating.append(i)

    if bad_rows:
        print(f"\n❌ {len(bad_rows)} 条字段不全:")
        for i, miss in bad_rows[:6]:
            print(f"   行{i}: 缺 {', '.join(miss[:5])}")
    if no_build:
        print(f"\n❌ {len(no_build)} 条缺**原版构建身份** —— 无法复核")
    if no_replay:
        print(f"\n❌ {len(no_replay)} 条缺**可重放命令** —— 证据不可复现")
    if mutating:
        print(f"\n🚨 {len(mutating)} 条 hook_strategy 疑似**修改状态**（行 {mutating[:8]}）")
        print("   ⚠️ **不得修改状态后声称观察到原版** —— 只读与受控桩必须分开")

    if not (bad_rows or no_build or no_replay or mutating):
        print("\n✅ 运行时取证完整")

    # 行为基元覆盖提醒
    print("\n⚠️ 请确认八项行为基元是否都被覆盖（--primitives）：")
    print("   其中最易漏的是「**对其他状态的副作用**」。")
    print("\n⚠️ 采样失败要以**失败计数 + 未覆盖基元清单**收口，")
    print("   **不能以「脚本运行成功」替代功能覆盖**。")
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

    return 1 if (a.gate and (bad_rows or no_build or no_replay or mutating or _ev or _ct)) else 0


def main():
    ap = argparse.ArgumentParser(description="运行时取证台账")
    ap.add_argument("--primitives", action="store_true")
    ap.add_argument("--tools", action="store_true")
    ap.add_argument("--init")
    ap.add_argument("--check")
    ap.add_argument("--gate", action="store_true")
    a = ap.parse_args()

    if a.primitives:
        return cmd_primitives(a)
    if a.tools:
        return cmd_tools(a)
    if a.init:
        return cmd_init(a)
    if a.check:
        return cmd_check(a)
    print("❌ 需要 --primitives / --tools / --init / --check 之一")
    return 2


if __name__ == "__main__":
    sys.exit(main())
