# -*- coding: utf-8 -*-
"""第一百五十四轮：G442 七方向破坏实验。

🔑 每条都：备份 → 破坏 → 读回核对破坏真生效 → 跑门禁 → 恢复 → 读回核对恢复。
🔴 153 轮教训：restore() 必须在 write() **之后**读快照（118 轮同款第二次）。
🔴 144 轮教训：大文件必须**原子写 + 写完读回核对**，否则静默截断。
"""
import io
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
PA = os.path.join(ROOT, 'scripts', 'push_api.py')
PY = sys.executable


def read():
    return io.open(PA, encoding='utf-8').read()


def atomic_write(txt):
    tmp = PA + '.tmp154'
    with io.open(tmp, 'w', encoding='utf-8') as f:
        f.write(txt)
        f.flush()
        os.fsync(f.fileno())
    got = io.open(tmp, encoding='utf-8').read()
    assert got == txt, '❌ 写入后读回不一致（静默截断？）'
    os.replace(tmp, PA)
    assert read() == txt, '❌ replace 后读回不一致'


def run(flag):
    p = subprocess.run([PY, PA, flag], capture_output=True,
                       text=True, timeout=300)
    return p.returncode, (p.stdout or '') + (p.stderr or '')


def case(name, mutate, flag, expect, also=None):
    """also: [(flag, expect), ...] 同时跑的对照门禁"""
    global SRC
    base = SRC
    new = mutate(base)
    if new == base:
        print(f'  ❌ {name}: 破坏**没有生效**（文本未变）—— 该方向无效')
        return False
    atomic_write(new)
    assert read() == new, '❌ 破坏态读回不一致'
    rc, out = run(flag)
    ok = (rc != 0) if expect == 1 else (rc == 0)
    print(f'  {"✅" if ok else "❌"} {name}: {flag} rc={rc} (期望'
          f'{"非0" if expect == 1 else "0"})')
    if not ok:
        print('    ---- 输出 ----')
        for ln in out.strip().splitlines()[-14:]:
            print('    ', ln)
    res = [ok]
    # 破坏态下的对照门禁（证明"谁守不住"）
    for f2, e2 in (also or []):
        rc2, out2 = run(f2)
        ok2 = (rc2 != 0) if e2 == 1 else (rc2 == 0)
        print(f'      {"✅" if ok2 else "❌"} 对照 {f2}: rc={rc2} '
              f'(期望{"非0" if e2 == 1 else "0"})')
        res.append(ok2)
    atomic_write(base)
    assert read() == base, '❌ 恢复后读回不一致'
    rc_r, _ = run(flag)
    print(f'      恢复后 {flag} rc={rc_r}')
    res.append(rc_r == 0)
    return all(res)


SRC = read()
shutil.copy(PA, os.path.join(ROOT, '.bak154_pre_break'))
results = {}

print('🔴 第一百五十四轮：G442 七方向破坏实验')
print('=' * 70)


# ① 核心对照：tree 环节改回裸 req（还原 153 轮形态）
def m1(s):
    return s.replace(
        "    t = req_retry('POST', f'{API}/git/trees', {'tree': tree})",
        "    t = req('POST', f'{API}/git/trees', {'tree': tree})", 1)


results['① tree 改回裸 req（153 轮形态）'] = case(
    '① tree 改回裸 req', m1, '--assert-write-retry', 1,
    also=[('--assert-blob-retry', 0)])


# ② 清空环节清单 → 判据① 必须拒绝（防恒真）
def m2(s):
    return s.replace(
        "WRITE_RETRY_STEPS = (\n    ('git/blobs', 'POST'),\n"
        "    ('git/trees', 'POST'),\n"
        "    ('git/commits', 'POST'),\n"
        "    ('git/refs/heads/main', 'PATCH'),\n)",
        "WRITE_RETRY_STEPS = ()", 1)


results['② 清空 WRITE_RETRY_STEPS'] = case(
    '② 清空环节清单', m2, '--assert-write-retry', 1)


# ③ 桩化 req_retry（恒返回成功）→ 行为反证必须抓到
def m3(s):
    return s.replace(
        "def req_retry(method, url, payload=None):",
        "def req_retry(method, url, payload=None):\n"
        "    return {'sha': '0' * 40}", 1)


results['③ 桩化 req_retry'] = case(
    '③ 桩化 req_retry', m3, '--assert-write-retry', 1)


# ④ 一致改名（代码 + 登记 + 判据同步）→ 不得误报
def m4(s):
    return (s.replace('req_retry', 'req_retry_v2')
             .replace("'req_retry': ('fn'", "'req_retry_v2': ('fn'"))


results['④ 一致改名不误报'] = case(
    '④ 一致改名', m4, '--assert-write-retry', 0)


# ⑤ _blob_retryable 无差别 True → 403 会被重试多次 → 判据④ 抓到
def m5(s):
    return s.replace(
        "    if isinstance(err, int):\n        return 500 <= err < 600",
        "    if isinstance(err, int):\n        return True", 1)


results['⑤ 无差别重试（4xx 也重试）'] = case(
    '⑤ 无差别重试', m5, '--assert-write-retry', 1)


# ⑥ 自测抄一份（不调用真实 req_retry）→ 判据⑤ 抓到
def m6(s):
    return s.replace(
        "        r = req_retry('POST', f'{API}/git/trees', {'tree': []})",
        "        r = ({'sha': '0' * 40} if len(calls) > 2 "
        "else {'__err': 503})", 1)


results['⑥ 自测抄一份（自证循环）'] = case(
    '⑥ 自测抄一份', m6, '--assert-write-retry', 1)


# ⑦ 只删 commits 环节（缺一个环节）→ 必须报
def m7(s):
    return s.replace(
        "    ('git/commits', 'POST'),\n", "", 1)


results['⑦ 删 commits 环节'] = case(
    '⑦ 删一个环节', m7, '--assert-write-retry', 1)


print('=' * 70)
bad = [k for k, v in results.items() if not v]
for k, v in results.items():
    print(f'  {"✅" if v else "❌"} {k}')
print('=' * 70)
print('❌ 不符预期: ' + (', '.join(bad) if bad else '无'))
