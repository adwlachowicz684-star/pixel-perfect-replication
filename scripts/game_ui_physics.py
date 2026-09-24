#!/usr/bin/env python3
"""UI 系统深化 + 物理深化（第六轮 B / C 类）。

**🔑 B 类**：UI 从字符串到像素是**多层参数链**：
字体选择 → 整形 → 度量 → 图集/SDF → 布局 → 导航 → 滚动。
> **视觉相同可能来自完全不同的布局链和度量链。**

**🔑 C 类**：物理从脚本请求到接触响应：
层过滤 → 形状 → 材质合并 → 接触偏移 → 求解 → 子步 → 回放。
> **漏一层、错一个合并模式，就会穿墙、卡住或永远滑不下去。**

用法:
  game_ui_physics.py --layout      # 🔴 布局四层链（**不是最终 pixel rect**）
  game_ui_physics.py --safezone    # 安全区不是四周统一留白
  game_ui_physics.py --font        # 字体回退链 + **HarfBuzz 整形**
  game_ui_physics.py --richtext    # 富文本拆成 token 流
  game_ui_physics.py --uianim      # UI 动画（**同事件同值**）
  game_ui_physics.py --nav         # 🔴 导航是**显式图**，不是自动找最近
  game_ui_physics.py --scroll      # 滚动五个系统
  game_ui_physics.py --virtual     # 虚拟化回收
  game_ui_physics.py --matrix      # 🔴 碰撞层矩阵（**漏一层就穿墙**）
  game_ui_physics.py --material    # 🔴 摩擦/弹性**合并模式**
  game_ui_physics.py --contact     # 接触偏移**不是**碰撞 margin
  game_ui_physics.py --query       # 查询起点与分类
  game_ui_physics.py --trigger     # 触发器退出事件丢失
  game_ui_physics.py --ccd         # CCD 模式
  game_ui_physics.py --substep     # 子步与**螺旋死亡**
  game_ui_physics.py --init ledger/ui_physics.csv
  game_ui_physics.py --check ledger/ui_physics.csv --gate

退出码: 0 通过 / 1 缺项 / 2 用法错误
"""
import argparse
import csv
import os
import sys

# 布局四层链
LAYOUT_CHAIN = [
    "**锚点**（四个 anchor 与四个 offset）", "pivot",
    "父 Rect", "**DPI**", "**内容缩放**", "**安全区父级**",
]

LAYOUT_FIELDS = [
    "四锚点", "四偏移", "pivot", "local position/rotation/scale", "rect",
    "min/max size", "parent size delta", "layout group 优先级",
    "size fitter 行为", "**minimum size**", "Container 管理",
]

LAYOUT_RULE = [
    "🔑 **不能只保存最终 pixel rect** —— "
    "锚点改变后 PosX/PosY/Width/Height 的**参考会变化**",
]

SAFEZONE = [
    "逻辑分辨率", "参考 DPI", "实际 DPI", "**device profile**",
    "scale factor", "safe area 矩形", "TV title/action safe",
    "**cutout（刘海）**", "**home indicator**", "横竖屏",
    "设备方向锁定", "**safe zone 父级**", "子控件 scale",
    "letterbox 与裁切策略",
]

SAFEZONE_RULE = "🔑 **安全区不是屏幕四周的统一留白** —— UE Safe Zone 会缩放子控件"

# 字体
FONT_FIELDS = [
    "主字体 GUID/家族/样式/权重/字号/**度量**", "图集页", "glyph",
    "kerning", "**fallback 顺序**（按列表顺序**递归**）", "OS/引擎回退",
    "动态生成", "**missing glyph 策略**", "粗体扩散", "斜体偏移",
    "CJK 标点压缩", "数字宽度", "分数与上下标", "emoji 色/黑白",
    "连字", "ordinal/lining tabular", "**variation selector**",
]

FONT_RULE = [
    "🔑 **HarfBuzz 整形和像素度量决定文本长度，SDF 只决定栅格化质量**",
    "⚠️ 同一字符串在 TMP / UMG / Godot 中的**光标、字符索引、自动换行、"
    "省略号和点击命中可能不同**",
    "🔑 应保存：整形日志 · **UTF-16 代码单元索引** · 字节索引 · glyph run · "
    "双向级别 · 每字形 advance",
    "⚠️ Godot fallback text server 仅支持简单 LTR 布局 —— "
    "advanced 才支持 HarfBuzz/ICU/MSDF",
]

RICHTEXT = [
    "标签解析顺序", "嵌套", "颜色 alpha", "gradient", "阴影/描边",
    "size 相对基准", "sprite emoji", "超链接", "material override",
    "line spacing", "paragraph spacing", "word/character spacing", "tab",
    "alignment", "horizontal overflow", "vertical overflow", "max lines",
    "**truncation mode**", "auto size min/max", "wrapping test width",
    "justification", "ruby/furigana", "BiDi", "**换行规则**",
    "emoji ZWJ", "变体选择符",
]

# UI 动画
UIANIM = [
    "timeline", "duration", "delay", "start/end value", "easing curve",
    "overshoot", "ping-pong", "repeat", "play rate", "time scale",
    "**frame / unscaled time**", "independent update", "realtime", "scrub",
    "skip on skip current", "**中断策略**", "rewind/hold/complete",
    "layout dirty", "canvas rebuild",
]

UIANIM_EDGE = [
    "页面打开是否**等入场动画完成才接受输入**",
    "取消返回时动画是否**反向**",
    "快速连点是否**排队**",
    "**失焦是否 pause**",
    "极低帧率下是否**超时跳过**",
]

UIANIM_RULE = "🔑 must-match 是「**同一触发事件下，同一属性在同一逻辑时间有同一值**」，"
"不是「都有缓动」"

# 🔴 导航是显式图
NAV_MODES = [
    ("Escape", "继续按方向寻找"),
    ("Explicit", "指向指定控件"),
    ("Wrap", "容器边界循环"),
    ("Stop", "阻断"),
    ("Custom / CustomBoundary", "交代码处理"),
]

NAV_FIELDS = [
    "**完整导航图**：每个控件在上下左右、Tab/Shift-Tab、LRUD 与手柄方向下的目标",
    "容器边界", "**首次默认焦点**", "**返回页保留焦点**", "历史栈",
    "显式目标命名", "wrap", "焦点记忆", "**滚动跟随**", "方向优先级",
]

NAV_RULE = "🔴 **手柄导航不是「自动找最近」** —— 是 Escape/Explicit/Wrap/Stop/Custom 的图"

# 滚动五个系统
SCROLL_SYSTEMS = [
    "**阻尼**（scroll_damping_factor）", "**死区**（scroll_deadzone）",
    "**吸附 snap**", "**回弹**（elasticity / overscroll threshold）",
    "**聚焦跟随**（follow_focus）",
]

SCROLL_INPUTS = [
    "鼠标轮", "触控拖拽", "手柄摇杆", "Page Up/Down", "Home/End", "箭头键",
]

SCROLL_FIELDS = [
    "scroll amount", "惯性曲线", "friction/deceleration", "elasticity",
    "overscroll threshold", "snap 对齐/容差/速度阈值",
    "滚动条可见性/可点击/可拖/最小 thumb/inset",
    "**focused child 居中还是只保证可见**", "滚动动画是否受 timescale",
]

VIRTUAL_FIELDS = [
    "item 高度固定/动态", "**预估高度**", "预取前后 item 数", "recycle 池",
    "bind/unbind", "content size change", "anchor item", "异步生成",
    "加载占位", "selection 持久化", "**排序/filter 时 scroll offset 修复**",
]

VIRTUAL_TRAP = [
    "🔴 回收 item 若**只重设文本**，不重置字体回退、富文本、尺寸约束和动画 → "
    "产生「**滚动后才变对**」的体验 bug",
]

# 🔴 碰撞层矩阵
MATRIX_FIELDS = [
    "**32/64 层 bitmask**", "layer name", "project preset",
    "static/dynamic/kinematic/trigger", "**查询 mask**",
    "ignore layer collisions runtime", "scene-specific override",
    "object override", "Broadphase filter", "custom dispatcher",
    "**query vs simulation 是否共用**",
]

MATRIX_TESTS = [
    "玩家—地形", "子弹—伤害区", "摄像机—可见", "武器—判定",
    "载具—可站立", "射线—可瞄准", "AI—听觉", "触发器—剧情",
    "debris—debris", "cloth—body", "ragdoll—world",
]

MATRIX_RULE = "🔴 **必须逐游戏层、逐查询层、逐预设保存**，不是抄一张总表 —— "
"**漏一层就是穿墙或卡住**"

# 🔴 合并模式
MATERIAL_COMBINE = [
    "🔑 **摩擦与弹性合并模式是成对的两套算法**",
    "字段：static/dynamic friction · restitution · "
    "**friction_combine_mode** · **restitution_combine_mode** · "
    "friction direction · anisotropic friction · rest offset · "
    "contact offset · surface type · physical material switch · "
    "per-triangle material",
    "常见模式：Average / Min / Max / Multiply",
    "🔴 **只有「两个表面相遇」才有合并结果** —— "
    "玩家胶囊贴地形与车辆轮子贴路面可能用**不同材质组合**，必须分别设计实验",
]

# 接触偏移
CONTACT_FIELDS = [
    "**contact_offset_multiplier**（以包围体最小维度计算）",
    "min_contact_offset", "max_contact_offset", "shape margin",
    "CCD", "speculative contact", "adaptive force", "max depenetration",
    "position/velocity iterations", "joint iterations", "sleep threshold",
    "solver type", "PGS/GS/SI", "baumgarte", "shock propagation",
    "contact mass scaling", "warm starting", "persistent contact manifold",
    "**enhanced determinism**",
]

CONTACT_RULE = [
    "🔑 **接触偏移不是碰撞 margin 的同义词**",
    "⚠️ 乘数值越大 → 越早生成接触、稳定性更高，但**性能成本增加**",
]

QUERY_FIELDS = [
    "起点", "方向", "距离", "半径", "layer", "mask", "trigger include",
    "hit normal/tangent", "**multi hit 顺序**", "backface",
    "query 在 update 的哪一段执行", "是否 read consistent state",
    "是否 parallel", "physics scene", "async scene", "filter callback",
]

QUERY_KINDS = [
    "raycast", "sphere/box/capsule cast", "sweep", "overlap",
    "shape test", "broadphase only",
]

QUERY_EDGE = [
    "起点在碰撞体内", "距离 0", "几乎平行表面", "backface", "two-sided",
    "**sub-step 边界**", "连续碰撞", "query 与 simulation 并行",
]

TRIGGER_RULE = [
    "🔑 触发器通常不参与接触阻力，但**事件顺序、重叠计数、enable/disable 时刻、"
    "FixedUpdate、scene change、sleep、teleport** 都可能造成 `OnTriggerExit` 丢失",
    "❌ **不要用每帧 overlap 查询直接替代退出事件** —— "
    "对象被回收、销毁或跨场景时语义不同",
]

CCD_MODES = [
    "Discrete", "**Sweep-based**", "Continuous", "**Speculative**",
]

CCD_FIELDS = [
    "最小时间步", "axis-aligned bound 扩展", "skin width",
    "rotation threshold", "mesh CCD", "depenetration velocity clamp",
    "maximum speed",
]

CCD_RULE = [
    "🔑 重点：薄墙 · 低角度斜坡 · 长杆 · 快速旋转 · 缩放网格 · 睡眠物体",
    "🔴 若目标引擎**只支持 sweep 不支持 speculative** → "
    "必须在偏离清单中列为**玩法级变化**",
]

SUBSTEP_FIELDS = [
    "**substepping**", "**max_substep_delta_time**",
    "**min_physics_delta_time**", "**max_physics_delta_time**",
    "fixed delta", "maximum substeps", "accumulator", "**catch-up clamp**",
    "variable/fixed/semi-fixed", "physics tick phase", "interpolation",
    "query phase", "threading", "time scale", "pause", "slow motion",
    "max allowed timestep", "**spiral of death guard**",
]

SUBSTEP_TESTS = [
    "30 / 60 / 120 / 144 Hz", "卡顿一帧", "最小 delta", "最大 delta",
    "**pause 后恢复**",
]

SUBSTEP_DET = [
    "确定性项目还要：固定种子 · **容器顺序** · 并行调度 · "
    "**增强确定性** · 浮点/数学一致性",
]

FIELDS = [
    ("item_id", "项编号"),
    ("domain", "域（layout / font / uianim / nav / scroll / matrix / material / contact / query / trigger / ccd / substep）"),
    ("legacy_value", "**原版值**"),
    ("new_value", "新引擎值"),
    ("match", "**是否一致**"),
    ("evidence", "证据"),
]


def _hdr(t, w=80):
    print("=" * w)
    print(t)
    print("=" * w)


def cmd_layout(a):
    _hdr("🔴 UI 布局四层链（**不是最终 pixel rect**）")
    print("链路: " + " · ".join(LAYOUT_CHAIN))
    print("\n必存字段: " + " · ".join(LAYOUT_FIELDS))
    print("\n规则:")
    for r in LAYOUT_RULE:
        print(f"   {r}")
    print("\n安全区: " + " · ".join(SAFEZONE))
    print(f"\n{SAFEZONE_RULE}")
    return 0


def cmd_safezone(a):
    _hdr("安全区")
    for f in SAFEZONE:
        print(f"   · {f}")
    print(f"\n{SAFEZONE_RULE}")
    print("⚠️ device profile 还会改变最终分辨率与 Mobile Content Scale Factor")
    return 0


def cmd_font(a):
    _hdr("字体回退链 + HarfBuzz 整形")
    for f in FONT_FIELDS:
        print(f"   · {f}")
    print("\n规则:")
    for r in FONT_RULE:
        print(f"   {r}")
    return 0


def cmd_richtext(a):
    _hdr("富文本（**拆成 token 流**）")
    for f in RICHTEXT:
        print(f"   · {f}")
    print("\n🔑 应拆成 token 流，而不是保存渲染后的字符串")
    return 0


def cmd_uianim(a):
    _hdr("UI 动画（**同事件同值**）")
    for f in UIANIM:
        print(f"   · {f}")
    print("\n边界:")
    for e in UIANIM_EDGE:
        print(f"   · {e}")
    print(f"\n🔑 {UIANIM_RULE}")
    return 0


def cmd_nav(a):
    _hdr("🔴 导航（**是显式图，不是自动找最近**）")
    for k, why in NAV_MODES:
        print(f"   {k:<24} {why}")
    print("\n必存:")
    for f in NAV_FIELDS:
        print(f"   · {f}")
    print(f"\n{NAV_RULE}")
    print("⚠️ Unity `Navigation.Mode`：None / Horizontal / Vertical / "
          "Automatic / Explicit")
    return 0


def cmd_scroll(a):
    _hdr("滚动五个系统")
    for s in SCROLL_SYSTEMS:
        print(f"   · {s}")
    print("\n输入: " + " · ".join(SCROLL_INPUTS))
    print("\n字段: " + " · ".join(SCROLL_FIELDS))
    return 0


def cmd_virtual(a):
    _hdr("滚动虚拟化")
    for f in VIRTUAL_FIELDS:
        print(f"   · {f}")
    print("\n陷阱:")
    for t in VIRTUAL_TRAP:
        print(f"   {t}")
    return 0


def cmd_matrix(a):
    _hdr("🔴 碰撞层矩阵（**漏一层就穿墙**）")
    for f in MATRIX_FIELDS:
        print(f"   · {f}")
    print("\n测试矩阵: " + " · ".join(MATRIX_TESTS))
    print(f"\n{MATRIX_RULE}")
    return 0


def cmd_material(a):
    _hdr("🔴 物理材质与合并模式")
    for m in MATERIAL_COMBINE:
        print(f"   {m}")
    return 0


def cmd_contact(a):
    _hdr("接触偏移（**不是碰撞 margin**）")
    for f in CONTACT_FIELDS:
        print(f"   · {f}")
    print("\n规则:")
    for r in CONTACT_RULE:
        print(f"   {r}")
    return 0


def cmd_query(a):
    _hdr("查询（**起点与分类**）")
    print("类型: " + " · ".join(QUERY_KINDS))
    print("\n字段: " + " · ".join(QUERY_FIELDS))
    print("\n边界:")
    for e in QUERY_EDGE:
        print(f"   · {e}")
    return 0


def cmd_trigger(a):
    _hdr("触发器（**退出事件丢失**）")
    for r in TRIGGER_RULE:
        print(f"   {r}")
    return 0


def cmd_ccd(a):
    _hdr("CCD")
    print("模式: " + " · ".join(CCD_MODES))
    print("\n字段: " + " · ".join(CCD_FIELDS))
    print("\n规则:")
    for r in CCD_RULE:
        print(f"   {r}")
    return 0


def cmd_substep(a):
    _hdr("子步与螺旋死亡")
    for f in SUBSTEP_FIELDS:
        print(f"   · {f}")
    print("\n回归: " + " · ".join(SUBSTEP_TESTS))
    print("\n确定性:")
    for d in SUBSTEP_DET:
        print(f"   {d}")
    return 0


def cmd_init(a):
    os.makedirs(os.path.dirname(a.init) or ".", exist_ok=True)
    with open(a.init, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow([k for k, _ in FIELDS])
        w.writerow(["TODO"] * len(FIELDS))
    print(f"已生成 UI/物理表: {a.init}")
    print("\n⚠️ 十二域：layout / font / uianim / nav / scroll / matrix / "
          "material / contact / query / trigger / ccd / substep")
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

    mismatch, no_legacy = [], []
    for i, r in enumerate(rows, 1):
        m = g(r, "match").lower()
        if m not in ("yes", "y", "true", "是", "一致"):
            mismatch.append(i)
        if not g(r, "legacy_value") or g(r, "legacy_value") == "TODO":
            no_legacy.append(i)

    print("=" * 76)
    print(f"UI/物理 · {len(rows)} 条")
    print("=" * 76)
    if mismatch:
        print(f"\n🚫 **不一致** {len(mismatch)} 条（行 {mismatch[:15]}）")
        print("   → UI 与物理都是「漏一项即变手感」的参数链")
    if no_legacy:
        print(f"\n❌ {len(no_legacy)} 条缺**原版值**（行 {no_legacy[:15]}）")

    if not (mismatch or no_legacy):
        print("\n✅ UI/物理：一致且原版值完整")

    print("\n🔑 **UI：视觉相同可能来自完全不同的布局链和度量链。**")
    print("   **物理：漏一层、错一个合并模式，就会穿墙、卡住或永远滑不下去。**")
    return 1 if (a.gate and (mismatch or no_legacy)) else 0


def main():
    ap = argparse.ArgumentParser(description="UI 与物理深化")
    ap.add_argument("--layout", action="store_true")
    ap.add_argument("--safezone", action="store_true")
    ap.add_argument("--font", action="store_true")
    ap.add_argument("--richtext", action="store_true")
    ap.add_argument("--uianim", action="store_true")
    ap.add_argument("--nav", action="store_true")
    ap.add_argument("--scroll", action="store_true")
    ap.add_argument("--virtual", action="store_true")
    ap.add_argument("--matrix", action="store_true")
    ap.add_argument("--material", action="store_true")
    ap.add_argument("--contact", action="store_true")
    ap.add_argument("--query", action="store_true")
    ap.add_argument("--trigger", action="store_true")
    ap.add_argument("--ccd", action="store_true")
    ap.add_argument("--substep", action="store_true")
    ap.add_argument("--init")
    ap.add_argument("--check")
    ap.add_argument("--gate", action="store_true")
    a = ap.parse_args()
    fns = {"layout": cmd_layout, "safezone": cmd_safezone, "font": cmd_font,
           "richtext": cmd_richtext, "uianim": cmd_uianim, "nav": cmd_nav,
           "scroll": cmd_scroll, "virtual": cmd_virtual, "matrix": cmd_matrix,
           "material": cmd_material, "contact": cmd_contact, "query": cmd_query,
           "trigger": cmd_trigger, "ccd": cmd_ccd, "substep": cmd_substep}
    for k, fn in fns.items():
        if getattr(a, k):
            return fn(a)
    if a.init:
        return cmd_init(a)
    if a.check:
        return cmd_check(a)
    print("❌ 需要 --layout / --safezone / --font / --richtext / --uianim / "
          "--nav / --scroll / --virtual / --matrix / --material / --contact / "
          "--query / --trigger / --ccd / --substep / --init / --check 之一")
    return 2


if __name__ == "__main__":
    sys.exit(main())
