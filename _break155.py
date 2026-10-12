# -*- coding: utf-8 -*-
"""第一百五十五轮：G443 对照实验 + 多方向破坏。

🔑 核心对照：同一状态（tree 环节同时有 req_retry 与**裸 req** 两处写调用）
   → 154 轮旧判据② **rc=0 放行**（集合里有 req_retry 就算过）
   → 155 轮新判据②（G442）/ G443 **rc=1 抓到**
"""
import ast
import hashlib
import io
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
PA = os.path.join(ROOT, 'scripts', 'push_api.py')
PY = sys.executable


def rd(p=PA):
    with io.open(p, encoding='utf-8') as f:
        return f.read()


def wr(s, p=PA):
    tmp = p + '.tmpb'
    with io.open(tmp, 'w', encoding='utf-8') as f:
        f.write(s)
    with io.open(tmp, encoding='utf-8') as f:
        back = f.read()
    if back != s:
        raise SystemExit('🔴 写回不一致（%d vs %d）' % (len(back), len(s)))
    os.replace(tmp, p)


def md5(s):
    return hashlib.md5(s.encode('utf-8')).hexdigest()


def run(flag):
    p = subprocess.run([PY, PA, flag], cwd=ROOT,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return p.returncode


def old_judge2(src, steps):
    """🔴 复刻 154 轮判据②：found[seg] 是函数名**集合**，只看有没有 req_retry。"""
    try:
        tree = ast.parse(src)
    except Exception:
        return ['无法解析']
    found = {}
    for sub in ast.walk(tree):
        if not isinstance(sub, ast.Call):
            continue
        fn = None
        if isinstance(sub.func, ast.Name):
            fn = sub.func.id
        if fn is None and isinstance(sub.func, ast.Attribute):
            fn = sub.func.attr
        if fn is None:
            continue
        blob = ast.dump(sub)
        for seg, _m in steps:
            if seg in blob:
                found.setdefault(seg, set()).add(fn)
    bad = []
    for seg, _m in steps:
        fns = found.get(seg)
        if not fns:
            bad.append('环节 %s：找不到对应调用' % seg)
            continue
        if 'req_retry' not in fns:
            bad.append('环节 %s 裸调 %s' % (seg, sorted(fns)))
    return bad


STEPS = (('git/blobs', 'POST'), ('git/trees', 'POST'),
         ('git/commits', 'POST'), ('git/refs/heads/main', 'PATCH'))

BASE = rd()
BASE_MD5 = md5(BASE)
rows = []


def case(tag, mutate, expect, note):
    """mutate(src) -> new_src；expect 为 {'G442': rc, 'G443': rc} 期望值"""
    src = rd()
    if md5(src) != BASE_MD5:
        print('🔴 [%s] 起点不是基准态，先恢复' % tag)
        wr(BASE)
        src = BASE
    new = mutate(src)
    if new == src:
        print('🔴 [%s] 改动未生效（mutate 返回原串）' % tag)
        rows.append((tag, 'NA', 'NA', 'NA', '改动未生效'))
        return
    wr(new)
    got = {}
    for name, flag in (('G442', '--assert-write-retry'),
                       ('G443', '--assert-write-step-scan')):
        got[name] = run(flag)
    # 旧逻辑（154 轮判据②）在同一状态下的表现
    old_bad = old_judge2(rd(), STEPS)
    old_rc = 1 if old_bad else 0
    wr(BASE)
    ok = md5(rd()) == BASE_MD5
    res = all(got[k] == v for k, v in expect.items())
    rows.append((tag, got.get('G442'), got.get('G443'), old_rc,
                 'OK' if res and ok else 'FAIL'))
    print('%-4s G442=%s G443=%s 旧判据②=%s 期望=%s → %s%s'
          % (tag, got.get('G442'), got.get('G443'), old_rc, expect,
             '符合' if res else '不符',
             '' if ok else ' 🔴恢复失败'))
    print('      %s' % note)


def append_fn(src, body):
    return src + '\n\n' + body + '\n'


# ① 核心对照：tree 环节新增一处**裸 req** 写调用（原有 req_retry 那行仍在）
case('①', lambda s: append_fn(s, "def _shadow_tree_write():\n"
                                 "    return req('POST', API + '/git/trees',"
                                 " {'tree': []})\n"),
     {'G442': 1, 'G443': 0},
     '🔑 154 轮旧判据② 应 rc=0（被另一处 req_retry 掩盖），新判据② rc=1')

# ② GET 的 req_retry + POST 的裸 req —— 旧判据不认方法
case('②', lambda s: append_fn(s, "def _shadow_tree_mixed():\n"
                                 "    req_retry('GET', API + '/git/trees', None)\n"
                                 "    return req('POST', API + '/git/trees',"
                                 " {'tree': []})\n"),
     {'G442': 1, 'G443': 0},
     '🔑 旧判据② 因 GET 走 req_retry 而放行；新判据只看写方法')

# ③ append 之类无关调用不得充当写环节
case('③', lambda s: append_fn(s, "def _shadow_append():\n"
                                 "    lst = []\n"
                                 "    lst.append('git/commits')\n"
                                 "    return lst\n"),
     {'G442': 0, 'G443': 0},
     '无关调用不应被当成写环节（不误报）')

# ④ 删 WRITE_RETRY_STEPS 中一条 → 判据⑥ 反向扫描必须抓到
def del_step(s):
    # 🔑 带下一行上下文：另一处反向扫描的元组缩进不同，只有这里唯一
    old = ("    ('git/commits', 'POST'),\n"
           "    ('git/refs/heads/main', 'PATCH'),\n")
    assert s.count(old) == 1, s.count(old)
    return s.replace(old, "    ('git/refs/heads/main', 'PATCH'),\n")


case('④', del_step, {'G442': 1, 'G443': 0},
     '🔴 删清单一条 → 该环节静默失去守护（154 轮破坏⑦ 同款）')

# ⑤ G443 判据② 被改成"有 req_retry 就放行" → G443 必须抓到，而 G442 仍绿
def weaken_bad(s):
    old = "        if c.get('req', 0) > 0:"
    assert s.count(old) == 1
    return s.replace(old, "        if False and c.get('req', 0) > 0:")


case('⑤', weaken_bad, {'G442': 0, 'G443': 1},
     '🔑 同一状态一绿一红：G442 看不见自己的判据被削弱')

# ⑥ WRITE_METHODS 放进 GET → 判据④（只有 GET 也算写调用）应失败
def add_get(s):
    old = "WRITE_METHODS = ('POST', 'PATCH', 'PUT', 'DELETE')"
    assert s.count(old) == 1
    return s.replace(old, "WRITE_METHODS = ('POST', 'PATCH', 'PUT', 'DELETE',"
                          " 'GET')")


case('⑥', add_get, {'G442': 1, 'G443': 1},
     '🔑 GET 被当写方法 → 读调用会顶替写调用；G442 也报（真实源码有 GET 读调用）'
     ' · G443 靠判据④ 抓到，非独立贡献')

# ⑦ G442 判据② 改回内联旧写法（不再调唯一实现）→ G443 判据① b) 抓到
def inline_back(s):
    old = "    found = _write_step_scan(tree, steps)"
    assert s.count(old) == 1
    return s.replace(old, "    found = {}")


case('⑦', inline_back, {'G442': 1, 'G443': 1},
     '各写一份 → G442 判"找不到"、G443 判"未调唯一实现"（两条都不许静默）')

print()
print('=' * 74)
print('%-4s %-6s %-6s %-10s %s' % ('方向', 'G442', 'G443', '旧判据②', '结论'))
for tag, a, b, c, r in rows:
    print('%-4s %-6s %-6s %-10s %s' % (tag, a, b, c, r))
print('=' * 74)
print('基准 md5 一致: %s' % (md5(rd()) == BASE_MD5))
