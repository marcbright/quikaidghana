"""
SOS page: fixed service slots (Police, Fire, Ambulance, ECG, GWCL) merged with
EmergencyContact rows by keyword. Unmatched contacts stay in "Other helplines".
Fallback numbers are common public Ghana lines — admins can override by adding contacts
whose names include the slot keywords (e.g. "Police", "ECG").
"""

from __future__ import annotations

import re
from typing import Any, Iterable

# Ordered: first match consumes a contact from the pool.
SOS_SLOTS: tuple[dict[str, Any], ...] = (
    {
        "key": "police",
        "title": "Police",
        "subtitle": "Crime, danger, or immediate police response",
        "keywords": ("police", "law enforcement"),
        "fallback_phone": "191",
    },
    {
        "key": "fire",
        "title": "Fire Service",
        "subtitle": "Fire, smoke, rescue, hazardous materials",
        "keywords": ("fire", "gnfs", "fire service"),
        "fallback_phone": "192",
    },
    {
        "key": "ambulance",
        "title": "Ambulance",
        "subtitle": "Medical emergency & ambulance dispatch",
        "keywords": ("ambulance", "nas", "medical emergency"),
        "fallback_phone": "193",
    },
    {
        "key": "ecg",
        "title": "ECG",
        "subtitle": "Power faults, dangerous lines, outages (Electricity Company of Ghana)",
        "keywords": ("ecg", "electricity company", "power company"),
        "fallback_phone": "0302611611",
    },
    {
        "key": "water",
        "title": "Water Company",
        "subtitle": "Burst pipes, no supply, billing (Ghana Water — GWCL)",
        "keywords": ("water", "gwcl", "ghana water"),
        "fallback_phone": "080040000",
    },
)


def tel_href(phone: str) -> str:
    """Build a tel: URI for mobile tap-to-call."""
    raw = (phone or "").strip()
    if not raw:
        return "#"
    compact = re.sub(r"[\s\-.]", "", raw)
    if compact.startswith("+"):
        return "tel:" + compact
    if compact.isdigit() and len(compact) <= 3:
        return f"tel:{compact}"
    if compact.startswith("0") and len(compact) >= 10:
        return "tel:+233" + compact[1:]
    return "tel:" + compact


def phone_display(phone: str) -> str:
    """Human-friendly spacing for large type (light formatting only)."""
    p = (phone or "").strip()
    if not p:
        return "—"
    if re.fullmatch(r"\d{3}", re.sub(r"\D", "", p)):
        return p
    return p


def build_sos_page_context(
    contacts: Iterable[Any],
    hospitals: Iterable[Any],
    *,
    max_hospitals: int = 36,
) -> dict[str, Any]:
    pool = list(contacts)
    cards: list[dict[str, Any]] = []

    for slot in SOS_SLOTS:
        match_index = None
        match = None
        for i, c in enumerate(pool):
            name_l = (c.service_name or "").lower()
            if any(k in name_l for k in slot["keywords"]):
                match_index = i
                match = c
                break

        if match is not None and match_index is not None:
            pool.pop(match_index)
            phone = (match.phone_number or "").strip() or slot["fallback_phone"]
            from_db = True
            directory_line = match.service_name
        else:
            phone = slot["fallback_phone"]
            from_db = False
            directory_line = ""

        cards.append(
            {
                "key": slot["key"],
                "title": slot["title"],
                "subtitle": slot["subtitle"],
                "phone": phone,
                "phone_display": phone_display(phone),
                "tel_href": tel_href(phone),
                "from_database": from_db,
                "directory_line": directory_line,
            }
        )

    extras = [{"contact": c, "tel_href": tel_href(c.phone_number)} for c in pool]

    return {
        "sos_cards": cards,
        "sos_extras": extras,
        "hospitals": list(hospitals)[:max_hospitals],
    }
