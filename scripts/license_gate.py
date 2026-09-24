#!/usr/bin/env python3
"""许可与字体门禁（L 类）—— 把"待确认"升级为可阻断的 SPDX/SBOM 状态机。

**为什么要做**：目前 `asset_inventory.py` 只对字体/音效/图标/图片标"待确认"，
但没有状态机、没有阻断能力。字体许可是像素级复刻**最容易忽略的红线**：
同一字体家族不同字重、不同厂商、不同分发渠道规则可能完全不同。

四态（不是统一标"待确认"）:
  confirmed_allowed     有许可证文本 + 允许当前使用方式 + 留存证据  ✅ 放行
  confirmed_restricted  需替换 / 需联系授权 / 需改变交付方式        ❌ 阻断
  unknown_evidence      发现组件但许可证证据不足                    ❌ 阻断
  not_applicable        内部自研代码且通过审批                      ✅ 放行

用法:
  license_gate.py --init ledger/licenses.md              # 生成台账骨架
  license_gate.py --check ledger/licenses.md             # 校验（软）
  license_gate.py --check ledger/licenses.md --gate      # 有阻断项退出码 1
  license_gate.py --scan-bom                             # 打印各生态 SBOM 工具

退出码: 0 无阻断 / 1 有阻断项 / 2 用法或文件错误
"""
import argparse
import os
import re
import sys

# 四态
ALLOWED = "confirmed_allowed"
RESTRICTED = "confirmed_restricted"
UNKNOWN = "unknown_evidence"
NOT_APP = "not_applicable"
BLOCKING = (RESTRICTED, UNKNOWN)

STATUS_HELP = {
    ALLOWED: "✅ 放行 —— 有许可证文本、允许当前使用方式、已留存证据",
    RESTRICTED: "❌ 阻断 —— 需替换 / 联系授权 / 改变交付方式",
    UNKNOWN: "❌ 阻断 —— 发现组件但许可证证据不足",
    NOT_APP: "✅ 放行 —— 仅限内部自研代码且通过审批",
}

# 字体许可必须逐项确认（不能凭"网上找到免费版"推断）
FONT_FIELDS = [
    ("font_name", "字体名"),
    ("version", "版本"),
    ("copyright", "版权声明"),
    ("trademark", "商标声明"),
    ("embedding", "是否允许嵌入（文档/应用内嵌）"),
    ("subsetting", "是否允许子集化"),
    ("redistribution", "是否允许再分发"),
    ("web_hosting", "是否允许 Web 托管（@font-face）"),
    ("modification", "是否允许修改"),
    ("source_url", "来源链接"),
    ("evidence_link", "证明链接（EULA / LICENSE / OFL FAQ）"),
]

# 各生态 SBOM / 许可扫描工具（真实仓库）
BOM_TOOLS = {
    "ScanCode Toolkit": ("aboutcode-org/scancode-toolkit",
                         "许可证、版权、包与依赖扫描；适合源码与二进制批量"),
    "Syft": ("anchore/syft", "生成 SPDX/CycloneDX SBOM"),
    "Grype": ("anchore/grype", "消费 SBOM 做漏洞匹配"),
    "cargo-deny": ("EmbarkStudios/cargo-deny",
                   "Cargo workspace 的许可 / 通告 / 来源 / 重复依赖治理"),
    "license-checker": ("dav glass 同名 npm 包生态", "Node 依赖许可清单"),
    "pip-licenses": ("raimon49/pip-licenses", "Python 依赖许可清单"),
    "licensee": ("licensee/licensee", "按文本匹配识别开源许可证"),
    "REUSE": ("reuse-tool/reuse", "让许可与版权信息机器可读"),
    "ClearlyDefined": ("clearlydefined", "汇总组件许可与来源数据"),
}

TEMPLATE = """# 许可合规台账 `ledger/licenses.md`

> 四态：{allowed} / {restricted} / {unknown} / {na}
> **{restricted} 与 {unknown} 阻断交付 —— 不许用功能完成替代许可完成。**
> 校验：`python3 scripts/license_gate.py --check ledger/licenses.md --gate`

## 一、一般组件

| 编号 | 组件 | 类别 | 来源 | SPDX | 使用方式 | 状态 | 证据链接 |
|---|---|---|---|---|---|---|---|
| LIC-001 | Custom.ttf | font | 官网下载 | 待定 | 应用内嵌 | {unknown} | — |
| LIC-002 | click.wav | audio | 素材站 | CC-BY-4.0 | 随包分发 | {allowed} | 需署名，署名位置见下 |
| LIC-003 | icons | icon | 图标库 | MIT | 随包分发 | {allowed} | 保留版权声明 |

## 二、字体专项（逐项确认，不许凭"免费版"推断）★★

{font_table}

**⚠️ 字体是像素级复刻最容易忽略的红线。**
同一家族不同字重、不同厂商、不同分发渠道规则可能完全不同。
建议用 FontBakery 做字体文件质量检查，结合 OFL FAQ / SIL 许可文本 / 厂商 EULA 人工判定。

## 三、SBOM（新旧两侧都要生成）

```bash
# 新版（按实际生态选）
syft packages dir:. -o spdx-json > bom.tauri-react.spdx.json
cargo deny check licenses

# 原版嵌入组件
scancode --license --copyright --package <原版目录> -o bom.original.json
```

两版 SBOM 做差集：新增 / 移除 / 许可变化 / 安全风险。
**SBOM 必须同时覆盖新版依赖与原版嵌入组件**（WPF 安装包、MSIX/AppX、原生 DLL、运行时）。
"""


def cmd_init(a):
    os.makedirs(os.path.dirname(a.init) or ".", exist_ok=True)
    font_table = "| 字段 | 值 |\n|---|---|\n" + \
        "\n".join(f"| {k} | 待填 —— {v} |" for k, v in FONT_FIELDS)
    body = TEMPLATE.format(allowed=ALLOWED, restricted=RESTRICTED,
                           unknown=UNKNOWN, na=NOT_APP, font_table=font_table)
    with open(a.init, "w", encoding="utf-8") as f:
        f.write(body)
    print(f"已生成许可台账骨架: {a.init}")
    print("\n四态说明:")
    for k, v in STATUS_HELP.items():
        print(f"   {k:<22} {v}")
    return 0


def cmd_check(a):
    if not os.path.exists(a.check):
        print(f"❌ 文件不存在: {a.check}")
        return 2
    with open(a.check, encoding="utf-8", errors="replace") as f:
        text = f.read()

    rows = [l for l in text.splitlines()
            if l.strip().startswith("|") and not re.match(r"^\|[\s\-:|]+\|$", l.strip())]
    header = None
    items = []
    for l in rows:
        cells = [c.strip() for c in l.strip().strip("|").split("|")]
        if header is None:
            if "状态" in cells:
                header = cells
            continue
        if len(cells) != len(header):
            continue
        items.append(dict(zip(header, cells)))

    blocking, pending, ok = [], [], []
    for it in items:
        st = it.get("状态", "").strip()
        name = it.get("组件") or it.get("编号") or "?"
        if st in BLOCKING:
            blocking.append((name, it.get("类别", ""), st))
        elif st in (ALLOWED, NOT_APP):
            ok.append(name)
        elif st:
            pending.append((name, st))

    print("=" * 64)
    print(f"许可台账: {len(items)} 条 · 放行 {len(ok)} · 阻断 {len(blocking)}")
    print("=" * 64)

    if blocking:
        print(f"\n❌ 阻断交付 {len(blocking)} 项:")
        for n, c, s in blocking:
            print(f"   [{c or '?'}] {n}  → {s}")
            print(f"        {STATUS_HELP[s]}")
    if pending:
        print(f"\n⚠️  状态未识别 {len(pending)} 项（应填四态之一）:")
        for n, s in pending[:10]:
            print(f"   {n}  → 「{s}」")
        print(f"   四态: {ALLOWED} / {RESTRICTED} / {UNKNOWN} / {NOT_APP}")

    # 字体专项检查
    if "font" in text.lower() or "字体" in text:
        missing = []
        for k, v in FONT_FIELDS:
            m = re.search(rf"\|\s*{k}\s*\|\s*([^|]*?)\s*\|", text)
            val = (m.group(1) if m else "").strip()
            # 「待填 —— xxx」也是未填，不能只判等值
            if not val or re.match(r"^(待填|TODO|—|-|\?)\s*(——.*)?$", val):
                missing.append(f"{k}（{v}）")
        if missing:
            print(f"\n⚠️  字体专项有 {len(missing)} 个字段未填:")
            for m in missing[:12]:
                print(f"   {m}")
            print("   字体许可能分别限制：个人/商用/嵌入/再分发/修改/网页托管/子集化。")

    if not items:
        # 🔴 第五十六轮混沌测试发现：**台账被污染成 0 条时会"无阻断项→通过"**
        print("\n🚫 **台账有效条目为 0** —— 这不是『无阻断项』。")
        print("   🔑 可能原因：文件被截断 / 表头被改 / 分隔符错乱 / 走错文件。")
        print("   🔴 空台账必须**显式失败**，不得静默通过。")
        if a.gate:
            return 1
    elif not blocking and not pending:
        print("\n✅ 许可台账无阻断项")

    print("\n⚠️ 不许用功能完成替代许可完成。")
    print("   允许用更优设计替代原实现，**不允许用侵权替代原版字体**。")

    if a.gate and (blocking or pending):
        return 1
    return 0


def cmd_bom(a):
    print("=" * 64)
    print("SBOM 与许可扫描工具（各生态）")
    print("=" * 64)
    for name, (repo, why) in BOM_TOOLS.items():
        print(f"  {name:<20} {repo}")
        print(f"       {why}")
    print("\n⚠️ ScanCode / Syft 等只处理**自身生态或可扫描目标**，")
    print("   不能替代对 WPF 原版第三方组件的扫描。")
    print("   必须同时生成 bom.original.spdx 与 bom.tauri-react.spdx 再做差集。")
    return 0


def main():
    ap = argparse.ArgumentParser(description="许可与字体门禁（L 类）")
    ap.add_argument("--init", help="生成许可台账骨架")
    ap.add_argument("--check", help="校验许可台账")
    ap.add_argument("--gate", action="store_true", help="有阻断项退出码 1")
    ap.add_argument("--scan-bom", action="store_true", help="打印 SBOM 工具清单")
    a = ap.parse_args()

    if a.init:
        return cmd_init(a)
    if a.check:
        return cmd_check(a)
    if a.scan_bom:
        return cmd_bom(a)
    print("❌ 需要 --init / --check / --scan-bom 之一")
    return 2


if __name__ == "__main__":
    sys.exit(main())
