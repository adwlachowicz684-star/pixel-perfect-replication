#!/usr/bin/env python3
"""帧预算分配 + 输入意图层 + 死亡分类（第二十四轮 C / D / G 类，
含 E 内容变体与 F 存档可检查性）。

**🔑 C 类核心**：
> 🔴 **帧预算不是一个数，而是硬预算、弹性预算和借还状态的结合。**
> 🔑 **降级档位解决的是设备层级，不能代替逐帧仲裁。**
> 🔴 **平均帧率相同，分配不同 = 手感完全不同。**

**🔑 D 类核心**：
> 🔑 **意图是玩家想让世界发生什么，输入设备只负责触发意图。**
> 🔴 **意图层必须新增自己的稳定排序键** ——
> 不能从 Action 集合顺序或绑定列表顺序推导。

用法:
  game_budget_intent.py --budget  # 🔴 预算**八字段**
  game_budget_intent.py --arbiter # 跨系统**资源仲裁器**
  game_budget_intent.py --report  # 帧报告**16 项**
  game_budget_intent.py --intent  # 🔴 五层**分层表**
  game_budget_intent.py --equiv   # 设备**语义等价但非无条件**
  game_budget_intent.py --life    # 意图**生命周期九态**
  game_budget_intent.py --variant # 🔴 内容**变体**不能被统一
  game_budget_intent.py --inspect # 存档**可检查性**
  game_budget_intent.py --death   # 🔴 死亡**四类**
  game_budget_intent.py --init ledger/budget_intent.csv
  game_budget_intent.py --check ledger/budget_intent.csv --gate

退出码: 0 通过 / 1 缺项 / 2 用法错误
"""
import argparse
import csv
import os
import sys

# 🔴 预算八字段
BUDGET_FIELDS = [
    '**budget_ms**', '**elasticity_ms**', '**debt_ms**', 'priority',
    'can_defer', '**must_complete_this_frame**',
    '**affects_input_latency**', '**determinism_class**',
]

BUDGET_RULE = [
    '🔑 物理 · 动画 · AI · 粒子 · UI · 音频 · 网络读取 · 资源流送 · '
    '脚本 · 渲染**各自先声明需求**，再由仲裁器分配',
    '🔑 若一帧只有 16.67ms 总预算，**不等于每个子系统都能获得固定份额**',
    '🔑 屏幕外动画可以减少，**网络反序列化不能无限延后**，'
    '**音频混音与提交还受硬件周期约束**',
]

# 🔴 仲裁器
ARB_FOUR = [
    ('**CPU**', '按关键路径 · 工作线程数 · cache locality 排序'),
    ('**GPU**', '按提交顺序 · 异步队列 · tile/barrier · 反馈机制'),
    ('**带宽**', '按流式优先级和缓存污染成本'),
    ('**IO**', '按必须帧和后续预测需求'),
]

ARB_RULE = [
    '🔑 CPU、GPU、内存带宽、显存和 IO **不能同时"各自以为还有余量"**',
    '🔴 **同一资源不能同时被两个子系统按各自预算占用**',
    '🔑 仲裁结果要写入帧报告，**不能只写"GPU 瓶颈"**',
]

# 帧报告 16 项
REPORT_FIELDS = [
    'frame_index', 'wall_time', 'sim_time', '**input_sample_count**',
    'rollback_count', 'prediction_error_bits', 'physics_steps',
    'animation_quality_level', 'ai_budget_granted',
    '**particle_emissions_capped**', 'audio_mixing_late',
    'render_pass_dropped', 'gpu_marker', '**debt_before**',
    '**debt_after**', 'reconciliation_late', 'determinism_mode',
]

REPORT_RULE = '🔑 帧报告必须能**重建玩家体感**，而不是只提供性能曲线 —— '
'这样才能区分"**平均 60 帧**"与"**输入采样被吞一帧 · '
'动画借债后表现不一致**"'

# 🔴 五层
LAYER_FIVE = [
    ('**硬件事件**', '设备 · 控件 · 电平/位移 · 时间戳 · 扫描码/原始轴',
     '游戏语义', '去抖 · 轮询 · 热插拔 · NKRO · 回中'),
    ('**映射层**', '控件→原始动作 · 模式 · 死区 · 曲线 · 设备族',
     '是否允许跳、能否瞄准', '同键双义 · 模式切换 · 触屏坐标'),
    ('**意图层**', 'intent_id · 优先级 · 阶段 · 上下文 · 有效窗口 · 目标槽位',
     '**是键盘还是手柄、死区曲线**',
     '语义等价 · 冲突 · 超时 · 撤销'),
    ('**仲裁层**', '**稳定排序键** · 互斥规则 · 缓冲区 · committed 点',
     '设备事件原始时间', '同帧多意图 · 输入丢失 · 重放一致'),
    ('**模拟层**', '能否执行 · 消耗资源 · 产生事件',
     '玩家"想不想"', '条件变化 · 服务端拒绝 · 预测回滚'),
]

INTENT_RULE = [
    '🔑 **意图层必须只表达"想要什么"，设备映射只能解释"怎样触发"**',
    '🔴 官方文档明确**同一帧多个 Action 的报告顺序未定义** —— '
    '若复刻依赖"跳跃和攻击同帧时哪一个先响应"，'
    '**不能把设备上报顺序当成仲裁结果**',
    '🔴 **意图层必须新增自己的稳定排序键**',
]

# 设备等价
EQUIV_RULE = [
    '🔑 **同一意图在不同设备间应尽量语义等价，但不能无条件等价**',
    '🔑 "轻击""确认""返回""瞄准""连续移动""长按""双段输入"'
    '在不同设备上可能由**单击 · 长按 · 径向菜单 · 眼动 dwell · '
    '语音命令 · 开关扫描**触发',
]

EQUIV_NOTES = [
    '**触屏**可能只有触摸坐标，**没有 hover**',
    '**眼动**可提供注视点，但**没有传统按键**',
    '**单键扫描**必须逐个确认',
    '**语音**带来识别置信度 · 误唤醒 · 延迟',
]

EQUIV_RULE2 = '🔴 **语音和眼动结果应进入"候选意图"，不是 `committed` 意图**；'
'**开关扫描确认后才提交**'

# 生命周期九态
LIFE_NINE = [
    ('**generated**', '设备事件已形成原始动作'),
    ('**submitted**', '进入上下文允许的缓冲'),
    ('**committed**', '在定义明确的采样点被系统读取'),
    ('**executing**', '模拟开始'),
    ('**completed**', '契约结束'),
    ('**superseded**', '被更高优先级意图替代'),
    ('**rejected**', '上下文条件不成立'),
    ('**expired**', '窗口结束'),
    ('**lost**', '设备失效或仲裁没有归属'),
]

LIFE_RULE = [
    '🔑 这些状态**不能只写成布尔值**',
    '🔑 **尤其 `expired ≠ failed`**：**超时不应扣分**，'
    '**拒绝则可能需要提示**',
]

# 🔴 内容变体
VARIANT_FIELDS = [
    '**内容坐标**', '**版本依赖**', '**切换边界**',
    '**成就与存档影响表**',
]

VARIANT_KINDS = [
    '**区域/平台/分级变体**（日版美版差异）',
    '**同一内容在不同版本间的差异**（补丁前后）',
    '**重制版"新增内容"与原内容的边界**',
    '**玩家可选的内容变体**（如"经典模式"）',
]

VARIANT_RULE = [
    '🔴 **重制常"统一"变体，等于删除内容**',
    '🔑 要记**变体切换是否影响存档、成就、进度**',
    '🔴 **兼容性模式不能被当成图形选项**',
]

# 存档可检查性
INSPECT_RULE = [
    '🔑 **玩家能否"看到"自己的存档状态**：进度 · 统计 · 成就明细',
    '🔑 **存档的"自证"能力**：能否验证未损坏/未作弊',
    '🔑 **统计数据的口径**：游戏时间**是否含暂停/菜单**',
    '🔑 **导出/分享/截图**能力是否属于功能',
    '🔑 **云存档/本地存档的可见性差异**',
    '🔴 **不能把"存档校验"简化成 CRC**',
]

INSPECT_FIELDS = [
    '统计 schema', '**用户可见证明**', '导出/分享权限',
    '**云/本地差异表**', '统计口径声明',
]

# 🔴 死亡四类
DEATH_FOUR = [
    ('**玩家失败**', '操作失误导致'),
    ('**角色死亡**', '世界内的角色状态'),
    ('**剧情必需失败**', '**假失败**：剧情失败但继续'),
    ('**世界状态变化**', '死亡后世界的记忆与推进'),
]

DEATH_RULE = [
    '🔴 **死亡必须分成玩家失败 · 角色失败 · 剧情失败，不能共用一个状态**',
    '🔑 **角色死亡后世界的"记忆"**：**NPC 是否记得**',
    '🔑 **重试时哪些是"同一世界"哪些是"重置"**',
    '🔑 **失败后的叙事衔接**：对话是否变化',
    '🔑 **"假失败"（剧情失败但继续）与真失败必须区分**',
    '🔴 **重制常把失败做成纯机制，丢掉叙事层**',
]

CONFLICTS = [
    '❌ **只保留平均/百分位帧率而不保存子系统时间轴**',
    '❌ **动态降级不可重现**',
    '❌ **关闭子系统后跳过其事件队列**（输入/动画/音频缺帧）',
    '❌ 帧预算只有一个毫秒总数',
    '❌ 降档代替逐帧仲裁',
    '❌ **把设备上报顺序当仲裁结果**',
    '❌ 意图层携带设备专属映射',
    '❌ **语音/眼动直接作 committed 意图**',
    '❌ 意图状态只写布尔值',
    '❌ **统一内容变体**（= 静默删除内容）',
    '❌ 兼容性模式当图形选项',
    '❌ **存档校验简化成 CRC**',
    '❌ 死亡界面只剩单一机制状态',
]

FIELDS = [
    ('item_id', '项编号'),
    ('domain', '域（budget / arbiter / report / intent / equiv / life / '
               'variant / inspect / death）'),
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


def cmd_budget(a):
    _hdr('🔴 帧预算（**八字段**）')
    for f in BUDGET_FIELDS:
        print(f'   · {f}')
    print('\n规则:')
    for r in BUDGET_RULE:
        print(f'   {r}')
    return 0


def cmd_arbiter(a):
    _hdr('🔴 跨系统资源仲裁器')
    for k, why in ARB_FOUR:
        print(f'   {k:<10} {why}')
    print('\n规则:')
    for r in ARB_RULE:
        print(f'   {r}')
    return 0


def cmd_report(a):
    _hdr('帧报告（**16 项**）')
    for f in REPORT_FIELDS:
        print(f'   · {f}')
    print(f'\n   {REPORT_RULE}')
    return 0


def cmd_intent(a):
    _hdr('🔴 输入五层（**意图层**）')
    print(f'   {"层":<12}{"保存":<34}{"不应保存"}')
    print('   ' + '-' * 74)
    for k, save, notsave, test in LAYER_FIVE:
        print(f'   {k:<12}{save:<34}{notsave}')
        print(f'   {"":<12}→ 测试重点: {test}')
    print('\n规则:')
    for r in INTENT_RULE:
        print(f'   {r}')
    return 0


def cmd_equiv(a):
    _hdr('设备语义等价（**非无条件**）')
    for r in EQUIV_RULE:
        print(f'   {r}')
    print('\n各设备限制:')
    for n in EQUIV_NOTES:
        print(f'   · {n}')
    print(f'\n   {EQUIV_RULE2}')
    return 0


def cmd_life(a):
    _hdr('意图生命周期（**九态**）')
    for k, why in LIFE_NINE:
        print(f'   {k:<16} {why}')
    print('\n规则:')
    for r in LIFE_RULE:
        print(f'   {r}')
    return 0


def cmd_variant(a):
    _hdr('🔴 内容变体（**不能被统一**）')
    for v in VARIANT_KINDS:
        print(f'   · {v}')
    print('\n字段: ' + ' · '.join(VARIANT_FIELDS))
    print('\n规则:')
    for r in VARIANT_RULE:
        print(f'   {r}')
    return 0


def cmd_inspect(a):
    _hdr('存档可检查性')
    for r in INSPECT_RULE:
        print(f'   {r}')
    print('\n字段: ' + ' · '.join(INSPECT_FIELDS))
    return 0


def cmd_death(a):
    _hdr('🔴 死亡（**四类**）')
    for k, why in DEATH_FOUR:
        print(f'   {k:<16} {why}')
    print('\n规则:')
    for r in DEATH_RULE:
        print(f'   {r}')
    return 0


def cmd_init(a):
    os.makedirs(os.path.dirname(a.init) or '.', exist_ok=True)
    with open(a.init, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow([k for k, _ in FIELDS])
        w.writerow(['TODO'] * len(FIELDS))
    print(f'已生成预算/意图表: {a.init}')
    print('\n⚠️ 九域：budget / arbiter / report / intent / equiv / life / '
          'variant / inspect / death')
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
    print(f'预算/意图 · {len(rows)} 条')
    print('=' * 76)
    if mismatch:
        print(f'\n🚫 **不一致** {len(mismatch)} 条（行 {mismatch[:15]}）')
    if no_legacy:
        print(f'\n❌ {len(no_legacy)} 条缺**原版值**（行 {no_legacy[:15]}）')
    if no_grade:
        print(f'\n🚫 {len(no_grade)} 条**证据等级缺失或 ≥7 级**'
              f'（行 {no_grade[:15]}）')

    if not (mismatch or no_legacy or no_grade):
        print('\n✅ 预算/意图：一致、原版值完整、证据等级达标')

    print('\n🔑 **平均帧率相同，分配不同 = 手感完全不同。**')
    print('   **意图层必须自带稳定排序键；语音/眼动是候选不是 committed。**')
    print('   **死亡要分四类；"统一内容变体"等于静默删除内容。**')
    return 1 if (a.gate_check and (mismatch or no_legacy or no_grade)) else 0


def main():
    ap = argparse.ArgumentParser(description='帧预算与输入意图')
    ap.add_argument('--budget', action='store_true')
    ap.add_argument('--arbiter', action='store_true')
    ap.add_argument('--report', action='store_true')
    ap.add_argument('--intent', action='store_true')
    ap.add_argument('--equiv', action='store_true')
    ap.add_argument('--life', action='store_true')
    ap.add_argument('--variant', action='store_true')
    ap.add_argument('--inspect', action='store_true')
    ap.add_argument('--death', action='store_true')
    ap.add_argument('--init')
    ap.add_argument('--check')
    ap.add_argument('--gate-check', action='store_true')
    a = ap.parse_args()
    fns = {'budget': cmd_budget, 'arbiter': cmd_arbiter,
           'report': cmd_report, 'intent': cmd_intent, 'equiv': cmd_equiv,
           'life': cmd_life, 'variant': cmd_variant, 'inspect': cmd_inspect,
           'death': cmd_death}
    for k, fn in fns.items():
        if getattr(a, k):
            return fn(a)
    if a.init:
        return cmd_init(a)
    if a.check:
        return cmd_check(a)
    print('❌ 需要 --budget / --arbiter / --report / --intent / --equiv / '
          '--life / --variant / --inspect / --death / --init / --check 之一')
    return 2


if __name__ == '__main__':
    sys.exit(main())
