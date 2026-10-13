import io, os
ROOT=os.getcwd(); P=os.path.join(ROOT,'ledger','claims_159.txt')
def read(p):
    with io.open(p,encoding='utf-8') as f: return f.read()
def write(p,s):
    t=p+'.tmp160f'
    with io.open(t,'w',encoding='utf-8') as f: f.write(s)
    if read(t)!=s: raise SystemExit('读回不一致')
    os.replace(t,p)
s=read(P)
a="grep:scripts/push_api.py::CALL_TARGET_USERS = ('_scan_ref_consts_bad', '_no_dirty_wired_bad')"
b="grep:scripts/push_api.py::                grefs |= _call_target_name(n)"
assert s.count(a)==1 and s.count(b)==1
s=s.replace(a,"grep:scripts/push_api.py::CALL_TARGET_USERS = ('_write_step_scan', '_no_dirty_wired_bad')",1)
s=s.replace(b,"grep:scripts/push_api.py::            if isinstance(n, (ast.Call, ast.Subscript)):",1)
s=s.rstrip('\n')+"""
# 🔑 修订记录（第一百六十轮）：两条 needle 因 160 轮修正而失效，已换成等价的真陈述。
#    - `CALL_TARGET_USERS` 首项 `_scan_ref_consts_bad` → `_write_step_scan`：
#      🔴 159 轮把**引用计数**接进调用目标解析是**过宽**的（见本文件诚实结论②），
#        160 轮改走 `_ns_ref_names`，该文件不再是"调用目标解析"的调用点
#        （改由 G448 守护），清单相应换成真正做调用目标解析的 `_write_step_scan`。
#    - `grefs |= _call_target_name(n)` → `if isinstance(n, (ast.Call, ast.Subscript)):`：
#      同上，宽口径已被窄口径取代；改用该处仍然成立的相邻真行。
"""
write(P,s)
print('✅ claims_159 已修订')
