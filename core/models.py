from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class ReportCategory(models.TextChoices):
    DUMSOR = "dumsor", "Dumsor"
    FUEL_QUEUE = "fuel_queue", "Fuel Queue"
    TRAFFIC = "traffic", "Traffic"
    WATER_SHORTAGE = "water_shortage", "Water Shortage"
    ACCIDENT = "accident", "Accident"
    FLOODING = "flooding", "Flooding"


class ReportStatus(models.TextChoices):
    PENDING = "pending", "Pending review"
    ACKNOWLEDGED = "acknowledged", "Acknowledged"
    IN_PROGRESS = "in_progress", "In progress"
    RESOLVED = "resolved", "Resolved"
    CLOSED = "closed", "Closed"


class Report(models.Model):
    """User-submitted civic / utility incident (map-ready)."""

    category = models.CharField(
        max_length=32,
        choices=ReportCategory.choices,
        db_index=True,
    )
    location = models.CharField(
        max_length=255,
        help_text="Human-readable place (e.g. neighbourhood, landmark, junction).",
    )
    description = models.TextField()
    status = models.CharField(
        max_length=32,
        choices=ReportStatus.choices,
        default=ReportStatus.PENDING,
        db_index=True,
    )
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        validators=[MinValueValidator(-90), MaxValueValidator(90)],
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        validators=[MinValueValidator(-180), MaxValueValidator(180)],
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["-created_at", "category"]),
            models.Index(fields=["status", "-created_at"]),
        ]
        verbose_name = "Report"
        verbose_name_plural = "Reports"

    def __str__(self) -> str:
        return f"{self.get_category_display()} — {self.location} ({self.get_status_display()})"


class Hospital(models.Model):
    """Hospital or major clinic for emergency routing."""

    name = models.CharField(max_length=255)
    location = models.CharField(max_length=255)
    phone = models.CharField(max_length=32, blank=True)
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        validators=[MinValueValidator(-90), MaxValueValidator(90)],
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        validators=[MinValueValidator(-180), MaxValueValidator(180)],
    )

    class Meta:
        ordering = ("name",)
        indexes = [
            models.Index(fields=["name"]),
        ]
        verbose_name = "Hospital"
        verbose_name_plural = "Hospitals"

    def __str__(self) -> str:
        return self.name


class EmergencyContact(models.Model):
    """National / regional emergency and helpline numbers."""

    service_name = models.CharField(max_length=128)
    phone_number = models.CharField(max_length=32)

    class Meta:
        ordering = ("service_name",)
        verbose_name = "Emergency contact"
        verbose_name_plural = "Emergency contacts"

    def __str__(self) -> str:
        return f"{self.service_name} ({self.phone_number})"


class Feedback(models.Model):
    """Site or product feedback from visitors."""

    name = models.CharField(max_length=120)
    email = models.EmailField()
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "Feedback"
        verbose_name_plural = "Feedback"

    def __str__(self) -> str:
        return f"{self.name} — {self.created_at:%Y-%m-%d}"


class PowerSchedule(models.Model):
    """Normalized ECG load-management schedule row per area/time window."""

    region = models.CharField(max_length=64, db_index=True)
    district = models.CharField(max_length=128, blank=True, db_index=True)
    area = models.CharField(max_length=255, db_index=True)
    outage_date = models.DateField(db_index=True)
    start_time = models.TimeField()
    end_time = models.TimeField()
    source_file = models.CharField(max_length=255)
    notes = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ("outage_date", "start_time", "region", "area")
        indexes = [
            models.Index(fields=["region", "outage_date"]),
            models.Index(fields=["district", "outage_date"]),
            models.Index(fields=["area", "outage_date"]),
            models.Index(fields=["outage_date", "start_time"]),
        ]
        verbose_name = "Power schedule"
        verbose_name_plural = "Power schedules"

    def __str__(self) -> str:
        return f"{self.area} ({self.region}) {self.outage_date:%Y-%m-%d} {self.start_time:%H:%M}-{self.end_time:%H:%M}"
