# AGENTS.md · week03-gmvmax-daily

GMV Max 投流诊断日报机器人。改代码前先读仓库根 `AGENTS.md`(硬性约定优先级更高)。

## 跑法

```bash
uv run week03          # 默认入口:打开工作台(学员用;--no-browser 供测试,端口 8703)

# CLI 子命令 = 管线,给 AI agent 和自动化用
uv run week03 doctor   # 体检
uv run week03 demo     # 零密钥全链路:样例 → output/modules/*.png(4 张)+ demo-report.html
uv run week03 send     # 需要 config.json 的 chat_id;图片上传还需要 .env 的 FEISHU_APP_ID/SECRET
```

改完代码先跑 `demo`,4 张 PNG + HTML 都生成才算通过。

## 数据流(单向,一份聚合)

```
导出表 CSV/XLSX ─┐
                 ├─ analyze.analyze() ─→ analysis.json(唯一数据源)
settings 表 ─────┘                          │
                        ┌───────────────────┤
                        ▼                   ▼
             render.render_modules()   workbench.report_body()
             4 张 PNG + manifest        camp-report HTML + 工作台页面
                        │
                        ▼
                  cli.cmd_send()(camp_lark 上传 + 发卡)
```

## 本项目约定

- 聚合逻辑只在 `analyze.py`,render/report 只消费 `analysis.json`,不许各自再算一遍
- 发飞书只走 `camp_lark`(send_card / upload_image),不许在本项目写任何 REST
- 模块图规格锁定 1080x1440 竖版、4 张;新增模块要同时更新 `render.MODULES` 和 README
- 字体不许硬编码进画图函数:走 `render.find_font()`(config `font_paths` 覆盖 + 系统候选兜底)
- 产物一律写 `output/`(gitignored);`data/sample/` 是脱敏样例,只读,不许写入真实数据
