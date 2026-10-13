# -*- coding: utf-8 -*-
"""第一百六十轮：G448 七方向破坏实验"""
import hashlib, io, os, subprocess, sys, time

ROOT = os.getcwd()
P = os.path.join(ROOT, 'scripts', 'push_api.py')

def read(p):
    with io.open(p, encoding='utf-8') as f: return f.read()
def write(p, s):
    with io.open(p, 'w', encoding='utf-8') as f: f.write(s)
    if read(p) != s: raise SystemExit('🔴 读回不一致')

base = read(P)
md5 = hashlib.md5(base.encode('utf-8')).hexdigest()

def run(*args, t=240):
    try:
        r = subprocess.run([sys.executable] + list(args), cwd=ROOT,
                           capture_output=True, text=True, timeout=t)
        return r.returncode
    except subprocess.TimeoutExpired:
        return 'TIMEOUT'

def case(name, repl, gates):
    old, new = repl
    assert base.count(old) >= 1, '锚点缺失: %s' % name
    write(P, base.replace(old, new, 1))
    time.sleep(0.2)
    res = {g: run('scripts/push_api.py', '--' + g) for g in gates}
    write(P, base)
    assert hashlib.md5(read(P).encode('utf-8')).hexdigest() == md5, '恢复失败'
    return res

CASES = [
 ('① 核心对照：引用计数改回宽口径 _call_target_name',
  ('                grefs |= _ns_ref_names(n)',
   '                grefs |= _call_target_name(n)'),
  ['assert-ns-ref-scope', 'assert-const-covered']),
 ('② 调用后丢弃结果',
  ('                grefs |= _ns_ref_names(n)',
   '                _ns_ref_names(n)'),
  ['assert-ns-ref-scope']),
 ('③ 桩化唯一实现（恒返回空）',
  ('    names = set()\n    nsf = tuple(globals().get(\'NS_FNS\') or ())\n    if not nsf:\n        return names',
   '    return set()\n    names = set()\n    nsf = tuple(globals().get(\'NS_FNS\') or ())\n    if not nsf:\n        return names'),
  ['assert-ns-ref-scope']),
 ('④ 命名空间形态表缩到 2 条',
  ('NS_REF_FORMS = ("globals()[\'X\']", "locals()[\'X\']", "vars()[\'X\']",\n                "globals().get(\'X\')", "locals().get(\'X\')", "vars().get(\'X\')",\n                "getattr(globals(), \'X\')")',
   'NS_REF_FORMS = ("globals()[\'X\']", "locals()[\'X\']")'),
  ['assert-ns-ref-scope']),
 ('⑤ 噪声形态表缩到 1 条',
  ('NS_REF_NOISE_FORMS = ("cfg[\'X\']", "cfg.get(\'X\')", "d[\'X\']", "d.get(\'X\')",\n                      "getattr(obj, \'X\')", "self.cfg[\'X\']")',
   'NS_REF_NOISE_FORMS = ("cfg[\'X\']",)'),
  ['assert-ns-ref-scope']),
 ('⑥ 一致改名 _ns_ref_names → _ns_ref_names_v2（应不误报）',
  ('_ns_ref_names', '_ns_ref_names_v2'),
  ['assert-ns-ref-scope']),
 ('⑦ 噪声形态混进命名空间形态表',
  ('                "getattr(globals(), \'X\')")',
   '                "getattr(globals(), \'X\')", "cfg[\'X\']")'),
  ['assert-ns-ref-scope']),
 ('⑧ 删 NS_REF_USERS 条目（清单清空）',
  ('NS_REF_USERS = (\'_scan_ref_consts_bad\',)', 'NS_REF_USERS = ()'),
  ['assert-ns-ref-scope']),
]

print('破坏实验基线 md5 =', md5[:12])
for name, repl, gates in CASES:
    if isinstance(repl[1], str) and '_ns_ref_names_v2' in repl[1]:
        # 一致改名：全量替换
        write(P, base.replace(repl[0], repl[1]))
        time.sleep(0.2)
        res = {g: run('scripts/push_api.py', '--' + g) for g in gates}
        write(P, base)
        assert hashlib.md5(read(P).encode('utf-8')).hexdigest() == md5
    else:
        res = case(name, repl, gates)
    print('%-46s %s' % (name, ' '.join('%s=%s' % (g, v) for g, v in res.items())))

print()
print('恢复后 md5 =', hashlib.md5(read(P).encode('utf-8')).hexdigest()[:12],
      '· 与基线一致 =', hashlib.md5(read(P).encode('utf-8')).hexdigest() == md5)
