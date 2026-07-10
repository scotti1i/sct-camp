"""Week 2 视频工厂流水线:脚本 → 分镜 prompt → 提交生成 → 轮询结果 → 写回飞书 Base。

状态机与 Base 表结构沿用课程模板,字段名与学员复制的飞书 Base 模板一一对应,不要改名。
provider 细节(mock / dreamina / video_api)在 providers.py。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from camp_core import read_json, write_json, command_exists
from camp_lark import lark_cli

from week02_video_factory.providers import SUBMITTERS, poll_task

PROJECT_DIR = Path(__file__).resolve().parents[2]
OUTPUT_DIR = PROJECT_DIR / "output"
TASKS_FILE = OUTPUT_DIR / "tasks.json"
BASE_STATE_FILE = OUTPUT_DIR / "base_state.json"
BASE_RECORDS_FILE = OUTPUT_DIR / "base_records.json"

# ==================== 状态机与表结构(与飞书 Base 模板一致) ====================

STATUSES = [
    "待生成",
    "已生成脚本",
    "已生成 prompt",
    "已提交",
    "生成中",
    "生成成功",
    "生成失败",
    "已通过",
    "可发布",
]

BASE_TABLES = {
    "产品配置": ["产品名", "目标人群", "核心卖点", "禁止表达", "生成语言", "状态"],
    "参考视频拆解": ["视频链接", "Hook 类型", "主卖点", "脚本结构", "可仿写点", "风险点", "参考价值"],
    "视频生成任务": [
        "任务编号", "产品名", "参考结构", "脚本", "分镜 prompt", "生成工具",
        "状态", "task_id", "视频链接", "本地文件", "失败原因", "重跑次数", "是否最佳",
    ],
    "验收复盘": [
        "任务编号", "视频链接", "画面质量", "产品一致性", "脚本匹配度",
        "是否可发布", "问题记录", "下一轮修改",
    ],
}

TASK_FIELDS = BASE_TABLES["视频生成任务"]

FORMULAS = [
    ("demonstration", "Show the result first, then explain the product."),
    ("pain_point", "Start from a daily frustration, then introduce the product."),
    ("comparison", "Compare the old situation with the improved situation."),
    ("scenario", "Put the product into a real-life use scene."),
    ("reaction", "Use a first-time reaction to make the benefit visible."),
]

# ==================== 任务读写 ====================


def load_tasks() -> list[dict[str, Any]]:
    return read_json(TASKS_FILE, [])


def save_tasks(tasks: list[dict[str, Any]]) -> None:
    write_json(TASKS_FILE, tasks)


# ==================== 脚本与分镜 prompt ====================


def build_script(task_id: int, product: dict[str, Any], formula: tuple[str, str]) -> dict[str, Any]:
    style, structure = formula
    point = product["selling_points"][task_id % len(product["selling_points"])]
    script = " ".join([
        "Still dealing with heat during your day?",
        f"{product['name']} gives {product['audience']} a simple way to get {point}.",
        "Show the product being used in a real commute, office, or outdoor scene.",
        "Check it before your next hot day.",
    ])
    return {
        "任务编号": f"V{task_id + 1:03d}",
        "产品名": product["name"],
        "参考结构": f"{style}: {structure}",
        "脚本": script,
        "分镜 prompt": "",
        "生成工具": "",
        "状态": "已生成脚本",
        "task_id": "",
        "视频链接": "",
        "本地文件": "",
        "失败原因": "",
        "重跑次数": 0,
        "是否最佳": False,
    }


def generate_scripts(config: dict[str, Any], count: int) -> list[dict[str, Any]]:
    product = config["product"]
    tasks = [build_script(i, product, FORMULAS[i % len(FORMULAS)]) for i in range(count)]
    save_tasks(tasks)
    return tasks


def build_prompt(task: dict[str, Any], config: dict[str, Any]) -> str:
    name = config["product"]["name"]
    return f"""Vertical video 9:16. Overall audio atmosphere: upbeat short-form product demo, clear voiceover, clean background music.

[0-3s] Close-up shot in a bright home entryway, white wall, matte plastic product surface, soft daylight from the left. A hand picks up {name} and brings it into frame.
On-screen text: "Too hot?". Voiceover: "Still dealing with heat during your day?"

[3-7s] Cut on the beat to a real commute or office scene. The user puts on or holds {name}, then turns it on with a clear button press. Camera slowly pushes in.
Voiceover: "{task['脚本'][:120]}"

[7-10s] Final shot shows the product being used naturally in daily life. The user relaxes and keeps moving.
Final text: "Stay cool". Voiceover: "Check it before your next hot day."

Style: realistic UGC product video, natural hand movement, no distorted hands, no extra logos, no unreadable long text."""


def generate_prompts(config: dict[str, Any]) -> list[dict[str, Any]]:
    tasks = load_tasks()
    if not tasks:
        raise SystemExit("还没有脚本。请先运行: uv run week02 scripts")
    for task in tasks:
        task["分镜 prompt"] = build_prompt(task, config)
        task["状态"] = "已生成 prompt"
    save_tasks(tasks)
    return tasks


# ==================== 提交与轮询(细节见 providers.py) ====================


def submit_tasks(config: dict[str, Any], provider: str) -> tuple[int, list[dict[str, Any]]]:
    submitter = SUBMITTERS.get(provider)
    if submitter is None:
        raise SystemExit(f"未知 provider: {provider}(可用:{' / '.join(SUBMITTERS)})")
    tasks = load_tasks()
    if not tasks:
        raise SystemExit("还没有任务。请先运行: uv run week02 scripts && uv run week02 prompts")
    submitted = 0
    for task in tasks:
        if task.get("状态") in ("已生成 prompt", "生成失败"):
            submitter(task, config)
            submitted += 1
    save_tasks(tasks)
    return submitted, tasks


def poll_tasks(config: dict[str, Any]) -> tuple[int, list[dict[str, Any]]]:
    tasks = load_tasks()
    if not tasks:
        raise SystemExit("还没有任务。请先运行: uv run week02 demo 或 uv run week02 scripts")
    download_dir = Path(config.get("video", {}).get("download_dir", "output/videos"))
    if not download_dir.is_absolute():
        download_dir = PROJECT_DIR / download_dir
    success = 0
    for task in tasks:
        if task.get("状态") == "生成中":
            success += poll_task(task, config, OUTPUT_DIR, download_dir)
    save_tasks(tasks)
    return success, tasks


# ==================== 飞书 Base 同步(全部走 camp_lark) ====================


def base_enabled(config: dict[str, Any]) -> bool:
    base = config.get("base", {})
    return bool(base.get("enabled") and base.get("base_token") and command_exists("lark-cli"))


def _task_payload(task: dict[str, Any]) -> dict[str, Any]:
    return {field: (None if task.get(field) == "" else task.get(field)) for field in TASK_FIELDS}


def _extract_record_id(data: dict[str, Any]) -> str:
    payload = data.get("data", data)
    record = payload.get("record") or payload.get("data", {}).get("record") or {}
    record_ids = record.get("record_id_list") or []
    if record_ids:
        return record_ids[0]
    return record.get("record_id") or record.get("id") or ""


def _upsert_task(base_token: str, table_name: str, task: dict[str, Any], record_id: str = "") -> str:
    args = [
        "base", "+record-upsert", "--as", "user",
        "--base-token", base_token, "--table-id", table_name,
        "--json", json.dumps(_task_payload(task), ensure_ascii=False),
    ]
    if record_id:
        args += ["--record-id", record_id]
    data = lark_cli(args)
    if not data.get("ok") and data.get("code") not in (0, None):
        raise RuntimeError(json.dumps(data, ensure_ascii=False)[:500])
    return _extract_record_id(data) or record_id


def sync_tasks(config: dict[str, Any], tasks: list[dict[str, Any]]) -> int:
    """把任务表 upsert 到飞书 Base;未启用时静默跳过,失败不打断本地流程。"""
    if not base_enabled(config):
        return 0
    base = config["base"]
    table_name = base.get("tables", {}).get("tasks", "视频生成任务")
    mapping = read_json(BASE_RECORDS_FILE, {})
    synced = 0
    for task in tasks:
        task_no = task["任务编号"]
        try:
            record_id = _upsert_task(base["base_token"], table_name, task, mapping.get(task_no, ""))
        except RuntimeError as exc:
            print(f"[WARN] 飞书 Base 同步失败({task_no}),本地 JSON 不受影响: {str(exc)[:200]}")
            break
        if record_id:
            mapping[task_no] = record_id
        synced += 1
    write_json(BASE_RECORDS_FILE, mapping)
    return synced


def write_base_state(config: dict[str, Any]) -> Path:
    """记录当前 Base 配置与要求的表结构,便于排障。"""
    base = config.get("base", {})
    write_json(BASE_STATE_FILE, {
        "base_enabled": bool(base.get("enabled")),
        "base_token": base.get("base_token", ""),
        "tables": base.get("tables", {}),
        "required_schema": BASE_TABLES,
    })
    return BASE_STATE_FILE
