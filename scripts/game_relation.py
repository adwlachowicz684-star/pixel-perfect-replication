#!/usr/bin/env python3
"""离开与弃坑 · 第 N 次体验 · 被砍内容幽灵 · 第一次的不可再生 ·
私有公平规则 · 笨拙容忍 · 共谋（第四十三轮 A–G，含 H 八项）。

**🔑 本轮的视角切换**：
> 前四十二轮已覆盖几乎所有**静态系统**；
> 真正的空白发生在**系统之间的时间接缝** ——
> **玩家与原版之间跨越会话、跨越周目、跨越版本的「关系状态」**。

存档 · 云存档 · 快照 · 断点 · 重连 · RNG · 耐久痕迹 · 多周目 · 教学 ·
失败重试 · 死亡惩罚 · 元操作都已有覆盖；但这些问题仍缺统一模型：

- 🔑 **玩家关闭游戏后，原版如何记住自己正准备做什么？**
- 🔑 **同一句台词第 50 次是否变化？**
- 🔑 **预告片承诺却没有实现，是否仍是 must-match？**

🔑 **本轮新增四个总状态机**（🔴 **它们是取证与验收状态机，不是游戏运行时大状态机**）：
`PlayerSessionState` · `RepeatExposureState` · `GhostAssetState` · `FirstnessState`

> 🔑 **引擎侧字段不应只写"是否已看"，而要写版本 · 触发路径 · 已播放次数 ·
> 最后退出时点 · 下一次允许的恢复点。**
> 🔴 **若仍用布尔，复刻项目会在第一次完成后误判"此后都可跳过"**——
> 随后才发现原版在第二次仍不可跳、通关后才可跳、新周目才可跳，
> 或只有同一实例重复失败时允许跳过。

用法:
  game_relation.py --leave    # 🔑 **弃坑地图**
  game_relation.py --afk      # **AFK 惩罚/踢出/重连不是一个状态**
  game_relation.py --return   # 🔑 **回归奖励是承诺的测试样本**
  game_relation.py --dignity  # 🔑 **未完成存档的尊严**
  game_relation.py --breakp   # 🔑 **断点与"最后动作"**
  game_relation.py --nth      # 🔑 **四层计数 × 语境标签**
  game_relation.py --skip     # 🔑 **跳过是控制权迁移，不是删内容**
  game_relation.py --variant  # **第 50 次台词的四种问题**
  game_relation.py --ghost    # 🔑 **幽灵六级**
  game_relation.py --first    # 🔑 **第一次的不可再生**
  game_relation.py --rule     # **玩家自定公平规则**
  game_relation.py --clumsy   # 🔑 **笨拙不是残障**
  game_relation.py --complic  # 🔑 **共谋：明知是演出仍配合**
  game_relation.py --h        # H 类八项
  game_relation.py --init ledger/relation.csv
  game_relation.py --check ledger/relation.csv --gate

退出码: 0 通过 / 1 缺项 / 2 用法错误
"""
import argparse
import csv
import os
import sys

# 🔑 A 离开
LEAVE_RULE = '🔑 **"玩家何时放弃"不能只统计关卡失败率，'
'必须记录离开前的「连续状态轨迹」。**'
LEAVE_TRACE = [
    '位置', '目标', '最近输入', '最近触发事件', '最近死亡', '当前倒计时',
    '自动保存节点', '手动保存节点', '暂停状态',
    '**电源 / 主页 / 任务管理器退出**',
]
LEAVE_LAST = '🔑 会话结束后的关键**不是"玩了多久"，而是最后 120 秒发生了什么**：'
'连续两次死亡后回主菜单 · 在商店前站立 90 秒 · 在不可跳过的演出中关机 · '
'任务说明弹出后立即离开'
LEAVE_WARN = '🔑 **这些路径会生成不同的回归承诺；'
'把它们统一成"流失原因"会丢失信息。**'
LEAVE_FIELDS = [
    '`exit_path`', '`seconds_in_current_state`', '`last_successful_action`',
    '`last_failed_action`', '`pending_interaction`', '`autosave_pending`',
    '`last_save_age_seconds`', '`resumable_from`', '`offline_duration_bucket`',
]
LEAVE_BUCKET = '🔑 `offline_duration_bucket` **只用于测试**，'
'🔴 **不要求原版真的使用同样阈值**'

RETURN_RULE = '🔑 **"回归奖励"不是留存设计，而是对原版承诺的测试样本。**'
RETURN_THRESH = '🔑 公开资料中回归阈值**从 30 天到 360 天并存**（35 / 90 / 135，'
'以及 30 / 180 / 360）—— 🔴 **它们并非同一口径，'
'不能据此宣称"30 天是行业标准"**'
RETURN_TEST = [
    '奖励是否影响难度', '是否改变进度包络', '**是否在回归后限时过期**',
    '**是否与离线时长相关**',
]
RETURN_EG = '🔑 特别要验证：**玩家是否故意弃坑 30 天 / 90 天后再上线领取奖励** —— '
'🔴 **若复刻改变了阈值或档位，就改变了原版经济与时间承诺**'
RETURN_BOTH = '🔴 复刻**不能因为现代游戏更重视"无损回归"就自动保留或强化**；'
'🔴 **也不能因为原版有惩罚性断线机制就沿用**'

DIGNITY_RULE = '🔑 **未完成存档的尊严不是给玩家看任务列表，'
'而是恢复"我当时在做什么"。**'
DIGNITY_SRC = '🔑 官方手册显示存档详情可含**保存地点 · 当前目标 · 难度 · '
'日期/游玩时间**，自动存档在检查点覆盖，手动存档另有多个槽位，'
'并**明确提醒写入时不要断电或关闭**'
DIGNITY_TEST = '🔑 至少做矩阵测试：**30 分钟 / 1 天 / 7 天 / 30 天 / 90 天 / 180 天**后，'
'进入存档 · 主菜单 · 崩溃恢复 · 不同设备 · 断电恢复，'
'分别核对**第一帧世界状态 · HUD · 目标 · 镜头 · 音频 · 计时器**'

AFK_RULE = '🔑 **AFK / 超时的最大盲区：很多项目只记录"闲置时长"，'
'不记录世界是否等待 · 他人是否受影响 · 重连是否保留责任。**'
AFK_SOLO = '🔑 单机可能是完全中性（待机 · 音乐降低 · 屏幕变暗 · 菜单自动关闭），'
'也可能是严厉惩罚（倒计时结束任务失败 · 资源消失 · 自动出售 · 耐力归零）'
AFK_MULTI = '🔑 联机中缺席**占用他人时间**，系统可能先警告 · 后扣分 · 再锁队列'
AFK_GRAPH = '`present → warned → inactive → removed → penalized → appealable`'
AFK_EDGE = '🔑 每条边记录**触发时间 · 提示文本 · 对方是否收到通知 · '
'世界是否暂停 · 物品是否结算**'
AFK_WORLD = '🔑 **"世界等你"也是原版表现，不应被现代便利自动替换。**'
'剧情倒计时是否继续 · 敌人 AI 是否仍在计算 · 食物/天气是否变化 · '
'伙伴是否继续说话 · 手柄是否自动断开 · 主机是否休眠'
AFK_ACTS = [
    '**停止所有输入**', '**只按住摇杆**', '**打开手柄菜单**', '**关闭手柄**',
    '**关闭显示器**',
]
AFK_BACK = '🔑 挂机回来后第一秒要核对：**输入延迟 · 音频爆音 · 镜头跳跃 · '
'误触菜单 · 敌人已贴脸 · QTE 已经失败**'

BREAKP_RULE = '🔑 **断点与"最后动作"是 must-match 的细粒度对象。**'
BREAKP_KINDS = [
    '自动保存节点', '任务完成即时保存', '退出菜单保存', '配置保存',
    '云同步点', '**可恢复快照**',
]
BREAKP_WHY = '🔑 原版可能**只在检查点保存，离开即丢失数分钟**；'
'可能允许手动覆盖；也可能在主菜单或退出流程额外写档'
BREAKP_MOMENTS = [
    '对话第一句', '对话最后一句', '奖励结算', '**掉落拾取前**',
    '**掉落拾取后**', '**存档写入提示出现时**', '场景加载 30% / 90%',
    'QTE 开始', 'QTE 成功', 'QTE 失败', '**商店确认前**', '确认后',
    '装备变更前', '属性点分配前', '角色正在移动',
]
BREAKP_WARN = '🔑 每个用例必须核对"**原版可恢复/不可恢复**"与'
'"重制是否相同"，🔴 **不能用"现代游戏应自动保存"覆盖**'

# 🔑 B 第 N 次
NTH_RULE = '🔑 **"第一次"与"第 N 次"的真正变量不是循环次数，'
'而是「哪个叙事单元」被重复。**'
NTH_MIN = '🔑 最低粒度：`playthrough_id + archivable_sequence_id + '
'sequence_instance_id + line_id + context_hash`'
NTH_CTX = '🔑 `context_hash` **只纳入稳定语境**（位置 · 时间 · 天气 · '
'世界状态 · 已知事实），🔴 **不纳入随机种子或帧计数**'
NTH_FIELDS = [
    ('`per_archivable_sequence_count`', '该重放单元第几次'),
    ('`per_instance_count`', '同一单元在第几次实际运行'),
    ('`line_play_count`', '台词级计数（🔑 区分跨任务重复与同任务重复）'),
    ('`context_hash`', '稳定语境'),
    ('`heard_variants` / `selected_branch` / `choice_outcome`',
     '🔑 **是否听过其他分支**'),
    ('`run_index` / `new_game_plus_depth`', '同一周目内的多次重复'),
    ('`first_play_lock` / `skip_unlock_condition`',
     '🔑 **第几次才允许跳过**'),
    ('`weighted_shuffle_bag` / `exhaust_then_repeat_policy`',
     '🔑 "随机"可能有权重 · 冷却 · 穷尽规则'),
]
NTH_BOOL = '🔴 **只记录全局 `seen_count` 会把"同一条通用台词"·'
'"同一段区域过场"·"同一个任务实例"·"同一个周目"混为一谈**'

SKIP_RULE = '🔑 **跳过不是删掉内容，'
'而是让控制权和世界状态迁移到新状态。**'
SKIP_FSM = '`GAMEPLAY → PRE_CUTSCENE → CUTSCENE → SKIPPING → '
'POST_CUTSCENE → GAMEPLAY`'
SKIP_ENTER = '🔑 进入时**冻结玩家输入 · 保存控制快照与事件上下文**'
SKIP_APPLY = '🔴 **跳过时不得只停止 Timeline 或隐藏 UI，'
'还必须应用跳过的目标状态** —— 逐项核对：主角位置与朝向 · 速度 · 摄像机 · '
'HUD · 对话标志 · 任务目标 · **分支变量** · 角色关系 · 场景加载 · 音效 · '
'震动 · 手柄灯 · 字幕 · **输入映射** · 敌人生成 · 计时器 · '
'**玩家已按下的按键是否继续生效**'
SKIP_MATRIX = [
    '跳过落到下一游戏段', '跳过落到检查点', '**跳过导致任务直接失败**',
    '**跳过保留中间选择**', '**跳过忽略中间选择**', '跳过只播放摘要',
    '跳过禁止后是否可重演', '跳过后字幕日志是否补全',
    '**跳过后音频是否有尾巴**',
]
SKIP_BUG = '🔑 一个常见伪 bug：**跳过逻辑认为"剧情已发生"，'
'但世界仍等待过场完成事件** —— 导致门不开 · 目标不更新 · NPC 永久沉默'
SKIP_FOUR = [
    '**首次播放**是否可跳', '**同一序列第二次**是否可跳',
    '**失败重试**是否可跳', '**通关后重放菜单**是否可跳',
    '**新周目**是否可跳', '多周目同一周目内是否可跳',
    '**按住时长**', '提示何时出现', '**跳过落到哪个恢复点**',
    '**跳过后世界状态是否改变**',
]
SKIP_RITUAL = '🔑 **"跳过仪式"与"跳过可用性"同样重要**：连按 · 长按 · '
'先按 Esc 再按跳过 · **在提示出现前一帧按下** · 打开字幕日志后再跳 · '
'暂停后跳 · 被伤害后跳。🔴 **任何一个仪式在原版有效而重制无效，'
'都是控制延迟与"可按下窗口"的偏离**'
SKIP_PROBE = '🔑 应在过场 **0% / 10% / 20% / 50% / 90% / 99% 及最后一帧**'
'分别尝试：单次点击 · 持续按住 · 暂停后点击 · 连点 10 次 · 取消再重试'

VARIANT_FOUR = [
    ('**穷尽**', '池子放完怎么办'),
    ('**衰减**', '是否降低重复权重'),
    ('**冷却**', '同一句多久内不再出现'),
    ('**伪穷尽**', '🔴 看似随机实则在池接近穷尽时提高未听行权重'),
]
VARIANT_TEST = '🔑 先在一个**稳定语境**下播放所有变体，记**池大小 · 去重窗口 · '
'连续不重复长度 · 循环点**；再改变位置 · 时间 · 天气 · 好感度 · 玩家历史，'
'确认是否进入**新子集**'
VARIANT_KEEP = '🔑 第 50 次与第一遍完全相同的台词**可能是怀旧锚点，'
'也可能是重复劳动** —— 🔴 **复刻不应以"加入更多变体"替代原版**，'
'而应保证**原版池 · 权重与循环边界优先**'

# 🔑 C 幽灵
GHOST_RULE = '🔑 **"幽灵内容"的最小取证单位是资源引用与可感知入口，'
'而不是"文件里有什么"。**'
GHOST_SIX = [
    ('`REF_ONLY`', '仅字符串 / ID'),
    ('`ASSET_ONLY`', '资源存在但无加载引用'),
    ('`REFERENCED_NOT_SPAWNED`', '资源被引用但未生成'),
    ('`SPAWNABLE_NOT_REACHABLE`', '可生成但入口关闭'),
    ('`REACHABLE_NOT_INTERACTABLE`', '**可到达但无碰撞/响应**'),
    ('`PERCEIVABLE`', '**玩家能看见 / 听见 / 读到**'),
]
GHOST_NOTE = '🔑 **只有达到 `REACHABLE_NOT_INTERACTABLE` 及以上时，'
'普通玩家才可能把它当成"进不去的门"**'
GHOST_DOOR = '🔑 **门后没有模型不等于没有承诺** —— 可能有**声音 · 风 · 光照 · '
'贴图 · 碰撞**，或只是在**旧版本有入口**'
GHOST_FIELDS = [
    '`asset_id`', '`build_version`', '`media_commitment_version`',
    '`referenced_by`', '`collider_present`', '`interaction_present`',
    '`perceivable_channel`', '`community_claim`', '`verification_method`',
    '`remaster_action`',
]

# 🔑 D 第一次
FIRST_RULE = '🔑 **"第一次"不可再生，但"重放第一次"必须是有意识分层。**'
FIRST_THREE = [
    ('**一次性事实态**', '初见 · 首通 · 首次死亡 —— 世界事实'),
    ('**一次性叙事标记**', '首通日期 · 初次日志 · 首次成就'),
    ('**不可再生情绪**', '🔑 无知 · 惊讶 · 误判 · 惊喜 —— '
     '🔴 **老玩家在重制版中无法重现**'),
]
FIRST_FIELDS = [
    '`first_fact_id`', '`first_occurred_at`', '`first_world_state_hash`',
    '`replayable`', '`reset_scope`', '`reset_cost`',
]
FIRST_NOTE = '🔑 情绪字段**不声称原版测量玩家心理**，只记录老玩家重放偏好'
FIRST_ASK = [
    '原版是否**记录"第一次"**（首次成就 · 首通标记）？',
    '重制是否提供"**假装第一次**"的入口（重置教学 · 新档）？',
    '🔴 **重制若剧透**（开场就把结局/机制摆出来），就摧毁了"第一次"',
]

# 🔑 E 私有道德
RULE_E = '🔑 **私有公平规则要作为"玩家承诺"抓取，而不是社区运营资料。**'
RULE_ITEMS = [
    '速通社区的**自我约束**（不用某 glitch · 不作弊 · 不利用某 bug）',
    '**SL 大法算作弊吗？**', '**看攻略算吗？**', '**修改器算吗？**',
    '原版是否**暗示**某种"正确玩法"（成就设计 · 排行榜 · 提示文案）？',
]
RULE_FAIL = '🔑 重制若使某种自我约束**失效**（原版可 SL，重制强制云存档）'
RULE_TABLE = '`self_rules.yaml` + **失效矩阵**'

# 🔑 F 笨拙
CLUMSY_RULE = '🔑 **笨拙不是残障，也不能被"简化按钮"悄悄改写。**'
CLUMSY_WHO = '🔑 不是残障辅助，而是**慢 · 犹豫 · 乱按 · 反复试错 · 不理解**的玩家'
CLUMSY_ASK = [
    '**乱按会不会误触不可逆操作**？',
    '**犹豫的代价**：站在原地不动会怎样？超时是否惩罚？',
    '**反复试错的成本**：死亡惩罚 · 资源消耗 · 时间损失',
    '**"卡住 10 分钟"的原版反应**：有提示？有保底？还是放任？',
]
CLUMSY_TABLE = '`clumsiness_matrix.csv`：误操作类型 · 响应窗口 · 撤销 · '
'倒计时 · 提示 · 保底'

# 🔑 G 共谋
COMPLIC_RULE = '🔑 **共谋的价值在于玩家愿意陪演出，而非演出是否真实。**'
COMPLIC_ITEMS = [
    '明知是脚本演出仍等待', '明知是套路仍走', '**明知是假选择仍选**',
    'QTE', '**假选择（railroad）**', '**假开放**',
]
COMPLIC_NO = '🔴 重制若"**揭穿**"演出（显示"这只是演出"· 允许跳过所有 QTE）'
COMPLIC_4TH = '🔑 **第四面墙的默契**：玩家配合游戏演戏，游戏假装不知道'
COMPLIC_TABLE = '`complicity_matrix.csv`：选择语义 · 可控后果 · 失败成本 · '
'跳过后状态 · **演出揭穿方式**'

H_EIGHT = [
    ('**H1 会话外声誉**', '🔑 玩家离开后世界是否记录其行为：NPC 后续台词 · '
     '公告 · 告示板 · 商店价格 · 营地变化 · 敌人悬赏 · 日记 · 同伴称呼。'
     '🔴 **重制只恢复任务目标而不恢复社会记忆，会让世界显得更干净，也更空**'),
    ('**H2 跨会话信任衰减**', '🔑 离开半年后玩家是否仍记得跳跃窗口 · 菜单顺序 · '
     '存档退出技巧 · 特定 bug · 平台组合键。'
     '🔴 **若教程重置、键位改变或自动跳过旧提示，'
     '玩家"记得的原版知识"可能成为反负担**'),
    ('**H3 文化性幽灵**', '预告片 · 早期攻略 · 杂志地图 · 宣传截图 · '
     '本地化初版中的地名/任务/角色/数值；可能在正式版改名 · 删除 · '
     '或从未存在。🔑 应新增 `media_commitment` 时间线，'
     '🔴 **不能与正式版未使用资源混为一谈**'),
    ('**H4 老玩家身份与遗产继承**', '存档图标 · 游玩时长 · **首通日期** · 称号 · '
     '外观 · 难度 · 死亡数 · 稀有资源 · 截图 · 改名记录是否原样继承。'
     '🔑 **只测试"能读档"不够** —— 玩家可能把游玩时长 · 旧称号 · '
     '首通日期视为**自我证明**。🔴 **重制若清零 · 四舍五入 · 重新计算，'
     '就是身份偏离**'),
    ('**H5 玩家制造的临时边界**', '🔑 玩家会把任意表面当成椅子 · '
     '把台阶边缘当休息点 · 把菜单当暂停世界 · 把截图当证据 · '
     '把某个角度当安全点。🔑 **原版容许玩家"借用非玩法空间"**，'
     '🔴 **重制对碰撞 · UI 或渲染的清洁化可能删除这些空间**'),
    ('**H6 仪式化等待与回归后的首屏**', '加载 · 开机动画 · 主菜单 · 公告 · '
     '回归弹窗 · 最后目标 · 新闻 · 补丁说明 · 按键提示 · 音乐 —— '
     '**谁先出现 · 多久可跳过 · 是否保存进度**。'
     '🔑 **回归玩家第一分钟不是新手教学，而是"游戏还认不认得我"**'),
    ('**H7 存档作为跨会话演出**', '覆盖确认 · 槽位顺序 · **缩略图生成时刻** · '
     '保存图标位置 · 闪退后自动恢复 · 上次游玩时间 · 角色状态 · '
     '死亡后自动保存 · 云冲突界面。🔑 **保存 UI 不是静态表单，'
     '而是玩家每次"我准备离开"时看到的最后画面**'),
    ('**H8 跨周目怀旧对象**', '🔑 第 N 次玩家记得的不只是内容，而是'
     '**按钮声音 · 过场抖动 · 延迟 · 门后贴图 · 角色语气 · 已知但不可达区域**。'
     '🔴 **重制提升分辨率 · 音频 · 动画后，可能保留信息却丢失怀旧触感**。'
     '应增 `nostalgia_probe`：让老玩家指认"哪一处第 N 次仍想听到/看到"'),
]

CONFLICTS = [
    '❌ 用布尔 `seen` 代替四层计数（**会误判"此后都可跳过"**）',
    '❌ **把"流失原因"统一成一个标签**（丢失回归承诺差异）',
    '❌ 宣称"30 天是行业回归标准"（🔴 **阈值非同一口径**）',
    '❌ **因现代游戏重视"无损回归"就自动保留或强化回归奖励**',
    '❌ **用"现代游戏应自动保存"覆盖原版断点语义**',
    '❌ **跳过时只停止 Timeline 或隐藏 UI**（不应用目标状态）',
    '❌ **以"加入更多变体"替代原版池 · 权重与循环边界**',
    '❌ **把幽灵当彩蛋全部补全**（补全可能就是偏离）',
    '❌ 把媒体承诺与未使用资源混为一谈',
    '❌ **重制剧透**（开场摆出结局/机制，摧毁"第一次"）',
    '❌ **用"简化按钮"悄悄改写笨拙玩家的空间**',
    '❌ **"揭穿"演出**（显示"这只是演出"· 允许跳过所有 QTE）',
    '❌ **只恢复任务目标而不恢复社会记忆**（世界更干净也更空）',
    '❌ **对老玩家身份清零 · 四舍五入 · 重新计算**',
    '❌ **清洁化碰撞/UI 删除玩家制造的临时边界**',
]

FIELDS = [
    ('item_id', '项编号'),
    ('domain', '域（leave / afk / return / dignity / breakp / nth / skip / '
               'variant / ghost / first / rule / clumsy / complic / h）'),
    ('legacy_value', '**原版值**'),
    ('new_value', '新引擎值'),
    ('match', '**是否一致**'),
    ('session_crossing', '**跨会话/跨周目证据**（关系状态）'),
    ('evidence', '证据等级 1-8'),
]


def _hdr(t, w=80):
    print('=' * w)
    print(t)
    print('=' * w)


def cmd_leave(a):
    _hdr('🔑 弃坑地图（**离开前的连续状态轨迹**）')
    print(f'   {LEAVE_RULE}')
    print('\n轨迹: ' + ' · '.join(LEAVE_TRACE))
    print(f'\n   {LEAVE_LAST}')
    print(f'\n   {LEAVE_WARN}')
    print('\n字段: ' + ' · '.join(LEAVE_FIELDS))
    print(f'\n   {LEAVE_BUCKET}')
    return 0


def cmd_afk(a):
    _hdr('🔑 AFK（**惩罚 / 踢出 / 重连不是一个状态**）')
    print(f'   {AFK_RULE}')
    print(f'\n   {AFK_SOLO}')
    print(f'\n   {AFK_MULTI}')
    print(f'\n状态图: {AFK_GRAPH}')
    print(f'\n   {AFK_EDGE}')
    print(f'\n   {AFK_WORLD}')
    print('\n五类真实动作: ' + ' · '.join(AFK_ACTS))
    print(f'\n   {AFK_BACK}')
    return 0


def cmd_return(a):
    _hdr('回归奖励（**承诺的测试样本**）')
    print(f'   {RETURN_RULE}')
    print(f'\n   {RETURN_THRESH}')
    print('\n必验: ' + ' · '.join(RETURN_TEST))
    print(f'\n   {RETURN_EG}')
    print(f'\n   {RETURN_BOTH}')
    return 0


def cmd_dignity(a):
    _hdr('🔑 未完成存档的尊严')
    print(f'   {DIGNITY_RULE}')
    print(f'\n   {DIGNITY_SRC}')
    print(f'\n   {DIGNITY_TEST}')
    return 0


def cmd_breakp(a):
    _hdr('🔑 断点与"最后动作"')
    print(f'   {BREAKP_RULE}')
    print('\n要区分: ' + ' · '.join(BREAKP_KINDS))
    print(f'\n   {BREAKP_WHY}')
    print('\n必测时刻: ' + ' · '.join(BREAKP_MOMENTS))
    print(f'\n   {BREAKP_WARN}')
    return 0


def cmd_nth(a):
    _hdr('🔑 第 N 次（**四层计数 × 语境标签**）')
    print(f'   {NTH_RULE}')
    print(f'\n   {NTH_MIN}')
    print(f'\n   {NTH_CTX}')
    print(f'\n   {NTH_BOOL}')
    print('\n字段:')
    for k, v in NTH_FIELDS:
        print(f'   {k:<48} {v}')
    return 0


def cmd_skip(a):
    _hdr('🔑 跳过（**控制权迁移**）')
    print(f'   {SKIP_RULE}')
    print(f'\n状态机: {SKIP_FSM}')
    print(f'\n   {SKIP_ENTER}')
    print(f'\n   {SKIP_APPLY}')
    print('\n后果矩阵: ' + ' · '.join(SKIP_MATRIX))
    print(f'\n   {SKIP_BUG}')
    print('\n四个独立资格: ' + ' · '.join(SKIP_FOUR))
    print(f'\n   {SKIP_RITUAL}')
    print(f'\n   {SKIP_PROBE}')
    return 0


def cmd_variant(a):
    _hdr('第 50 次台词（**四种不同问题**）')
    for k, v in VARIANT_FOUR:
        print(f'   {k:<16} {v}')
    print(f'\n   {VARIANT_TEST}')
    print(f'\n   {VARIANT_KEEP}')
    return 0


def cmd_ghost(a):
    _hdr('🔑 幽灵内容（**六级**）')
    print(f'   {GHOST_RULE}')
    print('\n六级:')
    for k, v in GHOST_SIX:
        print(f'   {k:<32} {v}')
    print(f'\n   {GHOST_NOTE}')
    print(f'\n   {GHOST_DOOR}')
    print('\n字段: ' + ' · '.join(GHOST_FIELDS))
    return 0


def cmd_first(a):
    _hdr('🔑 第一次（**不可再生**）')
    print(f'   {FIRST_RULE}')
    print('\n三层:')
    for k, v in FIRST_THREE:
        print(f'   {k:<20} {v}')
    print('\n字段: ' + ' · '.join(FIRST_FIELDS))
    print(f'\n   {FIRST_NOTE}')
    print('\n必答:')
    for f in FIRST_ASK:
        print(f'   · {f}')
    return 0


def cmd_rule(a):
    _hdr('🔑 私有公平规则（**玩家承诺**）')
    print(f'   {RULE_E}')
    print('\n抓取项:')
    for r in RULE_ITEMS:
        print(f'   · {r}')
    print(f'\n   {RULE_FAIL}')
    print(f'\n   {RULE_TABLE}')
    return 0


def cmd_clumsy(a):
    _hdr('🔑 笨拙（**不是残障**）')
    print(f'   {CLUMSY_RULE}')
    print(f'\n   {CLUMSY_WHO}')
    print('\n必答:')
    for c in CLUMSY_ASK:
        print(f'   · {c}')
    print(f'\n   {CLUMSY_TABLE}')
    return 0


def cmd_complic(a):
    _hdr('🔑 共谋（**明知是演出仍配合**）')
    print(f'   {COMPLIC_RULE}')
    print('\n内容: ' + ' · '.join(COMPLIC_ITEMS))
    print(f'\n   {COMPLIC_NO}')
    print(f'\n   {COMPLIC_4TH}')
    print(f'\n   {COMPLIC_TABLE}')
    return 0


def cmd_h(a):
    _hdr('H 类（**八项**）')
    for k, why in H_EIGHT:
        print(f'\n   【{k}】\n      {why}')
    return 0


def cmd_init(a):
    os.makedirs(os.path.dirname(a.init) or '.', exist_ok=True)
    with open(a.init, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow([k for k, _ in FIELDS])
        w.writerow(['TODO'] * len(FIELDS))
    print(f'已生成关系状态表: {a.init}')
    print('\n⚠️ 十四域：leave / afk / return / dignity / breakp / nth / skip / '
          'variant / ghost / first / rule / clumsy / complic / h')
    print('\n⚠️ `session_crossing` 列＝**跨会话/跨周目证据**')
    print('\n🔑 四个总状态机：PlayerSessionState · RepeatExposureState · '
          'GhostAssetState · FirstnessState')
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

    mismatch, no_legacy, no_cross, no_grade = [], [], [], []
    for i, r in enumerate(rows, 1):
        m = g(r, 'match').lower()
        if m not in ('yes', 'y', 'true', '是', '一致'):
            mismatch.append(i)
        if not g(r, 'legacy_value') or g(r, 'legacy_value') == 'TODO':
            no_legacy.append(i)
        p = g(r, 'session_crossing')
        if not p or p == 'TODO':
            no_cross.append(i)
        ev = g(r, 'evidence')
        if not ev or ev == 'TODO':
            no_grade.append(i)
        else:
            d = ev.split('.')[0].strip()
            if d.isdigit() and int(d) >= 7:
                no_grade.append(i)

    print('=' * 76)
    print(f'关系状态 · {len(rows)} 条')
    print('=' * 76)
    if mismatch:
        print(f'\n🚫 **不一致** {len(mismatch)} 条（行 {mismatch[:15]}）')
    if no_legacy:
        print(f'\n❌ {len(no_legacy)} 条缺**原版值**（行 {no_legacy[:15]}）')
    if no_cross:
        print(f'\n🚫 {len(no_cross)} 条缺**跨会话证据**'
              f'（行 {no_cross[:15]}）')
    if no_grade:
        print(f'\n🚫 {len(no_grade)} 条**证据等级缺失或 ≥7 级**'
              f'（行 {no_grade[:15]}）')

    if not (mismatch or no_legacy or no_cross or no_grade):
        print('\n✅ 关系状态：一致、原版值完整、跨会话已验证、证据达标')

    print('\n🔑 **前四十二轮覆盖了静态系统；'
          '本轮补的是「系统之间的时间接缝」。**')
    print('   🔑 **玩家关闭游戏后，原版如何记住自己正准备做什么？**')
    print('   🔴 **用布尔 `seen` 会误判"此后都可跳过"。**')
    print('   🔑 **门后没有模型 ≠ 没有承诺。回归玩家第一分钟不是新手教学，'
          '而是"游戏还认不认得我"。**')
    return 1 if (a.gate_check and
                 (mismatch or no_legacy or no_cross or no_grade)) else 0


def main():
    ap = argparse.ArgumentParser(description='关系状态：离开/第N次/幽灵/第一次')
    ap.add_argument('--leave', action='store_true')
    ap.add_argument('--afk', action='store_true')
    ap.add_argument('--return', action='store_true')
    ap.add_argument('--dignity', action='store_true')
    ap.add_argument('--breakp', action='store_true')
    ap.add_argument('--nth', action='store_true')
    ap.add_argument('--skip', action='store_true')
    ap.add_argument('--variant', action='store_true')
    ap.add_argument('--ghost', action='store_true')
    ap.add_argument('--first', action='store_true')
    ap.add_argument('--rule', action='store_true')
    ap.add_argument('--clumsy', action='store_true')
    ap.add_argument('--complic', action='store_true')
    ap.add_argument('--h', action='store_true')
    ap.add_argument('--init')
    ap.add_argument('--check')
    ap.add_argument('--gate-check', action='store_true')
    a = ap.parse_args()
    fns = {'leave': cmd_leave, 'afk': cmd_afk, 'return': cmd_return,
           'dignity': cmd_dignity, 'breakp': cmd_breakp, 'nth': cmd_nth,
           'skip': cmd_skip, 'variant': cmd_variant, 'ghost': cmd_ghost,
           'first': cmd_first, 'rule': cmd_rule, 'clumsy': cmd_clumsy,
           'complic': cmd_complic, 'h': cmd_h}
    for k, fn in fns.items():
        if getattr(a, k):
            return fn(a)
    if a.init:
        return cmd_init(a)
    if a.check:
        return cmd_check(a)
    print('❌ 需要 --leave / --afk / --return / --dignity / --breakp / --nth / '
          '--skip / --variant / --ghost / --first / --rule / --clumsy / '
          '--complic / --h / --init / --check 之一')
    return 2


if __name__ == '__main__':
    sys.exit(main())
