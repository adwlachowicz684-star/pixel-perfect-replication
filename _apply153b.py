# -*- coding: utf-8 -*-
"""第一百五十三轮 b：给过短的豁免说明补上**常量自身特征**，并修正豁免条数下限。

🔴 判据④（说明最短长度）一上岗就抓到 11 条 —— 判据真在起作用。
🔑 说明必须带常量自身特征：否则「同一分类下说明雷同」判据形同虚设
   （PATH_ROOT 下会有 6 条一字不差的「仓库根目录」）。
"""
import os, re

ROOT = os.path.dirname(os.path.abspath(__file__))
PA = os.path.join(ROOT, 'scripts', 'push_api.py')

REPS = [
    ("'push_api.py::HERE': 'PATH_ROOT: 脚本目录本身，非产物或台账路径',",
     "'push_api.py::HERE': 'PATH_ROOT: push_api 所在脚本目录，非产物或台账路径',"),
    ("'push_api.py::ROOT': 'PATH_ROOT: 仓库根目录，非产物或台账路径',",
     "'push_api.py::ROOT': 'PATH_ROOT: push_api 解析出的仓库根，非产物或台账路径',"),
    ("'run_all_gates.py::HERE': 'PATH_ROOT: 脚本目录本身',",
     "'run_all_gates.py::HERE': 'PATH_ROOT: run_all_gates 所在脚本目录',"),
    ("'run_all_gates.py::REPO_ROOT': 'PATH_ROOT: 仓库根目录',",
     "'run_all_gates.py::REPO_ROOT': 'PATH_ROOT: run_all_gates 解析出的仓库根',"),
    ("'claim_verify.py::ROOT': 'PATH_ROOT: 仓库根目录',",
     "'claim_verify.py::ROOT': 'PATH_ROOT: claim_verify 解析出的仓库根',"),
    ("'gate_chaos.py::ROOT': 'PATH_ROOT: 仓库根目录',",
     "'gate_chaos.py::ROOT': 'PATH_ROOT: gate_chaos 解析出的仓库根',"),
    ("'_scan_cross_ref_consts.py::ROOT': 'PATH_ROOT: 仓库根目录',",
     "'_scan_cross_ref_consts.py::ROOT': 'PATH_ROOT: 交叉引用扫描脚本解析出的仓库根',"),
    ("'_scan_value_root_cands.py::HERE': 'PATH_ROOT: 脚本目录本身',",
     "'_scan_value_root_cands.py::HERE': 'PATH_ROOT: 取值根候选扫描脚本所在目录',"),
    ("'_scan_value_root_cands.py::ROOT': 'PATH_ROOT: 仓库根目录',",
     "'_scan_value_root_cands.py::ROOT': 'PATH_ROOT: 取值根候选扫描脚本解析出的仓库根',"),
    ("'gate_chaos.py::PY': 'PATH_ROOT: 解释器路径 sys.executable',",
     "'gate_chaos.py::PY': 'PATH_ROOT: gate_chaos 复用的解释器路径 sys.executable',"),
    ("'coverage_gate.py::ROW': 'OUTPUT_FMT: 表格行模板',",
     "'coverage_gate.py::ROW': 'OUTPUT_FMT: coverage_gate 的表格行模板',"),
    ("'license_gate.py::TEMPLATE': 'OUTPUT_FMT: 报告模板',",
     "'license_gate.py::TEMPLATE': 'OUTPUT_FMT: license_gate 的报告模板',"),
    ("'push_api.py::HDR': 'NET_CFG: 请求头模板',",
     "'push_api.py::HDR': 'NET_CFG: push_api 发 API 请求用的请求头模板',"),
    ("'gate_chaos.py::CAPABILITY_ANCHOR_FLOOR': 'PROBE_SPEC: 锚点下界表',",
     "'gate_chaos.py::CAPABILITY_ANCHOR_FLOOR': 'PROBE_SPEC: gate_chaos 的锚点下界表',"),
    ("'gate_chaos.py::FIXTURE_OVERRIDES': 'TYPE_ENUM: 夹具覆盖表',",
     "'gate_chaos.py::FIXTURE_OVERRIDES': 'TYPE_ENUM: gate_chaos 按夹具名覆盖取值',"),
    ("'gate_chaos.py::PLACEHOLDERS': 'TYPE_ENUM: 占位符表',",
     "'gate_chaos.py::PLACEHOLDERS': 'TYPE_ENUM: gate_chaos 文本替换用的占位符表',"),
]

src = open(PA, encoding='utf-8').read()
n = 0
for a, b in REPS:
    if a in src:
        src = src.replace(a, b, 1)
        n += 1
    else:
        print('[warn] 未找到：%s' % a[:60])
print('[ok] 说明补特征 %d/%d 条' % (n, len(REPS)))

# ── 豁免条数下限改用独立常量（CONST_SCAN_MIN 是**常量扫描数**下限，语义不同）──
if "CONST_SCAN_EXEMPT_MIN" not in src:
    a = "CONST_SCAN_EXEMPT_FN = '_scan_const_exempt_bad'\n"
    assert a in src
    src = src.replace(a, a + "CONST_SCAN_EXEMPT_MIN = 60        # 豁免条数下限（表被清空/缩小 → 拒绝给结论）\n", 1)
    src = src.replace("    'CONST_SCAN_EXEMPT_FN': ('const', 'G441 唯一实现函数名登记项'),\n",
                      "    'CONST_SCAN_EXEMPT_FN': ('const', 'G441 唯一实现函数名登记项'),\n"
                      "    'CONST_SCAN_EXEMPT_MIN': ('const', '豁免条数下限（G441 防清空）'),\n", 1)
    print('[ok] CONST_SCAN_EXEMPT_MIN 已加入并登记')

old = """    if scanned < (globals().get('CONST_SCAN_MIN') or 0):
        print(u'\\U0001f534 豁免仅 %d 条 < 下限 %d —— 疑似被清空，拒绝给结论'
              % (scanned, globals().get('CONST_SCAN_MIN') or 0))
        return 1"""
new = """    minx = globals().get('CONST_SCAN_EXEMPT_MIN') or 0
    if scanned < minx:
        print(u'\\U0001f534 豁免仅 %d 条 < 下限 %d —— 疑似被清空，拒绝给结论'
              % (scanned, minx))
        return 1"""
if old in src:
    src = src.replace(old, new, 1)
    print('[ok] 豁免下限改用 CONST_SCAN_EXEMPT_MIN')
else:
    print('[warn] 下限片段形态不同：%s' % ('已含 minx' if 'minx' in src else '未找到'))

open(PA, 'w', encoding='utf-8').write(src)
print('[done] push_api.py 已写入')
