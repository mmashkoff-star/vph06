from __future__ import annotations

from typing import Any

DEADLINE_HOT = ("сегодня", "срочно", "немедлен", "asap", "в течение дня", "прямо сейчас", "горит")
DEADLINE_SOON = ("завтра", "1 день", "2 дня", "выходн", "ближайш")
DEADLINE_WEEK = ("недел", "7 дн")
DEADLINE_COLD = ("месяц", "не горит", "когда удобно", "без срока", "не срочно", "когда будет слот")
PRESTIGE = ("rolls", "ferrari", "bentley", "lamborghini", "maybach")
HIGH = ("porsche", "aston", "maserati")
DEPARTMENTS = (
    ("сезонн", "Сопровождение / консьерж"),
    ("сопровожд", "Сопровождение / консьерж"),
    ("ppf", "PPF / антигравий"),
    ("антиграв", "PPF / антигравий"),
    ("детейл", "Детейлинг"),
    ("керамик", "Детейлинг"),
    ("кузов", "Кузов и цвет"),
    ("салон", "Салон и кожа"),
    ("диагност", "Сервис и ТО"),
    (" т.о", "Сервис и ТО"),
    ("то", "Сервис и ТО"),
)


def _text(*parts: Any) -> str:
    return " ".join(str(part or "") for part in parts).lower()


def _budget(raw: Any) -> int:
    digits = "".join(ch for ch in str(raw or "") if ch.isdigit())
    return int(digits) if digits else 0


def _year(raw: Any) -> int:
    digits = "".join(ch for ch in str(raw or "") if ch.isdigit())
    year = int(digits[:4]) if len(digits) >= 4 else 0
    return year if 1950 <= year <= 2100 else 0


def _department(service: str, work: str) -> str:
    blob = f"{service} {work}"
    for needle, title in DEPARTMENTS:
        if needle in blob:
            return title
    return "Приём заявок"


def analyze_lead(lead: dict[str, Any]) -> dict[str, Any]:
    score = 0
    signals: list[str] = []
    timing = _text(lead.get("needed_by"), lead.get("comments"))
    work = _text(lead.get("work_type"), lead.get("work_area"), lead.get("visit_format"))
    service = _text(lead.get("service"))
    role = _text(lead.get("booked_by"))
    make = _text(lead.get("make"))
    contact = _text(lead.get("preferred_contact"))
    budget = _budget(lead.get("budget"))
    year = _year(lead.get("year"))

    if any(token in timing for token in DEADLINE_COLD):
        score += 1
        signals.append("срок спокойный")
    elif any(token in timing for token in DEADLINE_HOT):
        score += 38
        signals.append("срок горит")
    elif any(token in timing for token in DEADLINE_SOON):
        score += 18
        signals.append("срок ближайшие дни")
    elif any(token in timing for token in DEADLINE_WEEK):
        score += 10
        signals.append("горизонт около недели")
    else:
        score += 4

    if budget >= 2_500_000:
        score += 28
        signals.append("бюджет очень высокий")
    elif budget >= 1_200_000:
        score += 16
        signals.append("бюджет высокий")
    elif budget >= 450_000:
        score += 10
        signals.append("бюджет рабочий")
    elif budget >= 150_000:
        score += 6
    else:
        score += 1
        if budget:
            signals.append("бюджет скромный")

    if "сезонн" in service or "сопровожд" in service or "сезонн" in work or "сопровожд" in work:
        score += 18
        signals.append("сезонное сопровождение")
    elif "полный кузов" in work or "полный комплекс" in work:
        score += 14
        signals.append("полный объём работ")
    elif "ppf" in service or "антиграв" in service:
        score += 10
        signals.append("зона PPF")
    elif "кузов" in service:
        score += 9
    elif "детейл" in service or "керамик" in service:
        score += 7
    elif "салон" in service:
        score += 6
    else:
        score += 4

    if "персональн" in work or "персональн" in timing:
        score += 6
        signals.append("просит персональный слот")

    if role == "owner":
        score += 10
        signals.append("пишет владелец")
    elif role == "assistant":
        score += 6
        signals.append("пишет ассистент")
    elif role == "driver":
        score += 2
        signals.append("пишет водитель")

    if any(brand in make for brand in PRESTIGE):
        score += 9
        signals.append("премиум-бренд")
    elif any(brand in make for brand in HIGH):
        score += 5

    if year >= 2024:
        score += 6
        signals.append("свежий автомобиль")
    elif year and year < 2000:
        score += 2

    if lead.get("phone") and lead.get("preferred_contact"):
        score += 4
    if lead.get("email"):
        score += 2
    if "звонок" in contact:
        score += 3
        signals.append("готов говорить сразу")

    score = min(100, score)
    if score >= 66:
        heat = "hot"
        heat_label = "Горячий"
        worth = True
        worth_label = "Брать сразу: время окупается"
    elif score >= 44:
        heat = "warm"
        heat_label = "Теплый"
        worth = True
        worth_label = "В очередь: стоит внимания"
    else:
        heat = "cold"
        heat_label = "Холодный"
        worth = False
        worth_label = "Не тратить персонального менеджера"

    personal = (
        score >= 68
        or "сезонн" in service
        or "сопровожд" in service
        or budget >= 1_800_000
        or (any(brand in make for brand in PRESTIGE) and role == "owner")
    )
    department = _department(service, work)
    return {
        "score": score,
        "heat": heat,
        "heat_label": heat_label,
        "temperature": score,
        "worth_time": worth,
        "worth_label": worth_label,
        "personal_manager": personal,
        "personal_label": "Нужен персональный менеджер" if personal else "Общая очередь ресепшена",
        "department": department,
        "signals": signals,
    }


def enrich_lead(lead: dict[str, Any]) -> dict[str, Any]:
    row = dict(lead)
    row["insight"] = analyze_lead(row)
    return row


def summarize_leads(rows: list[dict[str, Any]]) -> dict[str, Any]:
    heats = {"hot": 0, "warm": 0, "cold": 0}
    budgets = []
    personal = 0
    for row in rows:
        insight = row.get("insight") or analyze_lead(row)
        heats[insight["heat"]] = heats.get(insight["heat"], 0) + 1
        if insight.get("personal_manager"):
            personal += 1
        value = _budget(row.get("budget"))
        if value:
            budgets.append(value)
    return {
        "total": len(rows),
        "hot": heats["hot"],
        "warm": heats["warm"],
        "cold": heats["cold"],
        "personal_manager": personal,
        "avg_budget": int(sum(budgets) / len(budgets)) if budgets else 0,
        "max_budget": max(budgets) if budgets else 0,
    }
