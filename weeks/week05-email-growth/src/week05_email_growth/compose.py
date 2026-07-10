"""联系人 → 个性化邮件:加载、渲染、合规检查。

本周项目的灵魂是合规,不是发送量:
- 没有 source / consent_status 合法标记的联系人默认拦截(status=blocked)
- 每封邮件强制带退订链接和真实邮寄地址
- 真实发送前 hard_blockers() 必须为空,cli 会拒发
"""

from __future__ import annotations

import csv
import html
from pathlib import Path
from typing import Any

PROJECT_DIR = Path(__file__).resolve().parents[2]
TEMPLATE = PROJECT_DIR / "prompts" / "outreach-email-template.html"
DEMO_CSV = PROJECT_DIR / "data" / "contacts-demo.csv"

CONTACT_KEYS = [
    "email", "first_name", "company", "role", "segment",
    "pain_point", "offer", "source", "consent_status",
]
# 只有这四类来源可以进入发送,这条不许放宽
CONSENT_OK = {"consented", "business_contact", "customer", "subscriber"}


# ---------- 名单 ----------

def load_contacts(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise SystemExit(f"找不到名单 CSV:{path}(字段见 README「换成你的名单」)")
    with path.open(newline="", encoding="utf-8-sig") as file:
        contacts = [_normalize(row) for row in csv.DictReader(file)]
    if not contacts:
        raise SystemExit(f"名单是空的:{path}")
    return contacts


def _normalize(row: dict[str, str]) -> dict[str, str]:
    return {key: str(row.get(key) or "").strip() for key in CONTACT_KEYS}


def consent_ok(contact: dict[str, str]) -> bool:
    return contact.get("consent_status") in CONSENT_OK


# ---------- 邮件生成 ----------

def build_emails(contacts: list[dict[str, str]], config: dict[str, Any]) -> list[dict[str, Any]]:
    return [render_email(contact, config, index) for index, contact in enumerate(contacts)]


def render_email(contact: dict[str, str], config: dict[str, Any], index: int) -> dict[str, Any]:
    campaign = config.get("campaign", {})
    subject = make_subject(contact, campaign, index)
    body = make_body(contact, config, subject)
    return {
        "email": contact.get("email"),
        "first_name": contact.get("first_name") or "你好",
        "company": contact.get("company"),
        "subject": subject,
        "text": body["text"],
        "html": body["html"],
        "cta_url": campaign.get("cta_url", "https://example.com"),
        "consent_ok": consent_ok(contact),
        "source_reason": f"{contact.get('source') or '手动整理名单'} / {contact.get('consent_status') or 'unknown'}",
        "status": "ready" if consent_ok(contact) else "blocked",
    }


def make_subject(contact: dict[str, str], campaign: dict[str, Any], index: int) -> str:
    first = contact.get("first_name") or "你好"
    company = contact.get("company") or "你的项目"
    product = campaign.get("product_name") or "我们的产品"
    purpose = campaign.get("purpose", "")
    if purpose == "creator_bd_registration":
        return f"{first}，邀请你体验 {product}"
    if purpose == "creator_outreach":
        return f"{first}，想和 {company} 做一次真实测评合作"
    if purpose == "b2b_outreach":
        return f"关于 {company} 的 AI 邮件跟进小建议"
    choices = [
        f"给 {company} 的一个小合作想法",
        f"{first}，这封邮件只讲一个具体机会",
    ]
    return choices[index % len(choices)]


def make_body(contact: dict[str, str], config: dict[str, Any], subject: str) -> dict[str, str]:
    brand = config.get("brand", {})
    campaign = config.get("campaign", {})
    first = contact.get("first_name") or "你好"
    target = contact.get("company") or "你的项目"
    role = contact.get("role") or "相关业务"
    pain = contact.get("pain_point") or "找到更稳定的增长机会"
    offer = campaign.get("offer_name") or contact.get("offer") or "合作方案"
    cta = campaign.get("cta_url", "https://example.com")
    sender = brand.get("sender_name") or "发件人"
    company = brand.get("company_name") or "我们的团队"
    address = brand.get("physical_address", "")
    unsubscribe = brand.get("unsubscribe_url", "")
    mail = sender_email(config)
    text = (
        f"{first}，你好。\n\n"
        f"我看到你这边是「{target}」，方向和「{role}」相关。\n"
        f"这封邮件不是群发模板，主要想聊一个具体点：{pain}。\n\n"
        f"我们现在准备一个「{offer}」的小合作。"
        f"如果你觉得方向匹配，可以打开这个链接了解详情：{cta}\n\n"
        f"如果不合适，直接回复不需要就行，我不会继续打扰。\n\n"
        f"{sender}\n{company}\n{mail}\n{address}\n退订：{unsubscribe}\n"
    )
    html_body = _render_template({
        "subject": subject,
        "preview_text": f"关于「{offer}」的一个具体小合作想法。",
        "headline": f"想和 {target} 聊一个具体的合作点",
        "first_name": first,
        "company": target,
        "role": role,
        "pain_point": pain,
        "offer_name": offer,
        "cta_url": cta,
        "cta_label": campaign.get("cta_label") or "了解合作详情",
        "sender_name": sender,
        "sender_email": mail,
        "company_name": company,
        "physical_address": address,
        "unsubscribe_url": unsubscribe,
    })
    return {"text": text, "html": html_body}


def sender_email(config: dict[str, Any]) -> str:
    from_email = config.get("resend", {}).get("from_email", "")
    if "<" in from_email and ">" in from_email:
        return from_email.split("<", 1)[1].split(">", 1)[0].strip()
    return from_email


def _render_template(values: dict[str, str]) -> str:
    template = TEMPLATE.read_text(encoding="utf-8")
    if template.startswith("<!--"):  # 文件头的变量说明注释不进真实邮件
        template = template.split("-->", 1)[1].lstrip()
    for key, value in values.items():
        template = template.replace("{{" + key + "}}", html.escape(str(value), quote=True))
    return template


# ---------- 合规检查 ----------

def hard_blockers(config: dict[str, Any]) -> list[str]:
    """真实发送前必须为空:退订链接 + 真实邮寄地址,少一样都拒发。"""
    brand = config.get("brand", {})
    blockers = []
    address = str(brand.get("physical_address", "")).strip()
    if not address or "请填写" in address or "真实公司" in address:
        blockers.append("缺少真实邮寄地址(config.json 的 brand.physical_address),商业邮件不应发送")
    unsubscribe = str(brand.get("unsubscribe_url", "")).strip()
    if not unsubscribe or "example.com" in unsubscribe:
        blockers.append("缺少真实退订链接(config.json 的 brand.unsubscribe_url),商业邮件不应发送")
    return blockers


def compliance_warnings(config: dict[str, Any], contacts: list[dict[str, str]]) -> list[str]:
    warnings = list(hard_blockers(config))
    if "onboarding@resend.dev" in config.get("resend", {}).get("from_email", ""):
        warnings.append("当前是 Resend 测试发件人,只适合 dry-run 或发给自己的邮箱")
    blocked = [row for row in contacts if not consent_ok(row)]
    if blocked:
        warnings.append(f"{len(blocked)} 个联系人缺少同意/合法业务来源,已默认拦截")
    return warnings
