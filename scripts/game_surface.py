#!/usr/bin/env python3
"""游戏"功能表面"穷尽（深化第三轮 A 类）—— **最容易整体遗忘的一层**。

**🔑 核心判断**：
> 复刻最大的"看着一样、玩着不对"风险，已从**核心循环扩散到高频外围系统**。
> 玩家每局都会遭遇：启动默认值、键鼠/手柄图标切换、暂停失焦、教程、
> 菜单 UI 恢复、本地化、任务对话、难度辅助、回放、统计、社交。
>
> **它们不在关卡数据里，也不在帧数据里，迁移时最容易被整体遗忘。**

**四层记录法**（每个功能表面都要有）：
`数据 schema` · `状态机` · `玩家轨迹` · `持久化副作用`

用法:
  game_surface.py --first-run      # 🔴 首次启动默认值（第一印象）
  game_surface.py --ui-restore     # 菜单 UI 状态恢复（低成本高可信）
  game_surface.py --input-prompt   # 输入提示图标切换（**真正的像素级细节**）
  game_surface.py --focus          # 暂停与失焦（**12 个正交维度**）
  game_surface.py --loc            # 本地化与可访问性
  game_surface.py --env            # 环境交互/可破坏物/昼夜天气
  game_surface.py --quest          # 任务/对话/背包/商店
  game_surface.py --meta           # 元游戏层（启动器/更新器/Overlay/社交）
  game_surface.py --init ledger/game_surface.csv
  game_surface.py --check ledger/game_surface.csv --gate

退出码: 0 通过 / 1 缺项 / 2 用法错误
"""
import argparse
import csv
import os
import sys

# 🔴 首次启动：**六条轨迹**
FIRST_RUN_TRACKS = [
    "全新用户",
    "同名但**旧配置**",
    "**旧版存档升级**",
    "**跨平台导入存档**",
    "**只读目录**",
    "首次选择语言/控制方案",
]

FIRST_RUN_FIELDS = [
    "默认画质档位", "帧率上限", "垂直同步", "分辨率", "窗口模式",
    "**各音频分轨**（主/音乐/音效/语音）", "字幕", "语言", "控制布局",
    "辅助模式", "相机灵敏度", "自动保存间隔", "网络区域", "图形 API",
    "**色盲模式**", "首次教程标志",
]

FIRST_RUN_RULE = [
    "🔑 判定规则：**首次运行观测值逐项等于基线**",
    "⚠️ **不得因「平台推荐默认值」而擅自替换**",
    "⚠️ 若原版默认值在不同**硬件档位**上分叉 → 记录**检测规则**，"
    "不是只记一个静态值",
]

# UI 状态恢复：**低成本、高可信度**
UI_RESTORE_FIELDS = [
    "光标所在按钮", "滚动偏移", "列表选择", "Tab 页", "折叠树",
    "排序方式", "筛选条件", "**搜索框文本**", "选中道具", "装备预览",
    "**确认弹窗焦点**", "虚拟键盘光标", "**弹窗栈**", "暂停/遮罩",
    "背景动画", "音频焦点", "当前导航路径", "**返回目标**",
]

UI_RESTORE_RULES = [
    "返回到**上次菜单**而非根菜单",
    "保留滚动位置**但清空搜索框**",
    "进入商店后光标移到**购买按钮**",
    "**二次确认默认取消**",
    "退出物品栏**保留当前装备预览**",
]

UI_RESTORE_METHOD = [
    "🔑 录制每一层 **push/pop 的完整焦点轨迹**，"
    "用事件日志 + 逐帧截图比对",
    "⚠️ 这些规则**不能由迁移后 UI 框架的默认行为决定**",
]

# 输入提示：**真正的像素级细节，不是美术资源问题**
INPUT_PROMPT_FIELDS = [
    "输入事件来源", "图标集合", "字符串表", "设备连接状态", "玩家插槽",
    "**最后输入设备**", "**提示更新时机**", "上下文优先级",
    "**切换防抖**", "首次输入阈值", "文本回退", "插拔事件",
    "设置是否覆盖自动识别",
]

INPUT_PROMPT_TESTS = [
    "仅键盘", "仅手柄", "**双设备**", "**拔线**", "睡眠唤醒",
    "**重连**", "电量变化", "**不同插槽**",
]

INPUT_PROMPT_RULES = [
    "⚠️ 设备热插拔后**不能把提示固定成首次检测设备**",
    "⚠️ **不能在每一帧重复弹出「设备切换」提示**",
    "🔑 不能肉眼比较「这张截图有没有手柄 A 键」 —— "
    "应断言**每帧/每个状态转移的图标 ID、文字 ID、是否显示、出现延迟、消失条件**",
]

# ABXY / Circle-Cross：**四类标识必须分开**
GLYPH_IDS = [
    ("physical_button", "物理键码"),
    ("action_semantic", "语义动作"),
    ("display_glyph", "显示图标"),
    ("display_label", "显示文字"),
    ("confirm_role", "确认角色"),
    ("cancel_role", "取消角色"),
    ("legacy_layout_override", "**原版布局覆盖**"),
]

GLYPH_NOTE = [
    "⚠️ Xbox 的 A=确认/B=取消 与 PlayStation 的 Circle=确认/Cross=取消"
    "**只是常见惯例，原版可能自行覆盖**",
    "⚠️ **不能把平台按钮标签硬编码**",
    "⚠️ 引擎框架默认映射**不能变成新基准** —— 要回到原版抓包/录屏事实",
]

# 暂停与失焦：**12 个正交维度**
FOCUS_DIMS = [
    "游戏逻辑时钟", "渲染帧", "动画", "粒子", "音频音乐", "音效", "语音",
    "震动", "**网络心跳**", "房间状态", "上传/下载", "着色器预热",
    "后台 CPU/GPU 节流", "**自动保存**", "通知弹窗", "输入缓冲",
    "光标可见性", "全屏独占",
]

FOCUS_RULES = [
    "🔴 **「按下 Start 暂停」与「Alt-Tab 暂停」可能是两个不同状态** —— "
    "**不能合并为布尔 `is_paused`**",
    "⚠️ 原版可能出现「暂停游戏但继续播放剧情语音」、"
    "「窗口失焦仍计时但手柄震动停止」、"
    "「Steam overlay 打开时冻结，系统菜单打开时不冻结」等不一致行为",
    "🔑 每项都要记录：进入条件 · 持续条件 · **恢复条件** · 边界",
]

# 本地化
LOC_TESTS = [
    "短词", "长复合词", "窄容器", "宽容器", "双行截断", "三行溢出",
    "空格换行", "连字", "**字体缺失字形**", "变体选择器", "零宽字符",
    "全角/半角", "数字", "日期", "时间", "货币", "百分比",
    "列表分隔符", "**排序规则**", "双向文本",
]

LOC_RULES = [
    "🔑 建立**伪本地化层**：文本扩张 + 非 ASCII + 稳定 key + 可回退 + 边界标记",
    "⚠️ 「德语比英语长 30%」**只能作测试用例之一**，"
    "**不是所有德语文本的固定膨胀系数**",
    "⚠️ **阿拉伯语/希伯来语不是简单「镜像 UI」** —— 字符串、数字、图标、"
    "控件方向共同变化",
    "⚠️ **字幕与配音是一条时间轴**，不是两套独立字符串表",
]

SUBTITLE_FIELDS = [
    "字幕开关", "字号", "背景", "区域", "安全区", "单行/双行上限",
    "说话人颜色", "语速", "自动推进", "静音", "**字幕延迟**",
    "语音提前结束", "语音晚于文本", "多语言配音切换", "未配音语言文本",
    "方言/粗口过滤", "**角色口型**", "表情触发",
]

# 环境交互：阶段 × 材质 × 交互
ENV_FIELDS = [
    "初始状态", "**分阶段转换**", "碎片实例数", "碎片网格/材质", "碎片速度",
    "碰撞衰减", "物理所有权", "可投掷", "可回收", "残骸寿命", "内存上限",
    "声音事件", "粒子", "贴花", "弹痕", "雪/沙/液体置换", "镜头震动",
    "性能降级", "跨场景保存", "**多人权威**",
]

WEATHER_FIELDS = [
    "时钟倍率", "时间原点", "昼夜曲线", "天空盒/光照参数", "雾", "后处理",
    "阴影", "云", "降水", "风力", "雷电", "洪水", "温度", "能见度",
    "**NPC 作息**", "**敌人生成**", "**AI 视野**", "声音传播", "水面反射",
    "室内外边界", "时间跳跃", "存档",
]

QUEST_FIELDS = [
    "任务状态机", "分支", "**失败条件**", "对话树", "语音触发",
    "奖励与副作用", "跨任务依赖", "可重复", "限时", "隐藏任务",
]

META_FIELDS = [
    "启动器", "**更新器**", "**模组管理器**", "崩溃报告", "反馈入口",
    "平台 Overlay", "云存档", "成就/统计", "好友/组队", "聊天/语音",
    "DLC/创意工坊", "商店", "订阅", "家长控制",
]

META_NOTE = [
    "🔑 玩家可能**通过启动器进入模组管理、从崩溃报告跳转反馈、"
    "由平台 Overlay 打开商店** —— 这些跨进程跳转也会改变",
    "   输入焦点、全屏状态、光标、音频和暂停规则",
    "⚠️ **不要默认「现代应用自动上传崩溃日志」** —— "
    "是否上传、上传哪些字段、是否可离线查看，**必须以原版行为为准**",
]

FIELDS = [
    ("item_id", "项编号"),
    ("domain", "域（first-run / ui-restore / input-prompt / focus / loc / env / quest / meta）"),
    ("legacy_value", "**原版值/轨迹**"),
    ("new_value", "新引擎值"),
    ("match", "**是否一致**"),
    ("persistence_side_effect", "持久化副作用"),
    ("evidence", "证据"),
]


def _hdr(t, w=80):
    print("=" * w)
    print(t)
    print("=" * w)


def cmd_first_run(a):
    _hdr("🔴 首次启动默认值（**决定玩家对原版的第一印象**）")
    print("\n六条轨迹:")
    for t in FIRST_RUN_TRACKS:
        print(f"   · {t}")
    print("\n字段:")
    for f in FIRST_RUN_FIELDS:
        print(f"   · {f}")
    print("\n规则:")
    for r in FIRST_RUN_RULE:
        print(f"   {r}")
    return 0


def cmd_ui_restore(a):
    _hdr("菜单 UI 状态恢复（**低成本、高可信度的 must-match**）")
    for f in UI_RESTORE_FIELDS:
        print(f"   · {f}")
    print("\n原版常见规则:")
    for r in UI_RESTORE_RULES:
        print(f"   · {r}")
    print("\n方法:")
    for m in UI_RESTORE_METHOD:
        print(f"   {m}")
    return 0


def cmd_input_prompt(a):
    _hdr("输入提示图标切换（🔴 **真正的像素级细节，不是美术资源问题**）")
    for f in INPUT_PROMPT_FIELDS:
        print(f"   · {f}")
    print("\n测试脚本（逐事件记录提示文本与图标索引）:")
    for t in INPUT_PROMPT_TESTS:
        print(f"   · {t}")
    print("\n四类标识必须分开:")
    for k, why in GLYPH_IDS:
        print(f"   {k:<26} {why}")
    print("\n规则:")
    for r in INPUT_PROMPT_RULES + GLYPH_NOTE:
        print(f"   {r}")
    return 0


def cmd_focus(a):
    _hdr("暂停与失焦（**12 个正交维度，不是布尔 is_paused**）")
    for d in FOCUS_DIMS:
        print(f"   · {d}")
    print("\n规则:")
    for r in FOCUS_RULES:
        print(f"   {r}")
    return 0


def cmd_loc(a):
    _hdr("本地化与可访问性（**按组合矩阵，不是单语言**）")
    print("每个语言至少覆盖:")
    for t in LOC_TESTS:
        print(f"   · {t}")
    print("\n字幕字段（**与配音是同一条时间轴**）:")
    for f in SUBTITLE_FIELDS:
        print(f"   · {f}")
    print("\n规则:")
    for r in LOC_RULES:
        print(f"   {r}")
    return 0


def cmd_env(a):
    _hdr("环境交互（**阶段 × 材质 × 交互** 三维）")
    print("可破坏物:")
    for f in ENV_FIELDS:
        print(f"   · {f}")
    print("\n昼夜与天气（**全局状态机，不是若干美术参数**）:")
    for f in WEATHER_FIELDS:
        print(f"   · {f}")
    print("\n⚠️ 「下雨使敌人视野降低」要记录受影响 AI、距离函数、视线衰减、")
    print("   音效遮挡和对玩家脚步的反馈 —— **不能只做视觉下雨**")
    return 0


def cmd_quest(a):
    _hdr("任务 / 对话 / 背包 / 商店（**状态机与副作用表，不是截图清单**）")
    for f in QUEST_FIELDS:
        print(f"   · {f}")
    print("\n🔑 用**状态机 + 副作用表**替代截图清单")
    return 0


def cmd_meta(a):
    _hdr("元游戏层（**是原版完整功能表面的一部分**）")
    for f in META_FIELDS:
        print(f"   · {f}")
    print("\n注意:")
    for n in META_NOTE:
        print(f"   {n}")
    return 0


def cmd_init(a):
    os.makedirs(os.path.dirname(a.init) or ".", exist_ok=True)
    with open(a.init, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow([k for k, _ in FIELDS])
        w.writerow(["TODO"] * len(FIELDS))
    print(f"已生成功能表面清单: {a.init}")
    print("\n⚠️ 八域：first-run / ui-restore / input-prompt / focus / "
          "loc / env / quest / meta")
    return 0


def cmd_check(a):
    if not os.path.exists(a.check):
        print(f"❌ 文件不存在: {a.check}")
        return 2
    with open(a.check, encoding="utf-8", errors="replace", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        print("❌ 空表 —— **功能表面未清点**")
        return 1

    def g(r, k):
        return (r.get(k) or "").strip()

    mismatch, no_side, no_legacy = [], [], []
    for i, r in enumerate(rows, 1):
        m = g(r, "match").lower()
        if m not in ("yes", "y", "true", "是", "一致"):
            mismatch.append(i)
        if not g(r, "persistence_side_effect") or \
                g(r, "persistence_side_effect") == "TODO":
            no_side.append(i)
        if not g(r, "legacy_value") or g(r, "legacy_value") == "TODO":
            no_legacy.append(i)

    print("=" * 76)
    print(f"功能表面 · {len(rows)} 条")
    print("=" * 76)
    if mismatch:
        print(f"\n🚫 **功能表面不一致** {len(mismatch)} 条（行 {mismatch[:15]}）")
        print("   → 缺失时不是「功能未实现」，而是玩家**立即感到不是同一个游戏**")
    if no_side:
        print(f"\n⚠️  {len(no_side)} 条未记**持久化副作用**（行 {no_side[:15]}）")
        print("   → 四层记录法：数据 schema / 状态机 / 玩家轨迹 / **持久化副作用**")
    if no_legacy:
        print(f"\n❌ {len(no_legacy)} 条缺**原版值/轨迹**（行 {no_legacy[:15]}）")

    if not (mismatch or no_legacy):
        print("\n✅ 功能表面一致且原版轨迹完整")

    print("\n🔑 **外围功能不是 polish，是 must-match 的一部分。**")
    print("   「先做核心、外围留待 polish」→ 外围常跨场景触发，后置会大量返工")
    return 1 if (a.gate and (mismatch or no_legacy)) else 0


def main():
    ap = argparse.ArgumentParser(description="游戏功能表面穷尽")
    ap.add_argument("--first-run", dest="first_run", action="store_true")
    ap.add_argument("--ui-restore", dest="ui_restore", action="store_true")
    ap.add_argument("--input-prompt", dest="input_prompt", action="store_true")
    ap.add_argument("--focus", action="store_true")
    ap.add_argument("--loc", action="store_true")
    ap.add_argument("--env", action="store_true")
    ap.add_argument("--quest", action="store_true")
    ap.add_argument("--meta", action="store_true")
    ap.add_argument("--init")
    ap.add_argument("--check")
    ap.add_argument("--gate", action="store_true")
    a = ap.parse_args()
    fns = {"first_run": cmd_first_run, "ui_restore": cmd_ui_restore,
           "input_prompt": cmd_input_prompt, "focus": cmd_focus, "loc": cmd_loc,
           "env": cmd_env, "quest": cmd_quest, "meta": cmd_meta}
    for k, fn in fns.items():
        if getattr(a, k):
            return fn(a)
    if a.init:
        return cmd_init(a)
    if a.check:
        return cmd_check(a)
    print("❌ 需要 --first-run / --ui-restore / --input-prompt / --focus / "
          "--loc / --env / --quest / --meta / --init / --check 之一")
    return 2


if __name__ == "__main__":
    sys.exit(main())
