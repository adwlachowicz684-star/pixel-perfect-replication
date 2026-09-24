#!/usr/bin/env python3
"""任务/对话系统深化（第十二轮 A / B 类）。

**🔑 A 类核心**：
> 任务状态必须记录**进入条件、退出副作用和失败补偿**，而不是只记枚举。
> **任务级状态不能替目标级状态代言。**
> 🔴 **`expired` 不等于 `failed`** —— expired 可能是限时未完成但保留历史；
> failed 可能允许重试；suppressed 可能因前置任务暂时不可见。

**🔑 B 类核心**：
> **"文本存在"与"会话语义"必须分开取证。**
> 🔴 **跳过要拆成 `char/turn/node/branch/choice/entire_conversation` 六级** ——
> 若原作把「进入节点」视为已访问，而新实现只跳过字幕但不执行命令，
> **玩家会获得未触发奖励**。

用法:
  game_quest_dialog.py --quest      # 🔴 任务十一状态
  game_quest_dialog.py --objective  # 🔴 目标八字段（**不能由任务级代言**）
  game_quest_dialog.py --complete   # **自动完成 vs 手动交付**是两类事务
  game_quest_dialog.py --expire     # 过期/锁定/互斥的**时钟来源**
  game_quest_dialog.py --linkage    # 任务与关卡联动证据表
  game_quest_dialog.py --dialog     # 对话图（**不是朴素树**）
  game_quest_dialog.py --variable   # 变量**写入边界**
  game_quest_dialog.py --timeline   # 🔴 对话四段时间轴
  game_quest_dialog.py --cameraline # 镜头与说话人高亮是**交互状态**
  game_quest_dialog.py --lipsync    # 唇形按 **cue** 对齐
  game_quest_dialog.py --init ledger/quest_dialog.csv
  game_quest_dialog.py --check ledger/quest_dialog.csv --gate

退出码: 0 通过 / 1 缺项 / 2 用法错误
"""
import argparse
import csv
import os
import sys

# 任务十一状态
QUEST_STATES = [
    "unavailable", "locked", "available", "offerable", "active",
    "ready_to_complete", "completed", "**failed**", "**expired**",
    "**abandoned**", "**suppressed**",
]

QUEST_RULE = [
    "🔑 可合并但**必须逐项说明合并依据**",
    "🔑 每个转换要有：触发器 · 前置世界条件 · **是否幂等** · "
    "重复进入次数 · 回滚动作 · 是否需要存档",
    "🔴 **`expired` 不等于 `failed`** —— expired 可能保留历史，"
    "failed 可能允许重试，suppressed 可能因前置任务暂时不可见",
    "🔴 原作若把「任务消失」实现为**锁**而不是删除 → "
    "迁移到列表模型后**重新出现条件和顺序就会错**",
]

# 🔴 目标
OBJECTIVE_FIELDS = [
    "id", "quest_id", "**ordering**（作者/进度/UI 三种排序）",
    "**group_operator**（AND/OR/COUNT）", "required_count", "current_count",
    "**auto_progress**", "**hidden**", "**optional**",
    "required_for_completion", "**failure_condition**",
    "**world_effect_on_complete**", "save_policy",
]

OBJECTIVE_RULE = [
    "🔴 **任务级状态不能替目标级状态代言**",
    "🔑 `hidden` **不等于** `optional` —— "
    "**隐藏目标可能影响奖励或结局**",
    "🔑 **可选目标失败不应把任务置为 failed**",
    "🔑 `failure_condition` 必须明确反方向：敌人死亡 / 物品销毁 / 超时 / "
    "离开区域**分别何时生效**，补偿动作是否允许回滚",
    "🔑 严格序列与「任一完成」必须写成**显式图**",
]

# 完成事务
COMPLETE_RULE = [
    "🔴 **自动完成与手动交付是两类不同的世界事务**",
    "自动完成：进度达成后**延迟多少帧/秒** · 是否立即发奖 · "
    "**是否在加载屏/过场/暂停/死亡时排队**",
    "手动交付：可交付 NPC/区域 · 距离判定 · 图标刷新 · "
    "对话前检查 · **奖励幂等键**",
    "🔴 若原作**先播演出再删任务**，新实现若先删任务后播演出 → "
    "**中断重开会漏奖励或重复奖励**",
    "✅ 必须加双阶段事务：**`prepare_rewards` 与 `commit_rewards`**，"
    "两者之间的**崩溃恢复路径逐条记录**",
]

# 过期/锁定/互斥
EXPIRE_CLOCK = [
    "真实时间", "**游戏世界时间**", "**玩家离开区域时间**",
    "连续会话时间", "服务端周期",
]

EXPIRE_TESTS = [
    "快速旅行", "暂停", "睡眠", "过场", "**存档退出**",
]

LOCK_SOURCES = [
    "flag", "计数", "声望", "物品", "等级", "其他任务状态", "**运行时脚本**",
]

MUTEX_RULE = [
    "互斥要记录：是否共享**互斥组** · 失败是否阻塞新任务 · "
    "**是否允许组内有多个 active**",
]

# 联动证据表
LINKAGE_FIELDS = [
    "门锁", "区域入口", "**敌人表**", "**NPC 生成/移除**", "巡逻路径",
    "对话表", "商店库存", "天气", "**寻路图**", "任务图标", "任务追踪行",
]

LINKAGE_TESTS = [
    "接任务后**旧 NPC 是否仍可见**",
    "**完成条件达成但 NPC 死亡时 UI**",
    "任务失败后**再解锁区域**",
    "**跨快速旅行保持对象引用**",
]

LINKAGE_RULE = "🔴 原作若以**实体实例 ID** 关联，新引擎若只按名称关联 → "
"**重复实体会让一个任务误影响多个对象**"

# 对话图
DIALOGUE_NODES = [
    "line", "option", "branch", "set_variable", "command", "camera",
    "audio", "wait", "**jump**", "**return**",
]

DIALOGUE_EDGES = [
    "条件", "权重", "**隐藏条件**", "**禁用原因**", "**回退节点**", "锁定顺序",
]

DIALOGUE_RULE = [
    "🔑 模型应是**对话图**，不是朴素树",
    "🔑 要记录原作是否在**节点边界外缓存选项**、"
    "是否允许**同一选项跨节点复用**",
    "🔑 对话资源与运行时呈现分离是成熟做法 —— "
    "但仍要逐项取证而非假定",
]

# 变量
VARIABLE_FIELDS = [
    "**storage_owner**", "**persist_scope**（节点/会话/存档/账号）",
    "**revert_on_branch_fail**", "**undefined_is_false**",
    "比较是否区分整数与浮点", "字符串区域",
    "**字符串相等是否区分大小写**",
]

VARIABLE_RULE = [
    "🔴 变量可为文本、数字、布尔或 `null`，**未设置值为 `null`** —— "
    "这**不能默认等于原作的持久化模型**",
    "🔑 对话中 `set` 触发世界写入时，要区分："
    "**立即提交 / 节点结束提交 / 玩家确认后提交**",
    "🔴 **若原作允许中途退出并保留部分写入，绝不能改成全事务回滚**",
]

# 🔴 对话时间轴
TIMELINE_SEGMENTS = [
    "**世界**（暂停掩码）", "**音频**（pause/resume）",
    "**字幕**（显示时间）", "**输入**（消费延迟）",
]

TYPEWRITER_FIELDS = [
    "**每字符固定间隔**", "**按标点延长**", "**富文本 tag 是否计时**",
    "**跨行续打还是清空**",
]

SKIP_LEVELS = [
    "char", "turn", "node", "branch", "choice", "**entire_conversation**",
]

SKIP_RULE = [
    "🔑 **快速跳过是否可取消** · **是否消耗未结算命令**",
    "🔴 若原作把「进入节点」视为已访问，而新实现只跳过字幕但不执行命令 → "
    "**玩家会获得未触发奖励**",
]

# 镜头与高亮
CAMERA_FIELDS = [
    "相机优先级", "目标", "**过肩/正反打**", "混合曲线", "FOV",
    "**head bob 开关**", "说话人缩放", "聆听者注视", "**未聚焦角色灰显**",
    "字幕归属", "**多人同屏归属**",
]

CAMERA_RETURN = [
    "过场中断", "菜单打开", "失焦", "来电", "**任务完成弹窗**",
]

CAMERA_RULE = "🔴 镜头由对话抢占时，要记录**归还顺序** —— "
"**归还失败会导致后续镜头永久偏移**"

READ_MARKS = [
    "**进入节点**", "**读完字幕**", "**播放语音**", "**作出选择**",
    "**完成副作用**",
]

READ_RULE = "🔑 已读标记要区分上述五者，并记录**跨存档/跨周目/跨语言是否共享**；"
"只存「已读/未读」会丢失隐藏重看和变量回退测试"

# 唇形
LIPSYNC_FIELDS = [
    "采样率", "**口型驱动源**（音频振幅 / 音素 / 骨骼 / blendshape）",
    "**首帧静音**", "双语字幕", "字幕安全区", "**超时强制显示**",
    "字幕换行规则", "**字幕被镜头遮罩规则**",
]

LIPSYNC_RULE = [
    "🔑 语音、字幕和唇形必须**按 cue 而非按整段对齐**",
    "🔑 录音时长与字幕消失**不能默认绑定**",
    "🔑 要分别测试：慢语速 · 机器翻译换行 · **缺失语音** · "
    "**带控制字符文本**",
    "🔴 **唇形若依赖实时音频，拍照模式或暂停后音频静音 → "
    "嘴型可能冻结错误** —— 这正是「看起来通了」的隐形差异",
]

CONFLICTS = [
    "❌ 只记任务枚举不记进入条件与回滚",
    "❌ **任务级状态替目标级代言**",
    "❌ 把 expired 与 failed 合并",
    "❌ 自动完成与手动交付当成同一类事务",
    "❌ **中断时全事务回滚**（原作可能保留部分写入）",
    "❌ 把对话当朴素树而非图",
    "❌ **跳过只做「跳过字幕」而不执行命令**",
    "❌ 唇形按整段对齐而非 cue",
    "❌ 把已读标记简化为已读/未读",
]

FIELDS = [
    ("item_id", "项编号"),
    ("domain", "域（quest / objective / complete / expire / linkage / dialog / variable / timeline / camera / lipsync）"),
    ("legacy_value", "**原版值**"),
    ("new_value", "新引擎值"),
    ("match", "**是否一致**"),
    ("idempotent", "**是否幂等**"),
    ("evidence", "证据"),
]


def _hdr(t, w=80):
    print("=" * w)
    print(t)
    print("=" * w)


def cmd_quest(a):
    _hdr("🔴 任务状态（**不是清单，是状态传播图**）")
    print("十一状态: " + " · ".join(QUEST_STATES))
    print("\n规则:")
    for r in QUEST_RULE:
        print(f"   {r}")
    return 0


def cmd_objective(a):
    _hdr("🔴 任务目标（**不能由任务级代言**）")
    for f in OBJECTIVE_FIELDS:
        print(f"   · {f}")
    print("\n规则:")
    for r in OBJECTIVE_RULE:
        print(f"   {r}")
    return 0


def cmd_complete(a):
    _hdr("自动完成 vs 手动交付（**两类事务**）")
    for r in COMPLETE_RULE:
        print(f"   {r}")
    return 0


def cmd_expire(a):
    _hdr("过期 / 锁定 / 互斥")
    print("`expired_at` 时钟来源: " + " · ".join(EXPIRE_CLOCK))
    print("\n是否推进该时钟: " + " · ".join(EXPIRE_TESTS))
    print("\n`locked` 来源: " + " · ".join(LOCK_SOURCES))
    print("\n互斥:")
    for r in MUTEX_RULE:
        print(f"   {r}")
    return 0


def cmd_linkage(a):
    _hdr("任务与关卡联动（**落到可见证据表**）")
    for f in LINKAGE_FIELDS:
        print(f"   · {f}")
    print("\n测试:")
    for t in LINKAGE_TESTS:
        print(f"   · {t}")
    print(f"\n   {LINKAGE_RULE}")
    return 0


def cmd_dialog(a):
    _hdr("对话图（**不是朴素树**）")
    print("节点: " + " · ".join(DIALOGUE_NODES))
    print("\n边: " + " · ".join(DIALOGUE_EDGES))
    print("\n规则:")
    for r in DIALOGUE_RULE:
        print(f"   {r}")
    return 0


def cmd_variable(a):
    _hdr("变量（**写入边界**）")
    for f in VARIABLE_FIELDS:
        print(f"   · {f}")
    print("\n规则:")
    for r in VARIABLE_RULE:
        print(f"   {r}")
    return 0


def cmd_timeline(a):
    _hdr("🔴 对话时间轴（**四段**）")
    print("分段: " + " · ".join(TIMELINE_SEGMENTS))
    print("\n逐字显示: " + " · ".join(TYPEWRITER_FIELDS))
    print("\n跳过六级: " + " · ".join(SKIP_LEVELS))
    print("\n规则:")
    for r in SKIP_RULE:
        print(f"   {r}")
    return 0


def cmd_cameraline(a):
    _hdr("镜头与说话人高亮（**交互状态**）")
    for f in CAMERA_FIELDS:
        print(f"   · {f}")
    print("\n归还顺序: " + " · ".join(CAMERA_RETURN))
    print(f"\n   {CAMERA_RULE}")
    print("\n已读标记五级: " + " · ".join(READ_MARKS))
    print(f"\n   {READ_RULE}")
    return 0


def cmd_lipsync(a):
    _hdr("语音/字幕/唇形（**按 cue 对齐**）")
    for f in LIPSYNC_FIELDS:
        print(f"   · {f}")
    print("\n规则:")
    for r in LIPSYNC_RULE:
        print(f"   {r}")
    return 0


def cmd_init(a):
    os.makedirs(os.path.dirname(a.init) or ".", exist_ok=True)
    with open(a.init, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow([k for k, _ in FIELDS])
        w.writerow(["TODO"] * len(FIELDS))
    print(f"已生成任务/对话表: {a.init}")
    print("\n⚠️ 十域：quest / objective / complete / expire / linkage / "
          "dialog / variable / timeline / camera / lipsync")
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

    mismatch, no_legacy, no_idem = [], [], []
    for i, r in enumerate(rows, 1):
        m = g(r, "match").lower()
        if m not in ("yes", "y", "true", "是", "一致"):
            mismatch.append(i)
        if not g(r, "legacy_value") or g(r, "legacy_value") == "TODO":
            no_legacy.append(i)
        idem = g(r, "idempotent")
        if idem in ("", "todo", "unknown"):
            no_idem.append(i)

    print("=" * 76)
    print(f"任务/对话 · {len(rows)} 条")
    print("=" * 76)
    if mismatch:
        print(f"\n🚫 **不一致** {len(mismatch)} 条（行 {mismatch[:15]}）")
    if no_legacy:
        print(f"\n❌ {len(no_legacy)} 条缺**原版值**（行 {no_legacy[:15]}）")
    if no_idem:
        print(f"\n⚠️  {len(no_idem)} 条**未判定是否幂等**（行 {no_idem[:15]}）")
        print("   → 🔴 任务转换与奖励发放必须逐条判定幂等性")

    if not (mismatch or no_legacy):
        print("\n✅ 任务/对话：一致且原版值完整")

    print("\n🔑 **expired 不等于 failed；自动完成与手动交付是两类事务。**")
    print("   **跳过要做六级；只跳字幕不执行命令会漏奖励。**")
    return 1 if (a.gate and (mismatch or no_legacy)) else 0


def main():
    ap = argparse.ArgumentParser(description="任务与对话系统")
    ap.add_argument("--quest", action="store_true")
    ap.add_argument("--objective", action="store_true")
    ap.add_argument("--complete", action="store_true")
    ap.add_argument("--expire", action="store_true")
    ap.add_argument("--linkage", action="store_true")
    ap.add_argument("--dialog", action="store_true")
    ap.add_argument("--variable", action="store_true")
    ap.add_argument("--timeline", action="store_true")
    ap.add_argument("--cameraline", action="store_true")
    ap.add_argument("--lipsync", action="store_true")
    ap.add_argument("--init")
    ap.add_argument("--check")
    ap.add_argument("--gate", action="store_true")
    a = ap.parse_args()
    fns = {"quest": cmd_quest, "objective": cmd_objective,
           "complete": cmd_complete, "expire": cmd_expire,
           "linkage": cmd_linkage, "dialog": cmd_dialog,
           "variable": cmd_variable, "timeline": cmd_timeline,
           "cameraline": cmd_cameraline, "lipsync": cmd_lipsync}
    for k, fn in fns.items():
        if getattr(a, k):
            return fn(a)
    if a.init:
        return cmd_init(a)
    if a.check:
        return cmd_check(a)
    print("❌ 需要 --quest / --objective / --complete / --expire / --linkage / "
          "--dialog / --variable / --timeline / --cameraline / --lipsync / "
          "--init / --check 之一")
    return 2


if __name__ == "__main__":
    sys.exit(main())
