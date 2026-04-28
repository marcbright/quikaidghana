import re
import subprocess
from datetime import datetime
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.models import PowerSchedule


KNOWN_REGIONS = {"ACCRA", "TEMA", "CENTRAL", "EASTERN", "VOLTA", "ASHANTI", "WESTERN"}
DATE_RE = re.compile(r"(\d{2}/\d{2}/\d{4})")
GROUP_HEADER_RE = re.compile(r"\b(ACCRA|TEMA|VOLTA|ASHANTI|ASHANT|WESTERN|EASTERN|CENTRAL)\b\s+([ABC])\b")
REGION_ONLY_RE = re.compile(r"^(ACCRA|TEMA|VOLTA|ASHANTI|ASHANT|WESTERN|EASTERN|CENTRAL)\b")
TIME_WINDOW_RE = re.compile(r"\((\d{1,2}:\d{2}\s*[AP]M)\s+TO\s+(\d{1,2}:\d{2}\s*[AP]M)\)", re.IGNORECASE)


def normalize_spaces(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip())


def parse_date(value: str):
    raw = value.strip()
    fmts = ("%d/%m/%Y", "%d/%m/%y", "%d-%m-%Y", "%d-%m-%y", "%m/%d/%Y")
    for fmt in fmts:
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Unable to parse date: {value}")


def parse_time(value: str):
    text = value.replace(".", ":").strip().upper()
    fmts = ("%H:%M", "%I:%M%p", "%I:%M %p")
    for fmt in fmts:
        try:
            return datetime.strptime(text, fmt).time()
        except ValueError:
            continue
    raise ValueError(f"Unable to parse time: {value}")


def clean_area_token(token: str):
    area = token.strip(" .,:;-")
    area = re.sub(r"\s+", " ", area)
    area = area.replace('"', "")
    if len(area) < 3:
        return ""
    if area.lower() in {"etc", "towns", "township"}:
        return ""
    return area


class Command(BaseCommand):
    help = "Import ECG load-management schedule from an official PDF file."

    def add_arguments(self, parser):
        parser.add_argument("pdf_path", type=str, help="Absolute path to ECG schedule PDF")
        parser.add_argument("--source-label", type=str, default="", help="Friendly source label")
        parser.add_argument("--replace-all", action="store_true", help="Delete existing PowerSchedule rows before import")

    def handle(self, *args, **options):
        pdf_path = Path(options["pdf_path"]).expanduser()
        if not pdf_path.exists():
            raise CommandError(f"PDF not found: {pdf_path}")

        source_label = options["source_label"] or pdf_path.name
        if options["replace_all"]:
            PowerSchedule.objects.all().delete()

        text = self._extract_text(pdf_path)
        rows = self._parse_rows(text, source_label)
        if not rows:
            raise CommandError("No schedule rows extracted from PDF. Verify PDF formatting and parser assumptions.")

        created = 0
        skipped = 0
        with transaction.atomic():
            for row in rows:
                _, made = PowerSchedule.objects.get_or_create(
                    region=row["region"],
                    district=row["district"],
                    area=row["area"],
                    outage_date=row["outage_date"],
                    start_time=row["start_time"],
                    end_time=row["end_time"],
                    defaults={"source_file": row["source_file"], "notes": row["notes"]},
                )
                if made:
                    created += 1
                else:
                    skipped += 1

        self.stdout.write(self.style.SUCCESS(f"Imported {created} rows ({skipped} duplicates skipped)."))

    def _extract_text(self, pdf_path: Path):
        try:
            proc = subprocess.run(
                ["pdftotext", "-layout", str(pdf_path), "-"],
                check=True,
                capture_output=True,
                text=True,
            )
        except FileNotFoundError as exc:
            raise CommandError("pdftotext not found. Install poppler-utils to import PDF schedules.") from exc
        except subprocess.CalledProcessError as exc:
            raise CommandError(f"Failed to extract text from PDF: {exc.stderr}") from exc
        return proc.stdout

    def _parse_rows(self, text: str, source_label: str):
        date_slots = self._parse_timetable(text)
        if not date_slots:
            return []

        areas_by_region_group = self._parse_group_areas(text)
        rows = []
        seen = set()

        for (region, group), areas in areas_by_region_group.items():
            for area in sorted(areas):
                for item in date_slots:
                    if item["group"] != group:
                        continue
                    key = (region, area.lower(), item["date"], item["start"], item["end"])
                    if key in seen:
                        continue
                    seen.add(key)
                    rows.append(
                        {
                            "region": region,
                            "district": "",
                            "area": area,
                            "outage_date": item["date"],
                            "start_time": item["start"],
                            "end_time": item["end"],
                            "source_file": source_label,
                            "notes": f"Group {group}",
                        }
                    )
        return rows

    def _parse_timetable(self, text: str):
        lines = [normalize_spaces(l) for l in text.splitlines() if normalize_spaces(l)]
        dates = []
        slots = []
        for line in lines[:60]:
            ds = DATE_RE.findall(line)
            if len(ds) >= 5:
                dates = [parse_date(d) for d in ds]
                break
        if not dates:
            return []

        for line in lines[:120]:
            if "DAY (" not in line.upper() and "NIGHT (" not in line.upper():
                continue
            window = TIME_WINDOW_RE.search(line)
            if not window:
                continue
            start_time = parse_time(window.group(1))
            end_time = parse_time(window.group(2))
            groups = re.findall(r"\b([ABC])\b", line.upper())
            if len(groups) < len(dates):
                continue
            for idx, date_value in enumerate(dates):
                slots.append(
                    {
                        "date": date_value,
                        "start": start_time,
                        "end": end_time,
                        "group": groups[idx],
                    }
                )
        return slots

    def _parse_group_areas(self, text: str):
        data = {}
        current_key = None
        pending_group = None
        buffered_tokens = set()
        for raw_line in text.splitlines():
            line = normalize_spaces(raw_line.replace("\x0c", " "))
            if not line:
                continue
            if "LOAD MANAGEMENT" in line.upper() or "AREAS TO BE AFFECTED" in line.upper():
                continue

            if re.fullmatch(r"[ABC]", line.upper()):
                pending_group = line.upper()
                continue

            match = GROUP_HEADER_RE.search(line.upper())
            if match:
                region = "ASHANTI" if match.group(1) == "ASHANT" else match.group(1)
                group = match.group(2)
                current_key = (region, group)
                data.setdefault(current_key, set())
                if buffered_tokens:
                    data[current_key].update(buffered_tokens)
                    buffered_tokens.clear()
                tail = line[match.end() :].strip(" -,:")
                self._collect_areas_into(data[current_key], tail)
                pending_group = None
                continue

            region_only = REGION_ONLY_RE.search(line.upper())
            if region_only and pending_group:
                region = "ASHANTI" if region_only.group(1) == "ASHANT" else region_only.group(1)
                current_key = (region, pending_group)
                data.setdefault(current_key, set())
                if buffered_tokens:
                    data[current_key].update(buffered_tokens)
                    buffered_tokens.clear()
                tail = line[region_only.end() :].strip(" -,:")
                self._collect_areas_into(data[current_key], tail)
                pending_group = None
            elif current_key:
                self._collect_areas_into(data[current_key], line)
            else:
                if "," in line or ";" in line:
                    self._collect_areas_into(buffered_tokens, line)

        return data

    def _collect_areas_into(self, bucket, text_line: str):
        for token in re.split(r"[;,]", text_line):
            area = clean_area_token(token)
            if area:
                bucket.add(area)
