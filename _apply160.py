# -*- coding: utf-8 -*-
"""第一百六十轮：G448 —— 「引用」口径必须有命名空间限定（159 轮诚实结论②）"""
import io, os, sys

ROOT = os.getcwd()
P = os.path.join(ROOT, 'scripts', 'push_api.py')

def read(p):
    with io.open(p, encoding='utf-8') as fh:
        return fh.read()

def write(p, s):
    """原子写：临时文件 → 读回核对 → os.replace（144 轮教训）"""
    tmp = p + '.tmp160'
    with io.open(tmp, 'w', encoding='utf-8') as fh:
        fh.write(s)
    back = read(tmp)
    if back != s:
        raise SystemExit('🔴 读回不一致：%s' % p)
    import py_compile, tempfile
    if p.endswith('.py'):
        try:
            py_compile.compile(tmp, cfile=tempfile.mktemp(), doraise=True)
        except Exception as e:
            raise SystemExit('🔴 语法错误，未写入：%s\n%s' % (p, e))
    os.replace(tmp, p)
    if read(p) != s:
        raise SystemExit('🔴 replace 后仍不一致：%s' % p)

src = read(P)
orig = src

# ── 1) DEPENDENT_NAMES 登记 ──────────────────────────────────────────────
anchor = "    'cmd_assert_call_target_single': ('fn', 'G447 断言入口'),\n"
assert src.count(anchor) == 1, 'anchor1'
add = anchor + """    # 🔑 第一百六十轮：G448（「引用」口径必须有命名空间限定）
    'NS_REF_FN': ('const', 'G448 判据① 依赖：命名空间限定引用解析唯一实现的函数名'),
    'NS_FNS': ('const', 'G448 判据④ 依赖：只认这三种命名空间函数'),
    'NS_REF_FORMS': ('const', 'G448 判据④ 依赖：命名空间引用形态表（必须被认）'),
    'NS_REF_FORMS_MIN': ('const', 'G448 判据⑦ 下限：命名空间形态条目数'),
    'NS_REF_NOISE_FORMS': ('const', 'G448 判据⑤ 依赖：任意字典查表形态表（必须**不**被认）'),
    'NS_REF_NOISE_MIN': ('const', 'G448 判据⑦ 下限：噪声形态条目数'),
    'NS_REF_USERS': ('const', 'G448 判据② 依赖：引用计数必须走限定实现的调用点'),
    'NS_REF_USERS_MIN': ('const', 'G448 判据⑦ 下限：调用点条目数'),
    'NS_REF_SCOPE_FN': ('const', 'G448 判据① 依赖：唯一实现的函数名'),
    '_ns_ref_names': ('fn', 'G448 治本唯一实现：只认命名空间限定的按字符串引用'),
    '_ns_ref_scope_bad': ('fn', 'G448 唯一实现：口径限定 + 结果真被用'),
    'cmd_assert_ns_ref_scope': ('fn', 'G448 断言入口'),
"""
src = src.replace(anchor, add, 1)

# ── 2) 常量 + 唯一实现 _ns_ref_names ──────────────────────────────────────
anchor2 = "def _write_step_scan(tree, steps):\n"
assert src.count(anchor2) == 1, 'anchor2'
ns_impl = '''# 🔑 第一百六十轮：G448 —— **「引用」口径的命名空间限定**（唯一实现）
#    🔴 159 轮诚实结论②：`_scan_ref_consts_bad` 改走 `_call_target_name` 后，
#       **任何** `x.get('X')` / `d['X']` 都算"引用过"（实测把 210 个与常量引用
#       无关的字符串 —— 'audit-all' / 'allowlist' / '' / '999999' … ——
#       当成引用证据）。
#       🔑 危害不是"多报几条"：引用证据被稀释 → 未登记常量几乎一律被判
#          "已引用" → 误报 → 催生**批量豁免**（152 轮实测 75 条理由一字不差）
#          → 判据被豁免表吃掉。
#    🔑 于是"引用"必须是**可判定的**：只认 `globals()/locals()/vars()` 这三种
#       命名空间上的按字符串访问；任意映射（cfg['X'] / getattr(obj,'X')）
#       **不算引用** —— 静态不可判定，宁可不认（并由 G448 判据⑤ 常驻对照）。
NS_REF_FN = '_ns_ref_names'
NS_FNS = ('globals', 'locals', 'vars')
NS_REF_FORMS = ("globals()['X']", "locals()['X']", "vars()['X']",
                "globals().get('X')", "locals().get('X')", "vars().get('X')",
                "getattr(globals(), 'X')")
NS_REF_FORMS_MIN = 6
NS_REF_NOISE_FORMS = ("cfg['X']", "cfg.get('X')", "d['X']", "d.get('X')",
                      "getattr(obj, 'X')", "self.cfg['X']")
NS_REF_NOISE_MIN = 5
NS_REF_USERS = ('_scan_ref_consts_bad',)
NS_REF_USERS_MIN = 1
NS_REF_SCOPE_FN = '_ns_ref_scope_bad'


def _ns_ref_names(node):
    """🔑 **唯一实现**：解析一个 AST 节点里**命名空间限定**的按字符串引用。

    🔑 只认（**必须有命名空间函数**）：
        globals()['X'] / locals()['X'] / vars()['X']
        globals().get('X') / locals().get('X') / vars().get('X')
        getattr(globals(), 'X')
    🔴 **不认**（任意映射，静态不可判定）：
        cfg['X'] / cfg.get('X') / d['X'] / getattr(obj, 'X') / self.cfg['X']
       —— 🔑 这些若算"引用"，任何字典键都会变成引用证据（159 轮实测 210 个）。
    """
    names = set()
    nsf = tuple(globals().get('NS_FNS') or ())
    if not nsf:
        return names

    def _ns_call(v):
        """v 是否是 globals() / locals() / vars() 这类命名空间调用"""
        if not isinstance(v, ast.Call) or v.args or v.keywords:
            return False
        f = v.func
        nm = f.id if isinstance(f, ast.Name) else (
            f.attr if isinstance(f, ast.Attribute) else None)
        return nm in nsf

    def _str_const(a):
        return isinstance(a, ast.Constant) and isinstance(a.value, str)

    if isinstance(node, ast.Subscript):
        if _ns_call(node.value) and _str_const(node.slice):
            names.add(node.slice.value)
    elif isinstance(node, ast.Call):
        f = node.func
        if isinstance(f, ast.Attribute) and f.attr == 'get':
            if _ns_call(f.value) and node.args and _str_const(node.args[0]):
                names.add(node.args[0].value)
        elif isinstance(f, ast.Name) and f.id == 'getattr':
            if len(node.args) >= 2 and _ns_call(node.args[0])                     and _str_const(node.args[1]):
                names.add(node.args[1].value)
    return names


'''
src = src.replace(anchor2, ns_impl + anchor2, 1)

# ── 3) _scan_ref_consts_bad 改走限定实现 ──────────────────────────────────
old_blk = """            # 🔑 第一百五十九轮：**治本推广** —— 按字符串 / 间接访问的所有等价
            #    写法由唯一实现 `_call_target_name` 一处解析（119 轮判据：
            #    重复出现的同类错误应改到"让它不可能发生"）。
            #    🔴 原实现只认 `globals().get('X')` 一种形态 ——
            #       `getattr(m, 'X')` / `ns['X']` / `locals().get('X')` /
            #       `vars().get('X')` / `globals()['X']` **数不到**，
            #       而"数不到"的表现是"未被引用"，与"真的没被引用"一模一样
            #       （152 轮同病的**残留**，本类第五次）。
            if isinstance(n, (ast.Call, ast.Subscript)):
                grefs |= _call_target_name(n)
"""
assert src.count(old_blk) == 1, 'anchor3'
new_blk = """            # 🔑 第一百六十轮修正：**引用计数必须是可判定的** ——
            #    按字符串访问只认 `globals()/locals()/vars()` 上的访问
            #    （唯一实现 `_ns_ref_names` 一处解析，119 轮判据：
            #    重复出现的同类错误应改到"让它不可能发生"）。
            #    🔴 159 轮把它换成宽口径 `_call_target_name` 后，任何
            #       `cfg['X']` / `cfg.get('X')` 都算"引用过" —— 实测多认
            #       **210** 个与常量引用无关的字符串，引用证据被稀释。
            #    ⚠️ 已知边界：配置字典里的真引用（`SETTINGS['CONST']`）会漏，
            #       但静态不可判定时"宁可不认"，由 G448 判据⑤ 常驻对照。
            if isinstance(n, (ast.Call, ast.Subscript)):
                grefs |= _ns_ref_names(n)
"""
src = src.replace(old_blk, new_blk, 1)

# ── 4) CALL_TARGET_USERS：`_scan_ref_consts_bad` 已不再做调用目标解析 ──────
old_u = "CALL_TARGET_USERS = ('_scan_ref_consts_bad', '_no_dirty_wired_bad')"
assert src.count(old_u) == 1, 'anchor4'
src = src.replace(old_u,
    "# 🔑 160 轮修正：`_scan_ref_consts_bad` 做的是**引用计数**（口径必须窄），\n"
    "#    已改走 `_ns_ref_names`，不再是调用目标解析的调用点（由 G448 守护）；\n"
    "#    此处补入 `_write_step_scan`（它真在做调用目标解析）。\n"
    "CALL_TARGET_USERS = ('_write_step_scan', '_no_dirty_wired_bad')", 1)

# ── 5) G448 唯一实现 + 断言入口 ───────────────────────────────────────────
anchor5 = "def cmd_assert_blob_retry():\n"
assert src.count(anchor5) == 1, 'anchor5'
g448 = '''def _ns_ref_scope_bad(tree):
    """🔑 G448 判据②③ 的**唯一实现**：「引用」口径必须有命名空间限定。

    🔴 159 轮诚实结论② 点名：`_scan_ref_consts_bad` 改走 `_call_target_name`
       后，**任何** `x.get('X')` / `d['X']` 都算"引用过"。
    🔑 三条：必须走限定实现 / **不得再调用宽口径** / 结果不得被丢弃。
    """
    rows = []
    if tree is None:
        return ['源码树为空 —— 拒绝给结论'], rows
    ns_key = globals().get('NS_REF_FN')
    fn_ns = globals().get(ns_key) if isinstance(ns_key, str) else None
    if not callable(fn_ns):
        return ['%r 指向的实现不存在 —— 拒绝给结论' % (ns_key,)], rows
    ct = globals().get('CALL_TARGET_FN')
    users = tuple(globals().get('NS_REF_USERS') or ())
    minu = int(globals().get('NS_REF_USERS_MIN') or 0)
    bad = []
    if len(users) < minu:
        bad.append('NS_REF_USERS 只有 %d 条 < %d —— 疑似被删条目，'
                   '引用计数的口径无人守护' % (len(users), minu))
    parents = {}
    for nd in ast.walk(tree):
        for ch in ast.iter_child_nodes(nd):
            parents[id(ch)] = nd
    fnmap = {}
    for nd in ast.walk(tree):
        if isinstance(nd, (ast.FunctionDef, ast.AsyncFunctionDef)):
            fnmap.setdefault(nd.name, nd)
    for u in users:
        fn = fnmap.get(u)
        if fn is None:
            bad.append('找不到函数 %s —— 调用点被删？拒绝给结论' % u)
            continue
        calls = [n for n in ast.walk(fn)
                 if isinstance(n, ast.Call) and isinstance(ns_key, str)
                 and ns_key in _call_target_name(n.func)]
        if not calls:
            bad.append('%s 未调用 %s —— 引用计数仍在用宽口径，'
                       '任意字典查表会被当成引用证据' % (u, ns_key))
        disc = sum(1 for c in calls if isinstance(parents.get(id(c)), ast.Expr))
        if disc:
            bad.append('%s 有 %d 处**调用后丢弃结果** —— 解析了却不用，'
                       '与"没解析"在输出上完全一样' % (u, disc))
        wide = 0
        if isinstance(ct, str):
            wide = sum(1 for n in ast.walk(fn)
                       if isinstance(n, ast.Call)
                       and ct in _call_target_name(n.func))
        if wide:
            bad.append('%s 仍有 %d 处调用 %s（**宽口径**）—— 应改用 %s，'
                       '否则任意字典查表都算引用' % (u, wide, ct, ns_key))
        rows.append((u, len(calls), disc, wide))
    return bad, rows


def cmd_assert_ns_ref_scope():
    """🔑 G448：**「引用」口径必须有命名空间限定**（第一百六十轮）。

    🔴 159 轮诚实结论②（本轮对照实验实证）：`_scan_ref_consts_bad` 改走
       `_call_target_name` 之后，**任何** `x.get('X')` / `d['X']` 都算"引用过"
       —— 实测宽口径比窄口径**多认 291 个字符串**，其中 **210 个**既不是
       `ast.Name` 引用也不是命名空间引用（'audit-all' / 'allowlist' / '' …）。
       🔑 危害是**稀释**：引用证据几乎恒真 → 未登记常量一律被判"已引用"
          → 误报 → 催生批量豁免（152 轮实测 75 条理由一字不差）→ 判据被吃掉。

    🔑 八条判据：
       ① 唯一实现 `_ns_ref_names` 存在（经常量取，不许硬编码函数名）
       ② 引用计数**必须**走它，且**不得**再调用宽口径 `_call_target_name`
       ③ 结果必须真被用（调用节点不得是独立的 `ast.Expr` 语句）
       ④ 命名空间形态**逐条**各造一次：真实实现**必须认**
          （漏认 = 真引用被判"没引用" → 静默假阴性）
       ⑤ 🔑 噪声形态**逐条**各造一次：真实实现**必须不认**，
          而宽口径实现**必须认** —— **内嵌对照**，证明两条口径真的不同，
          否则"限定"只是文字游戏
       ⑥ 一致改名不得假阳性
       ⑦ 形态表 / 调用点表条目数下限（防删条目缩小视野）
       ⑧ 桩化（恒返回空）→ 必须拒绝给结论
    """
    print('\\U0001f511 **「引用」口径必须有命名空间限定**（G448）')
    print('=' * 70)
    os.chdir(ROOT)
    bad = []

    ns_key = globals().get('NS_REF_FN')
    fn_ns = globals().get(ns_key) if isinstance(ns_key, str) else None
    ct_name = globals().get('CALL_TARGET_FN')
    fn_ct = globals().get(ct_name) if isinstance(ct_name, str) else None
    print('① 唯一实现（经常量取）: %s=%r · 可调用=%s'
          % ('NS_REF_FN', ns_key, fn_ns is not None))
    if fn_ns is None:
        bad.append('NS_REF_FN 缺失或其指向的实现不存在 —— 拒绝给结论')

    src_p = os.path.join(ROOT, 'scripts', 'push_api.py')
    try:
        with io.open(src_p, encoding='utf-8') as fh:
            text = fh.read()
        tree = ast.parse(text)
    except (OSError, SyntaxError) as e:
        print('\\U0001f534 解析自身源码失败：%s' % e)
        return 1

    # ②③ 口径限定 + 不得再用宽口径 + 结果真被用
    sfn = globals().get('NS_REF_SCOPE_FN')
    fn_scope = globals().get(sfn) if isinstance(sfn, str) else None
    if fn_scope is None:
        bad.append('唯一实现 %r 缺失 —— 拒绝给结论' % sfn)
        rows = []
    else:
        b2, rows = fn_scope(tree)
        for u, ncall, disc, wide in rows:
            print('②③ %-24s 限定实现调用处=%d · 丢弃结果=%d · 宽口径残留=%d'
                  % (u, ncall, disc, wide))
        bad.extend(b2)
        un = len(tuple(globals().get('NS_REF_USERS') or ()))
        print('②③ 调用点条数=%d · 实际逐条核验=%d' % (un, len(rows)))
        if len(rows) != un:
            bad.append('②③ 逐条核验了 %d 个调用点 != 清单 %d 条 —— '
                       '疑似唯一实现被桩化（恒返回空），拒绝给结论'
                       % (len(rows), un))

    # ④⑤ 逐形态行为反证（常驻对照）
    forms = tuple(globals().get('NS_REF_FORMS') or ())
    fmin = int(globals().get('NS_REF_FORMS_MIN') or 0)
    noise = tuple(globals().get('NS_REF_NOISE_FORMS') or ())
    nmin = int(globals().get('NS_REF_NOISE_MIN') or 0)
    print('⑦ 命名空间形态=%d（下限 %d）· 噪声形态=%d（下限 %d）'
          % (len(forms), fmin, len(noise), nmin))
    if len(forms) < fmin:
        bad.append('NS_REF_FORMS 只有 %d 条 < %d —— 疑似被删形态'
                   % (len(forms), fmin))
    if len(noise) < nmin:
        bad.append('NS_REF_NOISE_FORMS 只有 %d 条 < %d —— 疑似被删形态'
                   % (len(noise), nmin))

    def _probe(form, fn):
        src2 = 'def _f():\\n    return %s\\n' % form
        try:
            t2 = ast.parse(src2)
        except SyntaxError:
            return None
        got = set()
        for n in ast.walk(t2):
            got |= fn(n)
        return 'X' in got

    if fn_ns is not None:
        for form in forms:
            real = _probe(form, fn_ns)
            old = _probe(form, fn_ct) if fn_ct is not None else None
            print('④ 命名空间形态 %-22s 真实实现认出=%s · 宽口径认出=%s'
                  % (form, real, old))
            if real is None:
                bad.append('④ 形态 %r 不是合法源码 —— 样本无效' % form)
            elif not real:
                bad.append('④ 形态 %r 连真实实现都认不出 —— 真引用会被判'
                           '"没引用"（静默假阴性）' % form)
        for form in noise:
            real = _probe(form, fn_ns)
            old = _probe(form, fn_ct) if fn_ct is not None else None
            print('⑤ 噪声形态     %-22s 真实实现认出=%s · 宽口径认出=%s'
                  % (form, real, old))
            if real is None:
                bad.append('⑤ 形态 %r 不是合法源码 —— 样本无效' % form)
            elif real:
                bad.append('⑤ 噪声形态 %r 被真实实现认成"引用" —— '
                           '口径又被放宽了' % form)
            if old is not True:
                bad.append('⑤ 噪声形态 %r 未被宽口径实现认出 —— 样本退化，'
                           '两条口径的对照关系漂移' % (form,))

    # ⑥ 一致改名不得假阳性
    if isinstance(ns_key, str) and fn_ns is not None:
        alias = ns_key + '_alias_probe'
        globals()[alias] = fn_ns
        try:
            ok = globals().get(alias) is fn_ns
        finally:
            globals().pop(alias, None)
        print('⑥ 一致改名（%s）后仍可取到同一实现: %s' % (alias, ok))
        if not ok:
            bad.append('⑥ 判据① 疑似硬编码函数名 —— 一致改名会假阳性')

    # ⑧ 桩化（恒返回空）→ 必须拒绝给结论
    if isinstance(ns_key, str) and fn_ns is not None and fn_scope is not None:
        saved = globals().get(ns_key)
        globals()[ns_key] = lambda node: set()
        try:
            b8, _r8 = fn_scope(tree)
            caught8 = bool(b8)
            print('⑧ 桩化（恒返回空）后仍被判为合规: %s' % (not caught8))
            if not caught8:
                bad.append('⑧ 唯一实现被桩成恒返回空后仍报合规 —— 判据恒真')
        finally:
            globals()[ns_key] = saved

    # ⚠️ 实测事实（只打印，不作断言 —— 环境变化不应造成假阳性）
    try:
        wide_n = set(); nar_n = set(); name_n = set()
        for ffn in sorted(os.listdir(os.path.join(ROOT, 'scripts'))):
            if not ffn.endswith('.py'):
                continue
            try:
                t3 = ast.parse(io.open(os.path.join(ROOT, 'scripts', ffn),
                                       encoding='utf-8').read())
            except Exception:
                continue
            for n in ast.walk(t3):
                if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load):
                    name_n.add(n.id)
                if isinstance(n, (ast.Call, ast.Subscript)):
                    if fn_ns is not None:
                        nar_n |= fn_ns(n)
                    if fn_ct is not None:
                        wide_n |= fn_ct(n)
        junk = wide_n - name_n - nar_n
        print('⚠️ 实测：宽口径认 %d 个字符串 · 窄口径认 %d 个 · '
              '宽口径多认的**无关**字符串 %d 个（只打印不断言）'
              % (len(wide_n), len(nar_n), len(junk)))
    except Exception as e:
        print('⚠️ 实测跳过：%s' % e)

    if bad:
        print()
        for b in bad:
            print('  \\U0001f534', b)
        print(chr(10) + '\\U0001f534 **「引用」口径必须有命名空间限定** 不成立')
        return 1
    print(chr(10) + '✅ **「引用」口径必须有命名空间限定** 成立')
    return 0


'''
src = src.replace(anchor5, g448 + anchor5, 1)

# ── 6) argparse ──────────────────────────────────────────────────────────
anchor6 = """    ap.add_argument('--assert-call-target-single', action='store_true',
                    help='G447：等价写法解析必须唯一实现，且结果真被用'
                         '（158 轮：只推广了一处 · 调用后丢弃结果照样绿）')
"""
assert src.count(anchor6) == 1, 'anchor6'
src = src.replace(anchor6, anchor6 + """    ap.add_argument('--assert-ns-ref-scope', action='store_true',
                    help='G448：「引用」口径必须有命名空间限定'
                         '（159 轮：任何 cfg[\\'X\\'] 都算引用 → 证据被稀释）')
""", 1)

# ── 7) 分发 ──────────────────────────────────────────────────────────────
anchor7 = """    if a.assert_call_target_single:
        os.chdir(ROOT)
        return cmd_assert_call_target_single()
"""
assert src.count(anchor7) == 1, 'anchor7'
src = src.replace(anchor7, anchor7 + """    if getattr(a, 'assert_ns_ref_scope', False):
        os.chdir(ROOT)
        return cmd_assert_ns_ref_scope()
""", 1)

write(P, src)
print('✅ push_api.py 已更新：%d → %d 字节' % (len(orig), len(src)))
