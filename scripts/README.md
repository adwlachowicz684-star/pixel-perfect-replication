# scripts · 可执行检查

> **原则**：确定性强、重复劳动、需要零上下文执行的操作，一律下沉为脚本。
> 让模型"检查是否一致"不可靠，让脚本检查才可靠。

---

## 清单

| 脚本 | 阶段 | 作用 | 关键陷阱 |
|---|---|---|---|
| `ledger.py` | S1/S2 | 文件台账：入账 / 未读 / 按档位 / 清零率 / 门禁 G1 | 必须按档位走完，不许只按行数倒序 |
| `coverage_gate.py` | S2-S7 | 覆盖率与 unknown 门禁 G2（unknown>0 阻塞） | 阻塞收工的唯一硬指标 |
| `renumber_check.py` | S2-S7 | 编号重复与缺号自检 | 索引里要写 `\| 123 \|` 而非 `#123` |
| `brace_check.py` | S6 | 括号平衡（含 Rust lifetime 陷阱）/ diff 新增行 / 基线对比 | `'a` 不是 char 字面量 |
| `comment_extract.py` | S2 | 提取 `//` 行内注释并标注所属方法（含负面教训词过滤） | `//` 比 `///` 值钱十倍 |
| `config_field_diff.py` | S2 | config/DTO 字段双向差集 + JSON 真实数据比对 | grep 单行会漏带泛型的字段 |
| `cross-end-check.mjs` | S4/S6/S7 | 跨端 C1-C4 四类检查 | `[^}]*` 会提前截断 |
| `bug_triage.py` | S2B-S7 | BUG 分诊与门禁：P0/P1 未处置阻塞、B5 存疑阻塞、简单项未修警告、B1 未登记行为变更警告 | B5 未确认等同 unknown |
| `tree_sitter_parse.py` | S2M | 全量源码可解析性（L1）；无 tree-sitter 时降级粗判并标 low | 解析失败不许自动关闭 unknown |
| `ast_query.py` | S2M | AST 精确查询（L2）；ast-grep 缺失时**如实降级**并标 low | ⚠️ `which sg` 会命中 Unix 的 set-group 命令 |
| **`run_all_gates.py`** | 全部 | **一键跑完所有可自动判定的门禁**，统一输出通过/阻断，并列出人工门禁 | 自动全绿 ≠ 可以收工 |
| `visual_check.py` | S7V | 视觉状态契约校验：必锁项 / 遮罩 reason / 阈值 reason / 语义等待 / 审批签字 / bulk approve | 只校验契约，**不做截图** |
| `param_extract.py` | S2P | 体验参数提取 + 双侧差集：时序/阈值/尺寸/动画/颜色/字体/层级 | ⚠️ XAML「左上右下」vs CSS「上右下左」，顺序不能照抄 |
| `asset_inventory.py` | S2A | 资产清点：资源清单 + **孤儿资源** + **悬空引用** + 许可待确认列表 | 孤儿**不许默认当残留**（动态拼接路径 grep 不到） |
| `text_extract.py` | S2T | 文案提取 + 差集：XAML 属性 / 提示调用 / CJK 字面量，识别**疑似改写** | 用序列相似度而非字符集合（同义词替换集合法会漏） |
| `original_capture.py` | S0 | 原版取证：控件树 + 三原语截图 + 环境契约（11 项未填则**阻塞采集**） | 非 Windows 如实降级为"待人工采集"，不假装成功 |
| `license_gate.py` | S2A/S7 | 许可四态门禁：allowed / restricted / unknown_evidence / not_applicable | 后两者**阻断交付**；字体需逐项确认嵌入/再分发/子集 |
| `motion_check.py` | S7V | 动效门禁：录屏抽帧分析时序，新旧比对（25% 容差） | ⚠️ **不能据此断言缓动曲线** |
| `tree_align.py` | S2M/S3 | UI 树对齐：原版 UIA ↔ 新版可访问性树，四级对齐（L1 锚点→L4 APTED） | **不能只依赖 role**；超预算降级，**不伪造精确映射** |
| `diff_classify.py` | S7V | 差异归因：像素差 → 十类根因（平移/缩放/缺失/结构变化…） | 缺依赖不假装分析；`unknown`/`structural` 须人工复核 |
| `env_lock.py` | S0/S7 | 环境锁 15 项（渲染敏感 7 项）；**不一致直接 FAIL**，`unknown` ≠ 已锁定 | 弱版本：不要求 bit-for-bit（MSVC/Rust 未承诺） |
| `diff_fuzz.py` | S6/S7 | 差分测试 + 四类 oracle 分类；**原版自己当 oracle** | 用行为距离选种非覆盖率；**不许改 oracle 让它通过** |
| `feature_matrix.py` | S3/S5/S7 | 功能对照表：五类处置校验 + 与台账**双向对账** | 「需讨论」缺四栏阻断；`原版✅新版❌`却标完成是危险组合 |
| `text_layout.py` | S2T/S7 | 文本排版金标准：NFC/NFKC/Bidi/断行/排序五维比对 | 缺依赖**如实降级**，不用截图代替；未定项不许结案 |
| `fault_matrix.py` | S6/S7 | 故障行为矩阵：26 类故障 × 六栏；**原版行为未采集即阻断** | 「没有崩溃」≠「韧性等价」 |
| `install_contract.py` | S2/S6 | 安装契约 13 字段 + 残留 13 处 owner | 平滑升级核心是残留矩阵，不是"能下载新包" |
| **`tool_run.py`** | 全程 | **外部工具调度器**：登记/身份校验/能力矩阵/调用 | ⚠️ 身份两道校验，防「同名不同工具」 |
| **`game_replay.py`** | 游戏 | 确定性回放 manifest + **desync 定位**（首个发散帧+子系统） | 不能只比最终状态（错误会偶然抵消） |
| **`game_render.py`** | 游戏 | 渲染取证基线校验 + 帧哈希；抓 JPEG/DLSS/动态分辨率污染 | 无软渲染基线就无法区分游戏错误与 GPU 差异 |
| **`game_asset.py`** | 游戏 | 资产取证 17 字段 + 引擎工具映射 + 结构等价清单 | 门禁是结构等价，不是"导入成功" |
| **`runtime_forensics.py`** | 全程 | 运行时取证台账：行为基元八要素 + 15 字段探针 | **Hook 数据 ≠ 语义事实**；不得改状态后声称观察原版 |
| **`binary_coverage.py`** | 全程 | 二进制函数覆盖：unmatched_primary / 低置信复核 | **禁止把自动映射直接写入规范** |
| **`context_pack.py`** | 全程 | 上下文打包 + 密钥扫描 + **AI 变更人工签名门禁** | AI **只有提出假设的权限**，无收工资格 |
| **`wpf_mechanism.py`** | 桌面原版 | WPF/.NET/Win32 机制 31 条 + 值优先级链 + 四大泄漏 | 验收须**可判定布尔条件**；resize 差异先跑约束传播探针 |
| **`target_stack.py`** | 新栈 | Tauri 2 迁移事实 / IPC 三语义 / 三 WebView / React / Rust | **三 WebView 不许共用 golden** |
| **`value_fidelity.py`** | 全程 | 浮点往返 / 编码 / 文化格式化 / 规范化 diff | **不能默认 JSON 无损保真** |
| **`state_migration.py`** | 迁移 | 迁移字段矩阵 + 六类静默失败 + 未知策略 + 路径陷阱 | 🚫 **不许 ignore**；DDL 相同 ≠ 数据无损 |
| **`ipc_surface.py`** | 集成 | IPC 契约 14 字段 + 单实例会话身份 + Shell 取证 | **功能通了 ≠ 语义对等**；改 framing 即不对等 |
| **`log_parity.py`** | 可观测 | 遥测契约 + 字段含义漂移 + 三层断言 + 崩溃五组 | **PII 须在进入遥测前分类**；重放/崩溃不得被采样 |
| **`security_trust.py`** | 安全 | 签名生命周期 / TUF / WebView ACL / 凭据 / 沙箱 | **每个 capability 要有负向拒绝路径**；无能力时禁用而非静默成功 |
| **`network_resilience.py`** | 网络 | 四层检测 + 25 故障 + 企业代理 + 幂等重试 | **离线是可用状态机**，不是一句错误提示 |
| **`a11y_ime.py`** | 无障碍 | NVDA 朗读事件序 / AccessKit 树 / **IME 全事件** | **「aria 无错」≠完成；「最终汉字相同」≠完成** |
| **`engine_migration.py`** ⭐ | **主场景** | **跨引擎迁移**：坐标系/概念映射/资产/着色器/物理/动画 + 二次创作四分类 | **must-match 不许以「新引擎更好」为由改** |
| **`game_content.py`** | 游戏 | 关卡实体/触发器/生成点/**隐藏内容**/流式/过场/**调试功能** | **画面相似 ≠ 内容相同**；隐藏内容最易静默丢失 |
| **`game_combat_ai.py`** | 游戏 | 帧数据 /**判定盒每帧多重集合** / 输入 / AI 状态转移 / 寻路 / 感知 | **先锁输入→再锁时间→最后观察判定** |
| **`game_rng_save.py`** | 游戏 | RNG 三合一 / 掉落统计 / 经济 / 存档六分类 / 成就 | **未知存档字段不得丢弃**；统计检验只是辅助 |
| **`game_surface.py`** | 游戏 | 首次启动 / **UI 状态恢复** / **输入提示图标切换** / 失焦 / 本地化 / 环境 / 元游戏 | **外围不是 polish，是 must-match** |
| **`game_net_mod.py`** | 游戏 | **版本基准指纹** / 补丁三类 / 五种同步 / 网络气象 / 失败注入 / 模组 API / 平台 | **GGPO 不是整个网络层**；服务器权威须注入证明 |
| **`game_latency_camera.py`** | 游戏 | **输入到光子九段链路** / **DXGI 三帧队列** / 相机八子系统 / 震屏 / FoV / 第一人称 | **只测 FPS 会漏掉延迟**；逻辑未变手感已变 |
| **`game_audio_render.py`** | 游戏 | 音频五层 / 动态音乐 / 空间 / 混音 / 语音 / 光照四联 / 剔除 / 后处理 / 画质档 / 可玩性 / PCG | **戴上耳机才发现的错**；**Bot 通关 ≠ 体验一致** |
| **`game_editor_data.py`** | 游戏 | 编辑器六清单 / **导入设置** / 构建七段 / 热重载四类 / 配置 schema / 魔法数 / **buff 叠加** / 数值管道 | **资产不是"有没有"是"如何解释"**；**数值并非天然外置** |
| **`game_input_ops.py`** | 游戏 | **鼠标指针加速** / **扫描码 vs 布局** / **手柄三个死区** / 触摸陀螺仪 / 存档迁移链 / 运营时间 / voice stealing | **KeyW 不许写死扫描码**；存档是**迁移链** |
| **`game_animation.py`** | 游戏 | 状态机中断 / 混合树归一化 / **根运动按源权重** / 重定向 / IK / **末端误差** / 事件触发权重 / 面部 / ragdoll | **平均误差会藏住手脚武器的错误** |
| **`game_ui_physics.py`** | 游戏 | **布局四层链** / HarfBuzz 整形 / **导航是显式图** / 滚动五系统 / **碰撞层矩阵** / 合并模式 / 接触偏移 / CCD / 子步 | **漏一层就穿墙**；导航不是"自动找最近" |
| **`game_stream_thread.py`** | 游戏 | **流式七态** / **hysteresis 迟滞环** / 同步门 / **大坐标精度** / 线程归属 / **容器迭代顺序契约** | **崩溃只在接近边界时出现**；Job 不保证顺序 |
| **`game_hotfix_mem.py`** | 游戏 | **热更新八态** / 依赖图 / 稳定 ID 与引用修复 / **每帧分配与 GC** / 快照五点 / **引擎隐藏默认值** | **差异最大的是另外 90% 未配置默认值** |
| **`game_feel.py`** | 游戏 | 🔴 **顿帧冻结域** / 闪白 / 霸体四类 / 伤害数字聚合 / **coyote / 跳跃缓冲 / 可变跳跃三类** / 地面八态 / 载具 | **冻结谁比冻结多久更重要**；**须在 30/60/120Hz 都测** |
| **`game_session.py`** | 游戏 | 锁定四表 / 软锁定 / 取消窗口 / 方向序列 / **会话状态恢复** / 潜行 / **粒子池耗尽** / **超分帧生成** / HDR | **帧生成插合成帧**；粒子池改变战斗可读性 |
| **`game_time_pacing.py`** | 游戏 | 🔴 **时间域与暂停掩码** / 计时器五字段 / **乘法链 vs 覆盖链** / 慢动作采样率 / pacing / 刷新率 / **AA 画面合同** | **scale=0.5 与 scale*=0.5 不是同义** |
| **`game_level_balance.py`** | 游戏 | 🔴 **关卡八维度** / 视觉引导四级 / **隐形墙五语义** / 教程五状态 / **难度关系网** / **DDA 四类** / 存档六态 | **能走通≠可读**；**原作无 DDA 不得加入** |
| **`game_world_body.py`** | 游戏 | 🔴 **离线推进六层** / NPC 日程 / 生态角色 / **部位伤害四时间表** / **负重舍入** / 外观持久化 | **分段压缩率是 must-match 曲线** |
| **`game_social_meta.py`** | 游戏 | 🔴 **ping 聚合与消失** / 队伍状态机 / UGC 三表 / **周目三表** / **同帧仲裁** / **确认框默认值** / **浮点矩阵** | **差异不在有没有 ping**；**不能只靠固定种子** |
| **`game_audio_read.py`** | 游戏 | 🔴 **七条传播通道** / 距离衰减 / 遮挡分通道 / **混响区过渡** / 多普勒介质 / **voice 抢占事件流** / **可读性采样** | **听不见 ≠ 静音**；**混响区是声音版隐形墙** |
| **`game_perf_interact.py`** | 游戏 | 🔴 **端到端延迟分段** / 抖动 vs 平均低帧 / **门可否中途取消** / 拾取 / 可破坏 / **载具操作反馈** / **拍照冻结什么** | **不搬阈值常数**；**门中断是独立状态机** |
| **`game_quest_dialog.py`** | 游戏 | 🔴 **任务十一状态** / 目标八字段 / **自动完成 vs 手动交付** / **对话图** / **跳过六级** / 唇形按 cue | **expired ≠ failed**；**只跳字幕会漏奖励** |
| **`game_inventory_flow.py`** | 游戏 | 🔴 **四种背包模型** / 满包行为 / **稳定排序键** / 拖拽状态机 / **配点四事务** / **快速旅行推进世界** | **刷新导致跳格也是 BUG**；**重生是显式事务** |
| **`game_combat_rules.py`** | 游戏 | 🔴 **伤害五管线** / 舍入位置 / **DOT 快照** / **免疫五语义** / **BOSS 阶段锁血回血** / 招式分布 | **保底 1 的位置决定少扣还是回血** |
| **`game_progress_input.py`** | 游戏 | 🔴 **能力门动作闭包** / 硬锁软锁 / **按动作分类输入反馈** / 帧率反例 / **动作仲裁层** | **手感是可量化区间**；**输入丢失可能是仲裁** |
| **`game_ui_sound_transition.py`** | 游戏 | 🔴 **同帧多音仲裁** / hover_repeat 分离 / ducking 呼吸感 / **过渡十阶段** / 输入五决策 | **播放被拒 ≠ 事件被消费**；**等 committed 才读会明显变钝** |
| **`game_ui_motion_camera.py`** | 游戏 | 🔴 **数字滚动中断** / 假进度 vs 真实 / 缓动数学规格 / **镜头控制权五元组** / **故意沉默** | **重启策略让数字追不上真实值**；**归还不吸附→准星偏** |
| **`game_world_economy.py`** | 游戏 | 🔴 **时间分钟基** / 暂停白名单 / **跳跃是批量模拟** / **价格冲击链** / 市场恢复 / 多货币兑换 | **没有恢复就写 recovery: none**；**睡眠不能只做时间加法** |
| **`game_faction_save.py`** | 游戏 | 🔴 **声望看见vs生效** / 零和vs累加 / **存档双向迁移** / **损坏四步** / **光照玩法阈值** | **禁止默认零值补齐**；**损坏不得清空进度** |
| **`game_netfeel_ai_trust.py`** | 游戏 | 🔴 **回溯按武器分别记录** / **外推才制造滑步** / 延迟不对称矩阵 / **AI意图互补通道** / 公平感信息对称 / 群体排队 | **判定对象是玩家眼里的因果**；**黑箱模型不得当真值** |
| **`game_pacing_info.py`** | 游戏 | 🔴 **节奏是时间函数** / 关卡时间≠战斗时间 / 补给是风险曲线 / 呼吸空间要有功能 / **信息架构四层** / 声音辨识度可测 / 存档心理契约 | **只按逻辑时间评价节奏会低估死亡重试疲劳** |
| **`game_luck_skill.py`** | 游戏 | 🔴 **保底六种语义** / **险胜谁获得戏剧性** / streak 边界 / 结果可回看 / **技巧帧基准** / **30-144Hz 扫描** / bug变feature | **演出后才回滚保底立即损害可信度**；**GPU trace 不能替代逻辑重放** |
| **`game_replay_identity.py`** | 游戏 | 🔴 **随机十层** / **NG+ 是跨周目契约** / 只存部件不存层级会改旧存档 / **展示场景是系统状态** / UGC 契约 / **故意不告知要建模** | **沉默是设计选择，不是取证遗漏** |
| **`game_degrade_fail.py`** | 游戏 | 🔴 **先砍什么=收益×玩法权重** / 升级滞回 / 硬件能力档映射 / 卡顿十类 / **失败六种语义** / **卡住系统检测** | **画质档不是视觉配置，是规则档**；**失败不是错误码，是可恢复状态** |
| **`game_content_limit.py`** | 游戏 | 🔴 **重复不是冗余，删除结果才是** / 变体轴 / 填充物双证据 / **极限四维组合** / 溢出策略 / **诚实进度** / 撤销分级 / **同义证明** | **只测单值上限会漏掉组合边界**；**进度停止会被理解为卡死** |
| **`game_evidence_chain.py`** | 游戏 | 🔴 **四层证据链** / 取证顺序（依赖而非文件类型）/ 风险驱动停止规则 / **证据八级** / 原版不一致三分类 / 无法复现 / bug-or-design 四门槛 / **偏离许可契约** | **反编译是推测实现，原版测量是真实行为**；**禁止 not_a_bug 兜底** |
| **`game_migration_govern.py`** | 游戏 | 🔴 **三棵树物理分离** / 原版更新兼容窗口 / **迁移四表不能合并** / `preserve_unknown` / **双轨三态承诺** / **自动化四档** / 假阳性降噪 / 测试账本 | **复刻不是终点，是长期分支**；**78 个脚本跑不完 = 没跑** |
| **`game_delivery_observe.py`** | 游戏 | 🔴 **交付清单五问** / 构建可复现三级 / **首启契约** / 卸载七类文件 / **自检五态** / **最后一帧环形缓冲** / 版本可识别性 | **做完了但装不上 = 没做完**；**单一崩溃堆栈不足以复现时间轴问题** |
| **`game_team_release.py`** | 游戏 | 🔴 **所有权矩阵 / 双向交接** / 进度按证据闭环 / **发布就绪六门槛** / "够好"是提高偏离成本 / **预算闸门** / 混沌验证门禁 / ROI | **用"差不多了"替代硬门槛会把风险推给玩家**；**82 个门禁可能全是假的** |
| **`game_sim_resource.py`** | 游戏 | 🔴 **驱动权表**（唯一 writer + reader 读哪一帧）/ 布娃娃·IK·根运动分别登记 / **碰撞音是物理事件还是动画事件** / 资源身份六种 / 池化是身份第三种语义 | **换引擎后漂移的是所有权，不是质量设置**；**仅比较指针会漏掉内容更新与复用** |
| **`game_frame_script.py`** | 游戏 | 🔴 **一帧九阶段** / **延迟一帧五方向** / 事件队列消费时机 / **异常四态** / 热重载四语义 / **场景是加载事务** / 调试 HUD 绑主循环阶段 | **延迟一帧必须说明是设计/优化/偏离，不能当原因**；**脚本抛错只打日志不可接受** |
| **`game_haptics_numbers.py`** | 游戏 | 🔴 **触觉是输出波形非强度** / **左右马达频段分工** / 自适应扳机是状态机 / 关闭震动的**信息补偿** / **数值五值分离** / 取整位置归属 / 百分比六量 / **阈值绑定数值版本** | **两马达压一条曲线 = 材质消失**；**显示错误是规则错误** |
| **`game_input_percept.py`** | 游戏 | 🔴 **输入从"键按下"下钻到设备事件** / 轮询率拍频 / LOD / 直线修正 / **NKRO 是关卡门** / **AI 听觉先证存在** / 诱饵是输入装置 / **云存档时钟不能排序** / Pass 顺序 / 模态栈 | **原版没有听觉就不许补**；**时间戳只能审计** |
| **`game_gen_shadow.py`** | 游戏 | 🔴 **生成六层** / 输入闭包 / **部分重算≠LOD** / **生成失败四结果** / 生成版本 / **shadow_authority 五档** / 影子先于身体 / **接触阴影是接地感** / 画质三档 | **"随机种子即确定性"是冲突**；**低配关阴影 = 关机制** |
| **`game_force_resource.py`** | 游戏 | 🔴 **"推不动"五态** / 重量感五通道 / 可推性状态机 / 门中途取消 / **资源五层** / **冷却起点八候选** / 四时钟 / **差一点舍入+溢出六义** / **过场阶段书签** / 伙伴更聪明是偏离 / 软性禁止六种 | **物理正确≠手感正确**；**"动画结束才冷却"与"按下即冷却"数值相同也差节奏** |
| **`game_trust_settings.py`** | 游戏 | 🔴 **client_claim_facts 事实表** / 服务端写"接受条件" / **三套信任拓扑** / 回滚分层 / **命中四事件** / 设置六类副作用 / **五义默认值** / 迁移与"未保存" | **视觉先显示命中不构成权威事实**；**只写 default: true 无法解释恢复哪一个默认** |
| **`game_budget_intent.py`** | 游戏 | 🔴 **帧预算硬/弹性/借还** / 跨系统资源仲裁器 / 帧报告 16 项 / **意图层五层与稳定排序键** / 设备等价但语音眼动是候选 / **生命周期九态** / 内容变体 / **死亡四类** | **平均帧率相同分配不同=手感不同**；**不能把设备上报顺序当仲裁结果** |
| **`game_trace_notify.py`** | 游戏 | 🔴 **痕迹八组** / **痕迹预算是玩法参数** / **读档四答案** / 痕迹×生成世界双重身份 / 通知**事实层与表现层分离** / **四把合并键** / 优先级双值 / 溢出八策略 / 消息疲劳 | **渲染代理可消失，"血迹曾在此"的事实不能消失**；**不能默认统一成一个 toast** |
| **`game_load_locale.py`** | 游戏 | 🔴 **加载八域连续契约** / **非文本本地化 locale_version** / 口型不是表情 / 音频六件事 / 文化适配 / **BiDi 不是镜像** / 字体回退 / 槽位契约 / **成就四层** / **相机四个面** | **undefined 就是 bug**；**看见/命中/IK/声音遮挡可能是四个不同代理** |
| **`game_terrain_water.py`** | 游戏 | 🔴 **地形采样与精度** / **LOD 呼吸测试** / 材质混合权重≠地表语义 / **植被渲染/碰撞/玩法三实例** / **植被稳定性≠数量** / `surface_footprint` / **水体三模型** / **水下状态机** / 浮力 / 雨雪积水 | **改植被密度即移动潜行边界**；**水下不是摄像机加蓝雾** |
| **`game_cloth_reflect.py`** | 游戏 | 🔴 **布料三拓扑** / **布料玩法事实字段** / 毛发四模型 / 次级动画 / **反射四方案** / **透明六字段** / 镜中玩家存在感 / 陀螺仪 / **VR comfort** / **粒子确定性** / **响度四把表** / **着色器预热** | **镜中看不到身后敌人 = 偏离**；**"同 seed 同结果"非天然属性**；**"异步编译可接受"是最危险冲突** |
| **`game_coupling_health.py`** | 游戏 | 🔴 **风场相位是否同源** / 耦合矩阵权威量 / 八组组合用例 / **系统健康十一检测项** / 阈值来源六者 / **健康状态机五态** / **A/A 自测** / 六个人口点 / **可观测性相位化** | **各系统各自正确 ≠ 组合正确**；**threshold_source=engine default 应拒绝**；**晚一帧是伪 bug 来源** |
| **`game_stats_runs.py`** | 游戏 | 🔴 **统计逐项口径** / 画像事实表 / **回放四层** / 分享导出时世界 / **RTA/IGT 竞速契约** / **教学强制边界** / **无障碍替代三语义** / 模组顺序与冲突四层 / H1 意图谱系 / H2 版本锁定 | **统计/竞速是功能契约不是边缘菜单**；**只提供开关不提供替代 = 信息丢失** |
| **`game_presence_interact.py`** | 游戏 | 🔴 **存在感与责任边界** / **能否挤过三态** / **同伴五事实**（挡枪·误伤·占位·卡门·抢路）/ **注视是状态机输出** / **密度预算是玩法预算** / 触发几何与状态交集 / **并发稳定排序键** / 对话六态 | **"能否挤过"是多帧推力结果**；**"低优先级角色停止碰撞"会消灭卡门与挡枪**；**禁止只按"最近"仲裁** |
| **`game_reach_material.py`** | 游戏 | 🔴 **可达性两阶段** / 能力**逐参数** / 捷径证据八级 / 卡点可判定输出 / **BRDF 可复现样本** / 工作流损失映射 / **色调映射是可测试函数** / 等价四层 / **音效事件覆盖审计** / 同帧重复 / 相机漂移 / 现实时钟五层 | **新 A* 可能双向判错**；**MaterialX/OpenPBR 不是转换器**；**"找不到文件就什么都不播"是静默丢失** |
| **`game_retry_spawn.py`** | 游戏 | 🔴 **失败十相位** / **控制归还 ≠ 设备重连** / 重试**起手差异表** / **「再来一次」六字段** / Boss 重试 / 连续失败 12 维度 / **生成点最小字段集** / 距离五种子 / 刷新可见性 / 资源再生三套触发 / 随机遭遇防连续保护 / H 类八盲区 | **死一次要等多久决定玩家是否继续玩**；**刷新改变的是压力曲线** |
| **`game_fault_reset.py`** | 游戏 | 🔑 确认对话框**语义与焦点** / **撤销窗口是延迟提交** / 误触保护解耦 / **存档覆盖最高风险** / **物件状态四层** / 对象状态 21 项 / 复位触发 11 种 / **已探索 vs 已互动两种持久性** / 可破坏物七种重建 / 持久化绑定版本 / EFG 补充 | **"开过的箱子又合上了"是经典体验破坏**；**默认"确定"奖励连按** |
| **`game_continuity.py`** | 游戏 | 🔴 **存档六类状态分类器** / 冻结点字段 / 读档六步 / 飞行投射物不能自动判 bug / **氛围层取证模板与测量法** / **同帧四种时钟** / 事件稳定排序键四阶段 / **"最后一下"数值 vs 演出** / **意图边界矩阵 13 边界** / 连招缓冲状态机 / HUD 双时钟 | **本轮交付「可验证缺口」而非虚构清单**；**序列化≠快照 · 发声≠持久化 · 同帧≠同序 · pressed≠意图有效** |
| **`game_colo_weather.py`** | 游戏 | 🔑 **分屏六层"同一帧"** / **视口拓扑状态机** / **垂直分屏改变水平 FOV** / **每视口独立预算** / 分屏渲染顺序 / **音频监听拓扑** / 输入与 HUD 持久绑定 / 拓扑重排事务 / **档案七类隔离域** / 切换六状态 / 删除六问 / **天气两层状态机** / **玩法耦合事件契约（雨熄火·潮湿导电）** / 室内外局部状态机 / **小地图两套坐标与更新相位** / EFG 补充 | **共置·归属·空间语义：按谁的坐标、谁的预算、谁的权限**；**分屏样本多是小游戏，天气多是模组，只能吸收算法与字段** |
| **`game_txn_contract.py`** | 游戏 | 🔑 **交互事务六类副作用** / **建造吸附只是提示、合法性才是门槛** / **放置五种否决** / 撤销按副作用分组 / **交易预览是可审计净变化** / **确认≠锁定** / 批量是舍入问题 / 买回窗口 / 零钱非展示层 / **目标三视图与未探索区可见性** / 路径是轮询查询 / **成长逐区间** / 卡关补偿是隐式设计 / **洗点状态残留** / **满级溢出** / **回放事实 vs 像素三种模型** / 导出 HUD·分轨·隐私 | **工具解决"怎样实现"，原版测量解决"实现成什么"** |
| **`game_cognitive_social.py`** | 游戏 | 🔑 **认知四层分流（对齐真相还是体验）** / **共识误解七字段** / 故意误导最小感知条件 / 实测真相 vs 玩家体验三例 / **高亮两条渲染路径（描边误做后处理＝高频失真源）** / 扫描模式是否改判定 / **邀请 9 态 FSM** / **踢出与退出是两个状态机** / **中途加入 8 子集** / 掉落分配 / **队友伤害"允许但有代价"** / 聊天"存在 vs 谁可见"双字段 / **非死亡失败 8 类** / **确认时刻 5 候选帧** / 预警是独立子系统 / EFG / H 十二项 | **催生玩家行为的误解＝玩法事实**；**Nakama 只解决"怎么发消息"，不解决"契约是什么"** |
| **`game_depth_difficulty.py`** | 游戏 | 🔑 **世界历史三层证据** / **visibility_scope 七级** / 🔴 **"剧情上应该记得"不能推断代码会记住** / **先例是访问计数不是布尔** / **知识四层边界（角色/玩家/系统/元）** / **地标五显著性** / 区域六签名 / **难度八维** / **中途调整七语义** / **等待十二事实与原子性** / 收集遗漏语义 / **涌现最小复现链** / H 十项 | **先证明原版行为，再决定实现**；**等待做成快速黑屏＝偏离而非现代化** |
| **`game_embodied_input.py`** | 游戏 | 🔑 **状态外显八字段（第一项不是颜色而是通道）** / **多状态叠加矩阵** / 恢复过程有可玩性 / **物品四段生命周期（held/worn/switched/world）** / **耐久是视觉可读性问题** / 装备切换是输入—动作契约 / **非语言六字段** / 🔴 **沉默必须进选项表** / 注视与距离是触发条件 / **肌肉记忆六时序表** / Unity started/performed/canceled / **声像冲突仲裁** / 非死亡时间损失 / **多人距离带成环** | **只迁移属性/背包/技能树：数值对但"不像原版"**；**统一互动半径＝抹平社交距离** |
| **`game_micro_rhythm.py`** | 游戏 | 🔑 **帧语义六问（sample→commit→resolve→event→visible→perceptual）** / 十二通道 / **微停顿逐项记录** / 🔴 **帧生成帧不得冒充原生帧** / **接缝四输出（不是动画混合权重）** / **注意力仲裁七字段** / **新增弹窗＝修改注意力合同** / 强制注意力返还合同 / **人格语气可观察维度** / 🔴 **「You died」五种语气** / 沉默基线测量 / **NaN·±0·±∞·溢出必触发** / 退化世界 | **只记帧率和平均延迟会把相位信息平均掉**；**边界是负空间不是补丁清单** |
| **`game_destruct_chain.py`** | 游戏 | 🔑 **破坏粒度四种（不是视觉档位）** / **承重是显式连接图属性** / **碎块消失是四个独立计时器** / 🔴 **NavMesh 障碍只能阻塞不能创造** / 开洞音频衍射 / **元素矩阵不对称方阵** / 🔴 **更新顺序决定确定性（30/60fps 会分叉）** / 风场 / **灭火残留** / 🔑 **绳索「同一参数」是伪命题** / 🔴 **孤岛最大值影响其他物体** / **荡绳可达性是连续函数** / **RNG 快照三档 + 固化时机四档** / 氛围密度 | **自研半程序化子系统 vs 通用解：直接迁移会静默改变玩法结果** |
| **`game_lifeplay_trace.py`** | 游戏 | 🔑 **钓鱼最小单元是拉力—时间曲线（不是难度档）** / 🔑 **上下马是控制权交接** / 宠物关系反馈三层 / **住宅因果图** / 🔑 **首次启动是不可重来的状态轨迹** / **失败教学三时序** / 🔴 **「不知道自己不知道」** / **人格化痕迹五类** / 🔴 **设置迁移要比语义不只比键名** / **过场控制权矩阵** / 选择延迟六层级 / 🔴 **「不可跳过」需证明** / **离线是功能降级图不是开关** / **经济四表五场景** / 稀缺性 | **验收单位从「功能存在」升级为「状态轨迹逐字段相等」** |
| **`game_carrier_rights.py`** | 游戏 | 🔑 **触控是连续触点拓扑不是键盘映射** / 🔴 **手势必须竞争不是分别回调** / 🔴 **按数组索引处理是高危** / 虚拟摇杆·掌机·陀螺仪 / 🔑 **官方编辑器＝产品决策** / **热重载四档** / API 三键 / 🔑 **沙箱是能力交集** / 🔴 **禁止目录扫描顺序冒充稳定** / **保底计数原子写服务端** / 🔴 **退款＝世界回滚预案** / 🔑 **数据布局是可审计字段** / 🔴 **SIMD 标量黄金路径** / 批处理归档 / **调试设施六态** / 云串流端到端 | **漏洞不在画面，而在「玩家如何伸手进去」和「数字权利如何流动」** |
| **`game_inference.py`** | 游戏 | 🔑 **玩家据此以为会发生什么** / **常识违反是资产** / 🔴 **`Wood_Barrel_01` 不可燃但 `Wood_Crate` 可燃（资源名不能代替运行时测试）** / 可学习线索 vs 静默陷阱 / 符号四态 verdict / 🔑 **OOB 是原版地图的一部分** / 边界厚度测距离非布尔 / OOB 美学 / 🔴 **通道权威性按状态机** / primary·indicative·thematic·undefined / **动画命中判定未中＝游戏撒谎** / 🔑 **复现随机接口非只分布** / `designed_illusion` / 可解释性四级 / 设备老化与校准 / `save_lineage` / `source_kind` 六种 | **从「游戏给什么」到「玩家据此以为会发生什么」** |
| **`game_relation.py`** | 游戏 | 🔑 **关系状态（系统之间的时间接缝）** / **离开前最后 120 秒轨迹** / AFK 六态图 / **回归奖励是承诺测试样本** / 🔑 **未完成存档的尊严** / 断点与最后动作 15 个时刻 / 🔴 **第 N 次四层计数 × 语境标签（布尔 seen 会误判可跳过）** / **跳过是控制权迁移非删内容** / 第 50 次台词四种问题 / 🔑 **幽灵六级**（门后没有模型 ≠ 没有承诺）/ 第一次三层不可再生 / `self_rules` · `clumsiness_matrix` · **共谋不揭穿** · `nostalgia_probe` | **前四十二轮是静态系统，本轮是时间接缝** |
| **`game_identity.py`** | 游戏 | 🔑 **名称只是标签，身份才是契约** / **同形异质六类** / ID 四层 / 🔴 **背包容缩为去重+数量＝消灭玩家记得的每一把剑** / 🔑 **整理背包也可能改变结果**（`observed_slot_history`）/ **个人操作方言＝动作短语非键位表** / `intent` 与 `command` 分离 / **缓冲宽严双向陷阱** / 🔑 **无效输入的副作用才是 must-match** / **意外组合八接缝** / 三级分类（含 `unintended_preserved`）/ 🔑 **惯例层与原版层并存**（Tank/现代双方案）/ 挂机是契约 / **输得好看** / **错过的稀缺性本身就是内容** / `seed_contract` · `prompt_binding` · `explanation_audience` | **实体身份 · 动作语义 · 玩家契约** |
| **`game_social.py`** | 游戏 | 🔑 **四条外部依赖链** / **老玩家教的是旧版本**（知识声明三层：观察/断言/证据链）/ 🔑 **假可玩性＝界面先承诺、系统再拒绝** / `placebo` / **试玩残留与教程临时能力** / 🔑 **玩家第二职业依赖可观测裂缝** / 四类接口 / 🔑 **版本地层 DAG 非时间轴**（标题相同≠构件相同）/ 🔴 **地区版不能写「日版总是更难」** / 仪式性浪费 / **个性化四个破绽接缝**（称呼/知识/时间/遗忘）/ 🔑 **苦行边界与多通道验证** / `metagame_entry` · `absent_social_clock` · `player_evidence` · `player_agency` · `aesthetic_stratum` | **社会层** |
| **`registry_normalize.py`** | 元 · **执行层修复** | 🔑 **不开新主题，先修审核 P0** / 🔑 `kind` 五分类：**cli(171) · lib(12) · doc(12) · sdk(7) · reference(140)** / 🔑 **真正可运行的 = cli+lib = 183 条（53%）**，其余 159 条**不是缺口，只是不能 `which`** / 🔴 **15 组重复 key 静默丢失 16 条**（YAML 后写覆盖先写）——**重名至少还在文件里，重复 key 是彻底没了** / 已重命名 `_dup2/_dup3`，**326 → 342 条** / 28 组重名已标 `dup_of` / 🔑 **真实缺口只看 cli+lib 两行** | **登记表归一化** |
| **`edge_pipeline.py`** | 游戏 · **端到端** | 🔑 **把四路验收链路真正跑通一次** / `--self-test` **用合成真值自测并验证还原**（实测误差 **0 帧**）/ 规范命名实测生效 `{build_id}/{state}/{media_type}/{index}_{clock_ns}.{ext}` / 🔑 **真正跑通 = 2/4**（clock + visual）；audio `degraded`、photo `tool_missing` **均不计入通过** / 🔴 无 `fpcalc` 时输出 `numpy_fft_fallback` **降级特征并标注 `backend`**，绝不当真指纹 / 🔑 `T_min_ms`/`T_max_ms` 为 **null**，🔴 **基线不可知不伪造 PASS** / 🔑 验证的是**流水线本身**，🔴 **不证明任何原版行为已取证** | **四路验收端到端** |
| **`build_manifest_spdx.py`** | 元 · **规范核验** | 🔑 **落地前先核一手规范，结果推翻三处** / 18→**19 字段**（9 自有 + 10 继承）· 🔑 **必填仅 3 个** / 🔴 **`buildId` 官方原文 `locally unique`**——须自加 `externalIdentifier` 全局层 / 🔴 **`buildStartTime/EndTime` 官方说可省略才利于可复现**，3.1 已弃用 → **脚本默认不写** / 🔑 `buildType` 只是 **hint** 不是真相 / 🔴 **前八轮漏了 Build profile 的 3 条强制关系**（hasInput · hasOutput · invokedBy，scope=build）——**只有字段没有关系不是 Build** / 实测：合规片段过 / 删 `hasOutput` 被拦 | **SPDX 3.0 Build 接入** |
| **`edge_pipeline.py --import`** | 游戏 · **真实捕获** | 🔑 **闭合第 51 轮第三项**：真实捕获接进四路流水线 / 🔴 **真实捕获不生成 `ground_truth.json`，`--verify` 被拒绝（退出码 1）** —— **从机制上挡住用合成自测冒充真实取证** / 🔑 必须先 `ffprobe` 探测 fps/时长/音轨；缺 ffprobe 直接报错；探测失败才用默认 25 并标 `fps_guessed` / 实测 91KB ffmpeg 编码素材：60 帧 · 74 时间点 · 观测段 [60] · `T_min/T_max` = null / 🔑 **管道已通，等待真实素材** | **真实捕获导入** |
| **`claim_verify.py`（第七十五轮 · **NEW**）** | 元 · **11/11** | 🔑 **完成声明核实器**：`--verify` 声明清单（gate/cmd/file/grep/cachekey） / `--scan-doc` 扫文档 G 编号报"文档有代码无" / `--self-test` 正反两组（正例 6/6 · 反例 6/6 拦住） / 🔴 抓到历史残留 **G381** | **G381** |
| **`claim_verify.py`（第八十轮·升级）** | 元 · **G382~G386** | 🔑 新增 **`--check-content`**（G386：AST 取三段体函数，断言特征串**存在性 + 唯一性**；`ALL_CONTENT_FN` 让"独有"成为**可校验事实**而非注释声称）/ 🔑 `--audit-all` **先自检判据**，坏尺子**拒绝给结论**/ 🔑 两个方向故意破坏**均被抓**（措辞漂移 / 非独有）/ self-test **12/12 · 7/7** | **通过 15→16** |
| **`gate_chaos.py`（第七十四轮）** | 元 · **99/101** | 🔴 **第七十三轮声称的 G341 全量 / G379 / G380 / full-sampled 全部不存在** —— 本轮补齐 / ✅ G341 真跑全量（**52 秒**，此前"3~5 分钟"是过时数据） / 🔑 **`--assert-full`**（G379）· **`--assert-no-pollute`**（G380）均 rc=0 / 🔴 三处**哨兵值**陷阱：`(未测)` 是真值字符串 | **通过 8→10** |
| **`gate_chaos.py`（第七十二轮）** | 元 · **99/101** | 🔑 **`--chaos --limit N`** 快速子集：G341 从"从未执行"→ **每次回归真跑**（20 个约 30~60s） / 🔴 抽样**不写全量缓存**（防汇总谎报 99/101） / 🔑 **`--self-check-limit`**（G378）秒级守 5 项 → **5/5** / 🔴 修自身截断 bug：固定 9000 字符切函数体会截掉尾部 | **说明性门禁 0** |
| **`gate_chaos.py`（第七十一轮）** | 元 · **99/101** | 🔑 **`--self-check`**：秒级能力自检（G346/G360 要求的能力可自动验证）→ **5/5** / 🔴 修检查器自身两处误判：BinOp 导致 literal_eval 失败被判"缺失"；ENUMS **问错对象** | **5/5** |
| **`edge_pipeline.py`（第七十一轮）** | 四路验收 | 🔑 **`--verify-guard`**：G338 的真实命令 —— 合成素材 → `--import` → `--verify` **必须退 1** / 🔴 修"只在某路径炸"：不传 `--dir` 时 `tempfile` 未导入 | **守卫成立** |
| **`run_all_gates.py`（第七十一轮）** | 元 · **126** | 🔴 **主 bug**：tpl 为字符串 → 逐字符拆命令 → hard 门禁**静默失效**成软警告 / ✅ 新增 `noop` 分类显式报出"从未执行" / 🔑 `--self-check-noop`（G377） | **软警告 2→0** |
| **`gate_chaos.py`（第六十九轮）** | 元 · **99/101** | 🔑 **`--catalog-probe --synthesize`**：模板仅 1 行示例时复制成 6 行再改瘦 → **覆盖 11/98 → 98/98**（无法改瘦 **0**） / 🔑 **87 个合成后全部是 B** → 实证"不是目录完备型"，**不是覆盖盲区** / 🔴 修假阳性：`idcol` 回退到首列会把 `match_type` 当 id → `exact_s3` 非法 → A 假阳性 / ✅ 合成后**必须重测基线** | **A 5 · B 90 · 脏 3** |
| **`gate_chaos.py`（第六十八轮）** | 元 · **99/101** | 🔴 **md 毒化器一直都在**（第五十九轮） —— 第六十七轮我自己选了 `_fill_md` 却记成"没有毒化器" / 🔑 `--format-audit` 升级**两阶段**：毒化有效 **95** · 无效 **0** · 崩溃 **0** / 🔑 **`--catalog-probe` 改瘦模板**：A 敏感 **5** · B 不敏感 **3** · 基线不干净 **3** / 🔴 **87/98 数据行 < 4 无法改瘦** —— 覆盖是 **11/98**，不是 98 / 🔑 格式复核已并入缓存与汇总 | **毒化有效 95** |
| **`gate_chaos.py`（第六十七轮）** | 元 · **99/101** | 🔑 **`--format-audit`**：98 个台账 → `csv 94 / md 3 / yaml 1`，**毒化后崩溃 0** / 🔴 抓到真 bug：**两个嗅探器打架**（`_sniff`=md vs `_is_md_table`=non-md）→ md 清单被 CSV 写回 / 🔑 增量完备性**合并写入**缓存并进汇总 / 🔴 踩坑：`--init` 可能生成**目录**（IsADirectoryError）→ 100 变 **98** / 🔑 `--format-audit` **故意不进 self-test**（98×2 子进程，~6min） | **无格式错配** |
| **`gate_chaos.py`（第六十六轮）** | 元 · **99/101** | 🔑 **漏网风险已由分类完备性封闭**：目录完备型≡"基线不干净"，而 101 个中仅 2 个不干净且**已全部登记** → **不存在第三类** / 🔴 **负结果**："删行 → blocker 上升"**不可用**——逐行校验型删行＝删掉 blocker 源（license 实测 `[3,2,2]`，方向反了） / 🔑 `--catalog-scan` 列候选题（**只列不下判定**）：127 → 收紧后 62 / 🔴 **纠正第六十四轮误记**：42 个脚本统一 `>=7` 阻断，**口径冲突不存在** | **分类完备性** |
| **`gate_chaos.py`（第六十五轮）** | 元 · **99/101** | 🔑 强证据 **99** · 目录完备型 **2** · 真弱证据 **0** / 🔑 **`--completeness` 增量完备性**：补齐一项 → 缺失计数应降一项（fault_matrix 24→0 · install_contract 10→0，均单调）/ 🔴 纠正上一轮误判：**`处置分布` 是正常统计打印不是缺失信号**→ feature_matrix 实为**可修**的真弱证据 / 🔑 `TEXT_REPLACEMENTS`：TODO 可能藏在**单元格内容**里，按列名匹配无效 / 🔴 修自己造的度量 bug：缺失归零后那行不打印 → **不能沿用上次值** | **99 + 增量完备性** |
| **`gate_chaos.py`（第六十四轮）** | 元 · **98/101** | 🔑 强证据 **98**（上一轮 89）· **真弱证据 0** / 🔑 **目录完备型 3** —— 「没记全」正是它要拦的，**上限不是 101 而是 98** / 🔑 `_sniff()` 按 **CSV/Markdown/YAML** 分派（🔴 YAML 按 CSV 写回会**毁文件**）/ 🔴 坑：YAML 的非法值是 `TODO` 不是 `__poison__`；`len(hdr)<2` 不碰；fixture 优先于"保留原值"；占位符按**前缀**判 / ⚠️ 口径冲突：`game_edge` 把 evidence≥7 判未达标，与别处相反（**未擅自统一**） | **98 + 3 上限** |
| **`gate_chaos.py`（第六十三轮）** | 元 · **强证据率** | 🔑 拦 101/101，但**强证据只有 89**（基线 rc=0）· 弱证据 12 / `--baseline empty` 时强证据**只有 4** → 🔴 **拦截率必须配强证据率读** / 🔑 反直觉：`match` 填 `yes`（而非 `exact`）让强证据 6→79 / 🔑 **用 AST 读脚本自己的 ENUMS** 填充 → 84→88（性价比最高，不需人工） / 🔑 `FIXTURE_OVERRIDES` 逐脚本登记 → 88→89 / 🔴 坑：只替换**占位符**、保留清单项名；配对字段必须相同 / ✅ 缓存新增 `strict_rate` 并接入汇总 | **强弱分级** |
| **`gate_chaos.py`（第六十二轮）** | 元 · **101/101** | 🔑 **拦截率 101/101 · skip 归零**（typed 与 semantic 一致） / ✅ 三脚本各用**不同**毒化：`ledger`=CSV 值 · `visual_check`=**结构删键** · `motion_check`=**时序放大**（ffmpeg 合成视频） / 🔴 两个坑：**init→prep 顺序不能反**；**适配器必须完全接管通用路径** / 🔑 新判据：**基线必须 rc=0**，否则计入 `baseline_not_clean` / ⚠️ 造的是**输入工件**，只证明门禁响应内容，**不证明原版已取证** | **全拦截** |
| **`gate_chaos.py`（第六十一轮）** | 元 · **skip 细分** | 🔑 3 个 skip 的**真实身份**：`ledger`/`visual_check` = `not_a_ledger`（`--init` 是 store_true，不生成 CSV）；`motion_check` = `needs_external_input`（compare 要 ffmpeg 抽帧 JSON） / 🔴 修真 bug：**缺数据即通过**——三字段全 None 仍打印"✅ 在容差内" rc=0 / 🔴 自犯第二错：**过度严格＝误杀**（无 evidence 列却做证据断言） / ✅ `ENUMS_KIND = constraint / must_match` 两类语义分开 | **物种细分** |
| **`gate_chaos.py`（第六十轮）** | 元 · **全参与 + 可信度** | 🔑 **101 项全部参与统计 · 拦截率 98/98 · iface_mismatch 归零** / ✅ `INTERFACE_ADAPTERS` 适配 `credits_diff`（`--diff OLD NEW`）：**OLD 干净 + NEW 毒化** → 必产生 diff 事件 → 门禁有效则必阻断 / ✅ 汇总新增「门禁自身可信度」：**混沌拦截率 + 字段覆盖率** / 🔴 **又踩两次静默 except**（错变量名 / 错键名 / 写在条件块内）—— 已全部改打印 / 🔑 **98/98 的分母是"能参与统计的 98 项"，不是 101** | **全参与** |
| **`gate_chaos.py`（第五十九轮）** | 元 · **A 类归零** | 🔑 **A 类盲区 9 → 0 · 拦截率 87/101 → 97/101** / 🔴 **推翻上一轮一半结论**：`game_progress_input` 的 `--gate` 是**子命令**，优先级最高 → `--check X --gate` 实际只打印章节，**一次校验都没跑** / 🔴 同脚本 `--gate` 与 `--gate_check` flag 分裂 / ✅ 其余 8 个加 `ENUMS` 白名单 + 跨字段一致性 / ✅ 毒化器支持 **md 台账**（原先把 md 当 CSV 会**摧毁结构**误判为崩溃） / ✅ 新增 `iface_mismatch` 分类（测试器没适配 ≠ 门禁失效） / 🔑 **最重要**：三种毒化一致**只证明现象可靠，不证明原因正确** —— **要找原因必须读代码** | **A 类归零** |
| **`gate_chaos.py --strategy semantic`** | 元 · **语义毒化** | 🔑 **把毒化从一维扩成「语法 × 语义」二维** / 🔴 语法毒化只测"校验是否检查了这个字段"；**真人填表不会填 `__poison__`，而是填合法但矛盾的值**（legacy=100 / new=200 / match=exact） / 🔴 **踩坑**：init 表全是 `TODO`，TODO 覆盖逻辑**把语义值冲成 `ok`**，**毒化静默失效却显示正常完成** —— 已修（semantic 完全不看原值） / 🔑 **最重要发现**：`a11y_ime` 是唯一被 typed 拦住、被 semantic 放过的脚本 —— **白名单只能证明值合法，不能证明行自洽**；已加跨字段一致性校验 / 🔴 **9 个盲区在三种完全不同的毒化下都不动** | **语义毒化** |
| **`gate_chaos.py --coverage`** | 元 · **覆盖率** | 🔑 **闭合第 56 轮疑问**：把"拦截率 88%"的**置信区间变成可测量数字** / 实测 **94 台账 · 705 字段 · 616 可断言 · 覆盖率 87.4%**，🔴 剩余 89 个是**真实盲区，只能靠人工** / 🔑 类型推断 8 类（新增 `pair`）/ 🔴 **一个假设被证伪**：以为 legacy/new 配对毒化成相同值会漏检 —— **实测 80 个中 79 个相同毒化即被拦**，假设错了，如实记录 / 🔑 **更重要**：`typed` 与 `legacy` 两种毒化**结果完全一致 87/101** —— **A 类盲区不是毒化不够狠，而是 check 根本不检查这些字段** | **毒化覆盖率** |
| **`gate_chaos.py`** | 元 · **门禁有效性** | 🔑 **第二十轮说"82 个门禁可能全是假的"，本轮第一次真的去改坏** / 对 **101 个台账型门禁**逐个 `--init` → **故意填违例** → 看是否阻断 / 🔑 实测 **拦截 89/101 ≈ 88%** —— 🔑 **门禁数量第一次被替换成拦截率** / 🔴 **B 类【空表即通过】**：`license_gate` 污染成 0 条 → "无阻断项" → rc=0 （**已修**：0 条显式失败） / 🔴 **A 类【内容盲区】8 个**：能拦 TODO，但**填任意非法值反而通过** —— 根因是**黑名单式校验**；已修 `a11y_ime`（加 `VERDICT_ENUM` 白名单） / ⚠️ 毒化只覆盖 11 类关键词，**未覆盖字段的有效性仍未知** | **门禁混沌测试** |
| **`kiosk_recorder.py`** | 游戏 | 🔑 **没有公开通用规则可以替代目标机型实测** / 🔑 **最小单位是 title+region+revision+DIP/设置+线束 五元组** / 🔴 **把一台机柜的 N 秒推广为行业默认值＝方法论污染** / **Service 键移动光标 · Test 键改设置 · COIN CHUTE TYPE 可 COMMON/INDIVIDUAL** / **同一笔 coin 是否进公共池取决于 operator 配置而不是玩家按键** / 🔑 **展会预约是另一种 Kiosk 状态**（QR 电子票分配时段 · 含现场时钟的同步视频）/ 🔴 **秒数已填但证据态非 verified 即硬拦截**（防伪造关键闸门）/ 开源 Kiosk 只做 capture harness | **试玩机状态层** |
| **`credits_diff.py`** | 游戏 | 🔑 **补丁会改变可归因事实，最合理的表示是带证据链的 diff** / 🔑 **不应把 Credits 当文本 dump**（应存 asset_path · version_range · evidence_url/artifact_sha256）/ **同作跨版本同 JSON 同一人从无到有的可验证闭环**（1.21.7 RC1 → 1.21.11 Pre-Release 1）/ 🔑 **离职者仍署名 · 原团队先列 · 错误应在后续 patch 修正** / **重制版以 "based on the work of…" 概括原团队** → 只记 public_dispute_evidence / 🔴 **众筹支持者自述缺失只标 claimed_omission** / 七类 event_type × 四档 confidence / 🔴 **删除·排序·跨段缺证据链接即硬阻断** | **Credits 演化** |
| **`cdkey_input_linter.py`** | 游戏 | 🔑 **CD-KEY 是字符消歧问题** / 0→Q/D/O · 1→I/L · O→Q/D · B→8 · G→6 / **正版用户也会在输入层失败** / 连字符自动插入 · 全半角 · 粘贴清洗 · 输错几位才反馈 · IME · 读屏文案 / 🔴 **原版不区分不得加校验；原版区分不得自动纠错** / ⚠️ **不做密钥生成 · 不做在线验证 · 不绕过检查** | **CD-KEY 输入层** |
| **`edge_accept.py`** | 游戏 | 🔑 **统一时钟比统一像素阈值更重要** / `{build_id}/{state}/{media_type}/{index}_{clock_ns}.{ext}` / 🔑 **构建矩阵展开为 engine×platform×renderer×build_id** / 🔑 **整屏 diff 用于状态边界，逐帧 diff 用于循环内容** / **pixelmatch windowSize=N 滑窗检测小区域滚动残影** / 主链 Playwright→PNG→ODiff / `phase_match_ratio < 0.98` 则 fail / 🔴 **基线不可知只产出 observed_durations.json，不伪造 PASS** / 🔑 **音频三层：指纹按窗切段 + cross-correlation + 频谱节拍** / ⚠️ Chromaprint 整体 LGPL-2.1，静态链接须合规审查 / 🔑 **物理表面以可复核尺度为 must-match**（色卡/ArUco/EXIF/measured LAB）/ 🔴 **缺产物哈希即硬拦截——没哈希就无法重放** | **四路验收接入** |
| **`game_edge.py`** | 游戏 | 🔑 **三张状态图挖到可录制·可断言·可回放的字段层** / 🔑 **共同性质：原版真实存在但通常不被认为是游戏内容的状态表面** / 🔑 **试玩机不是零售版换皮**——90 秒空闲 → 5 秒重置 → 复位亮度/自动旋转/手电筒/语言/无障碍 / **关电重开·程序异常·观看者离开都回到 Attract 而不是上次进度** / 🔑 **倒计时是逐渐加压的中断流程**（最后 10 秒变色闪烁 · 给出宽限—等待输入—超时清场，不是立刻黑屏）/ 高分表拆本轮/历史/断电是否保留 / **被磨平的字符 · 摇杆防尘圈 · Service 键盲点 · 屏幕烧残 · 手柄线被拉断的应急** / Kiosk 内容差异是分支版本不是 bug / 🔑 **失败屏是完整表现资产**（CRT 抖动 · 扫描线 · 噪点）/ 🔑 **故意错误内容是最容易被判成 bug 的 must-match**（海盗眼罩 · 偏离节拍的 vuvuzela · 近乎停止的边缘 · 无法受伤的追踪敌人）/ 🔑 **CD-KEY 是字符消歧问题**（0→Q/D/O · 1→I/L · B→8 · G→6 · 正版也会在输入层失败 · 不得自动纠错）/ 🔑 **Credits 是版本化证据链**（原始团队在前且两类同时可见 · 某人在最后可能意味着末位分组/外包/离职/别名/只是没重排）/ **支持者拼写不能简单改正** · **为版式整齐删除众筹名单是善意的破坏** · **删除原作者不是品牌更新是署名缺陷** / 🔑 **证据态四态不得留空** | **边缘状态层** |
| **`game_variant.py`** | 游戏 | 🔑 **四套被压平为单一正式版的状态表面** / 🔑 **Demo 不是正式版的截短，是带独立权限·内容·存档·结束协议的产品形态** / 七态状态机 / **勋章可继承但奖杯不可——走了两条规则** / 🔑 **存档继承是带一次性决策和不可逆分支的协议**（长按确认 · 拒绝后必须删全部槽位才重新开放 · 仅限同平台 · 模式锁） / 🔴 **不得悄悄增加恢复安全网** / 🔑 **Attract Mode 假操作是刻意编排不是录制**（投币提示本身是循环一部分 · 不能只截一张标题画面）/ 🔑 **秘籍是发布内容不是调试残留** / **testingcheats 只关当前存档奖杯** · 主机长按○再按× / 五层输入窗口与 IME / 开发者菜单按发布证据分判 / 🔑 **旁观者是无输入权限的第二名玩家** / **(on radio) 收音状态标注** · `original_purpose` 区分官方无障碍·社区速通·家长代打·观众放映 / 🔑 **纸质地图与数字小地图是两套认知工具** / 布质地图折痕与两人摊开 · **回函卡不只扫描正反面** / OST 游戏外记忆 / **印刷错别字是时代地层** / 🔑 **错误画面可能是可互动迷你关卡** / 🔴 **单槽强制自动保存破坏叙事仪式** | **变体与载体层** |
| **`game_meta.py`** | 游戏 | 🔑 **对象是「玩家如何借系统理解世界、表达意图并承担后果」** / **判断从"是否实现"升级为"是否形成同一行为契约"** / 🔑 **沟通不是聊天的集合，是多通道异步协同协议** / 五维模态矩阵 / 🔑 **`message_id` 是沟通复刻第一类数据** / 九种通道不可让渡语义 / **四种回应与四人会话脚本** / 🔑 **跨语言＝把不可译动作排除在契约外** / 无语音玩家完整贡献路径 / 堆叠 vs 去重都是偏离 / 🔑 **行动前知道什么才决定选择属于自己** / 风险账本 18 字段 / 不可逆层级与提示强度 / **保存边界不能用云同步覆盖** / 🔑 **行为记忆是带证据和期限的缓存** / 被监视感来自无法关闭的影响 / 每个自动化建议都要有手动等价物 / 🔑 **外部工具是接口生态不是作弊** / damage 可能指六种伤害 / **overlay 读已导出文件不算作弊** / 🔑 **稀有度是通道同步的承诺** / 屏蔽声音后能否识别层级 / 🔑 **认知地图不是地图几何** / 🔴 **沉默是规则不是空缺** | **元协议层** |
| **`game_life.py`** | 游戏 | 🔑 **玩家管理的是会话承诺，不是时长** / **"打完这个 BOSS 就睡"** / 会话承诺曲线七段 / **存档点不可中断窗口** / 🔑 **暂停取决于能否冻结而非按钮存在** / 再来一局触发器集合与 1–5 评分 / 生活接口污染 / 🔑 **容忍不可预测 ≠ 容忍无法归因** / **黑箱更公平是错误推论** / 七类受控随机通道 / 透明度三层 / 性格与作弊＝规律可学习 / 🔑 **文化层十维**（4 在东亚不吉利 · 紫色表哀悼 · 笑点功能 · 源语言默认无文化是盲点）/ 🔑 **排序稳定性是首要 must-match** / 平局按什么排 / **Mod 加载顺序决定功能** / **命名截断契约** / 🔑 **展示与删除权六种操作** / 精通曲线与技能遗忘 / 🔑 **第三空间不是低效率空间** | **生活层** |
| **`game_periphery.py`** | 游戏 | 🔑 **原版「游戏」不止于进程内画面** / **十三类外围层按状态机取证**（启动器/成就面板/云存档UI/好友/通知/商店/社区/工坊/排行榜/反作弊/DRM/模组管理器/覆盖层）/ 🔑 **GOG：Init 失败不应停止加载，只禁用成就等** / **EOS：身份与数据是两条链** / 五类账号标识 / 🔑 **玩家自救＝第二控制流**（先快照→后报告→再确认，禁自动删）/ 🔑 **物理外设四层抽象**（开关 0/1 · 绝对轴 -65536~65536 · 单端轴负半区 · 振动线程排队）/ **方向盘饱和区与断电残留扭矩** · **光枪刷新相位与离屏装填** · **跳舞毯相邻误触与鞋底磨损** / 🔑 **游玩环境考古（客厅≠书房）** / WCAG 只作测量尺度 / 元进度五层 / 🔑 **玩家作品出处链** / **通关后世界是叙事状态机** | **外围层** |
| **`game_cognition.py`** | 游戏 | 🔑 **心智地图非 NavMesh** / 地标可回忆·可方向化·可复访 / 🔴 **捷径记忆价值（碰撞瑕疵形成的捷径可能要保留）** / **迷路三分类** / 垂直空间是认知层 / 🔑 **决策承诺语义** / 后果四级 / **故意隐瞒＝must-match** / 不可逆五轴 / **仪式感 1.2 秒关门声** / 🔴 **SL 可行性实测** / **长时间漂移五阶段** / 听觉习惯化 / 🔴 **操作自动化是故障源** / 上手曲线 / **成功包络非平均成功率** / **责任归因六方** | **从「读出什么意义」推进到「是否装进记忆·肌肉与信任」** |
| **`game_meaning_layer.py`** | 游戏 | 🔑 **事实态+表达态+可辨态三层** / 🔴 **可辨性优先于可播放性** / **脚步是四段链条不是表面枚举** / 🔴 **「楼上还是楼下」必须独立字段** / 威胁按声学角色拆分 / **步态暴露状态** / 🔑 **成长五通道 + delta_direction** / **沉默事实不许补成「更爽」** / 🔴 **聚焦生命周期 19 事件** / 多显示器拓扑 / **截图录屏是能力清单** / 🔴 **原版允许却悄悄禁止＝破坏** / **跨通道节拍偏移 + beat_clock** / 等待四要素 / **APM 天花板** / 🔑 **刻意坏味清单** / **社群锚点三空间** | **前 39 轮覆盖传输链，本轮覆盖「玩家读出什么」** |

### `tools/` 外部工具封装层（42 个工具）

见 `scripts/tools/README.md`。登记表 `tools/registry.yaml`，
封装脚本 9 个（harfbuzz / odiff / toxiproxy / kaitai / vmaf / gumtree /
resvg / ocr / duckdb_evidence）。**缺失时如实降级，不得静默跳过。**

---

## 快速上手

```bash
cd <你的工作区>

# ⭐ 外部工具调度（42 个工具，先探测能力再调用）
python3 scripts/tool_run.py --list                     # 全部登记工具
python3 scripts/tool_run.py --env                      # 能力矩阵（是否**真**可用）
python3 scripts/tool_run.py --check ast_grep           # 单个身份校验
python3 scripts/tool_run.py --check-all --json ledger/capability.json --gate
#   ⚠️ `which sg` 命中的是 Unix 的 sg（set group ID）—— 必须校验身份

# ⭐ 一键跑全部门禁（推荐：每次提交都跑）
python3 scripts/run_all_gates.py --work work/ --strict
python3 scripts/run_all_gates.py --list                    # 只看门禁清单，不执行
#   ⚠️ 自动门禁全绿 ≠ 可以收工：人工门禁一项没签字就不得声明完成

# S0：原版取证（最先做 —— 原版是唯一可信的测量基准）
python3 scripts/original_capture.py --init work/original_capture/   # 环境契约骨架
python3 scripts/original_capture.py --env                           # 看契约与定位优先级
python3 scripts/original_capture.py --pid <pid> --out work/original_capture/ --tree --shot

# 树对齐与差异归因（像素差只是症状，不能作为终态证据）
python3 scripts/tree_align.py --old old.uia.json --new new.a11y.json --out alignment.json --gate
python3 scripts/tree_align.py --budget                  # 预算、匹配向量、归一化规则
python3 scripts/diff_classify.py --old a.png --new b.png --out diff.json --gate
python3 scripts/diff_classify.py --rules                # 十类根因判据

# 环境锁（先做：环境不一致 = 证据失效）
python3 scripts/env_lock.py --record --out environment.lock
python3 scripts/env_lock.py --check environment.lock --gate    # 不一致直接 FAIL

# 差分测试（原版自己当 oracle，不需要人写 oracle）
python3 scripts/diff_fuzz.py --old ./old --new ./new --inputs inputs/ --gate
python3 scripts/diff_fuzz.py --pairs pairs.jsonl --out oracle.json --gate
python3 scripts/diff_fuzz.py --classes                         # 四类 oracle 判据

# 功能对照表（原版有啥/新版有啥/每条怎么处置）
python3 scripts/feature_matrix.py --init ledger/feature_matrix.md
python3 scripts/feature_matrix.py --check ledger/feature_matrix.md \
        --features ledger/features.md --gate      # 顺带双向对账
python3 scripts/feature_matrix.py --classes      # 五类处置与四条判据

# 语义证据层（文本 / 故障 / 安装）
python3 scripts/text_layout.py --dims                     # 五维与根因对照
python3 scripts/text_layout.py --old a.csv --new b.csv --gate
python3 scripts/fault_matrix.py --catalog                 # 26 类故障目录
python3 scripts/fault_matrix.py --check ledger/faults.csv --gate
python3 scripts/install_contract.py --fields              # 13 字段 + 13 残留位置
python3 scripts/install_contract.py --check ledger/install.md --gate

# 游戏引擎复刻（确定性 / 渲染 / 资产）
python3 scripts/game_replay.py --subsystems                 # 子系统判因表
python3 scripts/game_replay.py --init ledger/replay_manifest.yaml
python3 scripts/game_replay.py --desync --old old.jsonl --new new.jsonl --gate
python3 scripts/game_render.py --tools                      # 取证工具分工
python3 scripts/game_render.py --baseline baseline.yaml --gate
python3 scripts/game_asset.py --engine                      # Unity/UE/Godot/GM 映射
python3 scripts/game_asset.py --check ledger/game_assets.csv --gate

# 运行时取证 / 二进制覆盖 / AI 门禁
python3 scripts/runtime_forensics.py --primitives       # 行为基元八要素
python3 scripts/runtime_forensics.py --check ledger/runtime_forensics.csv --gate
python3 scripts/binary_coverage.py --tools              # BinDiff/Diaphora/ghidriff 约束
python3 scripts/binary_coverage.py --check ledger/binary_coverage.csv --gate
python3 scripts/context_pack.py --gates                 # AI 七道强制门
python3 scripts/context_pack.py --scan src --gate       # 密钥扫描
python3 scripts/context_pack.py --review-check ledger/ai_changes.json --gate

# 游戏深化：内容 / 战斗 / AI / 数值 / 存档
python3 scripts/game_content.py --level          # 关卡实体与触发器对账
python3 scripts/game_content.py --hidden         # 隐藏内容穷举
python3 scripts/game_content.py --dev            # 调试/作弊功能（是真功能）
python3 scripts/game_content.py --check ledger/level_manifest.csv --gate
python3 scripts/game_combat_ai.py --framedata / --hitbox / --input / --conflict
python3 scripts/game_combat_ai.py --ai / --nav / --sense
python3 scripts/game_combat_ai.py --check ledger/combat_ai.csv --gate
python3 scripts/game_rng_save.py --rng / --rng-traps / --drops / --save / --achievement
python3 scripts/game_rng_save.py --check ledger/rng_save.csv --gate

# 游戏第四十二轮：常识 / OOB / 通道权威 / 伪因果 / 设备
python3 scripts/game_inference.py --common  # 🔑 常识规则测试矩阵
python3 scripts/game_inference.py --oob     # 🔑 OOB 是原版地图的一部分
python3 scripts/game_inference.py --chan    # 🔑 通道权威性
python3 scripts/game_inference.py --ritual  # 🔑 伪因果四档
python3 scripts/game_inference.py --explain # 🔑 可解释性四级
python3 scripts/game_inference.py --check ledger/inference.csv --gate-check

# 游戏第四十三轮：离开 / 第 N 次 / 幽灵 / 第一次
python3 scripts/game_relation.py --leave   # 🔑 弃坑地图（最后120秒）
python3 scripts/game_relation.py --nth     # 🔑 四层计数 × 语境标签
python3 scripts/game_relation.py --ghost   # 🔑 幽灵六级
python3 scripts/game_relation.py --first   # 🔑 第一次三层不可再生
python3 scripts/game_relation.py --check ledger/relation.csv --gate-check

# 游戏第四十四轮：同形异质 / 方言 / 组合 / 惯例
python3 scripts/game_identity.py --same   # 🔑 同形异质六类
python3 scripts/game_identity.py --phrase # 🔑 动作短语（非键位表）
python3 scripts/game_identity.py --combo  # 🔑 意外组合八接缝
python3 scripts/game_identity.py --conv   # 🔑 游戏惯例污染
python3 scripts/game_identity.py --check ledger/identity.csv --gate-check

# 游戏第四十五轮：教与学 / 假可玩性 / 第二职业 / 版本地层
python3 scripts/game_social.py --teach   # 🔑 老玩家教的是旧版本
python3 scripts/game_social.py --fake    # 🔑 假可玩性
python3 scripts/game_social.py --prof    # 🔑 玩家第二职业
python3 scripts/game_social.py --stratum # 🔑 版本地层 DAG
python3 scripts/game_social.py --check ledger/social.csv --gate-check

# 游戏第四十六轮：外围层 / 自救 / 外设 / 环境考古
python3 scripts/game_periphery.py --meta   # 🔑 元游戏外围层
python3 scripts/game_periphery.py --save   # 🔑 玩家自救第二控制流
python3 scripts/game_periphery.py --device # 🔑 物理外设四层抽象
python3 scripts/game_periphery.py --env    # 🔑 游玩环境考古
python3 scripts/game_periphery.py --check ledger/periphery.csv --gate-check

# 游戏第四十七轮：时间预算 / 拟人化 / 文化层 / 元收藏
python3 scripts/game_life.py --budget  # 🔑 会话承诺曲线
python3 scripts/game_life.py --persona # 🔑 公平归因链
python3 scripts/game_life.py --culture # 🔑 文化层十维
python3 scripts/game_life.py --sort    # 🔑 排序稳定性
python3 scripts/game_life.py --check ledger/life.csv --gate-check

# 游戏第四十八轮：沟通 / 风险 / 记忆 / 工具契约
python3 scripts/game_meta.py --comms  # 🔑 沟通元语言
python3 scripts/game_meta.py --risk   # 🔑 行动前风险账本
python3 scripts/game_meta.py --tool   # 🔑 外部工具契约
python3 scripts/game_meta.py --silence # 🔑 沉默是规则
python3 scripts/game_meta.py --check ledger/meta48.csv --gate-check

# 游戏第四十九轮：非完整版 / 秘籍 / 旁观者 / 实体载体
python3 scripts/game_variant.py --sku      # 🔑 非完整版本七态
python3 scripts/game_variant.py --cheat    # 🔑 秘籍是发布内容
python3 scripts/game_variant.py --watch    # 🔑 旁观者信息层
python3 scripts/game_variant.py --carrier  # 🔑 实体载体
python3 scripts/game_variant.py --check ledger/variant49.csv --gate-check

# 游戏第五十轮：试玩机 / 反盗版屏 / Credits
python3 scripts/game_edge.py --kiosk   # 🔑 试玩机状态链
python3 scripts/game_edge.py --antip   # 🔑 失败屏是表现资产
python3 scripts/game_edge.py --credit  # 🔑 Credits 是证据链
python3 scripts/game_edge.py --check ledger/edge50.csv --gate-check

# 游戏第五十二轮：执行层修复（不开新主题）
python3 scripts/registry_normalize.py --stats          # 🔑 真实能力面
python3 scripts/registry_normalize.py --check --gate-check
python3 scripts/registry_normalize.py --apply          # 修重复 key / 补 kind

# 游戏第六十九轮：合成改瘦（覆盖 98/98）
python3 scripts/gate_chaos.py --catalog-probe --synthesize

# 游戏第六十八轮：改瘦模板探针（把论证变成实测）
python3 scripts/gate_chaos.py --catalog-probe

# 游戏第六十七轮：格式错配复核（两个嗅探器必须一致）
python3 scripts/gate_chaos.py --format-audit

# 游戏第六十六轮：漏网风险封闭（分类完备性论证，非扫描覆盖度）
python3 scripts/gate_chaos.py --catalog-scan   # 只列候选，不下判定

# 游戏第六十五轮：强证据 99 + 增量完备性（目录完备型专用指标）
python3 scripts/gate_chaos.py --completeness

# 游戏第六十四轮：强证据 98 / 弱证据 0（上限不是 101）
python3 scripts/gate_chaos.py --chaos DIR     # 强证据 98 · 目录完备型 3

# 游戏第六十三轮：强证据率（拦截率须分强弱）
python3 scripts/gate_chaos.py --chaos DIR            # 默认 baseline=valid
python3 scripts/gate_chaos.py --chaos DIR --baseline empty   # 对比：强证据仅 4

# 游戏第六十二轮：造可毒化输入源（101/101）
python3 scripts/gate_chaos.py --chaos DIR --strategy typed    # 101/101

# 游戏第六十一轮：skip 细分到物种
python3 scripts/gate_chaos.py --chaos DIR   # 显示 not_a_ledger / needs_external_input

# 游戏第六十轮：101 项全参与 + 可信度进汇总
python3 scripts/gate_chaos.py --chaos DIR            # 拦截率 98/98
python3 scripts/run_all_gates.py --work DIR          # 汇总显示可信度

# 游戏第五十九轮：A 类盲区归零（9 → 0）
python3 scripts/gate_chaos.py --chaos DIR --strategy typed     # 拦截率 97/101
python3 scripts/gate_chaos.py --chaos DIR --strategy semantic  # 一致

# 游戏第五十八轮：语义毒化（字段合法 ≠ 行自洽）
python3 scripts/gate_chaos.py --chaos DIR --strategy semantic

# 游戏第五十七轮：毒化覆盖率（拦截率的置信区间）
python3 scripts/gate_chaos.py --coverage                     # 字段覆盖率（秒级）
python3 scripts/gate_chaos.py --chaos DIR --strategy typed   # 类型感知毒化

# 游戏第五十六轮：门禁混沌测试（故意改坏）
python3 scripts/gate_chaos.py --probe          # 哪些门禁可做混沌测试
python3 scripts/gate_chaos.py --chaos DIR      # 故意填违例，统计拦截率

# 游戏第五十五轮：真实捕获导入（自测 ≠ 取证）
python3 scripts/edge_pipeline.py --import FILE --dir DIR --build-id B
# 🔑 真实捕获无真值：不生成 ground_truth.json，--verify 拒绝（退出码 1）

# 游戏第五十四轮：SPDX 3.0 Build 接入
python3 scripts/build_manifest_spdx.py --show        # 字段表 + 三处修正
python3 scripts/build_manifest_spdx.py --self-test

# 游戏第五十三轮：四路验收端到端跑通
python3 scripts/edge_pipeline.py --self-test                      # 🔑 含真值校验
python3 scripts/edge_pipeline.py --capture DIR --build-id B       # 抽帧/抽音
python3 scripts/edge_pipeline.py --report  DIR --build-id B

# 游戏第五十一轮：证据补洞 + 四路验收接入
python3 scripts/kiosk_recorder.py --gap        # 🔑 证据不足清单
python3 scripts/credits_diff.py --diff v1 v2   # 🔑 Credits 演化事件流
python3 scripts/cdkey_input_linter.py --check ledger/cdkey_input.csv --gate-check
python3 scripts/edge_accept.py --clock         # 🔑 统一时钟

# 游戏第四十一轮：心智地图 / 决策承诺 / 耐力 / 信任
python3 scripts/game_cognition.py --map     # 🔑 心智地图
python3 scripts/game_cognition.py --commit  # 🔑 决策承诺语义
python3 scripts/game_cognition.py --drift   # 🔑 三小时后
python3 scripts/game_cognition.py --trust   # 🔑 统计公平 ≠ 主观可信
python3 scripts/game_cognition.py --blame   # 🔑 责任归因六方
python3 scripts/game_cognition.py --check ledger/cognition.csv --gate-check

# 游戏第四十轮：声音语义 / 成长可感 / 元操作 / 时间美学
python3 scripts/game_meaning_layer.py --vert   # 🔴 楼上还是楼下
python3 scripts/game_meaning_layer.py --growth # 🔑 成长五通道
python3 scripts/game_meaning_layer.py --meta   # 🔴 聚焦生命周期
python3 scripts/game_meaning_layer.py --beat   # 🔑 跨通道节拍偏移
python3 scripts/game_meaning_layer.py --imperf # 🔑 刻意坏味
python3 scripts/game_meaning_layer.py --check ledger/meaning_layer.csv --gate-check

# 游戏第三十九轮：输入载体 / UGC / 权利账本 / 数据布局
python3 scripts/game_carrier_rights.py --touch # 🔑 触控拓扑
python3 scripts/game_carrier_rights.py --pity  # 🔑 保底是玩法状态
python3 scripts/game_carrier_rights.py --simd  # 🔴 标量黄金路径
python3 scripts/game_carrier_rights.py --check ledger/carrier_rights.csv --gate-check

# 游戏第三十八轮：生活玩法 / 首次启动 / 痕迹 / 叙事接口
python3 scripts/game_lifeplay_trace.py --fish   # 🔑 拉力—时间曲线
python3 scripts/game_lifeplay_trace.py --mount  # 🔑 控制权交接
python3 scripts/game_lifeplay_trace.py --trace  # 🔑 人格化痕迹
python3 scripts/game_lifeplay_trace.py --check ledger/lifeplay_trace.csv --gate-check

# 游戏第三十七轮：可破坏 / 元素连锁 / 绳索 / 读档重摇
python3 scripts/game_destruct_chain.py --dest # 🔑 破坏粒度
python3 scripts/game_destruct_chain.py --rope  # 🔑 同一参数是伪命题
python3 scripts/game_destruct_chain.py --rng   # 🔑 RNG 快照三档
python3 scripts/game_destruct_chain.py --check ledger/destruct_chain.csv --gate-check

# 游戏第三十六轮：微观节奏 / 注意力 / 人格语气 / 边界
python3 scripts/game_micro_rhythm.py --ladder # 🔑 帧语义六问
python3 scripts/game_micro_rhythm.py --stop   # 🔴 1-3 帧微停顿
python3 scripts/game_micro_rhythm.py --num    # 🔴 NaN/±0/±∞ 必触发
python3 scripts/game_micro_rhythm.py --check ledger/micro_rhythm.csv --gate-check

# 游戏第三十五轮：具身表现 / 物品实体 / 非语言 / 肌肉记忆
python3 scripts/game_embodied_input.py --body  # 🔑 状态外显八字段
python3 scripts/game_embodied_input.py --nonv  # 🔑 非语言六字段
python3 scripts/game_embodied_input.py --sil   # 🔴 沉默是选项
python3 scripts/game_embodied_input.py --check ledger/embodied_input.csv --gate-check

# 游戏第三十四轮：世界纵深 / 知识边界 / 环境叙事 / 难度
python3 scripts/game_depth_difficulty.py --prec  # 🔑 先例是访问计数
python3 scripts/game_depth_difficulty.py --know  # 🔑 知识四层边界
python3 scripts/game_depth_difficulty.py --diff  # 🔑 难度八维
python3 scripts/game_depth_difficulty.py --wait  # 🔴 等待可能是玩法
python3 scripts/game_depth_difficulty.py --check ledger/depth_difficulty.csv --gate-check

# 游戏第三十三轮：认知 / 可读复杂度 / 联机契约 / 非死亡失败
python3 scripts/game_cognitive_social.py --four  # 🔑 四层分流（对齐谁）
python3 scripts/game_cognitive_social.py --join  # 🔑 中途加入 8 个真子集
python3 scripts/game_cognitive_social.py --frame # 🔴 确认时刻 5 个候选帧
python3 scripts/game_cognitive_social.py --check ledger/cognitive_social.csv --gate-check

# 游戏第三十二轮：交互事务（建造/交易/目标/成长/回放）
python3 scripts/game_txn_contract.py --deny   # 🔴 放置五种否决
python3 scripts/game_txn_contract.py --trade  # 🔑 预览是可审计净变化
python3 scripts/game_txn_contract.py --obj    # 🔑 目标三个独立视图
python3 scripts/game_txn_contract.py --replay # 🔑 事实 vs 像素
python3 scripts/game_txn_contract.py --check ledger/txn_contract.csv --gate-check

# 游戏第三十一轮：分屏共置 / 多档案 / 天气 / 小地图
python3 scripts/game_colo_weather.py --fov     # 🔑 垂直分屏改变水平 FOV
python3 scripts/game_colo_weather.py --profile # 🔴 档案七类隔离域
python3 scripts/game_colo_weather.py --wgame   # 🔴 天气玩法耦合是事件契约
python3 scripts/game_colo_weather.py --map     # 🔑 小地图两套稳定坐标
python3 scripts/game_colo_weather.py --check ledger/colo_weather.csv --gate-check

# 游戏第三十轮：世界连续性 / 氛围层 / 同帧事件序 / 意图边界
python3 scripts/game_continuity.py --snap   # 🔴 存档六类状态分类器
python3 scripts/game_continuity.py --clock  # 🔴 「同一帧」有四种解释
python3 scripts/game_continuity.py --intent # 🔑 意图边界矩阵 13 边界
python3 scripts/game_continuity.py --amb / --order / --kill / --hud
python3 scripts/game_continuity.py --check ledger/continuity.csv --gate-check
# ⚠️ 无原版证据填 unknown；加 --allow-unknown 才视为「已登记待采集缺口」

# 游戏第二十九轮：失败循环 / 刷新节奏 / 容错撤销 / 物件复位
python3 scripts/game_retry_spawn.py --phases # 🔴 失败十相位
python3 scripts/game_retry_spawn.py --again  # 🔑 「再来一次」六字段
python3 scripts/game_retry_spawn.py --spawn  # 🔴 刷新改变压力曲线
python3 scripts/game_retry_spawn.py --check ledger/retry_spawn.csv --gate-check
python3 scripts/game_fault_reset.py --four   # 🔴 物件状态四层
python3 scripts/game_fault_reset.py --undo / --confirm / --schema
python3 scripts/game_fault_reset.py --check ledger/fault_reset.csv --gate-check

# 游戏第二十八轮：存在感 / 交互仲裁 / 可达性 / 材质 / 音效覆盖
python3 scripts/game_presence_interact.py --ally # 🔴 同伴五个独立事实
python3 scripts/game_presence_interact.py --arb   # 🔴 并发稳定排序键
python3 scripts/game_presence_interact.py --check ledger/presence_interact.csv --gate-check
python3 scripts/game_reach_material.py --reach # 🔴 可达性两阶段
python3 scripts/game_reach_material.py --brdf / --audio / --clock
python3 scripts/game_reach_material.py --check ledger/reach_material.csv --gate-check

# 游戏第二十七轮：环境耦合 / 系统健康 / 统计竞速
python3 scripts/game_coupling_health.py --wind   # 🔴 风场相位是否同源
python3 scripts/game_coupling_health.py --health # 🔴 十一检测项与阈值来源
python3 scripts/game_coupling_health.py --obs    # 🔴 可观测性相位化
python3 scripts/game_coupling_health.py --check ledger/coupling_health.csv --gate-check
python3 scripts/game_stats_runs.py --speed  # 🔴 RTA/IGT 竞速契约
python3 scripts/game_stats_runs.py --a11y / --mod / --stat / --lineage
python3 scripts/game_stats_runs.py --check ledger/stats_runs.csv --gate-check

# 游戏第二十六轮：地形植被 / 水体 / 布料毛发 / 反射透明
python3 scripts/game_terrain_water.py --terrain # 🔴 地形采样精度
python3 scripts/game_terrain_water.py --stable  # 🔑 植被稳定性≠数量
python3 scripts/game_terrain_water.py --under   # 🔴 水下是独立状态机
python3 scripts/game_terrain_water.py --check ledger/terrain_water.csv --gate-check
python3 scripts/game_cloth_reflect.py --reflect # 🔴 反射是可见性语义
python3 scripts/game_cloth_reflect.py --vfx / --loud / --warm / --xr
python3 scripts/game_cloth_reflect.py --check ledger/cloth_reflect.csv --gate-check

# 游戏第二十五轮：持久痕迹 / 通知聚合 / 加载连续性 / 非文本本地化
python3 scripts/game_trace_notify.py --trace  # 🔴 痕迹八组
python3 scripts/game_trace_notify.py --budget # 🔴 痕迹预算是玩法参数
python3 scripts/game_trace_notify.py --merge  # 🔴 四把合并键
python3 scripts/game_trace_notify.py --check ledger/trace_notify.csv --gate-check
python3 scripts/game_load_locale.py --cont   # 🔴 加载八域连续契约
python3 scripts/game_load_locale.py --lip / --bidi / --camera / --ach
python3 scripts/game_load_locale.py --check ledger/load_locale.csv --gate-check

# 游戏第二十四轮：信任边界 / 设置契约 / 帧预算 / 意图层
python3 scripts/game_trust_settings.py --facts  # 🔴 事实表（谁可上报谁须复算）
python3 scripts/game_trust_settings.py --hit    # 🔴 命中四个独立事件
python3 scripts/game_trust_settings.py --default # 🔴 reset to default 五义
python3 scripts/game_trust_settings.py --check ledger/trust_settings.csv --gate-check
python3 scripts/game_budget_intent.py --budget # 🔴 硬预算+弹性池+借还
python3 scripts/game_budget_intent.py --intent # 🔴 意图层稳定排序键
python3 scripts/game_budget_intent.py --life / --death / --variant / --inspect
python3 scripts/game_budget_intent.py --check ledger/budget_intent.csv --gate-check

# 游戏第二十三轮：程序生成 / 阴影玩法信息 / 交互反作用力 / 资源冷却
python3 scripts/game_gen_shadow.py --gen     # 🔴 生成六层与输入闭包
python3 scripts/game_gen_shadow.py --shadow  # 🔴 shadow_authority 先判权威
python3 scripts/game_gen_shadow.py --contact # 🔴 接触阴影是接地感
python3 scripts/game_gen_shadow.py --check ledger/gen_shadow.csv --gate-check
python3 scripts/game_force_resource.py --stall # 🔴 "推不动"五态
python3 scripts/game_force_resource.py --cd    # 🔴 冷却起点八候选
python3 scripts/game_force_resource.py --over / --cut / --soft / --companion
python3 scripts/game_force_resource.py --check ledger/force_resource.csv --gate-check

# 游戏第二十二轮：力反馈 / 数值多值 / 输入硬件 / AI 听觉 / 云存档
python3 scripts/game_haptics_numbers.py --motor   # 🔴 左右马达频段分工
python3 scripts/game_haptics_numbers.py --numbers # 🔴 数值五值分离
python3 scripts/game_haptics_numbers.py --threshold / --round / --trigger / --fallback
python3 scripts/game_haptics_numbers.py --check ledger/haptics_numbers.csv --gate-check
python3 scripts/game_input_percept.py --hw      # 🔴 输入硬件事件表
python3 scripts/game_input_percept.py --hearing # 🔴 AI 听觉先证存在
python3 scripts/game_input_percept.py --cloud / --mouse / --kb / --pass / --focus
python3 scripts/game_input_percept.py --check ledger/input_percept.csv --gate-check

# 游戏第二十一轮：隐性耦合 / 资源生命周期 / 帧契约 / 脚本边界
python3 scripts/game_sim_resource.py --ownership # 🔴 唯一 writer + 读哪一帧
python3 scripts/game_sim_resource.py --audio     # 🔴 碰撞音事件源
python3 scripts/game_sim_resource.py --identity / --pool / --life / --ragdoll
python3 scripts/game_sim_resource.py --check ledger/sim_resource.csv --gate-check
python3 scripts/game_frame_script.py --frame  # 🔴 一帧九个阶段
python3 scripts/game_frame_script.py --lag    # 🔴 延迟一帧五个方向
python3 scripts/game_frame_script.py --error / --script / --scene / --debug
python3 scripts/game_frame_script.py --check ledger/frame_script.csv --gate-check

# 游戏第二十轮：可交付性 / 可观测性 / 组织协作 / 终止条件
python3 scripts/game_delivery_observe.py --manifest  # 🔴 交付清单五问
python3 scripts/game_delivery_observe.py --lastframe # 🔴 最后一帧环形缓冲
python3 scripts/game_delivery_observe.py --firstrun / --residual / --selfcheck
python3 scripts/game_delivery_observe.py --check ledger/delivery_observe.csv --gate-check
python3 scripts/game_team_release.py --readiness # 🔴 发布就绪六项硬门槛
python3 scripts/game_team_release.py --handoff   # 🔴 交接要双向签收
python3 scripts/game_team_release.py --budget / --chaos / --roi / --post
python3 scripts/game_team_release.py --check ledger/team_release.csv --gate-check

# 游戏第十九轮：取证顺序 / 证据仲裁 / 演进治理 / 老玩家迁移
python3 scripts/game_evidence_chain.py --chain  # 🔴 四层证据链
python3 scripts/game_evidence_chain.py --grade  # 🔴 证据八级（7级以上不作验收）
python3 scripts/game_evidence_chain.py --diverge / --unrepro / --bugordesign
python3 scripts/game_evidence_chain.py --check ledger/evidence_chain.csv --gate-check
python3 scripts/game_migration_govern.py --trees  # 🔴 三棵树物理分离
python3 scripts/game_migration_govern.py --mig4   # 🔴 迁移四表不能合并验收
python3 scripts/game_migration_govern.py --dual / --auto / --testbook
python3 scripts/game_migration_govern.py --check ledger/migration_govern.csv --gate-check

# 游戏第十八轮：最坏情况 / 失败路径 / 内容冗余 / 极限边界
python3 scripts/game_degrade_fail.py --order  # 🔴 先砍什么 = 收益×玩法权重
python3 scripts/game_degrade_fail.py --stuck  # 🔴 卡住必须被系统检测
python3 scripts/game_degrade_fail.py --tier / --hyst / --fail6 / --honest
python3 scripts/game_degrade_fail.py --check ledger/degrade_fail.csv --gate-check
python3 scripts/game_content_limit.py --variant  # 🔴 删除结果才是冗余判定
python3 scripts/game_content_limit.py --limits   # 🔴 极限是四维组合
python3 scripts/game_content_limit.py --wait / --undo / --consist
python3 scripts/game_content_limit.py --check ledger/content_limit.csv --gate-check

# 游戏第十七轮：运气 / 技巧天花板 / 重复可玩 / 玩家表达
python3 scripts/game_luck_skill.py --pity      # 🔴 保底六种语义
python3 scripts/game_luck_skill.py --sweep     # 🔴 30/60/120/144Hz 扫描
python3 scripts/game_luck_skill.py --nearmiss / --framebase / --bugfeat
python3 scripts/game_luck_skill.py --check ledger/luck_skill.csv --gate-check
python3 scripts/game_replay_identity.py --ngplus   # 🔴 NG+ 是跨周目契约
python3 scripts/game_replay_identity.py --slot     # 🔴 不存层级会改旧存档
python3 scripts/game_replay_identity.py --showcase / --ugc / --obscure
python3 scripts/game_replay_identity.py --check ledger/replay_identity.csv --gate-check

# 游戏第十六轮：联机延迟 / AI 信任 / 节奏 / 信息架构 / 听觉认知
python3 scripts/game_netfeel_ai_trust.py --rollback # 🔴 回溯不是越长越公平
python3 scripts/game_netfeel_ai_trust.py --interp   # 🔴 外推才制造滑步
python3 scripts/game_netfeel_ai_trust.py --intent / --fairness / --difficulty / --group
python3 scripts/game_netfeel_ai_trust.py --check ledger/netfeel_ai.csv --gate-check
python3 scripts/game_pacing_info.py --timescale  # 🔴 关卡时间 ≠ 战斗时间
python3 scripts/game_pacing_info.py --infoarch / --audible / --savemind / --breath
python3 scripts/game_pacing_info.py --check ledger/pacing_info.csv --gate-check

# 游戏第十五轮：时间推进 / 动态经济 / 声望 / 存档兼容 / 玩法耦合
python3 scripts/game_world_economy.py --jump      # 🔴 跳跃是批量世界模拟
python3 scripts/game_world_economy.py --recovery  # 🔴 没有恢复就写 recovery: none
python3 scripts/game_world_economy.py --clock / --pause / --price / --currency
python3 scripts/game_world_economy.py --check ledger/world_economy.csv --gate-check
python3 scripts/game_faction_save.py --feedback  # 🔴 看见 vs 生效
python3 scripts/game_faction_save.py --corrupt   # 🔴 损坏不得清空进度
python3 scripts/game_faction_save.py --matrix / --slot / --light / --shadow
python3 scripts/game_faction_save.py --check ledger/faction_save.csv --gate-check

# 游戏第十四轮：UI 音效 / 过渡 / UI 动态 / 镜头叙事
python3 scripts/game_ui_sound_transition.py --arbit      # 🔴 同帧多音仲裁
python3 scripts/game_ui_sound_transition.py --transition # 🔴 过渡十阶段
python3 scripts/game_ui_sound_transition.py --uievent / --merge / --input / --failure
python3 scripts/game_ui_sound_transition.py --check ledger/ui_sound_transition.csv --gate-check
python3 scripts/game_ui_motion_camera.py --numroll   # 🔴 数字永远追不上真实值
python3 scripts/game_ui_motion_camera.py --narrative # 🔴 归还不吸附→准星偏
python3 scripts/game_ui_motion_camera.py --reject / --scalable / --progress / --env
python3 scripts/game_ui_motion_camera.py --check ledger/ui_motion_camera.csv --gate-check

# 游戏第十三轮：战斗规则 / BOSS / 解锁节奏 / 输入反馈 / 动作仲裁
python3 scripts/game_combat_rules.py --rounding  # 🔴 保底 1 的位置
python3 scripts/game_combat_rules.py --dot       # 🔴 DOT 快照是版本控制
python3 scripts/game_combat_rules.py --boss / --move / --immunity / --spawn
python3 scripts/game_combat_rules.py --check ledger/combat_rules.csv --gate
python3 scripts/game_progress_input.py --arbiter # 🔴 动作闭包非物理可通行
python3 scripts/game_progress_input.py --input / --refresh / --gate / --spectate
python3 scripts/game_progress_input.py --check ledger/progress_input.csv --gate-check

# 游戏第十二轮：任务状态 / 对话 / 库存手感 / 配点 / 死亡流程
python3 scripts/game_quest_dialog.py --quest    # 🔴 expired ≠ failed
python3 scripts/game_quest_dialog.py --timeline  # 🔴 跳过六级
python3 scripts/game_quest_dialog.py --objective / --complete / --variable
python3 scripts/game_quest_dialog.py --check ledger/quest_dialog.csv --gate
python3 scripts/game_inventory_flow.py --sort   # 🔴 稳定排序键
python3 scripts/game_inventory_flow.py --travel  # 🔴 快速旅行是模拟模式入口
python3 scripts/game_inventory_flow.py --pickup / --equip / --point / --respawn
python3 scripts/game_inventory_flow.py --check ledger/inventory_flow.csv --gate

# 游戏第十一轮：声音传播 / 可读性 / 感知性能 / 环境交互 / 拍摄
python3 scripts/game_audio_read.py --propagation  # 🔴 七条传播通道
python3 scripts/game_audio_read.py --reverb       # 🔴 混响区是声音版隐形墙
python3 scripts/game_audio_read.py --readability / --voice / --exposure
python3 scripts/game_audio_read.py --check ledger/audio_read.csv --gate
python3 scripts/game_perf_interact.py --door      # 🔴 门可否中途取消
python3 scripts/game_perf_interact.py --perf / --jit / --photo / --replay
python3 scripts/game_perf_interact.py --check ledger/perf_interact.csv --gate

# 游戏第十轮：世界模拟 / 身体 / 社交 / 元游戏 / 反馈 / 浮点
python3 scripts/game_world_body.py --offline   # 🔴 离线推进六层
python3 scripts/game_world_body.py --bodypart   # 🔴 两条腿各伤 50% = 一条腿 100%？
python3 scripts/game_world_body.py --world / --ecology / --encumbrance / --appearance
python3 scripts/game_world_body.py --check ledger/world_body.csv --gate
python3 scripts/game_social_meta.py --ping      # 🔴 差异不在有没有 ping
python3 scripts/game_social_meta.py --float     # 🔴 确定性下沉到编译层
python3 scripts/game_social_meta.py --ngplus / --feedback / --confirm / --a11y
python3 scripts/game_social_meta.py --check ledger/social_meta.csv --gate

# 游戏第九轮：时间语义 / 关卡空间 / 教程 / 难度 / pacing / AA
python3 scripts/game_time_pacing.py --timedomain  # 🔴 一张 timeScale 覆盖不了
python3 scripts/game_time_pacing.py --timer       # 🔴 不能写 t -= dt
python3 scripts/game_time_pacing.py --scale / --slowmo / --pacing / --aa / --taa
python3 scripts/game_time_pacing.py --check ledger/time_pacing.csv --gate
python3 scripts/game_level_balance.py --level / --boundary / --tutorial
python3 scripts/game_level_balance.py --difficulty / --dda / --savestate
python3 scripts/game_level_balance.py --check ledger/level_balance.csv --gate

# 游戏第八轮：战斗手感 / 移动手感 / 会话 / 粒子 / 超分
python3 scripts/game_feel.py --hitstop     # 🔴 顿帧：冻结谁比冻结多久更重要
python3 scripts/game_feel.py --coyote      # 🔴 土狼时间是有限有效窗口
python3 scripts/game_feel.py --varjump     # 🔴 可变跳跃三类语义
python3 scripts/game_feel.py --stagger / --dmg / --shake / --ground / --vehicle
python3 scripts/game_feel.py --check ledger/game_feel.csv --gate
python3 scripts/game_session.py --session / --reconnect / --lockon / --cancel
python3 scripts/game_session.py --particle / --upscale / --hdr / --stealth
python3 scripts/game_session.py --check ledger/session.csv --gate

# 游戏第七轮：流式 / 并发 / 热更新 / 内存 / 默认值
python3 scripts/game_stream_thread.py --stream     # 🔴 流式七态
python3 scripts/game_stream_thread.py --hyst       # 🔴 hysteresis 是迟滞环
python3 scripts/game_stream_thread.py --world / --thread / --order / --parallel
python3 scripts/game_stream_thread.py --check ledger/stream_thread.csv --gate
python3 scripts/game_hotfix_mem.py --hotfix        # 🔴 热更新八态
python3 scripts/game_hotfix_mem.py --defaults      # 🔴 另外 90% 未配置默认值
python3 scripts/game_hotfix_mem.py --gc / --snapshot / --serialize / --depgraph
python3 scripts/game_hotfix_mem.py --check ledger/hotfix_mem.csv --gate

# 游戏第六轮：动画 / UI / 物理参数链
python3 scripts/game_animation.py --root       # 🔴 根运动按源权重混合
python3 scripts/game_animation.py --compress   # 🔴 末端误差不是平均误差
python3 scripts/game_animation.py --retarget / --fsm / --blend / --ik / --notify
python3 scripts/game_animation.py --check ledger/animation.csv --gate
python3 scripts/game_ui_physics.py --layout    # 🔴 不是最终 pixel rect
python3 scripts/game_ui_physics.py --nav       # 🔴 导航是显式图
python3 scripts/game_ui_physics.py --matrix / --material / --contact / --ccd / --substep
python3 scripts/game_ui_physics.py --check ledger/ui_physics.csv --gate

# 游戏第五轮：编辑器 / 构建 / 配置 / 输入设备 / 存档链
python3 scripts/game_editor_data.py --editor       # 编辑器六张清单
python3 scripts/game_editor_data.py --import       # 🔴 导入设置是体验参数
python3 scripts/game_editor_data.py --build / --hotreload / --config / --magic
python3 scripts/game_editor_data.py --modifier     # 🔴 buff 叠加极细细节
python3 scripts/game_editor_data.py --check ledger/editor_data.csv --gate
python3 scripts/game_input_ops.py --mouse / --keyboard / --gamepad / --touch
python3 scripts/game_input_ops.py --savechain / --ops / --crash / --voice
python3 scripts/game_input_ops.py --check ledger/input_ops.csv --gate

# 游戏第四轮：延迟 / 相机 / 音频 / 渲染 / 可玩性
python3 scripts/game_latency_camera.py --chain      # 🔴 输入到光子九段链路
python3 scripts/game_latency_camera.py --swapchain  # DXGI 默认三帧队列
python3 scripts/game_latency_camera.py --camera / --shake / --fov / --fp
python3 scripts/game_latency_camera.py --check ledger/latency_camera.csv --gate
python3 scripts/game_audio_render.py --audio / --music / --spatial / --mix / --voip
python3 scripts/game_audio_render.py --lighting / --visibility / --postfx / --quality
python3 scripts/game_audio_render.py --playability / --pcg
python3 scripts/game_audio_render.py --check ledger/audio_render.csv --gate

# 游戏第三轮：功能表面 / 版本 / 网络 / 模组
python3 scripts/game_surface.py --first-run     # 🔴 首次启动默认值
python3 scripts/game_surface.py --ui-restore    # 菜单 UI 状态恢复
python3 scripts/game_surface.py --input-prompt  # 输入提示图标切换 + ABXY
python3 scripts/game_surface.py --focus         # 暂停/失焦 12 维度
python3 scripts/game_surface.py --check ledger/game_surface.csv --gate
python3 scripts/game_net_mod.py --version       # 版本基准指纹
python3 scripts/game_net_mod.py --sync / --metrics / --weather / --inject
python3 scripts/game_net_mod.py --mod / --platform / --patch
python3 scripts/game_net_mod.py --check ledger/net_mod.csv --gate

# 跨引擎迁移与二次创作（主场景）
python3 scripts/engine_migration.py --ownership    # 项目性质与法律门禁开关
python3 scripts/engine_migration.py --axes         # 🔴 坐标系（最容易错）
python3 scripts/engine_migration.py --map          # 引擎概念映射矩阵
python3 scripts/engine_migration.py --assets / --shader / --physics / --anim
python3 scripts/engine_migration.py --recreate     # 二次创作四分类
python3 scripts/engine_migration.py --check ledger/engine_matrix.csv --gate

# 安全信任 / 网络韧性 / 无障碍与 IME
python3 scripts/security_trust.py --signing         # 时间戳不是「签一次管永久」
python3 scripts/security_trust.py --update / --webview / --secrets / --sandbox
python3 scripts/security_trust.py --check ledger/security_gates.csv --gate
python3 scripts/network_resilience.py --layers / --faults / --proxy / --retry
python3 scripts/network_resilience.py --check ledger/network_matrix.csv --gate
python3 scripts/a11y_ime.py --ime                   # 中文/日文输入法全事件
python3 scripts/a11y_ime.py --screen-reader / --tree / --contrast / --keyboard
python3 scripts/a11y_ime.py --check ledger/a11y_matrix.csv --gate

# 状态迁移 / IPC / 可观测性
python3 scripts/state_migration.py --silent            # 六类静默失败
python3 scripts/state_migration.py --unknown           # 未知字段策略
python3 scripts/state_migration.py --fs                # 路径与文件系统陷阱
python3 scripts/state_migration.py --config            # 配置位置语义
python3 scripts/state_migration.py --check ledger/migration_fields.csv --gate
python3 scripts/ipc_surface.py --list                  # IPC 机制
python3 scripts/ipc_surface.py --shell                 # Shell 集成取证点
python3 scripts/ipc_surface.py --check ledger/ipc_contract.csv --gate
python3 scripts/log_parity.py --drift / --layers / --crash
python3 scripts/log_parity.py --check ledger/telemetry_contract.csv --gate

# 原版机制与目标栈
python3 scripts/wpf_mechanism.py --list            # 31 条机制
python3 scripts/wpf_mechanism.py --precedence      # 依赖属性值优先级链
python3 scripts/wpf_mechanism.py --dpi             # DPI 基线矩阵
python3 scripts/target_stack.py --tauri            # Tauri 2 迁移事实
python3 scripts/target_stack.py --webview          # 三 WebView 差异基线
python3 scripts/target_stack.py --check ledger/capabilities.json --gate
python3 scripts/value_fidelity.py --charsets       # 字符/编码/时区坑
python3 scripts/value_fidelity.py --culture        # 文化格式化差异分类

# 许可与动效
python3 scripts/license_gate.py --init ledger/licenses.md
python3 scripts/license_gate.py --check ledger/licenses.md --gate
python3 scripts/motion_check.py --init motion/                      # 动效契约骨架
python3 scripts/motion_check.py --compare --old mo.json --new mn.json --gate

# S1：建台账
python3 scripts/ledger.py --init --src <原版src> --ledger ledger/files.csv

# S2：按档位推进（不许跳档，中等文件最肥）
python3 scripts/ledger.py --by-band --band "中等60-150" --ledger ledger/files.csv
python3 scripts/comment_extract.py src --recursive --ext .cs --negative

# S2 门禁
python3 scripts/ledger.py --gate --src <原版src> --ledger ledger/files.csv
python3 scripts/renumber_check.py ledger/features.md
python3 scripts/coverage_gate.py ledger/unknown.md ledger/features.md

# S2B：BUG 分诊（挖到可疑处先记卡，简单项当场修）
python3 scripts/bug_triage.py ledger/bugs.md            # 看统计与警告
python3 scripts/bug_triage.py ledger/bugs.md --gate     # CI：有 P0/P1 未处置则退出码 1
python3 scripts/bug_triage.py ledger/bugs.md --strict   # 警告也算阻塞

# S4/S6/S7：跨端契约
node scripts/cross-end-check.mjs --strict

# S2M：机器证据（正则容易漏，用 AST 补）
python3 scripts/ast_query.py --check                                   # 先确认工具是真 ast-grep
python3 scripts/tree_sitter_parse.py --src <原版src> --ext .cs         # 机器能不能读懂
python3 scripts/ast_query.py --rules rules/sg --src <src> --out ledger/findings.json
python3 scripts/ast_query.py --rules rules/sg --src <src> --fallback-regex   # 允许降级（标 low）

# S2A：资产与资源（图标/字体/音效/色板 —— 像素藏在资源里）
python3 scripts/asset_inventory.py --src <资源目录> --code <代码目录> --out ledger/assets.csv --gate
python3 scripts/asset_inventory.py --src <资源目录> --code <代码目录> --out ledger/assets.csv --list-license
#  输出：资源清单 + 孤儿资源(0引用) + 悬空引用(文件不存在,硬错误) + 许可待确认

# S2T：文案（不许"重写得更清楚" —— 用户肌肉记忆认的是原句）
python3 scripts/text_extract.py --src <原版> --out ledger/texts-old.csv
python3 scripts/text_extract.py --src <新版> --out ledger/texts-new.csv
python3 scripts/text_extract.py --compare --old ledger/texts-old.csv --new ledger/texts-new.csv --gate
#  输出三类：疑似改写(相似度≥50%) / 原版有新版无(丢失) / 新版多出

# S2P：体验参数（tips 延迟/间距/动画/阈值 —— 不记录就会丢失）
python3 scripts/param_extract.py --src <原版src> --out ledger/params-old.csv
python3 scripts/param_extract.py --src <新版src> --out ledger/params-new.csv
python3 scripts/param_extract.py --compare --old ledger/params-old.csv --new ledger/params-new.csv --gate
#  输出四类：疑似改名 / 原版有新版无(会丢失) / 值不同 / 新版多出

# S7V：视觉状态契约
python3 scripts/visual_check.py --init --states visual/states --feature "#1" --name <功能>.<状态>
python3 scripts/visual_check.py --states visual/states --approved visual/approved --gate

# S6：无编译环境静态验证
python3 scripts/brace_check.py src-tauri/src/fpx/mod.rs
python3 scripts/brace_check.py src-tauri/src/fpx/mod.rs --diff
```

---

## 换项目要改什么（`cross-end-check.mjs` 顶部 CONFIG）

| 项 | 本项目值 | 改成你的 |
|---|---|---|
| Rust 源目录 | `src-tauri/src/fpx` | 你的路径 |
| 注册文件 | `src-tauri/src/main.rs` | 你的入口 |
| 注册写法 | `fpx::fpx_xxx` | 你的形式（改 `registerPattern`） |
| 前端调用文件 | `plugins/project-group/api.ts` | 你的路径 |
| 调用写法 | `call<T>('cmd', {...})` | 你的封装（改 `apiCallPattern`） |
| 注入参数 | `app` / `state` | 你的（如 `window` / `db`） |
| 结构体别名 | `ChainActionItem → ChainAction` | 你的改名映射 |
| 内部结构体 | `LinkRecord` | 你的 |
| DTO 文件列表 | model/backup/screen/chain/watch/editor | 你的 |

也可用外部配置：`node cross-end-check.mjs --config my.json`（字段同名，`injectedParams`/`internalOnly` 传数组）。

---

## ⚠️ 写完/接手必须先做故障注入

**脚本第一次跑就"全绿"，要怀疑脚本是死的。**

| 故障 | 注入方式 | 期望 |
|---|---|---|
| F1 | api.ts `{ new_name: newName }` → `{ newName }` | `[参数名不符]` + `[必传参数缺失]` |
| F2 | types.ts 删掉一个字段 | `[DTO 字段缺失]` |
| F3 | Rust 加一个非 Option 参数 | `[必传参数缺失]` |
| F4 | main.rs 删掉一行注册 | `[注册缺失]` |

```bash
cp api.ts /tmp/api.bak && sed -i 's/xxx/yyy/' api.ts
node scripts/cross-end-check.mjs | grep "❌"
cp /tmp/api.bak api.ts && git status --short   # 应该只剩脚本文件
```

**本仓库的 `cross-end-check.mjs` 已对上述四类做过实测，均能命中。**
