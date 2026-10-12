# -*- coding: utf-8 -*-
"""第一百五十五轮改动：G443 —— 写环节扫描必须识破"一处对了就放行"。

🔴 真实缺陷（154 轮判据②）：
   `found[seg]` 收集**所有**匹配调用的函数名集合，再看 `'req_retry' not in fns`
   → 🔑 同一环节只要有一处走 `req_retry`，另一处**裸 req 写调用就被掩盖**；
   且 GET 读操作、乃至 `append('git/trees')` 这类无关调用也计入 found。

本脚本：
  1) 抽出**唯一实现** `_write_step_scan(tree, steps)` + `_write_step_bad(found, steps)`
  2) G442 判据② 改为调用这两个函数（只认写方法 · 裸 req 即报）
  3) 新增 `cmd_assert_write_step_scan`（G443）
  4) 登记常量 / argparse / dispatch / GATES / BOTH_LAYERS
"""
import io
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
PA = os.path.join(ROOT, 'scripts', 'push_api.py')
RG = os.path.join(ROOT, 'scripts', 'run_all_gates.py')


def rd(p):
    with io.open(p, encoding='utf-8') as f:
        return f.read()


def wr(p, s):
    """原子写：临时文件 → 读回核对 → os.replace（144 轮真实事故）"""
    tmp = p + '.tmp155'
    with io.open(tmp, 'w', encoding='utf-8') as f:
        f.write(s)
    with io.open(tmp, encoding='utf-8') as f:
        back = f.read()
    if back != s:
        raise SystemExit('🔴 写回不一致（%d vs %d）' % (len(back), len(s)))
    os.replace(tmp, p)


def sub1(src, old, new, tag):
    if src.count(old) != 1:
        raise SystemExit('🔴 [%s] old 命中 %d 次（应为 1）' % (tag, src.count(old)))
    return src.replace(old, new)


src = rd(PA)

# ---------------------------------------------------------------- 1) 唯一实现
anchor = """WRITE_RETRY_STEPS = (
    ('git/blobs', 'POST'),
    ('git/trees', 'POST'),
    ('git/commits', 'POST'),
    ('git/refs/heads/main', 'PATCH'),
)
"""
impl = anchor + '''
# 🔑 第一百五十五轮：G442 判据② 抽出为**唯一实现**（G443 要拿它做行为反证，
#    不许 G442 判据② 与 G443 各写一份 —— 152 / 155 轮"同口径两处实现"
#    会让两条门禁给出互相矛盾的结论而无人发现）。
WRITE_METHODS = ('POST', 'PATCH', 'PUT', 'DELETE')
# 🔑 G443 判据① 依赖：唯一实现的函数名（一致改名时不得假阳性）
WRITE_SCAN_FN = '_write_step_scan'
WRITE_BAD_FN = '_write_step_bad'


def _write_step_scan(tree, steps):
    """🔑 G442 判据② 的**唯一实现**：扫描源码里的远端**写**调用。

    🔴 154 轮判据② 的真实缺陷（155 轮对照实验实证）：
       `found[seg] = {所有匹配调用的函数名}`，判据是 `'req_retry' not in fns`
       → 🔑 **只要有一处走 req_retry，同一环节的裸 req 就被掩盖**。
       且不区分 HTTP 方法：GET 读操作也计入，`append('git/trees')`
       这类与网络无关的调用同样计入（153 轮点名的"排除 GET 与 append"）。

    🔑 本实现三条约束：
       a) 函数名**只认** `req` / `req_retry` —— 排除 append / print 等噪声
       b) 第一个参数必须是**写方法**常量（POST/PATCH/PUT/DELETE）
          —— 🔑 GET 读操作不要求走写重试，也不得用来"顶替"写调用
       c) 返回 {片段: {'req': n, 'req_retry': n}}（**分函数计数**，不合并成集合）

    返回 dict；tree 为 None 时返回空 dict（调用方须判空，106 轮同病）。
    """
    found = {}
    if tree is None:
        return found
    for sub in ast.walk(tree):
        if not isinstance(sub, ast.Call):
            continue
        fn = None
        if isinstance(sub.func, ast.Name):
            fn = sub.func.id
        elif isinstance(sub.func, ast.Attribute):
            fn = sub.func.attr
        # 🔑 133 轮教训：按名字访问 vs 按字符串访问都要认；
        #    但**只认网络入口函数**，其余一律排除（154 轮缺陷 a）。
        if fn not in ('req', 'req_retry'):
            continue
        if not sub.args:
            continue
        a0 = sub.args[0]
        if not (isinstance(a0, ast.Constant) and a0.value in WRITE_METHODS):
            continue
        blob = ast.dump(sub)
        for seg, _m in steps:
            if seg in blob:
                found.setdefault(seg, {}).setdefault(fn, 0)
                found[seg][fn] += 1
    return found


def _write_step_bad(found, steps):
    """🔑 判据② 的判定部分（唯一实现）：由扫描结果给出违规列表。

    🔑 每个环节必须**至少一个 req_retry 写调用**且**零个裸 req 写调用**。
       🔴 关键取舍：不是"有 req_retry 就放行" —— 那正是 154 轮的洞：
          同一环节一处走 req_retry，会把另一处裸 req 掩盖掉。
    """
    bad = []
    for seg, _m in steps:
        c = found.get(seg)
        if not c:
            bad.append('环节 %s：源码里找不到**写方法**调用 —— 环节被删？'
                       '（或全改成 GET / append 等无关调用）' % seg)
            continue
        if c.get('req_retry', 0) < 1:
            bad.append('环节 %s 未走 req_retry（%s） —— 一次 5xx 就整轮白干'
                       % (seg, sorted(c)))
        if c.get('req', 0) > 0:
            bad.append('环节 %s 有 %d 处**裸 req** 写调用 —— '
                       '🔴 同一环节另一处走 req_retry 也**不得掩盖**它'
                       '（155 轮实测：154 轮判据② 在此状态 rc=0）'
                       % (seg, c.get('req', 0)))
    return bad
'''
src = sub1(src, anchor, impl, 'impl')

# ------------------------------------------------------ 2) G442 判据② 改调用
old2 = """    found = {}   # url片段 -> set(函数名)
    # 🔑 154 轮修正：原限定 main()，而 git/blobs 在 mk_blob 里 → 判据②
    #    把"清单里有 blobs"误判成"环节被删"。② 与 ⑥ 互为**反向**：
    #    ② = 清单里的每个环节都必须**真的被找到**且走 req_retry；
    #    ⑥ = 源码里的每个写环节都必须**在清单里**。缺任一侧都开洞。
    if tree is not None:
        for sub in ast.walk(tree):
            if not isinstance(sub, ast.Call):
                continue
            fn = None
            if isinstance(sub.func, ast.Name):
                fn = sub.func.id
            # 🔑 133 轮教训：按名字访问 vs 按字符串访问都要认
            if fn is None and isinstance(sub.func, ast.Attribute):
                fn = sub.func.attr
            if fn is None:
                continue
            blob = ast.dump(sub)
            for seg, _m in steps:
                if seg in blob:
                    found.setdefault(seg, set()).add(fn)
    for seg, _m in steps:
        fns = found.get(seg)
        if not fns:
            bad.append(f'环节 {seg}：源码里找不到对应调用 —— 环节被删？')
            continue
        if 'req_retry' not in fns:
            bad.append(f'环节 {seg} 裸调 {sorted(fns)} —— 未走 req_retry，'
                       '一次 5xx 就整轮白干')
    print(f'② AST 三环节函数名: '
          f'{ {k: sorted(v) for k, v in sorted(found.items())} }')
"""
new2 = """    # 🔑 155 轮：判据② 改调**唯一实现**（原内联实现有"一处对了就放行"的洞，
    #    见 _write_step_scan 的 docstring）。② 与 ⑥ 互为**反向**：
    #    ② = 清单里的每个环节都必须**真的被找到**且走 req_retry、且无裸 req；
    #    ⑥ = 源码里的每个写环节都必须**在清单里**。缺任一侧都开洞。
    found = _write_step_scan(tree, steps)
    for b in _write_step_bad(found, steps):
        bad.append(b)
    print(f'② AST 各写环节调用计数: '
          f'{ {k: sorted(v.items()) for k, v in sorted(found.items())} }')
"""
src = sub1(src, old2, new2, 'judge2')

# ------------------------------------------------------------ 3) 新增 G443
anchor3 = """def cmd_assert_blob_retry():
"""
g443 = '''def cmd_assert_write_step_scan():
    """🔑 G443：**写环节扫描必须真能识破"一处对了就放行"**（第一百五十五轮）。

    🔴 真实缺陷（154 轮判据②，本轮对照实验实证）：
       把 tree 环节改成「一处走 req_retry + 一处裸 req」——
       🔑 154 轮判据② **rc=0 放行**（它只看集合里有没有 req_retry），
          G443 **rc=1 抓到**。
       🔴 同一状态一绿一红 —— G443 的存在理由不是推演，是跑出来的。

    🔑 六条判据：
       ① 唯一实现 `_write_step_scan` / `_write_step_bad` 存在，
          且 `cmd_assert_write_retry` **真调用**了它们（不许各写一份）
       ② **行为反证 A**：同一环节同时有 req_retry 与裸 req 的**写**调用
          → 必须报"裸 req"（🔴 154 轮判据② 在此状态 rc=0）
       ③ **行为反证 B**：GET 的 req_retry + POST 的裸 req → 仍须报违规
          （🔴 154 轮判据② 会因 GET 走 req_retry 而放行 —— 不认方法）
       ④ **反向**：只有 GET 的 req_retry、无写调用 → 报"找不到写方法调用"
          （不误报成"走了 req_retry 就合格"）
       ⑤ **桩化反证**：`_write_step_scan` 换成恒返回 {} 的桩
          → ④ 必须仍然报违规（防"扫描被换成空壳"）
       ⑥ 一致改名（函数名整体改）→ **不得**假阳性
    """
    print('🔑 **写环节扫描必须识破"一处对了就放行"**（G443）')
    print('=' * 70)
    os.chdir(ROOT)
    bad = []

    steps = globals().get('WRITE_RETRY_STEPS')
    if not isinstance(steps, (list, tuple)) or not steps:
        bad.append('WRITE_RETRY_STEPS 缺失或为空 —— 反证无样本，判据恒真'
                   '（106 轮"缺失≠没有违规"同病）')
        steps = ()

    fn_scan = globals().get(WRITE_SCAN_FN)
    fn_bad = globals().get(WRITE_BAD_FN)
    print(f'① 唯一实现: {WRITE_SCAN_FN}={fn_scan is not None} · '
          f'{WRITE_BAD_FN}={fn_bad is not None}')
    if fn_scan is None or fn_bad is None:
        bad.append('唯一实现 %s / %s 缺失 —— 崩溃与拒绝在 rc 上无法区分'
                   '（133 轮同病）' % (WRITE_SCAN_FN, WRITE_BAD_FN))
    else:
        # ① b) G442 必须真调用它（不许内联抄一份）
        try:
            me = ast.parse(io.open(os.path.join(
                ROOT, 'scripts', 'push_api.py'), encoding='utf-8').read())
        except Exception as e:
            bad.append(f'无法解析源码 —— 拒绝给结论: {e}')
            me = None
        used_scan = used_bad = False
        if me is not None:
            for node in ast.walk(me):
                if (isinstance(node, ast.FunctionDef)
                        and node.name == 'cmd_assert_write_retry'):
                    for s in ast.walk(node):
                        if (isinstance(s, ast.Call)
                                and isinstance(s.func, ast.Name)
                                and s.func.id in (WRITE_SCAN_FN, WRITE_BAD_FN)):
                            if s.func.id == WRITE_SCAN_FN:
                                used_scan = True
                            else:
                                used_bad = True
        if not used_scan or not used_bad:
            bad.append('cmd_assert_write_retry 未调用 %s / %s'
                       '（scan=%s bad=%s）—— 各写一份会让两条门禁互相矛盾'
                       '而无人发现（152 轮同病）'
                       % (WRITE_SCAN_FN, WRITE_BAD_FN, used_scan, used_bad))
        print(f'① b) G442 真调用唯一实现: scan={used_scan} · bad={used_bad}')

    # ② 行为反证 A：同一环节 req_retry + 裸 req 并存
    snip_a = chr(10).join([
        'def _snip_a():',
        "    req_retry('POST', API + '/git/trees', {'tree': []})",
        "    req('POST', API + '/git/trees', {'tree': []})",
        '',
    ])
    # ③ 行为反证 B：GET 走 req_retry，POST 却是裸 req
    snip_b = chr(10).join([
        'def _snip_b():',
        "    req_retry('GET', API + '/git/trees', None)",
        "    req('POST', API + '/git/trees', {'tree': []})",
        '',
    ])
    # ④ 反向：只有 GET，没有写调用
    snip_c = chr(10).join([
        'def _snip_c():',
        "    req_retry('GET', API + '/git/trees', None)",
        '',
    ])
    if fn_scan is not None and fn_bad is not None and steps:
        for tag, snip, want_kind in (('②', snip_a, '裸 req'),
                                     ('③', snip_b, '裸 req'),
                                     ('④', snip_c, '找不到')):
            try:
                t = ast.parse(snip)
            except Exception as e:
                bad.append('%s 反证样本无法解析 —— 拒绝给结论: %s' % (tag, e))
                continue
            f = fn_scan(t, steps)
            b = fn_bad(f, steps)
            hit = any(want_kind in x for x in b)
            if not hit:
                bad.append('%s 反证失败：期望含「%s」，实际违规=%s —— '
                           '扫描识破不了该形态' % (tag, want_kind, b))
            print('%s 反证（%s）: 扫描=%s · 违规=%d · 命中=%s'
                  % (tag, snip.strip().splitlines()[-1].strip()[:40],
                     f, len(b), hit))
    else:
        bad.append('唯一实现或环节清单缺失 —— ②③④ 无样本，拒绝给结论')

    # ⑤ 桩化反证：把扫描换成恒返回 {} 的桩，④ 必须仍报违规
    if fn_bad is not None and steps:
        stub_hit = len(fn_bad({}, steps)) > 0
        if not stub_hit:
            bad.append('⑤ 桩化反证失败：`_write_step_scan` 被换成恒返回 {} 的桩后'
                       ' _write_step_bad 不报任何违规 —— 扫描变成空壳无人发现')
        print(f'⑤ 桩化反证（扫描恒返回空）: 仍报违规={stub_hit}')

    # ⑥ 一致改名不得假阳性：把样本里的函数名整体改掉，语义不变
    if fn_scan is not None and fn_bad is not None and steps:
        snip_d = snip_a.replace('req_retry(', 'req_retry_renamed(')
        try:
            t = ast.parse(snip_d)
        except Exception as e:
            bad.append('⑥ 反证样本无法解析: %s' % e)
            t = None
        if t is not None:
            f = fn_scan(t, steps)
            # 🔑 改名后两个调用都不再是 req/req_retry → 该环节应判"找不到写调用"
            b = fn_bad(f, steps)
            miss = any('找不到' in x for x in b)
            if not miss:
                bad.append('⑥ 一致改名后未判「找不到写方法调用」—— '
                           '扫描可能按别的口径命中，会假阳性')
            print(f'⑥ 一致改名后: 扫描={f} · 判缺失={miss}')

    if bad:
        print()
        for b in bad:
            print('  🔴', b)
        print(chr(10) + '🔴 **写环节扫描** 不成立')
        return 1
    print(chr(10) + '✅ **写环节扫描** 成立')
    return 0


''' + anchor3
src = sub1(src, anchor3, g443, 'g443')

# -------------------------------------------------------- 4) DEPENDENT_NAMES
old4 = """    'req_retry': ('fn', 'G442 唯一实现：所有远端写操作的重试入口'),
    'cmd_assert_write_retry': ('fn', 'G442 tree/commit/ref 重试的断言入口'),
"""
new4 = old4 + """    # 🔑 第一百五十五轮：G443 依赖
    'WRITE_METHODS': ('const', '远端**写**方法枚举（判据② 只认这些，排除 GET）'),
    'WRITE_SCAN_FN': ('const', 'G443 判据① 依赖：写环节扫描唯一实现的函数名'),
    'WRITE_BAD_FN': ('const', 'G443 判据① 依赖：写环节判定唯一实现的函数名'),
    '_write_step_scan': ('fn', 'G442 判据② 唯一实现：扫描远端写调用'),
    '_write_step_bad': ('fn', 'G442 判据② 唯一实现：由扫描结果给出违规'),
    'cmd_assert_write_step_scan': ('fn', 'G443 写环节扫描的断言入口'),
"""
src = sub1(src, old4, new4, 'dep')

# ------------------------------------------------------------- 5) argparse
old5 = """    ap.add_argument('--assert-write-retry', action='store_true',
                    help='G442：tree/commit/ref 三个写环节必须走 req_retry')
"""
new5 = old5 + """    ap.add_argument('--assert-write-step-scan', action='store_true',
                    help='G443：写环节扫描必须识破"一处对了就放行"'
                         '（154 轮判据② 的真实缺陷）')
"""
src = sub1(src, old5, new5, 'argparse')

# ------------------------------------------------------------- 6) dispatch
old6 = """    if a.assert_write_retry:
        return cmd_assert_write_retry()
"""
new6 = old6 + """    if a.assert_write_step_scan:
        return cmd_assert_write_step_scan()
"""
src = sub1(src, old6, new6, 'dispatch')

wr(PA, src)

# ------------------------------------------------------------- 7) GATES 表
g = rd(RG)
old7 = """    ("G442", "**tree/commit/ref 必须走同一套重试**（不许裸调 req）",
     ["{py}", "{s}/push_api.py", "--assert-write-retry"], "hard",
     ["scripts/push_api.py"]),
"""
new7 = old7 + """    # 🔑 第一百五十五轮：G443 —— **写环节扫描不许"一处对了就放行"**。
    #    🔴 154 轮判据②：`found[seg]` 是函数名**集合**，只看
    #       `'req_retry' not in fns` → 同一环节一处走 req_retry，
    #       **另一处裸 req 被掩盖**；且 GET / append 等无关调用也计入。
    ("G443", "**写环节扫描不许一处对了就放行**（裸 req 不得被掩盖）",
     ["{py}", "{s}/push_api.py", "--assert-write-step-scan"], "hard",
     ["scripts/push_api.py"]),
"""
g = sub1(g, old7, new7, 'gates')

old8 = """    ('G441', 'G440',
"""
new8 = """    # 🔑 第一百五十五轮：G442 ↔ G443 —— 扫描的"有"与"准"必须互补。
    ('G442', 'G443',
     'G442 验「清单里每个写环节**走不走** req_retry」；'
     'G443 验「这个判断**准不准**」（一处对了不得掩盖另一处裸 req）。'
     '只留 G442 → 154 轮判据② 的掩盖洞无人发现；'
     '只留 G443 → 缺少"环节清单被删/新增未登记"这一侧的守望者（判据②⑥）。'),
    ('G441', 'G440',
"""
g = sub1(g, old8, new8, 'both_layers')

old9 = "BOTH_LAYERS_MIN = 16"
new9 = "BOTH_LAYERS_MIN = 17"
g = sub1(g, old9, new9, 'both_min')
wr(RG, g)

print('✅ 155 轮改动已写入')
print('   push_api.py: %d 字节' % len(src))
print('   run_all_gates.py: %d 字节' % len(g))
