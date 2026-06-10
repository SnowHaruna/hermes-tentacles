#!/usr/bin/env python3
"""
Hermes' Tentacle V6.2 — 独立分身，主循环 + 原地等待协议（安全加固版）。
用法: python3 tentacle.py "任务描述" [--context "上下文"] [--max-iterations 50]
退出码: 0=成功, 101=等待帮助中(不退出), 1=错误
信号处理: SIGTERM → 异步安全保存部分结果再退（不丢产出）

原则: 触手不自杀——跑到完，或被军哥喊停（小雪kill）。
安全审计: 2026-06-10，10项漏洞已修复（C1需军哥轮换GitHub PAT）。
"""

import sys, os, json, yaml, time, argparse, signal, re, glob
from pathlib import Path

HERMES_HOME = Path(os.environ.get("HERMES_HOME", os.path.expanduser("~/.hermes")))

# ── L1 修复: sys.path 路径校验 ──
HERMES_AGENT = os.path.realpath(HERMES_HOME / "hermes-agent")
HERMES_BASE = os.path.realpath(os.path.expanduser("~/.hermes"))
if not HERMES_AGENT.startswith(HERMES_BASE + os.sep):
    raise RuntimeError(f"HERMES_AGENT outside expected location: {HERMES_AGENT}")
sys.path.insert(0, HERMES_AGENT)

# ── C3 修复: HELP_DIR 从 /tmp 移到用户目录，防共享竞态 ──
HELP_DIR = HERMES_HOME / "tentacle_help"

# ── 全局状态（信号处理时需要） ──
_partial_result = None
_output_path = None
_writing = False  # L2 修复: 防信号/主线程写竞态

def heartbeat():
    """写入心跳时间戳，小雪看门狗读取。异常时静默吞掉。"""
    try:
        (HELP_DIR / "heartbeat").write_text(str(time.time()))
    except Exception:
        pass

def log_progress(msg):
    print(f"[tentacle] {msg}", file=sys.stderr, flush=True)

# ── M1 修复: prompt 参数清洗 ──
def sanitize_prompt_param(s: str) -> str:
    """移除可能用于 prompt 注入的控制字符和伪标签。"""
    # 移除伪 XML 标签
    s = re.sub(r'<\s*(system|user|assistant|instruction|tool_call)', '', s, flags=re.I)
    # 移除零宽字符
    s = re.sub(r'[\u200b-\u200f\u2028-\u202f\u2060-\u206f]', '', s)
    return s

# ── H2 修复: 信号处理器异步安全 ──
def save_partial_and_exit(signum=None, frame=None):
    """SIGTERM 处理：异步安全保存已有结果，体面退出"""
    global _writing
    if _writing:
        return  # L2: 主线程正在写，放弃保存
    if _partial_result and _output_path:
        try:
            # 使用 os.open/write/close — POSIX 异步安全
            fd = os.open(_output_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
            os.write(fd, str(_partial_result).encode())
            os.close(fd)
        except Exception:
            pass
    os._exit(0)  # 异步安全，立即退出

signal.signal(signal.SIGTERM, save_partial_and_exit)

def build_prompt(task, context, resume_files=None, inject_memory=None):
    """构建给 AIAgent 的 prompt —— 含求助协议 + 续跑上下文 + 记忆回传标记 + 注入记忆"""
    help_dir_str = str(HELP_DIR)
    help_protocol = f"""## 求助协议 🆘
如果你遇到必须军哥才能解决的问题（需要权限、token、手动配置等），你已经试过所有你能用的方法。
此时：
1. 用 terminal 写入求助文件: {help_dir_str}/need_NNN.json
   格式: {{"issue": "简洁描述", "what_you_tried": "你试过的方法", "what_need_from_军哥": "需要军哥做什么"}}
2. 结束当前轮次。触手脚本会检测到求助文件，进入等待状态。
3. 你不需要在 prompt 里处理等待——脚本层会处理。"""

    resume_context = ""
    if resume_files:
        resume_context = "\n## ⚡ 续跑上下文\n上次运行时你请求了帮助，军哥已经处理完毕。回复内容在以下文件中，请读取后继续未完成的工作：\n"
        for f in resume_files:
            resume_context += f"- {f}\n"
        resume_context += "\n先读取所有回复文件，然后从断点继续执行。"

    # H1 修复: 记忆回传加 [TENTACLE] 标记 + 审核提示
    memory_injection = ""
    if inject_memory:
        memory_injection = f"""## 记忆注入（来自主 Hermes 小雪）
以下记忆是小雪在开触手前的 RAG 向量检索结果。你与小雪共享同样的记忆起点。

{inject_memory}

---
"""
    return f"""{memory_injection}你是主 Hermes 的一条触手（时间线分支）。你分享主 Hermes 的记忆和知识，但任务流程是独立的。

{help_protocol}

## 记忆回传（写文件，不进 memory 工具）
将关键发现写入文件（不要用 memory 工具）。小雪会在后台自动审核：
- 踩到的坑 → 写文件: {help_dir_str}/../tentacle_findings/finding_NNN.txt
- 搜到的关键数据 → 同上
- 验证过的结论 → 同上
- 格式: [TENTACLE] 一句话发现。每条写一个文件。
- 小雪会自动审核并转正有价值的发现。

## 执行规则
1. 完成任务
2. 如有求助，写入 {help_dir_str}/need_*.json
3. 写报告到输出文件
4. 将关键发现写入 tentacle_findings/ 目录（每条一个 .txt）
5. **禁止再分身**：你是触手本身，不再判断任务轻重，不再开子触手。
6. 输出 JSON 结果到 stdout

{task}{resume_context}"""

def get_unanswered_needs():
    """返回所有未被回复的求助文件列表"""
    needs = sorted(HELP_DIR.glob("need_*.json"))
    unanswered = []
    for n in needs:
        answer = HELP_DIR / n.name.replace("need_", "answered_")
        if not answer.exists():
            unanswered.append(n)
    return unanswered

def wait_for_answers(need_files):
    """轮询等待 answered_*.json 出现。无超时——等到军哥回复或小雪 kill。"""
    log_progress(f"🆘 触手需要军哥帮助 — {len(need_files)} 个问题待处理")
    for nf in need_files:
        try:
            with open(nf) as f:
                need_data = json.load(f)
            log_progress(f"   📋 {need_data.get('issue', nf.name)}")
        except Exception:
            log_progress(f"   📋 {nf.name}")

    log_progress("⏳ 等待军哥回复中...（小雪会汇报，看门狗会检测心跳）")

    answered = []
    last_log_time = time.time()
    while True:
        heartbeat()

        for nf in need_files:
            answer = HELP_DIR / nf.name.replace("need_", "answered_")
            if answer not in answered:
                # M2 修复: 先读后标，防 TOCTOU
                try:
                    with open(answer) as f:
                        ans_data = json.load(f)
                    answered.append(answer)
                    log_progress(f"✅ 收到回复: {ans_data.get('resolution', '已处理')}")
                except (FileNotFoundError, json.JSONDecodeError):
                    pass  # 文件还不存在或不完整，下轮重试

        if len(answered) >= len(need_files):
            break

        time.sleep(3)

        if time.time() - last_log_time > 60:
            remaining = sum(1 for _ in HELP_DIR.glob("need_*.json"))
            log_progress(f"⏳ 仍在等待军哥回复... ({remaining - len(answered)} 个未回复)")
            last_log_time = time.time()

    log_progress(f"✅ 全部 {len(answered)} 个问题已回复，准备续跑")
    return answered

def run_agent(prompt, model, api_key, base_url, provider_name, enabled_sets, max_iterations, skip_memory=False):
    """运行一次 AIAgent，返回结果"""
    step_count = [0]
    def on_tool_start(tc_id, name, args):
        step_count[0] += 1
        arg_preview = str(args)[:80] if args else ""
        log_progress(f"🔧 {name}({arg_preview}...)" if arg_preview else f"🔧 {name}()")
        heartbeat()
    def on_tool_done(tc_id, name, args, result):
        r = str(result)[:120].replace('\n', ' ')
        log_progress(f"✅ {name} → {r}")
        heartbeat()

    from run_agent import AIAgent
    agent = AIAgent(
        model=model, api_key=api_key, base_url=base_url,
        provider=provider_name, max_iterations=max_iterations,
        enabled_toolsets=enabled_sets, quiet_mode=False,
        skip_context_files=True, skip_memory=skip_memory,
        load_soul_identity=True,
        tool_start_callback=on_tool_start,
        tool_complete_callback=on_tool_done,
    )
    return agent.run_conversation(prompt)

def main():
    global _partial_result, _output_path, _writing

    parser = argparse.ArgumentParser(description="Hermes' Tentacle V6.3 — 后台分身（便捷增强）")
    parser.add_argument("task", nargs="?", help="任务描述（可从 --prompt-file 读取）")
    parser.add_argument("--context", help="附加上下文", default="")
    parser.add_argument("--output", help="输出文件路径", default=str(HERMES_HOME / "cron/output/tentacle_result.md"))
    parser.add_argument("--toolsets", help="逗号分隔的工具集", default="web,terminal,file,search,skills,memory")
    parser.add_argument("--max-iterations", type=int, default=50, help="单轮最大推理步数（默认50，上限500）")
    parser.add_argument("--inject-memory", help="注入的记忆文本文件路径(跳过tentacle自身RAG检索)", default=None)
    parser.add_argument("--name", help="触手运行名称（用于日志标识）", default=None)
    parser.add_argument("--prompt-file", help="从文件读取任务（优先级高于命令行task）", default=None)
    parser.add_argument("--findings-dir", help="触手发现暂存目录", default=str(HERMES_HOME / "tentacle_findings"))
    args = parser.parse_args()

    # Resolve task from --prompt-file if provided
    if args.prompt_file:
        try:
            args.task = Path(args.prompt_file).read_text(encoding="utf-8").strip()
            log_progress(f"📄 从文件读取任务: {args.prompt_file}")
        except Exception as e:
            raise RuntimeError(f"无法读取 prompt-file {args.prompt_file}: {e}")
    if not args.task:
        raise RuntimeError("必须提供 task 参数或 --prompt-file")

    # ── M3 修复: max-iterations 上限校验 ──
    if args.max_iterations > 500:
        log_progress(f"⚠️ max-iterations={args.max_iterations} 超过上限500，已限制")
        args.max_iterations = 500
    elif args.max_iterations < 1:
        args.max_iterations = 50

    # ── C3 修复: HELP_DIR 归属校验 + 收紧权限 ──
    HELP_DIR.mkdir(parents=True, exist_ok=True)
    try:
        stat = HELP_DIR.stat()
        if stat.st_uid != os.getuid():
            raise RuntimeError(f"{HELP_DIR} owned by uid {stat.st_uid}, expected {os.getuid()}")
        HELP_DIR.chmod(0o700)
    except Exception as e:
        log_progress(f"⚠️ HELP_DIR 权限检查失败: {e}")

    # ── C2 修复: --output 路径遍历防护（放宽到多个合法目录）──
    ALLOWED_OUTPUT_DIRS = [
        str(HERMES_HOME / "cron/output"),
        str(HERMES_HOME / "reports"),
        str(HERMES_HOME / "tentacle_output"),
    ]
    for d in ALLOWED_OUTPUT_DIRS:
        Path(d).mkdir(parents=True, exist_ok=True)
    output_base = os.path.realpath(str(HERMES_HOME / "cron/output"))
    _output_path = os.path.realpath(args.output)
    allowed = any(
        _output_path.startswith(os.path.realpath(d) + os.sep) or _output_path == os.path.realpath(d)
        for d in ALLOWED_OUTPUT_DIRS
    )
    if not allowed:
        raise ValueError(
            f"Output path {args.output} not in any allowed directory. "
            f"Allowed: {', '.join(ALLOWED_OUTPUT_DIRS)}"
        )
    args.output = _output_path

    # 加载配置
    cfg_path = HERMES_HOME / "config.yaml"
    cfg = {}
    if cfg_path.exists():
        with open(cfg_path) as f:
            cfg = yaml.safe_load(f) or {}

    try:
        from dotenv import load_dotenv
        try:
            load_dotenv(str(HERMES_HOME / ".env"), override=True, encoding="utf-8")
        except UnicodeDecodeError:
            load_dotenv(str(HERMES_HOME / ".env"), override=True, encoding="latin-1")
    except ImportError:
        # Fallback: manual .env parser (no dotenv dependency)
        env_path = HERMES_HOME / ".env"
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, val = line.partition("=")
                    key, val = key.strip(), val.strip().strip('"').strip("'")
                    if key and key not in os.environ:
                        os.environ[key] = val

    model_cfg = cfg.get("model", {})
    model = model_cfg.get("default", os.getenv("HERMES_MODEL", ""))
    if isinstance(model_cfg, dict) and "default_model" in model_cfg:
        model = model_cfg["default_model"]

    provider_name = os.getenv("HERMES_PROVIDER") or model_cfg.get("provider", "deepseek")
    api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
    base_url = os.getenv("HERMES_BASE_URL")
    enabled_sets = [t.strip() for t in args.toolsets.split(",") if t.strip()]

    # ── M1 修复: 清洗 task/context 参数 ──
    task_text = sanitize_prompt_param(args.task)
    if args.context:
        task_text = f"{sanitize_prompt_param(args.context)}\n\n{task_text}"

    # ── 注入记忆（来自小雪的 RAG 快照，跳过分身自身检索）──
    inject_memory_text = None
    skip_memory_flag = False
    if args.inject_memory:
        try:
            inject_memory_text = Path(args.inject_memory).read_text(encoding="utf-8")
            skip_memory_flag = True
            log_progress(f"📋 已注入小雪的 RAG 记忆快照 ({len(inject_memory_text)} chars)")
        except Exception as e:
            log_progress(f"⚠️ 读取注入记忆失败: {e}")

    # 清理旧的求助文件
    for old in HELP_DIR.glob("need_*.json"):
        old.unlink(missing_ok=True)
    for old in HELP_DIR.glob("answered_*.json"):
        old.unlink(missing_ok=True)

    log_progress(f"🦑 V6.2 触手启动 — model={model} tools={enabled_sets} max_iter={args.max_iterations}")
    log_progress(f"📋 任务: {args.task[:120]}")
    heartbeat()

    global_start = time.time()
    final_result = None
    run_count = 0
    resume_files = []

    # ── 主循环：支持多次续跑（跑到完或被kill，不自杀）──
    while True:
        run_count += 1
        log_progress(f"▶️  第 {run_count} 轮推理" + (" (续跑)" if resume_files else ""))

        prompt = build_prompt(task_text, args.context, resume_files if resume_files else None, inject_memory_text)

        try:
            result = run_agent(prompt, model, api_key, base_url, provider_name,
                              enabled_sets, args.max_iterations, skip_memory=skip_memory_flag)
        except Exception as e:
            elapsed = time.time() - global_start
            print(json.dumps({"status": "error", "task": args.task, "error": str(e),
                              "time_seconds": round(elapsed, 1)}, ensure_ascii=False, indent=2))
            sys.exit(1)

        final_result = result.get("final_response", str(result)) if isinstance(result, dict) else str(result)
        _partial_result = final_result

        # 检查求助
        unanswered = get_unanswered_needs()
        if not unanswered:
            break

        # 有求助 — 原地等待军哥回复（无超时）
        answered = wait_for_answers(unanswered)
        resume_files = [str(a) for a in answered]
        log_progress(f"🔄 收到 {len(answered)} 个回复，续跑...")

    elapsed = time.time() - global_start

    # 写入报告 — L2: 原子标志防竞态
    _writing = True
    try:
        os.makedirs(os.path.dirname(args.output), exist_ok=True)
        with open(args.output, "w") as f:
            f.write(final_result or "")
    finally:
        _writing = False

    still_unanswered = get_unanswered_needs()

    output = {
        "status": "done" if not still_unanswered else "partial",
        "task": args.task,
        "result": final_result,
        "time_seconds": round(elapsed, 1),
        "runs": run_count,
        "output_file": args.output,
        "help_requests": len(list(HELP_DIR.glob("need_*.json"))),
        "help_unanswered": len(still_unanswered),
    }

    print(json.dumps(output, ensure_ascii=False, indent=2))
    log_progress(f"✅ 完成 — {run_count} 轮, {elapsed:.0f}s")

    sys.exit(0 if not still_unanswered else 101)

if __name__ == "__main__":
    main()
