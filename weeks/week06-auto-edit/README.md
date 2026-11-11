# Week 6 · 自动视频剪辑流水线

把 5-8 段产品素材,自动剪成能发 TikTok 的 1080x1920 竖屏带货视频。
六步流水线,分镜表(`storyboard.json`)是唯一中枢,人可读可改:

```
① 扫描素材 → ② AI 打标 → ③ 话术 + 分镜 → ④ 配音 → ⑤ 成片(ffmpeg)/ ⑥ 剪映草稿
```

## 30 秒跑通(零密钥、零 ffmpeg)

```bash
cd sct-camp
uv sync
uv run week06 demo     # 命令行版
uv run week06          # 工作台版:浏览器自动打开 http://127.0.0.1:8706,点「跑一遍 Demo」
```

demo 不碰任何外部服务:占位素材是 Pillow 现场画的,打标和话术走内置 mock,
镜头匹配和分镜校验用的是**和真实流程完全同一套代码**——它证明流水线的"脑子"能跑,
重资产步骤(ffmpeg 成片、TTS 配音)留给配好环境之后。

产物(都在 `weeks/week06-auto-edit/output/`,gitignored):

| 产物 | 说明 |
|---|---|
| `demo/assets/*.png` | 5 张占位"素材"帧(现场生成,不提交二进制) |
| `demo/assets.json` | 素材清单 + mock 打标(note 画面描述 / roles 适合角色) |
| `demo/script.json` | 五段结构话术(hook → pain → feature → proof → cta) |
| `demo/storyboard.json` | 分镜表:每句话配哪个镜头、截几秒 |
| `demo/subs.ass` | 标准 ASS 字幕轨(*词* 转高亮黄) |
| `demo-report.html` | 流程报告:每步一张卡(输入 → 输出),一页看懂流水线 |

想核对分镜的素材截取时间和 ASS 字幕时间线，可以按同一组占位素材复跑 [中文算例](https://sctcamp.com/posts/product-video-storyboard-ass-captions) · [English walkthrough](https://sctcamp.com/en/posts/product-video-storyboard-ass-captions)。

## 环境体检

```bash
uv run week06 doctor
```

只跑 demo 可以无视 [FIX];真实成片需要装好这两样:

| 检查项 | 安装命令 |
|---|---|
| ffmpeg / ffprobe | Mac:`brew install ffmpeg` · Windows:`winget install ffmpeg`(装完**重开终端**);都不行去 gyan.dev 下 release full,把 `bin` 加进 PATH |
| 中文字体 | 一般系统自带(PingFang/微软雅黑);字幕出豆腐块时,在 `config.json` 的 `font_paths` 填一个中文字体路径,如 `/System/Library/Fonts/PingFang.ttc` |

## 换成你自己的产品

1. 素材放 `input/assets/`(每段 5-30 秒,竖屏最好),BGM 可选放 `input/bgm/bgm.mp3`
2. `config.json` 改产品名/卖点/人群
3. 要全 AI 流程,仓库根 `.env` 填 `LLM_API_KEY` / `LLM_BASE_URL`(OpenAI 兼容中转,base 不带 `/v1`)

```bash
uv run week06 analyze                 # ① 扫描素材 → output/assets.json
uv run week06 label                   # ② AI 打标(没 key 就手写 assets.json 的 note)
uv run week06 script                  # ③ 话术 + 分镜(--mock 零密钥;--script 接外部话术)
uv run week06 voice                   # ④ 配音(edge-tts 免费;--voice zh-CN-YunxiNeural 换男声)
uv run week06 render                  # ⑤ 成片 → output/final.mp4
uv run week06 jianying                # ⑥ 剪映草稿(先 uv pip install pyjianyingdraft)
```

不满意:直接改 `output/storyboard.json`(改它 = 改片子),重跑 ④⑤。

## 密钥去哪了(和源课程项目不同的一点)

密钥**永远不进 config.json**,一律写仓库根 `.env`(参考 `.env.example`):

| 变量 | 用途 |
|---|---|
| `LLM_API_KEY` / `LLM_BASE_URL` | 自动打标(视觉模型)+ AI 话术分镜 |
| `TTS_API_KEY` / `TTS_BASE_URL` | 仅 `voice.provider=api` 时需要;默认 edge-tts 免费零配置 |

`config.json` 只放非密钥项:产品信息、模型名(`llm.model` / `llm.vision_model`)、声音选择等。

## 常见问题

- **成片字幕是方块/乱码**:跑 `uv run week06 doctor` 看字体检查;`config.json` 的 `font_paths` 填一个中文字体路径。
- **报 `No such filter: 'ass'` 或 `drawtext`**:你改过渲染器用了这些滤镜——回退。本项目字幕方案(Pillow PNG + overlay)就是为了绕开它们。
- **成片画面被裁得只剩中间**:横屏素材硬裁 9:16 会切两边,正常。用竖屏素材,或把 `steps/render.py` 的 crop 改成 pad 加黑边。
- **AI 出的分镜很差**:大概率是素材描述(note)没写好。写"画面里是什么",不是"素材1"。
- **edge-tts 卡住/网络错误**:它走微软服务,关掉代理软件的"全局模式"重跑;已合成的段不受影响。
- **配音比画面长**:每秒约念 4 个字,段长 3 秒别写超 12 个字;改 storyboard.json 的 voiceover 重跑 voice + render。
- **剪映草稿素材全是红色感叹号**:素材是绝对路径,项目文件夹被移动了,移回去重跑 `jianying`。
- **装的是 CapCut 国际版**:草稿格式不同,参考 `pip install pycapcut` 自己改 `steps/jianying.py`,或直接走成片出口。

## 子命令一览

| 命令 | 作用 |
|---|---|
| `uv run week06` | 工作台(总览 + 六步流水线,端口 8706) |
| `uv run week06 demo` | 零密钥零 ffmpeg 走通"脑子":分镜表 + 字幕 + 流程报告 |
| `uv run week06 doctor` | 体检:ffmpeg / 字体 / Pillow / edge-tts / 密钥状态 |
| `uv run week06 analyze / label / script / voice / render / jianying` | 六步各自单跑 |
