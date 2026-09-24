#!/usr/bin/env python3
"""现实常识迁移 · 越界(OOB) · 多感官权威 · 伪因果仪式 · 失败可解释性 · 设备漂移
（第四十二轮 A / B / C / D / E / F 类，含 G 补充）。

**🔑 本轮的视角切换**：
> 前四十一轮主要记录了"**游戏给什么**"；
> 本轮必须记录"**玩家据此以为会发生什么**"。

🔑 **像素级复刻的对象不只是最终画面 · 碰撞 · 伤害与状态，
还包括玩家在观察若干通道后形成的「稳定预期」。**
> 🔑 **预期并非纯主观意见**——它可由原版输入序列 · 事件日志 · 内存状态 ·
> 资产可见性与社区规则共同**证伪或验证**。

因此 `must-match` 的边界应扩张到"**玩家可合理推断的因果承诺**"，
🔴 **而不是把直觉一律当作非可复现传闻**。

用法:
  game_inference.py --common   # 🔑 **物理常识按"玩家可见承诺"取证**
  game_inference.py --matrix   # **常识规则测试矩阵**
  game_inference.py --teach    # 🔑 **违反常识要有可学习线索**
  game_inference.py --sign     # **符号直觉做可辨态测试**
  game_inference.py --oob      # 🔑 **OOB 是原版地图的一部分**
  game_inference.py --oobmap   # **边界厚度 · 入口 · 退出**
  game_inference.py --oobart   # **OOB 美学**
  game_inference.py --chan     # 🔑 **通道权威性本身就是机制**
  game_inference.py --author   # **按状态机给权威，不按固定权重**
  game_inference.py --ritual   # 🔑 **伪因果是玩家自建规律**
  game_inference.py --rng      # **复现随机接口，不是只复现分布**
  game_inference.py --explain  # 🔑 **可解释性四级**
  game_inference.py --device   # **设备个体差异 · 老化 · 校准状态**
  game_inference.py --g        # G 类八项
  game_inference.py --init ledger/inference.csv
  game_inference.py --check ledger/inference.csv --gate

退出码: 0 通过 / 1 缺项 / 2 用法错误
"""
import argparse
import csv
import os
import sys

# 🔑 A 常识
COMMON_RULE = '🔑 **物理常识必须按"玩家可见承诺"取证，而非按艺术家命名取证。**'
COMMON_EG = '🔑 `Wood_Barrel_01` 可能**不可燃**，但同图集的 `Wood_Crate` 可能**可燃**；'
'`Water` 区域可能阻断火，也可能只允许水面技能。🔴 **资源名不能代替运行时测试。**'
COMMON_FIELDS = [
    '对象/表面的**视觉材质**', '碰撞体积', '阵营/标签',
    '**可点燃 / 可导电 / 可承重 / 可浮 / 可反射 / 可声透 / 可冰冻 / 可腐蚀**',
    '**各状态转移**', '**失败时是否播特效或音效**', '距离衰减', '朝向依赖',
    '**连续接触 vs 单次触发**',
]
COMMON_THREE = [
    ('**物理直觉**', '木桶是否可燃 · 水是否导电 · 重物是否压下压力板 · '
     '镜面是否反射 · 声音能否穿透门 · 物体是否坠落'),
    ('**世界规则直觉**', '🔑 原版中**火烧不燃木桶 · 水下点火 · 纸挡箭** —— '
     '表面违反现实，却是**稳定的玩法承诺**'),
    ('**符号直觉**', '骷髅 · 绿色 · 红色 · 门 · 感叹号 · 脉动光 —— '
     '🔴 **在不同文化 · 题材与玩家经验下并不等价**'),
]

MATRIX_RULE = '🔑 **常识规则测试矩阵**'
MATRIX_FIELDS = [
    '现实预期', '**原版实际**', '**预期—实际差**', '**玩家可见线索**',
    '原版修复状态', '**社区命名**',
]
MATRIX_WARN = '🔑 **单看资源文件无法判定木桶"本该燃但不能燃"** —— '
'必须结合**可点燃实体清单 · 特效触发条件 · 脚本条件 · 失败反馈 · '
'旧攻略 · 录像与玩家口述**'
MATRIX_INTENDED = '🔑 若原版有燃效但无转移、有可破坏标记但无销毁，'
'便应记录为 `intended_deviation`，🔴 **而不是"引擎不够真实"**'
MATRIX_COMBOS = [
    '燃烧弹 × 油桶', '雷 × 积水', '炸药 × 门', '重物 × 开关', '冰 × 地面',
    '声波 × 墙体', '镜面 × 激光', '草 × 火', '尸体 × 毒池',
]
MATRIX_KEEP = '🔑 模糊条件需**保留视频**，🔴 **不能只留 true/false**'

TEACH_RULE = '🔑 **"常识反直觉"要有可学习的线索，否则不是设计，而是静默陷阱。**'
TEACH_FIELDS = [
    '`first_teach_moment`', '`teachable_evidence`', '`failure_feedback_kind`',
    '`misread_risk`', '`community_mnemonic`',
]
TEACH_EG = '🔑 原版"**蓝色火**"只烧特定目标：若有首见教学 · 目标高亮 · '
'命中音效 → **可学资产**；若任何线索都没有 → 只是历史遗留数据'
TEACH_WARN = '🔑 后者应判为"**保留原版行为，但重制是否保留属于显式决策**"，'
'🔴 **不能默认改成普通火**'

SIGN_RULE = '🔑 **符号直觉应做可辨态测试，而不是由开发者凭语义解释。**'
SIGN_CATS = [
    '危险', '安全', '可用', '可收集', '敌对', '友方', '任务相关', '可交互',
]
SIGN_TEST = '🔑 让**不同经验与目标语言**参与者在**不知机制**时做快速分类，'
'再与真实机制交叉'
SIGN_RECORD = [
    '符号形态', '颜色', '运动', '上下文', '体裁预期', '**正确含义**',
    '**误读率**', '**误读后果**',
]
SIGN_WARN = '🔴 **绿色在国际化中不能自动等同安全；红色也不应自动等于敌人。**'
SIGN_VERDICT = [
    ('`stable`', '所有样本正确读出'),
    ('`context_dependent`', '背景或题材可消歧'),
    ('`degraded`', '**原版已有明显误读** —— 🔴 **不等于自动修正**'),
    ('`unknown`', '无证据 —— 🔴 **保留，避免用开发者直觉编造**'),
]

# 🔑 B OOB
OOB_RULE = '🔑 **OOB 不是单一漏洞，而是"可达空间"问题。**'
OOB_KINDS = [
    '碰撞穿模', '几何缝隙', '序列破坏', '**未加载区域进入**', '**天空盒外**',
    '**背面贴图区**', '**开发者房间**', '**调试区域**', '**合法高跳**',
    '**击飞越界**', '边界外导航', '软锁', '**回退与恢复**',
]
OOB_MISS = '🔑 只把"穿墙"记入物理 bug 会漏掉大量资产：`noclip` 进入的几何秩序 · '
'缺失背面 · 远处 LOD 接缝 · 天空盒内侧 · 地图加载优先级 · 边界传送位置 · '
'未完成的文字与贴图，🔑 **以及玩家把背面当作捷径或美学空间的实践**'

OOB_SR = [
    '🔑 **SCP: Containment Breach** 社区只允许 OOB 用于 Any% · Legacy Any% · '
    'Legacy Random%',
    '🔑 **Hop Swap** 把完整关卡分成 **Restricted**（禁止任何使玩家 OOB '
    '或与背景同色的漏洞）与 **Unrestricted**（允许所有漏洞并要求游戏音频）',
]
OOB_SR_NOTE = '🔑 这**不是法律问题**，而是'
'🔑 **「原版玩法边界已由社区实践固定」的证据**。'
'🔴 若重制修复碰撞 · 封掉背面 · 统一天空盒 · 删除调试房，'
'玩家失去的可能**不是"一个漏洞"，而是一整条路径 · 验证生态和多年攻略知识**'

OOBMAP_FIELDS = [
    '合法入口', '**已知 OOB 入口**', '触发动作', '需要工具', '**精度窗口**',
    '**成功率**', '进入后几何与纹理', '可导航方向', '高度与坠落', '加载状态',
    '可见世界', '出口', '**回合法**', '**软锁条件**', '录像链接', '原版版本',
]
OOBMAP_THICK = '🔑 边界应测量**从"最后一次稳定接触"到"判定出界/坠落/传送"的'
'距离与时间**，🔴 **而不是只记一个布尔值**'

OOBART_RULE = '🔑 **OOB 美学是最容易被"美术现代化"破坏的部分。**'
OOBART_ITEMS = [
    '背面贴图', '单面墙', '未封闭天空盒', '远处方块世界', '占位材质',
    '开发者房间',
]
OOBART_WHY = '🔑 它们**并非一律丑陋** —— 构成玩家对"**引擎如何组织世界**"的'
'**可见解释**'
OOBART_RECORD = [
    '视点', '可见资产', '层级关系', '颜色与构图', '帧率变化',
    '**是否可截图分享**',
]
OOBART_WARN = '🔑 重制可改善清晰度，🔴 **但不得在没有显式决策时把背面全部封闭 · '
'贴图全部补全 · 删除调试区域**'

OOB_LAYERS = [
    '`intent`', '`first_known_date`', '`route_name`', '`human_feasible`',
    '`tool_feasible`', '`required_glitch_chain`', '`category_status`',
    '`risk_to_save`', '`reproducibility`',
]
OOB_NET = '🔑 对联网玩法，另记**权威端 · 反作弊误判 · 回放可复现性 · '
'是否影响他人经济**'
OOB_CHAIN = '🔑 保存 `oob_evidence_chain`：录像 · 输入日志 · 内存快照 · '
'地图坐标 · 社区规则 —— 🔑 **保证一个 OOB 说法能从现象追到证据，'
'🔴 而不是从攻略追到断言**'

# 🔑 C 通道权威
CHAN_RULE = '🔑 **"视觉 · 听觉 · 震动 · UI 哪个更重要"是错误问题；'
'正确问题是"在何种状态与何种后果下谁拥有权威"。**'
CHAN_EG = [
    '🔑 **数字满血但角色在喘气** —— UI 说安全，身体语言说危险',
    '🔑 **音效命中但无伤害数字** —— 音频说命中，结算说未命中',
    '🔑 **画面显示已到但碰撞未生效** —— 视觉说已接触，物理说没有',
]
CHAN_WARN = '🔑 通道互相冗余只是**理想情形**；'
'🔴 **冲突时若没有固定顺序，玩家会建立摇摆预期**'

AUTHOR_FIELDS = [
    '`state`', '`question`', '`authoritative_channel`', '`secondary_channel`',
    '`conflict_policy`', '`lag_tolerance_ms`', '`expected_player_reading`',
    '`actual_player_reading`', '`mismatch_severity`',
]
AUTHOR_Q = '🔑 例如 `health < critical` 时：'
'**呼吸动画应服从生命值权威，还是生命值服从呼吸？**'
AUTHOR_WHY = '🔑 若呼吸是**纯粹戏剧表现**，它必须**不能让玩家误判为可行动资源**；'
'若它是**状态病征**，则 UI 与身体语言应有**可分辨语义**'

DIVISION = '🔑 **同一事件的不同通道可能合法地回答不同问题** —— 这不是冲突，'
'而是**分工**'
DIVISION_MAP = [
    ('屏幕红边', '**受击方向**'), ('数字', '**伤害量**'),
    ('震动', '**冲击强度**'), ('音效', '**武器/材质身份**'),
]
DIVISION_ASK = '🔑 取证应明确每个通道回答 `who / what / where / when / '
'how much / future risk` 中的哪一个；'
'🔴 **若多个通道都声称同一答案却不同，就进入冲突裁决**'

GOV_FOUR = [
    ('`primary`', '**结算事实**'),
    ('`indicative`', '**线索但未结算**'),
    ('`thematic`', '**氛围，不承诺事实**'),
    ('`undefined`', '**原版未稳定，玩家会误读**'),
]
GOV_RULE = '🔴 **重制不得把 `indicative` 升级为 `primary`，'
'也不能把 `thematic` 降为无反馈。**'
GOV_NO = '🔴 **尤其要禁止"为了表现力而让动画与判定不一致"** —— 一次命中若'
'**动画明显命中但判定未中**，🔑 **玩家不认为这是风格，而认为游戏撒谎**'
AUTHOR_KEEP = '🔑 权威档案必须**同时记录原版缺陷与重制意图**：'
'`original_conflict_accepted` · `original_ambiguity_purpose` · '
'`remaster_decision` · `player_cost_if_changed` · `evidence_tier`'

# 🔑 D 伪因果
RITUAL_RULE = '🔑 **伪因果学习是玩家主动生成规律的行为，'
'不自动等于"玩家蠢"或"设计恶意"。**'
RITUAL_WHY = '独立事件会被读成连胜/连败 · 操作会读成影响掉落 · '
'时间点会读成影响结果'
RITUAL_WARN = '🔴 **重制改动画 · 加载 · UI 重排 · 网络往返，'
'即使保底概率相同，也可能让原有仪式失效或催生新迷信**'
RITUAL_FIELDS = [
    '玩家可见动作序列', '结果事件', '**时间窗口**', '**是否可见调用**',
    '**是否可见内部计数**', '**是否有伪关联**', '旧社区名称', '视频证据',
]
RITUAL_OUT = ['**无证据**', '**弱相关**', '**机制相关**', '**确定性因果**']
RITUAL_NOTE = '🔑 只输出四档，🔴 **避免把巧合包装成机制**'

RNG_RULE = '🔑 **重制应复现随机接口，而不是只复现分布。**'
RNG_ITEMS = [
    '随机种子来源', '**调用顺序**', '**调用栈**', '**每次调用的原因**',
    '**是否每帧/每事件/每渲染调用**', '客户端与服务器边界', '保底状态',
    '**显示数字与真实概率是否同一值**', '抽卡/开箱/暴击/掉落分别用哪些生成器',
    '**存档前后是否重摇**', '**暂停/快进/网络重发是否改变顺序**',
]
RNG_WARN = '🔑 若原版玩家会依据动画结尾或音效终点推断"已经生成"，'
'🔴 **重制也不得让 UI 承诺早于真实结算**'
RNG_TEST = [
    '连续成功/失败分布', '等待时长', '保底表现', '**结果显示与结算时间差**',
    '**撤销或重试是否改变序列**',
]
RNG_NO = '🔴 **禁止为提高"感知公平"而暗中绑定动态难度 · 隐藏概率 · '
'改变历史调用 · 让 UI 显示与内部概率不同**'

SUPER_THREE = [
    ('**玩家自行建立的仪式**', '🔑 应保留原版**时序**'),
    ('**官方刻意提供但无实际因果的操作空间**', '可显式标注为表演或改为明确机制'),
    ('**官方利用伪因果增加投入**', '🔴 **不得伪装成真实影响**'),
]
SUPER_FIELD = '🔑 `designed_illusion` 必须明确，'
'🔴 **不能把任何玩家迷信都归咎于设计**'

# 🔑 E 可解释性
EXPLAIN_RULE = '🔑 **玩家不是只在死亡时需要解释，'
'而是在每一次资源 · 能力或机会不可用时都需要解释。**'
EXPLAIN_WHEN = [
    '为什么输了', '为什么死了', '为什么任务失败', '为什么被拒绝',
    '门为什么打不开', '物品为什么不能用', '技能为什么在冷却',
    '为什么合成失败', '对话为什么消失', '路径为什么封锁',
    '**伤害为什么被免**', '**治疗为什么无效**',
]
EXPLAIN_FIELDS = [
    '问题是否可见', '**何时可见**', '**能否追溯**', '**能否复盘**',
    '**是否有静默条件**',
]
EXPLAIN_FOUR = [
    ('`none`', '只有结果'),
    ('`state`', '告诉你当前状态'),
    ('`reason`', '告诉你触发条件'),
    ('`counterfactual`', '**告诉你改变什么会发生不同**'),
]
EXPLAIN_IDEAL = '🔑 **理想并非一律四级** —— 某些机制应被探索；'
'🔑 但至少要回答**玩家是否能学会**'
EXPLAIN_WARN = '🔑 对竞技或强惩罚机制，🔴 **缺少 `reason` 会把失败归给'
'"游戏不讲理"，而非策略**'

# 🔑 F 设备
DEVICE_RULE = '🔑 **同一游戏在不同老化程度的设备上体验不同。**'
DEVICE_ITEMS = [
    '**摇杆漂移**', '键盘磨损/连击失效', '鼠标微动老化',
    '**显示器老化（色偏 · 亮度衰减）**', '**耳机频响差异**',
    '**手柄电池电量影响震动**',
]
DEVICE_ASK = [
    '原版是否对老设备有**宽容设计**？重制后是否消失？',
    '**玩家是否校准过**摇杆 / 显示器 / 耳机？',
]
DEVICE_CAL = '🔑 建立 `device_profile`：设备型号 · 固件 · 使用时长 · '
'**校准状态** · 死区实测 · 频响曲线 · 色偏测量'

G_EIGHT = [
    ('**G1 多玩家共同因果推断**',
     'A–D 都默认单玩家；多人时玩家从**队友视角 · 语音 · 标记 · 位置 · '
     '动画 · 结算**互相推断。🔑 同一伤害在**个人客户端 · 队友视角 · '
     '死亡回放 · 权威结算**可能不同。需增 `observer_id` · '
     '`observer_authority` · `disagreement_kind`'),
    ('**G2 责任归因的会话现实**',
     '🔑 已有 client view/server truth，但未覆盖**玩家如何在失败时公开指认**。'
     '🔴 **重制不应设计"自动甩锅"UI**，但应记原版失败时谁能被识别：'
     '个人操作 · 队友 · AI · 环境 · 网络 · 机制 · 未知'),
    ('**G3 长期漂移与版本记忆的双向影响**',
     '玩家会记住某版手感 · 某次伤害公式 · 某个 OOB；'
     '🔑 **新版本即使修掉偶然漏洞，也可能破坏记忆与老录像**。'
     '新增 `version_memory`：首次引入版本 · 社区名称 · '
     '**旧录像可复现性** · 当前状态 · 是否保留兼容模式'),
    ('**G4 玩家可撤销的现实后果**',
     '🔑 暂停 · 存档 · 退出 · 交易 · 组队邀请 · 聊天 · 截图 · 直播 · 语音，'
     '🔑 **甚至"把手柄放下"都可能发生在判定中间**。'
     '🔴 **重制若把玩家现实动作当作"放弃承诺"，会把操作中断错误归因成失败**'),
    ('**G5 设备自动更新与环境迁移**',
     '驱动 · 固件 · OS · 平台输入层 · 显示器 night mode · 空间音频 · HDR · '
     '刷新率 · VR 房间尺度都可能改变读数。🔑 **原版测试环境即使老化也固定**；'
     '🔴 **重制若允许自动校准或云端配置漂移，会失去可复现基线**'),
    ('**G6 保存污染与跨存档因果**',
     '🔑 玩家会**复制存档 · 导入旧配置 · 跨平台合并 · 用他人存档测试**；'
     '一个"仪式"可能来自**旧档隐藏计数**。'
     '🔴 **取证不能只测全新档** —— 增 `save_lineage`：来源 · 迁移路径 · '
     '隐藏计数 · RNG 状态 · 设备校准 · OOB 标记'),
    ('**G7 隐性承诺的生命周期**',
     '🔑 一个提示可能在 5 小时前出现 · 一次教程道具可能已回收 · '
     '某个 NPC 可能永久消失；玩家事后不知道机制"**曾经出现过**"。'
     '补**跨时间可寻址性**：`first_evidence_time` · `last_evidence_time` · '
     '`expiry_condition` · `reminder_surface`'),
    ('**G8 元迷信与社区解释污染**',
     '官方补丁说明 · 开发者只言片语 · 主播经验 · 翻译错误 · 伪造视频'
     '都会成为玩家模型的一部分。🔑 `source_kind` 分：`primary_artifact` · '
     '`runtime_trace` · `official_statement` · `community_assertion` · '
     '`secondary_media` · `unverified`'),
]

CONFLICTS = [
    '❌ **"合理化修正"** —— 把火烧不燃木桶改成"更真实"、让水下点燃失败、'
    '让纸不再挡箭（🔴 把设计资产当缺陷）',
    '❌ **"冲突通道择优显示"** —— 交给一个 HUD 总览、删除"多余"提示、'
    '让 UI 数字覆盖角色表现',
    '❌ **"动态随机以改善体感"** —— 按失败次数/支付/在线时长/设备暗改概率',
    '❌ **"无障碍即自动适配"** —— 自动改色 · 扩大判定 · 简化输入，'
    '却不保存玩家选择',
    '❌ **"自动校准与云同步默认开启"** —— 漂移基线随温度/电量/设备身份变化',
    '❌ **用 AI/自然语言摘要替代证据链** —— 评论 · 攻略 · 弹幕只能定位假设',
    '❌ 把 OOB 只记成物理 bug',
    '❌ **在没有显式决策时封闭背面 / 补全贴图 / 删除调试区域**',
    '❌ 把 `indicative` 升级为 `primary`、把 `thematic` 降为无反馈',
    '❌ **为了表现力让动画与判定不一致**（"游戏撒谎"）',
    '❌ 把 `degraded` 符号自动修正',
    '❌ 用开发者直觉填 `unknown`',
    '❌ 把玩家迷信都归咎于设计（不标 `designed_illusion`）',
    '❌ 只测全新档（漏掉 `save_lineage`）',
    '❌ 设计"自动甩锅"UI',
]

FIELDS = [
    ('item_id', '项编号'),
    ('domain', '域（common / matrix / teach / sign / oob / oobmap / oobart / '
               'chan / author / ritual / rng / explain / device / g）'),
    ('legacy_value', '**原版值**'),
    ('new_value', '新引擎值'),
    ('match', '**是否一致**'),
    ('player_inference', '**玩家据此以为会发生什么**（推断层）'),
    ('evidence', '证据等级 1-8'),
]


def _hdr(t, w=80):
    print('=' * w)
    print(t)
    print('=' * w)


def cmd_common(a):
    _hdr('🔑 现实常识（**按可见承诺取证**）')
    print(f'   {COMMON_RULE}')
    print(f'\n   {COMMON_EG}')
    print('\n三层直觉:')
    for k, v in COMMON_THREE:
        print(f'   {k:<20} {v}')
    print('\n字段: ' + ' · '.join(COMMON_FIELDS))
    return 0


def cmd_matrix(a):
    _hdr('常识规则测试矩阵')
    print(f'   {MATRIX_RULE}')
    print('\n字段: ' + ' · '.join(MATRIX_FIELDS))
    print(f'\n   {MATRIX_WARN}')
    print(f'\n   {MATRIX_INTENDED}')
    print('\n必测组合: ' + ' · '.join(MATRIX_COMBOS))
    print(f'\n   {MATRIX_KEEP}')
    return 0


def cmd_teach(a):
    _hdr('🔑 可学习性（**不是静默陷阱**）')
    print(f'   {TEACH_RULE}')
    print('\n字段: ' + ' · '.join(TEACH_FIELDS))
    print(f'\n   {TEACH_EG}')
    print(f'\n   {TEACH_WARN}')
    return 0


def cmd_sign(a):
    _hdr('符号直觉（**可辨态测试**）')
    print(f'   {SIGN_RULE}')
    print('\n类别: ' + ' · '.join(SIGN_CATS))
    print(f'\n   {SIGN_TEST}')
    print('\n记录: ' + ' · '.join(SIGN_RECORD))
    print(f'\n   {SIGN_WARN}')
    print('\n`verdict` 四种:')
    for k, v in SIGN_VERDICT:
        print(f'   {k:<22} {v}')
    return 0


def cmd_oob(a):
    _hdr('🔑 越界（**OOB 是原版地图的一部分**）')
    print(f'   {OOB_RULE}')
    print('\n种类: ' + ' · '.join(OOB_KINDS))
    print(f'\n   {OOB_MISS}')
    print('\n速通社区分层（🔑 **原版玩法边界已由社区实践固定**）:')
    for s in OOB_SR:
        print(f'   · {s}')
    print(f'\n   {OOB_SR_NOTE}')
    return 0


def cmd_oobmap(a):
    _hdr('OOB 地图（**边界厚度 · 入口 · 退出**）')
    print('\n字段: ' + ' · '.join(OOBMAP_FIELDS))
    print(f'\n   {OOBMAP_THICK}')
    print('\n分层: ' + ' · '.join(OOB_LAYERS))
    print(f'\n   {OOB_NET}')
    print(f'\n   {OOB_CHAIN}')
    return 0


def cmd_oobart(a):
    _hdr('🔑 OOB 美学（**最易被美术现代化破坏**）')
    print(f'   {OOBART_RULE}')
    print('\n内容: ' + ' · '.join(OOBART_ITEMS))
    print(f'\n   {OOBART_WHY}')
    print('\n记录: ' + ' · '.join(OOBART_RECORD))
    print(f'\n   {OOBART_WARN}')
    return 0


def cmd_chan(a):
    _hdr('🔑 多感官冲突（**通道权威性本身就是机制**）')
    print(f'   {CHAN_RULE}')
    print('\n例子:')
    for e in CHAN_EG:
        print(f'   · {e}')
    print(f'\n   {CHAN_WARN}')
    print(f'\n   {DIVISION}')
    print('\n分工:')
    for k, v in DIVISION_MAP:
        print(f'   {k:<12} → {v}')
    print(f'\n   {DIVISION_ASK}')
    return 0


def cmd_author(a):
    _hdr('通道权威（**按状态机给，不按固定权重**）')
    print('\n字段: ' + ' · '.join(AUTHOR_FIELDS))
    print(f'\n   {AUTHOR_Q}')
    print(f'\n   {AUTHOR_WHY}')
    print('\n治理四级:')
    for k, v in GOV_FOUR:
        print(f'   {k:<14} {v}')
    print(f'\n   {GOV_RULE}')
    print(f'\n   {GOV_NO}')
    print(f'\n   {AUTHOR_KEEP}')
    return 0


def cmd_ritual(a):
    _hdr('🔑 伪因果（**玩家自建规律**）')
    print(f'   {RITUAL_RULE}')
    print(f'\n   {RITUAL_WHY}')
    print(f'\n   {RITUAL_WARN}')
    print('\n字段: ' + ' · '.join(RITUAL_FIELDS))
    print('\n只输出四档: ' + ' · '.join(RITUAL_OUT))
    print(f'\n   {RITUAL_NOTE}')
    print('\n三种迷信生态:')
    for k, v in SUPER_THREE:
        print(f'   {k:<34} {v}')
    print(f'\n   {SUPER_FIELD}')
    return 0


def cmd_rng(a):
    _hdr('🔑 随机接口（**不只分布**）')
    print(f'   {RNG_RULE}')
    print('\n必录: ' + ' · '.join(RNG_ITEMS))
    print(f'\n   {RNG_WARN}')
    print('\n实测: ' + ' · '.join(RNG_TEST))
    print(f'\n   {RNG_NO}')
    return 0


def cmd_explain(a):
    _hdr('🔑 可解释性（**四级**）')
    print(f'   {EXPLAIN_RULE}')
    print('\n要解释的时刻: ' + ' · '.join(EXPLAIN_WHEN))
    print('\n字段: ' + ' · '.join(EXPLAIN_FIELDS))
    print('\n四级:')
    for k, v in EXPLAIN_FOUR:
        print(f'   {k:<18} {v}')
    print(f'\n   {EXPLAIN_IDEAL}')
    print(f'\n   {EXPLAIN_WARN}')
    return 0


def cmd_device(a):
    _hdr('🔑 设备（**个体差异 · 老化 · 校准**）')
    print(f'   {DEVICE_RULE}')
    print('\n项目: ' + ' · '.join(DEVICE_ITEMS))
    print('\n必答:')
    for d in DEVICE_ASK:
        print(f'   · {d}')
    print(f'\n   {DEVICE_CAL}')
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
    print(f'已生成推断层表: {a.init}')
    print('\n⚠️ 十四域：common / matrix / teach / sign / oob / oobmap / '
          'oobart / chan / author / ritual / rng / explain / device / g')
    print('\n⚠️ `player_inference` 列＝**玩家据此以为会发生什么**')
    print('\n🔑 六张新表：material_world_model · sign_meaning_test · '
          'oob_atlas · channel_authority · ritual_surface · '
          'failure_explanation · device_profile')
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

    mismatch, no_legacy, no_infer, no_grade = [], [], [], []
    for i, r in enumerate(rows, 1):
        m = g(r, 'match').lower()
        if m not in ('yes', 'y', 'true', '是', '一致'):
            mismatch.append(i)
        if not g(r, 'legacy_value') or g(r, 'legacy_value') == 'TODO':
            no_legacy.append(i)
        p = g(r, 'player_inference')
        if not p or p == 'TODO':
            no_infer.append(i)
        ev = g(r, 'evidence')
        if not ev or ev == 'TODO':
            no_grade.append(i)
        else:
            d = ev.split('.')[0].strip()
            if d.isdigit() and int(d) >= 7:
                no_grade.append(i)

    print('=' * 76)
    print(f'推断层 · {len(rows)} 条')
    print('=' * 76)
    if mismatch:
        print(f'\n🚫 **不一致** {len(mismatch)} 条（行 {mismatch[:15]}）')
    if no_legacy:
        print(f'\n❌ {len(no_legacy)} 条缺**原版值**（行 {no_legacy[:15]}）')
    if no_infer:
        print(f'\n🚫 {len(no_infer)} 条缺**玩家推断**'
              f'（行 {no_infer[:15]}）')
    if no_grade:
        print(f'\n🚫 {len(no_grade)} 条**证据等级缺失或 ≥7 级**'
              f'（行 {no_grade[:15]}）')

    if not (mismatch or no_legacy or no_infer or no_grade):
        print('\n✅ 推断层：一致、原版值完整、玩家推断已验证、证据达标')

    print('\n🔑 **前四十一轮记录了「游戏给什么」；'
          '本轮记录「玩家据此以为会发生什么」。**')
    print('   🔑 **常识违反若可重复，就不是瑕疵，而是资产。**')
    print('   🔴 **一次命中若动画明显命中但判定未中 —— '
          '玩家不认为这是风格，而认为游戏撒谎。**')
    return 1 if (a.gate_check and
                 (mismatch or no_legacy or no_infer or no_grade)) else 0


def main():
    ap = argparse.ArgumentParser(description='推断层：常识/OOB/权威/迷信')
    ap.add_argument('--common', action='store_true')
    ap.add_argument('--matrix', action='store_true')
    ap.add_argument('--teach', action='store_true')
    ap.add_argument('--sign', action='store_true')
    ap.add_argument('--oob', action='store_true')
    ap.add_argument('--oobmap', action='store_true')
    ap.add_argument('--oobart', action='store_true')
    ap.add_argument('--chan', action='store_true')
    ap.add_argument('--author', action='store_true')
    ap.add_argument('--ritual', action='store_true')
    ap.add_argument('--rng', action='store_true')
    ap.add_argument('--explain', action='store_true')
    ap.add_argument('--device', action='store_true')
    ap.add_argument('--g', action='store_true')
    ap.add_argument('--init')
    ap.add_argument('--check')
    ap.add_argument('--gate-check', action='store_true')
    a = ap.parse_args()
    fns = {'common': cmd_common, 'matrix': cmd_matrix, 'teach': cmd_teach,
           'sign': cmd_sign, 'oob': cmd_oob, 'oobmap': cmd_oobmap,
           'oobart': cmd_oobart, 'chan': cmd_chan, 'author': cmd_author,
           'ritual': cmd_ritual, 'rng': cmd_rng, 'explain': cmd_explain,
           'device': cmd_device, 'g': cmd_g}
    for k, fn in fns.items():
        if getattr(a, k):
            return fn(a)
    if a.init:
        return cmd_init(a)
    if a.check:
        return cmd_check(a)
    print('❌ 需要 --common / --matrix / --teach / --sign / --oob / '
          '--oobmap / --oobart / --chan / --author / --ritual / --rng / '
          '--explain / --device / --g / --init / --check 之一')
    return 2


if __name__ == '__main__':
    sys.exit(main())
