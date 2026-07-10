"""week04 命令行:TikTok 竞品视频监控。

子命令:
  demo    零密钥零网络:自带演示快照 → 打分 → output/demo-report.html
  doctor  体检本周依赖(yt-dlp / ffmpeg / Pillow / 演示数据)
  fetch   真实采集:config.json 的竞品账号 → output/snapshots.jsonl(追加一轮)
  analyze 打分最近一轮快照 → output/analysis.json + daily-report.html
  serve   本地看板:/ 最新分析结果,/videos 视频清单
  sync    命中视频写进飞书 Base(缺表自动建,字段结构与源项目一致)
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from camp_core import append_jsonl, load_config, now_iso, read_json, write_json
from camp_core.doctor import Check, core_checks, run_checks
from camp_core.proc import command_exists
from camp_lark import lark_cli
from camp_workbench import Workbench

from week04_competitor_watch.core import build_analysis
from week04_competitor_watch.fetch import FRIENDLY_HINT, fetch_all
from week04_competitor_watch.reports import actions_table, overview_card, videos_table, write_report

PROJECT_DIR = Path(__file__).resolve().parents[2]
OUTPUT_DIR = PROJECT_DIR / "output"
SAMPLE_JSON = PROJECT_DIR / "data" / "sample" / "sample-snapshots.json"
SNAPSHOTS_JSONL = OUTPUT_DIR / "snapshots.jsonl"
ANALYSIS_JSON = OUTPUT_DIR / "analysis.json"

# 与源项目 tm_feishu.feishu_fields 完全一致,不要增删改名(老学员的 Base 靠它对齐)
FEISHU_FIELDS = [
    "采集ID", "视频ID", "账号", "标题", "封面", "视频链接", "发布时间",
    "播放", "点赞", "评论", "转发", "收藏", "互动率", "优先级",
    "素材类型", "建议动作", "视频文件", "关键帧目录", "脚本文件",
    "发布期限", "文案复制", "同步时间",
]
_NUMBER_FIELDS = {"播放", "点赞", "评论", "转发", "收藏", "互动率", "优先级"}


def _read_snapshot_lines(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def _run_analysis(snapshots: list[dict[str, Any]], config: dict[str, Any],
                  report_name: str, source_label: str) -> dict[str, Any]:
    """打分 + 落盘,demo/analyze 共用的唯一入口。"""
    analysis = build_analysis(snapshots, config, source_label)
    write_json(ANALYSIS_JSON, analysis)
    report_path = write_report(analysis, OUTPUT_DIR / report_name)
    print(f"OK analysis={ANALYSIS_JSON}")
    print(f"OK report={report_path}")
    print(f"OK 视频 {analysis['video_count']} 条,命中规则 {analysis['matched_count']} 条,"
          f"进拆解清单 {len(analysis['actions'])} 条")
    return analysis


# ---------- 子命令 ----------

def cmd_demo(_: argparse.Namespace) -> None:
    config = load_config(PROJECT_DIR)
    sample = read_json(SAMPLE_JSON, {})
    snapshots = sample.get("snapshots", [])
    if not snapshots:
        raise SystemExit(f"演示数据缺失:{SAMPLE_JSON}(试试 git checkout weeks/week04-competitor-watch/data/sample)")
    _run_analysis(snapshots, config, "demo-report.html", "data/sample 演示数据(数字虚构)")
    print("OK demo 完成。看板:uv run week04 serve;真实采集:uv run week04 fetch")


def week_checks() -> list[Check]:
    def importable(name: str) -> tuple[bool, str]:
        try:
            __import__(name)
            return True, ""
        except ImportError:
            return False, "在仓库根运行 uv sync"

    return [
        Check("yt-dlp 可用(采集元数据)", lambda: (command_exists("yt-dlp"), "在仓库根运行 uv sync(yt-dlp 是本周依赖)")),
        Check("ffmpeg 已安装(进阶下载视频/抽帧才需要)", lambda: (command_exists("ffmpeg"), "brew install ffmpeg;只跑元数据采集可忽略")),
        Check("Pillow 可用(进阶抽帧拼图需要)", lambda: importable("PIL")),
        Check("演示数据在位(demo 需要)", lambda: (SAMPLE_JSON.exists(), "git checkout weeks/week04-competitor-watch/data/sample")),
    ]


def cmd_doctor(_: argparse.Namespace) -> None:
    ok = run_checks(core_checks() + week_checks())
    print("week04 环境全绿。" if ok else "按 [FIX] 提示逐条修复后重跑。")
    raise SystemExit(0 if ok else 1)


def cmd_fetch(_: argparse.Namespace) -> None:
    config = load_config(PROJECT_DIR)
    sources = [row for row in config.get("sources", []) if str(row.get("handle") or "").strip()]
    if not sources:
        raise SystemExit("config.json 的 sources 是空的:先填几个竞品账号(handle 不带 @)")
    videos, errors = fetch_all(sources, config)
    for error in errors:
        print(f"WARN @{error['handle']}: {error['hint']}")
    if not videos:
        raise SystemExit(f"这一轮一条都没拿到。{FRIENDLY_HINT}")
    append_jsonl(SNAPSHOTS_JSONL, videos)
    print(f"OK fetch {len(sources)} 个账号,{len(videos)} 条视频 → {SNAPSHOTS_JSONL}")
    print("下一步:uv run week04 analyze")


def cmd_analyze(_: argparse.Namespace) -> None:
    config = load_config(PROJECT_DIR)
    snapshots = _read_snapshot_lines(SNAPSHOTS_JSONL)
    if not snapshots:
        raise SystemExit(f"缺少 {SNAPSHOTS_JSONL}:先跑 uv run week04 fetch(或先用 demo 看效果)")
    _run_analysis(snapshots, config, "daily-report.html", "output/snapshots.jsonl 真实采集")


def cmd_serve(args: argparse.Namespace) -> None:
    config = load_config(PROJECT_DIR)
    port = args.port or int(config.get("serve_port") or 8784)
    wb = Workbench("Week 4 · TikTok 竞品监控")
    nav = '<p><a href="/">最新分析</a> · <a href="/videos">视频清单</a></p>'
    empty = "<p>还没有分析结果:先跑 uv run week04 demo(或 fetch + analyze),刷新本页即可。</p>"

    @wb.route("/")
    def home(_: dict) -> str:
        analysis = read_json(ANALYSIS_JSON)
        if not analysis:
            return nav + empty
        return nav + overview_card(analysis) + "<h2>优先拆解(按优先级排序)</h2>" + actions_table(analysis)

    @wb.route("/videos")
    def videos(_: dict) -> str:
        analysis = read_json(ANALYSIS_JSON)
        if not analysis:
            return nav + empty
        return nav + "<h2>本轮视频清单</h2>" + videos_table(analysis.get("videos", []))

    wb.serve(port=port, open_browser=not args.no_browser)


# ---------- 飞书同步 ----------

def _field_specs() -> list[dict[str, str]]:
    return [{"name": name, "type": "number" if name in _NUMBER_FIELDS else "text"} for name in FEISHU_FIELDS]


def _feishu_rows(analysis: dict[str, Any]) -> list[list[Any]]:
    rows = []
    for row in analysis.get("actions", []):
        rows.append([
            analysis.get("generated_at", ""), row.get("video_id", ""), row.get("handle", ""),
            row.get("title", ""), row.get("thumbnail_url", ""), row.get("webpage_url", ""),
            row.get("published_at", ""),
            row.get("view_count", 0), row.get("like_count", 0), row.get("comment_count", 0),
            row.get("share_count", 0), row.get("save_count", 0),
            row.get("engagement_rate", 0), row.get("priority_score", 0),
            row.get("format_guess", ""), row.get("suggested_action", ""),
            "", "", "",  # 视频文件 / 关键帧目录 / 脚本文件:进阶功能,见 README
            row.get("publish_deadline", ""), row.get("copy_text", ""), now_iso(),
        ])
    return rows


def _ensure_base(config: dict[str, Any]) -> tuple[str, str]:
    """已配置就直接用;没配置就建 Base + 数据表,并回填 config.json。"""
    feishu = config.get("feishu", {})
    if feishu.get("base_token") and feishu.get("table_id"):
        return str(feishu["base_token"]), str(feishu["table_id"])
    name = f"Week4 TikTok 竞品素材库 {datetime.now().strftime('%Y%m%d-%H%M')}"
    base = lark_cli(["base", "+base-create", "--name", name, "--time-zone", "Asia/Shanghai", "--as", "user", "--json"])
    base_data = base.get("data", {}).get("base", {})
    base_token = base_data.get("base_token") or base_data.get("app_token") or base_data.get("token") or ""
    if not base_token:
        raise SystemExit(f"Base 创建成功但没有返回 base_token:{base}")
    table = lark_cli([
        "base", "+table-create", "--base-token", base_token, "--name", "竞品视频素材",
        "--fields", json.dumps(_field_specs(), ensure_ascii=False), "--as", "user", "--json",
    ])
    table_data = table.get("data", {}).get("table", {})
    table_id = str(table_data.get("table_id") or table_data.get("id") or "")
    config_path = PROJECT_DIR / "config.json"
    saved = read_json(config_path, {})
    saved.setdefault("feishu", {}).update({
        "base_token": base_token, "table_id": table_id, "base_url": base_data.get("url", ""),
    })
    write_json(config_path, saved)
    print(f"OK 已创建飞书 Base:{base_data.get('url') or base_token} table={table_id}(已回填 config.json)")
    return base_token, table_id


def cmd_sync(_: argparse.Namespace) -> None:
    config = load_config(PROJECT_DIR)
    analysis = read_json(ANALYSIS_JSON)
    if not analysis:
        raise SystemExit(f"缺少 {ANALYSIS_JSON}:先跑 uv run week04 demo(或 fetch + analyze)")
    rows = _feishu_rows(analysis)
    if not rows:
        raise SystemExit("本轮没有命中规则的视频,没有可同步的记录;放宽 config.json 的 rules 再试")
    base_token, table_id = _ensure_base(config)
    payload = {"fields": FEISHU_FIELDS, "rows": rows}
    response = lark_cli([
        "base", "+record-batch-create", "--base-token", base_token, "--table-id", table_id,
        "--json", json.dumps(payload, ensure_ascii=False), "--as", "user", "--format", "json",
    ])
    write_json(OUTPUT_DIR / "sync-result.json", {"records": len(rows), "response": response.get("data", {})})
    print(f"OK sync {len(rows)} 条记录 → 飞书 Base,回执见 {OUTPUT_DIR / 'sync-result.json'}")


# ---------- 入口 ----------

def main() -> None:
    parser = argparse.ArgumentParser(prog="week04", description="TikTok 竞品视频监控")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("demo", help="零密钥跑通:演示快照 → 打分 → HTML 日报").set_defaults(func=cmd_demo)
    sub.add_parser("doctor", help="体检本周依赖").set_defaults(func=cmd_doctor)
    sub.add_parser("fetch", help="yt-dlp 采集竞品账号最新公开视频元数据").set_defaults(func=cmd_fetch)
    sub.add_parser("analyze", help="打分最近一轮快照并生成日报").set_defaults(func=cmd_analyze)
    serve = sub.add_parser("serve", help="本地看板(/ 分析结果,/videos 视频清单)")
    serve.add_argument("--port", type=int, default=0, help="覆盖 config.json 的 serve_port")
    serve.add_argument("--no-browser", action="store_true", help="不自动打开浏览器")
    serve.set_defaults(func=cmd_serve)
    sub.add_parser("sync", help="命中视频写进飞书 Base(缺表自动建)").set_defaults(func=cmd_sync)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
