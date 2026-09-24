#!/usr/bin/env python3
"""视觉状态清单校验 + 骨架生成（S7V 门禁的清单侧）。

本脚本**不做截图**（截图由 Playwright 执行器负责），它保证的是：
每个视觉状态的"契约"字段完整、稳定化项已锁、遮罩有理由、阈值有理由、审批有签字。

检查项:
  1. 必填字段齐全（state_id / preconditions / steps / selectors.stable / comparison / review）
  2. 稳定化必锁项（clock / font / device_scale_factor / reduced_motion / seed / locale）
  3. 遮罩必须写 reason（不许无理由遮罩）
  4. threshold 必须写 threshold_reason（说不出理由就不给阈值）
  5. 等待必须是语义等待（禁止 waitForTimeout 这类固定等待）
  6. .approved 必须有 approved_by 与 decision_type（AI 不得代签）
  7. 禁止 bulk approve 痕迹（同一 approved_at 批量、或 approved_by 含 bot/auto）

用法:
  visual_check.py --states visual/states
  visual_check.py --states visual/states --approved visual/approved --gate
  visual_check.py --init --states visual/states --feature "#142" --name settings-dialog.default

退出码: 0 通过 / 1 有违规 / 2 用法或文件错误
"""
import argparse
import os
import re
import sys

try:
    import yaml
except ImportError:
    yaml = None

REQUIRED_TOP = ["state_id", "preconditions", "steps", "selectors", "comparison", "review"]
REQUIRED_LOCK = {
    "clock": "固定时钟（时间戳/相对时间类必锁）",
    "font": "字体名@版本（抗锯齿不稳定源）",
    "device_scale_factor": "设备像素比（高 DPI 未处理会导致截图错位）",
    "reduced_motion": "缩减动画（或改为等稳定终态）",
    "seed": "随机种子",
    "locale": "语言",
}
FIXED_WAIT = re.compile(r"waitForTimeout|sleep\(|wait_for_timeout|setTimeout\s*\(")


def load_yaml(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        text = f.read()
    if yaml is None:
        # 无 pyyaml 时做轻量键值检查（够抓缺失，不做结构解析）
        return {"__text__": text}, text
    return yaml.safe_load(text), text


def check_state(path):
    errs, warns = [], []
    name = os.path.basename(path)
    data, text = load_yaml(path)

    if yaml is None:
        for k in REQUIRED_TOP:
            if not re.search(rf"^{k}\s*:", text, re.M):
                errs.append(f"缺少顶层字段 `{k}`")
        for k, why in REQUIRED_LOCK.items():
            if not re.search(rf"^\s*{k}\s*:", text, re.M):
                errs.append(f"preconditions 未锁 `{k}` —— {why}")
        if FIXED_WAIT.search(text):
            errs.append("检测到固定等待（waitForTimeout/sleep）→ 改用语义断言等待")
        if re.search(r"^\s*-?\s*selector:", text, re.M) and not re.search(r"reason:", text):
            errs.append("遮罩项缺少 `reason` —— 不许无理由遮罩")
        return errs, warns

    if not isinstance(data, dict):
        return [f"{name}: 不是合法映射"], []

    for k in REQUIRED_TOP:
        if k not in data:
            errs.append(f"缺少顶层字段 `{k}`")

    pre = data.get("preconditions", {}) or {}
    for k, why in REQUIRED_LOCK.items():
        if k not in pre:
            errs.append(f"preconditions 未锁 `{k}` —— {why}")

    steps = data.get("steps", []) or []
    for i, s in enumerate(steps):
        if isinstance(s, str):
            if FIXED_WAIT.search(s):
                errs.append(f"steps[{i}] 用了固定等待 → 改用语义断言（如 aria-expanded=true）")
        elif isinstance(s, dict):
            blob = " ".join(str(v) for v in s.values())
            if FIXED_WAIT.search(blob):
                errs.append(f"steps[{i}] 用了固定等待 → 改用语义断言")
            if "wait" in s and re.match(r"^\d+$", str(s["wait"]).strip()):
                errs.append(f"steps[{i}] 的 wait 是纯数字（毫秒）→ 改成语义条件")

    sel = data.get("selectors", {}) or {}
    if not sel.get("stable"):
        errs.append("selectors.stable 为空 —— 必须指定比对范围")
    for m in sel.get("mask", []) or []:
        if isinstance(m, dict):
            if not m.get("reason"):
                errs.append(f"遮罩 `{m.get('selector', '?')}` 缺少 reason —— 不许无理由遮罩")
            elif len(str(m["reason"])) < 10:
                warns.append(f"遮罩 `{m.get('selector', '?')}` 的 reason 过短，说清'为何不属于本契约'")

    cmp_ = data.get("comparison", {}) or {}
    if "engine" not in cmp_:
        errs.append("comparison.engine 未指定 —— 建议 [pixel, layout] 双引擎交叉验证")
    elif isinstance(cmp_.get("engine"), list) and len(cmp_["engine"]) < 2:
        warns.append("comparison.engine 只有单引擎 —— 建议像素+结构双引擎")
    if "threshold" not in cmp_:
        errs.append("comparison.threshold 未指定")
    else:
        try:
            t = float(cmp_["threshold"])
        except (TypeError, ValueError):
            errs.append("comparison.threshold 不是数字")
            t = None
        if t is not None and not cmp_.get("threshold_reason"):
            errs.append(f"threshold={t} 但缺 threshold_reason —— 说不出理由就不给阈值")

    rev = data.get("review", {}) or {}
    if not rev.get("baseline_ref"):
        warns.append("review.baseline_ref 为空（首次建立时可接受）")
    if not rev.get("approvers"):
        errs.append("review.approvers 为空 —— 必须指定审查人")
    return errs, warns


def check_approved(approved_dir):
    """已批准基线的签字与批量痕迹检查。"""
    errs, warns = [], []
    if not os.path.isdir(approved_dir):
        return [f"目录不存在: {approved_dir}"], []
    stamps = {}
    for fn in sorted(os.listdir(approved_dir)):
        if not fn.endswith((".yaml", ".yml", ".md", ".json")):
            continue
        with open(os.path.join(approved_dir, fn), encoding="utf-8", errors="replace") as f:
            t = f.read()
        if "approved_by" not in t:
            errs.append(f"{fn}: 无 approved_by（AI 不得代签）")
        elif re.search(
            r"approved_by\s*:\s*(?:null|~|"
            r"(?:\S*(?:bot|auto|agent|ai|gpt|claude|copilot|assistant)\S*))\s*$",
            t, re.M | re.I):
            errs.append(f"{fn}: approved_by 疑似 AI/bot/null —— 批准决策必须由人签字")
        if "decision_type" not in t:
            errs.append(f"{fn}: 无 decision_type（须为 原端有意变更/目标端等价/目标端择优且有证据）")
        m = re.search(r"approved_at\s*:\s*(\S+)", t)
        if m:
            stamps.setdefault(m.group(1), []).append(fn)
    for ts, files in stamps.items():
        if len(files) > 3:
            warns.append(f"{len(files)} 个基线共用同一 approved_at={ts} —— 怀疑 bulk approve")
    return errs, warns


def cmd_init(a):
    os.makedirs(a.states, exist_ok=True)
    path = os.path.join(a.states, f"{a.name}.yaml")
    tpl = f"""state_id: {a.name}
feature_ref: "{a.feature}"
capability: CAP-TODO-001

preconditions:
  fixture: user.admin
  db_seed: TODO.yaml
  clock: 2026-09-17T09:00:00+08:00
  seed: 42
  font: Inter@2.001
  locale: zh-CN
  timezone: Asia/Shanghai
  viewport: {{ width: 1440, height: 900 }}
  device_scale_factor: 1
  zoom: 1
  theme: light
  reduced_motion: reduce
  animations: disabled

steps:
  - action: click role=button name="TODO"
  - wait: aria-expanded=true          # ✅ 语义等待；禁止 waitForTimeout

selectors:
  stable: [data-testid=TODO]
  mask:
    - selector: data-testid=TODO
      reason: 说明为什么这个区域不属于本状态的视觉契约（核心体验不许遮）

comparison:
  engine: [pixel, layout]
  threshold: 0.000
  threshold_reason: TODO（精确对齐项必须零差异；说不出理由就不给阈值）
  include_aa: false

review:
  approvers: [design, domain_owner]
  baseline_ref: baselines/{a.name}.png
  decision_ref: decisions/{a.name}.md
  approved_by: null
  approved_at: null
  decision_type: null                 # 原端有意变更 | 目标端等价 | 目标端择优且有证据
"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(tpl)
    print(f"已生成骨架: {path}")
    print("下一步：填 TODO，然后跑 visual_check.py --gate 校验")


def main():
    ap = argparse.ArgumentParser(description="视觉状态契约校验")
    ap.add_argument("--states", default="visual/states")
    ap.add_argument("--approved", default="visual/approved")
    ap.add_argument("--gate", action="store_true", help="有违规退出码 1")
    ap.add_argument("--strict", action="store_true", help="警告也算阻塞")
    ap.add_argument("--init", action="store_true")
    ap.add_argument("--name", default="new-state")
    ap.add_argument("--feature", default="#TODO")
    a = ap.parse_args()

    if a.init:
        cmd_init(a)
        return 0

    if not os.path.isdir(a.states):
        print(f"❌ 状态目录不存在: {a.states}（可用 --init 生成骨架）")
        return 2

    files = sorted(
        os.path.join(a.states, f) for f in os.listdir(a.states)
        if f.endswith((".yaml", ".yml")))
    if not files:
        print(f"❌ {a.states} 下无状态文件")
        return 2

    all_errs, all_warns = [], []
    for p in files:
        e, w = check_state(p)
        all_errs += [f"{os.path.basename(p)}: {x}" for x in e]
        all_warns += [f"{os.path.basename(p)}: {x}" for x in w]

    if os.path.isdir(a.approved):
        e, w = check_approved(a.approved)
        all_errs += e
        all_warns += w

    print("=" * 60)
    print(f"视觉状态 {len(files)} 个" + (f" · 已批准基线目录 {a.approved}" if os.path.isdir(a.approved) else ""))
    print("=" * 60)
    if yaml is None:
        print("⚠️  未安装 pyyaml —— 降级为轻量文本检查（仍可抓缺失项，但不做结构解析）")

    for w in all_warns:
        print(f"⚠️  {w}")
    if all_errs:
        print(f"\n❌ [S7V] {len(all_errs)} 项违规:")
        for e in all_errs:
            print("   ", e)
        return 1
    print("\n✅ [S7V] 视觉状态契约字段完整、稳定化已锁、审批可追溯")
    if a.strict and all_warns:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
