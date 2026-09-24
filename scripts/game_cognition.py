#!/usr/bin/env python3
"""心智地图 · 决策承诺 · 长时间游玩漂移 · 上手曲线 · 确定性信任 · 责任归因
（第四十一轮 A / B / C / D / E / F 类，含 G 补充）。

**🔑 本轮的视角**：
> 从"**玩家读出什么意义**"推进到
> "**玩家是否把意义装进了自己的记忆 · 肌肉与信任**"。

前四十轮已覆盖导航网格 · 选择延迟 · 撤销 · RNG · 读档重摇 · 微观节奏，
但尚缺四类"**意义发生后的状态**"：

1. 地标是否形成**可复述的坐标系**
2. 抉择是否携带**不可逆承诺**
3. 同一关卡玩**三小时后**玩家还能否听见 · 看见 · 按准
4. 前 **5 / 30 / 120 分钟**是否完成了必要的理解与顿悟

🔑 **客观可达性只能作为"玩家认知"的必要条件，不能代替玩家测试。**
> **"AI 能过去" ≠ "玩家知道能过去"**

用法:
  game_cognition.py --map     # 🔑 **心智地图**（不是 NavMesh）
  game_cognition.py --mark    # **地标是可回忆/可方向化/可复访的参考点**
  game_cognition.py --short   # 🔴 **捷径要记几何与记忆价值**
  game_cognition.py --lost    # 🔑 **迷路三种不同事件**
  game_cognition.py --vert    # 垂直空间是**认知层**
  game_cognition.py --commit  # 🔑 **决策的承诺语义**
  game_cognition.py --conseq  # **后果可见性四级，不是二元**
  game_cognition.py --irrev   # **不可逆五轴**
  game_cognition.py --ritual  # 仪式感是**可感知承诺**
  game_cognition.py --sl      # 🔴 **SL 可行性必须实测**
  game_cognition.py --drift   # 🔑 **长时间游玩漂移**
  game_cognition.py --habit   # **关键音频线索会被习惯化**
  game_cognition.py --auto    # 🔴 **操作自动化是精通也是故障源**
  game_cognition.py --onboard # **上手阻力曲线**
  game_cognition.py --trust   # 🔑 **统计公平 ≠ 主观可信**
  game_cognition.py --envel   # **成功包络，不是平均成功率**
  game_cognition.py --blame   # 🔑 **失败归因六方**
  game_cognition.py --g       # G 类八项
  game_cognition.py --init ledger/cognition.csv
  game_cognition.py --check ledger/cognition.csv --gate

退出码: 0 通过 / 1 缺项 / 2 用法错误
"""
import argparse
import csv
import os
import sys

# 🔑 A 心智地图
MAP_RULE = '🔑 **客观可达性只能作为"玩家认知"的必要条件，不能代替玩家测试。**'
MAP_WHY = '🔑 同一张 NavMesh 可以由不同**地标 · 颜色 · 声音 · 垂直节点**'
'形成完全不同的心智地图'
MAP_TWO = [
    ('**navmesh_topology**', '区域邻接图 · 分层连接 · 门与钥匙条件 · '
     '捷径两端 · 死胡同 · 回环'),
    ('**mental_map**', '🔑 **玩家侧证据**（另一张表）'),
]

MARK_RULE = '🔑 **地标不是美术清单，'
'而是可回忆 · 可方向化 · 可复访的参考点**'
MARK_FIELDS = [
    '地标 ID', '可见区域集合', '**可见距离分层（近/中/远）**',
    '**多方向轮廓差异**', '日/夜/天气可见性', '声音/灯光等动态成分',
    '命名与外观冲突', '遮挡体', '**首次揭示时间**',
    '**是否可作为"回程锚点"**',
]
MARK_REGRESS = '🔑 重制后要同时做"**视觉回归 + 认知回归**" —— '
'🔴 **只比较像素会漏掉**：远处塔被一棵新树挡住 15% · '
'广告牌光污染盖掉地平线轮廓 · 字体更改让路牌更难读 · '
'分辨率变化导致小地图图标与实景不对应'
MARK_WARN = '🔑 **此类变化对事实态可能毫无影响，却直接破坏表达态**'

SHORT_RULE = '🔑 **捷径必须同时记录几何与记忆价值**'
SHORT_WHY = '🔑 拓扑上只是边权更低的路径；'
'在玩家心智中必须同时具备**可发现性 · 可记住性 · 可复现性 · 可传授性**'
SHORT_FIELDS = [
    '`shortcut_id`', '`required_ability`', '`prerequisite_event`',
    '`first_discoverable_version`', '`round_trip_memory_test`',
    '`ambiguous_entrance`', '`audio_visual_signature`',
    '`claimed_by_players`', '`broken_in_remaster`',
]
SHORT_WARN = [
    '🔴 **"原版靠碰撞瑕疵形成的捷径"**：若严格修正，它便不再是原版承诺 —— '
    '此时 `must-match` 可能要求**保留**',
    '🔴 **重制无意中封锁的捷径属于回归 BUG**，'
    '🔴 **不应因"更整洁"而被解释为优化**',
]

LOST_RULE = '🔑 **迷路本身要被编码为三种不同事件**'
LOST_THREE = [
    ('**探索性迷路**', '玩家仍有候选路径 · 地标 · 方向感',
     '✅ 设计资产 → `intended_confusion = true`'),
    ('**可读性迷路**', '看见可去线索但**信息互相冲突**'
     '（所有门同色、所有走廊同比例）', '❌ `navigation_defect`'),
    ('**拓扑性迷路**', '无合法前进信息，或唯一路径依赖隐式碰撞',
     '❌ `navigation_defect`'),
]
LOST_SIGNALS = [
    '无目的折返', '同一节点多次重访', '持续打开地图', '求助频率',
    '方向键反复往返', '**平均路线长度 / 最优路线长度之比**',
    '口头/问卷中的"**我以为那是另一条路**"',
]

VERT_RULE = '🔑 **垂直空间是认知层，不是简单的 Z 轴**'
VERT_FIELDS = [
    '楼层编号', '**跨层视野**', '升降连接', '**上下声源**',
    '**跳下可回 / 跳下不可回**', '投影仪 · 天窗 · 井等"**反向确认物**"',
]
VERT_ASK = [
    '**穿越前能预测另一端吗**',
    '**穿越后知道自己在哪吗**',
    '**能否回到入口**',
]
VERT_WARN = '🔑 原版常利用"**从上层看见下层敌人**"让玩家提前形成回路；'
'🔴 **重制若只保留碰撞，最容易丢失的正是这种「俯视证据」**'

# 🔑 B 决策承诺
COMMIT_RULE = '🔑 **要记录的不是"有没有分支"，'
'而是玩家在那一刻是否知道：后果何时出现 · 由谁承担 · 能否撤销 · '
'撤销成本多少 · 承诺是否有二次确认**'
OPTION_FIELDS = [
    '`option_text`', '`summary_truth`', '**`order_position`**',
    '**`default_or_cursor_position`**', '`required_information_available`',
    '`consequence_visibility`', '`consequence_latency`', '`stake_type`',
    '`stake_preview`', '`who_sees_preview`', '`is_socially_constrained`',
]
OPTION_WARN = '🔑 **必须特别标出"默认选项"与"高亮选项"**：'
'原版"是/否"顺序 · 光标起始位 · 等待超时 · 方向键循环 · 确认键都可能改变选择'
OPTION_UI = '🔴 **重制更改字体宽度 · 按钮布局 · 手柄焦点环 · 触摸热区**，'
'都可能使原本偏左的"接受"变成偏右的"拒绝" —— **这是可辨态的硬细节**'

CONSEQ_FOUR = [
    ('**第一级**', '即时且明确（数值 · 状态 · 对话反应同步变化）'),
    ('**第二级**', '即时但需**玩家主动检查**（库存/关系/世界状态不自动提示）'),
    ('**第三级**', '**延迟后果**（数分钟后或数小时后才显现）'),
    ('**第四级**', '**系统后果**（经济 · 声望 · 可去区域 · 后续随机遭遇）'),
]
CONSEQ_WARN = '🔴 **只比较"是否执行回调"会把第四级判定为没有后果**'

WITHHELD = '🔑 **"原版故意隐瞒"不是低信息量，而是设计承诺**'
WITHHELD_VALS = [
    ('none', '无隐瞒'),
    ('**mechanical_telegraph**', '机制性暗示'),
    ('**narrative_ambiguity**', '叙事模糊'),
    ('**hidden_system**', '隐藏系统'),
    ('lack_of_polish', '完成度不足 —— 🔑 **只有这一项才可能转化为缺陷**'),
]
WITHHELD_RULE = '🔴 前三种均为 `must-match`。'
'若原版不给掉落率 · 不给伤害公式 · 不让玩家看到 NPC 真实意图，'
'🔴 **重刻不得为了"透明"而自动显示**（可单独做内部训练模式或开发层）'

IRREV_FIVE = ['**知识**', '**动作**', '**资源**', '**世界**', '**角色/结局**']
IRREV_FIELDS = [
    '`commitment_id`', '`available_from_version`',
    '`visible_irreversibility`', '`warning_text`', '`warning_timing`',
    '`warning_duration`', '`can_quit_without_commit`',
    '`can_reload_before_save`', '`can_undo_in_session`', '`remedy_kind`',
    '`remedy_cost`', '`downstream_effects`',
]
IRREV_EG = [
    '原版在**确认前**说"此后无法挽回"',
    '原版在**确认后不立即存档**',
    '原版让"拒绝"在**下一对话轮仍可改变**',
    '原版在**死亡后才写盘**',
]
IRREV_FRAME = '🔑 **必须逐帧记录确认框出现至输入锁定的窗口**'

RITUAL_RULE = '🔑 **仪式感是"可感知承诺"，不是装饰**'
RITUAL_ITEMS = [
    '二次确认是否**独占输入**', '是否暂停世界', '是否播放**不可逆音效**',
    '是否进入黑屏/特写', '是否写入永久档案', '是否显示计数器',
    '**是否阻断 Alt-Tab**',
]
RITUAL_EG = '🔑 **原版如果有 1.2 秒的关门声，重制缩短到 0.4 秒，'
'玩家可能不再感到选择落地，尽管状态机完全一致**'
RITUAL_NO = '🔴 反过来，**重制也不应擅自加入慢镜头 · 震动 · 音效**，'
'否则会把"普通选项"误升为"重大承诺"'

SL_RULE = '🔴 **SL 可行性必须被实测，而不是按开发者态度归类**'
SL_TEST = [
    '可手动存档点密度', '自动存档触发', '死亡后读档回退', '退出是否保存',
    '**状态是否在确认瞬间冻结**', '**随机数是否在事件开始前抽样**',
    '**多人主机是否拥有唯一存档**', '**云存档是否覆盖本地回滚**',
    '**崩溃恢复是否形成"伪不可逆"**',
]
SL_VALS = ['trivial', 'possible', 'costly', 'impossible']
SL_RECORD = '🔑 并记录**玩家实际重读次数 · 重读前后路线 · '
'失败/死亡前后的事件样本**'
SL_WARN = [
    '🔑 **若原版允许 SL，它就是玩法的一部分**，'
    '🔴 **不应因重制加入自动云同步而意外消除**',
    '🔴 若原版刻意让某些后果立即固化，也不能为"便利"改成可撤销',
]
REMEDY_SCOPE = ['**仅当前会话**', '**本存档**', '**本周目**', '**永久**']
REMEDY_WARN = '🔑 **重开整档是最高成本**；'
'🔴 **伪装成"补救"的软锁定仍属高后悔**'

# 🔑 C 长时间漂移
DRIFT_RULE = '🔑 **三小时后的"同一功能"可能已不是同一体验**'
DRIFT_WHY = '🔑 **短局测试能验证"第一次听见提示音"，'
'却不能验证玩家第 120 分钟是否仍把它识别为威胁**'
DRIFT_PHASES = [
    '0–15 min', '15–30 min', '30–60 min', '60–120 min', '**120–180+ min**',
]
DRIFT_RECORD = '🔑 每个阶段同时记录**输入 · 声音 · 视觉 · 注意力 · '
'主观负荷 · 游戏内部表现**'

HABIT_RULE = '🔑 **关键音频线索存在"被习惯化"的风险**'
HABIT_CLUES = [
    '低频脚步', '远处爆炸', '队友呼救', '低血量', '可破坏物崩塌',
    '**敌人发现声**',
]
HABIT_CHANGE = [
    '频谱', '动态范围', '压缩', '混音优先级', '空间化', '重复间隔',
    '音量衰减',
]
HABIT_TEST = ['检测率', '误报率', '反应时间', '**主观显著性**',
              '**是否转成视觉/触觉代偿**']
HABIT_WARN = '🔴 **若原版故意让某提示随时间变得含混，也必须保留** —— '
'🔴 **不得用"更清晰"自动覆盖**'

VISUAL_ITEMS = [
    '小字号', '细描边', '快速闪烁', '相近色', '低对比 HUD', '永久红边框',
    '受伤 vignette', '镜头抖动', '景深', '光晕', '粒子遮挡',
    '**同色敌人/可交互物**', '长时间注视同一界面',
]
VISUAL_RECORD = [
    '后段**错误点击率**', '注视时长', '眨眼/闭合指标', '视线分布',
    '**UI 盲区**', '**是否形成"只看局部区域"的自动化**',
]

AUTO_RULE = '🔑 **操作自动化既是精通，也是复刻故障源**'
AUTO_WHY = '🔑 玩家会形成"**看到 X 就按 Y**"的条件反射；'
'🔴 重刻若改键位 · 改输入窗口 · 改确认/取消 · 改振动 · 改镜头滞后 · '
'改移动容差，**即使单次手感测试合格，也可能在长期自动化后发生错位**'
AUTO_THREE = ['**首次执行**', '**熟练执行**', '**疲劳执行**']
AUTO_RECORD = [
    '输入序列熵', '按键重叠', '错误率', '取消率', '补救时间',
    '**死亡前最后输入**', '手指位移', '连续操作后的节奏漂移',
]
AUTO_TIP = '🔑 原版靠"**模糊输入窗口**"允许肌肉记忆时，**精确化不一定更友好**；'
'原版靠"**严格窗口**"形成技巧时，**放宽也不一定更公平**'
AUTO_UI = '🔴 **"自动化后不再看 UI"会造成二次认知迁移** —— '
'🔑 老玩家常**记住位置而非文字**，复刻若移动生命条 · 改变图标语义 · '
'增加动画 · 重排技能，🔴 **即使内容相同，也可能在疲劳时造成误放技能 · '
'误吞物品 · 误进商店**'

ATTENTION = '🔑 **注意力衰退应被视为与反应时间不同的指标**'
ATTENTION_ITEMS = [
    '反应时', '漏报', '误报', '微停顿', '**目标切换成本**', '空操作',
    '重复检查', '**分心恢复时间**',
]
ATTENTION_METHOD = '🔑 结论应来自**同任务前后的对照**，'
'🔴 而非一次疲劳自述'
ATTENTION_TLX = '🔑 NASA-TLX 六维自评（心理需求 · 身体需求 · 时间需求 · '
'表现 · 努力 · 挫败感）🔴 **更适合比较版本，不可把分数直接当神经疲劳诊断**'
ATTENTION_BIO = '🔑 生理指标应以**个体会话内偏差**表示，'
'🔴 **而非跨人比较绝对心率 · 皮电或脑电**'

REST_FIELDS = [
    '暂停是否真正停时', '是否有快速存盘', '自动存盘点是否靠近退出',
    '退出到重进时间', '**重进后的目标记忆**', '音频/音乐重启点',
    '镜头/角色位置', 'HUD 状态', '任务提示', '手柄连接', '多显示器焦点',
    '挂机惩罚', '睡眠/待机恢复', '崩溃恢复',
]
REST_Q = '🔑 **最重要的体验问题：「重开游戏后我还能不能立刻想起自己要做什么」**'
'—— 要记录回归后 **10 / 30 / 60 秒**的导航与任务恢复动作'
DRIFT_CONFLICT = [
    '❌ **自动降低难度**', '❌ **自动放大关键 UI**',
    '❌ **动态调整摄像机或声音**',
    '❌ **疲劳后弹出"休息一下"并自动存盘**',
]
DRIFT_NOTE = '🔑 **耐力本身是游戏意义的一部分；"更舒适"不等于"更忠实"。**'
'🔑 若提供这些，应做成**与原版互斥的模式，而不是静默覆盖**'

# D 上手曲线
ONBOARD_RULE = '🔑 **留存不是目标，前段理解完成度才是**'
ONBOARD_CLOCK = ['**前 5 分钟**', '**前 30 分钟**', '**前 2 小时**']
ONBOARD_ASK = [
    '各阶段**给什么**',
    '**顿悟时刻的位置**（重制后是否提前或延后）',
    '**上手阻力的来源**（复杂操作 · 术语 · UI · 数值）',
    '**"卡住"的时点与类型**',
]
ONBOARD_THREE = ['**发现**', '**理解**', '**掌握**']

# 🔑 E 信任
TRUST_RULE = '🔑 **统计公平与主观可信是两本账**'
TRUST_WHY = '🔑 **代码可重复 ≠ 玩家相信可重复**；'
'🔑 **随机符合概率 ≠ 玩家觉得公平**'
TRUST_PHYS = '🔑 **物理可重复性应测"玩家可学会的成功边界"** —— '
'固定输入序列 · 固定资源 · 固定角色状态下 **N 次**投掷/跳跃/连招/碰撞'
TRUST_RECORD = [
    '首次成功到连续成功', '**失败后的修正方向**',
    '**玩家是否把成功归于时机/位置/版本/运气**',
]
TRUST_WARN = '🔑 原版若因浮点 · 帧率 · 输入缓冲存在**隐性窗口**，'
'复刻必须保留或明确偏离'
TRUST_BOTH = [
    '🔴 **精确锁帧的"确定性"若破坏原版的可学习窗口，不应无条件赞许**',
    '🔴 **宽松窗口若变成新引擎下随机不可复现，也不应无条件保留**',
]

ENVEL_RULE = '🔑 **技巧可学习性可量化为成功包络，而不是平均成功率**'
ENVEL_FIELDS = [
    '输入时间', '位置', '角度', '速度', '帧序', '碰撞状态', '环境参数',
    '输出结果',
]
ENVEL_FIT = '🔑 拟合"**成功输入集**"并比较**中心 · 边界 · 允许抖动 · '
'失败梯度**'
ENVEL_KEY = '🔑 **原版玩家真正信任的是"边界附近的小修正有效"** —— '
'🔴 **重刻即使平均成功率相同，只要边界移动或梯度变陡，就会感觉不可控**'

RAND_TWO = [
    ('**机制层**', '样本分布 · 稀有事件间隔 · 条件概率显示 · 连败保护 · '
     '洗牌算法 · 状态依赖 · 重读档影响'),
    ('**体验层**', '玩家预期 · 惊讶 · 归因 · 是否主动重投 · 是否改变策略'),
]
RAND_SPLIT = '🔑 **必须区分"短序列看起来不公"和"代码概率错误"** —— '
'前者可能是**表达问题**，后者才是 BUG'
RAND_KEEP = '🔴 若原版隐藏概率，**重刻不得自动公开**；'
'若原版显示概率但 UI 误导，也应作为**历史表达记录**，🔴 **不能直接"修正"**'

BOUND_RULE = '🔑 **"我以为能过"的边界，是可见判定与玩家直觉的冲突**'
BOUND_RECORD = [
    '角色判定盒', '目标判定盒', '伤害/成功判定', '**视觉边缘**',
    '**动画承诺帧**', '**玩家自述边界**',
]
BOUND_CHECK = [
    '装饰性最外点', '**披风/头发/特效**', '斜坡边缘', '移动平台',
    '**相机透视**', '镜头裁切', '动态分辨率', '角色朝向', '动画取消',
]
BOUND_NOTE = '🔑 这里的 `must-match` **不是保留错误，而是原版实际成立的边界** —— '
'🔴 **让判定更紧或更松，都属于偏离**'
TRUST_BOTH_FIELDS = '🔑 脚本应同时输出**统计可信度**（卡方/KS/序列相关）'
'与**主观可信度**（预期—结果差 · 归因类别），'
'🔑 **只有两者都在阈值内才可称"信任等价"**'

# 🔑 F 归因
BLAME_RULE = '🔑 **清晰数据不一定带来公平感，'
'但模糊系统一定制造猜测**'
BLAME_SIX = ['**操作者**', '**系统**（延迟/判定/服务器）', '**队友**',
             '**对手**', '**随机**', '**设备**']
BLAME_RECORD = [
    '可见信息', '被隐藏信息', '玩家陈述', '**事后回放是否改变判断**',
    '投票/踢出/抱怨行为',
]
BLAME_WARN = '🔑 **多人回放若只显示服务器真相而不显示客户端当时可见状态，'
'会让玩家正确感到"我被打得没道理"** —— '
'🔑 **必须把 client view 与 server truth 分轨记录**'

BLAME_DATA = [
    '伤害数字', '治疗', '助攻', '承伤', '站位', '资源贡献', '目标贡献',
    '复活', '控制时间', '**死亡责任**', '撤离', '购买', '**是否显示 ID**',
    '**是否显示延迟**', '是否显示输入',
]
BLAME_NO = '🔴 **重刻不得为"公平"新增 leaderboard · 评分 · MVP · '
'伤害排名 · 连接质量条 · 死亡原因**'
BLAME_REVERSE = '🔑 反过来，**原版有模糊归因而重刻只是提高精度，'
'也需审查是否改变团队压力**'

BLAME_PUBLIC = [
    '数据可见范围', '默认公开', '可隐藏', '评价是否匿名', '是否永久',
    '是否关联账号', '是否允许编辑', '是否可申诉', '踢出门槛', '主机权限',
    '弃赛/断线判定', '掉线后回滚',
]
BLAME_EMO = '🔑 **若原版随机 ID 让指责变弱，复刻改成实名稳定 ID，'
'🔴 即使技术上更准确，也改变了情绪体验**'

ASYM_LAYERS = [
    '地图信息', '敌人信息', '资源信息', '任务状态', '对话选择',
    '客户端预测', '**服务器秘密**', '旁观者信息', '跨平台可见性',
]
ASYM_ASK = '🔑 字段记"**谁知道 · 何时知道 · 如何知道 · 能否向队友证明**"'
ASYM_WARN = '🔴 **重刻统一多端视角 · 给旁观者更多数据 · 默认显示延迟，'
'可能打破原版的欺骗/合作结构**'

G_EIGHT = [
    ('**G1 跨周目"第二世界知识"**',
     '🔑 二周目玩家知道捷径 · 敌人 · 结局与**谎言**；'
     '🔴 **复刻若按新玩家重排难度，会破坏元游戏承诺**'),
    ('**G2 玩家身体的摆放与环境**',
     '坐姿 · 手柄握持 · 掌机重量分布 · 散热 · 风扇噪声 · 线材 · '
     '桌面高度 · 站立/坐姿 · 光照反射。'
     '🔑 跨平台尤其要记**外设 ergonomics**，而非只记输入设备型号'),
    ('**G3 旁观者 · 直播 · 共创空间**',
     '观众提示 · 弹幕协作 · 围观屏幕 · 排位观战 · 赛事 OB · 云串流压缩。'
     '🔑 记**延迟 · 信息泄露 · 可发言对象 · 敏感任务可见性 · '
     '键位/库存隐私 · 观战相机**。🔴 **自动加入观众投票会改变原版独占决策**'),
    ('**G4 版本记忆与怀旧校准**',
     '🔑 玩家口中的"原版"常混合**童年设备 · CRT · 低帧率 · 压缩音频 · '
     '早期补丁 · fan patch**；应建 `reference_edition`（原始介质 · 系统 · '
     '分辨率 · 刷新率 · 音频硬件 · 控制器 · 地区 · 补丁哈希）'),
    ('**G5 错误记忆与"曼德拉效应"**',
     '玩家可能记得**不存在的捷径 · 更明亮的配色 · 更难的 BOSS · 更长的音乐**。'
     '🔴 `claimed_by_memory` 必须与 `verified_in_build` 分开；'
     '访谈同时记"我确定 / 我大概记得 / 我听说"'),
    ('**G6 时间同步之外的"生活时间"**',
     '课堂 · 网吧 · 客厅 · 通勤；🔑 记**设备使用场景 · 通知中断 · '
     '家庭账户切换 · 家长控制 · 共享主机 · 跨设备继续 · 电量/网络变化**。'
     '🔴 **它们不是周边背景，而直接影响死亡重试 · 保存 · 节奏 · 社交**'),
    ('**G7 文化映射与"外国感"**',
     '单位 · 禁忌符号 · 宗教/政治标记 · 历史地名 · 俚语 · 性别称谓 · '
     '死亡/鬼魂 · 动物 · 食物 · 身体 · 数字 · 颜色 · 手势 · 领土。'
     '🔑 复刻**不是机械翻译，而是先记录原版符号的本土意义**；'
     '有争议时可保留原版并做非默认注释'),
    ('**G8 竞技与排位压力**',
     '排名可见性 · 连胜保护 · 掉段 · 禁选 · 举报 · 行为分 · 代练 · '
     '跨平台输入差异 · 服务器选择 · 观战 · 回放举报。'
     '🔑 应记**原版是否公开这些信号**；'
     '🔴 **新增"反 toxicity"功能若改变羞辱与责任结构，不能自动算修复**'),
]

CONFLICTS = [
    '❌ **自动降低难度**',
    '❌ **自动放大关键 UI**',
    '❌ **动态调整摄像机或声音**',
    '❌ **疲劳后弹"休息一下"并自动存盘**',
    '❌ **为"透明"自动显示原版故意隐瞒的信息**',
    '❌ **为"便利"把原版固化的后果改成可撤销**',
    '❌ **因加入自动云同步而意外消除 SL 玩法**',
    '❌ **擅自加入慢镜头/震动/音效**（把普通选项误升为重大承诺）',
    '❌ **严格修正"碰撞瑕疵形成的捷径"**',
    '❌ 把重制无意封锁的捷径**解释为"优化"**',
    '❌ **只比较像素而漏掉认知回归**',
    '❌ **把"更清晰"覆盖原版故意含混的提示**',
    '❌ **精确化模糊输入窗口 / 放宽严格技巧窗口**（都是偏离）',
    '❌ **让判定更紧或更松**（原版实际成立的边界才是 must-match）',
    '❌ **为"公平"新增 leaderboard / MVP / 伤害排名 / 死亡原因**',
    '❌ **把实名稳定 ID 替换随机 ID**',
    '❌ **统一多端视角 / 给旁观者更多数据**',
    '❌ **二周目按新玩家重排难度**',
    '❌ **静默覆盖原版耐力承诺**',
]

FIELDS = [
    ('item_id', '项编号'),
    ('domain', '域（map / mark / short / lost / vert / commit / conseq / '
               'irrev / ritual / sl / drift / habit / auto / onboard / '
               'trust / envel / blame / g）'),
    ('legacy_value', '**原版值**'),
    ('new_value', '新引擎值'),
    ('match', '**是否一致**'),
    ('player_side', '**玩家侧证据**（可辨态/记忆/信任）'),
    ('evidence', '证据等级 1-8'),
]


def _hdr(t, w=80):
    print('=' * w)
    print(t)
    print('=' * w)


def cmd_map(a):
    _hdr('🔑 心智地图（**不是 NavMesh**）')
    print(f'   {MAP_RULE}')
    print(f'\n   {MAP_WHY}')
    print('\n两张表:')
    for k, v in MAP_TWO:
        print(f'   {k:<22} {v}')
    return 0


def cmd_mark(a):
    _hdr('地标（**可回忆 · 可方向化 · 可复访**）')
    print(f'   {MARK_RULE}')
    print('\n字段: ' + ' · '.join(MARK_FIELDS))
    print(f'\n   {MARK_REGRESS}')
    print(f'\n   {MARK_WARN}')
    return 0


def cmd_short(a):
    _hdr('捷径（**几何 + 记忆价值**）')
    print(f'   {SHORT_RULE}')
    print(f'\n   {SHORT_WHY}')
    print('\n字段: ' + ' · '.join(SHORT_FIELDS))
    print('\n警告:')
    for w in SHORT_WARN:
        print(f'   {w}')
    return 0


def cmd_lost(a):
    _hdr('🔑 迷路（**三种不同事件**）')
    print(f'   {LOST_RULE}')
    print('\n三分类:')
    for k, w, v in LOST_THREE:
        print(f'   {k:<18} {w}')
        print(f'   {"":<18} → {v}')
    print('\n判别信号: ' + ' · '.join(LOST_SIGNALS))
    return 0


def cmd_vert(a):
    _hdr('垂直空间（**认知层**）')
    print(f'   {VERT_RULE}')
    print('\n字段: ' + ' · '.join(VERT_FIELDS))
    print('\n每次穿越必答: ' + ' · '.join(VERT_ASK))
    print(f'\n   {VERT_WARN}')
    return 0


def cmd_commit(a):
    _hdr('🔑 决策（**承诺语义**）')
    print(f'   {COMMIT_RULE}')
    print('\n选项字段: ' + ' · '.join(OPTION_FIELDS))
    print(f'\n   {OPTION_WARN}')
    print(f'\n   {OPTION_UI}')
    return 0


def cmd_conseq(a):
    _hdr('后果可见性（**四级**）')
    for k, v in CONSEQ_FOUR:
        print(f'   {k:<12} {v}')
    print(f'\n   {CONSEQ_WARN}')
    print(f'\n   {WITHHELD}')
    print('\n`information_withheld_reason`:')
    for k, v in WITHHELD_VALS:
        print(f'   {k:<26} {v}')
    print(f'\n   {WITHHELD_RULE}')
    return 0


def cmd_irrev(a):
    _hdr('不可逆（**五轴**）')
    print('五轴: ' + ' · '.join(IRREV_FIVE))
    print('\n字段: ' + ' · '.join(IRREV_FIELDS))
    print('\n会改变主观重量的情形:')
    for e in IRREV_EG:
        print(f'   · {e}')
    print(f'\n   {IRREV_FRAME}')
    return 0


def cmd_ritual(a):
    _hdr('仪式感（**可感知承诺**）')
    print(f'   {RITUAL_RULE}')
    print('\n必录: ' + ' · '.join(RITUAL_ITEMS))
    print(f'\n   {RITUAL_EG}')
    print(f'\n   {RITUAL_NO}')
    return 0


def cmd_sl(a):
    _hdr('🔴 SL 可行性（**必须实测**）')
    print(f'   {SL_RULE}')
    print('\n必测: ' + ' · '.join(SL_TEST))
    print('\n取值: ' + ' · '.join(SL_VALS))
    print(f'\n   {SL_RECORD}')
    print('\n警告:')
    for w in SL_WARN:
        print(f'   {w}')
    print('\n补救范围: ' + ' · '.join(REMEDY_SCOPE))
    print(f'\n   {REMEDY_WARN}')
    return 0


def cmd_drift(a):
    _hdr('🔑 长时间漂移（**三小时后**）')
    print(f'   {DRIFT_RULE}')
    print(f'\n   {DRIFT_WHY}')
    print('\n阶段: ' + ' · '.join(DRIFT_PHASES))
    print(f'\n   {DRIFT_RECORD}')
    print('\n❌ 冲突做法:')
    for c in DRIFT_CONFLICT:
        print(f'   {c}')
    print(f'\n   {DRIFT_NOTE}')
    return 0


def cmd_habit(a):
    _hdr('听觉习惯化（**关键线索会消失**）')
    print(f'   {HABIT_RULE}')
    print('\n线索: ' + ' · '.join(HABIT_CLUES))
    print('\n会改变适应的量: ' + ' · '.join(HABIT_CHANGE))
    print('\n采样指标: ' + ' · '.join(HABIT_TEST))
    print(f'\n   {HABIT_WARN}')
    print('\n视觉: ' + ' · '.join(VISUAL_ITEMS))
    print('\n记录: ' + ' · '.join(VISUAL_RECORD))
    return 0


def cmd_auto(a):
    _hdr('🔴 操作自动化（**精通也是故障源**）')
    print(f'   {AUTO_RULE}')
    print(f'\n   {AUTO_WHY}')
    print('\n三类状态: ' + ' · '.join(AUTO_THREE))
    print('\n记录: ' + ' · '.join(AUTO_RECORD))
    print(f'\n   {AUTO_TIP}')
    print(f'\n   {AUTO_UI}')
    print(f'\n   {ATTENTION}')
    print('   指标: ' + ' · '.join(ATTENTION_ITEMS))
    print(f'   {ATTENTION_METHOD}')
    print(f'   {ATTENTION_TLX}')
    print(f'   {ATTENTION_BIO}')
    print('\n休息恢复: ' + ' · '.join(REST_FIELDS))
    print(f'\n   {REST_Q}')
    return 0


def cmd_onboard(a):
    _hdr('上手曲线（**理解完成度**）')
    print(f'   {ONBOARD_RULE}')
    print('\n时点: ' + ' · '.join(ONBOARD_CLOCK))
    print('\n三段: ' + ' · '.join(ONBOARD_THREE))
    print('\n必答:')
    for o in ONBOARD_ASK:
        print(f'   · {o}')
    return 0


def cmd_trust(a):
    _hdr('🔑 信任（**两本账**）')
    print(f'   {TRUST_RULE}')
    print(f'\n   {TRUST_WHY}')
    print(f'\n   {TRUST_PHYS}')
    print('\n记录: ' + ' · '.join(TRUST_RECORD))
    print(f'\n   {TRUST_WARN}')
    print('\n两边都不能无条件:')
    for t in TRUST_BOTH:
        print(f'   {t}')
    print('\n随机两层:')
    for k, v in RAND_TWO:
        print(f'   {k:<12} {v}')
    print(f'\n   {RAND_SPLIT}')
    print(f'\n   {RAND_KEEP}')
    print(f'\n   {TRUST_BOTH_FIELDS}')
    return 0


def cmd_envel(a):
    _hdr('成功包络（**不是平均成功率**）')
    print(f'   {ENVEL_RULE}')
    print('\n字段: ' + ' · '.join(ENVEL_FIELDS))
    print(f'\n   {ENVEL_FIT}')
    print(f'\n   {ENVEL_KEY}')
    print(f'\n   {BOUND_RULE}')
    print('\n记录: ' + ' · '.join(BOUND_RECORD))
    print('\n必查: ' + ' · '.join(BOUND_CHECK))
    print(f'\n   {BOUND_NOTE}')
    return 0


def cmd_blame(a):
    _hdr('🔑 责任归因（**六方**）')
    print(f'   {BLAME_RULE}')
    print('\n六方: ' + ' · '.join(BLAME_SIX))
    print('\n每次失败记录: ' + ' · '.join(BLAME_RECORD))
    print(f'\n   {BLAME_WARN}')
    print('\n数据粒度: ' + ' · '.join(BLAME_DATA))
    print(f'\n   {BLAME_NO}')
    print(f'\n   {BLAME_REVERSE}')
    print('\n公开数据: ' + ' · '.join(BLAME_PUBLIC))
    print(f'\n   {BLAME_EMO}')
    print('\n信息不对称分层: ' + ' · '.join(ASYM_LAYERS))
    print(f'\n   {ASYM_ASK}')
    print(f'\n   {ASYM_WARN}')
    return 0


def cmd_g(a):
    _hdr('G 类（**八项**）')
    for k, why in G_EIGHT:
        print(f'\n   【{k}】\n      {why}')
    return 0


def cmd_init(a):
    os.makedirs(os.path.dirname(a.init) or '.', exist_ok=True)
    with open(a.init, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow([k for k, _ in FIELDS])
        w.writerow(['TODO'] * len(FIELDS))
    print(f'已生成认知与耐力表: {a.init}')
    print('\n⚠️ 十八域：map / mark / short / lost / vert / commit / conseq / '
          'irrev / ritual / sl / drift / habit / auto / onboard / trust / '
          'envel / blame / g')
    print('\n⚠️ `player_side` 列＝**玩家侧证据**（可辨态/记忆/信任）')
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

    mismatch, no_legacy, no_player, no_grade = [], [], [], []
    for i, r in enumerate(rows, 1):
        m = g(r, 'match').lower()
        if m not in ('yes', 'y', 'true', '是', '一致'):
            mismatch.append(i)
        if not g(r, 'legacy_value') or g(r, 'legacy_value') == 'TODO':
            no_legacy.append(i)
        p = g(r, 'player_side')
        if not p or p == 'TODO':
            no_player.append(i)
        ev = g(r, 'evidence')
        if not ev or ev == 'TODO':
            no_grade.append(i)
        else:
            d = ev.split('.')[0].strip()
            if d.isdigit() and int(d) >= 7:
                no_grade.append(i)

    print('=' * 76)
    print(f'认知与耐力 · {len(rows)} 条')
    print('=' * 76)
    if mismatch:
        print(f'\n🚫 **不一致** {len(mismatch)} 条（行 {mismatch[:15]}）')
    if no_legacy:
        print(f'\n❌ {len(no_legacy)} 条缺**原版值**（行 {no_legacy[:15]}）')
    if no_player:
        print(f'\n🚫 {len(no_player)} 条缺**玩家侧证据**'
              f'（行 {no_player[:15]}）')
    if no_grade:
        print(f'\n🚫 {len(no_grade)} 条**证据等级缺失或 ≥7 级**'
              f'（行 {no_grade[:15]}）')

    if not (mismatch or no_legacy or no_player or no_grade):
        print('\n✅ 认知与耐力：一致、原版值完整、玩家侧已验证、证据达标')

    print('\n🔑 **从「玩家读出什么意义」推进到'
          '「玩家是否把意义装进了自己的记忆 · 肌肉与信任」。**')
    print('   🔑 **"AI 能过去" ≠ "玩家知道能过去"。**')
    print('   🔴 **耐力本身是游戏意义的一部分；"更舒适"不等于"更忠实"。**')
    return 1 if (a.gate_check and
                 (mismatch or no_legacy or no_player or no_grade)) else 0


def main():
    ap = argparse.ArgumentParser(description='认知 · 承诺 · 耐力 · 信任')
    ap.add_argument('--map', action='store_true')
    ap.add_argument('--mark', action='store_true')
    ap.add_argument('--short', action='store_true')
    ap.add_argument('--lost', action='store_true')
    ap.add_argument('--vert', action='store_true')
    ap.add_argument('--commit', action='store_true')
    ap.add_argument('--conseq', action='store_true')
    ap.add_argument('--irrev', action='store_true')
    ap.add_argument('--ritual', action='store_true')
    ap.add_argument('--sl', action='store_true')
    ap.add_argument('--drift', action='store_true')
    ap.add_argument('--habit', action='store_true')
    ap.add_argument('--auto', action='store_true')
    ap.add_argument('--onboard', action='store_true')
    ap.add_argument('--trust', action='store_true')
    ap.add_argument('--envel', action='store_true')
    ap.add_argument('--blame', action='store_true')
    ap.add_argument('--g', action='store_true')
    ap.add_argument('--init')
    ap.add_argument('--check')
    ap.add_argument('--gate-check', action='store_true')
    a = ap.parse_args()
    fns = {'map': cmd_map, 'mark': cmd_mark, 'short': cmd_short,
           'lost': cmd_lost, 'vert': cmd_vert, 'commit': cmd_commit,
           'conseq': cmd_conseq, 'irrev': cmd_irrev, 'ritual': cmd_ritual,
           'sl': cmd_sl, 'drift': cmd_drift, 'habit': cmd_habit,
           'auto': cmd_auto, 'onboard': cmd_onboard, 'trust': cmd_trust,
           'envel': cmd_envel, 'blame': cmd_blame, 'g': cmd_g}
    for k, fn in fns.items():
        if getattr(a, k):
            return fn(a)
    if a.init:
        return cmd_init(a)
    if a.check:
        return cmd_check(a)
    print('❌ 需要 --map / --mark / --short / --lost / --vert / --commit / '
          '--conseq / --irrev / --ritual / --sl / --drift / --habit / '
          '--auto / --onboard / --trust / --envel / --blame / --g / '
          '--init / --check 之一')
    return 2


if __name__ == '__main__':
    sys.exit(main())
