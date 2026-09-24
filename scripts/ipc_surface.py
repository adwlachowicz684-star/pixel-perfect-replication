#!/usr/bin/env python3
"""进程间通信与系统集成面（第十轮 B 类）。

**为什么需要**：我们覆盖了 Win32 消息与部分 Shell，但**不系统**。
原版可能在用命名管道、COM out-of-proc、共享内存、协议处理器、Toast……

**🔑 核心认知**：
> **IPC 的"功能通了"与"语义对等"之间至少隔**
> **三次重试、两个超时和一个权限上下文。**

每个消息要建模为：
`protocol_id, transport, encoding, framing, direction, caller_identity,
callee_security, request_fields, response_fields, timeout, retry, ordering,
side_effects, failure_mode`

用法:
  ipc_surface.py --list                        # IPC 机制与验证重点
  ipc_surface.py --init ledger/ipc_contract.csv
  ipc_surface.py --check ledger/ipc_contract.csv --gate
  ipc_surface.py --single-instance             # 单实例会话身份模型
  ipc_surface.py --shell                       # Shell 集成取证点

退出码: 0 通过 / 1 缺项或语义字段不全 / 2 用法错误
"""
import argparse
import csv
import os
import sys

MECHANISMS = [
    ("Named Pipe", "同机服务、legacy IPC",
     "**字节流 vs 消息模式**：消息模式把每次写入视为一个消息，"
     "部分读取返回 `ERROR_MORE_DATA`；字节模式不保留 write 边界",
     "Microsoft Named Pipe Modes；kotauskas/interprocess"),
    ("Mailslot", "单向广播、旧组件通知", "单向语义、消息尺寸、**丢失是否可接受**",
     "ProcMon IPC class"),
    ("WM_COPYDATA / Window messages", "进程内窗口通信、**单实例参数传递**",
     "消息 ID、wparam/lparam、ANSI/Unicode、目标窗口",
     "Spy++ / Accessibility Insights / ETW / ProcMon"),
    ("Shared Memory + Mutex/Event/Semaphore", "高频共享、同步",
     "消息协议、**ownership abandoned**、**崩溃残留脏数据**", "Win32 同步 API"),
    ("COM / RPC", "插件、Shell、Out-of-proc server",
     "套间、STA/MTA、激活、接口 IID、权限", "oleview / 反编译；COM 接口录制"),
    ("Shell", "URL protocol、文件关联、拖放、Toast、上下文菜单",
     "参数注入、动词、图标、per-user/machine、权限提升",
     "registry 取证、ProcMon、WinRT Toast API"),
]

FIELDS = [
    ("protocol_id", "协议编号"),
    ("transport", "传输（Named Pipe / Mailslot / WM_COPYDATA / 共享内存 / COM / Shell）"),
    ("message_framing", "**消息边界**（字节流 / 消息模式 / 长度前缀）"),
    ("encoding", "编码（ANSI/Unicode/UTF-8/二进制）"),
    ("direction", "方向"),
    ("caller_identity", "调用方身份"),
    ("callee_security", "被调用方安全上下文"),
    ("request_fields", "请求字段"),
    ("response_fields", "响应字段"),
    ("timeout", "超时"),
    ("retry", "重试策略"),
    ("ordering", "顺序保证"),
    ("side_effects", "副作用"),
    ("failure_mode", "**失败模式**（拆包/粘包/丢失/重入/UAC 拆分令牌）"),
]

# 单实例：**单位是会话身份，不是进程数**
SINGLE_INSTANCE = [
    "machine ID", "install ID", "user SID", "session ID", "window/profile ID",
]

SINGLE_ROLES = [
    "GUI 单实例", "CLI 并发", "后台服务",
    "安装器/卸载器", "渲染器/工具进程",
]

SINGLE_TRAPS = [
    "⚠️ 单实例**必须传递第二个实例的命令行/工作目录**，而不仅是阻止启动。",
    "⚠️ **不要用裸全局 mutex** —— 需考虑 `Global\\\\` 与 `Local\\\\` 命名空间、"
    "Session 0、快速用户切换、远程桌面、不同权限。",
    "⚠️ 持有者崩溃后 **abandoned mutex 不等于状态仍然有效**。",
    "⚠️ 旧实例退出后**文件锁残留**、abandoned mutex、命名管道实例耗尽、"
    "端口抢占都可能造成**假「已运行」**。",
    "⚠️ 若原版允许服务进程、CLI、GUI 三个角色并存，"
    "**不能套一个全局 mutex**。",
    "⚠️ Session 0 的服务进程**不能无脑给交互用户显示 Toast 或打开文件对话框**。",
]

SESSION_MATRIX = [
    "同用户双开", "不同用户", "同会话", "服务调用", "UAC",
    "**崩溃后重启**", "第二个实例带不同 cwd", "只读配置", "网络路径",
]

SHELL_POINTS = [
    ("URL protocol", "**完整 URI 逐字符传递** —— 引号、空格、`#`、本地文件 fragment、"
                     "Unicode、相对路径；⚠️ **命令行注入风险**意味着不能简单 `shell::open(uri)`"),
    ("文件关联", "区分 `Open` / `Open with` / `Print` / `Drop` / `ShareTarget`；"
                 "拖放格式（CF_HDROP、Shell IDList、FileGroupDescriptor）；"
                 "默认应用注册与用户选择"),
    ("上下文菜单", "进程外 COM / Explorer 宿主问题，**不是普通 Tauri command**"),
    ("Toast", "AUMID、tag/group、按钮、过期、设置中和失败回调；"
              "**Windows 10/11 表现可能不同**"),
]

FORENSICS = [
    ("Process Monitor 4.1", "**本轮最重要的 Windows 系统取证补件** —— "
                            "v4.1 新增**命名管道和邮槽的 IPC event class**"),
    ("ETW", "controller / provider / consumer；比 ProcMon 更底层、更接近 provider 定义的时间线。"
            "⚠️ 默认**不是抓取任意管道明文** —— 必须知道 provider GUID/name、keyword、event template"),
]

PROFILES = [
    "①启动/退出：文件、注册表、进程线程",
    "②**Named Pipe / Mailslot**",
    "③Shell execute / URL / file association",
    "④通知与托盘",
    "⑤崩溃",
]

REPLAY_STD = [
    "**请求—响应—副作用**三段，而不只是抓到字节",
    "故意启动第二个实例",
    "从 Explorer 拖文件",
    "调用 URL protocol",
    "从命令行打开 **UNC / 中文 / 空格**路径",
    "发送 Toast action",
    "录新实例收到的 argv、cwd、窗口激活、**去重/排队/拒绝策略**",
    "同一操作至少做**普通用户、管理员、Session 0/服务、远程桌面、受限用户**四组",
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

ENUMS = {'transport': ('named_pipe', 'uds', 'tcp', 'shm', 'grpc', 'websocket', 'other', 'unknown'), 'direction': ('request_response', 'oneway', 'duplex', 'pubsub', 'unknown'), 'ordering': ('ordered', 'unordered', 'per_channel', 'unknown'), 'side_effects': ('none', 'idempotent', 'non_idempotent', 'unknown')}
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

def cmd_list(a):
    print("=" * 78)
    print("IPC 机制与验证重点")
    print("=" * 78)
    for name, use, verify, tool in MECHANISMS:
        print(f"\n【{name}】{use}")
        print(f"   验证重点: {verify}")
        print(f"   工具: {tool}")
    print("\n🔑 **Windows IPC 清点不能停在「有没有 Named Pipe」** ——")
    print("   Named Pipe 既可以是字节流也可以是消息流。")
    print("   ⚠️ 消息模式改成字节流只追加长度前缀，**不能声称 IPC 对等**；反之亦然。")
    print("\n⚠️ 跨平台 Rust 传输应吸收 **kotauskas/interprocess**（Windows 用 Named Pipe、"
          "Unix 用 UDS）。")
    print("   🚫 **不要用 servo/ipc-channel 做通用服务** —— "
          "其文档明确服务器**一次只接受一个客户端**。")
    return 0


def cmd_single(a):
    print("=" * 76)
    print("单实例（**单位是会话身份，不是进程数**）")
    print("=" * 76)
    print("   身份维度: " + " · ".join(SINGLE_INSTANCE))
    print("\n   角色（**不能套一个全局 mutex**）:")
    for r in SINGLE_ROLES:
        print(f"      · {r}")
    print("\n坑:")
    for t in SINGLE_TRAPS:
        print(f"   {t}")
    print("\n会话测试矩阵:")
    for s in SESSION_MATRIX:
        print(f"   · {s}")
    return 0


def cmd_shell(a):
    print("=" * 74)
    print("Shell 集成取证点（**取证优先级应高于重新设计**）")
    print("=" * 74)
    for k, why in SHELL_POINTS:
        print(f"\n   【{k}】")
        print(f"      {why}")
    print("\n取证工具:")
    for k, why in FORENSICS:
        print(f"\n   【{k}】{why}")
    print("\n取证 profile（**不要在普通取证中无差别启用 boot logging**）:")
    for p in PROFILES:
        print(f"   {p}")
    print("\n录制判定标准:")
    for r in REPLAY_STD:
        print(f"   · {r}")
    return 0


def cmd_init(a):
    os.makedirs(os.path.dirname(a.init) or ".", exist_ok=True)
    with open(a.init, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow([k for k, _ in FIELDS])
        w.writerow(["TODO"] * len(FIELDS))
    print(f"已生成 IPC 契约表: {a.init}")
    print("\n⚠️ 先以 **ProcMon IPC** 发现端点，再以**目标 provider** 细化 ETW。")
    return 0


def cmd_check(a):
    if not os.path.exists(a.check):
        print(f"❌ 文件不存在: {a.check}")
        return 2
    with open(a.check, encoding="utf-8", errors="replace", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        print("❌ 空表 —— **未清点 IPC 面**")
        return 1

    def g(r, k):
        return (r.get(k) or "").strip()

    no_framing, no_failure, no_timeout, missing = [], [], [], []
    for i, r in enumerate(rows, 1):
        if not g(r, "message_framing") or g(r, "message_framing") == "TODO":
            no_framing.append(i)
        if not g(r, "failure_mode") or g(r, "failure_mode") == "TODO":
            no_failure.append(i)
        if not g(r, "timeout") or g(r, "timeout") == "TODO":
            no_timeout.append(i)
        miss = [k for k, _ in FIELDS
                if not g(r, k) or g(r, k) in ("TODO", "待填", "—")]
        if miss:
            missing.append((i, miss))

    print("=" * 74)
    print(f"IPC 契约 · {len(rows)} 条")
    print("=" * 74)
    if no_framing:
        print(f"\n❌ {len(no_framing)} 条缺**消息边界**（行 {no_framing[:15]}）")
        print("   → 字节流 vs 消息模式**必须明确**，否则语义不对等")
    if no_failure:
        print(f"\n❌ {len(no_failure)} 条缺**失败模式**（行 {no_failure[:15]}）")
        print("   → 拆包/粘包/消息丢失/COM 重入/UAC 拆分令牌 都要记")
    if no_timeout:
        print(f"\n⚠️ {len(no_timeout)} 条缺超时声明")
    if missing:
        print(f"\n⚠️ {len(missing)} 条字段不全")

    if not (no_framing or no_failure):
        print("\n✅ IPC 契约消息边界与失败模式齐全")

    print("\n🔑 **IPC 的「功能通了」与「语义对等」之间至少隔")
    print("   三次重试、两个超时和一个权限上下文。**")
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

    return 1 if (a.gate and (no_framing or no_failure or _ev or _ct)) else 0


def main():
    ap = argparse.ArgumentParser(description="IPC 与系统集成面")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--single-instance", dest="single_instance", action="store_true")
    ap.add_argument("--shell", action="store_true")
    ap.add_argument("--init")
    ap.add_argument("--check")
    ap.add_argument("--gate", action="store_true")
    a = ap.parse_args()
    if a.list:
        return cmd_list(a)
    if a.single_instance:
        return cmd_single(a)
    if a.shell:
        return cmd_shell(a)
    if a.init:
        return cmd_init(a)
    if a.check:
        return cmd_check(a)
    print("❌ 需要 --list / --single-instance / --shell / --init / --check 之一")
    return 2


if __name__ == "__main__":
    sys.exit(main())
