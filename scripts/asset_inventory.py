#!/usr/bin/env python3
"""资产与资源清点（S2A）—— 资源文件清单 + 引用计数 + 孤儿/悬空检测。

**为什么要单独扫**：视觉像素藏在资源里，不在逻辑里。
功能清单上不会写图标和音效，但丢一个就是"说不出哪里不对"。

三类输出:
  1. 资源清单 CSV：路径 / 类别 / 大小 / hash / 被引用次数 / 许可标记
  2. **孤儿资源**：文件存在但代码里 0 引用（可能是残留，也可能是动态加载）
  3. **悬空引用**：代码引用了但文件不存在 —— **这一种是硬错误**

用法:
  asset_inventory.py --src <目录> --out work/ledger/assets.csv
  asset_inventory.py --src <目录> --code <代码目录> --out assets.csv
  asset_inventory.py --src <目录> --code <代码目录> --gate      # 有悬空引用退出码 1
  asset_inventory.py --src <目录> --list-license               # 列出需人工确认许可的资源

类别: image / icon / font / audio / video / fonticon / other
退出码: 0 正常 / 1 --gate 且存在悬空引用 / 2 用法或文件错误
"""
import argparse
import csv
import hashlib
import os
import re
import sys

SKIP_DIRS = (".git", "node_modules", "target", "dist", "bin", "obj", "build", ".next")

# 类别 → 扩展名
CATEGORY_EXT = {
    "image": (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".avif", ".tiff"),
    "icon":  (".ico", ".icns", ".cur", ".ani"),
    "font":  (".ttf", ".otf", ".woff", ".woff2", ".eot", ".pfb"),
    "audio": (".wav", ".mp3", ".ogg", ".oga", ".flac", ".m4a", ".aac"),
    "video": (".mp4", ".webm", ".avi", ".mov", ".mkv"),
    "vector": (".svg",),
}
# 需要人工确认许可的类别（法律坑）
LICENSE_REQUIRED = ("font", "audio", "icon", "image", "vector")


def category_of(fn):
    low = fn.lower()
    for cat, exts in CATEGORY_EXT.items():
        if low.endswith(exts):
            return cat
    return "other"


def sha1(path, chunk=1 << 20):
    h = hashlib.sha1()
    try:
        with open(path, "rb") as f:
            while True:
                b = f.read(chunk)
                if not b:
                    break
                h.update(b)
    except Exception:
        return "?"
    return h.hexdigest()[:12]


def walk_files(root, exts=None):
    out = []
    for d, dirs, fns in os.walk(root):
        dirs[:] = [x for x in dirs if x not in SKIP_DIRS]
        for fn in fns:
            if exts and not fn.lower().endswith(tuple(exts)):
                continue
            out.append(os.path.join(d, fn))
    return sorted(out)


CODE_EXT = (".cs", ".xaml", ".ts", ".tsx", ".js", ".jsx", ".rs", ".json",
            ".css", ".scss", ".html", ".vue", ".py", ".qml")


def build_reference_index(code_roots):
    """把代码文件内容读成一份大字符串（按文件存，便于定位引用位置）。"""
    idx = []
    for root in code_roots:
        if not os.path.isdir(root):
            continue
        for p in walk_files(root, CODE_EXT):
            try:
                with open(p, encoding="utf-8", errors="replace") as f:
                    idx.append((p, f.read()))
            except Exception:
                continue
    return idx


def count_refs(filename, stem, idx):
    """统计资源被引用的次数（按完整文件名与去扩展名两种形态都算）。"""
    n = 0
    where = []
    pat_full = re.compile(re.escape(filename), re.I)
    pat_stem = re.compile(r"[\w\-./]*" + re.escape(stem) + r"[\w\-.]*", re.I)
    for path, text in idx:
        if pat_full.search(text):
            n += 1
            where.append(path)
        elif pat_stem.search(text):
            n += 1
            where.append(path)
    return n, where[:3]


def cmd_scan(a):
    if not os.path.isdir(a.src):
        print(f"❌ 目录不存在: {a.src}")
        return 2

    all_exts = [e for exts in CATEGORY_EXT.values() for e in exts]
    files = walk_files(a.src, all_exts)
    if not files:
        print(f"⚠️  {a.src} 下未找到资源文件（可能目录不对）")
        return 0

    idx = build_reference_index(a.code or [a.src]) if a.code else []

    rows = []
    for p in files:
        fn = os.path.basename(p)
        stem = os.path.splitext(fn)[0]
        cat = category_of(fn)
        refs, where = (count_refs(fn, stem, idx) if idx else (0, []))
        rows.append({
            "path": p, "category": cat, "filename": fn,
            "size_kb": f"{os.path.getsize(p) / 1024:.1f}",
            "sha1_12": sha1(p),
            "refs": refs,
            "ref_sample": ";".join(where),
            "license": "待确认" if cat in LICENSE_REQUIRED else "-",
        })

    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    with open(a.out, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["path", "category", "filename", "size_kb",
                                          "sha1_12", "refs", "ref_sample", "license"])
        w.writeheader()
        w.writerows(rows)

    # 类别统计
    cats = {}
    for r in rows:
        cats[r["category"]] = cats.get(r["category"], 0) + 1

    print("=" * 64)
    print(f"资源文件 {len(rows)} 个 → {a.out}")
    print("=" * 64)
    for k in sorted(cats, key=lambda x: -cats[x]):
        print(f"   {k}: {cats[k]}")

    orphans = [r for r in rows if idx and r["refs"] == 0]
    if idx and orphans:
        print(f"\n⚠️  【孤儿资源】{len(orphans)} 个 —— 文件存在但代码 0 引用:")
        for r in orphans[:15]:
            print(f"   [{r['category']}] {r['filename']}")
        print("   处置：确认是残留（可删/可不迁）还是动态加载（必须迁）。"
              "**不许默认当残留**——动态拼接的路径 grep 不到。")

    return 0


def scan_dangling(code_roots, asset_dir):
    """悬空引用：代码里写了资源名，但文件不存在。"""
    idx = build_reference_index(code_roots)
    if not idx:
        return []
    known = set()
    for p in walk_files(asset_dir):
        known.add(os.path.basename(p).lower())
    pat = re.compile(r"""["']([\w\-./ ]+\.(?:png|jpg|jpeg|gif|svg|ico|ttf|otf|woff2?|
                          wav|mp3|ogg|cur|ani|webp))["']""", re.I | re.X)
    bad = []
    for path, text in idx:
        for m in pat.finditer(text):
            ref = m.group(1)
            base = os.path.basename(ref).lower()
            if base not in known:
                bad.append((path, ref))
    return bad


def main():
    ap = argparse.ArgumentParser(description="资产与资源清点")
    ap.add_argument("--src", help="资源目录")
    ap.add_argument("--code", nargs="*", help="代码目录（用于引用计数）")
    ap.add_argument("--out", default="ledger/assets.csv")
    ap.add_argument("--gate", action="store_true", help="有悬空引用退出码 1")
    ap.add_argument("--list-license", action="store_true",
                    help="只列出需人工确认许可的资源")
    a = ap.parse_args()

    if not a.src:
        print("❌ 需要 --src")
        return 2

    rc = cmd_scan(a)

    if a.list_license:
        try:
            with open(a.out, encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
        except Exception:
            print(f"❌ 读不了 {a.out}")
            return 2
        need = [r for r in rows if r["license"] == "待确认"]
        print(f"\n📜 需人工确认许可的资源 {len(need)} 个:")
        for r in need[:30]:
            print(f"   [{r['category']}] {r['filename']}  ({r['size_kb']}KB)")
        print("\n   ⚠️ 字体/音效/图标/图片的**商用与再分发授权**是最容易踩的法律坑。")
        print("      逐条记录来源与许可，见 `references/资产与资源总清单.md` L 类。")
        return 0

    dangling = scan_dangling(a.code or [], a.src) if a.code else []
    if dangling:
        print(f"\n❌ 【悬空引用】{len(dangling)} 处 —— 代码引用了但文件不存在:")
        for path, ref in dangling[:15]:
            print(f"   {path}: {ref}")
        print("\n   这是硬错误：运行时必然取不到资源。")
        if a.gate:
            return 1

    return rc


if __name__ == "__main__":
    sys.exit(main())
