"""news-radar:AI 新闻雷达(源列表 → 采集 → 双视角打分 → 今日雷达 → 飞书卡片)。"""

from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[2]
OUTPUT_DIR = PROJECT_DIR / "output"
SOURCES_JSON = PROJECT_DIR / "data" / "sources.json"
SAMPLE_JSON = PROJECT_DIR / "data" / "sample" / "sample-items.json"
PULL_JSON = OUTPUT_DIR / "items.json"
RADAR_JSON = OUTPUT_DIR / "radar.json"
