#!/usr/bin/env python3
"""沟通元语言 · 行动前风险账本 · 行为记忆 · 外部工具契约 ·
价值信号 · 认知地图 · 沉默设计（第四十八轮 A–G，含 H 三项）。

**🔑 本轮的粒度切换**：
> 🔑 **像素级复刻的对象是「玩家如何借系统理解世界、表达意图并承担后果」，
> 而不是菜单里有没有某一项功能。**
>
> 🔑 判断要从"**是否实现**"升级为"**是否形成同一行为契约**"。

用法:
  game_meta.py --comms   # 🔑 **沟通元语言（不是聊天的集合）**
  game_meta.py --ping    # **每条消息的独立身份与九种通道**
  game_meta.py --cross   # **跨语言契约（无语音玩家必须有完整路径）**
  game_meta.py --risk    # 🔑 **行动前风险账本（不是撤销）**
  game_meta.py --irrev   # **不可逆层级与提示强度**
  game_meta.py --memory  # 🔑 **行为记忆（带证据和期限的缓存）**
  game_meta.py --tool    # 🔑 **外部工具契约（第一方接口生态）**
  game_meta.py --schema  # **数据字典比接口技术更重要**
  game_meta.py --value   # 🔑 **价值信号（稀有度是通道同步的承诺）**
  game_meta.py --map     # 🔑 **认知地图（不是地图几何）**
  game_meta.py --silence # 🔑 **沉默是规则不是空缺**
  game_meta.py --h       # H 类三项
  game_meta.py --init ledger/meta48.csv
  game_meta.py --check ledger/meta48.csv --gate

退出码: 0 通过 / 1 缺项 / 2 用法错误
"""
import argparse
import csv
import os
import sys

# 🔑 A 沟通元语言
COMMS_RULE = '🔑 **沟通不是多个聊天的集合，而是多通道异步协同协议。**'
COMMS_FIVE = ['**游戏共存性**（是否打断操作）',
              '**多通信能力**（能否同时承载多条信息）',
              '**持久性**（信息保留多久）',
              '**表达能力**（能说多复杂）',
              '**多语言能力**（不同语言玩家能否理解）']
COMMS_MIN = '🔑 最低记录单位是「**情境 × 语义 × 媒介 × 反馈 × 消失规则**」'
COMMS_NO = '🔑 统一成一种"现代 ping"会**同时抹平**快速位置信号 · 身份表演 · '
'情感回应 · 固定短语 · 持久涂鸦之间的差异，🔴 **属于与 must-match 冲突**'
MSG_FIELDS = [
    ('`message_id`', '全局或会话唯一消息标识'),
    ('`message_type`', 'ping / emote / quick_chat / voice_macro / drawing / marker / signal_flare / radio / gesture'),
    ('`schema_version`', '通道协议版本'),
    ('`actor_id`', '发送者或匿名角色'),
    ('`intended_audience`', 'self / team / squad / faction / world / enemy-visible'),
    ('`semantic_intent`', 'go / danger / enemy / loot / help / affirm / disagree / thank'),
    ('`target_ref`', '位置 · 实体 · 物品 · 地图对象或 none'),
    ('`created_at`', '发送时间'),
    ('`expires_at`', '消失时间'),
    ('`ttl_policy`', '固定时长 / 距离衰减 / 事件取消 / 人工移除'),
    ('`display`', '3D 世界标记 · 地图标记 · 头顶 · 边缘箭头 · 聊天行'),
    ('`audio_cue`', '语音线 · 音效 · 是否随距离衰减'),
    ('`translation_bundle_key`', '本地化键'),
    ('`input_latency_ms`', '从输入到显示'),
    ('`conflict_policy`', '新信号覆盖 / 堆叠 / 取消旧信号'),
]
MSG_ID = '🔑 **`message_id` 是沟通复刻的第一类数据，不是后端实现细节。**'
SEMANTIC_NO = '🔑 `semantic_intent` **不能只写成自由字符串** —— '
'`enemy-here` 与 `danger` 可能共享红色标记，🔴 **却不一定拥有相同冷却 · '
'可见范围或战术含义**'
PING_TEST = '🔑 必须测目标类型变化：同一按键指向**地面 · 敌人 · 物品 · 门 · '
'队友 · 空区域**时，原版是否切换语义。'
'🔴 **若重制始终返回"前往此处"，上下文 ping 已偏离**'
CHANNELS_9 = [
    ('**单点 ping**', '目标类型 · 命中表面 · 地图/世界双显示 · 边缘箭头 · 距离衰减',
     '标记敌人 · 资源 · 门 · 路线 · 危险点', '合并为一种泛用标记；删除指向实体的语境'),
    ('**径向轮盘**', '打开时长 · 扇区数量 · 输入曲线 · 同义冲突 · 确认反馈',
     '高压下快速选"危险/集合/需要补给"', '用 12 项大轮盘替代原版 4 项'),
    ('**表情或动作**', '第三人称动画 · 范围 · 是否打断操作 · 重复冷却',
     '远距确认 · 嘲讽 · 庆祝 · 道歉', '仅留贴图或聊天 emoji，删除身体表演'),
    ('**预设短语**', '本地化键 · 触发条件 · 说话人身份 · 语音/文字回退',
     '"谢谢/抱歉/跟我来/需要治疗"', '把本地化文本写死成英文；删除语音回退'),
    ('**快捷语音**', '冷却 · 可中断性 · 收听距离 · **敌方是否听见**',
     '角色喊"守住这里"、危险呼叫', '让全局语音成为唯一路径；敌人可见信号泄露'),
    ('**涂鸦**', '世界坐标 · 笔刷 · 持久性 · 清理 · 遮挡 · 可举报性',
     '标注路线 · 箭头 · 脸和恶意涂写', '改为屏幕贴纸；缩短至数秒或无法删除'),
    ('**地图标记**', '图标 · 拥有者 · 队伍同步 · 编辑 · 过期 · 战争迷雾',
     '集结点 · 巡逻路线 · 埋伏点', '全图共享 · 永久存在 · 删除确认链改变'),
    ('**旗帜/光柱/信号弹**', '3D 位置 · 射程 · 动画 · 多信号层级',
     '跨地形集合 · 危险 · 求救', '用统一小地图图标替代；删除现场可观察层'),
    ('**无线电**', '频道 · 静默 · 按键 · 中继 · 距离 · 加密',
     '小队频段 · 监听 · 偷听', '全局无衰减语音；删除频道边界'),
]
ACK_4 = '🔑 **每个语义至少要有「同意 · 拒绝 · 完成 · 再次请求」四种回应。**'
'🔑 一个只能发起、不能取消和确认的 ping **不是完整指令**'
FOUR_TEST = '🔑 需要**四人会话脚本**：发送者只发一次；队友分别执行**同意 · '
'忽略 · 重复请求 · 拒绝**；**第五人验证敌队是否可见**'
CROSS_RULE = '🔑 **跨语言不是"翻译成同义文本"，'
'而是把不可译动作排除在契约之外。**'
CROSS_THREE = '🔑 要把每个条目分为「**可本地化文本**」「**不可译图标**」'
'「**不可压缩的表演**」。🔴 **后两类不允许被翻译成一句看似同义、'
'实际改变承诺的文本**'
CROSS_EG = '🔑 例如"help"**不应扩大成自动呼叫所有玩家**；'
'"谢谢"不应变成永久增益；"等我"不应变成暂停世界'
CROSS_NOVOICE = '🔑 **无语音玩家必须拥有完整贡献路径** —— '
'每条信息至少检查**键盘 · 手柄 · 鼠标 · 触屏**入口，'
'以及发送后的**视觉 · 听觉 · 字幕**反馈。'
'🔴 **若关闭语音会失去关键战术信息，就违反游戏共存性和公平协作原则**'
CROSS_RACE = '🔑 **重复 · 冲突 · 垃圾信号必须被测试** —— '
'短间隔三次同一 ping 可能是"敌人在这里"，也可能是"你在害我"；'
'同一地点的新"集合"可能**覆盖 · 确认或否定**旧"危险"。'
'🔑 原版若允许堆叠，🔴 **重制去重就是信息损失**；'
'原版若只保留最新，🔴 **重制堆叠就是噪声增加**'

# 🔑 B 风险账本
RISK_RULE = '🔑 **"能不能反悔"只决定后果多严重，'
'"行动前知道什么"才决定玩家是否认为选择属于自己。**'
RISK_STUDY = '🔑 关于保存与读档的经典观点指出：**玩家应依据直接损失比较'
'决定是否读档**；🔑 **若近期损失已充分预告，玩家更可能继续**；'
'🔑 **当玩家拥有选择风险及其执行方式的自由时，也更容易接受结果**'
RISK_LEDGER = [
    ('`commit_id`', '决策唯一标识'),
    ('`trigger`', '触发位置 · 时间 · 输入'),
    ('`intent_options`', '可执行动作'),
    ('**`information_available_before`**', '**可预览内容**'),
    ('`probability_exposed`', '是否暴露概率 · 区间或隐藏'),
    ('`probability_distribution`', '概率及随机源'),
    ('`cost_visible`', '资源 · 时间 · 关系 · 机会成本'),
    ('`best_case`', '最好结果'),
    ('**`worst_case`**', '**最坏结果**'),
    ('`undo_path`', '撤销 · 回城 · 读档 · 重投'),
    ('`save_snapshot_id`', '保存前状态'),
    ('**`irreversibility_level`**', '完全可逆 / 资源可逆 / 叙事不可逆 / 元进度不可逆'),
    ('`confirmation_strength`', '无提示 / 一次确认 / 双重确认 / 等待 / 退出重入'),
    ('`preview_fidelity`', '真模拟 / 概率 / 占位 / 纯文本'),
    ('`risk_currency`', '生命 · 资源 · 时间 · 关系 · 存档 · 声誉 · 元进度'),
    ('`recoverability`', '自动恢复 / 可购回 / 重做 / 永久损失'),
    ('`failure_explanation_id`', '失败归因模板'),
    ('`camera_lock`', '过场 · 输入 · 菜单 · 保存锁定'),
]
IRREV_RULE = '🔑 **提示强度必须根据不可逆层级增加，'
'但提示本身不能成为风险的一部分。**'
IRREV_EG = '🔑 只消耗 5 金币且可重试的选择，若要求输入完整"我已知晓"句子，'
'🔴 **会把低代价变成操作负担**；'
'永久杀死 · 覆盖存档 · 删除物品 · 背叛阵营 · 改变通关状态的选择，'
'🔴 **只出现一次普通确认，则会低估损失**'
SAVE_BOUND = '🔑 **保存边界本身就是风险账本的一部分** —— '
'玩家需知道当前处于**自动保存 · 检查点 · 手动保存 · 事务性预览 · 只读**状态。'
'🔴 **该边界不能用平台自动云同步覆盖**'
PREVIEW_TWO = '🔑 **预览边界要区分"发现"与"选择"** —— '
'掉落表概率 · 资源消耗 · 路径终点可能原版不公开；'
'角色动机 · 按键后果 · 当前保存状态通常可以公开。'
'🔴 **不得用"现代玩家更聪明"为由统一补上信息**'

# 🔑 C 行为记忆
MEM_RULE = '🔑 **行为记忆不是画像表，而是带证据和期限的缓存。**'
MEM_DIFF = '🔑 与第四十二轮的关键差异：🔑 **原版是否真的读取并改变行为，'
'以及玩家能否看见 · 理解 · 关闭 · 删除这种读取**'
MEM_FIELDS = [
    ('`observation_id`', '观察标识'),
    ('`player_consent_state`', '同意状态'),
    ('`observed_signal`', '实际观察信号（区分事实与推断）'),
    ('`inference_rule`', '推断规则（**防止黑箱读心**）'),
    ('`confidence`', '置信度'),
    ('`valid_from` / `expires_at`', '生效 / 过期时间（**防止永久监视**）'),
    ('`scope`', '本局 / 本周目 / 本存档 / 本设备 / 账号'),
    ('`usage`', '允许用途（**禁止用途扩散**）'),
    ('`effect_observed`', '实际效果'),
    ('`visual_explanation`', '玩家可见反馈（防止"被操纵感"）'),
    ('`opt_out`', '关闭路径'),
    ('`deletion_audit`', '删除审计'),
    ('`retention_policy`', '留存策略'),
]
MEM_OK = '🔑 **跨局习惯最适合用于**菜单排序 · 默认装备 · 提示折叠 · '
'路线备选 · 训练复现；🔴 **最危险的是动态改变平衡**'
MEM_NO = '🔑 常用武器快捷位 · 死亡点 · 地图路线可用于**缩短重复操作**，'
'🔴 **但不应自动强化敌人弱点 · 调整掉落 · 降低判定难度**'
MEM_MANUAL = '🔑 **每个自动化建议都必须有一个手动等价物。**'
'🔴 若原版允许玩家手动选择，重制不能把推荐锁成强制流程；'
'🔴 **若原版没有记忆，重制不得用机器学习"改善体验"**'
MEM_SURVEIL = '🔑 **被监视感来自看不见的读取和无法关闭的影响，'
'而不是数据量本身。** 若记录**只在本地 · 短期 · 透明 · 不改变规则**，'
'可能只是便利；🔴 **若跨设备永久保存 · 改变敌人或奖励 · 无法查看和删除，'
'即使只记录两个字段，也会形成操纵**'

# 🔑 D 外部工具契约
TOOL_RULE = '🔑 **若外部流程能在原版中稳定工作，'
'就应被当成游戏接口生态，而不是"作弊"。**'
TOOL_MIN = '🔑 接口的最小单元是「**端点—字段—语义—版本—稳定性**」，'
'🔴 **而不是"有 JSON"**'
TOOL_3 = [('**HTTP 或进程间接口**', '`OpenAPI`', '端点 · 参数 · 请求 · 响应 · 认证 · 错误码 · 示例'),
          ('**数据文件或事件载荷**', '`JSON Schema`', '字段 · 单位 · 枚举 · 必填项 · 时区 · 精度'),
          ('**跨进程遥测**', '`OpenTelemetry`', '事件 · 指标 · 日志 · 资源 · 采样 · 导出目标')]
TOOL_FIELDS = '`surface_id` · `transport` · `auth_model` · `schema_id` · '
'`schema_version` · `stability` · `data_class` · `export_format` · '
'`encoding` · **`timezone`** · **`units`** · **`precision`** · '
'`rate_limit` · `retention` · `local_only` · `consent` · `known_consumers`'
SCHEMA_RULE = '🔑 **工具能否迁移，取决于字段语义是否稳定，而不是 JSON 是否美观。**'
SCHEMA_EG = '🔑 例如"damage"可能指**显示伤害 · 应用伤害 · 暴击前 · 暴击后 · '
'护甲前 · 护甲后**；"position"可能采用不同坐标系；'
'"timestamp"可能采用**本地时间 · UTC · 游戏时间 · tick**。'
'🔴 **重制即使保留 JSON 结构，只要单位 · 精度 · 坐标系变化，'
'外部计算器就可能静默错误**'
SCHEMA_TIME = '🔑 **时区和随机源决定回放与数据是否能跨工具成立** —— '
'若日志含日期应明确本地时间与 UTC；若含随机事件应保留**seed · 版本 · '
'算法 · 抽取边界 · 消耗顺序**'
ANTICHEAT = '🔑 **可以限制外部进程，但不能因此破坏原版公开的数据表面。**'
'🔑 禁止项：**内存读写 · 自动瞄准 · 未公开协议 · 注入 · 自动化输入 · '
'实时模型推理**；允许项：**本地只读数据 · 玩家主动导出 · 剪贴板 · '
'开放文档 · 可验证回放**。'
'🔑 overlay 若只读取玩家已导出的文件，🔴 **不应被当成作弊**'
WIKI_NO = '🔑 **第三方 wiki · 伤害计算器 · 地图站只能作为假设来源。**'
'🔴 除非能访问原版资源 · 调试符号或开发者文档，'
'否则不能把社区推断写入 must-match'

# 🔑 E 价值信号
VAL_RULE = '🔑 **玩家判断"这个东西值多少"时，'
'使用的是多通道信号，而不是读取隐藏数值。**'
VAL_TIER = '🔑 **稀有度是通道同步的承诺，不是一张颜色表。**'
VAL_FIELDS = '`tier_id` · `localized_name` · `icon_shape` · `outline` · '
'`background_gradient` · `text_color` · `ambient_light` · `beam_color` · '
'**`beam_duration_ms`** · `beam_occlusion` · `hold_sound` · `drop_sound` · '
'`music_ducking` · `animation_curve` · **`drop_delay_ms`** · '
'`label_duration_ms` · `camera_reaction` · `inventory_insert_animation` · '
'`stacking_behavior` · `first_discovery_bonus` · `colorblind_safe_pattern`'
VAL_TEST = '🔑 测试应把**声音 · 颜色 · 动画 · 文字 · 镜头分别屏蔽**，'
'确认玩家仍能识别层级。🔑 若删除声音后层级完全无法判断，'
'原版可能依赖听觉；🔴 **若只能依赖颜色，则重制对色觉差异玩家构成公平问题**'
VAL_CADENCE = '🔑 **掉落演出时长必须与稀有度建立可复现映射**：'
'普通物品立即入库 → 稀有先出现闪光和延迟 → 史诗有更长光束 · 镜头 · 音效 → '
'传说还伴随**环境停顿**。'
'🔴 **重制若把全部稀有度压缩成同一种宝箱演出，'
'价值感会从"有层级"变成"一次性奖励"**'
VAL_CULT = '🔑 **价值信号不能跨作品机械移植** —— '
'欧洲传说装备的紫色 · 东亚语境的金色 · 抽卡文化的彩虹色，'
'🔴 **并不能直接证明某种颜色全球通用。颜色只能记录为原版具体表现**'
VAL_INFL = '🔑 **"钱不值钱"是玩家对成本梯度的判断，不是金币余额变化** —— '
'要记基础物品价格 · 升级费用 · 回收价 · 商店刷新 · 货币兑换 · '
'终局材料稀缺度 · 奖励节奏'

# 🔑 F 认知地图
MAP_RULE = '🔑 **F 的复刻对象不是地图几何，'
'而是玩家形成的地标—路径—关系网络。**'
MAP_ORDER = '🔑 心理地图通常**先识别地标，再建立路径连接，'
'最后形成整体空间关系**。'
'🔑 **即使地图拓扑一致，只要地标被替换 · 灯光变化 · 声音遮蔽 · '
'节点重排 · 方向提示消失，玩家的方向感也可能无法重建**'
MAP_FIELDS = '`anchor_id` · `zone` · `landmark` · **`audio_landmark`** · '
'**`light_direction`** · `path_to_next` · **`turning_signature`** · '
'`distance_estimate` · `vertical_relation` · `map_reveal_condition` · '
'`offscreen_indicator` · `fast_travel_relation` · `load_boundary` · '
'`death_restart_point`'
MAP_BLIND = '🔑 **"不看地图导航"测试**：新玩家完成一次带地图引导，'
'随后关闭**小地图 · 目标标记 · 指南针 · 光柱 · 队友 ping**，'
'要求**沿原路返回 · 前往已访问目标 · 迷路后重新定向**。'
'记迷路次数 · 方向选择 · 声音地标使用 · 回退策略 · 重新定向所需时间'
MAP_MIRROR = '🔑 **镜像 · 旋转 · 折叠空间 · 电梯 · 传送门 · 快速旅行点，'
'每个都要记入口朝向 · 出口朝向 · 重力 · 天空盒 · 地图索引 · 玩家转身角度**'
MAP_FIX = ['传送前后**固定角色朝向**', '保留**世界北向指示**',
           '小地图**明确折叠关系**', '使用**可识别门 · 声音 · 灯光**',
           '加载后提供**短暂方向回正**', '用**房间编号或稳定地图索引**补充连续性']
MAP_NO = '🔑 **只测试"能够到达"无法发现传送方向感破坏。**'
'🔑 原版允许玩家通过反复失败形成**捷径记忆**；'
'🔴 **重制若随机改变捷径入口 · 删除捷径线索 · 自动导航，就会破坏身体记忆**'

# 🔑 G 沉默设计
SIL_RULE = '🔑 **沉默是规则而不是空缺。**'
SIL_TWO = '🔑 **提示关闭属于设置；'
'不显示隐藏路径 · 捷径 · 彩蛋 · 失败条件 · 跨周目秘密，属于沉默设计。'
'🔴 二者不能混为一类**'
SIL_FIELDS = '`region_id` · **`unsaid_truth`** · **`discovery_channel`** · '
'`retry_teaches` · `false_lead` · `first_failure_consequence` · '
'`hint_threshold` · `hint_text` · `hint_authority` · `death_count` · '
'`time_spent` · **`cross_session_memory`**'
SIL_EG = '🔑 原版不提示门后有捷径，但**地面痕迹 · 敌人走向 · 声音差异 · '
'回头可观察的视野**会告诉玩家"这里可能连通"；'
'🔴 **重制若加上箭头，就是把发现性秘密变成交付清单**。'
'🔴 反之，原版已有教程文本、重制删除却声称"保留硬核沉默"，同样不是复刻'
SIL_CONSIST = '🔑 **沉默必须跨系统一致** —— '
'若原版不提示隐藏却持续提示收集品、不提示捷径却用箭头标出普通路径、'
'不提示危险却在低威胁处反复弹窗，🔴 **玩家会失去规则预期**。'
'🔑 应扫描所有区域，比较"**可提示事项**"与"**实际提示事项**"'
SIL_WEEK = '🔑 **沉默还应覆盖多周目** —— '
'第一次不知道的机关，第二次可能变成玩家主动炫耀的知识；'
'第一次的空白，第二次可以成为结构笑点'

H_3 = [
    ('**H1 跨局秘密记忆**',
     '🔑 "只有玩过的人才懂"会形成跨局知识，载体可能只是**文本 · 贴图 · '
     '关卡排列 · NPC 眼神**。🔑 must-match 不是"NPC 必须记得"，'
     '而是**原版是否拥有可复现的跨局读取**。'
     '记触发条件 · 写入时机 · 有效期 · 是否依赖同一存档或设备 · '
     '可见反馈 · 失效条件。🔑 若重制因跨平台账号无法读取旧平台痕迹，'
     '🔴 **应明确记录为平台能力差异，而不是悄悄改写秘密状态**'),
    ('**H2 跨游戏迁移痕迹**',
     '🔑 玩家**不是每款游戏都从零开始**——带入的是**操作 · 地图阅读 · '
     '风险判断 · 术语 · 社群记忆**。'
     '🔑 这不是要求新作向前作兼容，而是要求新作在"**玩家误迁移**"的地方'
     '保持原版行为。🔑 老玩家可能把原作**判定窗口 · 跳跃距离 · 商店规则**'
     '迁移到新作；🔴 **若新作确实允许并利用了这种误判，就不能自动修正**'),
    ('**H3 可携带元数据**',
     '🔑 每个玩家作品可导出：**作品 ID · 标题 · 作者 · 原引擎版本 · '
     '目标引擎版本 · 迁移工具版本 · 创建时间 · 修改时间 · 依赖资产 · '
     '许可证声明 · 父作品 ID · 派生关系 · 导出 schema 版本**。'
     '🔴 **这些用于跨工具迁移和出处追踪，不代表原始素材权利可无条件迁移**。'
     '🔴 **不能把"加入 SchemaStore"误写为 must-match**'),
]

CONFLICTS = [
    '❌ **统一为一种现代 ping**（抹平位置信号 · 身份表演 · 持久涂鸦的差异）',
    '❌ **自动翻译固定短语时改变承诺**（同义文本 ≠ 同义行为）',
    '❌ **关闭语音时删除关键战术信息**（违反无语音玩家公平参与）',
    '❌ **加入原版没有的安全预览**（可能暴露原版隐藏条件）',
    '❌ **删除原版的危险提示**（破坏行动前风险计算）',
    '❌ **用平台自动备份覆盖保存边界**（把承担后果变成等待回滚）',
    '❌ **"聪明 AI 替玩家避免坏结果"**（玩家不再拥有失败所有权）',
    '❌ **黑箱 AI 实时改变敌人或奖励**（结果不可审计）',
    '❌ **永久画像 · 跨设备不可删**（超出可解释便利，形成监视）',
    '❌ **只有"关闭个性化"总开关**（无法审计单项用途）',
    '❌ **改格式 · 混淆 · 加密原本可导出数据**（破坏外部工具生态）',
    '❌ **用反作弊无差别封锁只读导出**（混淆安全与玩家数据权利）',
    '❌ **外挂式工具新增为默认 must-match**（原版没有的接口不能补建）',
    '❌ **把所有外部工具都视为作弊**（忽略玩家真实工作流）',
    '❌ **统一稀有度颜色**（可能改变跨层级识别）',
    '❌ **缩短或延长所有掉落演出**（改变价值预期与时间投入）',
    '❌ 提高全服掉落解决终局疲劳（改变原版稀缺感与通胀）',
    '❌ **用异作品颜色规范覆盖原版**',
    '❌ **自动导航 · 改变地标 · 统一灯光**（破坏无地图导航）',
    '❌ **随机化镜像规则但保留原地图外观**（玩家无法建立空间记忆）',
    '❌ **删除捷径线索**（破坏身体记忆）',
    '❌ **所有区域统一加提示或箭头**（破坏秘密与学习发现）',
    '❌ **原版已有提示却删除并称为"硬核"**（把信息缺失误当沉默设计）',
    '❌ **跨周目新增回忆提示**（可能改变元叙事知识边界）',
    '❌ **自动纠正玩家的前作误迁移**（破坏原版故意利用的经验偏差）',
    '❌ **未经验证便声称玩家会迁移某项习惯**（不能写成 must-match）',
]

FIELDS = [
    ('item_id', '项编号'),
    ('domain', '域（comms / ping / cross / risk / irrev / memory / tool / '
               'schema / value / map / silence / h）'),
    ('legacy_value', '**原版值**'),
    ('new_value', '新引擎值'),
    ('match', '**是否一致**'),
    ('contract_evidence', '**行为契约证据**（可回放至原版可观察结果）'),
    ('evidence', '证据等级 1-8'),
]


def _hdr(t, w=80):
    print('=' * w)
    print(t)
    print('=' * w)


def cmd_comms(a):
    _hdr('🔑 沟通元语言（**不是聊天的集合**）')
    print(f'   {COMMS_RULE}')
    print('\n五维: ' + ' · '.join(COMMS_FIVE))
    print(f'\n   {COMMS_MIN}')
    print(f'\n   {COMMS_NO}')
    print(f'\n   {MSG_ID}')
    return 0


def cmd_ping(a):
    _hdr('消息身份与九种通道')
    print('\n' + MSG_ID)
    print('\n十五条字段:')
    for k, v in MSG_FIELDS:
        print(f'   {k:<38} {v}')
    print(f'\n   {SEMANTIC_NO}')
    print(f'\n   {PING_TEST}')
    print('\n九种通道:')
    for k, f, use, bad in CHANNELS_9:
        print(f'\n   【{k}】\n      字段: {f}\n      玩法: {use}\n      🔴 偏离: {bad}')
    print(f'\n   {ACK_4}')
    print(f'\n   {FOUR_TEST}')
    return 0


def cmd_cross(a):
    _hdr('跨语言契约')
    print(f'   {CROSS_RULE}')
    print(f'\n   {CROSS_THREE}')
    print(f'\n   {CROSS_EG}')
    print(f'\n   {CROSS_NOVOICE}')
    print(f'\n   {CROSS_RACE}')
    return 0


def cmd_risk(a):
    _hdr('🔑 行动前风险账本（**不是撤销**）')
    print(f'   {RISK_RULE}')
    print(f'\n   {RISK_STUDY}')
    print('\n十八条字段:')
    for k, v in RISK_LEDGER:
        print(f'   {k:<40} {v}')
    return 0


def cmd_irrev(a):
    _hdr('不可逆层级与提示强度')
    print(f'   {IRREV_RULE}')
    print(f'\n   {IRREV_EG}')
    print(f'\n   {SAVE_BOUND}')
    print(f'\n   {PREVIEW_TWO}')
    return 0


def cmd_memory(a):
    _hdr('🔑 行为记忆（**带证据和期限的缓存**）')
    print(f'   {MEM_RULE}')
    print(f'\n   {MEM_DIFF}')
    print('\n字段:')
    for k, v in MEM_FIELDS:
        print(f'   {k:<34} {v}')
    print(f'\n   {MEM_OK}')
    print(f'\n   {MEM_NO}')
    print(f'\n   {MEM_MANUAL}')
    print(f'\n   {MEM_SURVEIL}')
    return 0


def cmd_tool(a):
    _hdr('🔑 外部工具契约（**第一方接口生态**）')
    print(f'   {TOOL_RULE}')
    print(f'\n   {TOOL_MIN}')
    print('\n三层:')
    for k, t, d in TOOL_3:
        print(f'   {k:<24} {t:<18} {d}')
    print(f'\n表面字段: {TOOL_FIELDS}')
    print(f'\n   {ANTICHEAT}')
    print(f'\n   {WIKI_NO}')
    return 0


def cmd_schema(a):
    _hdr('数据字典（**比接口技术更重要**）')
    print(f'   {SCHEMA_RULE}')
    print(f'\n   {SCHEMA_EG}')
    print(f'\n   {SCHEMA_TIME}')
    return 0


def cmd_value(a):
    _hdr('🔑 价值信号（**稀有度是通道同步的承诺**）')
    print(f'   {VAL_RULE}')
    print(f'\n   {VAL_TIER}')
    print(f'\n字段: {VAL_FIELDS}')
    print(f'\n   {VAL_TEST}')
    print(f'\n   {VAL_CADENCE}')
    print(f'\n   {VAL_CULT}')
    print(f'\n   {VAL_INFL}')
    return 0


def cmd_map(a):
    _hdr('🔑 认知地图（**不是地图几何**）')
    print(f'   {MAP_RULE}')
    print(f'\n   {MAP_ORDER}')
    print(f'\n字段: {MAP_FIELDS}')
    print(f'\n   {MAP_BLIND}')
    print(f'\n   {MAP_MIRROR}')
    print('\n可归位机制:')
    for m in MAP_FIX:
        print(f'   · {m}')
    print(f'\n   {MAP_NO}')
    return 0


def cmd_silence(a):
    _hdr('🔑 沉默设计（**是规则不是空缺**）')
    print(f'   {SIL_RULE}')
    print(f'\n   {SIL_TWO}')
    print(f'\n字段: {SIL_FIELDS}')
    print(f'\n   {SIL_EG}')
    print(f'\n   {SIL_CONSIST}')
    print(f'\n   {SIL_WEEK}')
    return 0


def cmd_h(a):
    _hdr('H 类（**三项**）')
    for k, why in H_3:
        print(f'\n   【{k}】\n      {why}')
    return 0


def cmd_init(a):
    os.makedirs(os.path.dirname(a.init) or '.', exist_ok=True)
    with open(a.init, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow([k for k, _ in FIELDS])
        w.writerow(['TODO'] * len(FIELDS))
    print(f'已生成元协议表: {a.init}')
    print('\n⚠️ 十二域：comms / ping / cross / risk / irrev / memory / tool / '
          'schema / value / map / silence / h')
    print('\n⚠️ `contract_evidence` 列＝**行为契约证据**'
          '（可回放至原版可观察结果）')
    print('\n🔑 新模板：communication-meta-language · modality-matrix · '
          'risk-before-action · risk-ledger · behavior-memory · '
          'adaptation-budget · external-tool-contract · tool-surface · '
          'value-semiotics · rarity-feedback · cognitive-map · '
          'spatial-anchor · silence-policy · meta-memory · '
          'cross-game-migration · portable-metadata')
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

    mismatch, no_legacy, no_contract, no_grade = [], [], [], []
    for i, r in enumerate(rows, 1):
        m = g(r, 'match').lower()
        if m not in ('yes', 'y', 'true', '是', '一致'):
            mismatch.append(i)
        if not g(r, 'legacy_value') or g(r, 'legacy_value') == 'TODO':
            no_legacy.append(i)
        p = g(r, 'contract_evidence')
        if not p or p == 'TODO':
            no_contract.append(i)
        ev = g(r, 'evidence')
        if not ev or ev == 'TODO':
            no_grade.append(i)
        else:
            d = ev.split('.')[0].strip()
            if d.isdigit() and int(d) >= 7:
                no_grade.append(i)

    print('=' * 76)
    print(f'元协议层 · {len(rows)} 条')
    print('=' * 76)
    if mismatch:
        print(f'\n🚫 **不一致** {len(mismatch)} 条（行 {mismatch[:15]}）')
    if no_legacy:
        print(f'\n❌ {len(no_legacy)} 条缺**原版值**（行 {no_legacy[:15]}）')
    if no_contract:
        print(f'\n🚫 {len(no_contract)} 条缺**行为契约证据**'
              f'（行 {no_contract[:15]}）')
    if no_grade:
        print(f'\n🚫 {len(no_grade)} 条**证据等级缺失或 ≥7 级**'
              f'（行 {no_grade[:15]}）')

    if not (mismatch or no_legacy or no_contract or no_grade):
        print('\n✅ 元协议层：一致、原版值完整、行为契约已验证、证据达标')

    print('\n🔑 **对象不是菜单里有没有功能，'
          '而是玩家如何借系统理解世界、表达意图并承担后果。**')
    print('   🔑 **判断从"是否实现"升级为"是否形成同一行为契约"。**')
    print('   🔑 **同义文本 ≠ 同义行为；删除声音后的层级识别是公平问题。**')
    print('   🔴 **沉默是规则，不是空缺。**')
    return 1 if (a.gate_check and
                 (mismatch or no_legacy or no_contract or no_grade)) else 0


def main():
    ap = argparse.ArgumentParser(description='元协议层：沟通/风险/记忆/工具')
    ap.add_argument('--comms', action='store_true')
    ap.add_argument('--ping', action='store_true')
    ap.add_argument('--cross', action='store_true')
    ap.add_argument('--risk', action='store_true')
    ap.add_argument('--irrev', action='store_true')
    ap.add_argument('--memory', action='store_true')
    ap.add_argument('--tool', action='store_true')
    ap.add_argument('--schema', action='store_true')
    ap.add_argument('--value', action='store_true')
    ap.add_argument('--map', action='store_true')
    ap.add_argument('--silence', action='store_true')
    ap.add_argument('--h', action='store_true')
    ap.add_argument('--init')
    ap.add_argument('--check')
    ap.add_argument('--gate-check', action='store_true')
    a = ap.parse_args()
    fns = {'comms': cmd_comms, 'ping': cmd_ping, 'cross': cmd_cross,
           'risk': cmd_risk, 'irrev': cmd_irrev, 'memory': cmd_memory,
           'tool': cmd_tool, 'schema': cmd_schema, 'value': cmd_value,
           'map': cmd_map, 'silence': cmd_silence, 'h': cmd_h}
    for k, fn in fns.items():
        if getattr(a, k):
            return fn(a)
    if a.init:
        return cmd_init(a)
    if a.check:
        return cmd_check(a)
    print('❌ 需要 --comms / --ping / --cross / --risk / --irrev / --memory / '
          '--tool / --schema / --value / --map / --silence / --h / '
          '--init / --check 之一')
    return 2


if __name__ == '__main__':
    sys.exit(main())
