import json
from django import forms
from django.utils.translation import ugettext as _
from corehq.apps.userreports.models import DataSourceConfiguration
from corehq.apps.userreports.ui.widgets import JsonWidget


class ReportDataSourceField(forms.ChoiceField):

    def __init__(self, domain, *args, **kwargs):
        self.domain = domain
        available_data_sources = DataSourceConfiguration.by_domain(self.domain)
        super(ReportDataSourceField, self).__init__(
            choices=[(src._id, src.display_name) for src in available_data_sources],
            *args, **kwargs
        )


class JsonField(forms.CharField):
    widget = JsonWidget
    expected_type = None

    def __init__(self, expected_type=None, *args, **kwargs):
        self.expected_type = expected_type
        super(JsonField, self).__init__(*args, **kwargs)

    def prepare_value(self, value):
        if isinstance(value, basestring):
            try:
                return json.loads(value)
            except ValueError:
                return value
        else:
            return value

    def validate(self, value):
        super(JsonField, self).validate(value)
        try:
            value = json.loads(value)
        except ValueError:
            raise forms.ValidationError(_(u'Please enter valid JSON. This is not valid: {}'.format(value)))
        if self.expected_type and not isinstance(value, self.expected_type):
            raise forms.ValidationError(_(u'Expected {} but was {}'.format(self.expected_type, type(value))))

    def clean(self, value):
        return json.loads(super(JsonField, self).clean(value))
