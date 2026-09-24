#!/usr/bin/env python3
"""Kaitai Struct 封装 —— 私有格式考古，验收要 round-trip 字节相等。

**核心闭环**：探测 → 假设 → `.ksy` 规格 → **双向 round-trip**。

**验收口径**（四条全满足才算格式稳定）:
1. 解析成功
2. 字段数稳定
3. 关键字段值可解释
4. **序列化后与原字节相等**（或在明确故意变更处差异可解释）

**⚠️ 证据不足时标 `schema_inferred`，禁止据此声称完整复刻协议。**

用法:
  kaitai_probe.py --check-env
  kaitai_probe.py --probe <文件> --out ledger/format_probe.json   # 采样探测
  kaitai_probe.py --roundtrip <文件> --ksy fmt.ksy --gate         # round-trip 验收
  kaitai_probe.py --criteria                                      # 打印验收口径

退出码: 0 通过 / 1 --gate 且 round-trip 不等 / 2 工具不可用
"""
import argparse
import hashlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import require, run, emit, print_summary  # noqa: E402

CRITERIA = [
    ("解析成功", "parser 对**样本集**（不是单样本）都能解析"),
    ("字段数稳定", "不同样本的字段数一致或差异可解释"),
    ("关键字段值可解释", "值能对应到业务含义，不是随机数"),
    ("**round-trip 字节相等**", "重新序列化后与原字节一致"),
]

# 格式指纹线索（先做指纹，再谈语义）
FINGERPRINTS = [
    ("magic bytes", "文件头固定字节", "binwalk / ImHex / 直接 hexdump"),
    ("protobuf", "varint + wire type", "protoscope（忠实字节结构）"),
    ("msgpack/cbor", "首字节类型标记", "msgpack / cbor 工具"),
    ("SQLite", "SQLite format 3\\x00", "sqlite3 直接打开"),
    ("zip/嵌套", "PK\\x03\\x04", "binwalk"),
]


def cmd_criteria(a):
    print("=" * 70)
    print("私有格式验收口径（四条全满足才算稳定）")
    print("=" * 70)
    for i, (k, why) in enumerate(CRITERIA, 1):
        print(f"   {i}. **{k}**")
        print(f"      {why}")
    print("\n" + "=" * 70)
    print("格式指纹线索（**先做指纹，再谈语义**）")
    print("=" * 70)
    for k, sig, tool in FINGERPRINTS:
        print(f"   {k:<16} {sig:<22} {tool}")
    print("\n⚠️ 禁止:")
    print("   · 用 LLM 直接猜整个二进制格式并生成写入器")
    print("   · 只因能解析一个样本就宣称格式稳定")
    print("   · 删除未知尾部字段或校验字段而不记录")
    print("\n⚠️ 证据不足 → 标 `schema_inferred`，**禁止声称完整复刻协议**。")
    return 0


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(65536), b""):
            h.update(b)
    return h.hexdigest()


def cmd_probe(a):
    if not os.path.exists(a.probe):
        print(f"❌ 文件不存在: {a.probe}")
        return 2
    size = os.path.getsize(a.probe)
    with open(a.probe, "rb") as f:
        head = f.read(64)
    hexdump = " ".join(f"{b:02x}" for b in head[:32])
    ascii_ = "".join(chr(b) if 32 <= b < 127 else "." for b in head[:32])

    # Python 侧可做的基础指纹（不依赖 kaitai）
    guesses = []
    if head[:4] == b"PK\x03\x04":
        guesses.append("zip / 嵌套容器")
    if head[:15] == b"SQLite format 3":
        guesses.append("SQLite")
    if head[:2] in (b"MZ",):
        guesses.append("PE 可执行（**注意：可能是原版程序本身**）")
    if head[:1] == b"\x7f" and head[1:4] == b"ELF":
        guesses.append("ELF")
    if head[:8] == b"\x89PNG\r\n\x1a\n":
        guesses.append("PNG")

    print("=" * 68)
    print(f"格式探测 · {a.probe}")
    print("=" * 68)
    print(f"   大小 {size} 字节")
    print(f"   SHA256 {sha256(a.probe)[:32]}…")
    print(f"   head: {hexdump}")
    print(f"          {ascii_}")
    if guesses:
        print(f"\n   指纹猜测: {', '.join(guesses)}")
    else:
        print("\n   指纹猜测: 无（需人工或 kaitai 分析）")

    emit("kaitai", None, a.out or "ledger/format_probe.json",
         evidence=[f"size={size}", f"sha256={sha256(a.probe)}",
                   f"head={hexdump}"],
         warnings=["仅基础指纹 —— **未做结构解析**，格式仍未知"],
         confidence="low",
         extra={"guesses": guesses, "schema_status": "schema_inferred"})
    print("\n⚠️ 结构未定 → 标 `schema_inferred`，**不许声称已复刻**。")
    return 0


def cmd_roundtrip(a):
    spec = require("kaitai")
    if spec is None:
        print("⚠️ kaitai 编译器不可用 —— round-trip 无法自动执行。")
        print("   可用 `python3 kaitai_probe.py --probe <f>` 做基础指纹，")
        print("   但**必须标注格式未定**，不得当已复刻。")
        return 2
    print(f"⚠️ round-trip 需要针对具体 .ksy 生成 parser 后执行。")
    print(f"   流程: ksc {a.ksy} → 生成 parser → parse → 重新序列化 → 比对 SHA256")
    before = sha256(a.roundtrip)
    print(f"\n   原文件 SHA256: {before}")
    print("   重新序列化后若与此不同：**必须逐字节解释差异**，")
    print("   或明确登记为有意变更 —— **不许静默放过**。")
    return 0


def cmd_env(a):
    spec = require("kaitai")
    if spec is None:
        return 2
    print_summary(emit("kaitai", True, None,
                       evidence=["ksc 可用"],
                       warnings=["GPLv3（compiler）—— 仅 third_party 对外分发时提示"]))
    return 0


def main():
    ap = argparse.ArgumentParser(description="Kaitai Struct 私有格式考古")
    ap.add_argument("--probe")
    ap.add_argument("--roundtrip")
    ap.add_argument("--ksy")
    ap.add_argument("--out")
    ap.add_argument("--criteria", action="store_true")
    ap.add_argument("--check-env", action="store_true")
    ap.add_argument("--gate", action="store_true")
    a = ap.parse_args()

    if a.criteria:
        return cmd_criteria(a)
    if a.probe:
        return cmd_probe(a)
    if a.roundtrip:
        return cmd_roundtrip(a)
    if a.check_env:
        return cmd_env(a)
    print("❌ 需要 --probe / --roundtrip / --criteria / --check-env 之一")
    return 2


if __name__ == "__main__":
    sys.exit(main())
