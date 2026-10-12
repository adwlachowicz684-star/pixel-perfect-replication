# -*- coding: utf-8 -*-
"""第一百五十三轮破坏测试：G441 豁免结构化分类。

🔑 每个方向都做两件事：
   1) 破坏前后各验一次「破坏确已生效」（118 轮教训：恢复快照取早了会一起覆盖掉修改）
   2) 同状态下同时跑 G440 与 G441 —— 用「一绿一红」证明 G441 不是冗余
🔴 备份必须在**修改之后**取（118 轮实测：cp 恢复时把修改一起覆盖掉了）。
"""
import os, re, subprocess, sys

ROOT = os.path.dirname(os.path.abspath(__file__))
PA = os.path.join(ROOT, 'scripts', 'push_api.py')
BAK = os.path.join(ROOT, '.bak153_break_push_api.py')

results = []


def run(flag):
    r = subprocess.run([sys.executable, PA.replace(os.path.join(ROOT, 'scripts'), os.path.join(ROOT, 'scripts')),
                        flag], cwd=ROOT, capture_output=True, text=True, timeout=300)
    return r.returncode, (r.stdout + r.stderr)


def read():
    return open(PA, encoding='utf-8').read()


def write(s):
    open(PA, 'w', encoding='utf-8').write(s)


def case(name, mutate, expect441, note='', also440=False):
    src = read()
    open(BAK, 'w', encoding='utf-8').write(src)   # 🔑 修改**之后**取快照
    try:
        new, applied = mutate(src)
        if not applied:
            results.append((name, 'SKIP', 'SKIP', '破坏未生效（改不动）'))
            print('  ⚠️  %s —— 破坏未生效' % name)
            return
        # 回读核对：确认改动真落盘（144 轮：直写大文件会截断且不报错）
        # 🔴 顺序必须是「先写再读」—— 读在写之前只会读到原文件，判据恒失败
        write(new)
        back = read()
        if new != back:
            results.append((name, 'X', 'X', '回读不一致 —— 写入失败'))
            return
        rc441, o441 = run('--assert-const-exempt')
        rc440, _ = run('--assert-const-covered') if also440 else (None, '')
        ok = (rc441 == expect441)
        results.append((name, str(rc441), str(rc440) if also440 else '-',
                        ('OK' if ok else 'MISMATCH') + (' · ' + note if note else '')))
        print('  %s %s  G441 rc=%s%s%s' % ('✅' if ok else '🔴', name, rc441,
                                           (' · G440 rc=%s' % rc440) if also440 else '',
                                           '  ← ' + note if note else ''))
        if not ok:
            print('     ' + '\n     '.join(o441.strip().splitlines()[-6:]))
    finally:
        write(open(BAK, encoding='utf-8').read())


print('=' * 70)
print('第一百五十三轮 · G441 破坏测试')
print('=' * 70)

# ① 核心对照：把一条豁免的分类改成**未定义**的分类
def m1(s):
    a = "'push_api.py::HERE': 'PATH_ROOT: push_api 所在脚本目录，非产物或台账路径',"
    b = "'push_api.py::HERE': 'BOGUS_CAT_NOT_DEFINED: push_api 所在脚本目录',"
    return s.replace(a, b, 1), a in s
case('① 豁免分类未定义（核心对照）', m1, 1, 'G440 应仍 rc=0（它只看键在不在表内）', also440=True)

# ② 清空分类表
def m2(s):
    m = re.search(r'^CONST_SCAN_CATEGORIES = \{.*?^\}', s, re.S | re.M)
    if not m:
        return s, False
    return s[:m.start()] + 'CONST_SCAN_CATEGORIES = {}' + s[m.end():], True
case('② 分类表清空', m2, 1, '分类数下限')

# ③ 三条豁免说明改成同一字符串（批量指纹）
def m3(s):
    n = 0
    for k in ['push_api.py::OWNER', 'push_api.py::REPO', 'push_api.py::TOK']:
        m = re.search(r"^(\s*'%s': 'NET_CFG: )[^']*(',)" % re.escape(k), s, re.M)
        if m:
            s = s[:m.start()] + m.group(1) + '同上同上同上' + m.group(2) + s[m.end():]
            n += 1
    return s, n == 3
case('③ 同分类下 3 条说明雷同', m3, 1, '雷同上限 CONST_SCAN_SAME_DETAIL_MAX=2')

# ④ 分类定义改成「同上」（过短）
def m4(s):
    a = "    'PATH_ROOT': '指向仓库或脚本目录自身的路径根常量；它不指向产物或台账，因此不适用「产物路径必须登记」的语义。',"
    b = "    'PATH_ROOT': '同上',"
    return s.replace(a, b, 1), a in s
case('④ 分类定义过短', m4, 1, 'CATDEF_MIN=20')

# ⑤ 桩化实现（返回空）—— 行为反证应抓到
def m5(s):
    a = "    return bad, len(allow)\n"
    i = s.index('def _scan_const_exempt_bad():')
    j = s.index(a, i)
    return s[:j] + "    return [], len(allow)\n" + s[j + len(a):], True
case('⑤ 桩化实现', m5, 1, '判据⑥ 行为反证必须抓到（否则反证恒真）')

# ⑥ 豁免值去掉「分类: 」前缀（退回自由文本）
def m6(s):
    a = "'license_gate.py::TEMPLATE': 'OUTPUT_FMT: license_gate 的报告模板',"
    b = "'license_gate.py::TEMPLATE': 'license_gate 的报告模板（无分类前缀）',"
    return s.replace(a, b, 1), a in s
case('⑥ 豁免值无分类前缀', m6, 1, '自由文本一律拒绝')

# ⑦ 一致改名（实现/常量/登记项三处同步）—— 不应误报
def m7(s):
    n = 0
    for a, b in [("CONST_SCAN_EXEMPT_FN = '_scan_const_exempt_bad'",
                  "CONST_SCAN_EXEMPT_FN = '_scan_const_exempt_bad2'"),
                 ('def _scan_const_exempt_bad():', 'def _scan_const_exempt_bad2():'),
                 ("'_scan_const_exempt_bad': ('fn'", "'_scan_const_exempt_bad2': ('fn'")]:
        if a in s:
            s = s.replace(a, b, 1)
            n += 1
    return s, n == 3
case('⑦ 一致改名（不误报）', m7, 0, '三处同步改名应仍 rc=0')

print('-' * 70)
rc441, _ = run('--assert-const-exempt')
rc440, _ = run('--assert-const-covered')
print('恢复后：G441 rc=%s · G440 rc=%s' % (rc441, rc440))
print('-' * 70)
for n, a, b, st in results:
    print('%-34s G441=%-3s G440=%-3s %s' % (n, a, b, st))
