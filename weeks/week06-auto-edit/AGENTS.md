# AGENTS.md · week06-auto-edit

自动视频剪辑流水线。改代码前先读仓库根 `AGENTS.md`(硬性约定优先级更高)。

## 跑法

```bash
uv run week06 doctor   # 体检(ffmpeg/字体是 [FIX] 也能跑 demo)
uv run week06 demo     # 零密钥零 ffmpeg:占位素材 → 分镜表 + subs.ass + demo-report.html
uv run week06          # 工作台 http://127.0.0.1:8706,点「跑一遍 Demo」
```

改完代码先跑 `demo`:output/demo/ 里 storyboard.json + subs.ass + assets/*.png 和
output/demo-report.html 都生成才算通过。动了 render/voice 还要用真素材各跑一遍。

## 数据流(storyboard.json 是唯一中枢)

```
input/assets/*.mp4
  → steps/analyze.py  ① ffprobe 元数据      → output/assets.json
  → steps/label.py    ② 视觉模型抽帧打标     → assets.json 的 note/roles
  → steps/script.py   ③ 话术 + 镜头匹配      → script.json + storyboard.json(★中枢)
  → steps/voice.py    ④ TTS(provider 可插拔)→ output/voice/seg-XX.mp3
  → steps/render.py   ⑤ 出口①:ffmpeg 成片   → output/final.mp4(字幕烧录)
  → steps/jianying.py ⑥ 出口②:剪映草稿      (字幕是可编辑文本轨,不烧)
demo.py:占位素材 + mock 打标 + 内置话术 + 规则匹配 → output/demo/(零外部依赖)
pipeline.py:六步的唯一注册表;workbench.py 和 cli.py 都只从它拿步骤
```

storyboard.json schema:

```json
{"product": "名", "segments": [{
  "asset": "clip-01.mp4", "in": 0.0, "out": 2.5,
  "caption": "字幕,*星号*=高亮黄", "voiceover": "口播文案",
  "role": "hook|pain|feature|proof|cta"}]}
```

## 硬性约定(改代码前必读)

1. **storyboard.json 是唯一中枢**,所有出口只吃它;改剪辑逻辑先想是不是该改决策层(steps/script.py),而不是渲染器
2. **字幕烧录只属于 mp4 出口**(render.py 的 `draw_caption`,Pillow 画 PNG + ffmpeg overlay)。不要改成 drawtext/ass 滤镜——学员机 ffmpeg 构建不一定带 libass,实测踩过
3. 剪映出口字幕走**文本轨**(可编辑),只用 pyJianYingDraft 的「生成草稿」能力(剪映 5+ 全兼容);不要引入模板模式/自动导出
4. TTS 走 `steps/voice.py` 的 `PROVIDERS` 字典,加新 TTS = 加一个函数 + config.voice 一段,不要动调用方
5. LLM/视觉模型走 OpenAI 兼容格式,全部收在 `llm.py`;**密钥只走 `camp_core.secret`**(LLM_API_KEY / LLM_BASE_URL / TTS_API_KEY / TTS_BASE_URL),永远不进 config.json
6. `llm.py` 的 mock provider 和 `steps/script.py` 的 `rule_match` 是 demo 的"脑子",LLM 和 mock 的产物都必须过同一个 `validate` 守门
7. ffmpeg 子进程统一 `cwd=PROJECT_DIR` + 相对路径(双平台);其余路径用 pathlib
8. 界面只用 camp_workbench(workbench.py 只摆页面,业务永远在 steps/);报表只用 camp_report
9. 依赖白名单:标准库 + camp 三包 + Pillow + edge-tts;pyjianyingdraft 是可选 extra,保持惰性导入

## 常见任务怎么改

| 任务 | 改哪里 |
|------|--------|
| 字幕样式(字号/位置/高亮色) | `steps/render.py` → `draw_caption()` / `HIGHLIGHT` |
| 换 TTS(如 ElevenLabs) | `steps/voice.py` → `PROVIDERS` 加函数 + config.voice |
| 改 AI 话术风格/语言/结构 | `steps/script.py` → `PROMPT_SCRIPT` |
| 改镜头匹配规则 | `steps/script.py` → `PROMPT_MATCH`(mock 对应 `rule_match`) |
| 改打标输出字段 | `steps/label.py` → `PROMPT` |
| 视频规格 | `base.py` 顶部 `W, H, FPS` |
| 工作台加按钮 | `pipeline.py` 的 `STEPS`(workbench 自动长出按钮) |
| 改 demo 占位素材/文案 | `demo.py` 的 `DEMO_CLIPS` / `llm.py` 的 `MOCK_*` |
