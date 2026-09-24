#!/usr/bin/env python3
"""教与学 · 假可玩性 · 玩家第二职业 · 版本地层 · 仪式性浪费 ·
个性化真伪 · 苦行（第四十五轮 A–G，含 H 六项）。

**🔑 本轮真正的新盲区不是第 46 种系统，而是四条「外部依赖链」：**

| 链 | 内容 |
|---|---|
| **知识传递** | 🔑 **玩家把错误版本的经验教给新玩家** |
| **假可玩性** | 🔑 **界面允许尝试，系统拒绝完成** |
| **第二职业** | 🔑 矿工 · 速通者 · Modder 依赖**原版的可观测裂缝** |
| **版本地层** | 🔑 玩家口中的"版本"是**多维组合**，不是两个标签 |

> 🔑 **老玩家教的是旧机制；按钮点了没反应；教程里能做的正式局不能；
> 数据矿工依赖的内存布局被重排；日版美版难度不同。**

用法:
  game_social.py --teach    # 🔑 **知识传递链（老玩家教旧版本）**
  game_social.py --claim    # **三层：事实观察/解释断言/证据链**
  game_social.py --fake     # 🔑 **假可玩性（比幽灵更隐蔽）**
  game_social.py --demo     # **试玩版残留 / 教程临时能力**
  game_social.py --prof     # 🔑 **玩家第二职业**
  game_social.py --obs      # **可观测契约四类接口**
  game_social.py --stratum  # 🔑 **版本地层学（DAG 非时间轴）**
  game_social.py --region   # 🔑 **地区版不能预设"只有文本不同"**
  game_social.py --ritual   # **仪式性浪费（故意低效）**
  game_social.py --person   # 🔑 **个性化真伪（四个破绽接缝）**
  game_social.py --ascetic  # 🔑 **苦行（可选择的自我约束）**
  game_social.py --h        # H 类六项
  game_social.py --init ledger/social.csv
  game_social.py --check ledger/social.csv --gate

退出码: 0 通过 / 1 缺项 / 2 用法错误
"""
import argparse
import csv
import os
import sys

# 🔑 A 教与学
TEACH_RULE = '🔑 **玩家知识传递链不是原版教学系统的延伸，'
'而是「玩家用旧版本观察构造出的第二套机制解释」。**'
TEACH_CHAIN = ['口传', '语音组队', '实况直播', '攻略视频', 'Wiki',
               '分享配置', '观战回放']
TEACH_JUDGE = '🔑 玩家**不只检查攻略是否正确**，还会根据'
'**讲述者的身份 · 语气 · 共同经历 · 技术"证物"**判断可信度'
TEACH_KEY = '🔑 **教学传递的关键不是文本正确，而是证据与版本共同可见。**'
TEACH_WIKI = '🔑 一份 Wiki 若只写"机制 M"却不写**观察版本 · 可执行哈希 · '
'地区 · 平台 · 触发条件**，🔴 **就会把特定版本的副作用改写成永恒规律**'
TEACH_FLAT = '🔑 反过来，🔴 **把每个补丁差异平铺成无时间顺序的清单**，'
'新玩家又会以为**所有版本同时有效**'

CLAIM_THREE = [
    ('**事实观察**', '原始行为'),
    ('**解释断言**', '机制结论'),
    ('**证据链**', '样本 · 步骤 · 录像 · 内存或日志'),
]
CLAIM_RULE = '🔑 三者**必须可分别质疑**：🔑 **录像失败不代表结论一定错，'
'但结论必须降级为"未复现"**；🔑 **多人一致也不代表为真，'
'只能升级为"社区共识"**'

TEACH_BREAK = '🔑 **重制会同时破坏"教"和"学"。**'
TEACH_HOW = '老玩家依靠**共享方言 · 固定坐标 · 视觉参照物 · 击杀数字 · '
'击退幅度 · 时间感 · 口头口诀**教学；🔑 **新玩家无法看见老玩家脑中的版本标签**，'
'只会把结果理解成"当前游戏就是这样"'
TEACH_LOSS = '🔑 老玩家在短链口传中会**删去版本限定** —— '
'因为"在老版本里，Boss 第三招会因为你站在右侧第二块砖上而少转一次"'
'**远不如"靠右躲"好传播**'
TEACH_VERDICT = '🔑 脚本输出 `verified | partial | not_reproduced | '
'version_mismatch | evidence_insufficient`，'
'🔴 **禁止根据多人同意人数输出"正确"**'

# 🔑 B 假可玩性
FAKE_RULE = '🔑 **"看起来能玩但实际上不能"不是普通死内容，'
'而是「界面先承诺、系统再拒绝」。**'
FAKE_EG = '按钮存在却无反应 · 地图区域可见但不可进入 · 菜单选项显示却不生效 · '
'功能只在部分版本开放 · **教程临时能力不能在正式游戏保留**'
FAKE_WORSE = '🔑 **其危害强于一般不可见死内容** —— '
'它**先索取玩家注意和尝试成本，再告知失败**；'
'🔑 玩家甚至无法确定这是**锁定 · 未解锁 · 版本差异 · 缺陷 · '
'还是重制后的废弃功能**'
FAKE_FIELDS = [
    '`widget_id`', '`label_i18n`', '`visible_when`', '`focusable`',
    '`clickable`', '`enabled`', '**`authority`**', '`response_time`',
    '`failure_reason`', '`error_text`', '`side_effect`',
    '**`expected_by_player`**', '`actual_state`', '`version_scope`',
]
FAKE_DEAD = '🔑 死内容要分七类：`dead | unreachable | disabled_by_version | '
'tutorial_only | demo_only | prerequisite_locked | **`placebo`**'
FAKE_SCAN = '🔑 自动枚举**可聚焦控件 · 无回调控件 · 命中相同禁用分支的重复入口 · '
'未绑定输入 · 空响应界面 · 未加载资源占位**；'
'🔑 输出**不是"缺陷"，而是待人工分级的承诺裂缝**'
FAKE_PLAYER = '🔑 玩家真实会做：**连续打开每个菜单页 · 点击每个灰显项 · '
'试图装备每个外观 · 从地图边缘走到可见边界 · 在加载前后保存 · '
'断网时点击 · 在教程和正式局来回切换 · 把临时物品拖入正式背包**'
FAKE_ABUSE = '🔑 这些行为应标记为 `exploratory_abuse`，🔴 **与缺陷区分开**'

DEMO_RULE = '🔑 **试玩版残留最容易被当成内容差异。**'
DEMO_EG = '试玩版可能开放完整版锁定的**武器 · 关卡 · 敌人 · 教程 · 资源 · 按钮**；'
'也可能移除正式版的**经济限制 · 死亡惩罚 · 联机功能**'
DEMO_RESID = '🔑 正式版若继续引用试玩资源，就会出现**文本可点但无结果 · '
'教程能做但正式局不能 · 菜单选项残留**'
DEMO_TUT = '🔑 **教程临时能力会让玩家错误学习交互语法** —— '
'教程可能临时**关闭伤害 · 给予无限资源 · 锁定敌人 · 开启调试视角 · '
'跳过判定 · 允许穿过门**'
DEMO_PLAYER = '🔑 玩家真实会做：**在教程里反复测试边界 · '
'尝试把临时资源带走 · 退出教程后回到同一地点 · 用同一操作打 Boss · '
'教新人"这里可以"**'
DEMO_PROMPT = '🔑 `prompt_binding` 应进一步区分 `presentation_prompt` · '
'**`tutorial_privilege`** · **`training_dummy`** · `authority_channel`，'
'🔴 **不能把所有"游戏说你可以"合并为单一提示**'
DEMO_TWO = '🔑 **删除按钮**和**让按钮生效**必须分别处理：'
'🔴 若原版长期让按钮无反应，它可能已成为**玩家识别的视觉秩序甚至速查布局**；'
'若点击会进入明确"未完成"的空界面，它更接近假可玩性；'
'🔴 **若同一按钮在不同地区/版本/账号状态下工作，则属版本地层，不得统一删除**'

# 🔑 C 第二职业
PROF_RULE = '🔑 **玩家第二职业不是用户分层，'
'而是依赖原版可观测性生存的生态。**'
PROF_ROLES = ['`guide_author`', '`wiki_editor`', '`modder`', '`streamer`',
              '`speedrunner`', '**`data_miner`**', '`tool_author`']
PROF_CRACK = '🔑 这些职业共同依赖原版留下的**裂缝**：'
'**固定内存布局 · 调试符号 · 日志 · 资源命名 · 控制台命令 · 录像 · '
'存档 · 配置目录 · 遥测事件 · 性能计数器 · 未剥离字符串**'
PROF_BREAK = '🔑 原版即使**没有"鼓励生态"的意图**，也可能因 '
'**C++ RTTI · PDB · 可读资源名 · 稳定地址 · 错误日志**'
'形成**事实上的可观测接口**；'
'🔴 **重制若重排结构体 · 哈希资源名 · 剥离符号 · 改变日志格式 · '
'删除调试菜单，旧脚本 · 工具 · 攻略坐标 · 验证方法会同时失效**'
PROF_MINER = '🔑 **矿工不是"读数据"，'
'而是把内存 · 文件 · 日志翻译为可持续引用的知识。**'
PROF_LIVESPLIT = '🔑 速通生态把**内存观测转成自动验证** —— '
'自动拆分器读取内存中的游戏状态（新游戏状态 · 关卡 · 读盘 · 收集数）。'
'🔴 **重制改变地址甚至状态表示后，旧自动拆分器会失效**'
PROF_FIELDS = [
    '`depends_on`', '`observability_channel`', '`artifact`',
    '`version_bound`', '`migration_cost`', '`failure_mode`',
]
OBS_FOUR = [
    ('**资源接口**', '命名 · 路径 · 格式'),
    ('**数据接口**', '存档 · 配置 · 遥测'),
    ('**运行时接口**', '内存 · 控制台 · 日志 · 调试绘制'),
    ('**传播接口**', '录像 · 回放 · 分享码 · 分屏观战'),
]
OBS_STATE = '🔑 每项给**稳定性 · 依赖版本 · 读取是否需要写权限 · '
'崩溃风险 · 账号风险 · 替代方案**，并标 `intended | accidental | '
'deprecated | unsupported`'
OBS_RULE = '🔑 **生态失效的判断不是"有没有 Mod"，'
'而是可观测契约是否稳定。**'
OBS_MOD = '🔑 模组兼容矩阵应从"**Mod 能否加载**"'
'扩展到"**知识 · 录像 · 拆分器 · 坐标 · 攻略能否迁移**"'

# 🔑 D 版本地层
STRATUM_RULE = '🔑 **玩家记忆中的版本通常无法定位证据。**'
STRATUM_NO = '🔑 "我玩的是原版"·"日版更难"·"1.0 有这个 bug"·'
'"高清版没有这个门" **都不足以复现**'
STRATUM_MIN = '🔑 真正可比较的最小单元：**发行标题 · 载体 · 地区 · 平台 · '
'SKU · 发行日期 · 构建号 · 可执行哈希 · 资源包哈希 · 补丁版本 · '
'内容/语言包 · 模组 · 启动参数 · 主机固件 · 显示与性能配置 · 输入设备**'
STRATUM_WARN = '🔑 **标题相同不等于构件相同；版本号相同也不等于可执行体相同**；'
'🔴 **不同地区可能共享版本号却使用不同资源 · 参数 · 可执行体**'
REGION_RULE = '🔑 **地区版不能预设成"只有文本不同"。**'
REGION_WARN = '🔑 日版与美版难度调整长期被解释为适应不同市场，'
'🔴 **但以文化刻板印象替代真实市场分析应被批评** —— '
'🔴 **本方法论不应写"日版总是更难"，必须逐字节 · 逐资源 · 逐参数取证**'
REGION_CMP = '启动参数 · 敌人属性 · AI/概率 · 计时器 · 碰撞 · 掉落 · '
'**审查内容** · 文本 · 语音 · 图像 · 动画 · 音乐 · 镜头 · UI 布局 · '
'存档格式 · 网络协议 · 平台特性 · 认证差异'
REGION_SIX = '`identical | text_only | tuning | behavior | content | structure`'
STRATUM_DAG = '🔑 **地层档案应同时保留发布说明和构件哈希。**'
'🔑 **补丁说明是有作者有日期的源，但不是完整差分；'
'哈希能识别构件，却不能解释语义。**'
'🔑 版本档案的合适结构是 **DAG 而非线性时间轴** —— '
'同一标题可**并行拥有日版 · 美版 · 欧版 · 开发版 · 体验服 · 试玩版 · '
'补丁分支 · 平台分支**'
STRATUM_CITE = '🔑 任何机制断言**若不能回溯到可识别构建，'
'就不得进入"原版事实库"**'
STRATUM_KEEP = '🔑 **保存地层而不是覆盖地层，是尊重玩家记忆的前提。**'
'🔴 重制应允许按证据选择原版 · 地区 · 补丁层，或至少保留原版基线；'
'🔴 **不能把后续补丁解释成唯一"正确原版"**'

# 🔑 E 仪式性浪费
RITUAL_RULE = '🔑 **仪式性浪费的价值来自自选题材，不是系统效率低。**'
RITUAL_EG = '刻意绕路 · 不用传送 · 不用自动拾取 · 反复听同一段音乐 · '
'收集无用物品 —— 🔑 **是自我表达而非愚蠢**；'
'把工具最优让位于**路线审美 · 风景 · 节奏 · 偶然遭遇 · 角色扮演 · '
'"我走过这个世界"的记忆**'
RITUAL_FIELD = ['`player_chosen`', '`optimization_available`',
                '**`optimization_default`**', '`bypassed_content`',
                '`meaning_source`', '`can_abandon`', '`witness_channel`']
RITUAL_NOTE = '🔑 `meaning_source` **只能记录玩家表达或行为证据，'
'🔴 **不能由开发者推断动机**'
RITUAL_KEEP = '🔑 **真正的仪式支持是「允许慢」，而不是「强迫慢」。**'
'🔴 不得移除**捷径 · 路标 · 音乐触发 · 环境叙事 · 随机事件**；'
'🔑 若原版冗长是缺陷而非仪式，可在偏离记录中解释，'
'🔴 **但必须区分"玩家自己选择绕路"与"系统强制拖延"**'
RITUAL_DEFAULT = '🔑 若原版玩家正是靠**拒绝传送**形成身份，'
'🔴 **"默认开启快速旅行"不是中性改进**；'
'若原版本身没有传送，**新增传送属于有意偏离**'

# 🔑 F 个性化
PERSON_THREE = [
    ('**通用脚本占位**', '在名称 · 称谓 · 装束 · 最近选择插入变量'),
    ('**由玩家状态选择的分支**', '状态驱动'),
    ('**跨会话形成的关系模型**', '真正累积'),
]
PERSON_KEY = '🔑 玩家感受到"被认识"**可能来自少量但准确的呼应**；'
'🔑 真正重要的是**一致性**：**改名 · 死亡 · 背叛 · 帮助 · 久别 · 跨周目**后，'
'NPC 能否**保留合法上下文并正确回称**'
FOUR_SEAMS = [
    ('**称呼破绽**', '文本正确但**语音无法发音** · 第一次见面就熟络 · '
     '角色先后用不同名字 · 玩家输入被当无意义占位'),
    ('**知识破绽**', 'NPC 不知道玩家刚完成的关键选择，**却准确评价结果**'),
    ('**时间破绽**', '久别回归立即连续追问 · **多年后重复同一首次见面台词**'),
    ('**遗忘破绽**', '**无限记忆**导致所有旧承诺同时存在，'
     '或**彻底失忆**导致跨周目关系无法累积'),
]
PERSON_AI = '🔑 **"真 AI 个性化"只有在状态真实 · 生成受限 · 可回放时才优于原版脚本。**'
'🔴 生成式方案可能**更像真人**，却违反 `prompt_binding` 的受众与解释边界 · '
'**不可确定性复现 · 难以本地化 · 难以证明未使用玩家私人数据**'
PERSON_NAME = '🔑 **玩家名字必须作为跨通道状态，而不是字符串变量。**'
'要查**字幕 · 语音 · 邮件/日志 · 任务目标 · 存档导出 · Mod/分享内容 · '
'直播 · 无障碍朗读**的**名称一致性与隐私边界**'
PERSON_NAME_EG = '允许空名 · 特殊字符 · 重名 · **敏感词** · '
'**与原 NPC 同名** · 改名 · 多语言音译；'
'**语音没有授权名称时如何省略**；**角色只知绰号时如何保持认知错误**'

# 🔑 G 苦行
ASCETIC_THREE = [
    ('**完全没有**', '社区传统'),
    ('**玩家自觉遵守**', '无系统验证'),
    ('**系统正式验证**', '内置模式 · 排行榜 · 计时 · 徽章 · 成就'),
]
ASCETIC_RULE = '🔑 **原版没有成就不代表玩家不苦行；'
'原版没有记录不代表该玩法不是玩法。**'
ASCETIC_HELP = '🔑 重制新增辅助模式时，'
'**必须说明它是否同时改变验证资格 · 计时 · 排行榜 · 成就**'
ASCETIC_EDGE = '🔑 **苦行最难的部分是边界，不是视频。**'
'玩家真实会问：**擦弹算不算受伤？** 允许治疗但禁止自伤吗？'
'允许特定装备吗？允许死亡后续关吗？允许特定种子吗？'
'**允许暂停 · 云存档 · 回滚 · 帧延迟工具吗？允许 Mod 吗？**'
ASCETIC_FIELDS = ['`challenge_id`', '`version_id`', '`ruleset`',
                  '`prohibited`', '`permitted`', '`required`', '`scope`',
                  '`entry_condition`', '**`invalidators`**',
                  '`state_source`', '`evidence`', '`witnesses`', '`appeal`']
ASCETIC_EVID = [
    ('**内部成就**', '只能证明系统允许，**不能证明外部挑战条件**'),
    ('**录像**', '能证明可见行为，**无法证明隐藏状态**'),
    ('**内存自动拆分器**', '可验证游戏时间 · 关卡 · 伤害 · 状态，'
     '🔴 **但依赖运行时接口**'),
    ('**保存哈希**', '可证明种子和规则，**不能证明操作过程**'),
    ('**人工见证**', '最适合解释**边界争议**'),
]
ASCETIC_RIGHT = '🔑 正确方案**不是选一个"最可信"，而是多通道交叉验证**'
ASCETIC_ID = '🔑 **辅助模式会同时改变苦行资格和玩家身份** —— '
'🔴 若成就没有**版本/模式标签**，后来玩家无法知道记录来自原版 · 复刻 · '
'还是辅助模式'

H_SIX = [
    ('**H1 元游戏入口**', '🔑 玩家从**商店页 · 更新公告 · 标题栏 · 图标 · '
     '启动器新闻 · 首屏 · 语言选择 · 云存档标签**推断"这是什么版本"。'
     '🔴 重制可能改变**图标语义 · 标题相似度 · 价格与版本名**，'
     '却不在玩家真实入口处解释差异。增 `metagame_entry`'),
    ('**H2 退出后继续（社会时间）**', '🔑 已覆盖退出重算 · 暂停时间 · '
     '现实时间礼物 · AFK 回归 · 离线降级，🔴 **但未单独覆盖'
     '"玩家不在线时，NPC · 邮件 · 任务 · 季节 · 世界状态如何继续"**。'
     '玩家真实会做：**故意关闭游戏让作物/酿造/商店冷却完成 · '
     '跨时区旅行改变本地日期 · 调系统时钟触发活动**。增 `absent_social_clock`'),
    ('**H3 自述证据**', '🔑 玩家证明"**我当时就是这么玩的**"：截屏 · 录像 · '
     '分享码 · 配置导出 · Mod 清单 · 日志 · 排行榜截图。'
     '🔑 每条都有脆弱点：**截屏可能裁掉 HUD · 录像可能没音频 · '
     '分享码可能依赖不同版本 · Mod 可能静默改状态**。增 `player_evidence`'),
    ('**H4 继承契约（跨产品）**', '🔑 已有跨周目怀旧，🔴 **但缺"跨产品继承契约"**：'
     '把原版存档带入重制 · 保留旧名/旧装扮/旧死亡数/旧照片 · '
     '把旧成就映射成新成就 · **在重制中故意重演第一次选择**。'
     '要记**哪些必须丢失 · 丢失是否有仪式解释 · 迁移错误如何撤销 · '
     '旧记录是否只读保留**'),
    ('**H5 多手共玩（代理操作）**', '🔑 一台设备被多人**连续或同时操作**：'
     '借机 · 代打 · 父母控制 · 朋友试玩 · 主播代选 · 儿童账户 · '
     '访客存档 · 设备共享 · **旁观者口头指挥**。'
     '🔴 **重制把"玩家"默认成单一账号**，会让**代打污染统计 · '
     '借机泄露隐私 · 旁观者影响关系状态**。增 `player_agency`'),
    ('**H6 审美稳定性（废元素也会成为意义）**', '🔑 技术限制可能成为审美：'
     '**雾让地图显得大 · 低帧让动作沉重 · 低分辨率让灯光柔和 · '
     '重复动画形成仪式节奏 · 未使用音轨成为失落感 · 空房间成为都市传说**。'
     '🔑 结论是**必须逐例测试，不能先给结论** —— '
     '🔴 既不能把性能限制当设计意图，🔴 也不能把一切旧瑕疵都当神圣不可改。'
     '增 `aesthetic_stratum`'),
]

CONFLICTS = [
    '❌ **只保存"攻略最终结论"的 Wiki**（丢观察版本与证据链）',
    '❌ **把直播剪辑当机制证明**',
    '❌ **用 AI 自动总结社区说法后直接改原版**',
    '❌ 根据最热门攻略**删除"少人使用但忠于原版"的可达路径**',
    '❌ **重制时自动移除所有"看起来没用"的入口**',
    '❌ 为视觉现代化统一重排菜单后**删除旧空项**',
    '❌ 用全新教程替代原版教程**却不说明原版曾允许何种尝试**',
    '❌ **把假可玩性"修复"成更安静的隐藏锁定而不提供原因**',
    '❌ 重制"顺手"**重排结构体 · 压缩日志 · 哈希资源 · 移除调试菜单**',
    '❌ 为安全**一律封禁外部读取且不提供替代**',
    '❌ **把矿工发现改写成官方设定**',
    '❌ 声称 Mod 支持却**没有稳定资源或数据契约**',
    '❌ 只用"原版"和"重制版"两个标签',
    '❌ **把美版当国际默认**；**把地区差异概括成文化性格**',
    '❌ **用最新补丁覆盖旧版档案**',
    '❌ 隐藏版本号导致玩家无法报告问题',
    '❌ **把所有等待自动化**；**删除无数值收益的收集**',
    '❌ **把长路线缩短成"生活质量改进"**；**通过成就强迫低效**',
    '❌ 用大模型**随机改写所有 NPC 台词**；**无限记住玩家行为**',
    '❌ 让角色**正确说出玩家从未透露的信息**',
    '❌ 把玩家输入**未经处理送回云端**；只测试英文名称',
    '❌ 用 AI **自动判断视频是否无伤**；**把通关录像等同完整挑战**',
    '❌ **辅助模式悄悄改变成就资格**；用单一"难度"滑块替代禁项规则',
]

FIELDS = [
    ('item_id', '项编号'),
    ('domain', '域（teach / claim / fake / demo / prof / obs / stratum / '
               'region / ritual / person / ascetic / h）'),
    ('legacy_value', '**原版值**'),
    ('new_value', '新引擎值'),
    ('match', '**是否一致**'),
    ('external_chain', '**外部依赖链证据**（版本/可观测性/证据链）'),
    ('evidence', '证据等级 1-8'),
]


def _hdr(t, w=80):
    print('=' * w)
    print(t)
    print('=' * w)


def cmd_teach(a):
    _hdr('🔑 教与学（**老玩家教的是旧版本**）')
    print(f'   {TEACH_RULE}')
    print('\n链条: ' + ' · '.join(TEACH_CHAIN))
    print(f'\n   {TEACH_JUDGE}')
    print(f'\n   {TEACH_KEY}')
    print(f'\n   {TEACH_WIKI}')
    print(f'\n   {TEACH_FLAT}')
    print(f'\n   {TEACH_BREAK}')
    print(f'\n   {TEACH_HOW}')
    print(f'\n   {TEACH_LOSS}')
    return 0


def cmd_claim(a):
    _hdr('知识声明（**三层可分别质疑**）')
    for k, v in CLAIM_THREE:
        print(f'   {k:<16} {v}')
    print(f'\n   {CLAIM_RULE}')
    print(f'\n   {TEACH_VERDICT}')
    return 0


def cmd_fake(a):
    _hdr('🔑 假可玩性（**界面先承诺，系统再拒绝**）')
    print(f'   {FAKE_RULE}')
    print(f'\n   {FAKE_EG}')
    print(f'\n   {FAKE_WORSE}')
    print('\n字段: ' + ' · '.join(FAKE_FIELDS))
    print(f'\n   {FAKE_DEAD}')
    print(f'\n   {FAKE_SCAN}')
    print(f'\n   {FAKE_PLAYER}')
    print(f'\n   {FAKE_ABUSE}')
    return 0


def cmd_demo(a):
    _hdr('🔑 试玩残留 / 教程临时能力')
    print(f'   {DEMO_RULE}')
    print(f'\n   {DEMO_EG}')
    print(f'\n   {DEMO_RESID}')
    print(f'\n   {DEMO_TUT}')
    print(f'\n   {DEMO_PLAYER}')
    print(f'\n   {DEMO_PROMPT}')
    print(f'\n   {DEMO_TWO}')
    return 0


def cmd_prof(a):
    _hdr('🔑 玩家第二职业（**依赖可观测裂缝**）')
    print(f'   {PROF_RULE}')
    print('\n角色: ' + ' · '.join(PROF_ROLES))
    print(f'\n   {PROF_CRACK}')
    print(f'\n   {PROF_BREAK}')
    print(f'\n   {PROF_MINER}')
    print(f'\n   {PROF_LIVESPLIT}')
    print('\n字段: ' + ' · '.join(PROF_FIELDS))
    print(f'\n   {OBS_RULE}')
    return 0


def cmd_obs(a):
    _hdr('可观测契约（**四类接口**）')
    for k, v in OBS_FOUR:
        print(f'   {k:<18} {v}')
    print(f'\n   {OBS_STATE}')
    print(f'\n   {OBS_MOD}')
    return 0


def cmd_stratum(a):
    _hdr('🔑 版本地层学（**DAG 非时间轴**）')
    print(f'   {STRATUM_RULE}')
    print(f'\n   {STRATUM_NO}')
    print(f'\n   {STRATUM_MIN}')
    print(f'\n   {STRATUM_WARN}')
    print(f'\n   {STRATUM_DAG}')
    print(f'\n   {STRATUM_CITE}')
    print(f'\n   {STRATUM_KEEP}')
    return 0


def cmd_region(a):
    _hdr('🔑 地区版（**不能预设"只有文本不同"**）')
    print(f'   {REGION_RULE}')
    print(f'\n   {REGION_WARN}')
    print('\n逐项比较: ' + REGION_CMP)
    print(f'\n六级结论: {REGION_SIX}')
    return 0


def cmd_ritual(a):
    _hdr('🔑 仪式性浪费（**故意低效**）')
    print(f'   {RITUAL_RULE}')
    print(f'\n   {RITUAL_EG}')
    print('\n字段: ' + ' · '.join(RITUAL_FIELD))
    print(f'\n   {RITUAL_NOTE}')
    print(f'\n   {RITUAL_KEEP}')
    print(f'\n   {RITUAL_DEFAULT}')
    return 0


def cmd_person(a):
    _hdr('🔑 个性化（**真伪与四个破绽接缝**）')
    print('\n三级:')
    for k, v in PERSON_THREE:
        print(f'   {k:<24} {v}')
    print(f'\n   {PERSON_KEY}')
    print('\n四个破绽接缝:')
    for k, v in FOUR_SEAMS:
        print(f'   {k:<16} {v}')
    print(f'\n   {PERSON_AI}')
    print(f'\n   {PERSON_NAME}')
    print(f'\n   {PERSON_NAME_EG}')
    return 0


def cmd_ascetic(a):
    _hdr('🔑 苦行（**可选择的自我约束**）')
    print('\n原版支持的三种强度:')
    for k, v in ASCETIC_THREE:
        print(f'   {k:<22} {v}')
    print(f'\n   {ASCETIC_RULE}')
    print(f'\n   {ASCETIC_HELP}')
    print(f'\n   {ASCETIC_EDGE}')
    print('\n字段: ' + ' · '.join(ASCETIC_FIELDS))
    print('\n验证手段可信等级:')
    for k, v in ASCETIC_EVID:
        print(f'   {k:<20} {v}')
    print(f'\n   {ASCETIC_RIGHT}')
    print(f'\n   {ASCETIC_ID}')
    return 0


def cmd_h(a):
    _hdr('H 类（**六项外部接缝**）')
    for k, why in H_SIX:
        print(f'\n   【{k}】\n      {why}')
    return 0


def cmd_init(a):
    os.makedirs(os.path.dirname(a.init) or '.', exist_ok=True)
    with open(a.init, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow([k for k, _ in FIELDS])
        w.writerow(['TODO'] * len(FIELDS))
    print(f'已生成社会层表: {a.init}')
    print('\n⚠️ 十二域：teach / claim / fake / demo / prof / obs / '
          'stratum / region / ritual / person / ascetic / h')
    print('\n⚠️ `external_chain` 列＝**外部依赖链证据**')
    print('\n🔑 新模板：knowledge_claim · social_chain · affordance · '
          'promised_action · player_profession · observability_contract · '
          'stratum · stratum_diff · ritual · personalization_state · '
          'addressing_contract · challenge_contract · challenge_run')
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

    mismatch, no_legacy, no_chain, no_grade = [], [], [], []
    for i, r in enumerate(rows, 1):
        m = g(r, 'match').lower()
        if m not in ('yes', 'y', 'true', '是', '一致'):
            mismatch.append(i)
        if not g(r, 'legacy_value') or g(r, 'legacy_value') == 'TODO':
            no_legacy.append(i)
        p = g(r, 'external_chain')
        if not p or p == 'TODO':
            no_chain.append(i)
        ev = g(r, 'evidence')
        if not ev or ev == 'TODO':
            no_grade.append(i)
        else:
            d = ev.split('.')[0].strip()
            if d.isdigit() and int(d) >= 7:
                no_grade.append(i)

    print('=' * 76)
    print(f'社会层与版本地层 · {len(rows)} 条')
    print('=' * 76)
    if mismatch:
        print(f'\n🚫 **不一致** {len(mismatch)} 条（行 {mismatch[:15]}）')
    if no_legacy:
        print(f'\n❌ {len(no_legacy)} 条缺**原版值**（行 {no_legacy[:15]}）')
    if no_chain:
        print(f'\n🚫 {len(no_chain)} 条缺**外部依赖链证据**'
              f'（行 {no_chain[:15]}）')
    if no_grade:
        print(f'\n🚫 {len(no_grade)} 条**证据等级缺失或 ≥7 级**'
              f'（行 {no_grade[:15]}）')

    if not (mismatch or no_legacy or no_chain or no_grade):
        print('\n✅ 社会层：一致、原版值完整、外部链已验证、证据达标')

    print('\n🔑 **老玩家教的是旧版本；按钮点了没反应；'
          '教程里能做的正式局不能。**')
    print('   🔑 **标题相同 ≠ 构件相同；版本号相同 ≠ 可执行体相同。**')
    print('   🔴 **地区版不能预设"只有文本不同"，也不能写"日版总是更难"。**')
    print('   🔑 **生态失效的判断不是"有没有 Mod"，'
          '而是可观测契约是否稳定。**')
    return 1 if (a.gate_check and
                 (mismatch or no_legacy or no_chain or no_grade)) else 0


def main():
    ap = argparse.ArgumentParser(description='社会层：教与学/假可玩/职业/地层')
    ap.add_argument('--teach', action='store_true')
    ap.add_argument('--claim', action='store_true')
    ap.add_argument('--fake', action='store_true')
    ap.add_argument('--demo', action='store_true')
    ap.add_argument('--prof', action='store_true')
    ap.add_argument('--obs', action='store_true')
    ap.add_argument('--stratum', action='store_true')
    ap.add_argument('--region', action='store_true')
    ap.add_argument('--ritual', action='store_true')
    ap.add_argument('--person', action='store_true')
    ap.add_argument('--ascetic', action='store_true')
    ap.add_argument('--h', action='store_true')
    ap.add_argument('--init')
    ap.add_argument('--check')
    ap.add_argument('--gate-check', action='store_true')
    a = ap.parse_args()
    fns = {'teach': cmd_teach, 'claim': cmd_claim, 'fake': cmd_fake,
           'demo': cmd_demo, 'prof': cmd_prof, 'obs': cmd_obs,
           'stratum': cmd_stratum, 'region': cmd_region,
           'ritual': cmd_ritual, 'person': cmd_person,
           'ascetic': cmd_ascetic, 'h': cmd_h}
    for k, fn in fns.items():
        if getattr(a, k):
            return fn(a)
    if a.init:
        return cmd_init(a)
    if a.check:
        return cmd_check(a)
    print('❌ 需要 --teach / --claim / --fake / --demo / --prof / --obs / '
          '--stratum / --region / --ritual / --person / --ascetic / --h / '
          '--init / --check 之一')
    return 2


if __name__ == '__main__':
    sys.exit(main())
