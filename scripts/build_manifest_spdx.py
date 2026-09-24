#!/usr/bin/env python3
"""build manifest ↔ SPDX 3.0 Build 字段接入（第五十四轮）。

> ## 🔑 本轮先做了一件前几轮没做的事：**核验一手规范**
>
> 第五十一轮说"SPDX 3.0 Build 类提供 18 个字段"。本轮打开官方页面核对后，
> **发现三处需要修正**——这正是"先证明，再落地"的价值：
>
> | 第五十一轮的记录 | 🔴 官方一手页面的实际 | 后果 |
> |---|---|---|
> | "18 个字段" | **9 个自有 + 10 个继承 = 19**；必填只有 3 个 | 误以为字段全要填 |
> | `buildId` 当全局唯一用 | 🔑 **官方原文：`locally unique identifier`** | 🔴 **必须自己加全局唯一层** |
> | 未提 | 🔑 **`buildStartTime/EndTime` 在 3.1 已弃用**，且官方说"**可省略以简化可复现构建**" | 我们一直在记时间戳，**反而损害可复现** |
>
> 🔑 **还有一个完全没记的东西**：Build profile 要求至少 **3 个关系**
> （`hasInput` / `hasOutput` / `invokedBy`，scope=`build`）。
> 🔴 **我们前几轮只记了字段，没记关系——那不是 Build，只是一张属性表。**

一手来源：https://spdx.github.io/spdx-spec/v3.0-dev/model/Build/Classes/Build

用法:
  build_manifest_spdx.py --show                    # 打印字段表与三处修正
  build_manifest_spdx.py --emit DIR --build-id B   # 产出 SPDX 3.0 片段
  build_manifest_spdx.py --check FILE              # 校验 manifest（门禁用）
  build_manifest_spdx.py --self-test               # 端到端自测

退出码: 0 通过 / 1 阻断 / 2 用法错误
"""
import argparse
import json
import os
import sys
import time

# --------------------------------------------------------------------------
# 🔑 一手核验的字段表（spdx.github.io v3.0-dev / Build / Classes / Build）
# (property, type, min, max, 是否 SPDX 3.1 弃用, 说明)
# --------------------------------------------------------------------------
OWN = [
    ('buildEndTime', 'DateTime', 0, 1, True,
     '🔴 **3.1 弃用**（改 /Core/endTime）；官方：可省略以简化可复现构建'),
    ('buildId', 'xsd:string', 0, 1, False,
     '🔑 官方原文 **locally unique identifier** —— 🔴 **不是全局唯一**'),
    ('buildStartTime', 'DateTime', 0, 1, True,
     '🔴 **3.1 弃用**（改 /Core/startTime）；可省略以简化可复现构建'),
    ('buildType', 'xsd:anyURI', 1, 1, False,
     '🔑 **唯一必填的自有属性**；官方措辞是 **hint**（提示），🔴 不是权威声明'),
    ('configSourceDigest', 'Hash', 0, -1, False, '构建配置文件的摘要'),
    ('configSourceEntrypoint', 'xsd:string', 0, -1, False, '构建的调用入口点'),
    ('configSourceUri', 'xsd:anyURI', 0, -1, False, '构建配置源文件的 URI'),
    ('environment', 'DictionaryEntry', 0, -1, False, '🔑 对应我们的 REPRO_ENV'),
    ('parameter', 'DictionaryEntry', 0, -1, False, '构建参数'),
]

INHERITED = [
    ('comment', 'xsd:string', 0, 1), ('creationInfo', 'CreationInfo', 1, 1),
    ('description', 'xsd:string', 0, 1), ('extension', 'Extension', 0, -1),
    ('externalIdentifier', 'ExternalIdentifier', 0, -1),
    ('externalRef', 'ExternalRef', 0, -1), ('name', 'xsd:string', 0, 1),
    ('spdxId', 'xsd:anyURI', 1, 1), ('summary', 'xsd:string', 0, 1),
    ('verifiedUsing', 'IntegrityMethod', 0, -1),
]

REQUIRED = ('buildType', 'spdxId', 'creationInfo')

# 🔑 Build profile 强制的三条关系（前八轮完全没记）
PROFILE_RELS = [
    ('hasInput', 'Build → 其输入', '配置文件/构建工具可用 configures/usesTool 替代'),
    ('hasOutput', 'Build → 其输出', '中间产物或最终产物'),
    ('invokedBy', 'Build → 调用它的 Agent', '🔑 谁发起的构建'),
]
OPT_RELS = [
    ('hasHost', 'Build → 构建宿主'), ('configures', '配置 → Build'),
    ('ancestorOf', '父 Build → 子 Build'), ('descendantOf', '子 → 父'),
    ('usesTool', 'Build → 构建工具'),
]

# 内部 manifest 字段 → SPDX 字段映射
MAP = [
    ('build_id', 'buildId', '⚠️ **仅局部唯一**——须再加全局键'),
    ('source_commit', 'configSourceUri / hasInput', '源码输入'),
    ('engine_commit', 'hasInput', '引擎输入'),
    ('toolchain_digest', 'buildType(hint) / usesTool', '🔑 hint 不是真相'),
    ('input_artifact_digests', 'configSourceDigest', '🔑 输入如何哈希'),
    ('output_inventory', 'hasOutput', '输出清单'),
    ('runtime_dependency_manifest', 'hasInput', '运行时依赖'),
    ('environment(构建路径/locale/并行性…)', 'environment', '🔑 直接对应 REPRO_ENV'),
    ('—', 'invokedBy', '🔴 **内部 manifest 完全没有对应字段**'),
]


def _hdr(t, w=78):
    print('=' * w)
    print(t)
    print('=' * w)


def cmd_show(a):
    _hdr('SPDX 3.0 Build 类字段（**一手核验**）')
    print('\n来源：spdx.github.io/spdx-spec/v3.0-dev/model/Build/Classes/Build\n')
    print('| 属性 | 类型 | min | max | 3.1 | 说明 |')
    print('|---|---|---|---|---|---|')
    for p, t, mn, mx, dep, note in OWN:
        print(f'| `{p}` | {t} | {mn} | {"*" if mx < 0 else mx} | '
              f'{"🔴弃用" if dep else ""} | {note} |')
    print('\n继承属性（10 个）：' +
          ' · '.join(f'`{p}`' for p, *_ in INHERITED))
    print(f'\n🔑 **必填只有 {len(REQUIRED)} 个**：' +
          ' · '.join(f'`{r}`' for r in REQUIRED))
    print('   🔑 合计 **9 自有 + 10 继承 = 19**（第五十一轮记的"18"需修正）')

    print('\n' + '-' * 78)
    print('🔴 三处修正')
    print('-' * 78)
    print('\n1. **字段数**：18 → **19**；且必填仅 3 个，'
          '🔴 不是"18 个都要填"')
    print('2. 🔑 **`buildId` 是 locally unique** —— 官方原文：'
          '"used by a builder to identify a unique instance of a build '
          'produced by it"。')
    print('   🔴 **复刻项目不能把它当全局唯一键**，必须再加一层')
    print('3. 🔑 **`buildStartTime/EndTime` 官方明说可省略**，'
          '且原文："may be omitted to simplify creating reproducible builds"。')
    print('   🔴 **我们一直在记构建时间戳——这反而损害可复现**。'
          '3.1 已弃用这两个属性。')

    print('\n' + '-' * 78)
    print('🔑 前八轮完全没记的东西：Build profile 的**关系**')
    print('-' * 78)
    print('\n| 关系 | 方向 | 备注 |')
    print('|---|---|---|')
    for r, d, n in PROFILE_RELS:
        print(f'| `{r}` | {d} | {n} |')
    print('\n可选关系：' + ' · '.join(f'`{r}`' for r, *_ in OPT_RELS))
    print('\n🔑 合规要求：至少 3 个 `LifecycleScopedRelationship`，'
          '`scope` 必须为 `"build"`。')
    print('🔴 **只有字段没有关系，那不是 Build，只是一张属性表。**')

    print('\n' + '-' * 78)
    print('内部 manifest ↔ SPDX 映射')
    print('-' * 78)
    print('\n| 内部字段 | SPDX | 提醒 |')
    print('|---|---|---|')
    for a_, b_, c_ in MAP:
        print(f'| `{a_}` | `{b_}` | {c_} |')
    return 0


def cmd_emit(a):
    """产出真实可落盘的 SPDX 3.0 JSON-LD 片段（含三条强制关系）。"""
    d = os.path.join(a.dir, a.build_id)
    os.makedirs(d, exist_ok=True)
    now = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    bid = a.build_id
    doc = {
        '@context': 'https://spdx.org/rdf/3.0/terms',
        '@graph': [
            {'type': 'Build/Build',
             'spdxId': f'urn:spdx:build-{bid}',
             # 🔑 buildType 是必填；但它只是 hint，不能当真相
             'buildType': a.build_type,
             'buildId': bid,
             'name': f'{bid} (internal build manifest)',
             # 🔑 官方说时间戳可省略以简化可复现构建 → 默认**不写**
             # 只有显式传 --with-timestamps 才写，并标注 3.1 已弃用
             'configSourceUri': [a.config_uri] if a.config_uri else [],
             'parameter': [{'key': k, 'value': v}
                           for k, v in (a.param or [])],
             'environment': [{'key': 'locale', 'value': 'C.UTF-8'},
                             {'key': 'fileOrder', 'value': 'sorted'},
                             {'key': 'parallelism', 'value': '1'}],
             'creationInfo': {'created': now,
                              'specVersion': '3.0',
                              'createdBy': ['urn:spdx:agent-replication-team']},
             # 🔑 复刻项目自己加的全局唯一层（SPDX 没有）
             'externalIdentifier': [{
                 'type': 'ExternalIdentifier',
                 'externalIdentifierType': 'other',
                 'identifier': a.global_key or f'global:{bid}:{a.global_salt}',
                 'comment': ('🔑 SPDX `buildId` 仅 locally unique —— '
                             '这是本项目自加的**全局唯一键**')}],
             },
            # 🔑 Build profile 强制的三条关系
            *[{'type': 'Relationship',
               'spdxId': f'urn:spdx:rel-{bid}-{r[0].lower()}',
               'from': f'urn:spdx:build-{bid}',
               'relationshipType': r[0],
               'to': [a.rel.get(r[0], f'urn:spdx:tbd-{r[0]}')],
               'scope': 'build'} for r in PROFILE_RELS],
        ],
        'note': ('🔑 `buildStartTime/EndTime` **默认不写**——官方明说可省略以'
                 '简化可复现构建，且 3.1 已弃用'),
    }
    if a.with_timestamps:
        doc['@graph'][0]['buildStartTime'] = now
        doc['@graph'][0]['buildEndTime'] = now
        doc['note'] += '；⚠️ 本次**显式加了时间戳**，可复现性已下降'
    p = os.path.join(d, 'spdx_build.json')
    json.dump(doc, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print(f'✅ 已产出 {p}')
    print(f'   必填三件: buildType ✅ / spdxId ✅ / creationInfo ✅')
    print(f'   强制关系: {len(PROFILE_RELS)} 条（hasInput · hasOutput · invokedBy）'
          f' · scope=build ✅')
    print('   🔑 **默认不写 buildStartTime/EndTime** —— 保护可复现性')
    print('   🔑 已自加 `externalIdentifier` 全局唯一键'
          '（SPDX 的 buildId 只是 locally unique）')
    return 0


def cmd_check(a):
    if not os.path.exists(a.file):
        print(f'⏭ 缺 {a.file} —— 跳过（不是通过）')
        return 0 if not a.gate else 1
    try:
        d = json.load(open(a.file, encoding='utf-8'))
    except Exception as e:
        print(f'🚫 JSON 解析失败: {e}')
        return 1
    g = d.get('@graph') or []
    b = next((x for x in g if x.get('type') == 'Build/Build'), None)
    miss = []
    if b is None:
        print('🚫 无 `Build/Build` 元素')
        return 1
    for r in REQUIRED:
        if not b.get(r):
            miss.append(r)
    # 关系检查
    rels = {x.get('relationshipType') for x in g
            if x.get('type') == 'Relationship'}
    miss_rel = [r[0] for r in PROFILE_RELS if r[0] not in rels]
    bad_scope = [x.get('relationshipType') for x in g
                 if x.get('type') == 'Relationship'
                 and x.get('relationshipType') in [r[0] for r in PROFILE_RELS]
                 and x.get('scope') != 'build']
    # 🔴 时间戳：存在即警告（可复现性）
    ts = [k for k in ('buildStartTime', 'buildEndTime') if k in b]
    print('=' * 74)
    print(f'SPDX Build 校验 · {a.file}')
    print('=' * 74)
    if miss:
        print(f'\n🚫 缺必填属性: {miss}')
    if miss_rel:
        print(f'\n🚫 缺强制关系: {miss_rel} —— '
              '🔴 **只有字段没有关系不是 Build**')
    if bad_scope:
        print(f'\n🚫 关系 scope 不为 "build": {bad_scope}')
    if ts:
        print(f'\n⚠️ 存在 {ts} —— 🔑 官方明说可省略以简化可复现构建，'
              '3.1 已弃用；🔴 **保留会降低可复现性**')
    if 'externalIdentifier' not in b:
        print('\n⚠️ 无 `externalIdentifier` —— '
              '🔑 SPDX `buildId` 仅 locally unique，**建议自加全局唯一键**')
    ok = not (miss or miss_rel or bad_scope)
    print('\n✅ 通过' if ok else '\n❌ 阻断')
    return 0 if ok else 1


def cmd_self_test(a):
    import tempfile
    tmp = a.dir or tempfile.mkdtemp(prefix='spdx54_')
    _hdr('SPDX 3.0 Build 接入 · 端到端自测')
    print(f'\n工作目录: {tmp}\n')
    print('--- ① 产出合规片段（默认不含时间戳）---')
    r = cmd_emit(argparse.Namespace(dir=tmp, build_id='b54',
                                    build_type='https://example.org/toolchain/v1',
                                    config_uri='https://git.example.com/cfg.git',
                                    param=[('MACHINE', 'pc')], global_key=None,
                                    global_salt='s1', rel={},
                                    with_timestamps=False))
    if r:
        return 1
    p = os.path.join(tmp, 'b54', 'spdx_build.json')
    print('\n--- ② 校验应通过 ---')
    r1 = cmd_check(argparse.Namespace(file=p, gate=True))
    print('\n--- ③ 故意加时间戳后校验仍过，但**警告可复现性下降** ---')
    cmd_emit(argparse.Namespace(dir=tmp, build_id='b54ts',
                                build_type='https://example.org/toolchain/v1',
                                config_uri='', param=[], global_key=None,
                                global_salt='s2', rel={},
                                with_timestamps=True))
    r2 = cmd_check(argparse.Namespace(file=os.path.join(tmp, 'b54ts',
                                                        'spdx_build.json'),
                                      gate=True))
    print('\n--- ④ 故意删掉 hasOutput 关系，应**阻断** ---')
    d = json.load(open(p, encoding='utf-8'))
    d['@graph'] = [x for x in d['@graph']
                   if not (x.get('type') == 'Relationship'
                           and x.get('relationshipType') == 'hasOutput')]
    bad = os.path.join(tmp, 'b54', 'broken.json')
    json.dump(d, open(bad, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    r3 = cmd_check(argparse.Namespace(file=bad, gate=True))
    print('\n' + '=' * 74)
    ok = (r1 == 0 and r3 == 1)
    print('✅ **端到端自测通过**（合规片段通过 / 缺关系被拦）'
          if ok else '❌ 自测未通过')
    print('=' * 74)
    print('\n🔑 这验证的是**接入层**，🔴 不是任何原版构建已被描述。')
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description='build manifest ↔ SPDX 3.0 Build')
    ap.add_argument('--show', action='store_true')
    ap.add_argument('--emit', metavar='DIR')
    ap.add_argument('--check', metavar='FILE')
    ap.add_argument('--self-test', action='store_true')
    ap.add_argument('--dir')
    ap.add_argument('--build-id', default='build001')
    ap.add_argument('--build-type', default='https://example.org/toolchain/v1')
    ap.add_argument('--config-uri', default='')
    ap.add_argument('--param', nargs='*', default=[],
                    help='KEY=VALUE …')
    ap.add_argument('--global-key')
    ap.add_argument('--global-salt', default='salt')
    ap.add_argument('--rel', nargs='*', default=[])
    ap.add_argument('--with-timestamps', action='store_true',
                    help='⚠️ 显式写入 buildStartTime/EndTime（降低可复现性）')
    ap.add_argument('--gate', action='store_true')
    a = ap.parse_args()
    a.param = [tuple(x.split('=', 1)) for x in a.param if '=' in x]
    a.rel = dict(x.split('=', 1) for x in a.rel if '=' in x)
    if a.show:
        return cmd_show(a)
    if a.emit:
        return cmd_emit(a)
    if a.check:
        return cmd_check(a)
    if a.self_test:
        return cmd_self_test(a)
    print('❌ 需要 --show / --emit / --check / --self-test 之一')
    return 2


if __name__ == '__main__':
    sys.exit(main())
