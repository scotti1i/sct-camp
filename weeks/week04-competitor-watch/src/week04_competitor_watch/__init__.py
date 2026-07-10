"""week04:TikTok 竞品视频监控(采集 → 打分 → 日报/看板 → 飞书 Base)。"""

from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[2]
OUTPUT_DIR = PROJECT_DIR / "output"
SAMPLE_JSON = PROJECT_DIR / "data" / "sample" / "sample-snapshots.json"
SNAPSHOTS_JSONL = OUTPUT_DIR / "snapshots.jsonl"
ANALYSIS_JSON = OUTPUT_DIR / "analysis.json"
