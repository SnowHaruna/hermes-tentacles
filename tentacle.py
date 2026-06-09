#!/usr/bin/env python3
"""
Hermes' Tentacle V6 — 独立分身，主循环 + 原地等待协议。
用法: python3 tentacle.py "任务描述" [--context "上下文"] [--max-iterations 50]
退出码: 0=成功, 101=等待帮助中(不退出), 1=错误
信号处理: SIGTERM → 保存部分结果再退（不丢产出）

原则: 触手不自杀——跑到完，或被军哥喊停（小雪kill）。
"""

import sys, os, json, yaml, time, argparse, signal, glob
from pathlib import Path

HERMES_HOME = Path(os.environ.get("HERMES_HOME", os.path.expanduser("~/.hermes")))
HERMES_AGENT = HERMES_HOME / "hermes-agent"
sys.path.insert(0, str(HERMES_AGENT))

HELP_DIR = Path("/tmp/tentacle_help")

# ── 全局状态（信号处理时需要） ──
_partial_result = None
_output_path = None

def heartbeat():
    """写入心跳时间戳，小雪看门狗读取。异常时静默吞掉（别因为磁盘满崩触手）。"""
    try:
        (HELP_DIR / "heartbeat").write_text(str(time.time()))
    except Exception:
        pass

def log_progress(msg):
    print(f"[tentacle] {msg}", file=sys.stderr, flush=True)

def save_partial_and_exit(signum=None, frame=None):
    """SIGTERM 处理：保存已有结果，体面退出"""
    if _partial_result and _output_path:
        try:
            os.makedirs(os.path.dirname(_output_path), exist_ok=True)
            with open(_output_path, "w") as f:
                f.write(str(_partial_result))
            log_progress(f"🗡️ 收到停止信号 — 已保存部分结果到 {_output_path}")
        except Exception as e:
            log_progress(f"🗡️ 收到停止信号 — 保存失败: {e}")
    else:
        log_progress("🗡️ 收到停止信号 — 无结果可保存")
    sys.exit(0)

signal.signal(signal.SIGTERM, save_partial_and_exit)

def build_prompt(task, context, resume_files=None):
    """构建给 AIAgent 的 prompt —— 含求助协议 + 续跑上下文"""
    help_protocol = """## 求助协议 🆘
如果你遇到必须军哥才能解决的问题（需要权限、token、手动配置等），你已经试过所有你能用的方法。
此时：
1. 用 terminal 写入求助文件: /tmp/tentacle_help/need_NNN.json
   格式: {"issue": "简洁描述", "what_you_tried": "你试过的方法", "what_need_from_军哥": "需要军哥做什么"}
2. 结束当前轮次。触手脚本会检测到求助文件，进入等待状态。
3. 你不需要在 prompt 里处理等待——脚本层会处理。"""

    resume_context = ""
    if resume_files:
        resume_context = "\n## ⚡ 续跑上下文\n上次运行时你请求了帮助，军哥已经处理完毕。回复内容在以下文件中，请读取后继续未完成的工作：\n"
        for f in resume_files:
            resume_context += f"- {f}\n"
        resume_context += "\n先读取所有回复文件，然后从断点继续执行。"

    return f"""你是主 Hermes 的一条触手（时间线分支）。你分享主 Hermes 的记忆和知识，但任务流程是独立的。

{help_protocol}

## 记忆回传
任务完成后，使用 memory 工具将关键发现写入记忆池：
- 踩到的坑 → memory(action="add", target="memory")
- 搜到的关键数据 → memory(action="add", target="memory")
- 验证过的结论 → memory(action="add", target="memory")
- 一句话一条

## 执行
1. 完成任务
2. 如有求助，写入 /tmp/tentacle_help/need_*.json
3. 写报告到文件
4. 用 memory 回传关键发现
5. 输出 JSON 结果到 stdout

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
        except:
            log_progress(f"   📋 {nf.name}")

    log_progress("⏳ 等待军哥回复中...（小雪会汇报，看门狗会检测心跳）")

    answered = []
    last_log_time = time.time()
    while True:
        heartbeat()  # 等待期间也保持心跳！

        for nf in need_files:
            answer = HELP_DIR / nf.name.replace("need_", "answered_")
            if answer.exists() and answer not in answered:
                answered.append(answer)
                try:
                    with open(answer) as f:
                        ans_data = json.load(f)
                    log_progress(f"✅ 收到回复: {ans_data.get('resolution', '已处理')}")
                except:
                    log_progress(f"✅ 收到回复: {answer.name}")

        if len(answered) >= len(need_files):
            break

        time.sleep(3)

        # 每 60 秒汇报一次等待状态（没那么频繁，别吵）
        if time.time() - last_log_time > 60:
            elapsed = int(time.time() - last_log_time)
            log_progress(f"⏳ 仍在等待军哥回复... ({sum(1 for _ in HELP_DIR.glob('need_*.json')) - len(answered)} 个未回复)")
            last_log_time = time.time()

    log_progress(f"✅ 全部 {len(answered)} 个问题已回复，准备续跑")
    return answered

def run_agent(prompt, model, api_key, base_url, provider_name, enabled_sets, max_iterations):
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
        skip_context_files=True, skip_memory=False,
        load_soul_identity=True,
        tool_start_callback=on_tool_start,
        tool_complete_callback=on_tool_done,
    )
    return agent.run_conversation(prompt)

def main():
    global _partial_result, _output_path

    parser = argparse.ArgumentParser(description="Hermes' Tentacle V6 — 后台分身（原地等待，不自杀）")
    parser.add_argument("task", help="任务描述")
    parser.add_argument("--context", help="附加上下文", default="")
    parser.add_argument("--output", help="输出文件路径", default=str(HERMES_HOME / "cron/output/tentacle_result.md"))
    parser.add_argument("--toolsets", help="逗号分隔的工具集", default="web,terminal,file,search,skills,memory")
    parser.add_argument("--max-iterations", type=int, default=50, help="单轮最大推理步数（默认50）")
    args = parser.parse_args()

    HELP_DIR.mkdir(parents=True, exist_ok=True)

    # 加载配置
    cfg_path = HERMES_HOME / "config.yaml"
    cfg = {}
    if cfg_path.exists():
        with open(cfg_path) as f:
            cfg = yaml.safe_load(f) or {}

    from dotenv import load_dotenv
    try:
        load_dotenv(str(HERMES_HOME / ".env"), override=True, encoding="utf-8")
    except UnicodeDecodeError:
        load_dotenv(str(HERMES_HOME / ".env"), override=True, encoding="latin-1")

    model_cfg = cfg.get("model", {})
    model = model_cfg.get("default", os.getenv("HERMES_MODEL", ""))
    if isinstance(model_cfg, dict) and "default_model" in model_cfg:
        model = model_cfg["default_model"]

    provider_name = os.getenv("HERMES_PROVIDER") or model_cfg.get("provider", "deepseek")
    api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
    base_url = os.getenv("HERMES_BASE_URL")
    enabled_sets = [t.strip() for t in args.toolsets.split(",") if t.strip()]

    task_text = args.task
    if args.context:
        task_text = f"{args.context}\n\n{task_text}"

    # 清理旧的求助文件（新任务开始）
    for old in HELP_DIR.glob("need_*.json"):
        old.unlink(missing_ok=True)
    for old in HELP_DIR.glob("answered_*.json"):
        old.unlink(missing_ok=True)

    log_progress(f"🦑 V6 触手启动 — model={model} tools={enabled_sets} max_iter={args.max_iterations}")
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

        prompt = build_prompt(task_text, args.context, resume_files if resume_files else None)

        try:
            result = run_agent(prompt, model, api_key, base_url, provider_name,
                              enabled_sets, args.max_iterations)
        except Exception as e:
            elapsed = time.time() - global_start
            print(json.dumps({"status": "error", "task": args.task, "error": str(e),
                              "time_seconds": round(elapsed, 1)}, ensure_ascii=False, indent=2))
            sys.exit(1)

        final_result = result.get("final_response", str(result)) if isinstance(result, dict) else str(result)
        _partial_result = final_result  # 随时可被 SIGTERM 保存

        # 检查求助
        unanswered = get_unanswered_needs()
        if not unanswered:
            # ✅ 无求助 — 任务完成
            break

        # 🆘 有求助 — 原地等待军哥回复（无超时）
        answered = wait_for_answers(unanswered)
        resume_files = [str(a) for a in answered]
        log_progress(f"🔄 收到 {len(answered)} 个回复，续跑...")

    elapsed = time.time() - global_start

    # 写入报告
    _output_path = args.output
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, "w") as f:
        f.write(final_result or "")

    # 检查是否还有未回复的求助
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
