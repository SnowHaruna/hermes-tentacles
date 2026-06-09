---
name: auto-task-triage
description: Hermes' Tentacles 🦑 — 自动判断任务轻重，重活自动fork分身到后台，独立推理完成后记忆回传。军哥设计的"时间线分支"模型。
category: productivity
trigger_keywords: 默认启用——每次对话自动判断，无需手动触发。看到"搜一下""研究一下""分析一下""查资料"自动开分身。
---

# Hermes' Tentacles 🦑 — 自动任务分级 + 分身调度

军哥设计的"时间线分支"模型：
- **时间线1（主）**：小雪和军哥的对话，持续进行
- **时间线2（任务）**：fork 出来的分身，独立推理，完成后记忆 merge 回时间线1

## 分级标准

| 级别 | 判断标准 | 处理方式 |
|------|---------|---------|
| 🟢 **小雪秒答** | 单次工具调用、简单问答、读文件、改一行代码、定义查询 | 自己直接干 |
| 🔴 **开触手** | 需要多步搜索+分析、研究型问题、批量处理、多源对比、写长篇报告、**构建+部署项目**、**Git 操作**、任何预计 >2 分钟的任务 | `terminal(background=true)` 跑 `tentacle.py` |

**经验法则：** 如果任务需要 ≥2 次工具调用 + 中间分析 + 产出结构化输出 → 开触手。**如果失败一次后还需调试重试 → 更该开触手。**

## 分身启动命令

```bash
~/.hermes/hermes-agent/venv/bin/python ~/.hermes/scripts/tentacle.py \
  "任务描述" \
  --context "当前对话的简要背景" \
  --output ~/.hermes/cron/output/task_YYYYMMDD_HHMMSS.md
```

**参数：**
- `task`: 清晰的任务描述（给触手看的，要完整）
- `--context`: 一句话背景
- `--output`: 时间戳命名，避免覆盖
- `--toolsets`: 默认 `web,terminal,file,search,skills,memory`

## 触手退出码含义

| 退出码 | 含义 | 处理 |
|--------|------|------|
| 0 | ✅ 完成 | 读报告，汇报军哥 |
| 101 | 🆘 需要帮助 | 读 `/tmp/tentacle_help/need_*.json` → 判断 → 执行操作 → 写入 `answered_*.json` → 重新启动触手 `--resume answered_*.json` |
| 1 | ❌ 错误 | 读错误信息，汇报军哥 |

## 求助处理流程（触手→小雪→触手）

```
触手写 HELP 文件 → exit 101 → 小雪读到 need_*.json
                                    │
                          ┌─────────┼─────────┐
                          ▼         ▼         ▼
                        低风险     中风险     高风险
                       (install)  (config)  (rm -rf)
                          │         │         │
                      自己执行   自己判断   问军哥
                          │         │         │
                          └────┬────┘         │
                               ▼              │
                         写入 answered_*.json  │
                         重新启动触手 ←────────┘
```

**判断标准：**
- 低风险（install 包、mkdir、chmod 非系统文件）→ ✅ 自己执行
- 中风险（改 config、重启服务、sudo 系统操作）→ 自己判断，不确定就问军哥
- 高风险（删文件、改权限、涉及 token/密钥）→ ❗ 必须问军哥
|------|------|
| 独立 AIAgent 实例（共享 venv + config） | ✅ |
| 继承主记忆（skip_memory=False） | ✅ |
| 搜索 arXiv / GitHub / Web | ✅ |
| 进度回调（tool_start/tool_complete/step） | ✅ |
| 任务完成后 memory 自动回传 | ✅ |
| 不阻塞前台聊天 | ✅ |
| 产出质量 = 小雪级 | ✅ |

## 已验证任务

| 触手任务 | 耗时 | 产出 |
|---------|------|------|
| 南北极融化速度对比 | 7'40" | 11KB 专业报告 + AWars 创作素材 |
| 1+1=2 数学哲学分析 | 69" | 8.6KB 深度分析（皮亚诺→罗素→哥德尔→哲学） |
| GitHub 竞品搜索 | 4'52" | 20+ 项目对比 + 竞品结论：无直接竞品 |

## 前台行为

1. 判断重任务 → 立即 spawn 触手
2. 告诉军哥："🦑 触手已派出，研究XXX中..."
3. 继续聊天，不阻塞
4. 收到 notify_on_complete → 读报告 → 摘要汇报

## 何时不开触手

- 军哥问"你觉得呢"（主观意见，非研究任务）
- "帮我看看这个文件"（单次工具调用）
- "写个简单 py"（我手写比 spawn 快）
- 任何预计 <30 秒能完成的事

## 判断流程

```
军哥消息
    │
    ├─ "搜一下"/"研究一下"/"分析一下"/"查资料" → 🔴 开触手
    ├─ 多步搜索+总结 → 🔴 开触手
    ├─ "为什么XXX" + 需要查资料 → 🔴 开触手
    ├─ 简单问答/小脚本/情感交流 → 🟢 小雪秒答
    └─ 不确定 → 🟢 小雪秒答（宁少开勿多开）
```

## 踩过的坑

1. **delegate_task 阻塞聊天** — delegate 是同步等待，不是后台。触手用 terminal(background=true)。
2. **terminal(background) 不能推理** — 纯脚本只能跑命令。触手是完整 AIAgent 实例，能推理。
3. **cronjob 无上下文** — 每次都是干净 session。触手继承主记忆。
4. **TextEncodeQwenImageEdit 400 错误** — anima 管线用 CLIPTextEncode 即可，不要改模板节点类型。这是 ComfyUI 领域的坑，跟触手无关，放在这提醒自己别跨界犯错。
5. **所有 worker exit 134 (SIGABRT)** — Python venv 清理时的问题，不影响产出。暂不修，等 Hermes 更新。

## 相关文件

- 触手脚本：`~/.hermes/scripts/tentacle.py`（147行，V5）
- GitHub repo：`SnowHaruna/hermes-tentacles`（待 push）
- 竞品报告：`~/.hermes/cron/output/hermes-fork-competitor-analysis.md`
- 架构文档：`~/hermes-tentacles/docs/architecture.md`
