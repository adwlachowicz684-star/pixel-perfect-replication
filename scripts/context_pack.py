#!/usr/bin/env python3
"""上下文打包与 AI 参与门禁（C 类）—— LLM 只能"提出假设"，
   **不能拥有"判定完成"的权限**。

**本 Skill 的既定立场**（前几轮已确立）：
> 拒绝"AI 自报已修复"、"AI 判定可收工"。
> AI 输出默认标 `confidence=low`，必须经机器与人工验证。

**⚠️ 七道强制门**（缺一不可）:
1. 原版侧 —— AI 不得访问未经许可的私有代码/原始素材；取证在隔离环境产生
2. 任务侧 —— 只描述**可观察行为**和证据约束，**不许让 AI 猜原版实现**
3. 生成侧 —— 必须区分「反编译器事实 / 运行观测 / 推断 / 未知」，
   逐函数给引用地址或文件行；**禁止生成未引用的 API、数值、资源路径、表项、魔法常数**
4. 编译侧 —— 必须过目标平台/架构/优化级别/依赖锁版本的 CI；
   **失败日志不得被 AI 重新解释为"接近正确"**
5. 测试侧 —— 确定性/差分/属性/回放/视觉/音频/帧时间交叉验证
6. 复核侧 —— 状态机、渲染、物理、音频、RNG、存档、计时、网络、错误处理**人复核**
7. 收工侧 —— 只有门禁全绿且未覆盖项为零或经批准才可收工；**AI 的"完成"声明无效**

用法:
  context_pack.py --pack <目录> --out context-manifest.json [--budget 200000]
  context_pack.py --scan <目录>             # 敏感信息扫描（密钥/令牌）
  context_pack.py --gates                   # 打印七道门
  context_pack.py --review-check <变更集.json> --gate   # AI 变更复核门禁

退出码: 0 通过 / 1 阻断 / 2 用法错误
"""
import argparse
import hashlib
import json
import os
import re
import sys

# 敏感信息模式（打包前必须扫）
SECRET_PATTERNS = [
    ("私钥", re.compile(r"-----BEGIN (RSA |EC |OPENSSH |PGP )?PRIVATE KEY-----")),
    ("AWS", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("GitHub token", re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}")),
    ("Slack token", re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}")),
    ("OpenAI key", re.compile(r"sk-[A-Za-z0-9]{20,}")),
    ("通用 API key", re.compile(r"(?i)(api[_-]?key|secret|password|passwd|token)"
                                r"\s*[:=]\s*['\"][^'\"]{8,}['\"]")),
    ("JWT", re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.")),
    ("数据库连接串", re.compile(r"(?i)(postgres|mysql|mongodb|redis)://[^\s'\"]*:[^\s'\"]*@")),
    ("硬编码 IP+端口", re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d{2,5}\b")),
]

TEXT_EXT = {".py", ".rs", ".ts", ".tsx", ".js", ".jsx", ".cs", ".cpp", ".c", ".h",
            ".hpp", ".go", ".java", ".kt", ".md", ".json", ".yaml", ".yml", ".toml",
            ".xaml", ".xml", ".sql", ".sh", ".mjs"}
SKIP_DIRS = {".git", "node_modules", "target", "build", "dist", "__pycache__",
             ".venv", "venv", "bin", "obj", ".idea", ".vs", "vendor"}

GATES = [
    ("1 原版侧", "AI 不得访问未经许可的私有代码/原始素材；"
                 "所有原版 IO、内存、轨迹须在**隔离取证环境**产生，记录构建身份与工具版本"),
    ("2 任务侧", "只描述**可观察行为**与证据约束，**不许让 AI 猜原版实现**；"
                 "提示须含反编译证据、调用轨迹、资源/状态、边界、禁止项、验收测试"),
    ("3 生成侧", "必须区分「反编译器事实 / 运行观测 / 推断 / 未知」，逐函数给引用地址或文件行；"
                 "**禁止生成未引用的 API、数值、资源路径、表项、魔法常数**"),
    ("4 编译侧", "必须过目标平台/架构/优化级别/依赖锁版本的 CI；"
                 "**失败日志不得被 AI 重新解释为「接近正确」**"),
    ("5 测试侧", "确定性 / 差分 / 属性 / 回放 / 视觉 / 音频 / **帧时间分布**交叉验证"),
    ("6 复核侧", "状态机、渲染、物理、音频、RNG、存档、计时、网络、错误处理**由人复核**；"
                 "高风险差异即使测试通过也要二次审查"),
    ("7 收工侧", "只有门禁全绿且未覆盖项为零或经批准才可收工；**AI 的「完成」声明无效**"),
]


def cmd_gates(a):
    print("=" * 74)
    print("AI 参与时的七道强制门（**缺一不可**）")
    print("=" * 74)
    for k, why in GATES:
        print(f"\n【{k}】")
        print(f"   {why}")
    print("\n⚠️ 核心立场：**LLM 只拥有提出假设的权限，不拥有判定完成的权限。**")
    print("   LLM4Decompile / GhidraMCP / Binary Ninja MCP / ida-pro-mcp —— **均不得有收工资格**。")
    print("\n⚠️ 反编译器 MCP 只开放**最小只读工具面**：")
    print("   允许：列函数、读反汇编/伪代码、查交叉引用、读注释、导出工件")
    print("   禁止：改名、打补丁、保存项目、执行脚本、远程下载、调用外部 LLM 插件")
    return 0


def iter_files(root):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            p = os.path.join(dirpath, fn)
            if os.path.splitext(fn)[1].lower() in TEXT_EXT:
                yield p


def cmd_scan(a):
    root = a.scan
    if not os.path.isdir(root):
        print(f"❌ 目录不存在: {root}")
        return 2
    hits = []
    for p in iter_files(root):
        try:
            text = open(p, encoding="utf-8", errors="replace").read()
        except Exception:
            continue
        for name, pat in SECRET_PATTERNS:
            m = pat.search(text)
            if m:
                hits.append({"file": p, "kind": name,
                             "snippet": m.group(0)[:40]})
    print("=" * 70)
    print(f"敏感信息扫描 · {root}")
    print("=" * 70)
    if hits:
        print(f"\n🚨 发现 {len(hits)} 处疑似敏感信息:")
        for h in hits[:15]:
            print(f"   [{h['kind']}] {h['file']}")
        print(f"\n❌ 打包前必须处理 —— **禁止把密钥投喂给模型**")
    else:
        print("\n✅ 未发现疑似敏感信息")
    print("\n⚠️ 扫描基于正则，**不能保证找出全部敏感信息** —— 仍需人工复核。")
    return 1 if (a.gate and hits) else 0


def cmd_pack(a):
    root = a.pack
    if not os.path.isdir(root):
        print(f"❌ 目录不存在: {root}")
        return 2
    files, total_bytes = [], 0
    for p in sorted(iter_files(root)):
        try:
            sz = os.path.getsize(p)
        except Exception:
            continue
        total_bytes += sz
        files.append({"path": os.path.relpath(p, root), "bytes": sz})

    # 敏感扫描（打包必带）
    secrets = 0
    for p in iter_files(root):
        try:
            text = open(p, encoding="utf-8", errors="replace").read()
        except Exception:
            continue
        for _, pat in SECRET_PATTERNS:
            if pat.search(text):
                secrets += 1
                break

    est_tokens = total_bytes // 4  # 粗估，仅作预算参考
    git_rev = ""
    try:
        import subprocess
        r = subprocess.run(["git", "-C", root, "rev-parse", "HEAD"],
                           capture_output=True, text=True, timeout=10)
        if r.returncode == 0:
            git_rev = r.stdout.strip()
    except Exception:
        pass

    blob = "\n".join(f["path"] for f in files).encode("utf-8")
    manifest = {
        "root": os.path.abspath(root),
        "file_count": len(files),
        "total_bytes": total_bytes,
        "estimated_tokens": est_tokens,
        "token_budget": a.budget,
        "over_budget": bool(a.budget and est_tokens > a.budget),
        "git_revision": git_rev,
        "suspect_secret_files": secrets,
        "files": files,
        "manifest_sha256": hashlib.sha256(blob).hexdigest(),
        "prompt_template_version": a.template_version,
        "warnings": [],
    }
    if manifest["over_budget"]:
        manifest["warnings"].append(
            f"超出令牌预算 {est_tokens} > {a.budget} —— "
            "**上下文过长会导致模型遗漏细节**；应先结构化检索，再向小窗口提交单函数证据")
    if secrets:
        manifest["warnings"].append(
            f"{secrets} 个文件疑似含敏感信息 —— **打包前必须处理**")
    if not git_rev:
        manifest["warnings"].append("未取得 git revision —— 上下文不可精确复现")

    if a.out:
        os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)
        print(f"→ {a.out}")

    print("=" * 70)
    print("上下文打包清单")
    print("=" * 70)
    print(f"   文件数 {len(files)} · 字节 {total_bytes} · 估算令牌 {est_tokens}")
    print(f"   git revision: {git_rev[:12] or '(未取得)'}")
    print(f"   疑似含密钥文件: {secrets}")
    print(f"   manifest sha256: {manifest['manifest_sha256'][:16]}…")
    for w in manifest["warnings"]:
        print(f"   ⚠️ {w}")

    print("\n⚠️ 任何被打包目录都必须生成 `context-manifest.json`：")
    print("   含文件数、排除规则、令牌估计、**git 状态**、密钥扫描结果、提示模板版本。")
    print("\n⚠️ 若搜索索引、反编译器与运行样本给出**三种不同解释**，")
    print("   应把**冲突本身**保存为待验证据，而不是让模型在对话中「最终裁定」。")
    return 1 if (a.gate and manifest["warnings"]) else 0


def cmd_review(a):
    if not os.path.exists(a.review_check):
        print(f"❌ 文件不存在: {a.review_check}")
        return 2
    data = json.load(open(a.review_check, encoding="utf-8"))
    items = data if isinstance(data, list) else data.get("changes", [])
    if not items:
        print("❌ 变更集为空")
        return 2

    REQUIRED = [
        ("proposer", "提议者身份（**须标明是 AI 还是人**）"),
        ("context_manifest_hash", "上下文包哈希"),
        ("target_file", "目标文件"),
        ("evidence_refs", "证据引用（**反编译器事实 / 运行观测 / 推断 / 未知** 四类区分）"),
        ("build_log", "编译日志"),
        ("test_log", "测试日志"),
        ("decompiler_evidence", "反编译器证据"),
        ("human_signature", "**人工签名**"),
    ]
    print("=" * 72)
    print(f"AI 变更复核 · {len(items)} 条")
    print("=" * 72)
    bad = []
    for i, it in enumerate(items, 1):
        miss = []
        for k, _ in REQUIRED:
            val = it.get(k, "")
            if isinstance(val, str):
                if not val.strip():
                    miss.append(k)
            elif not val:
                miss.append(k)
        if miss:
            bad.append((i, miss))

    if bad:
        print(f"\n❌ {len(bad)} 条缺必填项:")
        for i, miss in bad[:8]:
            print(f"   #{i}: 缺 {', '.join(miss)}")
    else:
        print("\n✅ 变更集字段齐全")

    ai_items = [i for i, it in enumerate(items, 1)
                if "ai" in str(it.get("proposer", "")).lower()
                or it.get("proposer") in ("llm", "agent", "copilot")]
    unsigned = [i for i, it in enumerate(items, 1)
                if not (it.get("human_signature") or "").strip()]
    if ai_items:
        print(f"\n⚠️ {len(ai_items)} 条由 AI 提议（#{ai_items[:10]}）")
        print("   → 必须经机器与人工验证，**AI 的「完成」声明无效**")
    if unsigned:
        print(f"\n❌ {len(unsigned)} 条缺**人工签名**（#{unsigned[:10]}）")

    print("\n⚠️ AI 迁移代理（aider / OpenHands / SWE-agent / plandex）**只能生成候选 diff**：")
    print("   它们倾向生成看起来完整、可编译、可解释的代码，")
    print("   **而不是证明与原版一致** —— 容易把同名 API、流行库用法、训练先验当原版行为。")
    return 1 if (a.gate and (bad or unsigned)) else 0


def main():
    ap = argparse.ArgumentParser(description="上下文打包与 AI 参与门禁")
    ap.add_argument("--pack")
    ap.add_argument("--out", default="context-manifest.json")
    ap.add_argument("--budget", type=int, help="令牌预算")
    ap.add_argument("--template-version", dest="template_version", default="")
    ap.add_argument("--scan")
    ap.add_argument("--gates", action="store_true")
    ap.add_argument("--review-check", dest="review_check")
    ap.add_argument("--gate", action="store_true")
    a = ap.parse_args()

    if a.gates:
        return cmd_gates(a)
    if a.scan:
        return cmd_scan(a)
    if a.pack:
        return cmd_pack(a)
    if a.review_check:
        return cmd_review(a)
    print("❌ 需要 --pack / --scan / --gates / --review-check 之一")
    return 2


if __name__ == "__main__":
    sys.exit(main())
