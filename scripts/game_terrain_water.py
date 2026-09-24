#!/usr/bin/env python3
"""地形/植被/地表 + 水体/水下/浮力（第二十六轮 A / B 类）。

**🔑 A 类核心**：
> 🔑 **地形的每个采样参数都可能直接改变"能站哪里、能跳哪里、
> 敌人能否看到你"。**
> 🔑 **一个被忽略的 must-match 是"植被稳定性"，不是"植被数量"。**
> 🔴 新引擎常为了性能随机减实例、统一 billboard、按画质档缩放密度 ——
> 但这些改动会**移动潜行边界**。

**🔑 B 类核心**：
> 🔑 **水体是最典型的"视觉相似、状态不同"系统。**
> 🔴 **水下必须作为独立状态机，而不是摄像机加蓝雾** ——
> 否则玩家会"**看见水却在水上**"。

用法:
  game_terrain_water.py --terrain  # 🔴 高度图**采样与精度**
  game_terrain_water.py --breath   # 🔴 LOD **呼吸测试**
  game_terrain_water.py --blend    # 材质混合**权重**与地表语义是两份数据
  game_terrain_water.py --foliage  # 🔴 植被**渲染/碰撞/玩法三实例**
  game_terrain_water.py --stable   # 🔑 **植被稳定性**≠植被数量
  game_terrain_water.py --surface  # `surface_footprint` 十项
  game_terrain_water.py --water    # 🔴 水体**高度场+流场+状态表**
  game_terrain_water.py --under    # 🔴 **水下状态机**
  game_terrain_water.py --buoy     # 浮力与拖曳
  game_terrain_water.py --rain     # 雨/雪/积水
  game_terrain_water.py --init ledger/terrain_water.csv
  game_terrain_water.py --check ledger/terrain_water.csv --gate

退出码: 0 通过 / 1 缺项 / 2 用法错误
"""
import argparse
import csv
import os
import sys

# 🔴 地形采样与精度
TERRAIN_FIELDS = [
    '原始分辨率', '**原始值精度**（float16/float32/定点）', '单位',
    '坐标系', '垂直范围', '**行列方向**', '**是否有无损压缩**',
]

TERRAIN_RULE = [
    '🔑 **不能只写"高度图已导入"**',
    '🔑 分块大小 · **最大像素误差** · 合成贴图距离 · 光照方向'
    '**共同决定近处细节与远处表示** —— 不是四个无关设置',
    '🔑 迁移应做"**高度采样差分图**"：同一世界坐标在两引擎采样，'
    '统计**最大误差 · 均方根误差 · 误差超过角色半径/台阶阈值的位置数**，'
    '**并单独列出斜坡 · 洞沿 · 桥面 · 洞穴入口**',
    '🔴 **"看起来一样"若没有逐格误差阈值，不能结案**',
]

# 🔴 LOD 呼吸
BREATH_RULE = [
    '🔑 **LOD morph 必须从可见瑕疵测试反向定义验收**，'
    '而不是只比较关卡设计师视图',
    '🔑 **呼吸测试**：摄像机固定 20—30 分钟，'
    '以**亚像素边缘追踪**统计同一地形的**顶点位移和法线变化**',
    '🔑 LOD 边界两侧各生成一条样条，逐点记录**高度差 · 法线差 · '
    '纹理导数差**',
    '🔴 若原版采用**硬切换**而新引擎只有 morph → **就是偏离**；'
    '若原版用 morph 但边界永不动，也**不能因"没有 pop"就改成硬切**',
]

# 材质混合
BLEND_FIELDS = [
    '层数', '每层 albedo/normal/roughness/metallic/height 来源',
    '**splat/ID map 精度**', '单通道或打包格式', '**归一化与剩余权重处理**',
    '**锐度/对比度曲线**', '顶点与片元混合位置', 'triplanar 轴',
    '宏纹理/合成贴图距离', 'mip bias',
]

BLEND_RULE = '🔑 **权重即使只有 0.01，也可能决定雪、泥、沙'
'是否覆盖某一格脚步声**'

# 🔴 植被三实例
FOLIAGE_THREE = [
    ('**渲染实例**', '看到的那份'),
    ('**碰撞实例**', '挡住的那份'),
    ('**玩法实例**', '**潜行/视线/可交互的那份**'),
]

FOLIAGE_FIELDS = [
    '分布算法与随机种子',
    '高度 · 坡度 · 曲率 · 水深 · 法线 · 现有对象排斥规则',
    '**密度场分辨率**',
    '逐 instance 位置 · 旋转 · 缩放 · 阶段 · 簇 ID',
    'LOD 0—N',
    '**billboard 距离 · 角度 · 抖动 · 交叉淡化**',
    'GPU/CPU 表示',
    '弯曲半径 · 优先级 · 衰减 · **恢复时间**',
    '**可踩倒 · 可燃烧 · 可砍伐的实例数上限**',
    '静态/动态碰撞半径',
    '**AI 视野阻挡与音频遮挡**',
    '**画质档缩放**', '绘制距离', '阴影投射/接收',
]

FOLIAGE_SUCKER = '🔑 潜行草**并非任意视觉高度**，而是**独立标记为潜行或装饰**，'
'并给一个**稳定的持续高度** —— 避免"真实草高被下一根草破坏"'
'造成玩家**被看见/看不见的不连贯**'

# 🔑 植被稳定性
STABLE_RULE = [
    '🔑 **同一世界坐标 · 同一种子 · 同一画质档 · 同一摄像机位置'
    '必须产生逐实例位置与存活状态的一致性**',
    '🔑 不能一致时，必须另存一份 `**gameplay_foliage**` '
    '**确定性实例表**',
    '🔑 若原版使用 GPU 剔除、流式预算或异步加载，'
    '实际存活实例**可能本来就非确定性** —— '
    '应记录版本与复现窗口，'
    '🔴 **不能把新引擎的"更整齐"包装成修复**',
]

# 地表
SURFACE_TEN = [
    '摩擦系数', '阻力', '**痕迹残留时间**', '足迹深度', '**声音材质**',
    '可燃烧', '可冻结', '是否允许滑行', '摄像机晃动', '**角色速度倍率**',
    '坡度容差',
]

SURFACE_RULE = '🔑 **原版没有显式表面系统并不等于没有规则**；'
'反编译找不到表时要用多组受控测试得到"**零阶记录**"，'
'**再把猜测明确降级为推测**'

# 🔴 水体
WATER_HEIGHT = [
    '网格尺寸', '采样频率', '**频谱/FFT 或 Gerstner 参数**', '**风力曲线**',
    '风向', '波高', '波向谱', '**相位 seed**', '法线精度', '焦散距离',
]

WATER_FLOW = [
    '逐格流向', '流速', '涡度', '深度', '障碍物',
    '**船/玩家可漂流区**',
]

WATER_SURFACE = [
    '岸线 foam', '**白浪阈值**', '划水/尾迹半径', '**涟漪传播与衰减**',
    '物体交互范围',
]

WATER_WINDOW = '🔑 水体也需要"**瞬态窗口**"和"**稳态窗口**"：'
'用 **0.5 秒 · 5 秒 · 60 秒** 测量**浮力位置漂移 · 阻尼误差 · 相位漂移**，'
'🔴 **避免单次截图通过**'

# 🔴 水下状态机
UNDER_FIELDS = [
    '**空气/水切换高度与滞后**', '**镜头位置**（角色眼位或偏移）',
    '近裁面', 'FOV', '色散', '雾颜色/距离', '指数', '焦平面', '体积光',
    '表面焦散', '水面外物体折射', '镜面反射', '**低通截止/共振**',
    '音量', '混响', '声音遮挡', '拖曳', '下潜输入曲线',
    '上浮/下潜速度', '冲量衰减', '**氧气/呼吸规则**', 'HUD 与水滴',
    '失重/重力缩放', '粒子气泡生命周期', '水下语音表现',
]

UNDER_RULE = [
    '🔴 **水下必须作为独立状态机，而不是摄像机加蓝雾**',
    '🔑 若原版在**第一人称和第三人称使用不同相机偏移或不同水面法线**，'
    '**必须分别录制** —— 否则玩家会"**看见水却在水上**"',
]

# 浮力
BUOY_FIELDS = [
    '浮力位置漂移', '阻尼误差', '相位漂移', '物体在水中的阻尼',
    '载具/木筏', '**河流方向是否影响可漂流物/投掷物/玩家被冲走**',
]

# 雨雪
RAIN_ITEMS = [
    '是否影响**能见度**', '**声音**', '**摩擦**', '**痕迹**',
    '雨滴粒子与镜头挂水', '积雪是否改变地形高度与移动',
]

CONFLICTS = [
    '❌ 只写"高度图已导入"',
    '❌ **"看起来一样"但没有逐格误差阈值**',
    '❌ 原版硬切换而新引擎只有 morph（或反之）',
    '❌ 为性能**随机减植被实例 / 统一 billboard / 按档缩放密度**',
    '❌ **把新引擎"更整齐"的植被包装成修复**',
    '❌ 植被只记"数量"不记"稳定性"',
    '❌ **水下做成摄像机加蓝雾**',
    '❌ 第一/第三人称水面相机偏移不分别录制',
    '❌ **单次截图通过水体验收**',
    '❌ 材质混合权重只记层数',
    '❌ 原版无显式表面系统就推断"没有规则"',
]

FIELDS = [
    ('item_id', '项编号'),
    ('domain', '域（terrain / breath / blend / foliage / stable / '
               'surface / water / under / buoy / rain）'),
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


def cmd_terrain(a):
    _hdr('🔴 地形（**采样与精度**）')
    print('字段: ' + ' · '.join(TERRAIN_FIELDS))
    print('\n规则:')
    for r in TERRAIN_RULE:
        print(f'   {r}')
    return 0


def cmd_breath(a):
    _hdr('🔴 LOD（**呼吸测试**）')
    for r in BREATH_RULE:
        print(f'   {r}')
    return 0


def cmd_blend(a):
    _hdr('材质混合（**权重 ≠ 地表语义**）')
    print('混合字段: ' + ' · '.join(BLEND_FIELDS))
    print(f'\n   {BLEND_RULE}')
    print('\n地表 `surface_footprint`: ' + ' · '.join(SURFACE_TEN))
    print(f'\n   {SURFACE_RULE}')
    return 0


def cmd_foliage(a):
    _hdr('🔴 植被（**渲染/碰撞/玩法三实例**）')
    for k, why in FOLIAGE_THREE:
        print(f'   {k:<14} {why}')
    print('\n字段:')
    for f in FOLIAGE_FIELDS:
        print(f'   · {f}')
    print(f'\n   {FOLIAGE_SUCKER}')
    return 0


def cmd_stable(a):
    _hdr('🔑 植被稳定性（**≠ 植被数量**）')
    for r in STABLE_RULE:
        print(f'   {r}')
    return 0


def cmd_surface(a):
    _hdr('地表 `surface_footprint`')
    for s in SURFACE_TEN:
        print(f'   · {s}')
    print(f'\n   {SURFACE_RULE}')
    return 0


def cmd_water(a):
    _hdr('🔴 水体（**高度场+流场+状态表**）')
    print('高度场: ' + ' · '.join(WATER_HEIGHT))
    print('\n流场:   ' + ' · '.join(WATER_FLOW))
    print('\n表面:   ' + ' · '.join(WATER_SURFACE))
    print(f'\n   {WATER_WINDOW}')
    return 0


def cmd_under(a):
    _hdr('🔴 水下（**独立状态机**）')
    print('字段: ' + ' · '.join(UNDER_FIELDS))
    print('\n规则:')
    for r in UNDER_RULE:
        print(f'   {r}')
    return 0


def cmd_buoy(a):
    _hdr('浮力与拖曳')
    for b in BUOY_FIELDS:
        print(f'   · {b}')
    print(f'\n   {WATER_WINDOW}')
    return 0


def cmd_rain(a):
    _hdr('雨 / 雪 / 积水')
    for r in RAIN_ITEMS:
        print(f'   · {r}')
    return 0


def cmd_init(a):
    os.makedirs(os.path.dirname(a.init) or '.', exist_ok=True)
    with open(a.init, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow([k for k, _ in FIELDS])
        w.writerow(['TODO'] * len(FIELDS))
    print(f'已生成地形/水体表: {a.init}')
    print('\n⚠️ 十域：terrain / breath / blend / foliage / stable / '
          'surface / water / under / buoy / rain')
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
    print(f'地形/水体 · {len(rows)} 条')
    print('=' * 76)
    if mismatch:
        print(f'\n🚫 **不一致** {len(mismatch)} 条（行 {mismatch[:15]}）')
    if no_legacy:
        print(f'\n❌ {len(no_legacy)} 条缺**原版值**（行 {no_legacy[:15]}）')
    if no_grade:
        print(f'\n🚫 {len(no_grade)} 条**证据等级缺失或 ≥7 级**'
              f'（行 {no_grade[:15]}）')

    if not (mismatch or no_legacy or no_grade):
        print('\n✅ 地形/水体：一致、原版值完整、证据等级达标')

    print('\n🔑 **植被 must-match 是"稳定性"，不是"数量"。**')
    print('   **水下是独立状态机；单次截图通过水体验收不成立。**')
    print('   **每个地形采样参数都可能改变"能站哪里、敌人能否看到你"。**')
    return 1 if (a.gate_check and (mismatch or no_legacy or no_grade)) else 0


def main():
    ap = argparse.ArgumentParser(description='地形植被与水体')
    ap.add_argument('--terrain', action='store_true')
    ap.add_argument('--breath', action='store_true')
    ap.add_argument('--blend', action='store_true')
    ap.add_argument('--foliage', action='store_true')
    ap.add_argument('--stable', action='store_true')
    ap.add_argument('--surface', action='store_true')
    ap.add_argument('--water', action='store_true')
    ap.add_argument('--under', action='store_true')
    ap.add_argument('--buoy', action='store_true')
    ap.add_argument('--rain', action='store_true')
    ap.add_argument('--init')
    ap.add_argument('--check')
    ap.add_argument('--gate-check', action='store_true')
    a = ap.parse_args()
    fns = {'terrain': cmd_terrain, 'breath': cmd_breath, 'blend': cmd_blend,
           'foliage': cmd_foliage, 'stable': cmd_stable,
           'surface': cmd_surface, 'water': cmd_water, 'under': cmd_under,
           'buoy': cmd_buoy, 'rain': cmd_rain}
    for k, fn in fns.items():
        if getattr(a, k):
            return fn(a)
    if a.init:
        return cmd_init(a)
    if a.check:
        return cmd_check(a)
    print('❌ 需要 --terrain / --breath / --blend / --foliage / --stable / '
          '--surface / --water / --under / --buoy / --rain / --init / '
          '--check 之一')
    return 2


if __name__ == '__main__':
    sys.exit(main())
