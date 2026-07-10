"""`uv run camp <子命令>`:营地总入口。

camp doctor  —— 基础环境体检(各周项目另有 `uv run weekNN doctor` 查本周专属依赖)
camp info    —— 仓库根、workspace 目录、已装周项目一览
"""

from __future__ import annotations

import sys

from camp_core.doctor import core_checks, run_checks
from camp_core.paths import repo_root, workspace_dir


def _info() -> None:
    root = repo_root()
    weeks = sorted(p.name for p in (root / "weeks").iterdir() if p.is_dir())
    print(f"仓库根: {root}")
    print(f"产出目录: {workspace_dir()}")
    print(f"周项目: {', '.join(weeks) if weeks else '(尚未安装)'}")


def main() -> None:
    command = sys.argv[1] if len(sys.argv) > 1 else "doctor"
    if command == "doctor":
        ok = run_checks(core_checks())
        print("基础环境全绿。" if ok else "按 [FIX] 提示逐条修复后重跑。")
        sys.exit(0 if ok else 1)
    if command == "info":
        _info()
        return
    raise SystemExit(f"未知子命令: {command}(可用:doctor / info)")
