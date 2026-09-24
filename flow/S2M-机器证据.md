# S2M · 机器证据（AST 查询四层流水线）

> **为什么需要这一阶段**：手写正则只能做低置信线索，不能充当结构体、命令、DTO 的事实来源。
> 实证：`[^}]*` 提前截断 → `FpxConfig` 39 字段只抓到 33；
> `grep -oP "pub \w+"` → 25 vs 实际 39（带 `Option<...>` 抓不全）。
>
> **原则**：**工具只产生证据，不批准变更。** 命中一律进台账与证据卡，不绕过硬门禁。

---

## 一、四层流水线

| 层 | 工具 | 输入 | 输出 | 证据等级 |
|---|---|---|---|---|
| **L0 原文** | 逐行阅读 | 源文件 | 逐行证据 | 原文证据（最高） |
| **L1 通用解析** | tree-sitter | 全量源码 | CST + 解析状态 | 机器结构证据 |
| **L2 精确查询** | **ast-grep** | YAML 规则 | 节点命中 JSON | 高，须复核歧义 |
| **L3 跨语言结构** | comby | 模板 / 规则 | 匹配与 diff | 中（结构线索） |
| **L4 目标端重写** | jscodeshift / recast | transform | AST→AST diff | 中高，需 fixture |
| L5 语义审计（可选） | Semgrep / CodeQL | 规则 / 数据库 | 数据流线索 | 视规则与版本 |

**现有脚本的定位**：`comment_extract.py`、`config_field_diff.py`、`cross-end-check.mjs`
**保留为胶水层与门禁**，但搜索后端必须可替换成 L2/L3 的结果。

---

## 二、L1 · tree-sitter：先问"机器能不能读懂"

```bash
python3 scripts/tree_sitter_parse.py --src <原版src> --lang cs
```

**价值**：解析失败的文件本身就是信号——旧实现不是每种语言都干净可解析，
说明"实现层"证据可能失效，应升级为反证和人工阅读，**而不是删项**。

| 结果 | 处置 |
|---|---|
| 解析成功 | 该文件的 AST 查询可作高置信证据 |
| 解析失败（目标端） | 进 `defer/file parsing failed`，**不许自动关闭 unknown** |
| 解析失败（源端） | AST 证据等级降级，改用原文阅读 + comby |

解析状态写进台账的「机器可解析」字段。

---

## 三、L2 · ast-grep：精确查询（首选）

```bash
# 规则文件在 rules/sg/*.yml
python3 scripts/ast_query.py --rules rules/sg --src <src> --out findings.json
```

**为什么它在正则之上**：基于 tree-sitter 的 AST 匹配，不受注释、字符串字面量、
换行、泛型嵌套影响。支持 YAML 规则、lint、搜索与重写。

**示例规则**（抓 Rust 公共字段）：

```yaml
id: struct_field
language: rust
evidence_question: 这个结构体有哪些 pub 字段？
expected_card_type: 数据层字段
rule:
  pattern: 'struct $NAME { $$$FIELDS }'
  constraints:
    FIELDS:
      regex: 'pub\s+\w+\s*:'
counter_example: |
  局部变量 pub: 只在 struct 内计；同名不同对象需人工区分
```

**每条规则必须包含五要素**：

| 要素 | 作用 |
|---|---|
| `evidence_question` | 这条规则在回答什么问题（防止为了命中而命中） |
| `language` | 语言（以官方支持清单为准，**不要假设**） |
| `pattern/selector` | 匹配模式 |
| `expected_card_type` | 命中该进哪类卡片 |
| `counter_example` | 反例：什么看起来像但实质不是 |

**⚠️ 语言支持以官方实时清单为准**。目标栈（Rust / TS / TSX / YAML）通常已支持；
**C# 是否稳定内置支持必须查官方清单**，不能凭检索快照承诺。
不支持时走 L3（comby）或 L0（人工）。

**规则首次运行必做**：统计命中、漏报样例、解析失败文件。
**漏报样例必须回灌规则**，而不是通过降低精度提高命中率。

---

## 四、L3 · comby：跨语言兜底

```bash
python3 scripts/comby_runner.py --match-only --template 'pub struct :[name] { :[body] }' --src <src>
```

**定位**：**结构线索，不是事实来源。** comby 用平衡括号/字符串/注释理解结构，
支持约所有语言，但**不解析语义、不解析类型、不能跨文件追踪数据流**。

命中后必须转成：目标端契约测试，或人工复核。

**批量改写纪律**：
- 禁止裸 `-i` 全仓替换
- 必须先 `-match-only` → `-diff` → 受影响文件清单 → 按目录分批 → 可回滚 commit

---

## 五、L4 · jscodeshift / recast：目标端保守重写

用于 TS/TSX 目标端的机械改写：旧 API 调用迁移、props 重命名、
事件签名统一、样式 token 映射、测试夹具迁移。

**每个 transform 必须**：
- 单目标（一个 transform 只做一件事）
- 可 dry-run、可回放
- 附带**至少一个正向 fixture + 一个不应匹配的反例 fixture**
- 只处理白名单目录（先跑 `ledger.py` 拿全量清单），**禁止 `**` 式全仓改写**

```bash
python3 scripts/codemod_runner.py --transform transforms/x.ts --dir plugins/x --dry-run
```

---

## 六、反证：每条规则都要回答"什么看起来像但不是"

| 目标 | 必须排除 |
|---|---|
| 命令定义 | 注释里的示例、字符串字面量、测试替身、日志文本、内部重实现 |
| DTO 字段 | 局部变量、URL 参数、同名不同对象 |
| 生命周期函数 | 反射注册、动态加载 |

脚本输出三态：`matched / near_miss / excluded`
**`near_miss`（结构匹配但上下文不符）要人工每周抽样** —— 这是规则质量的体温计。

若反证样例只能靠"再加一层正则"修补 → 说明该升级为 CST 节点约束，或改用专门重构引擎。

---

## 七、产物

| 文件 | 内容 |
|---|---|
| `ledger/findings.json` | 统一命中格式：`file/range/node_kind/matched_text/rule_id/language/confidence/evidence_card_id` |
| `ledger/files.csv` | 新增「机器可解析」「机器已查询」字段 |
| `rules/sg/*.yml` | ast-grep 规则（可审查） |

## 八、门禁

- [ ] 全量文件跑过 L1 解析，解析失败文件已登记（不自动关闭 unknown）
- [ ] 命令 / 结构体字段 / DTO 三类查询已用 L2 或 L3 覆盖
- [ ] 每条规则有 `evidence_question` 与 `counter_example`
- [ ] 规则漏报样例已回灌
- [ ] 所有命中都关联到证据卡 ID，**没有"查到了但没入账"的命中**

## 九、不通过怎么办

| 情况 | 处置 |
|---|---|
| 语言不被 ast-grep 支持 | 走 comby 或人工，**不许因为难查就跳过** |
| 解析失败 | 登记 + 降级证据等级 + 人工阅读，**不许删项** |
| 规则命中过多像噪音 | 加 `counter_example` 约束，不是加阈值放行 |
| 工具没装 | 降级到正则并**明确标注 confidence=low**（脚本会如实报告） |
