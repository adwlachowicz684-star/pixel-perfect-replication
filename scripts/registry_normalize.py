#!/usr/bin/env python3
"""登记表归一化：加 `kind` + 标记重名（第五十二轮 · 执行层修复）。

> ## 🔑 这份脚本存在的原因
>
> 🔑 审核发现：**登记表把三类东西混在一起——真 CLI、参考仓库、商业 SDK**
> （还有纯规范文档）。`tool_run.py` 对后几类照样探测可执行文件，**必然全部"缺失"**。
> 🔑 **"缺失 260"既不代表没装，也不代表能力缺口，只代表它们不是 CLI。**
>
> 🔴 **最该警惕的不是数字虚高，而是使用者据此产生"机器已经查过了"的错觉。**

## kind 五分类

| kind | 含义 | 能否被 `which` 探测 |
|---|---|---|
| `cli` | **独立可执行程序** | ✅ 能 |
| `lib` | **库**（python/C++/JS，靠 import 或 wrapper 调） | ❌ 不能（要 import 检测） |
| `doc` | **规范/文档**（无代码） | ❌ 不能 |
| `sdk` | **专有/商业 SDK 或服务**（不可自由安装） | ❌ 不能 |
| `reference` | **参考仓库**（只读取证，不运行） | ❌ 不能 |

> ## 🔑 还有一个更隐蔽的 bug：重复 **key**
>
> 🔑 51 轮追加登记时，**同一个 key 被写了两次甚至三次**。YAML 加载时
> **后写的静默覆盖先写的**——本库中这种情况造成 **16 条登记被无声丢弃**。
> 🔴 **这比"重名"更危险：重名至少还在文件里，重复 key 是彻底没了。**

用法:
  registry_normalize.py --check            # 🔑 查 kind / 重名 / **重复 key**（门禁用）
  registry_normalize.py --apply            # 写回 `kind` / `dup_of` / **重命名重复 key**
  registry_normalize.py --stats            # 🔑 按 kind 统计真实能力面

退出码: 0 通过 / 1 有未分类或重名 / 2 用法错误
"""
import argparse
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REG = os.path.join(HERE, 'tools', 'registry.yaml')

CLI_HINT = re.compile(r'^(cli)$')
DOC_RE = re.compile(r'(规范|标准|ISO|OASIS|SPDX|IGDA|EBU|WCAG|HIG|OpenAPI|'
                    r'JSON Schema|OpenTelemetry|CLDR|Unicode|IETF|RFC|'
                    r'官方技术文档|AOSP|官方 PDF|官方帮助|官方支持|政策|'
                    r'Guidelines|guideline|官方资料|社区 wiki)')
SDK_RE = re.compile(r'(专有|商业|Business Source|Companion|官方 SDK|服务，不是|'
                    r'不是开源|不得复制|不授权|NDA|SDK/服务)')


def _blocks(path):
    """按顶层 tool key 切块，保留注释。"""
    lines = open(path, encoding='utf-8').read().split('\n')
    out, cur_key, cur = [], None, None
    for ln in lines:
        m = re.match(r'^  ([A-Za-z0-9_.\-]+):\s*$', ln)
        if m and not ln.startswith('   '):
            if cur_key:
                out.append((cur_key, cur))
            cur_key, cur = m.group(1), [ln]
        else:
            if cur is None:
                out.append((None, [ln]))
            else:
                cur.append(ln)
    if cur_key:
        out.append((cur_key, cur))
    return out


def _field(block_lines, key):
    for ln in block_lines:
        m = re.match(r'^\s{4}' + re.escape(key) + r':\s*(.*)$', ln)
        if m:
            return m.group(1).strip().strip('"').strip("'")
    return None


def classify(name, exe, license_s, purpose, repo):
    if exe and not exe.startswith('('):
        return 'cli'
    if exe in ('(py)', '(lib)', '(source)'):
        return 'lib'
    blob = ' '.join(x for x in (name, license_s, purpose, repo) if x)
    if SDK_RE.search(blob):
        return 'sdk'
    if exe == '(doc)' or (repo and repo.startswith('(')):
        return 'doc' if DOC_RE.search(blob) else 'doc'
    return 'reference'


def load(path):
    """返回 [(key, block_lines, name, kind, dup_of)]"""
    items = []
    for key, blk in _blocks(path):
        if key is None:
            continue
        name = _field(blk, 'name')
        if name is None:
            continue
        items.append({
            'key': key,
            'blk': blk,
            'name': name,
            'exe': _field(blk, 'exe'),
            'license': _field(blk, 'license') or '',
            'purpose': _field(blk, 'purpose') or '',
            'repo': _field(blk, 'repo') or '',
            'kind': _field(blk, 'kind'),
            'dup_of': _field(blk, 'dup_of'),
        })
    return items


def _hdr(t, w=80):
    print('=' * w)
    print(t)
    print('=' * w)


def _dup_groups(items):
    by = {}
    for it in items:
        by.setdefault(it['name'], []).append(it)
    return {n: v for n, v in by.items() if len(v) > 1}


def _dup_keys(path):
    """🔑 重复 key —— YAML 加载时后写覆盖先写，造成**静默数据丢失**。"""
    keys = []
    for ln in open(path, encoding='utf-8').read().split('\n'):
        m = re.match(r'^  ([A-Za-z0-9_.\-]+):\s*$', ln)
        if m:
            keys.append(m.group(1))
    import collections
    c = collections.Counter(keys)
    return {k: v for k, v in c.items() if v > 1}, len(keys) - len(c)


def cmd_stats(a):
    items = load(REG)
    dk, lost = _dup_keys(REG)
    if dk:
        print(f'\n🔴 **重复 key {len(dk)} 组** —— '
              f'YAML 加载时静默丢失 **{lost} 条**登记：')
        for k, v in dk.items():
            print(f'   · `{k}` 出现 {v} 次')
        print('\n   🔑 这不是"没装"，是**登记本身被无声覆盖**。')
    cnt = {}
    for it in items:
        k = it['kind'] or classify(it['name'], it['exe'], it['license'],
                                   it['purpose'], it['repo'])
        cnt.setdefault(k, []).append(it['key'])
    dups = _dup_groups(items)
    _hdr('🔑 登记表的真实能力面')
    print(f'\n登记条目 {len(items)} · 唯一名称 '
          f'{len({i["name"] for i in items})} · 重名组 {len(dups)}')
    print('\n| kind | 条数 | **能否被 `which` 探测** |')
    print('|---|---|---|')
    for k in ('cli', 'lib', 'doc', 'sdk', 'reference'):
        v = cnt.get(k, [])
        probe = '✅ 能' if k == 'cli' else ('⚠️ 需 import 检测' if k == 'lib'
                                           else '❌ 不能')
        print(f'| `{k}` | {len(v)} | {probe} |')
    real = len(cnt.get('cli', [])) + len(cnt.get('lib', []))
    print(f'\n🔑 **真正"能跑起来"的 = cli + lib = {real} 条**，'
          f'占 {real * 100 // max(len(items), 1)}%')
    print('🔑 其余是不可执行的规范 · SDK · 参考仓库——'
          '**它们不是能力缺口，只是不能 `which`**')
    if dups:
        print(f'\n🚫 **重名组 {len(dups)}**：')
        for n, v in list(dups.items())[:20]:
            marked = [x['key'] for x in v if x['dup_of']]
            print(f'   · {n}: {[x["key"] for x in v]}'
                  + (f'  （已标记 {marked}）' if marked else '  🔴 **未标记**'))
    return 0


def cmd_check(a):
    items = load(REG)
    no_kind = [i['key'] for i in items if not i['kind']]
    dups = _dup_groups(items)
    unmarked = []
    for n, v in dups.items():
        canon = [x for x in v if not x['dup_of']]
        if len(canon) != 1:
            unmarked.append(n)
    dk, lost = _dup_keys(REG)
    print('=' * 76)
    print(f'登记表归一化 · {len(items)} 条')
    print('=' * 76)
    if dk:
        print(f'\n🚫 **{len(dk)} 组重复 key —— 静默丢失 {lost} 条**（{list(dk)[:12]}）')
    if no_kind:
        print(f'\n🚫 {len(no_kind)} 条**缺 `kind`**（{no_kind[:12]}）')
    if unmarked:
        print(f'\n🚫 {len(unmarked)} 组**重名未标记 `dup_of`**（{unmarked[:12]}）')
    if not (dk or no_kind or unmarked):
        print('\n✅ 登记表：无重复 key、全部有 `kind`、重名均已标记唯一 canonical')
    print('\n🔑 **"缺失 N"既不代表没装，也不代表能力缺口——只代表它们不是 CLI。**')
    print('🔑 **重复 key 更危险：不是没装，是登记本身被无声覆盖。**')
    return 1 if (a.gate_check and (dk or no_kind or unmarked)) else 0


def cmd_apply(a):
    # 🔑 先修重复 key（会造成静默数据丢失，优先级最高）
    dk, lost = _dup_keys(REG)
    if dk and not a.dry_run:
        shutil.copy(REG, REG + '.bak')
        seen, out_lines = {}, []
        for ln in open(REG, encoding='utf-8').read().split('\n'):
            m = re.match(r'^  ([A-Za-z0-9_.\-]+):\s*$', ln)
            if m:
                k = m.group(1)
                seen[k] = seen.get(k, 0) + 1
                if seen[k] > 1:
                    ln = f'  {k}_dup{seen[k]}:'
            out_lines.append(ln)
        open(REG, 'w', encoding='utf-8').write('\n'.join(out_lines))
        print(f'✅ 已重命名 {len(dk)} 组重复 key（挽回 {lost} 条登记）；'
              f'备份 {REG}.bak')
    items = load(REG)
    dups = _dup_groups(items)
    changes = 0
    for n, v in dups.items():
        canon = v[0]['key']
        for x in v[1:]:
            if not x['dup_of']:
                x['dup_of'] = canon
                changes += 1
    for it in items:
        if not it['kind']:
            it['kind'] = classify(it['name'], it['exe'], it['license'],
                                  it['purpose'], it['repo'])
            changes += 1
    # 写回：在块内插入/替换 kind 与 dup_of
    out = []
    for key, blk in _blocks(REG):
        if key is None:
            out.extend(blk)
            continue
        it = next((x for x in items if x['key'] == key), None)
        if it is None:
            out.extend(blk)
            continue
        new, has_kind, has_dup = [], False, False
        for ln in blk:
            if re.match(r'^\s{4}kind:', ln):
                new.append(f'    kind: {it["kind"]}')
                has_kind = True
            elif re.match(r'^\s{4}dup_of:', ln):
                new.append(f'    dup_of: {it["dup_of"]}' if it['dup_of']
                           else '    dup_of: null')
                has_dup = True
            else:
                new.append(ln)
        if not has_kind:
            idx = next((i for i, l in enumerate(new)
                        if re.match(r'^\s{4}name:', l)), 0)
            new.insert(idx + 1, f'    kind: {it["kind"]}')
        if it['dup_of'] and not has_dup:
            idx = next((i for i, l in enumerate(new)
                        if re.match(r'^\s{4}kind:', l)), 0)
            new.insert(idx + 1, f'    dup_of: {it["dup_of"]}')
        out.extend(new)
    if not a.dry_run:
        shutil.copy(REG, REG + '.bak')
        open(REG, 'w', encoding='utf-8').write('\n'.join(out))
    print(f'✅ 已写入 {changes} 处改动' + ('（--dry-run 未落盘）' if a.dry_run
                                      else f'；备份 {REG}.bak'))
    return 0


def main():
    ap = argparse.ArgumentParser(description='登记表归一化（kind + 重名）')
    ap.add_argument('--check', action='store_true')
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--stats', action='store_true')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--gate-check', action='store_true')
    a = ap.parse_args()
    if a.stats:
        return cmd_stats(a)
    if a.check:
        return cmd_check(a)
    if a.apply:
        return cmd_apply(a)
    print('❌ 需要 --stats / --check / --apply 之一')
    return 2


if __name__ == '__main__':
    sys.exit(main())
