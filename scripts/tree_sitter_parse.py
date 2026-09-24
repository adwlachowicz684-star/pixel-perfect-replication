#!/usr/bin/env python3
"""全量源码可解析性扫描（S2M L1）—— 先问"机器能不能读懂"。

解析失败本身就是信号：旧实现不是每种语言都干净可解析，
说明"实现层"证据可能失效 → 应升级为反证和人工阅读，**而不是删项**。

优先用 tree-sitter CLI；不可用时降级为"括号/引号配对"粗判，
并明确标注 confidence=low（不假装做了 AST 解析）。

用法:
  tree_sitter_parse.py --src <src> [--ext .cs] [--out ledger/parse-status.csv]
  tree_sitter_parse.py --src src --lang rust

退出码: 0 全部可解析 / 1 存在解析失败（不自动关闭 unknown）/ 2 用法错误
"""
import argparse
import csv
import os
import shutil
import subprocess
import sys

SKIP_DIRS = (".git", "node_modules", "target", "dist", "bin", "obj", "build")
LANG_EXT = {
    "csharp": ".cs", "rust": ".rs", "typescript": ".ts", "tsx": ".tsx",
    "javascript": ".js", "python": ".py", "go": ".go", "java": ".java",
    "cpp": ".cpp", "c": ".c",
}


def walk(src, ext=None):
    out = []
    for root, dirs, fns in os.walk(src):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for fn in fns:
            if ext and not fn.endswith(ext):
                continue
            out.append(os.path.join(root, fn))
    return sorted(out)


def ts_available():
    return shutil.which("tree-sitter") is not None


def parse_with_tree_sitter(files, lang):
    """用 tree-sitter parse 逐个解析，靠 stderr/退出码判断。"""
    rows = []
    for p in files:
        cmd = ["tree-sitter", "parse"]
        if lang:
            cmd += ["--scope", lang] if False else []
        cmd.append(p)
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            ok = (r.returncode == 0) and ("ERROR" not in r.stdout)
            err = (r.stdout + r.stderr).strip().splitlines()
            msg = next((l for l in err if "ERROR" in l or "error" in l), "")
        except Exception as e:
            ok, msg = False, f"执行失败: {e}"
        rows.append({"path": p, "parsed": "yes" if ok else "no",
                     "engine": "tree-sitter", "confidence": "high", "note": msg[:160]})
    return rows


def crude_parse(text):
    """降级：括号/引号配对粗判（复用 brace_check 的逻辑）。"""
    depth, i, n = 0, 0, len(text)
    in_s = in_c = in_lc = in_bc = False
    while i < n:
        ch = text[i]
        nxt = text[i + 1] if i + 1 < n else ""
        if in_lc:
            if ch == "\n":
                in_lc = False
            i += 1
            continue
        if in_bc:
            if ch == "*" and nxt == "/":
                in_bc = False
                i += 2
                continue
            i += 1
            continue
        if in_s:
            if ch == "\\":
                i += 2
                continue
            if ch == '"':
                in_s = False
            i += 1
            continue
        if in_c:
            if ch == "\\":
                i += 2
                continue
            if ch == "'":
                in_c = False
            i += 1
            continue
        if ch == "/" and nxt == "/":
            in_lc = True
            i += 2
            continue
        if ch == "/" and nxt == "*":
            in_bc = True
            i += 2
            continue
        if ch == '"':
            in_s = True
            i += 1
            continue
        if ch == "'":
            if nxt.isalpha() or nxt == "_":
                i += 1
                continue
            in_c = True
            i += 1
            continue
        if ch in "{[(":
            depth += 1
        elif ch in "}])":
            depth -= 1
            if depth < 0:
                return False
        i += 1
    return depth == 0


def crude_rows(files):
    rows = []
    for p in files:
        try:
            with open(p, encoding="utf-8", errors="replace") as f:
                t = f.read()
            ok = crude_parse(t)
            note = "" if ok else "括号/引号不平衡（粗判）"
        except Exception as e:
            ok, note = False, f"读取失败: {e}"
        rows.append({"path": p, "parsed": "yes" if ok else "no",
                     "engine": "crude-brace", "confidence": "low", "note": note})
    return rows


def main():
    ap = argparse.ArgumentParser(description="源码可解析性扫描")
    ap.add_argument("--src", required=True)
    ap.add_argument("--ext", default="")
    ap.add_argument("--lang", default="")
    ap.add_argument("--out", default="ledger/parse-status.csv")
    a = ap.parse_args()

    if not os.path.isdir(a.src):
        print(f"❌ 目录不存在: {a.src}")
        return 2

    ext = a.ext or LANG_EXT.get(a.lang, "")
    files = walk(a.src, ext or None)
    if not files:
        print(f"❌ 未找到文件（src={a.src} ext={ext or '全部'}）")
        return 2

    if ts_available():
        print(f"✅ tree-sitter 可用，解析 {len(files)} 个文件")
        rows = parse_with_tree_sitter(files, a.lang)
    else:
        print(f"⚠️  未找到 tree-sitter CLI —— 降级为括号配对粗判，confidence=low")
        print("   不假装做了 AST 解析；粗判只能说明「结构是否闭合」，不能说明语法正确。")
        rows = crude_rows(files)

    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    with open(a.out, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["path", "parsed", "engine", "confidence", "note"])
        w.writeheader()
        w.writerows(rows)

    bad = [r for r in rows if r["parsed"] == "no"]
    total = len(rows)
    print("=" * 60)
    print(f"文件 {total} · 可解析 {total - len(bad)} · 失败 {len(bad)}")
    print(f"→ {a.out}")
    if bad:
        print(f"\n❌ {len(bad)} 个文件解析失败:")
        for r in bad[:20]:
            print(f"   {r['path']}  {r['note']}")
        print("\n处置：登记进台账「机器可解析」字段 + 降低 AST 证据等级 + 人工阅读。")
        print("     **不许因为难解析就删项，也不许自动关闭 unknown。**")
        return 1
    print("\n✅ 全部可解析")
    return 0


if __name__ == "__main__":
    sys.exit(main())
