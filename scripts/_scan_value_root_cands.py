# 🔑 第一百一十七轮：**值型根候选扫描器**（报告入口，不是门禁）
#
# 判据（116 轮 `_root_criteria` 判据①）：
#   「改变它会让某条门禁**静默失效**」—— 即：某条门禁**断言了这个常量的值**。
#
# 🔑 与 116 轮失败的自动标准（"跨文件被引用次数"）的区别：
#    116 轮扫的是「谁被引用得多」→ 216 个候选，真根 0 命中。
#    本轮扫的是「谁的值被门禁**断言**」→ 这才是根的定义性特征。
#
# 扫描方式：找出各门禁入口里形如
#     `X != CONST` / `X == CONST` / `CONST != X` / `X not in CONST`
# 的比较，且 CONST 是**顶层大写常量** → 该常量即"被断言的值型根"候选。
import ast, glob, os, json, sys, argparse

_ap = argparse.ArgumentParser(description='🔑 值型根候选（判据①：值被门禁断言）')
_ap.add_argument('--limit', type=int, default=40, help='打印前 N 条')
_a = _ap.parse_args()

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# ① 收集所有顶层大写常量的定义文件
consts = {}
for f in sorted(glob.glob(os.path.join(HERE, '*.py'))):
    try:
        t = ast.parse(open(f, encoding='utf-8').read())
    except Exception:
        continue
    for n in t.body:
        if isinstance(n, ast.Assign):
            for tg in n.targets:
                if isinstance(tg, ast.Name) and tg.id.isupper():
                    consts.setdefault(tg.id, set()).add(os.path.basename(f))

# ② 找出被"比较断言"的常量（== / != / not in / in）
hits = {}
for f in sorted(glob.glob(os.path.join(HERE, '*.py'))):
    try:
        t = ast.parse(open(f, encoding='utf-8').read())
    except Exception:
        continue
    for m in ast.walk(t):
        names = []
        if isinstance(m, ast.Compare):
            if any(isinstance(o, (ast.Eq, ast.NotEq, ast.In, ast.NotIn)) for o in m.ops):
                for c in [m.left] + list(m.comparators):
                    if isinstance(c, ast.Name) and c.id in consts:
                        names.append(c.id)
        for nm in names:
            hits.setdefault(nm, set()).add(os.path.basename(f))

tr = json.load(open(os.path.join(ROOT, 'ledger', 'trust_root.json'), encoding='utf-8'))
vr = set(tr.get('VALUE_ROOTS') or {})

print('🔑 值型根候选 —— 判据①「值被门禁断言」（**报告用，不是门禁**）')
print('🔑 已登记 %d 个值型根：%s' % (len(vr), sorted(vr)))
print()
rows = sorted(hits.items(), key=lambda x: (-len(x[1]), x[0]))
for nm, fs in rows[:_a.limit]:
    mark = 'REG' if nm in vr else 'NEW'
    print('  %-4s %-34s 断言处%s: %s' % (mark, nm, len(fs), sorted(fs)))
print()
print('  共 %d 个候选 · 已登记 %d' % (len(rows), len(vr & set(hits))))
sys.exit(0)
