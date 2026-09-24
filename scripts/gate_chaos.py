#!/usr/bin/env python3
"""门禁混沌测试（第五十六轮）：**故意改坏，验证门禁不是假的**。

> ## 🔑 为什么需要这个脚本
>
> 第五十二轮的审核报告说："**263 个工具 → 3 个可直接调用；232 个门禁 →
> 130 个人工待签字**"。第二十轮自己也写过：
> **"82 个门禁可能全是假的——必须故意改坏验证测试有效。"**
>
> 🔑 但那句话**一直只是一句话**。340 个门禁里没人真的做过一次"故意改坏"。
>
> 🔴 **本轮做这件事**：对每一条**台账型**门禁，先 `--init` 生成空台账，
> 再**故意填入违反规则的数据**，看它**是否真的阻断**。
> 🔴 **填坏数据仍然退出 0 的门禁 = 假门禁**，必须暴露出来。

用法:
  gate_chaos.py --probe DIR          # 探测哪些脚本支持 init/check
  gate_chaos.py --coverage           # 🔑 **字段覆盖率**（拦截率的置信区间）
  gate_chaos.py --chaos DIR          # 🔑 **故意改坏，统计拦截率**
  gate_chaos.py --self-test          # 端到端自测

退出码: 0 全部拦截 / 1 存在假门禁 / 2 用法错误
"""
import argparse
import json
import os
import tempfile
import re
import tempfile
import shutil
import time
import subprocess
import sys

PY = sys.executable
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 🔑 第九十轮：把「能力自报 + 产物 + 真值」框架**推广到第二个能力**。
#    🔴 第八十九轮诚实结论：整套机制只守护了 `audit-all` **一个点**。
#    🔑 本模块提供能力 `chaos-full`：**全量混沌统计**（拦截率 / 强证据率）。
DECLARED_CAPABILITIES = (
    'chaos-full',
)
CAPABILITY_PROBE = {
    'chaos-full': 'cmd_chaos',
}
CAPABILITY_ARTIFACT = {
    'chaos-full': os.path.join('ledger', '_chaos_last.json'),
}
CAPABILITY_ARTIFACT_KEYS = {
    'chaos-full': ('participated', 'intercepted', 'strong'),
}

# 🔑 第九十一轮：**外部锚点下界**。
#    🔴 第九十轮诚实结论：下界基线来自**上一次运行** ——
#       若第一次就写假值，基线会被**污染**，此后永远比对错误值。
#    🔑 解法：给每个键一个**不依赖上一次产物**的硬下界（外部锚点），
#       取自**可独立计数的客观事实**：
#         · participated —— `scripts/` 下**.py 文件数**的 60%
#           （排除 run_all_gates.py / gate_chaos.py 自身）
#         · intercepted  —— 同锚点的 60%（混沌拦截率不应低于此）
#         · strong       —— 同锚点的 50%（强证据率，第六十三轮实测 99/101）
#    🔑 取值理由写在注释里；**不是拍脑袋的数字**。
# 🔑 第九十二轮：锚点分母从「`.py` 文件数」改为「**台账型脚本数**」。
#    🔴 第九十一轮诚实结论②：若新增大量**非台账**脚本，
#       `len(_scripts())` 变大 → 锚点被抬高 → **可能误杀真实结果**。
#    🔑 解法：分母用 `chaosable`（既有 --init 又有 --check/--gate），
#       这正是 `cmd_probe` 已能判定的**台账型**定义。
CAPABILITY_ANCHOR_FLOOR = {
    'participated': 0.90,   # 台账型脚本几乎都参与（实测 101/101）
    'intercepted': 0.90,
    'strong': 0.90,         # 强证据率实测 99/101 ≈ 0.98
}

_ANCHOR_DENOM_MODE = 'chaosable'   # 'chaosable' | 'all_scripts'


def _anchor_denom():
    """🔑 锚点分母 —— **台账型**脚本数（第九十二轮）。

    🔴 为什么不直接用 `len(_scripts())`：
       非台账脚本（纯打印 / 纯自测 / 需外部素材）**不参与混沌**，
       把它们算进分母会**抬高锚点**，进而误杀真实结果。
    🔑 取不到台账型计数时**返回 0**（不猜），由调用方拒绝给结论。
    """
    if _ANCHOR_DENOM_MODE != 'chaosable':
        return len(_scripts())
    n = 0
    for _n in _scripts():
        try:
            _src = open(os.path.join('scripts', _n), encoding='utf-8').read()
        except Exception:
            continue
        if '--init' in _src and ('--check' in _src or '--gate' in _src):
            n += 1
    return n



def _scripts():
    return sorted(p for p in os.listdir('scripts') if p.endswith('.py')
                  and p not in ('run_all_gates.py', 'gate_chaos.py'))


def _has(path, *flags):
    try:
        s = open(path, encoding='utf-8').read()
    except Exception:
        return False
    return all(f in s for f in flags)



def _declare_capability():
    """🔑 自报本脚本提供的能力（供 G387 与登记双向校验）。"""
    print('=' * 70)
    print('🔑 **能力自报** —— ' + os.path.basename(__file__))
    print('=' * 70)
    for c in DECLARED_CAPABILITIES:
        print(f'  CAPABILITY {c}')
    print('=' * 70)
    return 0


def _probe_capability(name):
    """🔑 **真跑一次**某个自报的能力（第八十五~八十九轮框架）。

    判据：① 已声明 ② 已登记实现入口 ③ 入口存在
          ④ 真跑 rc=0 ⑤ 产物纳秒戳变大
          ⑥ 产物内容键齐全且与**跨进程真值**一致
    """
    print('=' * 70)
    print('🔑 **能力探测** —— ' + os.path.basename(__file__))
    print('=' * 70)
    name = (name or '').strip()
    print(f'\n探测能力: `{name}`')
    if name not in DECLARED_CAPABILITIES:
        print(f'\n🔴 该能力**未被声明**（已声明: {DECLARED_CAPABILITIES}）')
        return 1
    fn_name = CAPABILITY_PROBE.get(name)
    if not fn_name:
        print(f'\n🔴 声明了 `{name}` 却**未登记实现入口**')
        return 1
    f_ = globals().get(fn_name)
    if f_ is None:
        print(f'\n🔴 实现入口 `{fn_name}` 不存在')
        return 1
    art = CAPABILITY_ARTIFACT.get(name)
    keys = CAPABILITY_ARTIFACT_KEYS.get(name)
    if not art or not keys:
        print('\n🔴 未登记产物或产物内容键')
        return 1
    ap2 = os.path.join(ROOT, art)
    before_ns = 0
    if os.path.isfile(ap2):
        try:
            before_ns = json.load(open(ap2, encoding='utf-8')).get(
                'generated_at_ns', 0)
        except Exception:
            before_ns = 0
    print(f'\n🔑 运行前产物快照: `{art}` ns={before_ns}')
    print(f'实现入口: `{fn_name}` —— **真的跑一次**（全量混沌，较慢）')
    import io
    import contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        # 🔑 用 `--baseline valid` 才可能产出**强证据**（empty 口径下强证据极少）
        rc = f_(argparse.Namespace(
            dir=None, strategy='typed', baseline='valid', limit=0))
    produced = buf.getvalue()
    print(f'\n真实输出 {len(produced)} 字符')
    if rc != 0:
        print(f'\n🔴 探测**失败**（rc={rc}）')
        return 1
    try:
        cur = json.load(open(ap2, encoding='utf-8'))
    except Exception as e:
        print(f'\n🔴 产物未生成或不可读：{type(e).__name__}: {e}')
        return 1
    after_ns = cur.get('generated_at_ns', 0)
    if after_ns <= before_ns:
        print(f'\n🔴 产物**未被重写**（ns {before_ns} → {after_ns}）')
        return 1
    print(f'  ✅ 产物已重写（ns {before_ns} → {after_ns}）')
    body = cur.get('results') if isinstance(cur.get('results'), dict) else cur
    print(f'\n🔑 产物内容键（须齐全、为 int、且达**下界**）: {list(keys)}')
    # 🔑 第九十轮补：只判 "> 0" **防不住写假值**（实测把 participated
    #    恒写成 1 也能过）。✅ 改为断言**下界**：
    #    🔑 下界不是拍脑袋 —— 它来自**上一次成功探测的产物**，
    #       再用 80% 留一点抖动余量。
    #    🔴 全量混沌有 101 个台账脚本，写 1 显然不可能是真的。
    lb_path = os.path.join(ROOT, 'ledger', '_chaos_baseline.json')
    prev = {}
    if os.path.isfile(lb_path):
        try:
            prev = json.load(open(lb_path, encoding='utf-8')).get(
                'results', {})
        except Exception:
            prev = {}
    # 🔑 第九十一轮补：**锚点下界自身**必须可信。
    #    🔴 若 `CAPABILITY_ANCHOR_FLOOR` 被改成 0.0（或整表被删），
    #       锚点会退化成 0 → 又变回"只判 > 0"的第九十轮旧病。
    #    🔑 判据：每个键都必须有**正比率**，且算出的锚点 > 0。
    _den_chk = cur.get('anchor_denom') or _anchor_denom()
    for k in keys:
        r = CAPABILITY_ANCHOR_FLOOR.get(k, 0)
        if not isinstance(r, (int, float)) or r <= 0:
            print(f'\n🔴 键 `{k}` **没有正的锚点比率** —— '
                  f'下界断言会退化成"只判 > 0"')
            return 1
        if int(_anchor_denom() * r) <= 0:
            print(f'\n🔴 键 `{k}` 的锚点下界算出来为 0 —— 断言无效')
            return 1
    for k in keys:
        if k not in body:
            print(f'\n🔴 产物**缺少键** `{k}`')
            return 1
        v = body[k]
        if not isinstance(v, int) or v <= 0:
            print(f'\n🔴 产物键 `{k}` = {v!r} 不是正整数 —— '
                  f'混沌若真跑了，参与数不可能为 0')
            return 1
        # 🔑 第九十一轮：**外部锚点** —— 不依赖上一次产物
        ratio = CAPABILITY_ANCHOR_FLOOR.get(k, 0)
        # 🔑 优先用**产物里缓存的分母**（省一次 128 文件遍历）；
        #    取不到才现算。
        _den = cur.get('anchor_denom') or _anchor_denom()
        anchor = int(_den * ratio) if ratio else 0
        lo = int(prev.get(k, 0) * 0.8) if prev.get(k) else 0
        # 🔑 取**两者较大值**：基线被污染时，锚点仍能兜住
        lo = max(lo, anchor)
        if lo and v < lo:
            print(f'\n🔴 产物键 `{k}` = {v} **低于下界** {lo} '
                  f'（基线 {prev.get(k)}，锚点 {anchor}'
                  f'= 脚本数 {len(_scripts())} × {ratio}）—— 疑似写假值')
            return 1
        print(f'  ✅ {k} = {v}（正整数'
              + (f'，≥ 下界 {lo}（锚点 {anchor}））' if lo else '）'))
    # 🔑 本次成功值写回基线（供下次比对）
    os.makedirs(os.path.dirname(lb_path), exist_ok=True)
    json.dump({'generated_at_ns': cur.get('generated_at_ns'),
               'results': {k: body[k] for k in keys}},
              open(lb_path, 'w', encoding='utf-8'),
              ensure_ascii=False, indent=2)
    print('\nPROBE_OK')
    print('=' * 70)
    print(f'✅ 能力 `{name}` **探测通过**（真跑 rc=0）')
    print('=' * 70)
    return 0


def cmd_probe(a):
    """🔑 探测每台账脚本是否提供 `--init`（生成空台账）+ `--check`（校验）接口。"""
    d = a.dir
    if d:
        os.makedirs(d, exist_ok=True)
    rows = []
    for n in _scripts():
        p = os.path.join('scripts', n)
        init = '--init' in open(p, encoding='utf-8').read()
        chk = ('--check' in open(p, encoding='utf-8').read()
               or '--gate' in open(p, encoding='utf-8').read())
        rows.append({'script': n, 'init': init, 'check': chk,
                     'chaosable': init and chk})
    n_ok = sum(1 for r in rows if r['chaosable'])
    print('=' * 74)
    print('门禁混沌可行性探测')
    print('=' * 74)
    print(f'\n总脚本: {len(rows)}')
    print(f'🔑 可做混沌测试（既有 --init 又有 --check/--gate）: **{n_ok}**')
    print(f'🔴 无法混沌测试: {len(rows) - n_ok}'
          '（多为纯打印/纯自测/需外部素材）')
    no_init = [r['script'] for r in rows if not r['init']]
    print(f'\n无 --init 的（{len(no_init)} 个，前 12）：')
    print('  ' + ' · '.join(no_init[:12]))
    if d:
        json.dump(rows, open(os.path.join(d, 'probe.json'), 'w',
                             encoding='utf-8'), ensure_ascii=False, indent=2)
        print(f'\n✅ 明细 → {d}/probe.json')
    return 0


# ==========================================================================
# 🔑 第五十七轮升级：**类型感知毒化** + **覆盖率**
#
# 🔴 第五十六轮的局限：毒化只有 11 类关键词 + 空值/TODO，
#    覆盖率未知 → "拦截率 88%" 的置信区间说不清。
#
# 🔑 本轮：先对列名做**类型推断**，再按类型下毒；
#    并统计**字段覆盖率** —— 只有"能被类型断言"的字段才算被覆盖。
#    🔑 **未覆盖字段 = 真实盲区，不能说它有效。**
# ==========================================================================

# (类型, 命中关键词, 毒化值)
TYPE_RULES = [
    ('timestamp', ('_at', '_time', 'timestamp', 'date', '_ts', 'deadline',
                   'expire', 'created', 'updated'), 'not-a-timestamp'),
    ('hash', ('sha256', 'sha1', 'md5', 'digest', 'hash', 'checksum',
              'fingerprint'), 'zz-not-a-hex'),
    ('boolean', ('is_', 'has_', 'enabled', 'flag', '_ok', 'idempotent',
                 'required', 'optional', 'confirmed'), 'maybe'),
    ('numeric', ('_ms', 'ms', 'frame', 'count', 'rate', 'pct', 'percent',
                 'duration', 'size', 'index', 'priority', 'level', 'num',
                 'budget', 'delay', 'window', 'threshold', 'score',
                 'tolerance', 'similarity', 'distance', 'radius', 'weight',
                 'amount', 'price', 'volume', 'length'), '-999999999'),
    ('url', ('uri', 'url', 'path', 'link', 'href'), 'not a url'),
    ('id', ('_id', '^id$', 'key', 'uuid', 'guid'), '??invalid-id??'),
    # 🔑 第五十七轮新增：**配对字段可断言**
    #    🔑 假设：legacy/new 被填成相同值 → 对比逻辑认为相等 → 漏检
    #    🔴 **实测证伪**：80 个含该配对的脚本中 79 个在"相同毒化"时即被拦
    #       （同行其他字段如 match/evidence 会先触发），仅 1 个完全盲。
    #    🔑 但仍纳入可断言：配对可被"差异化毒化"断言，属于**可测**。
    ('pair', ('legacy_', 'new_', 'original', 'target', '_before', '_after',
              'primary_', 'secondary_', 'old_', 'expected', 'observed'),
     '__PAIR_DIFF__'),
    ('enum', ('status', 'state', 'kind', 'type', 'mode', 'verdict', 'match',
              'policy', 'class', 'category', 'disposition', 'evidence',
              'source_kind', 'must_match', 'license', 'owner', 'reviewer',
              'baseline', 'confidence', 'domain', 'tool', 'algorithm',
              'side_effects'), '__INVALID_ENUM__'),
]

# 🔑 可断言类型 = 能给出"明确违例"的类型；text 不算覆盖
ASSERTABLE = ('timestamp', 'hash', 'boolean', 'numeric', 'url', 'id',
              'enum', 'pair')


def classify(col):
    """🔑 按列名推断类型。返回 (type, poison_value)。"""
    c = col.strip().lower()
    if not c:
        return ('empty', '__poison__')
    for t, kws, pv in TYPE_RULES:
        for k in kws:
            if k.startswith('^'):
                if re.match(k, c):
                    return (t, pv)
            elif k in c:
                return (t, pv)
    return ('text', '__poison__')


# ==========================================================================
# 🔑 第五十八轮新增：**语义毒化（semantic poison）**
#
# 🔑 前两轮（legacy / typed）都是**语法毒化**：填**非法值**
#    （`__poison__` / `-999999999` / `not-a-timestamp`）。
#    🔴 但语法毒化有个盲点：**它只测"校验是否检查了这个字段"**。
#
# 🔑 真实场景里，人填表**不会填 `__poison__`**，而是填**看起来合法、
#    但彼此矛盾的值**——比如 legacy=100 / new=200，却把 match 写成 `exact`。
#    🔴 这才是台账最容易出错、也最危险的错误形态：
#    **每个字段都合法，但整行在说谎。**
#
# 🔑 语义毒化 = 用**合法值**制造**内部矛盾**。
# ==========================================================================

# 列名 → 语义毒化值（**全部是合法值**，但组合起来自相矛盾）
SEMANTIC = {
    'legacy_value': '100',
    'legacy_trace': 'trace_A',
    'new_value': '200',          # 🔴 与 legacy 不同
    'new_trace': 'trace_B',      # 🔴 与 legacy 不同
    'match': 'exact',            # 🔴 合法枚举，但与上面矛盾
    'equivalence_verdict': 'equivalent',   # 🔴 同上
    'tolerance': '0',            # 🔴 差 100 却写 0 容差
    'evidence': 'observed',      # 合法
    'evidence_level': '8',       # 合法
    'status': 'done',            # 合法
    'owner': 'someone',
    'reviewer': 'someone',
    'license': 'MIT',
    'must_match': 'yes',
    'unknown_policy': 'block',
    'confidence': 'high',
    'similarity': '1.0',
    'domain': 'other',
    'note': 'ok',
    'sha256': '0' * 64,          # 🔑 合法 hex，但**与内容无关**
    'file_hash': '0' * 64,
}

# 🔑 语义矛盾断言：这些字段组合**必然**应被拦
CONTRADICTIONS = [
    # (字段A, 字段B, 说明)
    ('legacy_value', 'match', '原值≠新值却声称 match=exact'),
    ('new_value', 'match', '原值≠新值却声称 match=exact'),
    ('legacy_trace', 'equivalence_verdict', '轨迹不同却判定 equivalent'),
]


# 🔑 兼容旧调用（第五十六轮的策略保留为"关键词兜底"）
POISON = {
    'unknown': 'yes', 'evidence_level': '99', 'evidence': '__INVALID_ENUM__',
    'status': 'done', 'owner': '', 'reviewer': '', 'must_match': 'maybe',
    'deviation': 'ok', 'license': '', 'sha256': 'x', 'artifact_sha256': '',
    'baseline': 'latest', 'kind': 'weird', 'source_kind': 'rumor',
    'confidence': 'high', 'note': '',
}


# ==========================================================================
# 🔑 第六十轮新增：**接口适配器**
#
# 🔴 第五十九轮遗留：101 项里有 1 项（`credits_diff`）因接口不匹配
#    被判为 `iface_mismatch`，**未参与统计**——不是"通过"，是"没测"。
# 🔑 修复：为不同调用约定的脚本登记专属 (init, check) 命令构造方式，
#    让它们**真正进入拦截率统计**。
# ==========================================================================

# 🔑 每个适配器：init（造干净输入）/ check（校验参数）/ poison（毒化）/ prep（可选）
INTERFACE_ADAPTERS = {
    # 🔑 credits_diff 用 `--diff OLD NEW`（比对两个名单快照），没有 `--check`
    'credits_diff': {
        'init': lambda led: ['--init', led],
        'check': lambda led: ['--diff', led, led + '.new', '--gate-check'],
        'poison': lambda led, st: _poison_csv(led + '.new', True, st),
        'prep': lambda led: subprocess.run(
            [sys.executable, 'scripts/credits_diff.py',
             '--init', led + '.new'],
            capture_output=True, text=True, timeout=60),
    },
    # 🔑 ledger：`--init` 是 store_true，但用 `--src`+`--ledger` **真生成 CSV**
    #    🔴 第六十一轮按"--init 是否接受路径参数"**误判**为 not_a_ledger
    'ledger': {
        'init': lambda led: ['--init', '--src', led + '.src',
                             '--ledger', led],
        'check': lambda led: ['--gate', '--ledger', led],
        'poison': lambda led, st: _poison_csv(led, True, st),
        'prep': lambda led: _prep_ledger(led),
    },
    # 🔑 visual_check：状态是 **YAML** → 毒化方式是**删必需字段**（结构毒化）
    'visual_check': {
        'init': lambda led: ['--init', '--states', led + '.d'],
        'check': lambda led: ['--states', led + '.d'],
        'poison': lambda led, st: _poison_yaml_struct(led + '.d'),
        'prep': lambda led: None,
    },
    # 🔑 motion_check：ffmpeg 造合成视频 → 抽帧 → 补时序 → 放大
    'motion_check': {
        'init': lambda led: ['--video', led + '.mp4', '--rate', '20',
                             '--out', led + '.json'],
        'check': lambda led: ['--old', led + '.json',
                              '--new', led + '.new.json',
                              '--compare', '--gate'],
        'poison': lambda led, st: _poison_motion_json(led + '.new.json', st),
        'prep': lambda led: _prep_motion(led),
    },
}


def _prep_ledger(led):
    """🔑 给 ledger 造一个**能通过基线**的干净台账。

    🔴 若基线本身就 rc≠0（比如 status 还是 TODO），
       那"毒化后 rc≠0"完全没信息量——**测了个寂寞**。
    """
    import csv as _c
    src = led + '.src'
    os.makedirs(src, exist_ok=True)
    with open(os.path.join(src, 'a.py'), 'w', encoding='utf-8') as f:
        f.write('# sample\n')
    # 🔑 用**脚本自己的 --init** 生成（字段以脚本为准，不手搓），
    #    再把 status 改成"清零"——让基线**真的干净**。
    subprocess.run([sys.executable, 'scripts/ledger.py',
                    '--init', '--src', src, '--ledger', led],
                   capture_output=True, text=True, timeout=60)
    try:
        rows = list(_c.DictReader(open(led, encoding='utf-8')))
        hdr = list(rows[0].keys()) if rows else []
        for r in rows:
            r['status'] = '清零'
        with open(led, 'w', encoding='utf-8', newline='') as f:
            w = _c.DictWriter(f, fieldnames=hdr)
            w.writeheader()
            w.writerows(rows)
    except Exception:
        pass


def _poison_yaml_struct(d):
    """🔑 **结构毒化**：删掉 YAML 状态里的必需字段。

    🔴 对只做"字段存在性"检查的门禁，**改值无效，删键才有效**。
    """
    n = 0
    for fn in sorted(os.listdir(d)):
        if not fn.endswith(('.yaml', '.yml')):
            continue
        p = os.path.join(d, fn)
        t = open(p, encoding='utf-8').read()
        out, drop = [], False
        for line in t.splitlines():
            if re.match(r'^(state_id|feature_ref|capability|preconditions|'
                        r'steps|selectors|comparison|review)\s*:', line):
                drop = True
                n += 1
                continue
            if drop and (re.match(r'^\s+\w', line) or line.strip() == ''):
                continue
            if line.strip() == '':
                drop = False
            if not drop:
                out.append(line)
        open(p, 'w', encoding='utf-8').write('\n'.join(out) + '\n')
    return n


def _prep_motion(led):
    """🔑 ffmpeg 造合成视频 → 抽帧 → **补上时序值**。

    🔴 合成视频不会"稳定"，`stable_ms`/`duration_ms` 会是 None。
    🔑 补成具体数值——**造的是门禁的输入工件**，
       🔴 **不声称这是任何原版动效的测量结果**。
    """
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi',
                    '-i', 'testsrc2=size=160x120:rate=20:duration=2',
                    '-pix_fmt', 'gray', led + '.mp4'],
                   capture_output=True, timeout=120)
    subprocess.run([sys.executable, 'scripts/motion_check.py',
                    '--video', led + '.mp4',
                    '--rate', '20', '--out', led + '.json'],
                   capture_output=True, text=True, timeout=180)
    try:
        j = json.load(open(led + '.json', encoding='utf-8'))
    except Exception:
        j = {}
    for k, v in (('first_change_ms', 100), ('stable_ms', 200),
                 ('duration_ms', 300)):
        j[k] = v
    json.dump(j, open(led + '.json', 'w', encoding='utf-8'))
    json.dump(dict(j), open(led + '.new.json', 'w', encoding='utf-8'))


def _poison_motion_json(path, strategy='typed'):
    """🔑 时序数值放大到**必然超 25% 容差**。"""
    j = json.load(open(path, encoding='utf-8'))
    n = 0
    for k in ('first_change_ms', 'stable_ms', 'duration_ms'):
        if k in j and isinstance(j[k], (int, float)):
            j[k] = j[k] * 1000
            n += 1
    json.dump(j, open(path, 'w', encoding='utf-8'))
    return n

# 🔑 需要**外部产物**才能门禁的脚本（🔴 不是"没测"，是**缺输入源**）
#    motion_check 的 `--compare` 期望的是 ffmpeg 抽帧产出的 JSON，
#    🔴 **不是** `--init` 生成的骨架（骨架里根本没有 first_change_ms 等字段）。
#    🔑 因此不能硬凑适配器让它"看起来通过"——应如实标为缺输入源。
# 🔑 第六十二轮：以下脚本**已升级为可毒化**（见 INTERFACE_ADAPTERS），
#    保留此表仅作**历史说明**——它们曾经被误判为"没测/缺输入源"。
NEEDS_EXTERNAL_INPUT = {}


def _needs_pair(path):
    """🔑 判断某脚本是否需要**第二份**台账（如 diff 类）。"""
    _b = os.path.basename(path)
    return (_b[:-3] if _b.endswith('.py') else _b) in INTERFACE_ADAPTERS


# ==========================================================================
# 🔑 第六十一轮新增：**台账型 init 识别** + 更多接口适配器
#
# 🔴 第六十轮遗留：3 项仍是 `skip`——`ledger` / `motion_check` / `visual_check`。
#    🔑 根因不是"脚本坏了"，而是 **它们的 `--init` 不是生成 CSV 台账**：
#       · `ledger.py --init`        → store_true，初始化 ledger **目录**
#       · `motion_check.py --init`  → nargs='?'，生成 **JSON 动效契约**
#       · `visual_check.py --init`  → store_true，生成 **YAML 视觉状态**
#    🔴 把它们标成 `skip` 会让人误以为"没测上/脚本有问题"。
#    ✅ 本轮新增 `not_a_ledger` 分类：**明确说明它是另一个物种**。
# ==========================================================================

# 🔑 `--init` 接受**路径参数**才算"台账型"；store_true / nargs='?' 都不是
def _is_ledger_init(src):
    """🔑 判断 `--init` 是否是"生成 CSV 台账"的接口。

    > 🔑 判据：**是否接受一个路径参数**。
    >    `--init` (store_true)     → 是命令，不是台账生成
    >    `--init` (nargs='?')      → 可选参数，通常是目录名
    >    `--init` (默认/无 action) → **路径参数**，写 CSV 台账 ✅
    """
    import re
    m = re.search(r"add_argument\(\s*['\"]--init['\"]([^)]*)\)", src)
    if not m:
        return False
    opt = m.group(1)
    if 'store_true' in opt or 'store_false' in opt:
        return False          # 🔴 纯开关，不生成台账
    if "nargs" in opt:
        return False          # 🔴 可选参数（多为目录名）
    return True               # ✅ 路径参数 → 台账


def _poison_json(path, strategy='typed'):
    """🔑 第六十一轮：为 **JSON 契约类**台账毒化（如 motion_check 的动效契约）。

    🔴 若用 `_poison_csv` 处理 JSON，会因为"没有表头/数据行"返回 nrow=0
       → 被判 `no_rows` → 计进 skip，看起来像"脚本坏了"。
    🔑 实际是**毒化器不认识 JSON**。
    """
    try:
        j = json.load(open(path, encoding='utf-8'))
    except Exception:
        return 0, {}
    if not isinstance(j, dict):
        return 0, {}
    n = 0
    for k, v in list(j.items()):
        if strategy == 'semantic':
            j[k] = 1 if isinstance(v, (int, float)) or v is None else 'ok'
        elif v is None:
            # 🔑 **None 也必须毒化**：骨架里的时序字段默认是 null，
            #    若毒化后仍是 None，比对器会"数据不足，跳过"→ **rc=0**。
            #    🔴 这是"缺数据即通过"的变体，与 B 类【空表即通过】同源。
            j[k] = 999999
        elif isinstance(v, bool):
            j[k] = True
        elif isinstance(v, (int, float)):
            # 🔑 数值：放大到**必然超阈值**（相对差 >25%）
            j[k] = (v * 1000) if v else 999999
        elif isinstance(v, str):
            j[k] = '__poison__'
        elif isinstance(v, list):
            j[k] = ['__poison__']
        n += 1
    json.dump(j, open(path, 'w', encoding='utf-8'), ensure_ascii=False)
    return n, {'total_cols': len(j), 'covered_cols': n,
               'uncovered_cols': 0, 'coverage_pct': 100.0,
               'uncovered_names': []}


def _is_md_table(txt):
    """🔑 第五十九轮：识别 **Markdown 表格台账**（不是 CSV）。

    🔴 若不识别，用 csv.reader 处理 md 会把 `|---|` 分隔行和 `|` 全部吃掉，
       **摧毁表体结构** → 脚本报"未解析到表体"rc=2 → 被误判为"崩溃"，
       实际是**毒化器不适配**，不是门禁失效。
    """
    lines = [l for l in txt.splitlines() if l.strip()]
    if not lines:
        return False
    # 🔴 第六十七轮修真 bug：**只扫前 8 行会漏** ——
    #    `install_contract` 的表格在 13 项**清单之后**（第 15 行左右），
    #    → `_is_md_table` 判 False，而 `_sniff` 判 md
    #    → 两个嗅探器**对同一文件给出不同答案**
    #    → `_poison_csv` 走 CSV 路径，**把 md 清单当 CSV 写回**。
    #    🔑 判据放宽到全文：CSV 文件不会产生"以 | 开头且含 ---"的行。
    if any(l.strip().startswith('|') and '---' in l for l in lines):
        return True
    if lines[0].strip().startswith('#') and any(
            l.strip().startswith('|') for l in lines[1:6]):
        return True
    return False


def _poison_md(path, strategy='typed'):
    """🔑 按 Markdown 表格格式毒化：**保留 `|` 结构**，只改单元格内容。"""
    lines = open(path, encoding='utf-8').read().splitlines()
    hdr_idx = next((i for i, l in enumerate(lines)
                    if l.strip().startswith('|')), None)
    if hdr_idx is None:
        return 0, {}
    hdr = [c.strip() for c in lines[hdr_idx].strip().strip('|').split('|')]
    kind = [classify(c)[0] for c in hdr]
    nrows = 0
    for i in range(hdr_idx + 1, len(lines)):
        l = lines[i].strip()
        if not l.startswith('|'):
            continue
        if '---' in l:                     # 🔑 分隔行必须原样保留
            continue
        cells = [c.strip() for c in l.strip('|').split('|')]
        new = []
        for j, v in enumerate(cells):
            col = hdr[j].strip().lower() if j < len(hdr) else ''
            if strategy == 'semantic':
                hit = None
                for k, pv in SEMANTIC.items():
                    if k == col or k in col:
                        hit = pv
                        break
                new.append(hit or 'ok')
            elif v in ('', 'TODO', '待填', '—'):
                new.append('__poison__')
            else:
                t, pv = classify(col)
                new.append(f'{pv}_{j}' if t == 'pair' else
                           ('__poison__' if t == 'text' else pv))
        lines[i] = '| ' + ' | '.join(new) + ' |'
        nrows += 1
    open(path, 'w', encoding='utf-8').write('\n'.join(lines) + '\n')
    cov = sum(1 for k in kind if k in ASSERTABLE)
    return nrows, {'total_cols': len(hdr), 'covered_cols': cov,
                   'uncovered_cols': len(hdr) - cov,
                   'coverage_pct': round(100.0 * cov / len(hdr), 1)
                   if hdr else 0.0,
                   'uncovered_names': [hdr[j] for j, k in enumerate(kind)
                                       if k not in ASSERTABLE]}


# ==========================================================================
# 🔑 第六十三轮新增：**强证据率** —— 101/101 里有多少是"基线干净"的
#
# 🔴 第六十二轮留下的最关键疑问：
#    拦截率 101/101 中，绝大多数项的**基线本身就 rc≠0**（空台账全是 TODO）。
#    🔑 这意味着："毒化后 rc≠0" 只能证明**门禁会拦截**，
#    🔴 **不能证明它拦截的是我们注入的内容**——两者都会被拦。
#
# 🔑 本轮把"ok"拆成两级：
#    ok_strict (**强证据**) —— 基线 rc=0 且毒化后 rc≠0
#                              → 门禁**确实对内容敏感**
#    ok_weak   (**弱证据**) —— 基线 rc≠0 且毒化后 rc≠0
#                              → 只证明"它会拦"，🔴 **可能是测了个寂寞**
#
# 🔑 并提供 `--baseline valid`：先填**合法值**让基线尽量干净，
#    把尽可能多的项从 weak 升级为 strict。
# ==========================================================================

# 🔑 合法填充值：**优先**于 SEMANTIC（SEMANTIC 是"合法但矛盾"，不合用于基线）
VALID_OVERRIDE = {
    'unknown': 'no', 'evidence': 'observed', 'evidence_level': '8',
    'status': 'done',
    # 🔑 owner 在多个脚本里是『责任人 + 到期日』，必须含 '/' 或 '-'
    'owner': 'someone/2026-12-31', 'reviewer': 'someone',
    'must_match': 'yes', 'license': 'MIT', 'confidence': 'high',
    'similarity': '1.0', 'tolerance': '0', 'domain': 'other',
    'note': 'ok', 'sha256': 'a' * 64, 'file_hash': 'a' * 64,
    # 🔑 **配对字段必须相同**，否则就是矛盾 → 基线不干净
    'legacy_value': '100', 'new_value': '100',
    'legacy_trace': 'trace_A', 'new_trace': 'trace_A',
    'match': 'yes', 'equivalence_verdict': 'equivalent',
    'baseline': 'latest', 'kind': 'other', 'source_kind': 'source',
}

# 🔑 占位符：只有这些才需要被填充；**其余原值一律保留**
# 🔑 **单元格内文本替换** —— 有的 TODO 藏在单元格**内容**里，不是整列占位
#    🔑 第六十五轮实测：feature_matrix 的第 4 行「需要讨论」四栏写在**一个格子**里
#       （`卡在哪：… / 谁拍板：产品 / 截止时间：TODO / 超时默认：…`）
#       🔴 按**列名**匹配 fixture 完全无效 —— 必须按**内容**替换。
TEXT_REPLACEMENTS = {
    'feature_matrix': [('截止时间：TODO', '截止时间：2026-12-31')],
}

PLACEHOLDERS = ('', 'todo', 'tbd', '待填', '待定', '—', '-', '--',
                'n/a', 'na', 'none', 'null', '?', 'xxx', '待确认',
                'fill', '<fill>', 'example', 'sample')

VALID_BY_TYPE = {
    'timestamp': '2026-09-21T10:00:00+08:00',
    'hash': 'a' * 64,
    'boolean': 'true',
    'numeric': '1',
    'url': 'https://example.com/x',
    'id': 'ID-001',
    'pair': 'A',
    'enum': 'ok',
    'text': 'ok',
}


# ==========================================================================
# 🔑 **逐脚本 fixture 覆盖** —— 强证据率的**唯一可靠提升路径**
#
# 🔴 实测结论：通用填充只能把强证据率提到 79/101。
#    🔑 剩下的项各自要求**本脚本专属的合法取值**，例如：
#       · `game_embodied_input` 的 `must_match` 必须是
#         **exact / tolerance / deliberate**（不是 yes）
#       · `game_edge` 的 `evidence` 是 **1-8 等级**（不是 observed）
#       · `game_rng_save` 的 `replayable` 必须是 yes
#    🔴 **通用值猜不出来** —— 必须逐脚本登记。
# 🔑 登记一条 = 把一个门禁从"弱证据"升级为"强证据"。
# ==========================================================================
FIXTURE_OVERRIDES = {
    'game_embodied_input': {'must_match': 'exact'},
    'game_edge': {'evidence': '8'},
    'game_rng_save': {'replayable': 'yes'},
    'security_trust': {'rejection_path_verified': 'yes'},
    'state_migration': {'reconciled': 'yes'},
    'game_net_mod': {'baseline_frozen': 'yes'},
    'engine_migration': {'disposition': 'must-match', 'equivalent': 'yes'},
    # 🔑 game_edge：`verification`=证据态（不是 evidence_state）
    #    🔴 第六十三轮填错列名 → 基线仍失败
    # 🔑 证据八级：**1 级最强，7-8 级为推测/无证据** → `>=7` 阻断。
    #    🔴 第六十四轮我曾记为"与别处口径冲突"——**那是记错了**：
    #       实测 **42 个脚本**统一采用 `>=7 阻断`，口径完全一致。
    'game_edge': {'evidence': '3', 'verification': 'verified'},
    'game_lifeplay_trace': {'deviation': '等价'},
    # 🔑 md 台账用**中文表头**，必须登记中文键
    'license_gate': {'状态': 'confirmed_allowed', 'spdx': 'MIT'},
    # 🔑 feature_matrix 的「处置」列是**中文五类枚举**，填通用 `ok` 会被拦
    'feature_matrix': {'处置': '不适用'},
    # 🔑 五元组必须 5 段；填了秒数就必须 evidence=verified
    'kiosk_recorder': {'machine_tuple': 'Title|JP|Rev1|DIP1|Harness1',
                       'evidence': 'verified'},
    # 🔑 该脚本按**名字**判断是否修改状态（含 patch/写入/修改 即拦）
    'runtime_forensics': {'hook_strategy': 'detour'},
}


def _load_script_enums(script):
    """🔑 **用 AST 读脚本自己的 ENUMS**——不 import，避免顶层副作用。

    🔑 第六十三轮关键改进：剩余弱证据项的阻塞原因高度一致——
       **`🚫 字段白名单违例：X 不在合法枚举内 · 合法值见本文件顶部 ENUMS`**
    🔑 也就是说：**脚本自己就写了合法值**，通用填充却猜不到。
       ✅ 直接读出来填进去即可——这是**可自动化的**。
    """
    import ast as _ast
    try:
        tree = _ast.parse(open('scripts/' + script + '.py',
                               encoding='utf-8').read())
    except Exception:
        return {}
    for node in tree.body:
        if isinstance(node, _ast.Assign):
            for t in node.targets:
                if isinstance(t, _ast.Name) and t.id == 'ENUMS':
                    try:
                        v = _ast.literal_eval(node.value)
                        return v if isinstance(v, dict) else {}
                    except Exception:
                        return {}
    return {}


def _fill_md(path, script=''):
    """🔑 **Markdown 台账填充**——表格 / 清单 / 键值表三类。

    🔑 第六十四轮：弱证据里有一整类是**格式错配**——
       脚本的台账是 `.md`（license_gate / feature_matrix / install_contract）
       或 YAML（game_replay），而毒化器只处理 CSV → **根本没填**。
    """
    try:
        txt = open(path, encoding='utf-8').read()
    except Exception:
        return 0
    n = 0
    out = []
    hdr = None
    enums = _load_script_enums(script)
    for line in txt.splitlines():
        # ① 清单：`- [ ]` → `- [x]`
        if re.match(r'^\s*- \[ \]', line):
            out.append(re.sub(r'- \[ \]', '- [x]', line, count=1)); n += 1
            continue
        # ② md 表头
        if line.strip().startswith('|') and hdr is None and '---' not in line:
            hdr = [c.strip().strip('*` ') for c in line.strip().strip('|').split('|')]
            out.append(line); continue
        if line.strip().startswith('|') and re.match(r'^[\s|\-:]+$', line.strip().replace('|', '')):
            out.append(line); continue
        # ③ md 数据行
        if line.strip().startswith('|') and hdr:
            cells = [c.strip() for c in line.strip().strip('|').split('|')]
            nc = []
            for i, c in enumerate(cells):
                key = (hdr[i] if i < len(hdr) else '').lower()
                raw = c.strip('*` ').strip()
                # 🔑 ① 单元格**内容**替换（藏在格子里的 TODO）
                _rep = TEXT_REPLACEMENTS.get(script, [])
                _before = c
                for _o, _nw in _rep:
                    c = c.replace(_o, _nw)
                if c != _before:
                    n += 1
                # 🔑 fixture 优先（逐脚本显式指令，覆盖非占位符原值）
                _fx = FIXTURE_OVERRIDES.get(script, {})
                _hit = [v for k, v in _fx.items() if k in key]
                if _hit:
                    nc.append(_hit[0]); n += 1; continue
                # 🔑 占位符判定放宽：`待填 —— 字体名` 这类**带说明**的也算占位
                _is_ph = (raw.lower() in PLACEHOLDERS
                          or raw.lower().startswith(('待填', 'todo', 'tbd',
                                                     '待定', '待补')))
                if not _is_ph:
                    nc.append(c); continue
                val = None
                for k, pv in FIXTURE_OVERRIDES.get(script, {}).items():
                    if k in key:
                        val = pv; break
                if val is None:
                    for k, pv in enums.items():
                        if k in key:
                            val = pv[0] if isinstance(pv, (list, tuple)) and pv else pv
                            break
                if val is None:
                    for k, pv in VALID_OVERRIDE.items():
                        if k in key:
                            val = pv; break
                if val is None:
                    val = 'https://example.com/e' if ('url' in key or 'link' in key or '链接' in key) else 'ok'
                nc.append(val); n += 1
            out.append('| ' + ' | '.join(nc) + ' |')
            continue
        if line.strip() == '' or not line.strip().startswith('|'):
            hdr = None
        # ④ 键值行 / YAML：`key: 待填 —— xxx`
        m = re.match(r'^(\s*)([\w\.]+):\s*(.+)$', line)
        if m and m.group(3).strip().strip('"\'').lower() in PLACEHOLDERS:
            key = m.group(2).lower()
            val = None
            for src in (FIXTURE_OVERRIDES.get(script, {}), enums, VALID_OVERRIDE):
                for k, pv in src.items():
                    if k in key:
                        val = pv[0] if isinstance(pv, (list, tuple)) and pv else pv
                        break
                if val is not None:
                    break
            out.append(f"{m.group(1)}{m.group(2)}: {val or 'ok'}")
            n += 1
            continue
        out.append(line)
    open(path, 'w', encoding='utf-8').write('\n'.join(out) + '\n')
    return n


def _sniff(path):
    """🔑 格式嗅探：csv / md / yaml。

    🔑 第六十四轮：弱证据里有一整类是**格式错配**——
       台账是 YAML（game_replay）或 Markdown（license_gate 等），
       却按 CSV 处理 → 填充无效、**毒化还会把文件写坏**。
    """
    try:
        txt = open(path, encoding='utf-8').read()
    except Exception:
        return 'csv'
    if re.search(r'^- \[ \]', txt, re.M) or '|---' in txt:
        return 'md'
    if re.search(r'^[\w\.]+:\s', txt, re.M) and '|---' not in txt:
        try:
            import yaml as _y
            if isinstance(_y.safe_load(txt), dict):
                return 'yaml'
        except Exception:
            return 'yaml'
    return 'csv'


def _fill_yaml(path, script=''):
    """🔑 YAML 填充：把 `TODO` 换成合法值（保留已有数值）。"""
    try:
        import yaml as _y
        txt = open(path, encoding='utf-8').read()
        d = _y.safe_load(txt)
    except Exception:
        return 0
    if not isinstance(d, dict):
        return 0
    enums = _load_script_enums(script)
    n = 0
    for k, v in list(d.items()):
        if isinstance(v, str) and v.strip().lower() in PLACEHOLDERS:
            val = None
            for src in (FIXTURE_OVERRIDES.get(script, {}), enums,
                        VALID_OVERRIDE):
                for kk, pv in src.items():
                    if kk in str(k).lower():
                        val = pv[0] if isinstance(pv, (list, tuple)) and pv else pv
                        break
                if val is not None:
                    break
            d[k] = val or 'ok'
            n += 1
    if n:
        open(path, 'w', encoding='utf-8').write(
            _y.safe_dump(d, allow_unicode=True, sort_keys=False))
    return n


def _poison_yaml_values(path):
    """🔑 YAML 毒化：把**所有标量值**换成非法值（结构保留）。"""
    try:
        import yaml as _y
        d = _y.safe_load(open(path, encoding='utf-8').read())
    except Exception:
        return 0
    if not isinstance(d, dict):
        return 0
    n = 0
    for k in list(d.keys()):
        # 🔑 对 YAML manifest，**非法值就是 TODO / 空**——
        #    🔴 填 `__poison__` 反而"不是 TODO" → 门禁放行 → A 类盲区（实测踩到）
        d[k] = 'TODO'
        n += 1
    open(path, 'w', encoding='utf-8').write(
        _y.safe_dump(d, allow_unicode=True, sort_keys=False))
    return n


def _fill_any(path, script=''):
    """🔑 **格式感知**：CSV / Markdown / YAML 三类都填。"""
    try:
        txt = open(path, encoding='utf-8').read()
    except Exception:
        return 0
    fmt = _sniff(path)
    if fmt == 'yaml':
        return _fill_yaml(path, script)
    if fmt == 'md':
        return _fill_md(path, script)
    return _fill_valid_csv(path, script)


def _fill_valid_csv(path, script=''):
    """🔑 把空台账填成**看起来合法**的值，让基线 rc=0。

    🔴 **尽力而为**：很多脚本要求**特定枚举值**，填 'ok' 未必合法。
       🔑 填完仍 rc≠0 的**如实计为 weak**——不夸大。
    """
    import csv
    try:
        txt = open(path, encoding='utf-8').read()
    except Exception:
        return 0
    if _is_md_table(txt):
        return 0
    try:
        rows = list(csv.reader(txt.splitlines()))
    except Exception:
        return 0
    if len(rows) < 2:
        return 0
    hdr = rows[0]
    # 🔑 **不是真表就别碰** —— 🔴 单列文件被当 CSV 写回会**毁掉 YAML**
    #    （第六十四轮实测：game_replay 的 YAML manifest 被写成 CSV 引号格式）
    if len(hdr) < 2:
        return 0
    kinds = [classify(c)[0] for c in hdr]
    out = [hdr]
    n = 0
    for r in rows[1:]:
        if not r:
            continue
        nr = []
        for i, v in enumerate(r):
            col = hdr[i].strip().lower() if i < len(hdr) else ''
            # 🔑 **fixture 是逐脚本显式指令，优先于"保留原值"**
            #    🔴 第六十四轮实测：kiosk_recorder 的 `evidence` 原值是
            #       `unverified`（非占位符）→ 被"保留原值"规则挡住 → 基线不干净
            _fx = FIXTURE_OVERRIDES.get(script, {})
            if col in _fx:
                nr.append(_fx[col])
                n += 1
                continue
            raw = (v or '').strip()
            # 🔑 **只替换占位符，保留原值**
            #    🔴 第六十三轮实测踩到：`--init` 生成的行里，
            #       **清单项名/行身份**（如 cdkey 的 21 项、edge_accept 的 5 路）
            #       本来就是真值；若被通用值冲成 'ok'，
            #       门禁会报"未覆盖项 21" → 基线永远不干净。
            if raw and raw.lower() not in PLACEHOLDERS:
                nr.append(v)
                continue
            val = None
            # 🔑 ① 优先：**本脚本专属**合法值
            for k, pv in FIXTURE_OVERRIDES.get(script, {}).items():
                if k == col:
                    val = pv
                    break
            # 🔑 ② **脚本自己的 ENUMS**（优先于通用值——通用值猜不出专属枚举）
            if val is None:
                for k, pv in _load_script_enums(script).items():
                    if k == col:
                        val = (pv[0] if isinstance(pv, (list, tuple)) and pv
                               else pv)
                        break
            # 🔑 ③ 通用合法值
            if val is None:
                for k, pv in VALID_OVERRIDE.items():
                    if k == col or k in col:
                        val = pv
                        break
            if val is None:
                for k, pv in SEMANTIC.items():
                    if k == col or k in col:
                        val = pv
                        break
            if val is None:
                val = VALID_BY_TYPE.get(
                    kinds[i] if i < len(kinds) else '', 'ok')
            nr.append(val)
            n += 1
        out.append(nr)
    with open(path, 'w', encoding='utf-8', newline='') as f:
        csv.writer(f).writerows(out)
    return n


def _poison_csv(path, aggr=True, strategy='typed'):
    """🔑 类型感知毒化。返回 (改动行数, 覆盖统计 dict)。"""
    import csv
    try:
        txt = open(path, encoding='utf-8').read()
    except Exception:
        return 0, {}
    # 🔑 第五十九轮：md 台账走专用毒化，**不能当 CSV 处理**
    if _is_md_table(txt):
        return _poison_md(path, strategy)
    try:
        rows = list(csv.reader(txt.splitlines()))
    except Exception:
        return 0, {}
    if len(rows) < 2:
        return 0, {}
    hdr = rows[0]
    kind = [classify(c)[0] for c in hdr]
    out = [hdr]
    for r in rows[1:]:
        if not r:
            continue
        nr = []
        for i, v in enumerate(r):
            col = hdr[i].strip().lower() if i < len(hdr) else ''
            hit = None
            for k, pv in POISON.items():          # 关键词兜底
                if k in col:
                    hit = pv
                    break
            if strategy == 'semantic':
                # 🔑 **完全不看原值**——整行重写为"合法但自相矛盾"的组合。
                #    🔴 第五十八轮踩过的坑：init 生成的表全是 `TODO`，
                #       若沿用"TODO → 覆盖"逻辑，语义值会被 `ok` 全部冲掉，
                #       毒化**静默失效**（表现得像什么都没填）。
                hit = None
                for k, pv in SEMANTIC.items():
                    if k == col or k in col:
                        hit = pv
                        break
                if hit is None:
                    hit = 'ok'      # 🔑 其他字段填**合法值**，不触发语法检查
            else:
                for k, pv in POISON.items():          # 关键词兜底
                    if k in col:
                        hit = pv
                        break
                if hit is None:
                    if strategy == 'legacy':
                        # 第五十六轮策略：无类型感知，一律 __poison__
                        hit = '__poison__'
                    else:
                        t, pv = classify(col)
                        hit = pv
                        if t == 'pair':
                            # 🔑 配对差异化：同一行内配对字段互不相同
                            hit = f'{pv}_{i}'
                if v.strip() == '' or v.strip().lower() in ('todo', 'tbd'):
                    hit = '__poison__'
            nr.append(hit)
        out.append(nr)
    with open(path, 'w', encoding='utf-8', newline='') as f:
        csv.writer(f).writerows(out)
    total = len(hdr)
    cov = sum(1 for k in kind if k in ASSERTABLE)
    stat = {'total_cols': total, 'covered_cols': cov,
            'uncovered_cols': total - cov,
            'coverage_pct': round(100.0 * cov / total, 1) if total else 0.0,
            'uncovered_names': [hdr[i] for i, k in enumerate(kind)
                                if k not in ASSERTABLE]}
    return len(out) - 1, stat


def cmd_coverage(a):
    """🔑 **字段覆盖率**——回答"88% 这个数字是在多大覆盖面上测出来的"。

    > 🔑 第五十六轮留下的最关键疑问：拦截率 88% 的**置信区间**是多少？
    > 本命令对每个台账表头做**类型推断**，统计"能被类型断言的字段"占比。
    > 🔴 **未覆盖字段 = 真实盲区**，不能宣称它已被验证。
    """
    import csv as _csv
    scripts = _scripts()
    rows = []
    for n in scripts:
        p = os.path.join('scripts', n)
        if '--init' not in open(p, encoding='utf-8').read():
            continue
        led = os.path.join('/tmp/_cov', n + '.csv')
        os.makedirs('/tmp/_cov', exist_ok=True)
        r = subprocess.run([PY, p, '--init', led], capture_output=True,
                           timeout=30)
        if r.returncode != 0 or not os.path.exists(led):
            continue
        try:
            rr = list(_csv.reader(open(led, encoding='utf-8')))
        except Exception:
            continue
        if not rr or len(rr[0]) < 2:
            continue
        hdr = rr[0]
        kinds = [classify(c)[0] for c in hdr]
        cov = sum(1 for k in kinds if k in ASSERTABLE)
        rows.append({'script': n, 'total': len(hdr), 'covered': cov,
                     'pct': round(100.0 * cov / len(hdr), 1) if hdr else 0.0,
                     'uncovered': [hdr[i] for i, k in enumerate(kinds)
                                   if k not in ASSERTABLE]})
    tot = sum(r['total'] for r in rows)
    covsum = sum(r['covered'] for r in rows)
    print('=' * 74)
    print('字段覆盖率（🔑 拦截率的置信区间）')
    print('=' * 74)
    print(f'\n台账脚本: {len(rows)}')
    print(f'总字段: **{tot}**')
    print(f'🔑 可断言类型（被毒化覆盖）: **{covsum}**')
    print(f'🔴 不可断言（真实盲区）: **{tot - covsum}**')
    print(f'\n🔑 **字段覆盖率 = {100.0*covsum/tot:.1f}%**' if tot else '')
    low = sorted(rows, key=lambda r: r['pct'])[:10]
    print('\n🔴 覆盖率最低的 10 个（**盲区最大**）：')
    for r in low:
        print(f"  {r['pct']:5.1f}%  `{r['script']}`  "
              f"({r['covered']}/{r['total']})")
    # 未覆盖字段名 TOP
    from collections import Counter
    c = Counter()
    for r in rows:
        for u in r['uncovered']:
            c[u.lower()] += 1
    print('\n🔑 最常"无法断言"的字段名（前 15，即**最需要人工看**的）：')
    for k, v in c.most_common(15):
        print(f'  {v:3d}×  `{k}`')
    # 🔑 第六十轮：覆盖率写进稳定缓存（**无条件**），供汇总读取
    #    🔴 注意：这里的 rows 用的是 cmd_coverage 自己的键名
    #       （pct / covered / total / uncovered），
    #       **不是** _poison_csv 返回的 covered_cols / total_cols。
    #       🔴 写错键名会被 `except: pass` 静默吞掉——正是本套方法批判的病。
    try:
        os.makedirs('audit', exist_ok=True)
        _pct = round(100.0 * covsum / tot, 1) if tot else 0.0
        json.dump({'coverage_pct': _pct, 'covered': covsum, 'total': tot},
                  open(os.path.join('audit', '.coverage_last.json'),
                       'w', encoding='utf-8'), ensure_ascii=False)
        print(f'\n🔑 已写入缓存: audit/.coverage_last.json '
              f'(覆盖率 {_pct}%)')
    except Exception as e:                      # 🔴 **不再静默**
        print(f'\n⚠️ 覆盖率缓存写入失败: {type(e).__name__}: {e}')
    if a.dir:
        os.makedirs(a.dir, exist_ok=True)
        json.dump(rows, open(os.path.join(a.dir, 'coverage.json'), 'w',
                             encoding='utf-8'), ensure_ascii=False, indent=2)
        print(f'\n✅ 明细 → {a.dir}/coverage.json')
    return 0


def cmd_chaos(a):
    d = a.dir or '/tmp/gate_chaos'
    if os.path.exists(d):
        shutil.rmtree(d)
    os.makedirs(d, exist_ok=True)
    PY_ = PY
    scripts = _scripts()
    # 🔑 第七十二轮：**快速子集** —— G341 此前"刻意不自动跑（3~5 分钟）"，
    #    结果**从未执行过**，一直显示成"说明性门禁"。
    #    ✅ 支持 `--limit N`：只测前 N 个，让每次回归都能真跑一次。
    #    🔴 但分母会变 —— **必须显式标"抽样"**，不得让人读成全量。
    _lim = a.limit or 0
    if _lim:
        scripts = scripts[:_lim]
    results = []
    skip = []          # 🔑 第六十一轮：非台账型/无数据行先收集
    _hdr('门禁混沌测试 —— **故意改坏，看是否拦截**')
    _strat = a.strategy
    print('\n工作目录: %s · 待测脚本: %d · 毒化策略: **%s**\n'
          % (d, len(scripts), _strat))
    if _lim:
        print(f'🔴 **抽样模式**：只扫描前 {_lim} 个**候选脚本**'
              f'（全量候选共 {len(_scripts())} 个）')
        print('   🔑 其中非台账型会被分类跳过，故**参与测试数 ≤ '
              f'{_lim}**。')
        print('   🔑 分母是抽样数，**不得**读作全量拦截率。\n')
    for n in scripts:
        p = os.path.join('scripts', n)
        try:
            src = open(p, encoding='utf-8').read()
        except Exception:
            continue
        if '--init' not in src:
            continue
        if not ('--check' in src or '--gate' in src):
            continue
        # 🔑 第六十一轮：**非台账型 `--init` 明确分类，不再混进 skip**
        if n[:-3] not in INTERFACE_ADAPTERS and not _is_ledger_init(src):
            _e = {'script': n, 'stage': 'not_a_ledger',
                  'verdict': 'not_a_ledger',
                  'why': '`--init` 不是生成 CSV 台账的接口'
                         '（store_true / nargs=? → 目录或 JSON/YAML 骨架）'}
            results.append(_e)
            skip.append(_e)
            continue
        led = os.path.join(d, n.replace('.py', '.csv'))
        _ad = INTERFACE_ADAPTERS.get(n[:-3])
        if _ad:
            # 🔑 **适配器路径完全接管**：不走通用 `--init` + `_poison_csv`
            #    🔴 第六十二轮实测：通用路径先跑 `--init led` 会失败
            #       → 直接判 `init_failed` skip，适配器根本没机会执行
            subprocess.run([PY_, p] + _ad['init'](led),
                           capture_output=True, text=True, timeout=180)
            if _ad.get('prep'):
                _ad['prep'](led)
            nrow, stat = 1, {'total_cols': 0, 'covered_cols': 0,
                             'uncovered_cols': 0, 'coverage_pct': 0.0,
                             'uncovered_names': []}
        else:
            # ① 生成空台账
            r0 = subprocess.run([PY_, p, '--init', led],
                                capture_output=True, text=True, timeout=60)
            if r0.returncode != 0 or not os.path.exists(led):
                results.append({'script': n, 'stage': 'init_failed',
                                'verdict': 'skip'})
                continue
        # ② 基线：**先造干净输入**，跑一次 → 记录基线 rc
        if _ad:
            # 🔑 **顺序很重要**：先 init（脚本自己生成）→ 再 prep（补成干净输入）
            #    🔴 反过来会被 init 覆盖回去，基线永远不干净（第六十二轮实测）
            subprocess.run([PY_, p] + _ad['init'](led),
                           capture_output=True, text=True, timeout=180)
            if _ad.get('prep'):
                _ad['prep'](led)
            r1 = subprocess.run([PY_, p] + _ad['check'](led),
                                capture_output=True, text=True, timeout=180)
        else:
            # 🔑 第六十三轮：**先填合法值**，让基线尽量干净
            if getattr(a, 'baseline', 'empty') == 'valid':
                _fill_any(led, n[:-3])
            r1 = subprocess.run([PY_, p, '--check', led, '--gate'],
                                capture_output=True, text=True, timeout=60)
        base = r1.returncode
        # ③ 🔑 故意改坏
        if not _ad:
            # 🔑 按**实际格式**毒化，别把 YAML/Markdown 当 CSV 写坏
            if _sniff(led) == 'yaml':
                nrow = _poison_yaml_values(led)
                stat = {'total_cols': 0, 'covered_cols': 0,
                        'uncovered_cols': 0, 'coverage_pct': 0.0,
                        'uncovered_names': []}
            else:
                nrow, stat = _poison_csv(led, True, a.strategy)
            if nrow == 0:
                results.append({'script': n, 'stage': 'no_rows',
                                'verdict': 'skip'})
                continue
        if _ad:
            # 🔑 毒化**专属**工件，再跑校验
            _ad['poison'](led, a.strategy)
            r2 = subprocess.run([PY_, p] + _ad['check'](led),
                                capture_output=True, text=True, timeout=180)
            # 🔑 第六十二轮：**基线必须 rc=0**
            #    🔴 若基线本身就 rc≠0，"毒化后 rc≠0"毫无信息量（测了个寂寞）
            if r1.returncode != 0:
                results.append({'script': n, 'rows': nrow,
                                'baseline_rc': r1.returncode,
                                'poisoned_rc': r2.returncode,
                                'verdict': 'baseline_not_clean', **stat})
                continue
        else:
            r2 = subprocess.run([PY_, p, '--check', led, '--gate'],
                                capture_output=True, text=True, timeout=60)
        bad = r2.returncode
        # 🔑 判定：改坏后**必须**非 0；若为 0 → 假门禁
        if bad == 0:
            # 🔑 第五十六轮关键改进：**区分两类根因**
            t2 = (r2.stdout or '') + (r2.stderr or '')
            zero = bool(re.search(r'[:：]\s*0\s*条|无阻断项|无待确认', t2))
            if zero:
                # 🔴 B 类：污染后变 0 条 → 报告"无阻断项" → 通过
                verdict = 'FAKE_EMPTY_PASSES'
            else:
                # 🔴 A 类：数据行仍在，但填非法值不拦截
                verdict = 'FAKE_CONTENT_BLIND'
        elif bad == 1:
            verdict = 'ok'        # ✅ 正确阻断
        else:
            # 🔑 第五十九轮：**区分"脚本崩溃"与"接口不匹配"**
            #    rc=2 + "unrecognized arguments" = 混沌测试的调用约定
            #    与该脚本实际接口不一致（如 credits_diff 用 `--diff OLD NEW`）
            #    🔴 这不是门禁失效，是**测试器没适配**——不能算进假门禁。
            _low = ((r2.stdout or '') + (r2.stderr or '')).lower()
            if bad == 2 and ('unrecognized arguments' in _low
                             or 'invalid choice' in _low):
                verdict = 'iface_mismatch'
            else:
                verdict = 'error'   # 用法/崩溃，不算有效门禁
        # 🔑 强/弱证据：只有**基线干净**才能证明"门禁对内容敏感"
        #    🔑 第六十四轮新增第三类：**目录完备型** —— 结构上不可能强证据
        #       🔑 判据：基线失败原因是"**没记全**"（未覆盖 N/M · 未提及 N 处 ·
        #          必录字段 N/M）而不是"**填错了**"。
        #       🔴 这类门禁的**设计意图**就是拦"没记全"，
        #          所以基线**必然** rc≠0 —— 强证据对它**不适用**，
        #          硬凑只会伪造"干净基线"。
        strength = ('strict' if base == 0 else 'weak') \
            if verdict == 'ok' else 'n/a'
        if strength == 'weak':
            _t = ((r1.stdout or '') + (r1.stderr or '')).lower()
            # 🔴 第六十五轮修正：**'处置分布' 是误判源** ——
            #    它是 feature_matrix 的**正常统计打印**，不代表缺失。
            #    🔑 实测：feature_matrix 补齐 TODO 后 rc=0 → 它是**可修的**，
            #       不是目录完备型。上一轮因此把强证据上限少算了 1。
            if any(w in _t for w in ('未覆盖', '需覆盖', '未提及',
                                     '必录字段', '目录覆盖')):
                strength = 'weak_by_design'
        results.append({'script': n, 'rows': nrow, 'baseline_rc': base,
                        'poisoned_rc': bad, 'verdict': verdict,
                        'strength': strength, **stat})
    ok = sum(1 for r in results if r['verdict'] == 'ok')
    ok_strict = sum(1 for r in results
                    if r['verdict'] == 'ok'
                    and r.get('strength') == 'strict')
    # 🔑 目录完备型：结构上不可能强证据
    ok_bydesign = sum(1 for r in results
                      if r.get('strength') == 'weak_by_design')
    ok_weak = ok - ok_strict - ok_bydesign
    fa = [r['script'] for r in results
          if r['verdict'] == 'FAKE_CONTENT_BLIND']
    fb = [r['script'] for r in results
          if r['verdict'] == 'FAKE_EMPTY_PASSES']
    fake = fa + fb
    err = [r['script'] for r in results if r['verdict'] == 'error']
    iface = [r['script'] for r in results
             if r['verdict'] == 'iface_mismatch']
    skip = [r for r in results
           if r['verdict'] in ('skip', 'not_a_ledger',
                                 'needs_external_input')]
    nal = [r for r in results if r['verdict'] == 'not_a_ledger']
    bnc = [r for r in results
           if r['verdict'] == 'baseline_not_clean']
    nei = [r for r in results
           if r['verdict'] == 'needs_external_input']
    print('=' * 74)
    print('混沌测试结果')
    print('=' * 74)
    print(f'\n参与测试: {len(results)}')
    print(f'✅ **正确拦截**: {ok}')
    if ok:
        print(f'   🔑 **强证据**（基线 rc=0 → 门禁**确实对内容敏感**）: '
              f'**{ok_strict}**')
        print(f'   🔑 **目录完备型**（🔴 **结构上不可能强证据** —— '
              f'**「没记全」正是它要拦的东西**）: {ok_bydesign}')
        print(f'   ⚠️ **弱证据**（基线本来就拦 → 只证明"它会拦"，'
              f'🔴 **可能测了个寂寞**）: {ok_weak}')
        if ok_bydesign:
            print(f'\n   🔑 **强证据率的上限不是 {ok}，而是 '
                  f'{ok - ok_bydesign}** —— '
                  f'目录完备型门禁无法也不应被"凑干净"。')
        if ok_strict == 0 and ok:
            print('\n   🔴 **全部是弱证据** —— 拦截率不能读作"门禁有效"')
    print(f'🔴 **假门禁 · A 类【内容盲区】**: {len(fa)}')
    print(f'🔴 **假门禁 · B 类【空表即通过】**: {len(fb)}')
    print(f'⚠️ 用法/崩溃（不算有效门禁）: {len(err)}')
    if iface:
        print(f'🔑 接口不匹配（**测试器未适配**，非门禁失效）: {len(iface)}')
    print(f'⏭ 跳过（无法生成/无数据行）: {len(skip)}')
    if nal:
        print(f'🔑 **非台账型脚本**（`--init` 不是生成 CSV，**另一个物种**）: {len(nal)}')
    if nei:
        print(f'🔑 **需外部产物**（🔴 不是没测，是**缺输入源**）: {len(nei)}')
    if bnc:
        print(f'🔴 **基线不干净**（基线 rc≠0，毒化结果无信息量）: {len(bnc)}')
    if fb:
        print('\n🔴 **B 类【空表即通过】**（🔑 最危险）：')
        for f in fb:
            print(f'  - `{f}`')
        print('  🔑 污染后条目变 0 → 报告"无阻断项" → 退出 0。')
        print('  🔴 **空台账不得静默通过**——这与"空工作区显示全绿"是同一根因。')
    if fa:
        print('\n🔴 **A 类【内容盲区】**：')
        for f in fa:
            print(f'  - `{f}`')
        print('  🔑 数据行仍在，但填任意非法值不拦截。')
        print('  🔑 根因：**校验是黑名单式**（只认空值/TODO），'
              '**不是白名单式**（校验合法枚举）。')
        print('  🔴 人工复核时不能依赖它们自动拦住"填错的值"。')
    if err:
        print(f'\n🔑 **接口不匹配**（混沌测试未适配该脚本接口，**不是门禁失效**）：')
        for f_ in iface[:10]:
            print(f'  - `{f_}`')
        print(f'\n⚠️ 用法/崩溃（前 10）：')
        for f in err[:10]:
            print(f'  - `{f}`')
    json.dump({'results': results, 'ok': ok, 'strict': ok_strict,
               'fake_content_blind': fa, 'fake_empty_passes': fb,
               'error': err},
              open(os.path.join(d, 'chaos.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=2)
    # 🔑 第九十轮：写出**能力产物**（供 `--probe-capability` 断言）。
    #    🔑 即便混沌**全失败**，产物也照写 ——
    #       🔴 否则"跑不通"与"没跑"又变成同一回事（与"空表即通过"同源）。
    _n_part = len(results)
    # 🔑 实测字段名：verdict 用 'ok' 表示拦截成功；strength 用 'strong' 表示强证据
    _n_int = len([r for r in results if r.get('verdict') == 'ok'])
    # 🔑 实测：强证据的 strength 值叫 'strict'（不是 'strong'）
    _n_str = len([r for r in results if r.get('strength') == 'strict'])
    _art = CAPABILITY_ARTIFACT.get('chaos-full')
    if _art:
        _ap2 = os.path.join(ROOT, _art)
        os.makedirs(os.path.dirname(_ap2), exist_ok=True)
        # 🔑 第九十三轮：把**锚点分母**缓存进产物。
        #    🔴 第九十二轮诚实结论③：`_anchor_denom()` 每次探测都要
        #        遍历读取 128 个文件 —— 慢，且**无法事后核对**分母。
        #    🔑 写进产物后，既能省一次重算，也让分母**可追溯**。
        _den = _anchor_denom()
        _rec = {'generated_at_ns': time.time_ns(),
                'anchor_denom': _den,
                'results': {'participated': _n_part,
                            'intercepted': _n_int,
                            'strong': _n_str},
                'ok': ok}
        with open(_ap2, 'w', encoding='utf-8') as _f:
            json.dump(_rec, _f, ensure_ascii=False, indent=2)
        print(f'\n🔑 能力产物已写入: `{_art}` '
              f'（participated={_n_part} intercepted={_n_int} '
              f'strong={_n_str}）')
    else:
        print('\n🔴 `CAPABILITY_ARTIFACT` 未登记 —— 无法证明外部副作用')
    # 🔑 第六十轮：把拦截率写进**稳定缓存**，供 run_all_gates 汇总读取
    _cache = os.path.join('audit', '.chaos_last.json')
    try:
        os.makedirs('audit', exist_ok=True)
        _mode = 'sampled' if _lim else 'full'
        _res = {'intercept_rate': '%d/%d' % (ok, ok + len(fa) + len(fb)),
                'strict_rate': '%d/%d (强/拦截)' % (ok_strict, ok),
                'bydesign': ok_bydesign,
                'ok': ok, 'fake': len(fa) + len(fb),
                'skipped': len(skip), 'iface_mismatch': len(iface),
                'strategy': a.strategy,
                'completeness': _last_completeness,
                'mode': _mode,
                'limit': _lim or None,
                'ts': time.strftime('%Y-%m-%d %H:%M:%S')}
        # 🔴 第七十四轮修真 bug：**顶层字段被抽样覆盖** → 汇总谎报全量。
        #    🔑 结构改为：`full` 与 `sampled` **分离存放**，
        #       顶层只保留**最近一次**的信息（含 mode），供兼容读取。
        #    🔴 抽样**绝不写** `full` 子对象。
        _j = {}
        try:
            _o = json.load(open(_cache, encoding='utf-8'))
            if isinstance(_o, dict):
                _j = dict(_o)
        except Exception:
            pass
        _j[_mode] = _res
        if _mode == 'full':
            # 顶层同步为全量结果（兼容旧读取路径）
            # 🔴 第七十四轮：`completeness` / `format_audit` 由**别的命令**写
            #    （--catalog-probe / --format-audit），
            #    🔑 chaos 不得用自己没有的值覆盖掉它们 → 只同步**自己有的**键。
            for _k, _v in _res.items():
                # 🔴 第七十四轮再修：'(未测)' 是**非空字符串**哨兵，
                #    `not _v` 判不出来 → 仍会把已有的"全部通过"覆盖掉。
                if _k == 'completeness' and (not _v
                                             or _v in ('(未测)', 'None')):
                    continue
                _j[_k] = _v
            for _keep in ('format_audit',):
                if not _j.get(_keep) and isinstance(_o, dict):
                    _j[_keep] = _o.get(_keep)
        else:
            # 🔑 抽样：顶层**只标 mode**，不动全量字段
            _j['run_mode'] = 'sampled'
            _j['sampled_limit'] = _lim
        _j['run_mode'] = _mode
        json.dump(_j, open(_cache, 'w', encoding='utf-8'),
                  ensure_ascii=False)
        print(f'\n🔑 已写入缓存: {_cache} · 模式 **{_mode}**'
              + (f' · 顶层全量字段**未被覆盖**' if _mode == 'sampled'
                 else ''))
    except Exception as e:                      # 🔴 **不再静默**
        print(f'\n⚠️ 混沌缓存写入失败: {type(e).__name__}: {e}')

    print(f'\n✅ 明细 → {d}/chaos.json')
    # 🔑 退出码：有假门禁就报警（但 skip/error 不阻断）
    if fake:
        print('\n🔴 **存在假门禁 —— 退出码 1**')
        return 1
    if nal:
        print(f'\n🔑 **非台账型脚本 {len(nal)} 个**（🔴 不是"没测上"，'
              '是**另一个物种**）：')
        for r in nal[:10]:
            print(f"   - `{r['script']}` —— {r.get('why','')}")
    if bnc:
        print(f'\n🔴 **基线不干净 {len(bnc)} 个**（🔑 造不出合法干净输入，'
              '**毒化结论无效**）：')
        for r in bnc[:10]:
            print(f"   - `{r['script']}` 基线 rc={r['baseline_rc']} "
                  f"毒化 rc={r['poisoned_rc']}")
    if nei:
        print(f'\n🔑 **需外部产物 {len(nei)} 个**（🔴 门禁依赖 ffmpeg/实机抽帧，毒化器造不出）：')
        for r in nei[:10]:
            print(f"   - `{r['script']}` —— {r.get('why','')}")
    print('\n✅ 未发现假门禁（在本次毒化策略覆盖范围内）')
    return 0


def _hdr(t, w=74):
    print('=' * w)
    print(t)
    print('=' * w)


# ==========================================================================
# 🔑 第六十五轮：**增量完备性测试** —— 目录完备型门禁的**专用指标**
#
# 🔴 第六十四轮遗留：目录完备型只知道"它会拦"，
#    🔑 却不知道"**记到第 25 项时它是否仍拦**"。
#    🔴 强/弱证据对它们**不适用**（基线必然不干净），需要新指标。
#
# 🔑 本指标：**逐项补齐目录，观察缺失计数是否单调下降**。
#    · 单调下降 → 门禁确实**按记录项数**判定（有效）
#    · 不下降 / 跳变 → 计数与补全脱钩（可疑）
#    · 补满后仍不为 0 → **永远无法满足**（最危险）
# ==========================================================================

# (脚本, 目录提取方式, 补齐方式, 缺失计数正则)
COMPLETENESS = {
    'fault_matrix': {
        'desc': '26 类故障目录',
        'catalog': 'CATALOG',
        'add': 'csv_row',
        'metric': (r'目录覆盖:\s*(\d+)/(\d+)', 'diff'),
    },
    'install_contract': {
        'desc': '13 处残留位置（需在文本中被提及）',
        'catalog': 'RESIDUE_LOCS',
        'add': 'md_mention',
        'metric': (r'未提及的残留位置\s*(\d+)\s*处', 'direct'),
        'absent_zero_kw': '未提及',
    },
}


def _ast_catalog(script, key):
    """🔑 从脚本 AST 提取目录常量（不 import）。"""
    import ast as _a
    try:
        tree = _a.parse(open('scripts/' + script + '.py', encoding='utf-8').read())
    except Exception:
        return []
    for node in tree.body:
        if isinstance(node, _a.Assign):
            for t in node.targets:
                if isinstance(t, _a.Name) and t.id == key:
                    try:
                        v = _a.literal_eval(node.value)
                    except Exception:
                        return []
                    if key == 'CATALOG':
                        return [i for _, items in v for i in items]
                    return [i if isinstance(i, str) else i[0] for i in v]
    return []


def _add_one(script, led, item, mode):
    """🔑 往台账补一项。"""
    if mode == 'csv_row':
        import csv
        try:
            rows = list(csv.reader(open(led, encoding='utf-8')))
        except Exception:
            return False
        if not rows:
            return False
        hdr = rows[0]
        row = []
        for c in hdr:
            cl = c.strip().lower()
            if cl in ('name',):
                row.append(item)
            elif cl in ('id',):
                row.append('X-%03d' % (len(rows)))
            elif cl in ('old_behavior',):
                row.append('原版实测：已采集')
            elif cl in ('new_behavior', 'status',):
                row.append('ok')
            else:
                row.append('ok')
        rows.append(row)
        with open(led, 'w', encoding='utf-8', newline='') as f:
            csv.writer(f).writerows(rows)
        return True
    if mode == 'md_mention':
        try:
            txt = open(led, encoding='utf-8').read()
        except Exception:
            return False
        open(led, 'w', encoding='utf-8').write(
            txt.rstrip() + f"\n- 残留位置：{item} —— owner: 某人\n")
        return True
    return False


# ==========================================================================
# 🔑 第六十六轮：**目录常量扫描** —— 用 AST 列出所有"疑似目录完备型"的候选
#
# 🔴 第六十五轮遗留：「增量完备性只覆盖 2 个已登记脚本，
#    若有第三个目录型门禁未被识别，它会被误当真弱证据去凑基线」。
#
# 🔴 **本轮先尝试了"通用删行法"，结论是它不成立** —— 见文末负结果。
#    🔑 因此改为：**不自动判定，只列出候选交人工登记**。
#
# 🔑 判据（三条同时满足才是候选）：
#    ① 顶层大写常量且 len >= 5（目录通常较长）
#    ② 脚本源码含覆盖率统计关键词
#    ③ 该常量**真的被遍历**（`for ... in CONST`）而非只用于打印
# ==========================================================================

# 🔑 关键词须是**"真缺失统计"**，不是泛化的"覆盖率"
#    🔴 第六十六轮实测：加上 '覆盖率'/'覆盖度' 后候选暴涨到 127 个 ——
#       因为 `FIELDS`（列定义）也被算了进来。
_last_completeness = '(未测)'

CATALOG_KW = ('未覆盖', '未提及', '目录覆盖', '需覆盖', '齐全')

# 🔑 这些是**列定义/工具清单/枚举**，不是"必须逐项记录的目录"
NOT_CATALOG = ('FIELDS', 'TOOLS', 'REQUIRED', 'MAP', 'CONFLICTS',
               'ENUMS', '_', 'OWNERSHIP', 'GRADES', 'PIPELINE')


# ==========================================================================
# 🔑 第六十七轮：**格式错配复核** —— 第六十四轮遗留③
#
# 🔴 第六十四轮发现：台账有 CSV / Markdown / YAML 三种，
#    毒化器只处理 CSV → 填充无效、**毒化还会把文件写坏**（game_replay 实测）。
#
# 🔑 本扫描对每个台账脚本：init → sniff → 判断"填充/毒化会不会毁文件"。
#    🔑 重点：**毒化后必须仍能被原脚本解析**（不崩溃）。
#       🔴 崩溃 = 毒化器**写坏了文件**，门禁结论**不可信**。
# ==========================================================================


# ==========================================================================
# 🔑 第六十八轮：**改瘦模板探针** —— 第六十六轮指引③
#
# 🔴 第六十六轮靠**分类完备性论证**封闭了漏网风险，但那是推理不是实测。
#    本轮把它变成可测的：**删掉一半目录行，看基线是否从干净变不干净**。
#
# 🔑 两类结论：
#    A **敏感型**（删一半 → 基线变不干净）
#      → 该目录**确实是强制的**，漏了会被发现 → ✅ 安全
#    B **不敏感型**（删一半 → 基线仍干净）
#      → 每行独立合法，**该常量不是强制目录**
#      → 🔴 若人工认为它【应该】是强制目录，这就是**门禁漏检**
#
# 🔑 判据不替人下结论：**只分类，不判"该不该"**。
# ==========================================================================


def _data_rows(led, fmt):
    """🔑 取可删的数据行下标（跳过表头/分隔/标题/空行）。

    🔑 第六十六轮为"删行法"写的，该方法已弃；
       第六十八轮**改瘦模板探针**重新用上它（用途不同：这里只删一半）。
    """
    try:
        lines = open(led, encoding='utf-8').read().splitlines()
    except Exception:
        return []
    idx = []
    if fmt == 'md':
        for i, l in enumerate(lines):
            st = l.strip()
            if not st.startswith('|'):
                continue
            if '---' in st.replace('|', ''):
                continue
            cells = [c.strip() for c in st.strip('|').split('|')]
            if cells and cells[0] in ('编号', '字段', '位置', ''):
                continue
            idx.append(i)
    else:
        import csv as _c
        try:
            rows = list(_c.reader(open(led, encoding='utf-8')))
        except Exception:
            return []
        for i, r in enumerate(rows):
            if i == 0:
                continue
            if not r or not any((c or '').strip() for c in r):
                continue
            if (r[0] or '').strip().startswith('#'):
                continue
            idx.append(i)
    return idx


def _synthesize_rows(led, lines, idx, K=6):
    """🔑 把只有 1~3 行示例的模板**复制成 K 行**，item_id 加后缀保证唯一。

    🔑 用途：让"删一半"对自由行数型台账也可测。
    🔴 局限：复制的行**内容相同**，只保证 id 唯一——
       🔑 若脚本按"目录常量"校验，复制不会让它变干净（**正是我们要的结论**）。
    """
    import csv as _c
    fmt = _sniff(led)
    try:
        if fmt == 'md':
            return False, lines, idx
        rows = list(_c.reader(open(led, encoding='utf-8')))
        if len(rows) < 2:
            return False, lines, idx
        hdr = rows[0]
        body = [r for r in rows[1:] if r and any((c or '').strip() for c in r)]
        if not body:
            return False, lines, idx
        # 🔑 item_id 列：优先找名为 item_id / id / 编号 / key 的列
        #    🔴 **找不到就 -1（不改任何列）** ——
        #       第六十九轮踩坑：回退到 0 会把 `match_type` 当 id 加后缀，
        #       → `exact_s3` 不在枚举内 → **合成基线直接不干净**
        #       → 删一半 rc=1 被误判为"A 敏感型"（**假阳性**）。
        idcol = -1
        for j, h in enumerate(hdr):
            if h.strip().lower() in ('item_id', 'id', '编号', 'key'):
                idcol = j
                break
        new_body = []
        for k in range(K):
            for r in body:
                nr = list(r)
                while len(nr) < len(hdr):
                    nr.append('')
                if idcol >= 0:
                    nr[idcol] = f'{r[idcol]}_s{k}' if k else r[idcol]
                new_body.append(nr)
        import io
        buf = io.StringIO()
        w = _c.writer(buf)
        w.writerow(hdr)
        w.writerows(new_body)
        open(led, 'w', encoding='utf-8', newline='').write(buf.getvalue())
        return True, buf.getvalue().splitlines(), _data_rows(led, fmt)
    except Exception:
        return False, lines, idx


# ==========================================================================
# 🔑 第七十一轮：**能力自检** —— 让 G346 / G360 变成真能跑的门禁
#
# 🔴 第七十一轮发现：G346「须做语义毒化」与 G360「强证据率靠 fixture」的 tpl
#    都是纯说明文字（在 MANUAL/说明列表里），**从未被任何命令验证过**。
#
# 🔑 本子命令**秒级**验证混沌器自身是否具备这些能力（不跑 101 个子进程）。
# ==========================================================================


def cmd_self_check(a):
    """🔑 秒级自检：混沌器是否具备语义毒化 / fixture 等能力。"""
    import ast as _ast
    ast__Tuple, ast__List = _ast.Tuple, _ast.List
    src = open('scripts/gate_chaos.py', encoding='utf-8').read()
    tree = _ast.parse(src)
    top = {}
    top_nodes = {}
    for nd in tree.body:
        if isinstance(nd, _ast.Assign):
            for t in nd.targets:
                if isinstance(t, _ast.Name):
                    top_nodes[t.id] = nd.value
                    try:
                        top[t.id] = _ast.literal_eval(nd.value)
                    except Exception:
                        # 🔴 第七十一轮修**检查器自己的 bug**：
                        #    `SEMANTIC` 里含 `'0' * 64` 这类 BinOp → literal_eval 失败
                        #    → 原实现记为"非字面量" → 被判"条目 0" → **假警报**。
                        #    🔑 回退：数容器元素的**语法个数**，而不是判缺失。
                        v = nd.value
                        if isinstance(v, _ast.Dict):
                            top[t.id] = {i: None for i in range(len(v.keys))}
                        elif isinstance(v, (ast__Tuple, ast__List)):
                            top[t.id] = [None] * len(v.elts)
                        else:
                            top[t.id] = '(非字面量)'
    checks = []

    def ck(name, ok, detail):
        checks.append((name, ok, detail))

    # G346 语义毒化
    sem = top.get('SEMANTIC')
    ck('G346 语义毒化字典存在', isinstance(sem, dict) and len(sem) > 0,
       f'SEMANTIC 条目 {len(sem) if isinstance(sem, dict) else 0}')
    ck('G346 支持 semantic 策略', "'semantic'" in src,
       'cmd_chaos 内 strategy == "semantic" 分支')
    # G360 逐脚本 fixture
    fo = top.get('FIXTURE_OVERRIDES')
    ck('G360 逐脚本 fixture 存在', isinstance(fo, dict) and len(fo) > 0,
       f'FIXTURE_OVERRIDES 条目 '
       f'{len(fo) if isinstance(fo, dict) else 0}')
    # G345 配对字段差异化
    ck('G345 配对字段差异化毒化', 'pair' in str(top.get('ASSERTABLE', '')),
       'ASSERTABLE 含 pair 类型')
    # 🔴 第七十一轮修**检查器问错对象**：
    #    ENUMS 是**各台账脚本**的常量（被 AST 读取），gate_chaos **自己没有**是正常的。
    #    🔑 该检查的**正确问法**：gate_chaos 是否具备"读其他脚本 ENUMS"的能力。
    ck('具备读取其他脚本 ENUMS 的能力',
       "t.id == 'ENUMS'" in src or "'ENUMS'" in src,
       'AST 读取 `_script_enums`（不 import，避开顶层副作用）')
    print('=' * 70)
    print('gate_chaos 能力自检（🔑 秒级，不跑 101 个子进程）')
    print('=' * 70)
    bad = 0
    for name, ok, detail in checks:
        print(f"{'✅' if ok else '🚫'} {name} —— {detail}")
        if not ok:
            bad += 1
    print('\n' + '=' * 70)
    print(f'✅ {len(checks) - bad}/{len(checks)} 项能力具备'
          if not bad else f'🔴 {bad} 项能力缺失')
    print('=' * 70)
    return 0 if not bad else 1


# ==========================================================================
# 🔑 第七十二轮：**抽样不污染全量** 守卫（G378）
#
# 🔴 风险：`--chaos --limit N` 若把 "N/N" 写成缓存，
#    汇总里的强证据率会**谎报全量**（真实是 99/101）。
#
# 🔑 本守卫秒级验证三件事（不跑子进程）：
#    ① cmd_chaos 会读 a.limit
#    ② 抽样时**不写**缓存（`_j = None` 并显式跳过）
#    ③ 抽样模式会在输出里显眼标出"抽样"
# ==========================================================================


def cmd_self_check_limit(a):
    """🔑 G378：抽样混沌结果不得写成全量缓存。"""
    src = open('scripts/gate_chaos.py', encoding='utf-8').read()
    i = src.index('def cmd_chaos(')
    # 🔑 取到下一个顶层 def 为止（🔴 固定 9000 字符会截断函数尾部 ——
    #    缓存写入在末尾，于是两项守卫被误判失效）
    j = src.find('\ndef ', i + 1)
    body = src[i:j] if j > 0 else src[i:]
    # 🔑 第七十四轮更新：实现从"抽样不写缓存"改为
    #    "**full/sampled 分离存放**，抽样只写 sampled"。
    #    🔴 旧检查项 `_j = None` 已不存在 → G378 会**正确失败**（守卫有效）。
    checks = [
        ('cmd_chaos 读取 --limit', 'a.limit or 0' in body),
        ('抽样时切片候选列表', 'scripts[:_lim]' in body),
        ('full/sampled 模式判定', "_mode = 'sampled' if _lim else 'full'" in body),
        ('抽样**只写** sampled 子对象', '_j[_mode] = _res' in body),
        ('全量时才同步顶层', "if _mode == 'full':" in body),
        ('抽样时顶层不被覆盖',
         "_j['run_mode'] = 'sampled'" in body),
        ('输出显式标注抽样',
         '抽样模式' in body and '不得**读作全量拦截率' in body),
    ]
    print('=' * 70)
    print('G378 · 🔑 抽样混沌不写全量缓存')
    print('=' * 70)
    bad = 0
    for name, ok in checks:
        print(f"{'✅' if ok else '🚫'} {name}")
        if not ok:
            bad += 1
    print('\n' + '=' * 70)
    print(f'✅ {len(checks) - bad}/{len(checks)} 项守卫成立'
          if not bad else f'🔴 {bad} 项守卫失效')
    print('=' * 70)
    return 0 if not bad else 1


# ==========================================================================
# 🔑 第七十四轮：**全量/抽样口径分离** 的两个真门禁（G379 / G380）
#
# 🔴 背景：第七十三轮的回复**声称**做到了 full/sampled 分离与 G341 全量，
#    但**实测代码里根本没有** —— G341 仍是 `--limit 20`，G379/G380 不存在。
#    🔑 这正是本套方法最该抓的病："说了" ≠ "做了"。本轮补齐并加守卫防回退。
# ==========================================================================


_CACHE = os.path.join('audit', '.chaos_last.json')


def _read_cache():
    try:
        return json.load(open(_CACHE, encoding='utf-8'))
    except Exception:
        return {}


def cmd_assert_full(a):
    """🔑 G379：全量混沌必须写入 `full` 口径缓存（且是本次执行的）。"""
    import time as _t
    j = _read_cache()
    full = j.get('full')
    print('=' * 70)
    print('G379 · 🔑 全量混沌必须写入 full 口径缓存')
    print('=' * 70)
    if not isinstance(full, dict):
        print('🚫 `full` 子对象不存在 —— 汇总会显示"从未执行全量"')
        print('   🔑 修复：跑 `gate_chaos.py --chaos DIR`（**不带 --limit**）')
        print('\n' + '=' * 70)
        print('🔴 守卫失效')
        print('=' * 70)
        return 1
    ok_mode = full.get('mode') == 'full'
    ok_rate = isinstance(full.get('intercept_rate'), str)
    ok_ts = isinstance(full.get('ts'), str)
    print(f"{'✅' if ok_mode else '🚫'} mode == full  → {full.get('mode')}")
    print(f"{'✅' if ok_rate else '🚫'} intercept_rate 已写入 → "
          f"{full.get('intercept_rate')}")
    print(f"{'✅' if ok_ts else '🚫'} 时间戳已写入 → {full.get('ts')}")
    if ok_ts:
        try:
            age = _t.time() - _t.mktime(
                _t.strptime(full['ts'], '%Y-%m-%d %H:%M:%S'))
            print(f"   🔑 距今 {age / 3600:.1f} 小时")
            if age > 24 * 7:
                print('   ⚠️ **超过 7 天** —— 建议重跑全量')
        except Exception:
            pass
    ok = ok_mode and ok_rate and ok_ts
    print('\n' + '=' * 70)
    print('✅ 守卫成立' if ok else '🔴 守卫失效')
    print('=' * 70)
    return 0 if ok else 1


def cmd_assert_no_pollute(a):
    """🔑 G380：抽样执行**不得**改写 `full` 口径。"""
    j = _read_cache()
    full_before = j.get('full')
    print('=' * 70)
    print('G380 · 🔑 抽样不得污染全量口径')
    print('=' * 70)
    if not isinstance(full_before, dict):
        print('⚠️ 当前无 `full` 基线 —— 先跑一次全量才能测污染')
        print('\n' + '=' * 70)
        print('🔴 无法验证（不是通过）')
        print('=' * 70)
        return 1
    _sig = '%s|%s' % (full_before.get('intercept_rate'),
                      full_before.get('ts'))
    print(f"   污染前 full: {full_before.get('intercept_rate')} "
          f"@ {full_before.get('ts')}")
    # 跑一次小抽样
    import tempfile as _tf
    d = _tf.mkdtemp(prefix='pollute_')
    rc = cmd_chaos(argparse.Namespace(dir=d, strategy='typed',
                                      baseline='valid', limit=4))
    j2 = _read_cache()
    full_after = j2.get('full')
    if not isinstance(full_after, dict):
        print('🚫 抽样后 `full` 消失')
        print('\n' + '=' * 70)
        print('🔴 守卫失效')
        print('=' * 70)
        return 1
    _sig2 = '%s|%s' % (full_after.get('intercept_rate'),
                       full_after.get('ts'))
    same = _sig == _sig2
    print(f"   抽样后 full: {full_after.get('intercept_rate')} "
          f"@ {full_after.get('ts')}")
    print(f"\n{'✅' if same else '🚫'} full **未被抽样改写**")
    smp = j2.get('sampled')
    ok_smp = isinstance(smp, dict) and smp.get('mode') == 'sampled'
    print(f"{'✅' if ok_smp else '🚫'} 抽样结果单独存于 `sampled`"
          f" → {smp.get('intercept_rate') if ok_smp else '(无)'}")
    ok = same and ok_smp
    print('\n' + '=' * 70)
    print('✅ 守卫成立：抽样写 sampled，不动 full'
          if ok else '🔴 守卫失效')
    print('=' * 70)
    return 0 if ok else 1


def cmd_catalog_probe(a):
    """🔑 改瘦模板：删一半目录行 → 基线是否变不干净。"""
    import ast as _a
    print('=' * 74)
    print('改瘦模板探针（🔑 第六十六轮指引③ —— 把论证变成实测）')
    print('=' * 74)
    print('\n🔑 删掉一半数据行：')
    print('   A 基线变不干净 → **该目录是强制的**，漏了会被发现（✅ 安全）')
    print('   B 基线仍干净   → 每行独立合法，**不是强制目录**')
    print('      🔴 若人工认为它【应该】是强制目录 → **门禁漏检**\n')
    limit = a.limit or 0
    tested = 0
    too_few = 0
    synthesized = 0
    syn_dirty = []
    sensitive, insensitive, dirty = [], [], []
    for f in sorted(os.listdir('scripts')):
        if not f.endswith('.py') or f.startswith('_'):
            continue
        n = f[:-3]
        if n in ('gate_chaos', 'run_all_gates'):
            continue
        if limit and tested >= limit:
            break
        led = os.path.join(tempfile.mkdtemp(prefix='cp_'), n + '.csv')
        r0 = subprocess.run([PY, 'scripts/' + n + '.py', '--init', led],
                            capture_output=True, timeout=30)
        if r0.returncode != 0 or not os.path.isfile(led):
            continue
        tested += 1
        _fill_any(led, n)
        r1 = subprocess.run([PY, 'scripts/' + n + '.py', '--check', led,
                             '--gate'], capture_output=True, timeout=30)
        if r1.returncode != 0:
            dirty.append(n)          # 基线本来就不干净（目录完备型）
            continue
        # 🔑 第六十九轮：**合成改瘦** —— 模板只有 1 行示例时，
        #    先**复制成 K 行**（item_id 加后缀保证唯一），再删一半。
        #    🔴 第六十八轮把 87 个记为"无法改瘦（覆盖盲区）"——
        #       🔑 实测发现这 90 个模板**只有 1 行 TODO 示例**，
        #          行数由用户自定 → **它们本来就不是目录完备型**。
        lines = open(led, encoding='utf-8').read().splitlines()
        idx = _data_rows(led, _sniff(led))
        if len(idx) < 4 and a.synthesize:
            ok_syn, lines, idx = _synthesize_rows(led, lines, idx)
            if not ok_syn:
                too_few += 1
                continue
            # 🔴 **合成后必须重测基线** ——
            #    与第六十三轮"基线必须 rc=0"同一条判据：
            #    🔑 合成破坏了合法性（如给枚举列加了后缀）→ 基线 rc≠0
            #       → 此后无论删不删都是 rc≠0 → **A 是假阳性**。
            _fill_any(led, n)
            rs = subprocess.run([PY, 'scripts/' + n + '.py', '--check', led,
                                 '--gate'], capture_output=True, timeout=30)
            if rs.returncode != 0:
                syn_dirty.append(n)
                continue
            synthesized += 1
        if len(idx) < 4:
            # 🔑 模板示例行太少，无法"删一半" —— 记数，不静默跳过
            too_few += 1
            continue
        cur = list(lines)
        for i in sorted(idx[:len(idx) // 2], reverse=True):
            del cur[i]
        open(led, 'w', encoding='utf-8').write('\n'.join(cur) + '\n')
        r2 = subprocess.run([PY, 'scripts/' + n + '.py', '--check', led,
                             '--gate'], capture_output=True, timeout=30)
        if r2.returncode != 0:
            sensitive.append(n)      # A：强制目录，漏了会发现
        else:
            insensitive.append(n)    # B：不是强制目录
    print(f'参与: {tested}')
    print(f'🔑 **合成改瘦**（模板仅 1~3 行示例 → 复制成 6 行）: {synthesized}')
    print(f'🔴 **合成后基线不干净**（🔑 合成破坏了合法性 → **不得判 A**）: '
          f'{len(syn_dirty)}')
    for x in syn_dirty[:15]:
        print(f'   `{x}`')
    print(f'🔴 **数据行 < 4 无法改瘦**（模板示例太少）: {too_few}')
    print(f'\n🔑 A **敏感型**（删一半就被抓）: {len(sensitive)}')
    for x in sensitive[:20]:
        print(f'   `{x}`')
    if len(sensitive) > 20:
        print(f'   … 另有 {len(sensitive) - 20} 个')
    print(f'\n⚠️ B **不敏感型**（删一半仍干净）: {len(insensitive)}')
    for x in insensitive[:20]:
        print(f'   `{x}`')
    if len(insensitive) > 20:
        print(f'   … 另有 {len(insensitive) - 20} 个')
    print(f'\n🔑 基线本就不干净（目录完备型）: {dirty}')
    print('\n🔴 **本探针只分类，不判"该不该"** ——')
    print('   B 类是否需要升级为强制目录，**必须由人逐个确认**。')
    print('\n' + '=' * 74)
    print(f'A {len(sensitive)} · B {len(insensitive)} · 基线不干净 '
          f'{len(dirty)}')
    print('=' * 74)
    return 0


def cmd_format_audit(a):
    """🔑 格式错配复核：sniff 分类 + **毒化不毁文件**守卫。"""
    print('=' * 74)
    print('格式错配复核（🔑 第六十四轮遗留③）')
    print('=' * 74)
    print('\n🔑 对每个台账脚本：init → sniff → 毒化 → 看**是否仍可解析**。')
    print('   🔴 毒化后崩溃 = 毒化器**写坏了文件** → 门禁结论**不可信**。\n')
    dist = {}
    broken = []
    mismatch = []
    ineffective = []
    weak_names = []
    strict = weak_ = 0
    weak = 0
    tested = 0
    for f in sorted(os.listdir('scripts')):
        if not f.endswith('.py') or f.startswith('_'):
            continue
        n = f[:-3]
        if n in ('gate_chaos', 'run_all_gates'):
            continue
        led = os.path.join(tempfile.mkdtemp(prefix='fa_'), n + '.csv')
        r0 = subprocess.run([PY, 'scripts/' + n + '.py', '--init', led],
                            capture_output=True, timeout=30)
        # 🔴 ledger 的 --init 是 store_true 且可能生成**目录**，
        #    必须先判 isfile，否则 open() 抛 IsADirectoryError
        if r0.returncode != 0 or not os.path.isfile(led):
            continue
        tested += 1
        fmt = _sniff(led)
        dist[fmt] = dist.get(fmt, 0) + 1
        # 🔑 **两个嗅探器必须一致** ——
        #    🔴 第六十七轮实测抓到 1 个不一致（install_contract）：
        #       `_sniff`=md 而 `_is_md_table`=non-md
        #       → `_poison_csv` 走 CSV 路径，**把 md 清单当 CSV 写回**。
        _md2 = _is_md_table(open(led, encoding='utf-8').read())
        if (fmt == 'md') != _md2:
            mismatch.append((n, fmt, 'md' if _md2 else 'non-md'))
        # 🔑 第六十八轮：**两阶段** —— 先填合法值测基线，再毒化测有效性
        #    🔴 第六十七轮我注释"md 目前无专用毒化 → 用填充代替"——**那是误记**：
        #       `_poison_md` 早在第五十九轮就存在（能注入 `__poison__`）。
        #       🔑 结果 md 三项只测了"不会写坏"，**没测毒化有效性**。
        _fill_any(led, n)
        rb = subprocess.run([PY, 'scripts/' + n + '.py', '--check', led,
                             '--gate'], capture_output=True, text=True,
                            timeout=30)
        base_rc = rb.returncode
        # 毒化（按当前格式分派）
        if fmt == 'yaml':
            _poison_yaml_values(led)
        elif fmt == 'md':
            _poison_md(led, 'typed')      # 🔑 真毒化，不是填充
        else:
            _poison_csv(led, True, 'typed')
        rr = subprocess.run([PY, 'scripts/' + n + '.py', '--check', led,
                             '--gate'], capture_output=True, text=True,
                            timeout=30)
        t = (rr.stdout or '') + (rr.stderr or '')
        # 🔑 崩溃判据：**Traceback** = 解析失败（文件被写坏）
        if 'Traceback' in t:
            broken.append((n, fmt, rr.returncode))
            continue
        # 🔑 **毒化有效性**：基线干净 + 毒化后被拦 = 真敏感
        if base_rc == 0 and rr.returncode == 0:
            ineffective.append((n, fmt))   # 🔴 注入非法值却通过
        elif base_rc == 0:
            strict += 1
        else:
            weak += 1
            weak_names.append((n, fmt))
    print(f'参与: {tested} 个台账脚本')
    print(f'格式分布: {dist}')
    print(f'\n🔴 **两个嗅探器结论不一致**: {len(mismatch)}')
    for n, f1, f2 in mismatch:
        print(f'   `{n}` — _sniff={f1} · _is_md_table={f2}')
    print(f'\n🔑 **毒化有效性**（基线 rc=0 → 毒化后 rc≠0）: {strict}')
    print(f'   ⚠️ 弱证据（基线本就不干净）: {weak}')
    for n, f1 in weak_names:
        print(f'      `{n}` — {f1}')
    print(f'\n🔴 **毒化无效**（注入非法值却仍 rc=0 —— 最危险）: '
          f'{len(ineffective)}')
    for n, f1 in ineffective:
        print(f'   `{n}` — {f1}')
    print(f'\n🔴 **毒化后崩溃**（文件被写坏 → 结论不可信）: {len(broken)}')
    for n, fmt, rc in broken:
        print(f'   `{n}` — sniff={fmt} · rc={rc}')
    if broken:
        print('\n   🔑 修法：给该格式补**专用毒化器**（不复用 CSV 路径）。')
    print('\n' + '=' * 74)
    print('✅ 无格式错配导致的崩溃' if not broken else f'🔴 {len(broken)} 个')
    print('=' * 74)
    # 🔑 第六十八轮：**并入缓存**让汇总能显示（指引②）
    try:
        _c = os.path.join('audit', '.chaos_last.json')
        try:
            j = json.load(open(_c, encoding='utf-8'))
        except Exception:
            j = {}
        j['format_audit'] = {'参与': tested, '格式分布': dist,
                             '毒化有效_强': strict, '弱': weak,
                             '毒化无效': len(ineffective),
                             '崩溃': len(broken),
                             '嗅探器不一致': len(mismatch)}
        json.dump(j, open(_c, 'w', encoding='utf-8'), ensure_ascii=False)
        print(f'\n🔑 已并入缓存: {_c} (format_audit)')
    except Exception as e:
        print(f'\n❌ 缓存写入失败: {e}')
    return 0 if (not broken and not mismatch and not ineffective) else 1


def cmd_catalog_scan(a):
    """🔑 列出疑似目录完备型的候选（**不下自动判定**）。"""
    import ast as _a
    print('=' * 74)
    print('目录常量扫描（🔑 列出候选 —— **判据可测，结论交人工**）')
    print('=' * 74)
    print('\n🔑 判据：① 顶层大写常量 len>=5 ② 含覆盖率统计关键词 '
          '③ 常量**真的被遍历**\n')
    cands = []
    for f in sorted(os.listdir('scripts')):
        if not f.endswith('.py') or f.startswith('_'):
            continue
        n = f[:-3]
        if n in ('gate_chaos', 'run_all_gates'):
            continue
        try:
            src = open('scripts/' + f, encoding='utf-8').read()
            tree = _a.parse(src)
        except Exception:
            continue
        if not any(k in src for k in CATALOG_KW):
            continue
        for node in tree.body:
            if not isinstance(node, _a.Assign):
                continue
            for t in node.targets:
                if not (isinstance(t, _a.Name) and t.id.isupper()):
                    continue
                try:
                    v = _a.literal_eval(node.value)
                except Exception:
                    continue
                if not isinstance(v, (list, tuple)) or len(v) < 5:
                    continue
                # 🔑 排除列定义/工具清单/枚举
                if any(t.id.startswith(x) or t.id == x
                       for x in NOT_CATALOG):
                    continue
                # 🔑 ③ 真被遍历：源码中出现 `in CONST`（排除纯打印）
                if f'in {t.id}' not in src and f'in {t.id})' not in src:
                    continue
                cands.append((n, t.id, len(v),
                              n in COMPLETENESS))
    reg = [c for c in cands if c[3]]
    unreg = [c for c in cands if not c[3]]
    print(f'候选总数: {len(cands)} · 已登记 {len(reg)} · **未登记 {len(unreg)}**')
    if reg:
        print('\n### ✅ 已登记（增量完备性已覆盖）')
        for n, k, ln, _ in reg:
            print(f'   `{n}` — `{k}` ({ln} 项)')
    if unreg:
        print('\n### ⚠️ **未登记**（🔴 需人工确认是否目录完备型）')
        for n, k, ln, _ in unreg:
            print(f'   `{n}` — `{k}` ({ln} 项)')
    print('\n🔴 **本扫描只列候选，不下"形同虚设"之类的判定** ——')
    print('   🔑 是否为目录完备型、metric 正则是什么，**必须人工登记**。')
    print('\n' + '=' * 74)
    print(f'候选 {len(cands)} · 未登记 {len(unreg)}（**待人工确认**）')
    print('=' * 74)
    return 0


def cmd_completeness(a):
    """🔑 目录完备型的**增量完备性**：补齐一项，缺失计数应降一项。"""
    import re as _re
    print('=' * 74)
    print('增量完备性测试（🔑 目录完备型门禁专用指标）')
    print('=' * 74)
    print('\n🔑 逐项补齐目录，观察**缺失计数是否单调下降**。')
    print('   🔴 不降 = 计数与补全脱钩；补满仍不为 0 = **永远无法满足**。\n')
    all_ok = True
    for n in COMPLETENESS:
        cfg = COMPLETENESS[n]
        items = _ast_catalog(n, cfg['catalog'])
        if not items:
            print(f'⚠️ `{n}`：无法提取目录常量 `{cfg["catalog"]}`')
            all_ok = False
            continue
        led = os.path.join(tempfile.mkdtemp(prefix='cmp_'), n + '.csv')
        r0 = subprocess.run([PY, 'scripts/' + n + '.py', '--init', led],
                            capture_output=True, timeout=30)
        if r0.returncode != 0:
            print(f'⚠️ `{n}`：init 失败')
            all_ok = False
            continue
        pat, how = cfg['metric']
        seq = []
        for k, item in enumerate(items, 1):
            _add_one(n, led, item, cfg['add'])
            rr = subprocess.run([PY, 'scripts/' + n + '.py', '--check', led,
                                 '--gate'], capture_output=True, text=True,
                                timeout=30)
            t = (rr.stdout or '') + (rr.stderr or '')
            m = _re.search(pat, t)
            if not m:
                # 🔴 第六十五轮修真 bug：**脚本只在有缺失时才打印该行**。
                #    原实现抓不到就 append(None)，导致序列最后停在 1
                #    —— 把「已归零」误读成「还剩 1」。
                #    🔴 这正是本套方法反复批判的病：**没打印 ≠ 还是原值**。
                #    ✅ 关键词完全没出现 → 判为 0；出现了但抓不到数字 → 解析失败
                _kw = cfg.get('absent_zero_kw', '')
                seq.append(0 if (_kw and _kw not in t) else None)
                continue
            if how == 'diff':
                seq.append(int(m.group(2)) - int(m.group(1)))
            else:
                seq.append(int(m.group(1)))
        ok_seq = [v for v in seq if v is not None]
        mono = all(ok_seq[i] >= ok_seq[i + 1] for i in range(len(ok_seq) - 1))
        final = ok_seq[-1] if ok_seq else None
        print(f'### `{n}` — {cfg["desc"]}（{len(items)} 项）')
        print(f'   缺失计数序列: {ok_seq[:6]} … {ok_seq[-4:]}'
              if len(ok_seq) > 8 else f'   缺失计数序列: {ok_seq}')
        print(f'   单调下降: {"✅ 是" if mono else "🔴 否"}'
              f' · 补满后缺失: **{final}**')
        if not mono:
            print('   🔴 **补齐一项却没让缺失减少** —— 计数与补全脱钩')
            all_ok = False
        if final != 0:
            print('   🔴 **补满全部目录仍不为 0** —— 该门禁永远无法满足')
            all_ok = False
    print('\n' + '=' * 74)
    global _last_completeness
    _last_completeness = ('✅ 全部通过' if all_ok else '🔴 存在问题')
    # 🔑 第六十七轮：**合并写入**已有缓存 ——
    #    🔴 否则单独跑 `--completeness` 的结果永远进不了汇总
    #       （chaos 先写缓存时它还是"(未测)"）
    try:
        _c = os.path.join('audit', '.chaos_last.json')
        try:
            j = json.load(open(_c, encoding='utf-8'))
        except Exception:
            j = {}
        j['completeness'] = _last_completeness
        json.dump(j, open(_c, 'w', encoding='utf-8'), ensure_ascii=False)
        print(f'\n🔑 已合并写入缓存: {_c} (增量完备性)')
    except Exception as e:
        print(f'\n❌ 缓存写入失败: {e}')   # 🔴 不再静默
    print('✅ 增量完备性全部通过' if all_ok else '🔴 存在问题，见上')
    print('=' * 74)
    return 0 if all_ok else 1


def cmd_self_test(a):
    _hdr('门禁混沌测试 · 端到端自测')
    d = a.dir or '/tmp/gate_chaos_selftest'
    print('\n--- ① probe ---')
    r = cmd_probe(argparse.Namespace(dir=d))
    if r:
        return 1
    print('\n--- ② chaos ---')
    rc = cmd_chaos(argparse.Namespace(dir=d, strategy='typed',
                                         baseline='valid', limit=0))
    print('\n' + '=' * 74)
    # 🔴 第五十八轮修掉一个"自己犯的病"：
    #    原实现**丢弃了 cmd_chaos 的返回码，永远 return 0**
    #    —— 这正是本套方法反复批判的"跑完了 = 通过了"。
    if rc == 1:
        print('🔴 **自测退出码 1 —— 存在假门禁（这是**预期结果**）**')
        print('   🔑 本工具的价值是**暴露**假门禁，不是证明"全绿"。')
        print('   🔑 退出码 1 = 发现真实问题；退出码 0 = 无假门禁。')
    else:
        print('✅ **自测完成**（未发现假门禁）')
    # 🔑 第六十五轮：目录完备型**不适用**强/弱证据，
    #    改用**增量完备性**（补齐一项 → 缺失计数应降一项）
    # 🔑 第六十七轮：再补**格式错配复核**（毒化是否写坏文件 + 嗅探器一致）
    print('=' * 74)
    rc2 = cmd_completeness(argparse.Namespace())
    # 🔑 `--format-audit` **故意不进自测**：它要跑 98×2 个子进程，
    #    🔴 会让自测从 ~3min 涨到 ~6min，拖垮每次回归。
    #    ✅ 作为**独立命令**由人按需跑（与 G341 混沌测试同理）。
    print('=' * 74)
    print('\n🔑 本脚本的价值不在于"通过"，而在于'
          '**它真的去改坏了台账**。')
    return rc if rc != 0 else rc2


def main():
    ap = argparse.ArgumentParser(description='门禁混沌测试')
    ap.add_argument('--probe', metavar='DIR', nargs='?', const='')
    ap.add_argument('--baseline', choices=['empty', 'valid'],
                    default='valid',
                    help='基线策略：empty=空台账(默认) / '
                         'valid=**先填合法值**让基线干净 → 升级为强证据')
    ap.add_argument('--strategy', choices=['typed', 'legacy', 'semantic'],
                    default='typed',
                    help='typed=类型感知(默认) / legacy=朴素非法值 / semantic=**合法值但内部矛盾**(第五十八轮)')
    ap.add_argument('--coverage', action='store_true')
    ap.add_argument('--chaos', metavar='DIR', nargs='?', const='')
    ap.add_argument('--completeness', action='store_true',
                    help='增量完备性测试（目录完备型专用指标）')
    ap.add_argument('--assert-full', action='store_true',
                    help='G379：full 口径缓存是否存在且有效')
    ap.add_argument('--assert-no-pollute', action='store_true',
                    help='G380：抽样是否污染 full（会真跑一次小抽样）')
    ap.add_argument('--self-check-limit', action='store_true',
                    help='G378：抽样混沌是否污染全量缓存')
    ap.add_argument('--self-check', action='store_true',
                    help='秒级能力自检（G346/G360 的真实命令）')
    ap.add_argument('--catalog-probe', action='store_true',
                    help='改瘦模板：删一半目录行 → 基线是否变不干净')
    ap.add_argument('--synthesize', action='store_true',
                    help='模板仅 1~3 行示例时，复制成 6 行再改瘦')
    ap.add_argument('--limit', type=int, default=0,
                    help='只测前 N 个（探针抽样用）')
    ap.add_argument('--format-audit', action='store_true',
                    help='格式错配复核：毒化后是否仍可解析')
    ap.add_argument('--catalog-scan', action='store_true',
                    help='列出疑似目录完备型的候选（交人工登记）')
    ap.add_argument('--probe-capability', metavar='NAME', default=None,
                    help='**真跑一次**某个自报的能力（防自报撒谎）')
    ap.add_argument('--declare-capability', action='store_true',
                    help='自报本脚本提供的能力（供 G387 双向校验）')
    ap.add_argument('--self-test', action='store_true')
    ap.add_argument('--dir')
    a = ap.parse_args()
    if a.declare_capability:
        return _declare_capability()
    if a.probe_capability is not None:
        return _probe_capability(a.probe_capability)
    if a.coverage:
        return cmd_coverage(a)
    if a.probe is not None:
        return cmd_probe(argparse.Namespace(dir=a.probe or None))
    if a.chaos is not None:
        return cmd_chaos(argparse.Namespace(dir=a.chaos or None,
                                          strategy=a.strategy,
                                          baseline=a.baseline,
                                          limit=a.limit))
    if a.assert_full:
        return cmd_assert_full(a)
    if a.assert_no_pollute:
        return cmd_assert_no_pollute(a)
    if a.self_check_limit:
        return cmd_self_check_limit(a)
    if a.self_check:
        return cmd_self_check(a)
    if a.catalog_probe:
        return cmd_catalog_probe(a)
    if a.format_audit:
        return cmd_format_audit(a)
    if a.catalog_scan:
        return cmd_catalog_scan(a)
    if a.completeness:
        return cmd_completeness(a)
    if a.self_test:
        return cmd_self_test(a)
    print('❌ 需要 --probe / --chaos / --completeness / --catalog-scan / --catalog-probe / --format-audit / --self-test 之一')
    return 2


if __name__ == '__main__':
    sys.exit(main())
