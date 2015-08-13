from corehq.apps.groups.fields import GroupField
from django import forms
from django.utils.translation import ugettext as _
from corehq.apps.app_manager.fields import ApplicationDataSourceUIHelper
from corehq.apps.performance_sms.models import TemplateVariable, ScheduleConfiguration, SCHEDULE_CHOICES
from corehq.apps.reports.daterange import get_simple_dateranges
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit


class PerformanceMessageEditForm(forms.Form):
    recipient_id = forms.CharField()
    schedule = forms.ChoiceField(choices=[(choice, choice) for choice in SCHEDULE_CHOICES])
    template = forms.CharField(widget=forms.Textarea)
    time_range = forms.ChoiceField(
        choices=[(choice.slug, choice.description) for choice in get_simple_dateranges()]
    )

    def __init__(self, domain, config, *args, **kwargs):
        super(PerformanceMessageEditForm, self).__init__(*args, **kwargs)
        self.domain = domain
        self.config = config

        self.fields['recipient_id'] = GroupField(domain=domain, label=_('Recipient Group'))

        self.app_source_helper = ApplicationDataSourceUIHelper(enable_cases=False)
        self.app_source_helper.bootstrap(self.domain)
        data_source_fields = self.app_source_helper.get_fields()
        self.fields.update(data_source_fields)

        self.helper = FormHelper()
        self.helper.form_class = "form-horizontal"
        self.helper.form_id = "performance-form"
        self.helper.form_method = 'post'
        self.helper.add_input(Submit('submit', _('Save Changes')))

    def clean_schedule(self):
        # todo: support other scheduling options
        return ScheduleConfiguration(interval=self.cleaned_data['schedule'])

    def save(self, commit=True):
        self.config.recipient_id = self.cleaned_data['recipient_id']
        self.config.schedule = self.cleaned_data['schedule']
        self.config.template = self.cleaned_data['template']
        # todo: support more than one data source
        template_variable = TemplateVariable(
            type=self.cleaned_data['source_type'],
            time_range=self.cleaned_data['time_range'],
            source_id=self.cleaned_data['source'],
            app_id=self.cleaned_data['application'],
        )
        self.config.template_variables = [template_variable]
        if commit:
            self.config.save()
        return self.config
