# AGENTS.md · week02-video-factory

批量 AI 视频工厂:一批任务从产品信息推进到「脚本 → 分镜 prompt → 提交生成 → 结果回收 → 写回飞书 Base」。
仓库总约定见根目录 AGENTS.md,本文件只写本周专属。

## 输入 / 产出

- 输入:`config.json` 的 `product` 区块(首跑自动从 `config.example.json` 生成)
- 产出:全部写本项目 `output/`(已 gitignore)
  - `tasks.json` —— 任务全量状态,状态机见 `pipeline.STATUSES`
  - `demo-report.html` —— demo 结果报告(camp_report 渲染)
  - `base_state.json` / `base_records.json` —— 飞书 Base 同步状态与 record 映射

## 跑法

```bash
uv run week02           # 默认入口:打开工作台(学员用;--no-browser 供测试,端口 8702)

# CLI 子命令 = 管线,给 AI agent 和自动化用
uv run week02 demo      # 零密钥 mock 流水线一条命令跑通(改代码后先跑这个)
uv run week02 doctor    # 本周环境体检

# 单步执行(真实运行走这条链)
uv run week02 scripts --count 8
uv run week02 prompts
uv run week02 submit --provider mock|web_manual|dreamina|video_api
uv run week02 poll
uv run week02 sync      # 手动同步 output/tasks.json 到飞书 Base
```

## 代码地图

- `cli.py` —— 入口:无参数开工作台,子命令走管线
- `workbench.py` —— 工作台页面(总览/任务表/报告直出)与 `run_demo`(CLI 与页面共用)
- `pipeline.py` —— 状态机、脚本/prompt 生成、Base 同步(只走 `camp_lark`)
- `providers.py` —— provider 适配层;新增 provider 在这里加 submit/poll 并注册 `SUBMITTERS`

## 默认工作流(agent 必读)

1. 先跑 `uv run week02 demo`,确认链路和 `output/tasks.json` 正常。
2. 再启用飞书 Base 写回(复制 Base 模板 → 填 `base.base_token` → `base.enabled: true`)。
3. 最后才接 `dreamina` 或 `video_api` 真实生成;批量提交前先小批量验证。

## 红线

- 密钥只放仓库根 `.env`(如 `VIDEO_API_KEY`),严禁写进 `config.json` 或代码。
- 发飞书只 import `camp_lark`,禁止自己打 open.feishu.cn。
- Base 模板 token 不是你的 `base_token`;必须先复制模板再取自己 Base 的 token。
- Base 写回失败不阻塞:本地 JSON 模式必须能独立跑完整链路。

## 验收命令

```bash
cd <仓库根> && uv sync
uv run week02 doctor
uv run week02 demo    # output/ 出 tasks.json + demo-report.html 即通过
```
