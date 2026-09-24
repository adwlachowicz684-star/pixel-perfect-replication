#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""🔑 **GitHub 推送脚本**（走 REST API，不依赖 git https）

## 为什么不用 `git push`
🔴 本沙盒对 `github.com` 的 **git https 协议**被代理拦截（403），
   而 `api.github.com` 是通的。所以改用 **Git Data API** 直接写对象。

## 用法
```bash
python3 scripts/push_api.py                 # 推送当前目录全部受管文件
python3 scripts/push_api.py -m "提交说明"    # 指定 commit message
python3 scripts/push_api.py --dry-run        # 只统计，不推送
```

## 令牌
🔑 从 `~/.gh_token` 或 `../.gh_token` 或环境变量 `GH_TOKEN` 读取。
🔴 不要把令牌写进本文件。

## 设计要点
- 🔑 用 `git ls-files -z` + `core.quotepath=false` —— **中文文件名**才不会被
  八进制转义（实测：不设 quotepath 会导致 75 个中文文件"读取失败"）。
- 🔑 blob 用 **base64** 统一编码，二进制文件也能正确传输。
- 🔑 commit 的 parent 设为**远程当前 main** —— 历史连续，不是孤立的 commit。
- 🔑 **空仓库**第一次要先建一个初始 commit（blob API 对空仓库返回 409）。
"""
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
# 🔑 第一百零二轮：历史遗留台账 —— 让"已知遗留"成为**可断言的事实**。
HISTORY_KNOWN = os.path.join(ROOT, 'audit', 'history_mode_known.json')
OWNER = 'adwlachowicz684-star'
REPO = 'pixel-perfect-replication'


def load_token():
    for p in (os.path.expanduser('~/.gh_token'),
              os.path.join(ROOT, '.gh_token'),
              '/data/workspace/.gh_token'):
        if os.path.exists(p):
            return open(p).read().strip()
    t = os.environ.get('GH_TOKEN')
    if t:
        return t.strip()
    print('🔴 未找到令牌（~/.gh_token 或 GH_TOKEN）')
    sys.exit(1)


TOK = load_token()
API = f'https://api.github.com/repos/{OWNER}/{REPO}'
HDR = {'Authorization': f'Bearer {TOK}',
       'Accept': 'application/vnd.github+json',
       'X-GitHub-Api-Version': '2022-11-28',
       'Content-Type': 'application/json'}


def req(method, url, data=None):
    body = json.dumps(data).encode() if data is not None else None
    r = urllib.request.Request(url, data=body, headers=HDR, method=method)
    try:
        with urllib.request.urlopen(r, timeout=120) as f:
            return json.loads(f.read().decode())
    except urllib.error.HTTPError as e:
        try:
            b = e.read().decode()[:300]
        except Exception:
            b = ''
        return {'__err': e.code, '__body': b}



def check_untracked():
    """🔑 返回**未纳入版本管理**的文件列表（相对路径）。

    🔑 只看 `git status --porcelain` 的前两列状态：
       - `??` = 未跟踪（忘了 `git add`）
       - ` D` = 已跟踪但被删除（忘了 `git rm` / 没提交删除）
    🔑 忽略 `.gitignore` 已排除的（`--porcelain` 默认不列它们）。
    🔴 解析失败返回 `None`（调用方按"无法确定"处理，不静默当"没有"）。
    """
    out = os.popen('git status --porcelain -z').read()
    if not out:
        # 🔴 空输出也可能是 git 出错，用 returncode 区分
        rc = os.system('git rev-parse --is-inside-work-tree >/dev/null 2>&1')
        if rc != 0:
            return None
        return []
    res = []
    for item in out.split('\0'):
        if not item.strip():
            continue
        # 状态占前 2 字符（`-z` 下格式为 "XY path"，路径可能含中文）
        st = item[:2]
        path = item[3:] if len(item) > 3 else ''
        if not path:
            continue
        # 🔑 重命名 `R ` 在 -z 下有两条记录，这里只取"未跟踪"与"已删"
        if st == '??' or st.strip() == 'D':
            res.append((st, path))
    return res


def list_files():
    """🔑 中文文件名安全：必须 `-z` + `core.quotepath=false`。"""
    raw = os.popen(
        'git -c core.quotepath=false ls-files -z').read()
    return [p for p in raw.split('\0') if p.strip()]


def blob_content(path):
    """🔑 路径在 **git 里的 blob 字节内容**（唯一实现）。

    🔑 第一百轮修复：**symlink 不能用 open() 读**。
       🔴 旧代码 `open(path,'rb').read()` 会**跟随链接**读目标文件内容，
          而 git 索引里 symlink 的 blob 是**链接路径字符串**本身。
          实测：链接指向 /tmp/target.txt 时
            open()  → 28dd9395…（目标文件内容）
            索引     → 69317bc9…（字符串 "/tmp/target.txt"）
          两者**必然不一致** → 推上去内容与 git 索引不符。
       🔑 判据：symlink 的"内容"就是它指向的路径（**git 的定义**）。

    🔴 第一百轮第二个修复：此函数必须是**唯一实现**。
       🔴 第一版 `--check-symlink` 在自测里**抄了一份同样的逻辑** →
          回退 `mk_blob` 的修复后自测**仍然报"✅ 正确"** ——
          **自测测的是自己抄的那份，不是真实实现**（自证循环）。
       🔑 所以 `mk_blob` 与自测**都调用本函数**。
    """
    if os.path.islink(path):
        return os.readlink(path).encode('utf-8')
    return open(path, 'rb').read()


def mk_blob(path):
    try:
        raw = blob_content(path)
    except Exception as e:
        return (path, None, f'读取失败: {e}')
    d = req('POST', f'{API}/git/blobs',
            {'content': base64.b64encode(raw).decode(),
             'encoding': 'base64'})
    if '__err' in d:
        return (path, None, f"HTTP {d['__err']} {d['__body'][:150]}")
    return (path, d['sha'], None)



def local_index_entries():
    """🔑 本地文件的 **(mode, sha)** —— 用 `git ls-files -s` 一次拿到。

    🔑 第九十九轮：从 `hash-object` 换成 `ls-files -s`。
       🔴 旧实现只取 sha，**拿不到 mode** → 权限差异查不出来；
          且对 **symlink**（mode 120000）结果不可靠。
       🔑 `ls-files -s` 输出：`<mode> <sha> <stage>\t<path>`
          —— mode 与 sha **同源**，不会出现"两者取自不同命令"的错位。

    🔑 返回的 mode/sha 与 GitHub tree API 的字段**语义一致**：
       100644 普通文件 · 100755 可执行 · 120000 symlink · 160000 gitlink
    🔑 返回 dict {path: (mode, sha)}；`None` 表示无法确定。
    """
    import subprocess
    try:
        proc = subprocess.run(
            ['git', '-c', 'core.quotepath=false', 'ls-files', '-s', '-z'],
            capture_output=True, text=True, timeout=120)
        if proc.returncode != 0:
            return None
    except Exception:
        return None
    res = {}
    for item in proc.stdout.split('\0'):
        if not item.strip():
            continue
        # 格式 "mode sha stage\tpath"
        meta, _, path = item.partition('\t')
        parts = meta.split()
        if len(parts) < 2 or not path:
            return None
        res[path] = (parts[0], parts[1])
    return res or None


def cmd_verify_push(report=False):
    """🔑 G391：**回读远端 tree** 并与本地逐条比对。

    🔴 第九十七轮诚实结论⑤：`push_api.py` 打印"已推送"，但**没有回读远端
       确认文件数一致** —— 这正是第五十三轮"自测 ≠ 取证"的同一类问题：
       **"我发了"不等于"对面收到了"。**

    🔑 **四层比对**（第九十九轮新增第④层）：
      ① **缺失** —— 本地有、远端无（漏传）
      ② **多余** —— 远端有、本地无（脏远端 / 旧文件残留）
      ③ **内容不一致** —— 路径同名但 **blob sha 不同**（部分漏传）
      ④ **权限不一致** —— 同名同内容但 **mode 不同**（100644 / 100755）

    🔑 `report=True`（`--report`）：**只报告不阻断**。
       🔴 第九十八轮诚实结论⑤：G391 移入人工门禁后，
          **推送之外无人定期验证远端完整性** —— 本模式就是那个定期入口，
          供人工定期跑，把"多余"这类**不阻断但会挂着的问题**看清楚。
    """
    print('=' * 70)
    tag = '🔑 **远端完整性复核**（报告模式，不阻断）' if report \
        else '🔑 **推送完整性验证** —— 回读远端 tree 与本地逐条比对'
    print(tag)
    print('=' * 70)
    loc = local_index_entries()
    if not loc:
        print('🔴 **无法确定**本地文件 mode/sha（git 不可用） —— 拒绝给结论')
        return 1
    print(f'\n🔑 本地受管文件 {len(loc)} 个')

    d = req('GET', f'{API}/git/trees/main?recursive=1')
    if '__err' in d:
        print(f"🔴 无法读取远端 tree: HTTP {d['__err']} {d['__body'][:150]}")
        return 1
    if d.get('truncated'):
        print('🔴 远端 tree **被截断**（文件过多） —— 无法完整比对')
        return 1
    rem = {t['path']: (t.get('mode', ''), t['sha'])
           for t in d['tree'] if t['type'] == 'blob'}
    print(f'🔑 远端 blob     {len(rem)} 个')

    missing = sorted(set(loc) - set(rem))
    extra = sorted(set(rem) - set(loc))
    both = set(loc) & set(rem)
    diff = sorted(p for p in both if loc[p][1] != rem[p][1])
    # 🔑 第九十九轮新增：mode 比对（本地 mode 可能只给 644/755 三位）
    def _mode_eq(a, b):
        if not a or not b:
            return True          # 🔴 拿不到就不比，不当成"不一致"
        return a[-3:] == b[-3:]
    mode_diff = sorted(p for p in both
                       if loc[p][1] == rem[p][1]
                       and not _mode_eq(loc[p][0], rem[p][0]))

    print()
    if missing:
        print(f'🔴 **缺失**（本地有、远端无）{len(missing)} 个 —— 漏传：')
        for p_ in missing[:10]:
            print(f'   - {p_}')
    if extra:
        print(f'⚠️ **多余**（远端有、本地无）{len(extra)} 个 —— 远端残留：')
        for p_ in extra[:10]:
            print(f'   - {p_}')
    if diff:
        print(f'🔴 **内容不一致**（同名但 sha 不同）{len(diff)} 个：')
        for p_ in diff[:10]:
            print(f'   - {p_}  本地 {loc[p_][1][:8]} ≠ 远端 {rem[p_][1][:8]}')
    if mode_diff:
        print(f'🔴 **权限不一致**（同名同内容但 mode 不同）{len(mode_diff)} 个：')
        for p_ in mode_diff[:10]:
            print(f'   - {p_}  本地 {loc[p_][0]} ≠ 远端 {rem[p_][0]}')

    bad = len(missing) + len(diff) + len(mode_diff)
    print()
    print('=' * 70)
    if bad:
        print(f'🔴 **{"远端与本地不一致" if report else "推送不完整"}**：'
              f'缺失 {len(missing)} · 内容不一致 {len(diff)} · '
              f'权限不一致 {len(mode_diff)}')
        if report:
            print('   🔑 报告模式：**只报告不阻断**，请人工判断')
            print('=' * 70)
            return 0
        print('   "已推送"是声称，逐条比对一致才是事实')
        print('=' * 70)
        return 1
    print(f'✅ {"远端与本地一致" if report else "推送完整"}：'
          f'{len(loc)} 个文件逐条 **mode + sha** 一致'
          f'{"（远端另有 " + str(len(extra)) + " 个残留）" if extra else ""}')
    print('=' * 70)
    return 0



def cmd_check_symlink():
    """🔑 G393：symlink 处理正确性**自测**。

    🔴 为什么要自测：symlink（mode 120000）在当前仓库里**一个都没有**，
       所以 G391 的常规比对**永远不会碰到它**——
       缺陷会一直潜伏到某天真有人加 symlink 才爆发。
    🔑 所以造一个**临时** symlink，验证：
       ① `local_index_entries()` 认出 mode = 120000
       ② `mk_blob()` 算出的内容 sha == git 索引的 sha
    🔑 自测结束**清理**临时文件，不留脏。
    """
    import hashlib, subprocess, tempfile, shutil

    def gitsha(b):
        return hashlib.sha1(b'blob %d\0' % len(b) + b).hexdigest()

    print('=' * 70)
    print('🔑 **symlink 处理自测**（G393）')
    print('=' * 70)
    link = 'scripts/_symlink_selftest_tmp'
    subprocess.run(['git', 'rm', '-f', '--cached', link],
                   capture_output=True)
    try:
        os.remove(link)
    except OSError:
        pass

    tgt_name = '_symlink_target_selftest.txt'
    tgt = os.path.join(tempfile.gettempdir(), tgt_name)
    with open(tgt, 'w', encoding='utf-8') as f:
        f.write('自测目标\n')
    ok_all = True
    try:
        os.symlink(tgt, link)
        subprocess.run(['git', 'add', '-A'], capture_output=True,
                       cwd=ROOT)
        idx = local_index_entries()
        e = idx.get(link) if idx else None
        print(f'\n① git 索引 mode/sha：{e}')
        if not e:
            print('🔴 索引里查不到该 symlink —— 无法自测')
            return 1
        got_mode = e[0] == '120000'
        print(f'   {"✅" if got_mode else "🔴"} mode == 120000'
              f'（实测 {e[0]}）')
        ok_all &= got_mode

        # 🔑 **调用真实实现** `blob_content`（不是抄一份），否则回退修复
        #    也不会被测出（第一百轮实测教训）。
        raw = blob_content(link)
        sha_new = gitsha(raw)
        same = sha_new == e[1]
        print(f'\n② mk_blob 内容 sha：{sha_new[:12]}…')
        print(f'   git 索引 sha      ：{e[1][:12]}…')
        print(f'   {"✅" if same else "🔴"} 两者一致'
              f'{"" if same else " —— 🔴 推上去会与 git 索引不符"}')
        ok_all &= same

        # 🔑 反证：展示 open() 会读到什么（证明修复前的 bug 真实存在）
        raw_bad = open(link, 'rb').read()   # 🔑 显式复现**旧实现**，仅作反证
        sha_bad = gitsha(raw_bad)
        print(f'\n③ 反证（旧实现 open() 跟随链接）：')
        print(f'   open() 读到   ：{raw_bad!r}')
        print(f'   open() 的 sha ：{sha_bad[:12]}…')
        if sha_bad != e[1]:
            print(f'   🔑 与索引 sha 不同 —— 说明该 bug **真实存在**，'
                  f'本修复确有必要')
        else:
            print(f'   ⚠️ 与索引 sha 相同（目标内容恰好等于链接路径？）')
    finally:
        # 清理
        try:
            subprocess.run(['git', 'rm', '-f', '--cached', link],
                           capture_output=True, cwd=ROOT)
        except Exception:
            pass
        try:
            os.remove(link)
        except OSError:
            pass
        try:
            os.remove(tgt)
        except OSError:
            pass

    print()
    print('=' * 70)
    if ok_all:
        print('✅ symlink 处理正确：mode 120000 已识别、内容 sha 与索引一致')
        print('=' * 70)
        return 0
    print('🔴 symlink 处理**不正确** —— 真加 symlink 时会推错内容')
    print('=' * 70)
    return 1



def cmd_audit_history():
    """🔑 G394：**历史 commit 权限审计**（只读，不改写历史）。

    🔴 第九十九轮诚实结论②：96~98 轮的 commit 里，266 个文件
       **全部被推成 100755**（`os.access(X_OK)` 恒 True 的遗留），
       第九十九轮只修正了**最新 commit**，历史未改写。
    🔑 本入口把这件事变成**可查的事实**：逐个 commit 统计 mode 分布。

    🔑 **只读**：不发 PATCH、不 force push。
       🔴 改写历史是破坏性操作，必须人工显式决定，不由脚本自作主张。
    """
    print('=' * 70)
    print('🔑 **历史 commit 权限审计**（只读 · 不改写历史）')
    print('=' * 70)
    idx = local_index_entries()
    if not idx:
        print('🔴 无法确定 git 索引 mode —— 拒绝给结论')
        return 1
    want = {}
    for _m, _ in idx.values():
        want[_m] = want.get(_m, 0) + 1
    print(f'\n🔑 当前 git 索引基准：{want}')

    d = req('GET', f'{API}/commits?per_page=100')
    if '__err' in d:
        print(f"🔴 无法读取 commit 列表: HTTP {d['__err']}")
        return 1
    if not isinstance(d, list):
        print('🔴 commit 列表格式异常 —— 拒绝给结论')
        return 1
    print(f'🔑 远端 commit {len(d)} 个\n')

    bad = []
    for c in d:
        sha = c['sha']
        t = req('GET', f'{API}/git/trees/{sha}?recursive=1')
        if '__err' in t:
            print(f"⚠️ {sha[:12]} 树读取失败 HTTP {t['__err']} —— 跳过")
            continue
        dist = {}
        for it in t.get('tree', []):
            if it['type'] == 'blob':
                dist[it['mode']] = dist.get(it['mode'], 0) + 1
        msg = c['commit']['message'].splitlines()[0][:34]
        # 🔑 判据：与该 commit **当时**应有的 mode 无法自动得知，
        #    故用**当前索引基准**比对：出现索引里**没有**的 mode 即为异常。
        odd = {m: n for m, n in dist.items() if m not in want}
        if odd:
            bad.append((sha[:12], msg, odd, dist))
            print(f'🔴 {sha[:12]}  {msg}')
            print(f'     异常 mode {odd}   全分布 {dist}')
        else:
            print(f'✅ {sha[:12]}  {msg}   {dist}')

    print()
    print('=' * 70)
    if bad:
        print(f'🔴 **{len(bad)} 个历史 commit 的 mode 与当前索引基准不一致**')
        print('   🔑 这些是**历史遗留**，当前 HEAD 已正确（见 G391）。')
        print('   🔴 修正需**改写历史（force push）** —— 破坏性操作，')
        print('      本脚本**只读不改写**，须人工显式决定。')
    else:
        print('✅ 全部历史 commit 的 mode 与当前索引基准一致')

    # 🔑 第一百零二轮：**写台账**，让遗留变成可断言的事实。
    #    🔴 上一轮问题：遗留只在 stdout 出现一次，G394 永远返回 0
    #       → "门禁绿但问题在"。写入台账后由 G396 双向断言。
    rec = {
        'generated_at': time.strftime('%Y-%m-%dT%H:%M:%S%z'),
        'baseline_modes': want,
        'checked_commits': len(d),
        'known_legacy': [{'sha': h, 'msg': m, 'odd_modes': o}
                         for h, m, o, _ in bad],
        'note': '历史 commit 的 mode 与当前 git 索引基准不一致。'
                ' 修正需 force push（破坏性），本脚本只读不改写。'
                ' 本台账由 G396 双向断言，不得手工静默删改。',
    }
    try:
        os.makedirs(os.path.dirname(HISTORY_KNOWN), exist_ok=True)
        with open(HISTORY_KNOWN, 'w', encoding='utf-8') as f:
            json.dump(rec, f, ensure_ascii=False, indent=2)
        print(f'\n🔑 台账已写：{os.path.relpath(HISTORY_KNOWN, ROOT)}'
              f' · known_legacy {len(rec["known_legacy"])} 条')
    except Exception as e:
        print(f'\n🔴 台账写入失败：{e} —— 遗留无法被 G396 断言')
        return 1
    print('=' * 70)
    # 🔑 审计本身不算失败 —— 它**不被掩盖**即算达标（由 G396 守）
    return 0


def cmd_check_gitlink():
    """🔑 G395：gitlink（mode 160000，submodule）处理自测。

    🔴 第一百轮诚实结论①：gitlink **仍未实测**。
    🔑 而且它比 symlink 更危险：gitlink **磁盘上没有对应文件**
       —— `git ls-files` 会列出它，但 `os.path.exists()` 为 False。
       🔴 这意味着：一旦仓库里真有 submodule，旧的推送流程会
          在「N 个文件在磁盘上不存在」处**直接退出**。

    🔑 用 `git update-index --add --cacheinfo` 造一个**纯索引** gitlink
       （不需要真 submodule），验证：
       ① `local_index_entries()` 认出 mode = 160000
       ② 推送前置检查**不会**把它当成"磁盘上不存在"而崩掉
    """
    import subprocess
    print('=' * 70)
    print('🔑 **gitlink 处理自测**（G395）')
    print('=' * 70)
    gl = 'scripts/_gitlink_selftest'
    subprocess.run(['git', 'rm', '-f', '--cached', gl],
                   capture_output=True, cwd=ROOT)
    # 一个任意存在的 commit sha 即可（gitlink 指向 submodule 的 commit）
    fake = '0000000000000000000000000000000000000001'
    ok_all = True
    try:
        r = subprocess.run(
            ['git', 'update-index', '--add', '--cacheinfo',
             f'160000,{fake},{gl}'],
            capture_output=True, text=True, cwd=ROOT)
        print(f'\n① 构造 gitlink（纯索引，无磁盘文件）: rc={r.returncode}')
        idx = local_index_entries()
        e = idx.get(gl) if idx else None
        print(f'   git 索引条目：{e}')
        got = bool(e) and e[0] == '160000'
        print(f'   {"✅" if got else "🔴"} mode == 160000'
              f'（实测 {e[0] if e else "无"}）')
        ok_all &= got

        # ② 磁盘上确实没有
        on_disk = os.path.exists(gl)
        print(f'\n② 磁盘上存在？{on_disk}'
              f'   {"✅ 符合预期（gitlink 无磁盘文件）" if not on_disk else "⚠️"}')
        ok_all &= (not on_disk)

        # ③ 复现旧流程：os.path.exists 检查会把它判为"文件不存在"
        print(f'\n③ 反证（旧流程 os.path.exists 前置检查）：')
        if not on_disk:
            print(f'   🔴 旧流程会报「{gl} 在磁盘上不存在」并 **sys.exit(1)**')
            print(f'   🔑 说明：仓库里一旦有 submodule，旧推送流程**完全不可用**')
        else:
            print('   ⚠️ 磁盘上竟然存在，无法复现')
    finally:
        subprocess.run(['git', 'rm', '-f', '--cached', gl],
                       capture_output=True, cwd=ROOT)
        try:
            os.remove(gl)
        except OSError:
            pass

    print()
    print('=' * 70)
    if ok_all:
        print('✅ gitlink 识别正确（mode 160000 · 无磁盘文件）')
        print('   🔑 但**推送流程仍未支持** —— 见下方诚实结论')
        print('=' * 70)
        return 0
    print('🔴 gitlink 识别不正确')
    print('=' * 70)
    return 1



def cmd_assert_history_known():
    """🔑 G396：历史遗留台账必须与**实测**一致（双向断言）。

    🔴 第一百零一轮诚实结论③：G394 **返回 0 即使发现问题**
       → 作为门禁它**永远通过**，靠人工读输出才发现，
       🔴 存在"门禁绿但问题在"的风险。
    🔑 本入口把遗留变成**可断言的事实**：台账 vs 实测，双向比对。

    | 方向 | 含义 | 处置 |
    |---|---|---|
    | 实测有 · 台账无 | 🔴 **新出现的遗留** | 阻断 |
    | 台账有 · 实测无 | 🔴 **台账过期**（遗留已消失＝历史被改写） | 阻断 |
    """
    print('=' * 70)
    print('🔑 **历史遗留台账断言**（G396 · 台账 vs 实测）')
    print('=' * 70)

    try:
        with open(HISTORY_KNOWN, encoding='utf-8') as f:
            rec = json.load(f)
    except FileNotFoundError:
        print(f'🔴 台账不存在：{HISTORY_KNOWN}')
        print('   先跑 `push_api.py --audit-history` 生成')
        return 1
    except Exception as e:
        print(f'🔴 台账不可读：{e} —— 拒绝给结论')
        return 1
    known = {r['sha']: r for r in rec.get('known_legacy', [])}
    print(f'\n🔑 台账 known_legacy {len(known)} 条'
          f' · 生成于 {rec.get("generated_at", "?")}')

    idx = local_index_entries()
    if not idx:
        print('🔴 无法确定 git 索引 mode —— 拒绝给结论')
        return 1
    want = {}
    for _m, _ in idx.values():
        want[_m] = want.get(_m, 0) + 1
    d = req('GET', f'{API}/commits?per_page=100')
    if '__err' in d or not isinstance(d, list):
        print('🔴 无法读取远端 commit 列表 —— **拒绝给结论**'
              '（远端不可达 ≠ 没有遗留）')
        return 1

    actual = {}
    for c in d:
        t = req('GET', f'{API}/git/trees/{c["sha"]}?recursive=1')
        if '__err' in t:
            print(f'⚠️ {c["sha"][:12]} 树读取失败 —— 跳过')
            continue
        dist = {}
        for it in t.get('tree', []):
            if it['type'] == 'blob':
                dist[it['mode']] = dist.get(it['mode'], 0) + 1
        odd = {m: n for m, n in dist.items() if m not in want}
        if odd:
            actual[c['sha'][:12]] = odd
    print(f'🔑 实测遗留 {len(actual)} 条（远端 {len(d)} commit）')

    new_ = sorted(set(actual) - set(known))
    gone = sorted(set(known) - set(actual))
    print()
    ok = True
    if new_:
        print(f'🔴 **新出现的遗留** {len(new_)} 条（实测有 · 台账无）：')
        for h in new_[:10]:
            print(f'   - {h}  {actual[h]}')
        print('   🔑 处置：跑 `--audit-history` 更新台账，'
              '并确认这不是**新引入**的推送缺陷')
        ok = False
    if gone:
        print(f'🔴 **台账过期** {len(gone)} 条（台账有 · 实测无）：')
        for h in gone[:10]:
            print(f'   - {h}  {known[h].get("msg", "")}')
        print('   🔑 含义：遗留**已消失** → 历史被改写过（force push）')
        print('      → 台账必须同步更新，否则它永远声称问题还在')
        ok = False

    print()
    print('=' * 70)
    if ok and actual:
        print(f'✅ 台账与实测一致：{len(actual)} 条已知遗留**未被掩盖**'
              f'（仍待人工决定是否 force push 修正）')
        print('=' * 70)
        return 0
    if ok and not actual:
        print('✅ 台账与实测一致：无历史遗留')
        print('=' * 70)
        return 0
    print('🔴 台账与实测**不一致** —— 遗留台账已失去断言能力')
    print('=' * 70)
    return 1


def main():
    msg = None
    # 🔑 第九十七轮：改用 **argparse**。
    #    🔴 原手写解析导致 `claim_verify.py` 的 `cmd:` 断言
    #       报"`--check-leak` 未在 argparse 中登记" —— 检查器是对的：
    #       手写解析的参数**无法被静态验证**，等于没有登记。
    import argparse as _ap
    ap = _ap.ArgumentParser(
        description='推送当前仓库到 GitHub（走 REST API）')
    ap.add_argument('-m', '--message', default=None,
                    help='commit message')
    ap.add_argument('--dry-run', action='store_true',
                    help='只统计，不推送')
    ap.add_argument('--check-leak', action='store_true',
                    help='G390：只检查是否会**静默漏传**（忘了 git add）')
    ap.add_argument('--allow-untracked', action='store_true',
                    help='明确接受漏传（不推荐）')
    ap.add_argument('--verify-push', action='store_true',
                    help='G391：**回读远端 tree** 并与本地逐条比对')
    ap.add_argument('--audit-history', action='store_true',
                    help='G394：历史 commit 权限审计（**只读**，不改写历史）')
    ap.add_argument('--assert-history-known', action='store_true',
                    help='G396：历史遗留台账与实测**双向**一致')
    ap.add_argument('--check-gitlink', action='store_true',
                    help='G395：gitlink（mode 160000）识别自测')
    ap.add_argument('--check-symlink', action='store_true',
                    help='G393：symlink（mode 120000）处理正确性**自测**')
    ap.add_argument('--report', action='store_true',
                    help='与 --verify-push 同用：**只报告不阻断**'
                         '（定期人工复核入口）')
    a = ap.parse_args()
    msg = a.message
    dry = a.dry_run
    allow_untracked = a.allow_untracked

    if a.audit_history:
        os.chdir(ROOT)
        return cmd_audit_history()

    if a.assert_history_known:
        os.chdir(ROOT)
        return cmd_assert_history_known()

    if a.check_gitlink:
        os.chdir(ROOT)
        return cmd_check_gitlink()

    if a.check_symlink:
        os.chdir(ROOT)
        return cmd_check_symlink()

    if a.verify_push:
        os.chdir(ROOT)
        return cmd_verify_push(report=a.report)

    if a.check_leak:
        # 🔑 G390：只做**漏传检查**，不统计不推送
        os.chdir(ROOT)
        u = check_untracked()
        if u is None:
            print('🔴 **无法确定**是否有漏传（git 不可用） —— 拒绝给结论')
            return 1
        if u:
            print(f'🔴 {len(u)} 个文件未纳入版本管理 —— 推送会**静默漏传**')
            for st, f in u[:10]:
                print(f'   [{st}] {f}')
            return 1
        print('✅ 无漏传风险：全部文件已纳入版本管理')
        return 0

    os.chdir(ROOT)

    os.chdir(ROOT)

    # 🔑 第九十七轮：**未纳入版本管理的文件检查**。
    #    🔴 第九十六轮诚实结论⑤：`push_api.py` 依赖 `git ls-files`，
    #       若某轮忘了 `git add`，新文件会被**悄悄漏传** ——
    #       而推送仍然"成功"，从输出完全看不出来。
    #    🔑 判据：`git status --porcelain` 里的 `??`（未跟踪）
    #       与已跟踪但**已删除**的文件，都必须在推送前处理。
    untracked = check_untracked()
    if untracked is None:
        print('\n🔴 **无法确定**是否有未纳入版本管理的文件'
              '（git 不可用或不在仓库内）')
        print('  🔑 这与"没有"是两回事 —— 拒绝推送，不静默放行')
        return 1
    if untracked:
        print(f'\n🔴 有 {len(untracked)} 个文件**未纳入版本管理**：')
        for st, f in untracked[:10]:
            print(f'   - [{st}] {f}')
        if len(untracked) > 10:
            print(f'   … 另 {len(untracked) - 10} 个')
        if allow_untracked:
            print('\n⚠️ `--allow-untracked` 已指定：**照常推送**，'
                  '上述文件**不会**出现在远端')
        else:
            print('\n🔑 处理办法：')
            print('   git add -A && git commit -m "说明"   ← 推荐')
            print('   或加 `--allow-untracked` 明确接受漏传（不推荐）')
            print('\n🔴 拒绝推送 —— 静默漏传比推送失败危险得多')
            return 1

    files = list_files()
    print(f'🔑 受管文件 {len(files)} 个')

    # 🔑 第一百轮修复：**gitlink（submodule）磁盘上没有文件**。
    #    🔴 旧流程用 `os.path.exists` 前置检查 → 一旦仓库有 submodule，
    #       会被判「N 个文件在磁盘上不存在」并 `sys.exit(1)`，
    #       🔴 **整个仓库都推不出去**（不是只漏传 submodule）。
    #    🔑 判据：gitlink 的"内容"是 submodule 的 commit sha，
    #        只存在于 **git 索引**里，磁盘上本就没有对应文件。
    idx_all = local_index_entries() or {}
    glinks = [f for f in files if idx_all.get(f, ('', ''))[0] == '160000']
    if glinks:
        print(f'🔑 其中 gitlink（submodule）{len(glinks)} 个'
              f' —— 无磁盘文件，按 commit 引用处理')
    miss = [f for f in files
            if f not in set(glinks) and not os.path.exists(f)]
    if miss:
        print(f'🔴 {len(miss)} 个文件在磁盘上不存在（中文路径问题？）:')
        for f in miss[:5]:
            print('  -', f)
        sys.exit(1)
    if dry:
        print('✅ --dry-run：未推送')
        return 0

    # 🔴 第九十九轮修复：**mode 必须取自 git 索引，不能看磁盘 x 位**。
    #    🔴 旧代码 `os.access(path, os.X_OK)` 在本沙盒里对**所有文件**
    #       都返回 True → 266 个文件**全部**被推成 100755，
    #       而 git 索引里其实全是 100644。
    #       —— 这是**前几轮推送一直存在、直到加了权限比对才暴露**的缺陷。
    #    🔑 判据：文件在仓库里"该是什么权限"由 **git 索引**决定，
    #       不由当前文件系统的挂载/umask 决定。
    idx = local_index_entries()
    if not idx:
        print('🔴 **无法确定** git 索引 mode —— 拒绝推送'
              '（否则会重演"全部推成 100755"）')
        sys.exit(1)

    # 🔑 gitlink 直接取**索引里的 sha**（就是 submodule 的 commit），
    #    不需要也不应该走 mk_blob（磁盘上没有内容可读）。
    tree = [{'path': p_, 'mode': '160000', 'type': 'commit',
             'sha': idx_all[p_][1]} for p_ in glinks]
    if tree:
        print(f'🔑 gitlink 条目已按 commit 引用加入 tree：{len(tree)} 个')

    _gs = set(glinks)
    fails = []
    with ThreadPoolExecutor(max_workers=8) as ex:
        for path, sha, err in ex.map(mk_blob,
                                     [f for f in files if f not in _gs]):
            if sha is None:
                fails.append((path, err))
            else:
                mode = idx.get(path, (None, None))[0]
                if not mode:
                    print(f'🔴 索引里查不到 {path} 的 mode —— 拒绝推送')
                    sys.exit(1)
                tree.append({'path': path, 'mode': mode,
                             'type': 'blob', 'sha': sha})
    _mc = {}
    for it in tree:
        _mc[it['mode']] = _mc.get(it['mode'], 0) + 1
    print(f'🔑 权限取自 git 索引：{_mc}')
    print(f'🔑 blob 成功 {len(tree)} / 失败 {len(fails)}')
    for p, e in fails[:5]:
        print('  🔴', p, e)
    if fails:
        sys.exit(1)

    t = req('POST', f'{API}/git/trees', {'tree': tree})
    if '__err' in t:
        print('🔴 tree 失败:', t)
        sys.exit(1)

    # 🔑 parent = 远程当前 main，保证历史连续
    parents = []
    ref_get = req('GET', f'{API}/git/ref/heads/main')
    if '__err' not in ref_get:
        parents = [ref_get['object']['sha']]

    if msg is None:
        msg = f'同步（{len(files)} 个文件）'
    c = req('POST', f'{API}/git/commits',
            {'message': msg, 'tree': t['sha'], 'parents': parents})
    if '__err' in c:
        print('🔴 commit 失败:', c)
        sys.exit(1)

    upd = req('PATCH', f'{API}/git/refs/heads/main',
              {'sha': c['sha'], 'force': False})
    if '__err' in upd:
        print('🔴 ref 更新失败:', upd)
        sys.exit(1)

    print(f'✅ 已推送 commit {c["sha"][:12]}'
          f'（parent {parents[0][:12] if parents else "无"}）')

    # 🔑 G391：推送后**必须回读验证** —— "我发了" ≠ "对面收到了"
    print()
    vr = cmd_verify_push(report=False)   # 🔴 推送后必须严格，不用报告模式
    if vr != 0:
        print('\n🔴 推送后验证未通过 —— 上面那句"已推送"不能当作完成')
        return vr
    print(f'   {len(files)} 个文件 · '
          f'https://github.com/{OWNER}/{REPO}/commit/{c["sha"][:12]}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
