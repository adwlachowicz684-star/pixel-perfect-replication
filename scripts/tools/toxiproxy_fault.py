#!/usr/bin/env python3
"""Toxiproxy 封装 —— 传输层故障注入。

**定位**：只管**传输层**（latency/down/bandwidth/slow_close/timeout/
reset_peer/slicer/limit_data/packet_loss）。

**⚠️ 不能做的事**（别指望它）：
- ❌ NTFS ACL、磁盘配额、独占文件锁 → 那是 Detours / IO shim 的活
- ❌ WPF COM 调用失败 → 同上
- ❌ 内容层篡改 → 那是 mitmproxy / WireMock 的活

**工具分层，互相不能替代**：
  mitmproxy/WireMock 管内容层 · **Toxiproxy 管传输层** · libfiu 管 POSIX 层

用法:
  toxiproxy_fault.py --catalog                       # 故障目录与三列表
  toxiproxy_fault.py --check-env                     # 校验 toxiproxy 可用
  toxiproxy_fault.py --gen ledger/network_faults.csv # 生成三列表骨架

退出码: 0 正常 / 2 工具不可用或用法错误
"""
import argparse
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import require, emit, print_summary  # noqa: E402

# 支持的 toxic 类型
TOXICS = [
    ("latency", "延迟", "latency(ms) + jitter(ms)"),
    ("down", "断开", "下游不可用"),
    ("bandwidth", "限速", "rate(KB/s)"),
    ("slow_close", "慢关闭", "delay(ms)"),
    ("timeout", "超时", "timeout(ms) —— **测重试与不重复提交**"),
    ("reset_peer", "重置连接", "TCP RST"),
    ("slicer", "切片", "把包切碎 —— **测部分响应**"),
    ("limit_data", "限流量", "bytes"),
    ("packet_loss", "丢包", "percentage"),
]

# 故障 → 原版可观察行为 → 新版本要求
TRIPLE = [
    ("连接超时", "timeout", "重试/提示/状态保留", "同提示、同重试上限、**不重复提交**"),
    ("断网瞬间", "down", "命令是否原子取消", "取消令牌在 N 毫秒内传播"),
    ("慢网络", "latency", "UI 是否冻结", "主窗口保持响应"),
    ("部分响应", "slicer", "是否写脏缓存", "临时文件原子替换或回滚"),
    ("重复响应", "latency", "是否重复导入", "幂等键 / 去重"),
]


def cmd_catalog(a):
    print("=" * 72)
    print("Toxiproxy toxic 类型（**仅传输层**）")
    print("=" * 72)
    for k, name, param in TOXICS:
        print(f"   {k:<14} {name:<8} {param}")
    print("\n" + "=" * 72)
    print("故障三列表（故障 → 原版可观察行为 → 新版本要求）")
    print("=" * 72)
    for name, toxic, old, new in TRIPLE:
        print(f"\n   {name}  [{toxic}]")
        print(f"      原版: {old}")
        print(f"      新版: {new}")
    print("\n⚠️ **「没有崩溃」≠「韧性等价」** —— 两条不同的门禁。")
    print("   原版可能也错了，但新版应与原版在**同一前置条件下表现一致**。")
    print("\n⚠️ 原版行为必须先采集 —— **不许凭空生成新版韧性**。")
    return 0


def cmd_gen(a):
    os.makedirs(os.path.dirname(a.gen) or ".", exist_ok=True)
    cols = ["id", "category", "name", "toxic", "precondition", "fault",
            "observed_error", "recovery", "postcondition",
            "user_visible_message", "old_behavior", "new_behavior", "status"]
    with open(a.gen, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for i, (name, toxic, old, new) in enumerate(TRIPLE, 1):
            w.writerow([f"NET-{i:03d}", "网络", name, toxic,
                        "TODO", f"toxiproxy {toxic}", "TODO", "TODO",
                        "TODO", "TODO",
                        "TODO：从原版采集", new, "待采"])
    print(f"已生成网络故障三列表骨架: {a.gen}")
    print("\n⚠️ `old_behavior` 留 TODO = **原版行为未采集** ——")
    print("   `fault_matrix.py --check --gate` 会阻断。")
    print("   **先采原版，再谈新版韧性。**")
    return 0


def cmd_env(a):
    spec = require("toxiproxy")
    if spec is None:
        emit("toxiproxy", False, a.out,
             warnings=["toxiproxy 不可用 —— 传输层故障注入未做，必须进 unknown"])
        return 2
    emit("toxiproxy", True, a.out,
         evidence=["toxiproxy-server 可用", f"支持 {len(TOXICS)} 类 toxic"],
         warnings=["**仅覆盖传输层** —— 文件/COM/注册表故障需 Detours 或 IO shim"])
    print_summary(emit("toxiproxy", True, None,
                       evidence=["toxiproxy-server 可用",
                                 f"{len(TOXICS)} 类 toxic 可用"],
                       warnings=["**仅覆盖传输层**"]))
    return 0


def main():
    ap = argparse.ArgumentParser(description="Toxiproxy 传输层故障注入")
    ap.add_argument("--catalog", action="store_true")
    ap.add_argument("--gen")
    ap.add_argument("--check-env", action="store_true")
    ap.add_argument("--out", default="ledger/network_faults.json")
    a = ap.parse_args()

    if a.catalog:
        return cmd_catalog(a)
    if a.gen:
        return cmd_gen(a)
    if a.check_env:
        return cmd_env(a)
    print("❌ 需要 --catalog / --gen / --check-env 之一")
    return 2


if __name__ == "__main__":
    sys.exit(main())
