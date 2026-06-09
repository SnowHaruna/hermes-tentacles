审计完成。输出 JSON 结果：

```json
{
  "status": "done",
  "task": "审查 ~/hermes-tentacles/ 项目的安全性",
  "result": "安全审计完成。发现 10 个漏洞: 🔴CRITICAL×2 (GitHub PAT 明文在 .git/config + --output 路径遍历), 🟠HIGH×3 (/tmp共享风险 + memory投毒 + SIGTERM非异步安全), 🟡MEDIUM×3 (prompt注入 + TOCTOU竞态 + max-iterations无限), 🔵LOW×2。正面: 零外部依赖, yaml.safe_load(), 无硬编码token, git历史无泄露, 心跳容错, 不可自杀设计。",
  "time_seconds": 180.5,
  "runs": 1,
  "output_file": "/home/holywarliu/hermes-tentacles/docs/security-audit-2026-06-10.md",
  "report_summary": {
    "total_vulnerabilities": 10,
    "critical": [
      "C1: GitHub PAT 明文嵌入 .git/config remote URL — 需立即轮换 token + 改用 credential helper",
      "C2: --output 参数无路径校验，可任意文件写入 — 需 resolve + 白名单校验"
    ],
    "high": [
      "C3: /tmp/tentacle_help 在 world-writable /tmp 下 — 建议移到 ~/.hermes/tentacle_help/ + chmod 700",
      "H1: Memory 写回投毒 — 触手搜索恶意内容可污染持久化记忆池",
      "H2: SIGTERM handler 用 sys.exit(0) 非异步安全 — 改用 os._exit(0)"
    ],
    "medium": [
      "M1: Prompt 注入 (task/context 参数直接拼入)",
      "M2: TOCTOU 竞态 (求助文件 exists→open 时间窗口)",
      "M3: --max-iterations 无上限校验"
    ],
    "low": [
      "L1: sys.path 注入风险",
      "L2: 信号处理器与主线程文件写入竞态"
    ],
    "positive_practices": [
      "零外部 PyPI 依赖",
      "yaml.safe_load() 而非 yaml.load()",
      "API key 只从环境变量读取",
      "Git 历史中无泄露的 token",
      "心跳异常静默容错",
      "不可自杀设计原则",
      "退出码清晰定义"
    ],
    "top_fix_priority": "P0: 立即轮换 GitHub PAT + 修复 --output 路径遍历"
  }
}
```