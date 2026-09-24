#!/usr/bin/env python3
"""角色存在感/空间占位 + 对话交互空间仲裁（第二十八轮 A / B 类）。

**🔑 A 类核心**：
> 🔑 **"存在感"缺的不是人群算法，而是所有权与责任边界。**
> 🔑 **"玩家能否挤过同伴/敌人"是三态，不是一个"碰撞开关"** ——
> 它是**多帧推力的结果**。
> 🔑 **同伴"有用"必须拆成挡枪 · 误伤 · 占位 · 卡门 · 抢路五个独立事实。**

**🔑 B 类核心**：
> 🔑 **触发条件是几何与状态的交集。**
> 🔑 **对话不是输入事件的消费，而是自己的状态机。**

用法:
  game_presence_interact.py --presence # 🔴 **存在感字段**
  game_presence_interact.py --pass     # 能否挤过**三态**
  game_presence_interact.py --ally     # 🔴 同伴**五个独立事实**
  game_presence_interact.py --gaze     # 视线**注视是状态机输出**
  game_presence_interact.py --budget   # 🔴 **密度超限**是玩法预算
  game_presence_interact.py --trigger  # 触发**几何与状态交集**
  game_presence_interact.py --arb      # 🔴 并发**稳定排序键**
  game_presence_interact.py --dialog   # 对话**六态**
  game_presence_interact.py --init ledger/presence_interact.csv
  game_presence_interact.py --check ledger/presence_interact.csv --gate

退出码: 0 通过 / 1 缺项 / 2 用法错误
"""
import argparse
import csv
import os
import sys

# 🔴 存在感字段
PRESENCE_FIELDS = [
    'entity_kind', 'collision_channel', 'rigid_vs_soft', 'local_avoidance',
    'avoidance_priority', 'separation_radius', 'stopping_distance',
    'follow_slot_index', 'look_at_target', '**blocks_player**',
    '**blocks_bullet**', '**blocks_camera_ray**', 'blocks_dialogue',
    'lod_retire_rule', 'retire_visibility_rule',
]

PRESENCE_DECL = [
    '是否与玩家**硬碰**', '是否共享碰撞通道', '是否**只避让不推开**',
    '是否能把玩家**挤出地面**', '是否参与局部避让',
    '**死亡/布娃娃后是否仍阻塞**', '是否能阻挡子弹', '是否能阻挡射线',
    '是否参与密度预算',
]

PRESENCE_RULE = [
    '🔑 **"存在感"缺的不是人群算法，而是所有权与责任边界**',
    '🔑 此前覆盖把角色当**寻路主体**；真正改变手感的是'
    '**角色之间、角色与环境之间的共同占用规则**',
]

# 🔴 能否挤过三态
PASS_THREE = [
    ('**pass_through**', '始终可穿过'),
    ('**soft_push**', '会被挤开'),
    ('**rigid_block**', '会被刚性卡住'),
    ('**conditional**', '条件性（必须附 `condition_expr`）'),
]

PASS_RULE = '🔑 **这不是一个"碰撞开关"，而是多帧推力的结果**'

# 🔴 同伴五事实
ALLY_FIVE = [
    ('**挡枪**', '子弹命中同伴 · 爆炸伤害半径 · 友军火焰/链条/穿透 · '
     '近战后摇是否误伤 · **同伴是否会主动站进玩家射击线**'),
    ('**误伤**', '同上，且记**是否可被关闭**'),
    ('**占位**', '是否会主动让出玩家所需站位的**帧数 · 频率 · 最终结果**'),
    ('**卡门**', '门阈值 · 持续输入 · 左右两侧判定 · 开门锁 · 关闭窗口 · '
     '**瞬时取消与中途取消**'),
    ('**抢路**', '狭窄走廊 · 阶梯 · 攀爬入口 · 载具 · **过场出口**'),
]

ALLY_RULE = [
    '🔑 **同伴"有用"必须拆成挡枪 · 误伤 · 占位 · 卡门 · 抢路五个独立事实**',
    '🔴 **任何把"AI 聪明"直接写进复刻的做法都可能与理念冲突** —— '
    '更聪明的导航**可能只是改变了原始 bug 或 trick route**',
    '🔑 默认 must-match 应写成"**同伴不主动让出玩家所需站位的'
    '帧数 · 频率与最终结果**"',
]

# 视线注视
GAZE_TARGETS = ['头部', '脊柱', '双眼', '武器', '互动对象']

GAZE_STATES = ['idle', 'alert', 'combat', 'dialogue', 'performative']

GAZE_EVENTS = [
    'look_target_kind', 'acquire_frame', 'lose_frame', 'evidence_kind',
    'evidence_strength', 'occluder_id',
]

GAZE_RULE = [
    '🔑 **视线注视不是表情，而是状态机输出**',
    '🔑 要记玩家进入视线后的**首帧反应 · 持续注视 · 转移注视 · '
    '盲视 · 背对反应**',
    '🔑 **应把视线视为输入** —— 它决定是否发现 · 是否回应 · '
    '是否允许交互 · 是否中断表演',
]

# 🔴 密度预算
BUDGET_DOMAINS = [
    '距离', '房间', '簇', '屏幕', '同屏', '同材质', '同动画种类',
    '同一角色种类',
]

BUDGET_RETIRE = [
    '更新', '动画', '语音', '物理', '碰撞', '阴影', '整个实体',
]

BUDGET_FIELDS = [
    'budget_domain', 'counter_kind', 'soft_limit', 'hard_limit',
    '**retire_strategy**', '**preserve_gameplay_facts**',
    're_evaluation_rate_ms', '**stable_sort_key**',
]

BUDGET_RULE = '🔴 **未记录这些时，新引擎把"低优先级角色停止碰撞"'
'当性能优化，会直接消灭原版的卡门与挡枪事实**'

# 触发
TRIGGER_FIELDS = [
    'prompt_id', 'actor_id', 'interactable_id', '**trigger_shape**',
    'trigger_radius', 'trigger_height_band', '**requires_los**',
    'los_channel_mask', '**facing_angle_deg**', 'min_hold_frames',
    'max_range', 'path_must_be_clear', 'path_ray_channel',
    '**prompt_space**', 'prompt_anchor', '**visible_when_occluded**',
    'prompt_offset_world', 'priority', '**stable_sort_key**',
    'input_action_id',
]

TRIGGER_QUESTIONS = [
    '触发半径**是否各向同性**',
    '是否使用**胶囊体 / OBB / 高度带**',
    '正面触发是**视轴点乘**、**角色朝向**还是**可旋转扇形**',
    '是否要求玩家**站立/移动/蹲伏/瞄准/携带特定物品**',
    '视线是否忽略**透明物 · 粒子 · 玻璃 · 水 · 门 · 某些层**',
    '**是否允许穿墙显示**',
    '是否需要**连续保持若干帧**',
    '**离开后是否有迟滞**',
    '**远程交互是否共享近距离半径**或另有一套射程',
]

# 🔴 并发仲裁
ARB_KEY = '(room_id, interaction_layer, priority desc, distance asc, ' \
          'angle asc, object_instance_id)'

ARB_RULE = [
    '🔑 同一帧多个候选时，**先用稳定排序键完全确定**，'
    '再记录距离/朝向权重与随机规则',
    '🔑 推荐键：' + ARB_KEY,
    '🔴 **禁止只按"最近"或"视线最先命中"**',
]

# 对话六态
DIALOG_SIX = [
    '**能否移动**', '移动是否进入', '**是否保持**', '**是否中断**',
    '是否只能退出', '**中断后能否续接**',
]

DIALOG_FIELDS = [
    'node_id', 'enter_conditions', 'allowed_movement', 'movement_policy',
    '**on_move_response**', 'on_los_lost_response', 'on_damage_response',
    '**on_death_response**', 'on_task_change_response', '**bookmark_kind**',
    '**resume_policy**', 'cancelable_phases',
]

DIALOG_RESUME = [
    '续最后一句', '重启节点', '**重新评估入口**', '跳转失败分支',
]

DIALOG_RULE = [
    '🔑 **对话不是输入事件的消费，而是自己的状态机**',
    '🔑 还要记：移动中**是否继续朝向** · **是否停止动画** · '
    '**是否维持视线**',
    '🔑 能否**同时战斗 / 受伤 / 死亡**',
    '🔑 NPC 死亡 · 任务状态变化 · 阵营变化 · 任务阶段变化 · 日程切换 · '
    '离场 · **载具离开**时是否中断',
]

DIALOG_MULTI = '🔑 **多人同时可交互时的选择**：优先级 · 朝向权重 · '
'距离权重 · **稳定排序**'

CONFLICTS = [
    '❌ 把"能否挤过"当成一个碰撞开关',
    '❌ **把"AI 聪明"直接写进复刻**',
    '❌ 更聪明的导航（可能只是改了原始 bug 或 trick route）',
    '❌ 把注视当表情而非状态机输出',
    '❌ **"低优先级角色停止碰撞"当性能优化**',
    '❌ **并发仲裁只按"最近"或"视线最先命中"**',
    '❌ 对话做成输入事件的消费',
    '❌ **中断后一律重启节点**（应分四种 resume）',
    '❌ 触发只记距离不记朝向/视线/高度带/迟滞',
]

FIELDS = [
    ('item_id', '项编号'),
    ('domain', '域（presence / pass / ally / gaze / budget / trigger / '
               'arb / dialog）'),
    ('legacy_value', '**原版值**'),
    ('new_value', '新引擎值'),
    ('match', '**是否一致**'),
    ('tolerance', '**允许偏差**'),
    ('evidence', '证据等级 1-8'),
]


def _hdr(t, w=80):
    print('=' * w)
    print(t)
    print('=' * w)


def cmd_presence(a):
    _hdr('🔴 存在感（**所有权与责任边界**）')
    print('每类角色分别声明:')
    for d in PRESENCE_DECL:
        print(f'   · {d}')
    print('\n字段: ' + ' · '.join(PRESENCE_FIELDS))
    print('\n规则:')
    for r in PRESENCE_RULE:
        print(f'   {r}')
    return 0


def cmd_pass(a):
    _hdr('🔴 能否挤过（**三态 + 条件**）')
    for k, why in PASS_THREE:
        print(f'   {k:<18} {why}')
    print(f'\n   {PASS_RULE}')
    print('   🔑 后两种必须附 `condition_expr`')
    return 0


def cmd_ally(a):
    _hdr('🔴 同伴（**五个独立事实**）')
    for k, why in ALLY_FIVE:
        print(f'   {k}\n      {why}')
    print('\n规则:')
    for r in ALLY_RULE:
        print(f'   {r}')
    return 0


def cmd_gaze(a):
    _hdr('视线（**注视是状态机输出**）')
    print('注视目标: ' + ' · '.join(GAZE_TARGETS))
    print('目标选择规则: ' + ' · '.join(GAZE_STATES))
    print('\n事件字段: ' + ' · '.join(GAZE_EVENTS))
    print('\n规则:')
    for r in GAZE_RULE:
        print(f'   {r}')
    return 0


def cmd_budget(a):
    _hdr('🔴 密度预算（**玩法预算**）')
    print('预算域: ' + ' · '.join(BUDGET_DOMAINS))
    print('被裁减的是: ' + ' · '.join(BUDGET_RETIRE))
    print('\n字段: ' + ' · '.join(BUDGET_FIELDS))
    print(f'\n   {BUDGET_RULE}')
    return 0


def cmd_trigger(a):
    _hdr('触发（**几何与状态的交集**）')
    print('字段: ' + ' · '.join(TRIGGER_FIELDS))
    print('\n必须回答:')
    for q in TRIGGER_QUESTIONS:
        print(f'   · {q}')
    return 0


def cmd_arb(a):
    _hdr('🔴 并发仲裁（**稳定排序键**）')
    print('推荐键: ' + ARB_KEY)
    print('\n规则:')
    for r in ARB_RULE:
        print(f'   {r}')
    print(f'\n   {DIALOG_MULTI}')
    return 0


def cmd_dialog(a):
    _hdr('对话（**自己的状态机**）')
    print('六态: ' + ' · '.join(DIALOG_SIX))
    print('\n字段: ' + ' · '.join(DIALOG_FIELDS))
    print('\nresume 四种: ' + ' · '.join(DIALOG_RESUME))
    print('\n规则:')
    for r in DIALOG_RULE:
        print(f'   {r}')
    return 0


def cmd_init(a):
    os.makedirs(os.path.dirname(a.init) or '.', exist_ok=True)
    with open(a.init, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow([k for k, _ in FIELDS])
        w.writerow(['TODO'] * len(FIELDS))
    print(f'已生成存在感/交互表: {a.init}')
    print('\n⚠️ 八域：presence / pass / ally / gaze / budget / trigger / '
          'arb / dialog')
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

    mismatch, no_legacy, no_grade = [], [], []
    for i, r in enumerate(rows, 1):
        m = g(r, 'match').lower()
        if m not in ('yes', 'y', 'true', '是', '一致'):
            mismatch.append(i)
        if not g(r, 'legacy_value') or g(r, 'legacy_value') == 'TODO':
            no_legacy.append(i)
        ev = g(r, 'evidence')
        if not ev or ev == 'TODO':
            no_grade.append(i)
        else:
            d = ev.split('.')[0].strip()
            if d.isdigit() and int(d) >= 7:
                no_grade.append(i)

    print('=' * 76)
    print(f'存在感/交互 · {len(rows)} 条')
    print('=' * 76)
    if mismatch:
        print(f'\n🚫 **不一致** {len(mismatch)} 条（行 {mismatch[:15]}）')
    if no_legacy:
        print(f'\n❌ {len(no_legacy)} 条缺**原版值**（行 {no_legacy[:15]}）')
    if no_grade:
        print(f'\n🚫 {len(no_grade)} 条**证据等级缺失或 ≥7 级**'
              f'（行 {no_grade[:15]}）')

    if not (mismatch or no_legacy or no_grade):
        print('\n✅ 存在感/交互：一致、原版值完整、证据等级达标')

    print('\n🔑 **"能否挤过"是三态，是多帧推力的结果，不是碰撞开关。**')
    print('   **同伴"有用"要拆成挡枪/误伤/占位/卡门/抢路五个事实。**')
    print('   **"低优先级角色停止碰撞"会消灭原版卡门与挡枪事实。**')
    print('   **并发仲裁禁止只按"最近"或"视线最先命中"。**')
    return 1 if (a.gate_check and (mismatch or no_legacy or no_grade)) else 0


def main():
    ap = argparse.ArgumentParser(description='角色存在感与交互仲裁')
    ap.add_argument('--presence', action='store_true')
    ap.add_argument('--pass', dest='pass_', action='store_true')
    ap.add_argument('--ally', action='store_true')
    ap.add_argument('--gaze', action='store_true')
    ap.add_argument('--budget', action='store_true')
    ap.add_argument('--trigger', action='store_true')
    ap.add_argument('--arb', action='store_true')
    ap.add_argument('--dialog', action='store_true')
    ap.add_argument('--init')
    ap.add_argument('--check')
    ap.add_argument('--gate-check', action='store_true')
    a = ap.parse_args()
    fns = {'presence': cmd_presence, 'pass_': cmd_pass, 'ally': cmd_ally,
           'gaze': cmd_gaze, 'budget': cmd_budget, 'trigger': cmd_trigger,
           'arb': cmd_arb, 'dialog': cmd_dialog}
    for k, fn in fns.items():
        if getattr(a, k):
            return fn(a)
    if a.init:
        return cmd_init(a)
    if a.check:
        return cmd_check(a)
    print('❌ 需要 --presence / --pass / --ally / --gaze / --budget / '
          '--trigger / --arb / --dialog / --init / --check 之一')
    return 2


if __name__ == '__main__':
    sys.exit(main())
