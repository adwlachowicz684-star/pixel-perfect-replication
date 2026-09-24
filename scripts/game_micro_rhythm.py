#!/usr/bin/env python3
"""微观节奏（帧语义）· 注意力仲裁 · 人格语气 · 边界退化
（第三十六轮 A / B / C / D 类，含 E / F / G / H 补充）。

**🔑 本轮最重要的一句**：
> **仅记录帧率 · 帧预算 · 平均延迟，会把最重要的相位信息平均掉。**
> 🔑 像素级复刻必须升级为"**事件级**"，帧预算只是其中一层指标。

**🔑 核心产物是"同一帧多通道事件轨迹"**：原版与复刻都从**同一个硬件触发**
开始，记录输入采样 → 状态提交 → 判定生效 → 逻辑可见 → 首像素/音频样本 →
首震动帧 → 玩家最终感知时间。**任何跨通道偏差都必须解释**，
🔴 **不能仅因"平均延迟相同"就判定通过**。

用法:
  game_micro_rhythm.py --ladder  # 🔑 **帧语义阶梯**（六问）
  game_micro_rhythm.py --chan    # 🔑 **十二通道**
  game_micro_rhythm.py --stop    # 🔴 **微停顿**（1-3 帧）
  game_micro_rhythm.py --seam    # 🔑 **接缝**（不是动画混合权重）
  game_micro_rhythm.py --attn    # 🔑 **注意力仲裁**（不是通知系统）
  game_micro_rhythm.py --intent  # 七类**意图类型**
  game_micro_rhythm.py --force   # 🔴 **强制注意力**控制权返还合同
  game_micro_rhythm.py --recov   # **注意力恢复**五件事
  game_micro_rhythm.py --voice   # 🔑 **人格语气**（逐字符串字段）
  game_micro_rhythm.py --tone    # 🔴 **"You died"有五种语气**
  game_micro_rhythm.py --silence # 🔑 **沉默的语气**要自己测量
  game_micro_rhythm.py --bound   # 🔑 **边界是一等状态模型**
  game_micro_rhythm.py --num     # 🔴 **NaN/±0/±∞/溢出**必须触发
  game_micro_rhythm.py --degen   # **退化世界**（空世界/满库存/过场输入）
  game_micro_rhythm.py --efgh    # E / F / G / H
  game_micro_rhythm.py --init ledger/micro_rhythm.csv
  game_micro_rhythm.py --check ledger/micro_rhythm.csv --gate

退出码: 0 通过 / 1 缺项 / 2 用法错误
"""
import argparse
import csv
import os
import sys

# 🔑 帧语义六问
LADDER_SIX = [
    ('**sample frame**', '原始硬件事件落入哪个输入采集阶段',
     '与原版同 tick，或证明外部采样窗口等价'),
    ('**commit frame**', '状态机是否接受输入并改变权威状态',
     '同帧同相位，**不允许无理由延后**'),
    ('**resolve frame**', '命中/判定结果是否最终确定',
     '与原版完全一致；**并发判定须冻结同序**'),
    ('**event frame**', '动画 · 粒子 · 音效 · 震动是否同时触发',
     '同帧相位优先；**错帧必须量化并签核**'),
    ('**visible frame**', '提交/呈现的首个可见结果',
     '**首像素与截帧一致性**，不接受仅尾帧相似'),
    ('**perceptual frame**', '显示 · 音频 · 震动分别到达玩家',
     '**分别测量**；click-to-photon 与感官相位均测'),
]

LADDER_RULE = '🔑 关键**不是**把"某动作耗时 16.7ms"写下来，而是回答：'
'输入在哪一轮被采样 · 哪一轮进入意图队列 · 哪一轮写入权威状态 · '
'哪一轮改变动画/伤害/音效 · 哪一轮第一次被渲染 · 哪一轮第一次被听见或感到震动'

# 🔑 十二通道
CHANNELS = [
    'input', 'logic', 'physics', 'animation', 'vfx', 'audio', 'haptic',
    'camera', 'ui', 'render_submit', 'present', 'photon',
]

CHAN_RULE = '🔑 每个事件至少记 **frame_index · 全局 tick · 硬件时间戳 · '
'引擎阶段 · 事件类型 · 所属通道 · 偏移量 · 是否同步 · 因果上游事件**'
'（新增 `frame_semantics.md` 与 `frame_event_trace.schema.json`）'

# 🔴 微停顿
STOP_ITEMS = [
    '停顿位于**哪一状态**',
    '是否**冻结逻辑/动画/物理/输入**',
    '**持续几帧**',
    '是否**跳过插值**',
    '**输入是否被吞掉**',
    '是否有 **hit-stop / Time Scale 变化**',
]

STOP_RULE = [
    '🔑 **微停顿尤其不能只靠主观"感觉重"** —— 必须逐项记录',
    '🔑 1–3 帧停顿要**测量三次以上**，并固定**刷新率 · 可变刷新率 · 超分 · '
    '帧生成 · 垂直同步**状态',
    '🔴 **帧生成插出的帧必须标 `frame_kind=interpolated`，'
    '不得冒充原生可见帧**',
]

# 🔑 接缝
SEAM_ITEMS = [
    '前一动作**最后一帧事件**', '**退出判定帧**', '**过渡帧数**',
    '后一动作**起始帧**', '**是否有 1 帧重叠**',
    '是否**复用前一姿态/速度/根运动**', '**Cancel 窗口开闭帧**',
    '动画剪辑边界 · **音频尾音** · **粒子继承** · 相机抖动 · **控制权**',
]

SEAM_RULE = '🔑 **很多人误把动画混合权重当接缝** —— '
'真正改变手感的是**权威状态和输入窗口**'
SEAM_OUT = '输出 `overlap_frames · gap_frames · authoritative_change_frame · '
'first_input_accepted_frame` —— **只有这些一致才算接缝 match**'

# 🔑 注意力仲裁
ATTN_FIELDS = [
    '当前目标', '**可感知信号通道**', '**视觉位置/运动**',
    '**颜色/亮度**', '**屏幕占比**', '**持续帧数**',
    '**音频频率/声像/响度**', '**控制器震动**',
    '字幕 · 图标 · 镜头运动 · 世界事件 · 可操作窗口',
]

ATTN_ARB = [
    '**priority_class**', '**salience_score**',
    '**channel_exclusivity**', '**max_overlap**',
    '**suppression_rule**', '**co_occurrence_behavior**', '**recovery_cue**',
]

ATTN_RULE = [
    '🔑 **注意力不是"通知系统"，而是原版预先确定的认知资源合同**',
    '🔑 **仲裁规则必须从原版反推，而不是由新引擎默认值决定**',
    '🔑 先统计**同时触发的事件组合**，再看**优先级是否稳定**：'
    '低血量报警是否覆盖任务提示？伤害反馈是否压掉拾取提示？'
    'QTE 是否暂停 HUD/声音/AI 对话/地图标记？',
    '🔑 "**同时**"要定义为**事件首次可见帧差小于约定阈值**'
    '（建议 **0 / 1 / 2 帧三套基线**）—— '
    '🔴 **避免把"同一逻辑帧"和"同一显示帧"混为一谈**',
]

# 七类意图
INTENT_SEVEN = [
    ('**goal**', '当前目标'),
    ('**alert**', '危险'),
    ('**opportunity**', '机会'),
    ('**confirmation**', '反馈'),
    ('**meta**', '系统'),
    ('**lore**', '世界'),
    ('**interrupt**', '**夺取控制**'),
]

# 🔴 强制注意力
FORCE_ITEMS = [
    '从玩家**可操作到不可操作的最后一帧**',
    '**输入吞掉规则**',
    '**提示首现帧**',
    '**可接受窗口**',
    '**失败反馈帧**',
    '**失败结果**',
    '**控制权返还帧**',
    '**原目标是否保留**',
]

FORCE_RULE = '🔑 既有"输入意图层"仍不够 —— '
'真正变化的是**控制权返回条件**。'
'🔴 原版可能用完整死亡动画重放 QTE 与对话，也可能只轻微 eject；'
'**前一种重放成本更高，但不能因"现代化"缩短**'

# 注意力恢复
RECOV_FIVE = [
    '**旧目标结束提示**', '**旧目标保存位置**', '**新任务锚点**',
    '**首个安全操作帧**', '**旧目标恢复帧**',
]

RECOV_RULE = '🔑 实验证据表明**未完成任务会持续占用认知资源并损害切换后表现** —— '
'🔴 **"重制时新增一个成就弹窗"并非纯 UI 改动，而是对既有注意力合同的修改**'
RECOV_TEST = '🔑 建议跑成对场景：场景 A 在**高认知负荷目标未完成时**被打断；'
'场景 B 在**自然结束点**被打断。测返回原目标后的**首次正确输入帧 · '
'错误操作数 · 目标回看帧 · HUD 聚焦帧**'

# 🔑 人格语气
VOICE_FIELDS = [
    'event_id', 'speaker_or_system', '**mood**', '**attitude**',
    '**politeness_power**', '**certainty**', '**humor**',
    '**regret_blame**', '**urgency**', '**verbosity**',
    '**sentence_structure**', 'character_voice_tags',
    'localization_constraints', 'reference_sample_hash',
]

VOICE_RULE = [
    '🔑 **游戏人格必须被写成可被复刻执行的语料结构**'
    '（`voice_persona.md` · `string_voice.csv` · `silence_baseline.md`）',
    '🔴 **不要把"嘲讽/鼓励/中性"做成单个枚举**，而应用**可观察维度**',
]

# 🔴 五种语气
TONE_FIVE = [
    '**冷陈述**', '**系统日志式**', '**黑色幽默**', '**残酷嘲讽**', '**轻蔑**',
]

TONE_RULE = '🔑 同一句 "You died" 可以是五种语气 —— '
'**差别常藏在标点 · 缩略 · 敬语 · 呼语 · 句子长度 · 音效之前**'

# 🔑 沉默
SILENCE_ITEMS = [
    '从事件发生至**首个文本/图标/语音/震动的静默帧数**',
    '整个反馈期间的**文字覆盖率 · 留白比例**',
    '**是否允许背景音乐继续**',
    '**NPC 是否反应**', '**相机是否后退**',
]

SILENCE_RULE = [
    '🔑 **"沉默的语气"需要自己的测量方法** —— '
    '用**静音基线视频 + 音频 RMS** 双重验证',
    '🔑 **只有视觉和听觉都无信号才可标 `silence=true`**',
    '🔑 要记录这是**设计留白 · 资源缺失 · 本地化漏翻 · 还是前置条件未满足**',
    '🔴 **不能把所有静默都自动归类为 bug**，也不能因'
    '"玩家可能不知道发生了什么"而补一句系统解释',
]

# 🔑 边界
BOUND_NUM = [
    '0', '1', '**最大值**', '**最大值+1**', '**最小值**', '**最小值-1**',
    '**正零**', '**负零**', '**最小正正规数**', '**最小正次正规数**',
    '**最大正规数**', '**NaN**（若语言可构造）', '**正无穷**', '**负无穷**',
    '**非规范位模式**', '**未初始化内存**', '**反序列化缺字段**',
]

BOUND_CASES = [
    ('**血量 0**', '死亡帧 · 状态 · UI · 音效 · 镜头 · 存档 · 动画',
     '全通道逐帧一致；🔴 **不允许"先显示 0 再晚一帧死亡"**'),
    ('**满血/满资源**', '再获得 · 治疗 · 溢出 · 提示是否触发',
     '提示数量 · 文本 · 计数一致'),
    ('**负数/NaN/Inf**', '是否崩溃 · 是否死亡 · 是否渲染 · 是否保存',
     '**保持原版行为；不得一律 sanitize**'),
    ('**非法状态组合**', '同时无敌且死亡 · 抓取且 ragdoll · 对话且暂停',
     '记录实际转移/断言/崩溃，🔴 **不按"合理"改写**'),
]

BOUND_RULE = [
    '🔑 **边界不是补丁清单，而是原版状态空间的"负空间"**',
    '🔑 整数还应测**符号扩展 · 截断 · 不同字节序 · 不同位宽**',
    '🔑 伤害管线同时测**加血 · 减血 · 治疗溢出 · 伤害溢出 · '
    '治疗与伤害同帧 · 负值 · 浮点转整数 · 四舍五入 · 钳制前/后顺序**',
    '🔴 **C++ 中 NaN 会破坏默认排序前置条件，甚至产生未定义行为**',
]

# 退化世界
DEGEN_ITEMS = [
    '**所有敌人死光**', '**物品全满**', '**任务全部完成**', '**地图全开**',
    '**过场中输入**', '**同时按所有键**', '**快速连点**', '**超长输入**',
    '**空世界**（无 NPC · 无敌人 · 无物件）',
]

DEGEN_RULE = '🔑 **退化情况必须成为必测状态，'
'而不是随机测试的偶然产物**'

# EFGH
EFGH = [
    ('**E 重复与变化**', '变化中的恒定比例 · 重复的节奏 · '
     '**变化的可预测性** · **重复疲劳的对抗手段是否保留**'),
    ('**F 社群与外部生态**', '**攻略/wiki 是否仍适用**（坐标 · 名称 · 机制）· '
     '**老模组能否运行** · **速通路线/技巧/计时是否仍成立** · '
     '**外部工具兼容**（伤害计算器 · 地图工具 · 存档编辑器）'),
    ('**G 文档与元数据**', '**游戏内帮助完整度** · **隐藏信息的文档化** · '
     '**版本说明与补丁记录**（是否影响复刻基准）· '
     '**开发者意图记录**（设计 vs 妥协 vs bug）'),
    ('**H 其他**', '**像素级取证标准** · **接口版本** · '
     '**可终止的自动迁移**'),
]

CONFLICTS = [
    '❌ **现代引擎的异步化**（平均延迟相同 ≠ 相位相同）',
    '❌ **NaN 清洗 / 自动 sanitize**',
    '❌ **默认 clamp**',
    '❌ **帧生成伪装成原生帧**',
    '❌ **AI 文案润色**（改变人格）',
    '❌ **本地化审校"规范化"掉人格**（错别字/口语/人称混用可能是设计）',
    '❌ **一致性工具**（原版刻意不一致时会制造偏离）',
    '❌ **自动去停顿**（手感变"滑"）',
    '❌ **新增成就弹窗**（不是纯 UI 改动，是修改注意力合同）',
    '❌ **把动画混合权重当接缝**',
    '❌ 因"现代化"缩短 QTE 重放',
    '❌ **用提示填满每一段沉默**',
    '❌ **把不可能状态"清理"掉**',
]

FIELDS = [
    ('item_id', '项编号'),
    ('domain', '域（ladder / chan / stop / seam / attn / intent / force / '
               'recov / voice / tone / silence / bound / num / degen / efgh）'),
    ('legacy_value', '**原版值**'),
    ('new_value', '新引擎值'),
    ('match', '**是否一致**'),
    ('tolerance', '**允许偏差**（相位类建议 0/1/2 帧三套基线）'),
    ('evidence', '证据等级 1-8'),
]


def _hdr(t, w=80):
    print('=' * w)
    print(t)
    print('=' * w)


def cmd_ladder(a):
    _hdr('🔑 帧语义阶梯（**六问**）')
    print(f'   {"帧":<22}{"问题":<34}判据')
    print('   ' + '-' * 76)
    for k, q, j in LADDER_SIX:
        print(f'   {k:<22}{q:<34}{j}')
    print(f'\n   {LADDER_RULE}')
    return 0


def cmd_chan(a):
    _hdr('🔑 十二通道')
    print('   ' + ' · '.join(CHANNELS))
    print(f'\n   {CHAN_RULE}')
    return 0


def cmd_stop(a):
    _hdr('🔴 微停顿（**1–3 帧**）')
    for s in STOP_ITEMS:
        print(f'   · {s}')
    print('\n规则:')
    for r in STOP_RULE:
        print(f'   {r}')
    return 0


def cmd_seam(a):
    _hdr('🔑 接缝（**不是动画混合权重**）')
    for s in SEAM_ITEMS:
        print(f'   · {s}')
    print(f'\n   {SEAM_RULE}')
    print(f'\n   {SEAM_OUT}')
    return 0


def cmd_attn(a):
    _hdr('🔑 注意力仲裁（**不是通知系统**）')
    print('逐场景必录: ' + ' · '.join(ATTN_FIELDS))
    print('\n仲裁字段: ' + ' · '.join(ATTN_ARB))
    print('\n规则:')
    for r in ATTN_RULE:
        print(f'   {r}')
    return 0


def cmd_intent(a):
    _hdr('七类意图类型')
    for k, why in INTENT_SEVEN:
        print(f'   {k:<20} {why}')
    return 0


def cmd_force(a):
    _hdr('🔴 强制注意力（**控制权返还合同**）')
    for f in FORCE_ITEMS:
        print(f'   · {f}')
    print(f'\n   {FORCE_RULE}')
    print(f'\n   {RECOV_TEST}')
    return 0


def cmd_recov(a):
    _hdr('注意力恢复（**五件事**）')
    for r in RECOV_FIVE:
        print(f'   · {r}')
    print(f'\n   {RECOV_RULE}')
    print(f'\n   {RECOV_TEST}')
    return 0


def cmd_voice(a):
    _hdr('🔑 人格语气（**逐字符串字段**）')
    for v in VOICE_FIELDS:
        print(f'   · {v}')
    print('\n规则:')
    for r in VOICE_RULE:
        print(f'   {r}')
    return 0


def cmd_tone(a):
    _hdr('🔴 "You died" 的五种语气')
    for t in TONE_FIVE:
        print(f'   · {t}')
    print(f'\n   {TONE_RULE}')
    return 0


def cmd_silence(a):
    _hdr('🔑 沉默的语气（**自己测量**）')
    for s in SILENCE_ITEMS:
        print(f'   · {s}')
    print('\n规则:')
    for r in SILENCE_RULE:
        print(f'   {r}')
    return 0


def cmd_bound(a):
    _hdr('🔑 边界（**一等状态模型**）')
    print('四类:')
    for k, why, j in BOUND_CASES:
        print(f'\n   【{k}】\n      录: {why}\n      判: {j}')
    print('\n规则:')
    for r in BOUND_RULE:
        print(f'   {r}')
    return 0


def cmd_num(a):
    _hdr('🔴 数值边界（**必须触发，不是随机产物**）')
    print('   ' + ' · '.join(BOUND_NUM))
    print('\n规则:')
    for r in BOUND_RULE:
        print(f'   {r}')
    return 0


def cmd_degen(a):
    _hdr('退化世界')
    for d in DEGEN_ITEMS:
        print(f'   · {d}')
    print(f'\n   {DEGEN_RULE}')
    return 0


def cmd_efgh(a):
    _hdr('E / F / G / H')
    for k, why in EFGH:
        print(f'\n   【{k}】\n      {why}')
    print('\n冲突做法:')
    for c in CONFLICTS:
        print(f'   {c}')
    return 0


def cmd_init(a):
    os.makedirs(os.path.dirname(a.init) or '.', exist_ok=True)
    with open(a.init, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow([k for k, _ in FIELDS])
        w.writerow(['TODO'] * len(FIELDS))
    print(f'已生成微观节奏表: {a.init}')
    print('\n⚠️ 十五域：ladder / chan / stop / seam / attn / intent / force / '
          'recov / voice / tone / silence / bound / num / degen / efgh')
    return 0


def cmd_check(a):
    if not os.path.exists(a.check):
        print(f'❌ 文件不存在: {a.check}')
        return 2
    with open(a.check, encoding='utf-8', errors='replace', newline='') as f:
        rows = list(csv.DictReader(f))
    if not rows:
        print('❌ 空表')
        return 1

    def g(r, k):
        return (r.get(k) or '').strip()

    mismatch, no_legacy, no_tol, no_grade = [], [], [], []
    for i, r in enumerate(rows, 1):
        m = g(r, 'match').lower()
        if m not in ('yes', 'y', 'true', '是', '一致'):
            mismatch.append(i)
        if not g(r, 'legacy_value') or g(r, 'legacy_value') == 'TODO':
            no_legacy.append(i)
        if not g(r, 'tolerance') or g(r, 'tolerance') == 'TODO':
            no_tol.append(i)
        ev = g(r, 'evidence')
        if not ev or ev == 'TODO':
            no_grade.append(i)
        else:
            d = ev.split('.')[0].strip()
            if d.isdigit() and int(d) >= 7:
                no_grade.append(i)

    print('=' * 76)
    print(f'微观节奏 · {len(rows)} 条')
    print('=' * 76)
    if mismatch:
        print(f'\n🚫 **不一致** {len(mismatch)} 条（行 {mismatch[:15]}）')
    if no_legacy:
        print(f'\n❌ {len(no_legacy)} 条缺**原版值**（行 {no_legacy[:15]}）')
    if no_tol:
        print(f'\n🚫 {len(no_tol)} 条缺**允许偏差**（行 {no_tol[:15]}）')
        print('   ⚠️ 相位类建议 0 / 1 / 2 帧三套基线，不许写"差不多"')
    if no_grade:
        print(f'\n🚫 {len(no_grade)} 条**证据等级缺失或 ≥7 级**'
              f'（行 {no_grade[:15]}）')

    if not (mismatch or no_legacy or no_tol or no_grade):
        print('\n✅ 微观节奏：一致、原版值完整、偏差已声明、证据达标')

    print('\n🔑 **仅记录帧率和平均延迟，会把最重要的相位信息平均掉。**')
    print('   **重制时新增一个成就弹窗不是纯 UI 改动，'
    '而是修改既有注意力合同。**')
    print('   **NaN/±0/±∞ 必须触发，不得一律 sanitize。**')
    return 1 if (a.gate_check and
                 (mismatch or no_legacy or no_tol or no_grade)) else 0


def main():
    ap = argparse.ArgumentParser(description='微观节奏与边界')
    ap.add_argument('--ladder', action='store_true')
    ap.add_argument('--chan', action='store_true')
    ap.add_argument('--stop', action='store_true')
    ap.add_argument('--seam', action='store_true')
    ap.add_argument('--attn', action='store_true')
    ap.add_argument('--intent', action='store_true')
    ap.add_argument('--force', action='store_true')
    ap.add_argument('--recov', action='store_true')
    ap.add_argument('--voice', action='store_true')
    ap.add_argument('--tone', action='store_true')
    ap.add_argument('--silence', action='store_true')
    ap.add_argument('--bound', action='store_true')
    ap.add_argument('--num', action='store_true')
    ap.add_argument('--degen', action='store_true')
    ap.add_argument('--efgh', action='store_true')
    ap.add_argument('--init')
    ap.add_argument('--check')
    ap.add_argument('--gate-check', action='store_true')
    a = ap.parse_args()
    fns = {'ladder': cmd_ladder, 'chan': cmd_chan, 'stop': cmd_stop,
           'seam': cmd_seam, 'attn': cmd_attn, 'intent': cmd_intent,
           'force': cmd_force, 'recov': cmd_recov, 'voice': cmd_voice,
           'tone': cmd_tone, 'silence': cmd_silence, 'bound': cmd_bound,
           'num': cmd_num, 'degen': cmd_degen, 'efgh': cmd_efgh}
    for k, fn in fns.items():
        if getattr(a, k):
            return fn(a)
    if a.init:
        return cmd_init(a)
    if a.check:
        return cmd_check(a)
    print('❌ 需要 --ladder / --chan / --stop / --seam / --attn / --intent / '
          '--force / --recov / --voice / --tone / --silence / --bound / '
          '--num / --degen / --efgh / --init / --check 之一')
    return 2


if __name__ == '__main__':
    sys.exit(main())
