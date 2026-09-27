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
import glob
import hashlib
import json
import os
import shutil
# 🔑 第一百一十九轮**根治**：本文件原**没有顶层** import subprocess，
#    只在各函数内 import —— 已导致**四次** NameError（84 轮 ROOT、111 轮 glob、
#    118 轮与 119 轮 subprocess）。
#    🔴 前三次改法都是「在函数里补一行 import」—— 治标：下一个新函数还会再犯。
#    ✅ 治本：改为**顶层导入**，新函数无需记得补，这类错误从根上不可能再发生。
#    🔑 判据：**重复出现的同类错误，应改到「让它不可能发生」，而不是每次补一处。**
import subprocess
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
# 🔑 第一百零二轮：历史遗留台账 —— 让"已知遗留"成为**可断言的事实**。
HISTORY_KNOWN = os.path.join(ROOT, 'audit', 'history_mode_known.json')
# 🔑 第一百零九轮：变更史**镜像** —— 放在 ledger/（与 audit/ 不同目录）。
#    🔴 只有一处时，整段替换变更史改一个文件就能蒙混（108 轮②）。
#    🔑 两处独立 → 误操作必须**同时改两处**才不被发现。
FP_HISTORY_MIRROR = os.path.join(ROOT, 'ledger', 'baseline_fp_mirror.json')
# 🔑 第一百零八轮：基准变更史上限（保留最早 1 条 + 最近 N-1 条）
BASELINE_FP_HISTORY_MAX = 20
# 🔑 第一百一十一轮：**镜像写入函数名**登记项。
#    🔴 110 轮诚实结论③：_write_mirror 硬编码在扫描器里 ——
#       改函数名会让 G403 **静默失效**（与 93 轮常量改名同源）。
#    🔑 登记后由 G404 断言该函数**真实存在**，改名即暴露。
MIRROR_WRITE_FN = '_write_mirror'

# 🔑 第一百一十二轮：**被依赖的名字**统一登记。
#    🔴 111 轮诚实结论②：只登记了 MIRROR_WRITE_FN 一个 ——
#       HISTORY_KNOWN / LEGACY_FILES_DIR 等同样是"被依赖的名字"，
#       改名同样会**静默失效**，却一个都没被覆盖。
#    🔑 本表让"改名静默失效"这一类问题**一次性**被覆盖，而不是逐个补。
#    🔑 值 = (类型, 说明)；类型: 'const'（模块级常量）· 'fn'（函数）
DEPENDENT_NAMES = {
    # ── 路径类常量：改了会让产物写到别处，而旧门禁全部静默失效 ──
    'HISTORY_KNOWN': ('const', '历史 mode 台账路径'),
    'FP_HISTORY_MIRROR': ('const', '变更史镜像路径'),
    'LEGACY_FILES_DIR': ('const', '异常文件完整清单落盘目录'),
    # ── 登记项本身：改名会让 G403/G404 静默失效 ──
    'MIRROR_WRITE_FN': ('const', '镜像写入函数名登记项'),
    'TRUST_ROOT_FILE': ('const', '信任根文件路径（G408 依赖）'),
    # ── 被依赖的函数 ──
    '_write_mirror': ('fn', '写镜像'),
    '_scan_write_pairing': ('fn', 'G403 用的函数级扫描器'),
    '_baseline_fp': ('fn', '基准指纹算法'),
    'blob_content': ('fn', 'blob 内容唯一实现（symlink 走 readlink）'),
    'local_index_entries': ('fn', 'git 索引 mode+sha 唯一来源'),
}
# 🔑 登记项**不得为空**：空表会让 G405 退化成"永远通过"
DEPENDENT_NAMES_MIN = 5
# 🔑 必须始终在表内的**核心**名字（防有人把关键项悄悄删掉）
DEPENDENT_NAMES_REQUIRED = ('HISTORY_KNOWN', 'MIRROR_WRITE_FN', '_write_mirror')

# 🔑 第一百一十三轮：**未登记常量豁免** —— 但必须写明理由。
#    🔴 112 轮①：G405 只能守住"已登记的"，守不住"该登记没登记的"。
#    🔑 豁免**不得静默**：每条都要理由，且理由非空（与 94/95 轮同构）。
PATH_CONST_ALLOW = {
    # 🔑 117 轮：只**读**信任根作对照，不是产物路径 → 走 ALLOW 而非 DEPENDENT_NAMES
    '_scan_cross_ref_consts.py::TRUST_ROOT_FILE': '只读信任根作对照，不写产物；由 G406 抓到后登记',
    # registry.yaml 是工具注册表，不是产物路径；改它不会让门禁静默失效
    'registry_normalize.py::REG': '工具注册表路径，非产物/台账路径',
    'tool_run.py::REGISTRY': '工具注册表路径，非产物/台账路径',
}
# 🔑 豁免**必须非空** —— 空表 + 新常量 = 应报未登记，不得静默
PATH_CONST_ALLOW_MIN_REASON = 6

# 🔑 第一百一十四轮：**元登记项** —— 被依赖的"登记表本身"。
#    🔴 113 轮③：PATH_CONST_ALLOW 自己未纳入登记项，
#       **它自己改名也会静默失效** —— 与 112 轮同一个洞又出现一次。
#    🔑 根治思路：**登记表自己也要被登记**，形成闭环。
#    🔑 这些名字同样是"被依赖的"：G405/G406 都靠它们工作。
SELF_REGISTERED_META = ('DEPENDENT_NAMES', 'DEPENDENT_NAMES_MIN',
                        'DEPENDENT_NAMES_REQUIRED', 'PATH_CONST_ALLOW',
                        'PATH_CONST_ALLOW_MIN_REASON')
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


# 🔑 第一百一十八轮：**自测临时目录**（根因修复，取代"清理写在 finally 里"）
#    🔴 第一百一十七轮真实事故：清理写在 `finally:` 里 → 进程被杀（沙盒 502）时
#       **不执行** → 残留落在 scripts/ 里 → 被 `git add -A` 收进索引 → 推送报
#       "文件在磁盘上不存在"（os.path.exists 跟随 dangling symlink → False）。
#    🔑 三道防线，**都不依赖 finally**：
#       ① 独立目录 `_selftest_tmp/` —— 残留只落在这里，不污染代码目录
#       ② **启动即清理** —— 进入自测先清空，上次残留本次就没了（不靠"结束才清"）
#       ③ `.gitignore` 排除 —— 即便残留，`git add -A` 也**收不进去**
#    🔑 gitignore 与"自测需要 git 索引它"不冲突：自测用 `git add -f` **显式强制**。
SELFTEST_TMP_DIR = '_selftest_tmp'


def _selftest_reset():
    """🔑 **启动即清理**（不依赖 finally）—— 返回该目录的绝对路径。

    🔑 为什么"启动即清理"比"结束才清理"强：
       🔴 "结束才清理"依赖进程**正常走到结尾**；进程被杀/断电/异常退出都不执行。
       ✅ "启动即清理"依赖的只是"**下次还会跑**" —— 即便上次被杀，
          下次启动的第一件事就是把残留清掉，残留的**生存期被压到最短**。
    """
    import subprocess   # 🔑 本文件**没有顶层** import subprocess（只在各函数内导入）
    d = os.path.join(ROOT, SELFTEST_TMP_DIR)

    # 先清 git 索引（残留若已被 add -f）
    # 🔴 注意：这里的 try/except 曾**吞掉 NameError** —— subprocess 未导入时，
    #    清理静默失效而调用方毫无察觉（与 106 轮"字段缺失静默跳过"同源）。
    # ✅ 第一百一十九轮：不再依赖 try 的"没报错"当作"清理好了"——
    #    下面**重新查一遍** git ls-files，用事实校验，而不是信任 try 块。
    try:
        got = subprocess.run(['git', 'ls-files', '--', SELFTEST_TMP_DIR],
                             capture_output=True, text=True, cwd=ROOT).stdout
        for ln in got.strip().split('\n'):
            if ln.strip():
                subprocess.run(['git', 'rm', '-f', '--cached', '--quiet',
                                ln.strip()], capture_output=True, cwd=ROOT)
    except Exception as e:
        # 🔑 不再静默 pass —— 打印出来，让"代码坏了"不会伪装成"没什么要清的"
        print(f'🔴 清理 git 索引时异常: {type(e).__name__}: {e}')

    # 再删磁盘（shutil.rmtree 能删掉目录里的 symlink）
    shutil.rmtree(d, ignore_errors=True)
    os.makedirs(d, exist_ok=True)

    # 🔑 第一百一十九轮：**清理后自断言**（防 shutil.rmtree 静默失败）
    #    🔴 rmtree(ignore_errors=True) 失败时**不报错也不删** —— 目录里仍有东西，
    #       而调用方拿到路径后照常使用，残留与被清理**看起来完全一样**。
    #    🔑 判据：**清理的结果必须被验证，不能假设**。
    #    🔑 失败时返回 None（**拒绝给结论**），而不是照常返回路径。
    left = os.listdir(d) if os.path.isdir(d) else None
    if left is None:
        print(f'🔴 自测临时目录 {SELFTEST_TMP_DIR} 创建失败 —— 拒绝继续')
        return None
    if left:
        print(f'🔴 清理后目录**非空**（{len(left)} 项: {left[:5]}）'
              f' —— shutil.rmtree 静默失败，拒绝继续')
        return None
    # 索引层同样复查一次
    try:
        still = subprocess.run(['git', 'ls-files', '--', SELFTEST_TMP_DIR],
                               capture_output=True, text=True, cwd=ROOT).stdout
        still = [x for x in still.strip().split('\n') if x.strip()]
    except Exception:
        still = []      # 🔴 查不到时按"未知"处理，下面会打印，不冒充"已清空"
    if still:
        print(f'🔴 清理后 git 索引仍有 {len(still)} 项残留: {still[:5]} —— 拒绝继续')
        return None
    return d


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

def cmd_assert_fp_history():
    """🔑 G401：**基准变更史**必须可答"哪一轮变的、为什么变"。

    🔴 第一百零七轮诚实结论②③（本轮要解决的两条）：
       ② 基准指纹不记"是什么时候变的" —— 只知道"变了"，
          不知道"哪一轮变的、为什么变"；
       ③ 台账不记历史基准指纹列表 —— 只留最新一个。

    🔑 三条判据：
       ① `baseline_fp_history` **必须存在**（缺字段 → 拒绝给结论）
          —— 🔴 "没有变更史"与"还没发生过变更"必须能区分（107 轮③）
       ② 每条必须含 round / from_fp / to_fp / legacy_from / legacy_to
          —— 🔴 缺任一字段则"为什么变"答不了
       ③ 🔑 **链条闭合**：首条 from_fp 与后续每条的 from_fp
          必须等于上一条的 to_fp
          —— 🔴 否则中间某次变更被跳过/被删，"历史"就是编的
    """
    print('🔑 **基准变更史断言**（G401）')
    print('=' * 70)
    try:
        with open(HISTORY_KNOWN, encoding='utf-8') as f:
            rec = json.load(f)
    except FileNotFoundError:
        print(f'🔴 台账不存在：{os.path.relpath(HISTORY_KNOWN, ROOT)}')
        return 1
    except ValueError as e:
        print(f'🔴 台账解析失败：{e} —— 拒绝给结论')
        return 1

    if 'baseline_fp_history' not in rec:
        print('🔴 台账**缺少 baseline_fp_history** —— '
              '无法区分"没变更过"与"变更史被删"，拒绝给结论')
        print('   🔑 修复：重跑 --audit-history')
        print('=' * 70)
        return 1

    h = rec['baseline_fp_history']
    if not isinstance(h, list):
        print(f'🔴 baseline_fp_history 类型异常：{type(h).__name__} '
              f'（应为 list）—— 拒绝给结论')
        return 1
    print(f'   变更史 {len(h)} 条')
    # 🔑 第一百零九轮：新增 seq / seq_in_round，解决 108 轮①
    need = ('seq', 'seq_in_round', 'round', 'from_fp', 'to_fp',
            'legacy_from', 'legacy_to')
    bad = []
    prev_to = None
    for i, e in enumerate(h):
        miss = [k for k in need if k not in e]
        if miss:
            bad.append(f'第 {i} 条缺少字段 {miss} —— "为什么变"答不了')
            continue
        if not isinstance(e['round'], int) or e['round'] <= 0:
            bad.append(f'第 {i} 条 round 非法：{e["round"]!r}')
        # 🔑 链条闭合
        if prev_to is not None and e['from_fp'] != prev_to:
            bad.append(f'第 {i} 条 **链条断裂**：from_fp '
                       f'{str(e["from_fp"])[:8]} ≠ 上一条 to_fp '
                       f'{str(prev_to)[:8]} —— 中间变更被跳过或被删')
        # 🔑 seq 必须严格等于下标+1（防删中间一条后重编号掩盖）
        if e.get('seq') != i + 1:
            bad.append(f'第 {i} 条 seq = {e.get("seq")!r}，应为 '
                       f'{i + 1} —— 变更史被删条或重编号')
        prev_to = e['to_fp']
        print(f'   #{i}  seq={e.get("seq")}  第 {e["round"]} 轮'
              f'（本轮第 {e.get("seq_in_round")} 次）  '
              f'{str(e["from_fp"])[:8]} → {str(e["to_fp"])[:8]}  '
              f'遗留 {e["legacy_from"]} → {e["legacy_to"]}')

    # 🔑 最后一条的 to_fp 必须等于台账当前指纹
    cur = rec.get('baseline_fp')
    if h and cur and h[-1]['to_fp'] != cur:
        bad.append(f'末条 to_fp {str(h[-1]["to_fp"])[:8]} '
                   f'≠ 台账当前指纹 {str(cur)[:8]} —— 台账被手工改过')

    if bad:
        print()
        for b in bad:
            print(f'🔴 {b}')
        print('=' * 70)
        return 1
    print()
    print(f'✅ 变更史闭合：{len(h)} 条 · 每条均含轮次与前后指纹')
    print('=' * 70)
    return 0

def cmd_assert_fp_mirror():
    """🔑 G402：**变更史镜像**必须与台账一致 —— 防"整段替换变更史"。

    🔴 第一百零八轮诚实结论②（本轮要解决的那一条）：
       "变更史没有独立门禁防整段手工替换 —— G401 只验链条闭合，
        若整段重造且自洽，它验不出来（与 89 轮同源自证循环同源）。"

    🔑 解法：**在另一处独立文件里放变更史的指纹**。
       整段替换变更史 → 必须**同时**改台账与镜像 → 少改一处即暴露。

    🔑 三条判据（任一不满足即阻断）：
       ① 镜像文件必须存在且可解析（缺失/损坏 → 拒绝给结论）
       ② `history_sha` 必须等于**当前台账**变更史的指纹
       ③ `history_len` 与 `baseline_fp` 也必须一致
          —— 🔴 只比 sha 时，长度不同但 sha 相同不可能；
             但若有人只改 len 不改 sha，也属于篡改，须拦。
    """
    print('🔑 **变更史镜像断言**（G402）')
    print('=' * 70)
    try:
        with open(HISTORY_KNOWN, encoding='utf-8') as f:
            rec = json.load(f)
    except FileNotFoundError:
        print(f'🔴 台账不存在：{os.path.relpath(HISTORY_KNOWN, ROOT)}')
        return 1
    except ValueError as e:
        print(f'🔴 台账解析失败：{e} —— 拒绝给结论')
        return 1

    h = rec.get('baseline_fp_history')
    if h is None:
        print('🔴 台账缺少 baseline_fp_history —— 无法与镜像比对，'
              '拒绝给结论')
        return 1

    try:
        with open(FP_HISTORY_MIRROR, encoding='utf-8') as f:
            mir = json.load(f)
    except FileNotFoundError:
        print(f'🔴 镜像不存在：{os.path.relpath(FP_HISTORY_MIRROR, ROOT)}')
        print('   🔴 变更史只有一处 —— 整段替换将无从发现')
        print('   🔑 修复：重跑 --audit-history')
        print('=' * 70)
        return 1
    except ValueError as e:
        print(f'🔴 镜像解析失败：{e} —— 拒绝给结论')
        return 1

    want = _mirror_payload(rec)
    bad = []
    for k in ('history_sha', 'history_len', 'baseline_fp'):
        got = mir.get(k)
        exp = want.get(k)
        if got != exp:
            bad.append(f'{k} 不符：镜像 {str(got)[:16]!r} ≠ '
                       f'台账 {str(exp)[:16]!r}')
        else:
            print(f'   ✅ {k} = {str(exp)[:16]}')
    # 🔑 幂等性：镜像里不得有多余键（防塞入伪造说明）
    extra = sorted(set(mir) - set(want))
    if extra:
        bad.append(f'镜像含多余键 {extra} —— 可能是手工改写')

    print(f'   变更史 {len(h)} 条 · 镜像路径 '
          f'{os.path.relpath(FP_HISTORY_MIRROR, ROOT)}')
    if bad:
        print()
        for b in bad:
            print(f'🔴 {b}')
        print('   🔴 变更史被改过而镜像未同步（或反之）—— '
              '**整段替换企图**')
        print('=' * 70)
        return 1
    print()
    print(f'✅ 镜像与台账一致 —— 整段替换须同时改两处')
    print('=' * 70)
    return 0

def _scan_write_pairing():
    """🔑 扫描 scripts/*.py：找出写**台账变更史**与写**镜像**的函数。

    🔑 为什么用 AST 而不是 grep：
       🔴 grep 分不清 `rec['baseline_fp_history'] = x`（写）
          与 `h = rec['baseline_fp_history']`（只读）。
    """
    import ast
    base_w, mir_w = {}, {}
    for f in sorted(glob.glob(os.path.join(HERE, '*.py'))):
        try:
            tree = ast.parse(open(f, encoding='utf-8').read())
        except (SyntaxError, ValueError):
            continue
        for fn_ in ast.walk(tree):
            if not isinstance(fn_, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            name = fn_.name
            wb, wm = False, False
            for n in ast.walk(fn_):
                # ① 写 baseline_fp_history：下标赋值 / .append 调用
                if isinstance(n, ast.Subscript):
                    sl = getattr(n.slice, 'value', None)
                    if sl == 'baseline_fp_history' and isinstance(
                            n.ctx, (ast.Store, ast.Del)):
                        wb = True
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)                         and n.func.attr in ('append', 'extend', 'insert', 'pop'):
                    v = n.func.value
                    if isinstance(v, ast.Subscript) and getattr(
                            v.slice, 'value', None) == 'baseline_fp_history':
                        wb = True
                # ② 写镜像
                if isinstance(n, ast.Call):
                    fn_id = getattr(n.func, 'id', None)
                    if fn_id == MIRROR_WRITE_FN:
                        wm = True
            if wb:
                base_w.setdefault(os.path.basename(f), []).append(name)
            if wm:
                mir_w.setdefault(os.path.basename(f), []).append(name)
    return base_w, mir_w


def cmd_assert_write_pairing():
    """🔑 G403：**写台账变更史必须与写镜像在同一个函数内**。

    🔴 第一百零九轮诚实结论②（本轮要解决的那一条）：
       "镜像只由 `--audit-history` 写，其它入口改变更史
        不会同步镜像（未设门禁禁止）"。

    🔑 双向断言（与 G396 同构）：
       - 改了台账**没同步镜像** → G402 抓得到（指纹不符）
       - 🔴 改了镜像**没同步台账** → **没有任何门禁能抓**
         本门禁补的就是这个反向漏洞。
       - 🔑 更根本的：新入口若只写台账不写镜像 → 从一开始就是单点。

    🔑 判据：写 `baseline_fp_history` 的函数集合
       **必须等于** 调用 `_write_mirror` 的函数集合。
    """
    print('🔑 **写入配对断言**（G403）')
    print('=' * 70)
    base_w, mir_w = _scan_write_pairing()
    if not base_w:
        print('🔴 未发现任何写 baseline_fp_history 的函数 —— '
              '台账无法被维护，拒绝给结论')
        return 1
    print(f'   写台账变更史的函数：{dict(base_w)}')
    print(f'   写镜像的函数：{dict(mir_w)}')

    def flat(d):
        return {f'{k}::{n}' for k, v in d.items() for n in v}

    only_base = sorted(flat(base_w) - flat(mir_w))
    only_mir = sorted(flat(mir_w) - flat(base_w))
    bad = []
    if only_base:
        bad.append('改了台账**未同步镜像**：'
                   f'{only_base} —— 变更史仍只有一处，整段替换无从发现')
    if only_mir:
        bad.append('改了镜像**未同步台账**：'
                   f'{only_mir} —— 镜像会与台账脱钩，G402 将误报')
    if bad:
        print()
        for b in bad:
            print(f'🔴 {b}')
        print('   🔑 正确做法：在**同一个函数内**先写台账、再写镜像')
        print('=' * 70)
        return 1
    print()
    print(f'✅ 写入配对一致 —— {len(flat(base_w))} 个函数同时写台账与镜像')
    print('=' * 70)
    return 0

def cmd_assert_mirror_fn():
    """🔑 G404：**登记项必须真实存在且真被使用** —— 防改名静默失效。

    🔴 第一百一十轮诚实结论③（本轮要解决的那一条）：
       "_write_mirror 名字**硬编码**在扫描器里 —— 改函数名会让 G403
        静默失效（与 93 轮常量改名同源，未设反制）。"

    🔑 三层判据（与 94 轮"常量必须真的被引用"同构）：
       ① 登记常量 **MIRROR_WRITE_FN** 必须存在且非空
       ② 该函数必须**真实定义**在 scripts/*.py 里（AST 顶层函数）
       ③ 该函数必须**真被扫描器使用** —— 即在 _scan_write_pairing 内被引用
          🔴 只验①+②不够：改了常量值而不改调用点 → 函数存在但没人用，
             G403 会静默变成"永远找不到镜像写入者"。

    🔑 为什么③必须查"在扫描函数内被引用"：
       这是把"登记"与"使用"绑成一条**可校验的链**，
       而不是只证明"这个名字碰巧存在"（83 轮"存在但无关"）。
    """
    print('🔑 **登记项完整性断言**（G404）')
    print('=' * 70)
    import ast
    bad = []
    fn_name = MIRROR_WRITE_FN
    if not fn_name or not isinstance(fn_name, str):
        print('🔴 MIRROR_WRITE_FN 未登记或类型异常 —— 拒绝给结论')
        return 1
    print(f'   登记值：{fn_name!r}')
    if fn_name not in globals() or not callable(globals().get(fn_name)):
        bad.append(f'登记的函数 {fn_name!r} **未定义** —— '
                   'G403 会静默失效')
    else:
        print(f'   ✅ 函数已定义（可调用）')

    # ③ 真被扫描器使用
    used = False
    try:
        src = open(os.path.join(HERE, 'push_api.py'), encoding='utf-8').read()
        tree = ast.parse(src)
        for n in ast.walk(tree):
            if isinstance(n, ast.FunctionDef) and n.name == '_scan_write_pairing':
                for m in ast.walk(n):
                    if isinstance(m, ast.Name) and m.id == 'MIRROR_WRITE_FN':
                        used = True
                    if isinstance(m, ast.Attribute) and m.attr == fn_name:
                        used = True
    except (SyntaxError, ValueError, FileNotFoundError) as e:
        bad.append(f'无法解析 push_api.py：{e} —— 拒绝给结论')
    if not bad and not used:
        bad.append(f'常量 MIRROR_WRITE_FN **未在 _scan_write_pairing 内被引用** '
                   f'—— 改名后 G403 静默失效')
    if bad:
        print()
        for b in bad:
            print(f'🔴 {b}')
        print('=' * 70)
        return 1
    print('   ✅ 扫描器 _scan_write_pairing 内**确被引用**')
    print()
    print(f'✅ 登记项闭合 —— {fn_name!r} 已定义且被使用')
    print('=' * 70)
    return 0

def cmd_assert_dependent_names():
    """🔑 G405：**所有被依赖的名字都必须闭合**（通用版）。

    🔴 第一百一十一轮诚实结论②（本轮要解决的那一条）：
       "只登记了 MIRROR_WRITE_FN 一个名字 —— HISTORY_KNOWN、
        LEGACY_FILES_DIR 等同样是'被依赖的名字'，未纳入登记项闭合机制。"

    🔑 与 G404 的关系：
       G404 对 **MIRROR_WRITE_FN** 做**深度**校验（还查"在 _scan_write_pairing
       内被引用"）；G405 对**所有**登记名做**广度**校验（存在 + 真被引用）。
       🔴 只有 G404 → 其它名字仍可改名静默失效；
          只有 G405 → 那一条最关键的链缺少"在特定函数内被引用"这层。

    🔑 三层判据：
       ① 表**非空**且达到 DEPENDENT_NAMES_MIN（空表 → 拒绝给结论）
       ② 核心名 DEPENDENT_NAMES_REQUIRED **必须都在表内**
       ③ 每个登记名 **真存在**（const 非空 / fn 可调用）
          **且真被引用**（AST 统计，排除定义/赋值处）
          🔴 只验"存在"不够 —— 改名后旧名字消失，
             若无人引用则门禁静默失效（与 83 轮"存在但无关"同源）。
    """
    print('🔑 **被依赖名字闭合断言**（G405）')
    print('=' * 70)
    import ast
    bad = []
    tbl = globals().get('DEPENDENT_NAMES')
    if not isinstance(tbl, dict) or not tbl:
        print('🔴 DEPENDENT_NAMES 未登记或为空 —— 拒绝给结论')
        return 1
    if len(tbl) < DEPENDENT_NAMES_MIN:
        bad.append(f'登记项仅 {len(tbl)} 条 '
                   f'< 下限 {DEPENDENT_NAMES_MIN} —— 疑似被删减')
    missing_req = [n for n in DEPENDENT_NAMES_REQUIRED if n not in tbl]
    if missing_req:
        bad.append(f'**核心**名字缺失：{missing_req} —— 不得从登记表的删除'.replace('的删除', '删除'))
    print(f'   登记 {len(tbl)} 条 · 核心名 {len(DEPENDENT_NAMES_REQUIRED)} 个齐全'
          if not missing_req else f'   登记 {len(tbl)} 条')

    # ③ 统计全 scripts/*.py 的**真引用**
    refs = {}
    for f in sorted(glob.glob(os.path.join(HERE, '*.py'))):
        try:
            tree = ast.parse(open(f, encoding='utf-8').read())
        except (SyntaxError, ValueError):
            continue
        for n in ast.walk(tree):
            nm = None
            if isinstance(n, ast.Name):
                # 🔑 排除**赋值目标**：那是定义，不是引用
                if isinstance(n.ctx, ast.Load):
                    nm = n.id
            elif isinstance(n, ast.Attribute):
                nm = n.attr
            # 🔑 收集范围 = 登记表 + 元登记项（后者不在表里，需显式并入）
            watch = tbl.keys() | set(globals().get('SELF_REGISTERED_META') or ())
            if nm in watch:
                refs[nm] = refs.get(nm, 0) + 1
            # 🔑 **字符串形式**的动态引用：globals().get('X')
            #    🔴 这类引用 AST 扫不到（是 Constant 不是 Name）——
            #       若不计入，元登记项会**永远**报"无引用"（114 轮实测踩到）。
            #    🔑 与 110 轮"grep 分不清写与只读"同源：
            #       **按名字访问**与**按字符串访问**是两种不同的引用形态。
            elif isinstance(n, ast.Constant) and isinstance(n.value, str) \
                    and n.value in watch:
                refs[n.value] = refs.get(n.value, 0) + 1
    # 🔑 元登记项：**登记表自己**也必须闭合（113 轮③）
    #    🔑 与 **G407 共用** `_meta_names_bad()`，不另抄一份。
    m_bad = _meta_names_bad(refs)
    if m_bad:
        bad.extend(m_bad)
    else:
        print(f'   ✅ meta    {len(globals().get("SELF_REGISTERED_META") or ())} '
              f'个元登记项闭合')

    for name, (kind, desc) in sorted(tbl.items()):
        g = globals().get(name)
        if kind == 'const':
            ok = g is not None and g != ''
        else:
            ok = callable(g)
        n_ref = refs.get(name, 0)
        if not ok:
            bad.append(f'{kind} {name}（{desc}）**不存在或为空**')
        elif n_ref == 0:
            bad.append(f'{name}（{desc}）**无任何引用** —— '
                       f'改名后门禁会静默失效')
        else:
            print(f'   ✅ {kind:5s} {name:22s} 引用 {n_ref} 处 · {desc}')
    if bad:
        print()
        for b in bad:
            print(f'🔴 {b}')
        print('=' * 70)
        return 1
    print()
    print(f'✅ {len(tbl)} 个被依赖的名字**全部闭合**（存在且真被引用）')
    print('=' * 70)
    return 0

def _scan_path_consts():
    """🔑 扫 scripts/*.py 的**模块级路径常量**（os.path.join(ROOT/HERE, ...)）。

    🔑 为什么只看模块级 + ROOT/HERE 开头：
       - 函数内的临时路径不是"被依赖的名字"，登记它们只会稀释登记表；
       - 以 ROOT/HERE 开头 = 仓库内**产物/台账**路径，改名会让门禁静默失效。
    """
    import ast
    out = []
    for f in sorted(glob.glob(os.path.join(HERE, '*.py'))):
        base = os.path.basename(f)
        try:
            tree = ast.parse(open(f, encoding='utf-8').read())
        except (SyntaxError, ValueError):
            continue
        for n in tree.body:
            if not isinstance(n, ast.Assign) or len(n.targets) != 1:
                continue
            t = n.targets[0]
            if not isinstance(t, ast.Name):
                continue
            v = n.value
            if not (isinstance(v, ast.Call)
                    and getattr(v.func, 'attr', '') == 'join'):
                continue
            src = ast.unparse(v)
            if 'ROOT' in src or 'HERE' in src:
                out.append((f'{base}::{t.id}', src))
    return out


def cmd_assert_path_consts():
    """🔑 G406：**新产物路径常量必须已登记**（防"该登记没登记"）。

    🔴 第一百一十二轮诚实结论①（本轮要解决的那一条，也是本机制最大的洞）：
       "登记表是人工维护的 —— 新增一个被依赖的名字没人提醒要登记，
        G405 照样绿。**只能守住已登记的，守不住该登记没登记的。**"

    🔑 做法：**反向**——不查"登记了什么"，而查"**代码里有什么**"。
       扫出全部模块级路径常量，凡不在 DEPENDENT_NAMES 也不在豁免表中的，
       一律报"未登记"。新增常量即刻暴露，不需要人记得去登记。

    🔑 三条判据：
       ① 每个路径常量必须 **已登记** 或 **已豁免**
       ② 豁免必须有理由且长度 ≥ PATH_CONST_ALLOW_MIN_REASON
          🔴 否则豁免退化成"随便放行"（与 81 轮粗粒度白名单同一个病）
       ③ 豁免中的名字必须**真实存在**（防登记了已删除的常量 = 僵尸豁免）
    """
    print('🔑 **路径常量登记断言**（G406）')
    print('=' * 70)
    tbl = globals().get('DEPENDENT_NAMES') or {}
    allow = globals().get('PATH_CONST_ALLOW') or {}
    consts = _scan_path_consts()
    if not consts:
        print('🔴 未发现任何路径常量 —— 扫描器可能失效，拒绝给结论')
        return 1
    bad = []
    reg_names = {n for n, (k, _) in tbl.items() if k == 'const'}
    print(f'   路径常量 {len(consts)} 个 · 登记表含 const {len(reg_names)} 个')
    seen = set()
    for key, src in consts:
        name = key.split('::', 1)[1]
        seen.add(name)
        if name in reg_names:
            print(f'   ✅ 已登记  {key}')
        elif key in allow:
            r = (allow[key] or '').strip()
            if len(r) < PATH_CONST_ALLOW_MIN_REASON:
                bad.append(f'豁免 {key} **理由过短**（{len(r)} < '
                           f'{PATH_CONST_ALLOW_MIN_REASON}）—— 不得静默放行')
            else:
                print(f'   ✅ 已豁免  {key} · {r}')
        else:
            bad.append(f'**未登记**的路径常量 {key} = {src}\n'
                       f'        → 加入 DEPENDENT_NAMES 或 PATH_CONST_ALLOW（须写理由）')
    # ③ 僵尸豁免
    zombie = sorted(k for k in allow if k not in {c[0] for c in consts})
    if zombie:
        bad.append(f'豁免指向**已不存在**的常量（僵尸豁免）：{zombie}')
    if bad:
        print()
        for b in bad:
            print(f'🔴 {b}')
        print()
        print('   🔑 G405 只能守住"已登记的"；本门禁从**代码侧**反向补上'
              '"该登记没登记的"。')
        print('=' * 70)
        return 1
    print()
    print(f'✅ {len(consts)} 个路径常量**均已登记或已豁免**（无未登记项）')
    print('=' * 70)
    return 0

def _meta_names_bad(refs):
    """🔑 元登记项校验（被 G405 与 **G407** 共用，避免两处各写一份）。

    🔴 必须与 G405 共用同一实现 —— 若 G407 自己抄一份，
       则第一百轮那种"自测测的是自己抄的那份"会重演。
    """
    meta = globals().get('SELF_REGISTERED_META')
    if not isinstance(meta, tuple) or not meta:
        return ['SELF_REGISTERED_META 未登记或为空 —— 拒绝给结论']
    out = []
    for nm in meta:
        g = globals().get(nm)
        if g is None or (isinstance(g, (dict, tuple, str)) and len(g) == 0):
            out.append(f'{nm}（元登记项）**不存在或为空**')
        elif refs.get(nm, 0) == 0:
            out.append(f'{nm}（元登记项）**无任何引用** —— 改名后静默失效')
    return out


def cmd_assert_meta_names():
    """🔑 G407：**元登记项闭合**（登记表自己也要被登记）。

    🔴 第一百一十三轮诚实结论③（本轮要解决的那一条）：
       "豁免表 PATH_CONST_ALLOW **本身未纳入**登记项 ——
        **它自己改名也会静默失效**（与 112 轮同一个洞，又出现一次）。"

    🔑 为什么**独立成门禁**而不只是并入 G405：
       🔴 破坏实测时只有 G405 会连带失败，看不出**是表内项还是元项**坏了。
       独立后可单独证明"元登记项这一层"确实有效（与 78 轮"保留三条编号"同理）。

    🔑 与 G405 共用 `_meta_names_bad()` —— 不另抄一份。
    """
    print('🔑 **元登记项闭合断言**（G407）')
    print('=' * 70)
    import ast
    meta = globals().get('SELF_REGISTERED_META') or ()
    refs = {}
    watch = set(meta)
    for f in sorted(glob.glob(os.path.join(HERE, '*.py'))):
        try:
            tree = ast.parse(open(f, encoding='utf-8').read())
        except (SyntaxError, ValueError):
            continue
        for n in ast.walk(tree):
            nm = None
            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load):
                nm = n.id
            elif isinstance(n, ast.Attribute):
                nm = n.attr
            elif isinstance(n, ast.Constant) and isinstance(n.value, str):
                nm = n.value
            if nm in watch:
                refs[nm] = refs.get(nm, 0) + 1
    bad = _meta_names_bad(refs)
    if bad:
        for b in bad:
            print(f'🔴 {b}')
        print('=' * 70)
        return 1
    for nm in sorted(meta):
        print(f'   ✅ {nm:28s} 引用 {refs.get(nm, 0)} 处')
    print()
    print(f'✅ {len(meta)} 个元登记项**全部闭合** —— 登记表自己也被登记了')
    print('=' * 70)
    return 0

TRUST_ROOT_FILE = os.path.join(ROOT, 'ledger', 'trust_root.json')


def _trust_root():
    """🔑 读信任根。**读不到返回 None**（区分"没有"与"读不到"）。"""
    try:
        return json.load(open(TRUST_ROOT_FILE, encoding='utf-8'))
    except Exception:
        return None


def _norm(v):
    """🔑 归一：tuple/list/set 视为等价且**排序**（JSON 只有 list，代码里可能是 tuple/set）。

    🔑 排序是必须的：`{"G21"}` 与 `["G21"]` 内容相同，但 set 遍历顺序不确定 ——
       不排序会让台账在每次运行时抖动（与 103 轮 `odd_sample` 必须排序同源）。
    """
    if isinstance(v, (list, tuple, set, frozenset)):
        try:
            return sorted((_norm(x) for x in v), key=lambda z: (str(type(z)), str(z)))
        except TypeError:
            return sorted((str(_norm(x)) for x in v))
    if isinstance(v, dict):
        return {k: _norm(x) for k, x in sorted(v.items())}
    return v


def _const_value(name):
    """🔑 取某常量在 scripts/*.py 中的**定义值**（AST literal_eval）。找不到返回 None。"""
    import ast as _ast
    # 🔑 HERE 本身就是 scripts/ —— 不要再加一层 'scripts'
    for f in sorted(glob.glob(os.path.join(HERE, '*.py'))):
        try:
            t = _ast.parse(open(f, encoding='utf-8').read())
        except Exception:
            continue
        for n in t.body:
            if isinstance(n, _ast.Assign) and isinstance(n.value, _ast.Constant):
                for tg in n.targets:
                    if isinstance(tg, _ast.Name) and tg.id == name:
                        try:
                            return _ast.literal_eval(n.value)
                        except Exception:
                            return None
            # 🔑 117 轮：补 Set/Dict —— LEGAL_GATES = {"G21"} 是 Set 字面量，
            #    原实现只认 Constant/Tuple/List → 会报"找不到定义"（拒绝而非放行，但登记会失效）
            if isinstance(n, _ast.Assign) and isinstance(
                    n.value, (_ast.Tuple, _ast.List, _ast.Set, _ast.Dict)):
                for tg in n.targets:
                    if isinstance(tg, _ast.Name) and tg.id == name:
                        try:
                            return _ast.literal_eval(n.value)
                        except Exception:
                            return None
            # 🔑 117 轮下一轮指引：补**空调用形式** set() / dict() / list() / tuple()。
            #    🔴 破坏③实测：`LEGAL_GATES = set()` 是 Call 节点，不是 Set 字面量 →
            #       报"找不到定义"。虽是**拒绝**而非误放行（安全），但会让登记失效：
            #       人改用调用写法即可让值型根检查**永远拒绝**，看似"很严"实则失守。
            if isinstance(n, _ast.Assign) and isinstance(n.value, _ast.Call):
                fn = n.value.func
                fnm = fn.id if isinstance(fn, _ast.Name) else None
                if fnm in ('set', 'dict', 'list', 'tuple', 'frozenset') and \
                        not n.value.args and not n.value.keywords:
                    for tg in n.targets:
                        if isinstance(tg, _ast.Name) and tg.id == name:
                            return {'set': set(), 'frozenset': frozenset(),
                                    'dict': {}, 'list': [], 'tuple': ()}[fnm]
    return None

def cmd_assert_trust_root():
    """🔑 G408：**信任根闭合** —— 代码里的元登记项必须与信任根一致。

    🔴 第一百一十四轮诚实结论①（本轮要解决的那一条）：
       "`SELF_REGISTERED_META` 自己是**元元登记项** —— 它本身不在任何表里，
        它改名同样无人发现。**这是同一条链的又一层，可无限递推。**"

    🔑 处置：**停止递推 + 明示信任根**。
       把期望值写进 `ledger/trust_root.json`（**独立于代码**的文件），
       并断言代码值 == 信任根值。
       🔑 为什么不再叠一层"元元元登记项"：递推没有终点，
          每叠一层只会让"守住了"的错觉更厚（114 轮已论证）。

    🔑 三条判据：
       ① 信任根**必须可读** —— 读不到拒绝给结论
          （🔴 若"读不到"当"没有信任根"，就会静默放行）
       ② 代码 `SELF_REGISTERED_META` **必须等于**信任根记录值（逐项比对）
       ③ 信任根**不得**把自己登记进 DEPENDENT_NAMES
          —— 🔴 若登记了，它就退化成普通登记项，递推重新开始
    """
    print('🔑 **信任根闭合断言**（G408）')
    print('=' * 70)
    tr = _trust_root()
    if tr is None:
        print('🔴 信任根不可读 —— 拒绝给结论（不静默当"没有信任根"）')
        print('=' * 70)
        return 1
    want = tr.get('SELF_REGISTERED_META')
    if not isinstance(want, list) or not want:
        print('🔴 信任根未登记 SELF_REGISTERED_META —— 拒绝给结论')
        print('=' * 70)
        return 1
    cur = list(globals().get('SELF_REGISTERED_META') or ())
    bad = []
    if cur != want:
        bad.append(f'代码值 {cur} ≠ 信任根 {want}')
    tbl = globals().get('DEPENDENT_NAMES') or {}
    # 🔑 判据③：**根名本身** + **元项名**都不得被登记进 DEPENDENT_NAMES
    #    🔴 若登记了，它们就从"根/元项"降级为"表内项"，递推层级混乱。
    #    🔑 115 轮实测：只查 want 中的项时，把**根名本身**加进表会**漏网**
    #       （rc=0）—— 因为根名不在 want 里。两种情形必须都覆盖。
    guard = {'SELF_REGISTERED_META'} | set(want)
    in_tbl = sorted(n for n in guard if n in tbl)
    if in_tbl:
        bad.append(f'信任根/元项**被登记进 DEPENDENT_NAMES**：{in_tbl} —— '
                   f'🔴 这会让递推重新开始，信任根必须停在根上')
    # 🔑 判据④（116 轮新增）：**值型根** —— VALUE_ROOTS 中每个常量，
    #    代码中**实际的值**必须 == 信任根记录值。
    #    🔴 与判据②（只比名字列表）的区别：这里比的是**值**。
    #       GATE_RC_DOMAIN 改成 (9,9) 时，名字仍在、仍被引用 —— G405/G406/G407
    #       **全部照绿**，只有值比对能抓到。
    vroots = tr.get('VALUE_ROOTS') or {}
    for nm, spec in sorted(vroots.items()):
        if not isinstance(spec, dict):
            bad.append(f'值型根 {nm} 的登记不是 dict —— 拒绝给结论')
            continue
        why = (spec.get('why') or '').strip()
        if len(why) < 20:
            bad.append(f'值型根 {nm} 的 why 过短（{len(why)}<20）—— 🔴 必须写明"为什么算根"')
        want_v = spec.get('value')
        if want_v is None:
            bad.append(f'值型根 {nm} 未登记 value —— 拒绝给结论')
            continue
        di = (spec.get('defined_in') or '').strip()
        if not di:
            bad.append(f'值型根 {nm} 未登记 defined_in —— 🔴 必须写明它定义在哪')
        elif not os.path.exists(os.path.join(ROOT, di)):
            bad.append(f'值型根 {nm} 的 defined_in 指向不存在的文件：{di}')
        got = _const_value(nm)
        if got is None:
            bad.append(f'值型根 {nm} **在代码中找不到定义** —— 拒绝给结论（读不到≠没有）')
        elif _norm(got) != _norm(want_v):
            bad.append(f'值型根 {nm} 代码值 {got!r} ≠ 信任根 {want_v!r}')
        else:
            # 🔑 117 轮补：判据④**通过时完全不打印** —— 看不出检查了几个值型根，
            #    "静默通过"与"没跑"在输出上无法区分（与 79 轮"跑了≠做了"同源）。
            av = spec.get('allowed_values')
            tail = f'（合法值 {av}）' if av else ''
            print(f'   ✅ 值型根 {nm} = {got!r}{tail}')

    print(f'   信任根 {TRUST_ROOT_FILE}')
    print(f'   代码值 {len(cur)} 项 · 信任根 {len(want)} 项')
    print(f'   理由：{(tr.get("_why") or "")[:60]}…')
    crit = tr.get('_root_criteria') or {}
    if not crit:
        bad.append('信任根未登记 _root_criteria —— 🔴 必须写明"什么算根"')
    else:
        print(f'   🔑 算根标准：{len(crit.get("三条人工判据") or [])} 条人工判据'
              f' · 自动标准已记录为失效: {"失效" in json.dumps(crit, ensure_ascii=False)}')
    if bad:
        print()
        for b in bad:
            print(f'🔴 {b}')
        print('=' * 70)
        return 1
    for n in want:
        print(f'   ✅ {n}')
    print()
    print(f'✅ 信任根闭合：{len(want)} 项一致，且未退回登记项')
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
    # 🔑 第一百一十八轮：**启动即清理**（不依赖 finally）
    d = _selftest_reset()
    if d is None:
        # 🔑 清理失败 → **拒绝给结论**，不能照常往下跑（否则残留与干净不可分辨）
        print('🔴 自测临时目录未能清理 —— 拒绝给结论')
        print('=' * 70)
        return 1
    link = os.path.join(SELFTEST_TMP_DIR, '_symlink_selftest')

    tgt_name = '_symlink_target_selftest.txt'
    tgt = os.path.join(tempfile.gettempdir(), tgt_name)
    with open(tgt, 'w', encoding='utf-8') as f:
        f.write('自测目标\n')
    ok_all = True
    try:
        os.symlink(tgt, link)
        # 🔑 用 `git add -f` **显式强制**（该目录已被 .gitignore 排除），
        #    🔴 不用 `git add -A` —— 那会把仓库里其它未跟踪文件一起收进索引。
        subprocess.run(['git', 'add', '-f', '--', link],
                       capture_output=True, cwd=ROOT)
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
        # 🔑 清理（**双保险**）—— 即便本段没执行到，
        #    ① 独立目录 ② 启动即清理 ③ .gitignore 三道防线仍生效。
        try:
            subprocess.run(['git', 'rm', '-f', '--cached', '--quiet', '--',
                            link], capture_output=True, cwd=ROOT)
        except Exception:
            pass
        shutil.rmtree(d, ignore_errors=True)
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



def _doc_max_round():
    """🔑 文档最大轮次 —— 用于给基准变更史标注"第几轮变的"。

    🔴 探测不到时返回 0，**不猜**（与 G389 同源）：
       一个猜出来的轮次会让变更史指向错误的轮次。

    🔴 第一百零八轮实测：第一版用朴素 `partition('百')` 解析 ——
       `一百零七` 被算成 **100**（"零七"不在字典里 → 0）。
       🔴 这个错误**不会报错**，只会让变更史**悄悄记错轮次**。
       ✅ 改为逐字符累计（与 claim_verify._cn2num 同算法）。
    """
    import re as _re
    _cn = {'零': 0, '一': 1, '二': 2, '三': 3, '四': 4,
           '五': 5, '六': 6, '七': 7, '八': 8, '九': 9}

    def _c2n(t):
        if t.isdigit():
            return int(t)
        total, sec, cur = 0, 0, None
        for ch in t:
            if ch in _cn:
                cur = _cn[ch]
            elif ch == '十':
                sec += (cur if cur is not None else 1) * 10
                cur = None
            elif ch == '百':
                sec += (cur if cur is not None else 1) * 100
                cur = None
            else:
                return None                  # 🔴 未知字符：不猜
        return total + sec + (cur or 0)

    mx = 0
    for dn in ('references', '.'):
        dp = os.path.join(ROOT, dn)
        if not os.path.isdir(dp):
            continue
        for f_ in os.listdir(dp):
            if not f_.endswith('.md'):
                continue
            try:
                for ln in open(os.path.join(dp, f_), encoding='utf-8'):
                    m = _re.match(r'^#{1,4}\s*第([0-9]+|[零一二三四五六七八九十百]+)轮',
                                  ln.strip())
                    if m:
                        v = _c2n(m.group(1))
                        if v is not None:
                            mx = max(mx, v)
            except Exception:
                pass
    return mx


def _mirror_payload(rec):
    """🔑 镜像里放什么：**只放变更史的指纹 + 条数**，不放变更史本身。

    🔑 为什么不直接复制一份变更史：
       🔴 复制 → 两处内容相同 → 改两处即可蒙混，
          而"两处内容相同"这件事本身**无法被发现**（G398 同源自证循环）。
       🔑 放**指纹**：改任一处 → 指纹不符 → 立刻暴露；
          且镜像体积小，不随变更史增长。
    """
    h = rec.get('baseline_fp_history') or []
    return {
        'history_sha': hashlib.sha1(
            json.dumps(h, ensure_ascii=False, sort_keys=True).encode()
        ).hexdigest(),
        'history_len': len(h),
        'baseline_fp': rec.get('baseline_fp'),
        'source': 'audit/history_mode_known.json',
        'note': '🔑 变更史镜像：整段替换变更史须同时改本文件与台账，'
                '否则 G402 会报指纹不符。',
    }


def _write_mirror(rec):
    """写镜像（幂等：内容一致则不重写）。"""
    payload = _mirror_payload(rec)
    try:
        os.makedirs(os.path.dirname(FP_HISTORY_MIRROR), exist_ok=True)
        prev = None
        try:
            with open(FP_HISTORY_MIRROR, encoding='utf-8') as f:
                prev = json.load(f)
        except (FileNotFoundError, ValueError):
            pass
        if prev == payload:
            return 'unchanged', payload
        with open(FP_HISTORY_MIRROR, 'w', encoding='utf-8') as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        return ('written' if prev is not None else 'created'), payload
    except Exception as e:
        return f'fail:{e}', payload

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
        # 🔑 第一百零八轮：变更史**必须始终存在**（含首次）。
        #    🔴 若只在漂移时建，"没有变更史"就无法与"还没发生过变更"区分
        #       —— 这正是"没有 ≠ 读不到"的同一个病。
        'baseline_fp_history': (prev or {}).get('baseline_fp_history', []) or [],
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
        # 🔑 第一百零八轮：**变更史** —— 只留最新指纹时，
        #    "哪一轮变的、为什么变"**无从回答**（107 轮诚实结论②③）。
        _rnd = _doc_max_round()
        rec['baseline_fp_history'] = list(
            (prev or {}).get('baseline_fp_history', []) or [])
        # 🔑 第一百零九轮：**单调序号** —— 108 轮①的修补。
        #    🔴 round 取自文档最大轮次 → 一轮内多次变更会**都记成同一轮**。
        #       （本轮实测已复现：两条变更都标第 108 轮）
        #    🔑 seq：全局单调递增（1..n）· seq_in_round：本轮内第几次
        _n = len(rec['baseline_fp_history'])
        _seq = _n + 1
        _seq_in_round = sum(1 for e in rec['baseline_fp_history']
                            if e.get('round') == _rnd) + 1
        rec['baseline_fp_history'].append({
            'seq': _seq,
            'seq_in_round': _seq_in_round,
            'round': _rnd,
            'from_fp': prev_fp,
            'to_fp': cur_fp,
            'from_modes': (prev or {}).get('baseline_modes'),
            'to_modes': want,
            'legacy_from': prev_n,
            'legacy_to': cur_n,
            'at': time.strftime('%Y-%m-%dT%H:%M:%S%z'),
        })
        # 🔑 变更史**不得无界增长**：超过阈值时保留最早 + 最近 N 条
        if len(rec['baseline_fp_history']) > BASELINE_FP_HISTORY_MAX:
            rec['baseline_fp_history'] = (
                rec['baseline_fp_history'][:1]
                + rec['baseline_fp_history'][-(BASELINE_FP_HISTORY_MAX - 1):])
        print(f'🔑 已记入基准变更史：第 {_rnd} 轮 · '
              f'{prev_fp[:8]} → {cur_fp[:8]}'
              f'（遗留 {prev_n} → {cur_n}）')

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

    # 🔑 第一百零九轮：**写变更史镜像**（另一处独立文件）
    #    🔴 108 轮②：变更史只在一处时，整段手工替换验不出来
    #       （G401 只验链条闭合 —— 重造一段自洽的照样通过）。
    st, pay = _write_mirror(rec)
    if st.startswith('fail'):
        print(f'\n🔴 镜像写入失败：{st} —— 整段替换变更史将无从发现')
        return 1
    print(f'🔑 变更史镜像（{os.path.relpath(FP_HISTORY_MIRROR, ROOT)}）：'
          f'{st} · history_sha {str(pay["history_sha"])[:12]}'
          f' · {pay["history_len"]} 条')
    # 🔑 供 --show-legacy-files 在同一进程内复用
    global _LAST_DETAILS
    _LAST_DETAILS = details
    print('=' * 70)
    # 🔑 审计本身不算失败 —— 它**不被掩盖**即算达标（由 G396 守）
    return 0


def cmd_assert_no_tmp_in_index():
    """🔑 G410：**索引里不得残留自测临时文件**。

    🔴 第一百一十七轮真实事故：
       `--check-symlink` 自测会建 `scripts/_symlink_selftest_tmp`（dangling symlink），
       清理写在 `finally:` 里 —— 但**进程被中断时 finally 不执行**
       （本轮遇到沙盒 502，进程被杀）。
       残留随后被 `git add -A` 收进索引 → 推送时报
       "🔴 1 个文件在磁盘上不存在"（os.path.exists 跟随 dangling symlink → False）。

    🔑 为什么必须单独一条门禁：
       G390 只查"**未 add** 的"（漏传），查不出"**已 add 但本不该存在**"（误传）。
       两者方向相反 —— 与 G406（代码→表）补 G405（表→代码）是同一种互补。
    """
    print('🔑 **索引残留自测临时文件断言**（G410）')
    print('=' * 70)
    ents = local_index_entries()
    if ents is None:
        print('🔴 无法读取 git 索引 —— 拒绝给结论')
        print('=' * 70)
        return 1
    marks = ('_selftest_tmp', '_tmp_', '_probe_tmp')
    # 🔑 第一百一十八轮修一处**静默失效**：
    #    🔴 原实现只查 `os.path.basename(p)` —— 而本轮把临时文件搬进
    #       `_selftest_tmp/` 目录后，basename 变成 `_symlink_selftest`，
    #       **不再含任何 mark** → G410 明明该报却报 rc=0。
    #    🔑 判据：**特征可能在目录名上，不只文件名** —— 必须查**全路径**。
    #    🔑 与第七十九轮（段体 vs 文件）、第八十一轮（每条 vs 整组）同源：
    #       **判据对象选错层级，检查就静默变成恒真。**
    bad = sorted(p for p in ents
                 if any(m in p or m in os.path.basename(p) for m in marks))
    for pth in bad:
        print(f'🔴 索引里残留临时文件: {pth}')
    if bad:
        print('🔑 处置：git rm --cached <路径> 并删除磁盘文件')
        print('   🔴 不要改检查逻辑放过它 —— 它是真实残留物')
        print('=' * 70)
        return 1
    print(f'✅ 无自测临时文件残留（索引 {len(ents)} 项）')
    print('=' * 70)
    return 0


def cmd_check_selftest_reset():
    """🔑 G412：**自测临时目录清理自断言**（防 shutil.rmtree 静默失败）。

    🔴 第一百一十八轮诚实结论：
       `_selftest_reset()` 用 `shutil.rmtree(d, ignore_errors=True)` ——
       🔑 `ignore_errors=True` 意味着**失败不报错也不删**。目录里仍有东西时，
       调用方拿到路径照常使用，**"残留"与"已清理"看起来完全一样**。

    ✅ 第一百一十九轮加了清理后自断言，本入口**专门验证那条自断言本身**：

       | 段 | 验什么 |
       |---|---|
       | ① 真造脏目录 | 普通文件 + 嵌套子目录 + dangling symlink + 已被 `git add -f` 的项 |
       | ② 真跑清理   | 调用**真实实现** `_selftest_reset()`（不抄一份） |
       | ③ 断言结果   | 目录存在且**为空**、git 索引**无残留** |
       | ④ 🔑 **反证** | 把 `shutil.rmtree` 换成 no-op，验证自断言**确实会拒绝**（返回 None） |

    🔑 ④ 是核心：**只验"正常情况下清理成功"证明不了什么** ——
       rmtree 从来都是成功的，测一万次也是绿。必须造一个"清理失败"出来，
       看自断言**会不会响**。这与 79 轮"先证明它会响，再证明现在没响"同源。
    """
    print('=' * 70)
    print('🔑 **自测临时目录清理自断言**（G412）')
    print('=' * 70)
    ok_all = True
    d = os.path.join(ROOT, SELFTEST_TMP_DIR)

    # ① 真造脏目录（四种脏东西，覆盖 rmtree 与 git rm 两条清理路径）
    os.makedirs(os.path.join(d, 'nested'), exist_ok=True)
    open(os.path.join(d, 'plain.txt'), 'w', encoding='utf-8').write('x')
    open(os.path.join(d, 'nested', 'deep.txt'), 'w', encoding='utf-8').write('y')
    try:
        os.symlink('/tmp/_g412_dangling', os.path.join(d, 'dangling'))
    except OSError:
        pass
    try:
        subprocess.run(['git', 'add', '-f', '--', d], capture_output=True,
                       cwd=ROOT)
    except Exception:
        pass
    before = sorted(os.listdir(d))
    n_idx_before = len([x for x in subprocess.run(
        ['git', 'ls-files', '--', SELFTEST_TMP_DIR], capture_output=True,
        text=True, cwd=ROOT).stdout.strip().split('\n') if x.strip()])
    print(f'① 已造脏：磁盘 {len(before)} 项 {before} · git 索引 {n_idx_before} 项')

    # ② 真跑清理（**调用真实实现**）
    got = _selftest_reset()
    if got is None:
        print('🔴 清理后自断言**拒绝**了 —— 正常情况不该拒绝')
        print('=' * 70)
        return 1
    left = sorted(os.listdir(got))
    n_idx_after = len([x for x in subprocess.run(
        ['git', 'ls-files', '--', SELFTEST_TMP_DIR], capture_output=True,
        text=True, cwd=ROOT).stdout.strip().split('\n') if x.strip()])
    ok2 = (not left) and (n_idx_after == 0)
    print(f'② 清理后：磁盘 {len(left)} 项 · git 索引 {n_idx_after} 项')
    print(f'   {"✅ 已清空" if ok2 else "🔴 未清空"}')
    ok_all &= ok2

    # ③ 目录确实存在（makedirs 那步）
    ok3 = os.path.isdir(got)
    print(f'③ 目录可用：{"✅" if ok3 else "🔴"}')
    ok_all &= ok3

    # ④ 🔑 反证：让 rmtree 变成 no-op，验证自断言**会响**
    print()
    print('④ 反证：**让 shutil.rmtree 失效**（模拟静默失败）')
    real_rmtree = shutil.rmtree
    shutil.rmtree = lambda *a, **k: None      # 🔑 no-op：什么都不删
    try:
        # 再造点脏东西（此时 rmtree 不会删掉它）
        open(os.path.join(d, 'undeletable.txt'), 'w',
             encoding='utf-8').write('z')
        got_bad = _selftest_reset()
    finally:
        shutil.rmtree = real_rmtree
    refused = (got_bad is None)
    print(f'   自测实现返回：{"None（✅ 拒绝给结论）" if refused else "路径（🔴 照常放行）"}')
    if not refused:
        print('   🔴 rmtree 静默失败时自断言**没响** —— 与修复前同病')
    ok_all &= refused

    # ⑤ 🔑 反证②：**复刻修复前的实现**，证明它确实会静默放行
    #    🔑 与第一百轮"反证让修复有必要成为可验证事实"同源：
    #       只说"ignore_errors=True 会静默失败"是**声称**，跑出来给它看才是**证据**。
    print()
    print('⑤ 反证②：复刻**修复前**的实现（rmtree + makedirs + 直接返回）')

    def _old_reset():
        shutil.rmtree(d, ignore_errors=True)
        os.makedirs(d, exist_ok=True)
        return d        # 🔴 不看结果，直接返回

    real_rmtree2 = shutil.rmtree
    shutil.rmtree = lambda *a, **k: None
    try:
        open(os.path.join(d, 'still_here.txt'), 'w',
             encoding='utf-8').write('z')
        old_got = _old_reset()
        old_left = sorted(os.listdir(old_got))
    finally:
        shutil.rmtree = real_rmtree2
    print(f'   旧实现返回：{old_got} · 目录内容 {old_left}')
    if old_left:
        print('   🔑 旧实现**照常放行**（目录里还有东西却返回了路径）'
              ' —— 该 bug **真实存在**，本修复确有必要')
    else:
        print('   ⚠️ 未复现（rmtree 实际生效了）')

    # 收尾：真清一次
    _selftest_reset()
    print()
    print(f'{"✅ 清理自断言有效" if ok_all else "🔴 清理自断言无效"}')
    print('=' * 70)
    return 0 if ok_all else 1


def cmd_assert_selftest_ignored():
    """🔑 G411：**自测临时目录必须真被 gitignore**（第三道防线的前置断言）。

    🔴 第一百一十八轮：三道防线里，只有 ③ gitignore 是**根治**——
       ①②（独立目录 / 启动即清理）都只在"下次还会跑"时才生效；
       ③ 却是**即便残留一直在，`git add -A` 也收不进去**。
    🔴 但 ③ 只是一行文本 —— 将来被删掉或写错，**没有任何东西会提醒**，
       而 G410 只在"已经进了索引"之后才发现（那时已需人工清理）。

    🔑 两条判据：
       ① `.gitignore` 里必须有该条目（**文本层**）
       ② 🔑 **真跑 `git check-ignore`** —— 只验文本不够：
          gitignore 语法写错（少了斜杠、路径不对、被后面的 `!` 取消）时，
          **文本里明明有，实际却不生效**。
          🔑 与第八十轮"存在性 + 唯一性"同源：**"写了"不等于"生效了"**。
    """
    print('🔑 **自测临时目录 gitignore 断言**（G411）')
    print('=' * 70)
    import subprocess
    gi = os.path.join(ROOT, '.gitignore')
    if not os.path.isfile(gi):
        print('🔴 .gitignore 不存在 —— 拒绝给结论（不静默当"没有豁免"）')
        print('=' * 70)
        return 1
    text = open(gi, encoding='utf-8').read()
    lines = [ln.strip() for ln in text.split('\n')
             if ln.strip() and not ln.strip().startswith('#')]
    hit = [ln for ln in lines if SELFTEST_TMP_DIR in ln]
    ok1 = bool(hit)
    print(f'① .gitignore 条目：{"✅ " + str(hit) if ok1 else "🔴 未找到"}')
    if not ok1:
        print(f'   🔑 应含 `{SELFTEST_TMP_DIR}/`')
        print('=' * 70)
        return 1

    # ② 真跑 git check-ignore（**造一个真实路径去问 git**，不是自己推理）
    probe = os.path.join(SELFTEST_TMP_DIR, '_gitignore_probe')
    r = subprocess.run(['git', 'check-ignore', '-v', '--', probe],
                       capture_output=True, text=True, cwd=ROOT)
    ok2 = (r.returncode == 0)
    print(f'② 真跑 `git check-ignore {probe}`：'
          f'{"✅ 已忽略" if ok2 else "🔴 未忽略（rc=%d）" % r.returncode}')
    if not ok2:
        print('   🔴 文本里有这一行，但 git **实际不忽略** —— '
              '语法写错或被后面的 `!` 规则取消')
        print('=' * 70)
        return 1
    print(f'   {r.stdout.strip()}')
    print()
    print('✅ 自测临时目录**确实**被忽略 —— 残留不会被 `git add -A` 收进索引')
    print('=' * 70)
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
    ap.add_argument('--assert-trust-root', action='store_true',
                    help='G408：信任根闭合（代码元登记项 == 信任根文件）')
    ap.add_argument('--assert-meta-names', action='store_true',
                    help='G407：元登记项（登记表本身）必须闭合')
    ap.add_argument('--assert-path-consts', action='store_true',
                    help='G406：新产物路径常量必须已登记')
    ap.add_argument('--assert-dependent-names', action='store_true',
                    help='G405：所有被依赖的名字必须闭合')
    ap.add_argument('--assert-mirror-fn', action='store_true',
                    help='G404：镜像写入函数登记项必须真实存在且被使用')
    ap.add_argument('--assert-write-pairing', action='store_true',
                    help='G403：写台账与写镜像必须在同一函数内')
    ap.add_argument('--assert-fp-mirror', action='store_true',
                    help='G402：变更史镜像须与台账一致（防整段替换）')
    ap.add_argument('--assert-fp-history', action='store_true',
                    help='G401：基准变更史须闭合且可答“哪一轮变的、为什么变”')
    ap.add_argument('--assert-baseline-fp', action='store_true',
                    help='G400：断言基准指纹未被改过（防遗留“消失”被误读成“修复”）')
    ap.add_argument('--assert-history-known', action='store_true',
                    help='G396：历史遗留台账与实测**双向**一致')
    ap.add_argument('--assert-no-tmp-in-index', action='store_true',
                    help='G410：索引里不得残留自测临时文件（防中断后误传）')
    ap.add_argument('--assert-selftest-ignored', action='store_true',
                   help='G411 自测临时目录必须真被 gitignore')
    ap.add_argument('--check-selftest-reset', action='store_true',
                   help='G412：自测临时目录清理自断言（防 rmtree 静默失败）')
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

    if a.assert_trust_root:
        return cmd_assert_trust_root()
    if a.assert_meta_names:
        return cmd_assert_meta_names()
    if a.assert_path_consts:
        return cmd_assert_path_consts()
    if a.assert_dependent_names:
        return cmd_assert_dependent_names()
    if a.assert_mirror_fn:
        return cmd_assert_mirror_fn()
    if a.assert_write_pairing:
        return cmd_assert_write_pairing()
    if a.assert_fp_mirror:
        return cmd_assert_fp_mirror()
    if a.assert_fp_history:
        return cmd_assert_fp_history()
    if a.assert_baseline_fp:
        return cmd_assert_baseline_fp()
    if a.assert_history_known:
        os.chdir(ROOT)
        return cmd_assert_history_known()

    if a.assert_no_tmp_in_index:
        return cmd_assert_no_tmp_in_index()

    if a.assert_selftest_ignored:
        return cmd_assert_selftest_ignored()

    if a.check_selftest_reset:
        return cmd_check_selftest_reset()
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
