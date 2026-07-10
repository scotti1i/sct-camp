# Week 3 · GMV Max 投流诊断日报机器人

把 TikTok Shop GMV Max 的后台导出表,变成 4 张手机竖版诊断图 + 一页 HTML 日报,一条命令发进飞书群。

核心立场:**日报不是复盘表,是行动单**。低 ROI 不等于关停,先补证据(素材、商品页、ROI Protection),再动预算。

## 30 秒跑通(零密钥)

```bash
cd sct-camp
uv sync
uv run week03 demo
```

产物(都在 `weeks/week03-gmvmax-daily/output/`,gitignored):

| 产物 | 说明 |
|---|---|
| `modules/*.png` | 4 张 1080x1440 手机竖版模块图:KPI 判断 / 趋势 / Top5 计划 / 今日动作 |
| `demo-report.html` | camp-report 一页日报:核心指标 + 建议动作 + 计划诊断 |
| `clean.csv` | 标准化后的明细表(任意后台表头都归一成同一套字段) |
| `analysis.json` | 结构化诊断结果(出图和日报都吃这一份) |
| `module-manifest.json` | 模块图清单,`send` 按它上传发卡 |

## 换成你的真实数据

```bash
uv run week03 analyze --input ~/Downloads/你的GMVMax导出.xlsx --settings 你的settings表.csv
uv run week03 render
```

- 导出表:GMV Max 后台按天导出的 CSV/XLSX,中英文表头都认(见 `analyze.py` 的 ALIASES)
- settings 表(可选):人工维护的 计划名称/目标ROI/阶段/日预算/近7天新增素材数,让判断更准
- 常用路径可以写进 `config.json` 的 `input` / `settings`,之后 `uv run week03 analyze` 不带参数即可

## 发到飞书群

```bash
uv run week03 send            # 读 config.json 的 chat_id
uv run week03 send --chat-id oc_xxx
```

前置条件(二选一,camp-lark 自动择路):

1. 装好并授权 `lark-cli`(`npm install -g @larksuiteoapi/lark-cli`)——发消息走它;
2. 仓库根 `.env` 里配 `FEISHU_APP_ID` / `FEISHU_APP_SECRET`(自建应用,开通 im:message 和图片上传权限)。

注意:**图片上传目前只走 OpenAPI 一条腿**,所以即使装了 lark-cli,`send` 也需要 `.env` 里有应用凭证。

## 子命令一览

| 命令 | 作用 |
|---|---|
| `uv run week03 demo` | 样例数据全链路:分析 → 4 张图 → HTML 日报(不发飞书) |
| `uv run week03 doctor` | 体检:openpyxl / Pillow / 中文字体 / 样例数据 |
| `uv run week03 analyze` | 清洗导出表 → `clean.csv` + `analysis.json` |
| `uv run week03 render` | 按 `analysis.json` 出模块图 + manifest + HTML 日报 |
| `uv run week03 send` | 最近一次模块图卡片 → 飞书群 |

## 常见问题

- **模块图中文变豆腐块**:跑 `uv run week03 doctor` 看字体检查;在 `config.json` 的 `font_paths` 里填一个中文字体路径(如 `/System/Library/Fonts/PingFang.ttc`)。
- **send 报缺 chat_id**:复制出来的 `config.json` 里填内部测试群的 `oc_xxx`。
- **XLSX 读不出来**:确认是后台原始导出(工具会在前 20 行里自动找表头);实在不行先另存为 CSV。
