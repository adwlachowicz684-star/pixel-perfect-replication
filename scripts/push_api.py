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
import hashlib
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
# 🔑 第一百零三轮：台账里每条遗留**最多记多少个异常文件路径**。
LEGACY_SAMPLE_N = 10
# 🔑 `--show-legacy-files` 每个 commit **最多打印多少个路径**（避免刷屏）
LEGACY_SHOW_N = 20
# 🔑 第一百零四轮：完整异常文件清单**落盘目录**（使"哪些文件不对"离线可答）
LEGACY_FILES_DIR = os.path.join(ROOT, 'audit', 'history_mode_files')
_LAST_DETAILS = {}


def _rec_body(rec):
    """台账**去掉 generated_at 后**的内容 —— 用于幂等比对。

    🔑 判据：`generated_at` 每次跑都变，**不能**作为"台账变了"的依据。
    """
    return json.dumps({k: v for k, v in rec.items()
                       if k != 'generated_at'},
                      ensure_ascii=False, sort_keys=True)
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
    except Exception as e:
        # 🔑 第一百零四轮：**网络层不可达**（DNS 失败 / 超时 / 连接重置）
        #    必须返回 `__err`，而不是抛出。
        #    🔴 断网实测时发现：只捕 HTTPError → URLError 直接抛出 →
        #       脚本**崩溃**而非"拒绝给结论"，调用方无法区分
        #       "远端不可达"与"代码有 bug"。
        return {'__err': f'NET:{type(e).__name__}:{e}'}



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


def _baseline_fp(want):
    """🔑 **基准指纹**：当前 git 索引基准 `want` 的 sha1。

    🔑 第一百零七轮：只记 `baseline_modes`（分布）**不够** ——
       🔴 第一百零六轮实测暴露：把 README.md 在索引里改成 100755
          → 100755 进入基准 → 历史遗留**集体消失**。
       🔴 此时 `--assert-history-known` 会报"台账过期"，
          但**没人解释"为什么突然没了"** —— 可能是修好了，
          也可能是**基准松了**。两者必须区分。
    """
    return hashlib.sha1(json.dumps(want or {}, sort_keys=True,
                                   ensure_ascii=False).encode()
                        ).hexdigest()

def _dirty_tracked():
    """🔑 返回**已跟踪但未提交修改**的文件列表；`None` 表示无法确定。

    🔑 第一百零六轮：只看 `M`/` M`/`MM`/`AM` 等"已跟踪且内容变了"的状态，
       🔴 **不看** `??`（未跟踪）—— 那是 G390 的职责，两者语义不同。
    """
    import subprocess
    try:
        proc = subprocess.run(
            ['git', '-c', 'core.quotepath=false', 'status', '--porcelain',
             '-z'],
            capture_output=True, text=True, timeout=120, cwd=ROOT)
        if proc.returncode != 0:
            return None
    except Exception:
        return None
    out = []
    for item in proc.stdout.split('\0'):
        if not item.strip():
            continue
        st = item[:2]
        path = item[3:]
        if st.strip() == '?':      # 🔑 ?? = 未跟踪 → G390 管，此处不管
            continue
        if st.strip():             # 已跟踪且有变化（含 M/A/D/R 等）
            out.append(path)
    return out

def cmd_assert_baseline_fp():
    """🔑 G400：**基准指纹断言** —— 防止"基准松了"被读成"历史被修好"。

    🔴 第一百零六轮诚实结论⑥（本轮要解决的那一条）：
       把 README.md 在 git 索引里改成 100755 → 100755 进入基准 →
       **历史遗留集体消失**（异常文件数 0）。
       此时 `--assert-history-known` 只会报"台账过期"，
       🔴 **没有任何东西解释"为什么突然没了"**。
       —— 可能是真的修好了，也可能是**基准松了**。

    🔑 判据（两条，缺一不可）：
       ① 台账**必须**有 `baseline_fp`（缺失 → 拒绝给结论，不静默）
       ② `baseline_fp` 必须**等于**当前 git 索引基准的指纹
          （不等 → 基准被改过，遗留数量变化的含义已不同）
    """
    print('🔑 **基准指纹断言**（G400）')
    print('=' * 70)
    idx = local_index_entries()
    if not idx:
        print('🔴 无法取得本地 git 索引 —— 拒绝给结论')
        return 1
    want = {}
    for _pp, (_m, _h) in idx.items():
        want[_m] = want.get(_m, 0) + 1
    cur_fp = _baseline_fp(want)

    try:
        with open(HISTORY_KNOWN, encoding='utf-8') as f:
            rec = json.load(f)
    except FileNotFoundError:
        print(f'🔴 台账不存在：{os.path.relpath(HISTORY_KNOWN, ROOT)}')
        print('   —— 尚未审计过，无法断言基准是否被改过')
        return 1
    except ValueError as e:
        print(f'🔴 台账解析失败：{e} —— 拒绝给结论')
        return 1

    fp = rec.get('baseline_fp')
    if not fp:
        print('🔴 台账**缺少 baseline_fp** —— 无法判断基准是否被改过，'
              '拒绝给结论')
        print('   🔑 修复：重跑 --audit-history')
        print('=' * 70)
        return 1

    print(f'   台账基准指纹 {fp[:12]}')
    print(f'   实测基准指纹 {cur_fp[:12]}')
    print(f'   基准分布     {rec.get("baseline_modes")}')
    if fp != cur_fp:
        print(f'\n🔴 **基准已被改过**：{fp[:8]} → {cur_fp[:8]}')
        print('   🔴 遗留数量的任何变化都**不能**读作"修复" ——')
        print('      基准松了 → 旧异常不再算异常 → 遗留"消失"；')
        print('      基准收紧 → 原本正常的文件变成异常 → 遗留"增加"。')
        print('   🔑 必须重跑 --audit-history 重建台账后再下结论')
        print('=' * 70)
        return 1
    print()
    print(f'✅ 基准指纹一致（{cur_fp[:8]}）'
          f' —— 遗留数量可安全比较')
    print('=' * 70)
    return 0

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

    # ⑤ 🔑 第一百零六轮：**本地有未提交的修改**
    #    🔴 实测事故：commit 之后又跑了会写产物的自检入口
    #       （--audit-history 重写了 history_mode_known.json）→
    #       工作区变脏 → 推送的内容是**旧 commit**的，
    #       而"本地文件"是新的 → 内容不一致。
    #    🔑 这一层把"commit 与 push 之间不该再跑写文件的命令"
    #       变成**可断言的事实**。
    dirty = _dirty_tracked()
    if dirty is None:
        print('🔴 **无法确定**本地是否有未提交修改（git 不可用）'
              ' —— 拒绝给结论')
        print('=' * 70)
        return 1
    if dirty:
        print(f'🔴 **本地有 {len(dirty)} 个未提交的修改** —— '
              f'推送的是 commit 的内容，不是当前工作区：')
        for p_ in dirty[:10]:
            print(f'   - {p_}')
        print('   🔑 成因通常是：commit 之后又跑了会写产物的入口'
              '（如 --audit-history / --dump-legacy-files）')

    bad = len(missing) + len(diff) + len(mode_diff) + len(dirty)
    print()
    print('=' * 70)
    if bad:
        print(f'🔴 **{"远端与本地不一致" if report else "推送不完整"}**：'
              f'缺失 {len(missing)} · 内容不一致 {len(diff)} · '
              f'权限不一致 {len(mode_diff)} · 未提交修改 {len(dirty)}')
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
    details = {}          # 🔑 第一百零三轮：文件级明细（供 --show-legacy-files）
    for c in d:
        sha = c['sha']
        t = req('GET', f'{API}/git/trees/{sha}?recursive=1')
        if '__err' in t:
            print(f"⚠️ {sha[:12]} 树读取失败 HTTP {t['__err']} —— 跳过")
            continue
        dist = {}
        odd_paths = {}    # mode -> [path, ...]（**排序**，保证确定性）
        for it in t.get('tree', []):
            if it['type'] != 'blob':
                continue
            dist[it['mode']] = dist.get(it['mode'], 0) + 1
            if it['mode'] not in want:
                odd_paths.setdefault(it['mode'], []).append(it['path'])
        msg = c['commit']['message'].splitlines()[0][:34]
        # 🔑 判据：与该 commit **当时**应有的 mode 无法自动得知，
        #    故用**当前索引基准**比对：出现索引里**没有**的 mode 即为异常。
        odd = {m: n for m, n in dist.items() if m not in want}
        if odd:
            for _m in odd_paths:
                odd_paths[_m].sort()
            flat = sorted(p for ps in odd_paths.values() for p in ps)
            # 🔑 清单指纹：全部异常路径排序后拼串的 sha1。
            #    🔴 只记数量会被"数量相同但文件不同"蒙混。
            fp = hashlib.sha1('\n'.join(flat).encode('utf-8')).hexdigest()
            ent = {'sha': sha[:12], 'msg': msg, 'odd_modes': odd,
                   'odd_count': len(flat),
                   'odd_sample': flat[:LEGACY_SAMPLE_N],
                   'odd_sample_truncated': len(flat) > LEGACY_SAMPLE_N,
                   'odd_paths_sha': fp,
                   # 🔑 第一百零六轮：**应有 mode 基准**必须写进台账。
                   #    🔴 破坏②实测发现：台账里没有这个字段 →
                   #       "应有 mode 是否凭空捏造"**根本无从校验**，
                   #       检查**静默跳过**（rc=0）而破坏**没被拦住**。
                   #    🔑 这是"读不到 ≠ 没有"的镜像：
                   #       不仅要区分，还必须在缺失时**拒绝给结论**。
                   'baseline_modes': dict(want)}
            bad.append((sha[:12], msg, odd, dist, ent))
            details[sha[:12]] = flat
            print(f'🔴 {sha[:12]}  {msg}')
            print(f'     异常 mode {odd}   全分布 {dist}'
                  f'   异常文件 {len(flat)} 个')
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
    prev = None
    try:
        with open(HISTORY_KNOWN, encoding='utf-8') as f:
            prev = json.load(f)
    except (FileNotFoundError, ValueError):
        pass
    cur_fp = _baseline_fp(want)
    rec = {
        'generated_at': time.strftime('%Y-%m-%dT%H:%M:%S%z'),
        'baseline_modes': want,
        # 🔑 第一百零七轮：**基准指纹** —— 让"基准是否被改过"可断言。
        #    🔴 只有 baseline_modes 时，"基准松了导致遗留消失"
        #       与"历史被修好导致遗留消失"**无法区分**。
        'baseline_fp': cur_fp,
        'checked_commits': len(d),
        # 🔑 第一百零三轮：每条含**文件级**信息：
        #    odd_count（异常文件总数）· odd_sample（排序后前 N 个路径）
        #    · odd_paths_sha（全部异常路径的指纹）
        #    🔴 上一轮只有 odd_modes（数量）→ 无法回答"哪些文件不对"，
        #       且"数量相同但文件不同"会被蒙混。
        'known_legacy': [e[4] for e in bad],
        'note': '历史 commit 的 mode 与当前 git 索引基准不一致。'
                ' 修正需 force push（破坏性），本脚本只读不改写。'
                ' 本台账由 G396/G397 双向断言，不得手工静默删改。',
    }
    # 🔑 第一百零七轮：**基准漂移**必须被明确报出
    prev_fp = (prev or {}).get('baseline_fp') if prev is not None else None
    prev_n = len((prev or {}).get('known_legacy', []) or [])
    cur_n = len(bad)
    if prev is not None and prev_fp and prev_fp != cur_fp:
        print(f'\n🔴 **基准已变**：指纹 {prev_fp[:8]} → {cur_fp[:8]}')
        print(f'   基准分布：{(prev or {}).get("baseline_modes")} → {want}')
        if cur_n < prev_n:
            print(f'🔴 遗留 {prev_n} → {cur_n} 条 **减少** —— '
                  f'这是"**消失**"不是"**被修复**"：'
                  f'基准松了，旧异常不再算异常')
        elif cur_n > prev_n:
            print(f'🔴 遗留 {prev_n} → {cur_n} 条 **增加** —— '
                  f'基准收紧，原本正常的文件变成异常')
        else:
            print(f'⚠️ 遗留数量不变（{prev_n}），但**判定基准本身变了** '
                  f'—— 结论的含义已不同')

    try:
        os.makedirs(os.path.dirname(HISTORY_KNOWN), exist_ok=True)
        # 🔑 幂等写入：除 generated_at 外内容一致 → **不重写**。
        #    🔴 上一轮问题③：generated_at 每次都变 → 台账**必然变脏**，
        #       但 G396 不比对它 → "跑一次就更新一次"永远发现不了。
        #    🔑 现在只在**内容真变**时才改时间戳。
        if prev is not None and _rec_body(prev) == _rec_body(rec):
            print(f'\n🔑 台账内容未变 —— **不重写**（避免时间戳抖动）：'
                  f'{os.path.relpath(HISTORY_KNOWN, ROOT)}')
        else:
            with open(HISTORY_KNOWN, 'w', encoding='utf-8') as f:
                json.dump(rec, f, ensure_ascii=False, indent=2)
            print(f'\n🔑 台账已写：{os.path.relpath(HISTORY_KNOWN, ROOT)}'
                  f' · known_legacy {len(rec["known_legacy"])} 条')
    except Exception as e:
        print(f'\n🔴 台账写入失败：{e} —— 遗留无法被 G396/G397 断言')
        return 1
    # 🔑 供 --show-legacy-files 在同一进程内复用
    global _LAST_DETAILS
    _LAST_DETAILS = details
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



def cmd_show_legacy_files(a):
    """🔑 列出某历史 commit 中 **mode 异常的具体文件**（人工可查）。

    🔴 第一百零二轮诚实结论②：台账只记 mode 与数量，
       **无法回答"哪些文件被推成 100755"**。
    🔑 本入口回答这个问题：给定 commit（默认台账里第一条），
       列出全部异常文件路径。

    🔑 用法：`--show-legacy-files [SHA前缀]`；省略则列**全部**遗留 commit。
    """
    print('=' * 70)
    print('🔑 **历史遗留文件清单**（哪些文件的 mode 不对）')
    print('=' * 70)
    want_arg = (getattr(a, 'show_legacy_files') or '').strip()
    try:
        with open(HISTORY_KNOWN, encoding='utf-8') as f:
            rec = json.load(f)
    except FileNotFoundError:
        print(f'🔴 台账不存在：{HISTORY_KNOWN} —— 先跑 --audit-history')
        return 1
    except Exception as e:
        print(f'🔴 台账不可读：{e} —— 拒绝给结论')
        return 1

    want = set()
    for _m, _ in (local_index_entries() or {}).values():
        want.add(_m)
    if not want:
        print('🔴 无法确定当前索引 mode 基准 —— 拒绝给结论')
        return 1

    targets = rec.get('known_legacy', [])
    if want_arg:
        targets = [t for t in targets if t['sha'].startswith(want_arg)]
        if not targets:
            print(f'🔴 台账里没有 sha 以 {want_arg!r} 开头的遗留')
            return 1

    total = 0
    for t in targets:
        # 🔑 第一百零四轮：**优先读本地落盘清单**（离线可答）。
        #    🔴 上一轮问题：完整清单只在远端 → 远端不可达就回答不了。
        fp = os.path.join(LEGACY_FILES_DIR, t['sha'] + '.txt')
        if os.path.isfile(fp):
            try:
                with open(fp, encoding='utf-8') as f:
                    _raw = [ln for ln in f.read().splitlines() if ln]
                # 🔑 每行 = `mode\tpath`；兼容旧版纯 path
                paths = [(ln.split('\t')[-1] if '\t' in ln else ln)
                         for ln in _raw]
                modes = sorted({(ln.split('\t')[0] if '\t' in ln
                                 else '?') for ln in _raw})
                exp_modes = sorted({ln.split('\t')[1] for ln in _raw
                                    if ln.count('\t') >= 2})
                src = '本地落盘'
            except Exception as e:
                print(f'\n🔴 {t["sha"]} 落盘清单不可读：{e} —— 拒绝给结论')
                return 1
        else:
            print(f'\n⚠️ {t["sha"]} 无落盘清单 —— 回退远端查询'
                  f'（离线时此处将失败；用 --dump-legacy-files 生成）')
            d = req('GET', f'{API}/git/trees/{t["sha"]}?recursive=1')
            if '__err' in d:
                print(f'🔴 远端也不可达 HTTP {d["__err"]} —— 拒绝给结论')
                return 1
            paths = sorted(it['path'] for it in d.get('tree', [])
                           if it['type'] == 'blob' and it['mode'] not in want)
            modes = sorted({it['mode'] for it in d.get('tree', [])
                            if it['type'] == 'blob'
                            and it['mode'] not in want})
            exp_modes = []
            src = '远端'
        total += len(paths)
        print(f'\n### {t["sha"]}  {t.get("msg", "")}   [来源：{src}]')
        print(f'    mode 异常文件 **{len(paths)} 个**'
              f'（台账记 odd_count={t.get("odd_count", "?")}）')
        if modes:
            print(f'    异常 mode：{modes}'
                  + (f' → 应有 {exp_modes}' if exp_modes else ''))
        if t.get('odd_count') != len(paths):
            print(f'    🔴 与台账 odd_count **不一致** —— 台账已过期')
        for p_ in paths[:LEGACY_SHOW_N]:
            print(f'      - {p_}')
        if len(paths) > LEGACY_SHOW_N:
            print(f'      … 另 {len(paths) - LEGACY_SHOW_N} 个'
                  f'（全部 {len(paths)} 个已计入 odd_paths_sha）')

    print()
    print('=' * 70)
    print(f'🔑 共 {total} 个文件路径分布在 {len(targets)} 个 commit')
    print('=' * 70)
    return 0


def cmd_assert_legacy_files():
    """🔑 G397：**文件级**遗留断言（odd_count / odd_paths_sha 与实测一致）。

    🔴 第一百零二轮诚实结论②：台账只记数量，
       🔴 "数量相同但文件不同"会被 G396 蒙混过去。
    🔑 G397 补上文件级：逐条比对 `odd_count` 与 `odd_paths_sha`。

    | 层 | 比什么 | 防什么 |
    |---|---|---|
    | G396 | **有哪些 commit** 有遗留 | 新遗留 / 台账过期 |
    | **G397** | 每个 commit **有哪些文件** | 数量对但文件变了 |
    """
    print('=' * 70)
    print('🔑 **文件级遗留断言**（G397 · odd_count / odd_paths_sha）')
    print('=' * 70)
    try:
        with open(HISTORY_KNOWN, encoding='utf-8') as f:
            rec = json.load(f)
    except FileNotFoundError:
        print(f'🔴 台账不存在：{HISTORY_KNOWN}')
        return 1
    except Exception as e:
        print(f'🔴 台账不可读：{e} —— 拒绝给结论')
        return 1

    known = {r['sha']: r for r in rec.get('known_legacy', [])}
    # ① 结构完整性：每条都**必须**有文件级字段
    need = ('odd_count', 'odd_sample', 'odd_paths_sha',
            'odd_sample_truncated')
    miss = [h for h, r in known.items() if any(k not in r for k in need)]
    print(f'\n① 台账 {len(known)} 条 · 文件级字段齐全？'
          f'{"✅" if not miss else "🔴"}')
    if miss:
        for h in miss[:10]:
            lack = [k for k in need if k not in known[h]]
            print(f'   🔴 {h} 缺少 {lack}')
        print('   🔑 处置：重跑 `--audit-history` 生成新格式台账')
        print('=' * 70)
        return 1

    idx = local_index_entries()
    if not idx:
        print('🔴 无法确定 git 索引 mode —— 拒绝给结论')
        return 1
    want = {}
    for _m, _ in idx.values():
        want[_m] = want.get(_m, 0) + 1
    d = req('GET', f'{API}/commits?per_page=100')
    if '__err' in d or not isinstance(d, list):
        print('🔴 无法读取远端 commit 列表 —— **拒绝给结论**')
        return 1

    print('\n② 逐条比对（台账 vs 实测）')
    bad_c, bad_s = [], []
    for h, r in sorted(known.items()):
        t = req('GET', f'{API}/git/trees/{h}?recursive=1')
        if '__err' in t:
            print(f'   ⚠️ {h} 树读取失败 —— 跳过')
            continue
        paths = sorted(it['path'] for it in t.get('tree', [])
                       if it['type'] == 'blob' and it['mode'] not in want)
        fp = hashlib.sha1('\n'.join(paths).encode('utf-8')).hexdigest()
        c_ok = (r['odd_count'] == len(paths))
        s_ok = (r['odd_paths_sha'] == fp)
        tag = '✅' if (c_ok and s_ok) else '🔴'
        print(f'   {tag} {h}  count 台账{r["odd_count"]}'
              f'/实测{len(paths)}  sha '
              f'{r["odd_paths_sha"][:8]}/{fp[:8]}')
        if not c_ok:
            bad_c.append(h)
        if not s_ok:
            bad_s.append(h)

    print()
    print('=' * 70)
    if bad_c or bad_s:
        print(f'🔴 文件级不一致：odd_count {len(bad_c)} 条'
              f' · odd_paths_sha {len(bad_s)} 条')
        print('   🔑 含义：遗留的**具体文件**变了，'
              '数量恰好相同也会被测出')
        print('=' * 70)
        return 1
    print(f'✅ {len(known)} 条遗留的文件级信息与实测一致'
          f'（count + 路径指纹双向）')
    print('=' * 70)
    return 0



def cmd_dump_legacy_files():
    """🔑 把每个遗留 commit 的**完整**异常文件清单**落盘**。

    🔴 第一百零三轮诚实结论①：`odd_sample` 只存前 10 个，
       完整清单**只在远端** —— 远端不可达时「哪些文件不对」**又回答不了**。
    🔑 本入口把完整清单写到 `audit/history_mode_files/<sha>.txt`，
       使该问题**离线可答**。

    🔑 判据：落盘内容 = 全部异常路径**排序**后逐行。
       与 `odd_paths_sha` 同源（同一份排序列表），故二者可互相校验。
    """
    print('=' * 70)
    print('🔑 **落盘：遗留文件完整清单**（使"哪些文件不对"离线可答）')
    print('=' * 70)
    try:
        with open(HISTORY_KNOWN, encoding='utf-8') as f:
            rec = json.load(f)
    except FileNotFoundError:
        print(f'🔴 台账不存在：{HISTORY_KNOWN} —— 先跑 --audit-history')
        return 1
    except Exception as e:
        print(f'🔴 台账不可读：{e} —— 拒绝给结论')
        return 1

    idx = local_index_entries()
    if not idx:
        print('🔴 无法确定 git 索引 mode 基准 —— 拒绝给结论')
        return 1
    want = {}
    for _m, _ in idx.values():
        want[_m] = want.get(_m, 0) + 1

    d = req('GET', f'{API}/commits?per_page=100')
    if '__err' in d or not isinstance(d, list):
        print('🔴 无法读取远端 commit 列表 —— **拒绝给结论**'
              '（远端不可达 ≠ 没有遗留）')
        return 1

    known = {r['sha']: r for r in rec.get('known_legacy', [])}
    os.makedirs(LEGACY_FILES_DIR, exist_ok=True)
    n_write = 0
    bad_fp = []
    for h in sorted(known):
        t = req('GET', f'{API}/git/trees/{h}?recursive=1')
        if '__err' in t:
            print(f'   ⚠️ {h} 树读取失败 HTTP {t["__err"]} —— 跳过')
            continue
        # 🔑 第一百零五轮：落盘每行 = `mode\tpath`
        #    🔴 上一轮只有 path —— 答不了"这个文件是 100755 还是 100664"。
        #    🔑 排序**只按 path**（不按 (mode,path)），因为台账的
        #       odd_paths_sha 也是按 path 排的 —— 两者必须**同源**。
        # 🔑 第一百零六轮（后半）：三列 `实际mode\t应有mode\tpath`
        #    🔑 **逐文件**取自当前 git 索引 —— 不是"取最多的那个"。
        #    🔴 第一百零六轮诚实结论②：基准若有两种 mode，
        #       "取最多的"就是**猜的**。逐文件取才是证据。
        #    🔑 文件已不在当前索引（历史新增/改名/删除）→ 回退到
        #       "基准里出现最多"，并**计数透明报出**。
        fallback = (max(want.items(), key=lambda kv: kv[1])[0]
                    if want else '100644')
        idx = local_index_entries() or {}
        n_idx = n_fb = 0
        entries = []
        for it in t.get('tree', []):
            if it['type'] != 'blob' or it['mode'] in want:
                continue
            pp = it['path']
            w = idx.get(pp, (None, None))[0]
            if w:
                n_idx += 1
            else:
                w = fallback
                n_fb += 1
            entries.append((it['mode'], w, pp))
        entries.sort(key=lambda x: x[2])
        print(f'   🔑 {h} 应有 mode 来源：索引 {n_idx} 个 · '
              f'回退(不在当前索引) {n_fb} 个 → {fallback}')
        paths = [pp for _m, _w, pp in entries]
        fp = hashlib.sha1('\n'.join(paths).encode('utf-8')).hexdigest()
        # 🔑 与台账指纹**同源校验**：不一致说明两者不是同一份数据
        if known[h].get('odd_paths_sha') != fp:
            bad_fp.append(h)
        fp_out = os.path.join(LEGACY_FILES_DIR, h + '.txt')
        # 🔑 幂等：内容一致不重写
        body = ''.join(f'{_m}\t{_w}\t{_p}\n' for _m, _w, _p in entries)
        try:
            prev = None
            if os.path.isfile(fp_out):
                with open(fp_out, encoding='utf-8') as f:
                    prev = f.read()
            if prev == body:
                print(f'   🔑 {h}  清单未变 —— 不重写（{len(paths)} 个）')
            else:
                with open(fp_out, 'w', encoding='utf-8') as f:
                    f.write(body)
                print(f'   ✅ {h}  已落盘 {len(paths)} 个路径')
                n_write += 1
        except Exception as e:
            print(f'   🔴 {h} 落盘失败：{e}')
            return 1

    print()
    print('=' * 70)
    # 🔑 清理**僵尸清单**：目录里有但台账没有（遗留已消失）
    try:
        have = {f[:-4] for f in os.listdir(LEGACY_FILES_DIR)
                if f.endswith('.txt')}
    except Exception as e:
        print(f'🔴 无法读取落盘目录：{e}')
        return 1
    zombie = sorted(have - set(known))
    if zombie:
        print(f'🔴 **僵尸清单** {len(zombie)} 个（目录有 · 台账无）：'
              f'{zombie[:5]}')
        print('   🔑 含义：遗留已消失（历史被改写），清单必须同步删除')
        print('=' * 70)
        return 1
    if zombie == [] and have:
        print(f'🔑 无僵尸清单（目录 {len(have)} 个 == 台账 '
              f'{len(known)} 条）')
    if bad_fp:
        print(f'🔴 落盘内容指纹与台账 odd_paths_sha 不一致：{bad_fp[:5]}')
        print('   🔑 两者必须**同源**（同一份排序列表）')
        print('=' * 70)
        return 1
    print(f'✅ 落盘完成：{len(have)} 份清单，本次重写 {n_write} 份')
    print('=' * 70)
    return 0


def cmd_assert_legacy_dump():
    """🔑 G398：**落盘清单**与实测一致（且离线可答）。

    🔴 第一百零三轮诚实结论①：完整清单只在远端 → 离线回答不了。
    🔑 G398 断言三件事：
       ① 台账每条**必须有**对应落盘清单（不得缺）
       ② 落盘内容指纹 == 台账 `odd_paths_sha`（**同源**）
       ③ 落盘行数 == 台账 `odd_count`
    🔑 与 G397 的区别：G397 查**远端**，G398 查**本地落盘** ——
       🔴 二者不可互相替代：G397 防台账撒谎，G398 防"离线答不了"。
    """
    print('=' * 70)
    print('🔑 **落盘清单断言**（G398 · 离线可答 + 与台账同源）')
    print('=' * 70)
    try:
        with open(HISTORY_KNOWN, encoding='utf-8') as f:
            rec = json.load(f)
    except FileNotFoundError:
        print(f'🔴 台账不存在：{HISTORY_KNOWN}')
        return 1
    except Exception as e:
        print(f'🔴 台账不可读：{e} —— 拒绝给结论')
        return 1
    known = {r['sha']: r for r in rec.get('known_legacy', [])}
    print(f'\n① 台账 {len(known)} 条')

    # ② 目录必须可读（不可读 ≠ 没有）
    if not os.path.isdir(LEGACY_FILES_DIR):
        print(f'🔴 落盘目录不存在：{LEGACY_FILES_DIR}')
        print('   先跑 `push_api.py --dump-legacy-files`')
        return 1
    try:
        have = sorted(f[:-4] for f in os.listdir(LEGACY_FILES_DIR)
                      if f.endswith('.txt'))
    except Exception as e:
        print(f'🔴 落盘目录不可读：{e} —— 拒绝给结论')
        return 1
    print(f'② 落盘清单 {len(have)} 份')

    miss = sorted(set(known) - set(have))
    extra = sorted(set(have) - set(known))
    print('\n③ 逐份比对（落盘 vs 台账）')
    ok = True
    if miss:
        print(f'   🔴 **缺清单** {len(miss)} 份：{miss[:10]}')
        ok = False
    if extra:
        print(f'   🔴 **僵尸清单** {len(extra)} 份：{extra[:10]}')
        ok = False

    for h in sorted(set(known) & set(have)):
        fp = os.path.join(LEGACY_FILES_DIR, h + '.txt')
        try:
            with open(fp, encoding='utf-8') as f:
                lines = [ln for ln in f.read().splitlines() if ln]
        except Exception as e:
            print(f'   🔴 {h} 不可读：{e}')
            ok = False
            continue
        # ② 每行必须是 `mode\tpath`
        recs, bad_line = [], []
        for ln in lines:
            n_tab = ln.count('\t')
            if n_tab < 2:
                bad_line.append(ln[:60])
                continue
            _m, _w, _pp = ln.split('\t', 2)
            recs.append((_m, _w, _pp))
        paths = [_pp for _m, _w, _pp in recs]
        fp_sha = hashlib.sha1('\n'.join(paths).encode('utf-8')).hexdigest()
        c_ok = known[h].get('odd_count') == len(paths)
        s_ok = known[h].get('odd_paths_sha') == fp_sha
        # ③ **内部自洽**：落盘里的 mode 必须是台账记录的 odd_modes 之一
        #    🔑 答得了"哪个文件的哪个权限不对"，且**不与台账自相矛盾**
        want_modes = set(known[h].get('odd_modes', {}).keys())
        modes = sorted({_m for _m, _w, _pp in recs})
        unknown_modes = sorted(set(modes) - want_modes) if want_modes else []
        # ④ 🔑 "应有 mode" 必须在台账 baseline_modes 内
        #    🔴 否则"本应是什么"是凭空捏造的值
        base_modes = set(known[h].get('baseline_modes') or {})
        exp_modes = sorted({_w for _m, _w, _pp in recs})
        # 🔴 字段缺失 → **拒绝给结论**，不得静默跳过
        #    （第一百零六轮破坏②实测：静默跳过会让破坏 rc=0）
        if not base_modes:
            print(f'   🔴 {h} 台账**缺少 baseline_modes** —— '
                  f'无法判断"应有 mode"是否凭空捏造，拒绝给结论')
            ok = False
            continue
        bad_exp = sorted(set(exp_modes) - base_modes)
        if bad_line:
            print(f'   🔴 {h}  {len(bad_line)} 行格式不对（应为 '
                  f'实际mode\t应有mode\tpath）：{bad_line[:2]}')
            ok = False
            continue
        if unknown_modes:
            print(f'   🔴 {h} 落盘 mode {unknown_modes} **不在**台账 '
                  f'odd_modes {sorted(want_modes)} —— 落盘与台账自相矛盾')
            ok = False
            continue
        if bad_exp:
            print(f'   🔴 {h} "应有 mode" {bad_exp} **不在**台账 '
                  f'baseline_modes {sorted(base_modes)} —— 是凭空捏造的值')
            ok = False
            continue
        if c_ok and s_ok:
            print(f'   ✅ {h}  {len(paths)} 行 · 指纹 {fp_sha[:8]} 一致'
                  f' · 实际 {modes} → 应有 {exp_modes}')
        else:
            print(f'   🔴 {h}  行数 台账{known[h].get("odd_count")}'
                  f'/落盘{len(paths)}  指纹 '
                  f'{str(known[h].get("odd_paths_sha"))[:8]}/{fp_sha[:8]}')
            ok = False

    print()
    print('=' * 70)
    if ok:
        print(f'✅ {len(known)} 条遗留的完整清单**已落盘且与台账同源**'
              f' —— 离线可答"哪些文件不对"')
        print('=' * 70)
        return 0
    print('🔴 落盘清单与台账不一致 —— "哪些文件不对"无法离线回答')
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
    ap.add_argument('--dump-legacy-files', action='store_true',
                    help='把遗留 commit 的**完整**异常文件清单落盘')
    ap.add_argument('--assert-legacy-dump', action='store_true',
                    help='G398：落盘清单与台账同源（离线可答）')
    ap.add_argument('--show-legacy-files', nargs='?', const='',
                    metavar='SHA前缀',
                    help='列出历史 commit 中 **mode 异常的具体文件**')
    ap.add_argument('--assert-legacy-files', action='store_true',
                    help='G397：文件级遗留断言（odd_count / odd_paths_sha）')
    ap.add_argument('--assert-baseline-fp', action='store_true',
                    help='G400：断言基准指纹未被改过（防遗留“消失”被误读成“修复”）')
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

    if a.dump_legacy_files:
        os.chdir(ROOT)
        return cmd_dump_legacy_files()

    if a.assert_legacy_dump:
        os.chdir(ROOT)
        return cmd_assert_legacy_dump()

    if a.show_legacy_files is not None:
        os.chdir(ROOT)
        return cmd_show_legacy_files(a)

    if a.assert_legacy_files:
        os.chdir(ROOT)
        return cmd_assert_legacy_files()

    if a.assert_baseline_fp:
        return cmd_assert_baseline_fp()
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
