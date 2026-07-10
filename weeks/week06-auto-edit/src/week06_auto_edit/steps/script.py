"""③ 决策层:两步出分镜——话术(说什么)→ 镜头匹配(配哪个镜头)。

产物:output/script.json(话术)+ output/storyboard.json(分镜,全流程唯一中枢)。
mock 模式零密钥:内置话术模板 + 规则匹配器,证明流水线的"脑子"不依赖外部服务。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from camp_core import read_json, write_json

from week06_auto_edit import llm
from week06_auto_edit.base import ASSETS_JSON, SCRIPT_JSON, STORYBOARD_JSON

PROMPT_SCRIPT = """你是 TikTok UGC 带货短视频的编剧。根据产品信息写一支 18-30 秒竖屏带货视频的完整话术。

规则:
1. 严格按结构:hook(前3秒抓人)→ pain(痛点)→ feature(卖点,可 1-3 句)→ proof(使用效果)→ cta(行动号召),共 5-8 句
2. 每句 = 一段口播(voiceover,像闺蜜安利,每句 10-16 个字能在 3 秒内念完)+ 一条画面字幕(caption,≤16 字,把最关键的 2-4 个字用星号包住,如 *秒吸收*)
3. 整段话术连起来必须通顺,像一个真人一口气说完
4. 只输出 JSON:
{"script":[{"role":"hook","voiceover":"口播","caption":"字幕含*高亮*"}]}"""

PROMPT_MATCH = """你是剪辑师,给一段已定稿的话术配镜头。

规则:
1. 话术的每一句配一个镜头,只能用镜头库里存在的文件
2. 优先选 roles 标签匹配的镜头(如 hook 句选带 hook 标签的);同一镜头尽量不连续使用,实在不够可复用但换不同截取区间
3. 每句时长 2-4 秒,按口播长度估(每秒约 4 个字);截取区间必须在素材时长内
4. 只输出 JSON:
{"segments":[{"asset":"文件名","in":0.0,"out":2.5,"caption":"原样保留","voiceover":"原样保留","role":"原样保留"}]}"""


def load_assets() -> list[dict[str, Any]]:
    data = read_json(ASSETS_JSON)
    if not data:
        raise SystemExit(f"缺少 {ASSETS_JSON}:先跑 uv run week06 analyze")
    return data["assets"]


def generate_script(config: dict[str, Any], mock: bool, external: Path | None) -> list[dict[str, str]]:
    """第一步:话术。外部话术(如 Week2 产物)> LLM > mock 模板。"""
    if external:
        script = read_json(external)
        if not script or "script" not in script:
            raise SystemExit(f"读不到外部话术:{external}(需要 {{\"script\": [...]}} 结构)")
        print(f"使用外部话术({external},{len(script['script'])} 句),跳过话术生成")
        return script["script"]
    product = config.get("product", {})
    if mock:
        print("mock 模式:使用内置话术模板(没调 AI)")
        return llm.mock_script(product)
    user = (f"产品:{product.get('name', '')}\n"
            f"卖点:{'、'.join(product.get('selling_points', []))}\n"
            f"目标人群:{product.get('audience', '不限')}")
    return llm.chat_json(config, PROMPT_SCRIPT, user)["script"]


def match_storyboard(config: dict[str, Any], script: list[dict[str, str]],
                     assets: list[dict[str, Any]], mock: bool) -> list[dict[str, Any]]:
    """第二步:镜头匹配。LLM 或规则匹配器,结果都过同一个 validate。"""
    if mock:
        board = {"segments": rule_match(script, assets)}
    else:
        shots = "\n".join(
            f"{a['file']} | {a['duration']}秒 | {a['note']} | 适合: {','.join(a.get('roles', []) or ['不限'])}"
            for a in assets
        )
        lines = "\n".join(
            f"{i + 1}. [{s.get('role')}] 口播「{s.get('voiceover')}」 字幕「{s.get('caption')}」"
            for i, s in enumerate(script)
        )
        board = llm.chat_json(config, PROMPT_MATCH,
                              f"话术:\n{lines}\n\n镜头库(文件 | 时长 | 画面 | 适合角色):\n{shots}")
    return validate(board, assets)


def rule_match(script: list[dict[str, str]], assets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """mock 匹配器:roles 命中优先,避免连用同一镜头;复用时换截取区间(每秒 4 字估时长)。"""
    segments = []
    prev_file = ""
    used: dict[str, int] = {}
    for line in script:
        role = line.get("role", "feature")
        pool = [a for a in assets if role in (a.get("roles") or []) and a["file"] != prev_file]
        pool = pool or [a for a in assets if a["file"] != prev_file] or assets
        asset = min(pool, key=lambda a: used.get(a["file"], 0))  # 用得最少的优先
        need = min(max(len(line.get("voiceover", "")) / 4, 2.0), 4.0)
        start = min(used.get(asset["file"], 0) * 1.0, max(asset["duration"] - need, 0.0))
        segments.append({"asset": asset["file"], "in": round(start, 2),
                         "out": round(min(start + need, asset["duration"]), 2),
                         "caption": line.get("caption", ""),
                         "voiceover": line.get("voiceover", ""), "role": role})
        prev_file = asset["file"]
        used[asset["file"]] = used.get(asset["file"], 0) + 1
    return segments


def validate(board: dict[str, Any], assets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """守门:丢弃不存在的素材、超界/过短的区间;有效段不足 3 段直接失败。"""
    by_file = {a["file"]: a for a in assets}
    segments = []
    for seg in board.get("segments", []):
        asset = by_file.get(seg.get("asset"))
        if not asset:
            print(f"  丢弃:素材不存在 {seg.get('asset')}")
            continue
        start = max(0.0, float(seg.get("in", 0)))
        end = min(float(seg.get("out", 0)), asset["duration"])
        if end - start < 0.8:
            print(f"  丢弃:区间太短 {seg.get('asset')} {start}-{end}")
            continue
        segments.append({
            "asset": seg["asset"], "in": round(start, 2), "out": round(end, 2),
            "caption": str(seg.get("caption", ""))[:30],
            "voiceover": str(seg.get("voiceover", "")).strip(),
            "role": seg.get("role", "feature"),
        })
    if len(segments) < 3:
        raise SystemExit("有效分镜不足 3 段:重跑一次,或检查素材描述/素材时长")
    return segments


def write_outputs(config: dict[str, Any], script: list[dict[str, str]],
                  segments: list[dict[str, Any]],
                  script_path: Path = SCRIPT_JSON,
                  board_path: Path = STORYBOARD_JSON) -> dict[str, Any]:
    """script.json + storyboard.json 落盘,打印分镜摘要。"""
    write_json(script_path, {"script": [{
        "role": line.get("role", "feature"),
        "voiceover": line.get("voiceover", ""),
        "caption": line.get("caption", ""),
    } for line in script]})
    board = {"product": config.get("product", {}).get("name", ""), "segments": segments}
    write_json(board_path, board)

    total = sum(s["out"] - s["in"] for s in segments)
    print(f"分镜表(共 {len(segments)} 段 / {total:.1f} 秒):")
    for i, seg in enumerate(segments, 1):
        print(f"  {i}. [{seg['role']:7s}] {seg['asset']} {seg['in']}-{seg['out']}s 「{seg['caption']}」")
    print(f"OK script={script_path}")
    print(f"OK storyboard={board_path}(中枢,可直接改)")
    return board


def run(config: dict[str, Any], mock: bool = False, external: Path | None = None) -> dict[str, Any]:
    """话术 + 分镜一条龙,CLI 的 script 子命令与工作台共用。"""
    assets = load_assets()
    missing = [a["file"] for a in assets if not a.get("note")]
    if missing and not mock:
        raise SystemExit(
            f"这些素材还没有画面描述: {', '.join(missing)}\n"
            "跑 uv run week06 label 自动打标,或手动填 output/assets.json 的 note"
        )
    script = generate_script(config, mock, external)
    for line in script:
        print(f"   [{line.get('role', '?'):7s}]「{line.get('voiceover', '')}」")
    segments = match_storyboard(config, script, assets, mock)
    return write_outputs(config, script, segments)
