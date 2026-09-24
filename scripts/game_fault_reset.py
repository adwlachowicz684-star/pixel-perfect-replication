#!/usr/bin/env python3
"""容错撤销 + 物件状态复位（第二十九轮 C / D 类，含 E/F/G/H 补充）。

**🔑 C 类核心**：
> 🔑 **容错不是弹出确认框，而是明确后果 · 撤销成本 · 输入稳定性。**
> 🔑 **撤销窗口是可测的"延迟提交"，不是软删除。**
> 🔴 **默认"确定"会奖励连按；默认"取消"会在连败后让玩家
> 误以为没有重试** —— 正确做法是**逐操作测量原版焦点**。

**🔑 D 类核心**：
> 🔑 **复位不是"是否保存"，而是状态所有权和重置时钟。**
> 🔑 一扇门有四层：**对象存在 · 运行时状态 · 玩家知识 · 世界规则**。
> 🔴 只持久化"对象状态"会出现
> "**门保持开、敌人已重置、地图图标又合上**"的**三重矛盾**。

用法:
  game_fault_reset.py --confirm # 确认对话框**语义与焦点**
  game_fault_reset.py --undo    # 🔑 **撤销窗口**（延迟提交）
  game_fault_reset.py --guard   # 误触保护**与确认语义解耦**
  game_fault_reset.py --save    # 🔴 存档覆盖**最高风险操作**
  game_fault_reset.py --four    # 🔴 物件状态**四层**
  game_fault_reset.py --enum    # 对象状态**枚举**
  game_fault_reset.py --trigger # 复位触发**不能混成"读档即重置"**
  game_fault_reset.py --known   # 🔑 **已探索**与**已互动**两种持久性
  game_fault_reset.py --break   # 可破坏物**重建规则**
  game_fault_reset.py --schema  # 持久化**粒度绑定版本**
  game_fault_reset.py --efg     # E/F/G 类补充
  game_fault_reset.py --init ledger/fault_reset.csv
  game_fault_reset.py --check ledger/fault_reset.csv --gate

退出码: 0 通过 / 1 缺项 / 2 用法错误
"""
import argparse
import csv
import os
import sys

# 确认对话框
CONFIRM_FIELDS = [
    'operation_id', 'affected_entity', 'preconditions', 'postconditions',
    'cost', 'irreversible', 'visible_preview', 'preview_in_world',
    '**confirm_role**', '**cancel_role**', '**default_focus**',
    'focus_order', 'escape_action', 'back_action', 'click_outside_action',
    'rapid_click_guard', 'hold_to_confirm', 'controller_disconnect_policy',
    '**state_on_timeout**',
]

CONFIRM_MEASURE = [
    '菜单首次进入', '上一步返回', '**错误输入**', '**超时**', '**无输入**',
]

CONFIRM_RULE = [
    '🔑 **必须记录操作语义 · 按钮角色 · 焦点移动**，'
    '而不只是"有二次确认"',
    '🔑 手柄的"取消/返回"和"确认"**可能位于不同拇指位置**；'
    '键盘 `Enter` · 方向键 · 鼠标点击**也可能有不同首次聚焦**',
    '🔑 逐操作测量原版焦点 —— '
    '🔴 **正确做法不是统一"默认取消"**',
]

# 🔑 撤销窗口
UNDO_ITEMS = [
    '执行后立即生效还是进入 `**pending**`', '**窗口多长**',
    '**窗口计时由现实时间还是游戏时间**', '**暂停是否冻结**',
    '窗口内能否叠加同类操作', '**撤销后资源是否回到原位**',
    '撤销是否会触发音效/通知/成就', '**撤销本身能否再撤销**',
    '**断线或崩溃后是否自动提交**',
]

UNDO_RULE = [
    '🔑 **撤销窗口是可测的"延迟提交"，不是软删除**',
    '🔴 **若窗口为 0，应显式写 `undo_window_ms: 0` 而不是省略**',
    '🔴 **若原版没有撤销，也不应新增"贴心撤销"**',
]

# 误触保护
GUARD_ITEMS = [
    '最小按键间隔', '双击判定', '长按阈值', '连点上限', '摇杆中立死区',
    '手柄静止判定', '防抖窗口', '**输入队列满时的丢弃策略**',
    '**暂停时输入归属**', '控制切换时的按键锁定',
    '**菜单首次聚焦后的首次确认锁定**',
]

GUARD_RULE = '🔑 **误触保护必须与确认语义解耦**，否则会**误杀快速操作**'
GUARD_QUANTITY = '🔑 对"出售 1/10/全部"，要测每个按钮**是否共享长按** · '
'**是否可在数量滚动中取消** · **滚动停止多久后确认生效**'

# 🔴 存档覆盖
SAVE_FIELDS = [
    'slot', 'version', 'content_hash', 'playtime', 'location',
    'checkpoint_label', 'world_time', 'modified_files', '**backup_path**',
    '**overwrite_preview**', '**race_against_autosave**',
    '**power_loss_recovery**',
]

SAVE_RULE = [
    '🔑 **存档覆盖是最高风险操作**',
    '🔴 若原版覆盖前**只显示时间和地点**，复刻**不应擅自加入完整装备预览**',
    '🔑 若原版有临时的 `.bak`，则要测**崩溃后恢复顺序**',
]

# 🔴 物件四层
FOUR_LAYERS = [
    ('**对象存在**', '存在与位置（通常属场景）'),
    ('**运行时状态**', '开/关、锁定进度'),
    ('**玩家知识**', '是否已在地图上标为开启'),
    ('**世界规则**', '门后的敌人重置'),
]

FOUR_RULE = '🔴 若复刻**只持久化"对象状态"**，常出现'
'"**门保持开、敌人已重置、地图图标又合上**"的**三重矛盾** —— '
'正确做法是**为每层分别记 `save_scope` 与 `reset_trigger`**'

# 对象状态枚举
OBJ_ENUM = [
    '开/关', '破坏', '剩余耐久', '搜索次数', '掉落表抽取值', '内容已取',
    '**移动后的位置**', '旋转', '父节点', '附着物', '门禁权限', '开关状态',
    '光照', '可交互性', 'NPC 占有', '碰撞', '动画阶段', '物理唤醒状态',
    '可见性', '**迷雾**', '**地图标记**',
]

# 复位触发
RESET_TRIGGERS = [
    '区域卸载', '完全卸载', '读档', '退出至主菜单', '重启应用', '新游戏',
    '**新周目**', '**剧情阶段变化**', '季节/日期变化', '特定脚本调用',
    '玩家行为',
]

RESET_FIELDS = [
    'retained_triggers', 'reset_triggers', 'recreate_triggers',
]

RESET_RULE = [
    '🔑 **复位触发不能混成一个"读档即重置"**',
    '🔑 同一扇门在不同触发下可能**保留状态 · 恢复默认值 · 重新随机 · '
    '完全重建**',
    '🔴 **若原版不可达，应写 `unobservable`，不能填 `false`**',
]

# 🔑 两种持久性
KNOWN_SIX = [
    'fog_of_war', 'discovered_markers', 'fast_travel_memory',
    'journal_read', 'dialogue_seen', 'object_interaction_memory',
]

KNOWN_RULE = [
    '🔑 **"已探索"和"对象已互动"是两种持久性，不能共享同一字段**',
    '🔑 玩家死亡后**迷雾可以保留，而物件状态从检查点恢复**',
    '🔴 若原版地图标记**会随周目重建**，重制保留旧标记'
    '**就可能提前泄露路径**',
]

# 可破坏物
BREAK_STATES = [
    '永久破坏', '临时重建', '**同位置重建**', '**附近随机重建**',
    '仅在未完全摧毁时重建', '保留碎片但恢复可交互性',
    '**重建时保留已施加的脚本状态**',
]

# 持久化粒度
SCHEMA_FIELDS = [
    'schema_version', 'persisted_fields', 'derived_fields_excluded',
    'migration_handler', '**unknown_field_policy**',
    '**default_value_when_missing**', 'checksum', 'migrated_test_replay',
]

SCHEMA_RULE = [
    '🔑 **持久化粒度必须与迁移版本绑定**',
    '🔴 若旧存档缺新字段，必须区分"**原版未保存**"和"**值为默认值**"，'
    '**不能把所有缺失都回填原版默认值**',
]

# E/F/G
EFG = [
    ('**E 自定义四态**', '**原始值—显示值—可见值—审核值** 分开；'
     '名字长度 · 字符集 · 敏感词过滤 · 是否可重名 · '
     '**联机中他人看到什么**'),
    ('**F 极端显示**', '超长数值（伤害数字/金币/时间）· 极小极大字体 · '
     '**数字与单位在各语言下的排版** · '
     '进度条极值（接近满/接近空/**负值**）· 极端条目数下的滚动'),
    ('**G 回访体验**', '老玩家回旧区域（是否变化/是否有新内容）· '
     '**二周目/重玩的区域状态** · 长期不玩的回归（是否提示/是否重置引导）· '
     '**版本更新后的回访**（旧存档进新版本）'),
]

CONFLICTS = [
    '❌ 只记"有二次确认"',
    '❌ **统一"默认取消"**（应逐操作测原版焦点）',
    '❌ 撤销窗口为 0 却省略字段',
    '❌ **原版没有撤销却新增"贴心撤销"**',
    '❌ 误触保护与确认语义耦合（误杀快速操作）',
    '❌ 覆盖存档擅自加完整装备预览',
    '❌ **只持久化"对象状态"**（三重矛盾）',
    '❌ 复位触发混成"读档即重置"',
    '❌ **原版不可达却填 false**（应写 unobservable）',
    '❌ **已探索与已互动共享同一字段**',
    '❌ 周目重建地图标记却保留旧标记（泄露路径）',
    '❌ **把所有缺失字段回填原版默认值**',
]

FIELDS = [
    ('item_id', '项编号'),
    ('domain', '域（confirm / undo / guard / save / four / enum / trigger / '
               'known / break / schema / efg）'),
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


def cmd_confirm(a):
    _hdr('确认对话框（**语义与焦点**）')
    print('字段: ' + ' · '.join(CONFIRM_FIELDS))
    print('\n必须分别测: ' + ' · '.join(CONFIRM_MEASURE))
    print('\n规则:')
    for r in CONFIRM_RULE:
        print(f'   {r}')
    return 0


def cmd_undo(a):
    _hdr('🔑 撤销窗口（**延迟提交**）')
    for u in UNDO_ITEMS:
        print(f'   · {u}')
    print('\n规则:')
    for r in UNDO_RULE:
        print(f'   {r}')
    return 0


def cmd_guard(a):
    _hdr('误触保护（**与确认语义解耦**）')
    for g in GUARD_ITEMS:
        print(f'   · {g}')
    print(f'\n   {GUARD_RULE}')
    print(f'   {GUARD_QUANTITY}')
    return 0


def cmd_save(a):
    _hdr('🔴 存档覆盖（**最高风险操作**）')
    print('字段: ' + ' · '.join(SAVE_FIELDS))
    print('\n规则:')
    for r in SAVE_RULE:
        print(f'   {r}')
    return 0


def cmd_four(a):
    _hdr('🔴 物件状态（**四层**）')
    for k, why in FOUR_LAYERS:
        print(f'   {k:<16} {why}')
    print(f'\n   {FOUR_RULE}')
    return 0


def cmd_enum(a):
    _hdr('对象状态（**枚举**）')
    print('   ' + ' · '.join(OBJ_ENUM))
    return 0


def cmd_trigger(a):
    _hdr('复位触发（**不能混成"读档即重置"**）')
    print('触发种类: ' + ' · '.join(RESET_TRIGGERS))
    print('\n字段: ' + ' · '.join(RESET_FIELDS))
    print('\n规则:')
    for r in RESET_RULE:
        print(f'   {r}')
    return 0


def cmd_known(a):
    _hdr('🔑 两种持久性（**已探索 vs 已互动**）')
    print('字段: ' + ' · '.join(KNOWN_SIX))
    print('\n规则:')
    for r in KNOWN_RULE:
        print(f'   {r}')
    return 0


def cmd_break(a):
    _hdr('可破坏物（**重建规则**）')
    for b in BREAK_STATES:
        print(f'   · {b}')
    return 0


def cmd_schema(a):
    _hdr('持久化粒度（**绑定版本**）')
    print('字段: ' + ' · '.join(SCHEMA_FIELDS))
    print('\n规则:')
    for r in SCHEMA_RULE:
        print(f'   {r}')
    return 0


def cmd_efg(a):
    _hdr('E / F / G 类补充')
    for k, why in EFG:
        print(f'\n   【{k}】\n      {why}')
    return 0


def cmd_init(a):
    os.makedirs(os.path.dirname(a.init) or '.', exist_ok=True)
    with open(a.init, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow([k for k, _ in FIELDS])
        w.writerow(['TODO'] * len(FIELDS))
    print(f'已生成容错/复位表: {a.init}')
    print('\n⚠️ 十一域：confirm / undo / guard / save / four / enum / '
          'trigger / known / break / schema / efg')
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
    print(f'容错/复位 · {len(rows)} 条')
    print('=' * 76)
    if mismatch:
        print(f'\n🚫 **不一致** {len(mismatch)} 条（行 {mismatch[:15]}）')
    if no_legacy:
        print(f'\n❌ {len(no_legacy)} 条缺**原版值**（行 {no_legacy[:15]}）')
    if no_grade:
        print(f'\n🚫 {len(no_grade)} 条**证据等级缺失或 ≥7 级**'
              f'（行 {no_grade[:15]}）')

    if not (mismatch or no_legacy or no_grade):
        print('\n✅ 容错/复位：一致、原版值完整、证据等级达标')

    print('\n🔑 **容错不是确认框，是后果 · 撤销成本 · 输入稳定性。**')
    print('   **撤销窗口是延迟提交；为 0 要显式写，原版没有就别新增。**')
    print('   **"开过的箱子又合上了"是经典体验破坏 —— 四层状态要分开。**')
    return 1 if (a.gate_check and (mismatch or no_legacy or no_grade)) else 0


def main():
    ap = argparse.ArgumentParser(description='容错撤销与物件复位')
    ap.add_argument('--confirm', action='store_true')
    ap.add_argument('--undo', action='store_true')
    ap.add_argument('--guard', action='store_true')
    ap.add_argument('--save', action='store_true')
    ap.add_argument('--four', action='store_true')
    ap.add_argument('--enum', action='store_true')
    ap.add_argument('--trigger', action='store_true')
    ap.add_argument('--known', action='store_true')
    ap.add_argument('--break', dest='break_', action='store_true')
    ap.add_argument('--schema', action='store_true')
    ap.add_argument('--efg', action='store_true')
    ap.add_argument('--init')
    ap.add_argument('--check')
    ap.add_argument('--gate-check', action='store_true')
    a = ap.parse_args()
    fns = {'confirm': cmd_confirm, 'undo': cmd_undo, 'guard': cmd_guard,
           'save': cmd_save, 'four': cmd_four, 'enum': cmd_enum,
           'trigger': cmd_trigger, 'known': cmd_known, 'break_': cmd_break,
           'schema': cmd_schema, 'efg': cmd_efg}
    for k, fn in fns.items():
        if getattr(a, k):
            return fn(a)
    if a.init:
        return cmd_init(a)
    if a.check:
        return cmd_check(a)
    print('❌ 需要 --confirm / --undo / --guard / --save / --four / --enum / '
          '--trigger / --known / --break / --schema / --efg / --init / '
          '--check 之一')
    return 2


if __name__ == '__main__':
    sys.exit(main())
