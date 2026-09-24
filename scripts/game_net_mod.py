#!/usr/bin/env python3
"""版本基准 / 网络同步 / 模组 API（深化第三轮 B / C / D 类）。

**🔑 B 类核心**：
> **"复刻哪个版本"必须成为独立需求，不是立项说明中的一句话。**
> 只写"复刻《某游戏》1.7"**不足以决定验收基线**。

**🔑 C 类核心**：
> **GGPO 只覆盖回滚输入同步的一部分，不是整个网络层的同义词。**
> 帧同步、状态同步、输入同步、客户端预测、服务器权威、插值/外插、
> 延迟补偿、回滚与重模拟是**不同故障域**。

**🔑 D 类核心**：
> 模组测试的目标不是"能加载"，而是**API 表面和错误语义稳定**。

用法:
  game_net_mod.py --version       # 版本指纹（**先冻结，再复刻**）
  game_net_mod.py --patch         # 补丁三类（不能按修复/新增粗分）
  game_net_mod.py --sync          # 五种同步模型
  game_net_mod.py --metrics       # 网络验证指标
  game_net_mod.py --weather       # 网络气象矩阵
  game_net_mod.py --inject        # 失败注入（**发布门禁，不是设计文档**）
  game_net_mod.py --mod           # 模组 API 表面与兼容矩阵
  game_net_mod.py --platform      # 平台集成表面
  game_net_mod.py --init ledger/net_mod.csv
  game_net_mod.py --check ledger/net_mod.csv --gate

退出码: 0 通过 / 1 缺项 / 2 用法错误
"""
import argparse
import csv
import os
import sys

# 版本指纹（**机器可比较**）
VERSION_FIELDS = [
    "平台", "商店 SKU", "构建号", "**可执行文件哈希**", "**资源包哈希**",
    "脚本/蓝图哈希", "**网络协议版本**", "服务器版本", "API/SDK 版本",
    "**内容清单**", "补丁编号", "**热修复编号**", "语言包版本",
    "日期时区", "安装序列", "启动参数", "区域", "硬件档位",
    "模拟器/固件版本",
]

VERSION_RULES = [
    "🔑 若可执行文件**剥离符号** → 同时保留资源版本与**运行时协议探针**",
    "🔑 若 PC/主机/移动端**内容清单不同** → **必须分别建分支**，"
    "不能只写一个「通用版本/最终版」字段",
    "⚠️ baseline mismatch 即失败",
]

# 补丁三类（**不能按修复/新增粗分**）
PATCH_CLASSES = [
    ("必须复现", "属于目标基准版本的行为", "进入 must-match"),
    ("**有意偏离**", "目标版本不含此行为", "登记 + 说明理由 + 批准"),
    ("**无法复现**", "技术或平台限制", "记录为已知差异，不是「以后再说」"),
]

PATCH_LOCATE = [
    "文件", "资源", "脚本", "配置", "**协议**", "关卡", "文案", "**数值**", "构建参数",
]

PATCH_FIELDS = [
    "变更前/后值", "触发场景", "**是否影响旧存档**", "是否跨平台一致",
    "发布日期", "**回滚影响**", "验证录像",
]

PATCH_TARGET = [
    "🔑 目标分歧必须先定：",
    "   · **忠实复刻首发版** → 1.0 的 bug、数值、隐藏内容就是 must-match，"
    "1.7 的「修复」只能作已知差异注释",
    "   · **最终体验** → 冻结最终稳定构建，并逐项解释**首发独有行为为何偏离**",
    "⚠️ 数值调整改写战斗经济性；关卡改动改变速通路径和隐藏内容；"
    "文案可能改变任务条件；协议变化可能让旧版客户端无法连接 —— "
    "**权重不同，不能都当内容补丁**",
]

# 五种同步模型（**不同故障域**）
SYNC_MODELS = [
    ("服务器权威状态同步", "客户端提交输入/意图，服务器算权威状态并广播增量",
     "依赖带宽、序列化、脏标记、对象生命周期"),
    ("确定性锁步 / 输入同步", "所有节点以相同初始状态和输入序列推进",
     "要求**固定步长、确定性随机、确定性浮点/容器顺序、版本一致规则集**"),
    ("客户端预测 + 服务器校正", "本地先动，服务器校正", "预测误差与校正量"),
    ("实体插值 / 外插", "远端实体平滑", "插值延迟、外插时间、抖动峰值"),
    ("延迟补偿 / 回滚重模拟", "命中判定做时间回滚", "需**状态快照 + 输入重放**"),
]

SYNC_NOTE = [
    "⚠️ 它们**并非互斥** —— 客户端可对本地移动预测、对远端实体插值、"
    "服务器对命中判定回滚；但**每种选择的故障表现不同**",
    "🔑 网络同步首先要回答**权威源、可观测状态、时钟模型**，"
    "**不是先选框架**",
]

METRICS = [
    "每秒状态差异", "状态字节数", "消息数", "重传数", "丢包率",
    "**RTT 及其抖动**", "发送/接收队列长度", "连接质量等级",
    "**回滚次数**", "**回滚深度**", "**重模拟帧数**",
    "**客户端预测误差**", "错误校正次数", "插值延迟", "外插时间",
    "抖动峰值", "命令延迟分布", "乱序包数", "重复包数",
    "快照确认延迟", "**服务器—客户端不一致计数**",
    "断线恢复时间", "状态最终收敛时间",
]

METRIC_RULES = [
    "🔑 **状态差异按相同输入序列比较权威快照字段**",
    "🔑 **预测误差按位置/速度/朝向/计时器的校正量分布记录**，"
    "并对 **95 分位和最大校正设阈值**",
    "⚠️ **不能用「看起来差不多」验收**",
    "⚠️ 从平均体验转向**尾部延迟和失败预算** —— "
    "尾部校正和回滚成本通常决定玩家是否感到「橡皮筋」",
]

WEATHER = [
    ("延迟", "0 / 20 / 80 / 150 / 300 ms"),
    ("丢包", "0.1% / 1% / 5% / 10%（**相关与非相关**）"),
    ("抖动", "5 / 20 / 50 ms"),
    ("重复", "1% / 5%"),
    ("损坏", "0.1% / 1%"),
    ("乱序", "10% / 25%"),
    ("带宽", "上限与**缓冲膨胀**"),
]

WEATHER_RULE = [
    "⚠️ **不能用单一 100 ms 延迟代表玩家网络**",
    "🔑 CI 中定义 **5~8 个固定「网络气象」**，每个对应性能/正确性基线",
    "🔑 网络变化后只允许结论为 **pass / fail / investigate**，"
    "**不得由开发者临时挑选「看起来不错」的一次录屏**",
]

# 失败注入（**门禁，不是文档**）
INJECT = [
    "客户端**越权写状态**", "重复提交同一命令", "**旧命令重放**", "乱序包",
    "未来时间戳", "过去时间戳", "命令漏执行", "重复 ack",
    "伪造 snapshot", "伪造实体 ID", "超长消息", "非法枚举",
    "**负数 / NaN / Infinity**", "越界数组", "缺失组件", "未知版本",
    "会话重连", "服务器版本回退", "连接抢占", "半关闭连接",
    "暂停后时间跳跃", "包发送过快", "包发送过慢",
]

INJECT_RULE = [
    "🔑 验收规则：服务器**拒绝 / 丢弃 / 封禁 / 回滚**，"
    "客户端**恢复到最后权威状态**，且不崩溃、不内存越界、"
    "**不出现无法退出状态**",
    "⚠️ **服务器权威不能只写进设计文档** —— 必须用失败注入证明"
    "客户端越权、重复提交、乱序包**均被拒绝**",
]

# 模组 API 表面
MOD_SURFACE = [
    "注册点", "生命周期（加载/启用/禁用/卸载）", "**API 版本**",
    "目标游戏版本", "**加载顺序**", "优先级/阶段", "依赖约束",
    "**资源覆盖层**", "虚拟文件系统", "符号解析", "脚本宿主",
    "沙箱", "CPU/内存/IO 配额", "**错误隔离**", "热重载",
    "持久化目录", "跨平台路径", "日志", "崩溃恢复", "**版本协商**",
]

MOD_TESTS = [
    "API 返回错误", "资源缺失", "符号缺失", "**旧脚本**",
    "**新脚本运行于旧宿主**", "并发注册", "重复注册", "取消注册",
    "热重载一半依赖", "加载顺序变化", "**依赖循环**", "递归调用",
    "栈溢出", "超大字符串", "恶意路径", "软链接", "权限不足",
    "只读目录", "磁盘满", "文件锁", "断点续传", "网络资源",
    "**脚本异常跨越 API 边界**", "宿主崩溃恢复",
]

MOD_RULES = [
    "🔑 目标不是「能加载」，而是**API 表面和错误语义稳定**",
    "🔑 API 兼容矩阵按**调用结果**设计，不是按「功能是否存在」 —— "
    "行=公开调用，列=旧实现/当前实现/缺失/新增必需参数/行为变化/"
    "错误码/超时/线程限制/资源所有权/回调生命周期/弃用计划",
    "🔑 脚本宿主应**当成正式 SDK**：语义版本、稳定文档、调用约定、"
    "禁止行为、性能预算、兼容性测试",
    "⚠️ 若原版**无官方模组 API**，仍要记录非官方扩展如何挂载 —— "
    "**这是原版功能的一部分**",
]

PLATFORM_FIELDS = [
    "可用", "不可用", "**平台独有**", "玩家可选", "首次授权", "登录状态",
    "**离线**", "过期 token", "账户切换", "区域", "隐私设置", "语言",
    "**Overlay**", "**输入提示**", "成就", "统计", "排行榜", "云存档",
    "好友", "邀请", "聊天", "语音", "DLC/创意工坊", "反馈", "商店",
    "订阅", "家长控制", "实名年龄", "**跨平台行为**",
]

PLATFORM_RULE = [
    "⚠️ 平台集成**即使被引擎插件封装，也不能只记录「调用成功」**",
    "⚠️ 若一个平台独有 DualSense 触觉而另一平台没有 → "
    "可保留为平台能力，但 must-match 基线应标记**「平台依赖」**，"
    "**不能凭空创造或删除**",
]

FIELDS = [
    ("item_id", "项编号"),
    ("domain", "域（version / patch / sync / metrics / inject / mod / platform）"),
    ("legacy_value", "**原版值**"),
    ("new_value", "新引擎值"),
    ("match", "**是否一致**"),
    ("baseline_frozen", "**版本基准是否已冻结**"),
    ("evidence", "证据"),
]


def _hdr(t, w=80):
    print("=" * w)
    print(t)
    print("=" * w)


def cmd_version(a):
    _hdr("版本指纹（🔑 **先冻结，再复刻**）")
    for f in VERSION_FIELDS:
        print(f"   · {f}")
    print("\n规则:")
    for r in VERSION_RULES:
        print(f"   {r}")
    print("\n🔑 **「复刻哪个版本」是独立需求，不是立项说明中的一句话。**")
    return 0


def cmd_patch(a):
    _hdr("补丁差异（**三类，不能按修复/新增粗分**）")
    for k, what, rule in PATCH_CLASSES:
        print(f"\n   【{k}】{what}")
        print(f"      → {rule}")
    print("\n先定位到: " + " · ".join(PATCH_LOCATE))
    print("\n再记录:")
    for f in PATCH_FIELDS:
        print(f"   · {f}")
    print("\n目标必须先定:")
    for t in PATCH_TARGET:
        print(f"   {t}")
    return 0


def cmd_sync(a):
    _hdr("五种同步模型（**不同故障域**）")
    for k, how, risk in SYNC_MODELS:
        print(f"\n   【{k}】{how}")
        print(f"      {risk}")
    print("")
    for n in SYNC_NOTE:
        print(f"   {n}")
    print("\n⚠️ **GGPO 只覆盖回滚输入同步的一部分** —— 完整多人还涉及连接、")
    print("   NAT、可靠/不可靠通道、重排、重复、心跳、重连、房间、匹配、")
    print("   服务器权威、反作弊、时间戳、时钟同步、带宽控制、平台中继。")
    return 0


def cmd_metrics(a):
    _hdr("网络验证指标（**不能用「看起来差不多」验收**）")
    for m in METRICS:
        print(f"   · {m}")
    print("\n规则:")
    for r in METRIC_RULES:
        print(f"   {r}")
    return 0


def cmd_weather(a):
    _hdr("网络气象矩阵")
    for k, v in WEATHER:
        print(f"   {k:<8} {v}")
    print("\n规则:")
    for r in WEATHER_RULE:
        print(f"   {r}")
    print("\n🔑 连续运行至少覆盖：暖机 · 空房间 · **峰值实体** · "
          "跨区域传送 · 长时在线 · 快速重连")
    return 0


def cmd_inject(a):
    _hdr("失败注入（🔑 **发布门禁，不是安全设计文档**）")
    for i, x in enumerate(INJECT, 1):
        print(f"   {i:>2}. {x}")
    print("\n规则:")
    for r in INJECT_RULE:
        print(f"   {r}")
    return 0


def cmd_mod(a):
    _hdr("模组 API 表面（**目标不是「能加载」**）")
    print("API 表面:")
    for f in MOD_SURFACE:
        print(f"   · {f}")
    print("\n边界测试:")
    for t in MOD_TESTS:
        print(f"   · {t}")
    print("\n规则:")
    for r in MOD_RULES:
        print(f"   {r}")
    return 0


def cmd_platform(a):
    _hdr("平台集成表面")
    for f in PLATFORM_FIELDS:
        print(f"   · {f}")
    print("\n规则:")
    for r in PLATFORM_RULE:
        print(f"   {r}")
    return 0


def cmd_init(a):
    os.makedirs(os.path.dirname(a.init) or ".", exist_ok=True)
    with open(a.init, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow([k for k, _ in FIELDS])
        w.writerow(["TODO"] * len(FIELDS))
    print(f"已生成网络/模组表: {a.init}")
    print("\n⚠️ 七域：version / patch / sync / metrics / inject / mod / platform")
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

    not_frozen, mismatch, no_legacy = [], [], []
    for i, r in enumerate(rows, 1):
        bf = g(r, "baseline_frozen").lower()
        if bf not in ("yes", "y", "true", "是", "已冻结", "n/a", "—"):
            not_frozen.append(i)
        m = g(r, "match").lower()
        if m not in ("yes", "y", "true", "是", "一致"):
            mismatch.append(i)
        if not g(r, "legacy_value") or g(r, "legacy_value") == "TODO":
            no_legacy.append(i)

    print("=" * 76)
    print(f"网络/模组 · {len(rows)} 条")
    print("=" * 76)
    if not_frozen:
        print(f"\n🚫 **版本基准未冻结** {len(not_frozen)} 条（行 {not_frozen[:15]}）")
        print("   → 🔑 **「复刻哪个版本」是独立需求** —— 只写「复刻 1.7」不足以决定基线")
    if mismatch:
        print(f"\n🚫 不一致 {len(mismatch)} 条（行 {mismatch[:15]}）")
    if no_legacy:
        print(f"\n❌ {len(no_legacy)} 条缺**原版值**（行 {no_legacy[:15]}）")

    if not (not_frozen or mismatch or no_legacy):
        print("\n✅ 网络/模组：基准已冻结、一致、原版值完整")

    print("\n🔑 **GGPO 不是整个网络层的同义词。**")
    print("   **服务器权威必须用失败注入证明，不能只写进设计文档。**")
    return 1 if (a.gate and (not_frozen or mismatch or no_legacy)) else 0


def main():
    ap = argparse.ArgumentParser(description="版本基准 / 网络同步 / 模组 API")
    ap.add_argument("--version", action="store_true")
    ap.add_argument("--patch", action="store_true")
    ap.add_argument("--sync", action="store_true")
    ap.add_argument("--metrics", action="store_true")
    ap.add_argument("--weather", action="store_true")
    ap.add_argument("--inject", action="store_true")
    ap.add_argument("--mod", action="store_true")
    ap.add_argument("--platform", action="store_true")
    ap.add_argument("--init")
    ap.add_argument("--check")
    ap.add_argument("--gate", action="store_true")
    a = ap.parse_args()
    fns = {"version": cmd_version, "patch": cmd_patch, "sync": cmd_sync,
           "metrics": cmd_metrics, "weather": cmd_weather, "inject": cmd_inject,
           "mod": cmd_mod, "platform": cmd_platform}
    for k, fn in fns.items():
        if getattr(a, k):
            return fn(a)
    if a.init:
        return cmd_init(a)
    if a.check:
        return cmd_check(a)
    print("❌ 需要 --version / --patch / --sync / --metrics / --weather / "
          "--inject / --mod / --platform / --init / --check 之一")
    return 2


if __name__ == "__main__":
    sys.exit(main())
