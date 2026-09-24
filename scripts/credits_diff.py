#!/usr/bin/env python3
"""Credits 演化 diff（第五十一轮 C）。

> 🔑 **补丁会改变可归因事实，最合理的表示是带证据链的 diff，而不是一份名单。**
> 🔑 **复刻项目不应把 Credits 当作文本 dump**，而应至少保存
> `asset_path` · `version_range` · `query_name` · `role` ·
> `evidence_type` · `evidence_url/artifact_sha256`。

用法:
  credits_diff.py --rule     # 🔑 七类事件 + 证据链
  credits_diff.py --case     # 🔑 **可验证闭环案例**
  credits_diff.py --policy   # 🔑 **离职者仍署名 / 原团队先列 / 补丁修正**
  credits_diff.py --disc     # **众筹支持者：只标 claimed，不直接定 bug**
  credits_diff.py --ids      # **EIDR/ISNI 只作 external id，不作本地主键**
  credits_diff.py --init ledger/credits_v1.csv
  credits_diff.py --diff ledger/credits_v1.csv ledger/credits_v2.csv --gate

退出码: 0 通过 / 1 有未附证据的删除或排序变化 / 2 用法错误
"""
import argparse
import csv
import os
import sys

RULE = '🔑 **补丁会改变可归因事实，最合理的表示是带证据链的 diff，'
'而不是一份名单。**'
EVENT_TYPES = ['added', 'removed', 'renamed', 'role_changed', 'order_changed',
               'spelling_fixed', 'section_moved']
CONFIDENCE = ['confirmed', 'inferred', 'claimed', 'disputed']
MIN_FIELDS = '`asset_path` · `version_range` · `query_name` · `role` · '
'`evidence_type` · `evidence_url/artifact_sha256`'

CASE = '🔑 **可验证闭环案例**：某作 Java 版 issue 标题即'
'"Hyper Potions (Ian Tsuchiura) is not mentioned in the credits and splash texts"；'
'🔑 影响 `1.21.7 Release Candidate 1` · `1.21.7 Release Candidate 2` · '
'`1.21.8 Release Candidate 1`，状态 Fixed，修复版本 `1.21.11 Pre-Release 1`；'
'🔑 复现步骤给出 `assets/minecraft/texts/credits.json` 与 `splashes.txt` 的搜索路径'
CASE_NOTE = '🔑 这是"**遗漏被承认并修复**"的证据；'
'🔴 **但它属社区共识确认、非官方人员名单主数据库，'
'不能单独证明该人员的全部劳动关系或完整角色**'

POLICY = '🔑 **署名规范把 Credits 从礼仪问题提升为可修正的产品缺陷**：'
'🔑 **离职员工（含承包商 · 自由职业者 · 外包 · 兼职 · 全职）在发售后仍保留署名**；'
'🔑 **移植 · 重制 · remaster · adaptation/re-release 的原团队须单独列出并排在首位**；'
'🔑 **发布后发现错误时，应能提交 issue，并在合理范围内通过后续 patch/hotfix 修正**；'
'🔑 **每条署名至少包含 first name · last name 与 role**'
POLICY_STAT = '🔑 调查数据（582 人中有 299 人"从未/很少/有时"获得官方署名，'
'83.1% 不确定雇主是否有署名政策）'
'🔑 **说明为什么单靠发售日截图会永久丢失信息**'
DISPUTE = '🔑 **重制版保留/删除原团队有可引用公开案例**：某重制版仅以'
'"based on the work of the original development staff"概括原团队，'
'这是该团队第二次被排除在重制版完整名单外。'
'🔑 支持字段 `original_team_section_present` · `original_individual_names` · '
'`remaster_original_header` · `public_dispute_evidence`，'
'🔴 **但不能把"粉丝/媒体认为不公平"直接写成"开发商违法"**'

BACKER_RULE = '🔑 **离职 · 承包商 · 众筹支持者的名单处理应记录状态，'
'🔴 不应靠姓名猜归属。**'
BACKER_ITEMS = [
    ('某本地化制作人名字被移除', '公司随后公开"**只有在职员工才署名**"政策并引发争议 → '
     '🔑 **作为 policy artifact 与名单差异证据**，🔴 **仍需官方名单原件逐版核验**'),
    ('某作众筹支持者反馈名字缺失', '🔑 **只应标记为 `claimed_credit_omission`，'
     '🔴 不直接认定为 bug**'),
    ('某作众筹奖励 "$100 Backer Credits"', '🔑 **可从主菜单查看 · 可跳到本人名字 · '
     '以闪烁提示** → **可复刻的具体交互模式，不是必须照抄的规则**'),
]

IDS_RULE = '🔑 **没有稳定、跨厂商的开放 Credits schema 占主导地位。**'
IDS_ITEMS = [
    ('EIDR', '娱乐作品标识符注册表，能标识 Movie/TV/Interactive 等工作及'
     '参与者/组织与角色，🔴 **但面向视听作品元数据而非游戏团队 build-to-credit 追踪**'),
    ('ISNI', '可唯一标识作者 · 作曲家 · 表演者 · 组织等 public identity，'
     '并处理**笔名 · 替代拼写 · 跨语言写法**；'
     '🔑 适合做 `person_external_id` 候选，🔴 **不作本地名单主键**'),
]
IDS_NO = '🔴 **本轮未确认名为 "Open Credits" 的稳定跨游戏 schema**；'
'第三方站点与工具包示例 CSV 只能作辅助数据源/导出格式，'
'🔴 **不能声称它们就是官方标准**'
SCRAPE_NO = '❌ **自动网络抓取第三方名单只作发现源；'
'🔑 必须与 binary/asset/官方补丁二次核验**'

CONFLICTS = [
    '❌ **把 Credits 当文本 dump 保存**（应存资产路径 + 版本范围 + 证据链）',
    '❌ **删除原团队署名当"品牌更新"**（是署名缺陷）',
    '❌ **离职即移除署名**',
    '❌ **把媒体/粉丝争议直接写成法律结论**',
    '❌ **把众筹支持者"自述缺失"直接认定为 bug**（应标 claimed）',
    '❌ **自动网络抓取第三方名单当官方标准**',
    '❌ 为版式整齐删除/合并/改正支持者姓名',
]

FIELDS = [
    ('person_key', '**内部稳定键**（🔴 不得仅用显示名）'),
    ('canonical_name', '规范名（given/family/middle/display）'),
    ('external_ids', '外部 ID（ISNI/EIDR/Wikidata，可空）'),
    ('role', '角色（可多角色）'),
    ('order_index', '**原作品中的稳定序号**'),
    ('credit_section', '段（original/remaster/port/localization/voice/'
                       'special_thanks/backer）'),
    ('game_version', '游戏版本'),
    ('build_hash', '构建哈希'),
    ('evidence_url', '**证据链接**'),
]


def _hdr(t, w=80):
    print('=' * w)
    print(t)
    print('=' * w)


def cmd_rule(a):
    _hdr('🔑 Credits diff（**带证据链的事件**）')
    print(f'   {RULE}')
    print(f'\n最小字段: {MIN_FIELDS}')
    print(f'\n七类事件: ' + ' · '.join(EVENT_TYPES))
    print(f'\n置信度: ' + ' · '.join(CONFIDENCE))
    print(f'\n   ❌ **删除与排序变化必须附证据**')
    return 0


def cmd_case(a):
    _hdr('🔑 可验证闭环案例')
    print(f'   {CASE}')
    print(f'\n   {CASE_NOTE}')
    return 0


def cmd_policy(a):
    _hdr('🔑 署名政策（**可修正的产品缺陷**）')
    print(f'   {POLICY}')
    print(f'\n   {POLICY_STAT}')
    print(f'\n   {DISPUTE}')
    return 0


def cmd_disc(a):
    _hdr('众筹与离职（**记录状态，不猜归属**）')
    print(f'   {BACKER_RULE}')
    for k, v in BACKER_ITEMS:
        print(f'\n   【{k}】\n      {v}')
    return 0


def cmd_ids(a):
    _hdr('外部标识（**不作本地主键**）')
    print(f'   {IDS_RULE}')
    for k, v in IDS_ITEMS:
        print(f'\n   【{k}】\n      {v}')
    print(f'\n   {IDS_NO}')
    print(f'\n   {SCRAPE_NO}')
    return 0


def cmd_init(a):
    os.makedirs(os.path.dirname(a.init) or '.', exist_ok=True)
    with open(a.init, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow([k for k, _ in FIELDS])
        w.writerow(['TODO'] * len(FIELDS))
    print(f'已生成 Credits 名单快照: {a.init}')
    print('\n⚠️ `person_key` 必须是**内部稳定键**，🔴 不得仅用显示名')
    print('\n⚠️ 每次版本更新都保存**完整名单快照**，再跑 --diff')
    return 0


def _load(p):
    if not os.path.exists(p):
        print(f'❌ 文件不存在: {p}')
        sys.exit(2)
    with open(p, encoding='utf-8', errors='replace', newline='') as f:
        return list(csv.DictReader(f))


def cmd_diff(a):
    old = _load(a.old)
    new = _load(a.new)

    def g(r, k):
        return (r.get(k) or '').strip()

    o = {g(r, 'person_key'): r for r in old}
    n = {g(r, 'person_key'): r for r in new}
    added = [k for k in n if k not in o]
    removed = [k for k in o if k not in n]
    events = []
    for k in added:
        events.append(('added', k, '新署名', n[k].get('evidence_url', '')))
    for k in removed:
        events.append(('removed', k, '🔴 **署名移除**', o[k].get('evidence_url', '')))
    for k in set(o) & set(n):
        if g(o[k], 'order_index') != g(n[k], 'order_index'):
            events.append(('order_changed', k,
                           f"{g(o[k],'order_index')}→{g(n[k],'order_index')}",
                           n[k].get('evidence_url', '')))
        if g(o[k], 'role') != g(n[k], 'role'):
            events.append(('role_changed', k,
                           f"{g(o[k],'role')}→{g(n[k],'role')}",
                           n[k].get('evidence_url', '')))
        if g(o[k], 'canonical_name') != g(n[k], 'canonical_name'):
            events.append(('renamed', k,
                           f"{g(o[k],'canonical_name')}→{g(n[k],'canonical_name')}",
                           n[k].get('evidence_url', '')))
        if g(o[k], 'credit_section') != g(n[k], 'credit_section'):
            events.append(('section_moved', k,
                           f"{g(o[k],'credit_section')}→{g(n[k],'credit_section')}",
                           n[k].get('evidence_url', '')))

    def has_ev(u):
        return bool(u) and u.strip() != 'TODO'

    no_ev = [e for e in events
             if e[0] in ('removed', 'order_changed', 'section_moved')
             and not has_ev(e[3])]
    print('=' * 76)
    print(f'Credits diff · {a.old} → {a.new} · {len(events)} 个事件')
    print('=' * 76)
    for t, k, d, ev in events:
        mark = ('✅' if has_ev(ev)
                else ('🚫' if t in ('removed', 'order_changed',
                                    'section_moved') else '⚠️'))
        print(f'   {mark} [{t}] {k}  {d}'
              + (f'  <{ev[:48]}>' if ev else ''))
    if removed:
        print(f'\n🚫 **署名移除 {len(removed)} 人** —— '
              '🔴 **离职不是移除理由；删除原团队是署名缺陷**')
    if no_ev:
        print(f'\n🚫 {len(no_ev)} 个**删除/排序/跨段事件缺证据链接**')
    if not events:
        print('\n   两版名单一致')
    if not (removed or no_ev):
        print('\n✅ Credits diff：无未附证据的删除或排序变化')

    print('\n🔑 **Credits 是版本化证据链，不是美术文案。**')
    print('   🔴 **删除原团队署名不是"品牌更新"。**')
    print('   🔑 **离职者仍保留署名；错误应在后续 patch 修正。**')
    return 1 if (a.gate_check and (removed or no_ev)) else 0


def main():
    ap = argparse.ArgumentParser(description='Credits 演化 diff')
    ap.add_argument('--rule', action='store_true')
    ap.add_argument('--case', action='store_true')
    ap.add_argument('--policy', action='store_true')
    ap.add_argument('--disc', action='store_true')
    ap.add_argument('--ids', action='store_true')
    ap.add_argument('--init')
    ap.add_argument('--diff', nargs=2, metavar=('OLD', 'NEW'))
    ap.add_argument('--gate-check', action='store_true')
    a = ap.parse_args()
    fns = {'rule': cmd_rule, 'case': cmd_case, 'policy': cmd_policy,
           'disc': cmd_disc, 'ids': cmd_ids}
    for k, fn in fns.items():
        if getattr(a, k):
            return fn(a)
    if a.init:
        return cmd_init(a)
    if a.diff:
        a.old, a.new = a.diff
        return cmd_diff(a)
    print('❌ 需要 --rule / --case / --policy / --disc / --ids / --init '
          '/ --diff OLD NEW 之一')
    return 2


if __name__ == '__main__':
    sys.exit(main())
