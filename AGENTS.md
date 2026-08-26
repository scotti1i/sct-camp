# AGENTS.md · 仓库总约定

本仓库是 uv workspace monorepo:`packages/` 是共享基座,`weeks/` 是按周直播交付的系统薄壳,
`projects/` 是不按周编号的营内实践项目(news-radar / product-mining)。三者约定完全一致。

## 环境与运行

- 一律用 `uv run <命令>`,不要直接 `python3`、不要 pip install、不要建 venv
- 首次或拉取后:`uv sync`
- 体检:`uv run camp doctor`(全局)/ `uv run <命令> doctor`(单项目;命令见根 README 表)
- 每个项目(weeks/ 与 projects/ 一样)必有 `demo` 子命令:零密钥、用自带样例数据、一条命令出结果。改代码后先跑 demo 验证
- **不带子命令 = 打开工作台**(七个系统统一,端口 8702-8708);子命令是给 AI agent 和自动化用的
- 每个项目都有 `demo` / `doctor` / `serve` 三个通用子命令(2026-08-26 补齐 week02、week03 缺的 serve)
- 停浏览器自弹一律 `--no-browser`,`--no-open` 保留为等价别名(argparse 双名,dest 统一 `no_browser`)

## 硬性约定(违反即 bug)

1. 发飞书只许 import `camp_lark`,禁止自己写 urllib 打 open.feishu.cn
2. 配置读取只许 `camp_core.load_config(project_dir)`;密钥只许 `camp_core.secret(NAME)`
3. HTML 报告只许用 `camp_report`;本地界面只许用 `camp_workbench.Workbench`
4. 密钥永不出现在:config*.json、代码、git、日志输出
5. 产出写项目 `output/`(gitignored)或 `camp_core.workspace_dir()`;不许写仓库其他位置
6. 新项目 = 复制同类目录下最新项目的骨架:pyproject.toml(console script)+ AGENTS.md + README.md + config.example.json + src 布局。
   按周直播交付的进 `weeks/`,不按周编号的进 `projects/`;两处都已在根 pyproject 的 workspace members 里,不用改配置

## 排障顺序

doctor → demo → 看 output/ 里最近一次产物 → 再查代码。外部 API 随机失败(TikTok 503、RSS 超时)不是项目坏了,重试或换 demo 数据源。
