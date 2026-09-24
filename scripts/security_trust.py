#!/usr/bin/env python3
"""安全与信任边界（第十一轮 A 类）—— **完全空白的一块**。

**🔑 核心认知**：
> **已有依赖扫描回答不了"谁能在哪一步替换可执行体"。**
> cargo-deny / Grype / ScanCode / REUSE 主要答成分、漏洞、许可证；
> 本轮补的是**代码签名、更新元数据、运行特权、Web 内容隔离、端到端验证**。

**六份文件**：`signing` · `update-trust` · `webview-acl` · `ipc-contract` ·
`secret-store` · `sandbox`

用法:
  security_trust.py --signing         # 签名生命周期（**时间戳不是永久**）
  security_trust.py --update          # TUF 威胁模型与更新信任
  security_trust.py --webview         # WebView 边界（**按攻击路径反推**）
  security_trust.py --secrets         # 凭据存储（**默认答案是否定**）
  security_trust.py --sandbox         # 沙箱与降权
  security_trust.py --init ledger/security_gates.csv
  security_trust.py --check ledger/security_gates.csv --gate

退出码: 0 通过 / 1 缺项或有未验证拒绝路径 / 2 用法错误
"""
import argparse
import csv
import os
import sys

# 签名：🔴 **时间戳不是"签一次管永久"**
SIGNING_MYTHS = [
    ("普通时间戳", "把签名有效期锚定到签名时刻 → 证书过期后**仍可能验证**", "✅ 有效"),
    ("**Lifetime Signing OID**",
     "签名证书含该 OID，或验证方设 `WTD_LIFETIME_SIGNING_FLAG` → **即使有时间戳，过期也失败**",
     "🔴 推翻常见误解"),
    ("时间戳证书不受信任", "时间戳证书位于不受信任存储 → 签名失败", "🔴 失败"),
    ("证书吊销", "吊销后即使当时有效也失败", "🔴 失败"),
]

# 签名策略四个必答字段 + 五种必测状态
SIGNING_FIELDS = [
    ("timestamp_authority", "时间戳机构"),
    ("timestamp_protocol", "**RFC 3161 + SHA-256**（优先）"),
    ("revocation_policy", "吊销策略"),
    ("long_term_verification_artifacts", "**长期验证制品**"),
]

SIGNING_STATES = [
    "CA 已吊销但签名当时有效",
    "根轮转",
    "TSA 不可达",
    "证书过期",
    "**Lifetime Signing**",
]

UPDATE_SCENARIOS = [
    "从哪里取 index",
    "是否校验目标**长度**",
    "何时拒绝**旧 snapshot**",
    "离线缓存保留多久",
    "**rollback 版本上限**",
    "**root 轮换演练**",
]

TUF_ROLES = ["root", "targets", "snapshot", "timestamp"]

# WebView：**穷尽度要用攻击路径反推，不能只列 CSP 头**
WEBVIEW_PATH = [
    "Web 内容 → preload → capability → Rust command → 文件/网络/进程",
]

WEBVIEW_QUESTIONS = [
    "是否可由**不可信 origin** 触发",
    "参数是否**白名单**",
    "是否跨窗口共享",
    "返回数据是否含**系统路径或令牌**",
    "能否改变**持久状态**",
    "错误是否泄漏**绝对路径或内部 URL**",
]

CSP_DIRECTIVES = ["default-src", "script-src", "style-src", "img-src",
                  "connect-src", "frame-src"]

CSP_BAN = [
    "`unsafe-inline`", "`unsafe-eval`", "**远程任意脚本**",
    "（除非有逐条豁免与签名证据）",
]

# 凭据：**默认答案是否定**
SECRET_RULE = [
    "🚫 **不应把 DPAPI blob 直接搬到新格式**",
    "🚫 **不应在跨用户、跨设备、跨 profile 时假定可解密**",
    "✅ 目标端**默认不迁移**",
    "✅ 不清空旧凭据但**不批量复制**",
    "✅ 提供**显式重新登录**",
    "⚠️ 若原版「明文记住密码」被用户视为功能 → 保留功能但改成系统钥匙串，"
    "并生成前后路径、权限与撤销证据（**不能因「体验一致」复制不安全实现**）",
]

SECRET_STORE = [
    ("Windows", "DPAPI", "仅作**原版行为取证对象**"),
    ("macOS", "Keychain", "逐平台定义 access_group、后台访问、锁屏后是否清除"),
    ("Linux", "Secret Service / libsecret", "定义 service / account / ACL"),
]

SANDBOX = [
    ("Windows", "AppContainer / MSIX、Job Object、低完整性令牌、LPAC",
     "每个后端记录最小 SID/能力与文件/注册表/管道/剪贴板/设备/网络边界"),
    ("Linux", "seccomp、landlock、namespaces、XDG、Wayland 门户", ""),
    ("macOS", "entitlements、sandbox、Hardened Runtime、notarization ticket", ""),
]

FIELDS = [
    ("gate_id", "门禁编号"),
    ("area", "域（signing / update-trust / webview-acl / secret-store / sandbox）"),
    ("legacy_behavior", "原版行为"),
    ("new_capability", "目标栈最小能力"),
    ("negative_test", "**负向测试**（必须有拒绝路径）"),
    ("rejection_path_verified", "**拒绝路径是否已验证**"),
    ("failure_state", "失败状态"),
    ("evidence_artifact", "证据制品"),
    ("rollback", "回滚条件"),
]


def cmd_signing(a):
    print("=" * 76)
    print("签名生命周期（🔴 **时间戳不是「签一次管永久」**）")
    print("=" * 76)
    for k, what, res in SIGNING_MYTHS:
        print(f"\n   【{k}】{res}")
        print(f"      {what}")
    print("\n四个必答字段:")
    for k, why in SIGNING_FIELDS:
        print(f"   · {k:<38} {why}")
    print("\n五种必测状态（**不能只检查 ValidSignature**）:")
    for s in SIGNING_STATES:
        print(f"   · {s}")
    print("\nCI 至少保存：`.exe/.msi/.dmg/.deb/.AppImage`、嵌入签名、"
          "`signtool verify /pa /all` 输出、RFC 3161 响应、TSA 链、CRL/OCSP 状态、完整日志")
    print("\n⚠️ 目标栈不是云原生工件时，**不能用「Sigstore 已存在」替代原生安装器签名**：")
    print("   Windows 要 Authenticode；macOS 要 notary/stapler + Gatekeeper 证据；")
    print("   Linux 要有包格式 digest/GPG/sigstore 选择矩阵。")
    return 0


def cmd_update(a):
    print("=" * 76)
    print("更新信任（**TUF 应作为协议设计参照，不是把 Python 实现塞进 Tauri**）")
    print("=" * 76)
    print("   四种角色: " + " · ".join(TUF_ROLES))
    print("\n强制写出的项：阈值签名、密钥轮转、consistent snapshot、"
          "hash 与长度校验、**回滚与冻结保护**")
    print("\n`security/update-trust.md` 必答:")
    for s in UPDATE_SCENARIOS:
        print(f"   · {s}")
    print("\n⚠️ 参考实现不是稳定 API，**不应成为生产依赖**。")
    print("   真正可落地的是把 TUF **威胁模型**转成 `update-scenarios/` 目录。")
    print("\n⚠️ **cosign 与 TUF 职责必须分开**：")
    print("   cosign 给制品与证据链签名（keyless、Fulcio、Rekor、KMS；2.x 稳定，")
    print("   默认 ECDSA-P256 + SHA-256）；TUF 管更新元数据的一致性。")
    print("   构建产物 / SBOM / attestation / 安装包 / 更新 manifest / 功能证据包"
          "**各有独立 digest**。")
    return 0


def cmd_webview(a):
    print("=" * 78)
    print("WebView 边界（**穷尽度要用攻击路径反推，不能只列 CSP 头**）")
    print("=" * 78)
    for p in WEBVIEW_PATH:
        print(f"   攻击路径: {p}")
    print("\n每个 command 必须回答:")
    for q in WEBVIEW_QUESTIONS:
        print(f"   · {q}")
    print(f"\nCSP 指令要逐个区分: " + " · ".join(CSP_DIRECTIVES))
    print("   ⚠️ 尤其 `tauri://`、`http://tauri.localhost` 与**多 WebView** 场景")
    print(f"\n禁止: " + " · ".join(CSP_BAN))
    print("\npreload: 只导出窄接口，**不在全局挂 `window.__api`**；")
    print("   `contextIsolation` + 固定 `nonce`；所有 `postMessage` 校验 origin/source/schema/幂等键")
    print("\n⚠️ **URL handler 与拖放文件把用户输入当命令或路径，是典型权宜设计** ——")
    print("   原版若双击任意文件路径就执行联网动作，目标必须拆成")
    print("   「打开—解析—预览—确认—执行」。")
    print("\nNuclei 模板建议: update-manifest-tamper · unsigned-update-asset ·")
    print("   ipc-command-injection · webview-file-origin · postmessage-origin-missing ·")
    print("   deep-link-scheme-injection · privileged-api-exposed")
    print("   ⚠️ Nuclei 明确提示「积极开发中可能有破坏性变更」 → **模板与 CI 必须锁 commit/版本**")
    return 0


def cmd_secrets(a):
    print("=" * 76)
    print("凭据存储（**默认答案是否定**）")
    print("=" * 76)
    for plat, api, note in SECRET_STORE:
        print(f"\n   {plat:<10} {api}")
        if note:
            print(f"              {note}")
    print("\n规则:")
    for r in SECRET_RULE:
        print(f"   {r}")
    return 0


def cmd_sandbox(a):
    print("=" * 78)
    print("沙箱与降权（**可验证场景，不是一句「Rust 更安全」**）")
    print("=" * 78)
    for plat, what, note in SANDBOX:
        print(f"\n   【{plat}】{what}")
        if note:
            print(f"      {note}")
    print("\n⚠️ **每个 capability 必须有一条正向成功路径 + 一条负向拒绝路径**。")
    print("   若某平台无法提供相同能力 → **显式降级或禁用**，")
    print("   **而不是静默返回成功**。")
    print("\n⚠️ 沙箱/降权是可验证场景，不是安全声明。")
    return 0


def cmd_init(a):
    os.makedirs(os.path.dirname(a.init) or ".", exist_ok=True)
    with open(a.init, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow([k for k, _ in FIELDS])
        w.writerow(["TODO"] * len(FIELDS))
    print(f"已生成安全门禁表: {a.init}")
    print("\n⚠️ 六域：signing / update-trust / webview-acl / "
          "ipc-contract / secret-store / sandbox")
    print("   每个都同时记：原版行为 · 目标最小能力 · **负向测试** · "
          "失败状态 · 证据制品 · 回滚条件")
    return 0


def cmd_check(a):
    if not os.path.exists(a.check):
        print(f"❌ 文件不存在: {a.check}")
        return 2
    with open(a.check, encoding="utf-8", errors="replace", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        print("❌ 空表 —— **未建立安全门禁**")
        return 1

    def g(r, k):
        return (r.get(k) or "").strip()

    no_negative, unverified, no_rollback, missing = [], [], [], []
    for i, r in enumerate(rows, 1):
        if not g(r, "negative_test") or g(r, "negative_test") == "TODO":
            no_negative.append(i)
        v = g(r, "rejection_path_verified").lower()
        if v not in ("yes", "y", "true", "是", "已验证"):
            unverified.append(i)
        if not g(r, "rollback") or g(r, "rollback") == "TODO":
            no_rollback.append(i)
        miss = [k for k, _ in FIELDS
                if not g(r, k) or g(r, k) in ("TODO", "待填", "—")]
        if miss:
            missing.append((i, miss))

    print("=" * 74)
    print(f"安全门禁 · {len(rows)} 条")
    print("=" * 74)
    if no_negative:
        print(f"\n❌ {len(no_negative)} 条缺**负向测试**（行 {no_negative[:15]}）")
        print("   → 每个 capability 都要有**拒绝路径**")
    if unverified:
        print(f"\n❌ {len(unverified)} 条**拒绝路径未验证**（行 {unverified[:15]}）")
        print("   → 没验证过的拒绝路径等于没有")
    if no_rollback:
        print(f"\n⚠️ {len(no_rollback)} 条缺回滚条件")
    if missing:
        print(f"\n⚠️ {len(missing)} 条字段不全")

    if not (no_negative or unverified):
        print("\n✅ 安全门禁负向测试齐全且已验证")

    print("\n🔑 **已有依赖扫描答不了「谁能在哪一步替换可执行体」。**")
    print("\n⚠️ 若某平台无法提供相同能力 → 显式降级或禁用，")
    print("   **不是静默返回成功**。")
    return 1 if (a.gate and (no_negative or unverified)) else 0


def main():
    ap = argparse.ArgumentParser(description="安全与信任边界")
    for f in ("signing", "update", "webview", "secrets", "sandbox"):
        ap.add_argument(f"--{f}", action="store_true")
    ap.add_argument("--init")
    ap.add_argument("--check")
    ap.add_argument("--gate", action="store_true")
    a = ap.parse_args()
    if a.signing:
        return cmd_signing(a)
    if a.update:
        return cmd_update(a)
    if a.webview:
        return cmd_webview(a)
    if a.secrets:
        return cmd_secrets(a)
    if a.sandbox:
        return cmd_sandbox(a)
    if a.init:
        return cmd_init(a)
    if a.check:
        return cmd_check(a)
    print("❌ 需要 --signing/--update/--webview/--secrets/--sandbox/--init/--check 之一")
    return 2


if __name__ == "__main__":
    sys.exit(main())
