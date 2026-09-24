#!/usr/bin/env python3
"""一键跑全部门禁 —— 收工判定不由模型自述决定，由脚本决定。

**为什么需要**：门禁散在十几个脚本里，逐个跑容易漏。
本脚本按阶段顺序跑完**所有可自动判定的门禁**，统一输出通过/阻断。

不代替人工的项（脚本会明确列出为"需人工"）：
  golden 人工批准、视觉逐张签字、许可证据、崩溃恢复实测、
  多显示器实测、无鼠标走全流程、旧数据逐字段比对

用法:
  run_all_gates.py --work work/                     # 跑全部（缺文件则跳过并提示）
  run_all_gates.py --work work/ --strict            # 缺文件也算阻断
  run_all_gates.py --work work/ --list              # 只列出门禁清单，不执行

退出码: 0 全部通过 / 1 有硬门禁阻断 / 2 用法错误
"""
import argparse
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

# 法律/许可类门禁 ID（**仅在 ownership == third_party 时生效**）
LEGAL_GATES = {"G21"}


def read_ownership(work):
    """读项目性质。**文件不存在时默认 self** —— 本 Skill 主场景是自有项目
    跨引擎搬迁与二次创作，不应让许可顾虑阻碍重制。"""
    for name in ("project.yaml", "project.yml", "project.json"):
        path = os.path.join(work, "ledger", name)
        if not os.path.exists(path):
            continue
        try:
            raw = open(path, encoding="utf-8", errors="replace").read()
        except Exception:
            continue
        for line in raw.splitlines():
            if line.strip().startswith("ownership"):
                v = line.split(":", 1)[-1].strip().strip('"').strip("'")
                v = v.split("#")[0].strip()
                if v:
                    return v.lower()
    return "self"

# (门禁ID, 名称, 命令模板, 硬/软, 需要的文件)
# 🔑 第八十一轮：**刻意重复**的门禁命令 —— 白名单（必须写明理由）。
#
# 🔴 默认规则：两条门禁跑**同一条命令** → 违反独立性，几乎一定是误登记。
# 🔑 但存在刻意例外：G382/G383/G384 共用 `--all`，是为了**减少子进程**，
#    三者语义不同（文档有代码无 / 已写的持续兑现 / 有没有写），
#    失败定位靠 G385（`--audit-all`）与各自的语义分工。
# 🔴 登记在此处**必须带理由**；`--check-dup-cmds` 会校验：
#    - 每条登记都**非空理由**
#    - 每条登记的门禁**真实存在**且**命令真的一致**（防止登记过时）
# 🔑 值 = (`批准重复的门禁 ID 集合`, `理由`)
#    🔴 第八十一轮实测修正：第一版**按命令 key 登记**，
#       导致往同一组塞一条**未登记的 G499** 也照样放行（整组被判"已登记"）。
#    🔑 改为**逐个 ID 校验**：组内**每一条**都必须出现在批准集合里。
# 🔑 第八十二轮：**共用命令 → 必须有完整性门禁**（G385 联动）。
#    🔴 第八十一轮指引：三者共用 `--all` 时，**必须**存在对应的完整性门禁。
#    🔑 否则"共用"就是纯风险：一条命令挂三条门禁，谁也不知道有没有漏跑。
# 🔑 第八十三轮：值 = (`完整性门禁 ID`, **`它守的是什么`**)
#    🔴 第八十二轮诚实结论：`'G385'` 只是**写死的门禁号**，
#        只校验了"存在且不是 `--all`" —— 若改成另一个
#        "存在但无关"的门禁号，检查**发现不了**。
#    🔑 本轮加 **`guards` 语义字段**，三层校验：
#       ① `guards` 必须**非空**（说得出守的是什么）
#       ② 守卫门禁的**命令**必须含 `guards` 声明的能力关键词
#          —— 使"存在但无关"无法蒙混
#       ③ 守卫门禁仍**不得**跑被守护的那条命令（自证循环）
DUP_CMDS_GUARDIAN = {
    '{s}/claim_verify.py --all': (
        'G385',
        'audit-all',        # 🔑 守的是"**三段是否都执行**"；命令须含此关键词
    ),
}

INTENTIONAL_DUP_CMDS = {
    '{s}/claim_verify.py --all': (
        {'G382', 'G383', 'G384'},
        'G382/G383/G384 共用 --all 只为**减少进程数**；'
        '三者语义不同，完整性由 G385（--audit-all）独立守。'
    ),
}

GATES = [
    ("G1", "台账 100% 精读",
     ["{py}", "{s}/ledger.py", "--work", "{w}", "--check"], "hard",
     ["ledger.csv"]),
    ("G2", "unknown 清零",
     ["{py}", "{s}/coverage_gate.py", "--work", "{w}", "--gate"], "hard",
     ["ledger/unknown.md"]),
    ("G3", "编号未重排",
     ["{py}", "{s}/renumber_check.py", "--work", "{w}"], "hard",
     ["ledger/features.md"]),
    ("G4", "括号平衡",
     ["{py}", "{s}/brace_check.py", "--src", "{w}/src"], "hard",
     ["src"]),
    ("G5", "config 字段差集",
     ["{py}", "{s}/config_field_diff.py", "--old", "{w}/old.json",
      "--new", "{w}/new.json", "--gate"], "hard", ["old.json", "new.json"]),
    ("G6", "跨端契约四类检查",
     ["node", "{s}/cross-end-check.mjs", "--src", "{w}", "--strict"], "hard",
     ["src"]),
    ("G11", "BUG 分诊无未处置",
     ["{py}", "{s}/bug_triage.py", "--file", "{w}/ledger/bugs.md", "--gate"], "hard",
     ["ledger/bugs.md"]),
    ("G15", "体验参数无缺失",
     ["{py}", "{s}/param_extract.py", "--compare", "--old",
      "{w}/ledger/params-old.csv", "--new", "{w}/ledger/params-new.csv", "--gate"],
     "hard", ["ledger/params-old.csv", "ledger/params-new.csv"]),
    ("G16", "资产无悬空引用",
     ["{py}", "{s}/asset_inventory.py", "--src", "{w}/assets", "--code",
      "{w}/src", "--out", "{w}/ledger/assets.csv", "--gate"], "hard",
     ["assets", "src"]),
    ("G17", "许可四态无阻断",
     ["{py}", "{s}/license_gate.py", "--check", "{w}/ledger/licenses.md", "--gate"],
     "hard", ["ledger/licenses.md"]),
    ("G18", "无丢失文案",
     ["{py}", "{s}/text_extract.py", "--compare", "--old",
      "{w}/ledger/texts-old.csv", "--new", "{w}/ledger/texts-new.csv", "--gate"],
     "hard", ["ledger/texts-old.csv", "ledger/texts-new.csv"]),
    ("G22", "动效时序在容差内",
     ["{py}", "{s}/motion_check.py", "--compare", "--old",
      "{w}/motion-old.json", "--new", "{w}/motion-new.json", "--gate"], "soft",
     ["motion-old.json", "motion-new.json"]),
    ("G23", "树对齐覆盖率达标",
     ["{py}", "{s}/tree_align.py", "--old", "{w}/old.uia.json", "--new",
      "{w}/new.a11y.json", "--out", "{w}/ledger/alignment.json", "--gate"],
     "hard", ["old.uia.json", "new.a11y.json"]),
    ("G24", "差异有根因归类",
     ["{py}", "{s}/diff_classify.py", "--old", "{w}/old.png", "--new",
      "{w}/new.png", "--out", "{w}/ledger/diff.json", "--gate"], "hard",
     ["old.png", "new.png"]),
    ("G26", "环境锁一致",
     ["{py}", "{s}/env_lock.py", "--check", "{w}/environment.lock", "--gate"],
     "hard", ["environment.lock"]),
    ("G27", "差分测试无真回归",
     ["{py}", "{s}/diff_fuzz.py", "--pairs", "{w}/pairs.jsonl",
      "--out", "{w}/ledger/oracle.json", "--gate"], "hard", ["pairs.jsonl"]),
    ("G31", "功能对照表无未定项",
     ["{py}", "{s}/feature_matrix.py", "--check", "{w}/ledger/feature_matrix.md",
      "--features", "{w}/ledger/features.md", "--gate"], "hard",
     ["ledger/feature_matrix.md", "ledger/features.md"]),
    ("G32", "文本排版五维一致",
     ["{py}", "{s}/text_layout.py", "--old", "{w}/ledger/texts-old.csv", "--new",
      "{w}/ledger/texts-new.csv", "--out", "{w}/ledger/text_layout.json", "--gate"],
     "hard", ["ledger/texts-old.csv", "ledger/texts-new.csv"]),
    ("G33", "故障矩阵六栏齐全",
     ["{py}", "{s}/fault_matrix.py", "--check", "{w}/ledger/faults.csv",
      "--gate"], "hard", ["ledger/faults.csv"]),
    ("G34", "安装契约与残留 owner",
     ["{py}", "{s}/install_contract.py", "--check", "{w}/ledger/install.md",
      "--gate"], "hard", ["ledger/install.md"]),
    ("G37", "能力契约已探测",
     ["{py}", "{s}/tool_run.py", "--check-all", "--json",
      "{w}/ledger/capability.json", "--gate"], "hard", []),
    ("G38", "证据库无未判重复",
     ["{py}", "{s}/tools/duckdb_evidence.py", "--work", "{w}", "--dup"], "soft",
     ["ledger/features.md"]),
    # ---- 游戏引擎复刻 ----
    ("G41", "回放 manifest 无缺项",
     ["{py}", "{s}/game_replay.py", "--check", "{w}/ledger/replay_manifest.yaml",
      "--gate"], "hard", ["ledger/replay_manifest.yaml"]),
    ("G43", "渲染基线完整无污染",
     ["{py}", "{s}/game_render.py", "--baseline", "{w}/ledger/render_baseline.yaml",
      "--gate"], "hard", ["ledger/render_baseline.yaml"]),
    ("G44", "资产取证齐全",
     ["{py}", "{s}/game_asset.py", "--check", "{w}/ledger/game_assets.csv",
      "--gate"], "hard", ["ledger/game_assets.csv"]),
    # ---- 运行时取证 / 二进制覆盖 / AI 门禁 ----
    ("G47", "运行时取证台账完整",
     ["{py}", "{s}/runtime_forensics.py", "--check",
      "{w}/ledger/runtime_forensics.csv", "--gate"], "hard",
     ["ledger/runtime_forensics.csv"]),
    ("G48", "无未覆盖函数",
     ["{py}", "{s}/binary_coverage.py", "--check",
      "{w}/ledger/binary_coverage.csv", "--gate"], "hard",
     ["ledger/binary_coverage.csv"]),
    ("G49", "上下文包无密钥泄露",
     ["{py}", "{s}/context_pack.py", "--scan", "{w}/src", "--gate"], "hard", ["src"]),
    ("G50", "AI 变更有人工签名",
     ["{py}", "{s}/context_pack.py", "--review-check", "{w}/ledger/ai_changes.json",
      "--gate"], "hard", ["ledger/ai_changes.json"]),
    # ---- 第九轮：原版机制与能力矩阵 ----
    ("G53", "WPF 机制清单有运行时取证与可判定验收",
     ["{py}", "{s}/wpf_mechanism.py", "--check", "{w}/ledger/wpf_mechanisms.csv",
      "--gate"], "hard", ["ledger/wpf_mechanisms.csv"]),
    ("G54", "Tauri 能力无 wildcard scope",
     ["{py}", "{s}/target_stack.py", "--check", "{w}/ledger/capabilities.json",
      "--gate"], "hard", ["ledger/capabilities.json"]),
    ("G55", "浮点/序列化逐字段保真",
     ["{py}", "{s}/value_fidelity.py", "--float", "--old", "{w}/baseline/old.json",
      "--new", "{w}/baseline/new.json", "--gate"], "hard",
     ["baseline/old.json", "baseline/new.json"]),
    # ---- 第十轮：状态迁移 / IPC / 可观测性 ----
    ("G57", "迁移矩阵无 ignore 策略且已四层对账",
     ["{py}", "{s}/state_migration.py", "--check",
      "{w}/ledger/migration_fields.csv", "--gate"], "hard",
     ["ledger/migration_fields.csv"]),
    ("G58", "IPC 契约消息边界与失败模式齐全",
     ["{py}", "{s}/ipc_surface.py", "--check", "{w}/ledger/ipc_contract.csv",
      "--gate"], "hard", ["ledger/ipc_contract.csv"]),
    ("G59", "遥测契约 PII 分类 + 采样声明 + 旧版证据",
     ["{py}", "{s}/log_parity.py", "--check", "{w}/ledger/telemetry_contract.csv",
      "--gate"], "hard", ["ledger/telemetry_contract.csv"]),
    # ---- 第十一轮：安全信任 / 网络韧性 / 无障碍与 IME ----
    ("G62", "安全门禁有负向测试且拒绝路径已验证",
     ["{py}", "{s}/security_trust.py", "--check", "{w}/ledger/security_gates.csv",
      "--gate"], "hard", ["ledger/security_gates.csv"]),
    ("G63", "网络故障矩阵有原版期望与幂等判定",
     ["{py}", "{s}/network_resilience.py", "--check", "{w}/ledger/network_matrix.csv",
      "--gate"], "hard", ["ledger/network_matrix.csv"]),
    ("G64", "无障碍矩阵有原版轨迹与平台/IME 版本矩阵",
     ["{py}", "{s}/a11y_ime.py", "--check", "{w}/ledger/a11y_matrix.csv",
      "--gate"], "hard", ["ledger/a11y_matrix.csv"]),
    # ---- 游戏深化：内容/战斗/AI/数值/存档 ----
    ("G67", "**关卡内容账本一致**（实体/触发器/生成点/隐藏）",
     ["{py}", "{s}/game_content.py", "--check", "{w}/ledger/level_manifest.csv",
      "--gate"], "hard", ["ledger/level_manifest.csv"]),
    ("G68", "**战斗帧数据与判定盒一致**",
     ["{py}", "{s}/game_combat_ai.py", "--check", "{w}/ledger/combat_ai.csv",
      "--gate"], "hard", ["ledger/combat_ai.csv"]),
    ("G69", "**RNG 可重放且未丢弃未知存档字段**",
     ["{py}", "{s}/game_rng_save.py", "--check", "{w}/ledger/rng_save.csv",
      "--gate"], "hard", ["ledger/rng_save.csv"]),
    # ---- 游戏第三轮：功能表面 / 版本 / 网络 / 模组 ----
    ("G72", "**功能表面一致**（首次启动/UI恢复/输入提示/失焦）",
     ["{py}", "{s}/game_surface.py", "--check", "{w}/ledger/game_surface.csv",
      "--gate"], "hard", ["ledger/game_surface.csv"]),
    ("G73", "**版本基准已冻结**",
     ["{py}", "{s}/game_net_mod.py", "--check", "{w}/ledger/net_mod.csv",
      "--gate"], "hard", ["ledger/net_mod.csv"]),
    # ---- 游戏第四轮：延迟/相机/音频/渲染/可玩性 ----
    ("G76", "**输入到光子延迟与相机手感可复现测量**",
     ["{py}", "{s}/game_latency_camera.py", "--check",
      "{w}/ledger/latency_camera.csv", "--gate"], "hard",
     ["ledger/latency_camera.csv"]),
    ("G77", "**音频信号链与渲染设置一致**",
     ["{py}", "{s}/game_audio_render.py", "--check",
      "{w}/ledger/audio_render.csv", "--gate"], "hard",
     ["ledger/audio_render.csv"]),
    # ---- 游戏第五轮：编辑器/构建/配置/输入设备/存档链 ----
    ("G80", "**导入设置与配置边界已固化**",
     ["{py}", "{s}/game_editor_data.py", "--check",
      "{w}/ledger/editor_data.csv", "--gate"], "hard",
     ["ledger/editor_data.csv"]),
    ("G81", "**输入设备参数与存档迁移链一致**",
     ["{py}", "{s}/game_input_ops.py", "--check",
      "{w}/ledger/input_ops.csv", "--gate"], "hard",
     ["ledger/input_ops.csv"]),
    # ---- 游戏第六轮：动画 / UI / 物理深化 ----
    ("G83", "**动画参数链一致**（含末端误差）",
     ["{py}", "{s}/game_animation.py", "--check",
      "{w}/ledger/animation.csv", "--gate"], "hard",
     ["ledger/animation.csv"]),
    ("G84", "**UI 布局链与物理参数链一致**",
     ["{py}", "{s}/game_ui_physics.py", "--check",
      "{w}/ledger/ui_physics.csv", "--gate"], "hard",
     ["ledger/ui_physics.csv"]),
    # ---- 游戏第七轮：流式/并发/热更新/内存/默认值 ----
    ("G86", "**流式七态与多线程顺序契约一致**",
     ["{py}", "{s}/game_stream_thread.py", "--check",
      "{w}/ledger/stream_thread.csv", "--gate"], "hard",
     ["ledger/stream_thread.csv"]),
    ("G87", "**热更新八态与内存/默认值一致**",
     ["{py}", "{s}/game_hotfix_mem.py", "--check",
      "{w}/ledger/hotfix_mem.csv", "--gate"], "hard",
     ["ledger/hotfix_mem.csv"]),
    # ---- 游戏第八轮：战斗手感/移动手感/会话/粒子/超分 ----
    ("G89", "**战斗手感参数链一致**（顿帧冻结域/跳跃宽容/霸体）",
     ["{py}", "{s}/game_feel.py", "--check",
      "{w}/ledger/game_feel.csv", "--gate"], "hard",
     ["ledger/game_feel.csv"]),
    ("G90", "**锁定/取消/会话/粒子/超分一致**",
     ["{py}", "{s}/game_session.py", "--check",
      "{w}/ledger/session.csv", "--gate"], "hard",
     ["ledger/session.csv"]),
    # ---- 游戏第九轮：时间域/关卡/教程/难度/pacing/AA ----
    ("G93", "**时间域与暂停掩码一致**（计时器已声明时钟）",
     ["{py}", "{s}/game_time_pacing.py", "--check",
      "{w}/ledger/time_pacing.csv", "--gate"], "hard",
     ["ledger/time_pacing.csv"]),
    ("G94", "**关卡体验/教程/难度关系网一致**",
     ["{py}", "{s}/game_level_balance.py", "--check",
      "{w}/ledger/level_balance.csv", "--gate"], "hard",
     ["ledger/level_balance.csv"]),
    # ---- 游戏第十轮：世界模拟/身体/社交/元游戏/反馈/浮点 ----
    ("G97", "**世界模拟与身体状态一致**（离线六层/部位/负重舍入）",
     ["{py}", "{s}/game_world_body.py", "--check",
      "{w}/ledger/world_body.csv", "--gate"], "hard",
     ["ledger/world_body.csv"]),
    ("G98", "**社交表达/元游戏/反馈仲裁/浮点一致**",
     ["{py}", "{s}/game_social_meta.py", "--check",
      "{w}/ledger/social_meta.csv", "--gate"], "hard",
     ["ledger/social_meta.csv"]),
    # ---- 游戏第十一轮：声音传播/可读性/感知性能/环境交互/拍摄回放 ----
    ("G101", "**音频传播七通道与可读性一致**",
     ["{py}", "{s}/game_audio_read.py", "--check",
      "{w}/ledger/audio_read.csv", "--gate"], "hard",
     ["ledger/audio_read.csv"]),
    ("G102", "**感知性能与环境交互一致**",
     ["{py}", "{s}/game_perf_interact.py", "--check",
      "{w}/ledger/perf_interact.csv", "--gate"], "hard",
     ["ledger/perf_interact.csv"]),
    # ---- 游戏第十二轮：任务/对话/库存/配点/地图/死亡流程 ----
    ("G105", "**任务状态与目标级语义一致**",
     ["{py}", "{s}/game_quest_dialog.py", "--check",
      "{w}/ledger/quest_dialog.csv", "--gate"], "hard",
     ["ledger/quest_dialog.csv"]),
    ("G106", "**库存手感与流程事务一致**",
     ["{py}", "{s}/game_inventory_flow.py", "--check",
      "{w}/ledger/inventory_flow.csv", "--gate"], "hard",
     ["ledger/inventory_flow.csv"]),
    # ---- 游戏第十三轮：战斗规则/BOSS/解锁节奏/输入反馈/动作仲裁 ----
    ("G109", "**战斗规则合约与 BOSS 行为契约一致**",
     ["{py}", "{s}/game_combat_rules.py", "--check",
      "{w}/ledger/combat_rules.csv", "--gate"], "hard",
     ["ledger/combat_rules.csv"]),
    ("G110", "**解锁节奏与输入反馈一致**",
     ["{py}", "{s}/game_progress_input.py", "--check",
      "{w}/ledger/progress_input.csv", "--gate-check"], "hard",
     ["ledger/progress_input.csv"]),
    # ---- 游戏第十四轮：UI 音效/过渡/UI 动态/镜头叙事 ----
    ("G113", "**UI 音效交互层与过渡体验一致**",
     ["{py}", "{s}/game_ui_sound_transition.py", "--check",
      "{w}/ledger/ui_sound_transition.csv", "--gate-check"], "hard",
     ["ledger/ui_sound_transition.csv"]),
    ("G114", "**UI 动态与镜头叙事一致**",
     ["{py}", "{s}/game_ui_motion_camera.py", "--check",
      "{w}/ledger/ui_motion_camera.csv", "--gate-check"], "hard",
     ["ledger/ui_motion_camera.csv"]),
    # ---- 游戏第十五轮：时间推进/动态经济/声望/存档兼容/玩法耦合 ----
    ("G117", "**时间推进语义与动态经济一致**",
     ["{py}", "{s}/game_world_economy.py", "--check",
      "{w}/ledger/world_economy.csv", "--gate-check"], "hard",
     ["ledger/world_economy.csv"]),
    ("G118", "**声望派系与存档兼容体验一致**",
     ["{py}", "{s}/game_faction_save.py", "--check",
      "{w}/ledger/faction_save.csv", "--gate-check"], "hard",
     ["ledger/faction_save.csv"]),
    # ---- 游戏第十六轮：联机延迟/AI 信任/节奏/信息架构/听觉认知 ----
    ("G121", "**联机延迟补偿与 AI 可读性一致**",
     ["{py}", "{s}/game_netfeel_ai_trust.py", "--check",
      "{w}/ledger/netfeel_ai.csv", "--gate-check"], "hard",
     ["ledger/netfeel_ai.csv"]),
    ("G122", "**节奏设计与信息架构一致**",
     ["{py}", "{s}/game_pacing_info.py", "--check",
      "{w}/ledger/pacing_info.csv", "--gate-check"], "hard",
     ["ledger/pacing_info.csv"]),
    # ---- 游戏第十七轮：运气/技巧/重复可玩/玩家表达 ----
    ("G125", "**运气体验与技巧天花板一致**",
     ["{py}", "{s}/game_luck_skill.py", "--check",
      "{w}/ledger/luck_skill.csv", "--gate-check"], "hard",
     ["ledger/luck_skill.csv"]),
    ("G126", "**重复可玩结构与玩家表达一致**",
     ["{py}", "{s}/game_replay_identity.py", "--check",
      "{w}/ledger/replay_identity.csv", "--gate-check"], "hard",
     ["ledger/replay_identity.csv"]),
    # ---- 游戏第十八轮：降级/失败/内容冗余/极限/等待/一致性 ----
    ("G129", "**性能降级语义与失败体验一致**",
     ["{py}", "{s}/game_degrade_fail.py", "--check",
      "{w}/ledger/degrade_fail.csv", "--gate-check"], "hard",
     ["ledger/degrade_fail.csv"]),
    ("G130", "**内容冗余必要性与系统极限一致**",
     ["{py}", "{s}/game_content_limit.py", "--check",
      "{w}/ledger/content_limit.csv", "--gate-check"], "hard",
     ["ledger/content_limit.csv"]),
    # ---- 游戏第十九轮：证据链/仲裁/演进治理/迁移 ----
    ("G133", "**证据链与仲裁层一致**",
     ["{py}", "{s}/game_evidence_chain.py", "--check",
      "{w}/ledger/evidence_chain.csv", "--gate-check"], "hard",
     ["ledger/evidence_chain.csv"]),
    ("G134", "**演进治理与老玩家迁移一致**",
     ["{py}", "{s}/game_migration_govern.py", "--check",
      "{w}/ledger/migration_govern.csv", "--gate-check"], "hard",
     ["ledger/migration_govern.csv"]),
    # ---- 游戏第二十轮：可交付性/可观测性/组织/终止 ----
    ("G137", "**可交付性与运行期可观测性一致**",
     ["{py}", "{s}/game_delivery_observe.py", "--check",
      "{w}/ledger/delivery_observe.csv", "--gate-check"], "hard",
     ["ledger/delivery_observe.csv"]),
    ("G138", "**组织协作与发布终止条件一致**",
     ["{py}", "{s}/game_team_release.py", "--check",
      "{w}/ledger/team_release.csv", "--gate-check"], "hard",
     ["ledger/team_release.csv"]),
    # ---- 游戏第二十一轮：隐性耦合/资源生命周期/帧契约/脚本边界 ----
    ("G141", "**物理—模拟耦合与资源生命周期一致**",
     ["{py}", "{s}/game_sim_resource.py", "--check",
      "{w}/ledger/sim_resource.csv", "--gate-check"], "hard",
     ["ledger/sim_resource.csv"]),
    ("G142", "**帧时序契约与脚本边界一致**",
     ["{py}", "{s}/game_frame_script.py", "--check",
      "{w}/ledger/frame_script.csv", "--gate-check"], "hard",
     ["ledger/frame_script.csv"]),
    # ---- 游戏第二十二轮：触觉/数值/输入硬件/AI听觉/云存档 ----
    ("G145", "**力反馈与数值多值契约一致**",
     ["{py}", "{s}/game_haptics_numbers.py", "--check",
      "{w}/ledger/haptics_numbers.csv", "--gate-check"], "hard",
     ["ledger/haptics_numbers.csv"]),
    ("G146", "**输入硬件/AI听觉/云存档一致**",
     ["{py}", "{s}/game_input_percept.py", "--check",
      "{w}/ledger/input_percept.csv", "--gate-check"], "hard",
     ["ledger/input_percept.csv"]),
    # ---- 游戏第二十三轮：程序生成/阴影/交互反作用力/资源冷却 ----
    ("G149", "**程序生成边界与阴影契约一致**",
     ["{py}", "{s}/game_gen_shadow.py", "--check",
      "{w}/ledger/gen_shadow.csv", "--gate-check"], "hard",
     ["ledger/gen_shadow.csv"]),
    ("G150", "**交互反作用力与资源冷却语义一致**",
     ["{py}", "{s}/game_force_resource.py", "--check",
      "{w}/ledger/force_resource.csv", "--gate-check"], "hard",
     ["ledger/force_resource.csv"]),
    # ---- 游戏第二十四轮：信任边界/设置契约/帧预算/意图层 ----
    ("G153", "**权威信任边界与玩家可调契约一致**",
     ["{py}", "{s}/game_trust_settings.py", "--check",
      "{w}/ledger/trust_settings.csv", "--gate-check"], "hard",
     ["ledger/trust_settings.csv"]),
    ("G154", "**帧预算分配与输入意图层一致**",
     ["{py}", "{s}/game_budget_intent.py", "--check",
      "{w}/ledger/budget_intent.csv", "--gate-check"], "hard",
     ["ledger/budget_intent.csv"]),
    # ---- 游戏第二十五轮：持久痕迹/通知聚合/加载连续性/非文本本地化 ----
    ("G157", "**持久痕迹与通知聚合语义一致**",
     ["{py}", "{s}/game_trace_notify.py", "--check",
      "{w}/ledger/trace_notify.csv", "--gate-check"], "hard",
     ["ledger/trace_notify.csv"]),
    ("G158", "**加载连续性与非文本本地化一致**",
     ["{py}", "{s}/game_load_locale.py", "--check",
      "{w}/ledger/load_locale.csv", "--gate-check"], "hard",
     ["ledger/load_locale.csv"]),
    # ---- 游戏第二十六轮：地形/水体/布料/反射 ----
    ("G161", "**地形植被与水体水下一致**",
     ["{py}", "{s}/game_terrain_water.py", "--check",
      "{w}/ledger/terrain_water.csv", "--gate-check"], "hard",
     ["ledger/terrain_water.csv"]),
    ("G162", "**布料毛发与反射透明一致**",
     ["{py}", "{s}/game_cloth_reflect.py", "--check",
      "{w}/ledger/cloth_reflect.csv", "--gate-check"], "hard",
     ["ledger/cloth_reflect.csv"]),
    # ---- 游戏第二十七轮：环境耦合/系统健康/统计竞速 ----
    ("G166", "**环境耦合与系统健康一致**",
     ["{py}", "{s}/game_coupling_health.py", "--check",
      "{w}/ledger/coupling_health.csv", "--gate-check"], "hard",
     ["ledger/coupling_health.csv"]),
    ("G167", "**统计回放竞速与教学无障碍模组一致**",
     ["{py}", "{s}/game_stats_runs.py", "--check",
      "{w}/ledger/stats_runs.csv", "--gate-check"], "hard",
     ["ledger/stats_runs.csv"]),
    # ---- 游戏第二十八轮：存在感/交互/可达性/材质/音效 ----
    ("G172", "**角色存在感与交互空间仲裁一致**",
     ["{py}", "{s}/game_presence_interact.py", "--check",
      "{w}/ledger/presence_interact.csv", "--gate-check"], "hard",
     ["ledger/presence_interact.csv"]),
    ("G173", "**可达性材质与音效覆盖一致**",
     ["{py}", "{s}/game_reach_material.py", "--check",
      "{w}/ledger/reach_material.csv", "--gate-check"], "hard",
     ["ledger/reach_material.csv"]),
    # ---- 游戏第二十九轮：失败循环/刷新/容错/复位 ----
    ("G177", "**失败重试循环与刷新节奏一致**",
     ["{py}", "{s}/game_retry_spawn.py", "--check",
      "{w}/ledger/retry_spawn.csv", "--gate-check"], "hard",
     ["ledger/retry_spawn.csv"]),
    ("G178", "**容错撤销与物件状态复位一致**",
     ["{py}", "{s}/game_fault_reset.py", "--check",
      "{w}/ledger/fault_reset.csv", "--gate-check"], "hard",
     ["ledger/fault_reset.csv"]),
    # ---- 游戏第三十轮：世界连续性 ----
    ("G183", "**世界一致性与事件序一致**",
     ["{py}", "{s}/game_continuity.py", "--check",
      "{w}/ledger/continuity.csv", "--gate-check", "--allow-unknown"], "hard",
     ["ledger/continuity.csv"]),
    # ---- 游戏第三十一轮：共置/档案/天气/小地图 ----
    ("G186", "**共置归属与天气空间语义一致**",
     ["{py}", "{s}/game_colo_weather.py", "--check",
      "{w}/ledger/colo_weather.csv", "--gate-check"], "hard",
     ["ledger/colo_weather.csv"]),
    # ---- 游戏第三十二轮：交互事务契约 ----
    ("G191", "**交互事务契约一致**",
     ["{py}", "{s}/game_txn_contract.py", "--check",
      "{w}/ledger/txn_contract.csv", "--gate-check"], "hard",
     ["ledger/txn_contract.csv"]),
    # ---- 游戏第三十三轮：认知层与联机契约 ----
    ("G197", "**认知层与联机社交契约一致**",
     ["{py}", "{s}/game_cognitive_social.py", "--check",
      "{w}/ledger/cognitive_social.csv", "--gate-check"], "hard",
     ["ledger/cognitive_social.csv"]),
    # ---- 游戏第三十四轮：世界纵深与难度维度 ----
    ("G203", "**世界纵深与难度维度一致**",
     ["{py}", "{s}/game_depth_difficulty.py", "--check",
      "{w}/ledger/depth_difficulty.csv", "--gate-check"], "hard",
     ["ledger/depth_difficulty.csv"]),
    # ---- 游戏第三十五轮：具身表现与输入契约 ----
    ("G208", "**具身表现与输入契约一致**",
     ["{py}", "{s}/game_embodied_input.py", "--check",
      "{w}/ledger/embodied_input.csv", "--gate-check"], "hard",
     ["ledger/embodied_input.csv"]),
    # ---- 游戏第三十六轮：微观节奏与边界退化 ----
    ("G214", "**微观节奏与边界退化一致**",
     ["{py}", "{s}/game_micro_rhythm.py", "--check",
      "{w}/ledger/micro_rhythm.csv", "--gate-check"], "hard",
     ["ledger/micro_rhythm.csv"]),
    # ---- 游戏第三十七轮：可破坏世界与连锁反应 ----
    ("G220", "**可破坏世界与连锁反应一致**",
     ["{py}", "{s}/game_destruct_chain.py", "--check",
      "{w}/ledger/destruct_chain.csv", "--gate-check"], "hard",
     ["ledger/destruct_chain.csv"]),
    # ---- 游戏第三十八轮：生活玩法与人格化痕迹 ----
    ("G226", "**生活玩法与人格化痕迹一致**",
     ["{py}", "{s}/game_lifeplay_trace.py", "--check",
      "{w}/ledger/lifeplay_trace.csv", "--gate-check"], "hard",
     ["ledger/lifeplay_trace.csv"]),
    # ---- 游戏第三十九轮：输入载体与数字权利 ----
    ("G233", "**输入载体与数字权利一致**",
     ["{py}", "{s}/game_carrier_rights.py", "--check",
      "{w}/ledger/carrier_rights.csv", "--gate-check"], "hard",
     ["ledger/carrier_rights.csv"]),
    # ---- 游戏第四十轮：意义层（玩家读出什么） ----
    ("G240", "**意义层一致**（含**可辨态**已验证）",
     ["{py}", "{s}/game_meaning_layer.py", "--check",
      "{w}/ledger/meaning_layer.csv", "--gate-check"], "hard",
     ["ledger/meaning_layer.csv"]),
    # ---- 游戏第四十一轮：认知 · 承诺 · 耐力 · 信任 ----
    ("G247", "**认知与耐力一致**（含**玩家侧证据**）",
     ["{py}", "{s}/game_cognition.py", "--check",
      "{w}/ledger/cognition.csv", "--gate-check"], "hard",
     ["ledger/cognition.csv"]),
    # ---- 游戏第四十二轮：推断层（常识/OOB/权威/迷信/解释/设备） ----
    ("G255", "**推断层一致**（含**玩家推断**已验证）",
     ["{py}", "{s}/game_inference.py", "--check",
      "{w}/ledger/inference.csv", "--gate-check"], "hard",
     ["ledger/inference.csv"]),
    # ---- 游戏第四十三轮：关系状态（离开/第N次/幽灵/第一次） ----
    ("G262", "**关系状态一致**（含**跨会话证据**）",
     ["{py}", "{s}/game_relation.py", "--check",
      "{w}/ledger/relation.csv", "--gate-check"], "hard",
     ["ledger/relation.csv"]),
    # ---- 游戏第四十四轮：身份与时序（同形异质/方言/组合/惯例） ----
    ("G269", "**身份与时序一致**（含**身份层/时序层证据**）",
     ["{py}", "{s}/game_identity.py", "--check",
      "{w}/ledger/identity.csv", "--gate-check"], "hard",
     ["ledger/identity.csv"]),
    # ---- 游戏第四十五轮：社会层与版本地层 ----
    ("G275", "**社会层与版本地层一致**（含**外部依赖链证据**）",
     ["{py}", "{s}/game_social.py", "--check",
      "{w}/ledger/social.csv", "--gate-check"], "hard",
     ["ledger/social.csv"]),
    # ---- 游戏第四十六轮：外围层 / 自救 / 外设 / 环境 ----
    ("G282", "**外围层与身体接口一致**（含**外围/环境证据**）",
     ["{py}", "{s}/game_periphery.py", "--check",
      "{w}/ledger/periphery.csv", "--gate-check"], "hard",
     ["ledger/periphery.csv"]),
    # ---- 游戏第四十七轮：生活层 / 文化层 / 元收藏 ----
    ("G289", "**生活层与文化层一致**（含**生活/文化/秩序证据**）",
     ["{py}", "{s}/game_life.py", "--check",
      "{w}/ledger/life.csv", "--gate-check"], "hard",
     ["ledger/life.csv"]),
    # ---- 游戏第四十八轮：沟通 / 风险 / 记忆 / 工具契约 ----
    ("G297", "**元协议层一致**（含**行为契约证据**）",
     ["{py}", "{s}/game_meta.py", "--check",
      "{w}/ledger/meta48.csv", "--gate-check"], "hard",
     ["ledger/meta48.csv"]),
    # ---- 游戏第四十九轮：非完整版 / 秘籍 / 旁观者 / 实体载体 ----
    ("G305", "**变体与载体层一致**（含**版本/载体证据**）",
     ["{py}", "{s}/game_variant.py", "--check",
      "{w}/ledger/variant49.csv", "--gate-check"], "hard",
     ["ledger/variant49.csv"]),
    # ---- 游戏第五十轮：Kiosk / 反盗版屏 / Credits ----
    ("G311", "**边缘状态层一致**（含**证据态合法性**）",
     ["{py}", "{s}/game_edge.py", "--check",
      "{w}/ledger/edge50.csv", "--gate-check"], "hard",
     ["ledger/edge50.csv"]),
    # ---- 游戏第五十一轮：证据补洞 + 四路验收接入 ----
    ("G318", "**试玩机状态机已覆盖十二类且无伪造秒数**",
     ["{py}", "{s}/kiosk_recorder.py", "--check",
      "{w}/ledger/kiosk_states.csv", "--gate-check"], "hard",
     ["ledger/kiosk_states.csv"]),
    ("G319", "**Credits 演化无未附证据的删除或排序变化**",
     ["{py}", "{s}/credits_diff.py", "--diff",
      "{w}/ledger/credits_v1.csv", "{w}/ledger/credits_v2.csv",
      "--gate-check"], "hard",
     ["ledger/credits_v1.csv", "ledger/credits_v2.csv"]),
    ("G320", "**CD-KEY 输入消歧项已覆盖且有原版值**",
     ["{py}", "{s}/cdkey_input_linter.py", "--check",
      "{w}/ledger/cdkey_input.csv", "--gate-check"], "hard",
     ["ledger/cdkey_input.csv"]),
    ("G321", "**四路验收已覆盖且产物可哈希复核**",
     ["{py}", "{s}/edge_accept.py", "--check",
      "{w}/ledger/edge_accept.csv", "--gate-check"], "hard",
     ["ledger/edge_accept.csv"]),
    # ---- 游戏第五十二轮：执行层修复（登记表归一化）----
    ("G328", "**登记表已归一化**（无重复 key / 全有 kind / 重名已标记）",
     ["{py}", "{s}/registry_normalize.py", "--check", "--gate-check"], "hard",
     []),
    # ---- 游戏第五十三轮：四路验收端到端跑通 ----
    ("G331", "**四路验收端到端自测通过**（fixture→capture→join→durations→verify）",
     ["{py}", "{s}/edge_pipeline.py", "--self-test"], "hard",
     []),
    # ---- 游戏第五十四轮：SPDX 3.0 Build 接入 ----
    ("G334", "**SPDX 3.0 Build 接入自测通过**（合规片段过 / 缺关系被拦）",
     ["{py}", "{s}/build_manifest_spdx.py", "--self-test"], "hard",
     []),
    # ---- 游戏第五十五轮：真实捕获导入（无真值路径）----
    # ---- 游戏第五十六轮：门禁混沌测试（故意改坏）----
    # 🔑 刻意**不自动执行**：混沌测试要跑 101 个子进程（约 3~5 分钟），
    #    放进门禁套件会让每次回归不可忍受。改为**人工定期执行**。
    # 🔑 第七十二轮：G341 从"说明性门禁（从未执行）"升级为**真能跑的快速子集**
    #    🔴 此前 tpl 是字符串 → 逐字符拆命令 → 硬门禁静默失效（第七十一轮病）
    #    ✅ 第七十四轮：实测全量仅 **52 秒**，故直接跑全量；`--limit` 仍保留于 gate_chaos 供人工抽样，
    #    🔑 但**此门禁不得再带 --limit** —— 否则又变回抽样兜底。
    ("G341", "**门禁混沌测试须全量执行**",
     # 🔑 第七十四轮：实测全量仅 **~52 秒**（此前"3~5 分钟"是过时数据），
     #    → 不再需要抽样兜底，直接跑全量 127 个候选。
     ["{py}", "{s}/gate_chaos.py", "--chaos", "{w}/chaos_g341"],
     "hard", []),
    ("G338", "**真实捕获不得走 --verify**",
     # 🔑 第七十一轮：此前 tpl 是**字符串** → 被逐字符拆成命令 → 执行异常
     #    → 🔴 **hard 门禁从未真正跑过**，却显示成"软警告"。
     #    ✅ 改为真命令：`--verify-guard` 实测守卫成立。
     ("{py}", "{s}/edge_pipeline.py", "--verify-guard"), "hard", []),
    # ---- 游戏第七十一轮：说明性门禁不得伪装 ----
    ("G376", "**混沌器能力自检须通过**",
     # 🔑 G346/G360 在 MANUAL_GATES（人工签字，无命令是正常的），
     #    但它们要求的**能力**可秒级自检 → 单列为**自动**门禁。
     ["{py}", "{s}/gate_chaos.py", "--self-check"], "hard", []),
    ("G377", "**说明性门禁不得伪装成软警告**",
     # 🔴 tpl 为字符串 → 逐字符拆命令 → FileNotFoundError → 被 except 吞掉
     #    → hard 门禁显示成"软警告"，从未执行。本项守这个不回退。
     ["{py}", "{s}/run_all_gates.py", "--self-check-noop"], "hard", []),
    # ---- 游戏第七十二轮：抽样结果不得污染全量缓存 ----
    ("G378", "**抽样混沌不写全量缓存**",
     # 🔴 抽样 10 个写成 "10/10" → 汇总会**谎报全量拦截率**
     ["{py}", "{s}/gate_chaos.py", "--self-check-limit"], "hard", []),
    # ---- 游戏第七十四轮：全量/抽样口径分离 ----
    ("G379", "**全量混沌必须写入 full 口径缓存**",
     # 🔴 G341 跑完若没写 full → 汇总显示"从未执行全量"，门禁形同虚设
     ["{py}", "{s}/gate_chaos.py", "--assert-full"], "hard", []),
    ("G380", "**抽样不得污染全量口径**",
     # 🔴 抽样的 20/20 若写进 full → 汇总谎报全量拦截率
     ["{py}", "{s}/gate_chaos.py", "--assert-no-pollute"], "hard", []),
    # ---- 游戏第七十五轮：**声明核实**（元规则） ----
    # 🔴 第七十三轮声称做了三条（G341 全量 / G379 / G380 / full-sampled），
    #    **代码里一条都没有**。🔑 本门禁让"回读代码核对声明"成为可执行动作。
    # 🔴 第七十五轮**更正**：本轮一度误判"G381 指向不存在的脚本"，
    #    实测 `scripts/claim_verify.py` **存在且可用**（self-test 6/6、
    #    claims_75.txt 11/11）。🔑 误判源于**只抽样核实**（只 grep 了 G379/G380）。
    ("G381", "**完成声明须回读代码核实**",
     ["{py}", "{s}/claim_verify.py", "--self-test"], "hard", []),
    # ---- 游戏第七十八轮：G382/G383/G384 **合并为一次进程**（G385） ----
    # 🔴 第七十七轮指引①：三条各起一次子进程 → 重复 import 门禁表、回归变慢。
    # 🔑 合并入口 `--all` 一次跑完三者，**任一失败即失败**；
    #    🔑 三条**编号保留**（各自语义不同），只是共用同一个进程。
    ("G382", "**文档里的门禁编号不得凭空出现**",
     ["{py}", "{s}/claim_verify.py", "--all"], "hard", []),
    ("G383", "**全部声明清单须持续兑现**（防回退）",
     ["{py}", "{s}/claim_verify.py", "--all"], "hard", []),
    ("G384", "**最新一轮须已写声明清单**",
     ["{py}", "{s}/claim_verify.py", "--all"], "hard", []),
    # 🔑 G385 = 合并入口的**完整性**，且**与 rc 解耦**（第七十九轮）：
    #    `--audit-all` 另起子进程跑 `--all`，只查三段**内容特征**是否齐全。
    #    🔴 不复用 `--all` 的 rc —— 否则漏跑时它自己发现不了。
    ("G385", "**`--all` 三段须全部执行**（独立校验）",
     ["{py}", "{s}/claim_verify.py", "--audit-all"], "hard", []),
    # ---- 游戏第八十轮：守「**判据本身**」而不只是「判据的结论」 ----
    ("G386", "**`ALL_CONTENT` 特征串须段体独有**",
     # 🔑 特征串人工挑选 → 措辞漂移会误报、非独有会漏报。
     #    `--check-content` 用 AST 取三个段体函数，断言存在性 + 唯一性。
     ["{py}", "{s}/claim_verify.py", "--check-content"], "hard", []),
    # ---- 游戏第八十一轮：区分**刻意重复**与**误重复** ----
    ("G387", "**门禁命令不得误重复**（刻意须登记）",
     # 🔑 G382/G383/G384 **故意**共用 --all；其余任何重复都是误登记。
     ["{py}", "{s}/run_all_gates.py", "--check-dup-cmds"], "hard", []),
    # ---- 游戏第九十三轮：rc 合法域不得**分裂成两处** ----
    ("G388", "**rc 合法域须是单一常量**（不得各写一处）",
     # 🔑 第八十九轮"子进程 rc 合法域"与第九十二轮"audit-all 值域锚点"
     #    是同一判据的两处实现 → 合并为 GATE_RC_DOMAIN，防再次分裂。
     ["{py}", "{s}/claim_verify.py", "--check-rc-domain"], "hard", []),
    # ---- 游戏第九十六轮：豁免清单本身必须被守 ----
    ("G389", "**豁免须带批准轮次**（不得静默增删、不得僵尸）",
     # 🔴 第九十五轮诚实结论②：两条 allowlist 的增删不触发任何检查。
     ["{py}", "{s}/claim_verify.py", "--check-allowlist"], "hard", []),
    # ---- 游戏第九十七轮：推送不得静默漏传 ----
    ("G390", "**无漏传风险**（无未 git add 的文件）",
     # 🔴 第九十六轮诚实结论⑤：`push_api.py` 依赖 `git ls-files`，
     #    忘 add 的新文件会被悄悄漏传，而推送仍显示"成功"。
     ["{py}", "{s}/push_api.py", "--check-leak"], "hard", []),
    # ---- 游戏第一百轮：symlink 处理正确性**自测** ----
    ("G393", "**symlink 处理正确**（mode 120000 · 内容 = 链接路径）",
     # 🔴 第九十九轮诚实结论③：symlink/gitlink **从未实测过**。
     #    🔑 且仓库里**一个 symlink 都没有** → G391 永远碰不到它，
     #       缺陷会潜伏到真有人加 symlink 才爆发 → 必须**造一个自测**。
     ["{py}", "{s}/push_api.py", "--check-symlink"], "hard", []),
    ("G395", "**gitlink 识别正确**（mode 160000 · 无磁盘文件）",
     # 🔴 第一百轮诚实结论①：gitlink 从未实测。
     #    🔑 更危险：gitlink **磁盘上没有文件** → 旧流程
     #       `os.path.exists` 前置检查会让**整个仓库推不出去**。
     ["{py}", "{s}/push_api.py", "--check-gitlink"], "hard", []),
    ("G396", "**历史遗留台账与实测双向一致**（遗留不得被掩盖）",
     # 🔴 第一百零一轮诚实结论③：G394 返回 0 即使发现问题
     #    → 作为门禁**永远通过**，存在"门禁绿但问题在"的风险。
     # 🔑 G396 让遗留成为**可断言的事实**：台账 vs 实测，双向比对。
     #    🔴 依赖远端 API：不可达时**拒绝给结论**（rc=1），不静默通过。
     ["{py}", "{s}/push_api.py", "--assert-history-known"], "hard", []),
]

MANUAL_GATES = [
    # 🔑 第九十八轮：**G391 只能人工执行**。
    #    🔴 实测发现：把它放进自动门禁会**必然失败** ——
    #       因为 G341/G383 等门禁运行时会**重写缓存文件**
    #       （audit/.chaos_last.json · ledger/_audit_all_last.json ·
    #        ledger/_chaos_last.json），导致本地 ≠ 远端。
    #    🔑 所以"本地=远端"只在**刚推送完、还没跑门禁**的时刻成立。
    #       → 它已集成进 `push_api.py` 推送主流程（推完立即验证）。
    ("G391", "**推送完整性回读验证**（本地与远端逐条 **mode+sha** 一致）",
     "推送后由 push_api.py 自动执行；不得放入自动门禁"
     " —— 门禁自身写缓存会使其必然失败"),
    # 🔑 第九十九轮：**定期人工复核入口**
    #    🔴 第九十八轮诚实结论⑤：G391 移入人工后，推送之外无人定期验证。
    # 🔑 第一百零一轮：**G394 只能人工执行**。
    #    🔑 它是**审计**入口：发现历史不一致时返回 0（不掩盖，只报告）。
    #    🔴 修正需**改写历史（force push）** —— 破坏性操作，不由脚本决定。
    ("G394", "**历史 commit 权限审计**（遗留写入台账，共 5 个 commit）",
     "只读审计：`push_api.py --audit-history`。"
     " 修正需 force push —— **破坏性，必须人工显式决定**"),
    ("G392", "**远端完整性定期复核**（`--verify-push --report` 报表）",
     "人工定期跑；只报告不阻断。"
     " 🔑 本仓库 core.fileMode=false —— git 不跟踪磁盘权限，"
     " 权限差异**只能**通过 `git update-index --chmod` 产生"),
    ("G7", "golden 人工批准", "golden diff 逐张签字，禁止 AI 代签"),
    ("G8", "故障注入全命中", "F1-F4 四类都必须命中，否则脚本永远绿"),
    ("G9", "视觉逐张签字", "每个视觉状态一张决策卡，design + domain_owner"),
    ("G10", "等价性三层", "差分 oracle + 属性不变量 + mutation"),
    ("G12", "契约冻结", "golden 入库 .approved，禁止手编与 bulk re-record"),
    ("G13", "解析失败已登记", "tree_sitter 解析失败不许自动关闭 unknown"),
    ("G14", "mutation 存活=0", "关键能力包"),
    ("G19", "C1-C12 无空类 + 六实测", "含强杀进程、拔鼠标、旧数据逐字段比对"),
    ("G20", "原版有 A 级证据", "每状态控件树 + 三原语截图 + 环境契约"),
    ("G21", "许可证据充分（**仅第三方内容**）",
     "字体嵌入/再分发/子集逐项确认 —— **ownership: self 时自动跳过**"),
    ("G25", "字体与色彩已锁", "font_lock.yml + ICC profile；未嵌入 profile 须标 unknown"),
    ("G28", "不变量置信度分母达标",
     "Daikon 候选必须以驱动覆盖率为分母，不足则降级人工，**不得直接进门禁**"),
    ("G29", "网络录制集命中已判",
     "未命中不得把 0 当目标：可能是原版死路径或新版少实现"),
    ("G30", "状态模型差异已裁决",
     "尤其「同状态不同转移守卫」—— 功能在但触发条件变了"),
    ("G35", "并发四项",
     "阻塞预算 / 锁跨度（持锁禁 await）/ 取消一致性 / 调度可回放 seed"),
    ("G36", "崩溃签名归一化对照",
     "**不比调用栈**（跨语言无相同函数）；比签名/阶段/输入/状态/恢复"),
    ("G39", "每项 deferred 有签名 manifest",
     "签的是 **manifest digest**；含缺陷哈希/验收规则/owner/expiry/复审周期"),
    ("G42", "无 desync（逐帧哈希链）",
     "逐帧状态哈希一致；有分歧时**必须报出首个发散帧 tick**与子系统"),
    ("G45", "matching 率不降低",
     "按 **ROM/build 矩阵**判定，不是按游戏名；禁止 PR 降低 matching 率"),
    ("G46", "手感参数已量化",
     "死区 / 响应曲线 / coyote time / 跳跃缓冲 / 轮询率 —— 差一帧就是不同游戏"),
    ("G51", "帧时间 p50/p95/p99 无退化",
     "**不只比均值** —— 只测平均帧率会把「偶尔卡顿」平均掉；须存 environment.json"),
    ("G52", "原版构建身份已确认",
     "哈希 / DAT / PDB 一致 —— 否则复刻的可能不是同一个版本"),
    ("G56", "三 WebView 各自 golden 且差异已分类",
     "WebView2 / WebKitGTK / WKWebView **不许共用一套基线**"),
    ("G60", "迁移有 receipt 且四层对账差异为零",
     "**没有 receipt 时新应用不得把状态标为「最新」**；"
     "「没有异常」不等于「迁移成功」"),
    ("G61", "单实例在四个会话上下文均符合原版",
     "同用户双开 / 不同用户 / UAC / 崩溃后重启 —— **不能套一个全局 mutex**"),
    ("G65", "签名撤销矩阵五种状态已验（含 Lifetime Signing）",
     "**不能只检查 ValidSignature** —— 吊销/根轮转/TSA 不可达/过期/Lifetime Signing"),
    ("G66", "**中文/日文 IME 事件序无回归**",
     "验收单位是**可观察状态序**，不是「最终汉字相同」"),
    ("G70", "隐藏内容组合已穷举回放",
     "未观测组合须标 `unconfirmed_reachable`，**不得直接删除**"),
    ("G71", "调试/作弊功能已作为功能清单清点",
     "**它是原版用户可达功能**，不能默认「开发杂务」不迁"),
    ("G74", "服务器权威经失败注入证明",
     "**不能只写进设计文档** —— 越权/重复提交/乱序包须被拒绝"),
    ("G75", "模组 API 兼容矩阵按调用结果而非「能加载」",
     "旧脚本/新脚本旧宿主/依赖循环/脚本异常跨 API 边界"),
    ("G78", "可玩性：关键路径可达且不软锁",
     "**Bot 通关 ≠ 体验一致** —— A 类不变式失败不得被模型置信度掩盖"),
    ("G79", "输入/相机/音频/渲染测量方法可复现",
     "**不能凭感觉调**；延迟须有绝对+相对双层门禁"),
    ("G82", "存档迁移链支持跨版本升级（v1→v3）",
     "**不能只测最新版读最新版**；每中间版本保留 golden fixture"),
    ("G85", "碰撞层矩阵逐层核对完成",
     "**漏一层就是穿墙或卡住**；摩擦/弹性合并模式分别设计实验"),
    ("G88", "引擎隐藏默认值逐项核对（含未设置键）",
     "**另外 90%**；未设置键必须进 review，不得默认视为无关"),
    ("G91", "手感参数在 30/60/120Hz 与可变帧率下均已实测",
     "**只测一个帧率不算通过**；coyote 须同时记 tick 数与毫秒"),
    ("G92", "超分/帧生成组合的输入时间线已实测",
     "**记原始输入时间**，不是笼统写「影响延迟」"),
    ("G95", "隐形墙已入 schema 且贴墙行为已测",
     "**不能因看不见而缺席**；移除不是改善是偏离"),
    ("G96", "DDA 已记 effect_size 与 player_perceivable",
     "**原作无 DDA 则复刻不得贴心加入**"),
    ("G99", "同帧反馈仲裁顺序已按原作实际顺序记录",
     "**不能用模板默认值替原作决定**"),
    ("G100", "浮点确定性矩阵已固定（编译器/标志/SIMD/版本）",
     "**不能只靠固定种子** —— 须下沉到编译与序列化层"),
    ("G103", "混响区过渡曲线已采样（8-16 点）",
     "**声音版隐形墙**；过渡参数比混响名字更重要"),
    ("G104", "感知性能已跨硬件实测（不搬运阈值常数）",
     "**建三级标准**：可见差异 → 不可接受 → 平台档位预算"),
    ("G107", "任务奖励双阶段事务（prepare/commit）与幂等键已实现",
     "**中断重开不得漏奖励或重复奖励**"),
    ("G108", "交易/拾取/奖励均有幂等键",
     "**重入会成为隐蔽 BUG**"),
    ("G111", "规则合约已绑定帧级证据（录像/时间码）",
     "**must-match 绑定可观测结果，不是函数名**"),
    ("G112", "可达性按**动作闭包**验证（非物理可通行）",
     "原版不可达而复刻可达的节点全部进待审"),
    ("G115", "同帧多音仲裁与音画样本偏移已记录",
     "**不能默认随机；不能只说同步**"),
    ("G116", "交互失败已显式声明**故意沉默**场景",
     "**否则会被当未实现补提示**"),
    ("G119", "时间推进已保存 advance_log",
     "**只写「前进了 6 小时」无法判定批量模拟顺序**"),
    ("G120", "存档迁移已跑**双向**且建永久 fixture 库",
     "**禁止默认零值补齐；损坏不得清空进度**"),
    ("G123", "命中回溯按**武器/动作**分别记录",
     "**全局统一化即偏离**"),
    ("G124", "节奏已同时输出**逻辑时间**与**真实时间**两组成果",
     "**只按逻辑时间会低估死亡重试疲劳**"),
    ("G127", "保底六种语义与险胜戏剧性归属已记录",
     "**演出后才回滚保底会立即损害可信度**"),
    ("G128", "技巧已声明**帧基准**并跑完 30/60/120/144Hz 扫描",
     "**图形 trace 不能替代逻辑重放**"),
    ("G131", "降级已记录**先砍什么 × 玩法权重**与升级滞回",
     "**画质档不是视觉配置，是规则档**"),
    ("G132", "极限按 **capacity × fan-out × rate × concurrency** 组合测试",
     "**只测单值上限会漏掉组合边界**"),
    ("G135", "每条目有**证据等级 1-8**；7 级以上不得作为验收依据",
     "**没有证据等级就只剩观点投票**"),
    ("G136", "每个偏离与测试有 **owner 和到期日**",
     "**否则长期分支会在无人认领中腐烂**"),
    ("G139", "发布就绪**六项硬门槛**全为真，否则 `not-shippable`",
     "**用「差不多了」替代硬门槛会把风险推给玩家**"),
    ("G140", "门禁已被**故意改坏**验证过（混沌注入）",
     "**82 个门禁可能全是假的**"),
    ("G143", "每个模拟值有**唯一 writer**，reader 声明**读哪一帧**",
     "**换引擎后漂移的是所有权，不是质量设置**"),
    ("G144", "**延迟一帧**已说明是设计/优化/偏离，未当作原因",
     "**不能把现象命名为原因**"),
    ("G147", "**震感记录为输出波形**，非「强度×时长」",
     "**两马达压一条曲线会让材质消失**"),
    ("G148", "**AI 听觉已先证存在**，未以「更真实」为由补入",
     "**原版没有就不许补**"),
    ("G151", "**同 seed 同世界**已在生成六层/输入闭包/精度/失败策略全部一致下验证",
     "**「随机种子即确定性」是冲突做法**"),
    ("G152", "**阴影已先判 shadow_authority**，低配未无差别关闭阴影",
     "**若阴影是玩法事实源，关阴影 = 关机制**"),
    ("G155", "**视觉命中与权威命中已拆成四事件**，未先播击杀再回滚",
     "**视觉先显示命中不构成权威事实**"),
    ("G156", "`reset to default` **五义已分开**，未伪造原版就有的设置历史",
     "**只写 default: true 无法解释恢复的是哪一个默认**"),
    ("G159", "**痕迹预算按玩法参数记录**，未因减 draw call 静默删最旧痕迹",
     "**渲染代理可消失，『血迹曾在此』的事实不能消失**"),
    ("G160", "**通知合并键与顺序已抓帧判定**，未默认统一成单一 toast",
     "**拾取 5 个可能是 ×5、5 条、或先 3 后 5——三者都可能是正确**"),
    ("G163", "**植被按「稳定性」验收**（非数量），未随机减实例或统一 billboard",
     "**改密度即移动潜行边界**"),
    ("G164", "**镜中可见对象已按原版记录**，未因换反射方案丢失屏外内容",
     "**反射是可见性语义，不是画质候选**"),
    ("G165", "**着色器预热状态已进入加载事务**，未加载 100% 即宣称完成",
     "**「异步编译可接受」是最危险冲突**"),
    ("G168", "**风场相位同源已记录**，各系统未各自使用独立风噪声",
     "**即使采样同一风向量，不同时间积分也会累积相位漂移**"),
    ("G169", "**系统健康阈值来源非 engine default**，且降级未改变判定",
     "**健康的单位是玩家是否仍获得原版承诺的状态**"),
    ("G170", "**调试读数已绑相位**，未混用 CPU 提交与 GPU 执行时戳",
     "**晚一帧的读数不是误差，而是伪 bug 来源**"),
    ("G171", "**speedrun 已分记 RTA/IGT**，PB 保留历史上下文",
     "**不能用一个「游戏时间」字段替代**"),
    ("G174", "**可达性由原版轨迹裁决**，未用新导航网格替代",
     "**新 A* 可能把原版合法 trick 判为不可达，或把不可达判为可达**"),
    ("G175", "**材质工作流转换无未审 semantic_mismatch**，未自动导入未映射属性",
     "**MaterialX/OpenPBR 是中间表示，不是自动转换器**"),
    ("G176", "**音效事件全部有声**，无静默回退",
     "**事件存在但声音不存在是最隐蔽的丢失**"),
    ("G179", "**控制归还时间已单独记录**且未等同输入设备重连",
     "**post_respawn_input_delay 缺失会吞掉连按「再来一次」**"),
    ("G180", "**重试起手状态是显式差异表**，未用「重置」概括",
     "**原版四档不是「满血/死亡」**"),
    ("G181", "**物件状态四层分别记 save_scope 与 reset_trigger**",
     "**只持久化对象状态会出现「门开着、敌人已重置、地图图标合上」三重矛盾**"),
    ("G182", "**撤销窗口已显式记录**（含为 0 的情况），原版没有未新增",
     "**撤销是延迟提交，不是软删除**"),
    ("G184", "**无原版证据的项已标 unknown**，未填 0/1/last_update 等假数据",
     "**本轮立场：交付可验证缺口，不虚构新体验清单**"),
    ("G185", "**四类冒充已排除**（序列化≠快照、发声≠持久化、同帧≠同序、"
     "pressed≠意图有效）",
     "**引擎默认值不能反推原版表现**"),
    ("G187", "**分屏视口拓扑是状态机**，FOV 锁定轴已记录未据引擎默认猜测",
     "**垂直分屏改变水平 FOV；无证据应写来源不确定**"),
    ("G188", "**档案七类隔离域已拆分**，切换为显式事务、删除六问已答",
     "**成就按账号、统计按档案，不能混为「全部清除」**"),
    ("G189", "**天气是两层状态机且玩法耦合为事件契约**",
     "**只复刻特效不复刻雨熄火/潮湿导电=偏离**"),
    ("G190", "**小地图两套坐标与更新相位已记录**，图标有稳定排序键",
     "**失败通常来自采样与排序，不是图标资源**"),
    ("G192", "**放置五种否决已分别记录**，未合并为「无效位置」",
     "**吸附只是提示，合法性才是门槛**"),
    ("G193", "**交易预览是可审计净变化**，确认与锁定分两状态",
     "**锁定后价格仍变＝旧价锁定新价扣除**"),
    ("G194", "**目标三视图与未探索区可见性已记录**，多目标有稳定排序键",
     "**三处刷新不同帧＝箭头已变地图仍高亮旧目标**"),
    ("G195", "**回放录制语义已声明**（输入/快照/帧画面），未声称「完全忠实」",
     "**回放看到重制行为不一定是 bug，但必须显式声明**"),
    ("G196", "**满级后与洗点残留已建模**",
     "**只把最大等级写成上限会漏经验溢出与二次货币**"),
    ("G198", "**认知层四层分流已判定**（语义不得偏离·叙事可注明·"
     "输入须写原因·视觉不得优化掉）",
     "**实际机制与玩家体验冲突时，对齐谁要有判据**"),
    ("G199", "**共识误解是一等资产**，rewrite 项已附 community_impact 与回归测试",
     "**催生玩家行为的误解＝玩法事实，非错误认知**"),
    ("G200", "**联机契约已定义**（邀请9态·踢出/退出两个状态机·中途加入8子集·"
     "掉落分配·队友伤害·聊天双字段）",
     "**「能联机」到「契约完整」差 60 多个真子集**"),
    ("G201", "**非死亡失败 8 类与确认时刻 5 候选帧已记录**",
     "**确认时刻与失败时刻分离是 D 层最核心的 must-match**"),
    ("G202", "**「没有预警」已显式声明**，未擅自加入预警",
     "**没有预警本身就是一种设计**"),
    ("G204", "**先证明原版行为再决定实现**——A–H 是附加观察维度，"
     "未当作新增功能域重新设计",
     "**世界历史/知识边界/环境语义不是新系统**"),
    ("G205", "**「先例」建模为访问计数与条件增量**，「第一次」未当布尔",
     "须测 pressed/committed/成功/结束/存档/读档各相位"),
    ("G206", "**难度八维系数已列出**，非只保留血量与伤害",
     "**中途调整七种语义已测**"),
    ("G207", "**等待是否已判定为玩法而非加载**",
     "**做成快速黑屏＝偏离而非现代化**；原子提交可能错过短窗口事件"),
    ("G209", "**状态外显按通道记录**（非只写「中毒变绿」），"
     "多状态叠加已建状态×表现矩阵",
     "**仅写颜色会漏掉调色、材质差异与叠加规则**"),
    ("G210", "**物品四段生命周期已记录**（held/worn/switched/world），"
     "耐久按视觉可读性处理",
     "**只保留数据库和 UI 图标＝失去物品存在感**"),
    ("G211", "**「沉默」已作为选项进入选项表**，互动半径未统一",
     "**统一半径＝抹平社交距离；默认第一项＝沉默消失**"),
    ("G212", "**肌肉记忆六张时序表已由日志与回放证明**",
     "**只有日志和回放能证明没变**"),
    ("G213", "**声像冲突仲裁规则已定义**",
     "**统一用视觉射线触发 AI＝听觉线索失真**"),
    ("G215", "**帧语义六问已记录**（sample/commit/resolve/event/"
     "visible/perceptual），非只记帧率与平均延迟",
     "**平均延迟相同 ≠ 相位相同**"),
    ("G216", "**微停顿已逐项记录**，帧生成帧已标 interpolated",
     "**不得冒充原生可见帧**"),
    ("G217", "**注意力仲裁从原版反推**，新增弹窗已视为修改注意力合同",
     "**不是纯 UI 改动**"),
    ("G218", "**人格语气为可观察维度**，非单个枚举；沉默基线已测量",
     "**「You died」有五种语气**"),
    ("G219", "**NaN/±0/±∞/溢出已触发**，未一律 sanitize",
     "**边界是负空间，不是补丁清单**"),
    ("G221", "**破坏粒度未擅自提升**（整体替换→Voronoi 会改碎块弹射与可站立面）",
     "**旧速通路线是否仍成立**"),
    ("G222", "**承重支撑拓扑已反向推导**，非只看破碎动画",
     "**整段崩塌 vs 级联坍塌时间窗与声音不同**"),
    ("G223", "**元素传播更新顺序与帧率依赖已验证**",
     "🔴 **不许「顺手修好」帧率依赖**——速通计时不再可比"),
    ("G224", "**约束参数已按求解语义匹配**（非只迁移刚度数值）",
     "**同一组参数在不同迭代/子步下是不同物理**"),
    ("G225", "**RNG 快照三档与固化时机已逐类记录**",
     "**决定玩家存档点设在哪，改了既有攻略失效**"),
    ("G227", "**生活玩法未「保留名字、重做手感」**，"
     "钓鱼按拉力—时间曲线而非难度档复刻",
     "**加辅助线/自动收线＝改变技能门槛与资源获取**"),
    ("G228", "**首次启动状态轨迹已逐字段记录**（含输入锁定与重复次数）",
     "**教学改动不可逆地改变首通体验**"),
    ("G229", "**人格化痕迹已跨保存/版本/平台迁移**（含元历史）",
     "🔴 **只迁移进度＝把老玩家重置成新玩家**"),
    ("G230", "**过场控制权矩阵已建立**，「不可跳过」已被证明",
     "**不可跳过必须被证明，而非引用文本**"),
    ("G231", "**离线功能降级图已建立**（非开关）",
     "🔴 **加入强制在线与「原版为唯一规格」冲突**"),
    ("G232", "**经济按流量验证**，稀缺性未「修复」",
     "**每样只改一点会累积成不同的经济**"),
    ("G234", "**触控按 pointerId 生命周期管理**，手势在同一状态机竞争",
     "🔴 **按触点数组索引处理是高危做法**"),
    ("G235", "**官方编辑器/创作入口去留已作为产品决策记录**",
     "🔴 **以「安全性」为由删除原版创作入口必须评审**"),
    ("G236", "**保底计数与权利账本原子写入服务端**",
     "🔴 **绝不能只在客户端保存**；独立池不得合并成共享池"),
    ("G237", "**数据布局已登记**（AoS/SoA/AoSoA·对齐·热冷分离·缓存行）",
     "🔴 **不能把 unordered_*/字典/集合当等价实现**"),
    ("G238", "**SIMD 保留标量黄金路径**，结果与参考一致才启用",
     "🔴 **把 -ffast-math 当性能开关会破坏核心信条**"),
    ("G239", "**调试设施六态已记录**，玩家可达调试功能变更已评审",
     "🔴 **不能用单一「开发版/发布版」开关代替**"),
    ("G241", "**声音语义已按「声音事实」记录**（材质链/垂直/威胁/步态）",
     "🔑 **可辨性优先于可播放性；混淆矩阵相同 > 响度相同**"),
    ("G242", "**成长按五通道记录**，「沉默事实」未被补成「更爽」",
     "🔑 **变强方向与原版一致（含 inversion）**"),
    ("G243", "**聚焦生命周期与元操作已逐事件录制**",
     "🔴 **C1 是唯一能直接导致流失的硬边界；「恢复后正常」不算**"),
    ("G244", "**跨通道节拍偏移已基于 beat_clock 测量**",
     "🔴 **原版故意错位也必须是 must-match**"),
    ("G245", "**刻意坏味清单已建立**，修复均有偏离许可",
     "🔴 **为现代 UI 统一删除所有不一致＝偏离**"),
    ("G246", "**社群锚点与版本语义已记录**（三空间统一）",
     "🔴 **路线不可达不能静默删词**"),
    ("G248", "**心智地图已建**（地标可回忆/可方向化/可复访）",
     "🔑 **客观可达性 ≠ 玩家认知；只比像素会漏掉认知回归**"),
    ("G249", "**决策承诺语义已记录**（后果四级/不可逆五轴/仪式感）",
     "🔴 **原版故意隐瞒是 must-match，不得为透明自动显示**"),
    ("G250", "**SL 可行性已实测**",
     "🔴 **不得因加入自动云同步而意外消除 SL 玩法**"),
    ("G251", "**长时间游玩漂移已按 5 阶段采样**",
     "🔑 **耐力本身是游戏意义的一部分；更舒适 ≠ 更忠实**"),
    ("G252", "**上手曲线已记前 5/30/120 分钟**",
     "🔑 **留存不是目标，前段理解完成度才是**"),
    ("G253", "**确定性信任两本账已测**（统计 + 主观）",
     "🔑 **成功包络，不是平均成功率**"),
    ("G254", "**责任归因六方已记录**，client view 与 server truth 分轨",
     "🔴 **不得为公平新增 leaderboard/MVP/死亡原因**"),
    ("G256", "**常识规则测试矩阵已建立**，反常识均有运行时证据",
     "🔑 **常识违反若可重复，就不是瑕疵，而是资产**"),
    ("G257", "**OOB 地图已记录**（边界厚度/入口/退出/证据链）",
     "🔴 **OOB 不是物理 bug，是原版地图的一部分**"),
    ("G258", "**通道权威性已按状态机记录**，四级治理无越级",
     "🔴 **动画明显命中但判定未中＝游戏撒谎**"),
    ("G259", "**随机接口已复现**（调用顺序/调用栈/显示与真实是否同一值）",
     "🔑 **不只复现分布；UI 承诺不得早于真实结算**"),
    ("G260", "**失败可解释性四级已记录**",
     "🔑 不是只在死亡时需要解释"),
    ("G261", "**设备老化与校准状态已进入 device_profile**",
     "🔑 同一游戏在不同老化设备上体验不同"),
    ("G263", "**离开与弃坑状态已记录**（最后120秒轨迹/断点/AFK六态）",
     "🔑 **统一成「流失原因」会丢失回归承诺差异**"),
    ("G264", "**第 N 次四层计数已建立**，跳过是控制权迁移",
     "🔴 **用布尔 seen 会误判「此后都可跳过」**"),
    ("G265", "**幽灵内容已按六级分级**（含 media_commitment）",
     "🔑 **门后没有模型 ≠ 没有承诺**"),
    ("G266", "**第一次三层已记录**，重制未剧透",
     "🔑 不可再生情绪只能记录老玩家重放偏好"),
    ("G267", "**玩家私有公平规则与笨拙容忍已取证**",
     "🔑 笨拙不是残障；不得用简化按钮改写"),
    ("G268", "**共谋未被揭穿**（假选择/QTE/假开放保持）",
     "🔴 显示「这只是演出」即破坏共谋"),
    ("G270", "**实体身份四层已建立**，同名异质已分级",
     "🔴 **背包容缩为去重+数量＝消灭玩家记得的每一把剑**"),
    ("G271", "**个人操作方言已录为动作短语**（含无效输入副作用）",
     "🔑 **键位重映射不解决「提前4帧按下是否还有效」**"),
    ("G272", "**意外组合已按三级分类**（社区契约不默认修复）",
     "🔑 **分模块测试会天然漏掉系统接缝**"),
    ("G273", "**惯例层与原版层并存**，现代键位未静默覆盖",
     "🔑 反惯例不是落后，是身份"),
    ("G274", "**挂机契约 / 失败美学 / 现实时间礼物已取证**",
     "🔑 错过的稀缺性本身就是内容"),
    ("G276", "**知识声明三层已建立**（观察/断言/证据链）",
     "🔑 **老玩家教的是旧版本；多人一致≠为真**"),
    ("G277", "**假可玩性已分级**（含 tutorial_only/demo_only/placebo）",
     "🔑 **界面先承诺、系统再拒绝**"),
    ("G278", "**玩家第二职业可观测契约已记录**",
     "🔑 **生态失效不是「有没有 Mod」，而是契约是否稳定**"),
    ("G279", "**版本地层 DAG 已建立**（地区/载体/构件哈希）",
     "🔴 **标题相同≠构件相同；不得写「日版总是更难」**"),
    ("G280", "**仪式性浪费与苦行契约已取证**（含辅助模式影响）",
     "🔑 原版没有成就 ≠ 玩家不苦行"),
    ("G281", "**个性化真伪与跨通道名称已验证**",
     "🔑 四个破绽接缝：称呼/知识/时间/遗忘"),
    ("G283", "**元游戏外围层按状态机记录**（十三类含失败态/离线态）",
     "🔑 **客户端可缺是硬要求；不能从 UI 截图倒推内部契约**"),
    ("G284", "**玩家自救已录为第二控制流**",
     "🔑 消除痛苦≠错误；删掉玩家共同语言才是偏离"),
    ("G285", "**物理外设逐设备建档**（校准/异步反馈/断电容错）",
     "🔴 禁止统一为「通用手柄」映射"),
    ("G286", "**游玩环境考古已逐环境取证**",
     "🔑 客厅≠书房；WCAG 只作测量尺度"),
    ("G287", "**元进度五层与账号连接流已记录**",
     "🔴 禁止把自动合并写成无感优化"),
    ("G288", "**玩家作品管线与通关后状态机已取证**",
     "🔑 照片模式不是截图键；通关后世界是叙事状态机"),
    ("G290", "**会话承诺曲线与退出尾部已取证**",
     "🔑 玩家管理的是会话承诺，不是时长"),
    ("G291", "**受控随机七通道与透明度三层已锁定**",
     "🔑 容忍不可预测 ≠ 容忍无法归因"),
    ("G292", "**文化层十维与区域变体已记录**",
     "🔴 不得统一成国际化中立版"),
    ("G293", "**排序稳定性与命名截断契约已验证**",
     "🔴 不能用稳定排序悄然取代原版未定义顺序"),
    ("G294", "**展示层与删除权已取证**",
     "🔑 删除权不是删号；分享码是证明"),
    ("G295", "**精通曲线与技能遗忘已记录**",
     "🔑 原版没有回归训练就不得插入"),
    ("G296", "**第三空间与弱互动已取证**",
     "🔴 优化掉它等于删除社交与仪式"),
    ("G298", "**沟通元语言按模态矩阵记录**",
     "🔴 统一 ping 会抹平位置信号/身份表演/持久涂鸦的差异"),
    ("G299", "**行动前风险账本已逐字段可回放**",
     "🔑 决定玩家是否认为选择属于自己"),
    ("G300", "**行为记忆带证据、期限与退出路径**",
     "🔴 黑箱读心与永久画像均冲突"),
    ("G301", "**外部工具契约已建立**",
     "🔑 字段语义稳定比 JSON 美观重要"),
    ("G302", "**价值信号全通道一致**",
     "🔑 稀有度是通道同步的承诺，不是颜色表"),
    ("G303", "**认知地图锚点可复现**",
     "🔑 对象不是地图几何，是地标—路径—关系网络"),
    ("G304", "**沉默区域已登记且未被贴心化**",
     "🔴 沉默是规则，不是空缺"),
    ("G306", "**非完整版本七态与存档继承状态图已取证**",
     "🔴 不得静默覆盖体验版档，不得悄悄加恢复安全网"),
    ("G307", "**秘籍按五层输入窗口与副作用建模**",
     "🔑 秘籍是发布内容，不是调试残留"),
    ("G308", "**非玩家参与者信息层已分离**",
     "🔑 给观众看 ≠ 给玩家听；不得合并成 easy_mode"),
    ("G309", "**实体载体与纸质地图已记录**",
     "🔴 数字化替身不得覆盖原版实体浏览物"),
    ("G310", "**错误美学与存档控制权已取证**",
     "🔴 不得替换原版错误弹窗；不得单槽强制自动保存"),
    ("G312", "**试玩机十二类状态已取证**",
     "🔴 超时立刻黑屏；把 Kiosk 内容差异当 bug 修掉"),
    ("G313", "**反盗版失败屏与故意异常已记录**",
     "🔴 不得悄悄修掉以可见异常著称的版本表面"),
    ("G314", "**CD-KEY 字符消歧已按原版语义**",
     "🔴 不得擅自加严格校验或自动纠错"),
    ("G315", "**Credits 排序按原版事实记录**",
     "🔴 不得按现代审美重排；删除原作者是署名缺陷"),
    ("G316", "**支持者名单未被善意破坏**",
     "🔴 不得为版式整齐删除、合并、改正拼写"),
    ("G317", "**证据态四态已显式填写**",
     "🔑 不可验证要升级为字段值，不是留空"),
    ("G322", "**构建矩阵已展开为 engine×platform×renderer×build_id**",
     "🔴 不能只有『原版/复刻版』两栏"),
    ("G323", "**baseline 与测试在同一环境生成**",
     "🔑 OS/版本/设置/硬件/电源模式/headless 都会影响渲染"),
    ("G324", "**基线不可知时不伪造 PASS**",
     "🔑 只产出 observed_durations.json"),
    ("G325", "**音频指纹已按时间窗切段且未静态链接未审查依赖**",
     "🔴 指纹库不是 general-purpose；LGPL 合规须审查"),
    ("G326", "**物理表面以可复核尺度记录**",
     "🔴 不以艺术化照片为 must-match"),
    ("G327", "**人工批准已记 reviewer 与新旧 baseline hash**",
     "🔑 调试 trace 不得冒充图形 baseline"),
    ("G329", "**能力矩阵已按 kind 解读**",
     "🔴 不得把『缺失 N』当能力缺口——cli/lib 之外的本来就不能 which"),
    ("G330", "**空工作区不得被读成『全绿』**",
     "🔑 通过 0 / 跳过 119 时必须显式警告：发现仍依赖人工"),
    ("G332", "**缺工具的路记为 tool_missing 而非通过**",
     "🔴 chromaprint/COLMAP 缺失时绝不伪造——只表示『已记录但未验证』"),
    ("G333", "**基线不可知时只产出 observed_durations.json**",
     "🔑 T_min/T_max 必须为 null，不得填推测值"),
    ("G335", "**Build 必含三条强制关系**",
     "🔴 hasInput/hasOutput/invokedBy 缺一即阻断——只有字段没有关系不是 Build"),
    ("G336", "**buildId 不得当全局唯一键**",
     "🔑 SPDX 官方：locally unique —— 必须自加 externalIdentifier 全局层"),
    ("G337", "**默认不写 buildStartTime/EndTime**",
     "🔑 官方明说可省略以简化可复现构建；3.1 已弃用；写了须显式标注"),
    ("G339", "**自测与真实取证分两条路径**",
     "🔴 不得以合成自测冒充真实取证；真实导入不生成 ground_truth.json"),
    ("G340", "**真实导入须先 ffprobe 探测**",
     "🔑 fps/时长/音轨不得猜；探测失败用显式默认并标注 fps_guessed"),
    ("G342", "**空台账不得静默通过**",
     "🔴 条目为 0 时必须显式失败——『无阻断项』不等于『没有条目』"),
    ("G343", "**枚举字段须白名单校验**",
     "🔴 只查空值/TODO 是黑名单式——填任意非法值会静默通过"),
    ("G344", "**混沌测试的字段覆盖率须被测量**",
     "🔑 拦截率必须伴随覆盖率；未覆盖字段 = 盲区，不得宣称已验证"),
    ("G345", "**配对字段须差异化毒化**",
     "🔑 legacy/new 填相同值可能掩盖对比逻辑失效"),
    ("G346", "**须做语义毒化（不只是语法毒化）**",
     # 🔑 第七十一轮核实：**本项在 MANUAL_GATES（人工签字），不是自动门禁**
     #    → 没有可执行命令是**正常的**，不是缺陷。
     "🔑 合法值+内部矛盾是最危险的错误形态；白名单拦不住它"),
    ("G347", "**跨字段一致性须被检查**",
     "🔑 verdict=equivalent 但 legacy≠new 必须阻断——字段合法≠行自洽"),
    ("G348", "**A 类盲区须归零**",
     "🔑 连续三轮混沌发现的 9 个内容盲区已修；不得回退"),
    ("G349", "**毒化器须适配 md 台账**",
     "🔴 把 md 表当 CSV 毒化会摧毁结构 → 误判为崩溃"),
    ("G350", "**接口不匹配须与崩溃分开计数**",
     "🔑 rc=2+unrecognized = 测试器没适配，不是门禁失效"),
    ("G351", "**101 项须全部参与统计**",
     "🔑 接口不匹配的脚本要适配专属接口，不能留作『没测』"),
    ("G352", "**汇总须显示门禁自身可信度**",
     "🔑 只报通过/阻断不够——必须同时报拦截率与字段覆盖率"),
    ("G353", "**skip 须细分到物种**",
     "🔑 not_a_ledger / needs_external_input 不能混成『没测上』"),
    ("G354", "**缺数据不得等同在容差内**",
     "🔴 motion_check 曾因字段全 None 而打印『✅ 在容差内』并 rc=0"),
    ("G355", "**枚举须标 constraint 或 must_match**",
     "🔑 没有 evidence 列就不做证据一致性断言——否则误杀"),
    ("G356", "**基线必须 rc=0，毒化才有效**",
     "🔴 基线本身 rc≠0 时，『毒化后 rc≠0』毫无信息量（测了个寂寞）"),
    ("G357", "**适配器须完全接管通用路径**",
     "🔴 通用 --init 先失败会直接判 skip，适配器根本没机会执行"),
    ("G358", "**值毒化无效时用结构毒化**",
     "🔑 只做字段存在性检查的门禁：改值无效，**删键**才有效"),
    ("G359", "**拦截率须区分强/弱证据**",
     "🔴 基线 rc≠0 时『毒化后 rc≠0』只证明它会拦，不证明拦的是注入内容"),
    ("G360", "**强证据率只能靠逐脚本 fixture 提升**",
     # 🔑 第七十一轮核实：同 G346，属 **MANUAL_GATES**
     "🔑 通用填充猜不出专属枚举（must_match 在 A 脚本是 yes、B 脚本是 exact）"),
    ("G361", "**强证据率须标注目录完备型上限**",
     "🔴 「没记全」正是这类门禁要拦的 —— 基线必然不干净，不应凑"),
    ("G362", "**填充/毒化须按台账实际格式分派**",
     "🔴 YAML/Markdown 台账按 CSV 处理 → 填充无效且**会把文件写坏**"),
    ("G363", "**目录完备型须用增量完备性验证**",
     "🔑 补齐一项 → 缺失计数应降一项；补满仍不为 0 = 永远无法满足"),
    ("G364", "**缺失计数行未打印 ≠ 仍有缺失**",
     "🔴 脚本只在有缺失时才打印该行 —— 抓不到数字要判 0，不是沿用上次值"),
    ("G365", "**不得用「删行→blocker 上升」做通用完备性**",
     "🔴 逐行校验型删行＝删掉 blocker 源，必然误判"),
    ("G366", "**目录扫描器只能列候选，不得下判定**",
     "🔑 是否目录完备型、metric 正则是什么，须人工登记"),
    ("G367", "**两个格式嗅探器结论必须一致**",
     "🔴 _sniff=md 而 _is_md_table=non-md → md 被当 CSV 写回"),
    ("G368", "**毒化后文件必须仍可解析**",
     "🔴 毒化后 Traceback = 毒化器**写坏了文件**，门禁结论不可信"),
    ("G369", "**不得用填充冒充毒化**",
     "🔴 填充填合法值，测不出内容敏感性；毒化须注入非法值"),
    ("G370", "**探针覆盖度 ≠ 全体覆盖度**",
     "🔴 未参与的就是未测（87/98 无法改瘦须显式报出）"),
    ("G371", "**合成改瘦后必须重测基线**",
     "🔴 合成破坏合法性 → rc≠0 → 不得判 A（假阳性）"),
    ("G372", "**关键词只能提示，不得判定 A/B**",
     "🔴 措辞不统一：license 用『有效条目为 0』，无『未覆盖』字样"),
    ("G40", "报告四类阈值均达",
     "像素/布局/可访问性/行为；未达标项均有签名批准，**「看起来通过」不算**"),
]


def build_cmd(tpl, work):
    # 🔴 第七十一轮修真 bug：**tpl 为字符串时会被逐字符拆成命令**。
    #    `for t in "🔑 gate_chaos.py ..."` → ['🔑', ' ', 'g', ...]
    #    → subprocess 报 No such file or directory: '🔑'
    #    → 被 except 吞掉 → **hard 门禁变成"软警告"，从未真正执行**。
    # 🔑 现在：字符串 tpl = **说明性门禁**，显式返回 None，由调用方归类。
    if isinstance(tpl, str):
        return None
    out = []
    for t in tpl:
        out.append(t.format(py=sys.executable, s=HERE, w=work))
    return out


def is_noop(tpl):
    """🔑 说明性门禁（无可执行命令）—— **不得**伪装成通过或阻断。"""
    return isinstance(tpl, str)


def has_inputs(work, files):
    return all(os.path.exists(os.path.join(work, f)) for f in files)




# ==========================================================================
# 🔑 第六十轮：把**门禁自身的可信度**接进汇总
#
# 🔴 此前汇总只报"通过/阻断/跳过"，但**没说这些门禁本身有多可靠**。
#    🔑 门禁数量会被误读为能力；真正该看的是：
#       · 拦截率（故意改坏后是否真拦）
#       · 字段覆盖率（毒化覆盖了多少字段）
# ==========================================================================


def _load_gate_trust():
    """🔑 读取混沌测试与覆盖率结果（缓存 JSON）。

    🔴 第七十四轮修真 bug：**抽样结果污染全量口径**。
       此前直接读顶层 `intercept_rate` —— 若最近一次是 `--limit 20`，
       汇总会显示 "20/20"，🔴 **谎报成全量**。

    🔑 现在：`full` 与 `sampled` **分离存放**，本函数**只认 `full`**
       作为全量口径；抽样结果单独作为一行并显式标注"抽样"。
    """
    import json
    out = {}
    _NO = '⚠️ **未测量**（跑 `--chaos` 全量后生成）'
    try:
        j = json.load(open('audit/.chaos_last.json', encoding='utf-8'))
    except Exception:
        j = {}
    full = j.get('full')
    if isinstance(full, dict):
        for name, key in (
            ('混沌拦截率', 'intercept_rate'),
            ('强证据率', 'strict_rate'),
        ):
            out[name] = full.get(key, '(无)')
        # 🔑 第七十四轮：`completeness` / `format_audit` 是**独立测量维度**
        #    （由 --catalog-probe / --format-audit 写），不属于 chaos 的
        #    full/sampled 语义 → 优先取 full，取不到**回退顶层**。
        for name, key in (('增量完备性', 'completeness'),
                          ('格式复核', 'format_audit')):
            # 🔴 第七十四轮再修：'(未测)' 是**真值字符串**，`or` 不会回退
            #    → 必须显式当空处理。
            _v = full.get(key)
            if not _v or _v in ('(未测)', '(无)', 'None'):
                _v = j.get(key)
            out[name] = _v or '(无)'
        out['🕒 全量执行时间'] = full.get('ts', '(无)')
    else:
        for name in ('混沌拦截率', '强证据率', '增量完备性', '格式复核'):
            out[name] = _NO
        out['🕒 全量执行时间'] = '🔴 **从未执行全量**'
    smp = j.get('sampled')
    if isinstance(smp, dict):
        out['🔬 最近抽样'] = ('%s · limit=%s · %s'
                              % (smp.get('ts', '?'),
                                 smp.get('limit', '?'),
                                 smp.get('intercept_rate', '?')))
    try:
        c = json.load(open('audit/.coverage_last.json', encoding='utf-8'))
        out['字段覆盖率'] = c.get('coverage_pct', '(无)')
    except Exception:
        out['字段覆盖率'] = '⚠️ **未测量**（跑 `--coverage` 后生成）'
    return out


def cmd_list(a):
    print("=" * 66)
    print("自动门禁（脚本判定）")
    print("=" * 66)
    for gid, name, tpl, kind, files in GATES:
        print(f"  {gid:<4} [{kind}] {name}")
        print(f"        需要: {', '.join(files)}")
    print("\n" + "=" * 66)
    print("人工门禁（脚本判不了，必须由人签字）")
    print("=" * 66)
    for gid, name, why in MANUAL_GATES:
        print(f"  {gid:<4} {name}")
        print(f"        {why}")
    print("\n⚠️ 收工由这些门禁共同决定，**不由模型自述决定**。")
    return 0


def cmd_self_check_noop(a):
    """🔑 G377：说明性门禁必须被**显式归类**，不得伪装成软警告。

    🔴 第七十一轮真 bug：tpl 写成字符串 → `build_cmd` 逐字符拆 → 命令不存在
       → `except` 吞掉 → **hard 门禁 G338 变成"软警告"，从未执行过**。

    🔑 本门禁守两件事：
       ① `build_cmd` 遇到字符串 tpl 必须返回 None（不得逐字符拆）
       ② cmd_run 必须把这类项归到 `noop`，**不进 passed 也不进 soft_warn**
    """
    src = open(os.path.join(HERE, 'run_all_gates.py'), encoding='utf-8').read()
    ok1 = 'if isinstance(tpl, str):' in src and 'return None' in src
    ok2 = 'noop.append(' in src
    strs = [(g, n) for g, n, t, k, f in GATES if isinstance(t, str)]
    print('=' * 70)
    print('G377 · 🔑 说明性门禁不得伪装成软警告')
    print('=' * 70)
    print(f"{'✅' if ok1 else '🚫'} build_cmd 对字符串 tpl 返回 None"
          f"（不得逐字符拆命令）")
    print(f"{'✅' if ok2 else '🚫'} cmd_run 将说明性门禁归入 noop 列表")
    print(f"\n🔑 当前说明性门禁 {len(strs)} 项（**从未执行**，须人工关注）:")
    for g, n in strs:
        print(f"   {g} {n}")
    ok = ok1 and ok2
    print('\n' + '=' * 70)
    print('✅ 守卫成立' if ok else '🔴 守卫失效')
    print('=' * 70)
    return 0 if ok else 1


def cmd_run(a):
    if not os.path.isdir(a.work):
        print(f"❌ 工作区不存在: {a.work}")
        return 2

    print("=" * 66)
    print(f"全部门禁 · 工作区 {a.work}")
    print("=" * 66)

    blocked, soft_warn, skipped, passed = [], [], [], []
    noop = []
    skipped_legal = []
    ownership = read_ownership(a.work)

    for gid, name, tpl, kind, files in GATES:
        if gid in LEGAL_GATES and ownership == "self":
            skipped_legal.append(gid)
            print(f"\n⏭  {gid} {name} —— **ownership: self，跳过**（自有项目不受限）")
            continue
        if not has_inputs(a.work, files):
            skipped.append((gid, name, files))
            print(f"\n⏭️  {gid} {name} —— 缺少输入 {files}，跳过")
            continue
        cmd = build_cmd(tpl, a.work)
        if cmd is None:
            # 🔑 说明性门禁：显式报出，**不进 passed 也不进 soft_warn**
            noop.append((gid, name, tpl))
            print(f"\n📝 {gid} {name} —— **说明性门禁**（无可执行命令）")
            print(f"        🔑 {tpl}")
            continue
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
            rc = r.returncode
        except Exception as e:
            print(f"\n⚠️  {gid} {name} —— 执行异常: {e}")
            soft_warn.append((gid, name, "执行异常"))
            continue
        if rc == 0:
            passed.append(gid)
            print(f"\n✅ {gid} {name}")
        elif kind == "hard":
            blocked.append((gid, name))
            print(f"\n❌ {gid} {name} —— **阻断**")
            if a.verbose and r.stdout:
                print("   " + r.stdout.strip().replace("\n", "\n   ")[:800])
        else:
            soft_warn.append((gid, name, f"退出码 {rc}"))
            print(f"\n⚠️  {gid} {name} —— 软门禁未过（退出码 {rc}）")

    if skipped_legal:
        print("\n" + "=" * 66)
        print(f"⏭ 法律/许可门禁已跳过（ownership: self）: {', '.join(skipped_legal)}")
        print("   **本 Skill 主场景是自有项目跨引擎搬迁与二次创作** ——")
        print("   不因许可顾虑阻碍重制与二次开发。")
        print("   仅在 ledger/project.yaml 写 ownership: third_party 时才需确认。")

    total = len(passed) + len(blocked) + len(soft_warn) + len(skipped)
    print("\n" + "=" * 66)
    print("汇总")
    print("=" * 66)
    print(f"  **通过 {len(passed)} / 共 {total}** · 阻断 {len(blocked)} · "
          f"软警告 {len(soft_warn)} · 跳过 {len(skipped)}")
    # 🔑 审核发现的误导：空工作区时 PASS=0、SKIP 上百，却仍打印"全绿"
    if len(passed) == 0:
        print("\n🔴 **一项都没真正通过** —— 不要把下面的长列表读成『都检查过了』。")
        print(f"   🔑 跳过 {len(skipped)} 项＝**缺台账输入**，"
              "不是『检查后合格』。")
        print("   🔑 自动门禁绝大多数是**台账校验器**："
              "校验的是你填的表，不是游戏本身。")
        print("   🔴 **发现仍然完全依赖人工。机器不会替你找到任何东西。**")
    elif len(skipped) > len(passed):
        print(f"\n⚠️ 跳过（{len(skipped)}）多于通过（{len(passed)}）—— "
              "**大部分门禁没拿到输入，结论覆盖有限**。")

    if blocked:
        print("\n❌ 硬门禁阻断 —— **不得声明复刻完成**:")
        for gid, name in blocked:
            print(f"   {gid} {name}")
    if soft_warn:
        print("\n⚠️  软门禁未过（需人工判定是否为有意变更）:")
        for gid, name, why in soft_warn:
            print(f"   {gid} {name} —— {why}")
    if noop:
        print("\n📝 **说明性门禁** —— 🔴 **无可执行命令，从未真正执行过**:")
        for gid, name, _t in noop:
            print(f"   {gid} {name}")
    if skipped:
        print(f"\n⏭️  跳过 {len(skipped)} 项（缺输入）:")
        for gid, name, files in skipped:
            print(f"   {gid} {name} —— 需要 {', '.join(files)}")
        if a.strict:
            print("   ⚠️ --strict：缺输入视为阻断")
            return 1

    print("\n" + "=" * 66)
    print("人工门禁（脚本判不了，必须由人签字）")
    print("=" * 66)
    for gid, name, why in MANUAL_GATES:
        if gid in LEGAL_GATES and ownership == "self":
            print(f"   {gid:<4} ~~{name}~~ —— **跳过：自有项目不受此限**")
            continue
        print(f"   {gid:<4} {name} —— {why}")

    # 🔑 第六十轮：把**门禁自身的可信度**也打进汇总
    _trust = _load_gate_trust()
    if _trust:
        print("\n" + "=" * 66)
        print("🔑 门禁自身可信度（**不是游戏可信度**）")
        print("=" * 66)
        for k, v in _trust.items():
            print(f"   {k}: {v}")
        print("   🔑 这两个数字回答：『上面的通过/阻断，有多值得信』")

    print("\n⚠️ 自动门禁全绿 ≠ 可以收工。")
    print("   人工门禁一项没签字，就不得声明完成。")
    print(f"\n🔑 本轮自动化真相：通过 {len(passed)} / 共 {total}"
          f"（跳过 {len(skipped)}）。")
    print("   🔑 **81% 的脚本是纯台账校验器**——读你填的 CSV，"
          "不读源码、不调引擎、不起进程。")
    print("   🔴 因此『通过』只表示『这张表填得自洽』，"
          "**不表示原版行为已被取证**。")

    return 1 if blocked else 0

def _cmd_key(tpl):
    """🔑 把命令元组归一成可比较的字符串（忽略 `python` 与路径前缀差异）。"""
    if not isinstance(tpl, (list, tuple)):
        return None                      # 🔴 字符串 tpl 是缺陷（第七十一轮）
    parts = [str(x) for x in tpl if x != '{py}']
    return ' '.join(parts)


def cmd_check_dup_cmds(a):
    """G387 · 🔑 **门禁命令不得误重复**（刻意重复须显式登记 + 理由）。

    🔴 第八十轮指引：G382/G383/G384 **故意**重复 `--all`，
       需能区分**刻意重复**与**误重复**。
    🔑 本门禁：
       - 找出**命令完全相同**的门禁组
       - 未在 `INTENTIONAL_DUP_CMDS` 登记 → 🔴 **阻断**
       - 已登记但**理由为空** → 🔴 阻断
       - 已登记但门禁**不存在**或**命令已不一致** → 🔴 阻断（登记过时）
       - 登记了却**实际没有重复**（重复已消除）→ ⚠️ 警告（登记应清理）
    """
    print('=' * 70)
    print('G387 · 🔑 **门禁命令重复性**（刻意 vs 误重复）')
    print('=' * 70)
    g = GATES          # 🔑 本文件即门禁表，直接取（_load_gates 属于 claim_verify）
    by = {}
    for gid, name, tpl, kind, files in g:
        k = _cmd_key(tpl)
        if k is None:
            print(f'\n🔴 {gid} 的命令模板是**字符串**（缺陷，第七十一轮）——'
                  f'无法参与重复性判定')
            print('\n' + '=' * 70 + '\n🔴 守卫失效\n' + '=' * 70)
            return 1
        by.setdefault(k, []).append(gid)

    dups = {k: v for k, v in by.items() if len(v) > 1}
    print(f'\n门禁 {len(g)} 条 · 不同命令 {len(by)} 种 · '
          f'重复组 {len(dups)} 组')
    if not dups:
        print('\n' + '=' * 70)
        print('✅ 守卫成立：无重复命令')
        if INTENTIONAL_DUP_CMDS:
            print('⚠️  但 `INTENTIONAL_DUP_CMDS` 仍有登记 —— **已过时，应清理**')
        print('=' * 70)
        return 0

    bad = 0
    for k, ids in sorted(dups.items()):
        print(f'\n[重复 ×{len(ids)}] {ids}')
        print(f'   命令: {k}')
        rec = None
        for pat, v in INTENTIONAL_DUP_CMDS.items():
            if pat.replace('{s}/', '') in k.replace('{s}/', ''):
                rec = v
                break
        if rec is None:
            print('   🔴 **未登记为刻意重复** —— 两条门禁跑同一条命令'
                  '违反独立性，几乎一定是误登记')
            bad += 1
            continue
        allowed, reason = rec
        if not reason.strip():
            print('   🔴 **已登记但理由为空** —— 必须写明为何刻意重复')
            bad += 1
            continue
        # 🔑 **逐个 ID** 校验：组内每一条都必须被批准
        unapproved = [i for i in ids if i not in allowed]
        if unapproved:
            print(f'   🔴 **组内存在未被批准的门禁 {unapproved}** —— '
                  f'登记只批准了 {sorted(allowed)}；'
                  f'🔑 新增/改名都会漏网，必须逐个登记')
            bad += 1
            continue
        print(f'   ✅ 已登记为刻意重复：{reason[:48]}…')

    # 🔑 反向检查：登记项是否仍对应真实重复（防登记过时）
    for pat, (allowed, _r) in INTENTIONAL_DUP_CMDS.items():
        hit = [k for k in dups if pat.replace('{s}/', '') in k.replace('{s}/', '')]
        if not hit:
            print(f'\n⚠️  登记项 `{pat}` **已无对应重复** —— '
                  f'登记过时（不阻断，但应清理）')
            continue
        actual = set(sum((dups[k] for k in hit), []))
        gone = sorted(allowed - actual)
        if gone:
            # 🔑 第八十二轮：从**警告**升级为**阻断**。
            #    🔴 理由：登记批准了实际不存在的门禁 = 登记与事实不符；
            #       继续放行会让"登记"变成可以随便写的注释。
            print(f'\n🔴 登记项 `{pat}` 批准了 **已不存在/已不重复** 的 {gone}'
                  f'（实际重复组 = {sorted(actual)}）')
            print('   🔑 登记的批准集合必须**等于**实际重复组 —— '
                  '第八十一轮为"警告"，本轮升级为**阻断**')
            bad += 1
        elif allowed != actual:
            print(f'\n🔴 登记项 `{pat}` 批准集合 {sorted(allowed)} '
                  f'≠ 实际重复组 {sorted(actual)} —— 必须**完全相等**')
            bad += 1

    # 🔑 第八十二轮：G385 联动 —— 共用命令**必须**有完整性门禁
    print('\n' + '-' * 70 + '\n🔑 联动检查：共用命令须有完整性门禁\n' + '-' * 70)
    gids = {gid for gid, *_ in GATES}
    for pat, rec in DUP_CMDS_GUARDIAN.items():
        guardian, guards = rec
        hit = [k for k in dups if pat.replace('{s}/', '') in k.replace('{s}/', '')]
        if not hit:
            print(f'  ⚪ `{pat}` 已无重复 —— 联动不适用')
            continue
        n = len(dups[hit[0]])
        # ⓪ `guards` 语义字段必须非空
        if not (guards or '').strip():
            print(f'  🔴 `{pat}` 的守卫登记**没说守的是什么** —— '
                  f'`guards` 为空则无法区分"相关"与"存在但无关"')
            bad += 1
            continue
        print(f'  [{pat}] 被 {n} 条门禁共用 · 声明守卫 {guardian} '
              f'（守的是 `{guards}`）')
        if guardian not in gids:
            print(f'     🔴 完整性门禁 **{guardian} 不存在**')
            bad += 1
            continue
        gcmd = [t for gid, _n, t, _k, _f in GATES if gid == guardian]
        flat = ' '.join(str(x) for x in (gcmd[0] if gcmd else []))
        # ① 自证循环：守卫不得跑被守护的那条命令
        if pat.replace('{s}/', '') in flat.replace('{s}/', ''):
            print(f'     🔴 守卫跑的仍是**同一条命令** —— 自己查自己，等于没查')
            bad += 1
            continue
        # ② 语义：守卫命令必须体现 `guards` 声明的能力
        if guards not in flat:
            print(f'     🔴 守卫命令 `{flat}` **不含**声明的能力关键词 '
                  f'`{guards}` —— 它可能是"存在但无关"的门禁')
            bad += 1
            continue
        # ③ 🔑 第八十四轮：**双向声明**（从子串匹配升级）
        #    让守卫脚本**自己**报出能力，与登记值做**相等比较**。
        #    🔴 子串匹配会放过"命令恰好含关键词却干别的事"的门禁；
        #       🔑 它必须**同时**自报该 capability 才算数。
        script = None
        for tok in (gcmd[0] if gcmd else []):
            if str(tok).endswith('.py'):
                script = str(tok)
                break
        if script is None:
            print(f'     🔴 守卫命令里找不到 .py 脚本 —— 无法做双向声明校验')
            bad += 1
            continue
        sp = os.path.join(HERE, os.path.basename(script))
        if not os.path.isfile(sp):
            print(f'     🔴 守卫脚本 `{sp}` 不存在 —— 无法自报能力')
            bad += 1
            continue
        rp = subprocess.run([sys.executable, sp, '--declare-capability'],
                            capture_output=True, text=True)
        if rp.returncode != 0:
            print(f'     🔴 守卫脚本**未声明任何能力** '
                  f'（`--declare-capability` rc={rp.returncode}）')
            bad += 1
            continue
        # 🔴 实测坑：输出行带**前导空格**（`  CAPABILITY audit-all`），
        #    `startswith` 直接判会**全空** → 误报"双向声明不一致"。
        #    🔑 必须先 strip 再判（与第六十七轮"读不到 ≠ 不存在"同源）。
        declared = set()
        for ln in rp.stdout.splitlines():
            t = ln.strip()
            if t.startswith('CAPABILITY '):
                declared.add(t.split(None, 1)[1].strip())

        if guards not in declared:
            print(f'     🔴 守卫脚本**自报的能力** {sorted(declared)} '
                  f'**不含**登记的 `{guards}` —— 双向声明不一致')
            bad += 1
            continue
        print(f'     ✅ {guardian} 独立校验 · 命令含 `{guards}` · '
              f'**脚本自报一致**（{sorted(declared)}）')
        # ④ 🔑 第八十五轮：**抽查**（防"自报撒谎"）
        #    双向声明只解决"认错人"，不解决"声明了却没实现/跑不通"。
        #    🔑 让脚本**真的跑一次**该能力：rc=0 且输出含 PROBE_OK。
        pp = subprocess.run(
            [sys.executable, sp, '--probe-capability', guards],
            capture_output=True, text=True)
        if pp.returncode != 0:
            print(f'     🔴 能力 `{guards}` **探测失败** '
                  f'(rc={pp.returncode}) —— 自报了但跑不通')
            bad += 1
            continue
        if 'PROBE_OK' not in pp.stdout:
            print(f'     🔴 探测 rc=0 但**输出无 PROBE_OK** —— '
                  f'可能是"跑了个空函数"')
            bad += 1
            continue
        print(f'     ✅ **抽查通过**：`{guards}` 真跑 rc=0 且输出 PROBE_OK')
    print('\n' + '=' * 70)
    if bad:
        print(f'🔴 {bad} 组重复命令**未获批准**')
        print('\n🔴 守卫失效')
        print('=' * 70)
        return 1
    print('✅ 守卫成立：所有重复命令**均已显式登记并说明理由**')
    print('=' * 70)
    return 0



def main():
    ap = argparse.ArgumentParser(description="一键跑全部门禁")
    ap.add_argument("--work", default="work", help="工作区目录")
    ap.add_argument("--strict", action="store_true", help="缺输入也算阻断")
    ap.add_argument("--check-dup-cmds", action="store_true",
                    help="G387：门禁命令不得误重复（刻意重复须登记）")
    ap.add_argument("--self-check-noop", action="store_true",
                    help="G377：说明性门禁是否未被伪装成软警告")
    ap.add_argument("--list", action="store_true", help="只列门禁清单")
    ap.add_argument("--verbose", "-v", action="store_true")
    a = ap.parse_args()
    if a.check_dup_cmds:
        return cmd_check_dup_cmds(a)

    if a.self_check_noop:
        return cmd_self_check_noop(a)
    if a.list:
        return cmd_list(a)
    return cmd_run(a)


if __name__ == "__main__":
    sys.exit(main())
