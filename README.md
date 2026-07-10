# SCT 超级个体营 · 开源基座

一个仓库装下营里所有能跑的系统。你只需要三条命令:

```bash
# 0. 装 uv(只装一次): https://docs.astral.sh/uv/getting-started/installation/
git clone <本仓库>
uv sync            # 自动装好 Python 和全部依赖(国内镜像已内置)
uv run camp doctor # 环境体检,红的照提示修
```

之后每个周项目都是同一个跑法:

```bash
uv run week02 demo   # 一条命令,用自带样例数据跑出结果(不需要任何密钥)
uv run week02 doctor # 本周专属依赖体检
```

拿更新(修 bug / 新一周内容)永远是同两条:`git pull && uv sync`。

## 里面有什么

| 目录 | 说明 |
|---|---|
| `packages/camp-core` | 配置、密钥、doctor 框架——所有工具共用的地基 |
| `packages/camp-lark` | 飞书唯一通道(lark-cli 优先,OpenAPI 兜底) |
| `packages/camp-report` | HTML 报表渲染,全营一个长相 |
| `packages/camp-workbench` | 本地看板壳,工具的界面都从这里长出来 |
| `weeks/weekNN-*` | 每周直播做出来的系统,薄壳,业务逻辑一目了然 |
| `workspace/` | 你的产出都写这里,不进 git,`git pull` 永不冲突 |

## 约定(所有周项目一致)

- **demo 先行**:每个工具 `uv run weekNN demo` 用自带脱敏样例出结果,先看到再配置
- **配置**:项目目录 `config.json`(首跑自动从 `config.example.json` 生成)
- **密钥**:只放仓库根 `.env`(参考 `.env.example`),永远不写进 config、不进 git
- **AI agent**:根目录和每个周项目都有 `AGENTS.md`,Codex / Claude Code 直接开箱

## License

MIT — 随便用,教学生意的诚意就是代码本身。课程与社群见 [scottplaybook.com](https://scottplaybook.com)。
