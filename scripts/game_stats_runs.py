#!/usr/bin/env python3
"""统计/回放/竞速/分享 + 教学/无障碍替代/模组顺序（第二十七轮 D / E / F / G 类，
含 H 类输入意图谱系与版本锁定）。

**🔑 D 类核心**：
> 🔑 **游玩统计、累计口径、击杀回放、截图录像、导出分享和竞速计时
> 都是功能契约 —— 重制常把整片能力当菜单丢弃。**
> 🔴 **原版若把死亡四类分别统计，复刻不能合并成一个"死亡次数"。**
> 🔑 speedrun 必须分别记 **RTA / IGT**，**不能用一个"游戏时间"字段替代**。

用法:
  game_stats_runs.py --stat    # 统计**逐项口径**
  game_stats_runs.py --profile # 玩家画像（**事实表**而非隐私）
  game_stats_runs.py --replay  # 🔑 回放**四层**，不能都叫 replay
  game_stats_runs.py --share   # 分享导出记"**导出时世界**"
  game_stats_runs.py --speed   # 🔴 speedrun**竞速契约**
  game_stats_runs.py --tutorial # 教学**强制边界**
  game_stats_runs.py --a11y    # 🔑 无障碍**替代方案**（三语义）
  game_stats_runs.py --mod     # 模组**加载顺序与冲突四层**
  game_stats_runs.py --lineage # H1 输入**意图谱系**
  game_stats_runs.py --lock    # H2 版本**锁定物料清单**
  game_stats_runs.py --init ledger/stats_runs.csv
  game_stats_runs.py --check ledger/stats_runs.csv --gate

退出码: 0 通过 / 1 缺项 / 2 用法错误
"""
import argparse
import csv
import os
import sys

# 统计口径
STAT_FIELDS = [
    'stat_id', 'display_format', 'raw_type', 'unit',
    '**scope**', 'lifetime_scope', '**accumulation_rule**',
    'retry_policy', '**menu_time_policy**', 'loading_time_policy',
    'cutscene_time_policy', 'pause_policy', 'failed_run_policy',
    'replay_policy', 'rollback_policy', 'cross_save_merge_policy',
    'version_migration_policy', 'achievement_gate', 'leaderboard_eligibility',
    'evidence',
]

STAT_SCOPE = ['当前存档', '角色', '周目', '全账号']

STAT_ACC = ['sum', 'max', 'min', 'set', 'replace', 'last-write-wins']

STAT_QUESTIONS = [
    '击杀数是按"**造成伤害**"还是按"**确认死亡**"',
    '**失败重试算一次还是全部累计**',
    '**读取旧档后是否撤销**',
    '**菜单停留是否计入游玩时间**',
    '**加载时间是否计入 RTA**',
    '自动暂停是否冻结时钟',
    '过场不可跳时是否计入',
    '**删档后是否保留全账号记录**',
    '同一账号多平台能否合并',
    '**更新改变统计定义后旧值是否保留**',
]

STAT_RULE = '🔴 **原版若把死亡四类（剧情·战斗·环境·坠落）分别统计，'
'复刻不能合并成一个"死亡次数"** —— 否则筛选、成就和玩家回忆都失效'

# 画像
PROFILE_FOUR = [
    ('**确定的游戏事实**', 'total_kills · longest_speedrun_run_id · '
     'collectible_bits'),
    ('**可验证运行**', 'run_hash · seed · version · modset_hash'),
    ('**展示性画像**', 'preferred_weapon · play_style_cluster'),
    ('**分享导出**', 'screenshot_exr_png · video_container · '
     'telemetry_export'),
]

PROFILE_RULE = [
    '🔑 **玩家画像不是隐私问题，而是复刻后的"事实表"问题**',
    '🔑 若原版只保存最后使用武器，新引擎**不能凭行为模型推断并展示成事实**',
    '🔑 若原版没有画像，新引擎新增画像**不属于 must-match**，'
    '但**必须显式立项**',
]

# 🔑 回放四层
REPLAY_FOUR = [
    ('**input_replay**', '保存**原始输入与时间**'),
    ('**state_replay**', '保存**关键状态哈希**'),
    ('**video_replay**', '只是**观演媒体**'),
    ('**highlight_replay**', '由事件触发并**重新查询可验证运行**'),
]

REPLAY_KILL = [
    'victim_id', 'damage_events', '**hitbox_snapshot**', 'animation_event',
    'camera_bookmark', '**authority**',
]

REPLAY_RULE = [
    '🔑 **回放至少分四层，不能都叫 replay**',
    '🔑 击杀回放应携带 ' + ' · '.join(REPLAY_KILL) +
    ' —— **避免只保存"事件发生"而无法解释最后一击**',
    '🔑 精彩时刻**不能依赖用户开关**，建议以**环形缓冲**保存最近 N 秒的'
    '原始输入、事件和必要状态',
    '🔑 但缓冲**长度 · 压缩 · 覆盖 · 删除策略要固定**',
]

# 分享
SHARE_FIELDS = [
    '场景', '相机', 'pose', '时间', '天气', '画质', '**HDR 显示映射**',
    '字幕与 UI 可见性',
]

SHARE_VIDEO = [
    '编码参数', '帧率', '时基', '音轨', '开始/结束 game time',
    '**IGT/RTA**', 'mod 声明', '版本',
]

SHARE_RULE = [
    '🔑 **分享和导出必须记录"导出时世界"而不是"当前世界"**',
    '🔴 分享内容**不得由新引擎默认加水印 · 裁剪 · 重新调色 · 自动配音** —— '
    '这些可作为选项，但**不是原版行为**',
]

# 🔴 speedrun
SPEED_ROWS = [
    ('**RTA**', '起点与终点 wall-clock 区间 · 加载 · 暂停 · 退出重入',
     '只保留游戏内计时'),
    ('**IGT**', '时间域 · 暂停冻结 · 菜单/过场是否计入 · 帧时间',
     '改引擎时钟后无法对齐原版 timer'),
    ('**segment**', '区间定义 · 时间补偿 · 加载归属', '分段不可比较'),
    ('**ruleset**', 'Any% / 100% / glitch / glitchless / NG+ / 低等级',
     '一个默认排行榜替代全部'),
    ('**加载时间**', '是否计时 · 分段归属 · 同一设备测试条件',
     '**新引擎更快被判为加速**'),
    ('**暂停**', '冻结 · 继续 · 重试 · 菜单是否暂停',
     '暂停策略变化改变路线'),
    ('**校验**', 'build hash · mod hash · seed · input hash · 录影',
     '只接受视频而无可验证状态'),
    ('**公平性**', '帧率 · 轮询率 · 超分/帧生成/预编译 · 平台差异',
     '**画质档或硬件影响可重复策略**'),
]

SPEED_SOT = [
    'original_game_timer', 'rta', 'community_rules', '**new_definition**',
]

SPEED_RULE = [
    '🔑 **speedrun 是统计盲区中信息密度最高的一项**',
    '🔑 契约逐项写 `source_of_truth`；🔴 若为 `**new_definition**`，'
    '必须写明**原版依据 · 是否影响成就 · 是否影响排行榜和分享**',
    '🔑 验证器计算 **RTA · IGT · 每个 split · IL · PB delta · loading · '
    'menu · pause · retry**，产出机器可读报告',
    '🔑 排行榜三段式：原始值 · **规则集版本** · **可复现证据**；'
    '**更新统计定义时旧记录不得重写**，应标 schema 版本',
]

SPEED_PB = '🔴 **PB 必须保留历史上下文，不能只覆盖一个更优数字**'

# 教学
TUTORIAL_FIELDS = [
    'tutorial_id', 'trigger_state', '**must_present**', 'can_skip',
    'skip_requires', 'retry_policy', 'abandon_policy', 'fail_state',
    '**retrigger_conditions**', '**retrigger_suppressions**',
    'completion_criteria', 'soft_prompt', 'hard_block', 'pause_game',
    'save_point', 'achievement_bit', 'collection_bit', 'cutscene_id',
    'localization_id', 'accessibility_alternatives', 'owner',
]

TUTORIAL_TRIGGERS = [
    '首次见机制', '失败重试', '角色死亡后', '难度变化', '**设备变化**',
    '**输入方案变化**', '**语言变化**', '字幕/音频变化', '画质变化',
    '回放/观战', '低体力或多次失败', '存档损坏恢复', '跨周目继承',
]

TUTORIAL_RULE = [
    '🔑 **教学不是"可跳过/不可跳过"一个开关**，'
    '而是每个教学单元的**可见性 · 控制权 · 后果**',
    '🔑 `retrigger_suppressions` 防止"**换手柄语言就再上一遍教学**"',
    '🔑 但 `must_present` 要明确哪些属于**法律 · 安全 · 核心机制**，'
    '**不能由无障碍选项关闭**',
    '🔑 失败后果必须区分：重试当前 · 回到检查点 · 重放整段 · 降级难度 · '
    '解锁辅助 · 只关闭该教学 · 写失败统计 —— '
    '🔴 **不得用统一"跳过教学"代替**',
]

# 🔑 无障碍替代
A11Y_CHANNELS = [
    ('**visual**', 'color / shape / icon / text / 亮度'),
    ('**auditory**', 'pitch / pan / rhythm / voice'),
    ('**haptic**', 'intensity / pattern / duration'),
    ('**narrative/ui**', '字幕 / 标签 / 编号 / 位置'),
]

A11Y_SEMANTIC = [
    ('**equivalent**', '**所有判定 · 奖励 · 节奏 · 记录资格相同**'),
    ('**assisted**', '帮助玩家但**改变难度或记录**'),
    ('**different**', '只提供信息，**不授予原机制权利**'),
]

A11Y_RULE = [
    '🔑 **必须从双通道设计升级为逐条替代映射，且记录玩法是否等价**',
    '🔑 每项事实建 `fact_id` 与**四个通道**；每通道写 `encoding · '
    'minimum_duration · redundancy · can_be_simultaneous · '
    'player_controllable`',
    '🔑 颜色信息除颜色外还应有**形状 · 文字 · 位置 · 编号 · 纹理**',
    '🔑 快速反应除时限外还可提供**放宽窗口 · 按住替代点按 · '
    '自动成功一次 · 提示模式 · 训练模式**',
]

A11Y_EXAMPLE = '🔑 把必须听音辨位的声音变成屏幕箭头，'
'**可能消除原玩法**；只降低 QTE 窗口而不提供相同替代，'
'则**信息未真正到达**'

A11Y_MORE = [
    '相机快摇 · 闪光 · 屏幕震动必须分别记 **vestibular-safe 替代**',
    '**颜色盲模式不能只换色板**，还要确认形状/编号独立可辨',
    '字幕要记**说话人 · 定位 · 持续时间 · 音效标签 · 口型 · 配音版本**',
]

# 模组
MOD_FIELDS = [
    '**mod_id**', 'version', 'engine_version_range', 'game_version_range',
    'checksum', 'signature_policy', '**load_phase**', '**load_priority**',
    'depends_on', 'optional_depends_on', 'conflicts_with',
    'soft_conflicts_with', 'patches', 'file_patches', 'asset_overrides',
    'data_overrides', 'script_overrides', 'last_written_component',
    '**determinism_impact**', 'save_compatibility', 'allowed_together_hash',
]

MOD_ORDER = [
    '先按**声明依赖做拓扑排序**',
    '再按显式 `load_priority`',
    '**同优先级按稳定字典序**',
    '🔴 **循环依赖必须拒绝**或请求用户拆解为冲突方案',
]

MOD_CONFLICT = [
    ('**manifest conflict**', '版本/依赖'),
    ('**asset path conflict**', '资源路径'),
    ('**data key conflict**', '同一数据表键'),
    ('**runtime semantic conflict**', '同一钩子 / 同一冷却起点 / 同一相机规则'),
]

MOD_CONFLICT_FIELDS = [
    'conflict_id', 'left', 'right', 'resolution', 'user_choice_hash',
    'first_detected_frame', 'severity',
]

MOD_RECOVERY = [
    'disable_conflicting_mod', 'disable_newest', 'disable_non_essential',
    'ask_user', 'abort_session', 'safe_mode_with_core_mods',
    'restore_last_working_set',
]

MOD_RULE = [
    '🔑 **模组系统的核心不是 API，而是加载顺序 · 依赖 · 覆盖 · '
    '故障隔离的"可复现图"**',
    '🔑 加载顺序应有**显式算法**，**而非只靠拖拽**',
    '🔑 正确做法：**保存前计算模组签名，加载时校验，不兼容则明确迁移**，'
    '🔴 **而不是静默吞错**',
    '🔑 整体回退虽然安全，却可能让用户无法继续；部分禁用虽灵活，'
    '却**可能破坏保存兼容** —— 必须记录**旧档是否仍合法**',
]

# H1 意图谱系
LINEAGE_FIELDS = [
    'intent_id', 'device_event_id', '**timestamp_domain**', 'raw_value',
    'deadzone', 'remap', 'repeat_policy', '**selection_change**',
    '**hover_repeat**', 'hold_progress', 'combo_window', '**commit_frame**',
    'latency_frames', 'suppressed_by_ui', 'suppressed_by_cutscene',
    'authority', 'cancel_result',
]

LINEAGE_CHAIN = [
    'intent → committed intent → action request → physics command → '
    'network command → feedback',
]

LINEAGE_RULE = '🔑 这个谱系能直接解释"**过渡输入等 committed 才读会变钝**"、'
'"**hover_repeat 与 selection_change 混用**"、'
'"**装备切换隐含依赖帧率**"'

# H2 版本锁定
LOCK_FIELDS = [
    'lockfile', 'build_manifest', 'source_hash', '**toolchain_hash**',
    'engine_patch_id', '**shader_tool_version**', 'asset_pipeline_version',
    'platform_sdk_version', 'runtime_attestation',
]

CONFLICTS = [
    '❌ **给玩家"更好的现代计时"**',
    '❌ **用总时长代替分段**',
    '❌ 自动去除加载"更公平"',
    '❌ 按当前硬件自动分榜',
    '❌ 只保留游戏内计时',
    '❌ **PB 只覆盖一个更优数字**',
    '❌ 更新统计定义时重写旧记录',
    '❌ 合并死亡四类统计',
    '❌ **凭行为模型推断并展示成事实**',
    '❌ 只提供开关不提供替代',
    '❌ **把听音辨位变成屏幕箭头却称等价**',
    '❌ 颜色盲模式只换色板',
    '❌ 用统一"跳过教学"代替失败后果分类',
    '❌ 模组加载顺序只靠拖拽',
    '❌ **静默吞掉模组不兼容**',
    '❌ 分享默认加水印/裁剪/重新调色/自动配音',
]

FIELDS = [
    ('item_id', '项编号'),
    ('domain', '域（stat / profile / replay / share / speed / tutorial / '
               'a11y / mod / lineage / lock）'),
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


def cmd_stat(a):
    _hdr('统计（**逐项口径**）')
    print('字段: ' + ' · '.join(STAT_FIELDS))
    print('\nscope: ' + ' · '.join(STAT_SCOPE))
    print('accumulation_rule: ' + ' · '.join(STAT_ACC))
    print('\n必须回答:')
    for q in STAT_QUESTIONS:
        print(f'   · {q}')
    print(f'\n   {STAT_RULE}')
    return 0


def cmd_profile(a):
    _hdr('玩家画像（**事实表**）')
    for k, ex in PROFILE_FOUR:
        print(f'   {k:<20} {ex}')
    print('\n规则:')
    for r in PROFILE_RULE:
        print(f'   {r}')
    return 0


def cmd_replay(a):
    _hdr('🔑 回放（**四层**）')
    for k, why in REPLAY_FOUR:
        print(f'   {k:<22} {why}')
    print('\n击杀回放字段: ' + ' · '.join(REPLAY_KILL))
    print('\n规则:')
    for r in REPLAY_RULE:
        print(f'   {r}')
    return 0


def cmd_share(a):
    _hdr('分享与导出（**导出时世界**）')
    print('截图: ' + ' · '.join(SHARE_FIELDS))
    print('\n录像: ' + ' · '.join(SHARE_VIDEO))
    print('\n规则:')
    for r in SHARE_RULE:
        print(f'   {r}')
    return 0


def cmd_speed(a):
    _hdr('🔴 speedrun（**竞速契约**）')
    print(f'   {"概念":<14}{"必须记录":<44}重制常见丢失')
    print('   ' + '-' * 74)
    for k, must, lost in SPEED_ROWS:
        print(f'   {k:<14}{must:<44}{lost}')
    print('\nsource_of_truth: ' + ' · '.join(SPEED_SOT))
    print('\n规则:')
    for r in SPEED_RULE:
        print(f'   {r}')
    print(f'\n   {SPEED_PB}')
    return 0


def cmd_tutorial(a):
    _hdr('教学（**强制边界**）')
    print('字段: ' + ' · '.join(TUTORIAL_FIELDS))
    print('\n触发条件: ' + ' · '.join(TUTORIAL_TRIGGERS))
    print('\n规则:')
    for r in TUTORIAL_RULE:
        print(f'   {r}')
    return 0


def cmd_a11y(a):
    _hdr('🔑 无障碍（**替代方案三语义**）')
    for k, why in A11Y_CHANNELS:
        print(f'   {k:<18} {why}')
    print('\n替代语义:')
    for k, why in A11Y_SEMANTIC:
        print(f'   {k:<16} {why}')
    print('\n规则:')
    for r in A11Y_RULE:
        print(f'   {r}')
    print(f'\n   {A11Y_EXAMPLE}')
    print('\n补充:')
    for m in A11Y_MORE:
        print(f'   · {m}')
    return 0


def cmd_mod(a):
    _hdr('模组（**加载顺序与冲突四层**）')
    print('字段: ' + ' · '.join(MOD_FIELDS))
    print('\n加载顺序:')
    for o in MOD_ORDER:
        print(f'   · {o}')
    print('\n冲突四层:')
    for k, why in MOD_CONFLICT:
        print(f'   {k:<32} {why}')
    print('\n冲突字段: ' + ' · '.join(MOD_CONFLICT_FIELDS))
    print('\n恢复策略: ' + ' · '.join(MOD_RECOVERY))
    print('\n规则:')
    for r in MOD_RULE:
        print(f'   {r}')
    return 0


def cmd_lineage(a):
    _hdr('H1 输入意图谱系')
    print('链: ' + ' → '.join(LINEAGE_CHAIN))
    print('\n字段: ' + ' · '.join(LINEAGE_FIELDS))
    print(f'\n   {LINEAGE_RULE}')
    return 0


def cmd_lock(a):
    _hdr('H2 版本锁定物料清单')
    print('字段: ' + ' · '.join(LOCK_FIELDS))
    print('\n🔑 每次复刻验收携带 **manifest hash**；'
          '任何漂移必须说明是**有意升级还是环境误差**')
    return 0


def cmd_init(a):
    os.makedirs(os.path.dirname(a.init) or '.', exist_ok=True)
    with open(a.init, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow([k for k, _ in FIELDS])
        w.writerow(['TODO'] * len(FIELDS))
    print(f'已生成统计/竞速表: {a.init}')
    print('\n⚠️ 十域：stat / profile / replay / share / speed / tutorial / '
          'a11y / mod / lineage / lock')
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
    print(f'统计/竞速 · {len(rows)} 条')
    print('=' * 76)
    if mismatch:
        print(f'\n🚫 **不一致** {len(mismatch)} 条（行 {mismatch[:15]}）')
    if no_legacy:
        print(f'\n❌ {len(no_legacy)} 条缺**原版值**（行 {no_legacy[:15]}）')
    if no_grade:
        print(f'\n🚫 {len(no_grade)} 条**证据等级缺失或 ≥7 级**'
              f'（行 {no_grade[:15]}）')

    if not (mismatch or no_legacy or no_grade):
        print('\n✅ 统计/竞速：一致、原版值完整、证据等级达标')

    print('\n🔑 **统计/回放/竞速是功能契约，不是边缘菜单。**')
    print('   **speedrun 必须分记 RTA/IGT；PB 要保留历史上下文。**')
    print('   **无障碍要有替代方案（且区分 equivalent/assisted/different）。**')
    return 1 if (a.gate_check and (mismatch or no_legacy or no_grade)) else 0


def main():
    ap = argparse.ArgumentParser(description='统计竞速与教学模组')
    ap.add_argument('--stat', action='store_true')
    ap.add_argument('--profile', action='store_true')
    ap.add_argument('--replay', action='store_true')
    ap.add_argument('--share', action='store_true')
    ap.add_argument('--speed', action='store_true')
    ap.add_argument('--tutorial', action='store_true')
    ap.add_argument('--a11y', action='store_true')
    ap.add_argument('--mod', action='store_true')
    ap.add_argument('--lineage', action='store_true')
    ap.add_argument('--lock', action='store_true')
    ap.add_argument('--init')
    ap.add_argument('--check')
    ap.add_argument('--gate-check', action='store_true')
    a = ap.parse_args()
    fns = {'stat': cmd_stat, 'profile': cmd_profile, 'replay': cmd_replay,
           'share': cmd_share, 'speed': cmd_speed, 'tutorial': cmd_tutorial,
           'a11y': cmd_a11y, 'mod': cmd_mod, 'lineage': cmd_lineage,
           'lock': cmd_lock}
    for k, fn in fns.items():
        if getattr(a, k):
            return fn(a)
    if a.init:
        return cmd_init(a)
    if a.check:
        return cmd_check(a)
    print('❌ 需要 --stat / --profile / --replay / --share / --speed / '
          '--tutorial / --a11y / --mod / --lineage / --lock / --init / '
          '--check 之一')
    return 2


if __name__ == '__main__':
    sys.exit(main())
