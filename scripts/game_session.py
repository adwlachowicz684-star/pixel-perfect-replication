#!/usr/bin/env python3
"""锁定/取消窗口 + 多人会话 + 粒子与超分色彩（第八轮 C / D / F / G 类）。

**🔑 C 类核心**：
> 锁定的关键不是 UI，而是**目标选择、辅助、取消、输入序列**四层合约。
> 若软锁定只改变瞄准而角色仍按移动方向出招 → 玩家看到
> **「准星吸住但攻击方向不一致」**。

**🔑 D 类核心**：
> 必须新增**会话状态恢复**，而不是只记录同步模型。
> 公开案例：小重连**补帧**、大重连**回放权威快照**，并维护 **5 秒关键帧缓存**与定时关键帧。

**🔑 F 类核心**：
> 粒子池耗尽策略必须被当成**可见规则** —— 若原项目过载时优先保留受击核心特效，
> 复刻为"谁先申请谁成功"会直接**改变战斗可读性**。

**🔑 G 类核心**：
> 帧生成会**插入合成帧**，可能影响端到端显示时序和输入采样。
> 应记录原始输入时间，而不是笼统写「影响延迟」。

用法:
  game_session.py --lockon     # 锁定：四张表
  game_session.py --softlock   # 软锁定是**独立输入映射**
  game_session.py --cancel     # 取消窗口**绑定状态/动画事件**
  game_session.py --command    # 方向输入序列识别器
  game_session.py --authority  # 朝向冲突优先级
  game_session.py --session    # 🔴 会话状态恢复
  game_session.py --reconnect  # 重连：**补帧 vs 回放快照**
  game_session.py --spectate   # 观战/回放/killcam（**玩家可见功能**）
  game_session.py --stealth    # 潜行：可见阈值 + 不可见状态机
  game_session.py --particle   # 粒子时间域与**池耗尽策略**
  game_session.py --upscale    # 🔴 超分与帧生成
  game_session.py --hdr        # HDR/色调映射/宽色域
  game_session.py --init ledger/session.csv
  game_session.py --check ledger/session.csv --gate

退出码: 0 通过 / 1 缺项 / 2 用法错误
"""
import argparse
import csv
import os
import sys

# 锁定四张表
LOCK_TABLES = [
    ("target_pool", "可见、可交互、敌我、距离、角度、**屏幕中心距离**、"
                    "视线遮挡、高度差、权重"),
    ("acquire_rules", "首次自动锁、手动切换、**屏幕中心优先**、朝向优先"),
    ("switch_rules", "左/右切换、最近邻、距离阈值、角度阈值"),
    ("loss_rules", "超距、遮挡、死亡、隐藏、视角变化"),
    ("post_loss_behavior", "保持方向、缓慢解除、保留相机目标、允许软锁定"),
]

LOCK_RANGE = [
    "🔑 锁定范围**不能只写圆半径** —— 还要记录：中心 · 屏幕空间还是世界空间 · "
    "**最大仰角/俯角** · 遮挡穿透规则",
]

# 软锁定
SOFTLOCK_FIELDS = [
    "**磁力**（吸附速度、最大偏移、方向权重）",
    "**摩擦力/减速区**（输入响应降低比例、衰减半径）",
    "开镜吸附", "腰射吸附", "**开火期间吸附**",
    "目标体积", "**骨骼或碰撞体目标点**", "距离衰减",
    "输入阈值触发", "持续时间", "释放条件",
]

SOFTLOCK_RULE = [
    "🔑 软锁定是**独立输入映射**，不是「瞄准更准」",
    "🔑 辅助只作用于客户端表现时，必须与**权威命中判定**分开 —— "
    "否则「手感更跟手」会变成**服务端判定变化**",
]

# 取消窗口
CANCEL_FIELDS = [
    "源状态", "源动作", "**取消起始帧/时间**", "**取消结束帧/时间**",
    "目标技能或动作", "**是否消耗资源**", "资源不足是否仍取消",
    "**是否保留位移**", "**是否继承连段计数**",
    "是否允许取消受击", "动画结束后是否仍保留窗口", "不同攻击等级优先级",
]

CANCEL_RULE = [
    "🔑 若原项目使用**动画通知**启停连段输入，复刻为**固定帧数并不等价** —— "
    "动画速率、命中缩放和状态切换会改变通知时机",
    "🔑 schema 必须同时记录 `window_kind`（notify / fixed_frame / phase / "
    "input_state）与**原始值**",
]

# 方向输入序列
COMMAND_FIELDS = [
    "输入序列", "允许方向", "**角度或方向容差**", "**斜向归并**",
    "输入最短/最长间隔", "**序列有效窗口**", "方向优先级",
    "**是否消费原始输入**", "与同时按下的攻击键优先级",
    "**角色朝向变化后的重新映射**", "暂停/菜单/死亡期间的保留策略",
]

COMMAND_NOTE = [
    "🔑 2D 游戏需区分「下前攻击」「前下前」「前攻击」「斜前攻击」；"
    "3D 还要区分**世界空间方向、相机相对方向、当前朝向相对方向**",
    "❌ 不建议用「手势识别库」自动吸收 —— "
    "黑盒匹配会掩盖精确的**方向归并与超时规则**",
]

AUTHORITY = [
    "player_input", "soft_aim", "hard_lock", "animation_root_motion",
]

AUTHORITY_RULE = [
    "🔑 锁定后**角色朝向、移动轴、相机目标、镜头距离、FOV、碰撞避让、"
    "位移技能方向、瞄准辅助**必须成对记录",
    "🔴 若软锁定只改变瞄准而角色仍按移动方向出招 → "
    "玩家看到「**准星吸住但攻击方向不一致**」",
    "🔴 若锁定强制转向，又可能与手动方向输入冲突",
]

# 🔴 会话状态恢复
SESSION_STATES = [
    "匹配 matchmaking", "房间/大厅 lobby", "准备与权限",
    "**主机迁移 host migration**", "**断线重连 reconnect**",
    "观战 spectator", "**回放 replay / killcam**",
]

RECONNECT_KINDS = [
    ("**小重连**", "补帧 —— 补齐断线期间的输入与事件"),
    ("**大重连**", "回放权威快照 —— 直接同步权威状态"),
]

RECONNECT_CACHE = [
    "🔑 维护 **5 秒关键帧缓存**与**定时关键帧**",
    "🔑 记录：状态恢复、重新同步、超时",
]

SESSION_NOTE = [
    "🔑 这些是**玩家可见功能**，迁移时最容易整体丢失",
    "⚠️ Steam 官方明确说明**大厅不自带网络传输** —— "
    "❌ 大厅 API 不能替代网络层",
]

# 潜行
STEALTH_VISION = [
    "视觉锥（角度、长度、**近距无锥区**、高度、仰俯角）",
    "目标可见条件（遮挡、光照、噪声、装备、动作、颜色、运动）",
    "**光照影响曲线**", "距离衰减", "视线检查",
    "**最后已知位置**", "**确认时间**", "失去目标行为",
]

STEALTH_AUDIO = [
    "音源类型", "传播介质", "距离", "衰减", "遮挡",
    "**方向不确定性**", "延迟", "惊动传播",
]

STEALTH_LEVELS = [
    "普通可见", "可疑", "确认", "搜索", "警报",
]

STEALTH_SM = [
    "patrol", "investigate", "alert", "search", "combat",
    "lose_target", "flee", "return",
]

STEALTH_SM_FIELDS = [
    "状态转移所需的**确认次数**", "计时", "**位置记忆**", "目标消失阈值",
    "**呼叫队友**", "**共享目标**", "声源优先级", "**搜索点生成**",
    "视野恢复", "任务失败或剧情暂停",
]

STEALTH_UI = [
    "🔑 潜行表现也是状态数据：HUD 计量条 · 敌人问号/感叹号图标 · "
    "**音乐切换** · 环境反应 · 对话 · 队友反应 · 玩家可见性提示 · "
    "**存档中是否保存警觉度**",
    "🔴 若只复刻 AI 逻辑而忽略 HUD 和音效阈值 → "
    "玩家感知为「**敌人反应一样，但不知道自己为什么被发现**」",
]

# 粒子
PARTICLE_TIME = [
    "时间源（world / **real_time** / audio / ui / **unscaled**）",
    "暂停行为", "慢动作缩放", "**固定步模拟**", "出生/死亡时机",
    "**随机种子**", "**回放一致性**", "确定性关卡", "local/world space",
]

PARTICLE_KINDS = [
    "GPU 粒子", "CPU 粒子", "网格", "骨骼附件", "轨迹", "贴花",
]

PARTICLE_POOL = [
    "**池归属**（全局 / 系统 / 场景）", "容量", "预 warm", "动态扩容",
    "**回收优先级**",
    "**新粒子失败策略**（丢弃 / 替换最旧 / 强制杀死同优先级 / 降画质）",
    "**最旧粒子选择依据**（年龄、重要性、距离、可见性、屏幕覆盖）",
    "**UI 与关键演出是否豁免**",
]

PARTICLE_TEST = [
    "暂停菜单", "**hit stop**", "时间倒流", "关卡卸载", "低画质",
    "**高同屏压力**", "**确定性回放**",
]

# 🔴 超分与帧生成
UPSCALE_FIELDS = [
    "质量档（ultra quality / quality / balanced / performance）",
    "**锐化**", "**运动向量来源**", "动态分辨率上下限", "最小/最大比例",
    "目标帧率", "开销监控", "**帧生成**", "低延迟集成",
    "GPU/CPU 占用", "**输入延迟**", "伪影",
    "**UI 缩放与独立渲染路径**",
]

UPSCALE_KINDS = [
    "FSR", "XeSS", "DLSS", "TSR",
]

UPSCALE_RULE = [
    "🔴 **帧生成会插入合成帧**，可能影响端到端显示时序和输入采样",
    "🔑 超分本身通常不改变逻辑世界状态，但若移动/瞄准读取显示延迟统计、"
    "动态分辨率改变时间预算，或输入响应依赖帧完成时刻 → **表现层会反馈到手感**",
    "🔑 必须保留 `input_to_photon` · `sim_tick_interval` · `frame_interval` · "
    "`dynamic_resolution_ratio` · `upscaler_mode` · `frame_generation`，"
    "并**每个组合实测输入时间线**",
    "⚠️ **AMD GPUOpen/FidelityFX 的 FSR 历史公开版本曾采用 MIT，"
    "但需按具体 release 复核**",
    "⚠️ **NVIDIA DLSS SDK 与 Intel XeSS SDK 主要提供二进制/SDK 分发** —— "
    "❌ 不能据此宣称内部超分模型已开源",
]

HDR_FIELDS = [
    "**色彩管理是否启用**", "HDR 显示检测", "**UI 是否保持 sRGB**",
    "后处理与 Bloom 的**白点**", "**色调映射曲线**", "自动曝光",
    "**截屏和回放录像色彩空间**",
]

HDR_MODES = [
    "HDR10 / BT.2100", "scRGB", "FP16", "HDR10 PQ", "HLG", "Dolby Vision",
]

HDR_NOTE = [
    "🔑 **这些模式并非可互换**",
    "🔑 Windows 高级色彩覆盖 HDR、宽色域、高位深和系统色彩管理；"
    "Windows 11 22H2 将支持扩展到符合条件的 **SDR 显示器**",
    "🔑 DXGI 交换链和色彩空间配置必须**统一** —— "
    "建议高级色彩用 `DXGI_FORMAT_R16G16B16A16_FLOAT`，"
    "默认浮点交换链用 `DXGI_COLOR_SPACE_TYPE_RGB_FULL_G10_NONE_P709`",
]

VRS_FIELDS = [
    "Tier", "per-draw", "per-primitive", "tile-based", "shading rate image",
    "基础速率", "轴对齐或旋转模式", "**屏幕区域映射**", "运动区域",
    "**边缘/UI 保留**", "后处理与透明对象策略", "画质档", "性能监控与伪影",
]

VRS_RULE = "⚠️ 运行时可用性、Tier 和平台差异必须在**目标硬件矩阵**中验证，"
"**不能只按 API 版本推断**"

FIELDS = [
    ("item_id", "项编号"),
    ("domain", "域（lock / softlock / cancel / command / session / stealth / particle / upscale / hdr / vrs）"),
    ("legacy_value", "**原版值**"),
    ("new_value", "新引擎值"),
    ("match", "**是否一致**"),
    ("evidence", "证据"),
]


def _hdr(t, w=80):
    print("=" * w)
    print(t)
    print("=" * w)


def cmd_lockon(a):
    _hdr("锁定（**四张表**）")
    for k, why in LOCK_TABLES:
        print(f"\n   【{k}】{why}")
    print("\n范围:")
    for r in LOCK_RANGE:
        print(f"   {r}")
    return 0


def cmd_softlock(a):
    _hdr("软锁定（**独立输入映射**）")
    for f in SOFTLOCK_FIELDS:
        print(f"   · {f}")
    print("\n规则:")
    for r in SOFTLOCK_RULE:
        print(f"   {r}")
    return 0


def cmd_cancel(a):
    _hdr("取消窗口（**绑定状态/动画事件**）")
    for f in CANCEL_FIELDS:
        print(f"   · {f}")
    print("\n规则:")
    for r in CANCEL_RULE:
        print(f"   {r}")
    return 0


def cmd_command(a):
    _hdr("方向输入序列识别器")
    for f in COMMAND_FIELDS:
        print(f"   · {f}")
    print("\n注意:")
    for n in COMMAND_NOTE:
        print(f"   {n}")
    return 0


def cmd_authority(a):
    _hdr("朝向冲突优先级")
    print("authority 取值: " + " · ".join(AUTHORITY))
    print("\n规则:")
    for r in AUTHORITY_RULE:
        print(f"   {r}")
    return 0


def cmd_session(a):
    _hdr("🔴 多人会话（**状态恢复，不只是同步模型**）")
    for s in SESSION_STATES:
        print(f"   · {s}")
    print("\n重连:")
    for k, why in RECONNECT_KINDS:
        print(f"   【{k}】{why}")
    print("")
    for c in RECONNECT_CACHE:
        print(f"   {c}")
    print("\n注意:")
    for n in SESSION_NOTE:
        print(f"   {n}")
    return 0


def cmd_reconnect(a):
    _hdr("重连（**补帧 vs 回放快照**）")
    for k, why in RECONNECT_KINDS:
        print(f"   【{k}】{why}")
    print("")
    for c in RECONNECT_CACHE:
        print(f"   {c}")
    return 0


def cmd_spectate(a):
    _hdr("观战 / 回放 / killcam（**玩家可见功能**）")
    for n in SESSION_NOTE:
        print(f"   {n}")
    print("\n🔑 新增：玩家可见回放语义 · 输入/事件/快照流 · **权限** · "
          "触发与播放控制")
    return 0


def cmd_stealth(a):
    _hdr("潜行（**可见阈值 + 不可见状态机**）")
    print("视觉: " + " · ".join(STEALTH_VISION))
    print("\n听觉: " + " · ".join(STEALTH_AUDIO))
    print("\n隐蔽度等级（**不能只写 0—1**）: " + " · ".join(STEALTH_LEVELS))
    print("\n警觉状态机: " + " · ".join(STEALTH_SM))
    print("转移字段: " + " · ".join(STEALTH_SM_FIELDS))
    print("\n表现:")
    for u in STEALTH_UI:
        print(f"   {u}")
    return 0


def cmd_particle(a):
    _hdr("粒子（🔴 **池耗尽策略是可见规则**）")
    print("时间域: " + " · ".join(PARTICLE_TIME))
    print("\n类型（**不能混写**）: " + " · ".join(PARTICLE_KINDS))
    print("\n池策略: " + " · ".join(PARTICLE_POOL))
    print("\n逐发射器验证: " + " · ".join(PARTICLE_TEST))
    print("\n🔴 若原项目过载时优先保留**受击核心特效**，"
          "复刻为「谁先申请谁成功」会直接改变**战斗可读性**")
    return 0


def cmd_upscale(a):
    _hdr("🔴 超分与帧生成")
    print("技术: " + " · ".join(UPSCALE_KINDS))
    print("\n字段: " + " · ".join(UPSCALE_FIELDS))
    print("\n规则:")
    for r in UPSCALE_RULE:
        print(f"   {r}")
    return 0


def cmd_hdr(a):
    _hdr("HDR / 色调映射 / 宽色域")
    print("模式: " + " · ".join(HDR_MODES))
    print("\n字段: " + " · ".join(HDR_FIELDS))
    print("\n注意:")
    for n in HDR_NOTE:
        print(f"   {n}")
    print("\nVRS: " + " · ".join(VRS_FIELDS))
    print(f"\n{VRS_RULE}")
    return 0


def cmd_init(a):
    os.makedirs(os.path.dirname(a.init) or ".", exist_ok=True)
    with open(a.init, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow([k for k, _ in FIELDS])
        w.writerow(["TODO"] * len(FIELDS))
    print(f"已生成会话/特效表: {a.init}")
    print("\n⚠️ 十域：lock / softlock / cancel / command / session / "
          "stealth / particle / upscale / hdr / vrs")
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
    print(f"会话/特效 · {len(rows)} 条")
    print("=" * 76)
    if mismatch:
        print(f"\n🚫 **不一致** {len(mismatch)} 条（行 {mismatch[:15]}）")
    if no_legacy:
        print(f"\n❌ {len(no_legacy)} 条缺**原版值**（行 {no_legacy[:15]}）")

    if not (mismatch or no_legacy):
        print("\n✅ 会话/特效：一致且原版值完整")

    print("\n🔑 **会话要记录状态恢复，不只是同步模型。**")
    print("   **粒子池耗尽策略是可见规则。**")
    print("   **帧生成插入合成帧 —— 记原始输入时间，不是笼统写「影响延迟」。**")
    return 1 if (a.gate and (mismatch or no_legacy)) else 0


def main():
    ap = argparse.ArgumentParser(description="会话/锁定/粒子/超分")
    ap.add_argument("--lockon", action="store_true")
    ap.add_argument("--softlock", action="store_true")
    ap.add_argument("--cancel", action="store_true")
    ap.add_argument("--command", action="store_true")
    ap.add_argument("--authority", action="store_true")
    ap.add_argument("--session", action="store_true")
    ap.add_argument("--reconnect", action="store_true")
    ap.add_argument("--spectate", action="store_true")
    ap.add_argument("--stealth", action="store_true")
    ap.add_argument("--particle", action="store_true")
    ap.add_argument("--upscale", action="store_true")
    ap.add_argument("--hdr", action="store_true")
    ap.add_argument("--init")
    ap.add_argument("--check")
    ap.add_argument("--gate", action="store_true")
    a = ap.parse_args()
    fns = {"lockon": cmd_lockon, "softlock": cmd_softlock, "cancel": cmd_cancel,
           "command": cmd_command, "authority": cmd_authority,
           "session": cmd_session, "reconnect": cmd_reconnect,
           "spectate": cmd_spectate, "stealth": cmd_stealth,
           "particle": cmd_particle, "upscale": cmd_upscale, "hdr": cmd_hdr}
    for k, fn in fns.items():
        if getattr(a, k):
            return fn(a)
    if a.init:
        return cmd_init(a)
    if a.check:
        return cmd_check(a)
    print("❌ 需要 --lockon / --softlock / --cancel / --command / --authority / "
          "--session / --reconnect / --spectate / --stealth / --particle / "
          "--upscale / --hdr / --init / --check 之一")
    return 2


if __name__ == "__main__":
    sys.exit(main())
