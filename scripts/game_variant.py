#!/usr/bin/env python3
"""非完整版本态 · 秘籍与开发者菜单 · 非玩家参与者 · 实体载体 ·
错误美学 · 存档控制权（第四十九轮 A–G，含 H）。

**🔑 本轮的核心不是"又一批功能"，而是四套被复刻工作普遍压平为
单一正式版的状态表面**：
> 🔑 **Demo/共享软件/Attract Mode 是独立但可合并的「非完整版本状态机」；
> 秘籍与开发者菜单是带版本 · 输入时序 · 存档标记和成就副作用的「已发布内容」；
> 沙发旁观者 · 代打 · 只看过场者构成「非操作参与者」；
> 说明书 · 地图 · 攻略本 · OST · 艺术集与回函卡是实体版「副内容包」。**

用法:
  game_variant.py --sku     # 🔑 **非完整版本状态机（七态）**
  game_variant.py --inherit # 🔑 **存档继承（带一次性决策与不可逆分支）**
  game_variant.py --attract # **Attract Mode 假操作是刻意编排**
  game_variant.py --cheat   # 🔑 **秘籍是发布内容，不是调试残留**
  game_variant.py --cheat5  # **五层输入窗口**
  game_variant.py --devmenu # **开发者菜单按发布证据分判**
  game_variant.py --watch   # 🔑 **旁观者是无输入权限的第二名玩家**
  game_variant.py --subtitle# **给观众看 ≠ 给玩家听**
  game_variant.py --carrier # 🔑 **实体载体是独立内容包**
  game_variant.py --map     # **纸质地图与数字小地图是两套认知工具**
  game_variant.py --error   # 🔑 **错误画面可能是玩家记得的风格化表达**
  game_variant.py --saveown # **存档控制权（玩家手动备份是流程延伸）**
  game_variant.py --h       # H 类
  game_variant.py --init ledger/variant49.csv
  game_variant.py --check ledger/variant49.csv --gate

退出码: 0 通过 / 1 缺项 / 2 用法错误
"""
import argparse
import csv
import os
import sys

# 🔑 A 非完整版本态
SKU_RULE = '🔑 **Demo/共享软件/Attract Mode 不是正式版的截短，'
'而是带独立**权限 · 内容 · 存档 · 结束协议**的产品形态。**'
SKU_STATES = ['retail', 'demo', 'trial', 'kiosk', 'press',
              'evaluation', 'attract']
SKU_NO = '🔑 状态机至少含七态。🔴 **不能只把体验版资源留在未引用关卡里**'
'（玩家会失去"第一次的分界线"）；🔴 **也不能按正式版照原样解锁**'
'（失去不可逆的资格感与资源稀缺性）'
MH_SAMPLE = '🔑 官方体验手册样本：体验版可玩**序章至第 1 章第 3 关**，'
'🔑 **不能使用在线功能和拍照模式**；'
'🔑 **可取得勋章但无法取得对应奖杯，勋章却会随存档继承**；选项设置也会继承'
MH_SPLIT = '🔑 至少要把 `playable_range` · `system_lock` · `reward_transfer` · '
'`trophy_transfer` · `setting_transfer` **拆开记录**。'
'🔴 **不能写死"奖励一律可继承"或"一律不可继承"** —— '
'该例中**勋章与奖杯走了两条规则**'
INHERIT_RULE = '🔑 **存档继承是带一次性决策和不可逆分支的协议，'
'不是启动时的复制文件。**'
SAO_SAMPLE = '🔑 官方迁移指南样本：要求正式版为最新版；'
'🔑 **首次检测到 Demo 存档时询问是否继承，需长按"Confirm"，'
'且所有槽位一起迁移**；'
'🔑 **一旦选择不继承并确认，后续启动不再提示，'
'必须把正式版全部槽位删掉再新建存档才重新开放机会**；'
'🔑 **禁止删除设备上的 Demo 存档 · 仅限同平台迁移**；'
'🔑 **Demo 继承存档不能切换到某模式，该模式若已解锁只能在第二或之后存档选择**'
INHERIT_STATES = [
    ('`demo_save_detected`', '检测时机 · 账号/用户 · 平台 · 路径 · Demo 版本',
     '只检查是否存在文件'),
    ('`latest_full_version_required`', '最低版本 · 当前版本 · 稍后补丁是否仍可迁',
     '要求网络或自动升级'),
    ('`carry_over_prompt`', '文案 · 默认项 · 是否可取消 · **长按确认**',
     '静默迁移或仅一次 Yes/No'),
    ('`do_not_carry_over_seen`', '是否持久化 · 能否重试 · **重试的前置破坏**',
     '每启动询问或永久隐藏无恢复'),
    ('`mode_lock_after_transfer`', '锁定模式 · 解锁前置 · 是否影响新档',
     '继承后无差别全开'),
    ('`platform_boundary`', '同平台定义 · 账号绑定 · **跨代主机**',
     '用云端账号假定可跨平台'),
    ('`option_transfer`', '画质 · 声音 · 控制 · 语言 · 隐私', '只迁剧情进度'),
]
ATTRACT_RULE = '🔑 **Attract Mode 的假操作是刻意编排，不是录制或 AI 掉帧。**'
ATTRACT_SHOW = '🔑 它属于"玩家第一次看到的内容"，可能展示**实际玩不到的关卡 · '
'过早出现的武器 · 解谜答案 · 虚构的跨关路径**，'
'也可能给"假玩家"**开挂或故意失败**'
ATTRACT_EG = '🔑 历史样本：某作会出现"**Coin detected in pocket**"，'
'某作使用**投币语音**，🔑 **投币提示本身也是循环的一部分**'
ATTRACT_NO = '🔴 **若复刻把它做成真实回放 · 可接管演示或随机 AI，'
'玩家会获得原版不存在的信息**，也会失去原版明确的"演示不是真玩"边界'
ATTRACT_REC = '🔑 逐帧记录：循环顺序 · 每张卡时间 · 输入序列 · 可接管窗口 · '
'投币/开始提示 · **假操作是否有无敌或资源作弊** · 是否展示谜题答案 · '
'演示结束是否回到标题 · 是否随版本更换 · 是否响应手柄按键 · '
'**是否能打出开发房间**。🔴 **不能只截一张标题画面**'
TRIAL_RULE = '🔑 **共享软件/试玩版的分发逻辑与中断点是真实叙事节奏** —— '
'记限时 · 限时区 · 次数锁 · 结束画面 · 返回标题/桌面的行为 · 重试成本 · '
'是否弹出商店 · **是否允许继续观看未解锁过场** · 是否保留最后输入状态'

# 🔑 B 秘籍
CHEAT_RULE = '🔑 **秘籍是发布内容 · 文化资产和潜在 competitive rule，'
'而不是调试代码残留。**'
CHEAT_NO = '🔑 复刻**删秘籍会丢失记忆**；🔴 **把秘籍全部挪成官方辅助选项，'
'也会消除原版的「口令感 · 风险标记 · 输入肌肉记忆 · 隐蔽性」**'
SIMS = '🔑 官方可复用语义边界：PC/Mac 用 `Ctrl+Shift+C` 打开控制台，'
'🔑 **主机需同时按四个肩键**；'
'🔑 **`testingcheats true` 会关闭「当前存档」的成就和奖杯，'
'但不影响其他存档**；🔑 **建造模式秘籍不在该限制内**；'
'🔑 部分实时秘籍要求**主机长按「○」再按「×」（Xbox 长按「B」再按「A」）**'
CHEAT_5 = ['**能否打开控制台/菜单**',
           '**序列识别**（并行按键 · 顺序按键 · 按住 · 双击 · 暂停中 · 输入法 · 控制器布局）',
           '**执行前提**（必须在存档 · 某章节 · 某场景）',
           '**副作用写入时机**（立即 · 下一次保存 · 退出到标题后）',
           '**恢复**（重启 · 改回控制台变量 · 新建存档 · 永久存档位）']
CHEAT_IME = '🔑 **重制常用的现代输入系统若忽略 IME · 手柄连发 · 宏 · '
'键盘布局，会令旧序列不可用**'
CHEAT_FIELDS = '输入序列 · 设备 · 布局 · 暂停状态 · 版本 · 区服 · 语言 · '
'**成就/统计/排行榜/云同步/Mod 权限** · 存档标记 · 可撤销性 · 副作用 · 社区玩法'
DEV_MENU = '🔑 **开发者菜单是否算秘籍，要按发布证据而不是开发者意图决定** —— '
'🔑 若**正式版安装目录 · 光盘 · 调试构建或公开版本**中存在可触发的开发者菜单，'
'应记为 must-match；🔴 **若只存在于内部调试构建 · 测试版或泄露版本，'
'则归入幽灵内容/版本地层，不可宣称玩家可稳定触发**'
CHEAT_BOUND = '🔑 **"作弊"的边界应写成规则集而非道德判断** —— '
'单机应保留秘籍；本地多人可配置"主机禁用/投票/仅观众模式"；'
'排行榜与竞速可要求未开启秘籍；🔑 **联机应明确反作弊是否把单机秘籍误判**'
'（是否隔离房间）。🔴 **不能把"使用秘籍"无条件等同违规**'
CHEAT_CULT = '🔑 noclip 观光 · 无敌刷钱 · 低重力挑战**若已有稳定社区意义，应保留入口**；'
'🔴 若会改变唯一隐藏事件触发 · 永久毁掉关键道具 · '
'令已通关存档进入不可退出状态，**必须记录副作用和可逆路径**'

# 🔑 C 非玩家参与者
WATCH_RULE = '🔑 **沙发旁观者会参与决策 · 记忆路线 · 辨认风险并承担情绪成本。**'
WATCH_Q = '🔑 已覆盖的第三空间没有充分回答：🔑 **看的人如何知道发生了什么 · '
'如何给建议 · 玩家为何会听从 · 如果两人意见不同谁有最终权**'
WATCH_SCENES = '配偶/室友/孩子观看 · 直播观众投票 · 父母带孩子玩 · '
'病房中玩给别人看 · 代打 · 访客完成难关 · **玩家把游戏当电影放映**'
WATCH_FIELDS = '🔑 玩家视口 · **观众可见 HUD** · 只有语音才知道的信息 · '
'隐私遮罩 · 字幕 · 重要音效文字 · **观众建议通道**应分别记录'
WATCH_DECIDE = '🔑 最细的决策字段：**观众是否能看见完整地图/生命值/库存** · '
'**玩家能否一键展示物品** · 旁人喊"往左"是否对应玩家本地化后的控制 · '
'**投票能否仅建议** · **代打时是否保留原玩家档案 · 统计 · 时间承诺** · '
'故事放映时是否可跳过战斗 · 自动推进 · 隐藏无关 HUD'
SUB_RULE = '🔑 **字幕规范证明"给观众看"和"给玩家听"是两个不同信息集。**'
SUB_XBOX = '🔑 官方准则要求**所有语音有字幕**，🔑 **重要非语音声音有说明**'
'（歌曲 · 歌词 · 枪声 · **脚步** · **敲门方向**）；'
'🔑 还应标出**发言者和收音状态**，例如"**(on radio)**"，'
'🔑 **可用颜色但不得只依赖颜色**'
SUB_FIELDS = '每条语音/声效记**发言者 · 方向 · 现场/远程 · 情绪或语气**；'
'每个字幕记**字体 · 字号 · 安全区 · 描边 · 行宽 · 停留时间 · '
'最大同屏行数 · 暂停/快进/回看**'
ACCESS_PURPOSE = '🔑 新增 `accessibility_modes.original_purpose`，'
'区分「**官方无障碍**」「**社区速通/观光**」「**家长代打**」'
'「**观众放映**」。🔴 **不能合并成 `easy_mode`**'
ACCESS_NO = '🔑 故事模式/辅助难度**不是把游戏变简单**，而是降低**输入负荷 · '
'信息密度 · 反应窗口 · 失败重启成本**。'
'🔴 **若复刻把原版"极低难度+可跳过战斗"删掉，只留标准难度，'
'就破坏了只关心剧情者 · 操作能力波动者 · 共同观看者的真实入口**'
VOTE_NO = '🔑 **观众介入不是把聊天直接改成游戏输入** —— '
'推荐在游戏内建立**只读事件总线 · 提案队列 · 批准状态**，'
'🔴 **避免聊天刷屏造成误触**。'
'🔑 直播插件的**投票 · 概率控制 · 权限与作弊必须由游戏服务端或本地仲裁，'
'🔴 不能信任浏览器来源**'

# 🔑 D 实体载体
CARRIER_RULE = '🔑 **原版的"游戏"曾包括纸 · 声音 · 盒子和回函卡，'
'复刻不能只剩可执行文件。**'
CARRIER_FIELDS = '`carrier_id` · `edition_sku` · `region` · `language` · '
'`print_run_known` · **`physical_dimensions`** · **`material`** · '
'**`fold_or_spread_behavior`** · **`navigation_affordance`** · `contents` · '
'**`known_errors`** · `scans` · `license_status`'
CARRIER_EG = '🔑 布质地图要记**经纬折痕 · 边缘磨损 · 挂起方式 · 两人摊开**；'
'纸质说明书要记**装订 · 插页 · 快速参考卡 · 控制表的位置**；'
'🔑 **回函卡要记双面文案 · 邮寄说明 · 抽奖/保修承诺，🔴 不只扫描正反面**'
MAP2_RULE = '🔑 **纸质地图与数字小地图是两套不同认知工具。**'
MAP2_DIFF = '🔑 纸质地图可**一眼看到全局 · 用物理尺度比较距离 · 以手指标记 · '
'折出当前区域 · 让旁观者同时指出目标**；'
'小地图通常**跟随玩家 · 强调相对方向和即时危险**'
MAP2_NO = '🔑 若复刻把纸图缩成角落小地图，🔴 **玩家失去摊开浏览**；'
'若只做全屏地图，🔴 **又失去"一边玩一边瞥见局部"的视线切换**。'
'🔑 理想做法是**同时保留"原版实体浏览物"和现代辅助地图，而不是二选一**'
MAP2_FIELDS = '可打开方式 · 默认是否展开 · **地图是否固定北向** · '
'是否可双指缩放 · **折痕是否被数字化** · 是否保留原符号 · '
'**是否显示玩家已手绘标记**'
DIGITAL_SUB = '🔑 **安装目录 PDF · 画廊 · 音乐鉴赏是实体载体的最低数字化替身，'
'但仍需逐页/逐轨比对** —— 新增 `digital_substitute_for`'
OST_RULE = '🔑 **OST 不应只记录曲目列表。** 玩家在车里 · 播放器 · 铃声 · '
'二创中听到主题，会把**情绪与特定场景 · 年份和版本绑定**；'
'🔴 复刻若改编曲 · 改采样 · 改版权名 · 删除间奏或重新切分，'
'会破坏"**游戏外记忆**"'
OST_FIELDS = '每首记**播放触发 · 版本差异 · 循环段落 · 淡入淡出 · '
'音轨文件名 · 是否有隐藏音轨 · CD 内页与场景对应**'
PRINT_ERR = '🔑 **说明 · 包装 · 回函卡中的错误信息同样是表现** —— '
'**印刷错别字 · 旧电话 · 过期网址 · 不同语言版本差异 · 回函卡奖励 · '
'同捆广告**若原版真实存在，应记其**印刷批次与版本关系**。'
'🔴 **改错字 · 改链接 · 删除广告可能让复刻更"正确"，却也删除时代地层**'

# 🔑 E/F/G
ERR_RULE = '🔑 **错误画面不是必须尽快消灭的缺陷，'
'而可能是玩家记得的风格化表达。**'
ERR_EG = '🔑 历史样本：某作曾把**系统卡版本错误做成一个可互动的迷你关卡**，'
'并在后续 PSP 重制版**保留**；某作用**图片配文字与语音**解释系统卡问题'
ERR_KINDS = '介质错误 · 版本/区域错误 · 存档损坏 · 内存不足 · 网络失败 · '
'DLC 缺失 · 安装未完成 · 输入设备断开 · 反盗版画面 · 开发期遗留错误 · '
'**玩家主动触发边界**'
ERR_FIELDS = '错误码 · 原文 · **字体 · 字号 · 字重 · 字符集** · 图标 · 边框 · '
'颜色 · 布局 · 背景 · **音乐 · 音效** · 震动力度 · 时长 · 自动重试 · '
'是否可取消 · **是否破坏存档** · 退出后回到哪里'
ERR_CD = '🔑 对 CD/DVD/卡带时代还要记**读盘失败次数 · 重试节奏 · '
'光驱噪声 · 等待画面**'
ERR_NO = '🔴 **不能把原版的"请插入光盘" · 蓝屏 · 未响应 · 假磁盘图标'
'直接改成云游戏断线提示** —— 这些**介质动作是历史接口**'
SAVE_RULE = '🔑 **玩家手动备份 · 命名 · 轮换 · 分享存档，'
'是正式游戏流程的延伸。**'
SAVE_EG = '🔑 复制到 U 盘 · 按日期命名 · 保留"**死亡前**""**选择前**"'
'"**结婚前**""**最终 BOSS 前**"等**个人里程碑** · 压缩加密 · 多设备迁移 · '
'论坛分享 · 编辑 · 比较'
SAVE_NO = '🔑 若只提供**单槽自动云存档**，🔴 **会消除玩家的分支管理与叙事仪式**；'
'🔴 **若加密 · 签名或隐藏路径使玩家无法复制，也破坏长期保存**'
SAVE_FIELDS = '路径与平台 · 单文件/目录 · 注册表 · 校验 · 版本字段 · '
'兼容范围 · 未迁移字段 · 命名惯例 · 备份前后哈希 · 玩家可见性 · '
'**可复制性** · 加密 · 云冲突 · 分享安全红线'
SAVE_FEAR = '🔑 **原版"损坏恐惧"往往由不可见性和不可逆性组成** —— '
'记存档槽是否可见 · 哈希/校验是否显示 · 是否自动备份 · '
'**覆盖前是否有确认** · **断电后是否双写** · **版本不兼容时是否提示或静默重置**'
SAVE_NO2 = '🔴 **禁止单槽强制自动保存 · 自动云同步覆盖 · 加密隐藏 · 禁止导出**；'
'🔑 现代增强可另加导出/导入 · 快照 · 冲突比较，'
'🔴 **但原版的槽位语义与风险感必须保留**'

H_ITEMS = [
    ('**H1 粉丝翻译 · 汉化补丁 · Romhack 不冒充主干**',
     '🔑 IPS/BPS/UPS 补丁格式与 Asar 等工具是**真实的版本变体载体**，'
     '🔴 **但通常属于修改版 · 翻译版或玩家工具链，除非原作官方发布或自己项目'
     '明确拥有权利，否则不属于 must-match 原文**。'
     '字段上可扩展 `variant_builds` 的 `origin`，🔴 **不得把社区补丁当官方分支**'),
    ('**H2 Credits / 标题画面 / 读盘提示只做小幅增强**',
     '🔑 复刻署名指南要求**原始团队列于新团队之前，且两组 credits 应同时可见**。'
     '🔑 Credits 记**滚动速度 · 分组 · 离场交互 · 音乐 · 跳过规则 · 版本差异 · '
     '原团队优先**；标题画面记**版本号 · 宣传语 · Kickstarter/评测/体验/正式版差异 · '
     '背景动画 · Attract 入口**；读盘画面记**提示文案 · 小知识 · 音效 · '
     '加载完成反馈 · 可操作时间**'),
    ('**H3 安装体积与磁盘管理是真实但低优先级**',
     '🔑 玩家会记住"**装不下**""**需换盘**""**下载内容必须顺序安装**"'
     '"**删盘后才能读另一张**""**临时空间是游戏两倍**"。'
     '新增 `installation_media.footprint`：原始介质数量 · 安装步骤 · 可用空间 · '
     '临时空间 · 可选择内容 · DLC 依赖 · 删除行为。'
     '🔴 **不需要扩成独立方法论章节**'),
    ('**H4 玩家自制攻略图 · 手绘地图 · 社区排序是外部文化**',
     '🔑 可记其**存在 · 时间 · 平台 · 传播路径**，'
     '🔴 **除非是自己项目的输入材料，不应纳入 must-match**。'
     '游戏外音乐使用 · 铃声 · 二创同样只记"是否形成外部记忆"与版权风险'),
    ('**H5 试玩机/Kiosk · Easter egg · 开发者房间 · 媒体评测版：证据不足**',
     '🔑 Kiosk 可能有**不同标题 · 无限币 · 限时 · 不可存档 · 重置流程 · '
     '投币音 · 店员菜单 · Attract 循环**，🔴 **但公开规范稀少**。'
     '🔑 建议下一轮集中补强：**只做 Kiosk/评测版 · 反盗版屏 · Credits 演化'
     '三张状态图，避免继续发散**'),
]

CONFLICTS = [
    '❌ **把单一完整版当作唯一产品态**',
    '❌ **启动正式版自动覆盖体验版档**（静默迁移）',
    '❌ 自动升级并覆盖体验版存档；**悄悄增加恢复安全网**',
    '❌ **移除秘籍/开发者菜单**；把秘籍改为一次性内购解锁；自动关闭秘籍后成就',
    '❌ **把调试变量名本地化 · 单位/资源字段改漂亮 · 重排菜单层级**',
    '❌ **用统一无障碍开关覆盖故事模式**（合并成 `easy_mode`）',
    '❌ **把数字小地图等同于纸质地图**（二选一而非并存）',
    '❌ 统一做干净化 PDF · 多语言说明合并成单一现代帮助页 · 用 Wiki 链接替代随盘文档',
    '❌ **替换原版错误弹窗为操作系统通用对话框**',
    '❌ 把"请插入光盘/蓝屏/未响应"改成云游戏断线提示',
    '❌ **单槽强制自动保存 · 自动云同步覆盖 · 加密隐藏 · 禁止导出**',
    '❌ 在错误后**自动从云端救回**原版会清空的槽位（除非增强层且有明确切换）',
    '❌ **把 Attract Mode 做成真实回放 · 可接管演示或随机 AI**',
    '❌ **把社区补丁当官方分支**；把外部文化纳入 must-match',
    '❌ **把"使用秘籍"无条件等同违规**',
]

FIELDS = [
    ('item_id', '项编号'),
    ('domain', '域（sku / inherit / attract / cheat / cheat5 / devmenu / '
               'watch / subtitle / carrier / map / error / saveown / h）'),
    ('legacy_value', '**原版值**'),
    ('new_value', '新引擎值'),
    ('match', '**是否一致**'),
    ('variant_evidence', '**版本/载体证据**（介质或实测）'),
    ('evidence', '证据等级 1-8'),
]


def _hdr(t, w=80):
    print('=' * w)
    print(t)
    print('=' * w)


def cmd_sku(a):
    _hdr('🔑 非完整版本状态机（**七态**）')
    print(f'   {SKU_RULE}')
    print('\n七态: ' + ' · '.join(SKU_STATES))
    print(f'\n   {SKU_NO}')
    print(f'\n   {MH_SAMPLE}')
    print(f'\n   {MH_SPLIT}')
    print(f'\n   {TRIAL_RULE}')
    return 0


def cmd_inherit(a):
    _hdr('🔑 存档继承（**带一次性决策与不可逆分支**）')
    print(f'   {INHERIT_RULE}')
    print(f'\n   {SAO_SAMPLE}')
    print('\n七项状态:')
    for k, v, bad in INHERIT_STATES:
        print(f'\n   【{k}】\n      记: {v}\n      🔴 误实现: {bad}')
    return 0


def cmd_attract(a):
    _hdr('Attract Mode（**假操作是刻意编排**）')
    print(f'   {ATTRACT_RULE}')
    print(f'\n   {ATTRACT_SHOW}')
    print(f'\n   {ATTRACT_EG}')
    print(f'\n   {ATTRACT_NO}')
    print(f'\n   {ATTRACT_REC}')
    return 0


def cmd_cheat(a):
    _hdr('🔑 秘籍（**发布内容，不是调试残留**）')
    print(f'   {CHEAT_RULE}')
    print(f'\n   {CHEAT_NO}')
    print(f'\n   {SIMS}')
    print(f'\n字段: {CHEAT_FIELDS}')
    print(f'\n   {CHEAT_BOUND}')
    print(f'\n   {CHEAT_CULT}')
    return 0


def cmd_cheat5(a):
    _hdr('五层输入窗口')
    for i, s in enumerate(CHEAT_5, 1):
        print(f'   {i}. {s}')
    print(f'\n   {CHEAT_IME}')
    return 0


def cmd_devmenu(a):
    _hdr('开发者菜单（**按发布证据分判**）')
    print(f'   {DEV_MENU}')
    return 0


def cmd_watch(a):
    _hdr('🔑 非玩家参与者（**无输入权限的第二名玩家**）')
    print(f'   {WATCH_RULE}')
    print(f'\n   {WATCH_Q}')
    print(f'\n场景: {WATCH_SCENES}')
    print(f'\n   {WATCH_FIELDS}')
    print(f'\n   {WATCH_DECIDE}')
    print(f'\n   {ACCESS_PURPOSE}')
    print(f'\n   {ACCESS_NO}')
    print(f'\n   {VOTE_NO}')
    return 0


def cmd_subtitle(a):
    _hdr('字幕（**给观众看 ≠ 给玩家听**）')
    print(f'   {SUB_RULE}')
    print(f'\n   {SUB_XBOX}')
    print(f'\n   {SUB_FIELDS}')
    return 0


def cmd_carrier(a):
    _hdr('🔑 实体载体（**独立内容包**）')
    print(f'   {CARRIER_RULE}')
    print(f'\n字段: {CARRIER_FIELDS}')
    print(f'\n   {CARRIER_EG}')
    print(f'\n   {PRINT_ERR}')
    print(f'\n   {OST_RULE}')
    print(f'\n   {OST_FIELDS}')
    return 0


def cmd_map(a):
    _hdr('纸质地图 vs 数字小地图')
    print(f'   {MAP2_RULE}')
    print(f'\n   {MAP2_DIFF}')
    print(f'\n   {MAP2_NO}')
    print(f'\n字段: {MAP2_FIELDS}')
    print(f'\n   {DIGITAL_SUB}')
    return 0


def cmd_error(a):
    _hdr('🔑 错误美学（**可能是风格化表达**）')
    print(f'   {ERR_RULE}')
    print(f'\n   {ERR_EG}')
    print(f'\n十一类: {ERR_KINDS}')
    print(f'\n字段: {ERR_FIELDS}')
    print(f'\n   {ERR_CD}')
    print(f'\n   {ERR_NO}')
    return 0


def cmd_saveown(a):
    _hdr('🔑 存档控制权（**手动备份是流程延伸**）')
    print(f'   {SAVE_RULE}')
    print(f'\n   {SAVE_EG}')
    print(f'\n   {SAVE_NO}')
    print(f'\n字段: {SAVE_FIELDS}')
    print(f'\n   {SAVE_FEAR}')
    print(f'\n   {SAVE_NO2}')
    return 0


def cmd_h(a):
    _hdr('H 类（**五项**）')
    for k, why in H_ITEMS:
        print(f'\n   【{k}】\n      {why}')
    return 0


def cmd_init(a):
    os.makedirs(os.path.dirname(a.init) or '.', exist_ok=True)
    with open(a.init, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow([k for k, _ in FIELDS])
        w.writerow(['TODO'] * len(FIELDS))
    print(f'已生成变体与载体表: {a.init}')
    print('\n⚠️ 十三域：sku / inherit / attract / cheat / cheat5 / devmenu / '
          'watch / subtitle / carrier / map / error / saveown / h')
    print('\n⚠️ `variant_evidence` 列＝**版本/载体证据**（介质或实测）')
    print('\n🔑 新模板：non_retail_product_states · sku_content_matrix · '
          'demo_save_transfer_state_machine · demo_input_script · '
          'cheats_and_dev_menus · cheat_version_validity · '
          'community_cheat_usage · non_player_participants · '
          'audience_information_layer · physical_carriers · '
          'error_aesthetics · save_file_ownership')
    print('\n🔑 新脚本：capture_attract_session · '
          'record_cheat_input_sequence · simulate_storage_fault · '
          'normalize_save_snapshot')
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

    mismatch, no_legacy, no_var, no_grade = [], [], [], []
    for i, r in enumerate(rows, 1):
        m = g(r, 'match').lower()
        if m not in ('yes', 'y', 'true', '是', '一致'):
            mismatch.append(i)
        if not g(r, 'legacy_value') or g(r, 'legacy_value') == 'TODO':
            no_legacy.append(i)
        p = g(r, 'variant_evidence')
        if not p or p == 'TODO':
            no_var.append(i)
        ev = g(r, 'evidence')
        if not ev or ev == 'TODO':
            no_grade.append(i)
        else:
            d = ev.split('.')[0].strip()
            if d.isdigit() and int(d) >= 7:
                no_grade.append(i)

    print('=' * 76)
    print(f'变体与载体层 · {len(rows)} 条')
    print('=' * 76)
    if mismatch:
        print(f'\n🚫 **不一致** {len(mismatch)} 条（行 {mismatch[:15]}）')
    if no_legacy:
        print(f'\n❌ {len(no_legacy)} 条缺**原版值**（行 {no_legacy[:15]}）')
    if no_var:
        print(f'\n🚫 {len(no_var)} 条缺**版本/载体证据**（行 {no_var[:15]}）')
    if no_grade:
        print(f'\n🚫 {len(no_grade)} 条**证据等级缺失或 ≥7 级**'
              f'（行 {no_grade[:15]}）')

    if not (mismatch or no_legacy or no_var or no_grade):
        print('\n✅ 变体与载体层：一致、原版值完整、版本载体证据已验证、证据达标')

    print('\n🔑 **非完整版本是独立产品形态，不是正式版的截短。**')
    print('   🔑 **秘籍是发布内容，删掉会丢失记忆。**')
    print('   🔑 **旁观者是无输入权限的第二名玩家。**')
    print('   🔴 **错误画面与实体载体也是作品的一部分。**')
    return 1 if (a.gate_check and
                 (mismatch or no_legacy or no_var or no_grade)) else 0


def main():
    ap = argparse.ArgumentParser(description='变体与载体层：非完整版/秘籍/载体')
    ap.add_argument('--sku', action='store_true')
    ap.add_argument('--inherit', action='store_true')
    ap.add_argument('--attract', action='store_true')
    ap.add_argument('--cheat', action='store_true')
    ap.add_argument('--cheat5', action='store_true')
    ap.add_argument('--devmenu', action='store_true')
    ap.add_argument('--watch', action='store_true')
    ap.add_argument('--subtitle', action='store_true')
    ap.add_argument('--carrier', action='store_true')
    ap.add_argument('--map', action='store_true')
    ap.add_argument('--error', action='store_true')
    ap.add_argument('--saveown', action='store_true')
    ap.add_argument('--h', action='store_true')
    ap.add_argument('--init')
    ap.add_argument('--check')
    ap.add_argument('--gate-check', action='store_true')
    a = ap.parse_args()
    fns = {'sku': cmd_sku, 'inherit': cmd_inherit, 'attract': cmd_attract,
           'cheat': cmd_cheat, 'cheat5': cmd_cheat5, 'devmenu': cmd_devmenu,
           'watch': cmd_watch, 'subtitle': cmd_subtitle,
           'carrier': cmd_carrier, 'map': cmd_map, 'error': cmd_error,
           'saveown': cmd_saveown, 'h': cmd_h}
    for k, fn in fns.items():
        if getattr(a, k):
            return fn(a)
    if a.init:
        return cmd_init(a)
    if a.check:
        return cmd_check(a)
    print('❌ 需要 --sku / --inherit / --attract / --cheat / --cheat5 / '
          '--devmenu / --watch / --subtitle / --carrier / --map / --error / '
          '--saveown / --h / --init / --check 之一')
    return 2


if __name__ == '__main__':
    sys.exit(main())
