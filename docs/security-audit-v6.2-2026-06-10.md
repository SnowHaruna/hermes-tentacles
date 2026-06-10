# 🔐 Hermes' Tentacles V6.2 安全审计报告

**审计日期**: 2026-06-10  
**审计范围**: `~/hermes-tentacles/` — tentacle.py V6.2 (326行), docs, .git/config  
**审计者**: 触手分身 (Hermes Tentacle)  
**上一轮审计**: 2026-06-10 (V6.1, 发现10项漏洞)  
**本轮审计**: V6.2 安全加固验证 + 增量发现  

---

## 执行摘要

V6.1 审计发现的 **10 项漏洞**，V6.2 已修复 **9 项**（代码级），剩余 **1 项** 需军哥手动操作（GitHub PAT 轮换）。

本轮增量审计发现 **4 项新问题**：🔵LOW×3 + ℹ️INFO×1。无新 CRITICAL/HIGH/MEDIUM。

**总体安全评级: 🟢 良好**（较 V6.1 的 🟡 显著提升）

---

## 一、V6.1 漏洞修复验证

### 🔴 CRITICAL

| # | 漏洞 | V6.1 状态 | V6.2 修复 | 验证结果 |
|---|------|-----------|-----------|----------|
| C1 | GitHub PAT 明文在 .git/config | 未修复 | 需手动轮换 | ⚠️ **仍待处理** — PAT `ghp_0A...6SK6` 仍在 `.git/config` 第7行 |
| C2 | --output 路径遍历 → 任意文件写入 | tentacle.py:254-256 | `os.path.realpath()` + 前缀白名单校验 (行214-222) | ✅ **已修复** — 5/5 路径遍历测试用例通过 |

**C2 修复细节：**
```python
# 行214-222
output_base = os.path.realpath(str(HERMES_HOME / "cron/output"))
_output_path = os.path.realpath(args.output)
if not _output_path.startswith(output_base + os.sep) and _output_path != output_base:
    raise ValueError(...)
```
测试验证：`../../../etc/passwd` → BLOCKED ✅ | `/etc/passwd` → BLOCKED ✅ | symlink跟随正确解析 ✅

### 🟠 HIGH

| # | 漏洞 | V6.1 状态 | V6.2 修复 | 验证结果 |
|---|------|-----------|-----------|----------|
| C3 | /tmp/tentacle_help 共享资源竞态 | 0775 world-readable | HELP_DIR → `~/.hermes/tentacle_help/` + `chmod 700` + uid校验 (行24-25,204-212) | ✅ **已修复** |
| H1 | Memory 写回投毒 | 无防护 | prompt 要求 `[TENTACLE]` 前缀 + 审核提示 (行92-97) | ✅ **已缓解** — 标记化隔离，主Hermes可审核 |
| H2 | SIGTERM 处理器 `sys.exit(0)` 非异步安全 | tentacle.py:46 | `os._exit(0)` + `os.open/write/close` POSIX异步安全API (行52-65) | ✅ **已修复** |

**C3 修复细节：**
- `HELP_DIR = HERMES_HOME / "tentacle_help"` (从 `/tmp` 移到用户目录)
- 创建后立即 `chmod(0o700)` 
- uid 归属校验 (防预占攻击)
- 注意：目录在首次运行时才创建，当前不存在（正常行为）

**H2 修复细节：**
- `os._exit(0)` 替代 `sys.exit(0)` — 不触发 `atexit`，不抛异常，立即退出
- 文件I/O使用 `os.open/os.write/os.close` — POSIX异步安全

### 🟡 MEDIUM

| # | 漏洞 | V6.1 状态 | V6.2 修复 | 验证结果 |
|---|------|-----------|-----------|----------|
| M1 | Prompt 注入 (task/context) | 无清洗 | `sanitize_prompt_param()` 移除伪XML标签+零宽字符 (行43-49) | ✅ **已修复** — ReDoS测试通过(10KB输入<0.001s) |
| M2 | TOCTOU 竞态 (exists→open) | tentacle.py:115-125 | 先读取成功后再 `append` (行138-146) | ✅ **已修复** |
| M3 | --max-iterations 无上限 | 无限制 | 上限500，下限1 (行197-202) | ✅ **已修复** |

**M1 修复注意**：正则 `<\\s*(system|user|assistant|instruction|tool_call)` 只移除开始标签，残留 `>` 无实际注入风险。

### 🔵 LOW

| # | 漏洞 | V6.1 状态 | V6.2 修复 | 验证结果 |
|---|------|-----------|-----------|----------|
| L1 | sys.path 注入 | tentacle.py:14-16 | `os.path.realpath()` + 归属校验 (行17-22) | ✅ **已修复** |
| L2 | 信号/主线程写竞态 | 无防护 | `_writing` 原子标志 (行30,54-56,299-305) | ✅ **已修复** |

---

## 二、本轮增量发现（V6.2 新问题）

### N1 — 🔵 LOW: 工具调用参数/结果泄露到 stderr 日志

**位置**: `tentacle.py` 行166-171  
**CWE**: CWE-532 (敏感信息存入日志)

```python
def on_tool_start(tc_id, name, args):
    arg_preview = str(args)[:80]     # ← 可能包含敏感参数
    log_progress(f"🔧 {name}({arg_preview}...)")

def on_tool_done(tc_id, name, args, result):
    r = str(result)[:120]             # ← 可能包含敏感结果
    log_progress(f"✅ {name} → {r}")
```

**风险**：若触手调用 `memory(action="add", content="敏感信息")` 或 `write_file(path="/etc/shadow", ...)`，参数/结果会明文输出到 stderr。stderr 通常被主 Hermes 进程捕获，在受控环境中风险低，但不符合防御深度原则。

**修复建议**：
```python
# 方案：对已知敏感工具名进行参数遮蔽
SENSITIVE_TOOLS = {"memory", "write_file", "patch"}
def on_tool_start(tc_id, name, args):
    if name in SENSITIVE_TOOLS:
        arg_preview = "<redacted>"
    else:
        arg_preview = str(args)[:80] if args else ""
    ...
```

### N2 — 🔵 LOW: HELP_DIR chmod 失败不阻断

**位置**: `tentacle.py` 行206-212  
**CWE**: CWE-276 (不正确的默认权限)

```python
try:
    stat = HELP_DIR.stat()
    if stat.st_uid != os.getuid():
        raise RuntimeError(...)
    HELP_DIR.chmod(0o700)
except Exception as e:
    log_progress(f"⚠️ HELP_DIR 权限检查失败: {e}")  # ← 不致命，继续运行
```

**风险**：如果 `mkdir` 成功但 `chmod` 失败（例如文件系统不支持权限），HELP_DIR 可能保留默认 umask 权限（通常 0755）。在单用户桌面系统风险低。

**建议**：权限失败后至少确保 `stat.st_mode & 0o077 == 0`（验证 other 无权限），否则警告但仍继续（不阻断功能）。

### N3 — 🔵 LOW: `from dotenv import load_dotenv` 无条件导入

**位置**: `tentacle.py` 行231  
**CWE**: CWE-754 (对异常条件的不当检查)

```python
from dotenv import load_dotenv          # ← 无 try/except，dotenv 不可用则崩溃
try:
    load_dotenv(...)
except UnicodeDecodeError:
    ...
```

**风险**：如果 `tentacle.py` 在非 hermes-agent venv 中运行（`python-dotenv` 不在系统 Python），启动即崩溃。当前调用链总是通过 venv 运行，但代码缺乏防御性。

**修复建议**：
```python
try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = lambda *a, **kw: None  # 优雅降级
```

### N4 — ℹ️ INFO: 未使用的导入 `glob`

**位置**: `tentacle.py` 行12  
**严重度**: 代码质量（非安全）

`import glob` 未被使用。代码中所有 glob 操作均通过 `pathlib.Path.glob()`。`re` 导入已被 V6.2 的 `sanitize_prompt_param()` 使用。

---

## 三、CWE 覆盖矩阵

| CWE | 描述 | tentacle.py 状态 | 备注 |
|-----|------|-----------------|------|
| CWE-22 | 路径遍历 | ✅ 已修复 | realpath + 白名单 |
| CWE-78 | OS命令注入 | ✅ 无风险 | 无 subprocess/os.system 调用 |
| CWE-94 | 代码注入 | ✅ 无风险 | 无 eval/exec/compile |
| CWE-312 | 敏感信息明文存储 | ⚠️ C1 待处理 | PAT 在 .git/config |
| CWE-367 | TOCTOU 竞态 | ✅ 已修复 | 先读后标 |
| CWE-400 | 资源消耗失控 | ✅ 已修复 | max_iterations ≤ 500 |
| CWE-426 | 不可信搜索路径 | ✅ 已修复 | sys.path 校验 |
| CWE-502 | 不可信数据反序列化 | ✅ 无风险 | yaml.safe_load() |
| CWE-532 | 日志中敏感信息 | ⚠️ N1 | 工具参数/结果记录 |
| CWE-276 | 默认权限不正确 | ✅ 已修复 (C3) + ⚠️ N2 | chmod 700 + 降级告警 |
| CWE-362 | 并发竞态 | ✅ 已修复 (L2) | _writing 原子标志 |
| CWE-754 | 异常检查不当 | ⚠️ N3 | dotenv 导入未保护 |

---

## 四、正面安全实践（保持）

| 实践 | V6.1 | V6.2 |
|------|------|------|
| 🔒 零外部 PyPI 依赖（仅 stdlib + yaml + dotenv + Hermes 内置） | ✅ | ✅ |
| 🔒 `yaml.safe_load()` 而非 `yaml.load()` | ✅ | ✅ |
| 🔒 API key 仅从环境变量读取，无硬编码 | ✅ | ✅ |
| 🔒 Git 历史中无 token 泄露（已扫描） | ✅ | ✅ |
| 🔒 心跳异常静默容错（磁盘满不崩） | ✅ | ✅ |
| 🔒 不可自杀设计（需人工 kill） | ✅ | ✅ |
| 🔒 退出码清晰定义（0/101/1） | ✅ | ✅ |
| 🔒 SIGTERM 异步安全退出 (`os._exit`) | ❌ | ✅ **新增** |
| 🔒 路径遍历防护 (realpath + 白名单) | ❌ | ✅ **新增** |
| 🔒 HELP_DIR 从 /tmp 移到用户目录 + chmod 700 | ❌ | ✅ **新增** |
| 🔒 Prompt 参数清洗 | ❌ | ✅ **新增** |
| 🔒 Memory 写回带标记隔离 | ❌ | ✅ **新增** |

---

## 五、修复优先级

| 优先级 | 项目 | 类型 | 工作量 | 负责人 |
|--------|------|------|--------|--------|
| **P0 立即** | C1 — GitHub PAT 轮换 | 手动操作 | 2分钟 | **军哥** |
| P3 可选 | N1 — 工具日志脱敏 | 代码 | 5分钟 | 小雪 |
| P3 可选 | N3 — dotenv 导入保护 | 代码 | 2分钟 | 小雪 |
| P3 可选 | N2 — chmod 验证加固 | 代码 | 3分钟 | 小雪 |
| — | N4 — glob 清理 | 代码质量 | 1分钟 | 小雪 |

---

## 六、总体结论

**V6.2 安全加固成效显著**。与 V6.1 相比：

- 🔴 CRITICAL: 2→1（C2已修复，C1需手动）
- 🟠 HIGH: 3→0（全部修复）
- 🟡 MEDIUM: 3→0（全部修复）  
- 🔵 LOW: 2→5（2项已修 + 3项新发现）
- ℹ️ INFO: 0→1

**唯一阻塞项**：C1 (GitHub PAT 轮换) — 需军哥登录 GitHub Settings → Developer settings → Personal access tokens → 撤销 `ghp_0A...6SK6` → 生成新 token → 配置 credential helper。

**推荐下一步**：
1. 军哥轮换 GitHub PAT (P0)
2. 可选修复 N1/N2/N3 (P3, 累计<10分钟)
3. 清理 `import glob` (N4, 1分钟)

---

*审计完成于 2026-06-10。触手分身提交。*
