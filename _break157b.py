# -*- coding: utf-8 -*-
"""第一百五十七轮方向⑦（修正版）：证明「覆盖数必须 == 清单条数」才是真在起作用那条。

🔑 半退化实现：只对 steps[0] 真按 URL 匹配，其余环节按方法匹配（不看 URL）。
   → G445 口径下 covered=1（只有首个环节正确）
   → 严格判据（covered != n_seg）报 rc=1；放宽成 covered < 1 后 rc=0 放行。
"""
import hashlib
import io
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PA = os.path.join(HERE, 'scripts', 'push_api.py')
TAIL = "\nif __name__ == '__main__':\n"
ORIG = io.open(PA, encoding='utf-8').read()
MD5 = hashlib.md5(ORIG.encode('utf-8')).hexdigest()


def md5_of(p):
    return hashlib.md5(io.open(p, 'rb').read()).hexdigest()


def write_atomic(p, s):
    tmp = p + '.tmp157'
    with io.open(tmp, 'w', encoding='utf-8') as f:
        f.write(s)
    if io.open(tmp, encoding='utf-8').read() != s:
        raise SystemExit('写回不一致')
    os.replace(tmp, p)


def restore():
    write_atomic(PA, ORIG)
    assert md5_of(PA) == MD5, '恢复失败'


def run(flag):
    r = subprocess.run([sys.executable, PA, flag], capture_output=True,
                       text=True, timeout=300)
    return r.returncode


SCAN_HALF = '''

# 🔴 半退化：只对 steps[0] 真按 URL 匹配，其余环节按方法匹配（不看 URL）
def _scan_half_break(tree, steps):
    out = {}
    for seg, _m in steps:
        out[seg] = {}
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
        blob = ast.dump(sub)
        first = steps[0][0]
        if first in blob:
            out[first][fn] = out[first].get(fn, 0) + 1
        else:
            for seg, _m in steps:
                if seg == first:
                    continue
                out[seg][fn] = out[seg].get(fn, 0) + 1
    return out

_write_step_scan = _scan_half_break
'''


def with_half(also_relax=False):
    s = ORIG
    if also_relax:
        s = s.replace('        if covered != n_seg:',
                      '        if covered < 1:')
        s = s.replace('        if miss:', '        if False and miss:')
        assert s != ORIG, 'relax 未命中'
    s = s.replace(TAIL, '\n' + SCAN_HALF + '\n' + TAIL, 1)
    assert TAIL in s
    write_atomic(PA, s)


print('基准 md5 =', MD5)
print()
print('【A】半退化 + **严格**判据（原实现） —— 预期 rc=1')
with_half(False)
ra = run('--assert-write-step-url')
print('   G445 rc =', ra)
restore()

print()
print('【B】半退化 + 判据放宽成「覆盖 ≥1 即可、忽略 miss」 —— 预期 rc=0 🔴')
with_half(True)
rb = run('--assert-write-step-url')
print('   G445 rc =', rb)
restore()

print()
print('基准 md5 复核:', md5_of(PA) == MD5)
print('结论：严格=%d · 放宽=%d → %s'
      % (ra, rb, '✅ 起作用的是「覆盖数必须 == 条数」' if (ra, rb) == (1, 0) else '🔴 不符预期'))
