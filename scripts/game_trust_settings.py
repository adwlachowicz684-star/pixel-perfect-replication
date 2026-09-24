#!/usr/bin/env python3
"""权威信任边界 + 玩家可调契约（第二十四轮 A / B 类）。

**🔑 A 类核心**：
> 🔑 **服务器信任的对象应是具体事实，而不是笼统的"客户端"。**
> 🔴 **视觉先显示命中并不构成权威事实。**
> 🔑 客户端仅可上报：**输入时间戳 · 意图 ID · 预测渲染证据**；
> 🔴 **位置边界 · 命中 · 伤害 · 经济结果 · 库存归属** 必须服务端复算。

**🔑 B 类核心**：
> 🔑 **设置不是单纯的个人偏好，而是一份有版本、有范围、
> 有冲突后果的契约。**
> 🔴 **`reset to default` 至少有五义，必须分开。**

用法:
  game_trust_settings.py --facts   # 🔴 client_claim_facts **事实表**
  game_trust_settings.py --accept  # 服务端**接受条件**（而非只写拒绝外挂）
  game_trust_settings.py --topo    # **三套信任拓扑**
  game_trust_settings.py --rollback # 🔴 预测回滚**分层**
  game_trust_settings.py --hit     # 🔴 命中**四个独立事件**
  game_trust_settings.py --replay  # **重放/观战/反作弊不是同源**
  game_trust_settings.py --settings # 🔴 设置**六类副作用**
  game_trust_settings.py --default # **五义默认值**
  game_trust_settings.py --migrate # 设置**迁移**
  game_trust_settings.py --unsaved # **"设置未保存"是独立状态**
  game_trust_settings.py --init ledger/trust_settings.csv
  game_trust_settings.py --check ledger/trust_settings.csv --gate

退出码: 0 通过 / 1 缺项 / 2 用法错误
"""
import argparse
import csv
import os
import sys

# 🔴 事实表
FACTS_TABLE = [
    ('设备按键、摇杆瞬时值', True, False, True,
     '以意图是否提交为准，**不显示"作弊"**'),
    ('输入发起时间/帧序号', True, '时间合理性、顺序与重放', True,
     '预测动画；**超过回滚窗口则拒绝预测**'),
    ('位置、速度、朝向', '意图与最后确认状态', True, True,
     '**软纠正；回滚才移动，禁止逐帧吸附**'),
    ('开火请求', True, True, '枪口反馈',
     '**命中回调与伤害回调必须分开**'),
    ('命中/伤害', '仅线索', True, '命中特效可预测',
     '**流血但不计数**；服务端随后确认或撤销'),
    ('掉落/拾取', '意图', '生成、归属、防重放', '道具飞行',
     '拾取失败要**回滚本地占位，不能静默消失**'),
    ('交易、货币、经验', '请求', True, '只显示"提交中"',
     '明确 **pending/succeeded/failed**'),
    ('技能结束/无敌', '请求与结束时间', True, '客户端预测',
     '**保命技能一旦确认，不能因后续模拟回滚**'),
    ('关卡完成、剧情选择', '请求', True, '界面可过渡',
     '**失败必须出现"操作被拒绝"，不能卡死**'),
    ('举报/反作弊遥测', True, True, '无',
     '**不得把检测状态暴露给对手**'),
]

FACTS_RULE = [
    '🔑 **每个事实只有一个权威写入者**',
    '🔑 **"必须复算"指结果被采用之前必须能重新推导**，'
    '**不是要求所有复算都走同一线程、同一 tick 或同一代码路径**',
    '🔑 只转发给其他客户端、不承担经济后果的社交事实可以本地预测，'
    '但**仍不能反过来修改权威状态**',
]

# 接受条件
ACCEPT_CHECKS = [
    '会话租约', '权限', '输入序号', '时间单调性', '动作前置条件',
    '资源余额', '距离与视线', '冷却', '技能状态', '随机源版本',
    '可达性', '**幂等键**',
]

ACCEPT_RULE = [
    '🔑 **服务端验证应写"接受条件"，而不是只写"拒绝外挂"**',
    '🔴 **反作弊度量必须独立保存** —— 不能因检测模块认为可疑就'
    '**静默修改权威状态**',
    '🔑 否则**被误检玩家无法申诉**，测试也无法区分'
    '"**预测纠正**"和"**反作弊回滚**"',
]

# 🔴 三拓扑
TOPO_THREE = [
    ('**P2P**', '适合同设备本地多人或完全合作；'
     '格斗的**点对点回滚仍要指定延迟边界、回滚上限、预测质量和胜负裁决**'),
    ('**局域网**', '要区分"**同一设备/同一账号本地多人**"与'
     '"**可信专用服务器都不存在的局域网房间**"；前者可更轻，'
     '后者**仍面对陌生客户端**'),
    ('**专用服务器**', '**默认不信任任何客户端可变状态**；'
     '平台层（EOS/Steam/大厅）**只能证明会话和身份，'
     '不能证明玩家没改本地状态**'),
]

TOPO_RULE = [
    '🔑 **P2P、局域网和专用服务器是三套信任拓扑，'
    '不是同一种网络的三种名称**',
    '🔑 **P2P 仲裁者必须固定或按明确规则轮换**，'
    '**不能在延迟变化时静默更换**',
    '🔑 专用服务器与 P2P 应分别记录**回滚深度 · 预测错误率 · '
    '拒绝原因 · 权威来源**',
]

# 🔴 回滚分层
ROLLBACK_STEPS = [
    '回滚**确定性模拟状态**（位置 · 动画状态 · 冷却 · 资源 · 库存事务）',
    '**保留**玩家输入历史 · 未提交意图 · 录像游标',
    '重新模拟到最新**已确认输入**',
    '再重放**本地预测输入**',
    '**按语义决定特效**：命中粒子可能撤销 · 镜头抖动可能是真实感知反馈 · '
    '**UI 错误提示不应消失**',
]

ROLLBACK_RULE = [
    '🔴 **禁止"整客户端状态重置"**',
    '🔑 **保命技能 · 已确认位移 · 已同步给队友的社交状态不能一概回滚**',
    '🔴 **不能因服务端修正了位置，就把玩家刚输入的下一次跳跃也吞掉** —— '
    '这会制造"**输入丢失**"，并会**伪装成网络问题**',
]

# 🔴 命中四事件
HIT_FOUR = [
    '客户端**开火**',
    '客户端**预测命中**',
    '服务端**权威命中**',
    '**结果结算**',
]

HIT_RULE = [
    '🔴 **视觉命中与服务端未命中必须拆成四个独立事件**',
    '🔑 客户端可立即播**枪口 · 命中火花 · 受伤音**，但'
    '**数字 · 击杀数 · 任务计数 · 击杀回放 · 战后结算必须等权威结果**',
    '🔑 若服务端最终拒绝，命中火花可保留为"**擦伤感**"，但'
    '**必须明确它不是伤害**',
    '🔴 **不能先播完整击杀演出，再让尸体站起来**；'
    '也**不能静默取消演出**',
]

HIT_PREDICTED = '🔑 受击者端可先显示一次**无数值受伤反应**再纠正，'
'但该效果必须记为 `predicted_reaction`，'
'**不能复用 `confirmed_damage`**'

# 重放非同源
REPLAY_SOURCES = [
    ('**玩家观战**', '服务端状态快照通常足够，且能**隐藏战争迷雾和隐私**'),
    ('**服务端反作弊**', '可能需要**原始输入 · 时间戳 · 内存完整性 · '
     '资产哈希 · 设备上下文**'),
    ('**战斗回放**', '需要**足以确定性重演的精简事件**'),
    ('**竞技申诉**', '可能需要**服务端裁判事件流**'),
]

REPLAY_RULE = '🔑 **重放、观战、反作弊数据不是天然同源**'

# 🔴 设置六类
SETTINGS_SIX = [
    ('**纯呈现**', '字幕 · 色盲模式 · UI 缩放 · 背景音量',
     '否', '否'),
    ('**性能呈现**', '帧率上限 · 画质档 · 超分模式',
     '仅安全下限/上限', '否'),
    ('**控制意图**', '键位 · 摇杆曲线 · 死区 · 输入设备',
     '否', '通常否，**但宏和辅助瞄准例外**'),
    ('**辅助功能**', '自动奔跑 · 一键难度 · 时间减缓 · 眼动/开关设备',
     '通常不可强制', '**必须单独标注"可访问性"**'),
    ('**玩法影响**', '辅助瞄准强度 · 自动格挡 · 永久标记 · 资源提示',
     '竞技模式可限制', '是'),
    ('**账号上下文**', '语言 · 云同步 · 数据共享 · 摄像头权限',
     '否', '否'),
]

SETTINGS_FIELDS = [
    'ID', '显示名', '设备/平台', '默认值版本', '当前默认', '首启默认',
    '**原版默认**', '允许范围', '步长', '**是否影响比赛公平性**',
    '**是否影响成就**', '**是否影响录制合法性**', '是否影响云同步',
    '是否影响跨平台匹配', '迁移规则', '回滚规则', '测试覆盖状态',
]

SETTINGS_RULE = [
    '🔑 **设置不是单纯的个人偏好，而是一份有版本、有范围、'
    '有冲突后果的契约**',
    '🔴 只写 `default: true` **无法解释"恢复默认"恢复的是哪一个默认值**，'
    '也无法证明一次行为变化来自**功能修改、设备检测还是数值重调**',
    '🔑 设置字段必须**绑定数据版本和语义版本**，'
    '**避免只凭同名设置进行迁移**',
]

# 🔴 五义默认值
DEFAULT_FIVE = [
    ('**原版默认**', '原版游戏当时使用的默认值'),
    ('**首次启动默认**', '新玩家第一次进入时的初始配置'),
    ('**当前版本默认**', '本版新键名的默认'),
    ('**厂商预设**', '可能按设备或平台统一'),
    ('**安全默认**', '硬件异常/驱动崩溃/配置损坏后的恢复值'),
]

DEFAULT_RULE = [
    '🔴 **`reset to default` 至少有五义，必须分开**',
    '🔑 菜单至少显示"**恢复当前版本默认** · **保留原版语义** · '
    '**恢复首启配置**"',
    '🔑 若旧版不存在该设置，还应标 `default_origin: version_added`，'
    '**不能伪造一个"原版就有"的历史**',
]

# 迁移
MIGRATE_RULE = [
    '🔑 **设置迁移不是只保留未知字段**',
    '🔑 **删除项**要保留历史值并解释去向',
    '🔑 **重命名**要绑定 `previous_keys`，'
    '**防止新旧版本各自写同一状态**',
    '🔑 **改变值域**要记旧值如何映射',
    '🔑 **改变默认值**必须记旧默认是否沿用',
    '🔑 **改变语义时即使键名相同，也必须触发迁移**',
]

MIGRATE_FIELDS = [
    'schema_version', 'binary_version', 'build_id', 'platform_id',
    'input_device_family', 'last_written_by', 'last_migrated_at',
]

MIGRATE_READ = '🔑 读取时采用"**未知键保留 · 非法值修复 · '
'冲突键按版本拓扑解决**"，**不能清空整个配置文件**。'
'🔑 **可以丢弃设备专属重映射，但不能静默删除通用控制语义**'

# 未保存
UNSAVED_STATES = ['脏编辑', '已验证', '**写入失败**', '**等待重启**']

UNSAVED_RULE = [
    '🔑 **"设置未保存"必须成为独立状态，而不是靠退出按钮猜**',
    '🔑 编辑器、过场、加载和崩溃时可能退出 —— '
    '菜单必须区分 ' + ' · '.join(UNSAVED_STATES),
    '🔑 **重启才生效的设置要明确显示"需重启"**，'
    '并在**重启失败时提供撤销**',
    '🔑 **控制设备拔插导致的设置变更不得触发未保存提示**',
]

CONFLICTS = [
    '❌ **集中式 anti-cheat SDK 让"客户端可信模块决定玩法状态"**',
    '❌ **自动打补丁或静默状态纠正**（缺旧值/新值/原因三字段）',
    '❌ 把检测状态暴露给对手',
    '❌ 检测模块认为可疑就静默修改权威状态',
    '❌ 整客户端状态重置',
    '❌ **修正位置后吞掉刚输入的下一次跳跃**',
    '❌ **先播完整击杀演出再让尸体站起来**',
    '❌ 静默取消演出',
    '❌ 用 `predicted_reaction` 复用 `confirmed_damage`',
    '❌ 把 P2P/局域网/专用服务器当同一种网络',
    '❌ **延迟变化时静默更换 P2P 仲裁者**',
    '❌ **"默认最佳设置"自动覆盖用户选择**',
    '❌ **首次启动重置删除玩家历史**',
    '❌ **跨平台统一按钮图标而忽略设备语义**',
    '❌ **云同步直接用最后写入时间覆盖本地**',
    '❌ `reset to default` 只有一义',
    '❌ 伪造"原版就有"的设置历史',
    '❌ 清空整个配置文件',
]

FIELDS = [
    ('item_id', '项编号'),
    ('domain', '域（facts / accept / topo / rollback / hit / replay / '
               'settings / default / migrate / unsaved）'),
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


def cmd_facts(a):
    _hdr('🔴 client_claim_facts（**事实表**）')
    print(f'   {"事实":<22}{"可上报":<10}{"须复算":<14}视觉可先呈现')
    print('   ' + '-' * 74)
    for f, up, re_, vi, note in FACTS_TABLE:
        print(f'   {f:<22}{str(up):<10}{str(re_):<14}{str(vi)}')
        print(f'   {"":<22}→ {note}')
    print('\n规则:')
    for r in FACTS_RULE:
        print(f'   {r}')
    return 0


def cmd_accept(a):
    _hdr('服务端**接受条件**')
    print('每项验证: ' + ' · '.join(ACCEPT_CHECKS))
    print('\n规则:')
    for r in ACCEPT_RULE:
        print(f'   {r}')
    return 0


def cmd_topo(a):
    _hdr('🔴 三套信任拓扑')
    for k, why in TOPO_THREE:
        print(f'   {k:<14} {why}')
    print('\n规则:')
    for r in TOPO_RULE:
        print(f'   {r}')
    return 0


def cmd_rollback(a):
    _hdr('🔴 预测回滚（**分层**）')
    for i, s in enumerate(ROLLBACK_STEPS, 1):
        print(f'   {i}. {s}')
    print('\n规则:')
    for r in ROLLBACK_RULE:
        print(f'   {r}')
    return 0


def cmd_hit(a):
    _hdr('🔴 命中（**四个独立事件**）')
    for i, h in enumerate(HIT_FOUR, 1):
        print(f'   {i}. {h}')
    print('\n规则:')
    for r in HIT_RULE:
        print(f'   {r}')
    print(f'\n   {HIT_PREDICTED}')
    return 0


def cmd_replay(a):
    _hdr('重放 / 观战 / 反作弊（**非同源**）')
    for k, why in REPLAY_SOURCES:
        print(f'   {k:<18} {why}')
    print(f'\n   {REPLAY_RULE}')
    return 0


def cmd_settings(a):
    _hdr('🔴 设置（**六类副作用**）')
    print(f'   {"类型":<14}{"服务端强制":<12}{"公平审查":<10}示例')
    print('   ' + '-' * 74)
    for k, ex, force, fair in SETTINGS_SIX:
        print(f'   {k:<14}{force:<12}{fair:<10}{ex}')
    print('\n字段: ' + ' · '.join(SETTINGS_FIELDS))
    print('\n规则:')
    for r in SETTINGS_RULE:
        print(f'   {r}')
    return 0


def cmd_default(a):
    _hdr('🔴 五义默认值')
    for k, why in DEFAULT_FIVE:
        print(f'   {k:<16} {why}')
    print('\n规则:')
    for r in DEFAULT_RULE:
        print(f'   {r}')
    return 0


def cmd_migrate(a):
    _hdr('设置迁移')
    for r in MIGRATE_RULE:
        print(f'   {r}')
    print('\n保留字段: ' + ' · '.join(MIGRATE_FIELDS))
    print(f'\n   {MIGRATE_READ}')
    return 0


def cmd_unsaved(a):
    _hdr('"设置未保存"是独立状态')
    for r in UNSAVED_RULE:
        print(f'   {r}')
    return 0


def cmd_init(a):
    os.makedirs(os.path.dirname(a.init) or '.', exist_ok=True)
    with open(a.init, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow([k for k, _ in FIELDS])
        w.writerow(['TODO'] * len(FIELDS))
    print(f'已生成信任/设置表: {a.init}')
    print('\n⚠️ 十域：facts / accept / topo / rollback / hit / replay / '
          'settings / default / migrate / unsaved')
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
    print(f'信任/设置 · {len(rows)} 条')
    print('=' * 76)
    if mismatch:
        print(f'\n🚫 **不一致** {len(mismatch)} 条（行 {mismatch[:15]}）')
    if no_legacy:
        print(f'\n❌ {len(no_legacy)} 条缺**原版值**（行 {no_legacy[:15]}）')
    if no_grade:
        print(f'\n🚫 {len(no_grade)} 条**证据等级缺失或 ≥7 级**'
              f'（行 {no_grade[:15]}）')

    if not (mismatch or no_legacy or no_grade):
        print('\n✅ 信任/设置：一致、原版值完整、证据等级达标')

    print('\n🔑 **服务器信任的是具体事实，不是笼统的"客户端"。**')
    print('   **视觉先显示命中不构成权威事实；`reset to default` 有五义。**')
    return 1 if (a.gate_check and (mismatch or no_legacy or no_grade)) else 0


def main():
    ap = argparse.ArgumentParser(description='信任边界与玩家设置')
    ap.add_argument('--facts', action='store_true')
    ap.add_argument('--accept', action='store_true')
    ap.add_argument('--topo', action='store_true')
    ap.add_argument('--rollback', action='store_true')
    ap.add_argument('--hit', action='store_true')
    ap.add_argument('--replay', action='store_true')
    ap.add_argument('--settings', action='store_true')
    ap.add_argument('--default', action='store_true')
    ap.add_argument('--migrate', action='store_true')
    ap.add_argument('--unsaved', action='store_true')
    ap.add_argument('--init')
    ap.add_argument('--check')
    ap.add_argument('--gate-check', action='store_true')
    a = ap.parse_args()
    fns = {'facts': cmd_facts, 'accept': cmd_accept, 'topo': cmd_topo,
           'rollback': cmd_rollback, 'hit': cmd_hit, 'replay': cmd_replay,
           'settings': cmd_settings, 'default': cmd_default,
           'migrate': cmd_migrate, 'unsaved': cmd_unsaved}
    for k, fn in fns.items():
        if getattr(a, k):
            return fn(a)
    if a.init:
        return cmd_init(a)
    if a.check:
        return cmd_check(a)
    print('❌ 需要 --facts / --accept / --topo / --rollback / --hit / '
          '--replay / --settings / --default / --migrate / --unsaved / '
          '--init / --check 之一')
    return 2


if __name__ == '__main__':
    sys.exit(main())
