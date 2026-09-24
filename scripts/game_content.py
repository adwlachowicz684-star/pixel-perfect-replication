#!/usr/bin/env python3
"""游戏内容穷尽账本（深化 A / F / G 类）—— **最容易静默丢失的一块**。

**🔑 核心认知**：
> 现有工具链已解决"状态可重放"，但复刻能否完成还取决于
> **内容集合是否相同**：同样的关卡实体集合、触发关系、技能帧事件、
> AI 状态与转移、掉落项、存档字段、成就条件。

**最常见的失败不是程序崩溃**，而是：
某一棵隐藏树 · 某一条跨场景事件链 · 某次稀有无敌帧 ·
某个只在满血时出现的生成点 —— **被静默丢失**。

> **画面相似不能证明隐藏实体、隐藏触发或禁用成就存在。**

用法:
  game_content.py --level      # 关卡实体/触发器/生成点/路径对账
  game_content.py --hidden     # 隐藏内容穷举
  game_content.py --streaming  # 开放世界流式加载
  game_content.py --cutscene   # 过场三条时间轴
  game_content.py --dev        # 调试/作弊功能（**常被忽略但是真实功能**）
  game_content.py --init ledger/level_manifest.csv
  game_content.py --check ledger/level_manifest.csv --gate

退出码: 0 通过 / 1 有缺项或对账不一致 / 2 用法错误
"""
import argparse
import csv
import os
import sys

# 关卡实体必留字段
ENTITY_FIELDS = [
    "稳定 ID", "原型/预制件 ID", "所属图层", "坐标", "旋转", "缩放",
    "激活条件", "引用脚本", "触发器", "生成点", "路径", "收集状态",
    "**隐藏标签**", "序列化版本",
]

# 触发器必须展开为 event_catalog
EVENT_CATALOG = [
    "触发区域或输入", "监听变量", "**门条件**", "延迟", "参与者",
    "**动作列表**", "**取消条件**", "失败回退", "**跨关卡跳转**",
]

# 六类对账
RECON = [
    ("实体", "递归展开场景实例与预制件引用",
     "数量、稳定 ID 集合、关键属性 diff"),
    ("触发器", "从状态机/脚本字节码或事件表反推条件—动作",
     "条件、边、顺序、循环与冲突覆盖率"),
    ("生成点", "**固定种子下多次生成**，记录顺序与失败",
     "生成集合、首次生成帧、失败率"),
    ("路径", "导出路径点、样条参数、循环和朝向",
     "几何误差与重采样轨迹误差"),
    ("**隐藏内容**", "穷举开关、变量、版本、区域组合",
     "状态空间覆盖与隐藏实体回放"),
    ("跨关卡", "记录加载依赖和共享持久对象",
     "**加载图同构**、重复加载幂等"),
]

# 场景序列化三路交叉（**不能只信文件**）
SCENE_TRAPS = [
    ("Unity", "SerializeField / HideInInspector / NonSerialized 与运行时实例"
              "可能使**纯 YAML 导出遗漏数据**",
     "**Editor 导出 + 运行期反射快照 + 打包资产提取 三路交叉**"),
    ("Unreal", "World Partition / Streaming Level / Level Instance / Data Layer —— "
               "**「关卡数」不是稳定单位**",
     "以可寻址世界单元、网格单元、Actor、数据层、运行时加载组为单位"),
    ("Godot", "`.tscn` 文本可读利于 diff，但**继承、场景实例、运行时生成**"
              "可能让静态文件与运行图不一致",
     "静态文件 + 运行图双采样"),
]

HIDDEN_METHODS = [
    "穷举**开关 × 变量 × 版本 × 区域**组合",
    "每个组合回放一次，记录出现/未出现的实体集合",
    "未观测到的组合**标记为 `unconfirmed_reachable`，不得直接删除**",
    "隐藏成就/收集品常依赖**游玩次数、伤害、失败次数**等统计源",
]

STREAMING_FIELDS = [
    "进入半径", "请求帧", "**可见首帧**", "完全加载帧", "卸载帧",
    "Actor 数量", "LOD 切换距离", "依赖单元",
]

STREAMING_RISK = [
    "⚠️ 新引擎**提前卸载使脚本链中断**",
    "⚠️ **延迟加载使生成点错过固定时间窗口**",
    "→ 即使最终画面出现同一建筑，也是 **must-match 偏离**。",
]

# 过场：三条**独立**时间轴
CUTSCENE_TRACKS = [
    ("镜头轨道", "位置/旋转/FOV、目标绑定、阻尼、碰撞、震屏、景深、过渡曲线"),
    ("游戏状态轨道", "角色动画、脚本事件、**跳过规则**、恢复状态"),
    ("字幕与音频轨道", "对话、**字幕显隐时间**、音频样本"),
]

CUTSCENE_FIELDS = [
    "开始/结束时间", "持续时间", "帧率", "**时间模式**",
    "镜头位置/旋转/FOV", "过渡曲线", "字幕显隐时间", "跳过规则", "恢复状态",
]

CUTSCENE_RULES = [
    "⚠️ **不能只比较视频文件** —— 转码会引入时间戳变化，"
    "必须把**内部事件时间与画面帧分开记录**",
    "⚠️ 字幕用**事件边界**验证，**不是 OCR**",
    "⚠️ 音频用**原始样本比对**或已验证的编码签名",
    "⚠️ 逐帧验证**首可跳 / 末可跳 / 跳过后状态重置 / 已发生事件是否补算**",
]

# 调试功能：**是功能，不是开发杂务**
DEV_FEATURES = [
    "控制台命令（含参数、权限、生命周期）",
    "**隐藏菜单 / 调试绘制**",
    "无敌、跳关、生成实体、时间缩放、无消耗",
    "**固定随机种子**",
    "解锁全部、输入回放、日志等级、崩溃报告",
]

DEV_FIELDS = [
    "输入方式", "条件", "副作用", "**是否可持久化**",
    "**是否可存档**", "**发布版是否残留**",
]

DEV_RULE = [
    "🔑 **判定「必须保留 / 应保留 / 可接受移除」前，"
    "应先证明它不是原版功能** —— 不能因为复刻没有而默认不存在。",
    "⚠️ 控制台命令与作弊码在原版是**用户可达功能**，复刻时容易**整个丢失**。",
]

FIELDS = [
    ("item_id", "项编号"),
    ("level_or_scope", "关卡/作用域"),
    ("kind", "类型（entity / trigger / spawner / path / hidden / dependency）"),
    ("legacy_value", "**原版值**"),
    ("new_value", "新引擎值"),
    ("match", "**是否一致**"),
    ("tolerance", "公差（无公差规则的 must-match 会伪失败）"),
    ("evidence", "证据"),
]


def cmd_level(a):
    print("=" * 80)
    print("关卡/场景内容穷尽对账（**不是「打开场景看一看」**）")
    print("=" * 80)
    print("\n每条实体至少保留:")
    for f in ENTITY_FIELDS:
        print(f"   · {f}")
    print("\n触发器必须展开为 `event_catalog`:")
    for e in EVENT_CATALOG:
        print(f"   · {e}")
    print("   🔴 脚本事件**不能只导出函数名** —— 要导出可达条件、调用顺序、")
    print("      参数和副作用目标")
    print("\n六类对账:")
    for k, how, gate in RECON:
        print(f"\n   【{k}】{how}")
        print(f"      门禁: {gate}")
    print("\n场景序列化陷阱（**不能只信文件**）:")
    for eng, trap, fix in SCENE_TRAPS:
        print(f"\n   【{eng}】{trap}")
        print(f"      → {fix}")
    return 0


def cmd_hidden(a):
    print("=" * 76)
    print("隐藏内容穷举（**最容易静默丢失**）")
    print("=" * 76)
    for m in HIDDEN_METHODS:
        print(f"   · {m}")
    print("\n🔑 **画面相似不能证明隐藏实体、隐藏触发或禁用成就存在。**")
    print("   该层必须**独立于画面比较**。")
    return 0


def cmd_streaming(a):
    print("=" * 76)
    print("开放世界流式加载（**不是只截一张完整世界图**）")
    print("=" * 76)
    print("每个流式单元至少记录:")
    for f in STREAMING_FIELDS:
        print(f"   · {f}")
    print("\n风险:")
    for r in STREAMING_RISK:
        print(f"   {r}")
    print("\n录制维度: **玩家路径 × 加载事件 × 内存驻留 Actor × LOD × 遮挡剔除**")
    return 0


def cmd_cutscene(a):
    print("=" * 76)
    print("过场动画（**三条独立时间轴**）")
    print("=" * 76)
    for k, why in CUTSCENE_TRACKS:
        print(f"\n   【{k}】{why}")
    print("\n字段:")
    for f in CUTSCENE_FIELDS:
        print(f"   · {f}")
    print("\n规则:")
    for r in CUTSCENE_RULES:
        print(f"   {r}")
    print("\n验证：分屏 + **差影图** + 轨道曲线叠加 + 事件时序表")
    return 0


def cmd_dev(a):
    print("=" * 78)
    print("调试/作弊/开发者功能（🔴 **是功能，不是开发杂务**）")
    print("=" * 78)
    for f in DEV_FEATURES:
        print(f"   · {f}")
    print("\n每个命令需记录:")
    for f in DEV_FIELDS:
        print(f"   · {f}")
    print("\n规则:")
    for r in DEV_RULE:
        print(f"   {r}")
    return 0


def cmd_init(a):
    os.makedirs(os.path.dirname(a.init) or ".", exist_ok=True)
    with open(a.init, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow([k for k, _ in FIELDS])
        w.writerow(["TODO"] * len(FIELDS))
    print(f"已生成关卡内容账本: {a.init}")
    print("\n⚠️ 六类：entity / trigger / spawner / path / **hidden** / dependency")
    return 0


def cmd_check(a):
    if not os.path.exists(a.check):
        print(f"❌ 文件不存在: {a.check}")
        return 2
    with open(a.check, encoding="utf-8", errors="replace", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        print("❌ 空表 —— **未做内容穷尽**")
        return 1

    def g(r, k):
        return (r.get(k) or "").strip()

    mismatch, no_tol, no_legacy = [], [], []
    for i, r in enumerate(rows, 1):
        m = g(r, "match").lower()
        if m not in ("yes", "y", "true", "是", "一致"):
            mismatch.append(i)
            if not g(r, "tolerance") or g(r, "tolerance") == "TODO":
                no_tol.append(i)
        if not g(r, "legacy_value") or g(r, "legacy_value") == "TODO":
            no_legacy.append(i)

    print("=" * 76)
    print(f"关卡内容账本 · {len(rows)} 条")
    print("=" * 76)
    if mismatch:
        print(f"\n🚫 **内容不一致** {len(mismatch)} 条（行 {mismatch[:15]}）")
        print("   → **某一棵隐藏树、某一条跨场景事件链**被静默丢失，"
              "是游戏复刻最常见的失败")
    if no_tol:
        print(f"\n❌ {len(no_tol)} 条不一致但**未声明公差**（行 {no_tol[:15]}）")
        print("   → 无公差规则的 must-match 会在浮点/跨引擎数学上**伪失败**")
    if no_legacy:
        print(f"\n❌ {len(no_legacy)} 条缺**原版值**（行 {no_legacy[:15]}）")

    if not (mismatch or no_legacy):
        print("\n✅ 内容账本一致且原版值完整")

    print("\n🔑 **画面相似 ≠ 内容相同。**")
    print("   内容指纹层必须**独立于画面比较**。")
    print("\n公差默认规则：")
    print("   · 离散状态/ID/顺序/条件/抽取结果 → **精确匹配**")
    print("   · 世界坐标/路径/镜头轨迹 → **相对误差**")
    print("   · 动画渲染 → 状态一致后单独评价")
    print("   · 随机分布 → 允许统计检验，但 **RNG 序列必须可重放**")
    return 1 if (a.gate and (mismatch or no_legacy)) else 0


def main():
    ap = argparse.ArgumentParser(description="游戏内容穷尽账本")
    ap.add_argument("--level", action="store_true")
    ap.add_argument("--hidden", action="store_true")
    ap.add_argument("--streaming", action="store_true")
    ap.add_argument("--cutscene", action="store_true")
    ap.add_argument("--dev", action="store_true")
    ap.add_argument("--init")
    ap.add_argument("--check")
    ap.add_argument("--gate", action="store_true")
    a = ap.parse_args()
    if a.level:
        return cmd_level(a)
    if a.hidden:
        return cmd_hidden(a)
    if a.streaming:
        return cmd_streaming(a)
    if a.cutscene:
        return cmd_cutscene(a)
    if a.dev:
        return cmd_dev(a)
    if a.init:
        return cmd_init(a)
    if a.check:
        return cmd_check(a)
    print("❌ 需要 --level / --hidden / --streaming / --cutscene / --dev / "
          "--init / --check 之一")
    return 2


if __name__ == "__main__":
    sys.exit(main())
