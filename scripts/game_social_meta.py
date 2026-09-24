#!/usr/bin/env python3
"""玩家表达与社交 + 元游戏 + 反馈仲裁 + 无障碍 + 浮点确定性（第十轮 A/D/E/F/G）。

**🔑 A 类核心**：
> 真正的差异**不是有没有 ping**，而是：
> **谁能在同一坐标再次 ping** · 聚合后显示什么 ·
> 消失是距离、超时、覆盖、超过上限还是新消息

**🔑 D 类核心**：
> 周目是否**同时改变**敌人配置、商店池、结局标志与隐藏判定。

**🔑 E 类核心**：
> 本质是"**同一时刻多个系统都想占据玩家注意力**"的仲裁层。

**🔑 G 类核心**：
> 确定性必须**下沉到编译和序列化层**，
> 不能只靠"固定种子"或"使用确定性库"。

用法:
  game_social_meta.py --expression  # 表达五层（语义/输入/网络/表现/审核）
  game_social_meta.py --ping        # 🔴 ping 的聚合与消失规则
  game_social_meta.py --party       # 队伍是**带生命周期的状态机**
  game_social_meta.py --ugc         # UGC 三张表
  game_social_meta.py --meta        # 成就/统计/图鉴
  game_social_meta.py --ngplus      # 🔴 周目三表
  game_social_meta.py --feedback    # 🔴 同帧仲裁
  game_social_meta.py --confirm     # 🔴 确认框**默认选中哪个**
  game_social_meta.py --progress    # 🔴 进度条"是否真实"
  game_social_meta.py --undo        # 撤销栈
  game_social_meta.py --a11y        # 无障碍游戏专有项
  game_social_meta.py --float       # 🔴 浮点矩阵
  game_social_meta.py --init ledger/social_meta.csv
  game_social_meta.py --check ledger/social_meta.csv --gate

退出码: 0 通过 / 1 缺项 / 2 用法错误
"""
import argparse
import csv
import os
import sys

# 表达五层
EXPR_LAYERS = [
    "**语义**", "**输入**", "**网络**", "**表现**", "**审核**",
]

EXPR_FIELDS = [
    "channel", "wheel / slot / activation",
    "**cursor_snap**（表面吸附）", "**range_limit**",
    "scope（party_or_squad 等）", "broadcast_radius_m",
    "**authoritative**", "reliable", "**expiry_policy**",
    "icon / vo / **world_billboard_seconds**",
]

# 🔴 ping
PING_Q = [
    "**谁能在同一坐标再次 ping**",
    "**聚合后显示什么**",
    "消失是**距离 / 超时 / 覆盖 / 超过上限 / 新消息**",
    "3D 空间标记类型与**屏幕边缘指示**",
    "**是否穿透墙体可见**",
    "**是否有音效与方向感**",
    "同一帧多人 ping 是否合并",
]

PING_CHANNELS = [
    "emote 表情轮盘", "phrase 预设短语/语音轮盘", "**ping 标记**",
    "graffiti 涂鸦/留言", "chat 聊天",
]

# 队伍
PARTY_FIELDS = [
    "邀请发起者", "被邀请者", "**邀请有效期**", "最大人数", "队伍类型",
    "队长", "加入冷却", "跨平台限制", "匹配状态", "准备状态",
    "**掉线归属**", "重连窗口", "**迁移策略**", "AI 替补",
    "队伍聊天", "队伍目标", "**掉落分配**", "**共享进度**",
    "禁止交互", "**跨队伍交易**", "观战权限",
]

PARTY_RULE = "🔑 **不能只记录「最多四人组队」**"

SOCIAL_ID_RULE = "🔑 社交**稳定 ID 不得复用**（重命名/合并/删除时）"

# UGC 三张表
UGC_TABLES = [
    ("**评审表**", "自动静态检查、人工审核、评分、冷却、自动隐藏、申诉、版本回滚"),
    ("**分发表**", "下载源、CDN、依赖、哈希、签名、更新策略、区域、灰度、过期"),
    ("**可见表**", "好友、公会、房主、平台、年龄/地区、已拥有 DLC、跨平台、作者自己"),
]

UGC_RULE = [
    "❌ 不应直接吸收某个开源游戏平台的分发实现（除非目标项目确用同一平台）",
    "✅ 更合适的是采用**配置契约**，把「分发状态机」做成**可替换适配器**",
    "❌ 商业 UGC 平台代码 —— 服务条款风险高，与自研架构透明要求冲突",
]

# 元游戏
META_TYPES = [
    "成就/奖杯的**隐藏条件与互斥**",
    "**统计页面**：显示什么、精度、**何时更新**",
    "**图鉴/收藏/博物馆**：解锁条件、完成度",
    "**新游戏+ / 周目**：继承什么、重置什么、难度变化",
    "**二周目专属内容与隐藏结局**",
    "**跨作品联动/彩蛋**",
]

# 🔴 周目三表
NGPLUS_TABLES = [
    ("**继承**", "等级、装备、货币、库存、技能、外观、统计、图鉴",
     "旧版消耗品与新周目敌人强度不匹配"),
    ("**重置**", "任务、世界状态、区域、NPC、商店、副本、临时 buff",
     "**旧任务 flag 残留导致永久卡关**"),
    ("**叠加**", "周目数、难度、敌人配置池、掉落池、剧情分支、隐藏结局",
     "**周目数作为整数溢出/负数**"),
]

NGPLUS_ACCESS = [
    "触发窗口", "**事件顺序**", "周目前提", "装备/技能/收集/对话/时间限制",
    "冲突选择", "可见提示", "**失败后可补救窗口**", "是否跨存档",
    "录像能否复现", "**重放是否能重新触发**",
]

NGPLUS_RULE = [
    "🔑 周目要**同时**记录是否改变敌人配置、商店池、结局标志与隐藏判定",
    "🔴 若原版要求「**在某一帧内完成特定序列**」，"
    "**不能将窗口扩大到整秒级** —— 仍是 must_match",
]

# 🔴 反馈仲裁
ARBITER_FIELDS = [
    "channel", "event_id", "severity", "required_action", "exclusivity",
    "pause_game", "input_lock", "**default_focus**", "escape_policy",
    "auto_dismiss", "queue_limit", "group_key", "suppress_condition",
    "replay_policy", "**same_frame_order**",
]

ARBITER_ORDER = [
    "致命错误 > 保存/退出阻塞 > 任务关键 > 教程 > 资源/获得物品 > 环境 > 调试",
]

ARBITER_RULE = [
    "⚠️ 上面是**模板默认值，不能替原作决定** —— 先记录原作**实际顺序**",
    "🔑 记录系统是按注册顺序 / 优先级 / 生成时间 / 屏幕位置 / **随机**仲裁",
    "🔑 同一帧三个 toast 是否压缩 · 同组消息是否累计 · "
    "离开暂停后是否**全部重放** · 过场/加载中提示是否排队或丢失",
    "🔑 HUD toast、模态框、屏幕边缘指示**能否共存**",
]

# 🔴 确认框
CONFIRM_FIELDS = [
    "**default_focus**（confirm / cancel / third_option / none）",
    "方向键循环", "**首次选择记忆**", "危险动作二次确认",
    "**自动聚焦陷阱**", "键盘回车语义", "手柄 A 语义",
    "**鼠标悬停是否改变默认项**", "对话框失焦/切窗口后焦点去向",
    "重复打开是否重置", "**快速连按是否导致误操作**",
]

CONFIRM_CASES = [
    "保存", "删除", "覆盖", "购买", "退出", "破坏建筑", "放弃任务",
    "移除装备", "**重置配点**",
]

CONFIRM_Q = "🔑 **默认选中「确定」还是「取消」？**"

# 进度条
PROGRESS_FIELDS = [
    "已完成的**真实工作单位**", "估算分母", "**分母是否变化**",
    "ETA 策略", "**虚假/真实语义**", "暂停时是否冻结", "反跳",
    "**最小显示时间**", "取消语义", "失败语义", "后台任务", "多任务排序",
]

PROGRESS_CASES = [
    "删除临时文件", "资源解压", "**着色器编译**", "烘焙", "下载", "安装",
    "云同步", "首启动资源准备", "**着色器编译卡顿是否共享同一进度口径**",
]

PROGRESS_RULE = "🔑 若原版进度条在最后 99% 等待 IO，目标端**必须保留该表现**"

# 撤销
UNDO_FIELDS = [
    "撤销栈容量", "**每步颗粒度**", "跨保存持久化",
    "是否记录移动/删除/购买/出售/配方/属性点/建筑组/**选择对话**/摄影",
    "**撤销是否扣资源**", "不可撤销窗口", "同帧批量", "重做上限",
    "**镜头与选择状态是否回滚**",
]

# 无障碍
A11Y_ITEMS = [
    "**色盲模式的具体映射**（哪种模式改哪些颜色、"
    "**是否影响判定可读性**）",
    "**单手模式 / 按键重映射 / 连发**",
    "**字幕**：大小、背景、**说话者标识**、**方向指示**、**音效字幕**",
    "**运动 sickness 选项**：视野、摇晃、**动态模糊开关**",
    "文本缩放与换行（UAX #14）",
]

A11Y_REFS = [
    "Game Accessibility Guidelines（**采用前核具体许可**）",
    "**WCAG 2.2**（W3C 推荐标准）：状态消息、焦点顺序、输入、目标大小、时间、文本间距",
    "**W3C IMSC 1.1**（字幕区域、样式、时间、profile）",
    "Unicode UAX #14（换行规则）",
]

A11Y_RULE = "🔑 无障碍**不能只放设置菜单**，必须与**可读性和安全区共同验收**"

# 🔴 浮点
FLOAT_MATRIX = [
    "**平台 × 编译器 × 优化 × 头文件**",
    "MSVC `/fp:strict` · `/arch:AVX2`",
    "Clang/GCC `-fno-fast-math` · **`-ffp-contract=off`**",
    "**FMA**（融合乘加）",
    "**SIMD 头文件**",
    "**编译器与运行时版本**",
]

FLOAT_ITEMS = [
    "跨平台 **sqrt / sin / 精度**",
    "**定点数与分数**：原版是否用定点",
    "**字符串哈希是否稳定、跨版本**",
    "**时间步累积误差**：长时间运行的漂移",
]

FLOAT_RULE = [
    "🔑 这是「**确定性**」的**数值根因层** —— "
    "前面只覆盖了回放，没覆盖根因",
    "🔴 **不能只靠「固定种子」或「使用确定性库」** —— "
    "必须下沉到编译和序列化层",
    "⚠️ 哈希/随机库要**固定版本、种子与长度语义**；"
    "**算法稳定 ≠ 跨版本 API 稳定**",
]

CONFLICTS = [
    "❌ 把社交当「非核心 UI」整体丢弃 —— 社区感载体",
    "❌ 直接吸收某平台的 UGC 分发实现（除非同平台）",
    "❌ 周目触发窗口扩大到整秒级 —— 仍是 must_match",
    "❌ 用模板默认值替原作决定同帧仲裁顺序",
    "❌ 只记录错误消息不记录失败后的下一状态",
    "❌ 进度条「看起来一样」就算过 —— 要记是否真实",
    "❌ 无障碍只放设置菜单 —— 必须与可读性共同验收",
    "❌ 只靠固定种子保证确定性",
]

FIELDS = [
    ("item_id", "项编号"),
    ("domain", "域（expression / ping / party / ugc / meta / ngplus / feedback / confirm / progress / undo / a11y / float）"),
    ("legacy_value", "**原版值**"),
    ("new_value", "新引擎值"),
    ("match", "**是否一致**"),
    ("evidence", "证据"),
]


def _hdr(t, w=80):
    print("=" * w)
    print(t)
    print("=" * w)


def cmd_expression(a):
    _hdr("表达通道（**五层**）")
    print("通道: " + " · ".join(PING_CHANNELS))
    print("\n五层: " + " · ".join(EXPR_LAYERS))
    print("\n字段: " + " · ".join(EXPR_FIELDS))
    return 0


def cmd_ping(a):
    _hdr("🔴 ping（**真正的差异不在有没有**）")
    for q in PING_Q:
        print(f"   · {q}")
    return 0


def cmd_party(a):
    _hdr("队伍（**带生命周期的状态机**）")
    for f in PARTY_FIELDS:
        print(f"   · {f}")
    print(f"\n   {PARTY_RULE}")
    print(f"   {SOCIAL_ID_RULE}")
    return 0


def cmd_ugc(a):
    _hdr("UGC 三张表")
    for k, why in UGC_TABLES:
        print(f"\n   【{k}】{why}")
    print("\n规则:")
    for r in UGC_RULE:
        print(f"   {r}")
    return 0


def cmd_meta(a):
    _hdr("元游戏层")
    for m in META_TYPES:
        print(f"   · {m}")
    return 0


def cmd_ngplus(a):
    _hdr("🔴 周目三表")
    for k, what, trap in NGPLUS_TABLES:
        print(f"\n   【{k}】{what}")
        print(f"      坑: {trap}")
    print("\n可访问性判定树: " + " · ".join(NGPLUS_ACCESS))
    print("\n规则:")
    for r in NGPLUS_RULE:
        print(f"   {r}")
    return 0


def cmd_feedback(a):
    _hdr("🔴 反馈仲裁（**同帧排序**）")
    print("字段: " + " · ".join(ARBITER_FIELDS))
    print("\n模板默认顺序:")
    for o in ARBITER_ORDER:
        print(f"   {o}")
    print("\n规则:")
    for r in ARBITER_RULE:
        print(f"   {r}")
    return 0


def cmd_confirm(a):
    _hdr("🔴 确认对话框")
    for f in CONFIRM_FIELDS:
        print(f"   · {f}")
    print(f"\n   {CONFIRM_Q}")
    print("\n尤其检查: " + " · ".join(CONFIRM_CASES))
    return 0


def cmd_progress(a):
    _hdr("🔴 进度条（**到底代表什么**）")
    for f in PROGRESS_FIELDS:
        print(f"   · {f}")
    print("\n场景: " + " · ".join(PROGRESS_CASES))
    print(f"\n{PROGRESS_RULE}")
    return 0


def cmd_undo(a):
    _hdr("撤销/重做")
    for f in UNDO_FIELDS:
        print(f"   · {f}")
    return 0


def cmd_a11y(a):
    _hdr("无障碍（游戏专有项）")
    for i in A11Y_ITEMS:
        print(f"   · {i}")
    print("\n参考: " + " · ".join(A11Y_REFS))
    print(f"\n{A11Y_RULE}")
    return 0


def cmd_float(a):
    _hdr("🔴 浮点确定性（**数值根因层**）")
    for m in FLOAT_MATRIX:
        print(f"   · {m}")
    print("\n项: " + " · ".join(FLOAT_ITEMS))
    print("\n规则:")
    for r in FLOAT_RULE:
        print(f"   {r}")
    return 0


def cmd_init(a):
    os.makedirs(os.path.dirname(a.init) or ".", exist_ok=True)
    with open(a.init, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow([k for k, _ in FIELDS])
        w.writerow(["TODO"] * len(FIELDS))
    print(f"已生成社交/元游戏表: {a.init}")
    print("\n⚠️ 十二域：expression / ping / party / ugc / meta / ngplus / "
          "feedback / confirm / progress / undo / a11y / float")
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
    print(f"社交/元游戏 · {len(rows)} 条")
    print("=" * 76)
    if mismatch:
        print(f"\n🚫 **不一致** {len(mismatch)} 条（行 {mismatch[:15]}）")
    if no_legacy:
        print(f"\n❌ {len(no_legacy)} 条缺**原版值**（行 {no_legacy[:15]}）")

    if not (mismatch or no_legacy):
        print("\n✅ 社交/元游戏：一致且原版值完整")

    print("\n🔑 **差异不在有没有 ping，在谁能再 ping、聚合显示什么、怎么消失。**")
    print("   **周目触发窗口不能扩大到整秒级。**")
    print("   **确定性要下沉到编译层，不能只靠固定种子。**")
    return 1 if (a.gate and (mismatch or no_legacy)) else 0


def main():
    ap = argparse.ArgumentParser(description="社交/元游戏/反馈/无障碍/浮点")
    ap.add_argument("--expression", action="store_true")
    ap.add_argument("--ping", action="store_true")
    ap.add_argument("--party", action="store_true")
    ap.add_argument("--ugc", action="store_true")
    ap.add_argument("--meta", action="store_true")
    ap.add_argument("--ngplus", action="store_true")
    ap.add_argument("--feedback", action="store_true")
    ap.add_argument("--confirm", action="store_true")
    ap.add_argument("--progress", action="store_true")
    ap.add_argument("--undo", action="store_true")
    ap.add_argument("--a11y", action="store_true")
    ap.add_argument("--float", action="store_true")
    ap.add_argument("--init")
    ap.add_argument("--check")
    ap.add_argument("--gate", action="store_true")
    a = ap.parse_args()
    fns = {"expression": cmd_expression, "ping": cmd_ping, "party": cmd_party,
           "ugc": cmd_ugc, "meta": cmd_meta, "ngplus": cmd_ngplus,
           "feedback": cmd_feedback, "confirm": cmd_confirm,
           "progress": cmd_progress, "undo": cmd_undo, "a11y": cmd_a11y,
           "float": cmd_float}
    for k, fn in fns.items():
        if getattr(a, k):
            return fn(a)
    if a.init:
        return cmd_init(a)
    if a.check:
        return cmd_check(a)
    print("❌ 需要 --expression / --ping / --party / --ugc / --meta / --ngplus / "
          "--feedback / --confirm / --progress / --undo / --a11y / --float / "
          "--init / --check 之一")
    return 2


if __name__ == "__main__":
    sys.exit(main())
