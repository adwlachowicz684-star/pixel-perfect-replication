#!/usr/bin/env python3
"""WPF / .NET / Win32 机制清单（第九轮 A 区）—— 最贴身的盲区。

**为什么这是盲区**：我们的案例就是 **WPF → Tauri**，
但前八轮从未系统清点"WPF 特有机制"。XAML 常被当成"控件和样式"，
实际应拆成**属性系统、事件系统、模板系统、资源系统、树结构**五张清单。

**每个机制必须写清三段**：
`静态定位 → 运行时取证 → 等价验收`
`acceptance_criteria` 必须给**可判定布尔条件**，不是"尽量一致"。

用法:
  wpf_mechanism.py --list                          # 全机制清单
  wpf_mechanism.py --init ledger/wpf_mechanisms.csv
  wpf_mechanism.py --check ledger/wpf_mechanisms.csv --gate
  wpf_mechanism.py --leak                          # WPF 四大泄漏根因
  wpf_mechanism.py --dpi                           # DPI 基线矩阵
  wpf_mechanism.py --precedence                    # 依赖属性值优先级链

退出码: 0 通过 / 1 缺项或验收未定 / 2 用法错误
"""
import argparse
import csv
import os
import sys

# 依赖属性值优先级（**真正的难点不是"有个属性"**）
PRECEDENCE = [
    ("1. 强制值 / coercion", "强制回调结果 —— **最高**（除活动动画）"),
    ("2. 活动动画 / Animation", "正在运行的动画**覆盖局部值**"),
    ("3. 局部值 LocalValue", "直接设置的值，**通常高于样式 setter**"),
    ("4. TemplateParent 模板属性", "模板触发器"),
    ("5. 隐式样式 Implicit Style", "TargetType 自动应用"),
    ("6. 样式触发器 Style Trigger", "IsMouseOver / IsEnabled / DataTrigger"),
    ("7. 模板触发器 Template Trigger", "ControlTemplate 内"),
    ("8. 样式 Setter", "Style 里的 Setter"),
    ("9. 默认样式 / 主题", "ThemeStyle"),
    ("10. 属性继承 Inherited", "沿逻辑树继承"),
    ("11. 元数据默认值 Default", "DependencyProperty 注册的默认值"),
]

# 五张机制清单
MECHANISMS = [
    # (类别, 机制, 必须记录字段, 目标栈常见误判)
    ("属性系统", "DependencyProperty",
     "注册 owner / name / type / default / metadata / coerce / changed / 只读 / **值优先级链**",
     "用普通 React state 替代，丢失优先级和元数据语义"),
    ("属性系统", "附加属性 AttachedProperty",
     "允许子元素向父元素报告值；RegisterAttached 定位", "被当成普通 props 传下去"),
    ("事件系统", "路由事件 RoutingStrategy",
     "**冒泡 / 隧道(Preview) / 直接**，event_path、handled_at、e.Handled 副作用",
     "只绑 onClick，漏掉隧道、Handled 或冒泡链"),
    ("事件系统", "隧道冒泡共享事件数据",
     "输入事件通常**先 Preview 再冒泡**，二者共享事件数据",
     "因 DOM stopPropagation 更简单而直接收敛为一次回调"),
    ("事件系统", "AddHandler(HandledEventsToo)",
     "即使 Handled=true 仍接收", "复刻后收不到已被处理的事件"),
    ("绑定系统", "Binding Mode",
     "OneWay / TwoWay / OneWayToSource / OneTime", "认为所有双向绑定都每次按键回写"),
    ("绑定系统", "UpdateSourceTrigger",
     "PropertyChanged（立即）/ LostFocus（延迟）/ Explicit；另有 **Delay**",
     "回写时机不同 = 手感与校验时机都不同"),
    ("绑定系统", "ValidationRule / IDataErrorInfo",
     "异常、IDataErrorInfo、自定义规则；**红框与错误模板**", "丢了验证视觉反馈"),
    ("绑定系统", "Converter / FallbackValue / TargetNullValue",
     "类型转换、绑定失败回退、null 目标值", "忽略回退/空值与格式化（**待核**）"),
    ("模板系统", "ControlTemplate",
     "模板目标、触发器、VisualState、TemplatePart", "只做 CSS 外观相似，未复刻按下/禁用/聚焦态"),
    ("模板系统", "DataTemplate / ItemsPanelTemplate", "数据呈现与项容器布局", ""),
    ("模板系统", "Adorner / Decorator",
     "覆盖在视觉树上层，**影响命中测试和遮挡**", "漏掉命中测试区"),
    ("资源系统", "StaticResource vs DynamicResource",
     "引用键、**资源字典合并顺序**、动态主题、ThemeDictionary",
     "全静态化破坏动态主题；全动态化损害性能"),
    ("资源系统", "Freezable 冻结资源",
     "冻结后不可修改；跨线程/动画/资源修改语义", "修改冻结资源是否抛异常未验"),
    ("树结构", "视觉树 vs 逻辑树",
     "Visual/Logical 节点、命名作用域、TemplatedParent、DataContext 范围",
     "只测逻辑结构，漏掉模板内命中测试区"),
    ("布局系统", "Measure / Arrange 双遍",
     "DesiredSize、availableSize、margin、constraint、LayoutSlot、触发源",
     "**只比最终尺寸，不比约束传播和布局抖动**"),
    ("布局系统", "VirtualizingStackPanel",
     "VirtualizationMode(Standard/Recycling)、CacheLength、容器回收、选中/焦点跨滚回用",
     "认为「用了虚拟化就是等价」"),
    ("运行时", "Dispatcher 优先级队列",
     "BeginInvoke 异步 / Invoke 同步 / PushFrame；**优先级决定行为时间轴**",
     "只测最终画面，不测事件执行顺序"),
    ("运行时", "CompositionTarget.Rendering", "持续驱动动画；**不用时必须解绑**", "成为持续工作源"),
    ("Win32", "SendMessage vs PostMessage",
     "SendMessage **处理完才返回**；PostMessage 入队立即返回",
     "同步/异步边界丢失 → 卡死或延迟回包"),
    ("Win32", "DPI Per-Monitor V2",
     "manifest/API awareness、WM_DPICHANGED、物理/逻辑坐标、非 DPI-aware 子进程",
     "只测 100% DPI"),
    ("Win32", "DWM 合成 / 非客户区 / Aero Snap", "", ""),
    ("Win32", "任务栏：进度 / 覆盖图标 / 缩略图工具栏 / 跳转列表", "", ""),
    ("Win32", "通知区域图标生命周期", "", ""),
    ("Win32", "文件关联与默认程序", "", ""),
    ("Win32", "UAC 清单 / 进程完整性级别", "", ""),
    ("Win32", "COM STA / MTA 线程模型", "原版若依赖 STA 消息泵", "用任意 worker 线程直接操作 UI"),
    ("Win32", "剪贴板格式链 / 延迟渲染 / OLE 拖放", "", ""),
    ("NET", "SynchronizationContext / ConfigureAwait", "UI 线程亲和性", ""),
    ("NET", "async void / 取消令牌 / 异常观察", "", ""),
    ("NET", "GC 模式（工作站/服务器、并发）、LOH", "", ""),
]

# WPF 四大泄漏根因（**不是泛化的"内存高"**）
LEAKS = [
    ("①静态/单例事件未退订", "长期对象订阅静态事件或单例事件且未退订"),
    ("②Binding 资源未释放", "Converter / ValidationRule / **Freezable** 等未释放"),
    ("③未注销的持续源", "CompositionTarget.Rendering、DispatcherTimer、"
                        "弱事件未使用或弱引用被提前复活"),
    ("④非托管与视觉树残留", "Dispose 缺失、finalizer 未终结、"
                        "**WPF 内部保留的视觉树/事件 handler 引用链**"),
]

DPI_MATRIX = [
    "96 / 120 / 144 / 150 / 175 / 200 DPI",
    "至少两种显示器排列",
    "主屏启动 / 副屏启动",
    "跨屏拖拽",
    "恢复窗口 / 最大化",
    "DWM 缩放",
    "远程桌面",
    "**整数与非整数缩放**（取整差异最容易漏）",
]

EXEC_ORDER = [
    "输入捕获", "路由事件（Preview → 冒泡）", "绑定校验",
    "布局无效化", "渲染帧", "动画 tick", "资源释放",
]

FIELDS = [
    ("id", "机制编号"),
    ("layer", "层（XAML / WPF运行时 / NET / Win32）"),
    ("category", "类别（属性/事件/绑定/模板/资源/树/布局/运行时/消息/DPI）"),
    ("runtime_evidence", "**运行时取证**（ETW/EventPipe/dump/日志/UIA/录制）"),
    ("side_effect", "副作用"),
    ("new_stack_equivalence", "新栈等价物"),
    ("visual_evidence", "视觉证据（分辨率/DPI/缩放/动画帧/焦点态/截图/diff）"),
    ("acceptance_criteria", "**可判定布尔条件**（不许写「尽量一致」）"),
    ("tool", "所用工具"),
    ("status", "状态"),
]



# ==========================================================================
# 🔑 第五十九轮新增：**白名单枚举** + **跨字段一致性**
#
# 🔴 混沌测试（第五十六～五十八轮）连续三轮发现：本脚本属于 A 类盲区——
#    `--check` 只做**结构性缺失**检查（空值/TODO），
#    🔴 **填任意非法值都静默通过**（黑名单式校验的通病）。
# 🔑 修复：关键字段改为**白名单枚举**；并检测"字段合法但整行自相矛盾"。
# ==========================================================================

# ==========================================================================
# 🔑 第六十一轮新增：**枚举的两类语义必须分开**
#
# 🔴 第六十轮留下的未闭合缺口：这些 `ENUMS` 合法值是**按字段语义推断**的，
#    不是从原版证据提取的。
# 🔑 本轮不是去"补全证据"（那需要原版取证），而是**把语义显式标出来**：
#
#    ENUMS_KIND = 'constraint'  → **校验器输入约束**
#        只用于"防止填错值"，🔴 **不构成 must-match 主张**。
#        例：level 只能是 debug/info/warn——这是我们给表定的填写规范。
#
#    ENUMS_KIND = 'must_match'  → **原版行为事实**
#        枚举本身是 must-match 对象，🔴 **必须由原版证据支撑**，
#        例：某作"处置"字段只有这三种，是原版真实存在的分类。
#
# 🔑 当前全部标为 'constraint' —— **因为我们没有原版证据**。
# 🔴 若某天要把它升为 'must_match'，必须同时补 `evidence` 字段，
#    **不能只改标签**。
# ==========================================================================
ENUMS_KIND = 'constraint'   # 🔴 不是 must-match；升级需附原版证据

ENUMS = {'status': ('待挖', '已挖', '已验证', '不适用', 'unknown')}
_CLAIM_OK = {'status': ('已验证',)}
_WEAK_EVIDENCE = ('unknown', 'secondhand', 'unverified', '', 'todo')


def _enum_violations(rows, enums=None):
    """🔑 白名单校验：值不在合法枚举内 → 违例。"""
    enums = enums or ENUMS
    out = []
    for i, r in enumerate(rows, 1):
        for k, ok in enums.items():
            v = (r.get(k) or '').strip()
            if not v or v.lower() in ('todo', 'tbd', '待填', '—'):
                continue          # 🔑 结构性缺失由原有逻辑负责
            if v.lower() not in ok:
                out.append((i, k, v))
    return out


def _contradictions(rows, enums=None):
    """🔑 跨字段一致性：**每个字段都合法，但整行在说谎**。"""
    enums = enums or ENUMS
    out = []
    for i, r in enumerate(rows, 1):
        ev = (r.get('evidence') or '').strip().lower()
        for k, claims in _CLAIM_OK.items():
            v = (r.get(k) or '').strip().lower()
            if v in claims and ev in _WEAK_EVIDENCE:
                out.append((i, '`' + k + '`=`' + v + '` 但 evidence=`'
                            + (ev or '(空)') + '`（证据不支持强主张）'))
        conf = (r.get('confidence') or '').strip().lower()
        mt = (r.get('match_type') or '').strip().lower()
        if mt == 'exact' and conf == 'low':
            out.append((i, 'match_type=exact 但 confidence=low（低置信不能声称精确）'))
    return out

def cmd_list(a):
    print("=" * 78)
    print(f"WPF/.NET/Win32 机制清单 · {len(MECHANISMS)} 条")
    print("=" * 78)
    cur = None
    for cat, mech, fields, wrong in MECHANISMS:
        if cat != cur:
            print(f"\n【{cat}】")
            cur = cat
        print(f"   · {mech}")
        if fields:
            print(f"       记录: {fields}")
        if wrong:
            print(f"       ⚠️ 误判: {wrong}")
    print("\n⚠️ XAML 不是「控件和样式」，是五张清单：")
    print("   属性系统 / 事件系统 / 模板系统 / 资源系统 / 树结构")
    return 0


def cmd_precedence(a):
    print("=" * 72)
    print("依赖属性值优先级（**从高到低**）")
    print("=" * 72)
    for k, why in PRECEDENCE:
        print(f"   {k:<34} {why}")
    print("\n⚠️ **局部值通常高于样式 setter，但正在运行的动画是例外** ——")
    print("   这条最容易在复刻时被颠倒。")
    print("\n⚠️ 改进发生在**计算完成后**，不是在测量前删除原版能力。")
    print("   除非证据表证明所有实际值路径只用到其中一两项，")
    print("   否则**不应发明一个统一状态对象直接替代**。")
    return 0


def cmd_leak(a):
    print("=" * 74)
    print("WPF 四大泄漏根因（**不是泛化的「内存高」**）")
    print("=" * 74)
    for k, why in LEAKS:
        print(f"\n   {k}")
        print(f"      {why}")
    print("\n取证: dotnet-counters / dotnet-trace / dotnet-dump / dotnet-gcdump")
    print("     （跨平台 EventPipe 由 dotnet/diagnostics 维护）")
    print("     Windows 深度分析可再用 PerfView（⚠️ **许可未核实，标来源不确定**）")
    return 0


def cmd_dpi(a):
    print("=" * 72)
    print("DPI 基线矩阵（**PMv2 下 DPI 改变要全树重布局**）")
    print("=" * 72)
    for d in DPI_MATRIX:
        print(f"   · {d}")
    print(f"\n执行顺序（Dispatcher 决定行为时间轴）:")
    for i, s in enumerate(EXEC_ORDER, 1):
        print(f"   {i}. {s}")
    print("\n⚠️ PMv2：窗口收到 WM_DPICHANGED，**不再位图拉伸**，")
    print("   自动处理非客户区/对话框/主题位图，但**应用仍须自己重设尺寸**。")
    return 0


def cmd_init(a):
    os.makedirs(os.path.dirname(a.init) or ".", exist_ok=True)
    with open(a.init, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow([k for k, _ in FIELDS])
        for i, (cat, mech, _f, _w) in enumerate(MECHANISMS, 1):
            w.writerow([f"W-{i:03d}", "", cat, "", "", "", "", "", "", "待挖"])
    print(f"已生成机制清单骨架: {a.init}（{len(MECHANISMS)} 条）")
    print("\n⚠️ 留空 = 未取证，--gate 会阻断。")
    print("   `acceptance_criteria` 必须是**可判定布尔条件**。")
    return 0


def cmd_check(a):
    if not os.path.exists(a.check):
        print(f"❌ 文件不存在: {a.check}")
        return 2
    with open(a.check, encoding="utf-8", errors="replace", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        print("❌ 空表")
        return 2

    no_runtime, no_accept, vague, missing = [], [], [], []
    for i, r in enumerate(rows, 1):
        def g(k):
            return (r.get(k) or "").strip()
        if not g("runtime_evidence") or g("runtime_evidence") == "TODO":
            no_runtime.append(i)
        ac = g("acceptance_criteria")
        if not ac or ac == "TODO":
            no_accept.append(i)
        elif any(w in ac for w in ("尽量", "差不多", "基本一致", "尽量一致", "看着对")):
            vague.append((i, ac))
        miss = [k for k, _ in FIELDS
                if not g(k) or g(k) in ("TODO", "待填", "—", "待挖")
                and k != "status"]
        if miss:
            missing.append((i, miss))

    print("=" * 72)
    print(f"WPF 机制清单 · {len(rows)} 条")
    print("=" * 72)
    if no_runtime:
        print(f"\n❌ {len(no_runtime)} 条缺**运行时取证**（行 {no_runtime[:15]}）")
        print("   静态定位不算证据 —— 必须 ETW/EventPipe/dump/UIA/录制")
    if no_accept:
        print(f"\n❌ {len(no_accept)} 条缺**验收条件**（行 {no_accept[:15]}）")
    if vague:
        print(f"\n❌ {len(vague)} 条验收条件含糊（**不可判定**）:")
        for i, ac in vague[:8]:
            print(f"   行{i}: {ac[:50]}")
        print("   → 必须改成布尔条件，例如「按下态背景色与基准 RGB 差 ≤ 1」")
    if missing:
        print(f"\n⚠️ {len(missing)} 条字段不全")

    if not (no_runtime or no_accept or vague):
        print("\n✅ 机制清单完整")

    print("\n⚠️ 若静态尺寸、字体、padding 都相同但 **resize 时**有像素差异 ——")
    print("   优先执行**约束传播探针**，**不要立即改 CSS**：")
    print("   固定尺寸 → 约束尺寸 → 内容增长 → 容器边界 → 滚动出现 → DPI 切换")
    # 🔑 第五十九轮：白名单违例 + 语义矛盾 也须阻断
    _ev = _enum_violations(rows)
    if _ev:
        print('\n🚫 **字段白名单违例**（🔴 黑名单只查空值，查不出**填错的值**）:')
        for i, k, v in _ev[:12]:
            print(f'   行 {i}: `{k}` = `{v}` 不在合法枚举内')
        print('   🔑 合法值见本文件顶部 ENUMS')
    _ct = _contradictions(rows)
    if _ct:
        print('\n🚫 **跨字段语义矛盾**（🔑 字段合法 ≠ 行自洽）:')
        for i, w in _ct[:12]:
            print(f'   行 {i}: {w}')

    return 1 if (a.gate and (no_runtime or no_accept or vague or _ev or _ct)) else 0


def main():
    ap = argparse.ArgumentParser(description="WPF/.NET/Win32 机制清单")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--precedence", action="store_true")
    ap.add_argument("--leak", action="store_true")
    ap.add_argument("--dpi", action="store_true")
    ap.add_argument("--init")
    ap.add_argument("--check")
    ap.add_argument("--gate", action="store_true")
    a = ap.parse_args()

    if a.precedence:
        return cmd_precedence(a)
    if a.leak:
        return cmd_leak(a)
    if a.dpi:
        return cmd_dpi(a)
    if a.init:
        return cmd_init(a)
    if a.check:
        return cmd_check(a)
    if a.list:
        return cmd_list(a)
    print("❌ 需要 --list / --precedence / --leak / --dpi / --init / --check 之一")
    return 2


if __name__ == "__main__":
    sys.exit(main())
