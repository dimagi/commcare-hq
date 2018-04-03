from __future__ import absolute_import
from __future__ import unicode_literals
from django import forms
from django.utils.translation import ugettext as _
from corehq.apps.calendar_fixture.models import CalendarFixtureSettings
from crispy_forms.helper import FormHelper
from crispy_forms import layout
from crispy_forms.bootstrap import StrictButton


class CalendarFixtureForm(forms.ModelForm):
    class Meta(object):
        model = CalendarFixtureSettings
        fields = ['days_before', 'days_after']

    def __init__(self, *args, **kwargs):
        super(CalendarFixtureForm, self).__init__(*args, **kwargs)
        self.fields['days_before'].label = _('Start calendar this many days in the past.')
        self.fields['days_after'].label = _('End calendar this many days in the future.')
        self.helper = FormHelper()
        self.helper.form_class = 'form-horizontal'
        self.helper.label_class = 'col-sm-3 col-md-3'
        self.helper.field_class = 'col-sm-3 col-md-3'
        self.helper.layout = layout.Layout(
            'days_before',
            'days_after',
            StrictButton(
                _("Update Settings"),
                type="submit",
                css_class='btn-primary',
            )
        )
