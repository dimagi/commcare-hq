from corehq.apps.hqwebapp.crispy import FieldWithHelpBubble
from crispy_forms import layout as crispy
from django import forms
from django.utils.translation import ugettext as _
from corehq.apps.app_manager.fields import ApplicationDataSourceUIHelper
from crispy_forms.bootstrap import FormActions
from crispy_forms.helper import FormHelper


class PerformanceMessageEditForm(forms.Form):
    recipient_id = forms.CharField()
    schedule = forms.CharField()  # todo
    template = forms.CharField()


    def __init__(self, domain, *args, **kwargs):
        super(PerformanceMessageEditForm, self).__init__(*args, **kwargs)
        self.domain = domain

        self.helper = FormHelper()
        self.helper.form_class = "form-horizontal"
        self.helper.form_id = "performance-form"

        self.app_source_helper = ApplicationDataSourceUIHelper(enable_cases=False)
        self.app_source_helper.bootstrap(self.domain)
        data_source_fields = self.app_source_helper.get_fields()
        # todo: help texts?
        data_source_help_texts = {
            "application": _("Which application should the data come from?"),
            "source": _("Choose form you want to count in the message template."),
        }
        self.fields.update(data_source_fields)
        data_source_crispy_fields = []
        for k in data_source_fields.keys():
            if k in data_source_help_texts:
                data_source_crispy_fields.append(FieldWithHelpBubble(
                    k, help_bubble_text=data_source_help_texts[k]
                ))
            else:
                data_source_crispy_fields.append(k)


        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                _('Data Source'), *data_source_crispy_fields
            ),
            FormActions(
                crispy.ButtonHolder(
                    crispy.Submit(
                        'create_new_report_builder_btn',
                        _('Next'),
                    )
                ),
            ),
        )
