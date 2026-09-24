#!/usr/bin/env python3
"""重复可玩结构 + 玩家表达与身份 + 次级盲区（第十七轮 C / D / E-H）。

**🔑 C 类核心**：
> **"随机"至少要分层到十层，才能计算第二次游玩的差异量。**
> 🔴 若地图、敌人、物品全部变，而**规则、事件、支线、结局完全相同**，
> **体验重复仍会快速出现**。
> 🔴 **新游戏+不是难度标签，而是一份跨周目契约。**

**🔑 D 类核心**：
> **复刻的不是滑块数量，而是外观是否真正进入各场景。**
> 🔴 只保存"选择了哪个部件"而**不保存层级与混搭状态** ——
> 会在新增服装后**改变旧存档外观**。

用法:
  game_replay_identity.py --runlayer  # 🔴 随机**十层**
  game_replay_identity.py --ngplus    # 🔴 新游戏+ **继承契约**
  game_replay_identity.py --honest    # 可见变化 vs **隐藏变化**
  game_replay_identity.py --fatigue   # 疲劳来自**确定性重复**
  game_replay_identity.py --slot      # 🔴 定制**槽位与约束**
  game_replay_identity.py --showcase  # 🔴 展示场景是**系统状态**
  game_replay_identity.py --identity  # 身份**四种可见性**
  game_replay_identity.py --ugc       # 🔴 UGC 兼容性**早于分享**
  game_replay_identity.py --intuition # 交互直觉**四个层级**
  game_replay_identity.py --learning  # 🔴 学习曲线**可回放行为数据**
  game_replay_identity.py --explain   # 系统可解释性
  game_replay_identity.py --obscure   # 🔴 **故意不告诉玩家**要显式建模
  game_replay_identity.py --init ledger/replay_identity.csv
  game_replay_identity.py --check ledger/replay_identity.csv --gate

退出码: 0 通过 / 1 缺项 / 2 用法错误
"""
import argparse
import csv
import os
import sys

# 🔴 随机十层
RUN_LAYERS = [
    '世界种子', '区域模板', '**连接关系**', '敌人与分布', '掉落表',
    '**事件/支线**', '**对话条件**', '**数值规则**', '玩家能力', '展示内容',
]

RUN_LAYER_META = [
    '**在开局 / 进入区域 / 首次加载时确定**', '**是否允许回滚**',
    '**是否可跨存档访问**',
]

RUN_RULE = [
    '🔴 只说"roguelike 随机地图"**无法回答第二局变化多少**',
    '🔑 每层还要记上述三项元信息',
]

# 🔴 NG+ 契约
NGPLUS_ITEMS = [
    '角色等级', '技能', '装备', '消耗品', '货币', '外观', 'codex', '解锁',
    '图鉴', '任务状态', '世界状态', '相机设置', '控制设置', '统计',
    '名声', '声望', '存档元信息', '平台服务状态', '**Bug 利用**',
    '**种子偏好**',
]

NGPLUS_DIRS = [
    '继承', '**软上限继承**', '**兑换为代币**', '**只解锁不发放**',
    '丢弃', '不可继承',
]

NGPLUS_HIDDEN = [
    '**敌人 AI**', '敌人池', '伤害公式', '商店库存', '掉落表',
    '事件概率', '镜头', '读取速度', '**显示概率**', '演出',
]

NGPLUS_RULE = [
    '🔴 **新游戏+不是难度标签，而是一份跨周目契约**',
    '🔑 逐项记上述 20 类内容的**保留方向**（六种之一）',
    '🔴 最易遗漏：进入 NG+ **是否改变敌人 AI / 敌人池 / 伤害公式 / '
    '商店库存 / 掉落表 / 事件概率 / 镜头 / 读取速度 / 显示概率 / 演出**',
    '🔴 **若原版从第二周目开始悄悄修改不可见参数，必须记录** —— '
    '**不能因为"难度提升"就视为模糊许可**',
]

# 诚实性
HONEST_VISIBLE = ['名称', '入口', '提示', '敌人外观或配置']
HONEST_HIDDEN = [
    'AI 状态转移', '判定盒', '伤害', '速度', '资源奖励', '读取概率',
]

HONEST_RULE = [
    '🔑 玩家投诉"**二周目突然变难**"常来自**难度只在内部变化**',
    '🔑 投诉"**二周目太简单**"则常来自**只继承数值而内容不变**',
    '🔑 二者都需把"**继承**"与"**挑战曲线**"分成**两个状态表**',
]

# 疲劳
FATIGUE_METRICS = [
    '首局完成事件集合', '**第二局新增集合**', '第三局新增集合',
    '固定内容命中率', '随机内容重复率', '模板重复率',
    '叙事分支覆盖率', '玩家能力组合覆盖率', '玩家可见内容覆盖率',
]

FATIGUE_TRIGGERS = [
    '重放同一入场动画', '重复同一谜题', '长走廊无分支', '固定 boss 前门',
    '固定拾取节拍', '**不可跳过的教程**',
]

FATIGUE_ANTI = [
    '快进', '跳过', '路径捷径', '节奏变化', '第二路线', '洗牌顺序',
]

FATIGUE_RULE = '🔴 **疲劳点来自确定性重复，而非内容总量** —— '
'不能只统计资产数量'

# 🔴 定制槽位
SLOT_ITEMS = [
    '头部', '脸型', '肤色', '斑痕', '发型', '发色', '胡须', '眉毛', '眼睛',
    '妆容', '身高', '体型', '四肢比例', '走/跑/待机姿态', '服装层', '材质',
    '图案', '颜色', '配件', '披风', '背包', '武器外观', '载具', '宠物',
    '签名', '名号', '徽章',
]

SLOT_FIELDS = [
    '**最小步长**', '是否允许负值/越界裁剪', '**是否混搭**',
    '**左右是否对称**', '**颜色是 HSB 还是 RGB**', '是否保存脏位',
    '读取默认值', '**缺失资产回退值**',
]

SLOT_RULE = '🔴 只保存"选择了哪个部件"而**不保存层级与混搭状态** → '
'**会在新增服装后改变旧存档外观**'

# 🔴 展示场景
SHOWCASE_SCENES = [
    '**第一人称镜面**', '第三人称菜单', 'Lobby', '观战', '过场', '死亡回放',
    '拍照模式', '加载界面', '匹配卡片', '排行榜', '分享图',
    '截图 EXIF/水印', '**其他玩家实时可见性与可见距离**',
]

SHOWCASE_FIELDS = [
    'LOD', '骨骼', 'SpringBone', '布料', '面部 blendshape', '头发穿透',
    '武器碰撞', '附件阴影', '**第一人称去头规则**', '**镜面裁剪**',
]

SHOWCASE_RULE = '🔴 **展示场景与观看者是系统状态，不是美术彩蛋**'

# 身份
IDENTITY_VIS = [
    '**自述**', '**同伴可见**', '**陌生人可见**', '**跨平台可见**',
]

IDENTITY_ITEMS = [
    '名号', '徽章', '签名', '头衔', '字色', '称号', '击杀数', '排名',
    '公会', '好友关系', '最近游玩时间', '在线状态',
]

IDENTITY_FILTER = [
    '本地静音/屏蔽', '平台屏蔽', '好友优先', '敏感词', '昵称冲突',
    '**Unicode 双向文本**', '**零宽字符**', '重复空白', '过长截断',
    '大小写折叠',
]

IDENTITY_RULE = '🔴 若原版允许表情符号而重制只保留 ASCII → '
'**不只是输入限制变化，也会改变老玩家身份可读性**'

# 🔴 UGC
UGC_FIELDS = [
    '内容格式', '**规范版本**', '引擎版本', '**依赖资产哈希**',
    '材质白名单', '脚本能力', '最大多边形数/纹理/骨骼/附件数',
    '运行时配额', '**导入后是否执行代码**', '预览缩略图', '创作者署名',
    '许可', '举报与下架状态',
]

UGC_RULE = [
    '🔑 **UGC 的兼容性契约必须早于分享功能**',
    '🔑 纯数据关卡可安全重放；**可执行脚本必须沙箱、资源限额、'
    '禁止文件系统/网络访问**，并明确**内容失效后的回退**',
]

# 交互直觉
INTUITION_LEVELS = [
    ('无提示', '玩家自己发现'),
    ('**环境痕迹**', '磨损、脚印、光照'),
    ('持续高亮', '可交互物发光'),
    ('**直接文字**', '按 E 开门'),
]

INTUITION_FIELDS = [
    '**提示何时出现**', '**何时消失**',
    '**是否按注视/距离/角度/工具/角色状态分层**',
    '**失败后提示是否变化**',
]

PUSH_FIELDS = [
    '重量', '质量', '受力阈值', '移动摩擦', '动画阻力', '声音', '镜头抖动',
    '手柄振动', '角色姿态', '**错误时长**',
]

PUSH_RULE = '🔴 若只是把物体"**锁定**"，'
'**玩家会把世界读成"还没找到开关"**'

INTERACT_STATE = [
    'first_detect_radius', 'strong_radius', '**deadzone_angle**',
    '**cone_angle**', 'occlusion_rule', 'line_of_sight_rule',
    'height_offset', 'crouch_modifier', 'tool_required_tag',
    'one_way_platform_rule', 'interact_cooldown',
]

INTERACT_RULE = [
    '🔑 距离与角度应记录为**状态机**，而不是"交互范围 2.5 米"',
    '🔑 还要记连续交互是否抢占、能否同时与两个对象交互、'
    '目标切换是否抖动、视角移动是否造成目标跳动',
    '🔴 若重制加入更灵敏的高亮，却把原本需要定位的技巧变成自动吸附 → '
    '**这是偏离**',
]

# 🔴 学习曲线
LEARNING_EVENTS = [
    '**首次接触事件**', '**首次正确输入**', '首次成功', '**首次主动复用**',
    '**24 小时后留存**', '7 日后复用', '失败次数', '求助事件', '跳过事件',
    '教学阻断时长',
]

LEARNING_STUCK = [
    '连续失败', '停留超时', '返回菜单', '暂停', '重读提示', '反复重试',
]

LEARNING_RULE = [
    '🔴 **学习曲线不能靠问卷代替可回放行为数据**',
    '🔑 卡点定义为上述**稳定模式**，**而非单次失败**',
    '🔑 啊哈时刻可用"**新机制首次使旧障碍变得可解**"的因果事件标记 —— '
    '例如刚学会钩锁后第一次无需绕路；**不能只写"玩家感到惊喜"**',
]

FORGET_FIELDS = [
    '上次游玩时间', '上次停留机制', '再进入后第一次输入', '是否正确',
    '是否重新展示', '**是否缩短/扩展教学**',
]

SKIP_FIELDS = [
    '**跳过后的隐藏知识**', '是否给物品/技能', '是否阻断后续任务',
    '**是否能从菜单补看**', '**补看是否计入统计**',
]

SKIP_RULE = '🔑 **可跳过性不能只有布尔值**'

# 可解释性
EXPLAIN_FIELDS = [
    '**隐藏机制的揭示程度**（何时告诉玩家规则）',
    '**数值的可见性**（伤害数字 / 概率显示 / 是否可查）',
    '**"为什么失败"的解释**',
    '**模拟 vs 告知**（是模拟结果还是直接显示）',
]

# 🔴 故意不告诉玩家
OBSCURE_FIELDS = [
    '隐藏概率', '**延迟揭示**', '**误导演出**', '教学保留',
    '**bug-feature 历史**', '**必须保持一致的老 bug**',
]

OBSCURE_META = [
    '**保留它的原因**', '**哪些界面不得泄露**', '**是否提供高级调试模式**',
]

OBSCURE_RULE = [
    '🔑 新增 `intentional_obscurity` 字段，显式建模上述六类',
    '🔑 若重制决定改透明，则**明确新版本号与偏离许可**',
    '🔑 这与"**故意沉默必须显式写**"一致 —— '
    '**沉默是设计选择，不是取证遗漏**',
]

CONFLICTS = [
    '❌ 把关卡生成器当重复可玩性测量工具',
    '❌ **给第二周目偷偷加不可见数值**',
    '❌ 只统计资产数量判断疲劳',
    '❌ 只保存"选择了哪个部件"',
    '❌ 把运行时展示质量当成格式保证',
    '❌ 不照搬 VRM 特有字段',
    '❌ **Khronos 批准的 glTF 规范非 CC-BY/Apache** —— 复制需逐文件核许可',
    '❌ 把模组冲突模型套到所有内容',
    '❌ **用视觉提示自动代打**',
    '❌ **以玩家流失数据自动缩短教程**',
    '❌ **生成式 AI 自动解释伤害公式**',
    '❌ **把纯渲染 trace 当逻辑重放**',
    '❌ **把不可复现随机当"更像原版"**',
    '❌ **把旧存档外观按当前部件表重新解释**',
]

FIELDS = [
    ('item_id', '项编号'),
    ('domain', '域（runlayer / ngplus / honest / fatigue / slot / showcase / '
               'identity / ugc / intuition / learning / explain / obscure）'),
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


def cmd_runlayer(a):
    _hdr('🔴 随机十层')
    print('层: ' + ' · '.join(RUN_LAYERS))
    print('\n每层元信息: ' + ' · '.join(RUN_LAYER_META))
    print('\n规则:')
    for r in RUN_RULE:
        print(f'   {r}')
    return 0


def cmd_ngplus(a):
    _hdr('🔴 新游戏+（**跨周目契约**）')
    print('逐项: ' + ' · '.join(NGPLUS_ITEMS))
    print('\n保留方向: ' + ' · '.join(NGPLUS_DIRS))
    print('\n隐藏层（最易遗漏）: ' + ' · '.join(NGPLUS_HIDDEN))
    print('\n规则:')
    for r in NGPLUS_RULE:
        print(f'   {r}')
    return 0


def cmd_honest(a):
    _hdr('可见变化 vs 隐藏变化')
    print('可见: ' + ' · '.join(HONEST_VISIBLE))
    print('\n隐藏: ' + ' · '.join(HONEST_HIDDEN))
    print('\n规则:')
    for r in HONEST_RULE:
        print(f'   {r}')
    return 0


def cmd_fatigue(a):
    _hdr('疲劳（**来自确定性重复**）')
    print('指标: ' + ' · '.join(FATIGUE_METRICS))
    print('\n触发器: ' + ' · '.join(FATIGUE_TRIGGERS))
    print('\n反疲劳: ' + ' · '.join(FATIGUE_ANTI))
    print(f'\n   {FATIGUE_RULE}')
    return 0


def cmd_slot(a):
    _hdr('🔴 定制槽位与约束')
    print('部位: ' + ' · '.join(SLOT_ITEMS))
    print('\n字段: ' + ' · '.join(SLOT_FIELDS))
    print(f'\n   {SLOT_RULE}')
    return 0


def cmd_showcase(a):
    _hdr('🔴 展示场景（**系统状态**）')
    print('场景: ' + ' · '.join(SHOWCASE_SCENES))
    print('\n每场景字段: ' + ' · '.join(SHOWCASE_FIELDS))
    print(f'\n   {SHOWCASE_RULE}')
    return 0


def cmd_identity(a):
    _hdr('身份可见性')
    print('四类: ' + ' · '.join(IDENTITY_VIS))
    print('\n项目: ' + ' · '.join(IDENTITY_ITEMS))
    print('\n过滤顺序: ' + ' · '.join(IDENTITY_FILTER))
    print(f'\n   {IDENTITY_RULE}')
    return 0


def cmd_ugc(a):
    _hdr('🔴 UGC 兼容性（**早于分享**）')
    for f in UGC_FIELDS:
        print(f'   · {f}')
    print('\n规则:')
    for r in UGC_RULE:
        print(f'   {r}')
    return 0


def cmd_intuition(a):
    _hdr('交互直觉')
    for k, why in INTUITION_LEVELS:
        print(f'   {k:<12} {why}')
    print('\n字段: ' + ' · '.join(INTUITION_FIELDS))
    print('\n推不动: ' + ' · '.join(PUSH_FIELDS))
    print(f'\n   {PUSH_RULE}')
    print('\n交互状态机: ' + ' · '.join(INTERACT_STATE))
    print('\n规则:')
    for r in INTERACT_RULE:
        print(f'   {r}')
    return 0


def cmd_learning(a):
    _hdr('🔴 学习曲线（**可回放行为数据**）')
    print('事件: ' + ' · '.join(LEARNING_EVENTS))
    print('\n卡点: ' + ' · '.join(LEARNING_STUCK))
    print('\n规则:')
    for r in LEARNING_RULE:
        print(f'   {r}')
    print('\n遗忘: ' + ' · '.join(FORGET_FIELDS))
    print('\n跳过: ' + ' · '.join(SKIP_FIELDS))
    print(f'\n   {SKIP_RULE}')
    return 0


def cmd_explain(a):
    _hdr('系统可解释性')
    for f in EXPLAIN_FIELDS:
        print(f'   · {f}')
    return 0


def cmd_obscure(a):
    _hdr('🔴 故意不告诉玩家（**显式建模**）')
    for f in OBSCURE_FIELDS:
        print(f'   · {f}')
    print('\n元信息: ' + ' · '.join(OBSCURE_META))
    print('\n规则:')
    for r in OBSCURE_RULE:
        print(f'   {r}')
    return 0


def cmd_init(a):
    os.makedirs(os.path.dirname(a.init) or '.', exist_ok=True)
    with open(a.init, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow([k for k, _ in FIELDS])
        w.writerow(['TODO'] * len(FIELDS))
    print(f'已生成重复/表达表: {a.init}')
    print('\n⚠️ 十二域：runlayer / ngplus / honest / fatigue / slot / '
          'showcase / identity / ugc / intuition / learning / explain / '
          'obscure')
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
    print(f'重复/表达 · {len(rows)} 条')
    print('=' * 76)
    if mismatch:
        print(f'\n🚫 **不一致** {len(mismatch)} 条（行 {mismatch[:15]}）')
    if no_legacy:
        print(f'\n❌ {len(no_legacy)} 条缺**原版值**（行 {no_legacy[:15]}）')

    if not (mismatch or no_legacy):
        print('\n✅ 重复/表达：一致且原版值完整')

    print('\n🔑 **NG+ 是跨周目契约，不是难度标签。**')
    print('   **只保存"选了哪个部件"会在新增服装后改变旧存档外观。**')
    print('   **沉默是设计选择，不是取证遗漏。**')
    return 1 if (a.gate_check and (mismatch or no_legacy)) else 0


def main():
    ap = argparse.ArgumentParser(description='重复可玩与玩家表达')
    ap.add_argument('--runlayer', action='store_true')
    ap.add_argument('--ngplus', action='store_true')
    ap.add_argument('--honest', action='store_true')
    ap.add_argument('--fatigue', action='store_true')
    ap.add_argument('--slot', action='store_true')
    ap.add_argument('--showcase', action='store_true')
    ap.add_argument('--identity', action='store_true')
    ap.add_argument('--ugc', action='store_true')
    ap.add_argument('--intuition', action='store_true')
    ap.add_argument('--learning', action='store_true')
    ap.add_argument('--explain', action='store_true')
    ap.add_argument('--obscure', action='store_true')
    ap.add_argument('--init')
    ap.add_argument('--check')
    ap.add_argument('--gate-check', action='store_true')
    a = ap.parse_args()
    fns = {'runlayer': cmd_runlayer, 'ngplus': cmd_ngplus,
           'honest': cmd_honest, 'fatigue': cmd_fatigue, 'slot': cmd_slot,
           'showcase': cmd_showcase, 'identity': cmd_identity,
           'ugc': cmd_ugc, 'intuition': cmd_intuition,
           'learning': cmd_learning, 'explain': cmd_explain,
           'obscure': cmd_obscure}
    for k, fn in fns.items():
        if getattr(a, k):
            return fn(a)
    if a.init:
        return cmd_init(a)
    if a.check:
        return cmd_check(a)
    print('❌ 需要 --runlayer / --ngplus / --honest / --fatigue / --slot / '
          '--showcase / --identity / --ugc / --intuition / --learning / '
          '--explain / --obscure / --init / --check 之一')
    return 2


if __name__ == '__main__':
    sys.exit(main())
