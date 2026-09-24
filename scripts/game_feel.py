#!/usr/bin/env python3
"""战斗反馈 juice + 移动手感与 traversal（第八轮 A / B 类）。

**🔑 A 类核心**：
> "打击感不一样"最常被归因于打击感整体，实际往往来自**某一项冻结域或曲线不一致**。

已确认的参数锚点：《层层梦境》复盘 —— 命中瞬间攻击者和被击中角色
定格约 **115 毫秒 / 约 7 帧**，**特效、相机和其他画面细节继续运行**，
停格使用自定义缓入缓出曲线。

> 🔴 简单把 `SetGlobalTimeDilation` 设成零会连 UI、镜头、粒子和音频一起冻住
> —— 这正是案例明确否定的方向，玩家会感知为"太僵"。

**🔑 B 类核心**：
> 平台手感由**多个跨帧窗口**共同决定，任何一项改成更"合理"的连续函数
> 都会改变**可跳过距离**。

用法:
  game_feel.py --hitstop    # 🔴 顿帧：**冻结谁**比冻结多久更重要
  game_feel.py --hitflash   # 闪白不是布尔，是**材质替换与恢复**
  game_feel.py --stagger    # 击退/硬直/霸体/韧性**同一受力图**
  game_feel.py --dmg        # 伤害数字：布局 + 运动 + 时间
  game_feel.py --shake      # 震屏与顿帧的**配合**
  game_feel.py --coyote     # 🔴 土狼时间是**有限有效窗口**
  game_feel.py --jumpbuf    # 跳跃缓冲是**过期输入如何被消耗**
  game_feel.py --varjump    # 可变跳跃高度**三类语义**
  game_feel.py --ground     # 落地/斜面/台阶/吸附八态
  game_feel.py --platform   # 移动平台**动量保留**
  game_feel.py --vehicle    # 载具/攀爬/mantle 的**所有权**
  game_feel.py --init ledger/game_feel.csv
  game_feel.py --check ledger/game_feel.csv --gate

退出码: 0 通过 / 1 缺项 / 2 用法错误
"""
import argparse
import csv
import os
import sys

# 🔴 顿帧
HITSTOP_SCOPES = [
    "player", "enemy", "projectile", "**vfx**", "**audio**",
    "**camera**", "ui", "physics", "anim_only",
]

HITSTOP_FIELDS = [
    "trigger_event", "**affected_scopes**", "duration_ms_at_60hz",
    "**scale_by_damage_curve**", "freeze_on_slow_motion",
    "enter_curve", "exit_curve", "**max_stack_policy**",
]

HITSTOP_MATRIX = [
    "🔑 `interruption_matrix`：同一帧多次命中如何叠加 —— "
    "取最大 / 刷新计时 / 忽略 / 相加",
    "🔴 一个持续多段攻击若每次命中都重置计时 → 玩家得到的是"
    "**「全程卡住」**，与只保留最大窗口完全不同",
]

HITSTOP_AUDIO = [
    "🔑 音频必须**显式分轨**：音乐 · 环境 · 对话 · **武器本体** · "
    "**命中点频** · UI",
    "❌ 不能只写「音频是否停止」 —— 同一游戏可能**停点频而保留环境**，"
    "也可能**只低通不暂停**",
]

HITSTOP_ANCHOR = [
    "📌 可复用锚点（《层层梦境》复盘）：约 **115 ms / 约 7 帧**，"
    "**只冻结攻击方与受击方**",
    "   视觉元素、摄像机和其他画面细节继续运行；停格用**自定义缓入缓出曲线**",
]

# 闪白
HITFLASH_FIELDS = [
    "闪白时长", "颜色", "**是否按亮度/色相分受伤类型**",
    "替换整个材质 / 叠加全屏 / **模型后处理**", "替换层数",
    "**受击结束后的恢复帧**", "多段命中是**重新触发还是延长**",
]

HITFLASH_STATES = [
    "普通", "格挡", "弱点", "暴击", "破防", "**无法受身**",
]

HITFLASH_RULE = [
    "🔑 命中颜色需与状态关联：各状态用不同**色相/饱和度/覆盖区域**",
    "⚠️ 若原项目只覆盖模型 silhouette，复刻为**全屏闪白**会误把风格放大",
    "⚠️ 若原项目替换材质且保留底色，复刻为**纯白叠加**会失去**体积感**",
    "⚠️ 材质替换要与**暂停、回放、截图模式兼容**，不能依赖临时全局材质",
]

# 击退/硬直/霸体/韧性
STAGGER_DIR = [
    "攻击方向", "攻击者朝向", "受击者朝向", "**受击点法线**", "角色重心",
]

STAGGER_MAG = [
    "基础力", "**重量**", "当前状态", "空中/地面", "面朝方向",
    "**动画根运动**", "**位移技能叠加**",
]

ARMOR_KINDS = [
    "**完全无视硬直**", "**只挡轻击**", "**减少 stun 但不挡位移**",
    "**免疫击退但不免疫硬直**",
]

ARMOR_RULE = "❌ **不能合并成一个 `super_armor: bool`**"

POISE_FIELDS = [
    "阈值", "**当前值**", "**恢复速率**", "**恢复延迟**",
]

POISE_RULE = [
    "🔑 否则无法区分「**连续攻击在阈值内触发**」与"
    "**受击恢复期间允许第二次打断**「",
]

# 伤害数字
DMG_FIELDS = [
    "出生锚点（命中盒中心 / **受击骨骼** / 头顶偏移）",
    "屏幕/世界投影", "**XY 随机半径**", "法线方向", "速度", "加速度",
    "阻尼", "持续时间", "缩放曲线", "颜色", "字体", "阴影", "描边",
    "**聚合键**", "**聚合窗口**", "聚合上限",
    "**暴击/格挡/治疗/护盾差异化**", "最大同屏数量",
    "远离相机自动缩小", "**重叠推挤**",
]

DMG_AGG = [
    "🔑 聚合最容易丢的是：**数字合并还是只延长**",
    "   · 同目标、同类型、同帧是否合并",
    "   · 是否只更新最高值或累加",
    "   · **暴击与普通命中能否合并**",
]

# 震屏与顿帧配合
SHAKE_COORD = [
    "震屏是否在冻结帧内冻结",
    "**冻结峰值还是冻结整个包络**",
    "震屏启动是否在顿帧**之后**",
    "顿帧恢复时是否保留**历史位移**",
    "多次命中如何**叠加包络**",
]

SHAKE_TEST = [
    "🔑 若原项目**只冻结角色而镜头继续** → 震屏可能在顿帧期间推进",
    "🔴 若复刻把整个 `WorldDelta` 冻结 → 震屏包络、音频播放头、粒子寿命"
    "会同步停滞 —— 玩家未必说得出为什么，但会明确感到**手感发死**",
]

# 🔴 土狼时间
COYOTE_MODES = [
    "last_grounded_timer", "post_ground_frames", "edge_query_window",
]

COYOTE_FIELDS = [
    "coyote_mode", "**window_ms_or_frames**", "refresh_on_grounded",
    "**excluded_states**", "visual_indicator",
]

COYOTE_RULE = [
    "🔑 常见实现**不是「检测离地帧」**，而是维护离开地面后的计时器或剩余有效帧",
    "🔑 重入地面是否清空 · 连续离开平台是否刷新 · "
    "**滑墙/蹬墙/梯子离开是否共享窗口** —— 逐状态配置",
    "🔴 若目标项目以 60Hz tick 设计，必须**同时记录 tick 数和实时毫秒** —— "
    "只写「约 0.1—0.2 秒」不足以验证 **30/60/120Hz 及可变帧率**的一致性",
]

# 跳跃缓冲
JUMPBUF_FIELDS = [
    "最早输入时刻", "最晚消耗时刻", "**可消耗动作集合**",
    "是否允许重复触发", "**落地帧立即消费还是下一固定步消费**",
    "被其他动作消费后是否退还", "**暂停期间计时器是否冻结**",
]

JUMPBUF_TRAPS = [
    "🔴 若缓冲输入在**菜单打开时保留并在关闭后触发** → 就是 bug",
    "🔴 若跳跃被攻击取消，**缓冲区是否继续保留** → 决定连招是否丢输入",
    "🔑 必须与现有输入缓冲合并 —— "
    "**不要把「方向序列」「技能队列」「跳跃宽限」分别实现成三套时间系统**",
]

# 可变跳跃：三类语义
VARJUMP_KINDS = [
    ("cut_velocity", "松开按钮时**截断上升速度**或施加额外重力"),
    ("hold_low_gravity", "按住期间**降低重力**"),
    ("cap_ascent", "限制**持续上升速度**"),
]

VARJUMP_FIELDS = [
    "最小/最大高度", "短按速度阈值", "**提前释放容忍**",
    "连续空中上升是否重新计时", "**下降重力是否与上升不同**",
    "撞到低矮障碍时剩余上升速度是否保留",
]

VARJUMP_RULE = "🔑 **三者手感不同，不能统称 variable jump**"

# 地面接触八态
GROUND_STATES = [
    "firm_ground", "slope_too_steep", "step_up", "ledge_grab_range",
    "slip_begin", "airborne", "coyote", "ground_pounding",
]

GROUND_FIELDS = [
    "**最大可走角度**", "滑落速度", "**贴地吸附距离**",
    "**射线/胶囊参数**", "台阶高度", "**着地判定的帧预测与物理接触选择**",
]

GROUND_RULE = [
    "⚠️ 这些会造成「**差一个像素上不去**」或「掉崖后被判定持续空中」",
    "⚠️ Godot 官方 2D 移动教程**只覆盖八方向、转向、鼠标朝向和点击移动** —— "
    "**不覆盖平台、地面检测、跳跃、空中控制或斜面**，把它当基线会严重漏项",
]

# 移动平台
PLATFORM_FIELDS = [
    "附着判定", "**相对坐标更新**", "**下平台速度继承**",
    "高速平台脱离", "角色与平台之间的**碰撞优先级**",
]

PLATFORM_TRANSITION = [
    "离开容差", "**相机先切还是角色先切**", "保留速度", "动画过渡",
    "目标落地点", "**房间加载边界**",
]

PLATFORM_TRAPS = [
    "🔴 若原项目允许**离墙数像素蹬墙跳**，复刻为必须紧贴墙面 → "
    "实质缩小可行操作空间",
    "🔴 若原项目只在特定平台保留移动平台动量，复刻为**统一继承** → "
    "在其他场景产生**穿墙或非法跳**",
]

# 载具/攀爬
VEHICLE_FIELDS = [
    "驾驶/乘坐座位", "进出动画", "相机切换", "**上下车空间查询**",
    "载具与角色碰撞", "**乘客是否独立受击**", "爆炸/翻车",
    "**退出速度继承**", "AI 临时驾驶",
]

CLIMB_FIELDS = [
    "抓握盒", "**边缘检测高度与法线**", "方向输入", "自动对齐",
    "落下恢复", "镜头碰撞",
]

MANTLE_FIELDS = [
    "可达性检测", "动画根运动", "**碰撞体开关**", "完成位置",
]

VEHICLE_AUTH = [
    "🔑 载具权威应归服务器/原引擎权威端，并同步速度、角速度、输入与物理状态",
    "🔴 否则回放会出现「**位置一致但弹跳轨迹不一致**」",
]

CONFLICTS = [
    "❌ **只调时间缩放实现顿帧** —— 全局冻住音频、粒子、镜头，违反最小干扰原则",
    "❌ **把霸体写成单个布尔** —— 无法表达挡轻击/挡硬直/挡位移/减伤的差异",
    "❌ **「连续力更真实」的默认角色控制器** —— 默认空气阻力、地面吸附和"
    "自动转向会抹掉原项目精细窗口",
    "❌ **用固定帧插值系数做转向/相机** —— 帧率变化时阻尼和相机跟随不一致，"
    "应使用**时间感知曲线**",
]

FIELDS = [
    ("item_id", "项编号"),
    ("domain", "域（hitstop / hitflash / stagger / dmg / shake / coyote / jumpbuf / varjump / ground / platform / vehicle）"),
    ("legacy_value", "**原版值**"),
    ("new_value", "新引擎值"),
    ("match", "**是否一致**"),
    ("frame_rate_tested", "**已实测帧率**（30/60/120/可变）"),
    ("evidence", "证据"),
]


def _hdr(t, w=80):
    print("=" * w)
    print(t)
    print("=" * w)


def cmd_hitstop(a):
    _hdr("🔴 顿帧 hit stop（**冻结谁比冻结多久更重要**）")
    for h in HITSTOP_ANCHOR:
        print(f"   {h}")
    print("\n冻结域: " + " · ".join(HITSTOP_SCOPES))
    print("\n字段: " + " · ".join(HITSTOP_FIELDS))
    print("\n叠加:")
    for m in HITSTOP_MATRIX:
        print(f"   {m}")
    print("\n音频:")
    for m in HITSTOP_AUDIO:
        print(f"   {m}")
    return 0


def cmd_hitflash(a):
    _hdr("受击闪白（**不是布尔**）")
    for f in HITFLASH_FIELDS:
        print(f"   · {f}")
    print("\n状态关联: " + " · ".join(HITFLASH_STATES))
    print("\n规则:")
    for r in HITFLASH_RULE:
        print(f"   {r}")
    return 0


def cmd_stagger(a):
    _hdr("击退 / 硬直 / 霸体 / 韧性（**同一受力图**）")
    print("方向由: " + " · ".join(STAGGER_DIR))
    print("幅度受: " + " · ".join(STAGGER_MAG))
    print("\n霸体至少区分:")
    for k in ARMOR_KINDS:
        print(f"   · {k}")
    print(f"\n   {ARMOR_RULE}")
    print("\n韧性必记: " + " · ".join(POISE_FIELDS))
    for r in POISE_RULE:
        print(f"   {r}")
    return 0


def cmd_dmg(a):
    _hdr("伤害数字（**布局 + 运动 + 时间**）")
    for f in DMG_FIELDS:
        print(f"   · {f}")
    print("\n聚合:")
    for d in DMG_AGG:
        print(f"   {d}")
    return 0


def cmd_shake(a):
    _hdr("震屏与顿帧的**配合**")
    for s in SHAKE_COORD:
        print(f"   · {s}")
    print("\n验证:")
    for t in SHAKE_TEST:
        print(f"   {t}")
    return 0


def cmd_coyote(a):
    _hdr("🔴 土狼时间 coyote time")
    print("模式: " + " · ".join(COYOTE_MODES))
    print("字段: " + " · ".join(COYOTE_FIELDS))
    print("\n规则:")
    for r in COYOTE_RULE:
        print(f"   {r}")
    return 0


def cmd_jumpbuf(a):
    _hdr("跳跃缓冲（**过期输入如何被消耗**）")
    for f in JUMPBUF_FIELDS:
        print(f"   · {f}")
    print("\n陷阱:")
    for t in JUMPBUF_TRAPS:
        print(f"   {t}")
    return 0


def cmd_varjump(a):
    _hdr("可变跳跃高度（**三类语义**）")
    for k, why in VARJUMP_KINDS:
        print(f"   {k:<20} {why}")
    print("\n字段: " + " · ".join(VARJUMP_FIELDS))
    print(f"\n{VARJUMP_RULE}")
    return 0


def cmd_ground(a):
    _hdr("地面接触八态")
    for s in GROUND_STATES:
        print(f"   · {s}")
    print("\n字段: " + " · ".join(GROUND_FIELDS))
    print("\n规则:")
    for r in GROUND_RULE:
        print(f"   {r}")
    return 0


def cmd_platform(a):
    _hdr("移动平台（**动量保留**）")
    print("字段: " + " · ".join(PLATFORM_FIELDS))
    print("\n转场: " + " · ".join(PLATFORM_TRANSITION))
    print("\n陷阱:")
    for t in PLATFORM_TRAPS:
        print(f"   {t}")
    return 0


def cmd_vehicle(a):
    _hdr("载具 / 攀爬 / mantle（**所有权**）")
    print("载具: " + " · ".join(VEHICLE_FIELDS))
    print("\n攀爬: " + " · ".join(CLIMB_FIELDS))
    print("\nmantle: " + " · ".join(MANTLE_FIELDS))
    print("\n权威:")
    for v in VEHICLE_AUTH:
        print(f"   {v}")
    return 0


def cmd_init(a):
    os.makedirs(os.path.dirname(a.init) or ".", exist_ok=True)
    with open(a.init, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow([k for k, _ in FIELDS])
        w.writerow(["TODO"] * len(FIELDS))
    print(f"已生成手感表: {a.init}")
    print("\n⚠️ 十一域：hitstop / hitflash / stagger / dmg / shake / "
          "coyote / jumpbuf / varjump / ground / platform / vehicle")
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

    mismatch, no_legacy, no_fps = [], [], []
    for i, r in enumerate(rows, 1):
        m = g(r, "match").lower()
        if m not in ("yes", "y", "true", "是", "一致"):
            mismatch.append(i)
        if not g(r, "legacy_value") or g(r, "legacy_value") == "TODO":
            no_legacy.append(i)
        fps = g(r, "frame_rate_tested")
        if not fps or fps == "TODO":
            no_fps.append(i)

    print("=" * 76)
    print(f"战斗手感/移动 · {len(rows)} 条")
    print("=" * 76)
    if mismatch:
        print(f"\n🚫 **不一致** {len(mismatch)} 条（行 {mismatch[:15]}）")
        print("   → 这是玩家说「打击感不一样」的第一来源")
    if no_legacy:
        print(f"\n❌ {len(no_legacy)} 条缺**原版值**（行 {no_legacy[:15]}）")
    if no_fps:
        print(f"\n⚠️  {len(no_fps)} 条**未记录已实测帧率**（行 {no_fps[:15]}）")
        print("   → 🔴 手感参数必须在 **30/60/120Hz 与可变帧率**下都验证 —— "
              "只测一个帧率不算通过")

    if not (mismatch or no_legacy):
        print("\n✅ 手感：一致且原版值完整")

    print("\n🔑 **顿帧关键是「冻结谁」，不是冻结多久。**")
    print("   **可变跳跃高度有三类语义，不能统称 variable jump。**")
    print("   **霸体不能写成单个布尔。**")
    return 1 if (a.gate and (mismatch or no_legacy)) else 0


def main():
    ap = argparse.ArgumentParser(description="战斗反馈与移动手感")
    ap.add_argument("--hitstop", action="store_true")
    ap.add_argument("--hitflash", action="store_true")
    ap.add_argument("--stagger", action="store_true")
    ap.add_argument("--dmg", action="store_true")
    ap.add_argument("--shake", action="store_true")
    ap.add_argument("--coyote", action="store_true")
    ap.add_argument("--jumpbuf", action="store_true")
    ap.add_argument("--varjump", action="store_true")
    ap.add_argument("--ground", action="store_true")
    ap.add_argument("--platform", action="store_true")
    ap.add_argument("--vehicle", action="store_true")
    ap.add_argument("--init")
    ap.add_argument("--check")
    ap.add_argument("--gate", action="store_true")
    a = ap.parse_args()
    fns = {"hitstop": cmd_hitstop, "hitflash": cmd_hitflash,
           "stagger": cmd_stagger, "dmg": cmd_dmg, "shake": cmd_shake,
           "coyote": cmd_coyote, "jumpbuf": cmd_jumpbuf,
           "varjump": cmd_varjump, "ground": cmd_ground,
           "platform": cmd_platform, "vehicle": cmd_vehicle}
    for k, fn in fns.items():
        if getattr(a, k):
            return fn(a)
    if a.init:
        return cmd_init(a)
    if a.check:
        return cmd_check(a)
    print("❌ 需要 --hitstop / --hitflash / --stagger / --dmg / --shake / "
          "--coyote / --jumpbuf / --varjump / --ground / --platform / "
          "--vehicle / --init / --check 之一")
    return 2


if __name__ == "__main__":
    sys.exit(main())
