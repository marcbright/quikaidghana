"""
QuickAid assistant — rule / keyword matching on live Django data (no external LLM).
"""

from __future__ import annotations

import re
from typing import Any

from django.db.models import Q

from .models import EmergencyContact, Hospital, Report, ReportCategory

MAX_CARDS = 10
MAX_INTRO = 280

# Longer phrases first so substrings (e.g. "accra" inside a longer name) still work sensibly.
GHANA_PLACES: tuple[str, ...] = (
    "greater accra",
    "ashanti region",
    "northern region",
    "east legon",
    "west hills",
    "cape coast",
    "tema motorway",
    "lapaz",
    "madina",
    "spintex",
    "ring road",
    "nima",
    "osu",
    "kasoa",
    "bolgatanga",
    "koforidua",
    "techiman",
    "sunyani",
    "takoradi",
    "sekondi",
    "tamale",
    "kumasi",
    "accra",
    "tema",
)

DEFAULT_HINTS = [
    "hospital near me",
    "light off",
    "fuel nearby",
    "traffic accra",
    "water shortage",
    "SOS numbers",
]


def _norm(message: str) -> str:
    return " ".join(message.lower().strip().split())


def _place_filter(msg: str) -> Q | None:
    """Return OR filter for location/description if a known place appears in the message."""
    hits: list[str] = []
    for place in sorted(GHANA_PLACES, key=len, reverse=True):
        if place in msg:
            hits.append(place)
    padded = f" {msg} "
    for short in (" ho ", " wa "):
        if short in padded and short.strip() not in hits:
            hits.append(short.strip())
    if not hits:
        return None
    q = Q()
    for h in hits:
        q |= Q(location__icontains=h) | Q(description__icontains=h)
    return q


def _report_cards(qs) -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = []
    for r in qs[:MAX_CARDS]:
        desc = (r.description or "").strip()
        if len(desc) > 140:
            desc = desc[:137] + "…"
        cards.append(
            {
                "kind": "report",
                "category": r.category,
                "category_label": r.get_category_display(),
                "title": (r.location or "Unknown place")[:120],
                "subtitle": desc or "No extra detail.",
                "status": r.status,
                "status_label": r.get_status_display(),
                "when_iso": r.created_at.isoformat(),
            }
        )
    return cards


def _hospital_cards(qs) -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = []
    for h in qs[:MAX_CARDS]:
        cards.append(
            {
                "kind": "hospital",
                "title": h.name,
                "subtitle": h.location,
                "phone": (h.phone or "").strip(),
                "has_coords": h.latitude is not None and h.longitude is not None,
            }
        )
    return cards


def _contact_cards(qs) -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = []
    for c in qs[:MAX_CARDS]:
        cards.append(
            {
                "kind": "contact",
                "title": c.service_name,
                "subtitle": c.phone_number,
            }
        )
    return cards


def _payload(
    *,
    intent: str,
    intro: str,
    cards: list[dict[str, Any]],
    hints: list[str] | None = None,
    links: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    intro = intro[:MAX_INTRO]
    return {
        "intent": intent,
        "intro": intro,
        "cards": cards,
        "hints": hints or DEFAULT_HINTS[:6],
        "links": links or [],
    }


def _is_greeting(msg: str) -> bool:
    greetings = (
        "hi ",
        " hi",
        "hello",
        "hey ",
        " hey",
        "good morning",
        "good afternoon",
        "good evening",
        "thanks",
        "thank you",
        "ok ",
        " okay",
        "help",
        "start",
        "what can you",
        "what do you",
    )
    if msg in ("hi", "hey", "hello", "yo", "help", "start"):
        return True
    return any(g in msg for g in greetings)


def _is_sos_query(msg: str) -> bool:
    if "sos" in msg:
        return True
    if "helpline" in msg or "help line" in msg:
        return True
    if "emergency" in msg and any(
        w in msg for w in ("number", "contact", "phone", "line", "call", "hotline")
    ):
        return True
    if "ambulance" in msg and "hospital" not in msg and "clinic" not in msg:
        return True
    if re.search(r"\b(112|193|191|192|194|195)\b", msg):
        return True
    return False


def _is_dumsor_query(msg: str) -> bool:
    if "traffic light" in msg or "traffic lights" in msg:
        return False
    if "dumsor" in msg:
        return True
    phrases = (
        "light off",
        "lights off",
        "no light",
        "no lights",
        "power outage",
        "power cut",
        "power is out",
        "power out",
        "blackout",
        "lights are out",
        "gone off",  # colloquial
        "no electricity",
        "no current",
    )
    return any(p in msg for p in phrases)


def _is_hospital_query(msg: str) -> bool:
    return any(
        k in msg
        for k in (
            "hospital",
            "clinic",
            "health center",
            "health centre",
            "medical center",
            "medical centre",
        )
    )


def _is_fuel_query(msg: str) -> bool:
    if any(k in msg for k in ("fuel", "petrol", "diesel", "filling station", "gas station", "pump")):
        if "traffic" in msg and "fuel" not in msg:
            return False
        return True
    if "queue" in msg and ("station" in msg or "shell" in msg or "goil" in msg):
        return True
    return False


def _is_traffic_query(msg: str) -> bool:
    return any(k in msg for k in ("traffic", "jam", "congestion", "roadblock", "road block"))


def _is_water_query(msg: str) -> bool:
    return any(
        k in msg
        for k in (
            "water shortage",
            "no water",
            "tap dry",
            "taps dry",
            "water cut",
            "water outage",
            "pipe burst",
        )
    ) or ("water" in msg and any(x in msg for x in ("shortage", "supply", "tanker", "tap")))


def _is_flood_query(msg: str) -> bool:
    return any(k in msg for k in ("flood", "flooding", "submerged", "overflow"))


def _is_accident_query(msg: str) -> bool:
    return any(k in msg for k in ("accident", "crash", "collision", "pile-up", "pile up"))


def process_chat_message(message: str) -> dict[str, Any]:
    """
    Classify the visitor message and return structured data for the chat UI.
    """
    msg = _norm(message)
    if not msg:
        return _payload(
            intent="empty",
            intro="Ask about hospitals, power (dumsor), fuel queues, traffic, water, or type SOS for helplines.",
            cards=[],
            hints=DEFAULT_HINTS,
            links=[{"label": "Report an issue", "href": "/report/"}],
        )

    if _is_greeting(msg) and len(msg) < 48 and not any(
        c in msg for c in ("hospital", "traffic", "fuel", "water", "flood", "accident", "dumsor", "light")
    ):
        return _payload(
            intent="greeting",
            intro=(
                "Hi — I match your question to QuickAid data (no paid API). "
                "Try one of the shortcuts below, or describe what you need in plain English."
            ),
            cards=[],
            hints=DEFAULT_HINTS,
            links=[
                {"label": "Live map", "href": "/map/"},
                {"label": "Submit report", "href": "/report/"},
            ],
        )

    place_q = _place_filter(msg)

    if _is_sos_query(msg):
        qs = EmergencyContact.objects.order_by("service_name")
        cards = _contact_cards(qs)
        intro = (
            "Here are emergency and helpline contacts from our directory. "
            "For life-threatening emergencies, call the appropriate national line first."
            if cards
            else "No emergency contacts are in the database yet — ask an admin to add them."
        )
        return _payload(
            intent="sos",
            intro=intro,
            cards=cards,
            hints=["hospital near me", "traffic accra", "fuel nearby"],
            links=[{"label": "SOS page", "href": "/sos/"}],
        )

    if _is_hospital_query(msg):
        qs = Hospital.objects.order_by("name")
        cards = _hospital_cards(qs)
        intro = (
            f"I found {len(cards)} hospital(s) and clinics in QuickAid. "
            '"Near me" lists everyone we have — precise GPS routing can be added later.'
            if cards
            else "No hospitals are listed yet. Admins can add them in the dashboard."
        )
        return _payload(
            intent="hospitals",
            intro=intro,
            cards=cards,
            hints=["traffic accra", "light off", "SOS numbers"],
            links=[{"label": "Map", "href": "/map/"}],
        )

    if _is_dumsor_query(msg):
        qs = Report.objects.filter(category=ReportCategory.DUMSOR).order_by("-created_at")
        if place_q is not None:
            qs = qs.filter(place_q)
        cards = _report_cards(qs)
        place_note = " (filtered by the place you named)" if place_q is not None else ""
        intro = (
            f"Recent dumsor / power-related reports{place_note} — newest first."
            if cards
            else "No dumsor reports on file yet. Submit what you see on the report form."
        )
        return _payload(
            intent="dumsor",
            intro=intro,
            cards=cards,
            hints=["fuel nearby", "water shortage", "hospital near me"],
            links=[{"label": "All reports", "href": "/reports/?category=dumsor"}],
        )

    if _is_water_query(msg):
        qs = Report.objects.filter(category=ReportCategory.WATER_SHORTAGE).order_by("-created_at")
        if place_q is not None:
            qs = qs.filter(place_q)
        cards = _report_cards(qs)
        intro = (
            "Water shortage reports from citizens (newest first)."
            if cards
            else "No water shortage reports yet — be the first to report."
        )
        return _payload(
            intent="water",
            intro=intro,
            cards=cards,
            hints=["flooding", "traffic accra", "hospital near me"],
            links=[{"label": "Filter reports", "href": "/reports/?category=water_shortage"}],
        )

    if _is_flood_query(msg):
        qs = Report.objects.filter(category=ReportCategory.FLOODING).order_by("-created_at")
        if place_q is not None:
            qs = qs.filter(place_q)
        cards = _report_cards(qs)
        intro = "Flooding reports (newest first)." if cards else "No flooding reports on file yet."
        return _payload(
            intent="flooding",
            intro=intro,
            cards=cards,
            hints=["accident nearby", "traffic tema", "SOS numbers"],
            links=[{"label": "Reports", "href": "/reports/?category=flooding"}],
        )

    if _is_accident_query(msg):
        qs = Report.objects.filter(category=ReportCategory.ACCIDENT).order_by("-created_at")
        if place_q is not None:
            qs = qs.filter(place_q)
        cards = _report_cards(qs)
        intro = "Accident reports (newest first)." if cards else "No accident reports on file yet."
        return _payload(
            intent="accident",
            intro=intro,
            cards=cards,
            hints=["traffic accra", "hospital near me", "SOS numbers"],
            links=[{"label": "Reports", "href": "/reports/?category=accident"}],
        )

    if _is_fuel_query(msg):
        qs = Report.objects.filter(category=ReportCategory.FUEL_QUEUE).order_by("-created_at")
        if place_q is not None:
            qs = qs.filter(place_q)
        cards = _report_cards(qs)
        intro = (
            "Fuel queue and station alerts from recent reports."
            if cards
            else "No fuel queue reports yet — submit one if stations are crowded."
        )
        return _payload(
            intent="fuel_queue",
            intro=intro,
            cards=cards,
            hints=["traffic accra", "light off", "hospital near me"],
            links=[{"label": "Reports", "href": "/reports/?category=fuel_queue"}],
        )

    if _is_traffic_query(msg):
        qs = Report.objects.filter(category=ReportCategory.TRAFFIC).order_by("-created_at")
        if place_q is not None:
            qs = qs.filter(place_q)
        cards = _report_cards(qs)
        intro = (
            "Traffic-related citizen reports (newest first)."
            if cards
            else "No traffic reports match yet — try naming a city (e.g. traffic Kumasi) or submit a report."
        )
        return _payload(
            intent="traffic",
            intro=intro,
            cards=cards,
            hints=["fuel nearby", "accident nearby", "hospital near me"],
            links=[{"label": "Reports", "href": "/reports/?category=traffic"}],
        )

    # Keyword overlap: map / report / about
    if "map" in msg and "report" not in msg:
        return _payload(
            intent="nav_map",
            intro="Open the live map for geo reports and hospitals with coordinates.",
            cards=[],
            hints=DEFAULT_HINTS,
            links=[{"label": "Open map", "href": "/map/"}],
        )

    return _payload(
        intent="unknown",
        intro=(
            "I could not match that to a category yet. Try: hospital near me, light off, "
            "fuel nearby, traffic Accra, water shortage, or SOS numbers."
        ),
        cards=[],
        hints=DEFAULT_HINTS,
        links=[
            {"label": "How to report", "href": "/report/"},
            {"label": "Browse reports", "href": "/reports/"},
        ],
    )
