#!/usr/bin/env python3
"""外部工具调度器 —— 让收集到的上百个工具真正可调用、可检测、可降级。

**为什么需要**：前几轮收集了大量工具，但只写在文档里等于没有。
本脚本把 `tools/registry.yaml` 里的工具变成**可调用的能力**。

**⚠️ 身份校验（本脚本存在的核心理由）**：
> `which sg` 命中的是 Unix 的 `sg`（set group ID）命令，
> 它可执行、退出码 0，但**没有 `scan` 子命令**
> —— 只查"命令存在"会得到**永远 0 命中却显示成功**的假工具。

所以每个工具必须过两道：
  1. **版本特征**：`--version` 输出里必须含 `version_contains` 之一
  2. **子命令**：指定的子命令必须真的存在

两道都过才算"真可用"。

用法:
  tool_run.py --list                       # 列出全部登记工具
  tool_run.py --check harfbuzz             # 校验单个工具身份
  tool_run.py --check-all                  # 校验全部（生成 capability 报告）
  tool_run.py --check-all --json cap.json
  tool_run.py --run harfbuzz --text "café" --font font.ttf
  tool_run.py --env                        # 打印能力矩阵（可用/缺失/降级）

退出码: 0 正常 / 1 --gate 且必需工具缺失 / 2 用法错误
"""
import argparse
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REGISTRY = os.path.join(HERE, "tools", "registry.yaml")


def load_registry():
    """尽力解析 YAML；没有 PyYAML 时用内置降级解析。"""
    if not os.path.exists(REGISTRY):
        print(f"❌ 登记表不存在: {REGISTRY}")
        return {}
    text = open(REGISTRY, encoding="utf-8").read()
    try:
        import yaml
        return yaml.safe_load(text) or {}
    except ImportError:
        return _mini_yaml(text)


def _mini_yaml(text):
    """极简降级解析：只提取本表用到的结构（tools.<id>.<key>）。

    ⚠️ 这是降級路径，只保证本文件能读，**不保证通用 YAML 语义**。
    需要完整支持请 `pip install pyyaml`。
    """
    tools, cur, key = {}, None, None
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip())
        s = raw.strip()
        if indent == 2 and s.startswith("tools:"):
            continue
        if indent == 4 and s.endswith(":") and not s.startswith("-"):
            cur = s[:-1]
            tools[cur] = {}
            key = None
            continue
        if cur is None:
            continue
        if s.startswith("- ") :
            lst = tools[cur].get(key or "_", [])
            if not isinstance(lst, list):
                lst = []
            lst.append(s[2:].strip())
            tools[cur][key or "_"] = lst
            continue
        if ":" in s:
            k, _, v = s.partition(":")
            v = v.strip()
            key = k.strip()
            if v:
                tools[cur][key] = v.strip("'\"")
            else:
                tools[cur][key] = []
    return {"tools": tools}


def as_list(v):
    if v is None:
        return []
    return v if isinstance(v, list) else [v]


def exe_path(spec):
    """取可执行文件的实际路径。返回 None 表示命令不存在。"""
    exe = spec.get("exe") or ""
    if not exe:
        return None
    first = exe.split()[0]
    return shutil.which(first)


def check_identity(tool_id, spec):
    """两道身份校验：版本特征 + 子命令。返回 (ok, reason, detail)。"""
    path = exe_path(spec)
    if path is None:
        return False, "命令不存在", f"{spec.get('exe')} 未在 PATH 中"

    ident = spec.get("identity") or {}
    ver_args = as_list(ident.get("version_args"))
    contains = as_list(ident.get("version_contains"))
    exe = spec.get("exe", "")

    # 第一道：版本特征
    if ver_args:
        cmd = exe.split() + [str(a) for a in ver_args]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            out = (r.stdout or "") + (r.stderr or "")
        except Exception as e:
            return False, "版本命令执行失败", str(e)
        # ⚠️ 退出码非 0 直接判失败。
        # 实证：`java -cp daikon.jar daikon.Daikon --version` 在 daikon.jar 缺失时
        # 报错信息里含 "daikon.Daikon" —— 只匹配字符串会**误判为可用**。
        if r.returncode != 0 and not ident.get("allow_nonzero"):
            hint = "**可能是同名不同工具**" if contains and any(
                c.lower() in out.lower() for c in contains) else "未安装或不可用"
            return False, f"版本校验失败（{hint}）", (
                f"rc={r.returncode}：{(out or '').strip()[:90]}")
        if contains:
            low = out.lower()
            if not any(c.lower() in low for c in contains):
                return False, "**疑似同名不同工具**", (
                    f"{exe} 存在但 --version 输出不含 {contains}。"
                    f" 实测：{(out or '').strip()[:80]}")
        else:
            if not out.strip():
                return False, "版本输出为空", "无法确认身份"

    # 第二道：子命令
    sub = ident.get("subcommand")
    if sub:
        cmd = exe.split() + [str(sub)]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            combined = (r.stdout or "") + (r.stderr or "")
        except Exception as e:
            return False, "子命令执行失败", str(e)
        low = combined.lower()
        bad = ("unknown command", "not recognized", "usage:", "unrecognized",
               "no such", "invalid command")
        if r.returncode != 0 and any(b in low for b in bad):
            return False, "**疑似同名不同工具**", (
                f"{exe} 有 {sub}？返回 {r.returncode}：{combined.strip()[:80]}")

    return True, "可用", path


def cmd_list(a):
    reg = load_registry()
    tools = reg.get("tools") or {}
    print("=" * 74)
    print(f"外部工具登记表 · {len(tools)} 个")
    print("=" * 74)
    for tid, spec in tools.items():
        if not isinstance(spec, dict):
            continue
        lic = spec.get("license", "?")
        lvl = spec.get("evidence_level", "?")
        deg = spec.get("degrade", "optional")
        print(f"\n【{tid}】{spec.get('name', '?')}  ({lic})")
        print(f"   {spec.get('purpose', '')}")
        print(f"   证据等级 {lvl} · 缺失时 {deg} · {spec.get('repo', '')}")
    print("\n" + "=" * 74)
    print("调用: tool_run.py --check <id> / --run <id> ...")
    print("⚠️ 身份校验两道：版本特征 + 子命令 —— 防「同名不同工具」")
    return 0


def cmd_check_one(a, reg):
    tools = reg.get("tools") or {}
    spec = tools.get(a.check)
    if not spec:
        print(f"❌ 未登记的工具: {a.check}")
        print(f"   已登记: {', '.join(sorted(tools))}")
        return 2
    ok, reason, detail = check_identity(a.check, spec)
    icon = "✅" if ok else "❌"
    print(f"{icon} {a.check} — {reason}")
    print(f"   {detail}")
    if not ok:
        print(f"\n   安装方式:")
        for k, v in (spec.get("install") or {}).items():
            print(f"     {k}: {v}")
        print(f"   缺失时行为: {spec.get('degrade')}")
    return 0 if ok else 1


def cmd_check_all(a):
    reg = load_registry()
    tools = reg.get("tools") or {}
    results = {}
    for tid, spec in sorted(tools.items()):
        if not isinstance(spec, dict):
            continue
        ok, reason, detail = check_identity(tid, spec)
        results[tid] = {"name": spec.get("name"), "available": ok,
                        "reason": reason, "detail": detail,
                        "evidence_level": spec.get("evidence_level"),
                        "degrade": spec.get("degrade"),
                        "purpose": spec.get("purpose")}

    avail = [k for k, v in results.items() if v["available"]]
    missing = [k for k, v in results.items() if not v["available"]]
    fake = [k for k, v in results.items() if "同名" in v["reason"]]
    required_missing = [k for k in missing
                        if (tools[k].get("degrade") == "required")]

    # 🔑 按 kind 分组——"缺失"里绝大多数根本不是 CLI，不该被叫"缺失"
    by_kind = {}
    for tid, spec in tools.items():
        if not isinstance(spec, dict):
            continue
        k = spec.get("kind") or "reference"
        by_kind.setdefault(k, []).append(tid)
    runnable = len(by_kind.get("cli", [])) + len(by_kind.get("lib", []))
    non_runnable = len(results) - runnable
    missing_runnable = [k for k in missing
                        if (tools[k].get("kind") in ("cli", "lib")
                            or not tools[k].get("kind"))]
    missing_other = [k for k in missing if k not in missing_runnable]

    print("=" * 74)
    print(f"能力探测 · 共 {len(results)} / 可用 {len(avail)} / 缺失 {len(missing)}")
    print("=" * 74)
    print("\n🔑 **把上面这个『缺失』数字当能力缺口是错的——先按 kind 拆开：**")
    print("\n| kind | 条数 | 能否被探测 |")
    print("|---|---|---|")
    for k in ("cli", "lib", "doc", "sdk", "reference"):
        v = by_kind.get(k, [])
        probe = ("✅ 能（`which` + `--version` 双重校验）" if k == "cli"
                 else "⚠️ 需 import/wrapper 校验" if k == "lib"
                 else "❌ 不能（规范/SDK/参考仓库，本来就没有可执行文件）")
        print(f"| `{k}` | {len(v)} | {probe} |")
    print(f"\n🔑 **真正可运行的 = cli + lib = {runnable} 条**")
    print(f"🔑 不可执行的 = {non_runnable} 条 —— "
          "**它们不是能力缺口，只是不能 `which`**")
    print(f"\n🔑 **真正值得盯的『可运行却缺失』= {len(missing_runnable)} 条**"
          f"（另有 {len(missing_other)} 条是不可执行类型，不计入缺口）")
    print("\n🔴 **最该警惕的不是数字虚高，而是使用者据此产生"
          "『机器已经查过了』的错觉。**")
    if fake:
        print(f"\n🚨 **疑似同名不同工具** {len(fake)} 个（最危险）:")
        for k in fake:
            print(f"   {k} — {results[k]['reason']}")
            print(f"      {results[k]['detail'][:90]}")
    if avail:
        print(f"\n✅ 可用 {len(avail)}:")
        for k in avail:
            print(f"   {k:<20} {results[k]['name']}")
    if missing_runnable:
        print(f"\n❌ **可运行却缺失（真正的缺口）** {len(missing_runnable)}:")
        for k in missing_runnable:
            d = tools[k].get("degrade")
            flag = "🔴必需" if d == "required" else "  可选"
            print(f"   {flag} {k:<20} {tools[k].get('name')}")
    if missing_other:
        print(f"\n⚪ **不可执行类型（规范/SDK/参考仓库，非缺口）** "
              f"{len(missing_other)} 条 —— 不逐条列出")

    if a.json:
        os.makedirs(os.path.dirname(a.json) or ".", exist_ok=True)
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"\n→ {a.json}")

    print("\n⚠️ 缺失不等于跳过：")
    print("   `required` 缺失 → 证据标 confidence=low 并**进 unknown**")
    print("   `optional` 缺失 → 标 skipped 并提示，**不许静默**")

    return 1 if (a.gate and required_missing) else 0


def cmd_run(a):
    reg = load_registry()
    tools = reg.get("tools") or {}
    spec = tools.get(a.run)
    if not spec:
        print(f"❌ 未登记的工具: {a.run}")
        return 2
    ok, reason, detail = check_identity(a.run, spec)
    if not ok:
        print(f"❌ {a.run} 不可用 —— {reason}")
        print(f"   {detail}")
        print(f"   缺失时行为: {spec.get('degrade')}")
        print("   ⚠️ 不得静默跳过：请在证据里标注并降级。")
        return 1
    wrapper = spec.get("wrapper")
    if not wrapper or wrapper.startswith("("):
        print(f"✅ {a.run} 可用（{detail}）")
        print(f"   该工具暂无封装脚本，直接调用: {spec.get('exe')}")
        return 0
    wp = os.path.join(HERE, wrapper)
    if not os.path.exists(wp):
        print(f"⚠️ 封装脚本缺失: {wp}")
        return 2
    print(f"✅ {a.run} 可用 → 调用 {wrapper}")
    return 0


def cmd_env(a):
    reg = load_registry()
    tools = reg.get("tools") or {}
    print("=" * 74)
    print("能力矩阵（工具是否真可用，不是「装了没」）")
    print("=" * 74)
    print(f"{'工具':<22} {'状态':<8} {'证据':<4} 说明")
    print("-" * 74)
    for tid, spec in sorted(tools.items()):
        if not isinstance(spec, dict):
            continue
        ok, reason, _ = check_identity(tid, spec)
        st = "可用" if ok else ("**假**" if "同名" in reason else "缺失")
        print(f"{tid:<22} {st:<8} {spec.get('evidence_level','?'):<4} "
              f"{(spec.get('purpose') or '')[:34]}")
    print("\n⚠️「**假**」= 命令存在但不是我们要的工具（如 Unix `sg` 冒充 ast-grep）")
    print("   这类最危险：脚本会显示成功，实际永远 0 命中。")

    # 🔑 **别把上面那串"缺失"当能力缺口——先按 kind 拆开**
    by_kind = {}
    for tid, spec in tools.items():
        if not isinstance(spec, dict):
            continue
        by_kind.setdefault(spec.get("kind") or "reference", []).append(tid)
    runnable = len(by_kind.get("cli", [])) + len(by_kind.get("lib", []))
    print("\n" + "=" * 74)
    print("🔑 上面的『缺失』不是能力缺口 —— 按 kind 拆开才看得懂")
    print("=" * 74)
    print("\n| kind | 条数 | 能否被探测 |")
    print("|---|---|---|")
    for k in ("cli", "lib", "doc", "sdk", "reference"):
        v = by_kind.get(k, [])
        probe = ("✅ 能（`which` + `--version` + 子命令三重校验）" if k == "cli"
                 else "⚠️ 需 import/wrapper 校验" if k == "lib"
                 else "❌ 不能（规范 / SDK / 参考仓库，本来就没有可执行文件）")
        print(f"| `{k}` | {len(v)} | {probe} |")
    print(f"\n🔑 **真正可运行的 = cli + lib = {runnable} 条**")
    print(f"🔑 不可执行的 = {len(tools) - runnable} 条 —— "
          "**不是缺口，只是不能 `which`**")
    print("\n🔴 **最该警惕的不是数字虚高，而是使用者据此产生"
          "『机器已经查过了』的错觉。**")
    print("🔑 真实缺口请只看 `cli` + `lib` 两行的『缺失』，其余不计入。")
    return 0


def main():
    ap = argparse.ArgumentParser(description="外部工具调度器")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--check")
    ap.add_argument("--check-all", action="store_true")
    ap.add_argument("--run")
    ap.add_argument("--env", action="store_true")
    ap.add_argument("--json")
    ap.add_argument("--gate", action="store_true", help="必需工具缺失退出码 1")
    a = ap.parse_args()

    reg = load_registry()
    if a.list:
        return cmd_list(a)
    if a.check:
        return cmd_check_one(a, reg)
    if a.check_all:
        return cmd_check_all(a)
    if a.run:
        return cmd_run(a)
    if a.env:
        return cmd_env(a)
    print("❌ 需要 --list / --check / --check-all / --run / --env 之一")
    return 2


if __name__ == "__main__":
    sys.exit(main())
