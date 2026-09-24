#!/usr/bin/env python3
"""CD-KEY / 序列号输入控件 linter（第五十轮 B + 第五十一轮补强）。

⚠️ **边界**：本脚本**不做密钥生成 · 不做在线验证 · 不绕过任何检查 ·
不读受保护内存**。**只检查输入控件是否明确处理了字符消歧与反馈语义。**

> 🔑 **CD-KEY 输入是字符消歧问题，不是任意字符串。**
> 🔑 **官方帮助给出的近似替换说明"正版用户也会在输入层失败"。**

用法:
  cdkey_input_linter.py --rule   # 🔑 消歧映射与处理清单
  cdkey_input_linter.py --init ledger/cdkey_input.csv
  cdkey_input_linter.py --check ledger/cdkey_input.csv --gate

退出码: 0 通过 / 1 有未处理项 / 2 用法错误
"""
import argparse
import csv
import os
import sys

MAP_RULE = '🔑 **CD-KEY 输入是字符消歧问题，不是任意字符串。**'
MAPS = [
    ('数字 `0`', '`Q` / `D` / `O`'),
    ('数字 `1`', '`I` / `L`'),
    ('字母 `O`', '`Q` / `D`'),
    ('字母 `B`', '`8`'),
    ('字母 `G`', '`6`'),
]
MAP_NOTE = '🔑 **这说明正版用户也会在输入层失败** —— '
'输入控件必须显式声明如何处理每一组形似字符'
NO_RULE = '🔑 **若原版不区分 `0/O` 或 `1/I`，复刻不应擅自加入严格校验**；'
'🔴 **若原版区分，也不能为"现代友好"自动纠错**'
FIELDS = '分组长度 · **连字符是否自动插入** · 大小写是否等价 · 全角/半角 · '
'**形似字符字形** · 光标跳格 · **粘贴后清洗规则** · '
'逐段校验还是提交后校验 · **输错多少位才开始反馈** · 失败是否清空前一段 · '
'是否显示最后一格遮罩 · 错误音 · 抖动 · 颜色 · 重试图标 · 键盘布局 · '
'**IME** · **读屏文案** · 帮助链接 · 客服电话 · 重试冷却'

ROWS = [
    ('group_length', '分组长度（如 5-5-5）'),
    ('hyphen_auto_insert', '**连字符是否自动插入**'),
    ('case_equivalent', '大小写是否等价'),
    ('full_half_width', '全角/半角处理'),
    ('glyph_disambiguation', '**形似字符字形是否可辨**'),
    ('cursor_jump', '光标跳格行为'),
    ('paste_sanitize', '**粘贴后清洗规则**'),
    ('validate_stage', '逐段校验还是提交后校验'),
    ('error_feedback_threshold', '**输错多少位才开始反馈**'),
    ('clear_on_failure', '失败是否清空前一段'),
    ('last_char_mask', '是否显示最后一格遮罩'),
    ('error_sound', '错误音'),
    ('error_motion', '抖动'),
    ('error_color', '颜色（🔴 不得只依赖颜色）'),
    ('retry_affordance', '重试图标'),
    ('keyboard_layout', '键盘布局'),
    ('ime_behavior', '**IME 行为**'),
    ('screen_reader_text', '**读屏文案**'),
    ('help_link', '帮助链接'),
    ('support_contact', '客服电话'),
    ('retry_cooldown', '重试冷却'),
]
REQUIRED = ['glyph_disambiguation', 'full_half_width', 'paste_sanitize',
            'error_feedback_threshold', 'ime_behavior', 'screen_reader_text']


def _hdr(t, w=80):
    print('=' * w)
    print(t)
    print('=' * w)


def cmd_rule(a):
    _hdr('🔑 CD-KEY 输入（**字符消歧问题**）')
    print(f'   {MAP_RULE}')
    print('\n官方给出的近似替换:')
    for k, v in MAPS:
        print(f'   · {k} → {v}')
    print(f'\n   {MAP_NOTE}')
    print(f'\n   {NO_RULE}')
    print(f'\n完整处理清单: {FIELDS}')
    print('\n⚠️ **边界**：不做密钥生成 · 不做在线验证 · 不绕过检查')
    return 0


def cmd_init(a):
    os.makedirs(os.path.dirname(a.init) or '.', exist_ok=True)
    with open(a.init, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow(['field', 'legacy_value', 'new_value', 'match', 'note'])
        for k, d in ROWS:
            w.writerow([k, 'TODO', 'TODO', '', d])
    print(f'已生成 CD-KEY 输入表: {a.init}（{len(ROWS)} 项）')
    print('\n⚠️ 必填项（缺失即硬阻断）：' + ' · '.join(REQUIRED))
    print('\n⚠️ **只记录可见表现与输入语义，不记录任何校验算法或密钥规则**')
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

    present = {g(r, 'field'): r for r in rows}
    missing = [k for k, _ in ROWS if k not in present]
    empty_req = [k for k in REQUIRED
                 if k in present and (not g(present[k], 'legacy_value')
                                      or g(present[k], 'legacy_value') == 'TODO')]
    mismatch = [g(r, 'field') for r in rows
                if g(r, 'match').lower() not in
                ('yes', 'y', 'true', '是', '一致', '')]

    print('=' * 76)
    print(f'CD-KEY 输入层 · {len(rows)} 条 / 需覆盖 {len(ROWS)} 项')
    print('=' * 76)
    if missing:
        print(f'\n🚫 **未覆盖项** {len(missing)}: {missing}')
    if empty_req:
        print(f'\n🚫 {len(empty_req)} 个**必填项缺原版值**: {empty_req}')
    if mismatch:
        print(f'\n🚫 **不一致** {len(mismatch)} 项: {mismatch[:15]}')
    if not (missing or empty_req or mismatch):
        print('\n✅ CD-KEY 输入层：项齐全、必填有值、语义一致')

    print('\n🔑 **若原版不区分 0/O，不得擅自加严格校验；'
          '若原版区分，不得自动纠错。**')
    print('   ⚠️ **边界：不做密钥生成 · 不做在线验证 · 不绕过检查。**')
    return 1 if (a.gate_check and (missing or empty_req or mismatch)) else 0


def main():
    ap = argparse.ArgumentParser(description='CD-KEY 输入控件 linter')
    ap.add_argument('--rule', action='store_true')
    ap.add_argument('--init')
    ap.add_argument('--check')
    ap.add_argument('--gate-check', action='store_true')
    a = ap.parse_args()
    if a.rule:
        return cmd_rule(a)
    if a.init:
        return cmd_init(a)
    if a.check:
        return cmd_check(a)
    print('❌ 需要 --rule / --init / --check 之一')
    return 2


if __name__ == '__main__':
    sys.exit(main())
