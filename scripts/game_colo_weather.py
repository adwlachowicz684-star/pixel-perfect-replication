#!/usr/bin/env python3
"""分屏共置 / 多档案隔离 / 天气季节 / 小地图空间语义
（第三十一轮 A / B / C / D 类，含 E/F/G 补充）。

**🔑 本轮核心视角**：
> 前三十轮已经把"**大系统**"覆盖完，本轮真正缺的是
> **共置 · 归属 · 空间语义** —— 同一模块在**多个主体共置**、
> **多个身份共设备**、**环境状态同时参与玩法**时，
> 究竟**按谁的坐标 · 谁的预算 · 谁的权限 · 谁的世界状态**运行。

**🔑 本轮最重要的发现（先说结论）**：
> **A—D 四个高优先级盲区几乎都没有可直接整体吸收的一站式成熟开源项目。**
> GitHub 上的分屏样本多是小游戏或插件，天气结果主要是 FiveM 模组。
> 🔑 因此正确做法是**吸收可复现的底层算法与取证字段**，
> 🔴 **而不是搬运第三方代码**。

**🔑 "同一帧"在本地多人下会裂成六层**：
> 共享模拟 tick · 每个玩家输入采样时刻 · 每个视口相机求值时刻 ·
> 每个视口 GPU 提交 · 音频监听/混音位置 · HUD 读世界状态的时刻。
> 🔴 仅要求"同一帧"**无法判断两名玩家看到的敌人位置是否来自同一模拟版本**。

用法:
  game_colo_weather.py --view     # 🔴 视口**拓扑状态机**
  game_colo_weather.py --fov      # 🔑 **垂直分屏改变水平 FOV**
  game_colo_weather.py --budget   # 每视口**独立预算**
  game_colo_weather.py --render   # 分屏**渲染顺序**
  game_colo_weather.py --audio    # 音频**监听拓扑**
  game_colo_weather.py --input    # 🔑 输入与 HUD **持久绑定**
  game_colo_weather.py --topo     # 死亡/掉线**拓扑重排事务**
  game_colo_weather.py --profile  # 🔴 **七类隔离域**
  game_colo_weather.py --switch   # 切换**六状态事务**
  game_colo_weather.py --delprof  # 删除**六个问题**
  game_colo_weather.py --weather  # 🔑 天气**两层状态机**
  game_colo_weather.py --wgame    # 🔴 天气**玩法耦合事件契约**
  game_colo_weather.py --indoor   # 室内外**局部状态机**
  game_colo_weather.py --season   # 季节**不变量与跨周目**
  game_colo_weather.py --map      # 🔑 小地图**两套稳定坐标**
  game_colo_weather.py --mapup    # 🔴 更新**相位**与图标稳定排序
  game_colo_weather.py --efg      # E/F/G 补充
  game_colo_weather.py --init ledger/colo_weather.csv
  game_colo_weather.py --check ledger/colo_weather.csv --gate

退出码: 0 通过 / 1 缺项 / 2 用法错误
"""
import argparse
import csv
import os
import sys

# 🔑 六层"同一帧"
SIX_TICK = [
    ('**world_tick**', '共享模拟 tick'),
    ('**sample_index**', '每个玩家输入采样时刻'),
    ('**view_tick**', '每个视口相机求值时刻'),
    ('**frame_index**', '每次渲染'),
    ('**audio_listen_clock**', '音频监听/混音位置'),
    ('**read_tick**', 'HUD 读世界状态的时刻'),
]

SIX_RULE = [
    '🔑 应给每帧一个 `world_tick`、每个玩家意图一个 `sample_index`、'
    '每个视口一个 `view_tick`、每次渲染一个 `frame_index` 和每个 HUD 一个 '
    '`read_tick`',
    '🔴 **禁止跨层混用**',
    '🔴 若原版**先串行更新玩家 0 再更新玩家 1**，复刻版**不得为了线程平衡'
    '改成交错或并行更新**',
]

# 🔴 视口拓扑
VIEW_TOPO = [
    '单人满屏', '水平二分', '垂直二分', '四等分', '对角三分', '主从跟随',
    '**一人死亡后的收缩黑边**', '**一人掉线后的保留/回收**', '加入退出过渡',
]

VIEW_FIELDS = [
    'top', 'left', 'width', 'height', '长宽比', '像素目标', '**FOV 计算模式**',
    '是否共享裁剪空间', '合并动画时长', '边界样式',
]

VIEW_RULE = '🔑 **视口拓扑必须作为状态机，而不是一次性布局**；'
'🔴 **绝不能只记录"2 玩家分屏"**'

# 🔑 FOV
FOV_KINDS = ['horizontal', 'vertical', 'diagonal']
FOV_FORMULA = 'vFov = 2*atan(tan(hFov/2) / r)'
FOV_RULE = [
    '🔑 **垂直分屏改变水平 FOV**，除非原版明确使用水平 FOV 并重新计算垂直 FOV',
    '🔑 公式：' + FOV_FORMULA,
    '🔑 若改为左右两等分，每半屏宽高比约为原值一半 —— '
    '**使用同一 hFov 会使每名玩家水平视野减半**；'
    '**使用同一 vFov 则水平 FOV 会扩大**',
    '🔑 原版应记为 `fov_kind ∈ {horizontal, vertical, diagonal}` · '
    '`locked_axis` · 分屏变化曲线',
    '🔴 **没有录像或调试截图证明时，只能写"来源不确定"，'
    '不能据现代引擎默认猜测**',
]

# 每视口预算
BUDGET_PER_VIEW = [
    '裁剪', '近平面', '远平面', 'LOD bias', '阴影距离', '粒子剔除距离',
    '**流式请求**',
]

BUDGET_RULE = [
    '🔑 **每个视口都要有自己的**裁剪 · 近平面 · 远平面 · LOD bias · '
    '阴影距离 · 粒子剔除距离 · 流式请求',
    '🔑 单视口调优得到的"**远处阴影 40 米**"**不是双玩家预算** —— '
    '**两名玩家朝相反方向时，可见世界与流式区域几乎翻倍**',
    '🔑 应把原版按 **1/2/3/4 名玩家**分别抓帧：世界位置 · 像素面积 · '
    '绘制调用 · 阴影 Pass · 后处理 · 贴图流送 · 稳定帧时长',
    '🔑 动态分辨率必须注明作用于**整屏 · 每个视口 · 还是每个 Pass**',
    '🔴 **"动态分辨率自动解决性能"是常见但危险的偏离**',
]

# 渲染顺序
RENDER_ITEMS = [
    '天空盒是否共用一次', '**阴影是否每视口重绘**', '预渲染深度是否共享',
    '**SSAO/SSR/DOF/模糊是全屏一次还是每视口独立**',
    '**UI 是否在各自视口内渲染**',
]

RENDER_RULE = '🔑 **分屏不等于把主相机复制两遍**；'
'🔴 若原版先渲染视口 A 再渲染 B，而新引擎把两视口放进同一 render graph，'
'**可能改变 HDR 输入 · 半分辨率 Pass · alpha 混合顺序**'

# 音频
AUDIO_TOPO = [
    '一个扬声器混所有？', '**按视口做声像？**', '语音聊天归属？',
    '**监听位置是各玩家角色还是共享点？**',
    '**两个玩家相距很远时的混音策略**',
    '环境音是播一遍还是两遍？',
]

AUDIO_RULE = '🔑 **音频归属必须记录为监听拓扑**，'
'🔴 **而不是"立体声"或"环绕声"**'

# 🔑 输入与 HUD 绑定
INPUT_ITEMS = [
    '哪个手柄归哪个视口', '**手柄拔出/重连后归属是否保留**',
    '加入/退出的设备绑定顺序', '**HUD 是每份还是共享**',
    '菜单谁控制', '暂停归谁', '**输入设备与玩家身份的持久绑定**',
]

INPUT_RULE = '🔑 **输入与 HUD 不是设备到玩家的一一映射**'

# 拓扑重排
TOPO_EVENTS = [
    '一名玩家死亡', '一名玩家掉线', '新玩家加入', '玩家主动退出',
    '设备断开', '暂停归属争议',
]

TOPO_RULE = '🔑 **死亡、掉线和加入退出是拓扑重排事务**，'
'要定视口是**合并 · 保留黑屏 · 还是回收**，且**过渡动画时长与边界样式**要记'

# 🔴 七类隔离域
PROFILE_SCOPES = [
    ('**身份与认证**', '平台用户 ID · 设备用户 ID · 游戏档案 ID'),
    ('**设备偏好**', '画质 · 分辨率 · 语言候选 · 输入设备名'),
    ('**账号/档案元数据**', '角色 · 进度 · 统计 · 解锁'),
    ('**角色存档**', '周目 · 槽位 · 世界状态'),
    ('**统计与成就**', '按账号还是按档案'),
    ('**解锁和跨周目契约**', 'NG+ 契约归谁'),
    ('**模组与自定义内容**', '是否跨档案共享'),
    ('**云同步状态**', '上传时间 · 哈希 · 设备 ID · 冲突版本'),
    ('**临时会话数据**', '当前关卡 · 待撤销事务 · 比赛时钟'),
]

PROFILE_LEVELS = [
    ('**机器级**', '画质 · 已安装 DLC · 语言候选 · 输入设备名', '是否保留'),
    ('**账号/档案级**', '角色 · 进度 · 统计 · 解锁', '完全隔离'),
    ('**会话级**', '当前关卡 · 待撤销事务 · 比赛时钟', '冻结或终止'),
    ('**临时级**', '截图草稿 · 缓存 · 临时输入映射', '丢弃或迁移'),
    ('**共享级**', '已购内容授权 · 全局教程', '**按授权而非按档案复制**'),
    ('**云审计级**', '上传时间 · 哈希 · 设备 ID · 冲突版本', '只追加或显式合并'),
    ('**访客级**', '试玩进度 · 儿童限制 · 数据保留期限', '能否转正式 · 到期删除'),
]

PROFILE_RULE = [
    '🔑 **同一个平台账号 · 同一设备用户 · 同一游戏档案 · 同一周目存档 · '
    '同一局内角色不是一回事**',
    '🔴 常见反例：把**分辨率 · 震动 · 字幕语言放进角色存档** → '
    '换档案后必须反复设置',
    '🔴 或把**皮肤解锁只按设备存储** → 原版另一档案没有',
    '🔑 **默认档案 · 访客档案 · 儿童档案不是三个普通昵称** —— '
    '访客可能禁止云同步 · 禁止上传统计 · 退出后删除',
    '🔑 **儿童档案的限制如果只在前端隐藏按钮，就仍可能通过快捷操作或'
    '调试菜单绕过** —— 要记受限操作白名单 · 解锁条件 · 到期时间 · 删除去向',
]

# 切换六状态
SWITCH_SIX = [
    'editing_pending', 'transaction_open', 'snapshot_written',
    'session_detached', 'transaction_committed', 'failed_rollback',
]

SWITCH_MEASURE = [
    '是否中断当前战斗', '是否保留暂停菜单', '是否保存临时标记',
    '**切换耗时多少**', '是否有强制保存提示',
]

SWITCH_RULE = '🔑 **档案切换是显式加载事务，不能静默重启**；'
'🔴 **把切换做成自动无提示重启会丢掉持续过程** —— '
'违反"持续过程要么冻结要么显式终止"'

# 删除六问
DEL_SIX = [
    '本地角色是否删', '云端是否删', '统计是否归零', '**成就是否撤回**',
    '共享解锁是否失效', '访客缓存是否清',
]

DEL_RULE = [
    '🔑 **成就通常按账号授予而不应随单角色删除**，'
    '但**统计可能按档案保留** —— 🔴 **二者不能混为"全部清除"**',
    '🔴 云冲突**不能只保留最新修改时间** —— '
    '本地未上传的**死亡 · 回滚 · 失败提交**可能反而更权威',
]

# 🔑 天气两层状态机
WEATHER_MACRO = ['晴', '阴', '雨', '雪', '雾', '雷暴', '沙暴']

WEATHER_PHASE = ['forming', 'active', 'weakening', 'transition']

WEATHER_FIELDS = [
    'weather_kind', '**phase**', '开始/结束时间', '过渡曲线', '**种子来源**',
    '主风场 ID', '**局部遮蔽 ID**', '可见粒子版本', '可听音景版本',
    '**玩法事件版本**', '观察者版本',
]

WEATHER_RULE = [
    '🔑 **天气要有两层状态机，不能只写一个当前枚举**',
    '🔑 宏观层负责转换概率 · 持续时间 · 季节门；'
    '局部层负责**是否在室内 · 是否在浅水 · 是否暴露在开阔地 · '
    '是否受屋顶遮蔽 · 过渡迟滞**',
    '🔴 **只看 `current_weather` 会丢掉"雨正在进入但角色尚在室内"'
    '这一中间态**',
    '🔑 多人同步时还要区分**权威世界天气**与**每个客户端的本地遮蔽结果** —— '
    '🔴 **玩家自己进入室内不应改变其他玩家的天气**',
]

# 🔴 天气玩法耦合
WEATHER_GAMEPLAY = [
    'AI 视距', '感知衰减', '听觉传播', '狙击镜反光', '角色摩擦',
    '操控响应', '跳跃/着陆', '**火焰点燃与持续时间**', '**电击/导体伤害**',
    '**弹道风偏**', '弓箭/抛射物阻力', '能见度', '**足迹保留**',
    '潜行痕迹', '水面涟漪', '**结冰**', '可破坏地形', '声景', '混响区',
]

WEATHER_COMBO = [
    '**雨熄灭火焰**', '**潮湿导电**', '**雷电偏向高处/导体**',
]

WEATHER_GP_RULE = [
    '🔑 **天气不是视觉触发装饰，而是多个系统共同订阅的事实源**',
    '🔑 组合伤害（如雨熄火、潮湿导电、雷电偏导体）必须记'
    '**判定盒 · 持续时间 · 失败条件 · 伤害来源**',
    '🔴 **不能只复刻特效**',
]

# 室内外
INDOOR_ITEMS = [
    '进门瞬间**声音与粒子如何切断**', '**是否有迟滞**',
    '半身跨门时的归属', '屋顶遮蔽的判定方式',
    '浅水/屋檐/洞穴是否算室内', '**雷声在室内的衰减版本**',
]

INDOOR_RULE = '🔑 **室内外过渡是局部状态机，不是简单音量开关**'

# 季节
SEASON_ITEMS = [
    '对植被的影响', '对 NPC 日程的影响',
    '**对可通行性的影响（结冰湖面）**', '不变量', '数据版本',
    '**跨周目语义**',
]

# 🔑 小地图两套坐标
MAP_TWO_COORDS = [
    ('**世界坐标**', '实体在世界的真实位置'),
    ('**地图坐标**', '实体在小地图上的投影位置（含缩放 · 旋转 · 锚定）'),
]

MAP_FIELDS = [
    '缩放级别', '**旋转方式**', '**中心锚点**', '**更新频率**',
    '**更新相位**', '图标密度', '**重叠规则**', '稳定排序键',
]

MAP_RULE = [
    '🔑 **小地图必须建立两套稳定坐标**',
    '🔑 要记**更新频率**（每帧还是每 N 帧）与'
    '**实体移动是插值还是跳变**',
    '🔴 **更新相位错了会导致位置跳变**，玩家会以为实体在瞬移',
]

MAP_MORE = [
    '多个敌人重叠时显示几个（**稳定排序**）',
    '**迷雾与已探索的粒度**（格子/房间/区域，是否随周目重建）',
    '**"下一目标"指引的语义**（箭头？路径线？距离数字？'
    '**是否会穿过未探索区域**？）',
    '**目标标记与玩家标记**（自定义标记是否持久化？）',
    '**小地图与全地图的一致性**（同一实体在两处位置是否一致？'
    '旋转是否一致？）',
    '**高低差的表达**（楼层怎么显示？地下？）',
]

MAP_FAIL = '🔑 **小地图失败通常来自采样 · 排序 · 跨层一致性**，'
'🔴 **而不是图标资源不足**'

# E/F/G
EFG = [
    ('**E 长文本阅读**', '分页 vs 滚动 · 字号 · 行长 · 是否可缩放 · '
     '**阅读时世界是否暂停（敌人是否继续）** · 是否可随时关闭 · '
     '是否可重读 · **是否记已读** · 朗读/字幕/语音是否同步 · '
     '**富内容（插图 · 地图 · 可交互链接）**'),
    ('**F 载具/坐骑**', '**上下车动画与碰撞切换（过程中是否无敌 · '
     '能否被打断）** · 悬挂 · 重心 · **翻车恢复** · "卡住"判定 · '
     '损坏与维修 · **乘客与驾驶者的视角差异** · '
     '**停在哪里 · 读档后在哪**'),
    ('**G 物品栏空间布局**', '**网格背包 · 体积 · 重量 · 形状**（占几格？'
     '能否旋转？） · **自动整理的规则与稳定排序** · 溢出与堆叠规则 · '
     '**容器嵌套（箱内箱）**'),
]

CONFLICTS = [
    '❌ 只记录"2 玩家分屏"',
    '❌ **据现代引擎默认猜测 FOV**（应写来源不确定）',
    '❌ 用单视口预算套双视口',
    '❌ **"动态分辨率自动解决性能"**',
    '❌ 把分屏当成"把主相机复制两遍"',
    '❌ 音频只写"立体声/环绕声"',
    '❌ **为了线程平衡把串行更新改成交错/并行**',
    '❌ 把分辨率/震动/字幕放进角色存档',
    '❌ 皮肤解锁只按设备存储',
    '❌ 儿童档案只在前端隐藏按钮',
    '❌ **档案切换静默重启**（丢持续过程）',
    '❌ **成就与统计混为"全部清除"**',
    '❌ 云冲突只保留最新修改时间',
    '❌ **天气只写 current_weather**',
    '❌ **只复刻天气特效不复刻玩法耦合**',
    '❌ 室内外做成简单音量开关',
    '❌ **小地图只用世界坐标**（缺地图坐标与更新相位）',
]

FIELDS = [
    ('item_id', '项编号'),
    ('domain', '域（view / fov / budget / render / audio / input / topo / '
               'profile / switch / delprof / weather / wgame / indoor / '
               'season / map / mapup / efg）'),
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


def cmd_view(a):
    _hdr('🔴 视口（**拓扑状态机**）')
    print('拓扑: ' + ' · '.join(VIEW_TOPO))
    print('\n字段: ' + ' · '.join(VIEW_FIELDS))
    print(f'\n   {VIEW_RULE}')
    return 0


def cmd_fov(a):
    _hdr('🔑 FOV（**垂直分屏改变水平 FOV**）')
    print('fov_kind: ' + ' · '.join(FOV_KINDS))
    print('公式: ' + FOV_FORMULA)
    print('\n规则:')
    for r in FOV_RULE:
        print(f'   {r}')
    return 0


def cmd_budget(a):
    _hdr('预算（**每视口独立**）')
    print('每视口: ' + ' · '.join(BUDGET_PER_VIEW))
    print('\n规则:')
    for r in BUDGET_RULE:
        print(f'   {r}')
    return 0


def cmd_render(a):
    _hdr('渲染（**分屏顺序**）')
    for r in RENDER_ITEMS:
        print(f'   · {r}')
    print(f'\n   {RENDER_RULE}')
    return 0


def cmd_audio(a):
    _hdr('音频（**监听拓扑**）')
    for a_ in AUDIO_TOPO:
        print(f'   · {a_}')
    print(f'\n   {AUDIO_RULE}')
    return 0


def cmd_input(a):
    _hdr('🔑 输入与 HUD（**持久绑定**）')
    for i in INPUT_ITEMS:
        print(f'   · {i}')
    print(f'\n   {INPUT_RULE}')
    return 0


def cmd_topo(a):
    _hdr('拓扑重排（**事务**）')
    print('事件: ' + ' · '.join(TOPO_EVENTS))
    print(f'\n   {TOPO_RULE}')
    return 0


def cmd_profile(a):
    _hdr('🔴 档案（**七类隔离域**）')
    print(f'   {"级别":<14}{"内容":<32}切换时决定')
    print('   ' + '-' * 70)
    for k, content, act in PROFILE_LEVELS:
        print(f'   {k:<14}{content:<32}{act}')
    print('\n作用域拆分:')
    for k, ex in PROFILE_SCOPES:
        print(f'   {k:<20} {ex}')
    print('\n规则:')
    for r in PROFILE_RULE:
        print(f'   {r}')
    return 0


def cmd_switch(a):
    _hdr('切换（**六状态事务**）')
    print('   ' + ' → '.join(SWITCH_SIX))
    print('\n必须测量: ' + ' · '.join(SWITCH_MEASURE))
    print(f'\n   {SWITCH_RULE}')
    return 0


def cmd_delprof(a):
    _hdr('删除（**六个问题**）')
    for d in DEL_SIX:
        print(f'   · {d}')
    print('\n规则:')
    for r in DEL_RULE:
        print(f'   {r}')
    return 0


def cmd_weather(a):
    _hdr('🔑 天气（**两层状态机**）')
    print('宏观: ' + ' · '.join(WEATHER_MACRO))
    print('phase: ' + ' · '.join(WEATHER_PHASE))
    print('\n字段: ' + ' · '.join(WEATHER_FIELDS))
    print('\n规则:')
    for r in WEATHER_RULE:
        print(f'   {r}')
    return 0


def cmd_wgame(a):
    _hdr('🔴 天气（**玩法耦合事件契约**）')
    print('订阅系统: ' + ' · '.join(WEATHER_GAMEPLAY))
    print('\n组合伤害: ' + ' · '.join(WEATHER_COMBO))
    print('\n规则:')
    for r in WEATHER_GP_RULE:
        print(f'   {r}')
    return 0


def cmd_indoor(a):
    _hdr('室内外（**局部状态机**）')
    for i in INDOOR_ITEMS:
        print(f'   · {i}')
    print(f'\n   {INDOOR_RULE}')
    return 0


def cmd_season(a):
    _hdr('季节')
    for s in SEASON_ITEMS:
        print(f'   · {s}')
    return 0


def cmd_map(a):
    _hdr('🔑 小地图（**两套稳定坐标**）')
    for k, why in MAP_TWO_COORDS:
        print(f'   {k:<16} {why}')
    print('\n字段: ' + ' · '.join(MAP_FIELDS))
    print('\n规则:')
    for r in MAP_RULE:
        print(f'   {r}')
    print(f'\n   {MAP_FAIL}')
    return 0


def cmd_mapup(a):
    _hdr('小地图（**其他必记**）')
    for m in MAP_MORE:
        print(f'   · {m}')
    return 0


def cmd_efg(a):
    _hdr('E / F / G 补充')
    for k, why in EFG:
        print(f'\n   【{k}】\n      {why}')
    return 0


def cmd_init(a):
    os.makedirs(os.path.dirname(a.init) or '.', exist_ok=True)
    with open(a.init, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow([k for k, _ in FIELDS])
        w.writerow(['TODO'] * len(FIELDS))
    print(f'已生成共置/天气表: {a.init}')
    print('\n⚠️ 十七域：view / fov / budget / render / audio / input / topo / '
          'profile / switch / delprof / weather / wgame / indoor / season / '
          'map / mapup / efg')
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
    print(f'共置/天气 · {len(rows)} 条')
    print('=' * 76)
    if mismatch:
        print(f'\n🚫 **不一致** {len(mismatch)} 条（行 {mismatch[:15]}）')
    if no_legacy:
        print(f'\n❌ {len(no_legacy)} 条缺**原版值**（行 {no_legacy[:15]}）')
    if no_grade:
        print(f'\n🚫 {len(no_grade)} 条**证据等级缺失或 ≥7 级**'
              f'（行 {no_grade[:15]}）')

    if not (mismatch or no_legacy or no_grade):
        print('\n✅ 共置/天气：一致、原版值完整、证据等级达标')

    print('\n🔑 **共置 · 归属 · 空间语义：按谁的坐标、谁的预算、谁的权限。**')
    print('   **垂直分屏改变水平 FOV；单视口预算不是双玩家预算。**')
    print('   **天气不是视觉装饰，是玩法事实源；小地图失败在采样与排序。**')
    return 1 if (a.gate_check and (mismatch or no_legacy or no_grade)) else 0


def main():
    ap = argparse.ArgumentParser(description='共置归属与天气空间语义')
    ap.add_argument('--view', action='store_true')
    ap.add_argument('--fov', action='store_true')
    ap.add_argument('--budget', action='store_true')
    ap.add_argument('--render', action='store_true')
    ap.add_argument('--audio', action='store_true')
    ap.add_argument('--input', action='store_true')
    ap.add_argument('--topo', action='store_true')
    ap.add_argument('--profile', action='store_true')
    ap.add_argument('--switch', action='store_true')
    ap.add_argument('--delprof', action='store_true')
    ap.add_argument('--weather', action='store_true')
    ap.add_argument('--wgame', action='store_true')
    ap.add_argument('--indoor', action='store_true')
    ap.add_argument('--season', action='store_true')
    ap.add_argument('--map', action='store_true')
    ap.add_argument('--mapup', action='store_true')
    ap.add_argument('--efg', action='store_true')
    ap.add_argument('--init')
    ap.add_argument('--check')
    ap.add_argument('--gate-check', action='store_true')
    a = ap.parse_args()
    fns = {'view': cmd_view, 'fov': cmd_fov, 'budget': cmd_budget,
           'render': cmd_render, 'audio': cmd_audio, 'input': cmd_input,
           'topo': cmd_topo, 'profile': cmd_profile, 'switch': cmd_switch,
           'delprof': cmd_delprof, 'weather': cmd_weather, 'wgame': cmd_wgame,
           'indoor': cmd_indoor, 'season': cmd_season, 'map': cmd_map,
           'mapup': cmd_mapup, 'efg': cmd_efg}
    for k, fn in fns.items():
        if getattr(a, k):
            return fn(a)
    if a.init:
        return cmd_init(a)
    if a.check:
        return cmd_check(a)
    print('❌ 需要 --view / --fov / --budget / --render / --audio / --input / '
          '--topo / --profile / --switch / --delprof / --weather / --wgame / '
          '--indoor / --season / --map / --mapup / --efg / --init / --check '
          '之一')
    return 2


if __name__ == '__main__':
    sys.exit(main())
