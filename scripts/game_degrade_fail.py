#!/usr/bin/env python3
"""性能降级语义 + 失败体验（第十八轮 A / B 类）。

**🔑 本轮核心**：
> 真正的盲区不是"有没有性能预算"，而是把
> **最坏情况、失败路径、边界状态和冗余内容**当成受控体验。
>
> 🔴 **像素级记录不能停在成功路径。**

**🔴 A 类**：
> **"先砍什么"不能只按性能收益排序，还要乘玩法权重** ——
> 应先算 `performance_gain × noticeability × gameplay_coupling × reversibility`。
> 🔴 阴影可能便宜于后处理，**却直接改变潜行可见性**。
> 🔴 **画质档已不是纯视觉配置，而是"规则档"**。

**🔴 B 类**：
> **失败不是错误码，而是可恢复状态。**
> 🔴 "**卡住**"必须可被系统检测，不能等玩家报告。

用法:
  game_degrade_fail.py --tier      # 🔴 降级**决策表**
  game_degrade_fail.py --order     # 🔴 先砍什么 = 收益 × **玩法权重**
  game_degrade_fail.py --hyst      # 降级可立即，**升级必须滞回**
  game_degrade_fail.py --hwmap     # 同档不同体验 → **能力档映射**
  game_degrade_fail.py --hitch     # 加载卡顿**共用异常帧取证**
  game_degrade_fail.py --fail6     # 🔴 失败**六种语义**
  game_degrade_fail.py --retry     # 重试保留输入 + **幂等**
  game_degrade_fail.py --stuck     # 🔴 卡住**系统检测**
  game_degrade_fail.py --honest    # 诚实度含**错误范围与副作用边界**
  game_degrade_fail.py --init ledger/degrade_fail.csv
  game_degrade_fail.py --check ledger/degrade_fail.csv --gate

退出码: 0 通过 / 1 缺项 / 2 用法错误
"""
import argparse
import csv
import os
import sys

# 🔴 降级决策表
TIER_FIELDS = [
    'tier', '**trigger_metric**', 'trigger_window', 'hold_frames',
    'cooldown_seconds', '**up_hysteresis_seconds**',
    '**down_hysteresis_seconds**', 'action', 'affected_features',
    '**visual_noticeable**', '**gameplay_relevant**', 'supported_hardware',
    'fallback_compensation', 'test_capture',
]

TIER_MONITOR = [
    '**P50/P95/P99 帧时**', 'GPU/CPU', '内存', '**热状态**', '流式队列',
]

TIER_DECIDE = [
    '**窗口长度**', '**连持多少帧才降级**', '**稳定多久才升级**',
    '**单次最大变化**', '**同一帧是否允许多项齐变**',
]

TIER_ACTION = [
    '渲染比例', '**阴影距离/分辨率**', '视距', 'LOD bias',
    '**粒子数量与寿命**', '后处理', '各向异性', '纹理流送', '动画 tick',
    '**物理 sub-step**', '音频质量', '目标刷新率',
]

# 🔴 砍的顺序
ORDER_FORMULA = 'performance_gain × noticeability × gameplay_coupling × reversibility'

ORDER_RULE = [
    '🔴 **性能收益最大的项不一定能砍**',
    '🔑 阴影可能便宜于后处理，**却直接改变潜行可见性**',
    '🔑 粒子数量变化可能改变**弹幕密度判断**',
    '🔑 视距变化可能**暴露或遮蔽敌人**',
    '🔴 **动态分辨率若作用于 HUD → 破坏准星、字幕和地图可读性**',
    '🔑 官方资料提示动态分辨率**通常不用于 2D UI** —— '
    '"砍分辨率"**不能成为无差别默认**',
]

# 滞回
HYST_RULE = [
    '🔑 **降级可立即执行，升级必须受更长稳定窗口约束**',
    '🔑 升级窗口常为降级的 **2–5 倍**（经验参数，**必须在目标硬件上校准**，'
    '不是通用规范）',
    '🔑 档位变化应触发**确定性日志**，但**不必打扰玩家**',
]

HYST_CHECK = [
    '**是否仅影响外观**', '**是否保留同一玩法规则**', '**是否改变 HUD 尺寸**',
    '**是否改变阴影判定**', '**是否改变可见距离**',
    '**是否改变命中盒或判定窗口**', '**是否改变声音传播**',
    '**是否引起音频/震感突变**',
]

HYST_ANTI = [
    '**一帧内多项齐变**', '**降级后立即升级**',
    '**同一档在 60 秒内切换三次**', '恢复后仍低于阈值', '档位变化未产生日志',
]

HYST_RULE2 = '🔑 **可逆不是缺陷，但没有滞回的不可逆才是缺陷**'

# 硬件映射
HWMAP_RULE = [
    '🔴 **同档不同体验不能用"同档"解决，必须用能力档映射**',
    '🔑 同一 `High` 档在低端、主流、旗舰 GPU 上的帧时和显存余量'
    '**可能完全不同**',
    '🔑 应建立 `hardware_profile → benchmark_score → quality_tier` 映射，'
    '**而非按 GPU 名写死允许列表**',
]

HWMAP_FIELDS = [
    'CPU/GPU/驱动/内存/分辨率/刷新率/OS 版本', '**实测分数**',
    '跨档迁移测试要证明：**同一操作在相同输入下的结果语义不因画质档改变**',
]

# 卡顿
HITCH_FIELDS = [
    '资产类别', '预期加载阶段', '实际开始/完成时间戳', '**主线程阻塞毫秒**',
    'IO 等待', '解压', '**着色器编译**', '纹理上传', 'GC', '渲染线程等待',
    '**玩家是否可移动**', '**是否显示诚实阶段**', '是否可跳过或取消',
    '是否允许输入', '**中断后状态**', '回滚资源',
]

HITCH_KINDS = [
    '首次运行', '冷启动', '热重载', '快速旅行', '区域流式',
    '**对象池耗尽**', '**着色器编译**', '音频解码', '脚本绑定', '序列化',
]

HITCH_RULE = '🔴 卡顿**不能只标"出现 loading"** —— 应区分上述十类'

# 🔴 失败六种
FAIL_SIX = [
    '**静默失败**', '**提示**', '**阻断**', '**自动重试**', '**手动重试**',
    '**保留输入**',
]

FAIL_RETURN = [
    '输入框', '**光标位置**', '选项页', '数量', '装备预设', '路径或目标',
]

FAIL_RULE = [
    '🔑 失败返回后应**保留上述六项**，除非保留会破坏安全契约',
    '🔑 明确**哪些保留、哪些必须重新授权、哪些自动清空**',
]

# 重试
RETRY_RULE = [
    '🔑 自动重试应**有限次、指数退避与抖动**，避免雪崩',
    '🔑 手动重试必须说明**是否重放同一输入、是否重新校验、'
    '是否会产生重复副作用**',
    '🔴 对"拾取""交易""使用消耗品"，重试前**必须做幂等检查** —— '
    '否则一次请求重试会变成**两份物品**',
]

# 🔴 卡住
STUCK_DETECTORS = [
    '主角连续不可移动但输入有效', '相机目标丢失', '**任务目标不可达**',
    '敌人 AI 长时间无状态转移', '**对话停留在同一句**', '过场时间未推进',
    '**交互处于 opening 但目标已销毁**', '持有道具却没有有效交付对象',
    '等待远程资源超时', '界面焦点丢失且不可导航', '输入被全屏面板持续吞掉',
]

STUCK_FIELDS = [
    'window', 'minimum_expected_event_rate', '**recovery_action**',
    'player_notice', 'telemetry_only',
]

STUCK_RULE = [
    '🔴 **"卡住"必须可被系统检测，不能等玩家报告**',
    '🔑 恢复优先回到**最近的稳定检查点、安全位置或可重试界面**',
    '🔴 **不得默默重置为标题菜单**',
]

# 诚实度
HONEST_CASES = [
    ('**保存失败**', '必须说明存档**是否部分写入**'),
    ('**交易失败**', '必须说明货币/物品**哪一侧回滚**'),
    ('**匹配失败**', '必须说明**是否扣费**'),
    ('**云同步失败**', '必须说明**本地是否仍是权威**'),
    ('**覆盖失败**', '必须说明目标**是否已被临时锁定**'),
]

HONEST_RULE = '🔑 **诚实度不仅是文字，还包括错误范围与副作用边界**'

FAIL_TESTS = [
    '合法', '非法', '**超时**', '**重复**', '**中断**', '**部分写**',
    '**并发写**', '**回滚失败**',
]

FAIL_ASSERT = ['提示', '状态', '重试', '**输入保留**', '日志']

CONFLICTS = [
    '❌ **默认最低画质，能跑再说**',
    '❌ **同档保证同体验**',
    '❌ **砍特效永远安全**',
    '❌ **动态分辨率自动覆盖 HUD**',
    '❌ 玩家不必知道档位变化',
    '❌ **只要平均帧率达标即可**（掩盖 P99 卡顿）',
    '❌ **失败只记录日志不提示**',
    '❌ **全局 try-catch 继续运行**（把未知状态伪装成正常）',
    '❌ **自动重试无上限**（重复提交）',
    '❌ **保存失败后仍显示成功**（虚假安全感）',
    '❌ **崩溃即静默退出**（丢失最后证据）',
    '❌ **任何错误都弹模态框**（频繁失败变成另一种卡顿）',
]

FIELDS = [
    ('item_id', '项编号'),
    ('domain', '域（tier / order / hyst / hwmap / hitch / fail6 / retry / '
               'stuck / honest）'),
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


def cmd_tier(a):
    _hdr('🔴 降级决策表')
    for f in TIER_FIELDS:
        print(f'   · {f}')
    print('\n监测指标: ' + ' · '.join(TIER_MONITOR))
    print('\n决策: ' + ' · '.join(TIER_DECIDE))
    print('\n响应: ' + ' · '.join(TIER_ACTION))
    return 0


def cmd_order(a):
    _hdr('🔴 先砍什么（**收益 × 玩法权重**）')
    print(f'   公式: {ORDER_FORMULA}')
    print('\n规则:')
    for r in ORDER_RULE:
        print(f'   {r}')
    return 0


def cmd_hyst(a):
    _hdr('滞回（**升级必须更慢**）')
    for r in HYST_RULE:
        print(f'   {r}')
    print('\n必记: ' + ' · '.join(HYST_CHECK))
    print('\n反模式: ' + ' · '.join(HYST_ANTI))
    print(f'\n   {HYST_RULE2}')
    return 0


def cmd_hwmap(a):
    _hdr('硬件能力档映射')
    for r in HWMAP_RULE:
        print(f'   {r}')
    print('\n字段: ' + ' · '.join(HWMAP_FIELDS))
    return 0


def cmd_hitch(a):
    _hdr('加载卡顿（**共用异常帧取证**）')
    for f in HITCH_FIELDS:
        print(f'   · {f}')
    print('\n阶段类型: ' + ' · '.join(HITCH_KINDS))
    print(f'\n   {HITCH_RULE}')
    return 0


def cmd_fail6(a):
    _hdr('🔴 失败六种语义')
    for f in FAIL_SIX:
        print(f'   · {f}')
    print('\n返回应保留: ' + ' · '.join(FAIL_RETURN))
    print('\n规则:')
    for r in FAIL_RULE:
        print(f'   {r}')
    print('\n注入测试: ' + ' · '.join(FAIL_TESTS))
    print('\n断言: ' + ' · '.join(FAIL_ASSERT))
    return 0


def cmd_retry(a):
    _hdr('重试（**幂等**）')
    for r in RETRY_RULE:
        print(f'   {r}')
    return 0


def cmd_stuck(a):
    _hdr('🔴 卡住（**系统检测**）')
    for s in STUCK_DETECTORS:
        print(f'   · {s}')
    print('\n字段: ' + ' · '.join(STUCK_FIELDS))
    print('\n规则:')
    for r in STUCK_RULE:
        print(f'   {r}')
    return 0


def cmd_honest(a):
    _hdr('诚实度（**错误范围与副作用边界**）')
    for k, why in HONEST_CASES:
        print(f'   {k:<14} {why}')
    print(f'\n   {HONEST_RULE}')
    return 0


def cmd_init(a):
    os.makedirs(os.path.dirname(a.init) or '.', exist_ok=True)
    with open(a.init, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow([k for k, _ in FIELDS])
        w.writerow(['TODO'] * len(FIELDS))
    print(f'已生成降级/失败表: {a.init}')
    print('\n⚠️ 九域：tier / order / hyst / hwmap / hitch / fail6 / retry / '
          'stuck / honest')
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
    print(f'降级/失败 · {len(rows)} 条')
    print('=' * 76)
    if mismatch:
        print(f'\n🚫 **不一致** {len(mismatch)} 条（行 {mismatch[:15]}）')
    if no_legacy:
        print(f'\n❌ {len(no_legacy)} 条缺**原版值**（行 {no_legacy[:15]}）')

    if not (mismatch or no_legacy):
        print('\n✅ 降级/失败：一致且原版值完整')

    print('\n🔑 **画质档不是视觉配置，是"规则档"。**')
    print('   **失败不是错误码，是可恢复状态；卡住必须被系统检测。**')
    print('   **像素级记录不能停在成功路径。**')
    return 1 if (a.gate_check and (mismatch or no_legacy)) else 0


def main():
    ap = argparse.ArgumentParser(description='性能降级与失败体验')
    ap.add_argument('--tier', action='store_true')
    ap.add_argument('--order', action='store_true')
    ap.add_argument('--hyst', action='store_true')
    ap.add_argument('--hwmap', action='store_true')
    ap.add_argument('--hitch', action='store_true')
    ap.add_argument('--fail6', action='store_true')
    ap.add_argument('--retry', action='store_true')
    ap.add_argument('--stuck', action='store_true')
    ap.add_argument('--honest', action='store_true')
    ap.add_argument('--init')
    ap.add_argument('--check')
    ap.add_argument('--gate-check', action='store_true')
    a = ap.parse_args()
    fns = {'tier': cmd_tier, 'order': cmd_order, 'hyst': cmd_hyst,
           'hwmap': cmd_hwmap, 'hitch': cmd_hitch, 'fail6': cmd_fail6,
           'retry': cmd_retry, 'stuck': cmd_stuck, 'honest': cmd_honest}
    for k, fn in fns.items():
        if getattr(a, k):
            return fn(a)
    if a.init:
        return cmd_init(a)
    if a.check:
        return cmd_check(a)
    print('❌ 需要 --tier / --order / --hyst / --hwmap / --hitch / --fail6 / '
          '--retry / --stuck / --honest / --init / --check 之一')
    return 2


if __name__ == '__main__':
    sys.exit(main())
