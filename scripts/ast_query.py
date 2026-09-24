#!/usr/bin/env python3
"""AST 精确查询（S2M L2）—— 优先 ast-grep，缺失时**如实降级**并标注 low confidence。

⚠️ 诚实降级原则：ast-grep 没装时**不假装成功、也不静默跳过**（静默跳过 = 假绿灯），
而是退出码 2 并明确打印"结果降级为正则，confidence=low"。

⚠️ 工具身份陷阱（实证）：`shutil.which("sg")` 会命中 Unix 的 `sg`（set group ID）
命令 —— 它可执行，但没有 `scan` 子命令，会让查询永远 0 命中却显示"成功"。
本脚本用 `--version` 特征 + `scan --help` 双重校验工具身份。

用法:
  ast_query.py --rule rules/sg/struct_field.yml --src src-tauri/src
  ast_query.py --rules rules/sg --src src --out ledger/findings.json
  ast_query.py --rules rules/sg --src src --fallback-regex   # 允许正则降级（标注 low）
  ast_query.py --check                                        # 只查工具是否可用

输出 findings.json 条目:
  file / range / node_kind / matched_text / rule_id / language
  / confidence(high|low) / engine(ast-grep|regex-fallback) / evidence_card_id
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys

def _verify(bin_path):
    """验证命令真的是 ast-grep，而不是同名的其它程序。

    ⚠️ 实证陷阱：`shutil.which("sg")` 会命中 Unix 的 `sg`（set group ID）命令，
    它也有可执行权限，但完全没有 `scan` 子命令。
    **只检查"命令存在"会得到一个永远 0 命中却显示成功的假工具。**
    """
    try:
        v = subprocess.run([bin_path, "--version"], capture_output=True,
                           text=True, timeout=15)
        blob = (v.stdout + v.stderr).lower()
        if "ast-grep" not in blob and "ast_grep" not in blob:
            return False, f"{bin_path} 不是 ast-grep（--version 中无 ast-grep 特征）"
        # 再确认有 scan 子命令
        h = subprocess.run([bin_path, "scan", "--help"], capture_output=True,
                           text=True, timeout=15)
        if h.returncode != 0 and "scan" not in (h.stdout + h.stderr).lower():
            return False, f"{bin_path} 无 scan 子命令"
        return True, (v.stdout or v.stderr).strip().splitlines()[0]
    except Exception as e:
        return False, f"{bin_path} 执行失败: {e}"


def find_ast_grep():
    for name in ("ast-grep", "sg"):
        p = shutil.which(name)
        if not p:
            continue
        ok, why = _verify(p)
        if ok:
            return p, why
    return None, "未找到可用的 ast-grep（或找到的 `sg` 是 Unix 的 set-group 命令）"


SG_BIN, SG_VER = find_ast_grep()


def tool_status():
    if SG_BIN:
        return True, f"ast-grep 可用: {SG_BIN}  {SG_VER}"
    return False, ("未安装 ast-grep —— 无法做 AST 精确查询。\n"
                   f"  原因: {SG_VER}\n"
                   "  安装: npm i -g @ast-grep/cli  (或 cargo install ast-grep)\n"
                   "  注意: `sg` 是 Unix 的 set-group 命令，本脚本已做身份校验，不会误认。\n"
                   "  未安装期间结果若用正则替代，必须标注 confidence=low，"
                   "不许假装是 AST 级证据。")


def run_ast_grep(rule_path, src, lang=None):
    cmd = [SG_BIN, "scan", "--json", "--rule", rule_path]
    if lang:
        cmd += ["--lang", lang]
    cmd.append(src)
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if p.returncode not in (0, 1):     # 1 = 有命中（lint 语义），非错误
        return None, p.stderr.strip()[:400]
    out = []
    for line in p.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out, (p.stderr.strip()[:200] or None)


def normalize(item, rule_id, lang):
    rng = item.get("range", {}) or {}
    rng = rng.get("byteOffset", rng) if isinstance(rng, dict) else rng
    return {
        "file": item.get("file", "?"),
        "range": rng,
        "node_kind": item.get("kind") or item.get("ruleId") or "?",
        "matched_text": (item.get("text") or item.get("lines") or "")[:400],
        "rule_id": rule_id,
        "language": lang or item.get("language") or "?",
        "confidence": "high",
        "engine": "ast-grep",
        "evidence_card_id": None,
    }


def rule_meta(rule_path):
    """从规则文件里读 id / language（含 YAML 注释里的 evidence_question）。"""
    with open(rule_path, encoding="utf-8", errors="replace") as f:
        text = f.read()
    rid = os.path.splitext(os.path.basename(rule_path))[0]
    m = re.search(r"^id\s*:\s*(\S+)", text, re.M)
    if m:
        rid = m.group(1).strip()
    lang = None
    m = re.search(r"^language\s*:\s*(\S+)", text, re.M)
    if m:
        lang = m.group(1).strip()
    return rid, lang


def _pattern_to_regex(pat):
    """把 ast-grep pattern 转成宽松正则：$VAR → [\\w]+，$$$VAR → .*。

    例: 'pub struct $NAME { $$$FIELDS }'  →  'pub\\s+struct\\s+[\\w]+\\s*\\{.*'
    这只是降级线索，不假装是 AST 匹配。
    """
    p = pat.strip().strip("'\"")
    # $ 变量先占位，避免被转义
    p = re.sub(r"\$\$\$\w+", "\x00", p)      # $$$FIELDS -> .*
    p = re.sub(r"\$\w+", "\x01", p)          # $NAME -> [\w]+
    p = re.escape(p)
    p = p.replace("\x00", r"[\s\S]*?").replace("\x01", r"[\w]+")
    p = p.replace(r"\ ", r"\s+")             # 转义后的空格 -> 允许多个空白
    return p


def regex_fallback(rule_path, src, rid, lang):
    """降级：把 pattern 转宽松正则做粗匹配，明确标 low。"""
    with open(rule_path, encoding="utf-8", errors="replace") as f:
        text = f.read()
    pats = re.findall(r"pattern\s*:\s*\|?\s*\n?\s*['\"]?([^'\"]+)['\"]?", text)
    pats = [p.strip() for p in pats if p.strip()]
    if not pats:
        return []
    res = []
    for p in pats:
        try:
            res.append(re.compile(_pattern_to_regex(p)))
        except re.error:
            continue
    if not res:
        return []

    out = []
    ext = {"rust": ".rs", "typescript": ".ts", "tsx": ".tsx", "csharp": ".cs"}.get(lang or "", "")
    for root, dirs, fns in os.walk(src):
        dirs[:] = [d for d in dirs if d not in
                   (".git", "node_modules", "target", "dist", "bin", "obj")]
        for fn in fns:
            if ext and not fn.endswith(ext):
                continue
            path = os.path.join(root, fn)
            try:
                with open(path, encoding="utf-8", errors="replace") as f:
                    body = f.read()
            except Exception:
                continue
            for rx in res:
                for m in rx.finditer(body):
                    line = body.count("\n", 0, m.start()) + 1
                    out.append({
                        "file": path, "range": f"L{line}", "node_kind": "regex-hit",
                        "matched_text": m.group(0)[:300].replace("\n", " "),
                        "rule_id": rid, "language": lang or "?",
                        "confidence": "low", "engine": "regex-fallback",
                        "evidence_card_id": None,
                    })
    return out


def main():
    ap = argparse.ArgumentParser(description="AST 精确查询（ast-grep）")
    ap.add_argument("--rule", help="单个规则文件")
    ap.add_argument("--rules", help="规则目录")
    ap.add_argument("--src", default=".")
    ap.add_argument("--out", default="ledger/findings.json")
    ap.add_argument("--fallback-regex", action="store_true",
                    help="ast-grep 不可用时允许正则降级（仍标 low）")
    ap.add_argument("--check", action="store_true", help="只查工具可用性")
    a = ap.parse_args()

    ok, msg = tool_status()
    if a.check:
        print(("✅ " if ok else "❌ ") + msg)
        return 0 if ok else 2
    print(msg)

    rules = []
    if a.rule:
        rules.append(a.rule)
    if a.rules and os.path.isdir(a.rules):
        rules += [os.path.join(a.rules, f) for f in sorted(os.listdir(a.rules))
                  if f.endswith((".yml", ".yaml"))]
    if not rules:
        print("❌ 未指定规则（--rule 或 --rules）")
        return 2

    if not ok and not a.fallback_regex:
        print("\n❌ ast-grep 不可用，且未加 --fallback-regex。")
        print("   机器查询不可用时必须如实报告，不许静默跳过（静默跳过 = 假绿灯）。")
        return 2

    all_hits, degraded = [], False
    for rp in rules:
        rid, lang = rule_meta(rp)
        if ok:
            hits, err = run_ast_grep(rp, a.src, lang)
            if hits is None:
                print(f"⚠️  {rid}: ast-grep 执行失败 → {err}")
                hits = []
            all_hits += [normalize(h, rid, lang) for h in hits]
            print(f"   {rid}: {len(hits)} 命中 (ast-grep, high)")
        else:
            degraded = True
            hits = regex_fallback(rp, a.src, rid, lang)
            all_hits += hits
            print(f"   {rid}: {len(hits)} 命中 (regex-fallback, ⚠️ low)")

    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(all_hits, f, ensure_ascii=False, indent=2)

    hi = sum(1 for h in all_hits if h["confidence"] == "high")
    lo = sum(1 for h in all_hits if h["confidence"] == "low")
    print("=" * 60)
    print(f"总命中 {len(all_hits)}  high={hi}  low={lo}  → {a.out}")
    if degraded:
        print("\n⚠️ 本轮为正则降级结果，confidence=low —— 必须人工复核后入账，"
              "不许当作 AST 级证据。")
    print("⚠️ 命中必须关联 evidence_card_id 才算出账；"
          "没有'查到了但没入账'的命中。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
