#!/usr/bin/env python3
"""动效门禁（S7V 补充）—— 静态截图比不出来的：动画时序与区域运动。

**为什么需要**：目前视觉验收只比静态截图，
比不出"动画多久开始、何时稳定、哪些区域在动、有没有异常跳动"。

**⚠️ 诚实边界**：FFmpeg/OpenCV 只能识别「何时开始变化、何时稳定、哪些区域移动」，
**不能仅凭像素自动识别缓动曲线**。
除非原版有可读取的动画定义或足够高质量采样，
否则只报告：持续时间、延迟、稳定帧、运动区域、可见速度变化 ——
**不直接断言 `ease-in-out`**。

用法:
  motion_check.py --video old.mp4 --out motion-old.json       # 分析录屏
  motion_check.py --compare motion-old.json motion-new.json    # 新旧比对
  motion_check.py --init motion/                               # 生成动效契约骨架
  motion_check.py --check ffmpeg                               # 检查 ffmpeg 是否可用

状态转移字段（每个动画一张契约）:
  trigger / pre_state / post_state / capture_start_event / capture_end_event
  / expected_duration_range / stable_region / forbidden_region / frame_sample_rate

退出码: 0 正常 / 1 --gate 且超出预期范围 / 2 用法或文件错误
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys

MOTION_CONTRACT = {
    "animation_id": "dialog.open",
    "trigger": "click role=button name=\"设置\"",
    "pre_state": "dialog__closed",
    "post_state": "dialog__open_stable",
    "capture_start_event": "click 完成时刻",
    "capture_end_event": "客户区像素连续 N 帧不变",
    "expected_duration_range_ms": [0, 300],
    "stable_region": ["data-testid=dialog-body"],
    "forbidden_region": ["data-testid=titlebar"],
    "frame_sample_rate": 60,
    "determinism": "wait-stable",
    "note": "先验证「N—M ms 内从不可见到稳定 + 标题栏无异常跳动」，"
            "不猜测原版贝塞尔曲线",
}


def ffmpeg_available():
    return shutil.which("ffmpeg") is not None


def cmd_check_tool(a):
    ok = ffmpeg_available()
    print(("✅ " if ok else "❌ ") + ("ffmpeg 可用" if ok else "未找到 ffmpeg"))
    if not ok:
        print("   安装：apt install ffmpeg / brew install ffmpeg")
        print("   没有 ffmpeg 时本脚本只能做契约登记，**不做帧分析**"
              "（不假装成功）。")
    return 0 if ok else 2


def cmd_init(a):
    d = a.init if isinstance(a.init, str) else "motion"
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, "dialog.open.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(MOTION_CONTRACT, f, ensure_ascii=False, indent=2)
    print(f"已生成动效契约骨架: {p}")
    print("\n每个动画一张契约，字段含义:")
    for k, v in MOTION_CONTRACT.items():
        print(f"   {k:<28} {v!r}"[:110])
    print("\n⚠️ 先上线：持续时间 / 稳态 / 区域变化 / 禁止区域")
    print("   **不要**一开始就追求识别缓动曲线 —— 那需要已知控制点和约束。")
    return 0


def analyze_video(path, sample_rate):
    """抽帧 + 帧间差异（需要 ffmpeg）。"""
    if not ffmpeg_available():
        return None, "未安装 ffmpeg，无法做帧分析"
    tmpdir = os.path.join(os.path.dirname(os.path.abspath(path)) or ".", "_frames")
    os.makedirs(tmpdir, exist_ok=True)
    cmd = ["ffmpeg", "-y", "-i", path, "-vf", f"fps={sample_rate}",
           os.path.join(tmpdir, "f%05d.png")]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if r.returncode != 0:
        return None, f"ffmpeg 抽帧失败: {r.stderr.strip()[:200]}"
    frames = sorted(f for f in os.listdir(tmpdir) if f.endswith(".png"))
    if not frames:
        return None, "未抽出任何帧"

    # 帧间字节差作粗粒度运动指示（真正的像素差需用 OpenCV/PIL 逐帧比对）
    sizes = [os.path.getsize(os.path.join(tmpdir, f)) for f in frames]
    diffs = [abs(sizes[i + 1] - sizes[i]) for i in range(len(sizes) - 1)]
    total = sum(diffs) or 1

    first_change = next((i for i, d in enumerate(diffs) if d > 0), None)
    # 稳定帧：连续 3 帧差异都很小（相对总变化量 < 0.5%）
    thresh = total * 0.005
    stable = None
    for i in range(len(diffs) - 3):
        if all(diffs[i + j] <= thresh for j in range(3)):
            stable = i
            break

    ms_per_frame = 1000.0 / sample_rate
    return {
        "video": path,
        "frame_count": len(frames),
        "sample_rate": sample_rate,
        "first_change_frame": first_change,
        "first_change_ms": round(first_change * ms_per_frame) if first_change is not None else None,
        "stable_frame": stable,
        "stable_ms": round(stable * ms_per_frame) if stable is not None else None,
        "duration_ms": round((stable - first_change) * ms_per_frame)
                        if (stable is not None and first_change is not None) else None,
        "engine": "ffmpeg-frame-size-diff",
        "confidence": "low",
        "note": "字节差是粗粒度指示；精确运动区域需 OpenCV 逐帧像素比对",
    }, None


def cmd_analyze(a):
    if not os.path.exists(a.video):
        print(f"❌ 文件不存在: {a.video}")
        return 2
    res, err = analyze_video(a.video, a.rate)
    if err:
        print(f"❌ {err}")
        return 2
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=2)
    print("=" * 60)
    print(f"动效分析 → {a.out}")
    print("=" * 60)
    for k in ("frame_count", "first_change_ms", "stable_ms", "duration_ms"):
        print(f"   {k:<18} {res.get(k)}")
    print(f"\n⚠️ confidence=low：字节差只说明「何时开始变、何时停」，")
    print("   **不能据此断言缓动曲线**（ease-in-out / cubic-bezier）。")
    print("   曲线识别需要已知控制点和约束，或原版可读的动画定义。")
    return 0


def cmd_compare(a):
    def load(p):
        if not os.path.exists(p):
            print(f"❌ 文件不存在: {p}")
            return None
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    old, new = load(a.old), load(a.new)
    if old is None or new is None:
        return 2

    print("=" * 64)
    print("动效比对（原版 vs 新版）")
    print("=" * 64)
    bad = []
    missing = []      # 🔑 第六十一轮：**缺数据不得静默通过**
    for k in ("first_change_ms", "stable_ms", "duration_ms"):
        o, n = old.get(k), new.get(k)
        if o is None or n is None:
            # 🔑 原实现只"跳过"，最后仍打印"✅ 在容差内"并 **rc=0**
            #    🔴 这是"**缺数据即通过**"，与 B 类【空表即通过】同源
            missing.append(k)
            print(f"   {k:<18} 原 {o} / 新 {n}  ← 🔴 **数据缺失**")
            continue
        delta = abs(n - o)
        rel = delta / o if o else 0
        flag = "❌" if rel > 0.25 else "✅"
        print(f"   {k:<18} 原 {o}ms / 新 {n}ms  差 {delta}ms ({rel:.0%}) {flag}")
        if rel > 0.25:
            bad.append((k, o, n))

    # 🔑 第六十一轮：**缺数据不得静默通过**
    if missing:
        print(f"\n🔴 **{len(missing)} 个关键时序字段缺失** "
              f"({', '.join(missing)})")
        print("   🔴 **『数据不足』不能等同『在容差内』** ——"
              " 这与【空表即通过】是同一个病。")
        print("   🔑 请先跑 `--video` 抽帧产出含时序的 JSON，再比对。")
        return 1 if a.gate else 0
    if bad:
        print(f"\n❌ {len(bad)} 项超出 25% 容差:")
        for k, o, n in bad:
            print(f"   {k}: {o}ms → {n}ms")
        print("\n   处置：判定是**有意变更**还是**漂移**。")
        print("   ⚠️ 动画时长不一致 = 用户说「觉得变卡/变快」但说不出哪里变了。")
    else:
        print("\n✅ 动效时序在容差内")

    print("\n⚠️ 本比对只覆盖**时序**，画面区域运动需 OpenCV 逐帧比对（暂未内置）。")
    if a.gate and bad:
        return 1
    return 0


def main():
    ap = argparse.ArgumentParser(description="动效门禁（时序与区域运动）")
    ap.add_argument("--video", help="录屏文件")
    ap.add_argument("--rate", type=int, default=60, help="抽帧率")
    ap.add_argument("--out", default="motion.json")
    ap.add_argument("--compare", action="store_true")
    ap.add_argument("--old")
    ap.add_argument("--new")
    ap.add_argument("--init", nargs="?", const=True)
    ap.add_argument("--check", help="检查工具（ffmpeg）")
    ap.add_argument("--gate", action="store_true")
    a = ap.parse_args()

    if a.check:
        return cmd_check_tool(a)
    if a.init is not None:
        if a.init is True:
            a.init = "motion"
        return cmd_init(a)
    if a.compare:
        if not (a.old and a.new):
            print("❌ --compare 需要 --old 与 --new")
            return 2
        return cmd_compare(a)
    if a.video:
        return cmd_analyze(a)
    print("❌ 需要 --video / --compare / --init / --check 之一")
    return 2


if __name__ == "__main__":
    sys.exit(main())
