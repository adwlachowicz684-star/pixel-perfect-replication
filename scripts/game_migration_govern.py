#!/usr/bin/env python3
"""演进治理 + 老玩家迁移 + 自动化预算（第十九轮 C / D / E 类）。

**🔑 C 类核心**：
> **复刻不是终点，是长期分支。**
> 维护**原版基线、兼容层与偏离账本三棵树**，必须**物理分离**。

**🔑 D 类核心**：
> 老玩家迁移是"**旧承诺在新版本仍然成立**"，**不是把字节搬到新格式**。
> 🔴 迁移必须拆成**契约、资产、外观与软资产**四类，
> **四类不能合并验收**。

**🔑 E 类核心**：
> 自动化的价值**不是覆盖 78 个脚本**，而是**每次改变只跑最小风险集**。
> 🔴 **78 个脚本跑不完 = 没跑**。

用法:
  game_migration_govern.py --trees  # 🔴 三棵树**物理分离**
  game_migration_govern.py --update # 原版更新**兼容窗口**
  game_migration_govern.py --debt   # 🔴 技术债要写"**当时为什么**"
  game_migration_govern.py --freeze # **重构安全边界**冻结八类
  game_migration_govern.py --mig4   # 🔴 迁移**四表不能合并**
  game_migration_govern.py --migrate # 迁移**双轨可回滚**
  game_migration_govern.py --dual   # 🔴 双轨期**三态承诺**
  game_migration_govern.py --feedback # 反馈回到**规格条目**
  game_migration_govern.py --auto   # 🔴 自动化**四档**
  game_migration_govern.py --noise  # 假阳性**降噪**
  game_migration_govern.py --testbook # 🔴 测试账本
  game_migration_govern.py --init ledger/migration_govern.csv
  game_migration_govern.py --check ledger/migration_govern.csv --gate

退出码: 0 通过 / 1 缺项 / 2 用法错误
"""
import argparse
import csv
import os
import sys

# 🔴 三棵树
TREES = [
    ('**原版基线树**', '目标规格 · 资源事实 · 测量',
     '原版新版本或新证据', '证据可回溯、**无实现细节污染**'),
    ('**兼容层**', '接口 · 模拟实现 · 策略替换',
     '需要匹配原版或适配目标平台', '同输入状态与表现回归'),
    ('**偏离账本**', '有意偏离 · 理由 · 风险 · 回滚',
     '任何非 must-match 变化', '审批链 · owner · 到期复审'),
]

TREE_RULE = '🔑 **原版基线、兼容层与偏离账本必须物理分离**'

# 原版更新
UPDATE_POLICY = [
    ('**小补丁**', '快速回归', '变更资源影响面 + 冒烟回放',
     '更新基线和证据哈希'),
    ('**重大更新**', '差异扫描', '全量关键路径、版本差异报告',
     '新基线分支'),
    ('**EOL 版本**', '冻结', '旧版兼容快照',
     '停止跟随，保留可复现环境'),
]

UPDATE_RULE = '🔑 兼容窗口必须**区分补丁、重大更新与 EOL 基线**'

# 技术债
DEBT_FIELDS = [
    '问题', '临时方案', '受影响模块', '**触发原因**', '**禁止重构原因**',
    '监测指标', '**偿还条件**', 'owner', '**到期日**',
]

DEBT_RULE = [
    '🔑 技术债模板要把"**当时为什么**"写成**可执行约束**',
    '🔑 文档应自动从**代码符号链接到规格条目和偏离许可**',
    '🔴 **删除代码时必须检查文档引用**；若代码删除后文档仍引用旧符号，'
    '**应自动失败**，而不是留下"曾经这样实现"的孤证',
]

# 冻结
FREEZE_EIGHT = [
    '模块接口', '**事件顺序**', '状态字段', '**持久格式**', '协议 ID',
    '资源 ID', '**确定性顺序**', '**计时语义**',
]

FREEZE_RULE = [
    '🔑 **内部性能优化可以发生**，但必须附**同输入状态重放和表现层回归**',
    '🔴 若新版性能模式改变**加载、插值或帧 pacing**，还要检查它是否把'
    '"**不可见优化**"变成**玩家可感知行为**',
]

# 🔴 迁移四表
MIG_FOUR = [
    ('**契约**', '进度 · 解锁 · 货币 · **成就状态** · **NG+ 状态**'),
    ('**资产**', '装备 · 库存 · 配置'),
    ('**外观**', '服装 · 染剂 · 显示选项 · **旧版独占物**'),
    ('**软资产**', '控制方案 · 提示偏好 · 辅助选项 · 好友备注 · '
     '**"玩家自己理解的规则"**'),
]

MIG_RULE = [
    '🔴 **四类不能合并验收**',
    '🔴 把外观放进通用 inventory 表 → '
    '**会在旧存档上改变层级与显示顺序**',
    '🔴 把成就完成时间覆盖为新版本地时间 → **丢失原版时间语义**',
    '🔴 把 NG+ 契约当普通配置导入 → **破坏跨周目承诺**',
]

# 迁移流程
MIGRATE_STEPS = [
    '校验原始校验值', '**在隔离区解析**', '**生成逐项映射和未映射字段**',
    '**预览差异**', '执行', '**导出可读报告**',
    '**保留旧档与可逆回滚点**',
]

MIGRATE_RULE = [
    '🔑 **迁移必须双轨运行并支持暂停、继续和回滚**',
    '🔴 对未识别字段采用 `preserve_unknown` **而不是清零**',
    '🔴 对字段冲突记录"**来源版本、发现值、处理动作**"，'
    '**禁止只写"修复损坏"**',
    '🔑 迁移成功后仍应**允许玩家返回旧版兼容快照**，'
    '至少支持**最近一次旧档恢复**',
]

# 🔴 双轨三态
DUAL_THREE = [
    ('**legacy_only**', '原版独有'),
    ('**both**', '共享'),
    ('**remaster_only**', '新版独有'),
]

DUAL_RULE = [
    '🔑 所有**宣传、商店页、补丁说明和平台列表**必须'
    '**生成同一份契约矩阵**',
    '🔴 **不能出现代码支持但文案不支持、或市场文案承诺代码未实现**',
    '🔑 **原版下线、价格变化、外观下架和跨平台权益必须分别说明** —— '
    '它们影响玩家心理契约',
    '🔴 若只说"进度可继承"而未说明外观、NG+ 或平台权益 → '
    '**玩家会把重制版理解为原版等价替代品，直接破坏心理契约**',
]

# 反馈
FEEDBACK_FIELDS = [
    '原版版本', '新版版本', '平台', '**旧档**', '复现步骤', '期望', '实际',
    '**录像**',
]

FEEDBACK_RULE = [
    '🔴 **老玩家反馈必须能回到规格条目，不能只做情绪聚类**',
    '🔑 **去重键是环境指纹和精确步骤，不是"手感不好"的文本相似度**',
    '🔑 优先级由**原版承诺破坏、数据丢失风险、老玩家专属权益和复现率**'
    '共同决定',
    '🔑 对争议变化**先公开原版行为、偏离理由、验收范围与替代方案** —— '
    '**模糊公告会放大老玩家敌意**',
]

# 🔴 自动化四档
AUTO_TIERS = [
    ('**门禁**', '确定性重放 · 关键状态 · 致命错误', '10–20 分钟',
     '立即阻止回归', '❌ 跑全量画面测试'),
    ('**提交**', '关键路径 · 平台矩阵 · 性能预算', '1–2 小时',
     '覆盖高风险变更', '❌ 用平均帧率替代尾延迟'),
    ('**夜间**', '长会话 · 随机输入 · 全量迁移', '整夜',
     '发现稀有状态和泄漏', '❌ 只保留最新一次日志'),
    ('**发布**', '人工验收 · 极端平台 · 契约生成', '按里程碑',
     '形成最终可交付证据', '❌ 临时手工验证不归档'),
]

AUTO_MUST = [
    '构建可重现', '证据指纹', '输入重放', '状态字段比对', '资源校验',
    '跨版本差异扫描', '**存档迁移 dry-run**', '兼容窗口检查',
    '发布契约生成',
]

AUTO_NOT = [
    '**证据权重**', '**原版 bug 判定**', '**老玩家预期**', '**叙事取舍**',
    '**跨版本审美评价**',
]

AUTO_RULE = [
    '🔑 **不宜自动化的五项**可由机器提出建议，但**最终必须由人签字**',
    '🔑 **运行时间预算应按结果成本而非脚本数量分配**',
    '🔑 一个**10 分钟但能阻止档位错乱**的测试，'
    '价值高于 **100 个纯画面截图测试**',
]

# 降噪
NOISE_SPLIT = [
    '语义区域', 'HDR/色域', '时序', 'UI', '**景深**', '**运动模糊**',
]

NOISE_RULE = [
    '🔑 画面比较必须**先拆语义区、UI 区、景深、运动模糊和色彩元数据**',
    '🔑 逻辑比较**必须使用状态白名单**',
    '🔑 每次报警保留**前后若干帧、输入、状态、原版参考和容忍参数**，'
    '并**自动生成最小重放**',
    '🔑 连续三次在容忍带内且不改变玩家结果可**降级为观察**，'
    '**但不得从账本删除**',
]

# 测试账本
TESTBOOK_FIELDS = [
    'owner', '业务规格', '采样路径', '依赖资源', '平台', '平均运行时间',
    '**失败率**', '**最近误报**', '**最近漏报**', '**复审日**',
]

TESTBOOK_RULE = [
    '🔑 **没有 owner 和复审日的测试视为未维护**',
    '🔑 运行时间超预算、长期无人维护或只通过巧合的测试进入"**隔离池**"，'
    '**不进入门禁**',
    '🔑 对纯随机输入，**用不变量测试而非固定录像**是更优成本选择',
    '🔴 但涉及 **coyote time、输入窗口和帧精确反馈**时，'
    '**固定输入仍不可替代**',
]

CONFLICTS = [
    '❌ 三棵树混在一起',
    '❌ 迁移四表合并验收',
    '❌ **未识别字段清零**',
    '❌ 字段冲突只写"修复损坏"',
    '❌ 迁移后不允许返回旧档',
    '❌ **只说"进度可继承"**而隐去外观/NG+/平台权益',
    '❌ 代码支持但文案不支持',
    '❌ 反馈只做情绪聚类',
    '❌ **跑全量画面测试作门禁**',
    '❌ **用平均帧率替代尾延迟**',
    '❌ 只保留最新一次日志',
    '❌ 临时手工验证不归档',
    '❌ **自动化覆盖率替代像素证据**',
    '❌ 假阳性从账本删除',
    '❌ 无 owner 和复审日的测试进门禁',
]

FIELDS = [
    ('item_id', '项编号'),
    ('domain', '域（trees / update / debt / freeze / mig4 / migrate / '
               'dual / feedback / auto / noise / testbook）'),
    ('legacy_value', '**原版值**'),
    ('new_value', '新引擎值'),
    ('match', '**是否一致**'),
    ('tolerance', '**允许偏差**'),
    ('owner', '**责任人 + 到期日**'),
]


def _hdr(t, w=80):
    print('=' * w)
    print(t)
    print('=' * w)


def cmd_trees(a):
    _hdr('🔴 三棵树（**物理分离**）')
    for name, has, trig, acc in TREES:
        print(f'\n   【{name}】')
        print(f'     内容: {has}')
        print(f'     修改触发: {trig}')
        print(f'     验收: {acc}')
    print(f'\n   {TREE_RULE}')
    return 0


def cmd_update(a):
    _hdr('原版更新（**兼容窗口**）')
    for what, resp, test, out in UPDATE_POLICY:
        print(f'   {what:<14} 响应={resp:<8} 验证={test}')
        print(f'                产出={out}')
    print(f'\n   {UPDATE_RULE}')
    return 0


def cmd_debt(a):
    _hdr('🔴 技术债（写"**当时为什么**"）')
    print('字段: ' + ' · '.join(DEBT_FIELDS))
    print('\n规则:')
    for r in DEBT_RULE:
        print(f'   {r}')
    return 0


def cmd_freeze(a):
    _hdr('重构安全边界（**冻结八类**）')
    for f in FREEZE_EIGHT:
        print(f'   · {f}')
    print('\n规则:')
    for r in FREEZE_RULE:
        print(f'   {r}')
    return 0


def cmd_mig4(a):
    _hdr('🔴 迁移四表（**不能合并验收**）')
    for k, why in MIG_FOUR:
        print(f'   {k:<12} {why}')
    print('\n规则:')
    for r in MIG_RULE:
        print(f'   {r}')
    return 0


def cmd_migrate(a):
    _hdr('迁移流程（**双轨可回滚**）')
    for i, s in enumerate(MIGRATE_STEPS, 1):
        print(f'   {i}. {s}')
    print('\n规则:')
    for r in MIGRATE_RULE:
        print(f'   {r}')
    return 0


def cmd_dual(a):
    _hdr('🔴 双轨期三态承诺')
    for k, why in DUAL_THREE:
        print(f'   {k:<18} {why}')
    print('\n规则:')
    for r in DUAL_RULE:
        print(f'   {r}')
    return 0


def cmd_feedback(a):
    _hdr('反馈（**回到规格条目**）')
    print('字段: ' + ' · '.join(FEEDBACK_FIELDS))
    print('\n规则:')
    for r in FEEDBACK_RULE:
        print(f'   {r}')
    return 0


def cmd_auto(a):
    _hdr('🔴 自动化四档')
    for name, has, dur, gain, ban in AUTO_TIERS:
        print(f'\n   【{name}】 {dur}')
        print(f'     内容: {has}')
        print(f'     收益: {gain}')
        print(f'     禁止: {ban}')
    print('\n必须自动化: ' + ' · '.join(AUTO_MUST))
    print('\n不宜自动化: ' + ' · '.join(AUTO_NOT))
    print('\n规则:')
    for r in AUTO_RULE:
        print(f'   {r}')
    return 0


def cmd_noise(a):
    _hdr('假阳性降噪')
    print('画面拆分: ' + ' · '.join(NOISE_SPLIT))
    print('\n规则:')
    for r in NOISE_RULE:
        print(f'   {r}')
    return 0


def cmd_testbook(a):
    _hdr('🔴 测试账本')
    print('字段: ' + ' · '.join(TESTBOOK_FIELDS))
    print('\n规则:')
    for r in TESTBOOK_RULE:
        print(f'   {r}')
    return 0


def cmd_init(a):
    os.makedirs(os.path.dirname(a.init) or '.', exist_ok=True)
    with open(a.init, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow([k for k, _ in FIELDS])
        w.writerow(['TODO'] * len(FIELDS))
    print(f'已生成治理/迁移表: {a.init}')
    print('\n⚠️ 十一域：trees / update / debt / freeze / mig4 / migrate / '
          'dual / feedback / auto / noise / testbook')
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

    mismatch, no_legacy, no_owner = [], [], []
    for i, r in enumerate(rows, 1):
        m = g(r, 'match').lower()
        if m not in ('yes', 'y', 'true', '是', '一致'):
            mismatch.append(i)
        if not g(r, 'legacy_value') or g(r, 'legacy_value') == 'TODO':
            no_legacy.append(i)
        ow = g(r, 'owner')
        if (not ow or ow == 'TODO'
                or ('到期' not in ow and '/' not in ow and '-' not in ow
                    and '~' not in ow)):
            no_owner.append(i)

    print('=' * 76)
    print(f'治理/迁移 · {len(rows)} 条')
    print('=' * 76)
    if mismatch:
        print(f'\n🚫 **不一致** {len(mismatch)} 条（行 {mismatch[:15]}）')
    if no_legacy:
        print(f'\n❌ {len(no_legacy)} 条缺**原版值**（行 {no_legacy[:15]}）')
    if no_owner:
        print(f'\n🚫 {len(no_owner)} 条**缺责任人或到期日**'
              f'（行 {no_owner[:15]}）—— '
              '**否则长期分支会在无人认领中腐烂**')

    if not (mismatch or no_legacy or no_owner):
        print('\n✅ 治理/迁移：一致、原版值完整、有 owner 与到期日')

    print('\n🔑 **复刻不是终点，是长期分支。**')
    print('   **迁移是"旧承诺在新版本仍成立"，不是搬字节。**')
    print('   **78 个脚本跑不完 = 没跑。**')
    return 1 if (a.gate_check and (mismatch or no_legacy or no_owner)) else 0


def main():
    ap = argparse.ArgumentParser(description='演进治理与迁移')
    ap.add_argument('--trees', action='store_true')
    ap.add_argument('--update', action='store_true')
    ap.add_argument('--debt', action='store_true')
    ap.add_argument('--freeze', action='store_true')
    ap.add_argument('--mig4', action='store_true')
    ap.add_argument('--migrate', action='store_true')
    ap.add_argument('--dual', action='store_true')
    ap.add_argument('--feedback', action='store_true')
    ap.add_argument('--auto', action='store_true')
    ap.add_argument('--noise', action='store_true')
    ap.add_argument('--testbook', action='store_true')
    ap.add_argument('--init')
    ap.add_argument('--check')
    ap.add_argument('--gate-check', action='store_true')
    a = ap.parse_args()
    fns = {'trees': cmd_trees, 'update': cmd_update, 'debt': cmd_debt,
           'freeze': cmd_freeze, 'mig4': cmd_mig4, 'migrate': cmd_migrate,
           'dual': cmd_dual, 'feedback': cmd_feedback, 'auto': cmd_auto,
           'noise': cmd_noise, 'testbook': cmd_testbook}
    for k, fn in fns.items():
        if getattr(a, k):
            return fn(a)
    if a.init:
        return cmd_init(a)
    if a.check:
        return cmd_check(a)
    print('❌ 需要 --trees / --update / --debt / --freeze / --mig4 / '
          '--migrate / --dual / --feedback / --auto / --noise / '
          '--testbook / --init / --check 之一')
    return 2


if __name__ == '__main__':
    sys.exit(main())
