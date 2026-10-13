# -*- coding: utf-8 -*-
import io, os, py_compile, tempfile
ROOT = os.getcwd(); P = os.path.join(ROOT, 'scripts', 'push_api.py')
def read(p):
    with io.open(p, encoding='utf-8') as fh: return fh.read()
def write(p, s):
    tmp = p + '.tmp160b'
    with io.open(tmp, 'w', encoding='utf-8') as fh: fh.write(s)
    if read(tmp) != s: raise SystemExit('读回不一致')
    py_compile.compile(tmp, cfile=tempfile.mktemp(), doraise=True)
    os.replace(tmp, p)
src = read(P)

# ① 探针改为**每次现场取活实现**（否则桩化后仍用捕获到的旧引用 → 判据⑧ 恒真）
old = """    def _probe(form, fn):
        src2 = 'def _f():\\n    return %s\\n' % form
        try:
            t2 = ast.parse(src2)
        except SyntaxError:
            return None
        got = set()
        for n in ast.walk(t2):
            got |= fn(n)
        return 'X' in got
"""
new = """    def _probe(form, key):
        \"\"\"🔑 每次**现场**取活实现（不复用捕获到的引用）——
        否则把实现桩成恒返回空后，探针仍用旧引用 → 判据⑧ 恒真。\"\"\"
        fn = globals().get(key)
        if not callable(fn):
            return None
        src2 = 'def _f():\\n    return %s\\n' % form
        try:
            t2 = ast.parse(src2)
        except SyntaxError:
            return None
        got = set()
        for n in ast.walk(t2):
            got |= fn(n)
        return 'X' in got
"""
assert src.count(old) == 1
src = src.replace(old, new, 1)
src = src.replace("            real = _probe(form, fn_ns)\n            old = _probe(form, fn_ct) if fn_ct is not None else None\n",
                  "            real = _probe(form, ns_key)\n            old = _probe(form, ct_name) if isinstance(ct_name, str) else None\n", 2)

# ② 判据⑧ 改为行为反证：桩化后④ 的探针必须全部认不出
old8 = """    # ⑧ 桩化（恒返回空）→ 必须拒绝给结论
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
"""
new8 = """    # ⑧ 桩化（恒返回空）→ ④ 的探针必须**全部认不出**（证明它真调活实现）
    if isinstance(ns_key, str) and fn_ns is not None:
        saved = globals().get(ns_key)
        globals()[ns_key] = lambda node: set()
        try:
            missed = [f for f in forms if _probe(f, ns_key) is not True]
            print('⑧ 桩化（恒返回空）后命名空间形态认不出的: %d/%d'
                  % (len(missed), len(forms)))
            if len(missed) != len(forms):
                bad.append('⑧ 唯一实现被桩成恒返回空后，④ 的探针仍认得出 —— '
                           '探针没真调用活实现（复用捕获引用），判据恒真')
        finally:
            globals()[ns_key] = saved
"""
assert src.count(old8) == 1
src = src.replace(old8, new8, 1)
write(P, src)
print('✅ 已修 ⑧')
