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
import ast
# 🔑 第一百三十五轮：**顶层**导入 `ast as _ast`。
#    🔴 本文件里有 3 处函数内 `import ast as _ast`（1170/3101/3192 行附近），
#       于是每个新函数都得"记得补一行"—— 119 轮已就 `subprocess` 治本过一次，
#       但**没覆盖到 `_ast`**，本轮写 G426 时第 5 次踩到同一个 NameError。
#    🔑 判据：重复出现的同类错误，应改到"让它不可能发生"，而不是每次补一处。
import ast as _ast
import base64
import glob
import hashlib
import io
import json
import os
# 🔑 第一百二十九轮：**顶层导入**（沿用第一百一十九轮的治本做法）。
#    🔴 在函数内 import 已导致四次 NameError（84/111/118/119 轮），
#       新函数每写一个就得记得补一行 —— 把它放在顶层，这类错误不可能再发生。
import re
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
# 🔑 第一百三十一轮：**轮次末尾回读函数名**登记项。
#    🔴 110 轮诚实结论③（镜像写入函数名硬编码）的同构问题：
#       若 G424 扫描器里写死 `_run_round_end_steps`，改函数名会让 G424
#       **静默失效** —— 表面"推送流程里有调用"，实际扫的是旧名字。
#    🔑 登记后由 G424 断言该函数**真定义 + 真被调用 + 真在表里**。
ROUND_END_FN = '_run_round_end_steps'
# 🔑 第一百三十二轮：**"轮次末尾步骤齐全"判据的唯一实现**登记项。
#    🔴 第一百三十一轮诚实结论②：G423 判据①与 G424 判据①是
#       **同一口径的两处实现** —— 改一处、漏一处，两条门禁会给出
#       **互相矛盾的结论**，而没有任何东西发现"它们已经不一致"。
#    🔑 登记后由 G425 断言：该函数真定义、被两条门禁**共同**调用、
#       且是**唯一**遍历 ROUND_END_REQUIRED_GIDS 的函数。
ROUND_END_STEPS_BAD_FN = '_round_end_steps_bad'

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
    # 🔑 第一百二十轮：G406 报出「未登记」—— 新增常量时忘了登记（第二次真实生效）
    'CLEANUP_ALLOWLIST': ('const', '清理类调用豁免表路径'),
    # 🔑 第一百二十七轮：G406 报出「未登记」—— 126 轮新增时忘了登记
    #    （G406 **第三次**在真实工作流中生效：115 轮 TRUST_ROOT_FILE、
    #      120 轮 CLEANUP_ALLOWLIST、本轮 ROUND_GAP_ALLOWLIST）
    'ROUND_GAP_ALLOWLIST': ('const', '轮次断号豁免清单路径（G418 依赖）'),
    # 🔑 第一百三十八轮：G428（哑门禁变异扫描）依赖的三个路径常量。
    #    🔴 按 115/120/127 轮同一条规程：新增常量**必须同步登记**，
    #       否则 G406 会报"未登记"（它已在真实工作流中生效三次）。
    'MUTATION_SCAN_FILE': ('const', '哑门禁扫描产物路径（G428 依赖）'),
    'MUTE_ALLOWLIST': ('const', '哑门禁豁免清单路径（G428 依赖）'),
    'MUTATION_TMP': ('const', '变异体副本路径（G428 写，已被 gitignore）'),
    # ── 登记项本身：改名会让 G403/G404 静默失效 ──
    'MIRROR_WRITE_FN': ('const', '镜像写入函数名登记项'),
    # 🔑 第一百三十一轮：G424 依赖它定位"推送主流程末尾的回读调用"
    'ROUND_END_FN': ('const', '轮次末尾回读函数名登记项'),
    '_run_round_end_steps': ('fn', '轮次末尾三项回读的唯一实现'),
    # 🔑 第一百三十二轮：G423/G424 共用判据的**唯一实现**
    #    （G406 会在新增常量忘记登记时报错，本条按规程登记）
    'ROUND_END_STEPS_BAD_FN': (
        'const', '轮次末尾步骤齐全判据的函数名登记项'),
    '_round_end_steps_bad': (
        'fn', 'G423/G424 共用的"步骤齐全"判据唯一实现'),
    # 🔑 第一百三十四轮：G425 判据④ 的唯一实现（防"只引用不调用"）
    '_gate_calls_helper': ('fn', '判断门禁函数体是否真调用 helper'),
    'TRUST_ROOT_FILE': ('const', '信任根文件路径（G408 依赖）'),
    # 🔑 第一百四十轮：G406 **第三次在真实工作流中生效**（115 轮 TRUST_ROOT_FILE、
    #    120 轮 CLEANUP_ALLOWLIST 之后）—— 139 轮新增它时忘了登记，无人提醒。
    'PUSH_LOCK_FILE': ('const', '推送互斥锁文件路径（G429 依赖，139 轮新增）'),
    'BLOB_NET_RETRY': ('const', 'blob 网络失败重试次数（G431 依赖，141 轮新增）'),
    'BLOB_RETRY_SLEEP': ('const', 'blob 重试退避基数秒（G431 依赖，141 轮新增）'),
    # 🔑 第一百四十二轮：G432（远端轮次对账）依赖的两个常量。
    #    按 115/120/127/139 轮同一条规程：新增常量**必须同步登记**。
    'REMOTE_ROUNDS_SINCE': ('const', '远端轮次对账起始轮（G432 依赖，142 轮新增）'),
    'REMOTE_ROUND_GAP_ALLOWLIST': ('const', '远端轮次缺口豁免清单路径（G432 依赖）'),
    # 🔑 第一百四十三轮：G433（文档轮次 ↔ 清单轮次互相印证）依赖的常量/函数。
    #    🔴 按 115/120/127/139/142 轮同一条规程：新增常量**必须同步登记**，
    #       否则 G406 会报"未登记"（它已在真实工作流中生效三次）。
    'DOC_ROUND_MIN_FILES': ('const', '文档轮次扫描 md 文件数下限（G433 依赖）'),
    'DOC_CLAIMS_SINCE': ('const', '文档↔清单对账起始轮（G433 依赖，143 轮新增）'),
    '_doc_claims_closure_bad': ('fn', 'G433 判据②③④⑤ 的唯一实现'),
    # 🔴 第一百三十五轮实测：**不得**在这里登记 'CRITERIA_ROOTS_REQUIRED'。
    #    它已进 SELF_REGISTERED_META（元项），G408 判据③ 规定"元项不得退回登记项"
    #    —— 否则递推重新开始。🔑 它由 G407（元项存在+被引用）守护，不靠本表。
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
                        'PATH_CONST_ALLOW_MIN_REASON',
                        'CRITERIA_ROOTS_REQUIRED')
# 🔑 第一百三十五轮：**判据存在性**的反向登记项（G426 依赖）。
#    🔴 134 轮破坏实测⑦⑧：G425 的判据⑧（行为反证）被删、判据⑨（判据不能验自己）
#       被改成恒真 —— **全部放行**，而 G425 其余判据照绿。
#    🔑 处置：把这两条判据的**存在性**写进 ledger/trust_root.json::CRITERIA_ROOTS，
#       并用本常量做**反向扫描**（代码 → 信任根），防"删掉一条信任根记录"。
#       （与 G406 反向扫描 DEPENDENT_NAMES 同构）
CRITERIA_ROOTS_REQUIRED = ('G425_c8_行为反证', 'G425_c9_判据不能验自己',
                           # 🔑 第一百三十六轮推广：G412/G413 的判据同样"可被改成桩"
                           'G412_c2_真跑真实实现', 'G412_c4_反证静默失败',
                           'G413_c1_扫描下限', 'G413_c5_豁免不可读须拒绝',
                           # 🔑 第一百四十轮：G430 的两条核心判据同样"可被改成桩"。
                           #    🔴 139 轮已证明：G429 的名字判据在"一致改名"下 rc=0；
                           #    🔴 且"实现体换成 return []"时 G429 三条判据**照绿**
                           #       —— 只有**真起进程跑真实实现**能发现。
                           'G430_c2_名字锚点', 'G430_c3_行为反证')
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


def req_err_desc(d):
    """🔑 **统一**描述 `req()` 的失败形态（第一百三十轮）。

    🔴 `req()` 有两种失败返回：
       - `HTTPError` → `{'__err': code, '__body': b}`；
       - 其它异常（断网 / DNS / 超时）→ `{'__err': 'NET:...'}`，**没有 `__body`**。
    🔑 直接写 `d['__body']` 在断网时抛 `KeyError` → **崩溃而非拒绝**。
       🔴 崩溃的 rc 也是 1，与"正确拒绝"**在退出码上无法区分**
          （104 轮「只捕 HTTPError 导致 URLError 崩溃」同源，本轮在**调用方**复发）。
    🔑 判据：**调用方必须能区分"拒绝了"与"代码坏了"** —— 前者有结论，后者没有。
    """
    if not isinstance(d, dict):
        return str(d)[:150]
    if '__err' not in d:
        return str(d)[:150]
    return f"{d['__err']} {str(d.get('__body', ''))[:150]}"


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
# 🔑 第一百二十轮：**清理类调用** —— 凡是"删东西"的调用，
#    都必须**验证结果**（带 ignore_errors=True 的不报错也不删；os.remove 失败抛异常但可能被 except 吞掉）。
#    🔴 第一百一十九轮诚实结论①：G412 只守 `_selftest_reset()` 一个函数，
#       其它 6 处 shutil.rmtree / os.remove 未验证 —— **同一模式可能在别处重演**。
# 🔴 必须匹配**限定名**（os.remove / shutil.rmtree / os.unlink），不能只匹配方法名：
#    `remove` 是极常见的方法名（`list.remove` / `set.remove`），只按方法名扫会
#    **把业务调用误判成清理调用** —— 实测 param_extract.py 的 only_old.remove(ko)
#    就被误报了两次。🔑 与 110 轮「grep 分不清写与只读」同源：**判据对象选错层级**。
CLEANUP_CALLS = ('os.remove', 'os.unlink', 'shutil.rmtree',
                 'os.rmdir', 'shutil.rmtree')
# 🔑 什么算"结果校验"：调用之后**查询了**被删路径的状态，或**显式处理了失败**。
CLEANUP_VERIFY_FNS = ('exists', 'lexists', 'isdir', 'isfile', 'listdir',
                      'islink', 'access')
# 🔑 豁免表（外部文件，与 scan_doc_allowlist.txt / rc_domain_allowlist.txt 同构）
CLEANUP_ALLOWLIST = os.path.join(ROOT, 'ledger', 'cleanup_allowlist.txt')
# 🔑 扫描下限：低于此数说明**扫描器本身失效了**（文件改名/调用方式变了）
CLEANUP_SCAN_MIN = 4

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
    """🔑 上传单个 blob（**网络层抖动必须重试** —— 第一百四十一轮）。

    🔴 真实事故：**连续三轮（137/138/139）内容始终没有抵达远端**，
       报的都是"域名解析失败"。实测一次推送 321 个文件里有 **26 个**
       因 `NET:URLError ... Temporary failure in name resolution` 失败，
       而**只要有一个失败，整次推送就中止**（fail-safe，但也意味着
       🔴 **一次抖动 = 整轮白干**）。
    🔑 判据：**网络抖动是可重试的失败，内容错误不是** ——
       只重试 `__err` 以 `NET:` 开头的（104 轮定义的网络层形态），
       HTTP 4xx/5xx 一律不重试（那是内容/权限问题，重试无意义且会放大故障）。
    """
    try:
        raw = blob_content(path)
    except Exception as e:
        return (path, None, f'读取失败: {e}')
    payload = {'content': base64.b64encode(raw).decode(),
               'encoding': 'base64'}
    d = req('POST', f'{API}/git/blobs', payload)
    for _i in range(BLOB_NET_RETRY):
        if '__err' not in d:
            break
        if not str(d.get('__err', '')).startswith('NET:'):
            break
        time.sleep(BLOB_RETRY_SLEEP * (_i + 1))
        d = req('POST', f'{API}/git/blobs', payload)
    if '__err' in d:
        return (path, None, f"HTTP {req_err_desc(d)}")
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

    # 🔑 第一百二十七轮：存在性**跨文件**查找（登记表在本文件，名字可能在别处）
    mconsts, mfns = _module_level_defs()
    for name, (kind, desc) in sorted(tbl.items()):
        g = globals().get(name)
        if kind == 'const':
            here = g is not None and g != ''
            ok = here or (name in mconsts)
            where = '本文件' if here else (mconsts.get(name) or '—')
        else:
            here = callable(g)
            ok = here or (name in mfns)
            where = '本文件' if here else (mfns.get(name) or '—')
        n_ref = refs.get(name, 0)
        if not ok:
            bad.append(f'{kind} {name}（{desc}）**不存在或为空**'
                       f'（已跨 scripts/*.py 查找）')
        elif n_ref == 0:
            bad.append(f'{name}（{desc}）**无任何引用** —— '
                       f'改名后门禁会静默失效')
        else:
            print(f'   ✅ {kind:5s} {name:22s} 引用 {n_ref:2d} 处 · '
                  f'@{where} · {desc}')
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

def _module_level_defs():
    """🔑 扫 `scripts/*.py` 的**模块级**定义，返回 (常量名→文件, 函数名→文件)。

    🔴 第一百二十七轮**实测发现**：`DEPENDENT_NAMES` 登记表在 `push_api.py`，
       而 G405 的"存在性"判据只用 `globals().get(name)` —— **只看本文件**。
       🔑 于是登记一个**定义在别处**的名字（如 `claim_verify.py::ROUND_GAP_ALLOWLIST`）
          会被误报"不存在或为空"，而它其实是**真被依赖**的。
    🔑 跨文件扩展**不是削弱判据**：名字在哪都不存在 → 仍然报错；
       只是把"存在性"的查找范围从单文件扩到 `scripts/`（与 G406 同范围）。
    """
    import ast
    consts, fns = {}, {}
    for f in sorted(glob.glob(os.path.join(HERE, '*.py'))):
        base = os.path.basename(f)
        try:
            tree = ast.parse(open(f, encoding='utf-8').read())
        except (SyntaxError, ValueError):
            continue
        for n in tree.body:
            if isinstance(n, ast.Assign):
                for t in n.targets:
                    if isinstance(t, ast.Name):
                        consts.setdefault(t.id, base)
            elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                fns.setdefault(n.name, base)
    return consts, fns


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

def _dynamic_call_name(node):
    """从 `globals()['f']` / `getattr(m, 'f', ...)` 里取出函数名；否则 None。"""
    if isinstance(node, ast.Subscript):
        sl = node.slice
        if isinstance(sl, ast.Constant) and isinstance(sl.value, str):
            return sl.value
        return None
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
            and node.func.id == 'getattr' and len(node.args) >= 2:
        a1 = node.args[1]
        if isinstance(a1, ast.Constant) and isinstance(a1.value, str):
            return a1.value
    return None


def _criteria_ast_missing(fn_node, specs):
    """🔑 G426 判据⑥：**AST 结构判据** —— 不认写法（第一百三十六轮补①）。

    🔴 第一百三十五轮诚实结论①：`require` 是**文本匹配** ——
       改写法但保留语义会**误报**；在别处复制一段相同文本可**蒙混**。
    🔑 本函数改为按 **AST 节点结构**判定：不管你写成 `x = f()` 还是
       `x = getattr(mod, 'f')()` 之外的等价写法，只要**结构在**就算在。

    | type | 含义 |
    |---|---|
    | `call` | 函数体内必须**调用**该名字（`Call(func=Name(name))`） |
    | `call_attr` | 必须调用 `obj.attr(...)` |
    | `assign_attr` | 必须**赋值**给 `obj.attr`（如 monkeypatch `shutil.rmtree = ...`）；可再加 `value` 约束 RHS 形状（`lambda`/`name`） |
    | `ref_name` | 函数体内必须**引用**该名字（`Name` Load **或**字符串常量）—— 🔑 第一百四十轮新增：`call` 认不出「`fn = globals().get('f')` 再 `fn()`」这一形态（与 133 轮"判据不认写法"同源，第 4 次） |

    🔑 `call` **不认写法**：除 `Name` 外还识别两种**动态取用**形态 ——
       `globals()['f']()` 与 `getattr(mod, 'f')()`。
       🔴 否则"改写法但保留语义"会**误报**，这就是判据⑥ 要解决的 135 轮①。
    """
    calls = set()
    call_attrs = set()
    assign_attrs = set()
    assign_shapes = set()
    ref_names = set()
    for n in ast.walk(fn_node):
        # 🔑 第一百四十轮：`ref_name` —— 引用即可（Name Load 或字符串常量）
        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load):
            ref_names.add(n.id)
        elif isinstance(n, ast.Constant) and isinstance(n.value, str):
            ref_names.add(n.value)
        if isinstance(n, ast.Call):
            f = n.func
            if isinstance(f, ast.Name):
                calls.add(f.id)
            elif isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name):
                call_attrs.add((f.value.id, f.attr))
            else:
                # 🔑 动态取用：`globals()['f']()` / `getattr(mod, 'f')()`
                got = _dynamic_call_name(f)
                if got:
                    calls.add(got)
        if isinstance(n, ast.Assign):
            for t in n.targets:
                if isinstance(t, ast.Attribute) and isinstance(t.value, ast.Name):
                    v = n.value
                    shape = 'lambda' if isinstance(v, ast.Lambda) \
                        else ('name' if isinstance(v, ast.Name) else 'other')
                    assign_attrs.add((t.value.id, t.attr))
                    assign_shapes.add((t.value.id, t.attr, shape))
    miss = []
    for s in specs:
        if not isinstance(s, dict):
            miss.append(s)
            continue
        t = s.get('type')
        if t == 'call':
            hit = s.get('name') in calls
        elif t == 'call_attr':
            hit = (s.get('obj'), s.get('attr')) in call_attrs
        elif t == 'assign_attr':
            hit = (s.get('obj'), s.get('attr')) in assign_attrs
            vs = s.get('value')
            if hit and vs:
                hit = (s.get('obj'), s.get('attr'), vs) in assign_shapes
        elif t == 'ref_name':
            # 🔑 第一百四十轮新增：只要求**引用**该名字（不要求调用形态）
            hit = s.get('name') in ref_names
        else:
            hit = False
        if not hit:
            miss.append(s)
    return miss


def cmd_assert_criteria_roots():
    """🔑 G426：**判据存在性信任根闭合**。

    🔴 第一百三十四轮破坏实测⑦⑧（本条要解决的那两条）：
       - 把 G425 判据⑨ 改成 `used = True`（恒真）   → ✅ **放行** rc=0
       - 删掉 G425 判据⑧ 整段（行为反证）           → ✅ **放行** rc=0
       而 G425 其余判据照绿 —— 这两条判据**自身没有外部守护**。

    🔑 处置（与 115 轮「停止递推 + 明示信任根」同构）：
       把「这两条判据必须存在」写进 `ledger/trust_root.json::CRITERIA_ROOTS`
       （**独立于代码**的文件），并断言代码里确实还有它们。
       🔴 已知边界：同时改代码与本文件仍会绕过（109 轮同源），靠 git 审计兜底。

    🔑 五条判据：
       ① 信任根必须可读 —— 读不到**拒绝给结论**（读不到 ≠ 没有）
       ② `CRITERIA_ROOTS_REQUIRED` 的每个键都必须在信任根里登记
          （🔑 **反向扫描**：代码 → 信任根，防"悄悄删掉一条信任根记录"）
       ③ 每条登记的判据：`defined_in` 存在 · `in_fn` 真存在（AST）
       ④ 每个 `require` 标记串都出现在**该函数行范围内**
          （🔴 AST 求行范围**并排除自身** —— 93 轮"检查器扫到自己"）
       ⑤ `why` ≥ 20 字符（🔴 否则信任根退化成无理由白名单）
          · `round` ≤ 文档最大轮次（G389 同款，防"来自未来的批准"）
       ⑥ `require_ast`：**AST 结构判据**（第一百三十六轮新增）
          🔴 135 轮①：纯文本匹配改写法会误报、复制文本可蒙混。
      ⑦ 每个标记串在该函数内**必须唯一**（第一百三十六轮新增）
          🔴 135 轮发现一：`_n.args` 出现 3 次时，删掉判据**仍放行**。
    """
    print('🔑 **判据存在性信任根闭合**（G426）')
    print('=' * 70)
    tr = _trust_root()
    if tr is None:
        print('🔴 信任根不可读 —— 拒绝给结论（不静默当"没有判据"）')
        print('=' * 70)
        return 1
    req = globals().get('CRITERIA_ROOTS_REQUIRED')
    if not req:
        print('🔴 CRITERIA_ROOTS_REQUIRED **未登记或为空** —— 拒绝给结论')
        print('=' * 70)
        return 1
    crit = tr.get('CRITERIA_ROOTS')
    if not isinstance(crit, dict) or not [k for k in crit if k != '_why']:
        print('🔴 信任根未登记 CRITERIA_ROOTS —— 拒绝给结论')
        print('=' * 70)
        return 1
    bad = []
    # ② 反向扫描：代码常量 → 信任根
    missing = [k for k in req if k not in crit]
    if missing:
        bad.append(f'CRITERIA_ROOTS_REQUIRED 中的 {missing} **未在信任根登记**'
                   f' —— 🔴 删掉信任根记录会让对应判据失去守护')
    mx = None
    try:
        mx = _doc_max_round()
    except Exception:
        mx = None
    src_cache = {}
    checked = 0
    for k in sorted(k for k in crit if k != '_why'):
        spec = crit[k]
        if not isinstance(spec, dict):
            bad.append(f'判据 {k} 的登记不是 dict —— 拒绝给结论')
            continue
        di = (spec.get('defined_in') or '').strip()
        fn_name = (spec.get('in_fn') or '').strip()
        why = (spec.get('why') or '').strip()
        rnd = spec.get('round')
        if len(why) < 20:
            bad.append(f'判据 {k} 的 why 过短（{len(why)}<20）—— 🔴 必须写明"为什么它算根"')
        if not isinstance(rnd, int) or rnd <= 0:
            bad.append(f'判据 {k} 未登记批准轮次 round —— 拒绝给结论')
        elif mx is not None and rnd > mx:
            bad.append(f'判据 {k} 的批准轮次 {rnd} **大于文档最大轮次 {mx}**'
                       f' —— 🔴 来自未来的批准')
        if not di:
            bad.append(f'判据 {k} 未登记 defined_in —— 拒绝给结论')
            continue
        fp = os.path.join(ROOT, di)
        if not os.path.exists(fp):
            bad.append(f'判据 {k} 的 defined_in 指向不存在的文件：{di}')
            continue
        if fp not in src_cache:
            src_cache[fp] = open(fp, encoding='utf-8').read()
        text = src_cache[fp]
        try:
            tree = _ast.parse(text)
        except SyntaxError:
            bad.append(f'判据 {k}：{di} 语法错误 —— 拒绝给结论')
            continue
        # ③ + ④ AST 求函数行范围
        node = None
        for n in _ast.walk(tree):
            if isinstance(n, (_ast.FunctionDef, _ast.AsyncFunctionDef)) \
                    and n.name == fn_name:
                node = n
                break
        if node is None:
            bad.append(f'判据 {k}：{di} 中**找不到函数** {fn_name} —— 拒绝给结论')
            continue
        lo = node.lineno
        hi = getattr(node, 'end_lineno', None) or node.lineno
        body = '\n'.join(text.splitlines()[lo - 1:hi])
        marks = spec.get('require')
        ast_spec = spec.get('require_ast')
        if marks is None and ast_spec is None:
            bad.append(f'判据 {k} 既未登记 require 也未登记 require_ast'
                       f' —— 拒绝给结论')
            continue
        ok_mark = True
        if marks is not None:
            if not (isinstance(marks, list) and marks):
                bad.append(f'判据 {k} 的 require 不是非空列表 —— 拒绝给结论')
                ok_mark = False
            else:
                # 判据④ 存在性 + 判据⑦ **唯一性**
                gone = [m for m in marks if m not in body]
                dup = [m for m in marks if body.count(m) > 1]
                if gone:
                    bad.append(f'判据 {k} 的标记串 {gone} **在 {fn_name}() 内找不到**'
                               f' —— 🔴 判据可能已被删除或改成恒真')
                    ok_mark = False
                if dup:
                    cnt = {m: body.count(m) for m in dup}
                    bad.append(f'判据 {k} 的标记串**不唯一** {cnt}'
                               f' —— 🔴 "判据被删"与"标记仍在别处命中"'
                               f'无法区分（135 轮发现一）')
                    ok_mark = False
        ok_ast = True
        if ast_spec is not None:
            if not (isinstance(ast_spec, list) and ast_spec):
                bad.append(f'判据 {k} 的 require_ast 不是非空列表 —— 拒绝给结论')
                ok_ast = False
            else:
                miss_ast = _criteria_ast_missing(node, ast_spec)
                if miss_ast:
                    bad.append(f'判据 {k} 的 AST 结构判据 {miss_ast}'
                               f' **在 {fn_name}() 内不满足**'
                               f' —— 🔴 判据可能已被删除')
                    ok_ast = False
        if ok_mark and ok_ast:
            checked += 1
            extra = f' · AST {len(ast_spec)} 条' if ast_spec else ''
            print(f'   ✅ 判据 {k} 在 {fn_name}():{lo}-{hi} 内'
                  f' 标记 {len(marks or [])} 个均唯一且在{extra}'
                  f' · 批准于第 {rnd} 轮')
    print(f'   信任根 {TRUST_ROOT_FILE}')
    print(f'   已登记判据 {len([k for k in crit if k != "_why"])} 条'
          f' · 反向必需 {len(req)} 条 · 校验通过 {checked} 条'
          f' · 文档最大轮次 {mx}')
    if bad:
        print()
        for b in bad:
            print(f'🔴 {b}')
        print('=' * 70)
        return 1
    print()
    print(f'✅ 判据存在性闭合：{checked} 条判据均仍在代码中'
          f'（134 轮破坏⑦⑧ 的放行方向已被封住）')
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
        print(f"🔴 无法读取远端 tree: HTTP {req_err_desc(d)}")
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
        # 🔑 第一百二十轮：**清理后自断言**（G413 要求）
        #    🔴 117 轮事故正源于此：进程被杀 → finally 未执行 → 残留被 git add -A 收走。
        #    🔑 这里再加一层：即便 rmtree/remove 静默失败，也要**查出来并报出来**。
        leftover = sorted(os.listdir(d)) if os.path.isdir(d) else []
        if leftover:
            print(f'\n🔴 自测清理后目录**非空** {leftover[:5]} —— 清理静默失败')
            ok_all = False
        idx_left = subprocess.run(['git', 'ls-files', '--', SELFTEST_TMP_DIR],
                                  capture_output=True, text=True,
                                  cwd=ROOT).stdout.strip()
        if idx_left:
            print(f'\n🔴 自测清理后 git 索引仍有残留 {idx_left.split()[:5]}')
            ok_all = False

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


def _scan_cleanup_calls():
    """🔑 扫出全部**清理类调用**并判定"是否带结果校验"。

    🔑 返回 `[(key, kind, verified, src)]`：
       - `key`  = `文件名::函数名::参数表达式`（比行号稳定，行号随代码增删漂移）
       - `kind` = rmtree / remove / unlink
       - `verified` = 调用之后是否**查询了状态**或**显式处理了失败**

    🔑 判据：什么算"结果校验"（三选一）
       ① 调用点之后出现**存在性检查**（exists/lexists/isdir/listdir/…）
       ② 调用被 `try` 包裹且 `except` 分支**不只是 pass**（真的处理了失败）
       ③ 之后直接 `return None` / `raise`（拒绝继续）
    🔴 反之：`shutil.rmtree(d, ignore_errors=True)` 后直接往下走、
       `try: os.remove(p) except OSError: pass` —— **都不算**。
       🔑 后者尤其要说明：except 确实**接住了**异常，但接着 `pass` 掉，
          与"没发生过"**完全无法区分**（与 118 轮 `except Exception: pass` 吞掉 NameError 同源）。
    """
    import ast
    out = []
    # 🔴 HERE 是 scripts/ 本身，不能写成 HERE/scripts —— 那样匹配到 0 个文件，
    #    扫描器会**静默返回空**（不报错），正因此需要下面的 CLEANUP_SCAN_MIN 下限。
    for fp in sorted(glob.glob(os.path.join(ROOT, 'scripts', '*.py'))):
        base = os.path.basename(fp)
        try:
            src = open(fp, encoding='utf-8').read()
            tree = ast.parse(src)
        except Exception:
            continue
        for fn in [n for n in ast.walk(tree)
                   if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]:
            fn_end = getattr(fn, 'end_lineno', fn.lineno)
            # 该函数内所有"校验性"调用的行号
            verify_lines = set()
            for c in ast.walk(fn):
                if isinstance(c, ast.Call):
                    nm = c.func.attr if isinstance(c.func, ast.Attribute) else (
                        c.func.id if isinstance(c.func, ast.Name) else '')
                    if nm in CLEANUP_VERIFY_FNS:
                        verify_lines.add(c.lineno)
            # 该函数内所有 try：行号区间 → handler 是否有实质处理
            try_zones = []
            for t in ast.walk(fn):
                if isinstance(t, ast.Try):
                    lo = min(x.lineno for x in t.body)
                    hi = max(getattr(x, 'end_lineno', x.lineno) for x in t.body)
                    real = False
                    for h in t.handlers:
                        for st in h.body:
                            if not isinstance(st, ast.Pass):
                                real = True
                    try_zones.append((lo, hi, real,
                                      max(getattr(x, 'end_lineno', x.lineno)
                                          for x in t.finalbody)
                                      if t.finalbody else -1))
            for c in ast.walk(fn):
                if not isinstance(c, ast.Call):
                    continue
                if isinstance(c.func, ast.Attribute) and \
                        isinstance(c.func.value, ast.Name):
                    nm = f'{c.func.value.id}.{c.func.attr}'
                elif isinstance(c.func, ast.Name):
                    nm = c.func.id
                else:
                    nm = ''
                if nm not in CLEANUP_CALLS:
                    continue
                kind = nm.split('.')[-1]
                ln = c.lineno
                arg = ''
                if c.args:
                    try:
                        arg = ast.unparse(c.args[0])
                    except Exception:
                        arg = '<?>'
                verified = False
                # ① 之后有存在性检查
                if any(v > ln for v in verify_lines):
                    verified = True
                # ② 在 try 内且 handler 有实质处理（或在 finally 里查了）
                for lo, hi, real, fend in try_zones:
                    if lo <= ln <= hi and real:
                        verified = True
                # ③ 之后 return None / raise
                for n2 in ast.walk(fn):
                    if isinstance(n2, ast.Raise) and n2.lineno > ln:
                        verified = True
                    if isinstance(n2, ast.Return) and n2.lineno > ln \
                            and isinstance(n2.value, ast.Constant) \
                            and n2.value.value is None:
                        verified = True
                out.append((f'{base}::{fn.name}::{arg}', kind, verified, ln))
    return out


def _read_cleanup_allowlist():
    """🔑 读豁免表；🔴 不可读返回 None（**拒绝给结论**，不静默当"没有豁免"）。"""
    try:
        txt = open(CLEANUP_ALLOWLIST, encoding='utf-8').read()
    except OSError:
        return None
    res = {}
    for ln in txt.strip().split('\n'):
        ln = ln.strip()
        if not ln or ln.startswith('#'):
            continue
        # 🔑 键形如 `文件::函数::参数`，内部含 `::` —— 不能按第一个冒号切，
        #    否则键会被切成 `push_api.py`（实测过，导致全部豁免判定为僵尸）。
        #    ✅ 键内部无空格，故以 **`: `（冒号+空格）** 作分隔，只切一次。
        if ': ' not in ln:
            return None
        k, reason = ln.split(': ', 1)
        res[k.strip()] = reason.strip()
    return res


def cmd_assert_cleanup_verified():
    """🔑 G413：全部**清理类调用**都必须带结果校验（或被登记豁免）。

    🔴 第一百一十九轮诚实结论①：G412 只守 `_selftest_reset()` 一个函数，
       其它 6 处 `shutil.rmtree` / `os.remove` 未验证 —— **同一模式可能在别处重演**。
    ✅ 本条把它从"**一个函数**"推广成"**一类写法**"。

    | 判据 | 防什么 |
    |---|---|
    | ① 扫描到 ≥ CLEANUP_SCAN_MIN 处 | 🔑 **扫描器自己失效**（返回空集） |
    | ② 未带校验的必须在豁免表内 | 清理静默失败 |
    | ③ 豁免键必须真实存在于扫描结果 | 僵尸豁免（豁免了不存在的东西） |
    | ④ 豁免理由非空且 ≥ 10 字符 | 豁免退化成"随便放行" |
    | ⑤ 豁免表不可读 → 拒绝给结论 | "读不到" ≠ "没有豁免" |
    """
    print('=' * 70)
    print('🔑 **清理类调用结果校验**（G413）')
    print('=' * 70)
    rows = _scan_cleanup_calls()
    ok_all = True

    # ① 下限 —— 防扫描器静默失效
    print(f'① 扫描到 {len(rows)} 处清理调用（下限 {CLEANUP_SCAN_MIN}）')
    if len(rows) < CLEANUP_SCAN_MIN:
        print(f'🔴 少于下限 —— 扫描器可能已失效（文件改名？调用方式变了？）')
        print('=' * 70)
        return 1
    print('   ✅ 扫描器有效')

    allow = _read_cleanup_allowlist()
    if allow is None:
        print(f'🔴 豁免清单不可读：{CLEANUP_ALLOWLIST} —— 拒绝给结论')
        print('=' * 70)
        return 1

    bad = [r for r in rows if not r[2]]
    print(f'\n② 未带结果校验 {len(bad)} 处：')
    unlisted = []
    for key, kind, _v, ln in bad:
        reason = allow.get(key)
        if reason is None:
            unlisted.append((key, kind, ln))
            print(f'   🔴 {key}  ({kind} @ L{ln}) —— **未登记豁免**')
        else:
            print(f'   ✅ {key} —— 已豁免')
    if unlisted:
        ok_all = False

    # ③ 僵尸豁免
    found = {r[0] for r in rows}
    zombie = [k for k in allow if k not in found]
    print(f'\n③ 僵尸豁免检查（登记了但扫描不到 {len(zombie)} 条）')
    for k in zombie:
        print(f'   🔴 {k} —— 代码里已无此调用，应删除')
    if zombie:
        ok_all = False

    # ④ 理由充分性
    print('\n④ 豁免理由检查')
    for k in sorted(allow):
        r = allow[k]
        if len(r) < 10:
            print(f'   🔴 {k} 理由过短（{len(r)} 字符）：{r!r}')
            ok_all = False
    if not any(len(v) < 10 for v in allow.values()):
        print(f'   ✅ {len(allow)} 条豁免理由均充分')

    print()
    print(f'{"✅ 全部清理调用均已校验或已登记豁免" if ok_all else "🔴 存在未校验的清理调用"}')
    print('=' * 70)
    return 0 if ok_all else 1


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
        # 🔑 第一百二十轮：**清理后自断言**（G413 要求）
        #    🔴 os.remove 失败会抛 OSError，但上面 `except OSError: pass` 把它吞了
        #       —— 失败与成功**完全无法区分**（118 轮同病）。这里补查一次。
        if os.path.lexists(gl):
            print(f'\n🔴 自测清理后 {gl} **仍存在** —— 清理静默失败')
            ok_all = False

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


def _claims_max_index():
    """🔑 ledger/ 里**磁盘上**已有的最大清单编号（不要求在 git 索引里）。"""
    d = os.path.join(ROOT, 'ledger')
    if not os.path.isdir(d):
        return 0
    mx = 0
    for f_ in os.listdir(d):
        m = re.match(r'claims_(\d+)\.txt$', f_)
        if m:
            mx = max(mx, int(m.group(1)))
    return mx


def cmd_assert_round_claims():
    """🔑 G421：**推送前必须已有本轮声明清单，且已纳入 git 索引**。

    🔴 第一百二十九轮真实事故（本条的存在理由）：
        第一百二十七轮的推送在 **08:07:59** 完成，
        而 `ledger/claims_127.txt` 在 **08:17:47** 才写入 → **漏传**。
        🔑 关键：**G390（防漏传）当时是绿的** ——
           文件在推送那一刻还**不存在**，无从检查。
        🔑 判据：**"没检查出问题"与"没问题"是两回事** ——
           G390 守的是"已存在但没 add"，守不住"还没写就推了"。

    🔑 取 N = max(文档最大轮次, ledger 里最大清单编号)：
       - 文档已写 129 轮但清单没写 → N=129 → 缺文件 → 🔴
       - 清单写了 129 但文档还没提 → N=129 → 只查它有没有进索引 → 🔴（防忘 add）
       🔑 两个方向都有意义，缺任一个都会漏掉一类事故。

    🔑 轮次探测不到时 **拒绝给结论**（与 G389 / G408 同源，不猜）。
    """
    print('=' * 70)
    print('🔑 G421 推送前本轮清单检查（防"还没写就推了"）')
    print('=' * 70)
    docs = _doc_max_round()
    cmax = _claims_max_index()
    n = max(docs, cmax)
    if n <= 0:
        print('🔴 无法确定当前轮次（文档未提及轮次，且 ledger 无清单）'
              ' —— 拒绝给结论')
        print('=' * 70)
        return 1
    rel = f'ledger/claims_{n}.txt'
    p = os.path.join(ROOT, 'ledger', f'claims_{n}.txt')
    if not os.path.isfile(p):
        print(f'🔴 缺 {rel} —— **本轮清单尚未写**')
        print(f'   （文档最大轮次 {docs} · ledger 最大清单编号 {cmax}）')
        print('   🔑 推送后补写 = 漏传：本轮做过什么将无法复核（127 轮真实事故）')
        print('=' * 70)
        return 1
    # 🔑 git 不可用 ≠ 文件没进索引（与 G390 同源：读不到要拒绝，不能当"没有"）
    if os.system('git rev-parse --is-inside-work-tree >/dev/null 2>&1') != 0:
        print('🔴 git 不可用 —— **无法确定**清单是否已纳入索引，拒绝给结论')
        print('=' * 70)
        return 1
    idx = list_files()
    if rel not in idx:
        print(f'🔴 {rel} **不在 git 索引里** —— 推送会漏传')
        print('   🔑 处理办法：git add -A（推送前 add，不是推送后）')
        print('=' * 70)
        return 1
    print(f'✅ 第 {n} 轮清单已写且已纳入索引'
          f'（文档最大轮次 {docs} · ledger 最大清单编号 {cmax}）')
    print('=' * 70)
    return 0


# 🔑 第一百三十轮：**轮次末尾必跑的三项**（第一百二十九轮诚实结论①）
#    🔴 129 轮：G421 只在"推送那一刻"有效 —— 推完又写新文件**仍无人发现**；
#       claims_127.txt 的漏传是靠**人工**核对远端 tree 才暴露的，不是门禁。
#    🔑 所以轮次末尾必须再问一次："本地有的，远端都有吗？"
#    🔑 mode='report' 的原因（如实写明，不掩饰）：
#       G391 是**全量四层比对 + 本地未提交修改**，回归跑完必然有产物变脏
#       （106 轮已知），若严格跑则**永远红**，等于把它从流程里挤出去。
#       故第三项用报告模式——**必跑但不阻断**，异常仍会打印出来。
ROUND_END_STEPS = (
    ('--assert-round-claims', 'G421', 'strict',
     '推送前本轮清单必须已写且已入索引'),
    ('--assert-index-pushed', 'G422', 'strict',
     '本地索引 ⊆ 远端 tree（轮次末尾再验一次）'),
    ('--verify-push', 'G391', 'report',
     '推送完整性回读（缺失/多余/内容/权限四层，报告模式）'),
    # 🔑 第一百四十二轮：G421/G422 都查**文件**，查不到**轮次**。
    #    🔴 141 轮实测：137~140 四轮从未独立抵达远端，
    #       而 141 推送后文件全都在 → G422 照绿。文件齐 ≠ 轮次齐。
    ('--assert-remote-rounds', 'G432', 'strict',
     '远端轮次对账（本轮内容必须真的抵达远端）'),
)
# 🔑 这三项缺一不可（G423 断言）：删任一个都会重新打开 127 轮那个洞。
ROUND_END_REQUIRED_GIDS = ('G421', 'G422', 'G391')


def cmd_assert_index_pushed():
    """🔑 G422：**本地索引 ⊆ 远端 tree**（轻量：只比路径，一次 API）。

    🔴 第一百二十九轮诚实结论①：G421 只在"推送那一刻"有效，
       推完又写的文件**没有任何门禁再看一眼**（127 轮真实漏传事故）。
    🔑 判据：**"推送前检查通过" ≠ "推完就没新增"** ——
       必须在**轮次末尾**再问一次"本地有的远端都有吗"。

    🔑 与 G391 的分工（两者互补，不可互相替代）：
       - G391 **四层全比**（缺失 / 多余 / 内容 sha / mode）+ 本地未提交修改，
         🔴 因此只在**推送刚结束**时严格跑（其后跑回归会写产物 → 必然不等）；
       - G422 **只比路径**且**只看缺失方向**，一次 API、秒级，
         ✅ 所以能放进**自动回归**，每轮都被跑一次。
       🔑 远端"多余"在此**只警告不阻断** —— 那是残留，不是漏传（G391 才管）。

    🔑 远端不可达 / git 不可用 → **拒绝给结论**（与 G390 / G421 同源，不猜）。
    """
    print('=' * 70)
    print('🔑 G422 本地索引 ⊆ 远端 tree（防"推完又写"无人发现）')
    print('=' * 70)
    loc = local_index_entries()
    if not loc:
        print('🔴 **无法确定**本地受管文件（git 不可用） —— 拒绝给结论')
        print('=' * 70)
        return 1
    print(f'\n🔑 本地受管文件 {len(loc)} 个')
    d = req('GET', f'{API}/git/trees/main?recursive=1')
    if '__err' in d:
        print(f"🔴 无法读取远端 tree: HTTP {req_err_desc(d)}"
              f" —— 拒绝给结论")
        print('=' * 70)
        return 1
    if d.get('truncated'):
        print('🔴 远端 tree **被截断** —— 无法完整比对，拒绝给结论')
        print('=' * 70)
        return 1
    rem = set(t['path'] for t in d['tree'] if t.get('type') == 'blob')
    print(f'🔑 远端 blob     {len(rem)} 个')
    missing = sorted(set(loc) - rem)
    extra = sorted(rem - set(loc))
    if missing:
        print(f'\n🔴 **本地有而远端没有** {len(missing)} 个 —— 漏传：')
        for p_ in missing[:10]:
            print(f'   - {p_}')
        print('   🔑 处理办法：git add -A && git commit && 重新推送')
        print('   🔑 这是 G421 守不住的方向：G421 只查本轮**清单**一类文件，'
              '本条查**全部**文件')
        print('=' * 70)
        return 1
    if extra:
        print(f'\n⚠️ 远端残留（远端有、本地无）{len(extra)} 个 —— '
              f'**不阻断**，由 G391 管：')
        for p_ in extra[:10]:
            print(f'   - {p_}')
    print('\n✅ 本地索引全部已推送'
          f'（{len(loc)} 个文件，远端残留 {len(extra)} 个不阻断）')
    print('=' * 70)
    return 0


def _run_round_end_steps(skip_gids=()):
    """🔑 轮次末尾三项回读的**唯一实现**（cmd_round_end 与推送主流程共用）。

    🔴 第一百轮教训：自测/复用若**复刻一份**判断逻辑，
       把真实实现改坏时自测仍然绿（"测了自己抄的那份"）。
    🔑 所以 G424 断言的是**推送主流程调用本函数**，而不是"看起来跑了三项"。
    """
    print('=' * 70)
    print('🔑 轮次末尾必跑：三项回读远端检查')
    print('=' * 70)
    rc = 0
    ran = 0
    for flag, gid, mode, why in ROUND_END_STEPS:
        if gid in set(skip_gids):
            print(f'\n### {gid}  {flag}  [跳过]  —— {why}')
            continue
        ran += 1
        print(f'\n### {gid}  {flag}  [{mode}]  —— {why}')
        cmd = [sys.executable, os.path.abspath(__file__), flag]
        if mode == 'report':
            cmd.append('--report')
        r = subprocess.run(cmd, cwd=ROOT)
        if r.returncode != 0:
            rc = 1
    print('\n' + '=' * 70)
    if rc == 0:
        print(f'✅ 轮次末尾 {ran} 项全部通过 —— 本轮产物与清单均已抵达远端')
    else:
        print('🔴 轮次末尾检查未全通过 —— 上面标红的项必须先处理再收工')
    print('=' * 70)
    return rc


def cmd_round_end():
    """🔑 轮次末尾必跑：G421 + G422 + G391(报告)。

    🔑 存在理由：第一百二十九轮诚实结论① ——
       "根治要'轮次末尾再回读一次远端'，而 G391 是人工门禁，没人跑"。
    🔑 本入口把"回读远端"从**人工自觉**变成**一条命令**。
    🔑 第一百三十一轮：实现抽到 `_run_round_end_steps`，
       使**推送主流程**与**手动入口**共用同一份，不复刻。
    """
    return _run_round_end_steps()


def _round_end_steps_bad():
    """🔑 **"轮次末尾步骤齐全"判据的唯一实现**（G423 与 G424 共用）。

    🔴 第一百三十一轮诚实结论②：
       G423 判据①（ROUND_END_STEPS 非空 + 三个必需编号齐全）与
       G424 判据①是**同一口径的两处实现**。
    🔑 危害不是"代码重复"，而是**改一处漏一处**时：
       两条门禁会给出**互相矛盾的结论**，而没有任何东西发现它们已不一致
       （与 93 轮"两处 rc 合法域"、106 轮"两处都写台账"同源）。
    🔑 返回**问题清单**（空列表 = 通过），由调用方决定怎么报。
    """
    bad = []
    if not ROUND_END_STEPS:
        bad.append('ROUND_END_STEPS 为空 —— 轮次末尾无人回读远端')
    gids = [g for _f, g, _m, _w in ROUND_END_STEPS]
    for g in ROUND_END_REQUIRED_GIDS:
        if g not in gids:
            bad.append(f'轮次末尾步骤**缺 {g}** —— 该方向又没人守了')
    return bad


def cmd_assert_round_end():
    """🔑 G423：**轮次末尾入口必须真含这三项**（防流程退化成"没人跑"）。

    🔴 129 轮诚实结论①的另一个面：光有命令也**没人会记得跑**。
       若 `ROUND_END_STEPS` 被人删掉一项（尤其 G391），
       表面"入口还在"，实际又退回"靠人工自觉"。
    🔑 三条判据：
       ① `ROUND_END_STEPS` 非空；
       ② 每项 flag **真被 argparse 登记**（AST 取 add_argument 首参，
          🔴 不数次数 —— 93 轮"数几个 ≠ 验是什么"同样适用）；
       ③ `ROUND_END_REQUIRED_GIDS` 里的编号**全都在**步骤里，
          且每个编号在 `run_all_gates.py` 里**真有门禁**。

    🔑 第一百三十二轮：判据①③抽到 `_round_end_steps_bad()`（唯一实现），
       与 G424 **共用同一份** —— 防"改一处漏一处"导致两条门禁结论矛盾。
    """
    print('=' * 70)
    print('🔑 G423 轮次末尾必跑入口须真含三项（防退化成没人跑）')
    print('=' * 70)
    ok = True
    # ①③ 共用实现
    #    🔑 第一百三十三轮：用 `globals().get` 取，缺失时**拒绝给结论**。
    #       🔴 直接写死调用时，helper 改名会抛 NameError ——
    #          **崩溃的 rc 也是 1**，与"正确阻断"在退出码上无法区分
    #          （104 轮 `req()` 同病，本轮为第 6 次同类）。
    _bad_fn = globals().get(ROUND_END_STEPS_BAD_FN)
    if _bad_fn is None:
        print(f'🔴 {ROUND_END_STEPS_BAD_FN}() **不存在**'
              f' —— 拒绝给结论（不是崩溃）')
        print('=' * 70)
        return 1
    for b in _bad_fn():
        print(f'🔴 {b}')
        ok = False
    # ② 真被 argparse 登记
    import ast as _ast
    tree = _ast.parse(io.open(os.path.abspath(__file__),
                              encoding='utf-8').read())
    flags = set()
    for n in _ast.walk(tree):
        if isinstance(n, _ast.Call) and isinstance(n.func, _ast.Attribute) \
                and n.func.attr == 'add_argument' and n.args \
                and isinstance(n.args[0], _ast.Constant):
            flags.add(n.args[0].value)
    for flag, gid, _m, _w in ROUND_END_STEPS:
        if flag not in flags:
            print(f'🔴 {gid} 的 {flag} **未在 argparse 中登记** —— 入口会报错')
            ok = False
    # ③（前半已由共用实现覆盖）在门禁表里真存在
    gids = [g for _f, g, _m, _w in ROUND_END_STEPS]
    rg = os.path.join(HERE, 'run_all_gates.py')
    try:
        rtxt = io.open(rg, encoding='utf-8').read()
    except Exception as e:
        print(f'🔴 无法读取门禁表 {rg}: {e} —— 拒绝给结论')
        print('=' * 70)
        return 1
    for g in ROUND_END_STEPS:
        if f'("{g[1]}"' not in rtxt:
            print(f'🔴 {g[1]} 在 `run_all_gates.py` 中**无门禁登记**'
                  f' —— 轮次末尾跑的项必须本身也是门禁')
            ok = False
    if not ok:
        print('=' * 70)
        return 1
    print(f'✅ 轮次末尾 {len(ROUND_END_STEPS)} 项齐全：'
          + ' · '.join(f'{g}({f})' for f, g, _m, _w in ROUND_END_STEPS))
    print('=' * 70)
    return 0


def cmd_assert_round_end_wired():
    """🔑 G424：**轮次末尾回读必须接在推送主流程末尾**（不跑就推不完）。

    🔴 第一百三十轮诚实结论①：
       "`--round-end` 仍然要靠人**记得跑** —— G423 只保证入口没被拆，
        保证不了有人执行它。"
    🔑 判据：**"入口存在" ≠ "每轮真跑"**。
       把 `_run_round_end_steps()` 接进 `main()` 的推送路径末尾，
       推送就不可能"跳过这一步还报成功"。

    🔑 四条判据：
       ① `ROUND_END_STEPS` 非空且三个必需编号齐全
          （🔑 第一百三十二轮：改为调用 `_round_end_steps_bad()`，
           与 G423 **共用同一实现**，不再是"同一口径的第二份"）；
       ② `ROUND_END_FN` **真定义**（改名即暴露，防 G424 自身静默失效）；
       ③ 在 `main()` 内**真被调用**，且调用行 **晚于**严格 `cmd_verify_push`
          的行 —— 🔑 **"末尾"必须是时序上的末尾**，不是注释里写着末尾；
       ④ `ROUND_END_FN` 已登记进 `DEPENDENT_NAMES`（与 112 轮同构）。

    🔴 与 G423 的分工（互补，不可互相替代）：
       - G423 守"**入口里有哪些项**"（防删项）；
       - G424 守"**推送流程真的调用了它**"（防没人跑）。
       🔑 只有 G423：入口齐全但没人跑 → 129 轮那个洞原样还在。
       🔑 只有 G424：调用是真调用了，但 ROUND_END_STEPS 被删成一项也看不出。
    """
    print('=' * 70)
    print('🔑 G424 轮次末尾回读必须接在推送主流程末尾（不跑就推不完）')
    print('=' * 70)
    ok = True
    # ① 共用实现（与 G423 同一份，防两条门禁结论矛盾）
    #    🔑 同 G423：缺失即拒绝给结论，不崩溃。
    _bad_fn = globals().get(ROUND_END_STEPS_BAD_FN)
    if _bad_fn is None:
        print(f'🔴 {ROUND_END_STEPS_BAD_FN}() **不存在**'
              f' —— 拒绝给结论（不是崩溃）')
        print('=' * 70)
        return 1
    for b in _bad_fn():
        print(f'🔴 {b} —— 接了也白接（跑了也漏一个方向）')
        ok = False
    gids = [g for _f, g, _m, _w in ROUND_END_STEPS]
    # ④ 🔑 两条**都要**：只验一条会退化成恒真。
    #    🔴 实测（本轮）：`ROUND_END_FN` 的值是 '_run_round_end_steps'，
    #       而该名字**也**作为 fn 登记在表内 → 单看"值在不在表里"
    #       **永远为真**，删掉常量登记项也照样绿（判据恒真）。
    #    🔑 所以：a) 常量**名**在表里；b) 常量**值**（函数）在表里。
    if 'ROUND_END_FN' not in DEPENDENT_NAMES:
        print('🔴 ROUND_END_FN **未登记进 DEPENDENT_NAMES**'
              ' —— 登记项被删无人知晓（与 112 轮同构）')
        ok = False
    if ROUND_END_FN not in DEPENDENT_NAMES:
        print(f'🔴 {ROUND_END_FN}() **未登记为被依赖函数**'
              f' —— 改名会让本门禁静默失效')
        ok = False
    # ②③ AST 扫描 main()
    import ast as _ast
    try:
        src = io.open(os.path.abspath(__file__), encoding='utf-8').read()
        tree = _ast.parse(src)
    except Exception as e:
        print(f'🔴 无法解析 {os.path.basename(__file__)}: {e} —— 拒绝给结论')
        print('=' * 70)
        return 1
    fns = {n.name: n for n in tree.body if isinstance(n, _ast.FunctionDef)}
    if ROUND_END_FN not in fns:
        print(f'🔴 {ROUND_END_FN}() **未定义** —— G424 会永远扫不到它')
        ok = False
    mainfn = fns.get('main')
    if mainfn is None:
        print('🔴 找不到 main() —— 拒绝给结论')
        print('=' * 70)
        return 1
    end_lineno = None
    strict_lineno = None
    for n in _ast.walk(mainfn):
        if not isinstance(n, _ast.Call):
            continue
        nm = getattr(n.func, 'id', None)
        if nm == ROUND_END_FN and end_lineno is None:
            end_lineno = n.lineno
        # 🔑 严格模式的 G391：`cmd_verify_push(report=False)`
        if nm == 'cmd_verify_push':
            for kw in n.keywords:
                if kw.arg == 'report' and isinstance(kw.value, _ast.Constant)                         and kw.value.value is False:
                    strict_lineno = n.lineno
    if end_lineno is None:
        print(f'🔴 main() 中**没有调用** {ROUND_END_FN}()'
              f' —— 轮次末尾回读仍然"靠人记得跑"')
        ok = False
    if strict_lineno is None:
        print('🔴 main() 中**没有严格模式**的 cmd_verify_push(report=False)'
              ' —— 推送后回读的严格层不在流程里')
        ok = False
    if end_lineno is not None and strict_lineno is not None:
        if end_lineno <= strict_lineno:
            print(f'🔴 {ROUND_END_FN}() 在第 {end_lineno} 行，'
                  f'而严格 G391 在第 {strict_lineno} 行'
                  f' —— 回读**不在末尾**（轮次末尾必须是时序上的最后一步）')
            ok = False
        else:
            print(f'🔑 调用顺序正确：严格 G391 第 {strict_lineno} 行'
                  f' → 轮次末尾回读第 {end_lineno} 行')
    if not ok:
        print('=' * 70)
        return 1
    print(f'✅ 轮次末尾 {len(ROUND_END_STEPS)} 项已接进推送主流程末尾：'
          + ' · '.join(gids))
    print('=' * 70)
    return 0


def _gate_calls_helper(node, fn):
    """🔑 判断一个门禁函数体内是否**真调用**了 helper（不只是引用）。

    🔴 第一百三十三轮诚实结论①：判据④为兼容
       `globals().get(ROUND_END_STEPS_BAD_FN)` 写法而放宽成"**引用**"
       —— 于是"拿到 helper 却**从不调用**"也算共用，判据形同虚设。
    🔑 判据：**该名字必须出现在 `Call` 的 `func` 位置**。

    🔑 兼容两种共用形态：
       a) 直接调用：`_round_end_steps_bad()`；
       b) 取用后调用：`_b = globals().get(ROUND_END_STEPS_BAD_FN)` → `_b()`。
          🔑 b) 要求 `get` 的实参**确为该常量名或其值**——
             只认"取的是 helper 的那个变量"，不是任何 `globals().get()`。
    """
    bound = set()
    for n in ast.walk(node):
        if isinstance(n, ast.Assign) and isinstance(n.value, ast.Call):
            f = n.value.func
            if isinstance(f, ast.Attribute) and f.attr in ('get', 'getattr'):
                for a in n.value.args:
                    hit = ((isinstance(a, ast.Name)
                            and a.id == 'ROUND_END_STEPS_BAD_FN')
                           or (isinstance(a, ast.Constant)
                               and a.value == fn))
                    if hit:
                        for t in n.targets:
                            if isinstance(t, ast.Name):
                                bound.add(t.id)
    for n in ast.walk(node):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name):
            if n.func.id == fn or n.func.id in bound:
                return True
    return False


def cmd_assert_round_end_single():
    """🔑 G425：**"步骤齐全"判据必须只有一处实现，且被 G423/G424 共用**。

    🔴 第一百三十一轮诚实结论②：
       G423 判据①与 G424 判据①是**同一口径的两处实现** ——
       改一处、漏一处时两条门禁会给出**互相矛盾的结论**，
       而没有任何东西发现它们已经不一致。
    🔑 判据：**"两条门禁都在" ≠ "它们看的是同一个事实"**。

    🔑 五条判据：
       ① `ROUND_END_STEPS_BAD_FN` **常量名**已登记（防登记项被删）；
       ② 其**值**已登记为 fn（🔴 单看一条会退化成恒真 —— 131 轮实测：
          常量值 '_run_round_end_steps' 本身也在表里，"值在不在表里"永真）；
       ③ 该函数**真定义**；
       ④ G423 / G424 **两个函数体内都真用到**它（只登记不算共用）。
          🔑 第一百三十三轮：兼容两种形态 —— 直接调用 `fn()`，
             或经常量名 `globals().get(ROUND_END_STEPS_BAD_FN)` 取用
             （后者是「缺失即拒绝给结论」所必需的写法）；
       ⑤ 🔑 **引用** `ROUND_END_REQUIRED_GIDS` 的函数**只有 helper 一个**
          —— 防"共用之外又内联一份"（**存在但无关**的老病，83 轮）。
          🔴 第一百三十三轮改：**不看写法**。旧判据只认
             `for x in ROUND_END_REQUIRED_GIDS` 这一种 for 形式，
             改用 `set(A) - set(B)` 或推导式就绕过（132 轮诚实结论①）；
             新判据按 **Name 引用**统计，任何写法都覆盖；
       ⑥ **行为反证**：真跑一次被改坏的 `ROUND_END_STEPS`，
          断言判据**会响**（防该函数被改成恒返回 `[]` 的桩，
          与 100 轮"自测必须调用真实实现"同源）；
       ⑦ helper 缺失时必须是**拒绝**而非**崩溃**（rc 相同，靠输出区分）；
       ⑧ 🔑 第一百三十四轮：**判据④ 本身也须被反证** ——
          真跑 `_gate_calls_helper` 对四种合成 AST 判断，
          防它被改成恒真的桩（132 轮破坏⑥同源）。
    """
    print('=' * 70)
    print('🔑 G425 步骤齐全判据须唯一实现且被 G423/G424 共用')
    print('=' * 70)
    ok = True
    fn = ROUND_END_STEPS_BAD_FN
    # ①② 两条都要（131 轮实测：单看"值在表里"恒真）
    if 'ROUND_END_STEPS_BAD_FN' not in DEPENDENT_NAMES:
        print('🔴 ROUND_END_STEPS_BAD_FN **未登记进 DEPENDENT_NAMES**'
              ' —— 登记项被删无人知晓')
        ok = False
    if fn not in DEPENDENT_NAMES:
        print(f'🔴 {fn}() **未登记为被依赖函数** —— 改名会让本门禁静默失效')
        ok = False
    import ast as _ast
    try:
        src = io.open(os.path.abspath(__file__), encoding='utf-8').read()
        tree = _ast.parse(src)
    except Exception as e:
        print(f'🔴 无法解析 {os.path.basename(__file__)}: {e} —— 拒绝给结论')
        print('=' * 70)
        return 1
    fns = {n.name: n for n in tree.body if isinstance(n, _ast.FunctionDef)}
    # ③
    if fn not in fns:
        print(f'🔴 {fn}() **未定义** —— G423/G424 无从共用')
        ok = False
    # ④ 两个门禁函数体内真调用
    for gate_fn, gid in (('cmd_assert_round_end', 'G423'),
                         ('cmd_assert_round_end_wired', 'G424')):
        g = fns.get(gate_fn)
        if g is None:
            print(f'🔴 找不到 {gate_fn}() —— 拒绝给结论')
            ok = False
            continue
        # 🔑 第一百三十四轮：**必须真调用**，只引用不算。
        #    🔴 实测（本轮）：只写 `_x = _bad_fn` 而不调用，
        #       旧判据照样报"共用 ✅" —— 判据形同虚设。
        used = _gate_calls_helper(g, fn)
        if not used:
            print(f'🔴 {gid}（{gate_fn}）**没有调用** {fn}()'
                  f' —— 只引用不调用，等于没共用（判据形同虚设）')
            ok = False
        else:
            print(f'🔑 {gid} 共用 {fn}() ✅')
    # ⑤ 🔑 第一百三十三轮：**按 Name 引用统计，不认写法**。
    #    🔴 旧判据只匹配 `for x in ROUND_END_REQUIRED_GIDS`，
    #       换成 `set(A) - set(B)`、`[... for g in A ...]` 就绕过。
    owners = []
    for name, node in fns.items():
        if name == 'cmd_assert_round_end_single':
            continue   # 本门禁自身只在字符串里提到它，不算引用
        for n in _ast.walk(node):
            if isinstance(n, _ast.Name) \
                    and n.id == 'ROUND_END_REQUIRED_GIDS' \
                    and isinstance(n.ctx, _ast.Load):
                owners.append(name)
                break
    owners = sorted(set(owners))
    if len(owners) != 1 or owners[0] != fn:
        print(f'🔴 引用 ROUND_END_REQUIRED_GIDS 的函数有 {len(owners)} 处'
              f' {owners}（应只有 {fn} 一处）—— 判据又被抄了一份')
        ok = False
    else:
        print(f'🔑 判据唯一实现：{fn}()（其余 {len(fns)} 个函数均未引用）')
    # ⑥ 行为反证：真跑一次改坏的输入
    try:
        import importlib.util as _ilu
        spec = _ilu.spec_from_file_location('_pa_probe',
                                            os.path.abspath(__file__))
        mod = _ilu.module_from_spec(spec)
        spec.loader.exec_module(mod)
    except Exception as e:
        print(f'🔴 无法导入本模块做行为反证: {e} —— 拒绝给结论')
        print('=' * 70)
        return 1
    for label, patched in (
            ('步骤表清空', ()),
            ('缺 G422/G391', (('--assert-round-claims', 'G421',
                               'strict', 'w'),)),
    ):
        mod.ROUND_END_STEPS = patched
        try:
            got = mod._round_end_steps_bad()
        except Exception as e:
            print(f'🔴 {label} 时 {fn}() 抛异常: {e} —— 判据不可用')
            ok = False
            continue
        if not got:
            print(f'🔴 {label} 时 {fn}() **返回空**（应报错）'
                  f' —— 判据是恒真的桩')
            ok = False
        else:
            print(f'🔑 反证通过（{label}）：报出 {len(got)} 条')
    # ⑦ 🔑 行为反证：helper **改名/不存在**时必须是"拒绝"而不是"崩溃"。
    #    🔴 第一百三十二轮诚实结论③：helper 改名会让 G423/G424 抛
    #       NameError —— **崩溃的 rc 也是 1**，与"正确阻断"在退出码上
    #       **无法区分**（104 轮 `req()` 同病，本类问题第 6 次）。
    #    🔑 判据：rc==1 且输出含"拒绝给结论"且**不含** Traceback。
    import io as _io2
    import contextlib as _cb
    for gid, cmd_name in (('G423', 'cmd_assert_round_end'),
                          ('G424', 'cmd_assert_round_end_wired')):
        real = getattr(mod, fn, None)
        try:
            if hasattr(mod, fn):
                delattr(mod, fn)      # 模拟改名：helper 从此不存在
            buf = _io2.StringIO()
            try:
                with _cb.redirect_stdout(buf):
                    rc = getattr(mod, cmd_name)()
            except Exception as e:
                print(f'\U0001f534 {gid} 在 {fn}() 缺失时**抛异常**: '
                      f'{type(e).__name__}: {e}'
                      f' —— 崩溃与拒绝在 rc 上无法区分')
                ok = False
                continue
            out = buf.getvalue()
            if rc != 1:
                print(f'\U0001f534 {gid} 在 {fn}() 缺失时 rc={rc}（应为 1）')
                ok = False
            elif 'Traceback' in out:
                print(f'\U0001f534 {gid} 输出含 Traceback —— 是**崩溃**不是拒绝')
                ok = False
            elif '拒绝给结论' not in out:
                print(f'\U0001f534 {gid} 未输出"拒绝给结论" —— 无法与崩溃区分')
                ok = False
            else:
                print(f'\U0001f511 反证通过（{gid}）：helper 缺失时'
                      f' **拒绝给结论**而非崩溃')
        finally:
            if real is not None:
                setattr(mod, fn, real)
    # ⑧ 🔑 行为反证：**真跑** `_gate_calls_helper` 对合成 AST 的判断。
    #    🔴 只做静态判据不够：若有人把它改成恒返回 True 的**桩**，
    #       判据④ 会永远"通过"而没人发现 —— 与 100 轮"自测必须调用
    #       真实实现"、132 轮破坏⑥（改成桩后静态判据全部照常通过）同源。
    #    🔑 所以这里**调用真实实现**，不复刻一份逻辑。
    _h = getattr(mod, '_gate_calls_helper', None)
    if _h is None:
        print('🔴 _gate_calls_helper() **不存在**'
              ' —— 判据④ 无从判定（拒绝给结论）')
        ok = False
    else:
        import ast as _ast2
        for label, src, want in (
                ('只引用不调用',
                 'def g():\n    _r = _round_end_steps_bad\n    return _r\n',
                 False),
                ('直接调用',
                 'def g():\n    return _round_end_steps_bad()\n', True),
                ('取用后调用',
                 'def g():\n    _b = globals().get(ROUND_END_STEPS_BAD_FN)'
                 '\n    return _b()\n', True),
                ('取的是别的常量',
                 'def g():\n    _b = globals().get(OTHER_CONST)'
                 '\n    return _b()\n', False),
        ):
            node = _ast2.parse(src).body[0]
            got = _h(node, fn)
            if got != want:
                print(f'🔴 反证失败（{label}）：判据返回 {got}'
                      f'（应为 {want}）—— 判据是恒真的桩或已失效')
                ok = False
            else:
                print(f'🔑 反证通过（{label}）：{got} ✅')
    # ⑨ 🔑 判据④ 本身必须真用 `_gate_calls_helper`。
    #    🔴 实测（本轮）：把它改成 `used = True` 的恒真桩后，
    #       ⑧ **依然全绿** —— ⑧ 验的是"helper 判得准不准"，
    #       验不了"判据④ 到底用没用它"。
    #    🔑 复用同一个 helper：它接受任意 (函数节点, 名字) 对。
    #    🔴 实测（本轮，两次才做对）：第一版用
    #       `_gate_calls_helper(_self, '_gate_calls_helper')`，
    #       结果判据④ 改成 `used = True` 后**仍然放行** ——
    #       因为 ⑧ 里 `_h = getattr(mod, '_gate_calls_helper')` 也被
    #       认作"调用"，⑨ 于是恒定为真。**判据不能验自己。**
    #    🔑 所以 ⑨ 要求：判据④ 那个**特定的调用**
    #       `_gate_calls_helper(g, fn)` 真存在于本函数体内。
    _self = fns.get('cmd_assert_round_end_single')
    _used_direct = False
    if _self is not None:
        for _n in _ast.walk(_self):
            if (isinstance(_n, _ast.Call)
                    and isinstance(_n.func, _ast.Name)
                    and _n.func.id == '_gate_calls_helper'
                    and len(_n.args) == 2
                    and all(isinstance(_a, _ast.Name) for _a in _n.args)
                    and [ _a.id for _a in _n.args ] == ['g', 'fn']):
                _used_direct = True
                break
    if _self is None or not _used_direct:
        print('🔴 判据④ 处**没有** `_gate_calls_helper(g, fn)` 这个调用'
              ' —— 它可能被写成了恒真的桩（拒绝给结论）')
        ok = False
    else:
        print('🔑 判据④ 确由 _gate_calls_helper(g, fn) 判定 ✅')
    if not ok:
        print('=' * 70)
        return 1
    print('✅ 步骤齐全判据唯一实现，且 G423/G424 共用同一份')
    print('=' * 70)
    return 0


def _index_worktree_diff():
    """🔑 G427 判据②：返回**工作区已改但未入索引**的文件；`None` = 无法确定。

    🔑 与 `_dirty_tracked()` 语义不同：
       `_dirty_tracked()` 比的是 **HEAD**（有没有未提交的修改）；
       本函数比的是 **索引**（工作区内容与索引是否一致）。
    🔴 第一百三十六轮事故正是这个形态：`git add -A` 之后又有脚本写了文件 ——
       HEAD 落后（dirty）**且** 索引落后（worktree ≠ index），
       而推送读的是**工作区** → 推上去的东西与仓库里记的不是一个版本。
    """
    import subprocess
    try:
        proc = subprocess.run(
            ['git', '-c', 'core.quotepath=false', 'diff', '--name-only', '-z'],
            capture_output=True, text=True, timeout=120, cwd=ROOT)
        if proc.returncode != 0:
            return None
    except Exception:
        return None
    return [x for x in proc.stdout.split('\0') if x.strip()]


def _no_dirty_wired_bad():
    """🔑 G427 判据③④：本检查必须**真的接在推送主流程**、早于首次网络写入、
       且**结果真的会导致拒绝推送**。

    🔑 与 G424 同源：**"入口在" ≠ "有人跑"**。
    🔴 判定"早于"的锚点取 `req('POST', ...git/trees...)` —— 那是第一次真正
       把内容写进远端的地方；在它之后调用本检查就毫无意义。
    🔴 判据④（第一百三十七轮补）：`if cmd_assert_no_dirty() != 0: return 1`
       若被改成 `if False:` 或删掉 `return 1`，调用仍在、时序仍对，
       🔑 **但结果被丢掉了** —— 检查变成摆设，而判据③照绿。
       （与第一百一十八轮"改进代码把 G410 弄失效而它不会自述"同源）
    """
    import ast
    text = io.open(os.path.join(ROOT, 'scripts', 'push_api.py'),
                   encoding='utf-8').read()
    try:
        tree = ast.parse(text)
    except Exception as e:
        return [f'解析失败：{e}']
    main_fn = None
    for n in ast.walk(tree):
        if isinstance(n, ast.FunctionDef) and n.name == 'main':
            main_fn = n
            break
    if main_fn is None:
        return ['找不到 main()']
    lines = text.splitlines()
    t_line = None
    for n in ast.walk(main_fn):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) \
                and n.func.id == 'req' and n.args:
            a0 = n.args[0]
            if isinstance(a0, ast.Constant) and a0.value == 'POST':
                seg = lines[n.lineno - 1] if n.lineno - 1 < len(lines) else ''
                if 'git/trees' in seg and t_line is None:
                    t_line = n.lineno
    # 🔑 判据③：**守卫结构**本身（`if <call> != 0: return 1`）。
    #    🔴 不能只找"有没有调用" —— dispatch 里也有一处
    #       `return cmd_assert_no_dirty()`，那会让"删掉推送前守卫"**照样绿**
    #       （第一百一十一轮"存在但无关"同病，破坏①实测蒙混成功）。
    guard_line = None
    for n in ast.walk(main_fn):
        if not isinstance(n, ast.If):
            continue
        hit_call = any(
            isinstance(x, ast.Call) and isinstance(x.func, ast.Name)
            and x.func.id == 'cmd_assert_no_dirty'
            for x in ast.walk(n.test))
        if not hit_call:
            continue
        ret1 = any(isinstance(x, ast.Return)
                   and isinstance(x.value, ast.Constant)
                   and x.value.value == 1
                   for x in ast.walk(n))
        if ret1:
            guard_line = n.lineno
            break
    bad = []
    if guard_line is None:
        bad.append('main() 里**没有** `if cmd_assert_no_dirty() != 0: return 1`'
                   ' 的守卫结构 —— 🔴 调用还在（dispatch 里有一处），'
                   '但**结果被丢掉了**，检查变成摆设（111 轮"存在但无关"）')
    if t_line is None:
        bad.append('main() 里找不到 req(\'POST\', ...git/trees...)'
                   ' —— 🔴 无法判定时序，拒绝给结论')
    if guard_line and t_line and guard_line > t_line:
        bad.append(f'守卫在第 {guard_line} 行，**晚于**首次远端写入'
                   f'（第 {t_line} 行） —— 🔴 推完了才查，等于没查')
    return bad


def cmd_assert_no_dirty():
    """🔑 G427：**推送前必须无未提交修改**（把 G391 第⑤层提前到推送前）。

    🔴 第一百三十六轮真实事故：只 `git add -A` 而**未本地 commit**，
       随后 `--audit-history` 又重写了台账与镜像 —— 索引里是**旧内容**，
       而推送读的是**工作区**（新内容）→ 远端与本地索引对不上：
       `内容不一致 2 个 · 本地有 10 个未提交的修改`，G391 第⑤层**推送后**才报出来。
    🔑 判据：**推送的必须是"仓库里的那个版本"**，而"仓库里的版本"
       由 **HEAD** 定义 —— 未提交的东西不属于它。

    | 判据 | 内容 |
    |---|---|
    | ① | 无**已跟踪未提交**的修改（`??` 归 G390 管，两者方向不同） |
    | ② | **索引 == 工作区**（`git diff --name-only` 为空）—— 136 轮事故的**具体形态** |
    | ③ | 本检查**真的接在推送主流程**，且早于首次 `git/trees` 远端写入 |
    """
    print('🔑 **推送前未提交修改检查**（G427）')
    print('=' * 70)
    bad = []

    d = _dirty_tracked()
    if d is None:
        bad.append('**无法确定**是否有未提交修改（git 不可用）')
    elif d:
        bad.append(f'{len(d)} 个文件已跟踪但**未提交**'
                   f' —— 推上去的将是工作区内容，而不是仓库里的版本')
        for f in d[:10]:
            print(f'   - {f}')
        if len(d) > 10:
            print(f'   … 另 {len(d) - 10} 个')

    dif = _index_worktree_diff()
    if dif is None:
        bad.append('**无法确定**索引与工作区是否一致（git 不可用）')
    elif dif:
        bad.append(f'{len(dif)} 个文件**工作区已改但未入索引**'
                   f' —— 🔴 136 轮事故形态：推的是工作区，比的却是索引')
        for f in dif[:10]:
            print(f'   - {f}')
        if len(dif) > 10:
            print(f'   … 另 {len(dif) - 10} 个')

    bad.extend(_no_dirty_wired_bad())

    print('=' * 70)
    if bad:
        for b in bad:
            print('🔴 ' + b)
        print('🔑 处理：git add -A && git commit -m "说明" 之后再推送')
        return 1
    print('✅ 无未提交修改 · 索引与工作区一致 · 本检查已接在推送前'
          ' —— 推的就是仓库里的版本')
    return 0


# ==================== 第一百三十八轮：G428 哑门禁变异扫描 ====================
# 🔴 第一百三十六轮指引③（第一百三十七轮诚实结论④明说**没做**）：
#    "用脚本自动扫**哪些判据可被改成桩而门禁仍绿**"。
#    🔑 此前每一轮都是**手工**做 4~6 方向破坏实测 —— 手工做的极限是：
#       **只测本轮新写的那几条**，而 30 个已有 cmd_* 门禁**从未被系统性地问过**
#       "把它整个换成 `return 0`，全仓库有谁会响？"
#    🔑 判据：**"被跑" ≠ "被守望"**。
#       GATES 表登记了 → 回归每轮都跑它；但把它改成桩后回归**依然全绿**
#       —— 没有任何东西会指出"这条门禁已经哑了"。
#       这正是 121 轮"整轮空转无人发现"在**门禁粒度**上的同构问题。
MUTATION_SCAN_FILE = os.path.join(ROOT, 'ledger', 'mutation_scan.json')
MUTE_ALLOWLIST = os.path.join(ROOT, 'ledger', 'mute_gate_allowlist.txt')
MUTATION_TARGET_MIN = 20
# 🔑 扫描器自身必须排除 —— 否则它会把自己当成最后一个目标（93 轮"扫到自己"）
MUTATION_SELF_EXCLUDE = ('cmd_mutation_scan', 'cmd_assert_mutation',
                         '_mutation_probe')
# 🔴 第一百三十八轮**真实事故**：第一版把变异体**写回 push_api.py 本身**，
#    结果磁盘上的文件出现**两段文本字节错位**（第 4479 行 SyntaxError）：
#    `print('🔴 **无法确定** git 索引 mode —— 拒绝` + `确定**是否有漏传…`
#    🔴 即：被测文件在变异过程中被**写坏**，而"恢复"只是把坏内容再写一遍。
#    🔑 判据：**变异测试绝不能写被测文件本身** —— 写坏了连"原文"都失去参照。
#    ✅ 改为把变异体写成**临时副本** scripts/_mutant_138.py，原文件全程不动。
MUTATION_TMP = os.path.join(HERE, '_mutant_138.py')

# 🔑 第一百三十九轮：G429 —— **推送必须互斥**。
#    🔴 真实事故（本轮）：工具报 TimeoutError，我据此判断"推送没启动"，
#       于是又启动两次 —— 实际**三个 push_api.py -m 进程同时存活**
#       （ps 可见 pid 1088 / 1161 / 1207）。
#    🔴 危害：三者都读取**同一个** parent ref 并各自建 commit，
#       最后更新 ref 的那个胜出 —— 另两个的工作**静默丢失**，
#       而胜出者的输出看起来完全正常（"推送成功"）。
#    🔑 判据：**命令超时 ≠ 命令没跑**。判活必须查进程，不能凭退出码/报错推断。
# 🔑 第一百四十一轮：**网络抖动必须重试**（真实事故驱动）。
#    🔴 137/138/139 三轮内容**始终没抵达远端**，报的都是"域名解析失败"；
#       实测 321 个文件里 26 个因 NET 失败 → 整次推送中止 → **整轮白干**。
#    🔑 只重试 `__err` 以 'NET:' 开头的（104 轮定义的网络层形态）；
#       HTTP 4xx/5xx 不重试 —— 那是内容/权限问题，重试无意义且放大故障。
BLOB_NET_RETRY = 5
BLOB_RETRY_SLEEP = 2.0

PUSH_LOCK_ARGS = ('push_api.py', '-m')
PUSH_LOCK_FILE = os.path.join(ROOT, 'audit', '.push_lock')

# 🔑 第一百四十轮：**推送互斥守卫的名字锚点**（G430 判据②）。
#    🔴 139 轮破坏实测：把 `_other_pushers` 与判据里的期望名**一起改**成
#       同一个新名字（一致改名）→ G429 三条判据**全部通过 rc=0**。
#       因为判据的"期望名"与被判对象**是同一个字符串** ——
#       🔑 判据：期望名与被判对象同名时，**"改名"与"换实现"无法区分**。
#    🔑 处置：把期望名写进 `ledger/trust_root.json::PUSH_EXCLUSIVE_NAMES`
#       （**独立于代码**的外部锚点），代码里的名字必须与锚点一致。
#    🔴 已知边界：同时改代码与锚点仍会绕过（109 轮同源），靠 git 审计兜底。
PUSH_EXCLUSIVE_NAMES = ('PUSH_LOCK_ARGS', 'PUSH_LOCK_FILE', '_other_pushers',
                        'cmd_assert_push_exclusive')


def _atomic_write_text(path, text):
    """🔑 原子写入（第一百三十五轮：破坏/变异脚本必须原子写入）。

    🔴 非原子写入在进程被杀时留下**半截文件** —— 那既不是原文也不是变异体，
       恢复无从下手（本仓库已被沙盒中断打断多次）。
    """
    import tempfile
    d = os.path.dirname(path) or '.'
    fd, tmp = tempfile.mkstemp(dir=d, prefix='.aw138_', suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as f:
            f.write(text)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    # 🔑 写后**读回校验**（138 轮真实事故：写出的文件字节错位却无人发现）
    try:
        with open(path, encoding='utf-8') as f:
            got = f.read()
    except Exception as e:
        raise RuntimeError('写入后无法读回：%s' % e)
    if hashlib.sha1(got.encode('utf-8')).hexdigest() != \
            hashlib.sha1(text.encode('utf-8')).hexdigest():
        raise RuntimeError('写入后读回内容与预期不一致 —— 拒绝继续')


def _top_fn_ranges(text):
    """顶层 def 的 (起始行, 结束行)（1-based，含）。"""
    out = {}
    try:
        tree = _ast.parse(text)
    except SyntaxError:
        return out
    for n in tree.body:
        if isinstance(n, _ast.FunctionDef):
            out[n.name] = (n.lineno, n.end_lineno)
    return out


def _cmd_flag_map(text):
    """main() 中 `if a.xxx: return cmd_yyy()` → {cmd_yyy: 'xxx'}。"""
    out = {}
    try:
        tree = _ast.parse(text)
    except SyntaxError:
        return out
    for n in tree.body:
        if not isinstance(n, _ast.FunctionDef) or n.name != 'main':
            continue
        for x in _ast.walk(n):
            if not isinstance(x, _ast.If):
                continue
            t = x.test
            attr = None
            if (isinstance(t, _ast.Attribute)
                    and isinstance(t.value, _ast.Name) and t.value.id == 'a'):
                attr = t.attr
            elif (isinstance(t, _ast.Compare)
                  and isinstance(t.left, _ast.Attribute)
                  and isinstance(t.left.value, _ast.Name)
                  and t.left.value.id == 'a'
                  and len(t.ops) == 1
                  and isinstance(t.ops[0], _ast.IsNot)
                  and isinstance(t.comparators[0], _ast.Constant)
                  and t.comparators[0].value is None):
                # 🔑 `if a.xxx is not None:` 形式（如 --show-legacy-files）
                #    🔴 只认 `if a.xxx:` 会让这类门禁**拿不到 flag** →
                #       桩化后无法实跑，扫描只能给"未知"（138 轮实测）。
                attr = t.left.attr
            if not attr:
                continue
            for b in _ast.walk(x):
                if (isinstance(b, _ast.Return) and isinstance(b.value, _ast.Call)
                        and isinstance(b.value.func, _ast.Name)
                        and b.value.func.id.startswith('cmd_')):
                    out.setdefault(b.value.func.id, attr)
    return out


def _stub_replace(lines, sig_line, end_line):
    """把 [sig_line, end_line] 整个函数体替换为单独一句 `    return 0`。

    🔑 只改这一个函数、其余字节不动 —— 比 `ast.unparse` 安全得多
       （后者会丢掉全文件注释，一旦恢复失败就是不可逆损毁）。
    """
    head = lines[:sig_line - 1]
    sig = lines[sig_line - 1]
    tail = lines[end_line:]
    body = head + [sig, '    return 0'] + tail
    new = '\n'.join(body)
    if not new.endswith('\n'):
        new += '\n'
    return new


def _callers_of(text, callee):
    """顶层函数中**真的调用**了 callee 的（AST Call + func 是 Name）。"""
    try:
        tree = _ast.parse(text)
    except SyntaxError:
        return []
    out = []
    for n in tree.body:
        if not isinstance(n, _ast.FunctionDef) or n.name == callee:
            continue
        for sub in _ast.walk(n):
            if (isinstance(sub, _ast.Call) and isinstance(sub.func, _ast.Name)
                    and sub.func.id == callee):
                out.append(n.name)
                break
    return out


def _flag_for_fn(text, fn, flags, depth=0):
    """把任意函数映射到**可执行命令**（自身没有 flag 就向上找调用者）。"""
    if fn in flags:
        return flags[fn]
    if depth >= 3:
        return None
    cs = _callers_of(text, fn)
    for c in cs:
        if c in flags:
            return flags[c]
    for c in cs:
        r = _flag_for_fn(text, c, flags, depth + 1)
        if r:
            return r
    return None


def _watchers_of(text, target, exclude, flags):
    """🔑 守望者 = 桩化 target 之后**仍然会响**的其它命令。

    🔴 第一百三十八轮**判据对象选错层级**（与 110 轮 grep、118 轮 mode 同源）：
       第一版只认 **AST Name 引用**（真的调用它）→ 结果 30 个门禁**全是 mute**。
       🔑 真相：本仓库的守望者**不是"调用它"，而是"解析源码找它"** ——
          如 `_no_dirty_wired_bad()` 是 `ast.parse` main() 后比 `n.func.id`，
          名字出现在**字符串比较**里，AST Name 引用统计**永远数不到**。
       ✅ 改为：先用**文本**找候选函数（宽），再映射到可执行命令并**实跑**（严）
          —— 宽进严出，误报由实跑过滤（rc=0 记 static_only，不算守望者）。
    """
    ranges = _top_fn_ranges(text)
    if not ranges:
        return None
    pat = re.compile(r'\b' + re.escape(target) + r'\b')
    lines = text.split('\n')
    cand = []
    for name, (s, e) in sorted(ranges.items()):
        if name == target or name in exclude:
            continue
        seg = '\n'.join(lines[s - 1:e])
        if pat.search(seg):
            cand.append(name)
    out = []
    for c in cand:
        f = _flag_for_fn(text, c, flags)
        # 🔑 自己守自己不算（G427 的 _no_dirty_wired_bad 就属于这种）
        if f and f != flags.get(target):
            out.append((c, f))
    return sorted(set(out))


def _run_flag(flag, timeout=90):
    """跑 push_api.py 的某个 flag，返回 rc；异常/超时返回 None。"""
    if not flag:
        return None
    cmd = [sys.executable, os.path.join(HERE, 'push_api.py'),
           '--' + flag.replace('_', '-')]
    try:
        p = subprocess.run(cmd, cwd=ROOT, stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, timeout=timeout)
        return p.returncode
    except Exception:
        return None


def _run_mut(mut_path, flag, timeout=90):
    # 🔑 跑**变异体副本**而不是原文件（138 轮真实事故）。
    #    🔴 写被测文件本身一旦写坏，"恢复"就没有参照物了。
    if not flag:
        return (None, '')
    cmd = [sys.executable, mut_path, '--' + flag.replace('_', '-')]
    try:
        p = subprocess.run(cmd, cwd=ROOT, stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, timeout=timeout)
        return (p.returncode, (p.stdout or b'').decode('utf-8', 'replace'))
    except Exception as e:
        return (None, '<异常> %s: %s' % (type(e).__name__, e))


def _run_flag2(flag, timeout=90):
    """同 _run_flag，但把 stdout/stderr 一并返回 —— 🔑 便于区分
    "拒绝"与"代码坏掉"（第一百零四轮：崩溃的 rc 也是 1）。"""
    if not flag:
        return (None, '')
    cmd = [sys.executable, os.path.join(HERE, 'push_api.py'),
           '--' + flag.replace('_', '-')]
    try:
        p = subprocess.run(cmd, cwd=ROOT, stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, timeout=timeout)
        return (p.returncode, (p.stdout or b'').decode('utf-8', 'replace'))
    except Exception as e:
        return (None, f'<异常> {type(e).__name__}: {e}')


def _other_pushers():
    """🔑 返回**其它**正在推送的进程 pid 列表（不含自己）。

    🔴 判活必须查 /proc（真实进程），不能凭"上次命令报了超时"推断
       —— 139 轮真实事故：工具报 TimeoutError，三个推送进程却都活着。
    🔑 读不到 /proc（非 Linux / 权限问题）时返回 None —— 拒绝给结论，
       与第一百零六轮"字段缺失不能当成没有违规"同一判据。
    """
    if not os.path.isdir('/proc'):
        return None
    me = os.getpid()

    def _ppid(pid):
        try:
            st = io.open('/proc/%d/stat' % pid, encoding='utf-8').read()
            return int(st.rsplit(')', 1)[1].split()[1])
        except Exception:
            return None

    # 🔑 必须排除**自己的祖先进程**（139 轮真实误报）：
    #    🔴 调用 push_api.py 的那条 bash -c 命令行里同样含
    #       'push_api.py' 与 '-m'（`git commit -m` / heredoc 里的源码），
    #       子串匹配会**把发起命令的 shell 自己当成并发推送** ——
    #       结果是每次推送都被自己堵死。
    #    🔑 判据：**"命令行里出现这两个词" ≠ "这个进程在推送"**。
    anc = set()
    p = me
    for _ in range(64):
        anc.add(p)
        q = _ppid(p)
        if not q or q == p or q in anc:
            break
        p = q

    out = []
    try:
        for e in os.listdir('/proc'):
            if not e.isdigit():
                continue
            pid = int(e)
            if pid in anc:
                continue
            try:
                cl = io.open('/proc/%s/cmdline' % e, 'rb').read()
            except OSError:
                continue
            # 🔑 按 **argv 分词**匹配，而不是整条命令行做子串匹配
            argv = [x.decode('utf-8', 'replace')
                    for x in cl.split(b'\0') if x]
            if not argv:
                continue
            if not any(a.endswith(PUSH_LOCK_ARGS[0]) for a in argv):
                continue
            if PUSH_LOCK_ARGS[1] not in argv:
                continue
            out.append(pid)
    except OSError:
        return None
    return sorted(out)


def cmd_assert_push_exclusive():
    """🔑 G429：断言"推送互斥"这条守卫**仍在代码里**。

    ① `PUSH_LOCK_ARGS` 常量非空且被引用
    ② `_other_pushers()` 有定义
    ③ 🔑 `main()` 推送路径里真有 `if _other_pushers(): return 1` 守卫
       —— 只验①②不够：常量和函数都在，但没人调用它，守卫等于不存在
       （与第一百一十一轮"登记了却没被引用"同源）
    """
    print('🔑 **推送互斥守卫检查**（G429）')
    print('=' * 70)
    text = io.open(os.path.join(HERE, 'push_api.py'), encoding='utf-8').read()
    bad = []

    val = globals().get('PUSH_LOCK_ARGS')
    if not val:
        bad.append('PUSH_LOCK_ARGS 为空 —— 门禁会静默失效')
    elif not isinstance(val, tuple):
        bad.append('PUSH_LOCK_ARGS 不是 tuple —— 门禁会静默失效')

    try:
        tree = ast.parse(text)
    except SyntaxError as ex:
        print('🔴 push_api.py 无法解析: %s —— 拒绝给结论' % ex)
        return 1
    refs = 0
    for n in ast.walk(tree):
        if isinstance(n, ast.Name) and n.id == 'PUSH_LOCK_ARGS' \
                and isinstance(n.ctx, ast.Load):
            refs += 1
    if refs == 0:
        bad.append('PUSH_LOCK_ARGS **无任何引用** —— 常量形同虚设')

    fns = {n.name for n in tree.body if isinstance(n, ast.FunctionDef)}
    if '_other_pushers' not in fns:
        bad.append('_other_pushers() **未定义** —— 门禁会 NameError')
    m = [n for n in tree.body
         if isinstance(n, ast.FunctionDef) and n.name == 'main']
    guard = False
    if m:
        for n in ast.walk(m[0]):
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) \
                    and n.func.id == '_other_pushers':
                guard = True
    if not guard:
        bad.append('main() 里**没有**调用 _other_pushers() —— 守卫等于不存在')

    if bad:
        print('🔴 推送互斥守卫**不完备**：')
        for b in bad:
            print('   - ' + b)
        print('=' * 70)
        return 1
    print('✅ 推送互斥守卫完备：常量已登记 · 函数已定义 · main() 真调用')
    print('=' * 70)
    return 0


def _spawn_fake_pusher():
    """🔑 起一个**假并发推送进程**（真的占住 /proc/<pid>/cmdline）。

    🔑 为什么必须造**真进程**而不造假 /proc 数据：
       🔴 若改成"造一个假 /proc 喂给它"，那就是**自测在测自己抄的那份**
          （第一百轮自证循环）—— 实现体换成 `return []` 时照样"通过"。
    🔑 假脚本名以 `push_api.py` 结尾（`_other_pushers` 用 endswith 匹配），
       内容只是 `time.sleep` —— **不会真推送**。
       🔴 139 轮事故的本体就是"真推送进程并发"，自测绝不能复刻它。
    🔑 落在 `scripts/_selftest_tmp/`（第一百一十八轮已 gitignore 且 G411 断言
       其真生效），故即便残留也进不了 git 索引。
    """
    d = os.path.join(HERE, '_selftest_tmp')
    try:
        if not os.path.isdir(d):
            os.makedirs(d, exist_ok=True)
        p = os.path.join(d, '.fake_push_api.py')
        io.open(p, 'w', encoding='utf-8').write(
            'import time\ntime.sleep(120)\n')
        return (p, subprocess.Popen([sys.executable, p, '-m'],
                                    stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL))
    except Exception:
        return (None, None)


def cmd_assert_blob_retry():
    """🔑 G431：blob 上传的**网络抖动必须重试**（第一百四十一轮）。

    🔴 真实事故（本条的动机）：**137/138/139 三轮内容始终没抵达远端**，
       每次报的都是"域名解析失败"。本轮实测一次推送 321 个文件里 **26 个**
       因 `NET:URLError ... Temporary failure in name resolution` 失败；
       🔑 只要有一个失败整次推送就中止（fail-safe），于是
       🔴 **一次抖动 = 整轮白干** —— 而且失败原因看起来像"网络不好"，
          不会有人去查"为什么没有重试"。

    🔑 四条判据：
       ① `BLOB_NET_RETRY` / `BLOB_RETRY_SLEEP` 存在且为正
          （🔴 缺失/为 0 → 重试静默变成"不重试"，与 106 轮同病）
       ② AST：`mk_blob` 内确有重试循环，且过滤条件是 `startswith('NET:')`
          —— 🔑 **重试必须只覆盖网络层**；HTTP 4xx/5xx 重试无意义且放大故障
       ③ **行为反证（真调用实现，不抄一份）**：把 `req` 换成"前 2 次返回
          NET 错误、第 3 次成功"，断言 `mk_blob` **最终成功**且真调了 3 次
          → 防"实现被换成只发一次"（130/132 轮判据唯一实现的同款洞）
       ④ **反向行为反证**：`req` 恒返回 HTTP 500，断言**只调用 1 次**
          → 防"无差别重试"（把内容/权限错误也重试，会放大故障）
    """
    print('🔑 **blob 网络抖动必须重试**（G431）')
    print('=' * 70)
    os.chdir(ROOT)
    bad = []

    n = globals().get('BLOB_NET_RETRY')
    sl = globals().get('BLOB_RETRY_SLEEP')
    if not isinstance(n, int) or n <= 0:
        bad.append('BLOB_NET_RETRY 不是正整数 —— 重试会静默变成"不重试"')
    if not isinstance(sl, (int, float)) or sl <= 0:
        bad.append('BLOB_RETRY_SLEEP 不是正数 —— 退避形同虚设')
    print(f'① 常量 BLOB_NET_RETRY={n} · BLOB_RETRY_SLEEP={sl}')

    # ② AST：重试循环 + 只认 NET
    try:
        tree = ast.parse(io.open(os.path.join(ROOT, 'scripts', 'push_api.py'),
                                encoding='utf-8').read())
    except Exception as e:
        bad.append(f'无法解析源码 —— 拒绝给结论: {e}')
        tree = None
    has_loop = has_net = False
    if tree is not None:
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == 'mk_blob':
                for sub in ast.walk(node):
                    if isinstance(sub, ast.For):
                        for s2 in ast.walk(sub):
                            if isinstance(s2, ast.Call) and isinstance(
                                    s2.func, ast.Attribute)                                     and s2.func.attr == 'startswith'                                     and any(isinstance(a, ast.Constant)
                                            and a.value == 'NET:'
                                            for a in s2.args):
                                has_loop = has_net = True
    if not has_loop:
        bad.append('mk_blob 内找不到"仅对 NET 错误重试"的循环 —— 116~140 轮旧实现')
    print(f'② AST 重试循环 · 只认 NET: {has_loop and has_net}')

    # ③ 行为反证：抖 2 次后应成功
    real_req = globals().get('req')
    old_sleep = globals().get('BLOB_RETRY_SLEEP')
    calls = []

    def _fake_net(m, u, d=None):
        calls.append(1)
        if len(calls) <= 2:
            return {'__err': 'NET:URLError:<urlopen error '
                             '[Errno -3] Temporary failure in name resolution>'}
        return {'sha': '0' * 40}

    globals()['req'] = _fake_net
    globals()['BLOB_RETRY_SLEEP'] = 0
    try:
        _p, sha, err = mk_blob('README.md')
    except Exception as e:
        sha, err = None, f'异常 {type(e).__name__}: {e}'
    finally:
        globals()['req'] = real_req
        globals()['BLOB_RETRY_SLEEP'] = old_sleep
    if sha is None:
        bad.append(f'连抖 2 次后仍失败（{err}）—— 重试没生效')
    elif len(calls) < 3:
        bad.append(f'只调用了 {len(calls)} 次 —— 重试次数不足')
    print(f'③ 行为反证：抖 2 次 → 调用 {len(calls)} 次 · 结果 '
          f'{"成功" if sha else "失败"}')

    # ④ 反向：HTTP 错误不得重试
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

    if bad:
        for b in bad:
            print('🔴', b)
        print('=' * 70)
        return 1
    print('✅ blob 网络抖动重试 4 条判据全部通过')
    print('=' * 70)
    return 0


# 🔑 第一百四十二轮：**远端轮次对账**（G432）。
#    🔴 第一百四十一轮真实事故：137 / 138 / 139 三轮内容**始终没抵达远端**，
#       而「远端 HEAD 停在第 136 轮」**没有任何门禁在看** ——
#       三轮的回复都写成「卡在最后一步」，连续三轮无人发现。
#    🔑 根因之一（本轮实测）：远端 59 个 commit 里 **43 个**消息是
#       `同步（N 个文件）`，**不含轮次** → 远端历史**无法逐轮回溯**，
#       「哪一轮的内容到了」在远端根本无从回答。
#    ✅ 治本：推送消息**必须**含"第X轮"；在此之后远端才可逐轮对账。
REMOTE_ROUNDS_SINCE = 142
# 🔑 历史缺口**不追溯**（137~140 的内容已随 141 抵达，但无独立 commit）；
#    自 REMOTE_ROUNDS_SINCE 起**逐轮**要求。
REMOTE_ROUND_GAP_ALLOWLIST = os.path.join(
    ROOT, 'ledger', 'remote_round_gap_allowlist.txt')


def _cn_round(msg):
    """🔑 从 commit 消息解析轮次；**解析不了返回 None**（不猜）。

    🔴 第一百零八轮真实 bug：`partition('百')` 把"一百零七"解析成 **100**。
       ✅ 现在复用 claim_verify 的逐字符累计实现（**不抄一份**）。
    """
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from claim_verify import _cn2num
    m = re.search(u'第([零一二三四五六七八九十百]+)轮', msg or '')
    if not m:
        return None
    return _cn2num(m.group(1))


def _round_msg_bad(msg):
    """🔑 推送消息校验（G432 判据①的**唯一实现**）。

    🔑 返回 [] = 通过；返回非空 = 阻断理由列表。
    🔴 消息为空 / 不含轮次 → 阻断（否则远端历史无法逐轮回溯）。
    """
    bad = []
    if msg is None or not str(msg).strip():
        bad.append(u'推送消息为空 —— 必须含"第X轮"')
        return bad
    n_ = _cn_round(msg)
    if n_ is None:
        bad.append(u'推送消息不含"第X轮"：%r —— 远端历史将无法逐轮回溯'
                   % str(msg)[:40])
        return bad
    if n_ <= 0:
        bad.append(u'推送消息轮次解析为 %r（异常）' % n_)
    return bad


def _round_msg_wired_bad():
    """🔑 G432 判据①：main() 里**真有**"消息不含轮次即退出"。

    🔑 与 134 轮同款：**不认写法**（If 的 test 里引用 `_round_msg_bad` 即可），
       但必须**同分支内真退出**（sys.exit / return）——
       🔴 只打印警告等于没拦（74 轮"说了≠拦住了"）。
    """
    try:
        with io.open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                  'push_api.py'), encoding='utf-8') as f:
            src_ = f.read()
    except Exception as e:
        return [u'读不到 push_api.py：%s' % e]
    tree = _ast.parse(src_)
    fn = None
    for nd in tree.body:
        if isinstance(nd, _ast.FunctionDef) and nd.name == 'main':
            fn = nd
            break
    if fn is None:
        return [u'找不到 main()']
    # 🔑 调用可能写在**赋值**里（`x = _round_msg_bad(msg)`）再被 If 引用 ——
    #    只查 If 的 test 会**认不出**（142 轮第一次实测就是这么漏的）。
    assigned = set()
    for nd in _ast.walk(fn):
        if isinstance(nd, _ast.Assign) and isinstance(nd.value, _ast.Call):
            f_ = nd.value.func
            if isinstance(f_, _ast.Name) and f_.id == '_round_msg_bad':
                for t in nd.targets:
                    if isinstance(t, _ast.Name):
                        assigned.add(t.id)
    if not assigned:
        return [u'main() 里没有 `_round_msg_bad(...)` 的调用 —— '
                u'推送仍可不带轮次']
    hit = False
    for nd in _ast.walk(fn):
        if not isinstance(nd, _ast.If):
            continue
        names = set(x.id for x in _ast.walk(nd.test)
                    if isinstance(x, _ast.Name))
        if not (names & assigned):
            continue
        exits = False
        for s in nd.body:
            if isinstance(s, (_ast.Return, _ast.Raise)):
                exits = True
            elif isinstance(s, _ast.Expr) and isinstance(s.value, _ast.Call):
                try:
                    if _ast.unparse(s.value.func).endswith('exit'):
                        exits = True
                except Exception:
                    pass
        if not exits:
            return [u'main() 里 `_round_msg_bad` 的分支**没有退出** '
                    u'—— 只是警告，拦不住']
        hit = True
    if not hit:
        return [u'main() 里没有 `_round_msg_bad` 的校验分支 '
                u'—— 推送仍可不带轮次']
    return []


def _remote_round_set():
    """🔑 远端 commit 消息里的轮次集合。返回 (set|None, err)。

    🔑 None = **读不到** —— 与"没有轮次"严格区分，调用方必须拒绝给结论。
    """
    d = req('GET', '%s/commits?per_page=100' % API)
    if '__err' in d or not isinstance(d, list):
        return None, u'无法读取远端 commit 列表：%s' % req_err_desc(d)
    out = set()
    for c in d:
        n_ = _cn_round((c.get('commit') or {}).get('message', ''))
        if n_:
            out.add(n_)
    return out, None


def _local_round_set():
    """🔑 本地已声明的轮次集合（ledger/claims_<N>.txt）。"""
    out = set()
    for f in glob.glob(os.path.join(ROOT, 'ledger', 'claims_*.txt')):
        m = re.search(r'claims_(\d+)\.txt$', f)
        if m:
            out.add(int(m.group(1)))
    return out


def _load_remote_round_gaps():
    """🔑 已登记的"远端没有该轮 commit"轮次。返回 None = **读不到**。"""
    try:
        with io.open(REMOTE_ROUND_GAP_ALLOWLIST, encoding='utf-8') as f:
            out = {}
            for ln in f:
                ln = ln.strip()
                if not ln or ln.startswith('#'):
                    continue
                k = ln.split(':', 1)[0].strip()
                if k.isdigit():
                    out[int(k)] = ln.split(':', 1)[1].strip() if ':' in ln else ''
            return out
    except Exception:
        return None


def cmd_assert_remote_rounds():
    """🔑 G432：**远端轮次对账** —— 本轮内容必须真的到了远端，且可逐轮回溯。

    🔴 第一百四十一轮实测：137/138/139 三轮从未抵达远端，
       而"远端 HEAD 停在 136"这件事**没有任何门禁在看**；
       🔑 更阴的是：141 推送后**文件全都在**（G422 变绿），
       却仍看不出"137~140 四轮从未独立抵达" —— 文件齐 ≠ 轮次齐。

    🔑 五条判据：
      ① 推送消息必须含轮次（治本）+ 常量为正 + **行为反证**（真跑实现）
      ② 远端 commit 列表可读（读不到 → **拒绝给结论**）
      ③ 远端最大轮次 ≥ 本地最大轮次（直接抓"整轮未抵达"）
      ④ 自 REMOTE_ROUNDS_SINCE 起**逐轮**对账（缺须登记，僵尸豁免要报）
      ⑤ `_cn_round` 行为反证（防 108 轮"一百零七→100"复发）
    """
    print('=' * 70)
    print(u'🔑 G432 远端轮次对账（本轮必须抵达远端 · 历史可逐轮回溯）')
    print('=' * 70)
    bad = []

    # ── 判据①：推送消息必须含轮次 ──
    if not isinstance(REMOTE_ROUNDS_SINCE, int) or REMOTE_ROUNDS_SINCE <= 0:
        bad.append(u'REMOTE_ROUNDS_SINCE 非正整数 —— 对账基线失效')
    bad.extend(_round_msg_wired_bad())
    _rm = globals().get('_round_msg_bad')
    if _rm is None:
        bad.append(u'_round_msg_bad 不存在 —— 判据① 静默失效')
    else:
        for m_, want in ((u'第一百四十二轮：G432 远端轮次对账', 0),
                         (u'第一百零七轮：G401 基准变更史闭合', 0),
                         (u'同步（305 个文件）', 1),
                         (None, 1), ('', 1)):
            got = 1 if _rm(m_) else 0
            if got != want:
                bad.append(u'行为反证失败：_round_msg_bad(%r) 实测 %d，期望 %d'
                           % (m_, got, want))

    # ── 判据⑤：轮次解析（108 轮 bug 防复发）──
    _cr = globals().get('_cn_round')
    if _cr is None:
        bad.append(u'_cn_round 不存在 —— 轮次解析静默失效')
    else:
        for m_, want in ((u'第一百零七轮：…', 107), (u'第一百四十一轮：…', 141),
                         (u'第一百轮：…', 100), (u'同步（305 个文件）', None)):
            got = _cr(m_)
            if got != want:
                bad.append(u'解析反证失败：_cn_round(%r) = %r，期望 %r'
                           % (m_, got, want))

    loc = _local_round_set()
    if not loc:
        bad.append(u'本地没有任何 claims_<N>.txt —— **拒绝给结论**')
    print(u'\n🔑 本地已声明轮次 %d 个（最大 %s）'
          % (len(loc), max(loc) if loc else u'—'))

    # ── 判据②：远端可读 ──
    rem, err = _remote_round_set()
    if rem is None:
        bad.append(u'远端 commit 列表读不到 —— **拒绝给结论**（%s）' % err)
    else:
        print(u'🔑 远端可解析轮次 %d 个（最大 %s）'
              % (len(rem), max(rem) if rem else u'—'))

    # ── 判据③：远端最大轮次 ≥ 本地最大轮次 ──
    if rem is not None and loc:
        if not rem:
            bad.append(u'远端 commit 消息**全部**解析不出轮次 —— 拒绝给结论')
        else:
            lm, rm_ = max(loc), max(rem)
            if rm_ < lm:
                missing = sorted(x for x in loc if x > rm_)
                bad.append(u'远端最新轮次 %d **落后于**本地 %d —— '
                           u'本轮内容**未抵达远端**；未抵达轮次：%s'
                           % (rm_, lm, missing[:12]))

    # ── 判据④：自 REMOTE_ROUNDS_SINCE 起逐轮对账 ──
    gaps = _load_remote_round_gaps()
    if gaps is None:
        bad.append(u'读不到 %s —— **拒绝给结论**（读不到 ≠ 没有豁免）'
                   % os.path.basename(REMOTE_ROUND_GAP_ALLOWLIST))
    elif rem is not None and loc:
        need = sorted(x for x in loc if x >= REMOTE_ROUNDS_SINCE)
        missing = [x for x in need if x not in rem]
        unreg = [x for x in missing if x not in gaps]
        if unreg:
            bad.append(u'自第 %d 轮起 %d 个轮次**未抵达远端且未登记**：%s'
                       u'（处置：重新推送，或登记豁免并写明理由）'
                       % (REMOTE_ROUNDS_SINCE, len(unreg), unreg[:12]))
        zombie = sorted(x for x in gaps if x in rem)
        if zombie:
            bad.append(u'僵尸豁免（登记了但远端其实有该轮）：%s' % zombie[:12])
        early = sorted(x for x in gaps if x < REMOTE_ROUNDS_SINCE)
        if early:
            bad.append(u'豁免轮次早于基线 %d（应调基线而非登记）：%s'
                       % (REMOTE_ROUNDS_SINCE, early[:12]))
        print(u'🔑 对账基线：自第 %d 轮起逐轮要求（需核 %d 轮 · 缺 %d · '
              u'已登记 %d）' % (REMOTE_ROUNDS_SINCE, len(need),
                               len(missing), len(gaps)))

    print()
    if bad:
        for b in bad:
            print(u'🔴 %s' % b)
        print('=' * 70)
        print(u'🔴 守卫失效（G432）')
        print('=' * 70)
        return 1
    print(u'✅ 远端轮次对账通过：远端最新轮次 %d ≥ 本地 %d，'
          u'且自第 %d 轮起无未登记缺口' % (max(rem), max(loc),
                                          REMOTE_ROUNDS_SINCE))
    print(u'   🔑 历史（< %d 轮）缺口**不追溯**，已在文档如实记录'
          % REMOTE_ROUNDS_SINCE)
    print('=' * 70)
    return 0


# 🔑 第一百四十三轮：G433 —— **文档轮次与清单轮次必须互相印证**。
#    🔴 142 轮诚实结论②（本轮指引）：G432 的本地轮次集合**只有 claims 一个来源**
#       （`_local_round_set()` 只 glob `ledger/claims_*.txt`）。
#    🔴 于是：claims_<N>.txt 被改名 / 漏写 / 编号写错 → 本地集合**少一轮**
#       → G432 判据③只要求「远端 max ≥ 本地 max」→ **缺口凭空消失**，rc=0 放行。
#    🔑 "文档里写了第 N 轮"是**独立于 claims 文件的第二个证据源**：
#       想让一轮悄悄消失，必须同时改**文档和清单两处**（109 轮同一已知边界）。
DOC_ROUND_MIN_FILES = 20
# 🔑 对账起始轮：**75**（G381 起才有声明清单机制）。
#    🔴 不用 REMOTE_ROUNDS_SINCE(142)：那只是"远端"对账基线；
#       文档↔清单是**本地两个证据源**之间的比对，覆盖面应更宽 ——
#       🔑 实测：若只用 142，删掉"第一百一十轮"的文档记录**无人发现**
#       （G384 只查最新一轮 · G418 只查清单有无 · G432 只看远端）。
DOC_CLAIMS_SINCE = 75
# 🔑 扫描范围：仓库内所有 .md，**排除** work/（已 gitignore 的回归产物）。
DOC_ROUND_SKIP_PARTS = ('/work/', '/.git/')


def _doc_round_set():
    """🔑 文档里声称的轮次集合。返回 (dict{轮次:set(文件)}|None, md 文件数)。

    🔑 None = **读不到**（md 文件数不足，或解析不出任何轮次）—— 拒绝给结论，
       与"文档里没有轮次"严格区分（106 轮："读不到 ≠ 没有违规"）。
    """
    hits = {}
    n_md = 0
    for f in glob.glob(os.path.join(ROOT, '**', '*.md'), recursive=True):
        fp = f.replace('\\', '/')
        if any(p in fp for p in DOC_ROUND_SKIP_PARTS):
            continue
        n_md += 1
        try:
            with io.open(f, encoding='utf-8', errors='ignore') as fh:
                t = fh.read()
        except Exception:
            continue
        for m in re.finditer(u'第([零一二三四五六七八九十百]+)轮', t):
            n_ = _cn_round(m.group(0))
            if n_:
                hits.setdefault(n_, set()).add(os.path.relpath(f, ROOT))
    if n_md < DOC_ROUND_MIN_FILES or not hits:
        return None, n_md
    return hits, n_md


def _load_round_gaps():
    """🔑 轮次断号豁免。返回 (dict|None, 路径)；None = **读不到**。

    🔴 该常量定义在 **claim_verify.py**（不是本模块）—— 直接写裸名会
       `NameError`（84/111/118/119/133 轮同款错误，**第六次**）。
    """
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from claim_verify import ROUND_GAP_ALLOWLIST as _p
    try:
        with io.open(_p, encoding='utf-8') as f:
            out = {}
            for ln in f:
                ln = ln.strip()
                if not ln or ln.startswith('#'):
                    continue
                k = ln.split(':', 1)[0].strip()
                if k.isdigit():
                    out[int(k)] = ln.split(':', 1)[1].strip() if ':' in ln else ''
            return out, _p
    except Exception:
        return None, _p


def _doc_claims_closure_bad(doc_rounds, claim_rounds, gaps, since):
    """🔑 G433 判据②③④⑤ 的**唯一实现**（可被行为反证直接调用）。

    🔑 doc_rounds / claim_rounds 为 int 集合，gaps 为 {轮次: 理由}。
    🔑 返回阻断理由列表（空 = 通过）。
    """
    bad = []
    if not doc_rounds or not claim_rounds:
        return [u'文档轮次或清单轮次为空 —— **拒绝给结论**']
    dmax, cmax = max(doc_rounds), max(claim_rounds)
    # ── 判据②：两边最大轮次必须指向同一轮 ──
    if dmax != cmax:
        bad.append(u'文档最大轮次 %d **不等于**清单最大轮次 %d —— 两边必须指向同一轮'
                   u'（文档有而清单无：%s / 清单有而文档无：%s）'
                   % (dmax, cmax,
                      sorted(x for x in doc_rounds if x > cmax)[:8],
                      sorted(x for x in claim_rounds if x > dmax)[:8]))
    # ── 判据③：文档声称的轮次必须有清单，除非已登记豁免且理由充分 ──
    miss = sorted(x for x in doc_rounds
                  if x >= since and x not in claim_rounds)
    unreg = [x for x in miss if x not in gaps]
    if unreg:
        bad.append(u'文档声称但**无清单且未登记**的轮次（≥ %d）：%s'
                   % (since, unreg[:12]))
    thin = [x for x in miss if x in gaps and len(gaps.get(x, '')) < 10]
    if thin:
        bad.append(u'已登记豁免但**理由不足 10 字符**：%s' % thin[:12])
    # ── 判据④（反向）：有清单却无文档记录 ──
    orphan = sorted(x for x in claim_rounds
                    if x >= since and x not in doc_rounds)
    if orphan:
        bad.append(u'有清单但**文档无该轮记录**（≥ %d）：%s' % (since, orphan[:12]))
    # ── 判据⑤：僵尸豁免 ──
    zombie = sorted(x for x in gaps if x in claim_rounds)
    if zombie:
        bad.append(u'僵尸豁免（登记了断号但 claims 文件其实在）：%s' % zombie[:12])
    return bad


def cmd_assert_doc_round_closure():
    """🔑 G433：**文档轮次与清单轮次必须互相印证**（两个独立证据源）。

    🔴 142 轮诚实结论②：G432 的本地集合只有 claims 一个来源 ——
       claims 文件改名 / 漏写 / 编号写错 → 本地少一轮 →
       G432 判据③「远端 max ≥ 本地 max」**直接失明**（rc=0）。
    🔑 "文档写了第 N 轮"是第二个证据源：想让一轮悄悄消失，
       必须同时改**文档和清单两处**（109 轮「同时改两处」的已知边界）。

    🔑 六条判据：
       ① 文档集合可读（md 数 ≥ 下限且解析出轮次）—— 读不到**拒绝给结论**
       ② 🔑 文档最大轮次 == 清单最大轮次（核心：两边必须指向同一轮）
       ③ 文档有而清单无（≥ 基线）→ 须已登记豁免且理由 ≥ 10 字符
       ④ 清单有而文档无（≥ 基线）→ 报（反向，防"清单凭空多一轮"）
       ⑤ 僵尸豁免：登记了断号却其实有 claims 文件 → 报
       ⑥ **行为反证**：真跑一次改坏的输入，断言判据会响（防判据被改成桩）
    """
    print('=' * 70)
    print(u'🔑 G433 文档轮次 ↔ 清单轮次互相印证（两个独立证据源）')
    print('=' * 70)
    bad = []

    # ── 判据①：文档集合可读 ──
    if not isinstance(DOC_ROUND_MIN_FILES, int) or DOC_ROUND_MIN_FILES <= 0:
        bad.append(u'DOC_ROUND_MIN_FILES 非正整数 —— 判据① 失效')
    if not isinstance(DOC_CLAIMS_SINCE, int) or DOC_CLAIMS_SINCE <= 0:
        bad.append(u'DOC_CLAIMS_SINCE 非正整数 —— 对账基线失效')
    doc, n_md = _doc_round_set()
    print(u'\n🔑 扫描 md %d 个（下限 %d）' % (n_md, DOC_ROUND_MIN_FILES))
    if doc is None:
        bad.append(u'文档轮次集合**读不到**（md %d 个 < 下限 %d，或解析不出轮次）'
                   u' —— **拒绝给结论**' % (n_md, DOC_ROUND_MIN_FILES))
    else:
        print(u'🔑 文档声称轮次 %d 个（最大 %d）' % (len(doc), max(doc)))

    claims = _local_round_set()
    if not claims:
        bad.append(u'清单轮次集合为空 —— **拒绝给结论**')
    else:
        print(u'🔑 清单轮次 %d 个（最大 %d）' % (len(claims), max(claims)))

    gaps, gpath = _load_round_gaps()
    if gaps is None:
        bad.append(u'读不到 %s —— **拒绝给结论**（读不到 ≠ 没有豁免）'
                   % os.path.basename(gpath))
    else:
        print(u'🔑 断号豁免已登记 %d 条：%s' % (len(gaps), sorted(gaps)[:12]))

    # ── 判据②③④⑤（唯一实现）──
    if doc is not None and claims and gaps is not None:
        if '_doc_claims_closure_bad' not in globals():
            bad.append(u'_doc_claims_closure_bad 不存在 —— 判据静默失效')
        else:
            bad.extend(_doc_claims_closure_bad(
                set(doc), claims, gaps, DOC_CLAIMS_SINCE))
            # ── 判据⑥：行为反证 ──
            for d_, c_, g_, s_, want, why in (
                    ({100}, {100}, {}, 100, 0, u'完全一致'),
                    ({101, 100}, {100}, {}, 100, 1, u'文档多一轮（无清单）'),
                    ({100}, {101, 100}, {}, 100, 1, u'清单多一轮（文档无记录）'),
                    ({100}, {100}, {100: u'理由理由理由'}, 100, 1, u'僵尸豁免'),
                    ({100, 99}, {100}, {99: u'短'}, 99, 1, u'理由不足 10 字符'),
            ):
                got = 1 if _doc_claims_closure_bad(d_, c_, g_, s_) else 0
                if got != want:
                    bad.append(u'行为反证失败[%s]：实测 %d，期望 %d'
                               % (why, got, want))
            print(u'🔑 行为反证 5 例已跑（含"完全一致"应为通过）')

    print()
    if bad:
        for b in bad:
            print(u'🔴 %s' % b)
        print('=' * 70)
        print(u'🔴 守卫失效（G433）')
        print('=' * 70)
        return 1
    print(u'✅ 两个证据源一致：文档最大轮次 == 清单最大轮次 == %d，'
          u'且自第 %d 轮起无未登记缺口' % (max(claims), DOC_CLAIMS_SINCE))
    print('=' * 70)
    return 0


def cmd_assert_push_exclusive_alive():
    """🔑 G430：推送互斥守卫**名字锚点 + 行为反证**。

    🔴 第一百三十九轮破坏实测（本条要补的那两个洞）：
       - **一致改名** rc=0：把 `_other_pushers` 与 G429 判据里的期望名**一起**
         改成同一个新名字 → G429 三条判据**全部通过**。
         🔑 判据：**期望名与被判对象同名时，"改名"与"换实现"无法区分。**
       - 更阴的一层（🔴 这才是真危害）：把实现体换成 `return []` 而**名字不动**
         → G429 判据②（有定义）✅ 判据③（main 真调用）✅ → **照绿**。
         守卫看起来完备，实际**永远放行并发推送**（139 轮的事故会重演）。

    🔑 三条判据：
       ① 外部锚点 `ledger/trust_root.json::PUSH_EXCLUSIVE_NAMES` 必须可读
          （🔴 读不到 → **拒绝给结论**，不当"没有名字要守"）
       ② 代码里的名字集合必须与锚点**完全一致**（多一个/少一个都报）
          → 一致改名会被抓（锚点没跟着改）
       ③ **行为反证**：真起一个假并发进程，调用**真实实现** `_other_pushers()`
          （🔑 `globals().get` 取，**不抄一份** —— 第一百轮自证循环），
          断言它**真的发现了那个 pid**：
          - 返回 None  → 拒绝给结论 rc=1
          - 不含假 pid → rc=1「守卫可能已被换成 return []」
          - 含自己/祖先 → rc=1（139 轮误报方向的反向断言）
    """
    print('🔑 **推送互斥守卫 · 名字锚点与行为反证**（G430）')
    print('=' * 70)
    bad = []
    tr = _trust_root()
    if tr is None:
        print('🔴 信任根不可读 —— 拒绝给结论（不静默当"没有名字要守"）')
        print('=' * 70)
        return 1
    anchor = tr.get('PUSH_EXCLUSIVE_NAMES')
    if not anchor or not isinstance(anchor, (list, tuple)):
        print('🔴 锚点 PUSH_EXCLUSIVE_NAMES 未登记或格式不对 —— 拒绝给结论')
        print('=' * 70)
        return 1
    want = set(anchor)
    local = globals().get('PUSH_EXCLUSIVE_NAMES')
    if not local:
        print('🔴 代码里 PUSH_EXCLUSIVE_NAMES 未登记 —— 拒绝给结论')
        print('=' * 70)
        return 1
    if set(local) != want:
        bad.append(
            '名字集合与锚点不一致：锚点有而代码无 %s / 代码有而锚点无 %s'
            ' —— 🔴 一致改名会让 G429 静默失效'
            % (sorted(want - set(local)), sorted(set(local) - want)))
    # ② 名字必须**真的存在**于代码（锚点一致 ≠ 真的定义了）
    try:
        text = io.open(os.path.join(HERE, 'push_api.py'),
                       encoding='utf-8').read()
        tree = ast.parse(text)
    except SyntaxError as ex:
        print('🔴 push_api.py 无法解析: %s —— 拒绝给结论' % ex)
        print('=' * 70)
        return 1
    top_names = set()
    for n in tree.body:
        if isinstance(n, ast.FunctionDef):
            top_names.add(n.name)
        elif isinstance(n, ast.Assign):
            for t in n.targets:
                if isinstance(t, ast.Name):
                    top_names.add(t.id)
    gone = sorted(x for x in want if x not in top_names)
    if gone:
        bad.append('锚点登记的名字在代码里**不存在**：%s' % gone)

    # ③ 行为反证
    path, proc = _spawn_fake_pusher()
    if proc is None:
        print('🔴 无法启动假并发进程 —— 拒绝给结论（不能跳过行为反证）')
        print('=' * 70)
        return 1
    killed = True
    try:
        time.sleep(0.8)
        fn = globals().get('_other_pushers')
        if fn is None:
            bad.append('_other_pushers **未定义** —— 无法行为反证')
            res = None
        else:
            res = fn()
        if res is None:
            bad.append('_other_pushers() 返回 None —— 拒绝给结论'
                       '（读不到进程表 ≠ 没有并发）')
        elif proc.pid not in res:
            bad.append(
                '未发现刚起的假并发进程（pid %d）—— 🔴 守卫可能已被换成'
                ' return []，届时并发推送将**永远放行**' % proc.pid)
        else:
            print('   ✅ 行为反证：真实实现发现了假并发进程 pid %d' % proc.pid)
        me = os.getpid()
        if isinstance(res, list) and me in res:
            bad.append('把**自己**（pid %d）当成了并发推送 —— 139 轮误报方向'
                       % me)
    finally:
        try:
            proc.kill()
            proc.wait(timeout=5)
        except Exception:
            killed = False
        # 🔑 清理自断言（第一百一十九轮：失败必须让调用方知道，不能只打印）
        try:
            if path and os.path.exists(path):
                os.remove(path)
            if path and os.path.exists(path):
                killed = False
        except Exception:
            killed = False
    if not killed:
        bad.append('假并发进程/临时脚本**清理失败** —— 会污染后续门禁')

    if bad:
        print('🔴 推送互斥守卫**不完备**：')
        for b in bad:
            print('   - ' + b)
        print('=' * 70)
        return 1
    print('✅ 名字与锚点一致 · 行为反证通过（真实实现真能发现并发进程）')
    print('=' * 70)
    return 0


def cmd_mutation_scan():
    """🔑 G428-扫描：**哑门禁变异扫描**。

    🔑 做法（变异测试）：把每个 `cmd_*` 门禁函数整体换成 `return 0`，
       然后问"**还有谁会响**"：
       - `guarded`    ：至少一个守望者**实跑** rc=1（真会被发现）
       - `static_only`：有函数引用了它，但实跑**全部 rc=0**（存在但无关）
       - `mute`       ：**无人引用** —— 改成桩后全仓库没有任何东西会发现
    """
    print('🔑 **哑门禁变异扫描**（G428）')
    print('=' * 70)
    src = os.path.join(HERE, 'push_api.py')
    orig = open(src, encoding='utf-8').read()
    orig_sha = hashlib.sha1(orig.encode('utf-8')).hexdigest()
    ranges = _top_fn_ranges(orig)
    flags = _cmd_flag_map(orig)
    exclude = set(MUTATION_SELF_EXCLUDE) | {'main'}
    targets = sorted(k for k in ranges
                     if k.startswith('cmd_') and k not in exclude)
    if len(targets) < MUTATION_TARGET_MIN:
        print(f'🔴 目标函数只有 {len(targets)} 个'
              f'（下限 {MUTATION_TARGET_MIN}）—— 拒绝给结论')
        print('   🔑 目标被大量删除时扫描会"扫得少却全绿"，必须拦住')
        print('=' * 70)
        return 1
    print(f'   目标门禁 {len(targets)} 个 · 逐个桩化为 `return 0` 后看谁会响')
    res = {}
    failed = []
    for t in targets:
        s, e = ranges[t]
        new = _stub_replace(orig.split('\n'), s, e)
        if hashlib.sha1(new.encode('utf-8')).hexdigest() == orig_sha:
            failed.append(f'{t}：**变异未改变文件** —— 扫描结论不可信')
            continue
        try:
            _atomic_write_text(MUTATION_TMP, new)
            own_rc, own_out = _run_mut(MUTATION_TMP, flags.get(t))
            wnames = _watchers_of(new, t, exclude, flags) or []
            wl = []
            for w, wf in wnames:
                wl.append({'fn': w,
                           'flag': ('--' + wf.replace('_', '-')) if wf else None,
                           'rc': _run_mut(MUTATION_TMP, wf)[0]})
            if own_rc != 0:
                verdict = 'unknown'
                tail = [x for x in (own_out or '').strip().split('\n')
                        if x.strip()][-4:]
                failed.append(f'{t}：桩化后自身 rc={own_rc}（应为 0）'
                              f' —— 变异体有副作用，结论不可用')
                print(f'   🔴 {t} rc={own_rc}')
                for x in tail:
                    print('      | ' + x[:150])
            elif any(x['rc'] == 1 for x in wl):
                verdict = 'guarded'
            elif wl:
                verdict = 'static_only'
            else:
                verdict = 'mute'
            res[t] = {'flag': ('--' + flags[t].replace('_', '-'))
                      if t in flags else None,
                      'muted_rc': own_rc, 'verdict': verdict, 'watchers': wl}
        finally:
            try:
                os.unlink(MUTATION_TMP)
            except OSError:
                pass
            # 🔑 第一百四十轮：清理自断言（第一百一十九轮同款）
            #    🔴 `except OSError: pass` 会把"清理失败"伪装成"没什么要清理的"；
            #       残留会让**下次扫描读到旧变异体**，结论变成编的。
            if os.path.exists(MUTATION_TMP):
                print("🔴 变异体副本**清理失败** —— 残留会让下次扫描读到旧变异体")
    # 🔑 原文件**全程未被写过** —— 这里校验它确实还是原文
    back = open(src, encoding='utf-8').read()
    if hashlib.sha1(back.encode('utf-8')).hexdigest() != orig_sha:
        print('🔴 **push_api.py 被改动过** —— 扫描不该写它，拒绝写产物')
        print('=' * 70)
        return 1
    if failed:
        print('🔴 扫描过程中出现不可用结论：')
        for f in failed:
            print('   - ' + f)
        print('=' * 70)
        return 1
    import collections
    cnt = collections.Counter(v['verdict'] for v in res.values())
    print()
    print(f'   guarded     {cnt.get("guarded", 0)} 个（有守望者，实跑 rc=1）')
    print(f'   static_only {cnt.get("static_only", 0)} 个（被引用但抓不到）')
    print(f'🔴 mute        {cnt.get("mute", 0)} 个（**改成桩全仓库无人发现**）')
    print()
    for t in sorted(res):
        if res[t]['verdict'] != 'mute':
            w = ', '.join(f"{x['fn']}(rc={x['rc']})" for x in res[t]['watchers'])
            print(f'   ✅ {t:<38} {res[t]["verdict"]:<11} ← {w}')
    mute = [t for t in sorted(res) if res[t]['verdict'] == 'mute']
    if mute:
        print()
        print(f'🔴 **哑门禁 {len(mute)} 个**（部分列出）：')
        for t in mute[:12]:
            print(f'   - {t}')
        if len(mute) > 12:
            print(f'   … 其余 {len(mute) - 12} 个见产物')
    try:
        os.makedirs(os.path.dirname(MUTATION_SCAN_FILE), exist_ok=True)
        payload = {'src_sha': orig_sha, 'targets': len(targets),
                   'count': dict(cnt), 'gates': res}
        _atomic_write_text(MUTATION_SCAN_FILE,
                           json.dumps(payload, ensure_ascii=False,
                                      indent=1, sort_keys=True))
        print()
        print(f'   产物：{os.path.relpath(MUTATION_SCAN_FILE, ROOT)}')
    except Exception as e:
        print(f'🔴 写产物失败：{e}')
        print('=' * 70)
        return 1
    print('=' * 70)
    return 0


def _mutation_probe(payload):
    """🔑 行为反证：**真跑一次**桩化，验证产物里记的 rc 不是编的。

    🔴 没有这一步，扫描器完全可以"声称某个门禁有守望者"而从不验证
       —— 与第一百轮"自测测了自己抄的那份"同源。
    """
    src = os.path.join(HERE, 'push_api.py')
    orig = open(src, encoding='utf-8').read()
    gates = payload.get('gates') or {}
    cand = [k for k in sorted(gates) if gates[k].get('verdict') == 'guarded']
    if not cand:
        return (False, '产物中**没有** guarded 门禁 —— 无法证明扫描可信，'
                       '拒绝给结论')
    t = cand[0]
    ranges = _top_fn_ranges(orig)
    if t not in ranges:
        return (False, f'{t} 在代码中已不存在 —— 产物过期')
    flags = _cmd_flag_map(orig)
    exclude = set(MUTATION_SELF_EXCLUDE) | {'main'}
    s, e = ranges[t]
    new = _stub_replace(orig.split('\n'), s, e)
    got = []
    try:
        _atomic_write_text(MUTATION_TMP, new)
        for w, wf in (_watchers_of(new, t, exclude, flags) or []):
            got.append((w, _run_mut(MUTATION_TMP, wf)[0]))
    finally:
        try:
            os.unlink(MUTATION_TMP)
        except OSError:
            pass
        # 🔑 第一百四十轮：清理自断言（第一百一十九轮同款）
        #    🔴 `except OSError: pass` 会把"清理失败"伪装成"没什么要清理的"；
        #       残留会让**下次扫描读到旧变异体**，结论变成编的。
        if os.path.exists(MUTATION_TMP):
            print("🔴 变异体副本**清理失败** —— 残留会让下次扫描读到旧变异体")
    back = open(src, encoding='utf-8').read()
    if hashlib.sha1(back.encode('utf-8')).hexdigest() != \
            hashlib.sha1(orig.encode('utf-8')).hexdigest():
        return (False, '反证后 push_api.py 被改动 —— 不该发生')
    want = {x['fn']: x['rc'] for x in gates[t].get('watchers', [])}
    got_d = dict(got)
    if not any(v == 1 for v in got_d.values()):
        return (False, f'反证失败：{t} 桩化后守望者实测 {got_d} '
                       f'**无人 rc=1**，而产物声称 guarded')
    for k, v in want.items():
        if k in got_d and got_d[k] != v:
            return (False, f'反证失败：{k} 产物记 rc={v}，实测 rc={got_d[k]}')
    return (True, f'{t} 桩化后守望者实测 {got_d} —— 与产物一致')


def cmd_assert_mutation():
    """🔑 G428-断言：**哑门禁必须被登记为已知风险**。

    🔑 判据：
       ① 扫描产物必须可读 —— 读不到**拒绝给结论**（读不到 ≠ 没有哑门禁）
       ② 覆盖目标数 ≥ 下限（防"扫得少却全绿"）
       ③ `mute` / `static_only` 必须在豁免清单登记：理由 ≥ 10 字符
          + 批准轮次 ≤ 文档最大轮次（G389 同款）
       ④ **僵尸豁免**：登记了但已不在扫描结果中 → 应删除
       ⑤ 🔑 **行为反证**：真跑一次桩化，验证产物记的 rc 与实测一致
    """
    print('🔑 **哑门禁断言**（G428）')
    print('=' * 70)
    try:
        with open(MUTATION_SCAN_FILE, encoding='utf-8') as f:
            payload = json.load(f)
    except FileNotFoundError:
        print(f'🔴 扫描产物不存在：{os.path.relpath(MUTATION_SCAN_FILE, ROOT)}')
        print('   🔑 先跑 `--mutation-scan`')
        print('=' * 70)
        return 1
    except ValueError as e:
        print(f'🔴 产物解析失败：{e} —— 拒绝给结论')
        print('=' * 70)
        return 1
    gates = payload.get('gates')
    if not isinstance(gates, dict) or not gates:
        print('🔴 产物中没有 gates —— 拒绝给结论')
        print('=' * 70)
        return 1
    if int(payload.get('targets') or 0) < MUTATION_TARGET_MIN:
        print(f'🔴 产物覆盖目标 {payload.get("targets")} < '
              f'{MUTATION_TARGET_MIN} —— 拒绝给结论')
        print('=' * 70)
        return 1
    src = os.path.join(HERE, 'push_api.py')
    try:
        cur = hashlib.sha1(open(src, encoding='utf-8').read()
                           .encode('utf-8')).hexdigest()
    except Exception:
        cur = None
    if cur and payload.get('src_sha') and cur != payload['src_sha']:
        print('⚠️  产物基于旧版 push_api.py —— 建议重跑 --mutation-scan')
        print(f'   产物 {str(payload.get("src_sha"))[:12]} · '
              f'当前 {cur[:12]}')
    mx = None
    try:
        mx = _doc_max_round()
    except Exception:
        mx = None
    # 豁免清单
    allow = {}
    try:
        with open(MUTE_ALLOWLIST, encoding='utf-8') as f:
            for ln in f:
                s = ln.strip()
                if not s or s.startswith('#'):
                    continue
                parts = s.split('::', 1)
                if len(parts) != 2 or not parts[1].strip():
                    continue
                allow[parts[0].strip()] = parts[1].strip()
    except FileNotFoundError:
        print(f'🔴 豁免清单不存在：{os.path.relpath(MUTE_ALLOWLIST, ROOT)}')
        print('   🔑 读不到 ≠ 没有哑门禁 —— 拒绝给结论')
        print('=' * 70)
        return 1
    bad = []
    risky = [k for k in sorted(gates)
             if gates[k].get('verdict') in ('mute', 'static_only')]
    for k in risky:
        v = gates[k]['verdict']
        why = allow.get(k)
        if not why:
            bad.append(f'{k}（{v}）**未登记豁免** —— 改成桩无人发现')
            continue
        if len(why) < 10:
            bad.append(f'{k} 豁免理由过短（{len(why)}<10）—— 必须写明处置')
        m = re.search(r'(\d+)\s*轮', why)
        if not m:
            bad.append(f'{k} 豁免理由未写批准轮次（须形如"138轮"）')
        elif mx is not None and int(m.group(1)) > mx:
            bad.append(f'{k} 批准轮次 {m.group(1)} > 文档最大轮次 {mx}'
                       f' —— 🔴 来自未来的批准')
    # ④ 僵尸豁免
    for k in sorted(allow):
        if k not in gates:
            bad.append(f'僵尸豁免：{k} **不在**扫描结果中 —— 应删除')
        elif gates[k].get('verdict') == 'guarded':
            bad.append(f'僵尸豁免：{k} 实测 **guarded**（有人守）'
                       f' —— 不该再豁免')
    # ⑤ 行为反证
    ok, note = _mutation_probe(payload)
    if not ok:
        bad.append(f'行为反证失败 —— {note}')
    print(f'   目标 {payload.get("targets")} 个 · '
          f'guarded {payload.get("count", {}).get("guarded", 0)} · '
          f'static_only {payload.get("count", {}).get("static_only", 0)} · '
          f'🔴 mute {payload.get("count", {}).get("mute", 0)}')
    print(f'   已登记豁免 {len(allow)} 条 · 需处置 {len(risky)} 条')
    print(f'   行为反证：{note}')
    print()
    if bad:
        print('🔴 哑门禁处置不完整：')
        for b in bad[:20]:
            print('   - ' + b)
        if len(bad) > 20:
            print(f'   … 其余 {len(bad) - 20} 条')
        print('=' * 70)
        return 1
    print(f'✅ {len(risky)} 条哑门禁均已登记处置 · 无僵尸豁免 · 反证一致')
    print('=' * 70)
    return 0


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
    ap.add_argument('--assert-round-claims', action='store_true',
                    help='G421：推送前必须已有**本轮声明清单**且已纳入索引')
    ap.add_argument('--assert-index-pushed', action='store_true',
                    help='G422：本地索引 ⊆ 远端 tree（防推完又写无人发现）')
    ap.add_argument('--round-end', action='store_true',
                    help='轮次末尾必跑：G421+G422+G391 三项回读远端')
    ap.add_argument('--assert-round-end', action='store_true',
                    help='G423：轮次末尾入口必须真含这三项')
    ap.add_argument('--assert-round-end-wired', action='store_true',
                    help='G424：轮次末尾回读必须接在**推送主流程末尾**'
                         '（防"入口在但没人跑"）')
    ap.add_argument('--assert-round-end-single', action='store_true',
                    help='G425：步骤齐全判据须**唯一实现**且被 G423/G424 共用')
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
    ap.add_argument('--assert-criteria-roots', action='store_true',
                    help='G426：判据存在性信任根闭合（G425 判据⑧/⑨ 必须仍在代码中）')
    ap.add_argument('--assert-no-dirty', action='store_true',
                    help='G427：推送前必须**无未提交修改**'
                         '（防推的是工作区而非仓库版本，136 轮真实事故）')
    ap.add_argument('--assert-push-exclusive', action='store_true',
                    help='G429：推送必须互斥（并发推送会静默丢失工作，'
                         '139 轮真实事故：三个推送进程同时存活）')
    ap.add_argument('--assert-blob-retry', action='store_true',
                    help='G431：blob 网络抖动必须重试（常量 + AST + 行为反证）')
    ap.add_argument('--assert-remote-rounds', action='store_true',
                    help='G432：远端轮次对账（本轮必须抵达远端 · 历史可逐轮回溯）')
    ap.add_argument('--assert-doc-round-closure', action='store_true',
                    help='G433：文档轮次与清单轮次必须互相印证'
                         '（G432 的本地集合只有 claims 一个来源）')
    ap.add_argument('--assert-push-exclusive-alive', action='store_true',
                    help='G430：推送互斥守卫的**名字锚点 + 行为反证**'
                         '（139 轮：一致改名 / 实现换成 return [] 都照绿）')
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
    ap.add_argument('--assert-cleanup-verified', action='store_true',
                   help='G413：全部清理类调用必须带结果校验或登记豁免')
    ap.add_argument('--mutation-scan', action='store_true',
                    help='G428：把每个门禁**桩化**一遍，看还有谁会响')
    ap.add_argument('--assert-mutation', action='store_true',
                    help='G428：哑门禁必须登记处置 + 扫描结论须**行为反证**')
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
    if a.assert_criteria_roots:
        return cmd_assert_criteria_roots()
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

    if a.assert_cleanup_verified:
        return cmd_assert_cleanup_verified()
    if a.check_gitlink:
        os.chdir(ROOT)
        return cmd_check_gitlink()

    if a.check_symlink:
        os.chdir(ROOT)
        return cmd_check_symlink()

    if a.verify_push:
        os.chdir(ROOT)
        return cmd_verify_push(report=a.report)

    if a.assert_round_claims:
        os.chdir(ROOT)
        return cmd_assert_round_claims()

    if a.assert_index_pushed:
        os.chdir(ROOT)
        return cmd_assert_index_pushed()

    if a.round_end:
        os.chdir(ROOT)
        return cmd_round_end()

    if a.assert_round_end:
        os.chdir(ROOT)
        return cmd_assert_round_end()

    if a.assert_round_end_wired:
        os.chdir(ROOT)
        return cmd_assert_round_end_wired()

    if a.assert_round_end_single:
        os.chdir(ROOT)
        return cmd_assert_round_end_single()

    if a.assert_no_dirty:
        os.chdir(ROOT)
        return cmd_assert_no_dirty()

    if a.assert_push_exclusive:
        os.chdir(ROOT)
        return cmd_assert_push_exclusive()

    if a.assert_blob_retry:
        os.chdir(ROOT)
        return cmd_assert_blob_retry()

    if a.assert_doc_round_closure:
        print()
        return cmd_assert_doc_round_closure()
    if a.assert_remote_rounds:
        os.chdir(ROOT)
        return cmd_assert_remote_rounds()

    if a.assert_push_exclusive_alive:
        os.chdir(ROOT)
        return cmd_assert_push_exclusive_alive()

    if a.mutation_scan:
        os.chdir(ROOT)
        return cmd_mutation_scan()

    if a.assert_mutation:
        os.chdir(ROOT)
        return cmd_assert_mutation()

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

    # 🔑 第一百二十九轮：**G421 本轮清单必须在推送前写**。
    #    🔴 真实事故：127 轮推送 08:07:59 完成，claims_127.txt 08:17:47 才写
    #       → 漏传；而 G390 当时是**绿的**（那一刻文件还不存在）。
    #    🔑 判据：G390 守"已存在但没 add"，本条守"还没写就推了" —— 互补。
    # 🔑 第一百三十九轮：**G429 推送必须互斥**。
    #    🔴 真实事故（本轮）：工具报 TimeoutError → 我判断"没启动"→ 又启两次
    #       → **三个推送进程同时存活**，都基于同一个 parent 建 commit，
    #         最后更新 ref 的胜出，另两个的工作**静默丢失且无人报错**。
    #    🔑 判据：判活查进程；查不到进程表时**拒绝给结论**，不当成"没有并发"。
    others = _other_pushers()
    if others is None:
        print('\n🔴 **无法确定**是否有其它推送进程在跑（读不到进程表）')
        print('  🔑 这与"没有并发"是两回事 —— 拒绝推送，不静默放行')
        return 1
    if others:
        print('\n🔴 检测到 %d 个**其它**推送进程仍在运行：%s'
              % (len(others), others[:8]))
        print('  🔑 并发推送会各自基于同一个 parent 建 commit —— '
              '最后更新 ref 的胜出，其余工作**静默丢失**')
        print('  🔑 判据：**命令超时 ≠ 命令没跑**；判活必须查进程')
        print('\n🔴 拒绝推送 —— 并发推送的失败是静默的')
        return 1

    if cmd_assert_round_claims() != 0:
        print('\n🔴 拒绝推送 —— 清单漏传会让"本轮做过什么"无法复核')
        return 1

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

    # 🔑 第一百三十七轮：**G427 推送前必须无未提交修改**。
    #    🔴 第一百三十六轮真实事故：只 `git add -A` 而**未本地 commit**，
    #       随后 `--audit-history` 又重写了台账与镜像 —— 索引里是旧内容，
    #       而推送读的是**工作区** → 远端与本地对不上（内容不一致 2 个）。
    #    🔑 G391 第⑤层只在**推送后**才发现；本条把它提前到**推送前拒绝**。
    if cmd_assert_no_dirty() != 0:
        print('\n🔴 拒绝推送 —— 推上去的将是工作区内容，而不是仓库里的版本')
        return 1

    # 🔑 G432：**推送消息必须含轮次**（第一百四十二轮）。
    #    🔴 41 轮实测：远端 59 个 commit 里 43 个消息是
    #       `同步（N 个文件）`，解析不出轮次 → 远端历史无法逐轮回溯。
    _rmsg_bad = _round_msg_bad(msg)
    if _rmsg_bad:
        print('\n🔴 推送消息校验未通过 —— 拒绝推送：')
        for _r in _rmsg_bad:
            print(f'   - {_r}')
        print('   🔑 处置：用 -m "第一百XX轮：..." 重新推送')
        sys.exit(1)

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

    # 🔑 第一百三十一轮：**轮次末尾回读接进推送主流程**。
    #    🔴 第一百三十轮诚实结论①：G423 只保证"入口没被拆"，
    #       保证不了"有人执行它" —— 129 轮 claims_127.txt 漏传正是如此。
    #    🔑 判据：**"能跑" ≠ "会跑"**；把这一步放在 `return 0` 之前，
    #       推送就不可能"没跑完这三项还报成功"。
    er = _run_round_end_steps()
    if er != 0:
        print('\n🔴 轮次末尾回读未通过 —— 本次推送**不算完成**')
        return er
    return 0


if __name__ == '__main__':
    sys.exit(main())
