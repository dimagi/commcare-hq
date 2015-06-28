from django import forms
from django.utils.translation import ugettext as _

from crispy_forms.bootstrap import FormActions
from crispy_forms.helper import FormHelper
from crispy_forms import layout as crispy

from corehq.apps.app_manager.models import get_apps_in_domain


class CreateFormExportForm(forms.Form):
    application = forms.ChoiceField()
    module = forms.ChoiceField()
    form = forms.ChoiceField()

    def __init__(self, domain, *args, **kwargs):
        super(CreateFormExportForm, self).__init__(*args, **kwargs)
        self.fields['application'].choices = [
            (app._id, app.name) for app in get_apps_in_domain(domain)
        ]
        self.fields['module'].choices = [
            (module.unique_id, module.name)
            for app in get_apps_in_domain(domain)
            for module in app.modules
        ]
        self.fields['form'].choices = [
            (form.get_unique_id(), form.name)
            for app in get_apps_in_domain(domain)
            for form in app.get_forms()
        ]

        self.helper = FormHelper()
        self.helper.form_id = "create-export-form"
        self.helper.form_class = "form-horizontal"

        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                _('Select Form'),
                crispy.Field(
                    'application',
                    data_bind='value: appId',
                ),
                crispy.Field(
                    'module',
                    data_bind="options: moduleOptions, optionsText: 'text', optionsValue: 'value', value: moduleId",
                ),
                crispy.Field(
                    'form',
                    data_bind="options: formOptions, optionsText: 'text', optionsValue: 'value'",
                ),
            ),
            FormActions(
                crispy.ButtonHolder(
                    crispy.Submit(
                        'create_export',
                        _('Next'),
                    ),
                ),
            ),
        )
