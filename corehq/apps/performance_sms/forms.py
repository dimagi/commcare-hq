from corehq.apps.groups.fields import GroupField
from django import forms
from django.utils.translation import ugettext as _
from corehq.apps.app_manager.fields import ApplicationDataSourceUIHelper
from crispy_forms.helper import FormHelper


class PerformanceMessageEditForm(forms.Form):
    recipient_id = forms.CharField()
    schedule = forms.CharField()  # todo
    template = forms.CharField()

    def __init__(self, domain, *args, **kwargs):
        super(PerformanceMessageEditForm, self).__init__(*args, **kwargs)
        self.domain = domain

        self.fields['recipient_id'] = GroupField(domain=domain, label=_('Recipient Group'))

        self.app_source_helper = ApplicationDataSourceUIHelper(enable_cases=False)
        self.app_source_helper.bootstrap(self.domain)
        data_source_fields = self.app_source_helper.get_fields()
        # todo: help texts?
        data_source_help_texts = {
            "application": _("Which application should the data come from?"),
            "source": _("Choose form you want to count in the message template."),
        }
        self.fields.update(data_source_fields)

        self.helper = FormHelper()
        self.helper.form_class = "form-horizontal"
        self.helper.form_id = "performance-form"
