# News Radar · AI 新闻雷达

盯一组 AI 信息源(公开 RSS/Atom + GitHub 高星搜索),每天产出一页「今日雷达」:
采集 → 去重 → **双视角打分** → 每条配一句摘要 → HTML 日报 + 飞书卡片。

核心立场:**雷达不是闻风就报,是替两双眼睛各筛一遍**。同一批内容,
「选题雷达」找增量信息和可拆解项目,「学员雷达」只留能落到业务动作的低门槛内容。
两个视角的关键词、门槛、加成全在 `config.json` 的 `profiles` 里,可以换成你自己的。

## 30 秒跑通(零密钥零网络)

```bash
cd sct-camp
uv sync
uv run radar
```

浏览器自动打开工作台(`http://127.0.0.1:8707`),点「跑一遍 Demo」:
自带虚构样例几秒打分完,「今日雷达」页直接看到两个视角各自的命中清单。全程不用看终端。

CLI 子命令是同一条流水线的管线形态,给 AI agent 和自动化用:

```bash
uv run radar demo
```

产物(都在 `projects/news-radar/output/`,gitignored):

| 产物 | 说明 |
|---|---|
| `demo-report.html` | 一页日报:概览 + 两个视角的命中表(分数/难度/摘要/链接) |
| `radar.json` | 结构化打分结果(日报、工作台、飞书卡片都吃这一份) |

demo 用的是 `data/sample/sample-items.json` 手写演示数据(**内容全部虚构**),
里面故意混了融资新闻、纯 benchmark 新闻和无关内容,可以看到降权词怎么把噪音挡在门外。

## 真实跑一轮

```bash
uv run radar fetch             # 拉全部源 → output/items.json(--limit 3 快速验证)
uv run radar digest            # 双视角打分 + 摘要 → daily-report.html
uv run radar send --dry-run    # 先看 output/card-preview.json
uv run radar send              # 发飞书卡片(config.json 填 feishu.chat_id)
```

- 源列表在 `data/sources.json`:18 个公开 feed + 5 组 GitHub 搜索,全部零密钥。
  加源 = 加一行 `{name, url, tier, bucket}`;YouTube 频道用官方 RSS
  `https://www.youtube.com/feeds/videos.xml?channel_id=...` 即可,不需要 yt-dlp。
- 单个源超时/限流只会记一条 WARN,不影响整轮(Reddit 偶发 429 属正常)。
- 摘要默认纯规则。想要 LLM 摘要:`config.json` 的 `llm` 填 OpenAI 兼容的
  `base_url`/`model`,仓库根 `.env` 加 `LLM_API_KEY=...`,失败自动退回规则。

## 每天自动跑

不需要调度脚本,cron 一行(工作日早上 9 点):

```
0 9 * * 1-5 cd /path/to/sct-camp && uv run radar fetch && uv run radar digest && uv run radar send
```

## 进阶(留在源项目,不迁入)

本项目是营内《AI 新闻自动化机器人》的开源瘦身版,只保留核心链路。
以下能力去源项目找,不建议加回来:

- **YouTube 播放量/评论数采集**(yt-dlp):官方 RSS 只有标题链接;要热度数据得上 yt-dlp,重依赖
- **抖音/X 信息源**(RSSHub):需要自建 RSSHub 实例并维护 cookie,稳定性看实例
- **多种发送通道**(webhook 签名/lark-cli 多 profile):本项目只走 `camp_lark` 一扇门
- **已发历史去重、来源健康度台账**:日更群发场景才需要
