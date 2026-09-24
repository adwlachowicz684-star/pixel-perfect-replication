#!/usr/bin/env python3
"""试玩机/展会机录制与状态机校验（第五十一轮 A）。

> 🔑 **没有公开通用规则可以替代目标机型实测：街机 Attract Mode 不是跨厂商
> 统一的定时器，而由各游戏软件定义。**
> 🔴 **"先记录后偏离"的最小单位不是"街机"这个品类，而是
> `title + region + revision + DIP/设置 + 机柜线束` 的五元组。**
> 🔴 **任何把某一台机柜测得的 N 秒推广为行业默认值的做法，本身就是方法论污染。**

用法:
  kiosk_recorder.py --fsm      # 🔑 十二类状态骨架
  kiosk_recorder.py --coin     # 🔑 **Credit 是四个字段，不是"INSERT COIN"某一帧**
  kiosk_recorder.py --tuple    # **五元组：不得跨机型推广**
  kiosk_recorder.py --expo     # **展会预约是另一种 Kiosk 状态，不是投币倒计时**
  kiosk_recorder.py --gap      # 🔑 **证据不足：转入实测计划，不写秒数**
  kiosk_recorder.py --harness  # **开源 Kiosk 只做 capture harness**
  kiosk_recorder.py --init ledger/kiosk_states.csv
  kiosk_recorder.py --check ledger/kiosk_states.csv --gate

退出码: 0 通过 / 1 缺项 / 2 用法错误
"""
import argparse
import csv
import os
import sys

FSM = [
    ('power_on', '上电自启'),
    ('watchdog_restore', '看门狗恢复'),
    ('attract', 'Attract 循环'),
    ('staff_menu', '店员菜单（后门键序列）'),
    ('coin_or_free', '投币/免费玩'),
    ('limited_session', '限定会话'),
    ('countdown_warning', '倒计时警告'),
    ('timeout_interrupt', '超时中断'),
    ('force_attract', '强制回 Attract'),
    ('clear_or_keep', '清档/保留高分'),
    ('staff_reset', '工作人员重置'),
    ('expo_end', '展会结束屏'),
]
FSM_RULE = '🔑 **每项写成 `(event, pre_state, post_state, observable_fields, '
'evidence)`；`observable_fields` 应含物理键磨损 · 灯箱 · 投币口灯 · 贴纸 · '
'菜单键序列 · 音频 · 屏幕烧残 · 排队提示 · 手柄应急**'

COIN_RULE = '🔑 **Credit 不是"INSERT COIN"的某一帧，而是四个字段。**'
COIN_FIELDS = [
    ('`credit_event`', '投币/刷卡/触发的具体事件'),
    ('`coin_to_credit_rate`', '**1 币＝N credit**（由 operator 配置）'),
    ('`common_or_individual`', '**共同 credit 池 vs 个人 credit**'),
    ('`service_credit`', '服务 credit（店员/测试）'),
]
COIN_EG = '🔑 官方机柜手册样本：**Service 键移动光标 · Test 键进入或修改设置**；'
'🔑 **COIN CHUTE TYPE 可为 COMMON/INDIVIDUAL**，SERVICE TYPE 亦可如此区分；'
'具体设定示例是 **1 COIN(S) COUNT AS 1 CREDIT(S)**'
COIN_INV = '🔑 可测试的不变量：**同一笔 coin 是否加入公共 credit 池，'
'取决于 operator configuration，🔴 而不是玩家按键**'

TUPLE_RULE = '🔑 最小取证单位是五元组，不是品类。'
TUPLE_5 = ['title', 'region', 'revision', 'DIP/设置', '机柜线束']
TUPLE_NO = '🔴 **不能把某一台机柜测得的 N 秒推广为行业默认值**'

EXPO_RULE = '🔑 **展会预约是另一种 Kiosk 状态，而不是街机投币倒计时。**'
EXPO_EG = '🔑 官方公开安排样本：要求**提前登记 · 不发现场票**，'
'采用 **QR 电子票并分配时段**；🔑 **同一公告明确其他展台游戏仍为先到先得**'
EXPO_REC = '🔑 可靠的做法是建立**原始素材档案**：'
'拍摄**含现场时钟与画面时间戳的同步视频** · '
'**投币/取票到实际可操作的 latency** · 每场试玩起止 · 工作人员强制结束屏。'
'🔴 **没有这些材料就不写具体秒数**'

GAP_ITEMS = [
    ('通用 Attract 秒数/帧数', '🔑 **证据不足** → 转入 `kiosk_measurement_plan` 逐机型实测'),
    ('投币后倒计时秒数 · 最后 N 秒提示', '🔑 **证据不足** → 只保留原始录制/现场时钟'),
    ('超时后回到 Attract 还是锁机', '🔑 **证据不足** → 仅当实拍形成状态迁移证据后才进 FSM'),
    ('零售展示机自动重置时钟', '🔑 **证据不足**（厂商规范只规定 demo 内容须本地存储 · '
     '设备不得自建 Ad-Hoc 网络 · 须有批准 CMS）；🔴 不吸收二手内部软件材料'),
]
GAP_RULE = '🔑 **对拿不到证据的部分，写"证据不足，转入接入流程"，🔴 不要编造秒数或规格。**'

HARNESS_RULE = '🔑 **开源 Kiosk/Attract 前端适合做承载层与复现层，'
'🔴 不适合冒充实机机柜。**'
HARNESS_ITEMS = [
    ('Attract-Mode（`mickelson/attract`，GPL-3.0-or-later，2026 年仍有提交）',
     '目标是以手柄控制命令行模拟器并**隐藏底层系统** → **capture harness**'),
    ('RetroArch Kiosk Mode（1.6.9）',
     '**隐藏子菜单 · 禁止访问设置 · 禁止安装/升级 core · 可加密码** → '
     '**访问保护/展示前端**，无跨机柜统一时序标准'),
]

CONFLICTS = [
    '❌ **把某一台机柜测得的 N 秒推广为行业默认值**（方法论污染）',
    '❌ 把 MAME 的驱动默认值或修复后行为当实机表现标准',
    '❌ 把"INSERT COIN"某一帧当成 credit 的唯一事实',
    '❌ **在无实拍证据时填倒计时秒数**',
    '❌ 把展会预约/排队当成投币倒计时的变体',
    '❌ 吸收二手内部展示机软件材料（获取方式风险）',
    '❌ 把开源 Kiosk 前端当原机 cabinet 表现',
]

FIELDS = [
    ('state_id', '状态编号（见 --fsm 十二类）'),
    ('machine_tuple', '**五元组**：title|region|revision|DIP/设置|线束'),
    ('pre_state', '前置状态'),
    ('post_state', '后置状态'),
    ('observable_fields', '**可观察字段**（含物理磨损/灯箱/音频）'),
    ('measured_seconds', '实测秒数（**无证据留空**）'),
    ('evidence', '证据态 verified/secondhand/unverified/not_present'),
]


def _hdr(t, w=80):
    print('=' * w)
    print(t)
    print('=' * w)


def cmd_fsm(a):
    _hdr('试玩机状态机（**十二类**）')
    for k, v in FSM:
        print(f'   · {k:<20} {v}')
    print(f'\n   {FSM_RULE}')
    return 0


def cmd_coin(a):
    _hdr('🔑 Credit（**四个字段，不是某一帧**）')
    print(f'   {COIN_RULE}')
    for k, v in COIN_FIELDS:
        print(f'\n   【{k}】\n      {v}')
    print(f'\n   {COIN_EG}')
    print(f'\n   {COIN_INV}')
    return 0


def cmd_tuple(a):
    _hdr('🔑 五元组（**不得跨机型推广**）')
    print(f'   {TUPLE_RULE}')
    print('   五元组: ' + ' · '.join(TUPLE_5))
    print(f'\n   {TUPLE_NO}')
    return 0


def cmd_expo(a):
    _hdr('展会预约（**另一种 Kiosk 状态**）')
    print(f'   {EXPO_RULE}')
    print(f'\n   {EXPO_EG}')
    print(f'\n   {EXPO_REC}')
    return 0


def cmd_gap(a):
    _hdr('🔑 证据缺口（**明确标不足，不编造**）')
    print(f'   {GAP_RULE}')
    for k, v in GAP_ITEMS:
        print(f'\n   【{k}】\n      {v}')
    return 0


def cmd_harness(a):
    _hdr('开源 Kiosk（**只做 capture harness**）')
    print(f'   {HARNESS_RULE}')
    for k, v in HARNESS_ITEMS:
        print(f'\n   【{k}】\n      {v}')
    return 0


def cmd_init(a):
    os.makedirs(os.path.dirname(a.init) or '.', exist_ok=True)
    with open(a.init, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow([k for k, _ in FIELDS])
        for k, _ in FSM:
            w.writerow([k, 'TODO', 'TODO', 'TODO', 'TODO', '', 'unverified'])
    print(f'已生成试玩机状态表: {a.init}（十二类骨架）')
    print('\n⚠️ `measured_seconds` **无证据必须留空**——填了就是伪造')
    print('\n⚠️ `machine_tuple` 必须是五元组，不得只写游戏名')
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

    ids = {r['state_id'] for r in rows}
    missing = [k for k, _ in FSM if k not in ids]
    bad_tuple, bad_ev, fabricated = [], [], []
    for i, r in enumerate(rows, 1):
        t = g(r, 'machine_tuple')
        if not t or t == 'TODO' or t.count('|') < 4:
            bad_tuple.append(i)
        if g(r, 'evidence') not in ('verified', 'secondhand',
                                    'unverified', 'not_present'):
            bad_ev.append(i)
        if g(r, 'measured_seconds') and g(r, 'evidence') != 'verified':
            fabricated.append(i)

    print('=' * 76)
    print(f'试玩机状态层 · {len(rows)} 条 / 需覆盖 {len(FSM)} 类')
    print('=' * 76)
    if missing:
        print(f'\n🚫 **未覆盖状态** {len(missing)} 类: {missing}')
    if bad_tuple:
        print(f'\n🚫 {len(bad_tuple)} 条**五元组不完整**（行 {bad_tuple[:15]}）')
    if bad_ev:
        print(f'\n🚫 {len(bad_ev)} 条**证据态非法**（行 {bad_ev[:15]}）')
    if fabricated:
        print(f'\n🚫 {len(fabricated)} 条**秒数已填但证据态非 verified**'
              f'（行 {fabricated[:15]}）—— 🔴 **伪造，必须清空或补实测**')
    if not (missing or bad_tuple or bad_ev or fabricated):
        print('\n✅ 试玩机状态层：十二类齐全、五元组完整、证据态合法、无伪造秒数')

    print('\n🔑 **没有公开通用规则可以替代目标机型实测。**')
    print('   🔴 **把一台机柜的 N 秒推广为行业默认值＝方法论污染。**')
    print('   🔑 **证据不足就写"证据不足"，不要编造。**')
    return 1 if (a.gate_check and
                 (missing or bad_tuple or bad_ev or fabricated)) else 0


def main():
    ap = argparse.ArgumentParser(description='试玩机状态录制与校验')
    ap.add_argument('--fsm', action='store_true')
    ap.add_argument('--coin', action='store_true')
    ap.add_argument('--tuple', action='store_true')
    ap.add_argument('--expo', action='store_true')
    ap.add_argument('--gap', action='store_true')
    ap.add_argument('--harness', action='store_true')
    ap.add_argument('--init')
    ap.add_argument('--check')
    ap.add_argument('--gate-check', action='store_true')
    a = ap.parse_args()
    fns = {'fsm': cmd_fsm, 'coin': cmd_coin, 'tuple': cmd_tuple,
           'expo': cmd_expo, 'gap': cmd_gap, 'harness': cmd_harness}
    for k, fn in fns.items():
        if getattr(a, k):
            return fn(a)
    if a.init:
        return cmd_init(a)
    if a.check:
        return cmd_check(a)
    print('❌ 需要 --fsm / --coin / --tuple / --expo / --gap / --harness '
          '/ --init / --check 之一')
    return 2


if __name__ == '__main__':
    sys.exit(main())
