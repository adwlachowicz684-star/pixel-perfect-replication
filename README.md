# 像素级复刻 Skill

> ## 🔑 主场景：自有项目跨引擎搬迁与二次创作
>
> **这是自己的项目，在不同游戏引擎之间搬迁、重制与二次创造。**
> **不因"许可未确认""反编译风险""DRM"这类顾虑阻碍重制与二次开发。**
>
> `ledger/project.yaml` 写 `ownership: self`（默认）→ 法律/许可门禁**自动跳过**。
>
> 核心理念：**先像素级记录原引擎表现，再有意识地偏离** ——
> `must-match`（手感/数值/碰撞/时序）必须等价；
> 二次创作空间在 `may-evolve` / `should-reinvent` / `explicit-new`。
 · 导航

> **一句话**：把一份"能跑的旧实现"像素级完整复刻到新技术栈——
> 逐文件逐功能穷尽挖掘，既保体验细节，也识别当年技术限制下的权宜之计并换更好方案，
> 同时保留原版优秀设计。

**入口**：`SKILL.md`（总控）→ `flow/00-流程怎么用.md`（怎么跑）→ 各阶段卡。

---

## 零、🔑 本 Skill 分成两半，用途不同

| 目录 | 只写什么 | 什么时候读 |
|---|---|---|
| **`guide/`** | **只写「怎么做」**：七阶段流程 / 取证 / 记录 / 判定偏离 / 验收 / 游戏场景 | **执行复刻时** |
| **`audit/`** | **只写「不能怎么做」**：禁令总表 **489** 条 / 不得收工判据 / 证据与 unknown 红线 / 门禁清单 | **审核完成效果时** |

```
执行阶段   → 读 guide/，不被禁令打断
阶段收尾   → 切到 audit/ 对一遍
声明完成前 → 只读 audit/
```

> **为什么分**：合在一起时，执行的人被禁令打断，审核的人被流程稀释。

---

## 一、三条铁律 + 三条补充

| 铁律 | 核心 |
|---|---|
| **1 · 像素级** | 体验细节就是功能本身（四像素：视觉/交互/数据/行为） |
| **2 · 穷尽** | 挖掘没有"差不多了"（判据是台账清零 + unknown 清零） |
| **3 · 择优** | 复刻 ≠ 照抄（保留设计意图 + 替换技术权宜 + 保留优秀思路 + 结构化重组） |
| **1·补 机器化** | 能由机器复现的证据必须工具化 |
| **1·补2 原版可测量** ⭐ | **原版不是需求，是唯一可信的测量基准** |
| **2·补 体验参数** ⭐ | **可以不照搬，但必须知道搬前是什么样** |
| **2·补2 资产资源** ⭐ | 像素藏在**资源**里，不在逻辑里 |
| **2·补3 文案全维度** ⭐ | 参数管手感、资产管外观、**本篇管能不能用** |

---

## 二、阶段（S0 最早，先于挖掘）

```
S1 立项与基线
  ↓
S0 原版证据采集  ⭐ 原版是测量基准，不是待描述的需求
  ↓
S2 穷尽挖掘 ┬─ S2M 机器证据（AST 补正则的漏）
           ├─ S2A 资产与资源（A-O 十五类）
           ├─ S2P 体验参数（七类）
           ├─ S2T 文案与全维度（C1-C12）
           └─ S2B BUG 与审查（简单项当场修）
  ↓
S3 证据与性质判定 → S4 契约与能力包 → S5 择优设计
  ↓
S6 迁移执行 → S7 验证与验收（+ S7V 视觉状态契约）
```

**每阶段有门禁**，`scripts/run_all_gates.py --work work/` 一次跑完。

---

## 三、十四份清单（真正的交付物）

| # | 清单 | 编号 |
|---|---|---|
| 1 | 功能缺口 | 1-N |
| 2 | 体验参数 ⭐ | P-N |
| 3 | 资产与资源 ⭐ | AS-N |
| 4 | 文案 ⭐ | WD-C1-N |
| 5 | 全维度 ⭐ | WD-C2…C12-N |
| 6 | BUG 与审查 ⭐ | B-N |
| 7 | 许可合规 ⭐ | 四态 |
| 8 | 整合机会 + 保留 | I-N / G-N |
| 9 | 反向清单（勿删） | — |
| 10 | 不适用清单 | — |
| 11 | unknown ⭐ | 最高优先级阻塞 |
| 12 | 视觉状态 | `visual/states/*.yaml` |
| 13 | 机器查询命中 | `findings.json` |
| 14 | **功能对照表** ⭐ | 五类处置：原样复刻/优化/架构调整/**需讨论** |
| 15 | **回放与资产**（游戏） | replay_manifest / game_assets |

模板：`assets/清单模板.md` · 对照表专版 `assets/功能对照表模板.md`

---

## 四、脚本速查（129 个 + 9 个工具封装）

| 管什么 | 脚本 |
|---|---|
| **一键全跑** ⭐ | `run_all_gates.py` |
| 台账与门禁 | `ledger.py` · `coverage_gate.py` · `renumber_check.py` |
| **原版取证** ⭐ | `original_capture.py` |
| **参数** ⭐ | `param_extract.py` |
| **资产** ⭐ | `asset_inventory.py` |
| **文案** ⭐ | `text_extract.py` |
| **许可** ⭐ | `license_gate.py` |
| **动效** ⭐ | `motion_check.py` |
| **树对齐** ⭐ | `tree_align.py` |
| **差异归因** ⭐ | `diff_classify.py` |
| **环境锁** ⭐ | `env_lock.py` |
| **差分测试** ⭐ | `diff_fuzz.py` |
| **功能对照表** ⭐ | `feature_matrix.py` |
| **文本排版** ⭐ | `text_layout.py` |
| **故障矩阵** ⭐ | `fault_matrix.py` |
| **安装契约** ⭐ | `install_contract.py` |
| 代码 | `ast_query.py` · `tree_sitter_parse.py` · `brace_check.py` · `comment_extract.py` · `config_field_diff.py` |
| BUG | `bug_triage.py` |
| 跨端 / 视觉 | `cross-end-check.mjs` · `visual_check.py` |

详见 `scripts/README.md`。

---

## 四·补：外部工具封装层（42 个工具已登记）

```
scripts/tool_run.py          调度器：--list / --env / --check / --check-all / --run
scripts/tools/registry.yaml  登记表：repo、许可、安装、身份特征、降级策略
scripts/tools/*.py           9 个封装：harfbuzz·odiff·toxiproxy·kaitai·vmaf
                                      ·gumtree·resvg·ocr·duckdb_evidence
```

> **`which sg` 命中的是 Unix 的 `sg`（set group ID）命令 ——
> 它可执行，但没 `scan` 子命令。只查"命令存在"会得到永远 0 命中却显示成功的假工具。**

身份校验两道：版本特征 + 退出码为 0 + 子命令存在。
缺失时 `required` 进 unknown 阻断、`optional` 标 skipped —— **不得静默跳过**。

---

## 四·补：游戏引擎复刻

> **游戏复刻不是"多一类资源"的桌面迁移，而是把不可见状态变成验收对象。**
> **即使画面相同**，也可能因一帧输入提前、一次浮点舍入、一处碰撞顺序不同而破坏回放。

**三条最硬的**：
1. **确定性是首要约束** —— 首个发散帧比最终画面差异重要一万倍（不能只比最终状态，错误会偶然抵消）
2. **没有软渲染基线就无法区分游戏错误与驱动/GPU 差异** —— "不同 GPU 结果不同很正常"在复刻里是错的
3. **有 savestate API ≠ 有可回滚游戏**（SaveState 只记物理位置速度）

```bash
python3 scripts/game_replay.py --desync --old old.jsonl --new new.jsonl
python3 scripts/game_render.py --baseline baseline.yaml --gate
python3 scripts/game_asset.py --engine
```

工具登记 42 → **66 个**（RenderDoc、GFXReconstruct、PIX、libTAS、BizHawk、GGPO、
Jolt、decomp.me、splat、reccmp、permuter、QuickBMS、AssetRipper、CUE4Parse、
Il2CppDumper、gdsdecomp、UndertaleModTool、vgmstream、SDL、OpenAL Soft…）

**匹配式反编译与本理念天然同源**：三档门禁 exact-match / equivalent /
modern-replacement —— **把第三档伪装成第一档是最危险的冲突**。

---

## 四·再补：运行时取证与 AI 边界（第八轮）

> **缺少运行时取证，所谓"逐文件复刻"会退化为反编译器可读化之后的二次开发。**
> **缺少二进制 diff，就无法回答"原版究竟有多少个行为单元、哪些只名字相似"。**

**行为基元**（最小工作单元不是功能点）：
`输入 / 触发条件 / 内部状态 / 可观察副作用 / 输出 / 时序 / 异常路径 /
**对其他状态的副作用**（最容易漏）`

```bash
python3 scripts/runtime_forensics.py --primitives
python3 scripts/binary_coverage.py --check ledger/binary_coverage.csv --gate
python3 scripts/context_pack.py --gates        # AI 七道强制门
```

**AI 只有提出假设的权限，没有判定完成的权限** ——
七道门：原版侧 · 任务侧（不许让 AI 猜原版实现）· 生成侧 ·
编译侧（**失败日志不得被重新解释为"接近正确"**）· 测试侧 · 复核侧 · 收工侧。

⚠️ **BinDiff 要求 IDA 9.0+，Diaphora 要求 IDA 7.4+ 且是 AGPL-3.0**
—— 不许宣传成零成本开源；ghidriff 才是降低 IDA 依赖的候选。

工具登记 66 → **85 个**（Frida、Qiling、Unicorn、DynamoRIO、bpftrace、
BinDiff、Diaphora、ghidriff、RetDec、angr、Triton、KLEE、repomix、
Zoekt、ctags、Tracy、hyperfine、Wine、DXVK…）

---

## 四·末：原版机制与目标栈（第九轮）

> **XAML 不是"控件和样式"，是五张清单**：属性 / 事件 / 模板 / 资源 / 树结构。

**依赖属性的难点是值优先级链** ——
强制值 > 活动动画 > **局部值（通常高于样式 setter）** > … > 继承 > 默认值。
**改进发生在计算完成后，不是在测量前删除原版能力。**

```bash
python3 scripts/wpf_mechanism.py --precedence      # 优先级链
python3 scripts/wpf_mechanism.py --leak            # WPF 四大泄漏根因
python3 scripts/target_stack.py --tauri            # Tauri 2 迁移事实
python3 scripts/target_stack.py --webview          # 三 WebView 差异
python3 scripts/value_fidelity.py --float --old a.json --new b.json
```

**Tauri 2 不是 Tauri 1 的升级** —— capabilities/ACL 是**默认拒绝**的新边界，
wildcard scope 会被脚本拦截。
**三 WebView 不许共用一套 golden**。
**不能默认 JSON 能无损保真浮点**（须记 `float_format`）。

工具登记 85 → **98 个**（dotnet/diagnostics、PerfView、miri、cargo-deny/nextest/
llvm-cov/geiger、ryu、ICU4X、chrono、vitest、web-vitals、git-cliff…）

---

## 四·终：状态迁移、IPC 与可观测性（第十轮）

> **迁移的失败是静默的** —— 已实证 `clusters` 字段被丢弃：
> 迁移返回成功，用户数据**永久丢失且无提示**。

```bash
python3 scripts/state_migration.py --silent    # 六类静默失败
python3 scripts/state_migration.py --unknown   # 未知字段策略（不许 ignore）
python3 scripts/ipc_surface.py --single-instance
python3 scripts/log_parity.py --drift          # 字段名一致但含义漂移
```

三条硬：
1. 🚫 **未知字段不允许 `ignore` / `default`** —— 只允许 passthrough / canonicalize / archive
2. **DDL 相同 ≠ 数据无损** —— 必须四层对账（catalog/基数/**content**/behavior）
3. **没有 receipt 时新应用不得把状态标为"最新"**

工具登记 98 → **111 个**（atlas、sqldef、refinery、dbmate、interprocess、
tracing-test、tracing-fluent-assertions、OTel semconv、dunce、normpath、trash、
extism、clap…）

---

## 四·续：安全信任、离线与 IME（第十一轮）

> **已有依赖扫描答不了"谁能在哪一步替换可执行体"。**

```bash
python3 scripts/security_trust.py --signing   # 时间戳不是"签一次管永久"
python3 scripts/network_resilience.py --faults # 25 个具名网络故障
python3 scripts/a11y_ime.py --ime             # 中文/日文输入法全事件
```

三条硬：
1. 🔴 **Lifetime Signing OID 会推翻"时间戳后永久有效"** —— 五种状态必测
2. **原版"能离线用"是可用状态机**，不是一句"断网提示用户"
3. 🔴 **IME 验收单位是"可观察状态序"，不是"最终汉字相同"** ——
   目标不得只在单语 Windows 11 默认输入法下通过

工具登记 111 → **118 个**（TUF、cosign、ZAP、Nuclei、NVDA、AccessKit、Fides、comcast…）

---

## 五、按需加载

| 想查什么 | 读哪个 |
|---|---|
| 挖不动了怎么办 | `references/九切角.md` |
| tips 延迟这类参数 | `references/体验参数挖掘.md` |
| 图标/字体/音效/色板 | `references/资产与资源总清单.md` |
| 边界/可访问性/系统整合 | `references/体验维度总清单.md` |
| 怎么驱动原版 WPF | `references/原版取证.md` |
| 差异说不清为什么 | `references/树对齐与差异归因.md` |
| 不知道哪些是隐含规则 | `references/不变量与差分测试.md` |
| 文本/并发/异常/安装 | `references/语义证据层.md` |
| 工具怎么调、签字怎么存 | `references/编排与证据治理.md` |
| 游戏引擎复刻怎么做 | `references/游戏引擎复刻.md` |
| 运行时取证/二进制覆盖/AI 边界 | `references/运行时取证与二进制覆盖.md` |
| 原版机制与目标栈怎么做 | `references/原版机制与目标栈.md` |
| 状态迁移/IPC/日志遥测 | `references/状态迁移与可观测性.md` |
| 安全信任/离线/无障碍与 IME | `references/安全信任与无障碍.md` |
| **跨引擎迁移与二次创作（主场景）** | `references/跨引擎迁移与二次创作.md` |
| 游戏深化（内容/战斗/AI/数值/存档） | `references/游戏引擎复刻.md` 第二部分 |
| 功能表面/版本基准/网络/模组 | `references/游戏引擎复刻.md` 第三部分 |
| 输入延迟/相机/音频/渲染/可玩性 | `references/游戏引擎复刻.md` 第四部分 |
| 编辑器/构建/配置/输入设备/存档链 | `references/游戏引擎复刻.md` 第五部分 |
| 动画/UI/物理参数链 | `references/游戏引擎复刻.md` 第六部分 |
| 流式/并发/热更新/内存/默认值 | `references/游戏引擎复刻.md` 第七部分 |
| 战斗/移动手感·锁定取消·会话·超分 | `references/游戏引擎复刻.md` 第八部分 |
| 时间语义·关卡空间·教程·难度·pacing·AA | `references/游戏引擎复刻.md` 第九部分 |
| 世界模拟·身体状态·社交·元游戏·浮点 | `references/游戏引擎复刻.md` 第十部分 |
| 声音传播·视觉可读性·感知性能·环境交互 | `references/游戏引擎复刻.md` 第十一部分 |
| 任务状态·对话结构·库存手感·配点·死亡流程 | `references/游戏引擎复刻.md` 第十二部分 |
| 战斗规则·BOSS契约·解锁节奏·输入反馈·动作仲裁 | `references/游戏引擎复刻.md` 第十三部分 |
| UI音效·过渡体验·UI动态·镜头叙事·环境叙事 | `references/游戏引擎复刻.md` 第十四部分 |
| 时间推进·动态经济·声望派系·存档兼容·玩法耦合 | `references/游戏引擎复刻.md` 第十五部分 |
| 联机延迟·AI信任·节奏·信息架构·听觉认知·存档心理契约 | `references/游戏引擎复刻.md` 第十六部分 |
| 运气体验·技巧天花板·重复可玩·玩家表达与身份 | `references/游戏引擎复刻.md` 第十七部分 |
| 最坏情况·失败路径·内容冗余·极限边界·等待·一致性 | `references/游戏引擎复刻.md` 第十八部分 |
| 取证顺序·证据仲裁·演进治理·老玩家迁移·自动化预算 | `references/游戏引擎复刻.md` 第十九部分 |
| 可交付性·可观测性·组织协作·终止条件·反脆弱·ROI | `references/游戏引擎复刻.md` 第二十部分 |
| 隐性耦合·资源生命周期·帧时序契约·脚本边界·场景事务 | `references/游戏引擎复刻.md` 第二十一部分 |
| 力反馈·数值多值·输入硬件物理层·AI听觉·云存档·Pass顺序 | `references/游戏引擎复刻.md` 第二十二部分 |
| 程序生成边界·阴影玩法信息·交互反作用力·资源冷却语义 | `references/游戏引擎复刻.md` 第二十三部分 |
| 信任边界·设置契约·帧预算分配·意图层·内容变体·死亡分类 | `references/游戏引擎复刻.md` 第二十四部分 |
| 持久痕迹·通知聚合·加载连续性·非文本本地化·相机四平面 | `references/游戏引擎复刻.md` 第二十五部分 |
| 地形植被·水体水下·布料毛发·反射透明·陀螺仪VR·粒子确定性·响度·预热 | `references/游戏引擎复刻.md` 第二十六部分 |
| 环境耦合·系统健康·可观测性相位·统计竞速·教学/无障碍/模组 | `references/游戏引擎复刻.md` 第二十七部分 |
| 存在感·交互仲裁·可达性·材质等价·音效覆盖·相机·现实时钟 | `references/游戏引擎复刻.md` 第二十八部分 |
| 失败重试循环·刷新节奏·容错撤销·物件复位 | `references/游戏引擎复刻.md` 第二十九部分 |
| 世界一致性·氛围层·同帧事件序·意图边界 | `references/游戏引擎复刻.md` 第三十部分 |
| 分屏共置·多档案·天气季节·小地图空间语义 | `references/游戏引擎复刻.md` 第三十一部分 |
| 交互事务：建造·交易·目标呈现·成长·回放 | `references/游戏引擎复刻.md` 第三十二部分 |
| 玩家认知·可读复杂度·联机契约·非死亡失败 | `references/游戏引擎复刻.md` 第三十三部分 |
| 世界纵深·知识边界·环境叙事·难度维度 | `references/游戏引擎复刻.md` 第三十四部分 |
| 具身表现·物品实体·非语言交互·肌肉记忆 | `references/游戏引擎复刻.md` 第三十五部分 |
| 微观节奏·注意力仲裁·人格语气·边界退化 | `references/游戏引擎复刻.md` 第三十六部分 |
| 可破坏世界·元素连锁·绳索软体·读档重摇 | `references/游戏引擎复刻.md` 第三十七部分 |
| 生活玩法·首次启动·人格化痕迹·叙事接口 | `references/游戏引擎复刻.md` 第三十八部分 |
| 输入载体·UGC创作链·权利账本·数据布局 | `references/游戏引擎复刻.md` 第三十九部分 |
| 声音语义·成长可感·玩家元操作·时间美学 | `references/游戏引擎复刻.md` 第四十部分 |
| 心智地图·决策承诺·长时间漂移·确定性信任 | `references/游戏引擎复刻.md` 第四十一部分 |
| 常识迁移·越界OOB·多感官权威·伪因果·设备漂移 | `references/游戏引擎复刻.md` 第四十二部分 |
| 离开弃坑·第N次·幽灵内容·第一次不可再生 | `references/游戏引擎复刻.md` 第四十三部分 |
| 同形异质·操作方言·意外组合·游戏惯例污染 | `references/游戏引擎复刻.md` 第四十四部分 |
| 教与学·假可玩性·第二职业·版本地层 | `references/游戏引擎复刻.md` 第四十五部分 |
| 外围层·玩家自救·物理外设·游玩环境 | `references/游戏引擎复刻.md` 第四十六部分 |
| 时间预算·拟人化·文化层·元收藏与展示 | `references/游戏引擎复刻.md` 第四十七部分 |
| 沟通元语言·风险账本·行为记忆·工具契约 | `references/游戏引擎复刻.md` 第四十八部分 |
| 非完整版本态·秘籍·旁观者·实体载体 | `references/游戏引擎复刻.md` 第四十九部分 |
| 试玩机·反盗版屏·Credits | `references/游戏引擎复刻.md` 第五十部分 |
| 证据补洞·四路验收接入 | `references/游戏引擎复刻.md` 第五十一部分 |
| 执行层修复（kind/重复 key/汇总诚实化） | `references/游戏引擎复刻.md` 第五十二部分 |
| 四路验收端到端跑通 | `references/游戏引擎复刻.md` 第五十三部分 |
| SPDX 3.0 Build 接入（含三处修正） | `references/游戏引擎复刻.md` 第五十四部分 |
| 真实捕获导入（自测与取证分离） | `references/游戏引擎复刻.md` 第五十五部分 |
| 门禁混沌测试（拦截率 89/101） | `references/游戏引擎复刻.md` 第五十六部分 |
| 毒化覆盖率 87.4%（置信区间） | `references/游戏引擎复刻.md` 第五十七部分 |
| 语义毒化（字段合法 ≠ 行自洽） | `references/游戏引擎复刻.md` 第五十八部分 |
| A 类盲区归零（9→0，拦截率 87→97） | `references/游戏引擎复刻.md` 第五十九部分 |
| 101 项全参与统计 + 门禁自身可信度 | `references/游戏引擎复刻.md` 第六十部分 |
| skip 细分到物种 + 缺数据不得等同通过 | `references/游戏引擎复刻.md` 第六十一部分 |
| 造可毒化输入源 → 拦截率 101/101 | `references/游戏引擎复刻.md` 第六十二部分 |
| 强证据率 89/101（拦截率须分强弱） | `references/游戏引擎复刻.md` 第六十三部分 |
| 强证据 98/101 + 目录完备型上限 | `references/游戏引擎复刻.md` 第六十四部分 |
| 强证据 99/101 + 增量完备性指标 | `references/游戏引擎复刻.md` 第六十五部分 |
| 漏网风险由分类完备性封闭 + 两处自我纠正 | `references/游戏引擎复刻.md` 第六十六部分 |
| 格式错配复核：抓到两个嗅探器互相打架 | `references/游戏引擎复刻.md` 第六十七部分 |
| md 毒化器一直都在（两次误记同源）+ 改瘦模板探针 | `references/游戏引擎复刻.md` 第六十八部分 |
| 合成改瘦：87 个不是盲区而是**分类结论**，覆盖 98/98 | `references/游戏引擎复刻.md` 第六十九部分 |
| hard 门禁**从未执行**却显示成软警告（字符串 tpl 逐字符拆命令） | `references/游戏引擎复刻.md` 第七十一部分 |
| 说明性门禁**归零**：G341 用 `--limit` 快速子集每次真跑 | `references/游戏引擎复刻.md` 第七十二部分 |
| 🔴 上一轮**声称做的三条，代码里一条都没有**（G341 真全量 + G379/G380） | `references/游戏引擎复刻.md` 第七十四部分 |
| 🔑 元规则落地：`claim_verify.py` + G381/G382；🔴 本轮**重复造轮子 + 误报缺陷**的自我纠正 | `references/游戏引擎复刻.md` 第七十五部分（续） |
| 🔑 `absent` 防回退类型 + `--verify-all`（G383）：故意改回 `--limit 20` 实测**会被抓** | `references/游戏引擎复刻.md` 第七十六部分 |
| 🔑 G384 `--check-current`：守「**有没有写清单**」（第七十六轮诚实缺口的落地） | `references/游戏引擎复刻.md` 第七十七部分 |
| 🔑 合并入口 `--all`（G385）+ `DEFAULT_REQUIRE_SINCE` 常量；🔴 代价：**三门禁不再独立** | `references/游戏引擎复刻.md` 第七十八部分 |
| 🔑 G385 解耦：🔴 **前两版解法都无效**（自证循环），第三版改用段体内容特征才真的会响 | `references/游戏引擎复刻.md` 第七十九部分 |
| 🔑 G386 自校验**判据本身**：存在性 + 唯一性两条断言，🔴 **坏尺子拒绝给结论** | `references/游戏引擎复刻.md` 第八十部分 |
| 🔑 G387 区分**刻意重复 vs 误重复**；🔴 第一版按组放行**漏网**，逐个 ID 校验才抓到 | `references/游戏引擎复刻.md` 第八十一部分 |
| 🔑 第八十二轮：登记集合须**等于**实际组（警告→阻断）+ G385 **联动**；🔴 临时编号须登记豁免而非改检查逻辑 | `references/游戏引擎复刻.md` 第八十二部分 |
| 🔑 第八十三轮：`guards` **语义字段**；🔴 四方向破坏实测，**"存在但无关"的 G37 被抓住** | `references/游戏引擎复刻.md` 第八十三部分 |
| 🔑 第八十四轮：**能力自报**；🔑「包含」是被动巧合，「自报」是主动承诺；🔴 两处"检查器自己的 bug" | `references/游戏引擎复刻.md` 第八十四部分 |
| 🔑 第八十五轮：**抽查**（`--probe-capability`）；🔴 只判 rc 会让**空函数**通过，必须判 `PROBE_OK` | `references/游戏引擎复刻.md` 第八十五部分 |
| 🔑 第八十六轮：**外部可观测副作用**；🔑 诚实结论不是免责声明，而是**下一轮的规格说明** | `references/游戏引擎复刻.md` 第八十六部分 |
| 🔑 第八十七轮：**文件系统产物**；🔴 快照在运行后取 → 探针**静默失效却不报错** | `references/游戏引擎复刻.md` 第八十七部分 |
| 🔑 第八十八轮：**产物内容 vs 独立真值**；🔑 产物可能"写对形状却写错值" | `references/游戏引擎复刻.md` 第八十八部分 |
| 🔑 第八十九轮：**跨进程真值**；🔴 只隔离入口路径**不隔离代码**；rc 合法域仅 {0,1} | `references/游戏引擎复刻.md` 第八十九部分 |
| 🔑 第九十轮：能力框架推广到**第二个能力** `chaos-full`；🔑 下界断言：**量级**而非形状 | `references/游戏引擎复刻.md` 第九十部分 |
| 🔑 第九十一轮：**外部锚点下界**；🔑 基线被污染为 1 时，锚点仍把下界拉回 76 | `references/游戏引擎复刻.md` 第九十一部分 |
| 🔑 第九十二轮：锚点分母改**台账型**；🔑 误杀实测：旧口径锚点 187 误杀真值 101，新口径正常 | `references/游戏引擎复刻.md` 第九十二部分 |
| 🔑 第九十三轮：rc 合法域**合并为单一常量** `GATE_RC_DOMAIN`；🔴 常量改成 (9,9) 也能被发现 | `references/游戏引擎复刻.md` 第九十三部分 |
| 🔑 第九十四轮：G388 扫全 130 个脚本，**立刻抓到真实第二处** `ast_query.py:83`（语义不同，登记豁免） | `references/游戏引擎复刻.md` 第九十四部分 |
| 🔑 第九十五轮：豁免清单**外部化**到 `ledger/`；🔴 文件读不到时拒绝给结论（不静默当"没有豁免"） | `references/游戏引擎复刻.md` 第九十五部分 |
| 🔑 第九十六轮：G389 守**豁免清单本身**（批准轮次/僵尸豁免）；🔑 仓库已建并全量同步（262 文件） | `references/游戏引擎复刻.md` 第九十六部分 |
| 🔑 第九十七轮：G390 **推送不得静默漏传**（未 add 即拒绝）；🔴 git 不可用 ≠ 没有漏传 | `references/游戏引擎复刻.md` 第九十七部分 |
| 🔑 第九十八轮：G391 **推送完整性回读验证**（逐条比对 blob sha）；🔴 门禁自身写缓存 → 只能人工/推送后执行 | `references/游戏引擎复刻.md` 第九十八部分 |
| 🔑 第九十九轮：第④层**权限比对** + `--report` 复核入口；🔴 曾把 266 文件全推成 100755（mode 须取自 git 索引） | `references/游戏引擎复刻.md` 第九十九部分 |
| 🔑 第一百轮：G393 **symlink 处理自测**（mode 120000）；🔴 自测曾复刻被测逻辑 → 回退也测不出 | `references/游戏引擎复刻.md` 第一百部分 |
| 🔑 第一百零一轮：G394 **历史权限审计**（🔴 5 个 commit 遗留 100755，未改写）+ G395 gitlink（160000）；🔴 有 submodule 时旧流程整个仓库推不出去 | `references/游戏引擎复刻.md` 第一百零一部分 |
| 🔑 第一百零二轮：G396 **遗留台账可断言化**；🔑 审计不自行阻断，另设断言门禁；🔴 改脚本时 assert 失败却误以为改完 | `references/游戏引擎复刻.md` 第一百零二部分 |
| 🔑 第一百零三轮：G397 **文件级遗留断言**；🔑 实测证明「数量对但文件变了」只有指纹能抓到；幂等写入解决时间戳抖动 | `references/游戏引擎复刻.md` 第一百零三部分 |
| 🔑 第一百零四轮：G398 **完整清单落盘，离线可答**；🔑 真断网验证（G398 绿 / G396·G397 拒绝给结论）；🔴 修 `req()` 只捕 HTTPError 导致断网崩溃 | `references/游戏引擎复刻.md` 第一百零四部分 |
| 🔑 元规则：**完成声明须回读代码核实**（`claim_verify.py`，G381） | `references/游戏引擎复刻.md` 第七十五部分 |
| 许可与 SBOM | `references/许可与依赖治理.md` |
| 证据可信度 | `references/证据等级.md` |
| 该保留还是替换 | `references/性质判定与动作.md` |
| 截图总不稳定 | `references/视觉稳定化.md` |
| 哪些做法不能要 | `references/负面教训库.md` |

---

## 六、未启用区

`_inactive/`（agents 与 rules 草案）**当前不参与主流程**。
原因是主流程单人也能跑通，且多 agent 不天然更准。
启用条件见 `_inactive/README.md`。

---

## 七、最容易被忽略的三句话

1. **功能全对但参数全丢，用户的感受就是"说不出哪里不对"。**
2. **可以不照搬，但必须知道搬前是什么样。**
3. **收工不由模型自述决定** —— 由脚本统计与人工签字共同决定。
