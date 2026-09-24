#!/usr/bin/env python3
"""节奏设计 + UI 信息架构 + 听觉认知 + 存档心理契约（第十六轮 C/D/E/F/G）。

**🔑 C 类核心**：
> **节奏是时间函数，而不是八类静态关卡标签。**
> 🔴 **关卡时间与战斗时间不是同一尺度** ——
> 只按关卡逻辑时间评价节奏，会**系统性低估死亡重试造成的疲劳**。

**🔑 D 类核心**：
> 信息架构决定玩家能否做出正确决策。
> 🔴 **`hover_repeat` 与 `selection_change` 仍要在信息层落实** ——
> 不得合并成同一个回调。

**🔑 E 类核心**：
> 声音是**信息通道**，不只是氛围。
> 🔑 辨识度要用"**正确识别率 × 反应时间 × 置信度**"衡量，
> 而不是只听是否不同。

用法:
  game_pacing_info.py --timeline  # 🔴 节奏**运行时间轴**
  game_pacing_info.py --density   # 战斗密度**不能只看敌人数量**
  game_pacing_info.py --supply    # 补给是**风险曲线**不是掉落率
  game_pacing_info.py --wave      # 难度微波动**不失去归因**
  game_pacing_info.py --breath    # 🔴 呼吸空间是**有功能的时段**
  game_pacing_info.py --agency    # 引导与自由的交替
  game_pacing_info.py --timescale # 🔴 关卡时间 ≠ 战斗时间
  game_pacing_info.py --infoarch  # 🔴 信息架构四层
  game_pacing_info.py --hoverinfo # hover_repeat 在信息层落实
  game_pacing_info.py --audible   # 🔴 声音**辨识度**可测
  game_pacing_info.py --masking   # 掩蔽三层
  game_pacing_info.py --fatigue   # 听觉疲劳**停止条件**
  game_pacing_info.py --savemind  # 🔴 存档**心理契约**
  game_pacing_info.py --death     # 死亡惩罚**四条契约**
  game_pacing_info.py --init ledger/pacing_info.csv
  game_pacing_info.py --check ledger/pacing_info.csv --gate

退出码: 0 通过 / 1 缺项 / 2 用法错误
"""
import argparse
import csv
import os
import sys

# 🔴 运行时间轴
TIMELINE_FIELDS = [
    '当前区域', '战斗状态', '敌人密度', '玩家资源', '资源事件', '威胁等级',
    '音频强度', '音乐节拍', '**玩家死亡/重试**', '探索自由度', 'NPC 对话',
    '**停顿是否玩家可控**',
]

TIMELINE_RULE = [
    '🔑 应新增 `pacing/run_timeline.csv`：以固定采样周期记录上述字段',
    '🔑 由此才可计算：**连续战斗时长、资源安全边际、难度微波动、'
    '呼吸段长度、引导后自由度、失败后的情绪恢复**',
]

# 密度
DENSITY_FIELDS = [
    'enemy_archetype', 'formation_density', 'spawn_batch_size',
    'spawn_interval_ms', 'time_between_attacks_ms', 'aggro_radius_overlap',
    'environmental_hazard_density', 'cover_availability',
    '**player_decision_points_per_minute**',
]

DENSITY_RULE = [
    '🔑 **战斗密度不能只看敌人数量** —— '
    '"多个弱敌"和"一个强力敌"可做成相近压力，却产生完全不同的阅读和输入节奏',
    '🔑 要区分**策划密度、运行时密度与玩家感知密度** —— '
    '一只敌人卡在墙后不会改变战斗，却可能改变仇恨、音频和补刀节奏',
]

# 补给
SUPPLY_FIELDS = [
    'resource_type', 'pre_resource_at_event', 'post_resource_at_event',
    '**expected_time_to_next_event_ms**', '**expected_damage_to_next_event**',
    '**minimum_safe_quantity**', 'critical_quantity_threshold',
    'event_visibility{world, ui, none}',
]

SUPPLY_RULE = [
    '🔑 **补给投放不是掉落率，而是"下一个安全点之前的风险曲线"**',
    '🔑 弹药、血量、耐力、技能资源、制造材料和存档机会都要以'
    '"**上次获得后还可支撑多久**"建模',
    '🔑 若玩家血量恰好等于一次失误代价 → **该投放点就是硬边界**',
    '🔑 若补包位置紧邻敌人刷新 → **资源价值会被风险抵消**',
]

# 微波动
WAVE_FIELDS = [
    'base_challenge', 'local_perturbation', 'density_perturbation',
    'resource_perturbation', 'recovery_budget', '**每个波次/房间保存配置**',
]

WAVE_RULE = [
    '🔑 一整段难度恒定会让体验平坦，持续单调上升又会疲劳',
    '🔑 **扰动幅度应受前置结果约束**：连续失败后**短暂降扰**，'
    '而不是悄悄永久降低 AI；连续成功后**提高复杂度**，而不是只提高敌人血量',
]

# 🔴 呼吸空间
BREATH_FIELDS = [
    'recovery_type', 'recovery_duration_ms', '**player_agency_level**',
    'narrative_information_load', 'music_tension_before_after',
    '**next_threat_warning_lead_time**',
]

BREATH_RULE = [
    '🔴 **呼吸空间必须是有功能的时间段，不是没有内容的空段**',
    '🔑 可能由慢速探索、短对话、安全补给、自由路径选择、环境叙事或'
    '降低音乐强度组成',
    '🔑 **过短不足以恢复，过长又会让玩家把节奏误解为卡关**',
    '🔑 必须同时看主观张力、玩家移动速度和资源增长',
]

# 引导与自由
AGENCY_FIELDS = [
    '**guidance_strength**{forced, cued, minimal, none}',
    'available_branches', 'visible_objectives', 'optional_content_count',
    'return_path_cost', 'discovery_reward_type',
]

AGENCY_RULE = [
    '🔑 引导段可限制出口、目标标记、敌人组合和路径；'
    '自由段应增加可选目标、支路、信息量与风险回报',
    '🔑 **切换不能只靠"教程完成"标志** —— 要记玩家何时获得选择权、'
    '**是否被告知可逆**、**失败后是否回到同一决策点**',
]

# 🔴 时间尺度
TIMESCALE_FIELDS = [
    'logic_time_ms', 'real_time_ms', 'paused_time_ms',
    '**death_and_retry_time_ms**', '**player_controlled_stillness_ms**',
]

TIMESCALE_RULE = '🔴 **关卡时间与战斗时间不是同一尺度** —— '
'流程脚本常按事件推进，玩家实际经历却受死亡、重跑、等待、菜单和收集改变。'
'**只按关卡逻辑时间评价节奏，会系统性低估死亡重试造成的疲劳**'

# 🔴 信息架构
INFOARCH_FOUR = [
    ('**优先级**', '什么常驻、什么弹出、**什么永不显示**'),
    ('**持久性**', '提示多久消失、**是否可回溯**（日志/历史）'),
    ('**冗余**', '同一信息在几个地方显示、**是否一致**'),
    ('**过载处理**', '同屏最多几条、**如何取舍**'),
]

INFOARCH_EVENT = [
    'event_id', 'canonical_state_id', 'layer', 'priority', 'show_at',
    'expire_at', '**log_retain_until**', 'dismiss_reason', 'user_queried_at',
]

INFOARCH_METRICS = [
    '同屏峰值', '平均寿命', '**不可找回比例**', '未读紧急项',
    '重复事件簇', '**玩家查询成功率**',
]

INFOARCH_WCAG = [
    '**通知不得偷走当前输入焦点**',
    '**死亡/结算/菜单导航焦点必须可预测**',
    '**手柄、键鼠和触控目标有独立安全区**',
    '**重复表单应保留上次有效值**',
]

# hover 信息层
HOVER_INFO = [
    '**hover_repeat.initial_delay_ms**', 'repeat_interval_ms',
    'hover_exit_cancels_repeat',
    '**selection_change.emits_only_on_identity_change**',
    'repeat_suppressed_when_modal_open',
]

HOVER_RULE = [
    '🔴 **`hover_repeat` 与 `selection_change` 仍要在信息层落实** —— '
    '前者是持续悬停的重复反馈，后者是选择身份变化的单次事件，'
    '**不得合并成同一个回调**',
    '🔑 若重复反馈继续播放 → 玩家会**误以为仍在查看原项**',
    '🔑 若每次光标微移触发完整语音 → 形成**声学风暴**',
]

# 🔴 声音辨识度
AUDIO_EVENT_FIELDS = [
    'event_id', 'source_entity_type',
    '**event_type**{attack, intent, resource, navigation, status, danger, '
    'ambient}',
    '**friend_or_foe_ambiguity**', 'threat_level', 'spatialization_type',
    '**min_identification_duration_ms**', 'ducking_group', 'concurrency_cap',
    '**repetition_variant_set**',
]

AUDIO_METRIC = '🔑 辨识度要用"**正确识别率 × 反应时间 × 置信度**"衡量，'
'而不是只听是否不同'

AUDIO_PRIORITY = [
    '🔑 威胁优先级会改变谁被听见',
    '🔑 相同声学距离下，**正在攻击玩家的敌人、正在交战的队友、普通环境声'
    '必须形成可测层次**',
    '🔑 复刻时应记**实际决策变量**，而不是抄"威胁值"概念',
]

# 掩蔽三层
MASKING_THREE = [
    '**频率掩蔽**（同频强音遮蔽弱音）',
    '**时域掩蔽**（前音尾音或后音起音掩盖）',
    '**功能掩蔽**（事件标签和音色过度相似，玩家无法判断是谁、做什么、'
    '威胁多大）',
]

MASKING_FIELDS = [
    'frequency_busyness', 'temporal_masking_window_ms',
    '**event_confusion_pair**', '**functional_audibility_score**',
]

MASKING_RULE = '🔴 **混音器峰值正常并不代表重要事件可被识别**'

# 疲劳
FATIGUE_FIELDS = [
    '**max_repetitions_before_variant**', '**max_repetitions_before_suppress**',
    'variant_set_size', 'cooldown_between_same_event_ms',
    'ambient_layer_rest_policy', 'fatigue_recovery_duration_ms',
]

FATIGUE_RULE = [
    '🔑 **听觉疲劳必须被设计成停止条件**',
    '🔑 同一击杀喊叫、错误音、循环环境层若长期不变 → **玩家会逐步忽略**',
    '🔑 **抑制不等于删除** —— 仍应进入日志或世界反馈',
]

REVERB_EXTRA = [
    'onset_smoothing_ms', 'cutoff_smoothing_ms', 'wet_mix_law',
    '**minimum_continuous_time_ms_before_change**', 'crossfade_overlap',
    'visual_and_mechanical_consistency',
]

REVERB_RULE = '🔑 玩家能靠声音判断门后空间是否变化；**突然切换会让空间不可读**。'
'**不同指纹不能用同一种混响预设换名**'

AV_ARBITRATION = [
    'audio_then_visual_lead_ms', 'visual_then_audio_lead_ms',
    'acceptable_offset_ms', '**critical_event_audio_required**',
]

AV_RULE = '🔑 敌人起手声音可以早于危险标记，但**标记不得早于玩家可感知证据**；'
'远距离警报可先于世界变化，**近距爆裂则视觉与音频必须同步**'

# 🔴 存档心理契约
SAVE_SUMMARY = [
    'save_id', 'version', '**save_reason**{manual, checkpoint, state_change, '
    'system}',
    'world_time', 'player_resources', 'active_objectives',
    '**irreversible_decisions**', '**next_safe_return_point**',
    '**unsaved_risk_warning**',
]

SAVE_MIND_RULE = [
    '🔑 存档问题不只是文件格式和损坏恢复，而是玩家相信'
    '"**什么时间点被记住、何时可以回来、哪些选择已经锁死**"',
    '🔴 自动保存必须在**玩家可理解的稳定边界**发生；'
    '若在**输入窗口、过场中间、随机结果刚生成却未确认**时保存 → '
    '玩家会把技术边界理解为**不公平竞争**',
]

CHECKPOINT_FIELDS = [
    '**checkpoint_visibility**{visual, audio, none}',
    'activation_feedback_delay_ms', 'safe_duration_ms',
    'pre_save_warning_lead_time', 'can_leave_without_saving',
    '**respawn_arrival_state**',
]

CHECKPOINT_RULE = [
    '🔑 **存档点可见性不是图标本身**',
    '🔑 玩家应知道"**我是否已进入安全区域**""**保存是否已经完成**"'
    '"**死亡后会回到这里还是更早**"',
    '🔑 **保存中强制禁止输入，却又不给进度反馈** → 形成不确定惩罚',
]

# 死亡惩罚
DEATH_FOUR = [
    '**lost_resources_schema**', '**progress_loss_boundary**',
    '**recovery_affordance**', '**expected_loss_transparency**',
]

DEATH_RULE = [
    '🔑 掉落、耐久损耗、经验削减、时间流逝或出生点回退都要列明',
    '🔑 **不能有的字段必须写 `none` 而不是留空**',
    '🔴 玩家允许"**有代价的失败**"，但**不能接受结果随机、边界不明、'
    '恢复机会不对称**',
]

CONFLICTS = [
    '❌ 用八类静态关卡标签代替节奏时间轴',
    '❌ **只按关卡逻辑时间评价节奏**（低估死亡重试疲劳）',
    '❌ 战斗密度只看敌人数量',
    '❌ 补给当掉落率而非风险曲线',
    '❌ 难度扰动悄悄永久降低 AI',
    '❌ 呼吸空间做成没有内容的空段',
    '❌ 引导转自由只靠"教程完成"标志',
    '❌ **把 hover_repeat 与 selection_change 合并成一个回调**',
    '❌ 提示不可回溯（丢失历史）',
    '❌ 同屏信息无上限',
    '❌ 声音辨识度只听"是否不同"',
    '❌ 混音器峰值正常就认为可识别',
    '❌ 听觉疲劳无停止条件',
    '❌ 不同空间用同一混响预设换名',
    '❌ **自动保存在输入窗口/过场中间**',
    '❌ 保存中禁输入却不给进度反馈',
    '❌ 死亡惩罚边界不明',
]

FIELDS = [
    ('item_id', '项编号'),
    ('domain', '域（timeline / density / supply / wave / breath / agency / '
               'timescale / infoarch / hoverinfo / audible / masking / '
               'fatigue / savemind / death）'),
    ('legacy_value', '**原版值**'),
    ('new_value', '新引擎值'),
    ('match', '**是否一致**'),
    ('tolerance', '**允许偏差**'),
    ('evidence', '证据'),
]


def _hdr(t, w=80):
    print('=' * w)
    print(t)
    print('=' * w)


def cmd_timeline(a):
    _hdr('🔴 节奏运行时间轴')
    for f in TIMELINE_FIELDS:
        print(f'   · {f}')
    print('\n规则:')
    for r in TIMELINE_RULE:
        print(f'   {r}')
    return 0


def cmd_density(a):
    _hdr('战斗密度（**不能只看敌人数量**）')
    for f in DENSITY_FIELDS:
        print(f'   · {f}')
    print('\n规则:')
    for r in DENSITY_RULE:
        print(f'   {r}')
    return 0


def cmd_supply(a):
    _hdr('补给（**风险曲线**）')
    for f in SUPPLY_FIELDS:
        print(f'   · {f}')
    print('\n规则:')
    for r in SUPPLY_RULE:
        print(f'   {r}')
    return 0


def cmd_wave(a):
    _hdr('难度微波动（**不失去归因**）')
    for f in WAVE_FIELDS:
        print(f'   · {f}')
    print('\n规则:')
    for r in WAVE_RULE:
        print(f'   {r}')
    return 0


def cmd_breath(a):
    _hdr('🔴 呼吸空间（**有功能的时段**）')
    for f in BREATH_FIELDS:
        print(f'   · {f}')
    print('\n规则:')
    for r in BREATH_RULE:
        print(f'   {r}')
    return 0


def cmd_agency(a):
    _hdr('引导与自由的交替')
    for f in AGENCY_FIELDS:
        print(f'   · {f}')
    print('\n规则:')
    for r in AGENCY_RULE:
        print(f'   {r}')
    return 0


def cmd_timescale(a):
    _hdr('🔴 关卡时间 ≠ 战斗时间')
    for f in TIMESCALE_FIELDS:
        print(f'   · {f}')
    print(f'\n   {TIMESCALE_RULE}')
    print('\n🔑 建议**同时输出两组成果**')
    return 0


def cmd_infoarch(a):
    _hdr('🔴 信息架构四层')
    for k, why in INFOARCH_FOUR:
        print(f'   {k:<12} {why}')
    print('\n事件字段: ' + ' · '.join(INFOARCH_EVENT))
    print('\n指标: ' + ' · '.join(INFOARCH_METRICS))
    print('\n可访问性:')
    for w in INFOARCH_WCAG:
        print(f'   · {w}')
    return 0


def cmd_hoverinfo(a):
    _hdr('hover_repeat 在信息层落实')
    for f in HOVER_INFO:
        print(f'   · {f}')
    print('\n规则:')
    for r in HOVER_RULE:
        print(f'   {r}')
    return 0


def cmd_audible(a):
    _hdr('🔴 声音辨识度（**可测**）')
    for f in AUDIO_EVENT_FIELDS:
        print(f'   · {f}')
    print(f'\n   {AUDIO_METRIC}')
    print('\n威胁优先级:')
    for r in AUDIO_PRIORITY:
        print(f'   {r}')
    return 0


def cmd_masking(a):
    _hdr('掩蔽三层')
    for m in MASKING_THREE:
        print(f'   · {m}')
    print('\n字段: ' + ' · '.join(MASKING_FIELDS))
    print(f'\n   {MASKING_RULE}')
    print('\n混响区补充: ' + ' · '.join(REVERB_EXTRA))
    print(f'\n   {REVERB_RULE}')
    print('\n音画交叉仲裁: ' + ' · '.join(AV_ARBITRATION))
    print(f'\n   {AV_RULE}')
    return 0


def cmd_fatigue(a):
    _hdr('听觉疲劳（**停止条件**）')
    for f in FATIGUE_FIELDS:
        print(f'   · {f}')
    print('\n规则:')
    for r in FATIGUE_RULE:
        print(f'   {r}')
    return 0


def cmd_savemind(a):
    _hdr('🔴 存档心理契约')
    print('可读摘要: ' + ' · '.join(SAVE_SUMMARY))
    print('\n规则:')
    for r in SAVE_MIND_RULE:
        print(f'   {r}')
    print('\n存档点可见性: ' + ' · '.join(CHECKPOINT_FIELDS))
    print('\n规则:')
    for r in CHECKPOINT_RULE:
        print(f'   {r}')
    return 0


def cmd_death(a):
    _hdr('死亡惩罚（**四条契约**）')
    for f in DEATH_FOUR:
        print(f'   · {f}')
    print('\n规则:')
    for r in DEATH_RULE:
        print(f'   {r}')
    return 0


def cmd_init(a):
    os.makedirs(os.path.dirname(a.init) or '.', exist_ok=True)
    with open(a.init, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow([k for k, _ in FIELDS])
        w.writerow(['TODO'] * len(FIELDS))
    print(f'已生成节奏/信息表: {a.init}')
    print('\n⚠️ 十四域：timeline / density / supply / wave / breath / agency / '
          'timescale / infoarch / hoverinfo / audible / masking / fatigue / '
          'savemind / death')
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

    mismatch, no_legacy = [], []
    for i, r in enumerate(rows, 1):
        m = g(r, 'match').lower()
        if m not in ('yes', 'y', 'true', '是', '一致'):
            mismatch.append(i)
        if not g(r, 'legacy_value') or g(r, 'legacy_value') == 'TODO':
            no_legacy.append(i)

    print('=' * 76)
    print(f'节奏/信息 · {len(rows)} 条')
    print('=' * 76)
    if mismatch:
        print(f'\n🚫 **不一致** {len(mismatch)} 条（行 {mismatch[:15]}）')
    if no_legacy:
        print(f'\n❌ {len(no_legacy)} 条缺**原版值**（行 {no_legacy[:15]}）')

    if not (mismatch or no_legacy):
        print('\n✅ 节奏/信息：一致且原版值完整')

    print('\n🔑 **节奏是时间函数；关卡时间 ≠ 战斗时间。**')
    print('   **hover_repeat 与 selection_change 在信息层也不得合并。**')
    print('   **自动保存必须在玩家可理解的稳定边界。**')
    return 1 if (a.gate_check and (mismatch or no_legacy)) else 0


def main():
    ap = argparse.ArgumentParser(description='节奏与信息架构')
    ap.add_argument('--timeline', action='store_true')
    ap.add_argument('--density', action='store_true')
    ap.add_argument('--supply', action='store_true')
    ap.add_argument('--wave', action='store_true')
    ap.add_argument('--breath', action='store_true')
    ap.add_argument('--agency', action='store_true')
    ap.add_argument('--timescale', action='store_true')
    ap.add_argument('--infoarch', action='store_true')
    ap.add_argument('--hoverinfo', action='store_true')
    ap.add_argument('--audible', action='store_true')
    ap.add_argument('--masking', action='store_true')
    ap.add_argument('--fatigue', action='store_true')
    ap.add_argument('--savemind', action='store_true')
    ap.add_argument('--death', action='store_true')
    ap.add_argument('--init')
    ap.add_argument('--check')
    ap.add_argument('--gate-check', action='store_true')
    a = ap.parse_args()
    fns = {'timeline': cmd_timeline, 'density': cmd_density,
           'supply': cmd_supply, 'wave': cmd_wave, 'breath': cmd_breath,
           'agency': cmd_agency, 'timescale': cmd_timescale,
           'infoarch': cmd_infoarch, 'hoverinfo': cmd_hoverinfo,
           'audible': cmd_audible, 'masking': cmd_masking,
           'fatigue': cmd_fatigue, 'savemind': cmd_savemind,
           'death': cmd_death}
    for k, fn in fns.items():
        if getattr(a, k):
            return fn(a)
    if a.init:
        return cmd_init(a)
    if a.check:
        return cmd_check(a)
    print('❌ 需要 --timeline / --density / --supply / --wave / --breath / '
          '--agency / --timescale / --infoarch / --hoverinfo / --audible / '
          '--masking / --fatigue / --savemind / --death / --init / --check 之一')
    return 2


if __name__ == '__main__':
    sys.exit(main())
