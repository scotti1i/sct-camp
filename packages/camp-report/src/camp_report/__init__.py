"""camp-report:工具产出的 HTML 报告都从这里渲染,一个模板,一个长相。"""

from camp_report.html import kv_card, page, save_report, table

__all__ = ["page", "table", "kv_card", "save_report"]
