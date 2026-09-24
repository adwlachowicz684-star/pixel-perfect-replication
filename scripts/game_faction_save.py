#!/usr/bin/env python3
"""声望派系 + 存档兼容体验（第十五轮 C / D 类）+ 玩法耦合（E/F/G）。

**🔑 C 类核心**：
> **声望不是进度条，而是触发条件与呈现状态的组合。**
> 🔴 **"看见"和"生效"可能不同** —— 可能立即显示 +10，但下一帧才允许购买。
> 🔴 **把多派系合并成"善恶值"是严重偏离**。

**🔑 D 类核心**：
> **存档列表本身就是系统状态。**
> 🔴 **用默认零值静默补齐缺失字段** —— 与"must-match 不许擅自改"直接冲突。
> 🔴 **损坏后清空进度** 是不可接受的。

用法:
  game_faction_save.py --axis      # 声望四张表
  game_faction_save.py --matrix    # 🔴 独立累加 vs **零和守恒**
  game_faction_save.py --feedback  # 🔴 **看见** vs **生效**
  game_faction_save.py --questmutex# 任务冲突是**图**不是清单
  game_faction_save.py --slot      # 🔴 存档列表是**系统状态**
  game_faction_save.py --migrate   # 跨版本迁移（**双向**）
  game_faction_save.py --platform  # 跨平台/云冲突
  game_faction_save.py --corrupt   # 🔴 损坏**检测/隔离/修复/告知**
  game_faction_save.py --weather   # 天气玩法耦合
  game_faction_save.py --light     # 🔴 光照作为**玩法机制**
  game_faction_save.py --shadow    # 阴影作为**信息源**
  game_faction_save.py --physics   # 物理交互玩法层
  game_faction_save.py --init ledger/faction_save.csv
  game_faction_save.py --check ledger/faction_save.csv --gate

退出码: 0 通过 / 1 缺项 / 2 用法错误
"""
import argparse
import csv
import os
import sys

# 声望四张表
AXIS_TABLES = [
    ('**声望轴**', '每派系数值 · 可见/隐藏 · 上限/下限 · **显示精度** · '
     '四舍五入 · 是否跨存档持久'),
    ('**关系状态**', '阈值 · 状态名 · 进入/退出条件 · **hysteresis**'),
    ('**反馈呈现**', 'UI 图标 · 颜色 · 称号 · 旁白 · **NPC 台词** · 价格 · '
     '商品解锁 · **区域准入** · 敌意'),
    ('**任务依赖**', '开启 · 隐藏 · 替代 · 失败 · **延迟** · 反转 · 补偿'),
]

# 🔴 关系矩阵
MATRIX_FIELDS = [
    '中立', '盟友', '敌对', '**共享声望**', '**反向声望**', '声誉溢出',
    '**隐藏厌恶**', '**时间衰减**',
]

MATRIX_Q = [
    '**帮 A 是否直接扣 B**',
    '是否**仅在该任务分支内**扣',
    '**是否可双满 / 可双敌 / 可重置 / 可赎罪**',
    '声望是否通过**物品、礼金、任务、杀戮、时间或第三方行为**改变',
]

MATRIX_EVENT = [
    '原因', '来源派系', '目标派系', '数值', '**是否显示**', '**是否延迟**',
    '是否可撤销', '**是否广播给其他 NPC**', '**是否会触发立即报复**',
]

MATRIX_RULE = '🔴 **多派系必须明确"独立累加"还是"零和守恒"**'

# 🔴 看见 vs 生效
FEEDBACK_RULE = [
    '🔴 **"看见"和"生效"可能不同**',
    '🔑 可能立即显示 +10，但**下一帧才允许购买**',
    '🔑 可能先改变关系，**下一次对话才播放台词**',
    '🔑 可能数值改变但**价格有独立折扣表**',
]

FEEDBACK_FIELDS = [
    '**反馈延迟**', '**同帧多声望变化的排序**', '**正负相抵展示**',
    '声望满值后的**状态锁**', '失败任务的**延迟惩罚**',
    '**匿名行为是否被识别**', '**伪装/变身/换装是否绕过识别**',
]

FEEDBACK_RULE2 = '🔴 若复刻把所有反馈压成一次 toast → '
'玩家将失去原作"**世界记得你做了什么**"的层次'

# 任务冲突
QUEST_MUTEX_FIELDS = [
    '依赖派系', '声望阈值', '**互斥任务**', '替代奖励', '过期时间',
    '**失败后是否仍可解锁**', '是否影响结局', '**是否只影响本周目**',
]

QUEST_MUTEX_TESTS = [
    '**先做帮 A 任务、回档改帮 B**', '**声望临界值只差一点**',
    '**同时接 A/B 再选一边**', '**在对话承诺与动作完成之间读档**',
    '**派系关系因第三方事件改变**',
]

QUEST_MUTEX_SORT = [
    '派系优先级', '声望', '任务顺序', '任务 ID', '分支 ID', '**因果链索引**',
]

QUEST_MUTEX_RULE = [
    '🔑 任务冲突应记录**图而非清单**',
    '🔑 稳定排序键至少要区分上述六项 —— '
    '否则同一组条件可能产生不同可用任务',
]

# 🔴 存档列表
SLOT_VISIBLE = [
    '角色名', '职业', '等级', '**游戏日期**', '**现实时间**', '地点', '任务',
    '平台', '**版本**', '**模组**', '截图', '时长', '难度', '死亡次数',
    '**同步状态**', '**损坏状态**',
]

SLOT_FIELDS = [
    '**排序默认键**', '玩家排序', '收藏/备注', '过滤', '空槽',
    '**自动存档/手动存档/检查点/云存档区分**',
    '选择、删除、复制、覆盖、命名、导出、导入的**确认流程**',
]

SLOT_INVISIBLE = [
    '唯一 ID', '**父存档**', '**分支**', '**依赖资产**', '**迁移历史**',
]

SLOT_RULE = [
    '🔑 保存界面也要记**输入延迟、滚动位置、选中态、删除焦点、'
    '控制器提示、读屏标签与暂停状态**',
]

SLOT_RULE2 = '🔴 **存档列表本身就是系统状态**'

# 迁移
MIGRATE_RULE = [
    '🔑 **先复制后转换**，比较**业务状态哈希**而非二进制相等',
    '🔑 CI 应跑**双向升级，不只是单向向前**',
    '🔑 建议建立"**永久 fixture 库**"：每个历史版本的极小存档、边界存档、'
    '损坏存档、平台存档、模组合法/非法组合、迁移中断档',
]

MIGRATE_Q = [
    '旧存档能否在新版用', '**丢失什么**', '**是否有提示**',
    '**能否回退**', '**回退后存档是否可用**',
]

# 平台
PLATFORM_FIELDS = [
    'PC / 主机 / 云', '**是否互通**', '限制',
    '**以最后修改时间解决云冲突**（❌ 禁止）',
]

# 🔴 损坏
CORRUPT_DETECT = [
    '读取顺序', '校验和', '**字段范围**', '**引用完整性**',
    '**跨文件一致性**', '资产存在性', '**循环引用**',
]

CORRUPT_ISOLATE = [
    '**不覆盖原档**', '创建 quarantine 副本', '**禁止自动继续写入**',
]

CORRUPT_REPAIR = [
    '**只修复明确可逆字段**', '修复前**保存原始字节哈希**',
    '无法修复则**保留可浏览的进度信息**而非直接清空',
]

CORRUPT_NOTIFY = [
    '使用**玩家语言**', '显示**版本与损坏位置**', '是否可继续',
    '是否可导出', '是否联系支持', '**是否关闭云同步防止污染**',
    '失败界面应提供**重试/退出/另存/备份/诊断信息**',
]

CORRUPT_RULE = [
    '🔑 损坏处理必须分为**检测 / 隔离 / 修复 / 告知**四步',
    '🔴 **不能只弹"存档损坏"**',
    '🔴 **损坏后清空进度**是不可接受的',
]

# 天气玩法
WEATHER_GAMEPLAY = [
    '**移动摩擦**', '**跳跃高度**', '**能见度**', '**命中率**',
    '**声音传播**', '**火把熄灭**', '**敌人感知**', 'NPC 日程',
    '**区域准入**', '音乐', '任务条件',
]

# 🔴 光照玩法
LIGHT_STEALTH = [
    '**光量采样位置**', '单位', '线性/感知空间',
    '**方向光与间接光权重**', '**明暗阈值**', '**移动/静止阈值**',
    '装备遮挡', '蹲伏/匍匐', '草丛', '雨水反光', '**敌人视力衰减**',
    '**记忆衰减**',
]

LIGHT_PUZZLE = [
    '光源 ID', '开关', '强度', '颜色', '持续时间', '**传播介质**',
    '遮挡', '反射', '镜面', '**时序容差**',
]

LIGHT_NAV = ['光源与可见标记', '**寻路标记**', '区域发现的关系']

LIGHT_DESTROY = [
    '可破坏 HP', '掉落', '**断电范围**', '**残光**', '重启', '再生',
    '**备用电源**', '**破坏期间保存**', '**NPC 反应**',
]

LIGHT_RULE = '🔴 光照作为玩法时，**阈值必须可测**'

# 阴影
SHADOW_FIELDS = [
    '**阴影出现时刻**', '对象最小尺寸', '距离', '层级', '室内/室外',
    '时间精度', '摄像机角度', '投影表面', '透明遮挡', '多光源叠加',
    '**低画质档降级**', '阴影分辨率边界', '**动态与静态对象差异**',
]

SHADOW_RULE = '🔴 若原作允许玩家**从影子发现敌人**，而新引擎因阴影串流或'
'遮挡规则变化使**影子延迟一帧** → 这就是 must-match 的玩法偏差，'
'**不应以"低画质无法复现"抹平**'

# 物理玩法
PHYSICS_PUSH = [
    '抓握点', '施力方向', '质量', '摩擦', '阻尼', '地面斜率',
    '**协作人数**', '动画时长', '输入缓冲', '中断', '体力',
    '角色朝向与摄像机',
]

PHYSICS_STACK = [
    '**稳定判据**', '接触点', '重心', '**扰动传播**', '**延迟坍塌**',
    '撤销/重试',
]

PHYSICS_DESTROY = [
    'HP', '断裂面', '**碎块数量**', '**质量守恒**', '碰撞层级', '声音',
    '遮挡', '可见性', '**寻路更新**', '性能降级',
]

PHYSICS_FLUID = [
    '**水位高度场**', '浮力', '阻力', '**载具浮力**', '游泳输入',
    '物体漂浮', '吸力/波浪', '区域过渡', '**冻结/蒸发**', '**保存精度**',
]

PHYSICS_Q = [
    '**破坏物挡住路径后，NPC 是否重新规划**',
    '**碎片是否参与击杀判定**',
    '**低配下碎块减少是否改变解谜**',
]

PHYSICS_RULE = '🔑 物理交互要记录**主观重量与确定性结果**'

CONFLICTS = [
    '❌ **将多派系合并成"善恶值"**',
    '❌ 让所有声望变化立刻刷新全部 UI',
    '❌ 把隐藏声望显式展示',
    '❌ 把任务互斥改成可同时完成',
    '❌ **为"给玩家更清楚"而删除延迟反馈**',
    '❌ 用声誉平均值替代原始关系矩阵',
    '❌ **用默认零值静默补齐缺失字段**',
    '❌ 升级后删除旧字段 / 未知字段全部忽略',
    '❌ **二进制格式不写版本**',
    '❌ **只测当前版本能读**',
    '❌ **以最后修改时间解决云冲突**',
    '❌ 自动覆盖原档 / **损坏后清空进度**',
    '❌ **为了"更友好"而自动合并玩家分支**',
    '❌ 把天气降为装饰粒子',
    '❌ 把光照硬编码为"暗=潜行"',
    '❌ 把动态阴影改成烘焙',
    '❌ 物理只保留可见碰撞',
    '❌ **破坏碎块数量随性能档变化**',
    '❌ 低画质自动关闭玩法相关阴影',
    '❌ **把推拉手感"手调得更舒服"**',
    '❌ 玩家可破坏物体统一改为不可破坏',
]

CONFLICTS_FINAL = '🔴 **任何让表现目标压过原作规则的优化，都属于理念冲突。**'

FIELDS = [
    ('item_id', '项编号'),
    ('domain', '域（axis / matrix / feedback / questmutex / slot / migrate / '
               'platform / corrupt / weather / light / shadow / physics）'),
    ('legacy_value', '**原版值**'),
    ('new_value', '新引擎值'),
    ('match', '**是否一致**'),
    ('tolerance', '**允许偏差**'),
    ('evidence', '证据'),
]


def _hdr(t, w=80):
    print('=' * w)
    print(t)
    print('=' * w)


def cmd_axis(a):
    _hdr('声望四张表')
    for k, v in AXIS_TABLES:
        print(f'   {k}')
        print(f'      {v}')
    return 0


def cmd_matrix(a):
    _hdr('🔴 关系矩阵（**独立累加 vs 零和**）')
    print('关系: ' + ' · '.join(MATRIX_FIELDS))
    print('\n必答:')
    for q in MATRIX_Q:
        print(f'   · {q}')
    print('\n声望变化事件字段: ' + ' · '.join(MATRIX_EVENT))
    print(f'\n   {MATRIX_RULE}')
    return 0


def cmd_feedback(a):
    _hdr('🔴 反馈（**看见 vs 生效**）')
    for r in FEEDBACK_RULE:
        print(f'   {r}')
    print('\n字段: ' + ' · '.join(FEEDBACK_FIELDS))
    print(f'\n   {FEEDBACK_RULE2}')
    return 0


def cmd_questmutex(a):
    _hdr('任务冲突（**图而非清单**）')
    for f in QUEST_MUTEX_FIELDS:
        print(f'   · {f}')
    print('\n测试: ' + ' · '.join(QUEST_MUTEX_TESTS))
    print('\n稳定排序键: ' + ' · '.join(QUEST_MUTEX_SORT))
    print('\n规则:')
    for r in QUEST_MUTEX_RULE:
        print(f'   {r}')
    return 0


def cmd_slot(a):
    _hdr('🔴 存档列表（**系统状态**）')
    print('可见字段: ' + ' · '.join(SLOT_VISIBLE))
    print('\n字段: ' + ' · '.join(SLOT_FIELDS))
    print('\n不可见但应记录: ' + ' · '.join(SLOT_INVISIBLE))
    print('\n规则:')
    for r in SLOT_RULE:
        print(f'   {r}')
    print(f'   {SLOT_RULE2}')
    return 0


def cmd_migrate(a):
    _hdr('跨版本迁移（**双向**）')
    print('必答: ' + ' · '.join(MIGRATE_Q))
    print('\n规则:')
    for r in MIGRATE_RULE:
        print(f'   {r}')
    return 0


def cmd_platform(a):
    _hdr('跨平台与云')
    for f in PLATFORM_FIELDS:
        print(f'   · {f}')
    return 0


def cmd_corrupt(a):
    _hdr('🔴 损坏（**检测/隔离/修复/告知**）')
    print('检测: ' + ' · '.join(CORRUPT_DETECT))
    print('\n隔离: ' + ' · '.join(CORRUPT_ISOLATE))
    print('\n修复: ' + ' · '.join(CORRUPT_REPAIR))
    print('\n告知: ' + ' · '.join(CORRUPT_NOTIFY))
    print('\n规则:')
    for r in CORRUPT_RULE:
        print(f'   {r}')
    return 0


def cmd_weather(a):
    _hdr('天气玩法耦合')
    print('影响: ' + ' · '.join(WEATHER_GAMEPLAY))
    print('\n🔑 天气**不只是视觉**')
    return 0


def cmd_light(a):
    _hdr('🔴 光照作为玩法机制')
    print('潜行: ' + ' · '.join(LIGHT_STEALTH))
    print('\n解谜: ' + ' · '.join(LIGHT_PUZZLE))
    print('\n导航: ' + ' · '.join(LIGHT_NAV))
    print('\n光源破坏: ' + ' · '.join(LIGHT_DESTROY))
    print(f'\n   {LIGHT_RULE}')
    return 0


def cmd_shadow(a):
    _hdr('阴影作为信息源')
    for f in SHADOW_FIELDS:
        print(f'   · {f}')
    print(f'\n   {SHADOW_RULE}')
    return 0


def cmd_physics(a):
    _hdr('物理交互玩法层')
    print('推/拉: ' + ' · '.join(PHYSICS_PUSH))
    print('\n平衡/堆叠: ' + ' · '.join(PHYSICS_STACK))
    print('\n破坏: ' + ' · '.join(PHYSICS_DESTROY))
    print('\n流体: ' + ' · '.join(PHYSICS_FLUID))
    print('\n必答:')
    for q in PHYSICS_Q:
        print(f'   · {q}')
    print(f'\n   {PHYSICS_RULE}')
    return 0


def cmd_init(a):
    os.makedirs(os.path.dirname(a.init) or '.', exist_ok=True)
    with open(a.init, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow([k for k, _ in FIELDS])
        w.writerow(['TODO'] * len(FIELDS))
    print(f'已生成声望/存档表: {a.init}')
    print('\n⚠️ 十二域：axis / matrix / feedback / questmutex / slot / '
          'migrate / platform / corrupt / weather / light / shadow / physics')
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

    mismatch, no_legacy = [], []
    for i, r in enumerate(rows, 1):
        m = g(r, 'match').lower()
        if m not in ('yes', 'y', 'true', '是', '一致'):
            mismatch.append(i)
        if not g(r, 'legacy_value') or g(r, 'legacy_value') == 'TODO':
            no_legacy.append(i)

    print('=' * 76)
    print(f'声望/存档 · {len(rows)} 条')
    print('=' * 76)
    if mismatch:
        print(f'\n🚫 **不一致** {len(mismatch)} 条（行 {mismatch[:15]}）')
    if no_legacy:
        print(f'\n❌ {len(no_legacy)} 条缺**原版值**（行 {no_legacy[:15]}）')

    if not (mismatch or no_legacy):
        print('\n✅ 声望/存档：一致且原版值完整')

    print('\n🔑 **声望"看见"与"生效"可能不同，别压成一次 toast。**')
    print('   **禁止用默认零值静默补齐缺失字段；损坏不得清空进度。**')
    print(f'   {CONFLICTS_FINAL}')
    return 1 if (a.gate_check and (mismatch or no_legacy)) else 0


def main():
    ap = argparse.ArgumentParser(description='声望派系与存档兼容')
    ap.add_argument('--axis', action='store_true')
    ap.add_argument('--matrix', action='store_true')
    ap.add_argument('--feedback', action='store_true')
    ap.add_argument('--questmutex', action='store_true')
    ap.add_argument('--slot', action='store_true')
    ap.add_argument('--migrate', action='store_true')
    ap.add_argument('--platform', action='store_true')
    ap.add_argument('--corrupt', action='store_true')
    ap.add_argument('--weather', action='store_true')
    ap.add_argument('--light', action='store_true')
    ap.add_argument('--shadow', action='store_true')
    ap.add_argument('--physics', action='store_true')
    ap.add_argument('--init')
    ap.add_argument('--check')
    ap.add_argument('--gate-check', action='store_true')
    a = ap.parse_args()
    fns = {'axis': cmd_axis, 'matrix': cmd_matrix, 'feedback': cmd_feedback,
           'questmutex': cmd_questmutex, 'slot': cmd_slot,
           'migrate': cmd_migrate, 'platform': cmd_platform,
           'corrupt': cmd_corrupt, 'weather': cmd_weather,
           'light': cmd_light, 'shadow': cmd_shadow, 'physics': cmd_physics}
    for k, fn in fns.items():
        if getattr(a, k):
            return fn(a)
    if a.init:
        return cmd_init(a)
    if a.check:
        return cmd_check(a)
    print('❌ 需要 --axis / --matrix / --feedback / --questmutex / --slot / '
          '--migrate / --platform / --corrupt / --weather / --light / '
          '--shadow / --physics / --init / --check 之一')
    return 2


if __name__ == '__main__':
    sys.exit(main())
