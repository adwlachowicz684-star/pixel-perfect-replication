#!/usr/bin/env python3
"""玩家认知层 / 可读复杂度 / 联机社交契约 / 非死亡失败
（第三十三轮 A / B / C / D 类，含 E / F / G / H 补充）。

**🔑 本轮最重要的判断**：
> A 层（玩家认知与误解）是 must-match **尚未触及的判定真空** ——
> 真正的问号**不是"怎么复刻"而是"对齐什么"**。
> **实际机制与玩家体验冲突时，该对齐谁？**

**🔑 可操作判据是四层分流，而不是"哪个更像真相"**：

| 层级 | 对齐对象 | 偏离时处置 | 判据 |
|---|---|---|---|
| **语义层**（判定/状态转移/数值） | 实测行为 | **属 BUG，不得偏离** | 同一输入同状态产生同一输出，可跨 seed 复现 |
| **叙事层**（台词/线索真假/教学说法） | 原版呈现内容 | 保留原句或显式标"移植性改写" | 台词可改，但"**它教的是错的**"这一属性不得丢 |
| **输入层**（不可通行/延迟/手感） | 实测响应 | 可提升，但须写"原版为何不可接受" | 违反现代平台最低可用标准且原版无补偿 |
| **视觉层**（高亮/噪声/可见性） | 实测可见性 | **不得优化掉**；可升分辨率不可改语义 | 边缘像素 · 层级 · 时序三处逐项对比 |

**🔑 "玩家共识误解"必须成为一等资产，而非 bug 清单备注。**
> 关键判据：若误解**催生了玩家行为**（速通路线 · 配装 · 探索路径 ·
> 社交信任），它就是**玩法事实而非错误认知** ——
> 重制必须保留其**可成立的感知条件**。

**🔑 C 层是本套方法目前最大的空白**：
> 「**能联机**」到「**契约完整**」之间还差 60 多个真子集。
> Nakama / Open Match / RakNet **只解决"怎么发消息"，
> 不解决"契约是什么"** ——
> 🔴 **Nakama 的组队/好友原语不能自动推导出掉落归属**。

用法:
  game_cognitive_social.py --four   # 🔑 **四层分流**（对齐真相还是体验）
  game_cognitive_social.py --myth   # 🔑 **共识误解七字段**
  game_cognitive_social.py --truth  # **实测真相 vs 玩家体验**三例
  game_cognitive_social.py --misdir # 🔴 **故意误导**的最小感知条件
  game_cognitive_social.py --layer  # 🔑 可读**信息层互斥与优先级**
  game_cognitive_social.py --hl     # 🔴 **高亮是"加在物体上"还是"替换材质"**
  game_cognitive_social.py --scan   # 扫描模式**是否改变判定**
  game_cognitive_social.py --invite # 🔑 邀请**9 态 FSM**
  game_cognitive_social.py --kick   # 🔴 **踢出与退出是两个独立状态机**
  game_cognitive_social.py --join   # **中途加入 8 个真子集**
  game_cognitive_social.py --loot   # 🔑 **掉落分配**细节
  game_cognitive_social.py --ff     # 🔴 **队友伤害"允许但有代价"**
  game_cognitive_social.py --chat   # 聊天**存在 vs 谁可见**两个字段
  game_cognitive_social.py --fail   # 🔑 **非死亡失败 8 类**
  game_cognitive_social.py --soft   # **软硬边界**与失败前是否自动存档
  game_cognitive_social.py --frame  # 🔴 **确认时刻 5 个候选帧**
  game_cognitive_social.py --warn   # **预警是独立子系统**
  game_cognitive_social.py --efg    # E / F / G 补充
  game_cognitive_social.py --h      # H 层十二项新盲区
  game_cognitive_social.py --init ledger/cognitive_social.csv
  game_cognitive_social.py --check ledger/cognitive_social.csv --gate

退出码: 0 通过 / 1 缺项 / 2 用法错误
"""
import argparse
import csv
import os
import sys

# 🔑 四层分流
FOUR_LAYERS = [
    ('**语义层**', '判定 · 状态转移 · 数值', '**实测行为**',
     '**属 BUG，不得偏离**',
     '同一输入在同一状态下产生同一输出，可跨 seed 复现'),
    ('**叙事层**', 'NPC 台词 · 线索真假 · 教学说法', '**原版呈现内容**',
     '保留原句或显式标"**移植性改写**"',
     '台词可改，但"**它教的是错的**"这一属性不得丢'),
    ('**输入层**', '不可通行 · 延迟 · 手感', '**实测响应**',
     '**可提升**，但须写"原版为何不可接受"',
     '违反现代平台最低可用标准且原版无对应补偿设计'),
    ('**视觉层**', '高亮 · 噪声 · 可见性', '**实测可见性**',
     '**不得优化掉**；可升分辨率不可改语义',
     '边缘像素 · 层级 · 时序三处逐项对比'),
]

FOUR_RULE = '🔑 判定规则应是**四层分流**，🔴 **而不是"哪个更像真相"**。'
'建议写进 `evidence/interpretation_policy.md`'

# 共识误解七字段
MYTH_FIELDS = [
    '**claimed_mechanism**（社区怎么认为）', '**measured_truth**（实测真相）',
    '**origin**（口口相传 · 速通 · 攻略 · 开发者访谈）',
    '**affected_skill_tier**（休闲 · 普通 · 速通 · 竞速）',
    '**preserve_as_experience**（是否构成玩法）',
    '**transfer_intent**（保真 · 迁移 · 显式改写）',
    '**evidence_grade**（八级）',
]

MYTH_RULE = [
    '🔑 **"玩家共识误解"必须成为一等资产，而非 bug 清单的备注** —— '
    '新增 `consensus_myth/` 目录',
    '🔑 关键判据：若误解**催生了玩家行为**'
    '（速通路线 · 配装 · 探索路径 · 社交信任），'
    '它就是**玩法事实而非错误认知**',
    '🔑 重制必须**保留其可成立的感知条件**',
    '🔑 若误解仅影响观感且无行为后果，可在不影响其他机制的前提下'
    '做**保真式澄清**',
    '🔑 所有 `transfer_intent=rewrite` 的条目**必须提供 '
    '`community_impact` 与 `regression_test_id`**，否则阻断合入',
]

# 三例
TRUTH_EXAMPLES = [
    ('敌人 AI 怪异但可复现',
     '重制必须复刻**可复现的怪异节奏**，而非"修正成更聪明"',
     '**玩家靠这个节奏判断进攻窗口**'),
    ('NPC 教的是错的但按错的也能通关',
     '必须保留"**错误教学可通关**"这一组合',
     '🔴 **不能只修正教学文案**'),
    ('bug 被速通社区当机制用多年',
     '标 `evidence_grade` 为"**测量 + 社区复现**"，'
     '同时记"**原版从未声明**"',
     '默认保真；允许 `transfer_intent=rewrite` 但需单列清单'),
]

# 故意误导
MISDIR_RULE = [
    '🔑 每条 `intentional_misdirection` 记录须校验'
    '"**误导成立所需的最小感知条件**"是否齐全',
    '🔴 **若高亮 · 阴影 · 反射任一被改动，误导即失效**',
]

# 🔑 信息层
INFO_LAYERS = [
    '敌人轮廓', '可交互物高亮', '任务标记', '队友', '掉落物', '危险区',
    '可破坏物',
]

LAYER_RULE = [
    '🔑 可读复杂度的度量**不是"能不能看清"**，'
    '而是**信息层之间是否互斥 · 分层 · 有序**',
    '🔑 要记**同时有多少可读信息层**与**视觉噪声阈值**'
    '（多少高亮会让玩家看不清？原版如何分层？）',
    '🔑 可交互物提示**何时出现**：距离？视线？是否穿墙？是否需要按住？',
]

# 🔴 高亮两条路径
HL_TWO = [
    ('**Custom Depth / Stencil 轮廓**',
     '后处理描边路径'),
    ('**Deferred Decal**',
     '进入 G-Buffer 的贴花路径'),
]

HL_RULE = [
    '🔑 承重证据落在 **Custom Depth/Stencil 轮廓**与 **Deferred Decal**'
    '两条渲染路径上',
    '🔑 高亮是"**加在物体上**"还是"**替换材质**"，'
    '**直接决定阴影 · 反射 · 透明 · 深度排序是否一致**',
    '🔴 **重制把描边误做成后处理是高频失真源**',
]

# 扫描模式
SCAN_ITEMS = [
    '开关时长', '影响范围', '**是否改变判定**', '是否改变可见性',
    '是否改变音频', '退出后恢复哪一帧',
]

SCAN_RULE = '🔑 **扫描模式"改变判定"是 B 层与已覆盖判定域的交界** —— '
'必须显式声明，🔴 **不能默认只改视觉**'

# 🔑 邀请 9 态
INVITE_NINE = [
    'idle', 'inviting', 'invited_pending', 'accepted', 'joining', 'in_lobby',
    'in_game', 'invite_expired', 'invite_declined',
]

INVITE_EXTRA = [
    '是否带**会话版本/内容哈希**', '**内容版本不一致时的提示文案**',
    '**邀请有效期帧数或秒数**', '**重复邀请去重键**',
    '**跨进度邀请**（邀请方第 8 章、被邀请方第 2 章）如何处理',
    '**拒绝后是否有冷却**', '**过场中是否可发送/接收**',
    '玩家已在另一会话时的合并策略',
]

INVITE_RULE = '🔑 原版若"**接受即跳到邀请方进度**"，'
'重制改成"**先同步进度再接受**"**就是契约偏离**'

# 🔴 踢出
KICK_FIELDS = [
    '踢出者是否需要**投票**', '**被踢者当次掉落归属**（随尸体/随角色/按分配）',
    '**被踢者是否能重连**', '**重连是否回到踢出时刻的副本状态**',
    '踢出惩罚（信誉 · 封禁时长 · 仅本会话）',
    '**退出是否触发队友 AI 接管**',
    '**退出时未确认的交易与未完成的交互事务如何回滚**',
]

KICK_RULE = [
    '🔑 **"踢出"与"退出"必须分开成两个独立状态机**',
    '🔑 **玩家实体离开会话本身是一次事务** —— '
    '需写 **stable sort key 与回滚点**',
    '🔑 这是前 32 轮"交互事务六类副作用"**未覆盖的会话级副作用**',
]

# 中途加入
JOIN_EIGHT = [
    '① 能否加入进行中副本',
    '② 加入点是**进入副本起点还是当前进度**',
    '③ **已错过的剧情是否补播**',
    '④ **进入时的等级/装备按谁**（自身 · 副本难度 · 房间内最低）',
    '⑤ **已获取的掉落是否补发**、以何种品质',
    '⑥ **加入前的进度是否标记为"未亲自完成"**',
    '⑦ 离开时进度是否保存',
    '⑧ 若副本有唯一 boss 掉落，**中途加入者是否有独立掉落权**',
]

JOIN_SPLIT = [
    '任务进度（可能共享）', '世界状态（可能独立）', '装备耐久（可能共享）',
    '声望（可能独立）', '已发现区域（可能共享）', '死亡计数（可能独立）',
]

JOIN_RULE = [
    '🔑 **"共享进度 / 独立进度"不是全局开关，而是按维度分裂**',
    '🔴 **任何一项被合并成全局规则都会产生可感知的契约偏离**',
]

# 🔑 掉落
LOOT_ITEMS = [
    '自由拾取时**是否有先手归属窗口** · 是否按距离 · '
    '**能否抢他人未拾取物**',
    '**轮流是严格轮转还是跳过错过者**',
    '**需求优先是否需要对应装备槽/职业**，贪婪与需求如何区分',
    '**掷骰是公开还是隐藏 · 平局如何处理 · '
    '未参与掷骰者能否在结果后拾取**',
    '稀有度阈值以上是否自动进入分配',
    '队长分配**是否可撤回**',
    '**分配期间掉线如何处理**',
    '分配结果**是否可申诉**',
]

LOOT_UI = [
    '**弹窗出现帧**', '**默认选中项**', '**倒计时**', '**超时归属**',
    '**能否在弹窗期间移动**',
]

LOOT_RULE = '🔑 **分配弹窗本身的时机与输入锁定也是 must-match**'

# 🔴 队友伤害
FF_ITEMS = [
    '**FF 开关是谁的权限**', '能否在副本中切换', '**切换冷却**',
    '**AI 与玩家是否分开**', '**伤害衰减比例**', '是否计入任务目标',
    '误伤是否触发仇恨/声望/通缉', '**是否有"原谅/原谅冷却"**',
    '击杀队友是软惩罚还是踢出', '**队友尸体掉落归属**',
]

FF_RULE = '🔴 **重制常把误伤统一成零伤害或全额伤害** —— '
'**两者都丢掉了原版"允许但有代价"这一核心契约**'

# 聊天
CHAT_TWO = [
    ('**聊天记录"是否存在"**', '属**存档六类状态**'),
    ('**"谁可见"**', '属**档案隔离域**'),
]

CHAT_ITEMS = [
    '语音是否**空间化**（近处可闻 / 全队）', '是否有**推流按键**',
    '语音是否会被**录制进回放**', '**文字频道隔离**（全部/队伍/附近/私聊）',
    '消息是否写入存档/录像/服务端日志', '举报的字段与可附证据',
    '**屏蔽是否双向**（屏蔽者不可见 vs 双向不可见）',
    '跨平台与跨存档好友可见性',
]

CHAT_RULE = '🔴 **"存在"与"谁可见"是两个字段，不得混写**'

# 🔑 非死亡失败 8 类
FAIL_EIGHT = [
    ('**mission_failed**', '任务条件不可逆'),
    ('**caught**', '被捕，进入押送/监狱/罚款分支'),
    ('**wanted**', '通缉等级提升，**世界状态持续变化而非读档**'),
    ('**equipment_destroyed**', '装备损坏（耐久归零或被没收）'),
    ('**resources_depleted**', '弹药/时间/体力/货币归零'),
    ('**time_expired**', '倒计时归零'),
    ('**reputation_collapsed**', '声望跌破阈值，NPC 拒绝交易/对话'),
    ('**relationship_broken**', '关系破裂，同伴离队/敌对'),
    ('**party_wiped**', '阵容团灭（全员被捕或全员离队）'),
]

FAIL_RULE = [
    '🔑 **"失败"是比死亡宽得多的概念** —— 与"死亡四类"只有两成交集',
    '🔑 这些状态**可以并发存在**（被捕+通缉、装备损坏+声望归零）'
    '—— 需定义**合并与优先级**',
]

# 软硬边界
SOFT_FIELDS = [
    '**recoverable**', '**recovery_cost**', '**recovery_input_lock_ms**',
    '**auto_saved_before_failure**（失败前是否自动存档）',
    '**retry_entry_point**（任务起点 · 失败点 · 最近检查点）',
    '**penalty_applied**（金钱 · 经验 · 耐久 · 声望）',
    '**state_preserved**（世界时间 · 天气 · NPC 位置 · 已收集物）',
]

SOFT_RULE = [
    '🔑 **软失败与硬失败的边界在原版里是有意设计，不是实现缺陷**',
    '🔑 软失败：花资源修装备 · 付罚款脱身 · 说服 NPC · 用备用方案继续',
    '🔑 硬失败：回到检查点 · 读档 · 重新进入副本',
    '🔴 **"失败是否自动存档"是独立字段** —— '
    '原版若不在被捕前存档，重制"**贴心**"地自动存档'
    '**就让读档这一恢复手段失效了**',
]

# 🔴 确认时刻
FRAME_FIVE = [
    '判定条件**首次成立**的帧',
    '结果**被写入状态**的帧',
    '**演出开始**帧',
    '**演出结束**帧',
    '**控制权交还玩家**帧',
]

FRAME_RULE = [
    '🔑 需记哪个帧 **UI 首次显示失败字样** · 哪个帧**玩家才真正知道** · '
    '哪个帧**输入被锁定**',
    '🔑 **"确认时刻"与"失败时刻"分离是 D 层最核心的 must-match**',
    '🔴 原版用演出延迟确认时，重制**把提示提前会让玩家提前反应**，'
    '**把提示延后则让玩家多操作一次无效输入**',
]

# 预警
WARN_ITEMS = [
    '**是否有预警**',
    '**触发阈值**（距通缉升级还差多少声望 · 耐久低于百分比 · 剩余秒数）',
    '**预警表现**（图标 · 音效 · 屏幕边缘 · 手柄震动）',
    '**预警精度**（告知类别还是只告知"有危险"）',
    '**是否能关闭** · 关闭后是否影响其他系统',
    '**预警到失败之间是否有缓冲帧让玩家补救**',
]

WARN_RULE = '🔑 **预警是独立子系统，不是 HUD 装饰**；'
'🔴 **"没有预警"本身就是一种设计，不得"为了体验加上预警"**'

# E / F / G
EFG = [
    ('**E 玩家表达**', '最小记录集是"**表达能否改变世界**"，'
     '而非资产清单。表情/动作的分类与触发（快捷轮盘？指令？可打断？）· '
     '**是否影响玩法**（能否用于交流？是否吸引敌人？）· '
     '**自定义涂装/图案的持久化与可见性**（其他玩家能否看到？审核？）· '
     '**社交反馈**（能否被屏蔽？举报？）'),
    ('**F 时间压力**', 'must-match 粒度是"**最后值含不含零点**"，'
     '不是显示格式。倒计时**显示精度**（秒？分？小数？）· '
     '**暂停条件**（过场？菜单？暂停？）· **"最后几秒"的表现**'
     '（变色？加速？音效？）· **时间到时的判定帧**'
     '（最后一帧还是下一帧？）· **0.01 秒算成功吗**'),
    ('**G 世界记忆**', '**声望值只能承载其中两个字段**。'
     'NPC 对**具体行为**的记忆（你偷过东西 · 你救过我 · 你杀了某人）· '
     '**衰减与遗忘**（多久？什么触发？）· '
     '**"被认出"的判定**（伪装？距离？视线？）· '
     '**世界对选择的长期反应**（环境变化 · NPC 对话 · 区域状态）'),
]

# H
H_TWELVE = [
    ('**证据冲突仲裁表**', '同行为多来源冲突时如何裁定'),
    ('**玩家证言可信度分层**', '🔴 **论坛观点不得当机制事实**'),
    ('**假线索归因**', '误导性 NPC 与伪装友军的记录'),
    ('**教程错误容忍**', '原版教的是错的但可通关'),
    ('**共识误解随版本漂移**', '同一误解在不同版本是否成立'),
    ('**扫描模式改变判定**', 'B 层与判定域交界'),
    ('**高亮参与阴影/反射**', 'B 层与材质域交界'),
    ('**信息层互斥与优先级合并**', '同时多层如何仲裁'),
    ('**限时最后值含不含零点**', 'F 层与时间域交界'),
    ('**失败演出能否打断**', '连续失败时的体验'),
    ('**连续失败补偿**', '是否有 · 上限 · 是否跨会话'),
    ('**认知偏离回归测试**', '🔑 本 Skill 从"**机制复刻**"走向'
     '"**体验复刻**"的必要升级'),
]

H_RULE = '🔑 三条**交界边界**须在合入时处理：'
'**扫描模式改变判定**（B 层 ↔ 判定域）· '
'**高亮参与阴影/反射**（B 层 ↔ 材质域）· '
'**限时最后值的边界帧**（F 层 ↔ 时间域）'

CONFLICTS = [
    '❌ **双开关"把选择权交给玩家"**（两个选项并存）',
    '❌ **"既然是 bug 就主动修"**',
    '❌ **按开发者最新说法重写**（把推测当真相）',
    '❌ "能联机就行"丢弃整个契约层',
    '❌ **联机沿用引擎默认会话模型**',
    '❌ "好友系统用平台 API 就行"（忽略跨平台可见性与邀请有效期）',
    '❌ "匹配就是撮合"（忽略匹配后的进度/奖励/补玩语义）',
    '❌ **把误伤统一成零伤害或全额伤害**',
    '❌ **共享/独立进度合并成全局规则**',
    '❌ **把描边误做成后处理**',
    '❌ "为了体验加上预警"',
    '❌ **一切失败都读档**（把软失败变硬失败）',
    '❌ 失败就进专属界面（破坏押送/罚款分支）',
    '❌ **连续失败自动降难度**（未声明偏离）',
    '❌ **优化掉视觉噪声导致玩家找不到东西**',
    '❌ 把"玩家共识误解"当 bug 清单备注',
]

FIELDS = [
    ('item_id', '项编号'),
    ('domain', '域（four / myth / truth / misdir / layer / hl / scan / '
               'invite / kick / join / loot / ff / chat / fail / soft / '
               'frame / warn / efg / h）'),
    ('legacy_value', '**原版值**'),
    ('new_value', '新引擎值'),
    ('match', '**是否一致**'),
    ('tolerance', '**允许偏差**'),
    ('evidence', '证据等级 1-8'),
]


def _hdr(t, w=80):
    print('=' * w)
    print(t)
    print('=' * w)


def cmd_four(a):
    _hdr('🔑 四层分流（**对齐真相还是对齐体验**）')
    print(f'   {"层级":<12}{"内容":<24}{"对齐对象":<18}偏离处置')
    print('   ' + '-' * 76)
    for k, content, target, act, _ in FOUR_LAYERS:
        print(f'   {k:<12}{content:<24}{target:<18}{act}')
    print('\n判据:')
    for k, _, _, _, why in FOUR_LAYERS:
        print(f'   {k:<12} {why}')
    print(f'\n   {FOUR_RULE}')
    return 0


def cmd_myth(a):
    _hdr('🔑 共识误解（**七字段**）')
    for f in MYTH_FIELDS:
        print(f'   · {f}')
    print('\n规则:')
    for r in MYTH_RULE:
        print(f'   {r}')
    return 0


def cmd_truth(a):
    _hdr('实测真相 vs 玩家体验（**三例**）')
    for k, act, why in TRUTH_EXAMPLES:
        print(f'\n   【{k}】\n      {act}\n      → {why}')
    return 0


def cmd_misdir(a):
    _hdr('🔴 故意误导（**最小感知条件**）')
    for r in MISDIR_RULE:
        print(f'   {r}')
    return 0


def cmd_layer(a):
    _hdr('🔑 可读复杂度（**信息层互斥与优先级**）')
    print('信息层: ' + ' · '.join(INFO_LAYERS))
    print('\n规则:')
    for r in LAYER_RULE:
        print(f'   {r}')
    return 0


def cmd_hl(a):
    _hdr('🔴 高亮（**两条渲染路径**）')
    for k, why in HL_TWO:
        print(f'   {k:<34} {why}')
    print('\n规则:')
    for r in HL_RULE:
        print(f'   {r}')
    return 0


def cmd_scan(a):
    _hdr('扫描模式')
    for s in SCAN_ITEMS:
        print(f'   · {s}')
    print(f'\n   {SCAN_RULE}')
    return 0


def cmd_invite(a):
    _hdr('🔑 邀请（**9 态 FSM**）')
    print('   ' + ' → '.join(INVITE_NINE))
    print('\n额外记录:')
    for e in INVITE_EXTRA:
        print(f'   · {e}')
    print(f'\n   {INVITE_RULE}')
    return 0


def cmd_kick(a):
    _hdr('🔴 踢出与退出（**两个独立状态机**）')
    for k in KICK_FIELDS:
        print(f'   · {k}')
    print('\n规则:')
    for r in KICK_RULE:
        print(f'   {r}')
    return 0


def cmd_join(a):
    _hdr('中途加入（**8 个真子集**）')
    for j in JOIN_EIGHT:
        print(f'   {j}')
    print('\n按维度分裂（不是全局开关）: ' + ' · '.join(JOIN_SPLIT))
    print('\n规则:')
    for r in JOIN_RULE:
        print(f'   {r}')
    return 0


def cmd_loot(a):
    _hdr('🔑 掉落分配')
    for l in LOOT_ITEMS:
        print(f'   · {l}')
    print('\n弹窗必记: ' + ' · '.join(LOOT_UI))
    print(f'\n   {LOOT_RULE}')
    return 0


def cmd_ff(a):
    _hdr('🔴 队友伤害（**允许但有代价**）')
    for f in FF_ITEMS:
        print(f'   · {f}')
    print(f'\n   {FF_RULE}')
    return 0


def cmd_chat(a):
    _hdr('聊天（**存在 vs 谁可见**）')
    for k, why in CHAT_TWO:
        print(f'   {k:<24} {why}')
    print('\n记录:')
    for c in CHAT_ITEMS:
        print(f'   · {c}')
    print(f'\n   {CHAT_RULE}')
    return 0


def cmd_fail(a):
    _hdr('🔑 非死亡失败（**8 类**）')
    for k, why in FAIL_EIGHT:
        print(f'   {k:<28} {why}')
    print('\n规则:')
    for r in FAIL_RULE:
        print(f'   {r}')
    return 0


def cmd_soft(a):
    _hdr('软硬边界（**失败前是否自动存档**）')
    print('字段: ' + ' · '.join(SOFT_FIELDS))
    print('\n规则:')
    for r in SOFT_RULE:
        print(f'   {r}')
    return 0


def cmd_frame(a):
    _hdr('🔴 确认时刻（**5 个候选帧**）')
    for i, f in enumerate(FRAME_FIVE, 1):
        print(f'   {i}. {f}')
    print('\n规则:')
    for r in FRAME_RULE:
        print(f'   {r}')
    return 0


def cmd_warn(a):
    _hdr('预警（**独立子系统**）')
    for w in WARN_ITEMS:
        print(f'   · {w}')
    print(f'\n   {WARN_RULE}')
    return 0


def cmd_efg(a):
    _hdr('E / F / G 补充')
    for k, why in EFG:
        print(f'\n   【{k}】\n      {why}')
    return 0


def cmd_h(a):
    _hdr('H 层（**十二项新盲区**）')
    for k, why in H_TWELVE:
        print(f'   {k:<26} {why}')
    print(f'\n   {H_RULE}')
    return 0


def cmd_init(a):
    os.makedirs(os.path.dirname(a.init) or '.', exist_ok=True)
    with open(a.init, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow([k for k, _ in FIELDS])
        w.writerow(['TODO'] * len(FIELDS))
    print(f'已生成认知/社交表: {a.init}')
    print('\n⚠️ 十九域：four / myth / truth / misdir / layer / hl / scan / '
          'invite / kick / join / loot / ff / chat / fail / soft / frame / '
          'warn / efg / h')
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

    mismatch, no_legacy, no_grade = [], [], []
    for i, r in enumerate(rows, 1):
        m = g(r, 'match').lower()
        if m not in ('yes', 'y', 'true', '是', '一致'):
            mismatch.append(i)
        if not g(r, 'legacy_value') or g(r, 'legacy_value') == 'TODO':
            no_legacy.append(i)
        ev = g(r, 'evidence')
        if not ev or ev == 'TODO':
            no_grade.append(i)
        else:
            d = ev.split('.')[0].strip()
            if d.isdigit() and int(d) >= 7:
                no_grade.append(i)

    print('=' * 76)
    print(f'认知/社交 · {len(rows)} 条')
    print('=' * 76)
    if mismatch:
        print(f'\n🚫 **不一致** {len(mismatch)} 条（行 {mismatch[:15]}）')
    if no_legacy:
        print(f'\n❌ {len(no_legacy)} 条缺**原版值**（行 {no_legacy[:15]}）')
    if no_grade:
        print(f'\n🚫 {len(no_grade)} 条**证据等级缺失或 ≥7 级**'
              f'（行 {no_grade[:15]}）')

    if not (mismatch or no_legacy or no_grade):
        print('\n✅ 认知/社交：一致、原版值完整、证据等级达标')

    print('\n🔑 **对齐真相还是对齐体验？四层分流：**')
    print('   语义不得偏离 · 叙事可注明改写 · 输入可提升须写原因 · '
          '视觉不得优化掉。')
    print('   **Nakama/Open Match/RakNet 只解决"怎么发消息"，'
          '不解决"契约是什么"。**')
    print('   **「确认时刻」与「失败时刻」分离是 D 层最核心的 must-match。**')
    return 1 if (a.gate_check and (mismatch or no_legacy or no_grade)) else 0


def main():
    ap = argparse.ArgumentParser(description='玩家认知层与联机契约')
    ap.add_argument('--four', action='store_true')
    ap.add_argument('--myth', action='store_true')
    ap.add_argument('--truth', action='store_true')
    ap.add_argument('--misdir', action='store_true')
    ap.add_argument('--layer', action='store_true')
    ap.add_argument('--hl', action='store_true')
    ap.add_argument('--scan', action='store_true')
    ap.add_argument('--invite', action='store_true')
    ap.add_argument('--kick', action='store_true')
    ap.add_argument('--join', action='store_true')
    ap.add_argument('--loot', action='store_true')
    ap.add_argument('--ff', action='store_true')
    ap.add_argument('--chat', action='store_true')
    ap.add_argument('--fail', action='store_true')
    ap.add_argument('--soft', action='store_true')
    ap.add_argument('--frame', action='store_true')
    ap.add_argument('--warn', action='store_true')
    ap.add_argument('--efg', action='store_true')
    ap.add_argument('--h', action='store_true')
    ap.add_argument('--init')
    ap.add_argument('--check')
    ap.add_argument('--gate-check', action='store_true')
    a = ap.parse_args()
    fns = {'four': cmd_four, 'myth': cmd_myth, 'truth': cmd_truth,
           'misdir': cmd_misdir, 'layer': cmd_layer, 'hl': cmd_hl,
           'scan': cmd_scan, 'invite': cmd_invite, 'kick': cmd_kick,
           'join': cmd_join, 'loot': cmd_loot, 'ff': cmd_ff, 'chat': cmd_chat,
           'fail': cmd_fail, 'soft': cmd_soft, 'frame': cmd_frame,
           'warn': cmd_warn, 'efg': cmd_efg, 'h': cmd_h}
    for k, fn in fns.items():
        if getattr(a, k):
            return fn(a)
    if a.init:
        return cmd_init(a)
    if a.check:
        return cmd_check(a)
    print('❌ 需要 --four / --myth / --truth / --misdir / --layer / --hl / '
          '--scan / --invite / --kick / --join / --loot / --ff / --chat / '
          '--fail / --soft / --frame / --warn / --efg / --h / --init / '
          '--check 之一')
    return 2


if __name__ == '__main__':
    sys.exit(main())
