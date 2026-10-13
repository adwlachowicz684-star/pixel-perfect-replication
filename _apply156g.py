"""第一百五十六轮：登记 G444 门禁项 + G443↔G444 互补层。"""
import ast
import io
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
RG = os.path.join(ROOT, 'scripts', 'run_all_gates.py')
BAK = os.path.join(ROOT, '_bak156_run_all_gates.py')


def rd(p):
    with io.open(p, encoding='utf-8') as f:
        return f.read()


def w_atomic(p, s):
    tmp = p + '.tmpg'
    with io.open(tmp, 'w', encoding='utf-8') as f:
        f.write(s)
    if rd(tmp) != s:
        os.remove(tmp)
        raise SystemExit('🔴 读回不一致: %s' % p)
    os.replace(tmp, p)


def main():
    src = rd(RG)
    if not os.path.exists(BAK):
        shutil.copy2(RG, BAK)
    out = src

    # ① 门禁项：插在 G441 条目之后（GATES 列表末尾）
    anchor = (
        "    (\"G441\", \"**豁免必须是结构化分类**（分类枚举外的值一律拒绝 · "
        "逐条说明可复核）\",\n"
        "     [\"{py}\", \"{s}/push_api.py\", \"--assert-const-exempt\"], \"hard\",\n"
        "     [\"scripts/push_api.py\"]),\n"
        "]"
    )
    if anchor not in out:
        raise SystemExit('🔴 找不到门禁项锚点')
    add = (
        "    (\"G441\", \"**豁免必须是结构化分类**（分类枚举外的值一律拒绝 · "
        "逐条说明可复核）\",\n"
        "     [\"{py}\", \"{s}/push_api.py\", \"--assert-const-exempt\"], \"hard\",\n"
        "     [\"scripts/push_api.py\"]),\n"
        "    # 🔑 第一百五十六轮：G444 —— **写环节反证必须逐环节各造一次**。\n"
        "    #    🔴 155 轮诚实结论② 点名的真实缺口：G443 的 ②/③/④ 三个反证\n"
        "    #       样本**都只造 git/trees 一个环节**，其余三个环节靠\n"
        "    #       「找不到」**间接**兜底 —— 扫描若退化成只认一个环节，\n"
        "    #       G443 仍 rc=0（本轮实测），而其余环节的裸 req 从此无人发现。\n"
        "    (\"G444\", \"**写环节反证必须逐环节各造一次**（不许只测一个环节）\",\n"
        "     [\"{py}\", \"{s}/push_api.py\", \"--assert-write-step-proof\"], \"hard\",\n"
        "     [\"scripts/push_api.py\"]),\n"
        "]"
    )
    out = out.replace(anchor, add, 1)
    print('① 门禁项已登记')

    # ② 互补层
    bl_anchor = (
        "    # 🔑 第一百四十五轮：第十五组（144 轮诚实结论③）\n"
    )
    if bl_anchor not in out:
        raise SystemExit('🔴 找不到互补层锚点')
    bl_add = (
        "    # 🔑 第一百五十六轮：G443 ↔ G444 —— 反证的「准」与「全」必须互补。\n"
        "    ('G443', 'G444',\n"
        "     'G443 验「反证样本这一**形态**能不能被识破」（一处对了不得掩盖另一处裸 req）；'\n"
        "     'G444 验「反证是不是**每个环节都造了一次**」（只测一个环节 = 其余交给运气）。'\n"
        "     '\\U0001f534 只留 G443 → 扫描退化成只认 git/trees 后它 rc=0 放行（156 轮实测①），'\n"
        "     '而 blobs/commits/refs 三处裸 req 从此无人发现；'\n"
        "     '只留 G444 → 缺少「一处对了就放行」这一形态的守望者（154 轮判据② 的洞）。'\n"
        "     '\\U0001f511 「反证准不准」与「反证覆盖全不全」是两件事，缺一则该环节等于没守护。'),\n"
        + bl_anchor
    )
    out = out.replace(bl_anchor, bl_add, 1)
    print('② 互补层已登记')

    try:
        ast.parse(out)
    except SyntaxError as e:
        raise SystemExit('🔴 语法失败: %s' % e)
    w_atomic(RG, out)
    print('✅ apply156_gates 完成')


if __name__ == '__main__':
    main()
