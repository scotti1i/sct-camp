# AGENTS.md · product-mining

选品挖掘:海外用户表达 → 需求信号 → 需求地图。改代码前先读仓库根 `AGENTS.md`(硬性约定优先级更高)。

## 跑法

```bash
uv run mining          # 默认入口:打开工作台(学员用;--no-browser 供测试,端口 8708)

# CLI 子命令 = 管线,给 AI agent 和自动化用
uv run mining doctor   # 体检
uv run mining demo     # 零密钥零网络:模拟表达 → output/analysis.json + demo-report.html
uv run mining fetch --keyword "pet hair remover"   # Reddit 公开 JSON(--asin 走 Amazon 差评)
uv run mining analyze  # expressions.jsonl + input/ 手贴原话 → demand-map.html
uv run mining map      # 只重渲染需求地图
uv run mining serve    # 打开工作台(等价于无参数运行)
```

改完代码先跑 `demo`,analysis.json + HTML 都生成才算通过。

## 数据流(单向,一份聚合)

```
mining fetch(urllib)──→ output/expressions.jsonl(逐轮追加)──┐
input/*.md 以「> 」开头的手贴原话 ────────────────────────────┤
data/sample/sample-expressions.json(demo,内容虚构)──────────┴─ signals.extract_signals()
                                                                      │
                                                                      ▼
                                                        output/analysis.json(唯一数据源)
                                                     ┌────────────────┴────────────────┐
                                                     ▼                                 ▼
                                             mapping.write_map                  workbench 页面
                                             需求地图 HTML                      (复用 mapping 片段)
```

## 本项目约定

- 聚类词典/打分只在 `signals.py`;报告和工作台只消费 `analysis.json`,不许各自再算一遍
- 采集只在 `fetch.py`,只用标准库 urllib 打纯公开 JSON;不引 requests/bs4/pandas,不保存 cookie 和登录态
- 报告只用 `camp_report`,工作台只用 `camp_workbench`,页面片段复用 `mapping.py`,不许再写第二套 HTML
- 用户原话是证据,只截断不改写;需求地图里每个机会点必须带原话引用
- 产物一律写 `output/`(gitignored);`data/sample/` 是手写虚构演示数据,只读,不许写入真实数据
- 重爬虫栈(pytrends / Playwright / PRAW)属于进阶,不迁入本项目;去源项目 `选品挖掘/scripts/` 找
- 外部源失败要友好:先解释是风控/网络,再给替代路径(手贴 input/),不许直接抛栈
