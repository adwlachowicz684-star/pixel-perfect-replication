"""第一百五十六轮：文档记录。🔴 原子追加 + 读回核对。"""
import io
import os

ROOT = os.path.dirname(os.path.abspath(__file__))

README_ADD = """
🔑 第一百五十六轮：G444 —— **写环节反证必须逐环节各造一次**（155 轮诚实结论② 的真实缺口）。
   🔴 155 轮 G443 的 ②/③/④ 三个反证样本**都只造 git/trees 一个环节**，其余三个环节（blobs / commits / refs）靠「找不到」**间接**兜底 —— 扫描若退化成只对那一个环节生效，其余环节的裸 req 从此无人发现。
   ✅ 新增唯一实现 `_write_proof_check`：对**每一个**写环节各造 A/B/C 三种形态（同一环节 req_retry + 裸 req 并存 / GET 走 req_retry + 写方法却是裸 req / 只有 GET 无写调用），逐环节**独立**判定；形态数下限**真查**（148 轮"声称与实现不符"同款，声明常量不算数）。
   🔑 对照实验①（同一状态：`_write_step_scan` 退化成只认 git/trees）：**G443 rc=0 放行** · G444 rc=1 🔴 —— G443 真的看不见，不是推演。
   🔑 内嵌对照（判据⑤，常驻门禁内部）：同一个退化实现在 G443 口径下 A/B/C **全部命中**，在 G444 逐环节口径下覆盖 1/4、未命中 6 条 —— 一绿一红不用等下一轮做对照实验。
   🔴 破坏④ 实测：把对照点 `WRITE_LEGACY_PROOF_SEG` 改成不存在的环节 → 内嵌对照不成立即**拒绝给结论**（防"对照点漂移后判据⑤ 形同虚设"）。
   🔑 七方向破坏全部符合预期：①只认一个环节 G443=0/**G444=1**（核心对照）· ②恒空桩 均=1 · ③清单缩到 1 条 G444=1 · ④对照点漂移 G444=1 · ⑤桩化唯一实现 G444=1 · ⑥一致改名 G444=0 不误报 · ⑦形态缩到 1 种 G444=1。恢复后 md5 一致。
"""

LESSON_ADD = """
---

## 七、反证类陷阱

| 陷阱 | 后果 |
|---|---|
| 🔑 反证样本只造**一个**样本点（156 轮实证） | G443 的三个反证都用同一个环节，扫描退化成"只对那个环节生效"后 G443 依旧全绿 —— **反证覆盖不到 == 没守护**，其余三个环节的裸 req 从此无人发现 |
| 只声明"形态数下限"常量而不真查 | 样本被缩水照样通过（156 轮破坏⑦：声明了 `WRITE_PROOF_KIND_MIN` 却没在实现里用） |
| 对照实验只在写门禁的那一轮做一次 | 之后实现退化无人再验；应把"退化实现在旧口径下全绿"做成**常驻**的内嵌对照判据 |
| 对照点硬编码而无人核对 | 旧门禁换了样本点后，内嵌对照的"一绿一红"关系漂移，形同虚设 |

🔑 **判据**：反证样本必须按被守护对象**参数化生成、逐个各造一次**（151 轮"逐条各造一次篡改"同款，156 轮推广到**环节**维度），并常驻一个"退化实现在该样本点上全绿"的内嵌对照。
"""


def rd(p):
    with io.open(p, encoding='utf-8') as f:
        return f.read()


def w_atomic(p, s):
    tmp = p + '.tmpd'
    with io.open(tmp, 'w', encoding='utf-8') as f:
        f.write(s)
    if rd(tmp) != s:
        os.remove(tmp)
        raise SystemExit('🔴 读回不一致: %s' % p)
    os.replace(tmp, p)


def main():
    rp = os.path.join(ROOT, 'README.md')
    s = rd(rp)
    if '第一百五十六轮' in s:
        raise SystemExit('🔴 README 已有 156 轮记录')
    w_atomic(rp, s.rstrip() + '\n' + README_ADD)
    print('README 已追加')

    lp = os.path.join(ROOT, 'references', '负面教训库.md')
    s2 = rd(lp)
    if '反证样本只造' in s2:
        raise SystemExit('🔴 教训库已有该条')
    w_atomic(lp, s2.rstrip() + '\n' + LESSON_ADD)
    print('教训库已追加')
    print('✅ doc156 完成')


if __name__ == '__main__':
    main()
