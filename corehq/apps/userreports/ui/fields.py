import json
from django import forms
from corehq.apps.userreports.models import IndicatorConfiguration
from corehq.apps.userreports.ui.widgets import JsonWidget


class ReportDataSourceField(forms.ChoiceField):

    def __init__(self, domain, *args, **kwargs):
        self.domain = domain
        available_data_sources = IndicatorConfiguration.by_domain(self.domain)
        super(ReportDataSourceField, self).__init__(
            choices=[(src._id, src.display_name) for src in available_data_sources],
            *args, **kwargs
        )


class JsonField(forms.CharField):
    widget = JsonWidget

    def prepare_value(self, value):
        if isinstance(value, basestring):
            return json.loads(value)
        else:
            return value

    def validate(self, value):
        super(JsonField, self).validate(value)
        try:
            json.loads(value)
        except:
            raise

    def clean(self, value):
        return json.loads(super(JsonField, self).clean(value))
