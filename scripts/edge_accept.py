#!/usr/bin/env python3
"""四路验收接入：统一时钟 · 截图 diff · 音频指纹 · 物理表面（第五十一轮 D）。

> 🔑 **统一时钟比统一像素阈值更重要。**
> 🔑 **整屏 diff 用于状态边界，逐帧 diff 用于循环内容。**
> 🔑 **音频验证分三层，不应让指纹库承担它不擅长的任务。**
> 🔑 **物理表面以可复核尺度为 must-match，不以艺术化照片为 must-match。**

用法:
  edge_accept.py --clock   # 🔑 **统一时钟与命名规范**
  edge_accept.py --visual  # **整屏 vs 逐帧**
  edge_accept.py --audio   # **三层音频验证**
  edge_accept.py --photo   # **可复核尺度**
  edge_accept.py --join    # **四路合并为同一时间轴事件流**
  edge_accept.py --init ledger/edge_accept.csv
  edge_accept.py --check ledger/edge_accept.csv --gate

退出码: 0 通过 / 1 缺项 / 2 用法错误
"""
import argparse
import csv
import os
import sys

CLOCK_RULE = '🔑 **统一时钟比统一像素阈值更重要。**'
CLOCK_NAMING = '`{build_id}/{state}/{media_type}/'
'{frame_or_sample_index}_{clock_ns}.{ext}`'
CLOCK_ITEMS = [
    ('视频', '无损容器或无损中间格式；截图保存**无损 PNG**'),
    ('音频', '同时保存**原始 WAV** 与由固定命令行产生的指纹'),
    ('照片', '保存 **RAW** 与**锁定白平衡 · 手动曝光 · 固定焦距**的副本'),
]
CLOCK_ENV = '🔑 官方提醒 **OS · 版本 · 设置 · 硬件 · 电源模式 · headless 模式'
'都会影响渲染**，要求 baseline 与测试在同一环境生成'
CLOCK_MATRIX = '🔑 **构建矩阵必须展开成 `engine × platform × renderer × build_id`，'
'🔴 不能只有"原版/复刻版"两栏**'

VISUAL_RULE = '🔑 **整屏 diff 用于状态边界，逐帧 diff 用于循环内容。**'
VISUAL_ITEMS = [
    ('整屏断言', '对 Attract 的每个**离散屏**用整屏参考；'
     '首次生成 reference，后续逐次比较'),
    ('逐帧', '对**连续滚屏**用逐帧 overlap 或 phase-locked frame'),
    ('滑窗差异', 'pixelmatch 的 `windowSize=N` 输出**任意 N×N 滑窗的最大差异数**，'
     '🔑 **非常适合检测"小区域滚动残影"而避免全屏 diff 被合理运动淹没**'),
    ('批量 CI', 'ODiff（Zig + SIMD）支持**不同布局/尺寸比较与忽略区**'),
]
VISUAL_CHAIN = '🔑 建议主链：**Playwright → PNG → ODiff**；'
'pixelmatch 作为可读 fallback（Playwright 内置引擎即 pixelmatch，不需重复封装）'
VISUAL_PREDICATE = '🔑 **must-match 偏离必须写成可执行谓词**：'
'Attract 循环固定起点后录 K 个周期，`phase_match_ratio` 为逐帧匹配率，'
'🔑 允许的视觉噪声只来自渲染器而非内容；'
'🔑 **若 `phase_match_ratio < 0.98` 则 fail**；'
'若整屏差异集中在 mask 内且不超过 `max_diff_px`，则 soft-fail 并人工 review'
VISUAL_UNKNOWN = '🔑 **若基线不可知，则 `T_min/T_max` 不填，'
'🔴 只产出 `observed_durations.json` 而非伪造 PASS**'

AUDIO_RULE = '🔑 **音频验证分三层，不应让指纹库承担它不擅长的任务。**'
AUDIO_3 = [
    ('指纹', '官方定位是**识别近相同音频**、追求紧凑指纹与搜索速度，'
     '🔴 **明确不是 general-purpose fingerprint**；'
     '🔑 应先按**时间窗切段**比较相似度'),
    ('样本级', '记 **cross-correlation offset**'),
    ('特征', '频谱 · 节拍 · 响度（如 librosa）'),
]
AUDIO_WHY = '🔑 三层合用才能区分"**同一音乐、不同转码**"与"**完全不同 cue**"'
AUDIO_LICENSE = '⚠️ **Chromaprint 整体应视为 LGPL-2.1**（内嵌 FFmpeg 代码，'
'许可证文件提示外部 FFT 库会改变二进制许可）；'
'🔴 **项目若静态链接 FFmpeg/FFTW 必须做完整合规审查**'
AUDIO_ALT = '🔑 audfprint（MIT，地标指纹，适合片段检索与离线索引）；'
'🔑 OLAF（**AGPL-3.0**，轻量，支持嵌入式与 WASM，🔴 **官方 README 明确提示相关'
'美国专利风险**）；'
'🔴 Dejavu 原仓库陈旧，活跃分支只作研究对比，不能作为唯一生产主键；'
'🔑 librosa（ISC）适合相似度分析而非替代音频哈希'

PHOTO_RULE = '🔑 **物理表面以可复核尺度为 must-match，不以艺术化照片为 '
'must-match。**'
PHOTO_ITEMS = '每处拍摄用**已知尺寸色卡/参考尺 · ArUco 或 CCTag 标记 · '
'镜头 EXIF · 固定光照**；'
'记 **camera pose · 镜头畸变 · 色卡 patch 的 measured LAB · 标称与实测尺寸**'
PHOTO_TOOLS = [
    ('COLMAP', 'BSD，SfM/MVS 通用流程，可处理有序或无序照片'),
    ('AliceVision', 'MPL-2.0，摄影测量框架，支持 SfM · MVS · HDR · RAW · 相机跟踪'),
    ('OpenCV', 'Apache-2.0，标定 · 检测 · 位姿；🔴 **独立 aruco 包常见 GPL-3.0 实现，'
     '具体依赖组合需在构建时核对**'),
    ('darktable', 'GPL，RAW 显影与色彩归档，🔴 **不是 3D 测量引擎**'),
]
PHOTO_CAUTION = '🔴 **Meshroom 本轮未确认确切许可证**，'
'只能作为 AliceVision 的实验前端，正式分发前需从仓库再次核实许可证与第三方依赖'

JOIN_SCHEMA = ['global_sample_clock_ns', 'capture_device_id',
               'media_kind ∈ {video,audio,photo,depth,annotation}',
               'state_machine', 'state', 'normalized_phase', 'asset_uri',
               'artifact_sha256', 'metric_name', 'metric_value', 'mask_id',
               'build_id']
JOIN_RULE = '🔑 **四路证据应合并成同一时间轴事件流**：'
'采集器先写 raw event log，再由 joiner 按 '
'`[build_id, global_sample_clock_ns]` 合并'
JOIN_NO = '🔑 调试 trace（DOM snapshot · 网络请求 · 控制台日志 · 截图）'
'🔴 **不应冒充图形 baseline**；'
'截图 · 视频 · 音频应进入**不可变对象存储**'
JOIN_REPORT = '🔑 最终报告显示同一时刻的**视频 diff heatmap · 音频指纹匹配 · '
'3D/照片标定状态 · 状态机迁移**；'
'🔑 **任何人工批准必须记 reviewer · 旧 baseline hash · 新 baseline hash · 偏离理由**'

CONFLICTS = [
    '❌ **只有"原版/复刻版"两栏的构建矩阵**（应展开为 engine×platform×'
    'renderer×build_id）',
    '❌ **baseline 与测试在不同环境/不同 headless 模式生成**',
    '❌ **基线不可知却伪造 PASS**（应产出 observed_durations.json）',
    '❌ 用整屏 diff 检测循环内容 / 用逐帧 diff 断言离散屏',
    '❌ **让指纹库承担通用比对任务**；不按时间窗切段',
    '❌ 静态链接 FFmpeg/FFTW 而不做 LGPL 合规审查',
    '❌ **以艺术化照片为 must-match**（应以可复核尺度）',
    '❌ **把调试 trace 当图形 baseline**',
    '❌ 人工批准不记 reviewer 与新旧 baseline hash',
]

FIELDS = [
    ('lane', '路（clock / visual / audio / photo / join）'),
    ('item', '项'),
    ('legacy_value', '**原版值**'),
    ('new_value', '新引擎值'),
    ('match', '**是否一致**'),
    ('artifact_sha256', '**产物哈希**（可复核）'),
    ('evidence', '证据等级 1-8'),
]
LANES = ['clock', 'visual', 'audio', 'photo', 'join']


def _hdr(t, w=80):
    print('=' * w)
    print(t)
    print('=' * w)


def cmd_clock(a):
    _hdr('🔑 统一时钟（**比像素阈值更重要**）')
    print(f'   {CLOCK_RULE}')
    print(f'\n命名规范: {CLOCK_NAMING}')
    for k, v in CLOCK_ITEMS:
        print(f'   · {k}: {v}')
    print(f'\n   {CLOCK_ENV}')
    print(f'\n   {CLOCK_MATRIX}')
    return 0


def cmd_visual(a):
    _hdr('截图 diff（**整屏 vs 逐帧**）')
    print(f'   {VISUAL_RULE}')
    for k, v in VISUAL_ITEMS:
        print(f'\n   【{k}】\n      {v}')
    print(f'\n   {VISUAL_CHAIN}')
    print(f'\n   {VISUAL_PREDICATE}')
    print(f'\n   {VISUAL_UNKNOWN}')
    return 0


def cmd_audio(a):
    _hdr('音频（**三层验证**）')
    print(f'   {AUDIO_RULE}')
    for k, v in AUDIO_3:
        print(f'\n   【{k}】\n      {v}')
    print(f'\n   {AUDIO_WHY}')
    print(f'\n   {AUDIO_LICENSE}')
    print(f'\n   {AUDIO_ALT}')
    return 0


def cmd_photo(a):
    _hdr('物理表面（**可复核尺度**）')
    print(f'   {PHOTO_RULE}')
    print(f'\n   {PHOTO_ITEMS}')
    for k, v in PHOTO_TOOLS:
        print(f'\n   【{k}】\n      {v}')
    print(f'\n   {PHOTO_CAUTION}')
    return 0


def cmd_join(a):
    _hdr('四路合并（**同一时间轴事件流**）')
    print(f'   {JOIN_RULE}')
    print('\nschema: ' + ' · '.join(JOIN_SCHEMA))
    print(f'\n   {JOIN_NO}')
    print(f'\n   {JOIN_REPORT}')
    return 0


def cmd_init(a):
    os.makedirs(os.path.dirname(a.init) or '.', exist_ok=True)
    with open(a.init, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow([k for k, _ in FIELDS])
        for ln in LANES:
            w.writerow([ln, 'TODO', 'TODO', 'TODO', '', '', ''])
    print(f'已生成四路验收表: {a.init}（{len(LANES)} 路骨架）')
    print('\n⚠️ `artifact_sha256` 是**可复核**的关键列，缺失即无法重放')
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

    lanes = {g(r, 'lane') for r in rows}
    missing = [x for x in LANES if x not in lanes]
    mismatch, no_hash, no_grade = [], [], []
    for i, r in enumerate(rows, 1):
        if g(r, 'match').lower() not in ('yes', 'y', 'true', '是', '一致'):
            mismatch.append(i)
        if not g(r, 'artifact_sha256'):
            no_hash.append(i)
        ev = g(r, 'evidence')
        if not ev or ev == 'TODO':
            no_grade.append(i)
        else:
            d = ev.split('.')[0].strip()
            if d.isdigit() and int(d) >= 7:
                no_grade.append(i)

    print('=' * 76)
    print(f'四路验收层 · {len(rows)} 条 / 需覆盖 {len(LANES)} 路')
    print('=' * 76)
    if missing:
        print(f'\n🚫 **未覆盖路** {len(missing)}: {missing}')
    if mismatch:
        print(f'\n🚫 **不一致** {len(mismatch)} 条（行 {mismatch[:15]}）')
    if no_hash:
        print(f'\n🚫 {len(no_hash)} 条**缺产物哈希**（行 {no_hash[:15]}）—— '
              '🔴 **无法重放**')
    if no_grade:
        print(f'\n🚫 {len(no_grade)} 条**证据等级缺失或 ≥7 级**'
              f'（行 {no_grade[:15]}）')
    if not (missing or mismatch or no_hash or no_grade):
        print('\n✅ 四路验收层：路齐全、一致、产物可哈希复核、证据达标')

    print('\n🔑 **统一时钟比统一像素阈值更重要。**')
    print('   🔑 **整屏 diff 用于状态边界，逐帧 diff 用于循环内容。**')
    print('   🔴 **基线不可知就产出 observed_durations.json，不要伪造 PASS。**')
    return 1 if (a.gate_check and
                 (missing or mismatch or no_hash or no_grade)) else 0


def main():
    ap = argparse.ArgumentParser(description='四路验收接入')
    ap.add_argument('--clock', action='store_true')
    ap.add_argument('--visual', action='store_true')
    ap.add_argument('--audio', action='store_true')
    ap.add_argument('--photo', action='store_true')
    ap.add_argument('--join', action='store_true')
    ap.add_argument('--init')
    ap.add_argument('--check')
    ap.add_argument('--gate-check', action='store_true')
    a = ap.parse_args()
    fns = {'clock': cmd_clock, 'visual': cmd_visual, 'audio': cmd_audio,
           'photo': cmd_photo, 'join': cmd_join}
    for k, fn in fns.items():
        if getattr(a, k):
            return fn(a)
    if a.init:
        return cmd_init(a)
    if a.check:
        return cmd_check(a)
    print('❌ 需要 --clock / --visual / --audio / --photo / --join '
          '/ --init / --check 之一')
    return 2


if __name__ == '__main__':
    sys.exit(main())
