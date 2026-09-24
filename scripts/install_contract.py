#!/usr/bin/env python3
"""安装契约与残留数据迁移（S2/S6）—— 桌面复刻最大的盲区之一。

**为什么需要**：WPF 程序有安装包、注册表、开始菜单、桌面快捷方式、文件关联、
URL 协议、卸载入口、自动更新。Tauri 默认 MSI **不能自动复刻原版所有安装语义**。
而"用户能不能平滑升级"是产品行为，不是 CI 附属步骤。

**核心认知**：
> **平滑升级的核心不是"能下载新包"，而是残留数据迁移矩阵。**

旧版可能在 AppData / LocalAppData / Roaming / ProgramData / HKCU / HKLM /
SQLite / 日志 / 缓存 / 锁文件 / 字体 / 插件目录留下数据。
新版必须先声明所有权：只读快照 / 迁移 / 兼容 / 双写 / 废弃。

用法:
  install_contract.py --init ledger/install.md
  install_contract.py --check ledger/install.md --gate
  install_contract.py --fields            # 打印必录字段与残留矩阵

退出码: 0 齐全 / 1 --gate 且有缺项或残留无 owner / 2 用法错误
"""
import argparse
import os
import re
import sys

# 必录字段：key, 说明
FIELDS = [
    ("install_scope", "安装范围", "PerUser / PerMachine / Either"),
    ("install_dir", "安装目录", "Program Files / AppData 等"),
    ("product_code", "MSI ProductCode", "升级与卸载标识"),
    ("upgrade_code", "MSI UpgradeCode", "**跨版本升级的锚**"),
    ("shortcuts", "快捷方式", "名称/目标/**参数**/工作目录/图标/显示方式"),
    ("start_menu", "开始菜单项", "⚠️ 需 Shortcut + RemoveFolder + KeyPath，否则卸载残留"),
    ("file_assoc", "文件关联", "扩展名 → ProgID → 打开命令"),
    ("url_protocol", "URL/CLI 协议", "自定义 scheme 与命令行参数"),
    ("registry_keys", "注册表键与值", "HKCU/HKLM 全量"),
    ("services_drivers", "服务与驱动", "含先决运行库（WebView2 等）"),
    ("silent_args", "静默参数", "安装/升级/降级/修复/卸载各自命令行"),
    ("update_mechanism", "更新机制", "Velopack / tauri-plugin-updater / WinSparkle / Omaha"),
    ("signature", "签名与供应链", "安装包、更新包、symbols 均签"),
]

# 残留数据可能位置（每个都要定 owner）
RESIDUE_LOCS = [
    "AppData\\Roaming", "AppData\\Local", "AppData\\LocalLow",
    "ProgramData", "HKCU", "HKLM", "SQLite/本地库", "日志文件",
    "缓存目录", "锁文件", "自装字体", "插件目录", "用户文档目录",
]

# 所有权五选一
OWNERSHIP = ["只读快照", "迁移", "兼容", "双写", "废弃"]

TEMPLATE = """# 安装契约

## 必录字段
{fields}

## 残留数据迁移矩阵

| 位置 | 内容 | Owner（{own}） | schema 版本 | 迁移方式 | 回滚点 | 幂等键 |
|---|---|---|---|---|---|---|
| AppData\\Roaming\\app | config.json | 迁移 | v2 | 事务脚本 + 校验和 | .bak | file_sha |

**⚠️ 每个残留项必须有 owner** —— 没有 owner 的数据在升级时一定会被漏掉。
"""


def cmd_fields(a):
    print("=" * 70)
    print("安装契约必录字段")
    print("=" * 70)
    for k, name, why in FIELDS:
        print(f"   {name:<18} {k}")
        print(f"        {why}")
    print("\n" + "=" * 70)
    print(f"残留数据可能位置（共 {len(RESIDUE_LOCS)} 处，每处都要定 owner）")
    print("=" * 70)
    for loc in RESIDUE_LOCS:
        print(f"   {loc}")
    print(f"\n所有权五选一: {' / '.join(OWNERSHIP)}")
    print("\n⚠️ 迁移脚本必须：事务或临时文件 · 版本上下界 · 校验和 · 回滚点 · 幂等键")
    print("\n工具选择:")
    for t, why in [
        ("WiX Toolset", "**安装契约源码**，不是临时打包脚本（Shortcut schema 可声明全部属性）"),
        ("Velopack", "比 Omaha 更适合复刻 Windows 桌面应用；`--msi` 生成 WiX 5 MSI"),
        ("tauri-plugin-updater", "Tauri 2 内嵌更新（check / downloadAndInstall / relaunch）"),
        ("Omaha", "成熟但重量级 C++/COM，**无硬约束不自建**"),
        ("Sparkle / WinSparkle", "分别只适用 macOS / Win32 原版对照，不能互换"),
    ]:
        print(f"   {t:<24} {why}")
    return 0


def cmd_init(a):
    os.makedirs(os.path.dirname(a.init) or ".", exist_ok=True)
    fields = "\n".join(f"- [ ] **{n}**（`{k}`）— {w}" for k, n, w in FIELDS)
    body = TEMPLATE.format(fields=fields, own=" / ".join(OWNERSHIP))
    with open(a.init, "w", encoding="utf-8") as f:
        f.write(body)
    print(f"已生成安装契约骨架: {a.init}")
    print("\n⚠️ 残留矩阵中每个位置都要定 owner，--gate 会检查。")
    return 0


def cmd_check(a):
    if not os.path.exists(a.check):
        print(f"❌ 文件不存在: {a.check}")
        return 2
    with open(a.check, encoding="utf-8", errors="replace") as f:
        text = f.read()

    print("=" * 68)
    print("安装契约")
    print("=" * 68)

    missing, unchecked, filled = [], [], []
    lines = text.splitlines()
    for k, name, _ in FIELDS:
        hit = None
        for l in lines:
            if k in l or name in l:
                hit = l
                break
        if hit is None:
            missing.append((k, name))
            continue
        # 模板用 `- [ ]` 作待办：未打勾 = 还没录值，不算完成
        low = hit.lstrip()
        if low.startswith("- [ ]") or low.startswith("- [ ]"):
            unchecked.append((k, name))
        elif "- [ ]" in hit:
            unchecked.append((k, name))
        elif "- [x]" in hit or "- [X]" in hit:
            filled.append((k, name))
        else:
            # 无 checkbox：要求该行除字段名外还有实际内容
            rest = hit.replace(name, "").replace(k, "")
            rest = rest.strip(" -|:*`—（）()")
            if not rest or rest in ("TODO", "待填", "未知"):
                unchecked.append((k, name))
            else:
                filled.append((k, name))

    # 残留矩阵：解析表格，检查 owner 列
    rows = [l for l in text.splitlines()
            if l.strip().startswith("|") and not re.match(r"^\|[\s\-:|]+\|$", l.strip())]
    header = None
    no_owner, has_owner = [], 0
    for l in rows:
        cells = [c.strip() for c in l.strip().strip("|").split("|")]
        if header is None:
            if any("Owner" in c for c in cells):
                header = cells
            continue
        if len(cells) != len(header):
            continue
        rec = dict(zip(header, cells))
        own = next((v for k, v in rec.items() if "Owner" in k), "")
        loc = next((v for k, v in rec.items()
                    if "位置" in k or "路径" in k), cells[0])
        if not own or own in ("—", "TODO", "待定"):
            no_owner.append(loc)
        else:
            has_owner += 1

    print(f"   必录字段: {len(filled)}/{len(FIELDS)} 已录值")
    if missing:
        for k, n in missing:
            print(f"      ❌ 缺 {n}（{k}）")
    if unchecked:
        print(f"      ❌ {len(unchecked)} 项仍是待办（- [ ] 未勾 / 值为空）:")
        for k, n in unchecked:
            print(f"         {n}（{k}）")
    print(f"   残留项: {has_owner} 有 owner / {len(no_owner)} 无 owner")
    for loc in no_owner[:12]:
        print(f"      ❌ 无 owner: {loc}")

    # 覆盖率：残留位置是否都提到
    unmentioned = [l for l in RESIDUE_LOCS if l not in text]
    if unmentioned:
        print(f"   未提及的残留位置 {len(unmentioned)} 处: "
              f"{', '.join(unmentioned[:8])}")

    blockers = []
    if missing:
        blockers.append(("字段", f"{len(missing)} 项未录"))
    if unchecked:
        blockers.append(("待办", f"{len(unchecked)} 项未勾/值为空"))
    if no_owner:
        blockers.append(("残留", f"{len(no_owner)} 项无 owner"))
    if unmentioned:
        blockers.append(("残留位置", f"{len(unmentioned)} 处未提及"))

    if not blockers:
        print("\n✅ 安装契约完整")
    else:
        print(f"\n❌ 阻断 {len(blockers)} 类")

    print("\n⚠️ **平滑升级的核心不是「能下载新包」，而是残留数据迁移矩阵。**")
    print("   没有 owner 的数据在升级时一定会被漏掉。")

    return 1 if (a.gate and blockers) else 0


def main():
    ap = argparse.ArgumentParser(description="安装契约与残留数据迁移")
    ap.add_argument("--check")
    ap.add_argument("--init")
    ap.add_argument("--gate", action="store_true")
    ap.add_argument("--fields", action="store_true")
    a = ap.parse_args()

    if a.fields:
        return cmd_fields(a)
    if a.init:
        return cmd_init(a)
    if a.check:
        return cmd_check(a)
    print("❌ 需要 --check / --init / --fields 之一")
    return 2


if __name__ == "__main__":
    sys.exit(main())
