# -*- coding: utf-8 -*-
"""第一百五十三轮：把 85 条「统一理由」豁免 → 结构化分类（G441）。

🔴 152 轮诚实结论②：85 条豁免是本轮**批量生成、理由统一**
   —— 实测 75 条理由完全相同 + 10 条另一个理由完全相同。
   🔑 统一理由 = 无法区分「真不该登记」与「随手豁免的」→ G440 的实际约束力
      只取决于「谁在写豁免表」，而不是「该不该」。
"""
import io, os, re, sys

ROOT = os.path.dirname(os.path.abspath(__file__))
PA = os.path.join(ROOT, 'scripts', 'push_api.py')

CATS = {
    'PATH_ROOT': '指向仓库或脚本目录自身的路径根常量；它不指向产物或台账，因此不适用「产物路径必须登记」的语义。',
    'NET_CFG': '远端访问配置与凭据（属主、仓库名、令牌、端点、请求头）；属于运行环境变量，不是代码内的被依赖名字。',
    'META_TABLE': '元表自身或其键集合；G440 的登记表与豁免表由它构成，让它自己登记自己会形成自证循环。',
    'SCAN_TUNING': '扫描器的阈值、容差与条数配置（调参型数值）；改动影响的是灵敏度而非「某个名字是否仍被登记」。',
    'SELFTEST_CFG': '自检与自测的运行配置（临时目录、进程特征、开关 flag）；只在自测路径上生效。',
    'TYPE_ENUM': '类型或状态的取值域集合（枚举与映射表）；它是取值集合而不是依赖名，逐条登记无意义。',
    'FN_IDENT': '以字符串形式引用的函数或命令标识；AST 里不是 Name 节点，G440 的引用判据天然数不到。',
    'PROBE_SPEC': '能力探针的规格数据（命令、产物名、读数键路径、锚点规格）；属探针配置而非依赖登记项。',
    'OUTPUT_FMT': '输出排版用的模板与字段清单；仅影响打印格式。',
}

# 🔑 逐条人工确认（85 条）—— 每条给出**该常量自己的**说明
ALLOW = {
'push_api.py::HERE': ('PATH_ROOT', '脚本目录本身，非产物或台账路径'),
'push_api.py::ROOT': ('PATH_ROOT', '仓库根目录，非产物或台账路径'),
'push_api.py::BASELINE_FP_HISTORY_MAX': ('SCAN_TUNING', '变更史保留条数上限'),
'push_api.py::CONST_SCAN_ALLOW': ('META_TABLE', 'G440 的豁免表自身，不能自己登记自己'),
'push_api.py::CONST_SCAN_ALLOW_MIN_REASON': ('SCAN_TUNING', '豁免理由最短长度阈值'),
'push_api.py::LEGACY_SAMPLE_N': ('SCAN_TUNING', '历史遗留条目抽样条数'),
'push_api.py::LEGACY_SHOW_N': ('SCAN_TUNING', '历史遗留条目展示条数'),
'push_api.py::OWNER': ('NET_CFG', 'GitHub 仓库属主'),
'push_api.py::REPO': ('NET_CFG', 'GitHub 仓库名'),
'push_api.py::TOK': ('NET_CFG', '访问令牌，属凭据不是依赖名'),
'push_api.py::API': ('NET_CFG', 'GitHub API 根地址'),
'push_api.py::HDR': ('NET_CFG', '请求头模板'),
'push_api.py::CLEANUP_CALLS': ('SELFTEST_CFG', '清理类调用的方法名集合，G413 的扫描面'),
'push_api.py::CLEANUP_VERIFY_FNS': ('SELFTEST_CFG', '校验类函数名集合，G413 判「是否带校验」'),
'push_api.py::CLEANUP_SCAN_MIN': ('SCAN_TUNING', '清理调用扫描数下限'),
'push_api.py::SELFTEST_TMP_DIR': ('SELFTEST_CFG', '自测临时目录名，G410/G411 依赖'),
'push_api.py::ROUND_END_STEPS': ('META_TABLE', '轮次末尾步骤表，G423/G424 依赖'),
'push_api.py::ROUND_END_REQUIRED_GIDS': ('META_TABLE', '轮次末尾必需的门禁编号集合'),
'push_api.py::MUTATION_TARGET_MIN': ('SELFTEST_CFG', '变异目标数下限'),
'push_api.py::MUTATION_SELF_EXCLUDE': ('SELFTEST_CFG', '变异扫描排除自身的文件名'),
'push_api.py::PUSH_LOCK_ARGS': ('SELFTEST_CFG', '推送互斥识别用的参数特征'),
'push_api.py::PUSH_EXCLUSIVE_NAMES': ('SELFTEST_CFG', '推送互斥进程名特征，G429 依赖'),
'push_api.py::DOC_ROUND_SKIP_PARTS': ('SCAN_TUNING', '文档轮次解析要跳过的路径片段'),
'push_api.py::NOTATION_SAMPLES_MIN': ('SCAN_TUNING', '写法反证样本数下限，G434 依赖'),
'run_all_gates.py::HERE': ('PATH_ROOT', '脚本目录本身'),
'run_all_gates.py::REPO_ROOT': ('PATH_ROOT', '仓库根目录'),
'run_all_gates.py::LEGAL_GATES': ('META_TABLE', '合法门禁编号全集'),
'run_all_gates.py::DUP_CMDS_GUARDIAN': ('FN_IDENT', '查重命令的 argv 特征'),
'run_all_gates.py::INTENTIONAL_DUP_CMDS': ('META_TABLE', '允许重复的（命令,门禁）对'),
'run_all_gates.py::GATES': ('META_TABLE', '门禁注册表自身'),
'run_all_gates.py::BOTH_LAYERS': ('META_TABLE', '互补层登记表自身'),
'run_all_gates.py::MANUAL_GATES': ('META_TABLE', '人工门禁编号集合'),
'claim_verify.py::ROOT': ('PATH_ROOT', '仓库根目录'),
'claim_verify.py::DEFAULT_REQUIRE_SINCE': ('SCAN_TUNING', '逐轮要求默认起始轮'),
'claim_verify.py::DECLARED_CAPABILITIES': ('META_TABLE', '能力声明表自身'),
'claim_verify.py::CAPABILITY_PROBE': ('PROBE_SPEC', '能力探针命令表'),
'claim_verify.py::CAPABILITY_EFFECT': ('PROBE_SPEC', '能力探针的效应描述'),
'claim_verify.py::CAPABILITY_ARTIFACT': ('PROBE_SPEC', '能力探针产物文件名'),
'claim_verify.py::CAPABILITY_ARTIFACT_KEYS': ('PROBE_SPEC', '能力产物里读数的键路径'),
'claim_verify.py::GATE_RC_DOMAIN': ('META_TABLE', '门禁退出码域定义'),
'claim_verify.py::CAPABILITY_ANCHOR_SPEC': ('PROBE_SPEC', '锚点规格，下界来源'),
'claim_verify.py::ALL_CONTENT': ('META_TABLE', '全内容守卫名'),
'claim_verify.py::ALL_CONTENT_FN': ('FN_IDENT', '全内容守卫的函数名，字符串引用'),
'claim_verify.py::ALLOWLIST_FILES': ('META_TABLE', '允许清单目录'),
'claim_verify.py::NO_ARTIFACT_FLAG': ('SELFTEST_CFG', '无产物对照开关，命令行 flag'),
'claim_verify.py::NO_ART_ARTIFACT_FN': ('FN_IDENT', '无产物时的产物读取函数名'),
'claim_verify.py::NO_ART_TRUTH_FN': ('FN_IDENT', '无产物时的真值函数名'),
'gate_chaos.py::PY': ('PATH_ROOT', '解释器路径 sys.executable'),
'gate_chaos.py::ROOT': ('PATH_ROOT', '仓库根目录'),
'gate_chaos.py::DECLARED_CAPABILITIES': ('META_TABLE', '能力声明表自身'),
'gate_chaos.py::CAPABILITY_PROBE': ('PROBE_SPEC', '能力探针命令表'),
'gate_chaos.py::CAPABILITY_ARTIFACT': ('PROBE_SPEC', '能力探针产物文件名'),
'gate_chaos.py::CAPABILITY_ARTIFACT_KEYS': ('PROBE_SPEC', '能力产物里读数的键路径'),
'gate_chaos.py::CAPABILITY_ANCHOR_FLOOR': ('PROBE_SPEC', '锚点下界表'),
'gate_chaos.py::CHAOS_BASELINE_FILE': ('META_TABLE', '基线文件名，台账路径另归 G406'),
'gate_chaos.py::CHAOS_BASELINE_TOLERANCE': ('SCAN_TUNING', '基线容差，G415 依赖'),
'gate_chaos.py::CHAOS_ARTIFACT_FULL_RATIO': ('SCAN_TUNING', '全量比率，G415 判「是否全量」'),
'gate_chaos.py::CHAOS_DENOM_TOLERANCE': ('SCAN_TUNING', '分母容差，G417 依赖'),
'gate_chaos.py::TYPE_RULES': ('TYPE_ENUM', '类型到规则的映射'),
'gate_chaos.py::ASSERTABLE': ('TYPE_ENUM', '可断言类型集合'),
'gate_chaos.py::SEMANTIC': ('TYPE_ENUM', '语义型类型集合'),
'gate_chaos.py::POISON': ('TYPE_ENUM', '破坏注入类型集合'),
'gate_chaos.py::INTERFACE_ADAPTERS': ('TYPE_ENUM', '接口适配器表'),
'gate_chaos.py::VALID_OVERRIDE': ('TYPE_ENUM', '合法覆盖值集合'),
'gate_chaos.py::TEXT_REPLACEMENTS': ('TYPE_ENUM', '文本替换规则'),
'gate_chaos.py::PLACEHOLDERS': ('TYPE_ENUM', '占位符表'),
'gate_chaos.py::VALID_BY_TYPE': ('TYPE_ENUM', '按类型的合法值集合'),
'gate_chaos.py::FIXTURE_OVERRIDES': ('TYPE_ENUM', '夹具覆盖表'),
'gate_chaos.py::COMPLETENESS': ('TYPE_ENUM', '完备性检查名'),
'gate_chaos.py::CATALOG_KW': ('SCAN_TUNING', '目录关键词，判断是否目录型'),
'gate_chaos.py::NOT_CATALOG': ('SCAN_TUNING', '非目录关键词'),
'coverage_gate.py::UNKNOWN_ANY': ('TYPE_ENUM', '覆盖率未知标记'),
'coverage_gate.py::ROW': ('OUTPUT_FMT', '表格行模板'),
'license_gate.py::ALLOWED': ('TYPE_ENUM', '许可状态-允许'),
'license_gate.py::RESTRICTED': ('TYPE_ENUM', '许可状态-受限'),
'license_gate.py::UNKNOWN': ('TYPE_ENUM', '许可状态-未知'),
'license_gate.py::NOT_APP': ('TYPE_ENUM', '许可状态-不适用'),
'license_gate.py::BLOCKING': ('TYPE_ENUM', '阻断级别集合'),
'license_gate.py::STATUS_HELP': ('OUTPUT_FMT', '状态说明文本表'),
'license_gate.py::FONT_FIELDS': ('OUTPUT_FMT', '字体字段清单'),
'license_gate.py::BOM_TOOLS': ('OUTPUT_FMT', '物料工具清单'),
'license_gate.py::TEMPLATE': ('OUTPUT_FMT', '报告模板'),
'_scan_cross_ref_consts.py::ROOT': ('PATH_ROOT', '仓库根目录'),
'_scan_value_root_cands.py::HERE': ('PATH_ROOT', '脚本目录本身'),
'_scan_value_root_cands.py::ROOT': ('PATH_ROOT', '仓库根目录'),
}

src = open(PA, encoding='utf-8').read()

# ── 1) 替换 CONST_SCAN_ALLOW 整块 ──────────────────────────────────
m = re.search(r'^CONST_SCAN_ALLOW = \{.*?^\}', src, re.S | re.M)
assert m, 'CONST_SCAN_ALLOW 未找到'
old_items = re.findall(r"^\s*'([^']+)':\s*'[^']*',\s*$", m.group(0), re.M)
assert set(old_items) == set(ALLOW), (
    '豁免键不一致：多 %s 少 %s' % (sorted(set(ALLOW) - set(old_items)),
                                  sorted(set(old_items) - set(ALLOW))))

lines = []
lines.append('CONST_SCAN_ALLOW = {')
lines.append('    # \U0001f511 第一百五十三轮：**逐条人工确认**（152 轮批量生成的统一理由已作废）。')
lines.append('    #    \U0001f534 152 轮实测：85 条里 75 条理由**完全相同** —— 无法区分')
lines.append('    #       「真不该登记」与「随手豁免的」，G440 的约束力只取决于谁在写这张表。')
lines.append('    #    \U0001f511 值格式改为「分类: 该常量自己的说明」，分类取自 CONST_SCAN_CATEGORIES。')
for k in sorted(ALLOW):
    cat, det = ALLOW[k]
    lines.append("    '%s': '%s: %s'," % (k, cat, det))
lines.append('}')
src = src[:m.start()] + '\n'.join(lines) + src[m.end():]
print('[ok] CONST_SCAN_ALLOW 重写 %d 条' % len(ALLOW))

# ── 2) 插入 CONST_SCAN_CATEGORIES 等常量（放在 CONST_SCAN_ALLOW_MIN_REASON 之后）──
anchor = 'CONST_SCAN_ALLOW_MIN_REASON = 6\n'
assert anchor in src
clines = []
clines.append(anchor)
clines.append('')
clines.append('# \U0001f511 第一百五十三轮：G441 —— 豁免必须是**结构化分类**，「为什么不该登记」才可复核。')
clines.append('#    \U0001f534 自由文本理由 → 任何常量都能用同一句话豁免（152 轮实测 75 条同文本）。')
clines.append('#    \U0001f511 分类是**枚举**：分类表外的值一律拒绝，分类定义必须写明适用范围。')
clines.append('CONST_SCAN_CATEGORIES = {')
for k in sorted(CATS):
    clines.append("    '%s': '%s'," % (k, CATS[k]))
clines.append('}')
clines.append('CONST_SCAN_CAT_MIN = 6            # 分类数下限（表被清空 → 拒绝给结论）')
clines.append('CONST_SCAN_CATDEF_MIN = 20        # 每个分类的**定义**最短长度（防「同上」）')
clines.append('CONST_SCAN_DETAIL_MIN = 6         # 每条豁免的**具体说明**最短长度')
clines.append('CONST_SCAN_SAME_DETAIL_MAX = 2    # 同一分类下说明完全相同的条目数上限（批量指纹）')
clines.append("CONST_SCAN_EXEMPT_FN = '_scan_const_exempt_bad'")
clines.append('CONST_SCAN_EXEMPT_MIN = 60        # 豁免条数下限（表被清空/缩小 → 拒绝给结论）')
clines.append('')   # 🔴 join 会吞掉尾部换行 —— 补一个空元素
assert src.count('CONST_SCAN_EXEMPT_FN') == 0
src = src.replace(anchor, '\n'.join(clines), 1)
print('[ok] CONST_SCAN_CATEGORIES 等常量已插入')

# ── 3) 新实现 + 入口（放在 cmd_assert_const_covered 之后）────────────
anchor2 = 'def cmd_assert_const_covered():'
assert anchor2 in src

IMPL = '''def _scan_const_exempt_bad():
    """\U0001f511 G441 **唯一实现**：豁免必须是**结构化分类**，而非自由文本。

    \U0001f534 152 轮诚实结论②：85 条豁免**批量生成、理由统一**
       （实测 75 条文本完全相同 + 10 条另一文本完全相同）。
       \U0001f511 统一理由 = 分不清「真不该登记」与「随手豁免的」——
          于是 G440 的约束力只取决于「谁在写这张表」，而不是「该不该」。
    \U0001f511 本函数把豁免收敛成**枚举分类**：分类表外的值一律拒绝，
       分类定义必须写明适用范围，同分类下说明雷同超过上限即判「批量生成」。
    """
    cats = globals().get('CONST_SCAN_CATEGORIES')
    if not cats:
        return None, 'CONST_SCAN_CATEGORIES 未登记或为空 —— 拒绝给结论'
    mincat = globals().get('CONST_SCAN_CAT_MIN') or 0
    if len(cats) < mincat:
        return None, ('分类数 %d < 下限 %d —— 疑似被清空，拒绝给结论'
                      % (len(cats), mincat))
    mindef = globals().get('CONST_SCAN_CATDEF_MIN') or 0
    mindet = globals().get('CONST_SCAN_DETAIL_MIN') or 0
    maxsame = globals().get('CONST_SCAN_SAME_DETAIL_MAX') or 0
    allow = globals().get('CONST_SCAN_ALLOW') or {}
    if not allow:
        return None, 'CONST_SCAN_ALLOW 未登记或为空 —— 拒绝给结论'
    bad = []
    seen = {}
    for k in sorted(allow):
        v = allow[k]
        if not isinstance(v, str) or ':' not in v:
            bad.append((k, '豁免值缺少「分类: 说明」前缀 —— 自由文本一律拒绝'))
            continue
        cat, _, detail = v.partition(':')
        cat = cat.strip()
        detail = detail.strip()
        if cat not in cats:
            bad.append((k, '分类「%s」未在 CONST_SCAN_CATEGORIES 中定义' % cat))
            continue
        if len(cats[cat] or '') < mindef:
            bad.append((k, '分类「%s」的定义过短（<%d）' % (cat, mindef)))
            continue
        if len(detail) < mindet:
            bad.append((k, '具体说明过短（<%d）—— 无法复核「为什么不该登记」' % mindet))
            continue
        seen.setdefault((cat, detail), []).append(k)
    for (cat, detail), ks in sorted(seen.items()):
        if len(ks) > maxsame:
            bad.append((ks[0], '分类「%s」下说明完全相同的条目 %d 条 > 上限 %d'
                        ' —— 疑似批量生成，非逐条确认' % (cat, len(ks), maxsame)))
    return bad, len(allow)


def cmd_assert_const_exempt_covered():
    """\U0001f511 G441：**豁免必须是结构化分类**（152 轮诚实结论② 的补偿）。"""
    print(u'\\U0001f511 **豁免结构化分类**（G441 · 152 轮诚实结论② 的补偿）')
    fn = globals().get('CONST_SCAN_EXEMPT_FN')
    if not fn:
        print(u'\\U0001f534 CONST_SCAN_EXEMPT_FN 未登记 —— 拒绝给结论')
        return 1
    impl = globals().get(fn)
    if impl is None:
        print(u'\\U0001f534 %s 不存在 —— 拒绝给结论' % fn)
        return 1
    bad, scanned = impl()
    if bad is None:
        print(u'\\U0001f534 %s' % scanned)
        return 1
    if scanned < (globals().get('CONST_SCAN_MIN') or 0):
        print(u'\\U0001f534 豁免仅 %d 条 < 下限 %d —— 疑似被清空，拒绝给结论'
              % (scanned, globals().get('CONST_SCAN_MIN') or 0))
        return 1
    # \U0001f511 行为反证：注入一条「未定义分类」的豁免，实现**必须**报出来
    #    \U0001f534 否则判据② 可能恒真（106 轮「缺失被当成没有违规」同病）。
    save = globals().get('CONST_SCAN_ALLOW')
    try:
        injected = dict(save or {})
        injected['_probe_bogus.py::BOGUS_CONST'] = 'BOGUS_CAT_NOT_DEFINED: 反证注入'
        globals()['CONST_SCAN_ALLOW'] = injected
        bad2, _n2 = impl()
        hit = bool(bad2) and any('BOGUS_CAT_NOT_DEFINED' in (b[1] if len(b) > 1 else '')
                                 for b in (bad2 or []))
    finally:
        globals()['CONST_SCAN_ALLOW'] = save
    if not hit:
        print(u'\\U0001f534 反证失效：注入「未定义分类」的豁免后未报出 —— 判据恒真')
        return 1
    if bad:
        for k, why in bad:
            print(u'   \\U0001f534 %s —— %s' % (k, why))
        print(u'\\U0001f534 守卫失效（G441）：%d 条豁免不合格' % len(bad))
        return 1
    print(u'   \\u2705 %d 条豁免全部为已定义分类，逐条说明可复核（反证已验）' % scanned)
    return 0


'''
src = src.replace(anchor2, IMPL + anchor2, 1)
print('[ok] _scan_const_exempt_bad + cmd_assert_const_exempt_covered 已插入')

# ── 4) DEPENDENT_NAMES 登记 ───────────────────────────────────────
anchor3 = "    'cmd_assert_const_covered': ('fn', 'G440 非路径常量反向扫描的断言入口'),\n"
assert anchor3 in src
dep = anchor3 + \
    "    # \U0001f511 第一百五十三轮：G441（豁免结构化分类）依赖\n" + \
    "    'CONST_SCAN_CATEGORIES': ('const', '豁免分类枚举表（G441 依赖）'),\n" + \
    "    'CONST_SCAN_CAT_MIN': ('const', '分类数下限（G441 防清空）'),\n" + \
    "    'CONST_SCAN_CATDEF_MIN': ('const', '分类定义最短长度（G441 依赖）'),\n" + \
    "    'CONST_SCAN_DETAIL_MIN': ('const', '豁免说明最短长度（G441 依赖）'),\n" + \
    "    'CONST_SCAN_SAME_DETAIL_MAX': ('const', '同分类下说明雷同上限（G441 依赖）'),\n" + \
    "    'CONST_SCAN_EXEMPT_FN': ('const', 'G441 唯一实现函数名登记项'),\n" + \
    "    '_scan_const_exempt_bad': ('fn', 'G441 豁免结构化分类的唯一实现'),\n" + \
    "    'cmd_assert_const_exempt_covered': ('fn', 'G441 豁免结构化分类的断言入口'),\n"
src = src.replace(anchor3, dep, 1)
print('[ok] DEPENDENT_NAMES 登记完成')

# ── 5) argparse ───────────────────────────────────────────────────
anchor4 = "    ap.add_argument('--assert-const-covered', action='store_true',"
assert anchor4 in src
i = src.index(anchor4)
j = src.index('\n', src.index('\n', i) + 1)
# 找到该 add_argument 结束（下一行以 ap.add_argument 或非缩进行开头）
k = i
while True:
    nk = src.index('\n', k) + 1
    nxt = src[nk:nk + 40]
    if nxt.strip() == '' or nxt.startswith('    ap.') or nxt.startswith('    args'):
        k = nk
        if nxt.startswith('    ap.') or nxt.startswith('    args'):
            break
        continue
    break
ins = ("    ap.add_argument('--assert-const-exempt', action='store_true',\n"
       "                    help='G441 豁免必须是结构化分类（152 轮统一理由的补偿）')\n")
src = src[:k] + ins + src[k:]
print('[ok] argparse 已加 --assert-const-exempt')

# ── 6) 命令分发 ───────────────────────────────────────────────────
anchor5 = "assert-const-covered"
i5 = src.index(anchor5)
seg = src[i5 - 400:i5 + 400]
mm = re.search(r"if\s+(?:getattr\(args,\s*'[a-z_]+'|args\.[a-z_]+)\s*:\s*\n\s*return\s+cmd_assert_const_covered\(\)", src)
if mm is None:
    mm2 = re.search(r"( *)return cmd_assert_const_covered\(\)", src)
    assert mm2, '未找到 G440 分发处'
    ind = mm2.group(1)
    ind2 = ind[:-4] if len(ind) >= 4 else ind   # 🔴 return 的缩进比 if 深 4 —— 必须退一级
    src = (src[:mm2.start()]
           + "%sif getattr(a, 'assert_const_exempt', False):\n%s    return cmd_assert_const_exempt_covered()\n%s"
             % (ind2, ind2, ind)
           + src[mm2.start():])
    print('[ok] 分发已插入（elif 形式，缩进 %d）' % len(ind))
else:
    print('[warn] 分发结构不同，需手工确认')

open(PA, 'w', encoding='utf-8').write(src)
print('[done] push_api.py 已写入')
