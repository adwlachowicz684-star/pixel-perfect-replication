#!/usr/bin/env python3
"""失败重试循环 + 刷新遭遇节奏（第二十九轮 A / B 类）。

**🔑 A 类核心**：
> 🔑 **失败/重试循环是独立状态机，不是死亡流程的尾巴。**
> 🔑 **死亡至少要切成十个可测相位，任一相位被合并都会漏掉体验偏差。**
> 🔑 **`control_restored` 不能等同 `input_device_reconnected`** ——
> 前者是玩家第一次可执行有意义操作，后者只是设备重新接管。
> 🔑 **"再来一次"不是单按钮，而是六字段的交互契约。**

**🔑 B 类核心**：
> 🔑 **刷新规则改变的是压力曲线，而不只是怪物数量。**
> 🔑 **单一"刷怪间隔"不足以复现节奏。**

用法:
  game_retry_spawn.py --phases  # 🔴 失败**十相位**
  game_retry_spawn.py --start   # 重试**起手状态差异表**
  game_retry_spawn.py --again   # 🔑 **"再来一次"六字段**
  game_retry_spawn.py --boss    # Boss 重试**单独建模**
  game_retry_spawn.py --streak  # 连续失败的**加速**维度
  game_retry_spawn.py --spawn   # 🔴 生成点**最小字段集**
  game_retry_spawn.py --dist    # 玩家距离**五种子**
  game_retry_spawn.py --vis     # 刷新点**可见性与公平性**
  game_retry_spawn.py --res     # 资源再生**三套触发**
  game_retry_spawn.py --enc     # 随机遭遇**五项**
  game_retry_spawn.py --h       # H 类**八个新盲区**
  game_retry_spawn.py --init ledger/retry_spawn.csv
  game_retry_spawn.py --check ledger/retry_spawn.csv --gate

退出码: 0 通过 / 1 缺项 / 2 用法错误
"""
import argparse
import csv
import os
import sys

# 🔴 失败十相位
PHASES_TEN = [
    ('damage_finalization', '伤害结算完成'),
    ('death_animation', '死亡动画'),
    ('physics_settling', '物理沉降（布娃娃/碎片停止）'),
    ('input_lock_confirmed', '输入锁确认'),
    ('camera_release', '相机释放'),
    ('fade_out', '淡出/黑屏'),
    ('results_or_load', '结算或加载'),
    ('zone_or_checkpoint_reset', '区域/检查点重置'),
    ('respawn_presentation', '复生演出'),
    ('**control_restored**', '**控制归还（玩家第一次可执行有意义操作）**'),
]

PHASE_RULE = [
    '🔑 最后两个状态尤其关键',
    '🔴 **`control_restored` 不能等同 `input_device_reconnected`** —— '
    '前者是玩家第一次可以执行有意义操作，后者只是设备重新接管',
    '🔑 若复刻版在控制归还后还要延迟若干帧才接受菜单输入，'
    '必须写成 `**post_respawn_input_delay**` —— '
    '否则玩家连按"再来一次"会**把输入吞掉或误触其他菜单**',
    '🔑 实测应以**原版视频为一级证据**，逐帧标注各相位',
    '🔑 若原版有掉帧、着色器编译或流式卡顿，应记"**观测时长**"与'
    '"**设计意图**"，🔴 **不得把偶发卡顿直接标成 must-match**',
    '🔑 失败循环必须新增"**控制归还时间**"，它比"画面出现多久"'
    '**更能解释挫败感**',
]

# 重试起手状态
START_DIFF = [
    '当前生命值', '临时生命值', '资源', '弹药', '耐力', '状态异常',
    '装备耐久', '消耗品', '快捷栏', '技能冷却', '锁定目标', '伙伴状态',
    '摄像机朝向', '世界时间', '天气', '**敌人血量**', '巡逻点',
    '**已触发的对话/演出**', '已打开的门', '已打破的物件', '掉落物',
    '任务阶段', '检查点', '最近读档点',
]

START_FOUR = [
    '**固定补给与传送**', '**检查点快照**', '**仅复活点重置**',
    '**从最近读档恢复**',
]

START_RULE = [
    '🔑 **必须是一张显式差异表，不能用"重置"二字概括**',
    '🔑 原版常见的四档**不是"满血/死亡"**',
    '🔑 尤其要验证**死亡时是否先落检查点再重置** —— '
    '若角色死亡动画期间世界继续，随后检查点冻结，'
    '会产生"**死亡前最后一击影响复活状态**"的隐藏窗口',
]

# 🔑 再来一次六字段
AGAIN_FIELDS = [
    'button_screen_position', '**default_focus**', 'confirm_role',
    'cancel_role', 'focus_wrap', 'controller_first_interact',
    'keyboard_shortcut_available', 'press_versus_confirm_semantics',
    'safe_area', '**minimum_input_lock_ms**',
]

AGAIN_RULE = [
    '🔑 **"再来一次"不是单按钮，而是六字段的交互契约**',
    '🔴 **默认"确定"会奖励连按；默认"取消"会在连败后让玩家'
    '误以为没有重试**',
    '🔑 **若原版没有默认焦点，则任何自动聚焦都是偏离**',
    '🔑 菜单首次出现时若原版要求**方向键移动一次才确认**，'
    '也**不能为了"手柄友好"改成自动聚焦**',
]

# Boss 重试
BOSS_FIELDS = [
    'skip_pre_boss_trash', 'reset_trash_on_entry',
    '**skip_intro_cutscene_when_seen**', 'skip_boss_phase_intro_on_retry',
    'retain_player_loadout', '**retain_boss_state_on_quit**',
    'reinstate_checkpoint_after_first_entry', 'allow_rest_or_shop_after_retry',
]

BOSS_RULE = [
    '🔑 **Boss 重试必须单独建模**，因为普通检查点规则在首领战往往失效',
    '🔴 最常见 bug：为了"提升节奏"**自动跳过玩家尚未观看过的剧情**，'
    '或为了"减少重复"**跳过对话但保留其已经施加的任务状态**',
    '🔑 正确实现应把"**看见过 · 触发过 · 已结算 · 可重播**"'
    '**四态分开**',
]

# 连续失败
STREAK_DIMS = [
    '死亡演出帧数', '黑屏时长', '加载异步度', '**前置演出跳过**',
    '敌人重置范围', '补给量', '复活点距离', '默认按钮', '教程重提示',
    '**Boss 前小怪跳过**', '剧情重播策略', '**隐藏或显式难度衰减**',
]

STREAK_RULE = [
    '🔑 **必须区分"减少挫败"与"改变难度"，两者都不能被默认改写**',
    '🔴 若原版只跳过**玩家已看过**的过场，重制**不能变成"永久跳过"**',
    '🔴 若原版降低敌人但**保留首领血量**，不能改写成全面削弱',
    '🔴 若原版只缩短黑屏，**不能把整个加载流程做成异步预加载后'
    '宣称等价**',
]

# 🔴 生成点
SPAWN_FIELDS = [
    'spawner_id', 'owner_zone', '**candidate_pool**', 'selection_weight',
    'min_interval_ms', 'max_interval_ms', 'initial_delay_ms', 'burst_size',
    'cooldown_after_burst', '**global_cap**', '**zone_cap**', 'faction_cap',
    '**player_distance_policy**', 'line_of_sight_required',
    '**spawn_point_visibility**', 'predictability',
    'biome_or_weather_modifier', 'time_of_day_modifier',
]

SPAWN_RULE = '🔑 若原版随机时**不是逐生成点独立**，'
'还必须记录**全局共享 RNG 是否参与选择**'

# 玩家距离
DIST_FIVE = [
    '中心', '入口', '声音源', '**玩家高度**', '**朝向**',
]

DIST_POLICY = [
    '固定半径', '自适应半径', '仅在玩家跨区后启用',
    '**玩家离开再进入的"休眠—唤醒"**', '房间清版后一次性生成',
    '**可见区域内禁用生成**',
]

DIST_FOUR_TIMES = [
    '声音前摇', '粒子前摇', '可见生成体积', '实际可战斗时间',
]

DIST_RULE = [
    '🔑 **距离不能只写最近点**',
    '🔴 若原版会在玩家接近时**先播生成音、隔若干帧再出现单位**，'
    '重制**不能改成同帧生成**',
    '🔴 若原版在**摄像机转离后停止生成**，重制也**不能为了"敌人更多"'
    '保持持续生成**',
]

# 刷新可见性
VIS_ITEMS = [
    '有声', '有光', '有粒子', '有空间扭曲', '有 UI 标记',
    '有脚印/震动', '**预警时长**',
    '**预警是否会被静音 · 画质档 · 摄像机遮挡取消**',
]

VIS_FAIL = [
    '候选池空', '容量满', '玩家太近', '区域未激活', '路径不可达',
    '时间/天气不匹配',
]

VIS_RULE = [
    '🔑 **刷新点的可见性既是反馈也是公平性**，'
    '必须与生成事件**一一绑定**',
    '🔑 **生成失败也必须有可观测结果**；若原版"看起来什么都没发生"，'
    '要区分**真的没有生成**与**生成失败**，'
    '🔴 **不能只测最终单位数**',
]

# 资源再生
RES_TRIGGERS = [
    '世界时间', '玩家离开时长', '区域卸载时长', '昼夜', '天气', '季节',
    'NPC 供给', '剧情阶段', '手动补货',
]

RES_FIELDS = [
    'elapsed_source', '**elapsed_when_paused**', 'reset_on_zone_revisit',
    'reset_on_save_reload', 'reset_on_new_game_plus', 'respawn_jitter',
    '**depletion_floor**',
]

RES_RULE = '🔑 **资源再生要记录世界时钟 · 玩家行为 · 重置边界三套触发**；'
'🔴 若离开地图一小时后恢复但读档不恢复，重制**必须保留这种'
'"时间来源不一致"** —— **统一成一种时钟会消除原版刻意留下的差异**'

# 随机遭遇
ENC_FIVE = ['间隔', '条件', '候选池', '上限', '**防连续保护**']

ENC_PROTECT = [
    '窗口长度', '保护对象（同事件/同阵营/同奖励）', '触发抑制', '补偿生成',
]

ENC_RULE = [
    '🔑 **随机遭遇必须同时有"间隔 · 条件 · 候选池 · 上限 · '
    '防连续保护"**',
    '🔑 **没有保护本身也是一种设计选择** —— '
    '🔴 **不能因为重制希望"节奏更均匀"就自行加入冷却**',
    '🔑 若原版连续遭遇会导致**镜头抖动 · 音频堆叠 · 输入锁冲突**，'
    '应记具体症状及解决优先级，而不是泛称"优化"',
]

# H 类八盲区
H_EIGHT = [
    ('**死亡/失败无限循环保护**', '新增 `failure_recovery_progress`；'
     '重新进入死亡演出/黑屏超阈值/区域重置重复触发 → 落 '
     '`safe_recovery_state`；原版没有则记 `no_built_in_protection`'),
    ('**恢复阶段超时与取消**', '每步记 `timeout_ms · timeout_action · '
     'user_cancelable · retry_count · backoff · failure_message · '
     'support_bundle`'),
    ('**复位的双时钟**', '分别记 `wall_clock_elapsed · game_clock_elapsed · '
     'zone_clock_elapsed · loading_pause_elapsed · menu_pause_elapsed · '
     'death_pause_elapsed`'),
    ('**失败菜单默认焦点**', '手柄重连后焦点是否保留 · 输入方式切换后'
     '是否重置 · 死亡动画中是否允许方向键 · 是否接受上次帧残留按键 · '
     '双人对战 P1/P2 归属 · 暂停与失败菜单叠加时焦点归谁'),
    ('**物件元数据版本与游戏版本分开**', '每个对象存 `format_schema · '
     'content_version · migration_applied · derived_state_invalidated`'),
    ('**失败动画取消的阶段书签**', '可取消起始帧 · 可跳过起始帧 · '
     '跳过后必须播放的最小尾部 · 被取消事件是否补发 · '
     '输入是否在尾部完成前锁定；`skip_policy: first_time|seen|always`'),
    ('**敌人/Boss 重置三种触发**', '进入触发 / 失败触发 / 超时触发 → '
     '`reset_cause × reset_scope` 矩阵'),
    ('**物件状态最小保存单位**', '实例 / 房间 / 区域 / 世界 / 账号 / 平台；'
     '对象跨边界移动后的行为必须实测'),
]

CONFLICTS = [
    '❌ 把控制归还等同于输入设备重连',
    '❌ **把偶发卡顿直接标成 must-match**',
    '❌ 用"重置"二字概括重试起手状态',
    '❌ **默认"确定"**（奖励连按）或默认"取消"（连败后误以为无重试）',
    '❌ 原版无默认焦点却自动聚焦',
    '❌ **自动跳过玩家尚未观看过的剧情**',
    '❌ 跳过对话但保留其已施加的任务状态',
    '❌ 为"减少挫败"改写难度（或反之）',
    '❌ **把整个加载做成异步预加载后宣称等价**',
    '❌ 只写"刷怪间隔"',
    '❌ 玩家距离只写最近点',
    '❌ 生成音与实际出现同帧（原版有前摇）',
    '❌ 摄像机转离后仍持续生成',
    '❌ **只测最终单位数**（不区分未生成与生成失败）',
    '❌ **把资源再生的多个时间源统一成一种**',
    '❌ **自行加入防连续遭遇冷却**',
    '❌ 预设一种"更现代"的保存粒度而不实测',
]

FIELDS = [
    ('item_id', '项编号'),
    ('domain', '域（phases / start / again / boss / streak / spawn / dist / '
               'vis / res / enc / h）'),
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


def cmd_phases(a):
    _hdr('🔴 失败（**十相位**）')
    for k, why in PHASES_TEN:
        print(f'   {k:<30} {why}')
    print('\n规则:')
    for r in PHASE_RULE:
        print(f'   {r}')
    return 0


def cmd_start(a):
    _hdr('重试（**起手状态差异表**）')
    print('逐项记录: ' + ' · '.join(START_DIFF))
    print('\n四档（**不是"满血/死亡"**）: ' + ' · '.join(START_FOUR))
    print('\n规则:')
    for r in START_RULE:
        print(f'   {r}')
    return 0


def cmd_again(a):
    _hdr('🔑 "再来一次"（**六字段交互契约**）')
    print('字段: ' + ' · '.join(AGAIN_FIELDS))
    print('\n规则:')
    for r in AGAIN_RULE:
        print(f'   {r}')
    return 0


def cmd_boss(a):
    _hdr('Boss 重试（**单独建模**）')
    print('字段: ' + ' · '.join(BOSS_FIELDS))
    print('\n规则:')
    for r in BOSS_RULE:
        print(f'   {r}')
    return 0


def cmd_streak(a):
    _hdr('连续失败（**加速维度**）')
    print('可变化维度: ' + ' · '.join(STREAK_DIMS))
    print('\n规则:')
    for r in STREAK_RULE:
        print(f'   {r}')
    return 0


def cmd_spawn(a):
    _hdr('🔴 生成点（**最小字段集**）')
    print('字段: ' + ' · '.join(SPAWN_FIELDS))
    print(f'\n   {SPAWN_RULE}')
    return 0


def cmd_dist(a):
    _hdr('玩家距离（**五种子 + 六策略**）')
    print('五种距离: ' + ' · '.join(DIST_FIVE))
    print('\n策略: ' + ' · '.join(DIST_POLICY))
    print('\n四个时刻: ' + ' · '.join(DIST_FOUR_TIMES))
    print('\n规则:')
    for r in DIST_RULE:
        print(f'   {r}')
    return 0


def cmd_vis(a):
    _hdr('刷新可见性（**反馈与公平性**）')
    print('预警形式: ' + ' · '.join(VIS_ITEMS))
    print('\n生成失败种类: ' + ' · '.join(VIS_FAIL))
    print('\n规则:')
    for r in VIS_RULE:
        print(f'   {r}')
    return 0


def cmd_res(a):
    _hdr('资源再生（**三套触发**）')
    print('触发源: ' + ' · '.join(RES_TRIGGERS))
    print('\n字段: ' + ' · '.join(RES_FIELDS))
    print(f'\n   {RES_RULE}')
    return 0


def cmd_enc(a):
    _hdr('随机遭遇（**五项**）')
    print('必备: ' + ' · '.join(ENC_FIVE))
    print('\n防连续保护字段: ' + ' · '.join(ENC_PROTECT))
    print('\n规则:')
    for r in ENC_RULE:
        print(f'   {r}')
    return 0


def cmd_h(a):
    _hdr('H 类（**八个新盲区**）')
    for k, why in H_EIGHT:
        print(f'\n   【{k}】\n      {why}')
    return 0


def cmd_init(a):
    os.makedirs(os.path.dirname(a.init) or '.', exist_ok=True)
    with open(a.init, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow([k for k, _ in FIELDS])
        w.writerow(['TODO'] * len(FIELDS))
    print(f'已生成重试/刷新表: {a.init}')
    print('\n⚠️ 十一域：phases / start / again / boss / streak / spawn / '
          'dist / vis / res / enc / h')
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
    print(f'重试/刷新 · {len(rows)} 条')
    print('=' * 76)
    if mismatch:
        print(f'\n🚫 **不一致** {len(mismatch)} 条（行 {mismatch[:15]}）')
    if no_legacy:
        print(f'\n❌ {len(no_legacy)} 条缺**原版值**（行 {no_legacy[:15]}）')
    if no_grade:
        print(f'\n🚫 {len(no_grade)} 条**证据等级缺失或 ≥7 级**'
              f'（行 {no_grade[:15]}）')

    if not (mismatch or no_legacy or no_grade):
        print('\n✅ 重试/刷新：一致、原版值完整、证据等级达标')

    print('\n🔑 **死一次要等多久，直接决定玩家是否继续玩。**')
    print('   **控制归还 ≠ 输入设备重连；要有 post_respawn_input_delay。**')
    print('   **刷新规则改变的是压力曲线，不只是怪物数量。**')
    return 1 if (a.gate_check and (mismatch or no_legacy or no_grade)) else 0


def main():
    ap = argparse.ArgumentParser(description='失败重试与刷新节奏')
    ap.add_argument('--phases', action='store_true')
    ap.add_argument('--start', action='store_true')
    ap.add_argument('--again', action='store_true')
    ap.add_argument('--boss', action='store_true')
    ap.add_argument('--streak', action='store_true')
    ap.add_argument('--spawn', action='store_true')
    ap.add_argument('--dist', action='store_true')
    ap.add_argument('--vis', action='store_true')
    ap.add_argument('--res', action='store_true')
    ap.add_argument('--enc', action='store_true')
    ap.add_argument('--h', action='store_true')
    ap.add_argument('--init')
    ap.add_argument('--check')
    ap.add_argument('--gate-check', action='store_true')
    a = ap.parse_args()
    fns = {'phases': cmd_phases, 'start': cmd_start, 'again': cmd_again,
           'boss': cmd_boss, 'streak': cmd_streak, 'spawn': cmd_spawn,
           'dist': cmd_dist, 'vis': cmd_vis, 'res': cmd_res, 'enc': cmd_enc,
           'h': cmd_h}
    for k, fn in fns.items():
        if getattr(a, k):
            return fn(a)
    if a.init:
        return cmd_init(a)
    if a.check:
        return cmd_check(a)
    print('❌ 需要 --phases / --start / --again / --boss / --streak / '
          '--spawn / --dist / --vis / --res / --enc / --h / --init / '
          '--check 之一')
    return 2


if __name__ == '__main__':
    sys.exit(main())
