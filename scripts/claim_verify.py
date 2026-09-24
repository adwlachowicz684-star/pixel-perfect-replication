#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
claim_verify.py —— 🔑 **声明核实器**（第七十五轮）

## 为什么需要它

🔴 第七十四轮发现：**第七十三轮的回复声称做了三条，代码里一条都没有。**
   - G341 全量（实为 `--limit 20`）
   - G379 / G380 / G381（grep 无匹配）
   - full/sampled 分离（缓存无此键）

🔑 本脚本把"回读代码逐条核对声明"变成**可执行的动作**：
   声明清单 → 逐条回读真实代码/缓存 → 未兑现即 **rc=1**。

## 用法

    # ① 扫文档里提到的门禁编号，报出"文档里有、代码里没有"
    python3 scripts/claim_verify.py --scan-doc references/游戏引擎复刻.md

    # ② 核实一份声明清单
    python3 scripts/claim_verify.py --verify ledger/claims.txt

    # ③ 自测（正反两组，证明守卫真有效）
    python3 scripts/claim_verify.py --self-test

## 声明清单格式

每行一条，`类型: 值`，`#` 后为注释，空行忽略：

    gate:G379                       # 门禁编号必须在 GATES 或 MANUAL_GATES 中
    cmd:gate_chaos.py --assert-full # 该脚本必须真的有这个 flag
    file:scripts/gate_chaos.py      # 文件必须存在
    grep:scripts/gate_chaos.py::cmd_assert_full   # 文件必须含该字符串
    cachekey:audit/.chaos_last.json::full         # JSON 必须含该顶层键
"""
import argparse
import ast
import importlib.util
import json
import os
import re
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 🔑 第七十八轮：**默认起始轮** —— 自该轮起**逐轮**要求声明清单。
#    🔴 此前只能每次手传 `--require-since 75`；现在默认值写在这里，
#       需要收紧/放宽时**只改这一行**，不必翻调用处。
#    🔑 设为 None 表示"只守最新一轮"（逐轮要求需显式开启）。
DEFAULT_REQUIRE_SINCE = 75

# 🔑 第七十九轮：`--all` 三段的**稳定标记行**。
#    🔴 G385 此前与 G382~G384 **跑同一条命令**，三者不再独立：
#       若 `--all` 内部漏跑某项，三条仍会显示同一 rc，G385 也发现不了。
#    🔑 解法：给每段打一个标记，`--audit-all` 作为**独立进程**校验
#       输出里**三段标记是否齐全** —— 与 rc 解耦。
ALL_MARKERS = ['[ALL:G382]', '[ALL:G383]', '[ALL:G384]']

# 🔴 **关键教训（第七十九轮实测）**：上面这串自打印标记**无效**。
#    两轮故意破坏实测都仍然通过 —— 因为标记行在 cmd_all 里必然执行，
#    **与段体是否真跑无关**（段首/段尾都一样）。测了个寂寞。
# ✅ 真正能证明"这一段跑了"的是**段体自己打印的内容特征**：
#    段体漏跑 → 这些串不会出现。
# 🔑 第八十四轮：**能力自报**（capability self-declaration）。
#    🔴 第八十三轮诚实结论：`guards` 只是**字符串子串匹配**，
#        若某门禁命令恰好包含 `audit-all` 却干别的事，检查仍会放行。
#    🔑 解法：由**守卫脚本自己声明**它提供哪些能力（此处登记），
#        再由 G387 拿"自报的值"与 `DUP_CMDS_GUARDIAN` 的登记做**相等比较**。
#    🔑 这样一个"恰好含关键词"的命令不会被误认——
#        因为它必须**同时**自报对应 capability。
DECLARED_CAPABILITIES = (
    'audit-all',          # `--audit-all`：校验 `--all` 三段是否都执行
)

# 🔑 第八十五轮：**每个自报的能力都必须可探测**。
#    🔴 第八十四轮诚实结论：脚本可以**自报一个它其实没实现的能力**，
#       G387 发现不了 —— 双向声明解决"认错人"，不解决"自报撒谎"。
#    🔑 解法：声明的能力必须**在此登记对应的实现入口**；
#       `--probe-capability NAME` 会**真的跑一次**并返回 rc。
#    🔴 声明了却未登记实现 → 直接阻断（"说了没有做"）。
CAPABILITY_PROBE = {
    'audit-all': 'cmd_audit_all',
}

# 🔑 第八十六轮：**外部可观测副作用**。
#    🔴 第八十五轮诚实结论：`PROBE_OK` 是**脚本自己打印的** ——
#       若把实现改成 `print('PROBE_OK'); return 0`，抽查**会放行**。
#    🔑 解法：每个能力必须登记它**应当产生的外部可观测结果行**
#       （此处是 `--audit-all` 的三段结论标记 G382/G383/G384）。
#    🔑 探测时**捕获实现的真实输出**并逐条断言 ——
#       🔴 「打印 PROBE_OK 就走人」无法蒙混，因为三段标记不会出现。
CAPABILITY_EFFECT = {
    'audit-all': ('G382', 'G383', 'G384'),   # ← `--audit-all` 的三段结论
}

# 🔑 第八十七轮：**文件系统产物**（真正的外部副作用）。
#    🔴 第八十六轮诚实结论：副作用仍是**脚本打印的字符串** ——
#       若实现改成 `print('G382 G383 G384')` 再 `return 0`，**仍能蒙混**。
#    🔑 解法：能力必须**真的写出一个产物文件**；
#       探测时读产物里的 `generated_at_ns`，跑完后断言它**确实变大**。
#    🔑 「打印几行字」无论如何都改变不了产物里的纳秒戳。
CAPABILITY_ARTIFACT = {
    # 相对 ROOT 的路径
    'audit-all': os.path.join('ledger', '_audit_all_last.json'),
}

# 🔑 第八十八轮：**产物内容**必须反映真实结果。
#    🔴 第八十七轮诚实结论：判据只是"纳秒戳变大" ——
#       若实现改成 `json.dump({'generated_at_ns': time.time_ns()})`，
#       **只写个时间戳而不干正事**，仍能蒙混。
#    🔑 解法：登记产物里**必须出现的键**（此处是三段的真实 rc），
#       探测时逐条断言：键齐全 · 值为 int · 与本次真实 rc 一致。
CAPABILITY_ARTIFACT_KEYS = {
    'audit-all': ('G382 文档编号', 'G383 持续兑现', 'G384 已写清单'),
}

# 🔑 第九十二轮：锚点推广到 `audit-all`。
#    🔴 第九十一轮诚实结论③：锚点只用于 `chaos-full`，`audit-all` 未采用。
#    🔑 但两者的值域**完全不同**，不能照搬量级下界：
#         · chaos-full 的值是**计数**（101 / 99），适合"量级下界"
#         · audit-all  的值是 **rc**（0 或 1），下界无意义
#    🔑 所以引入两类锚点：
#         · 'floor'  —— 值 ≥ 分母 × 比率（量级）
#         · 'domain' —— 值必须落在**外部规定的合法域**（值域）
#    🔴 两种都**不依赖上一次产物**，这才是"锚点"的意义。
# 🔑 第九十三轮：**合并重复判据**。
#    🔴 第九十二轮诚实结论④：这里的 {0,1} 与第八十九轮
#       "子进程 rc 合法域"是**同一判据的两处实现** ——
#       将来改一处忘另一处，就会出现"一边放行一边拦截"。
#    🔑 统一为单一常量，两处**同时引用它**。
GATE_RC_DOMAIN = (0, 1)

CAPABILITY_ANCHOR_SPEC = {
    'audit-all': {'type': 'domain', 'allowed': GATE_RC_DOMAIN},
}

ALL_CONTENT = [
    ('G382', '提到的 G 编号'),        # cmd_scan_doc 独有
    ('G383', '清单 '),                # cmd_verify_all 独有："清单 N 份"
    ('G384', 'ledger 清单'),          # cmd_check_current 独有
]


# 🔑 第八十轮：`ALL_CONTENT` 与三段体函数的**映射**（自校验用）。
#    🔴 第七十九轮诚实结论：三个特征串是**人工挑的**，若某段改了措辞
#       或该串并非该段独有，G385 会**误报/漏报**。
#    🔑 本映射让"特征串 ↔ 段体函数"成为**可校验的事实**，而不是注释里的声称。
ALL_CONTENT_FN = {
    'G382': 'cmd_scan_doc',
    'G383': 'cmd_verify_all',
    'G384': 'cmd_check_current',
}


def _fn_code_lines(src_lines, tree, name):
    """🔑 返回某函数体范围内的**代码行**（排除 # 注释 + 其 docstring）。"""
    out = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                and node.name == name:
            lo, hi = node.lineno, (node.end_lineno or node.lineno)
            doc = set()
            for b in ast.walk(node):
                if b is not node and isinstance(b, ast.Expr) \
                        and isinstance(b.value, ast.Constant) \
                        and isinstance(b.value.value, str):
                    for i in range(b.lineno, (b.end_lineno or b.lineno) + 1):
                        doc.add(i)
            for i in range(lo, hi + 1):
                ln = src_lines[i - 1]
                if ln.strip().startswith('#') or i in doc:
                    continue
                out.append(ln)
    return out


def cmd_declare_capability(a):
    """🔑 **`--declare-capability`**：本脚本**自报**提供的能力。

    🔴 用途：让 G387 从**子串匹配**升级为**双向声明**——
       ① 脚本自报它有哪些 capability（此处打印）
       ② G387 比对"自报值"与 `DUP_CMDS_GUARDIAN` 的登记是否**相等**
    🔑 判据是**相等**而非"包含"，所以"命令恰好含关键词但没自报"
       的门禁**无法通过**。
    """
    print('=' * 70)
    print('🔑 **能力自报** —— ' + os.path.basename(__file__))
    print('=' * 70)
    if not DECLARED_CAPABILITIES:
        print('\n🔴 本脚本**未声明任何能力**')
        print('\n' + '=' * 70 + '\n🔴 守卫失效\n' + '=' * 70)
        return 1
    for c in DECLARED_CAPABILITIES:
        print(f'  CAPABILITY {c}')
    print('\n' + '=' * 70)
    print(f'✅ 自报 {len(DECLARED_CAPABILITIES)} 项能力')
    print('=' * 70)
    return 0


def cmd_probe_capability(a):
    """🔑 **`--probe-capability NAME`**：**真的跑一次**某个自报的能力。

    🔴 用途：防「自报撒谎」——声明了能力却没实现 / 实现了却跑不通。
    🔑 判据：① 该能力**已声明** ② 已登记**实现入口** ③ **真跑**且 rc=0
       ④ 输出含 `PROBE_OK`（防止"跑了个空函数也 rc=0"）
    """
    print('=' * 70)
    print('🔑 **能力探测** —— ' + os.path.basename(__file__))
    print('=' * 70)
    name = (a.probe_capability or '').strip()
    if not name:
        print('\n🔴 未指定能力名（`--probe-capability NAME`）')
        print('\n' + '=' * 70 + '\n🔴 守卫失效\n' + '=' * 70)
        return 1
    print(f'\n探测能力: `{name}`')
    if name not in DECLARED_CAPABILITIES:
        print(f'\n🔴 该能力**未被本脚本声明**（已声明: {DECLARED_CAPABILITIES}）')
        print('\n' + '=' * 70 + '\n🔴 守卫失效\n' + '=' * 70)
        return 1
    fn_name = CAPABILITY_PROBE.get(name)
    if not fn_name:
        print(f'\n🔴 声明了 `{name}` 却**未登记实现入口** —— '
              f'这是"自报撒谎"，必须登记到 `CAPABILITY_PROBE`')
        print('\n' + '=' * 70 + '\n🔴 守卫失效\n' + '=' * 70)
        return 1
    fn = globals().get(fn_name)
    if fn is None:
        print(f'\n🔴 实现入口 `{fn_name}` 在本文件中不存在')
        print('\n' + '=' * 70 + '\n🔴 守卫失效\n' + '=' * 70)
        return 1
    print(f'实现入口: `{fn_name}` —— **真的跑一次**')
    # 🔑 第八十七轮：**运行前**先取产物快照。
    #    🔴 实测坑：若在运行**之后**才读，读到的是刚写的新值，
    #       `after <= before` 永远不成立 → 探针**静默失效**。
    #    🔑 与第六十三轮"基线必须 rc=0"同源：**先有可比对的基线**。
    art0 = CAPABILITY_ARTIFACT.get(name)
    before_ns = 0
    if art0:
        ap0 = os.path.join(ROOT, art0)
        if os.path.isfile(ap0):
            try:
                before_ns = json.load(open(ap0, encoding='utf-8')).get(
                    'generated_at_ns', 0)
            except Exception:
                before_ns = 0
        print(f'\n🔑 运行前产物快照: `{art0}` ns={before_ns}')
    # 🔑 第八十六轮：**捕获**实现的真实输出（不是只看 rc）
    import io
    import contextlib
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            rc = fn(a)
    except Exception as e:
        rc = -1
        buf.write(f'EXC {type(e).__name__}: {e}\n')
    produced = buf.getvalue()
    if rc != 0:
        print(f'\n🔴 探测**失败**（rc={rc}）—— 该能力自报了但跑不通')
        print('\n' + '=' * 70 + '\n🔴 守卫失效\n' + '=' * 70)
        return 1
    # 🔑 断言**外部可观测副作用**：登记的结果行必须真的出现
    effects = CAPABILITY_EFFECT.get(name)
    if not effects:
        print(f'\n🔴 能力 `{name}` **未登记外部可观测副作用** —— '
              f'无法区分"真做了"与"打印 PROBE_OK 就走人"')
        print('\n' + '=' * 70 + '\n🔴 守卫失效\n' + '=' * 70)
        return 1
    print(f'\n🔑 外部可观测副作用（须全部出现在真实输出中）: '
          f'{list(effects)}')
    missing = [e for e in effects if e not in produced]
    if missing:
        print(f'\n🔴 真实输出**缺少** {missing} —— '
              f'该能力可能只是"打印了个标记就走人"')
        print('\n' + '=' * 70 + '\n🔴 守卫失效\n' + '=' * 70)
        return 1
    for e in effects:
        print(f'  ✅ {e} 已出现在真实输出中')

    # 🔑 第八十七轮：**文件系统产物**快照比对（真正的外部副作用）
    art = CAPABILITY_ARTIFACT.get(name)
    if not art:
        print(f'\n🔴 能力 `{name}` **未登记文件系统产物** —— '
              f'仅凭打印内容无法证明"真做了"')
        print('\n' + '=' * 70 + '\n🔴 守卫失效\n' + '=' * 70)
        return 1
    ap2 = os.path.join(ROOT, art)
    print(f'\n🔑 文件系统产物: `{art}` （运行前 ns={before_ns}）')
    try:
        cur = json.load(open(ap2, encoding='utf-8'))
    except Exception as e:
        print(f'\n🔴 产物**未生成或不可读**：{type(e).__name__}: {e}')
        print('\n' + '=' * 70 + '\n🔴 守卫失效\n' + '=' * 70)
        return 1
    after_ns = cur.get('generated_at_ns', 0)
    if after_ns <= before_ns:
        print(f'\n🔴 产物**未被重写**（ns {before_ns} → {after_ns}）—— '
              f'该能力可能只是"打印几行字"')
        print('\n' + '=' * 70 + '\n🔴 守卫失效\n' + '=' * 70)
        return 1
    print(f'  ✅ 产物已重写（ns {before_ns} → {after_ns}）')

    # 🔑 第八十八轮：**产物内容**必须反映真实结果
    keys = CAPABILITY_ARTIFACT_KEYS.get(name)
    if not keys:
        print('\n🔴 能力 `{n}` **未登记产物内容键** —— '
              '只写个时间戳也能通过'.replace('`{n}`', f'`{name}`'))
        print('\n' + '=' * 70 + '\n🔴 守卫失效\n' + '=' * 70)
        return 1
    print(f'\n🔑 产物内容键（须齐全、为 int、且与真实 rc 一致）: {list(keys)}')
    # 🔑 第八十九轮：**跨进程**取真值。
    #    🔴 第八十八轮诚实结论：真值是**同一进程内的函数调用** ——
    #       若三段函数本身被改坏，真值与产物会**一起错**，比对仍一致（自证循环）。
    #    🔑 解法：另起**三个独立子进程**跑各自的 CLI 入口取 rc，
    #       与产物里的值比对。
    #    🔑 为什么这能打破自证循环：子进程跑的是**同一份代码**，
    #       但它通过**独立 CLI 路径**进入 —— 若有人篡改 `cmd_all` 的
    #       写入逻辑，子进程路径不受影响，真值仍然真实。
    print('\n🔑 跨进程取真值（三个独立子进程）')
    self_path = os.path.join(ROOT, 'scripts', 'claim_verify.py')
    doc0 = os.path.join(ROOT, 'references', '游戏引擎复刻.md')
    sub_cmds = {
        'G382 文档编号': [sys.executable, self_path, '--scan-doc', doc0],
        'G383 持续兑现': [sys.executable, self_path, '--verify-all'],
        'G384 已写清单': [sys.executable, self_path, '--check-current'],
    }
    truth = {}
    sub_failed = False
    for k, c in sub_cmds.items():
        try:
            rr = subprocess.run(c, capture_output=True, text=True, timeout=300)
        except Exception as e:
            print(f'  🔴 子进程失败 `{k}`: {type(e).__name__}: {e}')
            sub_failed = True
            continue
        # 🔴 实测发现的真 bug：子进程**参数写错**时 argparse 返回 rc=2，
        #    而原实现把 rc=2 当成"真值"收下 —— 于是比对的是**假真值**。
        #    🔑 门禁 rc 的合法域只有 {0, 1}（通过 / 阻断）；
        #       其它值一律视为"没取得真值"，拒绝给出结论。
        if rr.returncode not in GATE_RC_DOMAIN:
            print(f'  🔴 子进程 `{k}` rc={rr.returncode} **不在合法域 '
                  f'{GATE_RC_DOMAIN}** —— 可能参数写错，不得当作真值')
            print(f'     stderr 尾部: {(rr.stderr or "").strip()[-120:]}')
            sub_failed = True
            continue
        if not (rr.stdout or '').strip():
            print(f'  🔴 子进程 `{k}` **无任何输出** —— 无法确认真跑过')
            sub_failed = True
            continue
        truth[k] = rr.returncode
    if sub_failed or len(truth) != len(sub_cmds):
        print('\n🔴 **无法取得独立真值** —— 拒绝给出"产物正确"结论')
        print('\n' + '=' * 70 + '\n🔴 守卫失效\n' + '=' * 70)
        return 1
    for k, v in truth.items():
        print(f'  ✅ 子进程真值 {k} = {v}')
    # 🔑 产物把三段 rc 放在 `results` 子对象下（不是顶层）——
    #    🔴 直接 `k not in cur` 会永远失败（实测踩到）。
    #    🔑 顶层若没有就下钻一层 `results`。
    body = cur.get('results') if isinstance(cur.get('results'), dict) else cur

    # 🔑 第九十二轮：**外部锚点**（不依赖上一次产物）
    spec = CAPABILITY_ANCHOR_SPEC.get(name)
    if not spec:
        print('\n🔴 能力 `%s` **未登记锚点** —— 下界/值域断言无从谈起'
              % name)
        print('\n' + '=' * 70 + '\n🔴 守卫失效\n' + '=' * 70)
        return 1
    _ty = spec.get('type')
    if _ty == 'domain':
        allowed = spec.get('allowed')
        if not allowed:
            print('\n🔴 值域锚点**未登记合法域** —— 断言无效')
            print('\n' + '=' * 70 + '\n🔴 守卫失效\n' + '=' * 70)
            return 1
        print(f'\n🔑 外部锚点（值域）: 每个键的值必须 ∈ {allowed}')
        for k in keys:
            if k in body and body[k] not in allowed:
                print(f'\n🔴 产物键 `{k}` = {body[k]!r} **不在合法域** '
                      f'{allowed} —— 门禁 rc 不可能是这个值')
                print('\n' + '=' * 70 + '\n🔴 守卫失效\n' + '=' * 70)
                return 1
        print('  ✅ 值域锚点成立')
    elif _ty == 'floor':
        print('\n🔑 外部锚点（量级）：本能力不适用，回退到"与真值一致"')
    else:
        print(f'\n🔴 未知锚点类型 `{_ty}`')
        print('\n' + '=' * 70 + '\n🔴 守卫失效\n' + '=' * 70)
        return 1

    for k in keys:
        if k not in body:
            print(f'\n🔴 产物**缺少键** `{k}` —— 只写了部分内容')
            print('\n' + '=' * 70 + '\n🔴 守卫失效\n' + '=' * 70)
            return 1
        v = body[k]
        if not isinstance(v, int):
            print(f'\n🔴 产物键 `{k}` 的值 {v!r} **不是 int** —— '
                  f'无法与真实 rc 比对')
            print('\n' + '=' * 70 + '\n🔴 守卫失效\n' + '=' * 70)
            return 1
        if v != truth.get(k):
            print(f'\n🔴 产物键 `{k}` = {v} 与**真实 rc** = {truth.get(k)} '
                  f'**不一致** —— 产物在说谎')
            print('\n' + '=' * 70 + '\n🔴 守卫失效\n' + '=' * 70)
            return 1
        print(f'  ✅ {k} = {v} 与真实 rc 一致')
    print('\nPROBE_OK')
    print('=' * 70)
    print(f'✅ 能力 `{name}` **探测通过**（真跑 rc=0）')
    print('=' * 70)
    return 0


def cmd_check_content(a):
    """G386 · 🔑 **`ALL_CONTENT` 自校验**：特征串必须是**段体独有能力**。

    🔴 第七十九轮留下的脆弱性：三个特征串人工挑选，若
       ① 某段**改了措辞** → 特征消失 → G385 **误报缺段**
       ② 该串**并非该段独有** → 别段也会打印 → 漏跑时 G385 **漏报**
    🔑 本门禁把这两条变成可测断言：
       - **存在性**：该串必须出现在**目标段体**的代码行里
       - **唯一性**：该串**不得**出现在另外两段体的代码行里
    """
    sp = os.path.join(ROOT, 'scripts', 'claim_verify.py')
    text = open(sp, encoding='utf-8').read()
    src_lines = text.splitlines()
    tree = ast.parse(text)
    print('=' * 70)
    print('G386 · 🔑 `ALL_CONTENT` **自校验**（特征串须为段体独有）')
    print('=' * 70)
    bodies = {g: _fn_code_lines(src_lines, tree, fn)
              for g, fn in ALL_CONTENT_FN.items()}
    for g, ls in bodies.items():
        if not ls:
            print(f'\n🔴 未找到段体函数 `{ALL_CONTENT_FN[g]}` 的代码行')
            print('\n' + '=' * 70 + '\n🔴 守卫失效\n' + '=' * 70)
            return 1
    bad = 0
    for gate, needle in ALL_CONTENT:
        own = bodies[gate]
        others = {g: ls for g, ls in bodies.items() if g != gate}
        has = any(needle in ln for ln in own)
        cross = [g for g, ls in others.items() if any(needle in ln for ln in ls)]
        print(f'\n[{gate}] `{needle}`  → `{ALL_CONTENT_FN[gate]}`')
        if not has:
            print('   🔴 **存在性失败**：目标段体里没有这串 —— '
                  '措辞漂移会让 G385 **误报缺段**')
            bad += 1
        else:
            print('   ✅ 存在性：目标段体确实会打印它')
        if cross:
            print(f'   🔴 **唯一性失败**：`{cross}` 的段体也会打印它 —— '
                  f'漏跑 {gate} 时 G385 仍会看到这串 → **漏报**')
            bad += 1
        else:
            print('   ✅ 唯一性：其它两段不会打印它')
    print('\n' + '=' * 70)
    if bad:
        print(f'🔴 {bad} 项自校验失败 —— `ALL_CONTENT` 不可信，'
              f'G385 的判定因此无效')
        print('\n🔴 守卫失效')
        print('=' * 70)
        return 1
    print('✅ 守卫成立：三段特征串均为**段体独有**且**存在**')
    print('=' * 70)
    return 0


def _load_gates():
    """🔑 从 run_all_gates.py 真实加载门禁编号（不 import，避免顶层副作用）。"""
    p = os.path.join(ROOT, 'scripts', 'run_all_gates.py')
    spec = importlib.util.spec_from_file_location('_rg', p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    auto = set(g for g, *_ in m.GATES)
    manual = set(g for g, *_ in m.MANUAL_GATES)
    return auto, manual


def _code_lines(rel):
    """🔑 返回 (代码行列表, 说明行数, 原文行数)。

    🔴 第七十五轮发现：**说明文字 ≠ 代码**。
       `absent` 曾误报两处 —— 注释行与 **docstring** 里的 `--limit 20`。
    🔑 判据应是「**代码里有没有**」：排除 `#` 注释行 + AST 求出的
       docstring 行，并**透明报出**跳过数（不静默）。
    """
    p = os.path.join(ROOT, rel)
    text = open(p, encoding='utf-8').read()
    lines = text.splitlines()
    doc = set()
    if rel.endswith('.py'):
        try:
            for node in ast.walk(ast.parse(text)):
                if isinstance(node, ast.Expr) and \
                        isinstance(node.value, ast.Constant) and \
                        isinstance(node.value.value, str):
                    for i in range(node.lineno,
                                   (node.end_lineno or node.lineno) + 1):
                        doc.add(i)
        except Exception:
            pass                      # 🔴 解析不了就只靠 # 过滤（不静默失败）
    code = [ln for i, ln in enumerate(lines, 1)
            if not ln.strip().startswith('#') and i not in doc]
    return code, len(lines) - len(code), len(lines)


def _check_one(kind, val):
    """返回 (ok, 说明)。🔴 未知类型一律判失败，不得静默放行。"""
    try:
        if kind == 'gate':
            auto, manual = _load_gates()
            if val in auto:
                return True, '自动门禁（真有命令）'
            if val in manual:
                return True, '人工门禁（签字项）'
            return False, '🔴 GATES 与 MANUAL_GATES 中**均无**此编号'
        if kind == 'cmd':
            # "脚本 --flag"
            parts = val.split()
            if len(parts) < 2:
                return False, '格式应为 `脚本 --flag`'
            sp = os.path.join(ROOT, 'scripts', parts[0])
            if not os.path.isfile(sp):
                return False, f'脚本不存在: {parts[0]}'
            src = open(sp, encoding='utf-8').read()
            flag = parts[1]
            if "add_argument('%s'" % flag in src or \
               'add_argument("%s"' % flag in src:
                return True, f'`{flag}` 已在 argparse 中登记'
            return False, f'🔴 `{flag}` **未在 argparse 中登记**'
        if kind == 'file':
            fp = os.path.join(ROOT, val)
            return (os.path.isfile(fp),
                    '存在' if os.path.isfile(fp) else '🔴 文件不存在')
        if kind == 'grep':
            fp2, needle = val.split('::', 1)
            if not os.path.isfile(os.path.join(ROOT, fp2)):
                return False, f'文件不存在: {fp2}'
            code, skipped, total = _code_lines(fp2)
            hit = sum(1 for ln in code if needle in ln)
            sk = f'（跳过 {skipped}/{total} 说明行）' if skipped else ''
            if hit:
                return True, f'代码行命中 {hit} 处 {sk}'
            all_hit = needle in open(os.path.join(ROOT, fp2),
                                     encoding='utf-8').read()
            if all_hit:
                # 🔴 只在说明文字里出现 —— 声明的是"代码里有"，故不成立
                return False, (f'🔴 **仅在说明行命中** {sk} —— '
                               f'说明文字 ≠ 代码')
            return False, f'🔴 未找到 `{needle}` {sk}'
        if kind == 'absent':
            # 🔑 第七十六轮新增：**必须不出现**（防回退）
            fp4, needle4 = val.split('::', 1)
            if not os.path.isfile(os.path.join(ROOT, fp4)):
                return False, (f'文件不存在: {fp4}'
                               f'（无法断言"不出现"）')
            code, skipped, total = _code_lines(fp4)
            sk = f'（跳过 {skipped}/{total} 说明行）' if skipped else ''
            hits = [ln.strip() for ln in code if needle4 in ln]
            if hits:
                return False, (f'🔴 **代码里不应出现却出现了** {sk}\n'
                               f'     ↳ {hits[0][:76]}')
            return True, f'代码里未出现 ✅ {sk}'
        if kind == 'cachekey':
            fp3, key = val.split('::', 1)
            p = os.path.join(ROOT, fp3)
            j = json.load(open(p, encoding='utf-8'))
            return (key in j, '键存在' if key in j else f'🔴 缓存无 `{key}` 键')
        return False, f'🔴 未知声明类型 `{kind}`'
    except Exception as e:
        # 🔴 **绝不静默**：解析异常也是"未核实"
        return False, f'🔴 核实过程异常: {type(e).__name__}: {e}'


def _verify_file(p, quiet=False):
    """核实一份清单，返回 (bad, total)。🔑 供 --verify / --verify-all 复用。"""
    if not os.path.isfile(p):
        print(f'🚫 声明清单不存在: {p}')
        return 1, 1
    if not quiet:
        print(f'\n清单: {p}\n')
    bad = 0
    total = 0
    for ln, line in enumerate(open(p, encoding='utf-8'), 1):
        line = line.split('#')[0].strip()
        if not line:
            continue
        if ':' not in line:
            print(f'🚫 第 {ln} 行无法解析（缺冒号）: {line}')
            bad += 1
            total += 1
            continue
        kind, val = line.split(':', 1)
        kind, val = kind.strip(), val.strip()
        total += 1
        ok, why = _check_one(kind, val)
        print(f"{'✅' if ok else '🚫'} [{kind}] {val}\n     {why}")
        if not ok:
            bad += 1
    return bad, total




def _load_rc_domain_allowlist():
    """🔑 从 `ledger/rc_domain_allowlist.txt` 读语义豁免。

    🔴 第九十五轮：**文件不存在或为空**不得静默通过 ——
       那会让"检查器找不到豁免文件"表现成"没有豁免"，
       进而把**应当豁免的**判成违规（误报）。
    🔑 与"空台账不得当通过"是同一个判据。
    """
    ap_ = os.path.join(ROOT, 'ledger', 'rc_domain_allowlist.txt')
    out = {}
    if not os.path.exists(ap_):
        print(f'\n🔴 豁免文件不存在: {ap_}')
        print('  🔑 若无豁免需建**带说明的空清单**（仅注释行）；'
              '缺文件会被当成"读不到"而非"没有"')
        return None
    for ln in open(ap_, encoding='utf-8'):
        ln = ln.strip()
        if not ln or ln.startswith('#'):
            continue
        if ':' not in ln:
            print(f'\n🔴 豁免行缺冒号: {ln!r}')
            return None
        k, r = ln.split(':', 1)
        out[k.strip()] = r.strip()
    return out



# 🔑 第九十六轮：**豁免清单本身必须被守**。
#    🔴 第九十五轮诚实结论②：`ledger/rc_domain_allowlist.txt` 与
#       `ledger/scan_doc_allowlist.txt` 的增删**不触发任何检查** ——
#       人可以悄悄加一条豁免，而没有任何门禁会问一句"为什么"。
#    🔑 三条判据：批准轮次 / 僵尸豁免 / 理由充分。
ALLOWLIST_FILES = {
    'rc_domain_allowlist.txt': 'file',   # 键 = 文件名 → 须存在于 scripts/
    'scan_doc_allowlist.txt': 'gate',    # 键 = 门禁号 → 须在文档里出现
}


def cmd_check_allowlist():
    """🔑 G389：豁免清单须**带批准轮次**，且不得有"僵尸豁免"。

    🔑 三条判据：
      ① **批准轮次** —— 理由必须以 `NN轮` 开头，让"何时批准"可查；
         且轮次不得大于文档最大轮次（🔴 不能写未来的轮次）。
      ② **僵尸豁免** —— 豁免的键在代码/文档里**根本不存在**，
         说明它掩盖了一个已经消失的问题，应删除而不是继续挂着。
      ③ **理由充分** —— ≥ 10 字符（沿用既有判据）。
    """
    import re as _re
    print('=' * 70)
    print('🔑 **豁免清单审计** —— 批准轮次 / 僵尸豁免 / 理由')
    print('=' * 70)
    # 🔑 文档最大轮次（不得写未来的轮次）
    max_round = 0
    for dn in ('references', '.'):
        dp = os.path.join(ROOT, dn)
        if not os.path.isdir(dp):
            continue
        for fn_ in os.listdir(dp):
            if not fn_.endswith('.md'):
                continue
            try:
                for ln in open(os.path.join(dp, fn_), encoding='utf-8'):
                    # 🔑 第九十六轮修：中文数字字符类**必须含 十/百** ——
                    #    🔴 否则 `第九十五轮` 匹配不到（"九"后是"十"），
                    #       最大轮次被误算成 9。
                    m = _re.match(r'^#{1,4}\s*第([0-9]+|[零一二三四五六七八九十百千]+)轮',
                                  ln.strip())
                    if m:
                        v = (_cn2num(m.group(1)) if not m.group(1).isdigit()
                             else int(m.group(1)))
                        max_round = max(max_round, v)
            except Exception:
                pass
    print(f'\n🔑 文档最大轮次 = {max_round}（豁免批准轮次不得大于它）')

    # 收集文档里出现的门禁号（用于僵尸检测）
    all_doc = ''
    for dn in ('references', 'audit', 'flow', 'guide', 'method', 'assets',
               '_inactive', '.'):
        dp = os.path.join(ROOT, dn)
        if not os.path.isdir(dp):
            continue
        for fn_ in os.listdir(dp):
            if fn_.endswith('.md'):
                try:
                    all_doc += open(os.path.join(dp, fn_),
                                    encoding='utf-8').read()
                except Exception:
                    pass

    bad = 0
    for fname, kind in ALLOWLIST_FILES.items():
        ap_ = os.path.join(ROOT, 'ledger', fname)
        print(f'\n### {fname}（键类型: {kind}）')
        if not os.path.exists(ap_):
            print(f'  🔴 文件不存在')
            bad += 1
            continue
        n = 0
        for ln in open(ap_, encoding='utf-8'):
            ln = ln.strip()
            if not ln or ln.startswith('#'):
                continue
            if ':' not in ln:
                print(f'  🔴 缺冒号: {ln!r}')
                bad += 1
                continue
            k, r = ln.split(':', 1)
            k, r = k.strip(), r.strip()
            n += 1
            # ③ 理由充分
            if len(r) < 10:
                print(f'  🔴 `{k}` 理由过短（{len(r)} 字符）')
                bad += 1
            # ① 批准轮次
            m = _re.match(r'^(\d+)轮', r)
            if not m:
                print(f'  🔴 `{k}` 理由未以 `NN轮` 开头 —— '
                      f'**批准轮次不可追溯**')
                bad += 1
            elif int(m.group(1)) > max_round:
                print(f'  🔴 `{k}` 批准轮次 {m.group(1)} '
                      f'**大于文档最大轮次 {max_round}**')
                bad += 1
            else:
                print(f'  ✅ `{k}` 批准于第 {m.group(1)} 轮')
            # ② 僵尸豁免
            if kind == 'file':
                if not os.path.exists(os.path.join(ROOT, 'scripts', k)):
                    print(f'  🔴 `{k}` **僵尸豁免** —— scripts/ 下无此文件')
                    bad += 1
            elif kind == 'gate':
                gid = 'G' + k if not k.startswith('G') else k
                if gid not in all_doc:
                    print(f'  🔴 `{gid}` **僵尸豁免** —— 文档中未出现')
                    bad += 1
        print(f'  共 {n} 条豁免')
    print()
    if bad:
        print('=' * 70)
        print(f'🔴 豁免清单存在 {bad} 处问题 —— 豁免不得静默增删')
        print('=' * 70)
        return 1
    print('=' * 70)
    print('✅ 守卫成立：豁免均带批准轮次，无僵尸豁免')
    print('=' * 70)
    return 0


def cmd_check_rc_domain():
    """🔑 G388：rc 合法域必须是**单一常量**，不得有第二处硬编码。"""
    print('=' * 70)
    print('🔑 **rc 合法域单一常量检查** —— claim_verify.py')
    print('=' * 70)
    sfiles = sorted(
        f for f in os.listdir(os.path.join(ROOT, 'scripts'))
        if f.endswith('.py'))
    print(f'\n🔑 扫描范围: scripts/*.py 共 {len(sfiles)} 个文件')
    return _scan_rc_domain(sfiles)


def _scan_rc_domain(sfiles):
    """🔑 在给定脚本列表里扫 `(0, 1)` 字面量。

    🔑 判据：整个 `scripts/` 里 `(0,1)` 字面量**只允许出现 1 处**
       （＝ `GATE_RC_DOMAIN` 的定义处）。
    🔑 自指处理：**每个文件**都排除其中"本检查器同名函数"的行范围。
    """
    # 🔑 先验常量**值本身** —— 只数出现次数防不住改值。
    if tuple(GATE_RC_DOMAIN) != (0, 1):
        print(f'\n🔴 `GATE_RC_DOMAIN` = {GATE_RC_DOMAIN!r} '
              f'**不是 (0, 1)** —— 常量被改值')
        return 1
    print(f'  ✅ 常量值 = {GATE_RC_DOMAIN}（即 rc 的通过/阻断两态）')

    # 🔑 第九十四轮：**语义豁免**。
    #    🔴 扩展扫描立刻抓到 `ast_query.py:83` 的 `(0, 1)` ——
    #       但它的语义是 **astgrep 的 rc**：`1 = 有命中（lint 语义）**，
    #       **不是**"门禁阻断"。强行合并会引入错误。
    #    🔑 所以豁免必须**逐条登记并写明语义差异**，不能静默放行。
    # 🔑 第九十五轮：改为**外部文件** `ledger/rc_domain_allowlist.txt`。
    #    🔴 第九十四轮诚实结论②：豁免硬编码在检查器里，
    #       新增豁免要**改代码**，而外部文件更可审计（谁改的有 git 记录）。
    RC_DOMAIN_ALLOW = _load_rc_domain_allowlist()
    if RC_DOMAIN_ALLOW is None:
        print('\n🔴 豁免清单不可读 —— 拒绝给结论（不静默当"没有豁免"）')
        return 1
    bad = []
    n_allowed = 0
    n_scanned = 0
    for fn in sfiles:
        fp = os.path.join(ROOT, 'scripts', fn)
        try:
            src = open(fp, encoding='utf-8').read()
            tree = ast.parse(src)
        except Exception as e:
            print(f'\n⚠️ 跳过 {fn}（解析失败: {e}）')
            continue
        n_scanned += 1
        # 🔑 排除本检查器在该文件内的行范围（自指）
        me = [n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef)
              and n.name in ('cmd_check_rc_domain', '_scan_rc_domain')]
        skip = set()
        for m in me:
            skip.update(range(m.lineno, (m.end_lineno or m.lineno) + 1))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Tuple, ast.Set)):
                continue
            if len(node.elts) != 2 or node.lineno in skip:
                continue
            try:
                vals = tuple(ast.literal_eval(e) for e in node.elts)
            except Exception:
                continue
            if vals == tuple(GATE_RC_DOMAIN):
                if fn in RC_DOMAIN_ALLOW:
                    n_allowed += 1
                    print(f'  ⚠️ 豁免 {fn}:{node.lineno} —— '
                          f'{RC_DOMAIN_ALLOW[fn]}')
                    continue
                bad.append((fn, node.lineno, vals))
    print(f'\n🔑 实际扫描 {n_scanned}/{len(sfiles)} 个文件'
          f'（排除检查器自身 {len(sfiles) - n_scanned} 个不可解析）')
    # 🔑 豁免理由**不得为空** —— 否则豁免退化为"随便放行"
    for _f, _r in RC_DOMAIN_ALLOW.items():
        if not _r or len(_r) < 10:
            print(f'\n🔴 豁免 `{_f}` **理由为空或过短** —— 不允许静默放行')
            return 1
    if n_allowed:
        print(f'  ✅ {n_allowed} 处豁免**均已登记语义差异理由**')
    if len(bad) != 1:
        print(f'\n🔴 rc 合法域字面量出现 **{len(bad)} 处**（应为 1 处）:')
        for fn, ln, v in bad:
            print(f'  - {fn}:{ln}: {v}')
        print('\n🔑 应统一引用常量 `GATE_RC_DOMAIN`，不得各自硬编码')
        return 1
    print(f'\n✅ rc 合法域字面量仅 1 处'
          f'（{bad[0][0]}:{bad[0][1]}）= 常量定义处')
    # 🔑 引用次数：定义 1 + 子进程校验 1 + 值域锚点 1 → ≥ 3
    allsrc = ''.join(
        open(os.path.join(ROOT, 'scripts', f), encoding='utf-8').read()
        for f in sfiles if f.endswith('.py'))
    n_ref = allsrc.count('GATE_RC_DOMAIN')
    if n_ref < 3:
        print(f'\n🔴 `GATE_RC_DOMAIN` 仅被引用 {n_ref} 次'
              f'（定义 1 + 子进程校验 1 + 值域锚点 1，应 ≥ 3）')
        return 1
    print(f'  ✅ 常量被引用 {n_ref} 处（定义 + 两处判据）')
    print('=' * 70)
    print('✅ 守卫成立：rc 合法域未分裂')
    print('=' * 70)
    return 0



def cmd_verify(a):
    p = a.verify
    print('=' * 70)
    print('🔑 声明核实 —— **回读代码逐条核对**')
    print('=' * 70)
    bad, total = _verify_file(p)
    print('\n' + '=' * 70)
    if bad:
        print(f'🔴 {bad}/{total} 条声明**未兑现** —— '
              f'不得在回复中声称已完成')
    else:
        print(f'✅ {total}/{total} 条声明已核实兑现')
    print('=' * 70)
    return 1 if bad else 0


_CN = {'零': 0, '一': 1, '二': 2, '三': 3, '四': 4, '五': 5,
       '六': 6, '七': 7, '八': 8, '九': 9}


def _cn2num(t):
    """中文数字 → int。支持 `七`/`十七`/`七十七`/`一百零三` 等常见形式。

    🔴 解析不了返回 None（**不猜**），由调用方显式报出。
    """
    if not t:
        return None
    if t.isdigit():
        return int(t)
    total, sec, cur = 0, 0, None
    i = 0
    while i < len(t):
        ch = t[i]
        if ch in _CN:
            cur = _CN[ch]
        elif ch == '十':
            sec += (cur if cur is not None else 1) * 10
            cur = None
        elif ch == '百':
            sec += (cur if cur is not None else 1) * 100
            cur = None
        else:
            return None                      # 🔴 未知字符：不猜
        i += 1
    return total + sec + (cur or 0)


def _rounds_in_docs(docs):
    """🔑 从文档**标题行**提取轮次（正文引用不算，避免把"下一轮计划"当已完成）。"""
    pat = re.compile(r'^#{1,4}\s*第([零一二三四五六七八九十百]+)轮', re.M)
    out = {}
    for d in docs:
        try:
            txt = open(d, encoding='utf-8').read()
        except Exception:
            continue
        for m in pat.finditer(txt):
            n = _cn2num(m.group(1))
            if n is None:
                continue                      # 🔴 解析不了就跳过，不猜
            out.setdefault(n, set()).add(os.path.basename(d))
    return out


def cmd_check_current(a):
    """G384 · 🔑 **最新一轮必须写了声明清单**。

    🔴 第七十六轮诚实结论：
       `--verify-all` 只核 `ledger/claims_*.txt`，
       🔑 **若某轮忘了写清单，它一样拦不住**。
    本门禁把"**有没有写**"也纳入守卫：
        文档标题里的**最大轮次** ≤ ledger 里**最大清单编号**
    """
    import glob
    print('=' * 70)
    print('G384 · 🔑 **每轮声明清单覆盖** —— 最新一轮不得漏写')
    print('=' * 70)
    docs = a.docs or sorted(glob.glob(os.path.join(
        ROOT, 'references', '*.md')) + glob.glob(os.path.join(ROOT, '*.md')))
    rounds = _rounds_in_docs(docs)
    if not rounds:
        print('\n🔴 未能从文档标题中解析出任何轮次 —— '
              '**不得静默通过**（与"空表即通过"同源）')
        print('\n' + '=' * 70 + '\n🔴 守卫失效\n' + '=' * 70)
        return 1
    mx = max(rounds)
    print(f'\n文档扫描: {len(docs)} 个 · 解析到轮次 {len(rounds)} 个 '
          f'（最大 = 第 {mx} 轮，来自 {sorted(rounds[mx])[:2]}）')

    files = sorted(glob.glob(os.path.join(ROOT, 'ledger', 'claims_*.txt')))
    have = set()
    for f in files:
        m = re.search(r'claims_(\d+)\.txt$', f)
        if m:
            have.add(int(m.group(1)))
    print(f'ledger 清单: {len(files)} 份 → 轮次 {sorted(have)}')

    since = a.require_since
    if since is not None:
        miss = [n for n in range(since, mx + 1) if n not in have]
        print(f'\n🔑 自第 {since} 轮起**逐轮**要求清单：'
              f'缺 {len(miss)} 轮' + (f' → {miss}' if miss else ''))
        bad = bool(miss)
        # 🔑 即便逐轮都齐，"最新一轮"仍须单独确认（since 可能设得比 mx 大）
        if mx not in have:
            bad = True
    else:
        bad = mx not in have
        miss = []

    print('\n' + '=' * 70)
    if bad:
        if not miss:
            print(f'🔴 **第 {mx} 轮没有声明清单** '
                  f'（ledger 最大仅 {max(have) if have else "无"}）')
        print('   🔑 元规则：每轮的声明必须写进 '
              '`ledger/claims_<轮次>.txt`，否则 `--verify-all` 核不到它。')
        print('\n🔴 守卫失效')
        print('=' * 70)
        return 1
    print(f'✅ 守卫成立：最新一轮（第 {mx} 轮）**已写清单**'
          + (f'，且第 {since}~{mx} 轮无缺失' if since is not None else ''))
    print('=' * 70)
    return 0


def cmd_all(a):
    """G385 · 🔑 **一次进程跑完声明核实三件事**。

    🔴 第七十七轮指引①：G383 与 G384 是**两次子进程**，
       每次全量回归都要起两遍 Python + 两遍 `_load_gates()`（import 门禁表）。
    🔑 本入口把 G382（scan-doc）+ G383（verify-all）+ G384（check-current）
       合并进**一个进程**，并把三者的 rc 汇总 —— **任一失败即失败**。
    """
    print('=' * 70)
    print('G385 · 🔑 声明核实**合并入口**（G382 + G383 + G384）')
    print('=' * 70)
    docs = a.docs or [os.path.join(ROOT, 'references', '游戏引擎复刻.md')]
    results = []

    print('\n' + '-' * 70 + '\n① G382 文档编号 vs 代码\n' + '-' * 70)
    r1 = cmd_scan_doc(argparse.Namespace(scan_doc=docs[0],
                                         allowlist=getattr(a, 'allowlist', None)))
    results.append(('G382 文档编号', r1))

    print('\n' + '-' * 70 + '\n② G383 全部清单持续兑现\n' + '-' * 70)
    r2 = cmd_verify_all(a)
    results.append(('G383 持续兑现', r2))

    print('\n' + '-' * 70 + '\n③ G384 最新一轮已写清单\n' + '-' * 70)
    r3 = cmd_check_current(a)
    results.append(('G384 已写清单', r3))

    print('\n' + '=' * 70)
    print('合并核实结果：')
    for name, rc in results:
        print('  %s %s（rc=%d）' % ('✅' if rc == 0 else '🔴', name, rc))
    bad = [n for n, rc in results if rc != 0]

    # 🔑 第八十七轮：**写出文件系统产物**（真正的外部副作用）。
    #    🔑 即使三段**都失败**，产物也照写 ——
    #       🔴 否则"跑不通"与"没跑"又变成同一回事（与"空表即通过"同源）。
    art = CAPABILITY_ARTIFACT.get('audit-all')
    ns = time.time_ns()
    if art:
        ap2 = os.path.join(ROOT, art)
        os.makedirs(os.path.dirname(ap2), exist_ok=True)
        rec = {'generated_at_ns': ns,
               'results': {n: rc for n, rc in results},
               'ok': not bad}
        with open(ap2, 'w', encoding='utf-8') as f:
            json.dump(rec, f, ensure_ascii=False, indent=2)
        print(f'\n🔑 文件系统产物已写入: `{art}` （generated_at_ns={ns}）')
    else:
        print('\n🔴 `CAPABILITY_ARTIFACT` 未登记 —— 无法证明外部副作用')

    print()
    if bad:
        print('🔴 守卫失效：%s' % bad)
        print('=' * 70)
        return 1
    print('✅ 守卫成立：G382 / G383 / G384 **一次进程全部通过**')
    print('=' * 70)
    return 0


def cmd_audit_all(a):
    """G385 · 🔑 **独立校验 `--all` 的完整性**（与 rc 解耦）。

    🔴 第七十八轮诚实结论：G382/G383/G384 现在**跑同一个命令**，
       若 `--all` 内部**漏跑**某项，三条仍会显示同一 rc —— 发现不了。
    🔑 本门禁**另起一个子进程**跑 `--all`，只检查
       **输出里三段标记是否齐全**，不看 rc：
       - 漏跑某段 → 标记缺失 → 🔴 失败
       - 三段都跑了但某段失败 → 标记齐全 → 🔑 **本门禁仍报"结构完整"**
         （🔴 业务失败由 G382~G384 自己报，不混为一谈）
    """
    import subprocess
    print('=' * 70)
    print('G385 · 🔑 `--all` **完整性独立校验**（三段内容特征，与 rc 解耦）')
    print('=' * 70)
    # 🔑 第八十轮：先确认**判据本身可信**。
    #    🔴 若特征串已漂移或非独有，下面的"齐全"结论毫无意义
    #       —— 与第六十三轮"基线必须 rc=0"同源：测之前先证明测得了。
    print('\n⓪ 先行自校验 `ALL_CONTENT`（特征串须段体独有）')
    if cmd_check_content(a) != 0:
        print('\n🔴 **`--audit-all` 的判据不可信** —— '
              '拒绝给出"结构完整"结论（不得用自己的坏尺子量东西）')
        return 1
    cmd = [sys.executable, os.path.join(ROOT, 'scripts', 'claim_verify.py'),
           '--all']
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        out = r.stdout or ''
    except Exception as e:
        print(f'\n🔴 无法运行 `--all`：{type(e).__name__}: {e}')
        print('\n' + '=' * 70 + '\n🔴 守卫失效\n' + '=' * 70)
        return 1
    print(f'\n`--all` 退出码 rc={r.returncode} '
          f'（🔑 本门禁**不看 rc**，只看结构）')
    print(f'输出 {len(out)} 字符')
    miss = [(g, c) for g, c in ALL_CONTENT if c not in out]
    print('\n三段**内容特征**（🔑 段体自己打印的，漏跑则不会出现）：')
    for g, c in ALL_CONTENT:
        print('  %s %s — 含 `%s`' % ('✅' if c in out else '🔴', g, c))
    print('\n' + '=' * 70)
    if miss:
        print(f'🔴 `--all` **未完整执行** —— 缺 {len(miss)} 段: '
              f'{[g for g, _ in miss]}')
        print('   🔑 若某段被漏跑，G382~G384 会**同时显示同一 rc**，无法分辨。')
        print('\n🔴 守卫失效')
        print('=' * 70)
        return 1
    print('✅ 守卫成立：`--all` **三段全部执行**（结构完整）')
    print('   🔑 注意：这**不等于**三段都通过 —— 业务结果看 G382~G384。')
    print('=' * 70)
    return 0


def cmd_verify_all(a):
    """🔑 G383：核实 ledger/ 下**所有** claims_*.txt。

    🔑 元规则：每轮把自己的声明写进 `ledger/claims_<轮次>.txt`，
       本门禁**一次性核实全部** —— 旧轮清单回退了也会被抓到。
    """
    import glob
    print('=' * 70)
    print('G383 · 🔑 全部声明清单核实（每轮一条，防回退）')
    print('=' * 70)
    files = sorted(glob.glob(os.path.join(ROOT, 'ledger', 'claims_*.txt')))
    if not files:
        print('\n🔴 ledger/ 下**没有任何** claims_*.txt —— '
              '不得静默通过（与"空表即通过"同源）')
        print('\n' + '=' * 70 + '\n🔴 守卫失效（无可核实清单）\n' + '=' * 70)
        return 1
    tb = tt = 0
    bad_files = []
    for f in files:
        print(f'\n--- {os.path.basename(f)} ---')
        b, t = _verify_file(f)
        tb += b
        tt += t
        if b:
            bad_files.append(os.path.basename(f))
    print('\n' + '=' * 70)
    print(f'清单 {len(files)} 份 · 声明 {tt} 条 · 🔴 未兑现 {tb}')
    if tb:
        print('🔴 未兑现清单: %s' % bad_files)
        print('\n🔴 守卫失效')
        print('=' * 70)
        return 1
    print('✅ 守卫成立：所有历史声明**至今仍兑现**')
    print('=' * 70)
    return 0


def cmd_scan_doc(a):
    """🔑 扫文档里提到的门禁编号，报出"文档有、代码无"。"""
    p = a.scan_doc
    if not os.path.isfile(p):
        print(f'🚫 文件不存在: {p}')
        return 1
    src = open(p, encoding='utf-8').read()
    ids = set(re.findall(r'G(\d{1,3})\b', src))
    auto, manual = _load_gates()
    valid = set()
    for g in auto | manual:
        valid.add(g[1:])
    unk = sorted([i for i in ids if i not in valid], key=int)
    # 🔑 第七十五轮：**豁免清单** —— 文档里作为**反例/历史记录**提到的
    #    编号（如自测用的 G999）不是真实门禁。
    #    🔴 但豁免必须**显式落盘并写明理由**，不得静默跳过。
    allow = {}
    ap_ = os.path.join(ROOT, 'ledger', 'scan_doc_allowlist.txt')
    if os.path.isfile(ap_):
        for ln in open(ap_, encoding='utf-8'):
            ln = ln.strip()
            if not ln or ln.startswith('#') or ':' not in ln:
                continue
            _k, _r = ln.split(':', 1)
            allow[_k.strip().lstrip('G')] = _r.strip()
    exempt = [i for i in unk if i in allow]
    real = [i for i in unk if i not in allow]
    print('=' * 70)
    print('🔑 文档门禁编号扫描 —— **声称 vs 代码**')
    print('=' * 70)
    print(f'\n文档: {p}')
    print(f'提到的 G 编号: {len(ids)} 个 · 已登记: {len(ids) - len(unk)}'
          f' · 豁免: {len(exempt)}')
    if exempt:
        print('\n🔑 **已豁免**（人工确认，见 ledger/scan_doc_allowlist.txt）：')
        for i in exempt:
            print(f'  - G{i} — {allow[i]}')
    if not real:
        print('\n✅ 无**未兑现**编号（已登记 + 已豁免）')
        print('=' * 70)
        return 0
    print(f'\n🔴 **{len(real)} 个编号在代码中不存在**：')
    for i in real:
        print(f'  - G{i}')
    print('\n🔑 两种可能，**都需人工确认**：')
    print('  ① 声称做了但**实际没做**（🔴 第七十三轮就是这种）')
    print('  ② 作为"未兑现声明"的**历史记录**被提及（✅ 可接受，但应显式标注）')
    print('=' * 70)
    return 1


def cmd_self_test(a):
    """🔑 正反两组实测 —— 证明守卫**真能拦住假声明**。"""
    print('=' * 70)
    print('G381 · 声明核实器自测')
    print('=' * 70)
    pos = [
        # 🔑 第七十九轮：`ALL_CONTENT` 三段内容特征必须齐全（防漏跑降级）
        ('grep', 'scripts/claim_verify.py::ALL_CONTENT'),
        ('cmd', 'claim_verify.py --audit-all'),
        # 🔑 第八十轮：`--check-content` 须存在（ALL_CONTENT 自校验）
        ('cmd', 'claim_verify.py --check-content'),
        ('grep', 'scripts/claim_verify.py::def cmd_check_content'),
        ('grep', 'scripts/claim_verify.py::ALL_CONTENT_FN'),
        # 🔑 第七十六轮：`absent` 正例 —— 该串在**代码行**里确实没有
        ('absent', 'scripts/gate_chaos.py::__绝无此串__'),
        ('gate', 'G379'),
        ('gate', 'G380'),
        ('cmd', 'gate_chaos.py --assert-full'),
        ('cmd', 'gate_chaos.py --assert-no-pollute'),
        ('cachekey', 'audit/.chaos_last.json::full'),
        ('grep', 'scripts/gate_chaos.py::cmd_assert_full'),
    ]
    neg = [
        # 🔑 第七十六轮：`absent` 反例 —— `"--limit", "20"` 已从 G341 移除，
        #    但**注释里**仍有 `--limit` 字样 → 若不过滤说明行会误报。
        #    🔴 这里用**代码行确实存在**的串，验证"出现即拦住"。
        ('absent', 'scripts/gate_chaos.py::_j[_mode] = _res'),
        ('gate', 'G999'),
        ('cmd', 'gate_chaos.py --no-such-flag'),
        ('cachekey', 'audit/.chaos_last.json::nope'),
        ('grep', 'scripts/gate_chaos.py::def_no_such_fn'),
        ('file', 'scripts/no_such_file.py'),
        ('bogus', 'x'),
    ]
    print('\n【正例】应当 **全部通过**（本轮真实实现的）')
    pbad = 0
    for k, v in pos:
        ok, why = _check_one(k, v)
        print(f"  {'✅' if ok else '🚫'} [{k}] {v} — {why}")
        if not ok:
            pbad += 1
    print('\n【反例】应当 **全部拦住**（假声明）')
    nbad = 0
    for k, v in neg:
        ok, why = _check_one(k, v)
        print(f"  {'✅' if not ok else '🚫'} [{k}] {v} — {why}")
        if ok:
            nbad += 1
    print('\n' + '=' * 70)
    ok = not pbad and not nbad
    print(f'✅ 守卫成立：正例 {len(pos) - pbad}/{len(pos)} 通过，'
          f'反例 {len(neg) - nbad}/{len(neg)} 拦住'
          if ok else
          f'🔴 守卫失效：正例漏 {pbad} · 反例漏 {nbad}')
    print('=' * 70)
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(
        description='🔑 声明核实器：回读代码逐条核对完成声明')
    ap.add_argument('--verify', help='声明清单文件')
    ap.add_argument('--scan-doc', help='扫描文档中的门禁编号')
    ap.add_argument('--verify-all', action='store_true',
                    help='G383：核实 ledger/ 下所有 claims_*.txt')
    ap.add_argument('--check-current', action='store_true',
                    help='G384：最新一轮是否写了声明清单')
    ap.add_argument('--require-since', type=int, nargs='?',
                    const=DEFAULT_REQUIRE_SINCE, default=None,
                    help='自该轮起**逐轮**要求清单；裸传则用 '
                         'DEFAULT_REQUIRE_SINCE=%r' % DEFAULT_REQUIRE_SINCE)
    ap.add_argument('--docs', action='append',
                    help='扫描轮次的文档（可重复，默认全部 md）')
    ap.add_argument('--all', action='store_true',
                    help='G385：一次进程跑完 G382+G383+G384')
    ap.add_argument('--audit-all', action='store_true',
                    help='G385：独立校验 --all 三段是否都跑了')
    ap.add_argument('--probe-capability', metavar='NAME', default=None,
                    help='**真跑一次**某个自报的能力（防自报撒谎）')
    ap.add_argument('--declare-capability', action='store_true',
                    help='自报本脚本提供的能力（供 G387 双向校验）')
    ap.add_argument('--check-content', action='store_true',
                    help='G386：自校验 ALL_CONTENT 特征串是否段体独有')
    ap.add_argument('--check-allowlist', action='store_true',
                    help='G389：豁免清单须**带批准轮次**且不得有僵尸豁免')
    ap.add_argument('--check-rc-domain', action='store_true',
                    help='G388：rc 合法域不得有**第二处硬编码**')
    ap.add_argument('--self-test', action='store_true',
                    help='G381：正反两组实测')
    a = ap.parse_args()
    if a.verify:
        return cmd_verify(a)
    if a.verify_all:
        return cmd_verify_all(a)
    if a.check_current:
        return cmd_check_current(a)
    if a.all:
        return cmd_all(a)
    if a.audit_all:
        return cmd_audit_all(a)
    if a.probe_capability is not None:
        return cmd_probe_capability(a)
    if a.declare_capability:
        return cmd_declare_capability(a)
    if a.check_content:
        return cmd_check_content(a)
    if getattr(a, 'check_allowlist', False):
        return cmd_check_allowlist()
    if getattr(a, 'check_rc_domain', False):
        return cmd_check_rc_domain()
    if a.scan_doc:
        return cmd_scan_doc(a)
    if a.self_test:
        return cmd_self_test(a)
    ap.print_help()
    return 0


if __name__ == '__main__':
    sys.exit(main())
