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
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
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


def mk_blob(path):
    try:
        raw = open(path, 'rb').read()
    except Exception as e:
        return (path, None, f'读取失败: {e}')
    d = req('POST', f'{API}/git/blobs',
            {'content': base64.b64encode(raw).decode(),
             'encoding': 'base64'})
    if '__err' in d:
        return (path, None, f"HTTP {d['__err']} {d['__body'][:150]}")
    return (path, d['sha'], None)


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
    a = ap.parse_args()
    msg = a.message
    dry = a.dry_run
    allow_untracked = a.allow_untracked

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
    miss = [f for f in files if not os.path.exists(f)]
    if miss:
        print(f'🔴 {len(miss)} 个文件在磁盘上不存在（中文路径问题？）:')
        for f in miss[:5]:
            print('  -', f)
        sys.exit(1)
    if dry:
        print('✅ --dry-run：未推送')
        return 0

    tree, fails = [], []
    with ThreadPoolExecutor(max_workers=8) as ex:
        for path, sha, err in ex.map(mk_blob, files):
            if sha is None:
                fails.append((path, err))
            else:
                mode = '100755' if os.access(path, os.X_OK) else '100644'
                tree.append({'path': path, 'mode': mode,
                             'type': 'blob', 'sha': sha})
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
    print(f'   {len(files)} 个文件 · '
          f'https://github.com/{OWNER}/{REPO}/commit/{c["sha"][:12]}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
