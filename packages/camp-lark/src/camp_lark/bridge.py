"""飞书桥:lark-cli 优先,OpenAPI REST 兜底。只用标准库。"""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path
from typing import Any
from uuid import uuid4

from camp_core import command_exists, run_cmd, secret

OPEN_API = "https://open.feishu.cn/open-apis"


# ---------- lark-cli 腿 ----------

def lark_cli(args: list[str], timeout: int = 240) -> dict[str, Any]:
    """调 lark-cli 并解析 JSON 输出。调用方保证传了 --json。"""
    code, output = run_cmd(["lark-cli", *args], timeout=timeout)
    if code != 0:
        raise RuntimeError(f"lark-cli 失败: {output[-800:]}")
    start = output.find("{")
    if start < 0:
        raise RuntimeError(f"lark-cli 没有返回 JSON: {output[-300:]}")
    return json.loads(output[start:])


# ---------- REST 腿(无 lark-cli 时兜底) ----------

def _post(url: str, payload: dict[str, Any], token: str = "") -> dict[str, Any]:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    if data.get("code") not in (0, None):
        raise RuntimeError(f"飞书 API 错误 {data.get('code')}: {data.get('msg')}")
    return data


def _tenant_token() -> str:
    app_id = secret("FEISHU_APP_ID", required=True)
    app_secret = secret("FEISHU_APP_SECRET", required=True)
    data = _post(
        f"{OPEN_API}/auth/v3/tenant_access_token/internal",
        {"app_id": app_id, "app_secret": app_secret},
    )
    return data["tenant_access_token"]


def _send_message(chat_id: str, msg_type: str, content: dict[str, Any]) -> dict[str, Any]:
    if command_exists("lark-cli"):
        return lark_cli([
            "im", "+message-send", "--receive-id", chat_id, "--receive-id-type", "chat_id",
            "--msg-type", msg_type, "--content", json.dumps(content, ensure_ascii=False),
            "--uuid", str(uuid4()), "--json",
        ])
    token = _tenant_token()
    return _post(
        f"{OPEN_API}/im/v1/messages?receive_id_type=chat_id",
        {"receive_id": chat_id, "msg_type": msg_type, "content": json.dumps(content, ensure_ascii=False)},
        token,
    )


# ---------- 门面 ----------

def send_text(chat_id: str, text: str) -> dict[str, Any]:
    return _send_message(chat_id, "text", {"text": text})


def send_card(chat_id: str, card: dict[str, Any]) -> dict[str, Any]:
    return _send_message(chat_id, "interactive", card)


def upload_image(path: Path) -> str:
    """上传图片,返回 image_key(卡片里引用)。REST 腿实现;lark-cli 暂无对应命令。"""
    token = _tenant_token()
    boundary = f"----camp{uuid4().hex}"
    body = (
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"image_type\"\r\n\r\nmessage\r\n"
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"image\"; filename=\"{path.name}\"\r\n"
        f"Content-Type: application/octet-stream\r\n\r\n"
    ).encode() + path.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(
        f"{OPEN_API}/im/v1/images",
        data=body,
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Authorization": f"Bearer {token}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    if data.get("code") != 0:
        raise RuntimeError(f"图片上传失败: {data.get('msg')}")
    return data["data"]["image_key"]
