#!/usr/bin/env python3
"""联机延迟补偿体验 + AI 可读性与信任（第十六轮 A / B 类）。

**🔑 A 类核心**：
> 联机复刻的判定对象**不是服务器状态，而是玩家眼里的因果**。
> 玩家实际感受到的是三重不同世界：**本地权威输入、服务端权威结算、
> 其他实体被插值或外推后的过去时画面**。
>
> 🔴 `must-match` 不能只比较最终血量，还必须比较
> "**命令发生时画面上的位置 — 回退后的判定位置 — 命中反馈出现时间**"的完整因果链。

**🔴 B 类核心**：
> AI 的"聪明"必须让位于**意图可读、信息对称与可解释信任**。
> **公平感来自可访问信息对称，而不是降低强度。**

用法:
  game_netfeel_ai_trust.py --rollback  # 🔴 回溯窗口**不是越长越公平**
  game_netfeel_ai_trust.py --tickrate  # 60Hz服务器 + 144Hz客户端
  game_netfeel_ai_trust.py --interp    # 🔴 插值安全，**外推才制造滑步**
  game_netfeel_ai_trust.py --asym      # 🔴 高延迟玩家**同时是受益与受损者**
  game_netfeel_ai_trust.py --predict   # 预测纠正**不该都静默抹平**
  game_netfeel_ai_trust.py --ping      # ping 显示是**公平判断证据**
  game_netfeel_ai_trust.py --intent    # 🔴 意图在**互补通道**同时表达
  game_netfeel_ai_trust.py --fairness  # 🔴 公平感来自**信息对称**
  game_netfeel_ai_trust.py --difficulty# 🔴 低难度不能无规格地"变笨"
  game_netfeel_ai_trust.py --fail      # 有意失误要**像设计不像故障**
  game_netfeel_ai_trust.py --group     # 🔴 群体**谁先谁等何时替换**
  game_netfeel_ai_trust.py --stuck     # 卡死恢复是**手感的一部分**
  game_netfeel_ai_trust.py --init ledger/netfeel_ai.csv
  game_netfeel_ai_trust.py --check ledger/netfeel_ai.csv --gate

退出码: 0 通过 / 1 缺项 / 2 用法错误
"""
import argparse
import csv
import os
import sys

# 🔴 回溯
ROLLBACK_FIELDS = [
    '**lag_compensation.max_rollback_ms**', '**per_weapon_rollback_ms**',
    '**rollback_exempt_states**', '**command_time_formula**',
    '**perception_to_resolution_gap_ms**',
]

ROLLBACK_RULE = [
    '🔴 **回溯窗口不是可以全局设为"越长越公平"的单一数字**',
    '🔑 长回溯让高延迟攻击者更容易命中过去的可见目标，却会提高'
    '"**我已进掩体却仍被打中**"的违和',
    '🔑 短回溯降低回溯感，却让高延迟玩家**打不到自己屏幕上已经命中的目标**',
    '🔑 **武器射速、命中盒、弹道速度、瞬发命中、投掷物与区域伤害要分别记录**',
    '🔴 若原项目对**不同武器或动作豁免**无敌、位移确认、爆头盒或近战判定，'
    '**全局统一化就是偏离而非简化**',
]

# 🔴 tick rate
TICK_FIELDS = [
    'local_input_sample_rate', '**logic_tick_rate**', 'render_frame_rate',
    '**projectile_substep_rate**', 'snapshot_send_interval',
    '**interpolation_buffer_ms**', '**max_buffered_snapshots**',
]

TICK_RULE = [
    '🔴 **60Hz 服务器与 144Hz 客户端不是简单"客户端更流畅"**',
    '🔑 本地输入和动画可在 144Hz 推进，但**服务端离散 tick 仍决定权威状态**',
    '🔑 预测、快照、纠正和表现层若不同步 → 输入更早生效、伤害更晚确认、'
    '**命中特效与扣血错位**、高刷下相机移动却仍有 tick 阶梯',
]

TICK_TESTS = [
    '**144Hz 相机抖动量**', '**tick 边界射速收益**',
    '**伤害数字与命中特效是否同一 tick**', '**纠正是否重放输入**',
]

# 🔴 插值 vs 外推
INTERP_FIELDS = [
    '**interpolation.algorithm**', '**extrapolation.max_time_ms**',
    '**extrapolation.max_speed_change**', '**path_deviation_snap_threshold**',
    '纠正时采用 **snap / teleport / short_warp / 重插值**',
]

INTERP_RULE = '🔴 **插值通常安全，外推才制造最刺耳的滑步** —— '
'两个权威快照之间的线性插值会落后，却**不会自行创造路径**；'
'外推可以补足更长的缓冲，却在**转向、急停、滑铲、瞬移或碰撞后偏离**'

INTERP_TESTS = [
    '横移反复时是否保持恒定速度', '**转身是否产生弧形轨迹**',
    '穿墙轨迹', '**停止后滑出半步**', '**多人载具各座位错位**',
]

# 🔴 延迟不对称
ASYM_MATRIX = [
    '0 / 50 / 100 / 150 / 220 毫秒单向上行', '下行', '**抖动**', '**丢包**',
    '**高延迟攻击者对低延迟目标**', '**低延迟攻击者对高延迟目标**',
    '**旁观者视角**',
]

ASYM_RECORD = [
    '命中率', '**被命中者看到自己已经规避后的死亡时间**', '确认延迟',
    '位置纠正量', '**玩家主观"明明打中/明明躲开"样本**',
]

ASYM_RULE = '🔴 **高延迟玩家可能同时是受益者和受损者** —— '
'他看到的目标更旧、开火后确认更晚，但**命中可能按过去位置成立**；'
'低延迟玩家则可能看到目标已离开掩体却仍被击中'

# 预测纠正
PREDICT_FIELDS = [
    '**reconcile.position_smoothing**',
    '**authoritative_states**[health, ammo, ability, cooldown, status_effect]',
    '**rollback_replay_input_range**', 'correction_max_position_error',
    '**correction_animation_restart_policy**',
]

PREDICT_RULE = [
    '🔴 **客户端预测错误并不都该被静默抹平**',
    '🔑 位置小误差可用平滑纠正，但**已确认状态、伤害、消耗、无敌和位移**'
    '可能明显错配',
    '🔑 弹药"**先显示减少后恢复**"、无敌技能被回滚、连招最后一击被取消 —— '
    '都**必须保留事件时间戳**，不能只存最终值',
]

# ping 显示
PING_FIELDS = [
    '**ping_display.mode**{off, conditional, always}', 'jitter_display',
    'packet_loss_display', 'missed_tick_display',
    '**latency_icon_threshold_ms**', '**sample_smoothing_frames**',
    '**网络问题提示是否可关、是否遮挡战斗**',
]

PING_RULE = [
    '🔴 **ping 显示不是 UI 装饰，而是玩家判断"是否公平"的证据**',
    '🔑 **平均 ping 可能掩盖瞬间 200 毫秒尖峰** —— '
    '应同时保存原始 RTT 分位数、抖动、丢包、服务端时钟偏差和命令队列长度',
]

# 🔴 AI 意图
INTENT_FIELDS = [
    'intent_state', '**intent_confidence_visible_to_player**',
    'telegraph_animation', 'telegraph_audio',
    '**telegraph_duration_min_max_ms**', 'body_orientation',
    'weapon_or_ability_orientation', 'threat_level', '**intent_can_change**',
]

INTENT_RULE = [
    '🔑 从感知到动作之间的**可见承诺**：先发现 → 形成意图 → 进入预警 → 执行',
    '🔴 同一个"即将冲锋"意图**不能只靠一种动画** —— '
    '否则无声或动画被遮挡时玩家无依据反应',
    '🔴 也**不能只靠 UI 箭头** —— 否则会失去 diegetic 表现',
    '🔑 预警时间必须随难度改变，但**同一难度下同类动作的相对差异应稳定** —— '
    '否则玩家无法学习',
]

# 🔴 公平感
FAIRNESS_FIELDS = [
    '**knowledge_source**{vision, hearing, shared_team_vision, '
    'true_position, forbidden}',
    '**information_max_age_ms**', 'blackboard_visible_subset',
    'cheat_prevention_test', '**reaction_delay_min_max_ms**',
]

FAIRNESS_RULE = [
    '🔴 **公平感来自可访问信息对称，而不是降低强度**',
    '🔑 若 AI 共享玩家视野、真实坐标、无敌状态、无限弹药或未来输入 → '
    '**玩家可以感知为作弊**',
    '🔑 若它用玩家也可理解的规则推理，**即使更强也更容易接受**',
    '🔑 测试必须记 AI 在**遮挡后第一次获得合法证据到动作反应的最小延迟**；'
    '若小于人类可信范围，**应调整而不是把反应时间随机化就结束**',
]

# 🔴 难度
DIFFICULTY_FIELDS = [
    'reaction_delay', '**accuracy_model**', 'resource_budget',
    'ability_usage_probability', '**target_priority_errors**',
    'movement_capability', '**每级难度保存完整配置哈希**',
]

DIFFICULTY_RULE = [
    '🔴 **低难度不能无规格地"让 AI 变笨"**',
    '🔑 迟钝影响节奏 · 射偏影响手感 · 路径错误影响空间 · '
    '忘记技能影响可预测性 —— **给玩家的感受不同**',
    '🔴 难度只改一个权重、却让所有表现同步变傻 → '
    '**通常会同时破坏可读性与挑战感**',
]

# 有意失误
FAIL_FIELDS = [
    '**intentional_failure.rate**', 'intentional_failure.allowed_actions',
    '**minimum_competence_window_ms**', '**failure_reveal_channel**',
]

FAIL_RULE = [
    '🔑 **有意失误必须写得像设计，而不是像故障**',
    '🔑 AI 在**关键窗口内不能连续失误**，失误也不能让它卡进几何或'
    '**永久重复同一动作**',
    '🔑 玩家应能把失误**归因于 AI 状态**，而不是归因于导航网格、'
    '寻路失败或动画事件丢失',
]

# 🔴 群体
GROUP_FIELDS = [
    'formation_role', 'formation_offset', '**engagement_slot_capacity**',
    'approach_lanes', 'flank_probability', '**attack_queue_policy**',
    '**simultaneous_max_attackers**', 'replacement_delay_ms',
    'reposition_after_attack_ms', 'rescue_or_retreat_threshold',
]

GROUP_RULE = [
    '🔑 群体协调必须显式管理"**谁先、谁等、何时替换**"',
    '🔴 **无限排队会导致远敌永远等待，无排队则群殴**',
    '🔑 应测入口容量、仇恨刷新、死亡替换、击退打断和'
    '**玩家快速移动后的"全员同时扑脸"**',
]

# 卡死
STUCK_FIELDS = [
    '**stuck_detection.{distance_window, time_window, threshold}**',
    'recovery_actions_priority', '**teleport_fallback_policy**',
    '**fallback_animation_visibility**', 'recovery_cooldown_ms',
    '**stuck_audible_reaction**',
]

STUCK_RULE = [
    '🔑 **卡死恢复是手感的一部分，不是日志里的异常**',
    '🔑 瞬移、穿地、重置目标、突然转向必须标记为'
    '"**表现可见**"或"**逻辑内部**" —— '
    '**避免把性能/错误恢复误当成角色能力**',
]

NAV_ANIM = [
    'agent_repath_interval_ms', 'goal_update_policy', 'traversal_link_type',
    'agent_radius_height_compensation',
    'animation_contribution{root_motion, turn_in_place, stop_distance}',
    'steering_jitter_max', 'two_agents_min_separation',
]

NAV_ANIM_RULE = '🔑 寻路精确但转向动画卡顿 → 玩家觉得 AI 被拖着走；'
'动画自主移动但 NavMesh 未授权 → 穿模或挤堆'

BLACKBOX = [
    '🔴 **不建议把黑箱学习模型直接吸收为行为真值**',
    '🔑 `Unity ML-Agents` 可用于**生成测试对手、模仿玩家行为、参数搜索**，'
    '但其策略可随时间、随机种子和训练集漂移',
    '🔑 **无法承诺稳定 telegraph、固定失误率或可读边界**',
    '🔑 `NVIDIA Isaac Sim` 属**仿真与生成测试基础设施**，不应成为复刻目标行为',
    '🔑 二者产生的数据可以进 `ai/training_artifacts/` 作参考，'
    '**不进入 must-match 真值**',
]

CONFLICTS = [
    '❌ 回溯窗口全局统一（**不同武器/动作豁免被抹掉**）',
    '❌ 只比较最终血量而不比因果链',
    '❌ 把"客户端更流畅"当高刷全部收益',
    '❌ **用外推掩盖插值落后**（制造滑步）',
    '❌ 高延迟玩家的优劣势被"补偿"掉而不记录',
    '❌ 预测错误全部静默抹平',
    '❌ 只显示平均 ping',
    '❌ AI 只靠一种通道表达意图',
    '❌ 难度只改一个权重让所有表现同步变傻',
    '❌ 把有意失误做成随机故障',
    '❌ 群体无排队（群殴）或无限排队（远敌永等）',
    '❌ **卡死恢复被当角色能力**',
    '❌ **把黑箱学习模型当 must-match 真值**',
]

FIELDS = [
    ('item_id', '项编号'),
    ('domain', '域（rollback / tickrate / interp / asym / predict / ping / '
               'intent / fairness / difficulty / fail / group / stuck）'),
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


def cmd_rollback(a):
    _hdr('🔴 回溯窗口（**不是越长越公平**）')
    for f in ROLLBACK_FIELDS:
        print(f'   · {f}')
    print('\n规则:')
    for r in ROLLBACK_RULE:
        print(f'   {r}')
    return 0


def cmd_tickrate(a):
    _hdr('🔴 服务器 tick 与客户端帧率（**解耦**）')
    for f in TICK_FIELDS:
        print(f'   · {f}')
    print('\n规则:')
    for r in TICK_RULE:
        print(f'   {r}')
    print('\n测试: ' + ' · '.join(TICK_TESTS))
    return 0


def cmd_interp(a):
    _hdr('🔴 插值 vs 外推')
    for f in INTERP_FIELDS:
        print(f'   · {f}')
    print(f'\n   {INTERP_RULE}')
    print('\n测试: ' + ' · '.join(INTERP_TESTS))
    return 0


def cmd_asym(a):
    _hdr('🔴 延迟不对称矩阵')
    for m in ASYM_MATRIX:
        print(f'   · {m}')
    print('\n每格记录: ' + ' · '.join(ASYM_RECORD))
    print(f'\n   {ASYM_RULE}')
    return 0


def cmd_predict(a):
    _hdr('预测与纠正（**不该都静默抹平**）')
    for f in PREDICT_FIELDS:
        print(f'   · {f}')
    print('\n规则:')
    for r in PREDICT_RULE:
        print(f'   {r}')
    return 0


def cmd_ping(a):
    _hdr('ping 显示（**公平判断证据**）')
    for f in PING_FIELDS:
        print(f'   · {f}')
    print('\n规则:')
    for r in PING_RULE:
        print(f'   {r}')
    return 0


def cmd_intent(a):
    _hdr('🔴 AI 意图（**互补通道**）')
    for f in INTENT_FIELDS:
        print(f'   · {f}')
    print('\n规则:')
    for r in INTENT_RULE:
        print(f'   {r}')
    return 0


def cmd_fairness(a):
    _hdr('🔴 公平感（**信息对称**）')
    for f in FAIRNESS_FIELDS:
        print(f'   · {f}')
    print('\n规则:')
    for r in FAIRNESS_RULE:
        print(f'   {r}')
    return 0


def cmd_difficulty(a):
    _hdr('🔴 难度（**不能无规格地变笨**）')
    for f in DIFFICULTY_FIELDS:
        print(f'   · {f}')
    print('\n规则:')
    for r in DIFFICULTY_RULE:
        print(f'   {r}')
    return 0


def cmd_fail(a):
    _hdr('有意失误（**像设计不像故障**）')
    for f in FAIL_FIELDS:
        print(f'   · {f}')
    print('\n规则:')
    for r in FAIL_RULE:
        print(f'   {r}')
    return 0


def cmd_group(a):
    _hdr('🔴 群体协调（**谁先谁等**）')
    for f in GROUP_FIELDS:
        print(f'   · {f}')
    print('\n规则:')
    for r in GROUP_RULE:
        print(f'   {r}')
    return 0


def cmd_stuck(a):
    _hdr('卡死恢复（**手感的一部分**）')
    for f in STUCK_FIELDS:
        print(f'   · {f}')
    print('\n规则:')
    for r in STUCK_RULE:
        print(f'   {r}')
    print('\n导航+动画: ' + ' · '.join(NAV_ANIM))
    print(f'\n   {NAV_ANIM_RULE}')
    print('\n黑箱模型:')
    for b in BLACKBOX:
        print(f'   {b}')
    return 0


def cmd_init(a):
    os.makedirs(os.path.dirname(a.init) or '.', exist_ok=True)
    with open(a.init, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow([k for k, _ in FIELDS])
        w.writerow(['TODO'] * len(FIELDS))
    print(f'已生成联机/AI 表: {a.init}')
    print('\n⚠️ 十二域：rollback / tickrate / interp / asym / predict / ping / '
          'intent / fairness / difficulty / fail / group / stuck')
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
    print(f'联机/AI · {len(rows)} 条')
    print('=' * 76)
    if mismatch:
        print(f'\n🚫 **不一致** {len(mismatch)} 条（行 {mismatch[:15]}）')
    if no_legacy:
        print(f'\n❌ {len(no_legacy)} 条缺**原版值**（行 {no_legacy[:15]}）')

    if not (mismatch or no_legacy):
        print('\n✅ 联机/AI：一致且原版值完整')

    print('\n🔑 **判定对象是玩家眼里的因果，不是服务器状态。**')
    print('   **回溯窗口不能全局统一；外推才制造滑步。**')
    print('   **公平感来自信息对称，不是降低强度。**')
    return 1 if (a.gate_check and (mismatch or no_legacy)) else 0


def main():
    ap = argparse.ArgumentParser(description='联机延迟与 AI 信任')
    ap.add_argument('--rollback', action='store_true')
    ap.add_argument('--tickrate', action='store_true')
    ap.add_argument('--interp', action='store_true')
    ap.add_argument('--asym', action='store_true')
    ap.add_argument('--predict', action='store_true')
    ap.add_argument('--ping', action='store_true')
    ap.add_argument('--intent', action='store_true')
    ap.add_argument('--fairness', action='store_true')
    ap.add_argument('--difficulty', action='store_true')
    ap.add_argument('--fail', action='store_true')
    ap.add_argument('--group', action='store_true')
    ap.add_argument('--stuck', action='store_true')
    ap.add_argument('--init')
    ap.add_argument('--check')
    ap.add_argument('--gate-check', action='store_true')
    a = ap.parse_args()
    fns = {'rollback': cmd_rollback, 'tickrate': cmd_tickrate,
           'interp': cmd_interp, 'asym': cmd_asym, 'predict': cmd_predict,
           'ping': cmd_ping, 'intent': cmd_intent, 'fairness': cmd_fairness,
           'difficulty': cmd_difficulty, 'fail': cmd_fail,
           'group': cmd_group, 'stuck': cmd_stuck}
    for k, fn in fns.items():
        if getattr(a, k):
            return fn(a)
    if a.init:
        return cmd_init(a)
    if a.check:
        return cmd_check(a)
    print('❌ 需要 --rollback / --tickrate / --interp / --asym / --predict / '
          '--ping / --intent / --fairness / --difficulty / --fail / --group / '
          '--stuck / --init / --check 之一')
    return 2


if __name__ == '__main__':
    sys.exit(main())
