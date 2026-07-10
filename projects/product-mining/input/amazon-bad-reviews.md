# Amazon 低星差评摘录

只看好评会让你以为产品完美,差评才告诉你微创新空间在哪里。
有 ASIN 时优先 `uv run mining fetch --asin B0XXXXXXXX` 自动抓;抓不到的,人工摘录 1-3 星评论:

- 没效果。
- 容易坏。
- 不适合某种材质/场景。
- 尺寸、重量、清洁方式不方便。
- 与页面承诺不一致。

**格式:一条原话一行,以 `> ` 开头,analyze 会自动识别。示例(代码块里的不算数):**

```text
> Broke on day 9. The roller axle is flimsy plastic
来源:ASIN B0XXXXXXXX · 1 星 · 失败原因:结构强度
```

从这里往下贴你自己的:

