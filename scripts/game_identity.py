#!/usr/bin/env python3
"""同形异质 · 个人操作方言 · 意外组合 · 游戏惯例污染 · 挂机契约 ·
失败美学 · 现实时间礼物（第四十四轮 A–G，含 H 八项）。

**🔑 本轮的视角切换**：
> 本轮新增的不是另一条"系统清单"，而是三个此前**未成型的取证维度**：

| 维度 | 问的是什么 |
|---|---|
| **实体身份** | **看起来是同一个东西，内部却不是同一个东西** |
| **动作语义** | 🔑 **按键序列不再是唯一事实，时序与解释才决定结果** |
| **玩家契约** | 挂机 · 失败 · 现实日历**都是被玩家记住的承诺** |

🔑 **名称只是标签，身份才是契约。**

用法:
  game_identity.py --same    # 🔑 **同形异质六类**
  game_identity.py --id      # **ID 四层**
  game_identity.py --slot    # 🔑 **整理背包也可能改变结果**
  game_identity.py --phrase  # 🔑 **个人操作方言＝动作短语**
  game_identity.py --window  # **缓冲/取消窗口的双向陷阱**
  game_identity.py --invalid # 🔑 **"无效输入"的预期结果**
  game_identity.py --combo   # 🔑 **意外组合（系统接缝）**
  game_identity.py --seam    # **八个接缝**
  game_identity.py --conv    # 🔑 **游戏惯例污染**
  game_identity.py --idle    # **挂机不是漏洞，是计时与收益契约**
  game_identity.py --defeat  # 🔑 **输得好看**
  game_identity.py --cal     # 🔑 **现实时间礼物**
  game_identity.py --h       # H 类八项
  game_identity.py --init ledger/identity.csv
  game_identity.py --check ledger/identity.csv --gate

退出码: 0 通过 / 1 缺项 / 2 用法错误
"""
import argparse
import csv
import os
import sys

# 🔑 A 同形异质
SAME_RULE = '🔑 **名称只是标签，身份才是契约。**'
SAME_WHY = '🔑 此前的"数据布局"覆盖序列化与字段迁移，"物品生命周期"覆盖'
'获得 · 使用 · 交易 · 消耗 · 销毁，🔴 **却未覆盖"两个视觉相同对象'
'是否可被玩家视为同一对象"**'
SAME_EG = '🔑 原版中 `item_id` 相同**既可能表示同一原型，也可能只是同一贴图索引**；'
'背包第 1 格与第 5 格的同名剑可能共享定义，却拥有**不同生成种子 · 来源任务 · '
'前任持有者 · 强化次数 · 破损状态 · 诅咒状态 · 可交易标记 · 是否被鉴定 · '
'是否被祝福 · 玩家备注 · 商店刷新序号**'
SAME_WARN = '🔴 **若重制把背包压缩为"按定义去重＋数量"，'
'就消灭了玩家记得的每一把剑。**'

SIX_KINDS = [
    ('**同名异义**', '两把同名剑 · 两个同名 NPC · 两条同名任务 —— '
     '由本地化别名 · 版本遗留 · 内容复用产生'),
    ('**同 ID 异实例**', '同一 `item_id` 但**实例来源 · 状态 · 附着物不同**；'
     '🔴 重制必须保留稳定的 `instance_id`，'
     '**不能让合成 · 整理 · 跨档迁移改变身份**'),
    ('**同名异版本**', '补丁未改显示名却改变**伤害 · 交互半径 · '
     '可破坏条件 · 消耗规则**；必须有 `content_version` 与版本化定义快照'),
    ('**图标同而行为异**', '🔑 原版用**颜色 · 角标 · 动画以外**的视觉提示承载同一性；'
     '🔴 复刻后**高分辨率 · 自动图集 · 统一图标反而抹平差异**'),
    ('**外观异而行为同**', '不同皮肤 · 地区版 · 重制模型对应同一原型；'
     '🔑 **玩家会误以为存在玩法差异** —— '
     '🔴 不能靠图标生成等效性结论'),
    ('**原版别名**', '🔑 同一实体被**内部表 · 脚本 · UI · 日志用不同字符串引用**；'
     '🔴 复刻若统一成一个名字，会让**老攻略 · 速通分类 · 模组配置 · '
     '调试录像同时失效**'),
]

ID_FOUR = [
    ('`definition_id`', '**不可变**的定义键'),
    ('`definition_snapshot_id`', '**内容版本化**的定义快照'),
    ('`entity_id`', '**跨会话稳定**的实体键'),
    ('`container_slot_id`', '**运行时短暂**的槽位键'),
]
ID_RULE = '🔑 **显示名只能从定义派生，不能反向成为主键。**'
ID_SPEC = '🔑 限定 ID（类型前缀 + 原型号，用于区分同名不同类物品）'
'应作为**最低规范，而不是足够规范** —— 兼容历史会让"唯一 ID"无法一蹴而就'

SLOT_RULE = '🔑 **整理背包也可能改变结果。**'
SLOT_EG = '🔑 玩家可能把**低耐久武器固定放第 1 格**作为"备用"、'
'第 5 格作为"当前武器"；🔴 **若自动排序 · 堆叠 · 跨容器压缩 · '
'存档重写槽位，原本可靠的记忆顺序就失效**'
SLOT_NOTE = '🔑 **`slot` 不是身份**，但槽位本身可能是**玩家可观察状态** —— '
'应记为 `observed_slot_history`，🔴 **不能复用 `instance_id`**'

MIGRATION_RULE = '🔑 **"迁移成功"和"玩家世界不变"不是一回事。**'
MIGRATION_FACTS = [
    '允许**原型改名/替换**与**运行时状态迁移**两类迁移',
    '存档**按名称记录已应用的迁移**且不会重复执行',
    '🔑 **JSON 迁移在地图加载时批量执行，且先于 Lua 迁移**',
    '🔴 **Ghost 实体在类型变化或不可建造时会被移除而不是保留**',
]
MIGRATION_GATE = '🔑 迁移门必须**分别报告**："定义可映射" · "实例可映射" · '
'**"幽灵/预览对象被删除"** · "旧名称无法归属"，🔴 **不能只报成功**'

IDENTITY_FIELDS = [
    ('`canonical_identity_triple`', '原版怎样判断两个对象相同？',
     '**定义键 + 实例键 + 内容版本相等才等价**'),
    ('`visual_identity`', '图标 · 名称 · 模型 · 颜色哪个承载同一性？',
     '**逐像素/逐音效 + 玩家术语交叉验证**'),
    ('`transfer_semantics`', '交易 · 丢弃 · 整理 · 跨容器是否保持实例？',
     '**搬运前后 `instance_id` 不变**'),
    ('`historical_provenance`', '来源 · 前任持有者 · 生成时间是否参与系统？',
     '**涉及任务 · 鉴定 · 诅咒时不得丢弃**'),
    ('`legacy_aliases`', '内部 · 脚本 · UI · 日志如何称呼它？',
     '**至少记录 3 种引用路径**'),
    ('`migration_status`', '旧档加载后是否创建新实例？',
     '**新实例必须标记 `remaster_born`**'),
]

# 🔑 B 个人方言
PHRASE_RULE = '🔑 **个人方言是动作序列 · 相对时序与失败恢复方式，不是键位表。**'
PHRASE_WHAT = '🔑 玩家发展出的"**先跳后攻**"·"**按住方向时延迟一帧取消**"·'
'"**连点三次以抢窗口**"·"**进菜单前先放技能**"·"**撞墙两下再转身**"·'
'"**按住交互键经过一串机关**" —— 🔑 **是把原版特定帧时序 · 缓冲 · 取消 · '
'动画锁定 · 状态机变成身体记忆**'
PHRASE_KEY = '🔑 **键位重映射只解决"E 还是 F"，'
'不解决"提前 4 帧按下是否还有效"。**'
PHRASE_WARN = '🔴 重制若改变**输入采样点 · 缓冲长度 · 前摇 · 取消条件 · '
'动画事件 · 帧率**，🔑 **玩家说出的"还是原来的操作"就不成立**'

PHRASE_FIELDS = [
    '逻辑动作', '**设备原始事件**', '**时间戳**',
    '**相对于上一动作/动画事件的偏移**', '**上下文栈**',
    '**是否被消费**', '**最终是否进入命令队列**',
]
PHRASE_LAYER = '🔑 输入层先产生 `raw_input` → 归一化为 `intent` → '
'由时序规则变成 `command` → 由状态机决定是否接受'
PHRASE_KEEP = '🔑 **必须保留 `intent` 与 `command` 的分离** —— '
'例如"跳＋攻击"可以是**两个并发意图**，也可能因原版事件消费规则'
'**变成一个组合命令**'

WINDOW_DIMS = [
    ('**缓冲窗口**', '最早可提前多少输入？过期是否保留？',
     '毫秒/帧误差带；**连续 100 次重放相同**'),
    ('**取消窗口**', '哪个动画事件后允许取消？',
     '🔑 **事件标签而非固定时间**；同 seed 同结果'),
    ('**冲突仲裁**', '同帧多个动作谁赢？', '**原版优先级表逐条回放**'),
    ('**长按语义**', '阈值 · 首帧 · 重复频率 · 释放沿',
     '**低电量手柄与按键粘连下一致**'),
    ('**状态清除**', '菜单打开/暂停/切换场景是否清缓冲？',
     '**与原版逐状态比对**'),
    ('**短语粒度**', '单键 · 双击 · 方向序列 · 节奏？',
     '🔑 **保存原始事件流，不保存"高级意图"**'),
]
WINDOW_TRAP = '🔑 **100–200 ms 的现代缓冲可能改善新手，却破坏高玩方言。**'
'原版也许只允许 1 帧缓冲，玩家据此发展出精确节奏；'
'🔑 **若新引擎加长缓冲，玩家会觉得操作"变滑"·"指令自动发生"**；'
'🔑 相反，原版若本就宽缓冲而新引擎按固定帧采样，则显得更硬'
WINDOW_RIGHT = '🔑 正确流程**不是选宽或严**，而是把**窗口数值 · 事件处理顺序 · '
'未决输入是否带时间戳 · 暂停期间是否继续计时**全部录成证据'

INVALID_RULE = '🔑 **必须记录"无效输入"的预期结果。**'
INVALID_EG = [
    '**连续按两次是否无响应**',
    '**在锁定窗口按攻击是否消耗输入**',
    '**菜单中按跳是否导致离开菜单后立刻跳**',
]
INVALID_WARN = '🔴 **若重制把无效输入静默吞掉或自动改为有效输入，'
'都会破坏玩家原有的恢复节奏。**'
INVALID_MATCH = '🔑 这里 `must-match` 的对象**不是"命令成功"，'
'而是"**输入被拒绝时的副作用是否相同**"**'

# 🔑 C 意外组合
COMBO_RULE = '🔑 **意外组合技是系统接口 · 帧时序与副作用顺序的副产品，'
'不是可逐项测试的单一功能。**'
COMBO_EG = '技能 A 作用于地形 B · 道具 C 改变怪物 D 的状态 · '
'**怪物死亡事件与掉落队列碰撞** · **存档瞬间切换区域** · '
'**低帧暂停使定时器一次性累加**'
COMBO_WHY = '🔑 前轮已覆盖涌现与 OOB，🔴 **仍未覆盖"两个原本独立系统'
'因副作用链而耦合"** —— 复刻**按系统分模块测试会天然漏掉**'

SEAM_EIGHT = [
    '**① 事件顺序**：A 系统先结算还是 B 系统先结算',
    '**② 帧边界**：两事件同帧或跨帧结果不同',
    '**③ 延迟执行**：协程 · 消息队列 · 物理回调何时落地',
    '**④ 状态所有权**：实体拥有状态还是世界拥有状态',
    '**⑤ 读写竞争**：一个系统读旧值，另一个已写新值',
    '**⑥ 对象生命周期**：临时实体死亡后引用是否仍有效',
    '**⑦ 跨场景边界**：对象迁移 · 引用重定向',
    '**⑧ 难度/模式分支**：同一组合在简单 · 普通 · 硬核 · 新游戏中结果不同',
]
COMBO_TABLE = [
    ('**技能 × 地形**', '冰面/梯子/浅水改变技能碰撞',
     '地形改用新碰撞层后组合消失'),
    ('**道具 × 怪物状态**', '眩晕 · 燃烧 · 倒地帧接受不同伤害',
     '状态机重排后命中窗口变化'),
    ('**AI × 世界规则**', '仇恨刷新与天气/音乐触发同步',
     'AI 重做后社区路线不成立'),
    ('**存档 × 迁移**', '跨区切换时保存临时实体',
     '临时对象被序列化或丢失'),
    ('**物理 × 动画**', '动画根运动与击退/绳索事件耦合',
     '根运动来源改变，位移不同'),
    ('**UI × 战斗**', '菜单打开冻结时间但不冻结计时器',
     '🔑 **原版冻结范围不一致**'),
    ('**网络 × 单机**', '单机时序被网络回滚重排',
     '回滚策略改变单机结果'),
    ('**生成 × 内容**', '种子 · 权重 · 房间模板决定社区路线',
     '新生成管线让旧 seed 失效'),
]
COMBO_ASSET = '🔑 **社区组合技必须被当成一等资产，而不是"bug 列表"。**'
COMBO_SRC = '取证来源：**速通录像 · Wiki 的"技巧/机制/版本差异" · '
'论坛异常报告 · 旧版本补丁说明 · 开发者直播口误**'
COMBO_RECORD = '🔑 每个组合建 `discovery_date` · 最早录像 · 依赖版本 · '
'**帧精确步骤** · 成功率 · **是否依赖设备/帧率** · 是否被补丁修复 · '
'是否用于分类规则'
COMBO_THREE = [
    ('`must_match`', '**必须复现**'),
    ('`intentional_divergence`', '设计者明知并文档化'),
    ('`unintended_preserved`', '🔑 **原版未计划但社区已形成契约** —— '
     '🔴 **应由项目裁决，而非程序员默认删除**'),
]

# 🔑 D 惯例
CONV_RULE = '🔑 **跨游戏惯例与游戏内常识不是同一层。**'
CONV_DIFF = '🔑 第 42 轮关注**现实世界常识**（门能推开 · 水会灭火）；'
'本轮关注**玩家从其他游戏带入的元知识**：WASD 移动 · E 交互 · Esc 菜单 · '
'右键瞄准 · **黄色可拾取** · **血条在左上** · **闪红代表受伤** · '
'传送点可反复使用'
CONV_WARN = '🔑 **惯例越稳定，偏离越容易被视为 bug。**'
'原版若用 **Q 交互 · 右键近战 · 血条在右下**，🔑 **那不是"落后"，而是身份**'
CONV_TWO = '🔑 复刻应维护"**惯例层**"与"**原版层**"，'
'🔴 **不能二选一后静默覆盖**'
CONV_FIELDS = [
    '该品类**常见默认**', '**原版实际默认**', '**目标平台现代默认**',
    '**偏离风险等级**', '**是否允许双方案**', '**UI 图标如何随方案更新**',
]
CONV_TR = '🔑 **可吸收**：双控制方案 + 明确切换；'
'🔴 **不可吸收**：把现代方案当唯一默认 + **默认删除原版可达动作**。'
'例：某重制版支持切换 Tank/现代控制，但**侧步与后撤步在现代方案不可用**，'
'抓边 · 侧翻/后翻 · 天鹅潜仍需特定原版组合'
CONV_CONFLICT = '🔑 若只做现代控制，玩家带入的"E 必是交互"预期'
'可能与原版"**攻击键靠近可拾取**"的语义冲突；'
'若只做原版键位，新平台用户又会抱怨"不符合预期"。'
'🔑 正确解法：**原版为 must-match + 明确命名的现代层并列**'

# 🔑 E 挂机
IDLE_RULE = '🔑 **挂机不是漏洞，而是计时与收益契约。**'
IDLE_ASK = [
    '原版是否**容忍**挂机？是否有收益？是否有惩罚？',
    '🔴 重制若加入**反挂机机制**（在线时长奖励 · 疲劳值），'
    '或**移除挂机收益**',
    '**"离线收益"的设计契约**是什么？',
]
IDLE_ANCHOR = '🔑 离线补算应以 `SystemTime` · 当前 `GameTime` · `ContentId`'
'为锚点，🔑 **恢复时按过期计时器顺序补偿**'

# 🔑 F 失败美学
DEFEAT_RULE = '🔑 **失败演出是连续情绪曲线，不是可以跳过的 UI。**'
DEFEAT_ITEMS = [
    '**死亡动画**', '**失败演出**', '**Game Over 画面**', '**重开提示**',
]
DEFEAT_ASK = [
    '🔑 原版失败时的**尊严**：是嘲讽 · 鼓励 · 黑色幽默 · 还是冷漠？',
    '🔴 重制若"优化"掉失败演出（快速重开 · 跳过 Game Over）',
    '🔑 **"输得好看"是体验的一部分** —— '
    '**连续失败 20 次时的情绪曲线**',
]
DEFEAT_AUD = '🔑 还需区分"**谁看见**"：失败提示可能**只给玩家 · 只给队友 · '
'只写日志 · 只展示给开发者** —— 增 `explanation_audience`'

# 🔑 G 现实时间
CAL_RULE = '🔑 **错过的稀缺性本身就是内容。**'
CAL_ITEMS = [
    '节假日 · 周年 · 季节 · **现实日期触发的内容**（圣诞皮肤 · 万圣活动）',
    '**限时内容的"错过即永久"**',
    '🔑 **现实时间 vs 游戏时间**的绑定',
    '🔑 玩家对"**错过了 2013 年圣诞活动**"的记忆',
]
CAL_SERVER = '🔑 应以**服务器时间**为准，🔑 **并明确设备时间篡改风险**'
CAL_REVIVE = '🔴 **重制若复活已绝版内容，是否改变稀缺性？** —— '
'这是必须显式裁决的问题，不是"补全彩蛋"'
CAL_GHOST = '🔑 服务器关闭后，现实时间内容会变成**不可再生幽灵**：'
'`entitlement_source` · `server_time_source` · `content_delivery_source`'
'可能全部失效。要决定**重新授权 · 模拟日期 · 保留空位 · 明确不再提供**'

H_EIGHT = [
    ('**H1 程序生成的"同一性"**', '🔑 前轮覆盖流式与生成，未覆盖'
     '**玩家如何称呼与识别随机产物**：同一 seed 是否保证相同房间 · 洞窟 · '
     '刷怪点 · 物品修饰词？社区会记录"**7 号洞**""**狗洞**"'
     '"**无限刷怪房**""**双宝箱 seed**"。'
     '🔴 重刻若换**噪声 · 排序 · 浮点精度 · 容器迭代 · 并行生成 · '
     '资产加载顺序**，外观可能近似，**身份却变化**。增 `seed_contract`'),
    ('**H2 事件/录像指纹只覆盖存证，不覆盖玩家命名**',
     '🔑 玩家把"录像"称为"**回放**""**demo**""**影分身**"。'
     '取证应同时保存**引擎内部标签 · 平台标签 · 玩家术语 · 社区分类**；'
     '🔴 **不得统一术语后误判老资料**'),
    ('**H3 提示系统与原版键位的双语言问题**',
     '🔑 原版方案说"按 X"，现代方案说"按方块"，**提示表可能错配**。'
     '增 `prompt_binding`：提示绑定**稳定动作 · 当前方案 · '
     '当前设备图标 · 方案版本**，并对每个方案生成**完整提示覆盖报告**'),
    ('**H4 现代辅助默认会改变"发现难度"**',
     '🔑 自动拾取 · 路径提示 · 敌人血条 · 伤害数字 · 战斗暂停 · 目标标记'
     '能提高可访问性，🔴 **但也可能消灭原版刻意保留的模糊与风险**。'
     '🔑 **应逐条列出，不整体归入"无障碍优化"**'),
    ('**H5 社区规则会因补丁内爆**',
     '🔑 补丁修复 A 系统 → 依赖 A 的组合失效 → 社区寻找 B 系统替代；'
     '分类规则 · 速通指南 · 奖杯路线会**同时出现旧版与新版**。'
     '版本差异文档需记**机制快照 · 依赖组合 · 规则生效日期 · 录像兼容性**'),
    ('**H6 服务器关闭后，现实时间内容变成不可再生幽灵**',
     '🔑 重点是**技术可触发性**：服务器时间 · 活动配置 · CDN 资源 · '
     '账号资格可能全部失效。记 `entitlement_source` · '
     '`server_time_source` · `content_delivery_source`'),
    ('**H7 控制可发现性**',
     '🔑 原版可能通过**试错 · 手册 · 关卡教学 · 隐藏交互**让玩家发现动作；'
     '🔴 **重刻若默认显示全部键位，会消灭发现**。'
     '应分别记录"**玩家初始已知**""**教学后已知**""**只有探索/外部资料知道**"'),
    ('**H8 失败可解释性还需区分"谁看见"**',
     '🔑 第 42 轮覆盖四级解释；本轮补：同一失败在**玩家 · 队友 · '
     '日志 · 开发者**的可见性不同 —— 增 `explanation_audience`'),
]

CONFLICTS = [
    '❌ **统一物品命名**（消灭别名 · 同名异义 · 跨版本引用）',
    '❌ **自动把原版键位改成 WASD / E / 右键瞄准**',
    '❌ **默认移除缓冲或默认加宽缓冲**（🔴 无原版时序证据时两者都是擅自偏离）',
    '❌ **默认修复"bug 组合技"**（破坏社区契约）',
    '❌ **默认反挂机 / 在线奖励**（改变闲置玩法契约）',
    '❌ **默认跳过失败演出 / 快速重试**（压缩失败美学）',
    '❌ **默认用本地时钟触发活动**（时间篡改改变稀缺性）',
    '❌ **默认让绝版内容常驻**（改写历史身份）',
    '❌ **统一控制提示术语**（破坏双方案覆盖）',
    '❌ **默认开启全面辅助提示**（可能消灭原版发现难度）',
    '❌ 把背包压缩为"按定义去重 + 数量"',
    '❌ **靠图标生成等效性结论**',
    '❌ **把 Ghost 实体删除作为静默默认**',
    '❌ **把现代控制方案当唯一默认并删除原版可达动作**',
]

FIELDS = [
    ('item_id', '项编号'),
    ('domain', '域（same / id / slot / phrase / window / invalid / combo / '
               'seam / conv / idle / defeat / cal / h）'),
    ('legacy_value', '**原版值**'),
    ('new_value', '新引擎值'),
    ('match', '**是否一致**'),
    ('identity_or_timing', '**身份层 / 时序层证据**'),
    ('evidence', '证据等级 1-8'),
]


def _hdr(t, w=80):
    print('=' * w)
    print(t)
    print('=' * w)


def cmd_same(a):
    _hdr('🔑 同形异质（**名称只是标签，身份才是契约**）')
    print(f'   {SAME_RULE}')
    print(f'\n   {SAME_WHY}')
    print(f'\n   {SAME_EG}')
    print(f'\n   {SAME_WARN}')
    print('\n六类:')
    for k, v in SIX_KINDS:
        print(f'   {k:<22} {v}')
    return 0


def cmd_id(a):
    _hdr('ID 四层')
    for k, v in ID_FOUR:
        print(f'   {k:<26} {v}')
    print(f'\n   {ID_RULE}')
    print(f'\n   {ID_SPEC}')
    print('\n字段 / 取证问题 / 断言:')
    for k, q, asrt in IDENTITY_FIELDS:
        print(f'   {k:<28}')
        print(f'       问: {q}')
        print(f'       断言: {asrt}')
    print(f'\n   {MIGRATION_RULE}')
    print('\n迁移事实:')
    for m in MIGRATION_FACTS:
        print(f'   · {m}')
    print(f'\n   {MIGRATION_GATE}')
    return 0


def cmd_slot(a):
    _hdr('🔑 槽位（**整理背包也可能改变结果**）')
    print(f'   {SLOT_RULE}')
    print(f'\n   {SLOT_EG}')
    print(f'\n   {SLOT_NOTE}')
    return 0


def cmd_phrase(a):
    _hdr('🔑 个人操作方言（**动作短语**）')
    print(f'   {PHRASE_RULE}')
    print(f'\n   {PHRASE_WHAT}')
    print(f'\n   {PHRASE_KEY}')
    print(f'\n   {PHRASE_WARN}')
    print('\n一个短语应含: ' + ' · '.join(PHRASE_FIELDS))
    print(f'\n   {PHRASE_LAYER}')
    print(f'\n   {PHRASE_KEEP}')
    return 0


def cmd_window(a):
    _hdr('窗口（**双向陷阱**）')
    print('\n| 维度 | 原版取证 | 新引擎门禁 |')
    print('\n六维:')
    for k, q, g in WINDOW_DIMS:
        print(f'   {k:<14}')
        print(f'       取证: {q}')
        print(f'       门禁: {g}')
    print(f'\n   {WINDOW_TRAP}')
    print(f'\n   {WINDOW_RIGHT}')
    return 0


def cmd_invalid(a):
    _hdr('🔑 无效输入（**被拒绝时的副作用**）')
    print(f'   {INVALID_RULE}')
    print('\n例子:')
    for e in INVALID_EG:
        print(f'   · {e}')
    print(f'\n   {INVALID_WARN}')
    print(f'\n   {INVALID_MATCH}')
    return 0


def cmd_combo(a):
    _hdr('🔑 意外组合（**玩家发现的是系统接缝**）')
    print(f'   {COMBO_RULE}')
    print(f'\n   {COMBO_EG}')
    print(f'\n   {COMBO_WHY}')
    print(f'\n   {COMBO_ASSET}')
    print(f'\n   {COMBO_SRC}')
    print(f'\n   {COMBO_RECORD}')
    print('\n三级分类:')
    for k, v in COMBO_THREE:
        print(f'   {k:<26} {v}')
    print('\n组合类型 / 取证样例 / 失败方式:')
    for k, s, f in COMBO_TABLE:
        print(f'   {k:<18}')
        print(f'       样例: {s}')
        print(f'       失败: {f}')
    return 0


def cmd_seam(a):
    _hdr('八个接缝')
    for s in SEAM_EIGHT:
        print(f'   · {s}')
    return 0


def cmd_conv(a):
    _hdr('🔑 游戏惯例污染（**现代默认值会无声改写原版反惯例**）')
    print(f'   {CONV_RULE}')
    print(f'\n   {CONV_DIFF}')
    print(f'\n   {CONV_WARN}')
    print(f'\n   {CONV_TWO}')
    print('\n字段: ' + ' · '.join(CONV_FIELDS))
    print(f'\n   {CONV_TR}')
    print(f'\n   {CONV_CONFLICT}')
    return 0


def cmd_idle(a):
    _hdr('🔑 挂机（**不是漏洞，是计时与收益契约**）')
    print(f'   {IDLE_RULE}')
    print('\n必答:')
    for i in IDLE_ASK:
        print(f'   · {i}')
    print(f'\n   {IDLE_ANCHOR}')
    return 0


def cmd_defeat(a):
    _hdr('🔑 输得好看（**失败美学**）')
    print(f'   {DEFEAT_RULE}')
    print('\n内容: ' + ' · '.join(DEFEAT_ITEMS))
    print('\n必答:')
    for d in DEFEAT_ASK:
        print(f'   · {d}')
    print(f'\n   {DEFEAT_AUD}')
    return 0


def cmd_cal(a):
    _hdr('🔑 现实时间礼物（**错过的稀缺性本身就是内容**）')
    print(f'   {CAL_RULE}')
    print('\n内容: ' + ' · '.join(CAL_ITEMS))
    print(f'\n   {CAL_SERVER}')
    print(f'\n   {CAL_REVIVE}')
    print(f'\n   {CAL_GHOST}')
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
    print(f'已生成身份/时序表: {a.init}')
    print('\n⚠️ 十三域：same / id / slot / phrase / window / invalid / '
          'combo / seam / conv / idle / defeat / cal / h')
    print('\n⚠️ `identity_or_timing` 列＝**身份层 / 时序层证据**')
    print('\n🔑 八份新模板：entity_identity · input_phrase · '
          'system_coupling · convention_layer · idle_contract · '
          'defeat_sequence · calendar_event · compatibility_oath')
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

    mismatch, no_legacy, no_idt, no_grade = [], [], [], []
    for i, r in enumerate(rows, 1):
        m = g(r, 'match').lower()
        if m not in ('yes', 'y', 'true', '是', '一致'):
            mismatch.append(i)
        if not g(r, 'legacy_value') or g(r, 'legacy_value') == 'TODO':
            no_legacy.append(i)
        p = g(r, 'identity_or_timing')
        if not p or p == 'TODO':
            no_idt.append(i)
        ev = g(r, 'evidence')
        if not ev or ev == 'TODO':
            no_grade.append(i)
        else:
            d = ev.split('.')[0].strip()
            if d.isdigit() and int(d) >= 7:
                no_grade.append(i)

    print('=' * 76)
    print(f'身份与时序 · {len(rows)} 条')
    print('=' * 76)
    if mismatch:
        print(f'\n🚫 **不一致** {len(mismatch)} 条（行 {mismatch[:15]}）')
    if no_legacy:
        print(f'\n❌ {len(no_legacy)} 条缺**原版值**（行 {no_legacy[:15]}）')
    if no_idt:
        print(f'\n🚫 {len(no_idt)} 条缺**身份层/时序层证据**'
              f'（行 {no_idt[:15]}）')
    if no_grade:
        print(f'\n🚫 {len(no_grade)} 条**证据等级缺失或 ≥7 级**'
              f'（行 {no_grade[:15]}）')

    if not (mismatch or no_legacy or no_idt or no_grade):
        print('\n✅ 身份与时序：一致、原版值完整、身份/时序已验证、证据达标')

    print('\n🔑 **名称只是标签，身份才是契约。**')
    print('   🔴 **把背包压缩为「按定义去重＋数量」，'
          '就消灭了玩家记得的每一把剑。**')
    print('   🔑 **键位重映射只解决"E 还是 F"，'
          '不解决"提前 4 帧按下是否还有效"。**')
    print('   🔑 **社区组合技是一等资产，不是 bug 列表。**')
    return 1 if (a.gate_check and
                 (mismatch or no_legacy or no_idt or no_grade)) else 0


def main():
    ap = argparse.ArgumentParser(description='身份与时序：同形异质/方言/组合')
    ap.add_argument('--same', action='store_true')
    ap.add_argument('--id', action='store_true')
    ap.add_argument('--slot', action='store_true')
    ap.add_argument('--phrase', action='store_true')
    ap.add_argument('--window', action='store_true')
    ap.add_argument('--invalid', action='store_true')
    ap.add_argument('--combo', action='store_true')
    ap.add_argument('--seam', action='store_true')
    ap.add_argument('--conv', action='store_true')
    ap.add_argument('--idle', action='store_true')
    ap.add_argument('--defeat', action='store_true')
    ap.add_argument('--cal', action='store_true')
    ap.add_argument('--h', action='store_true')
    ap.add_argument('--init')
    ap.add_argument('--check')
    ap.add_argument('--gate-check', action='store_true')
    a = ap.parse_args()
    fns = {'same': cmd_same, 'id': cmd_id, 'slot': cmd_slot,
           'phrase': cmd_phrase, 'window': cmd_window, 'invalid': cmd_invalid,
           'combo': cmd_combo, 'seam': cmd_seam, 'conv': cmd_conv,
           'idle': cmd_idle, 'defeat': cmd_defeat, 'cal': cmd_cal, 'h': cmd_h}
    for k, fn in fns.items():
        if getattr(a, k):
            return fn(a)
    if a.init:
        return cmd_init(a)
    if a.check:
        return cmd_check(a)
    print('❌ 需要 --same / --id / --slot / --phrase / --window / --invalid / '
          '--combo / --seam / --conv / --idle / --defeat / --cal / --h / '
          '--init / --check 之一')
    return 2


if __name__ == '__main__':
    sys.exit(main())
