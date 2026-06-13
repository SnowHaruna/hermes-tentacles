<p align="center">
  <img src="https://img.shields.io/badge/license-MIT-blue" alt="License">
  <img src="https://img.shields.io/badge/python-3.10+-green" alt="Python">
  <img src="https://img.shields.io/badge/版本-V6.3-brightgreen" alt="Version">
  <img src="https://img.shields.io/badge/架构-章鱼分布式神经-purple" alt="Architecture">
  <img src="https://img.shields.io/badge/零依赖-共享_venv-success" alt="Zero Deps">
</p>

<h1 align="center">🦑 Hermes' Tentacles</h1>
<p align="center"><strong>指令驱动的 AI 分身系统 —— Fork 完整对话克隆到后台，独立推理，无缝回传</strong></p>
<p align="center">
  <em>榛名雪说搜/查/研究/分析/对比 → 立刻开分身。你全程不阻塞，该聊天聊天。</em>
</p>

---

## 为什么叫"触手"

2026 年 6 月，榛名雪和小雪在追溯 AI Agent 间通信的进化谱系时，走过一条完整的逆行路线：

```
章鱼分布式神经 → 昆虫串联神经索 → 单细胞生物化学通信
```

**章鱼的触手有独立神经节**——每根触手能自主决策、独立感知，同时通过分布式神经环与中央脑保持协同。这正是触手系统的架构隐喻：每个触手是独立的 Hermes 分身（独立推理），但共享主记忆快照（RAG 注入），完成后的发现通过 `tentacle_findings/` 回传、由小雪审查转正。

> 📚 详见：[单细胞通信研究报告](https://github.com/SnowHaruna/Hermes-MemVault) — 从群体感应到内共生，9 大生物通信机制 → AI Agent 间通信映射

---

## 为什么需要触手

现有 AI 助手做重活只有三条路：

| 方式 | 问题 |
|------|------|
| 前台干活 | 你干等 |
| 后台脚本 | 只会跑命令，不能推理 |
| 子 Agent | 干活时冻结聊天 |

**触手是第四条路。**

---

## 怎么工作

```
榛名雪发指令："搜一下XXX"
     │
     ▼
  小雪判断：明确指令 → 开触手！
     │
     ├─ 导出当前 RAG 记忆快照
     ├─ tentacle.py --inject-memory
     ├─ fork 独立 Hermes 实例
     │
     ├─ 🔧 推理中… (每步工具调用实时可见)
     ├─ 💭 内部推理 (stderr 进度)
     ├─ 📝 发现写入 tentacle_findings/
     │
     ├─ 🆘 遇到卡点 → 原地等待求助 (不退出!)
     │      ├─ 小雪读到 → 汇报榛名雪
     │      └─ 榛名雪处理完 → 触手续跑
     │
     └─ ✅ 完成 → 小雪自动审查发现
            ├─ 有用 → 转正进记忆
            └─ 废话 → 丢弃
```

---

## 快速开始

```bash
git clone https://github.com/SnowHaruna/hermes-tentacles.git

# 基础用法
~/.hermes/hermes-agent/venv/bin/python tentacle.py \
  --prompt "研究XXX" \
  --output ~/.hermes/reports/report.md \
  --max-iterations 40

# 带记忆快照注入
~/.hermes/hermes-agent/venv/bin/python tentacle.py \
  --prompt-file task.txt \
  --inject-memory /tmp/memory_snapshot.txt \
  --name "my-research" \
  --output ~/.hermes/reports/report.md \
  --toolsets "web,terminal,file"
```

---

## 关键设计决策（V6）

| 决策 | 原因 |
|------|------|
| 榛名雪指令驱动（非自动分级） | 榛名雪最清楚自己要什么，不猜 |
| RAG 快照注入（非触手自己搜） | 主副时间线记忆对齐 |
| 求助原地等待（非退出重开） | 不丢上下文，断点续跑 |
| tentacle_findings/ 文件回传 | 不进 MEMORY.md，防分身污染主记忆 |
| 小雪自动审查（非榛名雪手动） | 后台完成，不打扰 |

---

## 实时监控

触手不是黑盒——每步工具调用实时可见：

```
[tentacle] 🔧 web_search("El Niño 2026 forecast"...)
[tentacle] ✅ web_search → 5 results, 2.3s
[tentacle] 💭 推理中...
[tentacle] 🔧 write_file("/home/.../finding_001.txt"...)
```

小雪看门狗每 3 分钟巡检：心跳超 10 分钟 → 汇报榛名雪；运行超 15 分钟 → 汇报进度。

---

## 已验证任务

| 触手任务 | 耗时 | 产出 |
|---------|------|------|
| 南北极融化速度对比 | 7'40" | 11KB 专业报告 + AWars 创作素材 |
| 1+1=2 数学哲学 | 69" | 8.6KB 深度分析（皮亚诺→罗素→哥德尔） |
| 单细胞生物通信研究 | 4'10" | 43KB 论文级报告，35 篇参考文献 |
| GitHub 竞品搜索 | 4'52" | 20+ 项目对比 → 结论：无直接竞品 |
| Kahana 记忆文献深挖 | 多轮 | 7章逐章分析 + MemVault 架构参考 |

---

## 数据

| 指标 | 值 |
|------|-----|
| Fork 成本 | ~150MB 内存 |
| 产出质量 | = 主 AI 同级别 |
| 依赖 | 零——共享同一 Python venv |
| 场景 | 通吃——研究/分析/编程/写作 |
| 求助协议 | 原地等待，不退出 |
| GitHub | [SnowHaruna/hermes-tentacles](https://github.com/SnowHaruna/hermes-tentacles) |

---

## 安全审计

[SECURITY_AUDIT.md](SECURITY_AUDIT.md) — V6.2 审计：10 项漏洞 9 项已修复（C2/C3/H1/H2/M1/M2/M3/L1/L2），仅 C1（GitHub PAT 明文）需手动轮换。

---

## 相关项目

| 项目 | 关系 |
|------|------|
| [Hermes-MemVault](https://github.com/SnowHaruna/Hermes-MemVault) | 记忆系统，触手的 RAG 快照来源 |
| [memvault](https://github.com/SnowHaruna/memvault) | 独立 pip 包（感谢 @GwynCat） |

---

## 作者

**Design:** 榛名雪  
**Implementation:** 小雪 (Hermes Agent)  
**License:** MIT  

---

<p align="center">
  <em>「进化的方向不是更大的大脑，而是更多的触手。」</em>
</p>
