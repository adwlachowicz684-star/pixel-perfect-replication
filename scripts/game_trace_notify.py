#!/usr/bin/env python3
"""持久痕迹 + 通知聚合语义（第二十五轮 A / B 类）。

**🔑 A 类核心**：
> 🔴 **痕迹不是贴图，而是带生命周期的世界事实。**
> 🔴 **预算不是性能参数，而是玩法参数。**
> 🔑 渲染代理可以消失，但"**血迹曾在此、敌人曾经过**"的**事实不能消失**。

**🔑 B 类核心**：
> 🔑 **通知系统的问题不是显示，而是事件账本。**
> 🔴 **拾取 5 个药水，原版可能显示"×5"、也可能 5 条、
> 还可能先 3 条后刷新为 5 条 —— 三者都可能是正确，必须抓帧判定。**
> 🔴 **绝不能默认"统一成一个 toast"。**

用法:
  game_trace_notify.py --trace   # 🔴 痕迹**八组**
  game_trace_notify.py --budget  # 🔴 预算**14 字段**
  game_trace_notify.py --load    # 🔴 读档**四答案**（混用即 BUG）
  game_trace_notify.py --gen     # 痕迹与**生成世界**双重身份
  game_trace_notify.py --notify  # 🔴 事实层 / 表现层**分离**
  game_trace_notify.py --merge   # **四把合并键**
  game_trace_notify.py --window  # 合并**窗口模式**
  game_trace_notify.py --prio    # **优先级双值化**
  game_trace_notify.py --overflow # **队列溢出八策略**
  game_trace_notify.py --fatigue # **消息疲劳**是可测规则
  game_trace_notify.py --init ledger/trace_notify.csv
  game_trace_notify.py --check ledger/trace_notify.csv --gate

退出码: 0 通过 / 1 缺项 / 2 用法错误
"""
import argparse
import csv
import os
import sys

# 🔴 痕迹八组
TRACE_EIGHT = [
    ('**静态痕迹**', '弹孔 · 血迹 · 烧痕 · 涂鸦 · 碎屑'),
    ('**动态介质**', '草地弯曲 · 雪地脚印 · 积水波纹 · 灰尘'),
    ('**残骸**', '尸体 · 破碎物 · 弹壳 · 遗落道具'),
    ('**空间改变**', '破坏 · 门洞 · 倒塌 · 可重建物'),
    ('**玩家标记**', '地图标记 · 日志 · 涂写 · 旗帜'),
    ('**模拟记录**', '脚步声 · 血腥味 · 枪声证据 · 线索'),
    ('**叙事残留**', '尸体摆放 · 血字 · 摆拍 · 爆炸焦痕'),
    ('**保存状态**', '已写盘 · 仅会话内 · 关联实体 · 由规则重生'),
]

TRACE_EACH = [
    '半径', '深度/角度', '材质白名单', '法线容差', '**同点合并**',
    '**最大密度**', '**离开后寿命**', '**离开渲染距离是否保留**',
    '**卸载区域是否保留**', '**重启后是否保留**', '**读档后保留到哪一版本**',
]

TRACE_FIELDS = [
    '**稳定身份**', '世界坐标或宿主实体', '来源事实', '产生时刻',
    '生效时刻', '材质/表面亲和', '可见性', '**玩法响应**', '衰减策略',
    '保存策略', '清理策略',
]

TRACE_RULE = [
    '🔑 只记录"贴花资源名＋坐标"会丢掉三个根本问题：'
    '**同一枪是否连续 · 是否还能被怪物发现 · 读档后该痕迹是否存在**',
]

# 🔴 预算
BUDGET_FIELDS = [
    'trace_type', 'surface', '**max_count**', 'ring_or_lru',
    '**replace_when_full**', 'decay_time', '**unload_policy**',
    '**save_scope**', '**affects_gameplay**', 'gameplay_dependents',
    'evidence_level', 'observed_value', 'test_case', 'capture_id',
]

BUDGET_RULE = [
    '🔴 **预算不是性能参数，而是玩法参数**',
    '🔑 若血迹会引怪 → **最大痕迹数决定"旧痕迹被清掉时敌人失去线索"**',
    '🔑 若弹孔显示弹道 → **预算决定连续射击能否形成可读的射击模式**',
    '🔑 若草地只有最近 100 个踩踏点 → '
    '**玩家可用"踩踏是否消失"判断返回时间**',
    '🔑 验证脚本应逐项比较**预算耗尽后的替换顺序**，不能只截一张画面',
]

BUDGET_CLEAN = '🔑 规则：`if affects_gameplay == true, then unload_policy in '
'[evict_render_proxy_keep_fact, persist_fact_only]`'
BUDGET_CLEAN2 = '🔴 若原版确实因预算删除了影响玩法的痕迹 → '
'记为"**原版已知偏差**"，保留首次观测值与复现步骤，'
'**绝不能直接改成无限预算**'

# 🔴 读档四答案
LOAD_FOUR = [
    ('**restore_all**', '完全还原（适合剧情犯罪现场）'),
    ('**restore_static_only**', '只还原静态痕迹（世界随时间恢复）'),
    ('**restore_quest_bound**', '还原未完成任务相关痕迹'),
    ('**reset_all**', '全部重置'),
]

LOAD_RULE = [
    '🔴 **读档语义有四个合法答案，但混用就是 BUG**',
    '🔑 必须记"**读档触发者**"：手动读档 · 死亡重生 · 快速旅行 · '
    '区域卸载 · **崩溃恢复可能规则不同**',
    '🔑 字段 `load_behavior` + `preserve_reason`，'
    '并附**原版视频帧 · 区域坐标 · 前后内存或资源快照**',
]

# 生成世界
GEN_FIELDS = [
    'world_seed', 'generation_version', 'region_id',
    'local_uv_or_surface_anchor', 'surface_hash',
]

GEN_FOUR = ['retain', 'migrate', 'invalidate', 'promote_to_narrative_artifact']

GEN_RULE = [
    '🔑 **痕迹与生成世界绑定需要双重身份**',
    '🔴 程序生成区域重 roll 后，旧痕迹可能仍按旧坐标存在，'
    '却贴到新几何上，形成"**弹孔悬空**"',
    '🔑 区域重生成后执行四态裁决：' + ' · '.join(GEN_FOUR),
    '🔑 还要记**痕迹在流式边界两侧是否共享预算** —— '
    '玩家常见观察是"**刚跨区回头，痕迹消失**"',
]

# 🔴 通知分层
NOTIFY_FACT = [
    'event_id', '**causal_event_id**', 'occurred_at_clock', 'world_frame',
    'source_entity', '**stable_sort_key**', 'payload_hash',
]

NOTIFY_VIEW = ['展示窗口', '动画', '音效', '图标', '停留时间']

NOTIFY_RULE = [
    '🔑 **同一帧多个事件必须先把事实层与表现层分开**',
    '🔴 若直接把"拾取事件"投成 UI，会丢失**同一因果链 · 同一物品批量 · '
    '同一帧竞争 · 重复提交**的语义',
]

# 🔴 四把合并键
MERGE_KEYS = [
    ('**content_key**', '完全相同'),
    ('**semantic_key**', '同类合并'),
    ('**causal_key**', '同一次原因'),
    ('**presentation_key**', '同槽互斥'),
]

MERGE_EXAMPLE = '🔑 拾取 5 个生命药水：可能显示"**获得生命药水×5**"，'
'也可能**5 条**，还可能**先 3 条后刷新为 5 条** —— '
'**三者都可能是正确，必须抓帧判定**'

MERGE_CONFLICT = '🔴 **绝不能默认"统一成一个 toast"**'

# 窗口
WINDOW_MODES = [
    'none', 'frame', 'real_time', 'game_time', 'animation_finish',
    'manual_dismiss',
]

WINDOW_FIELDS = [
    '**window_mode**', 'merge_limit', '**order_rule**', 'collapse_format',
    'counter_position', 'same_source_bonus',
]

ORDER_RULES = ['fifo', 'priority_then_time', 'time_then_priority',
               'stable_causal']

WINDOW_RULE = [
    '🔑 **合并窗口不是固定毫秒，而是事件时钟与稳定排序**',
    '🔑 特别记录"**同帧**"和"**同渲染帧但不同逻辑 tick**"的区别 —— '
    '后者会让窗口系统表现出**看似随机的跨帧聚合**',
]

# 🔴 优先级双值
PRIO_FIELDS = [
    '**display_priority**', '**log_priority**', 'suppressible',
    'group_interrupt', 'replayable',
]

PRIO_RULE = [
    '🔴 **优先级必须双值化：可见优先级与事实优先级**',
    '🔑 重要事件可以打断 UI，但**未必应该删除低优先级历史**',
    '🔑 低优先级事件也可以"**不显示、仍入日志**"',
]

# 溢出八策略
OVERFLOW_EIGHT = [
    '丢最旧', '丢最低优先级', '丢同键', '丢不可见', '合并到摘要',
    '降级到日志', '阻塞直到确认', '扩容并报警',
]

OVERFLOW_RULE = '🔴 **前两种最危险** —— 会改变玩家理解的**事件历史**'

# 疲劳
FATIGUE_ITEMS = [
    '重复间隔抑制', '短时爆发抑制', '离开触发范围抑制', '同一来源抑制',
    '静音档', '玩家主动折叠', '换区域后重置',
    '**暂停时累计还是冻结**', '**死亡/过场时排队还是丢弃**',
]

FATIGUE_RULE = [
    '🔑 **消息疲劳是可测规则，不是"少弹点"**',
    '🔑 还要区分"**未显示**"和"**已提交但被抑制**" —— '
    '成就 · 任务 · 教学常依赖前者进入**待显示队列**，'
    '**直接丢弃会造成返回菜单后不再提醒**',
]

FATIGUE_TIME = '🔴 **用浮点时间排序事件会冲突** —— '
'同毫秒事件顺序会随平台浮点误差变化，**必须用稳定因果排序键**'

CONFLICTS = [
    '❌ 用无数量上限的粒子/贴花堆表现痕迹',
    '❌ **把痕迹限制写成全局画质档**',
    '❌ 为减少绘制调用**静默删除最旧痕迹**',
    '❌ **把血迹/弹孔合并成一张图**（破坏连续射击的空间可辨性）',
    '❌ 读档语义混用',
    '❌ 把影响玩法的痕迹直接改成无限预算',
    '❌ **单队列 toast / 固定顶替 / 自动隐藏 / 全局去重**',
    '❌ 只显示最新一条',
    '❌ 系统提示与剧情提示塞进同一队列',
    '❌ **用浮点时间排序事件**',
    '❌ 默认"统一成一个 toast"',
    '❌ 丢最旧 / 丢最低优先级（改变事件历史）',
]

FIELDS = [
    ('item_id', '项编号'),
    ('domain', '域（trace / budget / load / gen / notify / merge / '
               'window / prio / overflow / fatigue）'),
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


def cmd_trace(a):
    _hdr('🔴 持久痕迹（**八组**）')
    for k, ex in TRACE_EIGHT:
        print(f'   {k:<14} {ex}')
    print('\n每组再测:')
    print('   ' + ' · '.join(TRACE_EACH))
    print('\n痕迹字段: ' + ' · '.join(TRACE_FIELDS))
    print('\n规则:')
    for r in TRACE_RULE:
        print(f'   {r}')
    return 0


def cmd_budget(a):
    _hdr('🔴 痕迹预算（**14 字段**）')
    print('字段: ' + ' · '.join(BUDGET_FIELDS))
    print('\n规则:')
    for r in BUDGET_RULE:
        print(f'   {r}')
    print(f'\n   {BUDGET_CLEAN}')
    print(f'   {BUDGET_CLEAN2}')
    return 0


def cmd_load(a):
    _hdr('🔴 读档语义（**四答案**）')
    for k, why in LOAD_FOUR:
        print(f'   {k:<26} {why}')
    print('\n规则:')
    for r in LOAD_RULE:
        print(f'   {r}')
    return 0


def cmd_gen(a):
    _hdr('痕迹 × 生成世界（**双重身份**）')
    print('字段: ' + ' · '.join(GEN_FIELDS))
    print('\n四态裁决: ' + ' · '.join(GEN_FOUR))
    print('\n规则:')
    for r in GEN_RULE:
        print(f'   {r}')
    return 0


def cmd_notify(a):
    _hdr('🔴 通知（**事实层 / 表现层分离**）')
    print('事实层: ' + ' · '.join(NOTIFY_FACT))
    print('表现层: ' + ' · '.join(NOTIFY_VIEW))
    print('\n规则:')
    for r in NOTIFY_RULE:
        print(f'   {r}')
    return 0


def cmd_merge(a):
    _hdr('🔴 四把合并键')
    for k, why in MERGE_KEYS:
        print(f'   {k:<22} {why}')
    print(f'\n   {MERGE_EXAMPLE}')
    print(f'   {MERGE_CONFLICT}')
    return 0


def cmd_window(a):
    _hdr('合并窗口（**非固定毫秒**）')
    print('window_mode: ' + ' · '.join(WINDOW_MODES))
    print('order_rule:  ' + ' · '.join(ORDER_RULES))
    print('\n字段: ' + ' · '.join(WINDOW_FIELDS))
    print('\n规则:')
    for r in WINDOW_RULE:
        print(f'   {r}')
    return 0


def cmd_prio(a):
    _hdr('🔴 优先级（**双值化**）')
    print('字段: ' + ' · '.join(PRIO_FIELDS))
    print('\n规则:')
    for r in PRIO_RULE:
        print(f'   {r}')
    print('\n队列溢出八策略: ' + ' · '.join(OVERFLOW_EIGHT))
    print(f'\n   {OVERFLOW_RULE}')
    return 0


def cmd_overflow(a):
    _hdr('队列溢出（**八策略**）')
    for i, o in enumerate(OVERFLOW_EIGHT, 1):
        print(f'   {i}. {o}')
    print(f'\n   {OVERFLOW_RULE}')
    return 0


def cmd_fatigue(a):
    _hdr('消息疲劳（**可测规则**）')
    for f in FATIGUE_ITEMS:
        print(f'   · {f}')
    print('\n规则:')
    for r in FATIGUE_RULE:
        print(f'   {r}')
    print(f'\n   {FATIGUE_TIME}')
    return 0


def cmd_init(a):
    os.makedirs(os.path.dirname(a.init) or '.', exist_ok=True)
    with open(a.init, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow([k for k, _ in FIELDS])
        w.writerow(['TODO'] * len(FIELDS))
    print(f'已生成痕迹/通知表: {a.init}')
    print('\n⚠️ 十域：trace / budget / load / gen / notify / merge / '
          'window / prio / overflow / fatigue')
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
    print(f'痕迹/通知 · {len(rows)} 条')
    print('=' * 76)
    if mismatch:
        print(f'\n🚫 **不一致** {len(mismatch)} 条（行 {mismatch[:15]}）')
    if no_legacy:
        print(f'\n❌ {len(no_legacy)} 条缺**原版值**（行 {no_legacy[:15]}）')
    if no_grade:
        print(f'\n🚫 {len(no_grade)} 条**证据等级缺失或 ≥7 级**'
              f'（行 {no_grade[:15]}）')

    if not (mismatch or no_legacy or no_grade):
        print('\n✅ 痕迹/通知：一致、原版值完整、证据等级达标')

    print('\n🔑 **痕迹不是贴图；渲染代理可消失，"血迹曾在此"的事实不能消失。**')
    print('   **通知问题不是显示而是事件账本；不能默认"统一成一个 toast"。**')
    print('   **用浮点时间排序事件会冲突，必须用稳定因果排序键。**')
    return 1 if (a.gate_check and (mismatch or no_legacy or no_grade)) else 0


def main():
    ap = argparse.ArgumentParser(description='持久痕迹与通知聚合')
    ap.add_argument('--trace', action='store_true')
    ap.add_argument('--budget', action='store_true')
    ap.add_argument('--load', action='store_true')
    ap.add_argument('--gen', action='store_true')
    ap.add_argument('--notify', action='store_true')
    ap.add_argument('--merge', action='store_true')
    ap.add_argument('--window', action='store_true')
    ap.add_argument('--prio', action='store_true')
    ap.add_argument('--overflow', action='store_true')
    ap.add_argument('--fatigue', action='store_true')
    ap.add_argument('--init')
    ap.add_argument('--check')
    ap.add_argument('--gate-check', action='store_true')
    a = ap.parse_args()
    fns = {'trace': cmd_trace, 'budget': cmd_budget, 'load': cmd_load,
           'gen': cmd_gen, 'notify': cmd_notify, 'merge': cmd_merge,
           'window': cmd_window, 'prio': cmd_prio,
           'overflow': cmd_overflow, 'fatigue': cmd_fatigue}
    for k, fn in fns.items():
        if getattr(a, k):
            return fn(a)
    if a.init:
        return cmd_init(a)
    if a.check:
        return cmd_check(a)
    print('❌ 需要 --trace / --budget / --load / --gen / --notify / '
          '--merge / --window / --prio / --overflow / --fatigue / '
          '--init / --check 之一')
    return 2


if __name__ == '__main__':
    sys.exit(main())
