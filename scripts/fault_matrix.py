#!/usr/bin/env python3
"""故障行为矩阵（S6/S7）—— 异常路径必须与正常路径一样穷尽。

**为什么需要**：现有 `cross-end-check` 只覆盖 F1-F4（参数名/DTO/必传/注册），
**那只是参数层**。原版在异常下的行为——部分写、断网、磁盘满、权限拒绝、
重复启动、剪贴板不可用——**一条都没采集**，而这些恰恰是用户真会遇到的。

**核心原则**：
> **"没有崩溃"与"韧性等价"是两条不同的门禁。**
> 原版可能"也错了"，但新版至少应与原版**在同一前置条件下表现一致**，或明确改进并登记。

每类故障必须六栏齐全:
  precondition 前置条件   fault 故障注入方式
  observed_error 观察到的错误  recovery 恢复动作
  postcondition 事后状态   user_visible_message 用户可见消息

用法:
  fault_matrix.py --init ledger/faults.csv
  fault_matrix.py --check ledger/faults.csv --gate
  fault_matrix.py --catalog            # 打印必覆盖故障目录
  fault_matrix.py --network            # 网络故障三列表模板

退出码: 0 齐全 / 1 --gate 且有缺栏或未采集原版行为 / 2 用法或文件错误
"""
import argparse
import csv
import os
import sys

REQUIRED = ["precondition", "fault", "observed_error",
            "recovery", "postcondition", "user_visible_message"]

# 必覆盖故障目录（不止网络，文件系统与平台资源同样重要）
CATALOG = [
    ("文件", ["打开失败", "部分写入", "磁盘满", "权限拒绝",
              "路径消失", "并发替换", "文件被占用"]),
    ("网络", ["连接超时", "瞬间断网", "慢网络", "部分响应",
              "重复响应", "乱序响应", "TLS 失败"]),
    ("平台", ["重复启动", "剪贴板不可用", "COM/OLE 繁忙", "字体缺失",
              "注册表不可写", "DPI 变化", "多显示器切换"]),
    ("生命周期", ["卸载中途取消", "升级中途断电", "配置损坏",
                  "旧版本残留数据", "首次运行无权限"]),
]

# 网络故障三列表（故障 → 原版可观察行为 → 新版本要求）
NETWORK_TRIPLE = [
    ("连接超时", "重试/提示/状态保留", "同提示、同重试上限、**不重复提交**"),
    ("断网瞬间", "命令是否原子取消", "取消令牌在 N 毫秒内传播"),
    ("慢网络", "UI 是否冻结", "主窗口保持响应"),
    ("部分响应", "是否写脏缓存", "临时文件原子替换或回滚"),
    ("重复响应", "是否重复导入", "幂等键 / 去重"),
]

TOOLS = [
    ("Toxiproxy", "传输层：latency/down/bandwidth/slow_close/timeout/reset_peer/slicer/limit_data",
     "**不适合**模拟 NTFS ACL、磁盘配额、独占文件锁、WPF COM 调用"),
    ("libfiu", "POSIX 层：`LD_PRELOAD` 注入 errno，`fiu-run`/`fiu-ctrl` 可运行时启停",
     "适合 Linux/macOS；Windows 端用 Detours 或自有 IO shim 建等价层"),
    ("Chaos Mesh", "K8s 原生，故障类型最全",
     "**仅实验室** —— 单机 Windows 桌面属重型外部依赖，不应进主链"),
]



# ==========================================================================
# 🔑 第六十一轮新增：**枚举的两类语义必须分开**
#    ENUMS_KIND = 'constraint'  → **校验器输入约束**，🔴 不构成 must-match 主张
#    ENUMS_KIND = 'must_match'  → **原版行为事实**，🔴 必须由原版证据支撑
# 🔑 当前全部标为 'constraint' —— **因为没有原版证据**。
# 🔴 升为 'must_match' 必须同时补 `evidence`，**不能只改标签**。
# ==========================================================================
ENUMS_KIND = 'constraint'   # 🔴 不是 must-match；升级需附原版证据

ENUMS = {
    'status': ('待采', '已采', '已验证', '不适用', 'blocked', 'unknown'),
    'category': ('网络', '存档', '渲染', '输入', '音频', '物理', 'UI',
                 '脚本', '存档冲突', 'other', 'unknown'),
    'recovery': ('none', 'auto', 'manual', 'retry', 'partial', 'unknown'),
}
# 🔑 第六十一轮修正：本表**没有 evidence 列**，
#    若把 status='已验证' 纳入强主张校验，会让**所有**已验证行都矛盾
#    → **过度严格 = 误杀**。🔴 没有证据列就不做证据一致性断言。
_CLAIM_OK = {}
_WEAK_EVIDENCE = ('unknown', 'secondhand', 'unverified', '', 'todo')


def _enum_violations(rows, enums=None):
    """🔑 白名单校验：值不在合法枚举内 → 违例。"""
    enums = enums or ENUMS
    out = []
    for i, r in enumerate(rows, 1):
        for k, ok in enums.items():
            v = (r.get(k) or '').strip()
            if not v or v.lower() in ('todo', 'tbd', '待填', '—'):
                continue
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
    return out

def cmd_catalog(a):
    print("=" * 70)
    print("必覆盖故障目录（**不止网络**）")
    print("=" * 70)
    for cat, items in CATALOG:
        print(f"\n【{cat}】")
        print("   " + " · ".join(items))
    print("\n" + "=" * 70)
    print("网络故障三列表（故障 → 原版可观察行为 → 新版本要求）")
    print("=" * 70)
    for f, o, n in NETWORK_TRIPLE:
        print(f"\n   {f}")
        print(f"      原版: {o}")
        print(f"      新版: {n}")
    print("\n" + "=" * 70)
    print("工具分工（**互相不能替代**）")
    print("=" * 70)
    for t, good, bad in TOOLS:
        print(f"\n   {t}")
        print(f"      能: {good}")
        print(f"      不能: {bad}")
    print("\n⚠️ mitmproxy/WireMock 管内容层，**Toxiproxy 管传输层**，不许互相替代。")
    return 0


def cmd_init(a):
    os.makedirs(os.path.dirname(a.init) or ".", exist_ok=True)
    cols = ["id", "category", "name"] + REQUIRED + ["old_behavior", "new_behavior", "status"]
    with open(a.init, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(cols)
        w.writerow(["F-001", "网络", "连接超时",
                    "已发起请求", "Toxiproxy timeout", "超时错误",
                    "重试 3 次后提示", "未提交", "连接超时，请检查网络",
                    "TODO：从原版采集", "TODO", "待采"])
    print(f"已生成故障矩阵骨架: {a.init}")
    print("\n⚠️ `old_behavior` 留 TODO = **原版行为未采集**，--gate 会阻断。")
    print("   先采原版，再谈新版韧性 —— 不许凭空生成新版韧性。")
    return 0


def cmd_check(a):
    if not os.path.exists(a.check):
        print(f"❌ 文件不存在: {a.check}")
        return 2
    with open(a.check, encoding="utf-8", errors="replace", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        print("❌ 空表")
        return 2

    print("=" * 68)
    print(f"故障矩阵 · {len(rows)} 条")
    print("=" * 68)

    blockers, warns = [], []
    covered = set()

    for r in rows:
        name = (r.get("name") or r.get("id") or "?").strip()[:34]
        covered.add(name)
        # 1. 六栏齐全
        miss = [c for c in REQUIRED
                if not (r.get(c) or "").strip()
                or (r.get(c) or "").strip() in ("TODO", "待填", "—")]
        if miss:
            blockers.append((name, f"缺 {len(miss)} 栏: {', '.join(miss)}"))
        # 2. 原版行为必须已采集（这是最硬的）
        ob = (r.get("old_behavior") or "").strip()
        if not ob or ob in ("TODO", "待填", "未知"):
            blockers.append((name, "**原版行为未采集** —— 不许凭空生成新版韧性"))
        elif "TODO" in ob:
            blockers.append((name, "原版行为含 TODO"))
        # 3. 新版行为
        nb = (r.get("new_behavior") or "").strip()
        if not nb or nb in ("TODO", "待填"):
            warns.append((name, "新版行为未填"))

    # 目录覆盖度
    all_items = [i for _, items in CATALOG for i in items]
    missing_cat = [i for i in all_items
                   if not any(i in c for c in covered)]
    print(f"目录覆盖: {len(all_items) - len(missing_cat)}/{len(all_items)}")
    if missing_cat:
        print(f"   未覆盖: {', '.join(missing_cat[:12])}")
        warns.append(("目录", f"{len(missing_cat)} 类故障未定义"))

    if blockers:
        print(f"\n❌ 阻断 {len(blockers)} 项:")
        for n, w in blockers[:15]:
            print(f"   {n} — {w}")
    if warns:
        print(f"\n⚠️  提醒 {len(warns)} 项:")
        for n, w in warns[:12]:
            print(f"   {n} — {w}")
    if not blockers and not warns:
        print("\n✅ 故障矩阵完整")

    print("\n⚠️ **「没有崩溃」≠「韧性等价」** —— 这是两条不同的门禁。")
    print("   原版可能也错了，但新版应与原版在**同一前置条件下表现一致**，")
    print("   或明确改进并登记为有意变更。")
    print("\n   原版采集五步：静态(ILSpy 找 catch/finally/retry) → 动态(FlaUI 驱动失败 UI)")
    print("   → 故障(Detours/fiu/Toxiproxy) → 结果(消息/日志/状态/重试次数)")
    print("   → 判定(契约验证**行为等价**，而非只是不崩溃)")

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
    return 1 if (a.gate and (blockers or _ev or _ct)) else 0


def cmd_network(a):
    print("网络故障三列表模板（复制进 faults.csv）:\n")
    print("| 故障 | 原版可观察行为 | 新版本要求 |")
    print("|---|---|---|")
    for f, o, n in NETWORK_TRIPLE:
        print(f"| {f} | {o} | {n} |")
    return 0


def main():
    ap = argparse.ArgumentParser(description="故障行为矩阵")
    ap.add_argument("--check")
    ap.add_argument("--init")
    ap.add_argument("--gate", action="store_true")
    ap.add_argument("--catalog", action="store_true")
    ap.add_argument("--network", action="store_true")
    a = ap.parse_args()

    if a.catalog:
        return cmd_catalog(a)
    if a.network:
        return cmd_network(a)
    if a.init:
        return cmd_init(a)
    if a.check:
        return cmd_check(a)
    print("❌ 需要 --check / --init / --catalog / --network 之一")
    return 2


if __name__ == "__main__":
    sys.exit(main())
