"""doctor 框架:每周项目注册自己的检查项,`uv run camp doctor` 一次查清。

用法(周项目里):
    from camp_core.doctor import Check, run_checks
    CHECKS = [Check("ffmpeg 已安装", lambda: (command_exists("ffmpeg"), "brew install ffmpeg"))]
    run_checks(CHECKS)

每个检查函数返回 (ok, 修复提示)。失败不中断,一次跑完全部,学员照提示逐条修。
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Callable

from camp_core.proc import command_exists


@dataclass
class Check:
    label: str
    probe: Callable[[], tuple[bool, str]]


def run_checks(checks: list[Check]) -> bool:
    """跑一组检查,打印 [OK]/[FIX],返回是否全绿。"""
    all_ok = True
    for check in checks:
        try:
            ok, hint = check.probe()
        except Exception as exc:  # 检查器自身不许把 doctor 搞挂
            ok, hint = False, f"检查器异常: {exc}"
        mark = "[OK] " if ok else "[FIX]"
        line = f"{mark} {check.label}"
        if not ok and hint:
            line += f" → {hint}"
        print(line)
        all_ok = all_ok and ok
    return all_ok


def core_checks() -> list[Check]:
    """全营通用的基础检查。"""
    return [
        Check(
            f"Python {sys.version_info.major}.{sys.version_info.minor}",
            lambda: (sys.version_info >= (3, 12), "由 uv 自动管理,运行 uv sync 即可"),
        ),
        Check("uv 已安装", lambda: (command_exists("uv"), "https://docs.astral.sh/uv/ 一条命令安装")),
        Check(
            "lark-cli 已安装(飞书功能需要)",
            lambda: (command_exists("lark-cli"), "npm install -g @larksuiteoapi/lark-cli;不用飞书可忽略"),
        ),
    ]
