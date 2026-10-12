# -*- coding: utf-8 -*-
"""第一百五十四轮：把 tree/commit/ref 三个写环节接上同一套可重试判据。

🔴 153 轮点名的缺口：G431 只覆盖 blob；`main()` 里
   POST git/trees · POST git/commits · PATCH git/refs/heads/main
   三处**全是裸 req，一次 502 就 sys.exit(1)** → 整轮白干，
   而本轮实测 502 正是发生在推送尾段。
🔑 判据：这三个环节与 blob **同性质**（服务端临时故障），
   必须走**同一个** req_retry，不许各写一份、也不许裸调 req。
"""
import io
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
PA = os.path.join(ROOT, 'scripts', 'push_api.py')

src = io.open(PA, encoding='utf-8').read()
orig = src


def rep(old, new, n=1):
    global src
    c = src.count(old)
    assert c == n, f'count={c} (want {n}) for: {old[:90]!r}'
    src = src.replace(old, new, n)
    print(f'  ok replaced ({c}) {old[:60]!r}')


# ── 1) 唯一实现 req_retry ────────────────────────────────────────────
anchor = """def mk_blob(path):"""
req_retry = '''def req_retry(method, url, payload=None):
    """🔑 第一百五十四轮：**所有远端写操作的唯一重试实现**。

    🔴 真实缺口（153 轮诚实结论④）：G431 只守 blob 一个环节；
       `main()` 里 POST git/trees · POST git/commits · PATCH git/refs/heads/main
       三处**全是裸 req** —— 一次 502 就 `sys.exit(1)`，整轮白干。
       🔑 判据：这三个环节与 blob **同性质**（服务端临时故障），
          必须走**同一个**实现，不许各写一份、也不许裸调 `req`。
    🔑 重试判据沿用 `_blob_retryable`：**网络层与 5xx 可重试，4xx 不可**
       （153 轮实测修正：141 轮"4xx/5xx 一律不重试"是错的）。
    """
    d = req(method, url, payload)
    for _i in range(BLOB_NET_RETRY):
        if '__err' not in d:
            break
        if not _blob_retryable(d.get('__err', '')):
            break
        time.sleep(BLOB_RETRY_SLEEP * (_i + 1))
        d = req(method, url, payload)
    return d


'''
assert src.count(anchor) == 1
src = src.replace(anchor, req_retry + anchor, 1)
print('  1) req_retry inserted')

# ── 2) mk_blob 改用唯一实现 ──────────────────────────────────────────
rep("""    d = req('POST', f'{API}/git/blobs', payload)
    for _i in range(BLOB_NET_RETRY):
        if '__err' not in d:
            break
        if not _blob_retryable(d.get('__err', '')):
            break
        time.sleep(BLOB_RETRY_SLEEP * (_i + 1))
        d = req('POST', f'{API}/git/blobs', payload)
    if '__err' in d:""",
     """    d = req_retry('POST', f'{API}/git/blobs', payload)
    if '__err' in d:""")
print('  2) mk_blob -> req_retry')

# ── 3) tree / commit / ref 三处写操作 ────────────────────────────────
rep("""    t = req('POST', f'{API}/git/trees', {'tree': tree})""",
    """    t = req_retry('POST', f'{API}/git/trees', {'tree': tree})""")
rep("""    c = req('POST', f'{API}/git/commits',
            {'message': msg, 'tree': t['sha'], 'parents': parents})""",
    """    c = req_retry('POST', f'{API}/git/commits',
                  {'message': msg, 'tree': t['sha'], 'parents': parents})""")
rep("""    upd = req('PATCH', f'{API}/git/refs/heads/main',
              {'sha': c['sha'], 'force': False})""",
    """    upd = req_retry('PATCH', f'{API}/git/refs/heads/main',
                    {'sha': c['sha'], 'force': False})""")
print('  3) tree/commit/ref -> req_retry')

# ── 4) 修 G431 判据②：循环已搬进 req_retry ──────────────────────────
old2 = """    has_loop = has_net = False
    if tree is not None:
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == 'mk_blob':
                for sub in ast.walk(node):
                    if isinstance(sub, ast.For):
                        for s2 in ast.walk(sub):
                            if isinstance(s2, ast.Call) and isinstance(
                                    s2.func, ast.Name)                                     and s2.func.id == '_blob_retryable':
                                has_loop = has_net = True
    if not has_loop:
        bad.append('mk_blob 内找不到调用 _blob_retryable 的重试循环'
                   ' —— 116~140 轮旧实现 / 判据被改回只认 NET:')
    print(f'② AST 重试循环 · 判据走 _blob_retryable: {has_loop and has_net}')"""
new2 = """    # 🔑 154 轮：重试循环已从 mk_blob 搬进 **唯一实现 req_retry**，
    #    所以判据② 改为两段：req_retry 内有循环走 _blob_retryable
    #    **且** mk_blob 调用 req_retry（否则 mk_blob 自己发一次就完事）。
    has_loop = has_net = False
    if tree is not None:
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == 'req_retry':
                for sub in ast.walk(node):
                    if isinstance(sub, ast.For):
                        for s2 in ast.walk(sub):
                            if (isinstance(s2, ast.Call)
                                    and isinstance(s2.func, ast.Name)
                                    and s2.func.id == '_blob_retryable'):
                                has_loop = has_net = True
    mk_calls = False
    if tree is not None:
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == 'mk_blob':
                for sub in ast.walk(node):
                    if (isinstance(sub, ast.Call)
                            and isinstance(sub.func, ast.Name)
                            and sub.func.id == 'req_retry'):
                        mk_calls = True
    if not has_loop:
        bad.append('req_retry 内找不到调用 _blob_retryable 的重试循环'
                   ' —— 116~140 轮旧实现 / 判据被改回只认 NET:')
    if not mk_calls:
        bad.append('mk_blob 不调用 req_retry —— 重试循环搬走后它自己只发一次')
    print(f'② AST 重试循环 · 判据走 _blob_retryable: {has_loop and has_net}'
          f' · mk_blob 走 req_retry: {mk_calls}')"""
rep(old2, new2)
print('  4) G431 判据② 已更新')

# ── 5) 登记常量与函数 ────────────────────────────────────────────────
rep("""    '_blob_retryable': ('fn', 'G431 重试判据：网络层与 HTTP 5xx 可重试，4xx 不可'),
""",
    """    '_blob_retryable': ('fn', 'G431 重试判据：网络层与 HTTP 5xx 可重试，4xx 不可'),
    # 🔑 第一百五十四轮：G442 依赖
    'WRITE_RETRY_STEPS': ('const', '必须走 req_retry 的远端写环节（URL 片段）'),
    'req_retry': ('fn', 'G442 唯一实现：所有远端写操作的重试入口'),
    'cmd_assert_write_retry': ('fn', 'G442 tree/commit/ref 重试的断言入口'),
""")
print('  5) DEPENDENT_NAMES 已登记')

# ── 6) 新增 cmd_assert_write_retry（G442） ───────────────────────────
anchor6 = "def cmd_assert_blob_retry():"
g442 = '''WRITE_RETRY_STEPS = (
    ('git/trees', 'POST'),
    ('git/commits', 'POST'),
    ('git/refs/heads/main', 'PATCH'),
)


def cmd_assert_write_retry():
    """🔑 G442：**tree / commit / ref 三个写环节必须走同一套重试**（154 轮）。

    🔴 真实缺口（153 轮点名）：G431 只守 blob；`main()` 里三处写操作
       **全是裸 req**，一次 502 就 `sys.exit(1)` —— 而 153 轮实测
       HTTP 502 正是服务端随机故障（两次失败文件不同）。
       🔑 判据：**写环节与 blob 同性质**，必须共用 `req_retry`，
          不许各写一份（否则"改了一处"留不下证据），也不许裸调 `req`。

    🔑 五条判据：
       ① `WRITE_RETRY_STEPS` 存在且非空 —— 🔴 环节清单被清空 → 判据恒真
          （106 轮"缺失≠没有违规"同病）
       ② AST：**不认写法** —— 收集 main() 里所有调用，按 URL 片段匹配，
          三个环节的**函数名必须是 `req_retry`**；裸 `req` 或缺一个环节即报
       ③ **行为反证（真调用实现）**：`req` 前 2 次 503、第 3 次成功 →
          断言 `req_retry` 最终成功且真调了 3 次
       ④ 反向：HTTP **403** → 断言**只调用 1 次**（无差别重试会放大故障）
       ⑤ **唯一实现**：本检查的反证必须调用真实 `req_retry`
          —— 防"自测抄一份"（79 轮自证循环）
    """
    print('🔑 **tree / commit / ref 必须走同一套重试**（G442）')
    print('=' * 70)
    os.chdir(ROOT)
    bad = []

    steps = globals().get('WRITE_RETRY_STEPS')
    if not isinstance(steps, (list, tuple)) or not steps:
        bad.append('WRITE_RETRY_STEPS 缺失或为空 —— 环节清单被清空，'
                   '判据② 会恒真（106 轮同病）')
        steps = ()
    print(f'① 必须走重试的写环节 {len(steps)} 个: '
          f'{[s[0] for s in steps]}')

    # ② AST：**不认写法** —— 遍历 main() 全部 Call，按 URL 片段匹配
    try:
        tree = ast.parse(io.open(os.path.join(ROOT, 'scripts', 'push_api.py'),
                                encoding='utf-8').read())
    except Exception as e:
        bad.append(f'无法解析源码 —— 拒绝给结论: {e}')
        tree = None
    found = {}   # url片段 -> set(函数名)
    if tree is not None:
        for node in ast.walk(tree):
            if not (isinstance(node, ast.FunctionDef)
                    and node.name == 'main'):
                continue
            for sub in ast.walk(node):
                if not isinstance(sub, ast.Call):
                    continue
                fn = None
                if isinstance(sub.func, ast.Name):
                    fn = sub.func.id
                # 🔑 133 轮教训：按名字访问 vs 按字符串访问都要认
                if fn is None and isinstance(sub.func, ast.Attribute):
                    fn = sub.func.attr
                if fn is None:
                    continue
                blob = ast.dump(sub)
                for seg, _m in steps:
                    if seg in blob:
                        found.setdefault(seg, set()).add(fn)
    for seg, _m in steps:
        fns = found.get(seg)
        if not fns:
            bad.append(f'环节 {seg}：main() 里找不到对应调用 —— 环节被删？')
            continue
        if 'req_retry' not in fns:
            bad.append(f'环节 {seg} 裸调 {sorted(fns)} —— 未走 req_retry，'
                       '一次 5xx 就整轮白干')
    print(f'② AST 三环节函数名: '
          f'{ {k: sorted(v) for k, v in sorted(found.items())} }')

    # ③ 行为反证：真调用 req_retry（不抄一份）
    real_req = globals().get('req')
    old_sleep = globals().get('BLOB_RETRY_SLEEP')
    calls = []

    def _fake_503(m, u, d=None):
        calls.append(1)
        if len(calls) <= 2:
            return {'__err': 503, '__body': 'Service Unavailable'}
        return {'sha': '0' * 40}

    globals()['req'] = _fake_503
    globals()['BLOB_RETRY_SLEEP'] = 0
    ok3 = False
    try:
        r = req_retry('POST', f'{API}/git/trees', {'tree': []})
        ok3 = '__err' not in r
    except Exception as e:
        ok3 = False
        bad.append(f'req_retry 抛异常 {type(e).__name__}: {e}'
                   ' —— 崩溃与拒绝在 rc 上无法区分（133 轮同病）')
    finally:
        globals()['req'] = real_req
        globals()['BLOB_RETRY_SLEEP'] = old_sleep
    if not ok3:
        bad.append(f'HTTP 503 抖 2 次后 req_retry 仍失败 —— 重试没生效')
    elif len(calls) < 3:
        bad.append(f'HTTP 503 只调用了 {len(calls)} 次 —— 重试次数不足')
    print(f'③ 行为反证：503 抖 2 次 → 调用 {len(calls)} 次 · '
          f'{"成功" if ok3 else "失败"}')

    # ④ 反向：4xx 不得重试
    calls2 = []

    def _fake_403(m, u, d=None):
        calls2.append(1)
        return {'__err': 403, '__body': 'boom'}

    globals()['req'] = _fake_403
    globals()['BLOB_RETRY_SLEEP'] = 0
    try:
        req_retry('POST', f'{API}/git/trees', {'tree': []})
    except Exception:
        pass
    finally:
        globals()['req'] = real_req
        globals()['BLOB_RETRY_SLEEP'] = old_sleep
    if len(calls2) != 1:
        bad.append(f'HTTP 403 被调用了 {len(calls2)} 次'
                   ' —— 无差别重试会放大故障')
    print(f'④ 反向反证：HTTP 403 调用 {len(calls2)} 次（应为 1）')

    # ⑤ 唯一实现：本检查必须真调用 req_retry
    try:
        me = ast.parse(io.open(os.path.join(ROOT, 'scripts', 'push_api.py'),
                               encoding='utf-8').read())
    except Exception:
        me = None
    self_calls = False
    if me is not None:
        for node in ast.walk(me):
            if (isinstance(node, ast.FunctionDef)
                    and node.name == 'cmd_assert_write_retry'):
                for sub in ast.walk(node):
                    if (isinstance(sub, ast.Call)
                            and isinstance(sub.func, ast.Name)
                            and sub.func.id == 'req_retry'):
                        self_calls = True
    if not self_calls:
        bad.append('本检查未调用真实 req_retry —— 自测抄一份会变成自证循环'
                   '（79 轮同病）')
    print(f'⑤ 本检查真调用 req_retry: {self_calls}')

    if bad:
        print()
        for b in bad:
            print('  🔴', b)
        print('\n🔴 **tree / commit / ref 重试** 不成立')
        return 1
    print('\n✅ **tree / commit / ref 重试** 成立')
    return 0


'''
assert src.count(anchor6) == 1
src = src.replace(anchor6, g442 + anchor6, 1)
print('  6) cmd_assert_write_retry inserted')

# ── 7) argparse + 分发 ───────────────────────────────────────────────
rep("""    ap.add_argument('--assert-blob-retry', action='store_true',""",
    """    ap.add_argument('--assert-write-retry', action='store_true',
                    help='G442：tree/commit/ref 三个写环节必须走 req_retry')
    ap.add_argument('--assert-blob-retry', action='store_true',""")
rep("""    if a.assert_blob_retry:""",
    """    if a.assert_write_retry:
        return cmd_assert_write_retry()
    if a.assert_blob_retry:""")
print('  7) argparse + 分发 已接')

assert src != orig
io.open(PA, 'w', encoding='utf-8').write(src)
print('written push_api.py')
