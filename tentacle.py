#!/usr/bin/env python3
"""
Hermes' Tentacle V6 — 独立分身，主循环 + 等待协议。
用法: python3 tentacle.py "任务描述" [--context "上下文"] [--resume]
退出码: 0=成功, 101=等待中(不退出), 102=超时/被掐, 1=错误

V6 核心改动: 101 不再退出，触手原地轮询等待 answered_*.json，
收到军哥回复后继续工作——真正的"暂停续跑"。
"""

import sys, os, json, yaml, time, argparse, glob
from pathlib import Path

HERMES_HOME = Path(os.environ.get("HERMES_HOME", os.path.expanduser("~/.hermes")))
HERMES_AGENT = HERMES_HOME / "hermes-agent"
sys.path.insert(0, str(HERMES_AGENT))

HELP_DIR = Path("/tmp/tentacle_help")

def log_progress(msg):
    print(f"[tentacle] {msg}", file=sys.stderr, flush=True)

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

def wait_for_answers(need_files, timeout=3600):
    """轮询等待 answered_*.json 出现。返回已出现的回答文件列表。"""
    log_progress(f"🆘 触手需要军哥帮助 — {len(need_files)} 个问题待处理")
    for nf in need_files:
        try:
            with open(nf) as f:
                need_data = json.load(f)
            log_progress(f"   📋 {need_data.get('issue', nf.name)}")
        except:
            log_progress(f"   📋 {nf.name}")

    log_progress("⏳ 等待军哥回复中...（小雪会汇报）")

    answered = []
    start = time.time()
    while time.time() - start < timeout:
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
        # 每 30 秒汇报一次等待状态
        if int(time.time() - start) % 30 < 3:
            log_progress(f"⏳ 仍在等待... ({int(time.time() - start)}s)")

    if len(answered) < len(need_files):
        log_progress(f"⚠️ 等待超时 ({timeout}s)，{len(need_files) - len(answered)} 个问题未回复")
    return answered

def run_agent(prompt, model, api_key, base_url, provider_name, enabled_sets):
    """运行一次 AIAgent，返回结果"""
    step_count = [0]
    def on_tool_start(tc_id, name, args):
        step_count[0] += 1
        arg_preview = str(args)[:80] if args else ""
        log_progress(f"🔧 {name}({arg_preview}...)")
    def on_tool_done(tc_id, name, args, result):
        r = str(result)[:100].replace('\n', ' ')
        log_progress(f"✅ {name} → {r}")

    from run_agent import AIAgent
    agent = AIAgent(
        model=model, api_key=api_key, base_url=base_url,
        provider=provider_name, max_iterations=30,
        enabled_toolsets=enabled_sets, quiet_mode=False,
        skip_context_files=True, skip_memory=False,
        load_soul_identity=True,
        tool_start_callback=on_tool_start,
        tool_complete_callback=on_tool_done,
    )
    return agent.run_conversation(prompt)

def main():
    parser = argparse.ArgumentParser(description="Hermes' Tentacle V6 — 后台分身（原地等待）")
    parser.add_argument("task", help="任务描述")
    parser.add_argument("--context", help="附加上下文", default="")
    parser.add_argument("--output", help="输出文件路径", default=str(HERMES_HOME / "cron/output/tentacle_result.md"))
    parser.add_argument("--toolsets", help="逗号分隔的工具集", default="web,terminal,file,search,skills,memory")
    parser.add_argument("--timeout", type=int, default=600, help="最大运行秒数，超时自爆")
    parser.add_argument("--resume", help="从求助恢复（用于外部重启，一般不需要）", default="")
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

    log_progress(f"🦑 V6 触手启动 — model={model} tools={enabled_sets}")
    log_progress(f"📋 任务: {args.task[:120]}")

    global_start = time.time()
    final_result = None
    run_count = 0
    resume_files = []

    # ── 主循环：支持多次续跑 ──
    while True:
        if global_start and time.time() - global_start > args.timeout:
            log_progress(f"⏰ 全局超时 ({args.timeout}s) — exit 102")
            print(json.dumps({"status": "killed", "task": args.task, "reason": "timeout",
                              "time_seconds": round(time.time() - global_start, 1)},
                             ensure_ascii=False, indent=2))
            sys.exit(102)

        run_count += 1
        log_progress(f"▶️  第 {run_count} 轮推理" + (" (续跑)" if resume_files else ""))

        prompt = build_prompt(task_text, args.context, resume_files if resume_files else None)

        try:
            result = run_agent(prompt, model, api_key, base_url, provider_name, enabled_sets)
        except Exception as e:
            elapsed = time.time() - global_start
            print(json.dumps({"status": "error", "task": args.task, "error": str(e),
                              "time_seconds": round(elapsed, 1)}, ensure_ascii=False, indent=2))
            sys.exit(1)

        final_result = result.get("final_response", str(result)) if isinstance(result, dict) else str(result)

        # 检查求助
        unanswered = get_unanswered_needs()
        if not unanswered:
            # ✅ 无求助 — 任务完成
            break

        # 🆘 有求助 — 等待军哥回复
        answered = wait_for_answers(unanswered)

        if answered:
            resume_files = [str(a) for a in answered]
            log_progress(f"🔄 收到 {len(answered)} 个回复，准备续跑...")
            continue
        else:
            # 等待超时 — 放弃
            log_progress("⚠️ 等待超时，放弃续跑")
            break

    elapsed = time.time() - global_start

    # 写入报告
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, "w") as f:
        f.write(final_result or "")

    # 检查是否还有未回复的求助（正常完成但可能有遗留）
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
