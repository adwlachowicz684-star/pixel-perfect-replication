#!/usr/bin/env python3
"""括号平衡检测（无编译环境下的静态验证第一道）。

能抓住绝大多数"改漏了一半个括号"。

必须处理的四个陷阱:
  1. 'a 是 Rust lifetime，不是 char 字面量 —— 否则后续引号配对全乱
  2. '{' '\'' 这类 char 字面量
  3. 字符串里的 \\ 转义要跳过下一个字符
  4. 注释里的括号必须跳过（// 与 /* */）

用法:
  brace_check.py <file> [<file2> ...]          # 报告绝对值
  brace_check.py <file> --baseline <orig>      # 与改前版本做基线对比
  brace_check.py --diff <file>                 # 只校验 git diff 的新增行
"""
import argparse
import re
import subprocess
import sys


def scan(text):
    """返回 (depth, ok)。depth 为结束时的大括号净深度。"""
    depth, i, n = 0, 0, len(text)
    ok = True
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
            # ⚠️ 关键：lifetime（'a / 'static / '_）不是字符字面量
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
                ok = False
        i += 1
    return depth, (ok and depth == 0)


def strip_noise(line):
    """粗略去掉字符串与注释，用于新增行统计。"""
    line = re.sub(r'"(\\.|[^"\\])*"', '""', line)
    line = re.sub(r"'(\\.|[^'\\])*'", "''", line)
    line = re.sub(r"//.*$", "", line)
    return line


def main():
    ap = argparse.ArgumentParser(description="括号平衡检测")
    ap.add_argument("files", nargs="+")
    ap.add_argument("--baseline", help="改前版本，做基线对比")
    ap.add_argument("--diff", action="store_true", help="只校验 git diff 新增行")
    a = ap.parse_args()

    rc = 0
    for fn in a.files:
        try:
            with open(fn, encoding="utf-8", errors="replace") as f:
                text = f.read()
        except Exception as e:
            print(f"❌ {fn}: 读取失败 {e}")
            rc = 1
            continue

        if a.diff:
            out = subprocess.run(["git", "diff", "HEAD", "--", fn],
                                 capture_output=True, text=True).stdout
            added = [l[1:] for l in out.splitlines()
                     if l.startswith("+") and not l.startswith("+++")]
            o = sum(strip_noise(l).count("{") for l in added)
            c = sum(strip_noise(l).count("}") for l in added)
            b = sum(strip_noise(l).count("(") for l in added)
            d = sum(strip_noise(l).count(")") for l in added)
            ok = (o == c and b == d)
            print(f"{'✅' if ok else '❌'} {fn}: 新增行 {{}} {o}/{c}  () {b}/{d}")
            if not ok:
                rc = 1
            continue

        depth, ok = scan(text)
        if a.baseline:
            try:
                with open(a.baseline, encoding="utf-8", errors="replace") as f:
                    bdepth, _ = scan(f.read())
            except Exception as e:
                print(f"❌ 基线读取失败: {e}")
                rc = 1
                continue
            same = (depth == bdepth)
            print(f"{'✅' if same else '❌'} {fn}: depth={depth} 基线={bdepth} "
                  f"{'一致（改动安全）' if same else '不一致（可能是你引入的）'}")
            if not same:
                rc = 1
        else:
            print(f"{'✅' if ok else '❌'} {fn}: depth={depth} "
                  f"{'平衡' if ok else '不平衡'}")
            if not ok:
                rc = 1
    return rc


if __name__ == "__main__":
    sys.exit(main())
