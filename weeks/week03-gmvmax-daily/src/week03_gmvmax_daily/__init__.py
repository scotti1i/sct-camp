"""week03:GMV Max 投流诊断日报机器人(分析 → 模块图 → 飞书卡片)。"""

from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[2]
OUTPUT_DIR = PROJECT_DIR / "output"
SAMPLE_ADS = PROJECT_DIR / "data" / "sample" / "gmv-max-ads-export-sanitized.csv"
SAMPLE_SETTINGS = PROJECT_DIR / "data" / "sample" / "gmv-max-settings-sanitized.csv"
ANALYSIS_JSON = OUTPUT_DIR / "analysis.json"
MANIFEST_JSON = OUTPUT_DIR / "module-manifest.json"
