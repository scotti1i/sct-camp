"""仓库路径定位:任何脚本在任何工作目录下都能找到自己的家。"""

from __future__ import annotations

from pathlib import Path


def repo_root(start: Path | None = None) -> Path:
    """向上找 workspace 根(有 pyproject.toml 且含 [tool.uv.workspace] 的目录)。"""
    current = (start or Path.cwd()).resolve()
    for candidate in [current, *current.parents]:
        marker = candidate / "pyproject.toml"
        if marker.exists() and "[tool.uv.workspace]" in marker.read_text(encoding="utf-8"):
            return candidate
    raise SystemExit("找不到仓库根:请在 sct-camp 仓库目录内运行")


def workspace_dir() -> Path:
    """学员产出目录(gitignored,git pull 永不冲突)。"""
    path = repo_root() / "workspace"
    path.mkdir(exist_ok=True)
    return path
