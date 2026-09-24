#!/usr/bin/env python3
"""跨游戏引擎迁移与二次创作（本 Skill 主场景）。

**🔑 定位**：这是**自己的项目在不同游戏引擎之间的搬迁与二次创造**，
不是复刻第三方专有软件。

> **法律/授权门禁在本场景默认不适用**（见 `--ownership`），
> 不要因为"许可未确认""反编译风险"这类顾虑阻碍自有项目的重制与二次开发。

---

**核心理念**：
> **先像素级记录原引擎上的表现，再有意识地偏离。**
> 偏离不是随意的 —— 每一处偏离都要有**分类、理由与证据**。

四类处置：
| 类别 | 含义 | 典型 |
|---|---|---|
| `must-match` | **必须等价**，偏离即 BUG | 手感、数值、碰撞、时序、关卡布局、输入响应 |
| `may-evolve` | 可以有意识地演进 | 渲染画质、特效、光照、模型精度、UI 美化 |
| `should-reinvent` | 应主动用新引擎特性重做 | Nanite/Lumen/GI、新后处理、内容扩展 |
| `explicit-new` | 明确的新增内容 | 新关卡、新机制、新美术方向 |

用法:
  engine_migration.py --ownership          # 项目性质（**法律门禁的开关**）
  engine_migration.py --axes               # 🔴 坐标系与朝向（**最容易错**）
  engine_migration.py --map                # 引擎概念映射矩阵
  engine_migration.py --assets             # 资产管线与法线贴图陷阱
  engine_migration.py --shader             # 着色器翻译
  engine_migration.py --physics            # 物理与时间步
  engine_migration.py --anim               # 动画与骨骼重定向
  engine_migration.py --recreate           # 二次创作决策四分类
  engine_migration.py --init ledger/engine_matrix.csv
  engine_migration.py --check ledger/engine_matrix.csv --gate

退出码: 0 通过 / 1 有 must-match 未等价或偏离未登记 / 2 用法错误
"""
import argparse
import csv
import os
import sys

# 🔴 坐标系：**最容易出错、且错误会弥漫到全项目**
AXES = [
    ("Unity", "**左手系**, Y-up", "+Z 前, +X 右, +Y 上",
     "FBX 导入默认**转成左手**；`Handedness` 影响法线/旋转"),
    ("Unreal", "**左手系**, Z-up", "+X 前, +Y 右, +Z 上",
     "**单位是厘米**（Unity/Godot 是米）—— 迁移动力学会全错"),
    ("Godot", "**右手系**, Y-up", "**-Z 前**, +X 右, +Y 上",
     "与 Unity 前向相反 → 角色/相机朝向要翻转"),
    (" Blender/glTF", "**右手系**, Z-up(源)", "glTF 规范为右手 Y-up",
     "导出时 `+Y up` 选项必须一致，否则整体旋转 90°"),
]

AXES_TRAPS = [
    "🔴 **Unreal 用厘米**，Unity/Godot 用米 —— 速度、重力、阻尼直接搬会差 100 倍",
    "🔴 **Godot 是 -Z 前向**，Unity 是 +Z 前向 —— 模型/相机/AI 朝向全反",
    "🔴 **左手 vs 右手**会翻转叉积、 winding order（**背面剔除反了**）、法线方向",
    "🔴 欧拉角顺序不同（Unity ZXY / Unreal 也不同）—— 直接搬数值会得到错误朝向",
    "🔴 缩放：负缩放会翻转法线并破坏物理凸包",
    "⚠️ 骨骼轴向（Bone Roll）不同 → 重定向后手臂扭曲",
]

# 概念映射（**不能按名字一一对应**）
CONCEPT_MAP = [
    ("场景对象", "GameObject", "Actor", "Node", "**Node 是树，Actor 是平表+组件**"),
    ("可复用模板", "Prefab", "Blueprint Class", "PackedScene / .tscn",
     "**嵌套与变体机制完全不同**（Prefab Variant / Child Actor / Inherited Scene）"),
    ("组件", "MonoBehaviour", "ActorComponent / SceneComponent", "Node 本身就是组件",
     "Godot 用**子节点**代替组件 → 遍历顺序与生命周期不同"),
    ("脚本", "C#", "C++ / Blueprint", "GDScript / C#", "执行顺序与生命周期钩子不同"),
    ("协程", "Coroutine(IEnumerator)", "Latent Action / Timeline", "`await` / 信号 / Timer",
     "**暂停/时间缩放下的行为不同** —— 手感会变"),
    ("资源引用", "GUID + 引用", "软/硬引用 TSoftObjectPtr", "路径 / UID",
     "迁移时**引用易断**，需重映射表"),
    ("数据资产", "ScriptableObject", "DataAsset / DataTable", "Resource",
     "序列化格式不同，需逐字段导出导入"),
    ("时间步", "FixedUpdate（fixedDeltaTime）", "Tick Group + 物理子步", "_physics_process",
     "🔴 **不一致会直接改变手感**"),
    ("输入", "Input System / InputManager", "Enhanced Input", "InputMap",
     "**死区、曲线、绑定、缓冲窗口**都要重录"),
    ("UI", "UGUI / UI Toolkit", "UMG / Slate", "Control 节点",
     "**锚点/缩放策略/像素对齐**语义不同"),
    ("音频", "AudioSource / 混音器", "Sound Cue / MetaSound", "AudioStreamPlayer + Bus",
     "中间件(Wwise/FMOD)需单独迁"),
]

# 资产管线
ASSET_TRAPS = [
    ("**法线贴图绿通道**", "OpenGL(+Y) vs DirectX(-Y) —— **反了光照全错**，"
     "Unity/Unreal 默认 DirectX，Godot/Blender 默认 OpenGL"),
    ("色彩空间", "**Linear vs Gamma**：sRGB 贴图标记错误会导致颜色发灰/过亮；"
     "迁移动画曲线与光照会全变"),
    ("单位与缩放", "Unreal 厘米 vs 米；导入缩放因子未设 → 模型大 100 倍"),
    ("切线空间", "MikkTSpace vs 其他 —— 法线细节差异"),
    ("骨骼轴向/单位", "FBX 骨骼缩放、Roll；重定向后扭曲"),
    ("顶点色/UV 通道", "通道语义（UV1/UV2/顶点色用途）不同"),
    ("LOD 与剔除", "LOD 生成规则、Screen Size 阈值不同"),
    ("纹理压缩", "ASTC/BC/ETC 平台差异；**透明通道**处理"),
    ("音频格式", "压缩格式、采样率、循环点、空间化元数据"),
    ("字体 SDF", "SDF 生成参数不同 → 字重与描边不一致"),
]

SHADER_NOTES = [
    "翻译方向：HLSL ↔ GLSL ↔ MSL ↔ WGSL ↔ SPIR-V",
    "**SPIRV-Cross** 可作中间表示（已登记）",
    "可视化着色器：Shader Graph ↔ Material Editor ↔ VisualShader —— "
    "**节点语义不完全等价**，需逐个验证输出",
    "⚠️ 精度限定符（`half`/`mediump`）在移动端会导致可见差异",
    "⚠️ 内置变量差异：`_Time` / `View.WorldToClip` / 矩阵乘序（**行主序 vs 列主序**）",
    "⚠️ 后处理栈顺序（Bloom → Tonemap → LUT）不同 → 最终画面不同",
    "⚠️ 色调映射（ACES / Reinhard / Filmic）与曝光必须锁定才能比对",
]

PHYSICS_NOTES = [
    ("引擎", "PhysX(Unity/Unreal4) · Chaos(Unreal5) · Bullet · Jolt · Godot 内置"),
    ("🔴 固定时间步", "**必须与原引擎一致**，否则跳跃高度、摩擦、阻尼全变"),
    ("碰撞形状", "Mesh/Convex/胶囊/盒 的近似方式不同 → 卡墙、穿透"),
    ("物理材质", "摩擦/弹性组合模式（average/min/max）不同"),
    ("CCD", "连续碰撞检测的开法不同 → 高速穿透"),
    ("求解器迭代", "迭代次数不同 → 堆叠稳定性不同"),
    ("重力/阻尼", "线性/角阻尼公式不同"),
    ("确定性", "**跨引擎不可能位级一致** —— 只保证「可玩等价」"),
]

ANIM_NOTES = [
    ("状态机", "Mecanim ↔ AnimBlueprint(StateMachine) ↔ AnimationTree"),
    ("混合树", "1D/2D/BlendSpace/Direct —— 参数与归一化语义不同"),
    ("骨骼重定向", "Humanoid/Avatar ↔ Retarget Chain ↔ BoneMap —— "
                  "**骨骼命名与轴向必须映射**"),
    ("根运动", "Root Motion 开关与提取方式不同 → 位移丢失"),
    ("IK", "目标/极向量/权重语义不同"),
    ("变形", "BlendShape/Morph 通道顺序与命名"),
    ("压缩", "动画压缩误差不同 → 细微抖动"),
    ("层与遮罩", "Avatar Mask / Layered blend / Bone filter"),
]

# 二次创作四分类
RECREATE = [
    ("must-match", "**必须等价**，偏离即 BUG",
     "输入响应延迟 · 跳跃高度与手感 · 移动速度与加速度 · 碰撞判定 · "
     "无敌帧/判定帧 · 时序与节奏 · 关卡布局与可达性 · 数值与伤害 · "
     "相机 FOV 与跟随 · 音频触发时机"),
    ("may-evolve", "可以有意识地演进",
     "渲染画质 · 光照与阴影质量 · 特效粒子 · 模型精度 · 材质细节 · "
     "UI 美化 · 字体 · 后处理强度"),
    ("should-reinvent", "应主动用新引擎特性重做",
     "Nanite / Lumen / GI / 体积光 · 新后处理栈 · 新物理特性 · "
     "更优动画系统 · 新平台能力"),
    ("explicit-new", "明确的新增内容",
     "新关卡 · 新机制 · 新美术方向 · 新剧情"),
]

RECREATE_RULE = [
    "🔑 **先像素级记录原引擎表现，再有意识地偏离** —— "
    "偏离必须有分类、理由与证据（对应 S2P 四栏：原值/新值/理由/性质）。",
    "⚠️ `must-match` 项**不许以「新引擎更好」为由擅自改动** —— 那是手感回归。",
    "⚠️ `should-reinvent` 项要单独记录**它是有意偏离**，"
    "否则验收时会被当成 BUG（对应 BUG 卡的「有意行为变更登记」）。",
    "✅ 二次创作的空间在 may-evolve / should-reinvent / explicit-new 三类，"
    "不在 must-match。",
]

FIELDS = [
    ("item_id", "项编号"),
    ("domain", "域（坐标/资产/着色器/物理/动画/音频/输入/UI/脚本/数值）"),
    ("source_engine_value", "**原引擎表现**（像素级记录）"),
    ("target_engine_value", "新引擎实现"),
    ("disposition", "**处置**（must-match / may-evolve / should-reinvent / explicit-new）"),
    ("equivalent", "**是否等价**（must-match 必须为是）"),
    ("deviation_reason", "偏离理由（非 must-match 必填）"),
    ("evidence", "证据"),
]


def cmd_ownership(a):
    print("=" * 78)
    print("项目性质（**法律/授权门禁的开关**）")
    print("=" * 78)
    print("""
  本 Skill 的主场景是：**自己的项目在不同游戏引擎之间的搬迁与二次创造**。

  ┌────────────────┬──────────────────────────────────┐
  │ ownership      │ 法律/许可门禁                     │
  ├────────────────┼──────────────────────────────────┤
  │ self（默认）   │ **不适用**，默认放行               │
  │ third_party    │ 才需要许可证据与授权确认           │
  └────────────────┴──────────────────────────────────┘
""")
    print("  🔑 **不要因为「许可未确认」「反编译风险」「DRM」这类顾虑")
    print("     阻碍自有项目的重制与二次开发。**")
    print("""
  下列门禁在 `ownership: self` 时**自动跳过**（不阻断、不降级、不报警）：
    · G21 许可证据充分
    · 字体/音效/图标的商用与再分发确认
    · clean room / 反向工程合法性
    · "遇加密/DRM/许可证校验停止并咨询法务"
    · AGPL/GPL 工具的"法务确认"提示

  改为：这些只在 `ownership: third_party`（复刻他人作品并**对外分发**）时才生效。
  即使是自有项目，若**引入第三方素材**（商城资源、外包音频、免费字体），
  那部分素材仍需各自确认 —— 只影响该素材，不阻断整个项目。
""")
    print("  设置：在 `ledger/project.yaml` 写 `ownership: self`。")
    print("       （文件不存在时**默认 self**）")
    return 0


def cmd_axes(a):
    print("=" * 80)
    print("🔴 坐标系与朝向（**最容易错，且错误会弥漫到全项目**）")
    print("=" * 80)
    for eng, sysinfo, fwd, note in AXES:
        print(f"\n   【{eng}】{sysinfo}")
        print(f"      前向: {fwd}")
        print(f"      {note}")
    print("\n陷阱:")
    for t in AXES_TRAPS:
        print(f"   {t}")
    print("\n🔑 迁移第一步就该**锁定坐标系与单位** —— 否则后面全白做。")
    return 0


def cmd_map(a):
    print("=" * 84)
    print("引擎概念映射（**不能按名字一一对应**）")
    print("=" * 84)
    for concept, unity, unreal, godot, note in CONCEPT_MAP:
        print(f"\n   【{concept}】")
        print(f"      Unity:  {unity}")
        print(f"      Unreal: {unreal}")
        print(f"      Godot:  {godot}")
        if note:
            print(f"      ⚠️ {note}")
    print("\n🔑 **概念同名 ≠ 语义相同** —— 尤其 Prefab/组件/协程/时间步。")
    return 0


def cmd_assets(a):
    print("=" * 78)
    print("资产管线陷阱")
    print("=" * 78)
    for k, why in ASSET_TRAPS:
        print(f"\n   【{k}】")
        print(f"      {why}")
    return 0


def cmd_shader(a):
    print("=" * 74)
    print("着色器翻译")
    print("=" * 74)
    for n in SHADER_NOTES:
        print(f"   · {n}")
    print("\n🔑 锁定**色调映射、曝光、色彩空间、后处理顺序**才能做视觉比对。")
    return 0


def cmd_physics(a):
    print("=" * 76)
    print("物理与时间步")
    print("=" * 76)
    for k, why in PHYSICS_NOTES:
        print(f"\n   【{k}】")
        print(f"      {why}")
    print("\n🔑 **固定时间步不一致 → 手感直接变**，这是 must-match 项。")
    return 0


def cmd_anim(a):
    print("=" * 76)
    print("动画与骨骼重定向")
    print("=" * 76)
    for k, why in ANIM_NOTES:
        print(f"\n   【{k}】")
        print(f"      {why}")
    return 0


def cmd_recreate(a):
    print("=" * 80)
    print("二次创作决策四分类")
    print("=" * 80)
    for k, what, examples in RECREATE:
        print(f"\n   【{k}】{what}")
        print(f"      {examples}")
    print("\n规则:")
    for r in RECREATE_RULE:
        print(f"   {r}")
    return 0


def cmd_init(a):
    os.makedirs(os.path.dirname(a.init) or ".", exist_ok=True)
    with open(a.init, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow([k for k, _ in FIELDS])
        w.writerow(["TODO"] * len(FIELDS))
    print(f"已生成跨引擎迁移矩阵: {a.init}")
    print("\n⚠️ 十域：坐标 · 资产 · 着色器 · 物理 · 动画 · 音频 · 输入 · "
          "UI · 脚本 · 数值")
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

    not_equiv, no_reason, no_source, missing = [], [], [], []
    for i, r in enumerate(rows, 1):
        disp = g(r, "disposition").lower()
        eq = g(r, "equivalent").lower()
        if disp == "must-match":
            if eq not in ("yes", "y", "true", "是"):
                not_equiv.append(i)
        elif disp in ("may-evolve", "should-reinvent", "explicit-new"):
            if not g(r, "deviation_reason") or g(r, "deviation_reason") == "TODO":
                no_reason.append(i)
        else:
            no_reason.append(i)  # 处置未分类也算缺理由
        if not g(r, "source_engine_value") or g(r, "source_engine_value") == "TODO":
            no_source.append(i)
        miss = [k for k, _ in FIELDS
                if not g(r, k) or g(r, k) in ("TODO", "待填", "—")]
        if miss:
            missing.append((i, miss))

    print("=" * 76)
    print(f"跨引擎迁移矩阵 · {len(rows)} 条")
    print("=" * 76)
    if not_equiv:
        print(f"\n🚫 **must-match 却不等价** {len(not_equiv)} 条（行 {not_equiv[:15]}）")
        print("   → 手感/数值/碰撞/时序**不许以「新引擎更好」为由改动**")
    if no_reason:
        print(f"\n❌ {len(no_reason)} 条偏离未写理由或未分类（行 {no_reason[:15]}）")
        print("   → 四分类必填其一，非 must-match 必须写理由")
    if no_source:
        print(f"\n❌ {len(no_source)} 条缺**原引擎表现**记录（行 {no_source[:15]}）")
        print("   → **先像素级记录原引擎表现，才有资格偏离**")
    if missing:
        print(f"\n⚠️ {len(missing)} 条字段不全")

    if not (not_equiv or no_reason or no_source):
        print("\n✅ 迁移矩阵完整：must-match 已等价、偏离已分类且有理有据")

    print("\n🔑 **先像素级记录原引擎表现，再有意识地偏离。**")
    print("   二次创作的空间在 may-evolve / should-reinvent / explicit-new，")
    print("   **不在 must-match**。")
    return 1 if (a.gate and (not_equiv or no_reason or no_source)) else 0


def main():
    ap = argparse.ArgumentParser(description="跨游戏引擎迁移与二次创作")
    ap.add_argument("--ownership", action="store_true")
    ap.add_argument("--axes", action="store_true")
    ap.add_argument("--map", dest="cmap", action="store_true")
    ap.add_argument("--assets", action="store_true")
    ap.add_argument("--shader", action="store_true")
    ap.add_argument("--physics", action="store_true")
    ap.add_argument("--anim", action="store_true")
    ap.add_argument("--recreate", action="store_true")
    ap.add_argument("--init")
    ap.add_argument("--check")
    ap.add_argument("--gate", action="store_true")
    a = ap.parse_args()
    if a.ownership:
        return cmd_ownership(a)
    if a.axes:
        return cmd_axes(a)
    if a.cmap:
        return cmd_map(a)
    if a.assets:
        return cmd_assets(a)
    if a.shader:
        return cmd_shader(a)
    if a.physics:
        return cmd_physics(a)
    if a.anim:
        return cmd_anim(a)
    if a.recreate:
        return cmd_recreate(a)
    if a.init:
        return cmd_init(a)
    if a.check:
        return cmd_check(a)
    print("❌ 需要 --ownership/--axes/--map/--assets/--shader/--physics/"
          "--anim/--recreate/--init/--check 之一")
    return 2


if __name__ == "__main__":
    sys.exit(main())
