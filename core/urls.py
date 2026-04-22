from django.urls import path

from . import views

app_name = "core"

# HTML pages first; JSON helpers under api/ (same namespace core:…).
urlpatterns = [
    path("", views.home, name="home"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("report/", views.report, name="report"),
    path("reports/", views.reports_list, name="reports"),
    path("chatbot/", views.chatbot, name="chatbot"),
    path("sos/", views.sos, name="sos"),
    path("map/", views.map_page, name="map"),
    path("about/", views.about, name="about"),
    path("contact/", views.contact, name="contact"),
    path("healthz/", views.healthz, name="healthz"),
    path("api/chatbot/", views.chatbot_reply, name="chatbot_reply"),
    path("api/geocode/", views.geocode_search, name="geocode"),
]
