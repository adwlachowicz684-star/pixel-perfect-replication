#!/usr/bin/env python3
"""离线与网络不确定环境（第十一轮 B 类）—— **完全空白的一块**。

**🔑 核心认知**：
> **原版"能离线用"是可用状态机，不是一句错误提示。**
> 结论不能写"断网提示用户"，而应写「原版在第几次失败、累计多少毫秒后
> 显示什么文案，目标必须同事件序复刻」。

**四层网络检测**（`online === navigator.onLine` 只说明部分事实）:
`link` → `dns` → `ip_routing` → `http_probe` / `tls_handshake` →
`proxy_auth` → `application_health` / `captive_portal`

用法:
  network_resilience.py --layers              # 四层检测
  network_resilience.py --faults              # 25 个具名故障场景
  network_resilience.py --proxy               # 企业网络（**不是一个布尔值**）
  network_resilience.py --retry               # 重试与幂等
  network_resilience.py --init ledger/network_matrix.csv
  network_resilience.py --check ledger/network_matrix.csv --gate

退出码: 0 通过 / 1 缺项 / 2 用法错误
"""
import argparse
import csv
import os
import sys

LAYERS = [
    ("1 link", "链路", "网卡/物理连接 —— 只能说明部分事实"),
    ("2 dns", "名称解析", "解析失败 ≠ 不可达（可能是瞬时）"),
    ("3 ip_routing", "路由可达", "能路由 ≠ 能握手"),
    ("4 http_probe", "应用探测", "握手 ≠ 业务成功"),
    ("5 tls_handshake", "TLS 握手", "证书错误要单独建模"),
    ("6 proxy_auth", "代理认证", "407 / NTLM / Negotiate"),
    ("7 application_health", "**业务健康**", "**真正决定原版行为的层**"),
    ("8 captive_portal", "强制门户", "重定向 ≠ 正常响应"),
]

DEGRADE_SCENARIOS = [
    "启动无网", "首次登录无网", "编辑中掉线", "附件上传中掉线", "下载中掉线",
    "证书错误", "企业代理", "PAC/WPAD", "NTLM/Kerberos", "TLS 拦截",
    "慢速响应", "HTTP 重定向", "DNS 失败", "断点续传", "幂等重试", "后台唤醒重试",
]

# 25 个具名故障场景
FAULTS = [
    "dns_nxdomain", "dns_timeout", "dns_slow",
    "tls_cert_untrusted", "tls_ca_intercepted", "tls_expired", "tls_wrong_host",
    "proxy_refused", "proxy_auth_407_ntlm", "proxy_loop",
    "http_502", "http_504", "redirect_loop",
    "slow_start", "slow_body", "stall_after_headers",
    "bandwidth_50kbps", "latency_2000ms_jitter", "packet_loss_10pct",
    "connection_reset", "read_timeout", "write_timeout",
    "server_slow_close", "captive_portal_redirect", "ipv6_blackhole",
]

PROXY_ITEMS = [
    "系统代理", "PAC", "WPAD", "自动检测", "手工代理", "SOCKS",
    "HTTP CONNECT", "NTLMv2", "Negotiate/Kerberos", "代理凭据提示",
    "CA 拦截", "客户端证书", "代理旁路", "白名单行为",
]

RETRY_FIELDS = [
    ("method", "方法"),
    ("uri_template", "URI 模板"),
    ("idempotency_key", "**幂等键**"),
    ("retryable_error_codes", "可重试错误码"),
    ("max_attempts", "最大尝试次数"),
    ("base_delay_ms / max_delay_ms", "退避区间"),
    ("jitter_ratio", "抖动比例"),
    ("circuit_breaker", "熔断"),
    ("timeout_connect/read/whole", "**三类超时**"),
    ("request_hash", "请求哈希"),
    ("response_etag/digest", "响应摘要"),
]

RETRY_TESTS = [
    "首次 200 之后第二次也成功 → **不得创建重复对象**",
    "首次超时后重复成功 → **不得静默覆盖**",
    "第二次返回 409/412 → 按契约处理",
    "代理在 body 中途断连 → **不得把 TLS 错误转成普通网络错误**",
]

FIELDS = [
    ("scenario", "场景名（25 个具名故障）"),
    ("entry_condition", "入口条件"),
    ("injection_layer", "注入层"),
    ("legacy_expectation", "**原版期望**（含提示文字与时机）"),
    ("new_expectation", "目标期望"),
    ("recovery_threshold", "恢复阈值"),
    ("user_message", "用户提示"),
    ("retry_policy", "重试策略"),
    ("idempotent", "**是否幂等**"),
    ("evidence", "证据"),
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

ENUMS = {'idempotent': ('yes', 'no', 'partial', 'unknown'), 'retry_policy': ('none', 'linear', 'exponential', 'unknown'), 'evidence': ('observed', 'measured', 'source', 'decompiled', 'secondhand', 'unverified', 'unknown')}
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

def cmd_layers(a):
    print("=" * 76)
    print("网络检测四层（**`navigator.onLine` 只说明部分事实**）")
    print("=" * 76)
    for k, what, note in LAYERS:
        print(f"   {k:<24} {what:<10} {note}")
    print("\n⚠️ **真正决定原版行为的是具体域名、协议、端口、认证、TLS 与业务响应**。")
    print("   状态迁移只能依据**明确事件**，")
    print("   **不把 online→offline 的瞬时 DNS 失败直接映射成数据丢失**。")
    print("\n降级矩阵（先按真实路径采集，再决定目标是否「足够好」）:")
    for s in DEGRADE_SCENARIOS:
        print(f"   · {s}")
    print("\n每项记录：原版**提示文字、出现时机**、是否允许重试、是否生成草稿、")
    print("   是否会**重复提交**、是否暴露技术错误。")
    print("\n目标栈新增字段: `network_class`(none/portal/captive/proxy/normal) ·")
    print("   `rtt_p50/p95/max` · `bytes_uploaded/downloaded` · `attempt_id` ·")
    print("   `request_hash` · `client_clock_drift` · `user_visible_state`")
    return 0


def cmd_faults(a):
    print("=" * 74)
    print(f"故障矩阵 · {len(FAULTS)} 个具名场景（Toxiproxy 之上扩展）")
    print("=" * 74)
    for i, f in enumerate(FAULTS, 1):
        print(f"   {i:>2}. {f}")
    print("\n每项定义：入口条件 · 注入层 · **原版期望** · 目标期望 ·")
    print("   恢复阈值 · 用户提示 · 重试策略 · 幂等策略")
    print("\n⚠️ Clumsy（Windows）与 tc-netem/Comcast（Linux）**只作手工探索与注入**，")
    print("   **不进入默认门禁**。")
    print("⚠️ `facebook/augmented-traffic-control` 与 `alexei-led/comcast` "
          "标**来源不确定**，需核验后再升级。")
    return 0


def cmd_proxy(a):
    print("=" * 76)
    print("企业网络（**不是「支持代理」一个布尔值**）")
    print("=" * 76)
    for p in PROXY_ITEMS:
        print(f"   · {p}")
    print("\n⚠️ WebView 与原生 HTTP 客户端**不得假定使用同一代理状态** ——")
    print("   分别记录 Tauri WebView 配置、WinHTTP/WinINet 语义、")
    print("   Rust `reqwest`/系统解析器、**PAC JS 特性差异**。")
    print("\n⚠️ PAC 与 WPAD 本身有**名称解析和中间人风险** ——")
    print("   测试环境必须显式声明 PAC 内容与网络拓扑，")
    print("   **不能在生产网络自动开启**。")
    print("\n⚠️ **企业 TLS 拦截测试默认不应把根 CA 导入个人信任库** ——")
    print("   只属受控测试 profile，证据必须可销毁。")
    return 0


def cmd_retry(a):
    print("=" * 76)
    print("重试与幂等（**围绕业务幂等性，不是只测「会不会重发」**）")
    print("=" * 76)
    for k, why in RETRY_FIELDS:
        print(f"   {k:<32} {why}")
    print("\n验证场景:")
    for t in RETRY_TESTS:
        print(f"   · {t}")
    print("\n写入操作用**服务端生成幂等键**或客户端 UUID + 去重窗口；")
    print("查询操作允许缓存但需 **stale-while-revalidate** 语义。")
    return 0


def cmd_init(a):
    os.makedirs(os.path.dirname(a.init) or ".", exist_ok=True)
    with open(a.init, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow([k for k, _ in FIELDS])
        for fa in FAULTS:
            w.writerow([fa] + ["TODO"] * (len(FIELDS) - 1))
    print(f"已生成网络故障矩阵: {a.init}（{len(FAULTS)} 场景）")
    print("\n⚠️ 离线证据落点应是**可重放数据包和确定性录制**：")
    print("   mitmproxy flow 导出 + 系统时钟 + 代理 + DNS + 磁盘 cache 一起作 fixture")
    return 0


def cmd_check(a):
    if not os.path.exists(a.check):
        print(f"❌ 文件不存在: {a.check}")
        return 2
    with open(a.check, encoding="utf-8", errors="replace", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        print("❌ 空表")
        return 1

    def g(r, k):
        return (r.get(k) or "").strip()

    no_legacy, no_idem, missing = [], [], []
    for i, r in enumerate(rows, 1):
        if not g(r, "legacy_expectation") or g(r, "legacy_expectation") == "TODO":
            no_legacy.append(i)
        v = g(r, "idempotent")
        if not v or v in ("TODO", "待填", "—", "未知"):
            no_idem.append(i)
        miss = [k for k, _ in FIELDS
                if not g(r, k) or g(r, k) in ("TODO", "待填", "—")]
        if miss:
            missing.append((i, miss))

    print("=" * 74)
    print(f"网络故障矩阵 · {len(rows)} 条")
    print("=" * 74)
    if no_legacy:
        print(f"\n❌ {len(no_legacy)} 条缺**原版期望**（行 {no_legacy[:15]}）")
        print("   → 必须含原版**提示文字与出现时机**，不能只写「报错」")
    if no_idem:
        print(f"\n❌ {len(no_idem)} 条幂等性未判定（行 {no_idem[:15]}）")
    if missing:
        print(f"\n⚠️ {len(missing)} 条字段不全")

    if not (no_legacy or no_idem):
        print("\n✅ 网络矩阵原版期望与幂等性齐全")

    print("\n🔑 **原版「能离线用」是可用状态机，不是一句错误提示。**")
    print("   目标必须**同事件序复刻**；后台任务必须**去重**。")
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

    return 1 if (a.gate and (no_legacy or no_idem or _ev or _ct)) else 0


def main():
    ap = argparse.ArgumentParser(description="离线与网络不确定环境")
    ap.add_argument("--layers", action="store_true")
    ap.add_argument("--faults", action="store_true")
    ap.add_argument("--proxy", action="store_true")
    ap.add_argument("--retry", action="store_true")
    ap.add_argument("--init")
    ap.add_argument("--check")
    ap.add_argument("--gate", action="store_true")
    a = ap.parse_args()
    if a.layers:
        return cmd_layers(a)
    if a.faults:
        return cmd_faults(a)
    if a.proxy:
        return cmd_proxy(a)
    if a.retry:
        return cmd_retry(a)
    if a.init:
        return cmd_init(a)
    if a.check:
        return cmd_check(a)
    print("❌ 需要 --layers / --faults / --proxy / --retry / --init / --check 之一")
    return 2


if __name__ == "__main__":
    sys.exit(main())
