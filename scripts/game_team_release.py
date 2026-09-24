#!/usr/bin/env python3
"""组织协作 + 终止条件 + 反脆弱 + 复刻 ROI（第二十轮 C / D / F / G）。

**🔑 C 类核心**：
> 关键是**单点所有权与双向交接**，而非增加会议。
> 🔴 最易失真的正是"**看似已经交接**"的中间产物 ——
> 美术交付贴图 ≠ 交付 mipmap/压缩/sRGB/过滤/色键/各 LOD/碰撞代理。

**🔑 D 类核心**：
> **发布定义必须由"证据账本"决定，终止条件不能只是负责人喊停。**
> 🔴 用"差不多了""只剩美术"替代硬门槛，**会把隐性风险推给玩家**。
> 🔑 **"够好"不是降低 must-match，而是提高偏离成本并限制偏离寿命。**

**🔑 F 类核心**：
> 🔴 **82 个门禁可能全是假的** —— 必须**故意改坏**验证测试有效。

用法:
  game_team_release.py --owners  # 🔴 清单**所有权矩阵**
  game_team_release.py --handoff # 🔴 交接**双向签收**
  game_team_release.py --team    # 最小可行团队
  game_team_release.py --onboard # **72 小时上手路径**
  game_team_release.py --progress # 🔴 进度按**证据闭环**不是百分比
  game_team_release.py --readiness # 🔴 发布就绪**六项硬门槛**
  game_team_release.py --good    # "够好"= 提高偏离成本
  game_team_release.py --legacy  # 🔴 遗留项**公开可观测可恢复**
  game_team_release.py --budget  # 🔴 预算闸门**防永远做不完**
  game_team_release.py --post    # 发布后**只允许四类**
  game_team_release.py --chaos   # 🔴 混沌：**坏构建能否被检出**
  game_team_release.py --roi     # 🔴 复刻 ROI 账本
  game_team_release.py --init ledger/team_release.csv
  game_team_release.py --check ledger/team_release.csv --gate

退出码: 0 通过 / 1 缺项 / 2 用法错误
"""
import argparse
import csv
import os
import sys

# 🔴 所有权
OWNER_FIELDS = [
    '**primary_owner**', '**secondary_owner**', 'source_evidence',
    '**acceptance_owner**', '**last_verified_at**', 'change_reviewers',
]

OWNER_MAP = [
    ('**美术**', '视觉规格 · 采样 · 色域 · 资产导入基线'),
    ('**关卡**', '触发器 · 相机 · 音频区域 · 路径规格'),
    ('**程序**', '时间域 · 输入 · 网络 · 物理 · 崩溃证据'),
    ('**QA**', '复现步骤 · 机器环境 · 验收报告'),
    ('**制作人**', '范围 · 里程碑 · 发布风险'),
    ('**构建负责人**', '`build_manifest`'),
]

OWNER_RULE = '🔑 每个规格/资产/测试对象都必须有上述六字段'

# 🔴 交接
HANDOFF_FIELDS = [
    '**evidence_artifact_uri**', '**can_reproduce**', 'assumptions',
    '**unknowns**', 'acceptance_test', '**owner_signatures**',
]

HANDOFF_TRAPS = [
    ('美术交付贴图', '≠ 交付 mipmap · 压缩格式 · sRGB · 过滤 · 色键 · '
     '各 LOD · **碰撞代理**'),
    ('程序交付参数', '≠ 交付原版行为视频 · 输入/时间域 · 失败注入 · 降级'),
    ('QA 交付测试视频', '≠ 交付可重放输入 · 版本 · 随机种子 · 帧号 · '
     '**环境锁定**'),
]

HANDOFF_RULE = [
    '🔴 接收方**不只签"收到"**，还要签'
    '"**能在目标环境复现源证据并解释未知字段**"',
    '🔑 这正是 `preserve_unknown` 的组织落地 —— '
    '**未知不能由交接自动消失，只能随责任人继续存在**',
]

# 团队
TEAM_MIN = [
    '1 名**规格/复现负责人**（原版取证与契约）',
    '1 名**引擎/玩法负责人**',
    '1 名**图形/资产负责人**',
    '1 名 **QA/兼容性负责人**',
]

TEAM_NOTE = [
    '🔑 构建、音频、网络、工具链可**由兼任者承担**，'
    '但**每个子系统仍须有主负责人和备选人**',
    '🔑 达到"能发布"还需要**版本、发布、回滚和事故响应**责任人',
]

# 上手
ONBOARD = [
    ('2 小时', '跑通**可复现构建与干净安装**'),
    ('4 小时', '完成一个 **must-match 修复**'),
    ('4 小时', '复现一个**已知原版 bug**'),
    ('6 小时', '完成一次**跨职能交接**'),
    ('其余', '阅读**证据链和录屏索引**'),
]

ONBOARD_RULE = [
    '🔑 新人加入**不能从读全部 GDD 开始**',
    '🔑 每个任务后签"**理解确认**" —— '
    '**防止文档存在却无人真正承担**',
]

# 🔴 进度
PROGRESS_COLS = [
    '**Evidence captured**（已有证据）', '**Specified**（已写规格）',
    '**Implemented**（实现并本地通过）',
    '**Closed by acceptance**（验收闭环）',
]

PROGRESS_STATUS = ['已闭环', '未闭环', '**偏离批准**', '**遗留接受**']

PROGRESS_FIELDS = ['first_seen_at', '**last_verified_at**', 'next_review_at']

PROGRESS_RULE = [
    '🔴 进度必须按**证据闭环**而不是**完成百分比**呈现',
    '🔑 门禁应映射到 `contract_id`，显示上述四状态，**而不是 80% 完成**',
    '🔑 **像素级证据会过期** —— 原版补丁、驱动、操作系统、CPU/GPU 调度或'
    '**显示器刷新率变化**都可能改变基准',
]

# 🔴 发布就绪
READINESS_SIX = [
    '所有 **must-match 有证据且验收闭环**',
    '所有偏离有 **deviation_license 与二次批准**',
    '所有未知字段有**降级、占位或 `preserve_unknown`**',
    '**干净安装、首启、核心流程、存档迁移、卸载与升级**均闭环',
    '崩溃诊断能落包且能按 **build_id 重建环境**',
    '**无阻塞安全、稳定性和数据损坏风险**',
]

READINESS_STATUS = [
    'verified', 'degraded_approved', '**unknown_accepted**', 'failing',
    'exempted_post_release',
]

READINESS_FIELDS = [
    'contract_id', '**evidence_tier**', 'owner', 'verification_method',
    'last_passed_build', 'blocking_on_failure', 'current_status',
]

READINESS_RULE = [
    '🔴 若六项**任何一项为假**，发布状态**只能是 `not-shippable`**',
    '🔴 用"**差不多了**""**只剩美术**"替代硬门槛 → '
    '**会把隐性风险推给玩家**',
    '🔑 只有 `verified` 和**经批准的非阻塞项**可进入候选',
    '🔑 `unknown_accepted` 必须写出**玩家可见表现、风险、恢复路径和'
    '后续复刻计划**',
]

# 够好
GOOD_FIELDS = [
    'intended_player_effect', 'regression_risk', 'implementation_cost',
    'alternative_cost', '**reversibility**', 'target_version',
    'acceptance_test', '**post_release_owner**',
]

GOOD_HIGH = [
    '**不可逆偏离**', '**跨周目/存档影响**', '**外观变化**',
    '**输入延迟**', '**时间语义变化**',
]

GOOD_RULE = [
    '🔑 **"够好"不是降低 must-match，而是提高偏离成本并限制偏离寿命**',
    '🔑 上述五类**默认为更高审批等级**',
    '🔑 若某项是为了新引擎架构、性能或现代设备，'
    '**应明确写成"有意偏离"**，**不能因实现简单而被默认接受**',
]

# 🔴 遗留
LEGACY_FIELDS = [
    '**known_reproduction_gaps**', '**environment_specific_behavior**',
    'expected_next_verification', '**workaround**', '**data_safety**',
]

LEGACY_RULE = [
    '🔴 **发布说明不应只列"修复了什么"**，还应列出上述五类',
    '🔴 **不能把原版未复现的行为宣称成"完全一致"**',
    '🔑 未闭环项的默认状态是 `publicly_acknowledged`，'
    '**不得混入"已完成"统计**',
]

# 🔴 预算闸门
BUDGET_GATES = [
    '**maximum_additional_rounds**', '累计工时/预算', '玩家影响阈值',
    '**退出规则**',
]

BUDGET_RULE = [
    '🔑 **防止永远做不完，需要预算闸门而非无限返工**',
    '🔑 非阻塞项连续**两轮未通过**，且玩家可见差异低于阈值、'
    '存在可靠回退、后续可无损恢复 → `deferred_with_contract`',
    '🔑 `must-match` 在证据无法取得且无法安全降级 → '
    '`blocked_until_evidence`，**而不是不断猜测实现**',
    '🔑 每轮**必须有一个明确的停止判断** —— 沿用"风险驱动停止规则"的 '
    '3-2-1 思想，本轮新增"**剩余证据增量价值 / 下一轮成本**"比',
]

# 发布后
POST_FOUR = [
    '**安全/数据风险**',
    '**造成无法完成/读档损坏的回归**',
    '**原版新证据推翻既有 must-match**',
    '**经公开契约接受的玩家可见差异**',
]

POST_RULE = [
    '🔑 **发布后继续复刻 ≠ 无限补丁** —— 只允许上述四类',
    '🔑 其余 `should-match` 必须进入**有边界的后续版本**',
    '🔑 **跨周目契约高于新内容** —— 任何改变旧存档语义的复刻改动'
    '**要先迁移、灰度、可回滚**',
]

# 🔴 混沌
CHAOS_RULE = [
    '🔴 **82 个门禁可能全是假的** —— 必须**故意改坏**验证测试有效',
    '🔑 混沌工程验证的是"**坏构建能否被检出**"，'
    '不是"新构建是否更稳定"',
    '🔑 证据链要**自校验**：证据**是否被篡改**',
    '🔑 "**假如原版证据丢失**"：如何恢复',
]

# 🔴 ROI
ROI_RULE = [
    '🔴 **不是所有东西都值得像素级**',
    '🔑 ROI 按**玩家可感知性**与**可逆性**降级',
    '🔑 **"不值得"的判定标准**必须显式',
    '🔑 **复刻深度可动态调整**',
]

CONFLICTS = [
    '❌ 用"差不多了""只剩美术"替代硬门槛',
    '❌ 把未复现行为宣称成"完全一致"',
    '❌ 未闭环项混入"已完成"统计',
    '❌ 进度按**完成百分比**呈现',
    '❌ 交接只签"收到"',
    '❌ 未知由交接自动消失',
    '❌ **降低 must-match 来求"够好"**',
    '❌ 因实现简单就默认接受偏离',
    '❌ 无限返工不设预算闸门',
    '❌ 证据无法取得却不断猜测实现',
    '❌ 发布后无限补丁',
    '❌ **改变旧存档语义却不先迁移灰度回滚**',
    '❌ 门禁从未被故意改坏验证过',
    '❌ 所有东西都无条件像素级',
]

FIELDS = [
    ('item_id', '项编号'),
    ('domain', '域（owners / handoff / team / onboard / progress / '
               'readiness / good / legacy / budget / post / chaos / roi）'),
    ('legacy_value', '**原版值**'),
    ('new_value', '新引擎值'),
    ('match', '**是否一致**'),
    ('tolerance', '**允许偏差**'),
    ('owner', '**责任人 + 到期日**'),
]


def _hdr(t, w=80):
    print('=' * w)
    print(t)
    print('=' * w)


def cmd_owners(a):
    _hdr('🔴 清单所有权矩阵')
    print('字段: ' + ' · '.join(OWNER_FIELDS))
    print('\n分工:')
    for who, what in OWNER_MAP:
        print(f'   {who:<16} {what}')
    print(f'\n   {OWNER_RULE}')
    return 0


def cmd_handoff(a):
    _hdr('🔴 交接（**双向签收**）')
    print('字段: ' + ' · '.join(HANDOFF_FIELDS))
    print('\n最易失真的中间产物:')
    for k, why in HANDOFF_TRAPS:
        print(f'   {k:<18} {why}')
    print('\n规则:')
    for r in HANDOFF_RULE:
        print(f'   {r}')
    return 0


def cmd_team(a):
    _hdr('最小可行团队')
    for t in TEAM_MIN:
        print(f'   · {t}')
    print('\n说明:')
    for n in TEAM_NOTE:
        print(f'   {n}')
    return 0


def cmd_onboard(a):
    _hdr('72 小时上手路径')
    for t, what in ONBOARD:
        print(f'   {t:<8} {what}')
    print('\n规则:')
    for r in ONBOARD_RULE:
        print(f'   {r}')
    return 0


def cmd_progress(a):
    _hdr('🔴 进度（**证据闭环**不是百分比）')
    for c in PROGRESS_COLS:
        print(f'   · {c}')
    print('\n状态: ' + ' · '.join(PROGRESS_STATUS))
    print('\n字段: ' + ' · '.join(PROGRESS_FIELDS))
    print('\n规则:')
    for r in PROGRESS_RULE:
        print(f'   {r}')
    return 0


def cmd_readiness(a):
    _hdr('🔴 发布就绪（**六项硬门槛**）')
    for i, r in enumerate(READINESS_SIX, 1):
        print(f'   {i}. {r}')
    print('\n字段: ' + ' · '.join(READINESS_FIELDS))
    print('\n状态: ' + ' · '.join(READINESS_STATUS))
    print('\n规则:')
    for r in READINESS_RULE:
        print(f'   {r}')
    return 0


def cmd_good(a):
    _hdr('"够好"（**提高偏离成本**）')
    print('字段: ' + ' · '.join(GOOD_FIELDS))
    print('\n高审批等级: ' + ' · '.join(GOOD_HIGH))
    print('\n规则:')
    for r in GOOD_RULE:
        print(f'   {r}')
    return 0


def cmd_legacy(a):
    _hdr('🔴 遗留项（**公开可观测可恢复**）')
    for f in LEGACY_FIELDS:
        print(f'   · {f}')
    print('\n规则:')
    for r in LEGACY_RULE:
        print(f'   {r}')
    return 0


def cmd_budget(a):
    _hdr('🔴 预算闸门（**防永远做不完**）')
    for g in BUDGET_GATES:
        print(f'   · {g}')
    print('\n规则:')
    for r in BUDGET_RULE:
        print(f'   {r}')
    return 0


def cmd_post(a):
    _hdr('发布后（**只允许四类**）')
    for p in POST_FOUR:
        print(f'   · {p}')
    print('\n规则:')
    for r in POST_RULE:
        print(f'   {r}')
    return 0


def cmd_chaos(a):
    _hdr('🔴 混沌（**坏构建能否被检出**）')
    for r in CHAOS_RULE:
        print(f'   {r}')
    return 0


def cmd_roi(a):
    _hdr('🔴 复刻 ROI')
    for r in ROI_RULE:
        print(f'   {r}')
    return 0


def cmd_init(a):
    os.makedirs(os.path.dirname(a.init) or '.', exist_ok=True)
    with open(a.init, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow([k for k, _ in FIELDS])
        w.writerow(['TODO'] * len(FIELDS))
    print(f'已生成团队/发布表: {a.init}')
    print('\n⚠️ 十二域：owners / handoff / team / onboard / progress / '
          'readiness / good / legacy / budget / post / chaos / roi')
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

    mismatch, no_legacy, no_owner = [], [], []
    for i, r in enumerate(rows, 1):
        m = g(r, 'match').lower()
        if m not in ('yes', 'y', 'true', '是', '一致'):
            mismatch.append(i)
        if not g(r, 'legacy_value') or g(r, 'legacy_value') == 'TODO':
            no_legacy.append(i)
        ow = g(r, 'owner')
        if (not ow or ow == 'TODO'
                or ('到期' not in ow and '/' not in ow and '-' not in ow
                    and '~' not in ow)):
            no_owner.append(i)

    print('=' * 76)
    print(f'团队/发布 · {len(rows)} 条')
    print('=' * 76)
    if mismatch:
        print(f'\n🚫 **不一致** {len(mismatch)} 条（行 {mismatch[:15]}）')
    if no_legacy:
        print(f'\n❌ {len(no_legacy)} 条缺**原版值**（行 {no_legacy[:15]}）')
    if no_owner:
        print(f'\n🚫 {len(no_owner)} 条**缺责任人或到期日**'
              f'（行 {no_owner[:15]}）')

    if not (mismatch or no_legacy or no_owner):
        print('\n✅ 团队/发布：一致、原版值完整、有 owner 与到期日')

    print('\n🔑 **发布定义必须由证据账本决定，终止不能只是负责人喊停。**')
    print('   **"够好"不是降低 must-match，是提高偏离成本。**')
    print('   **没有故意改坏验证过，门禁可能全是假的。**')
    return 1 if (a.gate_check and (mismatch or no_legacy or no_owner)) else 0


def main():
    ap = argparse.ArgumentParser(description='组织协作与发布终止')
    ap.add_argument('--owners', action='store_true')
    ap.add_argument('--handoff', action='store_true')
    ap.add_argument('--team', action='store_true')
    ap.add_argument('--onboard', action='store_true')
    ap.add_argument('--progress', action='store_true')
    ap.add_argument('--readiness', action='store_true')
    ap.add_argument('--good', action='store_true')
    ap.add_argument('--legacy', action='store_true')
    ap.add_argument('--budget', action='store_true')
    ap.add_argument('--post', action='store_true')
    ap.add_argument('--chaos', action='store_true')
    ap.add_argument('--roi', action='store_true')
    ap.add_argument('--init')
    ap.add_argument('--check')
    ap.add_argument('--gate-check', action='store_true')
    a = ap.parse_args()
    fns = {'owners': cmd_owners, 'handoff': cmd_handoff, 'team': cmd_team,
           'onboard': cmd_onboard, 'progress': cmd_progress,
           'readiness': cmd_readiness, 'good': cmd_good,
           'legacy': cmd_legacy, 'budget': cmd_budget, 'post': cmd_post,
           'chaos': cmd_chaos, 'roi': cmd_roi}
    for k, fn in fns.items():
        if getattr(a, k):
            return fn(a)
    if a.init:
        return cmd_init(a)
    if a.check:
        return cmd_check(a)
    print('❌ 需要 --owners / --handoff / --team / --onboard / --progress / '
          '--readiness / --good / --legacy / --budget / --post / --chaos / '
          '--roi / --init / --check 之一')
    return 2


if __name__ == '__main__':
    sys.exit(main())
