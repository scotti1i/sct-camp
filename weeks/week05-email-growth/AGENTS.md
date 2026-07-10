# AGENTS.md · week05-email-growth

AI 邮件增长工作台(合规触达,dry-run 优先)。改代码前先读仓库根 `AGENTS.md`(硬性约定优先级更高)。

## 跑法

```bash
uv run week05                           # 默认入口:打开工作台(学员用;--no-browser 供测试,端口 8705)

# CLI 子命令 = 管线,给 AI agent 和自动化用
uv run week05 doctor                    # 体检
uv run week05 demo                      # 零密钥零外发:demo 名单 → output/demo-report.html
uv run week05 send                      # 默认 dry-run,只写 output/send-log.jsonl
uv run week05 send --really --limit 1   # 真发(需 .env 的 RESEND_API_KEY + config 真实退订/地址)
uv run week05 serve --no-open           # 打开工作台(等价于无参数运行)
```

改完代码先跑 `demo`,`output/demo-report.html` 里有全部预览邮件才算通过。

## 数据流(单向,一份数据源)

```
名单 CSV(data/contacts-demo.csv 或 config 的 contacts_csv)
        │  compose.load_contacts(consent 拦截在这里定 status)
        ▼
compose.build_emails ──→ output/emails.json + summary.json(唯一数据源)
        │                         │
        ▼                         ▼
workbench.write_report     cli.cmd_send
(camp-report HTML)          ├─ 默认 dry-run → output/send-log.jsonl
        │                   └─ --really → resend_api.send_batch(先过 hard_blockers)
        ▼
workbench.py(工作台页面:/ 总览,/emails 读 emails.json,/metrics 读 send-log.jsonl)
```

## 本项目约定

- **合规逻辑是灵魂,不许删不许绕**:consent 拦截(`compose.consent_ok`)、退订链接与真实邮寄地址检查(`compose.hard_blockers`)、邮件模板里的退订/地址区块、Resend payload 的 `List-Unsubscribe` 头
- **默认永远 dry-run**:`--really` 是唯一真发开关,不许加"默认真发"的配置项;真发前 `hard_blockers()` 必须为空
- Resend HTTP 只在 `resend_api.py`;密钥只走 `camp_core.secret("RESEND_API_KEY")`,其他文件不许打 api.resend.com
- 界面只走 `camp_workbench.Workbench`,报告只走 `camp_report`;禁止自带 http.server / 手写 HTML 壳
- 邮件生成只在 `compose.py`,cli/serve 只消费 `output/emails.json`,不许各自再渲染一遍
- 产物一律写 `output/`(gitignored);`data/contacts-demo.csv` 全 example.com 脱敏样例,只读
