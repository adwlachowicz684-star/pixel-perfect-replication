#!/usr/bin/env python3
"""持久化状态迁移保真（第十轮 A 类）—— **最高优先级**。

**为什么最高优先级**：
> 已实证过的惨痛教训：旧版配置/数据迁移时某个字段（`clusters`）被
> **静默丢弃**，导致用户数据**永久丢失且无任何提示**。

**🔑 核心认知**：
> **"schema 迁移工具"和"迁移保真验证"是两件事。**
> DDL 完全相同**不代表数据转换无损失**。

**六类静默失败**（**迁移返回成功、但数据语义已变**）—— 本脚本存在的理由。

用法:
  state_migration.py --silent                   # 六类静默失败与检测
  state_migration.py --unknown                  # 未知字段策略（**不许 ignore**）
  state_migration.py --init ledger/migration_fields.csv
  state_migration.py --check ledger/migration_fields.csv --gate
  state_migration.py --fs                       # 路径与文件系统陷阱
  state_migration.py --config                   # 配置位置语义清单

退出码: 0 通过 / 1 有 ignore/未映射/未对账 / 2 用法错误
"""
import argparse
import csv
import os
import sys

# 六类静默失败（**无报错但数据已变**）
SILENT = [
    ("①反序列化忽略未知字段",
     "`serde(default)` / JSON 无该键 / ORM 模型缺列",
     "旧快照 schema 全覆盖；迁移前强制 FORBID_UNKNOWN_FIELDS；**未知字段计数器**",
     "阻断，要求映射或显式存档"),
    ("②列保留但写入空",
     "INSERT 列表漏字段、默认值、复制 SELECT 漏列",
     "列存在性之外**逐列原始值/摘要比对**",
     "阻断并报告业务键"),
    ("③类型/文化转换",
     "`ToString()`、地区数字、日期往返损失",
     "十进制字符串快照、逐字段规范化前后比对",
     "阻断；允许值需有容差契约"),
    ("④枚举未知值被默认值替代",
     "旧库存自由字符串，新模型只认识已知分支",
     "枚举值域覆盖率与未映射值集合",
     "**保留原值或阻断，不允许静默 `Other`**"),
    ("⑤外键/孤儿行",
     "批量插入顺序、软删除、缺失父记录",
     "行数、存在性、外键完整性与孤儿查询",
     "阻断并保留源行 ID"),
    ("⑥写入成功但读取失败",
     "锁、权限、store 未 flush、缓存覆盖",
     "**开/关应用、崩溃、重开后的读回测试**与 breadcrumb",
     "阻断启动并提示修复路径"),
]

# 未知字段策略（**不允许 ignore**）
UNKNOWN_POLICIES = [
    ("passthrough", "**原样保留**为版本化扩展字段", "✅ 允许"),
    ("canonicalize", "按**批准的**归一化规则转换", "✅ 允许（须有往返/业务样例测试）"),
    ("archive", "脱离主表但进入**只读审计/附件**", "✅ 允许（须证明可检索）"),
    ("ignore", "直接丢弃", "🚫 **禁止** —— 这正是 `clusters` 事故的形式"),
    ("default", "填默认值", "🚫 **禁止** —— 等价于静默改写"),
]

# 迁移矩阵必填字段
FIELDS = [
    ("legacy_location", "原版位置（SQLite 表/列、INI section、registry key、XML、AppData 文件）"),
    ("legacy_type", "旧类型与样例"),
    ("source_version", "来源版本"),
    ("destination_field", "新位置"),
    ("transform", "转换/序列化/规范化规则"),
    ("unknown_policy", "**未知策略**（passthrough/canonicalize/archive）"),
    ("normalization_test", "保真测试 fixture"),
    ("reconciled", "**是否已四层对账**"),
    ("owner", "负责人"),
    ("evidence", "证据链接"),
]

# 四层对账
RECONCILE = [
    ("1 catalog", "表、列、类型、可空、默认值、索引、唯一约束、外键、迁移历史"),
    ("2 cardinality", "每个 fixture 分区的 COUNT(*)、重复键、空值数、最大/最小值"),
    ("3 content", "**按业务键 join**，比较规范化后的字段值；数值与日期用字符串往返快照"),
    ("4 behavior", "旧版与新版**打开同一文档、执行同一操作、关闭再打开**，"
                   "断言状态/MRU/窗口/词典/模板/许可证一致"),
]

# 路径与文件系统陷阱（D 类）
FS_TRAPS = [
    ("长路径", "Windows MAX_PATH 260 / `\\\\?\\` 前缀",
     "⚠️ `\\\\?\\` **不是可选项，也不应无条件剥离** —— 部分旧 API/Shell 不接受 UNC"),
    ("8.3 短名", "SFN 与 LFN 不一致", "迁移前枚举"),
    ("大小写", "NTFS 不敏感 / ext4 敏感 / APFS 默认不敏感",
     "⚠️ **不能在内存里无脑 to_lowercase()** —— Turkish dotted i、Unicode 映射"),
    ("符号链接 / junction / hardlink / reparse", "跨设备移动**不能保留 hardlink**", "迁移前扫描"),
    ("NTFS ADS 备用数据流", "**移到 FAT32/exFAT、zip、邮件、Linux 时可能静默永久丢失**",
     "迁移前枚举并显式搬运"),
    ("文件锁", "Windows **强制锁** vs Unix 建议锁",
     "⚠️ 被打开时 `rename`/`replace` 可能**失败**而不只是等待"),
    ("原子写", "**写临时文件 → fsync → rename**",
     "⚠️ `tempfile` 只解决临时文件，**不自动做最终替换**"),
    ("回收站", "移动到回收站 vs 永久删除", "**必须成为显式产品决策**"),
    ("路径规范化", "`/` vs `\\`、`.`/`..`、UNC、驱动器字母",
     "分层：**显示路径 / 系统路径 / 存储路径 / 审计路径**"),
]

CONFIG_LOCS = [
    "app.config",
    "用户 scope `user.config`（ClickOnce / SettingsProvider）",
    "**AppData\\Roaming / Local / LocalLow**",
    "ProgramData",
    "HKCU / HKLM registry",
    "INI / XML / JSON",
    "**最近文件 MRU**",
    "窗口状态（**须保留监视器布局快照**）",
    "自定义词典",
    "模板",
    "许可证/激活状态",
    "缓存（可重建）",
]

CONFIG_PITFALLS = [
    "⚠️ Windows **INI File Mapping** 会让部分 `GetPrivateProfile*` 调用"
    "**从注册表返回数据** —— 只复制 .ini 会得到空配置。"
    "读取旧版时应**同时枚举文件与对应注册表映射**。",
    "⚠️ 配置迁移必须区分「**用户偏好**」（默认保留）与「**内部状态**」（可重建）。",
    "⚠️ 许可证/激活可能受 **EULA 与机器绑定约束**，"
    "**不能直接复制哈希** —— 应进入「待用户确认/重新激活」状态并保留原文件。",
    "⚠️ MRU 中失效路径**不应静默消失**，应标记为不可用并允许逐项修复。",
    "⚠️ 多显示器或 DPI 不可达时，**不得把窗口放在屏外**。",
]


def cmd_silent(a):
    print("=" * 78)
    print("六类静默失败（**迁移返回成功，但数据语义已变**）")
    print("=" * 78)
    for name, why, detect, action in SILENT:
        print(f"\n【{name}】")
        print(f"   为什么无报错: {why}")
        print(f"   检测方法:     {detect}")
        print(f"   默认处置:     {action}")
    print("\n🔑 **「schema 迁移工具」和「迁移保真验证」是两件事** ——")
    print("   DDL 完全相同**不代表数据转换无损失**。")
    print("\n🔑 迁移脚本最常见的失败**不是报错**，")
    print("   而是「**读取时已经看不到旧数据**」：先删旧库、先覆盖配置、")
    print("   把旧路径重命名后再迁移、用新应用打开旧文件触发自动升级、")
    print("   WebView 缓存与用户 store 并发写。")
    print("\n   修复：**取证—迁移—运行三段彻底隔离** ——")
    print("   只读挂载或副本原版数据；迁移器不可改变源；所有写先进入 staging；")
    print("   启动新应用前记录 source checksum；完成后生成 `migration_receipt.json`。")
    print("   **没有 receipt 时新应用不得把状态标为「最新」。**")
    return 0


def cmd_unknown(a):
    print("=" * 74)
    print("未知字段策略（**一等字段**）")
    print("=" * 74)
    for k, what, ok in UNKNOWN_POLICIES:
        print(f"\n   【{k}】{what}")
        print(f"      {ok}")
    print("\n⚠️ **未知字段/未知消息必须暴露给用户**，但**不能暴露实现细节**：")
    print("   ✗ 「JSON 字段 clusters 未映射」")
    print("   ✓ 「旧版 X 中有 N 项集群设置未自动识别，可保留为高级数据")
    print("      并联系迁移支持；继续前这些设置不会生效」")
    print("   技术细节进入诊断包。")
    print("\n⚠️ 若用户选择丢弃，也必须记录**明确同意、影响项、时间、操作者**；")
    print("   **不允许默认勾选**。")
    print("\n四层对账:")
    for k, why in RECONCILE:
        print(f"   【{k}】{why}")
    print("\n⚠️ 双向对账应在旧源和新目标之间**闭环**，")
    print("   **不是只校验「新库有没有数据」**。")
    return 0


def cmd_fs(a):
    print("=" * 76)
    print("路径与文件系统陷阱（跨平台隐形杀手）")
    print("=" * 76)
    for k, what, note in FS_TRAPS:
        print(f"\n   【{k}】{what}")
        print(f"      {note}")
    print("\n⚠️ 路径规范化必须分四层：")
    print("   **显示路径 / 系统路径 / 存储路径 / 审计路径** —— 不要混用三者。")
    print("   `normpath` 做词法清理（`canonicalize` 会做 I/O、解析符号链接并可能失败）；")
    print("   `dunce::simplified` 处理 UNC（跨平台 no-op）。")
    return 0


def cmd_config(a):
    print("=" * 74)
    print("配置位置语义清单（**先穷尽位置，再谈格式转换**）")
    print("=" * 74)
    for c in CONFIG_LOCS:
        print(f"   · {c}")
    print("\n坑:")
    for p in CONFIG_PITFALLS:
        print(f"   {p}")
    print("\n`config-migration-report.json` 至少含：")
    for f in ["每个 source 是否存在", "读取成功", "目标字段", "是否未知",
              "是否敏感", "是否需要用户确认", "是否可重建", "迁移版本", "hash"]:
        print(f"   · {f}")
    return 0


def cmd_init(a):
    os.makedirs(os.path.dirname(a.init) or ".", exist_ok=True)
    with open(a.init, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow([k for k, _ in FIELDS])
        w.writerow(["TODO"] * len(FIELDS))
    print(f"已生成迁移字段矩阵: {a.init}")
    print("\n⚠️ **第一步先冻结旧版证据，而不是先写新 schema。**")
    print("   ProcMon 4.1 / ETW / 旧 logging / SQLite+配置 dump → 三份原始证据库")
    print("   → 然后才生成迁移矩阵。")
    return 0


def cmd_check(a):
    if not os.path.exists(a.check):
        print(f"❌ 文件不存在: {a.check}")
        return 2
    with open(a.check, encoding="utf-8", errors="replace", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        print("❌ 空表")
        return 2

    def g(r, k):
        return (r.get(k) or "").strip()

    ignore_rows, todo_policy, unreconciled, no_fixture, missing = [], [], [], [], []
    for i, r in enumerate(rows, 1):
        pol = g(r, "unknown_policy").lower()
        if pol in ("ignore", "default", "skip", "丢弃", "忽略"):
            ignore_rows.append(i)
        if not pol or pol in ("todo", "待填", "—"):
            todo_policy.append(i)
        rec = g(r, "reconciled").lower()
        if rec not in ("yes", "y", "true", "是", "已对账"):
            unreconciled.append(i)
        if not g(r, "normalization_test") or g(r, "normalization_test") == "TODO":
            no_fixture.append(i)
        miss = [k for k, _ in FIELDS
                if not g(r, k) or g(r, k) in ("TODO", "待填", "—")]
        if miss:
            missing.append((i, miss))

    print("=" * 74)
    print(f"迁移字段矩阵 · {len(rows)} 条")
    print("=" * 74)
    if ignore_rows:
        print(f"\n🚫 **ignore/default 策略** {len(ignore_rows)} 条（行 {ignore_rows[:15]}）")
        print("   → **禁止**。这正是 `clusters` 事故的直接形式 ——")
        print("     未知数据必须 passthrough / canonicalize / archive。")
    if todo_policy:
        print(f"\n❌ {len(todo_policy)} 条未知策略未定（行 {todo_policy[:15]}）")
    if unreconciled:
        print(f"\n❌ {len(unreconciled)} 条**未完成四层对账**（行 {unreconciled[:15]}）")
    if no_fixture:
        print(f"\n❌ {len(no_fixture)} 条缺保真测试 fixture（行 {no_fixture[:15]}）")
    if missing:
        print(f"\n⚠️ {len(missing)} 条字段不全")
        for i, miss in missing[:5]:
            print(f"   行{i}: 缺 {', '.join(miss[:5])}")

    if not (ignore_rows or todo_policy or unreconciled or no_fixture):
        print("\n✅ 迁移矩阵完整：无 ignore、策略已定、已对账、有 fixture")

    print("\n⚠️ 回滚的正确含义是「**能证明回到可读旧状态**」，")
    print("   **不是无条件反向执行 DDL** —— 禁止在数据已按新语义写入后重跑旧的破坏性转换。")
    print("   应：旧版快照保持只读 + 保留旧配置备份 + 记录已迁移最大业务版本。")
    print("\n⚠️ **「没有异常」≠「迁移成功」** —— 必须内容对账（第 3 层）。")
    return 1 if (a.gate and (ignore_rows or todo_policy or unreconciled
                             or no_fixture)) else 0


def main():
    ap = argparse.ArgumentParser(description="持久化状态迁移保真")
    ap.add_argument("--silent", action="store_true")
    ap.add_argument("--unknown", action="store_true")
    ap.add_argument("--fs", action="store_true")
    ap.add_argument("--config", action="store_true")
    ap.add_argument("--init")
    ap.add_argument("--check")
    ap.add_argument("--gate", action="store_true")
    a = ap.parse_args()

    if a.silent:
        return cmd_silent(a)
    if a.unknown:
        return cmd_unknown(a)
    if a.fs:
        return cmd_fs(a)
    if a.config:
        return cmd_config(a)
    if a.init:
        return cmd_init(a)
    if a.check:
        return cmd_check(a)
    print("❌ 需要 --silent / --unknown / --fs / --config / --init / --check 之一")
    return 2


if __name__ == "__main__":
    sys.exit(main())
