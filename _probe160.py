import ast, os, re, io, sys
sys.path.insert(0, os.path.join(os.getcwd(), 'scripts'))
import push_api as P
P.ROOT = os.getcwd()
files = P.CONST_SCAN_FILES
dep = P.DEPENDENT_NAMES
meta = P.CONST_SCAN_META_EXEMPT
allow = P.PATH_CONST_ALLOW
callow = P.CONST_SCAN_ALLOW
refs=set(); wide=set()
for fn in sorted(os.listdir(os.path.join(P.ROOT,'scripts'))):
    if not fn.endswith('.py'): continue
    try: t=ast.parse(io.open(os.path.join(P.ROOT,'scripts',fn),encoding='utf-8').read())
    except Exception: continue
    for n in ast.walk(t):
        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load): refs.add(n.id)
        if isinstance(n,(ast.Call, ast.Subscript)): wide |= P._call_target_name(n)
NS=('globals','locals','vars')
def ns_call(v):
    if not isinstance(v, ast.Call) or v.args or v.keywords: return False
    f=v.func
    nm=f.id if isinstance(f,ast.Name) else (f.attr if isinstance(f,ast.Attribute) else None)
    return nm in NS
def narrow(n):
    names=set()
    if isinstance(n, ast.Subscript):
        sl=n.slice
        if ns_call(n.value) and isinstance(sl,ast.Constant) and isinstance(sl.value,str): names.add(sl.value)
    elif isinstance(n, ast.Call):
        f=n.func
        if isinstance(f,ast.Attribute) and f.attr=='get':
            if ns_call(f.value) and n.args:
                a0=n.args[0]
                if isinstance(a0,ast.Constant) and isinstance(a0.value,str): names.add(a0.value)
        elif isinstance(f,ast.Name) and f.id=='getattr':
            if len(n.args)>=2 and ns_call(n.args[0]):
                a1=n.args[1]
                if isinstance(a1,ast.Constant) and isinstance(a1.value,str): names.add(a1.value)
    return names
nrefs=set()
for fn in sorted(os.listdir(os.path.join(P.ROOT,'scripts'))):
    if not fn.endswith('.py'): continue
    try: t=ast.parse(io.open(os.path.join(P.ROOT,'scripts',fn),encoding='utf-8').read())
    except Exception: continue
    for n in ast.walk(t):
        if isinstance(n,(ast.Call,ast.Subscript)): nrefs |= narrow(n)
print('wide=%d narrow=%d refs=%d' % (len(wide), len(nrefs), len(refs)))
print('wide-only (非 narrow 非 Name):', len(wide-refs-nrefs))
print(sorted(wide-refs-nrefs)[:40])
# 统计核心文件里 只因 wide 而被判"已引用"的未登记常量
only_wide=[]; scanned=0; skipped=0
for fn in files:
    p=os.path.join(P.ROOT,'scripts',fn)
    t=ast.parse(io.open(p,encoding='utf-8').read())
    for node in t.body:
        names=[]
        if isinstance(node, ast.Assign):
            for tg in node.targets:
                if isinstance(tg,ast.Name): names.append(tg.id)
        elif isinstance(node,ast.AnnAssign) and isinstance(node.target,ast.Name): names.append(node.target.id)
        for name in names:
            if not re.fullmatch(r'[A-Z][A-Z0-9_]*',name): continue
            scanned+=1
            if name in dep or name in meta: continue
            if f'{fn}::{name}' in allow: continue
            if f'{fn}::{name}' in callow: continue
            if name in refs or name in nrefs:
                if name not in refs and name in wide: only_wide.append((fn,name))
                continue
            skipped+=1
print('scanned=%d skipped(未引用)=%d' % (scanned, skipped))
print('仅因宽口径被判已引用(会被 flag):', only_wide)
