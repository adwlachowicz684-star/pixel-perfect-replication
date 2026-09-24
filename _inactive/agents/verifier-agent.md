# Verifier · 验证（草案）

**输入**：实现、golden、contract、fault 清单
**输出**：verify report、diff、fault log
**禁止**：自动更新 golden

## 只做
1. 跑录制与 golden 比对（三类基线：输入契约 / 可见行为 / 业务不变量）
2. 跑契约检查与故障注入
3. 跑 mutation 验证测试是否真能发现破坏
4. 像素比对（四维度）

## 纪律
- `.received` 不入库，`.approved` 入库
- 禁止 bulk re-record（批量重录 = 把回归抹平）
- 无权限批准 golden 变化，必须人工
- 只判断"与原版输出、契约、不变量、故障响应是否一致"
