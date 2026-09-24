#!/usr/bin/env python3
"""感知性能 + 环境交互手感 + 拍摄回放（第十一轮 C / D / E 类）。

**🔑 C 类核心**：
> **平均帧率和平均延迟不足以定验收线。**
> 输入延迟**没有脱离任务和设备的一刀切阈值**。
>
> 结论应是：先做原作**跨硬件测量**，再建立
> "可见差异—不可接受差异—平台档位预算"**三级标准**，
> 而不是搬运一个常数。

**🔑 D 类核心**：
> 环境交互必须建模成**多阶段过程状态机** ——
> 显式记录**能否中途取消、取消后回退到哪一帧、碰撞是否临时缩放、
> 手与世界对象谁拥有父级**。

**🔑 E 类核心**：
> 拍照模式要建模"**何时冻结、冻结什么、谁控制时间**"；
> 回放**不是录屏，也不只是输入流**。

用法:
  game_perf_interact.py --perf      # 🔴 端到端延迟与帧间隔分布
  game_perf_interact.py --latency   # 逐段预算（**不含一刀切阈值**）
  game_perf_interact.py --jit       # 🔴 抖动 vs 平均低帧率
  game_perf_interact.py --loading   # 加载等待的**可交互性**
  game_perf_interact.py --door      # 🔴 门/抽屉**可否中途取消**
  game_perf_interact.py --carry     # 拾取拖拽的重量感与**放下行为**
  game_perf_interact.py --break     # 可破坏物**阶段与碎片**
  game_perf_interact.py --vehicle   # 载具**操作反馈**（非物理）
  game_perf_interact.py --inspect   # 世界内检视
  game_perf_interact.py --photo     # 🔴 拍照模式冻结什么
  game_perf_interact.py --replay    # 回放**三种来源**
  game_perf_interact.py --init ledger/perf_interact.csv
  game_perf_interact.py --check ledger/perf_interact.csv --gate

退出码: 0 通过 / 1 缺项 / 2 用法错误
"""
import argparse
import csv
import os
import sys

# 🔴 端到端延迟
LATENCY_SEGMENTS = [
    "usb_poll_phase", "os_input_queue", "engine_input_system",
    "**input_buffering_decision**", "simulation", "animation_commit",
    "camera_update", "gpu_recording", "present", "display_scanout",
    "photon_exit", "photon_arrival",
]

LATENCY_TASKS = [
    "移动", "旋转", "UI", "菜单", "载具", "瞄准", "**慢动作**",
]

LATENCY_RULE = [
    "🔑 **同一总延迟在不同输入通道的容忍度不同** —— 分任务测量",
    "🔑 用**光电二极管/高速摄像**对可控灯或画面边角事件校准",
    "🔴 鼠标交互研究**明确反驳了「100 ms 足够快」的泛化结论** —— "
    "**低于 100 ms 的延迟可被感知**",
    "⚠️ 动作游戏服务器日志观察到玩家偏好 150–180 ms 以内 —— "
    "但这只是**网络选择行为**，不能当成人机交互阈值",
]

# 帧间隔分布
JITTER_FIELDS = [
    "**frame_interval_p50 / p95 / p99**", "**max_stall_ms**",
    "stall_count_per_minute", "**interval_histogram**",
    "dropped_frame_policy", "**frame_time_vs_interval**",
]

JITTER_RULE = [
    "🔑 **抖动 vs 平均低帧率，哪个更难受** —— 必须实测，不能假设",
    "🔑 记录**停顿次数/分钟**比平均帧率更能反映感知",
]

# 加载
LOADING_FIELDS = [
    "**是否有可交互元素**", "进度条真实性（见 game_social_meta --progress）",
    "**着色器首次编译的等待体验**", "首启动资源准备",
    "**编译卡顿是否可预测/可预编译**", "最小显示时间", "取消语义",
]

LOADING_RULE = "🔑 卡顿的**可预测性**本身就是体验 —— "
"突发卡顿比稳定低帧率更恼人"

# 🔴 门/抽屉
DOOR_STATES = [
    "closed", "opening", "**held**", "open", "closing",
    "**cancelled_partial**", "**latched**",
]

DOOR_FIELDS = [
    "开合动画", "**阻力**", "**吸附**", "音效",
    "**是否可中途取消**", "**取消后回退到哪一帧**",
    "**是否保留当前角速度**", "**吸附到最近槽位还是回滚**",
    "**碰撞是否临时缩放**", "**连锁触发**",
]

DOOR_RULE = "🔑 **热更新八态不覆盖门开合中途被中断后应如何处理** —— "
"这是独立的交互过程状态机"

# 拾取拖拽
CARRY_FIELDS = [
    "**重量感**", "惯性", "碰撞", "**吸附到手**", "**放下行为**",
    "**手与世界对象谁拥有父级**", "双手 vs 单手",
    "**放下时是自由落体、轻放还是吸附到地面**",
    "**超重时的表现**（拖行 / 掉落 / 无法拿起）",
    "**切换手持物时的过渡**",
]

# 可破坏物
BREAK_STATES = [
    "intact", "cracked_1/2/3", "breaking", "fractured_physics_active",
    "settling", "stable_rubble", "**partial_repaired**",
]

BREAK_FIELDS = [
    "damage_accumulator", "**debris_seed**", "**detach_order**",
    "constraint_break_force", "impulse_threshold",
    "impact_direction_inheritance", "ragdoll_transfer",
    "sound_pre_break_rumble", "**first_fracture_frame**",
    "**last_piece_settle_frame**", "**debris_pool_exhaustion_rule**",
    "destroyed_collider_layer", "**navmesh_carve**",
    "decoration_persistence", "**offscreen_culling_rule**",
]

BREAK_TESTS = [
    "拳头", "子弹", "爆炸", "载具", "火焰", "**环境伤害**",
]

BREAK_RULE = "🔑 测试同一个桶被上述手段破坏是否走**相同 phase**；"
"若只在进入模拟范围后才拆分 → **远处破坏会有可见 pop**，必须记录"

# 载具操作反馈
VEHICLE_FEEL = [
    "throttle_deadzone_curve", "brake_bias", "handbrake_lockup",
    "**gear_change_rumble_gain**", "engine_note_transmission_loss",
    "wheel_slip_audio_min_speed", "surface_material_blend",
    "**suspension_camera_bounce**", "steering_speed_ratio",
    "**counter_steer_assist**", "reverse_camera_switch", "horn_input_rule",
    "**exit_while_moving**", "**exit_velocity_inherit**",
]

VEHICLE_RULE = "🔑 它**不同于载具物理** —— 参数相同也可能因"
"**相机阻尼、音频延迟、力反馈、UI 换挡提示**不同而完全不同"

# 检视
INSPECT_FIELDS = [
    "inspect_input", "**rotation_axis_lock**", "inertia_decay",
    "zoom_min/max", "field_of_view", "background_dim", "lighting_override",
    "auto_center", "pan_distance_limit", "inspectable_collider_priority",
    "**original_transform_restore_rule**", "**pause_world_while_inspect**",
    "**affects_achievement_viewing_flag**",
]

INSPECT_RULE = [
    "🔑 若原作允许旋转但不允许缩放 · 允许双指缩放但禁用平移 · "
    "**检视时只暂停模拟而继续播放音乐** → 均须作为 must-match 字段",
    "❌ **不能用「通用检视组件」替换**",
]

# 🔴 拍照
PHOTO_FIELDS = [
    "activation_input", "**requires_game_paused**", "**simulation_mask**",
    "**animation_mask**", "**particles_mask**", "**physics_mask**",
    "audio_mask", "time_scale", "fixed_delta_pause", "camera_rig_id",
    "free_camera_collision", "**free_camera_speed_curve**", "boost_modifier",
    "min/max_distance_to_player", "min/max_fov", "focal_distance", "aperture",
    "bokeh", "exposure_lock", "white_balance", "vignette", "film_grain",
    "bloom", "chromatic_aberration", "**lut_asset_hash**",
    "character_pose_animations", "hide_hair_cap", "hide_helmet_rule",
    "**hide_ui**", "**hide_reticle**", "**hide_subtitles**",
    "hide_damage_vignette", "hide_photographer_weapon", "selfie_camera_rule",
    "depth_of_field_in_world", "water_reflection", "shadow_follow_free_camera",
    "capture_format", "super_resolution", "alpha_channel",
    "**screenshot_delay_frames**", "**metadata_rule**", "export_codec",
    "export_ui_state_hash",
]

PHOTO_EDGE = [
    "**拍照是否暂停敌人**", "时间冻结是否冻结粒子",
    "**隐藏 UI 是否仍显示任务箭头**", "暂停物理是否允许漂浮物继续",
    "**改变 FoV 是否影响后续武器准星**", "旋转角色时手持物是否换位",
    "导出 PNG/JPEG/HDR/EXR 是否保留元数据", "分享是否带滤镜和位置",
    "🔴 **是否改变随机种子 / 触发成就 / 跳过计时器 / 产生可恢复点**",
]

# 回放三种来源
REPLAY_KINDS = [
    ("video", "简单", "难做自由相机、时间倒流、教练模式、命中框、音频独立开关"),
    ("input_stream", "空间小", "**要求确定性**"),
    ("state_snapshot", "灵活", "**容易随机插值与新增实体**"),
]

REPLAY_FIELDS = [
    "replay_source_kind", "container", "codec",
    "**color_space / bit_depth / HDR_transfer**",
    "frame_rate_numerator/denominator", "audio_channels",
    "**ui_layer_track**", "**subtitle_track**", "killcam_source_frames",
    "seek_gop_rule", "**deterministic_replay_hash**", "engine_build_hash",
    "content_build_hash", "rng_rule", "scripting_vm_state_size",
    "network_clock_rule", "**input_poll_phase_rule**",
]

REPLAY_RULE = "🔑 三种方案的「**支持 UI 否**」必须在原作中**实测**，"
"**不能默认任一答案**"

HIGHLIGHT_AUTO = [
    "event_window_pre/post", "camera_candidate_score", "audio_sting",
    "slowmo_entry/exit", "player_visibility_rule", "obstruction_rule",
    "hud_overlay", "export_after_match", "user_edit_timeline",
]

CONFLICTS = [
    "❌ **搬运一个固定的延迟阈值常数** —— 应建三级标准而非抄数",
    "❌ 只看平均帧率 / 平均延迟",
    "❌ 假设抖动或平均低帧率哪个更难受 —— 必须实测",
    "❌ **用「通用检视组件」替换**",
    "❌ 把载具操作反馈与载具物理合并",
    "❌ 远距离可破坏物只在进模拟范围后拆分却不记录 pop",
    "❌ 拍照模式默认不改变状态 —— 可能改种子/触发成就/跳过计时器",
    "❌ 回放默认支持 UI —— 必须实测",
]

FIELDS = [
    ("item_id", "项编号"),
    ("domain", "域（perf / latency / jit / loading / door / carry / break / vehicle / inspect / photo / replay）"),
    ("legacy_value", "**原版值**"),
    ("new_value", "新引擎值"),
    ("match", "**是否一致**"),
    ("measured_on", "**实测硬件/平台**"),
    ("evidence", "证据"),
]


def _hdr(t, w=80):
    print("=" * w)
    print(t)
    print("=" * w)


def cmd_perf(a):
    _hdr("🔴 感知性能（**平均帧率不足以定验收线**）")
    print("逐段: " + " · ".join(LATENCY_SEGMENTS))
    print("\n分任务测量: " + " · ".join(LATENCY_TASKS))
    print("\n规则:")
    for r in LATENCY_RULE:
        print(f"   {r}")
    return 0


def cmd_latency(a):
    _hdr("输入到光子（**不含一刀切阈值**）")
    print("分段: " + " · ".join(LATENCY_SEGMENTS))
    print("\n三级标准: 可见差异 → 不可接受差异 → **平台档位预算**")
    print("\n规则:")
    for r in LATENCY_RULE:
        print(f"   {r}")
    return 0


def cmd_jit(a):
    _hdr("🔴 抖动 vs 平均低帧率")
    for f in JITTER_FIELDS:
        print(f"   · {f}")
    print("\n规则:")
    for r in JITTER_RULE:
        print(f"   {r}")
    return 0


def cmd_loading(a):
    _hdr("加载与等待")
    for f in LOADING_FIELDS:
        print(f"   · {f}")
    print(f"\n{LOADING_RULE}")
    return 0


def cmd_door(a):
    _hdr("🔴 门/抽屉（**可否中途取消**）")
    print("状态: " + " · ".join(DOOR_STATES))
    print("\n字段: " + " · ".join(DOOR_FIELDS))
    print(f"\n{DOOR_RULE}")
    return 0


def cmd_carry(a):
    _hdr("拾取与拖拽")
    for f in CARRY_FIELDS:
        print(f"   · {f}")
    return 0


def cmd_break(a):
    _hdr("可破坏物（**阶段与碎片**）")
    print("状态: " + " · ".join(BREAK_STATES))
    print("\n字段: " + " · ".join(BREAK_FIELDS))
    print("\n测试: " + " · ".join(BREAK_TESTS))
    print(f"\n{BREAK_RULE}")
    return 0


def cmd_vehicle(a):
    _hdr("载具操作反馈（**非物理**）")
    for f in VEHICLE_FEEL:
        print(f"   · {f}")
    print(f"\n{VEHICLE_RULE}")
    return 0


def cmd_inspect(a):
    _hdr("世界内检视")
    for f in INSPECT_FIELDS:
        print(f"   · {f}")
    print("\n规则:")
    for r in INSPECT_RULE:
        print(f"   {r}")
    return 0


def cmd_photo(a):
    _hdr("🔴 拍照模式（**冻结什么、谁控制时间**）")
    for f in PHOTO_FIELDS:
        print(f"   · {f}")
    print("\n边界:")
    for e in PHOTO_EDGE:
        print(f"   · {e}")
    return 0


def cmd_replay(a):
    _hdr("回放（**不是录屏，也不只是输入流**）")
    for k, pro, con in REPLAY_KINDS:
        print(f"   {k:<16} 优点: {pro:<8} 限制: {con}")
    print("\n字段: " + " · ".join(REPLAY_FIELDS))
    print(f"\n{REPLAY_RULE}")
    print("\n自动集锦: " + " · ".join(HIGHLIGHT_AUTO))
    print("\n⚠️ killcam 常使用**服务端快照或专用回滚缓存**，"
          "不一定与自由回放共享管线")
    return 0


def cmd_init(a):
    os.makedirs(os.path.dirname(a.init) or ".", exist_ok=True)
    with open(a.init, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow([k for k, _ in FIELDS])
        w.writerow(["TODO"] * len(FIELDS))
    print(f"已生成性能/交互表: {a.init}")
    print("\n⚠️ 十一域：perf / latency / jit / loading / door / carry / "
          "break / vehicle / inspect / photo / replay")
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

    mismatch, no_legacy, no_hw = [], [], []
    for i, r in enumerate(rows, 1):
        m = g(r, "match").lower()
        if m not in ("yes", "y", "true", "是", "一致"):
            mismatch.append(i)
        if not g(r, "legacy_value") or g(r, "legacy_value") == "TODO":
            no_legacy.append(i)
        hw = g(r, "measured_on")
        if not hw or hw == "TODO":
            no_hw.append(i)

    print("=" * 76)
    print(f"性能/交互 · {len(rows)} 条")
    print("=" * 76)
    if mismatch:
        print(f"\n🚫 **不一致** {len(mismatch)} 条（行 {mismatch[:15]}）")
    if no_legacy:
        print(f"\n❌ {len(no_legacy)} 条缺**原版值**（行 {no_legacy[:15]}）")
    if no_hw:
        print(f"\n⚠️  {len(no_hw)} 条**未记录实测硬件/平台**（行 {no_hw[:15]}）")
        print("   → 🔴 性能与延迟必须**跨硬件实测**，"
              "不能搬运阈值常数")

    if not (mismatch or no_legacy):
        print("\n✅ 性能/交互：一致且原版值完整")

    print("\n🔑 **门开合中途被中断后应停在哪，是独立的交互状态机。**")
    print("   **拍照模式可能改随机种子/触发成就 —— 必须记录。**")
    print("   **回放三种来源的「支持 UI 否」必须实测。**")
    return 1 if (a.gate and (mismatch or no_legacy)) else 0


def main():
    ap = argparse.ArgumentParser(description="感知性能与环境交互")
    ap.add_argument("--perf", action="store_true")
    ap.add_argument("--latency", action="store_true")
    ap.add_argument("--jit", action="store_true")
    ap.add_argument("--loading", action="store_true")
    ap.add_argument("--door", action="store_true")
    ap.add_argument("--carry", action="store_true")
    ap.add_argument("--break", dest="brk", action="store_true")
    ap.add_argument("--vehicle", action="store_true")
    ap.add_argument("--inspect", action="store_true")
    ap.add_argument("--photo", action="store_true")
    ap.add_argument("--replay", action="store_true")
    ap.add_argument("--init")
    ap.add_argument("--check")
    ap.add_argument("--gate", action="store_true")
    a = ap.parse_args()
    fns = {"perf": cmd_perf, "latency": cmd_latency, "jit": cmd_jit,
           "loading": cmd_loading, "door": cmd_door, "carry": cmd_carry,
           "brk": cmd_break, "vehicle": cmd_vehicle, "inspect": cmd_inspect,
           "photo": cmd_photo, "replay": cmd_replay}
    for k, fn in fns.items():
        if getattr(a, k):
            return fn(a)
    if a.init:
        return cmd_init(a)
    if a.check:
        return cmd_check(a)
    print("❌ 需要 --perf / --latency / --jit / --loading / --door / --carry / "
          "--break / --vehicle / --inspect / --photo / --replay / --init / "
          "--check 之一")
    return 2


if __name__ == "__main__":
    sys.exit(main())
