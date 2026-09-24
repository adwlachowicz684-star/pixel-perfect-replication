#!/usr/bin/env python3
"""行内注释全量提取（意图层挖掘，最高产的一轮）。

`//` 比 `///` 值钱十倍:
  /// 回答「这个函数是干什么的」
  //  回答「为什么必须这么写」 —— 踩过的坑、隐含约束、数据风险全在这里

实证：把 /// 全量提取换成 // 全量提取，单轮从 +30 跳到 +90。

用法:
  comment_extract.py <file> [<file2> ...]
  comment_extract.py <file> --inline-only          # 只要行尾注释（最值钱）
  comment_extract.py <file> --negative             # 只输出含负面教训词的
  comment_extract.py <dir> --recursive --ext .cs   # 整目录
"""
import argparse
import os
import re
import sys

METHOD = re.compile(
    r"^\s{0,8}(?:private|public|internal|protected|static|async|fn|pub fn|function|def)"
    r"[\w\s<>\[\],?\.]*\s+(\w+)\s*\(")
INLINE = re.compile(r"//\s*(.*[\u4e00-\u9fa5].*)$")
DOC = re.compile(r"^\s*///")
NEGATIVE = re.compile(
    r"否则|不然|会|可能|需|必须|绝不能|不能|警惕|注意|坑|错|误|"
    r"残留|丢失|死锁|振荡|黑屏|穿透|错位|小心|避免|防止|因为")


def extract(path, inline_only=False, negative=False):
    with open(path, encoding="utf-8", errors="replace") as f:
        lines = f.read().split("\n")
    cur = "?"
    hits = []
    for i, l in enumerate(lines):
        m = METHOD.match(l)
        if m:
            cur = m.group(1)
        if DOC.match(l):
            continue
        m2 = INLINE.search(l)
        if not m2:
            continue
        text = m2.group(1).strip()
        # 行尾注释（前面有代码）vs 整行注释
        is_trailing = l[:m2.start()].strip() != ""
        if inline_only and not is_trailing:
            continue
        if negative and not NEGATIVE.search(text):
            continue
        hits.append((i + 1, cur, text, "行尾" if is_trailing else "整行"))
    return hits


def main():
    ap = argparse.ArgumentParser(description="行内注释提取")
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--inline-only", action="store_true", help="只要行尾注释")
    ap.add_argument("--negative", action="store_true", help="只要含负面教训词的")
    ap.add_argument("--recursive", action="store_true")
    ap.add_argument("--ext", default="")
    a = ap.parse_args()

    files = []
    for p in a.paths:
        if os.path.isdir(p):
            for root, dirs, fns in os.walk(p):
                dirs[:] = [d for d in dirs if d not in
                           (".git", "node_modules", "target", "dist", "bin", "obj")]
                for fn in fns:
                    if not a.ext or fn.endswith(a.ext):
                        files.append(os.path.join(root, fn))
        else:
            files.append(p)

    total = 0
    for fn in files:
        try:
            hits = extract(fn, a.inline_only, a.negative)
        except Exception as e:
            print(f"# {fn}: 读取失败 {e}")
            continue
        if not hits:
            continue
        print(f"\n## {fn}  ({len(hits)} 条)")
        for ln, method, text, kind in hits:
            print(f"  L{ln:<5} [{method}] ({kind}) {text}")
        total += len(hits)
    print(f"\n合计 {total} 条")
    return 0


if __name__ == "__main__":
    sys.exit(main())
