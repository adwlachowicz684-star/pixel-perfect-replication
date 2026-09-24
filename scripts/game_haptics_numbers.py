#!/usr/bin/env python3
"""力反馈（触觉）+ 数值多值契约（第二十二轮 A / B 类）。

**🔑 A 类核心**：
> 🔴 **震感不是强度的浮点数，而是一段应录制的输出波形。**
> 🔴 **左右马达不是"强/弱"两档** —— 低频马达产生**持续冲击与身体重量**，
> 高频马达表达**纹理、材质和脆感**；包络的上升时间、峰值位置、
> 衰减斜率和停振时间都不同。
>
> 🔑 若重制版把两个马达压成一条强度曲线，
> 玩家感受到的**不是"震得小了"，而是材质消失**。

**🔑 B 类核心**：
> 🔴 **显示错误是规则错误。**
> 🔑 若 12.7 显示 13 但暴击阈值判断仍用 12.7 → "显示 13"**不是错误**；
> 🔑 若升级阈值用的是显示 13 → **升级帧会改变**。
> 🔴 **不能只写"四舍五入"**。

用法:
  game_haptics_numbers.py --haptic   # 🔴 触觉**17 字段**
  game_haptics_numbers.py --motor    # 🔴 左右马达**频段分工**
  game_haptics_numbers.py --trigger  # 自适应扳机是**状态机不是百分比**
  game_haptics_numbers.py --fallback # 🔴 关震动后信息**是否用其他通道补**
  game_haptics_numbers.py --numbers  # 🔴 数值**五值分离**
  game_haptics_numbers.py --round    # **取整位置**必须明确归属
  game_haptics_numbers.py --percent  # 🔴 百分比**六种不同量**
  game_haptics_numbers.py --abbrev   # 大数缩写**不是固定三位分组**
  game_haptics_numbers.py --threshold # 🔴 阈值绑定**哪一类值**
  game_haptics_numbers.py --locale   # 本地化**不能从 ICU 反推**
  game_haptics_numbers.py --init ledger/haptics_numbers.csv
  game_haptics_numbers.py --check ledger/haptics_numbers.csv --gate

退出码: 0 通过 / 1 缺项 / 2 用法错误
"""
import argparse
import csv
import os
import sys

# 🔴 触觉 17 字段
HAPTIC_FIELDS = [
    'source_event_id', 'game_time', 'phase', 'intent', '**low_motor**',
    '**high_motor**', 'left_trigger_effect', 'right_trigger_effect',
    'device_profile', 'connection_type', 'report_timestamp',
    'sample_interval', 'expected_settling_time', 'visual_offset_ms',
    'audio_offset_ms', '**fallback_channels**', 'closed_reason',
]

HAPTIC_RULE = [
    '🔴 **震感不是强度的浮点数，而是一段应录制的输出波形**',
    '🔑 `low_motor` 与 `high_motor` **不能只写"0–1"** —— '
    '必须记录**设备原始粒度、校准曲线和持续时间**',
    '🔑 自适应扳机还要记录**起始位置、停止位置、力级、阻尼模式、'
    '触发区、模式切换和是否立即取消**',
    '🔑 触觉要记录**设备固件、连接方式和报告提交时间**，'
    '**不能只用同一帧的逻辑时间打戳**',
]

# 🔴 左右马达
MOTOR_BANDS = [
    ('**低频马达**', '产生**持续冲击和身体重量**'),
    ('**高频马达**', '表达**纹理、材质和脆感**'),
]

MOTOR_FIELDS = [
    '**frequency_band**', '**attack_ms**', '**peak_at_ms**',
    '**decay_curve**', 'stop_before_zero', 'resonance_avoidance_hz',
]

MOTOR_RULE = [
    '🔴 **左右马达不是"强/弱"两档**，真正的记录至少包含**频段分工**',
    '🔑 两者包络的**上升时间、峰值位置、衰减斜率和停振时间**都不同',
    '🔑 换弹碰撞可先由低频产生"撞击"，再由高频产生"金属细响"',
    '🔴 若重制版把两个马达压成**一条强度曲线** → '
    '玩家感受到的**不是"震得小了"，而是材质消失**',
]

# 自适应扳机
TRIGGER_MODES = [
    'resistance', 'vibration', 'feedback', 'weapon', 'bow', 'section',
]

TRIGGER_TESTS = [
    '阻力是否在**按下过程中变化**',
    '越过硬点是否**有一帧释放**',
    '**半程松手是否保留**',
    '连续开火是否**叠加或重启**',
    '**暂停时是否继续施力**',
    '切到菜单/过场**是否解除**',
    '**拔线重连**是否从默认无阻力变回旧状态',
    '**低电量、USB/蓝牙、固件版本**切换是否改变包络',
]

TRIGGER_RULE = [
    '🔑 **自适应扳机是可执行状态机，而不是阻力百分比**',
    '🔑 每个扳机状态应写 '
    '`mode: ' + '|'.join(TRIGGER_MODES) + '`，'
    '并保存**当前段、下一段、触发点、释放点、方向、循环、条件中断和恢复策略**',
    '🔴 任何一项未记录，**只能标 `unknown_protocol`，不能标 `match`**',
]

# 🔴 关闭补偿
FALLBACK_RULE = [
    '🔴 **"关闭震动就关闭所有反馈"是错误补偿**',
    '🔑 视觉震动、屏幕边缘红光、控制器扬声器、音效、字幕和准星反馈'
    '**可能承载方向、材质、受伤、装填完成等信息**',
    '🔑 新增字段 `information_payload` 与 `fallback_set`，'
    '**逐项检查原版信息是否可缺失**',
    '🔑 若原版允许关闭后**仍保留视觉提示** → 重制必须保留',
    '🔴 若原版**完全关闭** → 重制**擅自增加提示属于偏离**',
]

FALLBACK_EXTRA = '🔑 **阻力不是纯反馈，也可能成为输入成本** —— '
'DualSense 触觉/扳机适配**可能影响瞄准和开枪速度**；'
'应测量**从按下到模拟权威值变化的延迟**，而非只测马达启动'

# 🔴 数值五值
NUM_FIVE = [
    ('**raw_value**', '可浮点/定点，存储精确值'),
    ('**computed_value**', '参与下一次判定'),
    ('**committed_value**', '事务结束后持久化'),
    ('**display_value**', '显示值'),
    ('**animated_value**', 'UI 动画追赶中的值'),
]

NUM_FIELDS = [
    'raw_value', 'computed_value', 'committed_value', 'display_value',
    'formatted_text', '**rounding_mode**', '**tie_break**', 'truncation',
    'locale',
]

NUM_RULE = [
    '🔑 **存储值、计算值、显示值必须成为同一字段的三个版本**'
    '（本轮扩展为五值）',
    '🔴 **禁止"把显示字符串再解析回战斗系统"**',
    '🔑 大数规则**不能脱离游戏规则直接继承区域规则** —— '
    '例如某作"小于亿保留原值，大于亿使用 M"是**专门阈值**',
]

# 取整位置
ROUND_CASES = [
    '浮点伤害**先舍入再比较暴击**，还是先比较再舍入',
    '经验值**先取整再触发升级**，还是升级阈值先以精确值判断',
    '价格**先舍入再交易**，还是交易后舍入',
    'UI 动画从 `committed_value` 开始，还是从上一帧 `display_value` 追赶',
]

ROUND_RULE = [
    '🔑 **取整位置必须明确归属**',
    '🔑 若 12.7 显示 13 但暴击阈值判断仍用 12.7 → **"显示 13"不是错误**',
    '🔑 若升级阈值用的是显示 13 → **升级帧会改变**',
    '🔴 **不能只写"四舍五入"**',
]

# 🔴 百分比六量
PERCENT_SIX = [
    '输入系数', '显示百分比', '实际倍率', '界面预览', '服务端权威值',
    '对比基准',
]

PERCENT_FIELDS = [
    '**unit_kind**', '**base_reference**', '**operation**', 'scale',
    'rounding_before_display', '**tooltip_rounding**', '**hud_rounding**',
]

PERCENT_RULE = [
    '🔑 "+15%" 可能是**乘 1.15**、**加 15 个百分点**、'
    '相对于**基础值还是当前总值**，也可能是**仅在 tooltip 中舍入**',
]

# 缩写
ABBREV_FIELDS = [
    '**grouping_size**', '**grouping_at_exponent**',
    '**abbreviation_threshold**', 'abbreviation_token',
    '**round_to_tier**', '**tiered_rounding**',
]

ABBREV_RULE = [
    '🔴 **大数缩写不是固定三位分组** —— 英文按三位、韩文按四位，'
    '另有"亿以上使用 M"的规则',
    '🔑 边界要逐个测：999,999 是否显示完整 · 1,000,000 是否变 1.00M · '
    '99.99M 是否跳到 100M —— **都可能是原版刻意边界**',
]

# 🔴 阈值绑定
THRESHOLD_VERSIONS = ['raw', 'computed', 'committed', 'display', 'animated']

THRESHOLD_RULE = [
    '🔑 血量"低于 20% 变红"至少**五种实现**：原始血量 · 显示血量 · '
    '当前/最大值 · 当前/上限值 · **平滑动画值**',
    '🔑 模板每个阈值增加 '
    '`observed_value_version: ' + '|'.join(THRESHOLD_VERSIONS) + '`',
    '🔑 还要记录**判定时刻是请求时、提交时还是绘制时**',
]

THRESHOLD_EXAMPLE = '🔑 某作伤害数字高亮**不只比较当前伤害**，还比较'
'"**上次以橙色显示的值**"，并让该基准**每秒衰减 3%**，同时'
'**忽略前 10 个最大值**、**连续 10 秒未造成伤害后重置** —— '
'**说明显示阈值本身就是玩法规则而非前端格式**'

# 本地化
LOCALE_FIELDS = [
    '**prefix_rule**', '**negative_format**', 'zero_format', 'empty_format',
    'min_width_justification', '**digit_glyph_set**', 'rtl_embedding',
]

LOCALE_RULE = [
    '🔑 `+X` · 正负号 · 空格 · 千分位 · 小数点 · 负号位置 · 括号负号 · '
    '从右到左文本 · 数字字形 · 大数词（万/亿）· 货币位置 · 宽度对齐',
    '🔴 **必须从原版截图或真机录制测量，不能从 ICU/CLDR 反推**',
    '🔑 不同库即使同一规范版本，也可能因**兼容模式和区域补丁**不同'
    '而输出不同',
]

CONFLICTS = [
    '❌ 把触觉做成"**强度×时长**"的通用抽象',
    '❌ 引擎默认"**震动随帧更新**"（会制造拍频）',
    '❌ **"关闭震动就关闭所有反馈"**',
    '❌ 两个马达压成一条强度曲线',
    '❌ 未记录却标 `match`（应标 `unknown_protocol`）',
    '❌ **只写"四舍五入"**',
    '❌ 在战斗结果上**直接取整**（会改后续 DOT/护盾/暴击/经验/交易）',
    '❌ **把显示字符串再解析回战斗系统**',
    '❌ 用浮点转字符串的**默认格式**做复刻',
    '❌ 大数缩写假定固定三位分组',
    '❌ 阈值不绑定数值版本',
    '❌ **本地化从 ICU/CLDR 反推**而非原版测量',
    '❌ 把 SDL 跨平台抽象当作**专有硬件真相**',
]

FIELDS = [
    ('item_id', '项编号'),
    ('domain', '域（haptic / motor / trigger / fallback / numbers / '
               'round / percent / abbrev / threshold / locale）'),
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


def cmd_haptic(a):
    _hdr('🔴 触觉（**输出波形**）')
    print('字段: ' + ' · '.join(HAPTIC_FIELDS))
    print('\n规则:')
    for r in HAPTIC_RULE:
        print(f'   {r}')
    return 0


def cmd_motor(a):
    _hdr('🔴 左右马达（**频段分工**）')
    for k, why in MOTOR_BANDS:
        print(f'   {k:<14} {why}')
    print('\n字段: ' + ' · '.join(MOTOR_FIELDS))
    print('\n规则:')
    for r in MOTOR_RULE:
        print(f'   {r}')
    return 0


def cmd_trigger(a):
    _hdr('自适应扳机（**状态机**）')
    print('mode: ' + ' | '.join(TRIGGER_MODES))
    print('\n必测:')
    for t in TRIGGER_TESTS:
        print(f'   · {t}')
    print('\n规则:')
    for r in TRIGGER_RULE:
        print(f'   {r}')
    return 0


def cmd_fallback(a):
    _hdr('🔴 关闭震动后的信息补偿')
    for r in FALLBACK_RULE:
        print(f'   {r}')
    print(f'\n   {FALLBACK_EXTRA}')
    return 0


def cmd_numbers(a):
    _hdr('🔴 数值五值分离')
    for k, why in NUM_FIVE:
        print(f'   {k:<22} {why}')
    print('\n字段: ' + ' · '.join(NUM_FIELDS))
    print('\n规则:')
    for r in NUM_RULE:
        print(f'   {r}')
    return 0


def cmd_round(a):
    _hdr('取整位置（**必须明确归属**）')
    for i, c in enumerate(ROUND_CASES, 1):
        print(f'   {i}. {c}')
    print('\n规则:')
    for r in ROUND_RULE:
        print(f'   {r}')
    return 0


def cmd_percent(a):
    _hdr('🔴 百分比六种不同量')
    for p in PERCENT_SIX:
        print(f'   · {p}')
    print('\n字段: ' + ' · '.join(PERCENT_FIELDS))
    print('\n规则:')
    for r in PERCENT_RULE:
        print(f'   {r}')
    return 0


def cmd_abbrev(a):
    _hdr('大数缩写（**非固定三位分组**）')
    print('字段: ' + ' · '.join(ABBREV_FIELDS))
    print('\n规则:')
    for r in ABBREV_RULE:
        print(f'   {r}')
    return 0


def cmd_threshold(a):
    _hdr('🔴 阈值绑定哪一类值')
    print('observed_value_version: ' + ' | '.join(THRESHOLD_VERSIONS))
    print('\n规则:')
    for r in THRESHOLD_RULE:
        print(f'   {r}')
    print(f'\n   {THRESHOLD_EXAMPLE}')
    return 0


def cmd_locale(a):
    _hdr('本地化（**不能从 ICU 反推**）')
    print('字段: ' + ' · '.join(LOCALE_FIELDS))
    print('\n规则:')
    for r in LOCALE_RULE:
        print(f'   {r}')
    return 0


def cmd_init(a):
    os.makedirs(os.path.dirname(a.init) or '.', exist_ok=True)
    with open(a.init, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow([k for k, _ in FIELDS])
        w.writerow(['TODO'] * len(FIELDS))
    print(f'已生成触觉/数值表: {a.init}')
    print('\n⚠️ 十域：haptic / motor / trigger / fallback / numbers / '
          'round / percent / abbrev / threshold / locale')
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
    print(f'触觉/数值 · {len(rows)} 条')
    print('=' * 76)
    if mismatch:
        print(f'\n🚫 **不一致** {len(mismatch)} 条（行 {mismatch[:15]}）')
    if no_legacy:
        print(f'\n❌ {len(no_legacy)} 条缺**原版值**（行 {no_legacy[:15]}）')
    if no_grade:
        print(f'\n🚫 {len(no_grade)} 条**证据等级缺失或 ≥7 级**'
              f'（行 {no_grade[:15]}）')

    if not (mismatch or no_legacy or no_grade):
        print('\n✅ 触觉/数值：一致、原版值完整、证据等级达标')

    print('\n🔑 **震感是输出波形，不是强度浮点数；两马达压一条曲线会让材质消失。**')
    print('   **显示错误是规则错误；取整位置必须明确归属。**')
    print('   **阈值要绑定数值版本；本地化不能从 ICU 反推。**')
    return 1 if (a.gate_check and (mismatch or no_legacy or no_grade)) else 0


def main():
    ap = argparse.ArgumentParser(description='力反馈与数值契约')
    ap.add_argument('--haptic', action='store_true')
    ap.add_argument('--motor', action='store_true')
    ap.add_argument('--trigger', action='store_true')
    ap.add_argument('--fallback', action='store_true')
    ap.add_argument('--numbers', action='store_true')
    ap.add_argument('--round', action='store_true')
    ap.add_argument('--percent', action='store_true')
    ap.add_argument('--abbrev', action='store_true')
    ap.add_argument('--threshold', action='store_true')
    ap.add_argument('--locale', action='store_true')
    ap.add_argument('--init')
    ap.add_argument('--check')
    ap.add_argument('--gate-check', action='store_true')
    a = ap.parse_args()
    fns = {'haptic': cmd_haptic, 'motor': cmd_motor, 'trigger': cmd_trigger,
           'fallback': cmd_fallback, 'numbers': cmd_numbers,
           'round': cmd_round, 'percent': cmd_percent,
           'abbrev': cmd_abbrev, 'threshold': cmd_threshold,
           'locale': cmd_locale}
    for k, fn in fns.items():
        if getattr(a, k):
            return fn(a)
    if a.init:
        return cmd_init(a)
    if a.check:
        return cmd_check(a)
    print('❌ 需要 --haptic / --motor / --trigger / --fallback / --numbers / '
          '--round / --percent / --abbrev / --threshold / --locale / '
          '--init / --check 之一')
    return 2


if __name__ == '__main__':
    sys.exit(main())
