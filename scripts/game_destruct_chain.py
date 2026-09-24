#!/usr/bin/env python3
"""可破坏世界 · 元素连锁 · 绳索软体约束 · 读档重摇
（第三十七轮 A / B / C / D 类，含 E / F / G 补充）。

**🔑 本轮的核心判断**：
> A—D 的共同特点：原版往往用一套"**半程序化 · 半脚本化 · 高度耦合**"的
> **自研子系统**实现，而重制侧现有引擎（Chaos / Blast / Flow / Obi）
> 提供的是**更高性能 · 更稳定的通用解**。
> 🔴 **直接迁移会静默改变玩法结果** ——
> 这正是 `must-match` "偏离即 BUG" 的典型场景。

**🔑 四条具体的发现**：
1. 破坏粒度从**整体替换**迁到 **Voronoi 分块** →
   **旧速通路线的碎块弹射角度与可站立面改变**
2. 元素传播若用**逐格扫描且更新顺序依赖遍历顺序** →
   **30fps / 60fps 下连锁结果分叉**
3. 约束求解器**同一组参数**在不同**迭代次数与子步**下给出不同周期与阻尼
   → **荡绳"差一点过不去"是可测量的连续函数**
4. **RNG 状态是否被快照**决定开箱前存档能否重摇 ——
   🔴 **固化时机（生成时 vs 开启时）比"是否固化"更隐蔽**

用法:
  game_destruct_chain.py --dest    # 🔑 **破坏粒度**（四种实现）
  game_destruct_chain.py --support # 🔴 **承重是显式连接图属性**
  game_destruct_chain.py --debris  # 🔑 **碎块消失是四个独立计时器**
  game_destruct_chain.py --nav     # 🔴 **障碍只能阻塞，不能创造可行走面**
  game_destruct_chain.py --hole    # 开洞对光照/遮挡/**音频衍射**的影响
  game_destruct_chain.py --persist # **破坏持久性四层**
  game_destruct_chain.py --elem    # 🔑 **元素矩阵是不对称方阵**
  game_destruct_chain.py --prop    # 🔴 **更新顺序决定确定性**
  game_destruct_chain.py --wind    # **风场是连锁范围最大的单一变量**
  game_destruct_chain.py --resid   # **灭火残留是玩法耦合最密集处**
  game_destruct_chain.py --rope    # 🔑 **同一参数是伪命题**
  game_destruct_chain.py --iter    # 🔴 **迭代/子步/时间步共同决定刚度**
  game_destruct_chain.py --swing   # **荡绳可达性是连续函数**
  game_destruct_chain.py --tangle  # 缠绕 · 自碰撞 · 断裂
  game_destruct_chain.py --rng     # 🔑 **RNG 状态快照三档**
  game_destruct_chain.py --when    # 🔴 **固化时机**（四档）
  game_destruct_chain.py --scope   # **RNG 实例隔离**
  game_destruct_chain.py --amb     # 氛围**密度不是数量**
  game_destruct_chain.py --g7      # 🔑 G 类七项新盲区
  game_destruct_chain.py --init ledger/destruct_chain.csv
  game_destruct_chain.py --check ledger/destruct_chain.csv --gate

退出码: 0 通过 / 1 缺项 / 2 用法错误
"""
import argparse
import csv
import os
import sys

# 🔑 破坏粒度
DEST_FOUR = [
    ('**整体替换**', 'mesh swap：整体静态网格换成已碎版本',
     '**碎块位置完全确定**'),
    ('**分块预制碎片**', '预拆分块', '中等'),
    ('**运行时 Voronoi/布尔切分**', '运行时计算断裂面',
     '🔴 **每次断裂面不同**'),
    ('**体素逐体素挖除**', '体积化挖洞', '最高自由度'),
]

DEST_FIELDS = [
    '**碎块数量分布**（最小值/众数/最大值/每资产）',
    '**碎片是否成为独立物理体**',
    '**碎块是否可拾取**',
    '**碎块是否可作为武器投掷**',
    '**碎块碰撞是否参与伤害事件**',
]

DEST_RULE = '🔑 **破坏粒度不是视觉档位，而是玩法结果的函数**'

# 🔴 承重
SUPPORT_ITEMS = [
    '每个 chunk 有**支持标记**',
    '**bond** 有表面质心 · 平均法线 · 面积',
    '支持 chunk 之间通过 bond 相连成 actor',
    '伤害定义为 **actor 材料完整性的损失**',
    '模块间有 **connection** 与 **anchor**，'
    '整体冲量超阈值（加随机偏移）则断',
    '求解器是**稀疏直接求解器**（Cholesky），连通性变化后重算',
]

SUPPORT_RULE = [
    '🔑 **"承重"不是启发式判断，而是显式的连接图属性** —— '
    'Blast 的层级分块 + 支撑图 + 键合模型是最佳结构化参照',
    '🔑 复刻必须**反向推导出原版每个可破坏物的支撑拓扑**，'
    '🔴 **而不能只看它何时播放破碎动画**',
    '🔑 取证任务：对每个承重结构逐一测"**打掉单根柱/梁后整段是否塌落**"，'
    '并区分"**整段同时崩塌**"与"**逐块级联坍塌**" —— '
    '🔴 **两者时间窗（数帧 vs 数秒）和声音设计完全不同**',
]

# 🔑 碎块四计时器
DEBRIS_FOUR = [
    '**停止运动 → 进入休眠**的时长（sleep threshold 决定）',
    '**休眠 → 开始淡出**的延迟',
    '**淡出持续时间**',
    '**碎片池回收时机**',
]

DEBRIS_EXTRA = [
    '距玩家多远时**提前回收**',
    '**视线外是否立即回收**',
    '同一区域**碎片数量上限**（超限按什么淘汰：最旧/最远/最小）',
]

DEBRIS_RULE = [
    '🔑 **碎块何时消失是四个独立计时器，'
    '不能合并为一个"碎块寿命"**',
    '🔑 量级参照：**6DOF** 用于非玩法关键的凸体，**3DOF** 用于点/球体粒子'
    '（火花 · 烟 · 雾 · 雨 · 雪 · 昆虫群）',
    '🔑 10000 个刚体换成 Physics Particles 后典型 **4–6 倍**性能提升；'
    '开启角效应（6DOF）增加约 **15%** 模拟开销',
    '🔴 **原版很可能对"可交互碎片"与"纯装饰碎片"走了两条不同代码路径** —— '
    '全用刚体性能先崩；全降级为粒子则**无法站上碎块 · 堵水 · 当武器**',
]

# 🔴 NavMesh
NAV_RULE = [
    '🔑 墙被炸开后 NavMesh 需重建；地板塌落后 AI 会掉下去',
    '🔑 路径：**Dynamic Obstacle** 标记需重建区域（比整块 Nav Tile 重建低），'
    '或 **NavMesh Data Chunk Streaming** 配静态 NavMesh 与子关卡加载',
    '🔴 **关键：障碍只能阻塞已有可行走面，不能凭空创造新可行走面** —— '
    '炸出新洞口需要**完整重烘焙**',
]

NAV_TEST = [
    '① 破坏后记录 **NavMesh 顶点变化**'
    '（原版当帧 / 延迟 / 完全不更新？）',
    '② 记录 **AI 对路径失效的反应**'
    '（立即重寻路 / 卡住数秒 / 退回上一检查点）',
]

NAV_WARN = '🔴 **若原版完全不更新导航，重制后 AI 突然会绕路，'
'反而改变了战术布局 —— 这是偏离原版**'

# 开洞
HOLE_ITEMS = [
    '🔑 **光照**：开洞后光透进来（体素化间接光可实时更新，但成本高）',
    '🔴 **法线与截面材质**：GPU 端 `discard` 挖洞只丢像素、'
    '**不改变顶点法线** → 破洞边缘**明暗断裂 · 高光漂移 · 自阴影伪影**',
    '🔑 **音频衍射**：声音绕开孔边缘，低频衰减更慢，边缘可视为点声源',
    '🔑 **音频透射**：声能穿透障碍，损失取决于材料密度与厚度',
    '🔴 **致密材料（如混凝土）的透射能量在附近有开孔时'
    '可能远小于衍射能量**',
]

HOLE_RULE = '🔑 **洞的大小是否改变直达声与混响，是必须逐场景实测的 '
'must-match 项** —— 原版若预烘焙混响区，重制换实时空间音频，'
'玩家能听出房间"变大"'

# 持久性
PERSIST_FOUR = [
    '**当前会话内**（退出区域是否恢复）',
    '**跨场景流式加载后**',
    '**读档后**',
    '**跨周目后**',
]

PERSIST_EXTRA = '联机还要加"**其他玩家是否看见同一破碎状态**"'

PERSIST_SOFTLOCK = [
    '**堵死唯一通路**（原版是否提供备用出口/自毁计时/可清除障碍）',
    '**掉出可到达区域**（是否有 kill volume 兜底）',
    '**堆叠碎块越过设计高度**（是否允许）',
]

PERSIST_RULE = '🔑 字段应**直接挂在可破坏资产上**，'
'🔴 **而不是写在关卡逻辑里** —— 这样批量校验与混沌测试才能覆盖'

# 🔑 元素矩阵
ELEM_MATRIX = [
    '是否反应', '反应产物', '**触发条件（元素量阈值）**',
    '产物持续时间', '**是否双向对称**',
    '**是否有顺序依赖**（A 先 B 后 vs B 先 A 后）',
]

ELEM_ASYM = [
    '**火点燃油**需要油达可燃条件 + 火源持续时间',
    '**油遇火**的反应可能不反向成立',
    '**电在水面**触发范围伤害，但水被"污染"后是否有持续时间、'
    '是否影响后续电事件，必须分开记录',
]

ELEM_EXTINGUISH = [
    '**燃料耗尽**', '**温度低于燃点**', '**氧气被隔绝**', '**被水冷却**',
    '**被沙覆盖**',
]

ELEM_RULE = [
    '🔑 **元素矩阵必须显式写成方阵，且矩阵不一定对称**',
    '🔑 推荐维度："**可承载元素 × 元素事件**"',
    '🔑 衰减/熄灭条件是不同的**状态转移**，'
    '🔴 **不是同一个"灭火"动作**',
]

# 🔴 传播
PROP_GRID = [
    '元素量网格（燃料 · 温度 · 燃烧 · 烟）',
    '速度场（速度三分量 + 散度）',
]

PROP_RULE = [
    '🔑 **传播是逐格模拟还是脚本，决定了能否确定性重放**',
    '🔴 **更新顺序决定是否对称** —— 从左到右扫描时左格先更新会影响右格，'
    '右到左扫描结果不同',
    '🔴 **30fps 与 60fps 下每帧处理的活跃格集合也不同，'
    '连锁的几何形状会分叉**',
    '🔑 燃烧在正式工具里是**一组可序列化 · 可版本化的参数**'
    '（`buoyancyPerBurn` · `burnPerTemp` · `fuelPerBurn` · '
    '`divergencePerBurn`），可逐字段当 must-match 对照项',
    '🔑 阻尼与衰减**分通道独立**（`damping` 指数衰减 · '
    '`fade` 固定单位/秒）',
]

PROP_TEST = '🔑 固定输入序列 + 固定种子，在 **30/60/120fps** 与'
'**两档 CPU 核心频率**下跑，逐格 dump 元素量网格并**二进制 diff**。'
'🔴 **若 diff 出现，则原版是帧率依赖的，重制必须刻意保留同一依赖'
'而非"顺手修好"** —— 否则速通计时不再可比'

# 风场
WIND_ITEMS = [
    '风是否影响**火焰传播速度与方向**',
    '风是否影响**烟雾浓度与可视距离**',
    '风是否影响**抛射物**（火球 · 火星）',
    '**室内外风场是否分别计算**',
    '**玩家动作**（奔跑 · 扇风 · 开扇门）是否局部扰动风场',
]

WIND_RULE = '🔑 **风场耦合是连锁范围最大的单一变量**。'
'🔴 特别要测"**运动平台上的火**"（电梯 · 马车 · 升降机）—— '
'**原版很可能完全忽略相对运动**'

# 残留
RESID_ITEMS = [
    '**灰烬**（是否可拾取/可堆肥）',
    '**炭化表面**（是否改变材质属性与摩擦）',
    '**湿痕**（是否有蒸发计时与二次点燃条件）',
    '**烟雾残留**（是否仍触发咳嗽/能见度 debuff）',
    '**熄灭的燃料源**（是否可重新点燃）',
]

RESID_CASE = '🔑 一个具体取证用例：**燃烧中的木桶被打灭后，用点燃箭再次射击**'
'—— 原版是重新燃起还是永久失效？🔴 **直接影响解谜路线与速通策略**'

RESID_ASK = '每个残留项都要追问：**读档后是否恢复 · '
'离开区域后是否消失 · 多人是否同步**'

# 🔑 绳索
ROPE_RULE = '🔑 **换求解器后"同一参数"是伪命题** —— '
'🔴 **必须先匹配求解语义，再匹配数值**'

ROPE_ITER = [
    '**0.1ms 时间步下 1 次迭代**即可消除拉伸',
    '**0.01ms 时间步下同样 1 次迭代**能同时获得稳定与"更有生气"的动态',
    '**0.1ms 下 10 次迭代**虽能保持绷紧，却**抑制动态并损失性能**',
]

ROPE_KINDS = [
    '**碰撞约束**（多碰撞时高迭代更稳健）',
    '**距离约束**（布料与绳索的弹性来源，高迭代更硬）',
    '**Pin 约束**（附着点漂移）',
    '**体积约束**（充气软体压力）',
    '**弯曲约束** · **tether** · **skin**',
    '**密度**（流体不可压缩，越高越像水而非果冻）',
    '**形状匹配**（软体） · **拉伸/剪切** · **弯曲/扭转**（杆）',
]

ROPE_WARN = '🔴 **只迁移"刚度 0.8"而不迁移该数值对应的'
'约束类型与迭代预算，结果不可预测**'

# 🔴 迭代
ITER_UNITY = 'Unity 官方建议**默认求解器迭代次数与默认速度迭代次数都设为 '
'10–20**，并启用 `ConfigurableJoint.projectionMode` 或 '
'`CharacterJoint.enableProjection`'
ITER_UE = '🔑 UE5 Chaos 有**位置/速度/投影**三类迭代；从 UE5.5 起支持'
'**逐对象迭代次数**，🔴 **对象实际使用的迭代次数是其所属约束孤岛内'
'所有对象设置的最大值**'
ITER_ISLAND = '🔴 **改变一个物体的迭代次数可能通过改变孤岛最大值'
'间接改变其他物体的手感**'

# 荡绳
SWING_FORMULA = '单摆周期（小角度近似）`T = 2π√(l/g)`，**与摆锤质量无关**；'
'但**空气阻尼下**，相同周期、不同截面积与质量的摆锤**衰减速度不同**'

SWING_FIELDS = [
    '静止长度', '可伸长范围', '附着点偏移容差', '**最大摆角**',
    '**末端位置在周期内的可达区域**',
    '**玩家碰撞体是否在摆动中触及目标平台**',
]

SWING_RULE = '🔑 **"绳索长度"不是唯一变量**：摆锤质量 · 玩家碰撞体尺寸 · '
'空气阻力 · 绳索质量分布 · 附着点摩擦 · 玩家输入额外冲量**共同决定**'
'能否荡到对岸。🔴 **速通回归要保存这些连续值的历史区间，'
'而不是只存"能否到达"**'

# 缠绕
TANGLE_ITEMS = [
    '绳索能否**绕柱半圈以上形成摩擦自锁**',
    '缠绕后能否**反向解开**',
    '缠绕是否影响**有效绳长**',
    '缆线/链条是否能**穿过自身**（自碰撞开关）',
    '**末端附件**（钩爪 · 摆锤）是否会因碰撞被卡住',
]

TANGLE_DIFF = '链条与绳索的差别在**弯曲刚度与质量分布**：'
'链条每个链节是独立碰撞体（开销与抖动风险更高）；'
'电缆常把内部线缆当无碰撞约束、仅外皮参与碰撞'
TANGLE_FIELDS = [
    '自碰撞开关', '碰撞厚度', '**质量沿长度的离散化段数**',
    '**段间最大相对角度**（链节关节限位）',
]

# 🔑 RNG
RNG_THREE = [
    ('**preserve**', '保存并恢复'),
    ('**reseed**', '读档时重新播种'),
    ('**consume**', '**动作发生时立即消耗并固化结果**'),
]

RNG_RULE = [
    '🔑 **RNG 是否在读档后重摇，取决于状态是否被快照 —— 这是一条硬开关**',
    '🔑 Unity `Random.state` 可获取并设置完整内部状态、可序列化、'
    '可跨会话保持确定性',
    '🔑 Sphere Engine `RNG::state` 是 **32 字节十六进制字符串**，'
    '官方明确把此能力用于**对抗 save scumming**',
    '🔴 **第三档（consume）最容易被忽略，却对刷取玩法影响最大**',
]

# 🔴 固化时机
WHEN_FOUR = [
    '**生成时**', '**首次交互时**', '**结果结算时**', '**读档时重算**',
]

WHEN_CASES = [
    '**宝箱内容**：区域生成时固化 / 开箱瞬间固化 / 读档后重算',
    '**掉落物**：敌人死亡时固化 / 拾取时固化',
    '**对话检定**：对话开始时固化 / 每次尝试时固化',
    '**商店库存**：每日刷新时固化 / 每次打开时重算',
    '**天气/随机事件**：时段切换时固化 / 每帧判定',
]

WHEN_RULE = '🔑 **固化时机的差异决定玩家"存档点应该设在哪"** —— '
'这是社区形成的肌肉记忆，🔴 **重制若改变，既有攻略失效**'

RNG_COMMUNITY = '🔑 常见利用：开箱前存档反复读取 · 检定/射击前存档重试 · '
'利用确定性序列故意消耗若干次随机调用到达"好结果" · 多槽管理"种子档"。'
'🔴 **重制若全部改为读档后重摇，这些玩法被破坏；若全部固化，'
'依赖重摇的刷取策略也失效。决策必须由 product/设计层显式作出，'
'不能在引擎迁移时"顺手统一"**'

# RNG 隔离
SCOPE_SIX = [
    '元信息（版本 · 槽位 · 时间戳）', '玩家状态', '世界状态',
    '任务/叙事状态', '配置状态', '**模拟状态**（RNG 属于此类）',
]

SCOPE_RULE = [
    '🔑 **仅有相同 RNG 状态而输入序列不同（如 NPC 行为消耗了不同次数的'
    '随机数），结果仍不同** —— NPC 漫游绑定 RNG，'
    '即使同种子，重读档后多等几秒掉落就不同',
    '🔑 取证要做**多 RNG 实例隔离测试**：玩家战斗 · 敌人 AI · 掉落 · '
    '世界事件 · 天气 · 对话检定**是否共用一个生成器**。'
    '🔴 **共用则一处多消耗就会污染另一处**',
]

SCOPE_FIELDS = [
    '`rng_scope`（全局 / 系统隔离 / 实体隔离）', '`rng_algorithm`',
    '`state_size_bytes`', '`consumption_order`（调用顺序是否版本化）',
    '`rng_version`（存档格式版本）',
]

# 氛围
AMB_IDLE = [
    '**主待机循环时长**', '**随机微动画的首次触发延迟区间**',
    '两次微动画间的**最小/最大间隔**', '**变体池大小**',
    '**起始帧是否随机化**', '过渡曲线（线性还是缓入缓出）',
    '被打断后的恢复行为', '**视线朝向与玩家距离是否影响触发概率**',
]

AMB_RULE = ('🔑 待机动画的最小取证单元是"**首次触发时间 + 变体池相位**"，'
            '不是动画名。🔴 **若所有同类 NPC 在同一帧切换动作，世界立刻显假**')

AMB_THREE = [
    '**日程表**（几点在哪做什么）',
    '**巡逻路径**（区域内怎么走）',
    '**小事件**（路过时是否发生互动）',
]

AMB_SEMANTIC = [
    '**装饰**', '**指引**（鸟飞走方向 = 安全路）',
    '**预警**（鸟惊散 = 附近有敌人/即将爆炸）',
    '**线索**（吵架位置 = 可触发支线）',
]

AMB_DENSITY = '🔑 "活着"的密度阈值**没有权威标准，只能差异法实测**：'
'在原版场景内做 A/B 抽帧，以 **25%/50%/75%/100%** 的 NPC 与事件密度'
'渲染同一段 60 秒行走，盲评"世界是否活着"，同时记帧率与内存。'
'🔴 **这是唯一建议用玩家研究而非逆向取证解决的子项**'

# G 七项
G_SEVEN = [
    ('**触发器脉冲沿语义**',
     '四种：**上升沿 · 电平 · 下降沿 · 双边沿**。'
     '🔴 最易把"进入一次"误做成"停留每帧"（重复触发），'
     '或把"停留持续伤害"误做成"进入一次"（完全无效）。'
     '锚点：`OnTriggerEnter`/`Stay`/`Exit`。'
     '字段：`trigger_edge` · `reentry_policy` · `cooldown` · '
     '`overlap_priority`'),
    ('**布料形变记忆**',
     '抓起斗篷/压窗帘/旗帜长期缠绕后松开，原版**可能保留褶皱**'
     '也可能**立即回弹**。前者让世界"记得你做过什么"。'
     '字段：`deformation_persistence`（none/short/medium/permanent）· '
     '`relaxation_curve` · `memory_across_load`'),
    ('**自动存档原子性与竞态**',
     '自动与手动同时触发 · 流式加载中存档 · 物理结算未完成快照 · '
     '异步写入被中断。字段：`atomicity_strategy` · `write_lock` · '
     '`temp_file_policy` · `checksum_algorithm` · '
     '`crash_recovery_behavior`'),
    ('**焦外注视与微表情**',
     '高分辨率下面部新破绽：眼球不微跳 · 注视点不随对话对象移动 · '
     '**眨眼周期过于规律** · 瞳孔缺高光点 · 喉结/次要肌肉不动。'
     '字段：`gaze_target` · `blink_interval_distribution` · '
     '`eye_micro_saccade` · `catch_light_consistency`'),
    ('**手柄力反馈频谱**',
     '震动不只是"强度+时长"：低频/高频**双马达配比** · '
     '随物理事件的**包络曲线** · 扳机阻尼 · 自适应扳机位置相关阻力。'
     '字段：`rumble_envelope`（采样点序列）· '
     '`trigger_resistance_curve` · `haptic_device_scope`'),
    ('**部分复位的边界**',
     '**部分状态复位而部分不复位**：地形恢复但弹坑不恢复 · '
     '油桶复位但泼出的油不复位 · NPC 醒来位置复位但仇恨列表不复位。'
     '字段：`reset_scope`（per-field mask）· `reset_trigger`'),
    ('**确定性构建与反作弊兼容**',
     '反作弊是否影响单机/模组/调试/录像/速通工具；'
     '内存校验是否破坏确定性。字段：构建配置矩阵'),
]

CONFLICTS = [
    '❌ **用 Voronoi 自动提升破坏粒度**',
    '❌ **把元素连锁简化为纯视觉特效**',
    '❌ **全局统一绳索求解器迭代次数**',
    '❌ **为反重摇统一固化所有 RNG**',
    '❌ 为性能砍氛围密度却不补偿多样性',
    '❌ 让反作弊常驻所有构建',
    '❌ 把已退役的 live ops 内容不写入清单',
    '❌ **用"看起来差不多"替代逐格/逐帧 diff 的确定性验证**',
    '❌ 把触发器电平与边沿混用而不记录语义',
    '❌ **把布料形变记忆"优化"为始终回弹**',
    '❌ **"顺手修好"帧率依赖的元素传播**（速通计时不再可比）',
    '❌ 只迁移"刚度 0.8"而不迁移约束类型与迭代预算',
]

FIELDS = [
    ('item_id', '项编号'),
    ('domain', '域（dest / support / debris / nav / hole / persist / elem / '
               'prop / wind / resid / rope / iter / swing / tangle / rng / '
               'when / scope / amb / g7）'),
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


def cmd_dest(a):
    _hdr('🔑 破坏粒度（**不是视觉档位**）')
    print(f'   {"实现":<26}{"说明":<30}确定性')
    print('   ' + '-' * 74)
    for k, why, d in DEST_FOUR:
        print(f'   {k:<26}{why:<30}{d}')
    print('\n必录字段:')
    for f in DEST_FIELDS:
        print(f'   · {f}')
    print(f'\n   {DEST_RULE}')
    return 0


def cmd_support(a):
    _hdr('🔴 承重（**显式连接图属性**）')
    for s in SUPPORT_ITEMS:
        print(f'   · {s}')
    print('\n规则:')
    for r in SUPPORT_RULE:
        print(f'   {r}')
    return 0


def cmd_debris(a):
    _hdr('🔑 碎块（**四个独立计时器**）')
    for i, d in enumerate(DEBRIS_FOUR, 1):
        print(f'   {i}. {d}')
    print('\n额外:')
    for e in DEBRIS_EXTRA:
        print(f'   · {e}')
    print('\n规则:')
    for r in DEBRIS_RULE:
        print(f'   {r}')
    return 0


def cmd_nav(a):
    _hdr('🔴 NavMesh（**障碍只能阻塞，不能创造**）')
    for r in NAV_RULE:
        print(f'   {r}')
    print('\n取证脚本:')
    for t in NAV_TEST:
        print(f'   {t}')
    print(f'\n   {NAV_WARN}')
    return 0


def cmd_hole(a):
    _hdr('开洞（光照 / 法线 / **音频衍射**）')
    for h in HOLE_ITEMS:
        print(f'   · {h}')
    print(f'\n   {HOLE_RULE}')
    return 0


def cmd_persist(a):
    _hdr('破坏持久性（**四层**）')
    for p in PERSIST_FOUR:
        print(f'   · {p}')
    print(f'\n   {PERSIST_EXTRA}')
    print('\n软锁防护:')
    for s in PERSIST_SOFTLOCK:
        print(f'   · {s}')
    print(f'\n   {PERSIST_RULE}')
    return 0


def cmd_elem(a):
    _hdr('🔑 元素矩阵（**不对称方阵**）')
    print('单元格: ' + ' · '.join(ELEM_MATRIX))
    print('\n不对称例:')
    for e in ELEM_ASYM:
        print(f'   · {e}')
    print('\n熄灭/衰减（不同状态转移）: ' + ' · '.join(ELEM_EXTINGUISH))
    print('\n规则:')
    for r in ELEM_RULE:
        print(f'   {r}')
    return 0


def cmd_prop(a):
    _hdr('🔴 传播（**更新顺序决定确定性**）')
    print('双层网格: ' + ' · '.join(PROP_GRID))
    print('\n规则:')
    for r in PROP_RULE:
        print(f'   {r}')
    print(f'\n   {PROP_TEST}')
    return 0


def cmd_wind(a):
    _hdr('风场（**连锁范围最大的单一变量**）')
    for w in WIND_ITEMS:
        print(f'   · {w}')
    print(f'\n   {WIND_RULE}')
    return 0


def cmd_resid(a):
    _hdr('灭火残留（**玩法耦合最密集**）')
    for r in RESID_ITEMS:
        print(f'   · {r}')
    print(f'\n   {RESID_CASE}')
    print(f'\n   {RESID_ASK}')
    return 0


def cmd_rope(a):
    _hdr('🔑 绳索（**同一参数是伪命题**）')
    print(f'   {ROPE_RULE}')
    print('\n时间步 × 迭代:')
    for i in ROPE_ITER:
        print(f'   · {i}')
    print('\n约束类型清单（参数审计表）:')
    for k in ROPE_KINDS:
        print(f'   · {k}')
    print(f'\n   {ROPE_WARN}')
    return 0


def cmd_iter(a):
    _hdr('🔴 迭代（**孤岛最大值**）')
    print(f'   {ITER_UNITY}')
    print(f'\n   {ITER_UE}')
    print(f'\n   {ITER_ISLAND}')
    return 0


def cmd_swing(a):
    _hdr('荡绳（**可达性是连续函数**）')
    print(f'   {SWING_FORMULA}')
    print('\n必测: ' + ' · '.join(SWING_FIELDS))
    print(f'\n   {SWING_RULE}')
    return 0


def cmd_tangle(a):
    _hdr('缠绕 · 断裂')
    for t in TANGLE_ITEMS:
        print(f'   · {t}')
    print(f'\n   {TANGLE_DIFF}')
    print('\n字段: ' + ' · '.join(TANGLE_FIELDS))
    return 0


def cmd_rng(a):
    _hdr('🔑 RNG 状态快照（**硬开关三档**）')
    for k, why in RNG_THREE:
        print(f'   {k:<16} {why}')
    print('\n规则:')
    for r in RNG_RULE:
        print(f'   {r}')
    return 0


def cmd_when(a):
    _hdr('🔴 固化时机（**四档**）')
    print('   ' + ' · '.join(WHEN_FOUR))
    print('\n逐类:')
    for w in WHEN_CASES:
        print(f'   · {w}')
    print(f'\n   {WHEN_RULE}')
    print(f'\n   {RNG_COMMUNITY}')
    return 0


def cmd_scope(a):
    _hdr('RNG 实例隔离')
    print('存档六类: ' + ' · '.join(SCOPE_SIX))
    print('\n规则:')
    for r in SCOPE_RULE:
        print(f'   {r}')
    print('\n字段: ' + ' · '.join(SCOPE_FIELDS))
    return 0


def cmd_amb(a):
    _hdr('氛围生命力（**密度不是数量**）')
    for x in AMB_IDLE:
        print(f'   · {x}')
    print(f'\n   {AMB_RULE}')
    print('\n三层: ' + ' · '.join(AMB_THREE))
    print('\n环境事件语义: ' + ' · '.join(AMB_SEMANTIC))
    print(f'\n   {AMB_DENSITY}')
    return 0


def cmd_g7(a):
    _hdr('🔑 G 类（**七项新盲区**）')
    for k, why in G_SEVEN:
        print(f'\n   【{k}】\n      {why}')
    return 0


def cmd_init(a):
    os.makedirs(os.path.dirname(a.init) or '.', exist_ok=True)
    with open(a.init, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow([k for k, _ in FIELDS])
        w.writerow(['TODO'] * len(FIELDS))
    print(f'已生成破坏/连锁表: {a.init}')
    print('\n⚠️ 十九域：dest / support / debris / nav / hole / persist / '
          'elem / prop / wind / resid / rope / iter / swing / tangle / '
          'rng / when / scope / amb / g7')
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
    print(f'破坏/连锁 · {len(rows)} 条')
    print('=' * 76)
    if mismatch:
        print(f'\n🚫 **不一致** {len(mismatch)} 条（行 {mismatch[:15]}）')
    if no_legacy:
        print(f'\n❌ {len(no_legacy)} 条缺**原版值**（行 {no_legacy[:15]}）')
    if no_tol:
        print(f'\n🚫 {len(no_tol)} 条缺**允许偏差**（行 {no_tol[:15]}）')
    if no_grade:
        print(f'\n🚫 {len(no_grade)} 条**证据等级缺失或 ≥7 级**'
              f'（行 {no_grade[:15]}）')

    if not (mismatch or no_legacy or no_tol or no_grade):
        print('\n✅ 破坏/连锁：一致、原版值完整、偏差已声明、证据达标')

    print('\n🔑 **A/C/D 决定旧技巧路线与社区刷取习惯是否仍然成立——P0。**')
    print('   **只迁移「刚度 0.8」而不迁移约束类型与迭代预算，结果不可预测。**')
    print('   **RNG 固化时机比「是否固化」更隐蔽；决策必须由产品层显式作出。**')
    return 1 if (a.gate_check and
                 (mismatch or no_legacy or no_tol or no_grade)) else 0


def main():
    ap = argparse.ArgumentParser(description='可破坏世界与连锁反应')
    ap.add_argument('--dest', action='store_true')
    ap.add_argument('--support', action='store_true')
    ap.add_argument('--debris', action='store_true')
    ap.add_argument('--nav', action='store_true')
    ap.add_argument('--hole', action='store_true')
    ap.add_argument('--persist', action='store_true')
    ap.add_argument('--elem', action='store_true')
    ap.add_argument('--prop', action='store_true')
    ap.add_argument('--wind', action='store_true')
    ap.add_argument('--resid', action='store_true')
    ap.add_argument('--rope', action='store_true')
    ap.add_argument('--iter', action='store_true')
    ap.add_argument('--swing', action='store_true')
    ap.add_argument('--tangle', action='store_true')
    ap.add_argument('--rng', action='store_true')
    ap.add_argument('--when', action='store_true')
    ap.add_argument('--scope', action='store_true')
    ap.add_argument('--amb', action='store_true')
    ap.add_argument('--g7', action='store_true')
    ap.add_argument('--init')
    ap.add_argument('--check')
    ap.add_argument('--gate-check', action='store_true')
    a = ap.parse_args()
    fns = {'dest': cmd_dest, 'support': cmd_support, 'debris': cmd_debris,
           'nav': cmd_nav, 'hole': cmd_hole, 'persist': cmd_persist,
           'elem': cmd_elem, 'prop': cmd_prop, 'wind': cmd_wind,
           'resid': cmd_resid, 'rope': cmd_rope, 'iter': cmd_iter,
           'swing': cmd_swing, 'tangle': cmd_tangle, 'rng': cmd_rng,
           'when': cmd_when, 'scope': cmd_scope, 'amb': cmd_amb,
           'g7': cmd_g7}
    for k, fn in fns.items():
        if getattr(a, k):
            return fn(a)
    if a.init:
        return cmd_init(a)
    if a.check:
        return cmd_check(a)
    print('❌ 需要 --dest / --support / --debris / --nav / --hole / '
          '--persist / --elem / --prop / --wind / --resid / --rope / '
          '--iter / --swing / --tangle / --rng / --when / --scope / '
          '--amb / --g7 / --init / --check 之一')
    return 2


if __name__ == '__main__':
    sys.exit(main())
