"""LLM 调用:OpenAI 兼容 HTTP(/v1/chat/completions)+ mock provider。

密钥只走 camp_core.secret(LLM_API_KEY / LLM_BASE_URL),config.json 只放模型名。
mock provider 零密钥可用:内置话术模板 + 内置素材标注,demo 和 --mock 都走它。
"""

from __future__ import annotations

import json
import urllib.request
from typing import Any

from camp_core import secret

TIMEOUT = 120


def have_llm() -> bool:
    return bool(secret("LLM_API_KEY") and secret("LLM_BASE_URL"))


def chat_json(config: dict[str, Any], system: str, user_content: Any,
              vision: bool = False, temperature: float = 0.4) -> Any:
    """调 OpenAI 兼容接口,要求模型只输出 JSON,解析后返回。"""
    key = secret("LLM_API_KEY")
    base = secret("LLM_BASE_URL")
    if not key or not base:
        raise SystemExit(
            "缺少 LLM 配置:在仓库根 .env 填 LLM_API_KEY 和 LLM_BASE_URL(中转站根地址,不带 /v1)。\n"
            "不想花钱:demo 和 --mock 都不需要密钥。"
        )
    llm = config.get("llm", {})
    model = (llm.get("vision_model") if vision else llm.get("model")) or "gpt-5-mini"
    req = urllib.request.Request(
        base.rstrip("/") + "/v1/chat/completions",
        method="POST",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
        data=json.dumps({
            "model": model, "stream": False, "temperature": temperature,
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": user_content}],
        }).encode(),
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        data = json.load(resp)
    return parse_json_reply(data["choices"][0]["message"]["content"])


def parse_json_reply(text: str) -> Any:
    """剥掉 ```json 围栏后解析。"""
    text = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return json.loads(text)


# ------------------------------------------------------------
# mock provider:不联网不花钱,给 demo / --mock 用
# ------------------------------------------------------------

# 内置话术模板(六句,五段结构),与 config.example.json 的示例产品配套
MOCK_SCRIPT = [
    {"role": "hook", "voiceover": "这瓶真的是把我烂脸期救回来的", "caption": "烂脸期把我*救回来*的一瓶"},
    {"role": "pain", "voiceover": "换季暴皮的时候,我敷什么都刺痛", "caption": "换季暴皮 敷什么都*刺痛*"},
    {"role": "feature", "voiceover": "它是乳霜质地,上脸真的秒吸收", "caption": "乳霜质地 上脸*秒吸收*"},
    {"role": "feature", "voiceover": "按一泵刚刚好用全脸,不浪费", "caption": "*一泵*刚好用全脸"},
    {"role": "proof", "voiceover": "坚持用了两周,泛红肉眼可见地退下去了", "caption": "两周 泛红*肉眼可见*地退"},
    {"role": "cta", "voiceover": "想要的评论区扣个一,链接直接发你", "caption": "评论区*扣1* 链接发你"},
]

# 内置素材标注(mock 的"视觉模型"):画面描述 + 适合角色
MOCK_LABELS = [
    {"note": "手拿棕色滴管精华瓶特写展示,米色背景,质感产品镜头", "roles": ["hook", "feature"]},
    {"note": "粉衣女生按压白色泵瓶,取用产品的动作特写", "roles": ["feature"]},
    {"note": "女生对着圆镜敷灰色清洁面膜,护肤流程镜头", "roles": ["pain"]},
    {"note": "裹浴巾的女生对镜涂面霜按摩脸部,使用场景", "roles": ["proof", "feature"]},
    {"note": "绿色背景,手拿白色面霜罐展示,旁边有植物,产品展示镜头", "roles": ["cta", "hook"]},
]


def mock_script(product: dict[str, Any]) -> list[dict[str, str]]:
    """内置话术模板;产品名不同也能跑,教学重点是结构不是文案。"""
    _ = product  # 模板与示例产品配套;换产品请配 LLM key 走真实生成
    return [dict(line) for line in MOCK_SCRIPT]


def mock_label(index: int) -> dict[str, Any]:
    """按序号循环发内置标注,行为与视觉模型一致(note + roles)。"""
    return dict(MOCK_LABELS[index % len(MOCK_LABELS)])
