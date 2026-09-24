#!/usr/bin/env python3
"""时间预算 · 拟人化 · 文化层 · 元收藏 · 展示与删除权 · 精通曲线 ·
第三空间（第四十七轮 A–G，含 H 七项）。

**🔑 本轮的核心不是"再加一套功能"，而是补齐四层像素级记录**：
🔑 **玩家把游戏嵌入生活 · 把系统当人 · 把文化符号当语义 ·
把整理与展示当仪式**。

🔑 最该记住的三句：
- 🔑 **"打完这个 BOSS 就睡"之所以危险，是因为 BOSS 战同时改变了
  剩余时间预期 · 失败重试成本 · 自动存档边界 · 下一段可退出节点。**
- 🔑 **玩家容忍不可预测，却不容忍结果无法归因。** 🔴 **"黑箱更公平"是错误推论。**
- 🔑 **排序"更科学"并不比"和原版一致"更正确。**
  🔴 **不能用稳定排序悄然取代原版的未定义顺序。**

用法:
  game_life.py --budget  # 🔑 **时间预算（管理的是会话承诺，不是时长）**
  game_life.py --exit    # 🔑 **退出尾部（决定退出到桌面之间的每一步）**
  game_life.py --pause   # **可暂停性取决于系统能否冻结，不是按钮存在**
  game_life.py --persona # 🔑 **拟人化（公平感的承重变量是归因链）**
  game_life.py --rng     # **七类受控随机通道**
  game_life.py --culture # 🔑 **文化层（不是文本外包问题）**
  game_life.py --sort    # 🔑 **元收藏（排序稳定性是首要 must-match）**
  game_life.py --name    # **命名截断契约**
  game_life.py --show    # **展示与删除权**
  game_life.py --master  # **精通曲线（可见进步信号本身就是系统）**
  game_life.py --third   # 🔑 **第三空间（不是低效率空间）**
  game_life.py --h       # H 类七项
  game_life.py --init ledger/life.csv
  game_life.py --check ledger/life.csv --gate

退出码: 0 通过 / 1 缺项 / 2 用法错误
"""
import argparse
import csv
import os
import sys

# 🔑 A 时间预算
BUDGET_RULE = '🔑 **A 类事实：玩家真正管理的不是游戏时长，'
'而是一段正在进行的会话承诺。**'
BOSS_RULE = '🔑 **"打完这个 BOSS 就睡"之所以危险，是因为 BOSS 战同时改变了'
'剩余时间预期 · 失败重试成本 · 自动存档边界 · 下一段可退出节点。**'
BUDGET_REC = '🔑 重制必须记录**从玩家决定退出到实际回到设备桌面**之间的'
'每一处**等待 · 确认 · 上传 · 重启 · 登录 · 界面层级**，'
'🔴 **不能只记录单局时长**'
SESSION_CURVE = ['**会话入口**（冷启动/恢复/每日奖励/匹配/活动提醒）',
                 '**开始摩擦**（启动时长/EULA/登录/协议同步/补丁/反作弊）',
                 '**可玩边界**（每帧可接受输入/首个可操作时刻/首个有意义选择）',
                 '**存档承诺**（触发条件/显式提示/实际落盘/崩溃恢复）',
                 '**退出承诺**（可暂停状态/确认层级/异步上传/重开冷却）',
                 '**会话尾部**（退出动画/排行榜同步/云上传/最终设备控制权）',
                 '**下一会话**（默认焦点/上下文恢复/待办提示）']
GOLDEN = '🔑 黄金录像：22:47 完成小目标 → "章节结束并自动保存" → 发生 BOSS 战；'
'比较**输入次数 · 时间 · 存档完整性 · 重入状态**'
SAVE_DENSITY = '🔑 **存档点密度不是均匀铺开，而是把承诺控制在可预期范围内** —— '
'手动保存 · 自动保存 · 检查点 · 场景边界 · 到达安全区 · 完成交易 · '
'拾取确认 · 进入结算 · **进程退出保存**'
SAVE_WINDOW = '🔑 每个存档点的**不可中断窗口**：进入 BOSS 前能否手动存档 · '
'失败后是否回到 BOSS 前 · 是否在播片中途 · 是否在读取动画期间 · '
'**退出后是否回到同一检查点**'
PAUSE_RULE = '🔑 **暂停的可用性取决于系统能否冻结，而不是是否存在暂停按钮。**'
PAUSE_STATES = [
    ('**实时战斗**', '输入 · 动画 · 伤害 · 计时 · 粒子 · 音频 · AI 思考 · 网络重连'),
    ('**过场**', '跳过条件 · 字幕 · 配音 · 镜头 · 输入接管 · 结尾回调'),
    ('**菜单**', '光标 · 焦点 · 未确认交易 · 教程锁 · 云存档上传'),
    ('**联机**', '踢出 · 断线 · 仲裁 · 暂停投票 · 旁观者 · 等待惩罚'),
    ('**移动端**', '后台 · 通知 · 来电 · 画中画 · 自动锁屏 · 触感'),
    ('**主机**', '休眠恢复 · 手柄断开 · 账号切换 · 奖杯同步'),
    ('**直播**', '隐私遮罩 · 暂停直播 · 观众提示 · 音频混音'),
]
PAUSE_NO = '🔑 若原版在菜单中可暂停、**在 BOSS 战和播片间不能**，'
'🔴 **这是行为事实，不是"原版设计不完美"，不能为统一体验而擅自改变**'
ONE_MORE = '🔑 **"再玩一局"应被记录成触发器集合，而非一句笼统的成瘾设计**：'
'即将升级 · 连续失败后的成功 · 稀有掉落 · 限时活动结束 · **每日任务差一项** · '
'排行榜刷新 · 队友等待 · 随机奖励未领取 · 自动战斗仍在进行 · '
'下一段播片即将开始 · 一次短局胜利 · **一次短局失败带来的"赢回来"冲动**'
BUDGET_STAT = '🔑 要统计的不是平均时长，而是 **P10 / P50 / P90 会话** · '
'**可安全退出节点间距** · **无存档最大连续时长** · '
'失败后回到可退出点所需时长 · 暂停恢复时长 · 异步云存档等待 · 最终确认步数'
ONE_MORE_SCORE = '🔑 "再来一局"评分 1–5：1 立即关闭 · 2 完成当前短任务后关闭 · '
'3 打完本节点 · 4 打完下一个节点 · 5 **取消闹钟继续**。'
'🔴 **复刻不得无故提高 4–5 的诱惑强度**'
LIFE_POLLUTE = '🔑 若重制通过**未拥有的 DLC 提示 · 活动弹窗 · 连续奖励 · '
'"只差一项"的每日任务**延长承诺，应另立"**生活接口污染**"缺陷，'
'🔴 **不等同于一般商业化问题**'

# 🔑 B 拟人化
PERSONA_RULE = '🔑 **玩家会把电脑对手拟人化，因此不可预测并不等于不公平。**'
PERSONA_STUDY = '🔑 一项修改版开源塔防实验显示：**作弊的电脑对手会被感知得更像人**，'
'并**提升恼怒与临场感**，却**没有降低总体享受**；'
'🔑 **更确定对手由电脑控制的人，敌意显著更低**'
PERSONA_NO = '🔴 **"黑箱更公平"是错误推论** —— '
'🔑 DDA · PRD · pity timer · 隐藏分 · RNG inspection **都应成为受版本锁定的 must-match 字段**'
ATTRIBUTION = '🔑 **公平感的承重变量是「行动—结果」的归因链，而不是公布概率。**'
'🔑 玩家真正需要回答三个问题：**我做了什么 · 为什么发生 · '
'下一次能否据此行动**。🔴 **若只能回答第一个，机制再真随机也会被归因为"针对我"**'
RNG_7 = [
    ('**纯随机**', '是否每帧/每请求重抽，是否依赖系统时间'),
    ('**PRD**', '当前权重 · 累计次数 · **重置条件**'),
    ('**Shuffle bag**', '抽取池 · 抽取后是否回补 · 初始填充规则'),
    ('**Pity timer**', '计数 · 阈值 · 保底 · **跨会话保留与溢出**'),
    ('**DDA**', '输入源 · 采样窗口 · 参与者 · 上下限 · 平滑算法'),
    ('**Hidden MMR**', '匹配池 · 衰减 · 新手保护 · **展示段位与真实队列**'),
    ('**AI bias**', '血量少时掉率 · 连败时命中 · 玩家速度时敌人强度'),
]
PERSONA_DIFF = '🔑 **"性格"与"作弊"的区别在于规律是否可学习。**'
'🔑 拟人的积极面来自**稳定怪癖**：某 BOSS 在玩家贴脸时更容易投技 · '
'某 NPC 连续两次被拒后改口 · 某敌人会故意留出破绽。'
'🔴 消极面来自**隐藏规则无法预测**'
PERSONA_NO2 = '🔑 原版若有可学习的怪癖，🔴 **重制不得为了"更公平"而随机化**；'
'若原版有不可见但有边界的黑箱，🔴 **也不应擅自做成数字面板**。'
'🔑 更稳妥的偏离是**保留不可见规则，只改变环境线索的清晰度**'
TRANSPARENCY = [
    ('**表层**', '玩家原始可见的命中 · 暴击 · 掉率 · 评级 · 连胜连败表现', '**不得改变**'),
    ('**元层**', '隐藏概率 · PRD 状态 · 隐藏分 · AI 人格 · 版本号',
     '仅专家/调试层，默认关闭'),
    ('**证据层**', '种子 · 回放 · RNG trace · 版本 · 复现步骤',
     '默认本地保存，上传需明示同意'),
]

# 🔑 C 文化层
CULT_RULE = '🔑 **文化不是文字表面的一层皮肤，'
'而是数值 · 颜色 · 手势 · 时间 · 姓名 · 排列规则的语义层。**'
CULT_NO = '🔑 **4 在东亚不吉利、紫色在部分地区关联哀悼，'
'这些不是可选审美注释。**'
CULT_DIMS = [
    ('**数字**', '4 · 7 · 8 · 9 · 13 · 18 · 88 · 666 及其组合'),
    ('**颜色**', '红 · 白 · 黑 · 紫 · 黄 · 绿及其**材质 · 饱和度 · 语境**'),
    ('**手势**', '角色动画 · 图标 · 徽章 · 庆典动作'),
    ('**历法**', '春节 · 盂兰盆 · 斋月 · 圣诞 · 生日 · 地区节日'),
    ('**时间**', '12/24 小时制 · 周日/周一 · 财年 · 节气'),
    ('**姓名**', '姓/名顺序 · 尊称 · 昵称 · 家族称谓'),
    ('**身体与社会规范**', '眼神接触 · 距离 · 性别表达 · 身份呈现 · 服饰暴露'),
    ('**视觉隐喻**', '动物 · 食物 · 宗教与历史符号 · 地图和旗帜'),
    ('**死亡与灾难**', '骨 · 血 · 幽灵 · 丧葬 · 自然灾害 · 事故'),
    ('**政治历史**', '国名 · 阵营 · 领土 · 历史人物与事件'),
]
CULT_JOKE = '🔑 若原版是日语笑话，重制把双关字面译出、'
'却让中文玩家只看到无意义的替代句，🔴 **这仍是文化失败**。'
'🔑 应记录**笑点功能**：自嘲 · 反差 · 地域梗 · 身份暗示 · 角色人格'
CULT_REGION = '🔑 **文化区域不能粗暴映射成单一国家** —— '
'中文区有简繁与港澳台海外差异；阿拉伯语有不同国家变体；'
'英语有美/英/印/澳新/西非差异；西班牙语有欧洲与拉美；葡语有葡与巴西；'
'法语有法国/加拿大/非洲'
CULT_TOOL = '🔑 **LDML 覆盖数字 · 日期 · 单位 · 复数 · 列表性别 · 大小写 · '
'排序 · 书写方向 · 键盘 · 地区信息，🔴 但它不是笑话 · 手势 · '
'颜色情绪 · 宗教隐喻的语义数据库**'
CULT_SOURCE = '🔑 **文化层还必须反向检查源语言区** —— '
'🔴 **把"源语言默认无文化"是最常见盲点**'

# 🔑 D 元收藏
SORT_RULE = '🔑 **玩家会把库存 · 图鉴 · 成就 · 截图 · Mod · 角色名'
'组织成私人秩序。**'
SORT_FIRST = '🔑 **稳定性是首要 must-match，而不是性能优化。**'
SORT_FIELDS = '主键 · 副键 · 插入顺序 · 内部 ID · 堆叠顺序 · '
'**未定义顺序** · 区域规则 · **稳定与否** · **刷新后是否保持**'
SORT_TIE = '🔑 特别要记"**平局时按什么排**"。'
'🔴 **如果原版顺序是未定义，重制也必须保留相同的未定义表现，'
'或显式承认存在不确定行为 —— 不能用稳定排序悄然取代。**'
SORT_UI = [
    ('**背包**', '自动整理 · 手动排序 · 锁定 · 堆叠 · 按类型/品质/等级/数量/时间/距离 · 逆序 · 分组'),
    ('**仓库**', '容器间搬运 · 跨容器排序 · 整组移动 · 筛选 · 忽略项 · 固定栏位'),
    ('**图鉴**', '编号 · 发现顺序 · 地区 · 稀有度 · 名称 · 完成状态 · 跨页滚动位置'),
    ('**Mod 列表**', '启用顺序 · **加载顺序** · 冲突顺序 · 更新时间 · 分组 · 依赖'),
    ('**收藏夹**', '顺序 · 复制 · 重命名 · 封面 · 过滤 · 批量应用'),
    ('**截图相册**', '时间 · 关卡 · 事件标签 · 缩略图位置 · 命名 · 导出目录'),
    ('**成就墙**', '顺序 · 分组 · 完成日期 · 稀有度 · 展示状态 · 时间线'),
]
SORT_ACTION = '🔑 **整理包含稳定动作，而不只是最终状态** —— '
'记排序前后的**光标位置 · 焦点 · 滚动位置 · 选中项 · 锁定项 · '
'未确认交易 · 拖拽目标 · 撤销栈**。'
'🔑 玩家会建立"**Shift 拖动先归堆**""**Ctrl 点击只移一个**"'
'"**从右下角向左倒序**"等肌肉记忆'
NAME_RULE = '🔑 **命名长度不是字符串上限，而是截断契约。**'
NAME_FIELDS = '字节长度 · 字符长度 · 显示宽度 · **组合字符** · 规范化形式 · '
'emoji 数量 · **双向文本** · 空格 · 全角 · 前导零 · 前缀 · 重名规则 · '
'敏感词提示 · 离线校验 · **重命名冷却** · **截断位置** · 跨平台同步'
NAME_WARN = '🔑 **东亚字符与双向文本尤其容易因按字节截断而破坏字符边界**；'
'🔴 **中文昵称不能仅因"国际化"缩短**'
MOD_ORDER = '🔑 **Mod 列表不是普通库存** —— **加载顺序决定功能**；'
'顺序变化可能改变**脚本 · 资源覆盖 · 兼容状态**。'
'🔴 **只支持"启用/禁用"而不支持顺序控制，可能直接破坏原版可复现的玩法组合**'

# E 展示与删除
SHOW_RULE = '🔑 **展示不是把数值陈列出来，'
'而是让玩家可组合地证明"这是我的历程"。**'
SHOW_OBJ = '成就墙（完成日期 · 显示顺序 · 稀有度 · 隐藏条件 · 未解锁暗示）· '
'名片（头像 · 标题 · 边框 · 统计 · 角色 · 标签 · 最近活动 · 隐私）· '
'展示柜 · 分享码 · 截图/录像 · **游戏时长（可见性 · 隐藏开关 · '
'计时边界 · 暂停是否计入 · AFK 是否计入）** · 收藏完成度 · 外观 · 社交资料'
SHOW_NO = '🔑 原版若**隐藏游戏时长**，🔴 **重制不能默认公开**；'
'原版若允许**隐藏成就日期**，复刻也不能强制显示'
DELETE_6 = [
    ('**隐藏**', '游戏时长 · 最近游玩 · 在线状态 · 成就日期 · 排行榜 · 好友列表'),
    ('**删除**', '单条截图 · 单局回放 · 单个名片 · 某个活动记录 · 单条聊天引用'),
    ('**撤销**', '成就 · 时长 · 收集 · 好友关系 · 排行榜'),
    ('**去标识**', '玩家名 · 好友关系 · **对他人的派生内容引用**'),
    ('**保留**', '仅切断可识别联系，🔑 **不必然删除世界内他人已引用的内容**'),
    ('**导出**', '成就 · 截图 · 回放 · 名片 · 统计 · Mod 配置的**机器可读最小包**'),
]
DELETE_RULE = '🔑 **删除权不是删号**，而是**证明可验证的最小化删除**。'
'🔴 **本地原版若没有删除功能，重制不能把"删除"当政治正确而加入**；'
'但应在调查表里明确标为**缺失能力**，由产品层决定是否偏离'
SHARE_CODE = '🔑 **分享码与回放是证明，而不只是链接** —— '
'记**生成算法 · 校验和 · 平台 · 区域 · 版本 · 过期 · 失效提示 · '
'截图压缩 · 字符集 · 空格与换行处理**。'
'🔑 原版分享码在旧版本失效，🔴 **重制若自动迁移，'
'会改变"来自旧版本的凭证"这一语义**'

# F 精通
MASTER_RULE = '🔑 **玩家可见的"进步信号"本身就是系统。**'
MASTER_FIELDS = '评级 · 连击 · 时间 · 伤害 · 命中率 · 无伤 · 漏敌 · 资源余量 · '
'段位 · 称号 · 回放对比 · 统计'
MASTER_NO = '🔑 原版"Great/Perfect"边界**即使不科学，也是 must-match**；'
'🔑 评级若按**内部帧数**计算，🔴 **重制不得按渲染帧计算**'
STAT_KIND = '累计 · 单局 · 最佳 · 平均 · 近期 · 连胜 · 失败 · 无伤 · 速通 · '
'资源余量 · 使用频率 · 命中 · 暴击 · 受击 · 死亡点 · 路径 · 输入 · 平台'
STAT_WHEN = '🔑 统计**何时更新 · 失败局是否计入 · 退出局是否计入 · '
'云同步冲突 · 跨版本迁移 · 重玩覆盖 · 回放重算**'
FORGET_RULE = '🔑 **技能遗忘是真实复玩成本** —— '
'手部肌肉记忆 · 输入序列 · 视角习惯 · 反应预期 · 菜单路径 · '
'判断知识**遗忘速度不同**'
FORGET_NO = '🔑 原版**没有"回归训练"，重制也不能为关怀玩家而擅自插入新手引导**。'
'🔑 可新增**默认关闭 · 不改变原版设置**的练习模式，'
'🔴 **但必须标成新增内容，而不是复刻结果**'

# G 第三空间
THIRD_RULE = '🔑 **安全区 · 大厅 · 篝火 · 座椅 · 表情 · 涂鸦 · 聊天 · '
'拍照点 · 舞蹈 · 摆 pose，共同构成玩家愿意长时间停留的第三空间。**'
THIRD_NO = '🔑 **优化掉这些"无效率"内容，会同时删除社交等待 · 身份表达 · '
'约定地点 · 弱连接 · 玩家摄影 · 仪式**'
THIRD_FIELDS = '是否可挂机 · **是否会被踢** · 是否持续消耗资源 · 是否保留聊天 · '
'是否有座椅/表情/舞蹈/拍照/涂鸦 · 能否邀请 · 能否旁观 · 能否交易 · '
'能否约会或开会'
THIRD_AFK = '🔑 **挂机聊天还可能承担防击退 · 原地警戒 · 防抢位 · 刷怪提醒 · '
'广告 · 公会 · 陌生人留言**等原版功能，🔴 **不能把"聊天室"简化为噪音**'
THIRD_WEAK = '🔑 **弱互动本身就是玩法。** 玩家会去安全区只为**聊天 · 展示外观 · '
'等人 · 拍照 · 结婚 · 开会 · 直播**。'
'共同条件：**低目标压力 · 可长期停留 · 身份可见 · 互动低成本 · 可离开且不掉队**'
THIRD_GRAF = '🔑 **涂鸦 · 摆 pose · 座椅是把空间变成私人场所的仪式** —— '
'记**对象旋转 · 坐标精度 · 贴图 · 时限 · 审核 · 举报 · 遮挡 · 回收 · '
'可见层级 · 跨会话保留**。'
'🔑 原版允许某面墙**长期保留涂鸦**，🔴 **复刻若自动清理，会删除玩家共同记忆**；'
'原版**定期清除**，复刻也不能永久化'
THIRD_SHOW = '🔑 **展示与社交相互依赖** —— 名片 · 时装 · 截图 · 角色外观'
'通常在安全区获得观众；🔑 **没有观众，展示系统失去一半功能**'

H_7 = [
    ('**H1 回归训练与肌肉记忆的版本化**',
     '记**休眠时长 · 设置漂移 · 键位/灵敏度 · 输入延迟 · 首次危险遭遇 · '
     '教程重入 · 回归错误**。🔑 新增 `F-回归曲线`：'
     '"是否有热身 · 是否默认关闭 · 是否进入危险内容 · 设置是否跨版本保留"独立成字段'),
    ('**H2 虚拟摄影与截图相册作为创作界面**',
     '滤镜 · 景深 · 隐藏 UI · 姿势 · 相机范围 · 分辨率 · 水印 · '
     '**相册排序 · 缩略图 · 跨设备同步 · 隐私 · 删除**。'
     '🔑 截图档案字段：源文件哈希 · 原文件名 · 创建时间 · 游戏内时间 · '
     '关卡/区域 · 会话 ID · **玩家坐标 · 角色状态 · 触发事件** · '
     '平台 · 构建版本 · 语言 · 手动备注。🔴 **不得自动把截图上传云端**'),
    ('**H3 会话录制与输入回放是最可靠的证明工具**',
     '🔑 新增 `replay_manifest`：构建版本 · 种子 · 输入 · 状态 · 帧数 · '
     '窗口尺寸 · 刷新率 · 音频缓冲 · 平台 · 后端 · shader · 随机结果 · 断言。'
     '🔴 **不应把回放器变成 DRM 或强制联网启动器**'),
    ('**H4 库存排序稳定性必须进入数据布局测试**',
     '🔑 即使只换排序算法，也可能改变**物品栏 · 图鉴 · 商店 · 任务 · 仓库 · '
     'Mod · 好友 · 搜索结果**。新增稳定排序 fuzz：**重复键 · 插入顺序 · '
     '区域规则 · 平局 · 刷新 · 分页 · 过滤 · 跨语言排序**'),
    ('**H5 命名截断 · 字符宽度 · 双向文本**',
     '🔑 至少覆盖**阿拉伯语 · 希伯来语 · 中文 · 日语 · 韩语 · 泰语 · 越南语 · '
     '德语长词 · 波兰语变音符号 · 繁简对照**'),
    ('**H6 跨会话统计与成就时间戳**',
     '记**时区 · 暂停/休眠是否计入 · 联机仲裁 · 云冲突 · 首次/最近/最佳口径 · '
     '版本迁移 · 重玩覆盖 · 失败局与退出局是否计入**'),
    ('**H7 数据遗产与删除 receipt**',
     '🔑 建立**可验证删除回执**。🔴 **不应以"游戏完整性"为由永久保留全部'
     '可识别数据，也不应把删号作为唯一删除方式**'),
]

CONFLICTS = [
    '❌ 用**自动暂停 · 过短会话 · 体力门 · 定时活动**去"教育玩家健康作息"',
    '❌ 把必须等待的联机匹配换成 AI 陪玩；取消原版没有取消的每日奖励',
    '❌ **重排检查点去适配现代节奏**',
    '❌ 为提升"可信度"**加入原本不存在的拟人动画**；用 LLM 给游戏加人格旁白',
    '❌ **把 PRD 换成更均匀但语义不同的新分布**；为消除"玄学"而删除掉落保底',
    '❌ **把隐藏机制全部公开**',
    '❌ **机器翻译直接定稿**；所有地区统一成美式英语语义',
    '❌ **自动替换颜色 · 删除数字 4 · 删掉紫色**或去除"不吉利"内容',
    '❌ 为政治中立**删除原有历史与政治隐喻**；用单一 fallback 覆盖所有区域',
    '❌ **自动分类"为玩家整理好"**；默认按策划推荐排序；跨语言自动重排',
    '❌ 自动重命名 · 按内容自动打标签 · **默认云端备份截图** · 强制统一库存布局',
    '❌ **把 Mod 顺序交给云端随意同步**',
    '❌ 默认社交网络登录才能查看名片；**强制成就墙公开**；默认上传截图',
    '❌ 为留存数据而阻止删除；**把删除账号设为唯一删除方式**；自动重置成就',
    '❌ 通过隐藏时长**制造留存焦虑**',
    '❌ 为回归玩家**自动降低难度**；把等级重置为"公平起点"；按新平台重设灵敏度',
    '❌ 为提升效率**删除篝火和绕路**；用自动匹配替代大厅；默认语音监听；禁止挂机',
    '❌ **把涂鸦自动审核成无痕内容**；为商业化出售原本免费的社交座位',
    '❌ 在重制中**自动补算旧版本漏记数据**',
]

FIELDS = [
    ('item_id', '项编号'),
    ('domain', '域（budget / exit / pause / persona / rng / culture / sort / '
               'name / show / master / third / h）'),
    ('legacy_value', '**原版值**'),
    ('new_value', '新引擎值'),
    ('match', '**是否一致**'),
    ('life_evidence', '**生活/文化/秩序证据**（录制或实测）'),
    ('evidence', '证据等级 1-8'),
]


def _hdr(t, w=80):
    print('=' * w)
    print(t)
    print('=' * w)


def cmd_budget(a):
    _hdr('🔑 时间预算（**管理的是会话承诺，不是时长**）')
    print(f'   {BUDGET_RULE}')
    print(f'\n   {BOSS_RULE}')
    print(f'\n   {BUDGET_REC}')
    print('\n会话承诺曲线:')
    for s in SESSION_CURVE:
        print(f'   · {s}')
    print(f'\n   {GOLDEN}')
    print(f'\n   {SAVE_DENSITY}')
    print(f'\n   {SAVE_WINDOW}')
    print(f'\n   {BUDGET_STAT}')
    return 0


def cmd_exit(a):
    _hdr('🔑 退出尾部与"再来一局"')
    print(f'   {ONE_MORE}')
    print(f'\n   {ONE_MORE_SCORE}')
    print(f'\n   {LIFE_POLLUTE}')
    return 0


def cmd_pause(a):
    _hdr('🔑 可暂停性（**取决于系统能否冻结**）')
    print(f'   {PAUSE_RULE}')
    print('\n逐状态:')
    for k, v in PAUSE_STATES:
        print(f'   {k:<14} {v}')
    print(f'\n   {PAUSE_NO}')
    return 0


def cmd_persona(a):
    _hdr('🔑 拟人化（**公平感的承重变量是归因链**）')
    print(f'   {PERSONA_RULE}')
    print(f'\n   {PERSONA_STUDY}')
    print(f'\n   {PERSONA_NO}')
    print(f'\n   {ATTRIBUTION}')
    print(f'\n   {PERSONA_DIFF}')
    print(f'\n   {PERSONA_NO2}')
    print('\n透明度三层:')
    for k, v, d in TRANSPARENCY:
        print(f'   {k:<12} {v}')
        print(f'   {"":<12} → {d}')
    return 0


def cmd_rng(a):
    _hdr('受控随机通道（**七类**）')
    for k, v in RNG_7:
        print(f'   {k:<16} {v}')
    return 0


def cmd_culture(a):
    _hdr('🔑 文化层（**不是文本外包问题**）')
    print(f'   {CULT_RULE}')
    print(f'\n   {CULT_NO}')
    print('\n十项维度:')
    for k, v in CULT_DIMS:
        print(f'   {k:<20} {v}')
    print(f'\n   {CULT_JOKE}')
    print(f'\n   {CULT_REGION}')
    print(f'\n   {CULT_TOOL}')
    print(f'\n   {CULT_SOURCE}')
    return 0


def cmd_sort(a):
    _hdr('🔑 元收藏（**排序稳定性是首要 must-match**）')
    print(f'   {SORT_RULE}')
    print(f'\n   {SORT_FIRST}')
    print(f'\n字段: {SORT_FIELDS}')
    print(f'\n   {SORT_TIE}')
    print('\n八类界面:')
    for k, v in SORT_UI:
        print(f'   {k:<14} {v}')
    print(f'\n   {SORT_ACTION}')
    print(f'\n   {MOD_ORDER}')
    return 0


def cmd_name(a):
    _hdr('命名截断契约')
    print(f'   {NAME_RULE}')
    print(f'\n字段: {NAME_FIELDS}')
    print(f'\n   {NAME_WARN}')
    return 0


def cmd_show(a):
    _hdr('展示与删除权')
    print(f'   {SHOW_RULE}')
    print(f'\n对象: {SHOW_OBJ}')
    print(f'\n   {SHOW_NO}')
    print('\n六种操作:')
    for k, v in DELETE_6:
        print(f'   {k:<12} {v}')
    print(f'\n   {DELETE_RULE}')
    print(f'\n   {SHARE_CODE}')
    return 0


def cmd_master(a):
    _hdr('精通曲线（**可见进步信号本身就是系统**）')
    print(f'   {MASTER_RULE}')
    print(f'\n信号: {MASTER_FIELDS}')
    print(f'\n   {MASTER_NO}')
    print(f'\n统计口径: {STAT_KIND}')
    print(f'\n   {STAT_WHEN}')
    print(f'\n   {FORGET_RULE}')
    print(f'\n   {FORGET_NO}')
    return 0


def cmd_third(a):
    _hdr('🔑 第三空间（**不是低效率空间**）')
    print(f'   {THIRD_RULE}')
    print(f'\n   {THIRD_NO}')
    print(f'\n字段: {THIRD_FIELDS}')
    print(f'\n   {THIRD_AFK}')
    print(f'\n   {THIRD_WEAK}')
    print(f'\n   {THIRD_GRAF}')
    print(f'\n   {THIRD_SHOW}')
    return 0


def cmd_h(a):
    _hdr('H 类（**七项**）')
    for k, why in H_7:
        print(f'\n   【{k}】\n      {why}')
    return 0


def cmd_init(a):
    os.makedirs(os.path.dirname(a.init) or '.', exist_ok=True)
    with open(a.init, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow([k for k, _ in FIELDS])
        w.writerow(['TODO'] * len(FIELDS))
    print(f'已生成生活层表: {a.init}')
    print('\n⚠️ 十二域：budget / exit / pause / persona / rng / culture / '
          'sort / name / show / master / third / h')
    print('\n⚠️ `life_evidence` 列＝**生活/文化/秩序证据**（录制或实测）')
    print('\n🔑 新模板：A-时间预算 · B-拟人化与公平归因 · culture_map · '
          'D-元收藏与整理契约 · E-展示与删除权 · F-回归曲线 · '
          'G-第三空间 · replay_manifest · virtual_photography')
    print('\n🔑 新脚本：sort_stability_diff · rng_trace_diff · '
          'session_exit_trace · text_boundary_fuzz · stat_audit')
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

    mismatch, no_legacy, no_life, no_grade = [], [], [], []
    for i, r in enumerate(rows, 1):
        m = g(r, 'match').lower()
        if m not in ('yes', 'y', 'true', '是', '一致'):
            mismatch.append(i)
        if not g(r, 'legacy_value') or g(r, 'legacy_value') == 'TODO':
            no_legacy.append(i)
        p = g(r, 'life_evidence')
        if not p or p == 'TODO':
            no_life.append(i)
        ev = g(r, 'evidence')
        if not ev or ev == 'TODO':
            no_grade.append(i)
        else:
            d = ev.split('.')[0].strip()
            if d.isdigit() and int(d) >= 7:
                no_grade.append(i)

    print('=' * 76)
    print(f'生活层与文化层 · {len(rows)} 条')
    print('=' * 76)
    if mismatch:
        print(f'\n🚫 **不一致** {len(mismatch)} 条（行 {mismatch[:15]}）')
    if no_legacy:
        print(f'\n❌ {len(no_legacy)} 条缺**原版值**（行 {no_legacy[:15]}）')
    if no_life:
        print(f'\n🚫 {len(no_life)} 条缺**生活/文化/秩序证据**'
              f'（行 {no_life[:15]}）')
    if no_grade:
        print(f'\n🚫 {len(no_grade)} 条**证据等级缺失或 ≥7 级**'
              f'（行 {no_grade[:15]}）')

    if not (mismatch or no_legacy or no_life or no_grade):
        print('\n✅ 生活层：一致、原版值完整、生活文化证据已验证、证据达标')

    print('\n🔑 **玩家管理的是会话承诺，不是游戏时长。**')
    print('   🔑 **玩家容忍不可预测，却不容忍结果无法归因。**')
    print('   🔴 **排序"更科学"并不比"和原版一致"更正确。**')
    print('   🔑 **第三空间不是低效率空间，优化掉它等于删除社交与仪式。**')
    return 1 if (a.gate_check and
                 (mismatch or no_legacy or no_life or no_grade)) else 0


def main():
    ap = argparse.ArgumentParser(description='生活层：时间预算/拟人/文化/秩序')
    ap.add_argument('--budget', action='store_true')
    ap.add_argument('--exit', action='store_true')
    ap.add_argument('--pause', action='store_true')
    ap.add_argument('--persona', action='store_true')
    ap.add_argument('--rng', action='store_true')
    ap.add_argument('--culture', action='store_true')
    ap.add_argument('--sort', action='store_true')
    ap.add_argument('--name', action='store_true')
    ap.add_argument('--show', action='store_true')
    ap.add_argument('--master', action='store_true')
    ap.add_argument('--third', action='store_true')
    ap.add_argument('--h', action='store_true')
    ap.add_argument('--init')
    ap.add_argument('--check')
    ap.add_argument('--gate-check', action='store_true')
    a = ap.parse_args()
    fns = {'budget': cmd_budget, 'exit': cmd_exit, 'pause': cmd_pause,
           'persona': cmd_persona, 'rng': cmd_rng, 'culture': cmd_culture,
           'sort': cmd_sort, 'name': cmd_name, 'show': cmd_show,
           'master': cmd_master, 'third': cmd_third, 'h': cmd_h}
    for k, fn in fns.items():
        if getattr(a, k):
            return fn(a)
    if a.init:
        return cmd_init(a)
    if a.check:
        return cmd_check(a)
    print('❌ 需要 --budget / --exit / --pause / --persona / --rng / '
          '--culture / --sort / --name / --show / --master / --third / '
          '--h / --init / --check 之一')
    return 2


if __name__ == '__main__':
    sys.exit(main())
