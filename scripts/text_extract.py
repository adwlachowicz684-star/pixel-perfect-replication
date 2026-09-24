#!/usr/bin/env python3
"""UI 文案提取 + 双侧差集（C1 类）—— 防止"重写得更清楚"把原文案丢掉。

**为什么单独做**：迁移时最常见的错误是**不看原文案，直接重写**。
用户的肌肉记忆是认**原句**的，换了措辞等于换了入口。

提取来源:
  - XAML: Content / Text / Header / ToolTip / PlaceholderText / Watermark / Title / Label
  - C#  : MessageBox.Show(...) / toast(...) / ShowMessage(...) / throw new XxxException(...)
  - TS/JS: 中文字符串字面量（在 UI 相关上下文里）
  - 通用 : 含 CJK 的字符串字面量

两种命令:
  1. 提取   --src <dir> --out texts.csv
  2. 差集   --compare --old old.csv --new new.csv [--gate]

差集输出:
  ❌ 原版有新版无  —— **丢失的文案**（硬阻塞：必须补或登记为有意变更）
  ⚠️ 措辞不同      —— 需人工判断是不是"重写得更清楚"
  ℹ️ 新版多出      —— 记入反向清单

用法:
  text_extract.py --src <原版> --out texts-old.csv
  text_extract.py --compare --old texts-old.csv --new texts-new.csv --gate

退出码: 0 正常 / 1 --gate 且存在丢失文案 / 2 用法或文件错误
"""
import argparse
import csv
import difflib
import os
import re
import sys

SKIP_DIRS = (".git", "node_modules", "target", "dist", "bin", "obj", "build", ".next")
CJK = re.compile(r"[\u4e00-\u9fff]")

# XAML 属性
XAML_ATTRS = ("Content", "Text", "Header", "ToolTip", "ToolTipService.ToolTip",
              "PlaceholderText", "Watermark", "Title", "Label", "Hint",
              "Description", "EmptyText")
XAML_RE = re.compile(
    r"(?<![\w:])(" + "|".join(XAML_ATTRS) + r")\s*=\s*\"([^\"]{1,200})\"")
# XAML 元素文本内容：<TextBlock>xxx</TextBlock>
XAML_TEXT_RE = re.compile(r"<(TextBlock|Label|Run)\b[^>]*>\s*([^<>{}\n]{1,200}?)\s*</\1>")

# C# 提示调用
CS_CALL_RE = re.compile(
    r"(?i)\b(MessageBox\.Show|ShowMessage|toast|Toast|ShowTip|ShowError|"
    r"ShowSuccess|ShowWarning|Notify|MessageBoxShow)\s*\(\s*"
    r"(@?\"(?:[^\"\\]|\\.)*\"|nameof\(\w+\))")

# 通用字符串字面量（含 CJK）
STR_RE = re.compile(r"""(["'`])((?:[^"'\\
]|\\.)*?)\1""")

CODE_EXT = (".cs", ".xaml", ".axaml", ".ts", ".tsx", ".js", ".jsx",
            ".vue", ".rs", ".py", ".json", ".html", ".qml")


def walk(src):
    out = []
    for root, dirs, fns in os.walk(src):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for fn in fns:
            if fn.lower().endswith(CODE_EXT):
                out.append(os.path.join(root, fn))
    return sorted(out)


def norm_text(s):
    """文案归一化：去空白、去占位符差异、去全角半角标点差异。"""
    s = (s or "").strip()
    if not s:
        return None
    if not CJK.search(s):
        return None                          # 只保留含中文的（英文多为标识符）
    # 占位符统一（{0} / {name} / %s / ${x}）
    s = re.sub(r"\{[^}]{0,30}\}|\$\{[^}]{0,30}\}|%\w|:\w+", "{}", s)
    s = re.sub(r"\s+", "", s)
    s = s.replace("：", ":").replace("，", ",").replace("。", ".") \
         .replace("！", "!").replace("？", "?").replace("；", ";")
    return s


def extract_file(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            lines = f.read().splitlines()
    except Exception:
        return []
    out = []
    seen = set()

    def add(line_no, kind, text):
        n = norm_text(text)
        if not n or len(n) < 2:
            return
        if n in seen:
            return
        seen.add(n)
        out.append({"file": path, "line": line_no, "kind": kind,
                    "text": n, "raw": text[:120]})

    for i, line in enumerate(lines, 1):
        s = line.strip()
        if s.startswith(("//", "#", "*", "<!--", "///")):
            continue
        ext = os.path.splitext(path)[1].lower()

        # XAML 属性与元素文本
        if ext in (".xaml", ".axaml", ".html", ".qml"):
            for m in XAML_RE.finditer(line):
                add(i, "xaml-attr", m.group(2))
            for m in XAML_TEXT_RE.finditer(line):
                add(i, "xaml-text", m.group(2))
        # C# / 其它：提示调用
        for m in CS_CALL_RE.finditer(line):
            raw = m.group(2)
            if raw.startswith("@"):
                raw = raw[1:]
            if raw.startswith('"'):
                try:
                    raw = raw.strip('"').encode().decode("unicode_escape")
                except Exception:
                    raw = raw.strip('"')
            add(i, "call", raw)
        # 兜底：任意含 CJK 的字符串字面量
        for m in STR_RE.finditer(line):
            add(i, "literal", m.group(2))
    return out


def cmd_extract(a):
    if not os.path.isdir(a.src):
        print(f"❌ 目录不存在: {a.src}")
        return 2
    files = walk(a.src)
    if not files:
        print(f"❌ 未找到源文件（src={a.src}）")
        return 2
    rows = []
    for p in files:
        rows += extract_file(p)
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    with open(a.out, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["file", "line", "kind", "text", "raw"])
        w.writeheader()
        w.writerows(rows)
    kinds = {}
    for r in rows:
        kinds[r["kind"]] = kinds.get(r["kind"], 0) + 1
    print(f"提取 {len(rows)} 条 UI 文案（{len(files)} 文件）→ {a.out}")
    for k in sorted(kinds, key=lambda x: -kinds[x]):
        print(f"   {k}: {kinds[k]}")
    return 0


def load(path):
    if not os.path.exists(path):
        print(f"❌ 文件不存在: {path}")
        return None
    with open(path, encoding="utf-8", errors="replace") as f:
        return list(csv.DictReader(f))


def agg(rows):
    d = {}
    for r in rows:
        d.setdefault(r["text"], set()).add(r["file"])
    return d


def similarity(a, b):
    """序列相似度（基于最长公共子序列），用于识别「重写得更清楚」。

    ⚠️ 为什么不用字符集合 Jaccard：短中文串里同义词替换（确定→确认）
    字符几乎不重叠，Jaccard 只有 0.33 会漏掉；
    序列相似度能抓到「语序保留的局部改写」（保存成功→操作成功 = 0.5）。
    """
    return difflib.SequenceMatcher(None, a, b).ratio()


def find_rewrites(only_old, only_new, threshold=0.5):
    """在「原版有新版无」与「新版多出」之间找疑似改写的配对。

    这正是最常见的迁移错误：不看原文案，直接"重写得更清楚"。
    用户的肌肉记忆认的是**原句**。
    """
    pairs = []
    used_new = set()
    for o in only_old:
        best, bs = None, 0.0
        for n in only_new:
            if n in used_new:
                continue
            s = similarity(o, n)
            if s > bs:
                best, bs = n, s
        if best and bs >= threshold:
            pairs.append((o, best, bs))
            used_new.add(best)
    return pairs


def cmd_compare(a):
    old, new = load(a.old), load(a.new)
    if old is None or new is None:
        return 2
    ao, an = agg(old), agg(new)

    only_old = sorted(set(ao) - set(an))
    only_new = sorted(set(an) - set(ao))

    print("=" * 64)
    print(f"原版文案 {len(ao)} 条 · 新版 {len(an)} 条")
    print("=" * 64)

    pairs = find_rewrites(only_old, only_new)
    rewritten_new = {p[1] for p in pairs}
    rewritten_old = {p[0] for p in pairs}
    lost = [t for t in only_old if t not in rewritten_old]
    added = [t for t in only_new if t not in rewritten_new]

    if pairs:
        print(f"\n🔄 【疑似改写】{len(pairs)} 组 —— 措辞变了，这是最容易丢体验的一类:")
        for o, n, s in pairs:
            print(f"   原「{o}」 → 新「{n}」  (相似度 {s:.0%})")
        print("\n   ⚠️ 用户肌肉记忆认的是**原句**。改了措辞 = 换了入口。")
        print("      要么补回原文案，要么**登记为有意变更**（写清为什么）。")

    if lost:
        print(f"\n❌ 【原版有、新版无】{len(lost)} 条 —— **丢失的文案**:")
        for t in lost[:40]:
            src = sorted(ao[t])[0]
            print(f"   「{t}」  ← {src}")
        if len(lost) > 40:
            print(f"   … 另有 {len(lost) - 40} 条")
        print("\n   处置：补回原文案，或**登记为有意变更**（写清改了什么、为什么）。")
    if added:
        print(f"\nℹ️  【新版多出】{len(added)} 条 —— 记入反向清单（勿删）:")
        for t in added[:15]:
            print(f"   「{t}」")
        if len(added) > 15:
            print(f"   … 另有 {len(added) - 15} 条")
    if not (only_old or only_new):
        print("\n✅ 文案完全一致")

    if a.gate and only_old:
        return 1
    return 0


def main():
    ap = argparse.ArgumentParser(description="UI 文案提取与双侧差集")
    ap.add_argument("--src")
    ap.add_argument("--out", default="ledger/texts.csv")
    ap.add_argument("--compare", action="store_true")
    ap.add_argument("--old")
    ap.add_argument("--new")
    ap.add_argument("--gate", action="store_true", help="有丢失文案退出码 1")
    ap.add_argument("files", nargs="*", help="等价写法: --compare old.csv new.csv")
    a = ap.parse_args()

    if a.compare:
        if not a.old and len(a.files) >= 1:
            a.old = a.files[0]
        if not a.new and len(a.files) >= 2:
            a.new = a.files[1]
        if not (a.old and a.new):
            print("❌ --compare 需要 --old 与 --new（或直接跟两个文件名）")
            return 2
        return cmd_compare(a)
    if not a.src:
        print("❌ 需要 --src（或用 --compare 做差集）")
        return 2
    return cmd_extract(a)


if __name__ == "__main__":
    sys.exit(main())
