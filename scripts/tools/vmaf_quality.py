#!/usr/bin/env python3
"""VMAF 封装 —— 感知视频质量。

**⚠️ 定位必须说清**：
> **VMAF 回答"看起来多像"，录屏回答"行为何时发生"—— 二者必须合并。**

VMAF **不能**定位：缺失的按钮、错误的焦点顺序、动画时序错误。
它只是一个质量分。

**完整流水线**：
  同分辨率/帧率/时间基/音频时钟/无鼠标输入录制
  → FFmpeg 按显示时间戳对齐
  → 逐帧生成工作帧
  → 裁剪与黑帧检测
  → 算 VMAF/SSIM
  → **低分帧送入像素与树诊断**

用法:
  vmaf_quality.py --old a.mp4 --new b.mp4 --out ledger/vmaf.json
  vmaf_quality.py --pipeline              # 打印完整流水线与环境指纹
  vmaf_quality.py --check-env

退出码: 0 正常 / 1 --gate 且低于阈值 / 2 工具不可用
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import require, run, emit, print_summary  # noqa: E402

# 视频基线必须记录的机器环境指纹（**不能只存 .mp4**）
ENV_FINGERPRINT = [
    "OS 与版本", "GPU / CPU", "显示缩放", "DPI", "字体版本", "显示器 ICC",
    "**电源模式**", "OBS 场景与编码器", "帧率", "时基", "时区",
    "鼠标可见性", "音频设备", "录制起止时间", "键盘宏版本",
]

PIPELINE = [
    ("1 录制", "同分辨率/帧率/时间基/音频时钟/**无鼠标输入**"),
    ("2 对齐", "FFmpeg 按显示时间戳对齐"),
    ("3 抽帧", "逐帧生成高分辨率工作帧"),
    ("4 清洗", "裁剪 + 黑帧检测"),
    ("5 评分", "VMAF / SSIM / MS-SSIM"),
    ("6 诊断", "**低分帧送入像素与树诊断**"),
]


def cmd_pipeline(a):
    print("=" * 70)
    print("完整流水线（VMAF 只是第 5 步）")
    print("=" * 70)
    for k, what in PIPELINE:
        print(f"   {k:<10} {what}")
    print("\n" + "=" * 70)
    print(f"视频基线必须记录的环境指纹（{len(ENV_FINGERPRINT)} 项）")
    print("=" * 70)
    for e in ENV_FINGERPRINT:
        print(f"   {e}")
    print("\n⚠️ Playwright 官方明确：主机 OS、版本、设置、硬件、**电源模式**、")
    print("   无头模式**均会改变渲染** —— **视频基线不能跨机器合并**。")
    print("\n❌ GIF 不作测量源（色深与帧损失污染指标）")
    print("❌ 不让 AI 直接看视频口述结论（应先转帧集 + 质量序列 + 候选簇）")
    return 0


def cmd_run(a):
    if not (os.path.exists(a.old) and os.path.exists(a.new)):
        print("❌ 视频不存在")
        return 2
    spec = require("vmaf")
    if spec is None:
        emit("vmaf", False, a.out,
             warnings=["VMAF 不可用 —— 感知质量证据未采集，必须进 unknown"])
        return 2

    cmd = ["ffmpeg", "-i", a.new, "-i", a.old, "-lavfi",
           "libvmaf=log_path=/dev/stdout:log_fmt=json", "-f", "null", "-"]
    rc, out, err = run(cmd, timeout=1800)
    combined = (out or "") + (err or "")

    score = None
    try:
        import json
        # VMAF JSON 里取 pooled VMAF
        idx = combined.find('"pooled_metrics"')
        if idx >= 0:
            seg = combined[idx:idx + 400]
            for k in ("vmaf", "mean"):
                p = seg.find(f'"{k}"')
                if p >= 0:
                    q = seg.find(":", p)
                    num = ""
                    for ch in seg[q + 1:]:
                        if ch.isdigit() or ch in ".-":
                            num += ch
                        elif num:
                            break
                    if num:
                        score = float(num)
                        break
    except Exception:
        pass

    warn = []
    if score is None:
        warn.append("未解析到 VMAF 分数 —— 确认 ffmpeg 是否 --enable-libvmaf")
    else:
        warn.append("**VMAF 只是质量分** —— 不能定位缺失按钮、错误焦点顺序、"
                    "动画时序错误；低分帧必须送入像素与树诊断")
        if a.min is not None and score < a.min:
            warn.append(f"VMAF {score:.2f} 低于阈值 {a.min}")

    rec = emit("vmaf", True, a.out,
               evidence=[f"old={a.old}", f"new={a.new}",
                         f"VMAF={score if score is not None else '未解析'}"],
               warnings=warn,
               extra={"vmaf": score, "raw": combined[:2000]})
    print_summary(rec)

    if a.gate and score is not None and a.min is not None and score < a.min:
        return 1
    return 0


def cmd_env(a):
    spec = require("vmaf")
    if spec is None:
        return 2
    print_summary(emit("vmaf", True, None, evidence=["VMAF 可用"],
                       warnings=["需 ffmpeg --enable-libvmaf"]))
    return 0


def main():
    ap = argparse.ArgumentParser(description="VMAF 感知视频质量")
    ap.add_argument("--old")
    ap.add_argument("--new")
    ap.add_argument("--out", default="ledger/vmaf.json")
    ap.add_argument("--min", type=float, help="阈值")
    ap.add_argument("--gate", action="store_true")
    ap.add_argument("--pipeline", action="store_true")
    ap.add_argument("--check-env", action="store_true")
    a = ap.parse_args()
    if a.pipeline:
        return cmd_pipeline(a)
    if a.check_env:
        return cmd_env(a)
    if not (a.old and a.new):
        print("❌ 需要 --old/--new，或 --pipeline / --check-env")
        return 2
    return cmd_run(a)


if __name__ == "__main__":
    sys.exit(main())
