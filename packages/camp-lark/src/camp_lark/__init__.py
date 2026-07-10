"""camp-lark:全营发飞书只从这扇门走。

两条腿,一个门面:
- lark-cli 装了 → 子进程调 lark-cli(用户授权,能力全)
- 没装      → OpenAPI REST 兜底(需要 .env 里 FEISHU_APP_ID / FEISHU_APP_SECRET)

严禁在周项目里自己写 urllib 打 open.feishu.cn,历史上写了三套,坑都在这修过一遍。
"""

from camp_lark.bridge import lark_cli, send_card, send_text, upload_image

__all__ = ["lark_cli", "send_text", "send_card", "upload_image"]
