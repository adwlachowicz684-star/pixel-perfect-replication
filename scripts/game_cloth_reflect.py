#!/usr/bin/env python3
"""布料/毛发/次级动画 + 反射/透明 + 陀螺仪VR + 粒子确定性 + 响度 + 着色器预热
（第二十六轮 C / D / E / F / G / H 类）。

**🔑 C 类核心**：
> 🔑 **布料要按模拟拓扑取证，而不是按"衣服"命名。**
> 🔴 **布料穿模不是单纯美术瑕疵** —— 是固定点、碰撞体版本、解算顺序、
> 角色缩放、根运动与 Teleport **共同作用的结果**。

**🔑 D 类核心**：
> 🔑 **反射不是画质候选，而是可见性与镜头语义。**
> 🔴 **原版镜子若能看到身后敌人，新方案即使"更真实但无屏幕外内容"，
> 也是玩法偏离。**

用法:
  game_cloth_reflect.py --cloth   # 🔴 布料**三种拓扑**
  game_cloth_reflect.py --clothgp # 🔴 布料**玩法事实字段**
  game_cloth_reflect.py --hair    # 毛发**四种模型**
  game_cloth_reflect.py --second  # 次级动画（**不是布料**）
  game_cloth_reflect.py --reflect # 🔴 反射**按可见范围/延迟/轴映射**验收
  game_cloth_reflect.py --trans   # 透明**六个必须锁定字段**
  game_cloth_reflect.py --mirror  # 🔴 镜中"**玩家存在感**"
  game_cloth_reflect.py --gyro    # 陀螺仪**输入/映射/状态机**
  game_cloth_reflect.py --xr      # 🔴 **comfort_profile** 不从 OpenXR 抄
  game_cloth_reflect.py --vfx     # 🔴 粒子**同 seed 同结果不是天然属性**
  game_cloth_reflect.py --loud    # 🔴 响度**四把表**
  game_cloth_reflect.py --warm    # 🔴 **异步编译可接受**是最危险冲突
  game_cloth_reflect.py --init ledger/cloth_reflect.csv
  game_cloth_reflect.py --check ledger/cloth_reflect.csv --gate

退出码: 0 通过 / 1 缺项 / 2 用法错误
"""
import argparse
import csv
import os
import sys

# 🔴 布料三种拓扑
CLOTH_TOPO = [
    ('**顶点模拟**', '逐顶点解算'),
    ('**骨骼弹簧**', '骨骼驱动弹簧'),
    ('**代理体**', '简化代理碰撞'),
]

CLOTH_FIELDS = [
    '解算器', '子步', '迭代次数', '约束类型',
    '拉伸/弯曲/剪切刚度', '阻尼', '质量', '重力缩放',
    '风场方向/速度/湍流', '**碰撞厚度**', '碰撞层', '**固定点**',
    '自碰撞', '双面对撞', '与骨骼绑定的优先级', '**LOD 停算距离**',
    '睡眠阈值', '**Teleport 重置**', '**延迟一帧原因**',
]

CLOTH_PEN = '🔑 **布料穿模不是单纯美术瑕疵** —— '
'是**固定点 · 碰撞体版本 · 解算顺序 · 角色缩放 · 动画根运动 · Teleport**'
'共同作用的结果，**必须有稳定重放**'

CLOTH_TRAJ = [
    '10 秒静止恢复', '急停', '180 度转身', '攀爬', '下蹲', '换装',
    '镜头穿越', 'Teleport',
]

# 🔴 布料玩法事实字段
CLOTH_GP = [
    '**affects_hitbox**', '**blocks_aim**', '**blocks_vision**',
    '**can_be_grabbed**', 'can_cover', 'can_be_cut', 'casts_shadow',
    'receives_shadow', 'depth_write',
]

CLOTH_GP_RULE = [
    '🔑 **布料是否进入玩法事实，必须在资产导入阶段显式声明**',
    '🔴 若原版披风**遮挡瞄准**或**能被伙伴抓住**，新引擎改成穿透**即是 bug**',
    '🔴 若原版明确**不遮挡**，也**不能"为了更好看"加碰撞**',
]

# 毛发四模型
HAIR_FOUR = [
    '**动态发丝/guid**', '**卡片**', '**壳层/鳍**', '**骨骼弹簧**',
]

HAIR_FIELDS = [
    '数量', '宽度', '透明度', '各向异性高光', '风', '头部位移',
    '碰撞体', '**与帽子/头盔/披风穿透优先级**', '**帽子吸附策略**',
    '动画缓存', 'LOD 降级', '深度排序', '阴影',
]

# 次级动画
SECOND_RULE = '🔑 **马尾与飘带应归入次级动画，而不是布料**'
SECOND_FIELDS = [
    '弹簧刚度', '阻尼', '重力', '骨骼父子链', '**最大偏转**',
    '**恢复曲线**', '动画层级', '**暂停处理**',
]

# 🔴 反射
REFLECT_FOUR = [
    ('**平面反射**', '对平面精确但代价高'),
    ('**SSR/SSPR**', '**只能反射屏幕空间内信息，屏幕外物体缺失**'),
    ('**反射探针/Cubemap**', '近似全局'),
    ('**光线追踪**', '覆盖更广但成本不同'),
]

REFLECT_FIELDS = [
    '启用条件', '分辨率', '**更新频率**（每帧/低频/静态）', '层数',
    '粗糙度模糊', '视口偏移', '深度裁剪', '天空与粒子可见性',
    '**音频反射是否共享**', '动态光源数',
]

REFLECT_RULE = '🔴 **原版镜子若能看到身后敌人，'
'新方案即使"更真实但无屏幕外内容"，也是玩法偏离**'

# 透明六字段
TRANS_SIX = [
    '**排序组与稳定排序键**', '**双 pass 的用途**', '**是否写深度**',
    '**是否测试深度**', '**是否投射阴影**', '**是否接收阴影**',
]

TRANS_MORE = [
    '厚度', '折射索引近似', '焦平面', '背面法线翻转',
    'Alpha-to-coverage', 'dither 与 MSAA 交互',
]

TRANS_RULE = '🔑 玻璃 · 水面 · 粒子 · 全息 UI · 角色披风'
'**可能使用不同策略**；🔴 **若把全部透明统一成 OIT/alpha 混合**，'
'可能修复某些穿帮，也**可能破坏原版稳定的前后关系**'

# 🔴 镜中玩家存在感
MIRROR_ITEMS = [
    '第一人称**是否显示头部/手/武器**', '模型是否简化',
    '**左右手镜像是否与原版一致**', '**镜中动画是否落后一帧**',
    '**菜单/截图/拍照模式是否进入反射**', '镜子是否渲染粒子或仅静态场景',
    '多次反射', '破碎镜', '**水洼与镜面是否共用同一管线**',
]

# 陀螺仪
GYRO_FIELDS = [
    '轴映射', '参考系', '**绝对/相对模式**', '**摇杆叠加**',
    '灵敏度曲线', '死区', '指数/线性', '翻转', '漂移补偿',
    '**暂停时是否冻结**', '每帧采样', '帧间插值', '相机时间偏移',
    '输入预测', '与 FOV/ADS 倍率关系', '轮询率', '热插拔', '校准恢复',
]

MOTION_FIELDS = [
    '方向向量', '阈值', '持续时间', '速度/加速度峰值', '手臂长度',
    '玩家朝向权重', '**误触去抖与取消窗口**',
]

GYRO_RULE = '🔑 若原版玩家依赖某一摇杆叠加方式，'
'**仅"手感相近"不足以结案**'

# 🔴 VR comfort
XR_COMFORT = [
    '参考空间', 'locomotion 类型', '**snap 角度**',
    '**暗角启用条件与曲线**', 'FOV', 'IPD', '**世界缩放**',
    '地面高度', '座椅高度', '延迟补偿', '闪屏/频闪上限',
]

XR_RULE = [
    '🔑 **OpenXR 是 API/参考空间标准，不是一套舒适参数**',
    '🔑 它能统一**设备枚举 · 动作路径 · 空间定位 · 输入源语义**，'
    '但**不规定 snap turn 度数 · 暗角强度 · IPD · 坐姿/站姿人体工学 · '
    '晕动阈值**',
    '🔑 中国成年人 IPD P50 约 **56mm（男）/54mm（女）**，'
    '建议显示 IPD 与用户实际偏差控制在 **±5%** 以内 —— '
    '但这是**健康技术草案，不是游戏平台合规要求**',
    '🔴 **具体数值必须从原版测量，不跨平台照抄**',
]

XR_UI = [
    '世界空间/头锁/腕部 UI', '**每度角像素密度**', '最小可读距离',
    '视差', '双目融合', '注视点', '语言 BiDi', '数字长度变化',
    'HUD 抖动', '菜单深度', '近裁与穿头', '控制器激光', '手部遮挡',
    '字重与描边',
]

XR_UI_NOTE = '🔑 若原版让玩家**在镜子中仍可操作 UI**，'
'也要记录**镜像文本与交互规则**'

# 🔴 粒子确定性
VFX_SEED_FIELDS = [
    'seed', '时间步', '子步', '**迭代顺序**', '**发射顺序**', '剔除',
    'LOD', '随机数生成器', '**平台/驱动/编译器版本**', '排序策略',
]

VFX_RULE = [
    '🔴 **"同 seed 同结果"不是 GPU 粒子的天然属性** —— '
    '**浮点加法非结合**，GPU 并行归约若改变求和顺序就可能改变结果',
    '🔑 CPU 粒子更可能提供稳定顺序，GPU 粒子更可能受**线程调度/'
    '非确定归约**影响',
    '🔴 **迁移不能只测"相同 seed 看起来一样"**',
]

VFX_GP = [
    '**gameplay_role**', '**authoritative_source**', 'visible_to_teams',
    'must_display_before_effect', '**pause_mode**', '**time_scale_mode**',
    'rewind_mode', 'rollback_mode', 'prediction_mode', 'deterministic_seed',
]

VFX_GP_RULE = '🔑 暂停时可能 **freeze / fade / continue**；'
'慢动作时可能按 **scaled delta / real delta / 固定子步**；'
'回放可能**重放 / 重新模拟 / 截断** —— 不同选择**直接改变'
'"预警是否已显示"**'

VFX_BUDGET = [
    'max_emitters', 'max_particles', 'max_overdraw', 'max_fillrate',
    'max_depth_writes', 'max_shadow_casters', 'platform_tiers',
    'distance_cull', 'lod_switch', 'collision_budget', 'lighting_budget',
    'translucency_sorting_budget',
]

VFX_BUDGET_RULE = '🔑 补"**预算耗尽时是否降低玩法可见性**" —— '
'🔴 若**预警 VFX 被画质档降低并变得不可见**而原版始终可见，'
'**即 must-match 失败**'

# 🔴 响度四把表
LOUD_FOUR = [
    ('**Momentary**', '**0.4 秒**窗口'),
    ('**Short-term**', '**3 秒**窗口'),
    ('**Integrated**', 'ITU-R BS.1770 **门控**'),
    ('**LRA**', 'Integrated 重置时重置'),
]

LOUD_RULE = [
    '🔑 EBU Mode 仪表默认 **EBU+9 刻度**，目标 **−23.0 LUFS**',
    '🔑 **真峰值须满足相应容差**',
    '🔑 ITU-R BS.1770 当前在册 **BS.1770-5（2023-11）**',
    '🔴 **不能只录一个"平均音量"**；'
    '🔴 **EBU 的 target 不是游戏发布响度目标** —— '
    '应先建**不可变的测量基线与版本化算法**',
]

LOUD_BUS = ['SFX', 'Music', 'Voice', 'UI', '**父子关系**', '**旁链**']
LOUD_MORE = ['动态范围压缩/限幅设置', '平台响度差异（主机/PC/移动/电视/耳机）',
             '**玩家的音量分项是否与总线对应**']

# 🔴 着色器预热
WARM_FIELDS = [
    'Shader/Shader Variant Collection', 'PSO', 'Render Pipeline State',
    'render pass 兼容信息', '顶点布局', 'render target 格式', 'MSAA',
    '深度格式', '关键字', 'pass 顺序', '资源绑定布局', '图形 API',
    '**驱动/OS/GPU/引擎版本**',
]

WARM_FAIL = [
    '未收录', '未编译', '编译失败', '链接失败', 'PSO 创建失败', '超时',
    '内存不足', '**回退材质**',
]

WARM_RULE = [
    '🔑 **预热范围必须来自真实运行时命中**',
    '🔑 失败必须分类，每类定义**加载期阻塞 · 首次遭遇延迟 · 错误材质 · '
    '黑屏 · 崩溃 · silent fallback**',
    '🔴 **"异步编译可接受"是最危险的理念冲突** —— '
    '允许先渲染错误/占位材质，会把**第一次遭遇变成状态漂移**',
    '🔑 若原版直接卡顿也不接受，则新引擎**不能把 placeholder '
    '静默包装成体验升级**',
    '🔑 应分别测**首启 · 关卡加载 · 首次技能 · 新区域 · 画质切换 · '
    '慢动作 · 回放/观战 · 热重载**，输出 **P50/P95/P99 与最大卡顿**',
    '🔑 **预热状态必须进入场景加载事务，不能加载 100% 即宣称完成**',
]

CONFLICTS = [
    '❌ 按"衣服"命名布料而非按模拟拓扑',
    '❌ 原版披风遮挡瞄准而新引擎改穿透',
    '❌ 原版明确不遮挡却"为了更好看"加碰撞',
    '❌ 把布料穿模当纯美术瑕疵',
    '❌ 马尾/飘带归入布料而非次级动画',
    '❌ **把反射当画质候选**',
    '❌ 镜中看不到身后敌人（原版能看到）',
    '❌ **把全部透明统一成 OIT/alpha 混合**',
    '❌ 从单一供应商抄 snap turn 度数或固定 IPD 列表',
    '❌ 跨平台照抄舒适参数',
    '❌ **只测"相同 seed 看起来一样"**',
    '❌ 预警 VFX 被画质档降至不可见',
    '❌ **只录一个"平均音量"**',
    '❌ 把 EBU target 当游戏母带目标',
    '❌ **"异步编译可接受"**',
    '❌ 加载 100% 即宣称预热完成',
]

FIELDS = [
    ('item_id', '项编号'),
    ('domain', '域（cloth / clothgp / hair / second / reflect / trans / '
               'mirror / gyro / xr / vfx / loud / warm）'),
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


def cmd_cloth(a):
    _hdr('🔴 布料（**三种拓扑**）')
    for k, why in CLOTH_TOPO:
        print(f'   {k:<14} {why}')
    print('\n字段: ' + ' · '.join(CLOTH_FIELDS))
    print(f'\n   {CLOTH_PEN}')
    print('\n八段受控轨迹: ' + ' · '.join(CLOTH_TRAJ))
    return 0


def cmd_clothgp(a):
    _hdr('🔴 布料（**玩法事实字段**）')
    for f in CLOTH_GP:
        print(f'   · {f}')
    print('\n规则:')
    for r in CLOTH_GP_RULE:
        print(f'   {r}')
    return 0


def cmd_hair(a):
    _hdr('毛发（**四种模型**）')
    for h in HAIR_FOUR:
        print(f'   · {h}')
    print('\n字段: ' + ' · '.join(HAIR_FIELDS))
    return 0


def cmd_second(a):
    _hdr('次级动画（**不是布料**）')
    print(f'   {SECOND_RULE}')
    print('\n字段: ' + ' · '.join(SECOND_FIELDS))
    return 0


def cmd_reflect(a):
    _hdr('🔴 反射（**四种方案**）')
    for k, why in REFLECT_FOUR:
        print(f'   {k:<22} {why}')
    print('\n字段: ' + ' · '.join(REFLECT_FIELDS))
    print(f'\n   {REFLECT_RULE}')
    print('   🔑 矩阵：**可见对象清单 × 反射方案 × 距离/角度 × 画质档**')
    return 0


def cmd_trans(a):
    _hdr('透明（**六个必须锁定字段**）')
    for t in TRANS_SIX:
        print(f'   · {t}')
    print('\n另需: ' + ' · '.join(TRANS_MORE))
    print(f'\n   {TRANS_RULE}')
    return 0


def cmd_mirror(a):
    _hdr('🔴 镜中（**玩家存在感**）')
    for m in MIRROR_ITEMS:
        print(f'   · {m}')
    return 0


def cmd_gyro(a):
    _hdr('陀螺仪 / 体感')
    print('陀螺仪瞄准: ' + ' · '.join(GYRO_FIELDS))
    print('\n体感挥动:   ' + ' · '.join(MOTION_FIELDS))
    print(f'\n   {GYRO_RULE}')
    return 0


def cmd_xr(a):
    _hdr('🔴 VR comfort_profile（**不从 OpenXR 抄**）')
    print('字段: ' + ' · '.join(XR_COMFORT))
    print('\n规则:')
    for r in XR_RULE:
        print(f'   {r}')
    print('\nVR UI: ' + ' · '.join(XR_UI))
    print(f'\n   {XR_UI_NOTE}')
    return 0


def cmd_vfx(a):
    _hdr('🔴 粒子（**同 seed 同结果不是天然属性**）')
    print('确定性字段: ' + ' · '.join(VFX_SEED_FIELDS))
    print('\n规则:')
    for r in VFX_RULE:
        print(f'   {r}')
    print('\n玩法化 VFX 字段: ' + ' · '.join(VFX_GP))
    print(f'\n   {VFX_GP_RULE}')
    print('\n预算: ' + ' · '.join(VFX_BUDGET))
    print(f'\n   {VFX_BUDGET_RULE}')
    return 0


def cmd_loud(a):
    _hdr('🔴 响度（**四把表**）')
    for k, why in LOUD_FOUR:
        print(f'   {k:<16} {why}')
    print('\n规则:')
    for r in LOUD_RULE:
        print(f'   {r}')
    print('\n总线: ' + ' · '.join(LOUD_BUS))
    print('\n另需: ' + ' · '.join(LOUD_MORE))
    return 0


def cmd_warm(a):
    _hdr('🔴 着色器预热（**首遇编译契约**）')
    print('预热范围: ' + ' · '.join(WARM_FIELDS))
    print('\n失败分类: ' + ' · '.join(WARM_FAIL))
    print('\n规则:')
    for r in WARM_RULE:
        print(f'   {r}')
    return 0


def cmd_init(a):
    os.makedirs(os.path.dirname(a.init) or '.', exist_ok=True)
    with open(a.init, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow([k for k, _ in FIELDS])
        w.writerow(['TODO'] * len(FIELDS))
    print(f'已生成布料/反射表: {a.init}')
    print('\n⚠️ 十二域：cloth / clothgp / hair / second / reflect / trans / '
          'mirror / gyro / xr / vfx / loud / warm')
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
    print(f'布料/反射 · {len(rows)} 条')
    print('=' * 76)
    if mismatch:
        print(f'\n🚫 **不一致** {len(mismatch)} 条（行 {mismatch[:15]}）')
    if no_legacy:
        print(f'\n❌ {len(no_legacy)} 条缺**原版值**（行 {no_legacy[:15]}）')
    if no_grade:
        print(f'\n🚫 {len(no_grade)} 条**证据等级缺失或 ≥7 级**'
              f'（行 {no_grade[:15]}）')

    if not (mismatch or no_legacy or no_grade):
        print('\n✅ 布料/反射：一致、原版值完整、证据等级达标')

    print('\n🔑 **反射是可见性语义，不是画质候选；镜中看不到身后敌人 = 偏离。**')
    print('   **"同 seed 同结果"不是 GPU 粒子天然属性（浮点非结合）。**')
    print('   **"异步编译可接受"是最危险的冲突；加载 100% ≠ 预热完成。**')
    return 1 if (a.gate_check and (mismatch or no_legacy or no_grade)) else 0


def main():
    ap = argparse.ArgumentParser(description='布料反射与渲染契约')
    ap.add_argument('--cloth', action='store_true')
    ap.add_argument('--clothgp', action='store_true')
    ap.add_argument('--hair', action='store_true')
    ap.add_argument('--second', action='store_true')
    ap.add_argument('--reflect', action='store_true')
    ap.add_argument('--trans', action='store_true')
    ap.add_argument('--mirror', action='store_true')
    ap.add_argument('--gyro', action='store_true')
    ap.add_argument('--xr', action='store_true')
    ap.add_argument('--vfx', action='store_true')
    ap.add_argument('--loud', action='store_true')
    ap.add_argument('--warm', action='store_true')
    ap.add_argument('--init')
    ap.add_argument('--check')
    ap.add_argument('--gate-check', action='store_true')
    a = ap.parse_args()
    fns = {'cloth': cmd_cloth, 'clothgp': cmd_clothgp, 'hair': cmd_hair,
           'second': cmd_second, 'reflect': cmd_reflect, 'trans': cmd_trans,
           'mirror': cmd_mirror, 'gyro': cmd_gyro, 'xr': cmd_xr,
           'vfx': cmd_vfx, 'loud': cmd_loud, 'warm': cmd_warm}
    for k, fn in fns.items():
        if getattr(a, k):
            return fn(a)
    if a.init:
        return cmd_init(a)
    if a.check:
        return cmd_check(a)
    print('❌ 需要 --cloth / --clothgp / --hair / --second / --reflect / '
          '--trans / --mirror / --gyro / --xr / --vfx / --loud / --warm / '
          '--init / --check 之一')
    return 2


if __name__ == '__main__':
    sys.exit(main())
