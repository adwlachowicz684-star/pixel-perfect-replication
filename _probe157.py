# -*- coding: utf-8 -*-
"""第一百五十七轮：探测 G443/G444 对各种**退化形态**的反应。

🔴 156 轮诚实结论②：反证形态只有 A/B/C 三种，
   「只认写方法但认错环节」等**其它退化形态未覆盖**。
🔑 本脚本不改动任何源码，只构造退化实现并观察 G444 是否放行。
"""
import ast
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'scripts'))
import push_api as P  # noqa: E402

os.chdir(P.ROOT)

STEPS = P.WRITE_RETRY_STEPS
METHODS = set(P.WRITE_METHODS)
print('环节清单:', STEPS)
print('写方法:', sorted(METHODS))


def _scan_real(tree, steps):
    return P._write_step_scan(tree, steps)


def _bad_real(found, steps):
    return P._write_step_bad(found, steps)


# ---- 退化形态 D：只按 HTTP 方法匹配，**完全不看 URL 里的环节** ----
def _scan_D(tree, steps):
    """🔴 退化：任何写方法调用都算**所有**环节命中。"""
    found = {}
    for seg, _m in steps:
        found[seg] = {}
    for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            fn = getattr(node.func, 'id', None)
            if fn not in ('req', 'req_retry'):
                continue
            if not node.args:
                continue
            a0 = node.args[0]
            if isinstance(a0, ast.Constant) and a0.value in METHODS:
                for seg, _m in steps:
                    found[seg][fn] = found[seg].get(fn, 0) + 1
    return found


# ---- 退化形态 E：URL 只做**前缀**模糊匹配（'git/' 开头即命中所有环节）----
def _scan_E(tree, steps):
    """🔴 退化：URL 含 'git/' 就算命中**第一个**环节。"""
    found = {}
    first = steps[0][0] if steps else ''
    for seg, _m in steps:
        found[seg] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = getattr(node.func, 'id', None)
        if fn not in ('req', 'req_retry'):
            continue
        if not node.args:
            continue
        a0 = node.args[0]
        if isinstance(a0, ast.Constant) and a0.value in METHODS:
            url = ''
            for a in node.args[1:]:
                if isinstance(a, ast.BinOp):
                    for n in ast.walk(a):
                        if isinstance(n, ast.Constant) and isinstance(n.value, str):
                            if '/' in n.value:
                                url += n.value
            if 'git/' in url:
                found[first][fn] = found[first].get(fn, 0) + 1
    return found


# ---- 退化形态 F：bad_fn 只报**第一条**违规就返回 ----
def _bad_F(found, steps):
    """🔴 退化：只报第一条违规，其余被吞。"""
    all_bad = P._write_step_bad(found, steps)
    return all_bad[:1]


def run(tag, scan_fn, bad_fn):
    miss, covered, rows = P._write_proof_check(scan_fn, bad_fn, STEPS)
    print('')
    print('---- 形态 %s ----' % tag)
    print('覆盖=%d/%d · 未命中=%d' % (covered, len(STEPS), len(miss)))
    for r in rows:
        print('   %-20s %s 期望「%s」命中=%s 违规数=%d'
              % (r[0], r[1], r[2], r[3], r[4]))
    for m in miss[:4]:
        print('   🔴 miss:', m)
    return len(miss)


print(chr(10) + '=' * 70)
n_real = run('基线(真实实现)', _scan_real, _bad_real)
n_D = run('D 只按方法匹配不看 URL', _scan_D, _bad_real)
n_E = run('E git/ 前缀模糊归到首个环节', _scan_E, _bad_real)
n_F = run('F bad_fn 只报第一条', _scan_real, _bad_F)

print(chr(10) + '=' * 70)
print('未命中数：基线=%d · D=%d · E=%d · F=%d' % (n_real, n_D, n_E, n_F))
print('🔑 若某退化形态未命中数==0 → G444 **放行**（守不住）')
