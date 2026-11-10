# SCT 超级个体营 · 开源基座

一个仓库装下营里所有能跑的系统。**每个系统都是一个本地网页工作台**——点一下出结果，不用看终端。

对应的课程、在线演示和文章见 [SCTCamp 官网](https://sctcamp.com/)。第一次上手，可以先看这些工作流程：

| 仓库里的系统 | 中文实操指南 | English guide |
|---|---|---|
| GMV Max 投流诊断 | [GMV Max 不消耗怎么查](https://sctcamp.com/posts/gmv-max-not-spending) | [GMV Max not spending](https://sctcamp.com/en/posts/gmv-max-not-spending) |
| TikTok 竞品调研 | [用 Creative Center 看竞品素材](https://sctcamp.com/posts/tiktok-creative-center-competitor-research) | [Creative Center competitor research](https://sctcamp.com/en/posts/tiktok-creative-center-competitor-research) |
| AI 带货视频 | [先写商品视频分镜表](https://sctcamp.com/posts/ai-product-video-shot-list) | [AI product video shot list](https://sctcamp.com/en/posts/ai-product-video-shot-list) |

## 装好（只做一次）

```bash
# 0. 装 uv: https://docs.astral.sh/uv/getting-started/installation/
git clone <本仓库>
uv sync            # 自动装好 Python 和全部依赖(国内镜像已内置)
uv run camp doctor # 环境体检,红的照提示修
```

## 用起来

**直接敲系统名字，浏览器会自动打开这个系统的工作台**：

```bash
uv run week02      # 打开「批量 AI 视频工厂」工作台
```

工作台里点「跑一遍 Demo」就出结果，用的是自带的脱敏样例数据，**不需要任何密钥**。
先看到东西长什么样，再决定要不要配自己的数据。

| 系统 | 命令 | 端口 | 做什么（取自各项目 README） |
|---|---|---|---|
| Week 2 · 批量 AI 视频工厂 | `uv run week02` | 8702 | 产品信息 → 脚本 → 分镜 prompt → 提交生成 → 结果回收 → 写回飞书多维表格 |
| Week 3 · GMV Max 投流诊断日报机器人 | `uv run week03` | 8703 | TikTok Shop 后台导出表 → 4 张手机竖版诊断图 + 一页 HTML 日报 → 发进飞书群 |
| Week 4 · TikTok 竞品视频监控 | `uv run week04` | 8704 | 盯一组竞品账号，把最新公开视频数据变成「今天拆什么」的优先级清单 |
| Week 5 · AI 邮件增长工作台 | `uv run week05` | 8705 | 合规名单 → 个性化触达邮件；先 dry-run，再发给自己，最后才小批量真发 |
| Week 6 · 自动视频剪辑流水线 | `uv run week06` | 8706 | 5-8 段产品素材 → 能发 TikTok 的 1080x1920 竖屏带货视频 |
| News Radar · AI 新闻雷达 | `uv run radar` | 8707 | 盯 AI 信息源（RSS/Atom + GitHub 高星）→ 每天一页「今日雷达」 |
| 选品挖掘 · 需求信号工作台 | `uv run mining` | 8708 | 从海外真实用户表达里挖需求（不是让 AI 直接告诉你什么品能卖） |

### 给命令行和 AI agent 的子命令

工作台点得到的事，命令行也能做——子命令是给自动化和 AI agent 用的。
**这三个七个系统都有**：

```bash
uv run week02 demo     # 跑自带样例数据,零密钥出结果
uv run week02 doctor   # 本系统专属依赖体检
uv run week02 serve    # 显式打开工作台(等价于不带子命令)
```

停浏览器自动弹出用 `--no-browser`（`--no-open` 是等价别名，两个都认）。

其余子命令每个系统不同（采集、渲染、发送……），用 `--help` 看当前真实支持的：

```bash
uv run week02 --help
```

拿更新（修 bug / 新一周内容）永远是同两条：`git pull && uv sync`。

## 里面有什么

| 目录 | 说明 |
|---|---|
| `packages/camp-core` | 配置、密钥、doctor 框架——所有工具共用的地基 |
| `packages/camp-lark` | 飞书唯一通道(lark-cli 优先,OpenAPI 兜底) |
| `packages/camp-report` | HTML 报表渲染,全营一个长相 |
| `packages/camp-workbench` | 本地看板壳,所有工作台都从这里长出来 |
| `weeks/weekNN-*` | 每周直播做出来的系统,薄壳,业务逻辑一目了然 |
| `projects/*` | 营内实践项目,不按周编号(news-radar / product-mining) |
| `workspace/` | 你的产出都写这里,不进 git,`git pull` 永不冲突 |

> `weeks/` 从 week02 开始：Week 1 是开营课，讲工作流本身，没有交付系统。

## 约定（所有系统一致）

- **工作台是默认入口**：`uv run <命令>` 不带子命令 = 开网页；CLI 子命令是给 AI agent 的
- **demo 先行**：`uv run <命令> demo` 用自带脱敏样例出结果，先看到再配置
- **配置**：项目目录 `config.json`（首跑自动从 `config.example.json` 生成）
- **密钥**：只放仓库根 `.env`（参考 `.env.example`），永远不写进 config、不进 git
- **AI agent**：根目录和每个项目都有 `AGENTS.md`，Codex / Claude Code 直接开箱

## License

MIT — 随便用，教学生意的诚意就是代码本身。课程与社群见 [sctcamp.com](https://sctcamp.com)。
