#!/usr/bin/env python3
"""目标栈能力矩阵（第九轮 B 区）—— 新栈怎么做对。

**为什么需要**：前八轮几乎全是"取证"工具，对**新栈怎么做得对**几乎是空白。
Tauri + React + Rust 各有自己的失败模式，且**三 WebView 的行为差异是像素级复刻的杀手**。

**⚠️ Tauri 2 不是 Tauri 1 的升级**：
`productName/version` 上移顶层、`tauri` 配置键改 `app`、二进制不再自动匹配 productName；
SystemTray / 旧 Menu / `Builder::on_menu_event` **被移除**；
更新器改为 `tauri-plugin-updater`；`@tauri-apps/api` 只保留 core/path/event/window，
其余进插件。**能力/ACL 是默认拒绝的新边界**。

用法:
  target_stack.py --tauri                     # Tauri 2 迁移事实与能力矩阵
  target_stack.py --ipc                       # invoke / 事件 / Channel 三套语义
  target_stack.py --webview                   # 三 WebView 差异基线
  target_stack.py --react                     # React 确定性字段
  target_stack.py --rust                       # Rust 工具链门禁
  target_stack.py --check ledger/capabilities.json --gate   # 能力审计

退出码: 0 通过 / 1 有风险项 / 2 用法错误
"""
import argparse
import csv
import json
import os
import sys

TAURI2 = [
    ("配置键变更", "`tauri` → `app`；`productName`/`version` 上移顶层"),
    ("二进制命名", "不再自动匹配 productName —— **打包产物名要显式确认**"),
    ("SystemTray", "**被移除** → tray-icon"),
    ("旧 Menu / Builder::on_menu_event", "**被移除**"),
    ("更新器", "改为 `tauri-plugin-updater`"),
    ("@tauri-apps/api 拆分", "只保留 core / path / event / window，其余进插件"),
    ("能力模型", "**capabilities / ACL = 默认拒绝的新边界**（不是 Tauri 1 的 allowlist）"),
    ("Rust 版本", "plugins-workspace 要求 Rust ≥ 1.77.2"),
]

IPC = [
    ("invoke", "**一次请求/响应**", "适合命令式调用；错误必须**可机读**"),
    ("事件 event", "跨窗口/后端**广播**", "适合状态变更通知"),
    ("Channel", "**长流与逐帧增量**", "连续像素数据、日志流、文件内容优先用它或临时文件句柄"),
]

IPC_FIELDS = [
    "command", "args schema", "result schema", "**error variant**",
    "channel", "event topic", "序列化方向", "平台", "调用频率", "**延迟预算**",
]

WEBVIEW_DIFF = [
    ("Windows", "WebView2 (Chromium)", "最接近 Chrome；注意 Evergreen 版本漂移"),
    ("Linux", "WebKitGTK", "**CSS、滚动、字体、缩放与 Chromium 有差异**"),
    ("macOS", "WKWebView", "**滚动惯性、字体渲染、缩放与 Chromium 有差异**"),
]

REACT_FIELDS = [
    ("list_key_strategy", "列表 key 策略（index 会破坏复用语义）"),
    ("key_stability", "key 稳定性（跨排序/过滤是否保持）"),
    ("component_pure_render", "纯渲染（StrictMode 双渲染可暴露不纯）"),
    ("effect_cleanup_present", "effect 清理是否齐全"),
    ("focus_trap_owner", "焦点陷阱归属"),
    ("portal_root", "portal 挂载点（影响 z-index 与事件冒泡）"),
    ("return_focus_to", "关闭后焦点归还到哪里"),
    ("controlled_input_rehydration", "受控输入回填"),
    ("css_layer_order", "**样式层顺序须由锁文件固定**"),
    ("runtime_determinism", "运行时确定性"),
]

RUST_GATES = [
    ("cargo-deny", "依赖图 / 许可 / 安全公告", "MIT / Apache-2.0", ""),
    ("cargo-nextest", "并发测试与重试", "MIT / Apache-2.0", ""),
    ("cargo-llvm-cov", "LLVM 源级覆盖（行/区域/分支），兼容 nextest", "MIT / Apache-2.0", ""),
    ("cargo-geiger", "统计 unsafe 用量", "Apache-2.0 / MIT",
     "⚠️ **不直接判断安全**，应与 crev / safety-dance 结合"),
    ("cargo-audit / cargo-vet", "供应链审核", "—", "后者需再核验仓库"),
    ("cargo-careful", "打开额外检查", "—", ""),
    ("cargo-fuzz", "解析器/反序列化/坐标/颜色/文件格式的结构保持 fuzz", "—", ""),
    ("cargo-msrv", "MSRV 版本提案", "—", "固定策略，**不是长期自动追随 latest stable**"),
    ("rust-lang/miri", "UB 解释器", "MIT / Apache-2.0",
     "⚠️ 需 nightly，非全 target；**crates.io 同名占位包是抢注的 yanked dummy，绝不可依赖**"),
    ("thiserror", "稳定错误类型", "—", ""),
    ("anyhow", "**只用于应用边界聚合**", "—", ""),
    ("serde", "稳定契约序列化", "—", ""),
]

VIRTUAL_LIST = [
    "滚动条比例", "顶部/底部空白", "**按像素锚定**",
    "内容高度变化时的跳动", "反向列表", "选择保留", "编辑保留",
    "键盘上下键", "Home/End", "分页加载", "窗口 resize", "字体变化", "滚动恢复",
]

CSS_RULES = [
    "相同输入生成**相同样式**",
    "不同主题切换**无 FOUC**",
    "z-index 层有**稳定 owner**",
    "样式层顺序受**锁文件固定**",
    "关键像素**不依赖 CSS 变量未定义回退**",
]

CAP_FIELDS = [
    "permission", "identifier", "platform", "target", "window_label",
    "webview_label", "scope", "description", "local", "remote", "requires",
    "added_in_version", "removed_in_version",
]


def cmd_tauri(a):
    print("=" * 74)
    print("Tauri 2 迁移事实（**不是 Tauri 1 的升级**）")
    print("=" * 74)
    for k, why in TAURI2:
        print(f"\n   【{k}】")
        print(f"      {why}")
    print("\n⚠️ 旧技能若仍以 Tauri 1 **allowlist** 思考，会系统性漏掉现代能力模型。")
    print(f"\n能力矩阵字段（{len(CAP_FIELDS)} 项）:")
    print("   " + " · ".join(CAP_FIELDS))
    print("\n⚠️ 官方插件聚合仓是**能力盘点起点，不是质量背书** ——")
    print("   每个插件的版本、许可证、维护状态须在生成时**重新读取仓库**，")
    print("   **不因聚合页一次核验而冻结版本结论**。")
    return 0


def cmd_ipc(a):
    print("=" * 72)
    print("IPC 三套语义（**不是只有「函数调用」**）")
    print("=" * 72)
    for k, what, note in IPC:
        print(f"\n   【{k}】{what}")
        print(f"      {note}")
    print(f"\nIPC 矩阵字段:")
    for f in IPC_FIELDS:
        print(f"   · {f}")
    print("\n⚠️ 禁止把**大数组反复序列化往返**。")
    print("⚠️ 所有边界错误必须**可机读**，不应让前端只看到 `error: something failed`。")
    return 0


def cmd_webview(a):
    print("=" * 74)
    print("三 WebView 差异基线（**像素级复刻的杀手**）")
    print("=" * 74)
    for plat, engine, note in WEBVIEW_DIFF:
        print(f"\n   {plat:<10} {engine}")
        print(f"              {note}")
    print("\n⚠️ WebView2 / WebKitGTK / WKWebView 的 **CSS、滚动、缩放、字体差异**")
    print("   应作为**版本化基线**，每个平台各自一套 golden，**不许跨平台共用**。")
    print("\n多 WebView 清单（**不是优化技巧，是复刻等价单元**）:")
    for f in ["window/WebView label", "owner", "URL 或本地路径", "上下文隔离",
              "预加载", "用户代理", "devtools", "文件拖入", "右键", "快捷键",
              "缩放", "剪贴板访问", "权限来源"]:
        print(f"   · {f}")
    print("\n⚠️ 双窗口共享状态时**不能只测前端状态同步**，还要测：")
    print("   首次挂载 / 失焦 / 关闭一个 WebView / 刷新 / 导航拦截 / 下载 /")
    print("   协议升级 / CSP / postmessage 来源")
    return 0


def cmd_react(a):
    print("=" * 74)
    print("React 确定性字段")
    print("=" * 74)
    for k, why in REACT_FIELDS:
        print(f"   {k:<32} {why}")
    print("\n⚠️ **StrictMode 故意双调用**是发现不纯渲染和缺失清理的有效机制，")
    print("   但**双调用产生的 UI 不是基准** —— WPF 原版一次渲染的确定结果才是基准。")
    print("   生产构建的探针仍必须**一次且仅一次**执行真实副作用。")
    print("\n虚拟列表**不能按「渲染了几千行」验收**，应按焦点和锚定验收:")
    for v in VIRTUAL_LIST:
        print(f"   · {v}")
    print("\nCSS 门禁（不规定只用某方案，规定确定性）:")
    for c in CSS_RULES:
        print(f"   · {c}")
    print("\n⚠️ 应在每个交互后读 `getComputedStyle` 和盒模型做**字段级 diff**，")
    print("   **而非只比较截图**。")
    return 0


def cmd_rust(a):
    print("=" * 76)
    print("Rust 工具链门禁（编译 → 审计 → 测试 → 覆盖 → UB）")
    print("=" * 76)
    for k, what, lic, note in RUST_GATES:
        print(f"\n   【{k}】{what}   ({lic})")
        if note:
            print(f"      {note}")
    print("\n⚠️ **Miri 只能从 rust-lang/miri 吸收** ——")
    print("   crates.io 上的同名占位包是**抢注的 yanked dummy，绝不可作为依赖**。")
    print("\n⚠️ MSRV 是固定策略：用 `rust-toolchain.toml` 固定 + `cargo-msrv` 做版本提案，")
    print("   **不在每次新稳定版发布时静默升版**。")
    print("\n职责边界：serde 管稳定契约 · thiserror 定义稳定错误 · ")
    print("   **anyhow 只用于应用边界聚合**。")
    return 0


def cmd_check(a):
    if not os.path.exists(a.check):
        print(f"❌ 文件不存在: {a.check}")
        return 2
    try:
        data = json.load(open(a.check, encoding="utf-8"))
    except Exception as e:
        print(f"❌ JSON 解析失败: {e}")
        return 2
    caps = data if isinstance(data, list) else data.get("capabilities", [])
    if not caps:
        print("❌ 无能力条目")
        return 2

    wildcard, no_platform, no_scope = [], [], []
    for i, c in enumerate(caps, 1):
        scope = str(c.get("scope", ""))
        if scope.strip() in ("*", "**", "allow-all", "true"):
            wildcard.append(i)
        if not c.get("platform"):
            no_platform.append(i)
        if not c.get("scope"):
            no_scope.append(i)

    print("=" * 72)
    print(f"Tauri 能力审计 · {len(caps)} 条")
    print("=" * 72)
    if wildcard:
        print(f"\n🔴 **wildcard scope** {len(wildcard)} 条（行 {wildcard[:15]}）")
        print("   → 能力模型是**默认拒绝**，wildcard 等于绕过整个边界")
    if no_platform:
        print(f"\n⚠️ {len(no_platform)} 条缺 platform 声明")
    if no_scope:
        print(f"\n⚠️ {len(no_scope)} 条缺 scope 表达式")

    if not (wildcard or no_platform or no_scope):
        print("\n✅ 能力配置无 wildcard、平台与 scope 齐全")

    print("\n⚠️ 应输出**最小权限补丁**，而不是保留宽泛 scope。")
    return 1 if (a.gate and wildcard) else 0


def main():
    ap = argparse.ArgumentParser(description="目标栈能力矩阵")
    ap.add_argument("--tauri", action="store_true")
    ap.add_argument("--ipc", action="store_true")
    ap.add_argument("--webview", action="store_true")
    ap.add_argument("--react", action="store_true")
    ap.add_argument("--rust", action="store_true")
    ap.add_argument("--check")
    ap.add_argument("--gate", action="store_true")
    a = ap.parse_args()
    if a.tauri:
        return cmd_tauri(a)
    if a.ipc:
        return cmd_ipc(a)
    if a.webview:
        return cmd_webview(a)
    if a.react:
        return cmd_react(a)
    if a.rust:
        return cmd_rust(a)
    if a.check:
        return cmd_check(a)
    print("❌ 需要 --tauri / --ipc / --webview / --react / --rust / --check 之一")
    return 2


if __name__ == "__main__":
    sys.exit(main())
