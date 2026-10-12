# -*- coding: utf-8 -*-
"""第一百五十三轮 c：G431 判据修正 —— **HTTP 5xx 可重试，4xx 不可重试**。

🔴 真实事故（本轮推送实测）：连续两次推送都在 blob 阶段中止，报
   `HTTP 502 Server Error`，而 **两次失败的却是不同的文件**
   （target_stack.py → game_asset.py）→ 是服务端随机故障，不是内容问题。
🔑 141 轮的判据写的是「HTTP 4xx/5xx 一律不重试（内容/权限问题）」——
   但 **5xx 是服务端临时故障，与网络抖动同性质**；4xx 才是内容/权限。
   🔴 于是「一次抖动 = 整轮白干」这个 141 轮想根治的病，换了个形态复发。
"""
import io, os, re

ROOT = os.path.dirname(os.path.abspath(__file__))
PA = os.path.join(ROOT, 'scripts', 'push_api.py')
src = open(PA, encoding='utf-8').read()

# ── 1) 新增 helper ────────────────────────────────────────────────
HELPER = '''def _blob_retryable(err):
    """\U0001f511 G431 重试判据（153 轮修正）：**5xx 可重试，4xx 不可重试**。

    \U0001f534 141 轮写的判据是「HTTP 4xx/5xx 一律不重试」—— 本轮实测推翻：
       连续两次推送都因 `HTTP 502 Server Error` 中止，而**两次失败的却是不
       同的文件** → 服务端随机故障，不是内容问题。
    \U0001f511 **5xx 与网络抖动同性质**（服务端临时故障）；**4xx 才是内容/权限**，
       重试无意义且会放大故障（141 轮这条判断对 4xx 仍然成立）。
    """
    if isinstance(err, int):
        return 500 <= err < 600
    e = str(err or '')
    if e.startswith('NET:'):
        return True
    m = re.search(r'(?<!\\d)(5\\d\\d)(?!\\d)', e)
    return bool(m)


'''
a1 = 'def mk_blob(path):'
assert a1 in src
src = src.replace(a1, HELPER + a1, 1)
print('[ok] _blob_retryable 已插入')

# ── 2) mk_blob 改用 helper ────────────────────────────────────────
a2 = """        if not str(d.get('__err', '')).startswith('NET:'):
            break"""
b2 = """        if not _blob_retryable(d.get('__err', '')):
            break"""
assert a2 in src
src = src.replace(a2, b2, 1)
print('[ok] mk_blob 改用 _blob_retryable')

# mk_blob docstring 更正
a2b = """    \U0001f511 判据：**网络抖动是可重试的失败，内容错误不是** ——
       只重试 `__err` 以 `NET:` 开头的（104 轮定义的网络层形态），
       HTTP 4xx/5xx 一律不重试（那是内容/权限问题，重试无意义且会放大故障）。"""
b2b = """    \U0001f511 判据：**网络抖动与服务端 5xx 是可重试的失败，4xx 不是** ——
       重试 `__err` 以 `NET:` 开头的（104 轮定义的网络层形态）**或 HTTP 5xx**；
       \U0001f534 HTTP 4xx 一律不重试（内容/权限问题，重试无意义且会放大故障）。
       \U0001f511 153 轮修正：原判据「4xx/5xx 一律不重试」被实测推翻 —— 连续两次
           推送都因 `HTTP 502` 中止且**失败文件不同**（服务端随机故障）。"""
if a2b in src:
    src = src.replace(a2b, b2b, 1)
    print('[ok] mk_blob docstring 更正')

# ── 3) G431 判据② 改为「调用 _blob_retryable」────────────────────
a3 = """       ② AST：`mk_blob` 内确有重试循环，且过滤条件是 `startswith('NET:')`
          —— \U0001f511 **重试必须只覆盖网络层**；HTTP 4xx/5xx 重试无意义且放大故障
       ③ **行为反证（真调用实现，不抄一份）**：把 `req` 换成"前 2 次返回
          NET 错误、第 3 次成功"，断言 `mk_blob` **最终成功**且真调了 3 次
          → 防"实现被换成只发一次"（130/132 轮判据唯一实现的同款洞）
       ④ **反向行为反证**：`req` 恒返回 HTTP 500，断言**只调用 1 次**
          → 防"无差别重试"（把内容/权限错误也重试，会放大故障）"""
b3 = """       ② AST：`mk_blob` 内确有重试循环，且过滤条件调用 `_blob_retryable`
          —— \U0001f511 **重试只覆盖网络层与服务端 5xx**（153 轮修正）
       ③ **行为反证（真调用实现，不抄一份）**：把 `req` 换成"前 2 次返回
          NET 错误、第 3 次成功"，断言 `mk_blob` **最终成功**且真调了 3 次
          → 防"实现被换成只发一次"（130/132 轮判据唯一实现的同款洞）
       ④ **反向行为反证**：`req` 恒返回 HTTP **403**，断言**只调用 1 次**
          → 防"无差别重试"（把内容/权限错误也重试，会放大故障）
       ⑤ **5xx 反证（153 轮新增）**：`req` 前 2 次返回 HTTP **503**、第 3 次
          成功，断言**最终成功**且真调了 3 次
          \U0001f534 141 轮判据④ 用的是 500 且断言"只调 1 次" —— 它把 5xx
              与 4xx 混为一谈，本轮实测（两次 502 失败文件不同）证明这是错的"""
if a3 in src:
    src = src.replace(a3, b3, 1)
    print('[ok] G431 docstring 更正')
else:
    print('[warn] G431 docstring 形态不同')

# AST 判据
a4 = """                    if isinstance(s2, ast.Call) and isinstance(
                                    s2.func, ast.Attribute)                                     and s2.func.attr == 'startswith'                                     and any(isinstance(a, ast.Constant)
                                            and a.value == 'NET:'
                                            for a in s2.args):
                                has_loop = has_net = True"""
b4 = """                    if isinstance(s2, ast.Call) and isinstance(
                                    s2.func, ast.Name)                                     and s2.func.id == '_blob_retryable':
                                has_loop = has_net = True"""
if a4 in src:
    src = src.replace(a4, b4, 1)
    print('[ok] AST 判据改为查 _blob_retryable')
else:
    print('[warn] AST 判据片段形态不同')
src = src.replace("""    if not has_loop:
        bad.append('mk_blob 内找不到"仅对 NET 错误重试"的循环 —— 116~140 轮旧实现')""",
"""    if not has_loop:
        bad.append('mk_blob 内找不到调用 _blob_retryable 的重试循环'
                   ' —— 116~140 轮旧实现 / 判据被改回只认 NET:')""", 1)
src = src.replace("""    print(f'② AST 重试循环 · 只认 NET: {has_loop and has_net}')""",
"""    print(f'② AST 重试循环 · 判据走 _blob_retryable: {has_loop and has_net}')""", 1)

# ── 4) 判据④ 500 → 403；新增判据⑤ 5xx 真重试 ────────────────────
a5 = """    # ④ 反向：HTTP 错误不得重试
    calls2 = []

    def _fake_http(m, u, d=None):
        calls2.append(1)
        return {'__err': 500, '__body': 'boom'}

    globals()['req'] = _fake_http
    globals()['BLOB_RETRY_SLEEP'] = 0
    try:
        mk_blob('README.md')
    except Exception:
        pass
    finally:
        globals()['req'] = real_req
        globals()['BLOB_RETRY_SLEEP'] = old_sleep
    if len(calls2) != 1:
        bad.append(f'HTTP 500 被调用了 {len(calls2)} 次 —— 无差别重试会放大故障')
    print(f'④ 反向反证：HTTP 500 调用 {len(calls2)} 次（应为 1）')
"""
b5 = """    # ④ 反向：HTTP **4xx**（内容/权限）不得重试
    calls2 = []

    def _fake_http(m, u, d=None):
        calls2.append(1)
        return {'__err': 403, '__body': 'boom'}

    globals()['req'] = _fake_http
    globals()['BLOB_RETRY_SLEEP'] = 0
    try:
        mk_blob('README.md')
    except Exception:
        pass
    finally:
        globals()['req'] = real_req
        globals()['BLOB_RETRY_SLEEP'] = old_sleep
    if len(calls2) != 1:
        bad.append(f'HTTP 403 被调用了 {len(calls2)} 次 —— 无差别重试会放大故障')
    print(f'④ 反向反证：HTTP 403 调用 {len(calls2)} 次（应为 1）')

    # ⑤ \U0001f511 153 轮新增：**5xx 必须重试**（141 轮判据④ 把 500 当成"不该重试"）
    calls3 = []

    def _fake_503(m, u, d=None):
        calls3.append(1)
        if len(calls3) <= 2:
            return {'__err': 503, '__body': 'Service Unavailable'}
        return {'sha': '0' * 40}

    globals()['req'] = _fake_503
    globals()['BLOB_RETRY_SLEEP'] = 0
    try:
        _p3, sha3, err3 = mk_blob('README.md')
    except Exception as e:
        sha3, err3 = None, f'异常 {type(e).__name__}: {e}'
    finally:
        globals()['req'] = real_req
        globals()['BLOB_RETRY_SLEEP'] = old_sleep
    if sha3 is None:
        bad.append(f'HTTP 503 抖 2 次后仍失败（{err3}）—— '
                   '5xx 重试没生效（141 轮"5xx 不重试"的旧判据？）')
    elif len(calls3) < 3:
        bad.append(f'HTTP 503 只调用了 {len(calls3)} 次 —— 5xx 重试次数不足')
    print(f'⑤ 5xx 反证：503 抖 2 次 → 调用 {len(calls3)} 次 · 结果 '
          f'{"成功" if sha3 else "失败"}')
"""
if a5 in src:
    src = src.replace(a5, b5, 1)
    print('[ok] 判据④ 改 403 · 新增判据⑤')
else:
    print('[warn] 判据④ 片段形态不同')

src = src.replace("print('✅ blob 网络抖动重试 4 条判据全部通过')",
                  "print('✅ blob 可重试失败（网络层 + 5xx）5 条判据全部通过')", 1)

# ── 5) 登记 helper ────────────────────────────────────────────────
a6 = "    'cmd_assert_const_exempt_covered': ('fn', 'G441 豁免结构化分类的断言入口'),\n"
assert a6 in src
src = src.replace(a6, a6 +
    "    # \U0001f511 第一百五十三轮：G431 判据修正（5xx 可重试）\n"
    "    '_blob_retryable': ('fn', 'G431 重试判据：网络层与 HTTP 5xx 可重试，4xx 不可'),\n", 1)
print('[ok] _blob_retryable 已登记')

open(PA, 'w', encoding='utf-8').write(src)
print('[done] push_api.py 已写入')
