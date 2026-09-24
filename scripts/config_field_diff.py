#!/usr/bin/env python3
"""config / DTO 字段双向差集（数据层挖掘，最容易丢东西的地方）。

⚠️ 踩过的坑：用 `grep -oP "pub \\w+"` 只抓到 25 个，实际 39 个 ——
带 Option<...> / 泛型的字段抓不全。**必须按大括号配对截取结构体。**

⚠️ 更隐蔽的坑：字段数对得上 ≠ 语义等价。
实证：原版有两层锁定（locked 账面固定 / folderLock.items[] 系统 ACL），
当前合并成一层 locks → 「仅账面固定」这一档消失。
所以差集为 0 时，本脚本仍会提示做语义合并检查。

支持:
  原版 C#  : [JsonPropertyName("x")] 或 public T X { get; set; }
  新版 Rust: pub struct X { pub y: T, ... }（大括号配对）
  通用 JSON: 顶层键与首条字段

用法:
  config_field_diff.py --old <原版文件> --new <新版文件>
  config_field_diff.py --old a.cs --new b.rs --struct FpxConfig
  config_field_diff.py --json-old a.json --json-new b.json
"""
import argparse
import json
import re
import sys


def read_braced(src, open_idx):
    """从 open_idx 处的 '{' 开始，按配对截取到匹配的 '}'，返回内部文本。"""
    depth, j = 0, open_idx
    while j < len(src):
        if src[j] == "{":
            depth += 1
        elif src[j] == "}":
            depth -= 1
            if depth == 0:
                return src[open_idx + 1:j]
        j += 1
    return src[open_idx + 1:]


def fields_of(text, lang, struct=None):
    out = []
    if lang == "cs":
        jp = re.findall(r'\[JsonPropertyName\("([^"]+)"\)\]', text)
        if jp:
            return jp
        out = re.findall(r'public\s+[\w<>\[\],\?\.]+\s+(\w+)\s*\{\s*get;', text)
    elif lang == "rs":
        if struct:
            m = re.search(r"pub\s+struct\s+" + re.escape(struct) + r"\s*\{", text)
            idx = m.end() - 1 if m else text.find("pub struct")
        else:
            m = re.search(r"pub\s+struct\s+\w+\s*\{", text)
            idx = m.end() - 1 if m else 0
        body = read_braced(text, idx)
        out = re.findall(r"pub\s+(\w+)\s*:", body)
    elif lang == "ts":
        for m in re.finditer(r"(?:interface|type)\s+\w+\s*\{", text):
            body = read_braced(text, m.end() - 1)
            out += re.findall(r"^\s*(\w+)\??\s*:", body, re.M)
    return out


def guess_lang(path):
    ext = path.lower().rsplit(".", 1)[-1]
    return {"cs": "cs", "rs": "rs", "ts": "ts", "tsx": "ts"}.get(ext, "cs")


def to_snake(s):
    s = re.sub(r"(?<!^)(?=[A-Z])", "_", s).lower()
    return re.sub(r"_+", "_", s).strip("_")


def main():
    ap = argparse.ArgumentParser(description="config 字段双向差集")
    ap.add_argument("--old", help="原版文件")
    ap.add_argument("--new", help="新版文件")
    ap.add_argument("--struct", default="", help="指定结构体名（Rust）")
    ap.add_argument("--json-old", help="原版 JSON 数据文件")
    ap.add_argument("--json-new", help="新版 JSON 数据文件")
    a = ap.parse_args()

    if a.json_old or a.json_new:
        def keys(p, prefix=""):
            if not p:
                return []
            with open(p, encoding="utf-8", errors="replace") as f:
                d = json.load(f)
            if isinstance(d, dict):
                ks = list(d.keys())
                for v in d.values():
                    if isinstance(v, list) and v and isinstance(v[0], dict):
                        ks += [f"<item>.{k}" for k in v[0].keys()]
                return ks
            return []
        o, n = keys(a.json_old), keys(a.json_new)
        print("⚠️ 这是真实数据文件比对 —— 代码只读它认识的字段，"
              "读不出的字段会在迁移时静默丢弃。")
    else:
        if not (a.old and a.new):
            ap.error("需要 --old/--new 或 --json-old/--json-new")
        to = open(a.old, encoding="utf-8", errors="replace").read()
        tn = open(a.new, encoding="utf-8", errors="replace").read()
        o = fields_of(to, guess_lang(a.old), a.struct)
        n = fields_of(tn, guess_lang(a.new), a.struct)

    os_, ns_ = {to_snake(x) for x in o}, {to_snake(x) for x in n}
    only_old, only_new = sorted(os_ - ns_), sorted(ns_ - os_)

    print(f"\n原版字段 {len(os_)} | 新版字段 {len(ns_)}")
    print(f"\n[原版有、新版无] {len(only_old)} —— 迁移时会被静默丢弃:")
    for x in only_old:
        print("   ", x)
    print(f"\n[新版有、原版无] {len(only_new)} —— 可能是增强，进勿删清单:")
    for x in only_new:
        print("   ", x)

    print("\n⚠️ 差集为 0 不等于等价：还要检查「语义合并」")
    print("   例：两层锁定（locked 账面 / folderLock.items[] 系统 ACL）")
    print("       合并成一层 locks → 「仅账面固定」这一档消失。")

    return 1 if (only_old or only_new) else 0


if __name__ == "__main__":
    sys.exit(main())
