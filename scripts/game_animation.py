#!/usr/bin/env python3
"""动画系统深化（第六轮 A 类）—— **跨引擎迁移最容易翻车的地方**。

**🔑 核心认知**：
> 动画不是「有 Idle/Walk/Run」，而是**从源剪辑到屏幕的多层参数链**：
> 导入 → 压缩 → 状态机 → 混合树 → 层与遮罩 → IK → 根运动 → 碰撞。
> 任意中间节点未记录，最终视觉差异就无从复现，只能被当作「像一点就行」。

用法:
  game_animation.py --fsm      # 状态机（**过渡中断规则**）
  game_animation.py --blend    # 混合树（**权重归一化**）
  game_animation.py --root     # 🔴 根运动（**按源权重混合**）
  game_animation.py --retarget # 重定向（**自动映射不是等价保证**）
  game_animation.py --ik       # IK（**不是「启用了 IK」**）
  game_animation.py --compress # 🔴 压缩（**末端误差，不是平均误差**）
  game_animation.py --notify   # 动画事件（**触发权重**）
  game_animation.py --face     # 面部与口型
  game_animation.py --ragdoll  # 物理动画（**三方混合**）
  game_animation.py --init ledger/animation.csv
  game_animation.py --check ledger/animation.csv --gate

退出码: 0 通过 / 1 缺项 / 2 用法错误
"""
import argparse
import csv
import os
import sys

# 状态机：过渡不只是时长与条件
FSM_TRANSITION = [
    "**Interrupt Source**（None / Current / Next / Current then Next / Next then Current）",
    "**Ordered Interruption**（是否允许低优先级打断）",
    "退出时间 exit time", "过渡时长与曲线", "**目标偏移**",
    "同帧两状态都满足时的**优先级**",
]

FSM_UE = [
    "入口规则", "选择器", "冷却", "布尔/枚举优先级", "历史记录",
    "过渡后位置", "分支点", "**sync group**",
]

FSM_RULE = [
    "🔑 must-match 的最小单元是「**同输入下的同状态转移**」 —— "
    "能重放同一参数输入、同帧触发同一状态、按同一曲线执行同一中断",
    "🔴 只复制「条件为真」、未复制「从哪条列表按什么顺序评估」 → "
    "快速连按或网络延迟时出现**不同的招式、不同的起手相位**",
]

# 混合树
BLEND_FIELDS = [
    "参数类型（1D / 2D / Direct）", "**采样点坐标**", "裁剪",
    "插值方法", "网格/重心坐标", "**归一化模式**", "阈值有效性",
    "瞬时 / 平滑", "参数 clamp", "反向归一化", "各 child 权重上限",
]

BLEND_DIRECT = [
    "🔑 Direct blend tree 尤其要记录：",
    "   · 各 clip 权重**是否经规范化**",
    "   · 归一化基准是**权重总和**还是**影响力总和**",
    "   · **零权重分支是否继续 tick**",
    "   · 归一化**前后**的权重分别用于事件/声音的哪个版本",
]

BLEND_2D = [
    "样本点", "三角剖分", "边缘外推", "目标位置 clamp",
    "**两个参数是否耦合**",
]

BLEND_RULE = [
    "🔑 权重必须**规范化后再验证混合形状**，不能直接认为引擎自动处理",
    "⚠️ 只记「速度—方向」而不记样本坐标 → "
    "得到**比例不同但无法命名的步态差异**",
]

# 🔴 根运动
ROOT_SOURCES = [
    "资产", "**贡献权重**", "位移/旋转提取开关", "窗口", "锁定模式",
    "motion warping", "目标匹配",
]

ROOT_RULE = [
    "🔑 同一动画参与最终 pose 时，根运动应**按源资产权重混合**，"
    "**不是只取当前主状态**",
    "🔑 UE 的 `Root Motion from Everything` 提取 AnimSequence、BlendSpace、"
    "AnimMontage 等**所有贡献者**并按最终 pose 的来源权重混合",
    "🔴 若目标引擎只实现「激活状态根运动」 → "
    "目标切换时出现**位移跳变**",
    "🔴 漏记 Walking / Falling 下 Z 轴被忽略 → "
    "**贴地、浮空或穿墙**",
]

# 重定向
RETARGET_FIELDS = [
    "源/目标 skeleton UUID", "每根骨骼 path", "原始名", "映射名",
    "Humanoid/Profile 槽位", "可选/必需", "父子关系",
    "**参考 pose**", "bind pose", "**T/A pose**", "全局旋转",
    "沿父—子方向的 Y 轴", "**关节弯曲轴**",
]

RETARGET_TRAPS = [
    "🔴 **Humanoid 自动映射不是跨引擎等价保证** —— "
    "Godot 的 `SkeletonProfileHumanoid` 会标记缺失、重复和父子关系错误，"
    "但**并不阻断导入**",
    "🔴 **重定向前必须先修复未应用的节点变换** —— "
    "导入 glTF 若未 Apply Transform，节点**看起来正确但内部 Transform 不同**",
    "⚠️ 前置资产步骤（不是运行时 IK 的「小修正」）：node_transform · "
    "bone_rest · import rotation/scale · apply_transform · 局部/全局 bake · "
    "轴向转换 · 镜像 · 自定义属性通道",
]

RETARGET_HEIGHT = [
    "🔴 不同身高角色共享移动动画 → **脚滑**；"
    "身高归一化又可能**破坏 bone rest**",
    "必记 `retarget.position_normalization`：是否开启 · **基准骨骼** · "
    "高度基准 · 绝对/比例/忽略 · 根与臀部处理 · **手和工具骨骼例外**",
    "🔑 迁移策略只能二选一：**优先保持脚—地接触**，还是**保持世界速度** —— "
    "两者无法天然同时成立",
]

# IK
IK_KINDS = [
    ("两骨骼 IK", "joint target、弯曲方向、twist、软限制、pole vector"),
    ("FABRIK", "迭代、容差、初始/末端 target、链长、长度比例"),
    ("CCD", "最大迭代、软目标、角度限制"),
    ("Look At", "轴、up vector、插值、clamp、插值前/后 pose"),
]

IK_FOOT = [
    "🔑 Foot IK 的可观察输出是：脚跟/脚尖权重 · 解算器 · 平面 · 偏移 · "
    "alpha · 插值时间 · 膝盖方向 · 碰撞 —— **不是「启用了 IK」**",
    "🔑 Foot IK 与根运动要**一起测试**：动画要求脚留在地面、根运动驱动胶囊、"
    "控制器允许侧向滑移时，**三者会互相覆盖**",
]

# 🔴 压缩
COMPRESS_UNITY = [
    "Off / Keyframe Reduction / Optimal",
    "🔴 `Keyframe Reduction and Compression` 只减**文件体积**，"
    "**运行时内存仍与仅 Keyframe Reduction 相同**",
    "⚠️ **旋转误差以角度表示，位置/缩放误差按百分比表示** —— "
    "切换精度口径前要先统一单位",
]

COMPRESS_UE = [
    "Max Pos Diff", "Max Angle Diff", "零化阈值", "允许格式",
    "重采样帧率", "最小重采样键数", "**per-track 误差**", "parent height bias",
]

COMPRESS_RULE = [
    "🔴 **压缩评估应关注末端位置/旋转误差，而不是平均曲线误差**",
    "🔑 UE 的 `Max End Effector Error` 会一直监控到末端执行器；"
    "自适应误差还能**根据骨骼层级或轨道对末端造成的误差调整阈值**",
    "🔑 采样点：脚底 · 手指 · **武器** · 镜头 · 飘带 · 头发",
    "🔑 以原始双精度 bake 为基准算 **P50/P95/P99 位置误差** · "
    "最大旋转误差 · **脚滑距离** · 抖动频率 · 循环首尾跳变",
    "🔑 Hero 角色 / 主角 / NPC / 过场 / 程序化动画**分别建质量档**",
]

# 动画事件
NOTIFY_FIELDS = [
    "**Min Trigger Weight**（UE 默认 0.00001 —— "
    "即使权重很低也会触发）",
    "**LOD 过滤**", "Trigger on Follower", "chance", "开始/结束", "tick 精度",
]

NOTIFY_UNITY = [
    "函数名", "参数类型与值", "是否随曲线导入", "时间", "帧",
    "重复模式", "clip 速率缩放",
]

NOTIFY_RULE = [
    "🔴 只记「第 12 帧播放音效」会漏掉：低速/反向播放 · rate scaling · "
    "跨过时间 · **过渡中权重不足** · 循环包裹 · LOD 剔除",
]

# 面部
FACE_BLENDSHAPE = [
    "每个 target 名称", "**索引映射**", "最小值/最大值",
    "normals/tangents 是否重算", "动画曲线", "材质参数", "UV 流", "导入模式",
]

FACE_BONE = [
    "ARKit / MPEG / 自定义映射", "**ARKit 52 个标准目标或实际子集**",
    "骨骼面部 rig", "DSDS", "眼睛注视", "舌头", "耳朵", "牙齿",
    "舌头碰撞", "pre/post process",
]

FACE_LIPSYNC = [
    "viseme 表", "音素映射", "口型时长", "**协同发音**", "闭嘴阈值",
    "音频采样率", "lookahead", "停顿", "区域与语言例外",
]

# 物理动画：**三方混合**
RAGDOLL = [
    "🔑 物理动画与布娃娃**不是开关**，而是"
    "**关键姿势 / 模拟姿势 / 动画姿势的三方混合**",
]

RAGDOLL_FIELDS = [
    "逐骨骼 sim 影响权重", "开始/结束混合时间", "kinematic keying",
    "motor", "damping", "limit", "mass scale", "linear/angular spring",
    "hit reaction curve", "ragdoll 胶囊", "肢体碰撞", "self-collision",
    "contact flag", "recovery animation", "blend out 条件", "死亡判定",
]

RAGDOLL_RULE = [
    "🔑 ragdoll aggregate、唤醒、睡眠、**求解顺序**应逐项记录",
    "⚠️ 跨引擎时骨骼长度、质量、约束求解器不同 —— "
    "**不能直接复用配置**",
]

FIELDS = [
    ("item_id", "项编号"),
    ("domain", "域（fsm / blend / root / retarget / ik / compress / notify / face / ragdoll）"),
    ("legacy_value", "**原版值**"),
    ("new_value", "新引擎值"),
    ("match", "**是否一致**"),
    ("end_effector_error", "**末端误差**（P50/P95/P99）"),
    ("evidence", "证据"),
]


def _hdr(t, w=80):
    print("=" * w)
    print(t)
    print("=" * w)


def cmd_fsm(a):
    _hdr("动画状态机（**过渡不只是时长与条件**）")
    print("过渡必记:")
    for f in FSM_TRANSITION:
        print(f"   · {f}")
    print("\nUE 额外: " + " · ".join(FSM_UE))
    print("\n规则:")
    for r in FSM_RULE:
        print(f"   {r}")
    return 0


def cmd_blend(a):
    _hdr("混合树（🔑 **权重归一化**）")
    for f in BLEND_FIELDS:
        print(f"   · {f}")
    print("\nDirect:")
    for d in BLEND_DIRECT:
        print(f"   {d}")
    print("\n2D: " + " · ".join(BLEND_2D))
    print("\n规则:")
    for r in BLEND_RULE:
        print(f"   {r}")
    return 0


def cmd_root(a):
    _hdr("🔴 根运动（**按源权重混合**）")
    print("`root_motion.sources[]`:")
    for f in ROOT_SOURCES:
        print(f"   · {f}")
    print("\n规则:")
    for r in ROOT_RULE:
        print(f"   {r}")
    return 0


def cmd_retarget(a):
    _hdr("重定向（🔴 **自动映射不是等价保证**）")
    for f in RETARGET_FIELDS:
        print(f"   · {f}")
    print("\n陷阱:")
    for t in RETARGET_TRAPS:
        print(f"   {t}")
    print("\n身高:")
    for h in RETARGET_HEIGHT:
        print(f"   {h}")
    return 0


def cmd_ik(a):
    _hdr("IK（**不是「启用了 IK」**）")
    for k, why in IK_KINDS:
        print(f"\n   【{k}】{why}")
    print("\nFoot IK:")
    for f in IK_FOOT:
        print(f"   {f}")
    return 0


def cmd_compress(a):
    _hdr("🔴 动画压缩（**末端误差，不是平均误差**）")
    print("Unity:")
    for c in COMPRESS_UNITY:
        print(f"   {c}")
    print("\nUE: " + " · ".join(COMPRESS_UE))
    print("\n规则:")
    for r in COMPRESS_RULE:
        print(f"   {r}")
    return 0


def cmd_notify(a):
    _hdr("动画事件（🔴 **触发权重**）")
    print("UE Notify: " + " · ".join(NOTIFY_FIELDS))
    print("\nUnity Event: " + " · ".join(NOTIFY_UNITY))
    print("\n规则:")
    for r in NOTIFY_RULE:
        print(f"   {r}")
    return 0


def cmd_face(a):
    _hdr("面部与口型（**两套 pipeline 分开**）")
    print("Blendshape: " + " · ".join(FACE_BLENDSHAPE))
    print("\n骨骼面部: " + " · ".join(FACE_BONE))
    print("\n口型: " + " · ".join(FACE_LIPSYNC))
    print("\n⚠️ **不能用通用 viseme 表覆盖原项目的自定义表**")
    return 0


def cmd_ragdoll(a):
    _hdr("物理动画（🔑 **三方混合**）")
    for r in RAGDOLL:
        print(f"   {r}")
    print("\n逐骨骼必记: " + " · ".join(RAGDOLL_FIELDS))
    print("\n规则:")
    for r in RAGDOLL_RULE:
        print(f"   {r}")
    return 0


def cmd_init(a):
    os.makedirs(os.path.dirname(a.init) or ".", exist_ok=True)
    with open(a.init, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow([k for k, _ in FIELDS])
        w.writerow(["TODO"] * len(FIELDS))
    print(f"已生成动画表: {a.init}")
    print("\n⚠️ 九域：fsm / blend / root / retarget / ik / "
          "compress / notify / face / ragdoll")
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
    print(f"动画 · {len(rows)} 条")
    print("=" * 76)
    if mismatch:
        print(f"\n🚫 **不一致** {len(mismatch)} 条（行 {mismatch[:15]}）")
        print("   → 动画是跨引擎迁移最容易翻车的地方")
    if no_legacy:
        print(f"\n❌ {len(no_legacy)} 条缺**原版值**（行 {no_legacy[:15]}）")

    if not (mismatch or no_legacy):
        print("\n✅ 动画：一致且原版值完整")

    print("\n🔑 **末端误差，不是平均误差** —— 只记平均曲线误差会把手、")
    print("   脚、武器的错误藏起来。")
    print("   **Humanoid 自动映射不是跨引擎等价保证。**")
    print("   **根运动按源权重混合，不是只取当前主状态。**")
    return 1 if (a.gate and (mismatch or no_legacy)) else 0


def main():
    ap = argparse.ArgumentParser(description="动画系统深化")
    ap.add_argument("--fsm", action="store_true")
    ap.add_argument("--blend", action="store_true")
    ap.add_argument("--root", action="store_true")
    ap.add_argument("--retarget", action="store_true")
    ap.add_argument("--ik", action="store_true")
    ap.add_argument("--compress", action="store_true")
    ap.add_argument("--notify", action="store_true")
    ap.add_argument("--face", action="store_true")
    ap.add_argument("--ragdoll", action="store_true")
    ap.add_argument("--init")
    ap.add_argument("--check")
    ap.add_argument("--gate", action="store_true")
    a = ap.parse_args()
    fns = {"fsm": cmd_fsm, "blend": cmd_blend, "root": cmd_root,
           "retarget": cmd_retarget, "ik": cmd_ik, "compress": cmd_compress,
           "notify": cmd_notify, "face": cmd_face, "ragdoll": cmd_ragdoll}
    for k, fn in fns.items():
        if getattr(a, k):
            return fn(a)
    if a.init:
        return cmd_init(a)
    if a.check:
        return cmd_check(a)
    print("❌ 需要 --fsm / --blend / --root / --retarget / --ik / --compress / "
          "--notify / --face / --ragdoll / --init / --check 之一")
    return 2


if __name__ == "__main__":
    sys.exit(main())
