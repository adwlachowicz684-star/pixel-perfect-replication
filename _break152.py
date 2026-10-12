import os, re, shutil, subprocess, sys
ROOT = os.path.dirname(os.path.abspath(__file__))
PA = os.path.join(ROOT, 'scripts', 'push_api.py')
BAK = PA + '.bak152run'

def run(flag):
    r = subprocess.run([sys.executable, 'scripts/push_api.py', flag],
                       cwd=ROOT, capture_output=True, text=True)
    return r.returncode

def fresh():
    shutil.copy(PA, BAK)

def restore():
    shutil.copy(BAK, PA)

def edit(fn):
    s = open(PA, encoding='utf-8').read()
    s2 = fn(s)
    assert s2 != s, '修改未生效（needle 未命中）'
    open(PA, 'w', encoding='utf-8').write(s2)

def rm_line(pat):
    def f(s):
        return re.sub(r'^.*' + pat + r'.*\n', '', s, count=1, flags=re.M)
    return f

def sub(old, new, cnt=1):
    def f(s):
        assert old in s, old[:40]
        return s.replace(old, new, cnt)
    return f

rows = []
def case(name, fn, flags=('assert-const-covered',)):
    fresh()
    edit(fn)
    got = {}
    for fl in flags:
        got[fl] = run('--' + fl.replace('_', '-'))
    restore()
    rows.append((name, got))

HELPER_ANCHOR = "    files = globals().get('CONST_SCAN_FILES')"

# ① 删 CACHE_PROOF_N 登记项（非路径常量）—— 核心对照
case('① 删 CACHE_PROOF_N 登记项',
     rm_line(r"'CACHE_PROOF_N': \('const'"),
     flags=('assert-const-covered', 'assert-dependent-names', 'assert-path-consts'))

# ② 桩化 helper（返回空 + scanned=0）
def stub(s):
    i = s.index('def _scan_ref_consts_bad():')
    j = s.index(HELPER_ANCHOR, i)
    return s[:j] + "    return [], 0\n" + s[j:]
case('② 桩化 _scan_ref_consts_bad（返回 ([],0)）', stub)

# ③ 新增未登记且被引用的大写常量
def addnew(s):
    return s + "\nNEW_UNREG_CONST_152 = 1\n_X152_USE = NEW_UNREG_CONST_152\n"
case('③ 新增未登记大写常量 NEW_UNREG_CONST_152', addnew)

# ④ 桩化 + CONST_SCAN_MIN=0（下限判据被去掉 → 应放行，证明②里起作用的是 min）
def stub_and_min0(s):
    s = stub(s)
    return s.replace('CONST_SCAN_MIN = 100', 'CONST_SCAN_MIN = 0', 1)
case('④ ②+CONST_SCAN_MIN=0（下限判据被拆）', stub_and_min0)

# ⑤ 一致改名
def ren(s):
    s = s.replace('_scan_ref_consts_bad', '_scan_ref_consts_bad2')
    s = s.replace("'_scan_ref_consts_bad2': ('fn'", "'_scan_ref_consts_bad2': ('fn'")
    return s
case('⑤ 一致改名 _scan_ref_consts_bad→…_bad2', ren)

# ⑥ 删 CONST_SCAN_FILES 登记项（非路径常量登记项被删）
case('⑥ 删 CONST_SCAN_FILES 登记项',
     rm_line(r"'CONST_SCAN_FILES': \('const'"))

print('%-46s %s' % ('方向', '各门禁 rc'))
for name, got in rows:
    print('%-46s %s' % (name, ' '.join(f'{k.split("-")[-1]}={v}' for k, v in got.items())))
print()
print('期望：① G440=1 且 G405=0 G406=0（核心对照）；②=1；③=1；④=0；⑤=0；⑥=1')
