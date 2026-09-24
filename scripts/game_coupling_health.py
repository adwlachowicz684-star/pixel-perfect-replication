#!/usr/bin/env python3
"""环境耦合 + 系统健康 + 可观测性相位（第二十七轮 A / B / C 类）。

**🔑 本轮主线**：
> 复刻对象必须从"**各系统正确**"升级为
> "**组合状态可复现 · 退化可判定 · 测量有相位**"。

**🔑 A 类核心**：
> 🔑 **最细也最容易被忽略的事实：草、树、旗、披风、粒子、烟
> 是否由同一风场、同一相位、同一时间积分驱动。**
> 🔑 若各自用自己的时间积分，**即使采样同一风向量，累积相位也会漂移**。

**🔑 B 类核心**：
> 🔑 **系统健康的正确单位不是"报错"，
> 而是"玩家是否仍能获得原版承诺的状态"。**
> 🔴 **`阈值来源 = engine default` 应被自动拒绝。**

**🔑 C 类核心**：
> 🔑 **晚一帧的读数不是误差，而是伪 bug 来源。**
> 🔴 RGP 已证明**提交时戳与 GPU 执行时戳不同**；
> OCAT 也证明**测量覆盖层自身可改变帧节奏**。

用法:
  game_coupling_health.py --wind   # 🔴 **风场相位**是否同源
  game_coupling_health.py --matrix # 环境**耦合矩阵**表头与单元格
  game_coupling_health.py --combo  # 八组**组合用例**
  game_coupling_health.py --health # 🔴 系统健康**检测项表**
  game_coupling_health.py --state  # 健康**状态机**五态
  game_coupling_health.py --obs    # 🔴 可观测性**相位化字段**
  game_coupling_health.py --probe  # 六个人口点健康摘要
  game_coupling_health.py --init ledger/coupling_health.csv
  game_coupling_health.py --check ledger/coupling_health.csv --gate

退出码: 0 通过 / 1 缺项 / 2 用法错误
"""
import argparse
import csv
import os
import sys

# 🔴 风场
WIND_FIELDS = [
    ('**wind_authority**', '全局 / 局部 / 对象局部'),
    ('**field_representation**', '采样网格 · 探针 · 噪声 · 玩家跟随盒'),
    ('**sample_space**', '世界 / 局部 / 地形 UV'),
    ('**phase_epoch**', '相位纪元'),
    ('**timestep_mode**', 'fixed / substep / real / render'),
    ('**player_influence**', '是否能推开、是否写回'),
    ('**coupling_mode**', 'read-only / two-way / event-only'),
]

WIND_RULE = [
    '🔑 第一列不应写"风系统"，而应写**权威量**',
    '🔑 只有写清这些，才能区分"**效果不完全一样**"和'
    '"**必须匹配则偏离**"',
    '🔑 每个消费者必须写 `**read_phase**`：草读模拟相位 · '
    '披风读布料子步 · 粒子读发射相位 · 音频读声音图相位',
    '🔴 若各自用自己的时间积分，**即使采样同一风向量，'
    '累积相位也会漂移**',
    '🔑 必须强制记 `**resample_or_integrate**`：'
    '每子步重采样，还是持有一份确定性状态积分 —— '
    '**两者不能由引擎默认值任意选择**',
]

# 耦合矩阵
MATRIX_HEADER = [
    'weather_id', 'time_of_day', 'moon_or_sun_angle', 'region_id',
    'terrain_surface', '**surface_wetness**', 'surface_depth',
    'surface_temperature', 'vegetation_density', 'water_depth',
    'water_flow', 'water_viscosity', '**cloth_drag_coeff**',
    'player_load_modifier', 'input_grip_or_friction',
]

MATRIX_CELL = [
    'authority', 'formula_or_asset', '**producer_phase**',
    '**consumer_phase**', 'unit', 'range', 'interpolation', 'fallback',
    'measured_at', 'sample_count', 'evidence_level',
]

MATRIX_FIELDS = [
    'state_key', '**authoritative_source**', 'domain_min', 'domain_max',
    'quantization', 'interpolation_mode', 'latency_budget', 'consumers',
    '**deviation_class**',
]

MATRIX_RULE = [
    '🔑 按"**环境状态 × 系统 × 动作**"索引，'
    '**而不是按美术资源索引**',
    '🔑 **单元格不是"有/无"**',
    '🔑 允许记"原版不明"，但**不得省略格位**',
]

# 八组组合用例
COMBO_EIGHT = [
    ('**雨天草丛**', '草的摆动阻尼、贴服、摩擦、脚步声与可见溅水是否同步',
     '至少**四通道在同一权威湿润度下产生一致状态**',
     '视觉湿润而音效仍干；物理摩擦未变'),
    ('**夜晚水面**', '镜面强度、法线尺度、发光、雾、反射源与可见性',
     '同一昼夜与相机状态下亮度、可见目标及反射内容匹配',
     '只降低曝光，不重做反射权威'),
    ('**风与服饰**', '树·草·旗·披风·粒子·烟的相位与振幅',
     '同风源、同时刻、同积分规则下相位关系匹配',
     '**各资源包各自风噪声**'),
    ('**雪地**', '脚步声、足迹形状、留存时间、可见性、速度惩罚',
     '表面·时间·角色状态·摄像机四视图一致',
     '只做贴花，没有寿命和声音语义'),
    ('**洞穴水体**', '混响、遮挡、水面声、玩家空间定位',
     '相机·音源·材质·遮挡共同进入声学结果',
     '把洞穴水体当普通 2D 环境音'),
    ('**湿装备**', '重量、耐力、潜行、换装与 UI 提示',
     '一套权威湿度映射，不因视觉贴图与玩法表不同步',
     '**披风变暗但负重不变**'),
    ('**水下布料**', '浮力、拖曳、穿透、碰撞层级、附着约束',
     '水下进入/退出沿同一权威水位判定',
     '**草与角色进入水中而披风仍按空气阻力**'),
    ('**披风-门-相机**', '碰撞、穿门、视野遮挡、瞬移与重附着',
     '每个实体记录进入/离开与 authority 转换',
     '视觉消失但碰撞仍阻塞；反之造成"推不动"'),
]

# 🔴 系统健康检测项
HEALTH_ROWS = [
    ('Shader 编译超时', '单 PSO/变体等待 · 队列长度 · 卡顿帧 · 首次画面帧',
     '黑屏 · 冻结 · **首次转头卡顿** · 音画继续',
     '预编译清单/异步队列/回退稳定变体',
     '**检测查询可能争编译线程，必须旁路测时**'),
    ('LOD 裂缝突变', '相邻 patch 等级差 · 屏幕空间跳变 · silhouette 距离',
     '**模型突然换皮** · 接缝可见 · 命中盒变化',
     '重新选择 · stitch · 限制换级帧',
     '**逐顶点检测成本过高，建议抽帧**'),
    ('植被密度突变', '实例数 · 密度场梯度 · 流式块完成率',
     '**草突然长出/消失** · 路线遮挡变化',
     '回滚流式块或等待下一加载边界',
     '每帧全量盘点会制造卡顿'),
    ('水面 NaN', '高度场 min/max · inf/NaN 位 · 法线长度 · 采样点',
     '水面消失 · **角色无限下沉** · 模拟发散',
     '重置场 · 回退前一稳定场 · 禁止进水',
     '**检测不可改变采样结果；复制后校验**'),
    ('布料穿透累积', '最大穿透 · 累计时长 · 约束误差 · 顶点越界',
     '**披风穿胸** · 拖曳异常 · 可见闪烁',
     '清除穿透/重投影/短窗口重模拟',
     '**诊断约束过强会改变正常摆动**'),
    ('反射缺失', '捕获成功 · 纹理有效 · 帧年龄 · 可见镜面区域',
     '**镜子空白** · 窗影缺失 · 玩家可凭此判断位置',
     '下一帧重试 · 稳定低开销替身',
     '连续全分辨率捕获破坏性能'),
    ('粒子预算超限', '活跃粒子 · 发射器 · overdraw · 峰值帧',
     '特效突减 · **战斗反馈变钝**',
     '裁剪距离/LOD/合并，**保留关键判定粒子**',
     '🔴 **降级不可改变命中或奖励判定**'),
    ('音频真峰值', 'true peak · sample 溢出 · clip count · device latency',
     '破音 · 爆音 · 节奏失准',
     '降低源增益/重置 graph/重建 voice',
     '检测不可改变玩家听到的最终混音'),
    ('OpenXR session loss', 'session state · loss reason · tracking loss',
     '画面冻结 · 重定位跳变 · 控制器消失',
     '按 loss-pending-resume 保存应用状态',
     '**误恢复可能清掉输入或破坏时间缩放**'),
    ('陀螺仪漂移', '零偏 · 静止方差 · 积分航向误差',
     '**视角自行旋转** · 瞄准漂移 · 晕动',
     '重校准/零速检测/限制积分',
     '**检测输入会改变玩家输入，需隔离**'),
    ('帧预算债务', '累计 overrun · debt · catch-up 帧数',
     '慢动作 · 回滚 · 卡顿 · 物理迟到',
     '限速 · 降预算 · 事件丢弃策略',
     '自我观测必须走轻量计数器'),
]

HEALTH_FIELDS = [
    'detector_id', 'component', '**owner**', 'version_introduced',
    '**threshold_source**', 'raw_value', 'threshold', 'comparison',
    '**severity**', '**player_visible_expression**', 'first_frame',
    'last_frame', 'duration_frames', 'sample_count', 'trigger_condition',
    'false_positive_risk', '**recovery_action**',
    'degraded_mode_change', '**changed_gameplay**', 'telemetry_key',
    'replay_context', 'allow_in_shipping',
]

HEALTH_RULE = [
    '🔑 **系统健康的正确单位不是"报错"，'
    '而是"玩家是否仍能获得原版承诺的状态"**',
    '🔴 **阈值来源只能是六者之一** —— '
    '**阈值来源 = engine default 应被自动拒绝**',
    '🔑 `player_visible_expression` 必须描述**玩家可观察结果**，'
    '例如"LOD 突变、模型突然换皮、摄像机穿模"，'
    '**不能只写"LOD 跳变"**',
    '🔑 `changed_gameplay` 明确写是否**改判 · 改速 · 改命中 · 改 AI · '
    '改可见区域**',
]

THRESHOLD_SIX = [
    '原版实测百分位', '需求契约', '资产预算', '设备规格', '用户研究',
    '工程默认值',
]

RECOVERY_SEVEN = [
    'none', 'retry', 'rebuild', 'fallback', 'disable_feature',
    'restart_phase', 'restart_session',
]

# 健康状态机
STATE_FIVE = [
    'nominal', 'observing', 'degraded', 'recovering', 'failed',
]

STATE_EXTRA = ['unknown', 'suppressed_for_test']

STATE_RULE = [
    '🔑 每次转换必须写 `before_snapshot · after_snapshot · '
    'affected_features · affected_decisions · player_notice · '
    'expected_duration`',
    '🔑 特别要检测"**降级检测导致的降级**" —— '
    '例如布料穿透检测开启更强约束，约束改变披风摆动，'
    '**进而让风耦合测试失败**',
    '🔑 或粒子降级删掉关键判定粒子，却只把"视觉特效减少"登记为降级',
    '🔑 所有检测必须运行 **A/A 自测**：相同输入两次执行，'
    '**检测开销自身应稳定且可关闭**',
    '🔑 **降级不能静默发生，也不能无条件改变玩法**',
]

# 🔴 可观测性相位
OBS_FIELDS = [
    '**frame_index**', '**phase**', '**substep**', '**wall_time**',
    '**scaled_time**', '版本', '平台签名',
]

OBS_DOMAINS = [
    '地形可见性', '水体状态', '**布料 sim 步**', '反射捕获', '粒子 tick',
    '音频 graph', '**XR pose**', '编译状态',
]

OBS_RULE = [
    '🔑 所有读数必须说明它属于**哪一帧 · 哪一段 · 哪一个时钟**',
    '🔴 RGP 已证明**提交时戳与 GPU 执行时戳不同**',
    '🔴 OCAT 也证明**测量覆盖层自身可改变帧节奏**',
    '🔑 **调试读数晚一帧**会与**输入预测 · 回滚 · 慢动作 · 加载阶段**'
    '形成**伪 bug**',
]

# 六个人口点
PROBE_SIX = [
    '启动自检', '**加载事务**', '**场景稳定期**', '关键战斗', '保存', '退出',
]

PROBE_RULE = '🔑 稳定期**不能只看平均帧率**，还要看 **P1/P0.1 · '
'连续超预算帧 · 输入到动作 · 声音到扬声器 · 渲染到显示**四段延迟'

PROBE_FATAL = '🔑 fatal 时应保留与当前 build 严格一致的**轻量 trace**，'
'而不是依赖用户手动开启高级抓取；'
'🔴 但自动抓取必须遵循"**先冻结证据、再改变状态**"'

CONFLICTS = [
    '❌ 各系统各自风噪声（**不共享风场相位**）',
    '❌ 视觉湿润而音效仍干 / 物理摩擦未变',
    '❌ 只做雪地贴花，没有寿命和声音语义',
    '❌ **披风变暗但负重不变**',
    '❌ 草与角色入水而披风仍按空气阻力',
    '❌ 视觉消失但碰撞仍阻塞（或反之）',
    '❌ **`阈值来源 = engine default`**',
    '❌ `player_visible_expression` 只写"LOD 跳变"',
    '❌ **静默降级**',
    '❌ **降级改变命中或奖励判定**',
    '❌ 检测本身改变被测对象（争编译线程/强约束/改变混音）',
    '❌ 只读平均帧率',
    '❌ **调试读数不绑相位**（晚一帧形成伪 bug）',
    '❌ 混用 CPU 提交时戳与 GPU 执行时戳',
]

FIELDS = [
    ('item_id', '项编号'),
    ('domain', '域（wind / matrix / combo / health / state / obs / probe）'),
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


def cmd_wind(a):
    _hdr('🔴 风场（**相位是否同源**）')
    for k, why in WIND_FIELDS:
        print(f'   {k:<26} {why}')
    print('\n规则:')
    for r in WIND_RULE:
        print(f'   {r}')
    return 0


def cmd_matrix(a):
    _hdr('环境耦合矩阵（**权威量表**）')
    print('表头: ' + ' · '.join(MATRIX_HEADER))
    print('\n单元格字段: ' + ' · '.join(MATRIX_CELL))
    print('\n矩阵字段: ' + ' · '.join(MATRIX_FIELDS))
    print('\n规则:')
    for r in MATRIX_RULE:
        print(f'   {r}')
    return 0


def cmd_combo(a):
    _hdr('八组组合用例')
    for k, must, judge, bad in COMBO_EIGHT:
        print(f'\n   {k}')
        print(f'     原版须记: {must}')
        print(f'     判定:     {judge}')
        print(f'     常见偏离: {bad}')
    return 0


def cmd_health(a):
    _hdr('🔴 系统健康（**检测项表**）')
    for k, raw, vis, rec, risk in HEALTH_ROWS:
        print(f'\n   【{k}】')
        print(f'     读数:     {raw}')
        print(f'     玩家可见: {vis}')
        print(f'     恢复:     {rec}')
        print(f'     ⚠️ {risk}')
    print('\n字段: ' + ' · '.join(HEALTH_FIELDS))
    print('\n阈值来源（**六者之一**）: ' + ' · '.join(THRESHOLD_SIX))
    print('恢复动作: ' + ' · '.join(RECOVERY_SEVEN))
    print('\n规则:')
    for r in HEALTH_RULE:
        print(f'   {r}')
    return 0


def cmd_state(a):
    _hdr('健康状态机（**五态 + 二附加**）')
    print('   ' + ' → '.join(STATE_FIVE))
    print('   附加: ' + ' · '.join(STATE_EXTRA))
    print('\n规则:')
    for r in STATE_RULE:
        print(f'   {r}')
    return 0


def cmd_obs(a):
    _hdr('🔴 可观测性（**相位化**）')
    print('字段: ' + ' · '.join(OBS_FIELDS))
    print('\n各域相位: ' + ' · '.join(OBS_DOMAINS))
    print('\n规则:')
    for r in OBS_RULE:
        print(f'   {r}')
    return 0


def cmd_probe(a):
    _hdr('六个人口点（**健康摘要**）')
    print('   ' + ' · '.join(PROBE_SIX))
    print(f'\n   {PROBE_RULE}')
    print(f'\n   {PROBE_FATAL}')
    return 0


def cmd_init(a):
    os.makedirs(os.path.dirname(a.init) or '.', exist_ok=True)
    with open(a.init, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow([k for k, _ in FIELDS])
        w.writerow(['TODO'] * len(FIELDS))
    print(f'已生成耦合/健康表: {a.init}')
    print('\n⚠️ 七域：wind / matrix / combo / health / state / obs / probe')
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
    print(f'耦合/健康 · {len(rows)} 条')
    print('=' * 76)
    if mismatch:
        print(f'\n🚫 **不一致** {len(mismatch)} 条（行 {mismatch[:15]}）')
    if no_legacy:
        print(f'\n❌ {len(no_legacy)} 条缺**原版值**（行 {no_legacy[:15]}）')
    if no_grade:
        print(f'\n🚫 {len(no_grade)} 条**证据等级缺失或 ≥7 级**'
              f'（行 {no_grade[:15]}）')

    if not (mismatch or no_legacy or no_grade):
        print('\n✅ 耦合/健康：一致、原版值完整、证据等级达标')

    print('\n🔑 **各系统各自正确 ≠ 组合正确；风场相位必须同源。**')
    print('   **系统健康的单位是"玩家是否仍获得原版承诺的状态"。**')
    print('   **晚一帧的读数不是误差，而是伪 bug 来源。**')
    return 1 if (a.gate_check and (mismatch or no_legacy or no_grade)) else 0


def main():
    ap = argparse.ArgumentParser(description='环境耦合与系统健康')
    ap.add_argument('--wind', action='store_true')
    ap.add_argument('--matrix', action='store_true')
    ap.add_argument('--combo', action='store_true')
    ap.add_argument('--health', action='store_true')
    ap.add_argument('--state', action='store_true')
    ap.add_argument('--obs', action='store_true')
    ap.add_argument('--probe', action='store_true')
    ap.add_argument('--init')
    ap.add_argument('--check')
    ap.add_argument('--gate-check', action='store_true')
    a = ap.parse_args()
    fns = {'wind': cmd_wind, 'matrix': cmd_matrix, 'combo': cmd_combo,
           'health': cmd_health, 'state': cmd_state, 'obs': cmd_obs,
           'probe': cmd_probe}
    for k, fn in fns.items():
        if getattr(a, k):
            return fn(a)
    if a.init:
        return cmd_init(a)
    if a.check:
        return cmd_check(a)
    print('❌ 需要 --wind / --matrix / --combo / --health / --state / '
          '--obs / --probe / --init / --check 之一')
    return 2


if __name__ == '__main__':
    sys.exit(main())
