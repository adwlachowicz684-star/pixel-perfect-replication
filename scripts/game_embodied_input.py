#!/usr/bin/env python3
"""具身表现 · 物品实体 · 非语言交互 · 肌肉记忆
（第三十五轮 A / B / C / D 类，含 E / F / G 补充）。

**🔑 本轮回填的主角是玩家持续观察 · 听见 · 操作的那层界面，
而不是又一套逻辑系统。**

> A—D 的共同点：原版**不一定要在屏幕上写出数字**，
> 玩家却能从**角色呼吸 · 脚步 · 镜头 · 动作受限 · 输入宽容度**中读出状态。
> 🔴 **若重制只迁移属性 · 背包 · 技能树，状态值仍正确，
> 但"像不像原版"已经改变。**

**🔑 建议 A—D 合入同一份《具身表现与输入契约清单》**
（`embodied_interface_contract.md`）；E—H 进入
《世界损失、信息冲突与多人边界清单》（`world_loss_and_social_boundaries.md`）。

**🔑 "must-match"应覆盖表现契约，不能只覆盖数据**：
- `exact` —— 步态帧 · 颜色 · 声音 · 延迟（**逐帧比对**）
- `tolerance` —— 时间窗允许设备补偿
- `deliberate` —— 重制目标明确要求改变

> 🔴 例如：把原来靠数字表达的饥饿改成"身体即 HUD"，
> **若非原版设计，则属冲突，不能标成改进**。

用法:
  game_embodied_input.py --body   # 🔑 角色是**状态画布**（八字段）
  game_embodied_input.py --stack  # 🔴 **多状态叠加矩阵**（不是后加覆盖前加）
  game_embodied_input.py --recov  # **恢复过程本身有可玩性**
  game_embodied_input.py --item   # 🔑 物品**四段生命周期**
  game_embodied_input.py --dura   # 🔴 **耐久是视觉可读性问题**
  game_embodied_input.py --swap   # 装备切换是**输入—动作契约**
  game_embodied_input.py --nonv   # 🔑 非语言**六字段**
  game_embodied_input.py --sil    # 🔴 **"沉默是选项"必须显式进选项表**
  game_embodied_input.py --gaze   # 注视与距离**是触发条件不是点缀**
  game_embodied_input.py --mus    # 🔑 肌肉记忆**六张时序表**
  game_embodied_input.py --phase  # Unity **started/performed/canceled** 可审计
  game_embodied_input.py --audio  # 🔑 声音是**信息源**（能否仅凭声音做决定）
  game_embodied_input.py --arb    # **声像冲突仲裁规则**
  game_embodied_input.py --loss   # 🔑 **非死亡时间损失**（F 不等于难度）
  game_embodied_input.py --miss   # **"错过"分三层**
  game_embodied_input.py --zone   # 🔑 多人**距离带成环**
  game_embodied_input.py --efgh   # E / F / G 摘要与 H 反例库
  game_embodied_input.py --init ledger/embodied_input.csv
  game_embodied_input.py --check ledger/embodied_input.csv --gate

退出码: 0 通过 / 1 缺项 / 2 用法错误
"""
import argparse
import csv
import os
import sys

# 🔑 角色状态画布八字段
BODY_FIELDS = [
    ('**channel**', '步态 · 呼吸 · 屏边 · LUT · FOV · 手柄震动 · 脚步 · 音色',
     'exact', '**第一项不是颜色，而是用了哪个通道**'),
    ('**threshold_table**', '25%/50%/0 切换哪一档？区间还是跳变？', 'exact',
     '阈值表要逐档录'),
    ('**source_value**', '血 · 耐力 · 饱食 · 体温 · 毒性累加器', 'exact',
     '内部值来源'),
    ('**layered_blend**', '颜色相加 · 最严重优先 · 相乘 · 后应用优先',
     'exact', '叠加方式'),
    ('**input_modulation**', '是否影响瞄准散布 · 跳跃高度 · 移动上限 · 转向',
     'exact', '🔑 **状态是否改变输入响应**'),
    ('**recovery**', '渐变/阶跃；恢复中是否仍可玩；有无"半恢复"档', 'exact',
     '恢复曲线'),
    ('**observer_scope**', '仅玩家 · 队友 · 敌人 · 镜子可见', 'exact',
     '多人可见性'),
    ('**accessibility_override**', '原版是否有色盲/震动/闪烁替代',
     'deliberate', '替代需显式决策'),
]

BODY_RULE = [
    '🔑 **状态外显的第一项不是颜色，而是它用了哪个通道**',
    '🔑 原版常见手法：低生命用**身体动画**，中毒用**肤色/粒子**，'
    '醉酒用**视角模糊+瞄准扰动**，疲劳用**步频和跳跃能力**',
    '🔴 **仅写一个"中毒变绿"会把后续调色 · 角色材质差异 · 状态叠加规则'
    '全部漏掉**',
]

# 🔴 叠加
STACK_FOUR = [
    '**同相叠加**（同时开始、同时最严重）',
    '**异相叠加**（一状态恢复、另一状态进入）',
    '**同标签互斥**',
    '**不同标签冲突**',
]

STACK_RULE = [
    '🔑 **多状态叠加必须形成"状态 × 表现"矩阵**，'
    '🔴 **而不是相信"后加的状态覆盖前面的状态"**',
    '🔑 每个状态对每种通道的**权重 · 上限 · 下限 · 乘算/加算**都要记，'
    '以及**恢复时谁先退出**',
    '🔑 中毒与醉酒同时出现时，颜色 · 模糊 · 呼吸 · 音效 · 输入惩罚'
    '**可能各自运行**',
    '🔑 若原版没有设计文档，证据等级应降至"**行为观察**"，'
    '并附**同一随机种子 · 同一状态**的对比录像',
]

# 恢复
RECOV_ITEMS = [
    '恢复时间 · **首帧变化** · **末帧变化**',
    '是否有**中间档**',
    '**死亡/受击/换装备是否中断恢复**',
    '**恢复过程中能否输入**',
    '恢复是否触发声音',
    '若渐变：相机与角色动画的**插值曲线**',
    '若触发提示：**是否抢走战斗焦点**',
]

RECOV_RULE = '🔴 **恢复过程本身常有可玩性，'
'最容易被"到 0 就恢复正常"抹平**'

# 🔑 物品四段生命周期
ITEM_FOUR = [
    ('**held**（持有）', '双手/单手 · 镜头偏移 · 重心 · 晃动 · 脚步 · 呼吸 · '
     '可换装 · **能否奔跑/潜行/爬梯**'),
    ('**worn**（装备）', '盔甲厚度视觉 · 金属高光 · 布质摩擦 · 脚步音色 · '
     '碰撞体 · **NPC 反应** · **重量对耐力的影响**'),
    ('**switched**（切换）', '收起/拔出完整动作 · **可打断窗口** · '
     '切换期间输入封锁 · 失败反馈 · 动画取消链'),
    ('**world**（世界）', '静态/物理 · 静置姿态 · 阴影 · 表面适配 · 拾取提示 · '
     '消失计时 · **被 NPC 拾取** · 其他玩家可见性'),
]

ITEM_RULE = [
    '🔑 **物品复刻最常见的偏差，是把"耐久 100/100"当成了物品的全部**',
    '🔑 B 的真正对象不是背包槽，而是物品存在的**四段生命周期**，'
    '**每段都可能有不同的模型 · 碰撞 · 声音 · 可见度和规则**',
    '🔴 **重制若只保留数据库和 UI 图标，玩家会失去'
    '"这件东西真的在我身上/地上"的感觉**',
]

# 🔴 耐久
DURA_ITEMS = [
    '原版用**纯数字 · 耐久条 · 颜色 · 图标角标 · 模型破损 · 多重皮肤**？',
    '**断裂瞬间**是否有碎裂声 · 粒子 · 镜头抖动 · 重量变化',
    '**耐久为 1 时是否保留最低功能**',
    '**修理是否立即满修还是逐步恢复**',
    '**不同材质/稀有度是否共用阈值**',
]

DURA_RULE = [
    '🔑 **耐久是"视觉可读性"问题，不只是资源消耗问题**',
    '🔴 **若原版只在提示框里显示数值，重制不能擅自加破损贴图**',
    '🔴 **反过来：原版已有可见裂痕，也不能因新引擎材质复杂而只留数字**',
]

# 装备切换
SWAP_ITEMS = [
    '输入 · 意图确认 · 动画开始 · **可打断点** · 完成点',
    '**碰撞/碰撞偏移变化**', '**输入封锁**', '失败反馈 · 回退路径',
    '网络预测与重放',
]

SWAP_RULE = [
    '🔑 **装备切换必须被当作一次输入—动作契约，而不是资源赋值**',
    '🔑 若切换被攻击打断，要记**状态是否回滚 · 武器是否部分拔出 · '
    '下一次输入是否仍被消耗**',
    '🔑 "**切换手感**"往往由**前摇 · 可取消窗口 · 输入响应**共同决定，'
    '🔴 **而不是动画长度**',
]

# 🔑 非语言六字段
NONV_FIELDS = [
    ('**gaze**（注视）', '谁先看谁 · 注视时长 · 断视后果 · 遮脸 · 镜中视线',
     '用简单对话触发替代，**失去"发现"**'),
    ('**proximity**（距离）', '开始 · 可对话 · **亲密冒犯** · 攻击/交易距离',
     '**统一互动半径，抹平社交距离**'),
    ('**silence**（沉默）', '是否可选 · 最短等待 · 超时 · 重试 · 后果',
     '**默认自动选第一项，沉默消失**'),
    ('**gesture**（手势）', '招手 · 点头 · 蹲下 · 敲门 · 敬礼 · 指路 · 拒绝',
     '只有表情或文本选项'),
    ('**body_posture**（姿态）', '背对 · 抱臂 · 武器指向 · 蹲伏 · 贴近',
     '对话动画过于通用'),
    ('**environmental_act**（环境动作）', '敲门 · 放花 · 点火 · 坐下 · 留物',
     '**动作只调用任务接口**'),
]

NONV_RULE = [
    '🔑 **C 的难点不是"有没有手势系统"，而是沉默 · 注视 · 距离 · 等待'
    '是否有叙事后果**',
    '🔑 一条非语言事件至少记：触发者 · 目标 · 关系 · 空间位置 · 朝向 · 视线 · '
    '开始/持续/结束 · 可中断条件 · 玩家可选回应 · NPC 后续状态 · 摄像机 · 音效',
    '🔴 传统对话树只记文本，会把"**长时间不按任何键**""**走近但不对话**"'
    '"**对话中转身离开**""**挥手后被拒绝**"全部丢掉',
]

# 🔴 沉默
SIL_THREE = [
    '原版**根本不允许沉默**',
    '原版**等待一定时间后进入特殊分支**',
    '原版把"**什么都不按**"当成**拒绝或失去时机**',
]

SIL_RULE = [
    '🔑 **"沉默是选项"必须显式进入选项表**',
    '🔑 每种要记**光标停留 · 默认高亮 · 超时 · 重复等待 · 跳过 · 回放保护**',
    '🔴 **若原版默认高亮第一项，重制不能因无障碍考虑擅自改为'
    '"什么都不做"**，除非有新的 `deliberate` 决策**并保留原版模式**',
]

# 注视
GAZE_ITEMS = [
    'NPC **视线锥**', '**头部/眼球 IK**', '玩家遮挡', '背对/面对',
    '**近距触发**', '**越界中断**', '多人目标选择',
]

GAZE_RULE = '🔑 **注视与距离不是表现点缀，而是可达性与事件触发条件**；'
'🔑 同一动作在**不同距离是否改变语义**（太远无法对话 · 适中可交易 · '
'**过近触发冒犯** · 贴脸是否影响动画和声音）'

# 🔑 肌肉记忆
MUS_SIX = [
    '**输入窗口**', '**缓冲**', '**取消**', '**前摇后摇**', '**锁定**',
    '**恢复**',
]

MUS_FIELDS = [
    '**原始事件**', '**动作阶段**', '**时间戳**', '**持续时间**',
    '缓冲 · 取消 · 抢占 · **复现种子**',
]

MUS_RULE = '🔑 **肌肉记忆由六张时序表组成，'
'🔑 只有日志和回放能证明没变**'

# 🔑 Unity 相位
PHASE_FOUR = [
    '**started**', '**performed**', '**canceled**', '**duration**',
]

PHASE_RULE = '🔑 Unity 输入回调可审计 **started/performed/canceled** · '
'时间与持续时间 · 可调 composite/interaction 参数 —— '
'这提供了**可审计接口**'
PHASE_ABSORB = '🔑 应吸收的是**表现事件与逻辑解耦** —— '
'虚幻 `UGameplayCueManager` 提供 `HandleGameplayCue/HandleGameplayCues` · '
'实例缓存 · 缺失提示 · 对象库和生命周期接口。'
'🔴 **不能用一个自带默认表现的库直接替换原版手调细节**'

# 🔑 声音
AUDIO_ITEMS = [
    '声源位置 · **最小可闻距离** · 衰减曲线 · 低频遮蔽',
    '朝向 · 遮挡 · 混响 · 多普勒',
    '**材质 · 鞋子/装备 · 地表 · 速度 · 潜行 multiplier**',
    '**敌人 AI 是否真正听见**',
]

AUDIO_RULE = [
    '🔑 **E 的 must-match 不只是音量，而是"玩家能否仅凭声音做决定"**',
    '🔑 要验证玩家在**盲听 · 遮挡 · 跨层 · 分屏**下能否定位',
    '🔴 **若原版靠"某只脚脚步更响"判断左右，随便做对称立体声就丢失了**',
    '🔑 **听不到的价值必须被测量，而不能被默认存在** —— '
    '要测**视觉未发现但声音已暴露**与**视觉已暴露但声音仍可隐藏**两条边界',
    '🔑 "**完全静音**"是否真的避开听觉 AI？掉落/换弹/受击/呼吸是否破隐？',
]

# 仲裁
ARB_ITEMS = [
    '视觉可见但**声音不存在**', '声音存在但**视觉遮挡**', '**声音先到**',
    '**视觉先到**', '**声音方向与视觉方向不一致**',
]

ARB_RULE = '🔑 **声像冲突要定义仲裁规则** —— '
'原版可能**声音主导警觉 · 视觉主导识别 · 距离主导衰减**。'
'🔴 **重制若统一用视觉射线触发 AI，潜行与听觉线索会失真**'

# 🔑 F
LOSS_ITEMS = [
    '走错路 · 重复劳动 · 无意义等待 · 限时错失',
    '错过 NPC · 错过对话 · 错过物品',
    '**不可逆选择** · **资源不可逆投入**',
    '**无法撤销的操作** · **世界状态推进后回不去了**',
]

LOSS_FIELDS = [
    ('**irreversible_event**', '哪个事件关闭分支？能否延时保存？'),
    ('**missed_window**', '时间窗 · 提示 · 补救 · 剧情后果'),
    ('**opportunity_cost**', '选择 A 时是否让玩家知道失去 B'),
    ('**sunk_cost**', '原版是否允许退还 · 分解 · 兑换 · 暂停 · 撤销 · 重置'),
    ('**backtrack**', '走错后最短修复路径与强制等待'),
    ('**idle_loss**', '等待不可跳过 · 无法加速 · 无法并行'),
]

LOSS_RULE = [
    '🔑 **F 与难度不同：难度决定挑战强度，F 决定玩家"做了无效事"后损失多少**',
    '🔑 每条要写**触发时间 · 可预见性 · 提示是否充分 · 补救窗口 · '
    '补救代价 · 重试路径 · 证据保存**',
]

# 错过三层
MISS_THREE = [
    ('**错过信息**', '可能只是提示'),
    ('**错过资源**', '可能是永久损失'),
    ('**错过规则改变**', '🔴 **可能让后续对话和结局变化**'),
]

MISS_RULE = '🔑 原版若用**环境叙事 · NPC 位置 · 限时天气**暗示机会，'
'🔴 **重制不能简单加感叹号**；🔴 **原版若什么都没提示，也不能擅自加教程**'

# 🔑 G 距离带
ZONE_RING = [
    '**存在感知**（声音 · 标记 · 脚印 · 位置频道）',
    '**距离带**（感知 · 互动 · 交易 · 攻击 · 冒犯）',
    '**越界反应**', '**靠近提示**',
    '**队友/陌生人/敌对身份**', '组队跟随 · 传送',
    '**围观干扰**', '目标选择', '碰撞/视线/**语音边界**',
]

ZONE_RULE = [
    '🔑 **G 不能只记录 PvP 规则，还要记录"附近有人"这一感知如何形成**',
    '🔑 每个距离带都要记**进入 · 停留 · 离开 · 同屏 · 分屏 · 旁观 · '
    '断线重连**表现',
    '🔑 **Vivox 位置频道证明了"距离+朝向"应是一等事件，而不是美术效果** —— '
    '含距离衰减 · 朝向渐变 · 人群噪声 · 进入/退出参与者事件',
    '🔴 **但它本身不是游戏内个人空间规范，也不覆盖 NPC 冒犯 · 碰撞 · '
    '游戏内交易规则**',
]

ZONE_STRANGER = '🔑 **"陌生玩家边界"要分协议层与体验两层** —— '
'协议层：能否交易 · 攻击 · 跟随 · 偷窃 · 组队 · 表情 · 私聊 · 位置语音。'
'体验层：是否有确认 · 冷却 · 范围 · 朝向 · 可见反馈 · 骚扰保护 · 旁观者提示。'
'🔴 **多人代码若把"其他玩家"只建模成网络对象，就会漏掉围观 · 越界 · '
'挡路 · 身份不确定**'

CONFLICTS = [
    '❌ **只迁移属性/背包/技能树**（状态值对但"不像原版"）',
    '❌ 只写"中毒变绿"',
    '❌ **相信"后加的状态覆盖前面的状态"**',
    '❌ "到 0 就恢复正常"（抹平恢复过程可玩性）',
    '❌ **把物品降格成数值条目**',
    '❌ **擅自加破损贴图 / 擅自只留数字**（双向偏离）',
    '❌ 装备切换当资源赋值',
    '❌ 对话树只记文本（丢沉默/注视/走近不说话）',
    '❌ **统一互动半径**（抹平社交距离）',
    '❌ **默认自动选第一项**（沉默消失）',
    '❌ 为无障碍擅自把默认项改成"什么都不做"',
    '❌ 用视觉射线统一触发 AI（听觉线索失真）',
    '❌ 随便做对称立体声（丢失左右脚步判断）',
    '❌ **把 F 并入难度八维**',
    '❌ 把"其他玩家"只建模成网络对象',
    '❌ **用自带默认表现的库替换原版手调细节**',
]

FIELDS = [
    ('item_id', '项编号'),
    ('domain', '域（body / stack / recov / item / dura / swap / nonv / sil / '
               'gaze / mus / phase / audio / arb / loss / miss / zone）'),
    ('legacy_value', '**原版值**'),
    ('new_value', '新引擎值'),
    ('match', '**是否一致**'),
    ('must_match', '**exact / tolerance / deliberate**'),
    ('evidence', '证据等级 1-8'),
]


def _hdr(t, w=80):
    print('=' * w)
    print(t)
    print('=' * w)


def cmd_body(a):
    _hdr('🔑 角色是**状态画布**（八字段）')
    print(f'   {"字段":<26}{"取证内容":<44}must_match')
    print('   ' + '-' * 76)
    for k, why, mm, _ in BODY_FIELDS:
        print(f'   {k:<26}{why:<44}{mm}')
    print('\n为什么:')
    for k, _, _, note in BODY_FIELDS:
        print(f'   {k:<26} {note}')
    print('\n规则:')
    for r in BODY_RULE:
        print(f'   {r}')
    return 0


def cmd_stack(a):
    _hdr('🔴 多状态叠加（**不是后加覆盖前加**）')
    for s in STACK_FOUR:
        print(f'   · {s}')
    print('\n规则:')
    for r in STACK_RULE:
        print(f'   {r}')
    return 0


def cmd_recov(a):
    _hdr('恢复（**过程本身有可玩性**）')
    for r in RECOV_ITEMS:
        print(f'   · {r}')
    print(f'\n   {RECOV_RULE}')
    return 0


def cmd_item(a):
    _hdr('🔑 物品（**四段生命周期**）')
    for k, why in ITEM_FOUR:
        print(f'\n   【{k}】\n      {why}')
    print('\n规则:')
    for r in ITEM_RULE:
        print(f'   {r}')
    return 0


def cmd_dura(a):
    _hdr('🔴 耐久（**视觉可读性问题**）')
    for d in DURA_ITEMS:
        print(f'   · {d}')
    print('\n规则:')
    for r in DURA_RULE:
        print(f'   {r}')
    return 0


def cmd_swap(a):
    _hdr('装备切换（**输入—动作契约**）')
    for s in SWAP_ITEMS:
        print(f'   · {s}')
    print('\n规则:')
    for r in SWAP_RULE:
        print(f'   {r}')
    return 0


def cmd_nonv(a):
    _hdr('🔑 非语言交互（**六字段**）')
    for k, why, loss in NONV_FIELDS:
        print(f'\n   【{k}】\n      {why}\n      重制损失: {loss}')
    print('\n规则:')
    for r in NONV_RULE:
        print(f'   {r}')
    return 0


def cmd_sil(a):
    _hdr('🔴 沉默（**必须显式进选项表**）')
    for s in SIL_THREE:
        print(f'   · {s}')
    print('\n规则:')
    for r in SIL_RULE:
        print(f'   {r}')
    return 0


def cmd_gaze(a):
    _hdr('注视与距离（**触发条件不是点缀**）')
    for g in GAZE_ITEMS:
        print(f'   · {g}')
    print(f'\n   {GAZE_RULE}')
    return 0


def cmd_mus(a):
    _hdr('🔑 肌肉记忆（**六张时序表**）')
    print('六张表: ' + ' · '.join(MUS_SIX))
    print('\n必记: ' + ' · '.join(MUS_FIELDS))
    print(f'\n   {MUS_RULE}')
    return 0


def cmd_phase(a):
    _hdr('🔑 输入相位（**可审计接口**）')
    print('   ' + ' · '.join(PHASE_FOUR))
    print(f'\n   {PHASE_RULE}')
    print(f'\n   {PHASE_ABSORB}')
    return 0


def cmd_audio(a):
    _hdr('🔑 声音（**信息源**）')
    for x in AUDIO_ITEMS:
        print(f'   · {x}')
    print('\n规则:')
    for r in AUDIO_RULE:
        print(f'   {r}')
    return 0


def cmd_arb(a):
    _hdr('声像冲突（**仲裁规则**）')
    for x in ARB_ITEMS:
        print(f'   · {x}')
    print(f'\n   {ARB_RULE}')
    return 0


def cmd_loss(a):
    _hdr('🔑 非死亡时间损失（**F 不等于难度**）')
    for x in LOSS_ITEMS:
        print(f'   · {x}')
    print('\n字段:')
    for k, why in LOSS_FIELDS:
        print(f'   {k:<26} {why}')
    print('\n规则:')
    for r in LOSS_RULE:
        print(f'   {r}')
    return 0


def cmd_miss(a):
    _hdr('错过（**三层**）')
    for k, why in MISS_THREE:
        print(f'   {k:<16} {why}')
    print(f'\n   {MISS_RULE}')
    return 0


def cmd_zone(a):
    _hdr('🔑 多人距离带（**成环**）')
    for z in ZONE_RING:
        print(f'   · {z}')
    print('\n规则:')
    for r in ZONE_RULE:
        print(f'   {r}')
    print(f'\n   {ZONE_STRANGER}')
    return 0


def cmd_efgh(a):
    _hdr('E / F / G 摘要与 H 反例库')
    print('   E 声音：见 --audio / --arb')
    print('   F 时间损失：见 --loss / --miss')
    print('   G 多人边界：见 --zone')
    print('\n   H 反例库（score_anti_pattern.py）:')
    for c in CONFLICTS[:8]:
        print(f'   {c}')
    return 0


def cmd_init(a):
    os.makedirs(os.path.dirname(a.init) or '.', exist_ok=True)
    with open(a.init, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow([k for k, _ in FIELDS])
        w.writerow(['TODO'] * len(FIELDS))
    print(f'已生成具身/输入表: {a.init}')
    print('\n⚠️ must_match 只能填 exact / tolerance / deliberate')
    print('\n⚠️ 十六域：body / stack / recov / item / dura / swap / nonv / '
          'sil / gaze / mus / phase / audio / arb / loss / miss / zone')
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

    OK = ('exact', 'tolerance', 'deliberate')
    mismatch, no_legacy, bad_mm, no_grade = [], [], [], []
    deli = []
    for i, r in enumerate(rows, 1):
        m = g(r, 'match').lower()
        if m not in ('yes', 'y', 'true', '是', '一致'):
            mismatch.append(i)
        if not g(r, 'legacy_value') or g(r, 'legacy_value') == 'TODO':
            no_legacy.append(i)
        mm = g(r, 'must_match').lower()
        if mm not in OK:
            bad_mm.append(i)
        elif mm == 'deliberate':
            deli.append(i)
        ev = g(r, 'evidence')
        if not ev or ev == 'TODO':
            no_grade.append(i)
        else:
            d = ev.split('.')[0].strip()
            if d.isdigit() and int(d) >= 7:
                no_grade.append(i)

    print('=' * 76)
    print(f'具身/输入 · {len(rows)} 条')
    print('=' * 76)
    if mismatch:
        print(f'\n🚫 **不一致** {len(mismatch)} 条（行 {mismatch[:15]}）')
    if no_legacy:
        print(f'\n❌ {len(no_legacy)} 条缺**原版值**（行 {no_legacy[:15]}）')
    if bad_mm:
        print(f'\n🚫 {len(bad_mm)} 条 must_match 非'
              f' exact/tolerance/deliberate（行 {bad_mm[:15]}）')
    if no_grade:
        print(f'\n🚫 {len(no_grade)} 条**证据等级缺失或 ≥7 级**'
              f'（行 {no_grade[:15]}）')
    if deli:
        print(f'\n⚠️  {len(deli)} 条标 `deliberate`（有意识偏离，'
              f'须有 owner 与到期日）：行 {deli[:15]}')

    if not (mismatch or no_legacy or bad_mm or no_grade):
        print('\n✅ 具身/输入：一致、原版值完整、must_match 合法、证据达标')

    print('\n🔑 **只迁移属性/背包/技能树：状态值仍正确，但"像不像原版"已改变。**')
    print('   **"中毒变绿"四个字会漏掉调色、材质差异与叠加规则。**')
    print('   **沉默必须是选项表的一行；统一互动半径会抹平社交距离。**')
    return 1 if (a.gate_check and
                 (mismatch or no_legacy or bad_mm or no_grade)) else 0


def main():
    ap = argparse.ArgumentParser(description='具身表现与输入契约')
    ap.add_argument('--body', action='store_true')
    ap.add_argument('--stack', action='store_true')
    ap.add_argument('--recov', action='store_true')
    ap.add_argument('--item', action='store_true')
    ap.add_argument('--dura', action='store_true')
    ap.add_argument('--swap', action='store_true')
    ap.add_argument('--nonv', action='store_true')
    ap.add_argument('--sil', action='store_true')
    ap.add_argument('--gaze', action='store_true')
    ap.add_argument('--mus', action='store_true')
    ap.add_argument('--phase', action='store_true')
    ap.add_argument('--audio', action='store_true')
    ap.add_argument('--arb', action='store_true')
    ap.add_argument('--loss', action='store_true')
    ap.add_argument('--miss', action='store_true')
    ap.add_argument('--zone', action='store_true')
    ap.add_argument('--efgh', action='store_true')
    ap.add_argument('--init')
    ap.add_argument('--check')
    ap.add_argument('--gate-check', action='store_true')
    a = ap.parse_args()
    fns = {'body': cmd_body, 'stack': cmd_stack, 'recov': cmd_recov,
           'item': cmd_item, 'dura': cmd_dura, 'swap': cmd_swap,
           'nonv': cmd_nonv, 'sil': cmd_sil, 'gaze': cmd_gaze, 'mus': cmd_mus,
           'phase': cmd_phase, 'audio': cmd_audio, 'arb': cmd_arb,
           'loss': cmd_loss, 'miss': cmd_miss, 'zone': cmd_zone,
           'efgh': cmd_efgh}
    for k, fn in fns.items():
        if getattr(a, k):
            return fn(a)
    if a.init:
        return cmd_init(a)
    if a.check:
        return cmd_check(a)
    print('❌ 需要 --body / --stack / --recov / --item / --dura / --swap / '
          '--nonv / --sil / --gaze / --mus / --phase / --audio / --arb / '
          '--loss / --miss / --zone / --efgh / --init / --check 之一')
    return 2


if __name__ == '__main__':
    sys.exit(main())
