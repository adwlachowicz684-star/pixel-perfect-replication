#!/usr/bin/env python3
"""帧时序契约 + 脚本与引擎边界（第二十一轮 C / D 类）。

**🔑 C 类核心**：
> 新盲区是"**可见性**"而不是"有没有用多线程"。
> 需要记录的不是笼统的"线程安全"，而是
> **写入何时提交、消费者何时读取、跨线程快照是否允许陈旧**。
>
> 🔴 **任何写"延迟一帧"的地方必须说明是设计、性能优化还是已知偏离，
> 不能把现象命名为原因。**

**🔑 D 类核心**：
> 关键不是脚本语法，而是**调用跨越边界时谁拥有控制权、
> 异常发生后世界处于什么状态**。
>
> 🔴 **任何"脚本里抛错只打日志"的默认策略都不可接受** ——
> 它可能发生在伤害、存档、交易、网络输入或场景切换的关键窗口。

用法:
  game_frame_script.py --frame    # 🔴 一帧**九个阶段**
  game_frame_script.py --lag      # 延迟一帧按**五个方向**分类
  game_frame_script.py --queue    # 事件队列**消费时机**
  game_frame_script.py --script   # 🔴 脚本边界**调用约定**
  game_frame_script.py --error    # 🔴 异常**四态**
  game_frame_script.py --hotreload # 热重载**四种语义**
  game_frame_script.py --scene    # 🔴 场景是**加载事务**
  game_frame_script.py --debug    # 调试工具**消失即失明**
  game_frame_script.py --init ledger/frame_script.csv
  game_frame_script.py --check ledger/frame_script.csv --gate

退出码: 0 通过 / 1 缺项 / 2 用法错误
"""
import argparse
import csv
import os
import sys

# 🔴 一帧九阶段
FRAME_NINE = [
    'input_poll', 'input_commit', 'script_logic', 'animation_pose',
    'physics_step', '**事件队列排空**', 'command_submit', 'render_consume',
    'present_or_next_input',
]

FRAME_FIELDS = [
    '**producer_phase**', '**consumer_phase**', '**visibility_rule**',
    'staleness_tolerance', 'rollback_version',
]

VISIBILITY_RULES = [
    'immediate_in_phase', 'barrier_before_read', 'snapshot_at_phase',
    '**allowed_one_frame_late**',
]

FRAME_RULE = [
    '🔑 每个跨阶段字段写 ' + ' · '.join(FRAME_FIELDS),
    '🔑 可见性规则至少四种：' + ' · '.join(VISIBILITY_RULES),
    '🔴 **"延迟一帧"必须说明是设计、性能优化还是已知偏离**',
]

# 🔴 延迟一帧五方向
LAG_FIELDS = ['direction', 'producer', 'consumer', 'frames',
              'observed_effect', '**approved_deviation**']

LAG_DIRS = [
    ('**逻辑→相机**', '相机轻微抖或穿透'),
    ('**相机→物理**', '命中与落地判断错位'),
    ('**物理→动画**', '姿势与碰撞不一致'),
    ('**动画→音频**', '通常可接受；**但若属判定反馈会改变节奏判断**'),
    ('**脚本事件→渲染**', '视觉反馈晚一帧'),
]

LAG_RULE = '🔑 **只测"总体输入延迟"无法区分这五类** —— '
'它们对玩家的解释完全不同'

# 事件队列
QUEUE_FIELDS = [
    'producer_phase', 'consumer_phase', '**capacity**',
    '**overflow_policy**', '**coalescing**', '**replay_on_rollback**',
    '**recursion_policy**',
]

QUEUE_QUESTIONS = [
    '同一物理接触在多个固定步中连续产生事件时，**是否合并**？',
    '动画事件中"武器开火"和脚本中"武器开火"**谁先消费**？',
    'rollback 后**未提交的输入/事件是否全部作废**？',
]

QUEUE_RULE = [
    '🔴 不建模会导致"**已经撤销的攻击仍造成伤害**"·'
    '"**同帧多音只响一次**"·'
    '"**事件在回调中再次入队导致不确定顺序**"',
]

RACE_RULE = [
    '🔑 **内存模型本身应作为测试对象，而不是假设**',
    '🔑 验收指标**不是"测试通过"**，而是'
    '**每个跨线程字段都有明确可见性证据**',
    '🔴 一个**未登记的数据竞争**即使当前平台不出错，'
    '也是 `must-match` 风险',
]

# 🔴 脚本边界
SCRIPT_FIELDS = [
    'entry_point', 'caller_thread',
    '**calling_convention**（sync / async / fire_and_forget）',
    '**reentrancy**', '**panic_or_exception_propagation**',
    '**engine_side_state_on_error**', 'hot_reload_state_transfer',
    'forbidden_api', 'sandbox_capability',
]

SCRIPT_THREE = [
    ('**同步**', '必须在**调用者阶段**完成'),
    ('**真正异步**', '必须**显式返回 future/handle**'),
    ('**延迟应用**', '先把命令写入**确定性队列**，在下一次指定阶段消费'),
]

COMMIT_FIELDS = ['**commit_phase**', '**apply_phase**']

SCRIPT_EXAMPLE = '🔑 "玩家在过渡期间输入装备切换"：脚本直接修改状态 → '
'**可能造成中途取消**；等 committed 才读 → **输入显得钝**；'
'立即应用却仍允许取消 → **可能留下中间状态**'

SCRIPT_RULE = '🔑 这是第 14 轮已覆盖体验的**边界化表达** —— '
'本轮把该语义扩展为**脚本调用通用规则**'

# 🔴 异常四态
ERROR_FOUR = [
    ('**allowed_to_fail**', '允许失败'),
    ('**fail_rolled_back**', '失败并回滚'),
    ('**fail_partial_state**', '失败但留下部分状态'),
    ('**engine_continues_unsafe**', '引擎在不安全状态下继续'),
]

ERROR_FIELDS = [
    '**rollback_scope**（transaction / component / entity / frame / none）',
    'compensation_action', 'diagnostic_level',
    '**must_not_corrupt**（save / replay / network_authority / '
    'resource_handle）',
]

ERROR_RULE = [
    '🔑 **每个边界必须选择四态之一**',
    '🔴 **如果原版不恢复，记录为 `must_match: fail_partial_state` '
    '也不许自行"优化"成事务**',
    '🔑 最重要的原则仍是：**先像素级记录原引擎表现，再有意识地偏离**',
]

# 热重载四语义
HOTRELOAD_FOUR = [
    ('**reload_module_only**', '无状态'),
    ('**preserve_selected_state**', '白名单迁移'),
    ('**restart_runtime**', '全部重置'),
    ('**fork_and_compare**', '旧逻辑继续服务，新逻辑从下一帧接管'),
]

HOTRELOAD_FIELDS = [
    'migration_script', 'preserved_fields', 'default_for_removed_field',
    '**active_coroutine_policy**', '**pending_event_policy**',
    '**resource_handle_policy**',
]

HOTRELOAD_RULE = [
    '🔴 **不能只做"重新编译后文件生效"**',
    '🔑 热重载脚本时**即使路径不变，运行时对象身份仍可能变化** —— '
    '脚本持有资源句柄**必须走版本检查，不能只比较路径或指针**',
]

# 🔴 场景
SCENE_FIELDS = [
    'subworld_id', 'boundary_definition', 'coordinate_space',
    '**origin_shift_policy**', 'load_phases', '**partial_state_policy**',
    '**cross_scene_reference_kind**', 'unload_order', 'authority_scope',
]

PARTIAL_POLICY = [
    'interactive_only_after_all_phases', 'simulate_loading_zone_only',
    'full_physics_lock', 'script_lock_but_input_open',
]

SCENE_RULE = [
    '🔑 **场景是"加载事务"，不是静态关卡文件**',
    '🔑 `partial_state_policy` 必须用上述**明确枚举**，'
    '**不允许写"加载中"**',
    '🔑 **"场景切换完成"和"所有旧对象已销毁"是两个状态** —— '
    '例如 `Destroy()` 只是标记待清理，**不代表立即从内存消失**',
]

CROSS_REF_FIVE = [
    '**全局注册表 ID**', '**弱路径引用**', '**延迟解析句柄**',
    '**复制权威对象**', '**世界持久对象**',
]

CROSS_REF_RULE = [
    '🔑 五种实现**玩法后果不同**；门、剧情、任务、快速旅行、玩家位置'
    '都可能依赖它',
    '🔴 **旧引擎"隐形关卡对象"或"按加载顺序隐式解析"的做法'
    '不应被新引擎的对象引用系统自动改写**',
    '🔑 每个跨区引用要记 `resolution_phase` · 失效语义 · 回滚语义 · '
    '**重连恢复语义**',
]

ORIGIN_FIELDS = [
    'origin_source', '**shift_commit_frame**', 'render_pose_version',
    'camera_query_version', 'physics_world_version',
    'network_transform_version',
]

ORIGIN_RULE = [
    '🔴 **origin 切换必须记录"谁先改、谁后看到"**',
    '🔑 只改逻辑坐标而渲染仍用旧矩阵 → **一帧抖动**',
    '🔑 相机和物理读取不同版本 → **碰撞偏离视觉**',
    '🔑 回滚后 origin 没同步回滚 → **重放不可恢复**',
]

# 调试工具
DEBUG_FIELDS = [
    'overlay_id', '**sample_source**', '**sample_phase**', '**time_origin**',
    'coordinate_space', 'console_command', 'mutation_scope',
    'requires_authority', 'side_effect_safe',
]

DEBUG_RULE = [
    '🔴 **工具消失意味着后续维护失去同一把尺子**',
    '🔑 每项调试量**必须和主循环阶段绑定** —— '
    '否则 HUD 读到的值与回放中的权威值**可能相差一帧**',
    '🔑 需要覆盖：运行时可视化 · 变量暴露 · **性能 HUD** · '
    '**控制台命令** · **录像标注** · **崩溃后恢复状态**',
]

CONFLICTS = [
    '❌ **延迟一帧**当作原因而不说明性质',
    '❌ 笼统说"线程安全"而不写可见性规则',
    '❌ **异步逻辑当作同步逻辑**',
    '❌ **用异常吞掉引擎边界错误**',
    '❌ **脚本里抛错只打日志**',
    '❌ 把"原版不恢复"自行优化成事务',
    '❌ **热重载只做"重新编译后文件生效"**',
    '❌ 只比较路径或指针判断资源身份',
    '❌ **场景部分加载时写"加载中"**',
    '❌ 新引擎自动改写旧引擎的隐式跨区引用',
    '❌ origin 切换不记录谁先改',
    '❌ 调试 HUD 不与主循环阶段绑定',
    '❌ **单机先测、联机后修**',
]

FIELDS = [
    ('item_id', '项编号'),
    ('domain', '域（frame / lag / queue / script / error / hotreload / '
               'scene / debug）'),
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


def cmd_frame(a):
    _hdr('🔴 一帧九个阶段')
    for i, p in enumerate(FRAME_NINE, 1):
        print(f'   {i}. {p}')
    print('\n跨阶段字段: ' + ' · '.join(FRAME_FIELDS))
    print('\n可见性规则: ' + ' · '.join(VISIBILITY_RULES))
    print('\n规则:')
    for r in FRAME_RULE:
        print(f'   {r}')
    print('\n数据竞争:')
    for r in RACE_RULE:
        print(f'   {r}')
    return 0


def cmd_lag(a):
    _hdr('🔴 延迟一帧（**五个方向**）')
    print('字段: ' + ' · '.join(LAG_FIELDS))
    print('\n方向:')
    for k, why in LAG_DIRS:
        print(f'   {k:<20} {why}')
    print(f'\n   {LAG_RULE}')
    return 0


def cmd_queue(a):
    _hdr('事件队列（**消费时机**）')
    print('字段: ' + ' · '.join(QUEUE_FIELDS))
    print('\n必须回答:')
    for q in QUEUE_QUESTIONS:
        print(f'   · {q}')
    print('\n规则:')
    for r in QUEUE_RULE:
        print(f'   {r}')
    return 0


def cmd_script(a):
    _hdr('🔴 脚本与引擎边界')
    print('字段: ' + ' · '.join(SCRIPT_FIELDS))
    print('\n三种语义:')
    for k, why in SCRIPT_THREE:
        print(f'   {k:<14} {why}')
    print('\n关键字段: ' + ' · '.join(COMMIT_FIELDS))
    print(f'\n   {SCRIPT_EXAMPLE}')
    print(f'\n   {SCRIPT_RULE}')
    return 0


def cmd_error(a):
    _hdr('🔴 异常四态')
    for k, why in ERROR_FOUR:
        print(f'   {k:<28} {why}')
    print('\n字段:')
    for f in ERROR_FIELDS:
        print(f'   · {f}')
    print('\n规则:')
    for r in ERROR_RULE:
        print(f'   {r}')
    return 0


def cmd_hotreload(a):
    _hdr('热重载（**四种语义**）')
    for k, why in HOTRELOAD_FOUR:
        print(f'   {k:<26} {why}')
    print('\n字段:')
    for f in HOTRELOAD_FIELDS:
        print(f'   · {f}')
    print('\n规则:')
    for r in HOTRELOAD_RULE:
        print(f'   {r}')
    return 0


def cmd_scene(a):
    _hdr('🔴 场景（**加载事务**）')
    print('字段: ' + ' · '.join(SCENE_FIELDS))
    print('\npartial_state_policy 枚举: ' + ' · '.join(PARTIAL_POLICY))
    print('\n跨场景引用五种: ' + ' · '.join(CROSS_REF_FIVE))
    print('\n规则:')
    for r in SCENE_RULE + CROSS_REF_RULE:
        print(f'   {r}')
    print('\norigin 切换字段: ' + ' · '.join(ORIGIN_FIELDS))
    print('\n规则:')
    for r in ORIGIN_RULE:
        print(f'   {r}')
    return 0


def cmd_debug(a):
    _hdr('调试工具（**消失即失明**）')
    print('字段: ' + ' · '.join(DEBUG_FIELDS))
    print('\n规则:')
    for r in DEBUG_RULE:
        print(f'   {r}')
    return 0


def cmd_init(a):
    os.makedirs(os.path.dirname(a.init) or '.', exist_ok=True)
    with open(a.init, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow([k for k, _ in FIELDS])
        w.writerow(['TODO'] * len(FIELDS))
    print(f'已生成帧/脚本表: {a.init}')
    print('\n⚠️ 八域：frame / lag / queue / script / error / hotreload / '
          'scene / debug')
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
    print(f'帧/脚本 · {len(rows)} 条')
    print('=' * 76)
    if mismatch:
        print(f'\n🚫 **不一致** {len(mismatch)} 条（行 {mismatch[:15]}）')
    if no_legacy:
        print(f'\n❌ {len(no_legacy)} 条缺**原版值**（行 {no_legacy[:15]}）')
    if no_grade:
        print(f'\n🚫 {len(no_grade)} 条**证据等级缺失或 ≥7 级**'
              f'（行 {no_grade[:15]}）')

    if not (mismatch or no_legacy or no_grade):
        print('\n✅ 帧/脚本：一致、原版值完整、证据等级达标')

    print('\n🔑 **"延迟一帧"必须说明是设计、优化还是偏离，不能当原因。**')
    print('   **脚本抛错只打日志不可接受；原版不恢复也不许自行优化成事务。**')
    print('   **场景是加载事务；调试工具消失 = 后续维护失去同一把尺子。**')
    return 1 if (a.gate_check and (mismatch or no_legacy or no_grade)) else 0


def main():
    ap = argparse.ArgumentParser(description='帧时序与脚本边界')
    ap.add_argument('--frame', action='store_true')
    ap.add_argument('--lag', action='store_true')
    ap.add_argument('--queue', action='store_true')
    ap.add_argument('--script', action='store_true')
    ap.add_argument('--error', action='store_true')
    ap.add_argument('--hotreload', action='store_true')
    ap.add_argument('--scene', action='store_true')
    ap.add_argument('--debug', action='store_true')
    ap.add_argument('--init')
    ap.add_argument('--check')
    ap.add_argument('--gate-check', action='store_true')
    a = ap.parse_args()
    fns = {'frame': cmd_frame, 'lag': cmd_lag, 'queue': cmd_queue,
           'script': cmd_script, 'error': cmd_error,
           'hotreload': cmd_hotreload, 'scene': cmd_scene,
           'debug': cmd_debug}
    for k, fn in fns.items():
        if getattr(a, k):
            return fn(a)
    if a.init:
        return cmd_init(a)
    if a.check:
        return cmd_check(a)
    print('❌ 需要 --frame / --lag / --queue / --script / --error / '
          '--hotreload / --scene / --debug / --init / --check 之一')
    return 2


if __name__ == '__main__':
    sys.exit(main())
