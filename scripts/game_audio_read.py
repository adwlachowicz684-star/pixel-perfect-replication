#!/usr/bin/env python3
"""音频空间传播 + 视觉可读性（第十一轮 A / B 类）。

**🔑 A 类核心**：
> **音频不是音量、衰减和 HRTF 三件事，而是一条可分解的传播路径。**
> 每个 3D 声源拆成**七条通道**，每条单独记录频率响应、增益、到达时间、
> 低通截止、声道间相关性、空间化、延迟和发送量。
>
> 🔴 **最致命的误判是"听不见就设为静音"** —— 原作可能让直达声完全消失，
> 却保留少量衍射或透射声；也可能在最大距离后停播 event，
> 但**环境 reverb tail 仍在延续**。

**🔑 B 类核心**：
> **画质参数不能证明玩家能看清目标。**
> 可读性应直接测量"**前景与背景在玩家会看的位置是否可分离**"。

用法:
  game_audio_read.py --propagation  # 🔴 七条传播通道
  game_audio_read.py --attenuation  # 距离衰减与**是否完全静音**
  game_audio_read.py --occlusion    # 遮挡**分通道**（直达/透射/衍射）
  game_audio_read.py --reverb       # 🔴 混响区切换是**声音版隐形墙**
  game_audio_read.py --doppler      # 多普勒/声速/介质
  game_audio_read.py --surface      # 脚步**双向材质查询**
  game_audio_read.py --voice        # 🔴 抢占须成为**可回放事件流**
  game_audio_read.py --readability  # 🔴 可读性采样（不是"有没有轮廓光"）
  game_audio_read.py --highlight    # 高亮核心是**状态条件**
  game_audio_read.py --priority     # 视觉优先级**四层竞争**
  game_audio_read.py --exposure     # 曝光/gamma/HDR 破坏可读性
  game_audio_read.py --init ledger/audio_read.csv
  game_audio_read.py --check ledger/audio_read.csv --gate

退出码: 0 通过 / 1 缺项 / 2 用法错误
"""
import argparse
import csv
import os
import sys

# 🔴 七条传播通道
PROPAGATION_CHANNELS = [
    "direct", "**diffracted_direct**", "**transmitted_through**",
    "early_reflection", "**late_reverb_send**",
    "**media_transition**", "**propagation_delay**",
]

PROPAGATION_RULE = [
    "🔑 每条通道单独记录：频率响应 · 增益 · **相位/到达时间** · 低通截止 · "
    "声道间相关性 · 空间化 · 延迟 · 发送量",
    "🔴 若只记「event—bus—mixer—Loudness—voice stealing」，会把"
    "**绕过门缝的微弱直达声、早期反射、卷积混响尾巴、门后低通混为一谈**",
    "🔴 **`mute_at_max_distance` 必须独立记录，不能从 `max_distance` 推导**",
]

# 衰减
ATTEN_FIELDS = [
    "**attenuation_curve_type**（custom / logarithmic / linear / reverse）",
    "min_distance", "max_distance", "**min_gain_not_zero**",
    "**zero_after_max**", "**custom_curve_samples**",
    "listener_relative_or_source_relative", "spread_angle",
    "center_percent", "**doppler_scaler**",
    "**distance_attenuation_lowpass**",
]

ATTEN_RULE = "🔑 **距离剔除是调用层预算，voice limit 是运行时抢占** —— "
"**二者不可合并成一个布尔**"

# 遮挡分通道
OCCLUSION_FIELDS = [
    "rays", "first_hit_only", "nearest_path",
    "**accumulated_path_fraction**", "wall_thickness_heuristic",
    "**lowpass_cutoff_curve_by_path**", "**gain_curve_by_path**",
    "high_frequency_absorber", "directional_occluder",
]

DIFFRACTION_FIELDS = [
    "diffraction_angle", "wedge_index", "**order_limit**",
    "path_visibility", "**direct_path_lost**", "diffracted_gain",
    "diffracted_lpf", "**portal_path_count**", "**portal_open_ratio**",
    "portal_transmission",
]

OCCLUSION_TESTS = [
    "双墙", "单墙", "**门缝**", "薄板", "开放洞口", "**听众站在洞口**",
]

OCCLUSION_NOTE = [
    "🔑 同一声源在**薄板后**可能保留高频，在**厚石墙后**只留低通尾巴，"
    "**门打开时还可能发生房间耦合突变**",
    "🔑 must-match 不只是音量 —— 还包括**路径切换是否产生可听 pop**",
    "🔑 因此要记 `send_smoothing_time` · `gain_ramp` · `filter_ramp` · "
    "`reverb_blend_ramp` · **`path_change_debounce`**",
]

# 🔴 混响区
REVERB_FIELDS = [
    "zone_id", "affects_direct_send", "wet_gain", "eq_low/mid/high",
    "decay_time", "pre_delay", "density", "diffusion", "early_delay",
    "**hrtf / ambisonics_order**", "binaural_rendering", "room_tone_loop",
    "**transition_time**", "**transition_curve**",
    "**listener_both_feet_rule**",
]

REVERB_RULE = [
    "🔴 **混响区切换是声音版的「隐形墙**」 —— "
    "**过渡参数比混响名字更重要**",
    "❌ 不要只导出「走廊使用大厅混响」",
    "🔑 要记**玩家半身跨过边界** · 跳跃 · 坐载具 · 贴墙 · 洞口 · 门打开",
    "🔑 原作可能对**脚部/头部/相机位置或最大贡献房间**投票 —— "
    "复刻改成中心点采样最容易出现「**身体一半在室外却仍听室内**」",
    "🔑 `transition_curve` 至少存 **8–16 个归一化样本**，"
    "并记录平滑作用在 gain / filter / send / **卷积 IR 混合系数**上",
]

# 多普勒与介质
DOPPLER_FIELDS = [
    "doppler_scale", "source_velocity_inclusion",
    "listener_velocity_inclusion", "clamp_speed",
    "**fixed_speed_of_sound / per_medium_speed**",
]

DOPPLER_TESTS = [
    "低速载具", "**超音速**", "**瞬间传送**", "**时间缩放**", "**倒放**",
]

MEDIA_RULES = [
    "真空: `direct_muted` · `only_transmission/vibration_path` · "
    "**`subtitles_retained`**",
    "水下: `underwater_bus_snapshot` · `air_bubble_above_water_cutoff` · "
    "`surface_interface` · **camera/head/torso_rule** · `reverb_override` · "
    "`lowpass_highpass_chain`",
    "隔墙: **「听墙振动」是否由独立 event 而非滤波器生成**",
]

# 脚步：双向材质查询
SURFACE_FIELDS = [
    "surface_material_id", "**footwear_id**", "**contact_velocity_bin**",
    "gait_phase", "impact_normal", "tire/paw/tail_flag", "variation_seed",
    "one_shot_or_scrape", "**scrape_pitch_from_slip_speed**",
    "distance_attenuation_id",
]

SURFACE_RULE = [
    "🔑 是**双向材质查询**，不是单张脚步表",
    "🔑 滚动/撞击/摩擦/布料/链条应分别记接触 pair 的**主材质、次材质、"
    "硬度、粗糙度、厚度、空腔、频率吸收** —— 避免只用「金属」「石头」一个标签",
]

# 🔴 voice 抢占
VOICE_FIELDS = [
    "explicit_priority", "category", "max_instances", "importance",
    "**distance_importance_weight**", "**play_time_bias**",
    "**emergency_flag**", "ducking_targets", "**virtual_voice_strategy**",
    "steal_oldest / lowest_priority / farthest / newest",
    "**fade_on_steal_ms**", "schedule_latency",
]

VOICE_EVENT = [
    "每次 voice 变化输出一行：",
    "  `frame · voice_id · event_id · state{queued, starting, virtual, "
    "playing, stopping, stolen, faded, killed} · reason · "
    "from_priority · to_priority`",
    "🔑 与原版同步播放，**逐 voice 标绿/红**",
    "🔑 特别检测：首次触发是否被延迟 · 抢占是否在音头 · "
    "**是否产生 click** · 同一事件是否去重 · **跨房间优先级是否异常**",
]

# 🔴 可读性
READABILITY_FIELDS = [
    "scene_id", "camera_transform_hash", "frametime", "object_id",
    "object_class", "target_status", "screen_position",
    "**screen_radius_px**", "depth",
    "luminance_fg_mean/max/min", "**luminance_bg_local_mean**",
    "**CIELAB_contrast**", "chroma_separation", "edge_length_ratio",
    "occlusion_ratio", "**silhouette_visible_ratio**",
    "outline_visible_ratio", "xray_visible", "hud_occlusion_ratio",
    "recording_session_hash",
]

READABILITY_RULE = [
    "🔑 关键指标**不是「有没有轮廓光」**，"
    "而是**目标轮廓在局部背景中的可见比例**",
    "🔑 用**局部背景环形采样**代替整屏平均亮度",
    "🔑 **按对象类别分层统计** —— 敌人、队友、可交互物、危险区、"
    "任务目标、可拾取物**不能共用一个阈值**",
]

READABILITY_PATHS = [
    "转身", "奔跑", "冲刺", "蹲下", "贴墙", "瞄准镜", "水下", "雨雾",
    "**逆光**", "**爆炸闪光**", "开门", "载具内", "变焦", "死亡回放",
]

RIM_FIELDS = [
    "rim_width_ndc/pixel", "rim_falloff", "shadow_occlusion_mask",
    "ao_suppression", "rim_color_mode", "sky_vs_bg_separation",
    "depth_fog_contribution", "exposure_influence",
]

RIM_NOTE = "🔑 若用后处理描边，需记是否**只在边缘检测后的细小轮廓上绘制** —— "
"避免手指、头发或铁丝网在超宽屏上变成**大面积实心线**"

# 高亮
HIGHLIGHT_FIELDS = [
    "trigger_volume_type", "min_interactable_angle", "facing_rule",
    "line_of_sight_rule", "max_distance_2d/3d", "height_bias",
    "occluder_layer", "**visible_when_occluded**", "**xray_stencil_rule**",
    "xray_pulse_frequency", "fill_alpha", "outline_width", "distance_fade",
    "**group_aggregation**", "prioritize_nearest/most_relevant",
    "transition_in/out_ms", "**look_at_dwell_time**", "multitarget_cycle_input",
]

HIGHLIGHT_TESTS = [
    "半透明玻璃", "粒子", "栅栏", "门", "**自身身体**", "队友", "HUD",
]

HIGHLIGHT_NOTE = [
    "🔑 原作可能让**被门完全遮挡的按钮不可见**，"
    "但让**被墙半挡的任务物品仍显示 x-ray**",
    "🔑 也可能只在「已可交互」状态显示，**按住交互键后切换为另一套样式**",
]

# 视觉优先级四层
PRIORITY_LAYERS = [
    "**攻击预警**", "**即时危险**", "**任务目标**", "**可拾取物**",
]

PRIORITY_MEANS = [
    "图标", "颜色", "脉冲", "描边", "**屏幕边缘箭头**", "距离环", "缩放",
    "镜头缩进", "FoV 压缩", "镜头聚焦", "DoF 焦点", "暗角", "色相偏移", "音效",
]

HAZARD_FIELDS = [
    "indicator_appear_lead_time", "warn_phase_duration",
    "active_phase_duration", "**damage_commit_frame**",
    "indicator_relative_to_hazard", "**player_owned_hazard_exception**",
    "offscreen_arrow_screen_margin",
]

HAZARD_RULE = [
    "🔑 攻击预警存在两种失败：**「看得见但读不懂」**与**「读得懂但太晚**」",
    "🔑 必须**同时测量首次可识别时间与反应可用时间**",
]

# 曝光
EXPOSURE_FIELDS = [
    "target_mid_grey", "min_exposure", "max_exposure",
    "**adapt_speed_up/down**", "histogram_black_clip", "white_clip",
    "calibration", "tonemapper", "**shadow_lift**", "ambient_boost",
    "local_contrast", "highlight_roll_off", "**ui_layer_exposure_rule**",
]

EXPOSURE_NOTE = [
    "🔑 测试**阴影中的敌人**与**逆光人脸**",
    "🔑 原作可能给重要角色保留**自身补光**，或给敌人轮廓叠加"
    "**不受曝光影响的标识**",
    "🔴 若复刻把标识也送入 ACES/Reverse Tone Map，"
    "**HDR 显示器上可能过曝消失**",
]

UI_READABILITY = [
    "ui_layer_color_space", "**max_nits_cap**", "ui_exposure_isolated",
    "safe_area_nits", "small_text_min_nits_contrast",
    "motion_blur_exemption", "depth_of_field_exemption",
    "camera_shake_exemption", "lens_flare_over_ui_rule",
]

UI_NOTE = "⚠️ WCAG 的 4.5:1 与 3:1 只能作为**非游戏文本的参考基线**，"
"**不是像素级 must-match 值**"

CONFLICTS = [
    "❌ **「真实波传播一定优于手工区域」** —— 原作可能是美术驱动",
    "❌ **一个 occlusion 值统一处理墙、门、洞口** —— 频率、路径、发送通道不同",
    "❌ **距离大于 max 就静音** —— 混响尾或环境声可能仍播放",
    "❌ 只记录 reverb preset 名 —— 引擎版本与 IR 可造成显著差异",
    "❌ **按 priority 排序后直接停掉旧 voice** —— 可能制造 click、错杀关键反馈",
    "❌ 可读性只看「有没有轮廓光」",
    "❌ 各类目标共用一个可读性阈值",
    "❌ 把标识送入 tonemapper —— HDR 下可能过曝消失",
    "❌ 把 WCAG 对比度当 must-match 值",
]

FIELDS = [
    ("item_id", "项编号"),
    ("domain", "域（propagation / attenuation / occlusion / reverb / doppler / surface / voice / readability / highlight / priority / exposure）"),
    ("legacy_value", "**原版值**"),
    ("new_value", "新引擎值"),
    ("match", "**是否一致**"),
    ("evidence", "证据"),
]


def _hdr(t, w=80):
    print("=" * w)
    print(t)
    print("=" * w)


def cmd_propagation(a):
    _hdr("🔴 音频七条传播通道")
    for c in PROPAGATION_CHANNELS:
        print(f"   · {c}")
    print("\n规则:")
    for r in PROPAGATION_RULE:
        print(f"   {r}")
    return 0


def cmd_attenuation(a):
    _hdr("距离衰减")
    for f in ATTEN_FIELDS:
        print(f"   · {f}")
    print(f"\n   {ATTEN_RULE}")
    return 0


def cmd_occlusion(a):
    _hdr("遮挡（**分通道**）")
    print("occlusion: " + " · ".join(OCCLUSION_FIELDS))
    print("\ndiffraction: " + " · ".join(DIFFRACTION_FIELDS))
    print("\n测试: " + " · ".join(OCCLUSION_TESTS))
    print("\n注意:")
    for n in OCCLUSION_NOTE:
        print(f"   {n}")
    return 0


def cmd_reverb(a):
    _hdr("🔴 混响区（**声音版隐形墙**）")
    for f in REVERB_FIELDS:
        print(f"   · {f}")
    print("\n规则:")
    for r in REVERB_RULE:
        print(f"   {r}")
    return 0


def cmd_doppler(a):
    _hdr("多普勒 / 声速 / 介质")
    print("字段: " + " · ".join(DOPPLER_FIELDS))
    print("\n测试: " + " · ".join(DOPPLER_TESTS))
    print("\n介质:")
    for m in MEDIA_RULES:
        print(f"   · {m}")
    return 0


def cmd_surface(a):
    _hdr("脚步与接触（**双向材质查询**）")
    for f in SURFACE_FIELDS:
        print(f"   · {f}")
    print("\n规则:")
    for r in SURFACE_RULE:
        print(f"   {r}")
    return 0


def cmd_voice(a):
    _hdr("🔴 voice 抢占（**可回放事件流**）")
    for f in VOICE_FIELDS:
        print(f"   · {f}")
    print("\n事件流:")
    for e in VOICE_EVENT:
        print(f"   {e}")
    return 0


def cmd_readability(a):
    _hdr("🔴 视觉可读性采样")
    for f in READABILITY_FIELDS:
        print(f"   · {f}")
    print("\n规则:")
    for r in READABILITY_RULE:
        print(f"   {r}")
    print("\n相机轨迹: " + " · ".join(READABILITY_PATHS))
    print("\nrim: " + " · ".join(RIM_FIELDS))
    print(f"\n   {RIM_NOTE}")
    return 0


def cmd_highlight(a):
    _hdr("可交互高亮（**状态条件，不是材质开关**）")
    for f in HIGHLIGHT_FIELDS:
        print(f"   · {f}")
    print("\n遮挡测试: " + " · ".join(HIGHLIGHT_TESTS))
    print("\n注意:")
    for n in HIGHLIGHT_NOTE:
        print(f"   {n}")
    return 0


def cmd_priority(a):
    _hdr("视觉优先级（**四层竞争**）")
    print("层次: " + " · ".join(PRIORITY_LAYERS))
    print("\n手段: " + " · ".join(PRIORITY_MEANS))
    print("\n危险区: " + " · ".join(HAZARD_FIELDS))
    print("\n规则:")
    for r in HAZARD_RULE:
        print(f"   {r}")
    return 0


def cmd_exposure(a):
    _hdr("曝光 / gamma / HDR（**共同破坏可读性**）")
    print("曝光: " + " · ".join(EXPOSURE_FIELDS))
    print("\n注意:")
    for n in EXPOSURE_NOTE:
        print(f"   {n}")
    print("\nHUD: " + " · ".join(UI_READABILITY))
    print(f"\n   {UI_NOTE}")
    return 0


def cmd_init(a):
    os.makedirs(os.path.dirname(a.init) or ".", exist_ok=True)
    with open(a.init, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow([k for k, _ in FIELDS])
        w.writerow(["TODO"] * len(FIELDS))
    print(f"已生成音频/可读性表: {a.init}")
    print("\n⚠️ 十一域：propagation / attenuation / occlusion / reverb / "
          "doppler / surface / voice / readability / highlight / priority / exposure")
    return 0


def cmd_check(a):
    if not os.path.exists(a.check):
        print(f"❌ 文件不存在: {a.check}")
        return 2
    with open(a.check, encoding="utf-8", errors="replace", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        print("❌ 空表")
        return 1

    def g(r, k):
        return (r.get(k) or "").strip()

    mismatch, no_legacy = [], []
    for i, r in enumerate(rows, 1):
        m = g(r, "match").lower()
        if m not in ("yes", "y", "true", "是", "一致"):
            mismatch.append(i)
        if not g(r, "legacy_value") or g(r, "legacy_value") == "TODO":
            no_legacy.append(i)

    print("=" * 76)
    print(f"音频/可读性 · {len(rows)} 条")
    print("=" * 76)
    if mismatch:
        print(f"\n🚫 **不一致** {len(mismatch)} 条（行 {mismatch[:15]}）")
    if no_legacy:
        print(f"\n❌ {len(no_legacy)} 条缺**原版值**（行 {no_legacy[:15]}）")

    if not (mismatch or no_legacy):
        print("\n✅ 音频/可读性：一致且原版值完整")

    print("\n🔑 **听不见 ≠ 设为静音** —— reverb tail 可能仍在延续。")
    print("   **混响区切换是声音版的隐形墙**，过渡参数比混响名字更重要。")
    print("   **可读性不是「有没有轮廓光」，是目标在局部背景中的可见比例。**")
    return 1 if (a.gate and (mismatch or no_legacy)) else 0


def main():
    ap = argparse.ArgumentParser(description="音频传播与视觉可读性")
    ap.add_argument("--propagation", action="store_true")
    ap.add_argument("--attenuation", action="store_true")
    ap.add_argument("--occlusion", action="store_true")
    ap.add_argument("--reverb", action="store_true")
    ap.add_argument("--doppler", action="store_true")
    ap.add_argument("--surface", action="store_true")
    ap.add_argument("--voice", action="store_true")
    ap.add_argument("--readability", action="store_true")
    ap.add_argument("--highlight", action="store_true")
    ap.add_argument("--priority", action="store_true")
    ap.add_argument("--exposure", action="store_true")
    ap.add_argument("--init")
    ap.add_argument("--check")
    ap.add_argument("--gate", action="store_true")
    a = ap.parse_args()
    fns = {"propagation": cmd_propagation, "attenuation": cmd_attenuation,
           "occlusion": cmd_occlusion, "reverb": cmd_reverb,
           "doppler": cmd_doppler, "surface": cmd_surface,
           "voice": cmd_voice, "readability": cmd_readability,
           "highlight": cmd_highlight, "priority": cmd_priority,
           "exposure": cmd_exposure}
    for k, fn in fns.items():
        if getattr(a, k):
            return fn(a)
    if a.init:
        return cmd_init(a)
    if a.check:
        return cmd_check(a)
    print("❌ 需要 --propagation / --attenuation / --occlusion / --reverb / "
          "--doppler / --surface / --voice / --readability / --highlight / "
          "--priority / --exposure / --init / --check 之一")
    return 2


if __name__ == "__main__":
    sys.exit(main())
