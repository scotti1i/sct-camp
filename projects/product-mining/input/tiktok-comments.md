# TikTok / 短视频评论摘录

TikTok 评论区拿不到公开 API,就用最笨最稳的办法:打开视频评论区,把和需求相关的原话复制过来。

优先收集:

- 用户主动问哪里买。
- 用户说自己也有同样问题。
- 用户吐槽现有解决方案。
- 用户提出希望产品改进的点。

**格式:一条原话一行,以 `> ` 开头,analyze 会自动识别。示例(代码块里的不算数):**

```text
> ok but does it work on car seats?? mine is covered in dog hair
来源:https://www.tiktok.com/@xxx/video/xxx · 1.2k 赞
```

来源链接和点赞数写在原话后面的普通行里,不影响识别。从这里往下贴你自己的:

