#!/usr/bin/env python3
"""辅助功能与输入法（第十一轮 C 类）—— **IME 是我们完全空白的一块**。

**🔑 两条核心认知**：
1. **NVDA 的价值在朗读事件序；AccessKit 的价值在可比较的辅助树。**
   ⚠️ **"aria 快照无错误"不等于可访问性复刻完成。**
2. **中文/日文输入法是最容易让"像素复刻"失败的隐藏交互层。**
   **验收单位是"可观察状态序"，不是"最终汉字相同"。**

用法:
  a11y_ime.py --ime                       # IME 全事件录制（**最重要**）
  a11y_ime.py --ime-schema                # IME 事件字段 schema
  a11y_ime.py --screen-reader             # 屏幕阅读器基线
  a11y_ime.py --tree                      # 辅助树（AccessKit 中立桥接）
  a11y_ime.py --contrast                  # 强制颜色/对比度/动效/文本缩放
  a11y_ime.py --keyboard                  # 键盘与输入法联合测试
  a11y_ime.py --init ledger/a11y_matrix.csv
  a11y_ime.py --check ledger/a11y_matrix.csv --gate

退出码: 0 通过 / 1 缺项 / 2 用法错误
"""
import argparse
import csv
import os
import sys

# IME 全事件序列（**每项都要录**）
IME_EVENTS = [
    "焦点进入编辑控件",
    "`compositionstart`",
    "每次按键后的 `compositionupdate` / `input` / `textInput`",
    "**候选窗口弹出、移动、翻页、横排/竖排、数量变化**",
    "候选选择",
    "`compositionend`",
    "最终 `input`",
    "光标位置",
    "删除 / 方向键",
    "**Esc 取消**",
    "**Enter 确认**",
    "标点符号模式",
    "**全角/半角**",
    "**简繁转换**",
    "直接输入与转换混用",
    "**焦点切换时未确认 preedit 的提交或丢弃**",
    "窗口失焦、多显示器、远程桌面、不同 DPI、不同 WebView 版本",
]

# IME 事件 schema
IME_SCHEMA = [
    ("before_value", "变更前的值"),
    ("composition_text", "**组合文本**（preedit）"),
    ("pending_commit", "待提交"),
    ("selected_candidate_index", "候选索引"),
    ("candidate_page", "候选页"),
    ("cursor_offset", "光标偏移"),
    ("focus_id", "焦点标识"),
    ("editing_rect", "编辑区矩形"),
    ("composition_rect", "**组合区矩形**"),
    ("candidate_rect", "**候选窗口矩形**"),
    ("action", "动作"),
]

IME_RULES = [
    "⚠️ React 须区分**受控值、合成字符串、最终值**",
    "⚠️ `onChange` **不得用最终值覆盖 `inputType`**",
    "⚠️ 输入框**不得把组合文本拆成多份**",
    "⚠️ 粘贴、撤销、输入法、**语音输入**共存时不得破坏受控状态",
    "⚠️ 通过 CDP/DevTools Protocol 事件或注入探针记录事件序列 —— "
    "**不依赖「看起来已经上屏」**",
    "⚠️ 候选窗口若遮挡输入区 → 验自动滚动、视口避让、多显示器边界、"
    "DPI 缩放、窗口最小化恢复",
    "⚠️ 系统候选 UI 不可控时，记录平台与 WebView 版本，"
    "并至少证明**原版行为与目标事件序无回归**",
    "⚠️ **目标不得只在单语 Windows 11 默认输入法下通过**",
]

SCREEN_READER = [
    ("固定项", "Windows 显示语言、TTS、语速、NVDA 版本、浏览器/WebView 版本、区域、**输入法**"),
    ("导出", "开启 **Speech Viewer** 后导出文本流"),
    ("结构化注释", "焦点、实时区域、对话框、表格索引、错误摘要、列表项计数"),
    ("归一化", "合并重复空格、忽略时间戳、**动态数值放占位符**、保留角色/状态 token"),
]

SR_ASSERTIONS = [
    "首次聚焦朗读", "状态变化朗读", "插入/删除项", "错误关联",
    "对话框标题", "模态焦点捕获", "焦点返回", "**实时日志是否打断输入**",
]

# 辅助树：AccessKit 作中立桥接
AT_TREE_MAP = [
    ("WPF UIA", "AutomationId、Name、ControlType、LocalizedControlType、Value、"
                "IsEnabled、HasKeyboardFocus"),
    ("Patterns", "ExpandCollapse / Scroll / Selection / Table / Grid pattern"),
    ("几何与文本", "位置、大小、文本范围、控件视图与内容视图"),
    ("AccessKit", "整数 ID + role + 可选属性；**Rust 是模式的规范定义**"),
    ("映射目标", "Windows AT-SPI 桥、Web AOM、Tauri WebView 可访问对象"),
]

AT_FIELDS = ["legacy_role", "missing_equivalent"]

CONTRAST_MOTION = [
    "Windows **高对比度主题**",
    "Chromium/WebView **forced-colors**",
    "标准深色/浅色",
    "用户色覆盖",
    "系统动画开关 / Reduce Animations",
    "**prefers-reduced-motion**",
    "**prefers-contrast**",
    "页面缩放 / 仅放大文本",
    "**最低 200% 文本缩放**",
    "窄窗口重排",
]

CONTRAST_CHECKS = [
    "颜色替换是否**破坏状态指示**",
    "边框是否消失",
    "**图标是否只剩颜色**",
    "过渡是否会**留在半透明态**",
    "缩放是否截断按钮",
    "长标签是否改变布局",
    "窗口尺寸是否回到原位置",
]

KEYBOARD_SCENARIOS = [
    "Tab / Shift-Tab 顺序", "**visible focus**", "Roving Tabindex",
    "箭头导航", "Home/End", "Page Up/Down", "Esc", "Enter", "Space",
    "修饰键", "**快捷键冲突**",
    "**IME 下 Enter 与候选确认**", "**Esc 取消组合**", "**方向键选候选**",
    "Caps Lock", "Num Lock",
    "**Sticky Keys / Filter Keys / Toggle Keys / Mouse Keys**",
    "开关控制", "语音输入",
]

KEYBOARD_NOTE = [
    "⚠️ 若原版在 IME 开启时快捷键失效 → 这是**行为基线而非缺陷**，"
    "目标应保留并在 `keyboard-legacy.md` 注明。",
    "⚠️ 远程桌面、屏幕键盘、眼动、开关访问、语音输入必须进入 C 级基线 —— "
    "它们会显著改变焦点、候选窗口、文本组合、滚动、可见性和确认方式。",
]

FIELDS = [
    ("item_id", "项编号"),
    ("category", "类别（screen-reader / at-tree / ime / keyboard / contrast / zoom）"),
    ("legacy_trace", "**原版轨迹**（事件序，不是结论）"),
    ("new_trace", "目标轨迹"),
    ("platform_matrix", "平台/AT/IME 版本矩阵"),
    ("equivalence_verdict", "等价判定"),
    ("evidence", "证据（**必须保留原始 trace**）"),
]

# 🔑 第五十六轮新增：**白名单枚举**（黑名单式校验拦不住"填错的值"）
VERDICT_ENUM = (
    "equivalent", "equivalent_with_note", "deliberate_deviation",
    "assisted_only", "not_equivalent", "unknown", "unverified",
    "待填", "TODO", "—",
)


def cmd_ime(a):
    print("=" * 78)
    print("IME 全事件录制（🔴 **最容易让「像素复刻」失败的隐藏交互层**）")
    print("=" * 78)
    for i, e in enumerate(IME_EVENTS, 1):
        print(f"   {i:>2}. {e}")
    print("\n⚠️ 每项记录候选窗口相对**光标、输入框、滚动容器、窗口边界**的位置。")
    print("\n🔑 **验收单位是「可观察状态序」，不是「最终汉字相同」。**")
    print("\n规则:")
    for r in IME_RULES:
        print(f"   {r}")
    return 0


def cmd_ime_schema(a):
    print("=" * 74)
    print("IME 事件字段 schema")
    print("=" * 74)
    for k, why in IME_SCHEMA:
        print(f"   {k:<28} {why}")
    return 0


def cmd_screen_reader(a):
    print("=" * 78)
    print("屏幕阅读器基线（**NVDA 的价值在朗读事件序**）")
    print("=" * 78)
    for k, why in SCREEN_READER:
        print(f"\n   【{k}】")
        print(f"      {why}")
    print("\n断言项:")
    for s in SR_ASSERTIONS:
        print(f"   · {s}")
    print("\n⚠️ **朗读对比必须保留原始 trace，不能只留「通过/不通过」。**")
    print("⚠️ **不应把「aria 快照无错误」当作可访问性复刻完成。**")
    print("⚠️ VoiceOver / Orca / Narrator / JAWS 进**季度手工基线池** ——")
    print("   它们的版本差异本身就是证据，不要求一次测试覆盖所有平台。")
    return 0


def cmd_tree(a):
    print("=" * 78)
    print("辅助树（**AccessKit 作中立桥接**）")
    print("=" * 78)
    for k, why in AT_TREE_MAP:
        print(f"\n   【{k}】")
        print(f"      {why}")
    print(f"\n新增字段: " + " · ".join(AT_FIELDS))
    print("\n⚠️ 原版若「文字不标准但读得对」（靠相邻文本被朗读），")
    print("   目标**不能复制「裸 div」** —— 应补 `aria-label`/`aria-labelledby`/`role`")
    print("   与可见标签，并在 NVDA trace 中**证明结果等价**。")
    print("\n⚠️ AccessKit **不替代真实屏幕阅读器**。")
    return 0


def cmd_contrast(a):
    print("=" * 76)
    print("强制颜色 / 对比度 / 动效 / 文本缩放（**不能只测 CSS 开关**）")
    print("=" * 76)
    for c in CONTRAST_MOTION:
        print(f"   · {c}")
    print("\n像素与语义都要测:")
    for c in CONTRAST_CHECKS:
        print(f"   · {c}")
    print("\n⚠️ Playwright/像素比对负责**外观**，axe/AccessKit 快照负责**语义** ——")
    print("   **两者缺一不可**。")
    return 0


def cmd_keyboard(a):
    print("=" * 76)
    print("键盘与输入法**联合**测试")
    print("=" * 76)
    for s in KEYBOARD_SCENARIOS:
        print(f"   · {s}")
    print("\n⚠️ 先读原版**焦点轨迹**，再对目标录可访问树节点与按键事件；")
    print("   两者按窗口/对话框归一化为**有序 token 序列**。")
    print("")
    for n in KEYBOARD_NOTE:
        print(f"   {n}")
    return 0


def cmd_init(a):
    os.makedirs(os.path.dirname(a.init) or ".", exist_ok=True)
    with open(a.init, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow([k for k, _ in FIELDS])
        w.writerow(["TODO"] * len(FIELDS))
    print(f"已生成无障碍矩阵: {a.init}")
    print("\n⚠️ 六类：screen-reader / at-tree / **ime** / keyboard / contrast / zoom")
    print("   ⚠️ 目标栈测试**不能省略 Windows 中文/日文输入法和 NVDA**；")
    print("   浏览器 VoiceOver 只能补充不能替代。")
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

    no_legacy_trace, no_matrix, no_verdict, missing = [], [], [], []
    bad_verdict = []   # 🔑 第五十六轮新增：非法枚举值
    # 🔑 第五十八轮新增：**跨字段一致性**（语法合法 ≠ 语义正确）
    contradict = []
    for i, r in enumerate(rows, 1):
        if not g(r, "legacy_trace") or g(r, "legacy_trace") == "TODO":
            no_legacy_trace.append(i)
        if not g(r, "platform_matrix") or g(r, "platform_matrix") == "TODO":
            no_matrix.append(i)
        v = g(r, "equivalence_verdict")
        if not v or v in ("TODO", "待填", "—"):
            no_verdict.append(i)
        elif v not in VERDICT_ENUM:
            # 🔴 第五十六轮混沌测试发现：只查"空值/TODO"是**黑名单式**，
            # 填任意非法值（如 __poison__）会静默通过。
            bad_verdict.append((i, v))
        else:
            # 🔑 第五十八轮：**语义矛盾检测**
            #    每个字段都合法，但整行在说谎——这才是最危险的错误形态。
            lt, nt = g(r, "legacy_trace"), g(r, "new_trace")
            if lt and nt and lt != nt and v in ("equivalent", "equivalent_with_note"):
                contradict.append((i, v, lt, nt))
        miss = [k for k, _ in FIELDS
                if not g(r, k) or g(r, k) in ("TODO", "待填", "—")]
        if miss:
            missing.append((i, miss))

    print("=" * 74)
    print(f"无障碍矩阵 · {len(rows)} 条")
    print("=" * 74)
    if no_legacy_trace:
        print(f"\n❌ {len(no_legacy_trace)} 条缺**原版轨迹**（行 {no_legacy_trace[:15]}）")
        print("   → 必须是**事件序**，不是结论")
    if no_matrix:
        print(f"\n❌ {len(no_matrix)} 条缺平台/AT/IME 版本矩阵")
    if bad_verdict:
        print("\n🚫 **equivalence_verdict 含非法枚举值**"
              "（🔑 只查空值是**黑名单式**，填错值会静默通过）:")
        for i, v in bad_verdict[:12]:
            print(f"   行 {i}: `{v}`")
        print(f"   合法值: {', '.join(VERDICT_ENUM[:7])} …")
    if contradict:
        print("\n🚫 **跨字段语义矛盾**（🔑 每个字段都合法，但整行在说谎）:")
        for i, v, lt, nt in contradict[:12]:
            print(f"   行 {i}: verdict=`{v}` 但 legacy=`{lt}` ≠ new=`{nt}`")
        print("   🔴 白名单校验只能证明**值合法**，不能证明**行自洽**。")
        print("   🔑 这正是第五十八轮 semantic 毒化暴露的盲区。")
    if no_verdict:
        print(f"\n⚠️ {len(no_verdict)} 条等价判定未填")
    if missing:
        print(f"\n⚠️ {len(missing)} 条字段不全")

    if not (no_legacy_trace or no_matrix):
        print("\n✅ 无障碍矩阵原版轨迹与平台矩阵齐全")

    print("\n🔑 **「aria 快照无错误」≠ 可访问性复刻完成。**")
    print("   **「最终汉字相同」≠ IME 复刻完成。**")
    # 🔑 第五十六轮：非法枚举值也须阻断（原来只拦空值/TODO）
    # 🔑 第五十八轮：语义矛盾也须阻断
    return 1 if (a.gate and (no_legacy_trace or no_matrix or bad_verdict
                            or contradict)) else 0


def main():
    ap = argparse.ArgumentParser(description="辅助功能与输入法")
    ap.add_argument("--ime", action="store_true")
    ap.add_argument("--ime-schema", dest="ime_schema", action="store_true")
    ap.add_argument("--screen-reader", dest="screen_reader", action="store_true")
    ap.add_argument("--tree", action="store_true")
    ap.add_argument("--contrast", action="store_true")
    ap.add_argument("--keyboard", action="store_true")
    ap.add_argument("--init")
    ap.add_argument("--check")
    ap.add_argument("--gate", action="store_true")
    a = ap.parse_args()
    if a.ime:
        return cmd_ime(a)
    if a.ime_schema:
        return cmd_ime_schema(a)
    if a.screen_reader:
        return cmd_screen_reader(a)
    if a.tree:
        return cmd_tree(a)
    if a.contrast:
        return cmd_contrast(a)
    if a.keyboard:
        return cmd_keyboard(a)
    if a.init:
        return cmd_init(a)
    if a.check:
        return cmd_check(a)
    print("❌ 需要 --ime / --ime-schema / --screen-reader / --tree / "
          "--contrast / --keyboard / --init / --check 之一")
    return 2


if __name__ == "__main__":
    sys.exit(main())
