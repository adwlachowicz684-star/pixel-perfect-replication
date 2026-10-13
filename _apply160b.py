import io, os, py_compile, tempfile
ROOT=os.getcwd()
def read(p):
    with io.open(p,encoding='utf-8') as f: return f.read()
def write(p,s):
    t=p+'.tmp160d'
    with io.open(t,'w',encoding='utf-8') as f: f.write(s)
    if read(t)!=s: raise SystemExit('读回不一致 %s'%p)
    py_compile.compile(t,cfile=tempfile.mktemp(),doraise=True)
    os.replace(t,p)

P=os.path.join(ROOT,'scripts','run_all_gates.py'); src=read(P)
old = """    ("G447", "**等价写法解析必须唯一实现，且结果真被用**（158 轮残留：只推广了一处）",
     ["{py}", "{s}/push_api.py", "--assert-call-target-single"], "hard",
     ["scripts/push_api.py"]),
]
"""
assert src.count(old)==1, 'gate anchor'
new = """    ("G447", "**等价写法解析必须唯一实现，且结果真被用**（158 轮残留：只推广了一处）",
     ["{py}", "{s}/push_api.py", "--assert-call-target-single"], "hard",
     ["scripts/push_api.py"]),
    # 🔑 第一百六十轮：G448 —— **「引用」口径必须有命名空间限定**。
    #    🔴 159 轮诚实结论②：把 `_scan_ref_consts_bad` 的引用计数改走宽口径
    #       `_call_target_name` 后，**任何** cfg['X'] / cfg.get('X') 都算
    #       "引用过" —— 实测宽口径比窄口径多认 292 个字符串，其中 211 个
    #       既非 Name 引用也非命名空间引用（audit-all / allowlist …）。
    #       🔑 危害是**稀释**：证据几乎恒真 → 误报 → 催生批量豁免 → 判据被吃掉。
    ("G448", "**「引用」口径必须有命名空间限定**（159 轮：任意字典查表都算引用 → 稀释）",
     ["{py}", "{s}/push_api.py", "--assert-ns-ref-scope"], "hard",
     ["scripts/push_api.py"]),
]
"""
src=src.replace(old,new,1)

old_b = """     '只留 G447 → 写环节扫描本身的逐环节 / 逐形态覆盖无人查。'),
)
"""
assert src.count(old_b)==1, 'both anchor'
new_b = """     '只留 G447 → 写环节扫描本身的逐环节 / 逐形态覆盖无人查。'),
    # 🔑 第一百六十轮：G448 —— 常量反向扫描的**引用口径限定**。
    ('G440', 'G448',
     'G440 负责"核心基建文件里被引用但未登记的常量必须被发现"（覆盖面），'
     'G448 负责它判定"被引用"时**只认命名空间限定的按字符串访问**'
     '（globals() / locals() / vars()），任意字典查表'
     '（cfg[X] / getattr(obj, X) 等）不得算引用。'
     '🔴 只留 G440 → 口径被放宽时（159 轮实测：多认 211 个无关字符串）'
     '它照样 rc=0，证据稀释无人发现；'
     '只留 G448 → 根本没有"哪些常量该被登记"的实际扫描，口径限定无的放矢。'),
)
"""
src=src.replace(old_b,new_b,1)
write(P,src)
print('✅ run_all_gates.py 已更新')
