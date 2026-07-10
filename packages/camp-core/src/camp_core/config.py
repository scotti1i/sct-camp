"""配置与密钥:一个约定,全营通用。

配置 = 项目目录的 config.json(缺失自动从 config.example.json 复制,复制即能跑 demo)。
密钥 = 环境变量 > 仓库根 .env。密钥永远不进 config.json,也永远不进 git。
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any

from camp_core.io import read_json
from camp_core.paths import repo_root


def load_config(project_dir: Path) -> dict[str, Any]:
    config = project_dir / "config.json"
    example = project_dir / "config.example.json"
    if not config.exists():
        if not example.exists():
            raise SystemExit(f"缺少配置模板: {example}")
        shutil.copyfile(example, config)
        print(f"[camp] 已从模板生成 {config.name},demo 模式可直接跑;真实运行前请按 README 填写")
    return read_json(config, {})


def _dotenv() -> dict[str, str]:
    path = repo_root() / ".env"
    data: dict[str, str] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                data[key.strip()] = value.strip()
    return data


def secret(name: str, required: bool = False) -> str:
    """取密钥:环境变量优先,仓库根 .env 兜底。"""
    value = os.environ.get(name, "").strip() or _dotenv().get(name, "")
    if required and not value:
        raise SystemExit(f"缺少密钥 {name}:请写入仓库根 .env(参考 .env.example),不要写进 config.json")
    return value
