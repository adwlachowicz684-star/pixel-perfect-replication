# -*- coding: utf-8 -*-
"""第一百五十七轮：文档同步（README + 负面教训库）。

🔑 144 轮教训第三次：needle 必须落在**正文行**，`#` 开头的标题行会被判为说明行。
"""
import hashlib
import io
import os

HERE = os.path.dirname(os.path.abspath(__file__))
RM = os.path.join(HERE, 'README.md')
RL = os.path.join(HERE, 'references', '负面教训库.md')


def md5(p):
    return hashlib.md5(io.open(p, 'rb').read()).hexdigest()


def w(p, s):
    tmp = p + '.tmp157'
    with io.open(tmp, 'w', encoding='utf-8') as f:
        f.write(s)
    if io.open(tmp, encoding='utf-8').read() != s:
        raise SystemExit('🔴 写回不一致: ' + p)
    os.replace(tmp, p)


# ── README ──
rm = io.open(RM, encoding='utf-8').read()
ANCHOR = ('   🔑 七方向破坏全部符合预期：①只认一个环节 G443=0/**G444=1**（核心对照）· '
          '②恒空桩 均=1 · ③清单缩到 1 条 G444=1 · ④对照点漂移 G444=1 · '
          '⑤桩化唯一实现 G444=1 · ⑥一致改名 G444=0 不误报 · ⑦形态缩到 1 种 G444=1。恢复后 md5 一致。\n')
assert rm.count(ANCHOR) == 1, 'README anchor'

ADD = ANCHOR + """
🔑 第一百五十七轮：G445 —— **写环节反证必须覆盖「不认 URL / 认错环节」这一形态**（156 轮诚实结论② 的真实缺口）。
   🔴 156 轮 G444 的 A/B/C 三形态样本，URL **都含当前环节** → 于是"扫描是否真的按 URL 区分环节"从未被检验。
   ✅ 新增唯一实现 `_write_proof_url_check`：对**每一个**写环节各造一个「只有与本环节无关的写 URL」的样本（`WRITE_PROOF_FOREIGN_URL`），期望该环节被判「找不到」。
   🔑 对照实验①（同一状态：`_write_step_scan` 退化成只按 HTTP 方法匹配、完全不看 URL）：**G443 rc=0 放行** · **G444 rc=0 放行** · G445 rc=1 🔴 —— 两绿一红，不是推演。
   🔑 内嵌对照（判据⑤，常驻门禁内部）：同一退化实现在 G444 口径下覆盖 4/4、未命中 0（**全绿**），在 G445 无关 URL 口径下覆盖 0/4、未命中 4。
   🔴 该退化的危害：只要源码里还有**任何一个** POST 走 `req_retry`，**所有**环节都被判"已覆盖" → 把 `git/trees` 改回裸 req 无人发现 → 一次 502 整轮白干（153 轮真实事故）。
   🔑 七方向破坏全部符合预期：①退化不看 URL G443=0/G444=0/**G445=1**（核心对照）· ②桩化唯一实现=1 · ③环节清单清空=1 · ④对照点漂移=1 · ⑤一致改名=0 不误报 · ⑥常量值改坏=1 · ⑦判据放宽成"覆盖≥1"=0（🔴 证明起作用的是「覆盖数必须 == 条数」）。恢复后 md5 一致。
   ⚠️ 诚实结论：① 🔴 **只探测了 D/E/F 三种退化形态**（D 不看 URL 被放行，E 前缀模糊、F 只报首条均被 G444 抓到），`globals().get('req')(...)` 这类**按字符串访问**的调用仍不被 `_write_step_scan` 认（152 轮同款，本类第五次）；② G445 判据自身被放宽无人发现（109 轮已知边界）；③ 同时改实现与环节清单仍绕过。
"""
rm2 = rm.replace(ANCHOR, ADD)
w(RM, rm2)
print('README  %d → %d 字节' % (len(rm), len(rm2)))

# ── 负面教训库 ──
rl = io.open(RL, encoding='utf-8').read()
A2 = ('| 🔑 反证样本只造**一个**样本点（156 轮实证） | G443 的三个反证都用同一个环节，'
      '扫描退化成"只对那个环节生效"后 G443 依旧全绿 —— **反证覆盖不到 == 没守护**，'
      '其余三个环节的裸 req 从此无人发现 |\n')
assert rl.count(A2) == 1, 'lessons anchor'
B2 = ('| 🔑 反证形态只测"含本对象的正样本"（157 轮实证） | G443/G444 的 A/B/C 三形态 URL '
      '**都含当前环节**，扫描退化成"只按 HTTP 方法匹配、完全不看 URL"后**两条都 rc=0 放行** '
      '—— **没造过"认错"的样本，就不知道它认不认得对**；危害是各环节的违规互相掩盖 |\n')
rl2 = rl.replace(A2, A2 + B2)

A3 = ('🔑 **判据**：反证样本必须按被守护对象**参数化生成、逐个各造一次**'
      '（151 轮"逐条各造一次篡改"同款，156 轮推广到**环节**维度），'
      '并常驻一个"退化实现在该样本点上全绿"的内嵌对照。')
assert rl2.count(A3) == 1, 'verdict anchor'
B3 = (A3 + '\n\n🔑 **判据（157 轮补）**：光"每个对象都测了"还不够，还必须有**至少一个'
      '与本对象不相干的反例样本** —— 否则"实现是否真的按对象区分"从未被检验'
      '（157 轮实测：不看 URL 的退化实现在逐环节口径下照样全绿）。')
rl2 = rl2.replace(A3, B3)
w(RL, rl2)
print('教训库  %d → %d 字节' % (len(rl), len(rl2)))

for p in (RM, RL):
    s = io.open(p, encoding='utf-8').read()
    print(p, '· 第一百五十七轮 出现次数 =', s.count('第一百五十七轮'),
          '· 反证形态只测 =', s.count('反证形态只测'))
