#!/usr/bin/env python3
"""加载连续性 + 非文本本地化 + 存档/成就/相机空间（第二十五轮 C / D / E / F / G）。

**🔑 C 类核心**：
> 🔑 **"无缝"不是"不黑屏"，而是八条连续契约。**
> 🔴 **`undefined` 就是高优先级 bug** ——
> 它允许不同版本、平台、帧率**随机漂移**。

**🔑 D 类核心**：
> 🔑 **非文本本地化是"资源版本与规则系统"，不是字符串表。**
> 🔑 字符串表只能保证文字，不能保证"**口型闭合但台词多 200ms**"。

用法:
  game_load_locale.py --cont    # 🔴 加载**八域连续契约**
  game_load_locale.py --locale  # 🔴 非文本本地化 **locale_version**
  game_load_locale.py --lip     # **口型**不是表情也不是简单开合
  game_load_locale.py --audio   # 音频本地化**六件事**
  game_load_locale.py --culture # **文化适配**逐项明确
  game_load_locale.py --bidi    # **BiDi 不是镜像**
  game_load_locale.py --font    # **字体回退**必须可复现
  game_load_locale.py --slot    # 多存档**槽位契约**
  game_load_locale.py --meta    # 存档**元数据**不能现算
  game_load_locale.py --ach     # 成就**四层**
  game_load_locale.py --retro   # **追溯补发**必须版本化
  game_load_locale.py --camera  # 🔴 相机**四个面**
  game_load_locale.py --init ledger/load_locale.csv
  game_load_locale.py --check ledger/load_locale.csv --gate

退出码: 0 通过 / 1 缺项 / 2 用法错误
"""
import argparse
import csv
import os
import sys

# 🔴 加载八域
CONT_DOMAINS = [
    'world_clock', 'physics', 'animation', 'audio', 'input', 'ai',
    'network', 'persistent_entities',
]

CONT_STATES = ['continue', 'freeze', 'decouple', 'reset', '**undefined**']

CONT_RULE = [
    '🔑 **无缝加载的承诺不是"不黑屏"，而是八条连续契约**',
    '🔑 每域显式声明 `during_load: ' + ' | '.join(CONT_STATES).replace('**', '') + '`',
    '🔴 **`undefined` 就是高优先级 bug** —— '
    '它允许**不同版本 · 平台 · 帧率随机漂移**',
]

CONT_QUESTIONS = [
    '加载期间**世界是否继续推进**',
    '切换前后"**同一物体**"是否同一身份（同一扇门？）',
    '**切换时的输入缓冲**（加载中按键是否缓存）',
    '**切换失败/超时**的呈现',
    '**快速连续切换**（反复进出）的行为',
]

# 🔴 非文本本地化
LOCALE_FIELDS = [
    '**locale_version**', '源语言时长', '**译配时长**', '字幕行',
    '**口型标记**', '角色表情', '停顿', '配音资产', '**字体**', '字号',
    '图标', '颜色', '**日期/数字/货币规则**', '**阅读方向**',
    '音频响度', '混音版本',
]

LOCALE_RULE = [
    '🔑 **真正漏掉的是"表现资源—规则文本—配音—口型—时间—版式"的一致性**',
    '🔑 字符串表**只能保证文字**，不能保证'
    '"**口型闭合但台词多 200 ms**"',
]

# 口型
LIP_FIELDS = [
    '**唇形集**', '**音素/视位映射**', '**帧精度**', '**闭嘴间隙**',
    '停顿粒度', '与字幕行的对齐', '方言变体', '跨语言表演差异',
]

LIP_RULE = [
    '🔑 **口型不是表情，也不是简单的开合**',
    '🔑 某些语言由配音演员重录 → **口型必须重绑**；'
    '**只替换音频却复用原口型会造成持续"不同步"**',
    '🔑 若原版明确采用**音节或元音近似**，也必须保留，'
    '**不能重做成逐音素**',
]

# 音频六件事
AUDIO_SIX = [
    '**配音语言切换是否立即生效**',
    '运行切换是否重新加载',
    '**缺失语言是否退回、是否显式标注**',
    '**字幕与配音能否独立**',
    '**不同配音时长是否改变时间轴**',
    '沉默 · 笑声 · 呼吸 · 拟声**是否有本地化资产**',
]

AUDIO_RULE = '🔑 若中文配音时长更短 → **过场 · 任务窗口 · '
'连击判定 · 字幕停留可能改变**；必须测"**最长和最短配音版本**"'

# 文化适配
CULTURE_ITEMS = [
    '手势', '宗教符号', '国旗', '颜色', '动物', '食物', '身体裸露',
    '死亡表现', '血腥程度', '政治边界', '地图名称', '货币符号',
    '数字分组', '日期顺序', '**12/24 小时制**', '**星期起始**',
    '姓名顺序', '尊称', '量词', '度量单位',
]

CULTURE_FIELDS = [
    '**culture_rule_id**',
    '**default_action**: preserve|replace|redact|locale_fallback',
    'approval_status', '**affects_gameplay**',
]

# BiDi
BIDI_RULE = [
    '🔑 **UI 版式必须双方向化，而不是镜像**',
    '🔑 `layout_binding` 要区分**逻辑属性与视觉属性**：'
    '`start/end` 与 `left/right`',
    '🔑 列表顺序 · 图标顺序 · 时间线方向 · 技能栏 · 雷达 · '
    '**镜头回中** · 进度条 · **角色转身是否翻转**，需逐项声明',
    '🔴 阿拉伯语/希伯来语**不是"把文本 RTL"** —— '
    '而是 **BiDi 算法 · 数字方向 · 标点位置 · 连字 · 字体回退 · '
    '控件镜像**共同决定',
]

# 字体回退
FONT_FIELDS = [
    'script', '**required_glyph_set**', '**fallback_chain**',
    'line_break_rules', 'justification', 'emoji_policy',
    '**missing_glyph_policy**',
]

FONT_COVER = [
    'CJK', '阿拉伯', '希伯来', '泰语', '梵文系', '日语', '韩语',
    '**合成字素**', '**零宽字符**', '**双向控制符**',
]

FONT_RULE = [
    '🔑 **字体回退必须可复现**',
    '🔑 从 XLIFF 或字符串表生成"**最小覆盖文本**"，'
    '渲染后做**像素差和溢出框检测**',
    '🔴 **缺字回退若偷偷换成不同字体高度 → '
    '会改版式和点击目标**',
]

# 存档槽位
SLOT_KINDS = [
    'autosave', 'checkpoint', 'manual', 'quicksave', 'backup', 'import',
    'recovery',
]

SLOT_FIELDS = [
    'save_kind', 'scope', 'owner_character', 'mode', 'difficulty',
    'ngplus_cycle', 'platform_profile', 'write_state', 'integrity',
    '**lock_reason**', 'screenshot', 'playtime_ms', 'game_version',
    'content_version', '**progress_percentage_method**', 'last_modified',
    'sort_key', 'rename_history', 'delete_grace', 'cross_save_policy',
]

SLOT_RULE = [
    '🔑 **多存档的核心是"槽位契约"而非文件数量**',
    '🔑 **自动存档可能是游戏事实**，**手动存档可能是玩家意图**，'
    '**快速存档可能允许覆盖** —— **混用会导致死亡前读档、'
    '挑战绕过或覆盖习惯变化**',
]

# 元数据
META_RULE = [
    '🔑 **存档元数据不能由 UI 现算** —— '
    '"**进度百分比**"必须有**确定性公式**',
    '🔑 **截图必须与写入完成绑定**',
    '🔑 **删除不应立即破坏正在读取的线程**',
    '🔑 **覆盖必须写临时文件后原子替换**',
    '🔑 **复制槽需生成新身份但保留因果链**',
    '🔑 导入可能受**内容版本或平台签名**限制',
]

META_TESTS = [
    '保存中崩溃', '**删除使用中的存档**', '槽位满', '跨模式覆盖',
    '**复制后继续写入**',
]

# 成就四层
ACH_FOUR = ['**事实**', '**资格**', '**提交**', '**交付**']

ACH_FIELDS = [
    'detection_event', 'predicate', 'evaluation_tick', 'submission_clock',
    '**idempotency_key**', 'delivery_channel', 'persistence_scope',
    'cross_save', 'cross_cycle', 'cross_character', 'post_delete',
    'grant_on_replay', '**retroactive_version**', 'revoke_policy',
    'reward_id', 'reward_delivery_phase', 'notification_event',
    'challenge_resume_scope',
]

ACH_RULE = [
    '🔑 **成就要拆成四层：' + ' → '.join(ACH_FOUR) + '**',
    '🔑 **满足条件瞬间解锁**与**提交成功时解锁**不同；后者需测'
    '**网络/磁盘失败重试**',
]

# 追溯
RETRO_FIELDS = [
    '**retroactive_until_rule_id**', 'min_game_version', 'max_game_version',
    'predicate_snapshot', 'test_save_set',
]

RETRO_QUESTIONS = [
    '新版本**降低目标**后，已满足旧条件的玩家是否补发',
    '目标**提高**后，已经通知的玩家是否**撤回**',
    '**删除存档后累计是否归零**',
    '**跨周目是否共享**',
    '**离线缓存是否允许重复提交**',
]

RETRO_RULE = '🔴 **这些规则不能由平台 SDK 默认值代替**'

# 挑战
CHALLENGE_FIELDS = [
    'challenge_id', 'stable_progress', 'best_attempt',
    'attempt_in_progress',
    '**resume_after**: save_load|crash|version_upgrade|session_end',
    'loss_events', 'verification_event', 'anti_cheat_boundary',
]

CHALLENGE_RULE = '🔑 **挑战进度应像存档一样有续接点** —— '
'只记"完成/未完成"会破坏可续接挑战；只记最高值又可能漏掉'
'"**单局内连续**"的语义'

# 🔴 相机四平面
CAMERA_FIELDS = [
    'render_geometry', 'near_clip', 'collision_probe',
    '**collision_response**: push_in|step_over|stop|hide_obstacle|'
    'fade_obstacle|preserve_distance',
    'camera_blocking_volume', '**player_visible_point**', '**hit_origin**',
    '**hit_destination**', 'hipfire_weapon_geo', 'ads_weapon_geo',
    'first_person_arms', 'shadow_caster', 'decal_receiver',
    'minimap_visibility', 'audio_occlusion', 'ik_goal', 'look_at_target',
]

CAMERA_RULE = [
    '🔑 **相机空间契约要绑定四个面**',
    '🔑 关键：玩家**看见的位置** · **命中检测位置** · **动画 IK 位置** · '
    '**声音遮挡位置** 可能是**四个不同代理**',
]

CAMERA_SEE = '🔑 **"看见即可交互"不是天然真理，必须显式承诺** —— '
'若游戏承诺"**可视即可打**"，**相机穿墙 · 肩枪模型覆盖准星 · '
'近裁剪吞掉近距离判定**都是 BUG；'
'若原版明确采用"**从头顶或肩膀发出命中射线**"，也必须记录'
'**命中源与相机源分离**，**不能重做成严格从镜头中心**'

CAMERA_TPS = '🔑 第三人称同样要测：**肩后瞄准 · 掩体探头 · 载具座椅 · '
'死亡镜头 · 过场归还**'

CONFLICTS = [
    '❌ 把"无缝"理解成"不黑屏"',
    '❌ **连续性标 undefined**',
    '❌ **运行时切语言只换文本**',
    '❌ **一个字体覆盖所有语言**',
    '❌ **RTL 全局镜像**（实为 BiDi + 连字 + 数字方向 + 控件镜像）',
    '❌ 翻译后不改配音时长',
    '❌ 文化替换只当"发行市场建议"而非资源规则',
    '❌ **缺失语言静默退回英语却不记录**',
    '❌ 只替换音频却复用原口型',
    '❌ 把音节近似口型"重做"成逐音素',
    '❌ 缺字回退偷偷换不同字体高度',
    '❌ 多存档槽位语义混用',
    '❌ 进度百分比由 UI 现算',
    '❌ 删除正在读取的存档',
    '❌ 成就追溯补发用平台 SDK 默认值',
    '❌ 挑战只记"完成/未完成"',
    '❌ 把"从头顶发命中射线"重做成严格镜头中心',
]

FIELDS = [
    ('item_id', '项编号'),
    ('domain', '域（cont / locale / lip / audio / culture / bidi / font / '
               'slot / meta / ach / retro / camera）'),
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


def cmd_cont(a):
    _hdr('🔴 加载连续性（**八域**）')
    print('域: ' + ' · '.join(CONT_DOMAINS))
    print('\n每域声明 during_load: ' + ' · '.join(CONT_STATES))
    print('\n规则:')
    for r in CONT_RULE[:3]:
        print(f'   {r}')
    print('\n还要回答:')
    for q in CONT_QUESTIONS:
        print(f'   · {q}')
    return 0


def cmd_locale(a):
    _hdr('🔴 非文本本地化（**locale_version**）')
    print('字段: ' + ' · '.join(LOCALE_FIELDS))
    print('\n规则:')
    for r in LOCALE_RULE:
        print(f'   {r}')
    return 0


def cmd_lip(a):
    _hdr('口型（**不是表情也不是简单开合**）')
    print('字段: ' + ' · '.join(LIP_FIELDS))
    print('\n规则:')
    for r in LIP_RULE:
        print(f'   {r}')
    return 0


def cmd_audio(a):
    _hdr('音频本地化（**六件事**）')
    for i, s in enumerate(AUDIO_SIX, 1):
        print(f'   {i}. {s}')
    print(f'\n   {AUDIO_RULE}')
    return 0


def cmd_culture(a):
    _hdr('文化适配（**逐项明确**）')
    print('需检查: ' + ' · '.join(CULTURE_ITEMS))
    print('\n字段: ' + ' · '.join(CULTURE_FIELDS))
    return 0


def cmd_bidi(a):
    _hdr('BiDi（**不是镜像**）')
    for r in BIDI_RULE:
        print(f'   {r}')
    return 0


def cmd_font(a):
    _hdr('字体回退（**必须可复现**）')
    print('字段: ' + ' · '.join(FONT_FIELDS))
    print('\n最小覆盖文本: ' + ' · '.join(FONT_COVER))
    print('\n规则:')
    for r in FONT_RULE:
        print(f'   {r}')
    return 0


def cmd_slot(a):
    _hdr('多存档（**槽位契约**）')
    print('槽位种类: ' + ' · '.join(SLOT_KINDS))
    print('\n字段: ' + ' · '.join(SLOT_FIELDS))
    print('\n规则:')
    for r in SLOT_RULE:
        print(f'   {r}')
    return 0


def cmd_meta(a):
    _hdr('存档元数据（**不能现算**）')
    for r in META_RULE:
        print(f'   {r}')
    print('\n校验器需模拟: ' + ' · '.join(META_TESTS))
    return 0


def cmd_ach(a):
    _hdr('成就（**四层**）')
    print(' → '.join(ACH_FOUR))
    print('\n字段: ' + ' · '.join(ACH_FIELDS))
    print('\n规则:')
    for r in ACH_RULE:
        print(f'   {r}')
    return 0


def cmd_retro(a):
    _hdr('追溯补发（**必须版本化**）')
    print('字段: ' + ' · '.join(RETRO_FIELDS))
    print('\n必须回答:')
    for q in RETRO_QUESTIONS:
        print(f'   · {q}')
    print(f'\n   {RETRO_RULE}')
    print('\n挑战续接: ' + ' · '.join(CHALLENGE_FIELDS))
    print(f'\n   {CHALLENGE_RULE}')
    return 0


def cmd_camera(a):
    _hdr('🔴 相机空间契约（**四个面**）')
    print('字段: ' + ' · '.join(CAMERA_FIELDS))
    print('\n规则:')
    for r in CAMERA_RULE:
        print(f'   {r}')
    print(f'\n   {CAMERA_SEE}')
    print(f'\n   {CAMERA_TPS}')
    return 0


def cmd_init(a):
    os.makedirs(os.path.dirname(a.init) or '.', exist_ok=True)
    with open(a.init, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow([k for k, _ in FIELDS])
        w.writerow(['TODO'] * len(FIELDS))
    print(f'已生成加载/本地化表: {a.init}')
    print('\n⚠️ 十二域：cont / locale / lip / audio / culture / bidi / '
          'font / slot / meta / ach / retro / camera')
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
    print(f'加载/本地化 · {len(rows)} 条')
    print('=' * 76)
    if mismatch:
        print(f'\n🚫 **不一致** {len(mismatch)} 条（行 {mismatch[:15]}）')
    if no_legacy:
        print(f'\n❌ {len(no_legacy)} 条缺**原版值**（行 {no_legacy[:15]}）')
    if no_grade:
        print(f'\n🚫 {len(no_grade)} 条**证据等级缺失或 ≥7 级**'
              f'（行 {no_grade[:15]}）')

    if not (mismatch or no_legacy or no_grade):
        print('\n✅ 加载/本地化：一致、原版值完整、证据等级达标')

    print('\n🔑 **"无缝"是八条连续契约；undefined 就是 bug。**')
    print('   **非文本本地化是资源版本，不是字符串表。**')
    print('   **看见的位置/命中位置/IK位置/声音遮挡位置可能是四个不同代理。**')
    return 1 if (a.gate_check and (mismatch or no_legacy or no_grade)) else 0


def main():
    ap = argparse.ArgumentParser(description='加载连续性与非文本本地化')
    ap.add_argument('--cont', action='store_true')
    ap.add_argument('--locale', action='store_true')
    ap.add_argument('--lip', action='store_true')
    ap.add_argument('--audio', action='store_true')
    ap.add_argument('--culture', action='store_true')
    ap.add_argument('--bidi', action='store_true')
    ap.add_argument('--font', action='store_true')
    ap.add_argument('--slot', action='store_true')
    ap.add_argument('--meta', action='store_true')
    ap.add_argument('--ach', action='store_true')
    ap.add_argument('--retro', action='store_true')
    ap.add_argument('--camera', action='store_true')
    ap.add_argument('--init')
    ap.add_argument('--check')
    ap.add_argument('--gate-check', action='store_true')
    a = ap.parse_args()
    fns = {'cont': cmd_cont, 'locale': cmd_locale, 'lip': cmd_lip,
           'audio': cmd_audio, 'culture': cmd_culture, 'bidi': cmd_bidi,
           'font': cmd_font, 'slot': cmd_slot, 'meta': cmd_meta,
           'ach': cmd_ach, 'retro': cmd_retro, 'camera': cmd_camera}
    for k, fn in fns.items():
        if getattr(a, k):
            return fn(a)
    if a.init:
        return cmd_init(a)
    if a.check:
        return cmd_check(a)
    print('❌ 需要 --cont / --locale / --lip / --audio / --culture / '
          '--bidi / --font / --slot / --meta / --ach / --retro / '
          '--camera / --init / --check 之一')
    return 2


if __name__ == '__main__':
    sys.exit(main())
