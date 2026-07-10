"""GMV Max 广告导出表 → 结构化诊断结果。

输入:平台导出的 CSV/XLSX(字段名中英混杂,靠 ALIASES 自动对齐)
     + 可选 settings 表(目标 ROI、阶段、预算等人工维护字段)
输出:一个 result dict(totals / days / campaigns / scalable / risks / actions),
     render 画图和 HTML 日报都吃这一份,不做第二套聚合。
"""

from __future__ import annotations

import csv
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

from openpyxl import load_workbook

DEFAULT_TARGET_ROI = 2.0
DETAIL_LIMIT = 12

# ---------- 字段别名:各版本后台导出的表头都归到标准字段 ----------
ALIASES = {
    "date": ["日期", "Date", "By Day", "Day", "时间"],
    "campaign": ["计划名称", "Campaign name", "Campaign", "Campaign Name", "广告计划", "计划"],
    "product": ["商品名称", "Product name", "Product", "商品", "产品"],
    "status": ["计划状态", "Campaign status", "Status", "Bid strategy", "状态"],
    "spend": ["消耗", "Spend", "Cost", "花费", "成本"],
    "gmv": ["GMV", "总收入", "Gross revenue (Shop)", "Gross revenue", "Purchase value (TikTok)", "成交金额", "销售额"],
    "roi": ["ROI", "ROAS (Shop)", "ROAS", "Purchases ROAS (TikTok)", "投入产出比"],
    "orders": ["订单数", "Purchases (Shop)", "Orders", "Conversions", "成交订单数", "SKU订单数", "订单"],
    "impressions": ["曝光", "Impressions", "展示"],
    "clicks": ["点击", "Clicks (destination)", "Clicks", "Clicks (all)"],
}

CLEAN_FIELDS = ["日期", "计划名称", "商品名称", "计划状态", "消耗", "GMV", "ROI", "订单数", "曝光", "点击"]


def num(raw: object) -> float:
    """千分位/百分号/空值都容忍的数字解析。"""
    text = str(raw or "").replace(",", "").replace("%", "").strip()
    try:
        return float(text) if text else 0.0
    except ValueError:
        return 0.0


def _text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value).strip()


# ---------- 读文件:CSV 直读,XLSX 自动找表头行 ----------

def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fp:
        return list(csv.DictReader(fp))


def _header_score(headers: list[str]) -> int:
    """一行像不像广告表头:能对上的标准字段越多分越高。"""
    return sum(1 for names in ALIASES.values() if any(name in headers for name in names))


def _find_header_row(ws) -> tuple[int, list[str]]:
    best = (0, 1, [])
    for row_index, row in enumerate(ws.iter_rows(values_only=True), 1):
        headers = [_text(value) for value in row]
        score = _header_score(headers)
        if score > best[0]:
            best = (score, row_index, headers)
        if row_index >= 20:
            break
    if best[0] < 3:
        raise SystemExit(f"{ws.title} 前 20 行里没找到可识别的广告数据表头。")
    return best[1], best[2]


def _read_xlsx(path: Path) -> list[dict[str, str]]:
    workbook = load_workbook(path, read_only=True, data_only=True)
    ws = max(workbook.worksheets, key=lambda sheet: _header_score([_text(c) for row in sheet.iter_rows(max_row=20, values_only=True) for c in row]))
    header_row, headers = _find_header_row(ws)
    rows = []
    for row_index, row in enumerate(ws.iter_rows(values_only=True), 1):
        values = [_text(value) for value in row]
        if row_index <= header_row or not any(values):
            continue
        rows.append({headers[i]: values[i] for i in range(min(len(headers), len(values))) if headers[i]})
    return rows


def read_rows(path: Path) -> list[dict[str, str]]:
    if path.suffix.lower() == ".csv":
        return _read_csv(path)
    if path.suffix.lower() in {".xlsx", ".xlsm"}:
        return _read_xlsx(path)
    raise SystemExit(f"暂不支持这个文件格式:{path.name}(只认 CSV / XLSX)")


# ---------- 标准化:任意表头 → 干净行 ----------

def _mapping(headers: list[str]) -> dict[str, str | None]:
    return {key: next((name for name in names if name in headers), None) for key, names in ALIASES.items()}


def normalize_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    mapping = _mapping(list(rows[0].keys()))
    get = lambda row, key: row.get(mapping[key] or "", "")  # noqa: E731
    clean = []
    for row in rows:
        campaign = get(row, "campaign").strip()
        spend, gmv = num(get(row, "spend")), num(get(row, "gmv"))
        orders, clicks = int(num(get(row, "orders"))), int(num(get(row, "clicks")))
        if not campaign or campaign == "-" or not any([spend, gmv, orders, clicks]):
            continue
        roi = num(get(row, "roi")) or (gmv / spend if spend else 0)
        clean.append({
            "日期": get(row, "date"), "计划名称": campaign,
            "商品名称": get(row, "product"), "计划状态": get(row, "status"),
            "消耗": f"{spend:.2f}", "GMV": f"{gmv:.2f}", "ROI": f"{roi:.2f}",
            "订单数": str(orders), "曝光": str(int(num(get(row, "impressions")))), "点击": str(clicks),
        })
    return sorted(clean, key=lambda row: (row["日期"], row["计划名称"]))


def write_clean(rows: list[dict[str, str]], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=CLEAN_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return path


# ---------- settings 表:人工维护的目标/阶段/预算 ----------

def read_settings(path: Path | None) -> dict[str, dict[str, str]]:
    if not path or not path.exists():
        return {}
    return {row.get("计划名称", ""): row for row in read_rows(path) if row.get("计划名称")}


# ---------- 聚合与判断 ----------

def _group_campaigns(rows: list[dict[str, str]]) -> list[dict]:
    grouped: dict[str, dict] = defaultdict(lambda: defaultdict(float))
    meta: dict[str, dict[str, str]] = {}
    for row in rows:
        item = grouped[row["计划名称"]]
        item["spend"] += num(row["消耗"])
        item["gmv"] += num(row["GMV"])
        item["orders"] += num(row["订单数"])
        item["clicks"] += num(row["点击"])
        if num(row["消耗"]) or num(row["GMV"]):
            meta[row["计划名称"]] = {"product": row["商品名称"], "last_roi": row["ROI"]}
    campaigns = []
    for name, item in grouped.items():
        spend, gmv, orders = item["spend"], item["gmv"], int(item["orders"])
        campaigns.append({
            "name": name, "product": meta.get(name, {}).get("product", ""),
            "spend": spend, "gmv": gmv, "orders": orders, "clicks": int(item["clicks"]),
            "roi": gmv / spend if spend else 0.0,
            "cpo": spend / orders if orders else 0.0,
            "last_roi": num(meta.get(name, {}).get("last_roi")),
        })
    return sorted(campaigns, key=lambda c: c["spend"], reverse=True)


def _group_days(rows: list[dict[str, str]]) -> list[dict]:
    grouped: dict[str, dict] = defaultdict(lambda: defaultdict(float))
    for row in rows:
        if row["日期"]:
            item = grouped[row["日期"]]
            item["spend"] += num(row["消耗"])
            item["gmv"] += num(row["GMV"])
            item["orders"] += num(row["订单数"])
    return [
        {"day": day, "spend": item["spend"], "gmv": item["gmv"], "orders": int(item["orders"]),
         "roi": item["gmv"] / item["spend"] if item["spend"] else 0.0}
        for day, item in sorted(grouped.items())
    ]


def _enrich(campaign: dict, settings: dict[str, dict[str, str]], target_roi: float) -> None:
    setting = settings.get(campaign["name"], {})
    mode = setting.get("优化模式", "")
    campaign.update({
        "mode": mode or "未知",
        "target_roi": num(setting.get("目标ROI")) or target_roi,
        "budget": num(setting.get("日预算")),
        "stage": setting.get("阶段", "未知"),
        "new_creatives": int(num(setting.get("近7天新增素材数"))),
        "page_issue": setting.get("商品页问题", ""),
    })


def verdict(campaign: dict) -> str:
    """单计划判断:冷启动先观察,低 ROI 先补证据,达标才谈放量。"""
    roi, target = campaign["roi"], campaign["target_roi"]
    if "冷启动" in campaign["stage"] or "最大投放量" in campaign["mode"]:
        return "冷启动观察:先补创意/商品质量,避免过早停计划" if roi < target else "冷启动健康:观察到 5-7 天再决定放量"
    if roi < target * 0.9:
        if campaign["new_creatives"] <= 1:
            return "低于目标:先补创意和查商品页,再决定降预算"
        return "低于目标:先查 ROI Protection,再决定是否降预算"
    if roi >= target and campaign["orders"] >= 10:
        return "达标:可逐日小幅加预算,单日不超过 30%"
    return "接近目标:保持预算,补素材继续观察"


def _actions(scalable: list[dict], risks: list[dict], watch: list[dict]) -> list[dict]:
    """今日动作清单:最多 5 条,每条一个对象一个动作。"""
    actions = []
    if risks:
        actions.append({"who": risks[0]["name"], "what": "补齐 ROI Protection / 目标 ROI / 预算 / 商品页截图,再决定是否降预算"})
    if len(risks) > 1:
        actions.append({"who": risks[1]["name"], "what": "复盘转化链路:优先查价格、评价、库存、优惠和商品页"})
    if scalable:
        actions.append({"who": scalable[0]["name"], "what": "预算逐日上调,单日不超过 30%,明天复查 ROI 是否守住"})
    if watch:
        actions.append({"who": watch[0]["name"], "what": "暂不大幅调整,补 1-2 条新素材继续喂计划"})
    actions.append({"who": "全部计划", "what": "把今天的调整动作写回表格,明天对比调整前后 ROI、订单数和 CPO"})
    return actions[:5]


def analyze(input_path: Path, settings_path: Path | None, target_roi: float) -> tuple[dict, list[dict[str, str]]]:
    """总入口:导出表 + settings → (result dict, 清洗后的行)。"""
    raw_rows = read_rows(input_path)
    if not raw_rows:
        raise SystemExit(f"{input_path} 没有数据。")
    clean_rows = normalize_rows(raw_rows)
    settings = read_settings(settings_path)
    campaigns = _group_campaigns(clean_rows)
    for campaign in campaigns:
        _enrich(campaign, settings, target_roi)
        campaign["verdict"] = verdict(campaign)
    days = _group_days(clean_rows)

    spend = sum(c["spend"] for c in campaigns)
    gmv = sum(c["gmv"] for c in campaigns)
    orders = sum(c["orders"] for c in campaigns)
    clicks = sum(c["clicks"] for c in campaigns)
    detail = campaigns[:DETAIL_LIMIT]
    scalable = sorted(
        [c for c in campaigns if c["roi"] >= c["target_roi"] and c["orders"] >= 10 and "冷启动" not in c["stage"]],
        key=lambda c: (c["roi"], c["orders"]), reverse=True)[:5]
    risks = sorted([c for c in detail if c["spend"] >= 100 and c["roi"] < c["target_roi"]],
                   key=lambda c: c["spend"], reverse=True)[:5]
    watch = [c for c in detail if c not in scalable and c not in risks]

    result = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source": input_path.name,
        "target_roi": target_roi,
        "data_range": f"{days[0]['day']} - {days[-1]['day']}" if days else "暂无日期",
        "totals": {
            "spend": spend, "gmv": gmv, "roi": gmv / spend if spend else 0.0,
            "orders": orders, "cpo": spend / orders if orders else 0.0,
            "click_to_order": orders / clicks if clicks else 0.0,
        },
        "days": days,
        "campaigns": campaigns,
        "scalable": scalable,
        "risks": risks,
        "actions": _actions(scalable, risks, watch),
    }
    return result, clean_rows
