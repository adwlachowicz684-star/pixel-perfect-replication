#!/usr/bin/env python3
"""解锁节奏、输入反馈、跨系统仲裁、教学与存档体验（第十三轮 C / D / E / F / G / H）。

**🔑 C 类核心**：
> **银河恶魔城式进度不能只记录「几时获得能力」，必须记录世界图的变化。**
> 仅记录「获得钩爪」无法回答「**错过支线后还能否回来**」。

**🔑 D 类核心**：
> **输入到反馈必须按动作分类，而非只测一条链路。**
> 🔴 **「手感」可量化为允许偏差区间，而非一个目标值** ——
> 复刻目标应是**分布逐动作落入原版容差**，而不只是平均相等。

**🔑 H 类核心**：
> **跨系统动作冲突仲裁** —— 新能力不应直接写入角色状态，
> 而应通过**动作仲裁层**。
> 🔑 **「玩家看起来能做」不等于能力合同允许。**

用法:
  game_progress_input.py --gate      # 🔴 能力门与**可到达集合**
  game_progress_input.py --lock      # 硬锁 vs 软锁（**玩家验证路径**）
  game_progress_input.py --unlock    # 商店/技能解锁是**同一时间线**
  game_progress_input.py --tutorial  # 首次使用引导三元组
  game_progress_input.py --input     # 🔴 按动作分类的输入反馈
  game_progress_input.py --lost      # **输入丢失不是 bug，是仲裁**
  game_progress_input.py --refresh   # 🔴 帧率相关输入（最高优先级反例）
  game_progress_input.py --party     # 队友可见性是**信息层级**
  game_progress_input.py --reconnect # 断线重连四类
  game_progress_input.py --teach     # 隐性教学（不说话的教学）
  game_progress_input.py --save      # 存档/读档的**体验**
  game_progress_input.py --arbiter   # 🔴 跨系统动作仲裁层
  game_progress_input.py --spectate  # 观演与**比赛终结三帧**
  game_progress_input.py --init ledger/progress_input.csv
  game_progress_input.py --check ledger/progress_input.csv --gate

退出码: 0 通过 / 1 缺项 / 2 用法错误
"""
import argparse
import csv
import os
import sys

# 🔴 能力门
GATE_FIELDS = [
    'acquire_time_since_start', 'level_or_event_id',
    'delivery_cutscene_can_skip', '**first_practice_room_id**',
    'mandatory_or_optional', '**retroactive_access**',
    'affected_actions', 'affected_traversal', 'affected_combat',
    'affected_interaction',
]

GATE_GRAPH = [
    '获得能力前后的**强连通分量**', '**最短路径**',
    '原本不可达的拾取', '**捷径**', 'Boss', '商店', '回城点',
]

GATE_RULE = '🔑 **仅记录「获得钩爪」无法回答「错过支线后还能否回来」**'

# 硬锁/软锁
HARD_LOCKS = [
    '无法开门', '碰撞墙', '技能未激活', '任务门未开', '钥匙缺失',
]

SOFT_LOCKS = [
    '**怪物太强**', '**资源不足**', '**隐藏入口**', '**缺少提示**',
    '**设计上允许但玩家不知道**',
]

LOCK_FIELDS = [
    'lock_kind', 'can_be_bypassed', 'is_visible_before_acquire',
    'can_be_seen_from_safe_position', 'hint_channel',
    'first_hint_time', 'retry_hint_time', 'max_hint_count',
    'hint_can_be_disabled',
]

LOCK_TESTS = [
    '**从门两侧进入时表现是否一致**',
    '**死亡、退出、读档后提示状态是否重复**',
]

LOCK_RULE = '🔑 硬锁与软锁是**玩家验证路径，不是策划意图**'

# 解锁时间线
UNLOCK_FIELDS = [
    'unlock_event', 'earliest_time', 'repeatable', 'price_kind',
    'price_after_discount', 'stock_refill_cycle', 'hidden_until_flag',
    'purchase_also_unlocks', 'removed_after_flag', 'save_persistence',
]

UNLOCK_TIME = [
    '**首次可见**', '**首次可购买**', '**首次理解用途**',
]

UNLOCK_RULE = '🔑 商店和技能解锁**不是独立表格，而是同一时间线**'

# 首次使用引导
TUTORIAL_TRIPLE = [
    '**首个练习空间是否安全**', '**敌人是否可击败**', '**失败后能否立即重试**',
]

TUTORIAL_FIELDS = [
    '是否强制', '练习中死亡是否回到门后', '跳过状态是否写入',
    '**二周目是否再显示**',
]

TUTORIAL_RULE = '🔑 不应只记录「弹出教程文本」 —— '
'是练习、提示、**允许失败**的三元组'

# 🔴 输入反馈
INPUT_ACTIONS = [
    'UI', '**攻击**', '**跳跃**', '**交互**', '菜单',
]

INPUT_METRICS = [
    '**按键至视觉反应**', '**缓冲窗口**', '**最长保留时间**',
    '**打断丢失**', '**重复输入合并**',
]

INPUT_SAMPLING = [
    '🔑 对原版 **30 次以上随机采样**',
    '至少记录 p50 · p95 · **最大延迟** · **延迟抖动** · **首个有效帧** · '
    '**判定宽容半径** · **取消窗口** · **恢复窗口** · **缓冲窗口**',
]

INPUT_RULE = '🔴 **复刻目标应是分布逐动作落入原版容差，而不只是平均相等**'

# 输入丢失
LOST_CONTEXTS = [
    '普通攻击', '**蓄力**', '换弹', '交互', '**受伤**', '硬直', '死亡',
    '动画取消', '切武器', '开地图', '暂停', '**失焦**',
]

LOST_INPUTS = [
    '方向', '跳跃', '闪避', '攻击', '瞄准', '特殊技能',
]

LOST_RULE = [
    '🔑 分别记录**丢失 / 排队 / 立即执行 / 延后执行**',
    '🔑 记录输入是否**允许触发动画但暂不产生判定** —— '
    '避免「角色已经转身，伤害却未发生」',
    '🔑 **攻击中的输入丢失不是 bug 的同义词，而是项目自定义仲裁**',
]

# 🔴 帧率
REFRESH_RATES = ['30', '60', '120', '144', '240', '**可变刷新率 VRR**']

REFRESH_TESTS = [
    '显示器**略低于**、**等于**、**高于**游戏输出时',
]

REFRESH_FIELDS = [
    'input_frame_index', 'logic_frame_index', 'render_frame_index',
    'vsync_state', 'refresh_rate', 'time_scale',
]

REFRESH_RULE = [
    '🔴 **禁止把逻辑 tick 与渲染帧号混用**',
    '🔑 若某动作窗口以**浮点秒存储、每秒多次轮询** → '
    '**不同刷新率可能先错过窗口**',
    '🔑 若以**固定逻辑帧**存储 → **慢动作和变速时间又可能错位**',
]

# 队友可见性
PARTY_VIS = [
    '血条是否显示**百分比**', '是否显示护盾', '是否显示状态',
    '名字是否始终显示 / **战斗时显示** / **远离时隐藏**',
    '**俯视标记是否保留距离、方向和高度**',
    '**穿墙是否只显示方向 / 只显示距离 / 完全隐藏**',
    '隐身、死亡、**载具内**、**观战**、**离队**时规则是否不同',
    '**HUD 与镜头的可见性能否分别配置**',
]

PARTY_XRAY = [
    '颜色', '材质', '透明物体', '玻璃', '水', '镜面',
    '**遮挡 LOD**', '**慢动作中的表现**',
]

PARTY_INTERACT = [
    '复活请求', '**复活占用时间**', '可被中断者', '可移动尸体', '共享掉落',
    '**拾取优先权**', '交易', '租借', '队伍 HP 共享', '经验共享',
    '仇恨共享', '敌意共享', '踢出投票', '举报来源', '屏蔽',
    '跨平台名称', '断线保留',
]

PARTY_TESTS = [
    '复活是否在 **BOSS 转换 / 慢动作 / 过场 / 载具 / 区域边界**仍有效',
    '队友处于「**倒地**」时是否仍算存活用于**任务判定**',
    '**踢出是否允许最终成员踢自己**',
    '**共享资源是否会产生同帧舍入漂移**',
]

# 匹配与重连
QUEUE_FIELDS = [
    'queue_state', 'region', 'ping_bucket', 'skill_or_rank_bucket', 'mode',
    'party_size', 'platform_match', 'cross_input_match',
    '**estimated_wait_visible**', '**estimated_formula**',
    'queue_can_be_cancelled', 'cancel_cost', 'search_timeout',
    'backfill_policy',
]

QUEUE_RULE = [
    '🔑 若原作允许匹配后取消但**不返还排队位置**，复刻成「立即取消」→ '
    '**破坏等待感**',
    '🔑 若显示静态「约 1 分钟」，**不能证明原作有动态预测**',
]

RECONNECT_FIELDS = [
    '检测心跳', '超时', '自动重连次数', '手动重连',
    '**恢复的是完整快照还是最近关键帧**', '是否补帧',
    '输入队列是否恢复', '**相机是否跳到当前视角**', '观战者是否保留',
    '**正在施法/蓄力/交互/过场如何恢复**', '随机种子是否同步',
    '是否判负或扣信用分', '重连后是否可立即行动',
]

# 隐性教学
TEACH_CHANNELS = [
    '**视觉对比**', '**材质变化**', '**声音变化**', '可破坏反馈',
    '敌人反应', '安全区', '**死亡位置**', '地图标记', '镜头构图',
    '**首个练习场**',
]

TEACH_FIELDS = [
    'intent', 'channel', 'is_optional', 'can_be_missed',
    'visible_before_ability', 'revisit_feedback', 'does_it_block_control',
]

TEACH_RULE = [
    '🔑 一堵**无法破坏的墙**与一扇**暂时无法打开的门**可能使用'
    '**相同视觉符号，但语义完全不同**',
    '🔑 后者还应检查**玩家重访时的反馈变化**',
]

DEATH_TEACH = [
    '玩家首次失败区域', '**死亡动画是否带信息**',
    '**检查点是否故意靠近机制**', '重生后是否给予**无惩罚练习**',
    '是否变化敌人配置', '是否给出**延迟提示**', '是否提供可查阅说明',
]

DEATH_TEACH_RULE = '🔑 应区分「**故意让玩家死一次学会机制**」和'
'「**仅因判定苛刻死亡**」 —— 二者都可能成立，但**不能把一个改成另一个**'

NPC_HINT = [
    '首次触发', '**重复触发冷却**', '玩家方向', '视线', '距离',
    '是否正在战斗', '是否已经完成目标', '是否已有更强提示',
    '语音优先级', '字幕和图标是否同步', '能否立即重看',
    '**重复查看是否播放完整台词或只给摘要**',
]

HINT_DISAPPEAR = [
    '获得能力后永久消失', '**本区域后消失**', '任务推进后消失',
    '玩家主动关闭', '**玩家连续失败后才出现**', '**同一提示最大次数**',
    '**新游戏+是否重置**', '**不同难度是否共享状态**',
    '**读档后是否重复**', '**暂停或切语言后是否恢复**',
]

HINT_RULE = [
    '🔑 提示消失机制**比首次提示更容易被遗漏**',
    '🔑 若提示只依赖**局部变量**，退出区域后状态可能**丢失**',
    '🔑 若依赖**全局状态**，玩家换路线又可能**永远错过**',
]

# 存档体验
SAVE_TRIGGERS = [
    '手动', '检查点', '任务完成', '进出区域', '退出', '定时', '进入菜单',
]

SAVE_FIELDS = [
    '触发源', '**是否冻结世界**',
    '**是否在战斗/过场/载具/动画/菜单/上传中允许**',
    '覆盖确认', '失败重试', '**崩溃临时档**', '跨槽复制', '删除确认',
]

LOAD_FIELDS = [
    '加载画面信息密度', '**原版玩法预览**', '**缩略图生成时刻**',
    '截图或动态预览', '时间戳', '区域名', '任务名', '玩家朝向',
    '自动/手动/恢复标签', '**首次与重复加载表现**',
]

CONFLICT_FIELDS = [
    '本地时间戳', '云时间戳', '**最后设备**', '文件校验',
    '**会话仍在运行**', '槽位占用', '版本', 'DLC', '平台',
]

CONFLICT_RULE = [
    '🔑 冲突界面是**保留两者 / 复制为新槽 / 按时间覆盖 / 逐字段合并**',
    '🔑 **玩家取消同步后是否反复提示**',
    '🔑 **离线保存后联网是否产生循环覆盖**',
    '🔑 普通版本号不足以解决字段级冲突 → 推荐 `entity_version` 与 `field_etag`',
    '🔴 **存档冲突必须保留原选择，不能替玩家决定**',
]

# 🔴 动作仲裁
ARBITER_ACTIONS = [
    '移动', '跳跃', '冲刺', '钩爪', '游泳', '攀爬', '载具', '攻击',
    '交互', '拾取', '菜单', '受伤', '过场', '对话', '拍照',
]

ARBITER_FIELDS = [
    'action_id', '**start_intent_frame**', '**validation_frame**',
    '**execution_frame**', 'cancels', 'cannot_cancel',
    '**exclusive_group**', 'priority', 'shared_animation', '**revert_frame**',
]

ARBITER_RULE = '🔑 **谁获得角色、谁等待、谁取消、谁只修改意图**'

MOBILITY_FIELDS = [
    '可站立区', '可攀区', '可滑区', '可游区', '**空气控制**', '摩擦',
    '**最大坡度**', '**相机模式**', '碰撞层', '判定盒', '平台接口',
    '**回头路径**',
]

MOBILITY_TESTS = [
    '能力刚获得但**未关闭菜单**', '获得后**立刻死亡**',
    '获得时**正与 NPC 交互**', '获得时**正在载具**', '跨区域切换',
    '**快速旅行中断**', '**网络主机迁移**',
]

CLOSURE_RULE = [
    '🔑 **「玩家看起来能做」不等于能力合同允许**',
    '🔑 自动生成可达性图：对每个节点计算**动作闭包**，'
    '而不是只判断物理可通行',
    '🔑 「能跳到边缘」不意味着「能进入下一状态」 —— '
    '**角色头部、手、钩索锚点、相机碰撞可能使用不同半径**',
    '🔑 脚本应比较原版与复刻的**闭包差集** —— '
    '任何原版不可达而复刻可达的节点都进入待审清单',
]

# 观演
SPECTATE_FIELDS = [
    '**死亡到观演首帧延迟**', '可控制相机范围', '**自由镜头是否穿墙**',
    '可查看队友', '可查看敌人', '可听语音', '可见 HUD', '**可见冷却**',
    '**时间是否继续**', '能否标记', '能否发指令', '自动切换目标',
    '回放生成', '延迟', '保留时长',
]

MATCH_END = [
    '**击杀镜头**', '助攻', '爆头', '多杀', '连杀', '终结技',
    '比分变化', '胜负条件', '**加时**', '弃权', '**断线判负**',
    '**赛后 MVP**', '**回放可跳过性**',
]

END_FRAMES = [
    '**logical_end_frame**', '**result_commit_frame**',
    '**presentation_end_frame**', '**input_unlock_frame**',
]

END_RULE = [
    '🔑 比赛终结必须区分**逻辑结束、表现结束、可操作结束** —— '
    '三者可能**相隔数百毫秒**',
    '🔴 若复刻允许玩家在**结果尚未提交时继续输入** → '
    '可能形成**网络裁决漏洞**',
    '🔴 若**过早锁定输入** → 又损失原版特有的'
    '「**结果出来前的最后操作**」',
]

CONFLICTS = [
    '❌ 只记录「几时获得能力」而不记录世界图变化',
    '❌ 硬锁软锁按策划意图而非玩家验证路径记录',
    '❌ 输入到反馈只测一条链路 / 只看平均值',
    '❌ 把输入丢失当 bug 修掉（**可能是项目自定义仲裁**）',
    '❌ **把逻辑 tick 与渲染帧号混用**',
    '❌ 队友可见性做成统一开关',
    '❌ 匹配取消做成「立即取消」',
    '❌ 提示只记录首次出现',
    '❌ **替玩家决定存档冲突**',
    '❌ 新能力直接写入角色状态（**应走动作仲裁层**）',
    '❌ 可达性只判断物理可通行',
]

FIELDS = [
    ('item_id', '项编号'),
    ('domain', '域（gate / lock / unlock / tutorial / input / lost / refresh / '
               'party / reconnect / teach / save / arbiter / spectate）'),
    ('legacy_value', '**原版值**'),
    ('new_value', '新引擎值'),
    ('match', '**是否一致**'),
    ('tolerance', '**允许偏差区间**'),
    ('evidence', '证据'),
]


def _hdr(t, w=80):
    print('=' * w)
    print(t)
    print('=' * w)


def cmd_gate(a):
    _hdr('🔴 能力门与可到达集合')
    for f in GATE_FIELDS:
        print(f'   · {f}')
    print('\n世界图变化: ' + ' · '.join(GATE_GRAPH))
    print(f'\n   {GATE_RULE}')
    return 0


def cmd_lock(a):
    _hdr('硬锁 vs 软锁（**玩家验证路径**）')
    print('硬锁: ' + ' · '.join(HARD_LOCKS))
    print('\n软锁: ' + ' · '.join(SOFT_LOCKS))
    print('\n字段: ' + ' · '.join(LOCK_FIELDS))
    print('\n测试: ' + ' · '.join(LOCK_TESTS))
    print(f'\n   {LOCK_RULE}')
    return 0


def cmd_unlock(a):
    _hdr('解锁时间线')
    for f in UNLOCK_FIELDS:
        print(f'   · {f}')
    print('\n三个时间字段: ' + ' · '.join(UNLOCK_TIME))
    print(f'\n   {UNLOCK_RULE}')
    return 0


def cmd_tutorial(a):
    _hdr('首次使用引导（**三元组**）')
    print('三元组: ' + ' · '.join(TUTORIAL_TRIPLE))
    print('\n字段: ' + ' · '.join(TUTORIAL_FIELDS))
    print(f'\n   {TUTORIAL_RULE}')
    return 0


def cmd_input(a):
    _hdr('🔴 输入到反馈（**按动作分类**）')
    print('动作: ' + ' · '.join(INPUT_ACTIONS))
    print('\n指标: ' + ' · '.join(INPUT_METRICS))
    print('\n采样:')
    for s in INPUT_SAMPLING:
        print(f'   {s}')
    print(f'\n   {INPUT_RULE}')
    return 0


def cmd_lost(a):
    _hdr('输入丢失（**不是 bug，是仲裁**）')
    print('上下文: ' + ' · '.join(LOST_CONTEXTS))
    print('\n输入: ' + ' · '.join(LOST_INPUTS))
    print('\n规则:')
    for r in LOST_RULE:
        print(f'   {r}')
    return 0


def cmd_refresh(a):
    _hdr('🔴 帧率相关输入（**最高优先级反例**）')
    print('刷新率: ' + ' · '.join(REFRESH_RATES))
    print('\n测试: ' + ' · '.join(REFRESH_TESTS))
    print('\n字段: ' + ' · '.join(REFRESH_FIELDS))
    print('\n规则:')
    for r in REFRESH_RULE:
        print(f'   {r}')
    return 0


def cmd_party(a):
    _hdr('队友可见性（**信息层级**）')
    for v in PARTY_VIS:
        print(f'   · {v}')
    print('\n隔墙高亮: ' + ' · '.join(PARTY_XRAY))
    print('\n交互: ' + ' · '.join(PARTY_INTERACT))
    print('\n测试:')
    for t in PARTY_TESTS:
        print(f'   · {t}')
    return 0


def cmd_reconnect(a):
    _hdr('匹配等待与断线重连')
    print('队列: ' + ' · '.join(QUEUE_FIELDS))
    print('\n规则:')
    for r in QUEUE_RULE:
        print(f'   {r}')
    print('\n重连: ' + ' · '.join(RECONNECT_FIELDS))
    return 0


def cmd_teach(a):
    _hdr('隐性教学（**不说话的教学**）')
    print('通道: ' + ' · '.join(TEACH_CHANNELS))
    print('\n字段: ' + ' · '.join(TEACH_FIELDS))
    print('\n规则:')
    for r in TEACH_RULE:
        print(f'   {r}')
    print('\n失败即教学: ' + ' · '.join(DEATH_TEACH))
    print(f'\n   {DEATH_TEACH_RULE}')
    print('\nNPC 提示: ' + ' · '.join(NPC_HINT))
    print('\n提示消失: ' + ' · '.join(HINT_DISAPPEAR))
    print('\n规则:')
    for r in HINT_RULE:
        print(f'   {r}')
    return 0


def cmd_save(a):
    _hdr('存档/读档的**体验**')
    print('触发源: ' + ' · '.join(SAVE_TRIGGERS))
    print('\n存档字段: ' + ' · '.join(SAVE_FIELDS))
    print('\n读档字段: ' + ' · '.join(LOAD_FIELDS))
    print('\n冲突字段: ' + ' · '.join(CONFLICT_FIELDS))
    print('\n规则:')
    for r in CONFLICT_RULE:
        print(f'   {r}')
    return 0


def cmd_arbiter(a):
    _hdr('🔴 跨系统动作仲裁层')
    print('竞争动作: ' + ' · '.join(ARBITER_ACTIONS))
    print('\n字段: ' + ' · '.join(ARBITER_FIELDS))
    print(f'\n   {ARBITER_RULE}')
    print('\n移动能力切换: ' + ' · '.join(MOBILITY_FIELDS))
    print('\n边界测试: ' + ' · '.join(MOBILITY_TESTS))
    print('\n可达性:')
    for r in CLOSURE_RULE:
        print(f'   {r}')
    return 0


def cmd_spectate(a):
    _hdr('观演与比赛终结')
    for f in SPECTATE_FIELDS:
        print(f'   · {f}')
    print('\n比赛终结: ' + ' · '.join(MATCH_END))
    print('\n四个帧: ' + ' · '.join(END_FRAMES))
    print('\n规则:')
    for r in END_RULE:
        print(f'   {r}')
    return 0


def cmd_init(a):
    os.makedirs(os.path.dirname(a.init) or '.', exist_ok=True)
    with open(a.init, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow([k for k, _ in FIELDS])
        w.writerow(['TODO'] * len(FIELDS))
    print(f'已生成进度/输入表: {a.init}')
    print('\n⚠️ 十三域：gate / lock / unlock / tutorial / input / lost / '
          'refresh / party / reconnect / teach / save / arbiter / spectate')
    return 0


# 🔑 第五十九轮新增：match 字段**白名单**（黑名单拦不住填错的值）
MATCH_ENUM = ('yes', 'y', 'true', '是', '一致', 'exact',
              'no', 'n', 'false', '否', '不一致',
              'tolerance', 'within_tolerance', 'deviation', 'unknown')


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

    mismatch, no_legacy, no_tol = [], [], []
    for i, r in enumerate(rows, 1):
        m = g(r, 'match').lower()
        if m not in ('yes', 'y', 'true', '是', '一致'):
            mismatch.append(i)
        if not g(r, 'legacy_value') or g(r, 'legacy_value') == 'TODO':
            no_legacy.append(i)
        t = g(r, 'tolerance')
        if t in ('', 'todo', 'unknown'):
            no_tol.append(i)

    print('=' * 76)
    print(f'进度/输入 · {len(rows)} 条')
    print('=' * 76)
    if mismatch:
        print(f'\n🚫 **不一致** {len(mismatch)} 条（行 {mismatch[:15]}）')
    if no_legacy:
        print(f'\n❌ {len(no_legacy)} 条缺**原版值**（行 {no_legacy[:15]}）')
    if no_tol:
        print(f'\n⚠️  {len(no_tol)} 条**未定义允许偏差区间**（行 {no_tol[:15]}）')
        print('   → 🔴 **手感是可量化区间，不是一个目标值**')

    if not (mismatch or no_legacy):
        print('\n✅ 进度/输入：一致且原版值完整')

    print('\n🔑 **可达性要算动作闭包，不是物理可通行。**')
    print('   **输入丢失可能是项目自定义仲裁，不要当 bug 修。**')
    print('   **存档冲突必须保留原选择。**')
    # 🔑 白名单：match 字段非法值也须拦（黑名单拦不住）
    bad_match = []
    for i, r in enumerate(rows, 1):
        m = g(r, 'match').lower()
        if m and m not in ('todo', 'tbd') and m not in MATCH_ENUM:
            bad_match.append((i, g(r, 'match')))
    if bad_match:
        print('\n🚫 **match 白名单违例**（🔴 黑名单只查空值，查不出**填错的值**）:')
        for i, v in bad_match[:12]:
            print(f'   行 {i}: match=`{v}` 不在合法枚举内')
        print('   🔑 合法值: ' + ' · '.join(sorted(MATCH_ENUM)))
    # 🔑 跨字段：legacy ≠ new 却声称 match=yes
    contra = []
    for i, r in enumerate(rows, 1):
        lv, nv, m = g(r, 'legacy_value'), g(r, 'new_value'), g(r, 'match').lower()
        if lv and nv and lv != nv and m in ('yes', 'y', 'true', '是', '一致', 'exact'):
            contra.append((i, lv, nv, m))
    if contra:
        print('\n🚫 **跨字段语义矛盾**（字段合法 ≠ 行自洽）:')
        for i, lv, nv, m in contra[:12]:
            print(f'   行 {i}: legacy=`{lv}` ≠ new=`{nv}` 却 match=`{m}`')
    # 🔴 第五十九轮修掉一个真 bug：原实现只读 a.gate_check，
    #    导致 `--gate` 参数**从未生效**（混沌测试正是传 --gate）。
    _g = getattr(a, 'gate_check', False) or getattr(a, 'gate', False)
    return 1 if (_g and (mismatch or no_legacy or bad_match or contra)) else 0


def main():
    ap = argparse.ArgumentParser(description='解锁节奏与输入反馈')
    ap.add_argument('--gate', dest='gate', action='store_true')
    ap.add_argument('--lock', action='store_true')
    ap.add_argument('--unlock', action='store_true')
    ap.add_argument('--tutorial', action='store_true')
    ap.add_argument('--input', action='store_true')
    ap.add_argument('--lost', action='store_true')
    ap.add_argument('--refresh', action='store_true')
    ap.add_argument('--party', action='store_true')
    ap.add_argument('--reconnect', action='store_true')
    ap.add_argument('--teach', action='store_true')
    ap.add_argument('--save', action='store_true')
    ap.add_argument('--arbiter', action='store_true')
    ap.add_argument('--spectate', action='store_true')
    ap.add_argument('--init')
    ap.add_argument('--check')
    ap.add_argument('--gate-check', action='store_true')
    a = ap.parse_args()
    fns = {'gate': cmd_gate, 'lock': cmd_lock, 'unlock': cmd_unlock,
           'tutorial': cmd_tutorial, 'input': cmd_input, 'lost': cmd_lost,
           'refresh': cmd_refresh, 'party': cmd_party,
           'reconnect': cmd_reconnect, 'teach': cmd_teach,
           'save': cmd_save, 'arbiter': cmd_arbiter,
           'spectate': cmd_spectate}
    # 🔴 第五十九轮修掉一个真 bug：
    #    本脚本的 `--gate` 是**子命令**（打印"能力门与可到达集合"章节），
    #    它在 fns 字典里优先级最高，会**劫持** `--check FILE --gate`。
    #    🔑 混沌测试正是用 `--check X --gate` 调用，
    #    → 实际执行的是 cmd_gate（**只打印章节，不做任何校验**），
    #    → rc=0，"看起来通过了"，其实**一次校验都没跑**。
    # 🔑 修复：**`--check` 优先于所有子命令**。
    if a.check:
        return cmd_check(a)
    for k, fn in fns.items():
        if getattr(a, k):
            return fn(a)
    if a.init:
        return cmd_init(a)
    if a.check:
        return cmd_check(a)
    print('❌ 需要 --gate / --lock / --unlock / --tutorial / --input / --lost / '
          '--refresh / --party / --reconnect / --teach / --save / --arbiter / '
          '--spectate / --init / --check 之一')
    return 2


if __name__ == '__main__':
    sys.exit(main())
