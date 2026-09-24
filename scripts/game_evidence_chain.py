#!/usr/bin/env python3
"""四层证据链 + 取证顺序 + 仲裁层（第十九轮 A / B 类）。

**🔑 A 类核心**：
> 十八轮之后，瓶颈已从"**知道查什么**"变成"**知道先查什么、证据如何裁决**"。
>
> 🔴 若没有采集顺序，多人容易并行采到大量**高噪声证据**，最后无法组合。
> 🔑 可执行工作流应按**依赖关系**而非文件类型组织。

**🔑 B 类核心**：
> **没有证据等级就只剩观点投票。**
> 🔴 **证据等级不是"源码一定赢"**，而是按**直接性与可验证性**排序。
> 🔴 **反编译源码描述的是推测实现，原版测量描述的是目标真实行为** ——
> 二者冲突时先标记 `evidence_conflict`，**不能直接认定原版是 bug**。

用法:
  game_evidence_chain.py --chain  # 🔴 **四层证据链**
  game_evidence_chain.py --order  # 取证顺序（**依赖**而非文件类型）
  game_evidence_chain.py --stop   # 🔴 "够用"是**风险驱动停止规则**
  game_evidence_chain.py --merge  # 多人合并键**不只是关卡名**
  game_evidence_chain.py --grade  # 🔴 证据**八级**
  game_evidence_chain.py --inconsist # 原版不一致**三分类**
  game_evidence_chain.py --unrepro  # 🔴 无法复现**不是缺失也不是 bug**
  game_evidence_chain.py --bugordesign # **四条门槛**
  game_evidence_chain.py --diverge  # **偏离许可**是可审计契约
  game_evidence_chain.py --init ledger/evidence_chain.csv
  game_evidence_chain.py --check ledger/evidence_chain.csv --gate

退出码: 0 通过 / 1 缺项 / 2 用法错误
"""
import argparse
import csv
import os
import sys

# 🔴 四层证据链
CHAIN_LAYERS = [
    ('**原版证据**', '构建哈希 · 资源校验 · 平台 · 录像 · 输入 · 状态 · '
     'GPU/音频捕获',
     '计算内容清单与证据包哈希',
     '❌ 裁剪失败样本、只留最终录像'),
    ('**双轨执行**', '同源输入 · 帧号 · 时钟 · 模拟状态 · 表现状态',
     '同机/同输入双跑，**先原版后新版**',
     '❌ 让画面相似掩盖状态不同'),
    ('**差异仲裁**', '证据等级 · 容忍带 · 冲突原因 · 审批链',
     '自动标记后**人工裁决**',
     '❌ 用投票或多数记忆覆盖源码/测量'),
    ('**兼容演进**', '原版基线版本 · 迁移版本 · 偏离类型 · 回滚点',
     '建立稳定兼容窗口与冻结区',
     '❌ 静默重编号、改写历史、删除旧格式'),
]

CHAIN_RULE = [
    '🔑 **四层证据链是本轮最重要的结构增量** —— '
    '它规定证据**如何排列、如何并行、何时停止**，而不是增加新的取证对象',
    '🔴 **上层不得覆盖下层原始事实**',
]

# 取证顺序
ORDER = [
    '**样本身份**', '**构建与依赖锁定**', '**输入与设备配置**',
    '**初始状态/种子**', '**关键游戏状态**', '**表现层**',
    '**GPU/音频命令**', '**跨版本重复**',
]

ORDER_WHY = [
    '🔑 原因**不是仪式感**，而是后一层证据若失去前一层的标识，'
    '就无法回答"**这是同一个测试吗**"',
    '🔴 没有输入时钟 → 录像**只能证明画面相似**',
    '🔴 没有构建哈希 → **无法区分原版补丁与旧录像**',
    '🔴 没有初始状态 → **随机行为无法复跑**',
]

ORDER_PARALLEL = [
    '✅ 可并行：不同关卡 · 不同设备 · 不同原版版本 · 独立录像机 · '
    '独立音频采集',
    '🔴 **不可并行**：同一次输入流的状态日志、视频和 GPU 捕获 —— '
    '它们必须**同一时间原点和同一输入时钟**',
]

# 🔴 停止规则
STOP_COVER = [
    '成功路径', '**失败路径**', '**首次触发**', '**边界值**',
    '**竞态窗口**', '**恢复路径**',
]

STOP_RATES = [
    '对时序敏感行为还要覆盖**原版帧率、目标刷新率，'
    '以及至少一个非对齐刷新率**',
]

STOP_THRESH = [
    '关键路径**不少于 3 次独立成功与失败重放**',
    '每条**原版版本 × 平台 × 输入设备**组合不少于 1 个有效样本',
    '每条不可复现证据至少有 **2 名操作者、2 次设备、2 次环境**尝试',
]

STOP_NOTE = [
    '🔴 这里的"**3、2、1**"**不是统计定理**，而是防止'
    '**单人、单设备和单次巧合**的排障阈值',
    '🔑 样本充分性最终由**分支覆盖率、变异敏感度和偏离数量**决定，'
    '**而不是"总游玩时长"**',
]

STOP_LEGACY = '🔑 老玩家迁移还需要**真实存档、失败存档和未知字段样例** —— '
'**只靠开发期测试档无法发现"旧档里某个从未文档化的状态"**'

# 合并键
MERGE_KEY = ('game_version + platform + build_hash + scene + entity + '
             'interaction + input_sequence_id + frame_index')

MERGE_RULE = [
    '🔴 多人协作的合并键**不应只是"关卡名"**',
    f'🔑 应为 `{MERGE_KEY}`',
    '🔑 冲突时**先检查环境、时钟、随机种子、资源和硬件**，再进入人工仲裁',
    '🔴 **不可自动覆盖**',
]

# 🔴 证据八级
GRADES = [
    ('1', '**目标构建确定性输入重放/状态**', 'must-match 真值',
     '构建哈希 · 初始状态 · 种子 · 帧号'),
    ('2', '**目标版本重复测量**', '时序、物理、概率真值',
     '样本数 · 设备 · 置信区间或观察区间'),
    ('3', '**目标二进制/资源静态事实**', '格式、常量、资源语义',
     '偏移 · 解析器 · 校验和'),
    ('4', '**反编译/汇编对应目标代码**', '解释机制，**不得独立证明行为**',
     '工具链 · 反编译误差 · 对照测量'),
    ('5', '**跨版本/跨平台实测**', '差异矩阵、兼容决策',
     '全部软件/硬件配置'),
    ('6', '**有上下文视频**', '现象、启发式假设',
     '时间码 · 帧率 · 输入日志'),
    ('7', '**无上下文视频**', '问题线索，**不作为验收**', '需补采'),
    ('8', '**玩家记忆/社区转述**', '生成取证任务',
     '受访者 · 日期 · 原始表述'),
]

GRADE_RULE = [
    '🔴 **源码高于原版行为只在它确实属于目标构建、目标配置且无反编译误差时成立**',
    '🔴 **反编译源码描述的是推测实现，原版测量描述的是目标真实行为**',
    '🔑 二者冲突时**先标记 `evidence_conflict`**，'
    '**不能直接认定原版是 bug**',
]

# 原版不一致三分类
INCONSIST_THREE = [
    ('**preserved_original**', '目标必须**全平台一致**的硬契约'),
    ('**version_fork**', '新版**特意保留**差异的版本分叉'),
    ('**observation_noise**', '因输入、网络、性能和硬件造成的观测噪声'),
]

INCONSIST_RULE = [
    '🔴 **原版本身不一致时，行为应成为版本化事实，'
    '而非选择"最正确"的一版**',
    '🔑 每个冲突都要写成"**在 X 版本、Y 平台、Z 配置下观察到 W**"，'
    '同时保存**影响范围和可复现率**',
    '🔑 **只有同一证据等级下无法解释的测量差异才进入仲裁**',
    '🔴 **不能为了"新版整洁"把原版差异压成单一规则**',
    '🔑 若新版决定按平台分支，**验收也必须接受不同平台的输出** —— '
    '**不能用跨平台像素完全一致作为门禁**',
]

EQUIV_RULE = '🔑 **"一致"与"等价"要分开**：逻辑和手感一致**不要求内存布局一致**；'
'表现一致**也不要求 GPU 命令一致**'

# 🔴 无法复现
UNREPRO_FIELDS = [
    '2 名操作者', '2 类设备', '2 种环境', '重复次数', '**可复现率**',
    '**最大观察值**', '**最小观察值**', '触发条件', '**补采计划**',
]

UNREPRO_ACCEPT = [
    '`deterministic_pass`', '`probabilistic_band`', '`unknown_pending`',
]

UNREPRO_RULE = [
    '🔴 **"无法复现"不是缺失，也不是 bug，必须进入独立证据状态**',
    '🔑 **对概率性行为，禁止用一次成功或一次失败定案**',
    '🔑 对硬件偶发，使用稳定版本下的**观察区间和重测计划**，'
    '**而不是假装行为稳定**',
    '🔴 **禁止 `not_a_bug` 兜底**',
]

# bug 还是设计
BUGDESIGN_GATES = [
    '**是否能由目标版本/平台直接复现**',
    '**是否存在跨实体、跨版本的稳定规则**',
    '**改变它是否破坏相邻系统**',
    '**原版玩家是否形成了对应策略和记忆**',
]

BUGDESIGN_RULE = [
    '🔑 满足**可复现与稳定规则**时倾向**原版设计**',
    '🔑 只出现在单一版本且改变会破坏相邻系统时 → '
    '可标 `preserved_platform_bug`',
    '🔴 **完全没有复现证据时只能标 `unknown`，不得写"原版 bug"**',
]

# 偏离许可
DIVERGE_FIELDS = [
    'divergence_id', '功能路径', '**原版证据**', '**冲突证据**',
    '目标行为', '影响面', '**玩家可观察变化**', '风险', '回归测试',
    '**回滚条件**', '审批者', '批准日期', '**过期复审日**',
]

DIVERGE_APPROVE = [
    '**must-match 无例外**',
    '原版不一致 → 仲裁组',
    '跨系统后果 → 受影响模块**共同签字**',
    '面向老玩家的 QoL 变化 → 还要增加**玩家代表或体验负责人**',
]

DIVERGE_RULE = [
    '🔴 **偏离许可不是一句"已批准"，而是把改变变成可审计契约**',
    '🔑 **每个偏离都必须有 owner 和到期日** —— '
    '否则长期分支会在**无人认领中腐烂**',
]

CONFLICTS = [
    '❌ **重构优先于保真**',
    '❌ **自动化覆盖率替代像素证据**',
    '❌ 无上下文的 LLM 复刻助手',
    '❌ 跨游戏存档转换器冒充通用方案',
    '❌ 用投票或多数记忆覆盖源码/测量',
    '❌ 把原版差异压成单一规则',
    '❌ **用跨平台像素完全一致作门禁**（当新版按平台分支时）',
    '❌ **`not_a_bug` 兜底**',
    '❌ 无复现证据就写"原版 bug"',
    '❌ 偏离无 owner 和到期日',
    '❌ 只靠开发期测试档验证迁移',
    '❌ 多人取证自动覆盖冲突',
]

FIELDS = [
    ('item_id', '项编号'),
    ('domain', '域（chain / order / stop / merge / grade / inconsist / '
               'unrepro / bugordesign / diverge）'),
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


def cmd_chain(a):
    _hdr('🔴 四层证据链')
    for name, has, act, ban in CHAIN_LAYERS:
        print(f'\n   【{name}】')
        print(f'     必存: {has}')
        print(f'     动作: {act}')
        print(f'     禁止: {ban}')
    print('\n规则:')
    for r in CHAIN_RULE:
        print(f'   {r}')
    return 0


def cmd_order(a):
    _hdr('取证顺序（**依赖**而非文件类型）')
    for i, o in enumerate(ORDER, 1):
        print(f'   {i}. {o}')
    print('\n为什么:')
    for r in ORDER_WHY:
        print(f'   {r}')
    print('\n并行:')
    for p in ORDER_PARALLEL:
        print(f'   {p}')
    return 0


def cmd_stop(a):
    _hdr('🔴 "够用"是风险驱动停止规则')
    print('覆盖: ' + ' · '.join(STOP_COVER))
    print('\n刷新率: ' + ' · '.join(STOP_RATES))
    print('\n阈值:')
    for t in STOP_THRESH:
        print(f'   · {t}')
    print('\n注意:')
    for n in STOP_NOTE:
        print(f'   {n}')
    print(f'\n   {STOP_LEGACY}')
    return 0


def cmd_merge(a):
    _hdr('多人合并键')
    print(f'   合并键: {MERGE_KEY}')
    print('\n规则:')
    for r in MERGE_RULE:
        print(f'   {r}')
    return 0


def cmd_grade(a):
    _hdr('🔴 证据八级')
    for g, what, use, ctx in GRADES:
        print(f'   {g}. {what}')
        print(f'      用途: {use}')
        print(f'      上下文: {ctx}')
    print('\n规则:')
    for r in GRADE_RULE:
        print(f'   {r}')
    return 0


def cmd_inconsist(a):
    _hdr('原版不一致三分类')
    for k, why in INCONSIST_THREE:
        print(f'   {k:<24} {why}')
    print('\n规则:')
    for r in INCONSIST_RULE:
        print(f'   {r}')
    print(f'\n   {EQUIV_RULE}')
    return 0


def cmd_unrepro(a):
    _hdr('🔴 无法复现（**不是缺失也不是 bug**）')
    print('字段: ' + ' · '.join(UNREPRO_FIELDS))
    print('\n验收三级: ' + ' · '.join(UNREPRO_ACCEPT))
    print('\n规则:')
    for r in UNREPRO_RULE:
        print(f'   {r}')
    return 0


def cmd_bugordesign(a):
    _hdr('bug 还是设计（**四条门槛**）')
    for i, g in enumerate(BUGDESIGN_GATES, 1):
        print(f'   {i}. {g}')
    print('\n规则:')
    for r in BUGDESIGN_RULE:
        print(f'   {r}')
    return 0


def cmd_diverge(a):
    _hdr('偏离许可（**可审计契约**）')
    print('字段: ' + ' · '.join(DIVERGE_FIELDS))
    print('\n审批链:')
    for d in DIVERGE_APPROVE:
        print(f'   · {d}')
    print('\n规则:')
    for r in DIVERGE_RULE:
        print(f'   {r}')
    return 0


def cmd_init(a):
    os.makedirs(os.path.dirname(a.init) or '.', exist_ok=True)
    with open(a.init, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow([k for k, _ in FIELDS])
        w.writerow(['TODO'] * len(FIELDS))
    print(f'已生成证据链表: {a.init}')
    print('\n⚠️ 九域：chain / order / stop / merge / grade / inconsist / '
          'unrepro / bugordesign / diverge')
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
    print(f'证据链 · {len(rows)} 条')
    print('=' * 76)
    if mismatch:
        print(f'\n🚫 **不一致** {len(mismatch)} 条（行 {mismatch[:15]}）')
    if no_legacy:
        print(f'\n❌ {len(no_legacy)} 条缺**原版值**（行 {no_legacy[:15]}）')
    if no_grade:
        print(f'\n🚫 {len(no_grade)} 条**证据等级缺失或 ≥7 级**'
              f'（行 {no_grade[:15]}）—— '
              '7 级以上**不得作为验收依据**')

    if not (mismatch or no_legacy or no_grade):
        print('\n✅ 证据链：一致、原版值完整、证据等级达标')

    print('\n🔑 **没有证据等级就只剩观点投票。**')
    print('   **反编译是推测实现，原版测量是真实行为。**')
    print('   **无法复现不是缺失也不是 bug；禁止 not_a_bug 兜底。**')
    return 1 if (a.gate_check and (mismatch or no_legacy or no_grade)) else 0


def main():
    ap = argparse.ArgumentParser(description='四层证据链与仲裁')
    ap.add_argument('--chain', action='store_true')
    ap.add_argument('--order', action='store_true')
    ap.add_argument('--stop', action='store_true')
    ap.add_argument('--merge', action='store_true')
    ap.add_argument('--grade', action='store_true')
    ap.add_argument('--inconsist', action='store_true')
    ap.add_argument('--unrepro', action='store_true')
    ap.add_argument('--bugordesign', action='store_true')
    ap.add_argument('--diverge', action='store_true')
    ap.add_argument('--init')
    ap.add_argument('--check')
    ap.add_argument('--gate-check', action='store_true')
    a = ap.parse_args()
    fns = {'chain': cmd_chain, 'order': cmd_order, 'stop': cmd_stop,
           'merge': cmd_merge, 'grade': cmd_grade,
           'inconsist': cmd_inconsist, 'unrepro': cmd_unrepro,
           'bugordesign': cmd_bugordesign, 'diverge': cmd_diverge}
    for k, fn in fns.items():
        if getattr(a, k):
            return fn(a)
    if a.init:
        return cmd_init(a)
    if a.check:
        return cmd_check(a)
    print('❌ 需要 --chain / --order / --stop / --merge / --grade / '
          '--inconsist / --unrepro / --bugordesign / --diverge / '
          '--init / --check 之一')
    return 2


if __name__ == '__main__':
    sys.exit(main())
