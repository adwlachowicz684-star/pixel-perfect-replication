#!/usr/bin/env python3
"""运气体验 + 技巧天花板（第十七轮 A / B 类）。

**🔑 A 类核心**：
> **"平均概率正确"无法保护运气体验，真正要验证的是有限样本尾部。**
> 玩家抱怨的不是随机，而是**不可理解的尾部与不一致的承诺**。
>
> 🔴 must-match 的基准应是**从同一内部状态出发、同一调用顺序、同一种子
> 产生同一结果及同一可见承诺**，而不是强求实现曲线逐字复刻。

**🔑 B 类核心**：
> **技巧不是动作名，而是跨刷新率仍然闭合的状态机。**
> 🔴 **技巧是否"有意"必须记录证据链，不能只靠社区共识。**
> 🔴 若同一输入在 60Hz 能触发而在 144Hz 不能 ——
> 问题通常**不是帧率导致变难，而是窗口依赖渲染帧或命令采样点**。

用法:
  game_luck_skill.py --luck4     # 运气**四层**
  game_luck_skill.py --pity      # 🔴 保底**六种语义**
  game_luck_skill.py --pseudo    # 伪随机的**体感**是 streak 边界
  game_luck_skill.py --nearmiss  # 🔴 险胜**谁获得戏剧性信息**
  game_luck_skill.py --audit     # 结果**可回看**但不必公开算法
  game_luck_skill.py --intent    # 🔴 技巧**是否有意**要有证据链
  game_luck_skill.py --framebase # 🔴 **帧基准声明**
  game_luck_skill.py --closure   # 跨版本保留**触发闭包**
  game_luck_skill.py --sweep     # 🔴 30/60/120/144Hz 扫描
  game_luck_skill.py --bugfeat   # 🔴 **bug 变 feature** 历史决策
  game_luck_skill.py --init ledger/luck_skill.csv
  game_luck_skill.py --check ledger/luck_skill.csv --gate

退出码: 0 通过 / 1 缺项 / 2 用法错误
"""
import argparse
import csv
import os
import sys

# 运气四层
LUCK_FOUR = [
    ('**种子**', '同一内部状态出发'),
    ('**调用顺序**', '相同 call 序列'),
    ('**状态快照**', '抽取前完整状态'),
    ('**可见承诺**', '玩家被告知了什么'),
]

LUCK_FIELDS = [
    '基础概率', '条件概率', '**当前窗口计数**', '**保底是否独立**',
    '是否洗牌后再抽取', '是否分池', '**是否跨场景续存**',
    '结果是否预先锁定', '**演出是否诚实**', '失败/成功是否触发额外反馈',
]

LUCK_RULE = [
    '🔑 第 90 抽必得**并不意味着第 89 抽前的每次概率都相同**',
    '🔑 展示 1.5% **也不意味着内部必须采用固定概率**',
    '🔑 要拆成上述十项分别记录',
]

# 🔴 保底六种语义
PITY_SIX = [
    '**UI 是否显示距离保底的进度**',
    '**是否区分软保底 / 硬保底**',
    '**保底是否分卡池**',
    '**跨周目是否继承**',
    '**读档是否回滚**',
    '**网络中断或重复请求是否重复消耗**',
]

PITY_RESET = [
    '结果确定时', '**动画开始时**', '**物品入账时**', '**提交完成时**',
]

PITY_RULE = [
    '🔴 **仅记录"有保底"不够**，还要记上述六种语义',
    '🔑 尤其要检查"**抽到就重置**"的精确时刻（上述四种之一）',
    '🔴 **若在玩家看到稀有演出后才回滚 → 保底可信度立即受损**',
    '🔴 若原版显示"下一次必中"而重制只显示"概率随次数提高" → '
    '**这是可感知偏离，不是纯表现差异**',
]

# 伪随机体感
PSEUDO_KINDS = [
    'shuffle bag', '**PRD**（伪随机分布）', '带记忆权重', '禁连抽',
    '保底', '稀有加权',
]

PSEUDO_TESTS = [
    '**连续 0 命中**', '连续成功', '**最坏 streak**', '首次成功分布',
    '第 N 次后条件概率', '**跨两次短会话的计数器续存**',
]

PSEUDO_RULE = [
    '🔑 **伪随机的体感不是算法名，而是失败 streak 与成功 streak 的边界**',
    '🔑 应记录"**玩家何时开始怀疑系统不公平**"，不能只记算法类别',
    '🔴 **若一个掉落同时在多处读取 RNG，调用顺序会成为隐蔽破坏点** —— '
    '新增音效、分析、教学都可能改变结果，却不影响配置文件',
    '🔑 建议为每类随机源设**独立命名 RNG**，'
    '并用 `source, sequence_index, call_site_id` 审计日志',
]

# 🔴 险胜
NEARMISS_SOURCES = [
    '剩余生命', '计时器', '距离', '**同步窗口**', '判定盒', '**结算顺序**',
]

NEARMISS_FIELDS = [
    '**临界阈值**', '**判定是在模拟 tick 还是渲染帧**',
    '**音画与结算谁先定稿**', '失败后是否补放"仅差 0.03 秒/1 点"',
    '**这个提示是否永远诚实**',
]

NEARMISS_RULE = [
    '🔴 **"差一点"不是天然好评，必须明确谁获得了戏剧性信息**',
    '🔴 若真实差 12%，却固定播放"就差一点" → '
    '**玩家会把所有接近失败理解为安慰话术**',
    '🔴 反过来，**若真的只差一个判定帧却不提示** → 戏剧性收益被浪费',
]

# 审计
AUDIT_PACK = [
    'seed', 'rng_version', 'source_id', 'call_index',
    '**weights_snapshot_hash**', 'outcome_id', '**commit_frame**',
    'visible_result_id',
]

AUDIT_RULE = [
    '🔑 **随机结果必须能被回看，但不必把内部算法全交给玩家**',
    '🔑 玩家侧可只显示"种子、流程版本、公开输入、可本地重算界面"',
    '🔑 服务端或内部诊断保留完整调用链',
]

# 🔴 技巧意图
INTENT_SOURCES = [
    '教程', 'loading tip', 'NPC 提示', '挑战提示', '成就', '局内引导',
    'UI tooltip', '**完全没有提示**',
]

INTENT_FIELDS = [
    '**发现渠道**', '首次出现章节', '是否有练习场景',
    '**是否会被教学技能门挡住**', '**社区发现前后是否存在版本变化**',
]

INTENT_RULE = [
    '🔴 **技巧是否"有意"必须记录证据链，不能只靠社区共识**',
    '🔑 若原版从未提示而玩家从 1% 保留率里发现连跳 → '
    '应标记为"**无意识允许→被社区接受→未正式承诺**"，'
    '**而不是重制时擅自加 tooltip**',
]

# 🔴 帧基准
FRAME_BASES = [
    '**sim_tick_window**', '**anim_frame_window**', '**render_frame_window**',
    '命令提交帧', '**物理 contact 帧**',
]

FRAME_RULE = [
    '🔑 必须记窗口的**开始事件与结束事件**',
    '🔑 每一技巧至少标记上述之一，并说明窗口边界采用 '
    '**inclusive 还是 exclusive**',
    '🔴 **若同一输入在 60Hz 能触发而在 144Hz 不能** —— '
    '问题通常**不是帧率导致变难，而是窗口依赖渲染帧或命令采样点**',
]

# 闭包
CLOSURE_FIELDS = [
    '入口状态', '触发条件', '消耗状态', '互斥状态', '**最长有效窗口**',
    '**输入沿与电平语义**', '缓冲队列长度', '**刷新率依赖**',
    '是否可中途取消', '**失败是否消耗资源**',
    '成功/失败是否产生音频', '**录像能否复现**',
]

CANCEL_FIELDS = [
    '**cancel_token_valid_from**', 'state_exit_point',
    'next_action_min_start', 'buffer_commit', '**失败时的状态恢复**',
]

CLOSURE_RULE = '🔑 **跨版本一致性不是保留彩蛋名单，而是保留触发闭包** —— '
'这样才能回答：重制加入更平滑过渡后，究竟是**技巧更难了**，'
'还是**输入仍发生在原窗口但视觉更晚闭合**'

# 🔴 扫描
SWEEP_RATES = ['30Hz', '60Hz', '120Hz', '144Hz']

SWEEP_ASSERT = [
    '**末次成功帧**', '**首次失败帧**', '状态消耗帧', '动画开始帧',
]

SWEEP_RULE = [
    '🔴 帧率回归应从"**最终位置**"升级为"**首次/末次成功边界**"',
    '🔑 固定输入序列分别在上述四档回放，检查四项是否一致',
    '🔴 **仅比较最终坐标是弱断言**',
    '🔑 物理建议运行固定步长；'
    '**若原版本就采用可变步长，则重制必须复刻该"缺陷"**',
    '🔑 对不确定项输出 `unstable_under_refresh_rate`，**不猜原因**',
]

# 🔴 bug 变 feature
BUGFEAT_FIELDS = [
    '**正式化版本号 / 补丁号**', '**公开措辞**',
    '修复后又恢复的原因', '社区反应证据',
]

BUGFEAT_RULE = '🔑 若某补丁修复了它，又因玩家抗议恢复 → '
'应记录"**正式化版本号/补丁号**"与公开措辞 —— '
'**这就是典型的 bug 变 feature 历史决策**'

GFXRECON_NOTE = [
    '🔑 GFXReconstruct 可捕获 Vulkan/D3D12 调用并**在同机或不同硬件重放**',
    '🔑 适合**证明图形调用序列相同**',
    '🔴 **它不能证明输入→模拟→技巧窗口一致** —— '
    '**必须与固定步长输入录像共同使用**',
    '🔴 **图形重放 ≠ 模拟/技巧一致性；不可仅用 GPU trace 验收**',
]

CONFLICTS = [
    '❌ 拿普通 RNG 冒充概率审计',
    '❌ **不自动改为均匀结果**',
    '❌ 引入新生成器却不锁定输出契约',
    '❌ **用 A/B 测试"优化"保底透明度**',
    '❌ **以动态难度掩盖运气尾部**',
    '❌ **仅用 GPU trace 验收技巧**',
    '❌ **将帧率相关技巧重命名为"有意加深难度"**',
    '❌ 重制采用可变步长而原版为固定步长（除非明确接受历史偏离）',
    '❌ 擅自给未承诺技巧加 tooltip',
]

FIELDS = [
    ('item_id', '项编号'),
    ('domain', '域（luck4 / pity / pseudo / nearmiss / audit / intent / '
               'framebase / closure / sweep / bugfeat）'),
    ('legacy_value', '**原版值**'),
    ('new_value', '新引擎值'),
    ('match', '**是否一致**'),
    ('tolerance', '**允许偏差**'),
    ('evidence', '证据'),
]


def _hdr(t, w=80):
    print('=' * w)
    print(t)
    print('=' * w)


def cmd_luck4(a):
    _hdr('运气四层')
    for k, why in LUCK_FOUR:
        print(f'   {k:<14} {why}')
    print('\n字段: ' + ' · '.join(LUCK_FIELDS))
    print('\n规则:')
    for r in LUCK_RULE:
        print(f'   {r}')
    return 0


def cmd_pity(a):
    _hdr('🔴 保底（**六种语义**）')
    for p in PITY_SIX:
        print(f'   · {p}')
    print('\n重置时刻: ' + ' · '.join(PITY_RESET))
    print('\n规则:')
    for r in PITY_RULE:
        print(f'   {r}')
    return 0


def cmd_pseudo(a):
    _hdr('伪随机（**体感是 streak 边界**）')
    print('种类: ' + ' · '.join(PSEUDO_KINDS))
    print('\n测试: ' + ' · '.join(PSEUDO_TESTS))
    print('\n规则:')
    for r in PSEUDO_RULE:
        print(f'   {r}')
    return 0


def cmd_nearmiss(a):
    _hdr('🔴 险胜（**谁获得戏剧性信息**）')
    print('临界来源: ' + ' · '.join(NEARMISS_SOURCES))
    print('\n字段: ' + ' · '.join(NEARMISS_FIELDS))
    print('\n规则:')
    for r in NEARMISS_RULE:
        print(f'   {r}')
    return 0


def cmd_audit(a):
    _hdr('结果可回看（**不必公开算法**）')
    print('最小可追溯包: ' + ' · '.join(AUDIT_PACK))
    print('\n规则:')
    for r in AUDIT_RULE:
        print(f'   {r}')
    return 0


def cmd_intent(a):
    _hdr('🔴 技巧（**是否有意要有证据链**）')
    print('发现渠道: ' + ' · '.join(INTENT_SOURCES))
    print('\n字段: ' + ' · '.join(INTENT_FIELDS))
    print('\n规则:')
    for r in INTENT_RULE:
        print(f'   {r}')
    return 0


def cmd_framebase(a):
    _hdr('🔴 帧基准声明')
    for f in FRAME_BASES:
        print(f'   · {f}')
    print('\n规则:')
    for r in FRAME_RULE:
        print(f'   {r}')
    return 0


def cmd_closure(a):
    _hdr('触发闭包（**跨版本保留**）')
    for f in CLOSURE_FIELDS:
        print(f'   · {f}')
    print('\n取消窗口字段: ' + ' · '.join(CANCEL_FIELDS))
    print(f'\n   {CLOSURE_RULE}')
    return 0


def cmd_sweep(a):
    _hdr('🔴 刷新率扫描（30/60/120/144Hz）')
    print('档位: ' + ' · '.join(SWEEP_RATES))
    print('\n断言: ' + ' · '.join(SWEEP_ASSERT))
    print('\n规则:')
    for r in SWEEP_RULE:
        print(f'   {r}')
    print('\nGFXReconstruct:')
    for g in GFXRECON_NOTE:
        print(f'   {g}')
    return 0


def cmd_bugfeat(a):
    _hdr('🔴 bug 变 feature（**历史决策**）')
    for f in BUGFEAT_FIELDS:
        print(f'   · {f}')
    print(f'\n   {BUGFEAT_RULE}')
    return 0


def cmd_init(a):
    os.makedirs(os.path.dirname(a.init) or '.', exist_ok=True)
    with open(a.init, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow([k for k, _ in FIELDS])
        w.writerow(['TODO'] * len(FIELDS))
    print(f'已生成运气/技巧表: {a.init}')
    print('\n⚠️ 十域：luck4 / pity / pseudo / nearmiss / audit / intent / '
          'framebase / closure / sweep / bugfeat')
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

    mismatch, no_legacy = [], []
    for i, r in enumerate(rows, 1):
        m = g(r, 'match').lower()
        if m not in ('yes', 'y', 'true', '是', '一致'):
            mismatch.append(i)
        if not g(r, 'legacy_value') or g(r, 'legacy_value') == 'TODO':
            no_legacy.append(i)

    print('=' * 76)
    print(f'运气/技巧 · {len(rows)} 条')
    print('=' * 76)
    if mismatch:
        print(f'\n🚫 **不一致** {len(mismatch)} 条（行 {mismatch[:15]}）')
    if no_legacy:
        print(f'\n❌ {len(no_legacy)} 条缺**原版值**（行 {no_legacy[:15]}）')

    if not (mismatch or no_legacy):
        print('\n✅ 运气/技巧：一致且原版值完整')

    print('\n🔑 **保底必须记六种语义；险胜要写清谁获得戏剧性信息。**')
    print('   **技巧要有帧基准声明；30/60/120/144Hz 都要扫。**')
    print('   **图形重放 ≠ 模拟一致性。**')
    return 1 if (a.gate_check and (mismatch or no_legacy)) else 0


def main():
    ap = argparse.ArgumentParser(description='运气体验与技巧天花板')
    ap.add_argument('--luck4', action='store_true')
    ap.add_argument('--pity', action='store_true')
    ap.add_argument('--pseudo', action='store_true')
    ap.add_argument('--nearmiss', action='store_true')
    ap.add_argument('--audit', action='store_true')
    ap.add_argument('--intent', action='store_true')
    ap.add_argument('--framebase', action='store_true')
    ap.add_argument('--closure', action='store_true')
    ap.add_argument('--sweep', action='store_true')
    ap.add_argument('--bugfeat', action='store_true')
    ap.add_argument('--init')
    ap.add_argument('--check')
    ap.add_argument('--gate-check', action='store_true')
    a = ap.parse_args()
    fns = {'luck4': cmd_luck4, 'pity': cmd_pity, 'pseudo': cmd_pseudo,
           'nearmiss': cmd_nearmiss, 'audit': cmd_audit,
           'intent': cmd_intent, 'framebase': cmd_framebase,
           'closure': cmd_closure, 'sweep': cmd_sweep,
           'bugfeat': cmd_bugfeat}
    for k, fn in fns.items():
        if getattr(a, k):
            return fn(a)
    if a.init:
        return cmd_init(a)
    if a.check:
        return cmd_check(a)
    print('❌ 需要 --luck4 / --pity / --pseudo / --nearmiss / --audit / '
          '--intent / --framebase / --closure / --sweep / --bugfeat / '
          '--init / --check 之一')
    return 2


if __name__ == '__main__':
    sys.exit(main())
