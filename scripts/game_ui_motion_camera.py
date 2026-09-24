#!/usr/bin/env python3
"""UI 动态 + 镜头叙事 + 次级盲区（第十四轮 C / D / E / F / G / H 类）。

**🔑 C 类核心**：
> **每个数字滚动动画都应具备确定性的起止与中断语义。**
> 🔴 很多项目只实现"重启"，造成**玩家连续获得金币时数字永远追不上真实值**。
> 🔴 **"假进度"与"真实进度"是两类状态** —— `indirect_fake` 表示逻辑尚未完成
> UI 先营造接近完成；`stage_artificial` 表示到某百分比后等待真条件。

**🔑 D 类核心**：
> **镜头叙事是"控制权五元组"，不是相机参数表。**
> 🔴 **归还控制后不能出现坐标系跳变** —— 若原作把玩家朝向吸附到镜头方向，
> 新作只归还镜头不吸附角色 → **"镜头对但准星偏"**。

用法:
  game_ui_motion_camera.py --numroll  # 🔴 数字滚动**中断语义**
  game_ui_motion_camera.py --progress # 🔴 假进度 vs 真实进度
  game_ui_motion_camera.py --easing   # 缓动要**数学规格**
  game_ui_motion_camera.py --time     # UI 时间域 `TimeMode`
  game_ui_motion_camera.py --scroll   # 滚动吸附是**离散状态机**
  game_ui_motion_camera.py --endstate # 🔴 动画终态是**正确性字段**
  game_ui_motion_camera.py --narrative# 🔴 镜头控制权五元组
  game_ui_motion_camera.py --return   # 归还**不能坐标系跳变**
  game_ui_motion_camera.py --env      # 环境叙事**物件证据**
  game_ui_motion_camera.py --reject   # 🔴 操作失败**故意沉默**
  game_ui_motion_camera.py --scalable # 🔴 自适应是**滞回控制律**
  game_ui_motion_camera.py --firstexp # 首次体验时间表
  game_ui_motion_camera.py --init ledger/ui_motion_camera.csv
  game_ui_motion_camera.py --check ledger/ui_motion_camera.csv --gate

退出码: 0 通过 / 1 缺项 / 2 用法错误
"""
import argparse
import csv
import os
import sys

# 数字滚动
NUMROLL_FIELDS = [
    'value_from', 'value_to', 'format', 'prefix', 'suffix',
    'separator_policy', 'significant_digits', 'duration_ms', 'easing',
    '**velocity_cap_per_s**', 'min_step', 'start_delay_ms',
    '**interrupt_policy**', '**skip_policy**', '**final_frame_snap**',
    'rounding_mode',
]

INTERRUPT_POLICIES = [
    'restart_from_current', 'reverse', 'jump_to_end',
    '**continue_to_new_target**', '**blend_new_curve**',
]

SKIP_POLICIES = [
    '按住跳过', '**再按一次跳过**', '过场自动可跳过',
    '**逻辑完成后才可跳过**',
]

NUMROLL_RULE = [
    '🔴 很多项目只实现"重启" → '
    '**玩家连续获得金币时数字永远追不上真实值**',
    '🔑 `skip_policy` 必须区分上述四种',
]

# 进度条
PROGRESS_KINDS = [
    ('determinate', '真实进度'),
    ('indeterminate', '不确定'),
    ('**indirect_fake**', '**逻辑尚未完成，UI 先营造接近完成**'),
    ('**stage_artificial**', '**到某百分比后等待真条件**'),
]

PROGRESS_FIELDS = [
    '目标值来源', '刷新率', '**是否可超过 100%**', '**回退策略**',
    '**倒退最小可见阈值**', '完成停留时间', '**是否锁在 99%**',
    '**失败后是否立即归零**',
]

PROGRESS_RULE = [
    '🔑 应额外保存 `progress_onset_frame` 与真实阶段 onset',
    '🔴 **验收时禁止 UI 先到 100% 后逻辑再晚数帧完成** —— '
    '除非原作就是该语义',
]

# 缓动
EASING_KINDS = [
    'linear', 'ease_in', 'ease_out', 'ease_in_out', '**back**',
    '**elastic**', '**bounce**', '**steps**', '**custom_bezier**',
]

EASING_FIELDS = [
    'easing_kind', '**control_points**', 'amplitude', 'period',
    '**overshoot_ratio**', 'direction', 'clamp_mode',
    '**可选 60Hz 关键帧采样**',
]

EASING_RULE = [
    '🔑 缓动**不能只写"缓入缓出"，应保存数学规格**',
    '🔑 弹性/回弹要明确**终点是视觉终点还是数学终点**',
    '🔑 若 `overshoot_ratio=0.12`，数字/血条/按钮是否允许**短暂越过逻辑 100%**？'
    '越过则**读数规则、辅助功能读出和稳定排序键**如何处理？',
    '🔑 这些**不是美术细节，而是数据一致性问题**',
]

# 时间域
TIME_MODES = [
    ('game_scaled', '受游戏时间缩放影响'),
    ('**real_time**', '真实时间'),
    ('manual_advance', '手动推进'),
    ('fixed_tick', '固定 tick'),
]

TIME_FIELDS = [
    'affected_by_time_scale', '**min_advance_step_ms**',
    '**max_advance_per_frame_ms**', '**substep_cap**', '**catch_up_policy**',
]

TIME_RULE = [
    '🔑 暂停游戏时，**确认弹窗、伤害数字、HUD 提示、背包飞入、场景过渡遮罩'
    '可以分别属于不同时间域**',
    '🔑 尤其**逐字打字机**，慢动作下必须规定：按字符时间缩放 / '
    '按整体持续时间缩放 / **保持可读恒定速率**',
]

# 滚动吸附
SCROLL_FIELDS = [
    'scroll_axis', 'page_size', 'item_size_policy', 'content_size_source',
    'inertia_curve', 'deceleration', 'friction_model',
    'initial_velocity_cap', 'snap_target', 'snap_duration', 'snap_easing',
    'snap_on_release', 'snap_on_input', '**edge_resistance**',
    '**edge_overscroll_max**', '**edge_return_curve**',
    'nested_scroll_policy', 'focus_preservation', 'scrollbar_visibility_policy',
]

SCROLL_RULE = [
    '🔑 滚动与吸附是**离散状态机，不能只调一个惯性参数**',
    '🔑 `edge_resistance` 与 `edge_overscroll_max` 正是用户会感受到的细节点：'
    '**移动端列表轻微越界再回弹，与 PC 页面对齐硬停，会给人完全不同的"高级感"**',
]

# 编排与终态
ORCHEST_FIELDS = [
    'motion_group_id', 'sequence_order', 'parallel_group', 'start_delay_ms',
    '**stagger_ms**', '**stagger_seed_or_sort_key**', 'navigation_focus_order',
    'read_order', 'completion_order',
]

ORCHEST_RULE = '🔑 多语言文本改变长度后，**原固定延迟可能造成遮罩与正文错位**；'
'若目标项目使用固定帧延迟，`must-match` **不应擅自改成响应式编排**'

END_STATES = [
    'hold_end', 'revert', 'revert_with_duration', 'destroy',
    'detach_from_tree', 'retain_canvas',
]

END_RULE = [
    '🔑 **UI 动画的终态是正确性字段**',
    '🔑 被打断时还要记：是否调用 `on_complete` · 是否回滚副作用 · '
    '**是否保留部分填充** · 是否允许中途销毁资源',
    '🔑 对**拍照/回放冻结**，需规定动画暂停时最后一帧是'
    '**保留显示值 / 逻辑值 / 捕获帧**',
]

# 🔴 镜头叙事
NARRATIVE_FIVE = [
    '**控制权所有者**', '**抢占理由**', '**归还条件**',
    '**落幅**', '**冲突胜者**',
]

NARRATIVE_FIELDS = [
    'active_camera_id', 'blend_weights', '**owner**', '**priority**',
    '**reason**', '**conflict_winner**',
]

NARRATIVE_RULE = [
    '🔑 镜头过场不仅是相机子系统故障，而是**导演层暂时剥夺玩家控制权**，'
    '并约定何时归还',
    '🔑 核心是"**谁优先、何时结束、结束后落在哪里**"',
    '🔑 应要求**导出每帧**的上述六字段；若引擎没有稳定 id，'
    '**应建立确定性映射并写入资产元数据**',
]

RETURN_FIELDS = [
    '玩家模型当前朝向', '相机 yaw/pitch', 'FoV', '瞄准状态', '载具座位',
    '**手柄右摇杆死区**', '**颈部/头部 IK**', '**第一人称手臂位置**',
    '**屏幕中心实体**',
]

RETURN_RULE = '🔴 若原作在归还时把**玩家朝向吸附到镜头方向**，'
'新作只归还镜头不吸附角色 → **"镜头对但准星偏"**'

# 环境叙事
ENV_FIELDS = [
    'object_role', 'state_machine_id', '**damage_stage**', '**wear_level**',
    '**ownership_hint**', '**event_cause**', 'ageing_model',
    'orientation_consistency', '**blood_or_stain_seed**', 'graffiti_text_id',
    'replacement_set_id', 'light_response_id',
]

ENV_STAGES = [
    '完好', '裂纹', '局部崩塌', '**不可通行**', '**永久变化**',
]

ENV_RULE = [
    '🔑 环境叙事的最小单元应是"**物件证据**"，而不是装饰资产',
    '🔑 **破坏程度不是随机贴图，而是状态链**',
    '🔑 应记同一物件在多个进入时机是否保持状态、'
    '**是否在死亡/读档/跨日重置**、**是否与其他物件形成因果链**',
]

ENV_AUDIO = [
    'wind_state', 'wind_direction_response', 'indoor_leakage',
    '**distant_voice_or_machine**', 'verticality_attenuation',
    'reverb_footprint', 'source_occlusion', '**event_age_hint**',
]

ENV_AUDIO_RULE = '🔑 远处声音是否暗示**尚未到达的空间、危险方向、'
'NPC 活动或历史事件**；若远处机器声在玩家**关闭电源后仍播放** → '
'**叙事状态未联动**'

LIGHT_SEMANTIC = [
    '**引导**', '**安全**', '**危险**', '**历史**',
]

LIGHT_FIELDS = [
    '主光方向', '明暗边界', '安全区照度', '**危险区色温**', '闪烁频率',
    '角色受光方向', '**可破坏光源的 fallback**', '**断电后的过渡**',
    '相机自动曝光目标',
]

# 🔴 操作失败
REJECT_CODES = [
    'too_far', '**not_facing**', 'cooldown', 'resource_insufficient',
    'requires_state', 'locked', 'occupied', 'disabled', 'context_invalid',
    'permission_denied', '**unknown**',
]

REJECT_SILENT = [
    '**距交互物极近但面对方向错误**', '**攻击无目标**', '**受控角色死亡**',
    '**摇杆轻微输入**', '**同一动作正在排队**',
]

REJECT_RULE = [
    '🔑 操作失败必须给出"**原因码 — 渠道 — 节流**"三元组',
    '🔴 最容易被漏掉的是 `no_feedback` —— 上述五种场景**可能故意不发声**',
    '🔴 **模板必须显式写"故意沉默"** —— '
    '否则复刻团队会按"未实现"补一个提示',
]

SUPPRESS_FIELDS = [
    '**suppress_key**（reason × target × context × player_action）',
    'first_delay_ms', 'repeat_interval_ms', 'max_visible_count',
    '**stack_policy**（newest_replace/queue/suppress/merge）',
    'group_by_screen_region', 'min_display_time_ms',
]

SUPPRESS_RULE = [
    '🔑 失败提示去重**不能只按文本去重**',
    '🔑 error 音、图标、文字**是否共享同一抑制窗口也要分开**',
    '🔑 若三个资源不足失败共用一条文案，复刻后改成三条独立提示 → '
    '**破坏 UI 节奏和音效密度**',
]

# 🔴 自适应
SCALABLE_FIELDS = [
    'observed_signal（gpu_frame_time/gpu_bound/cpu_bound/temperature/'
    'battery/thermal_state）',
    '采样窗口', '**上升阈值**', '**下降阈值**', '**迟滞带**',
    '上升一帧数', '下降一帧数', 'perceptual_step',
    '**min_duration_before_change**', '**max_changes_per_minute**',
    'cooldown', 'resolution_min_scale', 'resolution_step',
    '**ui_render_scale_mode**', 'target_frame_time', 'safety_cap',
]

SCALABLE_RULE = [
    '🔑 自适应画质**不是"低配开关"，而是滞回控制律**',
    '🔑 **上升阈值与下降阈值不同**，才能防止在临界点反复升降级',
    '🔴 **如果原项目没有滞回，也不能为了"更先进"擅自加入**',
]

DRS_VISIBLE = [
    '渲染目标整数/非整数缩放', '**UI 是否在低分辨率目标上**',
    '**文字抗锯齿变化**', '后处理输入/输出尺寸', '**TAA 历史是否有效**',
    '粒子/贴花是否随相机分辨率', 'UI 截图采样是否跳变',
    '窗口模式与 VRR 行为',
]

DRS_RULE = '🔴 若原作**只在低电量与高温下降级**，新作若默认开启 → '
'**改变整局画质基线**'

# 首次体验
FIRST_EXP = [
    '首次启动', '**首次可控制**', '**首次死亡**', '**首次失败交互**',
    '首次打开地图', '**首次读盘失败**', '首次切换视角', '首次暂停',
    '首次热更新', '**首次跨平台继承存档**',
]

FIRST_EXP_FIELDS = [
    '触发前提', '阻塞条件', '是否可跳过', '**跳过是否进入历史记录**',
    '**失败后下次是否重播**',
]

FIRST_EXP_RULE = '🔴 尤其要防止"**教程已显示过**"布尔值'
'**吞掉首次失败恢复** —— 第一次操作失败应显示提示；'
'第二次主动取消后是否再提示**必须区分**'

CONFLICTS = [
    '❌ **把 UI 音效统一成"通用反馈总线"**',
    '❌ **用预制缓动库替代逐动画规格** —— "风格接近"代替可验收表现',
    '❌ **自动镜头混合器掩盖显式镜头状态**',
    '❌ **响应式 UI 重排代替固定帧动画**',
    '❌ **自动画质按"最佳体验"自适应**',
    '❌ **"失败也反馈一点"当成普适原则**',
    '❌ 数字滚动只实现"重启"',
    '❌ 假进度与真实进度混为一谈',
    '❌ 缓动只写"缓入缓出"',
    '❌ 归还镜头不吸附角色朝向',
    '❌ 把"故意沉默"当未实现补提示',
    '❌ **擅自给没有滞回的原项目加滞回**',
]

FIELDS = [
    ('item_id', '项编号'),
    ('domain', '域（numroll / progress / easing / time / scroll / endstate / '
               'narrative / return / env / reject / scalable / firstexp）'),
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


def cmd_numroll(a):
    _hdr('🔴 数字滚动（**中断语义**）')
    for f in NUMROLL_FIELDS:
        print(f'   · {f}')
    print('\n中断策略: ' + ' · '.join(INTERRUPT_POLICIES))
    print('\n跳过策略: ' + ' · '.join(SKIP_POLICIES))
    print('\n规则:')
    for r in NUMROLL_RULE:
        print(f'   {r}')
    return 0


def cmd_progress(a):
    _hdr('🔴 进度条（**假进度 vs 真实进度**）')
    for k, why in PROGRESS_KINDS:
        print(f'   {k:<20} {why}')
    print('\n字段: ' + ' · '.join(PROGRESS_FIELDS))
    print('\n规则:')
    for r in PROGRESS_RULE:
        print(f'   {r}')
    return 0


def cmd_easing(a):
    _hdr('缓动（**数学规格**）')
    print('类型: ' + ' · '.join(EASING_KINDS))
    print('\n字段: ' + ' · '.join(EASING_FIELDS))
    print('\n规则:')
    for r in EASING_RULE:
        print(f'   {r}')
    return 0


def cmd_time(a):
    _hdr('UI 时间域（**TimeMode**）')
    for k, why in TIME_MODES:
        print(f'   {k:<16} {why}')
    print('\n字段: ' + ' · '.join(TIME_FIELDS))
    print('\n规则:')
    for r in TIME_RULE:
        print(f'   {r}')
    return 0


def cmd_scroll(a):
    _hdr('滚动与吸附（**离散状态机**）')
    for f in SCROLL_FIELDS:
        print(f'   · {f}')
    print('\n规则:')
    for r in SCROLL_RULE:
        print(f'   {r}')
    return 0


def cmd_endstate(a):
    _hdr('🔴 编排与终态（**正确性字段**）')
    print('编排: ' + ' · '.join(ORCHEST_FIELDS))
    print(f'\n   {ORCHEST_RULE}')
    print('\n终态: ' + ' · '.join(END_STATES))
    print('\n规则:')
    for r in END_RULE:
        print(f'   {r}')
    return 0


def cmd_narrative(a):
    _hdr('🔴 镜头叙事（**控制权五元组**）')
    print('五元组: ' + ' · '.join(NARRATIVE_FIVE))
    print('\n每帧导出: ' + ' · '.join(NARRATIVE_FIELDS))
    print('\n规则:')
    for r in NARRATIVE_RULE:
        print(f'   {r}')
    return 0


def cmd_return(a):
    _hdr('归还控制权（**不能坐标系跳变**）')
    for f in RETURN_FIELDS:
        print(f'   · {f}')
    print(f'\n   {RETURN_RULE}')
    return 0


def cmd_env(a):
    _hdr('环境叙事（**物件证据**）')
    for f in ENV_FIELDS:
        print(f'   · {f}')
    print('\n破坏状态链: ' + ' · '.join(ENV_STAGES))
    print('\n规则:')
    for r in ENV_RULE:
        print(f'   {r}')
    print('\n环境音景: ' + ' · '.join(ENV_AUDIO))
    print(f'\n   {ENV_AUDIO_RULE}')
    print('\n光照语义: ' + ' · '.join(LIGHT_SEMANTIC))
    print('\n光照字段: ' + ' · '.join(LIGHT_FIELDS))
    return 0


def cmd_reject(a):
    _hdr('🔴 操作失败（**故意沉默**）')
    print('原因码: ' + ' · '.join(REJECT_CODES))
    print('\n可能故意沉默: ' + ' · '.join(REJECT_SILENT))
    print('\n规则:')
    for r in REJECT_RULE:
        print(f'   {r}')
    print('\n抑制字段: ' + ' · '.join(SUPPRESS_FIELDS))
    print('\n规则:')
    for r in SUPPRESS_RULE:
        print(f'   {r}')
    return 0


def cmd_scalable(a):
    _hdr('🔴 自适应（**滞回控制律**）')
    for f in SCALABLE_FIELDS:
        print(f'   · {f}')
    print('\n规则:')
    for r in SCALABLE_RULE:
        print(f'   {r}')
    print('\n动态分辨率可见性: ' + ' · '.join(DRS_VISIBLE))
    print(f'\n   {DRS_RULE}')
    return 0


def cmd_firstexp(a):
    _hdr('首次体验时间表')
    for e in FIRST_EXP:
        print(f'   · {e}')
    print('\n字段: ' + ' · '.join(FIRST_EXP_FIELDS))
    print(f'\n   {FIRST_EXP_RULE}')
    return 0


def cmd_init(a):
    os.makedirs(os.path.dirname(a.init) or '.', exist_ok=True)
    with open(a.init, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow([k for k, _ in FIELDS])
        w.writerow(['TODO'] * len(FIELDS))
    print(f'已生成 UI 动态/镜头表: {a.init}')
    print('\n⚠️ 十二域：numroll / progress / easing / time / scroll / '
          'endstate / narrative / return / env / reject / scalable / firstexp')
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
    print(f'UI 动态/镜头 · {len(rows)} 条')
    print('=' * 76)
    if mismatch:
        print(f'\n🚫 **不一致** {len(mismatch)} 条（行 {mismatch[:15]}）')
    if no_legacy:
        print(f'\n❌ {len(no_legacy)} 条缺**原版值**（行 {no_legacy[:15]}）')

    if not (mismatch or no_legacy):
        print('\n✅ UI 动态/镜头：一致且原版值完整')

    print('\n🔑 **数字滚动只实现"重启"会让数字永远追不上真实值。**')
    print('   **归还镜头不吸附角色朝向 → 镜头对但准星偏。**')
    print('   **"故意沉默"必须显式写，否则会被当未实现补提示。**')
    return 1 if (a.gate_check and (mismatch or no_legacy)) else 0


def main():
    ap = argparse.ArgumentParser(description='UI 动态与镜头叙事')
    ap.add_argument('--numroll', action='store_true')
    ap.add_argument('--progress', action='store_true')
    ap.add_argument('--easing', action='store_true')
    ap.add_argument('--time', action='store_true')
    ap.add_argument('--scroll', action='store_true')
    ap.add_argument('--endstate', action='store_true')
    ap.add_argument('--narrative', action='store_true')
    ap.add_argument('--return', dest='ret', action='store_true')
    ap.add_argument('--env', action='store_true')
    ap.add_argument('--reject', action='store_true')
    ap.add_argument('--scalable', action='store_true')
    ap.add_argument('--firstexp', action='store_true')
    ap.add_argument('--init')
    ap.add_argument('--check')
    ap.add_argument('--gate-check', action='store_true')
    a = ap.parse_args()
    fns = {'numroll': cmd_numroll, 'progress': cmd_progress,
           'easing': cmd_easing, 'time': cmd_time, 'scroll': cmd_scroll,
           'endstate': cmd_endstate, 'narrative': cmd_narrative,
           'ret': cmd_return, 'env': cmd_env, 'reject': cmd_reject,
           'scalable': cmd_scalable, 'firstexp': cmd_firstexp}
    for k, fn in fns.items():
        if getattr(a, k):
            return fn(a)
    if a.init:
        return cmd_init(a)
    if a.check:
        return cmd_check(a)
    print('❌ 需要 --numroll / --progress / --easing / --time / --scroll / '
          '--endstate / --narrative / --return / --env / --reject / '
          '--scalable / --firstexp / --init / --check 之一')
    return 2


if __name__ == '__main__':
    sys.exit(main())
