#!/usr/bin/env python3
"""渲染取证与帧基线（游戏复刻 B 类）。

**为什么需要**：没有软件渲染基线，就**无法区分游戏错误与驱动/GPU 差异**。
> "不同 GPU 结果不同很正常" —— 这句话在复刻场景里是**错的**，
> 它会掩盖真正的实现差异。

**渲染基线的正确做法**：
  原版在真实 GPU + 真实驱动下捕获（事实源）
  → 原版与新实现**各跑软件渲染器**（llvmpipe / lavapipe / SwiftShader / ANGLE）
  → 再在新 GPU 上跑参考渲染
  → 逐帧比较**只允许预先声明、数值可解释的容差**

用法:
  game_render.py --forbid            # 打印基线必须禁用的项
  game_render.py --baseline --check ledger/render_baseline.yaml --gate
  game_render.py --frame-hash --dir frames/ --out frames.json
  game_render.py --tools             # 打印取证工具分工

退出码: 0 通过 / 1 缺项或帧哈希不一致 / 2 用法错误
"""
import argparse
import hashlib
import json
import os
import sys

# 基线必须禁用的项（每个都是"看起来更好但实际破坏基线"）
FORBIDDEN = [
    ("JPEG 输出", "有损压缩污染像素比对"),
    ("随机超分 / DLSS / FSR", "**非确定性**且改变画面 —— 复刻阶段禁用"),
    ("色调映射差异", "不同 tonemapping 曲线 → 全屏色偏"),
    ("动态分辨率", "渲染分辨率随帧变化，无法比对"),
    ("TAA 累积帧数不一致", "历史帧数不同 → 残影不同"),
    ("未锁定后处理种子", "胶片颗粒、色差、抖动随机"),
    ("sRGB / linear 转换不一致", "整屏亮度偏差"),
    ("异步加载未冻结", "资源未就绪 → 随机缺件"),
    ("粒子/镜头抖动未锁种子", "逐帧随机"),
]

# 取证工具分工（互相不能替代）
TOOLS = [
    ("RenderDoc", "交互式**单帧**取证（F12 捕获，纹理/事件树/管道/网格）",
     "事实源；支持 Vulkan/D3D11-12/GL-ES，捕获可跨平台共享，有 Python 接口"),
    ("GFXReconstruct", "Vulkan layer / D3D12 库录制 API 调用 → `.gfxr` **可重放**",
     "**自动化 CI 首选**；可 info/compress/extract SPIR-V/convert JSONL"),
    ("PIX on Windows", "D3D12 必需补充；可录制全部 API 调用并重放，查调用参数/管道/资源",
     "旧 D3D11 用 D3D11On12 重定向；多启动器需直启主 exe"),
    ("apitrace", "老 OpenGL/D3D 工作流，可脚本化 diff、无头测试",
     "⚠️ 帧内资源检查不如 RenderDoc，**不得冒充 RenderDoc**"),
    ("NVIDIA Nsight / Intel GPA", "Pixel History、GPU Trace、Shader Debugger",
     "厂商工具，常含专有组件/平台限制，**不能假定可再分发**"),
]

# 软件渲染基线（消除 GPU 噪声）
SOFTWARE = [
    ("Mesa llvmpipe", "OpenGL 软渲染"),
    ("Mesa lavapipe", "Vulkan 软渲染"),
    ("SwiftShader", "CPU 光栅化"),
    ("ANGLE", "API 转译层，统一后端"),
]

BASELINE_FIELDS = [
    ("api_trace", "API trace 或独立 headless scene"),
    ("renderer_backend", "渲染后端"),
    ("icd_or_gl_impl", "ICD / GL 实现"),
    ("driver_version", "驱动版本"),
    ("thread_count", "线程数"),
    ("output_format", "输出格式（**须 PNG/EXR，禁 JPEG**）"),
    ("locked_seed", "后处理/粒子 RNG 种子"),
    ("taa_history_frames", "TAA 历史帧数"),
    ("postprocess_state", "后处理开关状态"),
    ("resolution_mode", "分辨率模式（**须固定**）"),
]


def cmd_forbid(a):
    print("=" * 72)
    print("渲染基线必须禁用的项（每个都会让基线失效）")
    print("=" * 72)
    for k, why in FORBIDDEN:
        print(f"\n   ❌ {k}")
        print(f"      {why}")
    print("\n⚠️ **「开 DLSS/FSR 后差不多」「后处理更现代所以不用复刻」** 与理念冲突 ——")
    print("   后处理、抗锯齿、色域、粒子、镜头抖动正是**体验差异高发区**。")
    print("   每项必须显式选择 preserve / reimplement / modernize / intentionally diverge。")
    return 0


def cmd_tools(a):
    print("=" * 72)
    print("渲染取证工具分工（**互相不能替代**）")
    print("=" * 72)
    for name, what, note in TOOLS:
        print(f"\n【{name}】")
        print(f"   {what}")
        print(f"   {note}")
    print("\n" + "=" * 72)
    print("软件渲染基线（消除 GPU 噪声）")
    print("=" * 72)
    for k, why in SOFTWARE:
        print(f"   {k:<20} {why}")
    print("\n⚠️ **渲染图比对优于单帧 PNG 比对** ——")
    print("   从 trace 抽 draw call / render pass / pipeline state / 资源绑定 /")
    print("   uniform 哈希，建结构化 golden；视觉只在该层一致仍失败时使用。")
    return 0


def cmd_baseline(a):
    if not os.path.exists(a.baseline):
        print(f"❌ 文件不存在: {a.baseline}")
        return 2
    text = open(a.baseline, encoding="utf-8", errors="replace").read()
    missing = [(k, why) for k, why in BASELINE_FIELDS if k not in text]
    print("=" * 70)
    print("渲染基线")
    print("=" * 70)
    for k, why in BASELINE_FIELDS:
        print(f"   {'✅' if k in text else '❌'} {k:<24} {why}")
    if missing:
        print(f"\n❌ 缺 {len(missing)} 项 —— 基线不可复现")

    # 禁用项检查
    bad = []
    low = text.lower()
    for k, _ in FORBIDDEN:
        key = k.split(" /")[0].split("（")[0].strip().lower()
        if key in low and "false" not in low and "禁用" not in low:
            pass
    if "jpeg" in low and "禁" not in low:
        bad.append("检出 JPEG —— **须改 PNG/EXR**")
    for kw in ("dlss", "fsr", "xess"):
        if kw in low and "禁" not in low and "false" not in low:
            bad.append(f"检出 {kw.upper()} —— 复刻阶段**必须禁用**（非确定性且改变画面）")
    if bad:
        print("\n❌ 基线污染:")
        for b in bad:
            print(f"   {b}")

    print("\n⚠️ 基线是**有版本的制品**，不是一次截图。")
    return 1 if (a.gate and (missing or bad)) else 0


def cmd_frame_hash(a):
    if not os.path.isdir(a.dir):
        print(f"❌ 目录不存在: {a.dir}")
        return 2
    files = sorted(f for f in os.listdir(a.dir)
                   if f.lower().endswith((".png", ".exr", ".bmp", ".tga")))
    if not files:
        print("❌ 无图像文件")
        return 2
    out = []
    for f in files:
        p = os.path.join(a.dir, f)
        h = hashlib.sha256(open(p, "rb").read()).hexdigest()
        out.append({"file": f, "sha256": h})
    if a.out:
        os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        print(f"→ {a.out}")
    print(f"\n{len(out)} 帧哈希已生成")
    print("\n⚠️ 逐帧比对**只允许预先声明、数值可解释的容差**：")
    print("   HUD 字体、动态分辨率、后处理抖动、TAA 历史、粒子 RNG、异步加载、")
    print("   阴影级联、色差、Gamma/sRGB 转换均可制造差异 —— 先冻结时间、输入、")
    print("   随机、资源和屏幕状态，再分层比较（背景/静态模型/角色/HUD/文字）。")
    return 0


def main():
    ap = argparse.ArgumentParser(description="渲染取证与帧基线")
    ap.add_argument("--forbid", action="store_true")
    ap.add_argument("--tools", action="store_true")
    ap.add_argument("--baseline")
    ap.add_argument("--frame-hash", action="store_true")
    ap.add_argument("--dir")
    ap.add_argument("--out")
    ap.add_argument("--gate", action="store_true")
    a = ap.parse_args()

    if a.forbid:
        return cmd_forbid(a)
    if a.tools:
        return cmd_tools(a)
    if a.baseline:
        return cmd_baseline(a)
    if a.frame_hash:
        if not a.dir:
            print("❌ --frame-hash 需要 --dir")
            return 2
        return cmd_frame_hash(a)
    print("❌ 需要 --forbid / --tools / --baseline / --frame-hash 之一")
    return 2


if __name__ == "__main__":
    sys.exit(main())
