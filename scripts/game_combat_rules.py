#!/usr/bin/env python3
"""战斗规则合约 + BOSS 行为契约（第十三轮 A / B 类）。

**🔑 本轮核心判断**：
> 从"**系统清单**"推进到"**规则合约**"。
> **有 AI 不等于 BOSS 的招式权重、锁血演出和回血语义被记录；
> 有状态机不等于 DOT 是刷新还是叠加。**
>
> **`must-match` 应绑定可观测结果，而不是源文件中的函数名。**
> 同名函数在两个引擎中完全可以产生不同结果。

**🔴 最小伤害保底 1 的位置极其关键**：
> 若原作在减伤把结果压到 0 以后才取 `max(x,1)`，会**少扣 1**；
> 若保底发生在反伤和吸血之后，复刻又会**错误回血**。

用法:
  game_combat_rules.py --pipeline  # 🔴 伤害**五条独立管线**
  game_combat_rules.py --rounding  # 🔴 舍入位置/方向/累计
  game_combat_rules.py --school    # 伤害类型是**规则路由键**
  game_combat_rules.py --shield    # 护盾四组规则
  game_combat_rules.py --dot       # 🔴 DOT 七种语义与**快照**
  game_combat_rules.py --immunity  # **免疫是阻止写入还是写入后移除**
  game_combat_rules.py --boss      # 🔴 阶段转换（不是"血量低于阈值"）
  game_combat_rules.py --move      # 招式表是**上下文条件分布**
  game_combat_rules.py --break     # 破防与弱点
  game_combat_rules.py --spawn     # 生成规则
  game_combat_rules.py --init ledger/combat_rules.csv
  game_combat_rules.py --check ledger/combat_rules.csv --gate

退出码: 0 通过 / 1 缺项 / 2 用法错误
"""
import argparse
import csv
import os
import sys

# 🔴 五条独立管线
PIPELINES = [
    '**命中裁决**', '**乘区折叠**', '**修改器快照**',
    '**结算副作用**', '**状态附着**',
]

# 🔴 伤害乘区顺序
DAMAGE_ORDER = [
    'base_dice_or_value', 'weapon_scaling', 'skill_base',
    'attacker_flat', '**attacker_percent_add**',
    '**attacker_percent_multiply**', 'target_flat_reduction',
    'target_percent_reduction', 'armor_or_resistance', 'penetration',
    '**critical**', 'conditional_multiply', 'damage_type_modifier',
    '**shield_layer**', 'overheal_or_overabsorb', 'lifesteal', 'thorns',
    '**minimum_damage**', '**rounding**', 'final_application',
]

DAMAGE_RULE = [
    '🔴 **暴击伤害不是「最终数字乘暴击倍率」** —— 暴击属于**独立乘区**',
    '🔑 命中也可能在伤害计算**之前**就被闪避、格挡、招架、免疫或无敌帧否决',
    '🔑 **乘区顺序决定测试矩阵，而非配置表顺序**',
]

DAMAGE_TESTS = [
    '0', '1', '**负数**', '极大值', '**穿透大于抗性**',
    '多个同类增减益', '**护盾为 0 且有反伤**', '**最终结果为负数**',
]

# 🔴 舍入
ROUNDING_Q = [
    '**每个乘区立即取整还是最后取整**',
    '**四舍五入 / 向下 / 向上 / 银行家舍入**',
    '**小数部分是否进入下一次 tick**',
    '客户端显示值是否截断而**真实值保留**',
    '护盾吸收是否按整数',
    '**吸血在最终伤害舍入前还是后计算**',
]

ROUNDING_EDGE = [
    '🔴 边界用例应是 **`expected = 1` 和 `expected = 0`**',
    '若原作有「最低 1」保底，复刻在减伤压到 0 后才取 `max(x,1)` → **少扣 1**',
    '**若保底发生在反伤和吸血之后 → 复刻会错误回血**',
]

# 伤害类型
SCHOOL_FIELDS = [
    '**school**（物理/元素/真实/治疗）',
    '**source**（近战/远程/范围/持续/反射/地形）', 'tags',
    'can_crit', 'affected_by_armor', 'affected_by_resistance',
    '**ignore_shield**', '**pierces_invuln**', '**applies_on_miss**',
]

PENETRATION_KINDS = [
    '忽略百分比减伤', '降低抗性', '额外伤害', '无视护盾',
    '**无视格挡**', '**穿透无敌帧**',
]

SCHOOL_RULE = '🔑 穿透要细分 —— **只记「穿透 30%」，测试仍无法覆盖上述语义**'

# 护盾
SHIELD_FIELDS = [
    '**独立层**', '**吸收优先级**', '**破碎时机**', '**溢出**',
]

SHIELD_Q = [
    '一个伤害包是**按顺序穿透多层**，还是先被最外层完全吸收',
    '伤害**不足一层**时是否触发破碎',
    '伤害**超过总护盾**时剩余是否继续结算',
    '同名护盾是刷新、叠加、取强还是栈',
    '**护盾破碎瞬间是否还提供减伤**',
    '**死亡阈值是在护盾扣除前还是后判定**',
    'HOT 对**满血带护盾**单位是否触发溢出治疗',
]

THORNS_Q = [
    '基于**原始 / 穿透前 / 减免前 / 最终**伤害',
    '**护盾完全吸收时是否仍触发**',
    '**反伤本身能否再触发反伤**',
]

# 🔴 DOT
DOT_SEMANTICS = [
    '**tick 源**（固定时间/帧/技能帧/攻击帧/回合/进入新状态）',
    '**首跳是否立即发生**', '**末跳是否发生**', 'duration 的起始帧',
    '暂停掩码', '慢动作采样', '跨场景保留', '最大层数',
    '**层间是独立实例还是合并**',
]

REFRESH_POLICY = [
    '仅刷新 duration', '仅加层', '**刷新 duration 并重置快照**',
    '**刷新 duration 但保留原快照**', '拒绝新效果',
    '升级为更强效果', '**叠层但各层独立结算**',
]

DOT_RULE = [
    '🔴 **要区分「新施加 DOT 延长旧 DOT」和「旧 DOT 继续按原快照结算」** —— '
    '二者都叫「刷新」，**结果可能完全不同**',
    '🔑 **快照是 DOT 的版本控制问题**：快照时刻是施法确认 / 飞行物创建 / '
    '命中 / 护甲穿透后 / **DOT 首次 tick**',
    '🔑 快照哪些字段、**哪些后续修改可穿透**',
]

# 状态附着四步
ATTACH_STEPS = [
    '**施加请求**', '**合法性**', '**实例创建**', '**视觉显示**',
]

ATTACH_FIELDS = [
    'owner', '来源技能', 'team', '**stack_key**', '**family**', 'category',
    'max_stacks', 'refresh_policy', 'duration_type',
    '**can_apply_while_stunned**', '**affected_by_tenacity**',
    'icon_priority', 'audio_cue', 'save_scope',
]

# 🔴 免疫
IMMUNITY_KINDS = [
    '**阻止掷骰**', '**阻止命中**', '**允许命中但阻止状态**',
    '**允许状态但阻止伤害**', '**施加后立即移除但触发「成功施加」事件**',
]

IMMUNITY_RULE = [
    '🔴 **必须验证「施加后立即移除」是否会错误触发**：伤害 · 顿帧 · 摄像机 · '
    '附着音效 · **任务计数器** · **成就** · **对话标记**',
    '🔑 这是典型的 **must-match 隐性边界**',
]

DISPEL_Q = [
    '移除所有负面 / **随机一个** / 最高等级 / 最近施加 / 可净化列表外',
    '**不可驱散效果如何显示**',
]

FAMILY_RULE = [
    '🔑 中毒、燃烧、冰冻属不同 family，却可能共享「**控制效果上限**」',
    '🔑 同名晕眩可能按实例叠加，不同技能但相同 stack_key 可能只刷新',
    '🔑 应增加 `family_limits` · `stack_key` · `instance_id` · `suppress_rules`',
]

# 🔴 BOSS 阶段
PHASE_FIELDS = [
    '**trigger_kind**（hp / fixed_time / real_time / mechanic_countdown / '
    'timer_after_skill / player_action）',
    'trigger_value', '**hysteresis_enter**', '**hysteresis_leave**',
    '**lock_hp**', '**refill_hp**', 'lock_both_sides',
    'invulnernance_frames', 'cancel_active_attacks', 'clear_projectiles',
    'clear_statuses', 'clear_aggro', 'swap_move_table', 'retain_enrage',
    'keep_arena_hazards',
]

PHASE_RULE = [
    '🔴 **阶段转换不是「血量低于阈值」**，而是事件源、锁定策略、演出时间线、'
    '结束条件和回滚条件',
    '🔑 若原作**锁血让玩家把阶段完整打完**，复刻成「血量到线立即切招」 → '
    '**玩家看不到机制**',
    '🔑 反之，**锁血持续时间、回血动画和可打断窗口必须逐帧取证**',
]

PHASE_SHOW = [
    '是否允许玩家移动 · 攻击 · **喝药** · **切换装备**',
    '输入缓冲是**冻结 / 清空 / 延迟执行**',
    '相机是锁定、过冲还是可由玩家控制', 'HUD 是否保留', '顿帧持续多久',
    '**演出能否跳过**', '**跳过后逻辑是否完整执行**',
    '阶段结束是动画事件、固定时长还是**逻辑完成信号**',
]

# 招式表
MOVE_FIELDS = [
    'id', '**startup_frames**', '**active_frames**', '**recovery_frames**',
    '**cancel_window**', 'hitbox_lifetime', 'damage_pipeline_id',
    'blockable', 'parryable', 'iframes_granted',
    '**telegraph_visual**', '**telegraph_audio**', 'telegraph_optional',
    '**distance_bucket**', '**angle_bucket**', '**height_bucket**',
    'hp_phase', 'enrage_flag', 'chance_weight',
    '**history_dependent_weight**', 'combo_required', '**anti_repeat_rule**',
    'max_repeats',
]

MOVE_RULE = [
    '🔑 招式表**不是权重总和，而是上下文条件分布**',
    '🔑 距离依赖**不能只写「近/中/远」** —— 应记录转换阈值、死区、'
    '**玩家是否在墙角**、**是否有平台高度差**',
]

SEED_Q = [
    '每场 BOSS / 每次攻击 / 每次伤害 / **系统全局**决定',
    '**种子是否受重连、观战、回放、暂停、慢动作影响**',
    '是否存在避免连续同招的「**洗牌袋**」',
    '是否存在**只在首次遭遇时固定的教程序列**',
    '阶段**重复进入时是否重置**',
]

SEED_RULE = '🔴 **若重放录像中招式序列不一致，即使视觉和伤害正确，也应视为 desync**'

# 破防
BREAK_FIELDS = [
    'breakable_part', 'health_or_value', '**hidden_before_break**',
    'multiple_phases', '**revealed_only_by_damage_type**',
    'damage_table_modifier', 'stagger_on_break',
    '**permanent_or_respawn**', '**heals_on_break**', 'swaps_move_table',
    'invulnernance_after_break', 'min_hits_to_reapply', 'player_visible_ui',
]

BREAK_KINDS = [
    '永久破坏', '**阶段性破坏**', '**离开战斗恢复**',
    '**仅本场恢复**', '**仅本难度恢复**',
]

BREAK_RULE = '🔴 部位破坏必须区分上述五种 —— 否则「**永久变化**」的存档世界' \
             '会在复刻中**错误复原**'

# 可读性
READABILITY_FIELDS = [
    '**首帧提示**', '**确定信息帧**',
    '视觉 / 音频 / 镜头 / **地面** / 敌人动作各通道',
    '**远距离弱化**', '遮挡处理', '**玩家是否能提前识别招式**',
    '攻击是否可被特定帧打断', '打断是否进入特殊倒地',
    '**玩家攻击是否只打断前摇**', '击中 BOSS 的确认反馈优先级',
]

READABILITY_RULE = [
    '🔑 **不应只记「0.8 秒前摇」**',
    '🔴 若一个 BOSS 的招式**只有声音提示**，复刻成明显亮光 → '
    '会**同时破坏聋人玩家、色盲玩家和戴耳机的玩家**',
    '🔴 反过来，**完全依赖音频也会产生无障碍问题**',
]

# 生成
SPAWN_FIELDS = [
    '触发事件', '最小/最大间隔', '波次人数', '位置候选', '路径',
    '**可见生成时间**', '生成音效', '**生成时是否可立即攻击**',
    '离场条件', '**上限**', '替换规则', '**玩家拉远是否暂停**',
    '**镜头外是否降级**', '回退逻辑',
]

SPAWN_RULE = '🔴 若原作用「**玩家进入触发器即锁定生成**」，复刻成「每秒检查范围」' \
             ' → **不同帧率会产生不同数量敌人**'

CONFLICT_SCHEMA = [
    'refresh: reject | extend_duration | reset_duration | refresh_and_resnapshot',
    'immunity: block_application | apply_then_remove | block_event',
    'stacking: independent | shared_key | max_duration | max_strength | force_remove',
    'replacement: oldest | newest | lowest_strength | highest_strength | random',
    '**damage_minimum: none | 0 | 1 | configurable_value**',
]

CONFLICTS = [
    '❌ **「先写通用战斗框架，再补数值」** —— 默认乘区/免疫语义/缓冲窗口'
    '会把未取证字段悄悄填成框架值',
    '❌ **功能近似即完成** —— 攻击能造成伤害、BOSS 能换招、'
    '玩家能解锁区域，都不等于规则匹配',
    '❌ 暴击当最终数字乘倍率',
    '❌ DOT 只记「每秒伤害」',
    '❌ 穿透只记一个百分比',
    '❌ 阶段转换只记「血量低于阈值」',
]

FIELDS = [
    ('contract_id', '合约编号'),
    ('domain', '域（pipeline / rounding / school / shield / dot / '
               'immunity / boss / move / break / spawn）'),
    ('legacy_value', '**原版值**'),
    ('new_value', '新引擎值'),
    ('match', '**是否一致**'),
    ('frame_evidence', '**帧级证据（录像/时间码）**'),
    ('evidence', '证据'),
]


def _hdr(t, w=80):
    print('=' * w)
    print(t)
    print('=' * w)


def cmd_pipeline(a):
    _hdr('🔴 战斗五条独立管线')
    for p in PIPELINES:
        print(f'   · {p}')
    print('\n伤害乘区顺序: ' + ' · '.join(DAMAGE_ORDER))
    print('\n规则:')
    for r in DAMAGE_RULE:
        print(f'   {r}')
    print('\n边界值测试: ' + ' · '.join(DAMAGE_TESTS))
    return 0


def cmd_rounding(a):
    _hdr('🔴 舍入（**位置 / 方向 / 累计**）')
    for q in ROUNDING_Q:
        print(f'   · {q}')
    print('\n边界:')
    for e in ROUNDING_EDGE:
        print(f'   {e}')
    return 0


def cmd_school(a):
    _hdr('伤害类型（**规则路由键**）')
    for f in SCHOOL_FIELDS:
        print(f'   · {f}')
    print('\n穿透细分: ' + ' · '.join(PENETRATION_KINDS))
    print(f'\n   {SCHOOL_RULE}')
    return 0


def cmd_shield(a):
    _hdr('护盾（**四组规则**）')
    print('组: ' + ' · '.join(SHIELD_FIELDS))
    print('\n必答:')
    for q in SHIELD_Q:
        print(f'   · {q}')
    print('\n反伤:')
    for q in THORNS_Q:
        print(f'   · {q}')
    return 0


def cmd_dot(a):
    _hdr('🔴 DOT/HOT（**七种语义**）')
    for s in DOT_SEMANTICS:
        print(f'   · {s}')
    print('\n刷新策略: ' + ' · '.join(REFRESH_POLICY))
    print('\n规则:')
    for r in DOT_RULE:
        print(f'   {r}')
    return 0


def cmd_immunity(a):
    _hdr('🔴 免疫与驱散')
    print('免疫五种: ' + ' · '.join(IMMUNITY_KINDS))
    print('\n规则:')
    for r in IMMUNITY_RULE:
        print(f'   {r}')
    print('\n驱散: ' + ' · '.join(DISPEL_Q))
    print('\n状态附着四步: ' + ' · '.join(ATTACH_STEPS))
    print('\n字段: ' + ' · '.join(ATTACH_FIELDS))
    print('\n叠加:')
    for r in FAMILY_RULE:
        print(f'   {r}')
    return 0


def cmd_boss(a):
    _hdr('🔴 BOSS 阶段转换（**不是「血量低于阈值」**）')
    for f in PHASE_FIELDS:
        print(f'   · {f}')
    print('\n规则:')
    for r in PHASE_RULE:
        print(f'   {r}')
    print('\n演出: ' + ' · '.join(PHASE_SHOW))
    return 0


def cmd_move(a):
    _hdr('招式表（**上下文条件分布**）')
    for f in MOVE_FIELDS:
        print(f'   · {f}')
    print('\n规则:')
    for r in MOVE_RULE:
        print(f'   {r}')
    print('\n种子:')
    for q in SEED_Q:
        print(f'   · {q}')
    print(f'\n   {SEED_RULE}')
    return 0


def cmd_break(a):
    _hdr('破防与弱点')
    for f in BREAK_FIELDS:
        print(f'   · {f}')
    print('\n破坏类型: ' + ' · '.join(BREAK_KINDS))
    print(f'\n   {BREAK_RULE}')
    print('\n可读性: ' + ' · '.join(READABILITY_FIELDS))
    print('\n规则:')
    for r in READABILITY_RULE:
        print(f'   {r}')
    return 0


def cmd_spawn(a):
    _hdr('生成规则')
    for f in SPAWN_FIELDS:
        print(f'   · {f}')
    print(f'\n   {SPAWN_RULE}')
    return 0


def cmd_init(a):
    os.makedirs(os.path.dirname(a.init) or '.', exist_ok=True)
    with open(a.init, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow([k for k, _ in FIELDS])
        w.writerow(['TODO'] * len(FIELDS))
    print(f'已生成战斗规则表: {a.init}')
    print('\n⚠️ 十域：pipeline / rounding / school / shield / dot / '
          'immunity / boss / move / break / spawn')
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

    mismatch, no_legacy, no_frame = [], [], []
    for i, r in enumerate(rows, 1):
        m = g(r, 'match').lower()
        if m not in ('yes', 'y', 'true', '是', '一致'):
            mismatch.append(i)
        if not g(r, 'legacy_value') or g(r, 'legacy_value') == 'TODO':
            no_legacy.append(i)
        fe = g(r, 'frame_evidence')
        if not fe or fe == 'TODO':
            no_frame.append(i)

    print('=' * 76)
    print(f'战斗规则 · {len(rows)} 条')
    print('=' * 76)
    if mismatch:
        print(f'\n🚫 **不一致** {len(mismatch)} 条（行 {mismatch[:15]}）')
    if no_legacy:
        print(f'\n❌ {len(no_legacy)} 条缺**原版值**（行 {no_legacy[:15]}）')
    if no_frame:
        print(f'\n⚠️  {len(no_frame)} 条**缺帧级证据**（行 {no_frame[:15]}）')
        print('   → 🔴 规则合约必须绑定**可观测结果**与录像时间码，'
              '不能只比对函数名')

    if not (mismatch or no_legacy):
        print('\n✅ 战斗规则：一致且原版值完整')

    print('\n🔑 **最小伤害保底 1 的位置**决定少扣还是错误回血。')
    print('   **DOT 快照是版本控制问题；免疫语义是隐性边界。**')
    print('   **阶段锁血与回血必须逐帧取证。**')
    print('\n冲突语义 schema: ' + ' | '.join(CONFLICT_SCHEMA))
    return 1 if (a.gate and (mismatch or no_legacy)) else 0


def main():
    ap = argparse.ArgumentParser(description='战斗规则与 BOSS 契约')
    ap.add_argument('--pipeline', action='store_true')
    ap.add_argument('--rounding', action='store_true')
    ap.add_argument('--school', action='store_true')
    ap.add_argument('--shield', action='store_true')
    ap.add_argument('--dot', action='store_true')
    ap.add_argument('--immunity', action='store_true')
    ap.add_argument('--boss', action='store_true')
    ap.add_argument('--move', action='store_true')
    ap.add_argument('--break', dest='brk', action='store_true')
    ap.add_argument('--spawn', action='store_true')
    ap.add_argument('--init')
    ap.add_argument('--check')
    ap.add_argument('--gate', action='store_true')
    a = ap.parse_args()
    fns = {'pipeline': cmd_pipeline, 'rounding': cmd_rounding,
           'school': cmd_school, 'shield': cmd_shield, 'dot': cmd_dot,
           'immunity': cmd_immunity, 'boss': cmd_boss, 'move': cmd_move,
           'brk': cmd_break, 'spawn': cmd_spawn}
    for k, fn in fns.items():
        if getattr(a, k):
            return fn(a)
    if a.init:
        return cmd_init(a)
    if a.check:
        return cmd_check(a)
    print('❌ 需要 --pipeline / --rounding / --school / --shield / --dot / '
          '--immunity / --boss / --move / --break / --spawn / --init / '
          '--check 之一')
    return 2


if __name__ == '__main__':
    sys.exit(main())
