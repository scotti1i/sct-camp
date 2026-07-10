"""product-mining:选品挖掘(用户表达 → 需求信号 → 需求地图)。"""

from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[2]
INPUT_DIR = PROJECT_DIR / "input"
OUTPUT_DIR = PROJECT_DIR / "output"
SAMPLE_JSON = PROJECT_DIR / "data" / "sample" / "sample-expressions.json"
EXPRESSIONS_JSONL = OUTPUT_DIR / "expressions.jsonl"
ANALYSIS_JSON = OUTPUT_DIR / "analysis.json"
