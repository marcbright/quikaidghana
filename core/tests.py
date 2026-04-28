from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import PowerSchedule


class PowerSchedulePageTests(TestCase):
    def setUp(self):
        today = timezone.localdate()
        PowerSchedule.objects.create(
            region="ACCRA",
            district="Adenta Municipal",
            area="Madina",
            outage_date=today,
            start_time=timezone.datetime.strptime("10:00", "%H:%M").time(),
            end_time=timezone.datetime.strptime("16:00", "%H:%M").time(),
            source_file="test.pdf",
            notes="",
        )

    def test_power_schedule_page_loads(self):
        response = self.client.get(reverse("core:power_schedule"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ECG Power Schedule Tracker")

    def test_area_search_returns_result(self):
        response = self.client.get(reverse("core:power_schedule"), {"q": "madina"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Madina")
