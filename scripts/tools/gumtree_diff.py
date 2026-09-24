#!/usr/bin/env python3
"""GumTree 封装 —— 树 diff，识别 move / rename / insert / delete（L3 结构细化）。

**在四级树对齐里的位置**（不许跳级）:
  L1 锚点匹配 → L2 VF2++ → **L3 GumTree** → L4 APTED（仅未匹配连通块）

**⚠️ 借鉴算法，不原样迁移语义**：
GumTree 的语言 parser 与 AST 概念**与 UI 树并非一一对应**。
要复用的是三阶段思路：自上而下找同构子树 → 自下而上用共享后代细化 → 生成编辑脚本。

**许可提醒**：GumTree 是 **AGPL-3.0** —— 仅 `third_party` 对外分发时提示；自有项目不受限。

用法:
  gumtree_diff.py --check-env
  gumtree_diff.py --old a.json --new b.json --out ledger/tree_edit_ops.json
  gumtree_diff.py --stages          # 打印三阶段与归一化规则

退出码: 0 正常 / 2 工具不可用
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import require, run, emit, print_summary  # noqa: E402

STAGES = [
    ("自上而下", "找最大同构子树", "建立粗粒度锚点"),
    ("自下而上", "用共享后代细化", "把锚点扩到叶子"),
    ("生成编辑脚本", "move / rename / insert / delete", "**能识别移动与重命名**"),
]

# UI 树特有归一化（不做则两棵树永远对不上）
NORMALIZE = [
    ("忽略装饰容器", "Border / Decorator / AdornerLayer / React fragment 折叠"),
    ("合并重复容器", "StackPanel / Grid / <div> 包装层按父子链折叠"),
    ("几何软匹配", "包围盒用容差比较，不要求像素级相等"),
    ("虚拟化恢复", "同 ID 节点按**可见顺序**恢复，不按 DOM 顺序"),
    ("role 回退", "ListViewItem → role=row / 列表项 / 虚拟滚动组合，**允许多候选**"),
]


def cmd_stages(a):
    print("=" * 70)
    print("GumTree 三阶段（借鉴算法，不原样迁移语义）")
    print("=" * 70)
    for k, what, why in STAGES:
        print(f"   {k:<14} {what:<22} {why}")
    print("\n" + "=" * 70)
    print("UI 树特有归一化（不做则两棵树永远对不上）")
    print("=" * 70)
    for k, why in NORMALIZE:
        print(f"   {k:<14} {why}")
    print("\n⚠️ **装饰层消失但语义结构保留 → 不应判为失败**")
    print("   （换掉权宜之计是对的）")
    print("\n⚠️ 许可：GumTree 为 **AGPL-3.0** —— 仅 `third_party` 对外分发时提示；自有项目不受限。")
    return 0


def cmd_run(a):
    if not (os.path.exists(a.old) and os.path.exists(a.new)):
        print("❌ 文件不存在")
        return 2
    spec = require("gumtree")
    if spec is None:
        emit("gumtree", False, a.out,
             warnings=["gumtree 不可用 —— 树编辑脚本未生成，"
                       "L3 结构细化未做，必须进 unknown"])
        return 2

    cmd = ["gumtree", "difftree", a.old, a.new]
    rc, out, err = run(cmd, timeout=300)
    combined = (out or "") + (err or "")
    ops = []
    for line in combined.splitlines():
        s = line.strip()
        if not s:
            continue
        low = s.lower()
        for op in ("insert", "delete", "move", "update", "rename"):
            if low.startswith(op) or f" {op} " in low or f"-{op}" in low:
                ops.append({"op": op, "raw": s[:160]})
                break

    warn = []
    if not ops:
        warn.append("未解析到编辑操作 —— 确认输入格式或工具输出格式")
    moves = [o for o in ops if o["op"] in ("move", "rename")]
    if moves:
        warn.append(f"{len(moves)} 处 move/rename —— "
                    "**可能是架构性调整**，需 S3 性质判定裁决")

    rec = emit("gumtree", True, a.out,
               evidence=[f"old={a.old}", f"new={a.new}",
                         f"编辑操作 {len(ops)} 条"],
               warnings=warn,
               extra={"ops": ops, "raw": combined[:4000],
                      "move_rename_count": len(moves)})
    print_summary(rec)
    return 0


def cmd_env(a):
    spec = require("gumtree")
    if spec is None:
        return 2
    print_summary(emit("gumtree", True, None,
                       evidence=["gumtree 可用"],
                       warnings=["AGPL-3.0 —— 仅 third_party 对外分发时提示"]))
    return 0


def main():
    ap = argparse.ArgumentParser(description="GumTree 树 diff（L3 结构细化）")
    ap.add_argument("--old")
    ap.add_argument("--new")
    ap.add_argument("--out", default="ledger/tree_edit_ops.json")
    ap.add_argument("--stages", action="store_true")
    ap.add_argument("--check-env", action="store_true")
    a = ap.parse_args()
    if a.stages:
        return cmd_stages(a)
    if a.check_env:
        return cmd_env(a)
    if not (a.old and a.new):
        print("❌ 需要 --old/--new，或 --stages / --check-env")
        return 2
    return cmd_run(a)


if __name__ == "__main__":
    sys.exit(main())
