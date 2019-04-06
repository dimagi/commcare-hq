from __future__ import absolute_import
from __future__ import unicode_literals
import json
from django import forms
from django.utils.translation import ugettext as _

from corehq import toggles
from corehq.apps.userreports.models import DataSourceConfiguration, \
    StaticDataSourceConfiguration
from corehq.apps.userreports.ui.widgets import JsonWidget
from corehq.util.python_compatibility import soft_assert_type_text
import six


class ReportDataSourceField(forms.ChoiceField):

    def __init__(self, domain, *args, **kwargs):
        self.domain = domain
        standard_sources = DataSourceConfiguration.by_domain(self.domain)
        custom_sources = list(StaticDataSourceConfiguration.by_domain(domain))
        available_data_sources = standard_sources + custom_sources
        if toggles.AGGREGATE_UCRS.enabled(domain):
            from corehq.apps.aggregate_ucrs.models import AggregateTableDefinition
            available_data_sources += AggregateTableDefinition.objects.filter(domain=self.domain)
        super(ReportDataSourceField, self).__init__(
            choices=[(src.data_source_id, src.display_name) for src in available_data_sources],
            *args, **kwargs
        )


class JsonField(forms.CharField):
    widget = JsonWidget
    expected_type = None
    default_null_values = (None, '', ())

    def __init__(self, expected_type=None, null_values=None, *args, **kwargs):
        self.expected_type = expected_type
        self.null_values = null_values if null_values is not None else self.default_null_values
        super(JsonField, self).__init__(*args, **kwargs)

    def prepare_value(self, value):
        if isinstance(value, six.string_types):
            soft_assert_type_text(value)
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
            raise forms.ValidationError(_('Please enter valid JSON. This is not valid: {}'.format(value)))

    def validate(self, value):
        if value in self.null_values and self.required:
            raise forms.ValidationError(self.error_messages['required'])
        if self.expected_type and not isinstance(value, self.expected_type):
            raise forms.ValidationError(_('Expected {} but was {}'.format(self.expected_type, type(value))))
