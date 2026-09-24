#!/usr/bin/env python3
"""世界一致性快照 / 氛围层 / 同帧事件序 / 意图边界（第三十轮 A/B/C/D/E 类）。

**🔑 本轮与以往最大的不同 —— 先说清楚**：
> 本轮**没有**把四个候选盲区直接升级为 must-match 规则。
> 原因不是它们不重要，而是**公开资料尚未提供足以支撑像素级复刻标准的证据**。
>
> 🔑 引擎文档只能证明**快照 · 事件队列 · 生命周期存在**，
> **不能证明原版具体行为**。
> 🔑 真正应吸收的是"**状态连续性治理方法**"，
> 🔴 **而不是从引擎默认值反推原版表现**。

**本轮交付的是"可验证缺口"，不是虚构的新体验清单。**

**四组最该拒绝的冒充**：
> 🔴 把"**序列化自动保存的字段**"当成"**世界快照完整性**"
> 🔴 把"**播放器当前正在发声**"当成"**声音对象已被持久化**"
> 🔴 把"**事件在同一帧触发**"当成"**事件按同一顺序消费**"
> 🔴 把"**按键仍在 pressed**"当成"**玩家意图仍然有效**"

用法:
  game_continuity.py --snap    # 🔴 存档**六类状态分类器**
  game_continuity.py --freeze  # 快照**冻结点字段**
  game_continuity.py --load    # 读档**六步**
  game_continuity.py --proj    # 🔑 飞行投射物**不能自动判 bug**
  game_continuity.py --amb     # 氛围层**取证模板**
  game_continuity.py --ambm    # 氛围层**测量方法**
  game_continuity.py --clock   # 🔑 **"同一帧"有四种解释**
  game_continuity.py --order   # 事件**稳定排序键**四阶段
  game_continuity.py --kill    # 🔑 **"最后一下"数值 vs 演出**
  game_continuity.py --intent  # 🔑 意图**边界矩阵**
  game_continuity.py --combo   # 连招缓冲**状态机**
  game_continuity.py --hud     # HUD**双时钟**
  game_continuity.py --init ledger/continuity.csv
  game_continuity.py --check ledger/continuity.csv --gate
  game_continuity.py --check ledger/continuity.csv --allow-unknown

退出码: 0 通过 / 1 缺项 / 2 用法错误
"""
import argparse
import csv
import os
import sys

# 🔴 六类状态分类器
SNAP_SIX = [
    ('**最终事实**', '是', '原子提交并校验版本',
     '进度丢失 · 重复奖励', '金钱 · 关键道具 · 剧情书签'),
    ('**持续事实**', '是', '冻结权威 tick 与确定相位',
     '位置漂移 · 装备错配', '位置 · 朝向 · 生命值 · 装备'),
    ('**持续过程**', '**条件性**', '**保存过程参数或显式终止**',
     '**子弹消失 · 音乐断句 · 动画跳变**',
     '飞行投射物相位 · 动画剩余 · 衰减包络 · 相机过渡 · AI 黑板 · '
     '导航查询 · 定时器 · 协程'),
    ('**瞬态输出**', '**原则上否**', '只有原版证明时才保留句柄与位置',
     '静默无声 · 粒子清零',
     '当前渲染帧 · 粒子存活集 · 已排队音源 · 控制器震动包络'),
    ('**派生缓存**', '否', '按主循环相位重建',
     '不应单独导致玩法偏差', '可见集合 · 空间哈希 · 遮挡结果'),
    ('**平台外部状态**', '**单独治理**', '只读审计 · 禁止双向覆盖',
     '**云端覆盖本地进度**', '设备连接 · 用户账号 · 云端时间戳'),
]

SNAP_RULE = [
    '🔑 前两类必须**冻结为事实**',
    '🔑 第三类**要么被冻结、要么必须显式终止**',
    '🔑 第四类**只能在原版被证明需要恢复时重建**',
    '🔑 第五类**不应进档**',
    '🔑 第六类**必须审计而不能照原覆盖**',
    '🔑 官方教程已明确要求"**把游戏状态回退，以免在加载时克隆对象**" —— '
    '🔴 **"读取成功即世界合法"应列为冲突做法**',
]

# 冻结点
FREEZE_FIELDS = [
    '**snapshot_authoritative_clock_domain**', '**authoritative_tick**',
    'physics_substep_index', 'animation_frame_phase',
    'audio_sample_position', 'input_event_cursor',
    'pending_event_front_index', 'save_frame_classification',
]

FREEZE_RULE = [
    '🔑 **存档冻结点必须记录为可验证事实，'
    '不能只记录"在菜单按了保存"**',
    '🔑 二进制序列化**只保存被 `PROPERTY_USAGE_STORAGE` 标记的属性** —— '
    '普通脚本状态 · 运行中的信号连接 · 回调链**不会自动成为持久状态**',
    '🔑 这说明"**序列化存在**"与"**世界一致性快照存在**"是**两个命题**',
    '🔴 **具体编号必须由原版测量决定；没有证据只能写 `unknown`，'
    '不能填 0 · 1 或 `last_update`**',
]

# 读档六步
LOAD_SIX = ['停写', '冻结', '校验', '回退', '重建', '放行']

LOAD_DETAIL = [
    '先**禁用外部事件和后台加载**',
    '再**冻结所有可变系统的同一时钟点**',
    '校验 **schema 版本 · checksum · 持久对象清单 · 交叉引用**',
    '随后**销毁或回退运行中的对象，重放持久身份与持续过程**',
    '最后**重建音频 · 粒子 · 接触查询等瞬态输出**',
    '🔴 若校验失败，**必须保留旧可玩世界或明确进入恢复界面**，'
    '**不能让对象在"半加载"状态继续运行**',
]

# 🔑 飞行投射物
PROJ_FIELDS = [
    '弹丸 ID', '生成 tick', '剩余距离', '当前相位', '动画句柄', '音频句柄',
]

PROJ_TEST = '在**相同 RNG 种子 · 相同输入序列**下比较 30 / 60 / 120 '
'及**可变刷新率**'

PROJ_RULE = [
    '🔑 **飞行中的投射物消失不能自动判为 bug，'
    '但必须判为证据缺口**',
    '🔑 原版可能采用**瞬时命中 · 锁帧模拟 · 确定性 replay**；'
    '也可能**只保存逻辑弹丸不保存视觉轨迹**；'
    '还可能**根本没有飞行过程**',
    '🔑 **若可变刷新率改变弹丸存在性** → '
    '保存对象至少是**物理弹丸而非图形粒子**',
    '🔑 **若结果稳定**，才继续判断它是否必须进档',
    '🔴 **本轮不声称任何具体原版采用何种方案**',
]

# 氛围层
AMB_EXAMPLES = [
    '脚步尘粒', '衣物摩擦', '呼吸', '心跳', '武器机械声', '环境风', '雨',
    '虫鸣', '远端交通', '空间反射与混响', '背景 NPC 闲聊', '远景动态',
    '昼夜渐变', '可破坏物残余', '接触表面的微反馈',
]

AMB_FIELDS = [
    'ambience_layer_id', 'trigger_zone_id', 'trigger_signal',
    '**continuity_mode**', 'spatialization', 'reverb_send', 'min_gain',
    'max_gain', 'fade_up_sec', 'fade_down_sec', 'random_period',
    'cross_layer_mutex', 'evidence_level',
]

AMB_MODE = [
    'continuous', 'triggered_resumable', 'triggered_restartable',
    'one_shot_ambience',
]

AMB_PER_LAYER = [
    '触发域', '持续条件', '淡入淡出', '随机周期', '位置',
    '**与玩家运动的相关性**', '**与昼夜或天气的相关性**',
    '**与其他层的互斥或叠加**', '对混响与遮挡的响应', '跨场景是否连续',
]

AMB_RULE = [
    '🔑 **氛围层不能直接从"太空了"反推**',
    '🔑 取证应记**层数 · 门控 · 相位 · 互相调制**，'
    '🔴 **而不是只统计音轨**',
    '🔑 若原版共有 N 层，应**逐个给稳定 ID** —— '
    '🔴 **不能把"雨声大、风声小"记成一句主观评价**',
    '🔑 "**六层环境音**"**必须由原始记录证明** —— '
    '🔴 **本轮不能把"六"写进规则**',
]

# 🔑 氛围层测量
AMBM_SIGNAL = [
    '频谱能量', '声像', 'RMS', '过零率', 'onset 密度', '混响尾长度',
    '左右耳差异',
]

AMBM_POSE = ['静止', '慢跑', '冲刺', '开门', '转身', '进出遮挡区']

AMBM_RULE = ('🔑 在**同一安全点**做 ' + ' · '.join(AMBM_POSE) +
             ' 六组，比较 ' + ' · '.join(AMBM_SIGNAL) + '。')
AMBM_KEY = ('🔑 **若工具层能量与玩家层能量出现可重复的独立 onset**，'
            '就说明**至少存在两条独立触发链**')
AMBM_VIS = ('🔑 视觉氛围层做**帧差 · 运动向量 · 色温 · 曝光 · 可见区域**分析；'
            '🔴 **但帧差只证明像素变化，不证明粒子实体**')

# 🔑 同一帧
CLOCK_FOUR = [
    '**逻辑帧**', '**固定更新（FixedUpdate）**', '**BeforeRender**',
    '**渲染帧**',
]

CLOCK_FIELDS = [
    'event_id', '**game_tick**', '**physics_substep**', '**render_frame**',
    '**audio_sample_clock**', '**stable_order_key**',
]

CLOCK_RULE = [
    '🔑 **同帧发生不等于同一时刻发生，更不等于同一时钟**',
    '🔑 至少有**逻辑 tick · 固定物理 tick · 渲染 · 音频 · 输入采样**'
    '等不同时间域',
    '🔴 **不能只记录 frame index**',
]

# 事件四阶段
ORDER_FOUR = [
    '**输入收集与意图提交**',
    '**确定性与仲裁模拟**',
    '**持续过程推进 · 音频与视觉演出**',
    '**UI 通知聚合**',
]

ORDER_KEY = '(system_priority, source_stable_id, event_type_priority, event_id)'

ORDER_RULE = [
    '🔑 **事件风暴应排序 · 合并 · 显式丢弃**，'
    '🔴 **不能依赖注册顺序**',
    '🔑 优先级**不是艺术偏好，而是对原版的观察结果**',
    '🔑 若原版同一 frame 内伤害 · 死亡 · 掉落 · 成就的**顺序未知**，'
    '应**保留多个候选并实现开关**，让原版录像回归选择 —— '
    '🔴 **不能直接定"先掉血后死亡"**',
    '🔑 脚本**自身不决定顺序**，顺序**必须由原版录像或日志指定**',
]

# 🔑 最后一下
KILL_FACT = ('每个受击者的**最后伤害来源 · 伤害事件 ID · 死亡事件 ID · '
             '结算 tick · 权威对象**')
KILL_SHOW = '**voice 占用 · 镜头归属 · 成就授予 · 掉落生成 · 通知合并键**'

KILL_OPTIONS = [
    '一次共享击杀', '两次独立击杀', '两个演出', '一次演出', '一次合并通知',
]

KILL_RULE = [
    '🔑 **"最后一下"必须同时记录数值事实与演出事实**',
    '🔑 数值与演出**可以不同，但差异必须显式** —— '
    '例如"**双杀事实一次，演出播放两次**"**是合法结论**，'
    '🔴 **前提是原版证据支持**',
]

# 🔑 意图边界
INTENT_RULE = [
    '🔑 **"按住奔跑"与"动作继续请求"是两个不同事实**',
    '🔑 菜单打开时某按钮**仍显示 pressed**，只说明'
    '**低层硬件或输入状态未变化**，'
    '🔴 **不能证明角色移动请求仍有效**',
]

INTENT_BOUNDARY = [
    '过场开始', '过场结束', '菜单打开', '菜单关闭', '场景加载', '控制接管',
    '死亡', '击退', '眩晕', '设备断开', '映射改变', '后台恢复',
    '输入模式切换',
]

INTENT_RESULT = ['**丢弃**', '**转为等待**', '**转为恢复**']

INTENT_FIELDS = [
    'preserve_raw_event', 'preserve_action_phase',
    '**preserve_combo_buffer**', '**preserve_held_request**', 'convert_to',
    'expire_after', 'resume_only_if', 'visual_feedback',
]

INTENT_EVENTS = [
    'device_lost', 'device_resumed', 'control_rebound', 'intent_invalidated',
    'intent_expired', 'intent_restored',
]

INTENT_RULE2 = [
    '🔑 边界事件至少应发出 ' + ' · '.join(INTENT_EVENTS) +
    '，**由玩法状态决定后续**',
    '🔴 **而不是由底层 API 默认行为决定**',
    '🔴 **"菜单消失即自动恢复所有按键"是高风险冲突做法**',
    '🔴 **设备重连不是输入自动恢复的同义词** —— '
    '新设备可能处于**不同映射 · 不同摇杆零点 · 不同权限状态**，'
    '未读事件继续消费会造成**幽灵输入**',
]

# 连招缓冲
COMBO_FIELDS = [
    'intent_id', 'action_id', 'trigger_phase', 'source_control_id',
    'control_mode_id', 'qualifier_mask', 'logical_clock', 'deadline_clock',
    'consumed_at', 'cancelled_at', 'boundary_version', 'resumable',
    'restored_as',
]

COMBO_RULE = [
    '🔑 **连招缓冲需要状态机和过期时间，不能只保存按钮布尔值**',
    '🔑 它可能属于 **input 域 · action 域 · character state 域**，'
    '🔴 **三者不能混用**',
    '🔑 属角色状态 → 过场打断后决定是否保留；'
    '属原始按键 → 设备变化后**不能原样复活**；'
    '属长期动作请求 → 只有**输入模式与权限允许时**恢复',
    '🔑 应支持两种模式：**严格原始事件序**（复现）与'
    '**确定性意图序**（gameplay），**映射必须显式**',
]

# HUD 双时钟
HUD_FIELDS = [
    '**world_authoritative_clock**', '**hud_observed_frame**',
    'render_present_time', 'displayed_value', 'display_transition_kind',
]

HUD_LEGAL = ['插值', '滚动动画', '离散跳变', '预测显示', '回滚']

HUD_ILLEGAL = [
    '同一事实在不同 HUD 上**显示不同最终值**',
    '**动画永远追不上**',
    '**回滚时数值反向跳跃却无任何反馈**',
]

HUD_RULE = ('🔑 **HUD 与世界必须共享可观测事实，但可以有合法表现延迟**；'
            '🔴 **没有原版测量时，不应填写固定延迟帧数**')

CONFLICTS = [
    '❌ **把"序列化自动保存的字段"当"世界快照完整性"**',
    '❌ 把"播放器正在发声"当"声音对象已持久化"',
    '❌ 把"事件在同一帧触发"当"按同一顺序消费"',
    '❌ **把"按键仍在 pressed"当"玩家意图仍有效"**',
    '❌ **"读取成功即世界合法"**',
    '❌ 没有证据却把冻结点填 0 / 1 / last_update',
    '❌ **把"六层环境音"写进规则**（须原始记录证明）',
    '❌ 只统计音轨而不记层数/门控/相位/互调',
    '❌ 把氛围层当"可优化"整层砍掉',
    '❌ **只记录 frame index**',
    '❌ 事件依赖注册顺序',
    '❌ **直接定"先掉血后死亡"**',
    '❌ **"菜单消失即自动恢复所有按键"**',
    '❌ 设备重连当成输入自动恢复',
    '❌ 连招缓冲只保存按钮布尔值',
    '❌ **帧差证明粒子实体**',
]

FIELDS = [
    ('item_id', '项编号'),
    ('domain', '域（snap / freeze / load / proj / amb / ambm / clock / '
               'order / kill / intent / combo / hud）'),
    ('legacy_value', '**原版值**（无证据填 unknown）'),
    ('new_value', '新引擎值'),
    ('match', '**是否一致**'),
    ('tolerance', '**允许偏差**'),
    ('evidence', '证据等级 1-8'),
]


def _hdr(t, w=80):
    print('=' * w)
    print(t)
    print('=' * w)


def cmd_snap(a):
    _hdr('🔴 存档（**六类状态分类器**）')
    print(f'   {"类别":<16}{"入档":<12}{"正确处置":<26}读档失败症状')
    print('   ' + '-' * 74)
    for k, y, act, sym, _ in SNAP_SIX:
        print(f'   {k:<16}{y:<12}{act:<26}{sym}')
    print('\n包含内容:')
    for k, _, _, _, ex in SNAP_SIX:
        print(f'   {k:<16} {ex}')
    print('\n规则:')
    for r in SNAP_RULE:
        print(f'   {r}')
    return 0


def cmd_freeze(a):
    _hdr('快照（**冻结点字段**）')
    print('字段: ' + ' · '.join(FREEZE_FIELDS))
    print('\n规则:')
    for r in FREEZE_RULE:
        print(f'   {r}')
    return 0


def cmd_load(a):
    _hdr('读档（**六步**）')
    print('   ' + ' → '.join(LOAD_SIX))
    print()
    for d in LOAD_DETAIL:
        print(f'   · {d}')
    return 0


def cmd_proj(a):
    _hdr('🔑 飞行投射物（**不能自动判 bug**）')
    print('记录: ' + ' · '.join(PROJ_FIELDS))
    print(f'\n测法: {PROJ_TEST}')
    print('\n规则:')
    for r in PROJ_RULE:
        print(f'   {r}')
    return 0


def cmd_amb(a):
    _hdr('氛围层（**取证模板**）')
    print('可能的层: ' + ' · '.join(AMB_EXAMPLES))
    print('\n每层记录: ' + ' · '.join(AMB_PER_LAYER))
    print('\n字段: ' + ' · '.join(AMB_FIELDS))
    print('\ncontinuity_mode: ' + ' · '.join(AMB_MODE))
    print('\n规则:')
    for r in AMB_RULE:
        print(f'   {r}')
    return 0


def cmd_ambm(a):
    _hdr('氛围层（**测量方法**）')
    print(f'   {AMBM_RULE}')
    print(f'\n   {AMBM_KEY}')
    print(f'\n   {AMBM_VIS}')
    return 0


def cmd_clock(a):
    _hdr('🔑 "同一帧"（**四种解释**）')
    for c in CLOCK_FOUR:
        print(f'   · {c}')
    print('\n事件必带字段: ' + ' · '.join(CLOCK_FIELDS))
    print('\n规则:')
    for r in CLOCK_RULE:
        print(f'   {r}')
    return 0


def cmd_order(a):
    _hdr('事件（**稳定排序键四阶段**）')
    for i, o in enumerate(ORDER_FOUR, 1):
        print(f'   {i}. {o}')
    print(f'\n排序键: {ORDER_KEY}')
    print('\n规则:')
    for r in ORDER_RULE:
        print(f'   {r}')
    return 0


def cmd_kill(a):
    _hdr('🔑 "最后一下"（**数值 vs 演出**）')
    print('数值侧: ' + KILL_FACT)
    print('演出侧: ' + KILL_SHOW)
    print('\n可能结论: ' + ' · '.join(KILL_OPTIONS))
    print('\n规则:')
    for r in KILL_RULE:
        print(f'   {r}')
    return 0


def cmd_intent(a):
    _hdr('🔑 意图（**边界矩阵**）')
    for r in INTENT_RULE:
        print(f'   {r}')
    print('\n13 个边界: ' + ' · '.join(INTENT_BOUNDARY))
    print('\n每边界三种结果: ' + ' · '.join(INTENT_RESULT))
    print('\n字段: ' + ' · '.join(INTENT_FIELDS))
    print('\n规则:')
    for r in INTENT_RULE2:
        print(f'   {r}')
    return 0


def cmd_combo(a):
    _hdr('连招缓冲（**状态机**）')
    print('字段: ' + ' · '.join(COMBO_FIELDS))
    print('\n规则:')
    for r in COMBO_RULE:
        print(f'   {r}')
    return 0


def cmd_hud(a):
    _hdr('HUD（**双时钟**）')
    print('字段: ' + ' · '.join(HUD_FIELDS))
    print('\n合法差异: ' + ' · '.join(HUD_LEGAL))
    print('非法差异: ' + ' · '.join(HUD_ILLEGAL))
    print(f'\n   {HUD_RULE}')
    return 0


def cmd_init(a):
    os.makedirs(os.path.dirname(a.init) or '.', exist_ok=True)
    with open(a.init, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow([k for k, _ in FIELDS])
        w.writerow(['TODO'] * len(FIELDS))
    print(f'已生成连续性表: {a.init}')
    print('\n⚠️ 十二域：snap / freeze / load / proj / amb / ambm / clock / '
          'order / kill / intent / combo / hud')
    print('⚠️ **无原版证据时 legacy_value 填 unknown，不要填 0/1/'
          'last_update**')
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
    unknown = []
    for i, r in enumerate(rows, 1):
        lv = g(r, 'legacy_value')
        m = g(r, 'match').lower()
        if lv.lower() in ('unknown', '未知', '待采集'):
            unknown.append(i)
            continue
        if m not in ('yes', 'y', 'true', '是', '一致'):
            mismatch.append(i)
        if not lv or lv == 'TODO':
            no_legacy.append(i)
        ev = g(r, 'evidence')
        if not ev or ev == 'TODO':
            no_grade.append(i)
        else:
            d = ev.split('.')[0].strip()
            if d.isdigit() and int(d) >= 7:
                no_grade.append(i)

    print('=' * 76)
    print(f'连续性 · {len(rows)} 条')
    print('=' * 76)
    if mismatch:
        print(f'\n🚫 **不一致** {len(mismatch)} 条（行 {mismatch[:15]}）')
    if no_legacy:
        print(f'\n❌ {len(no_legacy)} 条缺**原版值**（行 {no_legacy[:15]}）')
    if no_grade:
        print(f'\n🚫 {len(no_grade)} 条**证据等级缺失或 ≥7 级**'
              f'（行 {no_grade[:15]}）')
    if unknown:
        tag = '（**本轮允许，属待采集缺口**）' if a.allow_unknown \
            else '（**未加 --allow-unknown，视为硬阻断**）'
        print(f'\n⚠️ **unknown 待采集** {len(unknown)} 条'
              f'（行 {unknown[:15]}）{tag}')
        if not a.allow_unknown:
            no_grade.extend(unknown)

    if not (mismatch or no_legacy or no_grade):
        print('\n✅ 连续性：一致、原版值完整、证据等级达标')

    print('\n🔑 **本轮交付的是「可验证缺口」，不是虚构的新体验清单。**')
    print('   **序列化存在 ≠ 世界一致性快照存在。**')
    print('   **事件同帧触发 ≠ 同顺序消费；按键 pressed ≠ 意图有效。**')
    print('   **没有原版证据就填 unknown，不许填 0/1/last_update。**')
    return 1 if (a.gate_check and (mismatch or no_legacy or no_grade)) else 0


def main():
    ap = argparse.ArgumentParser(description='世界连续性与事件序')
    ap.add_argument('--snap', action='store_true')
    ap.add_argument('--freeze', action='store_true')
    ap.add_argument('--load', action='store_true')
    ap.add_argument('--proj', action='store_true')
    ap.add_argument('--amb', action='store_true')
    ap.add_argument('--ambm', action='store_true')
    ap.add_argument('--clock', action='store_true')
    ap.add_argument('--order', action='store_true')
    ap.add_argument('--kill', action='store_true')
    ap.add_argument('--intent', action='store_true')
    ap.add_argument('--combo', action='store_true')
    ap.add_argument('--hud', action='store_true')
    ap.add_argument('--init')
    ap.add_argument('--check')
    ap.add_argument('--gate-check', action='store_true')
    ap.add_argument('--allow-unknown', action='store_true')
    a = ap.parse_args()
    fns = {'snap': cmd_snap, 'freeze': cmd_freeze, 'load': cmd_load,
           'proj': cmd_proj, 'amb': cmd_amb, 'ambm': cmd_ambm,
           'clock': cmd_clock, 'order': cmd_order, 'kill': cmd_kill,
           'intent': cmd_intent, 'combo': cmd_combo, 'hud': cmd_hud}
    for k, fn in fns.items():
        if getattr(a, k):
            return fn(a)
    if a.init:
        return cmd_init(a)
    if a.check:
        return cmd_check(a)
    print('❌ 需要 --snap / --freeze / --load / --proj / --amb / --ambm / '
          '--clock / --order / --kill / --intent / --combo / --hud / '
          '--init / --check 之一')
    return 2


if __name__ == '__main__':
    sys.exit(main())
