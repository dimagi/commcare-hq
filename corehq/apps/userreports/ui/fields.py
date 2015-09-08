import json
from django import forms
from django.utils.translation import ugettext as _
from corehq.apps.userreports.models import DataSourceConfiguration, \
    StaticDataSourceConfiguration
from corehq.apps.userreports.ui.widgets import JsonWidget


class ReportDataSourceField(forms.ChoiceField):

    def __init__(self, domain, *args, **kwargs):
        self.domain = domain
        standard_sources = DataSourceConfiguration.by_domain(self.domain)
        custom_sources = list(StaticDataSourceConfiguration.by_domain(domain))
        available_data_sources = standard_sources + custom_sources
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

    def to_python(self, value):
        val = super(JsonField, self).to_python(value)
        try:
            return json.loads(val)
        except:
            raise forms.ValidationError(_(u'Please enter valid JSON. This is not valid: {}'.format(value)))

    def validate(self, value):
        if value in (None, '', ()) and self.required:
            raise forms.ValidationError(self.error_messages['required'])
        if self.expected_type and not isinstance(value, self.expected_type):
            raise forms.ValidationError(_(u'Expected {} but was {}'.format(self.expected_type, type(value))))
