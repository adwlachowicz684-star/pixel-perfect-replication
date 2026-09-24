#!/usr/bin/env python3
"""时间推进语义 + 动态经济（第十五轮 A / B 类）。

**🔑 本轮核心**：
> 从"**存在某系统**"升级为"**一次推进到底发生了什么**"。
> **"已记录系统存在"不等于"已记录推进语义"**。

**🔴 A 类**：
> **时间跳跃不是等待的快捷方式，而是一次批量世界模拟。**
> 若日志只写"时间前进了 6 小时"，不能判断守卫换班、作物生长、
> 任务截止、商店补货、天气滚动和存档事件是否按原引擎顺序触发。
> 🔴 **暂停不是统一的全局停止，而是按系统白名单冻结。**

**🔴 B 类**：
> **静态价格表只是商品目录，价格冲击函数才是系统。**
> 不能只记最终成交价，**必须记录计算链** ——
> 否则一个等价价格可能来自完全不同的冲击反馈。
> 🔴 **若原引擎没有恢复，必须写 `recovery: none`，
> 不能"为了更真实"自行补充。**

用法:
  game_world_economy.py --clock      # 🔴 时间基（**不是昼夜循环**）
  game_world_economy.py --pause      # 🔴 暂停**白名单**
  game_world_economy.py --calendar   # 离散日期 + **连续分数时间**
  game_world_economy.py --season     # 气象季节 vs **玩法季节**
  game_world_economy.py --jump       # 🔴 时间跳跃是**批量模拟**
  game_world_economy.py --schedule   # 商店/NPC/任务**共享同一时钟**
  game_world_economy.py --weathertime# 天气×时间**二维状态表**
  game_world_economy.py --price      # 🔴 价格**计算链**
  game_world_economy.py --trade      # 买卖量 → **可回放价格曲线**
  game_world_economy.py --recovery   # 市场恢复（**砸盘后世界回不回来**）
  game_world_economy.py --currency   # 🔴 多货币是**兑换语义**
  game_world_economy.py --depth      # 市场深度与套利
  game_world_economy.py --init ledger/world_economy.csv
  game_world_economy.py --check ledger/world_economy.csv --gate

退出码: 0 通过 / 1 缺项 / 2 用法错误
"""
import argparse
import csv
import os
import sys

# 🔴 时间基
CLOCK_FIELDS = [
    '**每秒真实时间对应多少游戏时间**', '**固定步长**', '**最大追赶步数**',
    '**昼夜各阶段分钟数**', '**是否可变流速**', '暂停条件',
    '**暂停时仍运行/冻结的系统白名单**', '**时间缩放能否叠加**',
]

CLOCK_RULE = [
    '🔴 首要字段**不是"昼夜循环"，而是游戏分钟精度的时间基**',
    '🔑 要测现实秒与游戏秒比例、一天总游戏分钟、日出/日落时刻、'
    '黄昏/夜晚/黎明过渡区间',
    '🔑 很多项目的"现实 1 秒 = 游戏 1 分钟"**不是全局规则** —— '
    '白天、夜晚、加载或特定模式可能用不同倍率',
    '🔴 **即使平均速度相同，逐帧记录也会因舍入不同而在多日模拟后漂移**',
]

# 🔴 暂停白名单
PAUSE_SYSTEMS = [
    '对话计时', '**中毒/流血**', 'buff', '建筑生产', '**云存档时钟**',
    '平台时间', '**每日奖励**', '季节事件', '网络同步', '粒子',
    '动画冷却', '**商品补货**', '**作物生长**', '**任务截止**', 'NPC 记忆',
]

PAUSE_TESTS = [
    '**打开背包时敌人是否继续攻击**',
    '**对话时昼夜是否继续**',
    '**暂停后是否重算未触发事件**',
    '**离线期间按现实时间还是最后游戏时间结算**',
]

PAUSE_RULE = '🔴 若原引擎暂停时仍计算每日重置，而复刻全部冻结 → '
'**每日商店、奖励和活动会在玩家体验上错位**'

# 日历
CALENDAR_FIELDS = [
    '纪元/年/月/日/星期', '**每月天数**', '季节边界',
    '**闰年或周期年规则**', '节日日期', '节日窗口与永久/一次性标志',
    '跨年滚动', '**存档基准日期**',
]

CALENDAR_RULE = [
    '🔑 日历必须**同时记录离散日期与连续分数时间** —— '
    '年/月/日/时/分只是可读表示，判定和事件通常用**分数日、周期日或内部 tick**',
    '🔑 要记闰日策略、年份循环、月份长度、周起始日',
    '🔑 若真实日历参与活动判定 → 还要记**客户端日期可改、跨时区旅行、'
    '云存档上传/下载时间**',
    '🔑 若是纯虚构日历 → 必须保存**虚构日期到版本内部 tick 的映射**，'
    '避免补丁改变日期解释',
]

# 季节
SEASON_TWO = [
    ('**气象季节**', '视觉边界'),
    ('**玩法季节**', '玩法边界'),
]

SEASON_FIELDS = [
    '切换时刻', '过渡时长', '**是否按地理纬度**', '海拔', '区域',
    '**地下层**', '室内', '**梦境/灵魂世界独立计时**',
]

SEASON_VISUAL = [
    '天空', '太阳轨迹', '光照方向', '雾', '云', '植被', '地表贴图',
    '**NPC 服装**', '粒子', '生物群落',
]

SEASON_GAMEPLAY = [
    '温度', '饥饿', '疲劳', '**作物速度**', '**敌人种类**', '物品生成',
    '任务开启', '**声望效果**', '节日', '**商店价格**',
]

SEASON_RULE = '🔑 季节切换若采用 hysteresis → 要记进入/退出阈值、'
'最小停留时长、受迫切换条件、跨季节睡眠及**版本首次启动的默认值**'

# 🔴 时间跳跃
JUMP_FIELDS = [
    '跳跃前时间', '跳跃后时间', '**步长**',
    '**每步是否运行 NPC AI / 作物 / 天气 / 事件 / 冷却**',
    '是否允许中断', '**是否补发错过事件**',
    '**是否执行多次午夜结算**',
    '掉血、饥饿、疲劳、感染、buff 是**按跳跃总量结算还是按隐藏分钟结算**',
]

JUMP_RULE = [
    '🔴 **时间跳跃不是等待的快捷方式，而是一次批量世界模拟**',
    '🔑 原引擎可以在睡觉、等待、快速旅行时**逐分钟 tick**，'
    '也可以按"**到达时刻重计算**"，还可能**冻结玩家外的世界**',
    '🔑 存档也应记"**上次离开时的时间**"和"**重入时的时间**" —— '
    '用于区分真实时间流逝与游戏时间流逝',
]

JUMP_TESTS = [
    '**最后一分钟入睡**', '跨午夜', '跨季节', '跨闰年',
    '最小睡眠', '最大睡眠', '**被打断睡眠**', '**读档续睡**',
]

# 共享时钟
SCHEDULE_RULE = [
    '🔴 **商店营业时间、NPC 日程和任务截止必须共享同一时钟** —— '
    '这是 A 类最容易复刻漏掉的真实细节',
    '🔑 原引擎可能让店门在**时刻到达时关闭**，也可能**当前交易完成后再关门**',
    '🔑 NPC 可能按"**到达地点**"切换日程，也可能按"**离开当前行为**"切换',
    '🔑 任务截止可能在**一天开始时**失败，也可能在**午夜结束时**、'
    '**事件 tick 中**或**玩家进入某个区域时**失败',
]

SCHEDULE_FIELDS = [
    '每个 NPC 的时间表', '旅行路线',
    '例外条件（**天气 / 战斗 / 节日 / 派系关系 / 玩家在场**）',
    '**迟到宽容**', '**换班瞬间可到达位置**',
    '**玩家正在与 NPC 交易/对话时日程到期**的仲裁',
]

# 天气×时间
WEATHER_TIME_MATRIX = [
    '🔑 **二维状态表**：维度一为昼夜/季节，维度二为天气类型/强度',
    '🔑 每格记录：能见度 · 湿度 · 温度 · 风 · 光衰减 · **火把燃料** · '
    '植物 · 动物行为 · **敌人生成** · **区域准入** · 音乐 · 天气预警',
    '🔑 天气变化是**连续混合还是状态切换**、混合坐标',
    '🔑 极端天气持续时间、不可跳过演出、玩家触发区、区域边界规则、'
    '**室内外判定**',
    '🔑 快速旅行时的**预报修正**，以及天气是否**反过来修改昼夜光照**',
]

WEATHER_TRANSITION = [
    '当前天气', '目标天气',
    '**过渡方式**（淡入 / 混音 / 粒子叠加 / 离散切换）',
    '过渡时间', '是否可中断', '**预警提前量**',
    '**玩家能否通过睡眠/快速旅行跳过预警**', '**预报准确率**',
    '天气区域边界', '室内外判定', '相机/后处理过渡与音频交叉淡化',
]

WEATHER_RULE = '🔑 若过渡越过午夜、季节或任务触发点 → '
'**必须记录中间状态是否被保存**'

# 🔴 价格
PRICE_FIELDS = [
    '基础价', '当前买价', '当前卖价', '**地区价差**', '税/手续费',
    '重量与运输成本', '**玩家声望折扣**', '**供需量**', '库存', '日需求量',
    '**恢复速率**', '上下限', '黑市标志', '稀有度与限购',
]

PRICE_RULE = [
    '🔴 **不能只记最终成交价，必须记录计算链** —— '
    '否则一个等价价格可能来自完全不同的冲击反馈',
    '🔑 B 类应从"商品价格"升级为"**市场状态**"',
]

# 交易
TRADE_FIELDS = [
    '玩家买入对库存与价格的**逐项影响**',
    '卖出对回收价与库存的影响',
    '**商店买回自己的库存 / 其他玩家可购买库存是否共享**',
    '**价格冲击是线性、分段、对数还是有交易深度**',
    '**单次交易是否先更新库存再算价**',
    '**多件同时购买是逐件重算还是统一价格**',
    '**折扣取整发生在单价、小计、税费还是最终支付**',
]

TRADE_EDGE = [
    '零库存', '**一件库存**', '**负数库存（是否允许）**', '整数除零',
    '超大额交易', '**批量卖出导致回收价触底**', '买入导致无限库存',
    '**玩家是否可通过反复买卖刷价**',
]

# 恢复
RECOVERY_FIELDS = [
    '每商店库存恢复周期', '恢复起始时刻',
    '**是否按游戏时间 / 现实时间 / 在线时间**', '**是否暂停时恢复**',
    '恢复速率恒定或**按缺口比例**',
    '**是否受季节/节日/战争/派系控制**',
    '上限是每商品还是每商店', '**恢复是否触发事件**',
]

RECOVERY_PRICE = [
    '半衰期', '最低/最高锚点', '随机扰动',
    '**记忆窗口（过去 N 天还是 EMA）**', '长期平衡价', '玩家声望偏移',
]

RECOVERY_RULE = [
    '🔑 市场恢复决定"**砸盘后世界还会不会回来**"',
    '🔴 **若原引擎没有恢复，必须在 `economy.yaml` 写 `recovery: none`** —— '
    '**不能"为了更真实"自行补充**',
]

# 🔴 多货币
CURRENCY_FIELDS = [
    '货币种类', '获得/消耗/显示优先级',
    '**兑换固定汇率或浮动汇率**', '**买卖价差**', '手续费', '兑换上限',
    '**整数舍入方向**', '**找零规则**', '不可兑换货币', '地区专属货币',
    '过期货币', '通货膨胀事件', '**价格标签与结算是否可能使用不同货币**',
]

CURRENCY_TESTS = [
    '**显示金币 99，实际扣除混合货币**',
    '**零钱不足是否取消交易**',
    '**信用/欠条何时扣还**',
    '**任务奖励货币与商店接受货币不同**',
]

CURRENCY_RULE = '🔴 **多货币不是多列数字，而是兑换与支付语义**'

# 市场深度
DEPTH_TESTS = [
    '单笔 1 件', '单笔上限', '分批', '**连续买入直到缺货**',
    '**连续卖出直到价格触底**', '跨城搬运', '**利用节日价差**',
    '**利用暂停/睡眠刷新**', '**跨平台/云存档转移货币**',
    '**修改系统时间套利**',
]

DEPTH_FIELDS = [
    '市场价格是否**全球同步 / 地区独立 / 实例独立**',
    'NPC 间交易、巡逻商人、战争、自然灾害是否影响市场',
]

DEPTH_RULE = '🔴 **没有市场深度的世界会表现为"玩家无限买入，'
'商人永远不缺货"** —— 这是与动态经济最典型的偏离'

CONFLICTS = [
    '❌ 只记录"有昼夜循环"而无分钟基',
    '❌ **用浮点秒直接比较日期**',
    '❌ 把不同系统改成统一时钟',
    '❌ **把睡眠做成简单时间加法而不重放事件**',
    '❌ 用插值代替离散时刻触发',
    '❌ 把经济表"简化成静态价格"',
    '❌ **给每个商人补上现代供需算法**',
    '❌ 用浮点均价跨版本比较',
    '❌ 把不同地区市场统一',
    '❌ **自动把负数库存钳制为 0**',
    '❌ **把玩家套利漏洞修复成"更合理"的玩法**',
    '❌ 未经记录便让商店跨版本补货',
    '❌ **擅自给没有恢复的市场加恢复**',
]

FIELDS = [
    ('item_id', '项编号'),
    ('domain', '域（clock / pause / calendar / season / jump / schedule / '
               'weathertime / price / trade / recovery / currency / depth）'),
    ('legacy_value', '**原版值**'),
    ('new_value', '新引擎值'),
    ('match', '**是否一致**'),
    ('advance_log', '**推进日志（时间/事件序号/状态哈希）**'),
    ('evidence', '证据'),
]


def _hdr(t, w=80):
    print('=' * w)
    print(t)
    print('=' * w)


def cmd_clock(a):
    _hdr('🔴 时间基（**不是昼夜循环**）')
    for f in CLOCK_FIELDS:
        print(f'   · {f}')
    print('\n规则:')
    for r in CLOCK_RULE:
        print(f'   {r}')
    return 0


def cmd_pause(a):
    _hdr('🔴 暂停（**白名单**）')
    print('系统: ' + ' · '.join(PAUSE_SYSTEMS))
    print('\n测试: ' + ' · '.join(PAUSE_TESTS))
    print(f'\n   {PAUSE_RULE}')
    return 0


def cmd_calendar(a):
    _hdr('日历（**离散 + 连续分数**）')
    for f in CALENDAR_FIELDS:
        print(f'   · {f}')
    print('\n规则:')
    for r in CALENDAR_RULE:
        print(f'   {r}')
    return 0


def cmd_season(a):
    _hdr('季节（**两套边界**）')
    for k, why in SEASON_TWO:
        print(f'   {k:<14} {why}')
    print('\n字段: ' + ' · '.join(SEASON_FIELDS))
    print('\n视觉: ' + ' · '.join(SEASON_VISUAL))
    print('\n玩法: ' + ' · '.join(SEASON_GAMEPLAY))
    print(f'\n   {SEASON_RULE}')
    return 0


def cmd_jump(a):
    _hdr('🔴 时间跳跃（**批量模拟**）')
    for f in JUMP_FIELDS:
        print(f'   · {f}')
    print('\n规则:')
    for r in JUMP_RULE:
        print(f'   {r}')
    print('\n边界: ' + ' · '.join(JUMP_TESTS))
    return 0


def cmd_schedule(a):
    _hdr('商店 / NPC / 任务（**共享同一时钟**）')
    print('规则:')
    for r in SCHEDULE_RULE:
        print(f'   {r}')
    print('\n字段: ' + ' · '.join(SCHEDULE_FIELDS))
    return 0


def cmd_weathertime(a):
    _hdr('天气 × 时间（**二维状态表**）')
    for m in WEATHER_TIME_MATRIX:
        print(f'   {m}')
    print('\n过渡: ' + ' · '.join(WEATHER_TRANSITION))
    print(f'\n   {WEATHER_RULE}')
    return 0


def cmd_price(a):
    _hdr('🔴 价格（**计算链**）')
    for f in PRICE_FIELDS:
        print(f'   · {f}')
    print('\n规则:')
    for r in PRICE_RULE:
        print(f'   {r}')
    return 0


def cmd_trade(a):
    _hdr('买卖量 → **可回放价格曲线**')
    for f in TRADE_FIELDS:
        print(f'   · {f}')
    print('\n边界: ' + ' · '.join(TRADE_EDGE))
    return 0


def cmd_recovery(a):
    _hdr('市场恢复（**砸盘后世界回不回来**）')
    for f in RECOVERY_FIELDS:
        print(f'   · {f}')
    print('\n价格恢复: ' + ' · '.join(RECOVERY_PRICE))
    print('\n规则:')
    for r in RECOVERY_RULE:
        print(f'   {r}')
    return 0


def cmd_currency(a):
    _hdr('🔴 多货币（**兑换语义**）')
    for f in CURRENCY_FIELDS:
        print(f'   · {f}')
    print('\n测试: ' + ' · '.join(CURRENCY_TESTS))
    print(f'\n   {CURRENCY_RULE}')
    return 0


def cmd_depth(a):
    _hdr('市场深度与套利')
    print('测试: ' + ' · '.join(DEPTH_TESTS))
    print('\n字段: ' + ' · '.join(DEPTH_FIELDS))
    print(f'\n   {DEPTH_RULE}')
    return 0


def cmd_init(a):
    os.makedirs(os.path.dirname(a.init) or '.', exist_ok=True)
    with open(a.init, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow([k for k, _ in FIELDS])
        w.writerow(['TODO'] * len(FIELDS))
    print(f'已生成世界/经济表: {a.init}')
    print('\n⚠️ 十二域：clock / pause / calendar / season / jump / schedule / '
          'weathertime / price / trade / recovery / currency / depth')
    return 0


def cmd_check(a):
    if not os.path.exists(a.check):
        print(f'❌ 文件不存在: {a.check}')
        return 2
    with open(a.check, encoding='utf-8', errors='replace', newline='') as f:
        rows = list(csv.DictReader(f))
    if not rows:
        print('❌ 空表')
        return 1

    def g(r, k):
        return (r.get(k) or '').strip()

    mismatch, no_legacy, no_log = [], [], []
    for i, r in enumerate(rows, 1):
        m = g(r, 'match').lower()
        if m not in ('yes', 'y', 'true', '是', '一致'):
            mismatch.append(i)
        if not g(r, 'legacy_value') or g(r, 'legacy_value') == 'TODO':
            no_legacy.append(i)
        lg = g(r, 'advance_log')
        if not lg or lg == 'TODO':
            no_log.append(i)

    print('=' * 76)
    print(f'世界/经济 · {len(rows)} 条')
    print('=' * 76)
    if mismatch:
        print(f'\n🚫 **不一致** {len(mismatch)} 条（行 {mismatch[:15]}）')
    if no_legacy:
        print(f'\n❌ {len(no_legacy)} 条缺**原版值**（行 {no_legacy[:15]}）')
    if no_log:
        print(f'\n⚠️  {len(no_log)} 条**缺推进日志**（行 {no_log[:15]}）')
        print('   → 🔴 必须保存 advance_log：时间/事件序号/状态哈希逐帧一致')

    if not (mismatch or no_legacy):
        print('\n✅ 世界/经济：一致且原版值完整')

    print('\n🔑 **时间跳跃是批量模拟，不是时间加法。**')
    print('   **若原引擎没有恢复机制，写 recovery: none，不要自行补充。**')
    return 1 if (a.gate_check and (mismatch or no_legacy)) else 0


def main():
    ap = argparse.ArgumentParser(description='时间推进与动态经济')
    ap.add_argument('--clock', action='store_true')
    ap.add_argument('--pause', action='store_true')
    ap.add_argument('--calendar', action='store_true')
    ap.add_argument('--season', action='store_true')
    ap.add_argument('--jump', action='store_true')
    ap.add_argument('--schedule', action='store_true')
    ap.add_argument('--weathertime', action='store_true')
    ap.add_argument('--price', action='store_true')
    ap.add_argument('--trade', action='store_true')
    ap.add_argument('--recovery', action='store_true')
    ap.add_argument('--currency', action='store_true')
    ap.add_argument('--depth', action='store_true')
    ap.add_argument('--init')
    ap.add_argument('--check')
    ap.add_argument('--gate-check', action='store_true')
    a = ap.parse_args()
    fns = {'clock': cmd_clock, 'pause': cmd_pause, 'calendar': cmd_calendar,
           'season': cmd_season, 'jump': cmd_jump, 'schedule': cmd_schedule,
           'weathertime': cmd_weathertime, 'price': cmd_price,
           'trade': cmd_trade, 'recovery': cmd_recovery,
           'currency': cmd_currency, 'depth': cmd_depth}
    for k, fn in fns.items():
        if getattr(a, k):
            return fn(a)
    if a.init:
        return cmd_init(a)
    if a.check:
        return cmd_check(a)
    print('❌ 需要 --clock / --pause / --calendar / --season / --jump / '
          '--schedule / --weathertime / --price / --trade / --recovery / '
          '--currency / --depth / --init / --check 之一')
    return 2


if __name__ == '__main__':
    sys.exit(main())
