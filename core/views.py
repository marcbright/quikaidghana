import csv
import difflib
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

from django.core.paginator import Paginator
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_http_methods

from .chatbot_logic import process_chat_message
from .forms import FeedbackForm, ReportForm
from .models import (
    EmergencyContact,
    Feedback,
    Hospital,
    PowerSchedule,
    Report,
    ReportCategory,
    ReportStatus,
)
from .sos_cards import build_sos_page_context


# -----------------------------------------------------------------------------
# Public pages
# -----------------------------------------------------------------------------


def home(request):
    now = timezone.now()
    week_ago = now - timedelta(days=7)

    latest_outages = (
        Report.objects.filter(category=ReportCategory.DUMSOR)
        .order_by("-created_at")[:3]
    )
    latest_reports = Report.objects.order_by("-created_at")[:3]

    city_chips = [
        {"label": "All Ghana", "query": ""},
        {"label": "Accra", "query": "accra"},
        {"label": "Kumasi", "query": "kumasi"},
        {"label": "Tema", "query": "tema"},
        {"label": "Takoradi", "query": "takoradi"},
        {"label": "Tamale", "query": "tamale"},
    ]

    incident_feed = []
    for r in Report.objects.order_by("-created_at")[:100]:
        incident_feed.append(
            {
                "id": r.id,
                "category_key": r.category,
                "category": r.get_category_display(),
                "location": r.location,
                "status": r.get_status_display(),
                "created_at": r.created_at.isoformat(),
                "created_label": timezone.localtime(r.created_at).strftime("%a %-d %b · %H:%M"),
                "lat": float(r.latitude) if r.latitude is not None else None,
                "lng": float(r.longitude) if r.longitude is not None else None,
                "is_outage": r.category == ReportCategory.DUMSOR,
            }
        )

    stats = {
        "reports_total": Report.objects.count(),
        "reports_week": Report.objects.filter(created_at__gte=week_ago).count(),
        "reports_pending": Report.objects.filter(status=ReportStatus.PENDING).count(),
        "hospitals_total": Hospital.objects.count(),
        "contacts_total": EmergencyContact.objects.count(),
    }

    today = timezone.localdate()
    trust_counts = {
        "verified_by_operator": Report.objects.exclude(status=ReportStatus.PENDING).count(),
        "community_pending": Report.objects.filter(status=ReportStatus.PENDING).count(),
        "resolved_today": Report.objects.filter(
            status__in=[ReportStatus.RESOLVED, ReportStatus.CLOSED],
            created_at__date=today,
        ).count(),
    }

    return render(
        request,
        "core/home.html",
        {
            "stats": stats,
            "latest_outages": latest_outages,
            "latest_reports": latest_reports,
            "city_chips": city_chips,
            "incident_feed": incident_feed,
            "trust_counts": trust_counts,
        },
    )


def about(request):
    return render(request, "core/about.html")


@require_http_methods(["GET", "POST"])
def contact(request):
    if request.method == "POST":
        form = FeedbackForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect(f"{reverse('core:contact')}?submitted=1")
        form.highlight_errors()
    else:
        form = FeedbackForm()
    return render(
        request,
        "core/contact.html",
        {
            "form": form,
            "feedback_submitted": request.GET.get("submitted") == "1",
        },
    )


@ensure_csrf_cookie
def chatbot(request):
    return render(request, "core/chatbot.html")


@require_http_methods(["POST"])
def chatbot_reply(request):
    """JSON assistant reply — keyword routing over local models (no paid API)."""
    try:
        data = json.loads(request.body.decode("utf-8") or "{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "invalid_json"}, status=400)
    message = (data.get("message") or "").strip()
    if len(message) > 500:
        return JsonResponse({"error": "too_long"}, status=400)
    payload = process_chat_message(message)
    return JsonResponse(payload)


@require_http_methods(["GET"])
def geocode_search(request):
    """Proxy Nominatim (OSM) search — browser-friendly, correct User-Agent for usage policy."""
    q = (request.GET.get("q") or "").strip()
    if len(q) < 2:
        return JsonResponse({"results": []})
    if len(q) > 200:
        return JsonResponse({"results": [], "error": "query_too_long"}, status=400)

    params = urllib.parse.urlencode(
        {
            "q": q,
            "format": "jsonv2",
            "limit": "8",
            "countrycodes": "gh",
            "addressdetails": "0",
        }
    )
    url = f"https://nominatim.openstreetmap.org/search?{params}"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "QuickAidGhana/1.0 (+https://github.com/quickaid-ghana; contact via site admin)",
            "Accept": "application/json",
            "Accept-Language": "en",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            payload = json.loads(resp.read().decode())
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError, json.JSONDecodeError):
        return JsonResponse({"results": [], "error": "geocode_unavailable"}, status=200)

    results = []
    for item in payload:
        try:
            lat = float(item["lat"])
            lon = float(item["lon"])
        except (KeyError, TypeError, ValueError):
            continue
        label = (item.get("display_name") or "")[:400]
        results.append({"lat": lat, "lng": lon, "label": label})
    return JsonResponse({"results": results})


# -----------------------------------------------------------------------------
# Incidents & map
# -----------------------------------------------------------------------------


@require_http_methods(["GET", "POST"])
def report(request):
    if request.method == "POST":
        form = ReportForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect(f"{reverse('core:report')}?submitted=1")
        form.highlight_errors()
    else:
        form = ReportForm()
    return render(
        request,
        "core/report.html",
        {
            "form": form,
            "report_submitted": request.GET.get("submitted") == "1",
        },
    )


def reports_list(request):
    queryset = Report.objects.order_by("-created_at")

    search_q = (request.GET.get("q") or "").strip()
    category_key = (request.GET.get("category") or "").strip()
    valid_categories = {c.value for c in ReportCategory}

    if search_q:
        queryset = queryset.filter(location__icontains=search_q)
    if category_key and category_key in valid_categories:
        queryset = queryset.filter(category=category_key)

    paginator = Paginator(queryset, 12)
    page_obj = paginator.get_page(request.GET.get("page"))

    query_params = request.GET.copy()
    query_params.pop("page", None)
    extra_query = query_params.urlencode()

    total_in_db = Report.objects.count()
    has_filters = bool(search_q or (category_key and category_key in valid_categories))

    return render(
        request,
        "core/reports_list.html",
        {
            "page_obj": page_obj,
            "search_q": search_q,
            "filter_category": category_key if category_key in valid_categories else "",
            "category_choices": ReportCategory.choices,
            "extra_query": extra_query,
            "total_in_db": total_in_db,
            "has_filters": has_filters,
        },
    )


def map_page(request):
    reports = list(
        Report.objects.filter(latitude__isnull=False, longitude__isnull=False).order_by(
            "-created_at"
        )[:300]
    )
    hospitals = list(
        Hospital.objects.filter(latitude__isnull=False, longitude__isnull=False).order_by(
            "name"
        )[:200]
    )

    report_markers = [
        {
            "id": r.id,
            "lat": float(r.latitude),
            "lng": float(r.longitude),
            "category_key": r.category,
            "category": r.get_category_display(),
            "location": r.location,
            "status": r.get_status_display(),
            "description": (r.description or "")[:600],
            "created_at": r.created_at.isoformat(),
        }
        for r in reports
    ]
    hospital_markers = [
        {
            "id": h.id,
            "lat": float(h.latitude),
            "lng": float(h.longitude),
            "name": h.name,
            "location": h.location,
        }
        for h in hospitals
    ]

    reports_missing_coords = Report.objects.filter(
        Q(latitude__isnull=True) | Q(longitude__isnull=True)
    ).count()

    return render(
        request,
        "core/map.html",
        {
            "report_markers": report_markers,
            "hospital_markers": hospital_markers,
            "reports_missing_coords": reports_missing_coords,
        },
    )


# -----------------------------------------------------------------------------
# Safety & operations
# -----------------------------------------------------------------------------


def sos(request):
    contacts = EmergencyContact.objects.order_by("service_name")
    hospitals = Hospital.objects.order_by("name")
    ctx = build_sos_page_context(contacts, hospitals)
    return render(request, "core/sos.html", ctx)


def dashboard(request):
    today = timezone.localdate()
    city_options = [
        ("all", "All"),
        ("accra", "Accra"),
        ("kumasi", "Kumasi"),
        ("tema", "Tema"),
        ("tamale", "Tamale"),
        ("takoradi", "Takoradi"),
    ]
    city_lookup = {value: label for value, label in city_options}
    selected_city = (request.GET.get("city") or "all").strip().lower()
    if selected_city not in city_lookup:
        selected_city = "all"

    reports_qs = Report.objects.all()
    if selected_city != "all":
        reports_qs = reports_qs.filter(location__icontains=city_lookup[selected_city])

    reports_today = reports_qs.filter(created_at__date=today).count()
    fuel_alerts_today = reports_qs.filter(
        created_at__date=today,
        category=ReportCategory.FUEL_QUEUE,
    ).count()
    traffic_today = reports_qs.filter(
        created_at__date=today,
        category=ReportCategory.TRAFFIC,
    ).count()
    dumsor_today = reports_qs.filter(
        created_at__date=today,
        category=ReportCategory.DUMSOR,
    ).count()
    hospitals_geo = Hospital.objects.filter(
        latitude__isnull=False,
        longitude__isnull=False,
    ).count()
    hospitals_total = Hospital.objects.count()

    status_rows = reports_qs.values("status").annotate(total=Count("id")).order_by("-total")
    status_labels = {s.value: s.label for s in ReportStatus}
    reports_by_status = [
        {"status": row["status"], "label": status_labels.get(row["status"], row["status"]), "total": row["total"]}
        for row in status_rows
    ]

    chart_day_labels: list[str] = []
    chart_day_values: list[int] = []
    for offset in range(13, -1, -1):
        day = today - timedelta(days=offset)
        chart_day_labels.append(day.strftime("%a %d"))
        chart_day_values.append(reports_qs.filter(created_at__date=day).count())

    category_rows = list(
        reports_qs.values("category").annotate(total=Count("id")).order_by("-total")
    )
    choice_labels = dict(ReportCategory.choices)
    chart_cat_labels = [choice_labels.get(r["category"], r["category"]) for r in category_rows]
    chart_cat_values = [r["total"] for r in category_rows]

    recent_reports = list(reports_qs.order_by("-created_at")[:15])

    verified_by_operator = reports_qs.exclude(status=ReportStatus.PENDING).count()
    pending_queue = reports_qs.filter(status=ReportStatus.PENDING).count()
    resolved_today = reports_qs.filter(
        status__in=[ReportStatus.RESOLVED, ReportStatus.CLOSED],
        created_at__date=today,
    ).count()

    queue_threshold_minutes = 120
    queue_threshold = timezone.now() - timedelta(minutes=queue_threshold_minutes)
    critical_queue_count = reports_qs.filter(
        status=ReportStatus.PENDING,
        created_at__lt=queue_threshold,
    ).count()

    reports_total = reports_qs.count()
    missing_geo_count = reports_qs.filter(Q(latitude__isnull=True) | Q(longitude__isnull=True)).count()
    map_ready_count = max(reports_total - missing_geo_count, 0)
    map_ready_percent = round((map_ready_count / reports_total) * 100, 1) if reports_total else 0

    severity_weights = {
        ReportCategory.DUMSOR: 45,
        ReportCategory.FLOODING: 42,
        ReportCategory.ACCIDENT: 40,
        ReportCategory.WATER_SHORTAGE: 33,
        ReportCategory.TRAFFIC: 28,
        ReportCategory.FUEL_QUEUE: 24,
    }
    status_weights = {
        ReportStatus.PENDING: 25,
        ReportStatus.ACKNOWLEDGED: 15,
        ReportStatus.IN_PROGRESS: 8,
        ReportStatus.RESOLVED: 0,
        ReportStatus.CLOSED: 0,
    }
    alert_rail = []
    for report in reports_qs.exclude(status__in=[ReportStatus.RESOLVED, ReportStatus.CLOSED]).order_by("-created_at")[:50]:
        age_hours = max((timezone.now() - report.created_at).total_seconds() / 3600, 0)
        age_score = min(20, int(age_hours * 4))
        severity_score = min(
            100,
            severity_weights.get(report.category, 20) + status_weights.get(report.status, 0) + age_score,
        )
        if severity_score >= 55:
            alert_rail.append(
                {
                    "id": report.id,
                    "category_label": report.get_category_display(),
                    "status_label": report.get_status_display(),
                    "location": report.location,
                    "created_at": report.created_at,
                    "severity_score": severity_score,
                    "age_hours": round(age_hours, 1),
                    "map_url": reverse("core:map"),
                    "reports_url": reverse("core:reports"),
                }
            )
    alert_rail = sorted(alert_rail, key=lambda item: item["severity_score"], reverse=True)[:6]

    now_local = timezone.localtime()
    schedule_today_qs = PowerSchedule.objects.filter(outage_date=now_local.date())
    areas_currently_off = []
    upcoming_outages = []
    for row in schedule_today_qs.order_by("start_time", "area"):
        start_dt, end_dt = _schedule_row_bounds(row)
        if start_dt <= now_local < end_dt:
            areas_currently_off.append(row)
        elif now_local < start_dt:
            upcoming_outages.append({"row": row, "starts_in_hours": round((start_dt - now_local).total_seconds() / 3600, 1)})
    areas_currently_off = areas_currently_off[:5]
    upcoming_outages = upcoming_outages[:5]

    if request.GET.get("export") == "csv":
        filename_suffix = selected_city if selected_city != "all" else "all-cities"
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="dashboard-export-{filename_suffix}.csv"'
        writer = csv.writer(response)
        writer.writerow(["metric", "value", "city_scope"])
        writer.writerow(["reports_total", reports_total, city_lookup[selected_city]])
        writer.writerow(["reports_today", reports_today, city_lookup[selected_city]])
        writer.writerow(["pending_queue", pending_queue, city_lookup[selected_city]])
        writer.writerow(["critical_queue_over_2h", critical_queue_count, city_lookup[selected_city]])
        writer.writerow(["verified_by_operator", verified_by_operator, city_lookup[selected_city]])
        writer.writerow(["resolved_today", resolved_today, city_lookup[selected_city]])
        writer.writerow(["map_ready_count", map_ready_count, city_lookup[selected_city]])
        writer.writerow(["map_ready_percent", map_ready_percent, city_lookup[selected_city]])
        return response

    return render(
        request,
        "core/dashboard.html",
        {
            "reports_total": reports_total,
            "reports_today": reports_today,
            "fuel_alerts_today": fuel_alerts_today,
            "traffic_today": traffic_today,
            "dumsor_today": dumsor_today,
            "hospitals_nearby": hospitals_geo,
            "hospitals_total": hospitals_total,
            "reports_by_status": reports_by_status,
            "reports_pending": pending_queue,
            "contacts_total": EmergencyContact.objects.count(),
            "feedback_total": Feedback.objects.count(),
            "recent_reports": recent_reports,
            "chart_day_labels": chart_day_labels,
            "chart_day_values": chart_day_values,
            "chart_cat_labels": chart_cat_labels,
            "chart_cat_values": chart_cat_values,
            "city_options": city_options,
            "selected_city": selected_city,
            "city_label": city_lookup[selected_city],
            "verified_by_operator": verified_by_operator,
            "pending_queue": pending_queue,
            "resolved_today": resolved_today,
            "queue_threshold_minutes": queue_threshold_minutes,
            "critical_queue_count": critical_queue_count,
            "missing_geo_count": missing_geo_count,
            "map_ready_count": map_ready_count,
            "map_ready_percent": map_ready_percent,
            "alert_rail": alert_rail,
            "schedule_today_off": areas_currently_off,
            "schedule_today_upcoming": upcoming_outages,
        },
    )


@staff_member_required(login_url="/admin/login/")
def dashboard_pending_admin_queue(request):
    return redirect(f"{reverse('admin:core_report_changelist')}?status__exact=pending")


def _schedule_row_bounds(row: PowerSchedule):
    tz = timezone.get_current_timezone()
    start_dt = timezone.make_aware(datetime.combine(row.outage_date, row.start_time), tz)
    end_dt = timezone.make_aware(datetime.combine(row.outage_date, row.end_time), tz)
    if end_dt <= start_dt:
        end_dt += timedelta(days=1)
    return start_dt, end_dt


def _normalize_text(value: str):
    text = (value or "").lower().strip()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text


def _ranked_area_matches(query: str, candidates):
    query_n = _normalize_text(query)
    if len(query_n) < 2:
        return []
    ranked = []
    seen = set()
    for c in candidates:
        area = c.area
        key = area.lower()
        if key in seen:
            continue
        seen.add(key)
        area_n = _normalize_text(area)
        score = 0
        if query_n in area_n:
            score = 95 if area_n.startswith(query_n) else 80
        else:
            sim = difflib.SequenceMatcher(None, query_n, area_n).ratio()
            if sim >= 0.74:
                score = int(sim * 100)
        if score > 0:
            ranked.append((score, area))
    ranked.sort(key=lambda x: (-x[0], x[1]))
    return [r[1] for r in ranked]


@require_http_methods(["GET"])
def power_schedule(request):
    q = (request.GET.get("q") or "").strip()
    region = (request.GET.get("region") or "").strip()
    date_raw = (request.GET.get("date") or "").strip()
    today = timezone.localdate()
    selected_date = today
    if date_raw:
        try:
            selected_date = datetime.strptime(date_raw, "%Y-%m-%d").date()
        except ValueError:
            selected_date = today

    qs = PowerSchedule.objects.all()
    if region:
        qs = qs.filter(region__iexact=region)
    qs = qs.filter(outage_date=selected_date)

    area_suggestions = list(
        PowerSchedule.objects.values_list("area", flat=True).distinct().order_by("area")[:2500]
    )
    matched_areas = []
    if q:
        matched_areas = _ranked_area_matches(q, list(qs))
        if matched_areas:
            qs = qs.filter(area__in=matched_areas)
        else:
            qs = qs.none()

    now_local = timezone.localtime()
    status_rows = []
    for row in qs.order_by("area", "start_time"):
        start_dt, end_dt = _schedule_row_bounds(row)
        status = "upcoming"
        countdown_hours = None
        status_text = "Power Expected / No Scheduled Outage Now"
        status_color = "success"
        if row.outage_date != now_local.date():
            status = "scheduled"
            status_text = "Scheduled outage on selected date"
            status_color = "secondary"
        else:
            if start_dt <= now_local < end_dt:
                status = "active"
                status_text = "Scheduled Lights Out Now"
                status_color = "danger"
            elif now_local < start_dt:
                status = "upcoming"
                countdown_hours = round((start_dt - now_local).total_seconds() / 3600, 1)
                status_text = f"Lights Out Starts in {countdown_hours} hours"
                status_color = "warning"
            elif now_local >= end_dt:
                status = "ended"
                status_text = "Power Should Be Restored"
                status_color = "success"
        status_rows.append(
            {
                "row": row,
                "status": status,
                "status_text": status_text,
                "status_color": status_color,
                "countdown_hours": countdown_hours,
            }
        )

    paginator = Paginator(status_rows, 25)
    page_obj = paginator.get_page(request.GET.get("page"))
    regions = list(PowerSchedule.objects.values_list("region", flat=True).distinct().order_by("region"))

    return render(
        request,
        "core/power_schedule.html",
        {
            "page_obj": page_obj,
            "search_q": q,
            "selected_region": region,
            "selected_date": selected_date,
            "regions": regions,
            "area_suggestions": area_suggestions,
            "has_query": bool(q),
            "matched_areas": matched_areas[:8],
            "no_data": len(status_rows) == 0,
        },
    )


@require_http_methods(["GET"])
def healthz(request):
    return JsonResponse({"status": "ok"})
