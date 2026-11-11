import argparse
import json
from pathlib import Path
import re


def require(condition, message):
    if not condition:
        raise ValueError(message)


def validate(report, facts):
    expected = {"normal-zh": "draft", "normal-en": "draft", "missing-proof": "needs-evidence"}
    parts = ["opening", "demo", "close"]
    require(isinstance(report, dict) and set(report) == {"cases"}, "Return a cases object")
    cases = report["cases"]
    require(isinstance(cases, list) and len(cases) == len(expected), "Return three cases")
    seen = set()
    for case in cases:
        require(
            isinstance(case, dict) and set(case) == {"case_id", "status", "lines", "missing"},
            "Invalid case fields",
        )
        case_id = case["case_id"]
        require(
            isinstance(case_id, str) and case_id in expected and case_id not in seen,
            "Invalid or duplicate case ID",
        )
        seen.add(case_id)
        require(case["status"] == expected[case_id], f"{case_id}: unexpected status")
        lines = case["lines"]
        if case["status"] == "needs-evidence":
            require(lines == [], f"{case_id}: leave the script empty")
            missing = case["missing"]
            require(
                isinstance(missing, list)
                and len(missing) == 2
                and "load_rating" in missing
                and "offer_end" in missing,
                f"{case_id}: report both missing facts",
            )
            continue
        require(case["missing"] == [], f"{case_id}: a draft has no missing fields")
        require(isinstance(lines, list) and len(lines) == len(parts), f"{case_id}: include three script parts")
        for line, part in zip(lines, parts):
            require(
                isinstance(line, dict) and set(line) == {"part", "text", "shot", "fact_ids"},
                f"{case_id}: invalid line fields",
            )
            require(
                line["part"] == part and all(
                    isinstance(line[field], str) and line[field].strip()
                    for field in ("text", "shot")
                ),
                f"{case_id}: write the {part} line and shot",
            )
            ids = line["fact_ids"]
            require(
                isinstance(ids, list) and ids
                and all(isinstance(item, str) and item in facts for item in ids),
                f"{case_id}: cite approved fact IDs",
            )


def main():
    parser = argparse.ArgumentParser(description="Check the SCTCamp practice JSON structure and references.")
    parser.add_argument("drafts", type=Path)
    args = parser.parse_args()
    product = Path(__file__).resolve().parents[1] / "fixtures" / "product.md"
    facts = set(re.findall(r"^- (F\d+):", product.read_text(encoding="utf-8"), re.MULTILINE))
    try:
        validate(json.loads(args.drafts.read_text(encoding="utf-8")), facts)
    except (OSError, ValueError, TypeError) as error:
        parser.exit(1, f"Check failed: {error}\n")
    print("Three cases passed structural checks. Review the script wording against the product facts.")


if __name__ == "__main__":
    main()
