#!/usr/bin/env python3
"""体验参数提取 + 双侧差集（P-N 清单的机器侧）。

**核心立场**：体验参数（tips 多久弹、按钮间距多少、动画多长、拖拽阈值多少）
**可以不照搬，但必须知道搬前是什么样**。不记录就会丢失，而它们直接影响体验。

两类命令:
  1. 提取：从源码里抓体验参数，落 CSV
  2. 差集：比对原版与新版，输出「原版有新版无 / 值不同 / 新版多出」

支持：XAML / C# / CSS-SCSS / TS-TSX / Rust / JSON 配置
类别：尺寸间距 / 时序 / 动画 / 阈值 / 颜色透明度 / 字体 / 层级 / 圆角描边 / 其它

用法:
  param_extract.py --src <dir> --out work/ledger/params-old.csv
  param_extract.py --src <dir> --ext .xaml --out old.csv
  param_extract.py --compare old.csv new.csv
  param_extract.py --compare old.csv new.csv --gate      # 有「原版有新版无」退出码 1

退出码: 0 正常 / 1 --gate 且存在未处置差异 / 2 用法或文件错误
"""
import argparse
import csv
import os
import re
import sys

SKIP_DIRS = (".git", "node_modules", "target", "dist", "bin", "obj", "build", ".next")

# 关键词表：(类别, [关键词]) —— 匹配**包含关键词的完整标识符**，
# 这样 `dragThreshold` / `tipTimer.Interval` / `marginTop` 都能命中
# （⚠️ 实证陷阱：写 `\bThreshold\b` 抓不到 `dragThreshold`，因为 g 与 T 之间无词边界）
KEYWORDS = [
    ("尺寸间距", ["margin", "padding", "width", "height", "spacing", "gap",
                  "thickness", "size", "offsetx", "offsety"]),
    ("时序",     ["duration", "interval", "delay", "timeout", "debounce", "throttle",
                  "cooldown", "ttl", "begintime", "polling", "intervalms", "delayms"]),
    ("动画",     ["animation", "transition", "easing", "keytime", "storyboard",
                  "cubicbezier", "springs", "stiffness", "damping"]),
    ("阈值",     ["threshold", "deadzone", "epsilon", "tolerance", "maxretry",
                  "chunksize", "buffersize", "limit", "min_delta", "max_delta"]),
    ("颜色透明度", ["background", "foreground", "fill", "stroke", "color",
                    "opacity", "brush", "alpha"]),
    ("字体",     ["fontsize", "fontfamily", "fontweight", "lineheight", "letterspacing"]),
    ("层级",     ["zindex", "z_index"]),
    ("圆角描边", ["cornerradius", "borderradius", "borderwidth", "borderthickness",
                  "boxshadow", "border_width", "border_radius"]),
]

# 预编译：(类别, 关键词, 编译后的正则)  —— (?i) 忽略大小写，\w* 包裹以覆盖驼峰
RULES = [
    (cat, kw, re.compile(r"(?i)\b(\w*" + kw + r"\w*)\b"))
    for cat, kws in KEYWORDS for kw in kws
]

# 值：优先取引号内整段（XAML 的 `Margin="8,4,8,4"` 含逗号，必须整段取），
# 否则取到分隔符为止（C#/TS 的 `Interval = 400;`）
QUOTED_RE = re.compile(r"""^\s*[:=]\s*["']([^"']{1,80})["']""")
BARE_RE = re.compile(r"""^\s*[:=]\s*\{?\s*([^"';>,}\s]{1,60})""")

# 一个标识符可能同时命中多个类别（如 FontSize 命中「字体」与「尺寸间距」），
# 按优先级只保留一个，避免同一参数重复入账
CATEGORY_PRIORITY = {
    "字体": 0, "圆角描边": 1, "层级": 2, "颜色透明度": 3,
    "动画": 4, "阈值": 5, "时序": 6, "尺寸间距": 7,
}

TIME_UNIT = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*(ms|s|秒|毫秒)?\s*$", re.I)


def norm_time(v):
    """时间归一化：400 / 400ms / 0.4s / 0:0:0.4 → 毫秒数（字符串）。"""
    m = TIME_UNIT.match(v.strip())
    if not m:
        return None
    n = float(m.group(1))
    u = (m.group(2) or "").lower()
    if u in ("s", "秒"):
        n *= 1000
    return f"{n:g}ms"


def norm_size(v):
    """尺寸归一化：8 / 8px / 8pt / 8,4,8,4 → 去单位与空白。"""
    s = v.strip()
    parts = [p.strip() for p in s.split(",")]
    out = []
    for p in parts:
        m = re.match(r"^(-?\d+(?:\.\d+)?)\s*(px|pt|dp|rem|em|%)?$", p)
        if m:
            out.append(f"{float(m.group(1)):g}{m.group(2) or ''}")
        else:
            out.append(p)
    return ",".join(out)


def norm_key(k):
    """键归一化：大小写与分隔符不敏感。

    ⚠️ 实证陷阱：不做归一化的话，`FontSize`(XAML) 与 `fontSize`(TSX)
    会被当成两个完全不同的参数 —— 差集里全是噪音，真差异反而看不见。
    """
    return re.sub(r"[^a-z0-9]", "", (k or "").lower())


def norm_color(v):
    """颜色归一化：`#FF2D2D30`（带 alpha）与 `#2D2D30` 视为同色。"""
    m = re.match(r"^#([0-9a-fA-F]{8})$", v.strip())
    if m:
        h = m.group(1)
        if h[:2].upper() == "FF":
            return "#" + h[2:].upper()
        return "#" + h.upper()
    m = re.match(r"^#([0-9a-fA-F]{6})$", v.strip())
    if m:
        return "#" + m.group(1).upper()
    return v.strip().lower()


def normalize(cat, val):
    v = (val or "").strip()
    if not v:
        return None
    if v.startswith(("{Binding", "{StaticResource", "{DynamicResource", "{x:")):
        return None                      # 绑定/资源引用无法静态比，留给人工
    if cat in ("时序", "动画"):
        t = norm_time(v)
        if t:
            return t
        # 兜底：`TimeSpan.FromMilliseconds(180)` / `TimeSpan.FromSeconds(0.2)`
        # ⚠️ 陷阱：`Milliseconds` 里含 `seconds` —— 必须先排除 milli，否则 180 变 180000
        nums = re.findall(r"\(?\s*(\d+(?:\.\d+)?)\s*\)?", v)
        if nums:
            n = float(nums[0])
            if not re.search(r"millisecond|\bms\b", v, re.I):
                if re.search(r"second|\bs\b", v, re.I):
                    n *= 1000
            return f"{n:g}ms"
        return v
    if cat == "阈值":
        m = re.search(r"-?\d+(?:\.\d+)?", v)
        return m.group(0) if m else v
    if cat == "尺寸间距":
        return norm_size(v)
    if cat == "颜色透明度":
        return norm_color(v)
    return v


def extract_file(path, ext_filter):
    if ext_filter and not path.endswith(ext_filter):
        return []
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            lines = f.read().splitlines()
    except Exception:
        return []
    # 先收集一行的全部候选，再按 (key,value) 取优先级最高的类别
    buckets = {}          # (line, key, value) -> (priority, cat)
    for i, line in enumerate(lines, 1):
        s = line.strip()
        if s.startswith(("//", "#", "*", "<!--", "///")):
            continue
        for cat, kw, rx in RULES:
            prio = CATEGORY_PRIORITY.get(cat, 9)
            for km in rx.finditer(line):
                key = km.group(1)
                tail = line[km.end():]
                vm = QUOTED_RE.match(tail) or BARE_RE.match(tail)
                if not vm:
                    continue
                nval = normalize(cat, vm.group(1))
                if nval is None:
                    continue
                sig = (i, key, nval)
                prev = buckets.get(sig)
                if prev is None or prio < prev[0]:
                    buckets[sig] = (prio, cat)
        # 按出现顺序输出
    out = []
    for (i, key, nval), (_, cat) in sorted(buckets.items(), key=lambda x: (x[0][0], x[0][1])):
        out.append({
            "file": path, "line": i, "category": cat,
            "key": key, "value": nval,
            "raw": (lines[i - 1].strip()[:120] if i <= len(lines) else ""),
        })
    return out


def walk(src, ext):
    files = []
    for root, dirs, fns in os.walk(src):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for fn in fns:
            if not re.search(r"\.(xaml|cs|css|scss|less|ts|tsx|js|jsx|rs|json|vue)$", fn):
                continue
            if ext and not fn.endswith(ext):
                continue
            files.append(os.path.join(root, fn))
    return sorted(files)


def cmd_extract(a):
    if not os.path.isdir(a.src):
        print(f"❌ 目录不存在: {a.src}")
        return 2
    files = walk(a.src, a.ext)
    if not files:
        print(f"❌ 未找到源文件（src={a.src} ext={a.ext or '全部'}）")
        return 2
    rows = []
    for p in files:
        rows += extract_file(p, a.ext)
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    with open(a.out, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["file", "line", "category", "key", "value", "raw", "nkey"])
        w.writeheader()
        w.writerows(rows)
    cats = {}
    for r in rows:
        cats[r["category"]] = cats.get(r["category"], 0) + 1
    print(f"提取 {len(rows)} 条体验参数（{len(files)} 文件）→ {a.out}")
    for k in sorted(cats, key=lambda x: -cats[x]):
        print(f"   {k}: {cats[k]}")
    return 0


def load_csv(path):
    if not os.path.exists(path):
        print(f"❌ 文件不存在: {path}")
        return None
    with open(path, encoding="utf-8", errors="replace") as f:
        return list(csv.DictReader(f))


def agg(rows):
    """聚合成 {(category, nkey): {value: count}} —— 键按 norm_key 归一化。"""
    d = {}
    for r in rows:
        k = (r["category"], r.get("nkey") or norm_key(r["key"]))
        d.setdefault(k, {})
        d[k][r["value"]] = d[k].get(r["value"], 0) + 1
    return d


def cmd_compare(a):
    old, new = load_csv(a.old), load_csv(a.new)
    if old is None or new is None:
        return 2
    ao, an = agg(old), agg(new)

    only_old = sorted(set(ao) - set(an))
    only_new = sorted(set(an) - set(ao))
    diff = []
    for k in sorted(set(ao) & set(an)):
        vo, vn = set(ao[k]), set(an[k])
        if vo != vn:
            diff.append((k, sorted(vo), sorted(vn)))

    print("=" * 64)
    print(f"原版参数种类 {len(ao)} · 新版 {len(an)}")
    print("=" * 64)

    # 疑似改名：同类别下「原有新无」与「新有原无」值集合相同 → 多半是改名，不是差异
    renamed = []
    for ko in list(only_old):
        for kn in list(only_new):
            if ko[0] == kn[0] and set(ao[ko]) == set(an[kn]):
                renamed.append((ko, kn))
                only_old.remove(ko)
                only_new.remove(kn)
                break

    if renamed:
        print(f"\n🔄 【疑似改名】{len(renamed)} 组 —— 值一致，多半是命名不同（确认后记入别名）:")
        for ko, kn in renamed:
            print(f"   [{ko[0]}] {ko[1]} → {kn[1]}  (= {','.join(sorted(ao[ko])[:3])})")

    if only_old:
        print(f"\n❌ 【原版有、新版无】{len(only_old)} 类 —— 这些就是会丢失的体验:")
        for k in only_old:
            vals = ",".join(sorted(ao[k])[:4])
            print(f"   [{k[0]}] {k[1]} = {vals}")
    if diff:
        print(f"\n⚠️  【值不同】{len(diff)} 类 —— 需要判断是有意变更还是漂移:")
        for k, vo, vn in diff:
            nums_o = set(re.findall(r"-?\d+(?:\.\d+)?", ",".join(vo)))
            nums_n = set(re.findall(r"-?\d+(?:\.\d+)?", ",".join(vn)))
            hint = ""
            if len(nums_o) > 1 and nums_o == nums_n:
                hint = ("  ⚠️ 数值集合相同但顺序不同 —— 注意简写顺序约定："
                        "XAML 是「左,上,右,下」，CSS 是「上 右 下 左」，别直接抄")
            print(f"   [{k[0]}] {k[1]}: 原 {','.join(vo[:3])}  →  新 {','.join(vn[:3])}{hint}")
    if only_new:
        print(f"\nℹ️  【新版多出】{len(only_new)} 类 —— 记入反向清单（勿删）:")
        for k in only_new[:20]:
            print(f"   [{k[0]}] {k[1]} = {','.join(sorted(an[k])[:3])}")

    if not (only_old or diff or only_new):
        print("\n✅ 体验参数完全一致")

    print("\n⚠️ 每条差异都必须落 P-N 卡：原值 / 新版值 / 差异理由 / 性质（等比迁移|需缩放|"
          "平台惯例|技术权宜|有意变更）")
    print("   **可以不照搬，但必须知道搬前是什么样。**")

    if a.gate and (only_old or diff):
        return 1
    return 0


def main():
    ap = argparse.ArgumentParser(description="体验参数提取与双侧差集")
    ap.add_argument("--src")
    ap.add_argument("--ext", default="")
    ap.add_argument("--out", default="ledger/params.csv")
    ap.add_argument("--compare", action="store_true")
    ap.add_argument("--old")
    ap.add_argument("--new")
    ap.add_argument("files", nargs="*", help="等价写法: --compare old.csv new.csv")
    ap.add_argument("--gate", action="store_true", help="存在差异退出码 1")
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
