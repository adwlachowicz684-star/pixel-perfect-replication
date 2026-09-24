#!/usr/bin/env python3
"""工具封装公共逻辑 —— 所有 wrapper 共用。

**四条公共纪律**（每个 wrapper 都必须遵守）:

1. **先校验身份**：用 `tool_run.py` 的校验逻辑，防「同名不同工具」
2. **缺失时如实降级**：标 `confidence=low` 并进 unknown，**不得静默跳过**
3. **输出归一化**：统一写 `{tool, available, confidence, evidence[], warnings[]}`
4. **证据带来源**：每条证据记 `engine`、`version`、`command`，便于复核

⚠️ 唯一可以"不做事"的情况：工具确实不可用。
   那时必须**明确写 unavailable 原因**，而不是输出一个空的成功结果。
"""
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tool_run import check_identity, load_registry  # noqa: E402


def get_spec(tool_id):
    reg = load_registry()
    return (reg.get("tools") or {}).get(tool_id) or {}


def require(tool_id):
    """校验工具可用。不可用则打印原因并返回 None（调用方必须如实降级）。"""
    spec = get_spec(tool_id)
    ok, reason, detail = check_identity(tool_id, spec)
    if not ok:
        print(f"❌ {tool_id} 不可用 —— {reason}")
        print(f"   {detail}")
        inst = spec.get("install") or {}
        if inst:
            print("   安装方式:")
            for k, v in inst.items():
                print(f"     {k}: {v}")
        print(f"\n⚠️ 缺失时行为: {spec.get('degrade')}")
        print("   **不得静默跳过** —— 请在证据中标 confidence=low 并进 unknown。")
        return None
    return spec


def run(cmd, timeout=120):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, (r.stdout or ""), (r.stderr or "")
    except FileNotFoundError:
        return 127, "", f"命令不存在: {cmd[0] if cmd else '?'}"
    except subprocess.TimeoutExpired:
        return -1, "", f"超时 {timeout}s"
    except Exception as e:
        return -2, "", str(e)


def emit(tool_id, available, out_path, evidence=None, warnings=None,
         confidence="high", extra=None):
    """统一输出格式。"""
    spec = get_spec(tool_id)
    rec = {
        "tool": tool_id,
        "name": spec.get("name"),
        "repo": spec.get("repo"),
        "license": spec.get("license"),
        "available": available,
        "confidence": confidence,
        "evidence": evidence or [],
        "warnings": warnings or [],
    }
    if extra:
        rec.update(extra)
    if not available:
        rec["confidence"] = "low"
        rec["warnings"].append(
            "工具不可用 —— 本条证据**未采集**，必须进 unknown，不得当已解决")

    if out_path:
        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(rec, f, ensure_ascii=False, indent=2)
        print(f"\n→ {out_path}")
    return rec


def print_summary(rec):
    print("=" * 64)
    print(f"{rec['name']} · {'可用' if rec['available'] else '不可用'}"
          f" · confidence={rec['confidence']}")
    print("=" * 64)
    for e in rec.get("evidence", [])[:12]:
        print(f"   · {e}")
    for w in rec.get("warnings", [])[:8]:
        print(f"   ⚠️ {w}")
