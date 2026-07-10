# Week 4 · TikTok 竞品视频监控

盯一组竞品 TikTok 账号,把最新公开视频的数据变成一张"今天拆什么"的优先级清单:
采集元数据 → 打分排序 → 一页 HTML 日报 + 本地看板 → 命中视频一键写进飞书 Base。

核心立场:**监控不是存数据,是每天给自己派活**。每条命中视频都带一句可执行的建议动作和发布期限。

## 30 秒跑通(零密钥零网络)

```bash
cd sct-camp
uv sync
uv run week04 demo
```

产物(都在 `weeks/week04-competitor-watch/output/`,gitignored):

| 产物 | 说明 |
|---|---|
| `demo-report.html` | 一页日报:本轮概览 + 优先级排序表(建议动作/发布期限)+ 视频清单 |
| `analysis.json` | 结构化打分结果(日报、看板、飞书同步都吃这一份) |

demo 用的是 `data/sample/sample-snapshots.json` 手写演示数据(数字虚构),其中 4 条视频带前一轮快照,可以看到"播放涨幅"的判断逻辑。

## 打开本地看板

```bash
uv run week04 serve            # http://127.0.0.1:8784
```

- `/` 最新一轮分析结果:概览 + 优先拆解表
- `/videos` 本轮全部视频清单

## 换成你的真实竞品

1. 把 `config.json` 的 `sources` 换成你盯的账号(`handle` 只写用户名,不带 `@`);
2. 采集 + 打分:

```bash
uv run week04 fetch            # yt-dlp 拉最新公开视频元数据,追加到 output/snapshots.jsonl
uv run week04 analyze          # 打分最近一轮 → analysis.json + daily-report.html
```

每天各跑一次,第二天开始就有"播放涨幅"信号(同一视频对比上一轮快照)。

**TikTok 偶发 503 / 超时不是 bug**:是外部源的脾气。fetch 会自动重试 3 次,单账号失败不拖垮整轮;整轮都失败就稍后再跑,或减少账号数。

## 同步到飞书 Base

```bash
uv run week04 sync
```

- 前置条件:装好并授权 `lark-cli`(`npm install -g @larksuiteoapi/lark-cli`);
- `config.json` 的 `feishu` 留空即可:第一次 sync 自动创建「Week4 TikTok 竞品素材库」Base 和数据表,并把 `base_token` / `table_id` 回填 `config.json`;
- 之后每次 sync 都把最近一次分析的命中视频追加成记录(字段结构与源项目一致,老 Base 可以继续用)。

## 打分规则(config.json 的 rules)

| 键 | 作用 |
|---|---|
| `min_views` / `min_engagement_rate` / `min_priority_score` | 硬过滤,不达标不进清单 |
| `min_views_for_priority` / `min_engagement_for_priority` / `comment_signal_threshold` | 优先级加分阈值 |
| `only_new` | 只看本轮新出现的视频 |
| `time_window` | `1d` / `7d` / `30d`,只看这段时间发布的;留空不限 |
| `max_action_items` | 拆解清单最多几条 |

## 子命令一览

| 命令 | 作用 |
|---|---|
| `uv run week04 demo` | 演示数据全链路:打分 → HTML 日报(零密钥零网络) |
| `uv run week04 doctor` | 体检:yt-dlp / ffmpeg / Pillow / 演示数据 |
| `uv run week04 fetch` | 采集竞品账号最新公开视频元数据(追加一轮快照) |
| `uv run week04 analyze` | 打分最近一轮快照 → analysis.json + daily-report.html |
| `uv run week04 serve` | 本地看板(`--port` 覆盖端口,`--no-browser` 不弹浏览器) |
| `uv run week04 sync` | 命中视频写进飞书 Base(缺表自动建) |

## 进阶:下载视频 / 抽关键帧 / whisper 逐字稿

这些重资产功能没有迁进营基座(控制薄壳规模),源项目里代码完整可用:

- 位置:`SCT-AI超级个体营/08-实践项目/TikTok竞品视频监控系统/scripts/tm_assets.py`
- `download_video()` 下载原视频(yt-dlp,需要 ffmpeg 合并)
- `extract_frames()` + `make_contact_sheet()` 抽关键帧并拼 contact sheet(ffmpeg + Pillow)
- `fetch_transcript()` 拉公开字幕,装了 whisper 还能 ASR 转逐字稿

想要的话把这三个函数抄进本项目新开一个 `assets.py`,数据入口就是 `analysis.json` 里每条视频的 `webpage_url`。

## 常见问题

- **fetch 一条都拿不到**:多半是 TikTok 临时 503,等几分钟重跑;也可能账号写错了(handle 不带 `@`)。
- **demo 报演示数据缺失**:`git checkout weeks/week04-competitor-watch/data/sample`。
- **sync 报 lark-cli 失败**:先 `lark-cli auth login` 完成授权;建 Base 用的是 user 身份。
- **想让别人看看板**:看板只监听 127.0.0.1,数据都在你自己电脑上;要分享就把 `output/daily-report.html` 发出去。
