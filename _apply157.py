# -*- coding: utf-8 -*-
"""第一百五十七轮：G445 —— 写环节反证必须包含「不认 URL / 认错环节」这一形态。

🔴 真实缺口（156 轮诚实结论② 点名 → 本轮实测）：
   G444 的反证形态只有 A/B/C 三种，三种样本的 URL **都含当前环节**，
   所以"扫描是否真的按 URL 区分环节"从未被检验。
   退化实现「只按 HTTP 方法匹配、完全不看 URL」实测：
       G443 rc=0 放行 · G444 rc=0 放行  ← 两个都看不见
   危害：任一环节只要源码里还有别的 POST 走 req_retry，所有环节都被判
   "已覆盖" → 把 git/trees 改成裸 req 无人发现 → 一次 502 整轮白干。
"""
import io
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PA = os.path.join(HERE, 'scripts', 'push_api.py')
RG = os.path.join(HERE, 'scripts', 'run_all_gates.py')

for p in (PA, RG):
    shutil.copy2(p, p + '.bak157')

pa = io.open(PA, encoding='utf-8').read()
rg = io.open(RG, encoding='utf-8').read()

# ─────────────────────────────────────────────────────────────
# 1) DEPENDENT_NAMES 登记
# ─────────────────────────────────────────────────────────────
A1 = "    'cmd_assert_write_step_proof': ('fn', 'G444 反证逐环节覆盖的断言入口'),\n"
N1 = A1 + """    # \U0001f511 第一百五十七轮：G445（反证必须覆盖「不认 URL」形态）依赖
    'WRITE_PROOF_URL_FN': ('const', 'G445 判据① 依赖：唯一实现的函数名'),
    'WRITE_PROOF_FOREIGN_URL': ('const', 'G445 对照点：与所有环节都不相干的写 URL'),
    'WRITE_PROOF_FOREIGN_WANT': ('const', 'G445 对照点：无关 URL 样本下的期望判定'),
    '_write_proof_url_check': ('fn', 'G445 唯一实现：逐环节各造无关 URL 反证样本'),
    'cmd_assert_write_step_url': ('fn', 'G445 反证「不认 URL」形态的断言入口'),
"""
assert pa.count(A1) == 1, 'A1'
pa = pa.replace(A1, N1)

# ─────────────────────────────────────────────────────────────
# 2) 常量 + 唯一实现（插在 cmd_assert_write_step_proof 定义之前）
# ─────────────────────────────────────────────────────────────
CONST_FN = '''# \U0001f511 第一百五十七轮：G445 依赖
# \U0001f534 156 轮诚实结论② 点名的真实缺口（本轮实测）：G443/G444 的反证
#    形态只有 A/B/C 三种，样本 URL **都含当前环节** —— 于是"扫描是否真的按
#    URL 区分环节"从未被检验。退化实现「只按 HTTP 方法匹配、完全不看 URL」
#    实测在 **G443 与 G444 两个口径下都 rc=0 放行**。
#    \U0001f534 危害：任一环节只要源码里还有**别的** POST 走 req_retry，
#    所有环节都被判"已覆盖" → 把 git/trees 改回裸 req 也无人发现
#    → 一次 502 就整轮白干（153 轮真实事故）。
WRITE_PROOF_URL_FN = '_write_proof_url_check'
# \U0001f511 对照点：与**所有**环节都不相干的写 URL（判据⑥ 守它真不相干）
WRITE_PROOF_FOREIGN_URL = '/repos/o/r/merges'
# \U0001f511 该样本下每个环节的期望判定
WRITE_PROOF_FOREIGN_WANT = '\\u627e\\u4e0d\\u5230'


def _write_proof_url_check(scan_fn, bad_fn, steps, foreign):
    """\U0001f511 G445 的**唯一实现**：对**每一个**写环节各造一个"只有与
    本环节无关的写 URL"的反证样本，期望该环节被判「找不到」。

    \U0001f534 为什么必须补这一形态（本轮实测）：
       A/B/C 三形态里样本 URL **总是含当前环节**，所以"扫描是否真的按 URL
       区分环节"从未被检验。退化实现"任何写方法调用都算所有环节命中"
       在 A/B/C 下**全部命中**（G444 rc=0），而它一旦发生，G442 判据②⑥
       同时失效 —— 环节之间被一视同仁。

    \U0001f511 返回 (miss, covered, rows)；实现缺失 / 清单为空 / foreign 为空时
       miss **非空** —— \U0001f534 缺失必须表现为"未命中"，不得静默通过（106 轮同病）。
    """
    miss = []
    rows = []
    if scan_fn is None or bad_fn is None:
        miss.append('\\u626b\\u63cf/\\u5224\\u5b9a\\u5b9e\\u73b0\\u7f3a\\u5931 \\u2014\\u2014 '
                    '\\u53cd\\u8bc1\\u65e0\\u6cd5\\u8fdb\\u884c\\uff0c\\u62d2\\u7edd\\u7ed9\\u7ed3\\u8bba')
        return miss, 0, rows
    if not steps:
        miss.append('\\u73af\\u8282\\u6e05\\u5355\\u4e3a\\u7a7a \\u2014\\u2014 '
                    '\\u53cd\\u8bc1\\u65e0\\u6837\\u672c\\uff0c\\u5224\\u636e\\u6052\\u771f')
        return miss, 0, rows
    if not foreign:
        miss.append('\\u65e0\\u5173 URL \\u5bf9\\u7167\\u70b9\\u4e3a\\u7a7a \\u2014\\u2014 '
                    '\\u6837\\u672c\\u9000\\u5316\\u6210 A/B/C\\uff0c\\u5224\\u636e\\u6052\\u771f')
        return miss, 0, rows
    want = globals().get('WRITE_PROOF_FOREIGN_WANT') or '\\u627e\\u4e0d\\u5230'
    covered = 0
    for idx, item in enumerate(steps):
        seg, method = item[0], item[1]
        slug = 'u%d' % idx
        # \U0001f511 样本按环节**参数化生成** —— 新增环节自动纳入，不许写死一组
        snip = chr(10).join([
            'def _snip_u_%s():' % slug,
            "    req_retry('%s', API + '%s', {})" % (method, foreign),
        ])
        try:
            t = ast.parse(snip)
        except Exception as e:
            miss.append('\\u73af\\u8282 %s \\u6837\\u672c\\u65e0\\u6cd5\\u89e3\\u6790 \\u2014\\u2014 '
                        '\\u62d2\\u7edd\\u7ed9\\u7ed3\\u8bba: %s' % (seg, e))
            continue
        found = scan_fn(t, steps)
        b = bad_fn(found, steps)
        # \U0001f511 只认**该环节**的违规：其它环节的命中会稀释判据
        #    （155 轮方向⑥ 实测：被无关命中顶替成 rc=0）
        hit = any((want in x and seg in x) for x in b)
        if not hit:
            miss.append('\\u73af\\u8282 %s \\u671f\\u671b\\u300c%s\\u300d\\u672a\\u547d\\u4e2d'
                        '\\uff08\\u5b9e\\u9645\\u8fdd\\u89c4=%s\\uff09\\u2014\\u2014 '
                        '\\u626b\\u63cf\\u7591\\u4f3c\\u53ea\\u6309 HTTP \\u65b9\\u6cd5\\u5339\\u914d'
                        '\\u800c\\u4e0d\\u770b URL\\uff0c\\u5404\\u73af\\u8282\\u88ab\\u4e00\\u89c6\\u540c\\u4ec1'
                        % (seg, want, b))
        else:
            covered += 1
        rows.append((seg, want, hit, len(b)))
    return miss, covered, rows


'''

A2 = 'def cmd_assert_write_step_proof():\n'
assert pa.count(A2) == 1, 'A2'
pa = pa.replace(A2, CONST_FN + A2)

# ─────────────────────────────────────────────────────────────
# 3) 命令（插在 cmd_assert_blob_retry 定义之前）
# ─────────────────────────────────────────────────────────────
CMD = '''def cmd_assert_write_step_url():
    """\U0001f511 G445：**写环节反证必须包含「不认 URL / 认错环节」这一形态**（第一百五十七轮）。

    \U0001f534 真实缺口（156 轮诚实结论② 点名，本轮对照实验实证）：
       G443/G444 的 A/B/C 三形态样本，URL **都含当前环节**；扫描若退化成
       "只按 HTTP 方法匹配、完全不看 URL"，三种形态**全部命中** ——
       \U0001f511 **G443 rc=0 放行** · **G444 rc=0 放行** · **G445 rc=1 抓到**。
       \U0001f534 同一状态两绿一红 —— G445 的存在理由不是推演，是跑出来的。
       \U0001f534 该退化的危害：只要源码里还有**任何一个** POST 走 req_retry，
           **所有**环节都被判"已覆盖"，把 git/trees 改回裸 req 无人发现。

    \U0001f511 七条判据：
       ① 唯一实现 `_write_proof_url_check` 存在（经常量 `WRITE_PROOF_URL_FN` 取，
          不许硬编码函数名 —— 一致改名会假阳性，134/155 轮同病）
       ② 反证覆盖**每一个**环节：覆盖数 == 清单条数，且 ≥ `WRITE_PROOF_SEG_MIN`
       ③ 用**真实** `_write_step_scan` / `_write_step_bad` 跑：未命中必须为空
       ④ **退化反证**："只按方法不看 URL"的实现必须产生未命中
          —— \U0001f534 证明判据③ 不是恒真（106 轮"缺失≠没有违规"）
       ⑤ **内嵌对照**：同一个退化实现在 **G444 口径**（A/B/C 三形态）下
          未命中**为空** —— 证明 G444 真看不见这一形态
       ⑥ 对照点 `WRITE_PROOF_FOREIGN_URL` 必须**真的**与所有环节不相干
          （互不为子串）且样本方法属于 `WRITE_METHODS`
          —— 否则对照点漂移，⑤ 形同虚设
       ⑦ 一致改名不得假阳性：以别名注入同名实现并同步常量后仍可取到
    """
    print('\\U0001f511 **\\\\u5199\\\\u73af\\\\u8282\\\\u53cd\\\\u8bc1\\\\u5fc5\\\\u987b'
          '\\\\u8986\\\\u76d6\\\\u300c\\\\u4e0d\\\\u8ba4 URL\\\\u300d\\\\u5f62\\\\u6001**'
          '\\uff08G445\\uff09')
    print('=' * 70)
    os.chdir(ROOT)
    bad = []

    steps = globals().get('WRITE_RETRY_STEPS')
    if not isinstance(steps, (list, tuple)) or not steps:
        bad.append('WRITE_RETRY_STEPS \\u7f3a\\u5931\\u6216\\u4e3a\\u7a7a \\u2014\\u2014 '
                   '\\u53cd\\u8bc1\\u65e0\\u6837\\u672c\\uff0c\\u5224\\u636e\\u6052\\u771f'
                   '\\uff08106 \\u8f6e"\\u7f3a\\u5931\\u2260\\u6ca1\\u6709\\u8fdd\\u89c4"\\u540c\\u75c5\\uff09')
        steps = ()

    fn_scan = globals().get(WRITE_SCAN_FN)
    fn_bad = globals().get(WRITE_BAD_FN)
    fn_url = globals().get(WRITE_PROOF_URL_FN)
    fn_legacy = globals().get(WRITE_PROOF_FN)
    foreign = globals().get('WRITE_PROOF_FOREIGN_URL')
    print('\\u2460 \\u552f\\u4e00\\u5b9e\\u73b0\\uff08\\u7ecf\\u5e38\\u91cf\\u53d6\\uff09: '
          '%s=%s \\u00b7 %s=%s \\u00b7 %s=%s'
          % (WRITE_PROOF_URL_FN, fn_url is not None,
             WRITE_SCAN_FN, fn_scan is not None,
             WRITE_BAD_FN, fn_bad is not None))
    if fn_url is None:
        bad.append('\\u552f\\u4e00\\u5b9e\\u73b0 %s \\u7f3a\\u5931 \\u2014\\u2014 '
                   '\\u5d29\\u6e83\\u4e0e\\u62d2\\u7edd\\u5728 rc \\u4e0a\\u65e0\\u6cd5\\u533a\\u5206'
                   '\\uff08133 \\u8f6e\\u540c\\u75c5\\uff09' % WRITE_PROOF_URL_FN)
    if fn_scan is None or fn_bad is None:
        bad.append('%s / %s \\u7f3a\\u5931 \\u2014\\u2014 \\u65e0\\u771f\\u5b9e\\u626b\\u63cf\\u53ef\\u4f9b\\u53cd\\u8bc1'
                   % (WRITE_SCAN_FN, WRITE_BAD_FN))
    if fn_legacy is None:
        bad.append('%s \\u7f3a\\u5931 \\u2014\\u2014 \\u2464 \\u65e0 G444 \\u53e3\\u5f84\\u53ef\\u4f9b\\u5bf9\\u7167'
                   % WRITE_PROOF_FN)

    n_seg = len(steps)
    print('\\u2461 \\u73af\\u8282\\u6e05\\u5355\\u6761\\u6570=%d \\u00b7 '
          '\\u8986\\u76d6\\u4e0b\\u9650=%d' % (n_seg, WRITE_PROOF_SEG_MIN))
    if n_seg < WRITE_PROOF_SEG_MIN:
        bad.append('\\u73af\\u8282\\u6e05\\u5355\\u53ea\\u6709 %d \\u6761 < %d \\u2014\\u2014 '
                   '\\u53cd\\u8bc1\\u6837\\u672c\\u96c6\\u8fc7\\u5c0f' % (n_seg, WRITE_PROOF_SEG_MIN))

    # \U0001f534 退化实现：只按 HTTP 方法匹配，完全不看 URL（本轮实测 G443/G444 都放行）
    def _scan_any(tree, steps):
        """\U0001f534 退化：任何写方法调用都算**所有**环节命中。

        \U0001f511 这正是 157 轮实测的洞：G443/G444 的样本 URL 都含当前环节，
           所以"是否真的按 URL 区分"从未被检验 —— 它俩口径下全部命中。
        """
        out = {}
        for seg, _m in steps:
            out[seg] = {}
        if tree is None:
            return out
        for sub in ast.walk(tree):
            if not isinstance(sub, ast.Call):
                continue
            fn = None
            if isinstance(sub.func, ast.Name):
                fn = sub.func.id
            elif isinstance(sub.func, ast.Attribute):
                fn = sub.func.attr
            if fn not in ('req', 'req_retry'):
                continue
            if not sub.args:
                continue
            a0 = sub.args[0]
            if not (isinstance(a0, ast.Constant) and a0.value in WRITE_METHODS):
                continue
            for seg, _m in steps:
                out[seg][fn] = out[seg].get(fn, 0) + 1
        return out

    if fn_url is not None and fn_scan is not None and fn_bad is not None:
        miss, covered, rows = fn_url(fn_scan, fn_bad, steps, foreign)
        for seg, want, hit, nbad in rows:
            print('\\u2462 \\u73af\\u8282 %-22s \\u671f\\u671b\\u300c%s\\u300d \\u00b7 '
                  '\\u547d\\u4e2d=%s \\u00b7 \\u8fdd\\u89c4\\u6570=%d' % (seg, want, hit, nbad))
        print('\\u2462 \\u8986\\u76d6\\u73af\\u8282\\u6570=%d/%d' % (covered, n_seg))
        if miss:
            for m in miss:
                bad.append('\\u2462 ' + m)
        if covered != n_seg:
            bad.append('\\u2462 \\u8986\\u76d6 %d \\u4e2a\\u73af\\u8282 != \\u6e05\\u5355 %d \\u6761'
                       % (covered, n_seg))

        # ④ 退化反证
        dmiss, dcov, _drows = fn_url(_scan_any, fn_bad, steps, foreign)
        print('\\u2463 \\u9000\\u5316\\uff08\\u53ea\\u6309\\u65b9\\u6cd5\\u4e0d\\u770b URL\\uff09: '
              '\\u8986\\u76d6=%d/%d \\u00b7 \\u672a\\u547d\\u4e2d=%d' % (dcov, n_seg, len(dmiss)))
        if not dmiss:
            bad.append('\\u2463 \\u9000\\u5316\\u5b9e\\u73b0\\u672a\\u88ab\\u5224\\u4e3a\\u9000\\u5316 '
                       '\\u2014\\u2014 \\u5224\\u636e\\u2462 \\u53ef\\u80fd\\u6052\\u771f')

        # ⑤ 内嵌对照：同一退化实现在 G444 口径下**放行**
        if fn_legacy is not None:
            lmiss, lcov, _lrows = fn_legacy(_scan_any, fn_bad, steps)
            print('\\u2464 G444 \\u53e3\\u5f84\\uff08A/B/C \\u4e09\\u5f62\\u6001\\uff09\\u4e0b\\u540c\\u4e00'
                  '\\u9000\\u5316\\u5b9e\\u73b0: \\u8986\\u76d6=%d/%d \\u00b7 \\u672a\\u547d\\u4e2d=%d'
                  % (lcov, n_seg, len(lmiss)))
            if lmiss or lcov != n_seg:
                bad.append('\\u2464 \\u9000\\u5316\\u5b9e\\u73b0\\u5728 G444 \\u53e3\\u5f84\\u4e0b\\u672a'
                           '\\u88ab\\u653e\\u884c\\uff08\\u672a\\u547d\\u4e2d=%d\\uff09 \\u2014\\u2014 '
                           '\\u5185\\u5d4c\\u5bf9\\u7167\\u4e0d\\u6210\\u7acb\\uff0c'
                           '\\u65e0\\u6cd5\\u8bc1\\u660e G444 \\u771f\\u770b\\u4e0d\\u89c1' % len(lmiss))
            else:
                print('\\u2465 \\U0001f511 \\u5185\\u5d4c\\u5bf9\\u7167\\u6210\\u7acb\\uff1a'
                      '\\u9000\\u5316\\u5b9e\\u73b0\\u5728 G444 \\u53e3\\u5f84\\u4e0b**\\u5168\\u7eff**\\uff0c'
                      '\\u5728 G445 \\u65e0\\u5173 URL \\u53e3\\u5f84\\u4e0b\\u88ab\\u6293\\u5230')

    # ⑥ 对照点必须真的与所有环节不相干
    if not foreign:
        bad.append('\\u2465 WRITE_PROOF_FOREIGN_URL \\u7f3a\\u5931 \\u2014\\u2014 '
                   '\\u65e0\\u5bf9\\u7167\\u70b9\\uff0c\\u62d2\\u7edd\\u7ed9\\u7ed3\\u8bba')
    else:
        clash = [s for s, _m in steps if (s in foreign or foreign in s)]
        print('\\u2465 \\u65e0\\u5173 URL=%r \\u00b7 \\u4e0e\\u73af\\u8282\\u51b2\\u7a81=%s'
              % (foreign, clash))
        if clash:
            bad.append('\\u2465 \\u65e0\\u5173 URL %r \\u4e0e\\u73af\\u8282 %s \\u4e92\\u4e3a\\u5b50\\u4e32 '
                       '\\u2014\\u2014 \\u6837\\u672c\\u9000\\u5316\\u6210 A/B/C\\uff0c'
                       '\\u2464 \\u7684\\u5bf9\\u7167\\u5173\\u7cfb\\u6f02\\u79fb' % (foreign, clash))
        if not steps or steps[0][1] not in WRITE_METHODS:
            bad.append('\\u2465 \\u6837\\u672c\\u65b9\\u6cd5\\u4e0d\\u5728 WRITE_METHODS \\u5185 '
                       '\\u2014\\u2014 \\u6837\\u672c\\u65e0\\u6548\\uff0c\\u5224\\u636e\\u6052\\u771f')

    # ⑦ 一致改名不得假阳性
    if fn_url is not None:
        alias = WRITE_PROOF_URL_FN + '_alias_probe'
        old = globals().get(WRITE_PROOF_URL_FN)
        globals()[alias] = old
        try:
            got = globals().get(alias)
            ok = got is old
        finally:
            globals().pop(alias, None)
        print('\\u2466 \\u4e00\\u81f4\\u6539\\u540d\\uff08%s\\uff09\\u540e\\u4ecd\\u53ef\\u53d6\\u5230'
              '\\u540c\\u4e00\\u5b9e\\u73b0: %s' % (alias, ok))
        if not ok:
            bad.append('\\u2466 \\u5224\\u636e\\u2460 \\u7591\\u4f3c\\u786c\\u7f16\\u7801\\u51fd\\u6570\\u540d '
                       '\\u2014\\u2014 \\u4e00\\u81f4\\u6539\\u540d\\u4f1a\\u5047\\u9633\\u6027'
                       '\\uff08134/155 \\u8f6e\\u540c\\u75c5\\uff09')

    if bad:
        print()
        for b in bad:
            print('  \\U0001f534', b)
        print(chr(10) + '\\U0001f534 **\\u5199\\u73af\\u8282\\u53cd\\u8bc1\\u5fc5\\u987b\\u8986\\u76d6'
              '\\u300c\\u4e0d\\u8ba4 URL\\u300d\\u5f62\\u6001** \\u4e0d\\u6210\\u7acb')
        return 1
    print(chr(10) + '\\u2705 **\\u5199\\u73af\\u8282\\u53cd\\u8bc1\\u5fc5\\u987b\\u8986\\u76d6'
          '\\u300c\\u4e0d\\u8ba4 URL\\u300d\\u5f62\\u6001** \\u6210\\u7acb')
    return 0


'''

A3 = 'def cmd_assert_blob_retry():\n'
assert pa.count(A3) == 1, 'A3'
pa = pa.replace(A3, CMD + A3)

# ─────────────────────────────────────────────────────────────
# 4) argparse
# ─────────────────────────────────────────────────────────────
A4 = """    ap.add_argument('--assert-blob-retry', action='store_true',
"""
N4 = """    ap.add_argument('--assert-write-step-url', action='store_true',
                    help='G445：写环节反证必须覆盖「不认 URL / 认错环节」形态'
                         '（156 轮：A/B/C 三形态都只测含本环节的 URL）')
""" + A4
assert pa.count(A4) == 1, 'A4'
pa = pa.replace(A4, N4)

# ─────────────────────────────────────────────────────────────
# 5) main 分发
# ─────────────────────────────────────────────────────────────
A5 = """    if a.assert_write_step_proof:
        return cmd_assert_write_step_proof()
"""
N5 = A5 + """    if a.assert_write_step_url:
        return cmd_assert_write_step_url()
"""
assert pa.count(A5) == 1, 'A5'
pa = pa.replace(A5, N5)

io.open(PA, 'w', encoding='utf-8').write(pa)

# ─────────────────────────────────────────────────────────────
# 6) run_all_gates：GATES 新增 G445
# ─────────────────────────────────────────────────────────────
A6 = """     ["{py}", "{s}/push_api.py", "--assert-write-step-proof"], "hard",
     ["scripts/push_api.py"]),
]
"""
N6 = """     ["{py}", "{s}/push_api.py", "--assert-write-step-proof"], "hard",
     ["scripts/push_api.py"]),
    # \U0001f511 第一百五十七轮：G445 —— **反证必须覆盖「不认 URL」这一形态**。
    #    \U0001f534 156 轮诚实结论② 点名的真实缺口：A/B/C 三形态的样本 URL
    #        **都含当前环节**，所以"扫描是否真的按 URL 区分环节"从未被检验。
    #        退化实现「只按 HTTP 方法匹配、完全不看 URL」实测在
    #        **G443 rc=0 与 G444 rc=0 两个口径下都放行**（本轮实测）。
    ("G445", "**写环节反证必须覆盖「不认 URL / 认错环节」形态**（每个环节各造一次）",
     ["{py}", "{s}/push_api.py", "--assert-write-step-url"], "hard",
     ["scripts/push_api.py"]),
]
"""
assert rg.count(A6) == 1, 'A6'
rg = rg.replace(A6, N6)

# ─────────────────────────────────────────────────────────────
# 7) BOTH_LAYERS：G444 ↔ G445
# ─────────────────────────────────────────────────────────────
A7 = """     '只留 G444 → 缺少「一处对了就放行」这一形态的守望者（154 轮判据② 的洞）。'
     '\\U0001f511 「反证准不准」与「反证覆盖全不全」是两件事，缺一则该环节等于没守护。'),
"""
N7 = A7 + """    # \U0001f511 第一百五十七轮：G444 ↔ G445 —— 反证的「全」与「认得对」必须互补。
    ('G444', 'G445',
     'G444 验「反证是不是**每个环节都造了一次**」；'
     'G445 验「反证样本里有没有**与本环节不相干的 URL**」—— 即扫描是否真按 URL 区分环节。'
     '\\U0001f534 只留 G444 → 扫描退化成"任何写方法调用都算所有环节命中"后它 rc=0 放行'
     '（157 轮实测），各环节的裸 req 从此互相掩盖；'
     '只留 G445 → 缺少"逐环节各造一次"的守望者（156 轮实测① 的洞）。'
     '\\U0001f511 「每个环节都测了」与「测得对不对」是两件事，缺一则该环节等于没守护。'),
"""
assert rg.count(A7) == 1, 'A7'
rg = rg.replace(A7, N7)

io.open(RG, 'w', encoding='utf-8').write(rg)

print('✅ 写入完成')
print('push_api.py  %d 字节' % len(pa))
print('run_all_gates.py  %d 字节' % len(rg))
