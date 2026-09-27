# 🔑 第一百一十六轮：**报告入口，不是门禁**
# 🔴 实测：用『跨文件被引用 >= 1』自动识别根 → 扫出 216 个，
#    但**真正的根 GATE_RC_DOMAIN 恰好 0 次**（只在定义文件内被引用）。
# 🔑 所以『跨文件引用』与『是不是根』不相关 —— 本脚本只作**人工参考**，
#    绝不作为门禁（否则会漏掉真根，同时把 216 个台账规则常量误报成根）。
import ast, glob, os, json, sys, argparse

# 🔑 117 轮：G406 抓到本文件用了 os.path.join(ROOT,'ledger',...) 形式却**未登记**。
#    ✅ 登记进 PATH_CONST_ALLOW（它只是**读**信任根，不是产物路径，无需进 DEPENDENT_NAMES）。
TRUST_ROOT_FILE = os.path.join(ROOT, 'ledger', 'trust_root.json')

files = sorted(glob.glob('scripts/*.py'))
asts, loads = {}, {}
for f in files:
    try:
        t = ast.parse(open(f, encoding='utf-8').read())
    except Exception:
        continue
    asts[f] = t
    loads[f] = {m.id for m in ast.walk(t)
                if isinstance(m, ast.Name) and isinstance(m.ctx, ast.Load)}

out = {}
for f, t in asts.items():
    for n in t.body:
        if not isinstance(n, ast.Assign):
            continue
        for tg in n.targets:
            if not isinstance(tg, ast.Name):
                continue
            nm = tg.id
            if not (nm.isupper() and len(nm) > 6):
                continue
            users = [g for g in asts if g != f and nm in loads[g]]
            if users:
                out[nm] = users

ap = argparse.ArgumentParser(description='🔑 跨文件引用常量候选（**报告用，不是门禁**）')
ap.add_argument('--limit', type=int, default=60, help='打印前 N 条（默认 60）')
_a = ap.parse_args()
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
tr_path = TRUST_ROOT_FILE
tr = json.load(open(tr_path, encoding='utf-8'))
vr = set(tr.get('VALUE_ROOTS') or {})
print('🔑 跨文件引用常量候选（**仅供人工参考，不是根判定**）')
print('🔴 真正的根 GATE_RC_DOMAIN 在本列表中**不存在**（它只在定义文件内被引用）')
lines = []
for nm, u in sorted(out.items(), key=lambda x: -len(x[1])):
    mark = 'REG' if nm in vr else 'NEW'
    lines.append(f'{mark} {nm} n={len(u)} def={os.path.basename(u[0]) if u else "-"}')
lines.append(f'TOTAL {len(out)} REG {len(vr & set(out))}')
for ln in lines[:_a.limit]:
    print('  ' + ln)
print('  …（共 %d 条）' % (len(lines) - 1))
sys.exit(0)
