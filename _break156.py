"""第一百五十六轮：G444 七方向破坏实验（含核心对照）。

🔑 每方向：备份 → 改坏 → 跑门禁 → 记录 → 恢复 → 核验 md5
🔴 吸取 144 / 155 轮教训：原子写 + 读回核对 + 语法检查 + 恢复后 md5 比对
"""
import hashlib
import io
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
API = os.path.join(ROOT, 'scripts', 'push_api.py')
BAK = os.path.join(ROOT, '_bak156_good.py')
LOG = []


def rd(p):
    with io.open(p, encoding='utf-8') as f:
        return f.read()


def w_atomic(p, s):
    tmp = p + '.tmpb'
    with io.open(tmp, 'w', encoding='utf-8') as f:
        f.write(s)
    back = rd(tmp)
    if back != s:
        os.remove(tmp)
        raise SystemExit('🔴 读回不一致')
    os.replace(tmp, p)


def md5(p):
    return hashlib.md5(rd(p).encode('utf-8')).hexdigest()


def run(flag, timeout=150):
    try:
        r = subprocess.run(
            [sys.executable, os.path.join(ROOT, 'scripts', 'push_api.py'), flag],
            capture_output=True, text=True, timeout=timeout, cwd=ROOT)
        return r.returncode, (r.stdout or '') + (r.stderr or '')
    except subprocess.TimeoutExpired:
        return 'TIMEOUT', ''


def sanity(flag='--assert-write-step-proof'):
    """基线自检：改坏之前先确认是绿的。"""
    rc, _ = run(flag)
    return rc


def sub1(src, old, new, tag):
    if old not in src:
        raise SystemExit('🔴 [%s] 找不到片段: %r' % (tag, old[:60]))
    return src.replace(old, new, 1)


def case(tag, mutate, flags, expect):
    """expect: {flag: 期望 rc}；跑完恢复。"""
    base = md5(API)
    src = rd(API)
    try:
        w_atomic(API, mutate(src))
    except SystemExit as e:
        print('  🔴 [%s] 改坏失败: %s' % (tag, e))
        return False
    ok = True
    got = {}
    for f in flags:
        rc, out = run(f)
        got[f] = rc
        want = expect[f]
        mark = '✅' if rc == want else '❌'
        if rc != want:
            ok = False
        firstbad = ''
        for line in out.splitlines():
            if line.strip().startswith('🔴'):
                firstbad = line.strip()[:110]
                break
        print('  %s [%s] %s rc=%s (期望 %s) %s' % (mark, tag, f, rc, want, firstbad))
    w_atomic(API, src)
    same = md5(API) == base
    print('     ↳ 恢复后 md5 一致: %s' % same)
    if not same:
        ok = False
    LOG.append((tag, ok, got, expect))
    return ok


def main():
    if not os.path.exists(BAK):
        w_atomic(BAK, rd(API))
    base_md5 = md5(API)
    print('基准 md5 =', base_md5)
    rc0 = sanity()
    print('基线 G444 rc =', rc0)
    if rc0 != 0:
        raise SystemExit('🔴 基线不是绿的，拒绝做破坏实验')

    # ① 核心对照：扫描退化成只认 git/trees —— G443 放行 / G444 抓到
    def m1(s):
        return sub1(s, "        for seg, _m in steps:\n            if seg in blob:",
                    "        for seg, _m in steps:\n"
                    "            if seg != 'git/trees':\n"
                    "                continue\n"
                    "            if seg in blob:", '①')

    case('① 扫描只认 git/trees（核心对照）', m1,
         ['--assert-write-step-scan', '--assert-write-step-proof'],
         {'--assert-write-step-scan': 0, '--assert-write-step-proof': 1})

    # ② 扫描换成恒空桩
    def m2(s):
        return sub1(s, "    found = {}\n    if tree is None:\n        return found",
                    "    found = {}\n    return found\n    if tree is None:\n        return found", '②')

    case('② 扫描恒空桩', m2,
         ['--assert-write-step-proof', '--assert-write-retry'],
         {'--assert-write-step-proof': 1, '--assert-write-retry': 1})

    # ③ 环节清单缩到 1 条
    def m3(s):
        old = ("WRITE_RETRY_STEPS = (\n    ('git/blobs', 'POST'),\n"
               "    ('git/trees', 'POST'),\n    ('git/commits', 'POST'),\n"
               "    ('git/refs/heads/main', 'PATCH'),\n)")
        new = "WRITE_RETRY_STEPS = (\n    ('git/trees', 'POST'),\n)"
        return sub1(s, old, new, '③')

    case('③ 清单缩到 1 条', m3, ['--assert-write-step-proof'],
         {'--assert-write-step-proof': 1})

    # ④ 对照点漂移
    def m4(s):
        return sub1(s, "WRITE_LEGACY_PROOF_SEG = 'git/trees'",
                    "WRITE_LEGACY_PROOF_SEG = 'git/nonexist'", '④')

    case('④ 对照点改成不存在的环节', m4, ['--assert-write-step-proof'],
         {'--assert-write-step-proof': 1})

    # ⑤ 桩化 _write_proof_check（恒返回"无未命中 + 全覆盖"）
    def m5(s):
        return sub1(s, "    miss = []\n    rows = []\n    if scan_fn is None",
                    "    miss = []\n    rows = []\n"
                    "    return miss, len(steps or ()), rows\n"
                    "    if scan_fn is None", '⑤')

    case('⑤ 桩化唯一实现（恒绿）', m5, ['--assert-write-step-proof'],
         {'--assert-write-step-proof': 1})

    # ⑥ 一致改名（不误报）
    def m6(s):
        s = sub1(s, 'def _write_proof_check(scan_fn', 'def _write_proof_check2(scan_fn', '⑥a')
        s = sub1(s, "WRITE_PROOF_FN = '_write_proof_check'",
                 "WRITE_PROOF_FN = '_write_proof_check2'", '⑥b')
        s = sub1(s, "    '_write_proof_check': ('fn'",
                 "    '_write_proof_check2': ('fn'", '⑥c')
        return s

    case('⑥ 一致改名（不得假阳性）', m6, ['--assert-write-step-proof'],
         {'--assert-write-step-proof': 0})

    # ⑦ 形态数缩水（A/B/C → 只剩 A）
    def m7(s):
        return sub1(s, "        seg_ok = True\n"
                       "        # 🔑 形态数必须**真查**",
                    "        snips = snips[:1]\n        seg_ok = True\n"
                       "        # 🔑 形态数必须**真查**", '⑦')

    case('⑦ 反证形态缩到 1 种', m7, ['--assert-write-step-proof'],
         {'--assert-write-step-proof': 1})

    print()
    print('=' * 70)
    allok = True
    for tag, ok, got, expect in LOG:
        print('  %s %s  got=%s' % ('✅' if ok else '❌', tag, got))
        allok = allok and ok
    print('最终 md5 一致: %s' % (md5(API) == base_md5))
    print('七方向全部符合预期: %s' % allok)
    return 0 if allok else 1


if __name__ == '__main__':
    sys.exit(main())
