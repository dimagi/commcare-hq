from django import forms
from corehq.util.timezones import zones
from corehq.util.timezones.utils import coerce_timezone_value


class TimeZoneChoiceField(forms.TypedChoiceField):

    def __init__(self, *args, **kwargs):
        if "choices" not in kwargs:
            kwargs["choices"] = zones.PRETTY_TIMEZONE_CHOICES
        kwargs["coerce"] = coerce_timezone_value
        super(TimeZoneChoiceField, self).__init__(*args, **kwargs)
