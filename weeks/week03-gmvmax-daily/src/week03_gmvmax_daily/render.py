"""诊断结果 → 4 张手机竖版模块 PNG(1080x1440,一模块一判断)。

01 KPI 判断 / 02 消耗与 ROI 趋势 / 03 Top5 计划 / 04 今日动作。
这是本项目的招牌产出:发到飞书群里,手机上一屏一张看完。
字体路径可在 config.json 的 font_paths 里覆盖,默认按系统常见中文字体兜底。
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from PIL import Image, ImageDraw, ImageFont

from camp_core import write_json

W, H = 1080, 1440
BG, CARD, INK, MUTED, LINE = "#f5f7fb", "#ffffff", "#111827", "#5f6368", "#d8dee8"
BLUE, GREEN, RED, AMBER = "#1a73e8", "#188038", "#d93025", "#f29900"
PALE_RED, PALE_GREEN, PALE_AMBER = "#fce8e6", "#e6f4ea", "#fff7e0"

# 默认字体候选:macOS → Linux → Windows,一个能中文的就行
FONT_CANDIDATES = [
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/STHeiti Light.ttc",
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    "C:/Windows/Fonts/msyh.ttc",
]


def find_font(extra_paths: list[str] | None = None) -> str:
    """按 config 覆盖 + 系统候选找中文字体,找不到返回空串(退化为 PIL 默认)。"""
    for candidate in [*(extra_paths or []), *FONT_CANDIDATES]:
        if candidate and Path(candidate).exists():
            return candidate
    return ""


def load_fonts(extra_paths: list[str] | None = None) -> SimpleNamespace:
    """一次性备好全部字号。TTC 的 index=1 当粗体用(PingFang 恰好是 Semibold)。"""
    path = find_font(extra_paths)

    def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
        if not path:
            return ImageFont.load_default(size=size)
        index = 1 if bold and path.endswith(".ttc") else 0
        try:
            return ImageFont.truetype(path, size=size, index=index)
        except OSError:
            return ImageFont.truetype(path, size=size)

    return SimpleNamespace(
        title=font(54, True), big=font(104, True), h1=font(64, True), h2=font(42, True),
        h3=font(34, True), body=font(31), body_b=font(31, True), small=font(25),
    )


# ---------- 基础画法 ----------

def money(value: float) -> str:
    return f"{value / 1000:.1f}k" if value >= 1000 else f"{value:,.0f}"


def _text_w(draw: ImageDraw.ImageDraw, value: str, fnt) -> int:
    box = draw.textbbox((0, 0), value, font=fnt)
    return box[2] - box[0]


def fit_text(draw: ImageDraw.ImageDraw, value: str, fnt, max_width: int) -> str:
    if _text_w(draw, value, fnt) <= max_width:
        return value
    result = value
    while result and _text_w(draw, result + "...", fnt) > max_width:
        result = result[:-1]
    return (result + "...") if result else "..."


def wrap_text(draw: ImageDraw.ImageDraw, value: str, fnt, max_width: int, max_lines: int) -> list[str]:
    tokens = value.split(" ") if " " in value else list(value)
    lines: list[str] = []
    current = ""
    for token in tokens:
        glue = " " if current and " " in value else ""
        candidate = current + glue + token
        if _text_w(draw, candidate, fnt) <= max_width:
            current = candidate
            continue
        if current:
            lines.append(current)
        current = token
        if len(lines) == max_lines:
            break
    if len(lines) < max_lines and current:
        lines.append(current)
    if len(lines) == max_lines:
        lines[-1] = fit_text(draw, lines[-1], fnt, max_width)
    return [line for line in lines if line]


def draw_wrapped(draw: ImageDraw.ImageDraw, xy, value: str, fnt, fill, max_width: int, max_lines: int, gap: int = 10) -> None:
    x, y = xy
    for line in wrap_text(draw, value, fnt, max_width, max_lines):
        draw.text((x, y), line, font=fnt, fill=fill)
        y += fnt.size + gap


def canvas() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", (W, H), BG)
    return img, ImageDraw.Draw(img)


def draw_round(draw: ImageDraw.ImageDraw, xy, fill: str = CARD, outline: str = LINE, radius: int = 24, width: int = 2) -> None:
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)


def draw_header(draw: ImageDraw.ImageDraw, f, title: str, subtitle: str, index: str, color: str = BLUE) -> None:
    draw.rounded_rectangle((54, 52, 146, 118), radius=20, fill=color)
    draw.text((78, 65), index, font=f.h3, fill="#ffffff")
    draw.text((170, 50), title, font=f.title, fill=INK)
    draw_wrapped(draw, (172, 122), subtitle, f.small, MUTED, 820, 2)


def roi_color(value: float, target_roi: float) -> str:
    if value >= target_roi:
        return GREEN
    return AMBER if value >= target_roi * 0.7 else RED


# ---------- 模块 01:KPI 判断 ----------

def draw_kpi_module(result: dict, f, output: Path) -> None:
    totals, target = result["totals"], float(result["target_roi"])
    roi = float(totals["roi"])
    label, action, color = _kpi_verdict(roi, target)
    img, d = canvas()
    draw_header(d, f, "今天先看一个判断", f"数据区间:{result['data_range']}", "01", color)

    draw_round(d, (56, 210, 1024, 612), fill=color, outline=color, radius=34, width=0)
    d.text((106, 260), "整体 ROI", font=f.h2, fill="#ffffff")
    d.text((100, 320), f"{roi:.2f}", font=f.big, fill="#ffffff")
    d.text((412, 365), f"目标 {target:.2f}", font=f.h2, fill="#ffffff")
    d.text((106, 485), label, font=f.h1, fill="#ffffff")
    d.text((106, 560), action, font=f.h3, fill="#ffffff")

    cards = [
        ("总消耗", money(totals["spend"]), "钱花在哪"),
        ("总 GMV", money(totals["gmv"]), "产出够不够"),
        ("订单数", str(int(totals["orders"])), "订单支撑判断"),
        ("CPO", money(totals["cpo"]), "单均获客成本"),
    ]
    for idx, (name, value, hint) in enumerate(cards):
        x, y = 56 + (idx % 2) * 496, 662 + (idx // 2) * 238
        draw_round(d, (x, y, x + 472, y + 204), radius=28)
        d.text((x + 36, y + 30), name, font=f.small, fill=MUTED)
        d.text((x + 36, y + 74), fit_text(d, value, f.h1, 390), font=f.h1, fill=INK)
        d.text((x + 36, y + 152), hint, font=f.small, fill=MUTED)

    draw_round(d, (56, 1168, 1024, 1326), fill="#fffdf7", outline="#f4d27a", radius=26)
    d.text((96, 1210), "读法", font=f.h3, fill=AMBER)
    draw_wrapped(d, (190, 1214), "低 ROI 不是直接关停。先看订单、素材、商品页、ROI Protection,再决定预算。", f.body, INK, 770, 2)
    img.save(output)


def _kpi_verdict(roi: float, target: float) -> tuple[str, str, str]:
    if roi >= target:
        return "达标", "先找可放量计划", GREEN
    if roi >= target * 0.7:
        return "接近目标", "先查高消耗计划", AMBER
    return "低于目标", "不要急停,先补证据", RED


# ---------- 模块 02:趋势 ----------

def draw_trend_module(result: dict, f, output: Path) -> None:
    days = result["days"][-21:]
    target = float(result["target_roi"])
    img, d = canvas()
    draw_header(d, f, "趋势比单日更重要", "蓝柱=消耗,红线=ROI,绿线=目标 ROI", "02")
    draw_round(d, (56, 218, 1024, 1114), radius=30)
    chart = (106, 330, 974, 948)
    d.rectangle(chart, fill="#fbfdff", outline="#e5e7eb", width=2)
    if days:
        _draw_spend_bars(d, chart, days)
        _draw_roi_line(d, f, chart, days, target)
        d.text((chart[0], chart[3] + 28), str(days[0]["day"])[5:], font=f.small, fill=MUTED)
        d.text((chart[2] - 88, chart[3] + 28), str(days[-1]["day"])[5:], font=f.small, fill=MUTED)
    latest = days[-1] if days else {"roi": 0, "spend": 0}
    draw_round(d, (96, 1180, 984, 1326), fill="#ffffff", radius=26)
    d.text((132, 1222), "最后一天", font=f.h3, fill=INK)
    d.text((344, 1224), f"ROI {float(latest['roi']):.2f}", font=f.h3, fill=roi_color(float(latest["roi"]), target))
    d.text((560, 1224), f"消耗 {money(float(latest['spend']))}", font=f.h3, fill=BLUE)
    img.save(output)


def _draw_spend_bars(draw: ImageDraw.ImageDraw, chart, days: list[dict]) -> None:
    max_spend = max([float(item["spend"]) for item in days] + [1])
    step = (chart[2] - chart[0]) / max(len(days), 1)
    bar_w = max(16, int(step * 0.55))
    for idx, item in enumerate(days):
        x = int(chart[0] + idx * step + (step - bar_w) / 2)
        height = int((float(item["spend"]) / max_spend) * (chart[3] - chart[1] - 90))
        draw.rounded_rectangle((x, chart[3] - height, x + bar_w, chart[3]), radius=8, fill="#bcd4ff")


def _draw_roi_line(draw: ImageDraw.ImageDraw, f, chart, days: list[dict], target: float) -> None:
    max_roi = max([target * 1.35] + [float(item["roi"]) for item in days])
    points = []
    for idx, item in enumerate(days):
        x = chart[0] + idx * (chart[2] - chart[0]) / max(len(days) - 1, 1)
        y = chart[3] - (float(item["roi"]) / max_roi) * (chart[3] - chart[1] - 80)
        points.append((x, y))
    target_y = chart[3] - (target / max_roi) * (chart[3] - chart[1] - 80)
    draw.line((chart[0], target_y, chart[2], target_y), fill=GREEN, width=5)
    if len(points) > 1:
        draw.line(points, fill=RED, width=7)
    for x, y in points[-5:]:
        draw.ellipse((x - 8, y - 8, x + 8, y + 8), fill=RED)
    draw.text((chart[0] + 28, chart[1] + 26), f"目标 ROI {target:.2f}", font=f.small, fill=GREEN)
    draw.text((chart[0] + 28, chart[1] + 66), "每日消耗", font=f.small, fill=BLUE)


# ---------- 模块 03:Top5 计划 ----------

def draw_top_module(result: dict, f, output: Path) -> None:
    items = result["campaigns"][:5]
    target = float(result["target_roi"])
    img, d = canvas()
    draw_header(d, f, "优先看这 5 个计划", "按消耗排序;颜色代表该不该先处理", "03")
    max_spend = max([float(item["spend"]) for item in items] + [1])
    y = 222
    for rank, item in enumerate(items, 1):
        _draw_campaign_row(d, f, rank, item, max_spend, target, y)
        y += 214
    draw_round(d, (56, 1264, 1024, 1354), fill="#ffffff", radius=24)
    d.text((96, 1294), "原则:Top 列表最多 5 行,更多明细回标准表 CSV。", font=f.body, fill=MUTED)
    img.save(output)


def _draw_campaign_row(draw: ImageDraw.ImageDraw, f, rank: int, item: dict, max_spend: float, target: float, y: int) -> None:
    roi, spend = float(item["roi"]), float(item["spend"])
    color = roi_color(roi, target)
    badge_bg = PALE_GREEN if color == GREEN else PALE_RED if color == RED else PALE_AMBER
    draw_round(draw, (56, y, 1024, y + 176), fill=CARD, radius=28)
    draw.rounded_rectangle((92, y + 34, 152, y + 94), radius=18, fill=color)
    draw.text((112 if rank < 10 else 104, y + 43), str(rank), font=f.h3, fill="#ffffff")
    draw.text((176, y + 30), fit_text(draw, str(item["name"]), f.body_b, 580), font=f.body_b, fill=INK)
    draw.text((176, y + 80), f"消耗 {money(spend)}  /  订单 {int(item['orders'])}", font=f.small, fill=MUTED)
    draw.rounded_rectangle((176, y + 124, 708, y + 150), radius=13, fill="#eef2f7")
    bar_w = int((spend / max_spend) * 532)
    draw.rounded_rectangle((176, y + 124, 176 + max(18, bar_w), y + 150), radius=13, fill=color)
    draw.rounded_rectangle((746, y + 42, 974, y + 104), radius=20, fill=badge_bg)
    draw.text((776, y + 54), f"ROI {roi:.2f}", font=f.h3, fill=color)


# ---------- 模块 04:今日动作 ----------

def draw_action_module(result: dict, f, output: Path) -> None:
    img, d = canvas()
    draw_header(d, f, "今天只做 3 件事", "日报不是复盘表,是行动单", "04")
    blocks = [
        ("1", "放量候选", GREEN, _scalable_text(result)),
        ("2", "优先诊断", RED, _risk_text(result)),
        ("3", "闭环记录", BLUE, "把今天的调整写回表格,明天对比调整前后 ROI、订单数和 CPO。"),
    ]
    y = 236
    for num_text, title, color, body in blocks:
        draw_round(d, (56, y, 1024, y + 248), fill=CARD, radius=30)
        d.rounded_rectangle((96, y + 54, 178, y + 136), radius=24, fill=color)
        d.text((122, y + 72), num_text, font=f.h2, fill="#ffffff")
        d.text((218, y + 54), title, font=f.h2, fill=color)
        draw_wrapped(d, (218, y + 116), body, f.body, INK, 720, 3, 12)
        y += 316
    draw_round(d, (56, 1220, 1024, 1344), fill="#ffffff", radius=26)
    draw_wrapped(d, (96, 1255), "低 ROI 先补证据;高 ROI 也要看订单量和库存。不要让图替你做没有证据的决定。", f.body, MUTED, 900, 2)
    img.save(output)


def _short(value: str) -> str:
    return value if len(value) <= 22 else value[:19] + "..."


def _scalable_text(result: dict) -> str:
    items = result["scalable"][:2]
    if not items:
        return "暂无稳定过线计划。先找订单不少且 ROI 接近目标的计划,补素材后再测。"
    names = ";".join(f"{_short(item['name'])} ROI {float(item['roi']):.2f}" for item in items)
    return f"{names}。先加 10%-20%,明天复查。"


def _risk_text(result: dict) -> str:
    items = result["risks"][:2]
    if not items:
        return "暂无高消耗低 ROI 计划。保持预算,继续看趋势。"
    names = ";".join(f"{_short(item['name'])} ROI {float(item['roi']):.2f}" for item in items)
    return f"{names}。先补商品页、素材、ROI Protection 截图。"


# ---------- 总入口 ----------

MODULES = [
    ("kpi", "01 今天先看一个判断", draw_kpi_module),
    ("trend", "02 趋势比单日更重要", draw_trend_module),
    ("top_spend", "03 优先看这 5 个计划", draw_top_module),
    ("actions", "04 今天只做 3 件事", draw_action_module),
]


def render_modules(result: dict, module_dir: Path, report_date: str, font_paths: list[str] | None = None) -> dict:
    """出 4 张模块图 + manifest.json(send 子命令按 manifest 上传)。"""
    module_dir.mkdir(parents=True, exist_ok=True)
    fonts = load_fonts(font_paths)
    modules = []
    for order, (module_id, title, draw_fn) in enumerate(MODULES, 1):
        output = module_dir / f"{report_date}-{order:02d}-{module_id}.png"
        draw_fn(result, fonts, output)
        modules.append({"id": module_id, "title": title, "file": str(output)})
    manifest = {
        "report_date": report_date,
        "target_roi": float(result["target_roi"]),
        "data_range": result["data_range"],
        "image_size": {"width": W, "height": H},
        "totals": result["totals"],
        "modules": modules,
    }
    write_json(module_dir.parent / "module-manifest.json", manifest)
    return manifest
