"""第一百五十六轮：插入 G444（写环节反证必须逐环节各造一次）。

🔴 吸取 144 / 155 轮教训：
   a) 写入用**原子写**（临时文件 → 读回核对 → os.replace）
   b) 写回后立刻 `ast.parse` 语法检查
   c) 每步打印 diff 行数，失败即非零退出
"""
import ast
import io
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
API = os.path.join(ROOT, 'scripts', 'push_api.py')
BODY = os.path.join(ROOT, '_g444_body.py')
BAK = os.path.join(ROOT, '_bak156_push_api.py')


def rd(p):
    with io.open(p, encoding='utf-8') as f:
        return f.read()


def atomic_write(p, s):
    tmp = p + '.tmp156'
    with io.open(tmp, 'w', encoding='utf-8') as f:
        f.write(s)
    back = rd(tmp)          # 🔑 写完立刻读回核对（136 轮）
    if back != s:
        os.remove(tmp)
        raise SystemExit('🔴 读回不一致：%s' % p)
    os.replace(tmp, p)
    return len(s)


def main():
    src = rd(API)
    body = rd(BODY)
    if not os.path.exists(BAK):
        shutil.copy2(API, BAK)
    print('备份已建立:', BAK)

    out = src

    # ① 插入 G444 实现：放在 `def cmd_assert_blob_retry():` 之前
    anchor = 'def cmd_assert_blob_retry():'
    if anchor not in out:
        raise SystemExit('🔴 找不到插入锚点: ' + anchor)
    if 'def cmd_assert_write_step_proof():' in out:
        raise SystemExit('🔴 G444 已存在，拒绝重复插入')
    out = out.replace(anchor, body.rstrip() + '\n\n\n' + anchor, 1)
    print('① 实现已插入')

    # ② 登记依赖
    dep_anchor = "    'cmd_assert_write_step_scan': ('fn', 'G443 写环节扫描的断言入口'),\n"
    if dep_anchor not in out:
        raise SystemExit('🔴 找不到登记锚点')
    dep_add = (
        dep_anchor
        + "    # 🔑 第一百五十六轮：G444（反证逐环节覆盖）依赖\n"
        + "    'WRITE_PROOF_SEG_MIN': ('const', '反证必须覆盖的环节数下限（G444）'),\n"
        + "    'WRITE_PROOF_KIND_MIN': ('const', '每环节反证形态数下限（G444）'),\n"
        + "    'WRITE_LEGACY_PROOF_SEG': ('const', 'G443 反证所用环节（G444 退化对照点）'),\n"
        + "    'WRITE_PROOF_FN': ('const', 'G444 判据① 依赖：唯一实现的函数名'),\n"
        + "    '_write_proof_check': ('fn', 'G444 唯一实现：逐环节各造反证样本'),\n"
        + "    'cmd_assert_write_step_proof': ('fn', 'G444 反证逐环节覆盖的断言入口'),\n"
    )
    out = out.replace(dep_anchor, dep_add, 1)
    print('② 依赖已登记')

    # ③ argparse
    arg_anchor = (
        "    ap.add_argument('--assert-blob-retry', action='store_true',\n"
    )
    if arg_anchor not in out:
        raise SystemExit('🔴 找不到 argparse 锚点')
    arg_add = (
        "    ap.add_argument('--assert-write-step-proof', action='store_true',\n"
        "                    help='G444：写环节反证必须**逐环节各造一次**'\n"
        "                         '（155 轮：只测一个环节 = 其余交给运气）')\n"
        + arg_anchor
    )
    out = out.replace(arg_anchor, arg_add, 1)
    print('③ argparse 已加')

    # ④ dispatch
    disp_anchor = "    if a.assert_write_step_scan:\n        return cmd_assert_write_step_scan()\n"
    if disp_anchor not in out:
        raise SystemExit('🔴 找不到 dispatch 锚点')
    disp_add = (
        disp_anchor
        + "    if a.assert_write_step_proof:\n"
        + "        return cmd_assert_write_step_proof()\n"
    )
    out = out.replace(disp_anchor, disp_add, 1)
    print('④ dispatch 已加')

    # 🔑 语法检查（先于落盘）
    try:
        ast.parse(out)
    except SyntaxError as e:
        raise SystemExit('🔴 语法检查失败: %s' % e)

    n = atomic_write(API, out)
    print('⑤ 已原子写入 %s（%d 字符）' % (API, n))
    print('✅ apply156 完成')


if __name__ == '__main__':
    main()
