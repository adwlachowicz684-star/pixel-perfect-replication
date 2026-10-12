import ast, os, re, sys, shutil, io
ROOT = os.path.dirname(os.path.abspath(__file__))
S = os.path.join(ROOT, 'scripts')
PA = os.path.join(S, 'push_api.py')
RA = os.path.join(S, 'run_all_gates.py')

for p in (PA, RA):
    shutil.copy(p, p + '.bak152')

src = open(PA, encoding='utf-8').read()

# ---------- 1) 先算出核心基建文件里"被引用但未覆盖"的常量（与 G440 同口径） ----------
CORE = ['push_api.py', 'run_all_gates.py', 'claim_verify.py', 'gate_chaos.py',
        'coverage_gate.py', 'license_gate.py', '_scan_cross_ref_consts.py',
        '_scan_value_root_cands.py']

def collect():
    refs = set(); grefs = set()
    for fn in sorted(os.listdir(S)):
        if not fn.endswith('.py'): continue
        try: t = ast.parse(open(os.path.join(S, fn), encoding='utf-8').read())
        except Exception: continue
        for n in ast.walk(t):
            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load): refs.add(n.id)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) \
               and n.func.attr == 'get' and isinstance(n.func.value, ast.Name) \
               and n.func.value.id == 'globals' and n.args \
               and isinstance(n.args[0], ast.Constant) and isinstance(n.args[0].value, str):
                grefs.add(n.args[0].value)
    assigned = []
    for fn in CORE:
        t = ast.parse(open(os.path.join(S, fn), encoding='utf-8').read())
        for node in t.body:
            names = []
            if isinstance(node, ast.Assign):
                for tg in node.targets:
                    if isinstance(tg, ast.Name): names.append(tg.id)
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                names.append(node.target.id)
            for name in names:
                if re.fullmatch(r'[A-Z][A-Z0-9_]*', name):
                    assigned.append((fn, name))
    return refs, grefs, assigned

refs, grefs, assigned = collect()
# 现有覆盖
m = re.search(r"DEPENDENT_NAMES = \{(.*?)\n\}", src, re.S)
dep_now = set(re.findall(r"^\s*'([A-Za-z_][A-Za-z0-9_]*)':", m.group(1), re.M))
m2 = re.search(r"PATH_CONST_ALLOW = \{(.*?)\n\}", src, re.S)
allow_now = set(re.findall(r"^\s*'([^']+)':", m2.group(1), re.M))
META = {'DEPENDENT_NAMES', 'DEPENDENT_NAMES_MIN', 'DEPENDENT_NAMES_REQUIRED',
        'PATH_CONST_ALLOW', 'PATH_CONST_ALLOW_MIN_REASON', 'CRITERIA_ROOTS_REQUIRED',
        'SELF_REGISTERED_META', 'CRITERIA_ROOTS_REQUIRED'}
need = []
for fn, name in assigned:
    if name in dep_now or name in META or f'{fn}::{name}' in allow_now: continue
    if name in refs or name in grefs:
        need.append((fn, name))
print('需豁免（被引用且未覆盖）:', len(need))

# ---------- 2) DEPENDENT_NAMES 新增登记项 ----------
anchor = "    'cmd_assert_cache_recheck_proof': ('fn', 'G439 反证全量覆盖的断言入口'),"
assert anchor in src
new_dep = anchor + """
    # 🔑 第一百五十二轮：G440（非路径常量**反向扫描**）依赖
    'CONST_SCAN_FILES': ('const', '反向扫描覆盖的核心基建文件清单（G440 依赖）'),
    'CONST_SCAN_MIN': ('const', '反向扫描常量数下限（桩化 → 拒绝给结论）'),
    'CONST_SCAN_FN': ('const', 'G440 唯一实现函数名登记项'),
    'CONST_SCAN_META_EXEMPT': ('const', '元项豁免名（SELF_REGISTERED_META 等，防递推）'),
"""
src = src.replace(anchor, new_dep, 1)

# ---------- 3) PATH_CONST_ALLOW 新增豁免 ----------
anchor2 = "    'tool_run.py::REGISTRY': 'tool_run 运行时工具注册表路径，非产物/台账路径',\n}"
assert anchor2 in src
lines = []
for fn, name in need:
    if name in ('ROOT', 'HERE', 'REPO_ROOT', 'PY'):
        reason = '路径根常量（非产物/台账路径；G440 反向扫描覆盖：删本条即暴露）'
    else:
        reason = '核心基建非登记表依赖项（G440 反向扫描覆盖：删本条即暴露）'
    lines.append(f"    '{fn}::{name}': '{reason}',")
add = "\n".join(lines)
src = src.replace(anchor2,
                  "    'tool_run.py::REGISTRY': 'tool_run 运行时工具注册表路径，非产物/台账路径',\n"
                  + add + "\n}", 1)

# ---------- 4) 常量块 ----------
anchor3 = "CACHE_PROOF_N = 64         # 反证**逐条覆盖**的条目上限（超 → 拒绝给结论）"
assert anchor3 in src
src = src.replace(anchor3, anchor3 + """
# ── 第一百五十二轮：G440（非路径常量的**反向扫描**）──
#    🔴 151 轮实测③：删 `CACHE_PROOF_N` 登记项 → G405/G406 **均 rc=0**。
#    🔑 真因：G406 只扫**路径**常量（os.path.join(ROOT/HERE,...) 形式），
#       非路径常量（CACHE_PROOF_N / CACHE_RECHECK_N / NET_RETRY_MAX …）
#       **被删登记无人发现** —— 151 轮诚实结论指名的真实缺口。
#    🔑 处置：把扫描面从"路径"扩到"核心基建文件里**被引用**的模块级大写常量"，
#       要求它们**必须仍在** DEPENDENT_NAMES 或 PATH_CONST_ALLOW 内。
CONST_SCAN_FILES = ('""" + "', '".join(CORE) + """')
CONST_SCAN_MIN = 100          # 扫描到的常量数下限（实现被桩化 → 拒绝给结论）
CONST_SCAN_FN = '_scan_ref_consts_bad'
CONST_SCAN_META_EXEMPT = ('SELF_REGISTERED_META', 'CRITERIA_ROOTS_REQUIRED')
""", 1)

# ---------- 5) helper + cmd ----------
anchor4 = "def cmd_assert_cache_recheck_proof():"
assert anchor4 in src
helper = '''def _scan_ref_consts_bad():
    """🔑 G440 **唯一实现**：反向扫描 —— 核心基建文件里**被引用**的模块级
    大写常量，必须仍在 DEPENDENT_NAMES 或 PATH_CONST_ALLOW 内。

    🔴 151 轮实测③：删 `CACHE_PROOF_N` 登记项 → G405/G406 **均 rc=0**。
       🔑 真因：G406 只扫**路径**常量（os.path.join(ROOT/HERE,...)），
          非路径常量被删登记**无人发现**（CACHE_PROOF_N / CACHE_RECHECK_N 等）。
    🔑 本函数把扫描面从"路径"扩到"核心基建文件里被引用的大写常量" ——
       "登记项被删"从此有了一条**不依赖路径形式**的反向守望者。
    """
    files = globals().get('CONST_SCAN_FILES')
    meta = globals().get('CONST_SCAN_META_EXEMPT') or ()
    if not files:
        return None, 'CONST_SCAN_FILES 未登记或为空 —— 拒绝给结论'
    dep = globals().get('DEPENDENT_NAMES') or {}
    allow = globals().get('PATH_CONST_ALLOW') or {}
    refs = set(); grefs = set()
    for fn in sorted(os.listdir(os.path.join(ROOT, 'scripts'))):
        if not fn.endswith('.py'): continue
        try:
            t = ast.parse(open(os.path.join(ROOT, 'scripts', fn), encoding='utf-8').read())
        except Exception:
            continue
        for n in ast.walk(t):
            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load):
                refs.add(n.id)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) \\
               and n.func.attr == 'get' and isinstance(n.func.value, ast.Name) \\
               and n.func.value.id == 'globals' and n.args \\
               and isinstance(n.args[0], ast.Constant) \\
               and isinstance(n.args[0].value, str):
                grefs.add(n.args[0].value)
    bad = []; scanned = 0
    for fn in files:
        p = os.path.join(ROOT, 'scripts', fn)
        if not os.path.exists(p):
            return None, f'CONST_SCAN_FILES 里的 {fn} 不存在 —— 拒绝给结论'
        t = ast.parse(open(p, encoding='utf-8').read())
        for node in t.body:
            names = []
            if isinstance(node, ast.Assign):
                for tg in node.targets:
                    if isinstance(tg, ast.Name): names.append(tg.id)
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                names.append(node.target.id)
            for name in names:
                if not re.fullmatch(r'[A-Z][A-Z0-9_]*', name): continue
                scanned += 1
                if name in dep or name in meta: continue
                if f'{fn}::{name}' in allow: continue
                if not (name in refs or name in grefs): continue
                bad.append((fn, name))
    return bad, scanned


def cmd_assert_const_covered():
    """🔑 G440：**非路径常量的反向扫描**（151 轮实测③ 的补偿）。"""
    print(u'\\U0001f511 **非路径常量反向扫描**（G440 · 151 轮实测③ 的补偿）')
    fn = globals().get('CONST_SCAN_FN')
    if not fn:
        print(u'\\U0001f534 CONST_SCAN_FN 未登记 —— 拒绝给结论')
        return 1
    impl = globals().get(fn)
    if impl is None:
        print(u'\\U0001f534 %s 不存在 —— 拒绝给结论' % fn)
        return 1
    bad, scanned = impl()
    if bad is None:
        print(u'\\U0001f534 %s' % scanned)
        return 1
    minc = globals().get('CONST_SCAN_MIN') or 0
    if scanned < minc:
        print(u'\\U0001f534 扫描到 %d 个常量 < 下限 %d —— 疑似桩化，拒绝给结论'
              % (scanned, minc))
        return 1
    if bad:
        for f, n in bad:
            print(u'   \\U0001f534 %s::%s 被引用但未登记也未豁免（登记项被删？）' % (f, n))
        print(u'\\U0001f534 守卫失效（G440）：%d 个未覆盖' % len(bad))
        return 1
    print(u'   \\u2705 扫描 %d 个常量，全部已登记或已豁免' % scanned)
    return 0


'''
src = src.replace(anchor4, helper + anchor4, 1)

# ---------- 6) argparse ----------
anchor5 = """    ap.add_argument('--assert-cache-recheck-proof', action='store_true',
                    help='G439：反证样本集**不得**与实现实际检查集合重合'
                         '（逐条各造一次篡改；150 轮判据⑦ 只造首/中/尾 3 条）')"""
assert anchor5 in src
src = src.replace(anchor5, anchor5 + """
    ap.add_argument('--assert-const-covered', action='store_true',
                    help='G440：非路径常量**反向扫描**（被引用的常量必须仍在'
                         '登记表/豁免表内；151 轮实测③ 删 CACHE_PROOF_N 无人发现）')""", 1)

# ---------- 7) dispatch ----------
anchor6 = "        return cmd_assert_cache_recheck_proof()"
assert anchor6 in src
src = src.replace(anchor6, anchor6 + """
    if getattr(a, 'assert_const_covered', False):
        return cmd_assert_const_covered()""", 1)

open(PA, 'w', encoding='utf-8').write(src)
print('push_api.py 已写入')

# ---------- 8) run_all_gates.py ----------
rsrc = open(RA, encoding='utf-8').read()
i = rsrc.index('("G439"')
j = rsrc.index('\n]', i)
g440 = '''
    # 🔑 第一百五十二轮：G440 —— **非路径常量的反向扫描**。
    #    🔴 151 轮实测③：删 `CACHE_PROOF_N` 登记项 → G405/G406 均 rc=0
    #       （G406 只扫路径常量，非路径常量被删登记无人发现）。
    ("G440", "**非路径常量反向扫描**（被引用的常量必须仍在登记表/豁免表内）",
     ["{py}", "{s}/push_api.py", "--assert-const-covered"], "hard",
     ["scripts/push_api.py"]),'''
rsrc = rsrc[:j] + g440 + rsrc[j:]

anchor7 = "'\\U0001f511 判据造的样本集必须与实现实际检查集合**独立**，否则反证是自我验证。'),"
assert anchor7 in rsrc
rsrc = rsrc.replace(anchor7, anchor7 + """
    # 🔑 第一百五十二轮：第十九组（151 轮实测③ 的补偿）
    ('G440', 'G406',
     'G406 只扫**路径**常量（os.path.join(ROOT/HERE,...) 形式）；'
     'G440 扫核心基建文件里**被引用**的模块级大写常量（不论是不是路径）。'
     '\\U0001f534 只留 G406 → 非路径常量（CACHE_PROOF_N / CACHE_RECHECK_N 等）'
     '被删登记无人发现（151 轮实测③ 已证）；'
     '只留 G440 → 缺少"新产物路径必须登记"的入口语义。'
     '\\U0001f511 登记项被删必须有一条**不依赖路径形式**的反向守望者。'),""", 1)
open(RA, 'w', encoding='utf-8').write(rsrc)
print('run_all_gates.py 已写入')
