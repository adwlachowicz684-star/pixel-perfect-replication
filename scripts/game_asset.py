#!/usr/bin/env python3
"""游戏资产取证记录（D 类）—— 资产是**逻辑数据**，不是静态附件。

**为什么单独一层**：游戏包常把动画事件、碰撞、关卡脚本、材质参数、音效事件、
字体和本地化混在自定义容器里。桌面应用的"资源"只是图和字体；
**游戏的资产里藏着逻辑**。

**核心纪律**：
> 提取器只负责"抽取"，**不能承担"资产事实源"职责**。
> 每个版本、加密、压缩和平台都可能失效。
> 事实源 = **原版文件哈希 + 版本 + 提取命令 + 输出路径 + 缺失项 + 权利状态**。

**门禁是"结构等价"，不是"重新导入成功"**。

用法:
  game_asset.py --engine                        # 引擎专属工具映射
  game_asset.py --init ledger/game_assets.csv
  game_asset.py --check ledger/game_assets.csv --gate
  game_asset.py --structural                    # 结构等价验收清单

退出码: 0 通过 / 1 缺项 / 2 用法错误
"""
import argparse
import csv
import os
import sys

# 引擎专属工具优先，通用扫描器只兜底
ENGINE_TOOLS = [
    ("Unity", "AssetRipper（GPLv3）资产与 AssetBundle 恢复；"
              "AssetStudio 浏览/导出；Il2CppDumper 从 libil2cpp.so + 元数据恢复类型/字符串/方法表",
     "⚠️ MelonLoader / BepInEx 是**运行时 mod 加载器**，不作离线资产事实源"),
    ("Unreal", "CUE4Parse（Apache-2.0）解析 UE4/UE5 归档/包/纹理/网格/动画/音频；"
               "FModel（GPLv3）浏览器；UAssetAPI 反序列化 UAsset",
     "⚠️ umodel/FModel 是提取器，**不是反编译器**；语义应优先从 UAsset/Blueprint/metadata 恢复"),
    ("Godot", "gdsdecomp（GPLv3）恢复 PCK / GDNative / GDExtension 与脚本", ""),
    ("GameMaker", "UndertaleModTool（GPLv3）读 GMS 1.4 与 GMS2 bytecode 13-17，"
                  "可重建**字节级精确副本**并反汇编", ""),
    ("RPG Maker", "EasyRPG Player / mkxp 是**兼容引擎运行时**，不是资产提取器", ""),
    ("通用归档", "QuickBMS（脚本引擎，覆盖大量游戏归档）、Noesis、Dragon UnPACKer",
     "⚠️ 每个版本/加密/压缩/平台都可能失效 —— **只作兜底**"),
    ("音频", "vgmstream 覆盖数百种游戏编码（ADX/DSP ADPCM/PSX VAG/XMA/HCA/Opus/Vorbis）与循环信息",
     "⚠️ vgmstream **不能**复现游戏内重采样、滤波、音量与 DSP"),
    ("Wwise", "有原工程 → 用 SoundBanksInfo XML/JSON 建事件/bus/Switch/State/参数/media 索引",
     "无工程时社区 .bnk 解析器只能形成**待验证假设**"),
    ("运行时抓取", "NinjaRipper / 3D Ripper DX 通过 D3D wrapper 抓 mesh、顶点属性、索引、纹理、shader",
     "⚠️ 只能识别资源构成，**不能证明原始资产格式或版权可复用**"),
    ("纹理", "DirectXTex / texconv / KTX2 / Basis；注意 BCn 压缩、mip、sRGB 与法线编码", ""),
]

# 资产记录必填字段
FIELDS = [
    ("original_path", "原版路径"),
    ("file_hash", "**原版文件哈希**（事实源）"),
    ("container_version", "容器/版本"),
    ("compression", "压缩方式"),
    ("encryption", "加密状态"),
    ("extract_tool", "提取工具与版本"),
    ("extract_cmd", "提取命令（**可复跑**）"),
    ("output_path", "输出路径"),
    ("mesh_info", "网格：顶点/索引/骨骼/权重"),
    ("texture_info", "纹理：格式/mip/通道/伽马"),
    ("anim_events", "动画事件时间轴"),
    ("collision", "碰撞体"),
    ("lod", "LOD 与切换"),
    ("audio_info", "音频 codec/loop/rate/channels"),
    ("script_ast_hash", "脚本 AST 哈希"),
    ("missing", "缺失项"),
    ("license_status", "**权利状态**（须进 SBOM，不能由工具自动判定）"),
]

# 结构等价验收（不是"导入成功"）
STRUCTURAL = [
    "顶点 winding（顺逆时针）",
    "UV channel 数量与布局",
    "骨骼绑定与权重",
    "**动画事件时间**（错一帧就是手感不同）",
    "碰撞体形状与尺寸",
    "LOD 切换距离",
    "材质属性与参数",
    "纹理 sRGB / 法线编码",
    "mip bias 与采样模式",
    "音频 loop point",
    "事件 trigger 条件",
    "字体度量与 RTL 整形",
]



# ==========================================================================
# 🔑 第五十九轮新增：**白名单枚举** + **跨字段一致性**
#
# 🔴 混沌测试（第五十六～五十八轮）连续三轮发现：本脚本属于 A 类盲区——
#    `--check` 只做**结构性缺失**检查（空值/TODO），
#    🔴 **填任意非法值都静默通过**（黑名单式校验的通病）。
# 🔑 修复：关键字段改为**白名单枚举**；并检测"字段合法但整行自相矛盾"。
# ==========================================================================

# ==========================================================================
# 🔑 第六十一轮新增：**枚举的两类语义必须分开**
#
# 🔴 第六十轮留下的未闭合缺口：这些 `ENUMS` 合法值是**按字段语义推断**的，
#    不是从原版证据提取的。
# 🔑 本轮不是去"补全证据"（那需要原版取证），而是**把语义显式标出来**：
#
#    ENUMS_KIND = 'constraint'  → **校验器输入约束**
#        只用于"防止填错值"，🔴 **不构成 must-match 主张**。
#        例：level 只能是 debug/info/warn——这是我们给表定的填写规范。
#
#    ENUMS_KIND = 'must_match'  → **原版行为事实**
#        枚举本身是 must-match 对象，🔴 **必须由原版证据支撑**，
#        例：某作"处置"字段只有这三种，是原版真实存在的分类。
#
# 🔑 当前全部标为 'constraint' —— **因为我们没有原版证据**。
# 🔴 若某天要把它升为 'must_match'，必须同时补 `evidence` 字段，
#    **不能只改标签**。
# ==========================================================================
ENUMS_KIND = 'constraint'   # 🔴 不是 must-match；升级需附原版证据

ENUMS = {'missing': ('yes', 'no', 'y', 'n', 'true', 'false', '是', '否'), 'license_status': ('ok', 'unknown', 'blocked', 'restricted', '需确认'), 'encryption': ('none', 'unknown', 'aes', 'custom', '有', '无'), 'compression': ('none', 'unknown', 'zlib', 'lz4', 'oodle', '有', '无')}
_CLAIM_OK = {}
_WEAK_EVIDENCE = ('unknown', 'secondhand', 'unverified', '', 'todo')


def _enum_violations(rows, enums=None):
    """🔑 白名单校验：值不在合法枚举内 → 违例。"""
    enums = enums or ENUMS
    out = []
    for i, r in enumerate(rows, 1):
        for k, ok in enums.items():
            v = (r.get(k) or '').strip()
            if not v or v.lower() in ('todo', 'tbd', '待填', '—'):
                continue          # 🔑 结构性缺失由原有逻辑负责
            if v.lower() not in ok:
                out.append((i, k, v))
    return out


def _contradictions(rows, enums=None):
    """🔑 跨字段一致性：**每个字段都合法，但整行在说谎**。"""
    enums = enums or ENUMS
    out = []
    for i, r in enumerate(rows, 1):
        ev = (r.get('evidence') or '').strip().lower()
        for k, claims in _CLAIM_OK.items():
            v = (r.get(k) or '').strip().lower()
            if v in claims and ev in _WEAK_EVIDENCE:
                out.append((i, '`' + k + '`=`' + v + '` 但 evidence=`'
                            + (ev or '(空)') + '`（证据不支持强主张）'))
        conf = (r.get('confidence') or '').strip().lower()
        mt = (r.get('match_type') or '').strip().lower()
        if mt == 'exact' and conf == 'low':
            out.append((i, 'match_type=exact 但 confidence=low（低置信不能声称精确）'))
    return out

def cmd_engine(a):
    print("=" * 74)
    print("引擎专属工具映射（**引擎专用优先，通用只兜底**）")
    print("=" * 74)
    for eng, tools, warn in ENGINE_TOOLS:
        print(f"\n【{eng}】")
        print(f"   {tools}")
        if warn:
            print(f"   {warn}")
    print("\n⚠️ 资产事实源 = 原版制品 + 抽取日志 + 归一产物。")
    print("   重制资产用 `source_hash + transform_hash` 生成 ID；")
    print("   运行时烘焙版本另建 derived artifact。")
    return 0


def cmd_structural(a):
    print("=" * 72)
    print("资产结构等价验收（**不是「重新导入成功」**）")
    print("=" * 72)
    for s in STRUCTURAL:
        print(f"   · {s}")
    print("\n❌ 与理念冲突的做法:")
    for bad in ["能导入引擎即可", "自动转成现代 PBR", "模型重新拓扑后应该更好",
                "音频转 MP3 够用", "字体用近似替代", "提取脚本一键搞定",
                "原版资源可直接自由再分发"]:
        print(f"   · {bad}")
    print("\n⚠️ 改进必须写成**明确决策**，且原版资产、抽取参数、转换参数可追溯；")
    print("   权利状态必须进 SBOM，**不能由工具自动判定**。")
    return 0


def cmd_init(a):
    os.makedirs(os.path.dirname(a.init) or ".", exist_ok=True)
    with open(a.init, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow([k for k, _ in FIELDS])
        w.writerow(["TODO"] * len(FIELDS))
    print(f"已生成资产取证表: {a.init}")
    print("\n⚠️ 留 TODO = 未取证，--gate 会阻断。")
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

    print("=" * 70)
    print(f"资产取证 · {len(rows)} 条")
    print("=" * 70)

    missing_rows, no_license, no_hash = [], [], []
    for i, r in enumerate(rows, 1):
        miss = [k for k, _ in FIELDS
                if not (r.get(k) or "").strip()
                or (r.get(k) or "").strip() in ("TODO", "待填", "—")]
        if miss:
            missing_rows.append((i, miss))
        if not (r.get("license_status") or "").strip() or \
                (r.get("license_status") or "").strip() in ("TODO", "未知"):
            no_license.append(i)
        if not (r.get("file_hash") or "").strip() or \
                (r.get("file_hash") or "").strip() == "TODO":
            no_hash.append(i)

    if missing_rows:
        print(f"\n❌ {len(missing_rows)} 条字段不全:")
        for i, miss in missing_rows[:8]:
            print(f"   行{i}: 缺 {', '.join(miss[:6])}")
    if no_hash:
        print(f"\n❌ {len(no_hash)} 条缺**原版文件哈希** —— 没有哈希就没有事实源")
    if no_license:
        print(f"\n❌ {len(no_license)} 条权利状态未确认 —— 必须进 SBOM")

    if not (missing_rows or no_hash or no_license):
        print("\n✅ 资产取证完整")

    print("\n⚠️ 门禁是**结构等价**，不是「重新导入成功」。")
    print("   见 `game_asset.py --structural`。")
    # 🔑 第五十九轮：白名单违例 + 语义矛盾 也须阻断
    _ev = _enum_violations(rows)
    if _ev:
        print('\n🚫 **字段白名单违例**（🔴 黑名单只查空值，查不出**填错的值**）:')
        for i, k, v in _ev[:12]:
            print(f'   行 {i}: `{k}` = `{v}` 不在合法枚举内')
        print('   🔑 合法值见本文件顶部 ENUMS')
    _ct = _contradictions(rows)
    if _ct:
        print('\n🚫 **跨字段语义矛盾**（🔑 字段合法 ≠ 行自洽）:')
        for i, w in _ct[:12]:
            print(f'   行 {i}: {w}')

    return 1 if (a.gate and (missing_rows or no_hash or no_license or _ev or _ct)) else 0


def main():
    ap = argparse.ArgumentParser(description="游戏资产取证记录")
    ap.add_argument("--engine", action="store_true")
    ap.add_argument("--structural", action="store_true")
    ap.add_argument("--init")
    ap.add_argument("--check")
    ap.add_argument("--gate", action="store_true")
    a = ap.parse_args()

    if a.engine:
        return cmd_engine(a)
    if a.structural:
        return cmd_structural(a)
    if a.init:
        return cmd_init(a)
    if a.check:
        return cmd_check(a)
    print("❌ 需要 --engine / --structural / --init / --check 之一")
    return 2


if __name__ == "__main__":
    sys.exit(main())
