# -*- coding: utf-8 -*-
"""第一百五十七轮：G445 七方向破坏实验。

🔑 每个方向：备份 → 改 → 跑 G443/G444/G445 → 恢复 → **读回 md5 核对**
   （144 轮"静默截断"、155 轮"restore 只恢复一个文件"同款教训）。
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
print('基准 md5 =', MD5)


def md5_of(p):
    return hashlib.md5(io.open(p, 'rb').read()).hexdigest()


def run(flag):
    r = subprocess.run([sys.executable, os.path.join(HERE, 'scripts', 'push_api.py'),
                        flag], capture_output=True, text=True, timeout=300)
    return r.returncode


def write_atomic(p, s):
    """🔑 原子写 + 写后读回核对（144 轮静默截断的教训）。"""
    tmp = p + '.tmp157'
    with io.open(tmp, 'w', encoding='utf-8') as f:
        f.write(s)
    back = io.open(tmp, encoding='utf-8').read()
    if back != s:
        raise SystemExit('🔴 写回不一致 —— 拒绝继续（文件可能已损坏）')
    os.replace(tmp, p)


def restore():
    write_atomic(PA, ORIG)
    if md5_of(PA) != MD5:
        raise SystemExit('🔴 恢复后 md5 不一致 —— 拒绝继续')


def inject(code):
    """在 `if __name__ == '__main__':` 之前注入代码（覆盖模块级定义）。"""
    s = ORIG.replace(TAIL, '\n' + code + '\n' + TAIL, 1)
    if s == ORIG:
        raise SystemExit('🔴 注入点未命中')
    write_atomic(PA, s)


results = []


def case(tag, expect, mutate, flags=None):
    flags = flags or ('--assert-write-step-scan',
                      '--assert-write-step-proof',
                      '--assert-write-step-url')
    mutate()
    got = {}
    for fl in flags:
        got[fl] = run(fl)
    restore()
    line = '%-46s' % tag
    for fl in flags:
        line += ' | %s=%d' % (fl.replace('--assert-', ''), got[fl])
    ok = '✅' if all(got[fl] == expect.get(fl, 1) for fl in flags) else '🔴'
    print(line + '  ' + ok)
    results.append((tag, got, ok))
    return got


SCAN_ANY = '''

# 🔴 破坏：只按 HTTP 方法匹配，完全不看 URL —— 所有环节一视同仁
def _scan_any_break(tree, steps):
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
        for seg, _m in steps:
            out[seg][fn] = out[seg].get(fn, 0) + 1
    return out

_write_step_scan = _scan_any_break
'''

STUB = '''

# 🔴 破坏：唯一实现被换成恒"通过"的桩
def _stub_break(scan_fn, bad_fn, steps, foreign):
    return [], len(steps), []

_write_proof_url_check = _stub_break
'''

SCAN_HALF = '''

# 🔴 破坏：只有第一个环节真按 URL 匹配，其余按方法匹配
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

print(chr(10) + '=' * 100)
print('方向① **核心对照**：真实扫描退化成"只按方法不看 URL"')
print('   预期：G443=0（放行）· G444=0（放行）· G445=1（抓到）')
case('① 扫描退化成只按方法不看 URL',
     {'--assert-write-step-scan': 0, '--assert-write-step-proof': 0,
      '--assert-write-step-url': 1},
     lambda: inject(SCAN_ANY))

print(chr(10) + '方向② 唯一实现被换成恒通过的桩')
print('   预期：G445=1（判据④ 抓到）')
case('② 桩化 _write_proof_url_check',
     {'--assert-write-step-url': 1},
     lambda: inject(STUB), flags=('--assert-write-step-url',))

print(chr(10) + '方向③ 环节清单被清空')
print('   预期：G445=1（判据② 抓到）')
case('③ WRITE_RETRY_STEPS 清空',
     {'--assert-write-step-url': 1},
     lambda: inject('\n\nWRITE_RETRY_STEPS = ()\n'),
     flags=('--assert-write-step-url',))

print(chr(10) + '方向④ 对照点漂移：无关 URL 改成含 git/trees')
print('   预期：G445=1（判据⑥ 抓到）')


def m4():
    s = ORIG.replace("WRITE_PROOF_FOREIGN_URL = '/repos/o/r/merges'",
                     "WRITE_PROOF_FOREIGN_URL = '/git/trees/merges'")
    assert s != ORIG, 'm4'
    write_atomic(PA, s)


case('④ 无关 URL 改为含 git/trees',
     {'--assert-write-step-url': 1},
     m4, flags=('--assert-write-step-url',))

print(chr(10) + '方向⑤ **一致改名**（实现与常量同步改）')
print('   预期：G445=0（不得假阳性）')


def m5():
    s = ORIG.replace("WRITE_PROOF_URL_FN = '_write_proof_url_check'",
                     "WRITE_PROOF_URL_FN = '_write_proof_url_check2'")
    s = s.replace('def _write_proof_url_check(', 'def _write_proof_url_check2(')
    s = s.replace("'_write_proof_url_check': ('fn'",
                  "'_write_proof_url_check2': ('fn'")
    assert s != ORIG, 'm5'
    write_atomic(PA, s)


case('⑤ 一致改名 _write_proof_url_check → …_check2',
     {'--assert-write-step-url': 0},
     m5, flags=('--assert-write-step-url',))

print(chr(10) + '方向⑥ 常量值改掉（指向不存在的函数）')
print('   预期：G445=1（判据① 抓到）')


def m6():
    s = ORIG.replace("WRITE_PROOF_URL_FN = '_write_proof_url_check'",
                     "WRITE_PROOF_URL_FN = '_no_such_fn_157'")
    assert s != ORIG, 'm6'
    write_atomic(PA, s)


case('⑥ WRITE_PROOF_URL_FN 值改坏',
     {'--assert-write-step-url': 1},
     m6, flags=('--assert-write-step-url',))

print(chr(10) + '方向⑦ **判据被放宽**（覆盖数改为 ≥1）+ 半退化实现')
print('   预期：G445=0 放行 —— 🔴 证明"严格要求 == 条数"才是真在起作用的那条')


def m7():
    s = ORIG.replace('        if covered != n_seg:',
                     '        if covered < 1:')
    s = s.replace('        if miss:', '        if False and miss:')
    assert s != ORIG, 'm7'
    write_atomic(PA, s)
    inject2(s)


def inject2(base):
    s = base.replace(TAIL, '\n' + SCAN_HALF + '\n' + TAIL, 1)
    write_atomic(PA, s)


case('⑦ 判据放宽为覆盖≥1 + 只有首个环节真按 URL',
     {'--assert-write-step-url': 0},
     m7, flags=('--assert-write-step-url',))

print(chr(10) + '=' * 100)
print('基准 md5 复核:', md5_of(PA) == MD5, md5_of(PA))
bad = [t for t, _g, ok in results if ok == '🔴']
print('不符预期方向:', bad if bad else '无')
