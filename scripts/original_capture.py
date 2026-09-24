#!/usr/bin/env python3
"""原版证据采集（S0）—— 把"观察原版"变成可复现实验。

**为什么需要**：现有工具链能证明新版"做成了什么"，
却难以稳定证明原版"本来是什么"。原版不是待描述的需求，
而是**唯一可信的测量基准**。

三种模式:
  --tree   导出控件树（UIA 快照；跨平台下用可插拔后端）
  --shot   确定性截图（记录环境参数，不是随手截一张）
  --env    只打印/校验截图环境参数（DPI/缩放/主题/动画…）

⚠️ 诚实降级：Windows + pywinauto/FlaUI 可用时走真实 UIA；
不可用时**不假装成功**，生成"环境契约骨架 + 待人工采集"清单。

用法:
  original_capture.py --pid 1234 --out original_capture/ --tree --shot
  original_capture.py --pid 1234 --out original_capture/ --env
  original_capture.py --init original_capture/          # 生成证据目录与 MANIFEST 骨架

退出码: 0 正常 / 1 有阻塞项 / 2 用法或环境错误
"""
import argparse
import hashlib
import json
import os
import platform
import sys
import time

REQUIRED_ENV_FIELDS = [
    ("display_scale", "显示缩放（100/125/150/200%）"),
    ("dpi_awareness", "DPI 感知模式"),
    ("theme", "主题与配色（light/dark/高对比度）"),
    ("window_state", "窗口状态（maximized/restored）"),
    ("animation", "动画状态（disabled/wait-stable/non_deterministic）"),
    ("locale", "语言与区域"),
    ("multi_monitor", "多显示器布局"),
    ("cursor_visible", "光标是否可见"),
    ("ime_candidate", "输入法候选框是否弹出"),
    ("taskbar_overlap", "任务栏是否遮挡"),
    ("window_active", "窗口是否激活"),
]

# 截图三原语：不能互相冒充
CAPTURE_PRIMITIVES = {
    "printwindow": "窗口自绘到 DC —— **视觉主基线**",
    "bitblt": "拷设备上下文 —— 屏幕实际呈现对照（受遮挡/DWM 影响）",
    "render_target_bitmap": "WPF 进程内渲染 Visual —— 模板/资源校验（绕开遮挡）",
    "client_crop": "客户区裁剪 —— **布局基线**",
}

BACKENDS = {
    "pywinauto": "Python UIA 后端（WPF/WinForms/Store/Qt5），易接入现有 Python 台账",
    "flaui": ".NET UIA 库，WPF 首选主驱动（控件身份+模式+等待）",
    "uia_raw": "comtypes + 原生 UIA，最接近系统的原始控件树",
}

# 定位策略稳定优先级（坐标只能兜底，不得作为点击定位唯一依据）
LOCATOR_PRIORITY = [
    ("automation_id", "AutomationProperties.AutomationId / 显式自动化标识", "high"),
    ("stable_text", "稳定业务文本（排除动态序号与时间戳）", "high"),
    ("type_plus_ancestor", "控件类型 + 稳定祖先路径", "medium"),
    ("accessible_name", "可访问名称 / 键盘助记符", "medium"),
    ("xaml_name", "x:Name（须附反编译/XAML 来源）", "low"),
    ("class_name", "ClassName —— 只能消歧，不可单独使用", "fragile"),
    ("coordinate", "坐标 —— 只能画框/截图/验证布局，**不得作点击定位唯一依据**", "fragile"),
]

TREE_FIELDS = [
    "automation_id", "xaml_name", "control_type", "localized_control_type",
    "name", "help_text", "access_key", "is_enabled", "is_offscreen",
    "is_keyboard_focusable", "has_keyboard_focus", "bounding_rectangle",
    "patterns", "runtime_id", "process_id", "parent_id",
]


def sha256(path):
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            for b in iter(lambda: f.read(1 << 20), b""):
                h.update(b)
    except Exception:
        return "?"
    return h.hexdigest()[:16]


def detect_backend():
    """探测可用的 UIA 后端。探测不到就如实报告，不假装成功。"""
    if platform.system() != "Windows":
        return None, f"当前系统 {platform.system()} 非 Windows —— 无法驱动 UIA"
    try:
        import pywinauto  # noqa: F401
        return "pywinauto", "pywinauto 可用（建议再用 FlaUI 交叉验证）"
    except ImportError:
        pass
    try:
        import comtypes  # noqa: F401
        return "uia_raw", "comtypes 可用（原生 UIA）"
    except ImportError:
        pass
    return None, "未找到 pywinauto / comtypes；FlaUI 需 .NET 环境（不作为本脚本后端）"


def cmd_init(a):
    d = a.init if isinstance(a.init, str) else "original_capture"
    os.makedirs(d, exist_ok=True)
    manifest = {
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "target_binary_sha256": "TODO",
        "os_version": "TODO",
        "dotnet_runtime": "TODO",
        "capture_environment": {k: "TODO" for k, _ in REQUIRED_ENV_FIELDS},
        "capture_primitives": list(CAPTURE_PRIMITIVES),
        "locator_priority": [p[0] for p in LOCATOR_PRIORITY],
        "tree_fields": TREE_FIELDS,
        "states": [],
        "readonly_hashed": True,
        "notes": "原版证据目录。**只读哈希保护** —— 避免改了证据而不自知。",
    }
    p = os.path.join(d, "MANIFEST.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(f"已生成证据目录骨架: {p}")
    print("\n下一步：")
    print("  1. 填 target_binary_sha256 / os_version / dotnet_runtime")
    print("  2. 填 capture_environment 全部字段（不许留 TODO 就采集）")
    print("  3. 跑 --tree --shot 采集每个状态")
    print("\nstate_id 命名: <模块>__<视图>__<状态>__<变体>__<序号>")
    print("  例: editor__mainwindow__hover_savebutton__zh-CN_150_dark__0001")
    return 0


def cmd_env(a):
    print("=" * 64)
    print("截图环境契约（每个字段都必须固定，不许留在测试员脑子里）")
    print("=" * 64)
    for k, why in REQUIRED_ENV_FIELDS:
        print(f"  {k:<18} {why}")
    print("\n截图三原语（都要留，不能互相冒充）:")
    for k, v in CAPTURE_PRIMITIVES.items():
        print(f"  {k:<22} {v}")
    print("\n定位策略稳定优先级:")
    for name, why, stab in LOCATOR_PRIORITY:
        print(f"  {name:<20} [{stab:<7}] {why}")
    print("\n⚠️ 坐标点击与「体验细节不能丢」直接冲突，只能作最后兜底。")
    return 0


def cmd_capture(a):
    os.makedirs(a.out, exist_ok=True)
    backend, why = detect_backend()
    print(f"后端探测: {why}")

    manifest_path = os.path.join(a.out, "MANIFEST.json")
    if os.path.exists(manifest_path):
        with open(manifest_path, encoding="utf-8") as f:
            m = json.load(f)
    else:
        m = {"capture_environment": {k: "TODO" for k, _ in REQUIRED_ENV_FIELDS},
             "states": []}

    todo = [k for k, _ in REQUIRED_ENV_FIELDS
            if str(m.get("capture_environment", {}).get(k, "TODO")).upper() == "TODO"]
    if todo:
        print(f"\n❌ [S0] 环境契约有 {len(todo)} 项未固定: {', '.join(todo)}")
        print("   环境不固定 → 像素门禁会把**环境噪声误判为功能回退**。")
        print("   先跑 --init 填 MANIFEST.json，再采集。")
        return 1

    state_id = a.state or f"state__{time.strftime('%Y%m%d%H%M%S')}__0001"
    rec = {"state_id": state_id, "pid": a.pid, "backend": backend,
           "invasive": False, "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z")}

    if a.tree:
        if not backend:
            print("\n⚠️  [S0] 无可用 UIA 后端 —— 生成**待人工采集**占位，不假装成功")
            rec["tree"] = {"status": "pending_manual",
                           "reason": why,
                           "required_fields": TREE_FIELDS,
                           "tool_hint": "FlaUInspect / Inspect.exe / Accessibility Insights for Windows"}
        else:
            rec["tree"] = {"status": "collected", "backend": backend,
                           "fields": TREE_FIELDS,
                           "note": "建议再用另一后端交叉验证；不一致标 tree_conflict 并人工复核"}

    if a.shot:
        rec["shot"] = {
            "primitives": {k: {"status": "pending_manual", "why": v}
                           for k, v in CAPTURE_PRIMITIVES.items()},
            "determinism": "unknown",
            "note": "三类原语都要留：视觉主基线/布局基线/资源校验/屏幕对照",
        }
        print("\n⚠️  [S0] 截图需按三原语分别采集（本脚本只登记契约，不代替采集器）")

    m.setdefault("states", []).append(rec)
    m["invasive_evidence_separated"] = True
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(m, f, ensure_ascii=False, indent=2)

    print("=" * 64)
    print(f"已登记状态: {state_id} → {manifest_path}")
    print("=" * 64)
    print(f"  证据目录哈希: {sha256(manifest_path)}")
    print("\n⚠️ 侵入式证据（调试器/内存/注入/TTD）必须标 invasive=true")
    print("   且**不能与常规截图基线混放** —— 调试器扰动后的程序不是原版常态。")
    print("\n⚠️ 反编译与内存读取仅限**合法拥有且授权分析**的目标；")
    print("   ⚠️ 遇加密/DRM/许可证校验：ownership: self（自有项目）**不受此限**；")
    print("      仅 third_party 时才需停止确认。")
    return 0


def main():
    ap = argparse.ArgumentParser(description="原版证据采集（S0）")
    ap.add_argument("--pid", type=int, help="目标进程 ID")
    ap.add_argument("--out", default="original_capture")
    ap.add_argument("--state", help="state_id")
    ap.add_argument("--tree", action="store_true", help="导出控件树")
    ap.add_argument("--shot", action="store_true", help="确定性截图")
    ap.add_argument("--env", action="store_true", help="打印环境契约与定位优先级")
    ap.add_argument("--init", nargs="?", const=True, help="生成证据目录骨架")
    a = ap.parse_args()

    if a.init is not None and a.init is not True and isinstance(a.init, str):
        return cmd_init(a)
    if a.init is True:
        a.init = "original_capture"
        return cmd_init(a)
    if a.env:
        return cmd_env(a)
    if not (a.tree or a.shot):
        print("❌ 需要 --tree / --shot / --env / --init 之一")
        return 2
    return cmd_capture(a)


if __name__ == "__main__":
    sys.exit(main())
