# 外部工具封装（可调用层）

> **为什么有这一层**：前几轮收集了上百个工具，
> 但**只写在文档里等于没有**。这一层让它们变成**可调用、可检测、可降级**的能力。

```
scripts/tool_run.py          调度器：登记 / 身份校验 / 调用 / 能力矩阵
scripts/tools/registry.yaml  登记表：31 个工具（repo、许可、安装、身份特征、产出、降级策略）
scripts/tools/_common.py     公共纪律（四条）
scripts/tools/*.py           具体封装（8 个）
```

---

## 一、⚠️ 身份校验：本层存在的理由

> **`which sg` 命中的是 Unix 的 `sg`（set group ID）命令** ——
> 它可执行、但在 PATH 里，**没有 `scan` 子命令**。
> 只查"命令存在"会得到**永远 0 命中却显示成功**的假工具。

所以每个工具必须过**两道**：

1. **版本特征**：`--version` 输出必须含指定字符串，**且退出码为 0**
2. **子命令**：指定子命令必须真的存在

### 实测（`--env`）

```
ast_grep    版本校验失败   rc=1：Usage: sg group [[-c] command]
```

**这就是那个陷阱** —— `sg` 存在，但它是 set-group-ID 命令，不是 ast-grep。

### 二次踩坑（也修了）

**只匹配字符串会误判**：`java -cp daikon.jar daikon.Daikon --version`
在 jar 缺失时报错信息里**含 "daikon.Daikon"** → 只匹配字符串会误判为可用。
所以加了**退出码必须为 0** 这一条。

**`python3 -c "print('apted')"` 恒成功** —— 模块探测必须真的 `import`：

```yaml
exe: python3
version_args: [-c, "import apted; print('APTED_OK')"]
version_contains: [APTED_OK]
```

---

## 二、四条公共纪律（`_common.py`）

| # | 纪律 |
|---|---|
| 1 | **先校验身份** —— 防「同名不同工具」 |
| 2 | **缺失时如实降级** —— 标 `confidence=low` 进 unknown，**不得静默跳过** |
| 3 | **输出归一化** —— `{tool, available, confidence, evidence[], warnings[]}` |
| 4 | **证据带来源** —— 记 `engine` / `version` / `command`，便于复核 |

**唯一可以"不做事"的情况：工具确实不可用。**
那时必须**明确写 unavailable 原因**，而不是输出一个空的成功结果。

---

## 三、已封装的 8 个

| 封装 | 工具 | 产出 | 关键纪律 |
|---|---|---|---|
| `harfbuzz_shape.py` | HarfBuzz | `glyphs.json` | **L1 字形簇合同**；`--compare` 与金标准比对 |
| `odiff_image.py` | odiff | `image_diff.json` | **抗锯齿是候选分类，不是默认豁免** |
| `toxiproxy_fault.py` | Toxiproxy | `network_faults.csv` | **只管传输层**；`--catalog` 有三列表 |
| `kaitai_probe.py` | Kaitai Struct | `format_probe.json` | 验收要 **round-trip 字节相等** |
| `vmaf_quality.py` | VMAF | `vmaf.json` | 只回答"多像"，**不能定位缺失按钮** |
| `gumtree_diff.py` | GumTree | `tree_edit_ops.json` | 借鉴三阶段算法；AGPL-3.0 仅 `third_party` 时提示 |
| `resvg_render.py` | resvg | 基准位图 | 须记版本/DPI/背景/CSS/shaping 后端 |
| `ocr_text.py` | Tesseract | `ocr_texts.csv` | **只作候选**，必须人工确认（实测可用） |
| `duckdb_evidence.py` | DuckDB（可降级） | 证据查询 | 纯 Python 兜底，**不依赖 duckdb 也能跑** |

---

## 四、用法

```bash
# 看全部登记工具
python3 scripts/tool_run.py --list

# 能力矩阵（**是否真可用**，不是"装了没"）
python3 scripts/tool_run.py --env

# 校验单个 / 全部，生成能力报告
python3 scripts/tool_run.py --check ast_grep
python3 scripts/tool_run.py --check-all --json ledger/capability.json --gate

# 调用封装
python3 scripts/tool_run.py --run harfbuzz
python3 scripts/tools/harfbuzz_shape.py --font f.ttf --text "café" --out ledger/glyphs.json
python3 scripts/tools/ocr_text.py --image shot.png --out ledger/ocr_texts.csv
python3 scripts/tools/duckdb_evidence.py --work work/ --cross
```

---

## 五、缺失时的行为（登记表 `degrade` 字段）

| 值 | 行为 |
|---|---|
| `required` | 证据标 `confidence=low`，**进 unknown，硬门禁阻断** |
| `optional` | 标 `skipped` 并提示，**不许静默** |

**任何情况下都不得静默跳过** —— 静默跳过会让"没采集"看起来像"没问题"。

---

## 六、许可注意（登记表已标）

| 工具 | 许可 | 注意 |
|---|---|---|
| **GumTree** | **AGPL-3.0** | 仅 `third_party` 对外分发时提示 |
| **resvg** | **MPL-2.0** | **非 MIT** |
| **Kaitai Struct** | GPLv3（compiler） | 仅 `third_party` 对外分发时提示 |
| Semgrep | LGPL-2.1 | — |
| 其余多数 | MIT / Apache-2.0 / BSD | 较宽松 |

> **允许用更优设计替代实现，不允许用侵权替代资源。**

---

## 七、新增工具的步骤

1. 在 `registry.yaml` 加条目：**repo / license / exe / identity / install / degrade**
2. `identity` 必须配 `version_args` + `version_contains` + （如有）`subcommand`
3. 跑 `tool_run.py --check <id>` 验证**不会误判**
4. 需要的话写封装脚本，继承 `_common.py` 的四条纪律
5. 跑 `--check-all` 确认没破坏别的工具
