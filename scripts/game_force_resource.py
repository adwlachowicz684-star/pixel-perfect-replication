#!/usr/bin/env python3
"""交互反作用力 + 资源与冷却语义 + 过场中断恢复（第二十三轮 C / D / G 类，
含 E 队伍与 F 软性禁止）。

**🔑 C 类核心**：
> 🔴 **"物理正确即手感正确"应列为冲突** ——
> 刚体稳定、质量与摩擦只是底层，**原版手感常来自人为曲线**。
> 🔴 **"推不动"有五态**，不是"完全静止"。

**🔑 D 类核心**：
> 🔴 **资源与冷却是"带版本的时间状态机"，不是数值表的一个字段。**
> 🔑 一个技能"**动画结束才冷却**"与"**按下即冷却**"，
> **数值完全相同也会产生明显节奏差**。

用法:
  game_force_resource.py --stall   # 🔴 "推不动"**五态**
  game_force_resource.py --weight  # 重量感**五通道**
  game_force_resource.py --push    # 可推性**状态机**（独立于移动语义）
  game_force_resource.py --cancel  # 门/拉杆**中途取消**三结果
  game_force_resource.py --res     # 🔴 资源**五语义层**
  game_force_resource.py --cd      # 🔴 冷却**起点**八候选
  game_force_resource.py --clock   # **四条时钟**
  game_force_resource.py --over    # 🔴 差一点**舍入合同**+溢出六义
  game_force_resource.py --recover # 恢复**窗口**非线性
  game_force_resource.py --gcd     # **公共冷却≠独立冷却≠动画锁**
  game_force_resource.py --cut     # 🔴 过场**阶段书签**
  game_force_resource.py --companion # 队伍**更聪明是偏离**
  game_force_resource.py --soft    # 🔴 软性禁止**六种表达**
  game_force_resource.py --init ledger/force_resource.csv
  game_force_resource.py --check ledger/force_resource.csv --gate

退出码: 0 通过 / 1 缺项 / 2 用法错误
"""
import argparse
import csv
import os
import sys

# 🔴 推不动五态
STALL_FIVE = [
    ('**零位移**', '完全静止'),
    ('**微颤**', '有微小抖动但无位移'),
    ('**弹性屈服**', '先形变再回弹'),
    ('**粘滑**', '断续滑移（stick-slip）'),
    ('**卡住**', '被几何卡死'),
]

STALL_RULE = [
    '🔴 **"推不动就完全静止"应列为冲突** —— 忽略微反馈',
    '🔴 **但反向"加入微位移"也必须有原版帧证据**',
    '🔑 新增字段 `stall_state` · `micro_motion_amplitude` · '
    '`deformation_curve`',
]

# 重量感五通道
WEIGHT_FIVE = [
    '**速度曲线**', '**音效**', '**震动**', '**相机**', '**形变（mesh）**',
]

WEIGHT_RULE = [
    '🔑 质量/惯性/摩擦是**配置**，手感要**分通道登记**',
    '🔴 **"统一刚体 API 替代逐对象曲线"应列为冲突** —— '
    '会**批量抹平重量差异**',
    '🔴 **"加抖动/形变显真实"也冲突** —— 未证原版存在就增加信息',
]

# 可推性状态机
PUSH_FSM = [
    'idle', 'winding', 'gripping', 'pushing', 'slipping', 'stalling',
    'releasing',
]

PUSH_RULE = [
    '🔑 **可推性的输入语义要独立于角色移动语义**',
    '🔑 分别记录**横向 · 纵向 · 斜向 · 高低差 · 地面摩擦 · 玩家朝向 · '
    '视角方向 · 输入设备死区**',
    '🔑 "轻推一下"要记**最小位移阈值 · 输入持续时间 · 首次响应帧 · '
    '是否受 fixed update 和时间缩放影响**',
    '🔑 这是"**装备切换耗时隐含依赖帧率**"的同类问题 —— '
    '**手感若绑物理步数而非输入时间，会在刷新率变化时漂移**',
]

# 中途取消
CANCEL_TRIGGERS = [
    '输入松开', '被另一侧碰撞', '被伤害打断', '镜头失去目标',
    '新交互抢占', '加载', '暂停',
]

CANCEL_THREE = [
    ('**rollback**', '回原位'),
    ('**hold**', '停在当前逻辑位置'),
    ('**commit_then_cancel**', '完成当前原子阶段后停'),
]

CANCEL_MORE = [
    '门关闭时**碰撞体何时启用**', '**判定盒何时启用**', '**声音何时触发**',
    '**NPC 能否穿过**', '**能否夹住玩家**',
    '**视觉 mesh 与逻辑门框是否同帧**',
]

# 🔴 资源五层
RES_FIVE = [
    '资源池**容量与当前值**',
    '**生成**（战斗/脱战 · 固定 tick · 动作 · 击杀 · 道具 · 恢复场）',
    '**消费**（按下 · commit · 结算 · 失败返还）',
    '**恢复时钟**（何时开始 · 何时停止 · 是否追赶）',
    '**溢出与保底**',
]

RES_VERSION_RULE = '🔑 资源重平衡时**旧存档按旧公式，新角色按新公式** —— '
'**不能只靠全局数值版本**'

# 🔴 冷却起点
CD_STARTS = [
    '输入 commit', '动画开始', '命中/释放事件', '弹道生成', '首次生效',
    '完整结算', '动画结束', '玩家松开',
]

CD_QUESTIONS = [
    '**失败释放是否进入冷却**',
    '**取消是否进入完整/缩短冷却**',
    '技能被**沉默/打断/死亡**是否清空',
    '**复活后保留还是重置**',
    '**切换装备/角色/场景**是否重置',
]

CD_RULE = '🔑 一个技能"**动画结束才冷却**"与"**按下即冷却**" —— '
'**数值完全相同也会产生明显节奏差**（改变连招窗口与公共冷却重叠）'

# 四条时钟
CLOCK_FOUR = [
    ('**real_time**', '真实时间'),
    ('**gameplay_time**', '玩法时间'),
    ('**ui_time**', 'UI 时间'),
    ('**animation_time**', '动画时间'),
]

CLOCK_RULE = [
    '🔑 每个资源与冷却**指定所属时钟**',
    '🔑 暂停白名单不能只写"暂停恢复继续" —— '
    '还要写**资源是否恢复 · 是否追赶 · 是否有最低 tick · '
    '断点与退出后的补偿**',
    '🔴 慢动作时若**输入采样率提高而资源时钟未同步** → '
    '玩家获得更多输入窗口却未增加资源，形成**无记录的手感变化**',
]

# 🔴 差一点与溢出六义
OVER_ROUND = [
    '比较是 `< cost` 还是 `<= cost`',
    '还是 `floor/ceil/round(value) >= cost`',
    '**资源显示值和权威值是否一致**',
]

OVER_EXAMPLE = '🔑 若显示 10、内部 9.6，差 0.4 能否释放**取决于取整时点**；'
'若显示 10、内部 10，但成本 10.01，结果又会不同'

OVER_SIX = [
    ('**floor_zero**', '负值截断到 0'),
    ('**no_overflow**', '截断到上限'),
    ('**negative_pool**', '允许借负'),
    ('**recovery_none**', '**不恢复必须显式写**'),
    ('**banked_overspend**', '允许透支但后续锁定'),
    ('**min_guarantee**', '**最小保底**（由"最小伤害保底 1 的位置"扩展）'),
]

# 恢复窗口
RECOVER_FIELDS = [
    'tick 间隔', '**首 tick 是否立即**', '**结束 tick 是否完整**',
    '暂停', '死亡', '对话', '过场', '菜单', '加载', '**技能释放中**',
    '**被控制状态**', '满池停止策略', '池子切换', '多人权威端',
]

RECOVER_NONLINEAR = [
    '阶梯阈值', '**战斗减半**', '**连续释放惩罚**', '满池后银行',
    '**越接近上限越慢**',
]

RECOVER_RULE = '🔑 验收应绘制 `resource over time`，**同时标注输入事件**；'
'**只看曲线面积会漏掉首 tick 和结束 tick**'

# GCD
GCD_THREE = [
    '**技能内部冷却**', '**全局公共冷却**', '**输入防抖**',
    '**动画 commit**', '**动作取消窗口**', '状态标记',
]

GCD_RULE = '🔑 若新引擎用"**冷却从 Timer 超时触发**"而原版用'
'"**状态阶段结束**" → **暂停/死亡/跳过阶段时顺序会错**'

CD_STRUCT = '🔑 冷却结构：`resource → ability → cost → preconditions → '
'commit_event → cooldown_clock → pause_scope → recovery_clock → '
'overflow → rollback`'

# 🔴 过场阶段书签
CUT_PHASES = [
    'preroll', 'input_lock', 'camera_transition', 'performance',
    'branching', 'simulation_effects', 'unbind', 'postroll',
    'committed_end',
]

CUT_SAVE = [
    'sequence time', '**phase**', '**已提交的事件**',
    '**待提交事件队列**', '演员绑定', '相机状态', '音频样本偏移',
    '物理 authoring', '**玩家输入缓冲**', '随机状态', '任务标记',
    '保存允许标志',
]

CUT_RULE = [
    '🔴 **过场必须保存比时间码更细的阶段书签**',
    '🔑 若只存当前播放秒数，读档后可能**重复获得物品 · 重复触发任务 · '
    '错过同时发生的世界模拟 · 或停在相机未归还阶段**',
]

CUT_INTERRUPT = [
    '断线', '低电量', '切后台', '来电', '崩溃', '内存不足', '热更新',
    '快速旅行', '玩家跳过',
]

CUT_ACTIONS = [
    'replay', 'resume', 'commit pending', 'rollback', 'save checkpoint',
    '**显示恢复提示**',
]

CUT_RULE2 = [
    '🔑 **系统打断后的默认不应是重头播放，也不应是静默续播**',
    '🔑 关键过场要记"**已发生不可撤销**"与"**可安全重放**"的事件边界 —— '
    '否则**重放会重复奖励，跳过又可能漏掉状态**',
]

# 队伍
COMPANION_FIELDS = [
    '距离弧', '目标选择', '视线', '避让', '**门/陷阱行为**',
    '**指令响应**', '离队/死亡', '**保存身份**',
]

COMPANION_RULE = [
    '🔴 **"更聪明的 AI 是升级"理念冲突** —— '
    '对复刻而言，**智能是待测量，不是改进方向**',
    '🔑 要跑**"伙伴更聪明"反事实**：关闭陷阱感知 · 让伙伴等待 · '
    '让伙伴独立探索，验证**原版路线是否依赖其"恰好不那么聪明"**',
]

COMPANION_CONFLICTS = [
    '❌ 群体避让越平滑越好（可能永远无法贴近玩家）',
    '❌ **伙伴共享玩家全部感知**（破坏信息差）',
    '❌ **自动避陷阱**（可能改潜行/任务设计）',
    '❌ **伙伴死亡后对象立即销毁**（可能清掉任务或叙事状态）',
    '❌ 统一跟随速度（忽略距离弧和战斗迟滞）',
]

# 🔴 软性禁止六种
SOFT_SIX = [
    ('**视觉阻断**', '光 · 雾 · 门 · 墙 · 相机'),
    ('**声音引导**', 'NPC 警告 · 敌人声 · 音乐'),
    ('**AI 引导**', '敌人站位 · 巡逻方向 · 掉落诱饵'),
    ('**规则阻断**', '消耗品 · 装备 · 任务状态'),
    ('**叙事阻断**', '对白 · 环境叙事'),
    ('**失败后果**', '掉落 · 伤害 · 重置'),
]

SOFT_RULE = [
    '🔑 隐形墙五语义覆盖**硬边界**，本项补充**软边界** —— '
    '**它不阻止移动，而是改变玩家对成本和收益的估计**',
    '🔑 应记玩家**第一次接近 · 第二次接近 · 即将越过 · 已经越界**'
    '分别看到什么：是**信息渐增 · 持续沉默 · 还是一次性警告**',
    '🔴 **"玩家不应迷路所以加导航标记"冲突** · '
    '**"越界必传送"冲突** · **"所有禁止都该有统一 UI"冲突**',
]

SOFT_NARRATIVE = [
    '记录**说话者身份**', '是否主角自言自语',
    '**是否可被静音/字幕设置影响**', '能否打断', '是否重复',
    '**是否依赖任务阶段**',
]

SOFT_NOTE = '🔴 若原版沉默是故意，复刻加入提示**可能反而制造'
'"系统允许/不允许"的歧义**；反之原版若用**危险台词作为唯一警告**，'
'新引擎只做 HUD 高亮会**漏掉听觉玩家**'

CONFLICTS = [
    '❌ **"物理正确即手感正确"**',
    '❌ **"推不动就完全静止"**',
    '❌ 未证原版存在就加抖动/形变',
    '❌ **统一刚体 API 替代逐对象曲线**',
    '❌ 碰撞开始/结束播音效（无法表达卡住/屈服/持续滑动）',
    '❌ 冷却只写"使用后"',
    '❌ 资源只靠全局数值版本',
    '❌ **慢动作提高采样率却不同步资源时钟**',
    '❌ 只看恢复曲线面积（漏首 tick/结束 tick）',
    '❌ 用 Timer 超时替代状态阶段结束',
    '❌ **过场只存播放秒数**',
    '❌ **打断后重头播放或静默续播**',
    '❌ 伙伴"更聪明"',
    '❌ **越界必传送** / 所有禁止统一 UI',
]

FIELDS = [
    ('item_id', '项编号'),
    ('domain', '域（stall / weight / push / cancel / res / cd / clock / '
               'over / recover / gcd / cut / companion / soft）'),
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


def cmd_stall(a):
    _hdr('🔴 "推不动"五态')
    for k, why in STALL_FIVE:
        print(f'   {k:<16} {why}')
    print('\n规则:')
    for r in STALL_RULE:
        print(f'   {r}')
    return 0


def cmd_weight(a):
    _hdr('重量感（**五通道**）')
    for w in WEIGHT_FIVE:
        print(f'   · {w}')
    print('\n规则:')
    for r in WEIGHT_RULE:
        print(f'   {r}')
    return 0


def cmd_push(a):
    _hdr('可推性状态机（**独立于移动语义**）')
    print(' → '.join(PUSH_FSM))
    print('\n规则:')
    for r in PUSH_RULE:
        print(f'   {r}')
    return 0


def cmd_cancel(a):
    _hdr('门/拉杆（**中途取消**）')
    print('触发: ' + ' · '.join(CANCEL_TRIGGERS))
    print('\n三结果:')
    for k, why in CANCEL_THREE:
        print(f'   {k:<24} {why}')
    print('\n还要记: ' + ' · '.join(CANCEL_MORE))
    return 0


def cmd_res(a):
    _hdr('🔴 资源（**五语义层**）')
    for i, r in enumerate(RES_FIVE, 1):
        print(f'   {i}. {r}')
    print(f'\n   {RES_VERSION_RULE}')
    return 0


def cmd_cd(a):
    _hdr('🔴 冷却起点（**八候选**）')
    for s in CD_STARTS:
        print(f'   · {s}')
    print('\n还要回答:')
    for q in CD_QUESTIONS:
        print(f'   · {q}')
    print(f'\n   {CD_RULE}')
    print(f'\n   {CD_STRUCT}')
    return 0


def cmd_clock(a):
    _hdr('四条时钟')
    for k, why in CLOCK_FOUR:
        print(f'   {k:<20} {why}')
    print('\n规则:')
    for r in CLOCK_RULE:
        print(f'   {r}')
    return 0


def cmd_over(a):
    _hdr('🔴 差一点（**舍入合同**）与溢出六义')
    for r in OVER_ROUND:
        print(f'   · {r}')
    print(f'\n   {OVER_EXAMPLE}')
    print('\n溢出六义:')
    for k, why in OVER_SIX:
        print(f'   {k:<22} {why}')
    return 0


def cmd_recover(a):
    _hdr('恢复（**窗口**而非每秒值）')
    print('字段: ' + ' · '.join(RECOVER_FIELDS))
    print('\n非线性: ' + ' · '.join(RECOVER_NONLINEAR))
    print(f'\n   {RECOVER_RULE}')
    return 0


def cmd_gcd(a):
    _hdr('公共冷却 ≠ 独立冷却 ≠ 动画锁')
    for g in GCD_THREE:
        print(f'   · {g}')
    print(f'\n   {GCD_RULE}')
    return 0


def cmd_cut(a):
    _hdr('🔴 过场（**阶段书签**）')
    print(' → '.join(CUT_PHASES))
    print('\n保存项: ' + ' · '.join(CUT_SAVE))
    print('\n规则:')
    for r in CUT_RULE:
        print(f'   {r}')
    print('\n打断类型: ' + ' · '.join(CUT_INTERRUPT))
    print('\n处置: ' + ' · '.join(CUT_ACTIONS))
    print('\n规则:')
    for r in CUT_RULE2:
        print(f'   {r}')
    return 0


def cmd_companion(a):
    _hdr('队伍 / 伙伴（**更聪明是偏离**）')
    print('字段: ' + ' · '.join(COMPANION_FIELDS))
    print('\n规则:')
    for r in COMPANION_RULE:
        print(f'   {r}')
    print('\n冲突:')
    for c in COMPANION_CONFLICTS:
        print(f'   {c}')
    return 0


def cmd_soft(a):
    _hdr('🔴 软性禁止（**六种表达**）')
    for k, why in SOFT_SIX:
        print(f'   {k:<14} {why}')
    print('\n规则:')
    for r in SOFT_RULE:
        print(f'   {r}')
    print('\n叙事性禁止: ' + ' · '.join(SOFT_NARRATIVE))
    print(f'\n   {SOFT_NOTE}')
    return 0


def cmd_init(a):
    os.makedirs(os.path.dirname(a.init) or '.', exist_ok=True)
    with open(a.init, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow([k for k, _ in FIELDS])
        w.writerow(['TODO'] * len(FIELDS))
    print(f'已生成交互/资源表: {a.init}')
    print('\n⚠️ 十三域：stall / weight / push / cancel / res / cd / clock / '
          'over / recover / gcd / cut / companion / soft')
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
    print(f'交互/资源 · {len(rows)} 条')
    print('=' * 76)
    if mismatch:
        print(f'\n🚫 **不一致** {len(mismatch)} 条（行 {mismatch[:15]}）')
    if no_legacy:
        print(f'\n❌ {len(no_legacy)} 条缺**原版值**（行 {no_legacy[:15]}）')
    if no_grade:
        print(f'\n🚫 {len(no_grade)} 条**证据等级缺失或 ≥7 级**'
              f'（行 {no_grade[:15]}）')

    if not (mismatch or no_legacy or no_grade):
        print('\n✅ 交互/资源：一致、原版值完整、证据等级达标')

    print('\n🔑 **物理正确 ≠ 手感正确；"推不动"有五态。**')
    print('   **"动画结束才冷却"与"按下即冷却"数值相同也差节奏。**')
    print('   **过场要存阶段书签，不是播放秒数。**')
    return 1 if (a.gate_check and (mismatch or no_legacy or no_grade)) else 0


def main():
    ap = argparse.ArgumentParser(description='交互反作用力与资源冷却')
    ap.add_argument('--stall', action='store_true')
    ap.add_argument('--weight', action='store_true')
    ap.add_argument('--push', action='store_true')
    ap.add_argument('--cancel', action='store_true')
    ap.add_argument('--res', action='store_true')
    ap.add_argument('--cd', action='store_true')
    ap.add_argument('--clock', action='store_true')
    ap.add_argument('--over', action='store_true')
    ap.add_argument('--recover', action='store_true')
    ap.add_argument('--gcd', action='store_true')
    ap.add_argument('--cut', action='store_true')
    ap.add_argument('--companion', action='store_true')
    ap.add_argument('--soft', action='store_true')
    ap.add_argument('--init')
    ap.add_argument('--check')
    ap.add_argument('--gate-check', action='store_true')
    a = ap.parse_args()
    fns = {'stall': cmd_stall, 'weight': cmd_weight, 'push': cmd_push,
           'cancel': cmd_cancel, 'res': cmd_res, 'cd': cmd_cd,
           'clock': cmd_clock, 'over': cmd_over, 'recover': cmd_recover,
           'gcd': cmd_gcd, 'cut': cmd_cut, 'companion': cmd_companion,
           'soft': cmd_soft}
    for k, fn in fns.items():
        if getattr(a, k):
            return fn(a)
    if a.init:
        return cmd_init(a)
    if a.check:
        return cmd_check(a)
    print('❌ 需要 --stall / --weight / --push / --cancel / --res / --cd / '
          '--clock / --over / --recover / --gcd / --cut / --companion / '
          '--soft / --init / --check 之一')
    return 2


if __name__ == '__main__':
    sys.exit(main())
