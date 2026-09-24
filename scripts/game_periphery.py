#!/usr/bin/env python3
"""元游戏外围层 · 玩家自救 · 物理外设 · 游玩环境考古 · 元进度 ·
玩家作品 · 通关后世界（第四十六轮 A–G，含 H 十五条）。

**🔑 本轮的主判断**：
> 🔑 **原版"游戏"并不止于进程内画面** —— 还包括启动器 · 覆盖层 ·
> 平台账号 · 校准 · 失败恢复 · 环境噪声 · 玩家肌肉记忆。

🔑 共同点：**玩家在这些界面里花的时间可能比游戏内还多**。

用法:
  game_periphery.py --meta    # 🔑 **元游戏外围层（不是皮肤，是有状态服务）**
  game_periphery.py --gog     # 🔑 **客户端可缺是硬要求，不是容错彩蛋**
  game_periphery.py --eos     # **身份与数据是两条链**
  game_periphery.py --save    # 🔑 **玩家自救＝第二控制流**
  game_periphery.py --repair  # **先快照 → 后报告 → 再请求确认**
  game_periphery.py --device  # 🔑 **物理外设（四层抽象）**
  game_periphery.py --wheel   # **方向盘 / 光枪 / 跳舞毯**
  game_periphery.py --env     # 🔑 **游玩环境考古（客厅≠书房）**
  game_periphery.py --wcag    # **WCAG 2.2 作可测量尺度**
  game_periphery.py --legacy  # **元进度四层**
  game_periphery.py --work    # 🔑 **玩家作品出处链（照片模式不是截图键）**
  game_periphery.py --ending  # 🔑 **通关后的世界是叙事状态机**
  game_periphery.py --h       # H 类十五条
  game_periphery.py --init ledger/periphery.csv
  game_periphery.py --check ledger/periphery.csv --gate

退出码: 0 通过 / 1 缺项 / 2 用法错误
"""
import argparse
import csv
import os
import sys

# 🔑 A 元游戏外围层
META_RULE = '🔑 **外围系统必须按状态机记录，而不能只列功能清单。**'
META_EG = '玩家在**启动器 · 好友列表 · 成就面板 · 云存档 · 通知中心 · '
'商店页 · 社区中心 · 工坊 · 排行榜 · 覆盖层**之间来回切换；'
'🔑 每一步都有**在线/离线 · 登录/未登录 · 授权/未授权 · 缓存命中/失效 · '
'上传/下载 · 冲突/成功**等分支'
META_WARN = '🔴 **重制若只迁移游戏进程**，玩家会看到功能"在"，'
'却在具体环境里出现**错误文案 · 无限转圈 · 双重弹窗 · '
'焦点被覆盖层抢走 · Alt-Tab 后输入锁死**'
META_13 = ['`launcher`', '`achievement_panel`', '`cloud_save_ui`',
           '`friends_list`', '`notification_center`', '`store_page`',
           '`community_hub`', '`workshop`', '`leaderboard`',
           '`anti_cheat_client`', '`drm_boot`', '`mod_manager`',
           '`overlay`']
META_FIELDS = ['平台', '原接口', '**进程内外边界**', '显示文本', '图标/音效',
               '触发延迟', '**失败文案**', '重试策略', '**离线文本**',
               '焦点策略', '权限请求', '**崩溃时是否残留托盘/驱动**',
               '版本与地区']
META_ORDER = '🔑 取证顺序必须是「**事件日志 → 网络/进程状态 → UI 录制 → '
'配置与缓存哈希 → 玩家口述**」，🔴 **不能从 UI 截图倒推内部契约**'
GOG_RULE = '🔑 **"客户端可缺"是硬要求，而不是容错彩蛋。**'
GOG_FACTS = [
    '🔑 若 `IGalaxy::Init()` 失败，**游戏不应停止加载**，'
    '🔑 **只应禁用成就 · 排行榜 · 统计 · 多人**',
    'GOG 客户端即使已安装运行，**服务器认证也应可选**',
    '🔑 **失去服务器连接应无缝切到离线模式**',
    '🔑 **成就带本地缓存，恢复联网后再同步**',
    '覆盖层还可收发多人邀请',
]
GOG_ASK = '🔑 所以像素记录不能只写"支持成就"，而要写：'
'**断网后首次解锁是否弹通知 · 弹窗延迟 · 角标数量 · '
'重启后是否仍在本地队列 · 联网恢复是静默还是二次弹窗 · '
'失败提示是否暴露账号/网络错误**'
EOS_RULE = '🔑 **"跨平台"是身份和数据两条不同链。**'
EOS_TWO = '🔑 好友 · 状态 · 社交覆盖层归到**需要 Epic 账号或代理账号**的层；'
'而**多人 · 玩家数据 · 成就 · 统计 · 排行榜**可用**支持的第三方身份**'
EOS_IDS = [
    '`platform_account_id`（平台原生）',
    '`namespace_account_id`（平台生态）',
    '`publisher_account_id`（发行商）',
    '`game_account_id`（本作）',
    '`character_id`',
]
EOS_CROSS = '🔑 跨游戏遗产还必须记录**允许迁移的是统计 · 外观 · 选择 · '
'权利还是仅"识别码"**'
EOS_GOG = '🔑 能跨平台联机**不自动等于**账号 · 好友 · 邀请 · 进度全面打通'

# 🔑 B 玩家自救
SAVE_RULE = '🔑 **玩家自救是真实的第二控制流，不是"修电脑的噪声"。**'
SAVE_KEY = '🔑 关键**不是"有没有验证文件完整性"**，而是玩家在**某一版本 · '
'某一显卡 · 某一系统 · 某一网络**下，**按什么顺序执行**'
SAVE_SEQ = ['先重启', '切兼容模式', '删配置', '验证文件', '清缓存',
            '重装运行库', '关闭覆盖层', '禁 Mod', '回滚驱动',
            '替换 DLL', '用第三方修复工具', '直接重装']
SAVE_FIELDS = ['`trigger_observation`', '**`precondition_hash`**',
               '`step_sequence`', '`expected_observable_change`', '`risk`',
               '`evidence_url`', '`first_seen`', '`last_seen`',
               '**`origin`（官方/社区/玩家自创）**',
               '`becomes_obsolete_in_version`']
SAVE_KEEP = '🔑 必须保留"**原版故障是否迫使玩家执行**"的证据，'
'🔴 **不能因重制版没有该故障就删掉条目**'
SAVE_MODE = '🔑 若目标为像素级复刻，应提供 `legacy_workaround_mode`；'
'若目标为重制，则把"已消除的必需自救"另存 `historical_pain`'
SAVE_WARN = '🔑 **"消除原版必需的痛苦"不等于错误；'
'🔴 但"为了让新版本更干净而删掉玩家共同语言"是偏离。**'
REPAIR_RULE = '🔑 **先快照 → 后报告 → 再请求确认。**'
REPAIR_3 = [
    ('`manifest.json`', '版本 · 相对路径 · 大小 · 分块/哈希 · 来源 · 签名状态'),
    ('`repair_report.json`', '**缺失 · 大小不符 · 哈希不符 · 权限错误 · '
     '设备占用**'),
    ('`repair_plan.json`', '下载项 · 预计字节 · 可恢复项 · **危险项**'),
]
REPAIR_NO = '🔴 **绝不能在发现损坏时自动删除玩家本地内容。**'
REPAIR_BUNDLE = '🔑 存档自检应允许玩家导出"**证据包**"，而不是只看校验和：'
'`save_id` · `platform_save_id` · `checksum` · `schema_version` · '
'`mod_state` · `cloud_state` · `created_at` · `modified_at` · '
'`previous_slot` · `corruption_risk`'
REPAIR_LOCAL = '🔑 坚持"**本地证据优先**"，🔴 **避免把敏感账号信息上传**'

# 🔑 C 物理外设
DEV_RULE = '🔑 **物理外设不是手柄枚举，而是身体动作的语义映射。**'
DEV_FOUR = ['**玩家意图**', '**动作语义**', '**设备能力**', '**输出反馈**']
DEV_MAME = '🔑 比"键码/轴号映射"更适合像素级记录：🔑 **开关只有 0/1**，'
'🔑 **绝对轴归一化到 -65,536 ~ 65,536（零点为中立位）**，'
'**相对轴表示上次更新后的位移**；🔑 **踏板 · 位移触发等单端轴只用零与负半区**，'
'负值对应**上 · 左 · 远离玩家 · 逆时针**'
DEV_SDL = '🔑 `SDL_GameControllerAddMapping` 用 `GUID,name,mapping` 字符串，'
'**允许按钮和轴互相映射**；Windows 的保留 GUID `xinput` 覆盖所有 XInput 设备'
DEV_ASYNC = '🔑 **振动请求在线程中排队处理** —— '
'🔴 **"发出振动"到"设备真正产生力"之间存在异步链**，'
'必须记录**调用 · 发送 · 完成回调 · 断开 · 取消 · 帧延迟**'
DEV_NO = '🔑 **"支持设备"必须记录不支持的异常，而非只写支持列表。**'
DEV_FIELDS = ['`device_class`', '`vendor_product`', '`firmware`',
              '`connection_bus`', '`input_domain`', '`output_domain`',
              '`calibration_domain`', '`axis_semantics`', '`button_aliases`',
              '`min_latency_ms`', '`max_latency_ms`', '`jitter_ms`',
              '`loss_rate`', '`reconnect_replay`',
              '`hot_unplug_recovery`', '`force_feedback_queue`']
DEV_REPLAY = '🔑 **禁止把设备原始值直接送入游戏玩法** —— '
'先注入录制的原始设备事件 → 映射为动作 → 最后执行反馈'
WHEEL_DETAIL = '🔑 **方向盘**：转向/油门/刹车/离合的输入类别 · 死区 · 颗粒度 · '
'**饱和区** · **自定中心** · 力反馈增益 · **恒定力 · 周期/正弦 · 阻尼 · 摩擦 · '
'惯性效果** · **扭矩曲线** · 表面反馈频率 · 换挡器/手刹/踏板顺序 · '
'🔑 **断电后是否残留扭矩** · **重新获取设备后的效果恢复**'
GUN_DETAIL = '🔑 **光枪**：CRT/液晶采样 · **刷新相位** · 边框与可见区 · '
'屏幕宽高比 · **多点校准** · 多枪区分 · **离屏装填** · 准星偏移 · '
'扳机键复用 · 抬起后是否仍输入 · 遮挡与反射'
GUN_MAME = '🔑 某版本把**离屏装填选项改为插件**，并使键盘 · 鼠标 · '
'轨迹球可绑定装填键 —— 🔑 **这证明"离屏开火＝装填"是应记录的语义，'
'而非硬件偶然**'
PAD_DETAIL = '🔑 **跳舞毯**：面板几何 · 箭头方向 · **相邻面板误触** · '
'同时按下窗口 · 抬起判定 · 缓冲窗口 · **连续踩踏顺序** · **鞋底磨损**'
OTHER_DETAIL = '🔑 吉他/乐器记**弦分离 · 按键 · 摇杆 · 敲击映射**；'
'街机摇杆记**八向/四向限制器 · 对角门 · 微动去抖 · 连打顺序**；'
'VR/体感记**追踪原点 · 房间规模 · 地面高度 · 控制器朝向 · 手指姿态 · 触觉**；'
'眼动/BCI 记**校准 · 采样 · 注视 · 眨眼 · 头部补偿 · 失败恢复**'

# 🔑 D 游玩环境
ENV_RULE = '🔑 **D 的核心不是市场平台，而是人体工学和注意力预算。**'
ENV_PLACES = ['客厅电视', '书房显示器', '床上掌机', '通勤手机', '网吧',
              '办公室', '直播台']
ENV_FIELDS = ['`viewing_distance_m`', '`screen_ppi`', '`screen_reflection`',
              '`ambient_lux`', '`ambient_noise_db`', '`output_device`',
              '`peak_volume_db`', '`posture`', '`single_hand`',
              '`attention_state`', '`interruption_risk`', '`privacy_risk`',
              '`thermal_throttling`', '`battery_percent`', '`network_class`',
              '`session_intent`']
WCAG_RULE = '🔑 **WCAG 2.2 可作为环境可访问性的最低外部基准** —— '
'🔴 **但不直接等于"电视 UI 规范"，只作"小字是否不可读"的可测量尺度**'
WCAG_ITEMS = [
    '**文字可放大到 200%** 而不丢失内容或功能',
    '**行高至少 1.5 倍字号** · 段后至少 2 倍 · 字距至少 0.12 倍 · 词距 0.16 倍',
    '**非文本界面组件和状态标识至少 3:1 对比**',
    '**指针目标增强级至少 44 × 44 CSS 像素**',
]
ENV_SPEC = '🔑 **"客厅优化"是具体数值，不是大字号开关** —— '
'要测玩家从 **1.5 / 2 / 3 米**观看时的**字高 · 图标尺寸 · HUD 密度 · '
'伤害数字 · 字幕 · 小地图 · 提示距离**；'
'🔑 测**低音量**下能否听见**对话 · 方向线索 · 交互提示 · 敌人预警**'
ENV_MOBILE = '🔑 手机/掌机补测：**单手可触及区 · 横竖屏 · 通知打断 · '
'自动锁屏 · 省电模式 · 热降频 · 电池 · 戴手套/手指遮挡 · 手持抖动**'
ENV_LIVE = '🔑 直播环境补测：**OBS 热键冲突 · 摄像头占用 · 键鼠隐私 · '
'双声道泄露 · 观众延迟 · Alt-Tab 恢复 · 窗口捕获黑屏 · 麦克风回声**'
ENV_PRESET = '🔑 **环境预设 ≠ 一套 UI 参数** —— '
'电视 · 桌面 · 掌机 · 手机 · 直播**各是一组独立组合**'
ENV_UNKNOWN = '🔑 若原版没有针对某环境的可见调整，'
'应显式标 **`unknown_environment_adaptation`**，🔴 **不要默认现代桌面**'

# E 元进度
LEGACY_FOUR = [
    ('`intra_game_meta`', '同游戏多个周目/模式'),
    ('`intra_ip_meta`', '同 IP/世界观的多个作品'),
    ('`publisher_account_meta`', '发行商账号'),
    ('`platform_account_meta`', 'Steam / Xbox / PSN / Switch 等'),
    ('`cross_title_token`', '跨游戏权利 / 解锁 / 外观'),
]
LEGACY_FIELDS = ['`source_title_version_region`', '`platform_authority`',
                 '`migration_trigger`', '`payload_schema`',
                 '`conflict_policy`', '`revocation`', '`display_only`',
                 '`audit_trail`']
LEGACY_KIND = '🔑 `legacy_payload` 记 `kind`（cosmetic / narrative / mechanical / '
'right / marker）· `direction`（单向/双向）· `trigger` · `first_version` · '
'`last_version` · `region_compatible` · `platform_compatible` · '
'**`fallback_when_absent`**'
LEGACY_NO = '🔴 **禁止把"自动创建账号""自动合并"写成无感优化** —— '
'这会改变玩家对**所有权和遗产**的感知'
LEGACY_LINK = '🔑 `account_link_flow` 要记：**玩家可选跳过 · 已有账号提示 · '
'首次携带资产提示 · 冲突账户提示 · 取消后果 · 失败回滚 · 重复链接 · 地区差异**'

# F 玩家作品
WORK_RULE = '🔑 **玩家作品是记忆的外部化，照片模式不是"可移除的截图键"。**'
WORK_TYPES = ['截图', '录像', '剪辑', '照片模式作品', 'Mod', '谱面',
              '存档挑战', 'Fan art', '音乐改编', 'Cosplay', '同人小说', '梗图']
WORK_FIELDS = ['`artifact_id`', '`type`', '`author_handle`', '`created_at`',
               '`source_game_version_region`', '`source_slot/save_hash`',
               '`parent_artifact_ids`', '`derived_artifact_ids`',
               '`toolchain`', '**`camera_pose/settings`**', '`render_flags`',
               '`capture_format/codec/bitrate`', '`shared_platform`',
               '`visibility`']
WORK_SHOT = '🔑 **截图**：快捷键 · 捕获来源 · HUD 开关 · 宽高比 · 格式 · '
'命名 · 保存路径 · **覆盖已有文件** · 跨进程弹窗 · 音效 · 相册排序'
WORK_VIDEO = '🔑 **录像/剪辑**：帧内/帧后捕获 · 编码 · 帧率 · 码率 · HDR · '
'音频混音 · 时长上限 · **循环缓冲** · 暂停时行为 · 后台录制 · 结束确认 · '
'元数据 · 分享目标'
WORK_PHOTO = '🔑 **照片模式**：自由相机 · 碰撞 · 过场暂停 · 人物隐藏 · '
'表情 · 景深 · 滤镜 · **时间冻结** · **敌人逻辑冻结** · HUD · 水印 · '
'**退出后是否恢复世界**'
WORK_MOD = '🔑 **Mod**：加载顺序 · 哈希 · 依赖 · 配置 · 热重载 · '
'**崩溃隔离** · 签名/作者 · 更新 · 禁用 · 卸载残留'
WORK_CLEAN = '🔑 **不得将"完全无 Mod"视为唯一干净状态** —— '
'若原版生态依赖 Mod 修复/扩展，重制应至少保留**可审计的兼容层**'

# G 通关后
ENDING_RULE = '🔑 **通关后的世界是叙事状态机，不是主菜单的一个开关。**'
ENDING_FIELDS = ['`post_credits_save_state`', '`postgame_exploration`',
                 '`final_decision_reversibility`', '`return_to_pre_ending`',
                 '**`ng_plus_exists_in_original`**', '`carry_payload`',
                 '`title_screen_delta`', '`main_menu_delta`',
                 '`ending_record_ui`', '`repeated_ending_policy`',
                 '`final_save_degradation`']
ENDING_NO = '🔑 原版若**通关即结束 · 自动覆盖 · 删除临时状态 · 回到标题画面**，'
'🔴 **复制版不应擅自加入 NG+**；'
'原版若有明确自由探索 · 通关后服装/音乐/标题变化，也必须保留'
ENDING_TWO = '🔑 **"回到结局前"要区分玩家撤销与世界回滚**：'
'玩家层面是存档槽 · 检查点 · 手动备份；'
'世界层面是**剧情状态 · NPC · 世界变化 · 多周目是否重新生成**'
ENDING_UI = '🔑 **通关后的 UI 变化往往比结局动画更被玩家记住** —— '
'标题画面背景 · 标题文本 · 菜单项增删 · 角色位置 · 天气 · 音乐 · '
'读取槽位标签 · 难度解锁 · 统计汇总 · 结局画廊 · 制作人名单是否可回看 · '
'**是否显示"已完成 N 次"** · 是否自动回到标题'
ENDING_TEST = '🔑 测试矩阵：正常通关 · 失败通关 · 部分结局 · 跳过演出 · '
'**断电** · 上传云失败 · 切换账号 · 离线 · 更新后回到旧存档。'
'🔑 **未观察到 ≠ 不存在，应标 `not_observed`**'

H_15 = [
    ('**1 进程外焦点**', '覆盖层 · 输入法 · Alt-Tab · 全屏独占 · HDR 切换 · '
     '多显示器主屏变化 · 手柄断开再连。🔑 记录**焦点顺序与输入捕获/释放**，'
     '而非只写"支持手柄"'),
    ('**2 平台面板时序**', '启动器 → EULA → 补丁 → DRM → 登录 → 云同步 → 标题。'
     '记每步**最短/最长等待 · 并行/串行 · 可跳过 · 失败回退**'),
    ('**3 云存档冲突的具体动作**', '🔑 显示"本地优先/远程优先/两份都留"'
     '还是只给一个确定键？**冲突后原文件是否改名 · 是否上传 · 是否永久覆盖**'),
    ('**4 离线与恢复**', '断网发生在**启动 · 登录 · 上传 · 下载 · 联机中途**'
     '分别怎样；恢复后是**静默 · 重试 · 还是强制回标题**；'
     '🔑 **失败原因文案是否暴露网络/账号/服务器**'),
    ('**5 通知与打断**', '成就 · 好友上线 · 商店更新 · 维护 · 封禁/申诉'
     '**如何排序**；🔑 **是否打断演出 · 能否关闭 · 是否暴露隐私**'),
    ('**6 商店/社区/工坊权利**', '所有权 · 地区 · 年龄 · 退款 · DLC · '
     '订阅依赖 · 版本兼容 · 举报审核 · **作者弃坑**。'
     '🔴 **权限不足与"内容不存在"不能只显示同一错误码**'),
    ('**7 设备冲突与残留**', '反作弊 · 覆盖层 · 录屏 · RGB · 宏软件 · '
     '虚拟声卡**同时加载**；🔑 **驱动升级后旧存档 · 旧配置 · 旧硬件映射失效**'),
    ('**8 异常输入重放**', '🔑 **手柄没电 · 键盘连发 · 跳舞毯同时踩 · '
     '方向盘拔线 · 光枪离屏 · 触摸屏误触 · 鼠标与手柄混用**。'
     '记**是否暂停 · 是否保存 · 是否提示**'),
    ('**9 环境感官适配**', '远距离小字 · 低音量低频 · 反光 · 噪声 · '
     '震动手套/坐垫 · 戴耳机/外放 · 听力障碍替代提示'),
    ('**10 元进度的视觉身份**', '🔑 初代携带 · 平台联动 · 跨周目外观 · 称号 · '
     '老玩家标识**必须在菜单和过场中原样呈现**，'
     '🔴 **不能只写数据库迁移成功**'),
    ('**11 创作管线元数据**', '照片模式相机位姿 · 滤镜 · 暂停逻辑；'
     '录像编码与音频；Mod 清单/配置/依赖；**截图命名与相册**'),
    ('**12 通关后的时间性**', '能否继续 · 是否覆盖 · 能否回结局前 · '
     '结局是否重复 · **标题画面/音乐/UI 变化**'),
    ('**13 安装器的失败经济**', '🔑 空间不足 · 下载限速 · 断点续传 · '
     '补丁冲突 · 校验失败 · 回滚版本 · 杀软拦截。'
     '🔑 **原版是否要求玩家手动处理，决定这是工作流还是缺陷**'),
    ('**14 账号与恢复**', '忘记密码 · 设备丢失 · 自动登录 · 会话过期 · '
     '跨设备 · 平台合并 · 申诉。🔴 **只录功能不录文案/等待/失败，'
     '会造成重制"能跑但不可信"**'),
    ('**15 遥测与隐私面板**', '遥测开关 · 崩溃上传 · 硬件指纹 · '
     '广告/追踪同意 · 家长控制 · 聊天过滤 · 屏幕时间 · 儿童账号'),
]

CONFLICTS = [
    '❌ **云存档自动合并/覆盖**（改变玩家确认权与冲突语义）',
    '❌ **无感后台更新 · 强制重启**（改变补丁等待与回滚预期）',
    '❌ **一键修复 · 自动清缓存**（🔴 掩盖玩家自救工作流及风险）',
    '❌ **统一"通用手柄"映射**（抹平方向盘 · 光枪 · 跳舞毯语义）',
    '❌ **把云游戏/串流视为等价平台**（忽略端到端延迟与退出恢复）',
    '❌ **跨平台账号自动合并**（改变权利 · 遗产 · 身份关系）',
    '❌ 把内置截图/录像/照片模式当"可有可无"',
    '❌ **自动加入 NG+ / 跳转结局**（改变通关后状态机与第一次不可再生）',
    '❌ **自适应 UI / 自动缩放**（掩盖原版在具体环境的可读性问题）',
    '❌ **反作弊"宁可误杀"**（把安全策略伪装成游戏表现）',
    '❌ **用"现代无障碍"默认替换原版**（可能改变提示通道 · 节奏 · 难度语义）',
    '❌ 以"现代系统"为由**拒录**兼容模式/回滚驱动等环境怪癖',
    '❌ **未经隔离直接吸收社区修复工具**',
    '❌ 把**重装当成正常路径**（不记不可逆代价）',
]

FIELDS = [
    ('item_id', '项编号'),
    ('domain', '域（meta / gog / eos / save / repair / device / wheel / '
               'env / wcag / legacy / work / ending / h）'),
    ('legacy_value', '**原版值**'),
    ('new_value', '新引擎值'),
    ('match', '**是否一致**'),
    ('peripheral_evidence', '**外围/环境/身体接口证据**'),
    ('evidence', '证据等级 1-8'),
]


def _hdr(t, w=80):
    print('=' * w)
    print(t)
    print('=' * w)


def cmd_meta(a):
    _hdr('🔑 元游戏外围层（**不是皮肤，是有状态服务**）')
    print(f'   {META_RULE}')
    print(f'\n   {META_EG}')
    print(f'\n   {META_WARN}')
    print('\n十三类: ' + ' · '.join(META_13))
    print('\n字段: ' + ' · '.join(META_FIELDS))
    print(f'\n   {META_ORDER}')
    return 0


def cmd_gog(a):
    _hdr('🔑 GOG 规范（**客户端可缺是硬要求**）')
    print(f'   {GOG_RULE}')
    for f in GOG_FACTS:
        print(f'   · {f}')
    print(f'\n   {GOG_ASK}')
    return 0


def cmd_eos(a):
    _hdr('🔑 EOS（**身份与数据是两条链**）')
    print(f'   {EOS_RULE}')
    print(f'\n   {EOS_TWO}')
    print('\n五类账号标识:')
    for i in EOS_IDS:
        print(f'   · {i}')
    print(f'\n   {EOS_CROSS}')
    print(f'\n   {EOS_GOG}')
    return 0


def cmd_save(a):
    _hdr('🔑 玩家自救（**第二控制流**）')
    print(f'   {SAVE_RULE}')
    print(f'\n   {SAVE_KEY}')
    print('\n常见顺序: ' + ' · '.join(SAVE_SEQ))
    print('\n字段: ' + ' · '.join(SAVE_FIELDS))
    print(f'\n   {SAVE_KEEP}')
    print(f'\n   {SAVE_MODE}')
    print(f'\n   {SAVE_WARN}')
    return 0


def cmd_repair(a):
    _hdr('🔑 验证与修复（**先快照 → 后报告 → 再确认**）')
    print(f'   {REPAIR_RULE}')
    print('\n三份产物:')
    for k, v in REPAIR_3:
        print(f'   {k:<22} {v}')
    print(f'\n   {REPAIR_NO}')
    print(f'\n   {REPAIR_BUNDLE}')
    print(f'\n   {REPAIR_LOCAL}')
    return 0


def cmd_device(a):
    _hdr('🔑 物理外设（**四层抽象**）')
    print(f'   {DEV_RULE}')
    print('\n四层: ' + ' → '.join(DEV_FOUR))
    print(f'\n   {DEV_MAME}')
    print(f'\n   {DEV_SDL}')
    print(f'\n   {DEV_ASYNC}')
    print(f'\n   {DEV_NO}')
    print('\n字段: ' + ' · '.join(DEV_FIELDS))
    print(f'\n   {DEV_REPLAY}')
    return 0


def cmd_wheel(a):
    _hdr('🔑 逐设备建档')
    print(f'\n   {WHEEL_DETAIL}')
    print(f'\n   {GUN_DETAIL}')
    print(f'\n   {GUN_MAME}')
    print(f'\n   {PAD_DETAIL}')
    print(f'\n   {OTHER_DETAIL}')
    return 0


def cmd_env(a):
    _hdr('🔑 游玩环境考古（**客厅 ≠ 书房**）')
    print(f'   {ENV_RULE}')
    print('\n场景: ' + ' · '.join(ENV_PLACES))
    print('\n字段: ' + ' · '.join(ENV_FIELDS))
    print(f'\n   {ENV_SPEC}')
    print(f'\n   {ENV_MOBILE}')
    print(f'\n   {ENV_LIVE}')
    print(f'\n   {ENV_PRESET}')
    print(f'\n   {ENV_UNKNOWN}')
    return 0


def cmd_wcag(a):
    _hdr('WCAG 2.2（**只作可测量尺度**）')
    print(f'   {WCAG_RULE}')
    for i in WCAG_ITEMS:
        print(f'   · {i}')
    return 0


def cmd_legacy(a):
    _hdr('元进度（**五层**）')
    for k, v in LEGACY_FOUR:
        print(f'   {k:<26} {v}')
    print('\n字段: ' + ' · '.join(LEGACY_FIELDS))
    print(f'\n   {LEGACY_KIND}')
    print(f'\n   {LEGACY_NO}')
    print(f'\n   {LEGACY_LINK}')
    return 0


def cmd_work(a):
    _hdr('🔑 玩家作品（**照片模式不是截图键**）')
    print(f'   {WORK_RULE}')
    print('\n类型: ' + ' · '.join(WORK_TYPES))
    print('\n字段: ' + ' · '.join(WORK_FIELDS))
    print(f'\n   {WORK_SHOT}')
    print(f'\n   {WORK_VIDEO}')
    print(f'\n   {WORK_PHOTO}')
    print(f'\n   {WORK_MOD}')
    print(f'\n   {WORK_CLEAN}')
    return 0


def cmd_ending(a):
    _hdr('🔑 通关后的世界（**叙事状态机**）')
    print(f'   {ENDING_RULE}')
    print('\n字段: ' + ' · '.join(ENDING_FIELDS))
    print(f'\n   {ENDING_NO}')
    print(f'\n   {ENDING_TWO}')
    print(f'\n   {ENDING_UI}')
    print(f'\n   {ENDING_TEST}')
    return 0


def cmd_h(a):
    _hdr('H 类（**十五条可执行取证清单**）')
    for k, why in H_15:
        print(f'\n   【{k}】\n      {why}')
    return 0


def cmd_init(a):
    os.makedirs(os.path.dirname(a.init) or '.', exist_ok=True)
    with open(a.init, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow([k for k, _ in FIELDS])
        w.writerow(['TODO'] * len(FIELDS))
    print(f'已生成外围层表: {a.init}')
    print('\n⚠️ 十三域：meta / gog / eos / save / repair / device / wheel / '
          'env / wcag / legacy / work / ending / h')
    print('\n⚠️ `peripheral_evidence` 列＝**外围/环境/身体接口证据**')
    print('\n🔑 新模板：metagame_surface · peripheral_state_matrix · '
          'launcher_session · player_workaround_playbook · repair_manifest · '
          'environment_quirk · save_evidence_schema · body_interface · '
          'play_environment · session_context · legacy_payload · '
          'account_link_flow · player_artifact · ending_state_machine')
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

    mismatch, no_legacy, no_peri, no_grade = [], [], [], []
    for i, r in enumerate(rows, 1):
        m = g(r, 'match').lower()
        if m not in ('yes', 'y', 'true', '是', '一致'):
            mismatch.append(i)
        if not g(r, 'legacy_value') or g(r, 'legacy_value') == 'TODO':
            no_legacy.append(i)
        p = g(r, 'peripheral_evidence')
        if not p or p == 'TODO':
            no_peri.append(i)
        ev = g(r, 'evidence')
        if not ev or ev == 'TODO':
            no_grade.append(i)
        else:
            d = ev.split('.')[0].strip()
            if d.isdigit() and int(d) >= 7:
                no_grade.append(i)

    print('=' * 76)
    print(f'外围层与身体接口 · {len(rows)} 条')
    print('=' * 76)
    if mismatch:
        print(f'\n🚫 **不一致** {len(mismatch)} 条（行 {mismatch[:15]}）')
    if no_legacy:
        print(f'\n❌ {len(no_legacy)} 条缺**原版值**（行 {no_legacy[:15]}）')
    if no_peri:
        print(f'\n🚫 {len(no_peri)} 条缺**外围/环境/身体接口证据**'
              f'（行 {no_peri[:15]}）')
    if no_grade:
        print(f'\n🚫 {len(no_grade)} 条**证据等级缺失或 ≥7 级**'
              f'（行 {no_grade[:15]}）')

    if not (mismatch or no_legacy or no_peri or no_grade):
        print('\n✅ 外围层：一致、原版值完整、外围证据已验证、证据达标')

    print('\n🔑 **原版「游戏」并不止于进程内画面。**')
    print('   🔑 **客户端可缺是硬要求；跨平台是身份与数据两条链。**')
    print('   🔑 **玩家自救是第二控制流；物理外设是身体动作的语义映射。**')
    print('   🔴 **不能从 UI 截图倒推内部契约。**')
    return 1 if (a.gate_check and
                 (mismatch or no_legacy or no_peri or no_grade)) else 0


def main():
    ap = argparse.ArgumentParser(description='外围层：元游戏/自救/外设/环境')
    ap.add_argument('--meta', action='store_true')
    ap.add_argument('--gog', action='store_true')
    ap.add_argument('--eos', action='store_true')
    ap.add_argument('--save', action='store_true')
    ap.add_argument('--repair', action='store_true')
    ap.add_argument('--device', action='store_true')
    ap.add_argument('--wheel', action='store_true')
    ap.add_argument('--env', action='store_true')
    ap.add_argument('--wcag', action='store_true')
    ap.add_argument('--legacy', action='store_true')
    ap.add_argument('--work', action='store_true')
    ap.add_argument('--ending', action='store_true')
    ap.add_argument('--h', action='store_true')
    ap.add_argument('--init')
    ap.add_argument('--check')
    ap.add_argument('--gate-check', action='store_true')
    a = ap.parse_args()
    fns = {'meta': cmd_meta, 'gog': cmd_gog, 'eos': cmd_eos, 'save': cmd_save,
           'repair': cmd_repair, 'device': cmd_device, 'wheel': cmd_wheel,
           'env': cmd_env, 'wcag': cmd_wcag, 'legacy': cmd_legacy,
           'work': cmd_work, 'ending': cmd_ending, 'h': cmd_h}
    for k, fn in fns.items():
        if getattr(a, k):
            return fn(a)
    if a.init:
        return cmd_init(a)
    if a.check:
        return cmd_check(a)
    print('❌ 需要 --meta / --gog / --eos / --save / --repair / --device / '
          '--wheel / --env / --wcag / --legacy / --work / --ending / --h / '
          '--init / --check 之一')
    return 2


if __name__ == '__main__':
    sys.exit(main())
