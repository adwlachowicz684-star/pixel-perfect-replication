#!/usr/bin/env python3
"""差分测试与 oracle 分类（S6/S7）—— 用原版自己当 oracle。

**为什么最高价值**：差分测试**不需要人先写 oracle**——原版的行为就是现成的 oracle。
"原版接受 / 新版拒绝同一输入"或反之，就是一条语义回归。
这类 bug **不产生崩溃**，纯视觉测试与纯单测都抓不到。

**与属性测试的关系（正交，不是替代）**：
| | 属性测试（fast-check/proptest） | 差分测试（本脚本） |
|---|---|---|
| oracle | 人写属性 | **另一实现** |
| 适用 | S5 择优**后**的新实现加固 | 复刻过程中的行为等价性 |

**复刻场景优先差分测试**，因为原版行为就是现成的 oracle。

四类 oracle 判定（S3 性质判定的实际输入）:
  1. real_regression   真回归 —— 原版成功新版失败（或反之）→ S2B BUG 直报
  2. workaround_removed 权宜之计消除 —— 原版因旧框架限制产生的非法/容错路径，
                        新版按正确语义拒绝 → S5 择优的正当理由，**必须附 S4 契约变更说明**
  3. nondeterministic  浮点/字体/渲染非确定 → 进 S7V 而非 S3（允许容差）
  4. external_contract 外部契约变更 —— 录制集过期 → **触发 S0 重采，不是改 oracle**

用法:
  # 成对跑两个程序并比对
  diff_fuzz.py --old ./old_app --new ./new_app --inputs inputs/ --timeout 10
  # 只分类已有的成对输出
  diff_fuzz.py --pairs pairs.jsonl --out oracle.json --gate
  # 打印四类判据
  diff_fuzz.py --classes

退出码: 0 无真回归 / 1 存在 real_regression 或未定项 / 2 用法错误
"""
import argparse
import json
import os
import subprocess
import sys

CLASSES = [
    ("real_regression", "真回归",
     "原版成功新版失败，或反之；或同输入产出不同结果",
     "S2B BUG 直报 —— 这是**硬失败**"),
    ("workaround_removed", "权宜之计消除",
     "原版因旧框架限制产生的非法/容错路径，新版按正确语义拒绝",
     "S5 择优的正当理由，**必须附 S4 契约变更说明**；不许默认放行"),
    ("nondeterministic", "非确定",
     "浮点 / 字体 / 渲染 / 时序导致的差异",
     "进 S7V 视觉门禁而非 S3；允许容差但**不许无理由豁免**"),
    ("external_contract", "外部契约变更",
     "录制集过期、外部依赖变了",
     "**触发 S0 重采**，不是改 oracle —— 改 oracle 会掩盖真实问题"),
]

# 输入变异策略（seed corpus 应来自 har_diff 结果，不是随机生成）
MUTATION_STRATEGIES = [
    ("structural", "结构变异", "JSON 字段增删、类型替换"),
    ("boundary", "边界变异", "负数、零、max、Unicode、路径穿越"),
    ("ordering", "顺序变异", "多请求并发与乱序"),
]

# ⚠️ 适配 NEZHA 的 δ-diversity：用"行为向量距离"选种，
# 不是代码覆盖率 —— 覆盖率引导会让新版"多跑"而忽视"结果不同"
FITNESS_NOTE = (
    "δ-diversity：每次变异后用「原版与新版行为向量距离」选下一代，"
    "**而不是代码覆盖率**。覆盖率引导会让新版多跑却忽视结果不同。"
)


def cmd_classes(a):
    print("=" * 70)
    print("四类 oracle 判定（S3 性质判定的实际输入）")
    print("=" * 70)
    for key, name, signal, action in CLASSES:
        print(f"\n【{name}】 {key}")
        print(f"   判定: {signal}")
        print(f"   处置: {action}")
    print("\n" + "=" * 70)
    print("变异策略（seed corpus 应来自网络录制，不是随机生成）")
    print("=" * 70)
    for k, name, why in MUTATION_STRATEGIES:
        print(f"   {k:<14} {name} — {why}")
    print(f"\n⚠️ {FITNESS_NOTE}")
    print("\n⚠️ 与属性测试正交：属性测试人写 oracle，差分测试用另一实现当 oracle。")
    print("   **复刻场景优先差分测试** —— 原版行为就是现成的 oracle。")
    return 0


def run_pair(old_cmd, new_cmd, inp, timeout):
    def one(cmd):
        try:
            r = subprocess.run(cmd, shell=True, input=inp, capture_output=True,
                               text=True, timeout=timeout)
            return {"rc": r.returncode, "out": r.stdout, "err": r.stderr}
        except subprocess.TimeoutExpired:
            return {"rc": -1, "out": "", "err": "TIMEOUT"}
        except Exception as e:
            return {"rc": -2, "out": "", "err": str(e)}
    return one(old_cmd), one(new_cmd)


def classify(o, n, tol):
    """四类分类。判不了就 unknown —— 不许猜。"""
    if o["rc"] == -1 or n["rc"] == -1:
        return ("real_regression", "超时差异",
                ["一侧超时"], [])
    if o["out"] == n["out"] and o["err"] == n["err"] and o["rc"] == n["rc"]:
        return ("identical", "完全一致", [], [])

    ev, conf = [], []
    if o["rc"] != n["rc"]:
        ev.append(f"退出码不同 原={o['rc']} 新={n['rc']}")
        if o["rc"] == 0 and n["rc"] != 0:
            # 原版接受、新版拒绝 —— 这是最典型的语义回归
            return ("real_regression",
                    "原版成功而新版失败（新版拒绝了原版接受的输入）",
                    ev, ["也可能是权宜之计消除：需确认该输入在原版是否本就该被拒绝"])
        if o["rc"] != 0 and n["rc"] == 0:
            # 原版失败、新版成功 —— 两种可能，必须人工判
            return ("unknown",
                    "原版失败而新版成功：可能是权宜之计消除，也可能是新版吞掉了错误",
                    ev, ["**新版成功于原版拒绝的输入** —— 若原版拒绝是对的，"
                         "这就是新版放行了非法输入（危险）"])
    try:
        if abs(float(o["out"].strip()) - float(n["out"].strip())) <= tol:
            return ("nondeterministic", "数值在容差内",
                    [f"差值 ≤ {tol}"], ["也可能是真实但极小的行为变化"])
    except Exception:
        pass

    ev.append(f"stdout 长度 原={len(o['out'])} 新={len(n['out'])}")
    if o["err"] and not n["err"]:
        conf.append("原版报错而新版没有 → 可能是新版吞掉了错误（**危险**）")
    if n["err"] and not o["err"]:
        conf.append("新版报错而原版没有 → 多数是真回归")

    return ("unknown", "证据不足，需人工判", ev, conf)


def cmd_run(a):
    inputs = []
    if a.inputs and os.path.isdir(a.inputs):
        for fn in sorted(os.listdir(a.inputs)):
            p = os.path.join(a.inputs, fn)
            if os.path.isfile(p):
                with open(p, encoding="utf-8", errors="replace") as f:
                    inputs.append((fn, f.read()))
    elif a.inputs and os.path.isfile(a.inputs):
        with open(a.inputs, encoding="utf-8", errors="replace") as f:
            inputs.append((os.path.basename(a.inputs), f.read()))
    if not inputs:
        print("❌ 未找到输入")
        return 2

    results = []
    for name, inp in inputs:
        o, n = run_pair(f"{a.old} < /dev/stdin" if False else a.old,
                        a.new, inp, a.timeout)
        kind, why, ev, conf = classify(o, n, a.tol)
        results.append({"input": name, "class": kind, "reason": why,
                        "evidence": ev, "conflicting": conf,
                        "old": {"rc": o["rc"], "out_len": len(o["out"]),
                                "err": o["err"][:200]},
                        "new": {"rc": n["rc"], "out_len": len(n["out"]),
                                "err": n["err"][:200]}})

    if a.out:
        os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

    counts = {}
    for r in results:
        counts[r["class"]] = counts.get(r["class"], 0) + 1

    print("=" * 68)
    print(f"差分测试 · {len(results)} 个输入")
    print("=" * 68)
    for k, v in sorted(counts.items(), key=lambda x: -x[1]):
        print(f"   {k:<22} {v}")

    bad = [r for r in results if r["class"] in ("real_regression", "unknown")]
    if bad:
        print(f"\n❌ {len(bad)} 项需处置:")
        for r in bad[:10]:
            print(f"   [{r['class']}] {r['input']} — {r['reason']}")
            for c in r["conflicting"]:
                print(f"        ⚠️ {c}")
    else:
        print("\n✅ 无真回归与未定项")

    print(f"\n⚠️ {FITNESS_NOTE}")
    print("\n⚠️ **未命中率不得把 0 当目标** —— 未命中意味着：")
    print("   原版有条死代码路径（S2B BUG 候选），或新版少实现了一条功能。")

    return 1 if (a.gate and bad) else 0


def cmd_pairs(a):
    if not os.path.exists(a.pairs):
        print(f"❌ 文件不存在: {a.pairs}")
        return 2
    results = []
    with open(a.pairs, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except Exception:
                continue
            o = {"rc": d.get("old_rc", 0), "out": str(d.get("old_out", "")),
                 "err": str(d.get("old_err", ""))}
            n = {"rc": d.get("new_rc", 0), "out": str(d.get("new_out", "")),
                 "err": str(d.get("new_err", ""))}
            kind, why, ev, conf = classify(o, n, a.tol)
            results.append({"input": d.get("name", "?"), "class": kind,
                            "reason": why, "evidence": ev, "conflicting": conf})
    if a.out:
        os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
    counts = {}
    for r in results:
        counts[r["class"]] = counts.get(r["class"], 0) + 1
    print("=" * 68)
    print(f"oracle 分类 · {len(results)} 对")
    print("=" * 68)
    for k, v in sorted(counts.items(), key=lambda x: -x[1]):
        print(f"   {k:<22} {v}")
    bad = [r for r in results if r["class"] in ("real_regression", "unknown")]
    print("\n⚠️ `real_regression` 与 `unknown` 必须进 S2B / S3 人工处置。")
    print("   **不许改 oracle 让它通过** —— 外部契约变更应触发 S0 重采。")
    return 1 if (a.gate and bad) else 0


def main():
    ap = argparse.ArgumentParser(description="差分测试与 oracle 分类")
    ap.add_argument("--old", help="原版命令")
    ap.add_argument("--new", help="新版命令")
    ap.add_argument("--inputs", help="输入文件或目录")
    ap.add_argument("--pairs", help="已有成对输出 JSONL")
    ap.add_argument("--out", default="ledger/oracle.json")
    ap.add_argument("--timeout", type=int, default=10)
    ap.add_argument("--tol", type=float, default=1e-9, help="数值容差")
    ap.add_argument("--gate", action="store_true")
    ap.add_argument("--classes", action="store_true")
    a = ap.parse_args()

    if a.classes:
        return cmd_classes(a)
    if a.pairs:
        return cmd_pairs(a)
    if a.old and a.new and a.inputs:
        return cmd_run(a)
    print("❌ 需要 --old/--new/--inputs、--pairs 或 --classes")
    return 2


if __name__ == "__main__":
    sys.exit(main())
