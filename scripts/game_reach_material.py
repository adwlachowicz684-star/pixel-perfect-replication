#!/usr/bin/env python3
"""关卡可通行性 + 材质等价 + 音效覆盖 + 相机漂移 + 现实时钟
（第二十八轮 C / D / E / F / G 类）。

**🔑 C 类核心**：
> 🔑 **可达性验证不能被新导航网格替代。**
> 🔴 新 A* 可能把原版合法 trick **判为不可达**，
> 也可能把原版**无法到达**的区域判为可达。

**🔑 D 类核心**：
> 🔑 **跨引擎等价的对象不是贴图文件，而是可复现的 BRDF 样本。**
> 🔑 **MaterialX / OpenPBR 是中间表示，不是自动双向转换器** ——
> 也**不能证明底层 BRDF 相同**。

**🔑 E 类核心**：
> 🔑 **音频盲点是"事件存在但声音不存在"。**
> 🔴 **默认不允许"找不到文件就什么都不播"** —— 静默回退要触发审计告警。

用法:
  game_reach_material.py --reach    # 🔴 可达性**两阶段**
  game_reach_material.py --cap      # 跳跃/攀爬/游泳**逐参数**
  game_reach_material.py --trick    # 捷径**允许/禁止清单**与证据八级
  game_reach_material.py --stuck    # 卡点**可判定输出**
  game_reach_material.py --brdf     # 🔴 **BRDF 样本**测量
  game_reach_material.py --workflow # 工作流转换**损失映射**
  game_reach_material.py --tonemap  # 色调映射是**可测试函数**
  game_reach_material.py --layer    # 等价判据**四层**
  game_reach_material.py --audio    # 🔴 音效**事件覆盖审计**
  game_reach_material.py --voice    # 同帧重复是**事件语义**
  game_reach_material.py --camera   # 相机**坐标稳定性**
  game_reach_material.py --clock    # 🔴 现实时钟**分层**
  game_reach_material.py --init ledger/reach_material.csv
  game_reach_material.py --check ledger/reach_material.csv --gate

退出码: 0 通过 / 1 缺项 / 2 用法错误
"""
import argparse
import csv
import os
import sys

# 🔴 可达性两阶段
REACH_TWO = [
    ('**运动学轨迹重放**', '以原版录制的按键/摇杆/物理状态序列驱动新角色，'
     '**在同样初始位姿逐帧比较位置和速度**'),
    ('**覆盖率导向探索**', '用原版碰撞/触发器采样点、已访问网格、'
     '**跳跃落点和边界样本**作为覆盖目标'),
]

REACH_FIELDS = [
    'run_id', 'origin_version', 'input_capture_hash', 'start_transform',
    'start_velocity', 'end_transform', 'end_velocity', 'max_error_cm',
    'frame_count', 'command_rate_hz', '**first_failure_frame**',
    '**failure_kind**',
]

REACH_FAIL = [
    'unreachable', 'wrong_landing', 'clipped_geometry',
    '**fell_out_of_world**', 'blocked_by_actor', 'blocked_by_door',
    'stuck', 'input_diverged', 'animation_diverged', 'physics_diverged',
]

REACH_RULE = [
    '🔑 若原版用**运动叠代 · 错位碰撞 · 动画根位移 · 脚本推力 · 平台 · '
    '传送 · 布娃娃 · 边界缝隙**，新 A* 可能判错',
    '🔑 **原版实际走过的轨迹存为权威**，Recast 路径用于'
    '"发现没有采样到的缺口"，**最后由运动学回放裁决**',
]

# 能力参数
CAP_FIELDS = [
    '水平初速', '重力', '最大水平速度', '**空气控制比例**', '起跳帧',
    '**可取消窗口**', '贴墙窗口', '最小/最大可抓边高度', '抓边吸附框',
    '抬升速度', '**抬升是否穿墙**', '水中重力', '浮力', '阻力',
    '游泳深度', '出水阈值', '滑行', '边缘自动攀爬', '连续跳限制',
]

CAP_MEASURE = [
    '固定角色朝向', '固定初始速度', '固定地面摩擦', '固定计时起点',
    '执行同一序列', '统计**最大水平位移 · 最大垂直位移 · '
    '最小可通过缝宽 · 起跳至离地帧数 · 落点标准差**',
]

CAP_RULE = '🔑 每个参数同时有 `original_value · measurement_method · '
'sample_count · confidence · new_value · allowed_deviation`；'
'🔴 **不确定值不得填零或引擎默认值**'

# 捷径技巧
TRICK_LEVELS = [
    ('**E1**', '源码'), ('**E2**', '内部断言/日志'), ('**E3**', '内存/网络包'),
    ('**E4**', '高精度逐帧录屏'), ('**E5**', '仪器化复测'),
    ('**E6**', '社区重复复测'), ('**E7**', '推测'), ('**E8**', '未证实'),
]

TRICK_RULE = [
    '🔑 原版能跳上的箱子 · 能抓的边缘 · 能挤过的门缝 · 能利用的碰撞角 · '
    '能滑过的平台间隙，都应按 `trick_id` 记录**证据级别 · 帧区间 · '
    '输入序列 · 版本范围 · 设备**',
    '🔑 **只证明新引擎能复现并不够，还要证明原版确实允许**',
]

# 卡点
STUCK_ITEMS = [
    '速度低于阈值', '位置抖动', '卡在碰撞体', '**被两个 actor 夹住**',
    '连续尝试同一路径', '掉出世界', '与摄像机/触发器边界冲突',
]

STUCK_FIELDS = [
    'entity_id', 'frame', 'position', 'velocity', 'average_speed',
    'stuck_rule_id', 'trigger_state', 'collision_pairs', 'recovered_frame',
]

STUCK_RULE = '🔑 阈值来自原版实测分布和玩法目标，'
'🔴 **不能填 engine_default**；首次未知可暂记 `source:measurement_pending`'

# 🔴 BRDF
BRDF_FIXED = [
    '固定球面/半球相机阵列', '固定曝光', '固定白平衡', '固定 HDR 输出',
    '固定环境光', '固定距离', '固定线性色彩空间', '固定 MIP',
]

BRDF_MEASURE = [
    '基础色', '金属度', '粗糙度', '**法线强度**', '各向异性', '清漆',
    '次表面', '透射', '剪切', '发光', '**法线解码**', '环境 BRDF LUT',
    '能量补偿', '高光', '菲涅尔', '环境反射', 'IBL',
]

BRDF_SAMPLES = [
    '低/中/高粗糙度', '**掠射角**', '暗色金属', '近黑非金属',
    '**0 与 1 边界**', '法线 0', '透明与蒙版',
]

BRDF_RULE = '🔑 **MaterialX 适合记录节点图 · 参数 · 纹理坐标和命名语义**，'
'降低"同名不同义"；🔴 **但不是两个引擎的自动双向转换器，'
'也不能证明底层 BRDF 相同**'

OPENPBR_RULE = '🔑 OpenPBR 可设为**首选迁移目标**；'
'🔴 但当前原版/新引擎未必都用它，**直接换模型仍会改变外观** —— '
'原版专有参数另存 `legacy_parameter_pack`'

# 工作流
WORKFLOW_FIELDS = [
    'material_id', 'source_workflow', 'target_workflow', 'source_field',
    'source_value', 'mapped_field', 'transform', '**loss_kind**',
    'fallback', 'requires_artist_review',
]

LOSS_KINDS = [
    'identity', 'formula', 'fit', 'clamped', 'missing_target_field',
    'missing_source_value', '**semantic_mismatch**',
]

WORKFLOW_RULE = [
    '🔑 **specular/glossiness 转 metallic/roughness 不是无损** —— '
    '反射颜色可能含漫反射贡献，光泽度曲线、环境贴图、AO 混合、'
    '透明度语义均可能不同',
    '🔴 **不要自动导入未映射属性**',
    '🔴 **任何 `semantic_mismatch` 默认阻断自动通过**',
]

# 色调映射
TONEMAP_FIELDS = [
    '白平衡模式', '色温', '色适应矩阵', '曝光计量区域', '中灰',
    '最小/最大曝光', '速度', '滞后', '镜头衰减', 'HDR 显示模式',
    '最大亮度', '色域', 'gamma', 'sRGB 解码', '线性工作空间',
    '**tonemapper 曲线**', '高光压缩', '阴影提升', 'vignette',
    'chromatic aberration', '**后期顺序**',
]

TONEMAP_PROBES = [
    '固定色卡', '渐变', '镜面高光', '暗部噪声', '透明', '发光', '水', '天空',
]

TONEMAP_OUTPUT = [
    '线性色差', '对数亮度误差', '色度误差', '饱和度误差',
    '**高光夹断率**', '**暗部截零率**',
]

TONEMAP_RULE = '🔑 **色调映射必须被当成一个可测试函数**；'
'🔴 允许阈值**必须以原版为参照**，'
'**不能在 RGB 或 sRGB 空间只比较"看起来像"**'

# 等价四层
LAYER_FOUR = [
    ('**第一层 几何与运动**', '角色位置 · 碰撞 · 阴影接触 · 反射可见性'),
    ('**第二层 低通外观**', '亮度 · 色度 · 粗糙度梯度'),
    ('**第三层 高频细节**', '法线 · 微阴影 · 纹理 · 噪点'),
    ('**第四层 感知体验**', '玩家照片盲测与稳定测点'),
]

LAYER_RULE = '🔴 **SSIM 不能单独证明"游戏正确"** —— '
'尤其会被**模糊 · 锐化 · TAA · 动态分辨率**欺骗'

# 🔴 音效覆盖
AUDIO_SPLIT = [
    'event_id', '触发源', '游戏状态', '触发者种类', '材质', '力度/速度',
    '距离层', '玩家朝向', '负载', '姿态', '昼夜', '天气', '区域', '回声',
    '混响区', 'voice limit', '并发策略', '**回退资源**',
]

AUDIO_MEASURE = [
    'attempt_frame', 'resolved_voice', 'resource_id', 'attenuation_distance',
    'spatialization', 'pan', 'pitch', 'volume', 'start_delay_ms',
    'actual_start_frame', '**silence_reason**',
]

AUDIO_FIELDS = [
    'event_id', 'event_name', 'source_module', 'parameters',
    'conditions_hash', '**expected_resource_count**',
    '**actual_resource_count**', '**actual_play_count**',
    'suppression_reason', 'fallback_resource', 'resolved_resource_id',
    'latency_ms', 'measured_at', 'evidence_level',
]

AUDIO_RULE = [
    '🔑 **音频盲点是事件存在但声音不存在**',
    '🔑 缺失回退必须显式记录 `silence_on_missing` · '
    '`last_known_good_resource` · `procedural_fallback` 或 '
    '`engine_default`',
    '🔴 **默认不允许"找不到文件就什么都不播"** —— '
    '**静默回退要触发审计告警**',
]

# 同帧重复
VOICE_FIVE = [
    'trigger', 'request play', 'queue', 'voice steal', 'instance start',
    'audible start',
]

VOICE_RULE = '🔑 **同一帧事件若原版播放 1 次而新版播放 N 次，'
'或触发去重却丢失首事件，都是偏离**'
VOICE_KEY = '🔴 合并键**不能只用 `event_name + frame`**，'
'至少加入 `source_entity + request_index + parameter_hash`'

AUDIO_VARIANT = '🔑 **变体覆盖要用组合测试而非事件名枚举** —— '
'🔴 **不能因 `footstep_metal_heavy` 存在就推导所有金属表面等价**'

# 相机
CAMERA_ITEMS = [
    '**摄像机是否抖动/漂移**（长时间运行后）',
    '**摄像机与角色的"绑定点"**（头部？胸口？**是否随动画移动**）',
    '**死亡/过场/载具切换时的坐标跳变**',
    '**摄像机插值是否受帧率影响**',
]

CAMERA_RULE = '🔑 **相机"不对劲"很难描述，但玩家立刻能感知**'

# 🔴 现实时钟
CLOCK_LAYERS = [
    '**物理时钟**（monotonic）', '**墙钟**（系统时间）', '**时区与夏令时**',
    '**游戏日**', '**离线账本**',
]

CLOCK_ITEMS = [
    '是否**读取真实系统时间**（节日活动 · 每日奖励 · 现实日期事件）',
    '**时区与夏令时**',
    '**离线期间的现实时间推进**',
    '**修改系统时间的影响**（作弊 · 崩溃 · **负时长**）',
    '**首启日期与"第 N 天"计算**',
]

CLOCK_RULE = '🔑 **重制常改时间源，"每日奖励"口径变化'
'会直接引发玩家不满**'

CONFLICTS = [
    '❌ **用新导航网格替代可达性验证**',
    '❌ 不确定能力参数填零或引擎默认值',
    '❌ 只证明新引擎能复现而不证明原版确实允许',
    '❌ 卡点阈值填 engine_default',
    '❌ 把 MaterialX/OpenPBR 当自动双向转换器',
    '❌ **直接换 OpenPBR 模型**（原版专有参数会丢）',
    '❌ 自动导入未映射属性',
    '❌ **只比较"看起来像"**（应在原版参照下定阈值）',
    '❌ **SSIM 单独证明游戏正确**',
    '❌ **"找不到文件就什么都不播"**',
    '❌ 合并键只用 event_name + frame',
    '❌ 因单个音效存在就推导所有变体等价',
]

FIELDS = [
    ('item_id', '项编号'),
    ('domain', '域（reach / cap / trick / stuck / brdf / workflow / '
               'tonemap / layer / audio / voice / camera / clock）'),
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


def cmd_reach(a):
    _hdr('🔴 可达性（**两阶段**）')
    for k, why in REACH_TWO:
        print(f'   {k}\n      {why}')
    print('\n字段: ' + ' · '.join(REACH_FIELDS))
    print('\n失败种类: ' + ' · '.join(REACH_FAIL))
    print('\n规则:')
    for r in REACH_RULE:
        print(f'   {r}')
    return 0


def cmd_cap(a):
    _hdr('能力参数（**逐参数**）')
    print('参数: ' + ' · '.join(CAP_FIELDS))
    print('\n测法: ' + ' · '.join(CAP_MEASURE))
    print(f'\n   {CAP_RULE}')
    return 0


def cmd_trick(a):
    _hdr('捷径技巧（**证据八级**）')
    for k, why in TRICK_LEVELS:
        print(f'   {k:<8} {why}')
    print('\n规则:')
    for r in TRICK_RULE:
        print(f'   {r}')
    return 0


def cmd_stuck(a):
    _hdr('卡点（**可判定输出**）')
    print('检测项: ' + ' · '.join(STUCK_ITEMS))
    print('\n字段: ' + ' · '.join(STUCK_FIELDS))
    print(f'\n   {STUCK_RULE}')
    return 0


def cmd_brdf(a):
    _hdr('🔴 BRDF（**可复现样本**）')
    print('固定条件: ' + ' · '.join(BRDF_FIXED))
    print('\n测量项: ' + ' · '.join(BRDF_MEASURE))
    print('\n采样必须含: ' + ' · '.join(BRDF_SAMPLES))
    print(f'\n   {BRDF_RULE}')
    print(f'   {OPENPBR_RULE}')
    return 0


def cmd_workflow(a):
    _hdr('工作流转换（**损失映射**）')
    print('字段: ' + ' · '.join(WORKFLOW_FIELDS))
    print('\nloss_kind: ' + ' · '.join(LOSS_KINDS))
    print('\n规则:')
    for r in WORKFLOW_RULE:
        print(f'   {r}')
    return 0


def cmd_tonemap(a):
    _hdr('色调映射（**可测试函数**）')
    print('字段: ' + ' · '.join(TONEMAP_FIELDS))
    print('\n八类探针: ' + ' · '.join(TONEMAP_PROBES))
    print('输出: ' + ' · '.join(TONEMAP_OUTPUT))
    print(f'\n   {TONEMAP_RULE}')
    return 0


def cmd_layer(a):
    _hdr('等价判据（**四层**）')
    for k, why in LAYER_FOUR:
        print(f'   {k}\n      {why}')
    print(f'\n   {LAYER_RULE}')
    return 0


def cmd_audio(a):
    _hdr('🔴 音效（**事件覆盖审计**）')
    print('事件拆分: ' + ' · '.join(AUDIO_SPLIT))
    print('\n实测记录: ' + ' · '.join(AUDIO_MEASURE))
    print('\n覆盖表字段: ' + ' · '.join(AUDIO_FIELDS))
    print('\n规则:')
    for r in AUDIO_RULE:
        print(f'   {r}')
    print(f'\n   {AUDIO_VARIANT}')
    return 0


def cmd_voice(a):
    _hdr('同帧重复（**事件语义**）')
    print('五个时间: ' + ' · '.join(VOICE_FIVE))
    print(f'\n   {VOICE_RULE}')
    print(f'   {VOICE_KEY}')
    return 0


def cmd_camera(a):
    _hdr('相机（**坐标稳定性**）')
    for c in CAMERA_ITEMS:
        print(f'   · {c}')
    print(f'\n   {CAMERA_RULE}')
    return 0


def cmd_clock(a):
    _hdr('🔴 现实时钟（**分层**）')
    print('五层: ' + ' · '.join(CLOCK_LAYERS))
    print('\n必须记录:')
    for c in CLOCK_ITEMS:
        print(f'   · {c}')
    print(f'\n   {CLOCK_RULE}')
    return 0


def cmd_init(a):
    os.makedirs(os.path.dirname(a.init) or '.', exist_ok=True)
    with open(a.init, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow([k for k, _ in FIELDS])
        w.writerow(['TODO'] * len(FIELDS))
    print(f'已生成可达性/材质表: {a.init}')
    print('\n⚠️ 十二域：reach / cap / trick / stuck / brdf / workflow / '
          'tonemap / layer / audio / voice / camera / clock')
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
    print(f'可达性/材质 · {len(rows)} 条')
    print('=' * 76)
    if mismatch:
        print(f'\n🚫 **不一致** {len(mismatch)} 条（行 {mismatch[:15]}）')
    if no_legacy:
        print(f'\n❌ {len(no_legacy)} 条缺**原版值**（行 {no_legacy[:15]}）')
    if no_grade:
        print(f'\n🚫 {len(no_grade)} 条**证据等级缺失或 ≥7 级**'
              f'（行 {no_grade[:15]}）')

    if not (mismatch or no_legacy or no_grade):
        print('\n✅ 可达性/材质：一致、原版值完整、证据等级达标')

    print('\n🔑 **可达性不能被新导航网格替代；原版轨迹才是权威。**')
    print('   **MaterialX/OpenPBR 是中间表示，不是自动转换器。**')
    print('   **音频盲点是"事件存在但声音不存在"；静默回退要告警。**')
    return 1 if (a.gate_check and (mismatch or no_legacy or no_grade)) else 0


def main():
    ap = argparse.ArgumentParser(description='可达性材质与音效覆盖')
    ap.add_argument('--reach', action='store_true')
    ap.add_argument('--cap', action='store_true')
    ap.add_argument('--trick', action='store_true')
    ap.add_argument('--stuck', action='store_true')
    ap.add_argument('--brdf', action='store_true')
    ap.add_argument('--workflow', action='store_true')
    ap.add_argument('--tonemap', action='store_true')
    ap.add_argument('--layer', action='store_true')
    ap.add_argument('--audio', action='store_true')
    ap.add_argument('--voice', action='store_true')
    ap.add_argument('--camera', action='store_true')
    ap.add_argument('--clock', action='store_true')
    ap.add_argument('--init')
    ap.add_argument('--check')
    ap.add_argument('--gate-check', action='store_true')
    a = ap.parse_args()
    fns = {'reach': cmd_reach, 'cap': cmd_cap, 'trick': cmd_trick,
           'stuck': cmd_stuck, 'brdf': cmd_brdf, 'workflow': cmd_workflow,
           'tonemap': cmd_tonemap, 'layer': cmd_layer, 'audio': cmd_audio,
           'voice': cmd_voice, 'camera': cmd_camera, 'clock': cmd_clock}
    for k, fn in fns.items():
        if getattr(a, k):
            return fn(a)
    if a.init:
        return cmd_init(a)
    if a.check:
        return cmd_check(a)
    print('❌ 需要 --reach / --cap / --trick / --stuck / --brdf / '
          '--workflow / --tonemap / --layer / --audio / --voice / '
          '--camera / --clock / --init / --check 之一')
    return 2


if __name__ == '__main__':
    sys.exit(main())
