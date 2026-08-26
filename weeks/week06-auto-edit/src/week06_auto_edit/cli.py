"""week06 命令行:自动视频剪辑流水线。

不带参数 = 打开工作台(浏览器点按钮,不用看终端)。子命令给 AI agent 和想看清每一步的人:
  demo     零密钥零 ffmpeg:占位素材 → mock 打标 → 话术 → 分镜表 + subs.ass + 流程报告
  doctor   体检本周依赖(ffmpeg / 中文字体 / Pillow / edge-tts / LLM 密钥状态)
  analyze  扫描 input/assets/ → output/assets.json
  label    视觉模型自动打标(需 LLM 密钥;不打就手写 note)
  script   话术 + 分镜(--mock 零密钥;--script 接外部话术)
  voice    配音(edge-tts 免费;--voice 换声音)
  render   出口①:ffmpeg 成片 output/final.mp4
  jianying 出口②:剪映草稿(可编辑文本轨)
  serve    工作台(同不带参数)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from camp_core import load_config, secret
from camp_core.doctor import Check, core_checks, run_checks
from camp_core.proc import command_exists

from week06_auto_edit import demo, llm, workbench
from week06_auto_edit.base import ASSETS_DIR, PROJECT_DIR, find_font
from week06_auto_edit.steps import analyze, jianying, label, render, script, voice


# ---------- 子命令 ----------

def cmd_demo(_: argparse.Namespace) -> None:
    demo.run_demo(load_config(PROJECT_DIR))


def week_checks() -> list[Check]:
    def importable(name: str) -> tuple[bool, str]:
        try:
            __import__(name)
            return True, ""
        except ImportError:
            return False, "在仓库根运行 uv sync"

    return [
        Check("Pillow 可用(画字幕/占位帧)", lambda: importable("PIL")),
        Check("edge-tts 可用(免费配音)", lambda: importable("edge_tts")),
        Check("ffmpeg 已安装(切片/成片需要,demo 不需要)",
              lambda: (command_exists("ffmpeg"),
                       "Mac: brew install ffmpeg / Windows: winget install ffmpeg(装完重开终端)")),
        Check("ffprobe 已安装(读素材元数据,随 ffmpeg 一起装)",
              lambda: (command_exists("ffprobe"), "同上,ffmpeg 装好就有")),
        Check("中文字体可用(字幕/占位帧不出豆腐块)",
              lambda: (bool(find_font()),
                       "config.json 的 font_paths 填一个中文字体路径,如 /System/Library/Fonts/PingFang.ttc")),
    ]


def cmd_doctor(_: argparse.Namespace) -> None:
    checks = [check for check in core_checks() if "lark-cli" not in check.label]
    ok = run_checks(checks + week_checks())
    llm_state = "已配置" if llm.have_llm() else "未配置(demo/--mock 不需要;自动打标和 AI 话术需要,填仓库根 .env)"
    print(f"[i]  LLM_API_KEY / LLM_BASE_URL:{llm_state}")
    tts_state = "已配置" if secret("TTS_API_KEY") else "未配置(默认 edge-tts 免费,不需要)"
    print(f"[i]  TTS_API_KEY / TTS_BASE_URL:{tts_state}")
    try:
        import pyJianYingDraft  # noqa: F401
        print("[i]  pyJianYingDraft:已安装(剪映草稿出口可用)")
    except ImportError:
        print("[i]  pyJianYingDraft:未安装(仅剪映出口需要;uv pip install pyjianyingdraft)")
    assets = list(ASSETS_DIR.glob("*")) if ASSETS_DIR.is_dir() else []
    print(f"[i]  input/assets/:{len(assets)} 个文件(demo 不需要;真实流程放 5-8 段产品片段)")
    print("week06 环境全绿。" if ok else "按 [FIX] 提示逐条修复后重跑(只跑 demo 可以无视 ffmpeg/字体)。")
    raise SystemExit(0 if ok else 1)


def cmd_analyze(_: argparse.Namespace) -> None:
    load_config(PROJECT_DIR)  # 确保 config.json 就位(缺失自动从模板复制)
    analyze.scan_assets()


def cmd_label(args: argparse.Namespace) -> None:
    label.label_assets(load_config(PROJECT_DIR), force=args.force)


def cmd_script(args: argparse.Namespace) -> None:
    external = Path(args.script).expanduser() if args.script else None
    script.run(load_config(PROJECT_DIR), mock=args.mock, external=external)


def cmd_voice(args: argparse.Namespace) -> None:
    voice.synth_all(load_config(PROJECT_DIR), voice_override=args.voice)


def cmd_render(_: argparse.Namespace) -> None:
    render.render(load_config(PROJECT_DIR))


def cmd_jianying(_: argparse.Namespace) -> None:
    jianying.export_draft(load_config(PROJECT_DIR))


def cmd_serve(args: argparse.Namespace) -> None:
    config = load_config(PROJECT_DIR)
    port = args.port or int(config.get("serve_port") or 8706)
    workbench.serve(config, port, open_browser=not args.no_browser)


# ---------- 入口 ----------

def main() -> None:
    parser = argparse.ArgumentParser(prog="week06", description="自动视频剪辑流水线(素材 → 成片/剪映草稿)")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("demo", help="零密钥零 ffmpeg:占位素材 → 分镜表 + 字幕 + 流程报告").set_defaults(func=cmd_demo)
    sub.add_parser("doctor", help="体检本周依赖").set_defaults(func=cmd_doctor)
    sub.add_parser("analyze", help="扫描 input/assets/ 生成素材清单").set_defaults(func=cmd_analyze)

    label_cmd = sub.add_parser("label", help="视觉模型自动打标(需 .env 的 LLM 密钥)")
    label_cmd.add_argument("--force", action="store_true", help="覆盖重打(手工 note 也会被覆盖)")
    label_cmd.set_defaults(func=cmd_label)

    script_cmd = sub.add_parser("script", help="话术 + 分镜 → script.json + storyboard.json")
    script_cmd.add_argument("--mock", action="store_true", help="不调 AI:内置话术模板 + 规则匹配")
    script_cmd.add_argument("--script", default="", help="外部话术 JSON(如 Week2 产物),只跑镜头匹配")
    script_cmd.set_defaults(func=cmd_script)

    voice_cmd = sub.add_parser("voice", help="配音:storyboard 每段口播 → mp3")
    voice_cmd.add_argument("--voice", default="", help="临时换声音,如 zh-CN-YunxiNeural")
    voice_cmd.set_defaults(func=cmd_voice)

    sub.add_parser("render", help="出口①:ffmpeg 成片 output/final.mp4").set_defaults(func=cmd_render)
    sub.add_parser("jianying", help="出口②:剪映草稿(可编辑文本轨)").set_defaults(func=cmd_jianying)

    serve = sub.add_parser("serve", help="工作台(不带参数默认就是它)")
    serve.add_argument("--port", type=int, default=0, help="默认取 config.json 的 serve_port(8706)")
    serve.add_argument("--no-browser", "--no-open", action="store_true", dest="no_browser", help="不自动打开浏览器")
    serve.set_defaults(func=cmd_serve)

    argv = sys.argv[1:] or ["serve"]
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
