"""Resend HTTP 调用的唯一入口。

密钥只走 camp_core.secret("RESEND_API_KEY")(环境变量 > 仓库根 .env),
永远不进 config.json / 代码 / git。本项目其他文件不许直接打 api.resend.com。
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from camp_core import secret

API_BASE = "https://api.resend.com"
USER_AGENT = "sct-camp-week05/1.0"
GUIDE = (
    "缺少 RESEND_API_KEY,无法真实发送。申请步骤:\n"
    "  1. 注册 https://resend.com,进入 Dashboard\n"
    "  2. Domains 里添加并验证你自己的发信域名(DNS 手动步骤见本周 README)\n"
    "  3. API Keys → Create API Key,权限只选 Sending access\n"
    "  4. 把 key 写进仓库根 .env:RESEND_API_KEY=re_xxx(参考 .env.example)\n"
    "key 不进 config.json、不进 git、不发群里、不截图。"
)


def api_key() -> str:
    key = secret("RESEND_API_KEY")
    if not key:
        raise SystemExit(GUIDE)
    return key


def send_batch(emails: list[dict[str, Any]], config: dict[str, Any]) -> dict[str, Any]:
    """批量真发。只该被 `week05 send --really` 调用,dry-run 永远不进这里。"""
    key = api_key()
    payload = [_payload(email, config) for email in emails]
    request = urllib.request.Request(
        f"{API_BASE}/emails/batch",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))
        return {"ok": True, "mode": "real", "sent": len(payload), "response": data}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return {"ok": False, "mode": "real", "status": exc.code, "error": body}
    except urllib.error.URLError as exc:
        return {"ok": False, "mode": "real", "error": f"网络错误:{exc.reason}"}


def _payload(email: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    brand = config.get("brand", {})
    resend = config.get("resend", {})
    return {
        "from": resend.get("from_email", ""),
        "to": [email["email"]],
        "reply_to": resend.get("reply_to", ""),
        "subject": email["subject"],
        "html": email["html"],
        "text": email["text"],
        # List-Unsubscribe 头是合规底线,不许去掉
        "headers": {"List-Unsubscribe": f"<{brand.get('unsubscribe_url', '')}>"},
    }
