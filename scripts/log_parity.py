#!/usr/bin/env python3
"""日志、遥测与可观测性对等（第十轮 C 类）—— **完全空白的一块**。

**🔑 核心认知**：
> **不能以"日志文本相似"为验收。**
> 最大的坑是「**字段名一致但含义漂移**」。

`user_id` 可能是本地 GUID、微软账户、邮箱或匿名哈希；
`session_id` 可能跨启动；
`duration_ms` 可能含睡眠；
`error` 可能为 null、空字符串、消息或类型；
`timestamp` 可能是本地时间、UTC、文件时间或单调时钟。

**日志断言至少分三层**（本脚本据此检查）。

用法:
  log_parity.py --init ledger/telemetry_contract.csv
  log_parity.py --check ledger/telemetry_contract.csv --gate
  log_parity.py --drift                        # 字段含义漂移
  log_parity.py --layers                       # 三层断言
  log_parity.py --crash                        # 崩溃上报五组字段

退出码: 0 通过 / 1 缺项或有未分类 PII/未知采样 / 2 用法错误
"""
import argparse
import csv
import os
import sys

# 字段含义漂移（**最容易骗过验收**）
DRIFT = [
    ("user_id", "本地 GUID / 微软账户 / 邮箱 / **匿名哈希**"),
    ("session_id", "**可能跨启动** —— 需明确边界"),
    ("duration_ms", "**可能含睡眠/挂起时间**"),
    ("error", "null / 空字符串 / 消息 / **类型**"),
    ("timestamp", "本地时间 / UTC / 文件时间 / **单调时钟**"),
    ("count", "累计 / 本次会话 / **去重后**"),
    ("version", "应用版本 / schema 版本 / **协议版本**"),
    ("level", "**级别映射不等于语义相同**（Warn vs Error 的边界）"),
]

LAYERS = [
    ("1 事件断言", "捕获多线程输出，断言某模板**出现 / 不出现 / 次数 / 字段**",
     "dbrgn/tracing-test（Rust 单测）"),
    ("2 span 生命周期", "断言 span 被**创建 / 进入 / 关闭**及次数 —— 例如迁移事务、"
                       "IPC 连接、文件写入是否**真正关闭**",
     "tobz/tracing-fluent-assertions（⚠️ 仅 dev-dependency，不进生产闭包）"),
    ("3 整行/结构化 diff", "旧版与复刻跑**同一 golden scenario**，日志规范化"
                        "（去时间戳/线程ID/路径/PID/相关性ID）后比对模板与属性",
     "⚠️ **不得将相似度阈值当成「通过」**"),
]

# 旧版 .NET 侧录制
DOTNET_RECORD = [
    ("serilog-contrib/SerilogSinksInMemory", "断言模板、级别、次数与属性",
     "⚠️ 上游归属需复核当前 NuGet package owner"),
    ("ReZoLin/serilog-exceptions", "解构旧版异常的自定义属性",
     "⚠️ **不得无边界递归**或记录整个 DbContext（会把数据库结构/数据带进日志）"),
]

# 崩溃上报五组字段
CRASH_GROUPS = [
    ("①应用标识", "名称、版本、build、commit、**schema 版本**"),
    ("②运行上下文", "OS、体系结构、语言、**DPI**、会话、权限、安装模式"),
    ("③崩溃现场", "线程、stack、loaded modules、**exception chain**、**breadcrumbs**"),
    ("④状态快照", "最近打开文件、**最后成功迁移阶段**、最后写入文件、最后 IPC message"),
    ("⑤环境健康", "磁盘、权限、WebView/渲染器进程、显卡驱动（**按需且脱敏**）"),
]

FIELDS = [
    ("event_domain", "事件域"),
    ("event_name", "事件名（⚠️ **动态值不得进事件名**，会破坏聚合）"),
    ("trigger", "触发条件"),
    ("level", "级别"),
    ("attributes", "属性名 / 类型 / **单位**"),
    ("pii_class", "**PII 分类**（须在进入遥测前分类、哈希或删除）"),
    ("sampling", "采样策略（⚠️ 重放/崩溃/迁移失败/**数据丢弃不得被采样掉**）"),
    ("correlation", "关联 ID"),
    ("retention", "保留期"),
    ("old_format", "旧版格式"),
    ("new_format", "新版格式"),
    ("evidence", "证据（**源是旧版录制，不是开发者的「合理推测」**）"),
]

AUDIT_FIELDS = ["actor", "process", "session", "operation", "target",
                "before_hash", "after_hash", "decision", "evidence_id",
                "result", "reason"]



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

ENUMS = {'level': ('debug', 'info', 'warn', 'error', 'fatal', 'trace', 'unknown'), 'pii_class': ('none', 'low', 'medium', 'high', 'pii', 'sensitive', 'unknown'), 'evidence': ('observed', 'measured', 'source', 'decompiled', 'secondhand', 'unverified', 'unknown')}
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

def cmd_drift(a):
    print("=" * 76)
    print("字段含义漂移（**最容易骗过验收**）")
    print("=" * 76)
    for k, why in DRIFT:
        print(f"\n   【{k}】")
        print(f"      {why}")
    print("\n🔑 对策：OTel 语义规范字段复用 + 项目 `custom_attributes.md`，")
    print("   每项标注**单位、基数、是否 PII、来源、缺失策略**。")
    print("\n⚠️ **遥测埋点要区分「事件语义对等」与「相同后端」** ——")
    print("   backend 可替换，事件契约不可替换。")
    return 0


def cmd_layers(a):
    print("=" * 78)
    print("日志断言三层")
    print("=" * 78)
    for k, what, tool in LAYERS:
        print(f"\n【{k}】")
        print(f"   {what}")
        print(f"   工具: {tool}")
    print("\n旧版 .NET 对等录制（**捕获结构化 LogEvent，不是渲染文本**）:")
    for k, what, note in DOTNET_RECORD:
        print(f"\n   【{k}】{what}")
        print(f"      {note}")
    print("\n⚠️ 这个组合的目标**不是把旧日志永久引入新项目**，")
    print("   而是用旧版可执行文件 + 注入式测试 logger 生成**可重放 event catalog**。")
    print("\n⚠️ Rust 侧用 tracing 作门面，输出 OTLP/JSON/file，")
    print("   但**不能让 OTLP 成为唯一 sink** —— 本地结构化 JSON、")
    print("   崩溃时最近 breadcrumb、启动修复信息必须**可离线读取**。")
    return 0


def cmd_crash(a):
    print("=" * 76)
    print("崩溃上报字段对等（**按「可复现性」验收，不是按字段数量**）")
    print("=" * 76)
    for k, why in CRASH_GROUPS:
        print(f"\n   【{k}】{why}")
    print("\nCrashpad/Breakpad 负责 minidump 采集，仍需验证：")
    for f in ["符号化", "去重键", "匿名用户 ID", "崩溃率指标", "**本地 breadcrumb 是否与原版同义**"]:
        print(f"   · {f}")
    print("\n审计日志（**append-only、可关联**）字段:")
    print("   " + " · ".join(AUDIT_FIELDS))
    print("\n⚠️ 审计**不可仅依赖 tracing filter**。")
    print("⚠️ 若原版没有审计，不能把像素级目标误解为「任何日志都补上」 ——")
    print("   应标记为**复刻新增的安全强化**，而非原版对等功能。")
    print("\n⚠️ **遥测失败本身必须可观测** ——")
    print("   collector 未启动 / 队列接近上限 / 导出连续失败 / 磁盘写入被拒")
    print("   → 升级为 warning/error 并进入下次启动的 recovery report。")
    print("   **不能把「没有异常」解释成「用户已上报」。**")
    return 0


def cmd_init(a):
    os.makedirs(os.path.dirname(a.init) or ".", exist_ok=True)
    with open(a.init, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow([k for k, _ in FIELDS])
        w.writerow(["TODO"] * len(FIELDS))
    print(f"已生成遥测契约表: {a.init}")
    print("\n⚠️ 契约的源是**旧版录制**，不是开发者的合理推测。")
    return 0


def cmd_check(a):
    if not os.path.exists(a.check):
        print(f"❌ 文件不存在: {a.check}")
        return 2
    with open(a.check, encoding="utf-8", errors="replace", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        print("❌ 空表 —— **未建立遥测契约**")
        return 1

    def g(r, k):
        return (r.get(k) or "").strip()

    no_pii, no_sampling, no_evidence, missing = [], [], [], []
    for i, r in enumerate(rows, 1):
        p = g(r, "pii_class")
        if not p or p in ("TODO", "待填", "—", "未知"):
            no_pii.append(i)
        s = g(r, "sampling")
        if not s or s in ("TODO", "待填", "—", "未知"):
            no_sampling.append(i)
        if not g(r, "evidence") or g(r, "evidence") == "TODO":
            no_evidence.append(i)
        miss = [k for k, _ in FIELDS
                if not g(r, k) or g(r, k) in ("TODO", "待填", "—")]
        if miss:
            missing.append((i, miss))

    print("=" * 74)
    print(f"遥测契约 · {len(rows)} 条")
    print("=" * 74)
    if no_pii:
        print(f"\n❌ {len(no_pii)} 条 PII 未分类（行 {no_pii[:15]}）")
        print("   → **PII 须在进入遥测前分类、哈希或删除**，不应依赖后端再脱敏")
    if no_sampling:
        print(f"\n❌ {len(no_sampling)} 条采样策略未声明（行 {no_sampling[:15]}）")
        print("   → **重放/崩溃/迁移失败/数据丢弃不得被采样掉**")
    if no_evidence:
        print(f"\n❌ {len(no_evidence)} 条缺旧版录制证据（行 {no_evidence[:15]}）")
        print("   → 契约必须来自**旧版录制**，不是推测")
    if missing:
        print(f"\n⚠️ {len(missing)} 条字段不全")

    if not (no_pii or no_sampling or no_evidence):
        print("\n✅ 遥测契约完整：PII 已分类、采样已声明、有旧版证据")

    print("\n🔑 **字段名一致但含义漂移**是最大坑 —— 见 `--drift`。")
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

    return 1 if (a.gate and (no_pii or no_sampling or no_evidence or _ev or _ct)) else 0


def main():
    ap = argparse.ArgumentParser(description="日志遥测对等")
    ap.add_argument("--drift", action="store_true")
    ap.add_argument("--layers", action="store_true")
    ap.add_argument("--crash", action="store_true")
    ap.add_argument("--init")
    ap.add_argument("--check")
    ap.add_argument("--gate", action="store_true")
    a = ap.parse_args()
    if a.drift:
        return cmd_drift(a)
    if a.layers:
        return cmd_layers(a)
    if a.crash:
        return cmd_crash(a)
    if a.init:
        return cmd_init(a)
    if a.check:
        return cmd_check(a)
    print("❌ 需要 --drift / --layers / --crash / --init / --check 之一")
    return 2


if __name__ == "__main__":
    sys.exit(main())
