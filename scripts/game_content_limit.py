#!/usr/bin/env python3
"""内容冗余必要性 + 系统极限 + 等待/容错/一致性（第十八轮 C / D / E-H）。

**🔑 C 类核心**：
> **重复本身不是冗余，删除结果才是判定。**
> 🔴 Unity 引用工具会把**运行时字符串加载、反射、远程目录或代码生成引用**
> 判为无引用 —— 应设"**待人工复核**"而非自动删除。
> 🔴 **"精简"可能把低密度节奏改为连续高强度，使原作呼吸感失效。**

**🔑 D 类核心**：
> **组合边界比单值上限更容易暴露差异。**
> 极限测试应按 `**capacity × fan-out × rate × concurrency**`。

用法:
  game_content_limit.py --necessity # 🔴 内容**必要性证明**
  game_content_limit.py --variant   # 重复要记**变体轴**
  game_content_limit.py --filler    # 填充物**静态+运行时**双证据
  game_content_limit.py --required  # 必做/可做**四层契约**
  game_content_limit.py --trace     # 删除的**反向追踪**
  game_content_limit.py --limits    # 🔴 极限是**组合**不是大数
  game_content_limit.py --overflow  # 🔴 溢出策略**不能让类型默认值替代设计**
  game_content_limit.py --wait      # 🔴 等待**诚实进度**
  game_content_limit.py --undo      # 误操作**可逆性分级**
  game_content_limit.py --consist   # 🔴 跨系统**同义证明**
  game_content_limit.py --init ledger/content_limit.csv
  game_content_limit.py --check ledger/content_limit.csv --gate

退出码: 0 通过 / 1 缺项 / 2 用法错误
"""
import argparse
import csv
import os
import sys

# 🔴 必要性
NECESSITY_TYPES = [
    '关卡', '遭遇', '对话', '教程', '收藏', '支线', '拾取', '路线', '动画',
    '音效', '环境叙事', '过场', '提示', '菜单页',
]

NECESSITY_PURPOSE = [
    '规则', '引导', '挑战', '选择', '奖励', '叙事', '**节奏**', '氛围',
    '教学', '指引', '经济', '元游戏',
]

NECESSITY_FLAGS = [
    '**optional**', '**skippable**', 'required_for_completion',
    'required_for_mastery', 'required_for_guide', '**required_for_pacing**',
    'required_for_skill', 'required_for_worldbuilding', 'aesthetic_only',
    'filler_suspected', '**removal_impact**', 'downstream_dependents',
]

NECESSITY_RULE = [
    '🔑 **重复本身不是冗余，删除结果才是判定**',
    '🔑 `purpose` 可多选；`removal_impact` **必须列出受影响系统**，'
    '**而非只填"影响体验"**',
]

# 变体轴
VARIANT_AXES = [
    '位置', '敌人组合', '资源压力', '奖励', '光照', '视角', '音效',
    '**敌人 AI**', '到达时间', '**玩家状态**',
]

VARIANT_RULE = [
    '🔑 同一房间、敌人、对话、提示的第二次出现，可能改变上述十项',
    '🔑 **只有变体轴全部为空，才可能是真正冗余**',
    '🔑 特别识别"**结构性重复**"：可选支线数量压缩 · 收集密度变化 · '
    '敌人种类减少 · **路径变直** · 教程文字删除 · 对话分支合并',
]

VARIANT_RULE2 = '🔴 **重制时"精简"可能把低密度节奏改为连续高强度，'
'使原作呼吸感失效**'

# 填充物
FILLER_STATIC = [
    '低唯一性资产', '低频引用', '相似路径', '重复蓝图', '低对话分支数',
    '**零脚本事件**', '**零奖励**', '**零新教学**',
]

FILLER_RUNTIME = [
    '玩家到达率', '完成率', '回退率', '平均停留', '**死亡后是否重走**',
    '**是否改变后续选择**', '**是否连接新区域**',
]

FILLER_RULE = '🔑 填充物识别必须**同时用静态与运行时证据** —— '
'内容填充度需要**事件遥测与手动玩法测试共同证明**'

# 四层契约
REQUIRED_FOUR = [
    ('**主线必做**', '不完成无法推进'),
    ('**精通必做**', '不完成无法达到某种完成度/ mastery'),
    ('**引导必做**', '不完成玩家会迷路/不懂机制'),
    ('**可做**', '纯可选'),
]

REQUIRED_RULE = '🔑 影子删除在内部构建中**保留资产，但关闭入口、指引和奖励**，'
'比较崩溃、剧情分歧、任务依赖、收藏计数、统计、地图可达性、教程顺序、'
'经济曲线和回放'

# 反向追踪
TRACE_BEYOND = [
    '**事件字符串**', '**成就条件**', '**动态加载路径**', '**随机池**',
    '**对话条件**', '**脚本回调**',
]

TRACE_RULE = '🔴 **反向追踪不能只查引用关系** —— '
'还要查上述六类。Unity 引用工具会把**运行时字符串加载、反射、远程目录或'
'代码生成引用**判为无引用，故应设"**待人工复核**"而非自动删除'

# 🔴 极限
LIMIT_AXES = ['**capacity**', '**fan-out**', '**rate**', '**concurrency**']

LIMIT_FIELDS = [
    'entity', 'property', '**storage_type**', 'min_value', 'max_value',
    '**min_display**', '**max_display**', '**overflow_policy**',
    'clamp_policy', 'wrap_policy', 'underflow_policy', 'unit',
    'fractional_allowed', 'separator_locale', '**max_string_bytes**',
    '**max_grapheme**', 'max_display_columns', 'max_stacked_items',
    'max_unique_items', 'max_skills', 'max_buffs', 'max_active_quests',
    'max_save_slots', 'max_simultaneous_sources',
    '**max_input_events_per_frame**', '**max_operation_rate**',
    'fan_out_limit', 'combined_state_id', 'test_value_set',
    'expected_visual', 'expected_state', 'must_match',
]

LIMIT_COMBO = [
    '🔑 超长名字不仅测显示，还要测**比较、排序、存档键、聊天、日志、'
    '本地化复数、文本测量、字素截断、数据库字段、文件名、字幕、语音朗读和'
    '屏幕录制元数据**',
    '🔑 满背包要**叠加**满货币、满负重、满技能、满 buff、满任务、同时拾取',
    '🔑 同时触发要覆盖**多段伤害、击退、状态切换、相机事件、音效抢占、'
    'UI 通知、成就、教程和统计**',
    '🔑 极限操作速度要测**单帧多输入、交替键、长按与短按、断触、'
    '按键重映射中切换、热插拔、窗口失焦、帧率突变下的输入队列**',
]

# 溢出
OVERFLOW_POLICIES = [
    'clamp', 'wrap', 'saturate', 'reject', 'coerce_to_float',
    'store_as_string',
]

OVERFLOW_CHECK = [
    '累计伤害', '**乘法 buff**', '商店总价', '负重', '经验', '声望',
    '**概率千分比**', '计时器', '**随机种子**',
]

OVERFLOW_TESTS = [
    '**min-1**', 'min', 'max', '**max+1**', '零', '负数', '**极小正小数**',
]

NAME_TESTS = [
    '空', '**仅空白**', '**控制字符**', '**双向文本**', '**组合字符**',
    '**同显示不同码点**', '超长', '**超宽**', '同名冲突',
    '**大小写与规范化差异**',
]

OVERFLOW_RULE = '🔴 **溢出策略必须显式，不能让类型默认值替代设计**'

LIMIT_BUGS = [
    '**失败后状态半更新**', '**UI 显示正常但数据已回滚**',
    '**数据保存成功但通知显示失败**',
    '**上限提示后仍然保留非法中间值**', '**取消操作后下一次操作沿用脏输入**',
]

# 🔴 等待
WAIT_FIELDS = [
    'wait_id', 'start_trigger', 'stage', 'stage_duration_estimate',
    '**determinate**', '**known_total**', '**progress_source**',
    '**can_interact**', '**can_cancel**', 'can_pause', 'can_background',
    '**side_effect_if_cancelled**', 'auto_save_before',
    'recoverable_after_interrupt', 'skippable_media', 'skip_penalty',
    'filler_type', 'filler_id', 'filler_seen_state', '**honesty_mode**',
    'eta_policy', 'minimum_show_threshold_ms', 'finalization_required',
    '**rollback_or_commit**',
]

WAIT_RULE = [
    '🔑 进度条应明确"**知道总量**"与"**仅活动指示**"两种语义',
    '🔑 指示器应**持续运动** —— **停止会被理解为卡死**',
    '🔴 **`progress_source` 必须真实**（字节/资源计数/IO 回调/阶段估算）；'
    '**无法确定时不得伪装成确定进度**',
]

WAIT_HONEST = [
    '**进度 90% 停留很久**', '**末尾突然完成**', '**各阶段速度不一致**',
    '**上传完成后还有隐式校验**', '**着色器编译后还要热重载**',
]

WAIT_HONEST_RULE = '🔑 应记录每个阶段**真实耗时占比**，并**分别显示'
'"当前阶段进度"和"总进度"**；**禁止用缓动伪造未知阶段**'

WAIT_INTERACT = [
    '阻断等待', '半交互（可打开非竞争菜单）', '可后台化', '可暂停', '可取消',
]

WAIT_CANCEL = [
    '暂停', '回滚', '**保留已下载部分**', '提交清理', '**保留临时存档**',
    '要求确认',
]

WAIT_RULE2 = [
    '🔴 **不得把"不可取消"当默认** —— '
    '只在**确有副作用**时阻断，并说明后果',
    '🔑 可无副作用中断时提供**取消**；可能造成损失时提供**暂停**；'
    '取消可能丢进度时**请求确认**',
]

# 容错
UNDO_LEVELS = [
    ('**撤销**', '近期、可回放、低副作用：移动物品/改名/整理/染色/配置/地图标记'),
    ('**二次确认**', '不可逆、跨设备、消耗货币或破坏进度'),
    ('**延迟确认**', '高频且可撤销'),
    ('**危险操作**', '长按、组合键或重新选择目标'),
]

UNDO_RULE = [
    '🔑 **撤销必须恢复原始状态与位置，不能只恢复数值** —— '
    '例如撤销装备应**同时恢复角色朝向、镜头、动画和输入上下文**',
    '🔑 立即反馈按下，**真正提交在抬起**；移动超过滑动阈值可取消',
    '🔑 长按与短按必须记**时间窗和重复间隔**',
]

UNDO_DEGRADE = [
    '🔑 连点购买、快速切换、重复拾取、高频菜单导航应有'
    '**节流、去抖、冷却、批量确认和音效合并**',
    '🔴 **但不得静默吞掉最后一次有效意图**',
    '🔑 快速重复同一错误时：**首次内联反馈 → 连续第二次扩展解释 → '
    '超过阈值暂停输入并询问是否打开设置**',
]

UNDO_SEPARATE = '🔑 **缓冲是有意保留，去抖是防止噪声，撤销是失败恢复** —— '
'三者与"输入缓冲"和"committed 输入"必须分开'

# 🔴 一致性
CONSIST_FIELDS = [
    'operation_family', 'verb_key', 'verb_localization_key', 'icon_id',
    'input_action', 'state_transition', 'precondition', 'failure_state',
    'toast', 'sound_event', 'haptic_pattern', 'animation_event',
    'camera_event', 'ordering_rule', 'sorting_rule', 'navigation_order',
    'default_value', '**primary_button**', '**secondary_button**',
    '**exception_reason**', 'evidence_reference',
]

CONSIST_FAMILIES = [
    '打开', '关闭', '确认', '取消', '返回', '购买', '出售', '分解', '装备',
    '卸下', '拾取', '丢弃', '保存', '覆盖', '删除', '重命名', '移动', '复制',
    '锁定', '解锁', '跳过', '暂停', '继续', '重置', '恢复默认', '申请匹配',
    '取消匹配', '切换档位', '**切换输入设备**',
]

CONSIST_RULE = [
    '🔑 同类操作必须在**意图、反馈和结果三层同义**',
    '🔴 同一"确认"**不应在商店按 A、在对话按 B、在菜单按 Start**',
    '🔴 同一"返回"**不应有时关闭界面、有时退回标题、有时回滚未保存修改**',
    '🔑 声音、震感、动画和镜头若用于表达同一结果，'
    '**其触发时机与相对优先级必须一致**；'
    '但**不要求每个界面物理位置相同**',
]

CONSIST_EXCEPTION = [
    '快捷键返回', '触屏返回', '手柄返回', '**系统手势返回**',
]

CONSIST_RULE2 = '🔑 要记录上述例外分别如何处理；'
'**必须证明例外是有意且可发现**'

TERM_FIELDS = [
    'term_id', 'original_text', 'locale', 'context', 'approved',
    '**forbidden_synonym**', 'definition', 'first_seen', 'owner',
]

TERM_SCOPE = [
    '资产名', '技能名', 'UI 标签', '教程', '提示', '成就', '**代码日志**',
    '设置项', '客服文案', '**平台元数据**',
]

TERM_RULE = '🔑 上述十处应**共用同一术语源**。每个字符串要测'
'最小设备 · 最长翻译 · **字素截断** · 双向文本 · 大小写 · 强调和颜色；'
'**不能只靠翻译审校发现不一致**'

CONFLICTS = [
    '❌ **文件未被引用即可删**',
    '❌ **提交时间久就是废弃内容**',
    '❌ 相似资产一定重复',
    '❌ **精简就是删重复**',
    '❌ **可选内容删除不影响主线**',
    '❌ 只测单值上限不测组合',
    '❌ **整型默认 0**（把非法输入伪装成合法）',
    '❌ **名字截断到字节长度**（切断字素）',
    '❌ **满背包时阻止所有拾取**（可能丢失唯一掉落）',
    '❌ **上限封顶**导致重复操作无限刷校验音效',
    '❌ **只要不崩溃就通过**（忽略静默错误）',
    '❌ **进度条平滑欺骗**',
    '❌ **快速确认弹窗**让玩家机械确认',
    '❌ **全局关闭确认**把高风险交给肌肉记忆',
    '❌ **按下即提交**（移动端尤其不利）',
    '❌ **撤销只恢复数据不恢复表现**',
    '❌ **快速点击可跳过等待**（可能重复触发副作用）',
]

FIELDS = [
    ('item_id', '项编号'),
    ('domain', '域（necessity / variant / filler / required / trace / '
               'limits / overflow / wait / undo / consist）'),
    ('legacy_value', '**原版值**'),
    ('new_value', '新引擎值'),
    ('match', '**是否一致**'),
    ('tolerance', '**允许偏差**'),
    ('evidence', '证据'),
]


def _hdr(t, w=80):
    print('=' * w)
    print(t)
    print('=' * w)


def cmd_necessity(a):
    _hdr('🔴 内容必要性证明')
    print('类型: ' + ' · '.join(NECESSITY_TYPES))
    print('\n用途（可多选）: ' + ' · '.join(NECESSITY_PURPOSE))
    print('\n标记: ' + ' · '.join(NECESSITY_FLAGS))
    print('\n规则:')
    for r in NECESSITY_RULE:
        print(f'   {r}')
    return 0


def cmd_variant(a):
    _hdr('重复（**记变体轴**）')
    print('轴: ' + ' · '.join(VARIANT_AXES))
    print('\n规则:')
    for r in VARIANT_RULE:
        print(f'   {r}')
    print(f'\n   {VARIANT_RULE2}')
    return 0


def cmd_filler(a):
    _hdr('填充物（**静态 + 运行时**）')
    print('静态: ' + ' · '.join(FILLER_STATIC))
    print('\n运行时: ' + ' · '.join(FILLER_RUNTIME))
    print(f'\n   {FILLER_RULE}')
    return 0


def cmd_required(a):
    _hdr('必做 / 可做（**四层契约**）')
    for k, why in REQUIRED_FOUR:
        print(f'   {k:<14} {why}')
    print(f'\n   {REQUIRED_RULE}')
    print('\n反向追踪还要查: ' + ' · '.join(TRACE_BEYOND))
    print(f'\n   {TRACE_RULE}')
    return 0


def cmd_trace(a):
    _hdr('删除的反向追踪')
    print('除引用关系还要查: ' + ' · '.join(TRACE_BEYOND))
    print(f'\n   {TRACE_RULE}')
    print('\n影子删除比较项: 崩溃 · 剧情分歧 · 任务依赖 · 收藏计数 · 统计 · '
          '地图可达性 · 教程顺序 · 经济曲线 · 回放')
    return 0


def cmd_limits(a):
    _hdr('🔴 极限（**组合不是大数**）')
    print('四维: ' + ' · '.join(LIMIT_AXES))
    print('\n字段: ' + ' · '.join(LIMIT_FIELDS))
    print('\n组合测试:')
    for c in LIMIT_COMBO:
        print(f'   {c}')
    print('\n必须检测的 BUG: ' + ' · '.join(LIMIT_BUGS))
    return 0


def cmd_overflow(a):
    _hdr('🔴 溢出策略')
    print('策略: ' + ' · '.join(OVERFLOW_POLICIES))
    print('\n必检项: ' + ' · '.join(OVERFLOW_CHECK))
    print('\n数值测试: ' + ' · '.join(OVERFLOW_TESTS))
    print('\n名称测试: ' + ' · '.join(NAME_TESTS))
    print(f'\n   {OVERFLOW_RULE}')
    return 0


def cmd_wait(a):
    _hdr('🔴 等待（**诚实进度**）')
    print('字段: ' + ' · '.join(WAIT_FIELDS))
    print('\n规则:')
    for r in WAIT_RULE:
        print(f'   {r}')
    print('\n不诚实表现: ' + ' · '.join(WAIT_HONEST))
    print(f'\n   {WAIT_HONEST_RULE}')
    print('\n交互权: ' + ' · '.join(WAIT_INTERACT))
    print('\n取消后: ' + ' · '.join(WAIT_CANCEL))
    print('\n规则:')
    for r in WAIT_RULE2:
        print(f'   {r}')
    return 0


def cmd_undo(a):
    _hdr('误操作（**可逆性分级**）')
    for k, why in UNDO_LEVELS:
        print(f'   {k:<14} {why}')
    print('\n规则:')
    for r in UNDO_RULE:
        print(f'   {r}')
    print('\n提示退化:')
    for r in UNDO_DEGRADE:
        print(f'   {r}')
    print(f'\n   {UNDO_SEPARATE}')
    return 0


def cmd_consist(a):
    _hdr('🔴 跨系统一致性（**同义证明**）')
    print('字段: ' + ' · '.join(CONSIST_FIELDS))
    print('\n操作族: ' + ' · '.join(CONSIST_FAMILIES))
    print('\n规则:')
    for r in CONSIST_RULE:
        print(f'   {r}')
    print('\n例外（必须证明有意且可发现）: ' + ' · '.join(CONSIST_EXCEPTION))
    print(f'\n   {CONSIST_RULE2}')
    print('\n术语表字段: ' + ' · '.join(TERM_FIELDS))
    print('\n共用范围: ' + ' · '.join(TERM_SCOPE))
    print(f'\n   {TERM_RULE}')
    return 0


def cmd_init(a):
    os.makedirs(os.path.dirname(a.init) or '.', exist_ok=True)
    with open(a.init, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow([k for k, _ in FIELDS])
        w.writerow(['TODO'] * len(FIELDS))
    print(f'已生成内容/极限表: {a.init}')
    print('\n⚠️ 十域：necessity / variant / filler / required / trace / '
          'limits / overflow / wait / undo / consist')
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

    mismatch, no_legacy = [], []
    for i, r in enumerate(rows, 1):
        m = g(r, 'match').lower()
        if m not in ('yes', 'y', 'true', '是', '一致'):
            mismatch.append(i)
        if not g(r, 'legacy_value') or g(r, 'legacy_value') == 'TODO':
            no_legacy.append(i)

    print('=' * 76)
    print(f'内容/极限 · {len(rows)} 条')
    print('=' * 76)
    if mismatch:
        print(f'\n🚫 **不一致** {len(mismatch)} 条（行 {mismatch[:15]}）')
    if no_legacy:
        print(f'\n❌ {len(no_legacy)} 条缺**原版值**（行 {no_legacy[:15]}）')

    if not (mismatch or no_legacy):
        print('\n✅ 内容/极限：一致且原版值完整')

    print('\n🔑 **重复本身不是冗余，删除结果才是判定。**')
    print('   **极限是 capacity × fan-out × rate × concurrency 的组合。**')
    print('   **进度条停止会被理解为卡死；不得用缓动伪造未知阶段。**')
    return 1 if (a.gate_check and (mismatch or no_legacy)) else 0


def main():
    ap = argparse.ArgumentParser(description='内容冗余与系统极限')
    ap.add_argument('--necessity', action='store_true')
    ap.add_argument('--variant', action='store_true')
    ap.add_argument('--filler', action='store_true')
    ap.add_argument('--required', action='store_true')
    ap.add_argument('--trace', action='store_true')
    ap.add_argument('--limits', action='store_true')
    ap.add_argument('--overflow', action='store_true')
    ap.add_argument('--wait', action='store_true')
    ap.add_argument('--undo', action='store_true')
    ap.add_argument('--consist', action='store_true')
    ap.add_argument('--init')
    ap.add_argument('--check')
    ap.add_argument('--gate-check', action='store_true')
    a = ap.parse_args()
    fns = {'necessity': cmd_necessity, 'variant': cmd_variant,
           'filler': cmd_filler, 'required': cmd_required,
           'trace': cmd_trace, 'limits': cmd_limits,
           'overflow': cmd_overflow, 'wait': cmd_wait,
           'undo': cmd_undo, 'consist': cmd_consist}
    for k, fn in fns.items():
        if getattr(a, k):
            return fn(a)
    if a.init:
        return cmd_init(a)
    if a.check:
        return cmd_check(a)
    print('❌ 需要 --necessity / --variant / --filler / --required / --trace / '
          '--limits / --overflow / --wait / --undo / --consist / '
          '--init / --check 之一')
    return 2


if __name__ == '__main__':
    sys.exit(main())
