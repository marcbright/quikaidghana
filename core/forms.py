from django import forms

from .models import Feedback, Report


class ReportForm(forms.ModelForm):
    """Public incident report — coordinates optional but must be paired."""

    class Meta:
        model = Report
        fields = ("category", "location", "description", "latitude", "longitude")
        labels = {
            "category": "What are you reporting?",
            "location": "Where did this happen?",
            "description": "Describe the situation",
            "latitude": "Latitude (optional)",
            "longitude": "Longitude (optional)",
        }
        help_texts = {
            "category": "Choose the closest match — operators can refine later.",
            "location": "Landmark, junction, neighbourhood, or street context.",
            "description": "Facts, time, and what people should watch for. Avoid names unless relevant to safety.",
            "latitude": "Filled when you search, use your location, or click the map — or type decimals here.",
            "longitude": "Must be provided together with latitude if you set either field.",
        }
        widgets = {
            "category": forms.Select(
                attrs={
                    "class": "form-select qa-report-input",
                    "autocomplete": "off",
                }
            ),
            "location": forms.TextInput(
                attrs={
                    "class": "form-control qa-report-input",
                    "placeholder": "e.g. Lapaz bus interchange, Ring Road East",
                    "autocomplete": "street-address",
                    "maxlength": 255,
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "rows": 6,
                    "class": "form-control qa-report-input",
                    "placeholder": "What happened? When? Who might be affected?",
                }
            ),
            "latitude": forms.NumberInput(
                attrs={
                    "class": "form-control qa-report-input",
                    "step": "any",
                    "placeholder": "e.g. 5.6037",
                    "inputmode": "decimal",
                }
            ),
            "longitude": forms.NumberInput(
                attrs={
                    "class": "form-control qa-report-input",
                    "step": "any",
                    "placeholder": "e.g. -0.1870",
                    "inputmode": "decimal",
                }
            ),
        }

    def clean_description(self):
        text = (self.cleaned_data.get("description") or "").strip()
        if len(text) < 12:
            raise forms.ValidationError("Please add a bit more detail (at least 12 characters).")
        return text

    def clean(self):
        cleaned = super().clean()
        lat = cleaned.get("latitude")
        lon = cleaned.get("longitude")
        has_lat = lat is not None
        has_lon = lon is not None
        if has_lat and not has_lon:
            self.add_error(
                "longitude",
                "Enter longitude as well, or clear latitude to skip coordinates.",
            )
        if has_lon and not has_lat:
            self.add_error(
                "latitude",
                "Enter latitude as well, or clear longitude to skip coordinates.",
            )
        return cleaned

    def highlight_errors(self) -> None:
        """After a failed POST, add Bootstrap is-invalid to errored widgets."""
        if not self.errors:
            return
        for name in self.errors:
            widget = self.fields[name].widget
            classes = widget.attrs.get("class", "")
            if "is-invalid" not in classes:
                widget.attrs["class"] = (classes + " is-invalid").strip()


class FeedbackForm(forms.ModelForm):
    """Public contact / feedback — persisted on the Feedback model."""

    class Meta:
        model = Feedback
        fields = ("name", "email", "message")
        labels = {
            "name": "Your name",
            "email": "Work or personal email",
            "message": "How can we help?",
        }
        help_texts = {
            "name": "So we can address you properly in our reply.",
            "email": "We never sell your address — only used to respond.",
            "message": "Partnerships, press, product ideas, or support — be as specific as you like.",
        }
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "form-control qa-contact-input",
                    "placeholder": "e.g. Ama Mensah",
                    "autocomplete": "name",
                    "maxlength": 120,
                }
            ),
            "email": forms.EmailInput(
                attrs={
                    "class": "form-control qa-contact-input",
                    "placeholder": "you@example.com",
                    "autocomplete": "email",
                }
            ),
            "message": forms.Textarea(
                attrs={
                    "rows": 6,
                    "class": "form-control qa-contact-input",
                    "placeholder": "Tell us what you need — timelines, links, and context help.",
                }
            ),
        }

    def highlight_errors(self) -> None:
        """After a failed POST, add Bootstrap is-invalid to errored widgets."""
        if not self.errors:
            return
        for name in self.errors:
            widget = self.fields[name].widget
            classes = widget.attrs.get("class", "")
            if "is-invalid" not in classes:
                widget.attrs["class"] = (classes + " is-invalid").strip()
