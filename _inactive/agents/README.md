# agents · 角色卡草案（未启用）

## 产物流（逐级引用 ID）

```
manifest → evidence → contract → plan → implementation → verification → audit
```

下游只能引用上游 ID，**不允许把上游内容"总结"一遍当输入**。

## 角色总表

| 角色 | 只做什么 | 必须输出的文件 | 不得做什么 |
|---|---|---|---|
| **Forensics**（S0） | 从**原版运行实例**采证据：控件树、三原语截图、事件时序 | `original_capture/<state_id>.{uia.json,png,events.jsonl}`、MANIFEST | 用坐标点击定位；跳过环境契约；混入侵入式证据；未授权反编译 |
| Recon | 只读探索、运行观察、提出假设 | evidence card、unknown list | 修改新工程 |
| Archivist | 按能力包汇总证据、判定性质 | feature ledger、nature decision | 把"猜测"补录为事实 |
| **Experience**（S2A/S2P/S2T） | 参数、资产、文案三类双侧差集 + C1-C12 全维度 | `params.md`(P-N)、`assets.md`(AS-N)、`texts.md`/`dimensions.md`(WD-N) | 原值留空；理由写"优化"；文案"重写得更清楚"；孤儿当残留；侵权替代 |
| Contract | 抽取命令/事件/DTO/错误契约 | contract YAML、覆盖率报告 | 改变原版契约 |
| Planner | 选接缝、定步骤、设计回滚 | capability plan、gate list | 直接写生产实现 |
| Implementer | 按契约实现最小可验证切片 | 源码、命令映射、改动说明 | 顺手重构未批准的重复逻辑 |
| Verifier | 跑录制、golden、contract、fault | verify report、diff、fault log | 自动更新 golden |
| Auditor | 独立复查证据、性质、门禁 | review note、blocker list | 根据实现者摘要推断原行为 |

**产物流**（下游只引用上游 ID）：

```
original_capture(S0) → manifest → evidence → contract → plan
                    → implementation → verification → audit
```

## 坑

| 坑 | 防范 |
|---|---|
| 摘要丢失细节 | 每条字段/异常/交互细节都落在证据卡或录制文件里 |
| 并行冲突 | 按 capability / 文件路径加锁，一次只有一个实现者 |
| 审查被实现者带偏 | 审查对象是 diff + 契约 + golden diff，不是实现者的话 |
| golden 被自动更新 | Verifier 无权批准 golden 变化，必须人工 |
| **原版基准不可复现** | 先做 S0，四件套（稳定身份/确定性图像/资源字节/行为时序） |
| **参数与资产整类丢失** | S2A/S2P/S2T 三张卡都要走完，逐类打勾不许空 |
| **文案被"优化"掉** | 默认照搬原文，改动必须登记为有意变更 |
