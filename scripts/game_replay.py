#!/usr/bin/env python3
"""确定性回放与 desync 定位（游戏复刻核心门禁）。

**为什么游戏必须有这一层**：
> 桌面应用不需要帧级确定性，**游戏需要** ——
> 回放、网络同步、TAS、得分比较、验证都建立在它之上。
> 即使最终画面相同，也可能因**一帧输入提前、一次浮点舍入、一处碰撞顺序不同**
> 而破坏回放。

**核心判据**：
> **首个发散帧（diverged_tick）比最终画面差异重要一万倍。**

不能只比较最终世界状态 —— 不同错误可能**偶然抵消**。
做法：原版与新实现从同一初始快照执行相同输入，逐帧算状态哈希链，
首次不匹配的 tick 就是 desync 点；再对子系统二分，定位到具体层。

用法:
  game_replay.py --init ledger/replay_manifest.yaml
  game_replay.py --check ledger/replay_manifest.yaml --gate
  game_replay.py --digest ledger/replay_manifest.yaml --out replay.digest
  game_replay.py --desync --old old.jsonl --new new.jsonl
  game_replay.py --subsystems        # 打印子系统哈希判因表

退出码: 0 一致 / 1 有 desync 或 manifest 缺项 / 2 用法错误
"""
import argparse
import csv
import hashlib
import json
import os
import sys

# 回放 manifest 必填（缺一项就无法复现）
REQUIRED = [
    ("version", "目标版本/构建 ID"),
    ("executable_hash", "原版可执行文件哈希"),
    ("seed", "初始 RNG 种子"),
    ("initial_state_hash", "初始状态哈希"),
    ("tick_rate", "逻辑帧率（**不是渲染帧率**）"),
    ("fixed_step", "固定时间步 dt"),
    ("max_substeps", "最大子步数（防螺旋死亡）"),
    ("input_stream_hash", "输入流哈希"),
    ("input_poll_rate", "输入轮询率"),
    ("render_api", "渲染 API"),
    ("physics_engine", "物理引擎"),
    ("audio_middleware", "音频中间件"),
    ("build_manifest", "编译器版本 + flags + 浮点模型"),
]

# 子系统哈希 → 先变说明什么
SUBSYSTEMS = [
    ("rng", "RNG 先变", "种子/调用顺序错误（**最常见**）"),
    ("input", "输入先变", "设备映射、轮询率、死区、规范化不一致"),
    ("physics", "物理先变但输入一致", "子步数、接触顺序、约束求解、休眠阈值"),
    ("collision", "碰撞先变", "碰撞层、射线、形状 margin、broadphase"),
    ("movement", "移动先变", "角色控制器参数：coyote time、跳跃缓冲、抓地"),
    ("ai", "AI 先变", "遍历顺序、浮点、并行任务窃取"),
    ("animation", "动画事件先变", "事件时间轴、混合权重、采样率"),
    ("audio_events", "音频事件先变", "触发条件、调度顺序"),
    ("render", "render 先变但逻辑不变", "**表现层问题**，不影响回放正确性"),
]

MANIFEST_TPL = """# 回放 manifest —— 缺任何一项都无法复现
version: "{version}"
executable_hash: "{exe}"
seed: 0
initial_state_hash: ""
tick_rate: 60
fixed_step: 0.016666666666666666
max_substeps: 5
input_stream_hash: ""
input_poll_rate: 1000
render_api: "d3d11"
physics_engine: ""
audio_middleware: ""
build_manifest: ""
compatible_mode: ""     # libTAS 兼容模式：软件渲染/时间追踪/音频驱动/线程回收
"""


def cmd_subsystems(a):
    print("=" * 74)
    print("子系统哈希判因（哪个先变 → 问题在哪层）")
    print("=" * 74)
    for k, sig, why in SUBSYSTEMS:
        print(f"\n【{k}】{sig}")
        print(f"   → {why}")
    print("\n⚠️ **render 先变但逻辑不变 = 表现层问题**，不影响回放正确性；")
    print("   反过来逻辑先变而 render 没变，**不代表没问题**（可能还没到那帧）。")
    print("\n⚠️ 有 savestate API ≠ 有可回滚游戏 ——")
    print("   摩擦改动、增删物体、约束触发、事件队列、对象 ID 都必须自行恢复并按原顺序重放。")
    return 0


def cmd_init(a):
    os.makedirs(os.path.dirname(a.init) or ".", exist_ok=True)
    body = MANIFEST_TPL.format(version="TODO", exe="TODO")
    with open(a.init, "w", encoding="utf-8") as f:
        f.write(body)
    print(f"已生成回放 manifest 骨架: {a.init}")
    print("\n⚠️ 留 TODO 的字段 = 无法复现，--gate 会阻断。")
    print("   **逻辑时钟不能取墙钟** —— libTAS 会拦截 clock_gettime/SDL_GetTicks/")
    print("   sleep/条件变量/线程生命周期，并把初始系统时间写进影片文件。")
    return 0


def _load_manifest(path):
    """尽力解析 YAML；无 PyYAML 时用 key: value 降级。"""
    text = open(path, encoding="utf-8", errors="replace").read()
    try:
        import yaml
        return yaml.safe_load(text) or {}
    except ImportError:
        out = {}
        for line in text.splitlines():
            if ":" in line and not line.lstrip().startswith("#"):
                k, _, v = line.partition(":")
                out[k.strip()] = v.strip().strip('"')
        return out


def cmd_check(a):
    if not os.path.exists(a.check):
        print(f"❌ 文件不存在: {a.check}")
        return 2
    m = _load_manifest(a.check)
    missing = []
    for k, why in REQUIRED:
        v = m.get(k)
        if v is None or str(v).strip() in ("", "TODO", "待填"):
            missing.append((k, why))

    print("=" * 70)
    print("回放 manifest")
    print("=" * 70)
    for k, why in REQUIRED:
        v = m.get(k)
        ok = v is not None and str(v).strip() not in ("", "TODO", "待填")
        print(f"   {'✅' if ok else '❌'} {k:<20} {why}"
              f"{'' if ok else '  ← 未填'}")
    if missing:
        print(f"\n❌ 阻断 {len(missing)} 项未填 —— 缺任何一项都**无法复现**")
        print("   ⚠️ 不要把「游戏能跑」当成「可回放」。")
    else:
        print("\n✅ manifest 完整")

    print("\n⚠️ 确定性三条腿：时钟（读 monotonic tick，不读墙钟）·")
    print("   输入（先序列化再送模拟）· 状态（覆盖实体/事件队列/RNG/计时器，")
    print("   **不能只存玩家位置**）")
    return 1 if (a.gate and missing) else 0


def cmd_digest(a):
    m = _load_manifest(a.digest)
    # 内容寻址：输入 + RNG + 配置 + 初始状态 + 构建版本
    parts = [str(m.get(k, "")) for k, _ in REQUIRED]
    blob = "|".join(parts).encode("utf-8")
    d = hashlib.sha256(blob).hexdigest()
    if a.out:
        os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump({"digest": d, "inputs": dict(m)}, f,
                      ensure_ascii=False, indent=2)
        print(f"→ {a.out}")
    print(f"\nreplay_digest: {d}")
    print("\n⚠️ **版本不一致直接失败** —— digest 必须包含构建版本，")
    print("   否则不同构建的回放会被误当作同一条。")
    return 0


def _load_chain(path):
    """读逐帧哈希链 JSONL 或 CSV。每行需 tick + 各子系统哈希。"""
    rows = []
    if path.endswith(".jsonl"):
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
    else:
        with open(path, encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))
    return rows


def cmd_desync(a):
    for p in (a.old, a.new):
        if not os.path.exists(p):
            print(f"❌ 文件不存在: {p}")
            return 2
    old, new = _load_chain(a.old), _load_chain(a.new)
    if not old or not new:
        print("❌ 哈希链为空")
        return 2

    def tick_of(r):
        for k in ("tick", "frame", "logical_tick"):
            if k in r:
                try:
                    return int(r[k])
                except Exception:
                    pass
        return None

    om = {tick_of(r): r for r in old if tick_of(r) is not None}
    nm = {tick_of(r): r for r in new if tick_of(r) is not None}
    ticks = sorted(set(om) & set(nm))

    # 全状态哈希列
    def state_of(r):
        for k in ("state_hash", "hash", "digest", "checksum"):
            if k in r and r[k]:
                return str(r[k])
        return None

    diverged = None
    matched = 0
    for t in ticks:
        so, sn = state_of(om[t]), state_of(nm[t])
        if so is None or sn is None:
            continue
        if so != sn:
            diverged = t
            break
        matched += 1

    print("=" * 72)
    print(f"desync 定位 · 比对 {len(ticks)} 帧")
    print("=" * 72)
    print(f"   一致前缀: {matched} 帧")

    if diverged is None:
        print("   ✅ 无 desync（在共同帧范围内）")
        if len(om) != len(nm):
            print(f"   ⚠️ 帧数不同：原版 {len(om)} / 新版 {len(nm)} —— 检查总时长")
        return 0

    print(f"\n🎯 **首个发散帧 tick={diverged}**")

    # 子系统定位：找第一个不一致的子系统
    subs = [k for k, _, _ in SUBSYSTEMS]
    found = []
    r_o, r_n = om[diverged], nm[diverged]
    for s in subs:
        vo, vn = r_o.get(s), r_n.get(s)
        if vo is not None and vn is not None and str(vo) != str(vn):
            found.append(s)
    if found:
        print(f"\n   该帧不一致的子系统: {', '.join(found)}")
        for s in found:
            why = next((w for k, _, w in SUBSYSTEMS if k == s), "")
            print(f"      【{s}】→ {why}")
    else:
        print("\n   ⚠️ 未标注子系统哈希 —— **无法判因**。")
        print("      建议逐帧导出 movement/physics/collision/rng/ai 等摘要，")
        print("      否则只能重新二分输入区间，代价高得多。")

    # 前一帧供对照
    prev = max((t for t in ticks if t < diverged), default=None)
    if prev is not None:
        print(f"\n   前一帧 tick={prev} 状态一致 → 发散发生在 [{prev} → {diverged}]")
        print("   下一步：恢复该区间前后状态，**二分输入区间**，")
        print("   可把数百小时回放收敛到几十帧。")

    print("\n⚠️ 不能只比较最终世界状态 —— 不同错误可能**偶然抵消**。")
    print("⚠️ matching 分三档：exact-match（模拟/RNG/碰撞/存档/回放必须一致）·")
    print("   equivalent（需完整差分+属性测试证明）· modern-replacement（明确允许改算法）")
    print("   **把第三档伪装成第一档是与理念最危险的冲突。**")

    if a.out:
        os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump({"matched_prefix": matched, "diverged_tick": diverged,
                       "subsystems_diverged": found,
                       "prev_tick": prev}, f, ensure_ascii=False, indent=2)
        print(f"\n→ {a.out}")
    return 1 if a.gate else 0


def main():
    ap = argparse.ArgumentParser(description="确定性回放与 desync 定位")
    ap.add_argument("--init")
    ap.add_argument("--check")
    ap.add_argument("--digest")
    ap.add_argument("--desync", action="store_true")
    ap.add_argument("--old")
    ap.add_argument("--new")
    ap.add_argument("--out")
    ap.add_argument("--gate", action="store_true")
    ap.add_argument("--subsystems", action="store_true")
    a = ap.parse_args()

    if a.subsystems:
        return cmd_subsystems(a)
    if a.init:
        return cmd_init(a)
    if a.check:
        return cmd_check(a)
    if a.digest:
        return cmd_digest(a)
    if a.desync:
        if not (a.old and a.new):
            print("❌ --desync 需要 --old/--new")
            return 2
        return cmd_desync(a)
    print("❌ 需要 --init / --check / --digest / --desync / --subsystems 之一")
    return 2


if __name__ == "__main__":
    sys.exit(main())
