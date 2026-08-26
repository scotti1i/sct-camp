"""`uv run week02`:Week 2 批量视频工厂入口。

无参数 = 默认入口:浏览器打开工作台(点「跑一遍 Demo」出结果,全程不看终端)。
子命令是管线,给 AI agent 和自动化用:

demo    —— 零密钥,mock 流水线一条命令跑通,结尾出 HTML 结果报告
doctor  —— 本周环境体检
scripts / prompts / submit / poll / sync —— 流水线单步执行
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from camp_core import command_exists, load_config
from camp_core.doctor import Check, core_checks, run_checks

from week02_video_factory import pipeline, workbench
from week02_video_factory.providers import video_api_key


def _config() -> dict[str, Any]:
    return load_config(pipeline.PROJECT_DIR)


def _print_sync(synced: int) -> None:
    if synced:
        print(f"已同步 {synced} 条任务到飞书 Base。")


# ==================== demo ====================


def cmd_demo(args: argparse.Namespace) -> None:
    """完整 mock 流水线:脚本 → prompt → mock 提交 → 轮询到成功 → HTML 报告。"""
    result = workbench.run_demo(args.count)
    print(f"\n任务数据: {pipeline.TASKS_FILE}")
    print(f"结果报告: {result['report']}")
    print("真实生成看 README:改 config.json 的 video.provider,再跑 week02 submit / poll。")


# ==================== doctor ====================


def _probe_base(config: dict[str, Any]) -> tuple[bool, str]:
    base = config.get("base", {})
    if not base.get("enabled"):
        return True, ""
    if not base.get("base_token"):
        return False, "base.enabled=true 但 base_token 为空;先复制 Base 模板再填 token"
    if not command_exists("lark-cli"):
        return False, "npm install -g @larksuiteoapi/lark-cli 并登录"
    return True, ""


def _probe_provider(config: dict[str, Any]) -> tuple[bool, str]:
    provider = config.get("video", {}).get("provider", "mock")
    if provider in ("mock", "web_manual"):
        return True, ""
    if provider == "dreamina":
        return command_exists("dreamina"), "安装并登录 dreamina CLI;或先把 provider 改回 mock"
    api = config.get("video_api", {})
    ready = bool(api.get("endpoint") and api.get("model") and video_api_key(api))
    return ready, "endpoint/model 填 config.json,密钥填仓库根 .env(参考 .env.example)"


def cmd_doctor(args: argparse.Namespace) -> None:
    config = _config()
    provider = config.get("video", {}).get("provider", "mock")
    checks = core_checks() + [
        Check("config.json 存在", lambda: (
            (pipeline.PROJECT_DIR / "config.json").exists(),
            "任意 week02 命令首跑会自动从 config.example.json 生成",
        )),
        Check("飞书 Base 写回(可选)", lambda: _probe_base(config)),
        Check(f"视频 provider 就绪(当前 {provider})", lambda: _probe_provider(config)),
    ]
    ok = run_checks(checks)
    print("本周环境全绿,先跑: uv run week02 demo" if ok else "按 [FIX] 提示逐条修复后重跑。")
    raise SystemExit(0 if ok else 1)


# ==================== 流水线单步 ====================


def cmd_scripts(args: argparse.Namespace) -> None:
    config = _config()
    tasks = pipeline.generate_scripts(config, args.count)
    print(f"已生成 {len(tasks)} 条脚本: {pipeline.TASKS_FILE}")
    _print_sync(pipeline.sync_tasks(config, tasks))
    print("下一步: uv run week02 prompts")


def cmd_prompts(args: argparse.Namespace) -> None:
    config = _config()
    tasks = pipeline.generate_prompts(config)
    print(f"已为 {len(tasks)} 条任务生成分镜 prompt。")
    _print_sync(pipeline.sync_tasks(config, tasks))
    print("下一步: uv run week02 submit --provider mock|web_manual|dreamina|video_api")


def cmd_submit(args: argparse.Namespace) -> None:
    config = _config()
    provider = args.provider or config.get("video", {}).get("provider", "mock")
    submitted, tasks = pipeline.submit_tasks(config, provider)
    print(f"已处理 {submitted} 条 {provider} 视频任务。")
    _print_sync(pipeline.sync_tasks(config, tasks))
    print("下一步: uv run week02 poll")


def cmd_poll(args: argparse.Namespace) -> None:
    config = _config()
    success, tasks = pipeline.poll_tasks(config)
    print(f"轮询完成:{success} 条任务变成生成成功。")
    _print_sync(pipeline.sync_tasks(config, tasks))


def cmd_sync(args: argparse.Namespace) -> None:
    config = _config()
    state = pipeline.write_base_state(config)
    print(f"已写入 Base 状态: {state}")
    if not pipeline.base_enabled(config):
        print("未启用飞书 Base(或缺 base_token / lark-cli),当前只用本地 JSON,不阻塞流程。")
        return
    tasks = pipeline.load_tasks()
    if not tasks:
        raise SystemExit("没有可同步任务,请先运行: uv run week02 scripts")
    _print_sync(pipeline.sync_tasks(config, tasks))


# ==================== 入口 ====================


def cmd_serve(args: argparse.Namespace) -> None:
    workbench.serve(port=args.port, open_browser=not args.no_browser)


def cmd_workbench(argv: list[str]) -> None:
    """无参数默认入口:浏览器打开工作台;子命令是给 AI agent 和自动化的。"""
    parser = argparse.ArgumentParser(prog="week02", description="Week 2 批量 AI 视频工厂(工作台)")
    parser.add_argument("--port", type=int, default=0, help=f"默认 {workbench.PORT}")
    parser.add_argument("--no-browser", "--no-open", action="store_true", help="不自动打开浏览器(测试用)")
    args = parser.parse_args(argv)
    workbench.serve(port=args.port, open_browser=not args.no_browser)


def main() -> None:
    argv = sys.argv[1:]
    if not argv or (argv[0].startswith("-") and argv[0] not in ("-h", "--help")):
        cmd_workbench(argv)
        return
    parser = argparse.ArgumentParser(
        prog="week02", description="Week 2 批量 AI 视频工厂",
        epilog="不带子命令直接运行 = 打开工作台(默认入口);子命令给 AI agent 和自动化用。")
    sub = parser.add_subparsers(dest="command", required=True)

    serve = sub.add_parser("serve", help="打开工作台(等价于无参数运行)")
    serve.add_argument("--port", type=int, default=0, help="覆盖 config.json 的 serve_port")
    serve.add_argument("--no-browser", "--no-open", action="store_true", dest="no_browser",
                       help="不自动打开浏览器")
    serve.set_defaults(func=cmd_serve)

    demo = sub.add_parser("demo", help="零密钥 mock 流水线一条命令跑通,出 HTML 报告")
    demo.add_argument("--count", type=int, default=8, help="生成任务条数(默认 8)")
    demo.set_defaults(func=cmd_demo)

    sub.add_parser("doctor", help="本周环境体检").set_defaults(func=cmd_doctor)

    scripts = sub.add_parser("scripts", help="按产品信息生成一批视频脚本")
    scripts.add_argument("--count", type=int, default=8, help="生成任务条数(默认 8)")
    scripts.set_defaults(func=cmd_scripts)

    sub.add_parser("prompts", help="把脚本转成视频生成 prompt").set_defaults(func=cmd_prompts)

    submit = sub.add_parser("submit", help="提交视频生成任务")
    submit.add_argument("--provider", default="", choices=["", *pipeline.SUBMITTERS],
                        help="不填则用 config.json 的 video.provider")
    submit.set_defaults(func=cmd_submit)

    sub.add_parser("poll", help="轮询生成结果并回写任务状态").set_defaults(func=cmd_poll)
    sub.add_parser("sync", help="手动把 output/tasks.json 同步到飞书 Base").set_defaults(func=cmd_sync)

    args = parser.parse_args()
    args.func(args)
