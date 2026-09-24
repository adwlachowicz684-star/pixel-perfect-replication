# Recon · 探索与运行观察（草案）

**输入**：manifest.md
**输出**：`ledger/evidence/*.yaml`、`ledger/unknown.md`
**禁止**：修改新工程任何文件

## 只做三件事
1. 枚举可观察入口（窗口/菜单/快捷键/命令/端点/文件/配置/日志/错误提示）
2. 真跑原版，录制可见行为（runtime-verified 级证据）
3. 提出假设并把无法验证的记进 unknown

## 纪律
- 不从 README 推断；未读取即标 unknown
- 不写"应该是这样"；猜的一律算 assumption 并进 unknown
- 每条证据必须带文件行号或录制文件路径
