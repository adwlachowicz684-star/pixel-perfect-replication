import io, os, py_compile, tempfile
ROOT=os.getcwd(); P=os.path.join(ROOT,'scripts','push_api.py')
def read(p):
    with io.open(p,encoding='utf-8') as f: return f.read()
def write(p,s):
    t=p+'.tmp160c'
    with io.open(t,'w',encoding='utf-8') as f: f.write(s)
    if read(t)!=s: raise SystemExit('读回不一致')
    py_compile.compile(t,cfile=tempfile.mktemp(),doraise=True)
    os.replace(t,p)
src=read(P)
old = """        dsrc = ('def _scan_ref_consts_bad():\\n'
                '    for n in ():\\n'
                '        %s(n)\\n' % ct_name)"""
new = """        # 🔑 160 轮修正：样本函数名**不许硬编码**（111 轮同病）—— 取清单首项，
        #    否则 CALL_TARGET_USERS 改了之后样本不在清单里，⑤ 会静默失效
        du = tuple(globals().get('CALL_TARGET_USERS') or ())
        dname = du[0] if du else None
        dsrc = ('def %s():\\n'
                '    for n in ():\\n'
                '        %s(n)\\n' % (dname, ct_name))"""
assert src.count(old)==1
src=src.replace(old,new,1)
write(P,src)
print('ok')
