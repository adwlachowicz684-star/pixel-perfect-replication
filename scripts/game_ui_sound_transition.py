#!/usr/bin/env python3
"""UI 音效交互层 + 过渡体验（第十四轮 A / B 类）。

**🔑 A 类核心**：
> **"有 hover 音"不是规格，"什么条件下可发声、与谁冲突、失败后是否重试"才是规格。**
> 🔴 **同帧多音不能默认随机播放** —— 必须明确取最高优先级、队列、合并还是截断。
> 🔴 **`hover_repeat` 与 `selection_change` 必须分开** —— 前者是连续焦点轮询，
> 后者是菜单导航的实际移动；合并会造成**手柄摇杆轻微漂移就连续响**。

**🔑 B 类核心**：
> **"加载时长"只是一条数字，十阶段规格才决定玩家是否感到等待。**
> 🔴 **`interactive_ready` 与 `presentation_ready` 必须分开** ——
> 要记录从可输入到完全可见的间隔、此期间能否移动、相机是否可转。

用法:
  game_ui_sound_transition.py --uievent   # UI 音效**事件语义枚举**
  game_ui_sound_transition.py --arbit     # 🔴 同帧仲裁
  game_ui_sound_transition.py --merge     # 同音合并的**事件身份**
  game_ui_sound_transition.py --floor     # 静音**三套阈值**
  game_ui_sound_transition.py --ducking   # 混音与 ducking
  game_ui_sound_transition.py --avsync    # 🔴 音画**样本偏移**
  game_ui_sound_transition.py --spatial   # 2D 音在 3D 世界的**四种语义**
  game_ui_sound_transition.py --transition# 🔴 过渡十阶段状态机
  game_ui_sound_transition.py --kind      # 过渡方式是**模式枚举**
  game_ui_sound_transition.py --input     # 过渡输入**五个独立决策**
  game_ui_sound_transition.py --audio     # 音频交接（**不是"是否连续"**）
  game_ui_sound_transition.py --failure   # 失败呈现是过渡的一部分
  game_ui_sound_transition.py --first     # 首次 vs 重复加载**两张表**
  game_ui_sound_transition.py --init ledger/ui_sound_transition.csv
  game_ui_sound_transition.py --check ledger/ui_sound_transition.csv --gate

退出码: 0 通过 / 1 缺项 / 2 用法错误
"""
import argparse
import csv
import os
import sys

# UI 音效事件枚举
UI_EVENTS = [
    'hover_enter', 'hover_exit', '**hover_repeat**', 'press_down', 'press_up',
    'click_confirm', 'click_cancel', 'back', 'open_start', 'open_end',
    'close_start', 'close_end', 'scroll_tick', 'scroll_stop',
    '**selection_change**', 'value_change', 'error', 'warning', 'notice',
    'unlock',
]

UI_EVENT_RULE = [
    '🔑 推荐事件枚举**不是"按钮音"这种笼统分类**',
    '🔴 **`hover_repeat` 与 `selection_change` 必须分开** —— '
    '前者是连续焦点轮询，后者是菜单导航的实际移动',
    '🔴 很多项目错误地把两者合并 → '
    '**手柄摇杆轻微漂移就连续响**',
]

UI_EVENT_FIELDS = [
    '事件主键', '事件来源', '**视觉配对**', '触发边界', '抑制窗口',
    '最大并发', '**同音策略**', '优先级', '混音组', '空间化',
    '**时间对齐**', '静音规则',
]

# 🔴 同帧仲裁
ARBIT_FIELDS = [
    'requested_at', 'event_id', 'layer', 'priority',
    '**instance_limit_key**', '**same_cue_strategy**', 'max_voice_count',
    'current_voice_count', '**decision**', 'actually_played_at',
]

ARBIT_STRATEGIES = [
    '**取最高优先级**', '**队列**', '**合并**', '**截断**',
]

ARBIT_RULE = [
    '🔴 **同帧多音不能默认随机播放**',
    '🔑 当策略是 `ReplaceOldest` 时，旧音要记录 **fade 曲线与剩余 tail** —— '
    '**不能把结尾瞬间切断**',
    '🔑 当策略是 `RejectNew` 时，新请求未必消失，而可能**改写绑定视觉状态**',
    '🔴 必须把"**播放被拒**"与"**事件被消费**"分开',
]

# 同音合并
MERGE_KEY = [
    '🔑 `same_cue_key` 由**事件类型 + 逻辑上下文 + 可选实体键**组成 —— '
    '**不能只用音频文件名**',
    '🔑 同一按钮 hover 在 50ms 内重复进/出，可能合并为一次 enter',
    '🔑 两个不同伤害数字的同名"coin"**不能合并**',
]

MERGE_FIELDS = [
    'global_cooldown_ms', 'local_cooldown_ms', '**min_retrigger_interval_ms**',
    '首次必播', '最低重复间隔', '**最大合并计数**', '**合并期满后的补播**',
]

MERGE_RULE = '🔑 若合并上限为 4，而第 5 次在 100ms 内到达 → '
'规范要规定"**静默丢弃 / 播放一次汇总音 / 显示未播放计数**"三者之一'

# 静音三套阈值
FLOOR_THREE = [
    '**低于该值转为停止**',
    '**低于该值转为虚拟声部**',
    '**低于该值只隐藏 UI 提示**',
]

FLOOR_RULE = [
    '🔑 `volume_floor_db` 与 `instance_budget` 必须**分别记录**',
    '🔑 **虚声部不等于不执行事件** —— 它仍需计数、更新状态，'
    '但**不再提交 DSP**',
    '🔑 **静音不是把音量写成 0** —— 解除静音后原尾音应继续还是新实例重启，'
    '也必须写成规范',
    '🔑 还应记：UI 音量归零时 hover 是否仍可发声、震动是否继续、'
    '**字幕是否仍出现**',
]

# Ducking
DUCK_FIELDS = [
    'bus_id', 'parent_bus', 'exclusive_group', '**ducking_trigger_bus**',
    'duck_amount_db', '**attack_s**', '**hold_min_s**', '**release_s**',
    'curve', 'sidechain_source', 'filter_bypass',
]

DUCK_RULE = [
    '🔑 混音要把**菜单 / 游戏 / 语音 / 反馈**分成可观察总线',
    '🔑 要写明 ducking 的**触发源、目标、阈值、attack、hold、release、曲线、旁链**',
    '🔑 特别观察"打开菜单后背景音乐下降 6 dB，但 **UI 密集滚动期间不会'
    '逐 tick 抖动**"',
    '🔴 **若只记录最终下降值，就会漏掉 hold/release 导致的呼吸感**',
]

# 🔴 音画同步
AVSYNC_FIELDS = [
    '视觉 onset 帧', '**音频 onset sample**', 'latency_mode',
    '**sample_offset**', '帧边界策略', '**慢动作是否 rescale**',
    '暂停期间是否继续', '**时间回滚时已触发但未播放的声部如何处理**',
]

AVSYNC_CSV = [
    'frame', 'frame_substep', 'event_id', 'visual_onset_ms',
    'audio_onset_ms', 'diff_ms', 'scale_mode', 'paused', 'fullscreen_blur',
]

AVSYNC_RULE = [
    '🔴 **反馈音与画面帧对齐必须测量样本偏移，不能只说"同步"**',
    '🔑 验收应**分别规定平均偏差与最大偏差**',
    '🔑 **慢动作下若音频保持正常音高而画面拉长，也须作为明确模式** —— '
    '不是默认假设',
]

# 2D 音在 3D 世界的四种语义
SPATIAL_MODES = [
    ('none', '纯 2D'),
    ('**anchor**', '**世界锚点 UI 音**'),
    ('screen', '屏幕空间固定'),
    ('**listener**', '跟随玩家 HUD 音'),
    ('**camera**', '相机空间旁白音'),
]

SPATIAL_FIELDS = [
    'spatial_mode', 'anchor_entity_id', 'min_distance', 'max_distance',
    'attenuation_curve_id', 'occlusion_mode', 'orientation_mode',
    'doppler_scale',
]

SPATIAL_RULE = '🔑 从菜单切回世界时，若菜单音正在播放 → '
'必须规定是**转路由 / 保留尾音 / 立即淡出 / 原地空间化**'

# 🔴 过渡十阶段
TRANSITION_STATES = [
    'idle', 'requested', 'pre_transition', '**input_lock_resolved**',
    'asset_reserve', 'load_started', '**interactive_ready**',
    '**presentation_ready**', 'post_transition', 'committed',
]

TRANSITION_FAIL = ['failed', '**retry_or_fallback**']

TRANSITION_RULE = [
    '🔑 `asset_reserve` 要记**内存预算、纹理流送、音频解码、脚本初始化'
    '的先后顺序**',
    '🔴 **`interactive_ready` 与 `presentation_ready` 必须分开** —— '
    '要记从可输入到完全可见的间隔、此期间**能否移动、相机是否可转、'
    '能否开菜单、能否暂停**',
]

# 过渡方式
KINDS = [
    'black_fade', 'cross_fade', '**directional_slide**',
    '**geometric_mask**', 'iris_wipe', '**scripted_event**',
    '**seamless_stream**', 'no_transition',
]

KIND_RULE = [
    '🔑 过渡方式应成为**模式枚举，不能由美术命名反推**',
    '🔑 遮罩**不能只写"圆形"** —— 还要记中心点来源（屏幕中心 / '
    '**玩家屏幕位置** / **交互点**）、半径曲线、抗锯齿宽度、'
    '**是否随玩家移动**、**是否受宽高比和安全区影响**、**是否改变渲染深度**',
    '🔑 方向性滑动要记方向、起始偏移、**是否夹带旧场景**、'
    '**新旧相机各自何时停止**、**是否随设备左右手设置镜像**',
]

# 🔴 过渡输入五决策
INPUT_DECISIONS = [
    '是否接受新输入', '**是否立即执行**',
    '**是否入队并在 committed 后补执行**', '**是否只缓冲白名单动作**',
    '**是否在 interactive_ready 前执行**',
]

INPUT_FIELDS = [
    'input_policy_before_lock', 'input_policy_during_pre_transition',
    'input_policy_during_load', '**earliest_action_frame**',
    'buffer_capacity', 'buffer_ttl_ms', 'whitelist_actions',
    'conflict_resolution',
]

INPUT_RULE = [
    '🔴 **任何一项缺失都会改变竞态**',
    '🔑 若原作允许玩家在**关门动画期间缓冲翻滚**，复刻后却等 `committed` '
    '才读取 → 手感不会"差不多"，**而是明显变钝**',
    '🔑 提前输入与输入丢失是**同一仲裁问题的两面**',
    '🔑 特别测试"进入新场景瞬间按**闪避、菜单确认、暂停、瞄准、移动摇杆**"'
    '是否仍绑定**正确玩家、正确设备、正确输入方案**',
    '🔑 **手柄重连、键盘/手柄切换、输入提示变化**均要在场景交接后重新解析',
]

# 音频交接
AUDIO_HANDOFF = [
    '音乐是否跨场景保留 `MusicBus` 状态', '是否进入新 Playlist',
    '**是否在落幅点切拍**', '**是否允许交叉淡入到下一首的节拍网格**',
    '环境音是否跟随旧世界继续', '**语音是否跨过 loading**',
    '**新场景首个 ambiance 何时淡入**', '过渡尾音是否共享总线',
]

AUDIO_HANDOFF_RULE = [
    '🔑 音频交接**不能只写"是否连续"，必须写快照与淡变**',
    '🔑 **失败重试时，音乐应回到 `requested_snapshot` 还是 '
    '`committed_snapshot`** 必须显式定义',
]

# 失败呈现
FAILURE_FIELDS = [
    '失败检测字段', '**最小失败持续时间**', '是否允许自动重试',
    '最大重试次数', '**指数退避**', '网络超时',
    '**磁盘/内存/资产校验失败是否采用不同文案**', '能否取消',
    '**取消后回到哪个稳定检查点**', '失败后音量是否降低',
    '**震动是否停止**', '**输入是否归还**', '重试期间是否继续显示旧帧',
]

FAILURE_RULE = [
    '🔑 **失败呈现是过渡的一部分，不是弹窗贴图**',
    '🔑 还要观察"**重试成功后跳过 pre_transition、只淡入、还是重放完整演出**"',
]

# 首次 vs 重复
FIRST_TABLES = [
    '**first_cold_load**', 'warm_reload', 'return_from_menu',
    '**resume_from_suspend**', '**retry_after_failure**',
    'asset_already_cached',
]

FIRST_RULE = [
    '🔑 上述六者的**遮罩、音乐、输入、提示和最小表现均可不同**',
    '🔑 冷启动可能有**首次教程、授权后重新初始化、着色器预热、'
    '首次网络握手**',
    '🔑 从挂起恢复可能要求**重新同步时钟**',
    '🔴 **不能把 `is_first_time` 只写成布尔值** —— '
    '应写首次进入各状态的时间点、可跳过点与**首次失败恢复点**',
]

CONFLICTS = [
    '❌ **把 UI 音效统一成一套"通用反馈总线"** —— 只保留 click/error/'
    'open/close 四个事件，会丢失同一操作在不同上下文的差别',
    '❌ 同帧多音默认随机播放',
    '❌ 把 hover_repeat 与 selection_change 合并',
    '❌ 静音写成音量 0',
    '❌ 只记录 ducking 最终下降值（漏掉呼吸感）',
    '❌ 音画"同步"不测样本偏移',
    '❌ 把 interactive_ready 与 presentation_ready 合并',
    '❌ 过渡方式由美术命名反推',
    '❌ 过渡输入等 committed 才读取（**手感明显变钝**）',
    '❌ 音频交接只写"是否连续"',
    '❌ **把 `is_first_time` 只写成布尔值**',
]

FIELDS = [
    ('item_id', '项编号'),
    ('domain', '域（uievent / arbit / merge / floor / ducking / avsync / '
               'spatial / transition / kind / input / audio / failure / first）'),
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


def cmd_uievent(a):
    _hdr('UI 音效事件（**不是"按钮音"**）')
    for e in UI_EVENTS:
        print(f'   · {e}')
    print('\n规则:')
    for r in UI_EVENT_RULE:
        print(f'   {r}')
    print('\n字段: ' + ' · '.join(UI_EVENT_FIELDS))
    return 0


def cmd_arbit(a):
    _hdr('🔴 同帧仲裁')
    print('策略: ' + ' · '.join(ARBIT_STRATEGIES))
    print('\n字段: ' + ' · '.join(ARBIT_FIELDS))
    print('\n规则:')
    for r in ARBIT_RULE:
        print(f'   {r}')
    return 0


def cmd_merge(a):
    _hdr('同音合并（**事件身份 + 时间窗口**）')
    for k in MERGE_KEY:
        print(f'   {k}')
    print('\n字段: ' + ' · '.join(MERGE_FIELDS))
    print(f'\n   {MERGE_RULE}')
    return 0


def cmd_floor(a):
    _hdr('静音（**三套阈值**）')
    for f in FLOOR_THREE:
        print(f'   · {f}')
    print('\n规则:')
    for r in FLOOR_RULE:
        print(f'   {r}')
    return 0


def cmd_ducking(a):
    _hdr('混音与 ducking')
    for f in DUCK_FIELDS:
        print(f'   · {f}')
    print('\n规则:')
    for r in DUCK_RULE:
        print(f'   {r}')
    return 0


def cmd_avsync(a):
    _hdr('🔴 音画同步（**测样本偏移**）')
    for f in AVSYNC_FIELDS:
        print(f'   · {f}')
    print('\nCSV: ' + ' · '.join(AVSYNC_CSV))
    print('\n规则:')
    for r in AVSYNC_RULE:
        print(f'   {r}')
    return 0


def cmd_spatial(a):
    _hdr('2D 音在 3D 世界（**四种语义**）')
    for k, why in SPATIAL_MODES:
        print(f'   {k:<12} {why}')
    print('\n字段: ' + ' · '.join(SPATIAL_FIELDS))
    print(f'\n   {SPATIAL_RULE}')
    return 0


def cmd_transition(a):
    _hdr('🔴 过渡十阶段状态机')
    print('正常: ' + ' → '.join(TRANSITION_STATES))
    print('\n失败: ' + ' → '.join(TRANSITION_FAIL))
    print('\n规则:')
    for r in TRANSITION_RULE:
        print(f'   {r}')
    return 0


def cmd_kind(a):
    _hdr('过渡方式（**模式枚举**）')
    for k in KINDS:
        print(f'   · {k}')
    print('\n规则:')
    for r in KIND_RULE:
        print(f'   {r}')
    return 0


def cmd_input(a):
    _hdr('🔴 过渡输入（**五个独立决策**）')
    for d in INPUT_DECISIONS:
        print(f'   · {d}')
    print('\n字段: ' + ' · '.join(INPUT_FIELDS))
    print('\n规则:')
    for r in INPUT_RULE:
        print(f'   {r}')
    return 0


def cmd_audio(a):
    _hdr('音频交接（**不是"是否连续"**）')
    for h in AUDIO_HANDOFF:
        print(f'   · {h}')
    print('\n规则:')
    for r in AUDIO_HANDOFF_RULE:
        print(f'   {r}')
    return 0


def cmd_failure(a):
    _hdr('失败呈现（**过渡的一部分**）')
    for f in FAILURE_FIELDS:
        print(f'   · {f}')
    print('\n规则:')
    for r in FAILURE_RULE:
        print(f'   {r}')
    return 0


def cmd_first(a):
    _hdr('首次 vs 重复加载（**两张表**）')
    for t in FIRST_TABLES:
        print(f'   · {t}')
    print('\n规则:')
    for r in FIRST_RULE:
        print(f'   {r}')
    return 0


def cmd_init(a):
    os.makedirs(os.path.dirname(a.init) or '.', exist_ok=True)
    with open(a.init, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow([k for k, _ in FIELDS])
        w.writerow(['TODO'] * len(FIELDS))
    print(f'已生成 UI 音效/过渡表: {a.init}')
    print('\n⚠️ 十三域：uievent / arbit / merge / floor / ducking / avsync / '
          'spatial / transition / kind / input / audio / failure / first')
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
    print(f'UI 音效/过渡 · {len(rows)} 条')
    print('=' * 76)
    if mismatch:
        print(f'\n🚫 **不一致** {len(mismatch)} 条（行 {mismatch[:15]}）')
    if no_legacy:
        print(f'\n❌ {len(no_legacy)} 条缺**原版值**（行 {no_legacy[:15]}）')

    if not (mismatch or no_legacy):
        print('\n✅ UI 音效/过渡：一致且原版值完整')

    print('\n🔑 **同帧多音不能默认随机；播放被拒 ≠ 事件被消费。**')
    print('   **interactive_ready 与 presentation_ready 必须分开。**')
    print('   **过渡输入等 committed 才读取 → 手感明显变钝。**')
    return 1 if (a.gate_check and (mismatch or no_legacy)) else 0


def main():
    ap = argparse.ArgumentParser(description='UI 音效与过渡体验')
    ap.add_argument('--uievent', action='store_true')
    ap.add_argument('--arbit', action='store_true')
    ap.add_argument('--merge', action='store_true')
    ap.add_argument('--floor', action='store_true')
    ap.add_argument('--ducking', action='store_true')
    ap.add_argument('--avsync', action='store_true')
    ap.add_argument('--spatial', action='store_true')
    ap.add_argument('--transition', action='store_true')
    ap.add_argument('--kind', action='store_true')
    ap.add_argument('--input', action='store_true')
    ap.add_argument('--audio', action='store_true')
    ap.add_argument('--failure', action='store_true')
    ap.add_argument('--first', action='store_true')
    ap.add_argument('--init')
    ap.add_argument('--check')
    ap.add_argument('--gate-check', action='store_true')
    a = ap.parse_args()
    fns = {'uievent': cmd_uievent, 'arbit': cmd_arbit, 'merge': cmd_merge,
           'floor': cmd_floor, 'ducking': cmd_ducking, 'avsync': cmd_avsync,
           'spatial': cmd_spatial, 'transition': cmd_transition,
           'kind': cmd_kind, 'input': cmd_input, 'audio': cmd_audio,
           'failure': cmd_failure, 'first': cmd_first}
    for k, fn in fns.items():
        if getattr(a, k):
            return fn(a)
    if a.init:
        return cmd_init(a)
    if a.check:
        return cmd_check(a)
    print('❌ 需要 --uievent / --arbit / --merge / --floor / --ducking / '
          '--avsync / --spatial / --transition / --kind / --input / --audio / '
          '--failure / --first / --init / --check 之一')
    return 2


if __name__ == '__main__':
    sys.exit(main())
