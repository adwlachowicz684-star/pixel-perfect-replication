#!/usr/bin/env python3
"""输入硬件物理层 + AI 听觉 + 云存档 + 渲染 Pass + UI 模态栈（第二十二轮 C/D/E/F/G）。

**🔑 C 类核心**：
> 🔴 **输入证据必须从"键按下"下钻到设备事件。**
> 🔑 鼠标轮询率不能只写"已设 1000Hz" —— 必须测**真实报告间隔序列**。

**🔑 D 类核心**：
> 🔴 **AI 听觉不能先假设原版"应该有"** —— 应先以原版音频事件为声源，
> 用固定探针测传播、衰减、遮挡、最大听距和黑板记忆。
> 🔴 **原版没有，就不应以"更真实"为由补入。**

用法:
  game_input_percept.py --hw     # 🔴 输入**硬件事件表**
  game_input_percept.py --mouse  # 🔴 轮询率**拍频**/LOD/直线修正
  game_input_percept.py --kb     # 🔴 NKRO/ghosting 是**关卡门**
  game_input_percept.py --hearing # 🔴 AI 听觉**先证存在**
  game_input_percept.py --noise  # 噪音**是否可被引诱**
  game_input_percept.py --cloud  # 🔴 云存档**13 字段 + 四档冲突**
  game_input_percept.py --lease  # **会话租约**
  game_input_percept.py --pass   # 渲染 **Pass 顺序与透明排序**
  game_input_percept.py --focus  # **UI 模态栈与焦点**
  game_input_percept.py --init ledger/input_percept.csv
  game_input_percept.py --check ledger/input_percept.csv --gate

退出码: 0 通过 / 1 缺项 / 2 用法错误
"""
import argparse
import csv
import os
import sys

# 🔴 输入硬件
HW_FIELDS = [
    'device_id', 'device_type', 'vendor_id', 'product_id',
    '**firmware_version**', 'driver_name', 'connection_type',
    '**polling_rate_hz**', 'report_timestamp', '**scancode**',
    'logical_key', 'raw_axis', 'dead_zone', 'calibration',
    'input_latency_ms',
]

HW_TABLE = [
    ('鼠标轮询率拍频', '小圆轨迹呈环形差、瞄准节奏跳变',
     '`polling_rate_hz` · phase_test'),
    ('抬离距离 LOD', '抬鼠后仍移动或丢追踪', '`lod_mm` · surface'),
    ('**直线修正/角度吸附**', '甩枪被拉直，微操被"纠正"',
     '`angle_snap_enabled` · snap_threshold_deg'),
    ('**键盘扫描矩阵**', '三键以上某些组合丢失', 'ghost 键矩阵'),
    ('按键去抖', '双击、连发或首次触发延迟',
     '`debounce_ms` · first_press_to_accepted_ms'),
    ('typematic', '长按加速、菜单重复间隔变化',
     '`delay_ms` · repeat_interval_ms · os_override'),
    ('摇杆回中偏差', '角色自行漂移、微调不归零',
     '`center_offset` · inner/outer_deadzone · wear_profile'),
    ('设备热插拔', '输入方案丢失、按钮含义变化',
     '`device_change_strategy` · input_ownership'),
    ('驱动/中间件重映射', 'XInput、DS4Windows、Steam Input 改变事件',
     '`mapping_layer` · report_source'),
    ('**手柄+键鼠混合**', '鼠标移动覆盖手柄视角，反之亦然',
     '`last_input_device` · exclusive_mode'),
]

HW_RULE = [
    '🔴 **输入证据必须从"键按下"下钻到设备事件**',
    '🔑 物理扫描码与布局映射后的逻辑键码**必须分离**',
    '🔑 要记录**设备事件时间戳**，不能用同一帧的逻辑时间打戳',
    '🔑 跨平台库可提供**物理键/逻辑键、多设备增删和原始轴采集底座**，'
    '但**不能代替原硬件测试**',
]

# 🔴 鼠标
MOUSE_RATE = '🔴 **鼠标轮询率不能只写"已设 1000Hz"** —— '
'必须测**真实报告间隔序列**，统计最小/最大/P50/P95/P99/丢报/重复报/时钟回退'

MOUSE_SCAN = '🔑 再在 **30/60/72/120/144/165/240 Hz** 逻辑更新下跑'
'**圆周、步进、停顿、回拉**测试'

MOUSE_CONCL = '🔑 结论应写"**哪些手势在某个组合下发生可见周期误差**"，'
'**而不是"高 Hz 更好"**'

# 🔴 键盘
KB_RULE = [
    '🔴 **键盘 NKRO/ghosting 是关卡门，不只是外设参数** —— '
    '复刻版若新增组合键、按住移动同时连续施放，'
    '就可能撞上**原键盘无法产生的键组合**',
    '🔑 扫描矩阵测试要记录**按键集合、实际接受集合、'
    '滚动/二极管拓扑（未知时保留）**',
    '🔑 把每个**必用组合**写入输入契约',
]

KB_DEBOUNCE = [
    '机械/霍尔/光学开关的**抖动窗口不同**',
    '"**按下后 5 ms 才接受**"可能消除双击，却让**快速 tap 消失**',
    'typematic 还决定**菜单滚动、聊天光标和长按技能**',
    '必须记录**首次延迟、重复间隔、是否吞掉首次 press、'
    '是否受系统加速影响**',
]

# 🔴 AI 听觉
HEARING_RULE = [
    '🔴 **AI 听觉不能先假设原版"应该有"**',
    '🔑 应先以**原版音频事件为声源**，用固定探针测'
    '**传播、衰减、遮挡、最大听距和黑板记忆**',
    '🔴 **原版没有，就不应以"更真实"为由补入**',
]

HEARING_MEM = [
    '首次/最近听到时间', '位置', '声源语义', '**可信度**',
    '**是否已调查**', '调查成功/失败', '**记忆过期**', '覆盖规则',
    '**是否跨状态保存**', '**是否受警觉等级影响**',
]

HEARING_ALERT = '🔑 新增 `alert_source=sound|sight|told` —— '
'**避免把看到和听到混成一个"发现"事件**'

HEARING_TIME = '🔑 要记录**事件发生、传播到达、感知处理、黑板写入**四段时间'

# 噪音诱饵
NOISE_SOURCES = [
    '投掷瓶', '呼叫器', '枪声', '门', '脚步', '**换弹**', '尸体掉落',
    '**角色重量**',
]

NOISE_RULE = [
    '🔑 **诱饵属于输入装置，不是普通物件** —— 每一项要分别测量：'
    '**是否发声 · 音量 · 延迟 · 可听范围 · 能否引起调查 · 调查位置 · '
    '是否可中断当前目标 · 是否暴露玩家位置**',
    '🔑 若原版允许玩家利用声音 → "静步鞋""地毯""消音器"'
    '**必须改变 AI 可听性**',
    '🔴 若原版没有该语义 → **重制"贴心加入"就是偏离**',
]

HEARING_EVIDENCE = [
    '🔑 **屏幕录像只能证明表现**',
    '🔑 **音频总线抓取只能证明播放**',
    '🔑 **AI 黑板抓取才能证明"听到"**',
    '🔑 **反向注入声源最接近因果证据**',
]

HEARING_INCONSIST = [
    '"同音效有时触发 AI、有时不" → 可能是**距离差、遮挡、状态门、随机性、'
    '计时窗口**',
    '"AI 对换弹声反应更快" → 可能是**固定延迟与声音时长重叠**',
    '🔑 **只有连续探针失败才标 `no_ai_hearing`**',
]

HEARING_CONFLICT = '🔴 **"现代 AI 应更聪明"式增强是偏离** —— '
'自适应声学、机器学习声音识别或真实物理声学**都可能改变可听半径、'
'反应位置和诱饵价值**'

# 🔴 云存档
CLOUD_FIELDS = [
    'save_id', 'schema_version', 'game_version', 'session_id',
    '**logical_clock**', 'wall_clock_usec（**仅审计**）',
    '**device_fingerprint**', 'file_manifest_hash', 'play_duration_ms',
    'checksum', 'authority', '**conflict_state**', 'pending_upload',
    'last_verified_signature',
]

CLOUD_FOUR = [
    ('**strict_manual**', '由玩家选择'),
    ('**per_field_crdt**', '对独立字段最后写入胜出'),
    ('**schema_aware_merge**', '对任务、背包、设置做语义合并'),
    ('**last_wins_with_backup**', '只在已证明无语义冲突时使用'),
]

CLOUD_RULE = [
    '🔑 **云存档契约的最小单元不是文件，而是可独立合并的事实**',
    '🔴 **时间戳只能用于审计，不能单独决定胜负**',
    '🔑 **应支持四档冲突策略，而不是统一"最新优先"**',
    '🔑 **玩家最后选择本身必须写回审计表，不能悄悄覆盖**',
]

# 租约
LEASE_RULE = [
    '🔑 **多设备同时游玩必须进入"会话租约"** —— '
    '启动游戏读取云端清单；**有租约则续租，无租约则请求**',
    '🔑 冲突或过期后**只进入只读或副本模式**，'
    '**不能让两个设备以 wall_clock 争写**',
]

LEASE_CASES = [
    '启动前云不可用', '运行中网络断开', '**上传到 99% 失败**',
    '**旧客户端写新格式**', '新客户端读旧格式', '云文件损坏',
    '本地文件损坏', '平台账号切换', '同一 PC 多用户', '**模拟时钟回拨**',
]

# 渲染 Pass
PASS_FIELDS = [
    '**pass_order**', '**transparent_sort_key**', '**depth_write**',
    '**depth_test**', '**msaa_resolve_phase**', '**taa_resolve_phase**',
    '**ui_in_tonemap**', 'multi_camera_order',
]

PASS_RULE = [
    '🔑 **渲染 Pass 的执行顺序**（谁在谁之后）必须逐帧取证',
    '🔑 **透明物体排序规则**：按距离？按 render queue？',
    '🔑 **深度写入 vs 深度测试**的开关要分别记录',
    '🔑 **MSAA/TAA resolve 时机**与后处理链的关系',
    '🔑 **后处理是否影响 UI**：UI 在 tonemapping 前还是后 —— '
    '**若把敌人标识送入 tonemapper，HDR 下可能过曝消失**',
]

# UI 焦点
FOCUS_FIELDS = [
    '**modal_stack**', '**focus_restore_target**', '**mouse_passthrough**',
    '**hybrid_input_owner**', 'virtual_cursor_mode',
]

FOCUS_RULE = [
    '🔑 **模态栈**：多层嵌套 UI 的输入路由',
    '🔑 **焦点恢复**：关闭子菜单后焦点回到哪',
    '🔑 **鼠标穿透**：UI 未覆盖区域是否穿透到世界',
    '🔑 **手柄 + 鼠标混合输入**（同时使用时谁优先）',
    '🔑 **虚拟光标**（手柄操作鼠标 UI）',
    '🔴 **即时模式 UI 控件不得成为玩家 UI 的焦点契约**',
]

CONFLICTS = [
    '❌ 只写"已设 1000Hz"而不测真实报告间隔',
    '❌ 结论写"高 Hz 更好"而非"哪些手势有周期误差"',
    '❌ 新增组合键却未验证原键盘能产生',
    '❌ 忽略 typematic 对菜单/长按技能的影响',
    '❌ **假设原版"应该有"AI 听觉**',
    '❌ **以"更真实"为由补入 AI 听觉**',
    '❌ 把看到和听到混成一个"发现"事件',
    '❌ 自适应声学/ML 声音识别当复刻收益',
    '❌ **用 wall_clock 决定云存档胜负**',
    '❌ 统一"最新优先"',
    '❌ 两个设备以 wall_clock 争写',
    '❌ 玩家选择不写回审计表',
    '❌ 后处理影响 UI 却不记录',
    '❌ 即时模式控件当焦点契约',
]

FIELDS = [
    ('item_id', '项编号'),
    ('domain', '域（hw / mouse / kb / hearing / noise / cloud / lease / '
               'pass / focus）'),
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


def cmd_hw(a):
    _hdr('🔴 输入硬件事件表')
    print('字段: ' + ' · '.join(HW_FIELDS))
    print('\n现象→感受→字段:')
    for k, feel, f in HW_TABLE:
        print(f'   {k:<20} {feel}')
        print(f'   {"":<20} → {f}')
    print('\n规则:')
    for r in HW_RULE:
        print(f'   {r}')
    return 0


def cmd_mouse(a):
    _hdr('🔴 鼠标（轮询率 / LOD / 直线修正）')
    print(f'   {MOUSE_RATE}')
    print(f'\n   {MOUSE_SCAN}')
    print(f'\n   {MOUSE_CONCL}')
    return 0


def cmd_kb(a):
    _hdr('🔴 键盘（NKRO / ghosting / 去抖）')
    for r in KB_RULE:
        print(f'   {r}')
    print('\n去抖与 typematic:')
    for r in KB_DEBOUNCE:
        print(f'   · {r}')
    return 0


def cmd_hearing(a):
    _hdr('🔴 AI 听觉（**先证存在**）')
    for r in HEARING_RULE:
        print(f'   {r}')
    print('\n记忆不是持续时间，而是一组黑板状态:')
    for m in HEARING_MEM:
        print(f'   · {m}')
    print(f'\n   {HEARING_ALERT}')
    print(f'   {HEARING_TIME}')
    print('\n证据分级:')
    for e in HEARING_EVIDENCE:
        print(f'   {e}')
    print('\n原版不一致:')
    for e in HEARING_INCONSIST:
        print(f'   {e}')
    print(f'\n   {HEARING_CONFLICT}')
    return 0


def cmd_noise(a):
    _hdr('噪音（**诱饵是输入装置**）')
    print('声源: ' + ' · '.join(NOISE_SOURCES))
    print('\n规则:')
    for r in NOISE_RULE:
        print(f'   {r}')
    return 0


def cmd_cloud(a):
    _hdr('🔴 云存档（**可独立合并的事实**）')
    print('字段: ' + ' · '.join(CLOUD_FIELDS))
    print('\n四档冲突策略:')
    for k, why in CLOUD_FOUR:
        print(f'   {k:<26} {why}')
    print('\n规则:')
    for r in CLOUD_RULE:
        print(f'   {r}')
    return 0


def cmd_lease(a):
    _hdr('会话租约')
    for r in LEASE_RULE:
        print(f'   {r}')
    print('\n必覆盖: ' + ' · '.join(LEASE_CASES))
    return 0


def cmd_pass(a):
    _hdr('渲染 Pass 与透明排序')
    print('字段: ' + ' · '.join(PASS_FIELDS))
    print('\n规则:')
    for r in PASS_RULE:
        print(f'   {r}')
    return 0


def cmd_focus(a):
    _hdr('UI 模态栈与焦点')
    print('字段: ' + ' · '.join(FOCUS_FIELDS))
    print('\n规则:')
    for r in FOCUS_RULE:
        print(f'   {r}')
    return 0


def cmd_init(a):
    os.makedirs(os.path.dirname(a.init) or '.', exist_ok=True)
    with open(a.init, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow([k for k, _ in FIELDS])
        w.writerow(['TODO'] * len(FIELDS))
    print(f'已生成输入/感知表: {a.init}')
    print('\n⚠️ 九域：hw / mouse / kb / hearing / noise / cloud / lease / '
          'pass / focus')
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
    print(f'输入/感知 · {len(rows)} 条')
    print('=' * 76)
    if mismatch:
        print(f'\n🚫 **不一致** {len(mismatch)} 条（行 {mismatch[:15]}）')
    if no_legacy:
        print(f'\n❌ {len(no_legacy)} 条缺**原版值**（行 {no_legacy[:15]}）')
    if no_grade:
        print(f'\n🚫 {len(no_grade)} 条**证据等级缺失或 ≥7 级**'
              f'（行 {no_grade[:15]}）')

    if not (mismatch or no_legacy or no_grade):
        print('\n✅ 输入/感知：一致、原版值完整、证据等级达标')

    print('\n🔑 **输入要从"键按下"下钻到设备事件。**')
    print('   **AI 听觉先证存在；原版没有就不许以"更真实"为由补入。**')
    print('   **时间戳只能审计，不能决定云存档胜负。**')
    return 1 if (a.gate_check and (mismatch or no_legacy or no_grade)) else 0


def main():
    ap = argparse.ArgumentParser(description='输入硬件与感知')
    ap.add_argument('--hw', action='store_true')
    ap.add_argument('--mouse', action='store_true')
    ap.add_argument('--kb', action='store_true')
    ap.add_argument('--hearing', action='store_true')
    ap.add_argument('--noise', action='store_true')
    ap.add_argument('--cloud', action='store_true')
    ap.add_argument('--lease', action='store_true')
    ap.add_argument('--pass', dest='pass_', action='store_true')
    ap.add_argument('--focus', action='store_true')
    ap.add_argument('--init')
    ap.add_argument('--check')
    ap.add_argument('--gate-check', action='store_true')
    a = ap.parse_args()
    fns = {'hw': cmd_hw, 'mouse': cmd_mouse, 'kb': cmd_kb,
           'hearing': cmd_hearing, 'noise': cmd_noise, 'cloud': cmd_cloud,
           'lease': cmd_lease, 'pass_': cmd_pass, 'focus': cmd_focus}
    for k, fn in fns.items():
        if getattr(a, k):
            return fn(a)
    if a.init:
        return cmd_init(a)
    if a.check:
        return cmd_check(a)
    print('❌ 需要 --hw / --mouse / --kb / --hearing / --noise / --cloud / '
          '--lease / --pass / --focus / --init / --check 之一')
    return 2


if __name__ == '__main__':
    sys.exit(main())
