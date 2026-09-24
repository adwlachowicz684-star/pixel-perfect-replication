#!/usr/bin/env python3
"""库存/配点手感 + 地图导航 + 死亡流程（第十二轮 C / D / E / F / G 类）。

**🔑 C 类核心**：
> **所有玩家可感知差异都来自边界事务。**
> 🔴 **`full_behavior` 与"排序是否稳定"是 must-match** ——
> **全量刷新若导致选中项跳格，虽然数据正确，也属于手感 BUG**。

**🔑 D 类核心**：
> **配点不是数值表，而是可撤销编辑会话。**
> `preview` 必须明确：仅 UI / 立即生效但可撤销 / **立即写入存档** ——
> **三者的死亡/退出/断点行为不同**。

**🔑 G 类核心**：
> 重生是**显式事务**，不能把「回到检查点」当一句重置。
> 🔴 **快速旅行不是地图 UI 功能，而是「模拟模式」入口。**

用法:
  game_inventory_flow.py --bag      # 四种背包模型
  game_inventory_flow.py --pickup   # 🔴 满包行为
  game_inventory_flow.py --sort     # 🔴 稳定排序要写**完整排序键**
  game_inventory_flow.py --drag     # 拖拽是**目标槽判据状态机**
  game_inventory_flow.py --equip    # 🔴 输入确认 vs 效果生效
  game_inventory_flow.py --compare  # 比较 UI 是否显示 **delta**
  game_inventory_flow.py --skill    # 技能树依赖图与**回退路径**
  game_inventory_flow.py --point    # 🔴 配点四事务
  game_inventory_flow.py --recalc   # **重算时机**决定体感
  game_inventory_flow.py --map      # 地图与小地图**不是同一坐标视图**
  game_inventory_flow.py --path     # 路径指引是**导航查询**
  game_inventory_flow.py --shop     # 商店价格显示
  game_inventory_flow.py --death    # 🔴 死亡流程片段
  game_inventory_flow.py --respawn  # 重生是显式事务
  game_inventory_flow.py --travel   # 🔴 快速旅行要**推进世界**
  game_inventory_flow.py --init ledger/inventory_flow.csv
  game_inventory_flow.py --check ledger/inventory_flow.csv --gate

退出码: 0 通过 / 1 缺项 / 2 用法错误
"""
import argparse
import csv
import os
import sys

# 四种背包模型
BAG_MODELS = [
    "**slot_grid**", "**slot_list**", "**weight**", "**volume**",
]

BAG_FIELDS = [
    "width/height/**rotation**", "sort_key", "**weight_epsilon**",
    "volume_units", "**container_nesting**", "**rigid_packing**",
]

BAG_GRID = [
    "物品尺寸", "**锚点**", "**旋转**", "重叠判定", "**空间整理启发式**",
]

BAG_WEIGHT = [
    "角色负重", "装备负重", "**容器自身重量**", "嵌套容器", "临时加成",
    "**UI 的舍入显示**",
]

BAG_RULE = "🔑 四种模型**不应被一个列表取代**"

# 🔴 满包
PICKUP_FIELDS = [
    "自动拾取距离/时间", "拾取半径", "**逐物品延迟**",
    "**堆叠补齐顺序**", "目标槽位选择", "**背包满后的地面残留**",
    "玩家拒绝", "**同类但不同绑定/耐久/附魔能否合并**",
    "**拆分舍入**", "**掉落所有权**",
]

FULL_BEHAVIOR = [
    "reject", "leave_on_ground", "send_to_mail", "overflow_bag",
    "**auto_drop_lowest**", "ask_player",
]

FULL_RULE = [
    "🔑 还要记：拒绝提示 · **残留数量** · 交易回滚 · **多物品交互的中断点**",
    "🔴 **自动拾取若按视距而不是原作的距离/延迟排序** → "
    "即使最终物品相同，**收集节奏也会改变**",
]

# 🔴 稳定排序
SORT_KEY = [
    "rarity", "type", "quality", "stackable", "item_id",
    "**instance_id**", "**obtain_time**", "**slot_index**",
]

SORT_TESTS = [
    "先按名称排序、再按品质排序后，**同名同品质物品顺序是否保留**",
    "**筛选后恢复** · **整理后恢复** · 交易/制造后恢复 —— "
    "分别保持原稳定键还是重建索引",
]

INSERT_POS = [
    "顶部", "底部", "**分组首部**", "**分组尾部**", "**保持排序键**",
]

SORT_RULE = "🔴 **全量刷新若导致选中项跳格，虽然数据正确，也属于手感 BUG**"

# 拖拽
DRAG_FIELDS = [
    "**命中测试顺序**", "**吸附像素**", "非法目标视觉", "源占位符",
    "跨容器幽灵图标", "**拖动中时间是否流动**", "设备焦点",
    "触摸长按", "鼠标右键", "键盘交换",
    "**交换 / 覆盖 / 合并 / 堆叠补齐**", "目标满后的行为", "撤销", "容器嵌套",
]

DRAG_RULE = [
    "🔑 必须明确：**不同物品是否交换 · 同物品是否合并 · "
    "同物品但不可合并是否保持原位**",
    "🔑 **`drop` 与 `commit` 若不同帧** → 回滚后图标位置、音效、"
    "**输入焦点**都需恢复",
]

# 🔴 装备
EQUIP_FIELDS = [
    "装备耗时", "动画长度", "**可打断窗口**",
    "**打断后是否保留预览属性**", "冷却是否共享", "快捷栏数量",
    "空手/双持/套装/饰品冲突", "自动卸下", "**统计重算事件**",
    "UI 高亮", "多人同步",
]

EQUIP_RULE = [
    "🔑 **切换耗时若仅由动画驱动 → 帧率下降会改变有效切换速度**；"
    "若按时间驱动 → **暂停和慢动作需单独规定**",
    "🔑 联动系统：攻击 · 技能 · 负重 · 移速 · 耐力 · 热量 · **声纹** · "
    "碰撞 · 动画 · 商店比较 · **任务条件**",
]

# 比较
COMPARE_FIELDS = [
    "**对比 delta 显示哪些字段**", "正负色", "舍入", "**百分比分母**",
    "**空槽基线**", "装备中属性", "临时 buff", "套装阈值",
    "潜能/品质上下界", "**隐藏属性揭示条件**",
]

COMPARE_RULE = "🔴 **比较 UI 若只显示最终值而不显示 delta** → "
"玩家无法感知原作的「**临界提升**」"

# 技能树
SKILL_FIELDS = [
    "**prerequisites**（AND/OR/COUNT/**threshold**）", "**exclusive_group**",
    "hidden_until", "unlocked_effects", "**preview_effects**",
    "**refund_policy**", "**respect_cost**", "refund_delay",
    "anim_interrupt", "save_point",
]

SKILL_RULE = [
    "🔑 依赖关系**不能只按树展示** —— 环形前置、互斥组、按等级解锁后续、"
    "**跨天赋树引用都是图问题**",
    "🔑 还要记：首次展示默认状态 · 已解锁高亮 · **未解锁但可预览** · "
    "**锁定原因** · 点数不足 · **无法回退的窗口**",
]

# 🔴 配点四事务
POINT_FIELDS = [
    "初始分配", "**批量加点**", "**批量清零**", "**单步撤销栈深度**",
    "**跨节点撤销**", "最大撤销/重做", "**推荐配点的保存者**",
    "**玩家能否修改推荐**", "确认前是否临时生效", "确认后是否可取消",
    "**回退货币是否原路返还**",
]

PREVIEW_KINDS = [
    ("仅 UI", "最安全"),
    ("**立即生效但可撤销**", "中间"),
    ("**立即写入存档**", "**死亡/退出/断点行为不同**"),
]

POINT_BATCH = [
    "长按速度", "**是否超过上限自动停**", "**连续输入重复消费**",
]

# 重算时机
RECALC_FIELDS = [
    "输入响应", "**UI delta**", "能力解锁", "资源回复", "被动事件",
    "任务条件", "**商店价**", "**伤害公式缓存**", "动画", "音效", "相机反馈",
]

LEVELUP_FIELDS = [
    "黑屏", "镜头", "震屏", "顿帧", "**HUD 锁定**", "暂停世界",
    "**对话框**", "语音", "**过场打断优先级**",
]

RECALC_RULE = [
    "🔑 配点后若触发满额奖励、任务条件或阶段变化 → "
    "需记录**是否与正在播放的升级演出竞争**",
    "🔴 **若原作允许连续升级队列，新实现只播一次演出会漏反馈**；"
    "若逐个强制播放，**快速加点会卡死输入**",
]

# 地图
MAP_FIELDS = [
    "map_zoom_levels", "icon_taxonomy", "**fog_source**",
    "fog_persistence", "**discovered_vs_visited_vs_revealed**",
    "offline_tick_policy",
]

FOG_SOURCES = [
    "视线", "任务", "传送", "回忆", "**NPC 告知**", "预设剧情",
]

MINIMAP_FIELDS = [
    "**旋转模式**", "北向偏差", "缩放档位", "是否跟随玩家",
    "**圆形/方形裁切**", "**屏幕边缘目标箭头**",
    "**目标离开视野后的边缘吸附**", "深度/楼层越界", "失真",
]

MAP_RULE = [
    "🔑 **地图与小地图不是同一坐标视图**",
    "🔴 **若小地图北向而世界 UI 不旋转** → 长距离跑图会形成**持续误判**",
]

# 路径
PATH_FIELDS = [
    "指引来源", "**更新频率**", "实时/半实时/静态",
    "**是否使用当前 NavMesh**", "**是否避开门锁、敌人、玩家建设、可破坏物、"
    "临时障碍、区域权限**",
    "**穿墙模式的虚线样式、颜色、终端点**", "**「不可到达」状态**",
]

PIN_FIELDS = [
    "数量上限", "层级", "图标", "文字", "颜色", "过期条件",
    "跨地图持久化", "**多人可见性**",
]

PATH_RULE = "🔑 路径指引是**导航查询，不是画一条直线**"

# 商店
SHOP_FIELDS = [
    "基础价", "买入价", "卖出价", "折价", "**税**", "声望折扣",
    "批量阶梯", "货币类型", "**价格舍入**", "**玩家货币显示时机**",
    "缺钱高亮", "**确认默认按钮**", "一键卖出/回购", "库存容量",
    "**货架刷新时钟**", "**随机库存 seed**", "商店专属库存",
    "玩家库存过滤", "**比较 delta**", "库存占用",
]

SHOP_RULE = [
    "🔑 价格显示要区分：**含税 / 折扣前 / 单个与批量总价**",
    "🔑 数量选择器的默认值、最小步长、长按、最大数量、确认键"
    "**不能按引擎默认推断**",
    "🔴 交易、拾取、任务奖励和存档**若没有幂等键，重入会成为隐蔽 BUG**",
]

# 🔴 死亡
DEATH_FIELDS = [
    "health_zero_event", "**ragdoll/corpse/cinematic**", "camera_path",
    "audio_duck", "**fade_curve**", "**skippable_before_frame**",
    "**input_death_lock**", "save_on_death", "autoload_checkpoint",
    "load_screen_message", "respawn_position_rule",
]

DEATH_RULE = [
    "🔑 演出可跳过粒度要与**死亡动画、黑屏、读盘、输入恢复**分别记录",
    "🔴 若原作在「You lost X」窗口后恢复，而新实现在读盘前恢复 → "
    "**死亡惩罚呈现会被漏掉**",
]

# 重生
RESPAWN_FIELDS = [
    "**重生点优先级**", "死亡位置", "神殿", "营火", "载具", "队伍", "区域规则",
    "读盘是否双阶段", "**保留哪些临时/永久 buff**", "装备耐久", "弹药",
    "消耗品", "任务进度", "**掉落物**", "**尸体**", "世界时间戳",
    "**NPC 状态**", "**敌人生成**", "**已破坏对象**",
]

RESPAWN_DROP = [
    "死亡掉落是否留在世界", "**是否归属新尸体**", "**多人中谁拥有**",
    "**掉落过期时钟是否被暂停**",
]

RESPAWN_RULE = "🔑 重生是**显式事务** —— "
"**「回到检查点」不是一句重置**"

# 快速旅行
TRAVEL_FIELDS = [
    "出发条件", "可抵达集合", "耗时", "加载", "**逐区域事件**",
    "**随机遭遇**", "资源消耗", "疲劳", "**昼夜**", "天气",
    "**NPC 日程**", "**商店刷新**", "**任务过期**", "**敌人重置**", "保存点",
]

TRAVEL_ENTITIES = [
    "队伍", "载具", "**尸体**", "**掉落物**", "宠物", "跟随者",
    "**战斗状态**",
]

TRAVEL_RULE = [
    "🔴 **快速旅行不是地图 UI 功能，而是「模拟模式」入口**",
    "🔑 若它复用正常更新但**没有相同的事件顺序** → "
    "离场后再返回的 NPC、战利品和机关状态会与原作不同",
]

CONFLICTS = [
    "❌ 四种背包模型被一个列表取代",
    "❌ 自动拾取按视距而非原作距离/延迟排序",
    "❌ **全量刷新导致选中项跳格** —— 数据对也是手感 BUG",
    "❌ 把 drop 与 commit 当同一帧",
    "❌ 装备切换耗时隐含依赖帧率",
    "❌ 比较 UI 只显示最终值不显示 delta",
    "❌ 技能依赖只按树展示 —— 是图问题",
    "❌ **连续升级只播一次演出**",
    "❌ 小地图北向而世界 UI 不旋转",
    "❌ 路径指引画一条直线",
    "❌ 商店数量选择器按引擎默认推断",
    "❌ **交易/拾取/奖励没有幂等键**",
    "❌ 把「回到检查点」当一句重置",
    "❌ 快速旅行不推进世界时钟",
]

FIELDS = [
    ("item_id", "项编号"),
    ("domain", "域（bag / pickup / sort / drag / equip / compare / skill / point / recalc / map / path / shop / death / respawn / travel）"),
    ("legacy_value", "**原版值**"),
    ("new_value", "新引擎值"),
    ("match", "**是否一致**"),
    ("player_perceivable", "**玩家能否察觉**"),
    ("evidence", "证据"),
]


def _hdr(t, w=80):
    print("=" * w)
    print(t)
    print("=" * w)


def cmd_bag(a):
    _hdr("四种背包模型")
    print("模型: " + " · ".join(BAG_MODELS))
    print("\n字段: " + " · ".join(BAG_FIELDS))
    print("\n网格模型: " + " · ".join(BAG_GRID))
    print("\n重量/体积模型: " + " · ".join(BAG_WEIGHT))
    print(f"\n   {BAG_RULE}")
    return 0


def cmd_pickup(a):
    _hdr("🔴 拾取与满包行为")
    for f in PICKUP_FIELDS:
        print(f"   · {f}")
    print("\n`full_behavior`: " + " · ".join(FULL_BEHAVIOR))
    print("\n规则:")
    for r in FULL_RULE:
        print(f"   {r}")
    return 0


def cmd_sort(a):
    _hdr("🔴 稳定排序（**要写完整排序键**）")
    print("`stable_sort_key`: " + " · ".join(SORT_KEY))
    print("\n测试:")
    for t in SORT_TESTS:
        print(f"   · {t}")
    print("\n新增物品插入位置: " + " · ".join(INSERT_POS))
    print(f"\n   {SORT_RULE}")
    return 0


def cmd_drag(a):
    _hdr("拖拽（**目标槽判据状态机**）")
    for f in DRAG_FIELDS:
        print(f"   · {f}")
    print("\n规则:")
    for r in DRAG_RULE:
        print(f"   {r}")
    return 0


def cmd_equip(a):
    _hdr("🔴 装备切换（**输入确认 vs 效果生效**）")
    for f in EQUIP_FIELDS:
        print(f"   · {f}")
    print("\n规则:")
    for r in EQUIP_RULE:
        print(f"   {r}")
    return 0


def cmd_compare(a):
    _hdr("比较 UI")
    for f in COMPARE_FIELDS:
        print(f"   · {f}")
    print(f"\n   {COMPARE_RULE}")
    return 0


def cmd_skill(a):
    _hdr("技能树（**依赖图与回退路径**）")
    for f in SKILL_FIELDS:
        print(f"   · {f}")
    print("\n规则:")
    for r in SKILL_RULE:
        print(f"   {r}")
    return 0


def cmd_point(a):
    _hdr("🔴 配点四事务")
    for f in POINT_FIELDS:
        print(f"   · {f}")
    print("\n`preview` 三种:")
    for k, why in PREVIEW_KINDS:
        print(f"   {k:<22} {why}")
    print("\n批量加点: " + " · ".join(POINT_BATCH))
    return 0


def cmd_recalc(a):
    _hdr("重算时机（**决定体感**）")
    print("每次属性变化记录: " + " · ".join(RECALC_FIELDS))
    print("\n升级瞬间: " + " · ".join(LEVELUP_FIELDS))
    print("\n规则:")
    for r in RECALC_RULE:
        print(f"   {r}")
    return 0


def cmd_map(a):
    _hdr("地图与小地图（**不是同一坐标视图**）")
    for f in MAP_FIELDS:
        print(f"   · {f}")
    print("\n迷雾来源: " + " · ".join(FOG_SOURCES))
    print("\n小地图: " + " · ".join(MINIMAP_FIELDS))
    print("\n规则:")
    for r in MAP_RULE:
        print(f"   {r}")
    return 0


def cmd_path(a):
    _hdr("路径指引（**导航查询**）")
    for f in PATH_FIELDS:
        print(f"   · {f}")
    print("\n自定义图钉: " + " · ".join(PIN_FIELDS))
    print(f"\n   {PATH_RULE}")
    return 0


def cmd_shop(a):
    _hdr("商店交互")
    for f in SHOP_FIELDS:
        print(f"   · {f}")
    print("\n规则:")
    for r in SHOP_RULE:
        print(f"   {r}")
    return 0


def cmd_death(a):
    _hdr("🔴 死亡流程（**可观测片段**）")
    for f in DEATH_FIELDS:
        print(f"   · {f}")
    print("\n规则:")
    for r in DEATH_RULE:
        print(f"   {r}")
    return 0


def cmd_respawn(a):
    _hdr("重生（**显式事务**）")
    for f in RESPAWN_FIELDS:
        print(f"   · {f}")
    print("\n掉落: " + " · ".join(RESPAWN_DROP))
    print(f"\n   {RESPAWN_RULE}")
    return 0


def cmd_travel(a):
    _hdr("🔴 快速旅行（**要推进世界**）")
    for f in TRAVEL_FIELDS:
        print(f"   · {f}")
    print("\n跟随实体: " + " · ".join(TRAVEL_ENTITIES))
    print("\n规则:")
    for r in TRAVEL_RULE:
        print(f"   {r}")
    return 0


def cmd_init(a):
    os.makedirs(os.path.dirname(a.init) or ".", exist_ok=True)
    with open(a.init, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow([k for k, _ in FIELDS])
        w.writerow(["TODO"] * len(FIELDS))
    print(f"已生成库存/流程表: {a.init}")
    print("\n⚠️ 十五域：bag / pickup / sort / drag / equip / compare / skill / "
          "point / recalc / map / path / shop / death / respawn / travel")
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

    mismatch, no_legacy, unclear = [], [], []
    for i, r in enumerate(rows, 1):
        m = g(r, "match").lower()
        if m not in ("yes", "y", "true", "是", "一致"):
            mismatch.append(i)
        if not g(r, "legacy_value") or g(r, "legacy_value") == "TODO":
            no_legacy.append(i)
        pp = g(r, "player_perceivable")
        if pp in ("", "todo", "unknown"):
            unclear.append(i)

    print("=" * 76)
    print(f"库存/流程 · {len(rows)} 条")
    print("=" * 76)
    if mismatch:
        print(f"\n🚫 **不一致** {len(mismatch)} 条（行 {mismatch[:15]}）")
    if no_legacy:
        print(f"\n❌ {len(no_legacy)} 条缺**原版值**（行 {no_legacy[:15]}）")
    if unclear:
        print(f"\n⚠️  {len(unclear)} 条**未判定玩家能否察觉**（行 {unclear[:15]}）")

    if not (mismatch or no_legacy):
        print("\n✅ 库存/流程：一致且原版值完整")

    print("\n🔑 **全量刷新导致选中项跳格 —— 数据对也是手感 BUG。**")
    print("   **重生是显式事务，不是一句重置。**")
    print("   **快速旅行是模拟模式入口，不是地图 UI。**")
    return 1 if (a.gate and (mismatch or no_legacy)) else 0


def main():
    ap = argparse.ArgumentParser(description="库存/配点/地图/死亡流程")
    ap.add_argument("--bag", action="store_true")
    ap.add_argument("--pickup", action="store_true")
    ap.add_argument("--sort", action="store_true")
    ap.add_argument("--drag", action="store_true")
    ap.add_argument("--equip", action="store_true")
    ap.add_argument("--compare", action="store_true")
    ap.add_argument("--skill", action="store_true")
    ap.add_argument("--point", action="store_true")
    ap.add_argument("--recalc", action="store_true")
    ap.add_argument("--map", action="store_true")
    ap.add_argument("--path", action="store_true")
    ap.add_argument("--shop", action="store_true")
    ap.add_argument("--death", action="store_true")
    ap.add_argument("--respawn", action="store_true")
    ap.add_argument("--travel", action="store_true")
    ap.add_argument("--init")
    ap.add_argument("--check")
    ap.add_argument("--gate", action="store_true")
    a = ap.parse_args()
    fns = {"bag": cmd_bag, "pickup": cmd_pickup, "sort": cmd_sort,
           "drag": cmd_drag, "equip": cmd_equip, "compare": cmd_compare,
           "skill": cmd_skill, "point": cmd_point, "recalc": cmd_recalc,
           "map": cmd_map, "path": cmd_path, "shop": cmd_shop,
           "death": cmd_death, "respawn": cmd_respawn, "travel": cmd_travel}
    for k, fn in fns.items():
        if getattr(a, k):
            return fn(a)
    if a.init:
        return cmd_init(a)
    if a.check:
        return cmd_check(a)
    print("❌ 需要 --bag / --pickup / --sort / --drag / --equip / --compare / "
          "--skill / --point / --recalc / --map / --path / --shop / --death / "
          "--respawn / --travel / --init / --check 之一")
    return 2


if __name__ == "__main__":
    sys.exit(main())
