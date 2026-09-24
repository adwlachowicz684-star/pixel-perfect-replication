#!/usr/bin/env python3
"""生活玩法 · 首次启动 · 人格化痕迹 · 叙事玩法接口
（第三十八轮 A / B / C / D 类，含 E / F / G 补充）。

**🔑 本轮的视角切换**：
> 前三十七轮已覆盖大量"能直接拿出帧数与参数"的系统和元层，
> 却仍把游戏当作一个**功能集合**。
> 🔑 而玩家感受到的是**连续体验**。

**🔑 盲区的共同结构：玩家记忆的是链路，不是菜单项。**
每条链路都要写成"**输入 → 状态转换 → 反馈 → 副作用 → 可逆性**"。

**🔑 验收单位升级**：从"**功能存在**"改为"**状态轨迹逐字段相等**"。
偏差等级不能由"看起来差不多"决定，要区分：
- 帧数/时间不等**但结果等价**
- 结果不等**但不在 must-match 范围**
- **状态 · 判定 · 反馈不等** → 默认 must-match

用法:
  game_lifeplay_trace.py --fish    # 🔑 钓鱼的**最小复刻单元是拉力—时间曲线**
  game_lifeplay_trace.py --gather  # 采集 · 烹饪 · 小游戏
  game_lifeplay_trace.py --mount   # 🔑 **上下马是一次控制权交接**
  game_lifeplay_trace.py --pet     # 宠物是**关系反馈层**
  game_lifeplay_trace.py --home    # 家园的**居住感＝空闲行为与因果循环**
  game_lifeplay_trace.py --fsm     # 🔑 **首次启动是不可重来的状态轨迹**
  game_lifeplay_trace.py --teach   # **失败教学三个时序**
  game_lifeplay_trace.py --unk     # 🔴 **"不知道自己不知道"**
  game_lifeplay_trace.py --adv     # 进阶技巧**延迟兑现**
  game_lifeplay_trace.py --trace   # 🔑 **人格化痕迹五类**
  game_lifeplay_trace.py --setmig  # **设置迁移要比较语义不只是键名**
  game_lifeplay_trace.py --keep    # 涂鸦/照片/录像**最易在"现代化"中失证**
  game_lifeplay_trace.py --matrix  # 🔑 **过场＝控制权矩阵**
  game_lifeplay_trace.py --choice  # **选择分即时表现与因果结果**
  game_lifeplay_trace.py --skip    # 🔴 **"不可跳过"必须被证明**
  game_lifeplay_trace.py --offline # 🔑 单机/联机是**功能降级图**不是开关
  game_lifeplay_trace.py --econ    # 🔑 **经济按流量验证，不是价格表**
  game_lifeplay_trace.py --scarc   # **稀缺性是反舒适但必须保留的设计**
  game_lifeplay_trace.py --g       # G 类三项新盲层
  game_lifeplay_trace.py --init ledger/lifeplay_trace.csv
  game_lifeplay_trace.py --check ledger/lifeplay_trace.csv --gate

退出码: 0 通过 / 1 缺项 / 2 用法错误
"""
import argparse
import csv
import os
import sys

# 🔑 钓鱼
FISH_ITEMS = [
    ('咬钩概率 / 延迟', '随机分布必须可重复'),
    ('**拉力目标区间**', '🔑 不是"难度档"'),
    ('玩家输入响应', '输入采样率'),
    ('线张力 / 耐久', '断线阈值'),
    ('线长 / 卷线速度', '单位与方向'),
    ('**挣扎节拍**', '与音高映射'),
    ('进度条方向', '是否反向'),
    ('鱼跃镜头 / 收网动画', '镜头抖动'),
    ('掉落归属', '谁捡到'),
]

FISH_RULE = [
    '🔑 **钓鱼的最小复刻单元应是"拉力—时间曲线"，而非"难度档"**',
    '🔑 用**固定输入脚本回放**，比较**相同随机种子下进度条是否同轨**',
    '🔴 若只能达到视觉近似，应标为"**等效变体**"，'
    '🔴 **仍不得在未显式批准时提交**',
]

FISH_CONFLICT = [
    '❌ 加入**辅助线**', '❌ **自动收线**', '❌ **取消断线**',
    '❌ **降低挣扎频率**', '❌ 用更平滑的曲线提高"手感"',
]

FISH_WHY = '🔴 这些都让游戏更容易，却**改变技能门槛和资源获取**'

# 采集/烹饪/小游戏
GATHER_FOUR = [
    ('**采集/采矿**', '判定半径 · 角度 · 持续时间 · 工具等级 · 碎裂阶段 · '
     '资源表 · 背包检查 · 打断恢复',
     '🔴 **采集距离变长 → 可到达资源变多 → 破坏稀缺区域设计**'),
    ('**烹饪/制作**', '配方容器 · 材料顺序 · 火候时间 · 焦糊/失败产物 · '
     '批量规则 · 属性叠加 · UI 预览',
     '🔴 **把随机配方改确定配方，或把"误操作损失"取消**'),
    ('**小游戏/赌博**', '伪随机序列 · 赔率 · 庄家规则 · 押注上下限 · '
     '冷却 · 奖励税 · 动画时长',
     '🔴 **高频重摇 · 显示概率与实际概率不同 · '
     '收益超过原版防刷边界**'),
]

GATHER_RULE = '🔑 **生活玩法最危险的复刻方式是"保留名字、重做手感"** ——'
' 玩家往往通过这些活动获得**节奏喘息 · 区域知识 · 稀有资源入口 · 角色成长**'

# 🔑 坐骑
MOUNT_ITEMS = [
    '座位偏移 · 根骨 · **碰撞层** · 质量 · 重心 · 倒地阈值',
    '**加速曲线** · 制动滑行 · 转向响应 · **不同地面摩擦** · 颠簸',
    '**镜头距离/FOV/碰撞** · 第一/三人称切换 · 音效',
    '**NPC 避让** · 能否战斗 · 能否开门 · 能否使用道具 · 能否在载具中拾取',
]

MOUNT_SWAP = [
    '**动画锁定帧**', '根骨匹配', '**旧控制器停用时机**',
    '**新碰撞启用时机**', '相机切层', '音频源移动', '输入队列',
    '**未结算命中**', '着地检查', '障碍物挤压与回退点',
]

MOUNT_RULE = '🔑 **"上下马"不是一个动画，而是一次控制权交接**'

MOUNT_CASES = [
    '斜坡 · 低矮顶棚 · 门框 · 水面',
    '**战斗中被打断** · 死亡 · 保存/读档 · 快速旅行 · 退出时点',
]

MOUNT_WARN = [
    '🔴 **若上马动画完成 1 帧后才解除旧碰撞 → 可能挤墙**',
    '🔴 **若先解除碰撞后播相机 → 可能短暂看到穿透**',
    '🔴 **若输入在动画中途恢复 → 玩家能偷跑**',
]

# 宠物
PET_ITEMS = [
    '亲密度来源与**衰减**', '跟随距离', '视线遮挡', '避障',
    '**路径失败**', '等待', '疲惫', '好感表情', '战斗位置',
    '**复活/离队**', '**死亡反应**', '继承与替代',
]

PET_THREE = '🔑 亲密度要拆成"**隐藏值 — 可观察行为 — UI 明示**"三层：'
'**数值可以复刻，但表现必须按原版触发** —— '
'🔴 **不能因为新动画更可爱就提高反馈频率**'

# 家园
HOME_ITEMS = [
    'NPC 日程', '**使用家具动画**', '对话变化', '灯光与天气响应',
    '宠物/孩子位置', '**家具互动音**', '相簿/信箱/收藏',
    '**长期无人访问后的变化**',
]

HOME_GRAPH = '🔑 建立"**住宅因果图**"：玩家放置 X → NPC 是否使用 → '
'是否触发 Y 对话 → 是否改变 Z 状态。'
'🔴 **没有这张图，家园很容易只剩摆放与拍照**'

# 🔑 首次启动状态机
FSM_STATES = [
    '启动视频/Logo', '语言选择', '平台协议', '显示与色盲', '字幕',
    '难度/辅助', '键位模板', '**首个输入发现**', '**首个失败**',
    '**首个成功**', '首个分支', '首个自由探索', '教程结束',
    '**进阶提示可用**',
]

FSM_FIELDS = [
    '进入条件', '退出条件', '**跳过条件**', '中断恢复', '**重复次数**',
    '**时间限制**', '音频/字幕', '镜头', '**输入锁定**',
]

FSM_RULE = '🔑 **教学改动不可逆地改变首通体验** —— '
'原版首次启动不是一串提示，而是**设置向导 · 输入发现 · 核心幻想 · '
'首胜 · 失败恢复 · 进阶暗示**的节奏编排'

# 失败教学三时序
TEACH_THREE = [
    ('**识别**', '系统如何**发现玩家卡住**'),
    ('**解释**', '何时显示**为何失败**'),
    ('**补救**', '是否给重试 · 提示 · 降低难度 · 改变目标'),
]

TEACH_FIELDS = [
    '检测信号', '**等待时长**', '**重复失败阈值**', '提示版本',
    '是否暂停计时', '是否记录已见', '跨场景保留', '**读档后是否重放**',
    '**是否影响成就/统计**',
]

TEACH_RULE = '🔴 **若原版在第三次失败后提示，复刻在第一次失败时提示** —— '
'**即使文本相同，也改变了挫败曲线**'

# 🔴 不知道自己不知道
UNK_ITEMS = [
    '机制如何被**环境展示**', 'NPC 台词', '物品描述', 'UI 图标',
    '**可试错空间**', '**可回退成本**', '**进阶入口**',
]

UNK_CONFLICT = [
    '❌ 一开始塞满**百科**',
    '❌ 用**高亮标出所有可互动物**',
    '❌ 允许随时查看**完美攻略**',
    '❌ 把**隐藏机制显性化**',
]

UNK_RULE = '🔑 它们提高新手完成率，却破坏原版"**偶然发现 — 验证 — 掌握**"的节奏。'
'🔑 **若必须加入新辅助，应作为默认关闭的附加层，且不在原版流程中自动触发**'

# 进阶
ADV_TABLE = [
    '技巧名称', '前置知识', '触发场景', '**可见线索**', '成功窗口',
    '**失败代价**', '**可发现时间**', '**跨版本是否仍可学会**',
]

ADV_RULE = '🔑 **进阶技巧的教学必须保留"延迟兑现"** —— '
'检查原版是否通过后续 NPC · 环境排布 · 失败代价 · 可选挑战 · 难度墙 · '
'重复场景促使玩家**返回旧机制**。'
'🔴 **重制若把跳跃谜题改为无障碍直达，或把帧数据训练关提前，'
'就改变了技巧的社会传播与成就感**'

ADV_GRADES = [
    ('**must-match**', '原版存在，必须逐字段复刻'),
    ('**compatibility-only**', '仅解决原版没有的新输入/显示问题'),
    ('**optional**', '默认关闭'),
    ('**reject**', '会改变学习节奏'),
]

ADV_PRINCIPLE = '🔑 原则：**先记录原版"没有教学"本身，再决定是否补**'

# 🔑 痕迹五类
TRACE_FIVE = [
    ('**机械可迁移**', '键位 · 图形设置', '精确映射'),
    ('**语义可迁移**', '画质档位 · 输入动作', '等价映射'),
    ('**平台专属**', '手柄键位 · 触控 · 陀螺仪', '转码或保留但禁用'),
    ('**表达性资产**', '照片 · 录像 · 涂鸦 · 角色 · 家具', '保留只读原始副本'),
    ('**元历史**', '首通日期 · 死亡/失败 · 统计 · 收藏', '必须保留并映射'),
]

TRACE_RULE = '🔑 **玩家作品与设置应被视为存档的延伸，而非可丢弃配置**'

TRACE_LOSS = [
    ('键位/控制', '动作映射 · 设备 · 死区 · 反转 · 扳机分段 · 陀螺仪 · 涡轮 · 宏',
     '🔴 **新输入系统重排动作 · 平台模板覆盖**'),
    ('UI/相机', '布局 · 缩放 · 色盲 · 字幕 · FOV · 灵敏度 · 滤镜预设',
     '🔴 **分辨率变化后锚点错位 · 宽屏裁剪**'),
    ('照片/录像', '原始帧 · 相机参数 · 元数据 · 可播放编码',
     '🔴 **重编码 · 宽高比变化 · HDR/色调映射失效**'),
    ('涂鸦/建造', '笔刷 · 图层 · 材质 · 物理对象 · 世界坐标',
     '🔴 **碰撞或寻路改变后漂浮/穿模/不可达**'),
    ('收藏/历史', '缩略图 · 时间 · 版本 · 校验 · 隐藏内容标记',
     '🔴 **只迁移进度，不迁移纪念性记录**'),
]

# 设置迁移语义
SETMIG_RULE = '🔑 **设置迁移不能只比较键名，要比较语义** —— '
'🔴 **原版"高画质"并不必然对应新引擎的"高画质"**；'
'要记该档实际影响的**阴影距离 · 材质 · 后期 · 分辨率缩放**'

SETMIG_KEY = '🔑 键位要区分**物理按键 · 输入动作 · 上下文动作** —— '
'一个动作可在多种设备间迁移，但**组合键 · 长按 · 双击 · 取消窗口**可能不同'

# 保留
KEEP_FIELDS = [
    '源资产', '容器', '编码', '帧率', '**色彩空间**', '**相机变换**',
    '时间戳', '签名/校验', '**可见 HUD 层**', '版本号',
]

KEEP_RULE = [
    '🔑 **涂鸦 · 照片 · 录像最容易在"格式现代化"中失证**',
    '🔑 迁移**至少保留一份只读原始副本**；若必须转码，另存结果并保留原文件',
    '🔴 **对于旧版录像，要明确兼容窗口和失效条件，'
    '不能静默宣称"旧录像可用"**',
]

KEEP_HISTORY = '🔑 **纪念性与统计是玩家历史的一部分** —— '
'即使重制不展示这些字段，也要在新存档中**保留并映射**，'
'🔴 **避免首次启动把老玩家重置成新玩家**'

# 🔑 控制权矩阵
MATRIX_STATES = [
    'gameplay', 'scripted_gameplay', 'cinematic_skippable',
    'cinematic_unskippable', 'qte', 'dialogue_paused',
    'dialogue_real_time', 'loading',
]

MATRIX_PER_FRAME = [
    '**输入所有者**', '**相机所有者**', '动画图', '**物理启用**',
    '**碰撞层**', '**伤害**', 'HUD', '音频', '**时间缩放**',
    '**保存点**', '**可跳过性**', '**选择结果**',
]

MATRIX_RULE = '🔑 **叙事与玩法接口必须写成控制权矩阵**'

MATRIX_QTE = '🔑 QTE 不只记按钮与窗口，还要记**失败分支 · 重复次数 · '
'跳过状态 · 读档点 · 镜头是否短暂归还玩家**'

MATRIX_FUZZY = [
    '对话中能否**移动 · 攻击 · 打开地图 · 快速旅行**',
    '战斗中能否**对话**',
    '过场中能否**使用道具**',
    '**暂停是否冻结脚本**',
    '**选择是否冻结世界**',
]

MATRIX_WARN = '🔴 **若玩家在对话 A 中可转身，而在对话 B 中不能，'
'不能抽象成统一规则，必须保留例外**'

# 选择
CHOICE_INSTANT = [
    '台词变化', '表情', '镜头', '音效', '关系值', 'UI 标记',
]

CHOICE_CAUSAL = [
    '后续对话', '任务状态', '**世界状态**', '**可到达区域**', '**结局**',
]

CHOICE_EDGES = [
    '**instant_reaction**', '**end_of_node**', '**end_of_scene**',
    '**end_of_mission**', '**post_load**', '**permanent**',
]

CHOICE_RULE = '🔑 **选择反馈必须区分即时表现（表现层）与因果结果（世界层）**，'
'建立"**选择因果图**"，每条边标注**延迟层级**'

# 跳过
SKIP_ITEMS = [
    '跳过按钮**出现时间**',
    '**完整与跳过两条轨迹**',
    '跳转目标',
    '**遗漏资产 · 未播音频 · 未触发事件**',
    '**选择默认值**',
    '**保存状态**',
    '**回归玩法**',
]

SKIP_TEST = [
    '首次/重复观看', '设置中的**自动跳过**', '回退对话', '暂停菜单',
    '读档', '离线', '不同平台', '**无障碍快捷跳过**', '崩溃恢复',
]

SKIP_RULE = '🔴 **"不可跳过"本身必须被证明，而非引用文本**'
SKIP_CASES = [
    '🔴 **若原版在第二次观看时才允许跳过，而重制默认允许 → '
    '玩家可避开必须承受的演出停顿**',
    '🔴 **若原版允许快进到选项而重制只能整段跳过 → 丢失即时反馈**',
]

# 🔑 离线
OFFLINE_MATRIX = [
    '启动授权', '本地保存', '**云保存**', '**好友列表**', '**排行榜**',
    '商店', '活动', '跨平台进度', '**多人会话**', '反作弊',
    'DLC 验证', '遥测', '补丁与平台服务',
]

OFFLINE_FIELDS = [
    '原版在线/离线行为', '失败错误', 'UI 提示', '重试', '超时',
    '**本地缓存**', '**写队列**', '**恢复顺序**',
]

OFFLINE_TEST = [
    '**断网瞬间**', '**DNS 失败**', '连接重置', '认证 401/403',
    '服务器 503', '证书变化', '时钟偏移', '**只读存档**', '磁盘满',
]

OFFLINE_RESIDUE = [
    '好友状态轮询', '云存档冲突弹窗', '排行榜上传', '活动令牌',
    '遥测', '崩溃上传', '新闻轮播', 'DLC 检查', '**反作弊心跳**',
]

OFFLINE_RULE = '🔑 **离线模式不能只问"能不能进"，要问哪些状态退化** —— '
'建立矩阵，每项记原版在线/离线行为'
OFFLINE_CONFLICT = '🔴 **重制若把这些功能默认常驻 → 提高启动失败率；'
'若全部移除 → 破坏原版成就 · 好友挑战 · 在线排行榜**'

# 经济
ECON_FOUR = [
    ('**产出表**', '来源 · 频率 · 上限 · 条件'),
    ('**消耗表**', '消耗 · 维修 · 死亡损失 · 转换'),
    ('**稀缺表**', '不可再生资源 · 时段资源 · 任务唯一资源'),
    ('**外部性表**', '交易 · 赠予 · 商店刷新 · 刷怪 · 时间加速'),
]

ECON_SCENARIOS = [
    '纯主线', '全收集', '**刷钱循环**', '长期挂机', '跨版本迁移',
]

ECON_RULE = '🔑 **经济重制不能只核对商店价格，要复现长期闭环**'

SCARCITY_ITEMS = [
    '唯一道具', '稀有材料', '日限', '周限', '商店库存', '随机池',
    '商店刷新', '任务资源', '**不可逆消费**', '死亡掉落',
]

SCARCITY_RULE = '🔑 **稀缺性是反舒适但必须保留的设计** —— '
'🔴 **重制若"修复"稀缺性，可能让后期失去约束；'
'若只提高掉率而不改价格，也可能造成通货膨胀**'

FARM_INVARIANTS = [
    '最大携带', '单价', '堆叠', '交易冷却', '商店补货', '掉落上限',
    '**保存/读档是否复制**', '交易回滚', '离线时间上限', '服务器时钟',
    '修改检测与异常惩罚',
]

FARM_RULE = '🔑 **刷钱边界要写成可执行不变量**：每项提供'
'**最小复现脚本和预期结果**'

ECON_WARN = '🔴 **若原版前 10 小时紧 · 中期开放 · 后期通胀，'
'重制不应平均化。任何单点改动都跑完整流量，'
'避免"每样只改一点"后累积成完全不同的经济**'

# G 三项
G_THREE = [
    ('**录像的"视觉可重演"≠ 逻辑确定性**',
     '缺"**像素级视觉 diff**"规范：固定种子 · 时间源 · 平台与驱动 · '
     '资产版本 · 相机 · 后处理 · 帧步 · **禁止异步加载突变**，'
     '对 RGB 逐帧做**容差比较**，同时保存**问题 · 帧范围 · 直方图 · 差异热图**。'
     '非确定性平台要记**概率事件 · 任务队列 · 物理子步 · 线程竞争 · '
     '时间回拨 · 浮点差异**'),
    ('**版本过期与内容淘汰策略**',
     '🔴 **"新版本兼容旧存档"只是宣传，不能证明**。'
     '需要 `version_contract.yaml`：版本 · 构建 · 资产哈希 · 启用特性 · '
     '保存 schema · 联网协议 · **过期日期** · 可迁移目标 · **不可迁移原因**'),
    ('**主线因果图与分支即时反馈**',
     '把任务 · 对话 · 世界状态 · 物品 · 地点 · 技能 · 结局建模为**有向图**，'
     '每条边记**触发条件 · 即时反应 · 延迟后果 · 可观察性 · 存档快照 · '
     '冲突解决**。🔴 **不能把"对话引擎"误当"分支因果验证器"**'),
]

CONFLICTS = [
    '❌ **"保留名字、重做手感"**（生活玩法）',
    '❌ 钓鱼加辅助线 / 自动收线 / 取消断线',
    '❌ **把随机配方改确定配方**',
    '❌ **第一次失败就提示**（改变挫败曲线）',
    '❌ 一开始塞满百科 / 高亮所有可互动物',
    '❌ **把跳跃谜题改为无障碍直达**',
    '❌ **只迁移进度不迁移纪念性记录**',
    '❌ 设置迁移**只比较键名**',
    '❌ **把对话 A 能转身、对话 B 不能抽象成统一规则**',
    '❌ **默认允许跳过原本不可跳过的过场**',
    '❌ **加入强制在线 / 登录门**',
    '❌ **"修复"稀缺性**',
    '❌ 每样只改一点（累积成不同的经济）',
    '❌ **静默宣称"旧录像可用"**',
]

FIELDS = [
    ('item_id', '项编号'),
    ('domain', '域（fish / gather / mount / pet / home / fsm / teach / unk / '
               'adv / trace / setmig / keep / matrix / choice / skip / '
               'offline / econ / scarc / g）'),
    ('legacy_value', '**原版值**'),
    ('new_value', '新引擎值'),
    ('match', '**是否一致**'),
    ('deviation', '**偏差等级**（等价/非must-match/不等）'),
    ('evidence', '证据等级 1-8'),
]


def _hdr(t, w=80):
    print('=' * w)
    print(t)
    print('=' * w)


def cmd_fish(a):
    _hdr('🔑 钓鱼（**最小单元是拉力—时间曲线**）')
    for k, why in FISH_ITEMS:
        print(f'   {k:<20} {why}')
    print('\n规则:')
    for r in FISH_RULE:
        print(f'   {r}')
    print(f'\n   {FISH_WHY}')
    print('\n冲突: ' + ' '.join(FISH_CONFLICT))
    return 0


def cmd_gather(a):
    _hdr('采集 / 烹饪 / 小游戏')
    for k, why, loss in GATHER_FOUR:
        print(f'\n   【{k}】\n      录: {why}\n      丢: {loss}')
    print(f'\n   {GATHER_RULE}')
    return 0


def cmd_mount(a):
    _hdr('🔑 坐骑（**上下马＝控制权交接**）')
    print('乘用层必录:')
    for m in MOUNT_ITEMS:
        print(f'   · {m}')
    print('\n交接必录: ' + ' · '.join(MOUNT_SWAP))
    print('\n必测场景: ' + ' · '.join(MOUNT_CASES))
    print(f'\n   {MOUNT_RULE}')
    print('\n警告:')
    for w in MOUNT_WARN:
        print(f'   {w}')
    return 0


def cmd_pet(a):
    _hdr('宠物（**关系反馈层**）')
    for p in PET_ITEMS:
        print(f'   · {p}')
    print(f'\n   {PET_THREE}')
    return 0


def cmd_home(a):
    _hdr('家园（**居住感＝空闲行为与因果循环**）')
    for h in HOME_ITEMS:
        print(f'   · {h}')
    print(f'\n   {HOME_GRAPH}')
    return 0


def cmd_fsm(a):
    _hdr('🔑 首次启动（**不可重来的状态轨迹**）')
    print('状态: ' + ' · '.join(FSM_STATES))
    print('\n每条必录: ' + ' · '.join(FSM_FIELDS))
    print(f'\n   {FSM_RULE}')
    return 0


def cmd_teach(a):
    _hdr('失败教学（**三个时序**）')
    for k, why in TEACH_THREE:
        print(f'   {k:<12} {why}')
    print('\n必录: ' + ' · '.join(TEACH_FIELDS))
    print(f'\n   {TEACH_RULE}')
    return 0


def cmd_unk(a):
    _hdr('🔴 "不知道自己不知道"')
    for u in UNK_ITEMS:
        print(f'   · {u}')
    print('\n冲突: ' + ' '.join(UNK_CONFLICT))
    print(f'\n   {UNK_RULE}')
    return 0


def cmd_adv(a):
    _hdr('进阶技巧（**延迟兑现**）')
    print('技巧可达性表: ' + ' · '.join(ADV_TABLE))
    print(f'\n   {ADV_RULE}')
    print('\n新增引导等级:')
    for k, why in ADV_GRADES:
        print(f'   {k:<26} {why}')
    print(f'\n   {ADV_PRINCIPLE}')
    return 0


def cmd_trace(a):
    _hdr('🔑 人格化痕迹（**五类**）')
    print(f'   {"类型":<18}{"内容":<28}策略')
    print('   ' + '-' * 72)
    for k, why, s in TRACE_FIVE:
        print(f'   {k:<18}{why:<28}{s}')
    print('\n常见丢失点:')
    for k, why, loss in TRACE_LOSS:
        print(f'\n   【{k}】\n      查: {why}\n      丢: {loss}')
    print(f'\n   {TRACE_RULE}')
    return 0


def cmd_setmig(a):
    _hdr('设置迁移（**比较语义不只是键名**）')
    print(f'   {SETMIG_RULE}')
    print(f'\n   {SETMIG_KEY}')
    return 0


def cmd_keep(a):
    _hdr('涂鸦 / 照片 / 录像（**最易失证**）')
    print('必录: ' + ' · '.join(KEEP_FIELDS))
    print('\n规则:')
    for r in KEEP_RULE:
        print(f'   {r}')
    print(f'\n   {KEEP_HISTORY}')
    return 0


def cmd_matrix(a):
    _hdr('🔑 过场（**控制权矩阵**）')
    print('状态: ' + ' · '.join(MATRIX_STATES))
    print('\n每帧必录: ' + ' · '.join(MATRIX_PER_FRAME))
    print(f'\n   {MATRIX_RULE}')
    print(f'\n   {MATRIX_QTE}')
    print('\n模糊边界:')
    for f in MATRIX_FUZZY:
        print(f'   · {f}')
    print(f'\n   {MATRIX_WARN}')
    return 0


def cmd_choice(a):
    _hdr('选择（**即时表现 vs 因果结果**）')
    print('即时层: ' + ' · '.join(CHOICE_INSTANT))
    print('因果层: ' + ' · '.join(CHOICE_CAUSAL))
    print('\n延迟层级: ' + ' · '.join(CHOICE_EDGES))
    print(f'\n   {CHOICE_RULE}')
    return 0


def cmd_skip(a):
    _hdr('🔴 跳过（**"不可跳过"必须被证明**）')
    for s in SKIP_ITEMS:
        print(f'   · {s}')
    print('\n必测: ' + ' · '.join(SKIP_TEST))
    print(f'\n   {SKIP_RULE}')
    print('\n案例:')
    for c in SKIP_CASES:
        print(f'   {c}')
    return 0


def cmd_offline(a):
    _hdr('🔑 单机/联机（**功能降级图**）')
    print('矩阵项: ' + ' · '.join(OFFLINE_MATRIX))
    print('\n每项必录: ' + ' · '.join(OFFLINE_FIELDS))
    print('\n必测: ' + ' · '.join(OFFLINE_TEST))
    print('\n联机残留: ' + ' · '.join(OFFLINE_RESIDUE))
    print(f'\n   {OFFLINE_RULE}')
    print(f'\n   {OFFLINE_CONFLICT}')
    return 0


def cmd_econ(a):
    _hdr('🔑 经济（**按流量验证**）')
    for k, why in ECON_FOUR:
        print(f'   {k:<16} {why}')
    print('\n场景: ' + ' · '.join(ECON_SCENARIOS))
    print(f'\n   {ECON_RULE}')
    print(f'\n   {ECON_WARN}')
    print('\n刷钱不变量: ' + ' · '.join(FARM_INVARIANTS))
    print(f'\n   {FARM_RULE}')
    return 0


def cmd_scarc(a):
    _hdr('稀缺性（**反舒适但必须保留**）')
    for s in SCARCITY_ITEMS:
        print(f'   · {s}')
    print(f'\n   {SCARCITY_RULE}')
    return 0


def cmd_g(a):
    _hdr('G 类（**三项新盲层**）')
    for k, why in G_THREE:
        print(f'\n   【{k}】\n      {why}')
    return 0


def cmd_init(a):
    os.makedirs(os.path.dirname(a.init) or '.', exist_ok=True)
    with open(a.init, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow([k for k, _ in FIELDS])
        w.writerow(['TODO'] * len(FIELDS))
    print(f'已生成生活玩法/痕迹表: {a.init}')
    print('\n⚠️ 十九域：fish / gather / mount / pet / home / fsm / teach / '
          'unk / adv / trace / setmig / keep / matrix / choice / skip / '
          'offline / econ / scarc / g')
    print('\n⚠️ 偏差等级只能填：等价 / 非must-match / 不等')
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

    OK_DEV = ('等价', 'equivalent', '非must-match', 'not-must-match', '不等',
              'different')
    mismatch, no_legacy, bad_dev, no_grade, unequal = [], [], [], [], []
    for i, r in enumerate(rows, 1):
        m = g(r, 'match').lower()
        if m not in ('yes', 'y', 'true', '是', '一致'):
            mismatch.append(i)
        if not g(r, 'legacy_value') or g(r, 'legacy_value') == 'TODO':
            no_legacy.append(i)
        d = g(r, 'deviation')
        if not d or d == 'TODO' or d not in OK_DEV:
            bad_dev.append(i)
        elif d == '不等':
            unequal.append(i)
        ev = g(r, 'evidence')
        if not ev or ev == 'TODO':
            no_grade.append(i)
        else:
            n = ev.split('.')[0].strip()
            if n.isdigit() and int(n) >= 7:
                no_grade.append(i)

    print('=' * 76)
    print(f'生活玩法/痕迹 · {len(rows)} 条')
    print('=' * 76)
    if mismatch:
        print(f'\n🚫 **不一致** {len(mismatch)} 条（行 {mismatch[:15]}）')
    if no_legacy:
        print(f'\n❌ {len(no_legacy)} 条缺**原版值**（行 {no_legacy[:15]}）')
    if bad_dev:
        print(f'\n🚫 {len(bad_dev)} 条偏差等级非法'
              f'（行 {bad_dev[:15]}）—— 只能填 等价/非must-match/不等')
    if unequal:
        print(f'\n🚫 {len(unequal)} 条标"**不等**"（行 {unequal[:15]}）')
        print('   ⚠️ 影响碰撞/伤害/可达区域/经济获取/保存/分支的，'
              '默认都是 must-match')
    if no_grade:
        print(f'\n🚫 {len(no_grade)} 条**证据等级缺失或 ≥7 级**'
              f'（行 {no_grade[:15]}）')

    if not (mismatch or no_legacy or bad_dev or no_grade or unequal):
        print('\n✅ 生活玩法/痕迹：一致、原版值完整、偏差已声明、证据达标')

    print('\n🔑 **验收单位从"功能存在"升级为"状态轨迹逐字段相等"。**')
    print('   **第一次失败就提示，即使文本相同，也改变了挫败曲线。**')
    print('   **只迁移进度不迁移纪念性记录＝把老玩家重置成新玩家。**')
    return 1 if (a.gate_check and
                 (mismatch or no_legacy or bad_dev or no_grade or
                  unequal)) else 0


def main():
    ap = argparse.ArgumentParser(description='生活玩法与人格化痕迹')
    ap.add_argument('--fish', action='store_true')
    ap.add_argument('--gather', action='store_true')
    ap.add_argument('--mount', action='store_true')
    ap.add_argument('--pet', action='store_true')
    ap.add_argument('--home', action='store_true')
    ap.add_argument('--fsm', action='store_true')
    ap.add_argument('--teach', action='store_true')
    ap.add_argument('--unk', action='store_true')
    ap.add_argument('--adv', action='store_true')
    ap.add_argument('--trace', action='store_true')
    ap.add_argument('--setmig', action='store_true')
    ap.add_argument('--keep', action='store_true')
    ap.add_argument('--matrix', action='store_true')
    ap.add_argument('--choice', action='store_true')
    ap.add_argument('--skip', action='store_true')
    ap.add_argument('--offline', action='store_true')
    ap.add_argument('--econ', action='store_true')
    ap.add_argument('--scarc', action='store_true')
    ap.add_argument('--g', action='store_true')
    ap.add_argument('--init')
    ap.add_argument('--check')
    ap.add_argument('--gate-check', action='store_true')
    a = ap.parse_args()
    fns = {'fish': cmd_fish, 'gather': cmd_gather, 'mount': cmd_mount,
           'pet': cmd_pet, 'home': cmd_home, 'fsm': cmd_fsm,
           'teach': cmd_teach, 'unk': cmd_unk, 'adv': cmd_adv,
           'trace': cmd_trace, 'setmig': cmd_setmig, 'keep': cmd_keep,
           'matrix': cmd_matrix, 'choice': cmd_choice, 'skip': cmd_skip,
           'offline': cmd_offline, 'econ': cmd_econ, 'scarc': cmd_scarc,
           'g': cmd_g}
    for k, fn in fns.items():
        if getattr(a, k):
            return fn(a)
    if a.init:
        return cmd_init(a)
    if a.check:
        return cmd_check(a)
    print('❌ 需要 --fish / --gather / --mount / --pet / --home / --fsm / '
          '--teach / --unk / --adv / --trace / --setmig / --keep / '
          '--matrix / --choice / --skip / --offline / --econ / --scarc / '
          '--g / --init / --check 之一')
    return 2


if __name__ == '__main__':
    sys.exit(main())
