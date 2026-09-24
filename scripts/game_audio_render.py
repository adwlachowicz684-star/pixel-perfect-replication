#!/usr/bin/env python3
"""音频信号链 / 渲染管线 / 可玩性测试（深化第四轮 B / D / E / F 类）。

**🔑 B 类**：音频系统应按 **内容—逻辑—混音—空间—输出** 五层分别取证。
**🔑 E 类**：渲染差异大多发生在**资源与设置层**，不是代码逻辑。
**🔑 D 类**：可玩性测试最低目标是「**关键路径仍可达、仍可在有界时间内完成**」。

用法:
  game_audio_render.py --audio        # 音频五层
  game_audio_render.py --music        # 动态音乐（**何时允许切**）
  game_audio_render.py --spatial      # 空间音频（**戴上耳机才发现的错**）
  game_audio_render.py --mix          # 混音与响度（**是功能，不是审美**）
  game_audio_render.py --voip         # 语音聊天必须与游戏音频分开
  game_audio_render.py --render       # 渲染取证四联
  game_audio_render.py --lighting     # 光照烘焙四联表
  game_audio_render.py --visibility   # LOD 与剔除链
  game_audio_render.py --postfx       # 后处理栈顺序
  game_audio_render.py --variants     # 着色器变体与预热
  game_audio_render.py --quality      # 画质档位（**是功能表面**）
  game_audio_render.py --playability  # 可玩性与四类卡死
  game_audio_render.py --pcg          # 程序化生成可复现性
  game_audio_render.py --init ledger/audio_render.csv
  game_audio_render.py --check ledger/audio_render.csv --gate

退出码: 0 通过 / 1 缺项 / 2 用法错误
"""
import argparse
import csv
import os
import sys

# 音频五层
AUDIO_LAYERS = [
    ("内容层", "stem 角色、循环长度、BPM、拍号、起拍、尾拍、淡入淡出、本征和速度倍率"),
    ("逻辑层", "music state、transition、quantization、stinger、music event、switch/parameter"),
    ("混音层", "bus 树、sends/returns、**snapshot 优先级**、ducking 曲线、侧链、限幅、响度"),
    ("空间层", "emitter 位置/方向、listener 高度朝向、距离模型、最小/最大距离、曲线、"
               "HRTF、occlusion/obstruction、portal、room/reverb"),
    ("输出层", "采样率、声道、声部预算、流式缓冲、压缩格式、平台 mix、真峰值"),
]

# 动态音乐
MUSIC_FIELDS = [
    ("状态层", "exploration/combat/stealth 等 state、进入/退出/守卫条件、超时"),
    ("分层层", "base/drums/bass/texture/pads 等 stem、每层 play/stop/fade、相对增益、负载预算"),
    ("水平层", "可拼接段、前奏、循环体、过门、尾段、下一小节/拍同步点"),
]

MUSIC_TRANSITIONS = [
    "instant", "scheduled-instant", "crossfade",
    "**quantized-to-beat**", "**quantized-to-bar**", "quantized-to-section-end",
    "tail-and-release", "stinger",
]

MUSIC_CLOCK = [
    "🔑 节拍同步**不是「播放时对齐 BPM」** —— 必须同时记录：",
    "   master clock 来源（game time / **audio sample position** / video time / network time）",
    "   音乐时间映射 · 首次拍子的全局时间 · loop 边界 sample · **sub-sample 相位**",
    "   节奏变化 · 暂停累积 · seek 重对齐",
    "⚠️ 若用 DSP/audio clock，迁移后**不得被可变逻辑 deltaTime 漂移**",
    "⚠️ 若原版跳跃在拍子前 8ms，而复刻允许 ±50ms 量化 —— "
    "视觉节奏虽对，**身体感觉已不同**",
]

# 空间音频
SPATIAL_FIELDS = [
    "HRTF on/off/auto", "**HRTF dataset**", "立体声 pan law", "单声道提升",
    "距离模型 / 最小 / 最大 / rolloff", "空气吸收", "directivity",
    "dry/wet 比例", "发送矩阵", "room 体积", "材质", "reverb time",
    "HF ratio", "portal open ratio", "listener 高度", "**头部朝向**",
]

SPATIAL_RULE = [
    "🔴 **空间音频最容易因默认 HRTF 而「看起来迁移成功、戴上耳机即错」**",
    "🔑 **Occlusion 与 Obstruction 必须区分**：",
    "   · occlusion = **全频遮断**",
    "   · obstruction = **经缝隙衍射的高频衰减**",
    "   → **不能合并成一个「音量」**",
]

# 混音
MIX_FIELDS = [
    "每级 bus 增益", "静音 / solo", "声像", "delay", "phase", "EQ",
    "compressor", "limiter", "**sidechain source**",
    "**duck amount / curve / lookahead / release**",
    "voice priority", "**virtual voice 规则**",
]

DUCKING_TRIGGERS = [
    "语音存在", "语音响度", "角色距离", "**subtitle 状态**", "**菜单焦点**",
]

LOUDNESS = [
    "🔑 平台交付需建立**响度基线**：`-23 / -16 / -14 LUFS` 之类目标"
    "**只适用相应平台规范，不能自行选择**",
    "记录：True Peak · **LRA** · dialog gating · master ceiling · codec · "
    "downmix 矩阵 · **聋哑/单耳可达性 mix**",
    "🔑 **混音与响度是功能表面，不是后期审美**",
]

VOIP_FIELDS = [
    ("采集", "device latency、buffer size、resampling、**AEC 参考**、双讲处理、NS、AGC、VAD"),
    ("编码与网络", "codec、bitrate、ptime/packet size、FEC、RED、PLC、**jitter buffer min/opt/max**、NACK/RTX"),
    ("接收", "**sidetone**、ducker、spatialization、push-to-talk"),
]

VOIP_RULE = [
    "🔑 **语音聊天与游戏音频必须分开**",
    "⚠️ 若原版使用自研 DSP，**不应为了「现代化」替换算法**",
    "❌ 冲突做法：**把语音接入普通 SFX bus、用音乐侧链压人声** —— "
    "会让对话清晰度与多人协作能力悄然退化",
]

# 渲染取证四联
RENDER_QUAD = [
    "**scene assets**", "**render graph**", "**quality settings**", "**platform build**",
]

RENDER_CAPTURE_FIELDS = [
    "GPU", "驱动", "API", "resolution", "render scale", "present mode",
    "MSAA/swapchain", "texture formats", "**capture hash**", "frame index", "repro steps",
]

# 光照烘焙四联表
LIGHTING = [
    ("资产", "静态/动态标记、contribute GI/receive、**lightmap UV1/UV2/UV3**、"
             "auto-unwrap settings、chart/margin/seam、**texel density**、"
             "lightmap size、compression、padding、directional mode"),
    ("UV", "**UV2 需避免重叠与 bleeding**；**UV3 用于实时 GI**"),
    ("探针", "光照探针采样位置、tetrahedralization、probe volume bounds/resolution、"
             "SH bands、sky visibility、indirect lighting；"
             "反射探针 cubemap resolution、HDR、culling mask、**box projection**、"
             "interpolation、refresh mode"),
    ("求解器", "direct/indirect intensity、bounce count、light leakage、sample count、"
               "denoising、environment lighting"),
]

LIGHTING_NOTE = [
    "⚠️ 静态几何体可以**既不贡献也不接收 lightmap**",
    "⚠️ **体积较大的物体仅靠单个 light probe 可能照明不正确**",
]

VISIBILITY = [
    "**LOD 生成参数**", "**遮挡剔除（OC / PVS）**", "视锥剔除",
    "小物件剔除", "GPU 驱动剔除", "剔除链顺序",
]

POSTFX = [
    "**栈顺序**", "色彩分级 LUT", "体积光", "SSR / SSAO",
    "TAA / FXAA / SMAA", "锐化", "每类参数",
]

VARIANTS = [
    "**变体爆炸**", "**预热策略**", "首次卡顿", "变体收集方式", "编译缓存",
]

QUALITY_TIERS = [
    "🔑 **画质档位是功能表面的一部分** —— 要记录每个档具体**开关了什么**",
    "字段：档位名 · 分辨率/渲染缩放 · 阴影质量与距离 · LOD bias · "
    "后处理开关 · 纹理流式预算 · 粒子预算 · 声部预算 · 特效距离 · 帧率上限",
]

# 可玩性
PLAYABILITY_BASELINE = [
    "起始状态哈希", "**输入时间轴**", "camera trace", "game state",
    "achievements/inventory/flags", "**per-room reachability**",
    "死亡/重生计数", "loading screen", "关键事件时间戳", "录像校验和",
]

STUCK_TYPES = [
    ("几何卡死", "player AABB 与碰撞、velocity/**penetration depth**、"
                 "连续 N 帧 stuck、非预期 collision layer、**掉出 world bounds**、"
                 "water/teleport 体积状态"),
    ("逻辑卡死", "quest flag/objective graph、事件触发计数、**超时无进展**、"
                 "required item 缺失、dialog 分支未推进、ability gate 未解锁"),
    ("软锁", "状态机不变式、**相互等待**、AI alert 但无巡逻路径、"
             "door 半开、load 完成但 gameplay 未 resume"),
    ("回归", "最短通关时间、关键节点到达顺序、收集品数、死亡数、"
             "输入序列长度、内存增长、帧预算"),
]

WATCHDOG = [
    "🔑 watchdog 必须同时知道「**正常等待**」与「卡死等待」 —— "
    "过场、loading、模拟宇宙生成本就需要较长超时，"
    "**不能简单按固定 wall-clock 判定**",
]

REACHABILITY = [
    ("几何可达", "navmesh、teleport、jump/glide 能力、移动 modifier、"
                 "velocity cap、**sequential abilities** 枚举可达区域"),
    ("状态可解锁", "按 quest/flag/door/inventory/ability 建立**可达图**"),
    ("**资源可持续**", "模拟 worst-case HP/ammo/time，"
                      "验证**不依赖偶然掉落**也能过关"),
]

PLAYABILITY_RULE = [
    "❌ **「Bot 通关即体验一致」是错误结论** —— RL 可能在某条捷径上成功，"
    "却绕开人类必经的对话、相机、动画和音频状态机",
    "🔑 门禁分层：**A 类**原版可到达/可完成不变式（失败不得被模型置信度掩盖）· "
    "**B 类**帧预算/内存/加载时间 · **C 类**观感回归",
]

PLAYABILITY_TOOLS = [
    ("Unity Test Framework", "Unity 官方包", "Edit/Play mode、NUnit、**协程/帧/yield 测试**"),
    ("GodotE2E", "godot-e2e/godot-e2e，Apache-2.0",
     "**外进程 TCP**、输入、属性、帧同步、截图；真实 Godot 进程 E2E"),
    ("GameTest", "luppichristian/GameTest，MIT",
     "C/C++ **确定性 record/replay + inline assertions**；不绑定引擎"),
    ("Unity ML-Agents", "Unity-Technologies/ml-agents",
     "⚠️ **单环境、单 agent、首个视觉观测优先** —— 适合探索/行为克隆，"
     "不适合承载完整状态机验证"),
    ("Gymnasium", "Farama-Foundation/Gymnasium", "统一 observation/action/reset/step 接口"),
]

PCG = [
    "🔑 **FastNoise2 默认 `FASTNOISE2_STRICT_FP=OFF` 不保证跨 SIMD 复现** —— "
    "若要跨引擎复现同一世界，必须显式开启并锁定 SIMD 等级",
    "记录：种子 · 噪声函数与参数 · **迭代顺序** · 浮点精度 · 随机源 · 生成顺序",
    "⚠️ 跨引擎复现同一程序化世界极难 —— 浮点、迭代顺序、随机数任一变化都会漂移",
]

FIELDS = [
    ("item_id", "项编号"),
    ("domain", "域（audio / music / spatial / mix / voip / lighting / visibility / postfx / variants / quality / playability / pcg）"),
    ("legacy_value", "**原版值**"),
    ("new_value", "新引擎值"),
    ("match", "**是否一致**"),
    ("evidence", "证据"),
]


def _hdr(t, w=80):
    print("=" * w)
    print(t)
    print("=" * w)


def cmd_audio(a):
    _hdr("音频五层（**事件迁移只是表层，信号链才是观感**）")
    for k, why in AUDIO_LAYERS:
        print(f"\n   【{k}】{why}")
    print("\n⚠️ Wwise/FMOD 工程**不是二进制黑盒**，但"
          "**不存在通用反编译器** ——")
    print("   应从原始工程数据库、work unit XML、event 描述、soundbank metadata、")
    print("   banks 清单和运行时日志导出**有向图**（WAAPI 可连 Wwise Authoring）。")
    print("   ⚠️ **不能假装通用格式可以无损互转**")
    return 0


def cmd_music(a):
    _hdr("动态音乐（🔑 **何时允许切，比切到哪更重要**）")
    for k, why in MUSIC_FIELDS:
        print(f"\n   【{k}】{why}")
    print("\n过渡类型:")
    for t in MUSIC_TRANSITIONS:
        print(f"   · {t}")
    print("")
    for m in MUSIC_CLOCK:
        print(f"   {m}")
    return 0


def cmd_spatial(a):
    _hdr("空间音频（🔴 **戴上耳机才发现的错**）")
    for f in SPATIAL_FIELDS:
        print(f"   · {f}")
    print("\n规则:")
    for r in SPATIAL_RULE:
        print(f"   {r}")
    return 0


def cmd_mix(a):
    _hdr("混音与响度（🔑 **是功能表面，不是后期审美**）")
    for f in MIX_FIELDS:
        print(f"   · {f}")
    print("\n音乐 ducking 触发条件:")
    for t in DUCKING_TRIGGERS:
        print(f"   · {t}")
    print("")
    for l in LOUDNESS:
        print(f"   {l}")
    return 0


def cmd_voip(a):
    _hdr("语音聊天（**必须与游戏音频分开**）")
    for k, why in VOIP_FIELDS:
        print(f"\n   【{k}】{why}")
    print("\n规则:")
    for r in VOIP_RULE:
        print(f"   {r}")
    return 0


def cmd_render(a):
    _hdr("渲染取证（🔑 **差异大多在资源与设置层，不是代码逻辑**）")
    print("四联: " + " · ".join(RENDER_QUAD))
    print("\n每次 renderdoc / gfxreconstruct 取证保留:")
    for f in RENDER_CAPTURE_FIELDS:
        print(f"   · {f}")
    return 0


def cmd_lighting(a):
    _hdr("光照烘焙四联表")
    for k, why in LIGHTING:
        print(f"\n   【{k}】{why}")
    print("\n注意:")
    for n in LIGHTING_NOTE:
        print(f"   {n}")
    return 0


def cmd_visibility(a):
    _hdr("LOD 与剔除链")
    for v in VISIBILITY:
        print(f"   · {v}")
    return 0


def cmd_postfx(a):
    _hdr("后处理栈")
    for p in POSTFX:
        print(f"   · {p}")
    print("\n🔑 **栈顺序必须记录** —— 顺序变了最终画面就变了")
    return 0


def cmd_variants(a):
    _hdr("着色器变体")
    for v in VARIANTS:
        print(f"   · {v}")
    print("\n⚠️ 变体未预热 → **首次卡顿**，这是真实的体验回归")
    return 0


def cmd_quality(a):
    _hdr("画质档位")
    for q in QUALITY_TIERS:
        print(f"   {q}")
    return 0


def cmd_playability(a):
    _hdr("可玩性测试（**从「能跑」到「能证明不软锁」**）")
    print("基线必录:")
    for f in PLAYABILITY_BASELINE:
        print(f"   · {f}")
    print("\n四类卡死（**必须相互独立**）:")
    for k, why in STUCK_TYPES:
        print(f"\n   【{k}】{why}")
    print("")
    for w in WATCHDOG:
        print(f"   {w}")
    print("\n可达性三条:")
    for k, why in REACHABILITY:
        print(f"   【{k}】{why}")
    print("\n规则:")
    for r in PLAYABILITY_RULE:
        print(f"   {r}")
    print("\n工具:")
    for name, repo, what in PLAYABILITY_TOOLS:
        print(f"\n   【{name}】{repo}")
        print(f"      {what}")
    return 0


def cmd_pcg(a):
    _hdr("程序化生成可复现性")
    for p in PCG:
        print(f"   {p}")
    return 0


def cmd_init(a):
    os.makedirs(os.path.dirname(a.init) or ".", exist_ok=True)
    with open(a.init, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow([k for k, _ in FIELDS])
        w.writerow(["TODO"] * len(FIELDS))
    print(f"已生成音频/渲染表: {a.init}")
    print("\n⚠️ 十二域：audio / music / spatial / mix / voip / lighting / "
          "visibility / postfx / variants / quality / playability / pcg")
    return 0


def cmd_check(a):
    if not os.path.exists(a.check):
        print(f"❌ 文件不存在: {a.check}")
        return 2
    with open(a.check, encoding="utf-8", errors="replace", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        print("❌ 空表")
        return 1

    def g(r, k):
        return (r.get(k) or "").strip()

    mismatch, no_legacy = [], []
    for i, r in enumerate(rows, 1):
        m = g(r, "match").lower()
        if m not in ("yes", "y", "true", "是", "一致"):
            mismatch.append(i)
        if not g(r, "legacy_value") or g(r, "legacy_value") == "TODO":
            no_legacy.append(i)

    print("=" * 76)
    print(f"音频/渲染 · {len(rows)} 条")
    print("=" * 76)
    if mismatch:
        print(f"\n🚫 **不一致** {len(mismatch)} 条（行 {mismatch[:15]}）")
        print("   → 音频信号链与渲染设置是观感的主要来源，不是可选项")
    if no_legacy:
        print(f"\n❌ {len(no_legacy)} 条缺**原版值**（行 {no_legacy[:15]}）")

    if not (mismatch or no_legacy):
        print("\n✅ 音频/渲染：一致且原版值完整")

    print("\n🔑 **渲染差异大多发生在资源与设置层，不是代码逻辑。**")
    print("   **音频事件迁移只是表层，信号链才是观感。**")
    print("   **Bot 通关 ≠ 体验一致。**")
    return 1 if (a.gate and (mismatch or no_legacy)) else 0


def main():
    ap = argparse.ArgumentParser(description="音频/渲染/可玩性")
    ap.add_argument("--audio", action="store_true")
    ap.add_argument("--music", action="store_true")
    ap.add_argument("--spatial", action="store_true")
    ap.add_argument("--mix", action="store_true")
    ap.add_argument("--voip", action="store_true")
    ap.add_argument("--render", action="store_true")
    ap.add_argument("--lighting", action="store_true")
    ap.add_argument("--visibility", action="store_true")
    ap.add_argument("--postfx", action="store_true")
    ap.add_argument("--variants", action="store_true")
    ap.add_argument("--quality", action="store_true")
    ap.add_argument("--playability", action="store_true")
    ap.add_argument("--pcg", action="store_true")
    ap.add_argument("--init")
    ap.add_argument("--check")
    ap.add_argument("--gate", action="store_true")
    a = ap.parse_args()
    fns = {"audio": cmd_audio, "music": cmd_music, "spatial": cmd_spatial,
           "mix": cmd_mix, "voip": cmd_voip, "render": cmd_render,
           "lighting": cmd_lighting, "visibility": cmd_visibility,
           "postfx": cmd_postfx, "variants": cmd_variants,
           "quality": cmd_quality, "playability": cmd_playability, "pcg": cmd_pcg}
    for k, fn in fns.items():
        if getattr(a, k):
            return fn(a)
    if a.init:
        return cmd_init(a)
    if a.check:
        return cmd_check(a)
    print("❌ 需要 --audio / --music / --spatial / --mix / --voip / --render / "
          "--lighting / --visibility / --postfx / --variants / --quality / "
          "--playability / --pcg / --init / --check 之一")
    return 2


if __name__ == "__main__":
    sys.exit(main())
