#!/usr/bin/env python3
"""交互事务契约：建造 / 交易 / 目标呈现 / 长期成长 / 回放
（第三十二轮 A / B / C / D / E 类，含 F / G 补充）。

**🔑 本轮核心视角**：
> 研究单位从"**系统**"改成"**交互事务**"。
>
> 真正的新增价值是识别"**原版会、重制没有**"的**交互副作用** ——
> 一次用户动作是否生成预览 · 是否允许中途修改 ·
> 何时进入不可逆提交 · 失败后如何恢复 ·
> 对库存/货币/世界/任务/UI 产生哪些可观察变化。

**🔑 本轮最重要的原则**：
> 🔑 **热门工具解决的是算法，不是原版的设计意图。**
> 🔑 Recast/Detour · OBS · Luanti · Google Blocks 提供的是
> **接口 · 许可证 · 工程实现参照**，
> 🔴 **不能证明原版商店先扣钱还是先扣库存**，
> 也**不能替原版决定建筑超上限时静默拒绝还是播放失败反馈**。
> 🔑 **工具解决"怎样实现"，原版测量解决"实现成什么"** —— 二者不能互相替代。

用法:
  game_txn_contract.py --six     # 🔑 **交互事务六类副作用**
  game_txn_contract.py --place   # 🔴 建造**吸附只是提示，合法性才是门槛**
  game_txn_contract.py --deny    # 🔴 放置**五种否决**
  game_txn_contract.py --undo    # 撤销**按副作用事务分组**
  game_txn_contract.py --trade   # 🔑 交易**预览是可审计净变化**
  game_txn_contract.py --lock    # 🔴 **确认与锁定是两个状态**
  game_txn_contract.py --batch   # 🔑 批量结算是**舍入问题**
  game_txn_contract.py --buyback # **买回窗口**与偷窃后果
  game_txn_contract.py --money   # 多货币**零钱不是展示层**
  game_txn_contract.py --obj     # 🔑 目标**三个独立视图**
  game_txn_contract.py --seethru # 🔴 **"是否穿墙"四种模式**
  game_txn_contract.py --multio  # 多目标**稳定排序**
  game_txn_contract.py --navpath # 🔑 路径是**连续轮询查询**
  game_txn_contract.py --curve   # 成长**按相邻区间测量**
  game_txn_contract.py --stuck   # 🔑 **卡关补偿是隐式设计**
  game_txn_contract.py --respec  # 洗点**状态残留**
  game_txn_contract.py --maxlv   # 🔴 **满级后**必须单独建模
  game_txn_contract.py --follow  # "世界跟随"**四层**
  game_txn_contract.py --replay  # 🔑 **事实 vs 像素**三种模型
  game_txn_contract.py --export  # 导出**HUD/分轨/隐私是语义**
  game_txn_contract.py --fg      # F / G 补充
  game_txn_contract.py --init ledger/txn_contract.csv
  game_txn_contract.py --check ledger/txn_contract.csv --gate

退出码: 0 通过 / 1 缺项 / 2 用法错误
"""
import argparse
import csv
import os
import sys

# 🔑 六类副作用
SIX_SIDE = [
    '**允许**', '**拒绝**', '**撤销**', '**回滚**', '**补偿**', '**可见性**',
]

TXN_FIELDS = [
    'actor', 'target', 'context', 'preconditions', '**preview**',
    'commit_frame', '**rollback_policy**', '**side_effects**', 'authority',
    'observable_order', 'must_match_evidence',
]

TXN_RULE = '🔑 建议新建 `rules/interaction_contract.md`，每类操作至少记录 ' + \
    ' · '.join(TXN_FIELDS)

# 🔴 建造
PLACE_TWO = [
    ('**snap_candidate**（预览）', '半按显示辅助线、完全按下前定位'),
    ('**snap_commit**（确认）', '完全按下确认吸附位置'),
]

PLACE_FIELDS = [
    '基准类型（点 · 边 · 面 · 顶点 · 网格）', '吸附半径', '有效法线',
    '碰撞降级', '预览颜色', '**确认音**', '**失败反馈**',
    '**连续拖拽中是否重新求解**',
]

PLACE_RULE = [
    '🔑 **吸附只是视觉提示，合法性才是提交门槛**',
    '🔑 吸附至少应拆成 `snap_candidate`（预览）与 `snap_commit`（确认）'
    '**两个阶段**',
    '🔴 **"高亮但无法放置"不能仅记录为灰色** —— '
    '要记它**为何失败**：地面坡度 · ownership · 权限 · 材料 · '
    '结构连接 · NPC 占用 · 任务区域',
]

# 🔴 五种否决
DENY_FIVE = [
    ('**几何冲突**', '重叠 · 越界 · 侵入地形'),
    ('**结构冲突**', '无支撑 · 重心外溢 · 连接断裂'),
    ('**语义冲突**', '任务区域 · 剧情锁 · 房屋 ownership'),
    ('**运行时约束**', '预算 · 内存 · 模拟成本 · 物理孤岛'),
    ('**输入冲突**', '正在移动 · 菜单打开 · 动画未提交'),
]

DENY_RULE = '🔴 **若只记录"能否放置"，重制就会把不同失败合并成同一个'
'"无效位置"** —— 而原版可能分别表现为**不同提示 · 音效 · 震动 · 权限界面**'

# 撤销
UNDO_FIELDS = [
    'undo_unit_id', 'input_event_id', 'committed_at', 'world_version',
    'commands[]', '**inverse_commands[]**', 'postconditions[]',
    '**compensation_policy**',
]

UNDO_RULE = [
    '🔑 **撤销必须按副作用事务分组**',
    '🔑 单次"放置"**未必等于一个撤销单元** —— 批量放置 · 镜像 · '
    '蓝图实例化 · 附带扣除资源 · 改变 ownership · 连接管道 · '
    '触发结构完整性检查，应形成事务',
    '🔑 连续拖动**可能合并为一条，也可能每条部件一条**；'
    '蓝图粘贴**可能是一整组，也可能只撤销最后一个部件**',
    '🔴 **不能擅自统一** —— 必须同时做**操作日志 · 录像回看 · 玩家访谈**'
    '三种取证',
]

# 🔑 交易预览
TRADE_PREVIEW = [
    'items_delta[]', 'currency_delta[]', '**capacity_delta[]**',
    'faction_delta[]', 'price_basis', 'barter_applied', 'tax_applied',
    'discount_applied', 'reputation_lock', 'side_effects[]', 'can_commit',
    '**reason_code**',
]

TRADE_RULE = [
    '🔑 **预览必须是可审计的净变化，而不是单价展示**',
    '🔑 买 10 个物品不能只显示单价 —— 要同时显示**总花费 · 背包是否溢出 · '
    '货币舍入后余数 · 折扣前/后价格 · 声望门槛 · 玩家是否能承担**',
    '🔑 预览必须明确它是"**当前世界状态的快照**"还是"**动态重新询价**" —— '
    '打开界面后涨价 · 商品售罄 · 声望变化时，是**保持原报价 · 重新询价 · '
    '还是取消交易**',
]

# 🔴 锁定
LOCK_STATES = [
    'offer_created', 'offer_valid_until', 'input_frozen', 'preview_finalized',
    'commit_requested', 'commit_acknowledged', 'rolled_back',
]

LOCK_RULE = [
    '🔑 **确认与锁定是两个状态，不是一句"点击确定"**',
    '🔑 修改任一数量 · 货币 · 物品时，原版究竟是**保留旧锁定 · 立即解锁 · '
    '还是只在提交时校验**，**必须以测量为准**',
    '🔴 **若锁定后价格仍变，会出现玩家按旧价锁定、提交时扣新价** —— '
    '这种差异**属于必须回放的交易录像**',
]

# 🔑 批量
BATCH_ITEMS = [
    '**逐件结算还是总量结算**', '**折扣应用在每件还是总额**',
    '**税率是否向下截断**', '多货币是否依次找零',
    '**舍入是银行家舍入 · 向零 · 向上 · 还是保留隐藏分数**',
    '**部分库存不足时整单失败还是成交可成交部分**',
]

BATCH_RULE = [
    '🔑 **批量结算的语义是四舍五入问题，不是性能问题**',
    '🔑 只保留展示小数而内部使用隐藏分数，才能避免买卖价差累积',
    '🔴 **但原版若确实每笔舍入，复刻也必须复刻该偏差**',
    '🔑 还应覆盖"**卖 1 件**"与"**卖最大数量**"'
    '**是否触发同一代码路径**',
]

# 买回
BUYBACK_FIELDS = [
    '**window_kind**（单次交易 · 当天 · 退出前 · 永久）',
    '**capacity**（最近 N 件 / 无限）',
    '**price_kind**（原价 · 回收价 · 涨价 · 不可用）',
    '**state_loss**（读档/退出/存档是否清除）',
    'ownership_change', 'visibility_in_inventory',
]

STEAL_ITEMS = [
    '检测事件', '即时声望', '阵营反应', '警报', '追捕', 'NPC 记忆',
    '任务失败', '**后续交易折扣**', '**能否撤销**',
]

STEAL_RULE = '🔑 **买回窗口与偷窃后果必须成为不可变事实字段**；'
'🔑 若原版"偷窃成功即永久改变世界"，**保存/读档是否回滚也要单独取证**'

# 多货币
MONEY_FIELDS = [
    'currency_id', 'integer_amount', 'subunit_amount', 'rounding_mode',
    'exchange_rate_version', 'fee_basis', 'fee_rounding', 'change_currency',
    'change_rounding', '**hidden_fraction**', '**negative_balance_policy**',
]

MONEY_RULE = [
    '🔑 **多货币和零钱不能当成展示层**',
    '🔑 结算要记来源与顺序：**先扣主货币，还是同时校验所有货币**；'
    '**找零不足是拒绝 · 允许负余额 · 还是用替代货币补齐**',
    '🔴 **除非原版存在，不应统一成"自动选择最优货币"** —— '
    '该行为**会改变玩家策略**',
]

# 🔑 目标三视图
OBJ_VIEWS = [
    ('**world_position / world_direction**', '世界中的真实位置与方向'),
    ('**screen_projection**', '屏幕投影（箭头/边缘指示）'),
    ('**minimap_position / compass_position**', '小地图与罗盘'),
]

OBJ_FIELDS = [
    'world_position', 'world_direction', 'screen_projection',
    'minimap_position', 'compass_position', 'distance_representation',
    'occlusion_state', '**exploration_state**',
]

OBJ_RULE = [
    '🔑 **一个目标至少存在世界 · 屏幕 · 地图三个坐标**',
    '🔑 光柱 · 箭头 · 地面标记 · **声音信标**各属不同通道 —— '
    '🔴 **不能只把"目标箭头"作为一个 UI 组件**',
    '🔑 要测屏幕目标 · 3D 世界标记 · 小地图**是否同步切换** —— '
    '🔴 若追踪目标改变而三处刷新不在同一帧，'
    '玩家会看到**箭头已变、地图仍高亮旧目标**',
]

# 🔴 穿墙四模式
SEETHRU_FOUR = [
    'A. **完全不可见**，只在小地图显示',
    'B. **墙后压缩为边缘指示**',
    'C. **穿墙显示但精度降低**',
    'D. **完全 3D 透视**',
]

SEETHRU_RULE = [
    '🔑 还要测**高度差 · 多层建筑 · 室内外 · 地下 · 镜面 · 分屏**'
    '各自如何表现',
    '🔑 **最容易被重制破坏的不是箭头方向，'
    '而是"未探索区域是否显示目标"** —— '
    '**显示太多会泄漏地图，显示不足会让玩家在已探索区内误判方向**',
    '🔴 **必须按距离 · 可见区域 · 任务阶段 · 玩家知识分别记录，'
    '不能写成单一布尔**',
]

# 多目标
MULTIO_FIELDS = [
    'priority', '**stickiness**', '**player_pinned**', 'objective_id',
    'dependency_order', '**stable_sort_key**', 'switch_notification_kind',
]

MULTIO_RULE = [
    '🔑 **多目标需要稳定排序，而不是只设优先级字段**',
    '🔑 `stable_sort_key` 必须在 priority 相同时**保证重绘不跳动**',
    '🔑 "手动追踪"还分**临时选择 · 永久置顶 · 仅本会话 · 跨会话记忆**',
    '🔑 原版若允许自由切换，仍要测**玩家切换后是否影响路径重算**',
]

# 🔑 路径
NAV_FIELDS = [
    'replan_policy', 'throttle', 'asynchronous_result_policy',
    '**stale_path_visual**', 'smoothing', 'portal_snap',
    'vertical_tolerance', 'last_result_age',
]

NAV_TRIGGERS = [
    '首次计算', '玩家偏离阈值', '目标移动', '链路变化', '动态障碍',
    '区域 cost 变化', '长帧', '加载', '暂停',
]

NAV_RULE = [
    '🔑 **导航路径是连续轮询查询，不是一次 A* 结果**',
    '🔑 Recast/Detour 将**生成与运行时查询分层**，适合作为'
    '"如何保持 NavMesh 与路径查询一致"的参照 —— '
    '🔴 **但算法本身不能证明原版重算频率**',
    '🔴 **最危险的简化**：异步拿到新路径后**瞬间折角**，'
    '玩家看到路径"**跳变**" —— 原版可能**使用旧路径一段 · 淡入新路径 · '
    '或只在新路径明显更优时切换**',
]

# 成长曲线
CURVE_FIELDS = [
    'level', '**cumulative_xp**', 'delta_xp', 'xp_source',
    'source_multiplier', 'bonus_cap', 'overflow_policy', 'auto_level',
    'pending_level_up',
]

CURVE_RULE = [
    '🔑 **经验曲线应按相邻区间测量，而不是只问"是否指数"**',
    '🔑 曲线可能有**软上限 · 硬上限 · 活动加成 · 组队加成 · 任务加成 · '
    '死亡惩罚 · 声望或难度修正**',
    '🔑 原始游戏常用"**经验需求表**"，重制若改成闭式公式，'
    '🔴 **即使端点近似相同，中间等级也可能累积漂移** —— '
    '必须**逐级记录累计值与舍入方式**',
]

# 🔑 卡关
STUCK_POINTS = [
    '低等级期', '首个硬战斗', '资源瓶颈', '关键技能缺失', '导航迷路',
    'Boss 检查点', '满级前后',
]

STUCK_FORMS = [
    '隐藏经验加成', '临时任务', '商人库存', '敌人削弱', '掉落保底', '恢复',
    '快速旅行', '同伴接管', '剧情提示',
]

STUCK_RULE = [
    '🔑 **卡关补偿通常是隐式设计，重制最容易无意识删除**',
    '🔑 它**不一定是"动态难度"** —— '
    '🔴 **把原版的静态补偿误判为动态系统，会在复刻中加错机制**',
    '🔑 若原版确实按玩家表现调整敌人 → 要记**采样窗口 · 阈值 · 滞后 · '
    '持续时间 · 局内/局外作用域 · 读档是否重置**',
]

# 洗点
RESPEC_FIELDS = [
    '**reset_scope**（单技能 · 单树 · 全职业 · 外观）', 'cost_kind',
    'cost_amount', 'currency_or_resource', 'attempt_limits', 'permission',
    'refund_rounding', '**dependent_buff_flush**', 'cooldown_restart',
    '**equipment_invalid_policy**', '**visual_preset_persistence**',
]

RESPEC_RULE = [
    '🔑 **洗点不能只记录返还点数，还要记录状态残留**',
    '🔑 若洗点清除**外观 · 保存位 · 称号 · 任务标记**，'
    '原版与重制会出现"**能力一样但沉没成本不同**"',
    '🔑 `visual_preset_persistence` 特别值得测：'
    '玩家选择的外观属于**角色 · 当前构筑 · 还是共享预设**',
]

# 🔴 满级
MAXLV_ITEMS = [
    '达到最大等级时**剩余经验去向**',
    '**溢出是否进入声望 · 货币 · 外观货币 · 下阶段 · 还是丢弃**',
    '**经验来源是否在满级后关闭**', '属性点是否继续获得',
    '敌人是否随之停止增长', '**能否降级**',
    '**满级后任务与统计是否改变**',
]

MAXLV_RULE = '🔴 **若只把"最大等级"写成上限，重制会漏掉经验溢出 · '
'二次货币 · 满级内容**，造成长期玩家感知"**变穷**"或"**变快**"'

# 世界跟随
FOLLOW_FOUR = [
    '**敌人血量/伤害**', '**敌人组合**', '**掉落与奖励**',
    '**任务与区域可用性**',
]

FOLLOW_RULE = [
    '🔑 **"世界跟随玩家"至少有四层，不能笼统称为动态难度**',
    '🔑 每层还要记**作用范围 · 玩家等级采样 · 装备修正 · 同伴修正 · '
    '是否回退 · 分屏中按谁采样**',
    '🔑 理想验收**不是数值差小于阈值**，而是'
    '**同一段录像 · 相同输入在固定等级下得到相同结果**，'
    '并在等级边界附近测**单调性 · 滞后 · 跳变**',
]

# 🔑 回放三种模型
REPLAY_THREE = [
    ('**输入录制**', '体积最小但**要求确定性模拟**', '重制换模拟后结果不同'),
    ('**周期状态快照**', '容忍少量非确定性，体积大，'
     '**插值可能改变碰撞**', '受浮点/组件顺序/并发排序影响'),
    ('**帧画面录制**', '最接近原版观感', '**无法自由切视角，'
     '且不能作为逻辑验证证据**'),
]

REPLAY_FIELDS = [
    'recording_semantics', 'seed_chain', 'determinism_scope',
    'engine_version', 'content_version', 'mod_manifest', 'frame_or_tick',
    'input_phase', 'rng_state_hash', 'entity_snapshot_interval',
    'non_reproducible_sources[]',
]

REPLAY_RULE = [
    '🔑 **回放保真度取决于录制层，而不是播放器功能多少**',
    '🔑 把每类事件标成 `original_only · recomputed · '
    'authoritative_snapshot · undefined`',
    '🔴 **禁止未声明时声称"完全忠实"**',
    '🔑 **回放看到重制行为并不一定是 bug，但必须显式声明**',
    '🔑 这与"**序列化存在 ≠ 世界一致性快照存在**"直接相连',
]

# 导出
EXPORT_FIELDS = [
    'container', 'codec', 'resolution', 'frame_rate', 'hdr_transfer',
    'color_primaries', 'audio_tracks[]', '**hud_policy**',
    '**watermark_policy**', 'safe_area', '**privacy_blur**',
    'metadata_license', 'platform_specific_max', 'file_rotation',
]

EXPORT_RULE = [
    '🔑 **录像导出应把 HUD · 分轨 · 隐私当作语义，不只是编码**',
    '🔑 OBS Studio 一手文档确认其包括 sources · scenes · outputs · '
    'encoders · services · 音频处理器与重采样器，并提供插件和脚本 API；'
    '许可证 **GPLv2 或更高版本**',
    '🔴 **但它不保存游戏世界状态，也不能解决'
    '"回放为什么和重制行为不同"**',
    '🔑 **60 与 59.94 · HDR/SDR · 全屏 HUD · 麦克风分轨'
    '应列为独立验收项**',
]

EXPORT_EDIT = '🔑 **剪辑会改变"同一帧"的语义** —— 要记剪切点所属 tick · '
'音频偏移 · 慢动作实现 · 时间轴标记 · 相机切换 · 自由相机轨迹 · '
'字幕 · 原始素材哈希。**慢动作若重采样音频而画面只是时间缩放，'
'会产生音高和口型偏差；若重新播放声音事件，又会改变一次触发多次**'

# F / G
FG = [
    ('**F 彩蛋发现条件**', '触发条件的**精确性**（时间窗口 · 位置精度 · '
     '操作序列 · 前置条件） · **发现的可重复性**（一次性？可重复？'
     '读档后是否重置） · 与成就/统计的耦合 · '
     '**"不可能被发现"的内容**（原版是否有实际无法触发的内容）'),
    ('**G 音乐编排**', '**段落结构**（intro/verse/chorus · 循环点 · '
     '是否无缝） · **节拍与玩法耦合**（敌人出现是否在拍点上 · '
     '战斗强度与音乐层次） · **静默的设计**（何时完全无声 · 持续多久） · '
     '**优先级仲裁**（多个重要音同时：谁被听到 · 谁被压低）'),
]

CONFLICTS = [
    '❌ 只记录"能否放置"（合并五种否决）',
    '❌ **"高亮但无法放置"只记为灰色**',
    '❌ **擅自统一撤销单元**',
    '❌ 交易预览只显示单价',
    '❌ 锁定后价格仍变（旧价锁定、新价扣除）',
    '❌ **统一"自动选择最优货币"**',
    '❌ 把"目标箭头"当单一 UI 组件',
    '❌ **未探索区是否显示目标写成单一布尔**',
    '❌ 多目标只设 priority 无 stable_sort_key',
    '❌ **异步新路径瞬间折角**',
    '❌ 用闭式公式替代经验需求表（中间等级漂移）',
    '❌ **把静态补偿误判为动态难度**',
    '❌ 洗点只记返还点数',
    '❌ **只把"最大等级"写成上限**',
    '❌ 笼统称"动态难度"',
    '❌ **未声明录制语义却声称"完全忠实"**',
    '❌ 慢动作重采样音频却不处理音高/口型',
]

FIELDS = [
    ('item_id', '项编号'),
    ('domain', '域（place / deny / undo / trade / lock / batch / buyback / '
               'money / obj / seethru / multio / navpath / curve / stuck / '
               'respec / maxlv / follow / replay / export / fg）'),
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


def cmd_six(a):
    _hdr('🔑 交互事务（**六类副作用**）')
    print('副作用: ' + ' · '.join(SIX_SIDE))
    print('\n每类操作必记字段:')
    for f in TXN_FIELDS:
        print(f'   · {f}')
    print(f'\n   {TXN_RULE}')
    return 0


def cmd_place(a):
    _hdr('🔴 建造（**吸附只是提示，合法性才是门槛**）')
    for k, why in PLACE_TWO:
        print(f'   {k:<26} {why}')
    print('\n记录: ' + ' · '.join(PLACE_FIELDS))
    print('\n规则:')
    for r in PLACE_RULE:
        print(f'   {r}')
    return 0


def cmd_deny(a):
    _hdr('🔴 放置（**五种否决**）')
    for k, why in DENY_FIVE:
        print(f'   {k:<16} {why}')
    print(f'\n   {DENY_RULE}')
    return 0


def cmd_undo(a):
    _hdr('撤销（**按副作用事务分组**）')
    print('字段: ' + ' · '.join(UNDO_FIELDS))
    print('\n规则:')
    for r in UNDO_RULE:
        print(f'   {r}')
    return 0


def cmd_trade(a):
    _hdr('🔑 交易（**预览是可审计净变化**）')
    print('字段: ' + ' · '.join(TRADE_PREVIEW))
    print('\n规则:')
    for r in TRADE_RULE:
        print(f'   {r}')
    return 0


def cmd_lock(a):
    _hdr('🔴 锁定（**确认与锁定是两个状态**）')
    print('   ' + ' → '.join(LOCK_STATES))
    print('\n规则:')
    for r in LOCK_RULE:
        print(f'   {r}')
    return 0


def cmd_batch(a):
    _hdr('🔑 批量结算（**舍入问题**）')
    for b in BATCH_ITEMS:
        print(f'   · {b}')
    print('\n规则:')
    for r in BATCH_RULE:
        print(f'   {r}')
    return 0


def cmd_buyback(a):
    _hdr('买回与偷窃（**不可变事实字段**）')
    print('buyback: ' + ' · '.join(BUYBACK_FIELDS))
    print('\n偷窃记录: ' + ' · '.join(STEAL_ITEMS))
    print(f'\n   {STEAL_RULE}')
    return 0


def cmd_money(a):
    _hdr('多货币（**零钱不是展示层**）')
    print('字段: ' + ' · '.join(MONEY_FIELDS))
    print('\n规则:')
    for r in MONEY_RULE:
        print(f'   {r}')
    return 0


def cmd_obj(a):
    _hdr('🔑 目标（**三个独立视图**）')
    for k, why in OBJ_VIEWS:
        print(f'   {k:<42} {why}')
    print('\n字段: ' + ' · '.join(OBJ_FIELDS))
    print('\n规则:')
    for r in OBJ_RULE:
        print(f'   {r}')
    return 0


def cmd_seethru(a):
    _hdr('🔴 可见性（**"是否穿墙"四种模式**）')
    for s in SEETHRU_FOUR:
        print(f'   {s}')
    print('\n规则:')
    for r in SEETHRU_RULE:
        print(f'   {r}')
    return 0


def cmd_multio(a):
    _hdr('多目标（**稳定排序**）')
    print('字段: ' + ' · '.join(MULTIO_FIELDS))
    print('\n规则:')
    for r in MULTIO_RULE:
        print(f'   {r}')
    return 0


def cmd_navpath(a):
    _hdr('🔑 路径（**连续轮询查询**）')
    print('重算触发: ' + ' · '.join(NAV_TRIGGERS))
    print('\n字段: ' + ' · '.join(NAV_FIELDS))
    print('\n规则:')
    for r in NAV_RULE:
        print(f'   {r}')
    return 0


def cmd_curve(a):
    _hdr('成长（**按相邻区间测量**）')
    print('字段: ' + ' · '.join(CURVE_FIELDS))
    print('\n规则:')
    for r in CURVE_RULE:
        print(f'   {r}')
    return 0


def cmd_stuck(a):
    _hdr('🔑 卡关（**补偿是隐式设计**）')
    print('需测节点: ' + ' · '.join(STUCK_POINTS))
    print('\n补偿可能形式: ' + ' · '.join(STUCK_FORMS))
    print('\n规则:')
    for r in STUCK_RULE:
        print(f'   {r}')
    return 0


def cmd_respec(a):
    _hdr('洗点（**状态残留**）')
    print('字段: ' + ' · '.join(RESPEC_FIELDS))
    print('\n规则:')
    for r in RESPEC_RULE:
        print(f'   {r}')
    return 0


def cmd_maxlv(a):
    _hdr('🔴 满级（**必须单独建模**）')
    for m in MAXLV_ITEMS:
        print(f'   · {m}')
    print(f'\n   {MAXLV_RULE}')
    return 0


def cmd_follow(a):
    _hdr('世界跟随（**四层**）')
    for f in FOLLOW_FOUR:
        print(f'   · {f}')
    print('\n规则:')
    for r in FOLLOW_RULE:
        print(f'   {r}')
    return 0


def cmd_replay(a):
    _hdr('🔑 回放（**事实 vs 像素**）')
    print(f'   {"模型":<18}{"特点":<38}风险')
    print('   ' + '-' * 74)
    for k, f, r in REPLAY_THREE:
        print(f'   {k:<18}{f:<38}{r}')
    print('\n字段: ' + ' · '.join(REPLAY_FIELDS))
    print('\n规则:')
    for r in REPLAY_RULE:
        print(f'   {r}')
    return 0


def cmd_export(a):
    _hdr('导出（**HUD/分轨/隐私是语义**）')
    print('字段: ' + ' · '.join(EXPORT_FIELDS))
    print('\n规则:')
    for r in EXPORT_RULE:
        print(f'   {r}')
    print(f'\n   {EXPORT_EDIT}')
    return 0


def cmd_fg(a):
    _hdr('F / G 补充')
    for k, why in FG:
        print(f'\n   【{k}】\n      {why}')
    return 0


def cmd_init(a):
    os.makedirs(os.path.dirname(a.init) or '.', exist_ok=True)
    with open(a.init, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow([k for k, _ in FIELDS])
        w.writerow(['TODO'] * len(FIELDS))
    print(f'已生成交互事务表: {a.init}')
    print('\n⚠️ 二十域：place / deny / undo / trade / lock / batch / buyback / '
          'money / obj / seethru / multio / navpath / curve / stuck / respec / '
          'maxlv / follow / replay / export / fg')
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
    print(f'交互事务 · {len(rows)} 条')
    print('=' * 76)
    if mismatch:
        print(f'\n🚫 **不一致** {len(mismatch)} 条（行 {mismatch[:15]}）')
    if no_legacy:
        print(f'\n❌ {len(no_legacy)} 条缺**原版值**（行 {no_legacy[:15]}）')
    if no_grade:
        print(f'\n🚫 {len(no_grade)} 条**证据等级缺失或 ≥7 级**'
              f'（行 {no_grade[:15]}）')

    if not (mismatch or no_legacy or no_grade):
        print('\n✅ 交互事务：一致、原版值完整、证据等级达标')

    print('\n🔑 **工具解决"怎样实现"，原版测量解决"实现成什么"。**')
    print('   **吸附只是提示，合法性才是门槛；不同否决不能合并成"无效位置"。**')
    print('   **回放保真度取决于录制层；未声明语义不得声称"完全忠实"。**')
    return 1 if (a.gate_check and (mismatch or no_legacy or no_grade)) else 0


def main():
    ap = argparse.ArgumentParser(description='交互事务契约')
    ap.add_argument('--six', action='store_true')
    ap.add_argument('--place', action='store_true')
    ap.add_argument('--deny', action='store_true')
    ap.add_argument('--undo', action='store_true')
    ap.add_argument('--trade', action='store_true')
    ap.add_argument('--lock', action='store_true')
    ap.add_argument('--batch', action='store_true')
    ap.add_argument('--buyback', action='store_true')
    ap.add_argument('--money', action='store_true')
    ap.add_argument('--obj', action='store_true')
    ap.add_argument('--seethru', action='store_true')
    ap.add_argument('--multio', action='store_true')
    ap.add_argument('--navpath', action='store_true')
    ap.add_argument('--curve', action='store_true')
    ap.add_argument('--stuck', action='store_true')
    ap.add_argument('--respec', action='store_true')
    ap.add_argument('--maxlv', action='store_true')
    ap.add_argument('--follow', action='store_true')
    ap.add_argument('--replay', action='store_true')
    ap.add_argument('--export', action='store_true')
    ap.add_argument('--fg', action='store_true')
    ap.add_argument('--init')
    ap.add_argument('--check')
    ap.add_argument('--gate-check', action='store_true')
    a = ap.parse_args()
    fns = {'six': cmd_six, 'place': cmd_place, 'deny': cmd_deny,
           'undo': cmd_undo, 'trade': cmd_trade, 'lock': cmd_lock,
           'batch': cmd_batch, 'buyback': cmd_buyback, 'money': cmd_money,
           'obj': cmd_obj, 'seethru': cmd_seethru, 'multio': cmd_multio,
           'navpath': cmd_navpath, 'curve': cmd_curve, 'stuck': cmd_stuck,
           'respec': cmd_respec, 'maxlv': cmd_maxlv, 'follow': cmd_follow,
           'replay': cmd_replay, 'export': cmd_export, 'fg': cmd_fg}
    for k, fn in fns.items():
        if getattr(a, k):
            return fn(a)
    if a.init:
        return cmd_init(a)
    if a.check:
        return cmd_check(a)
    print('❌ 需要 --six / --place / --deny / --undo / --trade / --lock / '
          '--batch / --buyback / --money / --obj / --seethru / --multio / '
          '--navpath / --curve / --stuck / --respec / --maxlv / --follow / '
          '--replay / --export / --fg / --init / --check 之一')
    return 2


if __name__ == '__main__':
    sys.exit(main())
