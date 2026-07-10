"""视频生成 provider 适配层:mock / web_manual / dreamina / video_api。

每个 provider 提供 submit(改任务状态为 生成中/生成失败)与 poll(把 生成中 推到终态)。
新增 provider 只需在这里加一对函数并注册进 SUBMITTERS / 轮询分支。
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

from camp_core import command_exists, run_cmd, secret


def parse_first_json(text: str) -> dict[str, Any]:
    """从 CLI 混合输出里抠出第一个 JSON 对象(dreamina / 视频 API 输出都不保证纯 JSON)。"""
    start = text.find("{")
    if start < 0:
        return {}
    try:
        data, _ = json.JSONDecoder().raw_decode(text[start:])
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _fail(task: dict[str, Any], tool: str, reason: str) -> None:
    task["生成工具"] = tool
    task["状态"] = "生成失败"
    task["失败原因"] = reason


# ==================== 提交 ====================


def submit_mock(task: dict[str, Any], config: dict[str, Any]) -> None:
    task["生成工具"] = "mock"
    task["task_id"] = f"mock-{task['任务编号'].lower()}-{int(time.time())}"
    task["状态"] = "生成中"


def submit_web_manual(task: dict[str, Any], config: dict[str, Any]) -> None:
    task["生成工具"] = "web"
    task["task_id"] = f"web-manual-{task['任务编号'].lower()}"
    task["状态"] = "已生成 prompt"
    task["失败原因"] = "请把分镜 prompt 复制到即梦网页端或其他网页端工具手动生成。"


def submit_dreamina(task: dict[str, Any], config: dict[str, Any]) -> None:
    if not command_exists("dreamina"):
        _fail(task, "dreamina", "未找到 dreamina CLI,请先安装并登录。")
        return
    video = config.get("video", {})
    code, out = run_cmd([
        "dreamina", "text2video",
        "--prompt", task["分镜 prompt"],
        "--duration", str(video.get("default_duration", 10)),
        "--ratio", video.get("aspect_ratio", "9:16"),
        "--model_version", video.get("dreamina_model", "seedance2.0fast"),
        "--poll", str(video.get("poll_seconds", 0)),
    ], timeout=600)
    data = parse_first_json(out)
    task["生成工具"] = "dreamina"
    submit_id = data.get("submit_id") or data.get("id") or ""
    gen_status = data.get("gen_status") or data.get("status") or ""
    fail_reason = data.get("fail_reason") or data.get("error") or ""
    if code != 0 or not submit_id:
        _fail(task, "dreamina", str(fail_reason or out.strip()[:500] or "dreamina 提交失败"))
        return
    task["task_id"] = submit_id
    if gen_status == "success":
        task["状态"] = "生成成功"
    elif gen_status == "fail":
        _fail(task, "dreamina", str(fail_reason or "dreamina 返回 fail"))
    else:
        task["状态"] = "生成中"


def _api_url(endpoint: str, path: str) -> str:
    return urljoin(endpoint.rstrip("/") + "/", path.lstrip("/"))


def video_api_key(api: dict[str, Any]) -> str:
    """真实 key 只从环境变量 / 仓库根 .env 读,永不进 config.json。"""
    return secret(str(api.get("api_key_env", "VIDEO_API_KEY")).strip() or "VIDEO_API_KEY")


def _http_json(request: urllib.request.Request, timeout: int) -> tuple[str, str]:
    """发请求,返回 (正文, 错误信息);两者只有一个非空。"""
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read().decode("utf-8"), ""
    except urllib.error.HTTPError as error:
        return "", f"HTTP {error.code}: {error.read().decode('utf-8', errors='replace')[:500]}"
    except OSError as error:
        return "", f"请求失败: {error}"


def extract_task_id(data: dict[str, Any]) -> str:
    for key in ("task_id", "submit_id", "id"):
        value = data.get(key)
        if isinstance(value, str) and value:
            return value
    for key in ("data", "result"):
        value = data.get(key)
        if isinstance(value, dict):
            nested = extract_task_id(value)
            if nested:
                return nested
    return ""


def submit_video_api(task: dict[str, Any], config: dict[str, Any]) -> None:
    api = config.get("video_api", {})
    endpoint = str(api.get("endpoint", "")).strip()
    submit_path = str(api.get("submit_path", "/v1/videos/generations")).strip()
    model = str(api.get("model", "")).strip()
    api_key = video_api_key(api)
    if not (endpoint and submit_path and model and api_key):
        env = api.get("api_key_env", "VIDEO_API_KEY")
        _fail(task, "video_api", f"video_api 配置不全:endpoint/model 填 config.json,密钥 {env} 填仓库根 .env")
        return
    video = config.get("video", {})
    payload = {
        "model": model,
        "prompt": task["分镜 prompt"],
        "duration": video.get("default_duration", 10),
        "aspect_ratio": video.get("aspect_ratio", "9:16"),
    }
    extra = api.get("extra_payload", {})
    if isinstance(extra, dict):
        payload.update(extra)
    request = urllib.request.Request(
        _api_url(endpoint, submit_path),
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    task["生成工具"] = "video_api"
    text, error = _http_json(request, int(api.get("timeout_seconds", 60)))
    if error:
        _fail(task, "video_api", f"视频 API {error}")
        return
    task_id = extract_task_id(parse_first_json(text))
    if not task_id:
        _fail(task, "video_api", f"视频 API 返回里没有 task_id/submit_id/id: {text[:300]}")
        return
    task["task_id"] = task_id
    task["状态"] = "生成中"


SUBMITTERS = {
    "mock": submit_mock,
    "web_manual": submit_web_manual,
    "dreamina": submit_dreamina,
    "video_api": submit_video_api,
}


# ==================== 轮询 ====================


def extract_video_url(data: dict[str, Any]) -> str:
    for key in ("video_url", "url"):
        if isinstance(data.get(key), str):
            return data[key]
    for container in (data.get("result_json"), data):
        if isinstance(container, dict):
            videos = container.get("videos") or []
            if videos and isinstance(videos[0], dict):
                return videos[0].get("video_url") or videos[0].get("url") or ""
    return ""


def api_status(data: dict[str, Any]) -> str:
    for key in ("status", "gen_status", "state"):
        value = data.get(key)
        if isinstance(value, str):
            return value.lower()
    for key in ("data", "result"):
        value = data.get(key)
        if isinstance(value, dict):
            nested = api_status(value)
            if nested:
                return nested
    return ""


def _poll_mock(task: dict[str, Any], output_dir: Path) -> bool:
    task["状态"] = "生成成功"
    task["视频链接"] = f"https://example.com/mock-videos/{task['任务编号']}.mp4"
    task["本地文件"] = str(output_dir / f"{task['任务编号']}.mp4")
    return True


def _poll_dreamina(task: dict[str, Any], download_dir: Path) -> bool:
    if not command_exists("dreamina"):
        _fail(task, "dreamina", "未找到 dreamina CLI,无法轮询。")
        return False
    download_dir.mkdir(parents=True, exist_ok=True)
    code, out = run_cmd([
        "dreamina", "query_result",
        "--submit_id", task["task_id"],
        "--download_dir", str(download_dir),
    ], timeout=600)
    data = parse_first_json(out)
    gen_status = data.get("gen_status") or data.get("status") or ""
    if code != 0:
        task["失败原因"] = out.strip()[:500]
        return False
    if gen_status == "success":
        task["状态"] = "生成成功"
        task["视频链接"] = extract_video_url(data)
        task["本地文件"] = str(download_dir)
        return True
    if gen_status == "fail":
        _fail(task, "dreamina", str(data.get("fail_reason") or "dreamina 返回 fail"))
    return False


def _poll_video_api(task: dict[str, Any], config: dict[str, Any]) -> bool:
    api = config.get("video_api", {})
    endpoint = str(api.get("endpoint", "")).strip()
    poll_path = str(api.get("poll_path", "")).strip()
    api_key = video_api_key(api)
    if not (endpoint and poll_path and api_key):
        _fail(task, "video_api", "video_api.endpoint / poll_path / 密钥不全,无法轮询")
        return False
    request = urllib.request.Request(
        _api_url(endpoint, poll_path.replace("{task_id}", str(task["task_id"]))),
        headers={"Authorization": f"Bearer {api_key}"},
        method="GET",
    )
    text, error = _http_json(request, int(api.get("timeout_seconds", 60)))
    if error:
        _fail(task, "video_api", f"视频 API {error}")
        return False
    data = parse_first_json(text)
    status = api_status(data)
    if status in ("success", "succeeded", "completed", "done"):
        task["状态"] = "生成成功"
        task["视频链接"] = extract_video_url(data)
        return True
    if status in ("fail", "failed", "error", "cancelled", "canceled"):
        _fail(task, "video_api", str(data.get("error") or data.get("message") or "视频 API 返回失败"))
    return False


def poll_task(task: dict[str, Any], config: dict[str, Any], output_dir: Path, download_dir: Path) -> bool:
    """按任务的生成工具轮询一次,推进到终态则返回 True。"""
    if str(task.get("task_id", "")).startswith("mock-"):
        return _poll_mock(task, output_dir)
    if task.get("生成工具") == "dreamina":
        return _poll_dreamina(task, download_dir)
    if task.get("生成工具") == "video_api":
        return _poll_video_api(task, config)
    return False
