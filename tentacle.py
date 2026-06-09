#!/usr/bin/env python3
"""
Hermes Worker — 独立的"身体"，被主 Hermes 唤醒执行后台任务。
用法: python3 hermes-tentacle.py "任务描述" [--context "上下文"]
输出: JSON 格式结果到 stdout，完整日志到文件
"""

import sys, os, json, yaml, time, argparse
from pathlib import Path

# 把 hermes-agent 加入路径
HERMES_HOME = Path(os.environ.get("HERMES_HOME", os.path.expanduser("~/.hermes")))
HERMES_AGENT = HERMES_HOME / "hermes-agent"
sys.path.insert(0, str(HERMES_AGENT))

def main():
    parser = argparse.ArgumentParser(description="Hermes Worker — 后台分身")
    parser.add_argument("task", help="任务描述")
    parser.add_argument("--context", help="附加上下文", default="")
    parser.add_argument("--output", help="输出文件路径", default=str(HERMES_HOME / "cron/output/worker_result.md"))
    parser.add_argument("--toolsets", help="逗号分隔的工具集", default="web,terminal,file,search,skills,memory")
    args = parser.parse_args()

    # 加载配置
    cfg_path = HERMES_HOME / "config.yaml"
    cfg = {}
    if cfg_path.exists():
        with open(cfg_path) as f:
            cfg = yaml.safe_load(f) or {}

    # 加载 .env
    from dotenv import load_dotenv
    try:
        load_dotenv(str(HERMES_HOME / ".env"), override=True, encoding="utf-8")
    except UnicodeDecodeError:
        load_dotenv(str(HERMES_HOME / ".env"), override=True, encoding="latin-1")

    # 模型配置
    model_cfg = cfg.get("model", {})
    model = model_cfg.get("default", os.getenv("HERMES_MODEL", ""))
    if isinstance(model_cfg, dict) and "default_model" in model_cfg:
        model = model_cfg["default_model"]

    # 构建 provider runtime
    provider_name = os.getenv("HERMES_PROVIDER") or model_cfg.get("provider", "deepseek")
    api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
    base_url = os.getenv("HERMES_BASE_URL")

    # 工具集
    enabled_sets = [t.strip() for t in args.toolsets.split(",") if t.strip()]

    # 构建 prompt
    prompt = args.task
    if args.context:
        prompt = f"## 背景上下文\n{args.context}\n\n## 任务\n{args.task}"

    worker_prompt = f"""你是一个被主 Hermes 派来执行后台任务的工作员。你是主 Hermes 的"时间线分支"——你分享主 Hermes 的记忆和知识，但你的任务流程是独立的。

⚠️ 关键规则：记忆回传
任务完成后，你必须使用 memory 工具将所有重要发现写入记忆池：
- 踩到的坑（API 格式、工具用法、网络问题）→ memory(action="add", target="memory")
- 搜到的关键数据/趋势 → memory(action="add", target="memory")
- 验证过的结论 → memory(action="add", target="memory")
- 一句话一条，不要堆大段

主线：
1. 执行任务
2. 写报告到文件
3. 最后一步：用 memory 工具回传关键发现 ← 不可跳过

{prompt}"""

    print(f"[worker] Starting... model={model} tools={enabled_sets}", file=sys.stderr)
    print(f"[worker] Task: {args.task[:100]}", file=sys.stderr)

    # 进度回调 — 让主 Hermes 能实时监控
    step_count = [0]
    def log_progress(msg):
        print(f"[worker:{step_count[0]:02d}] {msg}", file=sys.stderr, flush=True)

    def on_tool_start(tc_id, name, args):
        step_count[0] += 1
        arg_preview = str(args)[:80] if args else ""
        log_progress(f"🔧 {name}({arg_preview}...)")

    def on_tool_done(tc_id, name, args, result):
        r = str(result)[:100].replace('\n', ' ')
        log_progress(f"✅ {name} → {r}")

    def on_step():
        log_progress(f"💭 推理中...")

    # 构建 AIAgent
    from run_agent import AIAgent

    agent = AIAgent(
        model=model,
        api_key=api_key,
        base_url=base_url,
        provider=provider_name,
        max_iterations=30,
        enabled_toolsets=enabled_sets,
        quiet_mode=False,
        skip_context_files=True,
        skip_memory=False,
        load_soul_identity=True,
        tool_start_callback=on_tool_start,
        tool_complete_callback=on_tool_done,
        step_callback=on_step,
    )

    start = time.time()
    try:
        result = agent.run_conversation(worker_prompt)
        elapsed = time.time() - start

        if isinstance(result, dict):
            final = result.get("final_response", str(result))
        else:
            final = str(result)

        output = {
            "status": "done",
            "task": args.task,
            "result": final,
            "time_seconds": round(elapsed, 1),
            "output_file": args.output,
        }

        # 保存结果
        os.makedirs(os.path.dirname(args.output), exist_ok=True)
        with open(args.output, "w") as f:
            f.write(final)

        print(json.dumps(output, ensure_ascii=False, indent=2))

    except Exception as e:
        elapsed = time.time() - start
        error_output = {
            "status": "error",
            "task": args.task,
            "error": str(e),
            "time_seconds": round(elapsed, 1),
        }
        print(json.dumps(error_output, ensure_ascii=False, indent=2))
        sys.exit(1)

if __name__ == "__main__":
    main()
