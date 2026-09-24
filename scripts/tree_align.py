#!/usr/bin/env python3
"""UI 树对齐（S2M/S3）—— 原版 UIA 树 ↔ 新版可访问性树的节点映射。

**为什么需要**：我们能导出两棵树，却只有"哪里不一样"，
缺"差异对应哪个原版节点"——像素差只是症状，不能作为穷尽验收的终态证据。

**⚠️ 核心认知**：新栈可访问性树**不是**原版 UIA 树的天然同构物。
WPF 暴露 AutomationId / ControlType / BoundingRectangle / IsEnabled / IsOffscreen；
React 的无障碍树偏语义角色、文本、焦点顺序、ARIA 状态。
自定义控件、装饰元素、虚拟化列表、弹出层常出现 **1:N、N:1、多对多**。

四级对齐（从稳到贵，不许跳级）:
  L1 锚点匹配   稳定键值 O(n)  —— automation_id / runtime_id / name
  L2 同构映射   NetworkX VF2++（唯一同构候选时）
  L3 结构细化   GumTree 思路：同构子树 → 共享后代细化 → 编辑脚本
  L4 编辑距离   APTED / Zhang-Shasha（**仅未匹配连通块，且有预算**）

用法:
  tree_align.py --old old.uia.json --new new.a11y.json --out alignment.json
  tree_align.py --old old.json --new new.json --gate      # 未匹配节点超阈值退出码 1
  tree_align.py --budget                                  # 打印复杂度预算

退出码: 0 正常 / 1 --gate 且未匹配过多或疑似结构变化 / 2 用法或文件错误
"""
import argparse
import json
import os
import sys

# 候选匹配向量：不能只依赖 role
MATCH_KEYS = [
    ("automation_id", "AutomationId / 显式自动化标识", 1.0),
    ("runtime_id", "runtime_id 哈希", 0.9),
    ("name", "可访问名称", 0.7),
    ("control_type", "控件类型", 0.6),
    ("text", "文本内容", 0.6),
    ("geometry", "几何中心 + 宽高", 0.4),
    ("depth", "父子深度", 0.2),
]

# 归一化规则：不做归一化，两棵树永远对不上
NORMALIZE_RULES = [
    ("忽略装饰容器", "Border / Decorator / AdornerLayer / React fragment 折叠"),
    ("合并重复容器", "StackPanel / Grid / <div> 包装层按父子链折叠"),
    ("几何软匹配", "包围盒用容差比较，不要求像素级相等"),
    ("虚拟化恢复", "同 ID 节点按可见顺序恢复，不按 DOM 顺序"),
    ("role 回退", "ListViewItem → role=row / 列表项 / 虚拟滚动组合，允许多候选"),
]

# 复杂度预算：L4 是高复杂度，必须限制
BUDGET = {
    "max_subtree_nodes": 200,
    "max_subtree_height": 8,
    "max_ted_ops": 500,
    "degrade_to": "连通域/区域匹配（不再输出假精确映射）",
}


def load(path):
    if not os.path.exists(path):
        print(f"❌ 文件不存在: {path}")
        return None
    with open(path, encoding="utf-8", errors="replace") as f:
        return json.load(f)


def flatten(node, out=None, depth=0):
    """把树摊平，便于按候选键做 L1 锚点匹配。"""
    if out is None:
        out = []
    if isinstance(node, dict):
        rec = {k: node.get(k) for k, _, _ in MATCH_KEYS}
        rec["depth"] = depth
        rec["_raw"] = node
        out.append(rec)
        for c in node.get("children", []) or []:
            flatten(c, out, depth + 1)
    elif isinstance(node, list):
        for c in node:
            flatten(c, out, depth)
    return out


def l1_anchor(old_nodes, new_nodes):
    """L1：稳定键锚点匹配（O(n)）。"""
    matched, used_new = [], set()
    for i, o in enumerate(old_nodes):
        best, bs, bj = None, 0.0, None
        for j, n in enumerate(new_nodes):
            if j in used_new:
                continue
            s = 0.0
            for k, _, w in MATCH_KEYS:
                ov, nv = o.get(k), n.get(k)
                if ov is None or nv is None:
                    continue
                if k == "geometry":
                    try:
                        close = all(abs(float(a) - float(b)) <= 2.0
                                    for a, b in zip(ov, nv))
                        s += w * (1.0 if close else 0.0)
                    except Exception:
                        pass
                elif str(ov).strip().lower() == str(nv).strip().lower():
                    s += w
            if s > bs:
                best, bs, bj = n, s, j
        if best is not None and bs >= 0.9:
            matched.append({"old_idx": i, "new_idx": bj, "score": round(bs, 3),
                            "level": "L1-anchor"})
            used_new.add(bj)
    unmatched_old = [i for i in range(len(old_nodes))
                     if i not in {m["old_idx"] for m in matched}]
    unmatched_new = [j for j in range(len(new_nodes)) if j not in used_new]
    return matched, unmatched_old, unmatched_new


def cmd_budget(a):
    print("L4 复杂度预算（超预算必须降级，不许输出假精确映射）:")
    for k, v in BUDGET.items():
        print(f"   {k:<22} {v}")
    print("\n四级对齐（从稳到贵，不许跳级）:")
    for lv, why in [("L1 锚点匹配", "稳定键值 O(n)"),
                    ("L2 同构映射", "NetworkX VF2++，唯一同构候选时"),
                    ("L3 结构细化", "GumTree：同构子树 → 共享后代细化 → 编辑脚本"),
                    ("L4 编辑距离", "APTED / Zhang-Shasha，仅未匹配连通块")]:
        print(f"   {lv:<14} {why}")
    print("\n候选匹配向量（**不能只依赖 role**）:")
    for k, why, w in MATCH_KEYS:
        print(f"   {k:<16} {w:<5} {why}")
    print("\n归一化规则（不做归一化，两棵树永远对不上）:")
    for name, why in NORMALIZE_RULES:
        print(f"   {name:<14} {why}")
    return 0


def cmd_align(a):
    old, new = load(a.old), load(a.new)
    if old is None or new is None:
        return 2
    on, nn = flatten(old), flatten(new)
    matched, um_old, um_new = l1_anchor(on, nn)

    total_old = len(on)
    cov = len(matched) / total_old if total_old else 0.0
    result = {
        "old_nodes": total_old,
        "new_nodes": len(nn),
        "matched": len(matched),
        "coverage": round(cov, 3),
        "unmatched_old": um_old,
        "unmatched_new": um_new,
        "matches": matched,
        "levels_used": ["L1-anchor"],
        "budget": BUDGET,
        "pending_levels": ["L2-vf2pp", "L3-gumtree", "L4-apted"],
        "note": "本脚本内置 L1；L2/L3/L4 需 NetworkX / GumTree / APTED，"
                "环境不具备时如实标 pending，**不伪造精确映射**",
    }

    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print("=" * 64)
    print(f"树对齐 → {a.out}")
    print("=" * 64)
    print(f"   原版节点 {total_old} · 新版节点 {len(nn)}")
    print(f"   L1 锚点匹配 {len(matched)} (覆盖率 {cov:.1%})")
    print(f"   未匹配 原版 {len(um_old)} / 新版 {len(um_new)}")

    if um_new:
        print("\nℹ️  【新版多出】可能是增强项 → 记入**反向清单（勿删）**")
    if um_old:
        print("\n❌ 【原版有新版无】**可能是功能缺失** → 逐条落 unknown 或功能缺口")

    print("\n⚠️ 未匹配节点需走 L2/L3/L4；**超预算一律降级为区域匹配**，")
    print("   不许为了「覆盖率好看」输出假的精确映射。")
    print("\n⚠️ 装饰层消失但语义结构保留 → **不应判为失败**（换掉权宜之计是对的）。")

    if a.gate and um_old and cov < (a.min_coverage if hasattr(a, "min_coverage") else 0.9):
        return 1
    return 0


def main():
    ap = argparse.ArgumentParser(description="UI 树对齐（原版 UIA ↔ 新版可访问性树）")
    ap.add_argument("--old", help="原版控件树 JSON")
    ap.add_argument("--new", help="新版可访问性树 JSON")
    ap.add_argument("--out", default="ledger/alignment.json")
    ap.add_argument("--gate", action="store_true", help="覆盖率不足退出码 1")
    ap.add_argument("--min-coverage", type=float, default=0.9)
    ap.add_argument("--budget", action="store_true", help="打印预算与匹配向量")
    a = ap.parse_args()

    if a.budget:
        return cmd_budget(a)
    if not (a.old and a.new):
        print("❌ 需要 --old 与 --new（或 --budget）")
        return 2
    return cmd_align(a)


if __name__ == "__main__":
    sys.exit(main())
