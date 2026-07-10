"""子进程封装:全营唯一实现。"""

from __future__ import annotations

import shutil
import subprocess


def command_exists(name: str) -> bool:
    return shutil.which(name) is not None


def run_cmd(args: list[str], timeout: int = 120) -> tuple[int, str]:
    """跑一条命令,返回 (returncode, stdout+stderr)。不抛异常,调用方看码。"""
    result = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", timeout=timeout)
    return result.returncode, (result.stdout or "") + (result.stderr or "")
