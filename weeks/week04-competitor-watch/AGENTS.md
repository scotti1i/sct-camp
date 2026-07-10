# AGENTS.md · week04-competitor-watch

TikTok 竞品视频监控。改代码前先读仓库根 `AGENTS.md`(硬性约定优先级更高)。

## 跑法

```bash
uv run week04          # 默认入口:打开工作台(学员用;--no-browser 供测试,端口 8704)

# CLI 子命令 = 管线,给 AI agent 和自动化用
uv run week04 doctor   # 体检
uv run week04 demo     # 零密钥零网络:演示快照 → output/analysis.json + demo-report.html
uv run week04 fetch    # 真实采集(yt-dlp,外部源偶发 503 不是 bug)
uv run week04 analyze  # 打分最近一轮 → daily-report.html
uv run week04 serve    # 打开工作台(等价于无参数运行)
uv run week04 sync     # 命中视频 → 飞书 Base(lark-cli,缺表自动建)
```

改完代码先跑 `demo`,analysis.json + HTML 都生成才算通过。

## 数据流(单向,一份聚合)

```
config.json sources ─ fetch.fetch_all() ─→ output/snapshots.jsonl(逐轮追加)
data/sample/*.json ──┐                          │
                     └── core.build_analysis() ←┘
                              │
                              ▼
                     output/analysis.json(唯一数据源)
              ┌───────────────┼────────────────┐
              ▼               ▼                ▼
     reports.write_report   workbench.py    cli.cmd_sync
     HTML 日报              工作台页面       camp_lark → Base
```

## 本项目约定

- 打分/规则/建议动作只在 `core.py`,报表/看板/同步只消费 `analysis.json`,不许各自再算一遍
- 采集只在 `fetch.py`,只拿公开元数据(--skip-download);不保存 cookie、签名 URL、账号密码
- 发飞书只走 `camp_lark.lark_cli`;`FEISHU_FIELDS` 字段结构与源项目一致,不许增删改名
- 看板只用 `camp_workbench.Workbench`,页面片段复用 `reports.py`,不许再写第二套 HTML
- 外部源失败要友好:先解释 TikTok 503 是外部源问题,再建议重跑或减账号,不许直接抛栈
- 产物一律写 `output/`(gitignored);`data/sample/` 是手写演示数据,只读,不许写入真实数据
- 下载视频/抽帧/whisper 属于进阶,不迁入本项目;去源项目 `scripts/tm_assets.py` 找
