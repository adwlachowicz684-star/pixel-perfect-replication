#!/usr/bin/env python3
"""声音语义 · 成长可感知 · 玩家元操作 · 时间美学
（第四十轮 A / B / C / D 类，含 E / F / G 补充）。

**🔑 本轮的视角切换**（四十轮的转折）：
> **前 39 轮覆盖的是传输链，本轮覆盖的是"玩家读出什么"。**

🔑 **既有方法论容易把"可复现"误判为"可理解"。**
若一记脚步被记录成"播放木地板样本"，**只说明声源播放成功**；
玩家真正获得的信息是"**正上方木地板 · 普通敌人 · 负重奔跑**"。

**🔑 六类盲区的共同结构：事实态 + 表达态 + 可辨态。**
- **事实态**：原版数据
- **表达态**：样本 · 混音 · 动画 · 特效 · UI · 震动
- **可辨态**：玩家在**盲测**中能否正确识别 ← **只有这层证明复刻有效**

🔑 **波形 · 帧时间 · 伤害数字都只能证明"值接近"，不能证明"听得懂"。**

用法:
  game_meaning_layer.py --audio  # 🔑 **声音事实，不是音效事件**
  game_meaning_layer.py --mat    # **脚步是四段链条不是表面枚举**
  game_meaning_layer.py --vert   # 🔴 **"楼上还是楼下"必须独立字段**
  game_meaning_layer.py --threat # **威胁等级按声学角色拆分**
  game_meaning_layer.py --gait   # **步态暴露角色状态**
  game_meaning_layer.py --mix    # **混音可读性阈值从原版测**
  game_meaning_layer.py --growth # 🔑 **成长五通道，不是 power_level**
  game_meaning_layer.py --delta  # **变化方向与原版一致**
  game_meaning_layer.py --unlock # **能力解锁必须改变世界**
  game_meaning_layer.py --avatar # **本体痕迹会说话**
  game_meaning_layer.py --meta   # 🔴 **C1 是唯一能直接导致流失的硬边界**
  game_meaning_layer.py --multi  # 多显示器**拓扑 · DPI · 刷新率 · 窗口所有权**
  game_meaning_layer.py --cap    # 截图/录屏/直播是**平台能力清单**
  game_meaning_layer.py --share  # **家庭共享 · 多开 · 多号**
  game_meaning_layer.py --beat   # 🔑 **跨通道节拍偏移**（不是"音频是否同步"）
  game_meaning_layer.py --wait   # 等待要记**时长 · 反馈 · 控制权 · 退出权**
  game_meaning_layer.py --apm    # **操作上限与连招节奏**
  game_meaning_layer.py --narr   # 叙事时间不能只写"昼夜变化"
  game_meaning_layer.py --imperf # 🔑 **刻意坏味清单**
  game_meaning_layer.py --comm   # **社群锚点 · 版本语义 · 文化记忆**
  game_meaning_layer.py --g      # G 类
  game_meaning_layer.py --init ledger/meaning_layer.csv
  game_meaning_layer.py --check ledger/meaning_layer.csv --gate

退出码: 0 通过 / 1 缺项 / 2 用法错误
"""
import argparse
import csv
import os
import sys

# 🔑 声音语义
AUDIO_RULE = '🔑 **A1–A5 的原子单元是"声音事实"，不是音效事件。**'
AUDIO_FIELDS = [
    '事件', '**声源移动状态**', '**表面**', '鞋履/体型', '空间体积', '声障',
    '**垂直关系**', '**威胁等级**', '直达/反射/遮挡', '混音轨道', '响度',
    '低频量', '起音', '节奏间隔', '**玩家应读出的结论**',
]
AUDIO_MULTI = ('🔑 字段必须允许**并列多个正确结论**'
              '（例如「木地板或薄木板」均可接受）'
              '—— 🔴 **不能只写一个绝对标签**')
AUDIO_EVIDENCE = [
    '源码', '日志', '音频总线', '高保真回放', '**玩家盲测**', '开发者访谈',
]
AUDIO_WARN = '🔴 **不能拿社区猜测充数**'

MAT_CHAIN = '🔑 **脚步材质不是一个表面枚举，'
'而是"可见材质 → 命中材质 → 声音映射 → 玩家识别"的链条**'
MAT_RULE = [
    '🔴 原版若只从**渲染材质**取声音，'
    '重制**不能为了真实改成射线查询物理材质**',
    '🔑 若原版同时查**地形纹理权重 · 碰撞盒材质 · 覆盖层**，'
    '应原样复刻**查询顺序 · 缓存 · 优先级**',
]
MAT_SAMPLE = '🔑 `godot-material-footsteps`（MIT）把**元数据 · GridMap 瓦片 · '
'HTerrain 层 · 实际材质表面**四种策略并列 —— '
'🔑 **说明真实项目不存在单一通用方案**'

VERT_RULE = '🔴 **"楼上还是楼下"必须作为独立字段，而不是 HRTF 的附属品**'
VERT_WHY = '🔑 垂直定位依赖**直达声强度 · 天花板反射延迟 · 地板遮挡 · '
'房间体积 · 混响尾部**，这些变量**未必随平面方位一起变化**'
VERT_SUB = ['直达声', '早期反射', '混响', '声障']
VERT_TEST = ['同层', '上一层', '下一层', '斜向楼梯']
VERT_GOAL = '🔑 最终目标不是"**响度相同**"，而是"**混淆矩阵相同**"'

THREAT_RULE = '🔑 **威胁等级编码要按声学角色拆分**'
THREAT_WHY = '🔴 同一精英敌人可能只改音量，也可能改**呼吸周期 · 装甲撞击 · '
'脚步间隔 · 低频重心 · 混响尾部 · 台词** —— '
'🔴 **不能统一表述为"声音更凶"**'
THREAT_TAGS = [
    '同类/异类', '精英/普通', '受伤/完整', '警觉/潜行', '攻击前摇/持续追击',
]
THREAT_LORE = '🔑 若原版存在**只有老玩家才懂的细微差异**，应标 `lore_critical=true`，'
'🔴 **不得因普通测试组无法识别而删除**'

GAIT_RULE = '🔑 **节奏不是"脚步有间隔"，而是步态暴露角色状态**'
GAIT_ITEMS = [
    '步频', '**左右相位**', '起音强弱', '落地衰减', '**负重滑动**',
    '**潜行拖步**', '**受伤短步**', '连跳压缩间隔',
]
GAIT_VARY = ['速度', '疲劳', '水面', '坡度', '装备']
GAIT_WARN = '🔴 **原版若故意让轻甲潜行仍有明显拖步，'
'重制成静音滑步就是 must-match 破坏**'
GAIT_VERIFY = '🔑 验证采用**音频 onset 与脚骨骼/根运动事件对齐**；'
'🔴 **不能只看事件名称**'

MIX_RULE = '🔑 **混音可读性需要绝对阈值，'
'但阈值应从原版测量，不应套用通用响度曲线**'
MIX_ITEMS = [
    '每条关键线索的**最小清晰余量**',
    '**互相掩蔽频带**',
    '关键声必须可懂时的**最大遮蔽**',
    '总线压缩与闪避',
]
MIX_TEST = '🔑 建立"**线索掩蔽测试**"：在环境 · 音乐 · 混响存在时，'
'逐项测是否还能识别**材质 · 方向 · 威胁 · 节拍**，'
'🔴 **而不是只做频响扫频**'
MIX_A11Y = '🔑 对老年玩家或高频听力下降应**另设可访问副本**，'
'🔴 **但原版副本仍需保留**'

# 🔑 成长
GROWTH_RULE = '🔑 **应新增成长反馈矩阵，而非在技能表加一个反馈列。**'
GROWTH_FIVE = [
    ('**animation**', '前摇 · 出招 · 恢复 · **重量感** · IK'),
    ('**vfx**', '规模 · 密度 · 颜色 · 拖尾 · **相机反应**'),
    ('**audio**', '音高 · 音头 · 低频 · 混响 · 材料'),
    ('**world**', '**敌人受击反应** · 破防 · 环境变化 · 交互解锁'),
    ('**meta**', '界面数字 · 图标 · 镜头 · 成就感'),
]
GROWTH_SILENT = '🔑 **若原版只改数字、没有任何视觉变化，'
'这同样是必须记录并复刻的"沉默事实"** —— 🔴 **不能补成"更爽"**'

DELTA_RULE = '🔑 **变强不是五个通道一起变大，而是变化方向与原版一致**'
DELTA_DIRS = ['increase', 'decrease', 'nonlinear', '**inversion**']
DELTA_EG = [
    '🔑 原版高等级**反而更克制**、低等级更夸张',
    '🔑 提升后敌人反应从"硬直"变为"**失衡**"而非"更响"',
]
DELTA_WARN = '🔴 **若只记录绝对值，重制很容易把它误判为错误并"修正"**'
DELTA_COMPARE = '🔑 把每个能力录成**输入触发 → 五通道输出**的时间线，'
'比较**增益 · 峰值 · 持续时间 · 曲线形状 · 相位**，'
'🔴 **而不是只比较数值**'

LEVEL_SPLIT = '🔑 等级映射要把"**效果参数**"与"**感知参数**"分开'
LEVEL_FIELDS = [
    '版本', '能力', '等级', '事实源', '效果量', '动画速率', '特效半径',
    '低频增益', '**敌人反应 ID**', '**世界响应 ID**',
]

UNLOCK_RULE = '🔑 **能力解锁必须改变世界，而不只是增加菜单项**'
UNLOCK_ITEMS = [
    '新路径', '捷径', '敌人', '互动', '光照', '音频', '隐藏文本', '可破坏物',
]
UNLOCK_WARN = [
    '🔴 **重制若仅加高模门而不接入能力条件，'
    '玩家会记住"以前从这里能过去"**',
    '🔴 **若原版门只是视觉巧合，也不能为了"能力有意义"补成捷径**',
]

AVATAR_RULE = '🔑 **角色本体演化要把损伤与变异处理成连续状态机**'
AVATAR_FIELDS = [
    '触发变量', '阈值', '**保持/消退**', '模型替换规则', '材质参数', '表情',
    '动画层', '语音', '**NPC 台词**', '**存档恢复**',
]
AVATAR_SCAR = '🔑 记录**伤疤 · 血迹 · 污垢 · 疲劳 · 装备破损**的'
'**累积 · 衰减 · 跨场景持久化 · 镜头可见性**'
AVATAR_WARN = '🔑 **本体痕迹会说话** —— '
'🔴 **同一把武器破损与角色本体破损给玩家的信息不同，不能共用一个状态**'

META_RULE = '🔴 **C1 是六盲区中唯一能直接导致玩家流失的硬边界**'
META_EVENTS = [
    'Alt-Tab', 'Win-G', 'Win-D', 'Win-L', 'Win-Shift-S', 'Win-P', 'Win-M',
    'Win-Space', '**多显示器**', '虚拟桌面', '独占全屏', '无边框', '边框化',
    '最小化', '关闭请求', '**睡眠/恢复**', '远程桌面', '游戏栏', '录屏覆盖',
]
META_ASK = [
    '是否暂停', '是否静音', '是否释放光标', '**时钟是否继续**',
    '**联机是否断线**', '输入是否残留', '**恢复后第一帧是否吞键**',
    '是否重置摄像机', '是否弹出独占覆盖', '**音频设备是否切换**',
]
META_EVIDENCE = '🔑 每对原版/复刻均录制**视频 · 输入日志 · 音频捕获 · 进程事件**；'
'🔴 **不能只写"恢复后正常"**'

MULTI_RULE = '🔑 **多显示器不能只测分辨率，要测拓扑 · DPI · 刷新率 · '
'窗口所有权**'
MULTI_ITEMS = [
    '主副屏位置', '任务栏屏', '**全屏目标屏**', '最大化行为', '弹窗归属',
    '**鼠标约束**', '**光标越界**', '截图区域', 'Replay Buffer', 'OBS 捕获',
    '画中画', '覆盖热键',
]
MULTI_EXCL = [
    '**Alt-Tab 黑屏时长**', '模式切换', '**GPU 重置**', 'HDR 输出',
    '**HDR10/SDR 捕获差异**',
]
MULTI_BORDERLESS = [
    '组合 Alt-Enter 行为', '**Alt 键陷阱**', '延迟', '最大 FPS 限制',
]
MULTI_WARN = '🔴 **任何"统一改成无边框"的默认优化都会改变原版输入与捕获语义** '
'—— 应标 `deviation-only`'

CAP_RULE = '🔑 **截图 · 录屏 · 直播应成为平台能力清单，'
'而不是反作弊的副作用**'
CAP_ITEMS = [
    '原版截图键', '**截图保存路径**', '**截图是否含 HUD/调试 UI**',
    '是否可静默禁用', '是否显示录制指示', '**Replay Buffer 时长**',
    '即时回放热键', '直播状态', '**覆盖是否捕获光标**', '是否保留原版滤镜',
    '水印', '暂停与字幕',
]
CAP_KEEP = '🔴 **若原版故意让某种画面不可截图，也必须作为事实保留** —— '
'🔴 **不能默认现代系统"应该可截屏"**'
CAP_TOOLS = [
    'OBS', 'Xbox Game Bar', 'Steam', 'Discord', 'GeForce/AMD 覆盖',
    'ShadowPlay Instant Replay', 'ReLive Instant Replay', '系统截图',
]

SHARE_RULE = '🔑 **家庭共享 · 多开 · 多号 · 多档案不是反作弊问题，'
'而是原版允许的外围操作**'
SHARE_ITEMS = [
    '是否允许多进程', '**是否通过互斥体/锁文件/端口/窗口标题限制**',
    '是否允许家庭共享', '**副本所有者是否影响 DLC/货币/排行榜**',
    '多号是否共享配置', '**云存档冲突策略**', '家庭共享限制触发条件',
]
SHARE_WARN = '🔴 **"原版允许、复刻却悄悄禁止"本身就是体验破坏**'
SHARE_STEAM = '🔑 官方 Steam Families 文档明确**共享许可是临时的**，'
'共享者**不应取得永久所有权**；应把"**原所有者 / 当前玩家 / 许可类型**"'
'写入所有权账本，🔴 **而不是只保存一个账号 ID**'

# 🔑 节拍
BEAT_RULE = '🔑 **核心指标是跨通道节拍偏移，不是"音频是否同步"**'
BEAT_CHANNELS = [
    '音乐小节', '**音乐 onset**', '音频播放样本', '**动画事件帧**',
    '**特效出生帧**', '**UI 提示帧**', '**输入允许帧**', '**震动 onset**',
    '**相机 shake onset**', '**屏幕 flash onset**', '**伤害判定帧**',
]
BEAT_TOL = '🔑 容差按项目帧预算给出（例如 60Hz 下 1–2 帧）；'
'🔴 **原版若故意错位，复刻错位也必须是 must-match**'
BEAT_METHOD = '🔑 从高速录屏提取光/声 onset，或从日志 · 动画事件 · 音频样本计算，'
'输出每个通道**相对音乐时间的直方图与最大偏差**'
BEAT_TOOL = '🔑 `Unity-Music-Sync-System` 能证明"**音频 onset → 动画速度**"的'
'工程路径，🔴 **不能证明重制应采用自动节拍对齐**。'
'🔑 应**优先手动指定原版节拍表，自动工具仅用于发现遗漏或校验**'

BEAT_CLOCK = [
    ('`bar/beat/subdivision`', '小节 · 拍 · 细分；原版无音乐时以主循环周期映射'),
    ('`beat_clock_us`', '**权威时戳，不因帧率变化**'),
    ('`channel`', 'audio / anim / vfx / ui / haptics / gameplay'),
    ('`event_id`', '原版事件 ID 或语义名'),
    ('`offset_us`', '相对节拍基准的偏差'),
    ('`match_class`', 'must-match / deviation-only / **intentional-art**'),
    ('`source_sample`', '回放片段或日志路径'),
]
BEAT_ONE = '🔑 **节拍档案应形成单一时间轴，而非多个异步表** —— '
'以音频采样或稳定高精度时钟为权威源，所有通道打**同一 `beat_clock` 戳**。'
'🔑 转换到 30/60/120Hz 或不同刷新率时，**只改显示映射，不改事件顺序**'

WAIT_RULE = '🔑 **等待必须同时记录时长 · 反馈 · 控制权 · 退出权**'
WAIT_KINDS = [
    '加载', '过场', '动画锁', '技能前摇', '冷却', '刷新', '制造', '交易',
    '传送', '**死亡重试**', '存档', '检查点', '教程锁', '菜单动画', '剧情选择',
]
WAIT_FIELDS = [
    '时间下限 · 上限 · 均值 · **方差**', '有无进度提示', '声音', '背景活动',
    '可操作对象', '**可跳过**', '**可中断**', '可后台', '可缓存', '**断线恢复**',
]
WAIT_WARN = '🔑 **一个"更短但更空"的等待与一个"更长但保留小活动"的等待'
'不可互换**'

APM_RULE = '🔑 **操作上限与连招节奏应成为输入时域档案**'
APM_ITEMS = [
    '单手/双手 **APM**', '**最短合法间隔**', '缓冲区长度', '允许重叠输入',
    '取消窗口', '前摇冻结', '网络预测', '**手柄 vs 键鼠差异**',
    '连招最长序列', '输入丢帧与高频宏',
]
APM_WARN = '🔴 **复刻若改变帧率 · 缓冲 · 输入采样 · 动画取消，'
'可能表面手感相同却提高或降低天花板**'

NARR_RULE = '🔑 **叙事时间不能只写"昼夜变化"**'
NARR_ITEMS = [
    '昼夜', '季节', '天气', '节日', '**剧情日期**', 'NPC 日程', '商店周期',
    '怪物刷新', '环境对话', '光照与音乐',
]
NARR_NAME = '🔑 另记**玩家称呼 · 内部构建名 · 补丁名 · '
'年度版/决定版/重制版差异**'
NARR_WARN = [
    '🔴 **若某事件原版只在星期三触发，重刻成每日事件会改变速通路线与社群记忆**',
    '🔑 若原版有"**版本内时间跳跃**"，也要保存其断点与叙事语义',
]

# 🔑 异常美学
IMPERF_RULE = '🔑 **要求建立"刻意坏味"清单，任何修复都须有偏离许可**'
IMPERF_ITEMS = [
    '穿模', '碰撞漏判', '摄像机穿墙', '动画瞬移', '动作重叠', 'UI 错位',
    '**字体不一致**', '**占位文本**', '长加载', '掉帧', '颜色溢出',
    '纹理拉伸', 'LOD 跳变', '音频截断', '延迟输入', '**旧版手柄图标**',
    '**误导性提示**', '**不可达奖励**', '冗余菜单',
]
IMPERF_FIELDS = [
    '触发条件', '版本', '**玩家是否利用**', '**利用后的策略价值**',
    '视觉/音频/操作影响', '**是否文化符号**',
]
IMPERF_SPLIT = '🔑 把"**刻意艺术**"与"**真正应修复的崩溃/安全漏洞**"分开：'
'前者为 `intentional-art`'
IMPERF_WARN = '🔴 **若为了现代 UI 统一风格而删除所有不一致，'
'要测量其对版本识别与社群称呼的影响**'

LOWCOST_RULE = '🔑 **低成本资产的魅力来自约束形成的风格，而非低分辨率滤镜**'
LOWCOST_3D = [
    '低模面数分布', '重复几何', '**程序化随机种子**', '纹理图集',
    '**调色板数量**', '抖动', '音频通道', '采样率', '**音头截断**',
    '循环长度与重复可感性',
]
LOWCOST_OLD = [
    '色深', '调色板', '**色循环**', '**仿射纹理映射**', '**顶点抖动**',
    '**定点截断**', '扫描线', 'CRT 辉光', '子像素渲染',
]
LOWCOST_WARN = '🔴 **高清化 · 抗锯齿 · 色板扩展 · 模型平滑默认会破坏异常美学**'
LOWCOST_ORDER = [
    '① **先像素级测量原版输出**',
    '② 做"**原版真实**"模式',
    '③ 最后才做现代便利模式（允许整数缩放 · 可选锐利滤镜 · 色板量化 · '
    '抖动 · 仿射映射 · 顶点抖动）',
    '🔴 **但不得替换原版素材**',
]
LOWCOST_FACE = '🔑 对角色脸 · 微表情 · 布料 · 口型，高清化尤其容易引入'
'**过度平滑 · 眼神变空 · uncanny 感**；应逐项记**原始法线 · 粗糙度 · '
'次表面 · 注视目标 · 眨眼周期 · 口型样本**'

# 社群
WIKI_RULE = '🔑 **把社群知识当成版本化锚点**'
WIKI_FIELDS = [
    'wiki 标题', '坐标', '**实体 ID**', '帧数', '**路线名**',
    '**输入序列哈希**', '版本', '**玩家术语**', '**旧术语**', '官方术语',
    '截图/录像链接', '证据等级',
]
WIKI_WARN = '🔴 **若路线不再可达，不能静默删词** —— '
'应标 `broken_by_design=true` 并**保留历史描述**'

VER_THREE = '🔑 **版本语义必须统一"内部名 / 商店名 / 玩家名"三个空间**'
VER_FIELDS = [
    '构建号', '**数据格式版本**', '补丁日期', '**存档兼容**', '商店 SKU',
    '启动器名称', '**玩家俗称**',
]
VER_WARN = [
    '🔴 **若重制版沿用旧名，wiki 自动跳转与搜索结果会错配**',
    '🔴 **若使用新名，老攻略链接会失效**',
]
VER_MIN = '🔑 至少提供**版本选择页 · 分享码携带版本 · '
'日志与录像头中的可读版本**'

CULTURE_RULE = '🔑 **文化记忆不能只做成彩蛋清单**'
CULTURE_ITEMS = [
    '梗', '名场面', '**失败台词**', '**经典穿帮**', '**约定俗成按键**',
    '**速通术语**', '秘密触发', '**玩家共同误解**', '**反直觉收益**',
]
CULTURE_FIELDS = [
    '触发器', '可见反馈', '**玩家意义**', '社群首次出现时间',
    '**是否仍是合法策略**',
]
CULTURE_WARN = '🔑 复刻后若角色 · 镜头 · 音效变化导致梗无法复现，'
'应判断是否保留一个**可触发的历史模式**，'
'🔴 **而不是只在采访中"致敬"**'

G_EXTRA = [
    ('**可辨性优先于可播放性**',
     '🔑 凡是玩家据以判断**材料 · 方向 · 威胁 · 状态 · 能力 · 节奏**的信号，'
     '都必须成为 `must-match`，🔴 **而不是由美术或音频团队按现代审美重新解释**'),
    ('**自动工具只能提供候选机制，不能提供美学判断**',
     '🔴 FFT/谱通量能检测 onset，不能决定重制该不该自动节拍对齐'),
    ('**任何使原版事实无法回滚的默认优化**',
     '🔴 都应显式降级为 `deviation-only` 或拒绝 —— '
     '🔑 **冲突点不在技术，而在决策权**'),
]

CONFLICTS = [
    '❌ **自动归一化响度 / 全局重混**',
    '❌ **按现代控制器映射清空旧键位**',
    '❌ **把经典 bug 标成 defect 修复**',
    '❌ 用 **AI 自动翻新低模与音频**',
    '❌ **只保留一个"重制版"名称**（丢掉版本语义）',
    '❌ **为了真实把渲染材质取声改成射线查物理材质**',
    '❌ **把"楼上还是楼下"当 HRTF 附属品**',
    '❌ 统一表述为"**声音更凶**"',
    '❌ **把潜行拖步做成静音滑步**',
    '❌ **用通用响度曲线替代原版测量**',
    '❌ **只改数字却补成"更爽"**（沉默事实被改）',
    '❌ **把"高等级更克制"误判为错误并修正**',
    '❌ **只加高模门不接能力条件**',
    '❌ **"统一改成无边框"的默认优化**',
    '❌ **默认现代系统"应该可截屏"**',
    '❌ **原版允许、复刻悄悄禁止**（多开/共享/宏）',
    '❌ **把只在星期三触发的事件改成每日**',
    '❌ **为了现代 UI 统一风格删除所有不一致**',
    '❌ **高清化替换原版素材**',
    '❌ **路线不可达就静默删词**',
]

FIELDS = [
    ('item_id', '项编号'),
    ('domain', '域（audio / mat / vert / threat / gait / growth / delta / '
               'unlock / avatar / meta / multi / cap / share / beat / wait / '
               'apm / narr / imperf / comm / g）'),
    ('legacy_value', '**原版值**'),
    ('new_value', '新引擎值'),
    ('match', '**是否一致**'),
    ('perceptible', '**玩家是否可辨**（可辨态）'),
    ('evidence', '证据等级 1-8'),
]


def _hdr(t, w=80):
    print('=' * w)
    print(t)
    print('=' * w)


def cmd_audio(a):
    _hdr('🔑 声音语义（**声音事实 ≠ 音效事件**）')
    print(f'   {AUDIO_RULE}')
    print('\n必录: ' + ' · '.join(AUDIO_FIELDS))
    print(f'\n   {AUDIO_MULTI}')
    print('\n证据: ' + ' · '.join(AUDIO_EVIDENCE))
    print(f'   {AUDIO_WARN}')
    return 0


def cmd_mat(a):
    _hdr('脚步材质（**四段链条**）')
    print(f'   {MAT_CHAIN}')
    print('\n规则:')
    for m in MAT_RULE:
        print(f'   {m}')
    print(f'\n   {MAT_SAMPLE}')
    return 0


def cmd_vert(a):
    _hdr('🔴 垂直定位（**必须独立字段**）')
    print(f'   {VERT_RULE}')
    print(f'\n   {VERT_WHY}')
    print('\n子轨: ' + ' · '.join(VERT_SUB))
    print('\n必测四类: ' + ' · '.join(VERT_TEST))
    print(f'\n   {VERT_GOAL}')
    return 0


def cmd_threat(a):
    _hdr('威胁等级（**按声学角色拆分**）')
    print(f'   {THREAT_RULE}')
    print(f'\n   {THREAT_WHY}')
    print('\n语义标签: ' + ' · '.join(THREAT_TAGS))
    print(f'\n   {THREAT_LORE}')
    return 0


def cmd_gait(a):
    _hdr('步态（**暴露角色状态**）')
    print(f'   {GAIT_RULE}')
    print('\n必录: ' + ' · '.join(GAIT_ITEMS))
    print('\n随哪些量变化: ' + ' · '.join(GAIT_VARY))
    print(f'\n   {GAIT_WARN}')
    print(f'\n   {GAIT_VERIFY}')
    return 0


def cmd_mix(a):
    _hdr('混音可读性（**阈值从原版测**）')
    print(f'   {MIX_RULE}')
    print('\n必录: ' + ' · '.join(MIX_ITEMS))
    print(f'\n   {MIX_TEST}')
    print(f'\n   {MIX_A11Y}')
    return 0


def cmd_growth(a):
    _hdr('🔑 成长（**五通道**）')
    print(f'   {GROWTH_RULE}')
    print('\n五通道:')
    for k, v in GROWTH_FIVE:
        print(f'   {k:<14} {v}')
    print(f'\n   {GROWTH_SILENT}')
    return 0


def cmd_delta(a):
    _hdr('变化方向（**与原版一致**）')
    print(f'   {DELTA_RULE}')
    print('\n方向: ' + ' · '.join(DELTA_DIRS))
    print('\n例子:')
    for e in DELTA_EG:
        print(f'   {e}')
    print(f'\n   {DELTA_WARN}')
    print(f'\n   {DELTA_COMPARE}')
    print(f'\n   {LEVEL_SPLIT}')
    print('\n等级映射字段: ' + ' · '.join(LEVEL_FIELDS))
    return 0


def cmd_unlock(a):
    _hdr('能力解锁（**必须改变世界**）')
    print(f'   {UNLOCK_RULE}')
    print('\n暴露内容: ' + ' · '.join(UNLOCK_ITEMS))
    print('\n警告:')
    for w in UNLOCK_WARN:
        print(f'   {w}')
    return 0


def cmd_avatar(a):
    _hdr('本体演化（**痕迹会说话**）')
    print(f'   {AVATAR_RULE}')
    print('\n字段: ' + ' · '.join(AVATAR_FIELDS))
    print(f'\n   {AVATAR_SCAR}')
    print(f'\n   {AVATAR_WARN}')
    return 0


def cmd_meta(a):
    _hdr('🔴 聚焦生命周期（**唯一能直接导致流失**）')
    print(f'   {META_RULE}')
    print('\n必测事件: ' + ' · '.join(META_EVENTS))
    print('\n每项必答: ' + ' · '.join(META_ASK))
    print(f'\n   {META_EVIDENCE}')
    return 0


def cmd_multi(a):
    _hdr('多显示器（**拓扑 · DPI · 刷新率 · 窗口所有权**）')
    print(f'   {MULTI_RULE}')
    print('\n必录: ' + ' · '.join(MULTI_ITEMS))
    print('\n独占全屏: ' + ' · '.join(MULTI_EXCL))
    print('\n无边框: ' + ' · '.join(MULTI_BORDERLESS))
    print(f'\n   {MULTI_WARN}')
    return 0


def cmd_cap(a):
    _hdr('截图 / 录屏 / 直播（**平台能力清单**）')
    print(f'   {CAP_RULE}')
    print('\n必录: ' + ' · '.join(CAP_ITEMS))
    print(f'\n   {CAP_KEEP}')
    print('\n逐项跑: ' + ' · '.join(CAP_TOOLS))
    return 0


def cmd_share(a):
    _hdr('家庭共享 / 多开 / 多号')
    print(f'   {SHARE_RULE}')
    print('\n必录: ' + ' · '.join(SHARE_ITEMS))
    print(f'\n   {SHARE_WARN}')
    print(f'\n   {SHARE_STEAM}')
    return 0


def cmd_beat(a):
    _hdr('🔑 跨通道节拍偏移（**不是"音频是否同步"**）')
    print(f'   {BEAT_RULE}')
    print('\n通道: ' + ' · '.join(BEAT_CHANNELS))
    print(f'\n   {BEAT_TOL}')
    print(f'\n   {BEAT_METHOD}')
    print(f'\n   {BEAT_TOOL}')
    print('\n`beat_clock` 字段:')
    for k, v in BEAT_CLOCK:
        print(f'   {k:<26} {v}')
    print(f'\n   {BEAT_ONE}')
    return 0


def cmd_wait(a):
    _hdr('等待（**时长 · 反馈 · 控制权 · 退出权**）')
    print(f'   {WAIT_RULE}')
    print('\n种类: ' + ' · '.join(WAIT_KINDS))
    print('\n字段: ' + ' · '.join(WAIT_FIELDS))
    print(f'\n   {WAIT_WARN}')
    return 0


def cmd_apm(a):
    _hdr('操作上限（**输入时域档案**）')
    print(f'   {APM_RULE}')
    print('\n必录: ' + ' · '.join(APM_ITEMS))
    print(f'\n   {APM_WARN}')
    return 0


def cmd_narr(a):
    _hdr('叙事时间（**不只昼夜**）')
    print(f'   {NARR_RULE}')
    print('\n必录: ' + ' · '.join(NARR_ITEMS))
    print(f'\n   {NARR_NAME}')
    print('\n警告:')
    for w in NARR_WARN:
        print(f'   {w}')
    return 0


def cmd_imperf(a):
    _hdr('🔑 刻意坏味（**任何修复都须有偏离许可**）')
    print(f'   {IMPERF_RULE}')
    print('\n清单: ' + ' · '.join(IMPERF_ITEMS))
    print('\n每条必录: ' + ' · '.join(IMPERF_FIELDS))
    print(f'\n   {IMPERF_SPLIT}')
    print(f'\n   {IMPERF_WARN}')
    print(f'\n   {LOWCOST_RULE}')
    print('\n3D: ' + ' · '.join(LOWCOST_3D))
    print('\n老硬件: ' + ' · '.join(LOWCOST_OLD))
    print(f'\n   {LOWCOST_WARN}')
    print('\n处理顺序:')
    for o in LOWCOST_ORDER:
        print(f'   {o}')
    print(f'\n   {LOWCOST_FACE}')
    return 0


def cmd_comm(a):
    _hdr('社群与版本语义')
    print(f'   {WIKI_RULE}')
    print('\n锚点字段: ' + ' · '.join(WIKI_FIELDS))
    print(f'\n   {WIKI_WARN}')
    print(f'\n   {VER_THREE}')
    print('\n版本字段: ' + ' · '.join(VER_FIELDS))
    print('\n警告:')
    for w in VER_WARN:
        print(f'   {w}')
    print(f'\n   {VER_MIN}')
    print(f'\n   {CULTURE_RULE}')
    print('\n条目: ' + ' · '.join(CULTURE_ITEMS))
    print('\n每条必录: ' + ' · '.join(CULTURE_FIELDS))
    print(f'\n   {CULTURE_WARN}')
    return 0


def cmd_g(a):
    _hdr('G 类（**三条总纲**）')
    for k, why in G_EXTRA:
        print(f'\n   【{k}】\n      {why}')
    return 0


def cmd_init(a):
    os.makedirs(os.path.dirname(a.init) or '.', exist_ok=True)
    with open(a.init, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow([k for k, _ in FIELDS])
        w.writerow(['TODO'] * len(FIELDS))
    print(f'已生成意义层表: {a.init}')
    print('\n⚠️ 二十域：audio / mat / vert / threat / gait / growth / delta / '
          'unlock / avatar / meta / multi / cap / share / beat / wait / '
          'apm / narr / imperf / comm / g')
    print('\n⚠️ `perceptible` 列＝**可辨态** —— 只有这层能证明复刻有效')
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

    mismatch, no_legacy, no_perc, no_grade = [], [], [], []
    for i, r in enumerate(rows, 1):
        m = g(r, 'match').lower()
        if m not in ('yes', 'y', 'true', '是', '一致'):
            mismatch.append(i)
        if not g(r, 'legacy_value') or g(r, 'legacy_value') == 'TODO':
            no_legacy.append(i)
        p = g(r, 'perceptible')
        if not p or p == 'TODO':
            no_perc.append(i)
        ev = g(r, 'evidence')
        if not ev or ev == 'TODO':
            no_grade.append(i)
        else:
            d = ev.split('.')[0].strip()
            if d.isdigit() and int(d) >= 7:
                no_grade.append(i)

    print('=' * 76)
    print(f'意义层 · {len(rows)} 条')
    print('=' * 76)
    if mismatch:
        print(f'\n🚫 **不一致** {len(mismatch)} 条（行 {mismatch[:15]}）')
    if no_legacy:
        print(f'\n❌ {len(no_legacy)} 条缺**原版值**（行 {no_legacy[:15]}）')
    if no_perc:
        print(f'\n🚫 {len(no_perc)} 条缺**可辨态**（行 {no_perc[:15]}）')
    if no_grade:
        print(f'\n🚫 {len(no_grade)} 条**证据等级缺失或 ≥7 级**'
              f'（行 {no_grade[:15]}）')

    if not (mismatch or no_legacy or no_perc or no_grade):
        print('\n✅ 意义层：一致、原版值完整、可辨态已验证、证据达标')

    print('\n🔑 **既有方法论容易把「可复现」误判为「可理解」。**')
    print('   **波形·帧时间·伤害数字只能证明"值接近"，不能证明"听得懂"。**')
    print('   🔴 **冲突点不在技术，而在决策权。**')
    return 1 if (a.gate_check and
                 (mismatch or no_legacy or no_perc or no_grade)) else 0


def main():
    ap = argparse.ArgumentParser(description='声音语义与意义层')
    ap.add_argument('--audio', action='store_true')
    ap.add_argument('--mat', action='store_true')
    ap.add_argument('--vert', action='store_true')
    ap.add_argument('--threat', action='store_true')
    ap.add_argument('--gait', action='store_true')
    ap.add_argument('--growth', action='store_true')
    ap.add_argument('--delta', action='store_true')
    ap.add_argument('--unlock', action='store_true')
    ap.add_argument('--avatar', action='store_true')
    ap.add_argument('--meta', action='store_true')
    ap.add_argument('--multi', action='store_true')
    ap.add_argument('--cap', action='store_true')
    ap.add_argument('--share', action='store_true')
    ap.add_argument('--beat', action='store_true')
    ap.add_argument('--wait', action='store_true')
    ap.add_argument('--apm', action='store_true')
    ap.add_argument('--narr', action='store_true')
    ap.add_argument('--imperf', action='store_true')
    ap.add_argument('--comm', action='store_true')
    ap.add_argument('--g', action='store_true')
    ap.add_argument('--init')
    ap.add_argument('--check')
    ap.add_argument('--gate-check', action='store_true')
    a = ap.parse_args()
    fns = {'audio': cmd_audio, 'mat': cmd_mat, 'vert': cmd_vert,
           'threat': cmd_threat, 'gait': cmd_gait, 'growth': cmd_growth,
           'delta': cmd_delta, 'unlock': cmd_unlock, 'avatar': cmd_avatar,
           'meta': cmd_meta, 'multi': cmd_multi, 'cap': cmd_cap,
           'share': cmd_share, 'beat': cmd_beat, 'wait': cmd_wait,
           'apm': cmd_apm, 'narr': cmd_narr, 'imperf': cmd_imperf,
           'comm': cmd_comm, 'g': cmd_g}
    for k, fn in fns.items():
        if getattr(a, k):
            return fn(a)
    if a.init:
        return cmd_init(a)
    if a.check:
        return cmd_check(a)
    print('❌ 需要 --audio / --mat / --vert / --threat / --gait / --growth / '
          '--delta / --unlock / --avatar / --meta / --multi / --cap / '
          '--share / --beat / --wait / --apm / --narr / --imperf / --comm / '
          '--g / --init / --check 之一')
    return 2


if __name__ == '__main__':
    sys.exit(main())
