# AGENTS.md · projects/news-radar

AI 新闻雷达。改代码前先读仓库根 `AGENTS.md`(硬性约定优先级更高)。

## 跑法

```bash
uv run radar           # 默认入口:打开工作台(学员用;--no-browser 供测试,端口 8707)

# CLI 子命令 = 管线,给 AI agent 和自动化用
uv run radar doctor    # 体检
uv run radar demo      # 零密钥零网络:虚构样例 → output/radar.json + demo-report.html
uv run radar fetch     # 真实采集(--limit 3 只拉前 3 个源;外部源偶发超时不是 bug)
uv run radar digest    # 打分最近一轮采集 → daily-report.html
uv run radar send      # 今日雷达 → 飞书卡片(--dry-run 只写 card-preview.json)
uv run radar serve     # 打开工作台(等价于无参数运行)
```

改完代码先跑 `demo`,radar.json + HTML 都生成才算通过。

## 数据流(单向,一份聚合)

```
data/sources.json ─ sources.fetch_all() ─→ output/items.json(最近一轮采集)
data/sample/*.json ──┐                          │
                     └─ rank.rank_items() ←─────┘   双雷达打分(config.profiles)
                              │
                     digest.add_digests()           摘要(规则默认,LLM 可选)
                              │
                              ▼
                     output/radar.json(唯一数据源)
              ┌───────────────┼────────────────┐
              ▼               ▼                ▼
     digest.write_report   workbench.py     cli.cmd_send
     HTML 日报             工作台页面        digest.build_card → camp_lark
```

## 本项目约定

- 打分/难度/筛选只在 `rank.py`,摘要/日报/卡片只在 `digest.py`,都只消费上游产出,不许各自再算一遍
- 采集只在 `sources.py`,只拉公开 RSS/Atom 和 GitHub 公开搜索;单源失败进 errors,不许拖垮整轮
- 双视角不许写死:关键词、门槛、加成全部走 `config.json` 的 `profiles`
- 摘要 LLM 是可选腿:没有 `LLM_API_KEY` 必须照样出报告(纯规则),LLM 调用失败必须静默退回规则
- 发飞书只走 `camp_lark.send_card`;工作台只用 `camp_workbench.Workbench`
- 产物一律写 `output/`(gitignored);`data/sample/` 是手写虚构数据,只读
- yt-dlp 播放量采集、抖音/RSSHub 源、多种发送通道属于进阶,不迁入本项目;见 README「进阶」
