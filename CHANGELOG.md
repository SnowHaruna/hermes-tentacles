# Changelog

## V6.3 (2026-06-10)

### 新增
- `--prompt-file`：从文件读取任务
- `--name`：日志标识
- `--findings-dir`：触手发现暂存区
- 放宽 `--output` 至 `~/.hermes/{cron/output,reports,tentacle_output}` 三个合法目录
- dotenv 改为 try/except + 手动解析 fallback

---

## V6.2 (2026-06-10)

### 安全加固
- 10 项漏洞审计 → 9 项已修复（C2/C3/H1/H2/M1/M2/M3/L1/L2）
- 仅 C1（GitHub PAT 明文）需手动轮换
- 工具参数泄露到 stderr：已过滤敏感字段
- chmod 降级、dotenv 无保护导入均已修复

---

## V6.1 (2026-06-09)

### 新增
- 主循环重构 + 原地等待机制
- 触手卡住时等待求助，不退出
- 小雪看门狗：3 分钟心跳检测 + 15 分钟超时汇报

---

## V5 (2026-06-09)

### 新增
- 首批实战任务：南北极融化（7'40"）、1+1=2（69"）、竞品搜索（4'52"）
- RAG 记忆快照注入（--inject-memory）

---

## V1-V4 (2026-06-09)

- V1：灵魂注入 —— 首个能推理的 Hermes 分身
- V2：治好癫痫 —— 回调参数修复，不再 crash
- V3：开眼看世界 —— stderr 实时进度
- V4：武装触手 —— 自主操作文件 + 工具调用批处理

> 详见 [docs/evolution.md](docs/evolution.md)
