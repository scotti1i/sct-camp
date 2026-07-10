"""Week 5:AI 邮件增长工作台(合规触达,dry-run 优先)。"""

from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[2]
OUTPUT_DIR = PROJECT_DIR / "output"
EMAILS_JSON = OUTPUT_DIR / "emails.json"
SUMMARY_JSON = OUTPUT_DIR / "summary.json"
SEND_LOG = OUTPUT_DIR / "send-log.jsonl"
