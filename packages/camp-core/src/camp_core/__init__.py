"""camp-core:全营工具共用的地基,只用标准库。

约定(全仓库唯一,不允许项目自带变体):
- 配置:项目目录 config.json,缺失时自动从 config.example.json 复制
- 密钥:只走环境变量或仓库根 .env,严禁写进 config.json
- 产出:写项目 output/ 或仓库根 workspace/,两者都被 gitignore
"""

from camp_core.config import load_config, secret
from camp_core.io import read_json, write_json, append_jsonl, now_iso
from camp_core.paths import repo_root, workspace_dir
from camp_core.proc import run_cmd, command_exists

__all__ = [
    "load_config",
    "secret",
    "read_json",
    "write_json",
    "append_jsonl",
    "now_iso",
    "repo_root",
    "workspace_dir",
    "run_cmd",
    "command_exists",
]
