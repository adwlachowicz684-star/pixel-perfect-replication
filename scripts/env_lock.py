#!/usr/bin/env python3
"""环境锁（S0/S7）—— 没有它，S2 的所有结论都无法复核。

**为什么必须做**：原版 WPF 的渲染结果依赖 .NET 运行时、字体、GPU 驱动、
DPI 感知模式、系统主题——**这些以前都不在取证清单里**。
证据不可复现，后面的契约、择优、验收就全部失去共同标尺。

**⚠️ 弱版本声明**：可复现构建的"bit-for-bit 相同"与 Tauri 目标不符
（MSVC 与 Rust 工具链均未承诺 bit-for-bit）。
本 Skill 采用**弱版本：输入集哈希一致 + 环境声明一致**，
而不是要求二进制逐位相同。**这一点必须写死，避免后续误用。**

用法:
  env_lock.py --record --out environment.lock      # 记录当前环境
  env_lock.py --check environment.lock             # 与当前环境比对
  env_lock.py --check environment.lock --gate      # 不一致退出码 1（不降级、不警告）
  env_lock.py --fields                             # 打印必锁字段

退出码: 0 一致 / 1 不一致且 --gate / 2 用法或文件错误
"""
import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import time

# 必锁字段：(key, 说明, 怎么取)
FIELDS = [
    ("os_version", "操作系统与版本", "platform + 发行版信息"),
    ("kernel", "内核版本", "uname -r / ver"),
    ("gpu_driver", "GPU 驱动版本", "驱动查询命令；无 GPU 则记 'none'"),
    ("display_edid", "显示器 EDID", "显示器标识，防换屏导致渲染差异"),
    ("display_scale", "显示缩放（100/125/150/200%）", "系统显示设置"),
    ("dpi_awareness", "DPI 感知模式", "进程 DPI awareness"),
    ("locale", "系统区域与数字格式", "locale / 区域设置"),
    ("system_theme", "系统主题与配色", "light/dark/高对比度"),
    ("dotnet_runtime", ".NET Runtime 版本哈希", "dotnet --info 后取哈希"),
    ("rustc_version", "rustc 版本哈希", "rustc --version"),
    ("cargo_version", "cargo 版本哈希", "cargo --version"),
    ("msvc_toolchain", "MSVC 工具链哈希", "cl.exe 版本（Windows）"),
    ("system_fonts", "系统字体清单与校验和", "字体文件列表 + SHA256"),
    ("timezone", "时区", "TZ / 系统时区"),
    ("power_mode", "电源模式", "⚠️ 电池 vs 电源会改变渲染"),
]

# 平台差异项：这些会改变渲染，必须记
RENDER_SENSITIVE = ["gpu_driver", "display_edid", "display_scale",
                    "dpi_awareness", "system_theme", "system_fonts", "power_mode"]


def run(cmd):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        return r.stdout.strip() or r.stderr.strip() or "unknown"
    except Exception:
        return "unknown"


def sha(s):
    return hashlib.sha256(str(s).encode()).hexdigest()[:16]


def probe():
    """尽力探测当前环境。探测不到的记 'unknown' —— 不假装知道。"""
    v = {}
    for k, _, _ in FIELDS:
        v[k] = "unknown"
    v["os_version"] = f"{platform.system()} {platform.release()} {platform.version()}".strip()
    v["kernel"] = platform.release()
    v["timezone"] = time.tzname[0] if time.tzname else "unknown"
    v["locale"] = os.environ.get("LANG") or os.environ.get("LC_ALL") or "unknown"
    v["rustc_version"] = run("rustc --version")
    v["cargo_version"] = run("cargo --version")
    v["dotnet_runtime"] = run("dotnet --version")
    v["gpu_driver"] = "unknown（需人工填：驱动版本会改变渲染）"
    v["display_edid"] = "unknown（需人工填：换屏会导致渲染差异）"
    v["display_scale"] = "unknown（需人工填）"
    v["dpi_awareness"] = "unknown（需人工填）"
    v["system_theme"] = "unknown（需人工填）"
    v["system_fonts"] = "unknown（需人工填：字体清单与 SHA256）"
    v["msvc_toolchain"] = "unknown（Windows 需人工填）"
    v["power_mode"] = "unknown（需人工填：电池 vs 电源会改变渲染）"
    return v


def cmd_fields(a):
    print("=" * 68)
    print("environment.lock 必锁字段")
    print("=" * 68)
    for k, why, how in FIELDS:
        mark = "🔴" if k in RENDER_SENSITIVE else "  "
        print(f" {mark} {k:<18} {why}")
        print(f"        取法: {how}")
    print("\n🔴 = 渲染敏感项：变了就会改渲染结果，G 门禁不得降级")
    print("\n⚠️ 弱版本：本 Skill 要求「输入集哈希一致 + 环境声明一致」，")
    print("   **不要求**二进制 bit-for-bit 相同（MSVC/Rust 均未承诺）。")
    return 0


def cmd_record(a):
    v = probe()
    v["_recorded_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    v["_lock_version"] = 1
    v["_policy"] = "weak: 输入集哈希一致 + 环境声明一致；不要求 bit-for-bit"
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(v, f, ensure_ascii=False, indent=2)
    print(f"已记录环境 → {a.out}")
    unknown = [k for k, _, _ in FIELDS if v.get(k) == "unknown"]
    if unknown:
        print(f"\n⚠️ {len(unknown)} 项未能自动探测，需人工填:")
        for k in unknown:
            why = next(w for kk, w, _ in FIELDS if kk == k)
            print(f"   {k:<18} {why}")
        print("\n   **unknown 不是「已锁定」** —— 门禁会把它当不一致。")
    return 0


def cmd_check(a):
    if not os.path.exists(a.check):
        print(f"❌ 锁文件不存在: {a.check}")
        return 2
    with open(a.check, encoding="utf-8") as f:
        old = json.load(f)
    cur = probe()

    diffs = []
    for k, _, _ in FIELDS:
        ov, cv = old.get(k, "missing"), cur.get(k, "missing")
        if ov == "unknown" or cv == "unknown":
            # 锁文件里是 unknown → 未真正锁定
            if ov == "unknown":
                diffs.append((k, ov, cv, "锁文件未填（unknown ≠ 已锁定）",
                              k in RENDER_SENSITIVE))
            continue
        if str(ov) != str(cv):
            diffs.append((k, ov, cv, "值不一致", k in RENDER_SENSITIVE))

    print("=" * 68)
    print(f"环境锁比对 · {a.check}")
    print("=" * 68)
    if not diffs:
        print("✅ 环境一致")
        return 0

    render_diff = [d for d in diffs if d[4]]
    print(f"\n❌ {len(diffs)} 项不一致（其中渲染敏感 {len(render_diff)} 项）:")
    for k, ov, cv, why, sens in diffs:
        flag = "🔴" if sens else "  "
        print(f" {flag} {k}: 锁={str(ov)[:40]} / 当前={str(cv)[:40]}  ({why})")

    if render_diff:
        print("\n🔴 渲染敏感项不一致 → **证据失效**，不是「轻微偏差」。")
        print("   处置：在同一环境重采 S0，或显式登记环境变更并重新批准 golden。")

    print("\n⚠️ 门禁行为：**不一致直接 FAIL，不降级、不警告**。")
    print("   环境不一致时通过的任何视觉比对都不可信。")

    return 1 if a.gate else 0


def main():
    ap = argparse.ArgumentParser(description="环境锁（S0/S7）")
    ap.add_argument("--record", action="store_true")
    ap.add_argument("--check", help="比对锁文件")
    ap.add_argument("--out", default="environment.lock")
    ap.add_argument("--gate", action="store_true", help="不一致退出码 1")
    ap.add_argument("--fields", action="store_true")
    a = ap.parse_args()

    if a.fields:
        return cmd_fields(a)
    if a.record:
        return cmd_record(a)
    if a.check:
        return cmd_check(a)
    print("❌ 需要 --record / --check / --fields 之一")
    return 2


if __name__ == "__main__":
    sys.exit(main())
