# Week 2 · 批量 AI 视频工厂

把一批视频任务从产品信息推进到:**脚本 → 分镜 prompt → 提交生成 → 结果回收 → 写回飞书多维表格**。

## 30 秒看到结果(不需要任何密钥)

```bash
uv run week02
```

浏览器自动打开工作台(`http://127.0.0.1:8702`),点「跑一遍 Demo」:
mock 流水线十几秒跑完,总览页直接看到任务数和成功数,「任务表」页是完整任务状态,
还能一键打开最新 HTML 报告。不装飞书 CLI、不消耗任何积分,全程不用看终端。

CLI 子命令是同一条流水线的管线形态,给 AI agent 和自动化用:

```bash
uv run week02 demo
```

跑完后:

- `output/tasks.json` —— 8 条任务的完整状态
- `output/demo-report.html` —— 一页结果报告,浏览器直接打开

## 环境体检

```bash
uv run week02 doctor
```

红的按 `[FIX]` 提示修;`lark-cli` 和 `dreamina` 都是可选项,不装也能跑 demo。

## 真实运行要配什么

首跑会自动生成 `config.json`(从 `config.example.json` 复制),按需改三处:

### 1. 换成你的产品

改 `config.json` 的 `product` 区块(名称、人群、卖点、禁用表达)。

### 2. 写回飞书多维表格(可选)

1. 复制 Base 模板:<https://my.feishu.cn/wiki/G9z4wAXqyi1hgCkx0rkcC0aLn5c>
2. 打开你复制后的 Base,把 URL 里 `/base/` 后面的 token 填进 `base.base_token`
3. `base.enabled` 改成 `true`,并确认已安装登录 `lark-cli`

之后每步都会自动同步「视频生成任务」表,也可手动 `uv run week02 sync`。

### 3. 真实生成视频(可选)

| provider | 用途 | 消耗积分 |
|---|---|---|
| `mock` | 流程验证(默认) | 否 |
| `web_manual` | 把 prompt 复制到网页端手动生成 | 否 |
| `dreamina` | 即梦 CLI 批量提交 | 是 |
| `video_api` | 任意视频生成 API 服务 | 是 |

```bash
# 单步流水线
uv run week02 scripts --count 8
uv run week02 prompts
uv run week02 submit --provider dreamina   # 或 video_api / web_manual
uv run week02 poll                          # 轮询结果,dreamina 会下载到 output/videos/
```

- `dreamina`:先安装并登录即梦 CLI,批量提交前跑 `dreamina user_credit` 确认余额。
- `video_api`:把 `endpoint` / `model` 填进 `config.json` 的 `video_api` 区块,
  密钥写仓库根 `.env`:`VIDEO_API_KEY=你的key`(永远不要写进 config.json)。

## 建议节奏

```text
mock 跑通流程 → 网页端手动兜底 → 即梦 CLI / 视频 API 小批量验证 → 批量生成
```
