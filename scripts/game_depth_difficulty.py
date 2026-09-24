#!/usr/bin/env python3
"""世界时间纵深 / 玩家—角色边界 / 环境叙事 / 难度维度
（第三十四轮 A / B / C / D 类，含 E / F / G / H 补充）。

**🔑 本轮最重要的判断（先说清楚）**：
> **本轮没有发现一个现成的"游戏世界历史数据库"或"二周目语义框架"
> 可直接吸收。**
> 真正的工程产物集中在**运行时注入与配置复测**，
> 而不是**世界状态模型**。
>
> 🔑 建议把 A—H 从"**系统设计议题**"**降格**为
> **可采集 · 可断言 · 可回归的取证对象**。

**🔑 正确的顺序**：
> **先证明原版行为，再决定实现。**
> 世界历史 · 玩家—角色边界 · 场景语义 · 难度 · 等待 · 收集 · 涌现
> **都不应成为新增功能域**；它们只是对已有世界状态 · UI · 镜头 ·
> 数值 · 保存 · 物理系统的**附加观察维度**。
> 🔴 每个主题都容易被理解成"功能模块"，从而**诱导复刻团队用目标引擎的
> 习惯重新设计** —— 这是本轮最要防的陷阱。

**🔑 本轮最重要的理念判断**：
> 原版若把"**等待**"做成让玩家产生特定误解的体验，或让门卡住形成紧张感，
> 🔴 **直接做成"优化后的快速黑屏"是偏离，而非现代化**。
> 原版若让简单模式不能解锁完整内容，🔴 复刻也不应擅自改成完整通关；
> 只能**显式标注为 must-match 偏离**。

用法:
  game_depth_difficulty.py --hist    # 🔑 世界历史**三层证据**
  game_depth_difficulty.py --vis     # 🔴 **visibility_scope** 七级
  game_depth_difficulty.py --prec    # 🔑 **"先例"是访问计数不是第二套流程**
  game_depth_difficulty.py --src     # 历史源**一致性是测试对象**
  game_depth_difficulty.py --tt      # 时间旅行**回读什么**
  game_depth_difficulty.py --know    # 🔑 **四层知识边界**
  game_depth_difficulty.py --replay2 # 🔴 **"重玩提示"是角色能力还是元层**
  game_depth_difficulty.py --meta    # 元进度**不能写成"跨周目保留"布尔**
  game_depth_difficulty.py --wall    # 破墙**打破什么**
  game_depth_difficulty.py --mark    # 🔑 **地标不是美术资产**
  game_depth_difficulty.py --sig     # 区域**六字段签名**
  game_depth_difficulty.py --perm    # 场景永久变化**三要素**
  game_depth_difficulty.py --diff    # 🔑 **难度八维**
  game_depth_difficulty.py --mid     # 🔴 **中途调整七种语义**
  game_depth_difficulty.py --hidden  # **隐藏参数必须完整反解**
  game_depth_difficulty.py --fair    # 公平性**四种可测属性**
  game_depth_difficulty.py --wait    # 🔴 **等待十二事实**（它可能是玩法）
  game_depth_difficulty.py --atomic  # 🔑 等待**原子性**会错过短窗口事件
  game_depth_difficulty.py --coll    # 收集**遗漏语义与提示公平性**
  game_depth_difficulty.py --eme     # 🔑 **涌现最小复现链**
  game_depth_difficulty.py --h       # H 层十项新盲区
  game_depth_difficulty.py --init ledger/depth_difficulty.csv
  game_depth_difficulty.py --check ledger/depth_difficulty.csv --gate

退出码: 0 通过 / 1 缺项 / 2 用法错误
"""
import argparse
import csv
import os
import sys

# 🔑 历史三层
HIST_THREE = [
    ('**当前世界状态**', '可序列化到存档，必须能恢复'),
    ('**世界事件日志**', '稳定事件编号 · 世界时钟 · 地点 · 因果前驱 · '
     '可见参与者 · 记录源'),
    ('**派生世界知识**', 'NPC 所知事实 · 公告当前文本 · 报纸当前页 · '
     '任务日志可见条目 · 玩家已见事实'),
]

HIST_FIELDS = [
    'event_id', 'world_clock', 'location_id', 'actor_id', 'fact_id',
    '**visibility_scope**', 'observer_id', 'record_source',
    'retention_policy', 'causality_ids',
]

HIST_RULE = [
    '🔑 **世界历史不能只记录当前状态，也不能混成无限事件流**',
    '🔴 **若原版没有这些对象，不能直接补成"更完整的历史系统"**',
    '🔑 若原版确实让**通缉令显示玩家名字**、让**酒馆对话提及玩家做过的事**，'
    '就**必须逐条证明**',
]

# 🔴 visibility_scope
VIS_SCOPE = [
    '仅参与者', '现场观察者', '特定派系', '区域公告', '世界公告',
    '玩家界面', '后台调试',
]

EVIDENCE_LEVELS = [
    ('**一级**', '录像连续行为'),
    ('**二级**', '内存/日志直接观测'),
    ('**三级**', '反复触发并反证'),
    ('**四级**', '数据挖掘'),
    ('**五级**', '官方资料'),
    ('**最低**', '🔴 **社区断言**'),
]

EVIDENCE_RULE = '🔴 **绝不能因为"剧情上应该记得"就推断代码会记住** —— '
'历史系统的真相来自**具体反馈**，不是世界观连贯性'

# 🔑 先例
PRECEDENT_SIX = [
    '仅**对话文本**改变',
    '**NPC 反应 · 仇恨 · 声望 · 任务可用状态**改变',
    '**分支解锁**，但旧选项仍可访问',
    '**旧路径被关闭**，形成不可逆门',
    '世界状态改变后，**旧行为不再合法**',
    '**只有玩家或元层标记改变**，世界本身不变',
]

PRECEDENT_TEMPLATE = [
    'precedent_id', 'fact_changed', 'reaction_changed', 'state_changed',
    '**knowledge_layer**', '**retention**', 'first_seen_counter',
    'second_seen_counter', 'reset_events', 'side_effects_on_repeat',
]

PRECEDENT_RULE = [
    '🔑 **"先例"应建模为访问次数与条件增量，而不是第二套流程**',
    '🔑 取证先测**第一次触发和第二次触发**，再测**新周目 · 新存档 · '
    '读档 · 回放 · 多人不同客户端**的差异',
    '🔴 **最容易错的是把"第一次"理解成布尔** —— '
    '玩家可能**看见提示但未选择 · 选择后读档 · 中途离开 · 重复进入又退出**',
    '🔑 必须测计数器在 **pressed · committed · 执行成功 · 剧情结束 · '
    '存档 · 读档**各相位如何变化',
]

# 历史源一致性
SRC_RULE = '🔑 **历史源的一致性必须成为测试对象，而非依赖人工判断**'

# 时间旅行
TT_ITEMS = [
    '回到过去**读取什么**（快照？重放？重建？）',
    '过去是否被**重新序列化**',
    '改变过去后**当前如何更新**',
    '**因果链是否被校验**',
    '回到过去**能否再次触发先例**',
]

# 🔑 四层知识
KNOW_FOUR = [
    ('**角色可见**', '主角能看见 · 使用 · 自然想象出的信息',
     '呼吸 · 步态 · 屏幕晕染'),
    ('**玩家可见**', '世界观无法解释但玩家必须使用的功能',
     '数字 · 血条 · 地图'),
    ('**系统可见**', '系统层面记录但两侧都不直接呈现', '后台日志 · 调试'),
    ('**元层可见**', '跨周目 · 跨存档 · 玩家本人的知识',
     '成就 · "你曾经选过这个"'),
]

KNOW_RULE = [
    '🔑 **玩家—角色边界是四种知识，而不是一个开关**',
    '🔑 同一个生命值，可能在角色侧表现为**呼吸 · 步态 · 屏幕晕染**，'
    '在玩家侧表现为**数字 · 血条 · 调试 HUD**',
    '🔴 复刻时若为了统一可读性把三者**合成一套通用 HUD**，'
    '可能**消除原版故意制造的角色无知 · 信息过载或破墙感**',
]

# 🔴 重玩提示
REPLAY2_RULE = '🔑 **"重玩提示"必须明确是角色能力还是元层提示** —— '
'二周目玩家知道答案、角色不知道时，🔴 **UI 是否提示"你曾经选过这个"'
'必须逐项测量**'

# 元进度
META_ITEMS = [
    '哪些是"**玩家**"的（跨周目保留）',
    '哪些是"**角色**"的（随周目重置）',
    '哪些是"**机器/账号**"的（档案隔离域）',
    '解锁的**归属与可见性**',
    '**NG+ 契约**归谁',
]

META_RULE = '🔴 **元进度必须分类，'
'不能写成一个"跨周目保留"布尔**'

# 破墙
WALL_ITEMS = [
    '角色**直接对玩家说话**',
    '**系统级提示**（成就弹窗打断叙事）',
    'UI **承认自己是 UI**',
    '**读档时角色是否"知道"自己死过**',
    '**打破的是哪一面墙**（角色↔玩家？世界↔系统？）',
]

# 🔑 地标
MARK_FIVE = [
    ('**几何显著性**', '高度 · 轮廓 · 颜色 · 发光 · 声音'),
    ('**画面显著性**', '距离 · 遮挡 · LOD · 天气 · 昼夜 · 镜头裁切'),
    ('**语义显著性**', '目标 · 危险 · 唯一性 · 叙事'),
    ('**拓扑显著性**', '是否分隔区域 · 是否可见多条路径'),
    ('**认知显著性**', '玩家是否多次经过 · 是否成为习惯定位点'),
]

MARK_TEST = '最近 · 中距 · 远景 · 小地图 · 过场 · 分屏 · VR · '
'照片模式 · 低画质'

MARK_RULE = [
    '🔑 **地标不是美术资产，而是可被玩家定位的节点**',
    '🔑 必须测同一地标在 ' + MARK_TEST + ' 下**是否仍具有原版显著性**',
    '🔴 **高度被降低 · 颜色被统一 · 发光被剔除 · 细节被 LOD 移除**，'
    '**都会改变玩家认知地图**',
]

# 区域签名
SIG_SIX = [
    ('**视觉签名**', '色温 · 饱和度 · 明度 · 材质 · 轮廓'),
    ('**空间签名**', '尺度 · 垂直性 · 路径宽度 · 视线通廊'),
    ('**听觉签名**', '环境层 · 混响 · 声源 · 音乐'),
    ('**时间签名**', '昼夜 · 天气 · NPC 节奏'),
    ('**玩法签名**', '可交互物 · 资源 · 敌人 · 移动方式'),
    ('**叙事签名**', '身份 · 日常 · 行为痕迹'),
]

SIG_RULE = [
    '🔑 区域签名要测"**为何一进入就认得**"',
    '🔑 原版可能用**一束光代替 HUD 引导**，也可能让**风向 · 声音 · '
    '角色反应**形成路径',
    '🔴 复刻若把这些改成**箭头或任务标记，属于明显偏离**',
    '🔴 反之，**如果原版本身有显式标记，也不能为了"环境叙事"擅自删除**',
]

# 场景永久变化
PERM_RULE = '🔑 场景永久变化必须测**所有权 · 可见性 · 一致性** —— '
'破坏后是否永久？读档后呢？周目后呢？其他玩家可见吗？'

# 🔑 难度八维
DIFF_EIGHT = [
    ('**目标承受力**', '生命 · 护甲 · 容错 · 恢复'),
    ('**输出威胁**', '伤害 · 破防 · DOT · 击退 · 即死'),
    ('**AI 智能**', '感知 · 决策 · 协作 · 资源管理'),
    ('**资源丰度**', '掉落 · 商店 · 补给 · 耐久'),
    ('**压力结构**', '敌人数量 · 波次 · 时间 · 同时攻击数'),
    ('**信息透明度**', '地图 · 高亮 · 提示 · 伤害数字'),
    ('**容错与惩罚**', '死亡损失 · 读档成本 · 连击重置'),
    ('**输入/执行负担**', '辅助瞄准 · 窗口长度 · 输入延迟 · 镜头速度'),
]

DIFF_RULE = [
    '🔑 **难度应拆成八维**，每个档位**必须列出实际系数**，'
    '🔴 **而不是"敌人更强"**',
    '🔑 已有资料显示不同难度**同时改变战斗 · 探索 · 解谜 · 辅助 · '
    '补给 · 提示和 HUD**；最高难度还可**锁定且改变死亡惩罚**',
    '🔴 **原版若如此，复刻必须逐项复刻，不能只保留敌人血量和伤害**',
]

# 🔴 中途调整七种语义
MID_SEVEN = [
    '**立即对新实体生效**',
    '**下一区域**生效',
    '**当前战斗结算后**生效',
    '**读档点后**生效',
    '**同帧生效并回滚进行中数值**',
    '**只允许更高或只允许更低**',
    '**仅新周目**生效',
]

MID_TEST = '当前血量与上限 · 护盾 · DOT · 冷却 · buff · AI · 补给 · 死亡计数'

MID_RULE = '🔑 必须测 ' + MID_TEST + ' **在调整瞬间如何变化**；'
'🔴 **若血量超过新上限，是截断 · 保留超额 · 暂时不扣 · 还是只扣到 1，'
'都是不同行为**'

# 隐藏参数
HIDDEN_RULE = '🔑 **隐藏参数必须完整反解** —— '
'模板应记录每个滑块**实际改动哪些行**，并与菜单文本**逐行对账**'

# 公平性
FAIR_FOUR = [
    '**可预测性**（敌人行为是否可预判）',
    '**可归因性**（玩家能否知道自己为什么死）',
    '**可恢复性**（失败后能否补救）',
    '**一致性**（同样操作是否总有同样结果）',
]

FAIR_RULE = '🔑 公平性必须分成**四种可测属性** —— '
'高难度是"**更聪明**"还是"**数值更高**"？**玩家能否感知**？'

# 🔴 等待十二事实
WAIT_TWELVE = [
    '**是否可以跳过**',
    '**等待单位**（现实秒 · 游戏小时 · 睡眠 · 天气周期）',
    '**表现**（黑屏 · 淡入 · 过场 · 加速 · 静态镜头）',
    '**输入是否冻结**',
    '**是否只推进模拟而不推进时钟**',
    '**时钟推进是否离散**',
    '**同时推进的子系统**',
    '**是否保留玩家位置**',
    '**是否允许镜头 · 菜单 · 装备 · 存档**',
    '**等待中能否死亡**',
    '**等待后 NPC · 商店 · 天气如何更新**',
    '**快速等待的最小/最大步长**',
]

WAIT_RULE = [
    '🔑 如果原版在等待时让玩家**被攻击 · 消耗燃料 · 错过事件**，'
    '它是**有意风险**',
    '🔑 如果等待只是黑屏加载，也必须在**同帧 · 同输入窗口 · 同副作用**'
    '层面复刻',
]

# 🔑 原子性
ATOMIC_RULE = '🔑 等待可能造成**四类时间不连续**：现实时间 · 游戏时钟 · '
'模拟相位 · 镜头/过场时间**各自前进不同量**'
ATOMIC_KEY = '🔴 **一个特别细但致命的问题**：等待是否允许"**跨过**"'
'一个只持续**一帧或极短窗口**的事件 —— '
'🔑 "**跳过**"若把整个时间片作为**原子提交**，'
'**可能错过原版逐 tick 检查**'

# 收集
COLL_ITEMS = [
    '收集品的**发现**（是否可见 · 是否需要探索 · 提示）',
    '**进度反馈**（已收集 X/Y？未完成的是否显示位置）',
    '**奖励**（即时还是延迟？是否与完成度挂钩）',
    '**遗漏惩罚**（错过是否可补？是否影响结局/成就）',
    '**叙事价值**（是否承载故事？重制后是否保留）',
]

COLL_RULE = '🔑 收集的差异在**遗漏语义**与**提示公平性** —— '
'🔴 重制常改变收集品位置或提示方式，"**收集体验**"完全不同'

# 🔑 涌现
EME_ITEMS = [
    '**涌现式玩法**（物理利用 · AI 利用 · 技能组合）',
    '**是否可复现**（重制后同样的利用是否成立）',
    '**"良性 bug"是否保留**',
    '**涌现与"修复"的冲突**（修 bug 是否消灭了涌现）',
]

EME_RULE = '🔑 应建立**涌现最小复现链**模板；'
'🔴 **重制常"修复"掉涌现，社区玩法消失**'

# H
H_TEN = [
    ('**9.1 NPC 私人空间与"礼貌物理"**',
     '座位 · 工位 · 床 · 队列 · 行走偏好 · 玩家不可进入的私人空间。'
     '🔴 重制常把 NPC 当资源点，**删掉私人生活半径与社交回避**'),
    ('**9.2 工作"取得进展但从不完成"**',
     '定居点 NPC 循环工作，玩家看到推进却永不完工 —— '
     '🔴 **直接改成"任务完成"会消除时间流动感**'),
    ('**9.3 宠物/伙伴跟随三态**',
     '**可通行 · 需等待 · 永久阻断**。🔴 伙伴"更聪明"'
     '**不能擅自变成会开门 · 替玩家解谜 · 提供额外信息**'),
    ('**9.4 坐骑输入到动作四段管道**',
     '**输入意图 · 骑乘状态 · 动物响应 · 镜头跟随**必须分开。'
     '🔴 只换动画不改物理 → "**脚滑**""**黏地**""**镜头穿墙**"'),
    ('**9.5 照片模式冻结语义**',
     '🔑 **照片模式不是暂停**。🔴 **暂停菜单截图和真正照片模式'
     '常是两套状态机**'),
    ('**9.6 昼夜生态是多系统耦合**',
     '同时影响生物作息 · 玩家属性 · 技能 · 掉落 · NPC · 交通 · 混响 · '
     '可见性 · 温度 · 事件。🔴 **不能只复刻天空颜色**'),
    ('**9.7 菜单/过场/游戏内时钟三套速度**',
     '时间可能分别驱动动画 · 模拟 · HUD。🔴 只同步表面显示'
     '会让植物生长 · NPC 日程 · 任务窗口错位'),
    ('**9.8 场景"身份—日常—痕迹"三层证据**',
     '身份回答空间是什么，日常回答正常运转，痕迹回答刚发生什么。'
     '🔑 取证顺序应**从物体状态倒推事件**，🔴 **不是直接记录开发者文本**'),
    ('**9.9 首次发现与重复发现的不同文本**',
     '要记访问计数 · 玩家是否已解谜 · 角色是否知道答案。'
     '🔴 **把重复文本合成一条会丢失玩家知识成长的体现**'),
    ('**9.10 危险物在等待中的状态**',
     '地雷 · 陷阱 · 毒区 · 警报 · 敌人 · 火源在等待时是继续 · 暂停 · '
     '还是批量推进。🔴 **原版若让等待"安全地"跳到白天，'
     '复刻不能让玩家在等待中仍被夜间机制杀死**'),
]

CONFLICTS = [
    '❌ **把等待做成"优化后的快速黑屏"**（原版有意为之）',
    '❌ **把门卡住"修复"成流畅**（紧张感是设计）',
    '❌ **简单模式不能解锁完整内容却擅自改成完整通关**',
    '❌ 把"第一次"当布尔（须访问计数与相位）',
    '❌ **因"剧情上应该记得"就推断代码会记住**',
    '❌ 补成"更完整的历史系统"',
    '❌ **为统一可读性把角色侧/玩家侧合成通用 HUD**',
    '❌ 元进度写成"跨周目保留"单一布尔',
    '❌ **把地标当美术资产**（高度/颜色/发光被改＝认知地图改变）',
    '❌ 用箭头/任务标记替换环境引导',
    '❌ **为"环境叙事"擅自删除原版显式标记**',
    '❌ **难度只保留敌人血量和伤害**',
    '❌ 中途调难度不测七种语义',
    '❌ **伙伴"更聪明"到会开门/解谜**',
    '❌ **照片模式当暂停**（常是两套状态机）',
    '❌ **只复刻天空颜色**',
    '❌ 把重复文本合成一条',
    '❌ **"修复"掉涌现导致社区玩法消失**',
]

FIELDS = [
    ('item_id', '项编号'),
    ('domain', '域（hist / vis / prec / src / tt / know / replay2 / meta / '
               'wall / mark / sig / perm / diff / mid / hidden / fair / '
               'wait / atomic / coll / eme / h）'),
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


def cmd_hist(a):
    _hdr('🔑 世界历史（**三层证据**）')
    for k, why in HIST_THREE:
        print(f'   {k:<18} {why}')
    print('\n核心字段: ' + ' · '.join(HIST_FIELDS))
    print('\n规则:')
    for r in HIST_RULE:
        print(f'   {r}')
    return 0


def cmd_vis(a):
    _hdr('🔴 visibility_scope（**七级**）')
    print('   ' + ' · '.join(VIS_SCOPE))
    print('\n证据等级:')
    for k, why in EVIDENCE_LEVELS:
        print(f'   {k:<10} {why}')
    print(f'\n   {EVIDENCE_RULE}')
    return 0


def cmd_prec(a):
    _hdr('🔑 先例（**访问计数不是第二套流程**）')
    print('六种情况:')
    for p in PRECEDENT_SIX:
        print(f'   · {p}')
    print('\n模板字段: ' + ' · '.join(PRECEDENT_TEMPLATE))
    print('\n规则:')
    for r in PRECEDENT_RULE:
        print(f'   {r}')
    return 0


def cmd_src(a):
    _hdr('历史源（**一致性是测试对象**）')
    print(f'   {SRC_RULE}')
    return 0


def cmd_tt(a):
    _hdr('时间旅行')
    for t in TT_ITEMS:
        print(f'   · {t}')
    return 0


def cmd_know(a):
    _hdr('🔑 知识边界（**四层，不是一个开关**）')
    print(f'   {"层":<14}{"含义":<38}例子')
    print('   ' + '-' * 72)
    for k, why, ex in KNOW_FOUR:
        print(f'   {k:<14}{why:<38}{ex}')
    print('\n规则:')
    for r in KNOW_RULE:
        print(f'   {r}')
    return 0


def cmd_replay2(a):
    _hdr('🔴 重玩提示（**角色能力还是元层**）')
    print(f'   {REPLAY2_RULE}')
    return 0


def cmd_meta(a):
    _hdr('元进度（**不能写成单一布尔**）')
    for m in META_ITEMS:
        print(f'   · {m}')
    print(f'\n   {META_RULE}')
    return 0


def cmd_wall(a):
    _hdr('破墙（**打破什么**）')
    for w in WALL_ITEMS:
        print(f'   · {w}')
    return 0


def cmd_mark(a):
    _hdr('🔑 地标（**不是美术资产**）')
    for k, why in MARK_FIVE:
        print(f'   {k:<16} {why}')
    print(f'\n须测条件: {MARK_TEST}')
    print('\n规则:')
    for r in MARK_RULE:
        print(f'   {r}')
    return 0


def cmd_sig(a):
    _hdr('区域（**六字段签名**）')
    for k, why in SIG_SIX:
        print(f'   {k:<14} {why}')
    print('\n规则:')
    for r in SIG_RULE:
        print(f'   {r}')
    return 0


def cmd_perm(a):
    _hdr('场景永久变化')
    print(f'   {PERM_RULE}')
    return 0


def cmd_diff(a):
    _hdr('🔑 难度（**八维**）')
    for i, (k, why) in enumerate(DIFF_EIGHT, 1):
        print(f'   {i}. {k:<16} {why}')
    print('\n规则:')
    for r in DIFF_RULE:
        print(f'   {r}')
    return 0


def cmd_mid(a):
    _hdr('🔴 中途调整（**七种语义**）')
    for m in MID_SEVEN:
        print(f'   · {m}')
    print(f'\n须测: {MID_TEST}')
    print(f'\n   {MID_RULE}')
    return 0


def cmd_hidden(a):
    _hdr('隐藏参数（**必须完整反解**）')
    print(f'   {HIDDEN_RULE}')
    return 0


def cmd_fair(a):
    _hdr('公平性（**四种可测属性**）')
    for f in FAIR_FOUR:
        print(f'   · {f}')
    print(f'\n   {FAIR_RULE}')
    return 0


def cmd_wait(a):
    _hdr('🔴 等待（**十二事实** —— 它可能是玩法，不是加载）')
    for i, w in enumerate(WAIT_TWELVE, 1):
        print(f'   {i:>2}. {w}')
    print('\n规则:')
    for r in WAIT_RULE:
        print(f'   {r}')
    print(f'\n   {ATOMIC_RULE}')
    print(f'\n   {ATOMIC_KEY}')
    return 0


def cmd_atomic(a):
    _hdr('🔑 等待（**原子性**）')
    print(f'   {ATOMIC_RULE}')
    print(f'\n   {ATOMIC_KEY}')
    return 0


def cmd_coll(a):
    _hdr('收集（**遗漏语义与提示公平性**）')
    for c in COLL_ITEMS:
        print(f'   · {c}')
    print(f'\n   {COLL_RULE}')
    return 0


def cmd_eme(a):
    _hdr('🔑 涌现（**最小复现链**）')
    for e in EME_ITEMS:
        print(f'   · {e}')
    print(f'\n   {EME_RULE}')
    return 0


def cmd_h(a):
    _hdr('H 层（**十项新盲区**）')
    for k, why in H_TEN:
        print(f'\n   【{k}】\n      {why}')
    return 0


def cmd_init(a):
    os.makedirs(os.path.dirname(a.init) or '.', exist_ok=True)
    with open(a.init, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow([k for k, _ in FIELDS])
        w.writerow(['TODO'] * len(FIELDS))
    print(f'已生成纵深/难度表: {a.init}')
    print('\n⚠️ 二十一域：hist / vis / prec / src / tt / know / replay2 / '
          'meta / wall / mark / sig / perm / diff / mid / hidden / fair / '
          'wait / atomic / coll / eme / h')
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
    print(f'纵深/难度 · {len(rows)} 条')
    print('=' * 76)
    if mismatch:
        print(f'\n🚫 **不一致** {len(mismatch)} 条（行 {mismatch[:15]}）')
    if no_legacy:
        print(f'\n❌ {len(no_legacy)} 条缺**原版值**（行 {no_legacy[:15]}）')
    if no_grade:
        print(f'\n🚫 {len(no_grade)} 条**证据等级缺失或 ≥7 级**'
              f'（行 {no_grade[:15]}）')

    if not (mismatch or no_legacy or no_grade):
        print('\n✅ 纵深/难度：一致、原版值完整、证据等级达标')

    print('\n🔑 **先证明原版行为，再决定实现。'
    'A—H 是附加观察维度，不是新增功能域。**')
    print('   **「剧情上应该记得」不能推断代码会记住；'
    '难度不能只保留血量和伤害。**')
    print('   **等待若是有意风险，做成快速黑屏就是偏离而非现代化。**')
    return 1 if (a.gate_check and (mismatch or no_legacy or no_grade)) else 0


def main():
    ap = argparse.ArgumentParser(description='世界纵深与难度维度')
    ap.add_argument('--hist', action='store_true')
    ap.add_argument('--vis', action='store_true')
    ap.add_argument('--prec', action='store_true')
    ap.add_argument('--src', action='store_true')
    ap.add_argument('--tt', action='store_true')
    ap.add_argument('--know', action='store_true')
    ap.add_argument('--replay2', action='store_true')
    ap.add_argument('--meta', action='store_true')
    ap.add_argument('--wall', action='store_true')
    ap.add_argument('--mark', action='store_true')
    ap.add_argument('--sig', action='store_true')
    ap.add_argument('--perm', action='store_true')
    ap.add_argument('--diff', action='store_true')
    ap.add_argument('--mid', action='store_true')
    ap.add_argument('--hidden', action='store_true')
    ap.add_argument('--fair', action='store_true')
    ap.add_argument('--wait', action='store_true')
    ap.add_argument('--atomic', action='store_true')
    ap.add_argument('--coll', action='store_true')
    ap.add_argument('--eme', action='store_true')
    ap.add_argument('--h', action='store_true')
    ap.add_argument('--init')
    ap.add_argument('--check')
    ap.add_argument('--gate-check', action='store_true')
    a = ap.parse_args()
    fns = {'hist': cmd_hist, 'vis': cmd_vis, 'prec': cmd_prec, 'src': cmd_src,
           'tt': cmd_tt, 'know': cmd_know, 'replay2': cmd_replay2,
           'meta': cmd_meta, 'wall': cmd_wall, 'mark': cmd_mark,
           'sig': cmd_sig, 'perm': cmd_perm, 'diff': cmd_diff, 'mid': cmd_mid,
           'hidden': cmd_hidden, 'fair': cmd_fair, 'wait': cmd_wait,
           'atomic': cmd_atomic, 'coll': cmd_coll, 'eme': cmd_eme,
           'h': cmd_h}
    for k, fn in fns.items():
        if getattr(a, k):
            return fn(a)
    if a.init:
        return cmd_init(a)
    if a.check:
        return cmd_check(a)
    print('❌ 需要 --hist / --vis / --prec / --src / --tt / --know / '
          '--replay2 / --meta / --wall / --mark / --sig / --perm / --diff / '
          '--mid / --hidden / --fair / --wait / --atomic / --coll / --eme / '
          '--h / --init / --check 之一')
    return 2


if __name__ == '__main__':
    sys.exit(main())
