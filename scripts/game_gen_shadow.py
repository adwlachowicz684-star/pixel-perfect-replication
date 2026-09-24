#!/usr/bin/env python3
"""程序生成边界 + 阴影作为玩法信息（第二十三轮 A / B 类）。

**🔑 A 类核心**：
> 🔴 **"同 seed 同世界"只有在算法、输入、浮点精度、顺序和失败策略
> 完全一致时才成立。**
> 🔴 **"随机种子即确定性"应列为冲突** —— 它忽略平台、浮点、调度、
> 全局副作用和生成失败。

**🔑 B 类核心**：
> 🔴 **先判定"阴影是否权威"，再决定低配档能砍什么。**
> 🔑 **敌人影子先于身体出现，是时间边界而非特效细节。**
> 🔴 **低配关闭所有阴影最危险** —— 若阴影是玩法事实源，
> 等同于**关闭机制**。

用法:
  game_gen_shadow.py --gen     # 🔴 生成**六层**与八字段
  game_gen_shadow.py --recompute # **部分重算** ≠ LOD 局部更新
  game_gen_shadow.py --fail    # 🔴 生成失败**四结果**
  game_gen_shadow.py --version # **生成版本**而非数据格式版本
  game_gen_shadow.py --shadow  # 🔴 shadow_authority 五档
  game_gen_shadow.py --first   # 影子**先于身体**是时间边界
  game_gen_shadow.py --stealth # 潜行**阴影如何进入判定**
  game_gen_shadow.py --contact # 🔴 接触阴影是**接地感**
  game_gen_shadow.py --light   # 动态光源**先证存在再证节奏**
  game_gen_shadow.py --quality # 三档语义 exact/compatible/degraded
  game_gen_shadow.py --init ledger/gen_shadow.csv
  game_gen_shadow.py --check ledger/gen_shadow.csv --gate

退出码: 0 通过 / 1 缺项 / 2 用法错误
"""
import argparse
import csv
import os
import sys

# 🔴 生成六层
GEN_LAYERS = [
    '**离线烘焙资产**', '**运行时世界实例化**', '**流式补丁**',
    '**玩家行为反馈**', '**保存态恢复**', '**版本升级迁移**',
]

GEN_FIELDS = [
    '**generation_layer**', '**input_closure**', 'rng_namespace',
    '**float_precision**', '**generation_phase_order**',
    '**recompute_scope**', '**serialization_policy**', '**failure_policy**',
]

GEN_RULE = [
    '🔑 每层必须明确**读哪些输入 · 是否写回原 seed · '
    '是否允许跨层修改 · 是否进入保存文件**',
    '🔴 若只记顶层 seed，而楼层生成还读**玩家进入时间、上一房间选择、'
    '已死亡次数、平台能力档或尚未确定的随机调用顺序** —— '
    '**原版同一个 seed 在新引擎中仍会发散**',
    '🔑 验收**不应只比较"最终世界哈希"**，应比较每个 '
    'tile/room/chunk 在**各自生成阶段的确定性快照**',
]

GEN_TABLE = [
    ('发生层', '离线烘焙 · 启动时 · 流式进入 · 首次看见 · 玩家交互后'),
    ('输入闭包', 'seed · 全局 RNG · 玩法 RNG · 坐标 · 时间 · '
     '玩家状态 · 配置版本'),
    ('重算范围', '单 chunk · cell · 房间 · 路径图 · 装饰层；'
     '**是否影响相邻边界**'),
    ('序列化', '保存原始 seed · 保存生成指令 · 还是保存结果；'
     '**版本变化后是否重生成**'),
    ('失败处理', '重试次数 · 回溯 · 替换模板 · 生成取消 · '
     '**玩家可见结果**'),
    ('玩法耦合', '几何 · 判定盒 · 敌人刷新 · 路径 · 任务 · 奖励 · '
     '保存标记'),
]

# 部分重算
RECOMPUTE_RULE = [
    '🔴 **"部分重算"必须与渲染 LOD 的局部更新分开** —— '
    '改一处房间模板后，可能只重建装饰，也可能重建**连接走廊、刷新点、'
    '导航图和世界状态**，两者影响完全不同',
    '🔑 每个生成节点保存**依赖指纹**：输入参数哈希 · 模板版本 · '
    '算法实现哈希 · **相邻边界哈希**',
    '🔑 Dirty 判定四步：**内容指纹改变 → 计算影响域 → 模拟副作用 → '
    '确认可见/玩法边界**',
    '🔴 **不是"节点地址变化即重建"**',
]

# 🔴 生成失败
FAIL_FOUR = [
    '**成功且稳定**', '**局部矛盾后重试**',
    '**回退到合法替代模板**', '**无法完成并触发明确的玩家层处理**',
]

FAIL_RULE = [
    '🔴 **生成失败不是异常退出，也不是随机换一个答案**',
    '🔑 WFC 官方明确：传播可能使某个像素的**所有系数归零**，'
    '形成**矛盾且不能继续**；其 NP-hard 背景意味着'
    '**不存在总能在快速时间内完成的通用解法**',
    '🔑 应记录原版在矛盾时是**重试、回滚、替换邻接状态还是生成空区域**',
    '🔴 若复刻简单改成"**直接换种子**" → 世界可生成，'
    '却与原版**分布和地图布局发生无许可偏离**',
]

# 生成版本
VERSION_FIELDS = [
    'generator_name', '**generator_semver**', '**template_set_version**',
    '**rng_family**', 'input_digest', 'generation_flags',
]

VERSION_POLICY = [
    ('只有生成器升级而世界数据仍有效', '标 `regenerate: forbidden`'),
    ('旧世界可保留但新区域按新规则生成', '记录**缝合边界**'),
    ('无法兼容', '执行**双向迁移**而非静默重生成'),
]

VERSION_RULE = '🔑 生成器算法 · 模板 · 规则权重 · RNG · 依赖库 · '
'编译器 · SIMD · 平台**都可能改变世界**'

PRECISION_RULE = [
    '🔑 **FastNoiseLite 支持 float 和/或 double** 说明'
    '**浮点类型本身就是生成输入**',
    '🔑 须记录 `float32/float64` · vector 与 matrix 顺序 · 采样坐标单位 · '
    '法线重建 · 确定性哈希 · **编译器融合设置**',
    '🔴 **不能为性能默认切 float64，也不能为"更精确"擅自改 float32** —— '
    '两者都可能改变**chunk 边界、洞穴连通性和移动轨迹**',
]

# 🔴 阴影权威
SHADOW_AUTHORITY = [
    ('visual_only', '仅视觉'),
    ('**stealth_occlusion**', '**潜行遮挡判定**'),
    ('trigger', '**触发器**'),
    ('navigation_hint', '导航提示'),
    ('narrative_info', '叙事信息'),
]

SHADOW_RULE = [
    '🔴 **先判定"阴影是否权威"，再决定低配档能砍什么**',
    '🔑 若阴影参与潜行判定 → **不能把软阴影、距离裁切、法线偏移和'
    '接触阴影当纯美术选项**',
    '🔑 必须保留 `shadow_cell` · `shadow_strength` · `receiver_mask` · '
    '`normal_offset` 与**采样时序**',
    '🔑 若阴影仅作视觉，可在配置档降档，但**仍要记录降档是否会产生'
    '新的可见阴影边界或让敌人/物体"消失"**',
]

# 影子先于身体
FIRST_FIELDS = [
    '**shadow_first_visible_frame**', 'shadow_world_occlusion',
    'shadow_receiver_flicker',
]

FIRST_RULE = [
    '🔑 **敌人影子先于身体出现，是时间边界而非特效细节**',
    '🔑 要记影子**何时进入视口 · 第一帧是否完整 · 是否受遮挡 · '
    '距离裁切和相机裁切是否一致**',
    '🔑 慢动作下还须记录阴影在**逻辑时间还是渲染时间**更新',
    '🔴 否则视觉上"影子先出现"会让玩家**预输入**，'
    '而逻辑上敌人尚未可见，形成**无记录的信息优势**',
]

# 潜行
STEALTH_FIELDS = [
    '**shadow_authority**（谁拥有）',
    '**shadow_query**（逐光照 / 逐光源采样 / 屏幕空间近似）',
    '**stealth_transfer**（衰减 · 半影 · **自阴影是否计为阴影**）',
    '**result_persistence**（持续到逻辑帧末还是逐渲染帧变化）',
]

STEALTH_RULE = '🔑 若原版用**屏幕空间阴影近似**而新引擎改成'
'**精确逐光源体积判定** → **半影边缘的潜行成功率可能整体改变**，'
'这属于 must-match 偏离'

# 🔴 接触阴影
CONTACT_FIELDS = [
    '**最大距离**', '**步数/采样数**', '**深度偏差**', '**接收面集合**',
    '**与 CSM 的优先级**',
    '**是否影响地面判定 · 脚步声 · 相机碰撞 · 点击目标**',
]

CONTACT_RULE = [
    '🔑 **接触阴影是接触关系，不是远处物体的一般阴影**',
    '🔴 若原版用接触阴影**掩盖脚底漏光**，新引擎提升脚底贴合或'
    '**关闭接触阴影后可能反而出现"浮空"**',
    '🔴 把**屏幕空间阴影当成可靠几何遮挡**也可能在'
    '**镜头切近、遮挡或高速运动**时产生错误判定',
]

# 动态光源
LIGHT_FIELDS = [
    '**光源位置更新源**（逻辑 tick / 动画 / 物理 / 渲染骨骼）',
    '周期', '相位', '随机抖动', '遮挡', '多光源合成',
]

LIGHT_RULE = [
    '🔑 **动态光源的移动、闪烁与可见性要先证存在，再证节奏**',
    '🔑 灯光闪烁若用于提示**电源、危险或解谜**，必须记'
    '"**玩家何时可据灯光推断状态**"，**不是只录 RGB**',
    '🔴 若原版闪烁只是美术，**不能以"更自然"为由加入延迟或缓动** —— '
    '会导致玩家**按旧节奏行动**',
]

# 交互分层
SHADOW_INTERACT = [
    '**影子是否可点击**', '点击命中按**阴影还是 mesh**',
    '**阴影被地形/其他物体遮挡时点击如何裁决**',
    '**阴影与 mesh 不一致时谁赢**',
]

SHADOW_INTERACT_RULE = '🔴 若"敌人影子可点击"在原版不成立，'
'新引擎**仅为视觉完整而让它响应点击，就是新增交互面**'

# 画质三档
QUALITY_THREE = [
    ('**exact**', '保留原版算法与精度'),
    ('**compatible**', '允许滤波/距离变化但**保持判定等价**'),
    ('**degraded**', '明确降低视觉且**列出玩法影响**'),
]

QUALITY_RULE = '🔑 **画质档之间真正要保持一致的是判定契约，'
'外观才允许分档**'

CONFLICTS = [
    '❌ **"随机种子即确定性"**',
    '❌ **运行时每次访问按需生成**（除非原版确实如此）',
    '❌ **生成器升级自动重建旧世界**（= 用重制版替换玩家历史）',
    '❌ **生成失败直接换种子**',
    '❌ 为性能默认切 float64 或为"更精确"改 float32',
    '❌ **统一阴影质量开关**',
    '❌ **能看见阴影就有潜行优势**（未证查询方式）',
    '❌ **接触阴影自动增强接地感**（可能掩盖浮体）',
    '❌ **默认开启软阴影**（半影改变潜行阈值）',
    '❌ **低配关闭所有阴影**（= 关闭机制）',
    '❌ 为视觉完整让影子响应点击',
    '❌ 闪烁只是美术却加延迟缓动',
]

FIELDS = [
    ('item_id', '项编号'),
    ('domain', '域（gen / recompute / fail / version / shadow / first / '
               'stealth / contact / light / quality）'),
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


def cmd_gen(a):
    _hdr('🔴 程序生成（**六层**）')
    for i, l in enumerate(GEN_LAYERS, 1):
        print(f'   {i}. {l}')
    print('\n字段: ' + ' · '.join(GEN_FIELDS))
    print('\n必记:')
    for k, why in GEN_TABLE:
        print(f'   {k:<10} {why}')
    print('\n规则:')
    for r in GEN_RULE:
        print(f'   {r}')
    return 0


def cmd_recompute(a):
    _hdr('部分重算（**≠ LOD 局部更新**）')
    for r in RECOMPUTE_RULE:
        print(f'   {r}')
    return 0


def cmd_fail(a):
    _hdr('🔴 生成失败（**四结果**）')
    for f in FAIL_FOUR:
        print(f'   · {f}')
    print('\n规则:')
    for r in FAIL_RULE:
        print(f'   {r}')
    print('\n精度:')
    for r in PRECISION_RULE:
        print(f'   {r}')
    return 0


def cmd_version(a):
    _hdr('生成版本（**非数据格式版本**）')
    print(f'   {VERSION_RULE}')
    print('\n文件头字段: ' + ' · '.join(VERSION_FIELDS))
    print('\n策略:')
    for k, why in VERSION_POLICY:
        print(f'   {k:<34} {why}')
    return 0


def cmd_shadow(a):
    _hdr('🔴 shadow_authority（**先判权威**）')
    for k, why in SHADOW_AUTHORITY:
        print(f'   {k:<24} {why}')
    print('\n规则:')
    for r in SHADOW_RULE:
        print(f'   {r}')
    print('\n交互分层:')
    for s in SHADOW_INTERACT:
        print(f'   · {s}')
    print(f'\n   {SHADOW_INTERACT_RULE}')
    return 0


def cmd_first(a):
    _hdr('影子先于身体（**时间边界**）')
    print('字段: ' + ' · '.join(FIRST_FIELDS))
    print('\n规则:')
    for r in FIRST_RULE:
        print(f'   {r}')
    return 0


def cmd_stealth(a):
    _hdr('潜行（**阴影如何进入判定**）')
    for f in STEALTH_FIELDS:
        print(f'   · {f}')
    print(f'\n   {STEALTH_RULE}')
    return 0


def cmd_contact(a):
    _hdr('🔴 接触阴影（**接地感**）')
    for f in CONTACT_FIELDS:
        print(f'   · {f}')
    print('\n规则:')
    for r in CONTACT_RULE:
        print(f'   {r}')
    return 0


def cmd_light(a):
    _hdr('动态光源（**先证存在再证节奏**）')
    print('字段: ' + ' · '.join(LIGHT_FIELDS))
    print('\n规则:')
    for r in LIGHT_RULE:
        print(f'   {r}')
    return 0


def cmd_quality(a):
    _hdr('画质三档语义')
    for k, why in QUALITY_THREE:
        print(f'   {k:<16} {why}')
    print(f'\n   {QUALITY_RULE}')
    print('   🔑 阴影距离 · 级联数量 · 法线偏移 · PCF/软阴影 · '
          '逐对象阴影 · **接触阴影**')
    print('      **不得被一个总"阴影质量"开关无差别开关**')
    return 0


def cmd_init(a):
    os.makedirs(os.path.dirname(a.init) or '.', exist_ok=True)
    with open(a.init, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow([k for k, _ in FIELDS])
        w.writerow(['TODO'] * len(FIELDS))
    print(f'已生成生成/阴影表: {a.init}')
    print('\n⚠️ 十域：gen / recompute / fail / version / shadow / first / '
          'stealth / contact / light / quality')
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
    print(f'生成/阴影 · {len(rows)} 条')
    print('=' * 76)
    if mismatch:
        print(f'\n🚫 **不一致** {len(mismatch)} 条（行 {mismatch[:15]}）')
    if no_legacy:
        print(f'\n❌ {len(no_legacy)} 条缺**原版值**（行 {no_legacy[:15]}）')
    if no_grade:
        print(f'\n🚫 {len(no_grade)} 条**证据等级缺失或 ≥7 级**'
              f'（行 {no_grade[:15]}）')

    if not (mismatch or no_legacy or no_grade):
        print('\n✅ 生成/阴影：一致、原版值完整、证据等级达标')

    print('\n🔑 **"同 seed 同世界"只在算法/输入/精度/顺序/失败策略全一致时成立。**')
    print('   **先判阴影是否权威，再决定低配能砍什么；低配关阴影 = 关机制。**')
    print('   **接触阴影是接地感；关闭它反而会出现"浮空"。**')
    return 1 if (a.gate_check and (mismatch or no_legacy or no_grade)) else 0


def main():
    ap = argparse.ArgumentParser(description='程序生成与阴影契约')
    ap.add_argument('--gen', action='store_true')
    ap.add_argument('--recompute', action='store_true')
    ap.add_argument('--fail', action='store_true')
    ap.add_argument('--version', action='store_true')
    ap.add_argument('--shadow', action='store_true')
    ap.add_argument('--first', action='store_true')
    ap.add_argument('--stealth', action='store_true')
    ap.add_argument('--contact', action='store_true')
    ap.add_argument('--light', action='store_true')
    ap.add_argument('--quality', action='store_true')
    ap.add_argument('--init')
    ap.add_argument('--check')
    ap.add_argument('--gate-check', action='store_true')
    a = ap.parse_args()
    fns = {'gen': cmd_gen, 'recompute': cmd_recompute, 'fail': cmd_fail,
           'version': cmd_version, 'shadow': cmd_shadow, 'first': cmd_first,
           'stealth': cmd_stealth, 'contact': cmd_contact,
           'light': cmd_light, 'quality': cmd_quality}
    for k, fn in fns.items():
        if getattr(a, k):
            return fn(a)
    if a.init:
        return cmd_init(a)
    if a.check:
        return cmd_check(a)
    print('❌ 需要 --gen / --recompute / --fail / --version / --shadow / '
          '--first / --stealth / --contact / --light / --quality / '
          '--init / --check 之一')
    return 2


if __name__ == '__main__':
    sys.exit(main())
