#!/usr/bin/env python3
"""物理—模拟隐性耦合 + 资源生命周期（第二十一轮 A / B 类）。

**🔑 A 类核心**：
> 换引擎后真正漂移的是**所有权**，不是质量设置。
> 🔴 **每个模拟值只能有一个 writer，且每个 reader 必须声明
> 它读取的是哪一帧版本**。

**🔑 B 类核心**：
> 资源的核心不是加载失败或内存峰值，而是
> "**同一资源身份、旧句柄是否失效、何时仍能安全读取**"。
>
> 🔴 **仅比较指针会同时漏掉内容更新和资源被复用。**

用法:
  game_sim_resource.py --ownership # 🔴 **驱动权表**（谁写谁读哪一帧）
  game_sim_resource.py --ragdoll  # 布娃娃/IK/根运动**分别登记**
  game_sim_resource.py --audio    # 🔴 碰撞音是**物理事件还是动画事件**
  game_sim_resource.py --fork     # **视觉物理 vs 逻辑物理**必须显式
  game_sim_resource.py --life     # 🔴 资源**六态生命周期**
  game_sim_resource.py --identity # 🔴 身份**六种语义**
  game_sim_resource.py --pool     # 🔴 池化是**对象身份第三种语义**
  game_sim_resource.py --init ledger/sim_resource.csv
  game_sim_resource.py --check ledger/sim_resource.csv --gate

退出码: 0 通过 / 1 缺项 / 2 用法错误
"""
import argparse
import csv
import os
import sys

# 🔴 驱动权
OWNERSHIP_FIELDS = [
    '**source_of_truth**', '**write_phase**', '**read_phase**',
    '**query_sync_policy**', 'rollback_policy', '**visual_physics_fork**',
]

OWNERSHIP_SOURCES = [
    '动画 Pose', '刚体 Transform', '**根运动**', '**IK**', '**相机**',
    '**玩法判定**',
]

QUERY_SYNC = ['auto_sync', 'explicit_flush_before_query', 'post_sim_only']

OWNERSHIP_RULE = [
    '🔴 **每个模拟值只能有一个 writer**',
    '🔴 **每个 reader 必须声明它读取的是哪一帧版本**',
    '🔑 `query_sync_policy` 必须**显式三选一，不得默认**',
    '🔑 "同一帧"内部至少存在**逻辑阶段、模拟阶段、提交/渲染阶段**三道边界',
    '🔴 **不能把跨阶段的读取默认成即时可见**',
]

OWNERSHIP_QUESTIONS = [
    '某个 Pose 在**哪一时刻**是权威数据源？',
    '根运动写入 Transform 后，物理查询**立即看见吗**？',
    '动画事件播放的碰撞声，能否在**动画回滚后撤销**？',
    '相机碰撞改变相机位置后，是否又通过**下一阶段相机射线**'
    '进入同一帧的物理结果？',
]

# 布娃娃
RAGDOLL_FIELDS = [
    '**ragdoll_transition_frame**（动画→布娃娃、布娃娃→起身）',
    'ragdoll_primary_bone', '**actor_snap_source**（骨盆/平均重心/胶囊中心）',
    '**pelvis_z_correction**', '**yaw_source**', 'mesh_collider_state',
    'capsule_state', 'sleep_velocity',
]

RAGDOLL_RULE = [
    '🔴 **布娃娃、IK 与根运动必须分别登记驱动权** —— '
    '**不能用一个"物理角色"开关概括**',
    '🔑 可测的体验细节：倒地瞬间**胶囊是否嵌入地面** · '
    '布娃娃改变位置后**相机是否立即跟随** · '
    '**起身朝向是否翻转** · **低速滑动是否永远不会停止**',
]

RAGDOLL_TRAP = '🔑 反例：**直接以骨盆设置 Actor 位置会让胶囊嵌入地面** —— '
'必须以射线或胶囊高度补偿。（该材料**只能作为取证线索，不能作为规范级证据**）'

# 🔴 音频耦合
AUDIO_FIELDS = [
    '**事件源**', '**撤销性**', '**空间化上下文**',
]

AUDIO_PHYSICS = [
    '碰撞法向', '相对速度', '材质对', '**接触寿命**',
    '**是否 first_contact_only**', '**是否允许同一接触多次发声**',
]

AUDIO_ANIM = [
    '事件在**动画曲线上的精确时间**', '**循环归一化位置**',
    '**裁剪后是否仍触发**', '**回滚后是否补偿**',
]

AUDIO_RULE = [
    '🔴 若原版采用**动画事件**，而复刻误用**物理接触** → '
    '在**慢动作、回滚、跳跃门槛、固定步频率变化**时产生'
    '"**多余脚步**"或"**缺脚步**"',
    '🔑 这正属于 `must-match`：**声音不是反馈装饰，'
    '而是玩家判断落地、重量和距离的感知输入**',
]

# 视觉物理分叉
FORK_FIELDS = ['enabled', '**fork_frame**', '**reader_list**',
               'reconciliation']

FORK_RULE = [
    '🔑 **视觉物理与逻辑物理允许分叉，但必须在表中显式声明**',
    '🔑 角色胶囊用于判定、布娃娃只用于表现 → 二者可以不同',
    '🔴 **但若视觉骨骼驱动了伤害盒、镜头碰撞或交互触发，'
    '就不再是纯视觉**',
    '🔑 验收必须生成"**逻辑快照**"与"**视觉快照**"两个轨道',
]

# 🔴 资源六态
LIFE_STATES = [
    '**已声明未加载**', '**加载中**', '**已加载**', '**被引用**',
    '**可回收**', '**已释放/待清理**',
]

LIFE_FIELDS = [
    '**load_policy**（path_key / content_hash / manual）',
    '**reference_kind**（strong / weak / counted / observer）',
    '**identity_rule**（same_path_is_same_object / versioned / '
    'instance_local）',
    '**unload_policy**（refcount_zero / scene_unload / manual / '
    'never_in_session）',
    '**hot_reload_policy**（atomic_swap / deferred_next_frame / '
    'invalidated_handle）',
]

LIFE_RULE = [
    '🔑 从磁盘加载资源时**只加载一次**；内存中已有副本时再次加载'
    '**会返回同一副本**',
    '🔑 **节点销毁不一定释放共享资源**；共享图片、网格等'
    '**跨场景实例共享**',
    '🔴 热重载后的"**同一路径**"**不一定是"同一对象"**',
]

# 🔴 身份六种
IDENTITY_SIX = [
    ('**path_identity**', '路径相同'),
    ('**content_identity**', '内容哈希相同'),
    ('**runtime_identity**', '对象地址相同'),
    ('**handle_identity**', '外部句柄相同'),
    ('**versioned_identity**', '路径与句柄版本相同'),
    ('**logical_identity**', '游戏语义相同但对象已替换'),
]

IDENTITY_FOUR = [
    '**source_id**（路径、包、哈希）', '**asset_version**（内容版本）',
    '**runtime_id**（内存对象）', '**handle_version**（外部句柄）',
]

IDENTITY_RULE = [
    '🔑 资源身份至少**四层**：' + ' · '.join(IDENTITY_FOUR),
    '🔴 **仅比较指针会同时漏掉内容更新和资源被复用**',
    '🔑 旧存档引用、多人同步、热重载和脚本回调**各应使用哪一种'
    '必须逐项写死**',
    '🔴 否则会出现"**资源已经替换，旧回调仍在读写**"的悬挂状态 —— '
    '**局部测试不崩溃，却在连续游玩数小时后暴露**',
]

# 🔴 池化
POOL_FIELDS = [
    '**acquire_frame**', '**return_frame**',
    '**reset_scope**（transform / velocity / collider / anim_state / '
    'audio_voice / network_id）',
    'reuse_delay', 'quarantine_after_crash',
]

POOL_RULE = [
    '🔑 **池化不是资源的二级优化，而是对象身份的第三种语义**',
    '🔴 最易遗漏的**不是"归还"**，而是：归还后**上一引用是否仍可读** · '
    '下一次取出是否**保留碰撞历史** · **动画状态机是否回到确定性入口** · '
    '**音频句柄是否还占用混音器 voice**',
    '🔑 一个旧引用读取到已被复用的敌人对象，表现为'
    '"**死人突然出现在别处**" —— **这不是野指针，'
    '而是对象身份没有版本化**',
]

CONFLICTS = [
    '❌ **物理只求看起来差不多**',
    '❌ **共享资源直接复制指针**',
    '❌ 异步逻辑当作同步逻辑',
    '❌ **用异常吞掉引擎边界错误**',
    '❌ **单机先测、联机后修**',
    '❌ 用一个"物理角色"开关概括布娃娃/IK/根运动',
    '❌ **直接以骨盆设置 Actor 位置**（胶囊嵌入地面）',
    '❌ 把动画事件改成物理接触触发碰撞音',
    '❌ 视觉物理分叉未声明',
    '❌ **延迟一帧**当作原因而不说明是设计/优化/偏离',
    '❌ 热重载只做"重新编译后文件生效"',
    '❌ 旧句柄失效却不版本化',
    '❌ 池对象归还后仍被旧引用读取',
]

FIELDS = [
    ('item_id', '项编号'),
    ('domain', '域（ownership / ragdoll / audio / fork / life / '
               'identity / pool）'),
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


def cmd_ownership(a):
    _hdr('🔴 驱动权表（**谁写谁读哪一帧**）')
    print('字段: ' + ' · '.join(OWNERSHIP_FIELDS))
    print('\n权威源: ' + ' · '.join(OWNERSHIP_SOURCES))
    print('\nquery_sync_policy 三选一: ' + ' · '.join(QUERY_SYNC))
    print('\n规则:')
    for r in OWNERSHIP_RULE:
        print(f'   {r}')
    print('\n必须回答:')
    for q in OWNERSHIP_QUESTIONS:
        print(f'   · {q}')
    return 0


def cmd_ragdoll(a):
    _hdr('布娃娃 / IK / 根运动（**分别登记**）')
    for f in RAGDOLL_FIELDS:
        print(f'   · {f}')
    print('\n规则:')
    for r in RAGDOLL_RULE:
        print(f'   {r}')
    print(f'\n   {RAGDOLL_TRAP}')
    return 0


def cmd_audio(a):
    _hdr('🔴 物理—音频耦合')
    print('三项: ' + ' · '.join(AUDIO_FIELDS))
    print('\nphysics_contact 触发要记: ' + ' · '.join(AUDIO_PHYSICS))
    print('\nanim_notify 触发要记: ' + ' · '.join(AUDIO_ANIM))
    print('\n规则:')
    for r in AUDIO_RULE:
        print(f'   {r}')
    return 0


def cmd_fork(a):
    _hdr('视觉物理 vs 逻辑物理（**必须显式**）')
    print('字段: ' + ' · '.join(FORK_FIELDS))
    print('\n规则:')
    for r in FORK_RULE:
        print(f'   {r}')
    return 0


def cmd_life(a):
    _hdr('🔴 资源六态生命周期')
    for i, s in enumerate(LIFE_STATES, 1):
        print(f'   {i}. {s}')
    print('\n字段:')
    for f in LIFE_FIELDS:
        print(f'   · {f}')
    print('\n规则:')
    for r in LIFE_RULE:
        print(f'   {r}')
    return 0


def cmd_identity(a):
    _hdr('🔴 身份六种语义')
    for k, why in IDENTITY_SIX:
        print(f'   {k:<24} {why}')
    print('\n四层标识: ' + ' · '.join(IDENTITY_FOUR))
    print('\n规则:')
    for r in IDENTITY_RULE:
        print(f'   {r}')
    return 0


def cmd_pool(a):
    _hdr('🔴 池化（**对象身份第三种语义**）')
    for f in POOL_FIELDS:
        print(f'   · {f}')
    print('\n规则:')
    for r in POOL_RULE:
        print(f'   {r}')
    return 0


def cmd_init(a):
    os.makedirs(os.path.dirname(a.init) or '.', exist_ok=True)
    with open(a.init, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow([k for k, _ in FIELDS])
        w.writerow(['TODO'] * len(FIELDS))
    print(f'已生成模拟/资源表: {a.init}')
    print('\n⚠️ 七域：ownership / ragdoll / audio / fork / life / '
          'identity / pool')
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
    print(f'模拟/资源 · {len(rows)} 条')
    print('=' * 76)
    if mismatch:
        print(f'\n🚫 **不一致** {len(mismatch)} 条（行 {mismatch[:15]}）')
    if no_legacy:
        print(f'\n❌ {len(no_legacy)} 条缺**原版值**（行 {no_legacy[:15]}）')
    if no_grade:
        print(f'\n🚫 {len(no_grade)} 条**证据等级缺失或 ≥7 级**'
              f'（行 {no_grade[:15]}）')

    if not (mismatch or no_legacy or no_grade):
        print('\n✅ 模拟/资源：一致、原版值完整、证据等级达标')

    print('\n🔑 **换引擎后漂移的是所有权，不是质量设置。**')
    print('   **每个模拟值只能有一个 writer；每个 reader 要声明读哪一帧。**')
    print('   **仅比较指针会漏掉内容更新和资源被复用。**')
    return 1 if (a.gate_check and (mismatch or no_legacy or no_grade)) else 0


def main():
    ap = argparse.ArgumentParser(description='物理耦合与资源生命周期')
    ap.add_argument('--ownership', action='store_true')
    ap.add_argument('--ragdoll', action='store_true')
    ap.add_argument('--audio', action='store_true')
    ap.add_argument('--fork', action='store_true')
    ap.add_argument('--life', action='store_true')
    ap.add_argument('--identity', action='store_true')
    ap.add_argument('--pool', action='store_true')
    ap.add_argument('--init')
    ap.add_argument('--check')
    ap.add_argument('--gate-check', action='store_true')
    a = ap.parse_args()
    fns = {'ownership': cmd_ownership, 'ragdoll': cmd_ragdoll,
           'audio': cmd_audio, 'fork': cmd_fork, 'life': cmd_life,
           'identity': cmd_identity, 'pool': cmd_pool}
    for k, fn in fns.items():
        if getattr(a, k):
            return fn(a)
    if a.init:
        return cmd_init(a)
    if a.check:
        return cmd_check(a)
    print('❌ 需要 --ownership / --ragdoll / --audio / --fork / --life / '
          '--identity / --pool / --init / --check 之一')
    return 2


if __name__ == '__main__':
    sys.exit(main())
