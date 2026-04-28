from django.contrib import admin

from .models import EmergencyContact, Feedback, Hospital, PowerSchedule, Report, ReportStatus


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "category_display",
        "location",
        "status",
        "description_excerpt",
        "coordinates_ok",
        "created_at",
    )
    list_display_links = ("id", "location")
    list_editable = ("status",)
    list_filter = (
        "category",
        "status",
        ("created_at", admin.DateFieldListFilter),
    )
    search_fields = ("location", "description", "category", "status")
    ordering = ("-created_at",)
    date_hierarchy = "created_at"
    readonly_fields = ("created_at",)
    list_per_page = 50
    save_on_top = True
    actions = ("mark_acknowledged", "mark_in_progress", "mark_resolved", "mark_closed")

    fieldsets = (
        (
            "Classification",
            {"fields": ("category", "status")},
        ),
        (
            "Where & what",
            {"fields": ("location", "description")},
        ),
        (
            "Coordinates",
            {
                "fields": ("latitude", "longitude"),
                "description": "Optional — used for maps and nearby search.",
                "classes": ("collapse",),
            },
        ),
        (
            "Record",
            {"fields": ("created_at",)},
        ),
    )

    @admin.display(description="Category", ordering="category")
    def category_display(self, obj: Report) -> str:
        return obj.get_category_display()

    @admin.display(description="Description")
    def description_excerpt(self, obj: Report) -> str:
        text = (obj.description or "").strip().replace("\n", " ")
        if len(text) <= 100:
            return text or "—"
        return f"{text[:100]}…"

    @admin.display(description="Map", boolean=True)
    def coordinates_ok(self, obj: Report) -> bool:
        return obj.latitude is not None and obj.longitude is not None

    @admin.action(description="Mark selected as acknowledged")
    def mark_acknowledged(self, request, queryset):
        queryset.update(status=ReportStatus.ACKNOWLEDGED)

    @admin.action(description="Mark selected as in progress")
    def mark_in_progress(self, request, queryset):
        queryset.update(status=ReportStatus.IN_PROGRESS)

    @admin.action(description="Mark selected as resolved")
    def mark_resolved(self, request, queryset):
        queryset.update(status=ReportStatus.RESOLVED)

    @admin.action(description="Mark selected as closed")
    def mark_closed(self, request, queryset):
        queryset.update(status=ReportStatus.CLOSED)

    def get_fieldsets(self, request, obj=None):
        fieldsets = list(self.fieldsets)
        if obj is None:
            fieldsets = [fs for fs in fieldsets if fs[0] != "Record"]
        return fieldsets

    def get_readonly_fields(self, request, obj=None):
        if obj is None:
            return ()
        return self.readonly_fields


@admin.register(Hospital)
class HospitalAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "location",
        "phone",
        "coordinates_ok",
    )
    list_display_links = ("id", "name")
    list_filter = (
        ("latitude", admin.EmptyFieldListFilter),
        ("phone", admin.EmptyFieldListFilter),
    )
    search_fields = ("name", "location", "phone")
    ordering = ("name",)
    list_per_page = 50
    save_on_top = True

    fieldsets = (
        (None, {"fields": ("name", "location", "phone")}),
        (
            "Coordinates",
            {"fields": ("latitude", "longitude"), "classes": ("collapse",)},
        ),
    )

    @admin.display(description="Map", boolean=True)
    def coordinates_ok(self, obj: Hospital) -> bool:
        return obj.latitude is not None and obj.longitude is not None


@admin.register(EmergencyContact)
class EmergencyContactAdmin(admin.ModelAdmin):
    list_display = ("id", "service_name", "phone_number")
    list_display_links = ("id", "service_name")
    search_fields = ("service_name", "phone_number")
    ordering = ("service_name",)
    list_per_page = 100
    save_on_top = True


@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "email",
        "message_excerpt",
        "created_at",
    )
    list_display_links = ("id", "name")
    list_filter = (("created_at", admin.DateFieldListFilter),)
    search_fields = ("name", "email", "message")
    ordering = ("-created_at",)
    date_hierarchy = "created_at"
    readonly_fields = ("created_at",)
    list_per_page = 40
    save_on_top = True

    fieldsets = (
        (None, {"fields": ("name", "email")}),
        ("Message", {"fields": ("message",)}),
        ("Record", {"fields": ("created_at",)}),
    )

    @admin.display(description="Message")
    def message_excerpt(self, obj: Feedback) -> str:
        text = (obj.message or "").strip().replace("\n", " ")
        if len(text) <= 80:
            return text or "—"
        return f"{text[:80]}…"

    def get_fieldsets(self, request, obj=None):
        fieldsets = list(self.fieldsets)
        if obj is None:
            fieldsets = [fs for fs in fieldsets if fs[0] != "Record"]
        return fieldsets

    def get_readonly_fields(self, request, obj=None):
        if obj is None:
            return ()
        return self.readonly_fields


@admin.register(PowerSchedule)
class PowerScheduleAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "region",
        "district",
        "area",
        "outage_date",
        "start_time",
        "end_time",
        "source_file",
    )
    list_display_links = ("id", "area")
    list_filter = ("region", "outage_date")
    search_fields = ("region", "district", "area", "notes", "source_file")
    ordering = ("outage_date", "start_time", "region", "area")
    readonly_fields = ("created_at",)


admin.site.site_header = "QuickAid Ghana"
admin.site.site_title = "QuickAid Admin"
admin.site.index_title = "Control centre"
