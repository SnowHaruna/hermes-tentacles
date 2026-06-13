# Hermes' Tentacles — 架构

## 时间线模型（榛名雪设计）

```
时间线1（主）────●────●────●────●──▶ 用户&AI 一直在聊
                  \              /
时间线2（任务）     ●──搜──踩坑──●──▶ 分支结束
                               merge 记忆
```

主对话持续进行。当 AI 判断任务过重时，自动 fork 一个时间线分支（触手）。
触手独立执行，完成后将关键发现 merge 回主记忆池。

## 组件

### tentacle.py（149 行）
核心分身脚本。被主 Hermes 通过 `terminal(background=true)` 调用。
- 继承主记忆（`skip_memory=False`）
- 独立 AIAgent 推理循环
- 任务完成后 `memory(action="add")` 回传发现
- 进度回调（`tool_start_callback` / `tool_complete_callback`）

### auto-task-triage（Skill）
内置于主 Hermes 的判定逻辑：
- 轻任务（<30秒）→ 自己秒答
- 重任务（多步搜索+分析）→ 自动 fork 触手

## 命令

```bash
~/.hermes/hermes-agent/venv/bin/python tentacle.py \
  "任务描述" \
  --context "背景上下文" \
  --output report.md
```

## 依赖

- Hermes Agent（纯 Python，共享 venv）
- DeepSeek API（触手调用的推理后端）
- 零外部依赖
