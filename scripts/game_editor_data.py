#!/usr/bin/env python3
"""编辑器与构建管线 + 数据驱动配置层（深化第五轮 A / B 类）。

**🔑 A 类核心**：
> 编辑器和导入设置不是"开发工具"，而是**原版行为的固化层**。
> 同一张法线贴图在重压缩、sRGB/线性解释、mip 偏差、各向异性或纹理组
> 不同的情况下，**画面会改变**。

**🔑 B 类核心**：
> **数值并非天然外置** —— 必须先证明配置边界，再谈改表。
> 没有抓到原版「读表」痕迹就断言"所有数值可热更"是错误的。

用法:
  game_editor_data.py --editor       # 编辑器六张清单
  game_editor_data.py --import       # **导入设置是体验参数**
  game_editor_data.py --build        # 构建七段
  game_editor_data.py --hotreload    # 热重载**四类不能统称 reload**
  game_editor_data.py --config       # 配置从「表」升级为 schema
  game_editor_data.py --magic        # 魔法数审计
  game_editor_data.py --modifier     # 🔴 buff 叠加的极细细节
  game_editor_data.py --formula      # 数值计算管道与**舍入时机**
  game_editor_data.py --init ledger/editor_data.csv
  game_editor_data.py --check ledger/editor_data.csv --gate

退出码: 0 通过 / 1 缺项 / 2 用法错误
"""
import argparse
import csv
import os
import sys

# 编辑器六张清单
EDITOR_LISTS = [
    ("编辑器功能", "对象/曲线/事件/对话/AI/特效/任务/相机 —— 原版能编辑什么"),
    ("项目模板", "新建项目的默认结构与默认参数"),
    ("自定义工具插件", "内部工具、批处理、校验器"),
    ("**导入管线**", "导入器版本、设置、产物、缓存"),
    ("构建管线", "七段：依赖→编译→收集→烘焙→打包→安装包→部署"),
    ("运行时编辑器", "游戏内调试编辑器、作弊菜单、实时调参"),
]

EDITOR_FIELDS = [
    "原版版本", "入口路径", "输入格式", "输出格式", "配置位置",
    "可脚本化程度", "耗时", "副作用", "**缺陷**", "迁移判定",
]

EDITOR_TRAPS = [
    "❌ 把导入设置完全交给编辑器默认值 → **破坏跨机器复现**",
    "❌ 「打开项目即全部重新导入」→ 掩盖了导入参数与缓存",
    "❌ 美术源文件、烘焙产物、运行时资产混在同一目录 → diff 与回滚失去意义",
    "❌ 依赖人工记忆「这个模型要改一下再导出」→ 把 must-match 交给个人经验",
]

# 导入设置：**资产"如何解释"**
IMPORT_FIELDS = [
    "source_path", "**stable_id**", "**importer_version**",
    "**source_hash**", "**settings_hash**", "last_imported_at",
    "platform_overrides", "warnings", "produced_artifacts",
]

IMPORT_MUST_MATCH = [
    "mesh_topology", "**tangent_space**", "**compression_error**",
    "normal_smoothing", "骨骼简化", "网格焊接", "法线平滑组",
    "根运动烘焙", "mipmap", "各向异性", "纹理组", "sRGB/线性解释",
]

IMPORT_RULE = [
    "🔑 指纹 = 源资产内容哈希 + **导入器版本** + **导入设置哈希** + 平台覆盖",
    "🔑 输出目录**只读**；源资产、缓存、包体、符号**分别隔离**",
    "⚠️ 资产不是「有没有」，而是「**如何解释**」",
]

# 构建七段
BUILD_STAGES = [
    "依赖解析", "代码编译", "资产收集", "资产烘焙",
    "资源打包", "安装包生成", "安装/部署",
]

BUILD_RECORD = [
    "输入清单", "输出清单", "工具版本", "命令", "环境变量", "目标平台",
    "CPU/内存", "耗时", "**缓存键**", "退出码",
]

BUILD_CACHE = [
    "🔑 每个产物记录 source hash · tool version · flags · environment · "
    "input order · dependency closure",
    "🔑 目录输出**固定顺序**；时间戳**只在 manifest 中记录**",
    "🔑 安装包同时保留：原始包 · 重新签名包 · **符号** · manifest · "
    "**SBOM** · 构建日志",
    "🔑 资源包记录 chunk graph · 依赖闭包 · 压缩格式 · 平台 ABI · "
    "**补丁差量基版本**",
    "→ 这样版本指纹才是**可回放的构建 DAG**，不是单文件哈希",
]

# 热重载：**四类不能统称 reload**
HOTRELOAD = [
    ("Resource", "只替换 GPU/音频/序列化对象",
     "替换贴图后现存实例是否变、引用是否断裂", "全部实例一致"),
    ("Config", "读取配置表，**必须校验 schema 并原子切换**",
     "中途改数值后，已有实体何时、按什么顺序重算", "**与原版帧对齐**"),
    ("Script", "涉及函数、闭包、模块、状态迁移",
     "旧模块函数、闭包、upvalue 如何迁移", "与原版行为一致"),
    ("Native", "旧符号、新符号、ABI、静态状态、回滚",
     "结构字段增删后旧对象是否仍能访问", "**不支持即明确为不支持**"),
    ("State", "热重载过程中输入/动画/物理是否暂停", "—", "与原版一致"),
    ("Determinism", "重载前后同一 seed 回放是否仍一致", "—", "允许重录输入起点"),
]

HOTRELOAD_NOTE = [
    "🔴 **数据热重载若非原子切换** → 正在进行的战斗读到**半新半旧状态**",
    "⚠️ 「语言可用」**不等于「热更新可靠」** —— Lua 官方镜像并不规则更新、"
    "发布从 lua.org 下载",
    "⚠️ 原生代码热重载**必须记录**旧符号/新符号/ABI/静态状态/回滚",
]

# 配置
CONFIG_SOURCES = [
    "csv · tsv · xls · xlsx · xlsm · json · xml · yaml · lua",
]

CONFIG_CAPABILITIES = [
    "**OOP 类型继承**",
    "多语言代码生成（C#/Java/Go/C++/Lua/Python/JS/TS/Rust/PHP/Erlang/Godot）",
    "**机器可读 schema**", "校验与报错", "CLI", "模块化插件",
]

CONFIG_RULES = [
    "🔑 配置表不只是 Excel —— **schema、校验、代码生成**才是可演进性",
    "⚠️ Excelize 只是**纯 Go 的表格读写库**，**无 schema 或代码生成能力** —— "
    "应放表格解析层，**不能冒充配置系统**",
    "✅ Luban 适合作为**配置管线候选**，不是「能自动还原原版数据」",
]

MAGIC_FIELDS = [
    "value", "unit", "observed_effect", "**reverse_engineered_formula**",
    "original_location", "configurable_now",
]

MAGIC_RULE = [
    "🔑 每个可调值记录：源文件 · 行号 · 字段路径 · 数据类型 · 合法范围 · "
    "默认值 · **是否运行时可变** · 是否有本地化 · **是否进入存档** · "
    "热重载语义 · 负责人",
    "🔴 没有抓到原版「读表」痕迹时，应标 **`externalization_unknown`** —— "
    "**不能因项目使用 Lua 就断言所有数值均可热更**",
]

# 🔴 buff 叠加的极细细节
MODIFIER_FIELDS = [
    "source", "category", "**stack_rule**（独立/刷新/覆盖/上限）",
    "duration_model", "tick_interval", "**application_time**", "expire_time",
    "attribute_path", "operation", "**order_key**", "chained_from",
    "**additive_group**", "**multiplicative_group**", "max_rule", "min_rule",
    "**rounding_mode**", "**fractional_state**", "**snapshot_when_applied**",
    "remove_on_death", "**remove_on_save_load**",
]

MODIFIER_TRAPS = [
    "🔴 只记「加 20% 攻击」会漏掉：",
    "   · 与同类**取最高还是相乘**",
    "   · 在**伤害公式内还是公式外**",
    "   · 施加帧 / 持续帧 / **墙钟时间**",
    "   · **小数是否保留到移除**",
    "   · 死亡、换图、**读档后是否残留**",
]

# 数值计算管道
FORMULA_STAGES = [
    "base", "equipment", "permanent_modifier", "additive_buff",
    "multiplicative_buff", "clamp", "**display_rounding**",
]

FORMULA_RECORD = [
    "每个阶段记录：输入精度 · 输出精度 · **舍入时机** · 除零 · 溢出",
]

FORMULA_RULE = [
    "🔑 数值公式必须还原**计算管道**，不是用一句配置表达",
    "⚠️ protobuf 的「未知字段保留、编号兼容」**不能替代业务层**"
    "对删除字段、改单位、改计算公式的迁移",
    "⚠️ protobuf 建议**固定到 release 分支**（main 可能有破坏性变更）",
]

CONFIG_CONFLICTS = [
    "❌ 可视化节点配置界面（搜索弱、diff 难、版本冲突难）—— "
    "不与像素级逐文件审计兼容",
    "❌ 用脚本直接读源表格、让运行时承担全部校验 —— "
    "把数据错误**推迟到 QA**",
    "❌ **删列后复用同名列而保留旧语义** —— 制造不可见回退",
]

FIELDS = [
    ("item_id", "项编号"),
    ("domain", "域（editor / import / build / hotreload / config / magic / modifier / formula）"),
    ("legacy_value", "**原版值**"),
    ("new_value", "新引擎值"),
    ("match", "**是否一致**"),
    ("externalizable", "**是否可外置**（不确定写 unknown）"),
    ("evidence", "证据"),
]


def _hdr(t, w=80):
    print("=" * w)
    print(t)
    print("=" * w)


def cmd_editor(a):
    _hdr("编辑器与工具链（**不是开发工具，是原版行为的固化层**）")
    for k, why in EDITOR_LISTS:
        print(f"\n   【{k}】{why}")
    print("\n每项至少记录:")
    for f in EDITOR_FIELDS:
        print(f"   · {f}")
    print("\n陷阱:")
    for t in EDITOR_TRAPS:
        print(f"   {t}")
    return 0


def cmd_import(a):
    _hdr("🔴 导入设置（**资产「如何解释」，不是「有没有」**）")
    print("最小字段:")
    for f in IMPORT_FIELDS:
        print(f"   · {f}")
    print("\nmust-match 项:")
    for f in IMPORT_MUST_MATCH:
        print(f"   · {f}")
    print("\n规则:")
    for r in IMPORT_RULE:
        print(f"   {r}")
    print("\n⚠️ 同一张法线贴图在重压缩、sRGB/线性解释、mip 偏差、各向异性")
    print("   或纹理组不同的情况下，**画面会改变**。")
    return 0


def cmd_build(a):
    _hdr("构建七段（**从「能出包」到「可证明的增量链路」**）")
    for i, s in enumerate(BUILD_STAGES, 1):
        print(f"   {i}. {s}")
    print("\n每段记录: " + " · ".join(BUILD_RECORD))
    print("\n构建缓存必须可复现:")
    for c in BUILD_CACHE:
        print(f"   {c}")
    return 0


def cmd_hotreload(a):
    _hdr("热重载（🔴 **四类不能统称 reload**）")
    for k, what, probe, gate in HOTRELOAD:
        print(f"\n   【{k}】{what}")
        print(f"      探针: {probe}")
        print(f"      判定: {gate}")
    print("\n注意:")
    for n in HOTRELOAD_NOTE:
        print(f"   {n}")
    return 0


def cmd_config(a):
    _hdr("配置层（**从「表」升级为 schema、代码与迁移链**）")
    print("源格式: " + CONFIG_SOURCES[0])
    print("\n应具备能力:")
    for c in CONFIG_CAPABILITIES:
        print(f"   · {c}")
    print("\n规则:")
    for r in CONFIG_RULES:
        print(f"   {r}")
    print("\n冲突:")
    for c in CONFIG_CONFLICTS:
        print(f"   {c}")
    return 0


def cmd_magic(a):
    _hdr("魔法数审计（🔴 **数值并非天然外置**）")
    for f in MAGIC_FIELDS:
        print(f"   · {f}")
    print("\n规则:")
    for r in MAGIC_RULE:
        print(f"   {r}")
    print("\n🔑 **必须先证明配置边界，再谈改表。**")
    return 0


def cmd_modifier(a):
    _hdr("🔴 modifier / buff（**极细体验集中在应用、叠加、衰减、显示**）")
    for f in MODIFIER_FIELDS:
        print(f"   · {f}")
    print("\n陷阱:")
    for t in MODIFIER_TRAPS:
        print(f"   {t}")
    return 0


def cmd_formula(a):
    _hdr("数值计算管道（**顺序与舍入时机**）")
    print("有序阶段:")
    print("   " + " → ".join(FORMULA_STAGES))
    print("")
    for r in FORMULA_RECORD:
        print(f"   {r}")
    print("\n规则:")
    for r in FORMULA_RULE:
        print(f"   {r}")
    return 0


def cmd_init(a):
    os.makedirs(os.path.dirname(a.init) or ".", exist_ok=True)
    with open(a.init, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow([k for k, _ in FIELDS])
        w.writerow(["TODO"] * len(FIELDS))
    print(f"已生成编辑器/数据表: {a.init}")
    print("\n⚠️ 八域：editor / import / build / hotreload / "
          "config / magic / modifier / formula")
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

    mismatch, no_legacy, weak_ext = [], [], []
    for i, r in enumerate(rows, 1):
        m = g(r, "match").lower()
        if m not in ("yes", "y", "true", "是", "一致"):
            mismatch.append(i)
        if not g(r, "legacy_value") or g(r, "legacy_value") == "TODO":
            no_legacy.append(i)
        ext = g(r, "externalizable").lower()
        if ext in ("assumed", "假设", "maybe", "大概"):
            weak_ext.append(i)

    print("=" * 76)
    print(f"编辑器/数据 · {len(rows)} 条")
    print("=" * 76)
    if mismatch:
        print(f"\n🚫 **不一致** {len(mismatch)} 条（行 {mismatch[:15]}）")
        print("   → 导入设置与数值管道是「如何解释」，直接改变观感与玩法")
    if no_legacy:
        print(f"\n❌ {len(no_legacy)} 条缺**原版值**（行 {no_legacy[:15]}）")
    if weak_ext:
        print(f"\n⚠️  {len(weak_ext)} 条「可外置」为假设（行 {weak_ext[:15]}）")
        print("   → 🔴 **不能因项目用 Lua 就断言所有数值可热更** —— "
              "应标 `externalization_unknown`")

    if not (mismatch or no_legacy):
        print("\n✅ 编辑器/数据：一致且原版值完整")

    print("\n🔑 **数值并非天然外置** —— 先证明配置边界，再谈改表。")
    print("   **导入设置是体验参数**，不是开发工具细节。")
    return 1 if (a.gate and (mismatch or no_legacy)) else 0


def main():
    ap = argparse.ArgumentParser(description="编辑器与数据驱动层")
    ap.add_argument("--editor", action="store_true")
    ap.add_argument("--import", dest="imp", action="store_true")
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--hotreload", action="store_true")
    ap.add_argument("--config", action="store_true")
    ap.add_argument("--magic", action="store_true")
    ap.add_argument("--modifier", action="store_true")
    ap.add_argument("--formula", action="store_true")
    ap.add_argument("--init")
    ap.add_argument("--check")
    ap.add_argument("--gate", action="store_true")
    a = ap.parse_args()
    fns = {"editor": cmd_editor, "imp": cmd_import, "build": cmd_build,
           "hotreload": cmd_hotreload, "config": cmd_config, "magic": cmd_magic,
           "modifier": cmd_modifier, "formula": cmd_formula}
    for k, fn in fns.items():
        if getattr(a, k):
            return fn(a)
    if a.init:
        return cmd_init(a)
    if a.check:
        return cmd_check(a)
    print("❌ 需要 --editor / --import / --build / --hotreload / --config / "
          "--magic / --modifier / --formula / --init / --check 之一")
    return 2


if __name__ == "__main__":
    sys.exit(main())
