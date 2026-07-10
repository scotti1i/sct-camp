# Week 5 · AI 邮件增长工作台

把一份合规联系人名单,变成个性化触达邮件:**先 dry-run,再发给自己测试,最后才小批量真实发送**。发信通道用 [Resend](https://resend.com),看板和报告都是全营统一长相。

## 红线:这不是垃圾邮件工具

- 只发这几类名单:**已有客户 / 订阅用户 / 历史询盘 / 授权达人名单 / 合法业务联系人**
- 不买邮箱包、不爬来路不明的名单、不绕垃圾箱、不隐藏身份
- 商业邮件必须包含:真实发件人身份、**真实邮寄地址**、**退订方式**——缺任何一样,`send --really` 直接拒发
- 名单里没有 `source` 和 `consent_status` 合法标记的联系人,系统默认拦截(blocked),不进入发送

## 30 秒跑通(零密钥零外发)

```bash
cd sct-camp
uv sync
uv run week05 demo
```

产物(都在 `weeks/week05-email-growth/output/`,gitignored):

| 产物 | 说明 |
|---|---|
| `demo-report.html` | 一页报告:本批概览 + 合规检查结果 + 全部邮件预览(收件人/主题/正文摘要) |
| `emails.json` | 全部个性化邮件(text + html + 状态),`send` 按它发 |
| `summary.json` | 本批统计与合规警告,看板首页吃这一份 |

## 子命令一览

| 命令 | 作用 |
|---|---|
| `uv run week05 demo` | 零密钥零外发:自带 demo 名单 → 全部个性化邮件 + HTML 报告 |
| `uv run week05 doctor` | 体检:名单 / 模板 / 生成链路 / RESEND_API_KEY 状态 |
| `uv run week05 preview` | 按 `config.json` 的名单生成邮件(`--contacts` 可覆盖,`--limit N` 只取前 N 个) |
| `uv run week05 send` | **默认 dry-run**,只写 `output/send-log.jsonl`,不发任何邮件 |
| `uv run week05 send --really --limit 1` | 真实发送(唯一开关);第一次只发 1 封给自己 |
| `uv run week05 serve` | 本地看板:`/` 邮件预览列表,`/metrics` 发送统计(`--no-open` 不弹浏览器) |

## 换成你的名单

准备一个 CSV(参考 `data/contacts-demo.csv`),表头字段:

```text
email, first_name, company, role, segment, pain_point, offer, source, consent_status
```

- `source`:这个邮箱怎么来的(如"历史询盘客户""公开主页主动留合作邮箱")
- `consent_status`:只有 `consented` / `business_contact` / `customer` / `subscriber` 四种值可进入发送,其余一律拦截

把路径写进 `config.json` 的 `contacts_csv`(或 `preview --contacts 路径`),再跑:

```bash
uv run week05 preview
```

个性化逻辑吃 `pain_point` / `offer` / `company` 三个字段,主题行风格由 `config.json` 的 `campaign.purpose` 决定(`creator_outreach` / `creator_bd_registration` / `b2b_outreach`)。想让 AI 帮你写更定制的版本,提示词在 `prompts/email-personalization.md`。

## 真实发送前:配置 Resend(手动 6 步)

课堂内容到 dry-run 为止;下面是你真要发信时的完整路径。

1. **注册** https://resend.com ,进入 Dashboard。
2. **添加 Domain**:`Domains → Add Domain`,填你拥有并能管 DNS 的域名。有真实业务邮箱的,优先用子域名(如 `send.yourdomain.com`),避免影响主邮箱。
3. **复制 DNS 记录**:进 Domain 的 Records 页,把 Resend 给的 DKIM / SPF / MX(/DMARC)记录逐条粘贴到域名服务商后台(GoDaddy / Cloudflare / 阿里云都行)。Type 对 Type、Host 对 Host、Value 对 Value,不要手打。
4. **验证**:回 Resend 点 `Verify DNS Records`,等状态变 `Verified`(DNS 同步可能要几分钟到几小时)。
5. **创建 API Key**:`API Keys → Create API Key`,权限只选 **Sending access**,能限定 Domain 就限定。key 只显示一次。
6. **配到本地**:把 key 写进仓库根 `.env`(参考 `.env.example`):

   ```text
   RESEND_API_KEY=re_xxxxxxxxx
   ```

   再改 `weeks/week05-email-growth/config.json`:

   ```json
   {
     "resend": {
       "from_email": "你的名字 <hello@yourdomain.com>",
       "reply_to": "you@yourdomain.com"
     },
     "brand": {
       "physical_address": "你的真实公司/工作室邮寄地址",
       "unsubscribe_url": "你的真实退订链接"
     }
   }
   ```

**key 永远不写进** config.json、代码、git、飞书文档、群聊、截图。

## 第一次真实发送

不要群发。只发给自己:

```bash
uv run week05 preview --limit 1   # 名单第一行先换成你自己的邮箱
uv run week05 send --really --limit 1
```

然后检查:收件箱有没有收到、发件人显示是否正确、退订链接和邮寄地址在不在、Resend Dashboard 的 Logs 里有没有成功记录。都对了,再小批量放大。

## 本地看板

```bash
uv run week05 serve
```

浏览器打开 `http://127.0.0.1:8785`:`/` 是邮件预览列表(含合规警告),`/metrics` 是发送统计和最近日志。界面由 `camp_workbench` 提供,数据都在你自己电脑上。

## 常见问题

- **`send` 报"缺少 emails.json"**:先跑 `uv run week05 demo` 或 `preview` 生成邮件。
- **`send --really` 被拒发**:`config.json` 的 `physical_address` / `unsubscribe_url` 还是占位文案。这是合规红线,填真实值才放行。
- **`send --really` 报缺 RESEND_API_KEY**:按上面 6 步申请,写进仓库根 `.env`。
- **联系人全被拦截**:CSV 缺 `consent_status` 列或值不在四种合法值内;补上真实来源,不要硬填。
- **打开/点击数据怎么看**:Resend 的 Domain 验证后可在 Dashboard 开启 open/click tracking,数据看 Resend Logs;本项目不再内置本地点击追踪。
