#!/usr/bin/env python3
"""
Hermes' Tentacle — 独立分身，被主 Hermes 唤醒执行后台任务。
用法: python3 tentacle.py "任务描述" [--context "上下文"] [--resume]
输出: JSON 格式结果到 stdout
退出码: 0=成功, 101=需要帮助(权限/人工介入), 1=错误
"""

import sys, os, json, yaml, time, argparse, glob
from pathlib import Path

HERMES_HOME = Path(os.environ.get("HERMES_HOME", os.path.expanduser("~/.hermes")))
HERMES_AGENT = HERMES_HOME / "hermes-agent"
sys.path.insert(0, str(HERMES_AGENT))

HELP_DIR = Path("/tmp/tentacle_help")

def log_progress(msg):
    print(f"[tentacle] {msg}", file=sys.stderr, flush=True)

def main():
    parser = argparse.ArgumentParser(description="Hermes' Tentacle — 后台分身")
    parser.add_argument("task", help="任务描述")
    parser.add_argument("--context", help="附加上下文", default="")
    parser.add_argument("--output", help="输出文件路径", default=str(HERMES_HOME / "cron/output/tentacle_result.md"))
    parser.add_argument("--toolsets", help="逗号分隔的工具集", default="web,terminal,file,search,skills,memory")
    parser.add_argument("--resume", help="从求助恢复（HELP文件路径）", default="")
    args = parser.parse_args()

    # 创建 help 目录
    HELP_DIR.mkdir(parents=True, exist_ok=True)

    # 加载配置 & .env
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

    # 构建 prompt — 含求助协议
    task_text = args.task
    resume_note = ""
    if args.resume:
        resume_note = f"\n\n⚠️ 上次运行时你请求了帮助，现已处理完毕。回复文件在 {args.resume}。请继续完成你未完成的工作。"

    worker_prompt = f"""你是主 Hermes 的一条触手（时间线分支）。你分享主 Hermes 的记忆和知识，但任务流程是独立的。

## 求助协议 🆘
如果你遇到需要主 Hermes 协助的操作（需要 sudo、需要 token、需要军哥确认才能执行的破坏性操作），**不要停下来，按以下协议处理**：

1. 用 terminal 写入求助文件：
   /tmp/tentacle_help/need_NNN.json
   格式：{{"action": "需要执行的操作", "risk": "低/中/高", "reason": "原因"}}

2. **继续执行任务的其他部分**——不要等待回复，先把能做的都做了

3. 任务结束时，检查 /tmp/tentacle_help/ 下是否有 answered_NNN.json 回复文件。如果有，读取并纳入最终结果

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

{task_text}{resume_note}"""

    log_progress(f"Starting... model={model} tools={enabled_sets}")
    log_progress(f"Task: {args.task[:100]}")

    # 进度回调
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

    start = time.time()
    try:
        result = agent.run_conversation(worker_prompt)
        elapsed = time.time() - start
        final = result.get("final_response", str(result)) if isinstance(result, dict) else str(result)

        # 检查是否有未处理的求助
        needs = list(HELP_DIR.glob("need_*.json"))
        has_unanswered = any(not Path(str(n).replace("need_", "answered_")).exists() for n in needs)

        output = {
            "status": "done" if not has_unanswered else "need_help",
            "task": args.task,
            "result": final,
            "time_seconds": round(elapsed, 1),
            "output_file": args.output,
            "help_needed": len(needs) if has_unanswered else 0,
        }

        os.makedirs(os.path.dirname(args.output), exist_ok=True)
        with open(args.output, "w") as f:
            f.write(final)

        print(json.dumps(output, ensure_ascii=False, indent=2))
        sys.exit(101 if has_unanswered else 0)

    except Exception as e:
        elapsed = time.time() - start
        print(json.dumps({"status": "error", "task": args.task, "error": str(e), "time_seconds": round(elapsed, 1)}, ensure_ascii=False, indent=2))
        sys.exit(1)

if __name__ == "__main__":
    main()
