#!/usr/bin/env python3
"""可交付性 + 运行期可观测性（第二十轮 A / B 类）。

**🔑 A 类核心**：
> **交付盲区不是打包器功能，而是"从构建机到玩家桌面的完整契约"。**
> 一个复刻产物至少应回答五个问题：**包含什么文件 · 由哪些输入和工具链生成 ·
> 能否在安装机上运行 · 首次启动做了什么 · 卸载和升级后留下什么**。
>
> 🔴 **做完了但装不上 = 没做完**。

**🔑 B 类核心**：
> 可观测性的正确结构是**四层"证明链"**，而非再加一个日志库：
> **运行期自检 · 玩家导出 · 崩溃最后一帧 · 开发者重建环境**。
>
> 🔴 **最后一帧必须保存连续窗口** ——
> **单一崩溃堆栈不足以复现输入/时间轴问题**。

用法:
  game_delivery_observe.py --manifest # 🔴 交付清单 build_manifest
  game_delivery_observe.py --repro    # 构建可复现**三级标记**
  game_delivery_observe.py --firstrun # 🔴 首启契约
  game_delivery_observe.py --residual # 🔴 卸载与共存**七类文件**
  game_delivery_observe.py --observe  # 🔴 可观测**四层**
  game_delivery_observe.py --selfcheck # 🔴 自检**五态**
  game_delivery_observe.py --lastframe # 🔴 最后一帧**环形缓冲**
  game_delivery_observe.py --version  # 🔴 版本**可识别性**
  game_delivery_observe.py --diag     # 诊断包结构与隐私
  game_delivery_observe.py --init ledger/delivery_observe.csv
  game_delivery_observe.py --check ledger/delivery_observe.csv --gate

退出码: 0 通过 / 1 缺项 / 2 用法错误
"""
import argparse
import csv
import os
import sys

# 🔴 交付清单
MANIFEST_FIELDS = [
    'build_id', 'source_commit', 'engine_commit', 'toolchain_digest',
    'input_artifact_digests', '**output_inventory**',
    'runtime_dependency_manifest', '**first_run_plan**', 'install_paths',
    '**expected_residual_paths**', '**side_by_side_rules**',
    'installer_signoff',
]

MANIFEST_FIVE = [
    '**包含什么文件**', '**由哪些输入和工具链生成**',
    '**能否在安装机上运行**', '**首次启动做了什么**',
    '**卸载和升级后留下什么**',
]

MANIFEST_RULE = [
    '🔑 应由 **CI 自动生成**，随后进入独立的"**交付验收**"阶段',
    '🔑 `build_id` 还须嵌入**可执行文件、启动日志、诊断报告与崩溃附件** —— '
    '确保玩家报障时能**精确到一次构建**',
    '🔴 任何**未声明文件**进入 `unknown_artifact` 清单，'
    '**而非自动删除或忽略**',
]

# 可复现三级
REPRO_LEVELS = [
    '**源码/资产可复现**', '**中间产物可复现**', '**最终可执行可复现**',
]

REPRO_ENV = [
    '构建路径', '**时间戳**', 'locale', '文件顺序', '并行性', '用户/组',
    '宿主机名', '架构', '内核信息',
]

REPRO_RULE = [
    '🔑 逐字节可复现意味着**外部观察者无法从输出区分原始构建机与二次构建机**',
    '🔴 **不能直接保证游戏可玩**，但它能把"同一源码为何产物不同"'
    '从取证泥潭变成**可复现实验**',
    '🔑 若依赖封闭工具链应明确标记 `reproducible: partial`，'
    '**分别记录三级**',
    '🔴 否则 `build_id` 只能证明"这是本次构建产物"，'
    '**不能证明跨环境可重建**',
]

# 🔴 首启
FIRSTRUN_FIELDS = [
    '**first_run_timeout_ms**', 'first_run_interactive_steps',
    'user_visible_progress_schema', '**can_cancel**', '**can_resume**',
    '**rollback_targets**', 'bootstrap_log_path',
    'bootstrap_health_checks',
]

FIRSTRUN_CHECKS = [
    '图形设备', '音频设备', '存档目录', '**着色器缓存目录**', '运行库',
    '磁盘空间', '**写入权限**',
]

FIRSTRUN_RULE = [
    '🔑 首启必须由**时间预算和可中断性共同定义**',
    '🔑 每一步须给出**玩家能理解的状态**，而非长期白屏',
    '🔴 首启若在**着色器编译、资产转换或旧存档迁移**中途崩溃，'
    '重启后必须能**定位到最近完成阶段并从该阶段继续** —— '
    '**不能把"重新从头处理"当作正确实现**',
]

# 🔴 卸载与共存
RESIDUAL_SEVEN = [
    'install_files', '**user_config_files**', '**user_save_files**',
    'diagnostic_files', 'cache_files', 'ephemeral_lock_files',
    '**shared_runtime_files**',
]

RESIDUAL_POLICY = ['remove', 'preserve', '**prompt**']

RESIDUAL_RULE = [
    '🔴 **卸载与升级是跨构建状态迁移，不是安装器的反向动作**',
    '🔑 卸载默认移除安装文件与缓存，**显式保留用户选择保留的内容**',
    '🔑 升级须验证旧用户目录的**所有权、权限、符号链接、文件锁和'
    '正在运行的实例**',
    '🔑 按 `game_version` **分桶**用户数据目录',
]

SIDE_BY_SIDE = '🔑 `side_by_side_versioning` 应明确**可执行目录、用户数据目录、'
'配置和缓存四者如何隔离**；🔴 **若采用全局锁或共享服务端口，'
'则 `side_by_side` 只能是 `false` 并说明锁归属**'

RESIDUAL_NOTE = '🔑 这与"只存部件不存层级会改旧存档外观"一脉相承 —— '
'**交付层面的目录层级本身也是跨版本外观与状态契约**'

# 🔴 可观测四层
OBSERVE_FOUR = [
    ('**运行期自检**', '每 5 秒采样一次，**发现连续异常后才向玩家提示**'),
    ('**玩家导出**', '玩家按组合键触发"导出诊断包"，**不触发则不上传**'),
    ('**崩溃最后一帧**', '崩溃处理器**退出前先落本地包**，'
     '联网上传**只能是可选项**'),
    ('**开发者重建**', '导入包后按 `environment_lock` '
     '**自动生成最接近的环境镜像**'),
]

OBSERVE_RULE = [
    '🔑 玩家敏感信息必须经过**显式"可识别信息预览—确认发送"两步**',
]

# 🔴 自检五态
SELFCHECK_STATES = [
    ('ok', '正常'),
    ('**degraded_acceptable**', '有意降级可接受，如 120Hz 屏在强制 60Hz 下'),
    ('**degraded_must_warn**', '降级但必须告知玩家'),
    ('**environment_unsupported**', '环境分支，如 Vulkan 缺失但 DirectX 可用'),
    ('**fatal_blocking**', '如着色器编译后每帧重编译'),
]

SELFCHECK_RULE = [
    '🔴 自检的核心是**区分"已知受限""环境不支持""系统故障"**，'
    '**而不是把一切报错上报**',
    '🔑 自检结果应进入**主菜单角落或诊断菜单**，但**不遮挡首次体验**',
    '🔑 健康检查必须有**权重、超时、依赖关系和降级动作** —— '
    '**仅输出"GPU: OK/FAIL"没有复刻价值**',
]

# 🔴 最后一帧
LASTFRAME_KEEP = [
    '崩溃前 N 帧的**世界状态快照**', '**输入事件**', '**时间域**',
    '**动画状态**', '**相机状态**', '**音频事件**',
    '**RNG 种子/检查点**', '**渲染指令序列**',
]

LASTFRAME_RULE = [
    '🔴 **最后一帧必须保存连续窗口** —— '
    '**单一崩溃堆栈不足以复现输入/时间轴问题**',
    '🔑 **N 不应全局统一，而按子系统设置** —— '
    '与"回溯窗口不能全局统一"一脉相承，可扩展为 '
    '`last_frame_budget_ms` 与 `retained_frame_count`',
    '🔑 为避免崩溃时写入损坏，**先写临时包，只有校验通过后原子改名**',
    '🔴 **崩溃处理器不得访问可能已被破坏的游戏堆**',
]

# 🔴 版本可识别
VERSION_FIELDS = [
    'version', '**build_id**', 'source_commit', 'engine_commit',
    'build_type', '**build_time_source**', 'artifact_digest',
    'config_digest',
]

VERSION_EXTRA = ['**loaded_patches**', '**baseline_build_id**']

VERSION_RULE = [
    '🔑 要**同时覆盖人类可读与机器可解析**',
    '🔑 **标题菜单、日志首行、崩溃附件、诊断包和安装清单必须完全一致**',
    '🔑 若允许补丁热更新，还要加入 `loaded_patches` 和 '
    '`baseline_build_id`',
    '🔴 否则开发者只能知道玩家**下载了哪个安装包**，'
    '**无法判断运行时实际替换了哪些模块**',
]

# 诊断包
DIAG_NAME = 'diagnosis-<build_id>-<session_id>-<timestamp>.zip'

DIAG_CONTENTS = [
    'manifest.json', 'self_check.json', '**last_frames.rr**', '日志',
    '配置摘要', '屏幕截图', 'minidump', '**GPU 状态**', '音频设备',
    '输入设备', '进程和模块清单',
]

CONFLICTS = [
    '❌ **做完了但装不上**就算完成',
    '❌ 未声明文件自动删除或忽略',
    '❌ 用 `build_id` 冒充跨环境可重建',
    '❌ **首启崩溃后重新从头处理**',
    '❌ 卸载把用户存档一起删',
    '❌ 全局锁却声明支持 side_by_side',
    '❌ **单一崩溃堆栈当最后一帧证据**',
    '❌ `retained_frame_count` 全局统一',
    '❌ 崩溃处理器访问已破坏的游戏堆',
    '❌ 未经预览确认就上传玩家敏感信息',
    '❌ **仅输出"GPU: OK/FAIL"**',
    '❌ 标题菜单与崩溃附件版本号不一致',
    '❌ **通用 APM 自动 instrumentation 替代玩家操作序列**',
]

FIELDS = [
    ('item_id', '项编号'),
    ('domain', '域（manifest / repro / firstrun / residual / observe / '
               'selfcheck / lastframe / version / diag）'),
    ('legacy_value', '**原版值**'),
    ('new_value', '新引擎值'),
    ('match', '**是否一致**'),
    ('tolerance', '**允许偏差**'),
    ('evidence', '证据等级 1-8'),
]


def _hdr(t, w=80):
    print('=' * w)
    print(t)
    print('=' * w)


def cmd_manifest(a):
    _hdr('🔴 交付清单（build_manifest）')
    print('必须回答: ' + ' · '.join(MANIFEST_FIVE))
    print('\n字段: ' + ' · '.join(MANIFEST_FIELDS))
    print('\n规则:')
    for r in MANIFEST_RULE:
        print(f'   {r}')
    print(f'\n   🔴 **做完了但装不上 = 没做完**')
    return 0


def cmd_repro(a):
    _hdr('构建可复现（**三级标记**）')
    print('三级: ' + ' · '.join(REPRO_LEVELS))
    print('\n环境锁定: ' + ' · '.join(REPRO_ENV))
    print('\n规则:')
    for r in REPRO_RULE:
        print(f'   {r}')
    return 0


def cmd_firstrun(a):
    _hdr('🔴 首启契约')
    print('字段: ' + ' · '.join(FIRSTRUN_FIELDS))
    print('\n自检项: ' + ' · '.join(FIRSTRUN_CHECKS))
    print('\n规则:')
    for r in FIRSTRUN_RULE:
        print(f'   {r}')
    return 0


def cmd_residual(a):
    _hdr('🔴 卸载与共存')
    print('七类文件: ' + ' · '.join(RESIDUAL_SEVEN))
    print('\n策略: ' + ' · '.join(RESIDUAL_POLICY))
    print('\n规则:')
    for r in RESIDUAL_RULE:
        print(f'   {r}')
    print(f'\n   {SIDE_BY_SIDE}')
    print(f'\n   {RESIDUAL_NOTE}')
    return 0


def cmd_observe(a):
    _hdr('🔴 可观测四层')
    for k, why in OBSERVE_FOUR:
        print(f'   {k:<18} {why}')
    print('\n规则:')
    for r in OBSERVE_RULE:
        print(f'   {r}')
    print(f'\n   诊断包命名: {DIAG_NAME}')
    print('\n包含: ' + ' · '.join(DIAG_CONTENTS))
    return 0


def cmd_selfcheck(a):
    _hdr('🔴 自检五态')
    for k, why in SELFCHECK_STATES:
        print(f'   {k:<26} {why}')
    print('\n规则:')
    for r in SELFCHECK_RULE:
        print(f'   {r}')
    return 0


def cmd_lastframe(a):
    _hdr('🔴 最后一帧（**环形缓冲**）')
    print('保留: ' + ' · '.join(LASTFRAME_KEEP))
    print('\n规则:')
    for r in LASTFRAME_RULE:
        print(f'   {r}')
    return 0


def cmd_version(a):
    _hdr('🔴 版本可识别性')
    print('字段: ' + ' · '.join(VERSION_FIELDS))
    print('\n热更新还要加: ' + ' · '.join(VERSION_EXTRA))
    print('\n规则:')
    for r in VERSION_RULE:
        print(f'   {r}')
    return 0


def cmd_diag(a):
    _hdr('诊断包')
    print(f'   命名: {DIAG_NAME}')
    print('\n包含: ' + ' · '.join(DIAG_CONTENTS))
    print('\n规则:')
    for r in OBSERVE_RULE:
        print(f'   {r}')
    return 0


def cmd_init(a):
    os.makedirs(os.path.dirname(a.init) or '.', exist_ok=True)
    with open(a.init, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow([k for k, _ in FIELDS])
        w.writerow(['TODO'] * len(FIELDS))
    print(f'已生成交付/可观测表: {a.init}')
    print('\n⚠️ 九域：manifest / repro / firstrun / residual / observe / '
          'selfcheck / lastframe / version / diag')
    return 0


def cmd_check(a):
    if not os.path.exists(a.check):
        print(f'❌ 文件不存在: {a.check}')
        return 2
    with open(a.check, encoding='utf-8', errors='replace', newline='') as f:
        rows = list(csv.DictReader(f))
    if not rows:
        print('❌ 空表')
        return 1

    def g(r, k):
        return (r.get(k) or '').strip()

    mismatch, no_legacy, no_grade = [], [], []
    for i, r in enumerate(rows, 1):
        m = g(r, 'match').lower()
        if m not in ('yes', 'y', 'true', '是', '一致'):
            mismatch.append(i)
        if not g(r, 'legacy_value') or g(r, 'legacy_value') == 'TODO':
            no_legacy.append(i)
        ev = g(r, 'evidence')
        if not ev or ev == 'TODO':
            no_grade.append(i)
        else:
            d = ev.split('.')[0].strip()
            if d.isdigit() and int(d) >= 7:
                no_grade.append(i)

    print('=' * 76)
    print(f'交付/可观测 · {len(rows)} 条')
    print('=' * 76)
    if mismatch:
        print(f'\n🚫 **不一致** {len(mismatch)} 条（行 {mismatch[:15]}）')
    if no_legacy:
        print(f'\n❌ {len(no_legacy)} 条缺**原版值**（行 {no_legacy[:15]}）')
    if no_grade:
        print(f'\n🚫 {len(no_grade)} 条**证据等级缺失或 ≥7 级**'
              f'（行 {no_grade[:15]}）')

    if not (mismatch or no_legacy or no_grade):
        print('\n✅ 交付/可观测：一致、原版值完整、证据等级达标')

    print('\n🔑 **做完了但装不上 = 没做完。**')
    print('   **最后一帧必须保存连续窗口；单一崩溃堆栈不够。**')
    print('   **版本号在标题菜单与崩溃附件必须完全一致。**')
    return 1 if (a.gate_check and (mismatch or no_legacy or no_grade)) else 0


def main():
    ap = argparse.ArgumentParser(description='可交付性与可观测性')
    ap.add_argument('--manifest', action='store_true')
    ap.add_argument('--repro', action='store_true')
    ap.add_argument('--firstrun', action='store_true')
    ap.add_argument('--residual', action='store_true')
    ap.add_argument('--observe', action='store_true')
    ap.add_argument('--selfcheck', action='store_true')
    ap.add_argument('--lastframe', action='store_true')
    ap.add_argument('--version', action='store_true')
    ap.add_argument('--diag', action='store_true')
    ap.add_argument('--init')
    ap.add_argument('--check')
    ap.add_argument('--gate-check', action='store_true')
    a = ap.parse_args()
    fns = {'manifest': cmd_manifest, 'repro': cmd_repro,
           'firstrun': cmd_firstrun, 'residual': cmd_residual,
           'observe': cmd_observe, 'selfcheck': cmd_selfcheck,
           'lastframe': cmd_lastframe, 'version': cmd_version,
           'diag': cmd_diag}
    for k, fn in fns.items():
        if getattr(a, k):
            return fn(a)
    if a.init:
        return cmd_init(a)
    if a.check:
        return cmd_check(a)
    print('❌ 需要 --manifest / --repro / --firstrun / --residual / '
          '--observe / --selfcheck / --lastframe / --version / --diag / '
          '--init / --check 之一')
    return 2


if __name__ == '__main__':
    sys.exit(main())
